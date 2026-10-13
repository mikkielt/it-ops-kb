"""The benchmarks' retrieval scenarios: the quality of the pack (retrieval, verdict, doc2query), the freshness the
lookup revalidation reports for the pool's cited sources, and the speed of the tools (stdlib only).

benchmarks.py registers these scenarios in SCENARIOS and holds the command line; the harness is bench_core.py
(kb/_self/code.md, Layout and Imports; the scenarios are described in kb/_self/reports/benchmarks.md). This
module imports no facade.
"""
import collections, contextlib, json, math, random, re, shutil, statistics, subprocess, sys, threading, time, urllib.parse, uuid
from pathlib import Path

from bench_core import (HOME, TOOLS, Skip, claude_json, mcp_session, no_plugin_env, stat_rows, time_runs)
from kbcommon import NO_HOOKS


def sonnet_json(prompt, cwd):
    """A tool-less Sonnet reply parsed as the JSON array it was asked for, and its cost."""
    ev = claude_json(["claude", "-p", "--no-session-persistence", "--model", "sonnet", *NO_HOOKS, "--tools", "",
                      "--setting-sources", "project,local", "--strict-mcp-config"], prompt, cwd)
    text = ev.get("result") or ""
    a, z = text.find("["), text.rfind("]")
    try:
        return json.loads(text[a:z + 1]), ev.get("total_cost_usd", 0)
    except ValueError:
        return [], ev.get("total_cost_usd", 0)


BLIND = ("For each numbered fact below, write one question a person would ask whose answer is that fact. Use your own "
         "words, not the fact's distinctive terms where a person would not know them. Reply with only a JSON array: "
         '[{"i": 0, "question": "..."}, ...].\n\n')


def numbered(texts):
    """The numbered list a blind prompt ends with: one line per text, cut at 400 characters."""
    return "\n".join(f"{i}. {t[:400]}" for i, t in enumerate(texts))


def s_retrieval(b):
    """Retrieval quality: keyword probes over sampled units, blind questions written by Sonnet from the fact text
    alone, the off-kb questions' verdicts, cut facts without a visible tag and the code examples a pack finds."""
    import kbfacts
    rng = random.Random(7)
    all_units = kbfacts.units(untagged=True)
    sample = rng.sample(all_units, min(844, len(all_units)))
    hit = {"tagged": [0, 0], "untagged": [0, 0]}
    for u in sample:
        words = sorted(set(re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", u["text"])), key=len, reverse=True)[:6]
        res = kbfacts.pack(" ".join(words))
        k = "tagged" if u["tags"] else "untagged"
        hit[k][1] += 1
        hit[k][0] += f"{u['path']}:{u['line']} " in res["text"] or f"{u['path']}:{u['line']}\n" in res["text"]
    for k, (h, n) in hit.items():
        label = "untagged content" if k == "untagged" else "tagged facts"
        b.row("retrieval", f"{label}, line in pack (keyword probes)", "current", "value", f"{100 * h / max(n, 1):.0f}%",
              1, note=f"{h} of {n} sampled units")
    blind = rng.sample([u for u in all_units if u["tags"]], 72)
    qs, cost = sonnet_json(BLIND + numbered([u["text"] for u in blind]), b.scratch)
    found = false_none = 0
    for q in qs:
        u = blind[q["i"]] if isinstance(q, dict) and q.get("i") in range(len(blind)) else None
        if not u:
            continue
        res = kbfacts.pack(q["question"])
        found += f"{u['path']}:{u['line']} " in res["text"] or f"{u['path']}:{u['line']}\n" in res["text"]
        false_none += res["verdict"] == "none"
    b.row("retrieval", "blind questions, line in pack", "current", "value", f"{found}/{len(qs)}", 1, "sonnet")
    b.row("retrieval", "blind questions, false none", "current", "value", f"{false_none}/{len(qs)}", 1, "sonnet")
    b.row("retrieval", "blind questions", "current", "cost", cost, 1, "sonnet")
    offkb = [q for q in (kbfacts.kbcommon.public().path + "/_retrieval/doc2query/offkb_questions.txt",)]
    lines = [ln.strip() for ln in Path(offkb[0]).read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")]
    verdicts = [kbfacts.pack(q)["verdict"] for q in lines]
    b.row("retrieval", "off-kb questions answered good", "current", "value", f"{verdicts.count('good')}/{len(lines)}", 1)
    import rag
    tagged = {f"{u['path']}:{u['line']}" for u in all_units if u["tags"]}
    cut_no_tag = 0  # a tagged fact cut to fit the budget whose printed line shows no tag
    for _, c in rag.eval_cases():
        for ln in kbfacts.pack(c["question"])["text"].splitlines():
            where = ln[2:].split(" ", 1)[0] if ln.startswith("- ") else ""
            if where in tagged and ("..." in ln or "…" in ln) and \
                    not re.search(r"\[(DOC|CODE|DER|COMMUNITY|UNK|DECISION)[^\]]*\]|tag=|\((DOC|CODE|DER|COMMUNITY|UNK|DECISION)\)", ln):
                cut_no_tag += 1
    b.row("retrieval", "cut facts with no visible tag", "current", "value", cut_no_tag, 1)
    snippets = [u for u in all_units if u["text"].lstrip().startswith("SNIPPET")]
    got = 0
    for u in snippets:
        words = sorted(set(re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", u["text"])), key=len, reverse=True)[:6]
        got += f"{u['path']}:{u['line']}" in kbfacts.pack(" ".join(words))["text"]
    b.row("retrieval", "code blocks retrievable", "current", "value", f"{got}/{len(snippets)}", 1)


def scatter_rows(b):
    """The scatter check's calibration (rag.scatter_calibration): the threshold fitted to the eval set's good rows
    against the off-kb list's good ones, the threshold pack uses, and the goods each flags."""
    import rag
    c = rag.scatter_calibration()
    for arm, threshold, off, ev in (("calibrated", c["threshold"], c["off_flagged"], c["eval_flagged"]),
                                    ("current", c["current"], c["off_noted"], c["eval_noted"])):
        b.row("verdict", "scatter check", arm, "threshold", threshold, 1)
        b.row("verdict", "scatter check", arm, "off_kb_goods_flagged", off, 1, note=f"of {c['off_goods']}")
        b.row("verdict", "scatter check", arm, "eval_goods_flagged", ev, 1, note=f"of {c['eval_goods']}")


def s_verdict(b):
    """Verdict corrections: the eval set, the off-kb list's verdicts, the scatter check's calibration, the indexed
    lines and pack's time over the eval questions, warm."""
    import kbfacts, rag
    res = rag.run_eval()
    b.row("verdict", "eval set", "current", "passed", f"{res['passed']}/{res['n']}", 1)
    b.row("verdict", "eval set", "current", "mean_chars", res["mean_chars"], 1)
    qs = rag.offkb_questions()
    vs = [kbfacts.pack(q)["verdict"] for q in qs]
    for v in ("good", "weak", "none"):
        b.row("verdict", "off-kb list", "current", f"verdict_{v}", vs.count(v), 1, note=f"of {len(qs)}")
    scatter_rows(b)
    b.row("verdict", "index", "current", "indexed_lines", len(kbfacts.units(untagged=True)), 1)
    questions = [c["question"] for _, c in rag.eval_cases()]
    times = []
    for _ in range(3):
        for q in questions:
            t = time.perf_counter()
            kbfacts.pack(q)
            times.append((time.perf_counter() - t) * 1000)
    times.sort()
    b.row("verdict", "pack, warm", "current", "median_ms", statistics.median(times), 3)
    b.row("verdict", "pack, warm", "current", "p95_ms", times[math.ceil(0.95 * len(times)) - 1], 3)


def s_doc2query(b):
    """doc2query: fresh blind paraphrases (Sonnet, 40 facts per arm of arms.json) evaluated with expansion off and on."""
    import doc2query
    doc2query.use_root()
    tests = []
    rng = random.Random(29)
    for arm in ("pilot", "control"):
        out = b.scratch / f"d2q-{arm}.json"
        subprocess.run([sys.executable, str(TOOLS / "doc2query.py"), "batch", arm, "--out", str(out)], cwd=HOME,
                       capture_output=True, env=no_plugin_env())
        facts = json.loads(out.read_text(encoding="utf-8"))
        pick = rng.sample(facts, min(40, len(facts)))
        qs, cost = sonnet_json(BLIND + numbered([f["text"] for f in pick]), b.scratch)
        b.row("doc2query", "blind questions", arm, "cost", cost, 1, "sonnet")
        tests += [{"key": pick[q["i"]]["key"], "question": q["question"]} for q in qs
                  if isinstance(q, dict) and q.get("i") in range(len(pick))]
    tf = b.scratch / "d2q-test.json"
    tf.write_text(json.dumps(tests), encoding="utf-8")
    p = subprocess.run([sys.executable, str(TOOLS / "doc2query.py"), "evaluate", str(tf)], cwd=HOME, capture_output=True,
                       text=True, encoding="utf-8", env=no_plugin_env())
    mode = None
    for ln in p.stdout.splitlines():
        m = re.match(r"== expansion (on|off)", ln)
        if m:
            mode = m.group(1)
            continue
        m = re.match(r"\s+(pilot|control)\s+n=\s*(\d+)\s+line=\s*(\d+)%\s+article=\s*(\d+)%", ln)
        if m and mode:
            b.row("doc2query", f"{m.group(1)} arm", f"expansion {mode}", "line_in_pack_pct", int(m.group(3)), 1,
                  note=f"n={m.group(2)}")
        m = re.match(r"\s+eval (\d+)/(\d+) mean_chars=(\d+); off-kb verdicts (.*)", ln)
        if m and mode:
            b.row("doc2query", "eval set", f"expansion {mode}", "passed", f"{m.group(1)}/{m.group(2)}", 1)
            b.row("doc2query", "eval set", f"expansion {mode}", "mean_chars", int(m.group(3)), 1)
            v = dict(re.findall(r"'(\w+)': (\d+)", m.group(4)))
            b.row("doc2query", "off-kb", f"expansion {mode}", "verdicts",
                  ", ".join(f"{k} {v.get(k, '0')}" for k in ("good", "weak", "none")), 1)


def s_tool_speed(b):
    """Tool speed: cold CLI calls with the persisted index, the kb: hook, rag.py eval and search, an MCP session of 12
    calls, check-trailers over 30 commits, an index build; in-process pack, the server's start, 1,000 random packs."""
    clone = b.lookup()
    py = sys.executable
    stat_rows(b, "tool-speed", "rag.py pack (CLI, cold)", "current", time_s=True, secs=time_runs([py, "_tools/rag.py", "pack", "default Windows LAPS password length"], 5, clone))
    hook = json.dumps({"hook_event_name": "UserPromptSubmit", "session_id": str(uuid.uuid4()), "prompt":
                       "kb: Does deleting an Entra device also delete its BitLocker recovery keys?"})
    stat_rows(b, "tool-speed", "kb: hook", "current", time_s=True, secs=time_runs([py, "_tools/kb_hook.py"], 5, clone, stdin=hook))
    stat_rows(b, "tool-speed", "rag.py eval", "current", time_s=True, secs=time_runs([py, "_tools/rag.py", "ev" + "al"], 3, clone))
    stat_rows(b, "tool-speed", "rag.py search", "current", time_s=True, secs=time_runs([py, "_tools/rag.py", "search", "gMSA password retrieval"], 5, clone))
    stat_rows(b, "tool-speed", "kbgit.py check-trailers (30 commits)", "current", time_s=True,
           secs=time_runs([py, "_tools/kbgit.py", "check-trailers", "HEAD~30..HEAD"], 3, clone))
    secs = [mcp_session(clone)[1] for _ in range(3)]
    stat_rows(b, "tool-speed", "MCP session (12 calls)", "current", secs, time_s=True)
    starts = [mcp_session(clone, [])[0] for _ in range(5)]
    stat_rows(b, "tool-speed", "MCP server start (initialize reply)", "current", starts)
    idx = b.scratch / "index-build"
    shutil.rmtree(idx, ignore_errors=True)
    idx.mkdir()
    t = time_runs([py, "_tools/rag.py", "pack", "x"], 1, clone, env=no_plugin_env({"KB_INDEX": str(idx)}))
    b.row("tool-speed", "index build", "current", "time", t[0], 1)
    b.row("tool-speed", "index build", "current", "size_mb", sum(f.stat().st_size for f in idx.glob("*.sqlite")) / 1e6, 1)
    import kbfacts, rag
    qs = [c["question"] for _, c in rag.eval_cases()]
    for q in qs[:5]:
        kbfacts.pack(q)
    ms = []
    for q in qs:
        t0 = time.perf_counter()
        kbfacts.pack(q)
        ms.append(time.perf_counter() - t0)
    stat_rows(b, "tool-speed", "pack in-process, warm", "current", ms)
    rng = random.Random(3)
    words = [w for u in rng.sample(kbfacts.units(), 400) for w in re.findall(r"[A-Za-z]{4,}", u["text"])]
    t0 = time.perf_counter()
    for _ in range(1000):
        kbfacts.pack(" ".join(rng.sample(words, 4)))
    b.row("tool-speed", "1,000 random packs", "current", "s", time.perf_counter() - t0, 1)


# ---- freshness: the lookup revalidation over the pool's answerable questions, no model

FRESH_KEYS = {"current": "current", "moved": "moved", "not found": "not_found", "source-dated only": "source_dated_only",
              "": "not_checked"}  # factdiff.revalidate's outcome of a printed line (empty: no cited source could be checked)


def fresh_host(url):
    """The host a source url is served from; `unknown` for a source row with no url."""
    return urllib.parse.urlsplit(url or "").netloc.lower() or "unknown"


@contextlib.contextmanager
def counted_requests(counts):
    """provider.request counted per host in `counts` ({host: [made, with no HTTP answer]}) for the block; a request the
    time budget refused was never made and is not counted."""
    import provider
    real, lock = provider.request, threading.Lock()

    def counting(url, *args, **kw):
        out = real(url, *args, **kw)
        if out.get("error") != provider.BUDGET_ERROR:
            with lock:
                c = counts.setdefault(fresh_host(url), [0, 0])
                c[0] += 1
                c[1] += not out.get("status")
        return out
    provider.request = counting
    try:
        yield
    finally:
        provider.request = real


def fresh_lines(res, doc):
    """The printed fact lines of a pack_many result that carry a DOC tag: [{path, line, key, text, ids}]; `doc` is the set
    of (path, line) of the units that do."""
    return [p for r in res["results"] for p in r.get("printed", []) if (p["path"], p["line"]) in doc]


def fresh_question(res, doc, srcs, wall):
    """One question's lookup: {wall, tally: {(host, metric): printed DOC lines}, sources: {state: n}, spent}. A line
    counts under the host of the source whose outcome it prints (of those it cites, the worst: factdiff.LOOKUP_ORDER),
    or of its first source when none could be checked; `spent` is whether the time budget cut a request."""
    import provider
    rev = res.get("revalidate")
    lines = rev["lines"] if rev else {}
    out = {"wall": wall, "tally": collections.Counter(), "sources": collections.Counter(), "spent": False}
    for p in fresh_lines(res, doc):
        r = lines.get(f"{p['path']}:{p['line']}") or {}
        outcome = r.get("outcome", "")
        sid = (r.get("id") if outcome else "") or p["ids"][0]
        out["tally"][(fresh_host((srcs.get(sid) or {}).get("url")), FRESH_KEYS[outcome])] += 1
    for v in (rev or {"sources": {}})["sources"].values():
        out["sources"][v["state"]] += 1
        out["spent"] |= v.get("why") == provider.BUDGET_ERROR
    out["spent"] |= any(w == provider.BUDGET_ERROR for r in lines.values() for w in r.get("unchecked", {}).values())
    return out


def _n(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def fresh_plan(asks, srcs, delay):
    """Print what a run would ask, per host: the cited sources (not superseded ones, which a lookup does not ask), the
    printed DOC lines and questions that cite them, and one request per source per question as the least a run makes
    (a moved page, a pinned repository or a search adds more; a source asked again within its provider's pacing is
    answered from the stored check). Returns the totals line."""
    hosts = {}
    for r, lines in asks:
        for p in lines:
            cited = set()  # the hosts this line cites, each counted once for it
            for sid in p["ids"]:
                row = srcs.get(sid) or {}
                if not row.get("url") or (row.get("superseded_by") or "").strip():
                    continue
                host = fresh_host(row["url"])
                h = hosts.setdefault(host, {"sources": {}, "lines": 0, "questions": set(), "url": {}})
                h["sources"].setdefault(sid, set()).add(r["id"])
                h["url"][sid] = row["url"]
                h["questions"].add(r["id"])
                if host not in cited:
                    cited.add(host)
                    h["lines"] += 1
    total = 0
    for host, h in sorted(hosts.items(), key=lambda kv: (-len(kv[1]["sources"]), kv[0])):
        requests = sum(len(q) for q in h["sources"].values())
        total += requests
        print(f"freshness: {host}: {_n(len(h['sources']), 'source')}, {_n(h['lines'], 'line')} in "
              f"{_n(len(h['questions']), 'question')}, {_n(requests, 'request')} ({requests * delay:.0f} s at {delay} s each)",
              flush=True)
        for sid in sorted(h["sources"]):
            print(f"freshness:   {sid}  {h['url'][sid]}  ({_n(len(h['sources'][sid]), 'question')})", flush=True)
    sources = sum(len(h["sources"]) for h in hosts.values())
    lines = sum(len(lines) for _, lines in asks)
    return (f"{_n(len(asks), 'answerable pool row')}, {_n(lines, 'printed DOC line')}, {_n(sources, 'source')} on "
            f"{_n(len(hosts), 'host')}, {_n(total, 'request')} at the least")


def fresh_rows(b, per_q, counts, pool_rows, note):
    """The rows of a run: for all printed DOC lines (case `all`) and per host of the source each line prints, the lines
    by outcome and the shares of current, moved and source-dated ones, the requests made and the wall time of the
    questions that cite the host (median and p95, seconds); for all, also the questions, the slowest, the questions the
    revalidation's time budget cut and the sources by how they were answered."""
    hosts = sorted({h for q in per_q for h, _ in q["tally"]})
    for case in ["all", *hosts, *sorted(set(counts) - set(hosts))]:
        mine = [q for q in per_q if case == "all" or any(h == case for h, _ in q["tally"])]
        n = {m: sum(v for q in per_q for (h, k), v in q["tally"].items() if k == m and case in ("all", h))
             for m in FRESH_KEYS.values()}
        total = sum(n.values())
        runs = len(mine) if case != "all" else len(per_q)  # a host that only answered requests has no question
        if case == "all" or case in hosts:
            b.row("freshness", case, "current", "doc_lines", total, runs, note=note if case == "all" else "")
            for m, v in n.items():
                b.row("freshness", case, "current", m, v, runs)
            for m in ("current", "moved", "source_dated_only"):
                if total:
                    b.row("freshness", case, "current", f"{m}_share", n[m] / total, runs)
        made = sum(c[0] for h, c in counts.items() if case in ("all", h))
        failed = sum(c[1] for h, c in counts.items() if case in ("all", h))
        b.row("freshness", case, "current", "requests", made, runs or "")
        b.row("freshness", case, "current", "failed_requests", failed, runs or "")
        walls = sorted(q["wall"] for q in mine)
        if walls and (case == "all" or case in hosts):
            b.row("freshness", case, "current", "median_s", statistics.median(walls), len(walls))
            b.row("freshness", case, "current", "p95_s", walls[max(0, math.ceil(0.95 * len(walls)) - 1)], len(walls))
    walls = [q["wall"] for q in per_q]
    b.row("freshness", "all", "current", "questions", len(per_q), len(per_q), note=f"of {len(pool_rows)} pool rows")
    b.row("freshness", "all", "current", "max_s", max(walls), len(per_q))
    b.row("freshness", "all", "current", "budget_spent", sum(q["spent"] for q in per_q), len(per_q))
    for state in ("live", "cached", "offline"):
        b.row("freshness", "all", "current", f"sources_{state}", sum(q["sources"][state] for q in per_q), len(per_q))


def s_freshness(b):
    """Freshness: each answerable row of the question pool (route `good`; `b.sample` rows of each kind, seed `b.seed`)
    is looked up with revalidation (kbfacts.pack_many, revalidate=True: the cited sources are asked live, within each
    provider's pacing and the revalidation's time budget), and the printed DOC lines are counted by outcome per host,
    with the wall time per question and the requests made. No model. With `b.dry` it prints the sources and requests a
    run would make and asks nothing."""
    import bench_pool, kbfacts
    sample, seed = getattr(b, "sample", None), getattr(b, "seed", bench_pool.SEED)
    pool = [r for r in bench_pool.load_pool(HOME) if r["expected_route"] == "good"]
    rows = bench_pool.sample_rows(pool, sample, seed)
    if not rows:
        raise Skip("no answerable rows in the pool: python3 _tools/benchmarks.py pool build")
    doc = {(u["path"], u["line"]) for u in kbfacts.units() if "DOC" in kbfacts.kinds_of(u["tags"])}
    srcs = kbfacts.source_rows()
    import provider
    if getattr(b, "dry", False):
        asks = [(r, fresh_lines(kbfacts.pack_many([r["question"]]), doc)) for r in rows]
        raise Skip("dry run: " + fresh_plan(asks, srcs, provider.DELAY) + ", no request made")
    counts, per_q = {}, []
    with counted_requests(counts):
        for r in rows:
            t = time.perf_counter()
            res = kbfacts.pack_many([r["question"]], revalidate=True)
            per_q.append(fresh_question(res, doc, srcs, time.perf_counter() - t))
    command = "run freshness" + (f" --sample {sample}" if sample else "") + (f" --seed {seed}" if seed != bench_pool.SEED else "")
    fresh_rows(b, per_q, counts, pool, command)
