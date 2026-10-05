"""The backlog's intake: deterministic detectors, each finding a candidate item, filed once by fingerprint.

`backlog.py intake` (the command and its exit codes are in backlog.py's docstring) is the facade; this module holds
the detectors and the filing of their candidates:

- the registry `DETECTORS`: detector name -> a function `fn(root: Path) -> iterable of Candidate`, added with the
  `@detector("name")` decorator. A detector reads the repository under `root` and nothing else: no network, no model,
  no clock, so the same inputs give the same candidates in any clone;
- `Candidate`: what a detector reports (kind bug or story, title, goal, a `key` naming the finding, a bug's severity,
  a story's checks, extra links);
- `fingerprint(detector, key)`: 12 hex characters naming one finding; the same detector and key give the same one, so a
  finding is filed once however often intake runs. The drift and trailers detectors report their whole finding set as
  one candidate keyed WHOLE_KEY, so each keeps one fingerprint while it reports anything;
- `collect(root)`: every detector's candidates in a fixed order, each with its fingerprint, and the detectors that
  failed;
- `item_of(candidate, iid)`: the draft item `--file` writes (outside any sprint; a bug's repro is
  `intake --status <fingerprint>`; its last link is `detector <name>`, which `querylog.py digest` counts by);
- `open_with_fingerprint(items, fp)`: the open item whose links already carry the fingerprint, which skips the
  candidate;
- `lines(candidate)`: the lines the command prints for one candidate;
- `file_found(bl, found, ...)`: what `intake --file` does with each candidate no open item's fingerprint covers
  (`file_draft`): one that `backlog.py similar` calls a near-duplicate of an open item of another detector is merged
  into that item's notes once, as `Found again by the intake: ... (fingerprint HEX)`, and no draft is filed; one that
  would pass OPEN_DRAFTS_MAX open drafts is refused with the cap message on stderr and exit 1, and so is every later
  one; the rest are saved as drafts. This is the one part that writes the backlog's files, through the `Backlog` it
  is given;
- the `drift` detector (`scan_drift`, `drift_detector`): items whose state disagrees with their commits. Its item
  checks run within a total budget (DRIFT_BUDGET_S, each check at most CHECK_TIMEOUT_S), the items taken in id order
  started after the last item the previous run reached (`rotated`, `read_cursor`, `write_cursor`; the commit count of
  main's tip, `rotation`, only seeds the first run), so every eligible item is reached within as many runs as there
  are whatever moved the tip between them, each check as a process group of
  its own that a timeout or this process's exit ends whole (`end_tree`, `end_live`), and a check that runs the whole
  test suite (`heavy_check`: `_tools/tests.py` or pytest with no narrowing `-k`, `stress_test.py`, a wrapper such as
  `perfcheck.py`, also inside `sh -c '...'`) never runs, nor one that is not of drift's read-only forms
  (`check_program_refusal` with `inline=False`: exactly python3 on one of DRIFT_SCRIPTS, so a committed `git push`,
  publish, sync or runner start never runs in a session's hook); the items those leave unchecked are counted in the
  story's notes, the refused ones apart from the heavy ones, never reported as passing. The budget is the detector's one reading of time, so an
  intake stays short enough for a SessionStart hook;
- the `trailers` detector (`trailer_findings`, `trailers_detector`, at the end): commits of main whose KB-Work line git
  does not read, or that change code with no KB-Work and no KB-Auto trailer;
- the `stranded` detector (`stranded_findings`, `stranded_detector`): query-log findings of the committed
  store whose newest record is a candidate-gap, an open source finding, no-fix or apply-failed and older than
  STRANDED_DAYS on HEAD's commit day (`kb/_self/querylog.md`, Store and Learn). It reads the findings files at HEAD
  directly, with no ql_ module;
- the `ci` detector (`latest_pipeline`, `pipeline_candidate`, `ci_detector`, at the end): the newest pipeline of the
  integration main in which a job ran, as `backlog.py red-pipeline` reads it (glab, gh), and the bug a red one files,
  with red-pipeline's fingerprint, links and repro. It is the one detector that uses the network, so it is in
  NETWORK_DETECTORS and `collect` runs it only when asked (`intake --network`); red-pipeline calls the same reader and
  candidate with its own `run`.

This module imports no tool module but `bl_base` (the backlog's constants, and its refusal in the filing) and `kbpublic` (the integration remote's
name) and, in the functions that read a pipeline, `ql_base` (the command runner) and `ql_deliver` (the forge calls),
inside the function that needs them; it is below backlog.py, which passes its own `run` to the readers.
"""
import atexit
import datetime
import hashlib
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from bl_base import REL_DIR, TEXT_MAX, Refused

DETECTORS = {}  # name -> fn(root) -> iterable of Candidate; the registry
NETWORK_DETECTORS = {"ci"}  # detectors that call the network: `collect` runs them only with network=True
KINDS = ("bug", "story")
SEVERITIES = ("S1", "S2", "S3", "S4")
FP_RE = re.compile(r"[0-9a-f]{12}")


FP_LINK = "fingerprint "  # a link `fingerprint <12 hex>`, the same marker red-pipeline's bugs carry
DETECTOR_LINK = "detector "  # the last link of an item intake files: `detector <name>`, which the digest counts by
STATUS_REPRO = ["python3", "_tools/backlog.py", "intake", "--status"]  # + the fingerprint: a filed bug's repro
WHOLE_KEY = "open"  # the key of a detector that reports its whole finding set as one candidate (drift, trailers): its
# fingerprint stays the same while the detector reports anything, whichever findings make up the set


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
    priority: str = "P2"  # a bug's, in the item `--file` writes
    repro: list = field(default_factory=list)  # a bug's repro argv when it is not `intake --status <fingerprint>`
    lead_links: list = field(default_factory=list)  # links before the fingerprint; an item naming one is the finding's
    fp_fixed: str = ""  # a fingerprint the detector computed itself, kept by collect() in place of the hash of its key
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


DETECT_STATS = {}  # {detector: {"budget": bool, "coverage": int}}: what a detector with a budget says of its own run


def record_detect(name, found, stats):
    """Append the `intake.detect` ops row of detector `name` (`ql_deliver.ops_row`: best effort, nothing is raised):
    `found` candidates kept, and `budget` (true when the detector's budget ran out before it reached every item it
    could check) and `coverage` (the items it checked) for a detector that reports them."""
    try:
        from ql_deliver import ops_row
        fields = {k: stats[k] for k in ("budget", "coverage") if k in stats}
        ops_row("intake.detect", detector=name, found=found, **fields)
    except Exception:  # noqa: BLE001 - intake never fails for its log
        pass


def collect(root, only=None, network=False, record=False):
    """(candidates, failures) over the registry: the candidates of every detector (or the one named `only`) sorted by
    detector name, then fingerprint, each with `detector` and `fp` set, a finding reported twice kept once; the
    failures as `detector: why` lines (a detector that raised, a candidate that `problem` refuses). A detector of
    NETWORK_DETECTORS runs only with `network`, or when it is the one named `only`. With `record`, a detector that
    found a candidate or ran out of its budget appends an `intake.detect` ops row (`record_detect`)."""
    out, failures, seen = [], [], set()
    for name in sorted(DETECTORS):
        if only is not None and name != only:
            continue
        if name in NETWORK_DETECTORS and not (network or only == name):
            continue
        DETECT_STATS.pop(name, None)
        try:
            found = list(DETECTORS[name](Path(root)))
        except Exception as e:  # noqa: BLE001 - one broken detector must not hide the others' findings
            failures.append(f"{name}: raised {type(e).__name__}: {e}")
            continue
        kept = 0
        for c in found:
            why = problem(c)
            if why:
                failures.append(f"{name}: candidate {getattr(c, 'title', '')!r} refused: {why}")
                continue
            c.detector, c.fp = name, c.fp_fixed or fingerprint(name, c.key)
            if c.fp not in seen:
                seen.add(c.fp)
                out.append(c)
                kept += 1
        stats = DETECT_STATS.pop(name, {})
        if record and (kept or stats.get("budget")):
            record_detect(name, kept, stats)
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


def named_by(items, c):
    """The id of an item, open or not, that names one of the candidate's `lead_links` (a CI finding's
    `pipeline <id>`) in its title, goal, notes or links, or None: the finding is filed already."""
    for lead in c.lead_links:
        for iid, it in sorted(items.items()):
            if names_pipeline(it, lead):
                return iid
    return None


def names_pipeline(it, marker):
    """True when an item names `marker` (`pipeline <id>`) in its title, goal, notes or links."""
    text = " ".join(str(it.get(f, "")) for f in ("title", "goal", "notes")) + " " + " ".join(map(str, it.get("links", [])))
    return re.search(rf"\b{re.escape(marker)}\b", text) is not None


def repro_of(c):
    return list(c.repro) if c.repro else STATUS_REPRO + [c.fp]


def links_of(c):
    out = [x.strip() for x in c.lead_links]
    if c.fp and f"{FP_LINK}{c.fp}" not in out:
        out.append(f"{FP_LINK}{c.fp}")
    for x in c.links:
        if x.strip() not in out:
            out.append(x.strip())
    if c.detector and f"{DETECTOR_LINK}{c.detector}" not in out:  # a candidate not from `collect` (red-pipeline's) has none
        out.append(f"{DETECTOR_LINK}{c.detector}")
    return out


def item_of(c, iid):
    """The draft item for candidate `c` under the id `iid`: no sprint, no parent, priority P2. A bug's repro is
    `intake --status <fingerprint>`, which exits 1 while the detector reports the finding."""
    it = {"id": iid, "kind": c.kind, "title": one(c.title)[:TEXT_MAX], "status": "draft",
          "priority": c.priority if c.kind == "bug" else "P2", "rank": 0, "goal": one(c.goal)[:TEXT_MAX]}
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


# ------------------------------------------------------------------ filing: near-duplicates and the open-drafts cap

OPEN_DRAFTS_MAX = 60  # open drafts, of any origin, past which `intake --file` files no more
SIMILAR_NEAR = re.compile(r"^\s*\d+\.\d+\s+\d+\s+near\s+((?:EP|ST|TK|SB|BG)-[a-z2-7]{8})\b", re.M)


def detector_of(it):
    """The name in the item's `detector NAME` link, or None."""
    return next((x[len(DETECTOR_LINK):] for x in it.get("links") or [] if isinstance(x, str)
                 and x.startswith(DETECTOR_LINK) and " " not in x[len(DETECTOR_LINK):]), None)


def open_drafts(items):
    return sum(1 for it in items.values() if it.get("status") == "draft")


def near_duplicates(root, title, goal):
    """The ids of the open items `backlog.py similar` calls near-duplicates of the finding, best first; Refused when
    `similar` fails."""
    p = subprocess.run([sys.executable, str(Path(__file__).with_name("backlog.py")), "--root", str(root), "similar",
                        title, *(["--goal", goal] if goal else [])], cwd=str(root), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    if p.returncode:
        raise Refused(f"intake: similar failed: {(p.stdout + p.stderr).strip()}")
    return SIMILAR_NEAR.findall(p.stdout)


def file_draft(bl, c, draft, say):
    """File one candidate's draft: merge it into the notes of a near-duplicate open item (once: a second run adds
    nothing; an item of the same detector is no duplicate, for a detector words its findings alike and each has its
    own fingerprint), else save the draft. Returns (`filed` or `merged`, id). Refused, the draft not saved, when the
    near-duplicate's notes are full or OPEN_DRAFTS_MAX open drafts are filed already."""
    title, goal = one(c.title), one(c.goal)
    dups = [d for d in near_duplicates(bl.root, title, goal) if detector_of(bl.items[d]) != c.detector]
    if dups:
        it = bl.items[dups[0]]
        note = f"Found again by the intake: {title}. {goal} (fingerprint {c.fp})"
        if note in (it.get("notes") or ""):
            say(f"intake: already in the notes of {bl.label(dups[0])}, a near-duplicate")
            return "merged", dups[0]
        text = f"{it['notes']}\n{note}" if it.get("notes") else note
        if len(text) > TEXT_MAX:
            raise Refused(f"intake: the notes of {bl.label(dups[0])} are full; the finding is not filed")
        it["notes"] = text
        bl.save(it)
        say(f"intake: merged into the notes of {bl.label(dups[0])}, a near-duplicate")
        return "merged", dups[0]
    n = open_drafts(bl.items)
    if n >= OPEN_DRAFTS_MAX:
        raise Refused(f"intake: {n} open drafts (at most {OPEN_DRAFTS_MAX}): triage before filing")
    bl.save(draft)
    say(f"intake: filed {bl.label(draft['id'])}")
    return "filed", draft["id"]


def file_found(bl, found, failures, say, new_id, withhold=str):
    """`intake --file`: each candidate no open item's fingerprint covers (nor an item that names its lead link) is
    filed by `file_draft`. Prints what `intake` prints for a candidate and the filing line. Exit 1 when a detector
    failed or a candidate was refused (the message goes to stderr once), else 0; a refusal at the open-drafts cap ends
    the filing, for it holds for every later candidate."""
    new = skipped = refused = 0
    stop = ""
    for c in found:
        dup = open_with_fingerprint(bl.items, c.fp) or named_by(bl.items, c)
        for ln in lines(c, bl.label(dup) if dup else None):
            say(ln)
        if dup:
            skipped += 1
            continue
        if stop:
            refused += 1
            continue
        try:
            if file_draft(bl, c, item_of(c, new_id(c.kind)), say)[0] == "filed":
                new += 1
            else:
                skipped += 1  # merged into a near-duplicate's notes
        except Refused as e:
            refused += 1
            stop = str(e)
            print(withhold(stop), file=sys.stderr)
    say(f"intake: {len(found)} candidate(s), {new} new filed, {skipped} skipped"
        + (f", {refused} refused" if refused else "") if found else "intake: no candidates")
    return 1 if failures or refused else 0


# ------------------------------------------------------------------ the drift detector

BACKLOG_DIR = REL_DIR  # the item files, one `<id>.json` each
DRIFT_HOURS = 24  # a doing item whose newest work commit is older than this drifted
CHECK_TIMEOUT_S = 15  # one check run by the detector; a check that exceeds it is counted and says nothing
DRIFT_BUDGET_S = 30  # all the checks of one scan; once spent, no further check starts and the rest are counted
HEAVY_SCRIPTS = ("stress_test.py", "perfcheck.py")  # a check that runs one of these (whole-suite wrappers) never runs
SUITE = "_tools/tests.py"  # a check that runs it, or pytest, with no narrowing `-k` selector never runs from intake
SEPARATORS = (";", "&&", "||", "|", "&")  # shell operators that end one command of a `sh -c` string
SHELLS = ("sh", "bash", "zsh", "dash", "ksh", "cmd", "powershell", "pwsh")  # their string arguments are commands
WORK_KEY = "KB-Work"
ID_RE = re.compile(r"[A-Z]{2}-[0-9a-z]{8}")


@dataclass
class Drift:
    """What `scan_drift` found: `stale` {doing item id: (work commit, hours it is older than the tip of main)},
    `passing` {draft or todo item id: how many checks it has} (all of its checks pass on HEAD), `timed_out` the ids of
    items with a check that exceeded the timeout, `heavy` the ids of items left unchecked because a check runs the
    whole test suite or the stress tests, `refused` the ids of items left unchecked because a check is not one of
    drift's read-only forms (check_program_refusal), `over_budget` the ids of items left unchecked once the budget was
    spent, `ran` how many items had their checks run, `last` the id of the last item reached in the run's order before
    the budget was spent (the next run starts after it)."""
    stale: dict = field(default_factory=dict)
    passing: dict = field(default_factory=dict)
    timed_out: list = field(default_factory=list)
    heavy: list = field(default_factory=list)
    refused: list = field(default_factory=list)
    over_budget: list = field(default_factory=list)
    ran: int = 0
    last: str = ""


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


def is_shell(word):
    return word.rsplit("/", 1)[-1].lower().removesuffix(".exe") in SHELLS


def words(argv, depth=0):
    """The argv's words, `\\` read as `/`, with each argument after a shell (`sh -c '...'`, `bash -lc`, `cmd /c`,
    `pwsh -Command`) that holds whitespace or a shell operator split into its own words and operators; a `-k`
    expression stays one word."""
    out = []
    for a in argv:
        a = str(a).replace("\\", "/")
        if (depth < 4 and any(is_shell(w) for w in out) and out[-1] != "-k"
                and re.search(r"[\s;&|]", a)):
            lex = shlex.shlex(a, posix=True, punctuation_chars=";&|")
            lex.whitespace_split = True
            try:
                parts = list(lex)
            except ValueError:
                parts = a.split()
            if parts != [a]:
                out.extend(words(parts, depth + 1))
                continue
        out.append(a)
    return out


def narrows(expr):
    """True when the `-k` expression selects a part of the suite: each `or` alternative has a term not under `not`
    (`-k 'not slow'` selects nearly all of it)."""
    for alt in re.split(r"\bor\b", re.sub(r"[()]", " ", expr)):
        ws = alt.split()
        if not any(w not in ("and", "not") and (j == 0 or ws[j - 1] != "not") for j, w in enumerate(ws)):
            return False
    return True


def command(rest):
    """The words of `rest` up to the end of their command (a shell operator)."""
    return rest[:next((j for j, w in enumerate(rest) if w in SEPARATORS), len(rest))]


def selects_part(seg):
    """True when the last `-k` expression among a suite runner's words (`-k EXPR` or `-kEXPR`) narrows it."""
    expr = None
    for j, w in enumerate(seg):
        if w == "-k":
            expr = seg[j + 1] if j + 1 < len(seg) else ""
        elif w.startswith("-k"):
            expr = w[2:]
    return expr is not None and narrows(expr)


KBGIT_REFUSED = ("publish", "bridge", "install-hooks", "hook")  # kbgit.py forms a check never runs: they push or arm hooks
DRIFT_ALLOWS_INLINE = False  # drift never runs `python3 -c`; the drift tests' planted checks set it, nothing else does
# the scripts drift runs a committed check with: read-only ones, so no check reaches sync, autopilot or a backlog writer
DRIFT_SCRIPTS = ("_tools/tests.py", "_tools/rag.py", "_tools/check.py", "_tools/selfdoc.py",
                 ".claude/skills/kb-verify/lint.py")
CHECK_SCRIPT = re.compile(r"_tools/[\w.-]+\.py")


def check_program_refusal(argv, inline=True):
    """Why a check's argv may not run where nothing reviews it, or None: its program must be python3 or python on a
    `_tools/` script of this repository (never `kbgit.py publish`, `bridge`, `install-hooks` or `hook`), so a check
    neither pushes nor publishes nor runs a shell. INLINE allows `python3 -c` / `-m` (the forms an open item's
    repro and checks may take, kb/_self/backlog.md); intake's drift passes False, since it runs committed checks in
    every session with that session's credentials."""
    argv = [str(a) for a in argv] if isinstance(argv, (list, tuple)) else []
    if not argv:
        return "a check with no program"
    if argv[0] not in ("python3", "python") and argv[0] != sys.executable:  # exactly: never a file named python3
        return f"its program is {argv[0]}, not python3 on a _tools/ script"
    rest = argv[1:]
    if rest and rest[0] in ("-c", "-m"):
        return None if inline else f"python3 {rest[0]} runs inline code"
    script = rest[0].replace("\\", "/") if rest else ""
    if not inline:  # drift: only the read-only forms, whatever else a committed check names
        return None if script in DRIFT_SCRIPTS else f"{script or 'nothing'} is not one of drift's read-only checks"
    if not CHECK_SCRIPT.fullmatch(script):
        return f"{script or 'nothing'} is not a _tools/ script"
    if script == "_tools/kbgit.py" and rest[1:2] and rest[1] in KBGIT_REFUSED:
        return f"kbgit.py {rest[1]} pushes or arms hooks"
    return None


def heavy_check(check):
    """True when the check runs `stress_test.py` or a whole-suite wrapper (HEAVY_SCRIPTS), or `_tools/tests.py` or
    pytest with no narrowing `-k` selector (pytest: nor a test file), seen through a shell string such as
    `sh -c '...'`."""
    ws = words(check.get("run", []))
    for i, a in enumerate(ws):
        name = a.rsplit("/", 1)[-1]
        if name in HEAVY_SCRIPTS:
            return True
        if a == SUITE or a.endswith("/" + SUITE) or a == "tests.py":
            if not selects_part(command(ws[i + 1:])):
                return True
        if name in ("pytest", "py.test") or (a == "-m" and ws[i + 1:i + 2] == ["pytest"]):
            rest = command(ws[i + 2:] if a == "-m" else ws[i + 1:])
            if not any(w.endswith(".py") or "::" in w for w in rest) and not selects_part(rest):
                return True
    return False


LIVE = set()  # the drift checks running now (Popen); an exit ends their process groups (end_live)
LIVE_LOCK = threading.Lock()


def end_tree(proc):
    """End the process group the check leads (tests.py, uv, pytest and its workers), then the check itself."""
    if os.name == "posix":
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    else:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    try:
        proc.kill()
    except OSError:
        pass


@atexit.register
def end_live():
    """End every drift check still running when the process exits: `intake --hook` stops waiting for a detector and
    exits while its thread may still run one."""
    with LIVE_LOCK:
        procs = list(LIVE)
    for proc in procs:
        end_tree(proc)


def check_result(root, check, timeout):
    """"pass", "fail" or "timeout" for one item check (`run` argv, optional `exit` and `match`), run in `root` without a
    shell as the leader of a process group of its own, which a timeout or an exit ends whole; a check that cannot
    start fails. python3 runs with the interpreter running this tool."""
    argv = list(check["run"])
    if argv and argv[0] in ("python3", "python"):
        argv[0] = sys.executable
    group = {"start_new_session": True} if os.name == "posix" else {
        "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    try:
        proc = subprocess.Popen(argv, cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                                env=check_env(), **group)
    except OSError:
        return "fail"
    with LIVE_LOCK:
        LIVE.add(proc)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        end_tree(proc)
        try:
            proc.communicate(timeout=2)  # the pipes close once the group is gone
        except subprocess.TimeoutExpired:
            pass
        return "timeout"
    except BaseException:
        end_tree(proc)
        raise
    finally:
        with LIVE_LOCK:
            LIVE.discard(proc)
    ok = proc.returncode == check.get("exit", 0)
    if ok and check.get("match"):
        ok = re.search(check["match"], (out or "") + (err or ""), re.M) is not None
    return "pass" if ok else "fail"


def rotation(root):
    """The rotation index of the drift checks: the number of commits on the tip of main (HEAD without one). It is a
    function of the tip, so the same inputs give the same order, and it moves by one per commit, so successive runs on
    successive tips start from successive eligible items."""
    ref = main_ref(root)
    try:
        return int(git_out(root, "rev-list", "--count", ref if ref_exists(root, ref) else "HEAD").strip() or 0)
    except (RuntimeError, ValueError):
        return 0


def cursor_path(root):
    """The file (in the git directory, so never tracked) that keeps the last item a drift run reached."""
    try:
        return (Path(root) / git_out(root, "rev-parse", "--git-path", "kb-intake-drift").strip()).resolve()
    except RuntimeError:
        return None


def read_cursor(root):
    """The id of the last item the previous drift run reached, or None."""
    p = cursor_path(root)
    try:
        return p.read_text(encoding="utf-8").strip() or None
    except (OSError, AttributeError):
        return None


def write_cursor(root, iid):
    """Keep `iid` as the last item reached; a failed write only loses the place."""
    p = cursor_path(root)
    if p is None or not iid:
        return
    try:
        p.write_text(iid + "\n", encoding="utf-8", newline="\n")
    except OSError:
        pass


def rotated(ids, index, after=None):
    """`ids` (sorted) wrapped round to start after the id `after` (the first id above it when it is gone), so every id
    is reached within len(ids) runs whatever moved the tip between them. Without `after` the start is a hash of
    `index`, not `index` modulo the number: a step between indexes that shares a factor with the number of ids
    would otherwise revisit the same few starts forever."""
    if not ids:
        return []
    if after is not None:
        k = sum(1 for i in ids if i <= after) % len(ids)
    else:
        k = int.from_bytes(hashlib.sha256(str(index).encode()).digest()[:8], "big") % len(ids)
    return ids[k:] + ids[:k]


def eligible(root, items):
    """[(id, checks)] of the draft or todo items with touches and checks whose touches changed since their file did,
    in id order: the items whose checks the drift detector runs."""
    out = []
    for iid, it in sorted(items.items()):
        checks = [c for c in it.get("checks", []) if isinstance(c, dict) and c.get("run")]
        if it.get("status") not in ("draft", "todo") or not it.get("touches") or not checks:
            continue
        if touches_changed_since_file(root, iid, it["touches"]):
            out.append((iid, checks))
    return out


def passing_open(root, items, timeout, drift, budget):
    """Run the checks of each draft or todo item that has touches and checks and whose touches changed since its file
    did; an item is reported when all its checks pass, left out when one fails, left out and counted when one
    exceeds `timeout` (or the budget left), when one is a heavy check (not run), or when the `budget` seconds for all
    the checks were spent before its turn (not run). The items are taken in id order starting after the last item the
    previous run reached (`rotation(root)` seeds the start when there is none), so a budget that covers only some of
    them still reaches every eligible item within as many runs as there are eligible items."""
    start = time.monotonic()
    found = eligible(root, items)
    order = rotated([iid for iid, _ in found], rotation(root), read_cursor(root))
    checks_of = dict(found)
    spent = False
    for iid in order:
        checks = checks_of[iid]
        # a heavy check never runs here, nor one that is not of drift's read-only forms: drift runs the committed
        # checks of every item in every session's hook, so a planted `git push` or publish check would run with that
        # session's credentials; such items are left unchecked and counted apart from the heavy ones
        if any(heavy_check(c) for c in checks):
            drift.heavy.append(iid)
            drift.last = drift.last if spent else iid
            continue
        if any(check_program_refusal(c.get("run"), inline=DRIFT_ALLOWS_INLINE) for c in checks):
            drift.refused.append(iid)
            drift.last = drift.last if spent else iid
            continue
        if time.monotonic() - start >= budget:
            drift.over_budget.append(iid)
            spent = True
            continue
        drift.last = drift.last if spent else iid
        drift.ran += 1
        results = []
        for c in checks:
            left = budget - (time.monotonic() - start)
            results.append(check_result(root, c, min(timeout, left)) if left > 0 else "timeout")
            if results[-1] != "pass":
                break
        if results[-1] == "timeout":
            drift.timed_out.append(iid)
        elif results[-1] == "pass":
            drift.passing[iid] = len(checks)
    for ids in (drift.timed_out, drift.heavy, drift.refused, drift.over_budget):
        ids.sort()


def scan_drift(root, hours=None, timeout=None, budget=None):
    """The `Drift` of the repository under `root`; `hours`, `timeout` and `budget` default to DRIFT_HOURS,
    CHECK_TIMEOUT_S and DRIFT_BUDGET_S."""
    hours = DRIFT_HOURS if hours is None else hours
    timeout = CHECK_TIMEOUT_S if timeout is None else timeout
    budget = DRIFT_BUDGET_S if budget is None else budget
    items = load_items(root)
    drift = Drift(stale=stale_doing(root, items, hours))
    passing_open(root, items, timeout, drift, budget)
    return drift


@detector("drift")
def drift_detector(root):
    """One story listing the items that disagree with their commits: each doing item whose newest work commit on main
    is older than DRIFT_HOURS (no done followed it), and each draft or todo item with touches whose own checks already
    pass on HEAD. The key is WHOLE_KEY, so the fingerprint stays the same whichever items drift or the budget reached;
    the notes list the items found. Items left unchecked (a timeout, a heavy check, a check that is not one of
    drift's read-only forms, the spent budget) are counted in the notes and never reported."""
    d = scan_drift(root)
    DETECT_STATS["drift"] = {"budget": bool(d.over_budget), "coverage": d.ran}  # collect's intake.detect row
    write_cursor(root, d.last)
    ids = sorted(set(d.stale) | set(d.passing))
    if not ids:
        return []
    notes = [f"{i}: doing, its newest work commit {d.stale[i][0][:10]} is {d.stale[i][1]} h older than the tip of "
             f"{main_ref(root)}, and no done followed it" for i in sorted(d.stale)]
    notes += [f"{i}: its {d.passing[i]} check(s) already pass on HEAD" for i in sorted(d.passing)]
    if d.timed_out:
        notes.append(f"{len(d.timed_out)} item(s) had a check that exceeded {CHECK_TIMEOUT_S} s (or the budget left) and were "
                     "left out")
    if d.heavy:
        notes.append(f"{len(d.heavy)} item(s) had a check that runs the whole test suite or the stress tests, "
                     "not run, and were left out")
    if d.refused:
        notes.append(f"{len(d.refused)} item(s) had a check drift does not run (not one of its read-only forms: "
                     f"{', '.join(DRIFT_SCRIPTS)}), and were left out: {', '.join(d.refused)}")
    if d.over_budget:
        notes.append(f"{len(d.over_budget)} item(s) were not checked: the {DRIFT_BUDGET_S} s budget for checks was "
                     "spent, and were left out")
    return [Candidate(
        kind="story", title=f"Drift: {len(ids)} backlog item(s) disagree with their commits",
        goal=f"Each of {', '.join(ids)} is finished with done, dropped, or has its status corrected, so no detector "
             "reports it as drifted.",
        key=WHOLE_KEY, checks=[STATUS_REPRO + [fingerprint("drift", WHOLE_KEY)]], notes="; ".join(notes))]


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
    nor a KB-Auto trailer. The key is WHOLE_KEY, so the fingerprint stays the same whichever commits the window
    holds; the notes list the commits found."""
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
        key=WHOLE_KEY, severity="S3", notes="; ".join(notes))]


# ------------------------------------------------------------------ the stranded-findings detector

STORE_REL = "kb/_querylog"  # the committed query-log store; its findings files are findings/<yyyy-mm>/<run-id>.jsonl
STRANDED_DAYS = 3  # a finding in a non-terminal state whose newest record is older than this many days is stranded
RUN_DAY = re.compile(r"(\d{4})(\d{2})(\d{2})T\d{6}Z-")  # a run id starts with the UTC day of the run
STUCK_STATES = ("no-fix", "apply-failed")  # states no stage moves on its own
STAGE_SIGNAL = "stage"  # a source finding with this signal asks for the host's provider to be probed
ROUTE_SIGNAL = "route"  # a source finding with this signal is report-only: never stranded


def head_day(root):
    """The UTC date of HEAD's commit, or None without a commit: the day that stands for "today"."""
    p = subprocess.run(["git", "log", "-1", "--format=%ct", "HEAD"], cwd=root, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode or not p.stdout.strip().isdigit():
        return None
    return datetime.datetime.fromtimestamp(int(p.stdout), datetime.timezone.utc).date()


def committed_findings(root):
    """[(run id, record)] of the findings files of the store at HEAD, oldest run first and in file order: the records
    that carry an `id` (a header carries none). `git grep` reads HEAD's tree, so a working tree edit changes nothing."""
    p = subprocess.run(["git", "grep", "-I", "-e", '"id"', "HEAD", "--", f"{STORE_REL}/findings/"], cwd=root,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = []
    for n, line in enumerate(p.stdout.splitlines()):
        path, sep, text = line.partition(".jsonl:")  # `HEAD:<path>.jsonl:<line>`
        if not sep:
            continue
        run = path.rsplit("/", 1)[-1]
        try:
            rec = json.loads(text)
        except ValueError:
            continue
        if isinstance(rec, dict) and isinstance(rec.get("id"), str):
            out.append((run, n, rec))
    out.sort(key=lambda t: (t[0], t[1]))
    return [(run, rec) for run, _, rec in out]


def stranded_label(rec):
    """Why the newest record `rec` of a finding is non-terminal, or None: its state (`no-fix`, `apply-failed`), `open`
    for a source finding but a route one (report-only), or the stage `candidate-gap` of an open gap finding."""
    state = rec.get("state")
    if state in STUCK_STATES:
        return state
    if state == "open" and rec.get("kind") == "source" and rec.get("signal") != ROUTE_SIGNAL:
        return "open"  # a route finding is report-only (querylog.py status lists it): no stage moves it
    if state == "open" and rec.get("stage") == "candidate-gap":
        return "candidate-gap"
    return None


def stranded_findings(root, days=None):
    """[(record, label, run id, age in days)] sorted by finding id: each finding of the committed store whose newest
    record is non-terminal (`stranded_label`) and more than `days` (default STRANDED_DAYS) days older than HEAD's commit
    day, the run id's day being the record's; a no-fix eval finding closed --tried is left out until its `tried` day is
    QUEUE_TRIED_DAYS old. No commit, no store or a run id without a day gives none."""
    days = STRANDED_DAYS if days is None else days
    today = head_day(root)
    if today is None:
        return []
    last = {}
    for run, rec in committed_findings(root):
        last[rec["id"]] = (rec, run)
    out = []
    from ql_research import QUEUE_TRIED_DAYS  # the query log's own wait after a tried note
    for fid, (rec, run) in sorted(last.items()):
        label, m = stranded_label(rec), RUN_DAY.match(run)
        if not label or not m:
            continue
        if label == "no-fix" and rec.get("kind") == "eval" and isinstance(rec.get("tried"), str):
            try:  # a no-fix eval finding closed --tried waits, as a tried gap does, until its note is old
                if (today - datetime.date.fromisoformat(rec["tried"])).days < QUEUE_TRIED_DAYS:
                    continue
            except ValueError:
                pass
        try:
            age = (today - datetime.date(*(int(g) for g in m.groups()))).days
        except ValueError:
            continue
        if age > days:
            out.append((rec, label, run, age))
    return out


@detector("stranded")
def stranded_detector(root):
    """One candidate per finding of the committed query-log store whose newest record is a candidate-gap, an open
    source finding, no-fix or apply-failed and older than STRANDED_DAYS on HEAD's commit day (`stranded_findings`): a
    story to probe its host's provider for a `stage` source finding, a bug for any other. The fingerprint is the finding
    id and its label, so a finding that moves on to another state is a new finding."""
    out = []
    for rec, label, run, age in stranded_findings(root):
        fid, key = rec["id"], f"{rec['id']} {label}"
        notes = (f"{rec.get('kind')} finding {fid}, {label}, newest record in run {run}, {age} day(s) before HEAD's "
                 f"commit; the limit is {STRANDED_DAYS}")
        if rec.get("kind") == "source" and rec.get("signal") == STAGE_SIGNAL:
            host = str(rec.get("host") or "an unnamed host")
            out.append(Candidate(
                kind="story", title=f"Probe the provider of {host}: source finding {fid} is stranded",
                goal=f"The provider of {host} is probed (a row in the provider registry, `/kb-probe`), so the stage "
                     f"source finding {fid} is no longer open and the stranded-findings detector does not report it.",
                key=key, checks=[STATUS_REPRO + [fingerprint("stranded", key)]], notes=notes))
        else:
            out.append(Candidate(
                kind="bug", title=f"Query-log finding {fid} is stranded in {label}",
                goal=f"The finding {fid} left the state {label}: learn, apply or research moved it on, or it was "
                     "closed by hand, so the stranded-findings detector does not report it.",
                key=key, severity="S3", notes=notes))
    return out


# ------------------------------------------------------------------ the repeats detector

REPEAT_THRESHOLD = 300  # calls of one command class or tool group in one ISO week above which it is a finding
REPEAT_ROWS_MAX = 200000  # the count budget: the committed call rows one scan reads; the rest are counted, not read
REPEAT_MAX = 5  # the findings one scan reports, most calls first
INSTEAD = {  # the section-sized command to use instead of a class read again and again, when one exists
    "cat": "python3 _tools/rag.py show PATH:LINE -n 30 (a kb article's lines around a fact) or selfdoc.py section",
    "head": "python3 _tools/rag.py show PATH:LINE -n 30, or python3 _tools/selfdoc.py section DOC HEADING",
    "tail": "python3 _tools/rag.py show PATH:LINE -n 30",
    "sed": "python3 _tools/rag.py show PATH:LINE -n 30, or python3 _tools/selfdoc.py section DOC HEADING",
    "grep": "python3 _tools/rag.py search \"<keywords>\" --index, or backlog.py find WORDS",
    "rg": "python3 _tools/rag.py search \"<keywords>\" --index",
    "tools.backlog": "python3 _tools/backlog.py show ID or next, rather than list and tree over the whole backlog",
    "tools.selfdoc": "python3 _tools/selfdoc.py section DOC HEADING ... in one call",
    "kb_show": "kb_pack first: one call answers most lookups",
}


def committed_calls(root, budget=None):
    """([(ISO week, class or tool group)] of the call.tool rows of the ops sidecars at HEAD, at most `budget` (default
    REPEAT_ROWS_MAX) of them, and how many more there were). `git grep` reads HEAD's tree: a working tree edit changes
    nothing, and no spool is read."""
    budget = REPEAT_ROWS_MAX if budget is None else budget
    p = subprocess.run(["git", "grep", "-I", "-h", "-e", '"call.tool"', "HEAD", "--", f"{STORE_REL}/ops/"], cwd=root,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    out, over = [], 0
    for line in p.stdout.splitlines():
        _, sep, text = line.partition(".jsonl:")
        try:
            rec = json.loads(text if sep else line)
        except ValueError:
            continue
        if not (isinstance(rec, dict) and rec.get("event") == "call.tool" and isinstance(rec.get("ts"), str)):
            continue
        if len(out) >= budget:
            over += 1
            continue
        try:
            y, w, _ = datetime.date.fromisoformat(rec["ts"][:10]).isocalendar()
        except ValueError:
            continue
        key = rec.get("class") or rec.get("tool")
        if isinstance(key, str) and key:
            out.append((f"{y}-W{w:02d}", key))
    return out, over


@detector("repeats")
def repeats_detector(root):
    """One story per command class or tool group (call.tool's `class`, else its `tool`) called more than
    REPEAT_THRESHOLD times in one ISO week by the sessions of the committed ops sidecars, the REPEAT_MAX most called
    first, naming the section-sized command to use instead when INSTEAD has one. The fingerprint is the week and the
    class, so each finding is filed once; nothing at or below the threshold is reported."""
    calls, over = committed_calls(root)
    counts = {}
    for week, key in calls:
        counts[(week, key)] = counts.get((week, key), 0) + 1
    found = sorted(((n, week, key) for (week, key), n in counts.items() if n > REPEAT_THRESHOLD),
                   key=lambda t: (-t[0], t[1], t[2]))[:REPEAT_MAX]
    out = []
    for n, week, key in found:
        fkey = f"{week} {key}"
        instead = INSTEAD.get(key)
        notes = (f"{n} calls of {key} in {week}; the threshold is {REPEAT_THRESHOLD} a week (bl_intake.REPEAT_THRESHOLD)"
                 + (f"; {over} call rows past the read budget were not counted" if over else ""))
        out.append(Candidate(
            kind="story", title=f"Calls of {key} repeat {n} times in {week}",
            goal=(f"Sessions call {key} at most {REPEAT_THRESHOLD} times a week"
                  + (f", using {instead} instead" if instead else ", or the reason they must is recorded")
                  + ", so the repeats detector does not report it."),
            key=fkey, checks=[STATUS_REPRO + [fingerprint("repeats", fkey)]], notes=notes))
    return out


# ------------------------------------------------------------------ the CI detector

GITLAB_FINISHED = ("success", "failed", "canceled", "skipped", "manual")  # manual: waits on a person, read by its jobs
S1_JOBS = ("kb-tests",)  # a red one means the gate every push runs fails on main itself: S1; any other job: S2
PIPELINE_REPRO = ["python3", "_tools/backlog.py", "red-pipeline", "--status"]  # a red-main bug adds --job <its job>
MAIN_PIPELINES = 100  # pipelines of main listed, newest first, to find the newest one in which a job ran
IDLE_PIPELINES = 10  # on GitLab the read stops after this many pipelines in a row in which no job ran: one job-list call each
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07")


def run_argv(argv, cwd=None):
    """(exit code, stdout, stderr) of a command given as an argument list (git, glab, gh); 127 when it cannot start.
    The readers below take a `run` of this shape, so a caller (backlog.py) passes its own."""
    from ql_base import run_cmd
    return run_cmd(argv, cwd=cwd, timeout=60)


# GitLab.com prefixes each log line with a timestamp and a stream marker: a 2-digit stream, O (stdout) or E
# (stderr), and `+` on a line continued from the one before (`2026-09-29T01:06:40.889927Z 01O `, `00O+`, where the
# text follows the `+` directly; a marker without `+` is followed by whitespace)
LOG_PREFIX_RE = re.compile(r"^\s*(?:\d{4}-\d\d-\d\dT[\d:.]+Z\s+(?:\d\d[OE](?:\+\s*|\s))?\s*)?"
                           r"(?:section_(?:start|end):\d+:\S+\s*)?")
ERROR_LINE_RE = re.compile(r"\b(?:error|errors|failed|failure|traceback|exception|fatal)\b", re.I)


def normalise_error_line(line, prefix_re=None):
    """One log line with what differs between two runs of the same failure taken out: colour codes, the runner's
    timestamp prefix (`prefix_re`, default LOG_PREFIX_RE), hex ids (7+ characters) and numbers become fixed tokens,
    whitespace collapses."""
    s = (prefix_re or LOG_PREFIX_RE).sub("", ANSI_RE.sub("", line))
    s = re.sub(r"\b[0-9a-f]{7,}\b", "<hex>", s, flags=re.I)
    s = re.sub(r"\d+", "<n>", s)
    return " ".join(s.split())[:200]


PYTEST_ID_START_RE = re.compile(r"(?:(?:FAILED|ERROR)\s+)?(\S+::)")
PYTEST_VERDICT_RE = re.compile(r"\s+(?:FAILED|ERROR)\b")


def pytest_id_end(ln, start):
    """The index in `ln` where the pytest id that begins at `start` ends: the next whitespace outside brackets, so
    an id whose parameter brackets hold spaces (`f[a b]`, nested `f[a[1] b]`) is read up to its closing `]`; the end
    of the `\\S+` token (the plain reading) when a bracket is never closed. One pass, no backtracking."""
    depth = 0
    for i in range(start, len(ln)):
        c = ln[i]
        if c == "[":
            depth += 1
        elif c == "]" and depth:
            depth -= 1
        elif c.isspace() and not depth:
            return i
    return len(ln) if not depth else start + len(ln[start:].split(None, 1)[0])


def pytest_test_id(ln):
    """The pytest id a failure line names (`FAILED a.py::t[a b] - msg`, `a.py::t[a b] FAILED`), else ''."""
    m = PYTEST_ID_START_RE.match(ln)
    if not m:
        return ""
    end = pytest_id_end(ln, m.start(1))
    if end <= m.end(1):
        return ""
    if ln[:m.start(1)] or PYTEST_VERDICT_RE.match(ln, end):
        return ln[m.start(1):end]
    return ""


def first_failure(log, prefix_re=None):
    """What failed first in a job log: the first failing pytest test id (`FAILED a.py::t`, `a.py::t FAILED`), else the
    normalised first line that names an error or a failure, else ''. `prefix_re` (default LOG_PREFIX_RE) takes the
    runner's per-line prefix off."""
    prefix_re = prefix_re or LOG_PREFIX_RE
    lines = [prefix_re.sub("", ANSI_RE.sub("", ln)).strip() for ln in (log or "").splitlines()]
    for ln in lines:
        tid = pytest_test_id(ln)
        if tid:
            return tid
    for ln in lines:
        if ERROR_LINE_RE.search(ln):
            return normalise_error_line(ln, prefix_re)
    return ""


def failure_fingerprint(job, failure=""):
    """12 hex characters naming one way of failing: the failed job's name and what failed first in it (a test id or
    a normalised error line, `first_failure`). Two pipelines that fail the same way get the same fingerprint. With
    no readable log `failure` is '' and the job alone names it."""
    return hashlib.sha256(f"{job}\n{failure}".encode("utf-8")).hexdigest()[:12]


def github_jobs(host, project, rid, run):
    """The jobs of GitHub Actions run `rid`, as `gh run view --json jobs` answers them, or None."""
    code, o, _ = run(["gh", "run", "view", str(rid), "-R", f"{host}/{project}", "--json", "jobs"])
    try:
        js = json.loads(o) if code == 0 else None
    except ValueError:
        js = None
    js = js.get("jobs") if isinstance(js, dict) else None
    return js if isinstance(js, list) else None


def latest_pipeline(root, job=None, run=None):
    """(pipeline, note): a finished pipeline of origin's main as {id, sha, url, red, jobs, unverified, how}, a red
    one with `failure` and `fingerprint` read from the log of its first failed job by name, and `first` (that job's
    name, which the bug's repro names) only when its script ran and failed, or None with the note that says why not (no origin, glab or gh not signed in, a failed call, no such
    pipeline). Which pipeline, newest first among the last MAIN_PIPELINES (on GitLab, which costs one job-list call
    for each pipeline read, the read stops after IDLE_PIPELINES pipelines in a row in which no job ran, and the answer
    is then None with a note naming the stop (red-pipeline: "not checked"), never a verdict, since a job that ran behind more pipelines
    no one started, red or not, is out of reach):
    - with `job`: the newest in which that job succeeded or failed on its own account (`ql_deliver.job_decided`),
      red when it failed: a job started and then canceled, left manual or skipped, or failed without its script
      (ci_quota_exceeded, runner_system_failure) holds no verdict;
    - else on GitLab the newest that failed or in which a job ran (every job is manual, so a newer pipeline no one
      started hides nothing), or the newest finished one when no job ran in any of the pipelines listed and the read
      did not stop early; on GitHub the newest completed run.
    On GitLab a pipeline waiting on manual jobs counts as finished, and one whose status is no failure is read by its
    jobs (`ql_deliver.job_verdict`): red when a job someone started failed, else `unverified` says how each gate job
    did not succeed. `how` names the choice for the message."""
    from ql_deliver import (GITHUB_RED, RAN_AND_FAILED, any_ran, counting, forge_list, gitlab_jobs, job_decided,
                            job_verdict, latest_jobs, origin_forge)
    run, calls = counting(run or run_argv)  # `calls` is the pipeline's `calls`: the job-list calls this read made
    import kbpublic
    remote = kbpublic.integration_remote(root)
    code, url, _ = run(["git", "remote", "get-url", remote], cwd=root)
    if code:
        return None, f"no {remote} remote"
    url = url.strip()
    forge, host, project = origin_forge(url)
    quoted = project.replace("/", "%2F")
    data, cli, note = forge_list(
        url, run, lambda repo: ["gh", "run", "list", "--branch", "main", "-R", repo, "--json",
                                "databaseId,headSha,status,conclusion,url", "-L", str(MAIN_PIPELINES)],
        lambda p: f"projects/{p}/pipelines?ref=main&per_page={MAIN_PIPELINES}", named=3)
    if data is None:
        return None, note
    newest = None  # GitLab without `job`: the newest finished pipeline, read when no job ran in any
    idle = read = 0  # GitLab: the pipelines read in a row in which no job ran, and the pipelines read
    for r in data:
        if idle >= IDLE_PIPELINES:  # an older job, red or not, is out of reach: no verdict
            return None, (f"no job ran in the last {idle} pipelines of main read on {host}, where the read "
                          f"stops (IDLE_PIPELINES), so a job that ran before them is out of reach ({cli})")
        if not isinstance(r, dict):
            continue
        jobs = None
        if forge == "github":
            if r.get("status") != "completed":
                continue
            p = {"id": r.get("databaseId"), "sha": r.get("headSha"), "url": r.get("url"),
                 "red": r.get("conclusion") in GITHUB_RED, "unverified": [], "how": "the newest completed"}
            if job:
                jobs = github_jobs(host, project, p["id"], run)
                mine = [j for j in jobs or [] if isinstance(j, dict) and j.get("name") == job
                        and j.get("conclusion") in ("success",) + GITHUB_RED]
                if jobs is None:  # as on GitLab: an unreadable job list is no verdict, and no reason to read an older run
                    p["red"], p["unverified"] = False, ["the pipeline's jobs could not be read"]
                elif not mine:
                    continue
                else:
                    p["red"] = mine[0].get("conclusion") in GITHUB_RED
                p["how"] = f"the newest {job}"
        else:
            if r.get("status") not in GITLAB_FINISHED:
                continue
            p = {"id": r.get("id"), "sha": r.get("sha"), "url": r.get("web_url"), "red": r.get("status") == "failed",
                 "unverified": [], "how": "the newest started"}
            jobs = gitlab_jobs(host, quoted, p["id"], run)
            read += 1
            idle = idle + 1 if jobs is not None and not any_ran(jobs) else 0
            if job:
                mine = latest_jobs(jobs).get(job)
                if jobs is None:
                    p["red"], p["unverified"] = False, ["the pipeline's jobs could not be read"]
                elif mine is None or not job_decided(mine):
                    continue  # canceled, manual, skipped or failed without its script: no verdict on the job
                else:
                    p["red"] = mine.get("status") == "failed"
                p["how"] = f"the newest {job}"
            elif not p["red"]:
                if jobs is not None and not any_ran(jobs):
                    newest = newest or (p, jobs)
                    continue
                verdict, _, unpassed = job_verdict(jobs)
                p["red"] = verdict == "red"
                p["unverified"] = unpassed if verdict in ("pending", "unverified") else []
        return dict(red_detail(p, jobs, forge, host, project, quoted, RAN_AND_FAILED, run, job), calls=calls[0]), note
    if newest:
        p, jobs = newest
        verdict, _, unpassed = job_verdict(jobs)
        p["red"] = verdict == "red"
        p["unverified"] = unpassed if verdict in ("pending", "unverified") else []
        p["how"] = f"no job ran in the last {read}; the newest finished"
        return dict(red_detail(p, jobs, forge, host, project, quoted, RAN_AND_FAILED, run), calls=calls[0]), note
    which = f"in which {job} ran" if job else "finished"
    return None, f"no pipeline of main {which} among the last {read or MAIN_PIPELINES} on {host} ({cli})"


def red_detail(p, jobs, forge, host, project, quoted, ran_and_failed, run, job=None):
    """`p` with `jobs` (the failed jobs' names) and, when it is red, `failure` and `fingerprint` read from the log of
    its first failed job by name (among the jobs whose script ran, when there are any; `job` when given), and `first`,
    that job's name, only when its script ran and failed (on GitHub, any failed job): the bug's repro names it with
    `--job`, which reads only a pipeline where the job reached a verdict, so a job that failed without running (such as
    ci_quota_exceeded or runner_system_failure) gets plain `--status`, which reads the red pipeline itself. On GitLab a
    job counts by its newest attempt (`ql_deliver.latest_jobs`): one that failed and was retried to success is no
    failed job."""
    from ql_deliver import latest_jobs
    p["jobs"] = []
    if not p["red"]:
        return p
    if forge == "github":
        js = jobs if jobs is not None else github_jobs(host, project, p["id"], run) or []
        bad, field = ("failure", "timed_out", "startup_failure"), "conclusion"
    else:
        js, bad, field = list(latest_jobs(jobs).values()), ("failed",), "status"  # a retried job's newest attempt
    failed = [j for j in js if isinstance(j, dict) and j.get(field) in bad and j.get("name")]
    failed = [j for j in failed if j.get("failure_reason") in ran_and_failed] or failed  # scripts that ran
    if job:
        failed = [j for j in failed if j["name"] == job][:1] or failed
    p["jobs"] = [j["name"] for j in failed]
    if failed:
        first = min(failed, key=lambda j: str(j["name"]))  # the failed job the fingerprint names
        jid = first.get("databaseId" if forge == "github" else "id")
        log = ""
        if jid is not None:
            argv = (["gh", "api", "--hostname", host, f"repos/{project}/actions/jobs/{jid}/logs"]
                    if forge == "github" else
                    ["glab", "api", "--hostname", host, f"projects/{quoted}/jobs/{jid}/trace"])
            code, o, _ = run(argv)
            log = o if code == 0 else ""
        if forge == "github" or first.get("failure_reason") in ran_and_failed:
            p["first"] = str(first["name"])
        p["failure"] = first_failure(log)
        p["fingerprint"] = failure_fingerprint(first["name"], p["failure"])
    return p


def covered_by_revert(root, sha, run=None):
    """True when an automatic revert (KB-Auto: revert) on origin/main reverts the automatic push that `sha` ends;
    None when the history cannot be read. The revert commit names the first commit of that push."""
    import kbpublic
    run = run or run_argv
    code, o, _ = run(["git", "log", f"{sha}..{kbpublic.integration_remote(root)}/main", "--format=%B%x1e"], cwd=root)
    if code:
        return None
    for body in o.split("\x1e"):
        m = re.search(r"^This reverts commit ([0-9a-f]{40})\b", body, re.M)
        if not m or "KB-Auto: revert" not in body:
            continue
        first = m.group(1)
        if sha == first:
            return True
        code, o2, _ = run(["git", "log", f"{first}..{sha}", "--format=%(trailers:key=KB-Auto,valueonly)%x1e"], cwd=root)
        recs = o2.split("\x1e")[:-1] if code == 0 else []
        if code == 0 and all(r.strip() for r in recs):
            return True
    return False


def pipeline_candidate(pid, sha, sev, jobs=(), url=None, extra="", fingerprint=None, job=None):
    """The bug candidate of a red pipeline of main: it names `pipeline PID` (the marker red-pipeline files by) in its
    title and links, and `fingerprint <hex>` in its links when one is given; its repro is
    `red-pipeline --status --job JOB` (the failed job the fingerprint names, when its script ran and failed), which
    fails until JOB passes on main again, or plain `--status` (the newest pipeline of main in which a job ran) when
    no such job was read; `extra` closes
    its notes. The fingerprint is the failure's own (`failure_fingerprint`), not the hash of the key: a pipeline that
    fails the same way as an earlier one is one finding."""
    marker = f"pipeline {pid}"
    repro = list(PIPELINE_REPRO) + (["--job", job] if job else [])
    end = (f"The newest pipeline of main in which {job} ran passed it" if job else
           "The newest pipeline of main in which a job ran is green")
    return Candidate(
        kind="bug", severity=sev, priority="P1" if sev == "S1" else "P2", key=marker,
        title=f"Red main {marker}: {', '.join(jobs) or 'no failed job read'}"[:200],
        goal=f"{end}: `{shlex.join(repro)}` exits 0.", repro=repro, lead_links=[marker],
        fp=fingerprint or "", fp_fixed=fingerprint or "",
        notes=(f"{marker.capitalize()} of commit {str(sha)[:12]} failed"
               + (f" in {', '.join(jobs)}" if jobs else "") + (f": {url}" if url else "") + "."
               + (" " + extra if extra else ""))[:TEXT_MAX])


def pipeline_finding(p):
    """The `pipeline_candidate` of a red pipeline `p` as `latest_pipeline` read it: S1 when a job of S1_JOBS failed,
    else S2."""
    jobs = p["jobs"]
    return pipeline_candidate(p["id"], p["sha"], "S1" if any(j in S1_JOBS for j in jobs) else "S2", jobs, p.get("url"),
                              f"It failed first on: {p['failure']}." if p.get("failure") else "",
                              fingerprint=p.get("fingerprint"), job=p.get("first"))


@detector("ci")
def ci_detector(root, run=None):
    """One bug when the newest pipeline of the integration main in which a job ran is red and no automatic revert covers
    it (`kb/_self/backlog.md`, red pipeline): the same candidate, fingerprint and links `backlog.py red-pipeline` files,
    so whichever runs first files the bug and the other finds it. A pipeline whose jobs nobody started is green; one
    that cannot be read (no remote, not signed in, a failed call) reports nothing. It fetches the integration main and
    calls the forge, so `collect` runs it only with `network` (`intake --network`)."""
    run = run or run_argv
    import kbpublic
    run(["git", "fetch", "-q", kbpublic.integration_remote(root), "main"], cwd=root)
    p, _ = latest_pipeline(root, None, run)
    if p is None or not p["red"] or covered_by_revert(root, p["sha"], run) is not False:
        return []
    return [pipeline_finding(p)]
