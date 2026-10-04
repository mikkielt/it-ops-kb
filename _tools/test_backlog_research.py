"""A sprint starts only once its research is done (bl_check.autopilot_start_causes, backlog.cmd_start): `new sprint`
files a goal research story whose touches are kb content, and `start` of a sprint whose start gate the autopilot
answered refuses, naming each cause, while that story is not done, while a committed story or bug has no knowledge asks
or refs, or while one of its asks or refs reads unknown, partial, stale or conflicting. An operator's approval starts as before.

Each refusal has a planted failure over a small kb of invented words (the corpus `test_bl_check.py`'s knowledge-state
tests use), run through a copy of the tools in the repository so the pack reads that kb."""
import os
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest

import backlog
import bl_check
import bl_testkit
from bl_testkit import PASS, TOOLS, argstr, b, commit, edit, is_file, item, item_json

bl_testkit.bind(backlog)

repo, no_git_location, gate_jobs = bl_testkit.repo, bl_testkit.no_git_location, bl_testkit.gate_jobs

TOOL_FILES = ("backlog.py",) + tuple(sorted(f.name for f in Path(TOOLS).glob("bl_*.py"))) + (
    "kbcommon.py", "kbfacts.py", "kbid.py", "kbpublic.py", "ql_base.py", "aliases.csv", "selfdoc.py")
SOURCES = "id,url,title,superseded_by,used_in\nS100,https://example.com/a,Zorbex agent guide,,demo/tool.md\n"
FACTS = ["The zorbex agent prints its build number at startup.", "The zorbex agent retries failed uploads three times."]
GOOD = "How many times does the zorbex agent retry failed uploads?"
NONE = "How do I configure the wumpus frobnicator?"


def article(topic, title, facts):
    return (f"---\ntopic: {topic}\nstatus: partial\n---\n\n# {title}\n\n## Facts\n"
            + "".join(f"- {f} [DOC S100]\n" for f in facts))


class Plan:
    """A planned sprint (its research story filed by `new sprint`) with a story and a bug that each carry one
    sufficient ask, in a repository with its own copy of the tools and a small kb."""

    def __init__(self, repo):
        self.repo = repo
        self.root = repo / "kb" / "public"
        (repo / "_tools").mkdir()
        for f in TOOL_FILES:
            shutil.copy(os.path.join(TOOLS, f), repo / "_tools" / f)
        (self.root / "demo").mkdir(parents=True)
        files = {"_root.md": "---\nroot: public\nid_prefix: S\nvisibility: public\n---\n\n# public\n",
                 "_sources.csv": SOURCES, "_conflicts.md": "# Conflicts\n",
                 "demo/tool.md": article("demo/tool", "Zorbex sync agent", FACTS),
                 **{f"demo/filler{i}.md": article(f"demo/filler{i}", f"Filler {i}", [
                     f"Filler{i}a widget{i}b gizmo{i}c runs {i}d.", f"Sprocket{i}e flange{i}f."]) for i in range(12)}}
        for rel, text in files.items():
            self.write(rel, text)
        self.env = {k: v for k, v in os.environ.items() if k not in ("KB_ROOTS", "CLAUDE_PLUGIN_DATA")} | {
            "KB_INDEX": "0"}
        assert self.run("new", "sprint", "--title", "Sprint", "--goal", "ship b")[0] == 0
        self.sp = item(repo, "Sprint")["id"]
        self.rs = item(repo, "Research sprint goal: Sprint")["id"]
        assert self.run("new", "story", "--title", "Story", "--sprint", self.sp, "--goal", "b exists",
                        "--touch", "src/**", "--check", argstr(is_file("src/b.txt")))[0] == 0
        assert self.run("new", "bug", "--title", "Bug", "--sprint", self.sp, "--severity", "S3", "--goal", "c exists",
                        "--repro", argstr(is_file("src/c.txt")), "--touch", "src/**")[0] == 0
        self.st, self.bg = item(repo, "Story")["id"], item(repo, "Bug")["id"]
        self.know(self.st)
        self.know(self.bg)
        commit(repo, "plan")

    def write(self, rel, text):
        (self.root / rel).write_text(text, encoding="utf-8", newline="\n")

    def run(self, *a):
        p = subprocess.run([sys.executable, str(self.repo / "_tools" / "backlog.py"), "--root", str(self.repo), *a],
                           cwd=self.repo, capture_output=True, text=True, encoding="utf-8", env=self.env)
        return p.returncode, p.stdout + p.stderr

    def know(self, iid, asks=(GOOD,), refs=()):
        edit(self.repo, iid, knowledge={"ask": list(asks), "refs": list(refs)})

    def research_done(self):
        """The research story claimed, its kb content written under its own id, and done."""
        edit(self.repo, self.rs, checks=[{"run": PASS}])
        commit(self.repo, "checks")
        assert self.run("claim", self.rs, "--by", "agent-1")[0] == 0
        commit(self.repo, "claim", self.rs)
        self.write("demo/found.md", article("demo/found", "Found", ["The zorbex agent found a thing."]))
        commit(self.repo, "research", self.rs)
        code, out = b(self.repo, "done", self.rs)
        assert code == 0, out
        commit(self.repo, "done", self.rs)

    def start(self, by):
        assert self.run("answer", self.sp, "start", "--answer", "approve", "--by", by)[0] == 0
        return self.run("start", self.sp)


@pytest.fixture
def plan(repo):
    bl_testkit.sh(repo, "git", "update-ref", "refs/remotes/origin/main", "HEAD")
    return Plan(repo)


def refused_unchanged(p, code_out, *causes):
    code, out = code_out
    assert code == 1 and "starts a sprint only once its research is done" in out, out
    for c in causes:
        assert c in out, (c, out)
    assert item_json(p.repo, p.sp)["status"] == "planned" and item_json(p.repo, p.st)["status"] == "draft"


def test_research_gated_start_new_sprint_files_a_research_story_inside_the_kb_roots(plan):
    rs = item_json(plan.repo, plan.rs)
    assert rs["goal_research"] is True and rs["kind"] == "story" and rs["sprint"] == plan.sp and rs["status"] == "draft"
    assert backlog.research_touches(rs["touches"]) and rs["checks"]
    assert plan.run("check")[0] == 0
    assert item_json(plan.repo, plan.rs)["status"] == "draft"


def test_research_gated_start_check_refuses_a_research_flag_that_is_not_true_on_a_story(plan):
    edit(plan.repo, plan.rs, goal_research="yes")
    code, out = plan.run("check")
    assert code == 1 and "goal_research is true on the goal research story" in out, out


def test_research_gated_start_runs_when_research_is_done_and_every_item_is_sufficient(plan):
    plan.research_done()
    code, out = plan.start("autopilot")
    assert code == 0, out
    assert item_json(plan.repo, plan.sp)["status"] == "active" and item_json(plan.repo, plan.st)["status"] == "todo"


def test_research_gated_start_refuses_while_the_research_story_is_not_done(plan):
    refused_unchanged(plan, plan.start("autopilot"), f"the goal research story {plan.rs}", "draft, not done")
    plan.research_done()
    assert plan.run("start", plan.sp)[0] == 0


def test_research_gated_start_refuses_a_sprint_without_a_research_story(plan):
    edit(plan.repo, plan.rs, goal_research=None)
    code, out = plan.start("autopilot")
    assert code == 1 and "the sprint has no goal research story" in out, out


def test_research_gated_start_refuses_an_item_without_knowledge_asks_or_refs(plan):
    plan.research_done()
    edit(plan.repo, plan.st, knowledge={"ask": [], "refs": []})
    code_out = plan.start("autopilot")
    refused_unchanged(plan, code_out, f"{plan.st}", "has no knowledge asks or refs")
    assert f"{plan.bg}" not in code_out[1]


@pytest.mark.parametrize("state", ["unknown", "stale", "conflicting"])
def test_research_gated_start_refuses_a_ref_reading_each_unsound_state(plan, state):
    plan.research_done()
    if state == "unknown":
        plan.know(plan.st, asks=[GOOD, NONE])
    elif state == "stale":
        plan.write("_sources.csv", SOURCES.replace("Zorbex agent guide,,", "Zorbex agent guide,S101,"))
    else:
        plan.write("_conflicts.md", "# Conflicts\n\n- The pages disagree on retries. (topic: demo/tool)\n")
    refused_unchanged(plan, plan.start("autopilot"), f"knowledge {state} ask")


def partial_sprint():
    """A sprint whose research story is done and whose one story asks something the kb answers only partially: the
    states are planted (a `weak` pack is not reproducible over a small kb), the cause list is the code under test."""
    items = {"SP-aaaaaaaa": {"kind": "sprint"}, "ST-research": {"kind": "story", "goal_research": True, "status": "done"},
             "ST-work": {"kind": "story", "status": "draft", "knowledge": {"ask": ["an ask"], "refs": ["a ref"]}}}
    state = types.SimpleNamespace(of_ask=lambda t: ("partial", "coverage weak"), of_ref=lambda t: ("sufficient", ""))
    return types.SimpleNamespace(items=items, sprint_items=lambda s: [k for k in items if k != s],
                                 order_key=lambda i: i, label=lambda i: i, state=state)


def test_research_gated_start_partial_reading_refuses_like_the_other_unsound_states():
    causes = bl_check.autopilot_start_causes(partial_sprint(), "SP-aaaaaaaa")
    assert causes == ["ST-work: knowledge partial ask: an ask (coverage weak)"], causes


def test_research_gated_start_partial_a_sufficient_ask_and_ref_do_not_refuse():
    bl = partial_sprint()
    bl.state = types.SimpleNamespace(of_ask=lambda t: ("sufficient", ""), of_ref=lambda t: ("sufficient", ""))
    assert bl_check.autopilot_start_causes(bl, "SP-aaaaaaaa") == []


def test_research_gated_start_partial_planted_failure_the_old_states_let_it_through(monkeypatch):
    monkeypatch.setattr(bl_check, "UNSOUND", ("unknown", "stale", "conflicting"))  # the states before the fix
    assert bl_check.autopilot_start_causes(partial_sprint(), "SP-aaaaaaaa") == []  # a partial reading ran the start


def test_research_gated_start_names_every_cause_at_once(plan):
    plan.know(plan.st, asks=[NONE])
    edit(plan.repo, plan.bg, knowledge={"ask": [], "refs": []})
    code, out = plan.start("autopilot")
    assert code == 1
    assert "is draft, not done" in out and f"{plan.st}" in out and "knowledge unknown ask" in out
    assert f"{plan.bg}" in out and "has no knowledge asks or refs" in out


def test_research_gated_start_an_operator_approved_start_is_unchanged(plan):
    """Research not done, no knowledge and an unknown ask: the operator's start still runs."""
    plan.know(plan.st, asks=[NONE])
    edit(plan.repo, plan.bg, knowledge={"ask": [], "refs": []})
    code, out = plan.start("operator")
    assert code == 0, out
    assert item_json(plan.repo, plan.sp)["status"] == "active"
    assert item_json(plan.repo, plan.rs)["status"] == "todo"
