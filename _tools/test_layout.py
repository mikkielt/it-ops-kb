"""The import rules of kb/_self/code.md (Imports), held over every _tools/*.py parsed with ast (never run):

- a prefixed helper (`ql_*`, `kg_*`, `bench_*`) never imports its facade (`querylog`, `kbgit`, `benchmarks`), at any depth;
- no module imports a name that starts with `_` from another _tools module (`from x import _y`) or reaches one through
  the module (`x._y`, also through `import x as z`): a leading underscore means the module's own.

The exceptions the tree had when the rule was written are listed by name in EXCEPTIONS; a new one fails, and so does a
listed one that no longer occurs, so the list only shrinks. Planted sources prove each rule fails when broken.
"""
import ast
from pathlib import Path

from conftest import TOOLS

FACADES = {"ql_": "querylog", "kg_": "kbgit", "bench_": "benchmarks"}

# (importing module, module it reaches into, the underscore name): what kind of reach it is. One entry per pair,
# however many uses.
TOOL, INSIDE, HELPER = "a tool reaches into a sibling", "a test reaches inside the module it drives", "a test file reuses a helper of another"
EXCEPTIONS = {
    ("kbpublic", "kbcommon", "_meta"): TOOL,
    ("factdiff", "provider", "_sibling"): TOOL,
    ("ql_learn", "provider", "_read"): TOOL,
    ("provider", "fetch", "_PageText"): TOOL,
    ("ql_apply", "kbfacts", "_FP"): TOOL,
    ("test_backlog", "kbgit", "_WANT"): INSIDE,
    ("test_factdiff", "factdiff", "_added"): INSIDE,
    ("test_factdiff", "factdiff", "_git"): INSIDE,
    ("test_factdiff", "factdiff", "_madeup"): INSIDE,
    ("test_factdiff", "factdiff", "_pages"): INSIDE,
    ("test_kb", "kbfacts", "_STORE"): INSIDE,
    ("test_kb_http", "test_kb_mcp", "_behind_clone"): HELPER,
    ("test_kb_root", "test_kb_mcp", "_embedded"): HELPER,
    ("test_ql_distill", "ql_distill", "_distill"): INSIDE,
    ("test_querylog", "provider", "_read"): INSIDE,
}


def private(name):
    return name.startswith("_") and not (name.startswith("__") and name.endswith("__"))


def violations(sources):
    """{(kind, module, target, name)} for `sources` ({module name: source text}); kind is `facade` or `private`, and
    `name` is the facade or the underscore name."""
    found = set()
    for mod, text in sources.items():
        tree = ast.parse(text)
        alias = {}  # the name a tool module is bound to in this file -> the module
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    if "." not in a.name and a.name in sources and a.name != mod:
                        alias[a.asname or a.name] = a.name
            elif isinstance(n, ast.ImportFrom) and n.module and not n.level and n.module in sources and n.module != mod:
                for a in n.names:
                    if private(a.name):
                        found.add(("private", mod, n.module, a.name))
        for n in ast.walk(tree):
            if isinstance(n, ast.Attribute) and private(n.attr) and isinstance(n.value, ast.Name) \
                    and n.value.id in alias:
                found.add(("private", mod, alias[n.value.id], n.attr))
        for prefix, facade in FACADES.items():
            if mod.startswith(prefix) and any(
                    (isinstance(n, ast.Import) and any(a.name.split(".")[0] == facade for a in n.names))
                    or (isinstance(n, ast.ImportFrom) and n.module and not n.level and n.module.split(".")[0] == facade)
                    for n in ast.walk(tree)):
                found.add(("facade", mod, facade, facade))
    return found


def unexcused(sources):
    return sorted(v for v in violations(sources) if v[0] == "facade" or v[1:] not in EXCEPTIONS)


def tool_sources():
    return {p.stem: p.read_text(encoding="utf-8") for p in sorted(Path(TOOLS).glob("*.py"))}


def test_import_layers_tree_holds():
    bad = unexcused(tool_sources())
    assert not bad, "import direction broken (kb/_self/code.md, Imports): " + "; ".join(
        f"{m} imports {'its facade ' + n if k == 'facade' else n + ' from ' + t}" for k, m, t, n in bad)


def test_import_layers_exceptions_are_all_still_used():
    used = {v[1:] for v in violations(tool_sources()) if v[0] == "private"}
    assert not set(EXCEPTIONS) - used, f"remove from EXCEPTIONS: {sorted(set(EXCEPTIONS) - used)}"


def test_import_layers_helper_importing_its_facade_fails():
    for prefix, facade in FACADES.items():
        helper = prefix + "stage"
        for body in (f"import {facade}\n", f"from {facade} import main\n", f"import {facade} as f\n",
                     f"def late():\n    import {facade}\n"):
            src = {facade: "", helper: body, prefix + "base": ""}
            assert unexcused(src) == [("facade", helper, facade, facade)], (helper, body)


def test_import_layers_facade_and_siblings_may_import_below():
    src = {"querylog": "import ql_base, ql_store\nfrom ql_store import load\n", "ql_base": "",
           "ql_store": "import ql_base\n", "kbgit": "import kg_base\n", "kg_base": "",
           "benchmarks": "from bench_base import row\n", "bench_base": "", "other": "import querylog\n"}
    assert unexcused(src) == []


def test_import_layers_underscore_name_across_modules_fails():
    for body in ("from b import _hidden\n", "from b import x, _hidden as h\n", "import b\nb._hidden()\n",
                 "import b as m\nvalue = m._hidden\n", "def f():\n    import b\n    return b._hidden\n"):
        assert unexcused({"a": body, "b": "_hidden = 1\n"}) == [("private", "a", "b", "_hidden")], body


def test_import_layers_underscore_rule_leaves_own_dunder_public_and_stdlib_alone():
    src = {"a": "import os, b\nfrom b import public, __version__\nfrom os import _exit\nos._exit(0)\nb.public()\n"
                "b.__doc__\nx._attr\nclass C:\n    def m(self):\n        return self._own\n"
                "def f():\n    return a._own\n",
           "b": "import b\nb._own\nfrom b import _own\n"}
    assert unexcused(src) == []


def test_import_layers_a_planted_violation_fails_on_the_real_tree():
    tree = tool_sources()
    assert unexcused(tree) == []
    planted = dict(tree, ql_planted="import querylog\n", kg_planted="from kbgit import main\n",
                   bench_planted="import benchmarks\n", planted_reach="import kbcommon\nkbcommon._meta\n")
    assert {v[1] for v in unexcused(planted)} == {"bench_planted", "kg_planted", "planted_reach", "ql_planted"}
    # a listed exception covers its own pair only: the same name reached from another module is a new violation
    assert ("private", "planted_reach", "kbcommon", "_meta") in unexcused(planted)
    # and a listed pair stops being one when the reach goes away
    assert ("kbpublic", "kbcommon", "_meta") in EXCEPTIONS
    assert ("kbpublic", "kbcommon", "_meta") not in {v[1:] for v in violations(dict(tree, kbpublic=""))}
