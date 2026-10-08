"""`backlog.py land ID` end to end in a scenario clone: a content-only item lands on origin/main; an item whose check
fails stops `land` at its step and leaves origin/main where it was. The first item's branch sits in a finished worker's
worktree that holds an untracked intake draft: `land` moves the draft aside and says so, and still refuses any other
untracked file. Before the second item lands, a commit of it that changes a mapped tool and no doc is refused at
`done` with stale-docs, and a `Self-Reviewed:` trailer naming the docs clears that."""
import json
import re
from pathlib import Path

import pytest

from conftest import requires_git

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


def test_land_content_item_then_planted_failure(scenario):
    repo = scenario.clone()
    repo.git("config", "core.fileMode", "false")
    sp = new_id(ok(repo, "new", "sprint", "--title", "Landing sprint"))
    good, bad = (new_id(ok(repo, "new", "story", "--title", f"Landing {n}", "--sprint", sp, "--goal",
                           f"The doc {n}.md exists.", "--touch", f"kb/_self/{n}.md", "--check", chk))
                 for n, chk in (("good", "python3 _tools/backlog.py list --kind sprint"),
                                ("bad", "python3 _tools/backlog.py show ST-00000000")))
    ok(repo, "answer", sp, "start", "--answer", "approve", "--by", "operator")
    ok(repo, "start", sp)
    ok(repo, "claim", good, "--by", "t", "--commit")
    ok(repo, "claim", bad, "--by", "t", "--commit")
    repo.commit(f"chore(backlog): plan {sp}", PLAN)
    p = repo.kbgit("sync", "--push", env=NOSYNC)
    assert p.returncode == 0, p.stdout + p.stderr
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
    moved = origin_main(scenario)
    assert moved != before

    research = re.search(r"(ST-[a-z0-9]+)\s.*Research sprint goal", ok(repo, "list", "--sprint", sp)).group(1)
    ok(repo, "claim", research, "--by", "t", "--commit")
    for notes, accepted in ((None, False), ("No outside facts:", False), ("Other. No outside facts: the goal is internal.", True)):
        if notes:
            ok(repo, "set", research, "--notes", notes)
        code, out = bl(repo, "done", research, "--dry-run")  # no commit changes a non-item file: only the note lets it pass
        assert (code == 0 and "would be done" in out) == accepted and (accepted or "KB-Work" in out), out
    repo.git("checkout", "--", PLAN)  # the notes were an experiment

    repo.git("checkout", "-q", "main")
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
