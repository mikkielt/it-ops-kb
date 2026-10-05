#!/usr/bin/env python3
"""kblog.py: record, confirm, invalidate, sweep, list and propose over LOG rows, in a small repository of its own.

The repository is the one test_kbdecide.py builds (a public root, an internal root `team` and kb/_self) with kblog.py
and the store it shares with kbdecide.py. Every command runs as a process; every success is followed by check.py over
the whole repository, and every refusal plants the failure it names and finds every log and decision file as it was.
"""
import json, shutil
from pathlib import Path

import pytest

import check, kbcommon
from conftest import requires_git
from test_kbdecide import (DAY, SWEEP_DAY, Repo as DecideRepo, add_superseding_source, commit_all, git, key_of, make_root,
                           put_item, set_facts, sid, write)

TOOLS = Path(__file__).resolve().parent
RUNS = "20261001T120000Z-0a1b2c3d;20261002T120000Z-4e5f6a7b"
OBSERVATION = "Median lookup latency was 142 ms over 5 days of 2 runs."
CONTEXT = "domain:ops; item:TK-abcd2345"
STORES = ("public", "team", "_self")


@pytest.fixture(scope="module")
def template(tmp_path_factory):
    """The repository every test starts from."""
    repo = tmp_path_factory.mktemp("kblog") / "repo"
    (repo / "_tools").mkdir(parents=True)
    for name in ("kbdecide.py", "kblog.py", "check.py", "kbcommon.py", "kbid.py", "kbfacts.py", "ql_base.py", "ql_capture.py",
                 "ql_store.py"):
        shutil.copy(TOOLS / name, repo / "_tools" / name)
    make_root(repo / "kb" / "public", "public", "S", "public")
    make_root(repo / "kb" / "team", "team", "T", "internal")
    write(repo / "kb" / "_self" / kbcommon.DECISIONS, ",".join(kbcommon.DECISION_COLS) + "\n")
    write(repo / "kb" / "_self" / kbcommon.DECISION_MAKERS, ",".join(kbcommon.MAKER_COLS) + "\nowner,operations owner,,\n")
    return repo


class Repo(DecideRepo):
    def log(self, *args):
        return self.run("kblog.py", *args)

    def logfile(self, store="public"):
        return self.path / "kb" / ("_self" if store == "_self" else store) / check.LOGS

    def logs(self, store="public"):
        return kbcommon.load_csv(str(self.logfile(store)))[1]

    def logrow(self, lid, store="public"):
        return next(r for r in self.logs(store) if r["id"] == lid)

    def snapshot(self):
        return {(s, f): (p.read_bytes() if p.exists() else None)
                for s in STORES for f, p in (("logs", self.logfile(s)), ("decisions", self.file(s)))}


@pytest.fixture
def repo(template, tmp_path):
    shutil.copytree(template, tmp_path / "repo")
    return Repo(tmp_path / "repo")


def ctx(store, text):
    """A context as the store writes it: kb/_self names an article or a domain as <root>/<path>."""
    return text if store != "_self" else text.replace("article:ops", "article:public/ops").replace("domain:ops", "domain:public/ops")


def record(repo, store="public", observation=OBSERVATION, context=CONTEXT, runs=RUNS, first="2026-09-26", last=DAY, *more):
    code, out = repo.log("record", "--root", store, observation, "--runs", runs, "--from", first, "--to", last,
                         "--context", ctx(store, context), *more)
    assert code == 0, out
    return out.split("\t")[0]


def refused(repo, *args, says):
    """A refused command: exit 2, the message names the rule, and no log or decision file changed."""
    before = repo.snapshot()
    code, out = repo.log(*args)
    assert code == 2 and says in out, (args, code, out)
    assert repo.snapshot() == before, (args, "a refused command changed a file")


def record_args(observation=OBSERVATION, **over):
    given = dict(runs=RUNS, first="2026-09-26", last=DAY, context=CONTEXT, root="public")
    given.update(over)
    return ["record", "--root", given["root"], observation, "--runs", given["runs"], "--from", given["first"],
            "--to", given["last"], "--context", given["context"]]


# ---- record and confirm: a proposed row, made active by the operator alone

def test_kblog_record_confirm_adds_a_proposed_row_that_the_operator_makes_active(repo):
    lid = record(repo, "public", "Median lookup latency was 142 ms over 5 days of 2 runs.", CONTEXT, RUNS, "2026-09-26", DAY,
                 "--links", "https://corp.example.com/notes")
    row = repo.logrow(lid)
    assert check.LOG_ID.fullmatch(lid) and list(row) == check.LOG_COLS
    assert (row["status"], row["observation"], row["source_run_ids"], row["observed_from"], row["observed_to"]) == (
        "proposed", OBSERVATION, "20261001T120000Z-0a1b2c3d; 20261002T120000Z-4e5f6a7b", "2026-09-26", DAY)
    assert (row["context"], row["links"], row["invalidated_reason"]) == (CONTEXT, "https://corp.example.com/notes", "")
    repo.check()
    refused(repo, "confirm", lid, "--root", "public", says="only the operator confirms a log row")
    refused(repo, "confirm", lid, "--root", "public", "--by", "agent", says="only the operator")
    proposed = repo.logrow(lid)
    assert proposed["status"] == "proposed"
    code, out = repo.log("confirm", lid, "--root", "public", "--by", "operator")
    assert code == 0 and out.strip() == f"{lid}\tactive\tpublic", out
    assert repo.logrow(lid) == dict(proposed, status="active")  # nothing but the status changes
    assert len(repo.logs()) == 1
    repo.check()
    refused(repo, "confirm", lid, "--root", "public", "--by", "operator", says="only proposed log rows can be confirmed")


def test_kblog_record_confirm_in_a_second_root_and_in_kb_self(repo):
    team = record(repo, "team", context="article:ops/patching; source:" + sid("T"))
    own = record(repo, "_self", context="article:ops/patching; item:TK-abcd2345")
    assert repo.logrow(team, "team")["status"] == repo.logrow(own, "_self")["status"] == "proposed"
    assert not repo.logfile("public").exists()
    assert repo.log("confirm", own, "--root", "_self", "--by", "operator")[0] == 0
    assert repo.logrow(own, "_self")["status"] == "active"
    refused(repo, "confirm", own, "--root", "team", "--by", "operator", says=f"no log row {own} in")
    repo.check()


def test_kblog_record_confirm_ids_follow_the_observation_context_runs_and_days(repo):
    first = record(repo)
    assert record(repo, "team") == first  # an id is made of the row, not of the root
    others = {record(repo, observation="Median lookup latency was 150 ms over 5 days of 2 runs."),
              record(repo, context="domain:ops"), record(repo, runs="20261002T120000Z-4e5f6a7b"),
              record(repo, first="2026-09-27"), record(repo, last="2026-10-02")}
    assert len(others | {first}) == 6
    refused(repo, *record_args(), says=f"{first} is already in public/_logs.csv")
    repo.check()


@pytest.mark.parametrize("observation, says", [
    ('{"query": "patch tuesday", "count": 3}', "holds a JSON object"),
    ("Median latency was 142 ms on 2026-10-01 12:30", "holds a timestamp with a time of day"),
    ("Spool event 20261001T123000Z had 3 hits", "holds a timestamp with a time of day"),
    ("Median latency was 142 ms\nfor kerberos queries", "holds a line break"),
    ("Median latency was 142 ms; seen from " + ".".join(["192", "168", "1", "20"]), "leak-scan hit (ip)"),
    ("Some queries were slow", "observation holds no number"),
    ("Median latency was 142 ms " + "x" * 240, "longer than 240 characters"),
])
def test_kblog_record_confirm_refuses_raw_event_text(repo, observation, says):
    """A row holds a derived aggregate: the shapes of a raw spool or ops event are refused as check.py refuses them,
    and the observation is never reflowed into one that passes."""
    refused(repo, *record_args(observation), says=says)
    assert not repo.logfile().exists()


def test_kblog_record_confirm_refuses_a_row_check_py_would_refuse(repo):
    keep = record(repo)
    refused(repo, *record_args("A second count was 7 runs."), "--links", "first line\nsecond line", says="links holds a line break")
    refused(repo, *record_args("A third count was 7 runs.", runs="20261001T1200Z-0a1b2c3d"), says="is not a run id")
    refused(repo, *record_args("A fourth count was 7 runs.", runs="20261001T120000Z-0a1b2c3d;20261001T120000Z-0a1b2c3d"),
            says="a run id twice")
    refused(repo, *record_args("A fifth count was 7 runs.", first="2026-10-02", last="2026-10-01"), says="is after observed_to")
    refused(repo, *record_args("A sixth count was 7 runs.", first="2026-13-40"), says="is not YYYY-MM-DD")
    refused(repo, *record_args("A seventh count was 7 runs.", context="table:ops"), says="context part 'table:ops'")
    refused(repo, *record_args("An eighth count was 7 runs.", context="article:ops/nope"), says="names no article ops/nope")
    refused(repo, *record_args("A ninth count was 7 runs.", context="domain:nope"), says="names no domain nope")
    refused(repo, *record_args("A tenth count was 7 runs.", context="item:abc"), says="not a valid item reference")
    refused(repo, *record_args("An eleventh count was 7 runs.", root="nowhere"), says="no root 'nowhere'")
    assert [r["id"] for r in repo.logs()] == [keep]
    repo.check()


@pytest.mark.parametrize("args, says", [
    (["record", "--root", "public", " ", "--runs", RUNS, "--from", DAY, "--to", DAY, "--context", CONTEXT], "needs an observation"),
    (["record", "--root", "public", OBSERVATION, "--runs", " ; ", "--from", DAY, "--to", DAY, "--context", CONTEXT], "needs --runs"),
    (["record", "--root", "public", OBSERVATION, "--runs", RUNS, "--from", DAY, "--to", DAY, "--context", ";"], "needs --context"),
    (["record", OBSERVATION, "--runs", RUNS, "--from", DAY, "--to", DAY, "--context", CONTEXT], "--root"),
    (["record", "--root", "public", OBSERVATION, "--runs", RUNS, "--from", DAY, "--context", CONTEXT], "--to"),
])
def test_kblog_record_confirm_needs_every_part_of_a_row(repo, args, says):
    code, out = repo.log(*args)
    assert code == 2 and says in out, out
    assert not repo.logfile().exists()


def test_kblog_record_confirm_refuses_a_file_that_is_not_the_format(repo):
    write(repo.logfile(), "id,text\nx,y\n")
    before = repo.snapshot()
    for args in (record_args(), ["confirm", "L-aaaaaaaa", "--root", "public", "--by", "operator"], ["list", "--root", "public"],
                 ["sweep", "--root", "public"]):
        code, out = repo.log(*args)
        assert code == 2 and "header is 'id,text'" in out, (args, out)
    assert repo.snapshot() == before


def test_kblog_record_confirm_refuses_a_malformed_or_unknown_id(repo):
    record(repo)
    refused(repo, "confirm", "D-aaaaaaaa", "--root", "public", "--by", "operator", says="is not a log row id (L-<8 base32>)")
    refused(repo, "confirm", "L-aaaaaaaa", "--root", "public", "--by", "operator", says="no log row L-aaaaaaaa")


def test_kblog_record_confirm_never_touches_the_decisions(repo):
    """The shared store keeps the two ledgers apart: a decision and a log row in one root change only their own file."""
    code, out = repo.decide("propose", "--root", "_self", "Servers patch on the second Tuesday.", "--source", sid(),
                            "--context", "domain:public/ops", "--date", DAY)
    assert code == 0, out
    decisions = repo.file("_self").read_bytes()
    lid = record(repo, "_self", context="domain:ops")
    assert repo.log("confirm", lid, "--root", "_self", "--by", "operator")[0] == 0
    assert repo.file("_self").read_bytes() == decisions
    assert repo.decide("list", "--root", "_self")[1].count("\n") == 2  # one decision and the count
    repo.check()


# ---- invalidate and list

def test_kblog_record_confirm_invalidate_withdraws_a_row_and_keeps_it(repo):
    lid = record(repo)
    refused(repo, "invalidate", lid, "--root", "public", "--reason", " ", says="--reason is empty")
    code, out = repo.log("invalidate", lid, "--root", "public", "--reason", "the runs were a rehearsal", "--date", DAY)
    assert code == 0 and out.strip() == f"{lid}\tinvalidated\tpublic", out
    row = repo.logrow(lid)
    assert (row["status"], row["invalidated_reason"], row["links"]) == ("invalidated", "the runs were a rehearsal", f"invalidated {DAY}")
    assert row["observation"] == OBSERVATION
    repo.check()
    refused(repo, "invalidate", lid, "--root", "public", "--reason", "again", says="only proposed or active log rows can be invalidated")
    refused(repo, "confirm", lid, "--root", "public", "--by", "operator", says="only proposed log rows can be confirmed")


def test_kblog_record_confirm_list_reads_one_root_or_all_and_filters(repo):
    one = record(repo)
    two = record(repo, "team", context="domain:ops")
    assert repo.log("confirm", two, "--root", "team", "--by", "operator")[0] == 0
    code, out = repo.log("list")
    assert code == 0 and "logs=2" in out and f"public\t{one}\tproposed\t2026-09-26\t{DAY}\t{CONTEXT}\t{OBSERVATION}" in out, out
    assert "logs=1" in repo.log("list", "--root", "team")[1]
    out = repo.log("list", "--status", "active")[1]
    assert "logs=1" in out and two in out and one not in out, out
    out = repo.log("list", "--context", "item:TK-abcd2345")[1]
    assert "logs=1" in out and one in out and two not in out, out
    assert "logs=2" in repo.log("list", "--context", "ops")[1]
    refused(repo, "list", "--root", "nowhere", says="no root 'nowhere'")


# ---- sweep: a row stays until its context stops holding, then it is invalidated and its row stays

def swept(repo, *args):
    """sweep as of SWEEP_DAY: (exit code, output)."""
    return repo.log("sweep", "--date", SWEEP_DAY, *args)


def sweep_record(repo, context, store="public", observation=OBSERVATION, confirm=False):
    lid = record(repo, store, observation, context)
    if confirm:
        assert repo.log("confirm", lid, "--root", store, "--by", "operator")[0] == 0
    return lid


def invalidated(repo, lid, store="public"):
    row = repo.logrow(lid, store)
    assert row["status"] == "invalidated" and row["links"].endswith(f"invalidated {SWEEP_DAY}"), row
    return row["invalidated_reason"]


def test_kblog_sweep_invalidates_with_context_a_dropped_item(repo):
    put_item(repo, "TK-dropped1", "dropped")
    put_item(repo, "TK-donedone", "done")
    proposed = sweep_record(repo, "item:TK-dropped1", observation="A proposed count was 3 runs.")
    active = sweep_record(repo, "item:TK-dropped1; domain:ops", "team", "An active count was 4 runs.", confirm=True)
    done = sweep_record(repo, "item:TK-donedone", observation="A count of a done item was 5 runs.", confirm=True)
    code, out = swept(repo)
    assert code == 0 and "invalidated=2" in out and "relink" not in out, out
    assert f"{proposed}\tinvalidated\tpublic\titem:TK-dropped1 dropped" in out, out
    assert invalidated(repo, proposed) == "item:TK-dropped1 dropped"
    assert invalidated(repo, active, "team") == "item:TK-dropped1 dropped"
    assert repo.logrow(done)["status"] == "active"  # the done item holds
    assert repo.logrow(active, "team")["observation"] == "An active count was 4 runs."  # the row stays whole
    assert len(repo.logs()) == 2 and len(repo.logs("team")) == 1
    repo.check()


def test_kblog_sweep_invalidates_with_context_a_row_stays_active_while_its_context_holds(repo):
    put_item(repo, "TK-stilldoi", "doing")
    ids = [sweep_record(repo, c, observation=f"A count of {n} runs.", confirm=True)
           for n, c in enumerate(("item:TK-stilldoi", "article:ops/patching", "domain:ops", f"source:{sid()}", "item:TK-neverhad"), 1)]
    before = repo.snapshot()
    code, out = swept(repo)
    assert code == 0 and "invalidated=0" in out, out
    assert repo.snapshot() == before and [repo.logrow(i)["status"] for i in ids] == ["active"] * 5


def test_kblog_sweep_invalidates_with_context_a_superseded_source_or_a_gone_article_or_domain(repo):
    source = sweep_record(repo, f"source:{sid()}", observation="A count of a source was 1 runs.")
    article = sweep_record(repo, "article:ops/patching", observation="A count of an article was 2 runs.")
    domain = sweep_record(repo, "domain:ops", observation="A count of a domain was 3 runs.", confirm=True)
    self_row = sweep_record(repo, "article:ops/patching", "_self", "A count of kb/_self was 4 runs.")
    newer = add_superseding_source(repo)
    code, out = swept(repo, "--root", "public")
    assert code == 0 and "invalidated=1" in out, out
    assert invalidated(repo, source) == f"source:{sid()} superseded by {newer}"
    (repo.path / "kb" / "public" / "ops" / "patching.md").unlink()
    code, out = swept(repo, "--root", "public")
    assert code == 0 and "invalidated=1" in out, out
    assert invalidated(repo, article) == "article:ops/patching is gone"
    assert repo.logrow(domain)["status"] == "active"
    shutil.rmtree(repo.path / "kb" / "public" / "ops")
    code, out = swept(repo)  # every root and kb/_self
    assert code == 0 and "invalidated=2" in out, out
    assert invalidated(repo, domain) == "domain:ops is gone"
    assert invalidated(repo, self_row, "_self") == "article:public/ops/patching is gone"
    repo.check()


def test_kblog_sweep_invalidates_with_context_a_fact_that_is_gone(repo):
    """Unlike a decision, which sweep flags for relink, an observation of a fact that is gone no longer holds."""
    old, other = "Servers patch on the second Tuesday.", "Laptops reboot after the Friday maintenance window."
    set_facts(repo, other, old)
    kept = sweep_record(repo, f"fact:{key_of(other)}", observation="A count of a kept fact was 1 runs.", confirm=True)
    gone = sweep_record(repo, f"fact:{key_of(old)}; domain:ops", observation="A count of a fact was 2 runs.", confirm=True)
    code, out = swept(repo)
    assert code == 0 and "invalidated=0" in out, out
    set_facts(repo, other)
    code, out = swept(repo)
    assert code == 0 and "invalidated=1" in out, out
    assert invalidated(repo, gone) == f"fact:{key_of(old)} is gone"
    assert repo.logrow(kept)["status"] == "active"
    repo.check()


def test_kblog_sweep_invalidates_with_context_names_every_broken_reference_and_fits_the_cell(repo):
    put_item(repo, "TK-dropped1", "dropped")
    many = [f"TK-drop{n:04d}" for n in range(1, 11)]
    for iid in many:
        put_item(repo, iid, "dropped")
    two = sweep_record(repo, "item:TK-dropped1; fact:0123456789ab", observation="A count of two refs was 2 runs.")
    long = sweep_record(repo, "; ".join(f"item:{i}" for i in many), observation="A count of ten refs was 10 runs.")
    code, out = swept(repo)
    assert code == 0 and "invalidated=2" in out, out
    assert invalidated(repo, two) == "item:TK-dropped1 dropped; fact:0123456789ab is gone"
    reason = invalidated(repo, long)
    assert len(reason) == check.LOG_TEXT_MAX and reason.endswith("...") and reason.startswith("item:TK-drop0001 dropped; "), reason
    assert all(f"item:{i} dropped" in out for i in many)  # the output names them all
    repo.check()


def test_kblog_sweep_invalidates_with_context_dry_run_prints_and_writes_nothing(repo):
    put_item(repo, "TK-dropped1", "dropped")
    lid = sweep_record(repo, "item:TK-dropped1")
    before = repo.snapshot()
    code, out = swept(repo, "--dry-run")
    assert code == 0 and f"{lid}\twould invalidate\tpublic\titem:TK-dropped1 dropped" in out and "would_invalidate=1" in out, out
    assert repo.snapshot() == before


def test_kblog_sweep_invalidates_with_context_leaves_invalidated_rows_and_decisions_as_they_are(repo):
    put_item(repo, "TK-dropped1", "dropped")
    withdrawn = sweep_record(repo, "item:TK-dropped1", observation="A withdrawn count was 1 runs.")
    assert repo.log("invalidate", withdrawn, "--root", "public", "--reason", "by hand", "--date", DAY)[0] == 0
    code, out = repo.decide("propose", "--root", "_self", "Servers patch on the second Tuesday.", "--source", sid(),
                            "--context", "item:TK-dropped1", "--date", DAY)
    assert code == 0, out
    before = repo.snapshot()
    code, out = swept(repo)
    assert code == 0 and "invalidated=0" in out, out
    assert repo.snapshot() == before  # the withdrawn row and the decision whose item was dropped stay as they were
    code, out = repo.decide("sweep", "--date", SWEEP_DAY)
    assert code == 0 and "invalidated=1" in out and repo.logrow(withdrawn)["invalidated_reason"] == "by hand", out


def test_kblog_sweep_invalidates_with_context_takes_a_root_and_refuses_what_it_cannot_sweep(repo):
    put_item(repo, "TK-dropped1", "dropped")
    one = sweep_record(repo, "item:TK-dropped1")
    two = sweep_record(repo, "item:TK-dropped1", "team")
    assert swept(repo, "--root", "team")[0] == 0
    assert (repo.logrow(one)["status"], repo.logrow(two, "team")["status"]) == ("proposed", "invalidated")
    refused(repo, "sweep", "--root", "nowhere", says="no root 'nowhere'")
    refused(repo, "sweep", "--date", "2026-13-40", says="is not YYYY-MM-DD")


@requires_git
def test_kblog_sweep_invalidates_with_context_an_item_deleted_at_close_by_its_last_version(repo):
    history = (("TK-closedrp", ("todo", "dropped")), ("TK-closedon", ("todo", "done")))
    for iid, statuses in history:
        put_item(repo, iid, statuses[0])
    git(repo, "init", "-q")
    commit_all(repo, "files")
    for iid, statuses in history:
        put_item(repo, iid, statuses[1])
    commit_all(repo, "last versions")
    for iid, _ in history:
        (repo.path / "kb" / "_self" / "backlog" / f"{iid}.json").unlink()
    commit_all(repo, "close the sprint")
    dropped, done = (sweep_record(repo, f"item:{i}", observation=f"A count of {i} was 1 runs.") for i in ("TK-closedrp", "TK-closedon"))
    code, out = swept(repo)
    assert code == 0 and "invalidated=1" in out, out
    assert invalidated(repo, dropped) == "item:TK-closedrp dropped" and repo.logrow(done)["status"] == "proposed"
    repo.check()


# ---- propose: aggregates of the ops sidecar as proposed rows, once

RUN_A, RUN_B = "20261001T120000Z-0a1b2c3d", "20261002T120000Z-4e5f6a7b"
ITEM = "TK-abcd2345"
OPS_ID = "11111111-0000-4000-8000-0000000000{:02d}"


def ops_store(repo, runs):
    """Plant a query-log store whose ops sidecars hold `runs`, {run id: [(time, event, keys)]}, and return its path."""
    store = repo.path / "ops-store"
    n = 0
    for run, lines in runs.items():
        out = [{"run": run, "counts": {"rows": len(lines)}}]
        for ts, event, keys in lines:
            n += 1
            out.append({"id": OPS_ID.format(n), "ts": ts, "event": event, **keys})
        write(store / "ops" / f"{run[:4]}-{run[4:6]}" / f"{run}.jsonl", "".join(json.dumps(o) + "\n" for o in out))
    return store


def land(ts, exit, ms, item=ITEM):
    return (ts, "land.step", {"item": item, "step": "rebase", "exit": exit, "ms": ms})


def suite(ts, ms, exit=0):
    return (ts, "test.run", {"mode": "fast", "ms": ms, "exit": exit})


PLANTED = {
    RUN_A: [land("2026-10-01T12:00:00Z", 0, 100), land("2026-10-01T12:00:05Z", 0, 300), land("2026-10-01T12:00:09Z", 1, 200),
            suite("2026-10-01T12:01:00Z", 4000)],
    RUN_B: [land("2026-10-02T09:00:00Z", 0, 400), suite("2026-10-02T09:05:00Z", 6000, 1)],
}
LAND_OBSERVATION = "ops land.step: 4 rows, 1 with a nonzero exit, ms median 250, range 100 to 400"


def propose(repo, store, *args, store_name="public"):
    code, out = repo.log("propose", "--root", store_name, "--store", str(store), *args)
    assert code == 0, out
    return out


def test_kblog_propose_from_ops_derives_aggregates_with_runs_dates_and_context(repo):
    store = ops_store(repo, PLANTED)
    out = propose(repo, store, "--since", "2026-10-01")
    (row,) = repo.logs()
    assert row["observation"] == LAND_OBSERVATION and row["status"] == "proposed", row
    assert (row["source_run_ids"], row["observed_from"], row["observed_to"], row["context"], row["links"]) == (
        f"{RUN_A}; {RUN_B}", "2026-10-01", "2026-10-02", f"item:{ITEM}", "")
    assert f"{row['id']}\tproposed\tpublic\titem:{ITEM}\t{LAND_OBSERVATION}" in out, out
    assert "proposed=1 known=0 no-context=2 not-closed=0" in out, out  # the two test.run rows name no item
    text = repo.logfile().read_text(encoding="utf-8")  # no raw event, id, time of day or step name
    assert not any(x in text for x in (OPS_ID.format(1), "T12:", "rebase", "11111111")), text
    repo.check()
    assert repo.log("list", "--status", "proposed")[1].count(LAND_OBSERVATION) == 1


def test_kblog_propose_from_ops_names_the_context_of_an_event_that_names_no_item(repo):
    store = ops_store(repo, PLANTED)
    propose(repo, store, "--since", "2026-10-01", "--context", "domain:ops")
    by = {r["context"]: r for r in repo.logs()}
    assert set(by) == {f"item:{ITEM}", "domain:ops"}
    assert by["domain:ops"]["observation"] == "ops test.run: 2 rows, 1 with a nonzero exit, ms median 5000, range 4000 to 6000"
    assert by["domain:ops"]["source_run_ids"] == f"{RUN_A}; {RUN_B}"
    repo.check()
    before = repo.snapshot()
    for context, says in (("table:ops", "not kind:value references"), ("item:abc", "not a valid item reference"),
                          ("article:ops/nope", "names no article ops/nope")):
        refused(repo, "propose", "--root", "public", "--store", str(store), "--since", "2026-10-01", "--context", context, says=says)
    assert repo.snapshot() == before


def test_kblog_propose_from_ops_reads_the_days_asked_for_and_the_closed_rows_only(repo):
    bad = ("2026-10-02T10:00:00Z", "land.step", {"item": ITEM, "step": "see jan.kowalski on PL-LT-00123", "exit": 0, "ms": 5})
    store = ops_store(repo, {**PLANTED, "20261003T120000Z-aaaa1111": [bad, land("2026-10-03T08:00:00Z", 0, 900)]})
    out = propose(repo, store, "--since", "2026-10-02", "--until", "2026-10-03")
    (row,) = repo.logs()
    assert row["observation"] == "ops land.step: 2 rows, 0 with a nonzero exit, ms median 650, range 400 to 900", row
    assert (row["source_run_ids"], row["observed_from"], row["observed_to"]) == (f"{RUN_B}; 20261003T120000Z-aaaa1111", "2026-10-02", "2026-10-03")
    assert "not-closed=1" in out and "jan.kowalski" not in repo.logfile().read_text(encoding="utf-8"), out
    assert "proposed=0" in propose(repo, store, "--since", "2026-10-05")


def test_kblog_propose_from_ops_never_activates_and_the_operator_confirms(repo):
    store = ops_store(repo, PLANTED)
    propose(repo, store, "--since", "2026-10-01")
    lid = repo.logs()[0]["id"]
    refused(repo, "confirm", lid, "--root", "public", "--by", "agent", says="only the operator")
    assert repo.logrow(lid)["status"] == "proposed"
    assert repo.log("confirm", lid, "--root", "public", "--by", "operator")[0] == 0
    assert repo.logrow(lid)["status"] == "active"
    repo.check()


def test_kblog_propose_from_ops_refuses_what_it_cannot_read_and_writes_nothing_on_dry_run(repo):
    store = ops_store(repo, PLANTED)
    refused(repo, "propose", "--root", "public", "--store", str(repo.path / "nowhere"), "--since", DAY, says="no query-log store")
    refused(repo, "propose", "--root", "public", "--store", str(store), "--since", "2026-13-01", says="is not YYYY-MM-DD")
    refused(repo, "propose", "--root", "public", "--store", str(store), "--since", DAY, "--until", "2026-09-01", says="is before --since")
    refused(repo, "propose", "--root", "nowhere", "--store", str(store), "--since", DAY, says="no root 'nowhere'")
    out = propose(repo, store, "--since", DAY, "--dry-run")
    assert LAND_OBSERVATION in out and out.endswith("dry-run\n") and not repo.logfile().exists(), out


def test_kblog_propose_converges_a_second_run_proposes_nothing_new(repo):
    store = ops_store(repo, PLANTED)
    propose(repo, store, "--since", "2026-10-01", "--context", "domain:ops")
    first = repo.logfile().read_bytes()
    assert len(repo.logs()) == 2
    out = propose(repo, store, "--since", "2026-10-01", "--context", "domain:ops")
    assert "proposed=0 known=2" in out and repo.logfile().read_bytes() == first, out
    # the operator's answer stays: a confirmed row and a withdrawn one are as known as a proposed one
    ids = [r["id"] for r in repo.logs()]
    assert repo.log("confirm", ids[0], "--root", "public", "--by", "operator")[0] == 0
    assert repo.log("invalidate", ids[1], "--root", "public", "--reason", "not about this")[0] == 0
    kept = repo.logfile().read_bytes()
    assert "proposed=0 known=2" in propose(repo, store, "--since", "2026-10-01", "--context", "domain:ops")
    assert repo.logfile().read_bytes() == kept
    repo.check()


def test_kblog_propose_converges_only_a_changed_aggregate_is_a_new_row(repo):
    store = ops_store(repo, PLANTED)
    propose(repo, store, "--since", "2026-10-01")
    (old,) = repo.logs()
    ops_store(repo, {**PLANTED, "20261004T120000Z-bbbb2222": [land("2026-10-04T08:00:00Z", 0, 50)]})
    out = propose(repo, store, "--since", "2026-10-01")
    assert "proposed=1 known=0" in out, out  # the same event over more runs is another row; the old one stays
    new = [r for r in repo.logs() if r["id"] != old["id"]]
    assert len(new) == 1 and new[0]["observation"].startswith("ops land.step: 5 rows") and new[0]["status"] == "proposed"
    assert repo.logrow(old["id"]) == old
    assert "proposed=0 known=1" in propose(repo, store, "--since", "2026-10-01")
    # a row `record` wrote for the same aggregate is the same row
    refused(repo, *record_args(new[0]["observation"], context=new[0]["context"], runs=new[0]["source_run_ids"],
                               first=new[0]["observed_from"], last=new[0]["observed_to"]), says=f"{new[0]['id']} is already in")
    repo.check()


SAMPLE = {"item": "TK-aaaaaaaa", "sprint": "SP-aaaaaaaa", "token": "x", "sha": "abcdef1", "agent": "abcdef12",
          "test_file": "test_x.py", "mode": "full", "ms": 1, "count": 1, "exit": 0, "flag": True}


def sample_keys(spec):
    """One closed value for each required key of an ops event (ql_capture.OPS_EVENTS)."""
    import ql_capture
    out = {}
    for k, (shape, required) in spec.items():
        if not required:
            continue
        if isinstance(shape, tuple):
            out[k] = []
        elif shape == "reason":
            out[k] = ql_capture.OPS_REFUSED[0]
        else:
            out[k] = SAMPLE[shape]
    return out


def test_kblog_propose_every_ops_event(repo):
    """ST-vaby3y5b (the operator's answer: every ops row): with --context naming what the item-less events are about,
    propose aggregates a row of every event of ql_capture.OPS_EVENTS, none left out for want of a context, each a
    proposed row; a second run proposes nothing new. Planted: without --context the item-less events are counted
    out."""
    import ql_capture
    events = sorted(ql_capture.OPS_EVENTS)
    store = ops_store(repo, {"20261003T120000Z-cccc3333": [
        ("2026-10-03T08:00:00Z", e, sample_keys(ql_capture.OPS_EVENTS[e])) for e in events]})
    out = propose(repo, store, "--since", "2026-10-01", "--context", "domain:ops")
    assert f"proposed={len(events)} known=0 no-context=0 not-closed=0" in out, out
    assert sorted(r["observation"].split(":", 1)[0][4:] for r in repo.logs()) == events
    assert {r["status"] for r in repo.logs()} == {"proposed"}
    assert "proposed=0 known=" in propose(repo, store, "--since", "2026-10-01", "--context", "domain:ops")
    bare = ops_store(repo, {"20261003T120000Z-cccc3333": [
        ("2026-10-03T08:00:00Z", e, sample_keys(ql_capture.OPS_EVENTS[e])) for e in events]})
    out = propose(repo, bare, "--since", "2026-10-01", "--dry-run")
    assert "no-context=0" not in out, out
    repo.check()
