"""backlog.py's project settings (kb/_self/backlog.md, Project settings): `config` prints the effective settings with
each value's source, the kb's committed backlog.json holds the kb's own values, and a file with an unknown key or a
wrong type is refused naming the key; `brief` prints the worker's brief and `dispatch --dry-run` its argv without
starting a session.

The settings files are throwaway directories under tmp_path; the one real file read is the repository's backlog.json."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

import bl_base
from conftest import TOOLS, Repo


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


TRACKERS = {"jira": {"pattern": "[A-Z][A-Z0-9]+-[0-9]+", "url": "https://jira.corp.example.com/browse/{id}"},
            "gitlab": {"pattern": "[0-9]+", "url": "https://gitlab.corp.example.com/group/proj/-/issues/{id}",
                       "ref": "#{id}"}}


def test_backlog_external_ids_are_validated_shown_found_and_carried_by_claim_commits(tmp_path):
    (tmp_path / "repo").mkdir()
    root = Repo(tmp_path / "repo")
    root.git("init", "-q", "-b", "main")
    cfg = tmp_path / "cfg" / "backlog.json"
    cfg.parent.mkdir()
    cfg.write_text(json.dumps({"trackers": TRACKERS}), encoding="utf-8")

    def bl(*args, config=cfg):
        p = subprocess.run([sys.executable, os.path.join(TOOLS, "backlog.py"), "--root", root.path, *args],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env={**root.env, "KB_BACKLOG_CONFIG": str(config)})
        assert "Traceback" not in p.stderr, p.stderr
        return p.returncode, p.stdout + p.stderr

    def item_files():
        return sorted(Path(root.file("kb/_self/backlog")).glob("*.json"))

    code, out = bl("new", "story", "--title", "Parent story", "--goal", "A parent story")
    parent = re.search(r"ST-[a-z2-7]{8}", out).group(0)
    task = ["new", "task", "--title", "Tracked work item", "--parent", parent, "--goal", "Tracked goal",
            "--touch", "x.txt", "--check", "python3 -c pass"]
    code, out = bl(*task, "--external", "wiki=PAGE-1")  # a tracker the file does not name: refused, nothing written
    assert code == 2 and "wiki" in out and len(item_files()) == 1
    code, out = bl(*task, "--external", "jira=PROJ-123", "--external", "gitlab=12")
    assert code == 0
    tid = re.search(r"TK-[a-z2-7]{8}", out).group(0)

    code, out = bl("set", tid, "--add-external", "jira=PROJ-124")
    assert code == 0
    before = Path(root.file(f"kb/_self/backlog/{tid}.json")).read_text(encoding="utf-8")
    code, out = bl("set", tid, "--add-external", "jira=proj-bad")  # an id its tracker's pattern does not match
    assert code == 2 and "proj-bad" in out and "pattern" in out
    assert Path(root.file(f"kb/_self/backlog/{tid}.json")).read_text(encoding="utf-8") == before

    code, out = bl("show", tid)
    shown = [ln for ln in out.splitlines() if ln.startswith("external ")]
    assert shown == ["external gitlab #12 https://gitlab.corp.example.com/group/proj/-/issues/12",
                     "external jira PROJ-123 https://jira.corp.example.com/browse/PROJ-123",
                     "external jira PROJ-124 https://jira.corp.example.com/browse/PROJ-124"]
    code, out = bl("find", "proj-124")
    assert code == 0 and tid in out

    code, out = bl("claim", tid, "--by", "tester", "--commit")
    assert code == 0, out
    refs = root.git("log", "-1", "--format=%(trailers:key=KB-Ref,valueonly,separator=%x2C)").strip()
    assert refs == "#12,PROJ-123,PROJ-124"
    assert root.git("log", "-1", "--format=%(trailers:key=KB-Work,valueonly)").strip() == tid

    path = Path(root.file(f"kb/_self/backlog/{tid}.json"))  # an id written by hand, as no command writes it
    planted = json.loads(path.read_text(encoding="utf-8"))
    planted["external"]["jira"].append("NOT AN ID")
    path.write_text(json.dumps(planted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    code, out = bl("check")
    assert code == 1 and "'NOT AN ID' does not match the tracker's pattern" in out
    path.write_text(before, encoding="utf-8")

    bare = tmp_path / "cfg" / "none.json"  # a project with no trackers key accepts none
    bare.write_text("{}", encoding="utf-8")
    code, out = bl("set", tid, "--add-external", "jira=PROJ-9", config=bare)
    assert code == 2 and "backlog.json does not name" in out and "names none" in out


def test_backlog_external_ids_trailer_is_accepted_by_check_trailers_and_a_malformed_one_is_not(scenario):
    repo = scenario.clone(hooks=False)

    def audited(message):
        repo.append("notes.txt", "x\n")
        repo.commit(message)
        p = repo.kbgit("check-trailers", "HEAD")
        return p.returncode, p.stdout + p.stderr

    code, out = audited("docs: one ref per id\n\nKB-Ref: PROJ-123\nKB-Ref: #12")
    assert code == 0, out
    code, out = audited("docs: two ids on a line\n\nKB-Ref: PROJ-123 PROJ-124")
    assert code == 1 and "KB-Ref: has PROJ-123 PROJ-124" in out
    code, out = audited("docs: a ref outside the trailer paragraph\n\nKB-Ref: PROJ-123\n\nCo-Authored-By: A <a@example.com>")
    assert code == 1 and "not a trailer: 'KB-Ref: PROJ-123'" in out


def test_backlog_brief_dispatch_prints_the_workers_brief_and_dry_run_starts_nothing(tmp_path):
    (tmp_path / "repo").mkdir()
    root = Repo(tmp_path / "repo")
    root.git("init", "-q", "-b", "main")
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"trackers": TRACKERS}), encoding="utf-8")

    def bl(*args):
        p = subprocess.run([sys.executable, os.path.join(TOOLS, "backlog.py"), "--root", root.path, *args],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env={**root.env, "KB_BACKLOG_CONFIG": str(cfg)})
        assert "Traceback" not in p.stderr, p.stderr
        return p.returncode, p.stdout + p.stderr

    def made(kind, title, *more):
        code, out = bl("new", kind, "--title", title, "--goal", f"Goal of {title}", *more)
        assert code == 0, out
        return re.search(r"[A-Z]{2}-[a-z2-7]{8}", out).group(0)

    story = made("story", "Parent story")
    ids = {}
    for name, touch in (("work", "a.txt"), ("sibling", "b.txt")):
        ids[name] = made("task", f"{name} item", "--parent", story, "--touch", touch, "--check", "python3 -c pass",
                         *(["--external", "jira=PROJ-123"] if name == "work" else []))
        assert bl("claim", ids[name], "--by", "tester")[0] == 0
    code, out = bl("brief", ids["work"], "--known", "tests/test_x.py::test_y=BG-aaaaaaaa")
    assert code == 0, out
    assert ".claude/agents/kb-worker.md" in out and f"_cache/scratch/{ids['work']}/" in out
    assert f'"id": "{ids["work"]}"' in out and "Goal of work item" in out  # the item's JSON and its goal text
    assert "external jira PROJ-123 https://jira.corp.example.com/browse/PROJ-123" in out
    assert f"- {ids['sibling']} \u201csibling item\u201d: b.txt" in out  # the in-flight sibling and its files
    assert f"- {ids['work']} \u201cwork item\u201d" not in out
    assert "- `tests/test_x.py::test_y`: BG-aaaaaaaa" in out
    assert f"KB-Work: {ids['work']}" in out and "never `tests.py --changed`" in out
    assert "No rules pack in this project" in out  # the throwaway repository holds no _tools/rag.py

    def dry(item, *more):
        code, out = bl("dispatch", "--dry-run", item, *more)
        assert code == 0, out
        return {ln.split(": ", 1)[0]: ln.split(": ", 1)[1] for ln in out.splitlines() if ": " in ln}

    shown = dry(ids["work"])
    assert shown["brief"].endswith(f"_cache/scratch/{ids['work']}/brief.md (stdin)")
    assert shown["argv"].startswith("claude -p --model sonnet --effort high --output-format json --add-dir ")
    assert shown["argv"].endswith("--max-turns 60")  # a task
    assert dry(story)["argv"].endswith("--max-turns 100")  # a story
    assert "--model other-model " in dry(ids["work"], "--model", "other-model")["argv"]
    assert not (Path(root.path) / "_cache").exists()  # nothing made, written or started
    assert not (Path(root.path) / ".claude" / "worktrees").exists()
