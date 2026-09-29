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


def test_check_interpreter_argv(monkeypatch, tmp_path):
    """run_check starts a python3 or python check with sys.executable (on Windows the venv launcher's base interpreter
    directory holds a python3.exe, so the PATH plant below cannot fail there); other commands are left as they are."""
    seen = []
    monkeypatch.setattr(backlog.subprocess, "run", lambda argv, **k: seen.append(argv) or subprocess.CompletedProcess(argv, 0, "", ""))
    for cmd in ("python3", "python", "git"):
        assert backlog.run_check(tmp_path, {"run": [cmd, "x"]})[0]
    assert seen == [[sys.executable, "x"], [sys.executable, "x"], ["git", "x"]]


def test_check_interpreter_is_the_one_running_backlog(sprint, tmp_path):
    """A check naming python3 runs with backlog.py's own interpreter: a python3 on PATH that fails (the Windows Store
    alias exits 49) or none at all does not fail the item."""
    import shutil
    repo, tk = sprint["repo"], sprint["tk"]
    edit(repo, tk, checks=[{"run": ["python3", "-c", "import os, sys; sys.exit(0 if os.path.isfile('src/b.txt') else 1)"]}])
    commit(repo, "a python3 check")
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    commit(repo, "write b", tk)
    bad = tmp_path / "bad-python"
    bad.mkdir()
    for name in ("python3", "python"):
        (bad / name).write_text("#!/bin/sh\nexit 49\n", encoding="utf-8", newline="\n")
        (bad / name).chmod(0o755)
    # Windows cannot start the planted scripts: there PATH holds git's directory and no Python at all
    path = os.path.dirname(shutil.which("git")) if os.name == "nt" else str(bad) + os.pathsep + os.environ["PATH"]
    env = {**os.environ, "PATH": path}
    run = lambda *a: subprocess.run([sys.executable, TOOL, "--root", str(repo), *a], cwd=repo, capture_output=True,  # noqa: E731
                                    text=True, encoding="utf-8", env=env)
    assert run("claim", tk, "--by", "agent-1").returncode == 0
    p = run("done", tk)
    assert p.returncode == 0, p.stdout + p.stderr
    assert item(repo, "Task")["status"] == "done"


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


# ---- red-pipeline: a planted red and a green pipeline on origin's main, glab and gh replaced (no network)

def forge(monkeypatch, repo, pipelines, jobs=(), signed_in=True):
    """origin is a GitLab project; `glab` answers the given pipelines (newest first) and failed jobs."""
    sh(repo, "git", "remote", "add", "origin", "https://gitlab.example.com/team/kb.git")
    sh(repo, "git", "update-ref", "refs/remotes/origin/main", "HEAD")
    real = backlog.run

    def fake(argv, cwd=None):
        if argv[:2] == ["git", "fetch"]:
            return 0, "", ""
        if argv[0] in ("glab", "gh"):
            if argv[1] == "auth":
                return (0, "", "") if signed_in else (1, "", "not logged in")
            return 0, json.dumps(jobs if "/jobs?" in argv[-1] else pipelines), ""
        return real(argv, cwd=cwd)

    monkeypatch.setattr(backlog, "run", fake)
    monkeypatch.setattr(backlog, "run_check", lambda root, c: (False, 1, ""))  # the repro fails: main is red


def head(repo):
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()


def bugs(repo):
    return [it for it in backlog.Backlog(repo).items.values() if it["kind"] == "bug"]


def red_pipeline(repo, *a):
    return backlog.main(["--root", str(repo), "red-pipeline", *a])


def test_red_pipeline_files_one_s2_bug_per_pipeline(repo, monkeypatch, capsys):
    sha = head(repo)
    forge(monkeypatch, repo, [{"id": 902, "sha": sha, "status": "running"},
                              {"id": 901, "sha": sha, "status": "failed", "web_url": "https://x/901"},
                              {"id": 900, "sha": sha, "status": "success"}],
          jobs=[{"name": "kb-tests-windows", "status": "failed"}])
    assert red_pipeline(repo) == 0
    (bug,) = bugs(repo)
    assert bug["severity"] == "S2" and bug["status"] == "draft" and "pipeline 901" in bug["title"]
    assert bug["repro"]["run"] == backlog.STATUS_REPRO
    assert backlog.validate(backlog.Backlog(repo)) == []
    capsys.readouterr()
    assert red_pipeline(repo) == 0  # the same pipeline again: named by the bug, nothing filed
    assert "already filed" in capsys.readouterr().out
    assert len(bugs(repo)) == 1


def test_red_pipeline_gate_job_is_s1_and_joins_the_active_sprint(sprint, monkeypatch):
    repo = sprint["repo"]
    forge(monkeypatch, repo, [{"id": 77, "sha": head(repo), "status": "failed"}],
          jobs=[{"name": "kb-tests", "status": "failed"}])
    assert red_pipeline(repo) == 0
    (bug,) = [x for x in bugs(repo) if "pipeline 77" in x["title"]]
    assert bug["severity"] == "S1" and bug["sprint"] == sprint["sp"] and bug["status"] == "todo"


def test_red_pipeline_green_files_nothing(repo, monkeypatch, capsys):
    forge(monkeypatch, repo, [{"id": 5, "sha": head(repo), "status": "success"},
                              {"id": 4, "sha": head(repo), "status": "failed"}])
    assert red_pipeline(repo) == 0
    assert bugs(repo) == [] and "green" in capsys.readouterr().out
    assert red_pipeline(repo, "--status") == 0


def test_red_pipeline_status_is_the_repro_of_a_red_main(repo, monkeypatch):
    forge(monkeypatch, repo, [{"id": 5, "sha": head(repo), "status": "failed"}])
    assert red_pipeline(repo, "--status") == 1


def test_red_pipeline_automatic_revert_covers_it(repo, monkeypatch):
    sh(repo, "git", "commit", "-q", "--allow-empty", "-m", "query log", "-m", "KB-Auto: apply")
    auto = head(repo)
    sh(repo, "git", "commit", "-q", "--allow-empty", "-m", "revert: query log commit",
       "-m", f"This reverts commit {auto}.", "-m", "KB-Auto: revert")
    forge(monkeypatch, repo, [{"id": 8, "sha": auto, "status": "failed"}])
    assert red_pipeline(repo) == 0
    assert bugs(repo) == []


def test_red_pipeline_revert_of_another_commit_does_not_cover_it(repo, monkeypatch):
    sh(repo, "git", "commit", "-q", "--allow-empty", "-m", "query log", "-m", "KB-Auto: apply")
    auto = head(repo)
    sh(repo, "git", "commit", "-q", "--allow-empty", "-m", "a human commit")
    human = head(repo)
    sh(repo, "git", "commit", "-q", "--allow-empty", "-m", "revert: query log commit",
       "-m", f"This reverts commit {auto}.", "-m", "KB-Auto: revert")
    forge(monkeypatch, repo, [{"id": 9, "sha": human, "status": "failed"}])
    assert red_pipeline(repo) == 0
    assert "pipeline 9" in bugs(repo)[0]["title"]


def test_red_pipeline_notes_when_not_signed_in(repo, monkeypatch, capsys):
    forge(monkeypatch, repo, [{"id": 5, "sha": head(repo), "status": "failed"}], signed_in=False)
    assert red_pipeline(repo) == 0
    assert "not signed in" in capsys.readouterr().out and bugs(repo) == []
    assert red_pipeline(repo, "--status") == 1
