"""A sprint's goal research story (backlog.cmd_new, backlog.cmd_start): `new sprint` files a goal research story whose
touches are kb content, `check` holds its flag, and the operator's approval starts the sprint whatever the research
and the knowledge of its items read.

Run over a small kb of invented words (the corpus `test_bl_check.py`'s knowledge-state tests use), through a copy of the
tools in the repository so the pack reads that kb."""
import os
import subprocess
import sys

import pytest

import backlog
import bl_testkit
from bl_testkit import argstr, commit, edit, is_file, item, item_json

bl_testkit.bind(backlog)

repo, no_git_location, gate_jobs = bl_testkit.repo, bl_testkit.no_git_location, bl_testkit.gate_jobs

TOOL_ROOTS = ("backlog.py", "selfdoc.py")  # run as scripts there; what they import comes with them (bl_testkit.tool_closure)
TOOL_DATA = ("aliases.csv",)
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
        bl_testkit.copy_tool_closure(repo / "_tools", *TOOL_ROOTS, data=TOOL_DATA)
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

    def start(self, by):
        assert self.run("answer", self.sp, "start", "--answer", "approve", "--by", by)[0] == 0
        return self.run("start", self.sp)


@pytest.fixture
def plan(repo):
    bl_testkit.sh(repo, "git", "update-ref", "refs/remotes/origin/main", "HEAD")
    return Plan(repo)


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


def test_research_gated_start_an_operator_approved_start_is_unchanged(plan):
    """Research not done, no knowledge and an unknown ask: the operator's start still runs."""
    plan.know(plan.st, asks=[NONE])
    edit(plan.repo, plan.bg, knowledge={"ask": [], "refs": []})
    code, out = plan.start("operator")
    assert code == 0, out
    assert item_json(plan.repo, plan.sp)["status"] == "active"
    assert item_json(plan.repo, plan.rs)["status"] == "todo"
