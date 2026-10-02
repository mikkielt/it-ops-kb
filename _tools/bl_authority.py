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
import re

from bl_base import START_GATE

AUTOPILOT = "autopilot"  # the `by` of an answer the autopilot gave, and its decision maker in kb/_self
CLASSES = ("secrets", "push", "start", "querylog", "agents-rule", "delete", "design")
AUTOPILOT_REFUSED = ("secrets", "push")  # the classes only the operator answers
REVIEW_DAYS = 30  # an autopilot decision's `review_by`: the operator ratifies or supersedes it by then

# Paths whose change makes a gate about the item one of the class: a directory ends with `/`, a file is exact. A touch
# names one when it is the path, a directory above it, or a glob that matches it.
PATHS = {
    "push": ("_tools/kbgit.py", "_tools/kg_", ".gitlab-ci.yml", ".github/", ".githooks/"),
    "querylog": ("kb/_querylog/",),
    "agents-rule": ("AGENTS.md", "CLAUDE.md", ".claude/agents/", ".claude/skills/", ".claude/settings.json",
                    ".claude-plugin/"),
}
SECRET_WORDS = re.compile(r"secret|credential|password|\.env\b|token|private[-_ ]?key", re.I)
QUESTION_WORDS = {
    "secrets": re.compile(r"secret|credential|password|token|api[- ]key|private key", re.I),
    "push": re.compile(r"\bpush(?:ing)?\b|publish|force[- ]push|\bremote\b|\bgithub\b", re.I),
    "querylog": re.compile(r"query[- ]?log|querylog|redact", re.I),
    "agents-rule": re.compile(r"AGENTS\.md|CLAUDE\.md|\brule\b|\bskill\b|\bagent definition", re.I),
    "delete": re.compile(r"\bdelet|\bremov(?:e|ing) .*(?:kb|content|history)|purge|erase", re.I),
}


def touch_names(touch, path):
    """Whether the touch `touch` names `path` (a file, or a directory ending `/`, or a prefix ending `_`)."""
    if not isinstance(touch, str) or not touch:
        return False
    if path.endswith("/"):
        return touch.startswith(path) or fnmatch.fnmatchcase(path + "x", touch) or touch == path.rstrip("/")
    if path.endswith("_"):  # a family of files: `_tools/kg_` is every `_tools/kg_*.py`
        return touch.startswith(path) or fnmatch.fnmatchcase(path + "x.py", touch)
    return touch == path or fnmatch.fnmatchcase(path, touch)


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
    text = f"{gate.get('question', '')} {' '.join(map(str, gate.get('options', []) or []))}"
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
    d = derived_class(item, gate)
    return stored if stored not in CLASSES or rank(stored) > rank(d) else None


def autopilot_may_answer(item, gate):
    """(allowed, class): whether the autopilot may answer the gate, with the class in force."""
    cls = gate_class(item, gate)
    return cls not in AUTOPILOT_REFUSED, cls


def review_by(today=None, days=REVIEW_DAYS):
    """The ISO date an autopilot decision falls due for the operator's review."""
    return ((today or datetime.date.today()) + datetime.timedelta(days=days)).isoformat()
