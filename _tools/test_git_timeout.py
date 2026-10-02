"""The bounded wait of a git network call made under the host main lock (kg_lock.run_git_bounded; kb/_self/git.md, Two
runners on one host). The test named git_fetch_timeout_releases_main_lock is the item's check: a git stub that sleeps
past KB_GIT_NETWORK_TIMEOUT ends within about the bound, the lock file is gone, and the error names the step, the
command, the bound and the holder step. Planted failures: the stub that sleeps, a garbage bound, a stub that finishes.
"""
import os, stat, time
from pathlib import Path

import pytest

import bl_land, kg_lock, kg_sync


@pytest.fixture(autouse=True)
def hermetic(tmp_path, monkeypatch):
    d = tmp_path / "hostlocks"
    d.mkdir()
    monkeypatch.setenv("KB_HOST_LOCK_DIR", str(d))
    monkeypatch.setenv("KB_HOST_LOCK_POLL", "0.05")
    monkeypatch.delenv(kg_lock.HELD_ENV, raising=False)
    monkeypatch.delenv(kg_lock.TIMEOUT_ENV, raising=False)
    return d


def stub_git(tmp_path, monkeypatch, body):
    """A `git` first on PATH that runs BODY (shell) for fetch and push and the real git for anything else."""
    real = Path(__import__("shutil").which("git")).as_posix()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    f = bin_dir / "git"
    f.write_text(f'#!/bin/sh\ncase "$1" in fetch|push|ls-remote) {body};; *) exec {real} "$@";; esac\n', encoding="utf-8")
    f.chmod(f.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")


posix_only = pytest.mark.skipif(os.name != "posix", reason="the git stub is a shell script")


@posix_only
def test_git_fetch_timeout_releases_main_lock(tmp_path, monkeypatch, hermetic):
    marker = tmp_path / "child.pid"
    stub_git(tmp_path, monkeypatch, f"sh -c 'echo $$ > {marker}; sleep 30' & sleep 30")
    monkeypatch.setenv(kg_lock.TIMEOUT_ENV, "0.5")
    lock = hermetic / kg_lock.LOCK_NAME
    t0 = time.time()
    with pytest.raises(kg_lock.GitNetworkTimeout) as e:
        with kg_lock.main_lock("test holder step", clone=str(tmp_path)):
            assert lock.exists()
            kg_lock.run_git_bounded(["fetch", "--quiet", "x"], tmp_path, "fetch")
    assert time.time() - t0 < 10
    assert not lock.exists()
    msg = str(e.value)
    for part in ("fetch", "git fetch", "0.5", "test holder step", "released"):
        assert part in msg
    assert kg_lock.HOLD["step"] is None
    pid = int(marker.read_text().strip()) if marker.exists() else None
    if pid:  # the child of the stub died with its group
        time.sleep(0.2)
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)


@posix_only
def test_git_timeout_land_stops_at_its_step(tmp_path, monkeypatch):
    stub_git(tmp_path, monkeypatch, "sleep 30")
    monkeypatch.setenv(kg_lock.TIMEOUT_ENV, "0.3")
    with pytest.raises(Exception) as e:
        bl_land.land_git(tmp_path, "fetch", "fetch", "--quiet", "x")
    assert "land stopped at step fetch" in str(e.value)
    assert "0.3" in str(e.value)


@posix_only
def test_git_timeout_sync_reports_and_pushes_nothing(tmp_path, monkeypatch):
    stub_git(tmp_path, monkeypatch, "sleep 30")
    monkeypatch.setenv(kg_lock.TIMEOUT_ENV, "0.3")
    monkeypatch.setattr(kg_sync, "KB", str(tmp_path))
    t0 = time.time()
    code, out = kg_sync.gitx_net("push", "x", "HEAD:refs/heads/main")
    assert code == 124 and "0.3" in out and "git push" in out
    assert time.time() - t0 < 10


@posix_only
def test_git_timeout_fast_stub_passes_through(tmp_path, monkeypatch):
    stub_git(tmp_path, monkeypatch, "echo out; echo err >&2; exit 3")
    p = kg_lock.run_git_bounded(["fetch"], tmp_path, "fetch")
    assert (p.returncode, p.stdout.strip(), p.stderr.strip()) == (3, "out", "err")
    assert kg_lock.HOLD["step"] is None


def test_git_timeout_env_override_and_garbage_default(monkeypatch):
    assert kg_lock.network_timeout() == 120.0
    monkeypatch.setenv(kg_lock.TIMEOUT_ENV, "7.5")
    assert kg_lock.network_timeout() == 7.5
    for bad in ("abc", "0", "-3", "nan", "inf", ""):
        monkeypatch.setenv(kg_lock.TIMEOUT_ENV, bad)
        assert kg_lock.network_timeout() == 120.0, bad
    assert kg_lock.network_timeout("2") == 2.0
