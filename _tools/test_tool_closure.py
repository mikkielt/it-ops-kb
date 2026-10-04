"""A test that runs a tool in a temporary repository copies the tool files from the tool's import closure
(`python3 _tools/tests.py -k tool_copy_follows_imports`): `bl_testkit.tool_closure` and `copy_tool_closure` follow every
import, a function-level or try-block one included, through the `_tools` modules, so a module that gains a lazy import
needs no edit to a list in a test file.

  planted   a tree whose modules import lazily, in a try block, transitively and in a cycle: all copied; a module
            nothing imports and a data file are not; the hand list the tests used to carry misses a lazy import
  real      the closure of backlog.py holds kbpublic.py (a lazy import of bl_check) and kbcommon.py, and equals what
            the standard library's ModuleFinder finds, which reads the bytecode and so shares no code with the walk
"""
import modulefinder, os, sys
from pathlib import Path

import pytest

from bl_testkit import TOOLS, copy_tool_closure, tool_closure


def plant(tmp_path, files):
    for name, text in files.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    return tmp_path


TREE = {
    "tool.py": "import json\nimport top_level\n\ndef run():\n    import lazy_one\n    from lazy_two import thing\n\n"
               "try:\n    import tried\nexcept ImportError:\n    tried = None\n",
    "top_level.py": "",
    "lazy_one.py": "from deep import x\n",  # transitive: the tool never names it
    "deep.py": "def f():\n    import tool\n",  # a cycle back to the tool
    "lazy_two.py": "import os.path\nimport dotted.name\n",
    "tried.py": "",
    "unused.py": "import top_level\n",  # imports a copied module, but nothing imports it
    "aliases.csv": "a,b\n",
    "json.py": "import never_copied\n",  # planted: a tool file named like a standard library module is followed as a tool
    "never_copied.py": "",
}


def test_tool_copy_follows_imports_lazy_try_and_transitive(tmp_path):
    """Planted: a function-level import, a `from` import in a function, a try-block import and a transitive one are all in
    the closure, once each though a cycle leads back; a module nothing imports is not."""
    plant(tmp_path, TREE)
    assert tool_closure("tool.py", tools=tmp_path) == [
        "deep.py", "json.py", "lazy_one.py", "lazy_two.py", "never_copied.py", "tool.py", "top_level.py", "tried.py"]
    assert "unused.py" not in tool_closure("tool.py", tools=tmp_path)


def test_tool_copy_follows_imports_copies_the_files_and_no_data_unless_named(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    plant(src, TREE)
    dest = tmp_path / "repo" / "_tools"
    names = copy_tool_closure(dest, "tool.py", tools=src)
    assert sorted(p.name for p in dest.iterdir()) == names == tool_closure("tool.py", tools=src)
    assert not (dest / "aliases.csv").exists() and not (dest / "unused.py").exists()  # a data file is not guessed
    assert (dest / "lazy_one.py").read_text(encoding="utf-8") == "from deep import x\n"
    both = copy_tool_closure(tmp_path / "other", "tool.py", data=("aliases.csv",), tools=src)
    assert both == [*tool_closure("tool.py", tools=src), "aliases.csv"]
    assert (tmp_path / "other" / "aliases.csv").read_text(encoding="utf-8") == "a,b\n"


def test_tool_copy_follows_imports_of_several_roots_and_a_missing_root(tmp_path):
    plant(tmp_path, TREE)
    assert tool_closure("top_level.py", "tried.py", tools=tmp_path) == ["top_level.py", "tried.py"]
    assert tool_closure("unused.py", tools=tmp_path) == ["top_level.py", "unused.py"]
    with pytest.raises(FileNotFoundError):  # planted: a root that is no file fails, not an empty copy
        tool_closure("absent.py", tools=tmp_path)


def old_hand_list(tools):
    """What test_backlog_research and test_bl_check carried: backlog.py, every bl_ module, a fixed list of the rest."""
    return ("backlog.py",) + tuple(sorted(f for f in os.listdir(tools) if f.startswith("bl_") and f.endswith(".py"))) + (
        "kbcommon.py", "kbfacts.py", "kbid.py", "ql_base.py", "aliases.csv")


def test_tool_copy_follows_imports_where_the_old_hand_list_missed_one(tmp_path):
    """Planted: a bl_ module gains a lazy `import kbpublic`, a file the fixed list does not name. The old list misses
    it (the first land gate of such a change failed twelve tests); the closure has it."""
    plant(tmp_path, {"backlog.py": "import bl_base\n", "bl_base.py": "", "kbcommon.py": "", "kbfacts.py": "",
                     "kbid.py": "", "ql_base.py": "", "aliases.csv": "x\n", "kbpublic.py": ""})
    assert "kbpublic.py" not in old_hand_list(tmp_path) and "kbpublic.py" not in tool_closure("backlog.py", tools=tmp_path)
    (tmp_path / "bl_base.py").write_text("def check():\n    import kbpublic\n    return kbpublic\n", encoding="utf-8")
    assert "kbpublic.py" not in old_hand_list(tmp_path)  # the list does not follow the new import
    assert "kbpublic.py" in tool_closure("backlog.py", tools=tmp_path)  # the closure does


def test_tool_copy_follows_imports_real_backlog_closure_holds_the_lazy_ones():
    closure = tool_closure("backlog.py")
    assert "kbpublic.py" in closure and "kbcommon.py" in closure and "bl_check.py" in closure
    assert "kbpublic.py" not in old_hand_list(TOOLS)  # still reached only through an import the list never named
    assert not any(n.startswith("test_") for n in closure) and "bl_testkit.py" not in closure


@pytest.mark.parametrize("root", ["backlog.py", "kbdecide.py", "kblog.py", "selfdoc.py", "check.py"])
def test_tool_copy_follows_imports_agrees_with_modulefinder(root):
    """The standard library's ModuleFinder reads the bytecode of the same files, so the two walks share no code: the
    closure is every _tools module it finds, and the script itself."""
    found = modulefinder.ModuleFinder(path=[TOOLS, *sys.path])
    found.run_script(str(Path(TOOLS) / root))
    theirs = {Path(m.__file__).name for m in found.modules.values()
              if getattr(m, "__file__", None) and Path(m.__file__).resolve().parent == Path(TOOLS).resolve()}
    assert set(tool_closure(root)) == theirs | {root}


def test_tool_copy_follows_imports_real_copy_imports_cleanly(tmp_path):
    """Planted by the copy itself: the copied backlog.py closure imports every module in it, in a directory that holds
    nothing else, so a missing file is an ImportError here instead of a failing test somewhere else."""
    import subprocess
    (tmp_path / "kb" / "public").mkdir(parents=True)  # the kb the modules look for at import
    names = copy_tool_closure(tmp_path / "_tools", "backlog.py")
    code = "import importlib, sys; [importlib.import_module(n[:-3]) for n in sys.argv[1:]]"
    p = subprocess.run([sys.executable, "-c", code, *names], cwd=tmp_path / "_tools", capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    assert p.returncode == 0, p.stderr[-2000:]
