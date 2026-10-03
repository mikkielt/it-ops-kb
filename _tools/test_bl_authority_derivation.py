"""Gate class derivation (bl_authority.derived_class, kb/_self/backlog.md, Dependencies, gates and triggers): a safety
classifier, so every test here plants the input a looser reading would let through and asserts the stricter class.

Touch spellings (a leading `./`, case, a trailing slash), a directory touch, `_tools/kbpublic.py`, `.claude/hooks/`, the
words origin, mirror, release, rotate keys, public repository and `.env`, a gate's `do` and `host_check` commands, an
empty question, and a sprint's start gate over its items' touches; the neutral wording stays `design`."""
import pytest

import backlog
import bl_authority
import bl_testkit
from bl_testkit import b, item

bl_testkit.bind(backlog)
repo = bl_testkit.repo

NEUTRAL = {"id": "way", "kind": "blocking", "question": "Which name for the flag?", "options": ["left", "right"]}


def cls(touches=(), gate=None, **item):
    return bl_authority.derived_class({"touches": list(touches), **item}, gate or NEUTRAL)


def gate(question="Which name?", **kw):
    return {"id": "way", "kind": "blocking", "question": question, "options": ["a", "b"], **kw}


@pytest.mark.parametrize("touch", [
    "_tools/kbgit.py", "./_tools/kbgit.py", "././_tools/kbgit.py", "_tools/KBGIT.py", "_Tools/KbGit.PY",
    "_tools/kbgit.py/", "./_tools/kbgit.py/", "_tools//kbgit.py", " _tools/kbgit.py ", "_tools/../_tools/kbgit.py",
    "_tools\\kbgit.py", "_tools/kbpublic.py", "./_tools/KBPUBLIC.py", "_tools/kg_lane.py", "./_tools/KG_x.py",
    ".GITLAB-CI.YML", "./.gitlab-ci.yml", ".github/workflows/x.yml", "./.GitHub/", ".githooks",
])
def test_gate_class_derivation_hardened_touch_spellings_are_push(touch):
    assert cls([touch]) == "push"


@pytest.mark.parametrize("touch", ["_tools/", "_tools", "./_tools/", "_TOOLS/", ".", "./", ".//", "_tools/*", "**"])
def test_gate_class_derivation_hardened_a_directory_touch_covers_every_path_under_it(touch):
    assert cls([touch]) == "push"


@pytest.mark.parametrize("touch,want", [
    (".claude/", "agents-rule"), (".claude", "agents-rule"), ("./.CLAUDE/", "agents-rule"),
    (".claude/hooks/x.py", "agents-rule"), ("./.claude/hooks/", "agents-rule"), (".claude/HOOKS/", "agents-rule"),
    (".claude/hooks", "agents-rule"), ("./agents.md", "agents-rule"), ("CLAUDE.MD/", "agents-rule"),
    ("./.claude/settings.json", "agents-rule"), (".claude-plugin", "agents-rule"), ("KB/_querylog", "querylog"),
    ("./kb/_querylog/", "querylog"), ("kb/", "querylog"),
])
def test_gate_class_derivation_hardened_other_paths_and_directories(touch, want):
    assert cls([touch]) == want


@pytest.mark.parametrize("touches", [
    ["src/**"], ["docs/readme.md"], ["_tools/bl_plan*.py"], ["_tools/test_x.py"], ["kb/_self/backlog.md"], ["./_tools/bl_plan.py"],
    ["_tools/kbgitx.py"], ["_toolsx/"], ["kb/public/x.md"], [".claude/other/"], ["src/"], ["_tools/kbgit"],
])
def test_gate_class_derivation_hardened_a_neutral_touch_stays_unclassed(touches):
    assert cls(touches) == "design"


def test_gate_class_derivation_hardened_a_touch_that_is_not_a_string_names_nothing():
    for bad in (None, 7, "", "  ", ["_tools/kbgit.py"]):
        assert cls([bad]) == "design"


@pytest.mark.parametrize("text,want", [
    ("Push to which remote?", "push"), ("Which origin do we use?", "push"), ("Fetch from origin/main?", "push"),
    ("ORIGIN?", "push"), ("Mirror the tree?", "push"), ("Should it be mirrored?", "push"), ("mirroring", "push"),
    ("Cut a release?", "push"), ("Which releases go out?", "push"), ("It was released.", "push"), ("releasing now", "push"),
    ("Move to the public repository?", "push"), ("Public-repository naming?", "push"), ("public repositories", "push"),
    ("Rotate keys now?", "secrets"), ("Rotate the keys?", "secrets"), ("rotating all keys", "secrets"),
    ("Rotate the signing key?", "secrets"), ("Where does .env live?", "secrets"), ("Copy .ENV over?", "secrets"),
    ("Which AGENTS.md rule?", "agents-rule"),
])
def test_gate_class_derivation_hardened_the_words_in_a_question(text, want):
    assert cls(gate=gate(text)) == want


@pytest.mark.parametrize("text", [
    "Which name for the flag?", "Is the original wording kept?", "Originate the list from source?", "Mirrorless cameras?",
    "Do we keep the relevant part?", "Which environment name?", "Envelope size?", "Pick a rotation order?",
    "Which keyboard layout?", "Is the public API stable?",
])
def test_gate_class_derivation_hardened_neutral_words_stay_unclassed(text):
    assert cls(gate=gate(text)) == "design"


def test_gate_class_derivation_hardened_the_words_in_the_options():
    assert cls(gate=gate("Which?", options=["keep", "mirror it"])) == "push"
    assert cls(gate=gate("Which?", options=["keep", "rotate keys"])) == "secrets"
    assert cls(gate=gate("Which?", options=["release", "wait"])) == "push"


@pytest.mark.parametrize("key", ["do", "host_check"])
@pytest.mark.parametrize("argv,want", [
    (["git", "push", "origin", "main"], "push"), (["sh", "-c", "mirror the tree"], "push"),
    (["cat", ".env"], "secrets"), (["echo", "rotate keys"], "secrets"), (["python3", "kbpublic.py", "release"], "push"),
    (["ls", "src"], "design"), (["echo", "original"], "design"),
])
def test_gate_class_derivation_hardened_a_gates_commands_are_read_as_text(key, argv, want):
    assert cls(gate=gate("Which name?", **{key: argv})) == want
    assert cls(gate=gate("Which name?", **{key: " ".join(argv)})) == want  # a string reads as the argv does


def test_gate_class_derivation_hardened_the_strictest_class_still_wins():
    assert cls(["_tools/kbgit.py"], gate("Which password?")) == "secrets"
    assert cls(["AGENTS.md", "./_tools/KBGIT.py"], gate("Which name?")) == "push"
    assert cls(["AGENTS.md"], gate("Which name?")) == "agents-rule"
    assert bl_authority.gate_class({"touches": ["./_tools/"]}, gate(**{"class": "design"})) == "push"
    assert bl_authority.lowered({"touches": ["./_tools/"]}, gate(**{"class": "design"})) == "design"


def test_gate_class_derivation_hardened_an_operator_answered_gate_is_not_reported_lowered():
    it = {"touches": ["./_tools/"]}
    low = {"class": "design"}
    assert bl_authority.lowered(it, gate(**low)) == "design"  # open: reported
    assert bl_authority.lowered(it, gate(**low, answer="yes", by="agent")) == "design"  # planted: an agent's answer stays reported
    assert bl_authority.lowered(it, gate(**low, answer="yes", by="autopilot")) == "design"
    assert bl_authority.lowered(it, gate(**low, by="operator")) == "design"  # no answer yet
    assert bl_authority.lowered(it, gate(**low, answer="yes", by="operator")) is None  # the operator answered it
    # and nothing is loosened: the class in force stays the stricter one, so the autopilot still may not answer it
    assert bl_authority.gate_class(it, gate(**low, answer="yes", by="operator")) == "push"
    assert bl_authority.autopilot_may_answer(it, gate(**low, answer="yes", by="operator"))[0] is False


@pytest.mark.parametrize("gate_text", [
    {}, {"question": ""}, {"question": "   "}, {"question": "\n\t"}, {"question": None}, {"question": 5}, {"question": []},
    {"question": "", "options": ["a"]},
])
def test_gate_class_derivation_hardened_an_empty_or_missing_question_fails_closed(gate_text):
    for it in ({"touches": []}, {}, {"touches": ["src/**"]}):
        ok, why = bl_authority.autopilot_may_answer(it, {"id": "g", "options": [], **gate_text})
        assert ok is False and "no question" in why


def test_gate_class_derivation_hardened_a_question_is_still_answered_when_neutral():
    assert bl_authority.autopilot_may_answer({"touches": []}, gate("Which name?")) == (True, "design")
    assert bl_authority.autopilot_may_answer({"touches": ["_tools/"]}, gate("Which name?")) == (False, "push")


MEMBER_TOUCHES = [
    (["_tools/kbgit.py"], "push"), (["_tools/kg_lane.py"], "push"), ([".gitlab-ci.yml"], "push"),
    ([".claude/settings.json"], "agents-rule"), (["AGENTS.md"], "agents-rule"), (["./_tools/KBGIT.py"], "push"),
    (["_tools/"], "push"), (["_tools/kbpublic.py"], "push"), ([".claude/hooks/x.py"], "agents-rule"),
    (["src/**", "./.GITHUB/"], "push"),
]


@pytest.mark.parametrize("touches,want", MEMBER_TOUCHES)
def test_gate_class_derivation_hardened_a_start_gate_is_the_strictest_over_its_items(touches, want):
    sp = {"id": "SP-aaaaaaaa", "kind": "sprint", "touches": []}
    start = {"id": "start", "kind": "blocking", "question": "Approve this sprint's goal and committed items?",
             "options": ["approve"]}
    members = [{"id": "TK-1", "touches": ["docs/**"]}, {"id": "TK-2", "touches": touches}]
    assert bl_authority.derived_class(sp, start) == "start"  # the bare sprint sees nothing: the planted failure
    scoped = bl_authority.sprint_scope(sp, start, members)
    assert bl_authority.derived_class(scoped, start) == ("push" if want == "push" else "start")  # start outranks a rule
    assert bl_authority.autopilot_may_answer(scoped, start) == (False, want)
    assert sp["touches"] == []  # the sprint item itself is not changed


def test_gate_class_derivation_hardened_a_start_gate_of_docs_and_tool_items_may_be_answered():
    sp = {"id": "SP-aaaaaaaa", "kind": "sprint", "touches": []}
    start = {"id": "start", "kind": "blocking", "question": "Approve?", "options": ["approve"]}
    members = [{"touches": ["kb/_self/x.md"]}, {"touches": ["src/**", "_tools/bl_plan*.py"]}]

    def may(ms):
        return bl_authority.autopilot_may_answer(bl_authority.sprint_scope(sp, start, ms), start)

    assert may(members) == (True, "start")
    assert may(members + [{"touches": ["_tools/kbgit.py"], "status": "dropped"}]) == (True, "start")  # not committed
    assert may(members + [{"touches": ["_tools/kbgit.py"], "status": "open"}]) == (False, "push")
    assert may(members + [{"touches": [".claude/skills/x/"]}]) == (False, "agents-rule")  # a skill is a rule
    assert may(members + [{"touches": ["src/.env"]}]) == (False, "secrets")


def test_gate_class_derivation_hardened_scope_changes_only_a_sprint_start_gate():
    story = {"id": "ST-1", "kind": "story", "touches": []}
    other = {"id": "way", "question": "Which name?", "options": []}
    members = [{"touches": ["_tools/kbgit.py"]}]
    assert bl_authority.sprint_scope(story, {"id": "start"}, members) is story
    assert bl_authority.sprint_scope({"kind": "sprint"}, other, members) == {"kind": "sprint"}


def test_gate_class_derivation_hardened_the_autopilot_cannot_start_a_sprint_of_risky_items(repo):
    b(repo, "new", "sprint", "--title", "Risky", "--goal", "ship")
    sp = item(repo, "Risky")["id"]
    code, out = b(repo, "new", "bug", "--title", "Risky bug", "--sprint", sp, "--severity", "S3", "--repro", "false",
                  "--goal", "g", "--touch", "./_tools/KBGIT.py")
    assert code == 0, out
    code, out = b(repo, "answer", sp, "start", "--answer", "approve", "--by", "autopilot")
    assert code == 2 and "class push" in out, out
    assert b(repo, "answer", sp, "start", "--answer", "approve", "--by", "operator")[0] == 0
