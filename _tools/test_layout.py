"""The import rules of kb/_self/code.md (Imports), held over every _tools/*.py parsed with ast (never run):

- a prefixed helper (`ql_*`, `kg_*`, `bench_*`, `bl_*`) never imports its facade (`querylog`, `kbgit`, `benchmarks`, `backlog`), at any depth;
- no module imports a name that starts with `_` from another _tools module (`from x import _y`) or reaches one through
  the module (`x._y`, also through `import x as z`): a leading underscore means the module's own.

The exceptions the tree had when the rule was written are listed by name in EXCEPTIONS; a new one fails, and so does a
listed one that no longer occurs, so the list only shrinks. Planted sources prove each rule fails when broken.
"""
import ast
from pathlib import Path

from conftest import TOOLS

FACADES = {"ql_": "querylog", "kg_": "kbgit", "bench_": "benchmarks", "bl_": "backlog"}

# (importing module, module it reaches into, the underscore name): what kind of reach it is. One entry per pair,
# however many uses.
TOOL, INSIDE, HELPER = "a tool reaches into a sibling", "a test reaches inside the module it drives", "a test file reuses a helper of another"
EXCEPTIONS = {
    ("kbpublic", "kbcommon", "_meta"): TOOL,
    ("factdiff", "provider", "_sibling"): TOOL,
    ("ql_learn", "provider", "_read"): TOOL,
    ("provider", "fetch", "_PageText"): TOOL,
    ("ql_apply", "kbfacts", "_FP"): TOOL,
    ("test_backlog", "kg_trailers", "_WANT"): INSIDE,
    ("test_factdiff", "factdiff", "_added"): INSIDE,
    ("test_factdiff", "factdiff", "_git"): INSIDE,
    ("test_factdiff", "factdiff", "_madeup"): INSIDE,
    ("test_factdiff", "factdiff", "_pages"): INSIDE,
    ("test_kb_http", "test_kb_mcp", "_behind_clone"): HELPER,
    ("test_kb_lookup", "kbfacts", "_STORE"): INSIDE,
    ("test_kb_root", "test_kb_mcp", "_embedded"): HELPER,
    ("test_ql_distill", "ql_distill", "_distill"): INSIDE,
    ("test_ql_learn", "provider", "_read"): INSIDE,
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


def test_import_layers_bl_helper_imports_backlog_fails():
    for body in ("import backlog\n", "from backlog import main\n", "def late():\n    import backlog\n"):
        src = {"backlog": "", "bl_intake": body}
        assert unexcused(src) == [("facade", "bl_intake", "backlog", "backlog")], body


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


def from_kit(node):
    """An assignment whose value is `bl_testkit.NAME` (or a tuple of them): the kit's own object bound by name."""
    v = node.value
    return all(isinstance(x, ast.Attribute) and isinstance(x.value, ast.Name) and x.value.id == "bl_testkit"
               for x in (v.elts if isinstance(v, ast.Tuple) else [v]))


def kit_names(source):
    """The public names a module defines at its top level: functions, classes and assigned names, but not a name
    bound to the kit's own object (`repo = bl_testkit.repo`, a fixture bound where its tests ask for it)."""
    names = set()
    for n in ast.parse(source).body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            names.add(n.name)
        elif isinstance(n, (ast.Assign, ast.AnnAssign)) and not (n.value and from_kit(n)):
            for t in n.targets if isinstance(n, ast.Assign) else [n.target]:
                names |= {x.id for x in ast.walk(t) if isinstance(x, ast.Name)}
    return {x for x in names if not x.startswith("_")}


def own_copies(kit, tests):
    """(test file, name) for each top-level definition in a test file that bl_testkit defines too."""
    shared = kit_names(kit)
    return sorted((f, n) for f, src in tests.items() for n in kit_names(src) & shared)


def backlog_test_sources():
    paths = sorted(set(Path(TOOLS).glob("test_*backlog*.py")) | set(Path(TOOLS).glob("test_bl_*.py")))
    return {p.name: p.read_text(encoding="utf-8") for p in paths}


def test_bl_split_testkit_no_test_file_keeps_its_own_copy_of_a_builder():
    kit = (Path(TOOLS) / "bl_testkit.py").read_text(encoding="utf-8")
    assert {"repo", "sprint", "b", "item", "edit", "commit"} <= kit_names(kit)
    assert own_copies(kit, backlog_test_sources()) == [], "import it from bl_testkit instead of defining it again"


def test_bl_split_testkit_planted_copy_of_a_builder_fails():
    kit = "def b(root, *a):\n    return 0\n\n" + "@pytest.fixture\ndef repo(tmp_path):\n    return tmp_path\n\nPASS = 1\n_own = 2\n"
    tests = {"test_bl_planted.py": "import bl_testkit\nrepo, sprint = bl_testkit.repo, bl_testkit.sprint\ndef b(root, *a):\n    return 1\nPASS = 2\n_own = 3\n",
             "test_bl_clean.py": "from bl_testkit import b\ndef helper(root):\n    return b(root)\n"}
    assert own_copies(kit, tests) == [("test_bl_planted.py", "PASS"), ("test_bl_planted.py", "b")]


BASE_CORE = {"Backlog", "Refused", "Rejected", "git", "run", "need", "say", "withhold", "commit_written", "commit_message",
             "scope", "in_scope", "glob_re", "research_touches", "item_file", "REL_DIR", "KINDS", "ID_RE", "TEXT_MAX"}


def tool_source(name):
    return (Path(TOOLS) / name).read_text(encoding="utf-8")


def imported_from(source, module):
    """The names a module's source imports from `module`, at any depth."""
    return {a.name for n in ast.walk(ast.parse(source)) if isinstance(n, ast.ImportFrom) and n.module == module
            for a in n.names}


def test_bl_split_base_holds_the_shared_ground_and_backlog_defines_none_of_it():
    base = tool_source("bl_base.py")
    assert BASE_CORE <= kit_names(base)
    assert own_copies(base, {"backlog.py": tool_source("backlog.py")}) == [], "backlog.py imports it from bl_base"


def test_bl_split_base_backlog_reexports_the_objects_not_copies():
    import backlog
    import bl_base
    for name in ("Backlog", "Refused", "Rejected", "git", "run", "need", "say", "commit_written", "in_scope", "KINDS"):
        assert getattr(backlog, name) is getattr(bl_base, name), name


def test_bl_split_base_bl_intake_takes_its_ground_from_bl_base_and_never_backlog():
    src = tool_source("bl_intake.py")
    assert {"REL_DIR", "TEXT_MAX"} <= imported_from(src, "bl_base")
    assert not imported_from(src, "backlog")
    assert "TEXT_MAX" not in kit_names(src), "bl_intake.py holds a copy of a bl_base constant"


def test_bl_split_base_imports_no_backlog_at_any_depth():
    tree = tool_sources()
    assert not [m for m, s in tree.items() if m.startswith("bl_") and imported_from(s, "backlog")]
    assert not any(isinstance(n, ast.Import) and any(a.name == "backlog" for a in n.names)
                   for m, s in tree.items() if m.startswith("bl_") for n in ast.walk(ast.parse(s)))


def test_bl_split_base_planted_failures_fail():
    base = tool_source("bl_base.py")
    # a name put back in backlog.py
    for body in ("class Refused(Exception):\n    pass\n", "def git(root, *args):\n    return ''\n", "REL_DIR = 'x'\n"):
        assert own_copies(base, {"backlog.py": body}) != [], body
    # an import of backlog by a bl_ module, however deep
    for body in ("import backlog\n", "from backlog import Refused\n", "def late():\n    from backlog import say\n"):
        assert unexcused({"backlog": "", "bl_base": body}) == [("facade", "bl_base", "backlog", "backlog")], body
    # a copy of a bl_base constant in bl_intake.py is seen
    assert "TEXT_MAX" in kit_names("TEXT_MAX = 2000\n") and "TEXT_MAX" not in kit_names("from bl_base import TEXT_MAX\n")


SUBCOMMANDS = ("new", "similar", "check", "fmt", "selectors", "list", "tree", "find", "show", "next", "held", "claim",
               "release", "answer", "set", "move", "reopen", "gate", "fire", "done", "land", "drop", "start",
               "host-check", "close", "horizon", "goal", "referrers", "cost", "red-pipeline", "intake")


def add_parser_calls(source, func):
    """The `add_parser` calls inside the function `func` of `source`."""
    fn = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef) and n.name == func)
    return [n for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "add_parser"]


def test_bl_split_parser_registry_main_builds_from_the_registry_and_holds_no_parser():
    import backlog
    import bl_cli
    assert add_parser_calls(tool_source("backlog.py"), "main") == []
    assert tuple(bl_cli.COMMANDS) == SUBCOMMANDS, "the registry keeps the order argparse prints"
    ap = bl_cli.build_parser("d", "r")
    usage = ap.format_usage()
    assert "{" + ",".join(SUBCOMMANDS) + "}" in usage
    assert all(bl_cli.handler_of(n) is getattr(backlog, "cmd_" + n.replace("-", "_")) for n in SUBCOMMANDS)
    for n in SUBCOMMANDS:  # --commit and --trailer exactly on the commands that commit
        sub = next(a for a in ap._actions if a.dest == "cmd").choices[n]
        assert ("--commit" in sub._option_string_actions) == (n in backlog.COMMITS), n


def test_bl_split_parser_registry_refuses_a_second_registration_of_a_name():
    import bl_cli
    reg = {}
    bl_cli.register("one", print, registry=reg)
    try:
        bl_cli.register("one", print, registry=reg)
    except ValueError as e:
        assert "registered twice" in str(e)
    else:
        raise AssertionError("a duplicate subcommand name was accepted")
    try:
        bl_cli.register("show", print)  # the real registry holds it
    except ValueError:
        pass
    else:
        raise AssertionError("a duplicate of a real subcommand was accepted")
    assert tuple(bl_cli.COMMANDS) == SUBCOMMANDS


def test_bl_split_parser_registry_planted_failures_fail():
    import bl_cli
    # an add_parser call put back in main is seen
    planted = "def main(argv=None):\n    p = sub.add_parser('new')\n"
    assert len(add_parser_calls(planted, "main")) == 1
    assert add_parser_calls("def main(argv=None):\n    ap = bl_cli.build_parser('d', 'r')\n", "main") == []
    # a registry built in another order prints another usage
    reg = {}
    for n in reversed(SUBCOMMANDS):
        bl_cli.register(n, print, registry=reg)
    assert "{" + ",".join(SUBCOMMANDS) + "}" not in bl_cli.build_parser("d", "r", registry=reg).format_usage()
    # a registered command with no arguments still parses, one with a help line shows it
    reg = {}
    bl_cli.register("zero", print, registry=reg, help="does nothing")
    assert "does nothing" in bl_cli.build_parser("d", "r", registry=reg).format_help()
    # bl_cli never imports backlog
    assert not imported_from(tool_source("bl_cli.py"), "backlog")
