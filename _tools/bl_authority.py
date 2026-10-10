"""Who may answer a gate (kb/_self/backlog.md, Dependencies, gates and triggers): the class of a gate and the classes
only the operator answers.

Every gate has a class, one of CLASSES, listed from the most restricted to the least. `gate_class(item, gate)` derives
it from the item's `touches` and the gate's question and id: the strictest class any of them names, `design` when none
does; `class_reasons` also names the touches and words that set it, which `gate add` prints. A class a gate stores (`gate add` writes it) is read as a floor for nothing but the record: the class in force is
the stricter of the stored and the derived, so an agent that writes a lower class into an item file changes nothing,
and `lowered` names it for `check`. A gate of a class in OPERATOR_CLASSES (secrets, push and agents-rule) is blocking
and takes only the operator's answer; the operator answers every class.

Standard library only; imports `bl_base` and never `backlog`, `bl_check` or `bl_plan`."""
import fnmatch
import posixpath
import re

from bl_base import START_GATE

CLASSES = ("secrets", "push", "start", "querylog", "agents-rule", "delete", "design")
OPERATOR_CLASSES = ("secrets", "push", "agents-rule")  # the classes only the operator answers

# Paths whose change makes a gate about the item one of the class: a directory ends with `/`, a file is exact. A touch
# names one when it is the path, a directory above it, or a glob that matches it.
PATHS = {
    "push": ("_tools/kbgit.py", "_tools/kbpublic.py", "_tools/kg_", "_tools/kblane.py", ".gitlab-ci.yml", ".github/",
             ".githooks/"),
    "querylog": ("kb/_querylog/",),
    # the rules agents run under (the plugin's `skills/` and `agents/` at its root are the one set the `.claude` entries
    # link to), and the code that guards them: the gate classes, the self-check, the hook script and the decision
    # record, and the code the tests run (the bl_ modules, the test runner and its conftest)
    "agents-rule": ("AGENTS.md", "CLAUDE.md", ".claude/agents/", ".claude/skills/", ".claude/hooks/",
                    ".claude/settings.json", ".claude/settings.local.json", ".claude-plugin/", "skills/", "agents/",
                    "_tools/bl_", "_tools/tests.py", "_tools/conftest.py", "_tools/kb_hook.py", "_tools/kbdecide.py",
                    "_tools/backlog.py", "_tools/kbpy"),
}
SECRET_WORDS = re.compile(r"secret|credential|password|\.env\b|private[-_ ]?key", re.I)
# `token` names a token file (`api.token`, `tokens.json`, `auth-token.db`) or a directory of them, so it classes a touch
# `secrets` anywhere but in the file name of a Markdown doc (`kb/_self/token-efficiency.md` is about token cost).
TOKEN_WORD = re.compile(r"token", re.I)


def names_secret(touch):
    """Whether the touch's path names a secret, credential, password, `.env`, private key or token file."""
    if not isinstance(touch, str):
        return False
    if SECRET_WORDS.search(touch):
        return True
    head, _, name = touch.strip().replace("\\", "/").rstrip("/").rpartition("/")
    return bool(TOKEN_WORD.search(head) or TOKEN_WORD.search(name) and not name.lower().endswith(".md"))

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


def class_reasons(item, gate):
    """The strictest class the item's touches and the gate's id and question name (`design` when none), with what set
    it: each touch (`touch '_tools/bl_items.py'`) and each word of the gate's text (`matched 'rule'`) that names that
    class, in that order; no reason for `design`. `derived_class` reads its class here, so the two never diverge."""
    found = {}
    if gate.get("id") == START_GATE:
        found.setdefault("start", []).append(f"gate id '{START_GATE}'")
    touches = [t for t in item.get("touches", []) or [] if isinstance(t, str)]
    for cls, paths in PATHS.items():
        for t in touches:
            if any(touch_names(t, p) for p in paths):
                found.setdefault(cls, []).append(f"touch '{t}'")
    for t in touches:
        if names_secret(t):
            found.setdefault("secrets", []).append(f"touch '{t}'")
    text = f"{gate.get('question', '')} {' '.join(map(str, gate.get('options', []) or []))} {command_words(gate)}"
    for cls, rx in QUESTION_WORDS.items():
        m = rx.search(text)
        if m:
            found.setdefault(cls, []).append(f"matched '{m.group(0)}'")
    m = re.search(r"sprint'?s? start|start (?:the )?sprint", text, re.I)
    if m:
        found.setdefault("start", []).append(f"matched '{m.group(0)}'")
    if not found:
        return "design", []
    cls = min(found, key=rank)
    return cls, list(dict.fromkeys(found[cls]))


def derived_class(item, gate):
    """The strictest class the item's touches and the gate's id and question name; `design` when none."""
    return class_reasons(item, gate)[0]


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

