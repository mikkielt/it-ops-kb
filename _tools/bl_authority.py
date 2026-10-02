"""Who may answer a gate (kb/_self/backlog.md, Dependencies, gates and triggers): the class of a gate and the autopilot's
authority over it.

Every gate has a class, one of CLASSES, listed from the most restricted to the least. `gate_class(item, gate)` derives
it from the item's `touches` and the gate's question and id: the strictest class any of them names, `design` when none
does. A class a gate stores (`gate add` writes it) is read as a floor for nothing but the record: the class in force is
the stricter of the stored and the derived, so an agent that writes a lower class into an item file changes nothing,
and `lowered` names it for `check`. The autopilot answers every class but AUTOPILOT_REFUSED; the operator answers all.

Standard library only; imports `bl_base` and never `backlog`, `bl_check` or `bl_plan`."""
import datetime
import fnmatch
import posixpath
import re

from bl_base import START_GATE

AUTOPILOT = "autopilot"  # the `by` of an answer the autopilot gave, and its decision maker in kb/_self
CLASSES = ("secrets", "push", "start", "querylog", "agents-rule", "delete", "design")
AUTOPILOT_REFUSED = ("secrets", "push")  # the classes only the operator answers
REVIEW_DAYS = 14  # an autopilot decision's `review_by`: the operator ratifies or supersedes it by then

# Paths whose change makes a gate about the item one of the class: a directory ends with `/`, a file is exact. A touch
# names one when it is the path, a directory above it, or a glob that matches it.
PATHS = {
    "push": ("_tools/kbgit.py", "_tools/kbpublic.py", "_tools/kg_", ".gitlab-ci.yml", ".github/", ".githooks/"),
    "querylog": ("kb/_querylog/",),
    "agents-rule": ("AGENTS.md", "CLAUDE.md", ".claude/agents/", ".claude/skills/", ".claude/hooks/",
                    ".claude/settings.json", ".claude-plugin/"),
}
SECRET_WORDS = re.compile(r"secret|credential|password|\.env\b|token|private[-_ ]?key", re.I)
# A gate's text is its question, its options and the words of its `do` and `host_check` commands. `origin`, `mirror` and
# `release` are word-bounded (`original` is not `origin`) and take their endings (`releases`, `released`, `mirrored`),
# so a gate about a release note is `push` too: the classifier fails closed.
QUESTION_WORDS = {
    "secrets": re.compile(r"secret|credential|password|token|api[- ]key|private key|\.env\b|rotat\w*\s+(?:\w+\s+){0,2}keys?\b",
                          re.I),
    "push": re.compile(r"\bpush(?:ing)?\b|publish|force[- ]push|\bremote\b|\bgithub\b|\borigin\b|\bmirror(?:s|ed|ing)?\b|"
                       r"\breleas(?:e|es|ed|ing)\b|public[- ]repositor(?:y|ies)", re.I),
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
        if held in AUTOPILOT_REFUSED + ("agents-rule",):
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
