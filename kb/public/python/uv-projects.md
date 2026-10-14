---
topic: python/uv-projects
priority: P2
applies_to: [uv, python]
retrieved_utc: 2026-10-11
sources: [S-wmmyfoun, S-f2okeu6a, S-47yzu2ea, S-ixzgi6xe, S-sqwzg5ex, S-y4cg63ji, S-j7nlfpkd, S-7xvirecf, S-x7kevebo, S-pwf7njbf, S-qo6uqong, S-4odritdm, S-2xpbl25y, S-e2utk2wn, S-dejuwanz]
status: complete
---

# uv project workflow

## Summary
uv manages a Python project through a `pyproject.toml` (metadata and dependency constraints) plus a
generated `uv.lock` (the exact resolved versions). Locking and syncing are automatic: `uv run` and
`uv sync` update the lockfile and the `.venv` project environment as needed before doing anything
else. `--frozen` and `--locked` both skip that automatic update, but differently: `--frozen` uses the
existing lockfile as-is and never errors on staleness; `--locked` requires the lockfile to already
match the project and errors if it does not. This repository's own `_tools/tests.py` runs
`uv run --frozen ...` (a fast path that trusts `uv.lock` and never touches the network to re-resolve),
while `.claude/hooks/session-start.sh` runs `uv sync --frozen` for the same reason. See
`arch/python-single-package-extras.md` for extras (`--extra`) and dependency groups (`--group`), which
this article does not repeat.

## Facts
- Locking resolves a project's dependencies into `uv.lock`; syncing installs a subset of the lockfile
  into the project's `.venv`. Both happen automatically: `uv run` locks and syncs the project before
  running the given command, and commands that read the lockfile (e.g. `uv tree`) also update it
  first. [DOC S-wmmyfoun]
- `--locked` disables automatic locking: if the lockfile is not up to date with the project metadata,
  uv raises an error instead of updating it (equivalent to `uv lock --check`). `--frozen` instead uses
  the lockfile without checking whether it is up to date at all. `--no-sync` skips updating the
  environment as well, on top of `--frozen`/`--locked`. [DOC S-wmmyfoun]
- `UV_FROZEN` and `UV_LOCKED` environment variables are equivalent to the `--frozen` and `--locked`
  CLI flags respectively (added in uv 0.4.25); `UV_NO_SYNC` is equivalent to `--no-sync` (added in
  0.4.18). [CODE S-x7kevebo: crates/uv-static/src/env_vars.rs#UV_FROZEN]
- A lockfile is considered outdated if the project's dependency constraints changed such that the
  locked version would now be excluded; uv never considers a lockfile outdated just because newer
  package versions were released upstream (an explicit `uv lock --upgrade` is required to move
  versions forward). [DOC S-wmmyfoun]
- `uv sync` performs "exact" syncing by default: it removes packages installed but absent from the
  lockfile (`--inexact` to keep them). `uv run` instead performs "inexact" syncing by default: it
  installs what's missing but does not remove extras (`--exact` to force removal). [DOC S-wmmyfoun]
- Dependency groups (`[dependency-groups]`, PEP 735) are synced with `--group <name>`, excluded with
  `--no-group <name>`, and `--only-group <name>` installs only that group without the project itself
  (like `--only-dev` for the `dev` group). Exclusions always take precedence over inclusions: given
  both `--no-group foo --group foo`, `foo` is excluded. [DOC S-wmmyfoun]
- The `dev` group is special-cased and synced by default; `--no-dev`/`--only-dev` are shorthand for
  `--group dev`/`--only-group dev`. The set of groups included by default is controlled by
  `tool.uv.default-groups` (a list of group names, or `"all"`); `--no-default-groups` disables this
  behaviour entirely for one invocation. [DOC S-ixzgi6xe]
- `uv.lock` is a *universal* (cross-platform) lockfile: during resolution, all required packages must
  be installable somewhere across the project's entire `requires-python` range and across operating
  system/architecture markers, so the same `uv.lock` is used by every contributor and every platform.
  A package may appear more than once in the lockfile with different pinned versions or URLs when
  different platforms need different versions. [DOC S-pwf7njbf, S-47yzu2ea]
- `project.requires-python` (e.g. `">=3.9"`) both bounds the Python syntax uv will accept in the
  project and constrains dependency version selection during resolution: during universal resolution
  every dependency must have a version compatible with the *entire* declared range, not just the
  lower bound. [DOC S-qo6uqong, S-pwf7njbf]
- `uv python install <version>` installs a managed CPython (or PyPy/Pyodide) build; without an
  explicit version, if a `.python-version` file is present, `uv python install` installs the version
  it names (`.python-versions`, plural, can list several versions to install at once). uv searches for
  `.python-version` in the working directory and its parents (and then the user configuration
  directory), and does not cross project/workspace boundaries except for that user-level fallback.
  `uv python pin` writes `.python-version` in the current directory (`--global` writes the user-level
  one). [DOC S-sqwzg5ex]
- By default uv prefers Python versions it manages itself (`python-preference = "managed"`) but will
  still prefer an already-installed system Python over downloading a new managed one; `--no-managed-python`
  restricts uv to system interpreters only, `--managed-python` to managed ones only. [DOC S-sqwzg5ex]
- The cache directory is chosen, in order: a temporary directory when `--no-cache` is passed; the
  directory from `--cache-dir` or the `UV_CACHE_DIR` environment variable, or `tool.uv.cache-dir`;
  otherwise a system default (`$XDG_CACHE_HOME/uv` or `$HOME/.cache/uv` on Unix,
  `%LOCALAPPDATA%\uv\cache` on Windows). uv always uses a cache directory, even under `--no-cache`
  (a temporary one, scoped to that single invocation). [DOC S-y4cg63ji]
- The cache is bucketed and versioned per uv release; a breaking cache-format change bumps a bucket's
  version so incompatible uv releases do not read or write each other's cache entries, but compatible
  releases can safely share one cache directory (including across concurrent uv processes: the cache
  is designed to be thread-safe/append-only). [DOC S-y4cg63ji]
- `uv cache clean` removes all cache entries (or, with a package name, just that package's); `uv cache
  prune` removes unused entries and is safe to run periodically; `uv cache prune --ci` additionally
  drops pre-built wheels and unzipped sdists while keeping wheels built from source, recommended at the
  end of a CI job. [DOC S-y4cg63ji]
- In GitLab CI, Astral publishes `ghcr.io/astral-sh/uv:$UV_VERSION-python$PYTHON_VERSION-$BASE_LAYER`
  images with uv preinstalled; setting `UV_LINK_MODE: copy` avoids failures from GitLab's separate
  build-directory mountpoint (hardlinks/CoW don't cross it). Caching `uv.lock` as the cache key file
  and persisting `$UV_CACHE_DIR` speeds up repeat jobs; `uv cache prune --ci` in `after_script` keeps
  the cache small. [DOC S-j7nlfpkd]
- `uvx <tool>` is an exact alias for `uv tool run <tool>`: it runs a tool in a disposable, isolated
  virtual environment (cached in the uv cache, so a later run reuses it) without adding the tool to
  the project. `uv tool install <tool>` instead creates a persistent environment under uv's tools
  directory and puts the tool's executables on `PATH`. `uvx <name>` is nearly equivalent to
  `uv run --no-project --with <name> -- <name>`, except the tool interface always runs isolated from
  the project and (if the tool is already installed) uses that installed version. [DOC S-7xvirecf]
- `uvx` uses the latest available version of a tool on its first invocation, then reuses that cached
  version on later invocations until the cache is pruned/refreshed or a different version is
  requested (`tool@version`, or `tool@latest` to force a refresh). Once a tool is `uv tool install`ed,
  plain `uvx <tool>` uses the installed version instead of the latest. [DOC S-7xvirecf]
- `uv run` invokes a command inside the project's `.venv`, ensuring it is up to date first; the
  command can come from the project itself or be arbitrary (`uv run bash scripts/foo.sh`).
  `uv run --with <pkg>[==<version>]` adds a package to that one invocation without touching the
  project's own dependencies. A script with inline PEP 723 metadata (a `# /// script` block declaring
  its own `dependencies`) is instead run fully isolated from the project's environment. [DOC S-f2okeu6a]
- Workspaces (uv 0.12.19 docs): a workspace is a set of packages, the workspace members, managed
  together. Each member keeps its own `pyproject.toml`, but the workspace shares ONE lockfile, so all
  members resolve to a consistent set of dependencies. `uv lock` works on the whole workspace at once;
  `uv run` and `uv sync` work on the workspace root unless `--package` selects another member. [DOC S-4odritdm]
- A workspace is created by adding a `[tool.uv.workspace]` table to a root `pyproject.toml`. `members`
  is required and `exclude` is optional; both are lists of globs. Every directory matched by `members`
  (and not by `exclude`) must contain a `pyproject.toml`, and a member may be an application or a
  library. [DOC S-4odritdm]
- In uv's settings schema `members` and `exclude` take globs or explicit paths (for example `libs/*` or
  `path/to/member2`), both default to an empty list, and a package that matches both `members` and
  `exclude` is excluded. [CODE S-dejuwanz: crates/uv-workspace/src/pyproject.rs#ToolUvWorkspace]
- Every workspace needs a root, and the root is itself a member. [DOC S-4odritdm]
- The uv source distinguishes two kinds of workspace root: a project root, and a non-project root
  that has the `[tool.uv.workspace]` table but no `[project]` table (the source calls it a virtual
  manifest). [CODE S-e2utk2wn: crates/uv-workspace/src/workspace.rs#Workspace::discover]
- `tool.uv.package = false` is a separate switch on a project: uv ignores a declared build system, so
  the project is not built or installed into the environment (an explicit `uv build` still builds
  it). [DOC S-qo6uqong]
- The `tool.uv` schema calls a `package = false` project "virtual": it is not built or installed and
  only its dependencies go into the environment, while `package = true` needs a build backend and
  installs it editable. [CODE S-dejuwanz: crates/uv-workspace/src/pyproject.rs#package]
- A member depends on another member with `name = { workspace = true }` in `[tool.uv.sources]`, so
  the dependency is provided by the workspace and not fetched from PyPI or another index.
  Dependencies between workspace members are editable. `tool.uv.sources` entries in the workspace root
  apply to all members unless a member overrides them; a member's own entry for a dependency
  wins even when its marker does not match the current platform. [DOC S-4odritdm]
- A workspace has a single `requires-python`: uv takes the intersection of all members' values. To test
  one member on a Python version the rest of the workspace does not support, uv's docs point to
  installing that member with `uv pip` into a separate virtual environment. [DOC S-4odritdm]
- Member selection: `uv sync --package NAME` (repeatable) updates `.venv` to the dependencies of just
  those members, `uv sync --all-packages` installs all members, and `uv run --package NAME` or
  `uv run --all-packages` do the same for a command; `--package` and `--all-packages` conflict, a
  missing member is an error, and extras and groups chosen with `--extra`/`--group` apply to every member
  under `--all-packages`. [CODE S-2xpbl25y: crates/uv-cli/src/lib.rs#SyncArgs]
- `uv sync` installs the project and other workspace members as editable packages, so re-syncing is
  not needed for code edits; `--no-editable` opts out. [DOC S-wmmyfoun]
- `uv sync --no-install-workspace` installs no workspace member, root included (env
  `UV_NO_INSTALL_WORKSPACE`); the help text names building Docker images as the use, so dependencies
  can be installed apart from the workspace code. [CODE S-2xpbl25y: crates/uv-cli/src/lib.rs#SyncArgs]
- `uv build --package NAME` builds one member and `uv build --all-packages` (alias `--all`) builds every
  member; the workspace is discovered from the source directory (default: the current one) and an
  unknown member is an error. [CODE S-2xpbl25y: crates/uv-cli/src/lib.rs#BuildArgs]
- uv's docs list a library with a performance-critical extension module (Rust, C++) among the intended
  uses of a workspace, next to a core library kept apart from its CLI and a library with plugins that
  depend on the root. [DOC S-4odritdm]
- Workspaces are not suited to members with conflicting requirements or members that each want their
  own virtual environment: uv suggests independent projects with `{ path = "..." }` sources instead, at
  the cost of losing `uv run --package` (commands must run from the member's directory). [DOC S-4odritdm]
- uv cannot check that a member imports only dependencies it declares itself: Python has no
  dependency isolation, so a member can import a package declared by another member. [DOC S-4odritdm]
- Inside an existing package, `uv init` adds the new project to the workspace by default, creating
  `[tool.uv.workspace]` in the root if absent. [DOC S-4odritdm]
- `uv init --no-workspace` avoids workspace discovery and creates a standalone project. [CODE S-2xpbl25y: crates/uv-cli/src/lib.rs#InitArgs]

## Reference
- SNIPPET: a project with a `requires-python` lower bound and a `dev` dependency group; context: PEP 735 `[dependency-groups]`, uv; checked: syntax [DOC S-qo6uqong,S-pwf7njbf: `requires-python` bounds; DOC S-ixzgi6xe: the `dev` group is special-cased]
```toml
[project]
name = "example-tool"
requires-python = ">=3.9"

[dependency-groups]
dev = ["pytest>=8", "pytest-xdist>=3", "ruff>=0.6"]
```
- SNIPPET: the uv lock/sync/run/pin/uvx invocations this article's facts cover; context: uv; checked: no [DOC S-wmmyfoun: `uv sync`/`--frozen`/`--locked`; DOC S-sqwzg5ex: `uv python pin`; DOC S-7xvirecf: `uvx`]
```console
$ uv lock                       # create/update uv.lock explicitly
$ uv sync                       # install the resolved deps + dev group into .venv
$ uv sync --frozen              # install exactly what uv.lock says, skip the up-to-date check
$ uv sync --locked              # error out if uv.lock is not already up to date
$ uv run --frozen pytest        # run a command against the lockfile as-is (this repo's tests.py)
$ UV_FROZEN=1 uv run pytest     # same, via the env var
$ uv python pin 3.12            # write .python-version
$ uvx ruff check .              # run ruff without adding it to the project
```
- SNIPPET: a workspace root with one Rust-backed member and the member commands; context: uv 0.12.19 `[tool.uv.workspace]`, `[tool.uv.sources]`; checked: no [DER S-4odritdm, S-2xpbl25y: key names and flags as in the workspace docs and CLI help; member names are placeholders]
```toml
# pyproject.toml of the workspace root
[project]
name = "example-shell"
version = "0.1.0"
requires-python = ">=3.9"
dependencies = ["example-core"]

[tool.uv.sources]
example-core = { workspace = true }

[tool.uv.workspace]
members = ["crates/*"]
exclude = ["crates/scratch"]
```
```console
$ uv lock                          # one uv.lock for the root and every member
$ uv sync --all-packages           # install every member into the single .venv
$ uv run --package example-core pytest
$ uv build --package example-core  # build one member's sdist and wheel
```
Related: `arch/python-single-package-extras.md` documents `[project.optional-dependencies]` extras
and `uv sync --extra`/`--all-extras`, and `python/pytest-xdist.md` and `python/ruff.md` cover the two
`dev`-group tools this repo installs via uv.

## Examples
- A CI job on a scheduled host runs `uv sync --frozen --no-dev` to install only the published
  runtime dependencies of `PL-SRV-0042`, skipping dev-only tooling and never touching the network to
  re-resolve.
- A `_tools/tests.py`-style wrapper calls `uv run --frozen python -m pytest` (adding its own `-n`
  worker count) so tests always run against the committed `uv.lock`, and fails loudly if `uv` itself is
  missing rather than silently falling back.
