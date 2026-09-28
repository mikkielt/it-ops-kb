"""backlog.py in a throwaway git repository: items are created, validated, scheduled, finished and deleted.

Each refusal has a planted failure: a bug whose repro passes, a non-canonical file, a cycle, a blocking gate an
agent answers, a sprint started without the operator, a failing check, a commit outside `touches` (and the revert
that clears it), a review with an unconfirmed provisional answer, a malformed KB-Work trailer. The repository's
own backlog must pass `backlog.py check`.
"""
import json, os, subprocess, sys
from pathlib import Path

import pytest

import backlog
import kbgit

TOOLS = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(TOOLS, "backlog.py")


def sh(root, *a):
    subprocess.run(list(a), cwd=root, check=True, capture_output=True)


def b(root, *a):
    p = subprocess.run([sys.executable, TOOL, "--root", str(root), *a], cwd=root, capture_output=True, text=True,
                       encoding="utf-8")
    return p.returncode, p.stdout + p.stderr


def item(root, title):
    for f in (Path(root) / backlog.REL_DIR).glob("*.json"):
        it = json.loads(f.read_text(encoding="utf-8"))
        if it["title"] == title:
            return it
    raise AssertionError(title)


def edit(root, iid, **kw):
    f = Path(root) / backlog.REL_DIR / f"{iid}.json"
    it = json.loads(f.read_text(encoding="utf-8"))
    it.update(kw)
    f.write_text(backlog.canonical(it), encoding="utf-8", newline="\n")


def commit(root, msg, work=None):
    sh(root, "git", "add", "-A")
    sh(root, "git", "commit", "-qm", msg, *(["-m", f"KB-Work: {work}"] if work else []))


@pytest.fixture
def repo(tmp_path):
    sh(tmp_path, "git", "init", "-q")
    sh(tmp_path, "git", "config", "user.email", "agent@example.com")
    sh(tmp_path, "git", "config", "user.name", "agent")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.txt").write_text("a\n", encoding="utf-8")
    commit(tmp_path, "init")
    return tmp_path


@pytest.fixture
def sprint(repo):
    """An approved, started sprint with a story, its task and a bug."""
    assert b(repo, "new", "epic", "--title", "Epic", "--goal", "outcome")[0] == 0
    ep = item(repo, "Epic")["id"]
    b(repo, "new", "sprint", "--title", "Sprint", "--goal", "ship b")
    sp = item(repo, "Sprint")["id"]
    b(repo, "new", "story", "--title", "Story", "--parent", ep, "--sprint", sp, "--goal", "b exists",
      "--check", "test -f src/b.txt")
    st = item(repo, "Story")["id"]
    b(repo, "new", "task", "--title", "Task", "--parent", st, "--goal", "b written", "--touch", "src/**",
      "--check", "test -f src/b.txt")
    b(repo, "new", "bug", "--title", "Bug", "--sprint", sp, "--severity", "S3", "--repro", "test -f src/c.txt",
      "--goal", "c exists")
    assert b(repo, "answer", sp, "start", "--answer", "approve", "--by", "operator")[0] == 0
    code, out = b(repo, "start", sp)
    assert code == 0, out
    return {"repo": repo, "ep": ep, "sp": sp, "st": st, "tk": item(repo, "Task")["id"], "bg": item(repo, "Bug")["id"],
            "rv": item(repo, "Review sprint: Sprint")["id"]}


def test_new_items_validate(sprint):
    code, out = b(sprint["repo"], "check")
    assert code == 0 and "errors=0" in out, out


def test_bug_repro_must_fail_now(repo):
    code, out = b(repo, "new", "bug", "--title", "Not a bug", "--severity", "S4", "--repro", "true", "--goal", "x")
    assert code == 1 and "must fail" in out


def test_check_finds_planted_errors(sprint):
    repo = sprint["repo"]
    f = Path(repo) / backlog.REL_DIR / f"{sprint['tk']}.json"
    f.write_text(json.dumps(json.loads(f.read_text(encoding="utf-8"))) + "\n", encoding="utf-8")
    edit(repo, sprint["bg"], depends_on=[sprint["st"]])
    edit(repo, sprint["st"], depends_on=[sprint["bg"]])
    code, out = b(repo, "check")
    assert code == 1
    assert "canonical form" in out and "cycle" in out
    assert f"{sprint['tk']} “Task”" in out  # an id is never printed without its title


def test_task_needs_parent_and_touches(repo):
    b(repo, "new", "epic", "--title", "E", "--goal", "g")
    code, out = b(repo, "new", "task", "--title", "Orphan", "--goal", "g")
    assert "needs a parent" in out and "touches missing" in out


def test_only_operator_answers_blocking_gates_and_starts_sprints(repo):
    b(repo, "new", "sprint", "--title", "S", "--goal", "g")
    sp = item(repo, "S")["id"]
    assert b(repo, "start", sp)[0] == 1
    code, out = b(repo, "answer", sp, "start", "--answer", "approve", "--by", "agent")
    assert code == 1 and "only the operator" in out
    assert b(repo, "answer", sp, "start", "--provisional")[0] == 1


def test_next_orders_s1_bugs_first(sprint):
    repo = sprint["repo"]
    edit(repo, sprint["bg"], severity="S1")
    code, out = b(repo, "next", "--all")
    assert code == 0
    assert out.splitlines()[0].startswith(sprint["bg"])
    assert sprint["st"] not in out  # a story with an open task is not ready itself
    assert sprint["rv"] not in out  # the review waits on every other item


def test_done_refuses_failing_check_and_scope_then_passes(sprint):
    repo, tk = sprint["repo"], sprint["tk"]
    assert b(repo, "claim", tk, "--by", "agent-1")[0] == 0
    code, out = b(repo, "done", tk)
    assert code == 1 and "check(s) failed" in out
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    (repo / "stray.txt").write_text("x\n", encoding="utf-8")
    commit(repo, "write b", tk)
    code, out = b(repo, "done", tk)
    assert code == 1 and "stray.txt, outside touches" in out
    sh(repo, "git", "rm", "-q", "stray.txt")
    commit(repo, "revert stray", tk)
    code, out = b(repo, "done", tk)
    assert code == 0, out
    it = item(repo, "Task")
    assert it["status"] == "done" and it["evidence"]["commit"] and "claimed_by" not in it


def test_done_refuses_uncommitted_changes_in_scope(sprint):
    repo = sprint["repo"]
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    code, out = b(repo, "done", sprint["tk"])
    assert code == 1 and "uncommitted" in out


def test_horizon_splits_reachable_from_gated(sprint):
    repo = sprint["repo"]
    edit(repo, sprint["bg"], gates=[{"id": "G1", "kind": "blocking", "question": "Fix or drop?",
                                     "recommendation": "fix"}])
    code, out = b(repo, "horizon")
    assert code == 0
    assert "2 more reachable" in out and "2 wait on the operator" in out
    assert "Fix or drop?" in out and "critical path (2 steps" in out
    code, out = b(repo, "horizon", "--hook")
    hook = json.loads(out)
    assert "Fix or drop?" in hook["hookSpecificOutput"]["additionalContext"]


def test_review_needs_confirmed_provisional_answers_and_close_deletes(sprint):
    repo, bg = sprint["repo"], sprint["bg"]
    edit(repo, bg, gates=[{"id": "G1", "kind": "provisional", "question": "Name c?", "recommendation": "c.txt"}])
    assert b(repo, "answer", bg, "G1", "--provisional")[0] == 0
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    (repo / "src" / "c.txt").write_text("c\n", encoding="utf-8")
    commit(repo, "b and c", f"{sprint['tk']}, {bg}")
    for iid in (sprint["tk"], sprint["st"], bg):
        code, out = b(repo, "done", iid)
        assert code == 0, out
    edit(repo, sprint["rv"], checks=[{"run": ["true"]}])
    commit(repo, "state")
    code, out = b(repo, "done", sprint["rv"])
    assert code == 1 and "provisional answer to confirm" in out
    assert b(repo, "answer", bg, "G1", "--confirm")[0] == 0
    assert b(repo, "done", sprint["rv"])[0] == 0
    assert b(repo, "done", sprint["ep"])[0] == 0
    code, out = b(repo, "close", sprint["sp"])
    assert code == 0, out
    assert not list((Path(repo) / backlog.REL_DIR).glob("*.json"))


def test_close_refuses_open_items(sprint):
    code, out = b(sprint["repo"], "close", sprint["sp"])
    assert code == 1 and "not finished" in out


def test_goal_condition_names_checks_and_scope(sprint):
    code, out = b(sprint["repo"], "goal", sprint["tk"])
    assert "`test -f src/b.txt` exits 0" in out and "src/**" in out and f"backlog.py done {sprint['tk']}" in out


def test_glob_scope():
    assert backlog.in_scope("_tools/backlog.py", ["_tools/*.py"])
    assert not backlog.in_scope("_tools/sub/x.py", ["_tools/*.py"])
    assert backlog.in_scope("_tools/sub/x.py", ["_tools/**"])
    assert backlog.in_scope("kb/public/_coverage.csv", [])


def test_work_trailer(monkeypatch):
    have = {("abc", "kb/_self/backlog/TK-aaaaaaaa.json")}
    monkeypatch.setattr(kbgit, "blob", lambda rev, rel: "{}" if (rev, rel) in have else None)
    assert kbgit.work_ok("abc", ["TK-aaaaaaaa"])
    assert not kbgit.work_ok("abc", ["TK-bbbbbbbb"])  # no such item
    assert not kbgit.work_ok("abc", ["task 7"])  # not an id
    assert not kbgit.work_ok("abc", ["TK-aaaaaaaa", "TK-aaaaaaaa"])  # a second line


def test_repository_backlog_is_valid():
    code, out = b(os.path.dirname(TOOLS), "check")
    assert code == 0, out
