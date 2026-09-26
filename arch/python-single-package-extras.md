---
topic: arch/python-single-package-extras
priority: P1
applies_to: [python, uv]
retrieved_utc: 2026-09-26
sources: [S1705, S1706, S1707, S1708, S1522]
status: complete
---

# One Python package with role-based extras

## Summary
PEP 621's `[project.optional-dependencies]` (extras) and PEP 735's `[dependency-groups]` are two
different mechanisms: extras ship with the published distribution and are installed by consumers
(`package[extra]`); dependency groups are dev-only and never published. `uv` supports both, plus
workspaces for genuinely separate packages in one repo. For a single Python package that plays several
roles on different hosts, extras plus lazy imports is the documented, standard way to keep one
distribution without forcing every install to pull heavy per-role dependencies (e.g. an NLP stack
needed by only one role).

## Facts
- An extra is an optional part of a distribution; installing `package[extra1,extra2]` unions the
  extras' dependencies with the base dependencies. Grammar: `extras = '[' extras_list ']'`. [DOC S1705]
- Extras are declared in `[project.optional-dependencies]` as a TOML table mapping extra name to a
  list of dependency specifiers (PEP 621 metadata). [DOC S1705][DOC S1708]
- `uv add httpx --optional network` adds a dependency to a named extra; `uv sync --extra <name>`
  installs a package with that extra's dependencies. [DOC S1706]
- Extras are published as part of the wheel/sdist metadata and are what an external consumer
  installs, e.g. `uv tool install 'package[sync]'`. [DOC S1706]
- PEP 735 dependency groups (`[dependency-groups]`) are for local, non-published dependencies such as
  test/lint tooling; a `dev` group is included by default in uv and toggled with `--dev`/`--no-dev`;
  groups can nest via `{include-group = "name"}`. [DOC S1706][DOC S1707]
- Dependency groups are explicitly *not* included in the project's published requirements when built
  for PyPI or another index — the opposite of extras. [DOC S1706]
- For genuinely separate distributions sharing one repository, uv recommends workspaces
  (`[tool.uv.workspace]` with `members = [...]`), where each member is its own package with its own
  `pyproject.toml`, installed editable by default. [DOC S1706]
- `uv pip compile --generate-hashes` locks a resolved set including whichever extras/groups are
  requested (existing kb fact, reused). [DOC S1522]

## Reference
```toml
[project]
name = "example-tool"
[project.scripts]
example-tool = "example_tool.cli:app"
[project.optional-dependencies]
sync = ["pyodbc", "msal"]
ingest = ["pyodbc"]
mcp = ["mcp"]
validate = ["presidio-analyzer", "spacy"]
[dependency-groups]
dev = ["pytest", "ruff", "mypy"]
```

## Examples
- `uv tool install 'example-tool[read,act,mcp]'` on a lightweight host installs only the
  dependencies the `read act mcp` roles need.
- `uv sync --extra sync --extra ingest` on a scheduled-job host installs those dependencies without
  the heavier NLP extras.

## Derivations
- A tool that runs different roles on different hosts, where one role needs heavy NLP dependencies
  (e.g. Presidio/spaCy) and others don't: extras alone don't stop `import spacy` at module load time
  from running on every invocation; the package must defer heavy imports into the function/command
  that a given role actually uses (e.g. import inside that command's handler, not at the package's
  top-level `__init__.py`), so a host installed with only the lighter extras never even attempts the
  import. [DER S1706: extras control install-time deps only, not import-time behaviour, so lazy
  imports are still required to keep role isolation real]
- A team that wants a single pure-Python package, with role/kind selected by configuration rather than
  a separate binary per role: one package with extras (not uv workspaces / multiple distributions)
  fits that — one wheel, one version, several roles selected by config and by which extras were
  installed — workspaces would reintroduce a multi-package surface such a team is trying to avoid.
  [DER S1706,S1708: extras give one distribution + optional installs, workspaces give many
  distributions — only the former matches "one Python package"]

## Conflicts
- None found between PyPA and uv docs; uv's extras/groups model is a direct implementation of
  PEP 621/PEP 735, no divergence noted. [DOC S1705,S1706,S1707]
