"""The benchmarks' harness: the results file, the isolation of a run (throwaway clones, plugin copies, a `claude` shim),
the `Bench` a run is, the paid-run spend and the reading of a session's transcript (stdlib only).

benchmarks.py runs the scenarios on this; bench_report.py holds the report tables, and bench_lookup.py,
bench_retrieval.py, bench_querylog.py and bench_install.py the scenarios. This module imports none of them,
and benchmarks.py, the facade, holds the command line (kb/_self/code.md, Layout and Imports; the commands and the
scenarios are described in kb/_self/reports/benchmarks.md).
"""
import csv, datetime, io, json, os, re, shutil, statistics, subprocess, sys, threading, time, uuid
from pathlib import Path

import agent_bench
from kbcommon import NO_HOOKS

HOME = Path(__file__).resolve().parent.parent
TOOLS = Path(__file__).resolve().parent

RESULTS = HOME / "kb" / "_self" / "reports" / "benchmarks.csv"
FIELDS = ["scenario", "record", "date", "commit", "claude_code", "kb_topics", "case", "arm", "model", "metric", "value",
          "runs", "note"]
# list prices per MTok of each pinned model, from the pricing page (PRICE_SOURCE): one tier per prompt length, each
# (largest prompt in tokens it covers, None for the last, input, output, 5-minute cache write, cache read); a
# run's cost and its effective input weights read the tier each request's prompt falls in. Plus $0.01 per web search
# (the method of the subagent measurement). Each row's kb fact, all [DOC S2131]:
PRICE_SOURCE = "S2131"
PRICE = {
    "claude-haiku-4-5": ((None, 1.0, 5.0, 1.25, 0.10),),  # kb/public/claude/ci-and-headless.md:87
    "claude-haiku-5-5": ((100_000, 0.10, 0.50, 0.125, 0.01),  # kb/public/claude/ci-and-headless.md:90
                         (None, 0.50, 2.50, 0.625, 0.05)),
    "claude-sonnet-5": ((None, 2.0, 10.0, 2.5, 0.20),),  # kb/public/claude/ci-and-headless.md:89
    "claude-sonnet-5-5": ((None, 2.0, 10.0, 2.5, 0.10),),  # kb/public/claude/ci-and-headless.md:87
    "claude-opus-5-5": ((None, 4.0, 20.0, 5.0, 0.20),),  # kb/public/claude/ci-and-headless.md:88
}
# the alias arms of a run and the model each names from a Claude Code version on; a run's own transcript names the model
# it used, and that wins: this table only prices a run that reports none. The versions' kb facts: haiku from 2.1.293
# kb/public/claude/ci-and-headless.md:85 [DOC S-ezqg74ki], sonnet from 2.1.284 kb/public/claude/ci-and-headless.md:86
# [DOC S1864]
ARMS = ("haiku", "sonnet", "opus")
ALIAS = {"haiku": (((0,), "claude-haiku-4-5"), ((2, 1, 293), "claude-haiku-5-5")),
         "sonnet": (((0,), "claude-sonnet-5"), ((2, 1, 284), "claude-sonnet-5-5")),
         "opus": (((0,), "claude-opus-5-5"),)}
WEB_SEARCH_USD = 0.01

# ---------------------------------------------------------------------------------------------------- results file


def read_rows(path=None):
    path = path or RESULTS
    if not Path(path).exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_rows(rows, path=None):
    path = path or RESULTS
    buf = io.StringIO()
    w = csv.DictWriter(buf, FIELDS, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") for k in FIELDS})
    Path(path).write_text(buf.getvalue(), encoding="utf-8", newline="\n")


ARMED = ("navigation",)  # scenarios whose run names one arm (--arm): a run replaces only its own arm's rows
SLOTTED = ARMED + ("pool",)  # scenarios whose rows a same-day run replaces by arm; the pool's arms are its --arms


def _slot(r):
    return r["scenario"], r["record"], r["arm"] if r["scenario"] in SLOTTED else ""


def merge_rows(old, new):
    """The results with `new` in place of every row of the same scenario and record (and, for a SLOTTED scenario, arm)."""
    keys = {_slot(r) for r in new}
    return [r for r in old if _slot(r) not in keys] + new


# ---------------------------------------------------------------------------------------------------- isolation


def git(*args, cwd, check=True):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
                          check=check).stdout.strip()


def isolate(clone, mode, bare):
    """Make `clone` safe to run hooks and pipeline commands in: its query log mode (`off` or `local`) in
    _private/querylog.json, its origin the local bare repository `bare`, research off."""
    priv = Path(clone) / "_private"
    priv.mkdir(exist_ok=True)
    (priv / "querylog.json").write_text(json.dumps({"mode": mode, "research": False}) + "\n", encoding="utf-8",
                                        newline="\n")
    git("remote", "set-url", "origin", str(bare), cwd=clone)


def throwaway_clone(dest, mode, rev="HEAD"):
    """A clone of this repository at `rev` under `dest`, isolated (isolate) with a bare origin beside it."""
    dest = Path(dest)
    bare = dest.with_name(dest.name + "-origin.git")
    for d in (dest, bare):
        shutil.rmtree(d, ignore_errors=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    git("clone", "-q", "--bare", str(HOME), str(bare), cwd=dest.parent)
    git("clone", "-q", str(bare), str(dest), cwd=dest.parent)
    if rev != "HEAD":
        git("checkout", "-q", "--detach", rev, cwd=dest)
    isolate(dest, mode, bare)
    return dest


def plugin_copy(src, dest, data):
    """A copy of the plugin at `src` whose hook commands write the query log under `data` (mode `local`) instead of
    the ${CLAUDE_PLUGIN_DATA} Claude Code gives a plugin loaded with --plugin-dir (~/.claude/plugins/data/<name>-inline):
    each command starts with CLAUDE_PLUGIN_DATA='<data>'. The texts that load into a session are unchanged."""
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns(".git", "_cache", "_private"))
    manifest = Path(dest) / ".claude-plugin" / "plugin.json"
    spec = json.loads(manifest.read_text(encoding="utf-8"))
    for groups in spec.get("hooks", {}).values():
        for g in groups:
            for h in g["hooks"]:
                h["command"] = f"CLAUDE_PLUGIN_DATA='{data}' " + h["command"]
    manifest.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8", newline="\n")
    q = Path(data) / "querylog"
    q.mkdir(parents=True, exist_ok=True)
    (q / "config.json").write_text(json.dumps({"mode": "local", "research": False}) + "\n", encoding="utf-8", newline="\n")
    return Path(dest)


SHIM = """#!/usr/bin/env python3
# a `claude` that runs the real one with --output-format json, logs the result event (usage, cost) to LOG and prints
# the answer text, as `claude -p` without that flag would
import json, subprocess, sys
REAL, LOG = {real!r}, {log!r}
args = [a for a in sys.argv[1:]]
if "--output-format" in args:
    i = args.index("--output-format"); del args[i:i + 2]
data = sys.stdin.read()
p = subprocess.run([REAL, *args, "--output-format", "json"], input=data, capture_output=True, text=True)
try:
    ev = json.loads(p.stdout)
except ValueError:
    sys.stderr.write(p.stderr); sys.exit(p.returncode or 1)
items = data.count('{{"i": ')
with open(LOG, "a", encoding="utf-8") as f:
    f.write(json.dumps({{"argv": args[:6], "items": items, "usage": ev.get("usage"), "cost": ev.get("total_cost_usd"),
                        "duration_ms": ev.get("duration_ms"), "is_error": ev.get("is_error")}}) + "\\n")
sys.stdout.write(ev.get("result") or "")
sys.exit(1 if ev.get("is_error") else p.returncode)
"""

FAIL_SHIM = "#!/bin/sh\n# a `claude` that fails at once: a launched distill finds no model and its entries wait\nexit 1\n"


def shim_dir(where, log=None, real=None):
    """A directory holding a `claude` for PATH: the logging shim (log given; it runs `real`, default the `claude` on
    PATH now) or one that always fails. On Windows it also holds a `claude.cmd` that does the same: Windows resolves a
    command only by a PATHEXT extension (shutil.which, CreateProcess), so the extensionless script alone is skipped
    and the real `claude` further down PATH would run instead; the extensionless one stays for Git Bash."""
    d = Path(where)
    d.mkdir(parents=True, exist_ok=True)
    exe = d / "claude"
    real = real or shutil.which("claude") or "claude"
    exe.write_text(SHIM.format(real=real, log=str(log)) if log else FAIL_SHIM, encoding="utf-8", newline="\n")
    exe.chmod(0o755)
    if os.name == "nt":
        run = f'@"{sys.executable}" "{exe}" %*\r\n@exit /b %ERRORLEVEL%\r\n' if log else "@exit /b 1\r\n"
        (d / "claude.cmd").write_text(run, encoding="utf-8", newline="")
    return d


class Skip(Exception):
    """A scenario that cannot run on this host; main prints the reason and writes no rows for it."""


def need_sh():
    """The `sh` the hook launcher scenarios start `_tools/kbpy` with, or Skip: PowerShell or cmd on Windows has no sh
    on PATH unless Git for Windows' usr/bin is there."""
    sh = shutil.which("sh")
    if not sh:
        raise Skip("no sh on PATH (Windows without Git Bash): run it from Git Bash")
    return sh


def no_plugin_env(extra=None):
    """This process's environment without plugin, project or bench variables, plus `extra`."""
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PLUGIN_ROOT", "CLAUDE_PLUGIN_DATA",
                                                             "CLAUDE_PROJECT_DIR", "BENCH_SCRATCH", "KB_INDEX")}
    env.update(extra or {})
    return env


# ---------------------------------------------------------------------------------------------------- a run


def today():
    """The UTC date a run starts on."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


class Bench:
    """One `run`: the record's identity (date, commit, Claude Code version, kb size), the scratch directory and its
    clones, and the rows written so far. The date is read once, here, and stamps every row and every file name of the
    run, so a run that crosses midnight stays one record."""

    def __init__(self, scratch, reps):
        self.scratch, self.reps = Path(scratch), reps
        self.scratch.mkdir(parents=True, exist_ok=True)
        self.date = today()
        self.record = self.date
        self.status = 0  # the exit code a scenario asks for (1: `pool` stopped at its --max-usd)
        self.commit = git("rev-parse", "--short=7", "HEAD", cwd=HOME)
        self.cc = (subprocess.run(["claude", "--version"], capture_output=True, text=True).stdout.split() or ["?"])[0]
        import kbfacts
        self.topics = str(len(kbfacts.articles()))
        self.rows, self._clones, self.registered = [], {}, []
        self.arm = ""  # the arm of an ARMED scenario's rows (run --arm)

    def row(self, scenario, case, arm, metric, value, runs="", model="", note=""):
        if isinstance(value, float):
            value = round(value, 6)
        self.rows.append({"scenario": scenario, "record": self.record, "date": self.date, "commit": self.commit,
                          "claude_code": self.cc, "kb_topics": self.topics, "case": case, "arm": arm, "model": model,
                          "metric": metric, "value": value, "runs": runs, "note": note})

    def clone(self, name, mode="off", rev="HEAD", register=False):
        """A throwaway clone (built once per run); `register` adds the kb and docs servers at local scope for it."""
        if name not in self._clones:
            c = throwaway_clone(self.scratch / name, mode, rev)
            subprocess.run([sys.executable, "_tools/rag.py", "pack", "warm the index"], cwd=c, capture_output=True,
                           env=no_plugin_env())
            if register:
                subprocess.run([sys.executable, "_tools/kb_mcp.py", "--register-local"], cwd=c, capture_output=True,
                               env=no_plugin_env())
                self.registered.append(c)
            self._clones[name] = c
        return self._clones[name]

    def lookup(self):
        """The clone the lookup scenarios run in: HEAD, query log off, servers registered for it."""
        return self.clone("kb", "off", register=True)

    def close(self):
        for c in self.registered:
            for name in ("kb", "microsoft-learn", "claude-code-docs", "mcp-docs"):
                subprocess.run(["claude", "mcp", "remove", "--scope", "local", name], cwd=c, capture_output=True)

    # -- model runs through agent_bench.py in the lookup clone

    def bench(self, cfgs, scens, reps, tag, parallel=False):
        """agent_bench.py runs in the lookup clone; `parallel` runs each config in its own process at once."""
        clone = self.lookup()
        groups = [[c] for c in cfgs] if parallel else [cfgs]
        outs, procs = [], []
        for g in groups:
            out = self.scratch / "raw" / f"{tag}-{self.date}-{uuid.uuid4().hex[:6]}.jsonl"
            out.parent.mkdir(parents=True, exist_ok=True)
            outs.append(out)
            procs.append(subprocess.Popen([sys.executable, str(clone / "_tools" / "agent_bench.py"), str(out),
                                           ",".join(g), ",".join(scens), str(reps)], cwd=clone, env=no_plugin_env(),
                                          stdout=subprocess.DEVNULL))
            if not parallel:
                procs[-1].wait()
        for pr in procs:
            pr.wait()
        runs = [json.loads(ln) for out in outs if out.exists()
                for ln in out.read_text(encoding="utf-8").splitlines() if ln.strip()]
        for r in runs:
            spent_run(r)
        return runs

    def bench_rows(self, scenario, runs, arm_of=lambda r: r["cfg"]):
        """Rows per case and arm from agent_bench runs: means of cost, time, input, output, turns and tool calls, the
        checks passed over all runs, the route of the first run, and the errors."""
        groups = {}
        for r in runs:
            groups.setdefault((r["scen"], arm_of(r)), []).append(r)
        for (scen, arm), rs in groups.items():
            ok = [r for r in rs if "error" not in r]
            if len(ok) < len(rs):
                self.row(scenario, scen, arm, "errors", len(rs) - len(ok), len(rs), note=rs[0].get("error", "")[:80]
                         if not ok else "")
            if not ok:
                continue
            model = max(ok[0].get("models") or {"": 0}, key=lambda m: ok[0]["models"].get(m, 0))
            n = len(ok)
            mean = lambda f: sum(f(r) for r in ok) / n  # noqa: E731
            self.row(scenario, scen, arm, "cost", mean(lambda r: r["cost"]), n, model)
            self.row(scenario, scen, arm, "wall_s", mean(lambda r: r["wall_s"]), n, model)
            self.row(scenario, scen, arm, "input", mean(lambda r: r["in_uncached"] + r["cache_write"] + r["cache_read"]),
                     n, model)
            self.row(scenario, scen, arm, "out", mean(lambda r: r["out"]), n, model)
            self.row(scenario, scen, arm, "turns", mean(lambda r: r["turns"]), n, model)
            self.row(scenario, scen, arm, "tool_calls", mean(lambda r: sum(r.get("tools", {}).values())), n, model)
            passed = sum(sum(bool(c) for c in r.get("checks") or []) for r in ok)
            total = sum(len(r.get("checks") or []) for r in ok)
            self.row(scenario, scen, arm, "checks", f"{passed}/{total}", n, model)
            self.row(scenario, scen, arm, "route", " > ".join(ok[0].get("route", [])) or "no tool call", n, model)


SPEND = {"usd": 0.0, "input": 0, "out": 0, "runs": 0}  # every paid run of this process
SPEND_LOCK = threading.Lock()  # runs of a parallel scenario (`pool --jobs`) add to SPEND from their own threads
RAW = {}  # the file a scenario's own stream runs are appended to


def spent(cost, inp, out):
    with SPEND_LOCK:
        SPEND["usd"] += cost or 0
        SPEND["input"] += inp or 0
        SPEND["out"] += out or 0
        SPEND["runs"] += 1


def spent_usd():
    with SPEND_LOCK:
        return SPEND["usd"]


def claude_json(argv, prompt, cwd, env=None, timeout=900):
    """One `claude -p ... --output-format json` run: its result event with `input` (uncached + cache write + cache
    read) and `wall_s`, or {"error": ...}."""
    t = time.time()
    p = subprocess.run(argv + ["--output-format", "json"], input=prompt, cwd=str(cwd), capture_output=True, text=True,
                       encoding="utf-8", env=env or no_plugin_env(), timeout=timeout)
    try:
        ev = json.loads(p.stdout)
    except ValueError:
        return {"error": (p.stderr or p.stdout)[-300:]}
    if ev.get("is_error"):
        return {"error": str(ev.get("result"))[:200]}
    u = ev.get("usage") or {}
    ev["input"] = u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
    ev["wall_s"] = round(time.time() - t, 1)
    spent(ev.get("total_cost_usd"), ev["input"], u.get("output_tokens", 0))
    return ev


def stream_run(argv, prompt, cwd, env=None):
    """One stream-json run parsed as agent_bench does (cost, tokens, tool calls, route, answer)."""
    r = agent_bench.execute(argv, prompt, cwd=str(cwd), env=env)
    spent_run(r)
    if RAW.get("path"):  # every run's parsed stream, for checking a row against its source
        with open(RAW["path"], "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps({"prompt": prompt[:300], **r}) + "\n")
    return r


def spent_run(r):
    if "error" not in r:
        spent(r["cost"], r["in_uncached"] + r["cache_write"] + r["cache_read"], r["out"])


def transcript(session_id):
    """[(requests of the main session), {agent file: requests}] of a persisted session; a request is one API call
    (the last line of each requestId) with its usage, time, tool calls and text."""
    base = Path.home() / ".claude" / "projects"
    hits = list(base.glob(f"*/{session_id}.jsonl"))
    if not hits:
        return [], {}
    main = read_requests(hits[0])
    subs = {p.name: read_requests(p) for p in sorted((hits[0].parent / session_id / "subagents").glob("agent-*.jsonl"))}
    return main, subs


def read_requests(path):
    reqs, results = {}, 0
    for ln in Path(path).read_text(encoding="utf-8").splitlines():
        try:
            ev = json.loads(ln)
        except ValueError:
            continue
        msg = ev.get("message") if isinstance(ev.get("message"), dict) else {}
        if ev.get("type") == "user":
            for c in msg.get("content", []) if isinstance(msg.get("content"), list) else []:
                if isinstance(c, dict) and c.get("type") == "tool_result":
                    body = c.get("content")
                    results += len(body if isinstance(body, str) else json.dumps(body))
        if ev.get("type") != "assistant" or not msg.get("usage"):
            continue
        rid = ev.get("requestId") or msg.get("id")
        r = reqs.setdefault(rid, {"usage": msg["usage"], "ts": ev.get("timestamp"), "tools": [], "text": "",
                                  "model": msg.get("model", "")})
        r["usage"] = msg["usage"]
        for c in msg.get("content", []):
            if c.get("type") == "tool_use":
                r["tools"].append(c["name"])
            elif c.get("type") == "text":
                r["text"] += c.get("text", "")
    out = list(reqs.values())
    if out:
        out[-1]["tool_result_chars"] = results
    return out


def pinned(name):
    """The pinned model id of a name a run reports: no date suffix, no context-window marker."""
    return re.sub(r"-\d{8}$", "", name.split("[")[0])


def resolve_model(name, observed="", cc=""):
    """The pinned id a run is priced at: the model its transcript reports, else what the alias `name` names on Claude
    Code version `cc`, else `name` itself. A version that is empty or unknown (`?`) names the alias's first model."""
    if observed:
        return pinned(observed)
    if name in ALIAS:
        ver = tuple(int(n) for n in re.findall(r"\d+", cc)[:3])
        return next(m for since, m in reversed(ALIAS[name]) if since <= ver) if ver else ALIAS[name][0][1]
    return pinned(name)


def tier_of(model, prompt):
    """The index of the price tier of `model` that a request of `prompt` input tokens falls in."""
    return next(i for i, t in enumerate(PRICE[model]) if t[0] is None or prompt <= t[0])


def tier_label(model, i):
    """What a run records of tier `i` of `model`: empty for a model with one price, else its prompt range."""
    tiers = PRICE[model]
    if len(tiers) == 1:
        return ""
    return f"<={tiers[i][0] // 1000}k" if tiers[i][0] else f">{tiers[i - 1][0] // 1000}k"


def usage_sum(reqs, model="", cc=""):
    """Token sums of a run's requests, priced as `model` (an alias or a pinned id) resolves on the run (resolve_model):
    the model, the tokens of each of its price tiers, the highest tier reached (`tier`) and the effective input, which
    weights a cache write 2x and a cache read by the model's read price over its input price."""
    u = lambda r, k: r["usage"].get(k, 0) or 0  # noqa: E731
    mid = resolve_model(model, next((r["model"] for r in reqs if r.get("model")), ""), cc)
    if mid not in PRICE:
        raise KeyError(f"no price for model {mid!r}: add it to bench_core.PRICE")
    by_tier, top = [dict(uncached=0, cache_write=0, cache_read=0, out=0) for _ in PRICE[mid]], 0
    for r in reqs:
        i = tier_of(mid, u(r, "input_tokens") + u(r, "cache_creation_input_tokens") + u(r, "cache_read_input_tokens"))
        top = max(top, i)
        for k, f in (("uncached", "input_tokens"), ("cache_write", "cache_creation_input_tokens"),
                     ("cache_read", "cache_read_input_tokens"), ("out", "output_tokens")):
            by_tier[i][k] += u(r, f)
    unc, cw, cr = (sum(t[k] for t in by_tier) for k in ("uncached", "cache_write", "cache_read"))
    return {"model": mid, "tier": tier_label(mid, top), "by_tier": by_tier,
            "uncached": unc, "cache_write": cw, "cache_read": cr, "input": unc + cw + cr,
            "out": sum(t["out"] for t in by_tier), "requests": len(reqs),
            "start_ctx": (u(reqs[0], "input_tokens") + u(reqs[0], "cache_creation_input_tokens")
                          + u(reqs[0], "cache_read_input_tokens")) if reqs else 0,
            "effective": sum(t["uncached"] + 2 * t["cache_write"] + round(p[4] / p[1], 6) * t["cache_read"]
                             for t, p in zip(by_tier, PRICE[mid]))}


def prompt_tokens(usage):
    """The whole prompt of one request's `usage`: uncached input + cache write + cache read."""
    return sum(usage.get(k, 0) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))


def run_tokens(r, name="", cc=""):
    """The token fields of one run `r` (agent_bench.result_of's fields, or any run with a `requests` list of {model,
    usage}), from its own requests: input, its cache split, the effective input (each model's requests weighted by that
    model's own prices, usage_sum), the first request's prompt (`start_ctx`), the models and the highest price tier
    reached. The output is the run's own `out` (agent_bench.result_of: its result event's count, which a stream's
    per-message usage, a partial count, undercuts) and only a run with no `out` sums its requests'. A run with no requests (a tool's answer, a hook)
    is all zeros. `name` prices a request that reports no model, as the alias resolves on the run's Claude Code version
    `cc`."""
    reqs = r.get("requests") or []
    out = {"input": 0, "uncached": 0, "cache_read": 0, "cache_write": 0, "effective_input": 0.0, "out": 0, "start_ctx": 0,
           "models": [], "tier": ""}
    groups = {}
    for q in reqs:
        groups.setdefault(q.get("model") or name, []).append(q)
    for model, rs in groups.items():
        s = usage_sum(rs, model, cc)
        for k, f in (("input", "input"), ("uncached", "uncached"), ("cache_read", "cache_read"),
                     ("cache_write", "cache_write"), ("out", "out"), ("effective_input", "effective")):
            out[k] += s[f]
        out["models"].append(s["model"])
        out["tier"] = max(out["tier"], s["tier"])
    if reqs:
        out["start_ctx"] = prompt_tokens(reqs[0]["usage"])
        if r.get("out") is not None:
            out["out"] = r["out"]
    return out


def est_cost(s, searches=0):
    """The list-price cost of a usage_sum run: each tier's tokens at that tier's prices."""
    return sum(t["uncached"] * p[1] + t["cache_write"] * p[3] + t["cache_read"] * p[4] + t["out"] * p[2]
               for t, p in zip(s["by_tier"], PRICE[s["model"]])) / 1e6 + searches * WEB_SEARCH_USD


def span_s(reqs):
    ts = [datetime.datetime.fromisoformat(r["ts"].replace("Z", "+00:00")) for r in reqs if r.get("ts")]
    return (max(ts) - min(ts)).total_seconds() if len(ts) > 1 else 0.0


def subagent(b, cwd, parent_model, agents, name, task, allowed, extra=(), env=None):
    """A parent `claude -p` (hooks off, session kept) that hands `task` to the agent `name` defined by `agents`; the
    agent's requests are read from the session's subagent transcript."""
    sid = str(uuid.uuid4())
    prompt = (f"Use the Agent tool once, with subagent_type {name}, and give it exactly this task: {task}\n"
              "Then reply with the agent's answer, unchanged.")
    argv = ["claude", "-p", "--model", parent_model, "--session-id", sid, *NO_HOOKS, "--agents", json.dumps(agents),
            "--allowedTools", "Agent", *allowed, *extra]
    ev = claude_json(argv, prompt, cwd, env=env)
    main, subs = transcript(sid)
    reqs = next(iter(subs.values()), [])
    return ev, reqs


# ---------------------------------------------------------------------------------------------------- shared by the scenarios

OK_PROMPT = "Reply with the single word ok."


def task_argv(model, extra=()):
    """The `claude -p` a task run starts: stream output, hooks off, no saved session."""
    return ["claude", "-p", "--output-format", "stream-json", "--verbose", "--no-session-persistence", *NO_HOOKS,
            "--model", model, *extra]


def time_runs(argv, n, cwd, env=None, stdin=None):
    """The seconds of `n` runs of `argv`."""
    out = []
    for _ in range(n):
        t = time.perf_counter()
        subprocess.run(argv, cwd=str(cwd), input=stdin, capture_output=True, text=True, encoding="utf-8",
                       env=env or no_plugin_env())
        out.append(time.perf_counter() - t)
    return out


def stat_rows(b, scenario, case, arm, secs, note="", time_s=False):
    """The rows of a timing: the median and the 95th percentile in ms, and with `time_s` the median in seconds."""
    ms = sorted(s * 1000 for s in secs)
    if time_s:  # the median in seconds too, as the tool-speed history gives it
        b.row(scenario, case, arm, "time", statistics.median(secs), len(ms), note=note)
    b.row(scenario, case, arm, "median_ms", statistics.median(ms), len(ms), note=note)
    b.row(scenario, case, arm, "p95_ms", ms[max(0, int(round(0.95 * len(ms))) - 1)], len(ms), note=note)


MCP_CALLS = [("kb_pack", {"question": "default Windows LAPS password length"}), ("kb_search", {"query": "gMSA"}),
             ("kb_audit", {"prefix": "intune"}), ("kb_facts", {"prefix": "auth/kerberos"}),
             ("kb_source", {"id": "S1216", "cited": True}), ("kb_status", {}),
             ("kb_pack", {"questions": ["LAPS password length", "Delivery Optimization port"]}),
             ("kb_topics_for", {"paths": ["src/adminservice.ts"], "keywords": "AdminService Kerberos"}),
             ("kb_show", {"path": "public/windows/laps.md:1"}), ("kb_search", {"query": "sp_getapplock"}),
             ("kb_audit", {"prefix": "agents", "entries": True}), ("kb_pack", {"question": "Intune remediations limits"})]


def mcp_session(clone, calls=MCP_CALLS):
    """The kb server over stdio: initialize, then each call; returns (seconds to the initialize reply, total seconds,
    the tool results' texts)."""
    msgs = [{"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2025-06-18",
            "capabilities": {}, "clientInfo": {"name": "bench", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"}]
    msgs += [{"jsonrpc": "2.0", "id": i + 1, "method": "tools/call", "params": {"name": n, "arguments": a}}
             for i, (n, a) in enumerate(calls)]
    t = time.perf_counter()
    p = subprocess.Popen([sys.executable, str(Path(clone) / "_tools" / "kb_mcp.py")], cwd=str(clone), stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, text=True, encoding="utf-8", env=no_plugin_env())
    p.stdin.write(json.dumps(msgs[0]) + "\n")
    p.stdin.flush()
    first = p.stdout.readline()
    t_init = time.perf_counter() - t
    texts = []
    for m in msgs[1:]:
        p.stdin.write(json.dumps(m) + "\n")
        p.stdin.flush()
        if "id" in m:
            reply = json.loads(p.stdout.readline())
            texts.append(" ".join(c.get("text", "") for c in (reply.get("result") or {}).get("content", [])))
    p.stdin.close()
    p.wait(timeout=60)
    return t_init, time.perf_counter() - t, [first] + texts
