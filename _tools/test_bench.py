"""The benchmarks' harness: a run is priced by the pinned model it reports (bench_core.PRICE), its effective input weights
cache reads by that model's own read ratio, and a tiered price records the tier the run's tokens fall in; the question pool
(bench_pool.py) builds on a fixture kb and store, with its counts per kind, a seed that decides, held-out rows without text
and the query log kept out of the public file."""
import inspect, json, os
from pathlib import Path

import pytest

import bench_core as bc


def req(model, uncached, write, read, out):
    return {"model": model, "usage": {"input_tokens": uncached, "cache_creation_input_tokens": write,
                                      "cache_read_input_tokens": read, "output_tokens": out}}


def bench_price_sonnet_55_run_weights_cache_reads_by_its_own_ratio():
    s = bc.usage_sum([req("claude-sonnet-5-5", 100, 1000, 10000, 500)], "sonnet", "2.1.284")
    assert s["model"] == "claude-sonnet-5-5" and s["tier"] == ""
    assert s["effective"] == 100 + 2 * 1000 + 0.1 * 10000  # the read price over the input price: 0.20 / 2.0
    # the table holds the page's 0.10 read; Claude Code's cost figure counted 0.20 up to 2.1.295 and the page's from 2.1.296
    assert bc.PRICE["claude-sonnet-5-5"][0][4] == 0.10
    run = [req("claude-sonnet-5-5", 100, 1000, 10000, 500)]
    last, first = bc.usage_sum(run, "sonnet", "2.1.295"), bc.usage_sum(run, "sonnet", "2.1.296")
    assert last["effective"] == s["effective"] and round(bc.est_cost(last), 6) == round(
        (100 * 2 + 1000 * 4.0 + 10000 * 0.20 + 500 * 10) / 1e6, 6)
    assert first["effective"] == 100 + 2 * 1000 + 0.05 * 10000
    assert round(bc.est_cost(first), 6) == round((100 * 2 + 1000 * 4.0 + 10000 * 0.10 + 500 * 10) / 1e6, 6)
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


def bench_price_tier_is_recorded_and_alias_follows_the_run():
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
    sc = ""
    for kind, route in (("sc_present", "good"), ("sc_partial", "split"), ("sc_absent", "web"), ("sc_offkb", "none"),
                        ("sc_stale", "good")):
        answer = "" if kind in ("sc_absent", "sc_offkb") else r"value\d+"
        for n in range(6):
            note = "false good: the pack lacks it" if kind == "sc_absent" and n == 0 else ""
            sc += f"{kind},d{n},Scenario {kind} question {n}?,{answer},{route},{note}\n"
    (ret / "bench_scenarios.csv").write_text("kind,domain,question,answer,route,note\n" + sc, encoding="utf-8")
    run = tmp_path / "kb" / "_querylog" / "2026-10"
    run.mkdir(parents=True)
    head = '{"run":"20261008T000000Z-aaaaaaaa","pipeline":7,"retrieval":8,"counts":{"entries":%d,"dropped":0,"waiting":0}}\n'
    ents = "".join(json.dumps({"id": f"{i:08x}-0000-4000-8000-{i:012x}", "surface": "prompt", "day": "2026-10-08",
                               "question": q, "verdict": "good", "articles": [f"public/d{i % 6}/a0.md"],
                               "citations": [{"line": "kb/_self/x.md:1" if i == 5 else f"public/d{i % 6}/a0.md:1"}]}) + "\n"
                   for i, q in enumerate(ql_questions))
    (run / "20261008T000000Z-aaaaaaaa.jsonl").write_text(head % len(ql_questions) + ents, encoding="utf-8")


def scenario_pack(question):
    """The pack a scenario question gets in the fixture: the route its kind expects (a gap question, which names no kind,
    routes to web), one fact line and one stale source."""
    import re
    route = {"sc_present": "good", "sc_partial": "split", "sc_absent": "web", "sc_offkb": "web", "sc_stale": "good"}
    kind = re.search(r"sc_\w+", question)
    return route[kind.group()] if kind else "web", "- d0/a0.md:7 equals value1\n\nsources:\n  -> S-src00000  https://x"


def bench_pool_build_counts_seed_heldout_and_querylog_stay_apart(tmp_path, monkeypatch, capsys):
    import argparse, re
    import bench_pool as bp
    monkeypatch.setattr(bp, "scenario_pack", scenario_pack)
    monkeypatch.setattr(bp, "source_stale", lambda ids: list(ids))
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
        "demand, so the gadget license and release channel show in one view.\n"
        "The gadget retry timeout is 45 seconds.\n\n"
        "- The gadget license and release channel are listed in `zz/plant.md`.\n"
        "- A gadget license is a signed file.\n"
        "  The gadget retry timeout is 90 seconds here.\n", encoding="utf-8")
    wrapped = {"question": "What is the gadget license and release channel?", "expect_paths": "zz/wrap.md"}
    assert bp.fact_for(tmp_path / "side", wrapped)[1] == 6  # the paragraph's first line; its wrapped line 7 and the pointer line 10 are no facts
    wrap_lines = (side / "wrap.md").read_text(encoding="utf-8").splitlines()
    assert [n for n, _ in bp.article_facts(wrap_lines)] == [6, 11]  # a wrapped line, even one that opens a sentence, is no fact of its own
    assert [n for n, _ in bp.article_facts(wrap_lines, prose=True)] == [6, 8, 11]  # a prose line that opens a sentence is; a list item's line is not
    assert bp.fact_for(tmp_path / "side", {"question": "gadget retry timeout seconds", "expect_paths": "zz/wrap.md"})[1] == 8  # the timeout sits on the third line of a paragraph
    (side / "phrase.md").write_text(
        "---\ntopic: zz/phrase\n---\n\n- The sync status of the board shows each agent and gizmo once a day.\n"
        "- The gizmo sync agent status board lists every gizmo.\n", encoding="utf-8")
    ask = {"question": "gizmo sync agent status board", "expect_paths": "zz/phrase.md"}
    assert bp.fact_for(tmp_path / "side", ask)[1] == 6  # the question's own four-word phrase, over a line with the same stems scattered
    with monkeypatch.context() as m:
        m.setattr(bp, "PHRASE_WEIGHT", 0.0)
        assert bp.fact_for(tmp_path / "side", ask)[1] == 5  # without the phrase weight the two lines tie and the first wins
    (side / "mixed.md").write_text(
        "---\ntopic: zz/mixed\n---\n\n- Sprocket timeout is 30 seconds; the full table is in `zz/plant.csv`.\n"
        "- See `zz/plant.csv` for the sprocket timeout.\n\n```\nsprocket timeout seconds\n```\n\n"
        "| Sprocket timeout seconds | Sprocket value |\n|---|---|\n| Sprocket cog | teeth |\n", encoding="utf-8")
    mixed = bp.article_facts((side / "mixed.md").read_text(encoding="utf-8").splitlines())
    assert [n for n, _ in mixed] == [5, 14]  # a fact keeps its pointer clause; a pure pointer, a code line and a table header are none
    assert bp.fact_for(tmp_path / "side", {"question": "sprocket timeout seconds", "expect_paths": "zz/mixed.md"})[1] == 5
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
        [w for _, w in kept][-2][:19], [w for _, w in kept][-1][:16]) == ("`Setting` is in 24 ", "`value\\d+` is in")  # the others keep the committed check; a pattern found across the articles is refused as a word is
    rows_of = {"own": ("a", "q"), "x": ("b", "value1"), "y": ("c", "value2"), "z": ("d", "value3"), "same": ("a", "value4")}
    assert bp.too_broad(r"value\d+", "own", rows_of, []) == "it matches 3 other eval rows"  # the row on the fact line of its own is not another
    assert bp.too_broad(r"value\d+|Setting", "own", {"own": ("a", "q")}, ["value1 Setting"] * 11).startswith("`value\\d+` is in 11 ")  # the phrase or pattern is judged too
    assert bp.too_broad(r"value\d+|(", "own", {"own": ("a", "q")}, ["value1"] * 10) == ""  # ten articles are not common; an alternative that does not compile is skipped
    own = {"own": ("a", "q")}
    assert bp.too_broad("Export-Cmd|Invented-Cmd", "own", own, ["Export-Cmd is real"]) == "`Invented-Cmd` is in no line of the kb"  # a name no line states
    assert bp.too_broad("Export-Cmd|Row-Cmd", "own", own, ["Export-Cmd is real"], ["id,Row-Cmd\n"]) == ""  # a data file's line is a line of the kb
    with pytest.raises(bp.PoolError):
        bp.build_public(tmp_path, 3, redo_ask, out, ["EV-nope"])
    replies = tmp_path / "replies.csv"
    bp.write_csv(replies, [{**r, "checks": json.dumps([r"value\d+"])} for r in rows])
    kept2 = []
    assert bp.build_public(tmp_path, 3, bp.csv_replies(replies), out, names[:1], kept2) == rows and [w[:10] for _, w in kept2] == [
        "`value\\d+`"]  # a csv answers without a model, and the guards judge its reply
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
    fresh = tmp_path / "fresh.csv"
    rns = argparse.Namespace(pool_cmd="build", querylog=False, seed=3, out=str(fresh), redo=None, dry_run=False, ask=False)
    assert bp.cli(rns, tmp_path) == 1 and not fresh.exists()  # neither --ask nor --redo: the rows are listed, nothing is asked or written
    assert "no call without --ask" in capsys.readouterr().out
    monkeypatch.setattr(bp, "sonnet_regexes", lambda items: [r"value\d+"] * len(items))
    rns.ask = True
    assert bp.cli(rns, tmp_path) == 0 and fresh.is_file()  # --ask asks as before
    held = [r for r in rows if r["kind"] == "heldout"]
    assert all(r["question"] == "" and json.loads(r["checks"]) for r in held)
    assert "HELDOUT TEXT" not in out.read_text(encoding="utf-8") and "HELDOUT TEXT" in bp.question_of(held[0], tmp_path)
    assert bp.check_problems(rows, tmp_path) == []
    assert {r["kind"]: r["expected_route"] for r in rows if r["kind"].startswith("sc_")} == {
        "sc_present": "good", "sc_partial": "split", "sc_absent": "web", "sc_offkb": "none", "sc_stale": "good"}
    assert all(json.loads(r["checks"]) == bp.scenario_checks(r["kind"], r"value\d+") for r in rows if r["kind"].startswith("sc_"))
    sc_file = tmp_path / bp.SCENARIO_FILE
    sc_text = sc_file.read_text(encoding="utf-8")
    sc_file.write_text(sc_text.replace("Scenario sc_offkb question 1?", "How do I run off-kb thing 3?"), encoding="utf-8")
    with pytest.raises(bp.PoolError, match="a line of the off-kb list"):  # the planted failure: an off-kb question the list holds
        bp.build_public(tmp_path, 3, lambda items: pytest.fail("a defective scenario file asks"), out)
    sc_file.write_text(sc_text.replace("Scenario sc_offkb question 1?", "What does setting alpha1 beta1 gamma1 equal  case 1?"),
                       encoding="utf-8")
    with pytest.raises(bp.PoolError, match="the question of a good eval row"):
        bp.build_public(tmp_path, 3, lambda items: pytest.fail("a defective scenario file asks"), out)
    sc_file.write_text(sc_text, encoding="utf-8")
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


def bench_pool_check_reports_stale_pick_of_a_row_whose_check_misses_the_picked_line(tmp_path, capsys, monkeypatch):
    import argparse, re
    import bench_pool as bp
    real_pack = bp.scenario_pack
    monkeypatch.setattr(bp, "scenario_pack", scenario_pack)
    monkeypatch.setattr(bp, "source_stale", lambda ids: list(ids))
    pool_home(tmp_path, [f"fixture session question number {i} about topic {i} in detail" for i in range(26)])
    out = tmp_path / "pool.csv"
    rows = bp.build_public(tmp_path, 3, lambda items: [r"value\d+"] * len(items), out)
    bp.write_csv(out, rows)
    check = argparse.Namespace(pool_cmd="check", file=str(out), querylog=False)
    assert bp.cli(check, tmp_path) == 0 and capsys.readouterr().out == ""  # every committed check matches the line picked
    stale = next(r for r in rows if r["kind"] == "fact")
    stale["checks"] = json.dumps(["no such answer"])
    bp.write_csv(out, rows)
    assert bp.cli(check, tmp_path) == 0  # a warning: the row's check still holds until it is redone
    seen = capsys.readouterr().out
    assert seen.count("warning") == 1 and f"{stale['id']}: warning: no check matches" in seen
    assert f"`pool build --redo {stale['id']}`" in seen
    stale["checks"] = json.dumps([r"value\d+"])
    absent = next(r for r in rows if r["kind"] == "sc_absent")  # its note marks a false good: a good or split pack is no defect
    present = next(r for r in rows if r["kind"] == "sc_present")
    monkeypatch.setattr(bp, "scenario_pack", lambda q: ("good" if "sc_absent question 0" in q else scenario_pack(q)[0],
                                                       scenario_pack(q)[1]))
    bp.write_csv(out, rows)
    assert bp.cli(check, tmp_path) == 0 and capsys.readouterr().out == ""
    monkeypatch.setattr(bp, "scenario_pack", lambda q: ("web" if q == present["question"] else scenario_pack(q)[0], scenario_pack(q)[1]))
    assert bp.cli(check, tmp_path) == 1  # the planted failure: a route the pack no longer prints
    seen = capsys.readouterr().out
    assert f"{present['id']}: expected route good but the pack prints web for its question" in seen and absent["id"] not in seen
    partial = next(r for r in rows if r["kind"] == "sc_partial")
    monkeypatch.setattr(bp, "scenario_pack", lambda q: (scenario_pack(q)[0], "- d0/a0.md:7 states nothing"
                                                        if q == partial["question"] else scenario_pack(q)[1]))
    assert bp.cli(check, tmp_path) == 1  # the planted failure: a pack with no line the row's answer regex matches
    assert f"{partial['id']}: its answer regex matches no line of the pack for its question" in capsys.readouterr().out
    import kbfacts
    flagged = {"route": "", "text": "check: a cited line may not answer it\n- d0/a0.md:7 equals value1\n\nsources:\n  -> S-src00000  https://x"}
    monkeypatch.setattr(kbfacts, "pack_many", lambda questions: flagged)  # the real scenario_pack reads this pack
    monkeypatch.setattr(bp, "scenario_pack", real_pack)
    assert real_pack(present["question"]) == ("check", flagged["text"])  # the pack prints a check: line and no route: line
    assert bp.cli(check, tmp_path) == 1  # the planted failure: a good row whose pack prints a check: line, never read as good
    seen = capsys.readouterr().out
    assert f"{present['id']}: expected route good but the pack prints a check: line and no route: for its question" in seen
    assert absent["id"] not in seen  # an sc_absent row marked a false good takes a check: line
    assert not re.search(bp.FRESH_CHECK, "## public/d0/a0.md  Fixture topic  [partial, retrieved 2026-10-13]")  # a bare header's date
    assert re.search(bp.FRESH_CHECK, "last confirmed 2026-10-13") and re.search(bp.FRESH_CHECK, "source changed since")
    monkeypatch.setattr(bp, "scenario_pack", scenario_pack)
    gap = next(r for r in rows if r["kind"] == "gap")
    gap["source"] = "_gaps.md#00000000"  # the planted failure: a gap row whose entry is no longer open
    bp.write_csv(out, rows)
    assert bp.cli(check, tmp_path) == 1 and f"{gap['id']}: its entry _gaps.md#00000000 is no longer open" in capsys.readouterr().out
    gap["source"] = bp.gap_source(next(t for t, _ in bp.open_gaps(tmp_path)))
    monkeypatch.setattr(bp, "scenario_pack", lambda q: ("good" if q == gap["question"] else scenario_pack(q)[0], scenario_pack(q)[1]))
    bp.write_csv(out, rows)
    assert bp.cli(check, tmp_path) == 1  # the planted failure: a gap row whose pack no longer routes to web
    assert f"{gap['id']}: expected route web but the pack prints good" in capsys.readouterr().out
    monkeypatch.setattr(bp, "scenario_pack", scenario_pack)
    present["checks"] = json.dumps([r"never printed"])
    bp.write_csv(out, rows)
    assert bp.cli(check, tmp_path) == 1 and "differs from its row of" in capsys.readouterr().out
    monkeypatch.setattr(bp, "source_stale", lambda ids: [])
    present["checks"] = json.dumps([r"value\d+"])
    bp.write_csv(out, rows)
    assert bp.cli(check, tmp_path) == 0  # a stale-source row whose sources a census confirmed is a warning
    assert capsys.readouterr().out.count("cites no source past its freshness lifetime") == bp.SCENARIO_ROWS
    invented = "Set-InventedThing"  # no article and no data file of the fixture kb states it
    stale["checks"] = json.dumps([r"value\d+", invented])  # a row built on a lookup_eval.csv case: the model's check
    hand = next(r for r in rows if r["kind"] == "near_miss" and not r["source"].startswith("lookup_eval.csv:"))
    hand["checks"] = json.dumps([invented])  # a hand-written near-miss row: its check is the author's
    bp.write_csv(out, rows)
    assert bp.cli(check, tmp_path) == 0  # a warning, not a defect
    seen = capsys.readouterr().out
    assert seen.count("found in no article or data file") == 1
    assert f"{stale['id']}: warning: its check names `{invented}`, found in no article or data file of the kb" in seen
    assert f"`pool build --redo {stale['id']}`" in seen and hand["id"] not in seen  # the near-miss row is not judged


def bench_pool_scenario_rows_derived_cells_and_report_tables(monkeypatch):
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
    usage = {m.replace("haiku-5-5", "haiku-5-5-20260301"): u for m, u in summary["model_usage"].items()}
    dated = {**summary, "model_usage": usage}
    assert "claude-haiku-5-5-20260301" in usage and bp.list_usd(dated, "sonnet") == bp.list_usd(summary, "sonnet")  # a dated key is priced at its pinned model
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


class FreshBench:
    """What a scenario needs of bench_core.Bench: the rows it writes, in the results file's shape, and the options."""

    def __init__(self, dry=False):
        self.rows, self.dry, self.sample, self.seed = [], dry, None, 11

    def row(self, scenario, case, arm, metric, value, runs="", model="", note=""):
        self.rows.append({"scenario": scenario, "record": "2026-10-12", "date": "2026-10-12", "commit": "", "claude_code": "",
                          "kb_topics": "", "case": case, "arm": arm, "model": model, "metric": metric, "value": str(value),
                          "runs": str(runs), "note": note})


def bench_freshness_rows_dry_run_and_report_check_exits_1_on_a_marker_with_no_rows(tmp_path, monkeypatch, capsys):
    import benchmarks as bm
    import bench_core as bc
    import bench_pool as bp
    import bench_report as br
    import bench_retrieval as bret
    import kbfacts
    import provider
    # a fixture pool of two answerable rows and one the kb does not answer, units with and without a DOC tag, five
    # sources on three hosts: the scenario's tally per outcome and host, its requests counted at provider.request (a
    # request the time budget refused is none, one with no answer is a failed one) and its dry run, which asks nothing
    url = {"S1": "https://learn.microsoft.com/a", "S2": "https://raw.githubusercontent.com/o/r/c/b.md",
           "S3": "https://learn.microsoft.com/c", "S4": "https://code.claude.com/d", "S5": "https://learn.microsoft.com/e"}
    unit = lambda line, kind: {"path": "public/x.md", "line": line, "tags": [{"kind": kind, "ids": []}]}  # noqa: E731
    units = [unit(1, "DOC"), unit(2, "DOC"), unit(3, "CODE"), unit(4, "DOC"), unit(5, "DOC")]
    printed = {"q1": [(1, ["S1"]), (2, ["S2", "S3"]), (3, ["S1"])], "q2": [(1, ["S1"]), (4, ["S4"]), (5, ["S5"])]}
    outcome = {("q1", 1): ("current", "S1"), ("q1", 2): ("moved", "S2"), ("q2", 1): ("not found", "S1"),
               ("q2", 4): ("", ""), ("q2", 5): ("source-dated only", "S5")}
    pool = [{"id": "P1", "kind": "fact", "expected_route": "good", "question": "q1"},
            {"id": "P2", "kind": "heldout", "expected_route": "good", "question": "q2"},
            {"id": "P3", "kind": "offkb", "expected_route": "none", "question": "q3"}]
    monkeypatch.setattr(bp, "load_pool", lambda home=None, kinds=None: pool)
    monkeypatch.setattr(kbfacts, "units", lambda *a, **kw: units)
    monkeypatch.setattr(kbfacts, "source_rows", lambda: {k: {"url": v} for k, v in url.items()})
    asked = []

    def request(u, *a, **kw):
        asked.append(u)
        if u == url["S4"]:
            return {"status": 0, "error": provider.BUDGET_ERROR}
        return {"status": 0, "error": "boom"} if u == url["S3"] else {"status": 200, "error": ""}
    monkeypatch.setattr(provider, "request", request)

    def pack_many(questions, revalidate=False, **kw):
        q = questions[0]
        lines = [{"path": "public/x.md", "line": n, "key": f"k{n}", "text": "t", "ids": ids} for n, ids in printed[q]]
        res = {"results": [{"printed": lines}]}
        if revalidate:
            sources = {}
            for sid in sorted({i for _, ids in printed[q] for i in ids}):
                got = provider.request(url[sid])
                sources[sid] = {"state": "live" if got["status"] else "offline", "verdict": "", "why": got["error"]}
            res["revalidate"] = {"sources": sources, "lines": {
                f"public/x.md:{n}": {"outcome": outcome[(q, n)][0], "id": outcome[(q, n)][1], "unchecked": {}}
                for n, _ in printed[q] if (q, n) in outcome}}
        return res
    monkeypatch.setattr(kbfacts, "pack_many", pack_many)
    assert "freshness" in bm.SCENARIOS and "freshness" in bm.PLANNED  # a --dry-run of it is a plan, not a run
    asked.clear()
    plan = FreshBench(dry=True)
    with pytest.raises(bc.Skip) as stopped:
        bret.s_freshness(plan)
    shown = capsys.readouterr().out
    assert asked == [] and plan.rows == []  # no request, no row
    assert "learn.microsoft.com: 3 sources, 4 lines in 2 questions, 4 requests" in shown
    assert "S2  https://raw.githubusercontent.com/o/r/c/b.md  (1 question)" in shown
    assert str(stopped.value).startswith("dry run: 2 answerable pool rows, 5 printed DOC lines, 5 sources on 3 hosts, 6 requests")
    live = FreshBench()
    bret.s_freshness(live)
    assert provider.request is request  # the counting wrapper is gone with the run
    got = {(r["case"], r["metric"]): r["value"] for r in live.rows}
    assert [got[("all", m)] for m in ("doc_lines", "current", "moved", "not_found", "source_dated_only", "not_checked")] == [
        "5", "1", "1", "1", "1", "1"]  # the CODE unit's line is no DOC line
    assert got[("all", "current_share")] == "0.2" and got[("all", "questions")] == "2" and got[("all", "budget_spent")] == "1"
    assert (got[("all", "requests")], got[("all", "failed_requests")]) == ("5", "1")  # the refused one was never made
    assert (got[("learn.microsoft.com", "requests")], got[("learn.microsoft.com", "failed_requests")]) == ("4", "1")
    assert got[("raw.githubusercontent.com", "moved")] == "1" and got[("raw.githubusercontent.com", "requests")] == "1"
    assert got[("code.claude.com", "not_checked")] == "1" and got[("code.claude.com", "requests")] == "0"  # none was made
    assert float(got[("all", "p95_s")]) >= float(got[("all", "median_s")]) >= 0 and got[("all", "sources_offline")] == "2"  # S3 failed, S4 refused
    marker = "<!-- bench:table freshness metrics=current,current_share,requests,median_s cases=all -->\n<!-- /bench -->\n"
    assert "| all | current | 1 | 20.0% | 5 | " in br.render(marker, live.rows) and br.empty_markers(marker, live.rows) == []
    # report --check reads the rows of a results file against the report's markers: one with no rows fails it
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


def bench_pool_session_shape_groups_resume_marginal_input_and_cache_share(monkeypatch):
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


def bench_pool_max_usd_in_flight_counts_the_runs_started_and_jobs_parallel_rows_equal_one_job_and_the_record_date_holds(monkeypatch, tmp_path):
    import time
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
        # a run priced at its kind's cost counts while in flight: four runs of $0.01 fit $0.045 at any `jobs`, no fifth starts
        reset()
        left = []
        got = bp.run_pool(rows[:4], cells, 2, slow_first([]), None, jobs=jobs, cap=0.045, left=left, usd=lambda label, kind: 0.01)
        assert got == one[:4] and len(left) == 20 and spend() == (0.04, 4)
    # run_tasks: ten tasks of $1 on four jobs under a cap of $3 start three (not the five that finish before a fourth is
    # looked at), whatever the order they finish in; a task with no price is priced at 0, and the first starts whatever it costs
    for cap, started in ((3.0, 3), (3.5, 3), (4.0, 4)):
        reset()
        first = []

        def work(task, first=first):
            time.sleep(0.03 if task == 0 else 0.002)
            first.append(task)
            bc.spent(1.0, 0, 0)
            return task
        got, rest = bp.run_tasks(list(range(10)), work, jobs=4, cap=cap, price=lambda task: 1.0)
        assert got == list(range(started)) and rest == list(range(started, 10)) and spend() == (float(started), started)
    reset()
    got, rest = bp.run_tasks(list(range(10)), lambda task: bc.spent(1.0, 0, 0) or task, jobs=4, cap=0.5, price=lambda task: 9.0)
    assert (got, rest[0], spend()) == ([0], 1, (1.0, 1))  # one run over a cap below its price, then the spend stops the rest
    reset()
    got, rest = bp.run_tasks(list(range(10)), lambda task: task, jobs=4, cap=0.0, price=lambda task: 1.0)
    assert got == [] and len(rest) == 10  # no cap above 0, no run
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
    reset()  # a session is priced as its six questions: $0.06 each, so three jobs under $0.15 start two, not three
    order.clear()
    fresh, left = slow_first([]), []
    capped = bp.run_sessions(groups, cell, 2, session_runner, jobs=3, cap=0.15, left=left, usd=lambda label, kind: 0.01)
    assert len(order) == 2 and len(capped) == 12 and spend() == (0.12, 12) and [n for _, n in left] == ["group 2#1", "group 2#2"]
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


def bench_pool_dry_run_kind_prices_and_jobs_scenario_stops_at_the_cap_with_a_spend_stopped_row(monkeypatch, capsys):
    import types
    import bench_pool as bp
    monkeypatch.setitem(bc.SPEND, "usd", 0.0)
    monkeypatch.setitem(bc.SPEND, "runs", 0)
    history = []  # the results file the estimates read: none at first
    monkeypatch.setattr(bp, "load_pool", lambda home, kinds=None: pool_rows(6))
    monkeypatch.setattr(bp, "live_runner", lambda b, sh: slow_first([]))
    monkeypatch.setattr(bp, "read_rows", lambda path: history)
    b = types.SimpleNamespace(arms=["sonnet-5-5"], efforts=["low"], kinds=None, shape="fresh", seed=1, dry=False, reps=2, jobs=2,
                              max_usd=0.045, rows=[], status=0)
    b.row = lambda scenario, case, arm, metric, value, runs="", model="", note="": b.rows.append((case, arm, metric, value, note))
    history.append({"scenario": "pool", "record": "2026-10-08", "case": "all", "arm": "sonnet-5-5:low", "model": "claude-sonnet-5-5",
                    "metric": "cost", "value": "0.01"})  # a run costs $0.01 (what the fake runner bills): four fit $0.045
    bp.s_pool(b)
    stopped = [r for r in b.rows if r[2] == "spend_stopped"]
    assert b.status == 1 and len(stopped) == 1 and stopped[0][:3] == ("not started", "sonnet-5-5:low", "spend_stopped")
    assert stopped[0][3] == len(stopped[0][4].split(", ")) == 8 and "#" in stopped[0][4] and bc.SPEND["runs"] == 4
    assert bc.SPEND["usd"] <= 0.045  # `jobs` 2 runs in flight did not carry it past the cap
    history.clear()
    b.dry, b.rows = True, []
    with pytest.raises(bp.Skip) as e:  # the estimate prices the stated default tokens at bench_core's prices
        bp.s_pool(b)
    run = (2000 * 2.0 + 8000 * 4.0 + 80000 * 0.10 + 1200 * 10.0) / 1e6  # a cache write at the 1-hour price
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
    legs = [bp.Leg("fresh", bp.plan_cells(arms, bp.EFFORTS), {a: [{}] * (13 if a.startswith("web-") else 35) for a in arms}, {}, {}, dict.fromkeys(arms, 1)),
            bp.Leg("session", bp.plan_cells(sessions, bp.EFFORTS), {}, {a: [[{}] * 6] * 5 for a in sessions}, {}, dict.fromkeys(sessions, 1))]
    est = {label: runs * usd for _, _, label, runs, usd, *_ in bp.estimates(legs, record)}
    assert all(abs(est[label] - usd) <= 0.25 * usd for label, usd in smoke.items()), {k: (est[k], v) for k, v in smoke.items()}
    mean = lambda label: float(next(r["value"] for r in record if r["arm"] == label and r["case"] == "all" and r["metric"] == "cost"))  # noqa: E731
    rest = {"web-haiku-5-5": 13, "web-sonnet-5-5": 13, **{f"{m}-5-5:{e}/session": 30 for m in ("haiku", "sonnet") for e in bp.EFFORTS}}
    full = sum(smoke.values()) + 35 * 0.021 + sum(n * mean(label) for label, n in rest.items())  # the router's one smoke run cost 0.021
    assert abs(sum(est.values()) - full) <= 0.25 * full and sum(est.values()) >= 12
    # a kind is priced at its own mean cost in the label's newest record that has it, not at the mean over all kinds
    # (SP-kp3boz7z: 60 runs of two kinds, estimated at the all-kinds mean $3.51 and billed $5.72 against a $5 cap)
    kind_cell = lambda label, case, usd, rec="2026-10-09": [{**r, "case": case} for r in  # noqa: E731
                                                            cell(rec, label, "claude-sonnet-5-5", cost=usd, **tokens)]
    kinds = (kind_cell("sonnet-5-5:low", "all", 0.0585) + kind_cell("sonnet-5-5:low", "sc_absent", 0.03)
             + kind_cell("sonnet-5-5:low", "sc_partial", 0.10) + kind_cell("sonnet-5-5:low", "sc_old", 0.07, "2026-10-01"))
    assert bp.assumed_run("sonnet-5-5:low", "sonnet-5-5", kinds, "sc_partial")[0] == 0.10
    assert bp.assumed_run("sonnet-5-5:low", "sonnet-5-5", kinds, "sc_partial")[3] == "the mean cost of the kind in the record 2026-10-09"
    assert bp.assumed_run("sonnet-5-5:low", "sonnet-5-5", kinds, "sc_old")[3] == "the mean cost of the kind in the record 2026-10-01"
    assert bp.assumed_run("sonnet-5-5:low", "sonnet-5-5", kinds, "fact")[0] == 0.0585  # a kind with no cell: the all cell
    assert bp.assumed_run("sonnet-5-5:low", "sonnet-5-5", kinds)[0] == 0.0585
    # the same kind of a kb twin when the label has no record: its means of that kind, priced as the arm's model
    twin_kind = [{**r, "case": "fact"} for r in cell("2026-10-09", "haiku-5-5:low", "claude-haiku-5-5", cost=0.01, **tokens)]
    got = bp.assumed_run("opus-5-5:low", "opus-5-5", twin_kind, "fact")
    assert got[3] == "the means of the kind of haiku-5-5:low in the record 2026-10-09, priced as claude-opus-5-5"
    assert bp.assumed_run("opus-5-5:low", "opus-5-5", twin_kind, "count")[3] == "the default"
    rows = [{"kind": "sc_absent"}] * 15 + [{"kind": "sc_partial"}] * 15
    leg = bp.Leg("fresh", bp.plan_cells(["sonnet-5-5"], ["low"]), {"sonnet-5-5": rows}, {}, {}, {"sonnet-5-5": 2})
    [(_, _, label, runs, usd, _, _, basis, parts)] = bp.estimates([leg], kinds)
    assert (label, runs) == ("sonnet-5-5:low", 60) and abs(runs * usd - (30 * 0.03 + 30 * 0.10)) < 1e-9  # $3.90, not 60 x $0.0585
    assert [(k, n, u) for k, n, u, _ in parts] == [("sc_absent", 30, 0.03), ("sc_partial", 30, 0.10)]
    capsys.readouterr()
    assert abs(bp.estimate_lines([leg], kinds, 8, 3.8) - 3.9) < 1e-9
    out = capsys.readouterr().out
    assert "by kind: sc_absent 30 x $0.0300, sc_partial 30 x $0.1000" in out and "over --max-usd $3.80" in out
    session = bp.Leg("session", leg.cells, {}, {"sonnet-5-5": [[{"kind": "sc_absent"}] * 4 + [{"kind": "sc_partial"}] * 2]}, {},
                     {"sonnet-5-5": 1})  # a session's questions are priced each at its own kind
    [(_, _, label, runs, usd, *_)] = bp.estimates([session], [{**r, "arm": r["arm"] + "/session"} for r in kinds])
    assert (label, runs) == ("sonnet-5-5:low/session", 6) and abs(runs * usd - (4 * 0.03 + 2 * 0.10)) < 1e-9


def bench_pool_record_plans_arm_reps_kinds_sample_both_shapes_and_one_cap(monkeypatch, capsys):
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
    history = []  # the results the estimates read: none, until a capped run below has each label's cost of $0.01 a run
    monkeypatch.setattr(bp, "read_rows", lambda path: history)

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
    history += [{"scenario": "pool", "record": "2026-10-08", "case": "all", "arm": label, "model": "claude-sonnet-5-5", "metric": "cost",
                 "value": "0.01"} for label in per_label(full)]
    late, _ = record(max_usd=3.505)  # each part of the cap is filled to a run (a session: six) short of it, and none passes it
    stopped = {a: v for c, a, m, v, n, note in late.rows if m == "spend_stopped"}
    assert late.status == 1 and stopped and per_label(late).keys() == per_label(full).keys()
    assert any(not a.endswith("/session") for a in stopped) and 3.505 - 0.12 <= bc.SPEND["usd"] <= 3.505
    assert "sessions not started" in capsys.readouterr().out
    early, _ = record(max_usd=1.0)
    stopped = {a: v for c, a, m, v, n, note in early.rows if m == "spend_stopped"}
    assert early.status == 1 and per_label(early).keys() == per_label(full).keys() and stopped.keys() == per_label(full).keys()
    assert 1.0 - 0.12 <= bc.SPEND["usd"] <= 1.0 and all(0 < n < per_label(full)[a] for a, n in per_label(early).items())
    history.clear()
    # --dry-run: the plan per arm label and the estimate, no run
    capsys.readouterr()
    dry, msg = record(dry=True)
    out = capsys.readouterr().out
    assert not dry.rows and bc.SPEND["runs"] == 0 and "estimated spend $" in msg and "shapes fresh+session" in msg
    assert "pool: sonnet-5-5:low: 52 runs (26 rows x 2 reps)" in out and "pool: web-haiku-5-5: 24 runs (12 rows x 2 reps)" in out
    assert "pool: haiku-5-5:low/session: 36 runs (3 groups x 2 reps, 4 of 22 rows left out)" in out
    # opus-5-5 named in --arms runs its sanity subset (16 of the 52 rows here), every row only for `--arm-kinds opus-5-5=all`
    capsys.readouterr()
    record(dry=True, arms=["opus-5-5"], shape="fresh", sample=None, reps=1, arm_reps={}, arm_kinds={})
    assert "pool: opus-5-5:low: 16 runs (16 rows x 1 reps)" in capsys.readouterr().out
    every, _ = bp.parse_arm_map(["opus-5-5=all"], "--arm-kinds", bp.kinds_value)
    record(dry=True, arms=["opus-5-5"], shape="fresh", sample=None, reps=1, arm_reps={}, arm_kinds=every)
    assert "pool: opus-5-5:low: 52 runs (52 rows x 1 reps)" in capsys.readouterr().out
    # an arm the flags name and the run does not run is an error, not an option left unused
    assert bm.main(["run", "pool", "--arm-reps", "opus-5-5=2", "--arm-kinds", "sonnet-5-5/session=fact", "--dry-run"]) == 2
    err = capsys.readouterr().err
    assert "--arm-reps: opus-5-5 is not run by this command (opt-in: name it in --arms)" in err
    assert "--arm-kinds: sonnet-5-5/session is not run by this command (the --shape has no session)" in err


def bench_pool_verify_exits_1_naming_each_planted_break_of_a_fake_record(monkeypatch, tmp_path, capsys):
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
    b = types.SimpleNamespace(arms=["opus-5-5", "sonnet-5-5", "web-sonnet-5-5"], efforts=["low"], kinds=None, shape="fresh,session",
                              seed=11, dry=False, reps=1, jobs=1, max_usd=None, sample=2, arm_reps={}, arm_kinds={}, rows=[],
                              status=0)
    b.row = lambda scenario, case, arm, metric, value, runs="", model="", note="": b.rows.append(
        {"scenario": scenario, "record": "2026-10-09", "case": case, "arm": arm, "model": model, "metric": metric,
         "value": str(value), "runs": str(runs), "note": note})
    bp.s_pool(b)
    labels = sorted({r["arm"] for r in b.rows})
    spend = {"scenario": "pool", "record": "2026-10-09", "case": "all paid runs", "arm": "paid: " + ",".join(labels),
             "metric": "spend_usd", "value": str(round(bc.SPEND["usd"], 6)), "runs": str(bc.SPEND["runs"]), "note": ""}
    record = b.rows + [spend]
    assert labels == ["opus-5-5:low", "sonnet-5-5:low", "sonnet-5-5:low/session", "web-sonnet-5-5"]
    assert next(r for r in record if r["metric"] == "planned_kinds" and r["arm"] == "opus-5-5:low")["value"] == (
        "csv_fact+multi+near_miss+synthesis")  # a subset arm plans the subset's kinds, and (a) holds with rows for those only
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


def bench_pool_rerun_of_one_label_narrows_the_earlier_spend_row_and_respend_repairs_a_record(monkeypatch, tmp_path, capsys):
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


def bench_repro_setup_pins_one_commit_per_instance_with_its_own_bare_mcp_config_log_mode_and_env(tmp_path, monkeypatch, capsys,
                                                                                               kb_seed):
    import subprocess
    import bench_repro as br
    import benchmarks as bm
    import bl_base
    import conftest
    sh = bc.shim_dir(tmp_path / "shim")  # a `claude` that fails at once: nothing started here may reach a model
    for k, v in {"PATH": f"{sh}{os.pathsep}{os.environ['PATH']}", "KB_SYNC_NO_TESTS": "1", "KB_SESSION": "other-session",
                 "KB_DOCS_CACHE": str(tmp_path / "docs"), "BENCH_SCRATCH": str(tmp_path / "scratch"),
                 "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t",
                 "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}.items():
        monkeypatch.setenv(k, v)
    git = lambda *a, cwd: subprocess.run(["git", *a], cwd=str(cwd), capture_output=True, text=True, check=True).stdout.strip()  # noqa: E731
    src, remote = tmp_path / "src", tmp_path / "remote.git"  # the bare stands in for the integration remote
    src.mkdir()
    git("init", "-q", "--initial-branch=main", cwd=src)
    shas = {}
    for name, files in (("first", ["a.txt"]), ("second", ["b.txt"]), ("added", [br.ADDED]), ("last", ["c.txt"])):
        for f in files:
            (src / f).parent.mkdir(parents=True, exist_ok=True)
            (src / f).write_text(name + "\n", encoding="utf-8", newline="\n")
        git("add", "-A", cwd=src)
        git("commit", "-q", "-m", name, cwd=src)
        shas[name] = git("rev-parse", "HEAD", cwd=src)
    git("clone", "-q", "--bare", str(src), str(remote), cwd=tmp_path)
    monkeypatch.setattr(br, "remote_url", lambda: ("origin", str(remote)))
    root = tmp_path / "dir"
    # --dry-run prints the plan and starts nothing
    assert bm.main(["repro", "setup", "--instances", "2", "--dir", str(root), "--dry-run"]) == 0
    plan = capsys.readouterr().out
    assert str(root / "origin2.git") in plan and not root.exists() and not (tmp_path / "scratch").exists()
    # the default REV is the parent of the first commit that added the file; the seed bare is gone afterwards
    assert bm.main(["repro", "setup", "--instances", "2", "--dir", str(root)]) == 0
    out = capsys.readouterr().out
    assert f"rev: {shas['second']}" in out and not (root / "seed.git").exists()
    clones = []
    for n in (1, 2):
        bare, clone = root / f"origin{n}.git", br.clone_path(root, n)
        clones.append(clone)
        assert str(bare) in out and str(clone) in out and str(br.mcp_path(root, n)) in out
        assert git("rev-parse", "main", cwd=bare) == shas["second"]  # only the pinned history: no later commit is there
        assert subprocess.run(["git", "cat-file", "-e", shas["last"]], cwd=str(bare), capture_output=True).returncode != 0
        assert git("remote", cwd=clone) == "origin" and git("remote", "get-url", "origin", cwd=clone) == str(bare)
        assert git("rev-parse", "HEAD", cwd=clone) == shas["second"] and not str(clone).startswith(str(conftest.KB))
        assert json.loads((clone / "_private" / "querylog.json").read_text(encoding="utf-8"))["mode"] == "off"
        cfg = json.loads(br.mcp_path(root, n).read_text(encoding="utf-8"))["mcpServers"]
        docs = json.loads((bc.HOME / br.DOCS_MCP).read_text(encoding="utf-8"))["mcpServers"]
        assert cfg["kb"]["args"] == [str(clone / "_tools" / "kb_mcp.py")] and {k: cfg[k] for k in docs} == docs and len(docs) == 3
        env = br.instance_env(root, n)
        assert not set(conftest.LEAKY) & {k for k, v in env.items() if v} and env["KB_SESSION"] == ""
        assert "KB_DOCS_CACHE" not in env and env["ENABLE_CLAUDEAI_MCP_SERVERS"] == "false"
        assert Path(env["KB_HOST_LOCK_DIR"]).parent == root and "KB_INDEX" not in env
    assert set(br.LEAKY_ENV) == set(conftest.LEAKY) and clones[0] != clones[1]
    # a second run converges, a --start inside the history moves every main, and one outside it is refused with exit 2
    assert bm.main(["repro", "setup", "--instances", "1", "--dir", str(root), "--start", shas["first"]]) == 0
    assert git("rev-parse", "main", cwd=root / "origin1.git") == shas["first"]
    assert bm.main(["repro", "setup", "--instances", "1", "--dir", str(root), "--start", "no-such-rev"]) == 2
    assert "no such commit" in capsys.readouterr().err
    assert bm.main(["repro", "setup", "--instances", "0", "--dir", str(root)]) == 2
    # repro check: a probe's sync --push lands on its own bare and never on the stand-in for the real origin (a bare copy
    # of this working tree's files, which has the tools the probe runs; the clone's own history lacks blobs); the probe is
    # gone afterwards
    real = tmp_path / "real.git"
    git("clone", "-q", "--bare", str(kb_seed[0]), str(real), cwd=tmp_path)
    tip = git("rev-parse", "main", cwd=real)
    monkeypatch.setattr(br, "remote_url", lambda: ("origin", str(real)))
    left = sorted((tmp_path / "scratch").iterdir())  # the clones of the setups above stay
    capsys.readouterr()
    assert bm.main(["repro", "check"]) == 0
    out = capsys.readouterr().out
    assert "the probe's push stayed on its own bare" in out and "FAIL" not in out, out
    assert git("rev-parse", "main", cwd=real) == tip and sorted((tmp_path / "scratch").iterdir()) == left
    assert br.CLAIMS_LEDGER == bl_base.CLAIMS_LEDGER
    # a planted failure: a commit that a fresh fetch of the real origin does have is named, the exit is 1, the probe still goes
    monkeypatch.setattr(br, "reaches", lambda sha, url, work: True)
    assert bm.main(["repro", "check"]) == 1
    out = capsys.readouterr().out
    assert "FAIL: the commit is not in a fresh fetch of the real origin's main" in out and "1 failed" in out, out
    assert sorted((tmp_path / "scratch").iterdir()) == left


def bench_repro_questions_and_status_name_each_planted_problem(tmp_path, monkeypatch, capsys):
    import shutil, subprocess
    import bench_repro as br
    import benchmarks as bm
    import bl_check
    for k, v in {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t",
                 "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}.items():
        monkeypatch.setenv(k, v)
    write = lambda path, header, rows: path.write_text(  # noqa: E731
        "\n".join(",".join(f'"{c}"' for c in r) for r in [header, *rows]) + "\n", encoding="utf-8", newline="\n")
    brief = lambda area, **cells: [area, *[cells.get(c, "present" if c == "coverage" else f"{c} of {area}") for c in br.BRIEF_COLUMNS[1:]]]  # noqa: E731
    # the briefs: load_briefs returns the six columns of each row; brief_problems names each planted defect
    bad, good = tmp_path / "bad_briefs.csv", tmp_path / "briefs.csv"
    write(bad, br.BRIEF_COLUMNS, [brief("alpha", scope=""), brief("beta", coverage="maybe"), brief("alpha"),
                                  brief("gamma", leave_out="")])
    rows = br.load_briefs(bad)
    assert [r["area"] for r in rows] == ["alpha", "beta", "alpha", "gamma"] and set(rows[0]) == set(br.BRIEF_COLUMNS)
    found = br.brief_problems(rows)
    assert len(found) == 3 and "row 1 (alpha): empty scope" in found[0] and "coverage 'maybe'" in found[1], found
    assert "row 3 (alpha): duplicate area, as row 1" in found[2] and br.load_briefs(tmp_path / "none.csv") == []
    write(good, br.BRIEF_COLUMNS, [brief("alpha", coverage="present"), brief("beta", coverage="partial"),
                                   brief("gamma", coverage="absent", leave_out="")])
    assert br.brief_problems(br.load_briefs(good)) == []
    # the frozen questions: an area short of rows, a duplicate id, a row with no expectation, a question a tool answers
    head = ["id", "area", "stratum", "question", "expect_paths", "expect_verdict", "allow_weak", "expect_text", "expect_re"]
    q = lambda qid, area, question="How do I restore a podman container from a checkpoint?", re_="podman": [  # noqa: E731
        qid, area, "present", question, "", "good", "", "", re_]
    asked = tmp_path / "asked.csv"
    write(asked, head, [q("A-1", "alpha"), q("A-2", "alpha"), q("A-3", "alpha"), q("B-1", "beta"), q("B-2", "beta"),
                        q("A-1", "gamma"), q("G-2", "gamma", re_=""), q("G-3", "gamma", "How many articles does the kb hold per domain?"),
                        q("Z-1", "zeta")])
    capsys.readouterr()
    assert bm.main(["repro", "questions", "--briefs", str(good), "--file", str(asked)]) == 1
    out = capsys.readouterr().out
    for want in ("area beta: 2 question rows, 3 to 5 wanted", "question A-1: duplicate id, as row 1",
                 "question G-2: none of expect_re, expect_text, expect_paths is filled", "question G-3: routed by kind to a tool (count)",
                 "area zeta: 1 question row(s) of no brief's area"):
        assert want in out, (want, out)
    assert "area alpha" not in out and "area gamma" not in out  # alpha and gamma hold 3 rows each
    write(asked, head, [q(f"{a}-{i}", a) for a in ("alpha", "beta", "gamma") for i in (1, 2, 3)])
    assert bm.main(["repro", "questions", "--briefs", str(good), "--file", str(asked)]) == 0
    assert "every one of 3 areas holds 3 to 5 questions" in capsys.readouterr().out
    assert bm.main(["repro", "questions", "--briefs", str(tmp_path / "none.csv"), "--file", str(asked)]) == 1
    assert "no brief rows" in capsys.readouterr().out
    # status: two instances of one start commit, one with two commits on its bare, one with none
    git = lambda *a, cwd: subprocess.run(["git", *a], cwd=str(cwd), capture_output=True, text=True, check=True).stdout.strip()  # noqa: E731
    src = tmp_path / "src"
    src.mkdir()
    git("init", "-q", "--initial-branch=main", cwd=src)
    shas = []
    for name in ("start", "one", "two"):
        (src / f"{name}.txt").write_text(name + "\n", encoding="utf-8", newline="\n")
        git("add", "-A", cwd=src)
        git("commit", "-q", "-m", f"commit {name}", cwd=src)
        shas.append(git("rev-parse", "HEAD", cwd=src))
    root, real = tmp_path / "dir", tmp_path / "real.git"
    root.mkdir()
    for name in ("origin1.git", "origin2.git", "real.git"):
        git("init", "-q", "--bare", "--initial-branch=main", str(tmp_path / name if name == "real.git" else root / name), cwd=tmp_path)
    git("push", "-q", str(root / "origin1.git"), "main:refs/heads/main", cwd=src)
    git("push", "-q", str(root / "origin2.git"), f"{shas[0]}:refs/heads/main", cwd=src)
    git("push", "-q", str(real), f"{shas[0]}:refs/heads/main", cwd=src)
    monkeypatch.setattr(br, "remote_url", lambda: ("origin", str(real)))
    assert bm.main(["repro", "status", "--dir", str(root / "no-manifest")]) == 0 and "holds no instances.json" in capsys.readouterr().out
    (root / br.MANIFEST).write_text(json.dumps({"rev": shas[0], "source": str(real), "instances": [
        {"n": n, "bare": str(root / f"origin{n}.git")} for n in (1, 2)]}), encoding="utf-8", newline="\n")
    assert bm.main(["repro", "status", "--dir", str(root)]) == 0  # the origin holds the start commit only
    out = capsys.readouterr().out
    assert "instance 1: 2 commit(s)" in out and "instance 2: 0 commit(s)" in out and f"{shas[2][:12]} commit two (not in" in out
    assert "no instance commit is in a fresh fetch" in out
    assert not [rx.pattern for rx in bl_check.NOOP_MARKERS if rx.search(out)] and bl_check.noop_output(out) is None, out
    # a planted failure: the first instance commit is in the origin's main, the second is not: exit 1 naming it
    git("push", "-q", str(real), f"{shas[1]}:refs/heads/main", cwd=src)
    assert bm.main(["repro", "status", "--dir", str(root)]) == 1
    out = capsys.readouterr().out
    assert f"{shas[1][:12]} commit one (IN the real origin main)" in out and f"{shas[2][:12]} commit two (not in" in out
    assert "1 instance commit(s) are in a fresh fetch" in out and not list(root.glob("tmp*"))
    shutil.rmtree(root / "origin2.git")
    assert bm.main(["repro", "status", "--dir", str(root)]) == 2
    assert "instance 2: its bare" in capsys.readouterr().err


def bench_stream_run_passes_timeout_and_clean_env_and_an_error_result_keeps_its_cost_usage_and_subtype(tmp_path, monkeypatch):
    import sys
    import agent_bench
    # a session that outlives its timeout is a failure named timeout, not an exception
    r = agent_bench.execute([sys.executable, "-c", "import time; time.sleep(30)"], "", cwd=str(tmp_path), timeout=0.5)
    assert r["error"] == "timeout" and r["timeout_s"] == 0.5 and r["wall_s"] < 10
    # an error result keeps what the run spent: cost, usage tokens, model usage and subtype
    line = json.dumps({"type": "result", "subtype": "error_max_budget_usd", "is_error": True, "total_cost_usd": 8.01,
                       "num_turns": 40, "duration_api_ms": 1000, "usage": {"input_tokens": 5, "output_tokens": 7},
                       "modelUsage": {"claude-sonnet-5-5": {"costUSD": 8.01, "outputTokens": 9}}, "result": ""})
    r = agent_bench.execute([sys.executable, "-c", f"print({line!r})"], "", cwd=str(tmp_path), timeout=30)
    assert r["error"] == "error_max_budget_usd" and r["subtype"] == "error_max_budget_usd" and r["cost"] == 8.01
    assert r["turns"] == 40 and r["in_uncached"] == 5 and r["out"] == 9
    assert r["model_usage"]["claude-sonnet-5-5"]["out"] == 9
    turns = agent_bench.result_of(line.replace("budget_usd", "turns"), "", 3.0)
    assert turns["subtype"] == "error_max_turns" and turns["cost"] == 8.01
    # the error run's cost counts in the spend, and a refused run with no cost does not
    monkeypatch.setattr(bc, "SPEND", {"usd": 0.0, "input": 0, "out": 0, "runs": 0})
    before = bc.spent_usd()
    bc.spent_run(r)
    assert round(bc.spent_usd() - before, 2) == 8.01
    bc.spent_run({"error": "timeout", "timeout_s": 1})
    assert round(bc.spent_usd() - before, 2) == 8.01
    # stream_run hands its timeout and clean env on to execute
    got = {}
    monkeypatch.setattr(agent_bench, "execute", lambda cmd, prompt, **kw: got.update(kw) or {"error": "timeout"})
    bc.stream_run(["claude"], "q", tmp_path, {"HOME": "/h"}, timeout=7, clean=True)
    assert got["timeout"] == 7 and got["clean"] is True and got["env"] == {"HOME": "/h"}
    bc.stream_run(["claude"], "q", tmp_path)
    assert got["timeout"] == 900 and got["clean"] is False and got["env"] is None


FAKE_CLAUDE = """import json, os, subprocess, sys, time
args, prompt, cwd = sys.argv[1:], sys.stdin.read(), os.getcwd()
area, n, work = prompt.split()[1].rstrip(":"), ("1" if "clone1" in cwd else "2"), os.environ["FAKE_DIR"]
other = work + "/started-" + ("2" if n == "1" else "1")
open(work + "/started-" + n, "w").close()
saw = False
for _ in range(100):  # the other instance's session must be running too: they start at the same time
    saw = saw or os.path.exists(other)
    if saw:
        break
    time.sleep(0.1)
stale = os.path.exists("left-by-session.txt")
open("left-by-session.txt", "w").write("x")
open(area + ".md", "w").write(area + n + str(time.time_ns()))
git = lambda *a: subprocess.run(["git", *a], check=True, capture_output=True)
git("add", area + ".md")
git("commit", "-q", "-m", "docs: " + area)
git("push", "-q", "origin", "main")
turns = n == "2" and area == "alpha" and not os.path.exists(work + "/turns-done")
if turns:
    open(work + "/turns-done", "w").close()
with open(work + "/calls.jsonl", "a") as f:
    f.write(json.dumps({"n": n, "area": area, "args": args, "prompt": prompt, "cwd": cwd, "saw_other": saw, "stale": stale,
                        "session": os.environ.get("KB_SESSION")}) + "\\n")
print(json.dumps({"type": "assistant", "message": {"id": "m1", "model": "claude-sonnet-5-5", "usage": {"input_tokens": 1},
                  "content": [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {}}]}}))
print(json.dumps({"type": "result", "subtype": "error_max_turns" if turns else "success", "is_error": turns,
                  "total_cost_usd": 3.0, "num_turns": 7, "duration_api_ms": 1000, "result": "done",
                  "usage": {"input_tokens": 11, "cache_creation_input_tokens": 22, "cache_read_input_tokens": 33,
                            "output_tokens": 44},
                  "modelUsage": {"claude-sonnet-5-5": {"costUSD": 3.0, "inputTokens": 11, "outputTokens": 44}}}))
"""


def bench_repro_run_starts_instances_together_stops_at_the_instance_budget_and_a_run_again_resumes(tmp_path, monkeypatch):
    import subprocess, sys
    import bench_repro as br
    import benchmarks as bm
    for k, v in {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t",
                 "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
                 "KB_SESSION": "other-session", "FAKE_DIR": str(tmp_path)}.items():
        monkeypatch.setenv(k, v)
    import kbfacts
    monkeypatch.setattr(kbfacts, "routed", lambda question: None)  # the routing check has its own body
    monkeypatch.setattr(bc, "SPEND", {"usd": 0.0, "input": 0, "out": 0, "runs": 0})  # the planted runs are no spend of this process
    fake = tmp_path / "fake_claude.py"
    fake.write_text(FAKE_CLAUDE, encoding="utf-8", newline="\n")
    monkeypatch.setattr(br, "CLAUDE", [sys.executable, str(fake)])
    git = lambda *a, cwd: subprocess.run(["git", *a], cwd=str(cwd), capture_output=True, text=True, check=True).stdout.strip()  # noqa: E731
    write = lambda path, header, rows: path.write_text(  # noqa: E731
        "\n".join(",".join(f'"{c}"' for c in r) for r in [header, *rows]) + "\n", encoding="utf-8", newline="\n")
    src, root = tmp_path / "src", tmp_path / "dir"
    src.mkdir()
    root.mkdir()
    git("init", "-q", "--initial-branch=main", cwd=src)
    (src / ".gitignore").write_text("_private/\n", encoding="utf-8", newline="\n")  # as the repository's: git clean keeps it
    shas = []
    for name, path in (("start", "start.txt"), ("added", br.ADDED)):
        (src / path).parent.mkdir(parents=True, exist_ok=True)
        (src / path).write_text(name + "\n", encoding="utf-8", newline="\n")
        git("add", "-A", cwd=src)
        git("commit", "-q", "-m", name, cwd=src)
        shas.append(git("rev-parse", "HEAD", cwd=src))
    insts = []
    for n in (1, 2, 3):  # origin3 holds the commit that adds repro_bench.csv
        bare, clone = root / f"origin{n}.git", tmp_path / f"clone{n}"
        git("init", "-q", "--bare", "--initial-branch=main", str(bare), cwd=tmp_path)
        git("push", "-q", str(bare), f"{shas[1] if n == 3 else shas[0]}:refs/heads/main", cwd=src)
        git("clone", "-q", str(bare), str(clone), cwd=tmp_path)
        bc.isolate(clone, "off", bare)
        mcp = clone / "_private" / "mcp-config.json"
        mcp.write_text("{}\n", encoding="utf-8", newline="\n")
        insts.append({"n": n, "bare": str(bare), "clone": str(clone), "mcp_config": str(mcp), "lock_dir": str(root / f"lock{n}")})
    manifest = lambda rev, rows: (root / br.MANIFEST).write_text(  # noqa: E731
        json.dumps({"rev": rev, "source": "x", "instances": rows}), encoding="utf-8", newline="\n")
    manifest(shas[0], insts[:2])
    brief = lambda area, scope="scope": [area, scope, "sources", "depth", "absent", ""]  # noqa: E731
    briefs, asked = tmp_path / "briefs.csv", tmp_path / "asked.csv"
    write(briefs, br.BRIEF_COLUMNS, [brief("alpha"), brief("beta")])
    head = ["id", "area", "stratum", "question", "expect_paths", "expect_verdict", "allow_weak", "expect_text", "expect_re"]
    ask = lambda areas: write(asked, head, [[f"{a}-{i}", a, "absent", "How do I restore a podman container from a checkpoint?",  # noqa: E731
                                             "", "good", "", "", "podman"] for a in areas for i in (1, 2, 3)])
    ask(["alpha", "beta"])
    lines = []
    go = lambda **kw: br.run(None, root, briefs_path=briefs, questions_path=asked, out=lines.append, **kw)  # noqa: E731
    results = lambda: br.read_results(root / br.RESULTS)  # noqa: E731
    calls = lambda: [json.loads(ln) for ln in (tmp_path / "calls.jsonl").read_text(encoding="utf-8").splitlines()]  # noqa: E731
    # the refusals: questions that fail, a start commit that holds repro_bench.csv, other limits than the run's recorded ones
    ask(["alpha"])
    with pytest.raises(br.Refused, match="repro questions fails"):
        go()
    ask(["alpha", "beta"])
    manifest(shas[1], [{**insts[2], "n": 1}])
    with pytest.raises(br.Refused, match="holds kb/public/_retrieval/repro_bench.csv"):
        go()
    assert go(dry_run=True) == 0 and any("the start commit" in ln for ln in lines) and not results()
    manifest(shas[0], insts[:2])
    # a dry run starts nothing, prints each instance's argv and the estimate, and exits 1 only for a briefs problem
    lines.clear()
    assert go(dry_run=True, instance_usd=2.5) == 0 and not (tmp_path / "calls.jsonl").exists() and not (root / br.RUN_RECORD).exists()
    shown = "\n".join(lines)
    assert shown.count("  argv: ") == 2 and "--strict-mcp-config" in shown and "estimate up to $10.50" in shown, shown
    assert "gitkraken@synced" in shown and "caveman@caveman" in shown
    assert br.run(None, root, dry_run=True, briefs_path=tmp_path / "none.csv", questions_path=asked, out=lines.append) == 0
    assert any("no brief rows" in ln for ln in lines)
    write(briefs, br.BRIEF_COLUMNS, [brief("alpha", scope=""), brief("beta")])
    assert go(dry_run=True) == 1 and any("briefs problem: row 1 (alpha): empty scope" in ln for ln in lines)
    write(briefs, br.BRIEF_COLUMNS, [brief("alpha"), brief("beta")])
    assert bm.main(["repro", "run", "--dry-run", "--instances", "0", "--dir", str(root)]) == 2
    # the first run: two instances at once; instance 1's alpha spends $3.0, past --instance-usd 2.5, so its beta is a
    # failure named budget; instance 2's alpha ends at its turn limit
    assert go(instance_usd=2.5) == 1
    got = {(r["instance"], r["area"]): r for r in results()}
    assert sorted(got) == [(1, "alpha"), (1, "beta"), (2, "alpha"), (2, "beta")]
    assert [got[k]["failure"] for k in sorted(got)] == ["", "budget", "turns", "budget"]
    ok = got[(1, "alpha")]
    assert ok["cost"] == 3.0 and ok["turns"] == 7 and ok["tool_calls"] == 1 and ok["subtype"] == "success"
    assert (ok["input_tokens"], ok["cache_write_tokens"], ok["cache_read_tokens"], ok["output_tokens"]) == (11, 22, 33, 44)
    assert ok["model_usage"]["claude-sonnet-5-5"]["out"] == 44 and ok["wall_s"] >= 0 and ok["effort"] == "high"
    assert ok["bare_before"] == shas[0] and ok["bare_after"] == git("rev-parse", "main", cwd=root / "origin1.git") != shas[0]
    assert got[(2, "alpha")]["subtype"] == "error_max_turns" and got[(2, "alpha")]["cost"] == 3.0
    assert got[(1, "beta")]["cost"] == 0 and "instance-usd" in got[(1, "beta")]["error"]
    first = calls()
    assert [c["area"] for c in first] == ["alpha", "alpha"] and all(c["saw_other"] and c["session"] == "" for c in first)
    assert first[0]["prompt"] == first[1]["prompt"] and first[0]["prompt"] == br.area_prompt(br.load_briefs(briefs)[0])
    assert sorted(Path(c["cwd"]).resolve() for c in first) == [Path(i["clone"]).resolve() for i in insts[:2]]
    same = [[a for a in c["args"] if "mcp-config.json" not in a] for c in first]
    assert same[0] == same[1] and "--mcp-config" in first[0]["args"] and "--strict-mcp-config" in first[0]["args"]
    a = first[0]["args"]
    assert a[a.index("--settings") + 1] == '{"enabledPlugins":{"gitkraken@synced":false,"caveman@caveman":false}}'
    assert a[a.index("--permission-mode") + 1] == "bypassPermissions" and a[a.index("--max-budget-usd") + 1] == "8"
    assert a[a.index("--output-format") + 1] == "stream-json" and a[a.index("--max-turns") + 1] == "150"
    prompt = first[0]["prompt"]
    for want in ("/kb-research", "kbgit.py sync --push", "lookup_eval.csv", "lookup_heldout.csv", "doc2query",
                 "kb/_self/backlog/", "kb/_self/reports/", "outside this clone"):
        assert want in prompt, want
    record = json.loads((root / br.RUN_RECORD).read_text(encoding="utf-8"))
    assert "gitkraken@synced" in record["settings"] and "caveman@caveman" in record["settings"] and record["timeout"] == 3600
    # limits other than the recorded ones would mix two runs in one results file
    with pytest.raises(br.Refused, match="other settings or limits"):
        go(max_turns=99)
    # the run again: finished areas are skipped, the failed ones retried from the bare's main with what a session left removed
    assert go(instance_usd=10) == 0
    final = {(r["instance"], r["area"]): r for r in results()[4:]}
    assert sorted(final) == [(1, "beta"), (2, "alpha"), (2, "beta")] and all(r["failure"] == "" for r in final.values())
    assert final[(1, "beta")]["bare_before"] == ok["bare_after"] and len(calls()) == 5
    assert not any(c["stale"] for c in calls()), "a file a session left was still there"
    assert {k: v["failure"] for k, v in br.latest(results()).items()} == {(i, a): "" for i in (1, 2) for a in ("alpha", "beta")}
    # a third run has nothing left to start
    before = len(results())
    assert go(instance_usd=10) == 0 and len(results()) == before and len(calls()) == 5


def bench_repro_record_merges_planted_lines_as_rows_and_a_second_record_changes_nothing(tmp_path, capsys):
    import hashlib
    import bench_repro as br
    import benchmarks as bm
    root, out = tmp_path / "dir", tmp_path / "benchmarks.csv"
    root.mkdir()
    rev = "0123456789abcdef0123456789abcdef01234567"
    (root / br.MANIFEST).write_text(json.dumps({"rev": rev, "instances": []}), encoding="utf-8", newline="\n")
    briefs, asked = tmp_path / "briefs.csv", tmp_path / "asked.csv"
    briefs.write_text("area,scope\nalpha,s\n", encoding="utf-8", newline="\n")
    asked.write_text("id,area\na-1,alpha\n", encoding="utf-8", newline="\n")
    args = ["repro", "record", "--dir", str(root), "--file", str(out), "--briefs", str(briefs), "--questions", str(asked)]
    # no lines: exit 0, nothing written, even with no manifest
    assert bm.main(["repro", "record", "--dir", str(tmp_path / "none"), "--file", str(out), "--dry-run"]) == 0
    assert "nothing to record" in capsys.readouterr().out and not out.exists()
    line = {"instance": 1, "area": "alpha", "started": "2026-10-15T08:00:00Z", "model": "claude-sonnet-5-5", "failure": "",
            "cost": 3.0, "input_tokens": 11, "output_tokens": 44, "cache_write_tokens": 22, "cache_read_tokens": 33,
            "turns": 7, "tool_calls": 5, "wall_s": 12.5, "model_usage": {"claude-sonnet-5-5": {}, "claude-haiku-5-5": {}},
            "bare_before": "a" * 40, "bare_after": "b" * 40}
    planted = [{**line, "failure": "turns", "cost": 8.0}, {**line, "area": "beta", "failure": "budget", "cost": 0},
               {**line, "instance": 2, "started": "2026-10-15T08:00:01Z"}, line]  # the newest line of (1, alpha) counts
    (root / br.RESULTS).write_text("not json\n" + "".join(json.dumps(r) + "\n" for r in planted), encoding="utf-8", newline="\n")
    other = {"scenario": "pool", "record": "2026-10-14", "case": "c", "arm": "a", "metric": "m", "value": "1"}
    bc.write_rows([other], out)
    # --dry-run prints the rows it would merge and writes nothing
    before = out.read_bytes()
    assert bm.main([*args, "--dry-run"]) == 0 and out.read_bytes() == before
    shown = capsys.readouterr().out
    assert "repro 0123456 2026-10-15 alpha instance-1 cost=3.0" in shown
    assert len([ln for ln in shown.splitlines() if ln.startswith("repro 0123456 ")]) == 36
    assert bm.main(args) == 0
    capsys.readouterr()
    rows = [r for r in bc.read_rows(out) if r["scenario"] == "repro"]
    assert len(rows) == 36 and bc.read_rows(out)[0] == {k: other.get(k, "") for k in bc.FIELDS}
    got = {(r["arm"], r["case"], r["metric"]): r["value"] for r in rows}
    assert {(a, c) for a, c, _ in got} == {("instance-1", "alpha"), ("instance-1", "beta"), ("instance-2", "alpha")}
    mine = {m: got[("instance-1", "alpha", m)] for m in
            ("cost", "input", "out", "cache_read", "cache_write", "turns", "tool_calls", "wall_s", "models", "failure",
             "main_before", "main_after")}
    assert mine == {"cost": "3.0", "input": "11", "out": "44", "cache_read": "33", "cache_write": "22", "turns": "7",
                    "tool_calls": "5", "wall_s": "12.5", "models": "claude-haiku-5-5,claude-sonnet-5-5", "failure": "none",
                    "main_before": "aaaaaaa", "main_after": "bbbbbbb"}
    assert got[("instance-1", "beta", "failure")] == "budget"
    sums = [hashlib.sha256(p.read_bytes()).hexdigest() for p in (briefs, asked)]
    assert {r["record"] for r in rows} == {"0123456"} and {r["date"] for r in rows} == {"2026-10-15"}
    assert {r["note"] for r in rows} == {f"start {rev}; briefs sha256 {sums[0]}; questions sha256 {sums[1]}"}
    # a second record of the same lines changes nothing, not the file's bytes either
    first = out.read_bytes()
    assert bm.main(args) == 0 and out.read_bytes() == first and "nothing changes" in capsys.readouterr().out
    # a changed line replaces the record's rows, the other scenario's row stays
    (root / br.RESULTS).write_text(json.dumps({**line, "cost": 1.5}) + "\n", encoding="utf-8", newline="\n")
    assert bm.main(args) == 0
    rows = bc.read_rows(out)
    assert [r["scenario"] for r in rows] == ["pool"] + ["repro"] * 12 and rows[1]["value"] == "1.5"
    # a manifest-less directory with lines, and a missing briefs file, are refusals
    (root / br.MANIFEST).unlink()
    assert bm.main(args) == 2
    (root / br.MANIFEST).write_text(json.dumps({"rev": rev}), encoding="utf-8", newline="\n")
    assert bm.main(["repro", "record", "--dir", str(root), "--file", str(out), "--briefs", str(tmp_path / "none.csv"),
                    "--questions", str(asked)]) == 2


FAKE_RAG = """import csv, json, os, re, subprocess, sys
from pathlib import Path
home, args = Path(__file__).resolve().parent.parent, sys.argv[1:]
if args[1] == "audit":  # one call of each state: the checkout must be detached
    head = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True).stdout.strip()
    with open(os.environ["FAKE_LOG"], "a") as f:
        f.write(json.dumps({"argv": args, "cwd": os.getcwd(), "head": head}) + "\\n")
kinds = ("DOC", "CODE", "DER", "COMMUNITY", "UNK")


def facts(root):
    out = []
    for a in sorted((home / "kb" / root).glob("*.md")):
        for n, ln in enumerate(a.read_text(encoding="utf-8").splitlines(), 1):
            if ln.startswith("- "):
                out.append({"path": root + "/" + a.name, "line": n, "section": "Facts", "text": ln[2:],
                            "tags": [{"kind": k, "ids": v.split(), "note": ""} for k, v in re.findall(r"\\[([A-Z]+) ([^\\]]+)\\]", ln)]})
    return out


assert args[0] == "--json"
if args[1] == "facts":
    print(json.dumps(facts(args[2])))
elif args[1] == "audit":
    rows = {}
    for f in facts("public"):
        r = rows.setdefault(f["path"], {"path": f["path"], "facts": 0, **{k: 0 for k in kinds}})
        r["facts"] += 1
        for t in f["tags"]:
            r[t["kind"]] += 1
    print(json.dumps(list(rows.values())))
else:
    res = []
    for q in csv.DictReader(open(args[3], encoding="utf-8", newline="")):
        hit = any(re.search(q["expect_re"], f["text"]) for f in facts("public"))
        verdict = "good" if hit else "none"
        if q["stratum"] == "flaky":  # good without the answer while the checkout holds the base fact only, weak after
            verdict = "good" if len(facts("public")) == 1 else "weak"
        res.append({"id": q["id"], "verdict": verdict, "failed": [] if hit else ["regex"]})
    print(json.dumps({"n": len(res), "rows": res}))
"""
FAKE_CHECK = """import sys
from pathlib import Path
home = Path(__file__).resolve().parent.parent
lines = [ln for f in (home / "kb").rglob("*.md") for ln in f.read_text(encoding="utf-8").splitlines()]
print("sources=1 citations=1 errors=%d" % sum("BROKEN" in ln for ln in lines))
"""
FAKE_LINT = """import json, sys
from pathlib import Path
home = Path(__file__).resolve().parents[3]
assert sys.argv[1:3] == ["--json", "--base"] and len(sys.argv) == 4
lines = [ln for f in (home / "kb").rglob("*.md") for ln in f.read_text(encoding="utf-8").splitlines()]
out = [{"level": "ERROR", "path": "x", "message": ln} for ln in lines if "LINT" in ln]
print(json.dumps(out))
sys.exit(1 if out else 0)
"""


def bench_repro_compare_measures_two_planted_instances_shared_paraphrased_and_conflicting_facts(tmp_path, monkeypatch, capsys):
    import shutil, subprocess
    import bench_repro as br
    import benchmarks as bm
    for k, v in {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t",
                 "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
                 "BENCH_SCRATCH": str(tmp_path / "scratch"), "FAKE_LOG": str(tmp_path / "calls.jsonl")}.items():
        monkeypatch.setenv(k, v)
    git = lambda *a, cwd: subprocess.run(["git", *a], cwd=str(cwd), capture_output=True, text=True, check=True).stdout.strip()  # noqa: E731
    sources = "id,url,title\n"

    def plant(bare, commits):
        """A bare repository whose main holds `commits` ([(message, {path: text})]) one after the other, made by one
        git fast-import with fixed dates so that two bares share their first commit; the shas of the commits."""
        git("init", "-q", "--bare", "--initial-branch=main", str(bare), cwd=tmp_path)
        stream = ""
        for k, (msg, files) in enumerate(commits):
            stream += f"commit refs/heads/main\ncommitter t <t@example.com> {1760000000 + k} +0000\ndata {len(msg)}\n{msg}\n"
            stream += "".join(f"M 100644 inline {n}\ndata {len(x.encode())}\n{x}\n" for n, x in files.items()) + "\n"
        subprocess.run(["git", "fast-import", "--quiet"], cwd=str(bare), input=stream.encode(), check=True)
        return git("rev-list", "--reverse", "main", cwd=bare).split()

    first = {"_tools/rag.py": FAKE_RAG, "_tools/check.py": FAKE_CHECK, ".claude/skills/kb-verify/lint.py": FAKE_LINT,
             "kb/public/_sources.csv": sources + "S-1,https://example.com/base,base\n",
             "kb/public/a.md": "# A\n\n- The base fact. [DOC S-1]\n"}
    cites = lambda *rows: sources + "S-1,https://example.com/base,base\n" + "".join(  # noqa: E731
        f"{i},{u},t\n" for i, u in rows)
    fact_a = "- The default retry count is 3 attempts. [DOC S-2]\n"
    import hashlib  # instance 1 anchors that fact only: its other DOC facts have no row, instance 2 has no _anchors.csv
    key = hashlib.sha256(" ".join(fact_a[2:].split()).encode()).hexdigest()[:12]
    anchors = "fact,path,source_id,status,heading,terms,sha,quote,verified_utc\n" + f"{key},a.md,S-2,unlocated:no-match,,,,,2026-10-15\n"
    plans = {1: [("alpha", {"kb/public/a.md": "# A\n\n- The base fact. [DOC S-1]\n" + fact_a +
                           "- The service restarts automatically after a failure. [DOC S-3]\n",
                           "kb/public/_anchors.csv": anchors,
                           "kb/public/_sources.csv": cites(("S-2", "https://example.com/retry?utm=1"),
                                                           ("S-3", "https://example.com/restart"))}),
                 ("beta", {"kb/public/a.md": "# A\n\n- The base fact. [DOC S-1]\n" + fact_a +
                           "- The service restarts automatically after a failure. [DOC S-3]\n"
                           "- The request timeout is 30 seconds. [DOC S-4]\nBROKEN marker\n",
                           "kb/public/b.md": "# B\n\n- A fact only this instance wrote. [DER S-7]\n",
                           "kb/public/_sources.csv": cites(("S-2", "https://example.com/retry?utm=1"),
                                                           ("S-3", "https://example.com/restart"),
                                                           ("S-4", "https://example.com/timeout"),
                                                           ("S-7", "https://example.com/unique"))})],
             2: [("alpha", {"kb/public/a.md": "# A\n\n- The base fact. [DOC S-1]\n" + fact_a +
                            "- The service restarts automatically after the failure. [DOC S-3]\n"
                            "- Logs are rotated daily. [UNK S-8]\n",
                            "kb/public/_sources.csv": cites(("S-6", "https://example.com/retry"),
                                                            ("S-8", "https://example.com/rotation"))}),
                 ("beta", {"kb/public/a.md": "# A\n\n- The base fact. [DOC S-1]\n" + fact_a +
                           "- The service restarts automatically after the failure. [DOC S-3]\n"
                           "- Logs are rotated daily. [UNK S-8]\n- The request timeout is 60 seconds. [DOC S-5]\n"
                           "LINT marker\n",
                           "kb/public/_sources.csv": cites(("S-6", "https://example.com/retry"),
                                                           ("S-8", "https://example.com/rotation"),
                                                           ("S-5", "https://learn.microsoft.com/timeouts"))})]}
    root, lines = tmp_path / "dir", []
    root.mkdir()
    insts = []
    for n, steps in plans.items():
        start, *shas = plant(root / f"origin{n}.git", [("start", first), *[(a, files) for a, files in steps]])
        insts.append({"n": n, "bare": str(root / f"origin{n}.git")})
        lines += [{"instance": n, "area": a, "started": "2026-10-15T08:00:00Z",
                   "failure": "turns" if (n, a) == (2, "beta") else "",
                   "bare_before": ([start] + shas)[i], "bare_after": shas[i]} for i, (a, _) in enumerate(steps)]
    (root / br.MANIFEST).write_text(json.dumps({"rev": start, "instances": insts}), encoding="utf-8", newline="\n")
    (root / br.RESULTS).write_text("".join(json.dumps(r) + "\n" for r in lines), encoding="utf-8", newline="\n")
    asked, out = tmp_path / "asked.csv", tmp_path / "benchmarks.csv"
    rows = [("A-1", "alpha", "retry count is 3"), ("A-2", "alpha", "restarts automatically after"),
            ("A-3", "alpha", "rotated daily"), ("B-1", "beta", "timeout is"), ("B-2", "beta", "only this instance"),
            ("B-3", "beta", "base fact"), ("A-4", "alpha", "retry count is 3"), ("A-5", "alpha", "no such text"),
            ("G-1", "gamma", "rotated daily"), ("G-2", "gamma", "base fact"), ("G-3", "gamma", "no such text")]
    # A-5 and G-3 are good at the start without the answer and weak after any research; the column's expect_verdict is
    # `none` for A-4 and A-5 and `good` for the rest, B-2 and A-3 among them, which the start commit measures as none
    asked.write_text("id,question,area,stratum,expect_re,expect_text,expect_paths,expect_verdict,allow_weak\n" + "".join(
        f"{i},q,{a},{'flaky' if i in ('A-5', 'G-3') else 'absent'},{r},,,{'none' if i in ('A-4', 'A-5') else 'good'},\n"
        for i, a, r in rows), encoding="utf-8", newline="\n")
    args = ["repro", "compare", "--dir", str(root), "--questions", str(asked)]
    # --dry-run lists the metrics and the instances it reads, and starts no tool
    assert bm.main([*args, "--dry-run"]) == 0
    shown = capsys.readouterr().out
    assert "metrics: articles_added, facts_added, doc, code, der, community, unk, sources_added, url_jaccard" in shown
    assert "instance 1: reads bare" in shown and "instance 2: reads bare" in shown and not (tmp_path / "calls.jsonl").exists()
    # the comparison, with --record: by the shas of each area, in a detached checkout of each instance's own
    other = {"scenario": "repro", "record": start[:7], "case": "c", "arm": "instance-1", "metric": "cost", "value": "1"}
    bc.write_rows([other], out)
    assert bm.main([*args, "--record", "--file", str(out)]) == 0
    shown = capsys.readouterr().out
    for want in ("instance 1 area alpha: 0 article(s), 2 fact(s) added (DOC 2, CODE 0, DER 0, COMMUNITY 0, UNK 0), 2 source(s)",
                 "instance 2 area alpha: 0 article(s), 3 fact(s) added (DOC 2, CODE 0, DER 0, COMMUNITY 0, UNK 1), 2 source(s)",
                 "instance 1 area beta: 1 article(s), 2 fact(s) added (DOC 1, CODE 0, DER 1, COMMUNITY 0, UNK 0)",
                 "instance 2 area beta: 0 article(s), 1 fact(s) added (DOC 1, CODE 0, DER 0, COMMUNITY 0, UNK 0)",
                 "pair 1+2 area alpha: url_jaccard 0.33, fact_overlap 0.67, 0 conflict(s)",
                 "pair 1+2 area beta: url_jaccard 0.00, fact_overlap 0.50, 1 conflict(s)",
                 "instance 1 public/a.md:", "The request timeout is 30 seconds.", "instance 2 public/a.md:",
                 "The request timeout is 60 seconds.", "instance 1: check.py errors 1, lint errors 0",
                 "instance 2: check.py errors 0, lint errors 1", "area alpha: agreement 0.80 of 5 frozen row(s)",
                 "instance 1 area alpha: answer found 0 at start, 3 at end; false good 1 at start, 0 at end",
                 "instance 2 area alpha: answer found 0 at start, 4 at end; false good 1 at start, 0 at end",
                 "instance 1 area beta: answer found 1 at start, 3 at end; false good 0 at start, 0 at end",
                 "instance 2 area beta: answer found 1 at start, 2 at end; false good 0 at start, 0 at end",
                 # an anchor row (whatever its status) anchors a fact; a DOC fact of Learn pages only needs none
                 "instance 1 area alpha: 1 DOC fact(s) added with no anchor row",
                 "instance 1 area beta: 1 DOC fact(s) added with no anchor row",
                 "instance 2 area alpha: 2 DOC fact(s) added with no anchor row",
                 "instance 2 area beta: 0 DOC fact(s) added with no anchor row",
                 "instance 1 area gamma (not researched): 1 of 3 frozen row(s) changed verdict",
                 "instance 2 area gamma (not researched): 2 of 3 frozen row(s) changed verdict"):
        assert want in shown, (want, shown)
    assert "area beta: agreement" not in shown  # instance 2's beta did not finish
    calls = [json.loads(ln) for ln in (tmp_path / "calls.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {c["head"] for c in calls} == {"HEAD"} and {Path(c["cwd"]).name for c in calls} == {"compare1", "compare2"}
    assert not [p for p in (tmp_path / "scratch").rglob("compare*") if p.is_dir()]
    # --record merged the numbers as the scenario repro-compare beside the other scenario's row, and a second record
    # changes nothing
    rows = bc.read_rows(out)
    got = {(r["arm"], r["case"], r["metric"]): r["value"] for r in rows if r["scenario"] == "repro-compare"}
    assert rows[0]["scenario"] == "repro" and {r["record"] for r in rows if r["scenario"] == "repro-compare"} == {start[:7]}
    want = {("instance-1", "alpha", "facts_added"): "2", ("instance-2", "alpha", "facts_added"): "3",
            ("instance-2", "alpha", "unk"): "1", ("instance-1", "beta", "articles_added"): "1",
            ("instance-1", "beta", "der"): "1", ("instance-1", "alpha", "sources_added"): "2",
            ("instance-1+instance-2", "alpha", "url_jaccard"): "0.333333",
            ("instance-1+instance-2", "alpha", "fact_overlap"): "0.666667",
            ("instance-1+instance-2", "beta", "fact_overlap"): "0.5", ("instance-1+instance-2", "beta", "conflicts"): "1",
            ("instance-1", "all", "check_errors"): "1", ("instance-2", "all", "lint_errors"): "1",
            ("instance-1", "alpha", "unanchored"): "1", ("instance-1", "beta", "unanchored"): "1",
            ("instance-2", "alpha", "unanchored"): "2", ("instance-2", "beta", "unanchored"): "0",
            # a row is compared with its verdict at the start commit: A-3 (instance 1) and B-2 (instance 2) expect `good`
            # in the column and were `none` at the start, so they pass; A-5 was good at the start and is weak now
            ("instance-1", "alpha", "eval_passed"): "4", ("instance-1", "alpha", "eval_total"): "5",
            ("instance-2", "alpha", "eval_passed"): "4", ("instance-2", "beta", "eval_passed"): "3",
            ("instance-1", "alpha", "found_start"): "0", ("instance-1", "alpha", "found_end"): "3",
            ("instance-2", "alpha", "found_end"): "4", ("instance-1", "beta", "found_start"): "1",
            ("instance-1", "beta", "found_end"): "3", ("instance-2", "beta", "found_end"): "2",
            ("instance-1", "alpha", "false_good_start"): "1", ("instance-1", "alpha", "false_good_end"): "0",
            ("instance-2", "beta", "false_good_start"): "0", ("instance-2", "beta", "false_good_end"): "0",
            ("instance-1", "gamma", "churn"): "1", ("instance-2", "gamma", "churn"): "2",
            ("all", "alpha", "agreement"): "0.8"}
    for k, v in want.items():
        assert got.get(k) == v, (k, v, got.get(k))
    assert not [k for k in got if k[2] == "agreement" and k[1] == "beta"] and len(got) == 73
    assert not [k for k in got if k[2] == "churn" and k[1] != "gamma"] and not [k for k in got if k[1] == "gamma" and k[2] != "churn"]
    first = out.read_bytes()
    assert bm.main([*args, "--record", "--file", str(out)]) == 0 and out.read_bytes() == first
    assert "nothing changes" in capsys.readouterr().out
    # a questions file that is not there is a refusal; a bare that is gone too
    assert bm.main(["repro", "compare", "--dir", str(root), "--questions", str(tmp_path / "none.csv")]) == 2
    capsys.readouterr()
    shutil.rmtree(root / "origin2.git")
    assert bm.main(args) == 2 and "instance 2: its bare" in capsys.readouterr().err


def bench_repro_pick_applies_the_landing_rule_and_replay_puts_one_instances_commits_on_a_work_branch(tmp_path, monkeypatch,
                                                                                                  capsys):
    import subprocess
    import benchmarks as bm
    for k, v in {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t",
                 "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}.items():
        monkeypatch.setenv(k, v)
    git = lambda *a, cwd: subprocess.run(["git", *a], cwd=str(cwd), capture_output=True, text=True, check=True).stdout.strip()  # noqa: E731
    # pick: the sum of eval_passed over the areas, then check_errors + lint_errors, then the summed cost, of the newest record
    def table(spec, record="abc1234", date="2026-10-16"):
        """repro-compare and repro rows of {n: (eval_passed per area, check_errors, lint_errors, cost per area)}, with the
        pair and agreement rows `compare` also writes."""
        rows = []
        for n, (passed, check, lint, cost) in spec.items():
            rows += [{"scenario": "repro-compare", "case": area, "arm": f"instance-{n}", "metric": "eval_passed", "value": str(passed)}
                     for area in ("alpha", "beta")]
            rows += [{"scenario": "repro-compare", "case": "all", "arm": f"instance-{n}", "metric": "check_errors", "value": str(check)},
                     {"scenario": "repro-compare", "case": "all", "arm": f"instance-{n}", "metric": "lint_errors", "value": str(lint)}]
            rows += [{"scenario": "repro", "case": area, "arm": f"instance-{n}", "metric": "cost", "value": str(cost)}
                     for area in ("alpha", "beta")]
            rows += [{"scenario": "repro-compare", "case": area, "arm": f"instance-{n}", "metric": "unanchored", "value": str(n)}
                     for area in ("alpha", "beta")]  # instance n left 2n DOC facts unanchored
        rows += [{"scenario": "repro-compare", "case": "alpha", "arm": "instance-1+instance-2", "metric": "fact_overlap", "value": "0.5"},
                 {"scenario": "repro-compare", "case": "alpha", "arm": "all", "metric": "agreement", "value": "1"}]
        return [{**r, "record": record, "date": date, "commit": record} for r in rows]

    def picked(rows):
        f = tmp_path / "picks.csv"
        bc.write_rows(rows, f)
        rc = bm.main(["repro", "pick", "--rows", str(f)])
        printed.append(capsys.readouterr().out)
        return rc, printed[-1].strip().splitlines()[-1]

    printed = []

    assert picked(table({1: (20, 0, 0, 25), 2: (22, 0, 1, 27.5)})) == (0, "picked: instance-2 (most eval_passed over instance-1)")
    assert "instance-2: eval_passed 44, check_errors+lint_errors 1, unanchored 4, cost 55.00" in printed[-1]  # summed over the areas
    assert picked(table({1: (22, 0, 1, 25), 2: (22, 1, 1, 25)}))[1].startswith("picked: instance-1 (fewest errors")
    assert picked([r for r in table({1: (22, 0, 0, 25)}) if r["metric"] != "unanchored"])[0] == 0
    assert "unanchored not recorded" in printed[-1]  # a record from before the metric
    assert picked(table({1: (22, 0, 0, 30), 2: (22, 0, 0, 25)}))[1].startswith("picked: instance-2 (lowest cost")
    assert picked(table({1: (22, 0, 0, 25), 2: (22, 0, 0, 25)}))[1].startswith("picked: instance-1 (a tie")
    old = table({1: (99, 0, 0, 1), 2: (1, 9, 9, 99)}, record="old0000", date="2026-10-01")
    assert picked(old + table({1: (20, 0, 0, 25), 2: (22, 0, 0, 25)}))[1].startswith("picked: instance-2")  # the newest record
    assert picked([r for r in table({1: (20, 0, 0, 25)}) if r["scenario"] == "repro"])[0] == 1  # no repro-compare row
    assert bm.main(["repro", "pick", "--rows", str(tmp_path / "none.csv")]) == 1 and "nothing to pick" in capsys.readouterr().out
    # replay: planted bares of two instances (one start commit, the same sha in each), a work tree on a branch of its own
    # whose origin is a planted bare standing in for the real one
    def plant(bare, commits):
        git("init", "-q", "--bare", "--initial-branch=main", str(bare), cwd=tmp_path)
        stream = ""
        for k, (msg, files) in enumerate(commits):
            stream += f"commit refs/heads/main\ncommitter t <t@example.com> {1760000000 + k} +0000\ndata {len(msg)}\n{msg}\n"
            stream += "".join(f"M 100644 inline {n}\ndata {len(x.encode())}\n{x}\n" for n, x in files.items()) + "\n"
        subprocess.run(["git", "fast-import", "--quiet"], cwd=str(bare), input=stream.encode(), check=True)
        return git("rev-list", "--reverse", "main", cwd=bare).split()

    first = ("start", {"a.txt": "base\n", "b.txt": "base\n"})
    root = tmp_path / "dir"
    root.mkdir()
    start, *_ = plant(root / "origin1.git", [first, ("add d", {"d.txt": "one\n"}), ("add e", {"e.txt": "one\n"})])
    plant(root / "origin2.git", [first, ("edit a", {"a.txt": "instance two\n"})])
    plant(tmp_path / "real.git", [first])
    (root / "instances.json").write_text(json.dumps({"rev": start, "instances": [
        {"n": n, "bare": str(root / f"origin{n}.git")} for n in (1, 2)]}), encoding="utf-8", newline="\n")
    work = tmp_path / "work"
    git("clone", "-q", str(tmp_path / "real.git"), str(work), cwd=tmp_path)
    git("checkout", "-q", "-b", "work/ST-test", cwd=work)
    (work / "a.txt").write_text("work\n", encoding="utf-8", newline="\n")
    git("commit", "-q", "-am", "work edits a", cwd=work)
    real_refs = git("for-each-ref", cwd=tmp_path / "real.git"), git("for-each-ref", "refs/remotes", cwd=work)
    monkeypatch.chdir(work)
    args = ["repro", "replay", "--item", "ST-test", "--dir", str(root)]
    # the commits of instance 1 land on the current branch, each with the trailer, and the helper branch is gone
    assert bm.main([*args, "--instance", "1"]) == 0
    assert "2 commit(s) of instance 1" in capsys.readouterr().out
    subjects = git("log", "--format=%s%n%(trailers:key=KB-Work,valueonly)", "-n", "2", cwd=work).split("\n")
    assert [s for s in subjects if s] == ["add e", "ST-test", "add d", "ST-test"]
    assert git("rev-list", "--count", f"{start}..HEAD", cwd=work) == "3" and git("branch", "--list", "repro-replay-*", cwd=work) == ""
    assert git("rev-parse", "--abbrev-ref", "HEAD", cwd=work) == "work/ST-test" and (work / "e.txt").exists()
    # neither the real origin nor the work tree's remote refs moved: the instance's bare was fetched by path
    assert (git("for-each-ref", cwd=tmp_path / "real.git"), git("for-each-ref", "refs/remotes", cwd=work)) == real_refs
    # instance 2 edits the file the work branch edited: the rebase stops, names it and stays in progress
    tip = git("rev-parse", "HEAD", cwd=work)
    assert bm.main([*args, "--instance", "2"]) == 1
    shown = capsys.readouterr().out
    assert "files in conflict:" in shown and "  a.txt" in shown
    assert (work / git("rev-parse", "--git-path", "rebase-merge", cwd=work)).is_dir()
    assert bm.main([*args, "--instance", "2"]) == 2 and "a rebase is in progress" in capsys.readouterr().err
    git("rebase", "--abort", cwd=work)
    git("checkout", "-q", "work/ST-test", cwd=work)
    git("branch", "-q", "-D", "repro-replay-instance2", cwd=work)
    assert git("rev-parse", "HEAD", cwd=work) == tip
    # a work tree with a change, a detached HEAD and an instance that is not there are refusals
    (work / "a.txt").write_text("changed\n", encoding="utf-8", newline="\n")
    assert bm.main([*args, "--instance", "2"]) == 2 and "uncommitted changes" in capsys.readouterr().err
    git("checkout", "-q", "--", "a.txt", cwd=work)
    assert bm.main([*args, "--instance", "3"]) == 2 and "holds instance(s) 1, 2" in capsys.readouterr().err
    git("checkout", "-q", "--detach", cwd=work)
    assert bm.main([*args, "--instance", "1"]) == 2 and "detached HEAD" in capsys.readouterr().err


def together(tmp_path, monkeypatch, capsys, *bodies, **fixtures):
    """Run each body as its own test would: a directory of its own, the patches of the ones before undone, no printed
    output of theirs left to read; `fixtures` are further fixtures a body names."""
    for n, body in enumerate(bodies):
        root = tmp_path / f"part{n}"
        root.mkdir()
        capsys.readouterr()
        with pytest.MonkeyPatch.context() as mp:
            have = {"tmp_path": root, "monkeypatch": mp, "capsys": capsys, **fixtures}
            body(**{k: v for k, v in have.items() if k in inspect.signature(body).parameters})


def test_bench_price_weights_and_tier_and_freshness_rows(tmp_path, monkeypatch, capsys, kb_seed):
    together(tmp_path, monkeypatch, capsys, bench_price_sonnet_55_run_weights_cache_reads_by_its_own_ratio,
             bench_price_tier_is_recorded_and_alias_follows_the_run,
             bench_freshness_rows_dry_run_and_report_check_exits_1_on_a_marker_with_no_rows,
             bench_repro_setup_pins_one_commit_per_instance_with_its_own_bare_mcp_config_log_mode_and_env,
             bench_repro_questions_and_status_name_each_planted_problem,
             bench_stream_run_passes_timeout_and_clean_env_and_an_error_result_keeps_its_cost_usage_and_subtype,
             bench_repro_run_starts_instances_together_stops_at_the_instance_budget_and_a_run_again_resumes,
             bench_repro_record_merges_planted_lines_as_rows_and_a_second_record_changes_nothing,
             bench_repro_compare_measures_two_planted_instances_shared_paraphrased_and_conflicting_facts,
             bench_repro_pick_applies_the_landing_rule_and_replay_puts_one_instances_commits_on_a_work_branch,
             kb_seed=kb_seed)


def test_bench_pool_build_check_scenario_rows_and_session_shape(tmp_path, monkeypatch, capsys):
    together(tmp_path, monkeypatch, capsys, bench_pool_build_counts_seed_heldout_and_querylog_stay_apart,
             bench_pool_check_reports_stale_pick_of_a_row_whose_check_misses_the_picked_line,
             bench_pool_scenario_rows_derived_cells_and_report_tables,
             bench_pool_session_shape_groups_resume_marginal_input_and_cache_share)


def test_bench_pool_max_usd_in_flight_dry_run_kind_prices_and_record_plans(tmp_path, monkeypatch, capsys):
    together(tmp_path, monkeypatch, capsys,
             bench_pool_max_usd_in_flight_counts_the_runs_started_and_jobs_parallel_rows_equal_one_job_and_the_record_date_holds,
             bench_pool_dry_run_kind_prices_and_jobs_scenario_stops_at_the_cap_with_a_spend_stopped_row,
             bench_pool_record_plans_arm_reps_kinds_sample_both_shapes_and_one_cap)


def test_bench_pool_verify_names_each_planted_break_and_a_rerun_of_one_label_narrows_the_spend_row(tmp_path, monkeypatch,
                                                                                                    capsys):
    together(tmp_path, monkeypatch, capsys, bench_pool_verify_exits_1_naming_each_planted_break_of_a_fake_record,
             bench_pool_rerun_of_one_label_narrows_the_earlier_spend_row_and_respend_repairs_a_record)
