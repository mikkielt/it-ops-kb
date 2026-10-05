"""backlog.py start and the plan rules it shares with check: the code-and-docs rules (a task whose docs wait for its
code, the docs a task's code leaves out of every touches, a touches path a move stranded), the start refusals (no
operator approval, a work item without touches, a host setup not checked on this host, docs after code), its warnings
(docs, a dependency outside the sprint, a recurring P1 item left out) and host-check (bl_plan.py).

Each rule has a planted failure: a sprint started without the operator, a work item without touches, a docs-only task
that depends on the code it describes, a dependency that points outside the sprint, a code task whose docs are in no
item's touches or only in a later task's, a standard doc a task need not carry, a touches path git deleted, a recurring
P1 item the sprint leaves out and a host check that fails or is malformed. The patches name the module where the code
looks the name up, `bl_plan`.
"""
from pathlib import Path

import pytest

import backlog
import bl_testkit
from bl_testkit import PASS, argstr, b, commit, edit, is_file, item, item_json, sh

bl_testkit.bind(backlog)
repo, sprint, no_git_location, gate_jobs = bl_testkit.repo, bl_testkit.sprint, bl_testkit.no_git_location, bl_testkit.gate_jobs


def test_backlog_stale_touches_names_a_file_git_deleted(sprint):
    """Planted: an open task whose touches name a committed file that a later commit moved away; check exits 1 and
    names the item and the path. A path no commit had (still to be created), a glob and a path the tree has again
    are no error, and neither is a done item's."""
    repo, tk = sprint["repo"], sprint["tk"]
    edit(repo, tk, touches=["src/a.txt", "src/never.txt", "src/*.txt", "src/gone/"])
    code, out = b(repo, "check")
    assert code == 0 and "errors=0" in out and "working tree lacks" not in out, out
    sh(repo, "git", "mv", "src/a.txt", "src/moved.txt")
    commit(repo, "move a")
    code, out = b(repo, "check")
    assert code == 1 and "errors=1" in out, out
    assert f"{tk} “Task”: touches names src/a.txt, which git history has and the working tree lacks" in out, out
    assert "src/never.txt" not in out and "src/*.txt" not in out and "src/gone/" not in out, out
    edit(repo, tk, touches=["src/moved.txt"])
    code, out = b(repo, "check")
    assert code == 0 and "errors=0" in out, out
    edit(repo, tk, touches=["src/a.txt"], status="dropped")
    code, out = b(repo, "check")
    assert code == 0 and "errors=0" in out and "working tree lacks" not in out, out


DOC_MAP ="doc,pattern\nkb/_self/tools.md,_tools/x.py\nkb/_self/plugin.md,.claude-plugin/**\n"


@pytest.fixture
def mapped(sprint):
    """The sprint with a kb/_self/map.csv: tools.md describes _tools/x.py, plugin.md all of .claude-plugin/."""
    repo = sprint["repo"]
    (repo / "kb" / "_self").mkdir(parents=True, exist_ok=True)
    (repo / "kb" / "_self" / "map.csv").write_text(DOC_MAP, encoding="utf-8", newline="\n")
    (repo / ".claude-plugin").mkdir()
    (repo / ".claude-plugin" / "plugin.json").write_text("{}\n", encoding="utf-8", newline="\n")
    commit(repo, "map")
    return sprint


def test_backlog_docs_touches_miss_check_warns(mapped):
    """Planted: a task whose touches name mapped code (a literal path and a glob) and none of its docs; check warns,
    naming them, and exits 0. Its docs in the task's own touches clear the warning."""
    repo, tk = mapped["repo"], mapped["tk"]
    code, out = b(repo, "check")
    assert code == 0 and "warnings=0" in out, out
    edit(repo, tk, touches=["_tools/x.py", ".claude-plugin/*.json"])
    code, out = b(repo, "check")
    assert code == 0 and "errors=0" in out and "warnings=1" in out, out
    assert (f"{tk} “Task”: touches code whose kb/_self/map.csv docs are in no item's touches: "
            f"kb/_self/plugin.md, kb/_self/tools.md") in out, out
    edit(repo, tk, touches=["_tools/x.py", ".claude-plugin/*.json", "kb/_self/tools.md", "kb/_self/plugin.md"])
    code, out = b(repo, "check")
    assert code == 0 and "warnings=0" in out, out


def test_check_warns_docs_in_later_task(mapped):
    """Planted: the code's doc only in a task that depends on the code task (a later task); check warns, naming the
    doc and that task. The same doc in an item that does not depend on it is no warning."""
    repo, st, tk = mapped["repo"], mapped["st"], mapped["tk"]
    edit(repo, tk, touches=["_tools/x.py"])
    b(repo, "new", "task", "--title", "Docs", "--parent", st, "--goal", "docs", "--touch", "kb/_self/tools.md",
      "--depends", tk, "--check", argstr(is_file("src/b.txt")))
    docs = item(repo, "Docs")["id"]
    code, out = b(repo, "check")
    assert code == 0 and "warnings=1" in out, out
    assert (f"{tk} “Task”: the docs of its code are only in a later task's touches, {docs} “Docs” "
            f"(it depends on this one): kb/_self/tools.md") in out, out
    assert "in no item's touches" not in out, out
    edit(repo, docs, depends_on=[])
    code, out = b(repo, "check")
    assert code == 0 and "warnings=0" in out, out
    assert code == 0 and "warnings=0" in out, out


def test_backlog_docs_skip_standard_doc(mapped):
    """A standard doc, mapped by a pattern that covers every _tools/*.py (code.md), is no item's to carry: a tools task
    with no code.md in any touches gets no code.md warning. Planted: its narrow doc (tools.md) missing still warns."""
    repo, tk = mapped["repo"], mapped["tk"]
    (repo / "kb" / "_self" / "map.csv").write_text(DOC_MAP + "kb/_self/code.md,_tools/*.py\n", encoding="utf-8",
                                                   newline="\n")
    commit(repo, "code map")
    edit(repo, tk, touches=["_tools/x.py", "kb/_self/tools.md"])
    code, out = b(repo, "check")
    assert code == 0 and "warnings=0" in out and "kb/_self/code.md" not in out, out
    edit(repo, tk, touches=["_tools/x.py"])
    code, out = b(repo, "check")
    assert code == 0 and "warnings=1" in out, out
    assert f"{tk} “Task”: touches code whose kb/_self/map.csv docs are in no item's touches: kb/_self/tools.md " in out, out
    assert "kb/_self/code.md" not in out, out


def test_only_operator_answers_blocking_gates_and_starts_sprints(repo):
    b(repo, "new", "sprint", "--title", "S", "--goal", "g")
    sp = item(repo, "S")["id"]
    assert b(repo, "start", sp)[0] == 1
    code, out = b(repo, "answer", sp, "start", "--answer", "approve", "--by", "agent")
    assert code == 1 and "only the operator" in out
    assert b(repo, "answer", sp, "start", "--provisional")[0] == 1


def test_start_refuses_work_items_without_touches(repo):
    """start names every story, task or bug (not the review) without a scope, changes nothing, and starts once each
    has one: touches of its own, or tasks that all have them. A dropped item is exempt."""
    b(repo, "new", "epic", "--title", "E", "--goal", "g")
    ep = item(repo, "E")["id"]
    b(repo, "new", "sprint", "--title", "S", "--goal", "g")
    sp = item(repo, "S")["id"]
    b(repo, "new", "story", "--title", "Split story", "--parent", ep, "--sprint", sp, "--goal", "g")
    st = item(repo, "Split story")["id"]
    b(repo, "new", "task", "--title", "Its task", "--parent", st, "--goal", "g", "--touch", "src/**")
    b(repo, "new", "story", "--title", "Bare story", "--parent", ep, "--sprint", sp, "--goal", "g")
    bare = item(repo, "Bare story")["id"]
    b(repo, "new", "bug", "--title", "Bare bug", "--sprint", sp, "--severity", "S3",
      "--repro", argstr(is_file("src/c.txt")), "--goal", "c exists")
    bug = item(repo, "Bare bug")["id"]
    b(repo, "new", "bug", "--title", "Dropped bug", "--sprint", sp, "--severity", "S4",
      "--repro", argstr(is_file("src/d.txt")), "--goal", "d exists")
    edit(repo, item(repo, "Dropped bug")["id"], status="dropped", notes="not this sprint")
    assert b(repo, "answer", sp, "start", "--answer", "approve", "--by", "operator")[0] == 0
    files = {f.name: f.read_bytes() for f in (Path(repo) / backlog.REL_DIR).glob("*.json")}
    code, out = b(repo, "start", sp)
    assert code == 1, out
    assert f"{bare} “Bare story”" in out and f"{bug} “Bare bug”" in out, out
    assert "Split story" not in out and "Its task" not in out and "Dropped bug" not in out and "Review" not in out
    assert {f.name: f.read_bytes() for f in (Path(repo) / backlog.REL_DIR).glob("*.json")} == files
    edit(repo, bare, touches=["src/b.txt"])
    edit(repo, bug, touches=["src/c.txt"])
    code, out = b(repo, "start", sp)
    assert code == 0, out
    assert item(repo, "S")["status"] == "active" and item(repo, "Bare bug")["status"] == "todo"


def test_backlog_docs_after_code_start_refuses_and_check_errors(repo):
    """Planted: a planned sprint's docs-only task (touches only kb/_self docs) that depends on a code task whose code
    kb/_self/map.csv maps to those docs; start refuses, changing nothing, and check errors, each naming both. The doc
    in the code task's touches (the docs task then holds another doc) or no dependency clears both."""
    (repo / "kb" / "_self").mkdir(parents=True, exist_ok=True)
    (repo / "kb" / "_self" / "map.csv").write_text(DOC_MAP, encoding="utf-8", newline="\n")
    commit(repo, "map")
    b(repo, "new", "epic", "--title", "E", "--goal", "g")
    ep = item(repo, "E")["id"]
    b(repo, "new", "sprint", "--title", "S", "--goal", "g")
    sp = item(repo, "S")["id"]
    b(repo, "new", "story", "--title", "Story", "--parent", ep, "--sprint", sp, "--goal", "g",
      "--check", argstr(is_file("src/b.txt")))
    st = item(repo, "Story")["id"]
    b(repo, "new", "task", "--title", "Code", "--parent", st, "--goal", "g", "--touch", "_tools/x.py",
      "--check", argstr(is_file("src/b.txt")))
    tk = item(repo, "Code")["id"]
    b(repo, "new", "task", "--title", "Docs", "--parent", st, "--goal", "g", "--touch", "kb/_self/tools.md",
      "--depends", tk, "--check", argstr(is_file("src/b.txt")))
    docs = item(repo, "Docs")["id"]
    assert b(repo, "answer", sp, "start", "--answer", "approve", "--by", "operator")[0] == 0
    files = {f.name: f.read_bytes() for f in (Path(repo) / backlog.REL_DIR).glob("*.json")}
    want = (f"{docs} “Docs”: touches only docs of code that {tk} “Code”, which it depends on, touches: "
            "kb/_self/tools.md")
    code, out = b(repo, "check")
    assert code == 1 and want in out and "errors=1" in out, out
    code, out = b(repo, "start", sp)
    assert code == 1 and want in out, out
    assert {f.name: f.read_bytes() for f in (Path(repo) / backlog.REL_DIR).glob("*.json")} == files
    edit(repo, docs, depends_on=[])
    code, out = b(repo, "start", sp)
    assert code == 0, out


def test_dependency_outside_sprint_named_by_horizon_and_start(repo):
    """Planted: a sprint story depends on an item in no sprint and one in a sprint not started; horizon --sprint
    and start name each with where it stands. A dependency inside the sprint, or on a done item, is not named."""
    b(repo, "new", "epic", "--title", "E", "--goal", "g")
    ep = item(repo, "E")["id"]
    b(repo, "new", "sprint", "--title", "S", "--goal", "g")
    sp = item(repo, "S")["id"]
    b(repo, "new", "sprint", "--title", "Later", "--goal", "g")
    later = item(repo, "Later")["id"]
    b(repo, "new", "story", "--title", "Story", "--parent", ep, "--sprint", sp, "--goal", "g",
      "--touch", "src/a.py", "--check", argstr(PASS))
    b(repo, "new", "story", "--title", "Inside", "--parent", ep, "--sprint", sp, "--goal", "g",
      "--touch", "src/b.py", "--check", argstr(PASS))
    b(repo, "new", "story", "--title", "Nowhere", "--parent", ep, "--goal", "g", "--touch", "src/c.py",
      "--check", argstr(PASS))
    b(repo, "new", "story", "--title", "Unstarted", "--parent", ep, "--sprint", later, "--goal", "g",
      "--touch", "src/d.py", "--check", argstr(PASS))
    st, inside, nowhere, unstarted = (item(repo, t)["id"] for t in ("Story", "Inside", "Nowhere", "Unstarted"))
    edit(repo, st, depends_on=[inside, nowhere, unstarted])
    assert b(repo, "answer", sp, "start", "--answer", "approve", "--by", "operator")[0] == 0
    code, out = b(repo, "horizon", "--sprint", sp)
    assert (f"waiting on outside this sprint: {nowhere} “Nowhere” (in no sprint), "
            f"{unstarted} “Unstarted” (in sprint {later} “Later”, not started)") in out, out
    assert code == 0, out
    code, out = b(repo, "start", sp)
    assert code == 0 and item(repo, "S")["status"] == "active", out
    assert f"  warning: {st} “Story” depends on {nowhere} “Nowhere”, outside this sprint (in no sprint)" in out, out
    assert (f"  warning: {st} “Story” depends on {unstarted} “Unstarted”, outside this sprint "
            f"(in sprint {later} “Later”, not started)") in out, out
    assert out.count("outside this sprint") == 2 and inside not in out, out


def test_start_names_docs_warnings(repo):
    """Planted: a sprint task whose touches name mapped code, its doc in no item's touches; start prints the docs warning for it, exit 0, and starts. The doc in its own
    touches gives no warning."""
    (repo / "kb" / "_self").mkdir(parents=True, exist_ok=True)
    (repo / "kb" / "_self" / "map.csv").write_text(DOC_MAP, encoding="utf-8", newline="\n")
    commit(repo, "map")
    b(repo, "new", "epic", "--title", "E", "--goal", "g")
    ep = item(repo, "E")["id"]
    b(repo, "new", "sprint", "--title", "S", "--goal", "g")
    sp = item(repo, "S")["id"]
    b(repo, "new", "story", "--title", "Story", "--parent", ep, "--sprint", sp, "--goal", "g", "--check", argstr(PASS))
    st = item(repo, "Story")["id"]
    b(repo, "new", "task", "--title", "Code", "--parent", st, "--goal", "g", "--touch", "_tools/x.py",
      "--check", argstr(PASS))
    tk = item(repo, "Code")["id"]
    assert b(repo, "answer", sp, "start", "--answer", "approve", "--by", "operator")[0] == 0
    code, out = b(repo, "start", sp)
    assert code == 0 and item(repo, "S")["status"] == "active", out
    assert (f"  warning: {tk} “Code”: touches code whose kb/_self/map.csv docs are in no item's touches: "
            "kb/_self/tools.md") in out, out
    assert out.count("warning:") == 1, out


def test_start_without_docs_warnings_is_quiet(repo):
    """The same sprint with the doc in the code task's own touches prints no warning."""
    (repo / "kb" / "_self").mkdir(parents=True, exist_ok=True)
    (repo / "kb" / "_self" / "map.csv").write_text(DOC_MAP, encoding="utf-8", newline="\n")
    commit(repo, "map")
    b(repo, "new", "epic", "--title", "E", "--goal", "g")
    ep = item(repo, "E")["id"]
    b(repo, "new", "sprint", "--title", "S", "--goal", "g")
    sp = item(repo, "S")["id"]
    b(repo, "new", "story", "--title", "Story", "--parent", ep, "--sprint", sp, "--goal", "g",
      "--touch", "_tools/x.py", "--touch", "kb/_self/tools.md", "--check", argstr(PASS))
    assert b(repo, "answer", sp, "start", "--answer", "approve", "--by", "operator")[0] == 0
    code, out = b(repo, "start", sp)
    assert code == 0 and "warning:" not in out, out


SKILL_FILE = ".claude/skills/kb-sprint/SKILL.md"


def test_plan_flags_shared_file_in_check_and_start(repo):
    """Three of a sprint's four items name one file: check warns of the planned sprint naming the file and the items,
    and start prints the same warning and starts (exit 0); a sprint whose items name different files is quiet."""
    b(repo, "new", "sprint", "--title", "S", "--goal", "g")
    sp = item(repo, "S")["id"]
    edit(repo, item(repo, "Research sprint goal: S")["id"], status="dropped")  # these tests plan no research
    ids = []
    for n, touch in enumerate((SKILL_FILE, SKILL_FILE, SKILL_FILE, "_tools/other.py")):
        b(repo, "new", "story", "--title", f"Edit {n}", "--sprint", sp, "--goal", "g", "--touch", touch,
          "--check", argstr(is_file("src/b.txt")))
        ids.append(item(repo, f"Edit {n}")["id"])
    code, out = b(repo, "check")
    assert code == 0 and f"{SKILL_FILE} is in the touches of 3 of 4 items ({', '.join(sorted(ids[:3]))})" in out, out
    assert out.count("is in the touches of") == 1 and "split the edits by section" in out, out
    assert b(repo, "answer", sp, "start", "--answer", "approve", "--by", "operator")[0] == 0
    code, out = b(repo, "start", sp)
    assert code == 0 and item(repo, "S")["status"] == "active", out
    assert f"  warning: {SKILL_FILE} is in the touches of 3 of 4 items" in out, out
    code, out = b(repo, "check")
    assert "is in the touches of" not in out, out  # check names a planned sprint's plan; a started one is past it


def test_plan_flags_shared_file_boundaries():
    """More than half and at least three: half, two of two, the exempt docs, a review story and a dropped item are
    no finding; the most shared file comes first."""
    import bl_plan

    class Bl:
        def __init__(self, items):
            self.items = items
    def sprint_of(touches, **kw):
        items = {f"ST-{n:08d}": {"kind": "story", "status": "todo", "touches": t, **kw} for n, t in enumerate(touches)}
        return Bl(items), list(items)
    for touches, want in (([["a"], ["a"], ["a"], ["b"]], [("a", 3)]),
                          ([["a"], ["a"], ["a"], ["b"], ["b"], ["c"]], []),  # half, not more than half
                          ([["a"], ["a"]], []),  # two of two: below the minimum
                          ([["a", "b"], ["a", "b"], ["a"], ["c"]], [("a", 3)]),
                          ([["kb/_self/backlog.md"]] * 4, []),  # the docs items edit by section
                          ([["kb/_self/tools.md", "a"], ["kb/_self/tools.md", "a"], ["kb/_self/tools.md", "a"]],
                           [("a", 3)]),
                          ([["a", "b"], ["a", "b"], ["a", "b"], ["a"]], [("a", 4), ("b", 3)])):
        bl, items = sprint_of(touches)
        found, n = bl_plan.shared_files(bl, items)
        assert [(p, len(ids)) for p, ids in found] == want and n == len(touches), (touches, found)
    bl, items = sprint_of([["a"]] * 3)
    bl.items[items[0]]["review"] = True  # a review story is no work item
    bl.items[items[1]]["status"] = "dropped"
    assert bl_plan.shared_files(bl, items) == ([], 1)


def test_start_warns_recurring_p1_item_left_out_of_the_sprint(repo):
    """start warns (exit 0) of an open P1 item with two or more recurrences outside the sprint; one recurrence, a
    recurring item already in the sprint, a P2 one and a done one give no warning."""
    b(repo, "new", "epic", "--title", "E", "--goal", "g")
    ep = item(repo, "E")["id"]
    b(repo, "new", "sprint", "--title", "S", "--goal", "g")
    sp = item(repo, "S")["id"]
    two = ["SP-aaaaaaaa", "SP-bbbbbbbb"]
    for title, extra, recurs in (("Recurring left out", [], two), ("Recurs once", [], two[:1]),
                                 ("Recurring inside", ["--sprint", sp, "--touch", "src/**"], two),
                                 ("Recurring P2", [], two), ("Recurring done", [], two)):
        prio = "P2" if title == "Recurring P2" else "P1"
        b(repo, "new", "story", "--title", title, "--parent", ep, "--goal", "g", "--priority", prio,
          "--check", argstr(is_file("src/b.txt")), *extra)
        edit(repo, item(repo, title)["id"], recurs=recurs)
    edit(repo, item(repo, "Recurring done")["id"], status="dropped", notes="planted")
    assert b(repo, "check")[0] == 0
    assert b(repo, "answer", sp, "start", "--answer", "approve", "--by", "operator")[0] == 0
    code, out = b(repo, "start", sp)
    assert code == 0, out
    left = item(repo, "Recurring left out")["id"]
    assert f"warning: recurring P1 item {left} “Recurring left out” (recurs in 2 sprints) is not in this sprint" in out
    assert out.count("warning") == 1, out
    assert item(repo, "S")["status"] == "active"


def host_sprint(repo, host_check):
    """A planned sprint whose story has a gate naming a host setup, answered by the operator, with `host_check`."""
    b(repo, "new", "sprint", "--title", "Host sprint", "--goal", "ship b")
    sp = item(repo, "Host sprint")["id"]
    b(repo, "new", "story", "--title", "Host story", "--sprint", sp, "--goal", "b exists",
      "--check", argstr(is_file("src/b.txt")), "--touch", "src/**")
    st = item(repo, "Host story")["id"]
    code, out = b(repo, "gate", "add", st, "--id", "setup", "--question", "Which host?", "--option", "sandbox",
                  "--option", "vm", "--recommendation", "sandbox", "--host-check", argstr(host_check))
    assert code == 0, out
    assert b(repo, "answer", st, "setup", "--answer", "sandbox", "--by", "operator")[0] == 0
    assert b(repo, "answer", sp, "start", "--answer", "approve", "--by", "operator")[0] == 0
    return sp, st


def test_host_setup_gate_checked_records_a_passing_check_and_start_follows(repo):
    sp, st = host_sprint(repo, PASS)
    code, out = b(repo, "start", sp)
    assert code == 1 and "gate setup" in out and "host-check" in out, out
    code, out = b(repo, "host-check", sp)
    assert code == 0 and "ok" in out, out
    assert item_json(repo, st)["gates"][0]["host_checked"] == {"ok": True, "exit": 0}
    assert b(repo, "check")[0] == 0
    code, out = b(repo, "start", sp)
    assert code == 0, out


def test_host_setup_gate_checked_planted_failure_stops_the_sprint(repo):
    sp, st = host_sprint(repo, ["python3", "-c", "import sys; print('feature is off'); sys.exit(3)"])
    code, out = b(repo, "host-check", sp)
    assert code == 1 and "FAILED" in out and "feature is off" in out and "Which host?" in out, out
    assert item_json(repo, st)["gates"][0]["host_checked"] == {"ok": False, "exit": 3}
    code, out = b(repo, "start", sp)
    assert code == 1 and "not checked on this host" in out, out
    assert item_json(repo, sp)["status"] != "active"


def test_host_setup_gate_checked_skips_gates_without_one_and_unanswered_ones(repo):
    b(repo, "new", "sprint", "--title", "Plain sprint", "--goal", "g")
    sp = item(repo, "Plain sprint")["id"]
    b(repo, "new", "story", "--title", "Plain story", "--sprint", sp, "--goal", "g",
      "--check", argstr(PASS), "--touch", "src/**")
    st = item(repo, "Plain story")["id"]
    code, out = b(repo, "host-check", sp)
    assert code == 0 and "no answered gate names a host setup" in out, out
    b(repo, "gate", "add", st, "--question", "Which?", "--option", "a", "--option", "b", "--recommendation", "a",
      "--host-check", argstr(["python3", "-c", "raise SystemExit(1)"]))
    code, out = b(repo, "host-check", sp)
    assert code == 0 and "no answered gate" in out, out


def test_host_setup_gate_checked_refuses_a_malformed_host_check(repo):
    sp, st = host_sprint(repo, PASS)
    edit(repo, st, gates=[dict(item_json(repo, st)["gates"][0], host_check={"run": []})])
    code, out = b(repo, "check")
    assert code != 0 and "host_check needs run" in out, out
    code, out = b(repo, "gate", "add", st, "--question", "Other?", "--option", "a", "--option", "b",
                  "--recommendation", "a", "--host-check", "  ")
    assert code == 2 and "--host-check needs a command" in out, out
