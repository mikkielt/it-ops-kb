"""An item check's program is checked before it runs where nothing reviews it: a headless run's done and land
(KB_HEADLESS_RUNNER) and intake's drift detector, which runs committed checks in every session's SessionStart hook.
There a check runs only as python3 on a _tools/ script, never kbgit.py publish, bridge, install-hooks or hook, nor a
shell, git or glab; drift also refuses python3 -c. An operator session's done keeps running the read-only sh and git
repros items carry (kb/_self/backlog.md)."""
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


def test_check_program_allowlist_headless_run_check_refuses_without_running(tmp_path, monkeypatch):
    marker = tmp_path / "ran"
    check = {"run": ["sh", "-c", f"touch {marker}"]}
    monkeypatch.setenv(bl_intake.HEADLESS_ENV, "1")
    ok, code, out = bl_land.run_check(str(tmp_path), check)
    assert not ok and code is None and "refused in a headless run" in out and not marker.exists()
    monkeypatch.delenv(bl_intake.HEADLESS_ENV)  # the planted contrast: an operator session runs the same repro
    ok, code, out = bl_land.run_check(str(tmp_path), check)
    assert ok and code == 0 and marker.exists()


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
    assert {"BG-aaaaaaaa", "BG-bbbbbbbb"} <= set(drift.heavy)
