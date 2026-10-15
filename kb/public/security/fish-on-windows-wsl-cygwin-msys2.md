---
topic: security/fish-on-windows-wsl-cygwin-msys2
priority: P3
applies_to: "fish 3.2 to 4.9.3 on a Windows host: Windows Subsystem for Linux (WSL 1 and 2), Cygwin and MSYS2, what the release notes and manual say about PATH, background jobs, completions of .exe commands, terminals and universal variables there"
retrieved_utc: 2026-10-15
sources: [S-eg4rjgcz, S-kcajyom3]
status: complete
---

# fish on a Windows host: WSL, Cygwin and MSYS2

## Summary
The documentation read here names Windows Subsystem for Linux (WSL), Cygwin and MSYS2 as the environments fish runs in on a Windows host, and the release notes since 3.2 record a steady series of Windows-specific fixes for those three. The facts that matter to an operator are how the Windows `PATH` reaches fish under WSL (4.0.0 changed it), what fish does to background jobs when WSL 1 closes a session, and how a command's `.exe` name and its completions relate on Cygwin and MSYS2. Configuration files and variables are in `security/fish-config-files-completions.md` and `security/fish-variables-scopes-export.md`. The manual read is fish 4.9.3, released on September 8, 2026.

## Facts
- Since 4.0.0 fish on a Windows host under WSL no longer searches the directories of the Windows system and user `$PATH` for Linux executables, so a Linux binary in a Windows folder run by name needs its `/mnt/c/...` path added explicitly to `$fish_user_paths`. [DOC S-eg4rjgcz]
- The 4.0.0 notes also say performance and interactivity under Windows Subsystem for Linux were improved, with a workaround for Windows-specific locations being appended to `$PATH` by default. [DOC S-eg4rjgcz]
- Under Windows WSL 1 (not WSL 2), 4.0.0 makes fish explicitly kill backgrounded jobs that were not disowned and do not end after SIGHUP and SIGCONT when the session exits, to work around a WSL 1 deficiency; the workaround for a job that must outlive the session is `disown`. [DOC S-eg4rjgcz]
- 4.0.6 fixed fish not inheriting `$PATH` properly under Windows WSL2. [DOC S-eg4rjgcz]
- Cygwin support was reintroduced in 4.1.0, since Rust gained a Cygwin target, so fish runs again in the Cygwin environment on a Windows host. [DOC S-eg4rjgcz]
- 4.1.1 added a workaround for Windows Terminal, where fish failed to read the terminal's response to its new startup queries, causing noticeable lags and a misleading error message. [DOC S-eg4rjgcz]
- 4.2.0 fixed a Windows-specific case of the web-based configuration (`fish_config`) failing to launch, and added an MSYS2-specific workaround that stops Konsole and WezTerm from using the wrong working directory when opening new tabs. [DOC S-eg4rjgcz]
- 4.2.0 also fixed, for MSYS2 on Windows, a regression from 4.1.0 in saving and loading universal variables. [DOC S-eg4rjgcz]
- Since 4.3.0, on Cygwin and MSYS under Windows, command name completion favours the non-exe name (`foo`) unless the user started typing the extension. [DOC S-eg4rjgcz]
- On Cygwin, MSYS2 and Windows the `.exe` extension is not required in `complete -c myprog`: completions for `myprog` also serve `myprog.exe` if there is no ambiguity, while completions given for `myprog.exe` are used only when the `.exe` extension is typed. [DOC S-kcajyom3]
- 3.6.1 silenced a spurious error seen in Google Drive directories under WSL 2 on a Windows host, improved the speed of completing directories in WSL 2, and builds correctly on Cygwin. [DOC S-eg4rjgcz]
- 3.6.0 made `help` on WSL use PowerShell to open the browser if available, which removed awkward UNC path errors on Windows. [DOC S-eg4rjgcz]
- 3.4.0 made the clipboard bindings ignore X-based clipboard programs when `DISPLAY` is not set, which helps prefer the Windows clipboard where it is available, such as on WSL. [DOC S-eg4rjgcz]
- 3.2.0 made executing a script with Windows line endings (CRLF) produce a sensible error. [DOC S-eg4rjgcz]
- 3.2.0 stopped fish crashing when it is started from a Windows-style working directory such as `F:\path`. [DOC S-eg4rjgcz]
- 3.2.0 made the web configuration tool detect Windows Services for Linux 2 properly. [DOC S-eg4rjgcz]
- 3.2.0 made `help` work properly on MSYS2 under Windows and use `cmd.exe` only when running on WSL. [DOC S-eg4rjgcz]
- 3.2.0 extended fish's clipboard bindings to Windows Subsystem for Linux through PowerShell and `clip.exe`, copying newlines of multi-line commands properly. [DOC S-eg4rjgcz]
- 3.2.0 made the cursor shape in vi mode change properly in Windows Terminal. [DOC S-eg4rjgcz]
- 3.2.1 removed an unhelpful "access: No error" message seen on Cygwin under Windows. [DOC S-eg4rjgcz]
- 3.3.0 stopped the `kill` completions from erroring on MSYS2 on a Windows host. [DOC S-eg4rjgcz]
- 3.4.0 added completions for WSL's `wslpath` and for Windows commands such as `cmd`, `powershell`, `reg`, `schtasks` and `setx`. [DOC S-eg4rjgcz]
- An automation that runs under fish in WSL and executes a Linux binary kept in a Windows folder by bare name must call it by an absolute `/mnt/c/...` path or have that directory in `$fish_user_paths`, because fish 4.0.0 and later do not search the Windows `PATH` directories for Linux executables. [DER S-eg4rjgcz: the first fact of this list]

## Reference
| Windows environment | what the notes and manual say | source |
|---|---|---|
| WSL 1 | unowned background jobs are killed at exit; use `disown` | S-eg4rjgcz |
| WSL (1 and 2) | Windows `PATH` directories not searched for Linux executables (4.0.0) | S-eg4rjgcz |
| WSL 2 | `$PATH` inheritance fixed (4.0.6) | S-eg4rjgcz |
| Cygwin | support reintroduced in 4.1.0; `.exe` completions unified | S-eg4rjgcz, S-kcajyom3 |
| MSYS2 | universal variables fixed in 4.2.0; `.exe` completions unified | S-eg4rjgcz, S-kcajyom3 |
| Windows Terminal | startup-query workaround in 4.1.1 | S-eg4rjgcz |

Related: `security/fish-config-files-completions.md`, `security/fish-variables-scopes-export.md`, `security/fish-feature-flags-release-changes.md`, `security/gentoo-in-wsl.md` (a Linux distribution in WSL on a Windows host), `windows/powershell-7.md` (the Windows-native shell), `windows/openssh-server.md` (the default shell of an SSH session to a Windows host).

## Examples
- SNIPPET: make a Linux binary kept in a Windows folder callable by name from fish under WSL; context: fish 4.0.0 or later in WSL, placeholder directory only; checked: no [DER S-eg4rjgcz: the Windows `PATH` directories are not searched for Linux executables, and `$fish_user_paths` takes the explicit path]
```
# ~/.config/fish/conf.d/windows_tools.fish
set -ga fish_user_paths /mnt/c/PL-Tools/bin
```
