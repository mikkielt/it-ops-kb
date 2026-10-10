"""backlog.py's project settings (kb/_self/backlog.md, Project settings): `config` prints the effective settings with
each value's source, the kb's committed backlog.json holds the kb's own values, and a file with an unknown key or a
wrong type is refused naming the key.

The settings files are throwaway directories under tmp_path; the one real file read is the repository's backlog.json."""
import argparse
import json

import pytest

import bl_base
from bl_base import Backlog, Rejected, cmd_config


def config(root, capsys):
    """(exit code, stdout) of the `config` command's handler on the repository at ROOT."""
    code = cmd_config(Backlog(root), argparse.Namespace(root=str(root)))
    return code, capsys.readouterr().out


def test_backlog_config_prints_each_setting_with_its_source(tmp_path, capsys):
    (tmp_path / "backlog.json").write_text(json.dumps({"item_dir": "work/items", "lane_module": "mylane"}),
                                           encoding="utf-8")
    code, out = config(tmp_path, capsys)
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
def test_backlog_config_refuses_an_unknown_key_and_a_wrong_type_naming_the_key(tmp_path, capsys, data, key):
    (tmp_path / "backlog.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(Rejected, match=key):
        config(tmp_path, capsys)
    assert any(key in e for e in Backlog(tmp_path).load_errors)
