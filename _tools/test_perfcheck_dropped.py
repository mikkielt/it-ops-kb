"""perfcheck.py dropped (ST-kd7vnu5r; kb/_self/tools.md): a dropped test id must name the removed code it tested.

A throwaway git repository with _tools/ modules and test files, some deleted in a commit, and a dropped-ids file:
the command warns of ids of a test file that still exists whose reason names no removed file or symbol and no
successor test, and of a deleted test file whose local imports are all still present; it is silent for the rest.
"""
import subprocess

import pytest
from pathlib import Path

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
    assert any("_tools/test_live_only.py (1 id(s)) is gone, but modules it tested are still present: mod_live"
               in ln for ln in out), out
    assert not any("test_gone_mod" in ln or "gone_fn" in ln or "test_new_name" in ln for ln in out), out


def test_dropped_ids_name_removed_code_a_clean_file_warns_nothing(clone, capsys):
    f = clone / "dropped.txt"
    f.write_text("# the old `gone_fn` path is removed\n_tools/test_stays.py::test_old_a\n", encoding="utf-8")
    assert perfcheck.main(["dropped", "--file", str(f)], root=clone) == 0
    assert capsys.readouterr().out.splitlines() == ["perfcheck dropped: 0 warning(s)"]
    assert perfcheck.main(["dropped", "--file", str(clone / "missing.txt")], root=clone) == 2


@pytest.fixture
def partial(tmp_path):
    """A clone where test_autoshape.py, which tested the removed mod_auto beside the live mod_live (the shape of
    test_autopilot_two_runners.py beside kg_lock), is deleted with mod_auto; test_stays.py holds test_new_name."""
    tools = tmp_path / "_tools"
    tools.mkdir()
    files = {"mod_live.py": "def live_fn():\n    return 1\n", "mod_auto.py": "def auto_fn():\n    return 2\n",
             "test_autoshape.py": "import mod_auto\nimport mod_live\n\ndef test_c():\n    assert mod_live.live_fn()\n",
             "test_stays.py": "def test_new_name():\n    pass\n"}
    for name, text in files.items():
        (tools / name).write_text(text, encoding="utf-8")
    sh(tmp_path, "init", "-q")
    sh(tmp_path, "add", "-A")
    sh(tmp_path, "commit", "-qm", "base")
    for name in ("mod_auto.py", "test_autoshape.py"):
        (tools / name).unlink()
    sh(tmp_path, "add", "-A")
    sh(tmp_path, "commit", "-qm", "remove")
    return tmp_path


@pytest.mark.parametrize("reason, warned", [
    ("test_autoshape.py went with mod_auto.py", True),  # names only the dropped test and the removed module
    ("`auto_fn` is removed", True),
    ("its mod_live tests came back as test_new_name", False),  # a successor test the code holds
    ("its mod_live tests moved to test_stays.py", False),  # a successor test file that exists
    ("its mod_live tests went to test_nowhere.py", True),  # a test file that does not exist
])
def test_dropped_ids_partial_removal_warned(partial, capsys, reason, warned):
    """ST-vxi7drn2 planted: a deleted test file that tested a removed module beside a live one is warned of, naming the
    live module, unless its reason names where those tests went; naming only itself or the removed code is no excuse."""
    f = partial / "dropped.txt"
    f.write_text(f"# {reason}\n_tools/test_autoshape.py::test_c\n", encoding="utf-8")
    assert perfcheck.main(["dropped", "--file", str(f)], root=partial) == 0
    out = capsys.readouterr().out
    hit = "_tools/test_autoshape.py (1 id(s)) is gone, but modules it tested are still present: mod_live" in out
    assert hit == warned, out
    assert "mod_auto" not in out.split("present:")[-1].split(";")[0], out


def test_dropped_ids_partial_removal_warned_since_reads_only_added_groups(partial, capsys):
    """With --since REV only the groups whose ids the range added are read: an old group is left alone, a new one is
    warned of."""
    f = partial / "_tools" / "test_ids_dropped.txt"
    f.write_text("# test_autoshape.py went with mod_auto.py\n_tools/test_autoshape.py::test_c\n", encoding="utf-8")
    sh(partial, "add", "-A")
    sh(partial, "commit", "-qm", "old drop")
    assert perfcheck.main(["dropped", "--since", "HEAD"], root=partial) == 0
    assert capsys.readouterr().out.splitlines() == ["perfcheck dropped: 0 warning(s)"]
    assert perfcheck.main(["dropped", "--since", "HEAD~1"], root=partial) == 0
    assert "mod_live" in capsys.readouterr().out


@pytest.mark.parametrize("reason, warned", [
    ("autopilot retired\n# live-module calls went with the removed mod_auto.py", False),
    ("autopilot retired\n# live-module calls went with the removed `auto_fn`", False),  # a removed symbol
    ("autopilot retired\n# live-module calls went with the runner", True),  # the phrase names nothing removed
    ("autopilot retired\n# live-module calls went with the removed mod_live.py", True),  # a module still present
    ("mod_auto.py is removed", True),  # a removed module without the phrase
])
def test_dropped_retired_feature_phrase(partial, capsys, reason, warned):
    """ST-l3ky22zo planted: a retired feature's gone test file is excused when its reason says the live module's calls
    went with the retired feature (perfcheck.RETIRED_PHRASE) and names the removed module, file or symbol; the phrase
    naming nothing removed, or a removed module without the phrase, is still warned of."""
    f = partial / "dropped.txt"
    f.write_text(f"# {reason}\n_tools/test_autoshape.py::test_c\n", encoding="utf-8")
    assert perfcheck.main(["dropped", "--file", str(f)], root=partial) == 0
    assert ("is gone, but modules it tested are still present: mod_live" in capsys.readouterr().out) == warned


def test_dropped_retired_feature_phrase_real_file_has_no_partial_removal_left():
    """The live dropped-ids file's retired-feature groups carry the phrase: a full dropped run over the repository
    names no gone test file whose live modules' tests went nowhere."""
    from conftest import KB
    text = (Path(KB) / perfcheck.DROPPED_FILE).read_text(encoding="utf-8")
    left = [w for w in perfcheck.dropped_warnings(KB, text) if "is gone, but modules" in w]
    assert left == [], left
