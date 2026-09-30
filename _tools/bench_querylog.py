"""The benchmarks' query-log scenarios: the hooks, the pipeline from spool to applied findings, redaction
speed and research cost (stdlib only).

benchmarks.py registers these scenarios in SCENARIOS and holds the command line; the harness is bench_core.py
(kb/_self/code.md, Layout and Imports; the scenarios are described in kb/_self/reports/benchmarks.md). This
module imports no facade.
"""
import json, os, re, shutil, statistics, subprocess, sys, time, uuid
from pathlib import Path

from bench_core import (TOOLS, git, need_sh, no_plugin_env, shim_dir, spent, stat_rows)


def _event(kind, sid, pid, **kw):
    return json.dumps({"hook_event_name": kind, "session_id": sid, "prompt_id": pid, "cwd": "/tmp", **kw})


def s_querylog_hooks(b):
    """The query log's hooks: capture per event (async, so no prompt waits on it), the synchronous UserPromptSubmit
    hooks, the SessionEnd launcher's return time (nothing to distill, and a closed session to distill: it starts a
    detached distill, whose `claude` here fails at once), and the weekly digest hook; all through `sh _tools/kbpy` of
    a throwaway clone, writing under a scratch plugin data directory in mode `local`."""
    sh = need_sh()
    clone = b.clone("kb-hooks", "local")
    data = b.scratch / "ql-hooks-data"
    shutil.rmtree(data, ignore_errors=True)
    (data / "querylog").mkdir(parents=True)
    (data / "querylog" / "config.json").write_text('{"mode": "local"}\n', encoding="utf-8")
    fail = shim_dir(b.scratch / "fail-shim")
    env = no_plugin_env({"CLAUDE_PLUGIN_ROOT": str(clone), "CLAUDE_PLUGIN_DATA": str(data), "KB_INDEX": str(clone / "_cache"),
                         "PATH": f"{fail}{os.pathsep}{os.environ.get('PATH', '')}"})
    kbpy = [sh, str(clone / "_tools" / "kbpy")]
    n = max(30, b.reps)
    sid = str(uuid.uuid4())
    events = {
        "UserPromptSubmit": lambda i: _event("UserPromptSubmit", sid, f"p{i}", prompt="kb: default Windows LAPS password length"),
        "PostToolUse (kb_pack)": lambda i: _event("PostToolUse", sid, f"p{i}", tool_name="mcp__plugin_it-ops-kb_kb__kb_pack",
                                                  tool_input={"question": "LAPS password length"},
                                                  tool_response=[{"type": "text", "text": "coverage: good\n## public/windows/laps.md"}]),
        "Stop": lambda i: _event("Stop", sid, f"p{i}", last_assistant_message="The default is 14 characters."),
    }
    for name, ev in events.items():
        secs = []
        for i in range(n):
            t = time.perf_counter()
            subprocess.run(kbpy + ["_tools/querylog.py", "capture"], cwd=clone, input=ev(i), capture_output=True, text=True, env=env)
            secs.append(time.perf_counter() - t)
        stat_rows(b, "querylog-hooks", f"capture, {name}", "async hook", secs)
    plain = _event("UserPromptSubmit", sid, "x", prompt="How do I rename a branch?")
    stat_rows(b, "querylog-hooks", "kb_hook.py, a prompt without kb:", "sync hook",
           [_t(kbpy + ["_tools/kb_hook.py"], clone, plain, env) for _ in range(n)])
    stat_rows(b, "querylog-hooks", "kb_change_router.py, a question", "sync hook (clone only)",
           [_t(kbpy + [".claude/hooks/kb_change_router.py"], clone, plain, env) for _ in range(n)])
    idle = []
    for _ in range(20):
        idle.append(_t(kbpy + ["_tools/querylog.py", "launch"], clone,
                       _event("SessionEnd", str(uuid.uuid4()), "", reason="other"), env))
    stat_rows(b, "querylog-hooks", "SessionEnd launcher, nothing waiting", "sync hook", idle,
           note="LAUNCH_BUDGET_S 500 ms")
    ready = []
    for _ in range(20):
        s = str(uuid.uuid4())
        subprocess.run(kbpy + ["_tools/querylog.py", "capture"], cwd=clone, input=_event("UserPromptSubmit", s, "p", prompt="kb: LAPS length"),
                       capture_output=True, text=True, env=env)
        (data / "querylog" / "distill.lock").unlink(missing_ok=True)
        ready.append(_t(kbpy + ["_tools/querylog.py", "launch"], clone, _event("SessionEnd", s, "", reason="other"), env))
    stat_rows(b, "querylog-hooks", "SessionEnd launcher, a session to distill", "sync hook", ready,
           note="starts a detached distill; LAUNCH_BUDGET_S 500 ms")
    b.row("querylog-hooks", "SessionEnd launcher", "sync hook", "max_ms", max(idle + ready) * 1000, len(idle + ready))
    (data / "querylog" / "digest-week").unlink(missing_ok=True)
    stat_rows(b, "querylog-hooks", "digest --hook", "sync hook",
           [_t(kbpy + ["_tools/querylog.py", "digest", "--hook"], clone, _event("SessionStart", sid, "", source="startup"), env)
            for _ in range(10)])
    time.sleep(3)


def _t(argv, cwd, stdin, env):
    t = time.perf_counter()
    subprocess.run(argv, cwd=str(cwd), input=stdin, capture_output=True, text=True, env=env)
    return time.perf_counter() - t


FIXTURES = TOOLS / "fixtures" / "querylog"


def _plant_spool(data):
    """The fixture spool under `data`'s querylog directory, every session closed by its SessionEnd marker."""
    sp = Path(data) / "querylog" / "spool"
    shutil.rmtree(sp, ignore_errors=True)
    shutil.copytree(FIXTURES / "spool", sp)
    for f in sp.glob("*.jsonl"):
        if not f.name.startswith("tools-"):
            (sp / (f.stem + ".end")).write_text("", encoding="utf-8")
    return sp


def _qdata(b, name, mode="local"):
    data = b.scratch / name
    shutil.rmtree(data, ignore_errors=True)
    (data / "querylog").mkdir(parents=True)
    (data / "querylog" / "config.json").write_text(json.dumps({"mode": mode}) + "\n", encoding="utf-8")
    return data


def _store_counts(store):
    n = 0
    for f in Path(store).rglob("*.jsonl"):
        if "findings" in f.parts:
            continue
        n += sum(1 for _ in f.read_text(encoding="utf-8").splitlines()[1:])
    return n


def _gates(clone):
    """(eval passed, eval rows, mean pack chars, off-kb good, off-kb questions) of the clone's working tree."""
    code = ("import sys, json; sys.path.insert(0, '_tools'); import rag, kbfacts; r = rag.run_" + "ev" + "al(); "
            "p = kbfacts.kbcommon.public().path + '/_retrieval/doc2query/offkb_questions.txt'; "
            "qs = [l.strip() for l in open(p, encoding='utf-8') if l.strip() and not l.startswith('#')]; "
            "g = sum(kbfacts.pack(q)['verdict'] == 'good' for q in qs); "
            "print(json.dumps([r['passed'], r['n'], r['mean_chars'], g, len(qs)]))")
    p = subprocess.run([sys.executable, "-c", code], cwd=str(clone), capture_output=True, text=True, env=no_plugin_env())
    return json.loads(p.stdout.strip().splitlines()[-1])


def s_querylog_pipeline(b):
    """Distill, learn and apply: run time on the recorded fixtures (distill with the recorded Haiku replies), the
    adoption gates' numbers before and after apply, and one real Haiku batch for its tokens per entry."""
    clone = b.clone("kb-pipeline", "local")
    ql = [sys.executable, str(clone / "_tools" / "querylog.py")]
    secs, entries = [], 0
    for _ in range(5):
        data = _qdata(b, "ql-distill")
        _plant_spool(data)
        env = no_plugin_env({"CLAUDE_PLUGIN_ROOT": str(clone), "CLAUDE_PLUGIN_DATA": str(data)})
        t = time.perf_counter()
        subprocess.run(ql + ["distill", "--replay", str(FIXTURES / "haiku.json")], cwd=clone, capture_output=True, env=env)
        secs.append(time.perf_counter() - t)
        entries = _store_counts(data / "querylog" / "store")
    stat_rows(b, "querylog-pipeline", "distill (recorded Haiku)", "fixtures", secs, note=f"{entries} entries written")
    b.row("querylog-pipeline", "distill (recorded Haiku)", "fixtures", "entries", entries, len(secs))
    pv = subprocess.run([sys.executable, "-c", "import ql_base; print(ql_base.PIPELINE_VERSION)"], cwd=clone / "_tools",
                        capture_output=True, text=True).stdout.strip()
    b.row("querylog-pipeline", "pipeline version", "fixtures", "PIPELINE_VERSION", pv, 1)
    store = b.scratch / "ql-store"
    shutil.rmtree(store, ignore_errors=True)
    shutil.copytree(FIXTURES / "store", store)
    env = no_plugin_env()
    t = time.perf_counter()
    subprocess.run(ql + ["learn", "--store", str(store)], cwd=clone, capture_output=True, env=env)
    b.row("querylog-pipeline", "learn", "fixtures", "s", time.perf_counter() - t, 1)
    findings = sum(len(f.read_text(encoding="utf-8").splitlines()) - 1 for f in (store / "findings").rglob("*.jsonl")) \
        if (store / "findings").exists() else 0
    b.row("querylog-pipeline", "learn", "fixtures", "finding_records", findings, 1)
    before = _gates(clone)
    t = time.perf_counter()
    subprocess.run(ql + ["apply", "--store", str(store)], cwd=clone, capture_output=True, env=env)
    b.row("querylog-pipeline", "apply", "fixtures", "s", time.perf_counter() - t, 1)
    after = _gates(clone)
    for i, metric in enumerate(("eval_passed", "eval_rows", "mean_pack_chars", "offkb_good", "offkb_questions")):
        b.row("querylog-pipeline", "adoption gates", "before apply", metric, before[i], 1)
        b.row("querylog-pipeline", "adoption gates", "after apply", metric, after[i], 1)
    states, gates = {}, []
    for f in sorted((store / "findings").rglob("*.jsonl")):
        for ln in f.read_text(encoding="utf-8").splitlines()[1:]:
            rec = json.loads(ln)
            states[rec["id"]] = (rec.get("kind"), rec.get("state"))
            if rec.get("kind") in ("alias", "expansion"):
                gates += (rec.get("observed") or {}).get("gate", [])
    b.row("querylog-pipeline", "adoption gates", "candidates", "rejected", len(gates), 1)
    for reason, pat in (("eval fails", "eval fails"), ("off-kb good rises", "off-kb good rises"),
                        ("mean pack grows", "mean pack")):
        b.row("querylog-pipeline", "adoption gates", "candidates", f"failed: {reason}",
              sum(pat in g for g in gates), 1, note="; ".join(g for g in gates if pat in g and "off-kb" in g)[:120])
    for (kind, state) in sorted(set(states.values())):
        b.row("querylog-pipeline", "apply outcomes", kind, state, sum(1 for v in states.values() if v == (kind, state)), 1)
    b.row("querylog-pipeline", "apply", "fixtures", "changed_files",
          len([ln for ln in git("status", "--porcelain", cwd=clone).splitlines() if ln.strip()]), 1)
    git("checkout", "-q", "--", ".", cwd=clone)
    # one real Haiku batch: the fixture spool distilled with the real CLI, through a shim that logs its usage
    data = _qdata(b, "ql-haiku")
    _plant_spool(data)
    log = b.scratch / "haiku-usage.jsonl"
    log.unlink(missing_ok=True)
    sd = shim_dir(b.scratch / "log-shim", log)
    env = no_plugin_env({"CLAUDE_PLUGIN_ROOT": str(clone), "CLAUDE_PLUGIN_DATA": str(data),
                         "PATH": f"{sd}{os.pathsep}{os.environ.get('PATH', '')}"})
    t = time.perf_counter()
    subprocess.run(ql + ["distill"], cwd=clone, capture_output=True, env=env)
    b.row("querylog-pipeline", "distill (real Haiku)", "fixtures", "s", time.perf_counter() - t, 1, "haiku")
    calls = _logged(log)
    items = sum(c["items"] for c in calls)
    u = [c["usage"] or {} for c in calls]
    tin = sum(x.get("input_tokens", 0) + x.get("cache_creation_input_tokens", 0) + x.get("cache_read_input_tokens", 0) for x in u)
    tout = sum(x.get("output_tokens", 0) for x in u)
    b.row("querylog-pipeline", "distill (real Haiku)", "fixtures", "haiku_calls", len(calls), 1, "haiku")
    b.row("querylog-pipeline", "distill (real Haiku)", "fixtures", "entries_sent", items, 1, "haiku")
    if items:
        b.row("querylog-pipeline", "distill (real Haiku)", "fixtures", "input_per_entry", tin / items, 1, "haiku")
        b.row("querylog-pipeline", "distill (real Haiku)", "fixtures", "out_per_entry", tout / items, 1, "haiku")
        b.row("querylog-pipeline", "distill (real Haiku)", "fixtures", "cost", sum(c["cost"] or 0 for c in calls), 1, "haiku")
    b.row("querylog-pipeline", "distill (real Haiku)", "fixtures", "entries_written",
          _store_counts(data / "querylog" / "store"), 1, "haiku")


def _logged(log):
    """The calls a logging shim recorded, each counted in the run's spend."""
    calls = [json.loads(ln) for ln in Path(log).read_text(encoding="utf-8").splitlines()] if Path(log).exists() else []
    for c in calls:
        u = c.get("usage") or {}
        spent(c.get("cost"), u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
              + u.get("cache_read_input_tokens", 0), u.get("output_tokens", 0))
    return calls


def s_redaction(b):
    """Redaction speed: the rules and the leak scan over the fixture texts, the public-root allowlist's load."""
    import redact, kbcommon, ql_base
    b.row("redaction", "pipeline version", "rules", "PIPELINE_VERSION", ql_base.PIPELINE_VERSION, 1)
    t = time.perf_counter()
    k = redact.known()
    b.row("redaction", "allowlist load (known())", "rules", "s", time.perf_counter() - t, 1)
    texts = []
    for f in (FIXTURES / "spool").glob("*.jsonl"):
        for ln in f.read_text(encoding="utf-8").splitlines():
            r = json.loads(ln)
            texts += [str(r[x]) for x in ("prompt", "answer", "question") if r.get(x)]
    for lk in json.loads((FIXTURES / "e2e.json").read_text(encoding="utf-8"))["lookups"].values():
        texts += [lk.get("prompt", ""), lk.get("answer", "")]
    texts = [x for x in texts if x]
    per = []
    for x in texts * 20:
        t0 = time.perf_counter()
        redact.redact(x, k)
        per.append(time.perf_counter() - t0)
    chars = sum(len(x) for x in texts) * 20
    b.row("redaction", "redact()", "rules", "median_us", statistics.median(per) * 1e6, len(per), note=f"{len(texts)} texts x 20")
    b.row("redaction", "redact()", "rules", "chars_per_s", chars / sum(per), len(per))
    t0 = time.perf_counter()
    for x in texts * 20:
        kbcommon.leak_hits(x)
    b.row("redaction", "leak scan", "rules", "chars_per_s", chars / (time.perf_counter() - t0), len(texts) * 20)


RESEARCH_ENTRY = {  # a judged miss the kb's LAPS article leads for but does not answer (the e2e fixture's `gap` lookup)
    "id": "66666666-0000-4000-8000-000000000001", "surface": "prompt", "day": "2026-09-28", "tools": ["kb_pack"],
    "question": "Can Windows LAPS back up the password of a Windows Server 2016 member server to Azure?",
    "verdict": "weak", "articles": ["public/windows/laps.md"],
    "summary": "The kb does not say whether Windows Server 2016 is supported.", "judged": "missed"}


def s_research(b):
    """Research cost per accepted fact: learn and apply on a one-entry store (a gap in the LAPS article's topic) in a
    throwaway clone with research on
    (one run a day), mode `local` and a local bare origin; the Sonnet run through a shim that logs its usage."""
    clone = b.clone("kb-research", "local")
    (clone / "_private" / "querylog.json").write_text(json.dumps({"mode": "local", "research": True, "research_daily": 1})
                                                      + "\n", encoding="utf-8")
    store = b.scratch / "research-store"
    shutil.rmtree(store, ignore_errors=True)
    (store / "2026-09").mkdir(parents=True)
    head = {"run": "20260928T120000Z-0000cafe", "pipeline": 2, "retrieval": 4, "kb_commit": "0" * 40,
            "counts": {"entries": 1, "dropped": 0, "waiting": 0}}
    (store / "2026-09" / (head["run"] + ".jsonl")).write_text(json.dumps(head) + "\n" + json.dumps(RESEARCH_ENTRY) + "\n",
                                                             encoding="utf-8", newline="\n")
    log = b.scratch / "research-usage.jsonl"
    log.unlink(missing_ok=True)
    sd = shim_dir(b.scratch / "log-shim", log)
    env = no_plugin_env({"PATH": f"{sd}{os.pathsep}{os.environ.get('PATH', '')}"})
    ql = [sys.executable, str(clone / "_tools" / "querylog.py")]
    subprocess.run(ql + ["learn", "--store", str(store)], cwd=clone, capture_output=True, env=env)
    t = time.perf_counter()
    p = subprocess.run(ql + ["apply", "--store", str(store), "--clone", str(clone)], cwd=clone, capture_output=True,
                       text=True, env=env)
    b.row("research", "apply with research", "sonnet", "s", time.perf_counter() - t, 1, note=p.stdout.strip()[-120:])
    calls = _logged(log)
    cost = sum(c["cost"] or 0 for c in calls)
    diff = git("diff", "--unified=0", "--", "kb/public", cwd=clone)
    facts = len([ln for ln in diff.splitlines() if ln.startswith("+- ") and re.search(r"\[(DOC|COMMUNITY) ", ln)])
    conflicts = len([ln for ln in git("diff", "--unified=0", "--", "kb/public/_conflicts.md", cwd=clone).splitlines()
                     if ln.startswith("+") and not ln.startswith("+++")])
    gaps = len([ln for ln in git("diff", "--unified=0", "--", "kb/public/_gaps.md", cwd=clone).splitlines()
                if ln.startswith("+") and not ln.startswith("+++")])
    b.row("research", "apply with research", "sonnet", "gap_lines", gaps, 1)
    b.row("research", "apply with research", "sonnet", "research_runs", len(calls), 1)
    b.row("research", "apply with research", "sonnet", "cost", cost, 1)
    b.row("research", "apply with research", "sonnet", "facts_accepted", facts, 1)
    b.row("research", "apply with research", "sonnet", "conflict_lines", conflicts, 1)
    if facts:
        b.row("research", "apply with research", "sonnet", "cost_per_fact", cost / facts, 1)
    u = [c["usage"] or {} for c in calls]
    b.row("research", "apply with research", "sonnet", "input", sum(x.get("input_tokens", 0) + x.get(
        "cache_creation_input_tokens", 0) + x.get("cache_read_input_tokens", 0) for x in u), 1)
    git("checkout", "-q", "--", ".", cwd=clone)
