"""A headless runner never answers as the operator (kb/_self/backlog.md, Dependencies, gates and triggers): with
KB_HEADLESS_RUNNER set, `backlog.py answer` and `kbdecide.py` refuse each act recorded as the operator's, whatever the
argument order or option abbreviation, because they read the parsed `--by`, not the command's text (the deny rule of
autopilot.RUNNER_DENY matches text and is a second layer). With the variable unset, the operator-present manager session
records the same answers as before.

Planted failures: the reordered form, the `--b` abbreviation, `--by=operator`, `--confirm` alone, `--confirm --by
operator`, `--record --by operator` and each operator-only kbdecide act, each refused with the variable set (exit 2, the
files unchanged) and working with it unset. The decision files are those of a throwaway repository, never this one's."""
from pathlib import Path

import pytest

import backlog
import bl_authority
import bl_cli
import kbpublic
import bl_testkit
from bl_testkit import b, edit, item_json
import test_backlog_authority as authority
from test_backlog_authority import decisions, gate_of, text_of, tool

bl_testkit.bind(backlog)
sprint = bl_testkit.sprint  # the fixture `decide` builds on
repo = bl_testkit.repo
throwaway_repo = authority.decide  # the fixture of test_backlog_authority.py: a started sprint's repository with the decision tools

ENV = kbpublic.HEADLESS_ENV


def provisional_answered_by_agent(r, bg):
    """A design gate the agent answered provisionally: the state `--confirm` acts on."""
    edit(r, bg, gates=[gate_of("Which way?", kind="provisional", answer="left", by="agent")])


def operator_forms(bg):
    """Every way to answer as the operator that a text rule on `answer * --by operator*` would miss or catch."""
    return {
        "reordered": ["answer", "--by", "operator", "--answer", "right", bg, "way"],
        "abbreviated": ["answer", bg, "way", "--answer", "right", "--b", "operator"],
        "equals": ["answer", bg, "way", "--answer", "right", "--by=operator"],
        "in-order": ["answer", bg, "way", "--answer", "right", "--by", "operator"],
        "record": ["answer", bg, "way", "--answer", "right", "--by", "operator", "--record"],
        "record-reordered": ["answer", "--record", "--by", "operator", "--answer", "right", bg, "way"],
        "confirm-alone": ["answer", bg, "way", "--confirm"],
        "confirm-operator": ["answer", bg, "way", "--confirm", "--by", "operator"],
        "confirm-abbreviated": ["answer", "--b", "operator", "--conf", bg, "way"],
        "confirm-agent": ["answer", bg, "way", "--confirm", "--by", "agent"],
    }


FORMS = list(operator_forms("X"))


@pytest.mark.parametrize("form", FORMS)
def test_backlog_headless_refuses_operator_answers_when_the_variable_is_set(throwaway_repo, monkeypatch, form):
    r, bg = throwaway_repo["repo"], throwaway_repo["bg"]
    provisional_answered_by_agent(r, bg)
    before = text_of(r, bg)
    monkeypatch.setenv(ENV, "1")
    code, out = b(r, *operator_forms(bg)[form])
    assert code == 2 and ENV in out and "operator-present" in out, out
    assert text_of(r, bg) == before and decisions(r) == []


@pytest.mark.parametrize("form", FORMS)
def test_backlog_headless_refuses_operator_answers_unset_works_as_before(throwaway_repo, monkeypatch, form):
    r, bg = throwaway_repo["repo"], throwaway_repo["bg"]
    provisional_answered_by_agent(r, bg)
    monkeypatch.delenv(ENV, raising=False)
    code, out = b(r, *operator_forms(bg)[form])
    gate = item_json(r, bg)["gates"][0]
    if form == "confirm-agent":  # existing behaviour: --by agent on --confirm is not refused without the variable
        assert code == 0, out
    elif form == "confirm-alone":  # existing behaviour: --confirm needs --by, which an agent passes only once told to
        assert code == 2 and gate["by"] == "agent", out
    else:
        assert code == 0 and gate["by"] == "operator", out
    if "record" in form:
        assert [d["by"] for d in decisions(r)] == ["operator"]


def test_backlog_headless_refuses_operator_answers_an_empty_variable_is_unset(throwaway_repo, monkeypatch):
    r, bg = throwaway_repo["repo"], throwaway_repo["bg"]
    monkeypatch.setenv(ENV, "")
    code, out = b(r, "answer", "--by", "operator", "--answer", "right", bg, "way")
    assert code == 0 and item_json(r, bg)["gates"][0]["by"] == "operator", out


def test_backlog_headless_refuses_operator_answers_keeps_agent_autopilot_and_provisional(throwaway_repo, monkeypatch):
    """Tightened (test_bl_authority_trust.py): a headless runner answers --by agent and --provisional only; the
    `--by autopilot` forms it used to keep (--confirm, --answer, --record) now exit 2 with the variable set, the
    autopilot's answers being the operator-present manager session's."""
    r, bg = throwaway_repo["repo"], throwaway_repo["bg"]
    monkeypatch.setenv(ENV, "1")
    edit(r, bg, gates=[gate_of("Which way?", kind="provisional")])
    code, out = b(r, "answer", bg, "way", "--provisional")
    assert code == 0 and item_json(r, bg)["gates"][0]["by"] == "agent", out
    before = text_of(r, bg)
    code, out = b(r, "answer", bg, "way", "--confirm", "--by", "autopilot")
    assert code == 2 and "--by agent only" in out and text_of(r, bg) == before, out
    code, out = b(r, "answer", "--by", "agent", "--answer", "right", bg, "way")
    assert code == 0 and item_json(r, bg)["gates"][0]["by"] == "agent", out
    edit(r, bg, gates=[gate_of("Which way?")])
    before = text_of(r, bg)
    code, out = b(r, "answer", "--by", "autopilot", "--answer", "right", "--record", bg, "way")
    assert code == 2 and decisions(r) == [] and text_of(r, bg) == before, out
    # existing class checks still hold with the variable set: a push gate is refused to the autopilot
    edit(r, bg, gates=[gate_of("Push to which remote?")])
    code, out = b(r, "answer", "--by", "autopilot", "--answer", "left", bg, "way")
    assert code == 2, out
    # and with the variable unset the manager session's autopilot answer is recorded as before
    monkeypatch.delenv(ENV)
    edit(r, bg, gates=[gate_of("Which way?")])
    code, out = b(r, "answer", "--by", "autopilot", "--answer", "right", "--record", bg, "way")
    assert code == 0 and [d["by"] for d in decisions(r)] == ["autopilot"], out


def test_backlog_headless_refuses_operator_answers_the_guard_reads_the_parsed_value(throwaway_repo, monkeypatch):
    """No text of the command matters: the abbreviation and the `=` form parse to the same `by`, and the refusal comes
    from `cmd_answer` on that value, with no permission rule involved."""
    r, bg = throwaway_repo["repo"], throwaway_repo["bg"]
    for argv in (["--b", "operator"], ["--by=operator"], ["--by", "operator"], ["--b=operator"]):
        a = bl_cli.build_parser("x", str(r)).parse_args(["--root", str(r), "answer", bg, "way", "--answer", "x", *argv])
        assert a.by == "operator"
        monkeypatch.setenv(ENV, "1")
        bl = backlog.Backlog(str(r))
        with pytest.raises(backlog.Rejected, match=ENV):
            backlog.cmd_answer(bl, a)
        monkeypatch.delenv(ENV)
        assert item_json(r, bg).get("gates")[0].get("answer") is None
    assert bl_authority.HEADLESS_ENV == ENV  # the name the runner sets (kbpublic.HEADLESS_ENV)


def test_backlog_headless_refuses_operator_answers_the_runner_sets_the_variable():
    import autopilot
    assert autopilot.HEADLESS_ENV == ENV == bl_authority.HEADLESS_ENV
    import kbdecide
    assert kbdecide.HEADLESS_ENV == ENV


def decide_state(r):
    return (Path(r) / "kb" / "_self" / "_decisions.csv").read_text(encoding="utf-8")


@pytest.fixture
def decided(throwaway_repo, monkeypatch):
    """kb/_self with a proposed decision and an active autopilot decision, made with the variable unset."""
    r = throwaway_repo["repo"]
    monkeypatch.delenv(ENV, raising=False)
    code, out = tool(r, "kbdecide.py", "propose", "--root", "_self", "--source", "test", "--context", f"item:{throwaway_repo['bg']}", "Proposed one")
    assert code == 0, out
    code, out = tool(r, "kbdecide.py", "record", "--root", "_self", "--source", "test", "--context", f"item:{throwaway_repo['st']}",
                     "--by", "autopilot", "--review-by", "2999-01-01", "Autopilot one")
    assert code == 0, out
    rows = {d["text"]: d["id"] for d in decisions(r)}
    return {"ctx": throwaway_repo["sp"], "repo": r, "proposed": rows["Proposed one"], "auto": rows["Autopilot one"]}


def decide_acts(d):
    return {
        "confirm": ["confirm", d["proposed"], "--root", "_self", "--by", "operator", "--maker", "operator"],
        "record": ["record", "--root", "_self", "--source", "s", "--context", "item:" + d["ctx"], "--by", "operator", "--maker", "operator", "Op one"],
        "record-reordered": ["record", "--by", "operator", "--root", "_self", "--context", "item:" + d["ctx"], "--source", "s",
                             "--maker", "operator", "Op one"],
        "record-abbreviated": ["record", "--root", "_self", "--source", "s", "--context", "item:" + d["ctx"], "--b", "operator",
                               "--maker", "operator", "Op one"],
        "supersede": ["supersede", d["auto"], d["proposed"], "--root", "_self", "--by", "operator"],
        "restore": ["restore", d["auto"], "--root", "_self", "--by", "operator"],
        "ratify": ["ratify", d["auto"], "--by", "operator"],
        "revert": ["revert", d["auto"], "--by", "operator", "--why", "no"],
        "makers": ["makers", "public", "--policy", "role-only", "--by", "operator"],
    }


ACTS = list(decide_acts({"proposed": "p", "auto": "a", "ctx": "x"}))


@pytest.mark.parametrize("act", ACTS)
def test_kbdecide_headless_refuses_operator_answers_when_the_variable_is_set(decided, monkeypatch, act):
    r = decided["repo"]
    before = decide_state(r)
    monkeypatch.setenv(ENV, "1")
    code, out = tool(r, "kbdecide.py", *decide_acts(decided)[act])
    assert code == 2 and ENV in out and "operator-present" in out, out
    assert decide_state(r) == before


@pytest.mark.parametrize("act", ["confirm", "record", "record-reordered", "record-abbreviated", "ratify"])
def test_kbdecide_headless_refuses_operator_answers_unset_works_as_before(decided, monkeypatch, act):
    r = decided["repo"]
    monkeypatch.delenv(ENV, raising=False)
    code, out = tool(r, "kbdecide.py", *decide_acts(decided)[act])
    assert code == 0, out


def test_kbdecide_headless_refuses_operator_answers_keeps_the_autopilot_record(decided, monkeypatch):
    r = decided["repo"]
    monkeypatch.setenv(ENV, "1")
    code, out = tool(r, "kbdecide.py", "record", "--root", "_self", "--source", "s", "--context", f"item:{decided['ctx']}", "--by",
                     "autopilot", "--review-by", "2999-01-01", "Another autopilot one")
    assert code == 0, out
    code, out = tool(r, "kbdecide.py", "list", "--root", "_self")
    assert code == 0 and "Another autopilot one" in out, out
