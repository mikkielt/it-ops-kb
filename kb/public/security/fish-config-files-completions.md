---
topic: security/fish-config-files-completions
priority: P3
applies_to: "fish 4.9.3 startup configuration (config.fish, conf.d snippets, vendor directories, login shell choice, invocation flags, WSL and Cygwin notes) and the completion system (complete, completions directories, fish_complete_path, wrapping)"
retrieved_utc: 2026-10-15
sources: [S-irnsu4to, S-bdc6dn7m, S-f6olkobv, S-c5jost2j, S-eg4rjgcz, S-kcajyom3, S-pmqazcbs, S116]
status: complete
---

# fish configuration files and completions

## Summary
fish has one user file, `~/.config/fish/config.fish`, and it is read by every fish process, interactive or not, login or not, which is the largest difference from `.bashrc` and `.profile`. Before it, fish sources the `*.fish` snippets of `conf.d` directories (user, system, then vendor), and the system `/etc/fish/config.fish` comes between the snippets and the user file, so the user file has the last word. Anything in these files that prints must be guarded with `status is-interactive`, or `ssh`, `scp` and `rsync` break. Completions are separate: a file `COMMAND.fish` in a directory of `fish_complete_path` is autoloaded when that command is completed, and `complete` defines the rules. The manual read here is fish 4.9.3; what the notes say about fish under WSL, Cygwin and MSYS2 on a Windows host (the Windows `PATH`, `.exe` completions) is in `security/fish-on-windows-wsl-cygwin-msys2.md`.

## Facts
- The main file is `~/.config/fish/config.fish`, more precisely `$XDG_CONFIG_HOME/fish/config.fish`, available as `$__fish_config_dir`. Configuration runs in this order: the `*.fish` snippets of `conf.d` directories, then the system-wide `config.fish` in `$__fish_sysconf_dir` (usually `/etc/fish/config.fish`), then the user's `config.fish`, which is sourced after the snippets so that it can override them. The `conf.d` directories are `$__fish_config_dir/conf.d`, `$__fish_sysconf_dir/conf.d`, the directories under `$__fish_user_data_dir` (usually `~/.local/share/fish`) and `fish/vendor_conf.d` in each `XDG_DATA_DIRS` directory, also listed in `$__fish_vendor_confdirs`. [DOC S-irnsu4to]
- Of several snippets with the same file name in these directories only the first is run, and snippets run in natural sort order of file name, so `01` sorts before `2`. Changing `$__fish_vendor_confdirs` in a running shell does nothing, because the directories were already read. [DOC S-irnsu4to]
- Unlike `.bashrc` and `.profile`, `config.fish` is always read, even by non-interactive and login shells, and a command meant only for an interactive shell is guarded with `status is-interactive`. If `config.fish` prints output, `ssh`, `scp` and `rsync` can fail with messages such as "Received message too long" or "Bad packet length" when fish is the login shell, and so can an unguarded `tmux` start; the FAQ's fix is to guard output with `status is-interactive` or `status is-login`. [DOC S-bdc6dn7m]
- The manual discourages software from installing system-wide fish configuration, since a badly written snippet can have side effects or slow startup and users of other shells do not benefit; where one is needed it goes in the vendor directory printed by `pkg-config --variable confdir fish`. fish also ships `__fish_build_paths.fish`, which a build can customise for system-specific paths. [DOC S-irnsu4to]
- `fish -c COMMAND` runs a command, `-C` or `--init-command` runs commands after reading the configuration and before `-c` or interactive input, `-N` or `--no-config` skips configuration files, `-n` only checks syntax, `-l` acts as a login shell and `-P` starts in private mode without history. `fish --profile-startup FILE -ic exit` writes timing for startup and the manual's example sorts it with `sort -nk2` to find what slows a configuration. [DOC S-f6olkobv]
- Since 4.3.0 fish sets no user-facing universal variables by default and, once on upgrade, migrates the old universal theme and key-binding variables into `conf.d/fish_frozen_theme.fish` and `conf.d/fish_frozen_key_bindings.fish`, which the release notes suggest deleting in favour of settings in `config.fish`. Since 4.8.0 fish tries harder to detect that a theme matches a historical default and then does not create `fish_frozen_theme.fish` when upgrading from before 4.3. 4.3.2 fixed the sample `config.fish` and the `conf.d`, `completions` and `functions` directories being recreated on every startup. [DOC S-eg4rjgcz]
- Since 4.7.0 an empty `XDG_DATA_DIRS` is treated as its default, so vendor directories such as `share/fish/vendor_completions.d` are used again, and 4.8.0 stopped installing files under `share/fish/completions` and `share/fish/functions`, which had been ignored since 4.2. [DOC S-eg4rjgcz]
- Making fish the login shell takes `command -v fish | sudo tee -a /etc/shells` and `chsh -s "$(command -v fish)"`, and the manual warns it can cause an incorrect `PATH` and that fish may not suit systems that need a Bourne-compatible login shell reading `/etc/profile`. A simpler route is to set the terminal emulator to start fish directly, which leaves the login shell unchanged. [DOC S-c5jost2j]
- A completion rule is written with `complete -c COMMAND`; `-s` adds a short option, `-l` a GNU long option and `-o` an old-style option, and the string given to `-a` is tokenised on spaces and tabs at completion time, with expansion and command substitution done then. Option arguments are optional by default, so candidates are offered only attached (`-ofile`, `--output=`); `-r` requires a parameter in the next word, `-f` forbids file completion and `-F` forces it back. [DOC S-pmqazcbs]
- `-n` or `--condition` offers a completion only if the given command succeeds, and several conditions are tried in the order given until one fails. `complete -c NEW -w EXISTING` makes `NEW` inherit the completions of `EXISTING`, wrapping is transitive, and it works only for rules given with `-c`, not `-p`. Repeated `complete` calls for a command add to what is already defined, `complete -c COMMAND -e` erases all of its completions, and `complete -C STRING` prints the completions for a string. [DOC S-kcajyom3]
- A completion file must be named after the command with the suffix `.fish`, and fish searches `$fish_complete_path`, using the first file found: `~/.config/fish/completions`, `/etc/fish/completions`, `~/.local/share/fish/vendor_completions.d`, `/usr/share/fish/vendor_completions.d`, the completions built into fish (`status list-files`) and those generated from man pages in `~/.cache/fish/generated_completions`. Software that ships fish completions installs them in the vendor completions directory printed by `pkg-config --variable completionsdir fish`. Functions whose names begin with `__fish_` are internal to fish and their name and interface may change in future versions. [DOC S-pmqazcbs]
- Since 4.8.0 the `--command` and `--path` options of `complete` no longer unescape their argument, and since 4.3.3 `abbr`, `bind`, `complete`, `functions`, `history` and `type` accept `--color`. [DOC S-eg4rjgcz]
- `-p` names a command by its absolute path, which may contain wildcards, instead of by name, and `-x` is short for `-r` and `-f` together. [DOC S-kcajyom3]
- The kb's DSC article lists `fish` among the shells for `dsc completer`; the generated script would be saved as `dsc.fish` in a `completions` directory to be autoloaded when `dsc` is completed. [DER S-pmqazcbs, S116: a completion file is named after the command with the suffix `.fish`, and `dsc completer fish` writes a script to standard output]
- A default an administrator places in `/etc/fish/conf.d` or `/etc/fish/config.fish` is a default, not an enforced setting: the user's `config.fish` runs after both and can override it, so a managed baseline for fish cannot rest on those files alone. [DER S-irnsu4to: the snippets and the system `config.fish` run before the user's `config.fish`]

## Reference
| order | what runs | location | source |
|---|---|---|---|
| 1 | snippets `*.fish` | `~/.config/fish/conf.d`, `/etc/fish/conf.d`, vendor `conf.d` | S-irnsu4to |
| 2 | system `config.fish` | `/etc/fish/config.fish` | S-irnsu4to |
| 3 | user `config.fish` | `~/.config/fish/config.fish` | S-irnsu4to |

| completion source (first match wins) | usual path | source |
|---|---|---|
| user | `~/.config/fish/completions` | S-pmqazcbs |
| administrator | `/etc/fish/completions` | S-pmqazcbs |
| user vendor | `~/.local/share/fish/vendor_completions.d` | S-pmqazcbs |
| system vendor | `/usr/share/fish/vendor_completions.d` | S-pmqazcbs |
| built in | in the fish binary, `status list-files` | S-pmqazcbs |
| man-page generated | `~/.cache/fish/generated_completions` | S-pmqazcbs |

Related: `security/fish-on-windows-wsl-cygwin-msys2.md`, `security/fish-functions-abbreviations-events.md`, `security/fish-variables-scopes-export.md`, `security/fish-syntax-bash-differences.md`, `dsc/cli-reference.md` (`dsc completer fish`), `security/zsh-completion-system.md`, `security/zsh-startup-files-invocation.md` (the zsh counterpart), `security/gentoo-in-wsl.md` (a Linux distribution on a Windows host), `windows/openssh-server.md` (the default shell of an SSH session on Windows).

## Examples
- SNIPPET: a guarded `config.fish` so that non-interactive sessions stay silent; context: fish 4.9.3, placeholder abbreviation and variable; checked: no [DER S-bdc6dn7m: output in `config.fish` is produced by non-interactive shells too, so it is guarded with `status is-interactive`]
```
# ~/.config/fish/config.fish
set -gx PL_EXAMPLE_REGION emea        # safe: no output
if status is-interactive
    abbr --add gst git status
    echo "welcome to PL-LT-00123"
end
```
- SNIPPET: a small completion file autoloaded by name; context: fish 4.9.3, placeholder command `pl-tool`; checked: no [DER S-pmqazcbs, S-kcajyom3: a completion file is `COMMAND.fish` in `fish_complete_path`, and `-f`, `-n` and `-a` are the documented switches]
```
# ~/.config/fish/completions/pl-tool.fish
complete -c pl-tool -f
complete -c pl-tool -n "not __fish_seen_subcommand_from start stop" -a "start stop"
complete -c pl-tool -l verbose -s v -d "print more output"
```
