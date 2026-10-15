---
topic: security/fish-syntax-bash-differences
priority: P3
applies_to: "fish 4.9.3 as a scripting language: how its syntax departs from Bash and POSIX shells (quoting, expansion, globbing, redirection, conditions, blocks, subshells, exit statuses) and the limits a script author meets"
retrieved_utc: 2026-10-15
sources: [S-irnsu4to, S-2l7kac72, S-bdc6dn7m, S-c5jost2j, S-mepkq6ry, S-eg4rjgcz]
status: complete
---

# fish syntax and how it departs from Bash and POSIX shells

## Summary
fish is intentionally not POSIX-compatible: a Bash or `sh` script does not run unchanged under it, and the manual's advice to a script author is to name the interpreter in the shebang line. The differences that matter most to an operator are that fish never word-splits a variable, splits command substitutions on newlines only, fails a command whose glob matches nothing, has no heredocs, no `$((...))`, no `${var%x}` and no subshells, and ends every block with `end`. The manual read here is fish 4.9.3, released on September 8, 2026, which also runs on a Windows host under WSL, Cygwin or MSYS2 (`security/fish-on-windows-wsl-cygwin-msys2.md`). Variable scopes are in `security/fish-variables-scopes-export.md`, functions and abbreviations in `security/fish-functions-abbreviations-events.md`, and the staged breaking changes in `security/fish-feature-flags-release-changes.md`.

## Facts
- The manual read here is for fish 4.9.3, which is the newest release in the project's release history, dated September 8, 2026. [DOC S-mepkq6ry]
- The "fish for Bash users" page opens by saying fish is intentionally not POSIX-compatible, so things a Bash user is used to work differently. [DOC S-2l7kac72]
- A fish script names its interpreter like any other: the manual's example is `#!/usr/bin/env fish`, which finds `fish` through `PATH`. [DOC S-c5jost2j]
- A command substitution is written `$(command)` or `(command)`, not with backticks; the FAQ says backticks are discouraged even in POSIX shells because they nest poorly and look like single quotes. [DOC S-bdc6dn7m]
- Command substitution output is split on newlines only, never on `$IFS`; inside double quotes (`"$(cmd)"`) it is not split and only trailing empty lines are removed, and `"(cmd)"` with no dollar sign stays literal text. [DOC S-irnsu4to]
- To split a command's output on something else the manual points to `string split`, `string split0` or `string collect`, whose splits are kept when they are the last command in the substitution, as in `for i in (find . -print0 | string split0)`. [DOC S-2l7kac72]
- A command substitution reads at most 1 GiB by default; past that the whole command fails without running and `$status` is 122, and the limit is changed with the `fish_read_limit` variable, where `0` means no limit. [DOC S-irnsu4to]
- fish does not perform word splitting: a variable keeps the value it was set to, so a value with a space passed unquoted to `printf '"%s"\n' $foo` is one argument, where Bash prints two. [DOC S-2l7kac72]
- Between single quotes fish performs no expansion; between double quotes it performs only variable expansion and `$(command)` substitution, with no brace expansion and escape sequences such as `\n` ignored. [DOC S-irnsu4to]
- fish has no `$'...'` quoting: the escape sequences are transformed when unquoted, so `echo a\nb` prints two lines. [DOC S-2l7kac72]
- A trailing backslash immediately followed by a literal newline is a line continuation that does not introduce whitespace or end a token. Wildcards are `*`, `**` and the deprecated `?`; `**` descends into subdirectories without a shell option, and matches are sorted case-insensitively with numbers in natural order. [DOC S-irnsu4to]
- Unlike Bash, fish follows symlinks with `**`, which needs no option such as `globstar`, and globbing does not happen on an expanded variable, so `set foo "*"; echo $foo` matches no files. [DOC S-2l7kac72]
- If a wildcard matches nothing the command is not run, `$status` is set to nonzero and a warning is printed, as with Bash's `failglob`; the exceptions are `set`, `path`, `count`, `for` and a variable override, whose glob expands to zero arguments. [DOC S-irnsu4to]
- The FAQ's advice for a command that does its own matching, such as `apt install` or `scp`, is to quote or escape the star so that fish does not try to match files. [DOC S-bdc6dn7m]
- Variables are set with `set`, not `VAR=VAL`; `set foo = bar` creates a list of the two values `=` and `bar`, and `set foo=bar` is an error. fish has no `${var:-default}`; the manual's replacement is `set -q XDG_CONFIG_HOME || set XDG_CONFIG_HOME $HOME/.config`. String surgery that Bash writes as `${foo%bar}`, `${foo#bar}` and `${foo/bar/baz}` is done with the `string` builtin (`replace`, `split`, `match -r`, `pad`, `lower`, `upper`). [DOC S-2l7kac72]
- There is no `$((i+1))` arithmetic expansion; the `math` builtin does it, handles floating point (`math 5 / 2` prints 2.5) and needs quotes around parentheses and `*`. The nearest fish names for Bash's special variables are `$argv` for `$*`, `$@` and `$1`, `$status` for `$?`, `$fish_pid` for `$$`, `count $argv` for `$#`, `$last_pid` for `$!` and `status filename` for `$0`. fish has no `<<EOF` heredocs; the manual's replacements are `printf`, an `echo` with a quoted multi-line string, or a pipe, since quotes are followed across newlines. [DOC S-2l7kac72]
- Process substitution is `(command | psub)` in place of `<(command)`, and there is no equivalent to `>(command)`; `source` can read standard input, so `command | source` replaces `source (command | psub)`. `test` and `[` are POSIX-compatible and also compare floating point, but there is no `[[`, and `test` does not accept `==` as a synonym for `=`. [DOC S-2l7kac72]
- An `if` condition is a command and ends after the first job, with no `then`; `and`, `or`, `&&` and `||` are lazy, and a `switch` has no fallthrough. A longer chain of `and` and `or` can run a later step on a status left by an earlier skipped one (`test -e f; or echo x; and return 1` returns 1 when the test succeeded), so the manual recommends an `if` block for anything but simple checks. [DOC S-irnsu4to]
- Blocks are `for`, `while`, `if`, `switch`, `begin` and `function`, each ended by `end`; `do`, `done`, `then` and `fi` are not used, `begin; ...; end` is the grouping form, and there is no `until`, which becomes `while not` or `while !`. [DOC S-2l7kac72]
- Since 4.1.0 a compound command can also be written with braces (`{ echo 1; echo 2 }`), and `{echo,echo}` is then a compound command and no longer a brace expansion; the "fish for Bash users" page still shows only `begin` (see `_conflicts.md`). [DOC S-eg4rjgcz]
- fish has no subshells: Bash's `(foo; bar) | baz` is often written by mistake for `{ foo; bar; }`, which groups without a subshell and is `begin; foo; bar; end` in fish, and a `while read` loop at the end of a pipe runs in the same process, so its variables remain visible afterwards. To run code in a new shell environment the manual says to start one explicitly with `fish -c 'your code here'`, and to isolate variables otherwise with `set -l`. [DOC S-2l7kac72]
- Redirections include `2>`, `>>`, `&>` for both streams, the noclobber forms `>?` and `2>?`, and `<?` which reads a file or `/dev/null` if it cannot be opened; `^` is no longer a stderr redirection. Redirecting a builtin, function or block to a file descriptor above 2 is an error, while it is supported for external commands. A pipe carries `2>|` for stderr, and `&|` sends both streams; with a pipe and redirections the pipe is set up first and the redirections are then read left to right. [DOC S-irnsu4to]
- A trailing `&` starts a background job, but an `&` followed by a character other than whitespace or one of `;<>&|` is not the background operator; functions cannot be started in the background. The exit status of the last process is in `$status`, and a pipeline's per-command statuses are in the list `$pipestatus`; `not` negates `$status` but not `$pipestatus`, and a process killed by a signal gives 128 plus the signal number. fish sets some statuses itself: 121 for invalid arguments, 123 for a command name with invalid characters, 124 for a command not run because no wildcard matched, 125 for an executable the operating system could not run, 126 for a file that is not executable, and 127 for a command not found. [DOC S-irnsu4to]
- fish has no `$PS1`; the prompt is the output of the `fish_prompt` function (plus `fish_mode_prompt` in vi mode and `fish_right_prompt` for the right side), and there is no `$PS2`, continuation lines are indented instead. Bash's `set -x` is enabled by setting `fish_trace`, and `fish --profile FILE` times each command, where `fish --profile-startup FILE` profiles startup. [DOC S-2l7kac72]
- A command name is resolved as a function (loading it from `fish_function_path` if needed), then a builtin, then an executable in `PATH`; if the kernel cannot run a file for a missing interpreter and the file passes a rudimentary check, fish has `/bin/sh` run it. When nothing matches, fish runs the `fish_command_not_found` function and sets `$status` to 127. [DOC S-irnsu4to]
- Since 4.6.0 fish also accepts Bash's `|&` as an alternate spelling of `&|`, for piping both standard output and standard error. [DOC S-eg4rjgcz]
- A script that must behave the same everywhere cannot assume Bash features under fish: it either carries a fish shebang and uses `set`, `string`, `math`, `end` and `psub`, or it keeps a `#!/bin/bash` shebang and fish only starts it as an external command. [DER S-2l7kac72, S-c5jost2j, S-irnsu4to: fish is not POSIX-compatible and resolves an external script through its shebang]

## Reference
| Bash or POSIX form | fish form | source |
|---|---|---|
| `export VAR=val` | `set -gx VAR val` | S-2l7kac72 |
| `local x=1` | `set -l x 1` | S-2l7kac72 |
| `unset VAR` | `set -e VAR` | S-2l7kac72 |
| `${v:-default}` | `set -q v \|\| set v default` | S-2l7kac72 |
| `$(( i + 1 ))` | `math $i + 1` | S-2l7kac72 |
| `<(cmd)` | `(cmd \| psub)` | S-2l7kac72 |
| `cat <<EOF` | `printf %s\n "line 1" "line 2"` | S-2l7kac72 |
| `$?`, `$$`, `$#`, `$@` | `$status`, `$fish_pid`, `count $argv`, `$argv` | S-2l7kac72 |
| `[[ -n $x ]]` | `test -n "$x"` or `string length -q -- $x` | S-2l7kac72, S-bdc6dn7m |
| `foo() { ...; }` | `function foo ...; end` | S-2l7kac72 |
| `(a; b) \| c` | `begin; a; b; end \| c` | S-2l7kac72 |
| `until cond; do ...; done` | `while not cond ...; end` | S-2l7kac72 |

Related: `security/fish-variables-scopes-export.md`, `security/fish-functions-abbreviations-events.md`, `security/fish-config-files-completions.md`, `security/fish-feature-flags-release-changes.md`, `security/zsh-options-emulation-bash-differences.md` (the same comparison for zsh), `windows/powershell-7.md` (the shell fish most often sits next to on a Windows host).

## Examples
- SNIPPET: the same loop in Bash and fish, showing that a fish variable needs no quotes to survive a space; context: fish 4.9.3 on a Linux host or a Windows host under WSL, placeholder path `/srv/PL-SRV-0042`; checked: no [DER S-irnsu4to: an unquoted variable expands to one argument per list element, with no word splitting]
```
# Bash:  for f in "$dir"/*; do printf '%s\n' "$f"; done
set dir "/srv/PL-SRV-0042/my files"
for f in $dir/*
    printf '%s\n' $f
end
```
- SNIPPET: set a default and test a variable that may be empty; context: fish 4.9.3, `XDG_CACHE_HOME` as the example variable; checked: no [DER S-2l7kac72, S-bdc6dn7m: `set -q` tests existence and `string length -q` tests non-emptiness]
```
set -q XDG_CACHE_HOME; or set -gx XDG_CACHE_HOME $HOME/.cache
if string length -q -- $XDG_CACHE_HOME
    echo "cache dir is set"
end
```
