---
topic: python/ruff
priority: P2
applies_to: [ruff]
retrieved_utc: 2026-09-27
sources: [S-y3zhzpmv, S-7fmtkrv5, S-qgwumz4k, S-s3ytflwh, S-yfbe6ete, S-guaor3a5, S-my7mtswb, S-ntllah3f]
status: complete
---

# ruff configuration and linting

## Summary
`ruff check` is the linter entry point and `ruff format` is a separate, Black-compatible formatter
entry point — this repository only uses the linter (`ruff check`, restricted to `select = ["F"]`,
pyflakes rules). Both read the same `pyproject.toml`/`ruff.toml`/`.ruff.toml` configuration. Rule
codes are grouped by a one-to-three letter prefix identifying their source linter (`F` = Pyflakes,
`E`/`W` = pycodestyle, `I` = isort, and so on); `select`/`ignore`/`per-file-ignores` accept full codes
or any valid prefix. As of ruff 0.16.9 (the version this repository pins), ruff's *default* rule set
(used only when `select` is left unset entirely) is not simply a short prefix list — it is an
explicitly curated list of 413 individual rule codes spanning many families (F, E/W, UP, B, SIM, PYI,
RUF, PLC/PLE/PLR/PLW, FURB, ASYNC, PT, DTZ and others); this repository does not rely on that default,
since it sets `select = ["F"]` explicitly.

## Facts
- `ruff check` lints files/directories recursively and can auto-fix with `--fix`; `ruff check --watch`
  re-lints on file change. `ruff format` is the separate formatter command; running it in-place
  reformats files, while `ruff format --check` reports unformatted files without writing changes,
  matching Black's `--check` semantics. [DOC S-y3zhzpmv, S-qgwumz4k]
- Rule codes are a 1-3 letter linter prefix plus digits (e.g. `F401`); the prefix names the "source"
  linter Ruff reimplements — `F` = Pyflakes, `E`/`W` = pycodestyle, `I` = isort, `UP` = pyupgrade,
  `B` = flake8-bugbear, `ANN` = flake8-annotations, and so on for dozens of other prefixes (confirmed
  against the rule registry, which maps each code like `E101` to its owning linter, e.g.
  `(Pycodestyle, "E101")`). `select` and `ignore` accept either an exact code or any valid prefix (e.g.
  `"E"` selects every pycodestyle rule). `ALL` selects every rule. [DOC S-y3zhzpmv, S-my7mtswb]
- Selector precedence, broadest to narrowest: `ALL < category < linter group < linter prefix < rule`;
  `ignore` takes precedence over `select` for the same specificity, and CLI options outrank
  `pyproject.toml`/`ruff.toml` settings, which outrank inherited config files. [DOC S-y3zhzpmv]
- If `select` is left completely unset, ruff 0.16.9's stable default is `DEFAULT_SELECTORS`: 413
  individually-listed rules (not a small set of prefixes), drawn heavily from `PYI`, `UP`, `F`, `RUF`,
  `PLE`/`PLW`/`PLR`/`PLC`, `B`, `SIM`, `FURB`, `C` (mccabe/comprehensions), `ASYNC`, `YTT`, `DTZ`, `PT`,
  `PIE`, `TRY`, `LOG`, `TC`, `G`, `EXE`, `S`, `PERF`, `INT`, `PTH`, `FA`, plus a couple each of `E`/`W`.
  [DOC S-yfbe6ete]
- This repository overrides that default entirely: `[tool.ruff.lint] select = ["F"]` (Pyflakes rules
  only — unused/undefined names and redefinitions), with `ignore = ["E731"]` (this ignore has no
  effect while `E` is not selected, but is harmless) and a comment explaining the choice keeps "the
  code's own layout". [DER S-y3zhzpmv: `select = ["F"]` selects exactly the Pyflakes-prefixed rules per
  the prefix rule above, overriding ruff's own default rule set.]
- `# noqa: CODE1, CODE2` on a line suppresses those specific violations for that line; a bare `# noqa`
  suppresses everything on that line. For a `noqa` on a multi-line string, it goes after the closing
  quote and covers the whole string; for an import block, it goes at the end of the first import line
  and covers the whole block. A file-level `# ruff: noqa` (or `# ruff: noqa: CODE`) anywhere in the
  file (preferably near the top) suppresses that violation kind across the entire file; Ruff also
  honours Flake8's `# flake8: noqa` as equivalent. [DOC S-7fmtkrv5]
- `ruff check` exits `0` when no violations remain (including when `--fix` fixed everything), `1` when
  violations were found, `2` on abnormal termination (invalid config/CLI options or an internal
  error). `--exit-zero` forces exit `0` even with remaining violations; `--exit-non-zero-on-fix` forces
  exit `1` if violations were found even though `--fix` fixed all of them. [DOC S-7fmtkrv5]
- `--output-format` accepts `concise`, `full` (default), `json`, `json-lines`, `junit`, `grouped`,
  `github`, `gitlab`, `pylint`, `rdjson`, `azure`, `sarif`; only `full`, `concise` and `grouped` are
  "human-readable" (include header/footer text) rather than machine-oriented. [DOC S-guaor3a5]
- `target-version` (e.g. `"py39"`) sets the minimum Python syntax/version ruff assumes for
  version-gated rules (defaults to `"py310"` if left unset and there is no `requires-python`). If a
  `pyproject.toml` sets `project.requires-python` (e.g. `">=3.9"`) and `target-version` is *not* set
  explicitly, ruff derives the equivalent `target-version` from the lower bound of `requires-python`
  (`>=3.9` behaves like `target-version = "py39"`, matching this repository's explicit
  `target-version = "py39"` and its `requires-python = ">=3.9"`). If both are set, the explicit
  `target-version` wins. [DOC S-s3ytflwh, S-ntllah3f]
- `per-file-ignores` (a table mapping glob file patterns to rule codes/prefixes to ignore for matching
  files) and `extend-per-file-ignores` (adds to it without replacing) let a project silence rules only
  in specific files, e.g. `E402` in `__init__.py`. [DOC S-s3ytflwh]
- The default `line-length` is 88 and `indent-width` is 4 (matching Black); this repository overrides
  `line-length` to 200. Ruff's own stated default configuration also excludes common tooling
  directories (`.venv`, `.git`, `.mypy_cache`, `dist`, `build`, etc.) by default. [DOC S-7fmtkrv5]

## Reference
```toml
[tool.ruff]
line-length = 200
target-version = "py39"
extend-exclude = ["_cache", "_private"]

[tool.ruff.lint]
select = ["F"]
ignore = ["E731"]
```
```console
$ ruff check                              # lint the current directory
$ ruff check --fix                        # lint and apply safe fixes
$ ruff check --output-format=concise .    # compact one-line-per-violation output
$ ruff format --check .                   # verify formatting without writing (not used by this repo)
```

## Examples
- CI runs `ruff check` with no arguments (repo default paths) and treats a non-zero exit as a failed
  job, since `2` (bad config/internal error) and `1` (violations found) both indicate something to fix.
- `# noqa: F401` on an intentionally-unused import (e.g. a re-export in `__init__.py`) suppresses only
  that Pyflakes rule on that line, leaving other Pyflakes checks active.
