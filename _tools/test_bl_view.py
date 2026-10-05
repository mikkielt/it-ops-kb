"""backlog.py's read-only views (bl_view.py): ready and next, the near-duplicates of similar, horizon and its
SessionStart hook form, held, find and tree. The patches name the module where the code looks the name up, `bl_view`.
"""
import json, os
from pathlib import Path

import pytest

import backlog
import bl_view
import bl_testkit
from bl_testkit import TOOLS, argstr, b, commit, edit, is_file, item, sh

bl_testkit.bind(backlog)

repo, sprint, no_git_location, gate_jobs = bl_testkit.repo, bl_testkit.sprint, bl_testkit.no_git_location, bl_testkit.gate_jobs


def test_backlog_similar_ranks_open_items_and_new_warns_of_a_near_duplicate(sprint):
    """A planted duplicate: similar ranks it first as near, new names it in a warning and still writes the item with
    exit 0; a unique title gets no warning, and a dropped item is no longer compared."""
    repo, ep = sprint["repo"], sprint["ep"]
    b(repo, "new", "story", "--title", "Rotate the BitLocker recovery keys after use", "--parent", ep,
      "--goal", "every used recovery key is rotated")
    dup = item(repo, "Rotate the BitLocker recovery keys after use")["id"]
    code, out = b(repo, "similar", "Rotate BitLocker recovery keys")
    assert code == 0, out
    first = out.splitlines()[0]
    assert dup in first and "near" in first and first.startswith("1.00"), out
    assert b(repo, "similar", "Rotate BitLocker recovery keys") == (code, out)  # deterministic
    code, out = b(repo, "new", "story", "--title", "Rotate used BitLocker recovery keys", "--parent", ep,
                  "--goal", "recovery keys rotated")
    assert code == 0, out
    assert f"warning: near-duplicate of open {dup} “Rotate the BitLocker recovery keys after use”" in out, out
    assert item(repo, "Rotate used BitLocker recovery keys")["status"] == "draft"
    code, out = b(repo, "new", "story", "--title", "Publish the sprint calendar", "--parent", ep,
                  "--goal", "calendar published")
    assert code == 0 and "warning" not in out, out
    edit(repo, dup, status="dropped", notes="planted")
    edit(repo, item(repo, "Rotate used BitLocker recovery keys")["id"], status="dropped", notes="planted")
    code, out = b(repo, "similar", "Rotate BitLocker recovery keys")
    assert code == 0 and dup not in out and "0 near-duplicate(s)" in out, out
    assert b(repo, "similar", "a the of")[0] == 1  # nothing to compare is refused, not an empty ranking


def test_backlog_similar_recurs_is_a_list_of_sprint_ids(sprint):
    """recurs is optional; check refuses a non-list, a non-sprint id and a repeated sprint, and fmt keeps it stable."""
    repo, st = sprint["repo"], sprint["st"]
    for bad, why in (("SP-aaaaaaaa", "recurs must be a list"), (["ST-aaaaaaaa"], "recurs must be a list"),
                     (["SP-aaaaaaaa", "SP-aaaaaaaa"], "recurs names a sprint twice")):
        edit(repo, st, recurs=bad)
        code, out = b(repo, "check")
        assert code == 1 and why in out, out
    edit(repo, st, recurs=["SP-aaaaaaaa", "SP-bbbbbbbb"])
    f = Path(repo) / backlog.REL_DIR / f"{st}.json"
    before = f.read_bytes()
    assert b(repo, "fmt")[1].strip() == "fmt: rewrote 0" and f.read_bytes() == before
    code, out = b(repo, "check")
    assert code == 0 and "errors=0" in out, out


def test_next_orders_s1_bugs_first(sprint):
    repo = sprint["repo"]
    edit(repo, sprint["bg"], severity="S1")
    code, out = b(repo, "next", "--all")
    assert code == 0
    assert out.splitlines()[0].startswith(sprint["bg"])
    assert sprint["st"] not in out  # a story with an open task is not ready itself
    assert sprint["rv"] not in out  # the review waits on every other item


def test_horizon_splits_reachable_from_gated(sprint):
    repo = sprint["repo"]
    edit(repo, sprint["bg"], gates=[{"id": "G1", "kind": "blocking", "question": "Fix or drop?",
                                     "recommendation": "fix"}])
    code, out = b(repo, "horizon")
    assert code == 0
    assert "2 more reachable" in out and "2 wait on the operator" in out
    assert "Fix or drop?" in out and "critical path (2 steps" in out
    code, out = b(repo, "horizon", "--hook")
    hook = json.loads(out)
    assert "Fix or drop?" in hook["hookSpecificOutput"]["additionalContext"]


def test_task_inherits_its_storys_undone_depends_on(sprint):
    """A story that depends on an undone item holds its tasks too, in waits, ready, next and horizon."""
    repo, st, tk, bg = sprint["repo"], sprint["st"], sprint["tk"], sprint["bg"]
    assert tk in bl_view.ready(backlog.Backlog(repo))
    edit(repo, st, depends_on=[bg])
    bl = backlog.Backlog(repo)
    assert any(w.startswith(f"depends on {bl.label(bg)} (through {bl.label(st)})") for w in backlog.waits(bl, tk))
    assert tk not in bl_view.ready(bl) and bl_view.ready(bl) == [bg]
    code, out = b(repo, "next", "--all")
    assert code == 0 and tk not in out and bg in out, out
    reach, stuck, path, widths = bl_view.horizon(bl, sprint["sp"])
    assert tk in reach and not stuck  # in-sprint: reachable, but after the bug on the critical path
    assert path == [bg, tk, st, sprint["rv"]] and widths == [1, 1, 1, 1]
    # a dependency outside the sprint holds the task as it holds the story
    b(repo, "new", "story", "--title", "Elsewhere", "--parent", sprint["ep"], "--goal", "x",
      "--check", argstr(is_file("src/x.txt")))
    edit(repo, st, depends_on=[item(repo, "Elsewhere")["id"]])
    reach, stuck, path, widths = bl_view.horizon(backlog.Backlog(repo), sprint["sp"])
    assert tk not in reach and any(tk in ids for c, ids in stuck.items() if c.startswith("outside this sprint"))


def planned_sprint(repo):
    """A planned sprint with a bug besides its review; its start gate is unanswered."""
    b(repo, "new", "sprint", "--title", "Planned", "--goal", "ship c")
    sp = item(repo, "Planned")["id"]
    b(repo, "new", "bug", "--title", "Planned bug", "--sprint", sp, "--severity", "S3",
      "--repro", argstr(is_file("src/c.txt")), "--goal", "c exists")
    return sp


def test_horizon_start_unanswered_is_the_operators_question(repo):
    sp = planned_sprint(repo)
    code, out = b(repo, "horizon", "--sprint", sp)
    assert code == 0, out
    assert "the sprint's start gate:" in out and "3 wait on the operator or a trigger" in out, out
    assert "approved, not started" not in out and "wait on backlog.py start" not in out, out
    # a change answer is no approval: still the operator's question (planted: an answer read as approval)
    edit(repo, sp, gates=[dict(g, answer="change: drop the bug", by="operator") if g["id"] == "start" else g
                          for g in item(repo, "Planned")["gates"]])
    code, out = b(repo, "horizon", "--sprint", sp)
    assert "the sprint's start gate:" in out and "approved, not started" not in out, out
    code, out = b(repo, "horizon", "--sprint", sp, "--hook")
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "3 wait on the operator" in ctx and "backlog.py start" not in ctx.split("Goals and")[0], ctx


def test_horizon_start_approved_waits_on_backlog_start_not_the_operator(repo):
    sp = planned_sprint(repo)
    assert b(repo, "answer", sp, "start", "--answer", "approve", "--by", "operator")[0] == 0
    code, out = b(repo, "horizon", "--sprint", sp)
    assert code == 0, out
    assert f"approved, not started; run python3 _tools/backlog.py start {sp}" in out, out
    assert f"3 wait on backlog.py start {sp}; 0 wait on the operator or a trigger" in out, out
    assert "Approve this sprint" not in out, out
    code, out = b(repo, "horizon", "--sprint", sp, "--hook")
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "3 wait on backlog.py start" in ctx and "wait on the operator" not in ctx, ctx
    assert "approved, not started" in ctx and "Approve this sprint" not in ctx, ctx
    code, out = b(repo, "horizon", "--hook")  # no active sprint: the planned list names the approval
    assert f"(approved, not started: backlog.py start {sp})" in json.loads(out)["systemMessage"], out
    # an item's own gate is still the operator's, inside an approved sprint
    bg = item(repo, "Planned bug")["id"]
    edit(repo, bg, gates=[{"id": "G1", "kind": "blocking", "question": "Fix or drop?", "recommendation": "fix"}])
    code, out = b(repo, "horizon", "--sprint", sp)
    assert "2 wait on backlog.py start" in out and "1 wait on the operator or a trigger" in out, out


def test_horizon_hook_lists_approved_sprint_beside_active(sprint):
    """BG-iu53ncyj planted: one active sprint and one planned sprint the operator approved; horizon and its hook name
    the approved one as approved, not started, with backlog.py start as its next step, first, while the active one is
    reported as before. An unapproved planned sprint is not listed."""
    repo, active = sprint["repo"], sprint["sp"]
    sp = planned_sprint(repo)
    code, out = b(repo, "horizon")
    assert code == 0 and f"sprint {sp} “Planned”" not in out, out
    assert b(repo, "answer", sp, "start", "--answer", "approve", "--by", "operator")[0] == 0
    want = f"sprint {sp} “Planned”: approved, not started; next step: python3 _tools/backlog.py start {sp}"
    code, out = b(repo, "horizon")
    assert code == 0 and out.splitlines()[0] == want and f"sprint {active} “Sprint” [active]" in out, out
    code, out = b(repo, "horizon", "--hook")
    msg = json.loads(out)["systemMessage"]
    assert msg.splitlines()[0] == want and f"sprint {active} “Sprint”:" in msg, msg
    code, out = b(repo, "horizon", "--sprint", active)
    assert "approved, not started; next step" not in out, out


HOOK_LIMIT = 1000  # characters of the SessionStart hook's whole stdout, which every session in a clone reads


def test_horizon_hook_prints_sprint_ids_and_titles_without_goals(sprint):
    repo = sprint["repo"]
    goals = {}
    for n in range(4):
        title = f"Long sprint {n}"
        goals[title] = f"Goal sentence {n}: " + "every part of this outcome is spelled out at length, " * 6
        b(repo, "new", "sprint", "--title", title, "--goal", goals[title])
        sp = item(repo, title)["id"]
        b(repo, "new", "bug", "--title", f"Bug {n}", "--sprint", sp, "--severity", "S3",
          "--repro", argstr(is_file("src/c.txt")), "--goal", "c exists", "--touch", "src/**")
        assert b(repo, "answer", sp, "start", "--answer", "approve", "--by", "operator")[0] == 0
        code, out = b(repo, "start", sp)
        assert code == 0, out
    code, out = b(repo, "horizon", "--hook")
    assert code == 0, out
    hook = json.loads(out)
    context = hook["hookSpecificOutput"]["additionalContext"]
    for title, goal in goals.items():
        sp = item(repo, title)["id"]
        assert f"{sp} “{title}”" in context and f"{sp} “{title}”" in hook["systemMessage"], context
        assert goal[:20] not in out
    assert "ship b" not in out and sprint["sp"] in context
    assert len(out) < HOOK_LIMIT, len(out)
    code, out = b(repo, "horizon")  # without --hook: unchanged, goals and critical paths included
    assert code == 0 and all(f"goal {g}" in out for g in goals.values()) and "goal ship b" in out
    assert "critical path" in out


def test_horizon_hook_of_the_repository_backlog_stays_under_the_limit():
    code, out = b(os.path.dirname(TOOLS), "horizon", "--hook")
    assert code == 0, out
    assert len(out) < HOOK_LIMIT, (len(out), out)


def test_horizon_hook_stays_under_the_limit_with_many_sprints_and_a_long_gate(sprint):
    """Six active sprints with long titles and a gate question of 1500 characters: the lines are clipped and the last
    ones give way to a line naming how many were left out, so the hook stays valid JSON under the limit."""
    repo = sprint["repo"]
    ids = []
    for n in range(6):
        title = f"Sprint {n} whose title runs on" + " and on" * 12
        b(repo, "new", "sprint", "--title", title, "--goal", f"goal {n}")
        sp = item(repo, title)["id"]
        ids.append(sp)
        b(repo, "new", "bug", "--title", f"Bug {n}", "--sprint", sp, "--severity", "S3",
          "--repro", argstr(is_file("src/c.txt")), "--goal", "c exists", "--touch", "src/**")
        assert b(repo, "answer", sp, "start", "--answer", "approve", "--by", "operator")[0] == 0
        assert b(repo, "start", sp)[0] == 0
    edit(repo, item(repo, "Bug 0")["id"], gates=[{"id": "G1", "kind": "blocking", "question": "Why? " * 300,
                                                  "recommendation": "fix"}])
    code, out = b(repo, "horizon", "--hook")
    assert code == 0, out
    assert len(out) < HOOK_LIMIT, (len(out), out)
    context = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "Why? " * 30 not in out and "more line(s): python3 _tools/backlog.py horizon" in context, context
    assert context.startswith("sprint SP-") and any(sp in context for sp in ids + [sprint["sp"]]), context
    code, out = b(repo, "horizon")  # without --hook: every sprint and the whole question
    assert code == 0 and all(sp in out for sp in ids) and "Why? " * 300 in out.replace("\n", "")


def holders(sprint):
    """The task claimed by agent-1 holding src/a.txt and docs/*.md, the bug by agent-2 holding src/**, a second task
    (todo, unclaimed) holding src/b/**; the story stays todo, so it holds nothing."""
    repo, tk, bg, st = sprint["repo"], sprint["tk"], sprint["bg"], sprint["st"]
    edit(repo, tk, touches=["src/a.txt", "docs/*.md"])
    b(repo, "new", "task", "--title", "Task two", "--parent", st, "--goal", "b/x written", "--touch", "src/b/**",
      "--check", argstr(is_file("src/b/x.txt")))
    assert b(repo, "claim", tk, "--by", "agent-1")[0] == 0
    assert b(repo, "claim", bg, "--by", "agent-2")[0] == 0
    return item(repo, "Task two")["id"]


def check_held_overlaps(out, code, sprint):
    """What held --overlaps must say for task two: the bug's src/** meets its src/b/**, the task's paths do not."""
    assert code == 1, out
    assert out.splitlines() == [f"src/**  {sprint['bg']} “Bug”  by agent-2  {sprint['sp']} “Sprint”  meets src/b/**"], out


def test_backlog_held_paths_lists_each_claimed_glob_with_claimer_and_sprint(sprint):
    repo, tk, bg, sp = sprint["repo"], sprint["tk"], sprint["bg"], sprint["sp"]
    holders(sprint)
    code, out = b(repo, "held")
    assert code == 0, out
    assert out.splitlines() == [f"docs/*.md  {tk} “Task”  by agent-1  {sp} “Sprint”",
                                f"src/**  {bg} “Bug”  by agent-2  {sp} “Sprint”",
                                f"src/a.txt  {tk} “Task”  by agent-1  {sp} “Sprint”"], out


def test_backlog_held_paths_overlaps_names_the_claimed_items_an_item_would_meet(sprint):
    repo = sprint["repo"]
    tk2 = holders(sprint)
    code, out = b(repo, "held", "--overlaps", tk2)
    check_held_overlaps(out, code, sprint)
    code, out = b(repo, "held", "--overlaps", sprint["tk"])  # its own src/a.txt meets the bug's src/**
    assert code == 1 and out.startswith(f"src/**  {sprint['bg']} “Bug”") and "meets src/a.txt" in out, out
    edit(repo, tk2, touches=["kb/public/x/**"])
    code, out = b(repo, "held", "--overlaps", tk2)
    assert code == 0 and "no claimed item's touches overlap" in out, out
    assert b(repo, "held", "--overlaps", "TK-zzzzzzzz")[0] == 2


def test_backlog_held_paths_planted_failure_of_the_overlap_rule_is_caught(sprint, capsys, monkeypatch):
    """The check is not vacuous: an overlap rule that never finds one (planted) fails it."""
    tk2 = holders(sprint)
    monkeypatch.setattr(bl_view, "touches_overlap", lambda a, b, files: False)  # planted
    code = backlog.main(["--root", str(sprint["repo"]), "held", "--overlaps", tk2])
    with pytest.raises(AssertionError):
        check_held_overlaps(capsys.readouterr().out, code, sprint)


def test_backlog_held_paths_overlap_rule():
    files = ["_tools/backlog.py", "_tools/kbgit.py"]
    assert backlog.touches_overlap("_tools/**", "_tools/x.py", [])  # a glob read as a path
    assert backlog.touches_overlap("_tools/*.py", "_tools/back*", files)  # a tracked file both match
    assert not backlog.touches_overlap("_tools/*.py", "_tools/zz*", files)
    assert not backlog.touches_overlap("kb/_self/a.md", "kb/_self/b.md", files)


def test_backlog_held_paths_ref_reads_the_claims_git_has(sprint):
    """--ref reads the item files as a ref has them: a claim pushed there shows though the files lost it."""
    repo, tk = sprint["repo"], sprint["tk"]
    holders(sprint)
    commit(repo, "claims")
    sh(repo, "git", "update-ref", "refs/remotes/origin/main", "HEAD")
    assert b(repo, "release", tk)[0] == 0
    assert f"{tk} “Task”" not in b(repo, "held")[1]
    code, out = b(repo, "held", "--ref", "origin/main")
    assert code == 0 and f"src/a.txt  {tk} “Task”  by agent-1" in out, out
    code, out = b(repo, "held", "--ref", "no/such/ref")
    assert code == 2 and "held --ref no/such/ref" in out, out


def test_backlog_find_prints_open_matches_with_parent_chain_and_tree_open_hides_finished(sprint):
    """Planted: a done and a dropped item that match are not found and not in tree --open; a miss exits 1 with one
    line; words are case-insensitive and all must match."""
    repo, ep = sprint["repo"], sprint["ep"]
    story = item(repo, "Story")["id"]
    b(repo, "new", "task", "--title", "Rotate BitLocker keys", "--parent", story, "--goal", "keys rotated",
      "--touch", "src/**")
    live = item(repo, "Rotate BitLocker keys")["id"]
    b(repo, "new", "story", "--title", "Old BitLocker report", "--parent", ep, "--goal", "report")
    gone = item(repo, "Old BitLocker report")["id"]
    edit(repo, gone, status="dropped", notes="planted")
    code, out = b(repo, "find", "bitlocker", "ROTATED")
    assert code == 0, out
    lines = out.splitlines()
    assert live in lines[0] and gone not in out, out
    assert f"parent: {story} “Story”" in lines[1] and f"parent: {ep} “Epic”" in lines[2], out
    assert b(repo, "find", "bitlocker", "ROTATED") == (code, out)  # deterministic
    code, out = b(repo, "find", "bitlocker", "report")  # all words must match: only the dropped item has both
    assert code == 1 and len(out.splitlines()) == 1 and gone not in out, out
    assert b(repo, "find", "nonexistentword")[0] == 1
    assert b(repo, "find", " ")[0] == 1
    code, out = b(repo, "tree")
    assert gone in out
    code, out = b(repo, "tree", "--open")
    assert code == 0 and gone not in out and live in out, out
