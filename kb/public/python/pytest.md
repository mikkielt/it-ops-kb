---
topic: python/pytest
priority: P2
applies_to: [pytest]
retrieved_utc: 2026-09-29
sources: [S-kobs45hd, S-f5tpmzia, S-mgv7bfqe, S-h5gurdir, S-tivsgmaq, S-7pmymrvf, S-447ck3rx, S-4riqrsyi, S-kthrpvjf, S-6rttndpw]
status: complete
---

# pytest configuration and fixtures

## Summary
pytest reads settings from one configuration file, chosen by a fixed precedence order; a
`pyproject.toml` can hold pytest config either as a native `[tool.pytest]` TOML table (pytest 9.0+) or
as the older INI-style `[tool.pytest.ini_options]` table (pytest 6.0+), and this repository uses the
latter. Test discovery, marker registration, fixture scopes and `tmp_path` retention are all
configuration knobs that a maintaining agent needs to read correctly; this article covers those, plus
the built-in fixtures (`capsys`, `monkeypatch`, `tmp_path`, `tmp_path_factory`) and exit codes.
`python/pytest-xdist.md` covers running these same tests in parallel workers.

## Facts
- Configuration files are tried in this order and the first match wins (never merged):
  `pytest.toml`/`.pytest.toml` (always matches, even empty; pytest 9.0+), `pytest.ini`/`.pytest.ini`
  (always matches, even empty), `pyproject.toml` (matches if it has a `[tool.pytest]` or
  `[tool.pytest.ini_options]` table), `tox.ini` (needs a `[pytest]` section), `setup.cfg` (needs a
  `[tool:pytest]` section). A bare `pyproject.toml` with none of those tables is used as a last-resort
  `rootdir` marker but not treated as a matched config file. [DOC S-kobs45hd]
- `[tool.pytest]` (native TOML types, e.g. `addopts = ["-ra", "-q"]`) was added in pytest 9.0;
  `[tool.pytest.ini_options]` (INI-style values, e.g. `addopts = "-ra -q"`) has been supported since
  pytest 6.0. This repository's `pyproject.toml` uses `[tool.pytest.ini_options]`. [DOC S-kobs45hd]
- `testpaths` sets the directories pytest searches when no file/directory/test id is given on the
  command line; this repository sets `testpaths = ["_tools"]`. [DOC S-mgv7bfqe]
- `python_files` defaults to `["test_*.py", "*_test.py"]` — both `test_*.py` (this repo's
  convention) *and* a trailing `*_test.py` are collected as test modules by default. `python_classes`
  defaults to `["Test"]` (any class prefixed `Test`, unless it's a `unittest.TestCase` subclass, which
  is always collected regardless of this setting). [DOC S-mgv7bfqe]
- `markers` lists known marker names; when `strict_markers` (or the umbrella `strict` option, which
  also implies `strict_config`, `strict_parametrization_ids` and `strict_xfail`) is enabled, using an
  unregistered marker raises an error instead of only a warning. `--strict-markers` is the equivalent
  CLI flag. [DOC S-mgv7bfqe]
- `-k EXPR` selects tests by substring/expression match on test (and parent) names; `-m EXPR` selects
  tests by marker expression (e.g. `-m "not stress"`, as this repo's `tests.py` uses to exclude the
  stress suite, and `-m "not stress and not git"` for `KB_TESTS_FAST=1`). [DER S-mgv7bfqe: `-m`/`-k`
  are documented pytest option flags; the specific expressions are this repo's own `_tools/tests.py`.]
- Built-in fixtures have exactly five possible scopes: `function` (default), `class`, `module`,
  `package` and `session`, declared with `@pytest.fixture(scope=...)`. A higher-scoped fixture (e.g.
  `session`) is instantiated once for all the tests sharing that scope, not once per test function.
  [CODE S-7pmymrvf: src/_pytest/fixtures.py#fixture]
- `tmp_path` returns a `pathlib.Path` unique to each test *function* invocation, backed by
  `tmp_path_factory` (a `session`-scoped fixture) for the underlying base temp directory management.
  [DOC S-h5gurdir, S-tivsgmaq]
- Retention of the per-test directories `tmp_path` creates is controlled by `tmp_path_retention_policy`
  (`"all"` — default, keep everything; `"failed"` — keep only directories from failed/errored tests;
  `"none"` — always remove) and `tmp_path_retention_count` (default `"3"`, how many recent *sessions'*
  worth of directories to retain per the policy). This repository sets
  `tmp_path_retention_policy = "failed"` because "each stress case copies the kb; keeping every
  passing run's copies filled a disk (74 GB over 4 runs, 2026-09-26)" (comment in `pyproject.toml`).
  [DOC S-mgv7bfqe]
- `capsys` captures text written to `sys.stdout`/`sys.stderr` during a test (`capsysbinary` captures
  bytes instead; `capfd`/`capfdbinary` capture at the file-descriptor level, which also catches output
  from subprocesses). `monkeypatch` (a `pytest.MonkeyPatch` instance) is used to temporarily set or
  delete attributes, dict items, environment variables, or `sys.path` entries, undoing all changes
  automatically at the end of the test. [DOC S-h5gurdir]
- Running `pytest` can exit with one of seven codes: `0` all collected tests passed; `1` tests ran but
  some failed; `2` execution interrupted by the user (e.g. Ctrl-C); `3` an internal error occurred
  while executing tests; `4` a command-line usage error; `5` no tests were collected; `6` the
  `--max-warnings` limit was exceeded. These are the `pytest.ExitCode` enum values. [DOC S-f5tpmzia]
- `-k EXPRESSION` is a Python-evaluable expression (`and`, `or`, `not`, parentheses) whose names are substring-matched, case-insensitively since 5.4, against the test's name and its parents' names (usually the file and the class), its attributes, markers and `extra_keyword_matches`. [DOC S-kthrpvjf]
- Because the file name is a `-k` keyword, `-k test_census` selects every test in a file whose name contains `test_census`; run on this repository's `_tools/test_census.py` and `_tools/test_change_router.py` together it kept 10 of 44 tests, all from the first file. [DER S-kthrpvjf: run 2026-09-29 with pytest 9.1.1, uv run --frozen python -m pytest ... --collect-only -q]
- A test's node id is `module.py::Class::method` or `module.py::function`, with `[param]` for a parametrized case, rooted at the `rootdir` and built from the full path. Moving a test class to another file therefore changes its node ids but not its class or function names, so a `-k ClassName` selector still finds it while a `path::Class` argument does not. [DER S-kthrpvjf, S-kobs45hd: the node-id form and its rootdir base are documented; the effect of moving a class follows from them]
- `--collect-only` (`--co`) collects without executing and shows what would run; with `-q` it prints one node id per line, and pytest 8.2+ can read such a file back with `pytest @file`, so a list of ids taken before a refactor can be compared with one taken after. [DOC S-447ck3rx, S-mgv7bfqe]
- When every collected test is deselected by `-k` (or none is collected), pytest exits with code 5; run here, `-k zzznomatch` on `_tools/test_census.py` printed `10 deselected` and exited 5. So a selector that matches nothing fails a gate as a pass-through check would not. [DER S-f5tpmzia: exit code 5 is "no tests collected"; the deselection case confirmed by running pytest 9.1.1]
- Default import mode `prepend` inserts each test file's directory at the start of `sys.path` and imports the file under its bare module name when the directory has no `__init__.py`; test files then need unique names across the tree or pytest raises an error, and a `conftest.py` is imported as `conftest`. [DOC S-4riqrsyi]
- In `prepend` mode a test in a flat directory can import its sibling modules by name because that directory is on `sys.path`; in `importlib` mode pytest leaves `sys.path` alone, test files get unique names derived from the `rootdir`, but test modules cannot import each other and helper modules in the test directory are not importable. [DOC S-4riqrsyi]
- `pytest` and `python -m pytest` behave nearly the same, except the latter adds the current directory to `sys.path`; the `pythonpath` setting adds directories (relative to the `rootdir`) to the head of `sys.path` for the session. [DOC S-4riqrsyi, S-mgv7bfqe]
- pytest loads `conftest.py` files as local per-directory plugins: for each test path it loads `conftest.py` and `test*/conftest.py` beside it, parents first. For a `conftest.py` outside a package, `import conftest` can be ambiguous, so the docs advise to import nothing from a `conftest.py` (or to put it in a package). [DOC S-6rttndpw]
- Splitting one test file into several in a flat test directory (no packages) is safe for discovery when each new file matches `python_files` (`test_*.py` here) and has a name no other test file uses; shared helpers belong in an ordinary importable module or in `conftest.py` fixtures, not in a helper imported from `conftest.py`. [DER S-4riqrsyi, S-6rttndpw, S-mgv7bfqe: from the import-mode and conftest rules above]

## Reference
- Related: `python/imports-and-modules.md` (`sys.path[0]`, circular imports, underscore names) and `gitlab/git-history-queries.md` (co-change and rename queries for a file split).
- SNIPPET: this repository's INI-style pytest config (`[tool.pytest.ini_options]`); context: pytest 6.0+, pyproject.toml; checked: syntax [DOC S-kobs45hd,S-mgv7bfqe: `[tool.pytest.ini_options]` table, `testpaths`, `python_files` default, and `tmp_path_retention_policy` values]
```toml
[tool.pytest.ini_options]
testpaths = ["_tools"]
python_files = ["test_*.py"]
tmp_path_retention_policy = "failed"
```
- SNIPPET: the newer native-TOML pytest config (`[tool.pytest]`), shown for contrast; context: pytest 9.0+; not used by this repo; checked: no [DOC S-kobs45hd: `[tool.pytest]` native TOML table added in pytest 9.0]
```ini
# pytest.toml (native TOML config, pytest 9.0+) — not used by this repo, shown for contrast
[pytest]
minversion = "9.0"
addopts = ["-ra", "-q"]
markers = ["slow", "serial"]
```

## Examples
- `pytest -m "not stress" -k Leak _tools` runs everything except the `stress`-marked suite, further
  narrowed to test names containing `Leak` — the pattern `_tools/tests.py -k Leak` builds on.
- A fixture shared by every test in a module (`@pytest.fixture(scope="module")`) is created once per
  module rather than once per test function; a `session`-scoped fixture is created once per pytest
  process (see `python/pytest-xdist.md` for what "once" means when workers are involved).
