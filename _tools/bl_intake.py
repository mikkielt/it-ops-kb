"""The backlog's intake: deterministic detectors, each finding a candidate item, filed once by fingerprint.

`backlog.py intake` (the command and its exit codes are in backlog.py's docstring) is the facade; this module holds
the part that does not touch the backlog's files:

- the registry `DETECTORS`: detector name -> a function `fn(root: Path) -> iterable of Candidate`, added with the
  `@detector("name")` decorator. A detector reads the repository under `root` and nothing else: no network, no model,
  no clock, so the same inputs give the same candidates in any clone;
- `Candidate`: what a detector reports (kind bug or story, title, goal, a `key` naming the finding, a bug's severity,
  a story's checks, extra links);
- `fingerprint(detector, key)`: 12 hex characters naming one finding; the same detector and key give the same one, so a
  finding is filed once however often intake runs;
- `collect(root)`: every detector's candidates in a fixed order, each with its fingerprint, and the detectors that
  failed;
- `item_of(candidate, iid)`: the draft item `--file` writes (outside any sprint; a bug's repro is
  `intake --status <fingerprint>`);
- `open_with_fingerprint(items, fp)`: the open item whose links already carry the fingerprint, which skips the
  candidate;
- `lines(candidate)`: the lines the command prints for one candidate;
- the `drift` detector (`scan_drift`, `drift_detector`): items whose state disagrees with their commits;
- the `trailers` detector (`trailer_findings`, `trailers_detector`, at the end): commits of main whose KB-Work line git
  does not read, or that change code with no KB-Work and no KB-Auto trailer.

This module imports no tool module but `kbpublic` (the integration remote's name, inside the function that needs it);
it is below backlog.py.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

DETECTORS = {}  # name -> fn(root) -> iterable of Candidate; the registry
KINDS = ("bug", "story")
SEVERITIES = ("S1", "S2", "S3", "S4")
FP_RE = re.compile(r"[0-9a-f]{12}")
FP_LINK = "fingerprint "  # a link `fingerprint <12 hex>`, the same marker red-pipeline's bugs carry
STATUS_REPRO = ["python3", "_tools/backlog.py", "intake", "--status"]  # + the fingerprint: a filed bug's repro
TEXT_MAX = 2000  # backlog.py's limit for one field's text; a candidate is cut to it


@dataclass
class Candidate:
    """One finding of a detector. `key` names it (a path, a rule id, a test id: nothing that differs between two runs
    on the same repository); the fingerprint hashes the detector's name and the key."""
    kind: str
    title: str
    goal: str
    key: str
    severity: str = "S3"  # a bug's
    checks: list = field(default_factory=list)  # a story's: argv lists proving the end state
    links: list = field(default_factory=list)  # besides the fingerprint
    notes: str = ""
    detector: str = ""  # set by collect()
    fp: str = ""  # set by collect()


def detector(name):
    """Register the decorated function as the detector `name`."""
    def add(fn):
        DETECTORS[name] = fn
        return fn
    return add


def fingerprint(name, key):
    """12 hex characters naming the finding `key` of detector `name`."""
    return hashlib.sha256(f"{name}\n{key}".encode("utf-8")).hexdigest()[:12]


def problem(c):
    """Why a candidate cannot be filed, or None."""
    if c.kind not in KINDS:
        return f"kind {c.kind!r} is not one of {', '.join(KINDS)}"
    for f in ("title", "goal", "key"):
        if not isinstance(getattr(c, f), str) or not getattr(c, f).strip():
            return f"{f} is empty"
    if c.kind == "bug" and c.severity not in SEVERITIES:
        return f"severity {c.severity!r} is not one of {', '.join(SEVERITIES)}"
    if c.kind == "story" and not (c.checks and all(isinstance(x, list) and x and all(isinstance(y, str) for y in x)
                                                   for x in c.checks)):
        return "a story needs checks: argv lists that prove its end state"
    if not isinstance(c.links, list) or not all(isinstance(x, str) and x.strip() for x in c.links):
        return "links must be a list of non-empty strings"
    return None


def collect(root, only=None):
    """(candidates, failures) over the registry: the candidates of every detector (or the one named `only`) sorted by
    detector name, then fingerprint, each with `detector` and `fp` set, a finding reported twice kept once; the
    failures as `detector: why` lines (a detector that raised, a candidate that `problem` refuses)."""
    out, failures, seen = [], [], set()
    for name in sorted(DETECTORS):
        if only is not None and name != only:
            continue
        try:
            found = list(DETECTORS[name](Path(root)))
        except Exception as e:  # noqa: BLE001 - one broken detector must not hide the others' findings
            failures.append(f"{name}: raised {type(e).__name__}: {e}")
            continue
        for c in found:
            why = problem(c)
            if why:
                failures.append(f"{name}: candidate {getattr(c, 'title', '')!r} refused: {why}")
                continue
            c.detector, c.fp = name, fingerprint(name, c.key)
            if c.fp not in seen:
                seen.add(c.fp)
                out.append(c)
    out.sort(key=lambda c: (c.detector, c.fp))
    return out, failures


def open_with_fingerprint(items, fp):
    """The id of an open item (not done or dropped) whose links carry `fingerprint <fp>`, or None."""
    for iid, it in sorted(items.items()):
        if it.get("status") not in ("done", "dropped") and f"{FP_LINK}{fp}" in it.get("links", []):
            return iid
    return None


def one(text):
    """A text on one line: whitespace runs, newlines included, become single spaces."""
    return " ".join(str(text).split())


def repro_of(c):
    return STATUS_REPRO + [c.fp]


def links_of(c):
    out = [f"{FP_LINK}{c.fp}"]
    for x in c.links:
        if x.strip() not in out:
            out.append(x.strip())
    return out


def item_of(c, iid):
    """The draft item for candidate `c` under the id `iid`: no sprint, no parent, priority P2. A bug's repro is
    `intake --status <fingerprint>`, which exits 1 while the detector reports the finding."""
    it = {"id": iid, "kind": c.kind, "title": one(c.title)[:TEXT_MAX], "status": "draft", "priority": "P2",
          "rank": 0, "goal": one(c.goal)[:TEXT_MAX]}
    if c.kind == "bug":
        it["severity"] = c.severity
        it["repro"] = {"run": repro_of(c)}
    else:
        it["checks"] = [{"run": list(x)} for x in c.checks]
    it["links"] = links_of(c)
    if c.notes.strip():
        it["notes"] = one(c.notes)[:TEXT_MAX]
    return it


def lines(c, filed=None):
    """The lines printed for candidate `c`; `filed` is the label of the open item that already carries its
    fingerprint (the candidate is then skipped)."""
    out = [f"{c.detector} {c.kind} {c.fp} {one(c.title)}" + (f" (skipped: filed as {filed})" if filed else ""),
           f"  goal: {one(c.goal)}"]
    if c.kind == "bug":
        out.append(f"  severity: {c.severity}")
        out.append("  repro: " + " ".join(repro_of(c)))
    else:
        out.extend("  check: " + " ".join(one(y) for y in x) for x in c.checks)
    out.append("  links: " + ", ".join(one(x) for x in links_of(c)))
    return out


# ------------------------------------------------------------------ the drift detector

BACKLOG_DIR = "kb/_self/backlog"  # backlog.py's REL_DIR: the item files, one `<id>.json` each
DRIFT_HOURS = 24  # a doing item whose newest work commit is older than this drifted
CHECK_TIMEOUT_S = 120  # one check run by the detector; a check that exceeds it is counted and says nothing
WORK_KEY = "KB-Work"
ID_RE = re.compile(r"[A-Z]{2}-[0-9a-z]{8}")


@dataclass
class Drift:
    """What `scan_drift` found: `stale` {doing item id: (work commit, hours it is older than the tip of main)},
    `passing` {draft or todo item id: how many checks it has} (all of its checks pass on HEAD), `timed_out` the ids of
    items with a check that exceeded the timeout, `ran` how many items had their checks run."""
    stale: dict = field(default_factory=dict)
    passing: dict = field(default_factory=dict)
    timed_out: list = field(default_factory=list)
    ran: int = 0


def git_out(root, *args):
    """git's stdout in `root`; RuntimeError with its message when it fails."""
    p = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {(p.stderr or p.stdout).strip()}")
    return p.stdout


def ref_exists(root, ref):
    return subprocess.run(["git", "rev-parse", "--verify", "-q", ref], cwd=root,
                          capture_output=True).returncode == 0


def load_items(root):
    """{id: item} of the item files under `root`; a file that is not a JSON object is left out."""
    out = {}
    d = Path(root) / BACKLOG_DIR
    for p in sorted(d.glob("*.json")) if d.is_dir() else []:
        try:
            item = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if isinstance(item, dict):
            out[p.stem] = item
    return out


def family(items, iid):
    """`iid` and the ids of every item below it (a story or bug whose tasks carried the work)."""
    out, grew = {iid}, True
    while grew:
        grew = False
        for k, it in items.items():
            if k not in out and it.get("parent") in out:
                out.add(k)
                grew = True
    return out


def is_item_file(path):
    return path.startswith(BACKLOG_DIR + "/") and path.endswith(".json")


def main_ref(root):
    """The integration remote's main as last fetched, such as `<remote>/main`: the branch work lands on."""
    import kbpublic
    return f"{kbpublic.integration_remote(root)}/main"


def work_commits(root, ref):
    """[(sha, committer time, ids named by KB-Work, paths)] of the commits on `ref` that changed a file other than an
    item file (a claim or a done is no work), newest first."""
    log = git_out(root, "log", ref, "--no-merges", "--name-only",
                  f"--format=%x1e%H%x00%ct%x00%(trailers:key={WORK_KEY},valueonly,separator=%x2C)%x00")
    out = []
    for rec in log.split("\x1e"):
        parts = rec.split("\x00", 3)
        if len(parts) < 4:
            continue
        paths = [p for p in parts[3].split("\n") if p.strip()]
        if any(not is_item_file(p) for p in paths):
            out.append((parts[0].strip(), int(parts[1]), set(ID_RE.findall(parts[2])), paths))
    return out


def stale_doing(root, items, hours):
    """{id: (sha, hours)} of the doing items whose newest work commit on main is more than `hours` older than the
    newest commit on main. The tip's time stands for "now": the detector reads the repository and no clock, so the same
    clone gives the same findings."""
    ref = main_ref(root)
    if not ref_exists(root, ref):
        return {}
    tip = int(git_out(root, "log", "-1", "--format=%ct", ref).strip() or 0)
    commits = work_commits(root, ref)
    out = {}
    for iid, it in sorted(items.items()):
        if it.get("status") != "doing":
            continue
        ids = family(items, iid)
        named = [c for c in commits if c[2] & ids]  # newest first
        if named and tip - named[0][1] > hours * 3600:
            out[iid] = (named[0][0], (tip - named[0][1]) // 3600)
    return out


def touches_changed_since_file(root, iid, touches):
    """True when a commit on HEAD after the one that last changed the item's file changed a file `touches` matches."""
    last = git_out(root, "log", "-1", "--format=%H", "--", f"{BACKLOG_DIR}/{iid}.json").strip()
    if not last or not touches:
        return False
    specs = [f":(glob){g}" for g in touches]
    return bool(git_out(root, "log", "-1", "--format=%H", f"{last}..HEAD", "--", *specs).strip())


def check_env():
    env = {k: v for k, v in os.environ.items() if k not in ("FORCE_COLOR", "PYTHON_COLORS", "CLICOLOR_FORCE")}
    env["NO_COLOR"] = "1"
    return env


def check_result(root, check, timeout):
    """"pass", "fail" or "timeout" for one item check (`run` argv, optional `exit` and `match`), run in `root` without a
    shell; a check that cannot start fails. python3 runs with the interpreter running this tool."""
    argv = list(check["run"])
    if argv and argv[0] in ("python3", "python"):
        argv[0] = sys.executable
    try:
        p = subprocess.run(argv, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, env=check_env())
    except subprocess.TimeoutExpired:
        return "timeout"
    except OSError:
        return "fail"
    ok = p.returncode == check.get("exit", 0)
    if ok and check.get("match"):
        ok = re.search(check["match"], (p.stdout or "") + (p.stderr or ""), re.M) is not None
    return "pass" if ok else "fail"


def passing_open(root, items, timeout, drift):
    """Run the checks of each draft or todo item that has touches and checks and whose touches changed since its file
    did; an item is reported when all its checks pass, left out when one fails, left out and counted when one
    exceeds `timeout`."""
    for iid, it in sorted(items.items()):
        checks = [c for c in it.get("checks", []) if isinstance(c, dict) and c.get("run")]
        if it.get("status") not in ("draft", "todo") or not it.get("touches") or not checks:
            continue
        if not touches_changed_since_file(root, iid, it["touches"]):
            continue
        drift.ran += 1
        results = []
        for c in checks:
            results.append(check_result(root, c, timeout))
            if results[-1] != "pass":
                break
        if results[-1] == "timeout":
            drift.timed_out.append(iid)
        elif results[-1] == "pass":
            drift.passing[iid] = len(checks)


def scan_drift(root, hours=None, timeout=None):
    """The `Drift` of the repository under `root`; `hours` and `timeout` default to DRIFT_HOURS and CHECK_TIMEOUT_S."""
    hours = DRIFT_HOURS if hours is None else hours
    timeout = CHECK_TIMEOUT_S if timeout is None else timeout
    items = load_items(root)
    drift = Drift(stale=stale_doing(root, items, hours))
    passing_open(root, items, timeout, drift)
    return drift


@detector("drift")
def drift_detector(root):
    """One story listing the items that disagree with their commits: each doing item whose newest work commit on main
    is older than DRIFT_HOURS (no done followed it), and each draft or todo item with touches whose own checks already
    pass on HEAD. The fingerprint is the sorted item ids."""
    d = scan_drift(root)
    ids = sorted(set(d.stale) | set(d.passing))
    if not ids:
        return []
    key = ",".join(ids)
    notes = [f"{i}: doing, its newest work commit {d.stale[i][0][:10]} is {d.stale[i][1]} h older than the tip of "
             f"{main_ref(root)}, and no done followed it" for i in sorted(d.stale)]
    notes += [f"{i}: its {d.passing[i]} check(s) already pass on HEAD" for i in sorted(d.passing)]
    if d.timed_out:
        notes.append(f"{len(d.timed_out)} item(s) had a check that exceeded {CHECK_TIMEOUT_S} s and were left out")
    return [Candidate(
        kind="story", title=f"Drift: {len(ids)} backlog item(s) disagree with their commits",
        goal=f"Each of {', '.join(ids)} is finished with done, dropped, or has its status corrected, so no detector "
             "reports it as drifted.",
        key=key, checks=[STATUS_REPRO + [fingerprint("drift", key)]], notes="; ".join(notes))]


# ------------------------------------------------------------------ the trailer detector

TRAILER_WINDOW_DAYS = 7  # the commits of main this much newer than its tip are read
AUTO_KEY = "KB-Auto"  # querylog.py's automatic commits carry no KB-Work
WORK_LINE = re.compile(r"KB-Work\s*:\s*(.*\S)\s*$", re.I)  # kbgit.py's WORK_LINE
WORK_PATHS = ("_tools/", ".claude/", ".githooks/", ".gitlab-ci.yml")  # a change to these is work: it needs a KB-Work
SHORT_SHA = 10


def code_path(path):
    return any(path == p or (p.endswith("/") and path.startswith(p)) for p in WORK_PATHS)


def trailer_findings(root, days=None):
    """[(short sha, why)] sorted by sha, for the non-merge commits on the integration main whose committer time is at
    most `days` (default TRAILER_WINDOW_DAYS) older than the tip's: `stray` when the message has more KB-Work lines than
    git reads as trailers (a blank line before Co-Authored-By?), `missing` when the commit changes a path of
    WORK_PATHS and carries neither a KB-Work nor a KB-Auto trailer. The tip's time stands for "now", as in the drift
    detector: no clock."""
    days = TRAILER_WINDOW_DAYS if days is None else days
    ref = main_ref(root)
    if not ref_exists(root, ref):
        return []
    tip = int(git_out(root, "log", "-1", "--format=%ct", ref).strip() or 0)
    since = tip - days * 86400
    log = git_out(root, "log", ref, "--no-merges", "--name-only", f"--since={since}",
                  f"--format=%x1e%H%x1f%ct%x1f%(trailers:key={WORK_KEY},valueonly,unfold)%x1f"
                  f"%(trailers:key={AUTO_KEY},valueonly,unfold)%x1f%B%x1f")
    out = []
    for rec in log.split("\x1e")[1:]:
        parts = rec.split("\x1f")
        if len(parts) < 6 or int(parts[1]) < since:
            continue
        sha, work, auto, body, paths = parts[0].strip(), parts[2], parts[3], parts[4], parts[5]
        trailers = sum(1 for ln in work.splitlines() if ln.strip())
        lines = sum(1 for ln in body.splitlines() if WORK_LINE.match(ln))
        if lines > trailers:
            out.append((sha[:SHORT_SHA], "stray"))
        elif not trailers and not auto.strip() and any(code_path(p.strip()) for p in paths.split("\n")):
            out.append((sha[:SHORT_SHA], "missing"))
    return sorted(out)


@detector("trailers")
def trailers_detector(root):
    """One bug listing the commits of the last TRAILER_WINDOW_DAYS on the integration main whose KB-Work line git
    reads as no trailer, or that change `_tools/`, `.claude/`, `.githooks/` or `.gitlab-ci.yml` with neither a KB-Work
    nor a KB-Auto trailer. The fingerprint is the sorted short shas."""
    found = trailer_findings(root)
    if not found:
        return []
    shas = [s for s, _ in found]
    stray = [s for s, why in found if why == "stray"]
    missing = [s for s, why in found if why == "missing"]
    notes = []
    if stray:
        notes.append("a KB-Work line git does not read as a trailer (a blank line before Co-Authored-By?): "
                     + ", ".join(stray))
    if missing:
        notes.append("changes _tools/, .claude/, .githooks/ or .gitlab-ci.yml with no KB-Work or KB-Auto trailer: "
                     + ", ".join(missing))
    return [Candidate(
        kind="bug", title=f"Trailers: {len(shas)} commit(s) on main without a KB-Work trailer git reads",
        goal=f"No commit of the last {TRAILER_WINDOW_DAYS} days on {main_ref(root)} has a KB-Work line git reads as no "
             "trailer, or changes code with no KB-Work and no KB-Auto trailer.",
        key=",".join(shas), severity="S3", notes="; ".join(notes))]
