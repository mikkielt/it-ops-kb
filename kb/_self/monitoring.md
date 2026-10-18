# Monitoring: kbmon, one snapshot of the kb and its surroundings

`python3 _tools/kbmon.py` names seven panels (the kb, coord, running sessions, the query log, the host, the sprint and the log) and shows each whose module exists, as one JSON snapshot (`--json`), as metric points (`--metrics`), as plain text (`--once`) or live (without any of them), laid out as the Layout section gives it. The facade `_tools/kbmon.py` holds the command line, the usage text and the exit codes; `_tools/mon_base.py` the panels, the run of a panel and the snapshot; `_tools/mon_view.py` the redaction, the layout of the text view and the console's escape support; `_tools/mon_export.py` the metric points; each panel is the module `_tools/mon_<name>.py` (`mon_kb.py` for the kb panel). A command's flags and exit codes are in `python3 _tools/kbmon.py --help` and `kb/_self/tools.md`.

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

## The metric points

`--metrics` prints one JSON object: `schema` (1), `taken` and `points`, from the same snapshot as `--json` (so `--panel` and `--from-snapshot` work, and the strings have passed `redact.redact`). `mon_export.py` turns it into points, each with `name`, `unit`, `kind`, `value` and `attributes`.

- **Names.** `kbmon.<panel>.<measure>`: `kbmon.kb.facts` (unit `{fact}`, attributes `root` and `tag`, the counts of `rag.py audit`), `kbmon.kb.articles`, `kbmon.kb.gaps`, `kbmon.kb.conflicts`, `kbmon.kb.index_age`, `kbmon.kb.eval_passed`; `kbmon.coord.claims` (attribute `state`: `live` or `over_budget`), `kbmon.coord.claim.left`, `.budget` and `.spend` (attribute `item`), `kbmon.coord.event_seq`; `kbmon.sessions.procs` (attribute `class`), `.worktrees` and `.stalled`; for every panel `kbmon.panel.up` (1 for `ok`) and `kbmon.panel.seconds` (attribute `panel`); and `kbmon.alerts`. A panel with no exporter gives its `up` and `seconds` points only.
- **Kinds.** `gauge` for a value that goes up and down, `sum` for the coord event sequence number, which only grows.
- **Attributes are numbers, flags or identifiers.** A string value is kept only when it is letters, digits and `_ . : / # @ -` (120 characters at most) and `redact.redact` returns it as it is; a point with any other attribute value is left out whole. No free text of a panel (an error, an event field, a digest line, a path) is exported.
- **No holder.** Claims are counted by state; a claim's key is the `item` attribute only when it is a backlog item id (two letters, a dash and eight characters), and a claim's holder is never an attribute.

## The OpenTelemetry adapter

`otel/kbmon_otel.py` sends the metric points over OTLP/HTTP with the OpenTelemetry Python SDK. It is a project of its own: `otel/pyproject.toml` names the SDK and the OTLP/HTTP exporter, `otel/uv.lock` pins them, and `uv run --frozen --project otel python otel/kbmon_otel.py` installs them into `otel/.venv` and runs it. No file in `_tools/` imports an OpenTelemetry package; the adapter runs `kbmon.py --metrics` as a child process and exports its points.

- **Off until an endpoint is set.** The SDK's own variables name where to send: `OTEL_EXPORTER_OTLP_ENDPOINT` (a base URL; the exporter appends `v1/metrics`) or `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT`. With neither set the adapter sends nothing, prints `export is off` and exits 0.
- **Credentials from the environment only.** Headers come from `OTEL_EXPORTER_OTLP_HEADERS` (or `OTEL_EXPORTER_OTLP_METRICS_HEADERS`) and no flag or file names them. No header value is printed or logged: a filter on the log handler replaces each value with `***`, the endpoint is shown as scheme, host and port only, and the child kbmon run gets the environment without any `OTEL_` variable.
- **Encoding.** The SDK exporter's own (protobuf over HTTP); nothing is encoded by hand.
- **What is sent.** The points of one snapshot as observable gauges, and `sum` points as observable counters, with the point's unit and attributes under the resource `service.name` `kbmon` (`OTEL_SERVICE_NAME` overrides it). The attribute rules of The metric points apply, since the points are kbmon's own.
- **Flags.** `--once` sends one snapshot and exits; without it the adapter sends every `--interval` seconds (default 60) until Ctrl-C. `--panel` and `--from-snapshot` are kbmon's, and `--timeout` bounds the child run. Exit codes: 0 sent or export off; 1 a send failed; 2 kbmon gave no points or an argument was bad.

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

## The sprint panel

`data` of `mon_sprint.py`:

| key | holds |
|---|---|
| `sprints` | per sprint of the backlog that is active or planned, active first, then approved, then planned, ids in order within a state: `id`, `state` (`active`; `approved`, a planned sprint whose start gate the operator approved and `backlog.py start` is left; `planned`), `items` (the count of its items for each status), `next` and `waiting` |
| `landings` | per landing in progress, newest first: `item`, `step` (the newest `land.step` row's step) and `since` (the time of the landing's first `land.step` row) |

- **Read through backlog.py.** The sprints and their items are `bl_base.Backlog`'s, `next` is the item `bl_view.ready` puts first (an active sprint only, else null) and `waiting` holds `{item, gate}` for each open blocking gate of the sprint (its start gate until it is answered) and of its items that are not done or dropped. A root with no backlog has an empty `sprints`.
- **Landings.** The ops rows are `bl_stall.ops_rows`' (this host's spool and the committed sidecars). An item is in progress while its newest `land.step` row has no later `land.end` row; rows of one millisecond in the spool keep the order of the file. A landing that stopped without a `land.end` row (a killed process, or a row from before landing wrote one) stays listed.
- **View.** A row for each sprint, its id, its state padded to 10 and `4/11 done · next ST-xxxxxxxx · todo 3, doing 1, done 4` (done and dropped count as done) for an active sprint, `not started` for an approved one and `waits on start gate` for a planned one; under it up to two `waiting  ITEM/GATE` rows of its other open gates (12 sprints at most); then up to six `landing  ITEM  STEP  since TIME` rows, each state written, not coloured.

## The host panel

`data` of `mon_host.py`:

| key | holds |
|---|---|
| `load` | the 1, 5 and 15 minute load as three numbers, or `"unsupported"` on a host with no `os.getloadavg` (Windows) |
| `cores` | `os.cpu_count()`, or null |
| `suite_lock` | the whole-suite lock's live holder: `pid`, `clone` (`this` or `other`) and `started` (UTC time); null when none holds it |
| `main_lock` | the main lock's live holder: `pid`, `clone`, `started` and `step`; null when none holds it |
| `ceiling` | `max_ids`, `max_files` and `max_seconds` (this platform's) of `_tools/tests_ceiling.json`, against `ids` and `last_run_s` (the newest passing full `test.run` row that ran pytest, null before any) and `files` (the clone's `test_*.py`); `{"error": ...}` where `tests.read_ceiling` refuses the file |

- **Read through the lockers' readers.** The two locks are the files `tests.py` (`kb-tests.lock`) and `kg_lock.py` (`kb-main.lock`) keep in the host lock directory (`KB_HOST_LOCK_DIR`, else `/tmp`); the panel reads them with `tests.read_lock`, `tests.parse_holder`, `tests.pid_alive` and `kg_lock.holder_step`, and the ceiling with `tests.read_ceiling`. It takes, clears and writes no lock, and the ceiling file is only read. A lock file whose pid no longer runs, or whose record cannot be read, is no holder.
- **`this` or `other`, never a path.** A holder's `clone` is `this` when it is the clone the panel reads (`--root`), else `other`; the path in the lock record is not printed.
- **Unsupported load.** A host with no `os.getloadavg` shows `load` as `unsupported`; the locks and the ceiling are shown as on any host.
- **View.** `load` (`1.00 · 2.00 · 3.00 · 8 cores`), `suite` and `main` (`pid · this clone · since YYYY-MM-DD HH:MMZ`, the main lock also `step`, or `none`), then the ceiling: `ids`, `files` and `last run`, each as `{used}/{limit} [|||||||...] {pct}%` with 10 cells (the percentage floored to a cell). From 100 columns the three share one row, below that three aligned rows. A bar of 80 to 99% starts its row with `! ` (yellow) and one of 100% or more with `!!` (red), the shared row by its worst bar; a row under 80% has no colour, since the view colours whole rows.

## The querylog panel

`data` of `mon_querylog.py`:

| key | holds |
|---|---|
| `mode`, `disabled` | the query log's mode in the config file (`auto`, `local` or `off`) and whether the `DISABLED` marker is there |
| `spool` | the rows waiting in the local spool: `files`, `rows`, `by_kind` (rows per surface, the surfaces that have a row) and `unreadable` (rows distill cannot read) |
| `undelivered`, `undelivered_runs`, `undelivered_since`, `delivery_ref` | the entries in the local store's run files that `origin/main` does not hold yet (0 in mode `local`, where an entry is delivered once distill wrote it), the run files holding them, the time of the oldest such run id or null, and false when the delivery ref cannot be read (then every run file of the store counts) |
| `last_distill` | the outcome of the last `distill:` line of `distill.log` (`written` with `entries`, `dropped` and `waiting`, `nothing`, `off`, `locked` or `failed`), or null |
| `last_delivery` | `{outcome, why, when}` of the last terminal `apply --push:` line (`pushed`, `nothing`, `conflict`, `waiting`, `locked`, `refused`, `fetch-failed`), or null; `why` is the failed gate and its first error line that `backlog.py land` reads for a push that delivered nothing, else empty |
| `last_pushed` | `{commit, when}` of the newest query log commit on `origin/main` (a first-parent commit with a `KB-Auto` trailer holding `querylog`), or null |
| `usage_today` | `{rows, tokens, usd, unpriced}`: the UTC day's usage rows (Usage, In the query log), their tokens (uncached input, cache writes, cache reads and output) and their cost at `backlog.py cost`'s prices; `unpriced` names a model the price table lacks |

- **Read through the query log's readers.** The counts come from the structured readers beside the text ones in `ql_report.py` (`spool_state`, `undelivered`, `last_outcomes`, `last_pushed`, `usage_today`), which `querylog.py show --spool` shares (`spool_scan`); the panel parses none of the lines `show` and `status` print. It reads the query log home of this copy of the tools (`ql_base.places`: the clone's `_cache/querylog`, or the plugin's data directory), whatever `--root` names, and writes nothing; the delivery ref is read with `git ls-tree` and `git log` on the local ref, with no fetch.
- **Counts and kinds only.** The spool keeps prompts and answers as typed; the panel carries no question, prompt or reply text, no session id and no row id: rows are counted by surface, runs by their id's time, commits by hash.
- **When.** `distill.log` carries no time per line, so `when` of an outcome is the log's last write, set only on the outcome that stands last in the log and null on the other.
- **View.** Four rows: `spool` (rows in files, then the four surfaces with most rows and `+N more`), `delivery` (the undelivered count, the last pushed commit and time, the last apply outcome), `distill` (the outcome with its counts, the mode, `DISABLED` when the marker is there) and `today` (rows, tokens and dollars, with the model that has no price). A refused push replaces the delivery row with `!!delivery  REFUSED <gate and first error line> · since <oldest undelivered run> · undelivered N`; a push whose fetch failed, or an undelivered entry with no readable delivery ref, makes it a `! ` row.
