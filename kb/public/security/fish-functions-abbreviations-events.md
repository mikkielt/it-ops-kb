---
topic: security/fish-functions-abbreviations-events
priority: P3
applies_to: "fish 4.9.3 functions, autoloading from fish_function_path, aliases as wrapper functions, abbreviations (abbr), and event handlers (--on-event, --on-variable, --on-signal, --on-job-exit, --on-process-exit)"
retrieved_utc: 2026-10-15
sources: [S-irnsu4to, S-sjzqydvb, S-mmucfvjk, S-bdc6dn7m, S-eg4rjgcz]
status: complete
---

# fish functions, abbreviations and event handlers

## Summary
A fish function is a named list of commands, and the same mechanism covers what other shells call aliases, the prompt and event handlers. Functions are autoloaded by name from the directories in `fish_function_path`, so a file `NAME.fish` holds the function `NAME`; an event handler is the exception, because it only exists once its file has been loaded, which is why handlers belong in `config.fish` or `conf.d`. An abbreviation is not a function: it is a word that the interactive command line expands when space or enter is pressed, and it is never expanded in a script. The manual read here is fish 4.9.3. Variables used inside functions are in `security/fish-variables-scopes-export.md`.

## Facts
- `function NAME [OPTIONS]; BODY; end` defines a function: a list of commands that run when the name of the function is given as a command. `-a` or `--argument-names` assigns successive arguments to names while they stay available in `$argv`, unless `--inherit-variable argv` was used or `argv` is one of the names. [DOC S-sjzqydvb]
- A function name cannot be empty, may not begin with a hyphen and may not contain a slash; any other character, including a space, is valid. [DOC S-irnsu4to]
- Function names cannot be reserved words, among them `if`, `set`, `end`, `command`, `builtin`, `string`, `status`, `test` and `time`. [DOC S-sjzqydvb]
- `funced` edits a function and `funcsave` saves it to a function file that fish autoloads when needed. When fish needs a function it searches the directories in `$fish_function_path` for `NAME.fish` and loads the first it finds, by default `~/.config/fish/functions`, `/etc/fish/functions` and the `vendor_functions.d` directories under the user data directory and `XDG_DATA_DIRS`. An autoloaded file is loaded by name, so a file with several functions is read only when the function sharing the file's name is run; if the file does not define the function, fish does not read further autoload files and goes on to builtins and commands, which lets a user mask an administrator's function. [DOC S-irnsu4to]
- An autoloaded function becomes available to all running shells, and a changed definition is reloaded by running shells after a while. Software that ships fish functions installs them to the vendor functions directory, whose path `pkg-config --variable functionsdir fish` prints. fish has no separate alias concept: `alias` immediately creates a wrapper function, `alias --save` or `funcsave` keeps it in an autoload file, and a wrapper with the name of the command it wraps must call `command NAME $argv` to avoid calling itself. [DOC S-irnsu4to]
- `-w` or `--wraps` makes the function inherit the completions of the wrapped command, and is ignored when the wrapped command is the function's own name. `-d` gives a description suitable as a completion description. fish has no closures: `-S` or `--no-scope-shadowing` shares the scope of the caller at call time, not of the definition, and `-V` or `--inherit-variable NAME` snapshots a variable's value as a local when the function is defined. [DOC S-sjzqydvb]
- The manual warns that a function with the name of an existing builtin or common program that behaves differently often breaks fish or others' scripts, and suggests an abbreviation for replacing one tool with another for interactive use. The switches `--on-event`, `--on-variable`, `--on-job-exit`, `--on-process-exit` and `--on-signal` make a function run automatically at specific events, and `-e`, `-v`, `-j`, `-p` and `-s` are their short forms. [DOC S-sjzqydvb]
- Named events fish emits include `fish_prompt`, `fish_preexec`, `fish_postexec`, `fish_posterror`, `fish_exit`, `fish_cancel`, `fish_focus_in` and `fish_focus_out`; the `fish_preexec` and `fish_postexec` handlers receive the command line as first parameter and are not emitted for an empty command. Any other event name can be fired with `emit NAME args...` without being defined first, and the handler receives the arguments. With several handlers for one event all run, but the order may change between releases and should not be relied on. [DOC S-irnsu4to]
- A handler is active only once its function is loaded, so it must be sourced or executed, for example from the configuration file, and cannot rely on autoloading. [DOC S-irnsu4to]
- A `--on-variable` handler is not guaranteed to run for every `set`: it may be skipped for some values or run when the value is set to the same value; for a universal variable changed in another shell only real value changes are picked up. `--on-signal` takes a number or a name such as `SIGHUP` or `HUP`, only for signals delivered to fish itself (Ctrl-C goes to the foreground process group), and observing a signal stops fish from exiting on it. `--on-job-exit PID` accepts `caller` inside a command substitution, and neither job nor process handlers trigger for disowned jobs. [DOC S-sjzqydvb]
- Events are received only within the current fish process; there is no way to send an event from one fish process to another. [DOC S-sjzqydvb]
- `abbr --add NAME EXPANSION` creates an abbreviation: a word replaced by a longer phrase when it is typed and space or enter is pressed, and `ctrl-space` inserts a space without expanding. Only typed-in commands use abbreviations; they are not expanded in scripts. An abbreviation expands only in command position by default (`--position command`); `--position anywhere` expands it in any position, and `--command CMD` limits it to arguments of that command and implies `anywhere`. [DOC S-mmucfvjk]
- `--regex PATTERN` matches the whole token with a PCRE2 pattern instead of the literal name, and with several matches the last abbreviation added is used. `--function FUNC` calls a function with the matching token and replaces the token by its output only when its exit status is 0; `--set-cursor` moves the cursor to a marker, `%` by default. Since fish 3.6.0 abbreviations can no longer be saved in universal variables; they are added with `abbr --add` lines in `config.fish` or a `conf.d` file, and `abbr` output can be redirected to such a file. [DOC S-mmucfvjk]
- Since 4.0.0 an abbreviation can be restricted to specific commands, and since 4.9.0 it can carry a description shown in the completion pager. [DOC S-eg4rjgcz]
- The history substitution `!!` is not supported by fish; the FAQ's replacement is an abbreviation with `--position anywhere --function` that returns `$history[1]`. [DOC S-bdc6dn7m]
- A script run under fish gets no abbreviations, so an automation must call the real command or function; an abbreviation is a convenience for a human at the prompt and should not be used to change what a tool does for a script. [DER S-mmucfvjk, S-sjzqydvb: abbreviations expand only for typed commands, while a function with a builtin's name changes behaviour for scripts too]

## Reference
| mechanism | defined with | active where | autoloaded | source |
|---|---|---|---|---|
| function | `function NAME ... end` | scripts and prompt | yes, from `fish_function_path` | S-irnsu4to |
| alias | `alias NAME CMD` (makes a function) | scripts and prompt | only if saved | S-irnsu4to |
| abbreviation | `abbr --add NAME ...` | typed commands only | no, put in a configuration file | S-mmucfvjk |
| event handler | `function ... --on-event NAME` | after its file is loaded | no | S-irnsu4to |

| handler switch | fires on | source |
|---|---|---|
| `--on-event NAME` | a named event (`fish_prompt`, `fish_exit`, custom via `emit`) | S-irnsu4to, S-sjzqydvb |
| `--on-variable NAME` | a change of the variable | S-sjzqydvb |
| `--on-signal SIG` | a signal delivered to fish | S-sjzqydvb |
| `--on-job-exit PID` | the job holding that process exits | S-sjzqydvb |
| `--on-process-exit PID` | that child process exits | S-sjzqydvb |

Related: `security/fish-variables-scopes-export.md`, `security/fish-config-files-completions.md` (where a handler or abbreviation is kept), `security/fish-syntax-bash-differences.md`, `security/zsh-completion-system.md` (zsh's own hook mechanism).

## Examples
- SNIPPET: a saved wrapper function and its abbreviation, placed so that the abbreviation is loaded at startup; context: fish 4.9.3, placeholder command name `pl-status`; checked: no [DER S-irnsu4to, S-mmucfvjk: a function file named after the function is autoloaded, and an abbreviation must be added by a configuration file]
```
# ~/.config/fish/functions/pl-status.fish
function pl-status --description 'show service state'
    command systemctl status $argv
end

# ~/.config/fish/conf.d/abbreviations.fish
abbr --add pls pl-status
```
- SNIPPET: an event handler in a configuration file; context: fish 4.9.3, prints the finished command line to standard error after every interactive command; checked: no [DER S-irnsu4to: a handler is active only once its function is loaded, so it is placed in `conf.d`]
```
# ~/.config/fish/conf.d/postexec_note.fish
function note_command --on-event fish_postexec
    echo "finished: $argv[1]" >&2
end
```
