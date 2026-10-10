"""`backlog.py land ID` end to end in a scenario clone, in three scenarios on three workers (a class each), and the step
that frees a worker's worktree in a fourth class. One: an item whose branch sits in a finished worker's worktree that holds an untracked intake draft lands on origin/main: `land` moves
the draft aside and says so, and still refuses any other untracked file; a research story's `done` needs its note on
outside facts. Two: a commit of an item that changes a mapped tool and no doc is refused at `done` with stale-docs, and a
`Self-Reviewed:` trailer naming the docs clears that; an item whose check fails stops `land` at its step and leaves
origin/main where it was; a content landing that adds a CODE tag with no pointer to an article stops at step `lint`,
which ran on that article's path alone. Three: the checkout `land` runs in holds untracked intake drafts and nothing else:
`land` moves them aside and says so before its clean tree step, keeps them there when it stops at a later step, and
refuses at clean tree, moving nothing, when another file or an item that is no filed draft is there. The fourth class,
on a throwaway repository: a finished worker's worktree that a session-end hook's run (its parent gone, its standard
output the clone's distill.log) still holds is waited for and then removed; the wait is bounded by
`bl_procs.HOOK_GRACE_S` and skipped for a process whose parent lives; the same class holds the landing of a
multi-repository item (`multirepo_land`): each repository's request read once, a request that is not merged refused by
repository and state, a dirty, locked or live-process worktree refused by name with none removed, the clean ones
removed, the branches on the default branch deleted, each merge commit written as evidence, and the leftovers close
removes."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import Repo, requires_git

pytestmark = [pytest.mark.git, requires_git]

NOSYNC = {"KB_SYNC_NO_TESTS": "1"}
PLAN = "kb/_self/backlog"


def bl(repo, *args):
    p = repo.tool("backlog.py", *args, env=NOSYNC)
    return p.returncode, p.stdout + p.stderr


def ok(repo, *args):
    code, out = bl(repo, *args)
    assert code == 0, f"backlog.py {' '.join(args)}: {out}"
    return out


def new_id(out):
    return re.search(r"\b((?:ST|SP|TK|BG)-[a-z0-9]+)\b", out).group(1)


def origin_main(scenario):
    return scenario.origin.rev("main")


def item(scenario, iid):
    return json.loads(scenario.origin.git("show", f"main:{PLAN}/{iid}.json"))


def work(repo, iid, rel):
    """One commit on a local branch work/<iid>, made from the pushed planning, changing one kb doc."""
    repo.git("checkout", "-q", "-b", f"work/{iid}", "main")
    repo.write(rel, f"# {iid}\n\nWork of the item.\n")
    repo.git("add", rel)
    repo.git("commit", "-q", "-m", f"docs(kb): {iid} work", "-m", f"KB-Work: {iid}")


def planned(scenario, *stories):
    """A clone whose started sprint has the stories ((name, kb path, check) each) claimed and pushed to origin/main:
    (clone, sprint id, story ids)."""
    repo = scenario.clone()
    repo.git("config", "core.fileMode", "false")
    sp = new_id(ok(repo, "new", "sprint", "--title", "Landing sprint"))
    ids = [new_id(ok(repo, "new", "story", "--title", f"Landing {n}", "--sprint", sp, "--goal", f"The doc {n}.md exists.",
                     "--touch", rel, "--check", chk)) for n, rel, chk in stories]
    ok(repo, "answer", sp, "start", "--answer", "approve", "--by", "operator")
    ok(repo, "start", sp)
    for iid in ids:
        ok(repo, "claim", iid, "--by", "t", "--commit")
    repo.commit(f"chore(backlog): plan {sp}", PLAN)
    p = repo.kbgit("sync", "--push", env=NOSYNC)
    assert p.returncode == 0, p.stdout + p.stderr
    return repo, sp, ids


# One class each: tests.py hands pytest-xdist whole scopes (a file, or a class in it), so the two scenarios run on
# two workers instead of one after the other.
class TestLandedItem:
    def test_land_moves_intake_draft_then_fast_forwards_and_done_checks_notes(self, scenario):
        repo, sp, (good,) = planned(scenario, ("good", "kb/_self/good.md", "python3 _tools/backlog.py list --kind sprint"))
        before = origin_main(scenario)

        work(repo, good, "kb/_self/good.md")
        repo.git("checkout", "-q", "main")  # land runs on main, whose upstream is origin/main: it ends level with it
        worker = Path(repo.file(f".claude/worktrees/agent-{good}"))
        repo.git("worktree", "add", "-q", str(worker), f"work/{good}")
        draft, stray = "kb/_self/backlog/ST-0d1e2f3a.json", "kb/_self/stray.md"
        for rel in (draft, stray):  # an intake draft the worker's session filed, and a file that is no draft
            (worker / rel).write_text("{}\n", encoding="utf-8", newline="\n")
        code, out = bl(repo, "land", good)
        assert code != 0 and "uncommitted changes" in out and (worker / draft).is_file(), out  # nothing moves on a refusal
        (worker / stray).unlink()
        code, out = bl(repo, "land", good)
        assert code == 0 and "landed" in out and "fast-forwarded main" in out, out
        kept = Path(repo.file("_cache/intake-drafts")) / worker.name / Path(draft).name
        assert "moved the untracked intake draft ST-0d1e2f3a.json" in out and kept.is_file() and not worker.exists(), out
        assert repo.rev("main") == origin_main(scenario) and repo.git("branch", "--show-current").strip() == "main"
        assert item(scenario, good)["status"] == "done" and item(scenario, good).get("evidence"), item(scenario, good)
        log = scenario.origin.git("log", "--format=%B", f"{before}..main")
        assert f"KB-Work: {good}" in log and f"done {good}" in log, log
        assert scenario.origin.git("show", "main:kb/_self/good.md").startswith(f"# {good}")
        assert origin_main(scenario) != before

        research = re.search(r"(ST-[a-z0-9]+)\s.*Research sprint goal", ok(repo, "list", "--sprint", sp)).group(1)
        ok(repo, "claim", research, "--by", "t", "--commit")
        for notes, accepted in ((None, False), ("No outside facts:", False), ("Other. No outside facts: the goal is internal.", True)):
            if notes:
                ok(repo, "set", research, "--notes", notes)
            code, out = bl(repo, "done", research, "--dry-run")  # no commit changes a non-item file: only the note lets it pass
            assert (code == 0 and "would be done" in out) == accepted and (accepted or "KB-Work" in out), out


class TestStoppedLand:
    def test_land_runs_lint_on_content_item_then_planted_failures(self, scenario, tmp_path):
        article = "kb/public/agents/codebase-mapping.md"
        nested = "kb/_self/lane/host.md"  # a code-lane path of the kb's lanes
        repo, sp, (bad, lint, host) = planned(
            scenario, ("bad", "kb/_self/bad.md", "python3 _tools/backlog.py show ST-00000000"),
            ("lint", article, "python3 _tools/backlog.py list --kind sprint"),
            ("host", nested, "python3 _tools/backlog.py list --kind sprint"))
        moved = origin_main(scenario)

        work(repo, bad, "kb/_self/bad.md")
        # planted failure of done's docs check: a commit of the item changes a mapped tool and no doc
        tool = "_tools/provider.py"
        repo.write(tool, Path(repo.file(tool)).read_text(encoding="utf-8") + "# changed\n")
        repo.git("commit", "-q", "-am", f"fix(kb): {bad} tool", "-m", f"KB-Work: {bad}")
        code, out = bl(repo, "done", bad, "--dry-run")
        assert code != 0 and "stale-docs:" in out and f"kb/_self/tools.md is older than {tool}" in out, out
        reviewed = "kb/_self/tools.md, kb/_self/code.md, kb/_self/web-sources.md"  # read and still correct: not stale
        repo.git("commit", "-q", "--allow-empty", "-m", f"docs(kb): {bad} review",
                 "-m", f"Self-Reviewed: {reviewed}\nKB-Work: {bad}")
        code, out = bl(repo, "done", bad, "--dry-run")
        assert "stale-docs" not in out and "outside touches" in out, out
        repo.git("reset", "-q", "--hard", "HEAD~2")
        code, out = bl(repo, "land", bad)
        assert code != 0 and "land stopped at step done" in out and "check(s) failed" in out, out
        assert origin_main(scenario) == moved
        assert item(scenario, bad)["status"] == "doing"

        # planted failure of the lint step: a content landing (no _tools/) adds a CODE tag with no path#symbol pointer
        repo.git("checkout", "-q", "-b", f"work/{lint}", "main")
        repo.write(article, Path(repo.file(article)).read_text(encoding="utf-8") + "\n- Planted fact. [CODE S0000001]\n")
        repo.git("commit", "-q", "-am", f"docs(kb): {lint} work", "-m", f"KB-Work: {lint}")
        repo.git("checkout", "-q", "main")
        code, out = bl(repo, "land", lint)
        assert code != 0 and "land stopped at step lint" in out, out
        assert "CODE tag without a path#symbol pointer" in out and f"lint.py {article[3:]} exited 1" in out, out
        assert origin_main(scenario) == moved and item(scenario, lint)["status"] == "doing"

        # a host project of the plugin: no code lane (`lane_module` empty: a commit of a code path lands as content,
        # no merge request) and its own push (`land_push`); a push that exits 3 stops land at that step, `done` already
        # made, and the same landing with a working push lands the item
        repo.git("checkout", "-q", "-b", f"work/{host}", "main")
        repo.write(nested, f"# {host}\n\nWork of the item.\n")
        repo.git("add", nested)
        repo.git("commit", "-q", "-m", f"docs(kb): {host} work", "-m", f"KB-Work: {host}")
        repo.git("checkout", "-q", "main")
        settings = json.loads(Path(repo.file("backlog.json")).read_text(encoding="utf-8"))
        settings.update(lane_module="", land_stale=[], land_eval=[], land_lint=[])

        def land_host(push):
            cfg = tmp_path / "backlog.json"
            cfg.write_text(json.dumps({**settings, "land_push": push}), encoding="utf-8")
            p = repo.tool("backlog.py", "land", host, env={**NOSYNC, "KB_BACKLOG_CONFIG": str(cfg)})
            return p.returncode, p.stdout + p.stderr

        code, out = land_host(["python3", "-c", "import sys; sys.exit(3)"])
        assert code != 0 and "land stopped at step python3 -c" in out and "exited 3" in out, out
        assert "No such file" not in out and origin_main(scenario) == moved and item(scenario, host)["status"] == "doing"
        code, out = land_host(["git", "push", "--no-verify", "origin", "HEAD:main"])
        assert code == 0 and "landed" in out, out
        assert "merge request" not in out and item(scenario, host)["status"] == "done", out
        assert scenario.origin.git("show", f"main:{nested}").startswith(f"# {host}") and origin_main(scenario) != moved


class TestOwnCheckoutDrafts:
    def test_land_moves_own_checkout_drafts_then_refuses_other_files(self, scenario):
        repo, sp, (good,) = planned(scenario, ("good", "kb/_self/good.md", "python3 _tools/backlog.py list --kind sprint"))
        before = origin_main(scenario)
        work(repo, good, "kb/_self/good.md")
        repo.git("checkout", "-q", "main")  # land runs on main in this checkout, which holds the hook's drafts
        aside = Path(repo.file("_cache/intake-drafts")) / Path(repo.path).name

        def plant(name, links):
            doc = {"id": name, "kind": "bug", "title": "A finding", "status": "draft", "links": links}
            repo.write(f"{PLAN}/{name}.json", json.dumps(doc) + "\n")
            return f"{PLAN}/{name}.json"

        filed = ["fingerprint 0123456789ab", "detector drift"]
        draft, handmade, stray = plant("BG-0a1b2c3d", filed), plant("BG-0e1f2a3b", ["parked: later"]), "kb/_self/stray.md"
        repo.write(stray, "# stray\n")
        for other in (stray, handmade):  # one file that is no filed draft keeps every draft where it is
            code, out = bl(repo, "land", good)
            assert code != 0 and "land stopped at step clean tree" in out and "moved the untracked" not in out, out
            assert Path(repo.file(draft)).is_file() and not aside.exists(), out
            (Path(repo.file(other))).unlink()

        code, out = bl(repo, "land", good, "--branch", "work/ST-00000000")  # a later step stops it: drafts stay aside
        assert code != 0 and "land stopped at step branch" in out, out
        assert "moved the untracked intake draft BG-0a1b2c3d.json out of this checkout" in out, out
        assert (aside / "BG-0a1b2c3d.json").is_file() and not Path(repo.file(draft)).exists(), out
        assert origin_main(scenario) == before and repo.git("status", "--porcelain").strip() == ""

        second = plant("BG-4c5d6e7f", ["fingerprint ba9876543210", "detector trailers"])
        code, out = bl(repo, "land", good)
        assert code == 0 and "landed" in out, out
        assert "moved the untracked intake draft BG-4c5d6e7f.json out of this checkout" in out, out
        assert (aside / "BG-4c5d6e7f.json").is_file() and (aside / "BG-0a1b2c3d.json").is_file(), out
        assert not Path(repo.file(second)).exists() and item(scenario, good)["status"] == "done"
        assert repo.rev("main") == origin_main(scenario) != before


def test_empty_selection_refused_and_gone_once(monkeypatch, capsys):
    """Planted failure: tests.py -k zzz_no_such_test exits 2 before any worker starts, names its selector in one line
    and records exit 2 with selected 0; a done item's check that collects nothing is found gone once, kept in its
    evidence and named by close's summary, and the next rerun does not run it."""
    import bl_land
    import tests as kbtests
    rows = []
    monkeypatch.setattr(kbtests, "record_run", lambda mode, entry, args, workers=None: rows.append(
        kbtests.run_fields(mode, entry, workers, False)))
    monkeypatch.setattr(kbtests, "run_pytest", lambda args: pytest.fail("a worker run started"))
    assert kbtests.run_main(["-k", "zzz_no_such_test"]) == 2
    said = capsys.readouterr().err.strip().splitlines()
    assert len(said) == 1 and "`-k zzz_no_such_test` collects no test in _tools/" in said[0], said
    assert [(r["mode"], r["exit"], r["selected"], r["workers"]) for r in rows] == [("keyword", 2, 0, 0)], rows
    assert bl_land.selected_nothing(2, said[0]) and not bl_land.selected_nothing(2, "usage: x\nx: error: y")

    check = {"run": ["python3", "_tools/tests.py", "-k", "zzz_no_such_test"]}
    done = {"id": "ST-00000001", "kind": "story", "title": "Done", "status": "done", "checks": [check],
            "evidence": {"commit": "0" * 40, "checks": []}}

    class FakeBacklog:
        root, items, saved = Path("."), {done["id"]: done}, []

        def sprint_items(self, sid):
            return [done["id"]]

        def save(self, it):
            self.saved.append(it["id"])

        def ancestors(self, iid):
            return []

        def label(self, iid):
            return iid

    runs = []
    monkeypatch.setattr(bl_land, "run_check", lambda root, c: runs.append(c) or (False, 2, said[0]))
    fake = FakeBacklog()
    assert bl_land.rerun_done_checks(fake, "SP-00000001") == [] and len(runs) == 1 and fake.saved == [done["id"]]
    assert bl_land.rerun_done_checks(fake, "SP-00000001") == [] and len(runs) == 1, runs  # not run again
    assert "gone check: python3 _tools/tests.py -k zzz_no_such_test" in bl_land.summary_line(fake, done["id"], set())


def test_land_no_work_rows_late_undelivered_or_missing(tmp_path, monkeypatch, capsys):
    """A landing that exits 0 with no line of the item in the committed work sidecars says which of three it is: a
    worker's row in the spool (rows late, a `land:` line naming the session and its state, no warning), a work sidecar
    naming the item that sits in a local store the integration main lacks (undelivered, the store named), or no worker's
    row anywhere (missing, the claim of the orchestrator's own session not counting); a sidecar the checkout holds says
    nothing, and the exit is 0 in each."""
    import types

    import bl_base
    import bl_land
    import kbpublic
    import ql_capture
    iid, other, sid = "TK-aaaaaaaa", "TK-bbbbbbbb", "c0ffee11-worker-session"
    spool, store, root = tmp_path / "home" / "spool", tmp_path / "home" / "store", tmp_path / "clone"
    spool.mkdir(parents=True)
    (root / "kb" / "_querylog" / "work" / "2026-10").mkdir(parents=True)
    monkeypatch.setattr(ql_capture, "spool_dir", lambda: spool)
    monkeypatch.setattr(bl_base, "main_worktree_spool", lambda r: None)
    monkeypatch.setattr(kbpublic, "integration_remote", lambda r: "origin")
    monkeypatch.setattr(bl_land, "Backlog", lambda r: types.SimpleNamespace(descendants=lambda i: []))

    def rows(item, action):
        return json.dumps({"id": f"{item}-{action}", "ts": "2026-10-10T10:00:00Z", "surface": "work",
                           "session_id": sid, "prompt_id": "p1", "action": action, "item": item}) + "\n"

    def landed():
        code = bl_land.ops_land(lambda bl, a: 0)(types.SimpleNamespace(root=root), types.SimpleNamespace(id=iid))
        assert code == 0
        return capsys.readouterr().out.strip().splitlines()

    session = spool / f"{sid}.jsonl"
    session.write_text(rows(iid, "branch"), encoding="utf-8")
    out = landed()
    assert len(out) == 1 and out[0].startswith(f"land: {iid}'s work rows are late: session {sid[:8]}"), out
    assert "still open" in out[0] and "landed with no work rows" not in out[0], out
    session.with_suffix(".end").write_text("", encoding="utf-8")
    assert "closed and not distilled" in landed()[0]
    session.with_suffix(".end").unlink()

    session.write_text(rows(iid, "agent-stop"), encoding="utf-8")  # a worker started with the Agent tool
    assert landed()[0].startswith(f"land: {iid}'s work rows are late")
    session.write_text(rows(iid, "claim") + rows(other, "branch"), encoding="utf-8")  # the orchestrator's own claim
    out = landed()
    assert len(out) == 1 and out[0].startswith(f"warning: {iid} landed with no work rows (missing)"), out

    sidecar = store / "work" / "2026-10" / "20261010T100000Z-0a1b2c3d.jsonl"
    sidecar.parent.mkdir(parents=True)
    counts = {"requests": 1, "in": 1, "cw": 0, "cw1h": 0, "cr": 0, "out": 1}
    sidecar.write_text(json.dumps({"run": sidecar.stem, "reader": 1, "counts": {"items": 1}}) + "\n" + json.dumps(
        {"item": iid, "prompts": 0, "main": {}, "sub": {"kb-worker": {"claude-sonnet-5-5": counts}}}) + "\n",
        encoding="utf-8")
    out = landed()
    assert len(out) == 1 and out[0].startswith(f"warning: {iid} landed with no work rows on origin/main (undelivered)")
    assert f"{store.parent.name}/store holds 1 work sidecar(s) naming it" in out[0], out  # say() redacts the user name
    assert "origin/main lacks" in out[0] and "apply --push" in out[0], out

    (root / "kb" / "_querylog" / "work" / "2026-10" / sidecar.name).write_text(sidecar.read_text(encoding="utf-8"),
                                                                              encoding="utf-8")
    assert landed() == []


def orphan_in(cwd, log, seconds):
    """The pid of a python process that sleeps SECONDS in the directory CWD, its standard output appended to LOG and its
    parent (the launcher that started it) already gone: what a session-end hook's distill is for a few seconds."""
    launcher = ("import subprocess, sys; log = open(sys.argv[2], 'ab'); p = subprocess.Popen([sys.executable, '-c', "
                "'import time; time.sleep(' + sys.argv[3] + ')'], cwd=sys.argv[1], stdin=subprocess.DEVNULL, "
                "stdout=log, stderr=log, start_new_session=True); print(p.pid)")
    started = subprocess.run([sys.executable, "-c", launcher, str(cwd), str(log), str(seconds)], capture_output=True,
                             text=True)
    return int(started.stdout.strip())


@pytest.mark.skipif(os.name == "nt", reason="Windows exposes no process's working directory")
class TestHookWait:
    def test_land_waits_hook_of_a_finished_session_then_removes_its_worktree_and_multirepo_land_cleans_per_repository(
            self, tmp_path, capsys, monkeypatch):
        """The step of `land` that frees a finished worker's worktree, on a real worktree whose only process is a run
        its session's end hook started: it waits for it, removes the worktree, and says so."""
        import bl_land
        repo = Repo(tmp_path / "clone")
        os.makedirs(repo.path)
        repo.git("init", "-q", "-b", "main")
        repo.write("a.txt", "a\n")
        repo.commit("base")
        worker = Path(repo.file(".claude/worktrees/agent-ST-00000001"))
        repo.git("worktree", "add", "-q", "-b", "work/ST-00000001", str(worker))
        log = Path(repo.file("_cache/querylog/distill.log"))  # the standard output of the run a SessionEnd starts
        log.parent.mkdir(parents=True)
        pid = orphan_in(worker, log, 1)
        try:
            why = bl_land.release_worker_worktree(Path(repo.path), worker, None, "work/ST-00000001")
        finally:
            try:
                os.kill(pid, 15)
            except OSError:
                pass
        said = capsys.readouterr().out
        assert why is None and not worker.exists(), (why, said)
        assert "land: waited " in said and "for the session-end hook to end" in said, said
        self.multirepo_land(tmp_path / "multi", capsys, monkeypatch)

    def multirepo_land(self, base, capsys, monkeypatch):
        """multirepo_land, on throwaway repositories built once with few git calls (empty commits, clones of bare
        origins): a workspace holding one item and three repositories, each with the worktree dispatch makes at
        `<worker dir>/<id>/<repo>` on `work/<id>`: api merged with a merge commit, web fast-forwarded, docs
        fast-forwarded and then given a commit its default branch lacks. The forge answers each repository's request
        from a table; `land_repositories` is `land`'s step of that name, and what it returns is read, not git."""
        import argparse

        import bl_base
        import bl_forge
        import bl_land
        iid = "ST-aaaaaaaa"
        ws, names = Repo(base / "ws"), {"api": "repos/api", "web": "repos/web", "docs": "repos/docs"}
        os.makedirs(ws.path)
        for k, v in (("NAME", "t"), ("EMAIL", "t@example.com")):  # the commits cmd_done makes in this process
            monkeypatch.setenv(f"GIT_AUTHOR_{k}", v)
            monkeypatch.setenv(f"GIT_COMMITTER_{k}", v)
        item = {"id": iid, "kind": "story", "title": "Multi", "status": "doing", "goal": "Merged in each repository.",
                "checks": [{"run": ["python3", "-c", "print('checked')"]}], "claimed_by": "t",
                "touches": [f"{n}/{n}.txt" for n in names], "repos": list(names)}
        ws.write(f"kb/_self/backlog/{iid}.json", json.dumps(item, indent=2) + "\n")
        ws.git("init", "-q", "-b", "main")
        ws.git("add", "-A")
        ws.git("commit", "-q", "-m", "plan")
        config = base / "config.json"
        config.write_text(json.dumps({"repositories": names, "item_dir": PLAN}), encoding="utf-8")
        monkeypatch.setattr(bl_base, "_LOADED", [])  # this workspace's settings, for this test only
        bl_base.load_settings(Path(ws.path), env={"KB_BACKLOG_CONFIG": str(config)})
        checkouts, trees = {}, {}
        for name, rel in names.items():
            origin = base / "origins" / f"{name}.git"
            ws.git("init", "-q", "-b", "main", "--bare", str(origin))
            ws.git("clone", "-q", str(origin), rel)
            checkouts[name] = Repo(Path(ws.path) / rel)
            checkouts[name].git("commit", "-q", "--allow-empty", "-m", "first")
            checkouts[name].git("push", "-q", "origin", "main")
            trees[name] = Repo(Path(ws.path) / ".claude" / "worktrees" / iid / name)
            checkouts[name].git("worktree", "add", "-q", "-b", f"work/{iid}", trees[name].path)
            trees[name].git("commit", "-q", "--allow-empty", "-m", f"{iid}: {name} work")
        states, seen = {}, []

        def request(root, branch=None, title_prefix=None, run=None):
            name = Path(root).name
            seen.append((name, title_prefix))
            return None if name not in states else bl_forge.Request(
                states[name], 7, f"{iid}: work", f"work/{iid}", f"https://gitlab.example.com/grp/{name}/-/merge_requests/7",
                None, None, False, False, None, "")

        monkeypatch.setattr(bl_forge, "read_request", request)
        bl = bl_base.Backlog(Path(ws.path))

        def refused(**states_now):
            states.clear()
            states.update(states_now)
            seen.clear()
            capsys.readouterr()
            with pytest.raises(bl_base.Refused) as e:
                bl_land.land_repositories(bl, iid)
            return str(e.value)

        # one request open and one missing: refused at `requests`, naming each repository and its state
        why = refused(api="merged", web="opened")
        assert "land stopped at step requests" in why and "nothing was removed or changed" in why, why
        assert "repository 'web': merge request !7" in why and "is opened, not merged" in why, why
        assert f"repository 'docs': no merge request titled '{iid}:' (state none)" in why and "'api'" not in why, why
        assert sorted(seen) == [(n, f"{iid}:") for n in sorted(names)], seen  # each request read once
        assert all(Path(t.path).is_dir() for t in trees.values())

        # the forge merges: api with a merge commit, web and docs by fast-forward; docs' worktree commits once more
        checkouts["api"].git("merge", "-q", "--no-ff", "-m", f"Merge branch 'work/{iid}' into 'main'", f"work/{iid}")
        for n in ("web", "docs"):
            checkouts[n].git("merge", "-q", "--ff-only", f"work/{iid}")
        for n in names:
            checkouts[n].git("push", "-q", "origin", "main")
        trees["docs"].git("commit", "-q", "--allow-empty", "-m", f"{iid}: docs more")  # a tip origin/main lacks
        merged = {n: "merged" for n in names}
        trees["web"].git("worktree", "lock", "--reason", "another tool", trees["web"].path)
        Path(trees["api"].file("dirty.txt")).write_text("uncommitted\n", encoding="utf-8")
        holder = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], cwd=trees["docs"].path)
        try:  # a dirty, a locked and a live-process worktree (a session that still runs): each named, none removed
            why = refused(**merged)
        finally:
            holder.kill()
            holder.wait()
        assert "land stopped at step repositories" in why and "nothing was removed" in why, why
        assert "repository 'api': its worktree" in why and "has uncommitted changes" in why, why
        assert "repository 'web': its worktree" in why and "locked (another tool)" in why, why
        assert "repository 'docs': its worktree" in why and f"pid {holder.pid}" in why, why
        assert all(Path(t.path).is_dir() for t in trees.values()), why
        trees["web"].git("worktree", "unlock", trees["web"].path)
        Path(trees["api"].file("dirty.txt")).unlink()

        seen.clear()
        repos = bl_land.land_repositories(bl, iid)
        assert [r.name for r in repos] == list(names) and len(seen) == 3, (repos, seen)  # read once more, once each
        assert not any(Path(t.path).exists() for t in trees.values()) and all(r.tip for r in repos)
        evidence = bl_land.repo_evidence(repos)
        merge_line = checkouts["api"].git("rev-list", "--parents", "-1", "HEAD").split()
        assert len(merge_line) == 3  # the merge commit and its two parents
        assert evidence == {
            "api": {"request": "https://gitlab.example.com/grp/api/-/merge_requests/7", "commit": merge_line[0]},
            "web": {"request": "https://gitlab.example.com/grp/web/-/merge_requests/7",
                    "commit": checkouts["web"].rev("HEAD")},  # a fast-forward: the branch's tip itself
            "docs": {"request": "https://gitlab.example.com/grp/docs/-/merge_requests/7", "commit": ""}}, evidence
        said = capsys.readouterr().out
        assert "repository docs: no merge commit found" in said and "repository api: removed its worktree" in said, said

        # done: the work is merged in the repositories, so land's evidence stands in for a commit of the workspace
        args = dict(id=iid, commit=True, trailer=[])
        with pytest.raises(bl_base.Refused, match=r"merged in its repositories.*run land"):
            bl_land.cmd_done(bl, argparse.Namespace(dry_run=True, **args))
        assert bl_land.cmd_done(bl, argparse.Namespace(dry_run=False, repositories=evidence, **args)) == 0
        saved = json.loads(Path(ws.file(f"kb/_self/backlog/{iid}.json")).read_text(encoding="utf-8"))
        assert saved["status"] == "done" and saved["evidence"]["repositories"] == evidence, saved
        committed = ws.git("log", "-1", "--format=%s", "--name-only").splitlines()
        assert committed[0].startswith(f"chore(backlog): done {iid}") and f"kb/_self/backlog/{iid}.json" in committed

        # after the landing the branches on the default branch go (api's here; docs' is kept and said), and close's
        # helper removes what is left: web's worktree, one more worktree of its merged branch, and then the branch
        assert bl_land.delete_repo_branches([repos[0], repos[2]], iid) == ["api"]
        assert "repository docs: kept work/" in capsys.readouterr().out
        checkouts["web"].git("worktree", "add", "-q", trees["web"].path, f"work/{iid}")
        kept = bl_land.clean_repository_leftovers(Path(ws.path), iid, [(n, Path(checkouts[n].path)) for n in names])
        assert kept == 1 and not Path(trees["web"].path).exists() and not Path(trees["web"].path).parent.exists()
        said = capsys.readouterr().out
        assert "close: repository web: deleted the landed branch" in said and "close: repository docs: kept" in said, said

    def test_land_waits_hook_at_most_the_bound_and_not_for_a_process_whose_parent_lives(self, monkeypatch):
        import bl_land
        import bl_procs
        now = [0.0]
        looks = []
        monkeypatch.setattr(bl_land, "live_processes", lambda path: looks.append(now[0]) or ([(4242, "python3")], None))
        monkeypatch.setattr(bl_procs, "hook_pids", lambda root, pids: {4242})

        def table(parent):
            return {4242: (parent, 0, "python3"), 1: (0, 0, "launchd"), 77: (1, 0, "claude")}

        monkeypatch.setattr(bl_procs, "process_table", lambda: table(1))  # its parent is gone: a hook in flight
        sleeps = []
        procs, waited, hooks = bl_land.wait_for_hooks(
            Path("w"), [(4242, "python3")], clock=lambda: now[0], sleep=lambda s: (sleeps.append(s), now.__setitem__(
                0, now[0] + s)))
        assert procs == [(4242, "python3")] and waited == bl_procs.HOOK_GRACE_S == 60 and hooks == {4242}, procs
        assert len(sleeps) == 60 and looks[-1] == 60.0, (len(sleeps), looks[-1])  # it looked each second, then gave up

        monkeypatch.setattr(bl_procs, "process_table", lambda: table(77))  # a live session's own process: no wait
        now[0], sleeps[:] = 0.0, []
        procs, waited, _ = bl_land.wait_for_hooks(Path("w"), [(4242, "python3")], clock=lambda: now[0],
                                                  sleep=lambda s: sleeps.append(s))
        assert procs == [(4242, "python3")] and waited == 0 and sleeps == []
