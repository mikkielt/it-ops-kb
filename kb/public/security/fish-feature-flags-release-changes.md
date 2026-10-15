---
topic: security/fish-feature-flags-release-changes
priority: P3
applies_to: "fish 3.x to 4.9.3: the future feature flags that stage breaking changes (status features, fish_features, --features) and the release notes that changed scripting behaviour, from the 4.0.0 Rust port to 4.9.3"
retrieved_utc: 2026-10-15
sources: [S-irnsu4to, S-eg4rjgcz, S-f6olkobv, S-mepkq6ry]
status: complete
---

# fish feature flags and what changed per release

## Summary
fish stages changes that could break scripts behind named feature flags: a change is first opt-in, in a few releases opt-out, and the old behaviour is then removed, at which point the flag can no longer be turned off. `status features` lists them, `fish --features` or the universal `fish_features` variable sets them, and a flag takes effect only at startup. The releases read here run from 3.x through 4.0.0 (February 27, 2025, the port of fish's core from C++ to Rust) to 4.9.3 (September 8, 2026). Scripts that depend on `?` globbing, the `^` stderr redirection, one-argument `test` or `%self` are the ones affected. Basic syntax differences are in `security/fish-syntax-bash-differences.md`.

## Facts
- Feature flags are how fish stages changes that might break scripts: introduced as opt-in, after a few releases opt-out, and eventually the old behaviour is removed. `status features` lists the flags with their state, and in 4.9.3 `stderr-nocaret`, `qmark-noglob`, `regex-easyesc`, `ampersand-nobg-in-token`, `mark-prompt`, `ignore-terminfo` and `query-term` are on, while `remove-percent-self`, `test-require-arg` and `omit-term-workarounds` are off. A flag is enabled for one session with `fish --features NAME,NAME`, or for a user with `set -U fish_features NAME ...`; features are read only at startup, so the variable must be universal or exported. [DOC S-irnsu4to]
- A version number such as `3.0` is a group of the flags introduced then, the group `all` enables every flag, and the prefix `no-` turns one off, as in `set -Ua fish_features no-qmark-noglob`. `stderr-nocaret` (3.0) made `^` an ordinary character instead of a stderr redirection, and cannot be turned off since 3.5; the redirection is `2>`. `qmark-noglob` (3.0) makes `?` an ordinary character instead of a single-character glob; it became the default in 4.0, and `set -Ua fish_features no-qmark-noglob` brings the glob back. [DOC S-irnsu4to]
- `regex-easyesc` (3.1, default since 3.5) means the replacement expression of `string replace -r` needs one fewer round of escaping for a backslash. `ampersand-nobg-in-token` (3.4, default since 3.5) stops `&` in the middle of a token from being the background operator, which helps with URLs. `remove-percent-self` (4.0) turns off the `%self` expansion in favour of `$fish_pid`, and `test-require-arg` (4.0) removes the one-argument form of `test`, so `test "string"` must become `test -n "string"`; both are off by default in 4.9.3. [DOC S-irnsu4to]
- With `test-require-arg` off, a `test` call that would change prints a debug message of category `deprecated-test`, and `fish --debug=deprecated-test` finds the callers. `ignore-terminfo` (4.1) disabled the terminfo lookup of `$TERM` and cannot be turned off since 4.5; `query-term` lets fish query the terminal with escape sequences, and `omit-term-workarounds` (4.3) skips workarounds for incompatible terminals. [DOC S-irnsu4to]
- 4.0.0 (February 27, 2025) ported fish's core code from C++ to Rust, which the release notes say should have no direct impact on users but changes dependencies and how fish is built. 4.0.0 also forbade a variable in command position that expands to a subcommand keyword (`set editor command emacs; $editor`), and `foo & && bar` became a syntax error. 4.0.0 added the `<?` redirection, `set --no-event`, `history append`, `commandline --tokens-raw` and command-restricted abbreviations (`abbr --add --command git ...`), and made `for` loops forget local variables of the previous iteration. [DOC S-eg4rjgcz]
- 4.1.0 allowed braces for compound commands, so `{echo,echo}` is no longer brace expansion, and made fish stop reading the terminfo database. 4.2.0 made fish assume UTF-8 for character encoding even when the system has no UTF-8 locale, and made the standalone build mode the default so that upgrades no longer break running shells. 4.3.0 stopped setting user-facing universal variables by default, added the `status language` command, and let `fish_trace` be set to `all` to also trace key bindings, event handlers and prompt functions. [DOC S-eg4rjgcz]
- 4.5.0 made the `ignore-terminfo` flag permanent, so that fish no longer depends on ncurses or terminfo, and 4.6.0 accepted `|&` as an alternate spelling of `&|` for Bash compatibility and switched the default emoji width from 1 to 2 (`$fish_emoji_width` set back to 1 restores it). 4.7.0 stopped setting the default theme (`fish_color_*`) in non-interactive shells. 4.8.0 gave `cd` the `-L` and `-P` options, made nested brace expansions strip unquoted leading and trailing spaces, removed unescaping from the `--command` and `--path` options of `complete`, and stopped creating the `__fish_initialized` universal variable. [DOC S-eg4rjgcz]
- 4.9.0 (September 3, 2026) allowed nested list indexing such as `$foo[$bar[1] 2]`, made `status=123 echo $status` an error, and let abbreviations carry a description; 4.9.1, 4.9.2 and 4.9.3 are fixes for terminal key handling. [DOC S-eg4rjgcz]
- The release history on the project home page lists 4.9.3 (September 8, 2026) at its top, and 4.9.3 is the version whose manual this article set was read from. [DOC S-mepkq6ry]
- A script that must run on both a 3.x and a 4.x fish should test for the behaviours above rather than a version: write `2>` instead of `^`, quote or escape `?`, use `test -n "$var"`, `$fish_pid` instead of `%self`, and `begin ... end` instead of braces. [DER S-irnsu4to, S-eg4rjgcz: `^` and `?` ordinary since 3.5 and 4.0.0, one-argument `test` and `%self` flagged for removal, braces only since 4.1.0]

## Reference
| flag | introduced | state in 4.9.3 | effect | source |
|---|---|---|---|---|
| `stderr-nocaret` | 3.0 | on, permanent since 3.5 | `^` is not a redirection | S-irnsu4to |
| `qmark-noglob` | 3.0 | on (default since 4.0.0) | `?` is not a glob | S-irnsu4to, S-eg4rjgcz |
| `regex-easyesc` | 3.1 | on (default since 3.5) | one fewer escape round in `string replace -r` | S-irnsu4to |
| `ampersand-nobg-in-token` | 3.4 | on (default since 3.5) | `&` inside a token is not background | S-irnsu4to |
| `remove-percent-self` | 4.0 | off | no `%self` | S-irnsu4to |
| `test-require-arg` | 4.0 | off | no one-argument `test` | S-irnsu4to |
| `mark-prompt` | 4.0 | on | OSC 133 prompt markers | S-irnsu4to |
| `ignore-terminfo` | 4.1 | on, permanent since 4.5 | no terminfo lookup | S-irnsu4to |
| `query-term` | 4.1 | on | query the terminal | S-irnsu4to |
| `omit-term-workarounds` | 4.3 | off | skip terminal workarounds | S-irnsu4to |

Related: `security/fish-syntax-bash-differences.md`, `security/fish-variables-scopes-export.md`, `security/fish-config-files-completions.md` (4.3.0 `conf.d` theme migration), `security/fish-on-windows-wsl-cygwin-msys2.md` (the Windows-host notes of the same releases: WSL, Cygwin, MSYS2), `security/zsh-options-emulation-bash-differences.md` (zsh's analogous option and emulation mechanism).

## Examples
- SNIPPET: check which flags a fish has and opt in to one for a single run; context: fish 4.9.3, any host; checked: no [DER S-irnsu4to, S-f6olkobv: `status features` lists flags and `fish --features` enables them for one session]
```
status features
fish --features test-require-arg --debug=deprecated-test -c 'test "x"'
```
- SNIPPET: opt in for the user, persistently; context: fish 4.9.3; checked: no [DER S-irnsu4to: `fish_features` read at startup must be universal or exported]
```
set -U fish_features remove-percent-self test-require-arg
```
