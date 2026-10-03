"""kbpublic.cmd_publish_hook and the environment that switches it off: KB_NO_PUBLISH_HOOK (a non-empty value) and
KB_HEADLESS_RUNNER make it publish nothing; unset or empty, it publishes as before (planted failures: a hook that
ignores the variable publishes to the configured public remote)."""
import types

import pytest

import kbpublic
from conftest import requires_git
import test_kbpublic

src = test_kbpublic.src  # the repository fixture of the kbpublic tests
ns = test_kbpublic.ns
pytestmark = [pytest.mark.git, requires_git]


def planted(src, tmp_path):
    r, pub, origin = test_kbpublic.TestPublish.setup(None, src, tmp_path)
    r.git("config", "kb.publishRemote", "pub")
    return r, pub


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv(kbpublic.NO_HOOK_ENV, raising=False)
    monkeypatch.delenv(kbpublic.HEADLESS_ENV, raising=False)


def published(pub):
    return pub.run_git("rev-parse", "main").returncode == 0


def test_no_publish_hook_env_set_publishes_nothing(src, tmp_path, monkeypatch):
    r, pub = planted(src, tmp_path)
    monkeypatch.setenv(kbpublic.NO_HOOK_ENV, "1")
    assert kbpublic.cmd_publish_hook(ns(hook=True), r.path) == 0
    assert not published(pub)


def test_no_publish_hook_env_set_never_reaches_publish(monkeypatch):
    called = []
    monkeypatch.setattr(kbpublic, "publish_remote", lambda cwd: "pub")
    monkeypatch.setattr(kbpublic, "cmd_publish", lambda a, cwd: called.append(1))
    monkeypatch.setenv(kbpublic.NO_HOOK_ENV, "1")
    assert kbpublic.cmd_publish_hook(types.SimpleNamespace(remote=None), ".") == 0
    assert called == []
    monkeypatch.delenv(kbpublic.NO_HOOK_ENV)
    assert kbpublic.cmd_publish_hook(types.SimpleNamespace(remote=None), ".") == 0
    assert called == [1]


def test_no_publish_hook_env_unset_publishes(src, tmp_path):
    r, pub = planted(src, tmp_path)
    assert kbpublic.cmd_publish_hook(ns(hook=True), r.path) == 0
    assert published(pub)


def test_no_publish_hook_env_empty_counts_as_unset(src, tmp_path, monkeypatch):
    r, pub = planted(src, tmp_path)
    monkeypatch.setenv(kbpublic.NO_HOOK_ENV, "")
    assert kbpublic.cmd_publish_hook(ns(hook=True), r.path) == 0
    assert published(pub)


def test_no_publish_hook_env_headless_runner_still_publishes_nothing(src, tmp_path, monkeypatch):
    r, pub = planted(src, tmp_path)
    monkeypatch.setenv(kbpublic.HEADLESS_ENV, "1")
    assert kbpublic.cmd_publish_hook(ns(hook=True), r.path) == 0
    assert not published(pub)
