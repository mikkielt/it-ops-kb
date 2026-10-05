"""The item writers' tests (bl_items.py: new, fmt, claim, release, answer, set, move, reopen, gate, host-check,
fire, drop, referrers and goal), moved whole from test_backlog.py with the writers."""

import os, shutil, subprocess, sys
from pathlib import Path

import pytest

import backlog
import bl_items
import kbgit
import kg_trailers
import bl_testkit
from bl_testkit import argstr, b, commit, edit, is_file, item, item_json, PASS, sh, TOOLS

bl_testkit.bind(backlog)
# the kit's fixtures, bound by name where this module's tests ask for them (an import would shadow the arguments)
repo, sprint, no_git_location, gate_jobs = bl_testkit.repo, bl_testkit.sprint, bl_testkit.no_git_location, bl_testkit.gate_jobs

GATE = ("--question", "Which way?", "--option", "left", "--option", "right", "--recommendation", "left")


ROOT_MD = "---\nroot: public\nid_prefix: S\nvisibility: public\ndescription: test root\n---\n"
SOURCES_HEADER = ("id,url,title,publisher,licence,reuse,retrieved_utc,version_or_date,artifact_sha256,used_in,"
                  "superseded_by\n")
DECIDE_TOOLS = ("kbdecide.py", "check.py", "kbcommon.py", "kbid.py", "kbfacts.py")


def test_new_warns_item_files_only_touches(sprint):
    """BG-2hxjopue planted: a bug whose touches are item files only can never pass done (it needs a KB-Work commit
    that changes another file): new warns and names the drop route, and so does check while it is open; touches that
    also name another file, or a story whose task does, give no warning."""
    repo, sp = sprint["repo"], sprint["sp"]
    code, out = b(repo, "new", "bug", "--title", "Fix an epic's text", "--sprint", sp, "--severity", "S4",
                  "--repro", argstr(is_file("src/z.txt")), "--goal", "z", "--touch", f"{backlog.REL_DIR}/EP-aaaaaaaa.json")
    assert code == 0 and "item files only" in out and "backlog.py drop ID --why" in out, out
    bg = item(repo, "Fix an epic's text")["id"]
    code, out = b(repo, "check")
    assert code == 0 and f"{bg} “Fix an epic's text”: its touches are item files only" in out, out
    edit(repo, bg, touches=[f"{backlog.REL_DIR}/**", "src/z.txt"])
    code, out = b(repo, "check")
    assert "item files only" not in out, out
    code, out = b(repo, "new", "bug", "--title", "Other", "--sprint", sp, "--severity", "S4",
                  "--repro", argstr(is_file("src/y.txt")), "--goal", "y", "--touch", "src/y.txt")
    assert code == 0 and "item files only" not in out, out
    assert backlog.item_files_only([f"{backlog.REL_DIR}/*.json"]) and not backlog.item_files_only([])
    assert not backlog.item_files_only([f"{backlog.REL_DIR}.md"])


def test_new_task_refuses_sprint(repo):
    """new task|subtask --sprint exits 2 naming the rule and writes nothing; a story may still name a sprint."""
    _, out = b(repo, "new", "sprint", "--title", "Sp")
    sp = item(repo, "Sp")["id"]
    _, out = b(repo, "new", "story", "--title", "St", "--goal", "g", "--sprint", sp)
    st = item(repo, "St")["id"]
    before = sorted((Path(repo) / backlog.REL_DIR).glob("*.json"))
    for kind, parent in (("task", st), ("subtask", st)):
        code, out = b(repo, "new", kind, "--title", "Child", "--parent", parent, "--sprint", sp)
        assert code == 2 and "only stories and bugs name a sprint" in out, out
    assert sorted((Path(repo) / backlog.REL_DIR).glob("*.json")) == before, "a refused new writes nothing"
    code, out = b(repo, "new", "task", "--title", "Child", "--parent", st)
    assert code == 0, out


def test_drop_chain_leaves_check_green(sprint):
    """Dropping a three-item chain, dependants first, leaves no dropped item depending on a dropped one: check
    stays at errors=0 (planted: the links stay and check reports a dependency on a dropped item)."""
    repo = sprint["repo"]
    ids = []
    for n in "abc":
        b(repo, "new", "bug", "--title", f"Chain {n}", "--sprint", sprint["sp"], "--severity", "S4", "--repro",
          argstr(is_file("src/y.txt")), "--goal", "y exists", "--touch", "src/**")
        ids.append(item(repo, f"Chain {n}")["id"])
    first, second, third = ids
    edit(repo, second, depends_on=[first])
    edit(repo, third, depends_on=[second, first])
    assert b(repo, "drop", first, "--why", "x")[0] == 1  # still a dependency of open items
    for iid in (third, second, first):
        code, out = b(repo, "drop", iid, "--why", "chain not needed")
        assert code == 0, out
    assert all(item_json(repo, i)["status"] == "dropped" for i in ids)
    assert not any(item_json(repo, i).get("depends_on") for i in ids)
    code, out = b(repo, "check")
    assert code == 0 and "errors=0" in out, out


def test_goal_condition_names_checks_and_scope(sprint):
    code, out = b(sprint["repo"], "goal", sprint["tk"])
    assert f"`{argstr(is_file('src/b.txt'))}` exits 0" in out and "src/**" in out and f"backlog.py done {sprint['tk']}" in out


def test_claim_committed_before_work(sprint, monkeypatch):
    """/kb-item commits the claimed item file on its own right after `claim`, before any work commit: check-trailers
    reads the item as each commit has it, so a work commit made while the claim is uncommitted is refused (planted:
    the claim commit left out) and the same work after a claim commit passes."""
    repo, tk = sprint["repo"], sprint["tk"]
    rel = f"{backlog.REL_DIR}/{tk}.json"
    commit(repo, "plan")
    sh(repo, "git", "update-ref", "refs/remotes/origin/main", "HEAD")
    monkeypatch.setattr(kbgit, "KB", str(repo))
    monkeypatch.setattr(kg_trailers, "KB", str(repo))
    kg_trailers._WANT.clear()

    def only(path, msg):
        sh(repo, "git", "add", "--", path)
        sh(repo, "git", "commit", "-qm", msg, "-m", f"KB-Work: {tk}")

    assert b(repo, "claim", tk, "--by", "agent-1")[0] == 0
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    only("src/b.txt", "write b")  # planted: the claim is still uncommitted
    _, _, bad = kg_trailers.trailer_audit("origin/main..HEAD", quiet=True)
    assert len(bad) == 1 and any("not claimed" in ln for ln in bad[0][1]), bad

    sh(repo, "git", "reset", "-q", "origin/main")  # keeps the claim and the work in the working tree
    kg_trailers._WANT.clear()
    only(rel, "claim")  # the claim commit: a backlog-planning commit
    only("src/b.txt", "write b")
    assert kg_trailers.trailer_audit("origin/main..HEAD", quiet=True)[2] == []


# ------------------------------------------------------------------ set and gate add

def item_text(repo, iid):
    return (Path(repo) / backlog.REL_DIR / f"{iid}.json").read_text(encoding="utf-8")


def refused_unchanged(repo, iid, *args, rule):
    """The command exits 2 with the rule in its message and leaves the item file as it was."""
    before = item_text(repo, iid)
    code, out = b(repo, *args)
    assert code == 2 and rule in out, (code, out)
    assert item_text(repo, iid) == before


def test_backlog_set_changes_each_field_and_check_passes(sprint):
    repo, tk, bg = sprint["repo"], sprint["tk"], sprint["bg"]
    code, out = b(repo, "set", tk, "--notes", "why", "--link", "pipeline 1", "--touch", "src/a.txt", "--touch", "kb/x/**",
                  "--check", argstr(is_file("src/b.txt")), "--depends", bg, "--relates", sprint["st"], "--priority", "P1", "--rank", "3")
    assert code == 0 and "set " in out, out
    it = item_json(repo, tk)
    assert it["notes"] == "why" and it["links"] == ["pipeline 1"] and it["touches"] == ["src/a.txt", "kb/x/**"]
    assert it["checks"] == [{"run": is_file("src/b.txt")}] and it["depends_on"] == [bg] and it["relates_to"] == [sprint["st"]]
    assert it["priority"] == "P1" and it["rank"] == 3
    code, out = b(repo, "check")
    assert code == 0 and "errors=0" in out, out


def test_backlog_set_moves_a_draft_story_to_another_sprint(repo):
    b(repo, "new", "sprint", "--title", "One", "--goal", "g")
    b(repo, "new", "sprint", "--title", "Two", "--goal", "g")
    one, two = item(repo, "One")["id"], item(repo, "Two")["id"]
    b(repo, "new", "story", "--title", "S", "--sprint", one, "--goal", "g", "--check", argstr(is_file("src/b.txt")))
    st = item(repo, "S")["id"]
    assert b(repo, "set", st, "--sprint", two)[0] == 0
    assert item_json(repo, st)["sprint"] == two
    assert b(repo, "set", st, "--clear", "sprint")[0] == 0
    assert "sprint" not in item_json(repo, st)
    assert b(repo, "check")[0] == 0


def test_backlog_set_second_run_changes_nothing(sprint):
    repo, tk = sprint["repo"], sprint["tk"]
    args = ("set", tk, "--notes", "why", "--link", "a", "--touch", "src/**", "--priority", "P3")
    assert b(repo, *args)[0] == 0
    after = item_text(repo, tk)
    code, out = b(repo, *args)
    assert code == 0 and "unchanged" in out and item_text(repo, tk) == after
    add = ("set", tk, "--add", "--link", "b", "--link", "a", "--notes", "more", "--touch", "kb/y/**")
    assert b(repo, *add)[0] == 0
    it = item_json(repo, tk)
    assert it["links"] == ["a", "b"] and it["notes"] == "why more" and it["touches"] == ["src/**", "kb/y/**"]
    after = item_text(repo, tk)
    code, out = b(repo, *add)
    assert code == 0 and "unchanged" in out and item_text(repo, tk) == after


def test_backlog_set_add_keeps_existing_checks(sprint):
    repo, tk = sprint["repo"], sprint["tk"]
    assert b(repo, "set", tk, "--add", "--check", argstr(PASS))[0] == 0
    assert item_json(repo, tk)["checks"] == [{"run": is_file("src/b.txt")}, {"run": PASS}]
    assert b(repo, "set", tk, "--check", argstr(PASS))[0] == 0  # without --add the list is replaced
    assert item_json(repo, tk)["checks"] == [{"run": PASS}]


@pytest.mark.parametrize("flag, value, rule", [
    ("--status", "done", "set refuses status"),
    ("--claimed-by", "me", "set refuses claimed_by"),
    ("--evidence", "x", "set refuses evidence"),
    ("--id", "TK-aaaaaaaa", "set refuses id"),
    ("--kind", "bug", "set refuses kind"),
    ("--gates", "[]", "set refuses gates"),
])
def test_backlog_set_refuses_status_claim_evidence_and_identity(sprint, flag, value, rule):
    refused_unchanged(sprint["repo"], sprint["tk"], "set", sprint["tk"], flag, value, rule=rule)


@pytest.mark.parametrize("field, rule", [
    ("status", "changes only through claim, release, start, close, drop and done"),
    ("claimed_by", "changes only through claim and release"),
    ("evidence", "is written only by done"),
    ("title", "would make `check` fail"),  # set replaces a title, and check needs one
    ("goal", "would make `check` fail"),
    ("repro", "only a bug has a repro"),
])
def test_backlog_set_clear_refuses_the_same_fields(sprint, field, rule):
    refused_unchanged(sprint["repo"], sprint["tk"], "set", sprint["tk"], "--clear", field, rule=rule)


def test_claim_refuses_a_shared_checkout(sprint, tmp_path, monkeypatch):
    """ST-ov6h4gbx planted (SP-tpulmoxh, SP-xdzgepun), with BG-g6zpyfgr: session s1 claims a task; session s2's claim
    of the bug in the same checkout is refused (exit 1), writes nothing and records nothing in the tree; in a worktree
    of it the same claim succeeds; once s1 releases, the shared checkout takes s2. One session (an orchestrator)
    claims for several names in its checkout, and with no session id set the claimer's name stands for it."""
    repo, tk, bg = sprint["repo"], sprint["tk"], sprint["bg"]
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s1")
    assert b(repo, "claim", tk, "--by", "one")[0] == 0
    before = item_text(repo, bg)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s2")
    code, out = b(repo, "claim", bg, "--by", "two")
    assert code == 1 and "another session (one) works in this checkout" in out and tk in out, out
    status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=repo, capture_output=True,
                            text=True, check=True).stdout
    assert item_text(repo, bg) == before and "claims" not in status, status  # the record lives in the git dir
    commit(repo, "one's claim")
    wt = tmp_path / "wt"
    sh(repo, "git", "worktree", "add", "-q", "--detach", str(wt))
    code, out = b(wt, "claim", bg, "--by", "two")
    assert code == 0, out
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s1")
    assert b(repo, "claim", tk, "--by", "one")[0] == 0  # the same session again: no refusal
    assert b(repo, "release", tk)[0] == 0
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s2")
    code, out = b(repo, "claim", bg, "--by", "two")
    assert code == 0, out


def test_claim_lets_one_session_claim_for_its_subagents(sprint, monkeypatch):
    """BG-g6zpyfgr planted: kb-sprint's orchestrator claims the task for worker-a and the bug for worker-b in its own
    checkout, one session: both pass. With no session id the names stand for sessions: the second is refused."""
    repo, tk, bg = sprint["repo"], sprint["tk"], sprint["bg"]
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "orchestrator")
    assert b(repo, "claim", tk, "--by", "worker-a")[0] == 0
    code, out = b(repo, "claim", bg, "--by", "worker-b")
    assert code == 0, out
    assert b(repo, "release", bg)[0] == 0 and b(repo, "release", tk)[0] == 0
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    assert b(repo, "claim", tk, "--by", "worker-a")[0] == 0
    code, out = b(repo, "claim", bg, "--by", "worker-b")
    assert code == 1 and "another session (worker-a)" in out, out


def test_goal_prints_ancestor_gates(sprint):
    """ST-73c5rhb5 planted (SP-fvztfmtm's TK-ymbmdww4): goal prints, under the task's condition, each answered gate
    of its parent story with its question, answer and who gave it; an unanswered gate is not printed, and a task with
    no answered gate above it prints its condition alone."""
    repo, st, tk = sprint["repo"], sprint["st"], sprint["tk"]
    code, out = b(repo, "goal", tk)
    assert code == 0 and "answered gates above it" not in out, out
    assert b(repo, "gate", "add", st, "--question", "Shared counts or per-row keys?", "--option", "shared",
             "--option", "per-row", "--recommendation", "shared", "--kind", "provisional")[0] == 0
    assert b(repo, "gate", "add", st, "--question", "Still open?", "--option", "a", "--option", "b",
             "--recommendation", "a", "--kind", "provisional")[0] == 0
    code, out = b(repo, "answer", st, "g1", "--answer", "shared", "--by", "operator")
    assert code == 0, out
    code, out = b(repo, "goal", tk)
    assert code == 0 and "answered gates above it" in out, out
    assert f"{st} “Story” g1: Shared counts or per-row keys? -> shared (by operator)" in out, out
    assert "Still open?" not in out, out


def test_set_replaces_goal_and_repro(sprint):
    """ST-3tgtrzd3 planted: set replaces a task's title, goal and parent and a bug's repro, repro_reason and
    severity; a repro that passes now, repro or severity on a task, an unknown parent, and goal or repro on a done
    item are refused with the item unchanged."""
    repo, tk, bg = sprint["repo"], sprint["tk"], sprint["bg"]
    assert b(repo, "new", "story", "--title", "Other story", "--sprint", sprint["sp"], "--goal", "o")[0] == 0
    other = item(repo, "Other story")["id"]
    for args in (["--title", "Renamed"], ["--goal", "new goal"], ["--parent", other]):
        code, out = b(repo, "set", tk, *args)
        assert code == 0, (args, out)
    it = item_json(repo, tk)
    assert (it["title"], it["goal"], it["parent"]) == ("Renamed", "new goal", other), it
    code, out = b(repo, "set", bg, "--repro", argstr(is_file("src/never.txt")), "--severity", "S2")
    assert code == 0, out
    it = item_json(repo, bg)
    assert it["repro"] == {"run": is_file("src/never.txt")} and it["severity"] == "S2", it
    assert b(repo, "set", bg, "--repro-reason", "only a text match is possible")[0] == 0
    assert item_json(repo, bg)["repro_reason"] == "only a text match is possible"
    before = item_text(repo, bg)
    code, out = b(repo, "set", bg, "--repro", argstr(PASS))
    assert code == 1 and "passes now" in out and item_text(repo, bg) == before, out  # exit 1, as new bug refuses it
    refused_unchanged(repo, tk, "set", tk, "--severity", "S1", rule="only a bug has a repro")
    refused_unchanged(repo, tk, "set", tk, "--parent", "ST-zzzzzzzz", rule="no such item")
    edit(repo, tk, status="done")
    for args in (["--goal", "late"], ["--repro", argstr(is_file("src/x.txt"))]):
        refused_unchanged(repo, tk, "set", tk, *args, rule="it is done")


def test_backlog_set_refuses_nothing_to_change_and_a_value_with_its_clear(sprint):
    repo, tk = sprint["repo"], sprint["tk"]
    refused_unchanged(repo, tk, "set", tk, rule="nothing to change")
    refused_unchanged(repo, tk, "set", tk, "--notes", "x", "--clear", "notes", rule="given a value and --clear")


@pytest.mark.parametrize("args, rule", [
    (["--priority", "P9"], "priority must be one of"),
    (["--notes", " "], "notes empty or longer than TEXT_MAX"),
    (["--notes", "x" * 2001], "notes empty or longer than TEXT_MAX"),
    (["--link", ""], "links must be a list of texts"),
    (["--depends", "TK-zzzzzzzz"], "depends_on names TK-zzzzzzzz, which does not exist"),
    (["--relates", "TK-zzzzzzzz"], "relates_to names TK-zzzzzzzz, which does not exist"),
    (["--sprint", "SP-zzzzzzzz"], "only stories and bugs name a sprint"),
    (["--check", ""], "checks must be a list of"),
    (["--clear", "touches"], "touches missing"),
    (["--clear", "priority"], "priority must be one of"),
    (["--clear", "checks"], "checks missing"),
    (["--touch", "src/**", "--clear", "touches"], "given a value and --clear"),
])
def test_backlog_set_refuses_what_check_would_flag(sprint, args, rule):
    refused_unchanged(sprint["repo"], sprint["tk"], "set", sprint["tk"], *args, rule=rule)


def test_backlog_set_refuses_a_check_that_is_not_a_command_line(sprint):
    refused_unchanged(sprint["repo"], sprint["tk"], "set", sprint["tk"], "--check", "python3 -c 'unclosed",
                      rule="not a command line")


def test_backlog_set_refuses_itself_and_a_dependency_cycle(sprint):
    repo, tk, bg = sprint["repo"], sprint["tk"], sprint["bg"]
    refused_unchanged(repo, tk, "set", tk, "--depends", tk, rule="names the item itself")
    assert b(repo, "set", bg, "--depends", tk)[0] == 0
    refused_unchanged(repo, tk, "set", tk, "--depends", bg, rule="cycle")


def test_backlog_set_refuses_a_missing_sprint_of_a_story_and_a_draft_item_in_an_active_sprint(sprint):
    repo, st = sprint["repo"], sprint["st"]
    refused_unchanged(repo, st, "set", st, "--sprint", "SP-zzzzzzzz", rule="sprint SP-zzzzzzzz does not exist")
    b(repo, "new", "story", "--title", "Loose", "--goal", "g", "--check", argstr(PASS))
    loose = item(repo, "Loose")["id"]
    refused_unchanged(repo, loose, "set", loose, "--sprint", sprint["sp"], rule="would never be ready")


def test_backlog_set_refuses_moving_the_review_story_out_of_its_sprint(sprint):
    repo, rv = sprint["repo"], sprint["rv"]
    b(repo, "new", "sprint", "--title", "Other", "--goal", "g")
    refused_unchanged(repo, rv, "set", rv, "--sprint", item(repo, "Other")["id"], rule="exactly one review story")


def test_backlog_set_refuses_a_sprint_except_notes_and_links(sprint):
    repo, sp = sprint["repo"], sprint["sp"]
    refused_unchanged(repo, sp, "set", sp, "--priority", "P1", rule="a sprint takes notes, links and delegates only")
    assert b(repo, "set", sp, "--notes", "n", "--link", "l")[0] == 0


def test_backlog_set_refuses_checks_and_touches_of_a_done_item(sprint):
    repo, tk = sprint["repo"], sprint["tk"]
    edit(repo, tk, status="done", evidence={"commit": "abc", "checks": []})
    refused_unchanged(repo, tk, "set", tk, "--check", argstr(PASS), rule="its evidence proves")
    refused_unchanged(repo, tk, "set", tk, "--clear", "touches", rule="its evidence proves")
    assert b(repo, "set", tk, "--notes", "after")[0] == 0


def test_backlog_set_refuses_a_name_of_this_host_in_notes(sprint, monkeypatch):
    monkeypatch.setenv("COMPUTERNAME", "ZyxwvuHost")
    refused_unchanged(sprint["repo"], sprint["tk"], "set", sprint["tk"], "--notes", "built on zyxwvuhost",
                      rule="holds a piece of this host's computer name")


def test_backlog_set_unknown_id_exits_2(sprint):
    code, out = b(sprint["repo"], "set", "TK-zzzzzzzz", "--notes", "x")
    assert code == 2 and "no item TK-zzzzzzzz" in out


def test_backlog_set_check_flags_malformed_links(sprint):
    repo, tk = sprint["repo"], sprint["tk"]
    edit(repo, tk, links="pipeline 1")  # planted: a string, not a list
    code, out = b(repo, "check")
    assert code == 1 and "links must be a list of texts" in out, out


def test_backlog_set_gate_add_blocks_until_answered(sprint):
    repo, tk = sprint["repo"], sprint["tk"]
    code, out = b(repo, "gate", "add", tk, *GATE)
    assert code == 0 and "g1 (blocking) added" in out, out
    assert item_json(repo, tk)["gates"] == [{"id": "g1", "kind": "blocking", "question": "Which way?",
                                              "options": ["left", "right"], "recommendation": "left",
                                              "class": "design"}]
    assert b(repo, "check")[0] == 0
    assert "waits on" in b(repo, "show", tk)[1]
    assert b(repo, "answer", tk, "g1", "--answer", "left", "--by", "operator")[0] == 0
    assert b(repo, "gate", "add", tk, "--question", "Second?", "--option", "a", "--option", "b",
             "--recommendation", "b", "--kind", "provisional")[0] == 0
    assert [g["id"] for g in item_json(repo, tk)["gates"]] == ["g1", "g2"]
    assert b(repo, "answer", tk, "g2", "--provisional")[0] == 0


def test_backlog_set_gate_add_second_run_changes_nothing(sprint):
    repo, tk = sprint["repo"], sprint["tk"]
    assert b(repo, "gate", "add", tk, *GATE, "--id", "way")[0] == 0
    assert b(repo, "answer", tk, "way", "--answer", "right", "--by", "operator")[0] == 0
    after = item_text(repo, tk)
    for extra in ((), ("--id", "way")):  # an answered gate is not reopened or duplicated
        code, out = b(repo, "gate", "add", tk, *GATE, *extra)
        assert code == 0 and "unchanged" in out and item_text(repo, tk) == after, out


@pytest.mark.parametrize("args, rule", [
    (["--question", "Which way?", "--option", "up", "--option", "down", "--recommendation", "up"],
     "refuses a different gate with the question or id of gate way"),
    (["--question", "Other?", "--option", "left", "--option", "right", "--recommendation", "left", "--id", "way"],
     "refuses a different gate with the question or id of gate way"),
    (list(GATE) + ["--id", "other"], "refuses a different gate with the question or id of gate way"),
    (["--question", "Q?", "--option", "a", "--recommendation", "a"], "--option twice or more"),
    (["--question", "Q?", "--option", "a", "--option", "a", "--recommendation", "a"], "each different"),
    (["--question", "Q?", "--option", "a", "--option", "b", "--recommendation", "c"], "must be one of the --option"),
    (["--question", "Q?", "--option", "a", "--option", "b", "--recommendation", "a", "--id", "start"], "not 'start'"),
    (["--question", "Q?", "--option", "a", "--option", "b", "--recommendation", "a", "--id", "Bad Id"],
     "lowercase letters, digits and hyphens"),
    (["--question", "Q?", "--option", "a", "--option", "b", "--recommendation", "a", "--kind", "maybe"],
     "a gate needs id, kind"),
    (["--question", " ", "--option", "a", "--option", "b", "--recommendation", "a"], "a gate needs id, kind"),
])
def test_backlog_set_gate_add_refuses(sprint, args, rule):
    repo, tk = sprint["repo"], sprint["tk"]
    assert b(repo, "gate", "add", tk, *GATE, "--id", "way")[0] == 0
    refused_unchanged(repo, tk, "gate", "add", tk, *args, rule=rule)


@pytest.mark.parametrize("options", [
    ("fold into maintaining.md", "drop a row"),  # no measured size
    ("fold into maintaining.md: 3990 bytes", "drop a row"),  # one option without
])
def test_gate_size_cap_measured_refuses_an_option_without_a_size(sprint, options):
    repo, tk = sprint["repo"], sprint["tk"]
    args = ["--question", "How does AGENTS.md stay under its cap?", "--recommendation", options[0]]
    for o in options:
        args += ["--option", o]
    code, out = b(repo, "gate", "add", tk, *args)
    assert code == 2 and "each --option states the file's measured size" in out, out
    assert "gates" not in item_json(repo, tk)


def test_gate_size_cap_measured_accepts_sizes_and_leaves_other_gates_alone(sprint):
    repo, tk = sprint["repo"], sprint["tk"]
    args = ["--question", "How does AGENTS.md stay under its cap?", "--option", "fold: 4001 bytes",
            "--option", "drop a row: 4,090 bytes", "--recommendation", "fold: 4001 bytes"]
    assert b(repo, "gate", "add", tk, *args)[0] == 0
    assert b(repo, "gate", "add", tk, "--question", "Name of the flag in AGENTS.md?", "--option", "a",
             "--option", "b", "--recommendation", "a")[0] == 0  # names the file, not a cap


def test_backlog_set_gate_add_refuses_a_done_item_and_an_unknown_one(sprint):
    repo, tk = sprint["repo"], sprint["tk"]
    edit(repo, tk, status="done", evidence={"commit": "abc", "checks": []})
    refused_unchanged(repo, tk, "gate", "add", tk, *GATE, rule="it is done")
    code, out = b(repo, "gate", "add", "TK-zzzzzzzz", *GATE)
    assert code == 2 and "no item TK-zzzzzzzz" in out


@pytest.fixture
def decide(sprint):
    """The started sprint's repository with a copy of the decision tools, a minimal public root and kb/_self's decision
    files, so `answer --record` writes into the copy and never into this repository."""
    repo = sprint["repo"]
    (repo / "_tools").mkdir()
    for name in DECIDE_TOOLS:
        shutil.copy(os.path.join(TOOLS, name), repo / "_tools" / name)
    pub = repo / "kb" / "public"
    pub.mkdir(parents=True)
    for rel, text in (("_root.md", ROOT_MD), ("_sources.csv", SOURCES_HEADER), ("_artifacts.csv", "path,source_id,sha256\n"),
                      ("_answers.md", "# Answers\n"), ("_gaps.md", "# Gaps\n"), ("_conflicts.md", "# Conflicts\n")):
        (pub / rel).write_text(text, encoding="utf-8", newline="\n")
    kb_self = repo / "kb" / "_self"
    kb_self.mkdir(exist_ok=True)
    (kb_self / "_decisions.csv").write_text(
        "id,text,by,by_ref,source,date,context,status,invalidated_reason,invalidated_date,supersedes,review_by,links\n",
        encoding="utf-8", newline="\n")
    (kb_self / "decision-makers.csv").write_text("id,role,name,source\noperator,operator,,the operator answers a gate\n",
                                                 encoding="utf-8", newline="\n")
    (repo / ".gitignore").write_text("__pycache__/\n", encoding="utf-8", newline="\n")
    edit(repo, sprint["bg"], gates=[{"id": "way", "kind": "blocking", "question": "Which way?",
                                      "options": ["left", "right"], "recommendation": "left"}])
    commit(repo, "decision tools")
    return sprint


def decisions(repo):
    import csv
    with open(Path(repo) / "kb" / "_self" / "_decisions.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def tool_run(repo, tool, *args):
    p = subprocess.run([sys.executable, str(Path(repo) / "_tools" / tool), *args], cwd=repo, capture_output=True,
                       text=True, encoding="utf-8")
    return p.returncode, p.stdout + p.stderr


def test_backlog_answer_record_writes_an_active_decision_of_the_item(decide):
    repo, bg = decide["repo"], decide["bg"]
    code, out = b(repo, "answer", bg, "way", "--answer", "left", "--by", "operator", "--record")
    assert code == 0, out
    assert item_json(repo, bg)["gates"][0]["answer"] == "left"
    (row,) = decisions(repo)
    assert (row["status"], row["text"], row["context"]) == ("active", "left", f"item:{bg}")
    assert (row["by"], row["by_ref"]) == ("operator", "operator")
    assert f"{bg} gate way" in row["source"]
    code, out = tool_run(repo, "kbdecide.py", "list", "--root", "_self", "--context", f"item:{bg}")
    assert code == 0 and row["id"] in out
    code, out = tool_run(repo, "check.py")
    assert code == 0, out


def test_backlog_answer_record_second_gate_same_text(decide):
    """Two gates of one item answered with the same text are two decisions, and the second answer is saved; the same
    gate answered alike again is still the same decision (refused)."""
    repo, bg = decide["repo"], decide["bg"]
    code, out = b(repo, "gate", "add", bg, "--question", "Which side?", "--option", "left", "--option", "right",
                  "--recommendation", "left", "--id", "side")
    assert code == 0, out
    commit(repo, "second gate")
    assert b(repo, "answer", bg, "way", "--answer", "left", "--by", "operator", "--record")[0] == 0
    code, out = b(repo, "answer", bg, "side", "--answer", "left", "--by", "operator", "--record")
    assert code == 0, out
    assert [g.get("answer") for g in item_json(repo, bg)["gates"]] == ["left", "left"]
    rows = decisions(repo)
    assert len(rows) == 2 and len({r["id"] for r in rows}) == 2, rows  # planted failure: one id means the gate is not in it
    assert [r["text"] for r in rows] == ["left", "left"] and {r["context"] for r in rows} == {f"item:{bg}"}
    assert [f"gate {g}" in r["source"] for g, r in zip(("way", "side"), rows)] == [True, True]
    code, out = tool_run(repo, "check.py")
    assert code == 0, out


def test_backlog_answer_record_without_record_writes_no_decision(decide):
    repo, bg = decide["repo"], decide["bg"]
    assert b(repo, "answer", bg, "way", "--answer", "left", "--by", "operator")[0] == 0
    assert decisions(repo) == []


@pytest.mark.parametrize("args", [
    ("--provisional",),
    ("--confirm",),
    ("--answer", "left", "--by", "agent"),
    ("--answer", "left"),
    ("--by", "operator"),
])
def test_backlog_answer_record_refuses_what_is_not_the_operators_answer(decide, args):
    repo, bg = decide["repo"], decide["bg"]
    before = item_text(repo, bg)
    code, out = b(repo, "answer", bg, "way", *args, "--record")
    assert code == 2 and "--record" in out, out
    assert decisions(repo) == [] and item_text(repo, bg) == before


def test_backlog_answer_record_leaves_the_gate_open_when_kbdecide_refuses(decide):
    """A decision kbdecide refuses (here a maker the register lacks) leaves the gate unanswered and no row behind."""
    repo, bg = decide["repo"], decide["bg"]
    (Path(repo) / "kb" / "_self" / "decision-makers.csv").write_text("id,role,name,source\n", encoding="utf-8", newline="\n")
    before = item_text(repo, bg)
    code, out = b(repo, "answer", bg, "way", "--answer", "left", "--by", "operator", "--record")
    assert code == 1 and "no decision maker 'operator'" in out, out
    assert decisions(repo) == [] and item_text(repo, bg) == before


def test_backlog_answer_record_decision_stays_active_after_close_and_sweep(decide):
    repo, tk, st, bg, rv, ep, sp = (decide[k] for k in ("repo", "tk", "st", "bg", "rv", "ep", "sp"))
    assert b(repo, "answer", bg, "way", "--answer", "left", "--by", "operator", "--record")[0] == 0  # commits its own files
    (repo / "src" / "b.txt").write_text("b\n", encoding="utf-8")
    (repo / "src" / "c.txt").write_text("c\n", encoding="utf-8")
    commit(repo, "b and c", f"{tk}, {bg}")
    for iid in (tk, st, bg):
        code, out = b(repo, "done", iid)
        assert code == 0, out
    edit(repo, rv, checks=[{"run": PASS}])
    commit(repo, "state")
    assert b(repo, "done", rv)[0] == 0
    assert b(repo, "done", ep)[0] == 0
    commit(repo, "done")
    code, out = b(repo, "close", sp)
    assert code == 0, out
    assert not (Path(repo) / backlog.REL_DIR / f"{bg}.json").exists()
    assert [r["status"] for r in decisions(repo)] == ["active"]
    code, out = tool_run(repo, "kbdecide.py", "sweep", "--root", "_self")
    assert code == 0, out
    assert [r["status"] for r in decisions(repo)] == ["active"]


# ------------------------------------------------------------------ move and reopen

@pytest.fixture
def planned(sprint):
    """The started sprint's story with its task, plus a second sprint still planned."""
    repo = sprint["repo"]
    assert b(repo, "new", "sprint", "--title", "Later", "--goal", "g")[0] == 0
    return {**sprint, "later": item(repo, "Later")["id"]}


def statuses(repo, *ids):
    return [item_json(repo, i)["status"] for i in ids]


def test_backlog_move_to_a_planned_sprint_writes_draft_and_the_tasks_follow(planned):
    repo, st, tk, later = planned["repo"], planned["st"], planned["tk"], planned["later"]
    assert statuses(repo, st, tk) == ["todo", "todo"]
    code, out = b(repo, "move", st, "--sprint", later)
    assert code == 0 and "status draft" in out and "1 task" in out, out
    assert item_json(repo, st)["sprint"] == later and statuses(repo, st, tk) == ["draft", "draft"]
    assert b(repo, "check")[0] == 0


def test_backlog_move_to_an_active_sprint_writes_todo_and_the_tasks_follow(planned):
    repo, st, tk, later, sp = planned["repo"], planned["st"], planned["tk"], planned["later"], planned["sp"]
    assert b(repo, "move", st, "--sprint", later)[0] == 0
    code, out = b(repo, "move", st, "--sprint", sp)
    assert code == 0 and "status todo" in out, out
    assert item_json(repo, st)["sprint"] == sp and statuses(repo, st, tk) == ["todo", "todo"]
    assert b(repo, "check")[0] == 0


def test_backlog_move_none_removes_the_sprint_and_writes_draft(planned):
    repo, st, tk = planned["repo"], planned["st"], planned["tk"]
    code, out = b(repo, "move", st, "--sprint", "none")
    assert code == 0, out
    assert "sprint" not in item_json(repo, st) and statuses(repo, st, tk) == ["draft", "draft"]
    assert b(repo, "check")[0] == 0


def test_backlog_move_second_run_changes_nothing(planned):
    repo, st, later = planned["repo"], planned["st"], planned["later"]
    for target in (later, "none"):
        assert b(repo, "move", st, "--sprint", target)[0] == 0
        files = {i: item_text(repo, i) for i in (st, planned["tk"])}
        code, out = b(repo, "move", st, "--sprint", target)
        assert code == 0 and "unchanged" in out, out
        assert {i: item_text(repo, i) for i in files} == files


def test_backlog_move_refuses_what_a_sprint_cannot_hold(planned):
    repo, st, tk, rv, sp, later = (planned[k] for k in ("repo", "st", "tk", "rv", "sp", "later"))
    refused_unchanged(repo, tk, "move", tk, "--sprint", later, rule="only a story or a bug names a sprint")
    refused_unchanged(repo, later, "move", later, "--sprint", sp, rule="only a story or a bug names a sprint")
    refused_unchanged(repo, rv, "move", rv, "--sprint", later, rule="exactly one review story")
    refused_unchanged(repo, st, "move", st, "--sprint", "SP-zzzzzzzz", rule="does not exist")
    refused_unchanged(repo, st, "move", st, "--sprint", planned["ep"], rule="is not a sprint")


def test_backlog_move_refuses_a_claimed_item_and_one_with_a_claimed_task(planned):
    repo, st, tk, later = planned["repo"], planned["st"], planned["tk"], planned["later"]
    assert b(repo, "claim", tk, "--by", "me")[0] == 0
    refused_unchanged(repo, st, "move", st, "--sprint", later, rule="is doing (claimed)")
    assert b(repo, "release", tk)[0] == 0
    edit(repo, st, status="doing", claimed_by="me")
    refused_unchanged(repo, st, "move", st, "--sprint", later, rule="is doing (claimed)")


def test_backlog_move_refuses_a_done_and_a_dropped_item(planned):
    repo, bg, later = planned["repo"], planned["bg"], planned["later"]
    edit(repo, bg, status="done", evidence={"commit": "abc", "checks": []})
    refused_unchanged(repo, bg, "move", bg, "--sprint", later, rule="reopen it first")
    edit(repo, bg, status="dropped")
    refused_unchanged(repo, bg, "move", bg, "--sprint", later, rule="it is dropped")


def test_backlog_move_refuses_an_item_without_touches_into_an_active_sprint(planned):
    repo, sp = planned["repo"], planned["sp"]
    assert b(repo, "new", "story", "--title", "Bare", "--goal", "g", "--check", argstr(PASS))[0] == 0
    bare = item(repo, "Bare")["id"]
    refused_unchanged(repo, bare, "move", bare, "--sprint", sp, rule="has no touches")
    assert b(repo, "move", bare, "--sprint", planned["later"])[0] == 0  # a planned sprint takes it as a draft


def test_backlog_move_refuses_what_check_would_flag_and_writes_no_task(planned):
    repo, st, tk, later = planned["repo"], planned["st"], planned["tk"], planned["later"]
    assert b(repo, "new", "task", "--title", "Second", "--parent", st, "--goal", "g", "--touch", "src/**",
             "--check", argstr(PASS))[0] == 0
    second = item(repo, "Second")["id"]
    edit(repo, tk, status="done", evidence={"commit": "abc", "checks": []})  # planted: done cannot sit in a planned sprint
    before = item_text(repo, second)
    refused_unchanged(repo, st, "move", st, "--sprint", later, rule="while its sprint")
    assert item_text(repo, second) == before and statuses(repo, second) == ["todo"]


def test_backlog_move_requires_a_sprint_argument(planned):
    code, out = b(planned["repo"], "move", planned["st"])
    assert code == 2 and "--sprint" in out, out


def test_backlog_move_unknown_id_exits_2(planned):
    code, out = b(planned["repo"], "move", "ST-zzzzzzzz", "--sprint", "none")
    assert code == 2 and "no item" in out, out


def test_backlog_move_reopen_clears_evidence_and_claim_and_sets_todo(planned):
    repo, bg = planned["repo"], planned["bg"]
    edit(repo, bg, status="done", evidence={"commit": "abc", "checks": []}, claimed_by="me")
    before = item_text(repo, bg)
    code, out = b(repo, "reopen", bg, "--why", "the fix regressed")
    assert code == 0 and "the fix regressed" in out, out
    it = item_json(repo, bg)
    assert it["status"] == "todo" and "evidence" not in it and "claimed_by" not in it
    assert "regressed" not in item_text(repo, bg) and item_text(repo, bg) != before
    assert b(repo, "check")[0] == 0


def test_backlog_move_reopen_in_a_planned_sprint_writes_draft(planned):
    repo, st, later = planned["repo"], planned["st"], planned["later"]
    assert b(repo, "move", st, "--sprint", later)[0] == 0
    edit(repo, st, status="done", evidence={"commit": "abc", "checks": []})
    assert b(repo, "reopen", st, "--why", "again")[0] == 0
    assert item_json(repo, st)["status"] == "draft"


def test_backlog_move_reopen_second_run_is_refused_and_changes_nothing(planned):
    repo, bg = planned["repo"], planned["bg"]
    edit(repo, bg, status="done", evidence={"commit": "abc", "checks": []})
    assert b(repo, "reopen", bg, "--why", "x")[0] == 0
    refused_unchanged(repo, bg, "reopen", bg, "--why", "x", rule="reopen takes only a done item")


@pytest.mark.parametrize("status", ["draft", "todo", "doing", "dropped"])
def test_backlog_move_reopen_refuses_every_status_but_done(planned, status):
    repo, bg = planned["repo"], planned["bg"]
    edit(repo, bg, status=status, **({"claimed_by": "me"} if status == "doing" else {}))
    refused_unchanged(repo, bg, "reopen", bg, "--why", "x", rule=f"it is {status}")


def test_backlog_move_reopen_refuses_a_missing_or_blank_reason_and_a_sprint(planned):
    repo, bg, sp = planned["repo"], planned["bg"], planned["sp"]
    edit(repo, bg, status="done", evidence={"commit": "abc", "checks": []})
    code, out = b(repo, "reopen", bg)
    assert code == 2 and "--why" in out, out
    refused_unchanged(repo, bg, "reopen", bg, "--why", "  ", rule="must not be empty")
    refused_unchanged(repo, sp, "reopen", sp, "--why", "x", rule="a sprint has no done status")
    code, out = b(repo, "reopen", "ST-zzzzzzzz", "--why", "x")
    assert code == 2 and "no item" in out, out


def referrer_repo(sprint):
    repo = Path(sprint["repo"])
    for rel, text in {"lib/mod.py": "def helper_fn():\n    pass\n", "lib/user.py": "import mod\nmod.helper_fn()\n",
                      "docs/n.md": "see lib/mod.py and `helper_fn`\nhelper_fn_other is another\n",
                      "src/t.txt": "lib/mod.py\n", "docs/none.md": "nothing\n"}.items():
        (repo / rel).parent.mkdir(exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8", newline="\n")
    commit(repo, "files")
    return repo


def test_backlog_referrers_lists_each_file_that_names_a_moved_file_or_symbol(sprint):
    repo = referrer_repo(sprint)
    code, out = b(repo, "referrers", "lib/mod.py", "helper_fn", "no_such_symbol")
    assert code == 0, out
    assert out.splitlines() == ["lib/mod.py  docs/n.md:1  1 line", "lib/mod.py  lib/user.py:1  1 line",
                                "lib/mod.py  src/t.txt:1  1 line",
                                "helper_fn  docs/n.md:1  1 line", "helper_fn  lib/mod.py:1  1 line",
                                "helper_fn  lib/user.py:2  1 line",
                                "no_such_symbol  no tracked file names it"], out


def test_backlog_referrers_item_marks_the_files_outside_its_touches(sprint):
    repo = referrer_repo(sprint)
    code, out = b(repo, "referrers", "lib/mod.py", "--item", sprint["tk"])  # the task's touches are src/**
    assert code == 1, out
    assert "lib/mod.py  src/t.txt:1  1 line\n" in out + "\n" and "src/t.txt:1  1 line  outside" not in out, out
    assert "docs/n.md:1  1 line  outside touches" in out and "lib/user.py:1  1 line  outside touches" in out, out
    edit(repo, sprint["tk"], touches=["src/**", "docs/n.md", "lib/user.py"])
    code, out = b(repo, "referrers", "lib/mod.py", "--item", sprint["tk"])
    assert code == 0 and "outside" not in out, out
    assert b(repo, "referrers", "x", "--item", "TK-zzzzzzzz")[0] == 2


def test_backlog_referrers_ignores_item_files_and_matches_doc_names(sprint):
    """BG-ncpteupy planted: an item file naming the moved file and prose that only says the module's word are no
    referrers; an import line and <stem>.py are. A moved doc is found by its file name, word-bounded, too."""
    repo = referrer_repo(sprint)
    edit(repo, sprint["tk"], touches=["src/**", "lib/mod.py"], notes="the mod word, and mod.py")
    for rel, text in {"docs/word.md": "a mod of the game\n", "docs/script.md": "run mod.py now\n",
                      "lib/other.py": "from lib import mod\n", "docs/guide.md": "# guide\n",
                      "docs/cites.md": "see guide.md and not myguide.md\n"}.items():
        (repo / rel).write_text(text, encoding="utf-8", newline="\n")
    commit(repo, "more files")
    code, out = b(repo, "referrers", "lib/mod.py", "docs/guide.md")
    assert code == 0, out
    assert backlog.REL_DIR not in out and "docs/word.md" not in out, out
    for want in ("lib/mod.py  docs/script.md:1  1 line", "lib/mod.py  lib/other.py:1  1 line",
                 "lib/mod.py  lib/user.py:1  1 line", "docs/guide.md  docs/cites.md:1  1 line"):
        assert want in out, (want, out)


def test_backlog_referrers_planted_failure_of_the_scope_rule_is_caught(sprint, capsys, monkeypatch):
    """A scope rule that holds every path (planted) hides the stray files, and the check sees it."""
    repo = referrer_repo(sprint)
    monkeypatch.setattr(bl_items, "in_scope", lambda path, globs: True)  # planted, where referrers looks it up
    code = backlog.main(["--root", str(repo), "referrers", "lib/mod.py", "--item", sprint["tk"]])
    out = capsys.readouterr().out
    assert code == 0 and "outside touches" not in out  # the stray files go unmarked: the test above would fail


def test_claim_accepts_own_claimed_dependency(sprint):
    """`claim --by X` accepts an item whose only undone dependency is doing and claimed by X, so a depends_on that
    orders two items sharing a file needs no hand edit; planted: another session's claim, an unclaimed dependency
    and a dependency of the same session that is not doing still refuse."""
    repo, tk, bg = sprint["repo"], sprint["tk"], sprint["bg"]
    edit(repo, tk, depends_on=[bg])
    code, out = b(repo, "claim", tk, "--by", "s1")
    assert code == 1 and "depends on" in out, out  # planted: bg is not claimed
    assert b(repo, "claim", bg, "--by", "s2")[0] == 0
    code, out = b(repo, "claim", tk, "--by", "s1")
    assert code == 1 and "depends on" in out, out  # planted: claimed by another session
    b(repo, "release", bg)
    assert b(repo, "claim", bg, "--by", "s1")[0] == 0
    code, out = b(repo, "claim", tk, "--by", "s1")
    assert code == 0, out
    assert backlog.Backlog(repo).items[tk]["claimed_by"] == "s1"
