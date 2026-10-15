---
topic: security/zsh-startup-files-invocation
priority: P3
applies_to: "Zsh 5.9.2 as an interactive and scripting shell: which startup and shutdown files run in which kind of shell, ZDOTDIR, the RCS and GLOBAL_RCS options, invocation flags, sh/ksh emulation at startup, PRIVILEGED and restricted mode"
retrieved_utc: 2026-10-15
sources: [S-jpnt2s3d, S-dqge7eik, S-e6mo6lhk, S-x7azxeah]
status: complete
---

# Zsh startup files and invocation

## Summary
Zsh reads its startup files in one fixed order: `/etc/zshenv` and `$ZDOTDIR/.zshenv` for every shell, then the login files (`zprofile`), then the interactive files (`zshrc`), then the last login files (`zlogin`); a login shell reads the logout files when it exits. The `RCS` and `GLOBAL_RCS` options (both on by default) and the `-f` flag decide whether the later files are read at all. Invoked under the name `sh` or `ksh`, zsh reads none of these and follows the `/etc/profile` and `$HOME/.profile` pattern instead. The manual this was read from documents Zsh 5.9.2, released on July 12, 2026, which also runs on a Windows host under Cygwin. Options themselves are in `security/zsh-options-emulation-bash-differences.md`.

## Facts
- The manual chapter read here is for Zsh version 5.9.2, released on July 12, 2026. [DOC S-jpnt2s3d]
- Commands are first read from `/etc/zshenv`, which cannot be overridden, and then from `$ZDOTDIR/.zshenv`, for every shell, interactive or not. [DOC S-jpnt2s3d]
- A login shell then reads `/etc/zprofile` and `$ZDOTDIR/.zprofile`; an interactive shell reads `/etc/zshrc` and `$ZDOTDIR/.zshrc`; a login shell finally reads `/etc/zlogin` and `$ZDOTDIR/.zlogin`. [DOC S-jpnt2s3d]
- When a login shell exits, `$ZDOTDIR/.zlogout` and then `/etc/zlogout` are read, after an explicit `exit` or `logout` or after end-of-file from the terminal, but not if the shell ends by exec'ing another process. [DOC S-jpnt2s3d]
- If `ZDOTDIR` is unset, `HOME` is used instead, and the files named `/etc/...` may sit in another directory depending on the installation. [DOC S-jpnt2s3d]
- `RCS` and `GLOBAL_RCS` are both set by default; a file in `$ZDOTDIR` can re-enable `GLOBAL_RCS`; and if `RCS` is unset when the shell exits, no history file is saved. [DOC S-jpnt2s3d]
- With `RCS` unset `/etc/zshenv` is still sourced but no other startup file is; unsetting `GLOBAL_RCS` skips `/etc/zprofile`, `/etc/zshrc`, `/etc/zlogin` and `/etc/zlogout`; and `-f` is the single-letter name of `NO_RCS`, so `zsh -f` starts without the later files. [DOC S-e6mo6lhk]
- Because `/etc/zshenv` runs for all instances of zsh, the manual says to keep it as small as possible and to put code that does not need to run every time behind `if [[ -o rcs ]]` so that `zsh -f` skips it. [DOC S-jpnt2s3d]
- Any startup file can be pre-compiled with the `zcompile` builtin; a file with the `.zwc` extension that is newer than the original is used instead. [DOC S-jpnt2s3d]
- The shell is a login shell if started with `-l` or, when `LOGIN` is not set explicitly, if the first character of `argv[0]` is `-`; `INTERACTIVE` is set at initialisation if standard input is a terminal and commands are read from it, and cannot be changed once zsh is running. [DOC S-e6mo6lhk]
- `-c` takes the first argument as the command, and a further argument becomes `$0`; `-i` forces an interactive shell and `-s` forces reading standard input; otherwise the first argument is the script file, searched for in `PATH` only if `PATH_SCRIPT` is set and the name holds no `/`. [DOC S-dqge7eik]
- An option can be set at invocation by name with `-o name` (`+o name` turns it off) or in GNU long style as `--sh-word-split`; `--emulate mode` must come before other options, takes extra steps compared with the `emulate` builtin (variables such as `path` are not defined), and `--version` and `--help` print and exit successfully. [DOC S-dqge7eik]
- Zsh emulates sh or ksh when invoked under a name whose first letter, ignoring an initial `r`, is `b`, `s` or `k`; the usual startup scripts are then not executed, login shells source `/etc/profile` and `$HOME/.profile`, and `$ENV` is sourced afterwards. [DOC S-dqge7eik]
- In sh or ksh mode these parameters are not special and not initialised: `ARGC`, `argv`, `cdpath`, `fignore`, `fpath`, `HISTCHARS`, `mailpath`, `MANPATH`, `manpath`, `path`, `prompt`, `PROMPT`, `PROMPT2`, `PROMPT3`, `PROMPT4`, `psvar` and `status`. [DOC S-dqge7eik]
- Invoked as `sh` or `ksh`, zsh sets `NO_BAD_PATTERN`, `NO_BANG_HIST`, `NO_BG_NICE`, `NO_EQUALS`, `NO_FUNCTION_ARGZERO`, `GLOB_SUBST`, `NO_GLOBAL_EXPORT`, `NO_HUP`, `INTERACTIVE_COMMENTS`, `KSH_ARRAYS`, `NO_MULTIOS`, `NO_NOMATCH`, `NO_NOTIFY`, `POSIX_BUILTINS`, `NO_PROMPT_PERCENT`, `RM_STAR_SILENT`, `SH_FILE_EXPANSION`, `SH_GLOB`, `SH_OPTION_LETTERS` and `SH_WORD_SPLIT`; as `sh` also `BSD_ECHO` and `IGNORE_BRACES`, as `ksh` also `KSH_OPTION_PRINT`, `LOCAL_OPTIONS`, `PROMPT_BANG`, `PROMPT_SUBST` and `SINGLE_LINE_ZLE`. [DOC S-dqge7eik]
- The manual states that zsh does not guarantee complete emulation of other shells or POSIX compliance. [DOC S-dqge7eik]
- `PRIVILEGED` is turned on at startup if the effective user or group ID differs from the real one and disables sourcing of user startup files; in sh or ksh mode `/etc/suid_profile` is then sourced, `~/.profile` is not and `ENV` is ignored; a privileged script starts with `#!/bin/zsh -p`. [DOC S-e6mo6lhk]
- A shell is restricted when the invocation name starts with `r`, `-r` is given or `RESTRICTED` is set; the restrictions (no `cd`, no change of `PATH`, `SHELL` or `IFS`, no command names with `/`, no output redirection to files, no `exec`) are enforced after the startup files. [DOC S-dqge7eik]
- The manual calls restricted mode an outdated way to restrict users, very difficult to implement safely, and possibly removed in a future version; the restrictions apply to the shell and not to the commands it runs, `readonly` is not a security feature, and modules such as `zsh/system`, `zsh/mapfile` and `zsh/files` can bypass most of them. [DOC S-dqge7eik]
- The FAQ names Zsh 5.9.2 as the latest production version. [DOC S-x7azxeah]
- On many machines `chsh` accepts only a shell listed in `/etc/shells`, so without root a copy of zsh is started by an `exec` from the login file of the original shell, with `-l` so that zsh knows it is a login shell, as in `[ -f $HOME/bin/zsh ] && exec $HOME/bin/zsh -l`. [DOC S-x7azxeah]
- The FAQ says the separate Windows and OS/2 ports of zsh are out of date and hard to get, and that zsh exists for the Cygwin environment. [DOC S-x7azxeah]
- All recent releases of zsh compile under Cygwin, a UNIX-style environment for the Win32 API, and the Cygwin installer offers a pre-compiled zsh. [DOC S-x7azxeah]
- Taken together the sequence gives four cases: a non-login non-interactive shell (a script, `zsh -c`) reads only the two `zshenv` files; a non-login interactive shell adds the `zshrc` files; a login non-interactive shell reads `zshenv`, `zprofile`, `zlogin`; a login interactive shell reads all four kinds in the order `zshenv`, `zprofile`, `zshrc`, `zlogin`. [DER S-jpnt2s3d: the order of the read steps with the conditions "login" and "interactive"]
- A setting that non-interactive zsh processes must see (for example `PATH` for a command run over a remote shell or by a tool that starts `zsh -c`) belongs in `.zshenv`, since `.zshrc` is read only when the shell is interactive and `.zprofile` only for a login shell. [DER S-jpnt2s3d: `zshenv` is the only file read for every shell]

## Reference
| shell kind | files read, in order | source |
|---|---|---|
| non-login, non-interactive (script, `zsh -c`) | `/etc/zshenv`, `$ZDOTDIR/.zshenv` | S-jpnt2s3d |
| non-login, interactive | `zshenv` files, `/etc/zshrc`, `$ZDOTDIR/.zshrc` | S-jpnt2s3d |
| login, non-interactive | `zshenv`, `zprofile`, `zlogin` files | S-jpnt2s3d |
| login, interactive | `zshenv`, `zprofile`, `zshrc`, `zlogin` files | S-jpnt2s3d |
| invoked as `sh` or `ksh` | `/etc/profile`, `$HOME/.profile`, then `$ENV` | S-dqge7eik |

Related: `security/zsh-options-emulation-bash-differences.md` (option defaults and emulation), `security/zsh-completion-system.md` (where `compinit` is run from), `claude/settings-and-scopes.md` (lists shell startup files among the files Claude Code protects), `security/kali-apt-sources-metapackages.md` (`zsh` is a dependency of `kali-system-core`).

## Examples
- SNIPPET: keep `/etc/zshenv` cheap by running the interactive-only part only when startup files are enabled; context: Zsh 5.9.2, the guard form the manual recommends; checked: no [DER S-jpnt2s3d: the `[[ -o rcs ]]` test from the manual's note on `/etc/zshenv`]
```
# /etc/zshenv  (read by every zsh, including `zsh -f`)
if [[ -o rcs ]]; then
  # code that is not needed for every single shell
  export PL_EXAMPLE_VAR=1
fi
```
- SNIPPET: keep a user's startup files in a separate directory; context: Zsh 5.9.2, `ZDOTDIR` set in `/etc/zshenv`; checked: no [DER S-jpnt2s3d: `$ZDOTDIR/.zshenv` is read after `/etc/zshenv`, and `HOME` is used when `ZDOTDIR` is unset]
```
# /etc/zshenv
export ZDOTDIR="$HOME/.config/zsh"
# zsh then reads $HOME/.config/zsh/.zshenv, .zprofile, .zshrc, .zlogin
```
