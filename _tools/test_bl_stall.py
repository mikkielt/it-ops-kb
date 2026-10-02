"""Tests of `backlog.py stalled` (bl_stall.py): the stall signals read from the claims, git, the ops rows and the host
lock, the ladder of remedies for each, and the remedy a stalled item gets, which leaves one ops row and one autopilot
decision. Real throwaway git repositories, spool rows built at run time, no network. A signal is planted for one item
and the listing is compared with exactly that; the items that stay quiet are not listed.

The event `stall.remedy` is the real one of `ql_capture.OPS_EVENTS`: a remedy writes a row of its closed shape.
"""
import argparse
import json
import os
import shutil
import time
import uuid
from pathlib import Path

import pytest

import backlog
import bl_procs
import bl_stall
import bl_testkit
from bl_base import CHECK_TIMEOUT_S
from bl_testkit import TOOLS, argstr, b, commit, is_file, item, sh

bl_testkit.bind(backlog)
repo, sprint, no_git_location, gate_jobs = bl_testkit.repo, bl_testkit.sprint, bl_testkit.no_git_location, bl_testkit.gate_jobs

DAY = "2026-10-01T10:00:00.000Z"
OLD = bl_stall.CLAIM_NO_COMMIT_S + 600  # a claim older than the no-commit limit
MID = bl_stall.RETURNED_GRACE_S + 300  # older than the returned-worker grace, younger than the no-commit limit


@pytest.fixture
def spool(tmp_path_factory, monkeypatch):
    """The ops capture of this test on, in a spool of its own; the guard that keeps a test run's rows out of the real
    spool is lifted, and `stall.remedy` is a known event. Returns the spool directory."""
    import ql_capture
    import ql_deliver
    d = tmp_path_factory.mktemp("querylog") / "spool"
    monkeypatch.setattr(ql_capture, "spool_dir", lambda: d)
    monkeypatch.setattr(ql_deliver, "inside_test", lambda: False)
    d.mkdir(parents=True)
    return d


def plant(spool, event, item_id=None, **keys):
    """One ops row in the spool, as capture writes it; its id is made now."""
    row = {"id": str(uuid.uuid4()), "ts": keys.pop("ts", DAY), "surface": "ops", "v": 1, "event": event}
    if item_id:
        row["item"] = item_id
    row.update(keys)
    with open(Path(spool) / "tools-2026-10-01.jsonl", "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(row) + "\n")


def commit_ago(root, monkeypatch, msg, work, age_s):
    """A commit dated `age_s` seconds ago."""
    when = f"{int(time.time()) - age_s} +0000"
    monkeypatch.setenv("GIT_COMMITTER_DATE", when)
    monkeypatch.setenv("GIT_AUTHOR_DATE", when)
    try:
        commit(root, msg, work)
    finally:
        monkeypatch.delenv("GIT_COMMITTER_DATE")
        monkeypatch.delenv("GIT_AUTHOR_DATE")


def started(sprint):
    """The fixture's sprint committed, and nine more ready tasks under its story: ids in the order made."""
    repo_, st = sprint["repo"], sprint["st"]
    commit(repo_, "plan and start")
    ids = [sprint["tk"]]
    for n in range(8):
        assert b(repo_, "new", "task", "--title", f"Extra {n}", "--parent", st, "--goal", "g", "--touch", "src/**",
                 "--check", argstr(is_file("src/b.txt")))[0] == 0
        ids.append(item(repo_, f"Extra {n}")["id"])
    commit(repo_, "tasks")
    return repo_, ids


def claim(repo_, monkeypatch, iid, age_s):
    """`iid` claimed `age_s` seconds ago, as `claim --commit` commits it."""
    assert b(repo_, "claim", iid, "--by", "worker")[0] == 0
    commit_ago(repo_, monkeypatch, f"chore(backlog): claim {iid} \"t\"", iid, age_s)


def work_commit(path, monkeypatch, iid, age_s, name="w"):
    (Path(path) / "src" / f"{iid}-{name}.txt").write_text("w\n", encoding="utf-8")
    commit_ago(path, monkeypatch, f"feat: work on {iid}", iid, age_s)


def worktree(repo_, iid):
    """A worktree of the clone on the branch `work/ID`, its path."""
    path = repo_.parent / f"wt-{iid}"
    sh(repo_, "git", "worktree", "add", "-q", "-b", f"work/{iid}", str(path))
    return path


@pytest.fixture
def no_procs(monkeypatch):
    """The process scan sees no process anywhere."""
    monkeypatch.setattr(bl_procs, "cwd_map", lambda: ({}, None))


@pytest.fixture
def no_lock(tmp_path_factory, monkeypatch):
    """The host test lock directory is an empty one of this test's."""
    d = tmp_path_factory.mktemp("lock")
    monkeypatch.setenv("KB_HOST_LOCK_DIR", str(d))
    return d


@pytest.fixture
def clean(spool, no_procs, no_lock):
    """No host lock, no process, an ops spool of this test's: the only signals are those a test plants."""
    return spool


def listing(repo_, now=None):
    """{item id: signals} of the items `stalled` lists."""
    got = bl_stall.collect(backlog.Backlog(repo_), now=now)
    return {r["id"]: r["signals"] for r in got["items"]}


# ---------------------------------------------------------------- one signal at a time, a quiet item beside it

def test_stalled_items_by_signal_claim_with_no_commit_past_the_limit(sprint, clean, monkeypatch):
    repo_, ids = started(sprint)
    claim(repo_, monkeypatch, ids[0], OLD)  # no work commit since
    claim(repo_, monkeypatch, ids[1], OLD)
    work_commit(repo_, monkeypatch, ids[1], OLD // 2)  # this one has its commit
    claim(repo_, monkeypatch, ids[2], 60)  # young: no stall yet
    assert listing(repo_) == {ids[0]: ["claim-no-commit"]}


def test_stalled_items_by_signal_claim_limit_is_exact_for_every_age(sprint, clean, monkeypatch):
    repo_, ids = started(sprint)
    claim(repo_, monkeypatch, ids[0], 0)
    base = bl_stall.claim_facts(str(repo_), ids[0])["claimed"]  # git keeps whole seconds
    for age in (0, 1, 59, bl_stall.CLAIM_NO_COMMIT_S - 1, bl_stall.CLAIM_NO_COMMIT_S, bl_stall.CLAIM_NO_COMMIT_S + 1,
                7 * bl_stall.CLAIM_NO_COMMIT_S):
        want = {ids[0]: ["claim-no-commit"]} if age > bl_stall.CLAIM_NO_COMMIT_S else {}
        assert listing(repo_, now=base + age) == want, age


def test_stalled_items_by_signal_returned_worker_without_a_commit(sprint, clean, monkeypatch):
    repo_, ids = started(sprint)
    for i in ids[:4]:
        claim(repo_, monkeypatch, i, MID)
    gone, live, committed, nowt = ids[:4]
    wts = {i: worktree(repo_, i) for i in (gone, live, committed)}  # nowt has no worktree yet
    work_commit(wts[committed], monkeypatch, committed, MID // 2)
    monkeypatch.setattr(bl_procs, "cwd_map", lambda: ({os.getpid() + 1: str(wts[live] / "src")}, None))
    assert listing(repo_) == {gone: ["returned-no-commit"]}


def test_stalled_items_by_signal_returned_worker_with_staged_files_and_no_process(sprint, clean, monkeypatch):
    repo_, ids = started(sprint)
    for i in ids[:2]:
        claim(repo_, monkeypatch, i, MID)
    wt = worktree(repo_, ids[0])
    (wt / "src" / "staged.txt").write_text("s\n", encoding="utf-8")
    sh(wt, "git", "add", "src/staged.txt")
    other = worktree(repo_, ids[1])
    (other / "src" / "loose.txt").write_text("untracked only\n", encoding="utf-8")  # an untracked file is no work left
    assert listing(repo_) == {ids[0]: ["returned-staged"], ids[1]: ["returned-no-commit"]}


def test_stalled_items_by_signal_a_host_that_cannot_list_processes_is_unknown_not_guessed(sprint, clean, monkeypatch):
    repo_, ids = started(sprint)
    claim(repo_, monkeypatch, ids[0], MID)
    worktree(repo_, ids[0])
    monkeypatch.setattr(bl_procs, "cwd_map", lambda: (None, "no process table here"))
    (row,) = bl_stall.collect(backlog.Backlog(repo_))["items"]
    assert (row["id"], row["signals"], row["unknown"]) == (ids[0], [], ["unknown:procs"])


def test_stalled_items_by_signal_a_claim_with_no_claim_commit_is_unknown_not_guessed(sprint, clean):
    repo_, ids = started(sprint)
    assert b(repo_, "claim", ids[0], "--by", "worker")[0] == 0  # never committed
    (row,) = bl_stall.collect(backlog.Backlog(repo_))["items"]
    assert (row["id"], row["signals"], row["unknown"]) == (ids[0], [], ["unknown:claim-time"])


def test_stalled_items_by_signal_repeated_refused_done(sprint, clean):
    repo_, ids = started(sprint)
    plant(clean, "done.refused", ids[0], reasons=["status"], ms=5)
    plant(clean, "done.refused", ids[0], reasons=["uncommitted", "no-work-commit"], ms=7)
    plant(clean, "done.refused", ids[1], reasons=["status"], ms=5)  # once: no stall
    assert listing(repo_) == {ids[0]: ["done-refused"]}


def test_stalled_items_by_signal_check_that_ran_out_of_time_twice(sprint, clean):
    repo_, ids = started(sprint)
    long_ms = CHECK_TIMEOUT_S * 1000
    plant(clean, "done.refused", ids[0], reasons=["check-failed"], ms=long_ms)
    plant(clean, "done.refused", ids[0], reasons=["check-failed"], ms=long_ms + 1)
    plant(clean, "done.refused", ids[1], reasons=["check-failed"], ms=long_ms)  # one timeout
    plant(clean, "done.refused", ids[1], reasons=["check-failed"], ms=long_ms - 1)  # a failure, quick
    plant(clean, "done.refused", ids[2], reasons=["status"], ms=long_ms)  # slow but no check ran
    plant(clean, "done.refused", ids[2], reasons=["status"], ms=long_ms)
    assert listing(repo_) == {ids[0]: ["done-refused", "check-timeout"], ids[1]: ["done-refused"],
                              ids[2]: ["done-refused"]}


def test_stalled_items_by_signal_land_stopping_at_the_same_step_twice(sprint, clean):
    repo_, ids = started(sprint)
    plant(clean, "land.step", ids[0], step="rebase", exit=1, ms=10)
    plant(clean, "land.step", ids[0], step="rebase", exit=1, ms=11)
    plant(clean, "land.step", ids[1], step="rebase", exit=1, ms=10)  # a step each: no repeat
    plant(clean, "land.step", ids[1], step="done", exit=1, ms=10)
    plant(clean, "land.step", ids[2], step="fetch", exit=0, ms=10)  # passing steps are no stop
    plant(clean, "land.step", ids[2], step="fetch", exit=0, ms=10)
    assert listing(repo_) == {ids[0]: ["land-same-step"]}


@pytest.mark.parametrize("n", range(0, 6))
def test_stalled_items_by_signal_a_repeat_counts_from_its_limit_for_every_number_of_rows(sprint, clean, n):
    repo_, ids = started(sprint)
    for _ in range(n):
        plant(clean, "land.step", ids[0], step="sync", exit=2, ms=1)
        plant(clean, "done.refused", ids[1], reasons=["status"], ms=1)
    got = listing(repo_)
    assert (ids[0] in got) == (n >= bl_stall.LAND_SAME_STEP_N)
    assert (ids[1] in got) == (n >= bl_stall.DONE_REFUSED_N)


def test_stalled_items_by_signal_the_same_row_in_the_spool_and_a_sidecar_counts_once(sprint, clean):
    repo_, ids = started(sprint)
    plant(clean, "done.refused", ids[0], reasons=["status"], ms=5)
    rows = [json.loads(ln) for ln in (clean / "tools-2026-10-01.jsonl").read_text(encoding="utf-8").splitlines()]
    side = repo_ / "kb" / "_querylog" / "ops" / "2026-10"
    side.mkdir(parents=True)
    header = {"run": "r1", "counts": {"rows": 1}}
    line = {k: v for k, v in rows[0].items() if k not in ("surface", "v")}
    (side / "r1.jsonl").write_text(json.dumps(header) + "\n" + json.dumps(line) + "\n", encoding="utf-8", newline="\n")
    assert [r["id"] for r in bl_stall.ops_rows(str(repo_))] == [rows[0]["id"]]
    assert listing(repo_) == {}  # one refusal, read twice, is one


def test_stalled_items_by_signal_red_main_marks_the_claimed_items_only(sprint, clean, monkeypatch):
    repo_, ids = started(sprint)
    claim(repo_, monkeypatch, ids[0], 60)
    plant(clean, "ci.pipeline", state="green", calls=1, ts="2026-10-01T09:00:00.000Z")
    assert listing(repo_) == {}
    plant(clean, "ci.pipeline", state="red", calls=2)
    got = bl_stall.collect(backlog.Backlog(repo_))
    assert got["main"]["state"] == "red"
    assert {r["id"]: r["signals"] for r in got["items"]} == {ids[0]: ["red-main"]}  # ready items stay unlisted
    plant(clean, "ci.pipeline", state="green", calls=1, ts="2026-10-01T11:00:00.000Z")
    assert listing(repo_) == {}  # the newest row decides


def test_stalled_items_by_signal_no_pipeline_row_says_main_is_unknown(sprint, clean, monkeypatch):
    repo_, ids = started(sprint)
    claim(repo_, monkeypatch, ids[0], 60)
    got = bl_stall.collect(backlog.Backlog(repo_))
    assert got["main"] == {"state": "unknown", "ts": None} and got["items"] == []


def write_lock(lock_dir, pid, age_s):
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - age_s))
    (Path(lock_dir) / bl_stall.LOCK_NAME).write_text(f"pid={pid}\nclone=somewhere\nstarted={started_at}\n", encoding="utf-8")


def test_stalled_items_by_signal_host_lock_held_past_the_limit(sprint, clean, no_lock, monkeypatch):
    repo_, ids = started(sprint)
    claim(repo_, monkeypatch, ids[0], 60)
    write_lock(no_lock, os.getpid(), bl_stall.HOST_LOCK_WAIT_S - 60)
    assert listing(repo_) == {}
    write_lock(no_lock, os.getpid(), bl_stall.HOST_LOCK_WAIT_S + 60)
    assert listing(repo_) == {ids[0]: ["lock-wait"]}
    write_lock(no_lock, 2 ** 22 + 7, bl_stall.HOST_LOCK_WAIT_S + 60)  # a holder that is gone: stale, no wait
    assert listing(repo_) == {}
    (Path(no_lock) / bl_stall.LOCK_NAME).write_text("garbled\n", encoding="utf-8")
    (row,) = bl_stall.collect(backlog.Backlog(repo_))["items"]
    assert row["unknown"] == ["unknown:lock"]


def test_stalled_items_by_signal_all_seven_at_once_and_the_quiet_items_unlisted(sprint, clean, no_lock, monkeypatch, capsys):
    repo_, ids = started(sprint)
    a, bb, c, d, e, f, g, quiet1, quiet2 = ids
    claim(repo_, monkeypatch, a, OLD)  # claim-no-commit
    claim(repo_, monkeypatch, bb, MID)  # returned-no-commit
    worktree(repo_, bb)
    plant(clean, "done.refused", c, reasons=["status"], ms=1)
    plant(clean, "done.refused", c, reasons=["status"], ms=1)  # done-refused
    for _ in range(2):
        plant(clean, "done.refused", d, reasons=["check-failed"], ms=CHECK_TIMEOUT_S * 1000)  # check-timeout
        plant(clean, "land.step", e, step="rebase", exit=1, ms=1)  # land-same-step
    plant(clean, "ci.pipeline", state="red", calls=1)  # red-main (a, bb are claimed)
    write_lock(no_lock, os.getpid(), bl_stall.HOST_LOCK_WAIT_S + 5)  # lock-wait
    claim(repo_, monkeypatch, quiet1, 30)
    work_commit(repo_, monkeypatch, quiet1, 10)  # claimed, working, but the main and the lock hamper it
    got = listing(repo_)
    assert got == {a: ["claim-no-commit", "red-main", "lock-wait"], bb: ["returned-no-commit", "red-main", "lock-wait"],
                   c: ["done-refused"], d: ["done-refused", "check-timeout"], e: ["land-same-step"],
                   quiet1: ["red-main", "lock-wait"]}
    assert f not in got and g not in got and quiet2 not in got, "ready items with no signal are not listed"
    assert set(sum(got.values(), [])) == set(bl_stall.SIGNALS) - {"returned-staged"}
    assert bl_stall.cmd_stalled(backlog.Backlog(repo_), argparse.Namespace(json=False, ladder=False, took=None)) == 0
    out = capsys.readouterr().out  # one line per item, its id and title together
    lines = [ln for ln in out.splitlines() if ln.startswith(("TK-", "ST-", "BG-"))]
    assert len(lines) == len(got) and all("\u201c" in ln for ln in lines), out
    assert "main red" in out and "next: claim-no-commit=retry-narrower" in out
    assert bl_stall.cmd_stalled(backlog.Backlog(repo_), argparse.Namespace(json=True, ladder=False, took=None)) == 0
    assert {r["id"] for r in json.loads(capsys.readouterr().out)["items"]} == set(got)


def test_stalled_items_by_signal_the_command_lists_a_claim_from_git_alone_and_exits_0(sprint, clean, monkeypatch):
    repo_, ids = started(sprint)
    claim(repo_, monkeypatch, ids[0], OLD)
    code, out = b(repo_, "stalled")
    assert code == 0, out
    (line,) = [ln for ln in out.splitlines() if ln.startswith(ids[0])]
    assert "\u201c" in line and "claim-no-commit" in line and "next: claim-no-commit=retry-narrower" in line, out
    code, out = b(repo_, "stalled", "--json")
    assert code == 0 and [r["id"] for r in json.loads(out)["items"]] == [ids[0]]


def test_stalled_items_by_signal_a_started_sprint_with_nothing_wrong_lists_nothing_and_exits_0(sprint, clean):
    repo_, ids = started(sprint)
    code, out = b(repo_, "stalled")
    assert code == 0 and "0 item(s) with a signal" in out, out
    assert listing(repo_) == {}


def test_stalled_items_by_signal_reads_no_network_and_no_process_arguments():
    src = (Path(TOOLS) / "bl_stall.py").read_text(encoding="utf-8")
    for word in ("urllib", "socket", "http.client", "cmdline", "environ", '"ps"', "-axo"):
        assert word not in src, word
    assert "bl_procs.cwd_map" in src  # the working-directory scan is bl_procs's, which prints command names only


# ---------------------------------------------------------------- the ladder and the remedy

def test_stall_ladder_files_blocker_and_moves_on_the_table(sprint):
    assert set(bl_stall.LADDER) == set(bl_stall.SIGNALS)
    for signal, remedies in bl_stall.LADDER.items():
        assert len(set(remedies)) == len(remedies) and set(remedies) <= set(bl_stall.REMEDIES), signal
        assert remedies[-2:] == ("file-blocker", "ask-operator"), signal  # the last but one files, the last asks
    assert bl_stall.LADDER["returned-staged"][0] == "finish-here"  # the staged worker: finish it here, checks foreground
    assert all(bl_stall.LADDER[s][0] == "retry-narrower" for s in
               ("claim-no-commit", "returned-no-commit", "done-refused", "check-timeout", "land-same-step"))


def test_stall_ladder_files_blocker_and_moves_on_the_skill_names_every_signal_and_remedy():
    skill = (Path(TOOLS).parent / ".claude" / "skills" / "kb-sprint" / "SKILL.md").read_text(encoding="utf-8")
    body = skill.split("## Stalled work", 1)[1]
    for word in (*bl_stall.SIGNALS, *bl_stall.REMEDIES, "stalled", "--took"):
        assert word in body, word
    for signal, remedies in bl_stall.LADDER.items():  # the doc keeps the ladder's order
        text = [ln for ln in body.splitlines() if ln.lstrip("-* |`").startswith(signal)]
        assert text, signal
        assert [r for r in text[0].replace("`", " ").replace(">", " ").split() if r in bl_stall.REMEDIES] == list(remedies)
    assert "never idles" in body


DECIDE_TOOLS = ("kbdecide.py", "check.py", "kbcommon.py", "kbid.py", "kbfacts.py")
EMPTY_DECISIONS = "id,text,by,by_ref,source,date,context,status,invalidated_reason,invalidated_date,supersedes,review_by,links\n"


@pytest.fixture
def decided(sprint):
    """The started sprint's repository with a copy of the decision tools, a minimal public root and kb/_self's decision
    files, so a remedy's decision lands in the copy; the story and nine tasks of `started`."""
    repo_, ids = started(sprint)
    (repo_ / "_tools").mkdir()
    for name in DECIDE_TOOLS:
        shutil.copy(os.path.join(TOOLS, name), repo_ / "_tools" / name)
    pub = repo_ / "kb" / "public"
    pub.mkdir(parents=True)
    root_md = "---\nroot: public\nid_prefix: S\nvisibility: public\ndescription: test root\n---\n"
    sources = "id,url,title,publisher,licence,reuse,retrieved_utc,version_or_date,artifact_sha256,used_in,superseded_by\n"
    for rel, text in (("_root.md", root_md), ("_sources.csv", sources), ("_artifacts.csv", "path,source_id,sha256\n"),
                      ("_answers.md", "# Answers\n"), ("_gaps.md", "# Gaps\n"), ("_conflicts.md", "# Conflicts\n")):
        (pub / rel).write_text(text, encoding="utf-8", newline="\n")
    kb_self = repo_ / "kb" / "_self"
    kb_self.mkdir(exist_ok=True)
    (kb_self / "_decisions.csv").write_text(EMPTY_DECISIONS, encoding="utf-8", newline="\n")
    (kb_self / "decision-makers.csv").write_text(
        "id,role,name,source\noperator,operator,,the operator\nautopilot,autopilot,,the autopilot\n", encoding="utf-8",
        newline="\n")
    (repo_ / ".gitignore").write_text("__pycache__/\n", encoding="utf-8", newline="\n")
    commit(repo_, "decision tools")
    return repo_, ids


def decision_rows(repo_):
    import csv
    with open(repo_ / "kb" / "_self" / "_decisions.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def spool_ops(spool_dir, event):
    return [r for f in sorted(Path(spool_dir).glob("*.jsonl"))
            for r in (json.loads(ln) for ln in f.read_text(encoding="utf-8").splitlines())
            if r.get("surface") == "ops" and r.get("event") == event]


def test_stall_ladder_files_blocker_and_moves_on_each_remedy_leaves_an_ops_row_and_a_decision(decided, clean, monkeypatch):
    repo_, ids = decided
    stuck = ids[0]
    claim(repo_, monkeypatch, stuck, OLD)
    signal, ladder = "claim-no-commit", bl_stall.LADDER["claim-no-commit"]
    for n, remedy in enumerate(ladder, start=1):
        assert bl_stall.next_remedy(str(repo_), stuck, signal) == remedy
        got = bl_stall.remedy_row(str(repo_), stuck, signal, remedy)
        assert got["count"] == n and got["ops"]["event"] == "stall.remedy"
        rows = spool_ops(clean, "stall.remedy")
        assert len(rows) == n and rows[-1]["item"] == stuck and rows[-1]["signal"] == signal
        assert (rows[-1]["remedy"], rows[-1]["count"]) == (remedy, n)
        dec = decision_rows(repo_)
        assert len(dec) == n and dec[-1]["id"] == got["decision"]
        assert (dec[-1]["by"], dec[-1]["status"], dec[-1]["context"]) == ("autopilot", "active", f"item:{stuck}")
        assert dec[-1]["review_by"] and remedy in dec[-1]["text"] and bl_stall.REMEDIES[remedy] in dec[-1]["text"]
        assert dec[-1]["source"] == f"backlog item {stuck} stalled {signal}"
    assert bl_stall.next_remedy(str(repo_), stuck, signal) is None  # the ladder is spent
    with pytest.raises(Exception, match="already"):  # a remedy is taken once
        bl_stall.remedy_row(str(repo_), stuck, signal, ladder[0])
    assert len(decision_rows(repo_)) == len(ladder) and len(spool_ops(clean, "stall.remedy")) == len(ladder)
    code, out = bl_testkit.b(repo_, "stalled", "--json")  # the listing shows the spent ladder
    row = next(r for r in json.loads(out)["items"] if r["id"] == stuck)
    assert row["next"] == {signal: None}
    import ql_capture
    for r in spool_ops(clean, "stall.remedy"):  # every row is of the closed shape
        assert ql_capture.ops_problems({k: v for k, v in r.items() if k not in ("id", "ts", "surface", "v")}) == []


def test_stall_ladder_files_blocker_and_moves_on_refuses_what_is_not_on_the_ladder(decided, clean):
    repo_, ids = decided
    for signal, remedy in (("no-such-signal", "retry-narrower"), ("red-main", "retry-narrower"),
                           ("claim-no-commit", "finish-here")):
        with pytest.raises(Exception, match="not a"):
            bl_stall.remedy_row(str(repo_), ids[0], signal, remedy)
    assert decision_rows(repo_) == [] and spool_ops(clean, "stall.remedy") == []


def test_stall_ladder_files_blocker_and_moves_on_the_blocker_is_filed_and_the_next_ready_item_taken(decided, clean, monkeypatch, capsys):
    repo_, ids = decided
    stuck, hampered = ids[0], ids[1]
    claim(repo_, monkeypatch, stuck, OLD)
    plant(clean, "done.refused", hampered, reasons=["status"], ms=1)
    plant(clean, "done.refused", hampered, reasons=["status"], ms=1)  # ready, but stalled: not the one to take
    before = set(backlog.Backlog(repo_).items)
    ready = bl_stall.ready_items(backlog.Backlog(repo_))  # the ready bug counts, so the order is the tool's own
    nxt = next(i for i in ready if i not in (stuck, hampered))
    a = argparse.Namespace(json=False, ladder=False, took=[stuck, "claim-no-commit", "file-blocker"])
    assert bl_stall.cmd_stalled(backlog.Backlog(repo_), a) == 0
    out = capsys.readouterr().out
    (filed,) = set(backlog.Backlog(repo_).items) - before
    blocker = backlog.Backlog(repo_).items[filed]
    assert blocker["kind"] == "story" and stuck in blocker["title"] and "claim-no-commit" in blocker["title"]
    assert f"filed {filed}" in out and "ops row written" in out
    assert f"take next {nxt}" in out, out  # the first ready item that is neither the stuck one nor stalled
    assert len(spool_ops(clean, "stall.remedy")) == 1 and len(decision_rows(repo_)) == 1
    assert bl_stall.next_ready(backlog.Backlog(repo_), stuck) == nxt


def test_stall_ladder_files_blocker_and_moves_on_never_idle_while_a_ready_item_remains(sprint, clean, monkeypatch):
    repo_, ids = started(sprint)
    bl = backlog.Backlog(repo_)
    ready = bl_stall.ready_items(bl)
    assert len(ready) >= 3
    for i in ready[:-1]:  # every ready item but the last one is stalled
        plant(clean, "land.step", i, step="rebase", exit=1, ms=1)
        plant(clean, "land.step", i, step="rebase", exit=1, ms=1)
    assert bl_stall.next_ready(bl, ready[0]) == ready[-1]  # the one quiet item is taken
    plant(clean, "land.step", ready[-1], step="rebase", exit=1, ms=1)
    plant(clean, "land.step", ready[-1], step="rebase", exit=1, ms=1)
    assert bl_stall.next_ready(bl, ready[0]) is None  # none left that is not itself stalled: only then ask


def test_stall_ladder_files_blocker_and_moves_on_the_event_is_in_the_real_set_and_the_row_is_written(decided, spool):
    import ql_capture
    assert bl_stall.EVENT in ql_capture.OPS_EVENTS  # the registry as it is, no patch
    repo_, ids = decided
    got = bl_stall.remedy_row(str(repo_), ids[0], "red-main", "ask-operator")
    assert got["ops"] is not None and got["decision"] and len(decision_rows(repo_)) == 1
    (row,) = spool_ops(spool, "stall.remedy")
    assert (row["item"], row["signal"], row["remedy"], row["count"]) == (ids[0], "red-main", "ask-operator", 1)
    assert set(row) == {"id", "ts", "surface", "v", "event", "item", "signal", "remedy", "count"}
    assert len(ql_capture.OPS_EVENTS[bl_stall.EVENT]) == 4  # item, signal, remedy, count: nothing free-form
