# Monitoring: kbmon, one snapshot of the kb and its surroundings

`python3 _tools/kbmon.py` names seven panels (the kb, coord, running sessions, the query log, the host, the sprint and the log) and shows each whose module exists, as one JSON snapshot (`--json`), as plain text (`--once`) or live (without either), laid out as the Layout section gives it. The facade `_tools/kbmon.py` holds the command line, the usage text and the exit codes; `_tools/mon_base.py` the panels, the run of a panel and the snapshot; `_tools/mon_view.py` the redaction, the layout of the text view and the console's escape support; each panel is the module `_tools/mon_<name>.py` (`mon_kb.py` for the kb panel). A command's flags and exit codes are in `python3 _tools/kbmon.py --help` and `kb/_self/tools.md`.

## The snapshot

- **Schema 1.** `--json` prints one object: `schema` (1), `taken` (UTC time), `panels` and `alerts` (a list, empty until a panel judges its data). `panels` holds one entry for each of `kb`, `coord`, `sessions`, `querylog`, `host`, `sprint` and `log`, or only those `--panel NAME` (repeatable) names, in that order.
- **A panel has a state and seconds.** `state` is `ok`, `timeout`, `error`, `absent` or `unsupported`; `seconds` is how long the panel took (the timeout itself for `timeout`, 0 for `absent`); `data` holds the panel's object for `ok`, `{"error": ...}` for `error` and `{"reason": ...}` for `unsupported`, and is left out for `timeout` and `absent`.
- **A panel is a module.** `mon_<name>.py` has `collect(ctx)`, which returns the panel's data (a dict of JSON values) and reads without writing, and may have `lines(data)` or `lines(data, width)`, the panel's body rows (`width` is the columns the view may use), which the view prints under the panel's title behind the gutter. `collect` raises `mon_base.Unsupported` when this host or setting cannot give the panel (state `unsupported`), any other exception is state `error`; a panel with no module is `absent`. The coord panel also ends in `absent` or `timeout` by its own word, with `{"reason": ...}` as its data (see The coord panel). `ctx` holds the clone `root`, the coord `store`, `url` and `key_file` (`--root`, `--store`, `--url`, `--key-file`). All flags are defined by the facade, so a panel's module changes none of them.
- **Each panel runs in a daemon thread, all at once, bounded by `--timeout` seconds** (default 10). A panel still running then is `timeout` and its thread is left behind: a daemon thread never holds the process at exit, so the snapshot returns when the slowest bound passes, not when the slow source answers.
- **Exit codes.** 0 a snapshot was shown; 1 it was shown and its `alerts` are not empty; 2 a bad argument, or a `--from-snapshot` file that is unreadable or is no snapshot of schema 1.

## Read only and redacted

- **A run writes nothing and starts nothing.** It builds no pack index, runs no lookup eval, makes no network request (but for the coord panel's, to the `--url` server) and writes no file in the clone, the query log home or `_cache/`. The kb panel sets `KB_INDEX=0` for the rest of the process, so even the fingerprint memo the lookup tools keep in the index directory is not written.
- **Every printed string passes `redact.redact`**, in `--json` and in `--once`: each string and each key of the snapshot, and each line of the text view once more after a panel's own `lines` made it. A snapshot saved with `--json` and shown with `--from-snapshot FILE` passes the same rules, so a saved file that holds a token, a path or a host name prints with the query log's placeholders. The public root's content, which `redact` allows, is read only when a string matches an identifier shape (`mon_view.LazyKnown`).
- **The text view prints no control character** of a panel's text; an escape byte appears only in a frame that is coloured and redrawn in place (see The live view).

## Layout

`mon_view.render_text` lays out every frame. `W` is the terminal's columns less one (`COLUMNS`, else the terminal's size, else 80): the last column is never written, and no line is longer than `W`.

- **Rows, top to bottom.** The alert line while an alert is shown; the header; a blank row; the panels `kb`, `coord`, `sessions`, `querylog`, `host` and `sprint` with a blank row between; the log tail last, which fills the rest of the screen (three rows at least; a row that does not fit is cut at the bottom). Only the panels `--panel` names are shown, in that order.
- **Header.** `kbmon · YYYY-MM-DD HH:MM:SSZ · refresh Ns · frame n · root`, with a space, U+00B7, a space between the parts, the time in UTC and the root `.` for the clone the script is in. `kbmon` is bold.
- **Alert line.** `!! ALERT message — since HH:MM`, white bold on red when coloured; without colour a row of `W` `=` follows it. A second alert adds ` (+N more)`. The snapshot's `alerts` make kbmon exit 1.
- **Panel title**, at column 0: `name  state  S.Ss`. A state other than `ok` adds `  — reason` (the error text, the reason a panel is unsupported, `no answer in time` for a timeout, `no mon_<name>.py` for an absent panel) and has no body. The name is bold, the state coloured, and the rest dim when the state is not `ok`.
- **Body rows** sit behind a two-column gutter: two spaces, `! ` for a warning (the row in yellow) or `!!` for an error (red). A panel's own row that starts `! ` or `!!` keeps that gutter; any other row gets two spaces. The label starts at column 2 padded to 10 and the value at column 12; lists are joined by ` · `; a table has a lowercase header row, two-space gaps and its flags in the gutter.
- **Colour** is the 16 ANSI colours and bold, every coloured run ends in SGR 0: green (32) for `ok`, passed and bars under 80%; yellow (33) for a warning, `timeout`, `! ` rows and bars of 80 to 99%; red (31) for an error, `!!` rows and bars of 100% and more; white bold on red (1;97;41) for the alert line only; dim (90) for `absent`, `unsupported` and reasons; bold for names. Colour never carries meaning alone: the state is always written.
- **A narrow terminal**, in this order: under 100 columns the side blocks stack (coord events under the claims, the host's ceiling as 3 rows); lists wrap at an item and continue at column 12; tables shrink their gaps from 2 to 1, cut paths from the left as `…/`, then drop the lowest column; free text is cut at `W` with `…`; ids, counts and states are never cut. The view cuts any line that still passes `W` with `…`.
- **Glyphs** are ASCII and `·`, `—`, `–`, `…`.

## The live view

Without `--json` and `--once`, kbmon shows a frame every `--interval` seconds (1 to 300, default 5) until Ctrl-C or `--count` frames (1 or more; an `--interval` or `--count` out of bounds exits 2) and exits 0, or 1 when the last snapshot had an alert.

- **On a terminal, or with `--ansi`, the frame is redrawn in place:** each frame starts with the cursor-home and screen-erase sequences (`ESC[H`, `ESC[2J`) and is cut to the terminal's lines less one.
- **A pipe, a file, or `NO_COLOR` set, gives plain frames:** no escape byte, one frame after another with a blank row between, unless `--ansi` asks for the escapes. `--once` is always one plain frame, with escapes only for `--ansi`.
- **Windows.** `mon_view.enable_vt()` switches on the console's virtual terminal processing for standard output (`ctypes`, `SetConsoleMode`). It returns True off Windows and False where the console cannot take escapes (no console, a redirected output, an old console host); kbmon then writes plain frames one after another, with or without `--ansi`.

## The kb panel

`data` of `mon_kb.py`:

| key | holds |
|---|---|
| `roots` | per root: `root`, `articles`, `facts` by tag (`DOC`, `CODE`, `DER`, `COMMUNITY`, `UNK`, `DECISION`): the counts of `rag.py audit` |
| `gaps`, `conflicts` | the entries of every root's `_gaps.md` and `_conflicts.md` that no continuation line has settled (`kbfacts.OPEN_GAP`) |
| `refreshed` | the newest `retrieved_utc` of the articles, or null |
| `census`, `census_tag` | the newest date of a `_census/YYYY-MM-DD.csv` file and the newest `census-*` tag of the clone, or null |
| `eval` | `{state, when}` of the newest recorded lookup eval at a landing (the `land.step` ops row of `rag.py-eval`: `passed` for exit 0, else `failed`), or null; the panel never runs the eval, and the row holds no count of passed rows |
| `index_age_s` | seconds since the newest pack index file was written or last used, or null when there is none |

The panel reads the clone the script is in; `--root` naming another clone makes it `unsupported`.

## The coord panel

`data` of `mon_coord.py`:

| key | holds |
|---|---|
| `source` | `local` (the store) or `url` (a `coord.py serve` server) |
| `claims` | per live claim, in key order: `key`, `holder`, `left_s` (whole seconds left of the lease), `budget_usd`, `spend_usd` (null for a claim with no budget) and `over_budget` |
| `events` | the newest 10 events, newest first: `seq`, `kind` and `fields` |
| `digest` | the lines of `coord.py digest`: the live intents and claims, with the progress state of an intent's items |

- **Read through coord.py.** The panel runs `coord.py list`, `wait --since 0 --timeout 0` and `digest --key '*'` as three child processes at once, so it opens no SQLite file and no key file itself. The lease tokens `list` and `digest` leave out are never in the data, and the key file's content is never read or printed by kbmon.
- **Where it reads.** With `--url` (and `--key-file`, which coord.py reads) from the server, else from the store `--store` names, else `KB_COORD_STORE`, else the clone's default store.
- **Absent.** A local store file that is not there makes the panel `absent` and is not created (coord.py's own commands would create it).
- **Timeout.** A server that cannot be reached, or whose three commands take over 30 seconds, makes the panel `timeout` with `{"reason": ...}`; one that is reached and gives no answer is `timeout` when `--timeout` passes, whichever is sooner. The children are killed when kbmon exits. Any other failure of a command (a key file others can read, a refused token) is `error` with coord.py's last line.
- **View.** A table of key, holder, seconds left, budget and spend, a row over budget starting `! `; at 100 columns or more the newest 5 events sit beside it from column 52 under `events` (`#410  claim     topic/winget  w2`), below 100 under it; then up to two intent lines of the digest under `intents`.

## The sessions panel

`data` of `mon_sessions.py`:

| key | holds |
|---|---|
| `procs` | per process with a working directory in a checkout of the clone, in pid order (`backlog.py procs`' inventory): `pid`, `age_s`, `class` (`orphan`, `hook` or `foreign`), `checkout`, `session` and `item` |
| `worktrees` | per worktree of `git worktree list`: `path` and `branch` (null for a detached head) |
| `stalled` | per claimed or ready item with a signal of `backlog.py stalled`: `item` and `signals`; left out where the root has no backlog items |

- **Checkout, never an absolute path.** `checkout` and a worktree's `path` are relative to the clone: `.` is the clone itself, a worktree under it is its path under it (`.claude/worktrees/agent-ST-xxxxxxxx`), one outside it is its directory name alone, and a process in a subdirectory adds it (`./_tools`).
- **Session.** A process whose command name is `claude` is a Claude Code session: `headless`, with `item` set to the id in the branch, when its checkout is a worktree on a `work/<id>` branch, else `interactive`. Any other process has null `session` and `item`. A directory name that two worktrees share names no branch, so a process in one is `interactive`. The command line of a process is never read.
- **Stalled.** The signals are those of `backlog.py stalled`, read without the forge: the panel starts no network request, so `mr-dead` is never in `signals` and an item with only an unknown signal is left out.
- **Unsupported.** A host that cannot list working directories (Windows, or no `/proc` and no `lsof`) makes the panel `unsupported`, with the reason of `backlog.py procs`.
- **View.** A table of pid, age, class, session, item and checkout, an orphan's row starting `! ` and orphans first (12 rows at most, then `+N more`); `worktrees` with `path  branch` joined by ` · `, those on a `work/` branch first (12 at most); then a `! ` row for each stalled item with its id and signals.
