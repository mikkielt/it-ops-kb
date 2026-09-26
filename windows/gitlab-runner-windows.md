---
topic: windows/gitlab-runner-windows
priority: P0
applies_to: "GitLab Runner 19.5 (main @49138a48, 2026-09-23) on Windows"
retrieved_utc: 2026-09-26
sources: [S406, S407, S408, S409, S410, S411, S412, S413, S414, S415, S400]
status: partial
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
- Mapped network drives aren't available to the service. Use UNC paths. [DOC S406]
- On Windows the `install` command has flags `--user/-u` ("Specify user-name to secure the runner") and `--password/-p` (usage text says "(required)"). These are passed to the service config as `UserName` and the `Password` option (kardianos/service v1.2.4). [DOC S413]
- Shells: `powershell` (Desktop) is the default for the `kubernetes` and `docker-windows` executors. `pwsh` (Core) is the default for new registrations on Windows and for the `shell` executor. The registration default applies only when `shell` is set in `config.toml`. [DOC S407]
- "PowerShell doesn't support executing the build in context of another user." [DOC S407]
- The generated script runs as `pwsh -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command <file>` (or `powershell ...` for Desktop). [DOC S407]
- `[runners.docker] security_opt` passes `--security-opt` to `docker run`. [DOC S408]
- Source: when `build.SafeDirectoryCheckout` is true, the runner writes `git config --global --add safe.directory <projectDir>` before checkout. [DOC S409]
- `safe_directory_checkout` (TOML) / `--safe-directory-checkout` / `RUNNER_SAFE_DIRECTORY_CHECKOUT` sets it per runner. [DOC S410]
- Executor defaults: `shell` false, docker true (also kubernetes, virtualbox, parallels true; ssh and custom false; read from source). [DOC S411,S412]
- `safe_directory_checkout` does not appear in the runner docs (`docs/`) at this commit. [UNK]
- Microsoft: services configured through Service Control Manager can use a gMSA. [DOC S400]
- Issue 27895, "Group Managed Service Account Support" (closed 2023-04-20, milestone 15.5): the proposer marks runner service support as "Already supported" with `install --user "CORP\Test-gMSA$"` and no password, and asks for the docs to drop "(required)" from `--password`. [COMMUNITY S414]
- The delivered GitLab feature is gMSA for the `docker-windows` executor through a credential spec in `security_opt` (15.5, MR 2913). [COMMUNITY S414]
- Issue 30963, "Update runner docs to capture details on gMSA support", is still open. [COMMUNITY S415]
- Running the service under a gMSA is plausible: the runner is an SCM service (S406, S413), and SCM services support gMSA (S400). GitLab has not documented it. [DER S400,S406,S413]

## Reference
| Item | Value | Source |
|---|---|---|
| Service name / event provider | `gitlab-runner` | S406 |
| Default shell (shell executor, Windows) | `pwsh` | S407 |
| Script flags | `-NoProfile -NonInteractive -ExecutionPolicy Bypass` | S407 |
| safe.directory switch | `safe_directory_checkout` / `RUNNER_SAFE_DIRECTORY_CHECKOUT` | S410 |
| Default safe.directory (shell executor) | false | S411 |

## Examples
```powershell
cd C:\GitLab-Runner
.\gitlab-runner.exe install                      # Built-in System Account (documented)
.\gitlab-runner.exe install --user "CORP\svc-runner$"   # gMSA, no password: COMMUNITY S414 only
.\gitlab-runner.exe start
```
```toml
[[runners]]
  executor = "shell"
  shell = "pwsh"
  safe_directory_checkout = true   # source-only option (S410)
```
