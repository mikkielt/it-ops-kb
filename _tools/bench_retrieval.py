"""The benchmarks' retrieval scenarios: the quality of the pack (retrieval, verdict, doc2query) and the speed
of the tools (stdlib only).

benchmarks.py registers these scenarios in SCENARIOS and holds the command line; the harness is bench_core.py
(kb/_self/code.md, Layout and Imports; the scenarios are described in kb/_self/reports/benchmarks.md). This
module imports no facade.
"""
import json, random, re, shutil, statistics, subprocess, sys, time, uuid
from pathlib import Path

from bench_core import (HOME, TOOLS, claude_json, mcp_session, no_plugin_env, stat_rows, time_runs)
from kbcommon import NO_HOOKS


def _sonnet_json(prompt, cwd):
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
    qs, cost = _sonnet_json(BLIND + "\n".join(f"{i}. {u['text'][:400]}" for i, u in enumerate(blind)), b.scratch)
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


def s_verdict(b):
    """Verdict corrections: the eval set, the off-kb list's verdicts, the indexed lines and pack's time over the eval
    questions, warm."""
    import kbfacts, rag
    res = rag.run_eval()
    b.row("verdict", "eval set", "current", "passed", f"{res['passed']}/{res['n']}", 1)
    b.row("verdict", "eval set", "current", "mean_chars", res["mean_chars"], 1)
    path = Path(kbfacts.kbcommon.public().path) / "_retrieval" / "doc2query" / "offkb_questions.txt"
    qs = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")]
    vs = [kbfacts.pack(q)["verdict"] for q in qs]
    for v in ("good", "weak", "none"):
        b.row("verdict", "off-kb list", "current", f"verdict_{v}", vs.count(v), 1, note=f"of {len(qs)}")
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
    b.row("verdict", "pack, warm", "current", "p95_ms", times[int(0.95 * len(times)) - 1], 3)


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
        qs, cost = _sonnet_json(BLIND + "\n".join(f"{i}. {f['text'][:400]}" for i, f in enumerate(pick)), b.scratch)
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
