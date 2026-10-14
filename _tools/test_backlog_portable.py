"""backlog.py's project settings (kb/_self/backlog.md, Project settings): `config` prints the effective settings with
each value's source, the kb's committed backlog.json holds the kb's own values, and a file with an unknown key or a
wrong type is refused naming the key; `brief` prints the worker's brief, with the rules of the project's own docs
(`docs_map`, `kb_root`), and `dispatch --dry-run` its argv without starting a session; `cost` on an item no capture
names says so and prints no table of zeros, and it counts a planted headless worker session's prompts on its item while
the orchestrator's prompts outside the item's window stay out of the item's own figure.

The settings files are throwaway directories under tmp_path; the one real file read is the repository's backlog.json."""
import argparse
import contextlib
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

import bl_base
import kbusage
import ql_distill
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
    assert 'land_push = ["_tools/kbgit.py", "sync", "--push"]  (default)' in lines
    assert 'worktree_dir = ".claude/worktrees"  (default)' in lines
    assert [line.split(" = ")[0] for line in lines[1:]] == list(bl_base.SETTINGS)
    # a host's own push and no code lane: an empty lane_module is a value, an empty land_push is not
    push = ["git", "push", "origin", "HEAD:main"]
    (tmp_path / "backlog.json").write_text(json.dumps({"lane_module": "", "land_push": push}), encoding="utf-8")
    lines = config(tmp_path)[1].splitlines()
    assert 'lane_module = ""  (file)' in lines and f"land_push = {json.dumps(push)}  (file)" in lines
    (tmp_path / "backlog.json").write_text(json.dumps({"land_push": []}), encoding="utf-8")
    problems = bl_base.read_settings(tmp_path, env={})[3]
    assert len(problems) == 1 and "key 'land_push' must be a non-empty list of strings" in problems[0]


def test_backlog_config_of_the_kb_is_its_committed_file_and_plugin_sprint_item_dir_default_is_backlog_at_the_root(tmp_path):
    values, sources, path, problems = bl_base.read_settings(bl_base.ROOT, env={})
    assert path.name == "backlog.json" and problems == []
    # the kb's own hook entries take no setting, and its landing's push is the default (the kb's gate script's sync)
    assert {k for k, s in sources.items() if s == "default"} == {"hooks", "land_push"}
    defaults = {k: d for k, (_, d) in bl_base.SETTINGS.items()}
    # the file names the two settings whose default is no longer the kb's value; every other value is the default
    assert values == {**defaults, "item_dir": "kb/_self/backlog",
                      "always_in_scope": ["kb/_self/backlog/**", *defaults["always_in_scope"][1:]]}
    # a project with no backlog.json, or one that names no item_dir, keeps its item files in _backlog/ at its root
    # (outside .claude/, which a headless worker cannot write): the item is created there, listed, and a git worktree
    # of the project can write a file at the same path
    assert defaults["item_dir"] == "_backlog" and defaults["always_in_scope"][0] == "_backlog/**"
    (tmp_path / "project").mkdir()
    root = Repo(tmp_path / "project")
    root.git("init", "-q", "-b", "main")
    cfg = Path(root.path) / "backlog.json"
    cfg.write_text(json.dumps({"lane_module": "mylane"}), encoding="utf-8")
    for missing in (False, True):  # a file without item_dir, then no file
        if missing:
            cfg.unlink()
        values, sources, _, problems = bl_base.read_settings(root.path, env={})
        assert problems == [] and values["item_dir"] == "_backlog" and sources["item_dir"] == "default"
    code, out, _ = config(root.path)
    assert code == 0 and 'item_dir = "_backlog"  (default)' in out.splitlines()
    made = subprocess.run([sys.executable, os.path.join(TOOLS, "backlog.py"), "--root", root.path, "new", "story",
                           "--title", "Default directory story", "--goal", "Goal"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert made.returncode == 0, made.stdout + made.stderr
    iid = re.search(r"ST-[a-z2-7]{8}", made.stdout).group(0)
    assert [p.name for p in (Path(root.path) / "_backlog").glob("*.json")] == [f"{iid}.json"]
    assert not (Path(root.path) / "kb" / "_self" / "backlog").exists()
    root.git("add", "-A")
    root.git("commit", "-q", "-m", "plan")
    work = tmp_path / "worktree"
    root.git("worktree", "add", "-q", "-b", "work/x", str(work))
    (work / "_backlog" / f"{iid}.json").write_text("{}\n", encoding="utf-8")  # a worktree writes at the item path


def test_backlog_config_of_the_root_the_command_runs_on_sets_item_dir_prefixes_trackers_and_worktrees_and_multirepo_fields_and_multirepo_default_and_multirepo_held_and_linked_touch_in_scope_and_linked_touch_check_warns(
        tmp_path, monkeypatch):
    prefixes = {"epic": "AA", "story": "BB", "task": "CC", "subtask": "DD", "bug": "EE", "sprint": "FF"}
    (tmp_path / "backlog.json").write_text(json.dumps({"item_dir": "work/items", "id_prefixes": prefixes,
                                                       "worktree_dir": "wt/agents", "trackers": TRACKERS}),
                                           encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)

    def bl(*args):
        p = subprocess.run([sys.executable, os.path.join(TOOLS, "backlog.py"), "--root", str(tmp_path), *args],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        assert "Traceback" not in p.stderr, p.stderr
        return p.returncode, p.stdout + p.stderr

    code, out = bl("new", "story", "--title", "Probe", "--goal", "Probe goal", "--external", "jira=PROJ-1")
    assert code == 0, out
    iid = re.search(r"\bBB-[a-z2-7]{8}\b", out).group(0)
    assert (tmp_path / "work" / "items" / f"{iid}.json").is_file()
    checked = bl("check")[1]
    assert "id is not" not in checked and "items=1 " in checked
    code, out = bl("dispatch", iid, "--dry-run")
    assert code == 0 and f"/wt/agents/agent-{iid} " in out.replace("\\", "/")  # the path's head may be withheld

    # multirepo_default: no repositories map, a task with touches and no repos is as valid as it was
    code, out = bl("new", "task", "--title", "Probe task", "--parent", iid, "--goal", "Probe task goal",
                   "--touch", "x.txt", "--check", "python3 -c 'import os; os.getcwd()'")
    tid = re.search(r"\bCC-[a-z2-7]{8}\b", out).group(0)
    assert code == 0 and "to fill in" not in out, out
    item_file = tmp_path / "work" / "items" / f"{tid}.json"

    # multirepo_fields: with the map declared, set writes the fields and check validates them
    (tmp_path / "backlog.json").write_text(json.dumps({"item_dir": "work/items", "id_prefixes": prefixes,
                                                       "repositories": {"api": "repos/api", "web": "repos/web"}}),
                                           encoding="utf-8")
    code, out = bl("check")
    assert code == 1 and "touches without repos: backlog.json declares repositories (api, web)" in out
    assert bl("set", tid, "--repos", "api", "--add-repos-if-needed", "web")[0] == 0
    for flags, why in ((("--repos", "nosuch"), "'nosuch', which backlog.json's repositories does not declare"),
                       (("--add-repos-if-needed", "api"), "'api' is in both repos and repos_if_needed")):
        code, out = bl("set", tid, *flags)
        assert code == 2 and why in out, out
    item = json.loads(item_file.read_text(encoding="utf-8"))
    assert item["repos"] == ["api"] and item["repos_if_needed"] == ["web"]
    for bad in ({"workspace": "x"}, {"a": "/abs"}, {"a": "p", "b": "p"}, ["a"]):  # a map the setting refuses
        (tmp_path / "backlog.json").write_text(json.dumps({"repositories": bad}), encoding="utf-8")
        values, _, _, problems = bl_base.read_settings(tmp_path, env={})
        assert values["repositories"] == {} and any("'repositories'" in p for p in problems)

    # multirepo_held: touches are <repo>/<glob>, listed per checkout, and meet only inside one repository
    import bl_plan
    import bl_view
    monkeypatch.setattr(bl_base, "_LOADED", [])  # this root's settings, for this test only
    (tmp_path / "backlog.json").write_text(json.dumps({"item_dir": "work/items", "id_prefixes": prefixes}), encoding="utf-8")
    bl_base.load_settings(tmp_path, env={})
    assert bl_plan.touch_files(tmp_path) == bl_plan.tracked_files(tmp_path)  # no map: the listing as before
    (tmp_path / "backlog.json").write_text(json.dumps({"item_dir": "work/items", "id_prefixes": prefixes,
                                                       "repositories": {"api": "repos/api", "web": "repos/web"}}),
                                           encoding="utf-8")
    bl_base.load_settings(tmp_path, env={})
    for name in ("api", "web"):  # two checkouts under the workspace, each with a tracked a.py
        (tmp_path / "repos" / name).mkdir(parents=True)
        (tmp_path / "repos" / name / "a.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "repos"], check=True)
    files = bl_plan.touch_files(tmp_path)
    assert sorted(f for f in files if f.endswith("a.py")) == ["api/a.py", "web/a.py"]
    assert bl_base.touches_overlap("api/*.py", "api/a*", files) and not bl_base.touches_overlap("api/*.py", "web/a*", files)
    assert not bl_base.touches_overlap("api/**", "web/**", files)  # two repositories share no path
    assert bl_base.touches_overlap("**", "api/a.py", ())  # a touch naming no repository is compared whole
    assert bl_plan.touches_meet("api/*.py", "api/a*", files) and not bl_plan.touches_meet("api/*.py", "web/a.py", files)
    assert not bl_plan.touches_meet("workspace/kb/_self/x.md", "workspace/kb/_self/*.md", files)  # a doc, inside its repository
    bl = bl_base.Backlog(tmp_path)
    task = {"kind": "task", "status": "todo", "sprint": "FF-sprint", "repos": ["api"]}
    bl.items = {"FF-sprint": {"id": "FF-sprint", "kind": "sprint", "status": "active"},
                "CC-mine": {**task, "id": "CC-mine", "touches": ["api/*.py"]},
                "CC-same": {**task, "id": "CC-same", "status": "doing", "claimed_by": "w1", "touches": ["api/a*"]},
                "CC-other": {**task, "id": "CC-other", "status": "doing", "claimed_by": "w2",
                             "touches": ["web/*.py", "workspace/**"]}}
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = bl_view.cmd_held(bl, argparse.Namespace(ref=None, overlaps="CC-mine"))
    held = buf.getvalue().splitlines()
    assert code == 1 and len(held) == 1 and held[0].startswith("api/a*  CC-same") and held[0].endswith("meets api/*.py"), held
    warned = bl_plan.unordered_overlap_warnings(bl)  # the same a.py name in two repositories is no common path
    assert len(warned) == 1 and "CC-mine" in warned[0] and "CC-same" in warned[0] and "api/a.py" in warned[0]
    assert not any("web/a.py" in w for w in warned)

    # linked_touch: a touch that names a link is the file it links to, so its change is in scope, it meets that file's
    # touches, no staging copy is made for it, and check warns naming the target
    if sys.platform == "win32":  # a symlink needs a privilege there
        return
    import bl_dispatch
    root = tmp_path / "linked"
    link = ".claude/skills/kb-sprint/SKILL.md"
    (root / "skills" / "sprint").mkdir(parents=True)
    (root / "skills" / "sprint" / "SKILL.md").write_text("# sprint\n", encoding="utf-8")
    (root / ".claude" / "skills" / "kb-sprint").mkdir(parents=True)
    os.symlink("../../../skills/sprint/SKILL.md", root / link)
    (root / ".claude" / "own.md").write_text("# own\n", encoding="utf-8")
    monkeypatch.setattr(bl_base, "_LOADED", [])
    bl_base.load_settings(root, env={})
    assert bl_base.in_scope("skills/sprint/SKILL.md", [link]) and bl_base.in_scope(link, [link])
    assert not bl_base.in_scope("skills/item/SKILL.md", [link]) and not bl_base.in_scope("skills/sprint/SKILL.md", [])
    assert bl_base.link_target(".claude/own.md") is None and bl_base.link_target(".claude/*") is None
    assert bl_base.touches_overlap(link, "skills/sprint/*.md", ()) and bl_plan.touches_meet("skills/sprint/SKILL.md", link, ())
    bl = bl_base.Backlog(root)
    bl.items = {"CC-linked": {"id": "CC-linked", "kind": "task", "status": "todo", "touches": [link, ".claude/own.md"]}}
    assert bl_dispatch.staged_files(bl, "CC-linked") == [".claude/own.md"]  # the link's target is outside .claude/
    warned = bl_plan.linked_touch_warnings(bl)
    assert len(warned) == 1 and f"touches names {link}, a link to skills/sprint/SKILL.md:" in warned[0], warned
    (root / "skills" / "sprint" / "SKILL.md").unlink()  # a link whose target went: the warning says so
    bl_base._link_target.cache_clear()
    gone = bl_plan.linked_touch_warnings(bl)
    assert len(gone) == 1 and "a link to skills/sprint/SKILL.md, which is gone:" in gone[0], gone


def test_backlog_scratch_setting_places_the_workers_scratch_and_refuses_an_absolute_or_dotdot_path(tmp_path,
                                                                                                   monkeypatch):
    import bl_dispatch
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    monkeypatch.setattr(bl_base, "_LOADED", [])  # the settings of this throwaway root, for this test only
    (tmp_path / "backlog.json").write_text(json.dumps({"scratch_dir": "wt/scratch"}), encoding="utf-8")
    bl_base.load_settings(tmp_path, env={})
    assert bl_dispatch.scratch_path(tmp_path, "ST-aaaaaaaa") == tmp_path.resolve() / "wt" / "scratch" / "ST-aaaaaaaa"
    for bad in ("/abs/scratch", "../scratch"):  # one planted failure for the setting's gate
        (tmp_path / "backlog.json").write_text(json.dumps({"scratch_dir": bad}), encoding="utf-8")
        values, _, _, problems = bl_base.read_settings(tmp_path, env={})
        assert values["scratch_dir"] == "_cache/scratch" and any("'scratch_dir'" in p for p in problems)


def test_backlog_config_refuses_an_unknown_key_and_a_wrong_type_naming_the_key(tmp_path):
    for data, key in (({"item_dri": "x"}, "item_dri"), ({"always_in_scope": "kb/**"}, "always_in_scope")):
        (tmp_path / "backlog.json").write_text(json.dumps(data), encoding="utf-8")
        code, out, err = config(tmp_path)
        assert code == 2 and out == "" and key in err


def test_backlog_done_refuses_unrelated_fetch_state_and_anchor_rows_until_the_goal_names_them_or_they_are_restored(
        tmp_path):
    """One planted failure for the gate: an anchor run's commit advances the baselines of S200 and drops its anchor,
    which neither the goal nor a changed fact names; S100's rows are named by a changed fact, S300's change only
    checked_utc and verified_utc."""
    root = Repo(tmp_path)
    root.git("init", "-q", "-b", "main")

    def bl(*args):
        p = subprocess.run([sys.executable, os.path.join(TOOLS, "backlog.py"), "--root", root.path, *args],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", env=root.env)
        assert "Traceback" not in p.stderr, p.stderr
        return p.returncode, p.stdout + p.stderr

    def state(s100, s200, s300, checked="2026-10-01T00:00:00Z"):
        return ("id,url,checked_utc,etag,doc_sha256\n" + f"S100,https://example.com/a,{checked},{s100},d1\n"
                f"S200,https://example.com/b,{checked},{s200},d2\nS300,https://example.com/c,{checked},{s300},d3\n")

    def anchors(quote, s200=True, verified="2026-10-01"):
        rows = [("f1", "a.md", "S100", quote), ("f2", "a.md", "S200", "q2"), ("f3", "b.md", "S300", "q3")]
        return "fact,path,source_id,status,quote,verified_utc\n" + "".join(
            f"{f},{p},{s},located,{q},{verified if s == 'S300' else '2026-10-01'}\n"
            for f, p, s, q in rows if s200 or s != "S200")

    root.write("backlog.json", json.dumps({"lane_module": ""}))
    root.write("kb/public/_fetch_state.csv", state("e1", "e2", "e3"))
    root.write("kb/public/_anchors.csv", anchors("q1"))
    root.write("kb/public/a.md", "- Fact one. [DOC S100]\n- Fact two. [DOC S200]\n")
    code, out = bl("new", "story", "--title", "Refresh one source", "--goal", "Refresh the facts of one source",
                   "--touch", "kb/public/**", "--check", "python3 -c pass")
    assert code == 0, out
    iid = re.search(r"[A-Z]{2}-[a-z2-7]{8}", out).group(0)
    item = json.loads(root.read(f"_backlog/{iid}.json"))
    root.write(f"_backlog/{iid}.json", json.dumps({**item, "status": "doing"}, indent=2) + "\n")
    root.commit("base")
    root.write("kb/public/a.md", "- Fact one, re-read. [DOC S100]\n- Fact two. [DOC S200]\n")
    root.write("kb/public/_fetch_state.csv", state("f1", "f2", "e3", checked="2026-10-12T00:00:00Z"))
    root.write("kb/public/_anchors.csv", anchors("q1 re-read", s200=False, verified="2026-10-12"))
    root.commit(f"anchor run\n\nKB-Work: {iid}")

    code, out = bl("done", iid, "--dry-run")
    assert code == 1 and "not done" in out, out
    assert "S200 (kb/public/_anchors.csv: dropped, kb/public/_fetch_state.csv: etag)" in out, out
    assert "S100" not in out and "S300" not in out, out  # named by a changed fact; only dates moved
    code, out = bl("set", iid, "--goal", "Refresh the facts of S100 and S200")  # the goal names it
    assert code == 0, out
    code, out = bl("done", iid, "--dry-run")
    assert code == 0 and "would be done" in out, out
    code, out = bl("set", iid, "--goal", "Refresh the facts of one source")
    assert code == 0, out
    root.write("kb/public/_fetch_state.csv", state("f1", "e2", "e3", checked="2026-10-12T00:00:00Z"))  # restored
    root.write("kb/public/_anchors.csv", anchors("q1 re-read", verified="2026-10-12"))
    root.commit(f"restore S200\n\nKB-Work: {iid}")
    code, out = bl("done", iid, "--dry-run")
    assert code == 0 and "would be done" in out, out


def test_backlog_done_orphan_anchor_rows_are_pruned_without_the_goal_naming_the_source_while_a_cited_one_is_refused(
        tmp_path):
    """An anchor run drops the _anchors.csv row of S900, which no fact of a.md cites at the base: it lands without the
    goal naming S900; a later commit dropping the row of S100, which a fact of a.md cites, is refused."""
    root = Repo(tmp_path)
    root.git("init", "-q", "-b", "main")

    def bl(*args):
        p = subprocess.run([sys.executable, os.path.join(TOOLS, "backlog.py"), "--root", root.path, *args],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", env=root.env)
        assert "Traceback" not in p.stderr, p.stderr
        return p.returncode, p.stdout + p.stderr

    def anchors(*rows):
        return "fact,path,source_id,status,quote,verified_utc\n" + "".join(
            f"{f},a.md,{s},{st},{q},2026-10-01\n" for f, s, st, q in rows)

    f1, f9 = ("f1", "S100", "located", "q1"), ("f9", "S900", "unlocated:no-match", "")
    root.write("backlog.json", json.dumps({"lane_module": ""}))
    root.write("kb/public/_anchors.csv", anchors(f1, f9))
    root.write("kb/public/a.md", "- Fact one. [DOC S100]\n")
    code, out = bl("new", "story", "--title", "Re-anchor one article", "--goal", "Re-anchor the facts of one article",
                   "--touch", "kb/public/**", "--check", "python3 -c pass")
    assert code == 0, out
    iid = re.search(r"[A-Z]{2}-[a-z2-7]{8}", out).group(0)
    item = json.loads(root.read(f"_backlog/{iid}.json"))
    root.write(f"_backlog/{iid}.json", json.dumps({**item, "status": "doing"}, indent=2) + "\n")
    root.commit("base")
    root.write("kb/public/_anchors.csv", anchors(f1))
    root.commit(f"prune the orphan row\n\nKB-Work: {iid}")
    code, out = bl("done", iid, "--dry-run")
    assert code == 0 and "would be done" in out, out
    root.write("kb/public/_anchors.csv", anchors())
    root.commit(f"drop a cited row\n\nKB-Work: {iid}")
    code, out = bl("done", iid, "--dry-run")
    assert code == 1 and "S100 (kb/public/_anchors.csv: dropped)" in out and "S900" not in out, out


TRACKERS = {"jira": {"pattern": "[A-Z][A-Z0-9]+-[0-9]+", "url": "https://jira.corp.example.com/browse/{id}"},
            "gitlab": {"pattern": "[0-9]+", "url": "https://gitlab.corp.example.com/group/proj/-/issues/{id}",
                       "ref": "#{id}"}}


def test_backlog_external_ids_are_validated_shown_found_and_carried_by_claim_commits_and_answer_root_commits_worker_item(tmp_path):
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
        return sorted(Path(root.file("_backlog")).glob("*.json"))  # the default item_dir: the config names none

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
    before = Path(root.file(f"_backlog/{tid}.json")).read_text(encoding="utf-8")
    code, out = bl("set", tid, "--add-external", "jira=proj-bad")  # an id its tracker's pattern does not match
    assert code == 2 and "proj-bad" in out and "pattern" in out
    assert Path(root.file(f"_backlog/{tid}.json")).read_text(encoding="utf-8") == before

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

    path = Path(root.file(f"_backlog/{tid}.json"))  # an id written by hand, as no command writes it
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

    # answer --root WORKTREE --commit: the item file alone, on the worker's branch, subject and KB-Work fixed
    for gid, kind in (("g", "blocking"), ("p", "provisional")):
        code, out = bl("gate", "add", tid, "--id", gid, "--kind", kind, "--question", f"Which name for {gid}?", "--option", "a",
                       "--option", "b", "--recommendation", "a")
        assert code == 0, out
    root.commit("gates")
    wt = tmp_path / "worker"
    root.git("worktree", "add", "-q", "-b", f"work/{tid}", str(wt))
    worker = Repo(wt, env=root.env)

    def answer(*args):
        p = subprocess.run([sys.executable, os.path.join(TOOLS, "backlog.py"), "--root", str(wt), "answer", tid, *args],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env={**root.env, "KB_BACKLOG_CONFIG": str(cfg)})
        assert "Traceback" not in p.stderr, p.stderr
        return p.returncode, p.stdout + p.stderr

    def last(fmt):
        return worker.git("log", "-1", f"--format={fmt}").strip()

    head = worker.rev("HEAD")
    code, out = answer("g", "--answer", "a", "--by", "operator")  # without --commit the file is only written
    assert code == 0 and worker.rev("HEAD") == head and worker.git("status", "--porcelain").strip(), out
    worker.git("checkout", "-q", "--", ".")
    code, out = answer("g", "--answer", "a", "--by", "operator", "--commit", "--trailer", "Co-Authored-By: A <a@example.com>")
    assert code == 0, out
    assert last("%s") == f'chore(backlog): answer {tid} "Tracked work item"'
    assert last("%(trailers:key=KB-Work,valueonly)") == tid
    assert worker.git("show", "--name-only", "--format=", "HEAD").split() == [f"_backlog/{tid}.json"]
    assert not worker.git("status", "--porcelain").strip()
    code, out = answer("p", "--provisional", "--commit")
    assert code == 0, out
    code, out = answer("p", "--confirm", "--by", "operator", "--commit")
    assert code == 0, out
    assert last("%s") == f'chore(backlog): answer {tid} "Tracked work item"'
    assert worker.git("log", "--format=%s", f"{head}..HEAD").count(f"chore(backlog): answer {tid}") == 3
    gates = json.loads(Path(wt, "_backlog", f"{tid}.json").read_text(encoding="utf-8"))["gates"]
    assert [(g["id"], g["by"]) for g in gates] == [("g", "operator"), ("p", "operator")]
    code, out = answer("g", "--answer", "a", "--by", "operator", "--trailer", "Co-Authored-By: A <a@example.com>")
    assert code == 1 and "--trailer goes with --record or --commit" in out


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


def test_backlog_brief_known_suite_failure_and_dispatch_prints_the_workers_brief_and_dry_run_starts_nothing_and_multirepo_dispatch_makes_a_worktree_per_required_repository(tmp_path, monkeypatch):
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
    code, out = bl("brief", ids["work"], "--known", "tests/test_x.py::test_y=BG-aaaaaaaa",
                   "--known-suite", "suite seconds budget exceeded=BG-bbbbbbbb")
    assert code == 0, out
    assert "agents/worker.md" in out and ".claude/agents/kb-worker.md" not in out  # no role file here: the plugin's
    assert f"_cache/scratch/{ids['work']}/" in out
    assert f'"id": "{ids["work"]}"' in out and "Goal of work item" in out  # the item's JSON and its goal text
    assert "external jira PROJ-123 https://jira.corp.example.com/browse/PROJ-123" in out
    assert f"- {ids['sibling']} \u201csibling item\u201d: b.txt" in out  # the in-flight sibling and its files
    assert f"- {ids['work']} \u201cwork item\u201d" not in out
    assert "- `tests/test_x.py::test_y`: BG-aaaaaaaa" in out
    assert "- suite-level, no test: suite seconds budget exceeded: BG-bbbbbbbb" in out  # --known-suite, the id as given
    assert "A failure listed here gets no new bug" in out.split("## Known failing", 1)[1].split("## Fixed rules", 1)[0]
    bad_code, bad = bl("brief", ids["work"], "--known-suite", "no bug id here")
    assert bad_code == 2 and "--known-suite 'no bug id here': expected TEXT=BUG" in bad
    plugin_backlog = bl_base.withhold(f"python3 {Path(TOOLS).parent.as_posix()}/_tools/backlog.py")  # no _tools/ here:
    # the plugin's, by its full path (the printed brief withholds the user's name in it, as the line above does)
    assert f"KB-Work: {ids['work']}" in out and f"`{plugin_backlog} gate add {ids['work']} --kind provisional" in out
    assert "python3 _tools/backlog.py" not in out and f"(`{plugin_backlog} goal {ids['work']}`)" in out
    assert f"`{plugin_backlog} done {ids['work']}` exits 0" in out  # the goal text's own `done` command too
    assert "this project has no `_tools/tests.py`" in out and "never `tests.py --changed`" not in out  # its own checks
    assert "`tests.py` result" not in out and "the result of the project's own checks" in out
    assert "No docs map is set for this project" in out  # the throwaway repository has no docs map and no _tools/rag.py

    def dry(item, *more):
        code, out = bl("dispatch", "--dry-run", item, *more)
        assert code == 0, out
        return {ln.split(": ", 1)[0]: ln.split(": ", 1)[1] for ln in out.splitlines() if ": " in ln}

    shown = dry(ids["work"])
    assert shown["brief"].endswith(f"_cache/scratch/{ids['work']}/brief.md (stdin)")
    assert shown["argv"].startswith("claude -p --model sonnet --effort high --output-format json --add-dir ")
    assert shown["argv"].endswith("--max-turns 100")  # a task
    assert dry(story)["argv"].endswith("--max-turns 150")  # a story
    research = made("task", "research item", "--parent", story, "--touch", "kb/public/windows/x.md",
                    "--check", "python3 -c pass")
    assert dry(research)["argv"].endswith("--max-turns 200")  # a task whose scope is kb content only
    assert "--model other-model " in dry(ids["work"], "--model", "other-model")["argv"]
    assert not (Path(root.path) / "_cache").exists()  # nothing made, written or started
    assert not (Path(root.path) / ".claude" / "worktrees").exists()

    # multirepo_dispatch: a worktree per required repository at <worktree_dir>/<id>/<repo>, from the fetched default
    import bl_dispatch
    ws = tmp_path / "ws"
    ws.mkdir()
    Repo(ws).git("init", "-q", "-b", "main")
    names = {"api": "repos/api", "web": "repos/web", "docs": "repos/docs"}  # docs is only in repos_if_needed
    clones = {}
    for name, path in names.items():
        origin, clones[name] = tmp_path / "origins" / f"{name}.git", Repo(ws / path)
        origin.mkdir(parents=True)
        Repo(origin).git("init", "-q", "--bare", "-b", "trunk")
        (ws / path).mkdir(parents=True)
        clones[name].git("init", "-q", "-b", "trunk")
        clones[name].git("remote", "add", "origin", str(origin))
        clones[name].write("a.txt", f"{name}\n")
        clones[name].git("add", "a.txt")
        clones[name].git("commit", "-q", "-m", "first")
        clones[name].git("push", "-q", "origin", "trunk")
        clones[name].git("checkout", "-q", "-b", "side")  # the checkout's own HEAD is not origin's default branch
        clones[name].write("c.txt", "local\n")
        clones[name].git("add", "c.txt")
        clones[name].git("commit", "-q", "-m", "local only")
    other = Repo(tmp_path / "other")  # a newer commit on origin's default branch that the checkout has not fetched
    Repo(tmp_path).git("clone", "-q", str(tmp_path / "origins" / "api.git"), str(other.path))
    other.write("b.txt", "newer\n")
    other.git("add", "b.txt")
    other.git("commit", "-q", "-m", "newer")
    other.git("push", "-q", "origin", "HEAD:trunk")
    newest = other.rev("HEAD")
    assert clones["api"].rev("origin/trunk") != newest

    monkeypatch.setattr(bl_base, "_LOADED", [])  # this workspace's settings, for this test only
    (ws / "backlog.json").write_text(json.dumps({"repositories": names}), encoding="utf-8")
    bl_base.load_settings(ws, env={})
    wbl, iid = bl_base.Backlog(ws), "TK-aaaaaaaa"
    wbl.items = {iid: {"id": iid, "kind": "task", "status": "doing", "title": "t", "goal": "g", "touches": ["api/a.txt"],
                       "repos": ["api", "web"], "repos_if_needed": ["docs"]}}
    item_dir = ws / ".claude" / "worktrees" / iid

    def run_dispatch(**kw):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cmd = bl_dispatch.cmd_dispatch(wbl, argparse.Namespace(id=iid, dry_run=True, model=None, max_turns=None,
                                                                   known=[], known_suite=[], probe=None, **kw))
        assert cmd == 0
        return buf.getvalue().replace("\\", "/")

    dry = run_dispatch()
    assert f"/worktrees/{iid}/api (would be made" in dry and f"/worktrees/{iid}/web (would be made" in dry  # head withheld
    assert "worktree of docs" not in dry and not item_dir.exists()  # a dry run makes nothing; repos_if_needed none
    brief = bl_dispatch.compose_brief(wbl, iid).replace("\\", "/")
    assert f"- api: {item_dir.as_posix()}/api" in brief and "may change if the work needs it: docs" in brief
    assert bl_dispatch.claude_argv(wbl, iid)[8:11] == ["--add-dir", str(bl_dispatch.scratch_path(ws, iid)),
                                                       str(bl_dispatch.repos_dir(ws, iid))]  # the worktrees' directory
    assert bl_dispatch.repo_defaults(wbl, iid) == {"api": "trunk", "web": "trunk"}  # origin's HEAD, after a fetch
    assert clones["api"].rev("origin/trunk") == newest
    for name, co in bl_dispatch.repo_checkouts(wbl, iid):
        bl_dispatch.make_repo_worktree(name, co, bl_dispatch.repo_worktree_path(ws, iid, name), iid, "trunk")
    for name in ("api", "web"):
        made = Repo(item_dir / name)
        assert made.git("symbolic-ref", "--short", "HEAD").strip() == f"work/{iid}"
        assert made.rev("HEAD") == clones[name].rev("origin/trunk") and made.rev("HEAD") != clones[name].rev("side")
        assert made.run_git("rev-parse", "--abbrev-ref", "@{upstream}").returncode != 0  # no upstream, as the workspace's
    assert (item_dir / "api" / "b.txt").is_file() and not (item_dir / "docs").exists()
    assert "(exists)" in run_dispatch()  # a second dispatch reuses the worktrees and fetches nothing

    # a repository whose fetch fails refuses the dispatch naming it, and no worktree is made
    wbl.items["TK-bbbbbbbb"] = {**wbl.items[iid], "id": "TK-bbbbbbbb", "repos": ["api", "web"]}
    os.replace(tmp_path / "origins" / "web.git", tmp_path / "origins" / "web.moved")
    with pytest.raises(bl_base.Refused, match=r"dispatch: repository 'web' .*git fetch origin failed"):
        bl_dispatch.repo_defaults(wbl, "TK-bbbbbbbb")
    assert not (ws / ".claude" / "worktrees" / "TK-bbbbbbbb").exists()

    # multirepo_default: no repositories map, the one worktree as today
    (ws / "backlog.json").write_text("{}", encoding="utf-8")
    bl_base.load_settings(ws, env={})
    assert bl_dispatch.repo_checkouts(wbl, iid) == [] and "worktree of" not in run_dispatch()
    assert bl_dispatch.repo_lines(wbl, iid, "work/x") == []


def test_backlog_brief_rules_are_the_mapped_docs_headings_or_the_kb_roots_fact_lines(tmp_path):
    repo, fx = tmp_path / "repo", tmp_path / "fx"
    for d in (repo / "docs", fx / "print"):
        d.mkdir(parents=True)
    (repo / "docs" / "style.md").write_text(
        "# Style\n\n## Naming\ntext\n\n```\n## not a heading\n```\n\n## Layout\n", encoding="utf-8")
    (repo / "docs" / "ops.md").write_text("# Ops\n\n## Deploy\n", encoding="utf-8")
    (repo / "docs" / "map.csv").write_text("doc,pattern\ndocs/style.md,src/*.py\ndocs/ops.md,deploy/*\n", encoding="utf-8")
    sid = "FXT-" + "a" * 8  # a team's kb root, served from outside the repository (KB_ROOTS)
    (fx / "_root.md").write_text("---\nroot: fixture\nid_prefix: FXT\nvisibility: internal\ndescription: a test root\n"
                                 "---\n", encoding="utf-8")
    (fx / "print" / "queues.md").write_text(
        "---\ntopic: print/queues\npriority: P1\napplies_to: \"PL-SRV-0042 print servers\"\nretrieved_utc: 2026-09-26\n"
        f"sources: [{sid}]\nstatus: partial\n---\n\n# Print queues\n\n## Summary\nKept 14 days.\n\n## Facts\n"
        f"- Finished jobs are kept for 14 days. [DOC {sid}]\n\n## Reference\n\n## Examples\n", encoding="utf-8")
    (fx / "_sources.csv").write_text("id,url,title,publisher,licence,reuse,retrieved_utc,version_or_date,"
                                     "artifact_sha256,used_in,superseded_by\n", encoding="utf-8")
    for name in ("_answers.md", "_conflicts.md", "_gaps.md"):
        (fx / name).write_text("# " + name + "\n", encoding="utf-8")
    root = Repo(repo)
    root.git("init", "-q", "-b", "main")
    cfg = tmp_path / "cfg.json"

    def bl(*args, settings):
        cfg.write_text(json.dumps(settings), encoding="utf-8")
        p = subprocess.run([sys.executable, os.path.join(TOOLS, "backlog.py"), "--root", root.path, *args],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env={**root.env, "KB_BACKLOG_CONFIG": str(cfg), "KB_ROOTS": str(fx),
                                "KB_INDEX": str(tmp_path / "idx")})
        assert "Traceback" not in p.stderr, p.stderr
        assert p.returncode == 0, p.stdout + p.stderr
        return p.stdout

    def made(kind, title, *more):
        out = bl("new", kind, "--title", title, "--goal", "How long are finished print jobs kept?", *more, settings={})
        return re.search(r"[A-Z]{2}-[a-z2-7]{8}", out).group(0)

    story = made("story", "Print queue retention")
    task = made("task", "Finished jobs retention", "--parent", story, "--touch", "src/a.py", "--check", "python3 -c pass")

    def rules(**settings):
        out = bl("brief", task, settings=settings)
        return out.split("## Rules of the docs your touches map to\n", 1)[1].split("\n## Report", 1)[0]

    mapped = rules(docs_map="docs/map.csv", kb_root="")  # the docs the touches map to, with their `##` headings
    assert "- docs/style.md: ## Naming (line 3); ## Layout (line 10)" in mapped
    assert "docs/ops.md" not in mapped and "not a heading" not in mapped
    cited = rules(docs_map="docs/map.csv", kb_root="fixture")  # a kb root: its cited fact lines, in place of the map
    assert "fixture/print/queues.md:16 Finished jobs are kept for 14 days. [DOC " in cited
    assert "docs/style.md" not in cited
    assert rules(docs_map="", kb_root="").strip().splitlines() == [
        "No docs map is set for this project (docs_map and kb_root are empty in backlog.json): follow the role file "
        "and the item's touches."]


def test_backlog_cost_no_capture_names_the_spool_and_prints_no_table_of_zeros(tmp_path):
    (tmp_path / "repo").mkdir()
    root = Repo(tmp_path / "repo")
    root.git("init", "-q", "-b", "main")
    data = tmp_path / "data"
    spool = data / "querylog" / "spool"
    env = {**root.env, "CLAUDE_PLUGIN_DATA": str(data), "CLAUDE_PLUGIN_ROOT": str(bl_base.ROOT)}

    def bl(*args):
        p = subprocess.run([sys.executable, os.path.join(TOOLS, "backlog.py"), "--root", root.path, *args],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
        assert "Traceback" not in p.stderr, p.stderr
        return p.returncode, p.stdout

    code, out = bl("new", "story", "--title", "Unworked story", "--goal", "A story no session worked")
    assert code == 0, out
    sid = re.search(r"ST-[a-z2-7]{8}", out).group(0)

    def worked(*args):
        code, out = bl("cost", sid, *args)
        assert code == 0, out
        return out

    # no spool at all: the header and the one line, no table, and json keeps its keys with the kind
    lines = worked().splitlines()
    assert len(lines) == 2 and lines[0].startswith(f"cost {sid} ")
    assert lines[1].startswith("no capture: ") and "spool" in lines[1] and lines[1].endswith(" no usage rows on this clone")
    shown = json.loads(worked("--format", "json"))
    assert shown["no_line"]["kind"] == "no-capture" and shown["no_line"]["spool"]["usage_rows"] == 0
    assert {"direct", "attributed", "shared", "session_total"} <= set(shown) and shown["session_total"] == {}

    # a spool with usage rows that name no window of the item: the existing line, saying so
    spool.mkdir(parents=True)
    row = {"id": "r1", "ts": "2026-10-10T10:00:00.000Z", "surface": "usage", "session_id": "s1", "prompt_id": "p1",
           "usage": {}}
    (spool / "s1.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    lines = worked().splitlines()
    assert len(lines) == 2 and lines[1].startswith("no item line: because no work sidecar names it")
    assert " usage rows but none in a window of the item" in lines[1]
    assert json.loads(worked("--format", "json"))["no_line"]["kind"] == "unnamed"
    assert worked("--rework").splitlines() == lines  # no open session: --rework prints what plain cost prints

    # a session still open that claimed the item: the same line, then its open session block, no table of zeros
    claim = {"id": "r2", "ts": "2026-10-10T10:01:00.000Z", "surface": "work", "session_id": "s2", "prompt_id": "p2",
             "item": sid, "action": "claim"}
    (spool / "s2.jsonl").write_text(json.dumps(claim) + "\n", encoding="utf-8")
    rework = worked("--rework").splitlines()
    assert rework[:2] == worked().splitlines() and " rows in a window of the item" in rework[1]
    assert rework[2].startswith("open session figures (the session has not closed: provisional until it does): 1 open ")
    assert rework[3].startswith("no figure yet: ")
    assert not any(x.startswith(("direct", "attributed", "session total", "work and rework")) for x in rework)
    assert json.loads(worked("--rework", "--format", "json"))["no_line"]["kind"] == "unnamed"

    # a sidecar line of the item: the tables, as before
    models = {"claude-sonnet-5-5": {"requests": 2, "in": 10, "cw": 0, "cw1h": 0, "cr": 5, "out": 7}}
    sidecar = root.file("kb/_querylog/work/2026-10/20261010T100000Z-abcdef01.jsonl")
    os.makedirs(os.path.dirname(sidecar))
    lines = [{"run": "20261010T100000Z-abcdef01", "reader": 1, "counts": {"items": 1, "shared": 0, "missing": 0}},
             {"item": sid, "prompts": 1, "main": models}]
    Path(sidecar).write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")
    out = worked()
    assert "no item line" not in out and "no capture" not in out
    assert "direct (main):" in out and "session total (direct + attributed + shared):" in out
    assert "claude-sonnet-5-5  requests 2  in 10  cr 5  out 7 | cw 0" in out


def test_backlog_headless_worker_cost_is_its_items_and_orchestrator_cost_not_attributed_outside_its_window(
        tmp_path, monkeypatch):
    """A headless worker session in a worktree the orchestrator made (the `branch` row of `work/<id>` on its first
    prompt, a `usage` row on each) and the orchestrator's session of the same item (`claim` and `done` rows, with
    prompts before the claim and after the done): `cost ID` and `cost --rework SP` count the worker's prompts and
    tokens on the item, once its session is closed and distilled, and of the orchestrator's prompts only those from
    its claim to its done; the others are its session's shared figure, not the item's own."""
    (tmp_path / "repo").mkdir()
    root = Repo(tmp_path / "repo")
    root.git("init", "-q", "-b", "main")
    # distill finds an item's sprint in the kb's item directory (ql_distill.BACKLOG_REL), so this root names it
    (Path(root.path) / "backlog.json").write_text(json.dumps({"item_dir": "kb/_self/backlog"}), encoding="utf-8")
    data = tmp_path / "data"
    qdir = data / "querylog"
    spool = qdir / "spool"
    spool.mkdir(parents=True)
    (qdir / "config.json").write_text(json.dumps({"mode": "local"}), encoding="utf-8")
    env = {**root.env, "CLAUDE_PLUGIN_DATA": str(data), "CLAUDE_PLUGIN_ROOT": str(bl_base.ROOT)}

    def bl(*args):
        p = subprocess.run([sys.executable, os.path.join(TOOLS, "backlog.py"), "--root", root.path, *args],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
        assert "Traceback" not in p.stderr and p.returncode == 0, p.stdout + p.stderr
        return p.stdout

    def made(kind, title, *more):
        return re.search(r"[A-Z]{2}-[a-z2-7]{8}", bl("new", kind, "--title", title, "--goal", "Goal", *more)).group(0)

    sprint = made("sprint", "Worker cost sprint")
    story = made("story", "Worker cost story", "--sprint", sprint)
    task = made("task", "Worker cost task", "--parent", story, "--touch", "a.txt", "--check", "python3 -c pass")
    model = "claude-sonnet-5-5"
    clock = iter(range(1, 60))

    def row(sid, pid, surface, **fields):
        n = next(clock)
        return {"id": f"row{n}", "ts": f"2026-10-10T10:{n:02d}:00.000Z", "surface": surface, "v": 1,
                "session_id": sid, "prompt_id": pid, **fields}

    def plant(sid, prompts):  # (prompt id, work action or None, input tokens): each prompt's rows, then its usage
        rows = []
        for pid, action, tokens in prompts:
            rows.append(row(sid, pid, "prompt"))
            if action:
                rows.append(row(sid, pid, "work", item=task, action=action))
            counts = {"requests": 2, "in": tokens, "cw": 0, "cw1h": 0, "cr": 0, "out": 1}
            rows.append(row(sid, pid, "usage", reader=kbusage.READER_VERSION, usage={"main": {model: counts}, "start": 0}))
        (spool / f"{sid}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    def closed_and_distilled(sid, run_id):
        """The session's end marker, then one distill over the clone's backlog, its sidecar where cost reads it."""
        (spool / f"{sid}.end").touch()
        monkeypatch.setattr(ql_distill, "HOME", Path(root.path))  # the item files its windows are checked against
        rc = ql_distill.distill(qdir=qdir, cfg=qdir / "config.json", haiku=lambda prompt: pytest.fail("no kb prompt"),
                                run_id=run_id, kb_commit="0" * 40, out=lambda s: None)
        assert rc == 0
        shutil.copytree(qdir / "store" / "work", Path(root.path) / "kb" / "_querylog" / "work", dirs_exist_ok=True)

    def report(*args):
        return json.loads(bl("cost", *args, "--format", "json"))

    plant("worker-session", [("w1", "branch", 100), ("w2", None, 200), ("w3", None, 400)])
    plant("orchestrator-session", [("o0", None, 1000), ("o1", "claim", 2000), ("o2", None, 4000), ("o3", "done", 8000),
                                   ("o4", None, 16000)])

    # both sessions still open: no sidecar line, the open block holds the worker's and the window's prompts only
    rep = report("--rework", sprint)
    assert rep["runs"] == 0 and rep["prompts"] == 0 and rep["open_sessions"]["sessions"] == 2
    assert rep["open_sessions"]["prompts"] == 6  # w1-w3 and o1-o3, not o0 and o4
    assert rep["open_sessions"]["rework_split"]["work"]["direct"][model]["in"] == 700 + 14000

    # the worker's session closed and distilled: its runs and tokens are the item's, the orchestrator's are not yet
    closed_and_distilled("worker-session", "20261010T110000Z-aaaa0001")
    for rep in (report(task), report("--rework", sprint)):
        assert rep["runs"] == 1 and rep["prompts"] == 3 and rep["items"] == [task]
        assert rep["direct"][model]["in"] == 700 and rep["by_item"][task]["prompts"] == 3
        assert rep["shared"] == {}

    # the orchestrator's closed too: its claim-to-done prompts join the item's line, the two outside it are shared
    closed_and_distilled("orchestrator-session", "20261010T120000Z-aaaa0002")
    for rep in (report(task), report("--rework", sprint)):
        assert rep["runs"] == 2 and rep["prompts"] == 6 and rep["items"] == [task]
        assert rep["direct"][model]["in"] == 700 + 14000  # 1000 (o0) and 16000 (o4) are not in it
        assert rep["shared_prompts"] == 2 and rep["shared"][model]["in"] == 1000 + 16000
        assert rep["session_total"][model]["in"] == 700 + 14000 + 17000
    split = report("--rework", sprint)["rework_split"]
    assert split["work"]["prompts"] == 6 and split["rework"]["prompts"] == 0 and split["items"] == []


@pytest.mark.skipif(os.name == "nt", reason="the stand-in session is an executable script")
def test_backlog_dispatch_worker_leaves_work_rows_in_the_spool_land_reads_or_its_closing_line_names_where_they_went(
        tmp_path):
    """A worker `dispatch` starts whose session wrote a `branch` row naming its item into the spool land and cost
    read: the closing line says that spool holds it. The same row in another plugin data spool of the host: the line
    names that spool and says land and cost do not read it. A session file with no such row, and no file at all: the
    line says each. The stand-in `claude` writes the session's spool file where the test says."""
    (tmp_path / "repo").mkdir()
    root = Repo(tmp_path / "repo")
    root.git("init", "-q", "-b", "main")
    root.write("a.txt", "a\n")
    root.git("add", "-A")
    root.git("commit", "-q", "-m", "base")
    data, home = tmp_path / "data", tmp_path / "home"
    read_spool = data / "querylog" / "spool"
    other_spool = home / ".claude" / "plugins" / "data" / "it-ops-kb-inline" / "querylog" / "spool"
    read_spool.mkdir(parents=True)
    (data / "querylog" / "config.json").write_text(json.dumps({"mode": "local"}), encoding="utf-8")
    other_spool.mkdir(parents=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "claude"
    fake.write_text(f"#!{sys.executable}\n"
                    "import json, os, sys\n"
                    "sys.stdin.read()\n"
                    "target, item = os.environ.get('FAKE_SPOOL_FILE'), os.environ['FAKE_ITEM']\n"
                    "if target:\n"
                    "    row = {'id': 'r1', 'ts': '2026-10-10T10:00:00.000Z', 'surface': 'work', 'v': 1,\n"
                    "           'session_id': 'sess-1', 'item': item, 'action': os.environ.get('FAKE_ACTION', 'branch')}\n"
                    "    open(target, 'w', encoding='utf-8').write(json.dumps(row) + '\\n')\n"
                    "print(json.dumps({'session_id': 'sess-1', 'is_error': False}))\n", encoding="utf-8")
    fake.chmod(0o755)
    env = {**root.env, "CLAUDE_PLUGIN_DATA": str(data), "CLAUDE_PLUGIN_ROOT": str(bl_base.ROOT), "HOME": str(home),
           "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}

    def bl(*args, extra=None):
        p = subprocess.run([sys.executable, os.path.join(TOOLS, "backlog.py"), "--root", root.path, *args],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", env={**env, **(extra or {})})
        assert "Traceback" not in p.stderr, p.stderr
        return p.returncode, p.stdout + p.stderr

    code, out = bl("new", "task", "--title", "Worked", "--goal", "Goal", "--touch", "a.txt", "--check", "python3 -c pass")
    assert code == 0, out
    iid = re.search(r"[A-Z]{2}-[a-z2-7]{8}", out).group(0)
    assert bl("claim", iid, "--by", "tester")[0] == 0

    def shown(path):  # `say` withholds the user's name in a path
        return bl_base.withhold(str(path))

    def closing(**extra):
        code, out = bl("dispatch", iid, extra={"FAKE_ITEM": iid, **extra})
        assert code == 0, out
        return next(ln for ln in out.splitlines() if ln.startswith(f"rows of {iid}"))

    line = closing(FAKE_SPOOL_FILE=str(read_spool / "sess-1.jsonl"))
    assert "session sess-1 left a branch, agent-start or agent-stop row" in line and f"{shown(read_spool)} (1 row(s))" in line
    assert line.endswith("a spool land and cost read"), line
    (read_spool / "sess-1.jsonl").unlink()
    line = closing(FAKE_SPOOL_FILE=str(other_spool / "sess-1.jsonl"), FAKE_ACTION="agent-stop")
    assert f"in {shown(other_spool)} (1 row(s)), a spool land and cost do not read (they read {shown(read_spool)}" in line, line
    assert "land will name its work rows missing" in line
    line = closing(FAKE_SPOOL_FILE=str(other_spool / "sess-1.jsonl"), FAKE_ACTION="claim")
    assert f"has a spool file in {shown(other_spool)} but no row of {iid} that attributes it" in line, line
    (other_spool / "sess-1.jsonl").unlink()
    line = closing()
    assert "no spool holds a file of session sess-1" in line and f"searched {shown(read_spool)}" in line, line
    assert f"; {shown(other_spool)})" in line, line


def orphan_in(cwd, log, seconds=60):
    """The pid of a python process that sleeps in the directory CWD, its standard output appended to LOG and its
    parent (the launcher that started it) already gone: what a session-end hook's distill is for a few seconds."""
    launcher = ("import subprocess, sys; log = open(sys.argv[2], 'ab'); p = subprocess.Popen([sys.executable, '-c', "
                "'import time; time.sleep(' + sys.argv[3] + ')'], cwd=sys.argv[1], stdin=subprocess.DEVNULL, "
                "stdout=log, stderr=log, start_new_session=True); print(p.pid)")
    started = subprocess.run([sys.executable, "-c", launcher, str(cwd), str(log), str(seconds)], capture_output=True,
                             text=True)
    return int(started.stdout.strip())


@pytest.mark.skipif(os.name == "nt", reason="Windows exposes no process's working directory")
def test_backlog_selfcheck_distill_run_holding_or_waiting_on_the_lock_is_a_hook_in_flight_and_an_old_stray_process_still_fails_and_selfcheck_host_load_suite_ceiling_and_worker_distill_outside_worktree_and_launch_places_keeps_plugin_data_spool_and_refusal_names_the_distill_lock_wait(
        tmp_path, monkeypatch):
    """A run whose standard output is the clone's distill.log and whose parent has exited, younger than
    ql_distill.USAGE_LOCK_WAIT_S plus bl_procs.HOOK_MARGIN_S (waiting for the distill lock) or the pid the lock
    records (holding it), is a `hook` that the orphans check names with its age and passes; the same run past
    both, and a stray process with another standard output, fail it. The host check fails over SUITE_LOAD_PER_CORE
    per core, the load a whole-suite run no longer fits its seconds ceiling at, whatever LOAD_PER_CORE allows, and a
    review story's `done` refuses a whole-suite run at that load, naming the host (a selection it lets through). A
    distill a worker's session end starts has the clone's main checkout as its working directory and script, so no
    process of it runs in the worker's worktree; where one still does, the refusal of `land` names the lock wait."""
    import bl_land
    import bl_procs
    import bl_selfcheck
    import ql_base
    log = tmp_path / "_cache" / "querylog" / "distill.log"
    log.parent.mkdir(parents=True)
    pids = []
    try:
        hook = orphan_in(tmp_path, log)
        pids.append(hook)
        procs, _, why = bl_procs.snapshot(str(tmp_path))
        if procs is None:
            pytest.skip(why)
        assert {p["pid"]: p["kind"] for p in procs} == {hook: bl_procs.HOOK}, procs
        check = bl_selfcheck.check_orphans(str(tmp_path))
        assert check["state"] == "ok" and f"hook(s) in flight: pid {hook} " in check["detail"], check
        assert "orphan(s)" not in check["detail"] and "age " in check["detail"], check

        stray = orphan_in(tmp_path, tmp_path / "stray.log")
        pids.append(stray)
        check = bl_selfcheck.check_orphans(str(tmp_path))
        assert check["state"] == "fail" and f"pid {stray} " in check["detail"], check
        assert f"pid {hook} " not in check["detail"], check  # the young hook is no orphan beside it

        assert bl_procs.hook_run_s() == ql_distill.USAGE_LOCK_WAIT_S + bl_procs.HOOK_MARGIN_S  # not HOOK_GRACE_S
        monkeypatch.setattr(ql_distill, "USAGE_LOCK_WAIT_S", 0)  # the same run, no longer younger than the wait
        monkeypatch.setattr(bl_procs, "HOOK_MARGIN_S", 0)
        check = bl_selfcheck.check_orphans(str(tmp_path))
        assert check["state"] == "fail" and f"pid {hook} " in check["detail"] and "2 orphan(s)" in check["detail"], check
        lock = log.with_name(ql_base.LOCK_NAME)  # the same run past the wait that holds the lock: still at work
        lock.write_text(json.dumps({"pid": hook, "started": "now", "started_epoch": time.time()}), encoding="utf-8")
        check = bl_selfcheck.check_orphans(str(tmp_path))
        assert check["state"] == "fail" and f"pid {hook} " not in check["detail"], check
        assert f"pid {stray} " in check["detail"] and "1 orphan(s)" in check["detail"], check
        lock.write_text(json.dumps({"pid": stray, "started": "now", "started_epoch": time.time()}), encoding="utf-8")
        check = bl_selfcheck.check_orphans(str(tmp_path))  # a lock another pid holds is no hold of this one's
        assert check["state"] == "fail" and "2 orphan(s)" in check["detail"], check
    finally:
        for pid in pids:
            try:
                os.kill(pid, 15)
            except OSError:
                pass

    clone = Repo(tmp_path / "clone")  # the main checkout, with a worker's linked worktree under .claude/worktrees
    os.makedirs(clone.path)
    clone.git("init", "-q", "-b", "main")
    clone.write("_tools/querylog.py", "\n")
    clone.git("add", "-A")
    clone.git("commit", "-q", "-m", "base")
    worker = Path(clone.file(".claude/worktrees/agent-ST-00000001"))
    clone.git("worktree", "add", "-q", "-b", "work/ST-00000001", str(worker))
    monkeypatch.setattr(ql_base, "HOME", worker)  # this copy of the tools is the worker's
    monkeypatch.setattr(ql_base, "ENTRY", worker / "_tools" / "querylog.py")
    entry, home = ql_base.launch_places()
    assert home.resolve() == Path(clone.path).resolve(), home
    assert entry.resolve() == (Path(clone.path) / "_tools" / "querylog.py").resolve(), entry
    data = tmp_path / "plugin-data"  # the worker's copy runs as the plugin: its own entry and directory, its own spool
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(data))
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(worker))
    assert ql_base.plugin_data() == data
    assert ql_base.launch_places() == (worker / "_tools" / "querylog.py", worker), ql_base.launch_places()
    assert ql_base.places()[0] == data / "querylog"
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(clone.path))  # another copy is the plugin: the clone's own rule holds
    assert ql_base.plugin_data() is None
    assert ql_base.launch_places()[1].resolve() == Path(clone.path).resolve()
    monkeypatch.delenv("CLAUDE_PLUGIN_DATA")
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT")
    pid = ql_distill.detach([sys.executable, "-c", "import time; time.sleep(30)"],
                            Path(clone.file("_cache/querylog/distill.log")))
    try:
        in_main, why = bl_land.live_processes(Path(clone.path))
        if in_main is None:
            pytest.skip(why)
        in_worker, _ = bl_land.live_processes(worker)
        assert pid in [p for p, _ in in_main] and pid not in [p for p, _ in in_worker], (in_main, in_worker)
    finally:
        try:
            os.kill(pid, 15)
        except OSError:
            pass

    running = [(4242, "python3")]  # a run still in the worktree: a hook (its distill waits for the lock) or not
    monkeypatch.setattr(bl_land, "live_processes", lambda path: (running, None))
    monkeypatch.setattr(bl_land, "wait_for_hooks", lambda path, procs, root=None: (running, 60, {4242}))
    refused = bl_land.release_worker_worktree(Path(clone.path), worker, None, "work/ST-00000001")
    assert refused and "pid 4242 (python3, a session-end hook)" in refused, refused
    assert f"USAGE_LOCK_WAIT_S ({ql_distill.USAGE_LOCK_WAIT_S} s)" in refused and "end it" not in refused, refused
    assert refused.endswith("then run land again"), refused
    monkeypatch.setattr(bl_land, "wait_for_hooks", lambda path, procs, root=None: (running, 0, set()))
    refused = bl_land.release_worker_worktree(Path(clone.path), worker, None, "work/ST-00000001")
    assert refused and "end it" in refused and "USAGE_LOCK_WAIT_S" not in refused, refused

    monkeypatch.setattr(bl_selfcheck, "lock_facts", lambda now: [])  # the host's own locks are no part of the load
    assert bl_selfcheck.SUITE_LOAD_PER_CORE < bl_selfcheck.LOAD_PER_CORE
    near_ten = bl_selfcheck.check_host(load=10.0, cores=14)  # the SP-wwacrsqr review's load, under LOAD_PER_CORE's 21
    assert near_ten["state"] == "fail" and "load 10.0 over 0.5 per core of 14" in near_ten["detail"], near_ten
    assert "whole-suite" in near_ten["detail"] and near_ten["remedy"] == bl_selfcheck.REMEDY["suite-load"], near_ten
    assert bl_selfcheck.check_host(load=7.0, cores=14)["state"] == "ok"  # at the limit, as 2 to 5 on 14 cores is
    assert bl_selfcheck.check_host(load=7.1, cores=14)["state"] == "fail"
    over_both = bl_selfcheck.check_host(load=30.0, cores=14)  # over LOAD_PER_CORE too: both remedies
    assert over_both["state"] == "fail" and bl_selfcheck.REMEDY["host-load"] in over_both["remedy"], over_both

    suite = [{"run": ["python3", "_tools/backlog.py", "check"]}, {"run": ["python3", "_tools/tests.py"]}]
    named = bl_land.loaded_host_for_suite(suite, load=10.0, cores=14)
    assert named and platform.node() in named and "load 10.0 over 0.5 per core of 14" in named, named
    assert bl_land.loaded_host_for_suite(suite, load=3.3, cores=14) is None  # the planning host's load
    for selection in (["-k", "x"], ["_tools/test_x.py"], ["--changed", "origin/main"]):
        assert bl_land.loaded_host_for_suite([{"run": ["python3", "_tools/tests.py", *selection]}], 10.0, 14) is None
    assert bl_land.loaded_host_for_suite([{"run": ["python3", "_tools/backlog.py", "check"]}], 10.0, 14) is None
    assert bl_land.loaded_host_for_suite([{"run": ["python3", "_tools/tests.py", "--no-reuse"]}], 10.0, 14)


PLUGIN_VAR = "${CLAUDE_PLUGIN_ROOT}"


def unparameterised(text):
    """What a plugin skill or agent text holds that only the kb has: a tool script without the plugin root before it,
    or a path of the kb's own tree."""
    bad = re.findall(r"(?<!\$\{CLAUDE_PLUGIN_ROOT\}/_tools/)\b[a-z_]+\.py\b", text)
    bad += re.findall(r"(?<!\$\{CLAUDE_PLUGIN_ROOT\}/)\b_tools/", text)
    return bad + re.findall(r"\bkb/|\.claude/|AGENTS\.md|_cache/", text)


def test_plugin_sprint_ships_the_skills_and_the_worker_parameterised_by_the_plugin_root_and_lists_them_and_plugin_sprint_hooks_opt_in(tmp_path):
    top = Path(TOOLS).parent
    manifest = json.loads((top / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    skills = {n: top / "skills" / n / "SKILL.md" for n in ("sprint", "item", "backlog")}
    agent = top / "agents" / "worker.md"
    assert {f"./skills/{n}" for n in skills} <= set(manifest["skills"]), manifest["skills"]
    assert "./agents/worker.md" in manifest["agents"], manifest["agents"]
    for path in (*skills.values(), agent):
        text = path.read_text(encoding="utf-8")
        assert f"python3 {PLUGIN_VAR}/_tools/backlog.py" in text and unparameterised(text) == [], (path, unparameterised(text))
        front = text.split("---")[1]
        # a skill's name is its directory's, so a link under another name serves it; an agent's name is required
        assert ("name: kb-worker" in front) == (path == agent) and ("name:" in front) == (path == agent), (path, front)
    assert unparameterised("python3 _tools/backlog.py show X") != []  # the planted failure: a bare kb path is found
    assert unparameterised("see kb/_self/backlog.md") != []
    # the plugin's backlog hook entries all carry --opt-in, and the manifest names the key that turns them on
    commands = [h["command"] for group in manifest["hooks"]["SessionStart"] for h in group["hooks"]
                if "backlog.py" in h["command"]]
    assert sorted(c.split("backlog.py ")[1] for c in commands) == ["horizon --hook --opt-in",
                                                                    "intake --file --hook --opt-in"], commands
    assert "hooks key" in manifest["description"]
    root = tmp_path / "project"
    root.mkdir()

    def hook(*argv):  # (exit code, stdout) of `backlog.py --root ROOT ARGV`
        p = subprocess.run([sys.executable, os.path.join(TOOLS, "backlog.py"), "--root", str(root), *argv],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        assert "Traceback" not in p.stderr, p.stderr
        return p.returncode, p.stdout

    def turn_on(*names):
        (root / "backlog.json").write_text(json.dumps({"hooks": list(names)}), encoding="utf-8")

    assert hook("horizon", "--hook", "--opt-in") == (0, "")  # default []: nothing printed, nothing filed
    assert hook("intake", "--file", "--hook", "--opt-in") == (0, "") and list(root.iterdir()) == []
    assert "backlog:" in hook("horizon", "--hook")[1]  # without the flag (the kb's own entries) it runs as before
    turn_on("horizon")
    assert hook("horizon", "--hook", "--opt-in")[1].count("backlog:") >= 1
    turn_on("intake")  # each hook is named on its own
    assert hook("horizon", "--hook", "--opt-in") == (0, "")
    assert hook("horizon", "--opt-in")[0] == 1  # the flag belongs to the hook form
    for bad in (["horizn"], "horizon"):  # the planted failure: an unknown value, a string for a list
        (root / "backlog.json").write_text(json.dumps({"hooks": bad}), encoding="utf-8")
        values, _, _, problems = bl_base.read_settings(root, env={})
        assert values["hooks"] == [] and any("'hooks'" in x for x in problems), problems
        assert hook("config")[0] == 2 and hook("horizon", "--hook", "--opt-in") == (0, "")


def test_plugin_sprint_role_file_is_the_projects_when_it_has_one_else_the_plugins_and_brief_names_always_in_scope(
        tmp_path, monkeypatch):
    import bl_dispatch
    plugin = bl_dispatch.PLUGIN_ROOT
    assert (plugin / bl_dispatch.PLUGIN_ROLE_FILE).is_file()  # the plugin's role file is where the brief says
    line = bl_dispatch.role_file_line(tmp_path)  # a project with none: the plugin's, and what the variable stands for
    assert f"`{plugin.as_posix()}/agents/worker.md`" in line and f"`{PLUGIN_VAR}` in it is `{plugin.as_posix()}`" in line
    assert ".claude/agents/kb-worker.md" not in line, line
    own = tmp_path / ".claude" / "agents" / "kb-worker.md"
    own.parent.mkdir(parents=True)
    own.write_text("# the project's own role file\n", encoding="utf-8", newline="\n")
    line = bl_dispatch.role_file_line(tmp_path)  # a project with its own keeps it
    assert "Your role file is `.claude/agents/kb-worker.md`" in line and "plugin" not in line.split("backlog. ")[1], line
    # the fixed rules and report: the kb's own wording where the project has the tool, else the project's own checks
    full = f"python3 {plugin.as_posix()}/_tools/backlog.py"
    assert bl_dispatch.backlog_cmd(tmp_path) == full  # no `_tools/backlog.py` under the project: the plugin's, by path
    host = "\n".join(bl_dispatch.worker_rules(tmp_path, "TK-aaaaaaaa", "work/TK-aaaaaaaa")) + bl_dispatch.report_line(tmp_path)
    assert f"`{full} gate add TK-aaaaaaaa --kind" in host and f"`{full} referrers SYMBOL --item TK-aaaaaaaa`" in host
    assert "python3 _tools/" not in host and "tests --changed" not in host and "test lock and waits" not in host
    assert "no `_tools/tests.py`" in host and "no `_tools/tests_ceiling.json`" in host and "selfdoc.py" not in host
    tools = tmp_path / "_tools"
    tools.mkdir()
    for name in ("backlog.py", "tests.py", "tests_ceiling.json", "selfdoc.py"):  # a project that has the kb's tools
        (tools / name).write_text("", encoding="utf-8", newline="\n")
    assert bl_dispatch.backlog_cmd(tmp_path) == "python3 _tools/backlog.py"
    kb = "\n".join(bl_dispatch.worker_rules(tmp_path, "TK-aaaaaaaa", "work/TK-aaaaaaaa")) + bl_dispatch.report_line(tmp_path)
    assert "`python3 _tools/backlog.py gate add TK-aaaaaaaa --kind" in kb and "never `tests.py --changed`" in kb
    assert "`_tools/tests_ceiling.json`" in kb and "`selfdoc.py stale --since <the item's base>`" in kb
    assert "`tests.py` result, `selfdoc.py stale --since origin/main` result, the staging" in kb
    assert "the project's own checks" not in kb and str(plugin.as_posix()) not in kb
    # the paths every item may change are named, as `in_scope` counts them; a project that sets none gets no such line
    globs = bl_base.always_in_scope()
    assert globs and all(f"`{g}`" in kb and f"`{g}`" in host for g in globs)
    assert "a source row in a file the touches name is in scope" in kb and "`_sources.csv` is none of those" in kb
    monkeypatch.setattr(bl_dispatch, "always_in_scope", lambda: ())
    none = "\n".join(bl_dispatch.worker_rules(tmp_path, "TK-aaaaaaaa", "work/TK-aaaaaaaa"))
    assert "Besides the touches" not in none and "A doc that needs an edit outside the touches" in none

