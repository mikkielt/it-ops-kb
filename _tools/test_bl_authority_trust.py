"""The autopilot's trust boundary (kb/_self/backlog.md, Dependencies, gates and triggers): the autopilot's authority
only ever shrinks. Five planted failures, one per change, named `authority_trust_boundary`:

1. `AUTOPILOT_REFUSED` holds agents-rule, so the autopilot is refused any gate of that class (the start gate was the
   only one it was refused);
2. `answer --by autopilot` exits 2 and writes nothing while KB_HEADLESS_RUNNER is set (a headless runner answers
   `--by agent` only, a provisional answer), and behaves as before with the variable unset;
3. `set --touch` re-derives every gate's class on the item and stores the stricter one, so widening the touches onto a
   guard file re-classes a gate already written (a stored class never goes down);
4. `_tools/backlog.py` and `_tools/kbpy`, the files that define what the agents may do, are agents-rule paths.

5. `check` reports a refused-class gate that an agent or the autopilot answered as a warning on a done or dropped
   item and as an error on an open one, while `answer` stays strict.

The decision files are those of a throwaway repository, never this one's."""
import pytest

import backlog
import bl_authority
import bl_testkit
from bl_testkit import b, edit, item_json
import test_backlog_authority as authority
from test_backlog_authority import gate_of, text_of

bl_testkit.bind(backlog)
sprint = bl_testkit.sprint  # the fixtures `decide` builds on
repo = bl_testkit.repo
throwaway_repo = authority.decide

ENV = bl_authority.HEADLESS_ENV
GUARD_FILES = ("_tools/backlog.py", "_tools/kbpy")


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch, tmp_path):
    monkeypatch.delenv("KB_TESTS_FAST", raising=False)
    monkeypatch.delenv("KB_TEST_WORKERS", raising=False)
    monkeypatch.setenv("KB_HOST_LOCK_DIR", str(tmp_path / "locks"))
    monkeypatch.delenv(ENV, raising=False)  # each test sets the runner's variable itself


def test_authority_trust_boundary_agents_rule_is_refused_to_the_autopilot():
    assert "agents-rule" in bl_authority.AUTOPILOT_REFUSED
    for q in ("Which rule goes in AGENTS.md?", "Which skill text?"):
        gate = {"id": "g", "question": q, "options": ["a", "b"]}
        assert bl_authority.autopilot_may_answer({"touches": []}, gate) == (False, "agents-rule"), q
    guard = {"id": "g", "question": "Which name?", "options": []}
    assert bl_authority.autopilot_may_answer({"touches": ["_tools/bl_bounds.py"]}, guard) == (False, "agents-rule")
    start = {"id": "start", "question": "Approve?", "options": ["approve", "no"]}
    assert bl_authority.autopilot_may_answer({"touches": []}, start)[0] is True  # a sprint over design work stays open
    assert bl_authority.autopilot_may_answer({"touches": ["AGENTS.md"]}, start) == (False, "agents-rule")
    assert bl_authority.autopilot_may_answer({"touches": []}, {"id": "g", "question": "Which name?"})[0] is True


def test_authority_trust_boundary_agents_rule_is_refused_to_the_autopilot_planted_failure(monkeypatch):
    """With agents-rule taken out of AUTOPILOT_REFUSED the autopilot may answer the gate: the test above refuses that."""
    monkeypatch.setattr(bl_authority, "AUTOPILOT_REFUSED", ("secrets", "push"))
    gate = {"id": "g", "question": "Which rule goes in AGENTS.md?", "options": []}
    assert bl_authority.autopilot_may_answer({"touches": []}, gate) == (True, "agents-rule")


def test_authority_trust_boundary_answer_refuses_the_autopilot_for_an_agents_rule_gate(throwaway_repo):
    r, bg = throwaway_repo["repo"], throwaway_repo["bg"]
    edit(r, bg, gates=[gate_of("Which rule goes in AGENTS.md?")])
    before = text_of(r, bg)
    for extra in ((), ("--record",)):
        code, out = b(r, "answer", bg, "way", "--answer", "left", "--by", "autopilot", *extra)
        assert code == 2 and "class agents-rule" in out and "only the operator" in out, out
        assert text_of(r, bg) == before
    code, out = b(r, "answer", bg, "way", "--answer", "left", "--by", "agent")
    assert code == 1 and text_of(r, bg) == before, out  # an agent's answer is not accepted either
    code, out = b(r, "answer", bg, "way", "--answer", "left", "--by", "operator")
    assert code == 0 and item_json(r, bg)["gates"][0]["by"] == "operator", out


def test_authority_trust_boundary_a_headless_runner_cannot_answer_by_autopilot(throwaway_repo, monkeypatch):
    r, bg = throwaway_repo["repo"], throwaway_repo["bg"]
    before = text_of(r, bg)
    monkeypatch.setenv(ENV, "1")
    for args in (("--answer", "left", "--by", "autopilot"), ("--by", "autopilot", "--answer", "left"),
                 ("--answer", "left", "--b", "autopilot"), ("--answer", "left", "--by=autopilot"),
                 ("--provisional", "--by", "autopilot"), ("--confirm", "--by", "autopilot"),
                 ("--answer", "left", "--by", "autopilot", "--record")):
        code, out = b(r, "answer", bg, "way", *args)
        assert code == 2 and ENV in out and "--by agent only" in out, (args, out)
        assert text_of(r, bg) == before, args
        assert authority.decisions(r) == [], args


def test_authority_trust_boundary_a_headless_runner_answers_by_agent(throwaway_repo, monkeypatch):
    r, bg = throwaway_repo["repo"], throwaway_repo["bg"]
    edit(r, bg, gates=[gate_of("Which way?", kind="provisional")])
    monkeypatch.setenv(ENV, "1")
    code, out = b(r, "answer", bg, "way", "--provisional")
    assert code == 0 and "(by agent)" in out, out
    assert item_json(r, bg)["gates"][0]["by"] == "agent"


def test_authority_trust_boundary_without_the_variable_the_autopilot_answers_as_before(throwaway_repo, monkeypatch):
    """Planted failure for the guard's condition: with the variable unset or empty the same command works."""
    r, bg = throwaway_repo["repo"], throwaway_repo["bg"]
    monkeypatch.setenv(ENV, "")
    code, out = b(r, "answer", bg, "way", "--answer", "left", "--by", "autopilot")
    assert code == 0 and "(by autopilot)" in out, out
    assert item_json(r, bg)["gates"][0]["by"] == "autopilot"


@pytest.mark.parametrize("touch", ["_tools/kbdecide.py", "_tools/backlog.py", "AGENTS.md", ".claude/hooks/*"])
def test_authority_trust_boundary_set_touch_re_classes_a_written_gate(throwaway_repo, touch):
    r, bg = throwaway_repo["repo"], throwaway_repo["bg"]
    edit(r, bg, gates=[gate_of("Which way?", kind="provisional", **{"class": "design"})])
    code, out = b(r, "set", bg, "--touch", touch, "--add")
    assert code == 0, out
    g = item_json(r, bg)["gates"][0]
    assert g["class"] == "agents-rule" and g["kind"] == "blocking", g  # stored, and no longer provisional
    code, out = b(r, "answer", bg, "way", "--answer", "left", "--by", "autopilot")
    assert code == 2 and "class agents-rule" in out, out
    assert b(r, "check")[0] == 0


def test_authority_trust_boundary_set_touch_never_lowers_a_stored_class(throwaway_repo):
    r, bg = throwaway_repo["repo"], throwaway_repo["bg"]
    edit(r, bg, gates=[gate_of("Which way?", **{"class": "push"})])
    code, out = b(r, "set", bg, "--touch", "src/**", "--add")
    assert code == 0, out
    assert item_json(r, bg)["gates"][0]["class"] == "push"


def test_authority_trust_boundary_set_touch_re_classes_every_gate(throwaway_repo):
    r, bg = throwaway_repo["repo"], throwaway_repo["bg"]
    edit(r, bg, gates=[gate_of("Which way?", **{"class": "design"}),
                       {**gate_of("Which side?"), "id": "side", "class": "delete"}])
    code, out = b(r, "set", bg, "--touch", "_tools/kbpy", "--add")
    assert code == 0, out
    assert [g["class"] for g in item_json(r, bg)["gates"]] == ["agents-rule", "agents-rule"]


def test_authority_trust_boundary_set_touch_re_classes_planted_failure(throwaway_repo):
    """The state `set --touch` leaves out when it does not re-class: touches on a guard file and a gate that stores
    design. `check` names it, so the re-classing above is what keeps a widened item from reaching it."""
    r, bg = throwaway_repo["repo"], throwaway_repo["bg"]
    edit(r, bg, gates=[gate_of("Which way?", **{"class": "design"})], touches=["_tools/kbdecide.py"])
    code, out = b(r, "check")
    assert code == 1 and "class design is lower than agents-rule" in out, out


@pytest.mark.parametrize("path", GUARD_FILES)
def test_authority_trust_boundary_the_agent_defining_files_are_agents_rule(path):
    gate = {"id": "g", "question": "Which name?", "options": []}
    assert bl_authority.derived_class({"touches": [path]}, gate) == "agents-rule"
    assert bl_authority.derived_class({"touches": ["_tools/"]}, gate) in ("push", "agents-rule")
    assert bl_authority.autopilot_may_answer({"touches": [path]}, gate) == (False, "agents-rule")


@pytest.mark.parametrize("path", GUARD_FILES)
def test_authority_trust_boundary_the_agent_defining_files_planted_failure(monkeypatch, path):
    """With the path taken out of PATHS the gate falls to design, which the autopilot may answer."""
    monkeypatch.setattr(bl_authority, "PATHS", {k: tuple(p for p in v if p != path)
                                                for k, v in bl_authority.PATHS.items()})
    gate = {"id": "g", "question": "Which name?", "options": []}
    assert bl_authority.derived_class({"touches": [path]}, gate) == "design"


def refused_gate(by):
    return gate_of("Which rule goes in AGENTS.md?", kind="provisional", answer="left", by=by,
                   **{"class": "agents-rule"})


@pytest.mark.parametrize("by", ["agent", "autopilot"])
def test_authority_trust_boundary_check_warns_of_a_refused_class_answer_on_a_done_item(throwaway_repo, by):
    r, bg = throwaway_repo["repo"], throwaway_repo["bg"]
    edit(r, bg, gates=[refused_gate(by)], status="done", evidence={"commit": "abc", "checks": []})
    code, out = b(r, "check")
    assert code == 0 and "errors=0" in out, out
    assert f"gate way class agents-rule: answered by {by} in a refused class: the operator re-confirms" in out, out
    assert "it is blocking" not in out and "is not the operator's" not in out, out


@pytest.mark.parametrize("by", ["agent", "autopilot"])
def test_authority_trust_boundary_check_errors_on_a_refused_class_answer_on_an_open_item(throwaway_repo, by):
    """Planted failure for the status split: the same gate on an open item is an error and no warning."""
    r, bg = throwaway_repo["repo"], throwaway_repo["bg"]
    for status in ("todo", "doing"):
        edit(r, bg, gates=[refused_gate(by)], status=status)
        code, out = b(r, "check")
        assert code == 1 and "only the operator answers it" in out, out
        assert "the operator re-confirms" not in out, out


def test_authority_trust_boundary_answer_stays_strict_for_a_refused_class_gate(throwaway_repo):
    """`check` is gentle with a closed item's old answer; a new answer in a refused class is still refused."""
    r, bg = throwaway_repo["repo"], throwaway_repo["bg"]
    edit(r, bg, gates=[gate_of("Which rule goes in AGENTS.md?", kind="provisional")])
    before = text_of(r, bg)
    for by in ("autopilot", "agent"):
        code, out = b(r, "answer", bg, "way", "--answer", "left", "--by", by)
        assert code != 0 and text_of(r, bg) == before, out
