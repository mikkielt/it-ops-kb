---
topic: claude/terminal-split-pane
priority: P3
applies_to: "tmux 3.8 manual (tag published 2026-09-09), WezTerm docs and release 20240203-110809-5046fc22, Windows Terminal command-line-arguments page (updated 2025-11-12); read 2026-10-18"
retrieved_utc: 2026-10-18
sources: [S-3gv2hqon, S-ul3bejly, S-jrp4n5ie, S-z4bixz66, S-4ingl4hx, S-fsgzj2gz, S-rwjcajd5]
status: partial
---

# Opening a pane beside the running terminal session: tmux, WezTerm and Windows Terminal

## Summary
Each of the three terminals splits the pane the caller runs in from a command line and starts a program in the new one:
`tmux split-window` (`-h`, `-l`, `-c`, `-d`, `-T`), `wezterm cli split-pane` (`--right`, `--percent`, `--cwd`, `-- PROG`)
and `wt split-pane` (`-V`, `-s`, `-d`, a trailing command line). tmux and WezTerm name the pane to split by an
environment variable the pane's own processes inherit (`TMUX_PANE`, `WEZTERM_PANE`); the Windows Terminal page documents
no such variable and no way to name the caller's pane. WezTerm's last tagged release is from February 2024, shipped as a
zip and a `setup.exe` for Windows and a zip for macOS, each beside a `.sha256` file.

## Facts
### tmux (manual of tag 3.8, released 2026-09-09)
- `split-window` creates a new pane by splitting `target-pane` (`-t`); with `-d` the session does not make the new pane the current pane. The synopsis lists `-bdefhIkPvZ`, `-B`, `-c start-directory`, `-e environment`, `-F format`, `-l size`, `-m
  message`, `-p percentage`, `-R`, `-s`, `-S`, `-t target-pane`, `-T title` and `[shell-command [argument ...]]`. [DOC S-3gv2hqon]
- `-h` does a horizontal split and `-v` a vertical split, and `-v` is assumed when neither is given; `-l` is the new
  pane's size in lines (vertical split) or columns (horizontal split), and a trailing `%` makes it a percentage of the
  available space; `-p` is a shorthand for the percentage. `-b` puts the new pane to the left of or above the target
  pane, and `-f` makes it span the full window height (with `-h`) or width (with `-v`). [DOC S-3gv2hqon]
- `-T` sets the pane title; `-k` keeps the pane open after the command exits, until a key is pressed (`remain-on-exit-format`
  sets the message), and `-m message` is `-k` with that message. [DOC S-3gv2hqon]
- `split-window` accepts the command as several arguments and runs it directly, without `sh -c`, which avoids shell
  quoting; a single string argument is passed to the shell. The pane's own processes get its id in the `TMUX_PANE`
  environment variable. [DOC S-3gv2hqon]
- The 3.8 manual describes `-c start-directory` for `new-window` ("the working directory in which the new window is
  created"), `respawn-pane` and `respawn-window`, but its `split-window` entry lists `-c`, `-e`, `-P` and `-F` in the
  synopsis only and carries no prose for them. [UNK: the 3.8 manual read gives no sentence for `split-window -c`, `-P` or `-F`]
- The 3.8 manual documents `new-pane`, which creates a floating pane; its options "have the same meaning as for the `split-window`
  command", and `-L` makes it behave like `split-window`. [DOC S-3gv2hqon]
- tmux 3.8 was published 2026-09-09 as the latest GitHub release at the time of reading; which version a given host ships
  (a distribution package, or the WSL one) was not read. [UNK: installed versions differ per host; the `-T` and `new-pane` entries are read from 3.8 only]

### WezTerm (`wezterm cli split-pane`)
- `wezterm cli split-pane` splits the current pane and spawns a command in the new one, and prints the new pane's id on
  success; with no arguments it splits to the bottom and runs the default command. [DOC S-ul3bejly]
- Direction: `--left`, `--right`, `--top`, `--bottom`; `--horizontal` is the same as `--right`, and with no direction the
  default is `--bottom`; `--top-level` splits the whole window instead of the active pane. [DOC S-ul3bejly]
- Size: `--cells N` is the new pane's size in cells (50% of the available space when omitted) and `--percent N` is a
  percentage of the available space; the page's example `--left --percent 30` makes a 30% split to the left. [DOC S-ul3bejly]
- A program is passed after the options, and the page recommends `--` before it so its own parameters are not read as
  `split-pane` options (`wezterm cli split-pane -- bash -l`); `--cwd` sets the new program's working directory;
  `--move-pane-id` moves an existing pane into the split instead of spawning one. [DOC S-ul3bejly]
- `--pane-id` names the pane to split; without it the pane is the one in the `WEZTERM_PANE` environment variable, and
  without that the focused pane of the most recently interacted client session. [DOC S-ul3bejly, S-jrp4n5ie]
- The latest non-prerelease GitHub release read on 2026-10-18 is `20240203-110809-5046fc22`, published 2024-02-03. Its files
  for macOS and Windows are `WezTerm-macos-<tag>.zip`, `WezTerm-windows-<tag>.zip` and `WezTerm-<tag>-setup.exe`; Linux
  files are an AppImage, `.deb`, `.tar.xz` and `.rpm` for named distributions, and most files have a `.sha256` file beside
  them, including the macOS zip, the Windows zip and the `setup.exe`. [DOC S-4ingl4hx]
- The Windows checksum file of that release, downloaded on 2026-10-18, is one line: 64 hexadecimal characters, two spaces,
  then the zip's file name (the `sha256sum` layout). The other files' checksum files were not opened. [DER S-4ingl4hx: one download on 2026-10-18 of `WezTerm-windows-<tag>.zip.sha256`]
- WezTerm needs 64-bit Windows 10.0.17763 or later (Pseudo Console support). The `setup.exe` installer is built with
  Inno Setup, needs administrator rights, installs under Program Files and adds itself to `PATH`, and takes the
  standard Inno Setup command-line options; the zip runs from any folder with no special privileges. `winget install
  wez.wezterm` also installs it. [DOC S-z4bixz66]

### Windows Terminal (`wt split-pane`)
- `wt.exe`, or the execution alias `wt`, opens Windows Terminal; its line is `wt [options] [command ; ]`, commands are
  separated by semicolons, and `new-tab` is the default command. `-w`/`--window` takes a window id or name, with `new` or
  `-1` for a new window and `last` or `0` for the most recently used window; an id that does not exist creates a window
  with that id. [DOC S-fsgzj2gz]
- `split-pane` (alias `sp`) takes `-H`/`--horizontal` or `-V`/`--vertical`, `-p`/`--profile`, `-d`/`--startingDirectory`,
  `--title`, `--tabColor`, `-s`/`--size` (a float, the portion of the parent pane, `.4` for 40%), `-D`/`--duplicate`,
  `--suppressApplicationTitle`, `--useApplicationTitle`, `--colorScheme`, and a trailing `commandline` (an executable with
  optional arguments). [DOC S-fsgzj2gz]
- The `splitPane` action halves the active pane (default size `0.5`, a fraction of the current pane), takes `split` values
  `up`, `right`, `down`, `left`, `auto`, `horizontal` or `vertical`, and `"auto"` splits in the direction that gives the
  most surface area. [DOC S-rwjcajd5]
- From PowerShell the semicolon between commands must be escaped with a backtick (or the line follows `--%`); from a WSL
  shell the execution alias does not work, and the page spawns it through `cmd.exe /c "wt.exe" ... \; split-pane ...`.
  [DOC S-fsgzj2gz]
- The command-line page says `-H` splits horizontally and `-V` vertically but does not say on which side of the active pane
  the new pane appears, whether `wt -w 0 split-pane` splits the pane the command was typed in or the active pane of the
  last used window, or that any environment variable names the caller's pane. [UNK: looked in the command-line-arguments and actions pages, 2026-10-18; needs a run on Windows Terminal]
- To make `wt` resolvable, the "app execution alias" for Windows Terminal (on by default) must be on in the Manage app
  execution aliases page; `%LOCALAPPDATA%\Microsoft\WindowsApps` should be on `PATH`. [DOC S-fsgzj2gz]

### How it fits
- A launcher that starts a side pane for a long-running viewer picks the terminal from the environment its own process
  inherited: `TMUX_PANE` set means tmux, `WEZTERM_PANE` set means WezTerm; neither gives a pane to split in Windows
  Terminal on the documented evidence, so `wt` splits the active pane of a window chosen with `-w`. [DER S-3gv2hqon, S-ul3bejly, S-fsgzj2gz: each tool's documented pane variable or its absence]
- The three size options are not the same unit: tmux `-l 40%` and WezTerm `--percent 40` are percentages of the available
  space, WezTerm `--cells 40` and tmux `-l 40` are cells, and Windows Terminal `-s .4` is a fraction of the parent pane.
  [DER S-3gv2hqon, S-ul3bejly, S-fsgzj2gz: the three size options as documented]

## Reference
- tmux manual, `split-window`: https://raw.githubusercontent.com/tmux/tmux/3.8/tmux.1
- WezTerm: https://wezterm.org/cli/cli/split-pane.html, https://wezterm.org/cli/cli/index.html, https://wezterm.org/install/windows.html
- Windows Terminal: https://learn.microsoft.com/en-us/windows/terminal/command-line-arguments,
  https://learn.microsoft.com/en-us/windows/terminal/customize-settings/actions
- Related articles: [mods.md](mods.md) (a pane drawn inside Claude Code), [skills-and-subagents.md](skills-and-subagents.md)
  (agent teams use tmux or iTerm2 panes), [parallel-sessions.md](parallel-sessions.md).

## Examples
- SNIPPET: a viewer in a side pane to the right, 40% wide, in a project directory, per terminal; context: tmux 3.8, a WezTerm
  CLI, Windows Terminal; `viewer` is a placeholder program; checked: no [DER S-3gv2hqon, S-ul3bejly, S-fsgzj2gz]

```text
tmux split-window -d -h -l 40% -T viewer viewer
wezterm cli split-pane --right --percent 40 --cwd /work/project -- viewer
wt -w 0 split-pane -V -s .4 -d C:\work\project viewer
```
