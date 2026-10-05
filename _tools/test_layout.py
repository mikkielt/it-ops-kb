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
               "release", "answer", "set", "move", "reopen", "gate", "fire", "done", "land", "merge", "drop", "start",
               "host-check", "close", "horizon", "goal", "referrers", "cost", "red-pipeline", "intake", "procs", "stalled",
               "selfcheck")


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
    import bl_check
    import bl_ci
    import bl_cost
    import bl_land
    import bl_plan
    import bl_procs
    import bl_selfcheck
    import bl_stall
    import bl_view
    owner = {"cost": bl_cost, "procs": bl_procs, "stalled": bl_stall, "selfcheck": bl_selfcheck, "check": bl_check, "selectors": bl_check, "start": bl_plan,
             "done": bl_land, "land": bl_land, "merge": bl_land, "close": bl_land,
             "red-pipeline": bl_ci, "intake": bl_ci, **dict.fromkeys(VIEW_USAGE, bl_view)}  # a command a bl_ module owns: its handler is that module's, not backlog's
    assert all(bl_cli.handler_of(n) is getattr(owner.get(n, backlog), "cmd_" + n.replace("-", "_")) for n in SUBCOMMANDS)
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


COST_MOVED = ("COST_KEYS", "COST_GROUPS", "cost_add", "cost_models", "cost_lines", "cost_scope", "history_parse",
              "history_items", "cost_view", "cost_report", "cost_row", "cost_figures", "cost_block", "cost_overhead",
              "cost_research", "cmd_cost", "args_cost")


def cost_defs(source):
    """The public names a module defines at its top level that belong to the cost report."""
    return {n for n in kit_names(source) if n in COST_MOVED}


def test_bl_split_cost_bl_cost_holds_the_report_and_backlog_defines_none_of_it():
    assert set(COST_MOVED) <= cost_defs(tool_source("bl_cost.py"))
    assert cost_defs(tool_source("backlog.py")) == set(), "backlog.py imports the cost report, it does not define it"


def test_bl_split_cost_bl_cost_never_imports_backlog_at_any_depth_and_registers_cost_through_bl_cli():
    import bl_cli
    import bl_cost
    src = tool_source("bl_cost.py")
    tree = ast.parse(src)
    assert not imported_from(src, "backlog")
    assert not any(isinstance(n, ast.Import) and any(a.name == "backlog" for a in n.names) for n in ast.walk(tree))
    assert bl_cli.COMMANDS["cost"][0] is bl_cost.cmd_cost and bl_cli.COMMANDS["cost"][1] is bl_cost.args_cost
    assert not any(isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "add_parser" for n in ast.walk(tree)), \
        "the parser is added through bl_cli"
    registers = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "register"
                 and n.args and isinstance(n.args[0], ast.Constant) and n.args[0].value == "cost"]
    assert len(registers) == 1


def test_bl_split_cost_cost_tests_are_in_test_bl_cost_and_none_are_left_in_test_backlog():
    def cost_tests(src):
        return {n.name for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_backlog_cost_")}
    assert len(cost_tests(backlog_test_sources()["test_bl_cost.py"])) >= 40
    assert cost_tests(backlog_test_sources()["test_backlog.py"]) == set()
    assert "backlog.cost_" not in backlog_test_sources()["test_backlog.py"]


def test_bl_split_cost_planted_failures_fail():
    # a moved name put back in backlog.py, a bl_cost that imports backlog (at any depth), a cost test left behind
    assert cost_defs("def cost_report(bl, iid):\n    return 1\n") == {"cost_report"}
    assert cost_defs("from bl_cost import cost_report\n") == set()
    for body in ("import backlog\n", "from backlog import say\n", "def late():\n    from backlog import say\n"):
        assert unexcused({"backlog": "", "bl_cost": body}) == [("facade", "bl_cost", "backlog", "backlog")], body
    assert any(isinstance(n, ast.FunctionDef) and n.name.startswith("test_backlog_cost_")
               for n in ast.parse("def test_backlog_cost_left_behind():\n    pass\n").body)


CHECK_MOVED = ("validate", "KnowledgeState", "KbAtHead", "knowledge_check", "knowledge_lines", "stale_knowledge",
               "selector_of", "collected", "selector_rows", "noop_output", "trivial_command", "text_only_repro",
               "repro_text_warnings", "state_path_warnings", "gate_do_warnings", "is_test_run", "noop_warnings",
               "host_bound_accepted", "cmd_check", "cmd_selectors")


def check_defs(source):
    """The public names a module defines at its top level that belong to the checks."""
    return {n for n in kit_names(source) if n in CHECK_MOVED}


def test_bl_split_check_bl_check_holds_the_checks_and_backlog_defines_none_of_them():
    assert set(CHECK_MOVED) <= check_defs(tool_source("bl_check.py"))
    assert check_defs(tool_source("backlog.py")) == set(), "backlog.py imports the checks, it does not define them"


def test_bl_split_check_bl_check_never_imports_backlog_at_any_depth():
    src = tool_source("bl_check.py")
    tree = ast.parse(src)
    assert not imported_from(src, "backlog")
    assert not any(isinstance(n, ast.Import) and any(a.name == "backlog" for a in n.names) for n in ast.walk(tree))


def test_bl_split_check_check_and_selectors_are_registered_through_bl_cli_with_bl_check_handlers():
    import backlog
    import bl_check
    import bl_cli
    assert backlog.bl_cli is bl_cli
    names = list(bl_cli.COMMANDS)
    assert names.index("check") < names.index("fmt") < names.index("selectors"), "the usage order is unchanged"
    assert bl_cli.handler_of("check") is bl_check.cmd_check and bl_cli.handler_of("selectors") is bl_check.cmd_selectors
    tree = ast.parse(tool_source("bl_check.py"))
    assert not any(isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "add_parser" for n in ast.walk(tree)), \
        "a parser is added through bl_cli"
    assert not hasattr(bl_check, "DOCS") and not hasattr(bl_check, "bind_docs"), "check reads the rules from bl_plan"


def test_bl_split_check_check_tests_are_in_test_bl_check_and_none_are_left_in_test_backlog():
    def check_tests(src):
        return {n.name for n in ast.parse(src).body if isinstance(n, ast.FunctionDef)
                and n.name.startswith(("test_knowledge_", "test_item_holds_host_names", "test_backlog_selectors_"))}
    sources = backlog_test_sources()
    assert len(check_tests(sources["test_bl_check.py"])) >= 25
    assert check_tests(sources["test_backlog.py"]) == set()
    for needle in ("backlog.validate", "backlog.KnowledgeState", "backlog.selector_of", "backlog.noop_output"):
        assert needle not in sources["test_bl_check.py"], needle


def test_bl_split_check_planted_failures_fail():
    # a moved name put back in backlog.py, a bl_check that imports backlog (at any depth), a check test left behind,
    # a builder copied into test_bl_check.py
    assert check_defs("def validate(bl):\n    return []\n") == {"validate"}
    assert check_defs("from bl_check import validate\n") == set()
    for body in ("import backlog\n", "from backlog import say\n", "def late():\n    from backlog import say\n"):
        assert unexcused({"backlog": "", "bl_check": body}) == [("facade", "bl_check", "backlog", "backlog")], body
    assert any(isinstance(n, ast.FunctionDef) and n.name.startswith("test_knowledge_")
               for n in ast.parse("def test_knowledge_left_behind():\n    pass\n").body)
    kit = (Path(TOOLS) / "bl_testkit.py").read_text(encoding="utf-8")
    assert own_copies(kit, {"test_bl_check.py": "def b(root, *a):\n    return 1\n"}) == [("test_bl_check.py", "b")]


PLAN_MOVED = ("touch_paths", "dependencies", "dependents", "docs_after_code", "docs_warnings", "stale_touches",
              "outside_deps", "where_outside", "host_gates", "has_scope", "start_approved", "recurring_left_out",
              "tracked_files", "is_code", "cmd_start", "args_start")


def plan_defs(source):
    """The public names a module defines at its top level that belong to the plan and start helpers."""
    return {n for n in kit_names(source) if n in PLAN_MOVED}


def bl_graph(sources):
    """{bl_ module: the bl_ modules it imports, at any depth} for `sources` ({module name: source text})."""
    graph = {}
    for mod, text in sources.items():
        if not mod.startswith("bl_") or mod == "bl_testkit":
            continue
        seen = set()
        for n in ast.walk(ast.parse(text)):
            if isinstance(n, ast.Import):
                seen |= {a.name for a in n.names}
            elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
                seen.add(n.module)
        graph[mod] = {m for m in seen if m.startswith("bl_") and m != mod}
    return graph


def import_cycle(graph):
    """One import cycle of GRAPH as a list of modules (the first repeated at the end), or None."""
    def walk(node, path):
        if node in path:
            return path[path.index(node):] + [node]
        for nxt in sorted(graph.get(node, ())):
            found = walk(nxt, path + [node])
            if found:
                return found
        return None
    for start in sorted(graph):
        found = walk(start, [])
        if found:
            return found
    return None


def test_bl_split_plan_bl_plan_holds_the_plan_helpers_and_backlog_defines_none_of_them():
    assert set(PLAN_MOVED) <= plan_defs(tool_source("bl_plan.py"))
    assert plan_defs(tool_source("backlog.py")) == set(), "backlog.py imports the plan helpers, it does not define them"


def test_bl_split_plan_bl_plan_never_imports_backlog_at_any_depth():
    src = tool_source("bl_plan.py")
    tree = ast.parse(src)
    assert not imported_from(src, "backlog")
    assert not any(isinstance(n, ast.Import) and any(a.name == "backlog" for a in n.names) for n in ast.walk(tree))


LAZY_EDGES = {("bl_base", "bl_intake")}  # bl_base reaches bl_intake.run_argv by an import in the function (its docstring)


def test_bl_split_plan_no_import_cycle_between_the_bl_modules_and_check_reads_plan_not_the_reverse():
    graph = {m: {d for d in deps if (m, d) not in LAZY_EDGES} for m, deps in bl_graph(tool_sources()).items()}
    assert import_cycle(graph) is None, import_cycle(graph)
    assert "bl_plan" in graph["bl_check"] and "bl_check" not in graph["bl_plan"]
    assert "bind_docs" not in tool_source("bl_check.py") + tool_source("backlog.py")


def test_bl_split_plan_start_is_registered_through_bl_cli_with_the_bl_plan_handler():
    import backlog
    import bl_cli
    import bl_plan
    names = list(bl_cli.COMMANDS)
    assert names.index("drop") < names.index("start") < names.index("host-check"), "the usage order is unchanged"
    assert bl_cli.handler_of("start") is bl_plan.cmd_start and bl_cli.COMMANDS["start"][1] is bl_plan.args_start
    assert backlog.has_scope is bl_plan.has_scope and backlog.start_approved is bl_plan.start_approved
    tree = ast.parse(tool_source("bl_plan.py"))
    assert not any(isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "add_parser" for n in ast.walk(tree)), \
        "a parser is added through bl_cli"


PLAN_TEST_PREFIXES = ("test_start_", "test_backlog_docs_", "test_backlog_stale_touches_", "test_host_setup_gate_",
                      "test_check_warns_docs_in_later_task", "test_dependency_outside_sprint_",
                      "test_only_operator_answers_blocking_gates_and_starts_sprints")


def test_bl_split_plan_plan_tests_are_in_test_bl_plan_and_none_are_left_in_test_backlog():
    def plan_tests(src):
        return {n.name for n in ast.parse(src).body if isinstance(n, ast.FunctionDef)
                and n.name.startswith(PLAN_TEST_PREFIXES)}
    sources = backlog_test_sources()
    assert len(plan_tests(sources["test_bl_plan.py"])) >= 14
    assert plan_tests(sources["test_backlog.py"]) == set()
    for needle in ("backlog.touch_paths", "backlog.docs_after_code", "backlog.stale_touches", "backlog.cmd_start"):
        assert needle not in sources["test_bl_plan.py"], needle


def test_bl_split_plan_planted_failures_fail():
    # a moved name put back in backlog.py, a bl_plan that imports backlog or bl_check (at any depth), a cycle, a plan
    # test left behind
    assert plan_defs("def touch_paths(item, files, literal):\n    return set()\n") == {"touch_paths"}
    assert plan_defs("from bl_plan import touch_paths\n") == set()
    for body in ("import backlog\n", "from backlog import say\n", "def late():\n    from backlog import say\n"):
        assert unexcused({"backlog": "", "bl_plan": body}) == [("facade", "bl_plan", "backlog", "backlog")], body
    assert import_cycle(bl_graph({"bl_check": "import bl_plan\n", "bl_plan": "from bl_base import say\n",
                                  "bl_base": ""})) is None
    for body in ("import bl_check\n", "from bl_check import validate\n", "def late():\n    import bl_check\n"):
        assert import_cycle(bl_graph({"bl_check": "import bl_plan\n", "bl_plan": body})) == \
            ["bl_check", "bl_plan", "bl_check"], body
    assert import_cycle(bl_graph({"bl_a": "import bl_b\n", "bl_b": "import bl_c\n", "bl_c": "import bl_a\n"})) == \
        ["bl_a", "bl_b", "bl_c", "bl_a"]
    assert any(isinstance(n, ast.FunctionDef) and n.name.startswith(PLAN_TEST_PREFIXES)
               for n in ast.parse("def test_start_left_behind():\n    pass\n").body)


LAND_MOVED = ("item_commits", "unlanded_code", "blob_id", "out_of_scope", "colourless_env", "run_check", "noop_proof",
              "cmd_done", "land_stop", "land_run", "land_git", "has_ref", "checked_out_elsewhere", "live_processes",
              "release_worker_worktree", "mr_stuck", "stuck_merge_request", "cmd_land", "summary_key", "summary_line",
              "cmd_close", "args_done", "args_land", "args_close", "LAND_HEAVY", "LAND_SYNC", "WORKER_LOCK")
LAND_USAGE = ("done", "land", "close")  # registered in their usage positions, not together


def land_defs(source):
    """The public names a module defines at its top level that belong to done, land and close."""
    return {n for n in kit_names(source) if n in LAND_MOVED}


def test_bl_split_land_bl_land_holds_land_done_and_close_and_backlog_defines_none_of_them():
    assert set(LAND_MOVED) <= land_defs(tool_source("bl_land.py"))
    assert land_defs(tool_source("backlog.py")) == set(), "backlog.py imports them, it does not define them"
    assert {"waits", "open_gates", "line"} <= kit_names(tool_source("bl_base.py")), "the readiness rules sit below bl_land"


def test_bl_split_land_bl_land_never_imports_backlog_at_any_depth_and_no_bl_module_cycles():
    src = tool_source("bl_land.py")
    tree = ast.parse(src)
    assert not imported_from(src, "backlog")
    assert not any(isinstance(n, ast.Import) and any(a.name == "backlog" for a in n.names) for n in ast.walk(tree))
    graph = {m: {d for d in deps if (m, d) not in LAZY_EDGES} for m, deps in bl_graph(tool_sources()).items()}
    assert import_cycle(graph) is None, import_cycle(graph)
    # bl_ci, a command module beside it, takes the runner of a check from it; nothing below bl_land does
    assert "bl_land" in graph and not any("bl_land" in deps for m, deps in graph.items() if m != "bl_ci")


def test_bl_split_land_done_land_and_close_keep_their_usage_positions_with_bl_land_handlers():
    import backlog
    import bl_base
    import bl_cli
    import bl_land
    names = list(bl_cli.COMMANDS)
    assert names.index("gate") < names.index("fire") < names.index("done") < names.index("land") < names.index("drop")
    assert names.index("host-check") < names.index("close") < names.index("horizon"), "close keeps its own position"
    for n in LAND_USAGE:
        assert bl_cli.handler_of(n) is getattr(bl_land, "cmd_" + n)
        assert bl_cli.COMMANDS[n][1] is getattr(bl_land, "args_" + n)
    assert backlog.run_check is bl_land.run_check and backlog.waits is bl_base.waits


def test_bl_split_land_land_names_the_branch_through_kg_lane_and_never_sets_kbgit_kb():
    src = tool_source("bl_land.py")
    assert "kg_lane.lane_plan" in src and "kbgit.KB" not in src
    assert not imported_from(src, "kbgit")
    assert not any(isinstance(n, ast.Import) and any(a.name == "kbgit" for a in n.names)
                   for n in ast.walk(ast.parse(src)))


LAND_TEST_PREFIXES = ("test_done_", "test_close_", "test_backlog_close_", "test_check_interpreter_", "TestBacklogLand",
                      "TestDoneLane", "test_bl_split_land_does_not_swap_kb",
                      "test_review_needs_confirmed_provisional_answers_and_close_deletes")


def test_bl_split_land_land_done_and_close_tests_are_in_test_bl_land_and_none_are_left_in_test_backlog():
    def land_tests(src):
        return {n.name for n in ast.parse(src).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
                and n.name.startswith(LAND_TEST_PREFIXES)}
    sources = backlog_test_sources()
    assert len(land_tests(sources["test_bl_land.py"])) >= 20
    assert land_tests(sources["test_backlog.py"]) == set()
    for needle in ("backlog.live_processes", "backlog.stuck_merge_request", "backlog.release_worker_worktree"):
        assert needle not in sources["test_bl_land.py"], needle


def test_bl_split_land_planted_failures_fail():
    # a moved name put back in backlog.py, a bl_land that imports backlog (at any depth) or closes a cycle, a land
    # test left behind, a builder copied into test_bl_land.py
    assert land_defs("def cmd_land(bl, a):\n    return 0\n") == {"cmd_land"}
    assert land_defs("from bl_land import cmd_land\n") == set()
    for body in ("import backlog\n", "from backlog import say\n", "def late():\n    from backlog import say\n"):
        assert unexcused({"backlog": "", "bl_land": body}) == [("facade", "bl_land", "backlog", "backlog")], body
    for body in ("import bl_land\n", "from bl_land import run_check\n", "def late():\n    import bl_land\n"):
        assert import_cycle(bl_graph({"bl_land": "import bl_check\n", "bl_check": body})) == \
            ["bl_check", "bl_land", "bl_check"], body
    assert any(isinstance(n, ast.ClassDef) and n.name.startswith(LAND_TEST_PREFIXES)
               for n in ast.parse("class TestBacklogLand:\n    pass\n").body)
    kit = (Path(TOOLS) / "bl_testkit.py").read_text(encoding="utf-8")
    assert own_copies(kit, {"test_bl_land.py": "def finish_task(repo, tk):\n    return 1\n"}) == \
        [("test_bl_land.py", "finish_task")]


CI_MOVED = ("normalise_error_line", "first_failure", "bug_with_fingerprint", "add_pipeline", "latest_pipeline",
            "covered_by_revert", "red_bug", "cmd_red_pipeline", "cmd_intake", "hook_intake", "args_red_pipeline",
            "args_intake", "INTAKE_HOOK_BUDGET_S", "INTAKE_HOOK_SLOW", "STATUS_REPRO")
CI_TEST_PREFIXES = ("test_red_pipeline_", "test_job_state_table_red_pipeline_", "test_fingerprint_",
                    "test_gitlab_com_", "test_real_forge_log_")


def ci_defs(source):
    """The public names a module defines (or assigns) at its top level that belong to the CI readers and commands."""
    tree = ast.parse(source)
    names = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    names |= {t.id for n in tree.body if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
    return names & set(CI_MOVED)


def ci_tests(src):
    return {n.name for n in ast.parse(src).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
            and n.name.startswith(CI_TEST_PREFIXES)}


def test_bl_split_ci_bl_ci_holds_the_ci_readers_and_commands_and_backlog_defines_none_of_them():
    assert set(CI_MOVED) <= ci_defs(tool_source("bl_ci.py"))
    assert ci_defs(tool_source("backlog.py")) == set(), "backlog.py imports them, it does not define them"


def test_bl_split_ci_bl_ci_never_imports_backlog_and_closes_no_cycle():
    src = tool_source("bl_ci.py")
    assert not imported_from(src, "backlog")
    assert not any(isinstance(n, ast.Import) and any(a.name == "backlog" for a in n.names) for n in ast.walk(ast.parse(src)))
    graph = {m: {d for d in deps if (m, d) not in LAZY_EDGES} for m, deps in bl_graph(tool_sources()).items()}
    assert import_cycle(graph) is None, import_cycle(graph)
    assert not any("bl_ci" in deps for deps in graph.values()), "only backlog.py imports bl_ci"


def test_bl_split_ci_red_pipeline_and_intake_keep_their_usage_positions_with_bl_ci_handlers():
    import backlog
    import bl_ci
    import bl_cli
    names = list(bl_cli.COMMANDS)
    assert names.index("red-pipeline") + 1 == names.index("intake")
    for n in ("red-pipeline", "intake"):
        assert bl_cli.handler_of(n) is getattr(bl_ci, "cmd_" + n.replace("-", "_"))
        assert bl_cli.COMMANDS[n][1] is getattr(bl_ci, "args_" + n.replace("-", "_"))
    assert backlog.first_failure is bl_ci.first_failure and backlog.red_bug is bl_ci.red_bug  # ql_deliver's names


def test_bl_split_ci_its_tests_are_in_test_bl_ci_and_none_are_left_in_test_backlog():
    sources = backlog_test_sources()
    assert len(ci_tests(sources["test_bl_ci.py"])) >= 20
    assert ci_tests(sources["test_backlog.py"]) == set()
    for needle in ('setattr(backlog, "run"', 'setattr(backlog, "run_check"', "backlog.first_failure"):
        assert needle not in sources["test_bl_ci.py"], needle


def test_bl_split_ci_planted_failures_fail():
    # a moved name put back in backlog.py, a bl_ci that imports backlog, a CI test left behind
    assert ci_defs("def cmd_red_pipeline(bl, a):\n    return 0\n") == {"cmd_red_pipeline"}
    assert ci_defs("STATUS_REPRO = []\n") == {"STATUS_REPRO"}
    assert ci_defs("from bl_ci import cmd_red_pipeline\n") == set()
    for body in ("import backlog\n", "from backlog import say\n", "def late():\n    from backlog import say\n"):
        assert unexcused({"backlog": "", "bl_ci": body}) == [("facade", "bl_ci", "backlog", "backlog")], body
    assert ci_tests("def test_red_pipeline_left_behind():\n    pass\n") == {"test_red_pipeline_left_behind"}


VIEW_MOVED = ("ready", "words", "similar", "is_near", "items_at", "held_line", "clip", "hook_json", "horizon",
              "cmd_horizon", "cmd_next", "cmd_list", "cmd_find", "cmd_tree", "cmd_show", "cmd_held", "cmd_similar",
              "HOOK_MAX", "HOOK_TITLE", "HOOK_CAUSE")
VIEW_USAGE = ("similar", "list", "tree", "find", "show", "next", "held", "horizon")
VIEW_TEST_PREFIXES = ("test_horizon_", "test_backlog_held_paths_", "test_backlog_similar_", "test_next_",
                      "test_backlog_find_", "test_task_inherits_its_storys_undone_depends_on")


def view_defs(source):
    """The public names a module defines (or assigns) at its top level that belong to the read-only views."""
    tree = ast.parse(source)
    names = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    names |= {t.id for n in tree.body if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
    return names & set(VIEW_MOVED)


def view_tests(src):
    return {n.name for n in ast.parse(src).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
            and n.name.startswith(VIEW_TEST_PREFIXES)}


def test_bl_split_view_bl_view_holds_the_views_and_backlog_defines_none_of_them():
    assert set(VIEW_MOVED) <= view_defs(tool_source("bl_view.py"))
    assert view_defs(tool_source("backlog.py")) == set(), "backlog.py imports them, it does not define them"


def test_bl_split_view_bl_view_never_imports_backlog_and_closes_no_cycle():
    src = tool_source("bl_view.py")
    assert not imported_from(src, "backlog")
    assert not any(isinstance(n, ast.Import) and any(a.name == "backlog" for a in n.names) for n in ast.walk(ast.parse(src)))
    graph = {m: {d for d in deps if (m, d) not in LAZY_EDGES} for m, deps in bl_graph(tool_sources()).items()}
    assert import_cycle(graph) is None, import_cycle(graph)
    assert not any("bl_view" in deps for deps in graph.values()), "only backlog.py imports bl_view"


def test_bl_split_view_the_views_keep_their_usage_positions_with_bl_view_handlers():
    import backlog
    import bl_cli
    import bl_view
    names = list(bl_cli.COMMANDS)
    assert names.index("new") < names.index("similar") < names.index("check") < names.index("list") \
        < names.index("tree") < names.index("find") < names.index("show") < names.index("next") < names.index("held") \
        < names.index("claim") and names.index("close") < names.index("horizon") < names.index("goal")
    for n in VIEW_USAGE:
        assert bl_cli.handler_of(n) is getattr(bl_view, "cmd_" + n)
        assert bl_cli.COMMANDS[n][1] is getattr(bl_view, "args_" + n)
    assert backlog.similar is bl_view.similar and backlog.cmd_horizon is bl_view.cmd_horizon  # new's and main's


def test_bl_split_view_its_tests_are_in_test_bl_view_and_none_are_left_in_test_backlog():
    sources = backlog_test_sources()
    assert len(view_tests(sources["test_bl_view.py"])) >= 15
    assert view_tests(sources["test_backlog.py"]) == set()
    for needle in ("backlog.ready", "backlog.horizon", 'setattr(backlog, "touches_overlap"'):
        assert needle not in sources["test_bl_view.py"], needle


def test_bl_split_view_planted_failures_fail():
    # a moved name put back in backlog.py, a bl_view that imports backlog, a view test left behind
    assert view_defs("def cmd_held(bl, a):\n    return 0\n") == {"cmd_held"}
    assert view_defs("HOOK_MAX = 1\n") == {"HOOK_MAX"}
    assert view_defs("from bl_view import cmd_held\n") == set()
    for body in ("import backlog\n", "from backlog import say\n", "def late():\n    from backlog import say\n"):
        assert unexcused({"backlog": "", "bl_view": body}) == [("facade", "bl_view", "backlog", "backlog")], body
    assert view_tests("def test_horizon_left_behind():\n    pass\n") == {"test_horizon_left_behind"}


FACADE_KEEP = ("parse_cmd", "cmd_new", "cmd_fmt", "cmd_claim", "cmd_release", "run_decide", "record_decision",
               "DECISIONS_REL", "commit_answer", "cmd_answer", "changed_item", "changed_items", "SET_LISTS",
               "SET_FIELDS", "SET_REFUSED", "set_refusal", "appended", "reclass_gate", "cmd_set", "cmd_move",
               "cmd_reopen", "GATE_ID_RE", "CAPPED_FILE_RE", "SIZE_WORD_RE", "MEASURED_SIZE_RE", "cmd_gate",
               "cmd_host_check", "cmd_fire", "cmd_drop", "referrer_patterns", "referrers_of", "cmd_referrers",
               "cmd_goal", "main")  # the item writers kept whole (kb/_self/backlog.md) and the dispatch
FACADE_COMMANDS = ("new", "fmt", "claim", "release", "answer", "set", "move", "reopen", "gate", "host-check", "fire",
                   "drop", "referrers", "goal")  # the commands of the kept block the verdict names


def facade_defs(source):
    """The names backlog.py defines or assigns at its top level, argument builders (args_*) left out: they go with
    the command they build."""
    tree = ast.parse(source)
    names = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    names |= {t.id for n in tree.body if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
    return {n for n in names if not n.startswith("args_")}


def facade_problems(backlog_src, module_srcs, runbook):
    """What breaks backlog.py's facade rule: a name outside the kept block, a name a bl_ module also defines, a kept
    command the runbook's keep-whole verdict does not name."""
    defs = facade_defs(backlog_src)
    out = [f"defines {n}" for n in sorted(defs - set(FACADE_KEEP))]
    for mod, src in sorted(module_srcs.items()):
        out += [f"{n} also in {mod}" for n in sorted(defs & facade_defs(src))]
    verdict = next((p for p in runbook.split("\n\n") if p.startswith("`backlog.py` is the facade")), "")
    out += [f"verdict lacks {c}" for c in FACADE_COMMANDS if f"`{c}`" not in verdict]
    return out


def test_bl_split_facade_only_backlog_defines_its_dispatch_and_the_kept_item_writers_only():
    modules = {p.stem: p.read_text(encoding="utf-8") for p in Path(TOOLS).glob("bl_*.py") if p.stem != "bl_testkit"}
    runbook = (Path(TOOLS).parent / "kb" / "_self" / "backlog.md").read_text(encoding="utf-8")
    assert facade_problems(tool_source("backlog.py"), modules, runbook) == []


def test_bl_split_facade_only_planted_failures_fail():
    runbook = (Path(TOOLS).parent / "kb" / "_self" / "backlog.md").read_text(encoding="utf-8")
    src = tool_source("backlog.py")
    assert facade_problems(src + "\ndef horizon(bl, sid):\n    return 0\n", {}, runbook) == ["defines horizon"]
    assert facade_problems(src, {"bl_x": "def cmd_gate(bl, a):\n    return 0\n"}, runbook) == ["cmd_gate also in bl_x"]
    assert facade_problems(src, {}, runbook.replace("`referrers`", "referrers")) == ["verdict lacks referrers"]
