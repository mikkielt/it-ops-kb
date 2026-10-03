"""The headless runner's child holds no credentials: `autopilot.child_env` drops the agent, askpass and token variables
(keeping the model's own authentication and the runner's marker), `runner start` passes it to a fake claude that records
its environment, and the runner's worktree gives the public remote a failing pushurl in its own config only. The tests
named runner_child_holds_no_credentials are the item's checks."""
import os

import pytest

import autopilot
from test_autopilot import World, stream

FAKE_ENV = '''import json, os, sys
open(os.environ["FAKE_SEEN"], "w", encoding="utf-8").write(json.dumps(dict(os.environ)))
sys.stdout.write(open(os.environ["FAKE_STREAM"], encoding="utf-8").read())
'''

PLANTED = {"SSH_AUTH_SOCK": "/tmp/placeholder-agent.sock", "SSH_AGENT_PID": "1234", "GIT_ASKPASS": "/bin/placeholder-askpass",
           "SSH_ASKPASS": "/bin/placeholder-askpass", "GITLAB_TOKEN": "placeholder-a", "GITHUB_TOKEN": "placeholder-b",
           "GH_TOKEN": "placeholder-c", "GLAB_TOKEN": "placeholder-d", "GITLAB_ACCESS_TOKEN": "placeholder-e",
           "CI_JOB_TOKEN": "placeholder-f", "NPM_TOKEN": "placeholder-g", "TWINE_USERNAME": "placeholder-h",
           "PYPI_UPLOAD": "placeholder-i", "MY_API_KEY": "placeholder-j", "DB_PASSWORD": "placeholder-k",
           "SOME_PRIVATE-KEY": "placeholder-l", "app_secret": "placeholder-m"}
KEPT = {"ANTHROPIC_API_KEY": "placeholder-n", "CLAUDE_CODE_OAUTH_TOKEN": "placeholder-o", "CLAUDE_CONFIG_DIR": "/placeholder",
        "KEEP_ME": "yes"}


def plant(monkeypatch):
    for k, v in {**PLANTED, **KEPT}.items():
        monkeypatch.setenv(k, v)


def test_runner_child_holds_no_credentials_child_env_drops_each_and_keeps_the_rest(monkeypatch):
    plant(monkeypatch)
    env = autopilot.child_env()
    assert not [k for k in PLANTED if k in env]
    assert {k: env[k] for k in KEPT} == KEPT  # the model's authentication stays, or the headless run cannot start
    assert env["PATH"] == os.environ["PATH"] and env.get("HOME") == os.environ.get("HOME")
    assert env[autopilot.HEADLESS_ENV] == "1" and env["GIT_TERMINAL_PROMPT"] == "0"
    assert env.get("GIT_ASKPASS", None) is None  # removed, not emptied


def test_runner_child_holds_no_credentials_child_env_reads_the_given_environment():
    env = autopilot.child_env({"PATH": "p", "GITHUB_TOKEN": "x", "ANTHROPIC_API_KEY": "y", "ssh_auth_sock": "z"})
    assert env == {"PATH": "p", "ANTHROPIC_API_KEY": "y", "GIT_TERMINAL_PROMPT": "0", autopilot.HEADLESS_ENV: "1"}


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.delenv("KB_TESTS_FAST", raising=False)
    monkeypatch.delenv("KB_TEST_WORKERS", raising=False)
    w = World(tmp_path, monkeypatch)
    w.fake.write_text(FAKE_ENV, encoding="utf-8", newline="\n")
    return w


def test_runner_child_holds_no_credentials_a_real_run_gets_the_scrubbed_environment(world, monkeypatch):
    plant(monkeypatch)
    world.stream(stream())
    assert world.start() == 0
    seen = world.seen()
    assert not [k for k in PLANTED if k in seen]
    assert {k: seen[k] for k in KEPT} == KEPT
    assert seen["KB_HEADLESS_RUNNER"] == "1" and seen["GIT_TERMINAL_PROMPT"] == "0" and "PATH" in seen and "HOME" in seen


def local_config(repo):
    """The clone's own config lines, but the branch.* ones `git worktree add` writes for the new branch."""
    return "\n".join(ln for ln in repo.git("config", "--local", "--list").splitlines() if not ln.startswith("branch."))


def add_public(world):
    world.repo.git("init", "--bare", "-b", "main", str(world.tmp / "public.git"))
    world.repo.git("remote", "add", "public", str(world.tmp / "public.git"))
    world.repo.git("config", "kb.publishRemote", "public")


def test_runner_child_holds_no_credentials_worktree_blocks_the_public_remote_only_there(world):
    add_public(world)
    world.stream(stream())
    before = local_config(world.repo)
    assert world.start() == 0
    wt = world.wt()
    assert world.repo.git("-C", str(wt), "config", "--get", "remote.public.pushurl").strip() == autopilot.NO_PUSH_URL
    assert world.repo.git("-C", str(wt), "remote", "get-url", "--push", "public").strip() == autopilot.NO_PUSH_URL
    assert world.repo.git("-C", str(world.root), "remote", "get-url", "--push", "public").strip() == str(world.tmp / "public.git")
    after = local_config(world.repo)
    assert "pushurl" not in after  # the main clone's pushurl is untouched, so its own publish still pushes
    assert [ln for ln in after.splitlines() if ln not in before.splitlines()] == ["extensions.worktreeconfig=true"]
    world.repo.git("-C", str(wt), "push", "origin", "HEAD:refs/heads/probe")  # the integration remote stays open
    bad = autopilot.subprocess.run(["git", "push", "public", "HEAD:refs/heads/probe"], cwd=wt, capture_output=True)
    assert bad.returncode != 0


def test_runner_child_holds_no_credentials_a_second_start_keeps_the_block(world):
    add_public(world)
    world.stream(stream())
    assert world.start() == 0
    assert world.start() == 0
    out = world.repo.git("-C", str(world.wt()), "config", "--get-all", "remote.public.pushurl")
    assert out.split() == [autopilot.NO_PUSH_URL]


def test_runner_child_holds_no_credentials_without_a_public_remote_nothing_is_set(world):
    world.stream(stream())
    before = local_config(world.repo)
    assert world.start() == 0
    assert local_config(world.repo) == before
    assert "pushurl" not in world.repo.git("-C", str(world.wt()), "config", "--list")


def test_runner_child_holds_no_credentials_a_public_name_without_a_remote_does_not_fail(world):
    world.repo.git("config", "kb.publishRemote", "nowhere")
    world.stream(stream())
    assert world.start() == 0
    assert "pushurl" not in world.repo.git("-C", str(world.wt()), "config", "--list")
