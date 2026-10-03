"""A kb-worker started in a hand-made worktree is counted for its item (`python3 _tools/tests.py -k worker_capture`).
  worker_usage_routing_by_worktree_path  a subagent whose working directory stays its session's (the Agent tool gives it
                    no directory of its own) and whose shell commands run in `<clone>/.claude/worktrees/<id>` is
                    routed to that item by `kbusage.prompt_usage`, for every kind of id and either path separator; a
                    worker that names no worktree, two items' or a directory only like one stays in `sub`; a work
                    branch in `gitBranch` still wins; no path reaches the record
  worker_capture_definition  `.claude/agents/kb-worker.md` names the requirement
"""
import json
from pathlib import Path

import pytest

import kbusage
from conftest import TOOLS

KINDS = ("EP", "ST", "TK", "SB", "BG", "SP")
A, B = "TK-aaaaaaaa", "TK-bbbbbbbb"


def jsonl(path, objs):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(o) + "\n" for o in objs), encoding="utf-8", newline="\n")


def worker_transcript(tmp_path, commands, branch="main"):
    """A main transcript of one prompt with one kb-worker subagent transcript: one request for each of `commands`
    (a Bash tool use), every record on `branch`, the working directory the session's; the main file's path."""
    main = tmp_path / "t.jsonl"
    jsonl(main, [
        {"type": "user", "promptId": "p0", "message": {"content": "x"}, "gitBranch": "main"},
        {"type": "assistant", "requestId": "q0", "gitBranch": "main", "message": {
            "model": "claude-sonnet-5", "usage": {"input_tokens": 10, "output_tokens": 1}, "content": []}}])
    recs = [{"type": "user", "promptId": "p0", "isSidechain": True, "message": {"content": "x"}}]
    for i, cmd in enumerate(commands):
        recs.append({"type": "assistant", "requestId": f"w{i}", "isSidechain": True, "gitBranch": branch,
                     "cwd": "/clone", "message": {
                         "model": "claude-sonnet-5", "usage": {"input_tokens": 2, "output_tokens": 7},
                         "content": [{"type": "text", "text": "ok"},
                                     {"type": "tool_use", "id": f"t{i}", "name": "Bash", "input": {"command": cmd}}]}})
    d = tmp_path / "t" / "subagents"
    jsonl(d / "agent-a1.jsonl", recs)
    (d / "agent-a1.meta.json").write_text(json.dumps({"agentType": "kb-worker"}), encoding="utf-8")
    return str(main)


def counts(n):
    return {"claude-sonnet-5": {"requests": n, "in": 2 * n, "cw": 0, "cw1h": 0, "cr": 0, "out": 7 * n}}


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("n", [1, 2, 3, 5, 6])
@pytest.mark.parametrize("form", ["git -C {p} status", "python3 {p}/_tools/check.py", "cd {p} && git log -1",
                                  "git -C {p}", "ls {p}/kb"])
def test_worker_usage_routing_by_worktree_path(tmp_path, kind, n, form):
    """Planted scenario: the worker's records name `main` (its directory is the session's) and its n commands run in
    the hand-made worktree of the item: the counts are the item's, not the session's."""
    item = f"{kind}-abcdefg{'234567'[n - 1]}"
    cmd = form.format(p=f"/clone/.claude/worktrees/{item}")
    rec = kbusage.prompt_usage(worker_transcript(tmp_path, [cmd] * n), "p0")
    assert rec["routed"] == {item: {"kb-worker": counts(n)}} and "sub" not in rec, rec
    text = json.dumps(rec)
    assert "worktrees" not in text and "/clone" not in text


def test_worker_capture_windows_separators(tmp_path):
    cmd = "py -3 C:\\clone\\.claude\\worktrees\\" + A + "\\_tools\\check.py"
    rec = kbusage.prompt_usage(worker_transcript(tmp_path, [cmd]), "p0")
    assert rec["routed"] == {A: {"kb-worker": counts(1)}}


@pytest.mark.parametrize("commands", [
    [], ["git status"], ["ls /clone/.claude/worktrees"], ["ls /clone/.claude/worktrees/runner-" + A],
    ["git -C /clone/.claude/worktrees/" + A + "x status"], ["git -C /clone/.claude/worktrees/" + A + "-x status"],
    ["git -C /clone/.claude/worktrees/TK-aaaaaaa1 status"], ["git -C /clone/.claude/worktrees/XX-aaaaaaaa status"],
    ["git -C /clone/.claude/worktrees/" + A + " status", "git -C /clone/.claude/worktrees/" + B + " status"],
    ["git -C /clone/.claude/worktrees/" + A + " diff /clone/.claude/worktrees/" + B + "/x"]])
def test_worker_capture_not_a_worker_worktree(tmp_path, commands):
    """No worktree named, two items' worktrees or a name only like one: the counts stay in `sub`."""
    rec = kbusage.prompt_usage(worker_transcript(tmp_path, commands or ["true"]), "p0")
    assert rec["sub"] == {"kb-worker": counts(len(commands) or 1)} and "routed" not in rec, rec


def test_worker_capture_work_branch_wins(tmp_path):
    """A record that names a work branch decides, whatever the commands name."""
    cmd = "git -C /clone/.claude/worktrees/" + B + " status"
    rec = kbusage.prompt_usage(worker_transcript(tmp_path, [cmd], branch="work/" + A), "p0")
    assert rec["routed"] == {A: {"kb-worker": counts(1)}}


def test_worker_capture_definition_names_the_requirement():
    text = (Path(TOOLS).parent / ".claude" / "agents" / "kb-worker.md").read_text(encoding="utf-8")
    assert "worker_usage_routing_by_worktree_path" in text
