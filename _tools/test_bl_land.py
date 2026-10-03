"""backlog.py done, land and close (bl_land.py): done runs an item's checks and records the evidence, land rebases a
worker's branch on the integration main and runs the steps after it, close deletes a finished sprint.

Each refusal has a planted failure: a check that fails, a commit outside `touches` (and the revert that clears it), a
KB-Work trailer outside the trailer paragraph, a claim commit that is not the work, a task whose code is not on the
integration main, a check that passes doing nothing in this clone, a landing whose step fails (land stops there, naming
it), a rebase conflict, a dirty tree, a worker's worktree with a process still running in it, a merge request stuck
behind a skipped pipeline, and a sprint closed with an item still open. The patches name the module where the code
looks the name up, `bl_land`.
"""
import argparse, json, os, shlex, subprocess, sys, time
from pathlib import Path

import pytest

import backlog
import bl_land
import bl_testkit
from bl_check import HOST_BOUND_GATE
from bl_testkit import (
    PASS, TOOL, TOOLS, argstr, b, commit, edit, finish_task, is_file, item, land, sh,
    story_with_touches,
)

bl_testkit.bind(backlog)
repo, sprint, no_git_location, gate_jobs = bl_testkit.repo, bl_testkit.sprint, bl_testkit.no_git_location, bl_testkit.gate_jobs


NOOP_TOOL = """import pathlib, sys
if not pathlib.Path('remote.cfg').is_file():
    print('note: no public remote (git config kb.publishRemote <remote>); nothing published')
    sys.exit(0)
sys.exit('refused: the defect')
"""


def noop_bug(sprint):
    """BG-uqmjlqfl planted: a bug whose repro runs a tool that fails while the clone has its remote (the defect), then
    the remote goes and the repro passes doing nothing."""
    repo = sprint["repo"]
    (repo / "pub.py").write_text(NOOP_TOOL, encoding="utf-8", newline="\n")
    (repo / "remote.cfg").write_text("pub\n", encoding="utf-8")
    (repo / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")  # pytest's rewritten test_fix.py
    commit(repo, "tool")
    code, out = b(repo, "new", "bug", "--title", "Publish refuses", "--sprint", sprint["sp"], "--severity", "S2",
                  "--repro", "python3 pub.py", "--goal", "publish works", "--touch", "remote.cfg", "--touch", "test_fix.py")
    assert code == 0 and "no --check runs tests" in out, out
    bg = item(repo, "Publish refuses")["id"]
    commit(repo, "file bug")
    sh(repo, "git", "rm", "-q", "remote.cfg")
    commit(repo, "the remote goes", bg)
    return repo, bg


def test_done_flags_noop_check_refuses_a_repro_that_does_nothing_here(sprint):
    repo, bg = noop_bug(sprint)
    code, out = b(repo, "done", bg)
    assert code == 1 and "passed without doing its work" in out and "no public remote" in out, out
    assert "no check that runs tests" in out and item(repo, "Publish refuses")["status"] != "done"
    # the operator accepts the host-bound proof: done passes, still warning of it
    assert b(repo, "gate", "add", bg, "--id", HOST_BOUND_GATE, "--question", "Accept?", "--option", "accept",
             "--option", "add-test", "--recommendation", "add-test")[0] == 0
    assert b(repo, "answer", bg, HOST_BOUND_GATE, "--answer", "accept", "--by", "operator")[0] == 0
    commit(repo, "gate", bg)
    code, out = b(repo, "done", bg, "--dry-run")
    assert code == 0 and "warning:" in out and "would be done" in out, out


def test_done_flags_noop_check_passes_with_a_test_run(sprint):
    """A check that runs tests and did its work proves the fix beside the no-op repro; one whose tests were all
    skipped does not."""
    pytest.importorskip("pytest")
    repo, bg = noop_bug(sprint)
    run = "python3 -m pytest -q -p no:cacheprovider test_fix.py"
    edit(repo, bg, checks=[{"run": shlex.split(run)}])
    (repo / "test_fix.py").write_text("import pytest\n\n\ndef test_fix():\n    pytest.skip('planted')\n",
                                      encoding="utf-8")
    commit(repo, "a skipped test", bg)
    code, out = b(repo, "done", bg)
    assert code == 1 and "no check that runs tests" in out, out
    (repo / "test_fix.py").write_text("def test_fix():\n    assert True\n", encoding="utf-8")
    commit(repo, "the test runs", bg)
    code, out = b(repo, "done", bg)
    assert code == 0 and "warning:" in out and "no public remote" in out, out


def test_done_refuses_failing_check_and_scope_then_passes(sprint):
    repo, tk = sprint["repo"], sprint["tk"]
    assert b(repo, "claim", tk, "--by", "agent-1")[0] == 0
    (repo / "src" / "x.txt").write_text("x\n", encoding="utf-8")
    commit(repo, "start", tk)
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


def test_done_refuses_kb_work_outside_trailers(sprint):
    """A KB-Work line in a paragraph before Co-Authored-By is no trailer for git: done sees no commit and refuses."""
    repo, tk = sprint["repo"], sprint["tk"]
    assert b(repo, "claim", tk, "--by", "agent-1")[0] == 0
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    sh(repo, "git", "add", "-A")
    sh(repo, "git", "commit", "-qm", f"write b\n\nKB-Work: {tk}\n\nCo-Authored-By: A <a@example.com>")
    code, out = b(repo, "done", tk)
    assert code == 1 and "no commit on HEAD carries the trailer" in out
    (repo / "src" / "y.txt").write_text("y\n", encoding="utf-8")
    sh(repo, "git", "add", "-A")
    sh(repo, "git", "commit", "-qm", f"more\n\nCo-Authored-By: A <a@example.com>\nKB-Work: {tk}")
    code, out = b(repo, "done", tk)
    assert code == 0, out


def test_done_claim_commit_alone_is_not_the_work(sprint):
    """Planted: the claim commit carries KB-Work but changes only item files, and the work commit's KB-Work sits in a
    paragraph before Co-Authored-By: done does not count the claim commit as the work, so it refuses."""
    repo, bg = sprint["repo"], sprint["bg"]
    assert b(repo, "claim", bg, "--by", "agent-1")[0] == 0
    commit(repo, "claim", bg)
    (repo / "src" / "c.txt").write_text("c\n", encoding="utf-8")
    sh(repo, "git", "add", "-A")
    sh(repo, "git", "commit", "-qm", f"write c\n\nKB-Work: {bg}\n\nCo-Authored-By: A <a@example.com>")
    code, out = b(repo, "done", bg)
    assert code == 1 and "no commit on HEAD carries the trailer" in out, out
    (repo / "src" / "d.txt").write_text("d\n", encoding="utf-8")
    commit(repo, "write d", bg)
    code, out = b(repo, "done", bg)
    assert code == 0, out


def test_done_counts_descendant_commits_story_closes(sprint):
    """A story with touches whose task's commits carried the work is done without a commit of its own."""
    repo, st, tk = story_with_touches(sprint)
    finish_task(repo, tk)
    code, out = b(repo, "done", st)
    assert code == 0, out
    assert item(repo, "Story")["status"] == "done"


def test_done_counts_descendant_commits_none_still_refused(sprint):
    """Planted: a story with touches and no commit under its id or its task's ids is still refused."""
    repo, st, tk = story_with_touches(sprint)
    edit(repo, tk, status="done")  # the task closed by hand, with no work commit anywhere
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    commit(repo, "b, with no KB-Work trailer")
    code, out = b(repo, "done", st)
    assert code == 1 and "no commit on HEAD carries the trailer" in out, out


def test_done_counts_descendant_commits_outside_touches(sprint):
    """A task's commit outside the story's scope is still refused on the story."""
    repo, st, tk = story_with_touches(sprint)
    assert b(repo, "claim", tk, "--by", "agent-1")[0] == 0
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    (repo / "stray.txt").write_text("x\n", encoding="utf-8")
    commit(repo, "write b and stray", tk)
    edit(repo, tk, status="done")
    commit(repo, "task done", tk)
    code, out = b(repo, "done", st)
    assert code == 1 and "stray.txt, outside touches" in out, out


def test_check_interpreter_argv(monkeypatch, tmp_path):
    """run_check starts a python3 or python check with sys.executable (on Windows the venv launcher's base interpreter
    directory holds a python3.exe, so the PATH plant below cannot fail there); other commands are left as they are."""
    seen = []
    monkeypatch.setattr(backlog.subprocess, "run", lambda argv, **k: seen.append(argv) or subprocess.CompletedProcess(argv, 0, "", ""))
    for cmd in ("python3", "python", "git"):
        assert bl_land.run_check(tmp_path, {"run": [cmd, "x"]})[0]
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
    land(repo)
    p = run("done", tk)
    assert p.returncode == 0, p.stdout + p.stderr
    assert item(repo, "Task")["status"] == "done"


def test_done_refuses_uncommitted_changes_in_scope(sprint):
    repo = sprint["repo"]
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    code, out = b(repo, "done", sprint["tk"])
    assert code == 1 and "uncommitted" in out


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
    edit(repo, sprint["rv"], checks=[{"run": PASS}])
    commit(repo, "state")
    code, out = b(repo, "done", sprint["rv"])
    assert code == 1 and "provisional answer to confirm" in out
    assert b(repo, "answer", bg, "G1", "--confirm", "--by", "operator")[0] == 0
    assert b(repo, "done", sprint["rv"])[0] == 0
    assert b(repo, "done", sprint["ep"])[0] == 0
    code, out = b(repo, "close", sprint["sp"])
    assert code == 0, out
    assert not list((Path(repo) / backlog.REL_DIR).glob("*.json"))


def test_close_summary_lists_every_item_with_its_evidence_commit(sprint):
    """close --summary prints one line per item close deletes (the task, the review, a dropped subtask and the
    finished epic included) with the commit done recorded, and nothing else."""
    repo, tk, st, bg, rv, ep = (sprint[k] for k in ("repo", "tk", "st", "bg", "rv", "ep"))
    b(repo, "new", "subtask", "--title", "Sub", "--parent", tk, "--goal", "x", "--touch", "src/**",
      "--check", argstr(PASS))
    sb = item(repo, "Sub")["id"]
    assert b(repo, "drop", sb, "--why", "not needed")[0] == 0
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    (repo / "src" / "c.txt").write_text("c\n", encoding="utf-8")
    commit(repo, "b and c", f"{tk}, {bg}")
    work = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
    for iid in (tk, st, bg):
        code, out = b(repo, "done", iid)
        assert code == 0, out
    edit(repo, rv, checks=[{"run": PASS}])
    commit(repo, "state")
    assert b(repo, "done", rv)[0] == 0
    assert b(repo, "done", ep)[0] == 0
    code, out = b(repo, "close", sprint["sp"], "--summary")
    assert code == 0, out
    lines = out.splitlines()
    assert lines[0] == f"delivered by {sprint['sp']} “Sprint”:", out
    body = lines[1:]
    assert any(x.startswith(f"- {ep} “Epic” (epic): done at ") for x in body)  # the finished epic goes too
    assert f"  - {st} “Story” (story): done at {work[:10]}" in body
    assert f"    - {tk} “Task” (task): done at {work[:10]}" in body
    assert f"      - {sb} “Sub” (subtask): dropped, no evidence commit" in body
    assert f"- {bg} “Bug” (bug): done at {work[:10]}" in body
    assert any(x.startswith(f"- {rv} “Review sprint: Sprint” (story): done at ") for x in body)
    assert f"- {sprint['rs']} “Research sprint goal: Sprint” (story): dropped, no evidence commit" in body
    assert len(body) == 7, body  # one line per deleted item, no more
    assert body.index(f"  - {st} “Story” (story): done at {work[:10]}") < body.index(
        f"    - {tk} “Task” (task): done at {work[:10]}")  # a child under its parent


def finish(sprint):
    """Every item of the sprint fixture done (the epic too), committed: close may delete them."""
    repo, tk, st, bg, rv, ep = (sprint[k] for k in ("repo", "tk", "st", "bg", "rv", "ep"))
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    (repo / "src" / "c.txt").write_text("c\n", encoding="utf-8")
    commit(repo, "b and c", f"{tk}, {bg}")
    for iid in (tk, st, bg):
        assert b(repo, "done", iid)[0] == 0
    edit(repo, rv, checks=[{"run": PASS}])
    commit(repo, "state")
    assert b(repo, "done", rv)[0] == 0
    assert b(repo, "done", ep)[0] == 0
    commit(repo, "done all")


def item_files(repo):
    return {f.name: f.read_bytes() for f in (Path(repo) / backlog.REL_DIR).glob("*.json")}


def check_summary_changed_nothing(repo, before, out):
    """What close --summary must leave: every item file as it was, nothing named deleted or closed."""
    after = item_files(repo)
    assert after == before, f"close --summary changed {sorted(set(before) ^ set(after)) or 'an item file'}"
    assert "deleted " not in out and "closed " not in out, out


def test_backlog_close_summary_leaves_every_item_file_and_close_deletes(sprint):
    repo, sp = sprint["repo"], sprint["sp"]
    finish(sprint)
    before = item_files(repo)
    assert len(before) == 7
    code, out = b(repo, "close", sp, "--summary")
    assert code == 0 and out.startswith(f"delivered by {sp} “Sprint”:"), out
    check_summary_changed_nothing(repo, before, out)
    assert not subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True,
                              text=True).stdout  # nothing written, nothing deleted
    code, out = b(repo, "close", sp)  # plain close deletes them all
    assert code == 0 and "closed " in out, out
    assert item_files(repo) == {}


def test_backlog_close_summary_planted_failure_of_a_deleting_summary_is_caught(sprint):
    """The check is not vacuous: a summary run that deleted an item file (planted: one removed by hand after it), or
    printed the deletions, fails it."""
    repo, sp = sprint["repo"], sprint["sp"]
    finish(sprint)
    before = item_files(repo)
    code, out = b(repo, "close", sp, "--summary")
    (Path(repo) / backlog.REL_DIR / f"{sprint['tk']}.json").unlink()  # planted
    with pytest.raises(AssertionError, match=sprint["tk"]):
        check_summary_changed_nothing(repo, before, out)
    with pytest.raises(AssertionError):
        check_summary_changed_nothing(repo, item_files(repo), out + f"deleted {sprint['tk']}\n")  # planted


def test_backlog_close_summary_with_commit_is_refused_and_commits_nothing(sprint):
    repo, sp = sprint["repo"], sprint["sp"]
    finish(sprint)
    before = item_files(repo)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout
    code, out = b(repo, "close", sp, "--summary", "--commit")
    assert code == 1 and "only prints" in out, out
    check_summary_changed_nothing(repo, before, out)
    assert subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout == head


def test_close_summary_refuses_open_items_and_deletes_nothing(sprint):
    code, out = b(sprint["repo"], "close", sprint["sp"], "--summary")
    assert code == 1 and "not finished" in out and "delivered by" not in out
    assert item(sprint["repo"], "Sprint")["id"] == sprint["sp"]


def test_close_refuses_open_items(sprint):
    code, out = b(sprint["repo"], "close", sprint["sp"])
    assert code == 1 and "not finished" in out


def test_close_drops_relates_to(sprint):
    """An open item outside the sprint relates to one close deletes: close drops the link, and check still passes."""
    repo = sprint["repo"]
    b(repo, "new", "bug", "--title", "Later", "--severity", "S4", "--repro", argstr(is_file("src/z.txt")),
      "--goal", "z exists")
    later = item(repo, "Later")["id"]
    edit(repo, later, relates_to=[sprint["bg"], sprint["ep"]])
    b(repo, "new", "bug", "--title", "Only", "--severity", "S4", "--repro", argstr(is_file("src/y.txt")),
      "--goal", "y exists")
    only = item(repo, "Only")["id"]
    edit(repo, only, relates_to=[sprint["tk"]])
    for iid in (sprint["st"], sprint["tk"], sprint["bg"], sprint["rv"]):
        edit(repo, iid, status="dropped")
    code, out = b(repo, "close", sprint["sp"])
    assert code == 0, out
    assert item(repo, "Later")["relates_to"] == [sprint["ep"]]  # the epic stays open, so its link stays
    assert "relates_to" not in item(repo, "Only")
    assert later in out and only in out  # close names the items it edited
    code, out = b(repo, "check")
    assert code == 0 and "errors=0" in out, out


def test_close_drops_depends_on(sprint):
    """An open item outside the sprint depends on a done one close deletes: the dependency is satisfied, so close
    drops it (and the key once empty), check still passes and horizon does not count the item as waiting."""
    repo = sprint["repo"]
    b(repo, "new", "bug", "--title", "Later", "--severity", "S4", "--repro", argstr(is_file("src/z.txt")),
      "--goal", "z exists")
    later = item(repo, "Later")["id"]
    b(repo, "new", "bug", "--title", "Other", "--severity", "S4", "--repro", argstr(is_file("src/y.txt")),
      "--goal", "y exists")
    other = item(repo, "Other")["id"]
    edit(repo, later, depends_on=[sprint["bg"]], relates_to=[sprint["tk"]])
    edit(repo, other, depends_on=[sprint["bg"], later])
    edit(repo, sprint["bg"], status="done")
    for iid in (sprint["st"], sprint["tk"], sprint["rv"]):
        edit(repo, iid, status="dropped")
    code, out = b(repo, "close", sprint["sp"])
    assert code == 0, out
    assert "depends_on" not in item(repo, "Later") and "relates_to" not in item(repo, "Later")
    assert item(repo, "Other")["depends_on"] == [later]  # an open dependency stays
    assert out.count(f"from {later} ") == 1 and f"from {other} " in out  # one line per changed item
    code, out = b(repo, "check")
    assert code == 0 and "errors=0" in out, out
    code, out = b(repo, "horizon")
    assert code == 0 and sprint["bg"] not in out, out


# --- the ops row `sprint.close` (ST-hwua72bg): the sprint's facts, written before close deletes the items ---

@pytest.fixture
def ops_spool(tmp_path_factory, monkeypatch):
    """The ops capture of this test on: rows go to a spool of its own (never the clone's), and the guard that keeps a
    test run's rows out of the real spool is lifted. Returns the spool directory."""
    import ql_capture, ql_deliver
    spool = tmp_path_factory.mktemp("querylog") / "spool"
    monkeypatch.setattr(ql_capture, "spool_dir", lambda: spool)
    monkeypatch.setattr(ql_deliver, "inside_test", lambda: False)
    return spool


def spool_rows(spool, event):
    out = []
    for f in sorted(Path(spool).glob("*.jsonl")) if Path(spool).is_dir() else []:
        out += [r for r in (json.loads(ln) for ln in f.read_text(encoding="utf-8").splitlines())
                if r.get("surface") == "ops" and r.get("event") == event]
    return out


def planned_sprint(sprint, monkeypatch, age_s=5400):
    """The fixture's sprint committed `age_s` seconds ago, its items in the statuses a finished sprint has: the story,
    task and review done, the bug dropped with a provisional gate an operator confirmed."""
    repo = sprint["repo"]
    when = f"{int(time.time()) - age_s} +0000"
    monkeypatch.setenv("GIT_COMMITTER_DATE", when)
    monkeypatch.setenv("GIT_AUTHOR_DATE", when)
    commit(repo, "plan the sprint")
    monkeypatch.delenv("GIT_COMMITTER_DATE")
    monkeypatch.delenv("GIT_AUTHOR_DATE")
    for iid in (sprint["st"], sprint["tk"], sprint["rv"]):
        edit(repo, iid, status="done")
    edit(repo, sprint["bg"], status="dropped",
         gates=[{"id": "G1", "kind": "provisional", "question": "Name c?", "recommendation": "c.txt",
                 "answer": "c.txt", "by": "operator"},
                {"id": "G2", "kind": "provisional", "question": "Name d?", "recommendation": "d.txt",
                 "answer": "d.txt", "by": "agent"}])
    return repo


def close_in_process(repo, sprint_id, **kw):
    ns = argparse.Namespace(sprint=sprint_id, summary=False, commit=False, trailer=[], **kw)
    return bl_land.cmd_close(backlog.Backlog(repo), ns)


def plant_refused(spool, item_id, row_id):
    spool.mkdir(parents=True, exist_ok=True)
    row = {"id": row_id, "ts": "2026-10-01T10:00:00.000Z", "surface": "ops", "v": 1, "event": "done.refused",
           "item": item_id, "reasons": ["status"], "ms": 5}
    with open(spool / "tools-2026-10-01.jsonl", "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(row) + "\n")


def test_ops_sprint_close_row_counts_the_sprint_before_its_items_go(sprint, ops_spool, monkeypatch):
    repo, sp = planned_sprint(sprint, monkeypatch), sprint["sp"]
    plant_refused(ops_spool, sprint["tk"], "11111111-1111-4111-8111-111111111111")
    plant_refused(ops_spool, sprint["tk"], "11111111-1111-4111-8111-111111111111")  # the same row, read twice
    plant_refused(ops_spool, sprint["bg"], "22222222-2222-4222-8222-222222222222")
    plant_refused(ops_spool, "TK-aaaaaaaa", "33333333-3333-4333-8333-333333333333")  # an item of no sprint here
    assert close_in_process(repo, sp) == 0
    (row,) = spool_rows(ops_spool, "sprint.close")
    assert (row["sprint"], row["landed"], row["dropped"], row["bugs"], row["confirmed"], row["refused"]) == (
        sp, 3, 2, 1, 1, 2), row  # dropped: the bug and the goal research story the fixture drops
    assert 5400 * 1000 <= row["ms"] <= 5400 * 1000 + 120_000, row  # planned to closed, from the planning commit
    assert not (repo / backlog.REL_DIR / f"{sp}.json").exists()  # and the sprint is closed


def test_ops_sprint_close_row_is_written_while_the_items_still_exist(sprint, ops_spool, monkeypatch):
    import ql_deliver
    repo = planned_sprint(sprint, monkeypatch)
    seen = []
    real = ql_deliver.ops_row
    monkeypatch.setattr(ql_deliver, "ops_row", lambda event, **f: seen.append(
        (event, [(repo / backlog.REL_DIR / f"{i}.json").exists() for i in (sprint["sp"], sprint["tk"], sprint["st"])]))
        or real(event, **f))
    assert close_in_process(repo, sprint["sp"]) == 0
    assert seen == [("sprint.close", [True, True, True])], seen


def test_ops_sprint_close_row_summary_writes_none(sprint, ops_spool, monkeypatch):
    repo = planned_sprint(sprint, monkeypatch)
    ns = argparse.Namespace(sprint=sprint["sp"], summary=True, commit=False, trailer=[])
    assert bl_land.cmd_close(backlog.Backlog(repo), ns) == 0
    assert spool_rows(ops_spool, "sprint.close") == [] and (repo / backlog.REL_DIR / f"{sprint['sp']}.json").exists()


def test_ops_sprint_close_row_failing_log_never_fails_the_close(sprint, ops_spool, monkeypatch):
    import ql_deliver
    repo = planned_sprint(sprint, monkeypatch)

    def broken(event, **fields):
        raise OSError("the spool is read-only")
    monkeypatch.setattr(ql_deliver, "ops_row", broken)
    assert close_in_process(repo, sprint["sp"]) == 0
    assert not (repo / backlog.REL_DIR / f"{sprint['sp']}.json").exists()


def test_ops_sprint_close_row_logging_off_writes_none_and_closes(sprint, ops_spool, monkeypatch):
    import ql_capture
    repo = planned_sprint(sprint, monkeypatch)
    monkeypatch.setattr(ql_capture, "spool_dir", lambda: None)  # mode off, or the DISABLED marker
    assert close_in_process(repo, sprint["sp"]) == 0
    assert spool_rows(ops_spool, "sprint.close") == []


def test_ops_sprint_close_row_a_sprint_never_committed_writes_none_and_closes(sprint, ops_spool, monkeypatch):
    """The planning commit is the start of `ms`: a sprint file git never saw has none, so there is no row to write."""
    repo = sprint["repo"]
    for iid in (sprint["st"], sprint["tk"], sprint["bg"], sprint["rv"]):
        edit(repo, iid, status="dropped")
    assert bl_land.close_row(backlog.Backlog(repo), sprint["sp"], backlog.Backlog(repo).sprint_items(sprint["sp"])) is None
    assert close_in_process(repo, sprint["sp"]) == 0
    assert spool_rows(ops_spool, "sprint.close") == []


class TestDoneLane:
    """done reads the integration main as last fetched: a code-lane KB-Work commit must be its ancestor."""

    def worked(self, sprint, path="src/b.txt"):
        repo, tk = sprint["repo"], sprint["tk"]
        assert b(repo, "claim", tk, "--by", "agent-1")[0] == 0
        commit(repo, "claim", tk)
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text("b\n", encoding="utf-8")
        commit(repo, "write b", tk)
        return repo, tk

    def done(self, repo, tk):
        p = subprocess.run([sys.executable, TOOL, "--root", str(repo), "done", tk], cwd=repo, capture_output=True,
                           text=True, encoding="utf-8")
        return p.returncode, p.stdout + p.stderr

    def test_unmerged_code_commit_is_refused_naming_the_branch(self, sprint):
        repo, tk = self.worked(sprint)
        sh(repo, "git", "update-ref", "refs/remotes/origin/main", "HEAD~1")  # planted: the code commit is not on main
        code, out = self.done(repo, tk)
        assert code == 1 and "not on origin/main" in out and f"code/{tk}" in out, out

    def test_missing_integration_ref_is_refused(self, sprint):
        repo, tk = self.worked(sprint)
        code, out = self.done(repo, tk)
        assert code == 1 and "not fetched" in out, out

    def test_merged_code_commit_passes(self, sprint):
        repo, tk = self.worked(sprint)
        land(repo)
        code, out = self.done(repo, tk)
        assert code == 0, out

    def test_done_counts_descendant_commits_unmerged_task_code(self, sprint):
        """A story whose task's code commit is not on main is refused, naming the task's code branch."""
        repo, st, tk = story_with_touches(sprint)
        finish_task(repo, tk)
        before = subprocess.run(["git", "log", "--format=%H", "--grep", "write b", "-1"], cwd=repo,
                                capture_output=True, text=True, encoding="utf-8").stdout.strip()
        sh(repo, "git", "update-ref", "refs/remotes/origin/main", f"{before}~1")  # planted: task code not on main
        code, out = self.done(repo, st)
        assert code == 1 and "not on origin/main" in out and f"code/{tk}" in out, out

    def test_content_item_needs_no_integration_main(self, sprint):
        repo, tk = self.worked(sprint, "kb/public/x/a.md")
        edit(repo, tk, checks=[{"run": is_file("kb/public/x/a.md")}], touches=["kb/public/**"])
        commit(repo, "widen", tk)
        code, out = self.done(repo, tk)
        assert code == 0, out


STEP_STUB = """import os, sys
NAME = {name!r}
with open(os.environ["LAND_LOG"], "a", encoding="utf-8") as f:
    f.write(NAME + "\\n")
if os.environ.get("LAND_FAIL") == NAME:
    print(NAME + ": planted failure")
    sys.exit(1)
print(NAME + ": ok")
"""


# sync's stand-in: pushes by lane as kbgit.py sync --push does, the lane and the code/<id> branch from the real
# kg_lane.lane_plan (LAND_TOOLS: this _tools/ directory), the one helper sync and land name the branch with
SYNC_STUB = STEP_STUB.format(name="sync") + """import subprocess
def git(*a):
    return subprocess.run(["git", *a], capture_output=True, text=True, check=True).stdout
git("fetch", "-q", "origin")
if os.environ.get("LAND_NOPUSH"):  # planted: exits 0 without pushing, as a sync that gave up quietly would
    sys.exit(0)
if os.environ.get("LAND_REJECT"):  # planted: other sessions push main between sync's fetch and push, twice; each round
    import tempfile  # rebases HEAD onto the fetched main, as sync does, and its push is rejected
    for n in range(2):
        git("rebase", "-q", "refs/remotes/origin/main")
        other = os.path.join(tempfile.mkdtemp(), "other")
        git("clone", "-q", git("remote", "get-url", "origin").strip(), other)
        open(os.path.join(other, f"other-{n}.txt"), "w").write("x\\n")
        subprocess.run(["git", "-C", other, "add", "-A"], check=True)
        subprocess.run(["git", "-C", other, "-c", "user.name=o", "-c", "user.email=o@example.com", "commit", "-qm",
                        f"other {n}"], check=True)
        subprocess.run(["git", "-C", other, "push", "-q", "origin", "HEAD:main"], check=True)
        pushed = subprocess.run(["git", "push", "-q", "origin", "HEAD:refs/heads/main"], capture_output=True, text=True)
        assert pushed.returncode and "rejected" in pushed.stderr, pushed.stderr
        git("fetch", "-q", "origin")
    if os.environ.get("LAND_DROP_DONE"):  # planted: the rebase is said to have taken the done commit away
        git("reset", "-q", "--hard", "HEAD^")
    print("pushed: no (rejected twice)")
    sys.exit(1)
sys.path.insert(0, os.environ["LAND_TOOLS"])
import kg_lane
_, branch = kg_lane.lane_plan(os.getcwd(), "refs/remotes/origin/main", "HEAD")
git("push", "-q", "origin", "HEAD:refs/heads/" + (branch or "main"))
"""


def swaps_kbgit_kb(source):
    """Whether the source assigns kbgit.KB (the module global land once swapped around lane_plan)."""
    import ast
    for node in ast.walk(ast.parse(source)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AugAssign) else []
        for t in targets:
            for sub in ast.walk(t):
                if isinstance(sub, ast.Attribute) and sub.attr == "KB" and getattr(sub.value, "id", "") == "kbgit":
                    return True
    return False


def test_bl_split_land_does_not_swap_kb():
    """land names the branch through kg_lane.lane_plan(root, ...) and never sets kbgit.KB. Planted failure: the old swap."""
    assert not swaps_kbgit_kb(Path(bl_land.__file__).read_text(encoding="utf-8"))
    assert swaps_kbgit_kb("kb, kbgit.KB = kbgit.KB, str(root)\n")
    assert swaps_kbgit_kb("kbgit.KB = kb\n")
    assert not swaps_kbgit_kb("x = kbgit.KB\n")


class TestBacklogLand:
    """backlog.py land ID in a throwaway clone with a local bare remote; the heavy steps (stress_test.py, rag.py eval,
    the lint) and kbgit.py sync are stubs in the clone that log their names. A content item lands in one run; a code
    item's first run gates and opens code/<id> without moving main, and a re-run after the merge finishes it. Planted
    failures (a failing heavy step, a failing done check, a rebase conflict, a dirty tree) stop land at that step,
    named, with nothing after it run."""

    CO = "Co-Authored-By: A <a@example.com>"
    HEAVY = ["stress_test.py", "rag.py eval", "lint"]

    @staticmethod
    def out(cwd, *a):
        return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                              check=True).stdout

    @pytest.fixture
    def landing(self, sprint, monkeypatch, tmp_path_factory):
        repo, tk = sprint["repo"], sprint["tk"]
        stubs = {"_tools/stress_test.py": STEP_STUB.format(name="stress_test.py"),
                 "_tools/rag.py": STEP_STUB.format(name="rag.py eval"),
                 ".claude/skills/kb-verify/lint.py": STEP_STUB.format(name="lint"), "_tools/kbgit.py": SYNC_STUB}
        for rel, text in stubs.items():
            (repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (repo / rel).write_text(text, encoding="utf-8")
        commit(repo, "plan and step stubs")
        sh(repo, "git", "branch", "-M", "main")
        side = tmp_path_factory.mktemp("land")  # unique per test: tmp_path names cut at 30 characters can repeat
        remote = side / "remote.git"
        sh(repo, "git", "init", "-q", "--bare", str(remote))
        sh(repo, "git", "remote", "add", "origin", str(remote))
        sh(repo, "git", "push", "-q", "origin", "main")
        log = side / "land.log"
        monkeypatch.setenv("LAND_LOG", str(log))
        monkeypatch.setenv("LAND_TOOLS", TOOLS)
        monkeypatch.delenv("LAND_FAIL", raising=False)
        monkeypatch.delenv("KB_TESTS_FAST", raising=False)
        monkeypatch.delenv("KB_TEST_WORKERS", raising=False)
        monkeypatch.setenv("KB_HOST_LOCK_DIR", str(side / "locks"))
        sh(repo, "git", "checkout", "-q", "-b", f"work/{tk}")
        assert b(repo, "claim", tk, "--by", "worker", "--commit")[0] == 0
        return {"repo": repo, "tk": tk, "remote": remote, "log": log,
                "main": self.out(remote, "rev-parse", "main").strip()}

    def work(self, ld, files, check):
        repo, tk = ld["repo"], ld["tk"]
        edit(repo, tk, touches=["src/**", "kb/public/**", "_tools/b.py"], checks=[{"run": is_file(check)}])
        for rel in files:
            (repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (repo / rel).write_text("b\n", encoding="utf-8")
        commit(repo, "work", tk)

    @staticmethod
    def steps(ld):
        return ld["log"].read_text(encoding="utf-8").splitlines() if ld["log"].exists() else []

    def remote_item(self, ld, ref="main"):
        return json.loads(self.out(ld["remote"], "show", f"{ref}:{backlog.REL_DIR}/{ld['tk']}.json"))

    def land(self, ld):
        return b(ld["repo"], "land", ld["tk"], "--trailer", self.CO)

    def test_backlog_land_content_item_in_one_run(self, landing):
        ld = landing
        self.work(ld, ["kb/public/x/a.md"], "kb/public/x/a.md")
        sh(ld["repo"], "git", "checkout", "-q", "main")  # main moves on meanwhile: land rebases onto it
        (ld["repo"] / "kb" / "public").mkdir(parents=True, exist_ok=True)
        (ld["repo"] / "kb" / "public" / "y.md").write_text("y\n", encoding="utf-8")
        commit(ld["repo"], "other work")
        sh(ld["repo"], "git", "push", "-q", "origin", "main")
        code, out = self.land(ld)
        assert code == 0 and "landed" in out, out
        assert self.steps(ld) == ["sync"], out  # no _tools/ change: no heavy step
        assert self.remote_item(ld)["status"] == "done"
        msg = self.out(ld["remote"], "log", "-1", "--format=%B", "main")
        assert msg.startswith(f"chore(backlog): done {ld['tk']}") and self.CO in msg, msg
        assert "kb/public/y.md" in self.out(ld["remote"], "ls-tree", "-r", "--name-only", "main")

    def test_backlog_land_code_item_waits_for_its_merge_request_then_finishes(self, landing):
        ld = landing
        self.work(ld, ["_tools/b.py", "src/b.txt"], "src/b.txt")
        code, out = self.land(ld)
        assert code == 0 and f"code/{ld['tk']}" in out and "not done yet" in out, out
        assert self.steps(ld) == self.HEAVY + ["sync"], out
        assert self.out(ld["remote"], "rev-parse", "main").strip() == ld["main"]  # main did not move
        assert self.remote_item(ld, f"code/{ld['tk']}")["status"] == "doing"
        code, out = self.land(ld)  # before the merge: nothing re-run, nothing pushed
        assert code == 0 and "waits for its merge request" in out, out
        assert len(self.steps(ld)) == 4
        sh(ld["remote"], "git", "update-ref", "refs/heads/main", f"refs/heads/code/{ld['tk']}")  # the merge
        code, out = self.land(ld)
        assert code == 0 and "landed" in out, out
        assert self.steps(ld)[4:] == ["sync"], out  # the item file alone: the heavy steps ran once
        assert self.remote_item(ld)["status"] == "done"

    def test_backlog_land_stops_at_the_failing_step_and_names_it(self, landing, monkeypatch):
        ld = landing
        self.work(ld, ["_tools/b.py", "src/b.txt"], "src/b.txt")
        monkeypatch.setenv("LAND_FAIL", "rag.py eval")  # planted
        code, out = self.land(ld)
        assert code == 1 and "land stopped at step rag.py eval" in out and "planted failure" in out, out
        assert self.steps(ld) == self.HEAVY[:2], out  # neither the lint nor sync ran
        assert not self.out(ld["remote"], "branch", "--list", "code/*").strip()

    def test_backlog_land_stops_at_done(self, landing):
        ld = landing
        self.work(ld, ["kb/public/x/a.md"], "kb/public/x/missing.md")  # planted: the item's check fails
        code, out = self.land(ld)
        assert code == 1 and "land stopped at step done" in out, out
        assert self.steps(ld) == [] and self.out(ld["remote"], "rev-parse", "main").strip() == ld["main"]

    def test_backlog_land_stops_at_rebase_and_aborts_it(self, landing):
        ld = landing
        self.work(ld, ["kb/public/x/a.md"], "kb/public/x/a.md")
        sh(ld["repo"], "git", "checkout", "-q", "main")
        (ld["repo"] / "kb" / "public" / "x").mkdir(parents=True, exist_ok=True)
        (ld["repo"] / "kb" / "public" / "x" / "a.md").write_text("other\n", encoding="utf-8")  # planted conflict
        commit(ld["repo"], "conflicting work")
        sh(ld["repo"], "git", "push", "-q", "origin", "main")
        code, out = self.land(ld)
        assert code == 1 and "land stopped at step rebase" in out, out
        assert self.steps(ld) == [] and not self.out(ld["repo"], "status", "--porcelain")
        assert not (ld["repo"] / ".git" / "rebase-merge").exists()

    def test_backlog_land_refuses_a_dirty_tree(self, landing):
        ld = landing
        self.work(ld, ["kb/public/x/a.md"], "kb/public/x/a.md")
        (ld["repo"] / "src" / "a.txt").write_text("dirty\n", encoding="utf-8")  # planted
        code, out = self.land(ld)
        assert code == 1 and "land stopped at step clean tree" in out, out
        assert self.steps(ld) == []

    # land returns the checkout to where it started: `git rebase UPSTREAM BRANCH` switches to BRANCH, and an
    # orchestrator's later claim --commit must not land on work/<id> and ride into its code/<id> merge request. The
    # names differ in their first 30 characters: pytest cuts tmp_path's name there, and the fixture's remote sits
    # beside it, so two tests on one worker would share it.
    def head_ref(self, ld):
        p = subprocess.run(["git", "symbolic-ref", "-q", "HEAD"], cwd=ld["repo"], capture_output=True, text=True,
                           encoding="utf-8")
        return p.stdout.strip() or None

    def orchestrate(self, ld, files, check):
        """The worker's commit on work/<id>, then the orchestrator's own branch checked out, as land finds it."""
        self.work(ld, files, check)
        sh(ld["repo"], "git", "checkout", "-q", "-b", "orch", "main")

    def test_content_lane_land_returns_to_start_branch(self, landing):
        ld = landing
        self.orchestrate(ld, ["kb/public/x/a.md"], "kb/public/x/a.md")
        code, out = self.land(ld)
        assert code == 0 and "landed" in out, out
        assert self.head_ref(ld) == "refs/heads/orch", out
        assert self.remote_item(ld)["status"] == "done"
        assert not self.out(ld["repo"], "status", "--porcelain")

    def test_code_lane_land_returns_to_start_branch(self, landing):
        ld = landing
        self.orchestrate(ld, ["_tools/b.py", "src/b.txt"], "src/b.txt")
        code, out = self.land(ld)
        assert code == 0 and "not done yet" in out, out
        assert self.head_ref(ld) == "refs/heads/orch", out
        code, out = self.land(ld)  # the re-run that waits for the merge request
        assert code == 0 and "waits for its merge request" in out, out
        assert self.head_ref(ld) == "refs/heads/orch", out

    def test_stopped_land_returns_to_start_branch(self, landing, monkeypatch):
        ld = landing
        self.orchestrate(ld, ["_tools/b.py", "src/b.txt"], "src/b.txt")
        monkeypatch.setenv("LAND_FAIL", "lint")  # planted: a stop after the rebase switched to work/<id>
        code, out = self.land(ld)
        assert code == 1 and "land stopped at step lint" in out, out
        assert self.head_ref(ld) == "refs/heads/orch", out

    def test_conflicted_land_returns_to_start_branch(self, landing):
        ld = landing
        self.work(ld, ["kb/public/x/a.md"], "kb/public/x/a.md")
        sh(ld["repo"], "git", "checkout", "-q", "main")
        (ld["repo"] / "kb" / "public" / "x").mkdir(parents=True, exist_ok=True)
        (ld["repo"] / "kb" / "public" / "x" / "a.md").write_text("other\n", encoding="utf-8")  # planted conflict
        commit(ld["repo"], "conflicting work")
        sh(ld["repo"], "git", "push", "-q", "origin", "main")
        sh(ld["repo"], "git", "checkout", "-q", "-b", "orch")
        code, out = self.land(ld)
        assert code == 1 and "land stopped at step rebase" in out, out
        assert self.head_ref(ld) == "refs/heads/orch", out

    def test_detached_land_returns_to_start_branch(self, landing):
        ld = landing
        self.work(ld, ["kb/public/x/a.md"], "kb/public/x/a.md")
        sh(ld["repo"], "git", "checkout", "-q", "--detach", "main")
        start = self.out(ld["repo"], "rev-parse", "HEAD").strip()
        code, out = self.land(ld)
        assert code == 0 and "landed" in out, out
        assert self.head_ref(ld) is None and self.out(ld["repo"], "rev-parse", "HEAD").strip() == start, out

    # land names the code/<id> branch it waits on with kg_lane.lane_plan, as sync names the branch it opens: a story's
    # range that begins with a content commit of another item (a bug filed with new --commit) is recognised on a
    # re-run before the merge. Planted: the bug's own code commit comes first, so sync opens code/<bug>, a branch
    # land's old naming (the item's own id) never looked for.
    def story_range(self, ld, bug_code):
        repo, tk = ld["repo"], ld["tk"]
        code, out = b(repo, "new", "bug", "--title", "Found", "--severity", "S3", "--repro",
                      argstr(is_file("src/c.txt")), "--goal", "c exists", "--touch", "src/**", "--commit")
        assert code == 0, out
        bug = item(repo, "Found")["id"]
        if bug_code:
            (repo / "src" / "c.txt").write_text("c\n", encoding="utf-8")
            commit(repo, "fix the bug first", bug)
        (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
        commit(repo, "the story's work", tk)
        return bug

    def land_story_twice(self, ld, branch):
        land = ["land", self.story, "--branch", f"work/{ld['tk']}", "--trailer", self.CO]
        code, out = b(ld["repo"], *land)
        assert code == 0 and f"merge request of branch {branch}" in out and "not done yet" in out, out
        assert self.out(ld["remote"], "branch", "--list", branch).strip(), out
        code, out = b(ld["repo"], *land)  # before the merge: it finds the branch sync opened
        assert code == 0 and "waits for its merge request" in out and f"branch {branch} on origin" in out, out
        assert self.steps(ld) == ["sync"], out  # nothing pushed again

    def test_claim_first_land_names_sync_branch(self, landing, sprint):
        self.story = sprint["st"]
        self.story_range(landing, bug_code=False)
        self.land_story_twice(landing, f"code/{landing['tk']}")

    def test_bug_first_land_names_sync_branch(self, landing, sprint):
        self.story = sprint["st"]
        bug = self.story_range(landing, bug_code=True)
        self.land_story_twice(landing, f"code/{bug}")

    # a finished worker's worktree under .claude/worktrees/ that Claude Code left locked ("claude agent ...") and
    # clean is unlocked and removed by land's branch step; planted: one with uncommitted files, another lock reason,
    # or outside .claude/worktrees/ is refused, its lock and files kept
    AGENT_LOCK = "claude agent agent-a0 (pid 1 start Mon Jan  1 00:00:00 2026)"

    def worker_tree(self, ld, lock=AGENT_LOCK, where=None):
        """The landed branch checked out in a worker's worktree, locked with LOCK; the clone back on main."""
        repo, tk = ld["repo"], ld["tk"]
        self.work(ld, ["src/b.txt"], "src/b.txt")
        sh(repo, "git", "checkout", "-q", "main")
        (repo / ".git" / "info").mkdir(exist_ok=True)
        (repo / ".git" / "info" / "exclude").write_text(".claude/worktrees/\n", encoding="utf-8")
        path = where or repo / ".claude" / "worktrees" / "agent-a0"
        sh(repo, "git", "worktree", "add", "-q", str(path), f"work/{tk}")
        if lock is not None:
            sh(repo, "git", "worktree", "lock", "--reason", lock, str(path))
        return path

    def worktree_listed(self, ld, path):
        listed = self.out(ld["repo"], "worktree", "list", "--porcelain")
        return f"worktree {path.resolve()}" in listed or f"worktree {path}" in listed

    def test_clean_worker_worktree_unlocked_and_removed(self, landing):
        ld = landing
        path = self.worker_tree(ld)
        code, out = self.land(ld)
        assert code == 0 and "removed the finished worker's worktree" in out and "not done yet" in out, out
        assert not path.exists() and not self.worktree_listed(ld, path), out
        assert self.head_ref(ld) == "refs/heads/main", out

    def refused_kept(self, ld, path, why):
        code, out = self.land(ld)
        assert code == 1 and "land stopped at step branch" in out and why in out, out
        assert path.exists() and self.worktree_listed(ld, path), out
        return out

    def test_dirty_worker_worktree_unlocked_never(self, landing):
        ld = landing
        path = self.worker_tree(ld)
        (path / "src" / "b.txt").write_text("unsaved\n", encoding="utf-8")  # planted: uncommitted work
        self.refused_kept(ld, path, "uncommitted changes")
        assert (path / "src" / "b.txt").read_text(encoding="utf-8") == "unsaved\n"
        assert "locked claude agent" in self.out(ld["repo"], "worktree", "list", "--porcelain")

    def test_other_lock_worker_worktree_unlocked_never(self, landing):
        ld = landing
        path = self.worker_tree(ld, lock="on a removable disk")  # planted: not Claude Code's lock
        self.refused_kept(ld, path, "locked (on a removable disk)")

    def test_land_removes_clean_unlocked_worker_worktree(self, landing):
        ld = landing
        path = self.worker_tree(ld, lock=None)  # an agent-* worktree Claude Code did not lock: agents may not remove it
        code, out = self.land(ld)
        assert code == 0 and "removed the finished worker's worktree" in out and "it was not locked" in out, out
        assert not path.exists() and not self.worktree_listed(ld, path), out

    def test_land_keeps_unlocked_worktree_not_a_workers(self, landing):
        ld = landing
        path = self.worker_tree(ld, lock=None, where=ld["repo"] / ".claude" / "worktrees" / "runner-SP")  # planted
        self.refused_kept(ld, path, "not a worker's (agent-*)")

    def test_land_deletes_the_landed_work_branch(self, landing):
        ld = landing
        branch = f"work/{ld['tk']}"
        self.work(ld, ["kb/public/x/a.md"], "kb/public/x/a.md")
        sh(ld["repo"], "git", "checkout", "-q", "main")
        code, out = self.land(ld)
        assert code == 0 and "landed" in out and f"deleted the landed branch {branch}" in out, out
        assert not self.out(ld["repo"], "branch", "--list", branch).strip(), out
        assert self.head_ref(ld) == "refs/heads/main", out

    def test_land_deletes_the_removed_workers_agent_branch(self, landing):
        ld = landing
        repo, tk = ld["repo"], ld["tk"]
        self.work(ld, ["kb/public/x/a.md"], "kb/public/x/a.md")
        sh(repo, "git", "checkout", "-q", "main")
        sh(repo, "git", "branch", "worktree-agent-a0", "main")  # the Agent tool's branch of the worker's worktree
        (repo / ".git" / "info").mkdir(exist_ok=True)
        (repo / ".git" / "info" / "exclude").write_text(".claude/worktrees/\n", encoding="utf-8")
        path = repo / ".claude" / "worktrees" / "agent-a0"
        sh(repo, "git", "worktree", "add", "-q", str(path), f"work/{tk}")
        code, out = self.land(ld)
        assert code == 0 and "landed" in out and not path.exists(), out
        for branch in (f"work/{tk}", "worktree-agent-a0"):
            assert f"deleted the landed branch {branch}" in out, out
            assert not self.out(repo, "branch", "--list", branch).strip(), out

    def test_land_keeps_the_branch_it_runs_on(self, landing):
        ld = landing
        branch = f"work/{ld['tk']}"
        self.work(ld, ["kb/public/x/a.md"], "kb/public/x/a.md")  # land run from the landed branch itself
        code, out = self.land(ld)
        assert code == 0 and "landed" in out and "deleted the landed branch" not in out, out
        assert self.out(ld["repo"], "branch", "--list", branch).strip(), out

    def test_land_keeps_a_work_branch_with_commits_main_lacks(self, landing, capsys):
        ld = landing
        repo, branch = ld["repo"], f"work/{ld['tk']}"
        self.work(ld, ["kb/public/x/a.md"], "kb/public/x/a.md")  # planted: a commit no remote main holds
        sh(repo, "git", "checkout", "-q", "main")
        sh(repo, "git", "fetch", "-q", "origin")
        bl_land.delete_landed_branch(repo, branch, "refs/remotes/origin/main")
        assert "has commits" in capsys.readouterr().out
        assert self.out(repo, "branch", "--list", branch).strip()

    def test_outside_worker_worktree_unlocked_never(self, landing):
        ld = landing
        where = ld["repo"].parent / f"{ld['repo'].name}-wt"  # planted: not under .claude/worktrees/
        path = self.worker_tree(ld, where=where)
        self.refused_kept(ld, path, "not under .claude/worktrees/")

    # land run in a clone that is itself a linked worktree (the autopilot runner's): the clone is the toplevel of the
    # directory land runs in, so the workers under that clone's own .claude/worktrees are its workers, not the main
    # checkout's
    def linked_clone(self, ld):
        """A linked worktree of the landing repo on a branch at the item's work commit, ready to run land in."""
        repo, tk = ld["repo"], ld["tk"]
        self.work(ld, ["src/b.txt"], "src/b.txt")
        sh(repo, "git", "checkout", "-q", "main")
        clone = ld["remote"].parent / "linked-clone"
        sh(repo, "git", "worktree", "add", "-q", "-b", "runner", str(clone), f"work/{tk}")
        (repo / ".git" / "info").mkdir(exist_ok=True)
        (repo / ".git" / "info" / "exclude").write_text(".claude/worktrees/\n", encoding="utf-8")
        return clone

    def linked_worker(self, ld, clone, name="agent-a0", lock=AGENT_LOCK, branch=None):
        path = clone / ".claude" / "worktrees" / name
        sh(ld["repo"], "git", "worktree", "add", "-q", str(path), branch or f"work/{ld['tk']}")
        if lock is not None:
            sh(ld["repo"], "git", "worktree", "lock", "--reason", lock, str(path))
        return path

    def land_in(self, ld, clone):
        return b(clone, "land", ld["tk"], "--trailer", self.CO)

    def test_land_removes_worker_worktree_of_a_linked_clone(self, landing):
        ld = landing
        clone = self.linked_clone(ld)
        sh(clone, "git", "checkout", "-q", "--detach")
        path = self.linked_worker(ld, clone)
        code, out = self.land_in(ld, clone)
        assert code == 0 and "removed the finished worker's worktree" in out, out
        assert not path.exists() and not self.worktree_listed(ld, path), out

    def test_land_removes_worker_worktree_of_a_linked_clone_named_by_item_id(self, landing):
        ld = landing
        clone = self.linked_clone(ld)
        sh(clone, "git", "checkout", "-q", "--detach")
        path = self.linked_worker(ld, clone, name=ld["tk"], lock=None)
        code, out = self.land_in(ld, clone)
        assert code == 0 and "removed the finished worker's worktree" in out and "it was not locked" in out, out
        assert not path.exists() and not self.worktree_listed(ld, path), out

    def test_land_removes_worker_worktree_of_a_linked_clone_keeps_one_under_the_main_checkout(self, landing):
        ld = landing
        clone = self.linked_clone(ld)
        sh(clone, "git", "checkout", "-q", "--detach")
        path = self.linked_worker(ld, ld["repo"])  # planted: under the main checkout, land runs in another clone
        code, out = self.land_in(ld, clone)
        assert code == 1 and "land stopped at step branch" in out and "not under .claude/worktrees/" in out, out
        assert path.exists() and self.worktree_listed(ld, path), out

    def test_land_removes_worker_worktree_of_a_linked_clone_keeps_a_dirty_one(self, landing):
        ld = landing
        clone = self.linked_clone(ld)
        sh(clone, "git", "checkout", "-q", "--detach")
        path = self.linked_worker(ld, clone)
        (path / "src" / "b.txt").write_text("unsaved\n", encoding="utf-8")  # planted: uncommitted work
        code, out = self.land_in(ld, clone)
        assert code == 1 and "land stopped at step branch" in out and "uncommitted changes" in out, out
        assert path.exists() and (path / "src" / "b.txt").read_text(encoding="utf-8") == "unsaved\n", out

    def test_land_removes_worker_worktree_of_a_linked_clone_keeps_another_items_branch(self, landing):
        ld = landing
        clone = self.linked_clone(ld)
        sh(ld["repo"], "git", "branch", "work/ST-other000", f"work/{ld['tk']}")
        path = self.linked_worker(ld, clone, branch="work/ST-other000")  # planted: another item's worker
        why = bl_land.release_worker_worktree(clone, path, self.AGENT_LOCK, branch=f"work/{ld['tk']}")
        assert why and "not on work/" in why and path.exists() and self.worktree_listed(ld, path), why

    # a worker that left a background command running in its worktree: land refuses to remove the worktree from
    # under it, naming the pid; planted: a process check blind to it removes the worktree, which the check catches.
    # The test names differ in their first 30 characters (pytest's tmp_path cut, beside which the remote sits).
    @staticmethod
    def sleeper(path):
        if bl_land.live_processes(path)[0] is None:
            pytest.skip(f"no process check on this host: {bl_land.live_processes(path)[1]}")
        return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"], cwd=path)

    @staticmethod
    def check_refused_naming(code, out, pid):
        assert code == 1 and "land stopped at step branch" in out and f"pid {pid} (" in out, out
        assert "a process still runs there" in out, out

    def test_pid_named_land_refuses_live_worker_process(self, landing):
        ld = landing
        path = self.worker_tree(ld)
        child = self.sleeper(path)
        try:
            code, out = self.land(ld)
            self.check_refused_naming(code, out, child.pid)
            assert path.exists() and self.worktree_listed(ld, path), out
            assert "locked claude agent" in self.out(ld["repo"], "worktree", "list", "--porcelain")
        finally:
            child.kill()
            child.wait()
        code, out = self.land(ld)  # the process gone: the clean worktree is removed as before
        assert code == 0 and "removed the finished worker's worktree" in out, out

    def test_planted_blind_land_refuses_live_worker_process(self, landing, monkeypatch, capsys):
        ld = landing
        path = self.worker_tree(ld)
        child = self.sleeper(path)
        try:
            monkeypatch.setattr(bl_land, "live_processes", lambda p: ([], None))  # planted: sees nothing
            other = bl_land.checked_out_elsewhere(ld["repo"], f"work/{ld['tk']}")
            why = bl_land.release_worker_worktree(ld["repo"], *other)
            with pytest.raises(AssertionError):
                self.check_refused_naming(1 if why else 0, f"land stopped at step branch: {why}", child.pid)
        finally:
            child.kill()
            child.wait()

    def test_unchecked_host_land_refuses_live_worker_process(self, landing, monkeypatch, capsys):
        """A host with no way to list processes does not refuse: land says it could not check and goes on."""
        ld = landing
        path = self.worker_tree(ld)
        monkeypatch.setattr(bl_land, "live_processes", lambda p: (None, "no /proc and no lsof on this host"))
        other = bl_land.checked_out_elsewhere(ld["repo"], f"work/{ld['tk']}")
        assert bl_land.release_worker_worktree(ld["repo"], *other) is None
        out = capsys.readouterr().out
        assert "could not check" in out and "no lsof" in out and not path.exists(), out

    def test_backlog_land_refuses_kb_trailers(self, landing):
        code, out = b(landing["repo"], "land", landing["tk"], "--trailer", f"KB-Work: {landing['tk']}")
        assert code == 1 and "--trailer" in out, out

    # a re-run of land while the code/<id> request waits reads the request on GitLab: open, mergeable, auto-merge set
    # and a skipped pipeline is stuck (auto-merge never fires), and land names the command that merges it
    MR_SAMPLE = Path(TOOLS) / "fixtures" / "forge_mr" / "gitlab-merged-skipped-pipeline.json"
    FORGE_URL = "https://gitlab.corp.example.com/team/kb.git"
    MERGE_CMD = "python3 _tools/backlog.py merge "  # + the item's id: agents merge only their own code/<id>, never glab

    @classmethod
    def recorded_mr(cls):
        return json.loads(cls.MR_SAMPLE.read_text(encoding="utf-8"))["reply"]

    @classmethod
    def open_mr(cls, pipeline="skipped", **change):
        """The recorded request as it was while it waited: open and mergeable, its pipeline in state PIPELINE."""
        mr = cls.recorded_mr()
        mr.update(state="opened", detailed_merge_status="mergeable", merged_at=None, merged_by=None)
        mr["head_pipeline"]["status"] = pipeline
        mr.update(change)
        return mr

    def gitlab(self, monkeypatch, mr, signed_in=True, down=False):
        """origin (as land reads its url) is a GitLab project whose glab answers MR (None: no open request) for the
        list of open requests and the single request; DOWN: every glab api call fails as a network failure does."""
        calls, real = [], backlog.run

        def fake(argv, cwd=None):
            if argv[:3] == ["git", "remote", "get-url"]:
                return 0, self.FORGE_URL + "\n", ""
            if argv[0] != "glab":
                return real(argv, cwd=cwd)
            calls.append(argv)
            if argv[1] == "auth":
                return (0, "", "") if signed_in else (1, "", "not logged in")
            if down:
                return 127, "", "dial tcp: lookup gitlab.corp.example.com: no such host"
            if "/merge_requests?" in argv[-1]:
                return 0, json.dumps([{"iid": mr["iid"]}] if mr else []), ""
            if mr and argv[-1].endswith(f"/merge_requests/{mr['iid']}"):
                return 0, json.dumps(mr), ""
            return 1, "", "404 Not Found"

        monkeypatch.setattr(bl_land, "run", fake)
        return calls

    def rerun(self, ld, capsys):
        """The code item's first land (it opens code/<id>), then the re-run in this process, where `run` is faked."""
        self.work(ld, ["_tools/b.py", "src/b.txt"], "src/b.txt")
        code, out = self.land(ld)
        assert code == 0 and "not done yet" in out, out
        capsys.readouterr()
        code = backlog.main(["--root", str(ld["repo"]), "land", ld["tk"], "--trailer", self.CO])
        out = capsys.readouterr().out
        assert code == 0 and "waits for its merge request" in out, out
        assert len(self.steps(ld)) == 4, out  # nothing re-run, nothing pushed
        return out

    def test_land_stuck_auto_merge_is_reported(self, landing, monkeypatch, capsys):
        calls = self.gitlab(monkeypatch, self.open_mr())
        out = self.rerun(landing, capsys)
        assert "!103" in out and "pipeline was skipped" in out and self.MERGE_CMD in out, out
        listed = [c[-1] for c in calls if "/merge_requests?" in c[-1]]
        assert listed and "state=opened" in listed[0] and f"source_branch=code%2F{landing['tk']}" in listed[0]

    def test_land_stuck_auto_merge_not_reported_while_its_pipeline_runs(self, landing, monkeypatch, capsys):
        self.gitlab(monkeypatch, self.open_mr(pipeline="running"))
        out = self.rerun(landing, capsys)
        assert "glab mr merge" not in out, out

    @pytest.mark.parametrize("mr, forge", [
        ({"pipeline": "running"}, {}),
        ({"pipeline": "pending"}, {}),
        ({"detailed_merge_status": "conflict"}, {}),  # not mergeable
        ({"detailed_merge_status": "not_approved"}, {}),
        ({"merge_when_pipeline_succeeds": False}, {}),  # no auto-merge: nothing waits to fire
        ({"state": "closed"}, {}),
        ({"head_pipeline": None}, {}),
        (None, {}),  # no open request
        ({}, {"signed_in": False}),  # glab not signed in: nothing extra
        ({}, {"down": True}),  # a network failure: nothing extra
    ])
    def test_land_stuck_auto_merge_not_reported(self, tmp_path, monkeypatch, mr, forge):
        self.gitlab(monkeypatch, None if mr is None else self.open_mr(**mr), **forge)
        assert bl_land.stuck_merge_request(tmp_path, "origin", "code/TK-aaaaaaaa") is None

    def test_land_stuck_auto_merge_reports_the_planted_stuck_request(self, tmp_path, monkeypatch):
        self.gitlab(monkeypatch, self.open_mr())
        note = bl_land.stuck_merge_request(tmp_path, "origin", "code/TK-aaaaaaaa")
        assert note and self.MERGE_CMD + "TK-aaaaaaaa" in note and "/merge_requests/103" in note, note

    def test_land_stuck_auto_merge_reads_the_recorded_sample(self):
        mr = self.recorded_mr()  # merged by hand after its skipped pipeline left auto-merge waiting
        assert mr["merge_when_pipeline_succeeds"] is True and mr["head_pipeline"]["status"] == "skipped"
        assert not bl_land.mr_stuck(mr)  # merged: nothing to report
        assert bl_land.mr_stuck(self.open_mr())  # the same reply while it was open and mergeable
        legacy = self.open_mr()
        del legacy["detailed_merge_status"]  # a GitLab without the detailed field: merge_status decides
        assert bl_land.mr_stuck(legacy)
        assert not bl_land.mr_stuck(dict(legacy, merge_status="cannot_be_merged"))

    # land verifies what it reports: its done commit is on the integration main after sync --push, fetched again; a
    # sync that exits 0 without pushing (planted: LAND_NOPUSH) must not end in "landed"
    def test_land_verifies_done_commit_on_integration_main(self, landing, monkeypatch):
        ld = landing
        self.orchestrate(ld, ["kb/public/x/a.md"], "kb/public/x/a.md")
        monkeypatch.setenv("LAND_NOPUSH", "1")
        code, out = self.land(ld)
        assert code == 1 and "land stopped at step verify" in out and "landed" not in out, out
        assert self.out(ld["remote"], "rev-parse", "main").strip() == ld["main"]  # nothing reached main
        assert self.head_ref(ld) == "refs/heads/orch", out
        monkeypatch.delenv("LAND_NOPUSH")
        code, out = self.land(ld)  # the run after it: the branch kept its done commit, and the push goes through
        assert code == 0 and self.remote_item(ld)["status"] == "done", out
        assert self.out(ld["remote"], "log", "--format=%s", "main").count(f"chore(backlog): done {ld['tk']}") == 1

    # a worker branch cut before the claim, the claim on the orchestrator's branch and never pushed: land puts it
    # under the worker's commit, so what it pushes holds claim, then work (src/ is the code lane: the branch is
    # code/<id>, where sync sends it, and a re-run before the merge carries nothing twice)
    def test_land_carries_claim_commit_under_worker_commit(self, landing):
        ld = landing
        repo, tk = ld["repo"], ld["tk"]
        sh(repo, "git", "checkout", "-q", "-b", "orch")  # the claim commit made on the orchestrator's branch
        sh(repo, "git", "checkout", "-q", f"work/{tk}")
        sh(repo, "git", "reset", "-q", "--hard", "main")  # the worker's branch was cut before it
        (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
        commit(repo, "work", tk)
        sh(repo, "git", "checkout", "-q", "orch")
        code, out = self.land(ld)
        assert code == 0 and "carry the claim commit" in out and "not done yet" in out, out
        branch = f"code/{tk}"
        subjects = self.out(ld["remote"], "log", "--reverse", "--format=%s", f"main..{branch}").splitlines()
        assert subjects == [f'chore(backlog): claim {tk} "Task"', "work"], subjects
        assert self.remote_item(ld, branch)["status"] == "doing"
        assert self.head_ref(ld) == "refs/heads/orch"
        code, out = self.land(ld)  # again, before the merge: the claim is on the branch now, nothing is carried
        assert code == 0 and "waits for its merge request" in out and "carry" not in out, out
        assert self.out(ld["remote"], "log", "--format=%s", f"main..{branch}").count("claim") == 1

    # a push rejected twice ends the land; the done commit is not lost with it: the run after it finds it (planted:
    # the failed sync took it off the branch) and does not run the item's checks again
    def rejected_push_land(self, ld, monkeypatch, drop):
        self.orchestrate(ld, ["kb/public/x/a.md"], "kb/public/x/a.md")
        monkeypatch.setenv("LAND_REJECT", "1")
        if drop:
            monkeypatch.setenv("LAND_DROP_DONE", "1")
        code, out = self.land(ld)
        assert code == 1 and "rejected twice" in out and "landed" not in out, out
        assert self.head_ref(ld) == "refs/heads/orch", out
        monkeypatch.delenv("LAND_REJECT")
        code, out = self.land(ld)
        assert code == 0 and "landed" in out and "land: done --commit" not in out and "ok   exit=" not in out, out
        assert self.remote_item(ld)["status"] == "done"
        assert self.out(ld["remote"], "log", "--format=%s", "main").count(f"chore(backlog): done {ld['tk']}") == 1
        assert not self.out(ld["repo"], "for-each-ref", "refs/land")  # the kept commit goes once it is verified
        return out

    def test_land_keeps_done_commit_after_rejected_push(self, landing, monkeypatch):
        out = self.rejected_push_land(landing, monkeypatch, drop=True)
        assert "has its done commit from the last run" in out, out

    def test_branch_land_keeps_done_commit_after_rejected_push(self, landing, monkeypatch):
        """The usual case, which held before: the rebased done commit is still on the branch."""
        out = self.rejected_push_land(landing, monkeypatch, drop=False)
        assert "done already" in out, out

    def test_land_stuck_auto_merge_skips_a_local_remote(self, landing, monkeypatch):
        """The landing fixture's origin is a bare repository on disk: no forge to ask, no glab call."""
        real, calls = bl_land.run, []
        monkeypatch.setattr(bl_land, "run", lambda argv, cwd=None: calls.append(argv) or real(argv, cwd=cwd))
        assert bl_land.stuck_merge_request(landing["repo"], "origin", f"code/{landing['tk']}") is None
        assert [c[:3] for c in calls] == [["git", "remote", "get-url"]], calls
