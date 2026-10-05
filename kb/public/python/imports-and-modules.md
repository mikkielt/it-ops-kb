---
topic: python/imports-and-modules
priority: P3
applies_to: [python]
retrieved_utc: 2026-10-05
sources: [S-y3vaig55, S-pnak2iyz, S-uwxacpum, S-d77lvlq4, S-kzlfvktk, S-o7nczrbn, S-nmpccgft, S-ci5jq2sq, S-q5frtccp, S-27tycl3n]
status: complete
---

# Python modules and imports in a flat directory of scripts

## Summary
A directory of scripts with no package (a flat `_tools/`) resolves its imports through `sys.path[0]`,
the directory of the script that started the run. That is why sibling modules import by bare name, why a
module can be both a script and a library, and why import cycles and underscore names matter when one large
script is split into several modules. This article records what the Python documentation and PEP 8 say
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
- Not found in the official pages read: what happens when a file run as a script is also imported by another module under its own name. The documentation says only that a script's `__name__` is `"__main__"`, so whether the file loads a second time as a separate module is left as a lead. [UNK: looked in the tutorial, the reference and library/__main__ at v3.14.7]
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
