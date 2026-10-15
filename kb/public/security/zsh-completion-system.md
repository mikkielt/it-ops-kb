---
topic: security/zsh-completion-system
priority: P3
applies_to: "Zsh 5.9.2 programmable completion: compinit and the dump file, fpath and underscore-named completion functions, #compdef and compdef, zstyle contexts, the insecure-directory check, and bashcompinit"
retrieved_utc: 2026-10-15
sources: [S-wkxevnxu, S-e6mo6lhk, S-jpnt2s3d, S116]
status: partial
---

# Zsh completion system

## Summary
Completion in zsh is wired by the shell function `compinit`, called from an interactive startup file (normally `.zshrc`). It scans `fpath` for functions whose first line is a `#compdef` tag, autoloads them, and redefines the completion widgets. Behaviour is configured with `zstyle`, matched against a six-field context string. `compinit` caches its work in a `.zcompdump` file and checks that the directories it loads from are not writable by others. The `dsc completer zsh` command of the kb's DSC article writes a completion script to stdout; how that script reaches a directory in `fpath` is not stated by the kb's sources.

## Facts
- If zsh was installed completely, calling `compinit` from an initialisation file is enough; it should be in a directory named in `fpath` and autoloaded (`autoload -U compinit` is recommended); it defines a few utility functions, arranges for the necessary functions to be autoloaded and redefines all widgets that do completion. [DOC S-wkxevnxu]
- `compinstall` can be run by a user to configure the system; it normally inserts code into `.zshrc`, or into another file it names if `.zshrc` is not writable, and if `.zshrc` usually returns early the lines must be moved before that point, because it is up to the user to make sure they run. [DOC S-wkxevnxu]
- If the `menu-select` widget of the `zsh/complist` module is used, the module must be loaded before the call to `compinit`; `compinit` rebinds a TAB bound to `expand-or-complete` to `complete-word` if styles are set up to expand as well as complete; and the original widgets stay reachable by a leading dot, for example `.expand-or-complete`. [DOC S-wkxevnxu]
- `compinit` writes a dump of its configuration by default, `-D` turns that off and `-d dumpfile` names the file; the default `.zcompdump` sits in the directory of the startup files, `$ZDOTDIR` or `$HOME`. [DOC S-wkxevnxu]
- A changed number of completion files produces a new dump, but if only a function name or the first line of a `#compdef` function changes the dump file should be deleted by hand; `compinit -C` skips the check for new functions and creates a dump only if none exists, `-w` explains why a dump is not loaded or is regenerated, and `compdump` writes the dump after a configuration change such as `compdef`. [DOC S-wkxevnxu]
- For security `compinit` checks whether the completion system would use files not owned by root or the current user, or files in group- or world-writable directories, and asks whether to use them; `-u` uses all files found without asking, `-i` silently ignores insecure ones, the check is skipped with `-C` when the dump file exists, and `compaudit` runs the same check on demand over `fpath` and `_compdir`. [DOC S-wkxevnxu]
- Autoloaded completion functions start with an underscore and must be in a directory of `fpath` (or `FPATH`); `compinit` reads the first line of each such file, and a file whose first line does not start with a recognised tag is not part of the completion system. [DOC S-wkxevnxu]
- `#compdef name ...` makes the file autoloadable and calls it when completing the named commands or special contexts such as `-redirect-` (`-p` and `-P` give patterns tried before or after other completions), a name may be `cmd=service` so that `cmd` is completed as if `service` were (the function receives `$service`), and `#autoload` marks a function for autoloading without otherwise treating it as a completion function. [DOC S-wkxevnxu]
- If `compinit` finds fewer than twenty files beginning with an underscore in the search path, it tries to add the `_compdir` directory. [DOC S-wkxevnxu]
- `compdef function name ...` defines the function used to complete the names from the shell; `compdef '_files -g "*.h"' foo` completes `.h` files for `foo`, `-n` keeps an existing definition and `-d` removes one. [DOC S-wkxevnxu]
- A style context is the string `:completion:function:completer:command:argument:tag`, with empty fields left empty but their colons kept; the most specific matching `zstyle` pattern wins regardless of the order of definition, strings over patterns and longer patterns over `*`; a pattern that uses something other than `*` for the completer, command or argument field should contain all six colons. [DOC S-wkxevnxu]
- `bashcompinit` defines the functions `compgen` and `complete`, so that completion specifications written for bash can be used. [DOC S-wkxevnxu]
- `AUTO_LIST` and `AUTO_MENU` are `<D>` options, on by default in every emulation: choices are listed on an ambiguous completion and menu completion starts at the second consecutive request. [DOC S-e6mo6lhk]
- `.zshrc` is read only by interactive shells, so `compinit` belongs there (or in a file `.zshrc` sources) and not in `.zshenv`. [DER S-jpnt2s3d, S-wkxevnxu: `.zshrc` is the interactive-shell file; compinit redefines ZLE widgets]
- On a shared host `compinit` stops to ask about group- or world-writable completion directories, so a provisioning script that writes `.zshrc` for users should either fix the directory permissions or choose `-u` or `-i` knowingly. [DER S-wkxevnxu: `-u`, `-i` and what the security check examines]
- `dsc completer zsh` writes a completion script to stdout (`dsc/cli-reference.md:34`); wiring such a script into zsh means a file with a leading underscore in an `fpath` directory carrying a `#compdef` line, or a `compdef` call. [DER S116, S-wkxevnxu: the DSC article gives the command; the zsh manual gives the autoload convention]
- Whether the script that `dsc completer zsh` prints starts with a `#compdef dsc` line, or is meant to be evaluated with `eval`, is not confirmed by a source in the kb. [UNK]

## Reference
| need | command or file | source |
|---|---|---|
| enable completion | `autoload -U compinit; compinit` in `.zshrc` | S-wkxevnxu |
| completion function for command `foo` | file `_foo` in an `fpath` directory, first line `#compdef foo` | S-wkxevnxu |
| ad hoc completion | `compdef _files foo` | S-wkxevnxu |
| skip or re-run the security check | `compinit -u`, `compinit -i`; `compaudit` | S-wkxevnxu |
| style context | `:completion:function:completer:command:argument:tag` | S-wkxevnxu |

Related: `security/zsh-startup-files-invocation.md` (`.zshrc` and `ZDOTDIR`), `security/zsh-options-emulation-bash-differences.md`, `dsc/cli-reference.md` (`dsc completer`). For a Linux distribution on a Windows host see `security/gentoo-in-wsl.md`.

## Examples
- SNIPPET: enable completion and make the argument after `2>` complete only `*.log` files; context: Zsh 5.9.2, interactive `.zshrc` on a Linux host or in a WSL distribution on a Windows host; checked: no [DER S-wkxevnxu: `autoload -U compinit` and the manual's own `zstyle` example for the `-redirect-` context]
```
# ~/.zshrc
autoload -U compinit
compinit
zstyle ':completion:*:*:-redirect-,2>,*:*' file-patterns '*.log'
```
