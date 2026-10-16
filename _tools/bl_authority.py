"""Who may answer a gate (kb/_self/backlog.md, Dependencies, gates and triggers): the class of a gate and the classes
only the operator answers, and of those the one no agent session answers at all.

Every gate has a class, one of CLASSES, listed from the most restricted to the least. `gate_class(item, gate)` derives
it from the item's `touches` and the gate's question and id: the strictest class any of them names, `design` when none
does; `class_reasons` also names the touches and words that set it, which `gate add` prints. A class a gate stores (`gate add` writes it) is read as a floor for nothing but the record: the class in force is
the stricter of the stored and the derived, so an agent that writes a lower class into an item file changes nothing,
and `lowered` names it for `check`. A gate of a class in OPERATOR_CLASSES (ceiling, secrets, push and agents-rule) is
blocking and takes only the operator's answer; the operator answers every class. The class in TERMINAL_CLASSES (ceiling,
the test suite's ceiling) is stricter still: `--by operator` from a Claude Code session (`in_agent_session`: the
environment names one, attended or not, headless or delegated) is no operator's answer, so it is recorded only from a
terminal of the operator's own.

Standard library only; imports `bl_base` and never `backlog`, `bl_check` or `bl_plan`."""
import fnmatch
import os
import posixpath
import re
from pathlib import Path

from bl_base import START_GATE

CLASSES = ("ceiling", "secrets", "push", "start", "querylog", "agents-rule", "delete", "design")
OPERATOR_CLASSES = ("ceiling", "secrets", "push", "agents-rule")  # the classes only the operator answers
TERMINAL_CLASSES = ("ceiling",)  # of those, the classes no agent session answers, whatever `--by` says
AGENT_SESSION_ENV = "CLAUDECODE"  # set in the environment of every Claude Code session and of each command it runs

# Paths whose change makes a gate about the item one of the class: a directory ends with `/`, a file is exact. A touch
# names one when it is the path, a directory above it, or a glob that matches it.
PATHS = {
    "ceiling": ("_tools/tests_ceiling.json",),
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


# In a gate's text `token` is a secret word, but not in the sense of a model's token counts (`output tokens`, `token
# counts`, `usage.output_tokens`) nor in the sense of the words of a text (`token overlap`, `overlap of the
# tokens`, `words or tokens`, `word tokens`) nor in the file name of a Markdown doc (`kb/_self/token-efficiency.md`, as
# for a touch). The ops-row value shapes `phase token` and `closed token` are no secret either, nor an upper-case identifier of
# token counts that holds `TOKENS` in the plural (`DISPATCH_BASE_TOKENS`, `MAX_TOKENS`). A bare `token`, one qualified
# as a credential (`API token counts` is a count of API tokens), a singular identifier (`GITLAB_TOKEN`) and a token file
# keep the class: the classifier fails closed.
TOKEN_DOC = re.compile(r"[\w./\\-]*token[\w./\\-]*\.md\b", re.I)
CRED_WORDS = "api|access|auth|bearer|refresh|session|personal|oauth|csrf|jwt|id"
TOKEN_COUNT = re.compile(
    rf"(?P<cred>\b(?:{CRED_WORDS})[-_ ])?"
    r"(?:\b(?:output|input|prompt|completion|cached?|total|max|context|reasoning)[-_ ]tokens?\b|"
    r"\b(?:phase|closed)[-_ ]tokens?\b|"
    r"\btokens?[-_ ](?:counts?|usage|budgets?|limits?|costs?|efficiency|estimates?)\b|"
    r"\btokens?[-_ ]overlaps?\b|\boverlaps? of (?:\w+[ ]){0,3}tokens\b|\bwords?[ ]+(?:or|and)[ ]+tokens\b|"
    r"\btokens[ ]+(?:or|and)[ ]+words\b|\bword[-_ ]tokens?\b|"
    r"\b(?:counts?|number|numbers) of tokens\b|\btokens per (?:second|minute|request|run)\b)", re.I)
# An upper-case constant name with `TOKENS` in the plural as one of its parts, at least one other part before it, not
# the stem of a file name (`LIMIT_TOKENS.json`); one with a credential word (`API_TOKENS`) or a secret word
# (`SECRET_TOKENS`, `PRIVATE_TOKENS`, `KEY_TOKENS`) among its parts is no count, so it stays in the text searched.
TOKEN_IDENT = re.compile(r"\b(?:[A-Z0-9]+_)+TOKENS(?:_[A-Z0-9]+)*\b(?!\.\w)")
CRED_PART = re.compile(rf"^(?:{CRED_WORDS}|(?:secret|password|passphrase|private|key|credential|pat|ssh)s?)$", re.I)
# `tokens` as one of the unit nouns of a list (`units, points, tokens, requests, calls`): a run of three or more list
# elements that holds `tokens` and at least two other unit nouns, with no credential word right before `tokens`. A bare
# `tokens` or `tokens, rows` and a credential sense (`API tokens, units, points`) keep the class.
UNIT_NOUN = r"(?:units|points|requests|calls|rows|bytes|lines|words)"
LIST_ELEMENT = rf"(?:{UNIT_NOUN}|tokens)"
LIST_SEP = r"(?:[ \t]*,[ \t]*(?:(?:and|or)[ \t]+)?|[ \t]+(?:and|or)[ \t]+)"
UNIT_LIST = re.compile(rf"(?<![\w-])\b{LIST_ELEMENT}(?:{LIST_SEP}{LIST_ELEMENT}){{2,}}\b", re.I)
CRED_BEFORE = re.compile(rf"\b(?:{CRED_WORDS})[-_ ]$", re.I)


def unit_list_without_credential(text, m):
    """Whether the UNIT_LIST match `m` in `text` lists `tokens` among two or more other unit nouns and no credential
    word stands right before the list (`API tokens, units, points`)."""
    words = re.findall(r"[a-z]+", m.group(0).lower())
    others = [w for w in words if w not in ("tokens", "and", "or")]
    return "tokens" in words and len(others) >= 2 and not CRED_BEFORE.search(text[:m.start()])


def without_unit_lists(text):
    """The text with each list that names `tokens` among unit nouns replaced by a space. `text` is one option or the
    question alone: `class_reasons` calls it for each of them, so a list never runs across the join of two."""
    return UNIT_LIST.sub(lambda m: " " if unit_list_without_credential(text, m) else m.group(0), text)


def without_token_counts(text):
    """The text with each token-count phrase, each upper-case identifier of token counts and each Markdown doc name that
    holds `token` replaced by a space: what the `secrets` words are searched in, so a model's token counts, a constant
    such as `DISPATCH_BASE_TOKENS`, the ops-row `phase token` and a doc such as `token-efficiency.md` are no secret."""
    text = TOKEN_DOC.sub(lambda m: m.group(0) if names_secret(m.group(0)) else " ", text)
    text = TOKEN_IDENT.sub(
        lambda m: m.group(0) if any(CRED_PART.match(p) for p in m.group(0).split("_")) else " ", text)
    return TOKEN_COUNT.sub(lambda m: m.group(0) if m.group("cred") else " ", text)


# A gate's text is its question, its options and the words of its `do` and `host_check` commands. `origin`, `mirror` and
# `release` are word-bounded (`original` is not `origin`) and take their endings (`releases`, `released`, `mirrored`),
# so a gate about a release note is `push` too, wherever the word stands: the classifier fails closed. The word `rule`
# is no `agents-rule` word of its own (a design question about which rows count by rule is no rule-guarding work): it
# classes only where the item's touches or the gate's text name a rule-guarding path or file (`rule_paths`).
QUESTION_WORDS = {
    "ceiling": re.compile(r"\btests?[-_ ]ceiling|\bsuite(?:['\u2019]s)?[-_ ]ceiling|\bceiling (?:of|for) the (?:test )?suite|"
                          r"\bseconds[-_ ]ceiling|\b(?:darwin|linux|win32)(?:['\u2019]s)?[-_ ]ceiling|"
                          r"\btests\.py[-_ ]ceiling|\bmax_seconds\b", re.I),
    "secrets": re.compile(r"secret|credential|password|passphrase|token|\bPATs?\b|\bbearer\b|\bssh\b|api[- ]key|"
                          r"private key|\.env\b|rotat\w*\s+(?:\w+\s+){0,2}keys?\b", re.I),
    "push": re.compile(r"\bpush(?:ing)?\b|publish|force[- ]push|\bremote\b|\bgithub\b|\bgitlab\b|\borigin\b|"
                       r"\bmirror(?:s|ed|ing)?\b|\breleas(?:e|es|ed|ing)\b|public[- ]repositor(?:y|ies)|"
                       r"\buploa(?:d|ds|ded|ding)\b|\bdeploy(?:s|ed|ing|ment)?\b|merge[- ]requests?\b", re.I),
    "querylog": re.compile(r"query[- ]?log|querylog|redact", re.I),
    "agents-rule": re.compile(r"AGENTS\.md|CLAUDE\.md|\bskill\b|\bagent definition", re.I),
    "delete": re.compile(r"\bdelet|\bremov(?:e|ing) .*(?:kb|content|history)|purge|erase", re.I),
}
# The `ceiling` words are the wordings the rules use for the suite's ceiling (`seconds ceiling`, `darwin ceiling`, `the
# suite's ceiling`, `ceiling for the test suite`, `tests.py ceiling`, `max_seconds`), so a gate that names the seconds
# of a platform is `ceiling` on an item whose touches name no ceiling file.
# The start of the text `tests.ceiling_token` builds: `names_ceiling` finds it with no word boundary, as `read_ceiling` does.
CEILING_TOKEN = re.compile(r"tests-ceiling ids=", re.I)
RULE_WORD = re.compile(r"\brule\b", re.I)
# The file names of the `agents-rule` paths that are no directory (`settings.json`, `backlog.py`, `bl_` for each
# `bl_*` module): a bare one in a gate's text names its file, while a directory (`skills/`) needs a path with a `/`,
# since `agents` and `skills` alone are prose.
RULE_FILES = tuple(posixpath.basename(p).lower() for p in PATHS["agents-rule"] if not p.endswith("/"))


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


def rule_paths(text):
    """The words of a gate's text that name a rule-guarding path or file: a word with a `/` that a path of
    PATHS['agents-rule'] names (`.claude/skills/kb-sprint/SKILL.md`, `_tools/bl_items.py`), or a bare file name of one
    (`settings.json`, `bl_authority.py`)."""
    out = []
    for word in re.findall(r"[\w.*\\/-]+", text):
        word = word.rstrip(".")
        low = word.lower()
        if "/" in low or "\\" in low:
            named = any(touch_names(low, p) for p in PATHS["agents-rule"])
        else:
            named = any(low == f or f.endswith("_") and low.startswith(f) for f in RULE_FILES)
        if named:
            out.append(word)
    return out


# Three wordings that hold a `push` word and are no push: the upload date of a package release (`uploaded` beside a
# date or a time), a kb topic path (`gitlab/git-commit-paths-and-symlinks`, a domain `gitlab` before the hyphenated slug
# of an article that exists under `kb/*/gitlab/`: `gitlab/main` and any other ref is no topic) and a display-only count
# question, where the push is a noun after a preposition (`before its push`) that only places a count or a list
# (`how many unpushed commits does land list before its push?`) and no word of the question acts on it or asks for it
# (`should`, `retry`, `run`, `force`). Every other use of those words keeps the class.
UPLOAD_DATE = re.compile(
    r"\buploaded\s+(?:(?:on|at|in)\s+)?(?=\d{4}-\d{2}-\d{2}\b|\d{1,2}:\d{2}\b|\d{1,2}\s+"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}\b)", re.I)
TOPIC_PATH = re.compile(r"\bgitlab/([a-z0-9][a-z0-9.-]*[a-z0-9])\b")
COUNT_QUESTION = re.compile(r"\bhow (?:many|much)\b|\b(?:which|what) (?:count|number)\b", re.I)
DISPLAY_WORD = re.compile(r"\b(?:list|lists|listed|listing|show|shows|print|prints|count|counts|name|names|report|reports)\b",
                          re.I)
PUSH_NOUN = re.compile(r"\b(?:before|after|prior to|ahead of|until|during) (?:its|the) push\b", re.I)
PUSH_ACTION = re.compile(
    r"\b(?:should|may|must|shall|can|could|would|will|need|needs|do|did|retry|retries|run|runs|rerun|force|forced|redo|"
    r"undo|skip|repeat|perform|execute|trigger|start|make|allow|approve|abort|cancel|reset|revert|enable|disable)\b",
    re.I)


def topic_slugs():
    """The hyphenated slugs of the articles under `kb/*/gitlab/` of this checkout (an empty set where there is no
    `kb/` beside `_tools/`, so a `gitlab/` path then keeps the class)."""
    kb = Path(__file__).resolve().parent.parent / "kb"
    return {f.stem for f in kb.glob("*/gitlab/*.md") if "-" in f.stem}


def without_benign_push_words(text, question=None):
    """The text with the three wordings above replaced by a space: what the `push` words are searched in. `question` is
    the gate's question: a count question's push noun is blanked only in it, so an option that says `push` keeps the
    class, and only when the question also holds a display word (`list`, `count`, `show`) and no word that acts on the
    push or asks for it."""
    if (question and question in text and COUNT_QUESTION.search(question) and DISPLAY_WORD.search(question)
            and not PUSH_ACTION.search(question)):
        text = text.replace(question, PUSH_NOUN.sub(" ", question), 1)
    slugs = topic_slugs()
    return TOPIC_PATH.sub(lambda m: " " if m.group(1) in slugs else m.group(0), UPLOAD_DATE.sub(" ", text))


def command_words(gate):
    """The words of a gate's `do` and `host_check` commands (argv lists, or a string)."""
    out = []
    for key in ("do", "host_check"):
        v = gate.get(key)
        out += [str(x) for x in v] if isinstance(v, (list, tuple)) else [str(v)] if v else []
    return " ".join(out)


def in_agent_session(env=None):
    """Whether the process runs in a Claude Code session (its environment, `os.environ` by default, sets
    AGENT_SESSION_ENV): the operator's own terminal does not. The signal a session's own command line can clear, so
    it guards against a delegated session passing `--by operator`, not against one set on defeating it."""
    return bool((os.environ if env is None else env).get(AGENT_SESSION_ENV))


def names_ceiling(text):
    """Whether the text (a gate's question, a decision) names the test suite's ceiling: the gate words of
    QUESTION_WORDS, or the token `tests.py` reads a ceiling's numbers from (`tests-ceiling ids=`) anywhere in it, a
    prefix glued to it included, since `read_ceiling` accepts any decision text that holds the token as a substring."""
    text = text or ""
    return bool(QUESTION_WORDS["ceiling"].search(text) or CEILING_TOKEN.search(text))


def rank(cls):
    """The place of a class in CLASSES (0 the most restricted); an unknown class ranks as the most restricted."""
    return CLASSES.index(cls) if cls in CLASSES else 0


def class_reasons(item, gate):
    """The strictest class the item's touches and the gate's id and question name (`design` when none), with what set
    it: each touch (`touch '_tools/bl_items.py'`) and each word of the gate's text (`matched 'rule'`) that names that
    class, in that order; no reason for `design`. The word `rule` is a reason for `agents-rule` only beside a touch or a
    path in the text that names a rule-guarding file. `derived_class` reads its class here, so the two never diverge."""
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
    options = [str(o) for o in gate.get("options", []) or []]
    text = f"{gate.get('question', '')} {' '.join(options)} {command_words(gate)}"
    push_text = without_benign_push_words(text, str(gate.get("question", "")))
    # a unit-noun list is read within the question or one option, never across the join of two texts
    secrets_text = without_token_counts(" ".join(
        without_unit_lists(str(p)) for p in [gate.get("question", ""), *options, command_words(gate)]))
    for cls, rx in QUESTION_WORDS.items():
        m = rx.search(secrets_text if cls == "secrets" else push_text if cls == "push" else text)
        if m:
            found.setdefault(cls, []).append(f"matched '{m.group(0)}'")
    m = RULE_WORD.search(text)
    if m:  # the word `rule` classes only beside a rule-guarding path: a touch of the item or a path in the text
        paths = rule_paths(text)
        if paths or found.get("agents-rule"):
            found.setdefault("agents-rule", []).append(f"matched '{m.group(0)}'" + (
                f" with '{paths[0]}' in the text" if paths else ""))
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

