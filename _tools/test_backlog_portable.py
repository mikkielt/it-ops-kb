"""backlog.py's project settings (kb/_self/backlog.md, Project settings): `config` prints the effective settings with
each value's source, the kb's committed backlog.json holds the kb's own values, and a file with an unknown key or a
wrong type is refused naming the key; `brief` prints the worker's brief, with the rules of the project's own docs
(`docs_map`, `kb_root`), and `dispatch --dry-run` its argv without starting a session; `cost` on an item no capture
names says so and prints no table of zeros.

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


def test_backlog_config_of_the_root_the_command_runs_on_sets_item_dir_prefixes_trackers_and_worktrees(tmp_path):
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
    assert "id is not" not in bl("check")[1] and "items=1 " in bl("check")[1]
    code, out = bl("dispatch", iid, "--dry-run")
    assert code == 0 and f"/wt/agents/agent-{iid} " in out.replace("\\", "/")  # the path's head may be withheld


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
    assert "No docs map is set for this project" in out  # the throwaway repository has no docs map and no _tools/rag.py

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
