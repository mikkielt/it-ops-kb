"""The runner's claude child pushes over ssh with the runner's deploy key only (KB_RUNNER_DEPLOY_KEY, else a file
outside every clone): no agent, no user ssh config, no fallback to the operator's ~/.ssh keys, and no key at all
when the file is missing (kb/_self/autopilot-test.md). Every test points the variable at a stub; none reads the real
key."""
import pytest

import autopilot


@pytest.fixture
def stub_key(tmp_path):
    key = tmp_path / "stub key"  # a space: the path is quoted
    key.write_text("not a key\n", encoding="utf-8")
    return key


def test_runner_deploy_key_child_uses_only_the_key(stub_key):
    env = autopilot.child_env({autopilot.RUNNER_KEY_ENV: str(stub_key), "PATH": "/bin"})
    cmd = env["GIT_SSH_COMMAND"]
    assert f"-i '{stub_key}'" in cmd and "IdentitiesOnly=yes" in cmd and "IdentityAgent=none" in cmd
    assert "-F " in cmd and ".ssh/config" not in cmd  # no ~/.ssh/config IdentityFile can add the operator's key


def test_runner_deploy_key_reads_the_system_config_alone(stub_key, tmp_path, monkeypatch):
    """The system ssh config (a container's timeouts) is read, alone; without one, none is."""
    system = tmp_path / "ssh_config"
    system.write_text("ServerAliveInterval 15\n", encoding="utf-8")
    monkeypatch.setattr(autopilot, "SYSTEM_SSH_CONFIG", str(system))
    assert f"-F {system}" in autopilot.runner_ssh_command({autopilot.RUNNER_KEY_ENV: str(stub_key)})
    monkeypatch.setattr(autopilot, "SYSTEM_SSH_CONFIG", str(tmp_path / "none"))
    assert "-F /dev/null" in autopilot.runner_ssh_command({autopilot.RUNNER_KEY_ENV: str(stub_key)})


def test_runner_deploy_key_missing_file_offers_no_key(tmp_path):
    env = autopilot.child_env({autopilot.RUNNER_KEY_ENV: str(tmp_path / "absent"), "PATH": "/bin"})
    cmd = env["GIT_SSH_COMMAND"]
    assert "IdentityFile=/dev/null" in cmd and " -i " not in cmd and "IdentitiesOnly=yes" in cmd


def test_runner_deploy_key_overrides_the_parents_ssh(stub_key):
    """A GIT_SSH_COMMAND or GIT_SSH in the manager's environment never reaches the child: the runner's wins."""
    env = autopilot.child_env({autopilot.RUNNER_KEY_ENV: str(stub_key), "GIT_SSH_COMMAND": "ssh -i ~/.ssh/id_ed25519",
                               "GIT_SSH": "/usr/bin/ssh", "SSH_AUTH_SOCK": "/tmp/agent"})
    assert "id_ed25519" not in env["GIT_SSH_COMMAND"] and "GIT_SSH" not in env and "SSH_AUTH_SOCK" not in env


def test_runner_deploy_key_planted_child_without_it_fails_the_check(stub_key, monkeypatch):
    """Planted: a child_env that keeps the parent's ssh command lets the operator's key through; the check above
    refuses that."""
    real = autopilot.child_env
    monkeypatch.setattr(autopilot, "child_env", lambda environ=None: {**real(environ), "GIT_SSH_COMMAND": "ssh"})
    cmd = autopilot.child_env({autopilot.RUNNER_KEY_ENV: str(stub_key)})["GIT_SSH_COMMAND"]
    assert "IdentitiesOnly=yes" not in cmd
