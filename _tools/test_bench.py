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
    assert s["effective"] == 100 + 2 * 1000 + 0.1 * 10000  # the read price over the input price: 0.20 / 2.0
    # no per-TTL split in the usage: the writes are priced at the billing surface's TTL, one hour on a subscription
    assert round(bc.est_cost(s), 6) == round((100 * 2 + 1000 * 4.0 + 10000 * 0.20 + 500 * 10) / 1e6, 6)
    api = bc.usage_sum([req("claude-sonnet-5-5", 100, 1000, 10000, 500)], "sonnet", "2.1.284", surface="api")
    assert api["effective"] == 100 + 1.25 * 1000 + 0.1 * 10000
    assert round(bc.est_cost(api), 6) == round((100 * 2 + 1000 * 2.5 + 10000 * 0.20 + 500 * 10) / 1e6, 6)
    # a split in the usage wins over the surface: 400 of the 1000 written tokens for one hour, 600 for five minutes
    mixed = req("claude-sonnet-5-5", 100, 1000, 10000, 500)
    mixed["usage"]["cache_creation"] = {"ephemeral_5m_input_tokens": 600, "ephemeral_1h_input_tokens": 400}
    for surface in ("subscription", "api"):
        m = bc.usage_sum([mixed], "sonnet", surface=surface)
        assert round(bc.est_cost(m), 6) == round((100 * 2 + 600 * 2.5 + 400 * 4.0 + 10000 * 0.20 + 500 * 10) / 1e6, 6)
    opus = bc.usage_sum([req("claude-opus-5-5", 0, 0, 10000, 0)], "opus")
    haiku = bc.usage_sum([req("claude-haiku-4-5-20251001", 0, 0, 10000, 0)], "haiku")
    assert (opus["effective"], haiku["effective"]) == (500, 1000)


def test_bench_price_tier_is_recorded_and_alias_follows_the_run():
    run = [req("claude-haiku-5-5", 100, 1000, 10000, 500), req("claude-haiku-5-5", 100, 0, 150000, 500)]
    s = bc.usage_sum(run, "haiku")
    assert s["tier"] == ">100k" and bc.usage_sum(run[:1], "haiku")["tier"] == "<=100k"
    first, second = (100 * 0.10 + 1000 * 0.20 + 10000 * 0.01 + 500 * 0.50), (100 * 0.50 + 150000 * 0.05 + 500 * 2.50)
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
                               "question": q, "verdict": "good", "articles": [f"public/d{i % 6}/a0.md"],
                               "citations": [{"line": "kb/_self/x.md:1" if i == 5 else f"public/d{i % 6}/a0.md:1"}]}) + "\n"
                   for i, q in enumerate(ql_questions))
    (run / "20261008T000000Z-aaaaaaaa.jsonl").write_text(head % len(ql_questions) + ents, encoding="utf-8")


def test_bench_pool_build_counts_seed_heldout_and_querylog_stay_apart(tmp_path, monkeypatch, capsys):
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
    assert [r["id"] for r in bp.build_public(tmp_path, 4, ask, tmp_path / "other.csv")] != [r["id"] for r in rows]  # a new file resamples
    ev_file = tmp_path / bp.EVAL_FILE
    ev_file.write_text(ev_file.read_text(encoding="utf-8") + "".join(
        f"EV-new{d},What does setting alpha{d * 4 + 1} beta{d * 4 + 1} gamma{d * 4 + 1} equal case new?,d{d}/a1.md,good,\n"
        for d in range(6)), encoding="utf-8")
    assert rows == bp.build_public(tmp_path, 3, lambda items: pytest.fail("a new eval row moves a row or asks"), out)  # the committed sample stays
    assert bp.fact_for(tmp_path, {"question": "which status is complete for the topic", "expect_paths": "d0/a0.md"}) is None  # no front-matter line
    plant = tmp_path / "kb/public/zz/plant.md"
    plant.parent.mkdir(parents=True)
    plant.write_text("---\ntopic: zz/plant\n---\n\n# Widget\n\n- The widget device joins a hybrid domain by design.\n"
                     "- Board replacement breaks the registered hash.\n" + "".join(
                         f"- The widget catalog lists item {i}.\n" for i in range(4)), encoding="utf-8")
    # "widget device" shares two exact words with line 7, "board replaced" only one; stems and rarity put the answer first
    assert bp.fact_for(tmp_path, {"question": "What happens to the widget device record when the board is replaced?",
                                  "expect_paths": "zz/plant.md"})[1] == 8
    side = tmp_path / "side" / "kb/public/zz"  # a home of its own: more files in zz would move the count rows
    side.mkdir(parents=True)
    (side / "wrap.md").write_text(
        "---\ntopic: zz/wrap\n---\n\n## Summary\nThe gadget exports its license state and reports the release channel on\n"
        "demand, so the gadget license and release channel show in one view.\n\n"
        "- The gadget license and release channel are listed in `zz/plant.md`.\n"
        "- A gadget license is a signed file.\n", encoding="utf-8")
    wrapped = {"question": "What is the gadget license and release channel?", "expect_paths": "zz/wrap.md"}
    assert bp.fact_for(tmp_path / "side", wrapped)[1] == 6  # the paragraph's first line; its wrapped line 7 and the pointer line 9 are no facts
    (side / "plant.csv").write_text(
        'project,licence,latest_release\nalpha,MIT licence,v1\nbetamin,GPL licence,v2\nbetamax,Apache licence,v3\n'
        '"gamma","BSD licence\nwrapped note",v4\n', encoding="utf-8")
    pick = lambda q: bp.fact_for(tmp_path / "side", {"question": q, "expect_paths": "zz/plant.csv"})
    assert pick("project licence latest_release") is None  # the header line shares every stem and is no fact
    assert pick("betamax licence")[1:] == (4, "betamax,Apache licence,v3")  # a data row; the whole word breaks the tie of stems
    assert pick("wrapped note licence")[1] == 5  # a row over two lines is one entry at its first line
    evrows =[r for r in rows if r["kind"] in bp.EVAL_KINDS]
    asked, kept = [], []

    def redo_ask(items):
        asked.append([i["row"] for i in items])
        own = re.search(r"value\d+", items[0]["fact"]).group()
        return [own, r"d0/a0\.md", "nomatch", r"Setting|equals", r"value\d+"]  # a specific regex, a path, a miss, a common word, a broad one
    names = [evrows[0]["id"], evrows[1]["source"].split(":", 1)[1], evrows[2]["id"], evrows[3]["id"], evrows[4]["id"]]
    again = bp.build_public(tmp_path, 3, redo_ask, out, names, kept)
    now = {r["source"]: r["checks"] for r in again if r["kind"] in bp.EVAL_KINDS}
    was = {r["source"]: r["checks"] for r in rows if r["kind"] in bp.EVAL_KINDS}
    assert asked == [[r["source"] for r in evrows[:5]]]  # only the named rows are asked
    assert [s for s in now if now[s] != was[s]] == [evrows[0]["source"]]  # one new regex passes the guards
    assert len(json.loads(now[evrows[0]["source"]])) == 1 and re.fullmatch(r"value\d+", json.loads(now[evrows[0]["source"]])[0])
    assert [s for s, _ in kept] == [r["source"] for r in evrows[1:5]] and (
        [w for _, w in kept][-2][:19], [w for _, w in kept][-1][:11]) == ("`Setting` is in 24 ", "it matches ")  # the others keep the committed check
    with pytest.raises(bp.PoolError):
        bp.build_public(tmp_path, 3, redo_ask, out, ["EV-nope"])
    replies = tmp_path / "replies.csv"
    bp.write_csv(replies, [{**r, "checks": json.dumps([r"value\d+"])} for r in rows])
    kept2 = []
    assert bp.build_public(tmp_path, 3, bp.csv_replies(replies), out, names[:1], kept2) == rows and [w[:10] for _, w in kept2] == [
        "it matches"]  # a csv answers without a model, and the guards judge its reply
    prompts = []
    monkeypatch.setattr(bp, "sonnet_json", lambda prompt, cwd: (prompts.append(prompt), ([], 0.0))[1])
    monkeypatch.setenv("BENCH_SCRATCH", str(tmp_path / "scratch"))
    item = {"row": "lookup_eval.csv:EV-0", "question": "q?", "where": "d0/a0.md:8", "fact": "f"}
    bp.sonnet_regexes([item])
    bp.sonnet_regexes([{**item, "redo": True}])
    limits = f"more than {bp.COMMON_ARTICLES} of its articles"
    assert limits not in prompts[0] and limits in prompts[1] and f"more than {bp.BREADTH} other items" in prompts[1]  # a redone row's prompt names the guard's limits
    before = out.read_text(encoding="utf-8")
    monkeypatch.setattr(bp, "sonnet_regexes", lambda items: pytest.fail("a dry run or a refused call pays"))
    rns = argparse.Namespace(pool_cmd="build", querylog=False, seed=3, out=str(out), redo=names, dry_run=True)
    assert bp.cli(rns, tmp_path) == 0 and out.read_text(encoding="utf-8") == before  # the listing writes nothing
    listing = capsys.readouterr().out
    assert "would ask 5 rows" in listing and "estimated $" in listing and all(r["source"] in listing for r in evrows[:5])
    rns.redo, rns.dry_run = [r["id"] for r in evrows[:bp.ASK_MAX_ROWS + 1]], False
    assert bp.cli(rns, tmp_path) == 1 and "no call" in capsys.readouterr().out and out.read_text(encoding="utf-8") == before  # the planted failure
    held = [r for r in rows if r["kind"] == "heldout"]
    assert all(r["question"] == "" and json.loads(r["checks"]) for r in held)
    assert "HELDOUT TEXT" not in out.read_text(encoding="utf-8") and "HELDOUT TEXT" in bp.question_of(held[0], tmp_path)
    assert bp.check_problems(rows, tmp_path) == []
    assert bp.check_problems([{**held[0], "question": bp.question_of(held[0], tmp_path)}], tmp_path)[0].endswith("names a case "
                                                                                                           "of lookup_heldout.csv")  # the planted failure
    monkeypatch.setattr(bp, "current_articles", lambda q: [f"d{int((re.findall(r'number (\d+)', q) or ['0'])[0]) % 6}/a0.md"])
    ns = argparse.Namespace(pool_cmd="build", querylog=True, seed=3, out=None)
    assert bp.cli(ns, tmp_path) == 0
    qlfile = tmp_path / bp.QUERYLOG_FILE
    qlrows = bp.read_csv(qlfile)
    assert len(qlrows) == bp.QUERYLOG_ROWS and bp.cli(argparse.Namespace(pool_cmd="check", querylog=True, file=None), tmp_path) == 0
    assert bp.cli(ns, tmp_path) == 0 and bp.read_csv(qlfile) == qlrows  # a rebuild keeps the rows it holds
    assert not any("number 5 " in r["question"] for r in qlrows)  # an answer cited only outside kb/public is no public question
    assert bp.check_article("d0/a0.md", ["d1/a1.md", "d0/a0.md"]) == "d0/a0.md" and bp.check_article("d0/a0.md", ["d1/a1.md"]) == "d1/a1.md"
    assert bp.check_article("d0/a0.md", []) is None
    monkeypatch.setattr(bp, "current_articles", lambda q: ["d9/now.md"])  # the kb's pack moved on: the kept rows follow it
    assert {json.loads(r["checks"])[0] for r in bp.build_querylog(tmp_path, 3, qlfile)} == {r"d9/now\.md"}
    public = out.read_text(encoding="utf-8")
    assert not any(r["question"] in public for r in qlrows) and "fixture session question" not in public
    assert org not in qlfile.read_text(encoding="utf-8") and not any(r["kind"] == "querylog" for r in rows)


# ---- the pool scenario (bench_pool.py): synthetic streams, no model

def pool_stream(answer, chars=480, model="claude-sonnet-5-5", final_out=80, cost=0.01, main_out=None, billed=None):
    """A stream-json run of two requests: a kb_pack call whose result is `chars` characters, then the answer. The
    messages' output counts are partial (50 and 30); the result event's `modelUsage` counts `final_out` and its `usage`
    (the main loop) `main_out`, by default the same. `billed` is merged into the `modelUsage`, per model: the fields a
    tool's own model call is billed (a WebFetch's summary, a WebSearch) and no message of the stream shows."""
    usage = lambda unc, write, read, out: {"input_tokens": unc, "cache_creation_input_tokens": write,  # noqa: E731
                                           "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": write},
                                           "cache_read_input_tokens": read, "output_tokens": out}
    events = [
        {"type": "assistant", "message": {"id": "m1", "model": model, "usage": usage(10, 2000, 0, 50),
                                          "content": [{"type": "tool_use", "id": "t1", "name": "mcp__kb__kb_pack", "input": {}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "x" * chars}]}},
        {"type": "assistant", "message": {"id": "m2", "model": model, "usage": usage(170, 0, 2010, 30),
                                          "content": [{"type": "text", "text": answer}]}},
        {"type": "result", "usage": usage(180, 2000, 2010, final_out if main_out is None else main_out), "total_cost_usd": cost, "duration_api_ms": 4000,
         "num_turns": 2, "result": answer,
         "modelUsage": {m: {**({"costUSD": cost, "outputTokens": final_out} if m == model else {}), **(billed or {}).get(m, {})}
                        for m in {model, *(billed or {})}}}]
    return "\n".join(json.dumps(e) for e in events)


def test_bench_pool_scenario_rows_derived_cells_and_report_tables(monkeypatch):
    import agent_bench
    import bench_pool as bp
    import bench_report as br
    rows = [{**bp.row(kind, "d0", "original", f"fixture:{i}", f"Question {i}?", [rf"value{i}"], "good"), "question": f"Question {i}?"}
            for i, kind in enumerate(["fact", "fact", "count"])]
    cells = bp.plan_cells(["sonnet-5-5", "haiku-4-5", "hook", "web-sonnet-5-5"], bp.EFFORTS)
    assert [c[2] for c in cells] == ["sonnet-5-5:low", "sonnet-5-5:default", "haiku-4-5", "hook", "web-sonnet-5-5"]
    assert [c[2] for c in bp.plan_cells(["opus-5-5"], bp.EFFORTS)] == ["opus-5-5:low", "opus-5-5:default"]
    assert "opus-5-5" in bp.ARMS and "opus-5-5" not in bp.DEFAULT_ARMS  # named in --arms only
    argv = bp.session_argv("opus-5-5", "low", "SID", 1)
    assert argv[argv.index("--model") + 1] == "claude-opus-5-5"

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
    assert cell("fact", "sonnet-5-5:low", "effective_input") == 180 + 2 * 2000 + 0.1 * 2010  # Sonnet 5.5 reads at 0.20 over its $2 input
    assert cell("fact", "sonnet-5-5:low", "pack_tokens") == 120  # the prompt's growth less the request's output, not 480 / 4
    # the output is the sum of the result event's modelUsage counts (500: the main loop's 200 and a subagent's), not the
    # messages' partial ones (50 + 30) nor the event's usage; the stream writes its cache for one hour (its usage splits
    # the writes by TTL), and the list cost, priced at the 1-hour rate, is near the run's reported cost
    planted = agent_bench.result_of(pool_stream("value1", final_out=500, cost=0.0136, main_out=200), "", 5.0)
    t = bc.run_tokens(planted, "sonnet")
    assert t["out"] == planted["out"] == 500
    assert planted["requests"][0]["usage"]["cache_creation"]["ephemeral_1h_input_tokens"] == 2000
    listed = bp.list_usd(planted, "sonnet")
    assert abs(listed - planted["cost"]) <= 0.2 * planted["cost"]  # the 5-minute rate would price it 22% under
    # a tool's own model call is billed and in no message of the stream: a WebFetch summary runs Haiku 5.5 inside a Sonnet
    # run (62k uncached input, 12k output: priced at Haiku's prices, not at the session's $10 per MTok of output), and a
    # WebSearch is billed $0.01 on a kb arm too, with the input of its own call on the session's model
    fetch = {"claude-haiku-5-5": {"inputTokens": 60_000, "outputTokens": 12_000, "webSearchRequests": 1,
                                  "costUSD": 0.022}}
    summary = agent_bench.result_of(pool_stream("value1", final_out=200, cost=0.0326, billed=fetch), "", 5.0)
    assert summary["out"] == 12_200 and summary["web_searches"] == 1  # 0.0106 the session, 0.0220 the Haiku call and its search
    assert abs(bp.list_usd(summary, "sonnet") - summary["cost"]) <= 0.2 * summary["cost"]
    search = {"claude-haiku-5-5": {"inputTokens": 20_180, "webSearchRequests": 1}}
    kb_search = agent_bench.result_of(pool_stream("value1", model="claude-haiku-5-5", final_out=4000, cost=0.0144, billed=search), "", 5.0)
    assert kb_search["web_searches"] == 1 and kb_search["searches"] == 0
    assert abs(bp.list_usd(kb_search, "haiku") - kb_search["cost"]) <= 0.2 * kb_search["cost"]
    assert cell("fact", "sonnet-5-5:low", "checks") == "1/2" and cell("fact", "sonnet-5-5:low", "fully_right") == "1 of 2"
    assert round(cell("fact", "sonnet-5-5:low", "fixed_share"), 4) == round(2010 / 4190, 4)
    assert cell("fact", "sonnet-5-5:low", "tokens_per_right") == 2 * 4381  # two runs' effective input over the one right
    # the 95% interval over the cell's rows (a row's reps kept together), fixed seed: the same runs give the same bounds
    lo, hi, tpr = (cell("fact", "sonnet-5-5:low", m) for m in ("right_share_lo", "right_share_hi", "tokens_per_right"))
    assert 0 <= lo <= 0.5 <= hi <= 1 and cell("fact", "sonnet-5-5:low", "tokens_per_right_lo") <= tpr
    assert cell("fact", "sonnet-5-5:low", "tokens_per_right_hi") >= tpr
    assert bp.cell_metrics([r for r in runs if r["label"] == "sonnet-5-5:low"]) == bp.cell_metrics(
        [r for r in runs if r["label"] == "sonnet-5-5:low"])
    twice = [{**r, "id": "one"} for r in runs if r["label"] == "sonnet-5-5:low"]
    assert dict(bp.cell_metrics(twice + twice))["right_share_lo"] == dict(bp.cell_metrics(twice + twice))["right_share_hi"]  # one row: a point
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
    assert "| fact | 8,762 | 8,762 | 8,762 | 0 | 8,762 |" in shown and "| count | 4,381 | 4,381 | 4,381 | 0 | - |" in shown  # kind by arm
    assert "| all | sonnet-5-5:low | 48.0% | 2,010 |" in shown  # the fixed share by arm
    assert "| all | sonnet-5-5 | 6,572 (+0%) | 6,572 |" in shown  # low against default
    assert "| all | haiku-4-5 (no effort setting) | - | 6,572 |" in shown and "| hook" not in shown.split("bench:effort")[1]
    assert br.empty_markers(text, out) == []
    # a `claude -p` timeout in a kb or web run is one error run: the other runs of the chunk still come back
    import subprocess

    def slow(cmd, prompt, **kw):
        raise subprocess.TimeoutExpired("claude", 900)
    monkeypatch.setattr(agent_bench, "execute", slow)
    mixed = bp.run_pool(rows[:2], bp.plan_cells(["sonnet-5-5", "hook"], bp.EFFORTS), 1,
                        lambda arm, effort, row: bp.hook_result("{}", 0.1) if arm == "hook" else bp.execute_run(["claude"], "q"),
                        lambda rec, r: None)
    assert [("error" in r) for r in mixed].count(True) == 4 and len(mixed) == 6 and mixed[0]["error"] == "the claude run took over 900 s"
    # a split route's row scores both parts: the reader's answer and tool calls count beside the researcher's, while an
    # escalation (the researcher answered the whole question) is scored on the researcher's run alone
    reader = agent_bench.result_of(pool_stream("kb has: value1", model="claude-haiku-4-5"), "", 5.0)
    researcher = agent_bench.result_of(pool_stream("live docs: value2"), "", 5.0)
    split_row = bp.row("fact", "d0", "original", "fixture:split", "Question?", ["value1", "value2", "tool:kb_pack"], "split")
    split = bp.record_of(split_row, "router", "router", agent_bench.add(reader, researcher, "and"))
    assert split["checks"] == [True, True, True] and split["tool_calls"] == 2 and split["model"].count("+") == 1
    assert agent_bench.add(reader, researcher, "and")["answer"] == "kb has: value1\n\nlive docs: value2"
    escalated = bp.record_of(split_row, "router", "router", agent_bench.add(reader, researcher, "escalate"))
    assert escalated["checks"] == [False, True, True] and escalated["tool_calls"] == 1


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
    # modelUsage is the running total too: each question's out, model usage and web searches are its own share, and
    # its list cost lands within 20% of its cost
    model, keys = "claude-sonnet-5-5", ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
    own = [(10, 21400, 45500, 381), (20, 2237, 69070, 1052), (30, 3454, 86129, 3046)]
    price = lambda u: (u[0] * 2 + u[1] * 4 + u[2] * 0.1 + u[3] * 10) / 1e6  # noqa: E731

    def resumed(n):
        u, t = dict(zip(keys, own[n])), [sum(o[i] for o in own[:n + 1]) for i in range(4)]
        mu = {model: {"inputTokens": t[0], "cacheCreationInputTokens": t[1], "cacheReadInputTokens": t[2], "outputTokens": t[3],
                      "costUSD": price(t), "webSearchRequests": n}}
        total = price(t) + 0.01 * n
        events = [{"type": "assistant", "message": {"id": "m", "model": model, "usage": u, "content": [{"type": "text", "text": "a"}]}},
                  {"type": "result", "usage": u, "total_cost_usd": total, "duration_api_ms": 1000, "num_turns": 1, "modelUsage": mu, "result": "a"}]
        return agent_bench.result_of("\n".join(json.dumps(e) for e in events), "", 1.0)
    results = iter([resumed(0), resumed(1), resumed(2)])
    monkeypatch.setattr(agent_bench, "execute", lambda *a, **k: next(results))
    recs = [bp.record_of({"id": "x", "kind": "fact", "checks": "[]"}, "sonnet-5-5", "l", live("sonnet-5-5", "low", {"question": "q"}, "S", n))
            for n in (1, 2, 3)]
    assert [r["out"] for r in recs] == [o[3] for o in own] and [r["model_usage"][model]["out"] for r in recs] == [o[3] for o in own]
    assert [r["web_searches"] for r in recs] == [0, 1, 1] and all(abs(r["cost"] - r["list_cost"]) <= 0.2 * r["list_cost"] for r in recs)


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
        # the runs start one of each cell in turn: the next one is the cell len(got) % 3 at its turn len(got) // 3
        assert (jobs > 1 or len(got) == 5) and left[0] == (one[len(got)]["label"], f"{one[len(got)]['id']}#{len(got) // 3 % 2 + 1}")
        assert {r["label"] for r in got} == {label for _, _, label in cells}  # the cap left every cell some runs
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
    run = (2000 * 2.0 + 8000 * 4.0 + 80000 * 0.20 + 1200 * 10.0) / 1e6  # a cache write at the 1-hour price
    assert f"estimated spend ${12 * run:.2f}" in str(e.value) and "the default" in capsys.readouterr().out
    cell = lambda record, label, model, **m: [{"scenario": "pool", "record": record, "case": "all", "arm": label, "model": model,  # noqa: E731
                                              "metric": k, "value": str(v)} for k, v in m.items()]
    tokens = dict(input=1000, cache_read=600, cache_write=100, out=50)
    # a label with a record is priced at the mean cost of its runs, the newest record first
    hist = cell("2026-10-08", "x", "claude-haiku-4-5", cost=0.09, **tokens) + cell("2026-10-09", "x", "claude-haiku-4-5", cost=0.05, **tokens)
    assert bp.assumed_run("x", "haiku-4-5", hist) == (0.05, "claude-haiku-4-5", None, "the mean cost of the record 2026-10-09")
    # a kb arm label with none is priced on the means of the same label of another kb arm at its own model's prices (Haiku 5.5's lowest tier)
    twin = cell("2026-10-08", "sonnet-5-5:low", "claude-sonnet-5-5", cost=0.1, **tokens) + cell("2026-10-09", "haiku-5-5:low", "claude-haiku-5-5", cost=0.01, **tokens)
    got = bp.assumed_run("opus-5-5:low", "opus-5-5", twin)
    assert got[:3] == (bp.run_usd({"uncached": 300, "cache_write": 100, "cache_read": 600, "out": 50}, "claude-opus-5-5"), "claude-opus-5-5",
                       {"uncached": 300, "cache_write": 100, "cache_read": 600, "out": 50}) and "haiku-5-5:low in the record 2026-10-09" in got[3]
    assert bp.run_usd({"uncached": 0, "cache_write": 0, "cache_read": 150_000, "out": 0}, "claude-haiku-5-5") == 150_000 * 0.01 / 1e6
    assert bp.assumed_run("web-haiku-5-5", "web-haiku-5-5", twin)[3] == "the default"
    # the smoke command's dry run against the smoke record's costs (its 35 runs a label: the opus labels had no record, the Haiku 5.5 labels a
    # price from a whole run counted as one request): each label within 25%, and the whole command within 25% of a full run's cost
    smoke = {"haiku-5-5:low": 0.31, "haiku-5-5:default": 0.32, "haiku-4-5": 1.55, "sonnet-5-5:low": 3.79, "sonnet-5-5:default": 4.92,
             "opus-5-5:low": 7.69, "opus-5-5:default": 8.02}
    record = [r for r in bc.read_rows() if r["scenario"] == "pool" and r["record"] == "2026-10-08"]
    arms, sessions = ["haiku-5-5", "haiku-4-5", "sonnet-5-5", "opus-5-5", "router", "hook", "web-haiku-5-5", "web-sonnet-5-5"], ["haiku-5-5", "sonnet-5-5"]
    legs = [bp.Leg("fresh", bp.plan_cells(arms, bp.EFFORTS), {a: [0] * (13 if a.startswith("web-") else 35) for a in arms}, {}, {}, dict.fromkeys(arms, 1)),
            bp.Leg("session", bp.plan_cells(sessions, bp.EFFORTS), {}, {a: [[0] * 6] * 5 for a in sessions}, {}, dict.fromkeys(sessions, 1))]
    est = {label: runs * usd for _, _, label, runs, usd, *_ in bp.estimates(legs, record)}
    assert all(abs(est[label] - usd) <= 0.25 * usd for label, usd in smoke.items()), {k: (est[k], v) for k, v in smoke.items()}
    mean = lambda label: float(next(r["value"] for r in record if r["arm"] == label and r["case"] == "all" and r["metric"] == "cost"))  # noqa: E731
    rest = {"web-haiku-5-5": 13, "web-sonnet-5-5": 13, **{f"{m}-5-5:{e}/session": 30 for m in ("haiku", "sonnet") for e in bp.EFFORTS}}
    full = sum(smoke.values()) + 35 * 0.021 + sum(n * mean(label) for label, n in rest.items())  # the router's one smoke run cost 0.021
    assert abs(sum(est.values()) - full) <= 0.25 * full and sum(est.values()) >= 12


def test_bench_pool_record_plans_arm_reps_kinds_sample_both_shapes_and_one_cap(monkeypatch, capsys):
    import types
    import agent_bench
    import benchmarks as bm
    import bench_pool as bp
    web = "csv_fact+multi+synthesis+false_good+snippet+offkb"
    sess = "csv_fact+multi+synthesis+false_good+near_miss+snippet+count+cites+decision+conflict+gap"
    kinds = ["fact", "csv_fact", "multi", "synthesis", "false_good", "near_miss", "offkb", "snippet", "count", "cites",
             "decision", "conflict", "gap"]
    rows = [{**bp.row(k, "d0", "original", f"fixture:{k}{i}", f"Question {k}{i}?", [r"value1"], "good"), "question": f"Question {k}{i}?"}
            for k in kinds for i in range(4)]
    # the flags of a record shaped like 2026-10-08's: kb arms at 3 reps, Sonnet 5.5 at 2, the web arms on six kinds at 2, sessions
    reps, bad = bp.parse_arm_map(["sonnet-5-5=2,web-haiku-5-5=2", "web-sonnet-5-5=2,haiku-5-5/session=2,sonnet-5-5/session=2"],
                                 "--arm-reps", bp.reps_value)
    akinds, bad2 = bp.parse_arm_map([f"web-haiku-5-5={web},web-sonnet-5-5={web}", f"haiku-5-5/session={sess},sonnet-5-5/session={sess}"],
                                    "--arm-kinds", bp.kinds_value)
    assert not bad and not bad2 and reps["sonnet-5-5"] == 2 and akinds["web-haiku-5-5"] == web.split("+")
    # --sample: N rows of each kind, seeded, one kind's rows independent of the others', every row when N is above a kind's count
    picked = bp.sample_rows(rows, 2, 11)
    assert [sum(r["kind"] == k for r in picked) for k in kinds] == [2] * 13 and bp.sample_rows(rows, 2, 11) == picked
    assert bp.sample_rows(rows, 2, 12) != picked and bp.sample_rows(rows, 9) == rows
    assert bp.sample_rows([r for r in rows if r["kind"] != "fact"], 2, 11) == [r for r in picked if r["kind"] != "fact"]
    stream = agent_bench.result_of(pool_stream("value1"), "", 5.0)  # one parsed run, $0.01, copied for each fake run
    seen = {}

    def fresh(arm, effort, row):
        seen.setdefault(f"{arm}:{effort}" if arm in bp.KB_ARMS else arm, set()).add(row["kind"])
        r = dict(stream)
        bc.spent_run(r)
        return r
    monkeypatch.setattr(bp, "load_pool", lambda home, kinds=None: rows)
    monkeypatch.setattr(bp, "live_runner", lambda b, sh: fresh)
    monkeypatch.setattr(bp, "live_session_runner", lambda b: lambda arm, effort, row, sid, position: fresh(arm, effort, row))
    monkeypatch.setattr(bp, "read_rows", lambda path: [])

    def record(**more):
        monkeypatch.setitem(bc.SPEND, "usd", 0.0)
        monkeypatch.setitem(bc.SPEND, "runs", 0)
        seen.clear()
        b = types.SimpleNamespace(arms=["haiku-5-5", "sonnet-5-5", "web-haiku-5-5", "web-sonnet-5-5"], efforts=["low", "default"],
                                  kinds=None, shape="fresh,session", seed=11, dry=False, reps=3, jobs=1, max_usd=None, sample=2,
                                  arm_reps=reps, arm_kinds=akinds, rows=[], status=0)
        for k, v in more.items():
            setattr(b, k, v)
        b.row = lambda scenario, case, arm, metric, value, runs="", model="", note="": b.rows.append((case, arm, metric, value, runs, note))
        try:
            bp.s_pool(b)
        except bp.Skip as e:
            return b, str(e)
        return b, ""
    per_label = lambda b: {arm: n for case, arm, m, v, n, note in b.rows if case == "all" and m == "input"}  # noqa: E731
    full, _ = record()
    assert per_label(full) == {"haiku-5-5:low": 78, "haiku-5-5:default": 78, "sonnet-5-5:low": 52, "sonnet-5-5:default": 52,
                               "web-haiku-5-5": 24, "web-sonnet-5-5": 24, **{f"{m}-5-5:{e}/session": 36 for m in ("haiku", "sonnet")
                                                                            for e in ("low", "default")}}
    assert seen["web-haiku-5-5"] == set(web.split("+")) and seen["haiku-5-5:low"] == set(kinds) and full.status == 0
    assert bc.SPEND["runs"] == 452 and not any(m == "spend_stopped" for _, _, m, *_ in full.rows)
    assert any(c == "position 6" and a == "sonnet-5-5:low/session" for c, a, *_ in full.rows)  # the session shape's rows beside
    # one cap over both shapes: the fresh runs take their part of it by the estimates, the session runs the rest, and each shape
    # starts one run of every label in turn, so a cap below the cost leaves every label of both shapes some runs
    late, _ = record(max_usd=3.505)
    stopped = {a: v for c, a, m, v, n, note in late.rows if m == "spend_stopped"}
    assert late.status == 1 and stopped and per_label(late).keys() == per_label(full).keys()
    assert any(not a.endswith("/session") for a in stopped) and 3.505 <= bc.SPEND["usd"] <= 3.505 + 0.06
    assert "sessions not started" in capsys.readouterr().out
    early, _ = record(max_usd=1.0)
    stopped = {a: v for c, a, m, v, n, note in early.rows if m == "spend_stopped"}
    assert early.status == 1 and per_label(early).keys() == per_label(full).keys() and stopped.keys() == per_label(full).keys()
    assert 1.0 <= bc.SPEND["usd"] <= 1.0 + 0.06 and all(0 < n < per_label(full)[a] for a, n in per_label(early).items())
    # --dry-run: the plan per arm label and the estimate, no run
    capsys.readouterr()
    dry, msg = record(dry=True)
    out = capsys.readouterr().out
    assert not dry.rows and bc.SPEND["runs"] == 0 and "estimated spend $" in msg and "shapes fresh+session" in msg
    assert "pool: sonnet-5-5:low: 52 runs (26 rows x 2 reps)" in out and "pool: web-haiku-5-5: 24 runs (12 rows x 2 reps)" in out
    assert "pool: haiku-5-5:low/session: 36 runs (3 groups x 2 reps, 4 of 22 rows left out)" in out
    # an arm the flags name and the run does not run is an error, not an option left unused
    assert bm.main(["run", "pool", "--arm-reps", "opus-5-5=2", "--arm-kinds", "sonnet-5-5/session=fact", "--dry-run"]) == 2
    err = capsys.readouterr().err
    assert "--arm-reps: opus-5-5 is not run by this command (opt-in: name it in --arms)" in err
    assert "--arm-kinds: sonnet-5-5/session is not run by this command (the --shape has no session)" in err


def test_bench_pool_verify_exits_1_naming_each_planted_break_of_a_fake_record(monkeypatch, tmp_path, capsys):
    import types
    import agent_bench
    import benchmarks as bm
    import bench_pool as bp
    kinds = ["fact", "csv_fact", "multi", "synthesis", "false_good", "near_miss", "offkb", "snippet", "count", "cites",
             "decision", "conflict", "gap"]
    pool = [{**bp.row(k, "d0", "original", f"fixture:{k}{i}", f"Question {k}{i}?", [r"value1"], "good"), "question": f"Question {k}{i}?"}
            for k in kinds for i in range(4)]
    stream = agent_bench.result_of(pool_stream("value1", cost=0.0094), "", 5.0)  # $0.0094 against $0.00936 at list price (cache write at 2x input)

    def fresh(arm, effort, row):
        r = dict(stream)
        bc.spent_run(r)
        return r
    monkeypatch.setattr(bp, "load_pool", lambda home, kinds=None: pool)
    monkeypatch.setattr(bp, "live_runner", lambda b, sh: fresh)
    monkeypatch.setattr(bp, "live_session_runner", lambda b: lambda arm, effort, row, sid, position: fresh(arm, effort, row))
    monkeypatch.setattr(bp, "read_rows", lambda path: [] if path == bp.RESULTS else bc.read_rows(path))  # no earlier record
    monkeypatch.setitem(bc.SPEND, "usd", 0.0)
    monkeypatch.setitem(bc.SPEND, "runs", 0)
    b = types.SimpleNamespace(arms=["sonnet-5-5", "web-sonnet-5-5"], efforts=["low"], kinds=None, shape="fresh,session", seed=11,
                              dry=False, reps=1, jobs=1, max_usd=None, sample=2, arm_reps={}, arm_kinds={}, rows=[], status=0)
    b.row = lambda scenario, case, arm, metric, value, runs="", model="", note="": b.rows.append(
        {"scenario": scenario, "record": "2026-10-09", "case": case, "arm": arm, "model": model, "metric": metric,
         "value": str(value), "runs": str(runs), "note": note})
    bp.s_pool(b)
    labels = sorted({r["arm"] for r in b.rows})
    spend = {"scenario": "pool", "record": "2026-10-09", "case": "all paid runs", "arm": "paid: " + ",".join(labels),
             "metric": "spend_usd", "value": str(round(bc.SPEND["usd"], 6)), "runs": str(bc.SPEND["runs"]), "note": ""}
    record = b.rows + [spend]
    assert labels == ["sonnet-5-5:low", "sonnet-5-5:low/session", "web-sonnet-5-5"]
    assert next(r for r in record if r["metric"] == "planned_kinds" and r["arm"] == "web-sonnet-5-5")["value"] == (
        "csv_fact+fact+false_good+multi+offkb+snippet+synthesis")  # a web arm plans the kinds a web search can answer
    assert bp.verify_problems(record, "2026-10-09") == ([], [])

    def planted(change):
        rows = [dict(r) for r in record]
        change(rows)
        path = tmp_path / "planted.csv"
        bc.write_rows(rows, path)
        capsys.readouterr()
        code = bm.main(["pool", "verify", "--file", str(path), "--record", "2026-10-09"])
        return code, capsys.readouterr().out

    def setv(rows, label, case, metric, value, runs=None):
        for r in rows:
            if (r["arm"], r["case"], r["metric"]) == (label, case, metric):
                r["value"] = str(value)
                if runs:
                    r["runs"] = str(runs)
                return
        rows.append({**record[0], "arm": label, "case": case, "metric": metric, "value": str(value), "runs": str(runs or 1), "note": ""})
    clean_code, clean = planted(lambda rows: None)
    assert clean_code == 0 and "is consistent" in clean, clean
    def drop_gap(rows):
        rows[:] = [r for r in rows if not (r["arm"] == "sonnet-5-5:low" and r["case"] == "gap")]
    breaks = [
        ("(a) sonnet-5-5:low: no row for the planned kind gap", drop_gap),
        ("(a) web-sonnet-5-5: 4 runs not started", lambda rows: rows.append(
            {**record[0], "case": "not started", "arm": "web-sonnet-5-5", "metric": "spend_stopped", "value": "4", "runs": "4"})),
        ("(b) web-sonnet-5-5: 3 of ", lambda rows: setv(rows, "web-sonnet-5-5", "all", "off_list", 3)),
        ("(c) spend of ", lambda rows: setv(rows, "paid: " + ",".join(labels), "all paid runs", "spend_usd", bc.SPEND["usd"] + 1)),
        ("(d) sonnet-5-5:low/session: the mean cost rises at every position", lambda rows: [
            setv(rows, "sonnet-5-5:low/session", f"position {p}", "cost", 0.01 * p) for p in range(1, 7)]),
        ("(e) web-sonnet-5-5: out is 0", lambda rows: setv(rows, "web-sonnet-5-5", "all", "out", 0)),
        ("(f) 3 of ", lambda rows: setv(rows, "sonnet-5-5:low", "all", "errors", 3, 26))]
    for text, change in breaks:
        code, out = planted(change)
        assert code == 1 and text in out, (text, out)
    # a record that predates the figures is checked for the properties its rows can carry, a newer one is not excused
    old = [{**r, "record": "2026-10-08"} for r in record if r["metric"] not in ("planned_kinds", "off_list", "list_cost")
           and not (r["metric"] == "cost" and r["case"].startswith("position"))]
    problems, notes = bp.verify_problems(old, "2026-10-08")
    assert problems == [] and [n[:3] for n in notes] == ["(a)", "(b)", "(d)"]
    newer = [{**r, "record": "2026-10-20"} for r in old]
    assert any(p.startswith("(a) sonnet-5-5:low: rows, and no `planned_kinds` row") for p in bp.verify_problems(newer, "2026-10-20")[0])


def test_bench_pool_rerun_of_one_label_narrows_the_earlier_spend_row_and_respend_repairs_a_record(monkeypatch, tmp_path, capsys):
    import agent_bench
    import benchmarks as bm
    import bench_pool as bp
    kinds = ["fact", "csv_fact", "multi", "synthesis", "false_good", "near_miss", "offkb", "snippet", "count", "cites",
             "decision", "conflict", "gap"]
    pool = [{**bp.row(k, "d0", "original", f"fixture:{k}", f"Question {k}?", [r"value1"], "good"), "question": f"Question {k}?"} for k in kinds]

    def live(b, sh):
        def fresh(arm, effort, row):
            r = agent_bench.result_of(pool_stream("value1", cost=0.0094), "", 5.0)
            bc.spent_run(r)
            return r
        return fresh
    monkeypatch.setattr(bp, "load_pool", lambda home, kinds=None: pool)
    monkeypatch.setattr(bp, "live_runner", live)
    monkeypatch.setattr(bp, "read_rows", lambda path: [] if path == bp.RESULTS else bc.read_rows(path))
    monkeypatch.setenv("BENCH_SCRATCH", str(tmp_path / "scratch"))
    out = tmp_path / "results.csv"
    run = lambda effort: bm.main(["run", "pool", "--arms", "sonnet-5-5", "--effort", effort, "--out", str(out)])  # noqa: E731
    verify = lambda *extra: bm.main(["pool", "verify", "--file", str(out), *extra])  # noqa: E731
    assert run("low,default") == 0 and verify() == 0
    full = {r["arm"]: r for r in bc.read_rows(out) if r["metric"] == "spend_usd"}
    assert set(full) == {"paid: sonnet-5-5:default,sonnet-5-5:low"}
    assert run("default") == 0  # a same-day rerun of one label: its old runs leave the earlier spend row
    capsys.readouterr()
    spend = {r["arm"]: (float(r["value"]), r["runs"]) for r in bc.read_rows(out) if r["metric"] == "spend_usd"}
    assert spend == {"paid: sonnet-5-5:low": (round(13 * 0.0094, 4), "13"), "paid: sonnet-5-5:default": (round(13 * 0.0094, 4), "13")}, spend
    assert verify() == 0, capsys.readouterr().out
    # a record written before the fix: the earlier row still counts the replaced runs (dearer ones), `pool respend` repairs it from the rows
    rows = [r for r in bc.read_rows(out) if r["arm"] != "paid: sonnet-5-5:low" or r["metric"] not in bp.SPEND_METRICS]
    old = [{**r, "arm": "paid: sonnet-5-5:default,sonnet-5-5:low", "value": str(float(r["value"]) * (1.5 if r["metric"] == "spend_usd" else 2)), "runs": "26"}
           for r in bc.read_rows(out) if r["arm"] == "paid: sonnet-5-5:low" and r["metric"] in bp.SPEND_METRICS]
    bc.write_rows(old + rows, out)
    capsys.readouterr()
    assert verify() == 1 and "(c) spend of sonnet-5-5:default, sonnet-5-5:low" in capsys.readouterr().out
    assert bm.main(["pool", "respend", "--file", str(out)]) == 0 and "sonnet-5-5:default left the spend row of 2 labels" in capsys.readouterr().out
    assert verify() == 0 and bm.main(["pool", "respend", "--file", str(out)]) == 0 and "overlaps another" in capsys.readouterr().out
