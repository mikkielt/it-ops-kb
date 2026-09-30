---
topic: windows/gitlab-runner-windows
priority: P0
applies_to: "GitLab Runner 19.5 (main @49138a48, 2026-09-23) on Windows"
retrieved_utc: 2026-09-30
sources: [S406, S407, S408, S409, S410, S411, S412, S413, S-xiyru25z, S414, S415, S400, S-dmxxlc75, S-5x5wqdjs, S-c7hn5f2e, S-z2riv2e3, S-wlt4mta2, S-kw4zko43, S-74r2p6k2]
status: complete
---

# GitLab Runner on Windows

## Summary
- Install: put `gitlab-runner.exe` in a folder, restrict write access to it, register the runner, then run `gitlab-runner.exe install` and `start` from an elevated prompt. The service runs as the Built-in System Account (recommended) or as a user given with `--user`/`--password`.
- Shells: `pwsh` is the default for new registrations on Windows and for the `shell` executor. Scripts run with `-NoProfile -NonInteractive -ExecutionPolicy Bypass`.
- `safe.directory`: the runner adds `git config --global --add safe.directory <project dir>` only when `safe_directory_checkout` is true. That is the default for docker, kubernetes, virtualbox and parallels, and not for shell, ssh or custom. The option exists in the source but not in the docs.
- gMSA: GitLab docs don't mention running the runner service as a gMSA. An issue says `install --user "DOMAIN\name$"` with no password works (COMMUNITY). The docs change it asked for is still open.

## Facts
- Requirements: Git; a password for the user account if the service runs under a user rather than the Built-in System Account; system locale English (United States). [DOC S406]
- Restrict `Write` permissions on the runner directory and executable. Otherwise regular users could replace it and run code with elevated privileges. [DOC S406]
- Built-in System Account: `.\gitlab-runner.exe install` then `.\gitlab-runner.exe start` (recommended). [DOC S406]
- User account: `.\gitlab-runner.exe install --user <name> --password <pw>`. A valid password is needed because Windows requires it to start the service. [DOC S406]
- If you get "The account name is invalid", prefix the user with `.\`. [DOC S406]
- If you get "The service did not start due to a logon failure", the account lacks `SeServiceLogonRight` ("Log on as a service"). [DOC S406]
- Runner service logs go to the Windows Event Log under provider `gitlab-runner` (`Get-WinEvent -ProviderName gitlab-runner`). [DOC S406]
- As a service, jobs run in session 0: no interactive desktop, and display resolution is limited to 1024x768. [DOC S406]
- When the service runs under a standard (non-administrator) user account it can't access mapped network drives (service logon sessions are restricted); use UNC paths. [DOC S406]
- On Windows the `install` command has flags `--user/-u` ("Specify user-name to secure the runner") and `--password/-p` (usage text says "(required)"). These are passed to the service config as `UserName` and the `Password` option (kardianos/service library). [CODE S413: commands/service.go#createServiceConfig; CODE S-xiyru25z: commands/service_windows.go#setupOSServiceConfig]
- Shells: `powershell` (Desktop) is the default for the `kubernetes` and `docker-windows` executors. `pwsh` (Core) is the default for new registrations on Windows and for the `shell` executor. The registration default applies only when `shell` is set in `config.toml`. [DOC S407]
- "PowerShell doesn't support executing the build in context of another user." [DOC S407]
- The generated script runs as `pwsh -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command <file>` (or `powershell ...` for Desktop). [DOC S407]
- `[runners.docker] security_opt` passes `--security-opt` to `docker run`. [DOC S408]
- Source: when `build.SafeDirectoryCheckout` is true, the runner writes `git config --global --add safe.directory <projectDir>` before checkout. [CODE S409: shells/abstract.go#AbstractShell.setupTemplateDir]
- `safe_directory_checkout` (TOML) / `--safe-directory-checkout` / `RUNNER_SAFE_DIRECTORY_CHECKOUT` sets it per runner. [CODE S410: common/config.go#SafeDirectoryCheckout]
- Executor defaults: `shell` false, docker true (read from source). [CODE S411: executors/shell/shell.go#NewProvider; CODE S412: executors/docker/docker_command.go#newDockerOptions]
- Other executor defaults at the same commit: `kubernetes`, `virtualbox` and `parallels` true; `ssh` and `custom` false. [CODE S-dmxxlc75: executors/kubernetes/kubernetes.go#executorOptions; CODE S-5x5wqdjs: executors/virtualbox/virtualbox.go#NewProvider; CODE S-c7hn5f2e: executors/parallels/parallels.go#NewProvider; CODE S-z2riv2e3: executors/ssh/ssh.go#NewProvider; CODE S-wlt4mta2: executors/custom/custom.go#NewProvider]
- `safe_directory_checkout` is undocumented: no file in the runner's `docs/` mentions it, neither at 49138a48 nor at main 0e3fe7d3 (2026-09-28), and the published advanced-configuration page has no mention either. [DER S410, S-kw4zko43: case-insensitive search of the docs directory at both commits]
- Microsoft: services configured through Service Control Manager can use a gMSA. [DOC S400]
- Issue 27895, "Group Managed Service Account Support" (closed 2023-04-20, milestone 15.5): the proposer marks runner service support as "Already supported" with `install --user "CORP\Test-gMSA$"` and no password, and asks for the docs to drop "(required)" from `--password`. [COMMUNITY S414]
- The delivered GitLab feature is gMSA for the `docker-windows` executor through a credential spec in `security_opt` (15.5, MR 2913). [COMMUNITY S414]
- Issue 30963, "Update runner docs to capture details on gMSA support", is still open. [COMMUNITY S415]
- Running the service under a gMSA is plausible: the runner is an SCM service (S406, S413), and SCM services support gMSA (S400). GitLab has not documented it. [DER S400,S406,S413]
- The `docker` and `docker-windows` executors take a `cpus` setting under `[runners.docker]` ("Number of CPUs", also `--docker-cpus` or `DOCKER_CPUS`), beside `memory` and `cpuset_cpus`. [CODE S410: common/config.go#DockerConfig]
- For a Windows container, Docker's `--cpus` maps to the host compute service's `ProcessorCount`; with hypervisor isolation it sets the number of virtual processors the container's utility VM exposes, and with process isolation it is simulated with a job-object CPU rate cap. [DOC S-74r2p6k2]
- So the CPU count a `docker-windows` job's tests see (and with it `pytest -n auto` and `os.cpu_count()` inside the container) is set by the runner's `cpus` setting under hypervisor isolation; the default when it is unset is not stated on the Microsoft page, and a job of this repository's `kb-tests-windows` on 2026-09-29 reported `created: 2/2 workers`. [DER S410, S-74r2p6k2: the setting and its mapping above; the worker count from job 16821688871's log]

## Reference
- Antivirus and Windows containers on a `docker-windows` runner host (what host scanning covers, what is unknown): `windows/dev-drive.md`.

| Item | Value | Source |
|---|---|---|
| Service name / event provider | `gitlab-runner` | S406 |
| Default shell (shell executor, Windows) | `pwsh` | S407 |
| Script flags | `-NoProfile -NonInteractive -ExecutionPolicy Bypass` | S407 |
| safe.directory switch | `safe_directory_checkout` / `RUNNER_SAFE_DIRECTORY_CHECKOUT` | S410 |
| Default safe.directory (shell executor) | false | S411 |

Related: `gitlab/hosted-runners-windows.md` (GitLab.com's own Windows runners: tier, tag, image, cost).

## Examples
- SNIPPET: install and start the runner service as the Built-in System Account (the gMSA line is a community-reported variant, not documented by GitLab); context: GitLab Runner 19.5 on Windows, elevated prompt; checked: no [DOC S406, COMMUNITY S414: `.\gitlab-runner.exe install` / `start` for the Built-in System Account (S406); `install --user "DOMAIN\name$"` with no password for a gMSA (S414, community-reported)]
```powershell
cd C:\GitLab-Runner
.\gitlab-runner.exe install                      # Built-in System Account (documented)
.\gitlab-runner.exe install --user "CORP\svc-runner$"   # gMSA, no password: COMMUNITY S414 only
.\gitlab-runner.exe start
```
- SNIPPET: shell executor config using `pwsh` and the source-only `safe_directory_checkout` option; context: `config.toml`, GitLab Runner 19.5; checked: no [DOC S407; CODE S410: common/config.go#SafeDirectoryCheckout: `shell = "pwsh"` is the default shell for the `shell` executor (S407); `safe_directory_checkout` is the TOML key read from source, not documented]
```toml
[[runners]]
  executor = "shell"
  shell = "pwsh"
  safe_directory_checkout = true   # source-only option (S410)
```
