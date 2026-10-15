---
topic: security/zsh-options-emulation-bash-differences
priority: P3
applies_to: "Zsh 5.9.2 options: how an option is named, set and listed, which defaults depend on the emulation mode, the emulate builtin and LOCAL_OPTIONS, and the documented differences from sh, ksh and Bash"
retrieved_utc: 2026-10-15
sources: [S-e6mo6lhk, S-ehyugoua, S-3gkyn5mu, S-cbs5knac]
status: complete
---

# Zsh options, emulation modes and differences from Bash

## Summary
Zsh behaviour is steered by named options: set with `setopt` or `unsetopt`, named case-insensitively with underscores ignored, and listed with a default that depends on the emulation mode (`zsh`, `sh`, `ksh`, `csh`). Most differences from POSIX sh and Bash that surprise a script author come from options that are off or on by default in zsh's own mode: no word splitting of unquoted parameters, an error for a glob with no match, arrays numbered from 1, `#` comments not allowed at an interactive prompt. `emulate` and `LOCAL_OPTIONS` give a function a known configuration. The Zsh FAQ says plainly that zsh is not a bug-for-bug copy of Bash and that Bash scripts should run under Bash. Startup files are in `security/zsh-startup-files-invocation.md`; expansion rules in `security/zsh-expansion-globbing-arrays.md`.

## Facts
- Option names are case insensitive and underscores are ignored (`allexport` is equivalent to `A__lleXP_ort`); a `no` prefix inverts the sense, once only (`setopt No_Beep` is `unsetopt beep`); single-letter names come in a default set and an sh/ksh set (`SH_OPTION_LETTERS`), `+` inverts a letter, and options can also be set within a function scope. [DOC S-e6mo6lhk]
- In the option list `<D>` marks an option set by default in all emulations and `<C>`, `<K>`, `<S>`, `<Z>` mark options set by default only in csh, ksh, sh or zsh emulation; `setopt` with no argument shows the options whose setting differs from the default, since those on by default are listed with a `no` prefix; `RCS` and `GLOBAL_RCS` are `<D>`. [DOC S-e6mo6lhk]
- `NOMATCH` is `<C> <Z>`: in zsh mode a filename pattern with no match is an error and not left unchanged; `NULL_GLOB` deletes a pattern with no match and `CSH_NULL_GLOB` deletes it unless all patterns of the command fail, and both override `NOMATCH`. [DOC S-e6mo6lhk]
- `EXTENDED_GLOB` carries no default mark and makes `#`, `~` and `^` part of patterns (an initial unquoted `~` always produces named directory expansion); `EQUALS` is `<Z>`, so `=` filename expansion is on in zsh mode. [DOC S-e6mo6lhk]
- `KSH_ARRAYS` (`<K> <S>`) numbers array elements from zero, makes a bare array name refer to its first element and requires braces for a subscript or a modifier; `SH_WORD_SPLIT` (`<K> <S>`) splits unquoted parameter expansions into fields, which the manual says has nothing to do with word splitting of the command line. [DOC S-e6mo6lhk]
- `GLOB_SUBST` (`<C> <K> <S>`) makes the characters that result from parameter expansion eligible for filename expansion and generation; `SH_GLOB` (`<K> <S>`) disables the special meaning of `(`, `|`, `)` and `<` in the result of substitutions and some other places; `KSH_GLOB` (`<K>`) lets `@`, `*`, `+`, `?` or `!` before a parenthesis change its meaning in patterns. [DOC S-e6mo6lhk]
- `INTERACTIVE_COMMENTS` (`-k`, `<K> <S>`) allows comments even in interactive shells, and `UNSET` (`<K> <S> <Z>`) treats unset parameters as empty when substituting and as zero in arithmetic, otherwise as an error. [DOC S-e6mo6lhk]
- `INTERACTIVE_COMMENTS` carries no `<Z>` mark, so in zsh's own mode a `#` typed at an interactive prompt is not a comment until the option is set. [DER S-e6mo6lhk: marks `<K> <S>` only, and `<Z>` marks defaults in zsh emulation]
- `RC_EXPAND_PARAM` (`-P`) makes `foo${xx}bar` with `xx` set to `(a b c)` give `fooabar foobbar foocbar` instead of `fooa b cbar`, and an empty array then removes the argument; `SHARE_HISTORY` imports new commands from the history file and appends typed ones, and should replace `INC_APPEND_HISTORY`, not be used with it. [DOC S-e6mo6lhk]
- `BASH_REMATCH`, when set, makes the `=~` operator fill the `BASH_REMATCH` array instead of `MATCH` and `match`, best with `KSH_ARRAYS` so that the whole match is index 0; `REMATCH_PCRE` makes `=~` use PCRE and needs the `zsh/pcre` module. [DOC S-e6mo6lhk]
- `LOCAL_OPTIONS` restores, at return from a function, most of the options in force on entry except `PRIVILEGED` and `RESTRICTED`; the manual's way to give a function a known configuration is `emulate -L zsh`, where `-L` turns on `LOCAL_OPTIONS`. [DOC S-e6mo6lhk]
- `emulate` with no argument prints the current mode and with `zsh`, `sh`, `ksh` or `csh` sets the options for that shell (csh will never be fully emulated); without `-R` it alters only the options likely to cause portability problems, with `-R` it resets all settable options except some for the interactive environment; `-L` sets `LOCAL_OPTIONS`, `LOCAL_PATTERNS` and `LOCAL_TRAPS`, and `emulate mode -c 'code'` runs the code with the emulation in effect and restores the options after. [DOC S-ehyugoua]
- The `echo` builtin differs from other shells: a single dash ends option processing and is not printed, while a double dash is printed, and `printf` is the manual's portable alternative. [DOC S-ehyugoua]
- The FAQ's summary: it is not safe to assume a user's zsh behaves like sh or ksh because of all the options, invoking it as `sh` or `ksh` sets the appropriate options, the classic difference is word splitting of unquoted parameters (fixed with `SH_WORD_SPLIT`), and the next is an unmatched glob that aborts the command (fixed with `NO_NOMATCH`). [DOC S-3gkyn5mu]
- In zsh arrays are by default csh-like: subscripts start at 1, `array[0]` refers to `array[1]`, `$array` is the whole array and braces are not needed for a subscript; an element of an ordinary array cannot be unset, only set to the empty string or cut off by shortening the array, while elements of associative arrays can be unset. [DOC S-3gkyn5mu]
- With default options the result of a parameter substitution is plain text, so `foo="*"; print $foo` prints `*` in zsh but all the files in ksh (`GLOB_SUBST` gives the ksh result), and the `PS1` to `PS4` prompt strings do not undergo parameter substitution unless `PROMPT_SUBST` is set. [DOC S-3gkyn5mu]
- In `cmd1 && cmd2 &` only `cmd2` runs in the background in zsh (`{ cmd1 && cmd2 } &` is the FAQ's workaround), and the FAQ says there is no `$ENV` variable in zsh's own mode (use `/etc/zshrc`, `~/.zshrc` and `$ZDOTDIR`); in sh or ksh mode `$ENV` is sourced (`security/zsh-startup-files-invocation.md`). [DOC S-3gkyn5mu]
- In the FAQ's example, `var="foo bar"; args $var` with `args() { echo $#; }` prints 1 in zsh and 2 after `setopt shwordsplit`; the natural zsh way to get word splitting is an array (`array=(one two three twenty)`), and `${=sentence}` splits one expansion without the option. [DOC S-cbs5knac]
- The FAQ states that bash and zsh are different programming languages and not interchangeable, that zsh is not a bug-for-bug compatible reimplementation of bash, and that a difference between the two does not make the zsh behaviour a bug, since what counts is what zsh's user manual specifies. [DOC S-3gkyn5mu]
- The FAQ's advice is not to run bash scripts under zsh, to keep `#!/usr/bin/env bash` scripts even when zsh is the interactive shell, and, to run a bash script or plugin under zsh, to port it properly, reviewing it line by line for differences. [DOC S-3gkyn5mu]
- For an automation that passes a script or a command string to a shell on a managed host, naming the interpreter explicitly (`bash script.sh`, `#!/usr/bin/env bash`) avoids depending on a user's login shell and its options; this follows from the options being a per-user and per-emulation setting. [DER S-3gkyn5mu, S-e6mo6lhk: FAQ advice to keep bash shebangs, and option defaults depending on emulation]
- A zsh script that must behave the same under any user's startup files starts with `emulate -L zsh` (or `emulate -L sh` for POSIX-style code) and sets the few options it relies on. [DER S-ehyugoua, S-e6mo6lhk: `emulate -L` makes the reset local to the function]

## Reference
| option | zsh mode default | sh/ksh mode | effect | source |
|---|---|---|---|---|
| `SH_WORD_SPLIT` | off | on | split unquoted parameter expansions on `IFS` | S-e6mo6lhk |
| `NOMATCH` | on | off | unmatched glob is an error | S-e6mo6lhk |
| `KSH_ARRAYS` | off | on | arrays from 0, bare name is first element | S-e6mo6lhk |
| `GLOB_SUBST` | off | on | results of substitutions are globbed | S-e6mo6lhk |
| `EXTENDED_GLOB` | off | off | `^`, `~`, `#` are pattern characters | S-e6mo6lhk |
| `INTERACTIVE_COMMENTS` | off | on | `#` comments at an interactive prompt | S-e6mo6lhk |

Related: `security/zsh-startup-files-invocation.md`, `security/zsh-expansion-globbing-arrays.md`, `security/zsh-completion-system.md`.

## Examples
- SNIPPET: make a function independent of the caller's options and give it the one option it needs; context: Zsh 5.9.2; checked: no [DER S-ehyugoua, S-e6mo6lhk: `emulate -L zsh` and `setopt` inside the function stay local]
```
pl_list_logs() {
  emulate -L zsh
  setopt null_glob
  local f
  for f in /var/log/pl-app/*.log; do print -r -- "$f"; done
}
```
