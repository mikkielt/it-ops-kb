"""The benchmarks' lookup scenarios: what a lookup costs a session (headless, subagents, models, routing,
how-to and partial-knowledge questions, reading files, a host project, the always-on cost, the kb-lookup
agent) and how well a session finds the code (navigation) (stdlib only).

benchmarks.py registers these scenarios in SCENARIOS and holds the command line; the harness is bench_core.py
(kb/_self/code.md, Layout and Imports; the scenarios are described in kb/_self/reports/benchmarks.md). This
module imports no facade.
"""
import json, re, shlex, shutil, subprocess, time, uuid
from pathlib import Path

import agent_bench
from bench_core import (OK_PROMPT, PRICE, RAW, claude_json, est_cost, git, no_plugin_env, plugin_copy, span_s,
                        spent_run, stream_run, subagent, task_argv, transcript, usage_sum)
from kbcommon import NO_HOOKS


OLD_COMMIT = "19010a8"  # the commit before the evidence pack, audit tools and kb: hook ("Lookup tools against reading files")
DOCS_TOOLS = ["mcp__microsoft-learn__microsoft_docs_search", "mcp__microsoft-learn__microsoft_docs_fetch"]
KB_TOOLS = [f"mcp__kb__{t}" for t in ("kb_pack", "kb_show", "kb_search", "kb_facts", "kb_audit", "kb_source", "kb_status")]
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


RBV_CASES = ["s5_none", "o1_offkb", "s8_falsegood2", "h2_applock", "s1_fact", "s3_multi"]
RBV_ARMS = ["router-pinned", "web-sonnet-5-5", "sonnet-5-5"]  # kb_ask.py's routing, the bare web arm, the kb arm
RBV_WEB_MARGIN = 1.10  # the operator's bar on a web pack: the router costs at most 110% of the bare web arm


def pack_route(runs):
    """The route a case's pack took (`good`, `web`, `split`, or `tool`), read from the router runs' routes."""
    for r in runs:
        route = r.get("route") or []
        for step in route:
            if step.startswith("pack:"):
                return step[5:]
        if "kb_ask:tool" in route:
            return "tool"
    return ""


def verdict_bar(kind, router, web, kb, escalated=False):
    """(holds, ratio) of the operator's bar for one case, from the arms' mean costs: on a web pack the router costs at
    most 110% of the bare web arm (ratio: its cost over that limit); on a split pack it costs less than both other arms
    (ratio: its cost over the cheaper); on a good pack it stays on the reader route, without escalating (no ratio).
    holds is None when a cost, or the kind, is missing."""
    if router is None:
        return None, None
    if kind == "good":
        return (not escalated), None
    if kind == "web" and web:
        ratio = router / (web * RBV_WEB_MARGIN)
        return ratio <= 1, ratio
    if kind == "split" and web and kb:
        ratio = router / min(web, kb)
        return ratio < 1, ratio
    return None, None


def s_route_by_verdict(b):
    """Routing by verdict against the bare web arm and the kb arm, all pinned by full model name: kb_ask.py's routing
    (agent_bench.route, `router-pinned`: Haiku 4.5 reads, Sonnet 5.5 researches), `web-sonnet-5-5` (WebSearch and
    WebFetch only) and `sonnet-5-5` (the kb and docs servers), on six questions. Per case it records the route the pack
    took on this commit (`pack_route`: web, split or good), each arm's cost, time and checks, and whether the
    operator's bar holds for the router (`bar` and `limit_ratio`, verdict_bar)."""
    runs = b.bench(RBV_ARMS, RBV_CASES, b.reps, "route-by-verdict", parallel=True)
    b.bench_rows("route-by-verdict", runs)
    for case in RBV_CASES:
        by = {arm: [r for r in runs if r["scen"] == case and r["cfg"] == arm and "error" not in r] for arm in RBV_ARMS}
        rs = by["router-pinned"]
        kind = pack_route(rs)
        if not kind:
            continue
        cost = {arm: (sum(r["cost"] for r in v) / len(v) if v else None) for arm, v in by.items()}
        escalated = any("escalate" in (r.get("route") or []) for r in rs)
        holds, ratio = verdict_bar(kind, cost["router-pinned"], cost["web-sonnet-5-5"], cost["sonnet-5-5"], escalated)
        b.row("route-by-verdict", case, "router-pinned", "pack_route", kind, len(rs))
        b.row("route-by-verdict", case, "router-pinned", "bar", "no data" if holds is None else
              ("holds" if holds else "misses"), len(rs))
        if ratio is not None:
            b.row("route-by-verdict", case, "router-pinned", "limit_ratio", ratio, len(rs))


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
            r = stream_run(task_argv("sonnet", extra), task, cwd)
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
            r = stream_run(task_argv("sonnet", extra), task, cwd, env)
            runs.append({**r, "cfg": arm, "scen": case, "checks": []})
        b.bench_rows("host-lookups", runs)
        _totals(b, "host-lookups", arm, runs)
    r = stream_run(task_argv("sonnet", common + ["--plugin-dir", str(clone), "--allowedTools", "mcp__plugin_it-ops-kb_kb",
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


NAV = {  # case: the question, the functions every right answer names, the tests of which a right answer names one. Only
    # names, never a path: a file that moves, or a module that splits, leaves the answer right, and the scenario scores
    # the new layout with the same prompts. Each question matches a file the code's split moves.
    "N1": {"prompt": "In this repository, the query log's automatic push reads a GitLab pipeline by its jobs, not by its "
                     "status, to decide whether the pushed commit is red and must be reverted: a job nobody started must "
                     "not make it red, a job that timed out must. Which function decides that, and which tests pin it?",
           "functions": ["job_verdict"],
           "tests": ["test_a_failed_script_is_red_and_an_unreadable_list_is_unverified",
                     "test_a_timed_out_or_stuck_job_is_red", "test_a_pipeline_whose_jobs_never_ran_is_ok"]},
    "N2": {"prompt": "In this repository, `kbgit.py sync --push` sends a range of commits that changes code to a "
                     "merge-request branch instead of main, named after a work id. Which function plans that (the lane "
                     "and the branch) and which test pins which id names the branch?",
           "functions": ["lane_plan"],
           "tests": ["test_branch_id_is_the_first_work_id"]},
    "N3": {"prompt": "In this repository, a benchmark scenario holds the router to a cost bar that depends on the "
                     "verdict of the pack: on a web pack it may cost at most 110% of the bare web arm. Which function "
                     "decides whether the bar holds, and which tests pin it?",
           "functions": ["verdict_bar"],
           "tests": ["test_the_bar_on_a_web_pack_is_110_percent_of_the_bare_arm",
                     "test_the_bar_on_a_split_pack_is_below_both_other_arms",
                     "test_the_bar_on_a_good_pack_is_the_reader_route_without_escalation"]},
}
NAV_ASK = (" Change no file. Answer in two lines and nothing else: `Functions:` and the exact names of the functions, "
           "then `Tests:` and the exact names of the tests, no paths.")
# read-only: files through Read, Grep, Glob and these commands; the kb's own tools as a session in a clone has them
NAV_ALLOWED = ["Read", "Grep", "Glob", "Bash(git grep *)", "Bash(git ls-files *)", "Bash(grep *)", "Bash(ls *)",
               "Bash(cat *)", "Bash(head *)", "Bash(tail *)", "Bash(sed -n *)", "Bash(wc *)",
               "Bash(python3 _tools/rag.py *)", "Bash(python3 _tools/selfdoc.py *)"]
NAV_DENIED = ["WebSearch", "WebFetch", "Agent", "Task", "Edit", "Write", "NotebookEdit"]
NAV_FILE = re.compile(r"[\w./-]+\.(?:py|md|csv|json|toml|ya?ml|txt|ps1|sh)")  # no wildcard, no space


def nav_named(name, answer):
    return re.search(rf"(?<!\w){re.escape(name)}(?!\w)", answer or "") is not None


def nav_check(case, answer):
    """[functions, tests] of one answer: it names every function of the case, and at least one of its tests."""
    spec = NAV[case]
    return [all(nav_named(f, answer) for f in spec["functions"]), any(nav_named(t, answer) for t in spec["tests"])]


def nav_path(p, root):
    """A path as the clone holds it: relative, with `/`, whatever prefix the run's working directory had."""
    p = str(p).strip().strip("\"'").replace("\\", "/")
    p = re.sub(r":\d+(-\d+)?$", "", p)  # a line suffix
    i = p.find(f"/{Path(root).name}/")
    if i >= 0:
        p = p[i + len(Path(root).name) + 2:]
    return p[2:] if p.startswith("./") else p


def nav_files(uses, root):
    """The distinct files a run read, from its tool calls [(name, input)]: the `file_path` of Read, the `path` of Grep or
    Glob when it names a file, and the files a Bash command names (an argument that ends in a file extension and has
    no wildcard). A search over a directory reads no one file, so it adds none."""
    seen = []
    for name, inp in uses:
        inp = inp if isinstance(inp, dict) else {}
        cands = []
        if name == "Read":
            cands = [inp.get("file_path")]
        elif name in ("Grep", "Glob"):
            cands = [inp.get("path")]
        elif name == "Bash":
            cmd = str(inp.get("command") or "")
            try:
                cands = shlex.split(cmd)
            except ValueError:
                cands = cmd.split()
        for c in cands:
            if not c:
                continue
            p = nav_path(c, root)
            if NAV_FILE.fullmatch(p) and p not in seen:
                seen.append(p)
    return seen


def nav_uses(stdout):
    """[(tool, input)] of every tool call in a stream-json run, in order."""
    out = []
    for line in stdout.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        msg = ev.get("message") if isinstance(ev, dict) else None
        if isinstance(ev, dict) and ev.get("type") == "assistant" and isinstance(msg, dict):
            out += [(c.get("name", ""), c.get("input")) for c in msg.get("content") or []
                    if isinstance(c, dict) and c.get("type") == "tool_use"]
    return out


def nav_result(stdout, root, wall=0.0):
    """One navigation run read from its stream: agent_bench's result fields (cost, turns, input, output, tool counts,
    answer) and `files_read`, or {"error": ...} when the run has no result or was refused."""
    seen, res = agent_bench.parse(stdout)
    if not res:
        return {"error": "no result event"}
    if res.get("is_error"):
        return {"error": str(res.get("result") or "is_error")[:200]}
    u = res.get("usage") or {}
    return {"wall_s": round(wall, 1), "api_s": round((res.get("duration_api_ms") or 0) / 1000, 1),
            "cost": round(res.get("total_cost_usd") or 0, 4), "turns": res.get("num_turns", 0),
            "in_uncached": u.get("input_tokens", 0), "cache_write": u.get("cache_creation_input_tokens", 0),
            "cache_read": u.get("cache_read_input_tokens", 0), "out": u.get("output_tokens", 0),
            "models": {m: round(v["costUSD"], 4) for m, v in (res.get("modelUsage") or {}).items()},
            **seen, "files_read": nav_files(nav_uses(stdout), root), "answer": res.get("result") or ""}


def nav_argv():
    return task_argv("sonnet", ["--strict-mcp-config", "--allowedTools", *NAV_ALLOWED, "--disallowedTools", *NAV_DENIED])


def nav_run(argv, prompt, cwd):
    """One `claude -p` run of a navigation question in `cwd`, hooks off, through nav_result."""
    t = time.time()
    try:
        p = subprocess.run(argv, cwd=str(cwd), input=prompt, capture_output=True, text=True, encoding="utf-8",
                           env=no_plugin_env(), timeout=900)
    except subprocess.TimeoutExpired:
        return {"error": "timed out after 900 s"}
    r = nav_result(p.stdout, cwd, time.time() - t)
    if "error" in r:
        r["error"] += (": " + p.stderr.strip()[-300:]) if p.stderr.strip() else ""
        return r
    spent_run(r)
    if RAW.get("path"):
        with open(RAW["path"], "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps({"prompt": prompt[:300], **r}) + "\n")
    return r


def s_navigation(b):
    """Finding the code: three questions (a query-log delivery rule, a kbgit.py trailer or sync rule, a benchmark
    scenario) put to fresh Sonnet sessions in a throwaway clone of HEAD, hooks off, read-only tools, no subagents, no
    MCP servers. An answer is right when it names the case's function and one of its tests (nav_check). Rows per case
    under the arm `--arm` names: turns, tool calls, files read and input tokens (means over `--reps` runs), the
    answers that named the right functions and tests (`checks`: functions and tests, each a run counts), and their sums."""
    arm = getattr(b, "arm", "") or "current"
    clone = b.clone("navigation", "off")
    runs = []
    for case, spec in NAV.items():
        for _ in range(b.reps):
            r = nav_run(nav_argv(), spec["prompt"] + NAV_ASK, clone)
            runs.append({**r, "cfg": arm, "scen": case, "checks": nav_check(case, r["answer"]) if "error" not in r else []})
    b.bench_rows("navigation", runs)
    ok = [r for r in runs if "error" not in r]
    for case in NAV:
        rs = [r for r in ok if r["scen"] == case]
        if rs:
            b.row("navigation", case, arm, "files_read", sum(len(r["files_read"]) for r in rs) / len(rs), len(rs))
    if ok and len({r["scen"] for r in ok}) == len(NAV):
        n = len(ok) / len(NAV)
        b.row("navigation", "N1-N3", arm, "turns", sum(r["turns"] for r in ok) / n, len(ok))
        b.row("navigation", "N1-N3", arm, "tool_calls", sum(sum(r["tools"].values()) for r in ok) / n, len(ok))
        b.row("navigation", "N1-N3", arm, "files_read", sum(len(r["files_read"]) for r in ok) / n, len(ok))
        b.row("navigation", "N1-N3", arm, "input", sum(r["in_uncached"] + r["cache_write"] + r["cache_read"]
                                                       for r in ok) / n, len(ok))
