"""Who may answer a gate (kb/_self/backlog.md, Dependencies, gates and triggers): the class of a gate and the classes
only the operator answers, and of those the one no agent session answers at all.

Every gate has a class, one of CLASSES, listed from the most restricted to the least. `gate_class(item, gate)` derives
it from the item's `touches` and the gate's question and id: the strictest class any of them names, `design` when none
does; `class_reasons` also names the touches and words that set it, which `gate add` prints. A class a gate stores (`gate add` writes it) is read as a floor for nothing but the record: the class in force is
the stricter of the stored and the derived, so an agent that writes a lower class into an item file changes nothing,
and `lowered` names it for `check`. A gate of a class in OPERATOR_CLASSES (ceiling, secrets, push and agents-rule) takes
only the operator's answer when it blocks and is confirmed by the operator when it is held: `disposition` says which,
`block` for a gate whose own words (BLOCK_CLASSES: those four and the query log and delete classes), options or item
title give the class or another reason, or whose touches give `ceiling` or `secrets`, `hold` for one only its item's
touches class `push` or `agents-rule`. The operator answers every class. The class in TERMINAL_CLASSES (ceiling,
the test suite's ceiling) is stricter still: `--by operator` from a Claude Code session (`in_agent_session`: the
environment names one, attended or not, headless or delegated) is no operator's answer, so it is recorded only from a
terminal of the operator's own, which an IDE's integrated terminal is not (IDE_ROUTE).

Standard library only; imports `bl_base` and never `backlog`, `bl_check` or `bl_plan`."""
import fnmatch
import os
import posixpath
import re
from pathlib import Path

from bl_base import START_GATE

CLASSES = ("ceiling", "secrets", "push", "start", "querylog", "agents-rule", "delete", "design")
OPERATOR_CLASSES = ("ceiling", "secrets", "push", "agents-rule")  # the classes only the operator answers
# the classes of a gate's own text that make it blocking: the operator classes, the query log and deleting
BLOCK_CLASSES = OPERATOR_CLASSES + ("querylog", "delete")
HOLD_CLASSES = ("push", "agents-rule")  # of those, the classes a touch alone holds; a touch of ceiling or secrets blocks
TERMINAL_CLASSES = ("ceiling",)  # of those, the classes no agent session answers, whatever `--by` says
AGENT_SESSION_ENV = "CLAUDECODE"  # set in the environment of every Claude Code session and of each command it runs
# CLAUDE_CODE_CHILD_SESSION is set only in subprocesses Claude Code starts, so `CLAUDECODE= ...` alone does not clear it
AGENT_SESSION_ENVS = (AGENT_SESSION_ENV, "CLAUDE_CODE_CHILD_SESSION")
# an IDE extension sets CLAUDECODE in its integrated terminals too (DOC S-exebozns): the refusal names that case
IDE_ROUTE = ("in an IDE's integrated terminal CLAUDECODE is set too, so that terminal is refused as a session is: open a "
             "standalone terminal outside the IDE, where neither CLAUDECODE nor CLAUDE_CODE_CHILD_SESSION is set, and run it there")

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
    """Whether the touch's path names a secret, credential, password, `.env`, private key or token file. The file name of
    a Markdown article under `kb/` (`kb/public/auth/shamir-secret-sharing.md`) is none: it is about the word, and its
    directories still count."""
    if not isinstance(touch, str):
        return False
    head, _, name = touch.strip().replace("\\", "/").rstrip("/").rpartition("/")
    doc = name.lower().endswith(".md")
    if doc and posixpath.normpath(head).lower().split("/")[0] == "kb":
        return bool(SECRET_WORDS.search(head) or TOKEN_WORD.search(head))
    if SECRET_WORDS.search(touch):
        return True
    return bool(TOKEN_WORD.search(head) or TOKEN_WORD.search(name) and not doc)


# In a gate's text `token` is a secret word, but not in the sense of a model's token counts (`output tokens`, `token
# counts`, `usage.output_tokens`, a hyphenated count used as a budget: `a 200-token floor`) nor in the sense of the words of a text (`token overlap`, `overlap of the
# tokens`, `words or tokens`, `word tokens`) nor in the file name of a Markdown doc (`kb/_self/token-efficiency.md`, as
# for a touch). The ops-row value shapes `phase token` and `closed token` are no secret either, nor an upper-case identifier of
# token counts that holds `TOKENS` in the plural (`DISPATCH_BASE_TOKENS`, `MAX_TOKENS`). A bare `token`, one qualified
# as a credential (`API token counts` is a count of API tokens), a singular identifier (`GITLAB_TOKEN`) and a token file
# keep the class: the classifier fails closed.
TOKENIZE_WORD = re.compile(r"(?<![\w.-])tokeni[sz](?:e|es|ed|er|ers|ing|ation)(?![\w-])", re.I)
# An attribute of the `tokenize` module (`tokenize.generate_tokens`, `tokenize.tokenize(f.readline)`,
# `tokenize.TokenInfo`): the name of the module's API, no credential. One with a credential, secret or service part among
# its `_` parts (`tokenize.api_token`) is kept, so only the module's own word is blanked in it.
TOKENIZE_ATTR = re.compile(r"(?<![\w.-])tokenize\.(\w+)", re.I)
TOKEN_DOC = re.compile(r"[\w./\\-]*token[\w./\\-]*\.md\b", re.I)
# A secrets word beside `token` in a doc name (`docs/bearer-token.md`, `ssh-token.md`, `passphrase-token-store.md`,
# `PAT-token.md`): the doc is about that credential, so its name keeps the class (`path` holds no `PAT`).
DOC_SECRET = re.compile(r"(?<![a-z])(?:bearer|ssh|passphrase|pat)(?![a-z])", re.I)
CRED_WORDS = "api|access|auth|bearer|refresh|session|personal|oauth|csrf|jwt|id"
TOKEN_COUNT = re.compile(
    rf"(?P<cred>\b(?:{CRED_WORDS})[-_ ])?"
    r"(?:\b(?:output|input|prompt|completion|cached?|total|max|context|reasoning)[-_ ]tokens?\b|"
    r"\b(?:phase|closed)[-_ ]tokens?\b|\b\d[\d,.]*-tokens?\b|"
    r"\btokens?[-_ ](?:counts?|usage|budgets?|limits?|costs?|efficiency|estimates?)\b|"
    r"\btokens?[-_ ]overlaps?\b|\boverlaps? of (?:\w+[ ]){0,3}tokens\b|\bwords?[ ]+(?:or|and)[ ]+tokens\b|"
    r"\btokens[ ]+(?:or|and)[ ]+words\b|\bword[-_ ]tokens?\b|"
    r"\b(?:counts?|number|numbers) of tokens\b|\btokens per (?:second|minute|request|run)\b|"
    r"\btokens (?:per|by) (?:(?:correct|right|wrong|failed) )?(?:answers?|questions?|tasks?|calls?|queries|turns?|models?)\b)",
    re.I)
# An upper-case constant name with `TOKENS` in the plural as one of its parts, at least one other part before it, not
# the stem of a file name (`LIMIT_TOKENS.json`); one with a credential word (`API_TOKENS`) or a secret word
# (`SECRET_TOKENS`, `PRIVATE_TOKENS`, `KEY_TOKENS`) among its parts is no count, so it stays in the text searched.
TOKEN_IDENT = re.compile(r"\b(?:[A-Z0-9]+_)+TOKENS(?:_[A-Z0-9]+)*\b(?!\.\w)")
# A lower-case snake_case code identifier that ends in `token` or `tokens` with at least one other part before it, not
# the stem of a file name. It is the name of a function or variable, no credential, only where every part before the
# ending is on the closed list CODE_PARTS (`bare_token`, `def_tokens`, `read_token`); any other part (`registration_token`,
# `vault_token`, `api_token`, `gitlab_token`) keeps the identifier in the text searched, so the rule fails closed, as does
# an identifier in upper case (`GITLAB_TOKEN`) or in mixed case, or after a credential word (`API bare_token`), or glued
# by a hyphen, dot, slash or colon to a word before it (`vault-read_token`, `vault.read_token`, `vault/read_token`): the
# prefix may be a credential's name, so only an identifier after a space, a backtick or the start stays blanked, and
# after `usage.` or `response.usage.`.
SNAKE_TOKEN_IDENT = re.compile(r"\b(?:[a-z0-9]+_)+tokens?\b(?!\.\w)")
GLUED_BEFORE = re.compile(r"\w[-./:]$")
# `usage.` or `response.usage.` right before the identifier is a model response's usage object, no credential's name:
# it does not count as glue, so `usage.cache_read_input_tokens` is judged by its parts alone.
USAGE_PREFIX = re.compile(r"(?:^|[\s`'\"(\[])(?:response\.)?usage\.$")
CODE_PARTS = frozenset(("bare", "def", "read"))
# A model's usage field or token-count function (`cache_read_input_tokens`, `cache_creation_input_tokens`,
# `output_tokens`, `count_tokens`, `max_tokens`): an identifier in the plural `tokens` whose every part before it is on
# the closed list USAGE_PARTS. It counts tokens, no credential; the singular and any other part keep the class.
USAGE_PARTS = frozenset((
    "cache", "cached", "read", "creation", "input", "output", "prompt", "completion", "reasoning", "total", "count",
    "num", "max"))
SERVICE_PART = re.compile(r"^(?:gitlab|github|glab|slack|npm|pypi|aws|azure|bot|service|deploy|runner|registry|user|admin)$")
# A credential word inside a matched phrase (`overlap of the API tokens`, `overlap of the deploy tokens`) keeps the
# class, as one right before it does.
CRED_INSIDE = re.compile(rf"\b(?:{CRED_WORDS}|deploy)\b", re.I)
CRED_PART = re.compile(rf"^(?:{CRED_WORDS}|(?:secret|password|passphrase|private|key|credential|pat|ssh)s?)$", re.I)
# `tokens` as one of the unit nouns of a list (`units, points, tokens, requests, calls`): a run of three or more list
# elements that holds `tokens` and at least two other unit nouns, with no credential qualifier of `tokens`. A bare
# `tokens` or `tokens, rows` and a credential sense keep the class: a credential word right before the list (`API
# tokens, units, points`, `API  tokens`, `API's tokens`), any other word right before a list that starts with `tokens`
# (`service tokens, units, points`, `Slack tokens, rows, lines`) unless it is a word that leads into a list (an article,
# a preposition, a verb such as `print`), and a credential noun in the question beside a list in an option (`for the
# API`, an option `tokens, units, points`).
UNIT_NOUN = r"(?:units|points|requests|calls|rows|bytes|lines|words)"
LIST_ELEMENT = rf"(?:{UNIT_NOUN}|tokens)"
LIST_SEP = r"(?:[ \t]*,[ \t]*(?:(?:and|or)[ \t]+)?|[ \t]+(?:and|or)[ \t]+)"
UNIT_LIST = re.compile(rf"(?<![\w-])\b{LIST_ELEMENT}(?:{LIST_SEP}{LIST_ELEMENT}){{2,}}\b", re.I)
CRED_BEFORE = re.compile(rf"\b(?:{CRED_WORDS})(?:['\u2019]s)?[-_ \t]+$", re.I)
WORD_BEFORE = re.compile(r"\b([a-z]+)(?:['\u2019]s)?[ \t]+$", re.I)
LIST_LEAD = frozenset((
    "a an the of in on at to by for from with per as and or nor but if that this these those which what how whether "
    "all any both each every no our its their his her is are be was were does do did can may should would will "
    "print prints show shows report reports log logs count counts name names list lists record records emit emits "
    "include includes sum sums use uses track tracks measure store return returns write add display give gives "
    "mean means only just also plus minus many total").split())
QUESTION_CRED = re.compile(r"\b(?:api|oauth|bearer|jwt|csrf|auth|ssh|pat|deploy)\b", re.I)


def unit_list_without_credential(text, m, question_cred=False):
    """Whether the UNIT_LIST match `m` in `text` lists `tokens` among two or more other unit nouns and carries no
    credential qualifier: no credential word right before the list (`API tokens, units, points`), no other
    qualifying word right before a list that starts with `tokens` (`service tokens, units, points`), and no credential
    noun in the question (`question_cred`)."""
    words = re.findall(r"[a-z]+", m.group(0).lower())
    others = [w for w in words if w not in ("tokens", "and", "or")]
    if "tokens" not in words or len(others) < 2 or question_cred:
        return False
    before = text[:m.start()]
    if CRED_BEFORE.search(before):
        return False
    lead = WORD_BEFORE.search(before)
    return not (words[0] == "tokens" and lead and lead.group(1).lower() not in LIST_LEAD)


def without_unit_lists(text, question_cred=False):
    """The text with each list that names `tokens` among unit nouns replaced by a space. `text` is one option or the
    question alone: `class_reasons` calls it for each of them, so a list never runs across the join of two.
    `question_cred`: the question names a credential owner, so no list is blanked."""
    return UNIT_LIST.sub(
        lambda m: " " if unit_list_without_credential(text, m, question_cred) else m.group(0), text)


def code_identifier(ident):
    """Whether the snake_case identifier `ident` (it ends in `token` or `tokens`) names code, no credential: every part
    before the ending is on CODE_PARTS, or the ending is the plural `tokens` and every part is on USAGE_PARTS."""
    *parts, last = ident.split("_")
    return all(p in CODE_PARTS for p in parts) or last == "tokens" and all(p in USAGE_PARTS for p in parts)


def glued_before(before):
    """Whether the text `before` an identifier ends in a word glued to it by a hyphen, dot, slash or colon (the word may
    be a credential's name), `usage.` and `response.usage.` apart."""
    return bool(GLUED_BEFORE.search(before)) and not USAGE_PREFIX.search(before)


def without_token_counts(text):
    """The text with each token-count phrase, each upper-case identifier of token counts, each snake_case code
    identifier such as `bare_token`, each Markdown doc name that holds `token` and each word of the Python `tokenize` module and each
    attribute of it (`tokenize.generate_tokens`) replaced by a space: what the `secrets` words are
    searched in, so a model's token counts, a constant such as `DISPATCH_BASE_TOKENS`, the ops-row `phase token`, a doc
    such as `token-efficiency.md` and `the tokenize module` are no secret. A doc name that holds a secrets word beside
    `token` (`bearer-token.md`, `ssh-token.md`) is kept."""
    text = TOKENIZE_ATTR.sub(
        lambda m: m.group(0) if any(CRED_PART.match(q) or SERVICE_PART.match(q.lower()) for q in m.group(1).split("_"))
        else " ", text)
    text = TOKENIZE_WORD.sub(" ", text)
    text = TOKEN_DOC.sub(
        lambda m: m.group(0) if names_secret(m.group(0)) or DOC_SECRET.search(m.group(0)) else " ", text)
    text = SNAKE_TOKEN_IDENT.sub(
        lambda m: m.group(0) if CRED_BEFORE.search(text[:m.start()]) or glued_before(text[:m.start()])
        or not code_identifier(m.group(0)) else " ", text)
    text = TOKEN_IDENT.sub(
        lambda m: m.group(0) if any(CRED_PART.match(p) for p in m.group(0).split("_")) else " ", text)
    return TOKEN_COUNT.sub(lambda m: m.group(0) if m.group("cred") or CRED_INSIDE.search(m.group(0)) else " ", text)


# A gate's text is its question, its options and the words of its `do` and `host_check` commands. The `push` words are
# the words for a write to a shared branch or a public copy (`push`, `publish`, `upload`, `deploy`, `mirror` with its
# endings, `public repository`), not the names of the places it goes to: `origin`, `remote`, `release`, a forge's name
# and `merge request` are nouns that a read-only question holds too (`git ls-remote`, `fails the eval on origin/main`,
# `the newest release`), so none of them classes a gate by itself. `AGENTS.md` and
# `CLAUDE.md` are `agents-rule` words only as a whole file name, alone or after a `/` (`skills/x/AGENTS.md`), so a kb
# article such as `gitops-for-agents.md` is none. The word `rule`
# is no `agents-rule` word of its own (a design question about which rows count by rule is no rule-guarding work): it
# classes only where the item's touches or the gate's text name a rule-guarding path or file (`rule_paths`).
QUESTION_WORDS = {
    "ceiling": re.compile(r"\btests?[-_ ]ceiling|\bsuite(?:['\u2019]s)?[-_ ]ceiling|\bceiling (?:of|for) the (?:test )?suite|"
                          r"\bseconds[-_ ]ceiling|\b(?:darwin|linux|win32)(?:['\u2019]s)?[-_ ]ceiling|"
                          r"\btests\.py[-_ ]ceiling|\bceiling[-_ ]profile|\bmax_seconds\b", re.I),
    "secrets": re.compile(r"secret|credential|password|passphrase|token|\bPATs?\b|\bbearer\b|\bssh\b|api[- ]key|"
                          r"private key|\.env\b|rotat\w*\s+(?:\w+\s+){0,2}keys?\b", re.I),
    "push": re.compile(r"\bpush(?:ing)?\b|publish|force[- ]push|\bmirror(?:s|ed|ing)?\b|public[- ]repositor(?:y|ies)|"
                       r"\buploa(?:d|ds|ded|ding)\b|\bdeploy(?:s|ed|ing|ment)?\b", re.I),
    "querylog": re.compile(r"query[- ]?log|querylog|redact", re.I),
    "agents-rule": re.compile(r"(?<![\w.-])(?:AGENTS|CLAUDE)\.md|\bskill\b|\bagent definition", re.I),
    "delete": re.compile(r"\bdelet|purge|erase|"
                         r"\bremov(?:e|es|ed|ing|al)\b(?:\s+(?!(?:flags?|options?|switch(?:es)?)\b)\S+){0,4}"
                         r"\s+(?:kb|content|history)\b|"
                         r"\bremov(?:e|es|ed|ing|al)\b(?:\s+\w+){0,4}?\s+(?:from|of|in|out of|within)"
                         r"\s+(?:(?:the|all|old|stale|any)\s+)*(?:kb|content|history)\b", re.I),
}
# The `ceiling` words are the wordings the rules use for the suite's ceiling (`seconds ceiling`, `darwin ceiling`, `the
# suite's ceiling`, `ceiling for the test suite`, `tests.py ceiling`, `ceiling profile`, `max_seconds`), so a gate that
# names the seconds of a platform or a clone's profile is `ceiling` on an item whose touches name no ceiling file.
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


# Three wordings that hold a `push` word and are no push (the third, `MIRROR_STORE`, is below): the upload date of a package release (`uploaded` beside a date
# or a time) and a display-only count question, where the push is a noun after a preposition (`before its push`) that
# only places a count or a list (`how many unpushed commits does land list before its push?`) and no word of the
# question acts on it or asks for it (`should`, `retry`, `run`, `force`). Every other use of those words keeps the class.
UPLOAD_DATE = re.compile(
    r"\buploaded\s+(?:(?:on|at|in)\s+)?(?=\d{4}-\d{2}-\d{2}\b|\d{1,2}:\d{2}\b|\d{1,2}\s+"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}\b)", re.I)
COUNT_QUESTION = re.compile(r"\bhow (?:many|much)\b|\b(?:which|what) (?:count|number)\b", re.I)
DISPLAY_WORD = re.compile(r"\b(?:list|lists|listed|listing|show|shows|print|prints|count|counts|name|names|report|reports)\b",
                          re.I)
PUSH_NOUN = re.compile(r"\b(?:before|after|prior to|ahead of|until|during) (?:its|the) push\b", re.I)
PUSH_ACTION = re.compile(
    r"\b(?:should|may|must|shall|can|could|would|will|need|needs|do|did|retry|retries|run|runs|rerun|force|forced|redo|"
    r"undo|skip|repeat|perform|execute|trigger|start|make|allow|approve|abort|cancel|reset|revert|enable|disable)\b",
    re.I)
# A mirror store is the directory an executor keeps its own copy of a queue in (`a local mirror store of its own`), a
# place on the executor's disk and no write to a shared branch or a public copy, so the two words together are no
# `push` word; `mirror` alone, and any other word after it, keep the class.
MIRROR_STORE = re.compile(r"\bmirror[- ]stores?\b", re.I)

# A forge's name in a `do` or `host_check` command acts on that forge (`curl -X POST https://gitlab.com/api/v4/.../tags`,
# `gh pr merge 12 --repo github`), so a command keeps the class by it; the name in a question or an option, or inside a
# host name such as `docs.gitlab.com`, is no push word.
FORGE_COMMAND = re.compile(r"\bgit(?:hub|lab)\b", re.I)
# `Publish` inside a longer identifier (`datePublished`, `date_published`) names a key, not an act: blanked only in the
# question and options of a gate about kb content.
KEY_IN_WORD = re.compile(r"\b\w*(?:[a-z]Publish|[A-Za-z0-9]_publish)\w*\b")


def kb_content_only(item):
    """Whether the item's touches all lie under `kb/` and none in the query log store (`kb/_querylog/`): a gate on such
    an item names a key such as `datePublished` as the subject of a fact. An item with no touches is no such item."""
    touches = [t for t in item.get("touches", []) or [] if isinstance(t, str) and t.strip()]
    return bool(touches) and all(
        norm(t).startswith("kb/") and not touch_names(t, "kb/_querylog/") for t in touches)


def without_benign_push_words(text, question=None, kb_content=False):
    """The text with the wordings above replaced by a space: what the `push` words are searched in. `question` is
    the gate's question: a count question's push noun is blanked only in it, so an option that says `push` keeps the
    class, and only when the question also holds a display word (`list`, `count`, `show`) and no word that acts on the
    push or asks for it. `kb_content` (the item's touches all under `kb/`, `kb_content_only`) also blanks each
    identifier that holds `Publish` inside a longer word."""
    if (question and question in text and COUNT_QUESTION.search(question) and DISPLAY_WORD.search(question)
            and not PUSH_ACTION.search(question)):
        text = text.replace(question, PUSH_NOUN.sub(" ", question), 1)
    text = MIRROR_STORE.sub(" ", UPLOAD_DATE.sub(" ", text))
    return KEY_IN_WORD.sub(" ", text) if kb_content else text


# A gate class name in backticks (`secrets`, `push`, `agents-rule`) in a question or an option names a class, as when a
# gate asks which class a phrase should get: its letters are no class word of the gate's own text. The same word
# unquoted, or inside any other backticked text (`git push`, `secrets.md`), keeps its class. A text with one such name
# and no word `class` asks for that act (`should the worker `push` the branch?`), so it keeps it: the names are blanked
# only in a text that holds two or more of them or the word `class`.
CLASS_NAME_QUOTED = re.compile(r"`(?:" + "|".join(re.escape(c) for c in CLASSES) + r")`")
CLASS_WORD = re.compile(r"\bclass(?:es)?\b", re.I)


def without_class_names(text):
    """The text with each backticked gate class name replaced by a space: what the class words are searched in. A text
    with one such name and no word `class` or `classes` is left as it is."""
    if len(CLASS_NAME_QUOTED.findall(text)) < 2 and not CLASS_WORD.search(text):
        return text
    return CLASS_NAME_QUOTED.sub(" ", text)


def command_words(gate):
    """The words of a gate's `do` and `host_check` commands (argv lists, or a string). A `do` dict maps each option's
    text to the argv or item id it runs: its values are read, never its keys, which are option text the question and
    option readers already see (and blank by their word-list and class-name rules)."""
    out = []
    for key in ("do", "host_check"):
        v = gate.get(key)
        if isinstance(v, dict):
            for x in v.values():
                out += [str(y) for y in x] if isinstance(x, (list, tuple)) else [str(x)] if x else []
        else:
            out += [str(x) for x in v] if isinstance(v, (list, tuple)) else [str(v)] if v else []
    return " ".join(out)


# Words that make a gate blocking whatever its class (STRICT_KINDS, the order `strict_signals` lists them in): a gate that
# names money, an act only the operator can do, a scope change of the item or running a program on input is one an agent
# does not answer, not even provisionally. The class is unchanged: `gate_class` and `derived_class` do not read them.
STRICT_WORDS = {
    "money": re.compile(r"\bUSD\b|\bUS dollars?\b|\bdollars?\b|\bpaid\b|\bspen(?:d|ds|ding|t)\b|\bbilling\b|"
                        r"\bActions minutes\b|\$\s?\d[\d.,]*", re.I),
    "operator-act": re.compile(r"\bsudo\b|\bonly the operator\b|\bthe operator (?:creates?|runs?|makes?|gives?|adds?|sets?)\b",
                               re.I),
    "scope": re.compile(r"\btouches\b|\bdrop the item\b|\bskip(?:s|ping)? (?:the )?experiment\b|\bworth building\b|"
                        r"\bdefer(?:s|red|ring)?\b", re.I),
    "execute": re.compile(r"\bexecut(?:e|es|ed|ing|ion)\b", re.I),
}
STRICT_KINDS = tuple(STRICT_WORDS)
# A gate that asks which words a pattern reads as a cue (`which words does PRICE_ASK read as a paying cue?`) quotes the
# words, and `paid` or `spend` inside that list names no spend: when the question asks for words (`which words`, `what
# words`, `word list`), each run of three or more bare words one comma apart (`pay, paid, spend, charge`, each word
# alone or in quotes or backticks) is no money text. A `$` figure, a list in a question that asks no such thing and the
# words outside a list keep the signal.
WORD_LIST_ASK = re.compile(r"\b(?:which|what)\s+words\b|\bword[- ]?lists?\b", re.I)
_LIST_WORD = r"""[`'"]?[A-Za-z][A-Za-z-]*[`'"]?"""
WORD_LIST = re.compile(rf"(?<![\w-]){_LIST_WORD}(?:[ \t]*,[ \t]*{_LIST_WORD}){{2,}}(?![\w-])")
PROGRAM_WORD = re.compile(r"\bprograms?\b", re.I)
RUN_WORD = re.compile(r"\b(?:run|runs|running|ran)\b", re.I)
# A clause ends at `;`, `:`, `?`, `!`, a line break, or a full stop that a space or the end follows: the dot inside a
# file name (`foo.py`) or a version (`1.2`) ends none.
CLAUSE_END = re.compile(r"[;:?!\n]|\.(?=\s|$)")


def strict_signals(gate):
    """[(kind, word)] for each of STRICT_KINDS that the gate's question, options, `do` and `host_check` words name, the
    first word of each kind in text order; [] for a design question with none. `execute` is `execute` with its endings,
    or `program` and `run` within one clause (a stretch with no `;`, `:`, `?`, `!`, line break or full stop followed by a
    space or the end in it: `foo.py` ends none). `money` is read without the word lists of a question that asks which
    words a pattern reads (`WORD_LIST`)."""
    options = [str(o) for o in gate.get("options", []) or []]
    texts = [str(gate.get("question", "")), *options, command_words(gate)]
    money_texts = texts
    if WORD_LIST_ASK.search(texts[0]):
        money_texts = [WORD_LIST.sub(" ", t) for t in texts[:-1]] + texts[-1:]
    out = []
    for kind, rx in STRICT_WORDS.items():
        word = next((m.group(0) for t in (money_texts if kind == "money" else texts) for m in [rx.search(t)] if m), None)
        if kind == "execute" and not word:
            for t in texts:
                for clause in CLAUSE_END.split(t):
                    p, r = PROGRAM_WORD.search(clause), RUN_WORD.search(clause)
                    if p and r:
                        word = f"{p.group(0)} ... {r.group(0)}"
                        break
                if word:
                    break
        if word:
            out.append((kind, word))
    return out


def strict_text(signals):
    """The signals as `gate add` prints them: `strict money 'USD', strict scope 'drop the item'`."""
    return ", ".join(f"strict {kind} '{word}'" for kind, word in signals)


def in_agent_session(env=None):
    """Whether the process runs in a Claude Code session (its environment, `os.environ` by default, sets one of
    AGENT_SESSION_ENVS): the operator's own terminal does not, and an IDE's integrated terminal does (IDE_ROUTE). The
    signal is an environment variable a session's own command line can still clear, so it guards against a delegated
    session passing `--by operator` or clearing one variable, not against one set on defeating it."""
    env = os.environ if env is None else env
    return any(env.get(k) for k in AGENT_SESSION_ENVS)


def names_ceiling(text):
    """Whether the text (a gate's question, a decision) names the test suite's ceiling: the gate words of
    QUESTION_WORDS, or the token `tests.py` reads a ceiling's numbers from (`tests-ceiling ids=`) anywhere in it, a
    prefix glued to it included, since `read_ceiling` accepts any decision text that holds the token as a substring."""
    text = text or ""
    return bool(QUESTION_WORDS["ceiling"].search(text) or CEILING_TOKEN.search(text))


def rank(cls):
    """The place of a class in CLASSES (0 the most restricted); an unknown class ranks as the most restricted."""
    return CLASSES.index(cls) if cls in CLASSES else 0


def touch_found(item):
    """{class: [reasons]} for each class the item's touches name (`touch '_tools/bl_items.py'`), none for a touch that
    names no class."""
    found = {}
    touches = [t for t in item.get("touches", []) or [] if isinstance(t, str)]
    for cls, paths in PATHS.items():
        for t in touches:
            if any(touch_names(t, p) for p in paths):
                found.setdefault(cls, []).append(f"touch '{t}'")
    for t in touches:
        if names_secret(t):
            found.setdefault("secrets", []).append(f"touch '{t}'")
    return found


def class_reasons(item, gate, touches=True):
    """The strictest class the item's touches and the gate's id and question name (`design` when none), with what set
    it (`touches` False: the gate's id and text alone, the item's touches left out, so the class its own words give): each touch (`touch '_tools/bl_items.py'`) and each word of the gate's text (`matched 'rule'`) that names that
    class, in that order; no reason for `design`. The word `rule` is a reason for `agents-rule` only beside a touch or a
    path in the text that names a rule-guarding file. `derived_class` reads its class here, so the two never diverge."""
    found = {}
    if gate.get("id") == START_GATE:
        found.setdefault("start", []).append(f"gate id '{START_GATE}'")
    if touches:
        for cls, why in touch_found(item).items():
            found.setdefault(cls, []).extend(why)
    question = without_class_names(str(gate.get("question", "")))
    options = [without_class_names(str(o)) for o in gate.get("options", []) or []]
    text = f"{question} {' '.join(options)} {command_words(gate)}"
    commands = command_words(gate)
    push_text = " ".join((
        without_benign_push_words(f"{question} {' '.join(options)}", question, kb_content_only(item)),
        without_benign_push_words(commands)))
    # a unit-noun list is read within the question or one option, never across the join of two texts
    question_cred = bool(QUESTION_CRED.search(question))
    secrets_text = without_token_counts(" ".join(
        without_unit_lists(str(p), question_cred) for p in [question, *options, command_words(gate)]))
    for cls, rx in QUESTION_WORDS.items():
        m = rx.search(secrets_text if cls == "secrets" else push_text if cls == "push" else text)
        if m:
            found.setdefault(cls, []).append(f"matched '{m.group(0)}'")
    m = FORGE_COMMAND.search(commands)
    if m:  # a `do` or `host_check` command that names a forge acts on it
        found.setdefault("push", []).append(f"matched '{m.group(0)}' in a command")
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


# The rule-text paths: the files that carry the rules agents run under (a subset of PATHS["agents-rule"]), so a gate option
# that names one is about a rule's wording and blocks, whatever the item's touches are.
RULE_TEXT_PATHS = ("AGENTS.md", "CLAUDE.md", ".claude/", ".claude-plugin/", "skills/", "agents/")
RULE_TEXT_FILES = ("agents.md", "claude.md")
# The classes of an item's title that make every gate of the item block: the title says what the item is about
TITLE_CLASSES = ("ceiling", "secrets", "push", "querylog")
PATH_EXT = re.compile(r"\.(?:py|md|csv|json|yml|yaml|toml|sh|txt)$", re.I)
TOP_DIRS = frozenset(("kb", "skills", "agents", "docs", "src", "tests", "code", "scripts"))


def option_paths(options):
    """The path-like words of the gate's options, each option read alone: a word with a `/` that ends in `/`, has a file
    extension in its last part or starts with a top-level directory, `_` or `.` (`and/or` is none), or a bare file
    name with a known extension (`AGENTS.md`, `bl_items.py`)."""
    out = []
    for opt in options:
        for word in re.findall(r"[\w.*\\/-]+", str(opt)):
            word = word.rstrip(".").replace("\\", "/")
            if not word:
                continue
            first = word.split("/")[0]
            path = ("/" in word and (word.endswith("/") or PATH_EXT.search(word) or first in TOP_DIRS
                                     or first.startswith(("_", ".")))) or ("/" not in word and PATH_EXT.search(word))
            if path:
                out.append(word)
    return list(dict.fromkeys(out))


def names_rule_text(word):
    """Whether the path-like word names a rule-text path (RULE_TEXT_PATHS), a directory above it or its file name."""
    low = word.lower()
    return posixpath.basename(low.rstrip("/")) in RULE_TEXT_FILES or (
        "/" in low and any(touch_names(low, p) for p in RULE_TEXT_PATHS))


def block_reasons(item, gate, kind=True):
    """Why the gate blocks, [] when none of the reasons holds: it is the sprint's start gate or is `blocking` (`kind`
    false leaves that one out: `gate add` stores `blocking` for a gate given no kind), its own words (the item's touches
    left out) give a class of BLOCK_CLASSES, they name a strict signal, an option names a path outside the item's touches
    or a rule-text path, or the item's title names TITLE_CLASSES."""
    why = []
    if gate.get("id") == START_GATE:
        why.append("the sprint's start gate")
    if kind and gate.get("kind") == "blocking":
        why.append("kind blocking")
    cls, reasons = class_reasons(item, gate, touches=False)
    if cls in BLOCK_CLASSES:
        why.append(f"class {cls} ({', '.join(reasons)})")
    signals = strict_signals(gate)
    if signals:
        why.append(strict_text(signals))
    touches = [t for t in item.get("touches", []) or [] if isinstance(t, str)]
    for word in option_paths(gate.get("options", []) or []):
        if names_rule_text(word):
            why.append(f"option names rule text '{word}'")
        elif "/" not in word and not rule_paths(word) and any(
                posixpath.basename(norm(t)) == word.lower() for t in touches if t.strip()):
            continue  # a bare doc file name that a touch of the item ends in; a rule-guarding file's bare name is no such
        elif not any(touch_names(t, word) for t in touches):
            why.append(f"option names '{word}', outside the touches")
    title = str(item.get("title") or "")
    tcls, treasons = class_reasons({"touches": []}, {"question": title}) if title else ("design", [])
    if tcls in TITLE_CLASSES:
        why.append(f"title names {tcls} ({', '.join(treasons)})")
    return why


def disposition(item, gate, kind=True):
    """(`block`, `hold` or `agent`, reasons): who settles the gate. `block`: the operator answers it and no agent does
    (block_reasons), and so does a gate the item's touches class `ceiling` or `secrets`, which always reaches the
    operator. `hold`: the gate is not blocking and only the item's touches give the class `agents-rule` or `push` (HOLD_CLASSES), so the agent goes on with its recommendation (`answer --provisional`)
    and the operator confirms it at the review; the reasons name those touches. `agent`: every other gate. The class
    stays what `gate_class` derives. `kind` false leaves the gate's own kind `blocking` out of the reasons."""
    why = block_reasons(item, gate, kind)
    if why:
        return "block", why
    found = touch_found(item)
    for cls in ("ceiling", "secrets"):  # a touch of the suite ceiling or of secrets blocks every gate of the item
        if cls in found:
            return "block", [f"class {cls} ({', '.join(found[cls])})"]
    ops = [c for c in found if c in HOLD_CLASSES]
    if ops:
        return "hold", list(dict.fromkeys(found[min(ops, key=rank)]))
    return "agent", []


# The implementation details a gate's question asks about: columns, caps, fields, units, a format, a layout, defaults, a
# name, one file or two, where something lives or appears
DETAIL_RE = re.compile(
    r"\b(?:columns?|caps?|fields?|units?|formats?|layouts?|defaults?|names?|one file or two|"
    r"where\b[^?]*\b(?:lives?|appears?|goes|sits?|is (?:kept|written|printed|shown)))\b", re.I)
DETAIL_LINE = ("detail only: settle it in the goal before the start or answer it provisionally, "
               "the gate is still added")


def detail_only(item, gate):
    """Whether the gate asks only an implementation detail (DETAIL_RE) and has no reason to block (`disposition` is not
    `block`) besides its kind `blocking`, which is the default `gate add` gives, so planning settles it in the item's
    goal."""
    return disposition(item, gate, kind=False)[0] != "block" and bool(DETAIL_RE.search(str(gate.get("question") or "")))


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

