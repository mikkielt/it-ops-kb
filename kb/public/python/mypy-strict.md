---
topic: python/mypy-strict
priority: P3
applies_to: "mypy 2.4.0 (docs and source read at release tag v2.4.0); ruff 0.16.9 FAQ; maturin 1.15.0 project-layout guide"
retrieved_utc: 2026-10-11
sources: [S-butt7tqv, S-itulia5o, S-dsu27qym, S-djet36tw, S-cmxorblf, S-2ial3y55, S-3zldz37q, S-hec62m7j]
status: partial
---

# mypy --strict as a CI gate beside ruff

## Summary
`mypy --strict` (or `strict = true` in `[tool.mypy]`) turns on a fixed bundle of optional checks that the
mypy project says may change between versions, so a CI gate should pin the mypy version. mypy exits
`0` (no errors), `1` (type errors) or `2` (blocking error) in the v2.4.0 source. Ruff is a linter and not
a type checker, and its own FAQ says to run both; the repository's ruff facts are in `python/ruff.md`.
For a compiled extension module (for example a PyO3 module built with maturin), mypy needs a `.pyi`
stub plus a `py.typed` marker to see any types, and `stubtest` can check the stub against the runtime
module. This article covers what a CI gate needs; `python/pytest.md` covers the test gate.

## Facts
- `--strict` "enables a defined subset of optional error-checking flags", primarily checks for
  inadvertent type unsoundness; the v2.4.0 docs say the exact list "may change over time" and point to
  `mypy --help` for the current list (the list is generated at documentation build time, not written in
  the source `.rst`). The same warning is on the config option `strict`. [DOC S-butt7tqv]
- In mypy v2.4.0 the strict set is the options registered with `strict_flag=True`: the 13 flags
  `--disallow-any-generics`, `--disallow-subclassing-any`, `--disallow-untyped-calls`,
  `--disallow-untyped-defs`, `--disallow-incomplete-defs`, `--check-untyped-defs`,
  `--disallow-untyped-decorators`, `--warn-redundant-casts`, `--warn-unused-ignores`,
  `--warn-return-any`, `--no-implicit-reexport`, `--strict-equality`, `--extra-checks`. [CODE S-2ial3y55: mypy/main.py#define_options]
- `--warn-unreachable` is not turned on by `--strict`, and the docs say so. [DOC S-butt7tqv]
- In the same v2.4.0 source, `--disallow-any-explicit`, `--disallow-any-unimported`,
  `--strict-equality-for-none` and `--allow-untyped-globals` are registered without `strict_flag`, so
  they are not part of the strict set; the strict assignments are applied after the config file is read
  and before the remaining command-line options are parsed. [CODE S-2ial3y55: mypy/main.py#process_options]
- `--strict` does not outrank other flags: a flag given explicitly for the alternate behaviour overrides
  strict regardless of the order the flags are passed. [DOC S-butt7tqv]
- `strict` is a boolean config option (default `False`); `warn_unused_ignores` (default `False`) warns
  about unneeded `# type: ignore` comments, and `warn_unused_configs` (default `False`) warns about
  per-module sections that match no file processed, which the docs suggest for catching misspelled
  section names. [DOC S-itulia5o]
- Config discovery walks up from the current directory and in each directory tries `mypy.ini`,
  `.mypy.ini`, `pyproject.toml` (needs a `[tool.mypy]` section) and `setup.cfg` (needs `[mypy]`), in that
  order; files are never merged, and `--config-file` has the highest precedence and must exist. [DOC S-itulia5o]
- In `pyproject.toml` the `[mypy]` section becomes `[tool.mypy]`; each `[mypy-PATTERN]` section becomes a
  `[[tool.mypy.overrides]]` table with `module` set to a string or an array of module patterns; booleans
  are lower case. [DOC S-itulia5o]
- When options conflict, the documented precedence is: inline config, concrete-module sections,
  unstructured-wildcard sections (later wins), structured-wildcard sections (more specific wins), then
  command-line options, then top-level config options. So a per-module override outranks a
  command-line `--strict` for that module. [DOC S-itulia5o]
- Exit status in v2.4.0 `main`: `0` when there are no messages or only notes, `1` when there are error
  messages, `2` when the build reported blocking errors; invalid flag combinations,
  a missing `--config-file` and a PyPy interpreter also end in `2`. With interactive
  `--install-types`, `2` is also returned after stubs were installed so the run is repeated. [CODE S-2ial3y55: mypy/main.py#main]
- The docs read here (command line, config file, running mypy) do not state mypy's exit codes as a
  documented contract; the values above come from the source only. [UNK]
- Ruff is a linter, not a type checker: it can detect some of the same problems but a type checker
  catches errors it misses and the reverse; the ruff FAQ recommends using Ruff together with a type
  checker such as Mypy, Pyright or Pyre (ruff 0.16.9 docs). [DOC S-3zldz37q]
- A package that ships inline types or stubs next to its code should put an empty `py.typed` file in
  its package directory; a package mixing `lib.py` and `lib.pyi` also needs `py.typed`, and mypy then
  reads `lib.pyi` where the interpreter loads `lib.py`. [DOC S-dsu27qym]
- maturin (1.15.0 guide): in a pure-Rust project a `<module_name>.pyi` in the project root is included in
  the build together with a generated `py.typed`; in a mixed Rust/Python project the `py.typed` marker
  and the `.pyi` files go in the Python package directory and the marker is the author's job. [DOC S-hec62m7j]
- mypy ships `stubtest`, which imports the module, introspects it at runtime and reports differences from
  its stubs; the docs say it works well with extension modules, that it cannot type-check code, and that
  it imports and executes the code it checks. [DOC S-cmxorblf]
- Without stubs or a `py.typed` marker, an installed module is reported as "module is installed, but
  missing library stubs or py.typed marker", because mypy does not infer types of installed third-party
  code unless it declares PEP 561 support or is registered with typeshed. [DOC S-djet36tw]
- For a compiled extension built in the same repository, a missing `.pyi` is therefore a gate failure
  under strict (untyped import) rather than a silent pass; the fix is the stub plus `py.typed`, not
  `--ignore-missing-imports`, which the docs recommend avoiding if possible. [DER S-djet36tw, S-dsu27qym, S-hec62m7j: running_mypy "missing library stubs" text applied to a stub-less extension module]
- Third-party stubs (`types-<library>`, mostly from typeshed) are separate packages. The running-mypy
  docs advise treating them like any other test dependency in CI (a requirements file), and describe
  `--install-types` as slower, since mypy effectively runs twice, and as making stub versions harder to
  control; `--non-interactive` installs without a prompt. [DOC S-djet36tw]
- If mypy is pinned to an older version, the docs recommend also pinning the stub packages, because new
  stub versions can use type-system features that older mypy versions do not support. [DOC S-dsu27qym]
- Incremental mode is on by default; the cache is `.mypy_cache` in the current directory, relocated by
  `--cache-dir` or `MYPY_CACHE_DIR` (the flag wins). `--no-incremental` stops reading the cache but mypy
  still writes it; `--cache-dir=/dev/null` (UNIX) or `nul` (Windows) disables writing. [DOC S-butt7tqv]
- Since mypy 2.0 `bytearray` and `memoryview` are no longer treated as subtypes of `bytes` by default
  (`strict_bytes` defaults to `True`; `--no-strict-bytes` restores the old behaviour). [DOC S-itulia5o]

## Reference
| Strict flag (v2.4.0 source) | Config key |
|---|---|
| `--disallow-any-generics` | `disallow_any_generics` |
| `--disallow-subclassing-any` | `disallow_subclassing_any` |
| `--disallow-untyped-calls` | `disallow_untyped_calls` |
| `--disallow-untyped-defs` | `disallow_untyped_defs` |
| `--disallow-incomplete-defs` | `disallow_incomplete_defs` |
| `--check-untyped-defs` | `check_untyped_defs` |
| `--disallow-untyped-decorators` | `disallow_untyped_decorators` |
| `--warn-redundant-casts` | `warn_redundant_casts` |
| `--warn-unused-ignores` | `warn_unused_ignores` |
| `--warn-return-any` | `warn_return_any` |
| `--no-implicit-reexport` | `implicit_reexport = false` |
| `--strict-equality` | `strict_equality` |
| `--extra-checks` | `extra_checks` |

| Exit status | Meaning (v2.4.0 source) |
|---|---|
| `0` | no messages, or notes only |
| `1` | type errors reported |
| `2` | blocking error, invalid options, or `--install-types` installed stubs |

## Examples
- SNIPPET: `[tool.mypy]` with strict mode and one per-module override for a third-party module that has no stubs; context: mypy 2.4.0, pyproject.toml, module names are placeholders; checked: syntax [DER S-itulia5o: `python_version`, `strict`, `warn_unused_configs` options and the `[[tool.mypy.overrides]]` table form from the config docs]
```toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_unused_configs = true

[[tool.mypy.overrides]]
module = "somelibrary.*"
ignore_missing_imports = true
```
- SNIPPET: the CI step and the stub layout for a maturin mixed project; context: mypy 2.4.0, maturin 1.15.0; checked: no [DER S-butt7tqv, S-djet36tw, S-hec62m7j: stub packages installed as test dependencies, config found by walking up from the current directory, `.pyi` and `py.typed` in the Python package directory]
```text
$ pip install mypy==2.4.0 types-requests     # pinned like any test dependency
$ mypy python/                                # exit 0 clean, 1 errors, 2 blocking

python/example_tool/__init__.py
python/example_tool/py.typed                  # empty marker, added by hand
python/example_tool/_native.pyi               # stubs for the compiled module
```
