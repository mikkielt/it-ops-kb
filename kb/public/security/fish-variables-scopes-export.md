---
topic: security/fish-variables-scopes-export
priority: P3
applies_to: "fish 4.9.3 variables: the four scopes (universal, global, function, local), export to child processes, universal variables on disk, lists and slices, PATH variables, argv and argparse, status variables"
retrieved_utc: 2026-10-15
sources: [S-irnsu4to, S-4tb7t5c2, S-bdc6dn7m, S-eg4rjgcz]
status: complete
---

# fish variables, scopes and export

## Summary
Every fish variable is a list and has one of four scopes: universal (shared by all of a user's sessions and kept on disk), global (the session), function and local (the current block). Whether a variable reaches child processes is a separate bit, set with `-x` and cleared with `-u`, not a scope. `set` picks the scope by fixed rules: an explicit flag wins, else the narrowest existing variable is changed, else a new variable is function-local inside a function and global outside one. The manual read here is fish 4.9.3. What the manual says about fish on a Windows host (WSL, Cygwin, MSYS2) is in `security/fish-on-windows-wsl-cygwin-msys2.md`, and syntax differences against Bash are in `security/fish-syntax-bash-differences.md`.

## Facts
- A variable name cannot be empty and may contain only letters, digits and underscores, at any position. fish has four variable scopes: universal variables are shared by all of a user's sessions on one computer and persist across reboots, global variables belong to the current session, function variables go out of scope when the function ends, and local variables belong to the current block. A block, for local scope, begins with `for`, `while`, `if`, `function`, `begin` or `switch` and ends with `end`; outside a block local scope is the same as function scope. [DOC S-irnsu4to]
- `set` takes `-U`, `-g`, `-f` and `-l` for universal, global, function and local scope; a variable of the same name in another scope is not changed when a scope is given. When no scope is given and the variable exists, the one in the smallest scope is modified and its scope is not changed; when it does not exist, it is created in function scope inside a function and in global scope when no function is running. [DOC S-4tb7t5c2]
- A reader sees the variable of the smallest scope, so a local shadows a global or universal variable of the same name, and a variable set inside a function is not visible to a function it calls unless it is global or exported. A called function cannot change the caller's local variables: `set phrase x` in a callee leaves the caller's `set --local phrase` untouched. The manual's guidance is to use function-scoped variables when in doubt, global for what must be reachable everywhere, universal for persistent configuration and local for a short block. [DOC S-irnsu4to]
- Exporting is not a scope but an additional state, so a variable can be global and exported, local and exported or universal and exported. A global variable is accessible to functions whether or not it is exported; a local exported variable is copied into functions, so a function cannot change it outside, and is still passed to commands. The manual's convention is uppercase names for exported variables and lowercase for unexported ones, as in `set -gx EDITOR emacs -nw`. [DOC S-irnsu4to]
- When an exported variable goes out of scope it is unexported. [DOC S-4tb7t5c2]
- `VAR=value command` overrides a variable for one command, supported since fish 3.1; fish sets it before it expands the rest of the line, so `foo=gagaga echo $foo` prints `gagaga` where other shells may print the old value. A variable override does not stop alias or function lookup, so the same command runs as without the override. Universal variables are stored in `~/.config/fish/fish_variables`, which the manual says not to edit by hand because edits may be overwritten, and changes propagate instantly to all running sessions. [DOC S-irnsu4to]
- The manual says not to append to a universal variable in `config.fish`, because it then grows with each new shell; set it once at the command line. [DOC S-irnsu4to]
- `set -Ux EDITOR vim` can appear to do nothing because an environment variable inherited at startup is imported as a global variable, and the global value wins over the universal one; the FAQ's fix is a `set -gx` line in `config.fish`. The FAQ gives `set -x key value` (typically `set -gx`) to set an environment variable and `set -e key` to clear it, and `set -q var` to test whether a variable is defined. [DOC S-bdc6dn7m]
- `set -q` sets the status to the number of variables not found, up to 255, and 255 when no variable was given; it can test a scope or an attribute such as `--export`. `set -S` (`--show`) describes a variable: the scopes it is set in, its values in each and whether it is exported; `set` alone prints all variables in sorted order and a scope or export flag filters it. All options of `set` must come before other arguments, so `set flags -l` assigns the value `-l` to `flags` and does not make it local. [DOC S-4tb7t5c2]
- In assignment mode `set` leaves `$status` as it was, including a status from a command substitution, which is what lets `if set output (command)` test the command. `--no-event` sets or erases a variable without firing a variable change event, useful inside a variable handler. [DOC S-4tb7t5c2]
- Variables are lists: an unquoted variable expands to one argument per element, an empty list to nothing, and inside double quotes to exactly one argument with the elements joined by spaces. Indexes start at 1, a negative index counts from the end, a range such as `$fruit[-2..-1]` is a slice, and an invalid index silently gives no value, not even an empty string. Lists are one-dimensional and cannot contain other lists. [DOC S-irnsu4to]
- Since 4.9.0 list indexing can be nested in more cases (`$foo[$bar[1] 2]`), and a variable containing a closing square bracket no longer ends a slice early. [DOC S-eg4rjgcz]
- `set -a` appends and `set -p` prepends values, and neither works on a slice; `set -e name[2]` erases one element. [DOC S-4tb7t5c2]
- Every variable whose name ends in `PATH` (case-sensitive), such as `PATH`, `CDPATH`, `MANPATH` and `PYTHONPATH`, is a path variable: it is a list that is split and joined on colons, and exported in the colon form; for that reason no element can contain a colon. [DOC S-irnsu4to]
- `--path` and `--unpath` mark or unmark any other variable as a path variable. [DOC S-4tb7t5c2]
- A list that is not a path variable is exported joined with spaces, so `set -x smurf blue small` is seen by a child as `smurf=blue small`. `fish_user_paths` is a list of directories prepended to `PATH` and may be universal. `$argv` holds a function's or script's arguments and is defined only inside a function or when fish was started with arguments; `argparse` removes recognised options from it and sets `_flag_NAME` variables. [DOC S-irnsu4to]
- A dereference `$$name` uses the value of `$name` as a variable name, and the variable must be reachable from the function (global, universal or exported). A variable can hold a command (`set EDITOR emacs -nw; $EDITOR foo`) only as separate elements, and a keyword such as `if` or `command` cannot be taken from a variable. [DOC S-irnsu4to]
- Since 4.9.0 `status=123 echo $status` is an error and no longer silently ignores the override, and erasing a read-only variable with `set --erase` is rejected again. Since 4.3.0 fish no longer sets user-facing universal variables by default: the `fish_color_*`, `fish_pager_color_*` and `fish_key_bindings` variables are global, and 4.8.0 stopped creating `__fish_initialized`, so fish creates universal variables only when told to. [DOC S-eg4rjgcz]
- `-x` or `--export` exports a variable to child processes, `-u` or `--unexport` stops that, and with no option the variable's earlier export state is kept, or it is not exported if it never existed. [DOC S-4tb7t5c2]
- Because the universal file is plain storage on disk shared by every session of a user, a secret or token should not be set with `set -U`; a secret needed by one command belongs in a `VAR=value command` override or a `set -lx` inside a function, not in a universal or global exported variable. [DER S-irnsu4to, S-4tb7t5c2: universal variables persist in `fish_variables` and exported ones are inherited by every command started from the session]

## Reference
| scope | flag | lifetime | visible in called functions | source |
|---|---|---|---|---|
| universal | `-U` | on disk, all sessions, across reboots | yes | S-irnsu4to |
| global | `-g` | the session, until `set -e` | yes | S-irnsu4to, S-4tb7t5c2 |
| function | `-f` | until the function ends | no (unless exported and copied) | S-irnsu4to |
| local | `-l` | until the block ends | no | S-irnsu4to |

| option | effect | source |
|---|---|---|
| `-x`, `--export` | passed to child processes | S-4tb7t5c2 |
| `-u`, `--unexport` | not passed | S-4tb7t5c2 |
| `--path`, `--unpath` | colon-list semantics on or off | S-4tb7t5c2 |
| `-a`, `-p` | append, prepend | S-4tb7t5c2 |
| `-e`, `-q`, `-S` | erase, query, show | S-4tb7t5c2 |

Related: `security/fish-syntax-bash-differences.md`, `security/fish-functions-abbreviations-events.md` (variable event handlers), `security/fish-config-files-completions.md` (where `set -gx` lines live), `security/zsh-expansion-globbing-arrays.md` (arrays in zsh).

## Examples
- SNIPPET: export a variable for the session and override another for one command; context: fish 4.9.3, placeholder values only; checked: no [DER S-irnsu4to, S-4tb7t5c2: `-gx` is global and exported, and `VAR=value command` is a one-command override]
```
set -gx PL_EXAMPLE_ENV staging
PL_EXAMPLE_ENV=lab env | grep PL_EXAMPLE_ENV   # prints lab
echo $PL_EXAMPLE_ENV                           # still staging
```
- SNIPPET: function-local state that a callee cannot change; context: fish 4.9.3; checked: no [DER S-irnsu4to: a function's local variable is not visible to the function it calls]
```
function outer
    set -l phrase 'outer value'
    inner
    echo $phrase          # outer value
end
function inner
    set phrase 'inner value'   # creates a new function-scope variable in inner
end
```
