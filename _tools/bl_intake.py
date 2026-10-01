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
- `lines(candidate)`: the lines the command prints for one candidate.

This module imports no other tool module (it is below backlog.py).
"""
import hashlib
import re
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
