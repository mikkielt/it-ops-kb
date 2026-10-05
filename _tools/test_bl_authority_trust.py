"""The trust boundary of the gate classes (kb/_self/backlog.md, Dependencies, gates and triggers): what only the
operator answers only ever grows. Planted failures, one per rule, named `authority_trust_boundary`:

1. `OPERATOR_CLASSES` holds agents-rule, so an agent's answer to a gate of that class is refused;
2. `set --touch` re-derives every gate's class on the item and stores the stricter one, so widening the touches onto a
   guard file re-classes a gate already written (a stored class never goes down);
3. `_tools/backlog.py` and `_tools/kbpy`, the files that define what the agents may do, are agents-rule paths.

4. `check` reports an operator-class gate that an agent answered as a warning on a done or dropped item and as an
   error on an open one, while `answer` stays strict.

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

GUARD_FILES = ("_tools/backlog.py", "_tools/kbpy")


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch, tmp_path):
    monkeypatch.delenv("KB_TESTS_FAST", raising=False)
    monkeypatch.delenv("KB_TEST_WORKERS", raising=False)
    monkeypatch.setenv("KB_HOST_LOCK_DIR", str(tmp_path / "locks"))


def test_authority_trust_boundary_agents_rule_is_the_operators(throwaway_repo):
    assert "agents-rule" in bl_authority.OPERATOR_CLASSES
    for q in ("Which rule goes in AGENTS.md?", "Which skill text?"):
        gate = {"id": "g", "question": q, "options": ["a", "b"]}
        assert bl_authority.gate_class({"touches": []}, gate) == "agents-rule", q
    guard = {"id": "g", "question": "Which name?", "options": []}
    assert bl_authority.gate_class({"touches": ["_tools/bl_stall.py"]}, guard) == "agents-rule"
    r, bg = throwaway_repo["repo"], throwaway_repo["bg"]
    edit(r, bg, gates=[gate_of("Which rule goes in AGENTS.md?", kind="provisional")])
    before = text_of(r, bg)
    code, out = b(r, "answer", bg, "way", "--answer", "left", "--by", "agent")
    assert code == 1 and "class agents-rule" in out and "only the operator" in out and text_of(r, bg) == before, out
    code, out = b(r, "answer", bg, "way", "--answer", "left", "--by", "operator")
    assert code == 0 and item_json(r, bg)["gates"][0]["by"] == "operator", out


def test_authority_trust_boundary_agents_rule_is_the_operators_planted_failure(throwaway_repo, monkeypatch):
    """With agents-rule taken out of OPERATOR_CLASSES an agent's answer to the gate goes through: the test above
    refuses that."""
    monkeypatch.setattr(bl_authority, "OPERATOR_CLASSES", ("secrets", "push"))
    r, bg = throwaway_repo["repo"], throwaway_repo["bg"]
    edit(r, bg, gates=[gate_of("Which rule goes in AGENTS.md?", kind="provisional")])
    import bl_cli
    a = bl_cli.build_parser("x", str(r)).parse_args(["--root", str(r), "answer", bg, "way", "--answer", "left", "--by",
                                                     "agent"])
    import bl_items
    assert bl_items.cmd_answer(backlog.Backlog(str(r)), a) == 0  # in this process, where the patch holds
    assert item_json(r, bg)["gates"][0]["by"] == "agent"


@pytest.mark.parametrize("touch", ["_tools/kbdecide.py", "_tools/backlog.py", "AGENTS.md", ".claude/hooks/*"])
def test_authority_trust_boundary_set_touch_re_classes_a_written_gate(throwaway_repo, touch):
    r, bg = throwaway_repo["repo"], throwaway_repo["bg"]
    edit(r, bg, gates=[gate_of("Which way?", kind="provisional", **{"class": "design"})])
    code, out = b(r, "set", bg, "--touch", touch, "--add")
    assert code == 0, out
    g = item_json(r, bg)["gates"][0]
    assert g["class"] == "agents-rule" and g["kind"] == "blocking", g  # stored, and no longer provisional
    code, out = b(r, "answer", bg, "way", "--answer", "left", "--by", "agent")
    assert code == 1 and "class agents-rule" in out, out
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
    assert bl_authority.gate_class({"touches": [path]}, gate) in bl_authority.OPERATOR_CLASSES


@pytest.mark.parametrize("path", GUARD_FILES)
def test_authority_trust_boundary_the_agent_defining_files_planted_failure(monkeypatch, path):
    """With the path taken out of PATHS the gate falls to design, which an agent may answer."""
    monkeypatch.setattr(bl_authority, "PATHS", {k: tuple(p for p in v if p != path)
                                                for k, v in bl_authority.PATHS.items()})
    gate = {"id": "g", "question": "Which name?", "options": []}
    assert bl_authority.derived_class({"touches": [path]}, gate) == "design"


def refused_gate(by):
    return gate_of("Which rule goes in AGENTS.md?", kind="provisional", answer="left", by=by,
                   **{"class": "agents-rule"})


@pytest.mark.parametrize("by", ["agent"])
def test_authority_trust_boundary_check_warns_of_a_refused_class_answer_on_a_done_item(throwaway_repo, by):
    r, bg = throwaway_repo["repo"], throwaway_repo["bg"]
    edit(r, bg, gates=[refused_gate(by)], status="done", evidence={"commit": "abc", "checks": []})
    code, out = b(r, "check")
    assert code == 0 and "errors=0" in out, out
    assert f"gate way class agents-rule: answered by {by} in a refused class: the operator re-confirms" in out, out
    assert "it is blocking" not in out and "is not the operator's" not in out, out


@pytest.mark.parametrize("by", ["agent"])
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
    code, out = b(r, "answer", bg, "way", "--answer", "left", "--by", "agent")
    assert code != 0 and text_of(r, bg) == before, out
