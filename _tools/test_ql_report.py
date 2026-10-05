"""Query log tests, report (kb/_self/querylog.md, Digest and Status; `python3 _tools/tests.py -k TestDigest`, and
the other classes below).

  TestDigest        two copies of one fixture store give byte-identical `digest` output, equal to the expected text;
                    the default week is the newest entry's; findings states stop at the week's Sunday; an empty or
                    missing store and a bad week; distill sums a fetch's result characters
  TestDigestWork    the digest's work lines (`-k digest_work`): the week's items by tokens, an item's runs summed, ties by
                    id, at most WORK_TOP listed, main and subagent shares, shared and overhead lines left out, a week
                    with no item line prints nothing extra, a sidecar that breaks the work gates is left out whole
  TestDigestHook    the first SessionStart of an ISO week shows last week's digest once as a systemMessage; mode off,
                    the DISABLED marker and an empty week show nothing; planted: over DIGEST_BUDGET_S shows nothing
                    and is not tried again that week; the hook command prints at most one JSON line and exits 0
  TestStatus        open source findings ranked by result characters, open querylog/ merge requests (glab and gh
                    stubs: GitLab MR API, gh pr list) and KB-Auto reverts; not signed in, a failed call and no origin
                    are skipped with a note; the revert trailer read from a real git log (marker git)
  TestQuerylogShow  `show`: the exact lines of --run, --entry, --findings (filters, cap), --usage and --spool; the
                    spool prints no text, id or host a row holds; the store is left as it was and two copies print the
                    same bytes; no process starts; every run, entry and sidecar of the committed store reads; planted:
                    each refusal (unknown or ambiguous id, bad kind, state or article, a filter without --findings,
                    --store with --spool, a missing store, two things to show) exits 2 with its rule and writes nothing
Every run writes under a temporary plugin data directory (conftest.querylog_env), never the clone's own spool, and no
test calls the real `claude`: Haiku is the recorded reply file or a stub. The helpers the classes share are in
ql_testkit.py.
"""
import datetime, json, os, re, subprocess, sys, time, uuid

import pytest

import ql_distill, ql_report, ql_store
from conftest import querylog_env, Repo
from ql_testkit import learn_store, QL, session_start


# ---------------------------------------------------------------- digest and status (Query log item 9)

W39_RUN = "20260927T100000Z-0000cafe"  # a second run file, in ISO week 2026-W39
W39_FINDINGS = "20260927T230000Z-0000d1ce"  # findings written in 2026-W39
W40_FINDINGS = "20260929T080000Z-0000d2ce"  # findings written in 2026-W40: after the week's end


def f_rec(kind, entry=None, state="open", **kw):
    rec = {"id": ql_store.finding_id(kind, entry if entry else kw.get("signal", ""), kw.get("host", "")),
           "kind": kind, "state": state}
    if entry:
        rec["id"] = ql_store.finding_id(kind, entry)
        rec.update(stage=kw.pop("stage", "miss"), entry=entry)
    rec.update(kw)
    return rec


def write_store_file(path, header, objs):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(o, separators=(",", ":")) + "\n" for o in [header, *objs]), encoding="utf-8",
                    newline="\n")


def digest_store(dst):
    """The fixture store plus a run file and findings files around ISO week 2026-W39: two misses fixed (one since,
    one by apply), a gap still open, two open source findings, and a later record that the week's end must not see."""
    store = learn_store(dst.parent, dst.name)
    a = "55555555-0000-4000-8000-0000000000"
    extra = {"id": "66666666-0000-4000-8000-0000000000a1", "surface": "kb_ask", "day": "2026-09-27", "tools": ["kb_ask"],
             "route": "good", "question": "Which port does WinRM over HTTPS use?", "verdict": "good"}
    write_store_file(store / "2026-09" / f"{W39_RUN}.jsonl",
                     {"run": W39_RUN, "pipeline": 2, "retrieval": 4, "kb_commit": "0" * 40,
                      "counts": {"entries": 1, "dropped": 2, "waiting": 0}}, [extra])
    lap = "public/windows/laps.md"
    w39 = [f_rec("eval", a + "a1", "fixed-since", expect=lap),
           f_rec("eval", a + "a3", "applied", expect="public/intune/win32-apps.md"),
           f_rec("expansion", a + "a3", "applied", article="public/intune/win32-apps.md"),
           f_rec("gap", a + "a4", stage="candidate-gap",
                 promotions=[{"from": "miss", "to": "candidate-gap", "by": "learn"}]),
           f_rec("eval", a + "a2", expect=lap),
           f_rec("alias", a + "a2", article=lap, terms=["zqxlapsor"]),
           f_rec("source", signal="stage", host="learn.microsoft.com", level=0, needs=1, triggers=["failures"]),
           f_rec("source", signal="stage", host="arxiv.org", level=0, needs=1, triggers=["failures"])]
    w40 = [f_rec("alias", a + "a2", "applied", article=lap, terms=["zqxlapsor"]),
           f_rec("eval", a + "a2", "applied", expect=lap)]
    for run, recs in ((W39_FINDINGS, w39), (W40_FINDINGS, w40)):
        write_store_file(store / "findings" / "2026-09" / f"{run}.jsonl",
                         {"run": run, "pipeline": 2, "retrieval": 4, "kb_commit": "0" * 40,
                          "counts": {"findings": len(recs)}}, recs)
    return store


DIGEST_W39 = """query log digest 2026-W39 (2026-09-21 to 2026-09-27)
lookups: 16 (prompt 5, kb_ask 1, tool_fetch 10)
verdicts: good 3, weak 1, none 2, no verdict 10
judged: answered 1, partly 1, missed 3, not judged 11
misses: 4, fixed: 2 (by the kb since 1, by apply 1, by research 0)
fetches: 13, failed 12, result characters 1079632
usage: 0 of 16 lookups
runs: 1, entries dropped by redaction 2
finding records written: 8
findings by kind and state at the week's end:
  eval: open 1, fixed-since 1, applied 1
  alias: open 1
  expansion: applied 1
  gap: open 1
  source: open 2"""


class TestDigest:
    def test_two_copies_of_one_store_give_identical_output(self, tmp_path):
        outs = []
        for name in ("one", "two"):
            store = digest_store(tmp_path / name / "store")
            assert ql_store.store_problems(store) == []
            p = subprocess.run([sys.executable, QL, "digest", "--store", str(store), "--week", "2026-W39"],
                               capture_output=True, timeout=120, cwd=str(tmp_path / name))
            assert p.returncode == 0, p.stderr
            outs.append(p.stdout)
        assert outs[0] == outs[1]
        assert outs[0].decode("utf-8").replace("\r\n", "\n") == DIGEST_W39 + "\n"

    def test_the_default_week_is_the_newest_entrys(self, tmp_path):
        store = digest_store(tmp_path / "store")
        week, lines_, found = ql_report.digest(store)
        assert (week, "\n".join(lines_), found) == ("2026-W39", DIGEST_W39, True)
        assert ql_report.digest(store) == ql_report.digest(store)  # nothing but the store goes in

    def test_the_weeks_end_bounds_the_findings(self, tmp_path):
        store = digest_store(tmp_path / "store")
        week, lines_, found = ql_report.digest(store, "2026-W40")
        text = "\n".join(lines_)
        assert found and "lookups: 0\n" in text and "finding records written: 2" in text
        assert "  eval: fixed-since 1, applied 2" in text and "  alias: applied 1" in text
        assert "runs: 1," in text  # the fixture's run file, written 2026-09-28

    def test_an_empty_or_missing_store_and_a_bad_week(self, tmp_path):
        assert ql_report.digest(tmp_path / "none") == (None, ["query log digest: the store holds no run file"], False)
        store = digest_store(tmp_path / "store")
        assert ql_report.digest(store, "2026-W30")[2] is False
        with pytest.raises(ValueError):
            ql_report.digest(store, "2026-09-27")
        p = subprocess.run([sys.executable, QL, "digest", "--store", str(store), "--week", "last"], capture_output=True,
                           timeout=120)
        assert p.returncode == 2 and b"not an ISO week" in p.stderr

    def test_digest_superseded_gap_is_not_fixed(self, tmp_path):
        """A gap candidate learn superseded (fixed-since) by an eval finding that apply recorded no-fix is no fix:
        the eval finding stands for the miss, and it is not fixed."""
        store = digest_store(tmp_path / "store")
        a4 = "55555555-0000-4000-8000-0000000000a4"
        recs = [f_rec("gap", a4, "fixed-since", stage="candidate-gap",
                      promotions=[{"from": "miss", "to": "candidate-gap", "by": "learn"}]),
                f_rec("eval", a4, "no-fix", stage="candidate-gap", expect="public/windows/laps.md",
                      promotions=[{"from": "miss", "to": "candidate-gap", "by": "apply"}])]
        run = "20260927T233000Z-0000d3ce"
        write_store_file(store / "findings" / "2026-09" / f"{run}.jsonl",
                         {"run": run, "pipeline": 2, "retrieval": 4, "kb_commit": "0" * 40,
                          "counts": {"findings": len(recs)}}, recs)
        text = "\n".join(ql_report.digest(store, "2026-W39")[1])
        assert "  gap: fixed-since 1" in text and "  eval: open 1, fixed-since 1, applied 1, no-fix 1" in text
        assert "misses: 4, fixed: 2 (by the kb since 1, by apply 1, by research 0)" in text

    def test_distill_sums_result_characters_per_fetch(self):
        import redact
        rows = [{"id": "77777777-0000-4000-8000-000000000001", "ts": "2026-09-27T08:00:00.000Z", "surface": "prompt",
                 "prompt": "kb: laps", "kb_intent": "lookup"}]
        for i, c in enumerate((10, 5, None)):
            rows.append({"id": str(uuid.uuid4()), "ts": f"2026-09-27T08:00:0{i + 1}.000Z", "surface": "fetch",
                         "tool": "WebFetch", "host": "learn.microsoft.com", "path": "/en-us/a", "outcome": "unknown",
                         **({"chars": c} if c is not None else {})})
        entry, _, _ = ql_distill.entry_of(rows, redact.known())
        assert entry["fetches"] == [{"tool": "WebFetch", "host": "learn.microsoft.com", "path": "/en-us/a",
                                     "outcome": "unknown", "n": 3, "chars": 15}]


INTAKE_ITEMS = {  # file stem: (status, links)
    "TK-aaaaaaaa": ("draft", ["fingerprint 111111111111", "detector drift"]),
    "TK-bbbbbbbb": ("draft", ["fingerprint 222222222222", "detector trailers"]),
    "BG-cccccccc": ("todo", ["fingerprint 333333333333", "detector trailers"]),
    "BG-dddddddd": ("done", ["fingerprint 444444444444", "detector ci"]),  # finished: not counted
    "BG-eeeeeeee": ("dropped", ["detector ci"]),  # dropped: not counted
    "TK-ffffffff": ("draft", ["pipeline 7"]),  # filed by hand, no detector link: not counted
}


def intake_backlog(dst, items=INTAKE_ITEMS):
    dst.mkdir(parents=True, exist_ok=True)
    for stem, (status, links) in items.items():
        (dst / f"{stem}.json").write_text(json.dumps({"id": stem, "status": status, "links": links}) + "\n",
                                          encoding="utf-8", newline="\n")
    (dst / "BG-garbage0.json").write_text("{not json", encoding="utf-8")  # unreadable: left out
    return dst


class TestDigestIntake:
    def test_digest_intake_line_counts_the_open_items_by_detector(self, tmp_path):
        d = intake_backlog(tmp_path / "backlog")
        assert ql_report.intake_line(d) == "intake: 3 open (drift 1, trailers 2)"
        assert ql_report.intake_line(tmp_path / "gone") == "intake: none open"
        assert ql_report.intake_line(intake_backlog(tmp_path / "other", {"TK-aaaaaaaa": ("done", ["detector ci"])})) \
            == "intake: none open"

    def test_digest_intake_line_closes_the_digest_when_a_backlog_is_given(self, tmp_path):
        store = digest_store(tmp_path / "store")
        lines = ql_report.digest(store, "2026-W39", intake_backlog(tmp_path / "backlog"))[1]
        assert "\n".join(lines) == DIGEST_W39 + "\nintake: 3 open (drift 1, trailers 2)"
        assert "\n".join(ql_report.digest(store, "2026-W39")[1]) == DIGEST_W39  # no backlog, no line

    def test_digest_intake_line_is_the_hooks_last_line(self, tmp_path, monkeypatch):
        q = tmp_path / "querylog"
        monkeypatch.setattr(ql_report, "places", lambda: (q, q / "config.json"))
        store = digest_store(tmp_path / "store")
        line = ql_report.digest_hook(TestDigestHook.MONDAY, store, intake_backlog(tmp_path / "backlog"))
        assert json.loads(line)["systemMessage"].splitlines()[-1] == "intake: 3 open (drift 1, trailers 2)"

    def test_digest_command_on_the_default_store_ends_with_the_intake_line(self, tmp_path):
        p = subprocess.run([sys.executable, QL, "digest"], capture_output=True, env=querylog_env(tmp_path), timeout=60)
        out = p.stdout.decode("utf-8").splitlines()
        assert p.returncode == 0 and out[-1].startswith("intake: "), out[-3:]

    def test_digest_intake_line_never_runs_a_detector(self, tmp_path, monkeypatch):
        import bl_intake
        monkeypatch.setattr(bl_intake, "collect", lambda *a, **k: pytest.fail("the digest ran the detectors"))
        assert ql_report.intake_line(intake_backlog(tmp_path / "backlog")).startswith("intake: 3 open")


WORK_W39_EARLY = "20260926T090000Z-0000a1ce"  # a second run in ISO week 2026-W39
WORK_W39_BAD = "20260925T090000Z-0000a3ce"  # a third, whose sidecar breaks the work gates
WORK_W40 = "20260929T090000Z-0000a2ce"  # a run in 2026-W40: after the week's end


def wcts(n):
    """The counts of n tokens, all of them uncached input."""
    return {"requests": 1, "in": n, "cw": 0, "cw1h": 0, "cr": 0, "out": 0}


def work_item(item, main=0, sub=0):
    """An item line: `main` tokens of its own prompts, `sub` tokens of subagents routed to it (an Explore group)."""
    line = {"item": item, "prompts": 1 if main else 0, "main": {"claude-opus-5-5": wcts(main)} if main else {}}
    if sub:
        line["sub"] = {"Explore": {"claude-haiku-4-5": wcts(sub)}}
    return line


def write_work_sidecar(store, run, lines):
    """The work sidecar of `run` with `lines`, and a run file of it beside it when the store has none."""
    header = {"run": run, "reader": 1, "counts": {"items": sum(1 for w in lines if "item" in w),
                                                  "shared": sum(1 for w in lines if "items" in w), "missing": 0}}
    if any("overhead" in w for w in lines):
        header["counts"]["overhead"] = sum(1 for w in lines if "overhead" in w)
    month = f"{run[:4]}-{run[4:6]}"
    write_store_file(store / "work" / month / f"{run}.jsonl", header, lines)
    if not (store / month / f"{run}.jsonl").exists():
        write_store_file(store / month / f"{run}.jsonl",
                         {"run": run, "pipeline": 2, "retrieval": 4, "kb_commit": "0" * 40,
                          "counts": {"entries": 0, "dropped": 0, "waiting": 0}}, [])


def work_store(dst):
    """The digest fixture store plus work sidecars: two runs of ISO week 2026-W39 (an item in both), one of 2026-W40,
    and in them a shared line and an overhead line, which no item owns."""
    store = digest_store(dst)
    shared = {"items": ["TK-aaaaaaaa", "TK-bbbbbbbb"], "prompts": 2, "main": {"claude-opus-5-5": wcts(5000)}}
    system = {"overhead": "distill", "calls": 1, "main": {"claude-haiku-4-5": wcts(7000)}}
    write_work_sidecar(store, W39_RUN, [work_item("TK-aaaaaaaa", 600, 400), work_item("TK-bbbbbbbb", 1200),
                                        work_item("TK-cccccccc", 0, 300), work_item("SP-dddddddd", 700),
                                        work_item("TK-ffffffff", 10), shared, system])
    write_work_sidecar(store, WORK_W39_EARLY, [work_item("TK-aaaaaaaa", 200), work_item("BG-eeeeeeee", 50)])
    write_work_sidecar(store, WORK_W40, [work_item("TK-aaaaaaaa", 99999), work_item("TK-gggggggg", 5)])
    assert ql_store.store_problems(store) == []
    return store


def work_part(lines_):
    """The digest lines between its usage line and its runs line: the work lines."""
    start = next(i for i, ln in enumerate(lines_) if ln.startswith("usage:")) + 1
    return lines_[start:next(i for i, ln in enumerate(lines_) if ln.startswith("runs:"))]


DIGEST_W39_WORK = """work: 6 items, tokens 3460 (main 80%, subagents 20%); top 5 by tokens
  TK-aaaaaaaa: 1200 tokens, main 67%, subagents 33%
  TK-bbbbbbbb: 1200 tokens, main 100%, subagents 0%
  SP-dddddddd: 700 tokens, main 100%, subagents 0%
  TK-cccccccc: 300 tokens, main 0%, subagents 100%
  BG-eeeeeeee: 50 tokens, main 100%, subagents 0%"""


class TestDigestWork:
    def test_digest_work_lists_the_weeks_items_by_tokens(self, tmp_path):
        store = work_store(tmp_path / "store")
        week, lines_, found = ql_report.digest(store, "2026-W39")
        assert week == "2026-W39" and found
        assert "\n".join(work_part(lines_)) == DIGEST_W39_WORK  # ties by id, an item's runs summed, W40 left out
        assert "runs: 2," in "\n".join(lines_)

    def test_digest_work_shows_the_share_of_subagents_beside_main(self, tmp_path):
        lines_ = work_part(ql_report.digest(work_store(tmp_path / "store"), "2026-W39")[1])
        assert "  TK-cccccccc: 300 tokens, main 0%, subagents 100%" in lines_  # routed subagents only, no prompt
        assert "  TK-aaaaaaaa: 1200 tokens, main 67%, subagents 33%" in lines_

    def test_digest_work_counts_tokens_as_input_cache_and_output(self, tmp_path):
        store = digest_store(tmp_path / "store")
        counts = {"requests": 3, "in": 10, "cw": 20, "cw1h": 5, "cr": 300, "out": 4000}
        write_work_sidecar(store, W39_RUN, [{"item": "TK-aaaaaaaa", "prompts": 1, "main": {"claude-opus-5-5": counts}}])
        assert work_part(ql_report.digest(store, "2026-W39")[1])[1] == \
            "  TK-aaaaaaaa: 4330 tokens, main 100%, subagents 0%"

    def test_digest_work_lists_the_top_items_only_and_counts_all(self, tmp_path):
        store = digest_store(tmp_path / "store")
        ids = [f"TK-{c * 8}" for c in "abcdefgh"]
        write_work_sidecar(store, W39_RUN, [work_item(i, 100 + n) for n, i in enumerate(ids)])
        part = work_part(ql_report.digest(store, "2026-W39")[1])
        assert ql_report.WORK_TOP == 5 and len(part) == 1 + 5
        assert part[0].startswith("work: 8 items, tokens 828 ") and part[0].endswith("top 5 by tokens")
        assert [ln.split(":")[0].strip() for ln in part[1:]] == ids[::-1][:5]  # most tokens first

    def test_digest_work_leaves_out_shared_and_overhead_lines(self, tmp_path):
        text = "\n".join(ql_report.digest(work_store(tmp_path / "store"), "2026-W39")[1])
        assert "5000" not in text and "7000" not in text and "tokens 3460 " in text

    def test_digest_work_prints_nothing_extra_for_a_week_without_item_lines(self, tmp_path):
        store = digest_store(tmp_path / "store")
        assert "\n".join(ql_report.digest(store, "2026-W39")[1]) == DIGEST_W39  # no sidecar at all
        write_work_sidecar(store, W39_RUN, [{"overhead": "distill", "calls": 1,
                                             "main": {"claude-haiku-4-5": wcts(7)}}])
        assert "\n".join(ql_report.digest(store, "2026-W39")[1]) == DIGEST_W39  # an overhead line is no item
        other = work_store(tmp_path / "other")
        assert not any(ln.startswith("work:") for ln in ql_report.digest(other, "2026-W38")[1])  # no run that week

    def test_digest_work_leaves_out_a_sidecar_that_breaks_the_work_gates(self, tmp_path):
        store = work_store(tmp_path / "store")
        bad = work_item("TK-aaaaaaaa", 888888)
        bad["session"] = "3f2a4c1e-0000-4000-8000-00000000abcd"  # a field a work line never has
        write_work_sidecar(store, WORK_W39_BAD, [bad])
        assert ql_store.work_problems(store) != []  # the store's own gate names it
        lines_ = ql_report.digest(store, "2026-W39")[1]
        assert "\n".join(work_part(lines_)) == DIGEST_W39_WORK
        assert "888888" not in "\n".join(lines_) and "3f2a4c1e" not in "\n".join(lines_)

    def test_digest_work_prints_item_ids_only(self, tmp_path):
        """An id deleted at sprint close has no item file; the line holds the id, never a title or a session."""
        store = work_store(tmp_path / "store")
        for ln in work_part(ql_report.digest(store, "2026-W39")[1])[1:]:
            assert re.fullmatch(r"  (?:EP|ST|TK|SB|BG|SP)-[a-z2-7]{8}: \d+ tokens, main \d+%, subagents \d+%", ln)

    def test_digest_work_two_copies_of_one_store_give_identical_output(self, tmp_path):
        outs = []
        for name in ("one", "two"):
            store = work_store(tmp_path / name / "store")
            p = subprocess.run([sys.executable, QL, "digest", "--store", str(store), "--week", "2026-W39"],
                               capture_output=True, timeout=120, cwd=str(tmp_path / name))
            assert p.returncode == 0, p.stderr
            outs.append(p.stdout)
        assert outs[0] == outs[1] and DIGEST_W39_WORK in outs[0].decode("utf-8").replace("\r\n", "\n")


class TestDigestHook:
    MONDAY = datetime.datetime(2026, 9, 28, 7, 0, tzinfo=datetime.timezone.utc)  # 2026-W40: shows 2026-W39

    @pytest.fixture
    def qdir(self, tmp_path, monkeypatch):
        q = tmp_path / "querylog"
        monkeypatch.setattr(ql_report, "places", lambda: (q, q / "config.json"))
        return q

    def test_the_first_session_of_a_week_shows_last_weeks_digest_once(self, tmp_path, qdir):
        store = digest_store(tmp_path / "store")
        line = ql_report.digest_hook(self.MONDAY, store)
        assert json.loads(line) == {"systemMessage": DIGEST_W39}
        assert (qdir / ql_report.DIGEST_MARKER).read_text(encoding="utf-8") == "2026-W40\n"
        assert ql_report.digest_hook(self.MONDAY + datetime.timedelta(days=6, hours=16), store) is None  # Sunday
        nxt = ql_report.digest_hook(self.MONDAY + datetime.timedelta(days=7), store)  # 2026-W41 shows 2026-W40
        assert json.loads(nxt)["systemMessage"].startswith("query log digest 2026-W40 ")

    def test_off_disabled_empty_and_over_budget_show_nothing(self, tmp_path, qdir, monkeypatch):
        store = digest_store(tmp_path / "store")
        qdir.mkdir(parents=True)
        (qdir / "config.json").write_text('{"mode": "off"}', encoding="utf-8")
        assert ql_report.digest_hook(self.MONDAY, store) is None and not (qdir / ql_report.DIGEST_MARKER).exists()
        (qdir / "config.json").unlink()
        (qdir / "DISABLED").touch()
        assert ql_report.digest_hook(self.MONDAY, store) is None and not (qdir / ql_report.DIGEST_MARKER).exists()
        (qdir / "DISABLED").unlink()
        late = datetime.datetime(2026, 12, 1, tzinfo=datetime.timezone.utc)
        assert ql_report.digest_hook(late, store) is None  # an empty week
        assert (qdir / ql_report.DIGEST_MARKER).exists()
        (qdir / ql_report.DIGEST_MARKER).unlink()
        monkeypatch.setattr(ql_report, "DIGEST_BUDGET_S", -1)  # planted: reading the store took too long
        assert ql_report.digest_hook(self.MONDAY, store) is None
        assert (qdir / ql_report.DIGEST_MARKER).read_text(encoding="utf-8") == "2026-W40\n"  # not tried again

    def test_the_hook_command_prints_at_most_one_json_line_and_exits_0(self, tmp_path):
        t0 = time.monotonic()
        p = subprocess.run([sys.executable, QL, "digest", "--hook"], input=json.dumps(session_start()).encode("utf-8"),
                           capture_output=True, env=querylog_env(tmp_path), timeout=60)
        assert p.returncode == 0 and time.monotonic() - t0 < ql_report.DIGEST_HOOK_TIMEOUT_S, p.stderr
        out = p.stdout.decode("utf-8").strip()
        assert out == "" or list(json.loads(out)) == ["systemMessage"]
        assert (tmp_path / "querylog" / ql_report.DIGEST_MARKER).exists()
        p = subprocess.run([sys.executable, QL, "digest", "--hook"], input=b"not json", capture_output=True,
                           env=querylog_env(tmp_path), timeout=60)
        assert (p.returncode, p.stdout) == (0, b"")  # shown once this week already


class StubRun:
    """git, glab and gh answers for status: origin's url, signed in or not, the open merge requests, the log."""

    def __init__(self, url="git@gitlab.corp.example.com:grp/kb.git", signed=True, mrs=None, log="", api_ok=True):
        self.url, self.signed, self.mrs, self.log, self.api_ok, self.calls = url, signed, mrs or [], log, api_ok, []

    def __call__(self, argv, cwd=None):
        self.calls.append(argv)
        if argv[1:3] == ["remote", "get-url"]:
            return (0, self.url + "\n", "") if self.url else (2, "", "error: No such remote 'origin'")
        if argv[1:2] == ["log"]:
            return 0, self.log, ""
        if argv[1:3] == ["auth", "status"]:
            return (0, "", "") if self.signed else (1, "", "You are not logged into any hosts")
        return (0, json.dumps(self.mrs), "") if self.api_ok else (1, "", "HTTP 401")


def status_lines(store, run):
    said = []
    assert ql_report.status(store, home=str(store.parent), run=run, out=said.append) == 0
    return said


class TestStatus:
    LOG = ("1111111\x1fchore(kb): query log apply 20260927T230000Z-0000d1ce\x1feval, expansion, querylog\x1e\n"
           "2222222\x1frevert: query log commit 3333333aa\x1frevert\x1e\n"
           "4444444\x1fdocs(kb): a person's commit\x1f\x1e\n")

    def test_the_three_lists_on_gitlab(self, tmp_path):
        store = digest_store(tmp_path / "store")
        mrs = [{"iid": 12, "source_branch": "querylog/20260927T230000Z-0000d1ce", "title": "chore(kb): query log apply",
                "web_url": "https://gitlab.corp.example.com/grp/kb/-/merge_requests/12"},
               {"iid": 13, "source_branch": "feature/x", "title": "a person's MR", "web_url": "u"}]
        run = StubRun(mrs=mrs, log=self.LOG)
        said = status_lines(store, run)
        assert said == [
            "open source findings, most result characters first: 2",
            f"  1018432 chars  learn.microsoft.com  stage: level 0, needs 1 (failures)  "
            f"{ql_store.finding_id('source', 'stage', 'learn.microsoft.com')}",
            f"  0 chars  arxiv.org  stage: level 0, needs 1 (failures)  "
            f"{ql_store.finding_id('source', 'stage', 'arxiv.org')}",
            "open conflict merge requests (glab on gitlab.corp.example.com): 1",
            "  !12 querylog/20260927T230000Z-0000d1ce  chore(kb): query log apply  "
            "https://gitlab.corp.example.com/grp/kb/-/merge_requests/12",
            "reverted automatic commits: 1",
            "  2222222 revert: query log commit 3333333aa"]
        assert ["glab", "api", "--hostname", "gitlab.corp.example.com",
                "projects/grp%2Fkb/merge_requests?state=opened&target_branch=main&per_page=100"] in run.calls

    def test_github_lists_pull_requests(self, tmp_path):
        store = digest_store(tmp_path / "store")
        prs = [{"number": 4, "headRefName": "querylog/20260927T230000Z-0000d1ce", "title": "t", "url": "https://x/4"}]
        run = StubRun(url="https://github.com/o/r.git", mrs=prs)
        said = status_lines(store, run)
        assert "open conflict merge requests (gh on github.com): 1" in said
        assert "  #4 querylog/20260927T230000Z-0000d1ce  t  https://x/4" in said
        assert ["gh", "pr", "list", "-R", "github.com/o/r", "--base", "main", "--state", "open",
                "--json", "number,title,headRefName,url", "-L", "100"] in run.calls

    @pytest.mark.parametrize("run,note", [
        (StubRun(signed=False), "not checked: glab is not signed in to gitlab.corp.example.com (You are not logged"),
        (StubRun(api_ok=False), "not checked: glab api failed (HTTP 401)"),
        (StubRun(url=None), "not checked: no remote origin"),
    ])
    def test_merge_requests_are_skipped_with_a_note(self, tmp_path, run, note):
        said = status_lines(digest_store(tmp_path / "store"), run)
        assert any(line.startswith("open conflict merge requests: " + note) for line in said), said
        if not run.signed or not run.url:
            assert not [c for c in run.calls if c[:2] in (["glab", "api"], ["gh", "pr"])]  # no API call

    @pytest.mark.git
    def test_reverted_commits_come_from_the_trailer(self, tmp_path):
        """In a real repository: the KB-Auto trailers of git log, one revert among them."""
        repo = Repo(tmp_path / "clone")
        os.makedirs(repo.path)
        repo.git("init", "-q")
        for text, msg in (("a\n", "chore(kb): query log apply x\n\nKB-Auto: eval"),
                          ("b\n", "revert: query log commit abc\n\nKB-Auto: revert"),
                          ("c\n", "docs: a body that names KB-Auto: revert\n\nno trailer here.\n\nOther: x")):
            repo.write("a.txt", text)
            repo.git("add", "a.txt")
            repo.git("commit", "-q", "-m", msg)

        def run(argv, cwd=None):
            p = subprocess.run(argv, cwd=cwd, env=repo.env, capture_output=True, text=True, encoding="utf-8")
            return p.returncode, p.stdout, p.stderr
        got = ql_report.reverted_commits(repo.path, run)
        assert [s for _, s in got] == ["revert: query log commit abc"]


# ---------------------------------------------------------------- show (Reporting, Show)

SHOW_USAGE_ENTRY = "66666666-0000-4000-8000-0000000000a1"  # the W39 run file's one entry, given a usage line
SHOW_LAPS_ENTRY = "55555555-0000-4000-8000-0000000000a2"  # an entry the findings of the fixture name


def usage_cts(**kw):
    return {"requests": 2, "in": 10, "cw": 100, "cw1h": 100, "cr": 1000, "out": 50, **kw}


def show_store(dst):
    """The digest fixture store plus the usage sidecar of its W39 run: one line, with a subagent group and a cut."""
    store = digest_store(dst)
    line = {"id": SHOW_USAGE_ENTRY, "main": {"claude-opus-5-5": usage_cts()},
            "sub": {"Explore": {"claude-haiku-4-5": usage_cts(**{"in": 1, "cw": 2, "cr": 3, "out": 4, "requests": 1,
                                                              "cw1h": 0})}},
            "start": 500, "steps": [{"tools": [{"tool": "kb_pack", "ok": True, "chars": 700}], "grow": 300}], "cut": 2}
    write_store_file(store / "usage" / "2026-09" / f"{W39_RUN}.jsonl",
                     {"run": W39_RUN, "reader": 1, "counts": {"entries": 1, "missing": 0}}, [line])
    assert ql_store.store_problems(store) == [] and ql_store.usage_problems(store) == []
    return store


def run_show(*args, store=None, env=None, cwd=None):
    """(exit code, stdout, stderr) of `querylog.py show ARGS` (--store STORE) in a subprocess."""
    argv = [sys.executable, QL, "show", *args] + (["--store", str(store)] if store else [])
    p = subprocess.run(argv, capture_output=True, timeout=120, env=env, cwd=str(cwd) if cwd else None)
    return p.returncode, p.stdout.decode("utf-8").replace("\r\n", "\n"), p.stderr.decode("utf-8").replace("\r\n", "\n")


def tree_bytes(store):
    return {p.relative_to(store).as_posix(): p.read_bytes() for p in sorted(store.rglob("*")) if p.is_file()}


class TestQuerylogShow:
    def test_querylog_show_run_prints_the_header_and_one_line_per_entry(self, tmp_path):
        store = show_store(tmp_path / "store")
        rc, out, err = run_show("--run", W39_RUN, store=store)
        assert (rc, err) == (0, "")
        assert out == (f"run {W39_RUN}: pipeline 2, retrieval 4, kb_commit 000000000000\n"
                       "counts: entries 1, dropped 2, waiting 0\n"
                       "usage sidecar: yes\n"
                       "entries: 1\n"
                       f"  {SHOW_USAGE_ENTRY} kb_ask 2026-09-27 good - 0 lines  Which port does WinRM over HTTPS use?\n")
        rc, out, _ = run_show("--run", "20260928", "--limit", "3", store=store)  # the start of an id; capped
        lines_ = out.splitlines()
        assert rc == 0 and lines_[0].startswith("run 20260928T130000Z-0000beef: ") and "usage sidecar: no" in lines_
        assert lines_[4].startswith("  55555555-0000-4000-8000-0000000000a1 prompt 2026-09-27 weak missed 1 lines  ")
        assert lines_[-1] == "... 12 more (--limit 0 prints all)" and len(lines_) == 8
        assert len(run_show("--run", "20260928", "--limit", "0", store=store)[1].splitlines()) == 4 + 15

    def test_querylog_show_entry_prints_every_field_its_findings_and_usage(self, tmp_path):
        store = show_store(tmp_path / "store")
        rc, out, err = run_show("--entry", SHOW_LAPS_ENTRY, store=store)
        assert (rc, err) == (0, "")
        assert out == (f"entry {SHOW_LAPS_ENTRY} (run 20260928T130000Z-0000beef)\n"
                       "surface: prompt\nday: 2026-09-27\ntools: kb_pack\n"
                       "question: How long is a zqxlapsor plomkinator secret by default?\n"
                       "verdict: none\narticles: public/windows/laps.md\n"
                       "citations: 1\n  public/windows/laps.md:12 DOC none\n"
                       "cited: pack\njudged: partly\nbest: public/windows/laps.md\n"
                       "findings: 2\n"
                       f"  {ql_store.finding_id('eval', SHOW_LAPS_ENTRY)} eval applied stage=miss "
                       "expect=public/windows/laps.md\n"
                       f"  {ql_store.finding_id('alias', SHOW_LAPS_ENTRY)} alias applied stage=miss "
                       "article=public/windows/laps.md terms=zqxlapsor\n"
                       "usage: none\n")
        out = run_show("--entry", SHOW_USAGE_ENTRY[:8], store=store)[1]  # the start of an id names one entry
        assert out.endswith("findings: 0\nusage: yes, in the usage sidecar of its run\n")

    def test_querylog_show_entry_prints_the_fetches_of_an_entry(self, tmp_path):
        store = show_store(tmp_path / "store")
        e = {"id": "77777777-0000-4000-8000-000000000001", "surface": "prompt", "day": "2026-09-27",
             "question": "q", "fetches": [{"tool": "WebFetch", "host": "learn.microsoft.com", "path": "/en-us/a",
                                           "outcome": "unknown", "n": 2, "chars": 15}]}
        run = "20260929T000000Z-0000feed"
        write_store_file(store / "2026-09" / f"{run}.jsonl",
                         {"run": run, "pipeline": 5, "retrieval": 5, "kb_commit": "0" * 40,
                          "counts": {"entries": 1, "dropped": 0, "waiting": 0}}, [e])
        out = run_show("--entry", "77777777", store=store)[1]
        assert "fetches: 1\n  tool=WebFetch host=learn.microsoft.com path=/en-us/a outcome=unknown n=2 chars=15\n" in out

    def test_querylog_show_findings_filters_by_kind_article_and_state(self, tmp_path):
        store = show_store(tmp_path / "store")
        rc, out, err = run_show("--findings", store=store)
        lines_ = out.splitlines()
        assert (rc, err) == (0, "") and lines_[0] == "findings: 8"  # every finding once, in its last state
        assert [ln.split()[1] for ln in lines_[1:]] == ["eval"] * 3 + ["alias", "expansion", "gap", "source", "source"]
        assert [ln.split()[2] for ln in lines_[1:4]] == ["fixed-since", "applied", "applied"]  # a2's later record wins
        out = run_show("--findings", "--kind", "alias", store=store)[1]
        assert out == (f"findings: 1 (kind alias)\n{ql_store.finding_id('alias', SHOW_LAPS_ENTRY)} alias applied "
                       f"stage=miss entry={SHOW_LAPS_ENTRY} article=public/windows/laps.md terms=zqxlapsor\n")
        out = run_show("--findings", "--article", "laps.md", "--state", "applied", store=store)[1]
        assert out.splitlines()[0] == "findings: 2 (article laps.md, state applied)"
        full = run_show("--findings", "--article", "public/windows/laps.md", "--state", "applied", store=store)[1]
        assert full.splitlines()[1:] == out.splitlines()[1:]  # the tail and the whole path name one article
        assert run_show("--findings", "--article", "nothing.md", store=store)[1] == "findings: 0 (article nothing.md)\n"
        capped = run_show("--findings", "--limit", "2", store=store)[1].splitlines()
        assert len(capped) == 4 and capped[-1] == "... 6 more (narrow with --kind, --article, --state, or --limit 0)"
        source = run_show("--findings", "--kind", "source", store=store)[1].splitlines()
        assert source[0] == "findings: 2 (kind source)"
        assert all(" source open " in ln and "signal=stage host=" in ln and "triggers=failures" in ln
                   for ln in source[1:])

    def test_querylog_show_usage_prints_the_run_sidecar(self, tmp_path):
        store = show_store(tmp_path / "store")
        rc, out, err = run_show("--usage", "20260927", store=store)
        assert (rc, err) == (0, "")
        assert out == (f"usage {W39_RUN}: reader 1, entries 1, missing 0\n"
                       f"  {SHOW_USAGE_ENTRY} input 1116 (uncached 11, cache write 102, cache read 1003), "
                       "output 54, requests 3, subagents input 6, steps 1 (+2 cut)\n")
        rc, out, _ = run_show("--usage", "20260928T130000Z-0000beef", store=store)  # a run without a sidecar
        assert rc == 0 and out == "usage 20260928T130000Z-0000beef: no sidecar (no entry of the run had a usage row)\n"

    def test_querylog_show_spool_prints_kinds_of_rows_and_never_their_text(self, tmp_path):
        from ql_testkit import plant_spool, NOW
        plant_spool(tmp_path / "querylog", NOW)
        env = querylog_env(tmp_path)
        rc, out, err = run_show("--spool", env=env)
        assert (rc, err) == (0, "")
        assert out.splitlines() == [
            "spool: 4 files, 19 rows",
            "  session 1, ended: 11 rows (prompt 4, kb_hook 2, mcp 1, fetch 3, stop 1), days 2026-09-27",
            "  session 2, open: 2 rows (prompt 1, mcp 1), days 2026-09-26",
            "  session 3, open: 2 rows (prompt 1, kb_hook 1), days 2026-09-28",
            "  tools 2026-09-27: 4 rows (kb_ask 2, tool_fetch 2), days 2026-09-27",
            "rows whose id the committed store holds: 0"]
        # planted: every string a spool row holds that the store does not (text, ids, hosts, paths, times) is absent
        raw = set()
        for f in (tmp_path / "querylog" / "spool").glob("*.jsonl"):
            for ln in f.read_text(encoding="utf-8").splitlines():
                row = json.loads(ln)
                for k in ("prompt", "answer", "question", "session_id", "prompt_id", "host", "path", "args", "id",
                          "ts"):
                    v = row.get(k)
                    raw |= {x for x in ([v] if isinstance(v, str) else []) if len(x) > 3}
        assert len(raw) > 20 and not [x for x in raw if x in out], [x for x in raw if x in out]
        assert run_show("--spool", env=querylog_env(tmp_path / "empty"))[1] == "spool: empty\n"

    def test_querylog_show_spool_counts_the_rows_the_store_holds(self, tmp_path, monkeypatch):
        from ql_testkit import plant_spool, NOW
        sp = plant_spool(tmp_path / "querylog", NOW)
        store = show_store(tmp_path / "store")
        held = ql_store.store_entries(store)[0][1]["id"]
        row = {"id": held, "ts": "2026-09-27T09:00:00.000Z", "surface": "kb_ask", "question": "q"}
        (sp / "tools-2026-09-30.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8", newline="\n")
        monkeypatch.setattr(ql_report, "STORE", store)
        said = []
        ql_report.show_spool(said.append, sp)
        assert said[-1] == "rows whose id the committed store holds: 1" and said[0] == "spool: 5 files, 20 rows"

    def test_querylog_show_reads_only_and_is_the_same_in_every_copy(self, tmp_path, monkeypatch):
        trees = []
        for name in ("one", "two"):
            store = show_store(tmp_path / name / "store")
            before = tree_bytes(store)
            outs = [run_show(*a, store=store, cwd=tmp_path / name)[1] for a in (
                ("--run", W39_RUN), ("--entry", SHOW_LAPS_ENTRY), ("--findings",), ("--usage", W39_RUN))]
            assert tree_bytes(store) == before  # nothing written, not even a marker
            trees.append(outs)
        assert trees[0] == trees[1] and all(trees[0])

        def refuse(*a, **k):
            raise AssertionError("show started a process")
        for name in ("run", "Popen"):
            monkeypatch.setattr(subprocess, name, refuse)
        store = show_store(tmp_path / "three" / "store")
        said = []
        for kw in ({"run": W39_RUN}, {"entry": SHOW_LAPS_ENTRY}, {"findings": True}, {"usage": W39_RUN}):
            assert ql_report.show(store, out=said.append, **kw) == 0  # no model, no network, no git

    def test_querylog_show_over_the_committed_store_reads_every_run_and_entry(self):
        import ql_base
        store = ql_base.STORE
        said = []
        for p in ql_store.run_files(store):
            assert ql_report.show(store, run=p.stem, limit=0, out=said.append) == 0, p.name
        for _, e in ql_store.store_entries(store):
            assert ql_report.show(store, entry=e["id"], out=said.append) == 0, e["id"]
        for run in ql_store.run_ids(store):
            assert ql_report.show(store, usage=run, limit=0, out=said.append) == 0, run
        assert ql_report.show(store, findings=True, limit=0, out=said.append) == 0

    @pytest.mark.parametrize("args,rule", [
        (["--run", "19990101"], "unknown run '19990101': no run id of the store starts with it"),
        (["--run", "2026"], "run '2026' is ambiguous: 2 ids start with it"),
        (["--run", "../x"], "run '../x' is not an id: it is letters, digits and hyphens"),
        (["--entry", "ffffffff"], "unknown entry 'ffffffff': no entry id of the store starts with it"),
        (["--entry", "55555555-0000-4000-8000-0000000000"], "entry '55555555-0000-4000-8000-0000000000' is ambiguous"),
        (["--usage", "nothing"], "unknown run 'nothing'"),
        (["--findings", "--kind", "bogus"], "--kind 'bogus' is not a finding kind: eval, alias, expansion, gap, source"),
        (["--findings", "--state", "open,applied"], "--state 'open,applied' is not a finding state: open, "),
        (["--findings", "--article", "laps md"], "--article 'laps md' is not an article path"),
        (["--run", "2026", "--kind", "gap"], "--kind, --article and --state filter --findings only"),
        (["--findings", "--limit", "-1"], "--limit is a number of lines, 0 or more"),
        (["--spool", "--store", "x"], "--spool reads the local spool, which is no store: --store does not apply"),
    ])
    def test_querylog_show_refuses_a_bad_request_with_exit_2_and_the_rule(self, tmp_path, args, rule):
        store = show_store(tmp_path / "store")
        before = tree_bytes(store)
        rc, out, err = run_show(*args, store=None if "--spool" in args else store)
        assert (rc, out) == (2, "") and err.startswith("show: refused: ") and rule in err, err
        assert tree_bytes(store) == before

    def test_querylog_show_refuses_a_missing_store_and_a_wrong_choice_of_what_to_show(self, tmp_path):
        rc, out, err = run_show("--findings", store=tmp_path / "none")
        assert (rc, out) == (2, "") and "--store names no directory" in err
        for args in ([], ["--run", "x", "--findings"], ["--spool", "--usage", "x"]):
            rc, out, err = run_show(*args)
            assert (rc, out) == (2, "") and ("not allowed with argument" in err or "one of the arguments" in err), err
        said = []
        assert ql_report.show(findings=True, run="x", out=said.append, err=said.append) == 2
        assert said == ["show: refused: give one of --run, --entry, --findings, --usage or --spool, "
                        "not --run and --findings"]

    def test_querylog_show_an_empty_store_answers_with_nothing_and_exits_0(self, tmp_path):
        (tmp_path / "empty").mkdir()
        assert run_show("--findings", store=tmp_path / "empty")[:2] == (0, "findings: 0\n")
        assert run_show("--run", "2026", store=tmp_path / "empty")[0] == 2  # an unknown run is a refusal


def ops_row(n, event, **kv):
    return {"id": f"00000000-0000-4000-8000-{n:012d}", "ts": "2026-09-27T10:00:00.000Z", "event": event, **kv}


def write_ops_sidecar(store, run, rows):
    month = f"{run[:4]}-{run[4:6]}"
    write_store_file(store / "ops" / month / f"{run}.jsonl", {"run": run, "counts": {"rows": len(rows)}}, rows)
    if not (store / month / f"{run}.jsonl").exists():
        write_store_file(store / month / f"{run}.jsonl",
                         {"run": run, "pipeline": 2, "retrieval": 4, "kb_commit": "0" * 40,
                          "counts": {"entries": 0, "dropped": 0, "waiting": 0}}, [])


OPS_W39 = [ops_row(1, "land.end", item="TK-aaaaaaaa", exit=0, ms=1000),
           ops_row(2, "land.end", item="TK-bbbbbbbb", exit=1, ms=3000),
           ops_row(3, "land.end", item="TK-cccccccc", exit=0, ms=2000),
           ops_row(4, "test.run", mode="changed", ms=500, exit=0),
           ops_row(5, "done.refused", item="TK-aaaaaaaa", reasons=["uncommitted"], ms=10),
           ops_row(6, "agent.run", group="kb-worker", ms=9000),
           ops_row(7, "call.tool", tool="bash", group="main", outcome="ok", size="lt1k", **{"class": "git.status"}),
           ops_row(8, "call.tool", tool="bash", group="main", outcome="error", size="empty", **{"class": "git.status"}),
           ops_row(9, "call.tool", tool="kb_pack", group="main", outcome="interrupt", size="empty"),
           ops_row(10, "compact.pre", trigger="auto", group="main")]
DIGEST_W39_OPS = """ops: 10 rows (agent.run 1, call.tool 3, compact.pre 1, done.refused 1, land.end 3, test.run 1)
  land.end: 3, failed 1, median 2000 ms
  test.run: 1, failed 0, median 500 ms
  done.refused: 1
  agent.run: 1 (kb-worker 1)
  call.tool: 3 calls, errors 1, interrupts 1; top classes: git.status 2, kb_pack 1
  compact.pre: 1"""


def ops_part(lines_):
    start = next((i for i, ln in enumerate(lines_) if ln.startswith("ops:")), None)
    return [] if start is None else lines_[start:next(i for i, ln in enumerate(lines_) if ln.startswith("runs:"))]


class TestDigestOps:
    def test_ql_report_ops_block(self, tmp_path):
        """ST-mbnahtlc: the digest prints one ops block per week from the committed ops sidecars: rows by event, the
        land, gate and test-run counts, failures and median ms, refused dones, agent runs by group, the call census
        with its top classes and the hook events; a sidecar of another week is left out, and one that breaks the ops
        gates is left out whole."""
        store = digest_store(tmp_path / "store")
        write_ops_sidecar(store, W39_RUN, OPS_W39)
        write_ops_sidecar(store, WORK_W40, [ops_row(11, "land.end", item="TK-dddddddd", exit=0, ms=5)])
        assert ql_store.store_problems(store) == []
        assert "\n".join(ops_part(ql_report.digest(store, "2026-W39")[1])) == DIGEST_W39_OPS
        write_ops_sidecar(store, WORK_W39_EARLY, [ops_row(12, "land.end", item="TK-eeeeeeee", exit=0, ms=5, extra="x")])
        assert "\n".join(ops_part(ql_report.digest(store, "2026-W39")[1])) == DIGEST_W39_OPS  # the broken file is out

    def test_run_row_selects_nothing_in_digest(self, tmp_path):
        """BG-nf6gcqsz: a test.run row with pytest's exit 5 (no test selected) is no failure in the ops block; it is
        counted as `selected nothing`, and a real failure (exit 1) still is one."""
        store = digest_store(tmp_path / "store")
        write_ops_sidecar(store, W39_RUN, [ops_row(1, "test.run", mode="keyword", ms=100, exit=5),
                                           ops_row(2, "test.run", mode="keyword", ms=300, exit=5),
                                           ops_row(3, "test.run", mode="full", ms=900, exit=1)])
        lines = ops_part(ql_report.digest(store, "2026-W39")[1])
        assert "  test.run: 3, failed 1, median 300 ms, selected nothing 2" in lines, lines

    def test_ql_report_ops_block_stable(self, tmp_path):
        """A second digest on unchanged inputs prints the same lines, and a week without ops rows prints no block."""
        store = digest_store(tmp_path / "store")
        assert ops_part(ql_report.digest(store, "2026-W39")[1]) == []
        write_ops_sidecar(store, W39_RUN, OPS_W39)
        assert ql_report.digest(store, "2026-W39") == ql_report.digest(store, "2026-W39")
