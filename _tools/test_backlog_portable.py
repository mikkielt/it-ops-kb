"""backlog.py's project settings (kb/_self/backlog.md, Project settings): `config` prints the effective settings with
each value's source, the kb's committed backlog.json holds the kb's own values, and a file with an unknown key or a
wrong type is refused naming the key.

The settings files are throwaway directories under tmp_path; the one real file read is the repository's backlog.json."""
import json
import os
import subprocess
import sys

import pytest

import bl_base
from conftest import TOOLS


def config(root):
    """(exit code, stdout, stderr) of `backlog.py --root ROOT config`."""
    p = subprocess.run([sys.executable, os.path.join(TOOLS, "backlog.py"), "--root", str(root), "config"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert "Traceback" not in p.stderr, p.stderr
    return p.returncode, p.stdout, p.stderr


def test_backlog_config_prints_each_setting_with_its_source(tmp_path):
    (tmp_path / "backlog.json").write_text(json.dumps({"item_dir": "work/items", "lane_module": "mylane"}),
                                           encoding="utf-8")
    code, out, _ = config(tmp_path)
    assert code == 0
    lines = out.splitlines()
    assert lines[0].startswith("backlog.json: read")
    assert 'item_dir = "work/items"  (file)' in lines
    assert 'lane_module = "mylane"  (file)' in lines
    assert 'worktree_dir = ".claude/worktrees"  (default)' in lines
    assert [line.split(" = ")[0] for line in lines[1:]] == list(bl_base.SETTINGS)


def test_backlog_config_of_the_kb_is_its_committed_file_and_its_defaults():
    values, sources, path, problems = bl_base.read_settings(bl_base.ROOT, env={})
    assert path.name == "backlog.json" and problems == []
    assert set(sources.values()) == {"file"}
    assert values == {k: d for k, (_, d) in bl_base.SETTINGS.items()}


@pytest.mark.parametrize("data, key", [({"item_dri": "x"}, "item_dri"), ({"always_in_scope": "kb/**"}, "always_in_scope")])
def test_backlog_config_refuses_an_unknown_key_and_a_wrong_type_naming_the_key(tmp_path, data, key):
    (tmp_path / "backlog.json").write_text(json.dumps(data), encoding="utf-8")
    code, out, err = config(tmp_path)
    assert code == 2 and out == "" and key in err
