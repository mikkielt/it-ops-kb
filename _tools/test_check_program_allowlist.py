"""An item check's program is checked before it runs where nothing reviews it: intake's drift detector, which runs
committed checks in every session's SessionStart hook. There a check runs only as python3 on one of drift's read-only
_tools/ scripts, never kbgit.py publish, bridge, install-hooks or hook, nor a shell, git, glab or python3 -c. The
form an open item's repro and checks may take (check_program_refusal with inline) also admits python3 -c. A session's
done keeps running the read-only sh and git repros items carry (kb/_self/backlog.md)."""
import sys

import pytest

import bl_intake, bl_land

REFUSED = [["sh", "-c", "exit 0"], ["git", "push", "--no-verify", "origin", "HEAD:main"],
           ["python3", "_tools/kbgit.py", "publish"], ["python3", "_tools/kbgit.py", "bridge", "x", "--push"],
           ["glab", "mr", "merge", "1"], ["python3", "/tmp/elsewhere.py"], ["python3", "_tools/../x.py"], []]
ALLOWED = [["python3", "_tools/tests.py", "-n", "2", "-k", "x"], ["python", "_tools/check.py"],
           ["python3", "_tools/kbgit.py", "sync", "--dry-run"], [sys.executable, "_tools/rag.py", "eval"]]


@pytest.mark.parametrize("argv", REFUSED, ids=[" ".join(a)[:40] or "empty" for a in REFUSED])
def test_check_program_allowlist_refuses(argv):
    assert bl_intake.check_program_refusal(argv)
    assert bl_intake.check_program_refusal(argv, inline=False)


@pytest.mark.parametrize("argv", ALLOWED, ids=[" ".join(a)[-40:] for a in ALLOWED])
def test_check_program_allowlist_allows(argv):
    assert bl_intake.check_program_refusal(argv) is None


def test_check_program_allowlist_inline_python_only_outside_drift():
    assert bl_intake.check_program_refusal(["python3", "-c", "pass"]) is None
    assert "inline" in bl_intake.check_program_refusal(["python3", "-c", "pass"], inline=False)


def test_check_program_allowlist_done_runs_a_shell_repro(tmp_path):
    """done's run_check is not drift: it runs the sh repro the allowlist refuses."""
    marker = tmp_path / "ran"
    check = {"run": ["sh", "-c", f"touch {marker}"]}
    assert bl_intake.check_program_refusal(check["run"])
    ok, code, out = bl_land.run_check(str(tmp_path), check)
    assert ok and code == 0 and marker.exists()


@pytest.mark.parametrize("argv", [
    ["python3", "_tools/kbgit.py", "sync", "--push", "--branch", "x"], ["python3", "_tools/kbgit.py", "sync", "--remote", "pub"],
    ["python3", "_tools/autopilot.py", "runner", "start", "SP-aaaaaaaa"], ["python3", "_tools/backlog.py", "answer", "x"],
    ["python3", "_tools/querylog.py", "apply", "--push"]], ids=lambda a: " ".join(a[1:3]))
def test_drift_allowlist_read_only_refuses_writers(argv):
    """Drift runs only read-only forms: a committed sync --push, runner start or backlog writer never runs there."""
    assert bl_intake.check_program_refusal(argv, inline=False)


@pytest.mark.parametrize("argv", [
    ["python3", "_tools/tests.py", "-n", "2", "-k", "x"], ["python3", "_tools/rag.py", "eval"],
    ["python3", "_tools/check.py"], ["python3", "_tools/selfdoc.py", "check"],
    ["python3", ".claude/skills/kb-verify/lint.py"]], ids=lambda a: a[1])
def test_drift_allowlist_read_only_runs_readers(argv):
    assert bl_intake.check_program_refusal(argv, inline=False) is None


@pytest.mark.parametrize("program", ["kb/x/python3", "./python3", "/tmp/python", "bin/python3"])
def test_drift_allowlist_read_only_program_is_exactly_python(program):
    """A file named python3 is not the interpreter: refused everywhere, drift or not."""
    assert bl_intake.check_program_refusal([program, "_tools/rag.py", "eval"])
    assert bl_intake.check_program_refusal([program, "_tools/rag.py", "eval"], inline=False)


def test_check_program_allowlist_drift_refuses_inline_by_default():
    assert bl_intake.DRIFT_ALLOWS_INLINE is False


def test_check_program_allowlist_drift_leaves_a_refused_check_unchecked(tmp_path, monkeypatch):
    """Drift never runs a shell or publish check; the item is counted unchecked, as a heavy one is."""
    ran = []
    monkeypatch.setattr(bl_intake, "check_result", lambda root, c, t: ran.append(c) or "pass")
    monkeypatch.setattr(bl_intake, "eligible", lambda root, items: [
        ("BG-aaaaaaaa", [{"run": ["sh", "-c", "git push"]}]),
        ("BG-bbbbbbbb", [{"run": ["python3", "-c", "import subprocess"]}]),
        ("BG-cccccccc", [{"run": ["python3", "_tools/check.py"]}])])
    monkeypatch.setattr(bl_intake, "rotation", lambda root: 0)
    monkeypatch.setattr(bl_intake, "read_cursor", lambda root: None)
    monkeypatch.setattr(bl_intake, "write_cursor", lambda root, last: None, raising=False)
    drift = bl_intake.Drift(stale=[])
    bl_intake.passing_open(str(tmp_path), {}, 30, drift, 60)
    assert [c["run"] for c in ran] == [["python3", "_tools/check.py"]]
    assert {"BG-aaaaaaaa", "BG-bbbbbbbb"} <= set(drift.refused) and not drift.heavy
