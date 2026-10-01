# Code: the rules for the tooling in `_tools/`

The Python under `_tools/` follows these rules; a change to it keeps them. They describe what the code does now. Each rule lives here once: the gate and the definition of done (`kb/_self/maintaining.md`, Conduct for changes; `kb/_self/backlog.md`, Definition of done) point here for the code, and `kb/_self/tools.md` lists the tools and their commands.

## Runtime

- **Standard library only.** A tool runs with the interpreter alone, on Python 3.11 or newer, with no install step. `pyproject.toml` names dependencies for development only (pytest, pytest-xdist, ruff); no tool imports them outside a test.
- **One entry point.** A hook reaches a script through `_tools/kbpy`, never by naming an interpreter (`kb/_self/querylog.md`, Portability).

## Portability

The same code runs on Linux, macOS and Windows.

- **Text is UTF-8.** Every `open`, `read_text` and `write_text` names `encoding="utf-8"`; a write adds `newline="\n"`, so a file has the same bytes on every host. A script that reads or prints text through a pipe (a hook, the MCP server) reconfigures its streams to UTF-8.
- **Paths go through `pathlib`** in new and changed code (older modules still use `os.path`): no string joins with `/` or `\`, no shell syntax in a path. A path written into a doc or a ledger uses `/`.
- **Subprocesses take an argument list**, never a string and never `shell=True`. A tool starts Python with `sys.executable`, not `python3`, which on Windows can be a Store alias.
- **No Unix-only calls** (`fcntl`, signalling a PID to probe it, `os.fork`). A lock is an `O_EXCL` file; a detached child sets the creation flags of each OS.
- **A test skips what a host lacks** (no `sh`, no `git`, no PowerShell) with a marker that names the missing part; it never passes without running.

## Git in tests

- **A test never acts on the real repository.** `_tools/conftest.py` removes the variables that name a repository (`GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE` and the others) from the environment before any test, because a git hook sets them and a run it starts would inherit them.
- **A scenario builds its own repository** in a temporary directory, with `git_env()` for its environment: no global or system git config, a fixed author and committer, and none of the variables that leak a CI run or a verification date. The `Repo` helper runs git in such a directory.

## Output

- **Output is deterministic.** The same inputs give the same bytes: sorted iteration where order is not data, `\n` line endings, no BOM, and a clock or an environment value only where recording it is the tool's purpose.
- **Derived state converges.** A second run on unchanged inputs writes nothing and changes nothing (`build_index.py` twice, `querylog.py learn` and `apply` twice, `kbid.py add` with the same row). A `--check` form writes nothing and exits 1 when a run would change a file.
- **A file another process reads while a run writes it** (the query log's) is written whole or not at all: to a temporary name, then replaced.

## Exit codes

- **Each tool documents its own codes** in its docstring and in `kb/_self/tools.md`; a change to them changes both. A code is never renumbered.
- **The pattern the tools share:** 0 done or nothing to do; 1 the tool found what it looks for (a failed check, stale docs, a change `--check` would make, a failed step); 2 it could not do what was asked (bad arguments, not a git clone, an unreadable input, a refusal); 3 a human or another process must act first (a conflict, a held lock). A tool states where it differs.
- **A hook that only logs or informs exits 0 whatever happens**, so it never blocks a prompt or a tool call by failing; only a gate blocks, with exit 1. A hook that answers by running another tool (`backlog:` runs `backlog.py`) lets the prompt through with a note when that tool fails or times out.
- **A usage error is not a finding.** An argument error exits 2, so a caller cannot mistake it for exit 1.

## Checks and their tests

- **Every check and gate has a test with a planted failure** that makes it fail: a wrong wording, a missing part, a dead reference. A check that no planted input can fail proves nothing (`kb/_self/backlog.md`, Definition of done). The totals check of `kbusage.py tree` fails on a planted group whose rows do not add up.
- **A check that parses a tool's or a forge's output** also has a test over a recorded real sample under `_tools/fixtures/`, besides its synthetic ones.
- **A test's name survives a refactor.** A split of a module or a test file keeps the test names, so a check that selects by `-k` still selects it.
- **Every tool module is reached by a test.** `python3 _tools/testmap.py orphans` lists any that none reaches.
- **A file format is named in `kbcommon` and checked in `check.py`.** The decision files (`kbcommon.DECISION_COLS`, `MAKER_COLS`, `POLICY_ROW`, `DECISION_ID`, `context_refs`) are checked by `check.py`'s `check_decisions`, which reports each broken rule by file and line; the tests named `decisions_store` (`test_kb_root.py`, `test_kb_cohesion.py`) plant one failure per rule.

## Layout

- **Flat modules in `_tools/`.** No packages: the directory is on `sys.path` for every script, and a package named like a script would shadow it.
- **A subsystem is a prefix.** The query log's stages are `ql_*.py` modules (`ql_base.py` holds the shared ground, the others one stage each, except `ql_testkit.py`, which holds the query-log tests' shared helpers and is no stage; its tests are one `test_ql_<stage>.py` for each stage); `kbgit.py`'s are `kg_*.py` (`kg_base.py` the shared ground, `kg_merge.py` merge and ledger repair); `benchmarks.py`'s are `bench_*.py` (`bench_core.py` the harness, `bench_report.py` the report tables, `bench_lookup.py`, `bench_retrieval.py`, `bench_querylog.py` and `bench_install.py` the scenario families); `backlog.py`'s are `bl_*.py` (`bl_intake.py` the intake's detector registry, candidates, fingerprints and draft items, the part that does not touch the backlog's files). A module's first lines say what it holds and which doc describes it.
- **A CLI facade keeps the command.** `_tools/querylog.py`, `_tools/kbgit.py`, `_tools/benchmarks.py` and `_tools/backlog.py` are the scripts hooks and people run; each holds the command line, the usage text and the dispatch (`benchmarks.py` also the `SCENARIOS` registry), and the stages live in the prefixed modules beside it. A split moves code behind a facade and leaves the commands, their output, their exit codes and the test names as they were.
- **Tests sit beside the tools** as `_tools/test_<subject>.py`, shared setup in `_tools/conftest.py`, which also holds the tracked-file scans that the kb content tests (`test_kb_cohesion.py`, `test_kb_lookup.py`, `test_kb_ids.py`, `test_kb_leaks.py`) share.

## Imports

- **A module imports the modules below it.** The facade imports its helpers; a helper never imports its facade. Inside a prefix, the shared ground (`ql_base.py`, `kg_base.py`, `bench_core.py`) imports no sibling, and a stage imports the stages it builds on, never one that builds on it.
- **No cycles at the top level.** A reach back up the order is an import inside the function that needs it.
- **A leading underscore means the module's own.** Another module does not import or call a name that starts with `_`; a name two modules need is public, without the underscore.
- **A reader of a file format that a writing tool also reads is below it.** `kbdecide.py` imports `kbfacts.py` (to find facts), so the lookup side reads `_decisions.csv` itself, tolerantly and by its columns (`kbfacts.decision_rows`), never through `kbdecide.py`; `check.py` stays the one place that judges the format. The lookup tests that plant decision rows (the tests named `decision_lookup`, in `test_kb_lookup.py` and `test_kb_mcp.py`) write them with `kbcommon.write_csv` and run `rag.py` over a fixture root, so a change to the row format reaches them through `kbcommon`.
- **A test holds the first and third rules.** `_tools/test_layout.py` parses every `_tools/*.py` with `ast` and fails when a `ql_*`, `kg_*`, `bench_*` or `bl_*` module imports its facade, or a module imports an underscore name from another one (`from x import _y` or `x._y`); the exceptions the tree had are listed by name in the test, and a new one fails.

## Writing a checked file

- **A tool that writes a file `check.py` checks asks `check.py` whether the write is clean.** `kbdecide.py` writes a root's `_decisions.csv` (or kb/_self's), then runs `check.check_decisions` over the files as they are and undoes the write, with exit 2 and the errors, when it added one the file did not have before; it never hand-copies a rule of the format, so a row it writes cannot fail the check, and a later rule applies to it at once. The module takes the check as a library, which is the one place a tool imports `check.py`.
- **A refusal is a planted failure.** Each rule a command refuses by has a test in `_tools/test_kbdecide.py` that runs the command, finds exit 2 and the rule in the message, and finds every decision file as it was. The commands an agent may not run (`supersede` and `restore` without `--by operator`) and the rejected proposal (`invalidate` of a `proposed` row, which names no maker) are the tests named `kbdecide_withdraw`. `sweep` is open to agents and has a planted failure per rule it applies (a dropped item, an item deleted at close whose last version in git history is dropped, a superseded source, a gone article or domain, a passed `review_by`) and one for each case it must leave alone (a done item, a missing fact), the tests named `decision_sweep`; they build a git repository of their own for the history. The relink flag for a missing fact and `relink`, which is open to agents too, are the tests named `decision_sweep_relink`: each source of the likeliest fact (git history, anchors, doc2query questions, the decision's words), the cut below which none is offered, and each refusal of `relink`. The tool reuses `kbfacts.fact_key` for a fact's key and `kbfacts.units` for the facts, so it never hashes a fact itself.
