"""A gate of class secrets or push is the operator's alone (kb/_self/backlog.md, Dependencies, gates and triggers):
`gate add` makes it blocking whatever --kind says, `answer` takes --provisional, --confirm and an agent's --answer for it
only with `--by operator`, `--confirm` with no --by is refused for every gate, and `check` reports a provisional or an
agent-answered gate of the class.

Planted failures: a provisional push gate answered with no --by, with --provisional --by agent, with --confirm and no
--by, with --confirm --by agent, and with --answer --by agent (each exit 2, the item unchanged, the class named); `gate
add --kind provisional` on a push question stored blocking; `check` on an item file that holds such a gate. The positives:
`--by operator` answers those gates, and a gate of another class takes --provisional and --confirm --by operator as
before."""
import pytest

import backlog
import bl_testkit
from bl_testkit import b, commit, edit, item_json

bl_testkit.bind(backlog)
repo, sprint = bl_testkit.repo, bl_testkit.sprint

PUSH_Q = "Push the commits to the public remote?"
SECRET_Q = "Rotate the api key?"
ADD = ("--option", "yes", "--option", "no", "--recommendation", "yes")


def gate_of(question, **kw):
    return {"id": "g1", "kind": "provisional", "question": question, "options": ["yes", "no"], "recommendation": "yes", **kw}


def planted(sprint, question):
    r, bg = sprint["repo"], sprint["bg"]
    edit(r, bg, gates=[gate_of(question)])
    commit(r, "planted gate")
    return r, bg


def unchanged(r, bg, before):
    assert item_json(r, bg)["gates"] == before


@pytest.mark.parametrize("question", [PUSH_Q, SECRET_Q])
@pytest.mark.parametrize("args", [
    ("--provisional",),
    ("--provisional", "--by", "agent"),
    ("--confirm",),
    ("--confirm", "--by", "agent"),
    ("--answer", "yes", "--by", "agent"),
])
def test_authority_refused_class_provisional_refuses_every_non_operator_answer(sprint, question, args):
    r, bg = planted(sprint, question)
    before = item_json(r, bg)["gates"]
    code, out = b(r, "answer", bg, "g1", *args)
    assert code == (1 if args[0] == "--answer" else 2), out
    assert ("class" in out and ("push" in out or "secrets" in out)) or "--by operator" in out, out
    unchanged(r, bg, before)
    # even an agent's answer already recorded cannot be confirmed without --by operator
    edit(r, bg, gates=[gate_of(question, answer="yes", by="agent")])
    commit(r, "agent answer")
    before = item_json(r, bg)["gates"]
    code, out = b(r, "answer", bg, "g1", "--confirm", *args[1:] if args[0] == "--confirm" else ())
    assert code == 2, out
    unchanged(r, bg, before)


@pytest.mark.parametrize("question", [PUSH_Q, SECRET_Q])
def test_authority_refused_class_provisional_operator_answers(sprint, question):
    r, bg = planted(sprint, question)
    assert b(r, "answer", bg, "g1", "--provisional", "--by", "operator")[0] == 0
    assert item_json(r, bg)["gates"][0]["by"] == "agent"
    assert b(r, "answer", bg, "g1", "--confirm", "--by", "operator")[0] == 0
    assert item_json(r, bg)["gates"][0]["by"] == "operator"


def test_authority_refused_class_provisional_touches_derive_push(sprint):
    r, bg = sprint["repo"], sprint["bg"]
    edit(r, bg, touches=["_tools/kbgit.py"], gates=[gate_of("Which name?")])
    commit(r, "kbgit touches")
    before = item_json(r, bg)["gates"]
    code, out = b(r, "answer", bg, "g1", "--provisional")
    assert code == 2 and "push" in out, out
    unchanged(r, bg, before)
    assert b(r, "answer", bg, "g1", "--provisional", "--by", "operator")[0] == 0


@pytest.mark.parametrize("by", [None, "operator", "agent"])
def test_authority_refused_class_provisional_confirm_needs_by_for_every_gate(sprint, by):
    r, bg = sprint["repo"], sprint["bg"]
    edit(r, bg, gates=[gate_of("Which name?")])
    commit(r, "plain gate")
    assert b(r, "answer", bg, "g1", "--provisional")[0] == 0  # no --by stays allowed outside secrets and push
    assert item_json(r, bg)["gates"][0]["by"] == "agent"
    code, out = b(r, "answer", bg, "g1", "--confirm", *(["--by", by] if by else []))
    if by is None:
        assert code == 2 and "--by operator" in out, out
        assert item_json(r, bg)["gates"][0]["by"] == "agent"
    else:
        assert code == 0, out
        assert item_json(r, bg)["gates"][0]["by"] == ("operator" if by in ("operator", "agent") else by)


@pytest.mark.parametrize("question, cls", [(PUSH_Q, "push"), (SECRET_Q, "secrets")])
def test_authority_refused_class_provisional_gate_add_makes_it_blocking(sprint, question, cls):
    r, bg = sprint["repo"], sprint["bg"]
    code, out = b(r, "gate", "add", bg, "--kind", "provisional", "--id", "g1", "--question", question, *ADD)
    assert code == 0 and "made blocking" in out and cls in out, out
    g = item_json(r, bg)["gates"][0]
    assert g["kind"] == "blocking" and g["class"] == cls
    code, out = b(r, "answer", bg, "g1", "--provisional")
    assert code == 2, out
    # the same command again changes nothing
    code, out = b(r, "gate", "add", bg, "--kind", "provisional", "--id", "g1", "--question", question, *ADD)
    assert code == 0 and "unchanged" in out, out


def test_authority_refused_class_provisional_gate_add_other_class_stays_provisional(sprint):
    r, bg = sprint["repo"], sprint["bg"]
    code, out = b(r, "gate", "add", bg, "--kind", "provisional", "--id", "g1", "--question", "Which name?", *ADD)
    assert code == 0 and "made blocking" not in out, out
    assert item_json(r, bg)["gates"][0]["kind"] == "provisional"


@pytest.mark.parametrize("question", [PUSH_Q, SECRET_Q])
def test_authority_refused_class_provisional_check_reports_bad_gates(sprint, question):
    r, bg = planted(sprint, question)
    code, out = b(r, "check")
    assert code != 0 and bg in out and "g1" in out and "provisional" in out, out
    edit(r, bg, gates=[gate_of(question, kind="blocking", answer="yes", by="agent")])
    commit(r, "answered by agent")
    code, out = b(r, "check")
    assert code != 0 and "g1" in out and "agent" in out, out
    edit(r, bg, gates=[gate_of(question, kind="blocking", answer="yes", by="operator")])
    commit(r, "operator answer")
    assert b(r, "check")[0] == 0


@pytest.mark.parametrize("question", [PUSH_Q, SECRET_Q])
def test_authority_refused_class_provisional_check_accepts_one_the_operator_answered(sprint, question):
    """a provisional gate of the class that the operator answered or confirmed stands: nothing to convert"""
    r, bg = planted(sprint, question)
    edit(r, bg, gates=[gate_of(question, kind="provisional", answer="yes", by="operator")])
    commit(r, "operator confirmed")
    assert b(r, "check")[0] == 0, b(r, "check")[1]
