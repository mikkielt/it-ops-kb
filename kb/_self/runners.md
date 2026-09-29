# CI runners: the project's own GitLab runners

The project has two self-hosted GitLab runners on the same Windows 11 Pro machine (here `PL-LT-00123`, the operator `jan.kowalski`), so a job that names one of their tags never waits on GitLab.com's shared-runner quota. Which job names which tag, and when each starts, is in `.gitlab-ci.yml` and `kb/_self/git.md` (Workflow). This file is the runbook for the runners themselves. Neither runner's token is in the repository: each lives only in its runner's `config.toml`.

| tag | executor | where | runs |
|---|---|---|---|
| `docker-windows` | `docker-windows`, Hyper-V isolation | the Windows service `gitlab-runner` on the host (`C:\GitLab-Runner`), Docker Engine for Windows containers | `kb-tests-windows` |
| `docker-linux` | `docker` | the service `gitlab-runner` under systemd in the WSL 2 distribution `Ubuntu-24.04` of the local account `kb-runner`, Docker Engine inside it; `concurrent = 2` | the Linux-image jobs that name `docker-linux` |

Both are project runners, locked to this project, and neither takes untagged jobs: a job reaches them only by naming a tag.

## Why WSL for Linux

A `docker-windows` runner runs Windows containers only, and Docker Engine on the host serves Windows containers. Docker Desktop is left out: it switches the one engine between Windows and Linux containers, and the Windows runner needs it in Windows mode all the time. A Linux VM runs the Linux jobs instead, and WSL 2 is the lightest one Windows 11 has.

## The docker-linux runner

1. **WSL 2.** Turn on Virtual Machine Platform (`Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -All -NoRestart`; on a host with Hyper-V already on it asks for no restart), then install the WSL package (`winget install --id Microsoft.WSL --exact`) and the distribution (`wsl --install -d Ubuntu-24.04 --no-launch --web-download`). The inbox `wsl.exe` stub installs nothing while the legacy "Windows Subsystem for Linux" feature waits for a restart; the package's `C:\Program Files\WSL\wsl.exe` does. Ubuntu 24.04's `/etc/wsl.conf` already has `[boot] systemd=true`.
2. **Docker Engine and GitLab Runner**, as root in the distribution: Docker's apt repository (`docs.docker.com/engine/install/ubuntu`: the `docker.asc` key, a `docker.sources` file, `docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin`), then GitLab's (`script.deb.sh` from `packages.gitlab.com`, then `apt install gitlab-runner`); `systemctl enable --now docker gitlab-runner`.
3. **Create and register.** Tags, `locked` and `run_untagged` can only be set when the runner is created, not at `gitlab-runner register` with an authentication token (docs.gitlab.com/runner/register). The runner is created with the API as a project runner (`glab api -X POST user/runners -f runner_type=project_type -F project_id=<id> -f tag_list=docker-linux -F run_untagged=false -F locked=true -f description=docker-linux-wsl2`), which returns its runner authentication token once. The token goes into `gitlab-runner register --non-interactive --url https://gitlab.com --token <token> --executor docker --docker-image python:3.14-slim` without being printed: through a variable and a root-only file inside the distribution, deleted after registering. A token lost on the way leaves a runner that never connects: delete it (`glab api -X DELETE runners/<id>`) and create another. Then set `concurrent = 2` at the top of `/etc/gitlab-runner/config.toml` (the service reloads it).
4. **Its own account.** A WSL distribution belongs to the Windows user that registered it, and a scheduled task cannot start in the background as an Entra ID (cloud) account. So the distribution lives in the local standard account `kb-runner`, which has "Log on as a batch job" (`SeBatchLogonRight`, through `secedit`). The distribution was built under the operator's account, moved with `wsl --export` and imported by `kb-runner` (`wsl --import Ubuntu-24.04 C:\WSL\kb-runner <tar> --version 2`); the tar holds the runner's token, so it sits in a folder only Administrators, SYSTEM and `kb-runner` can read, and is deleted after the import. The account's random password is kept DPAPI-encrypted in the operator's profile, readable by the operator's account only; Task Scheduler keeps its own copy for the task.
5. **Kept running.** `%UserProfile%\.wslconfig` of `kb-runner` sets `[general] instanceIdleTimeout=-1`, which turns off the distribution's shutdown when idle (default 15 s, learn.microsoft.com/windows/wsl/wsl-config). The scheduled task `it-ops-kb WSL runner keep-alive` runs at startup as `kb-runner` with its stored password: `C:\WSL\kb-runner-import\keepalive.ps1` imports the distribution when it is missing, then holds it up with `sleep infinity`; no time limit, restarted every minute when it stops.

## Checking them

- GitLab's view: `glab api "projects/mikkielt%2Fit-ops-kb/runners?status=online"` lists the online runners (a runner counts as online for a while after its last contact: read `contacted_at` in `glab api runners/<id>` for the last one).
- The Linux runner: the task's state (`Get-ScheduledTask -TaskName 'it-ops-kb WSL runner keep-alive'`, `Running`), its log `C:\WSL\kb-runner-import\keepalive.log` (import result, `systemctl is-active docker gitlab-runner`). As `kb-runner`, `wsl -d Ubuntu-24.04 -u root -- gitlab-runner verify`. The operator's own `wsl -l` does not list it: it is another user's distribution.
- The Windows runner: `Get-Service gitlab-runner`, and `C:\GitLab-Runner\config.toml`.
- A job that stays pending names a tag no online runner has, or waits for `concurrent`: the Windows runner runs one job at a time, the Linux one two.
