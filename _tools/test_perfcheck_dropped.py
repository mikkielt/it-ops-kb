"""perfcheck.py dropped (ST-kd7vnu5r; kb/_self/tools.md): a dropped test id must name the removed code it tested.

A throwaway git repository with _tools/ modules and test files, some deleted in a commit, and a dropped-ids file:
the command warns of ids of a test file that still exists whose reason names no removed file or symbol and no
successor test, and of a deleted test file whose local imports are all still present; it is silent for the rest.
"""
import subprocess

import pytest

import perfcheck


def sh(cwd, *argv):
    p = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@corp.example.com", *argv], cwd=cwd,
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stderr


@pytest.fixture
def clone(tmp_path):
    tools = tmp_path / "_tools"
    tools.mkdir()
    files = {"mod_live.py": "def live_fn():\n    return 1\n", "mod_gone.py": "def gone_fn():\n    return 2\n",
             "test_live_only.py": "import conftest\nimport mod_live\n\ndef test_a():\n    assert mod_live.live_fn()\n",
             "test_gone_mod.py": "import mod_gone\n\ndef test_b():\n    assert mod_gone.gone_fn()\n",
             "test_stays.py": "def test_new_name():\n    pass\n"}
    for name, text in files.items():
        (tools / name).write_text(text, encoding="utf-8")
    sh(tmp_path, "init", "-q")
    sh(tmp_path, "add", "-A")
    sh(tmp_path, "commit", "-qm", "base")
    for name in ("mod_gone.py", "test_live_only.py", "test_gone_mod.py"):
        (tools / name).unlink()
    sh(tmp_path, "add", "-A")
    sh(tmp_path, "commit", "-qm", "remove")
    return tmp_path


DROPPED = """_tools/test_live_only.py::test_a
# gone_fn went with mod_gone.py
_tools/test_gone_mod.py::test_b
# the old `gone_fn` path is removed
_tools/test_stays.py::test_old_a
# became test_new_name in the same file
_tools/test_stays.py::test_old_b
# tidied up
_tools/test_stays.py::test_old_c
"""


def test_dropped_ids_name_removed_code(clone, capsys):
    """Planted: test_old_c's reason names nothing removed and no successor; test_live_only.py is gone while mod_live,
    the module it tested, stays. The other ids name a removed symbol, a removed file or a successor test."""
    f = clone / "dropped.txt"
    f.write_text(DROPPED, encoding="utf-8")
    assert perfcheck.main(["dropped", "--file", str(f)], root=clone) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[-1] == "perfcheck dropped: 2 warning(s)", out
    assert any("1 id(s) of _tools/test_stays.py" in ln and "tidied up" in ln for ln in out), out
    assert any("_tools/test_live_only.py (1 id(s)) is gone, but every module it tested is still present: mod_live"
               in ln for ln in out), out
    assert not any("test_gone_mod" in ln or "gone_fn" in ln or "test_new_name" in ln for ln in out), out


def test_dropped_ids_name_removed_code_a_clean_file_warns_nothing(clone, capsys):
    f = clone / "dropped.txt"
    f.write_text("# the old `gone_fn` path is removed\n_tools/test_stays.py::test_old_a\n", encoding="utf-8")
    assert perfcheck.main(["dropped", "--file", str(f)], root=clone) == 0
    assert capsys.readouterr().out.splitlines() == ["perfcheck dropped: 0 warning(s)"]
    assert perfcheck.main(["dropped", "--file", str(clone / "missing.txt")], root=clone) == 2
