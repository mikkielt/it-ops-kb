"""`backlog.py land ID` end to end in a scenario clone: a content-only item lands on origin/main; an item whose check
fails stops `land` at its step and leaves origin/main where it was."""
import json
import re

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
    code, out = bl(repo, "land", good)
    assert code == 0 and "landed" in out, out
    assert item(scenario, good)["status"] == "done" and item(scenario, good).get("evidence"), item(scenario, good)
    log = scenario.origin.git("log", "--format=%B", f"{before}..main")
    assert f"KB-Work: {good}" in log and f"done {good}" in log, log
    assert scenario.origin.git("show", "main:kb/_self/good.md").startswith(f"# {good}")
    moved = origin_main(scenario)
    assert moved != before

    repo.git("checkout", "-q", "main")
    work(repo, bad, "kb/_self/bad.md")
    code, out = bl(repo, "land", bad)
    assert code != 0 and "land stopped at step done" in out and "check(s) failed" in out, out
    assert origin_main(scenario) == moved
    assert item(scenario, bad)["status"] == "doing"
