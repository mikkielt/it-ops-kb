#!/usr/bin/env python3
"""Agent-layer benchmark of kb lookups (stdlib only; each run is a paid headless `claude -p`).

  agent_bench.py OUT.jsonl CONFIG[,CONFIG] SCENARIO[,SCENARIO] [REPS]
  agent_bench.py --summary OUT.jsonl [OUT.jsonl ...]

Appends one JSON line per run: cost (USD), wall and API seconds, turns, uncached / cache-write / cache-read input
tokens, output tokens, cost per model, tool calls of the main session and of subagents, and a regex check per
expected answer element. CONFIG: `haiku`, `sonnet`, `opus` (that model answers alone); `opus+delegate` (asked to hand
the lookup to the Haiku kb-lookup agent); `haiku+escalate` (Haiku told to hand live-docs work to a Sonnet agent
defined with --agents); `+strict` also denies the docs tools (note: the deny reaches subagents too); `router`
(kb_ask.py's routing by verdict). Results of 2026-09-26: token-usage-report.md, "Agent benchmark".
"""
import json, os, re, subprocess, sys, time
from collections import Counter

KB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = {
    "s1_fact": ("What is the default Windows LAPS password length? Answer from the kb with citation.", [r"\b14\b"]),
    "s2_fact_csv": ("Which TCP port does Delivery Optimization use for peer-to-peer traffic? Answer from the kb with citation.", [r"7680"]),
    "s3_multi": ("Answer from the kb, cite path:line for each: (1) default Windows LAPS password length; (2) the Delivery "
                 "Optimization peer-to-peer port; (3) which Claude Code version added the Elicitation hook.",
                 [r"\b14\b", r"7680", r"2\.1\.76"]),
    "s4_count": ("How many intune articles in the kb have status partial? Give the number and list them.", [r"\b6\b", r"remediations"]),
    "s5_none": ("How do I configure a Kubernetes cluster autoscaler on AWS EKS spot instances? Use the kb.",
                [r"(?i)(not cover|doesn.t cover|does not cover|no coverage|not in the kb|kb lacks|isn.t in|none)"]),
    "s6_falsegood": ("Using the kb, how do I create and update the Group Policy Central Store with the Windows 11 24H2 ADMX "
                     "templates? If the kb does not really answer it, use live Microsoft docs and label them.",
                     [r"(?i)SYSVOL", r"(?i)PolicyDefinitions"]),
    "s7_web": ("How should the KRBTGT account password be reset safely in an AD domain (how many times, how long between "
               "resets)? Check the kb first; if it lacks this, use live docs or web search and label the source.",
               [r"(?i)twice|two times|2 times", r"(?i)\b10\b ?hours|replicat"]),
}
AGENTS = {"kb-live-docs": {
    "description": "Live-docs research for a question the it-ops-kb does not answer: searches Microsoft Learn, Claude Code "
                   "and MCP docs (web search last) and returns a short cited answer. Give it the question and what the kb had.",
    "prompt": "You research one IT-ops question in official live documentation. Microsoft products: microsoft_docs_search, "
              "then microsoft_docs_fetch on the best page. Other products: WebSearch, then WebFetch. Answer in at most 15 "
              "lines: the answer first, then each claim with its url. Say what the docs do not state; never fill gaps from memory.",
    "model": "sonnet", "tools": ["mcp__microsoft-learn__microsoft_docs_search", "mcp__microsoft-learn__microsoft_docs_fetch",
                                 "WebSearch", "WebFetch"]}}
ROUTER = ("Routing for it-ops questions: call kb_pack first. If the pack's facts directly answer the question, answer from "
          "them yourself with path:line and urls. If coverage is weak or none, or the facts are only about something "
          "related, do not research it yourself: send the question and what the kb had to the kb-live-docs agent, then "
          "relay its answer labelled 'live docs, not in the kb'.")
MODEL = {"router": "haiku", "opus": "opus", "sonnet": "sonnet", "haiku": "haiku"}
DELEGATE = (" Delegate the kb lookup to the kb-lookup subagent (Haiku) and only relay its answer; do the live-docs step "
            "yourself only if it reports the kb lacks the answer.")


def run(cfg, scen):
    q, checks = S[scen]
    model = cfg.split("+")[0]
    prompt = q + (DELEGATE if "+delegate" in cfg else "")
    extra = []
    if "+escalate" in cfg:
        extra = ["--agents", json.dumps(AGENTS), "--append-system-prompt", ROUTER]
    if "+strict" in cfg:
        extra += ["--disallowedTools", "mcp__microsoft-learn__microsoft_docs_search", "mcp__microsoft-learn__microsoft_docs_fetch",
                  "mcp__microsoft-learn__microsoft_code_sample_search", "WebSearch", "WebFetch"]
    cmd = ["claude", "-p", "--output-format", "stream-json", "--verbose", "--no-session-persistence",
           "--model", MODEL[model], "--allowedTools", "WebSearch", "WebFetch", "mcp__kb", "Agent",
           "mcp__microsoft-learn__microsoft_docs_search", "mcp__microsoft-learn__microsoft_docs_fetch"] + extra
    if cfg == "router":
        sys.path.insert(0, os.path.join(KB, "_tools"))
        import kb_ask
        verdict, text, argv = kb_ask.route(q)
        cmd = argv[:2] + ["--output-format", "stream-json", "--verbose"] + argv[2:]
        prompt = kb_ask.prompt(q, text)
    t = time.time()
    p = subprocess.run(cmd, cwd=KB, input=prompt, capture_output=True, text=True, timeout=900)
    wall = time.time() - t
    tools, res, subs = Counter(), None, Counter()
    for line in p.stdout.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "assistant":
            for c in ev["message"].get("content", []):
                if c.get("type") == "tool_use":
                    name = c["name"] + (":" + c["input"].get("subagent_type", "") if c["name"] in ("Agent", "Task") else "")
                    (subs if ev.get("parent_tool_use_id") else tools)[name] += 1
        if ev.get("type") == "result":
            res = ev
    if not res:
        return {"cfg": cfg, "scen": scen, "error": p.stderr[-500:]}
    u = res["usage"]
    text = res.get("result") or ""
    return {"cfg": cfg, "scen": scen, "wall_s": round(wall, 1), "api_s": round(res["duration_api_ms"] / 1000, 1),
            "cost": round(res["total_cost_usd"], 4), "turns": res["num_turns"],
            "in_uncached": u["input_tokens"], "cache_write": u["cache_creation_input_tokens"],
            "cache_read": u["cache_read_input_tokens"], "out": u["output_tokens"],
            "models": {m: round(v["costUSD"], 4) for m, v in res.get("modelUsage", {}).items()},
            "tools": dict(tools), "sub_tools": dict(subs),
            "checks": [bool(re.search(c, text)) for c in checks], "answer": text}


def summary(paths):
    for f in paths:
        for line in open(f):
            r = json.loads(line)
            if "error" in r:
                print(r["cfg"], r["scen"], "ERROR", r["error"][:100])
                continue
            print(f"{r['cfg']:22} {r['scen']:13} ${r['cost']:.3f} {r['wall_s']:5.0f}s turns={r['turns']} "
                  f"write={r['cache_write']} read={r['cache_read']} out={r['out']} "
                  f"checks={''.join('Y' if c else 'n' for c in r['checks'])} {r['tools']} {r['sub_tools'] or ''}")


def main():
    if sys.argv[1:2] == ["--summary"]:
        return summary(sys.argv[2:])
    out, cfgs, scens = sys.argv[1], sys.argv[2].split(","), sys.argv[3].split(",")
    reps = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    with open(out, "a") as f:
        for _ in range(reps):
            for cfg in cfgs:
                for s in scens:
                    r = run(cfg, s)
                    f.write(json.dumps(r) + "\n")
                    f.flush()
                    print(cfg, s, r.get("cost"), r.get("wall_s"), r.get("checks"), r.get("tools"), flush=True)


if __name__ == "__main__":
    main()
