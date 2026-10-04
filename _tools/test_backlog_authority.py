"""Who answers a gate (kb/_self/backlog.md, Dependencies, gates and triggers): each gate has a class that backlog.py
derives from the item's touches and the gate's question and an agent cannot lower, a gate of a class in
`bl_authority.OPERATOR_CLASSES` (secrets, push, agents-rule) takes only the operator's answer, and `--record` keeps the
operator's answer as an active decision of kb/_self.

Every refusal has a planted failure: a secrets gate and a push gate an agent answers (the item unchanged, the class
named), a class an agent wrote lower than the derived one (the agent is still refused, `check` reports it), an item
whose touches raise the class of a gate with a harmless question, an answer or a decision by a maker that is not the
operator, and a decision kbdecide refuses. The decision files are those of a throwaway repository, never this one's."""
import csv, os, shutil, subprocess, sys
from pathlib import Path

import pytest

import backlog
import bl_authority
import bl_testkit
from bl_testkit import b, commit, edit, item_json, TOOLS

bl_testkit.bind(backlog)
repo, sprint, no_git_location, gate_jobs = bl_testkit.repo, bl_testkit.sprint, bl_testkit.no_git_location, bl_testkit.gate_jobs

DECIDE_TOOLS = ("kbdecide.py", "check.py", "kbcommon.py", "kbid.py", "kbfacts.py")
ROOT_MD = "---\nroot: public\nid_prefix: S\nvisibility: public\ndescription: test root\n---\n"
SOURCES_HEADER = ("id,url,title,publisher,licence,reuse,retrieved_utc,version_or_date,artifact_sha256,used_in,"
                  "superseded_by\n")
DECISION_COLS = "id,text,by,by_ref,source,date,context,status,invalidated_reason,invalidated_date,supersedes,review_by,links\n"
MAKERS = ("id,role,name,source\noperator,operator,,the operator answers a gate\n"
          "autopilot,autopilot,,the maker of the autopilot decisions kept from before its retirement\n")


def gate_of(question, **kw):
    return {"id": "way", "kind": "blocking", "question": question, "options": ["left", "right"],
            "recommendation": "left", **kw}


@pytest.fixture
def decide(sprint):
    """The started sprint's repository with a copy of the decision tools, a minimal public root and kb/_self's decision
    files with the operator role, so a recorded answer lands in the copy."""
    r = sprint["repo"]
    (r / "_tools").mkdir()
    for name in DECIDE_TOOLS:
        shutil.copy(os.path.join(TOOLS, name), r / "_tools" / name)
    pub = r / "kb" / "public"
    pub.mkdir(parents=True)
    for rel, text in (("_root.md", ROOT_MD), ("_sources.csv", SOURCES_HEADER), ("_artifacts.csv", "path,source_id,sha256\n"),
                      ("_answers.md", "# Answers\n"), ("_gaps.md", "# Gaps\n"), ("_conflicts.md", "# Conflicts\n")):
        (pub / rel).write_text(text, encoding="utf-8", newline="\n")
    (r / "kb" / "_self").mkdir(exist_ok=True)
    (r / "kb" / "_self" / "_decisions.csv").write_text(DECISION_COLS, encoding="utf-8", newline="\n")
    (r / "kb" / "_self" / "decision-makers.csv").write_text(MAKERS, encoding="utf-8", newline="\n")
    (r / ".gitignore").write_text("__pycache__/\n", encoding="utf-8", newline="\n")
    edit(r, sprint["bg"], gates=[gate_of("Which way?")])
    commit(r, "decision tools")
    return sprint


def text_of(r, iid):
    return (Path(r) / backlog.REL_DIR / f"{iid}.json").read_text(encoding="utf-8")


def decisions(r):
    with open(Path(r) / "kb" / "_self" / "_decisions.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def tool(r, name, *args):
    p = subprocess.run([sys.executable, str(Path(r) / "_tools" / name), *args], cwd=r, capture_output=True, text=True,
                       encoding="utf-8")
    return p.returncode, p.stdout + p.stderr


@pytest.mark.parametrize("question,cls", [
    ("Which password do we rotate?", "secrets"),
    ("Which API key does the runner use?", "secrets"),
    ("Push to which remote?", "push"),
    ("May we publish the tree?", "push"),
    ("Which query log mode?", "querylog"),
    ("How is the log redacted?", "querylog"),
    ("Which rule goes in AGENTS.md?", "agents-rule"),
    ("Delete the old kb articles?", "delete"),
    ("Which name for the flag?", "design"),
])
def test_gate_authority_class_follows_the_question(question, cls):
    assert bl_authority.derived_class({"touches": ["src/**"]}, gate_of(question)) == cls


@pytest.mark.parametrize("touches,cls", [
    (["_tools/kbgit.py"], "push"),
    ([".gitlab-ci.yml"], "push"),
    (["_tools/kg_*.py"], "push"),
    ([".github/**"], "push"),
    (["kb/_querylog/**"], "querylog"),
    (["AGENTS.md"], "agents-rule"),
    ([".claude/agents/kb-worker.md"], "agents-rule"),
    ([".claude/skills/**"], "agents-rule"),
    ([".claude/**"], "agents-rule"),
    (["src/credentials.json"], "secrets"),
    (["src/**", "docs/readme.md"], "design"),
    (["_tools/bl_plan*.py"], "agents-rule"),  # the bl_ modules are guarded code the tests run
    (["_tools/bl_plan.py", "_tools/tests.py", "_tools/conftest.py"], "agents-rule"),
    (["_tools/blame.py", "_tools/test_x.py", "docs/tests.py.md"], "design"),
])
def test_gate_authority_class_follows_the_touches(touches, cls):
    assert bl_authority.derived_class({"touches": touches}, gate_of("Which name?")) == cls


def test_gate_authority_strictest_class_wins_and_the_start_gate_is_start():
    it = {"touches": ["AGENTS.md", "_tools/kbgit.py"]}
    assert bl_authority.derived_class(it, gate_of("Which password?")) == "secrets"
    assert bl_authority.derived_class(it, gate_of("Which name?")) == "push"
    assert bl_authority.derived_class({}, {"id": "start", "question": "Approve?", "options": ["approve", "no"]}) == "start"
    assert bl_authority.OPERATOR_CLASSES == ("secrets", "push", "agents-rule")
    assert [c for c in bl_authority.CLASSES if c not in bl_authority.OPERATOR_CLASSES] == [
        "start", "querylog", "delete", "design"]


@pytest.mark.parametrize("question,cls", [("Which password do we rotate?", "secrets"), ("Push to which remote?", "push"),
                                          ("Which rule goes in AGENTS.md?", "agents-rule")])
def test_gate_authority_refuses_an_agent_an_operator_class_and_leaves_the_item(decide, question, cls):
    r, bg = decide["repo"], decide["bg"]
    edit(r, bg, gates=[gate_of(question, kind="provisional")])
    before = text_of(r, bg)
    code, out = b(r, "answer", bg, "way", "--provisional")
    assert code == 2 and f"class {cls}" in out and text_of(r, bg) == before, out
    code, out = b(r, "answer", bg, "way", "--answer", "left", "--by", "agent")
    assert code == 1 and f"class {cls}" in out and text_of(r, bg) == before, out
    code, out = b(r, "answer", bg, "way", "--answer", "left", "--by", "operator")
    assert code == 0 and item_json(r, bg)["gates"][0]["by"] == "operator", out


@pytest.mark.parametrize("touches,cls", [
    (["_tools/kbgit.py"], "push"),
    (["_tools/kg_sync.py", "src/**"], "push"),
    (["src/secrets.env"], "secrets"),
])
def test_gate_authority_the_items_touches_raise_the_class_of_a_harmless_gate(decide, touches, cls):
    r, bg = decide["repo"], decide["bg"]
    edit(r, bg, touches=touches, gates=[gate_of("Which way?", kind="provisional")])
    before = text_of(r, bg)
    code, out = b(r, "answer", bg, "way", "--provisional")
    assert code == 2 and f"class {cls}" in out, out
    assert text_of(r, bg) == before


def test_gate_authority_an_agent_cannot_lower_the_class(decide):
    r, bg = decide["repo"], decide["bg"]
    edit(r, bg, gates=[gate_of("Which password do we rotate?", **{"class": "design"})])
    assert bl_authority.gate_class(item_json(r, bg), item_json(r, bg)["gates"][0]) == "secrets"
    code, out = b(r, "check")
    assert code == 1 and "class design is lower than secrets" in out, out
    before = text_of(r, bg)
    code, out = b(r, "answer", bg, "way", "--answer", "left", "--by", "agent")
    assert code == 1 and "only the operator" in out and text_of(r, bg) == before, out
    edit(r, bg, gates=[gate_of("Which password do we rotate?", **{"class": "nonsense"})])
    code, out = b(r, "check")
    assert code == 1 and "not one of" in out, out


def test_gate_authority_a_stored_class_above_the_derived_one_holds(decide):
    r, bg = decide["repo"], decide["bg"]
    edit(r, bg, gates=[gate_of("Which name?", kind="provisional", **{"class": "push"})])
    assert bl_authority.gate_class(item_json(r, bg), item_json(r, bg)["gates"][0]) == "push"
    assert b(r, "check")[0] == 0
    code, out = b(r, "set", bg, "--touch", "docs/**", "--add")  # a re-class keeps the stricter stored class
    assert code == 0, out
    g = item_json(r, bg)["gates"][0]
    assert (g["class"], g["kind"]) == ("push", "blocking")
    before = text_of(r, bg)
    code, out = b(r, "answer", bg, "way", "--provisional")
    assert code == 1 and "only the operator" in out and text_of(r, bg) == before, out


def test_gate_authority_gate_add_stores_the_derived_class(decide):
    r, bg = decide["repo"], decide["bg"]
    code, out = b(r, "gate", "add", bg, "--id", "pw", "--question", "Which password do we rotate?",
                  "--option", "a", "--option", "b", "--recommendation", "a")
    assert code == 0, out
    assert [g.get("class") for g in item_json(r, bg)["gates"]] == [None, "secrets"]
    assert b(r, "check")[0] == 0
    code, out = b(r, "gate", "add", bg, "--id", "pw", "--question", "Which password do we rotate?",
                  "--option", "a", "--option", "b", "--recommendation", "a")
    assert code == 0 and "unchanged" in out, out


def test_gate_authority_only_the_operator_and_an_agent_answer(decide):
    """The answer's maker is the operator or an agent: any other `--by` is a usage error and leaves the item."""
    r, bg = decide["repo"], decide["bg"]
    edit(r, bg, gates=[gate_of("Which name?", kind="provisional")])
    before = text_of(r, bg)
    for by in ("autopilot", "manager"):
        code, out = b(r, "answer", bg, "way", "--answer", "left", "--by", by)
        assert code == 2 and "invalid choice" in out and text_of(r, bg) == before, (by, out)
        code, out = b(r, "answer", bg, "way", "--confirm", "--by", by)
        assert code == 2 and text_of(r, bg) == before, (by, out)
    assert b(r, "answer", bg, "way", "--provisional")[0] == 0
    assert b(r, "answer", bg, "way", "--confirm", "--by", "operator")[0] == 0
    assert item_json(r, bg)["gates"][0]["by"] == "operator"


def test_gate_authority_record_writes_the_operators_active_decision(decide):
    r, bg = decide["repo"], decide["bg"]
    code, out = b(r, "answer", bg, "way", "--answer", "left", "--by", "operator", "--record")
    assert code == 0, out
    (row,) = decisions(r)
    assert (row["status"], row["by"], row["by_ref"], row["context"]) == ("active", "operator", "operator", f"item:{bg}")
    assert row["review_by"] == "" and f"{bg} gate way" in row["source"] and row["text"] == "left"
    assert item_json(r, bg)["gates"][0]["answer"] == "left"
    assert tool(r, "check.py")[0] == 0


def test_gate_authority_record_needs_the_operators_answer(decide):
    r, bg = decide["repo"], decide["bg"]
    edit(r, bg, gates=[gate_of("Which name?", kind="provisional")])
    before = text_of(r, bg)
    code, out = b(r, "answer", bg, "way", "--answer", "left", "--by", "agent", "--record")
    assert code == 2 and "--by operator" in out and text_of(r, bg) == before and decisions(r) == [], out


def test_gate_authority_a_record_refused_by_kbdecide_leaves_the_gate_open(decide):
    r, bg = decide["repo"], decide["bg"]
    (Path(r) / "kb" / "_self" / "decision-makers.csv").write_text(MAKERS.splitlines()[0] + "\nreviewer,reviewer,,x\n",
                                                                  encoding="utf-8", newline="\n")
    before = text_of(r, bg)
    code, out = b(r, "answer", bg, "way", "--answer", "left", "--by", "operator", "--record")
    assert code == 1 and "no decision maker 'operator'" in out, out
    assert text_of(r, bg) == before and decisions(r) == []


@pytest.mark.parametrize("args", [
    ("--by", "autopilot", "--review-by", "2999-01-01"),
    ("--by", "autopilot"),
    ("--by", "agent", "--review-by", "2999-01-01"),
    (),
])
def test_gate_authority_kbdecide_record_is_the_operators_only(decide, args):
    r = decide["repo"]
    code, out = tool(r, "kbdecide.py", "record", "--root", "_self", "--source", "s", "--context", "item:BG-aaaaaaaa", *args,
                     "--", "left")
    assert code != 0 and "operator" in out and decisions(r) == [], out
    code, out = tool(r, "kbdecide.py", "record", "--root", "_self", "--source", "s", "--context",
                     f"item:{decide['bg']}", "--by", "operator", "--maker", "operator", "--", "left")
    assert code == 0 and [x["by"] for x in decisions(r)] == ["operator"], out
