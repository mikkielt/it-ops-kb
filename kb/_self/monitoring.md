# Monitoring: kbmon, one snapshot of the kb and its surroundings

`python3 _tools/kbmon.py` names seven panels (the kb, coord, running sessions, the query log, the host, the sprint and the log) and shows each whose module exists, as one JSON snapshot (`--json`) or as plain text (`--once`, or live without either). The facade `_tools/kbmon.py` holds the command line, the usage text and the exit codes; `_tools/mon_base.py` the panels, the run of a panel and the snapshot; `_tools/mon_view.py` the redaction and the text view; each panel is the module `_tools/mon_<name>.py` (`mon_kb.py` for the kb panel). A command's flags and exit codes are in `python3 _tools/kbmon.py --help` and `kb/_self/tools.md`.

## The snapshot

- **Schema 1.** `--json` prints one object: `schema` (1), `taken` (UTC time), `panels` and `alerts` (a list, empty until a panel judges its data). `panels` holds one entry for each of `kb`, `coord`, `sessions`, `querylog`, `host`, `sprint` and `log`, or only those `--panel NAME` (repeatable) names, in that order.
- **A panel has a state and seconds.** `state` is `ok`, `timeout`, `error`, `absent` or `unsupported`; `seconds` is how long the panel took (the timeout itself for `timeout`, 0 for `absent`); `data` holds the panel's object for `ok`, `{"error": ...}` for `error` and `{"reason": ...}` for `unsupported`, and is left out for `timeout` and `absent`.
- **A panel is a module.** `mon_<name>.py` has `collect(ctx)`, which returns the panel's data (a dict of JSON values) and reads without writing, and may have `lines(data)`, the text lines `--once` prints under the panel's heading. `collect` raises `mon_base.Unsupported` when this host or setting cannot give the panel (state `unsupported`), any other exception is state `error`; a panel with no module is `absent`. `ctx` holds the clone `root`, the coord `store`, `url` and `key_file` (`--root`, `--store`, `--url`, `--key-file`). All flags are defined by the facade, so a panel's module changes none of them.
- **Each panel runs in a daemon thread, all at once, bounded by `--timeout` seconds** (default 10). A panel still running then is `timeout` and its thread is left behind: a daemon thread never holds the process at exit, so the snapshot returns when the slowest bound passes, not when the slow source answers.
- **Exit codes.** 0 a snapshot was shown; 1 it was shown and its `alerts` are not empty; 2 a bad argument, or a `--from-snapshot` file that is unreadable or is no snapshot of schema 1.

## Read only and redacted

- **A run writes nothing and starts nothing.** It builds no pack index, runs no lookup eval, makes no network request and writes no file in the clone, the query log home or `_cache/`. The kb panel sets `KB_INDEX=0` for the rest of the process, so even the fingerprint memo the lookup tools keep in the index directory is not written.
- **Every printed string passes `redact.redact`**, in `--json` and in `--once`: each string and each key of the snapshot, and each line of the text view once more after a panel's own `lines` made it. A snapshot saved with `--json` and shown with `--from-snapshot FILE` passes the same rules, so a saved file that holds a token, a path or a host name prints with the query log's placeholders. The public root's content, which `redact` allows, is read only when a string matches an identifier shape (`mon_view.LazyKnown`).
- **The text view prints no control character** of a panel's text; an escape byte appears only with `--ansi`, which colours the state and clears the screen between live frames.

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
