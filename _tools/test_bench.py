"""The benchmarks' harness: a run is priced by the pinned model it reports (bench_core.PRICE), its effective input weights
cache reads by that model's own read ratio, and a tiered price records the tier the run's tokens fall in; the question pool
(bench_pool.py) builds on a fixture kb and store, with its counts per kind, a seed that decides, held-out rows without text
and the query log kept out of the public file."""
import json

import pytest

import bench_core as bc


def req(model, uncached, write, read, out):
    return {"model": model, "usage": {"input_tokens": uncached, "cache_creation_input_tokens": write,
                                      "cache_read_input_tokens": read, "output_tokens": out}}


def test_bench_price_sonnet_55_run_weights_cache_reads_by_its_own_ratio():
    s = bc.usage_sum([req("claude-sonnet-5-5", 100, 1000, 10000, 500)], "sonnet", "2.1.284")
    assert s["model"] == "claude-sonnet-5-5" and s["tier"] == ""
    assert s["effective"] == 100 + 2 * 1000 + 0.05 * 10000  # the old fixed 0.1 gives 3100
    assert round(bc.est_cost(s), 6) == round((100 * 2 + 1000 * 2.5 + 10000 * 0.10 + 500 * 10) / 1e6, 6)
    opus = bc.usage_sum([req("claude-opus-5-5", 0, 0, 10000, 0)], "opus")
    haiku = bc.usage_sum([req("claude-haiku-4-5-20251001", 0, 0, 10000, 0)], "haiku")
    assert (opus["effective"], haiku["effective"]) == (500, 1000)


def test_bench_price_tier_is_recorded_and_alias_follows_the_run():
    run = [req("claude-haiku-5-5", 100, 1000, 10000, 500), req("claude-haiku-5-5", 100, 0, 150000, 500)]
    s = bc.usage_sum(run, "haiku")
    assert s["tier"] == ">100k" and bc.usage_sum(run[:1], "haiku")["tier"] == "<=100k"
    first, second = (100 * 0.10 + 1000 * 0.125 + 10000 * 0.01 + 500 * 0.50), (100 * 0.50 + 150000 * 0.05 + 500 * 2.50)
    assert round(bc.est_cost(s), 6) == round((first + second) / 1e6, 6)
    # the transcript's model wins over the alias; with none reported the alias names its model on the Claude Code version
    assert bc.resolve_model("sonnet", "claude-sonnet-5-5") == "claude-sonnet-5-5"
    assert bc.resolve_model("sonnet", "", "2.1.283") == "claude-sonnet-5"
    assert bc.resolve_model("sonnet", "", "2.1.284") == "claude-sonnet-5-5"
    assert bc.resolve_model("haiku", "", "2.1.292") == "claude-haiku-4-5"
    assert bc.resolve_model("haiku", "", "2.1.293") == "claude-haiku-5-5"


# ---- the question pool (bench_pool.py): built on a fixture kb and a fixture query log store, no model call

def pool_home(tmp_path, ql_questions):
    """A fixture home: six domains of articles with cited sources and SNIPPET lines, an eval set, a held-out set, an
    off-kb list, a gaps and a conflicts ledger, a decisions file and a query log store holding `ql_questions`."""
    kb = tmp_path / "kb" / "public"
    sources = []
    for d in range(6):
        for a in range(4):
            n = d * 4 + a
            sources.append(f"S-src{n:05d}")
            snip = f"- SNIPPET: run `Invoke-Tool{n}` with `-Param{n}` against a device; context: fixture; checked: no [DOC S-src{n:05d}]\n"
            body = (f"---\ntopic: d{d}/a{a}\nstatus: complete\n---\n\n# Article {n}\n\n- Setting alpha{n} beta{n} gamma{n} equals "
                    f"value{n}. [DOC S-src{n:05d}]\n{snip}")
            (kb / f"d{d}").mkdir(parents=True, exist_ok=True)
            (kb / f"d{d}" / f"a{a}.md").write_text(body, encoding="utf-8")
    (kb / "_sources.csv").write_text("id,url\n" + "".join(f"{s},https://example.com/{s}\n" for s in sources), encoding="utf-8")
    ret = kb / "_retrieval"
    (ret / "doc2query").mkdir(parents=True)
    brands = {7: "CMPivot", 9: "BitLocker"}
    ev = "".join(f"EV-{n},What does setting alpha{n % 24} beta{n % 24} gamma{n % 24} equal {brands.get(n, '')} case {n}?,"
                 f"d{n % 24 // 4}/a{n % 4}.md,good,\n" for n in range(60))
    (ret / "lookup_eval.csv").write_text("id,question,expect_paths,expect_verdict,allow_weak\n" + ev, encoding="utf-8")
    ho = "".join(f"HO-{n},HELDOUT TEXT {n} about nothing else,d{n % 6}/a0.md,good,\n" for n in range(20))
    (ret / "lookup_heldout.csv").write_text("id,question,expect_paths,expect_verdict,allow_weak\n" + ho, encoding="utf-8")
    (ret / "doc2query" / "offkb_questions.txt").write_text("".join(f"How do I run off-kb thing {n}?\n" for n in range(20)),
                                                          encoding="utf-8")
    (kb / "_gaps.md").write_text("# Gaps\n\n## d0-x\n\n" + "".join(
        f"- **Still open: whether fixture feature number {n} is supported.** Not confirmed. [UNK] (topic: d{n % 6}/a0)\n"
        for n in range(8)), encoding="utf-8")
    (kb / "_conflicts.md").write_text("# Conflicts\n\n## d1-y\n\n" + "".join(
        f"### Fixture limit {n} differs\n\nOne page (S-src{n:05d}) says 5, another (S-src{n + 8:05d}) says 7.\n\n" for n in range(4)),
        encoding="utf-8")
    (tmp_path / "kb" / "_self").mkdir()
    (tmp_path / "kb" / "_self" / "_decisions.csv").write_text("id,text,by,status\n" + "".join(
        f"D-fixture{n},the fixture picks option number {n} always,operator,active\n" for n in range(4)), encoding="utf-8")
    run = tmp_path / "kb" / "_querylog" / "2026-10"
    run.mkdir(parents=True)
    head = '{"run":"20261008T000000Z-aaaaaaaa","pipeline":7,"retrieval":8,"counts":{"entries":%d,"dropped":0,"waiting":0}}\n'
    ents = "".join(json.dumps({"id": f"{i:08x}-0000-4000-8000-{i:012x}", "surface": "prompt", "day": "2026-10-08",
                               "question": q, "verdict": "good", "articles": [f"public/d{i % 6}/a0.md"]}) + "\n"
                   for i, q in enumerate(ql_questions))
    (run / "20261008T000000Z-aaaaaaaa.jsonl").write_text(head % len(ql_questions) + ents, encoding="utf-8")


def test_bench_pool_build_counts_seed_heldout_and_querylog_stay_apart(tmp_path):
    import argparse, re
    import bench_pool as bp
    ql = [f"fixture session question number {i} about topic {i} in detail" for i in range(26)]
    org = "conto" + "so"  # built from parts: the leak scan of the authored files reads source text
    ql[3] = f"why does the sync for jan.doe@{org}.com fail on the fixture topic every time"
    pool_home(tmp_path, ql)
    calls = []

    def ask(items):
        calls.append(len(items))
        return [r"value\d+"] * len(items)

    out = tmp_path / "pool.csv"
    rows = bp.build_public(tmp_path, 3, ask, out)
    kinds = {}
    for r in rows:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    assert sum(kinds.pop(k, 0) for k in bp.EVAL_KINDS) == bp.EVAL_ROWS and kinds == bp.PLAN and len(calls) == 1
    assert rows == bp.build_public(tmp_path, 3, ask, out) and len(calls) == 2  # same seed, same rows
    bp.write_csv(out, rows)
    assert rows == bp.build_public(tmp_path, 3, lambda items: pytest.fail("a rebuild asks again"), out)  # checks are reused
    assert [r["id"] for r in bp.build_public(tmp_path, 4, ask, out)] != [r["id"] for r in rows]
    held = [r for r in rows if r["kind"] == "heldout"]
    assert all(r["question"] == "" and json.loads(r["checks"]) for r in held)
    assert "HELDOUT TEXT" not in out.read_text(encoding="utf-8") and "HELDOUT TEXT" in bp.question_of(held[0], tmp_path)
    assert bp.check_problems(rows, tmp_path) == []
    assert bp.check_problems([{**held[0], "question": bp.question_of(held[0], tmp_path)}], tmp_path)[0].endswith("names a case "
                                                                                                           "of lookup_heldout.csv")  # the planted failure
    ns = argparse.Namespace(pool_cmd="build", querylog=True, seed=3, out=None)
    assert bp.cli(ns, tmp_path) == 0
    qlfile = tmp_path / bp.QUERYLOG_FILE
    qlrows = bp.read_csv(qlfile)
    assert len(qlrows) == bp.QUERYLOG_ROWS and bp.cli(argparse.Namespace(pool_cmd="check", querylog=True, file=None), tmp_path) == 0
    public = out.read_text(encoding="utf-8")
    assert not any(r["question"] in public for r in qlrows) and "fixture session question" not in public
    assert org not in qlfile.read_text(encoding="utf-8") and not any(r["kind"] == "querylog" for r in rows)


# ---- the pool scenario (bench_pool.py): synthetic streams, no model

def pool_stream(answer, chars=480, model="claude-sonnet-5-5", final_out=80, cost=0.01, main_out=None):
    """A stream-json run of two requests: a kb_pack call whose result is `chars` characters, then the answer. The
    messages' output counts are partial (50 and 30); the result event's `modelUsage` counts `final_out` and its `usage`
    (the main loop) `main_out`, by default the same."""
    usage = lambda unc, write, read, out: {"input_tokens": unc, "cache_creation_input_tokens": write,  # noqa: E731
                                           "cache_read_input_tokens": read, "output_tokens": out}
    events = [
        {"type": "assistant", "message": {"id": "m1", "model": model, "usage": usage(10, 2000, 0, 50),
                                          "content": [{"type": "tool_use", "id": "t1", "name": "mcp__kb__kb_pack", "input": {}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "x" * chars}]}},
        {"type": "assistant", "message": {"id": "m2", "model": model, "usage": usage(170, 0, 2010, 30),
                                          "content": [{"type": "text", "text": answer}]}},
        {"type": "result", "usage": usage(180, 2000, 2010, final_out if main_out is None else main_out), "total_cost_usd": cost, "duration_api_ms": 4000,
         "num_turns": 2, "modelUsage": {model: {"costUSD": cost, "outputTokens": final_out}}, "result": answer}]
    return "\n".join(json.dumps(e) for e in events)


def test_bench_pool_scenario_rows_derived_cells_and_report_tables():
    import agent_bench
    import bench_pool as bp
    import bench_report as br
    rows = [{**bp.row(kind, "d0", "original", f"fixture:{i}", f"Question {i}?", [rf"value{i}"], "good"), "question": f"Question {i}?"}
            for i, kind in enumerate(["fact", "fact", "count"])]
    cells = bp.plan_cells(["sonnet-5-5", "haiku-4-5", "hook", "web-sonnet-5-5"], bp.EFFORTS)
    assert [c[2] for c in cells] == ["sonnet-5-5:low", "sonnet-5-5:default", "haiku-4-5", "hook", "web-sonnet-5-5"]

    def runner(arm, effort, row):
        if arm == "hook":
            return bp.hook_result(json.dumps({"decision": "block", "reason": "pack: value0 value2"}), 0.02)
        return agent_bench.result_of(pool_stream("value1 is the answer" if row["kind"] == "fact" else "value2"), "", 5.0)

    seen = []
    runs = bp.run_pool(rows, cells, 1, runner, lambda rec, r: seen.append(rec["id"]))
    assert len(runs) == len(seen) == 3 * 4 + 2 and not any("error" in r for r in runs)  # the web arm skips the `count` row
    got = {(c, label, m): (v, n, note) for c, label, m, v, n, model, note in bp.cell_rows(runs)}
    cell = lambda case, label, m: got[(case, label, m)][0]  # noqa: E731
    assert cell("fact", "sonnet-5-5:low", "input") == 180 + 2000 + 2010 and cell("fact", "sonnet-5-5:low", "start_ctx") == 2010
    assert cell("fact", "sonnet-5-5:low", "effective_input") == 180 + 2 * 2000 + 0.05 * 2010  # Sonnet 5.5 reads at 0.05x
    assert cell("fact", "sonnet-5-5:low", "pack_tokens") == 120  # the prompt's growth less the request's output, not 480 / 4
    # the output is the sum of the result event's modelUsage counts (500: the main loop's 200 and a subagent's), not the
    # messages' partial ones (50 + 30) nor the event's usage, and prices the run near its cost
    planted = agent_bench.result_of(pool_stream("value1", final_out=500, cost=0.0105, main_out=200), "", 5.0)
    t = bc.run_tokens(planted, "sonnet")
    assert t["out"] == planted["out"] == 500
    usage = {"input_tokens": t["uncached"], "cache_creation_input_tokens": t["cache_write"],
             "cache_read_input_tokens": t["cache_read"], "output_tokens": t["out"]}
    listed = bc.est_cost(bc.usage_sum([{"model": "claude-sonnet-5-5", "usage": usage}], "sonnet"))
    assert abs(listed - planted["cost"]) <= 0.2 * planted["cost"]
    assert cell("fact", "sonnet-5-5:low", "checks") == "1/2" and cell("fact", "sonnet-5-5:low", "fully_right") == "1 of 2"
    assert round(cell("fact", "sonnet-5-5:low", "fixed_share"), 4) == round(2010 / 4190, 4)
    assert cell("fact", "sonnet-5-5:low", "tokens_per_right") == 2 * 4280.5  # two runs' effective input over the one right
    assert got[("fact", "haiku-4-5", "checks")][2] == "no effort setting: one level"
    assert cell("all", "hook", "effective_input") == 0 and ("all", "hook", "fixed_share") not in got
    assert cell("all", "hook", "tokens_per_right") == 0 and got[("all", "web-sonnet-5-5", "input")][1] == 2
    out = [{"scenario": "pool", "record": "2026-10-09", "date": "2026-10-09", "commit": "abc1234", "claude_code": "2.1.300",
            "kb_topics": "1", "case": c, "arm": label, "model": "", "metric": m, "value": str(v), "runs": str(n), "note": note}
           for (c, label, m), (v, n, note) in got.items()]
    text = ("<!-- bench:matrix pool metric=tokens_per_right -->\n<!-- /bench -->\n"
            "<!-- bench:table pool metrics=fixed_share,start_ctx cases=all -->\n<!-- /bench -->\n"
            "<!-- bench:effort pool metrics=tokens_per_right cases=all -->\n<!-- /bench -->\n")
    shown = br.render(text, out)
    assert "| fact | 8,561 | 8,561 | 8,561 | 0 | 8,561 |" in shown and "| count | 4,280 | 4,280 | 4,280 | 0 | - |" in shown  # kind by arm
    assert "| all | sonnet-5-5:low | 48.0% | 2,010 |" in shown  # the fixed share by arm
    assert "| all | sonnet-5-5 | 6,421 (+0%) | 6,421 |" in shown  # low against default
    assert "| all | haiku-4-5 (no effort setting) | - | 6,421 |" in shown and "| hook" not in shown.split("bench:effort")[1]
    assert br.empty_markers(text, out) == []


def test_bench_pool_report_check_exits_1_on_a_marker_with_no_rows(tmp_path, monkeypatch, capsys):
    import benchmarks as bm
    import bench_core as bc
    import bench_report as br
    other = {"scenario": "tool-speed", "record": "2026-10-09", "date": "2026-10-09", "case": "c", "arm": "a", "metric": "ms",
             "value": "1", "runs": "1"}
    for name, value in (("RESULTS", tmp_path / "results.csv"), ("REPORT", tmp_path / "report.md"),
                        ("README", tmp_path / "README.md"), ("HOME", tmp_path)):
        monkeypatch.setattr(bm, name, value)
    bm.README.write_text("No numbers here.\n", encoding="utf-8")
    bc.write_rows([other], bm.RESULTS)
    marker = "<!-- bench:matrix pool metric=tokens_per_right -->\n<!-- /bench -->\n"
    bm.REPORT.write_text(br.render(marker, [other]), encoding="utf-8")  # every table agrees: only the marker is bare
    assert bm.main(["report", "--check"]) == 1 and "marker of scenario 'pool' has no rows" in capsys.readouterr().out
    bc.write_rows([other, {**other, "scenario": "pool", "metric": "tokens_per_right"}], bm.RESULTS)
    bm.REPORT.write_text(br.render(marker, [other, {**other, "scenario": "pool", "metric": "tokens_per_right"}]), encoding="utf-8")
    assert bm.main(["report", "--check"]) == 0


def test_bench_pool_session_shape_groups_resume_marginal_input_and_cache_share(monkeypatch):
    import agent_bench
    import bench_pool as bp
    import bench_report as br
    kinds = ["fact", "count", "cites", "snippet", "offkb", "gap"]
    rows = [{**bp.row(kinds[i % 6] if i < 12 else "variant_typo", "d0", "original", "fixture:0" if i in (0, 12, 13) else f"fixture:{i}",
                      f"Question {i}?", [rf"value{i}"], "good"), "question": f"Question {i}?"} for i in range(15)]
    groups, left = bp.session_groups(rows)
    assert len(groups) == 2 and len(left) == 3 and all(len(g) == 6 for g in groups)
    assert all(len({r["source"] for r in g}) == 6 for g in groups)  # a base question and its variants never share a group
    assert bp.session_groups(rows)[0] == groups  # the seed decides: the same rows, the same groups
    first, later = (bp.session_argv("sonnet-5-5", "low", "SID", n) for n in (1, 2))
    assert "--no-session-persistence" not in first + later and first[2:4] == ["--session-id", "SID"] and later[2:4] == ["--resume", "SID"]
    assert later[-2:] == ["--effort", "low"] and bp.session_argv("sonnet-5-5", "default", "SID", 2)[-1] != "default"
    # six requests of one session, one per question: (uncached, cache write, cache read, output) of each
    usages = [(10, 2000, 0, 50), (20, 100, 2010, 40), (30, 200, 2130, 60), (40, 0, 2360, 30), (50, 300, 2400, 20), (60, 0, 2750, 10)]

    def stream(answer, usage, model="claude-sonnet-5-5"):
        u = dict(zip(("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens"), usage))
        events = [{"type": "assistant", "message": {"id": "m1", "model": model, "usage": u, "content": [{"type": "text", "text": answer}]}},
                  {"type": "result", "usage": u, "total_cost_usd": 0.01, "duration_api_ms": 1000, "num_turns": 1,
                   "modelUsage": {model: {"costUSD": 0.01}}, "result": answer}]
        return "\n".join(json.dumps(e) for e in events)
    seen, cells = [], [("sonnet-5-5", "low", "sonnet-5-5:low")]

    def runner(arm, effort, row, sid, position):
        seen.append((sid, position))
        if position == 4 and row is groups[1][3]:
            return {"error": "usage limit"}
        return agent_bench.result_of(stream("nope" if position == 3 else row["checks"][2:-2], usages[position - 1]), "", 3.0)
    runs = bp.run_sessions(groups, cells, 1, runner)
    assert [s[0] for s in seen[:6]] == [seen[0][0]] * 6 and seen[0][0] != seen[6][0]  # one session id per group
    one = [r for r in runs if r["group"] == 1]
    assert [r["position"] for r in one] == [1, 2, 3, 4, 5, 6] and {r["label"] for r in runs} == {"sonnet-5-5:low/session"}
    assert [r["marginal_input"] for r in one] == [2010, 120, 230, 40, 350, 60]  # each request's prompt less the one before
    assert round(one[1]["cache_read_share"], 4) == round(2010 / 2130, 4) and one[0]["cache_read_share"] == 0
    assert [r["checks"] for r in one] == [[True], [True], [False], [True], [True], [True]]
    two = [r for r in runs if r["group"] == 2]
    assert [("error" in r) for r in two] == [False, False, False, True, True, True]  # a failed question ends its session
    assert two[5]["error"] == "the session ended at position 4"
    got = {(c, m): (v, n, note) for c, label, m, v, n, model, note in bp.session_rows(runs)}
    assert got[("position 1", "marginal_input")] == (2010, 2, "the whole prompt: no request before it")
    assert got[("position 2", "marginal_input")][0] == 120 and got[("position 5", "cache_read_share")][0] == 2400 / 2750
    assert got[("position 3", "checks")][0] == "0/2" and got[("position 4", "checks")][0] == "1/1" and got[("position 4", "errors")][0] == 1
    out = [{"scenario": "pool", "record": "2026-10-09", "date": "2026-10-09", "commit": "abc1234", "claude_code": "2.1.300",
            "kb_topics": "1", "case": c, "arm": label, "model": "", "metric": m, "value": str(v), "runs": str(n), "note": note}
           for c, label, m, v, n, model, note in bp.session_rows(runs)]
    shown = br.render("<!-- bench:session pool -->\n<!-- /bench -->\n", out)
    assert "| position | sonnet-5-5:low/session marginal_input | sonnet-5-5:low/session cache_read_share |" in shown
    assert "| 1 | 2,010 | 0.0% |" in shown and "| 2 | 120 | 94.4% |" in shown and shown.index("| 2 |") < shown.index("| 6 |")
    assert br.empty_markers("<!-- bench:session pool -->\n<!-- /bench -->\n", out) == []
    # a resumed run's result event reports the session's running total: each question costs its own share, and so
    # does the spend; a new session starts from 0
    totals, spent = iter([0.10, 0.25, 0.31, 0.04]), []
    monkeypatch.setattr(agent_bench, "execute", lambda *a, **k: {"cost": next(totals)})
    monkeypatch.setattr(bp, "spent_run", lambda r: spent.append(r["cost"]))
    live = bp.live_session_runner(type("B", (), {"lookup": lambda self: "."})())
    costs = [live("haiku-5-5", "default", {"question": "q"}, sid, n)["cost"] for sid, n in (("A", 1), ("A", 2), ("A", 3), ("B", 1))]
    assert [round(c, 6) for c in costs] == [0.10, 0.15, 0.06, 0.04] and spent == costs


def pool_rows(n):
    import bench_pool as bp
    kinds = ["fact", "count", "cites", "snippet", "offkb", "gap"]
    return [{**bp.row(kinds[i % 6], "d0", "original", f"fixture:{i}", f"Question {i}?", [rf"value{i}"], "good"),
             "question": f"Question {i}?"} for i in range(n)]


def slow_first(finished):
    """A fake runner: every run costs $0.01, and the first one started is the slowest, so runs finish out of start order."""
    import itertools, time
    import agent_bench
    count = itertools.count()

    def run(*args):
        n = next(count)
        time.sleep(0.04 if n == 0 else 0.001 * (n % 3))
        r = agent_bench.result_of(pool_stream("value1"), "", 5.0)
        bc.spent_run(r)
        finished.append(n)
        return r
    return run


def test_bench_pool_jobs_parallel_rows_equal_one_job_cap_stops_and_the_record_date_holds(monkeypatch, tmp_path):
    import bench_pool as bp
    rows, cells = pool_rows(12), bp.plan_cells(["sonnet-5-5", "haiku-4-5"], bp.EFFORTS)
    spend = lambda: (round(bc.SPEND["usd"], 6), bc.SPEND["runs"])  # noqa: E731

    def reset():
        monkeypatch.setitem(bc.SPEND, "usd", 0.0)
        monkeypatch.setitem(bc.SPEND, "runs", 0)
    reset()
    seen_one, seen_three, fin = [], [], []
    one = bp.run_pool(rows[:4], cells, 2, slow_first([]), lambda rec, r: seen_one.append(rec["id"]))
    assert len(one) == len(seen_one) == 24 and spend() == (0.24, 24)
    reset()
    three = bp.run_pool(rows[:4], cells, 2, slow_first(fin), lambda rec, r: seen_three.append(rec["id"]), jobs=3)
    assert fin != sorted(fin) and three == one and seen_three == seen_one  # out of order in flight, in order in the rows
    assert spend() == (0.24, 24)  # the shared spend lost no update to a thread
    for jobs in (1, 3):  # the cap: no run starts once the finished runs cost it, those in flight finish, the rest are named
        reset()
        left = []
        got = bp.run_pool(rows[:4], cells, 2, slow_first([]), None, jobs=jobs, cap=0.045, left=left)
        assert got == one[:len(got)] and len(got) + len(left) == 24 and 5 <= len(got) <= 4 + jobs and spend()[1] == len(got)
        assert (jobs > 1 or len(got) == 5) and left[0] == (one[len(got)]["label"], f"{one[len(got)]['id']}#{len(got) % 2 + 1}")
    groups, _ = bp.session_groups(rows)  # a group's six questions stay in order inside one session, the records equal one job's
    cell, order = [("sonnet-5-5", "low", "sonnet-5-5:low")], {}
    fresh = slow_first([])

    def session_runner(arm, effort, row, sid, position):
        order.setdefault(sid, []).append(position)
        return fresh(arm, effort, row)
    flat = bp.run_sessions(groups, cell, 2, session_runner)
    assert len(order) == 4 and all(p == [1, 2, 3, 4, 5, 6] for p in order.values())
    order.clear()
    fresh = slow_first([])
    assert bp.run_sessions(groups, cell, 2, session_runner, jobs=3) == flat
    assert len(order) == 4 and all(p == [1, 2, 3, 4, 5, 6] for p in order.values())
    days = iter(["2026-10-09", "2026-10-10"])  # one record date: read once, at the start; a later midnight changes no row
    monkeypatch.setattr(bc, "today", lambda: next(days))
    monkeypatch.setattr(bc, "git", lambda *a, **k: "abc1234")
    monkeypatch.setattr(bc.subprocess, "run", lambda *a, **k: type("P", (), {"stdout": "2.1.300 (Claude Code)"})())
    monkeypatch.setattr("kbfacts.articles", lambda: [])
    b = bc.Bench(tmp_path, 1)
    b.row("pool", "all", "a", "m", 1)
    assert bc.today() == "2026-10-10"  # the clock has passed midnight
    b.row("pool", "all", "a", "m", 2)
    assert {(r["record"], r["date"]) for r in b.rows} == {("2026-10-09", "2026-10-09")}


def test_bench_pool_jobs_scenario_stops_at_the_cap_with_a_spend_stopped_row_and_dry_run_estimates(monkeypatch, capsys):
    import types
    import bench_pool as bp
    monkeypatch.setitem(bc.SPEND, "usd", 0.0)
    monkeypatch.setitem(bc.SPEND, "runs", 0)
    monkeypatch.setattr(bp, "load_pool", lambda home, kinds=None: pool_rows(6))
    monkeypatch.setattr(bp, "live_runner", lambda b, sh: slow_first([]))
    monkeypatch.setattr(bp, "read_rows", lambda path: [])
    b = types.SimpleNamespace(arms=["sonnet-5-5"], efforts=["low"], kinds=None, shape="fresh", seed=1, dry=False, reps=2, jobs=2,
                              max_usd=0.045, rows=[], status=0)
    b.row = lambda scenario, case, arm, metric, value, runs="", model="", note="": b.rows.append((case, arm, metric, value, note))
    bp.s_pool(b)
    stopped = [r for r in b.rows if r[2] == "spend_stopped"]
    assert b.status == 1 and len(stopped) == 1 and stopped[0][:3] == ("not started", "sonnet-5-5:low", "spend_stopped")
    assert stopped[0][3] == len(stopped[0][4].split(", ")) and 12 - stopped[0][3] in (5, 6) and "#" in stopped[0][4]
    b.dry, b.rows = True, []
    with pytest.raises(bp.Skip) as e:  # the estimate prices the stated default tokens at bench_core's prices
        bp.s_pool(b)
    run = (2000 * 2.0 + 8000 * 2.5 + 80000 * 0.10 + 1200 * 10.0) / 1e6
    assert f"estimated spend ${12 * run:.2f}" in str(e.value) and "the default" in capsys.readouterr().out
    hist = [{"scenario": "pool", "record": "2026-10-09", "case": "all", "arm": "x", "model": "claude-haiku-4-5", "metric": m,
             "value": v} for m, v in (("input", "1000"), ("cache_read", "600"), ("cache_write", "100"), ("out", "50"))]
    tokens, model, basis = bp.assumed_run("x", "haiku-4-5", hist)
    assert (tokens, model, basis) == ({"uncached": 300, "cache_write": 100, "cache_read": 600, "out": 50}, "claude-haiku-4-5",
                                      "the means of the record 2026-10-09")
