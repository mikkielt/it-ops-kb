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
