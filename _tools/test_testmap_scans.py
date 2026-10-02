"""testmap.py's selection of the tests that read the tool sources as text (TOOL_SCANS, `source_scans()`):
`python3 _tools/tests.py -k testmap_selects_source_scans`. No git: every repository here is a plain directory copy."""
import os
import shutil
import subprocess
import sys

import pytest

import testmap
from conftest import TOOLS, timeout_s

REMOTE_SCAN = "_tools/test_kbpublic.py::TestRemoteRoles"
PLANTED_TOOL = "zz_planted_tool"


@pytest.fixture(autouse=True)
def fresh_caches():
    for fn in (testmap.graph, testmap.source_scans, testmap.strings_and_imports):
        fn.cache_clear()
    yield
    for fn in (testmap.graph, testmap.source_scans, testmap.strings_and_imports):
        fn.cache_clear()


def throwaway_copy(tmp_path, monkeypatch):
    """A copy of _tools with a new tool file that names the remote literally, and the test file that imports it; testmap
    reads the copy."""
    root = tmp_path / "copy"
    shutil.copytree(TOOLS, root / "_tools", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (root / "kb").mkdir()  # test_kbpublic.py reads the directory at import
    (root / "_tools" / f"{PLANTED_TOOL}.py").write_text('REMOTE = "origin"\n', encoding="utf-8", newline="\n")
    (root / "_tools" / f"test_{PLANTED_TOOL}.py").write_text(f"import {PLANTED_TOOL}\n\n\ndef test_x():\n    assert {PLANTED_TOOL}.REMOTE\n",
                                                           encoding="utf-8", newline="\n")
    monkeypatch.setattr(testmap, "TOOLS", str(root / "_tools"))
    monkeypatch.setattr(testmap, "KB", str(root))
    return root


def test_testmap_selects_source_scans_for_a_new_tool_file(tmp_path, monkeypatch):
    """The defect: a new tool file naming the remote selected its own test and the leak scan, not the remote-role scan."""
    root = throwaway_copy(tmp_path, monkeypatch)
    sel, _ = testmap.select([f"_tools/{PLANTED_TOOL}.py"])
    assert sel != testmap.ALL and f"_tools/test_{PLANTED_TOOL}.py" in sel
    assert set(testmap.TOOL_SCANS) <= set(sel), sorted(set(testmap.TOOL_SCANS) - set(sel))
    assert REMOTE_SCAN in sel
    # planted failure: the selected scan fails on the planted file, and passes on the same copy without it
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-x", f"{root / REMOTE_SCAN}::test_no_tool_holds_the_string_origin"]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    bad = subprocess.run(cmd, cwd=root / "_tools", env=env, capture_output=True, text=True, encoding="utf-8", timeout=timeout_s(300))
    assert bad.returncode == 1 and PLANTED_TOOL in bad.stdout, bad.stdout + bad.stderr
    (root / "_tools" / f"{PLANTED_TOOL}.py").unlink()
    good = subprocess.run(cmd, cwd=root / "_tools", env=env, capture_output=True, text=True, encoding="utf-8", timeout=timeout_s(300))
    assert good.returncode == 0, good.stdout + good.stderr


def test_testmap_selects_source_scans_drops_without_the_declaration(tmp_path, monkeypatch):
    """Planted: with the remote-role scan out of TOOL_SCANS the same change no longer selects it."""
    throwaway_copy(tmp_path, monkeypatch)
    monkeypatch.setattr(testmap, "TOOL_SCANS", [n for n in testmap.TOOL_SCANS if n != REMOTE_SCAN])
    sel, _ = testmap.select([f"_tools/{PLANTED_TOOL}.py"])
    assert REMOTE_SCAN not in sel


def test_testmap_selects_source_scans_explain_names_the_reason():
    _, why = testmap.select(["_tools/kbgit.py"])
    assert "read every tool source as text" in why[0][1]


def test_testmap_selects_source_scans_every_reader_is_declared():
    """Every test that reads the tool sources as text is in the set: a new such test fails here until it is added."""
    found = testmap.source_scans()
    assert REMOTE_SCAN in found and "_tools/test_layout.py" in found and "_tools/test_ql_capture.py::TestNoHooks" in found
    assert testmap.scans_missing() == []


def test_testmap_selects_source_scans_a_new_reader_is_found_and_reported(tmp_path, monkeypatch):
    """Planted: a test file that globs the tool sources, in a class and as a function, is derived and reported missing;
    a test file that globs something else is not."""
    tools = tmp_path / "_tools"
    tools.mkdir()
    (tools / "test_zz_reader.py").write_text(
        "from pathlib import Path\n\n\nclass TestScan:\n    def test_a(self):\n        assert Path('.').glob('*.py')\n\n\n"
        "def test_b():\n    assert Path('.').glob('x_*.py')\n\n\ndef helper():\n    return Path('.').rglob('*.py')\n",
        encoding="utf-8", newline="\n")
    (tools / "test_zz_other.py").write_text("from pathlib import Path\n\n\ndef test_c():\n    assert Path('.').glob('*.json')\n",
                                            encoding="utf-8", newline="\n")
    monkeypatch.setattr(testmap, "TOOLS", str(tools))
    found = testmap.source_scans()
    assert found == {"_tools/test_zz_reader.py::TestScan", "_tools/test_zz_reader.py::test_b", "_tools/test_zz_reader.py"}
    assert testmap.scans_missing() == sorted(found)
    monkeypatch.setattr(testmap, "TOOL_SCANS", ["_tools/test_zz_reader.py"])  # a whole file declared covers its nodes
    assert testmap.scans_missing() == []
