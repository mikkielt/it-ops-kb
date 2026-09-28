#!/usr/bin/env python3
"""Agent-layer benchmark of kb lookups (stdlib only; each run is a paid headless `claude -p`).

  agent_bench.py OUT.jsonl CONFIG[,CONFIG] SCENARIO[,SCENARIO] [REPS]
  agent_bench.py --summary OUT.jsonl [OUT.jsonl ...]

Appends one JSON line per run: cost (USD), wall and API seconds, turns, uncached / cache-write / cache-read input
tokens, output tokens, cost per model, tool calls of the main session and of subagents, and a regex check per
expected answer element. CONFIG: `haiku`, `sonnet`, `opus` (that model answers alone); `opus+delegate` (asked to hand
the lookup to the Haiku kb-lookup agent); `haiku+escalate` (Haiku told to hand live-docs work to a Sonnet agent
defined with --agents); `+strict` also denies the docs tools (note: the deny reaches subagents too); `router`
(kb_ask.py's routing); `web-haiku`, `web-sonnet`, `web-opus` (a typical
web-search session: no kb, no MCP servers, no project files, only WebSearch and WebFetch).

Host scenarios (HOST) run `haiku`, `sonnet` or `opus` in an empty directory under BENCH_SCRATCH (default
_cache/bench) with the kb and docs plugins loaded by --plugin-dir, no user settings or claude.ai connectors:
`p*` partial knowledge (the kb answers one part; a line records the urls fetched and those a kb tool had already
returned, `refetched`), `n*` a newer version upstream (a scratch clone planted with an older presidio release),
`k*` a kb copy behind its remote (a scratch clone whose origin/main is 3 commits ahead). Checks are regexes over the
answer, or `tool:NAME` (a tool called), `web` (a search or fetch) and `no-refetch`. Results:
kb/_self/reports/token-usage.md ("Models and hand-off patterns" and later sections) and kb/_self/reports/benchmark-bare-vs-kb.md.
"""
import json, os, re, shutil, subprocess, sys, time
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
    "s8_falsegood2": ("Microsoft Purview Data Loss Prevention endpoint DLP onboarding requirements",
                      [r"(?i)1809|Windows 11", r"(?i)live docs|not in the kb|does not cover"]),
    "s7_web": ("How should the KRBTGT account password be reset safely in an AD domain (how many times, how long between "
               "resets)? Check the kb first; if it lacks this, use live docs or web search and label the source.",
               [r"(?i)twice|two times|2 times", r"(?i)\b10\b ?hours|replicat"]),
    # how-to scenarios: the answer is a code example in the kb (the SNIPPET migration measures these)
    "h1_gmsa": ("Using the kb, give the PowerShell to create a gMSA, allow a server group to retrieve its password, and "
                "install and test it on the server. Cite path:line.",
                [r"New-ADServiceAccount", r"PrincipalsAllowedToRetrieveManagedPassword", r"Install-ADServiceAccount"]),
    "h2_applock": ("Using the kb, show T-SQL that takes an exclusive session-owned application lock without waiting, "
                   "fails if it is held, and releases it. Cite path:line.",
                   [r"sp_getapplock", r"(?i)@LockTimeout\s*=\s*0", r"sp_releaseapplock"]),
    "h3_mggraph": ("Using the kb, show how to sign in to Microsoft Graph PowerShell app-only with a certificate and "
                   "call the devices endpoint directly. Cite path:line.",
                   [r"Connect-MgGraph", r"-CertificateThumbprint", r"Invoke-MgGraphRequest"]),
    # cross-topic synthesis: facts from two articles (auth/kerberos, mecm/adminservice)
    "x1_synth": ("Using the kb: a Python CLI must call the ConfigMgr AdminService as the engineer's own identity. Which "
                 "authentication works on ConfigMgr 2509 and later, what does the Python side need before the call, and "
                 "what ConfigMgr permission must the account have? Cite path:line.",
                 [r"(?i)NTLM", r"(?i)requests-gssapi|kinit|TGT", r"(?i)administrative user|admin(istrative)? user"]),
    # off-kb with a fallback allowed: the kb must say it lacks it, then live docs or the web answer
    "o1_offkb": ("How do I run the Kubernetes Cluster Autoscaler on AWS EKS with spot instances? Check the kb first; if "
                 "it lacks this, use live docs or web search and label the source.",
                 [r"(?i)spot", r"(?i)auto ?scaling group|node ?group|ASG"]),
    # host scenarios (HOST below): run in an empty host directory with the kb loaded by --plugin-dir.
    # Partial knowledge: the kb answers one part; the other needs the web. `no-refetch`: no url a kb tool returned
    # was fetched again; `web`: at least one search or fetch filled the gap.
    "p1_partial": ("How long are Entra ID sign-in logs kept with a P1 licence, and how long does Intune keep its audit "
                   "logs? Check the kb first; if it lacks part of this, use live docs or web search for that part and "
                   "label the source.",
                   [r"(?i)\b30\b ?days|30-day", r"(?i)two years|2 years|\b2-year|24 months", "web", "no-refetch"]),
    "p2_partial": ("Where does the Intune EPM agent install itself on a Windows device, and what are the names of its log "
                   "files? Check the kb first; if it lacks part of this, use live docs or web search for that part and "
                   "label the source.",
                   [r"(?i)Microsoft EPM Agent", r"(?i)not (officially )?documented|undocumented|does not (list|name|document)"
                                                r"|doesn.t (list|name|document)|no (official|documented)|not (published|have)", "web", "no-refetch"]),
    # A newer version upstream: the planted kb copy (plant()) says presidio-analyzer 2.2.361 is the latest, retrieved
    # 2026-02-20; PyPI's latest is 2.2.364 (2026-07-22), which still lacks UuidRecognizer (kb/public/privacy/presidio.md).
    "n1_newer": ("Using the kb: what is the latest presidio-analyzer release, and when was it published?",
                 [r"2\.2\.364", r"2\.2\.361", "web"]),
    "n2_newer": ("Using the kb: does presidio-analyzer 2.2.364 include the UuidRecognizer?",
                 [r"(?i)^\W*no\b|2\.2\.364\W+(does not|doesn.t) (include|contain|ship)|(not|isn.t) (included |shipped |present )?"
                  r"in (presidio-analyzer )?\*?\*?2\.2\.364|still unreleased",
                  r"2\.2\.361", "web"]),
    # the same two questions with leave to use the web ("Using the kb:" kept every model inside the kb)
    "n3_newer": ("what is the latest presidio-analyzer release, and when was it published? Check the kb first; use live "
                 "docs or web search where it is not enough, and label the source.", [r"2\.2\.364", r"2\.2\.361", "web"]),
    "n4_newer": ("does presidio-analyzer 2.2.364 include the UuidRecognizer? Check the kb first; use live docs or web "
                 "search where it is not enough, and label the source.", None),
    # An older kb than its remote: the stale clone (stale()) is 3 commits behind the origin/main it follows.
    "k1_stale": ("Using the kb: which Claude Code version added the Elicitation hook? I need this to be current, so also "
                 "tell me how current the kb copy you are using is.",
                 [r"2\.1\.76", "tool:kb_status", r"(?i)\bbehind\b|out of date|outdated|not (up to date|current|the latest)"
                                                  r"|newer commits|pull --ff-only|marketplace update|update (the|your) (kb|plugin|copy)"]),
}
S["n4_newer"] = (S["n4_newer"][0], S["n2_newer"][1])
HOST = {"p1_partial": "current", "p2_partial": "current", "n1_newer": "planted", "n2_newer": "planted",
        "n3_newer": "planted", "n4_newer": "planted", "k1_stale": "stale"}
SCRATCH = os.environ.get("BENCH_SCRATCH") or os.path.join(KB, "_cache", "bench")
STALE_BY = 3
PLANT = [("2.2.364", "2.2.361"), ("2.2.363", "2.2.360")]  # every kb file: the copy's newest release is older
PLANT_PRESIDIO = [("2026-07-22", "2026-02-12"), ("2026-06-28", "2025-09-09"), ("2026-07-27", "2026-02-17"),
                  ("2026-09-23", "2026-02-20"), ("2026-09-26", "2026-02-20")]  # on every line naming presidio
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
MODEL = {"opus": "opus", "sonnet": "sonnet", "haiku": "haiku"}
DELEGATE = (" Delegate the kb lookup to the kb-lookup subagent (Haiku) and only relay its answer; do the live-docs step "
            "yourself only if it reports the kb lacks the answer.")


URL = re.compile(r"https?://[^\s)\]>\"'`,]+")
FETCHERS = ("WebFetch", "microsoft_docs_fetch")  # tools that read one page by url (a docs search reads none)


def norm_url(u):
    """A url as a comparable key: no scheme, www, locale segment, query, fragment or trailing slash; lower case."""
    u = re.sub(r"^https?://(www\.)?", "", u.strip().lower()).split("#")[0].split("?")[0].rstrip("/.")
    return re.sub(r"^(learn\.microsoft\.com)/[a-z]{2}-[a-z]{2}/", r"\1/", u)


def parse(stdout):
    """The stream-json events of one run: tool counts (main and subagents), the call route, every url a kb tool
    returned, the urls a fetch tool read, the number of web and docs searches, and the result event."""
    tools, subs, path, res = Counter(), Counter(), [], None
    names, kb_urls, fetched, searches = {}, set(), [], 0
    for line in stdout.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        content = (ev.get("message") or {}).get("content", []) if isinstance(ev.get("message"), dict) else []
        if ev.get("type") == "assistant":
            for c in content:
                if c.get("type") != "tool_use":
                    continue
                inp = c.get("input") or {}
                name = c["name"] + (":" + inp.get("subagent_type", "") if c["name"] in ("Agent", "Task") else "")
                names[c.get("id")] = c["name"]
                (subs if ev.get("parent_tool_use_id") else tools)[name] += 1
                path.append(("sub:" if ev.get("parent_tool_use_id") else "") + name.replace("mcp__", ""))
                if c["name"].endswith(FETCHERS) and inp.get("url"):
                    fetched.append(inp["url"])
                elif c["name"] == "WebSearch" or c["name"].endswith(("docs_search", "_search_claude_code_docs",
                                                                     "search_model_context_protocol")):
                    searches += 1
        elif ev.get("type") == "user":
            for c in content:
                if isinstance(c, dict) and c.get("type") == "tool_result" and "kb_" in names.get(c.get("tool_use_id"), ""):
                    body = c.get("content")
                    text = body if isinstance(body, str) else " ".join(b.get("text", "") for b in body or [] if isinstance(b, dict))
                    kb_urls.update(norm_url(u) for u in URL.findall(text))
        elif ev.get("type") == "result":
            res = ev
    refetched = sorted({norm_url(u) for u in fetched} & kb_urls)
    return {"tools": dict(tools), "sub_tools": dict(subs), "route": path, "kb_urls": len(kb_urls),
            "fetched": fetched, "refetched": refetched, "searches": searches}, res


def execute(cmd, prompt, cwd=KB, env=None):
    """Run one headless claude and parse its stream: the result fields (or {"error": ...})."""
    t = time.time()
    p = subprocess.run(cmd, cwd=cwd, input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=900,
                       env={**os.environ, **env} if env else None)
    wall = time.time() - t
    seen, res = parse(p.stdout)
    if not res:
        return {"error": p.stderr[-500:]}
    if res.get("is_error") or (not res.get("total_cost_usd") and re.search(r"(?i)hit your (session|usage) limit", res.get("result") or "")):
        return {"error": (res.get("result") or "is_error")[:200]}  # a refused run is void, not a cheap answer
    u = res["usage"]
    return {"wall_s": round(wall, 1), "api_s": round(res["duration_api_ms"] / 1000, 1),
            "cost": round(res["total_cost_usd"], 4), "turns": res["num_turns"],
            "in_uncached": u["input_tokens"], "cache_write": u["cache_creation_input_tokens"],
            "cache_read": u["cache_read_input_tokens"], "out": u["output_tokens"],
            "models": {m: round(v["costUSD"], 4) for m, v in res.get("modelUsage", {}).items()},
            **seen, "answer": res.get("result") or ""}


def add(a, b):
    """Two runs of one question (reader, then escalation) as one row."""
    out = dict(b)
    out["route"] = a.get("route", []) + ["escalate"] + b.get("route", [])
    for k in ("wall_s", "api_s", "cost", "turns", "in_uncached", "cache_write", "cache_read", "out"):
        out[k] = round(a[k] + b[k], 4)
    out["models"] = {m: round(a["models"].get(m, 0) + b["models"].get(m, 0), 4) for m in {*a["models"], *b["models"]}}
    return out


def route(q):
    """kb_ask.py's routing as a benchmark run: tool answers cost nothing; a good pack goes to the tool-less reader,
    whose INSUFFICIENT reply escalates to the researcher (costs summed)."""
    sys.path.insert(0, os.path.join(KB, "_tools"))
    import kb_ask
    t = time.time()
    tool = kb_ask.tool_answer(q)
    if tool is not None:
        return {"wall_s": round(time.time() - t, 1), "api_s": 0, "cost": 0, "turns": 0, "in_uncached": 0,
                "cache_write": 0, "cache_read": 0, "out": 0, "models": {}, "tools": {"kb_ask:tool": 1},
                "sub_tools": {}, "route": ["kb_ask:tool"], "answer": tool}
    p = kb_ask.plan(q)
    stream = ["--output-format", "stream-json", "--verbose"]
    user = kb_ask.prompt(q, p["text"])
    first = None
    if p["kind"] == "good":
        first = execute(kb_ask.claude_argv(p["model"], False)[:2] + stream + kb_ask.claude_argv(p["model"], False)[2:]
                        + ["--append-system-prompt", kb_ask.READER], user)
        first["route"] = [f"pack:{p['kind']}", f"reader:{p['model']}"] + first.get("route", [])
        if "error" in first or not first["answer"].lstrip().startswith(kb_ask.SENTINEL):
            return first
        user += f"\n\nA first reader of this evidence said: {first['answer'].strip().splitlines()[0]}"
    argv = kb_ask.claude_argv("sonnet", True)
    second = execute(argv[:2] + stream + argv[2:] + ["--append-system-prompt", kb_ask.RESEARCHER], user)
    if "error" not in second:
        second["route"] = ([] if first else [f"pack:{p['kind']}"]) + ["researcher:sonnet"] + second.get("route", [])
    return add(first, second) if first and "error" not in second else second


WEB_Q = {  # the same questions without the kb: what a session without it would be asked
    "s1_fact": "What is the default Windows LAPS password length? Cite the source urls.",
    "s2_fact_csv": "Which TCP port does Delivery Optimization use for peer-to-peer traffic? Cite the source urls.",
    "s3_multi": ("Cite the source url for each: (1) default Windows LAPS password length; (2) the Delivery "
                 "Optimization peer-to-peer port; (3) which Claude Code version added the Elicitation hook."),
    "s6_falsegood": ("How do I create and update the Group Policy Central Store with the Windows 11 24H2 ADMX templates? "
                     "Cite the source urls."),
    "s7_web": ("How should the KRBTGT account password be reset safely in an AD domain (how many times, how long between "
               "resets)? Cite the source urls."),
    "s8_falsegood2": "Microsoft Purview Data Loss Prevention endpoint DLP onboarding requirements. Cite the source urls.",
    "h1_gmsa": ("Give the PowerShell to create a gMSA, allow a server group to retrieve its password, and install and "
                "test it on the server. Cite the source urls."),
    "h2_applock": ("Show T-SQL that takes an exclusive session-owned application lock without waiting, fails if it is "
                   "held, and releases it. Cite the source urls."),
    "x1_synth": ("A Python CLI must call the ConfigMgr AdminService as the engineer's own identity. Which authentication "
                 "works on ConfigMgr 2509 and later, what does the Python side need before the call, and what ConfigMgr "
                 "permission must the account have? Cite the source urls."),
    "o1_offkb": "How do I run the Kubernetes Cluster Autoscaler on AWS EKS with spot instances? Cite the source urls.",
}


def web(model, q):
    """A typical web-search session: no kb, no plugins or MCP servers, no project files (an empty directory), only
    WebSearch and WebFetch."""
    empty = os.path.join(KB, "_cache", "bench-web")
    os.makedirs(empty, exist_ok=True)
    cmd = ["claude", "-p", "--output-format", "stream-json", "--verbose", "--no-session-persistence", "--model", model,
           "--strict-mcp-config", "--setting-sources", "project,local", "--allowedTools", "WebSearch", "WebFetch",
           "--disallowedTools", "Bash", "Read", "Grep", "Glob", "Edit", "Write", "Agent", "Skill"]
    return execute(cmd, q, cwd=empty)


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=True).stdout.strip()


def clone(name):
    """A fresh clone of this repository's HEAD at SCRATCH/<name> (replacing one left by an earlier run)."""
    dest = os.path.join(SCRATCH, name)
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(SCRATCH, exist_ok=True)
    subprocess.run(["git", "clone", "--quiet", KB, dest], check=True)
    return dest


def plant(dest):
    """Make the copy at `dest` look retrieved before presidio 2.2.362-2.2.364 shipped: every kb file names 2.2.361
    as the newest release, and the presidio articles and every line that names presidio (data rows, source rows)
    carry February dates."""
    for root, _, files in os.walk(os.path.join(dest, "kb", "public")):
        for f in files:
            if not f.endswith((".md", ".csv")):
                continue
            p = os.path.join(root, f)
            with open(p, encoding="utf-8") as fh:
                text = fh.read()
            new = "".join(_swap(_swap(ln, PLANT), PLANT_PRESIDIO) if "presidio" in f + ln.lower() or "2.2.36" in ln
                          else _swap(ln, PLANT) for ln in text.splitlines(keepends=True))
            if new != text:
                with open(p, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(new)
    return dest


def _swap(s, pairs):
    for a, b in pairs:
        s = s.replace(a, b)
    return s


def stale(dest, by=STALE_BY):
    """Put the remote-tracking branch of the clone at `dest` `by` empty commits ahead of its HEAD, as a fetch that
    brought newer commits would: the copy runs today's code and is `by` commits behind the remote it follows."""
    tip = git("rev-parse", "HEAD", cwd=dest)
    tree = git("rev-parse", "HEAD^{tree}", cwd=dest)
    for i in range(by):
        tip = git("commit-tree", tree, "-p", tip, "-m", f"bench: upstream commit {i + 1}", cwd=dest)
    branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=dest)
    git("update-ref", f"refs/remotes/origin/{branch}", tip, cwd=dest)
    return dest


def kb_copy(kind):
    """The directory a host run loads with --plugin-dir: this repository, or a scratch clone built for the scenario."""
    if kind == "current":
        return KB
    return plant(clone("kb-planted")) if kind == "planted" else stale(clone("kb-stale"))


def host(model, q, kb):
    """A session in another project: an empty host directory, the kb and docs plugins by --plugin-dir, no user
    settings, plugins or claude.ai connectors; the kb index kept in SCRATCH."""
    where = os.path.join(SCRATCH, "host")
    os.makedirs(where, exist_ok=True)
    cmd = ["claude", "-p", "--output-format", "stream-json", "--verbose", "--no-session-persistence", "--model", model,
           "--setting-sources", "project,local", "--plugin-dir", kb,
           "--plugin-dir", os.path.join(KB, ".claude-plugin", "it-ops-kb-docs"),
           "--allowedTools", "mcp__plugin_it-ops-kb_kb", "mcp__plugin_it-ops-kb-docs_microsoft-learn",
           "mcp__plugin_it-ops-kb-docs_claude-code-docs", "mcp__plugin_it-ops-kb-docs_mcp-docs", "WebSearch", "WebFetch"]
    env = {"ENABLE_CLAUDEAI_MCP_SERVERS": "false", "KB_INDEX": os.path.join(SCRATCH, "index")}
    return execute(cmd, q, cwd=where, env=env)


def check(c, r):
    """One answer check: a regex over the answer, or a behaviour read from the tool calls."""
    if c.startswith("tool:"):
        return any(c[5:] in t for t in r["tools"])
    if c == "web":
        return bool(r["fetched"] or r["searches"])
    if c == "no-refetch":
        return not r["refetched"]
    return bool(re.search(c, r["answer"]))


def run(cfg, scen, copies=None):
    q, checks = S[scen]
    if scen in HOST:
        if cfg not in MODEL:
            raise SystemExit(f"{scen} runs only with {', '.join(MODEL)}")
        copies = {} if copies is None else copies
        if HOST[scen] not in copies:
            copies[HOST[scen]] = kb_copy(HOST[scen])
        r = host(MODEL[cfg], q, copies[HOST[scen]])
    elif cfg == "router":
        r = route(q)
    elif cfg.startswith("web-"):
        r = web(MODEL[cfg[4:]], WEB_Q[scen])
    else:
        model = cfg.split("+")[0]
        prompt = q + (DELEGATE if "+delegate" in cfg else "")
        extra = []
        if "+escalate" in cfg:
            extra = ["--agents", json.dumps(AGENTS), "--append-system-prompt", ROUTER]
        if "+strict" in cfg:
            extra += ["--disallowedTools", "mcp__microsoft-learn__microsoft_docs_search",
                      "mcp__microsoft-learn__microsoft_docs_fetch", "mcp__microsoft-learn__microsoft_code_sample_search",
                      "WebSearch", "WebFetch"]
        cmd = ["claude", "-p", "--output-format", "stream-json", "--verbose", "--no-session-persistence",
               "--model", MODEL[model], "--allowedTools", "WebSearch", "WebFetch", "mcp__kb", "Agent",
               "mcp__microsoft-learn__microsoft_docs_search", "mcp__microsoft-learn__microsoft_docs_fetch"] + extra
        r = execute(cmd, prompt)
    r = {"cfg": cfg, "scen": scen, **r}
    if "error" not in r:
        r["checks"] = [check(c, r) for c in checks]
    return r


def summary(paths):
    for f in paths:
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            if "error" in r:
                print(r["cfg"], r["scen"], "ERROR", r["error"][:100])
                continue
            if r["scen"] in S and "fetched" in r:  # re-score with today's checks: a corrected check needs no re-run
                r["checks"] = [check(c, r) for c in S[r["scen"]][1]]
            print(f"{r['cfg']:22} {r['scen']:13} ${r['cost']:.3f} {r['wall_s']:5.0f}s turns={r['turns']} "
                  f"write={r['cache_write']} read={r['cache_read']} out={r['out']} "
                  f"checks={''.join('Y' if c else 'n' for c in r['checks'])} fetched={len(r.get('fetched', []))} "
                  f"refetched={len(r.get('refetched', []))} searches={r.get('searches', 0)} {r['tools']} {r['sub_tools'] or ''}")


def main():
    if sys.argv[1:2] == ["--summary"]:
        return summary(sys.argv[2:])
    out, cfgs, scens = sys.argv[1], sys.argv[2].split(","), sys.argv[3].split(",")
    reps = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    copies = {}  # host scenarios build each scratch kb copy once per invocation
    with open(out, "a", encoding="utf-8", newline="\n") as f:
        for _ in range(reps):
            for cfg in cfgs:
                for s in scens:
                    r = run(cfg, s, copies)
                    f.write(json.dumps(r) + "\n")
                    f.flush()
                    print(cfg, s, r.get("cost"), r.get("wall_s"), r.get("checks"), r.get("tools"), flush=True)


if __name__ == "__main__":
    main()
