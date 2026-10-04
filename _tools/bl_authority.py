"""Who may answer a gate (kb/_self/backlog.md, Dependencies, gates and triggers): the class of a gate and the autopilot's
authority over it.

Every gate has a class, one of CLASSES, listed from the most restricted to the least. `gate_class(item, gate)` derives
it from the item's `touches` and the gate's question and id: the strictest class any of them names, `design` when none
does. A class a gate stores (`gate add` writes it) is read as a floor for nothing but the record: the class in force is
the stricter of the stored and the derived, so an agent that writes a lower class into an item file changes nothing,
and `lowered` names it for `check`. The autopilot answers every class but AUTOPILOT_REFUSED (secrets, push and agents-rule); the operator answers all.

Standard library only; imports `bl_base` and never `backlog`, `bl_check` or `bl_plan`."""
import datetime
import fnmatch
import posixpath
import os
import re
from pathlib import Path

from bl_base import START_GATE

AUTOPILOT = "autopilot"  # the `by` of an answer the autopilot gave, and its decision maker in kb/_self
CLASSES = ("secrets", "push", "start", "querylog", "agents-rule", "delete", "design")
AUTOPILOT_REFUSED = ("secrets", "push", "agents-rule")  # the classes only the operator answers
HEADLESS_ENV = "KB_HEADLESS_RUNNER"  # set (non-empty) in every headless runner's environment: kbpublic.HEADLESS_ENV, kbdecide.py's copy
REVIEW_DAYS = 14  # an autopilot decision's `review_by`: the operator ratifies or supersedes it by then

# Paths whose change makes a gate about the item one of the class: a directory ends with `/`, a file is exact. A touch
# names one when it is the path, a directory above it, or a glob that matches it.
PATHS = {
    "push": ("_tools/kbgit.py", "_tools/kbpublic.py", "_tools/kg_", "_tools/kblane.py", ".gitlab-ci.yml", ".github/",
             ".githooks/"),
    "querylog": ("kb/_querylog/",),
    # the rules agents run under, and the code that guards the autopilot itself: a sprint may not approve a change to
    # its own runner, gate classes, bounds, self-check, edit guard or decision record, nor to the code the tests run
    # (the bl_ modules, the test runner and its conftest)
    "agents-rule": ("AGENTS.md", "CLAUDE.md", ".claude/agents/", ".claude/skills/", ".claude/hooks/",
                    ".claude/settings.json", ".claude/settings.local.json", ".claude-plugin/",
                    "_tools/bl_", "_tools/tests.py", "_tools/conftest.py", "_tools/kb_hook.py", "_tools/kbdecide.py",
                    "_tools/backlog.py", "_tools/kbpy"),
}
SECRET_WORDS = re.compile(r"secret|credential|password|\.env\b|token|private[-_ ]?key", re.I)
# A gate's text is its question, its options and the words of its `do` and `host_check` commands. `origin`, `mirror` and
# `release` are word-bounded (`original` is not `origin`) and take their endings (`releases`, `released`, `mirrored`),
# so a gate about a release note is `push` too: the classifier fails closed.
QUESTION_WORDS = {
    "secrets": re.compile(r"secret|credential|password|passphrase|token|\bPATs?\b|\bbearer\b|\bssh\b|api[- ]key|"
                          r"private key|\.env\b|rotat\w*\s+(?:\w+\s+){0,2}keys?\b", re.I),
    "push": re.compile(r"\bpush(?:ing)?\b|publish|force[- ]push|\bremote\b|\bgithub\b|\bgitlab\b|\borigin\b|"
                       r"\bmirror(?:s|ed|ing)?\b|\breleas(?:e|es|ed|ing)\b|public[- ]repositor(?:y|ies)|"
                       r"\buploa(?:d|ds|ded|ding)\b|\bdeploy(?:s|ed|ing|ment)?\b|merge[- ]requests?\b", re.I),
    "querylog": re.compile(r"query[- ]?log|querylog|redact", re.I),
    "agents-rule": re.compile(r"AGENTS\.md|CLAUDE\.md|\brule\b|\bskill\b|\bagent definition", re.I),
    "delete": re.compile(r"\bdelet|\bremov(?:e|ing) .*(?:kb|content|history)|purge|erase", re.I),
}


def norm(touch):
    """A touch as a lower-case, slash-separated path with no leading `./` or trailing `/` (`.` for the root)."""
    return posixpath.normpath(touch.strip().replace("\\", "/")).lower()


def touch_names(touch, path):
    """Whether the touch `touch` names `path` (a file, or a directory ending `/`, or a prefix ending `_`). A touch is
    read lower-case with a leading `./` and a trailing `/` dropped; a directory touch (`_tools/`, `.claude`, `.`)
    names every path under it."""
    if not isinstance(touch, str) or not touch.strip():
        return False
    t, path = norm(touch), path.lower()
    under = t == "." or path.startswith(t + "/")  # the touch is a directory above the path
    if path.endswith("/"):
        return under or t.startswith(path) or fnmatch.fnmatchcase(path + "x", t) or t == path.rstrip("/")
    if path.endswith("_"):  # a family of files: `_tools/kg_` is every `_tools/kg_*.py`
        return under or t.startswith(path) or fnmatch.fnmatchcase(path + "x.py", t)
    return under or t == path or fnmatch.fnmatchcase(path, t)


# Files kb_hook.headless_guard denies a headless Edit/Write beside the PATHS of the agents-rule and push classes.
GUARD_EXTRA = ("_tools/kb_hook.py", "_tools/kbpy", ".githooks/")


def guard_paths():
    """The project paths a headless run never writes (kb_hook.guard_paths returns this): the guard's own files and the
    files PATHS gives the agents-rule and push classes (a directory ends with /, a family of files with _)."""
    return GUARD_EXTRA + tuple(p for cls in ("agents-rule", "push") for p in PATHS[cls])


NEW_TEST_FILE = re.compile(r"_tools/test_[^/]*\.py")  # kb_hook.NEW_TEST_FILE: a test file tests.py would run as code


def project_dir():
    """The project the guard judges paths against: CLAUDE_PROJECT_DIR, else this clone (kb_hook.repo_path's rule)."""
    return os.path.realpath(os.environ.get("CLAUDE_PROJECT_DIR") or os.path.dirname(os.path.dirname(
        os.path.realpath(__file__))))


def new_test_file(touch, root=None):
    """Whether the touch names a `_tools/test_*.py` that does not exist yet, which kb_hook.headless_guard denies a
    headless Write of. A path is judged by whether the file exists; a glob by what it matches today (an existing file
    unguards it, no file at all guards it); an existing test file stays unguarded."""
    path = posixpath.normpath(touch.strip().replace("\\", "/"))
    if not NEW_TEST_FILE.fullmatch(path.lower()):
        return False
    root = root or project_dir()
    if any(c in path for c in "*?["):
        return not any(True for _ in Path(root).glob(path))
    return not os.path.exists(os.path.join(root, path))


def guarded_touches(item, root=None):
    """The item's touches a headless run may not edit: each names a guard_paths() entry (the path, a directory above
    it, a glob that matches it) or lies inside one (`_tools/kbpy/x.py`), or names a `_tools/test_*.py` that does not
    exist yet (the headless guard denies creating it). `backlog.py start` names them, so such a sprint is operator-present only."""
    found = []
    for t in item.get("touches", []) or []:
        if not isinstance(t, str) or not t.strip():
            continue
        n = norm(t)
        if any(touch_names(t, p) or n.startswith(p.lower() + "/") for p in guard_paths()) or new_test_file(t, root):
            found.append(t)
    return found


def command_words(gate):
    """The words of a gate's `do` and `host_check` commands (argv lists, or a string)."""
    out = []
    for key in ("do", "host_check"):
        v = gate.get(key)
        out += [str(x) for x in v] if isinstance(v, (list, tuple)) else [str(v)] if v else []
    return " ".join(out)


def rank(cls):
    """The place of a class in CLASSES (0 the most restricted); an unknown class ranks as the most restricted."""
    return CLASSES.index(cls) if cls in CLASSES else 0


def derived_class(item, gate):
    """The strictest class the item's touches and the gate's id and question name; `design` when none."""
    found = set()
    if gate.get("id") == START_GATE:
        found.add("start")
    for cls, paths in PATHS.items():
        if any(touch_names(t, p) for t in item.get("touches", []) or [] for p in paths):
            found.add(cls)
    if any(isinstance(t, str) and SECRET_WORDS.search(t) for t in item.get("touches", []) or []):
        found.add("secrets")
    text = f"{gate.get('question', '')} {' '.join(map(str, gate.get('options', []) or []))} {command_words(gate)}"
    for cls, rx in QUESTION_WORDS.items():
        if rx.search(text):
            found.add(cls)
    if re.search(r"sprint'?s? start|start (?:the )?sprint", text, re.I):
        found.add("start")
    return min(found, key=rank) if found else "design"


def gate_class(item, gate):
    """The class in force: the stricter of the class the gate stores and the one derived from the item and the question."""
    d = derived_class(item, gate)
    stored = gate.get("class")
    return stored if stored in CLASSES and rank(stored) < rank(d) else d


def lowered(item, gate):
    """The stored class when it is less restricted than the derived one (an agent edited it down), else None."""
    stored = gate.get("class")
    if stored is None:
        return None
    if gate.get("by") == "operator" and "answer" in gate:  # the operator answered it: the class guarded nothing since
        return None
    d = derived_class(item, gate)
    return stored if stored not in CLASSES or rank(stored) > rank(d) else None


def autopilot_may_answer(item, gate):
    """(allowed, class): whether the autopilot may answer the gate, with the class in force. A gate with no question
    text is refused, its class `unclassified (no question)`: there is nothing to classify."""
    if not isinstance(gate.get("question"), str) or not gate["question"].strip():
        return False, "unclassified (no question)"
    cls = gate_class(item, gate)
    if gate.get("id") == START_GATE:  # a sprint that changes the push path, secrets or the rules is started by the operator
        held = derived_class(item, {**gate, "id": "", "question": "-"})
        if held in AUTOPILOT_REFUSED:
            return False, held
    return cls not in AUTOPILOT_REFUSED, cls


def review_by(today=None, days=REVIEW_DAYS):
    """The ISO date an autopilot decision falls due for the operator's review."""
    return ((today or datetime.date.today()) + datetime.timedelta(days=days)).isoformat()


def sprint_scope(item, gate, members):
    """The item whose touches classify the gate: for a sprint's start gate the item with the touches of every member
    item (`members`, the sprint's items but a dropped one) added, so the class is the strictest over what the sprint would run; any
    other gate, or a sprint without members, the item itself."""
    if item.get("kind") != "sprint" or gate.get("id") != START_GATE:
        return item
    touches = list(item.get("touches", []) or [])
    for m in (m for m in members if m.get("status") != "dropped"):
        touches += [t for t in m.get("touches", []) or [] if t not in touches]
    return {**item, "touches": touches}


def headless():
    """True in a headless runner's process (and the children it starts): the variable the runner sets is not empty."""
    return bool(os.environ.get(HEADLESS_ENV))


def headless_operator_refusal(what):
    """The message that refuses `what` (an act recorded as the operator's) in a headless run; the guard that holds when
    a permission rule's text match misses an argument order or an option abbreviation."""
    return (f"{what} is the operator's and {HEADLESS_ENV} is set: only an operator-present session answers as the "
            "operator (--by agent and --provisional are open to a headless run, --by autopilot is not: a runner answers --by agent only)")
