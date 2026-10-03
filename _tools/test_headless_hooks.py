"""A headless runner's SessionStart hooks (`intake --file --hook`, `red-pipeline --hook`) file nothing.

`autopilot.py runner start` sets KB_HEADLESS_RUNNER in the child it runs in a worktree; a draft the child's hooks
wrote there would leave the worktree dirty and its next restart refused. Planted failures: with the variable set a
planted finding is not filed and the red-pipeline read never runs; with it unset the same hook files the finding
and runs the read (so each test fails without the guard); `intake --file` run by hand is not affected.
"""
import json
from pathlib import Path

import pytest

import backlog
import bl_intake
import kbpublic
from bl_intake import Candidate
from conftest import Repo


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(bl_intake, "DETECTORS", {})
    monkeypatch.delenv("KB_TESTS_FAST", raising=False)
    monkeypatch.delenv("KB_TEST_WORKERS", raising=False)
    monkeypatch.setenv("KB_HOST_LOCK_DIR", str(tmp_path / "locks"))


@pytest.fixture
def clone(tmp_path):
    root = tmp_path / "clone"
    root.mkdir()
    repo = Repo(root)
    repo.git("init", "-q", "-b", "main")
    (root / "a.txt").write_text("a\n", encoding="utf-8")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "init")
    bl_intake.detector("docs")(lambda r: [Candidate(kind="bug", title="A doc names a gone file",
                                                    goal="The doc names no gone file.", key="stale-doc:a", severity="S3")])
    return root


def drafts(root):
    d = Path(root) / backlog.REL_DIR
    return sorted(d.glob("*.json")) if d.is_dir() else []


def run_hook(root, capsys, *argv):
    capsys.readouterr()
    code = backlog.main(["--root", str(root), *argv])
    out = capsys.readouterr()
    return code, out.out, out.err


def test_headless_hooks_env_name_is_the_one_the_runner_sets():
    assert bl_intake.HEADLESS_ENV == kbpublic.HEADLESS_ENV


def test_headless_hooks_file_no_drafts_intake(clone, capsys, monkeypatch):
    monkeypatch.setenv(kbpublic.HEADLESS_ENV, "1")
    assert run_hook(clone, capsys, "intake", "--file", "--hook") == (0, "", "")
    assert drafts(clone) == []


def test_headless_hooks_file_no_drafts_red_pipeline(clone, capsys, monkeypatch):
    ran = []
    monkeypatch.setattr(backlog, "cmd_red_pipeline", lambda bl, a: ran.append(1) or 0)
    monkeypatch.setenv(kbpublic.HEADLESS_ENV, "1")
    assert run_hook(clone, capsys, "red-pipeline", "--hook") == (0, "", "")
    assert ran == [] and drafts(clone) == []


def test_headless_hooks_still_file_when_not_a_headless_runner(clone, capsys, monkeypatch):
    ran = []
    monkeypatch.setattr(backlog, "cmd_red_pipeline", lambda bl, a: ran.append(1) or 0)
    monkeypatch.delenv(kbpublic.HEADLESS_ENV, raising=False)
    assert run_hook(clone, capsys, "red-pipeline", "--hook") == (0, "", "") and ran == [1]
    assert run_hook(clone, capsys, "intake", "--file", "--hook") == (0, "", "")
    (f,) = drafts(clone)
    assert json.loads(f.read_text(encoding="utf-8"))["links"][-1] == "detector docs"


def test_headless_hooks_leave_a_hand_run_intake_file_unchanged(clone, capsys, monkeypatch):
    monkeypatch.setenv(kbpublic.HEADLESS_ENV, "1")
    code, out, _ = run_hook(clone, capsys, "intake", "--file")
    assert code == 0 and len(drafts(clone)) == 1 and "filed" in out
