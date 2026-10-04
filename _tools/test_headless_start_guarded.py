"""A sprint with an item whose touches a headless run may not edit (the files kb_hook.headless_guard denies:
bl_authority.guarded_touches) is operator-present only: `backlog.py start` warns of each such item. A done item does
not count. The tests named headless_start_guarded_items are the item's checks; the shared function agrees with
kb_hook.guarded_file on every path the guard covers, so the notice and the guard cannot drift apart."""
import pytest

import backlog
import bl_authority
import bl_testkit
import kb_hook
from bl_testkit import PASS, argstr, b, item

bl_testkit.bind(backlog)
repo = bl_testkit.repo

GUARDED, PLAIN = "_tools/backlog.py", "kb/public/x.md"


@pytest.fixture(autouse=True)
def host(tmp_path, monkeypatch):
    for k in ("KB_TESTS_FAST", "KB_TEST_WORKERS", "KB_HEADLESS_RUNNER"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("KB_HOST_LOCK_DIR", str(tmp_path / "hostlocks"))


def test_headless_start_guarded_items_start_warns_for_the_guarded_item_only(repo):
    b(repo, "new", "epic", "--title", "E", "--goal", "g")
    ep = item(repo, "E")["id"]
    b(repo, "new", "sprint", "--title", "S", "--goal", "g")
    sp = item(repo, "S")["id"]
    b(repo, "new", "story", "--title", "Story", "--parent", ep, "--sprint", sp, "--goal", "g", "--check", argstr(PASS))
    st = item(repo, "Story")["id"]
    b(repo, "new", "task", "--title", "Guarded", "--parent", st, "--goal", "g", "--touch", GUARDED, "--check", argstr(PASS))
    b(repo, "new", "task", "--title", "Plain", "--parent", st, "--goal", "g", "--touch", PLAIN, "--check", argstr(PASS))
    tk = item(repo, "Guarded")["id"]
    assert b(repo, "answer", sp, "start", "--answer", "approve", "--by", "operator")[0] == 0
    code, out = b(repo, "start", sp)
    assert code == 0 and item(repo, "S")["status"] == "active", out
    assert (f"  warning: {tk} “Guarded” touches {GUARDED}: a headless runner cannot edit them "
            "(operator-present session only)") in out, out
    assert out.count("operator-present session only") == 1 and "“Plain”" not in out, out


def concrete(path):
    """A file the guard path PATH covers: a directory gets a file inside, a family of files a member."""
    return path + "x.md" if path.endswith("/") else path + "x.py" if path.endswith("_") else path


GUARD_SAMPLE = sorted({concrete(p) for p in bl_authority.guard_paths()})
OTHER_SAMPLE = sorted({concrete(p) for p in bl_authority.PATHS["querylog"]}
                      | {"kb/public/x.md", "_tools/test_headless_start_guarded.py", "_tools/kbpyx.py", "README.md", "kb/_self/backlog.md"})


@pytest.mark.parametrize("path", GUARD_SAMPLE + OTHER_SAMPLE)
def test_headless_start_guarded_items_function_agrees_with_the_guard(path):
    """The notice (guarded_touches) and the guard (kb_hook.guarded_file) agree on every path of PATHS' agents-rule and
    push classes, the guard's own files and a sample of the others."""
    want = bool(kb_hook.guarded_file(path))
    assert bool(bl_authority.guarded_touches({"touches": [path]})) is want, path
    assert (path in GUARD_SAMPLE) is bool(kb_hook.guarded_file(path)), path


def test_headless_start_guarded_items_touch_forms_name_a_guard_path():
    """A directory above, a glob and a file inside a guard directory are guarded touches; the rest of a list is not."""
    touches = ["_tools/", "_tools/*.py", ".claude/skills/kb-x/SKILL.md", "_tools/kbpy/x.py", "kb/public/", "README.md", ""]
    got = bl_authority.guarded_touches({"touches": touches})
    assert got == touches[:4], got
    assert bl_authority.guarded_touches({}) == [] and bl_authority.guarded_touches({"touches": None}) == []


def test_headless_start_guarded_items_planted_new_guard_path_moves_both(monkeypatch):
    """Planted: a path added to the guard's list is denied by headless_guard and named by the notice together, as both
    read bl_authority.guard_paths."""
    probe = "tools_extra/guarded.py"
    assert not kb_hook.guarded_file(probe) and not bl_authority.guarded_touches({"touches": [probe]})
    monkeypatch.setattr(bl_authority, "GUARD_EXTRA", bl_authority.GUARD_EXTRA + (probe,))
    assert kb_hook.guarded_file(probe) and bl_authority.guarded_touches({"touches": [probe]}) == [probe]
