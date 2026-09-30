#!/usr/bin/env python3
"""Which tests a change can break: a map from changed paths to test files, computed from the code (stdlib only).

  testmap.py select [--since REV] [--paths P ...]   the pytest selection for the changed paths: `all`, `none`, or one
                                                    node per line (`_tools/test_x.py` or `_tools/test_x.py::Class`);
                                                    --since REV: the paths changed from REV's merge base to HEAD plus
                                                    the working tree (untracked included); --paths: those paths
  testmap.py explain [--since REV] [--paths P ...]  the same, with the reason for each path
  testmap.py deps [TEST_FILE ...]                   the tool modules each test file reaches
  testmap.py orphans                                tool modules no test file reaches; exit 1 when any

How a path maps (first rule that applies):
- `_tools/conftest.py`, `_tools/tests.py`, `_tools/testmap.py`, `pyproject.toml`, `uv.lock`, `.python-version`: all tests.
- `_tools/test_*.py`: that file; `_tools/stress_test.py`: test_stress.py (RUNNERS).
- `_tools/<module>.py`: every test file that reaches the module. A file reaches a module when it imports it or names its
  script (a string `<module>.py`, as `tool("check.py")` or `[sys.executable, ".../kbgit.py"]` do), directly or through
  the modules it reaches the same way.
- `kb/_self/backlog/**`, `kb/_querylog/**`: no tests of their own (kbgit.py's gate runs `backlog.py check` and
  `querylog.py check`).
- kb content (`kb/**`, `AGENTS.md`, `README.md`, `CLAUDE.md`): the tests that read the live kb (CONTENT_TESTS).
- a deleted test file or runner: nothing.
Every selection short of all adds the repository-wide leak scan (LEAKS), and a tool module's adds the tests that read
every tool module by glob, not by import, so no edge of the graph reaches them (TOOL_SCANS: ruff, the import layers).
- other paths under `_tools/`, `.claude/`, `.githooks/`, `.claude-plugin/`, `.github/`, `.gitlab-ci.yml`: the test files
  and modules whose string constants name the path, its file name or its directory (SEARCH_TOKENS), and for
  `.claude/` and `.githooks/` also the content classes; all tests when nothing names it.
- any other path: all tests.
A path no rule can place never selects fewer tests than before: an unknown path selects all of them.
Exit 0 (select, explain, deps), 1 orphans found, 2 bad arguments or git failed.
"""
import argparse, ast, functools, os, subprocess, sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
KB = os.path.dirname(TOOLS)
ALL, NONE = "all", "none"
RUNNERS = {"_tools/stress_test.py": {"_tools/test_stress.py"}}  # a suite's runner script: its suite
EVERYTHING = {"_tools/conftest.py", "_tools/tests.py", "_tools/testmap.py", "pyproject.toml", "uv.lock", ".python-version"}
NO_TESTS = ("kb/_self/backlog/", "kb/_querylog/")
CONTENT = ("kb/", "AGENTS.md", "README.md", "CLAUDE.md")
# the tests that read the live kb: test_kb.py's content classes (TestToolChecks runs check.py and the contract lint on
# it), the route eval set, the kb MCP server's answers and the kb's own signals.csv
CONTENT_TESTS = ["_tools/test_kb.py::TestCohesion", "_tools/test_kb.py::TestSelfDocs", "_tools/test_kb.py::TestLookup",
                 "_tools/test_kb.py::TestIds", "_tools/test_kb.py::TestLeaks", "_tools/test_kb.py::TestToolChecks",
                 "_tools/test_route.py::TestRouteEvalSet", "_tools/test_kb_mcp.py::TestKbServer", "_tools/test_kbfacts_imports.py"]
LEAKS = "_tools/test_kb.py::TestLeaks"  # the repository-wide leak scan: part of every selection short of all
# the tests that read every _tools/*.py by glob, not by import: part of every tool change's selection; ruff over every
# tool, and the import layers of kb/_self/code.md parsed over every module
TOOL_SCANS = ["_tools/test_kb.py::TestCohesion", "_tools/test_layout.py"]
SEARCHED = ("_tools/", ".claude/", ".githooks/", ".claude-plugin/", ".github/", ".gitlab-ci.yml")
WITH_CONTENT = (".claude/", ".githooks/")
# names too common to say which file a string means; a path under a directory also searches these directory tokens
GENERIC = {"SKILL.md", "README.md", "__init__.py", "plugin.json", ".mcp.json", "fixtures", "_tools", ".claude"}
SEARCH_TOKENS = {".claude/skills/": ["skills"], ".claude/hooks/": ["hooks"], ".claude/agents/": ["agents"],
                 ".githooks/": [".githooks", "githooks"], ".claude-plugin/": [".claude-plugin"], ".github/": [".github"]}


def modules():
    """The tool modules: _tools/*.py but the test files, conftest.py and this map."""
    return sorted(f[:-3] for f in os.listdir(TOOLS) if f.endswith(".py") and not f.startswith("test_")
                  and f not in ("conftest.py",))


def test_files():
    return sorted(f for f in os.listdir(TOOLS) if f.startswith("test_") and f.endswith(".py"))


@functools.lru_cache(maxsize=None)
def strings_and_imports(path):
    """(the string constants, the imported module names) of a Python file; ([], []) when it does not parse."""
    try:
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except (OSError, SyntaxError, ValueError):
        return (), ()
    strs, imps, skip = [], [], set()
    for n in ast.walk(tree):  # docstrings and f-string parts are prose (messages, docs), not a file a program opens
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.body \
                and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant):
            skip.add(id(n.body[0].value))
        elif isinstance(n, ast.JoinedStr):
            skip.update(id(v) for v in n.values)
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in skip:
            strs.append(n.value)
        elif isinstance(n, ast.Import):
            imps += [a.name.split(".")[0] for a in n.names]
        elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
            imps.append(n.module.split(".")[0])
    return tuple(strs), tuple(imps)


def direct_refs(path, mods):
    """The tool modules a file imports or names as a script."""
    strs, imps = strings_and_imports(path)
    got = {m for m in imps if m in mods}
    names = {m + ".py": m for m in mods}
    for s in strs:
        s = s.replace("\\", "/")
        if " " not in s and s.rsplit("/", 1)[-1] in names:  # a file name or a path, as argv or os.path.join take it
            got.add(names[s.rsplit("/", 1)[-1]])
    return got


@functools.lru_cache(maxsize=None)
def graph():
    """{test file: every tool module it reaches}, and {module: its direct refs}."""
    mods = set(modules())
    edges = {m: direct_refs(os.path.join(TOOLS, m + ".py"), mods) - {m} for m in mods}

    def closure(start):
        seen, todo = set(), list(start)
        while todo:
            m = todo.pop()
            if m not in seen:
                seen.add(m)
                todo += edges.get(m, ())
        return seen

    return {t: closure(direct_refs(os.path.join(TOOLS, t), mods)) for t in test_files()}, edges


def mentions(path):
    """Test files and modules whose string constants name `path`, its file name or its directory tokens."""
    rel = path.replace("\\", "/")
    base = rel.rsplit("/", 1)[-1]
    tokens = {rel} | ({base} if base not in GENERIC else set())
    for pre, toks in SEARCH_TOKENS.items():
        if rel.startswith(pre):
            tokens.update(toks)
            sub = rel[len(pre):].split("/", 1)[0]
            if "/" in rel[len(pre):] and sub not in GENERIC:
                tokens.add(sub)  # a skill's or a fixture's directory name
    if rel.startswith("_tools/fixtures/"):
        sub = rel[len("_tools/fixtures/"):].split("/", 1)[0]
        tokens.add(sub)
    tests, mods = set(), set()
    for f in test_files() + [m + ".py" for m in modules()]:
        strs, _ = strings_and_imports(os.path.join(TOOLS, f))
        if any(t in s.replace("\\", "/") for s in strs for t in tokens):
            (tests if f.startswith("test_") else mods).add(f)
    return tests, {m[:-3] for m in mods}


def place(path):
    """(the selection for one path: ALL, NONE or a set of nodes, the reason)."""
    rel = path.replace("\\", "/").lstrip("./") if not path.startswith(".") else path.replace("\\", "/")
    reach, _ = graph()
    if rel in EVERYTHING:
        return ALL, "shared test setup: every test"
    if rel.startswith("_tools/test_") and rel.endswith(".py") and "/" not in rel[len("_tools/"):]:
        if not os.path.exists(os.path.join(KB, *rel.split("/"))):
            return NONE, "a deleted test file: nothing left to run"
        return {rel}, "a test file: itself"
    if rel in RUNNERS:
        if not os.path.exists(os.path.join(KB, *rel.split("/"))):
            return NONE, "a deleted runner: nothing left to run"
        return set(RUNNERS[rel]), "a suite's runner: its suite"
    if rel.startswith("_tools/") and rel.endswith(".py") and "/" not in rel[len("_tools/"):]:
        m = rel[len("_tools/"):-3]
        hits = {f"_tools/{t}" for t, ms in reach.items() if m in ms}
        return (hits | set(TOOL_SCANS), f"test files that reach {m}") if hits else (ALL, f"no test file reaches {m}: every test")
    if rel.startswith(NO_TESTS):
        return NONE, "backlog items and the query log store: the gate's own check"
    if rel.startswith(SEARCHED) or rel == ".gitlab-ci.yml":
        tests, mods = mentions(rel)
        tests = {f"_tools/{t}" for t in tests} | {f"_tools/{t}" for t, ms in reach.items() if ms & mods}
        if rel.startswith(WITH_CONTENT):
            tests |= set(CONTENT_TESTS)
        return (tests, "test files and tools that name it") if tests else (ALL, "nothing names it: every test")
    if rel.startswith(CONTENT):
        return set(CONTENT_TESTS), "kb content: the content checks"
    return ALL, "no rule places it: every test"


def select(paths):
    """(ALL, NONE or a sorted node list, [(path, reason)]). A whole file absorbs its classes."""
    nodes, why = set(), []
    for p in paths:
        got, reason = place(p)
        why.append((p, reason))
        if got == ALL:
            return ALL, why
        if got != NONE:
            nodes |= got
    if paths:
        nodes.add(LEAKS)  # a secret or a private path can sit in any file
    files = {n for n in nodes if "::" not in n}
    nodes = {n for n in nodes if "::" not in n or n.split("::")[0] not in files}
    return (sorted(nodes) if nodes else NONE), why


def changed(since):
    """Paths changed from the merge base of `since` and HEAD to the working tree, untracked files included."""
    def git(*args):
        p = subprocess.run(["git", *args], cwd=KB, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if p.returncode:
            raise SystemExit(f"testmap.py: git {' '.join(args)} failed: {p.stderr.strip()}")
        return p.stdout
    base = git("merge-base", since, "HEAD").strip()
    names = git("diff", "--name-only", base).splitlines() + git("ls-files", "--others", "--exclude-standard").splitlines()
    return sorted({n.strip() for n in names if n.strip()})


def orphans():
    reach, _ = graph()
    used = set().union(*reach.values()) if reach else set()
    runners = {r[len("_tools/"):-3] for r in RUNNERS} | {e[len("_tools/"):-3] for e in EVERYTHING if e.startswith("_tools/")}
    return [m for m in modules() if m not in used and m not in runners]


def main(argv):
    ap = argparse.ArgumentParser(prog="testmap.py", description=__doc__.split("\n", 1)[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("select", "explain"):
        s = sub.add_parser(name)
        s.add_argument("--since")
        s.add_argument("--paths", nargs="+")
    d = sub.add_parser("deps")
    d.add_argument("files", nargs="*")
    sub.add_parser("orphans")
    a = ap.parse_args(argv)
    if a.cmd in ("select", "explain"):
        if bool(a.since) == bool(a.paths):
            ap.error("give --since REV or --paths P ...")
        paths = a.paths or changed(a.since)
        got, why = select(paths)
        if a.cmd == "explain":
            for p, reason in why:
                print(f"{p}: {reason}")
        print("\n".join(got) if isinstance(got, list) else got)
        return 0
    if a.cmd == "deps":
        reach, _ = graph()
        for t in (a.files or sorted(reach)):
            t = os.path.basename(t)
            print(f"_tools/{t}: {', '.join(sorted(reach.get(t, ()))) or '-'}")
        return 0
    lost = orphans()
    for m in lost:
        print(f"_tools/{m}.py: no test file reaches it")
    print(f"orphans={len(lost)}")
    return 1 if lost else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
