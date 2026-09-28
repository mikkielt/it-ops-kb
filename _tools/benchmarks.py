#!/usr/bin/env python3
"""The kb's benchmarks: every measurement of kb/_self/reports/benchmarks.md, run again by one command (stdlib only).

  benchmarks.py list                        the scenarios, each with its report section
  benchmarks.py run [SCENARIO ...] [--reps N] [--out FILE]
                                            run every scenario, or the named ones, and write their rows to the results
                                            file (kb/_self/reports/benchmarks.csv; rows of the same scenario and date
                                            are replaced), or to FILE; prints each scenario's rows and the spend
  benchmarks.py report [--check]            write the report's generated tables from the results file; --check writes
                                            nothing and exits 1 when a table, or a number in README.md, disagrees with
                                            the results file

The results file has one row per scenario, record, case, arm and metric: `record` names one measurement (the date of a
run of this tool, or the commit of a historical number taken from the reports it replaced), with its date, commit,
Claude Code version and kb size (topics). The report's tables sit between `<!-- bench:table SCENARIO metrics=... -->`
and `<!-- /bench -->` (a cell is each record's value in date order and the change of the newest from the one before),
and its records tables between `<!-- bench:records SCENARIO -->` and `<!-- /bench -->`.

Isolation: model runs start `claude -p` with hooks off (querylog.NO_HOOKS) from a throwaway clone of HEAD under the
scratch directory (BENCH_SCRATCH, default <temp>/it-ops-kb-bench) whose query log is `off` and whose origin is a local
bare repository; the scenarios that measure the query log's hooks run them in a throwaway clone in mode `local` with a
local bare origin, or as a plugin copy whose hooks write under the scratch directory. Nothing a run does reaches this
clone's spool, a plugin data directory of ~/.claude or a real remote. A clone gets the servers of `kb_mcp.py
--register-local` for its own path; they are removed at the end of the run.

Paid scenarios (each a `claude -p` per case): headless, subagents, models, router, howto, partial, files-subagents,
files-headless, host-lookups, always-on, kb-lookup-agent, retrieval and doc2query (their blind questions), research,
ingest, host-roots, querylog-pipeline (one real Haiku batch). The rest run no model.
"""
import argparse, csv, datetime, io, json, os, platform, random, re, shutil, statistics, subprocess, sys, tempfile, time
import uuid
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
HOME = TOOLS.parent
sys.path.insert(0, str(TOOLS))
import agent_bench  # noqa: E402
from querylog import NO_HOOKS  # noqa: E402

RESULTS = HOME / "kb" / "_self" / "reports" / "benchmarks.csv"
REPORT = HOME / "kb" / "_self" / "reports" / "benchmarks.md"
README = HOME / "README.md"
FIELDS = ["scenario", "record", "date", "commit", "claude_code", "kb_topics", "case", "arm", "model", "metric", "value",
          "runs", "note"]
OLD_COMMIT = "19010a8"  # the commit before the evidence pack, audit tools and kb: hook ("Lookup tools against reading files")
# list prices per MTok used to estimate a subagent's cost from its transcript (input, output); cache writes 1.25x input,
# cache reads 0.1x input (Opus 5.5: $0.20), plus $0.01 per web search (the method of the subagent measurement)
PRICE = {"haiku": (1.0, 5.0, 0.1), "sonnet": (2.0, 10.0, 0.2), "opus": (4.0, 20.0, 0.2)}
WEB_SEARCH_USD = 0.01
OK_PROMPT = "Reply with the single word ok."
DOCS_TOOLS = ["mcp__microsoft-learn__microsoft_docs_search", "mcp__microsoft-learn__microsoft_docs_fetch"]
KB_TOOLS = [f"mcp__kb__{t}" for t in ("kb_pack", "kb_show", "kb_search", "kb_facts", "kb_audit", "kb_source", "kb_status")]
# numbers in README.md that are not measurements (names, versions of models, licences, rules, placeholders)
NOT_MEASURED = [r"Haiku 4\.5", r"Sonnet 5", r"Opus 5\.5", r"Apache-2\.0", r"CC BY 4\.0", r"\b25 words", r"PL-LT-00123",
                r"census-YYYY-MM-DD", r"BM25", r"\b1-2 tool calls", r"Python 3\.\d+"]

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


def merge_rows(old, new):
    """The results with `new` in place of every row of the same scenario and record."""
    keys = {(r["scenario"], r["record"]) for r in new}
    return [r for r in old if (r["scenario"], r["record"]) not in keys] + new


# ---------------------------------------------------------------------------------------------------- report tables

NUM = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def numbers(text):
    return [float(m.replace(",", "")) for m in NUM.findall(str(text))]


def num(v):
    """The value as one number: itself, or the mean of the numbers a historical cell holds (`$0.043 / $0.051`, a
    range `9-12 s`); None when it holds none, or several of different kinds (`2/2`)."""
    s = str(v).strip()
    if not s or re.fullmatch(r"\d+/\d+(, \d+/\d+)*", s):
        return None
    try:
        return float(s)
    except ValueError:
        pass
    ns = [abs(n) for n in numbers(re.sub(r"(\d)-(\d)", r"\1 \2", s))]
    return sum(ns) / len(ns) if ns else None


FORMATS = {"cost": "${:.3f}", "cost_est": "${:.3f}", "wall_s": "{:.0f} s", "api_s": "{:.0f} s", "input": "{:.0f}",
           "out": "{:.0f}", "turns": "{:.1f}", "tool_calls": "{:.1f}", "requests": "{:.1f}", "start_ctx": "{:.0f}",
           "ms": "{:.1f} ms", "s": "{:.2f} s", "time": "{:.2f} s", "pct": "{:.1f}%"}


def fmt(metric, v):
    """A value as the tables show it: numbers from a run with the metric's format, anything else as written."""
    s = str(v)
    try:
        x = float(s)
    except ValueError:
        return s
    kind = metric if metric in FORMATS else metric.rsplit("_", 1)[-1]
    f = FORMATS.get(kind)
    if f:
        return f.format(x)
    return f"{x:,.0f}" if x == int(x) and abs(x) >= 1000 else (f"{x:g}")


def change(a, b):
    x, y = num(a), num(b)
    if x is None or y is None or x == 0:
        return ""
    return f" ({(y - x) / x * 100:+.0f}%)"


def records(rows, scenario):
    """The scenario's records in date order (history first when a date ties): [(record, first row)]."""
    seen = {}
    for r in rows:
        if r["scenario"] == scenario and r["record"] not in seen:
            seen[r["record"]] = r
    return sorted(seen.items(), key=lambda kv: (kv[1]["date"], kv[0]))


def table(rows, scenario, metrics, cases=None, arms=None):
    """A Markdown table: one line per case and arm, a column per metric; each cell holds every record's value in date
    order, `->` between them, and the change of the last from the one before."""
    order = [rec for rec, _ in records(rows, scenario)]
    cells, keys = {}, []
    for r in rows:
        if r["scenario"] != scenario or r["metric"] not in metrics:
            continue
        if (cases and r["case"] not in cases) or (arms and r["arm"] not in arms):
            continue
        k = (r["case"], r["arm"])
        if k not in keys:
            keys.append(k)
        cells.setdefault((k, r["metric"]), {})[r["record"]] = r["value"]
    out = ["| case | arm | " + " | ".join(metrics) + " |", "|---|---|" + "---|" * len(metrics)]
    for k in keys:
        line = []
        for m in metrics:
            vals = [(rec, cells.get((k, m), {}).get(rec)) for rec in order]
            vals = [(rec, v) for rec, v in vals if v not in (None, "")]
            text = " -> ".join(fmt(m, v) for _, v in vals)
            if len(vals) >= 2:
                text += change(vals[-2][1], vals[-1][1])
            line.append(text or "-")
        out.append(f"| {k[0] or '-'} | {k[1] or '-'} | " + " | ".join(line) + " |")
    return "\n".join(out)


def records_table(rows, scenario):
    out = ["| record | date | commit | Claude Code | kb topics | runs per cell | spend of the runs |", "|---|---|---|---|---|---|---|"]
    for rec, first in records(rows, scenario):
        mine = [r for r in rows if r["scenario"] == scenario and r["record"] == rec]
        runs = sorted({r["runs"] for r in mine if r["runs"] and r["metric"] != "spend_usd"}, key=lambda x: float(x))
        total = [float(r["value"]) for r in mine if r["metric"] == "spend_usd" and _isnum(r["value"])]
        spend = total[0] if total else sum(float(r["value"]) * float(r["runs"] or 1) for r in mine
                                           if r["metric"] in ("cost", "cost_est") and _isnum(r["value"]))
        out.append(f"| {rec} | {first['date'] or '-'} | {first['commit'] or '-'} | {first['claude_code'] or '-'} | "
                   f"{first['kb_topics'] or '-'} | {', '.join(runs) or '-'} | {('$%.2f' % spend) if spend else '-'} |")
    return "\n".join(out)


def _isnum(v):
    try:
        float(v)
        return True
    except ValueError:
        return False


BLOCK = re.compile(r"(<!-- bench:(table|records|spend)((?: [^\n]*?)?) -->\n)(.*?)(<!-- /bench -->)", re.S)
OPT = re.compile(r"(\w+)=(.*?)(?= \w+=|$)")


def spend_table(rows):
    """Each scenario's spend per record: paid runs, input and output tokens, dollars (its `all paid runs` rows)."""
    got = {}
    for r in rows:
        if r["case"] == "all paid runs":
            got.setdefault((r["scenario"], r["record"]), {"runs": r["runs"]})[r["metric"]] = r["value"]
    out = ["| scenario | record | paid runs | input tokens | output tokens | spend |", "|---|---|---|---|---|---|"]
    tot = [0, 0.0, 0.0, 0.0]
    for (scen, rec), v in sorted(got.items()):
        inp, outp, usd = (float(v.get(k, 0)) for k in ("spend_input_tokens", "spend_output_tokens", "spend_usd"))
        tot = [tot[0] + int(v["runs"] or 0), tot[1] + inp, tot[2] + outp, tot[3] + usd]
        out.append(f"| {scen} | {rec} | {v['runs']} | {inp:,.0f} | {outp:,.0f} | ${usd:.2f} |")
    out.append(f"| all | | {tot[0]} | {tot[1]:,.0f} | {tot[2]:,.0f} | ${tot[3]:.2f} |")
    return "\n".join(out)


def render(text, rows):
    """The report text with every generated block rewritten from `rows`."""
    def one(m):
        kind, rest = m.group(2), m.group(3).strip()
        scen, _, rest = rest.partition(" ")
        opts = dict(OPT.findall(rest))
        if kind == "spend":
            body = spend_table(rows)
        elif kind == "records":
            body = records_table(rows, scen)
        else:
            split = lambda k: opts[k].split(",") if k in opts else None  # noqa: E731
            body = table(rows, scen, split("metrics"), split("cases"), split("arms"))
        return m.group(1) + body + "\n" + m.group(5)
    return BLOCK.sub(one, text)


def readme_misses(text, rows):
    """Numbers in `text` (README.md) that match no row of the results file at the precision and unit written: a
    value, a Claude Code version, a kb size, a run count or a number inside a row's text."""
    for pat in NOT_MEASURED:
        text = re.sub(pat, " ", text)
    text = re.sub(r"`[^`]*`|\(https?://[^)]*\)|kb/_self/\S+", " ", text)  # code, links and paths hold no measurements
    pool = []
    for r in rows:
        for k in ("value", "claude_code", "kb_topics", "runs", "note"):
            pool += numbers(r[k]) if k != "value" or not _isnum(r[k]) else [float(r[k])]
    pool = sorted(set(pool))
    versions = {r["claude_code"] for r in rows}
    misses = []
    for m in re.finditer(r"(\$?)(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)*)(k|x| ?%)?", text):
        raw, unit = m.group(2), (m.group(3) or "").strip()
        if raw.count(".") > 1:
            if raw not in versions:
                misses.append(m.group(0))
            continue
        if raw in ("0", "1", "2") and not unit and not m.group(1):
            continue  # counting words written as digits ("1-2 tool calls")
        n = float(raw.replace(",", ""))
        dec = len(raw.split(".")[1]) if "." in raw else 0
        tol = 0.5 * 10 ** -dec + 1e-9
        scale = 1000 if unit == "k" else 1
        if not any(abs(v / scale - n) <= tol or abs(v - n) <= tol for v in pool):
            misses.append(m.group(0))
    return misses


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


def shim_dir(where, log=None):
    """A directory holding a `claude` for PATH: the logging shim (log given) or one that always fails."""
    d = Path(where)
    d.mkdir(parents=True, exist_ok=True)
    exe = d / "claude"
    real = shutil.which("claude") or "claude"
    exe.write_text(SHIM.format(real=real, log=str(log)) if log else FAIL_SHIM, encoding="utf-8", newline="\n")
    exe.chmod(0o755)
    return d


def no_plugin_env(extra=None):
    """This process's environment without plugin, project or bench variables, plus `extra`."""
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PLUGIN_ROOT", "CLAUDE_PLUGIN_DATA",
                                                             "CLAUDE_PROJECT_DIR", "BENCH_SCRATCH", "KB_INDEX")}
    env.update(extra or {})
    return env


# ---------------------------------------------------------------------------------------------------- a run


class Bench:
    """One `run`: the record's identity (date, commit, Claude Code version, kb size), the scratch directory and its
    clones, and the rows written so far."""

    def __init__(self, scratch, reps):
        self.scratch, self.reps = Path(scratch), reps
        self.scratch.mkdir(parents=True, exist_ok=True)
        self.date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        self.record = self.date
        self.commit = git("rev-parse", "--short=7", "HEAD", cwd=HOME)
        self.cc = (subprocess.run(["claude", "--version"], capture_output=True, text=True).stdout.split() or ["?"])[0]
        import kbfacts
        self.topics = str(len(kbfacts.articles()))
        self.rows, self._clones, self.registered = [], {}, []

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
            _spent_run(r)
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


def spent(cost, inp, out):
    SPEND["usd"] += cost or 0
    SPEND["input"] += inp or 0
    SPEND["out"] += out or 0
    SPEND["runs"] += 1


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
    _spent_run(r)
    return r


def _spent_run(r):
    if "error" not in r:
        spent(r["cost"], r["in_uncached"] + r["cache_write"] + r["cache_read"], r["out"])


def transcript(session_id):
    """[(requests of the main session), {agent file: requests}] of a persisted session; a request is one API call
    (the last line of each requestId) with its usage, time, tool calls and text."""
    base = Path.home() / ".claude" / "projects"
    hits = list(base.glob(f"*/{session_id}.jsonl"))
    if not hits:
        return [], {}
    main = _requests(hits[0])
    subs = {p.name: _requests(p) for p in sorted((hits[0].parent / session_id / "subagents").glob("agent-*.jsonl"))}
    return main, subs


def _requests(path):
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


def usage_sum(reqs):
    u = lambda r, k: r["usage"].get(k, 0) or 0  # noqa: E731
    unc = sum(u(r, "input_tokens") for r in reqs)
    cw = sum(u(r, "cache_creation_input_tokens") for r in reqs)
    cr = sum(u(r, "cache_read_input_tokens") for r in reqs)
    return {"uncached": unc, "cache_write": cw, "cache_read": cr, "input": unc + cw + cr,
            "out": sum(u(r, "output_tokens") for r in reqs), "requests": len(reqs),
            "start_ctx": (u(reqs[0], "input_tokens") + u(reqs[0], "cache_creation_input_tokens")
                          + u(reqs[0], "cache_read_input_tokens")) if reqs else 0,
            "effective": unc + 2 * cw + 0.1 * cr}


def est_cost(model, s, searches=0):
    pin, pout, pread = PRICE[model]
    return (s["uncached"] * pin + s["cache_write"] * pin * 1.25 + s["cache_read"] * pread * (1 if model == "opus" else pin)
            + s["out"] * pout) / 1e6 + searches * WEB_SEARCH_USD


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


# ---------------------------------------------------------------------------------------------------- scenarios

HEADLESS_SCENS = ["s1_fact", "s2_fact_csv", "s3_multi", "h1_gmsa", "h2_applock", "x1_synth", "s7_web", "s8_falsegood2",
                  "o1_offkb"]


def s_headless(b):
    """Bare agent against agent with the kb, headless: agent_bench.py's `web-<model>`, `<model>` and `router` configs
    on the nine questions both arms get, and the count question for the kb arms."""
    runs = b.bench(["web-haiku", "web-sonnet", "web-opus", "haiku", "sonnet", "opus", "router"], HEADLESS_SCENS,
                   b.reps, "headless", parallel=True)
    runs += b.bench(["haiku", "sonnet", "opus", "router"], ["s4_count"], b.reps, "headless", parallel=True)
    b.bench_rows("headless", runs)
    covered = {"s1_fact", "s2_fact_csv", "s3_multi", "h1_gmsa", "h2_applock", "x1_synth", "s7_web"}
    for case, scens in (("covered (7)", covered), ("not covered (2)", {"s8_falsegood2", "o1_offkb"})):
        by = {}
        for r in runs:
            if r["scen"] in scens and "error" not in r:
                by.setdefault(r["cfg"], []).append(r)
        for cfg, rs in by.items():
            n = len(rs)
            b.row("headless", case, cfg, "cost", sum(r["cost"] for r in rs) / n, n)
            b.row("headless", case, cfg, "wall_s", sum(r["wall_s"] for r in rs) / n, n)
            b.row("headless", case, cfg, "input", sum(r["in_uncached"] + r["cache_write"] + r["cache_read"] for r in rs) / n, n)
            b.row("headless", case, cfg, "tool_calls", sum(sum(r.get("tools", {}).values()) for r in rs) / n, n)
            full = sum(all(r.get("checks") or [False]) for r in rs)
            b.row("headless", case, cfg, "fully_right", f"{full} of {n}", n)
    # Router against web search: the router and the web arms on the same covered questions, and on the false good
    for case, scens in (("covered", covered), ("not covered (false good)", {"s8_falsegood2"})):
        for cfg in ("router", "web-haiku", "web-sonnet", "web-opus"):
            rs = [r for r in runs if r["scen"] in scens and r["cfg"] == cfg and "error" not in r]
            if not rs:
                continue
            n = len(rs)
            b.row("router-web", case, cfg, "cost", sum(r["cost"] for r in rs) / n, n)
            b.row("router-web", case, cfg, "wall_s", sum(r["wall_s"] for r in rs) / n, n)
            b.row("router-web", case, cfg, "input", sum(r["in_uncached"] + r["cache_write"] + r["cache_read"] for r in rs) / n, n)
            b.row("router-web", case, cfg, "correct", f"{sum(all(r.get('checks') or [False]) for r in rs)}/{n}", n)


SUB_TASKS = {  # the subagent measurement's four questions, with agent_bench's checks
    "s1": ("What is the default Windows LAPS password length?", agent_bench.S["s1_fact"][1]),
    "h1": ("PowerShell to create a gMSA, let a server group retrieve its password, install and test it.",
           agent_bench.S["h1_gmsa"][1]),
    "x1": ("A Python CLI calls the ConfigMgr AdminService as the engineer: which auth works on 2509+, what the Python "
           "side needs, which ConfigMgr permission?", agent_bench.S["x1_synth"][1]),
    "o1": ("Run the Kubernetes Cluster Autoscaler on AWS EKS with spot instances", agent_bench.S["o1_offkb"][1]),
}


def s_subagents(b):
    """Bare agent against agent with the kb, as subagents of a running session: one agent per arm and model, its usage
    from the subagent transcript, its cost estimated at list price (PRICE)."""
    clone = b.lookup()
    agents = {}
    for m in PRICE:
        agents[f"bench-bare-{m}"] = {"description": "Answers with web search and Microsoft Learn only.", "model": m,
                                     "prompt": "Answer the question with web search and the Microsoft Learn docs "
                                               "server only. Cite the source urls.",
                                     "tools": ["WebSearch", "WebFetch", *DOCS_TOOLS]}
        agents[f"bench-kb-{m}"] = {"description": "Answers from the it-ops-kb first.", "model": m,
                                   "prompt": "Answer from the it-ops-kb: call kb_pack first and cite path:line, the tag "
                                             "and the url. Use Microsoft Learn or web search only for what the kb "
                                             "lacks, and label that part live docs.",
                                   "tools": [*KB_TOOLS, *DOCS_TOOLS, "WebSearch", "WebFetch"]}
    allowed = [*KB_TOOLS, *DOCS_TOOLS, "WebSearch", "WebFetch"]
    totals = {}
    for case, (task, checks) in SUB_TASKS.items():
        for arm in ("bare", "kb"):
            for m in PRICE:
                ev, reqs = subagent(b, clone, "haiku", agents, f"bench-{arm}-{m}", task, allowed)
                if "error" in ev or not reqs:
                    b.row("subagents", case, f"{arm}-{m}", "errors", 1, 1, note=str(ev.get("error", "no transcript"))[:80])
                    continue
                s = usage_sum(reqs)
                tools = [t for r in reqs for t in r["tools"]]
                answer = ev.get("result") or ""
                passed = sum(bool(re.search(c, answer)) for c in checks)
                arm_name = f"{arm}-{m}"
                for metric, v in (("input", s["input"]), ("out", s["out"]),
                                  ("cost_est", est_cost(m, s, tools.count("WebSearch"))),
                                  ("wall_s", span_s(reqs)), ("requests", s["requests"]), ("tool_calls", len(tools)),
                                  ("start_ctx", s["start_ctx"]), ("checks", f"{passed}/{len(checks)}"),
                                  ("route", " > ".join(t.replace("mcp__", "") for t in tools) or "no tool call")):
                    b.row("subagents", case, arm_name, metric, v, 1, reqs[0]["model"])
                totals.setdefault(arm_name, [0, 0.0, 0, 0])
                t = totals[arm_name]
                t[0] += s["input"]; t[1] += est_cost(m, s, tools.count("WebSearch")); t[2] += passed == len(checks); t[3] += 1
    for arm_name, (inp, cost, right, n) in totals.items():
        b.row("subagents", "total (4 scenarios)", arm_name, "input", inp, n)
        b.row("subagents", "total (4 scenarios)", arm_name, "cost_est", cost, n)
        b.row("subagents", "total (4 scenarios)", arm_name, "fully_right", f"{right}/{n}", n)


def s_models(b):
    """Models and hand-off patterns: each model alone on s1-s7, Opus handing the lookup to the Haiku kb-lookup agent,
    and Haiku told to hand live-docs work to a Sonnet agent."""
    scens = ["s1_fact", "s2_fact_csv", "s3_multi", "s4_count", "s5_none", "s6_falsegood", "s7_web"]
    runs = b.bench(["haiku", "sonnet", "opus"], scens, b.reps, "models")
    runs += b.bench(["opus+delegate"], ["s1_fact", "s3_multi", "s4_count", "s6_falsegood", "s7_web"], b.reps, "models")
    runs += b.bench(["haiku+escalate"], ["s6_falsegood", "s7_web"], b.reps, "models")
    b.bench_rows("models", runs)


def s_router(b):
    """Routing by verdict: kb_ask.py's routing on eight questions, a first run and a repeat; and the start context of
    the reader's `claude -p` with the user's plugins and servers, without them, and without tools."""
    scens = ["s1_fact", "s2_fact_csv", "s3_multi", "s4_count", "s5_none", "s6_falsegood", "s7_web", "s8_falsegood2"]
    runs = b.bench(["router"], scens, max(2, b.reps), "router")
    for i, r in enumerate(runs):
        r["cfg"] = "router first run" if i < len(scens) else "router repeat"
    b.bench_rows("router", runs)
    clone = b.lookup()
    base = ["claude", "-p", "--no-session-persistence", "--model", "haiku", *NO_HOOKS]
    lean = ["--setting-sources", "project,local", "--strict-mcp-config"]
    for arm, argv in (("user plugins and servers", base), ("lean", base + lean), ("lean, no tools", base + lean + ["--tools", ""])):
        vals = [claude_json(argv, OK_PROMPT, clone) for _ in range(2)]
        vals = [v for v in vals if "error" not in v]
        if vals:
            b.row("router", "start context", arm, "start_ctx", max(v["input"] for v in vals), len(vals), "haiku",
                  note="; ".join(str(v["input"]) for v in vals))
            b.row("router", "start context", arm, "cost", sum(v["total_cost_usd"] for v in vals) / len(vals), len(vals), "haiku")


def s_howto(b):
    """How-to questions answered by a SNIPPET: h1-h3 on Haiku and Sonnet."""
    runs = b.bench(["haiku", "sonnet"], ["h1_gmsa", "h2_applock", "h3_mggraph"], b.reps, "howto")
    b.bench_rows("howto", runs)
    for cfg in ("haiku", "sonnet"):
        rs = [r for r in runs if r["cfg"] == cfg and "error" not in r]
        if rs:
            b.row("howto", "h1-h3", cfg, "cost", sum(r["cost"] for r in rs), len(rs), note="sum over the three")
            b.row("howto", "h1-h3", cfg, "checks", f"{sum(sum(map(bool, r['checks'])) for r in rs)}/"
                  f"{sum(len(r['checks']) for r in rs)}", len(rs))


def s_partial(b):
    """Partial knowledge, newer versions and stale copies: agent_bench.py's host scenarios on Haiku and Sonnet."""
    runs = b.bench(["haiku", "sonnet"], ["p1_partial", "p2_partial", "n1_newer", "n2_newer", "k1_stale"], b.reps, "partial")
    runs += b.bench(["haiku", "sonnet"], ["n3_newer", "n4_newer"], 1, "partial")
    b.bench_rows("partial", runs)
    for r in runs:
        if "error" not in r:
            b.row("partial", r["scen"], r["cfg"], "fetched", len(r.get("fetched", [])), 1, note="per run")
            b.row("partial", r["scen"], r["cfg"], "refetched", len(r.get("refetched", [])), 1, note="per run")
            b.row("partial", r["scen"], r["cfg"], "searches", r.get("searches", 0), 1, note="per run")


T_TASKS = {  # the six lookup tasks of the file-reading and host measurements (their wording follows the eval rows
    # the tasks seeded)
    "T1": "When does NTLMv1 become disabled by default on Windows, and what setting's default flips? Answer from the kb "
          "with path:line citations.",
    "T2": "In the kb, what is source id S1216: its row (url, publisher, date), is it superseded, and which files and "
          "lines cite it?",
    "T3": "An engineer activates PIM for Groups membership in a cloud group meant to grant rights in on-prem Active "
          "Directory. How long until it is visible to a new token and in on-prem AD, and what sync is required? Answer "
          "from the kb with path:line citations.",
    "T4": "A Python CLI must authenticate with Kerberos to call the ConfigMgr AdminService and query SQL Server as the "
          "engineer: what SPN, Negotiate and permission requirements does the kb give for each side? Cite path:line.",
    "T5": "What is the recommended Intel Wi-Fi adapter Roaming Aggressiveness setting for corporate laptops managed by "
          "Intune? Answer from the kb.",
    "T6": "Audit the kb's agents/ domain: which articles have status partial, how many UNK and COMMUNITY facts each "
          "article has, and which gap and conflict entries are linked to each article.",
}
GUIDED = " Follow the /kb-lookup skill."


def s_files_subagents(b):
    """Reading files without the lookup tools: the six tasks as Sonnet subagents in a clone of the commit before the
    lookup tools (search and show only), T1 and T4 also told to follow /kb-lookup."""
    old = b.clone("kb-old", "off", rev=OLD_COMMIT)
    agents = {"bench-reader": {"description": "Answers questions from this repository's files.", "model": "sonnet",
                               "prompt": "Answer the question from this repository's knowledge base files.",
                               "tools": ["Bash", "Read", "Grep", "Glob", "Skill"]}}
    allowed = ["Bash", "Read", "Grep", "Glob", "Skill"]
    tasks = [("T1 guided", T_TASKS["T1"] + GUIDED), ("T1", T_TASKS["T1"]), ("T2", T_TASKS["T2"]), ("T3", T_TASKS["T3"]),
             ("T4 guided", T_TASKS["T4"] + GUIDED), ("T4", T_TASKS["T4"]), ("T5", T_TASKS["T5"]), ("T6", T_TASKS["T6"])]
    for case, task in tasks:
        ev, reqs = subagent(b, old, "haiku", agents, "bench-reader", task, allowed, extra=["--strict-mcp-config"])
        if not reqs:
            b.row("files-subagents", case, "subagent", "errors", 1, 1, note=str(ev.get("error", "no transcript"))[:80])
            continue
        s = usage_sum(reqs)
        tools = [t for r in reqs for t in r["tools"]]
        for metric, v in (("tool_calls", len(tools)), ("requests", s["requests"]), ("start_ctx", s["start_ctx"]),
                          ("input", s["input"]), ("start_share_pct", 100 * s["start_ctx"] * s["requests"] / max(s["input"], 1)),
                          ("tool_output_kb", reqs[-1].get("tool_result_chars", 0) / 1024),
                          ("effective_input", s["effective"]), ("wall_s", span_s(reqs))):
            b.row("files-subagents", case, "subagent", metric, v, 1, "sonnet")
    for arm, cwd, extra in (("empty directory", b.scratch / "empty", ["--setting-sources", "project,local", "--strict-mcp-config"]),
                            ("old clone, no servers", old, ["--strict-mcp-config"]), ("old clone", old, [])):
        Path(cwd).mkdir(exist_ok=True)
        ev = claude_json(["claude", "-p", "--no-session-persistence", "--model", "sonnet", *NO_HOOKS, *extra], OK_PROMPT, cwd)
        if "error" not in ev:
            b.row("files-subagents", "fixed context", arm, "input", ev["input"], 1, "sonnet")


def _task_argv(model, extra=()):
    return ["claude", "-p", "--output-format", "stream-json", "--verbose", "--no-session-persistence", *NO_HOOKS,
            "--model", model, *extra]


def _totals(b, scenario, arm, runs):
    """The six tasks' sums (T1-T6) of one arm: turns, input, output, time."""
    rs = [r for r in runs if r["scen"] in T_TASKS and "error" not in r]
    if len(rs) == len(T_TASKS):
        b.row(scenario, "T1-T6", arm, "turns", sum(r["turns"] for r in rs), 1)
        b.row(scenario, "T1-T6", arm, "input", sum(r["in_uncached"] + r["cache_write"] + r["cache_read"] for r in rs), 1)
        b.row(scenario, "T1-T6", arm, "out", sum(r["out"] for r in rs), 1)
        b.row(scenario, "T1-T6", arm, "wall_s", sum(r["wall_s"] for r in rs), 1)


def s_files_headless(b):
    """Lookup tools against reading files: the six tasks in fresh Sonnet sessions, in a clone of the commit before the
    lookup tools and in one of HEAD, rag.py, Read, Grep, Glob and skills allowed, no web, no subagents, no servers."""
    old, new = b.clone("kb-old", "off", rev=OLD_COMMIT), b.lookup()
    extra = ["--strict-mcp-config", "--allowedTools", "Bash(python3 _tools/rag.py *)", "Read", "Grep", "Glob", "Skill",
             "--disallowedTools", "WebSearch", "WebFetch", "Agent", "Task"]
    for arm, cwd in (("before", old), ("after", new)):
        runs = []
        for case, task in [("fixed context", OK_PROMPT)] + list(T_TASKS.items()):
            r = stream_run(_task_argv("sonnet", extra), task, cwd)
            runs.append({**r, "cfg": arm, "scen": case, "checks": []})
        b.bench_rows("files-headless", runs)
        _totals(b, "files-headless", arm, runs)


HOST_TS = {  # the throwaway host project of "Plugin in a host project": five planted problems
    "CLAUDE.md": "# mecm-ad-mcp\n\nA TypeScript MCP server that exposes ConfigMgr (MECM) and Active Directory lookups to "
                 "agents. Node 22, stdio transport. `src/` holds the server and one client per backend.\n",
    "src/adminservice.ts": (
        "// ConfigMgr AdminService client\n"
        "import { negotiate, ntlm } from './auth';\n"
        "const BASE = 'https://PL-SRV-0042.corp.example.com/AdminService/wmi';\n"
        "export async function devices() {\n"
        "  // Negotiate first; fall back to NTLM when Kerberos fails\n"
        "  const auth = (await negotiate('HTTP/PL-SRV-0042')) ?? (await ntlm('CORP\\\\svc-mecm'));\n"
        "  return fetch(`${BASE}/SMS_R_System`, { headers: { Authorization: auth } });\n"
        "}\n"),
    "src/ldap.ts": (
        "// Active Directory lookups\n"
        "import ldap from 'ldapjs';\n"
        "const client = ldap.createClient({ url: 'ldap://PL-SRV-0042.corp.example.com' });\n"
        "export function bind(user: string, password: string) {\n"
        "  return new Promise((ok, err) => client.bind(user, password, (e) => (e ? err(e) : ok(true))));\n"
        "}\n"),
    "src/graph.ts": (
        "// Microsoft Graph for device lookups\n"
        "import { PublicClientApplication } from '@azure/msal-node';\n"
        "const pca = new PublicClientApplication({ auth: { clientId: '00000000-0000-0000-0000-000000000000' } });\n"
        "export const scopes = ['Directory.ReadWrite.All', 'DeviceManagementManagedDevices.ReadWrite.All', 'User.ReadWrite.All'];\n"
        "export const token = () => pca.acquireTokenByDeviceCode({ scopes, deviceCodeCallback: (r) => console.log(r.message) });\n"),
    "src/server.ts": (
        "// MCP server over stdio\n"
        "import { Server } from '@modelcontextprotocol/sdk/server/index.js';\n"
        "import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';\n"
        "const server = new Server({ name: 'mecm-ad', version: '0.1.0' }, { capabilities: { tools: {} } });\n"
        "console.log('mecm-ad MCP server starting');\n"
        "await server.connect(new StdioServerTransport());\n"),
}
REVIEW_CHECKS = [r"(?i)NTLM", r"(?i)SPN|HTTP/", r"(?i)ldaps|simple bind|plain ?text|ldap://", r"(?i)stdout|console\.log",
                 r"(?i)ReadWrite\.All|least[- ]privilege|broad"]


def host_project(b):
    host = b.scratch / "host-ts"
    shutil.rmtree(host, ignore_errors=True)
    for rel, text in HOST_TS.items():
        (host / rel).parent.mkdir(parents=True, exist_ok=True)
        (host / rel).write_text(text, encoding="utf-8", newline="\n")
    git("init", "-q", cwd=host)
    return host


def s_host_lookups(b):
    """Plugin in a host project: the six tasks in fresh Sonnet sessions in a throwaway TypeScript project with the
    plugin loaded by --plugin-dir, and in the clone; the fixed context; /kb-review-workspace in the host; the start
    context of a general-purpose Sonnet agent."""
    clone, host = b.lookup(), host_project(b)
    env = no_plugin_env({"ENABLE_CLAUDEAI_MCP_SERVERS": "false", "KB_INDEX": str(b.scratch / "index")})
    common = ["--setting-sources", "project,local"]
    arms = (("host", host, common + ["--plugin-dir", str(clone), "--allowedTools", "mcp__plugin_it-ops-kb_kb"]),
            ("clone", clone, common + ["--allowedTools", "mcp__kb", "Bash(python3 _tools/rag.py *)"]))
    for arm, cwd, extra in arms:
        runs = []
        for case, task in [("fixed context", OK_PROMPT)] + list(T_TASKS.items()):
            r = stream_run(_task_argv("sonnet", extra), task, cwd, env)
            runs.append({**r, "cfg": arm, "scen": case, "checks": []})
        b.bench_rows("host-lookups", runs)
        _totals(b, "host-lookups", arm, runs)
    r = stream_run(_task_argv("sonnet", common + ["--plugin-dir", str(clone), "--allowedTools", "mcp__plugin_it-ops-kb_kb",
                                                  "Read", "Grep", "Glob", "Agent"]),
                   "/it-ops-kb:kb-review-workspace", host, env)
    if "error" not in r:
        r["checks"] = [bool(re.search(c, r["answer"])) for c in REVIEW_CHECKS]
        b.bench_rows("host-lookups", [{**r, "cfg": "host", "scen": "kb-review-workspace"}])
        b.row("host-lookups", "kb-review-workspace", "host", "sub_tool_calls", sum(r.get("sub_tools", {}).values()), 1)
    agents = {"bench-general": {"description": "A general-purpose agent.", "model": "sonnet",
                                "prompt": "You are a general-purpose agent. Answer the task."}}
    ev, reqs = subagent(b, host, "haiku", agents, "bench-general", T_TASKS["T1"],
                        ["mcp__plugin_it-ops-kb_kb"], extra=common + ["--plugin-dir", str(clone)], env=env)
    if reqs:
        b.row("host-lookups", "general-purpose agent", "host", "start_ctx", usage_sum(reqs)["start_ctx"], 1, "sonnet")


def _ok_runs(argv, cwd, n, env=None):
    vals = [claude_json(argv, OK_PROMPT, cwd, env) for _ in range(n)]
    return [v["input"] for v in vals if "error" not in v]


def s_always_on(b):
    """Always-on cost: `claude -p "Reply with the single word ok." --model haiku` in an empty directory without and with
    the plugin (hooks off, and hooks on in a copy that writes under the scratch directory), and in a clone with its
    query log hooks on (mode local, local origin) and off. The value is the steady (highest) input of the runs."""
    clone = b.lookup()
    empty = b.scratch / "empty"
    empty.mkdir(exist_ok=True)
    data = b.scratch / "plugin-data"
    shutil.rmtree(data, ignore_errors=True)
    hooked = plugin_copy(clone, b.scratch / "plugin-hooks", data)
    hooks_clone = b.clone("kb-hooks", "local")
    env = no_plugin_env({"KB_INDEX": str(b.scratch / "index")})
    base = ["claude", "-p", "--model", "haiku", "--no-session-persistence", "--setting-sources", "project,local"]
    n = max(4, b.reps)
    arms = (("no plugin", base + NO_HOOKS, empty), ("--plugin-dir, hooks off", base + NO_HOOKS + ["--plugin-dir", str(clone)], empty),
            ("--plugin-dir, hooks on", base + ["--plugin-dir", str(hooked)], empty),
            ("clone, hooks off", base + NO_HOOKS, hooks_clone), ("clone, query log hooks on", base, hooks_clone))
    for arm, argv, cwd in arms:
        vals = _ok_runs(argv, cwd, n, env)
        if vals:
            b.row("always-on", "ok", arm, "input", max(vals), len(vals), "haiku", note="; ".join(map(str, vals)))
    wrote = [f.name for f in (data / "querylog").iterdir() if f.name != "config.json"]
    b.row("always-on", "isolation", "--plugin-dir, hooks on", "files_the_hooks_wrote", len(wrote),
          note="under the scratch plugin data directory: " + " ".join(sorted(wrote)))


def s_kb_lookup_agent(b):
    """The kb-lookup agent's start context: the first request of its transcript, handed one question by Haiku with the
    plugin loaded by --plugin-dir (hooks off)."""
    clone = b.lookup()
    empty = b.scratch / "empty"
    empty.mkdir(exist_ok=True)
    env = no_plugin_env({"KB_INDEX": str(b.scratch / "index")})
    for i in range(max(3, b.reps)):
        sid = str(uuid.uuid4())
        ev = claude_json(["claude", "-p", "--model", "haiku", "--session-id", sid, *NO_HOOKS, "--setting-sources",
                          "project,local", "--plugin-dir", str(clone), "--allowedTools", "Agent,mcp__plugin_it-ops-kb_kb"],
                         "Use the it-ops-kb:kb-lookup agent to answer this, then relay its answer: How many apps can an "
                         "Intune Win32 app supersede?", empty, env)
        _, subs = transcript(sid)
        reqs = next(iter(subs.values()), [])
        if not reqs:
            b.row("kb-lookup-agent", f"run {i + 1}", "kb-lookup", "errors", 1, 1, note=str(ev.get("error", ""))[:80])
            continue
        s = usage_sum(reqs)
        b.row("kb-lookup-agent", f"run {i + 1}", "kb-lookup", "start_ctx", s["start_ctx"], 1, reqs[0]["model"])
        b.row("kb-lookup-agent", f"run {i + 1}", "kb-lookup", "input", s["input"], 1, reqs[0]["model"])
        b.row("kb-lookup-agent", f"run {i + 1}", "kb-lookup", "requests", s["requests"], 1, reqs[0]["model"])
        b.row("kb-lookup-agent", f"run {i + 1}", "kb-lookup", "route",
              " > ".join(t.replace("mcp__plugin_it-ops-kb_kb__", "") for r in reqs for t in r["tools"]), 1)
        b.row("kb-lookup-agent", f"run {i + 1}", "kb-lookup", "checks",
              "1/1" if re.search(r"\b10\b", ev.get("result") or "") else "0/1", 1)


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
    cut_no_tag = 0
    for _, c in rag.eval_cases():
        for ln in kbfacts.pack(c["question"])["text"].splitlines():
            if ln.startswith("- ") and ("..." in ln or "…" in ln) and not re.search(r"\[(DOC|CODE|DER|COMMUNITY|UNK)[^\]]*\]|\(no tag\)", ln):
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
            b.row("doc2query", "off-kb", f"expansion {mode}", "verdicts", m.group(4), 1)


def _time(argv, n, cwd, env=None, stdin=None):
    out = []
    for _ in range(n):
        t = time.perf_counter()
        subprocess.run(argv, cwd=str(cwd), input=stdin, capture_output=True, text=True, encoding="utf-8",
                       env=env or no_plugin_env())
        out.append(time.perf_counter() - t)
    return out


def _stats(b, scenario, case, arm, secs, note="", time_s=False):
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


def s_tool_speed(b):
    """Tool speed: cold CLI calls with the persisted index, the kb: hook, rag.py eval and search, an MCP session of 12
    calls, check-trailers over 30 commits, an index build; in-process pack, the server's start, 1,000 random packs."""
    clone = b.lookup()
    py = sys.executable
    _stats(b, "tool-speed", "rag.py pack (CLI, cold)", "current", time_s=True, secs=_time([py, "_tools/rag.py", "pack", "default Windows LAPS password length"], 5, clone))
    hook = json.dumps({"hook_event_name": "UserPromptSubmit", "session_id": str(uuid.uuid4()), "prompt":
                       "kb: Does deleting an Entra device also delete its BitLocker recovery keys?"})
    _stats(b, "tool-speed", "kb: hook", "current", time_s=True, secs=_time([py, "_tools/kb_hook.py"], 5, clone, stdin=hook))
    _stats(b, "tool-speed", "rag.py eval", "current", time_s=True, secs=_time([py, "_tools/rag.py", "ev" + "al"], 3, clone))
    _stats(b, "tool-speed", "rag.py search", "current", time_s=True, secs=_time([py, "_tools/rag.py", "search", "gMSA password retrieval"], 5, clone))
    _stats(b, "tool-speed", "kbgit.py check-trailers (30 commits)", "current", time_s=True,
           secs=_time([py, "_tools/kbgit.py", "check-trailers", "HEAD~30..HEAD"], 3, clone))
    secs = [mcp_session(clone)[1] for _ in range(3)]
    _stats(b, "tool-speed", "MCP session (12 calls)", "current", secs, time_s=True)
    starts = [mcp_session(clone, [])[0] for _ in range(5)]
    _stats(b, "tool-speed", "MCP server start (initialize reply)", "current", starts)
    idx = b.scratch / "index-build"
    shutil.rmtree(idx, ignore_errors=True)
    idx.mkdir()
    t = _time([py, "_tools/rag.py", "pack", "x"], 1, clone, env=no_plugin_env({"KB_INDEX": str(idx)}))
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
    _stats(b, "tool-speed", "pack in-process, warm", "current", ms)
    rng = random.Random(3)
    words = [w for u in rng.sample(kbfacts.units(), 400) for w in re.findall(r"[A-Za-z]{4,}", u["text"])]
    t0 = time.perf_counter()
    for _ in range(1000):
        kbfacts.pack(" ".join(rng.sample(words, 4)))
    b.row("tool-speed", "1,000 random packs", "current", "s", time.perf_counter() - t0, 1)


# -- query log


def _event(kind, sid, pid, **kw):
    return json.dumps({"hook_event_name": kind, "session_id": sid, "prompt_id": pid, "cwd": "/tmp", **kw})


def s_querylog_hooks(b):
    """The query log's hooks: capture per event (async, so no prompt waits on it), the synchronous UserPromptSubmit
    hooks, the SessionEnd launcher's return time (nothing to distill, and a closed session to distill: it starts a
    detached distill, whose `claude` here fails at once), and the weekly digest hook; all through `sh _tools/kbpy` of
    a throwaway clone, writing under a scratch plugin data directory in mode `local`."""
    clone = b.clone("kb-hooks", "local")
    data = b.scratch / "ql-hooks-data"
    shutil.rmtree(data, ignore_errors=True)
    (data / "querylog").mkdir(parents=True)
    (data / "querylog" / "config.json").write_text('{"mode": "local"}\n', encoding="utf-8")
    fail = shim_dir(b.scratch / "fail-shim")
    env = no_plugin_env({"CLAUDE_PLUGIN_ROOT": str(clone), "CLAUDE_PLUGIN_DATA": str(data), "KB_INDEX": str(clone / "_cache"),
                         "PATH": f"{fail}{os.pathsep}{os.environ.get('PATH', '')}"})
    kbpy = ["sh", str(clone / "_tools" / "kbpy")]
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
        _stats(b, "querylog-hooks", f"capture, {name}", "async hook", secs)
    plain = _event("UserPromptSubmit", sid, "x", prompt="How do I rename a branch?")
    _stats(b, "querylog-hooks", "kb_hook.py, a prompt without kb:", "sync hook",
           [_t(kbpy + ["_tools/kb_hook.py"], clone, plain, env) for _ in range(n)])
    _stats(b, "querylog-hooks", "kb_change_router.py, a question", "sync hook (clone only)",
           [_t(kbpy + [".claude/hooks/kb_change_router.py"], clone, plain, env) for _ in range(n)])
    idle = []
    for _ in range(20):
        idle.append(_t(kbpy + ["_tools/querylog.py", "launch"], clone,
                       _event("SessionEnd", str(uuid.uuid4()), "", reason="other"), env))
    _stats(b, "querylog-hooks", "SessionEnd launcher, nothing waiting", "sync hook", idle,
           note="LAUNCH_BUDGET_S 500 ms")
    ready = []
    for _ in range(20):
        s = str(uuid.uuid4())
        subprocess.run(kbpy + ["_tools/querylog.py", "capture"], cwd=clone, input=_event("UserPromptSubmit", s, "p", prompt="kb: LAPS length"),
                       capture_output=True, text=True, env=env)
        (data / "querylog" / "distill.lock").unlink(missing_ok=True)
        ready.append(_t(kbpy + ["_tools/querylog.py", "launch"], clone, _event("SessionEnd", s, "", reason="other"), env))
    _stats(b, "querylog-hooks", "SessionEnd launcher, a session to distill", "sync hook", ready,
           note="starts a detached distill; LAUNCH_BUDGET_S 500 ms")
    b.row("querylog-hooks", "SessionEnd launcher", "sync hook", "max_ms", max(idle + ready) * 1000, len(idle + ready))
    (data / "querylog" / "digest-week").unlink(missing_ok=True)
    _stats(b, "querylog-hooks", "digest --hook", "sync hook",
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
    _stats(b, "querylog-pipeline", "distill (recorded Haiku)", "fixtures", secs, note=f"{entries} entries written")
    b.row("querylog-pipeline", "distill (recorded Haiku)", "fixtures", "entries", entries, len(secs))
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
    import redact, kbcommon
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
    "question": "Can Windows LAPS back up the password of a Windows Server 2012 R2 member server to Azure?",
    "verdict": "weak", "articles": ["public/windows/laps.md"],
    "summary": "The kb does not say whether Windows Server 2012 R2 is supported.", "judged": "missed"}


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


INGEST_REPO = ("https://github.com/pypa/sampleproject.git", "621e4974ca25ce531773def586ba3ed8e736b3fc")


def s_ingest(b):
    """/kb-ingest on a sample repository (a public one at a pinned commit): kbingest.py's survey, then the skill in a
    headless Sonnet session in a throwaway clone (query log off, local origin), its questions answered in the prompt."""
    url, sha = INGEST_REPO
    repo = b.scratch / "sample-repo"
    if not (repo / ".git").exists():
        shutil.rmtree(repo, ignore_errors=True)
        git("clone", "-q", url, str(repo), cwd=b.scratch)
    git("checkout", "-q", "--detach", sha, cwd=repo)
    secs = _time([sys.executable, str(TOOLS / "kbingest.py"), "survey", str(repo), "--rev", sha, "--files"], 3, HOME)
    _stats(b, "ingest", "kbingest.py survey", "sampleproject", secs)
    out = subprocess.run([sys.executable, str(TOOLS / "kbingest.py"), "survey", str(repo), "--rev", sha, "--files"],
                         capture_output=True, text=True, encoding="utf-8").stdout
    keep = sum(ln.startswith("keep\t") for ln in out.splitlines())
    skip = sum(ln.startswith("skip\t") for ln in out.splitlines())
    b.row("ingest", "kbingest.py survey", "sampleproject", "files_kept", keep, 1)
    b.row("ingest", "kbingest.py survey", "sampleproject", "files_left_out", skip, 1)
    clone = b.clone("kb-ingest", "off")
    prompt = (f"/kb-ingest {repo} sample\n\nThe answers to the skill's questions, agreed in advance: the root is a new "
              "root named `sample`, prefix SMP, visibility public, description \"The PyPA sample project\"; the "
              f"repository is public on GitHub and pinned at {sha}; the topic plan is one topic, "
              "`python/sampleproject`, covering its packaging layout, build backend, entry points, tests and CI. "
              "Write it now without asking again. Do not commit or push.")
    r = stream_run(["claude", "-p", "--output-format", "stream-json", "--verbose", "--no-session-persistence", *NO_HOOKS,
                    "--model", "sonnet", "--permission-mode", "bypassPermissions", "--max-budget-usd", "4"], prompt, clone)
    if "error" in r:
        b.row("ingest", "/kb-ingest", "sonnet", "errors", 1, 1, note=r["error"][:80])
        return
    b.bench_rows("ingest", [{**r, "cfg": "sonnet", "scen": "/kb-ingest", "checks": []}])
    p = subprocess.run([sys.executable, "_tools/rag.py", "audit", "sample"], cwd=clone, capture_output=True, text=True)
    facts = sum(int(m.group(1)) for m in re.finditer(r"^\| \S+ \| \w+ \| (\d+) \|", p.stdout, re.M))
    b.row("ingest", "/kb-ingest", "sonnet", "facts_written", facts, 1)
    chk = subprocess.run([sys.executable, "_tools/check.py"], cwd=clone, capture_output=True, text=True).stdout
    m = re.search(r"errors=(\d+)", chk)
    b.row("ingest", "/kb-ingest", "sonnet", "check_errors", int(m.group(1)) if m else "", 1)


TEAM_ARTICLE = """---
topic: intune/compliance-naming
priority: P2
applies_to: "The team's Intune compliance policies"
retrieved_utc: {date}
sources: [TM-unavfdbc]
status: complete
---

# Team Intune compliance policy naming

## Summary
How the team names its Intune compliance policies and sets the grace period of the built-in noncompliance action.

## Facts
- Team naming rule: every Intune compliance policy is named `CMP-<platform>-<ring>-<purpose>`, for example `CMP-WIN-PROD-Baseline`. [DOC TM-unavfdbc]
- The ring part is one of `PILOT`, `BROAD` or `PROD`, and a policy is assigned to the group of its ring only. [DOC TM-unavfdbc]
- The team sets the schedule of the built-in "Mark device noncompliant" action to 1 day on every `CMP-*-PROD-*` policy, as a grace period. [DOC TM-unavfdbc]

## Reference
- The team wiki page on compliance naming.

## Examples
- `CMP-WIN-PILOT-Encryption`
"""
ROOTS_Q = ("what is our team's naming rule for Intune compliance policies, and can the built-in Mark device "
           "noncompliant action be removed?")
ROOTS_CHECKS = [r"CMP-", r"(?i)can.?not be removed|can't be removed|cannot remove|can't remove|not be removed",
                r"team/intune/compliance-naming\.md", r"compliance-policies\.md"]


def s_host_roots(b):
    """A host plugin with team roots: a fork (a throwaway clone) with a `team` root beside public, asked one question
    spanning both roots with the plugin loaded by --plugin-dir and with the team root served by KB_ROOTS; and the
    server over stdio (no model). The installed-plugin mode is not run: it writes the installed plugin's data
    directory under ~/.claude."""
    fork = b.clone("kb-fork", "off")
    py = sys.executable
    subprocess.run([py, "_tools/kbroot.py", "add", "team", "--prefix", "TM", "--visibility", "internal"], cwd=fork,
                   capture_output=True, env=no_plugin_env())
    art = fork / "kb" / "team" / "intune" / "compliance-naming.md"
    art.parent.mkdir(parents=True, exist_ok=True)
    art.write_text(TEAM_ARTICLE.format(date=b.date), encoding="utf-8", newline="\n")
    with open(fork / "kb" / "team" / "_sources.csv", "a", encoding="utf-8", newline="\n") as f:
        f.write(f"TM-unavfdbc,https://wiki.corp.example.com/endpoint/intune-compliance-naming,Intune compliance naming,"
                f"Endpoint team,internal,quote,{b.date},,,,\n")
    subprocess.run([py, "_tools/build_index.py"], cwd=fork, capture_output=True, env=no_plugin_env())
    chk = subprocess.run([py, "_tools/check.py"], cwd=fork, capture_output=True, text=True, env=no_plugin_env()).stdout
    m = re.search(r"errors=(\d+)", chk)
    b.row("host-roots", "fork", "check.py", "errors", int(m.group(1)) if m else "", 1)
    host = b.scratch / "host-roots"
    shutil.rmtree(host, ignore_errors=True)
    host.mkdir()
    git("init", "-q", cwd=host)
    env = no_plugin_env({"ENABLE_CLAUDEAI_MCP_SERVERS": "false", "KB_INDEX": str(b.scratch / "index-fork")})
    teamdir = b.scratch / "team-root"
    shutil.rmtree(teamdir, ignore_errors=True)
    shutil.copytree(fork / "kb" / "team", teamdir / "team")
    lookup = b.lookup()
    mcp = json.dumps({"mcpServers": {"kb": {"command": py, "args": [str(lookup / "_tools" / "kb_mcp.py")],
                                            "env": {"KB_ROOTS": str(teamdir / "team")}}}})
    modes = (("--plugin-dir", ["--setting-sources", "project", "--plugin-dir", str(fork), "--allowedTools", "mcp__plugin_it-ops-kb_kb"]),
             ("KB_ROOTS", ["--setting-sources", "project", "--mcp-config", mcp, "--strict-mcp-config", "--allowedTools", "mcp__kb"]))
    for mode, extra in modes:
        runs = []
        for _ in range(max(2, b.reps)):
            r = stream_run(_task_argv("haiku", extra), ROOTS_Q, host, env)
            if "error" not in r:
                r["checks"] = [bool(re.search(c, r["answer"])) for c in ROOTS_CHECKS]
            runs.append({**r, "cfg": mode, "scen": "both roots"})
        b.bench_rows("host-roots", runs)
    _, _, texts = mcp_session(fork, [("kb_status", {}), ("kb_pack", {"question": ROOTS_Q})])
    pack = texts[-1] if texts else ""
    b.row("host-roots", "server over stdio", "no model", "coverage", (re.search(r"coverage: (\w+)", pack) or [None, "?"])[1], 1)
    b.row("host-roots", "server over stdio", "no model", "roots_in_pack",
          sum(x in pack for x in ("team/intune/compliance-naming.md", "public/intune/compliance-policies.md")), 1)


def s_kbpy(b):
    """The hook launcher's start-up: a no-op script run by `sh _tools/kbpy` against the same script run by the
    interpreter directly, on this OS."""
    d = b.scratch / "kbpy" / "_tools"
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(TOOLS / "kbpy", d / "kbpy")
    (d.parent / "noop.py").write_text("pass\n", encoding="utf-8")
    osname = platform.system()
    n = max(50, b.reps)
    direct = _time([shutil.which("python3") or sys.executable, str(d.parent / "noop.py")], n, d.parent)
    via = _time(["sh", str(d / "kbpy"), "noop.py"], n, d.parent)
    _stats(b, "kbpy", "python3 noop.py", osname, direct)
    _stats(b, "kbpy", "sh _tools/kbpy noop.py", osname, via)
    b.row("kbpy", "launcher overhead", osname, "median_ms", (statistics.median(via) - statistics.median(direct)) * 1000, n)


SCENARIOS = {  # name: (report section, function)
    "headless": ("Bare agent against agent with the kb: headless sessions", s_headless),
    "subagents": ("Bare agent against agent with the kb: subagents", s_subagents),
    "models": ("Models and hand-off patterns", s_models),
    "router": ("Routing by verdict", s_router),
    "howto": ("How-to questions and SNIPPET units", s_howto),
    "partial": ("Partial knowledge, newer versions and stale copies", s_partial),
    "files-subagents": ("Reading files without the lookup tools", s_files_subagents),
    "files-headless": ("Lookup tools against reading files", s_files_headless),
    "host-lookups": ("Plugin in a host project", s_host_lookups),
    "always-on": ("Always-on cost", s_always_on),
    "kb-lookup-agent": ("kb-lookup agent start context", s_kb_lookup_agent),
    "retrieval": ("Retrieval quality", s_retrieval),
    "verdict": ("Verdict corrections", s_verdict),
    "doc2query": ("doc2query", s_doc2query),
    "tool-speed": ("Tool speed", s_tool_speed),
    "querylog-hooks": ("Query log hooks", s_querylog_hooks),
    "querylog-pipeline": ("Distill, learn and apply", s_querylog_pipeline),
    "redaction": ("Redaction speed", s_redaction),
    "research": ("Research cost per accepted fact", s_research),
    "ingest": ("/kb-ingest on a sample repository", s_ingest),
    "host-roots": ("A host plugin with team roots", s_host_roots),
    "kbpy": ("Hook launcher start-up", s_kbpy),
}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    r = sub.add_parser("run")
    r.add_argument("scenarios", nargs="*")
    r.add_argument("--reps", type=int, default=1)
    r.add_argument("--out")
    rep = sub.add_parser("report")
    rep.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "list":
        for name, (section, _) in SCENARIOS.items():
            print(f"{name:18} {section}")
        return 0
    if a.cmd == "report":
        rows = read_rows()
        text = REPORT.read_text(encoding="utf-8")
        new = render(text, rows)
        misses = readme_misses(README.read_text(encoding="utf-8"), rows)
        if a.check:
            bad = new != text
            if bad:
                print(f"{REPORT.relative_to(HOME)}: a generated table differs from {RESULTS.relative_to(HOME)}; "
                      "python3 _tools/benchmarks.py report rewrites it")
            for m in misses:
                print(f"README.md: {m!r} matches no row of {RESULTS.relative_to(HOME)}")
            return 1 if bad or misses else 0
        REPORT.write_text(new, encoding="utf-8", newline="\n")
        for m in misses:
            print(f"README.md: {m!r} matches no row of {RESULTS.relative_to(HOME)}")
        return 0
    names = a.scenarios or list(SCENARIOS)
    unknown = [n for n in names if n not in SCENARIOS]
    if unknown:
        print(f"unknown scenario: {', '.join(unknown)} (benchmarks.py list)", file=sys.stderr)
        return 2
    b = Bench(os.environ.get("BENCH_SCRATCH") or Path(tempfile.gettempdir()) / "it-ops-kb-bench", a.reps)
    out = Path(a.out) if a.out else RESULTS
    try:
        for n in names:
            start = len(b.rows)
            t = time.time()
            try:
                SCENARIOS[n][1](b)
            except Exception as e:  # one failed scenario does not lose the others' rows
                b.row(n, "run", "", "errors", 1, 1, note=f"{type(e).__name__}: {e}"[:200])
            if SPEND["runs"]:
                b.row(n, "all paid runs", "", "spend_usd", SPEND["usd"], SPEND["runs"])
                b.row(n, "all paid runs", "", "spend_input_tokens", SPEND["input"], SPEND["runs"])
                b.row(n, "all paid runs", "", "spend_output_tokens", SPEND["out"], SPEND["runs"])
            mine = b.rows[start:]
            print(f"{n}: {len(mine)} rows, ${SPEND['usd']:.2f} in {SPEND['runs']} paid runs, "
                  f"{time.time() - t:.0f} s", flush=True)
            SPEND.update(usd=0.0, input=0, out=0, runs=0)
            write_rows(merge_rows(read_rows(out), mine), out)
    finally:
        b.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
