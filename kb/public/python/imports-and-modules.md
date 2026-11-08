---
topic: python/imports-and-modules
priority: P3
applies_to: [python]
retrieved_utc: 2026-11-08
sources: [S-lebxvs2r, S-y3vaig55, S-pnak2iyz, S-uwxacpum, S-d77lvlq4, S-kzlfvktk, S-o7nczrbn, S-nmpccgft, S-ci5jq2sq, S-q5frtccp, S-27tycl3n, S-blp22gnh, S-k56yckat, S-irs7c62v, S-b576ksco]
status: complete
---

# Python modules and imports in a flat directory of scripts

## Summary
A directory of scripts with no package (a flat `_tools/`) resolves its imports through `sys.path[0]`,
the directory of the script that started the run. That is why sibling modules import by bare name, why a
module can be both a script and a library, and why import cycles and underscore names matter when one large
script is split into several modules. It also records how a loader finds a plugin by entry point group or by a
`module:attr` name (`importlib.metadata`, `import_module`); the version side of such a plugin API is in
`python/extension-api-versioning.md`. This article records what the Python documentation and PEP 8 say
about those points; the rest of the Python tooling is in `python/pytest.md` (test discovery and import
modes) and `python/ruff.md` (lint and size rules), and `agents/codebase-mapping.md` covers `ast` and
`ruff analyze graph` as import maps.

## Facts
- The first entry of `sys.path` is the directory that contains the input script; with no script (interactive shell, `-c`, `-m`) it is the current directory. `PYTHONPATH` entries and the standard-library directories follow. [DOC S-kzlfvktk]
- The script's directory is placed ahead of the standard-library path, so a script-directory module with a standard-library name hides the library one; the docs call this an error unless intended. The script's directory is computed after following a symlink, so the directory holding the symlink is not added. [DOC S-y3vaig55]
- `-P` (or `PYTHONSAFEPATH`, Python 3.11+) stops Python prepending the script's directory (`python script.py`) or the current directory (`python -m module`); `-I` (isolated mode) implies `-P`, so a script's sibling modules are then not importable by bare name. [DOC S-d77lvlq4]
- A module's top-level statements run only the first time its name is imported (and when the file runs as a script). A file becomes usable as both script and library by guarding its entry point with `if __name__ == "__main__":`, which does not run when another module imports it. [DOC S-y3vaig55, S-o7nczrbn]
- Circular imports work when both modules use `import module` and fail when the second does `from module import name` at top level, because the first module is still executing and its names do not exist yet; the same failure appears with `import foo` followed by `foo.name` in global code. [DOC S-uwxacpum]
- The FAQ lists three remedies that can be combined: use only `import module` and reference `module.name` inside functions, order each module as exports then imports then active code, or restructure so the recursive import is unnecessary. Moving an import into a function is for a real circular import or start-up cost, and a repeated import costs a dictionary lookup because the module stays in `sys.modules`. [DOC S-uwxacpum]
- `from module import *` imports every name except those starting with an underscore, and the docs call `import *` bad practice in production code; naming the module you need (`from package import submodule`) is the recommended form. [DOC S-y3vaig55]
- A name with a leading underscore is by convention a non-public part of the API and an implementation detail that may change without notice; PEP 8 calls it a weak "internal use" indicator. Documented interfaces are public and undocumented ones are to be assumed internal. [DOC S-pnak2iyz, S-nmpccgft]
- PEP 8 asks for short, all-lowercase module names, with underscores allowed when they help readability; imports go at the top, grouped standard library, third party, local. Absolute imports are recommended and explicit relative imports are an accepted alternative in complex package layouts. [DOC S-nmpccgft]
- PEP 8 says wildcard imports should be avoided, with one defensible use (republishing an internal interface as a public API), and that modules should declare their public names in `__all__`. [DOC S-nmpccgft]
- `ast.parse` turns source into a tree without running it. An `ast.Import` node has `names`, a list of `alias` nodes; an `ast.ImportFrom` node has `module` (a string without leading dots, `None` for `from . import foo`), `names` and `level` (0 means absolute). `ast.walk` yields every descendant node in no specified order. [DOC S-ci5jq2sq]
- A check of import direction between flat modules can parse each file, walk all `Import` and `ImportFrom` nodes (the walk also reaches imports inside function bodies, so a lazy import that avoids a cycle still counts), map `module` or `alias.name` to a sibling file, and flag an import of the facade or of a name starting with `_`; sort the findings, since the walk order is unspecified. The language itself blocks neither. [DER S-ci5jq2sq, S-y3vaig55, S-pnak2iyz: node fields and the underscore convention as documented above]
- A prefix such as `kg_` or `bench_` on sibling modules is a naming choice within PEP 8's lowercase-with-underscores form, and a facade script run as `python _tools/kbgit.py` puts `_tools/` first on `sys.path`, so its helper modules import by bare name from any working directory. [DER S-nmpccgft, S-kzlfvktk: naming rule and the sys.path[0] rule]
- The import reference's section "Special considerations for `__main__`" says that even when `__main__` corresponds to an importable module, the two are "still considered distinct modules", because the blocks guarded by `if __name__ == "__main__":` run only when the module populates the `__main__` namespace, not during a normal import. [DOC S-lebxvs2r]
- So a file run as a script (`python _tools/kbgit.py`) that a helper module then imports by its own name (`import kbgit`) is executed a second time as a separate module object, with its top-level statements run again and its `__main__` guard skipped; a helper that imports its facade back therefore gets a second copy, not the running script's state. [DER S-lebxvs2r, S-y3vaig55: distinct modules; top-level statements run on each first import]
- `ModuleNotFoundError` (added in 3.6) is "A subclass of ImportError which is raised by import when a module
  could not be located"; `ImportError` is also raised when a name in the "from list" of `from ... import`
  cannot be found, while a failed attribute reference such as `module.name` raises `AttributeError`,
  which is not an `ImportError`. [DOC S-q5frtccp]
- So `except ImportError` catches both a missing module and a missing `from`-imported name, but not a
  missing attribute read through the module; a check that classes "the code could not import" must name
  `AttributeError` beside `ImportError`. [DER S-q5frtccp]
- `unittest.mock.patch` works by name: "you patch where an object is looked up, which is not necessarily the
  same place as where it is defined"; after `from a import SomeClass` in `b`, a test patches `b.SomeClass`.
  [DOC S-27tycl3n]
- So when functions move from one module to another and the old module re-exports them, a test that patched
  the old module's name no longer reaches the moved code's own lookups: such tests patch the new module, and
  the re-export keeps only callers' imports working. [DER S-27tycl3n]
- `importlib.metadata.entry_points(**select_params)` describes the entry points of the current environment as an `EntryPoints` collection, and it hands its keyword parameters to `select` to compare them with each entry point's attributes, so `entry_points(group="g")` and `entry_points().select(group="g")` are the same query. An `EntryPoint` has `name`, `group`, `value`, `module`, `attr`, `extras` and `dist` and a `load()` method that resolves the value. [DOC S-blp22gnh]
- Before Python 3.12 `entry_points()` accepted no parameters and returned a dictionary keyed by group (selection arrived in Python 3.10); from 3.12 it always returns an `EntryPoints` object, and from 3.13 an `EntryPoint` is no longer indexable like a tuple. The docs say a client "will wish to resolve all entry points for a particular group". [DOC S-blp22gnh]
- The entry points specification defines an entry point by a group, a name and an object reference, written `importable.module` or `importable.module:object.attr`, and says to look it up with `importlib.import_module` on the part before the colon and a `getattr` for each dot-separated part after it. [DOC S-irs7c62v]
- A consumer that defines a new entry point group should start its name with a PyPI name it owns and a dot; a group name is letters, digits and underscores in parts separated by dots (`^\w+(\.\w+)*$`), so `it_ops_kb.ranker` is a valid group name. Within one distribution entry point names should be unique. [DOC S-irs7c62v]
- When two distributions provide the same name in one group, the specification says "the consumer decides how to handle such conflicts"; `importlib.metadata` states no rule for it, so a loader that wants exactly one extender for a group counts the selected entry points itself and treats more than one as an error. [DER S-irs7c62v, S-blp22gnh: the specification leaves conflicts to the consumer; the `entry_points` page documents selection and no conflict rule]
- Run on Python 3.13.2 (macOS, `python3 -I`, 2026-11-08) with hand-made `.dist-info` directories on `sys.path`: two different distributions that each declared the name `grp` in one group were both returned by `entry_points(group=...)`, each with its own `dist.name`; one distribution present in two `sys.path` entries returned one entry point, from the entry that came first in `sys.path`; a group nobody declared returned an empty collection. Other Python versions were not run. [DER S-blp22gnh: `entry_points` and `EntryPoint.dist` as documented; the three outcomes are this run's own observation]
- In `pyproject.toml` a package declares entry points in `[project.entry-points]`, a table of tables: each sub-table's name is the group (`[project.entry-points."it_ops_kb.ranker"]`), each key an entry point name and each value an object reference. `[project.scripts]` is the `console_scripts` group, and groups stay one level deep (nested sub-tables are not allowed). [DOC S-b576ksco]
- `importlib.import_module(name, package=None)` imports a module by absolute or relative name and returns that module (not the top-level package, as `importlib.__import__` does); for a module file created after the interpreter started, `importlib.invalidate_caches()` may be needed before the import system sees it. [DOC S-k56yckat]

## Reference
- SNIPPET: list the sibling-module imports of every file in a flat directory; context: Python 3.11+, standard library only; checked: syntax [DER S-ci5jq2sq: `ast.parse`, `ast.walk`, `Import`, `ImportFrom`, `alias` fields as documented]
```python
import ast
import pathlib

def imports(path):
    tree = ast.parse(pathlib.Path(path).read_text(encoding="utf-8"), filename=str(path))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [(a.name, node.lineno) for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found += [(node.module, node.lineno)] + [(a.name, node.lineno) for a in node.names if a.name.startswith("_")]
    return sorted(found)
```
- Related: `python/pytest.md` (import modes, `conftest.py`, `-k`), `python/ruff.md` (module-size rules), `agents/codebase-mapping.md`.

## Examples
- `python3 _tools/rag.py` starts with `_tools/` as `sys.path[0]`, so `import kbfacts` inside it finds `_tools/kbfacts.py` whatever the current directory is; `python3 -I _tools/rag.py` would not.
- Two modules that each run `from other import helper` at the top level fail on the second import; making one of them import inside the function that uses it, or moving the shared helper to a third module both import, removes the cycle.
