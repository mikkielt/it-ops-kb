#!/usr/bin/env python3
"""Agent-layer benchmark of kb lookups (stdlib only; each run is a paid headless `claude -p`).

  agent_bench.py OUT.jsonl CONFIG[,CONFIG] SCENARIO[,SCENARIO] [REPS]
  agent_bench.py --summary OUT.jsonl [OUT.jsonl ...]
  agent_bench.py --route "QUESTION"        the pinned route (`router-pinned`) on one question, its run as one JSON line

Appends one JSON line per run: cost (USD), wall and API seconds, turns, uncached / cache-write / cache-read input
tokens, output tokens, cost per model, tool calls of the main session and of subagents, and a regex check per
expected answer element. CONFIG: `haiku`, `sonnet`, `opus` (that model answers alone; `sonnet-5`,
`sonnet-5-5`, `haiku-4-5`, `haiku-5-5`, `opus-5-5` pin a model id where an alias would follow the newest); `opus+delegate` (asked to hand
the lookup to the Haiku kb-lookup agent); `haiku+escalate` (Haiku told to hand live-docs work to a Sonnet agent
defined with --agents); `+strict` also denies the docs tools (note: the deny reaches subagents too); `router`
(kb_ask.py's routing), `router-pinned` (the same with the routed models as full names); `web-haiku`, `web-sonnet`, `web-opus`,
`web-sonnet-5-5` (a typical web-search session: no kb, no MCP servers, no project files, only WebSearch and WebFetch).

Host scenarios (HOST) run `haiku`, `sonnet` or `opus` in an empty directory under BENCH_SCRATCH (default
_cache/bench) with the kb and docs plugins loaded by --plugin-dir, no user settings or claude.ai connectors:
`p*` partial knowledge (the kb answers one part; a line records the urls fetched and those a kb tool had already
returned, `refetched`), `n*` a newer version upstream (a scratch clone planted with an older presidio release),
`k*` a kb copy behind its remote (a scratch clone whose origin/main is 3 commits ahead). Checks are regexes over the
answer, or `tool:NAME` (a tool called), `web` (a search or fetch) and `no-refetch`.

Every `claude -p` it starts runs with hooks off (`--settings '{"disableAllHooks": true}'`, kbcommon.NO_HOOKS), so no
run is captured, distilled or pushed by the query log of the clone or of a plugin. The kb arms run in this clone with
the `kb` server registered at local scope for it; _tools/benchmarks.py runs this file from a throwaway clone whose
query log is off and whose origin is a local bare repository. Results: kb/_self/reports/benchmarks.md.
"""
import json, os, re, shutil, subprocess, sys, time
from collections import Counter

KB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KB, "_tools"))
from kbcommon import NO_HOOKS  # noqa: E402  every run's hooks are off
S = {
    "s1_fact": ("What is the default Windows LAPS password length? Answer from the kb with citation.", [r"\b14\b"]),
    "s2_fact_csv": ("Which TCP port does Delivery Optimization use for peer-to-peer traffic? Answer from the kb with citation.", [r"7680"]),
    "s3_multi": ("Answer from the kb, cite path:line for each: (1) default Windows LAPS password length; (2) the Delivery "
                 "Optimization peer-to-peer port; (3) which Claude Code version added the Elicitation hook.",
                 [r"\b14\b", r"7680", r"2\.1\.76"]),
    # the count is read from the kb at check time (it was 6, remediations among them, when the scenario was written)
    "s4_count": ("How many intune articles in the kb have status partial? Give the number and list them.",
                 ["count:intune:partial", "list:intune:partial"]),
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
MODEL = {"opus": "opus", "sonnet": "sonnet", "haiku": "haiku",
         # pinned ids, for comparing a new model with the one before it (benchmarks.py's `new-model`)
         "sonnet-5": "claude-sonnet-5", "sonnet-5-5": "claude-sonnet-5-5", "haiku-4-5": "claude-haiku-4-5",
         "haiku-5-5": "claude-haiku-5-5", "opus-5-5": "claude-opus-5-5"}
DELEGATE = (" Delegate the kb lookup to the kb-lookup subagent (Haiku) and only relay its answer; do the live-docs step "
            "yourself only if it reports the kb lacks the answer.")


URL = re.compile(r"https?://[^\s)\]>\"'`,]+")
FETCHERS = ("WebFetch", "microsoft_docs_fetch")  # tools that read one page by url (a docs search reads none)


def norm_url(u):
    """A url as a comparable key: no scheme, www, locale segment, query, fragment or trailing slash; lower case."""
    u = re.sub(r"^https?://(www\.)?", "", u.strip().lower()).split("#")[0].split("?")[0].rstrip("/.")
    return re.sub(r"^(learn\.microsoft\.com)/[a-z]{2}-[a-z]{2}/", r"\1/", u)


CHARS_PER_TOKEN = 4  # what a kb result is counted at when the stream gives no usable growth of the prompt (kb_tokens)


def kb_tokens(reqs, out=None):
    """The tokens of the kb tool results of a run's main-session requests, `reqs` ({usage, results}: the characters of
    each kb result that came back before the request). A result is the growth of the prompt from the request before
    it, less that request's output, at most its characters; a request with no earlier one, or whose prompt did not
    grow, is counted at CHARS_PER_TOKEN characters per token. The messages' own output counts are partial, so `out`,
    the main loop's output count of the result event, is shared by the requests in proportion to them (evenly when
    they are all zero); with no `out` a request's own count is its output."""
    prompt = lambda r: sum(r["usage"].get(k, 0) or 0 for k in ("input_tokens", "cache_creation_input_tokens",  # noqa: E731
                                                                  "cache_read_input_tokens"))
    partial = lambda r: r["usage"].get("output_tokens", 0) or 0  # noqa: E731
    total = sum(partial(r) for r in reqs)
    real = lambda r: partial(r) * out / total if out and total else out / len(reqs) if out else partial(r)  # noqa: E731
    n, prev = 0, None
    for r in reqs:
        chars = sum(r["results"])
        if chars:
            grew = prompt(r) - prompt(prev) - real(prev) if prev else 0
            n += round(min(grew, chars)) if grew > 0 else chars // CHARS_PER_TOKEN
        prev = r
    return n


def parse(stdout):
    """The stream-json events of one run: tool counts (main and subagents), the call route, every url a kb tool
    returned, the urls a fetch tool read, the number of web and docs searches, the main session's requests (`requests`:
    one per message id, its model and usage), the tokens of its kb tool results (`kb_tokens`, which shares the result event's main-loop output count over the
    requests), and the result event."""
    tools, subs, path, res = Counter(), Counter(), [], None
    names, kb_urls, fetched, searches = {}, set(), [], 0
    reqs, waiting = {}, []
    for line in stdout.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if not isinstance(ev, dict):
            continue
        content = (ev.get("message") or {}).get("content", []) if isinstance(ev.get("message"), dict) else []
        if ev.get("type") == "assistant":
            msg = ev["message"] if isinstance(ev.get("message"), dict) else {}
            if msg.get("usage") and not ev.get("parent_tool_use_id"):
                r = reqs.setdefault(msg.get("id") or f"r{len(reqs)}", {"results": waiting})
                if r["results"] is waiting:
                    waiting = []
                r.update(usage=msg["usage"], model=msg.get("model", ""))
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
                    if not ev.get("parent_tool_use_id"):
                        waiting.append(len(text))
        elif ev.get("type") == "result":
            res = ev
    refetched = sorted({norm_url(u) for u in fetched} & kb_urls)
    return {"tools": dict(tools), "sub_tools": dict(subs), "route": path, "kb_urls": len(kb_urls),
            "fetched": fetched, "refetched": refetched, "searches": searches,
            "requests": [{"model": r["model"], "usage": r["usage"]} for r in reqs.values()],
            "kb_tokens": kb_tokens(list(reqs.values()), ((res or {}).get("usage") or {}).get("output_tokens"))}, res


def execute(cmd, prompt, cwd=KB, env=None, clean=False):
    """Run one headless claude and parse its stream: the result fields (or {"error": ...}). `env` is added to this
    process's environment, or with `clean` is the whole environment."""
    t = time.time()
    p = subprocess.run(cmd, cwd=cwd, input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=900,
                       env=env if clean else {**os.environ, **env} if env else None)
    return result_of(p.stdout, p.stderr, time.time() - t)


def result_of(stdout, stderr, wall):
    """The result fields of one run's stream-json `stdout` that took `wall` seconds (or {"error": ...}). The input
    tokens are those of the result event's `usage` (the main loop). `out` is the sum of the event's `modelUsage`
    `outputTokens` (the whole run: subagents and internal calls too, thinking included), else its `usage` output
    count; the `usage` of the stream's messages (`requests`) carries partial output counts, so it gives the model
    and the prompt of each request, not the output. `model_usage` keeps what `modelUsage` bills each model ({model:
    {uncached, cache_write, cache_read, out}}): a WebFetch or WebSearch call runs a model of its own inside the tool
    (Haiku 5.5, whatever the session's model), billed there and in no message of the stream; `web_searches` is the
    searches `modelUsage` bills (`webSearchRequests`), set when the event has a `modelUsage`."""
    seen, res = parse(stdout)
    if not res:
        return {"error": stderr[-500:]}
    if res.get("is_error") or (not res.get("total_cost_usd") and re.search(r"(?i)hit your (session|usage) limit", res.get("result") or "")):
        return {"error": (res.get("result") or "is_error")[:200]}  # a refused run is void, not a cheap answer
    u = res["usage"]
    billed = {m: v for m, v in (res.get("modelUsage") or {}).items() if isinstance(v, dict)}
    counts = [v["outputTokens"] for v in billed.values() if isinstance(v.get("outputTokens"), int)]
    num = lambda v, k: v.get(k) if isinstance(v.get(k), int) else 0  # noqa: E731
    extra = ({"model_usage": {m: {"uncached": num(v, "inputTokens"), "cache_write": num(v, "cacheCreationInputTokens"),
                                  "cache_read": num(v, "cacheReadInputTokens"), "out": num(v, "outputTokens")}
                              for m, v in billed.items()},
              "web_searches": sum(num(v, "webSearchRequests") for v in billed.values())} if billed else {})
    return {"wall_s": round(wall, 1), "api_s": round(res["duration_api_ms"] / 1000, 1),
            "cost": round(res["total_cost_usd"], 4), "turns": res["num_turns"],
            "in_uncached": u["input_tokens"], "cache_write": u["cache_creation_input_tokens"],
            "cache_read": u["cache_read_input_tokens"], "out": sum(counts) if counts else u["output_tokens"],
            "models": {m: round(v["costUSD"], 4) for m, v in res.get("modelUsage", {}).items()},
            **seen, **extra, "answer": res.get("result") or ""}


def add(a, b, sep="escalate"):
    """Two runs of one question (reader, then escalation or the lacks part) as one row; `sep` joins their routes. An
    escalation (`escalate`) keeps the second run's answer, tools and urls alone, as it answered the whole question. A
    split (`and`) answered one part in each run, so the row's answer is both answers (the reader's first, a blank line
    between), its tool counts and searches the sums and its fetched urls both runs' (the refetched ones their union)."""
    out = dict(b)
    out["route"] = a.get("route", []) + [sep] + b.get("route", [])
    if sep == "and":
        out["answer"] = "\n\n".join(x for x in (a.get("answer", "").strip(), b.get("answer", "").strip()) if x)
        for k in ("tools", "sub_tools"):
            out[k] = dict(Counter(a.get(k, {})) + Counter(b.get(k, {})))
        out["fetched"] = a.get("fetched", []) + b.get("fetched", [])
        out["refetched"] = sorted({*a.get("refetched", []), *b.get("refetched", [])})
        for k in ("searches", "kb_urls"):
            out[k] = a.get(k, 0) + b.get(k, 0)
    for k in ("wall_s", "api_s", "cost", "turns", "in_uncached", "cache_write", "cache_read", "out"):
        out[k] = round(a[k] + b[k], 4)
    out["models"] = {m: round(a["models"].get(m, 0) + b["models"].get(m, 0), 4) for m in {*a["models"], *b["models"]}}
    out["requests"] = a.get("requests", []) + b.get("requests", [])
    if "model_usage" in a or "model_usage" in b:
        out["model_usage"] = {m: {k: a.get("model_usage", {}).get(m, {}).get(k, 0) + b.get("model_usage", {}).get(m, {}).get(k, 0)
                                  for k in ("uncached", "cache_write", "cache_read", "out")}
                              for m in {*a.get("model_usage", {}), *b.get("model_usage", {})}}
        out["web_searches"] = a.get("web_searches", 0) + b.get("web_searches", 0)
    for k in ("kb_tokens", "pack_chars"):
        out[k] = a.get(k, 0) + b.get(k, 0)
    return out


PIN = {"haiku": MODEL["haiku-4-5"], "sonnet": MODEL["sonnet-5-5"]}  # the routed aliases as full names (`router-pinned`)


def _stream_argv(model, tools, system):
    """kb_ask.claude_argv as a stream-json run (what execute parses) with `system` appended."""
    import kb_ask
    return kb_ask.claude_argv(model, tools, "stream-json") + ["--verbose", "--append-system-prompt", system]


def _step(model, tools, system, user, steps, cwd=KB, env=None):
    """One run of the route (a stream-json `claude -p` of kb_ask.claude_argv) with `steps` put before its own route;
    `env` is the whole environment of the run."""
    r = execute(_stream_argv(model, tools, system), user, cwd=cwd, env=env, clean=env is not None)
    if "error" not in r:
        r["route"] = steps + r.get("route", [])
    return r


def route(q, pin=None, cwd=KB, env=None):
    """kb_ask.py's routing as a benchmark run, step for step (its plan, prompts and models): tool answers cost nothing;
    a web pack (the kb lacks the question) goes to the researcher (live docs through the kb server's cached docs_search and docs_fetch) with the question,
    what the kb lacks and the nearest articles; a split pack with a `kb has:` and a `kb lacks:` line (a `-` line is empty: kb_ask.has_lacks)
    goes to the Haiku reader for the kb has part and to the researcher for the lacks part (in a pack of several parts,
    each part as its own route sends it: kb_ask.part_routes), their costs summed, and a reader INSUFFICIENT gives the whole question to
    the researcher; a good pack, and a split pack that cannot be divided, go to the tool-less reader with the pack,
    whose INSUFFICIENT escalates to the researcher with the pack. `pin` maps the routed aliases to full model names.
    The route lists `pack:KIND`, then each run (`reader:MODEL`, `researcher:MODEL`), with `escalate` between an
    escalation's two runs and `and` between a split's two. `pack_chars` is the length of the pack the reader is given.
    The runs start in `cwd` with `env` as their whole environment."""
    sys.path.insert(0, os.path.join(KB, "_tools"))
    import kb_ask
    t = time.time()
    tool = kb_ask.tool_answer(q)
    if tool is not None:
        return {"wall_s": round(time.time() - t, 1), "api_s": 0, "cost": 0, "turns": 0, "in_uncached": 0,
                "cache_write": 0, "cache_read": 0, "out": 0, "models": {}, "tools": {"kb_ask:tool": 1},
                "sub_tools": {}, "route": ["kb_ask:tool"], "answer": tool}
    p = kb_ask.plan(q)
    name = lambda m: (pin or {}).get(m, m)  # noqa: E731
    kind, researcher = p["kind"], name("sonnet")
    if kind == "web":
        return _step(researcher, True, kb_ask.WEB_RESEARCHER, kb_ask.web_prompt(q, p),
                     [f"pack:{kind}", f"researcher:{researcher}"], cwd, env)
    divided = kind == "split" and bool(p["has"] and p["lacks"])
    reader = name(p["model"] if kind == "good" else kb_ask.READER_MODEL)
    if divided:
        system, user = kb_ask.SPLIT_READER, kb_ask.split_prompt(q, p)
    else:
        system, user = kb_ask.READER, kb_ask.prompt(q, p["text"])
    first = _step(reader, False, system, user, [f"pack:{kind}", f"reader:{reader}"], cwd, env)
    if "error" in first:
        return first
    first["pack_chars"] = len(p["text"])
    said = first["answer"].strip()
    insufficient = said.startswith(kb_ask.SENTINEL)
    note = f"\n\nA first reader of {'the kb' if divided else 'this'} evidence said: {said.splitlines()[0] if said else ''}"
    if not divided:  # the reader's INSUFFICIENT escalates with the pack
        if not insufficient:
            return first
        system, user = kb_ask.RESEARCHER, kb_ask.prompt(q, p["text"]) + note
    elif insufficient:  # the whole question, no lacks line
        system, user = kb_ask.WEB_RESEARCHER, kb_ask.web_prompt(q, p, whole=True) + note
    else:
        system, user = kb_ask.WEB_RESEARCHER, kb_ask.web_prompt(q, p)
    second = _step(researcher, True, system, user, [f"researcher:{researcher}"], cwd, env)
    return second if "error" in second else add(first, second, "escalate" if insufficient else "and")


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
    "s5_none": ("How do I configure a Kubernetes cluster autoscaler on AWS EKS spot instances? Cite the source urls."),
}


def web(model, q):
    """A typical web-search session: no kb, no plugins or MCP servers, no project files (an empty directory), only
    WebSearch and WebFetch."""
    empty = os.path.join(KB, "_cache", "bench-web")
    os.makedirs(empty, exist_ok=True)
    return execute(web_argv(model), q, cwd=empty)


def web_argv(model):
    return ["claude", "-p", "--output-format", "stream-json", "--verbose", "--no-session-persistence", "--model", model,
            "--strict-mcp-config", "--setting-sources", "project,local", *NO_HOOKS, "--allowedTools", "WebSearch",
            "WebFetch", "--disallowedTools", "Bash", "Read", "Grep", "Glob", "Edit", "Write", "Agent", "Skill"]


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
    env = {"ENABLE_CLAUDEAI_MCP_SERVERS": "false", "KB_INDEX": os.path.join(SCRATCH, "index")}
    return execute(host_argv(model, kb), q, cwd=where, env=env)


def host_argv(model, kb):
    return ["claude", "-p", "--output-format", "stream-json", "--verbose", "--no-session-persistence", "--model", model,
            "--setting-sources", "project,local", *NO_HOOKS, "--plugin-dir", kb,
            "--plugin-dir", os.path.join(KB, ".claude-plugin", "it-ops-kb-docs"),
            "--allowedTools", "mcp__plugin_it-ops-kb_kb", "mcp__plugin_it-ops-kb-docs_microsoft-learn",
            "mcp__plugin_it-ops-kb-docs_claude-code-docs", "mcp__plugin_it-ops-kb-docs_mcp-docs", "WebSearch", "WebFetch"]


def check(c, r):
    """One answer check: a regex over the answer, or a behaviour read from the tool calls."""
    if c.startswith("tool:"):
        return any(c[5:] in t for t in r["tools"])
    if c == "web":
        return bool(r["fetched"] or r["searches"])
    if c == "no-refetch":
        return not r["refetched"]
    if c.startswith(("count:", "list:")):  # count:DOMAIN:STATUS, list:DOMAIN:STATUS against the kb at check time
        kind, domain, status = c.split(":")
        paths = partial_articles(domain, status)
        if kind == "list":
            return all(re.search(re.escape(p.rsplit("/", 1)[-1].removesuffix(".md")), r["answer"]) for p in paths)
        n = len(paths)
        return bool(re.search(rf"\b{n}\b", r["answer"]) or (n == 0 and re.search(r"(?i)\b(no|none|zero)\b", r["answer"])))
    return bool(re.search(c, r["answer"]))


def partial_articles(domain, status):
    """The article paths under `domain` with front-matter `status`, from this clone's kb."""
    import kbfacts
    return sorted(p for p, m in kbfacts.articles().items() if m.get("status") == status
                  and kbfacts.bare(p).split("/", 1)[0] == domain)


def run(cfg, scen, copies=None):
    q, checks = S[scen]
    if scen in HOST:
        if cfg not in MODEL:
            raise SystemExit(f"{scen} runs only with {', '.join(MODEL)}")
        copies = {} if copies is None else copies
        if HOST[scen] not in copies:
            copies[HOST[scen]] = kb_copy(HOST[scen])
        r = host(MODEL[cfg], q, copies[HOST[scen]])
    elif cfg in ("router", "router-pinned"):
        r = route(q, PIN if cfg == "router-pinned" else None)
    elif cfg.startswith("web-"):
        r = web(MODEL[cfg[4:]], WEB_Q[scen])
    else:
        r = execute(kb_argv(cfg), q + (DELEGATE if "+delegate" in cfg else ""))
    r = {"cfg": cfg, "scen": scen, **r}
    if "error" not in r:
        r["checks"] = [check(c, r) for c in checks]
    return r


def kb_argv(cfg):
    """A kb arm in this clone: the model alone (`haiku`, `sonnet`, `opus`), or with `+delegate`, `+escalate`,
    `+strict`; the user's plugins and the clone's local-scope servers load as in a person's session."""
    extra = []
    if "+escalate" in cfg:
        extra = ["--agents", json.dumps(AGENTS), "--append-system-prompt", ROUTER]
    if "+strict" in cfg:
        extra += ["--disallowedTools", "mcp__microsoft-learn__microsoft_docs_search",
                  "mcp__microsoft-learn__microsoft_docs_fetch", "mcp__microsoft-learn__microsoft_code_sample_search",
                  "WebSearch", "WebFetch"]
    return ["claude", "-p", "--output-format", "stream-json", "--verbose", "--no-session-persistence", *NO_HOOKS,
            "--model", MODEL[cfg.split("+")[0]], "--allowedTools", "WebSearch", "WebFetch", "mcp__kb", "Agent",
            "mcp__microsoft-learn__microsoft_docs_search", "mcp__microsoft-learn__microsoft_docs_fetch"] + extra


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
    if sys.argv[1:2] == ["--route"]:  # one question through the pinned route, its run as one JSON line (benchmarks.py pool)
        print(json.dumps(route(sys.argv[2], PIN)))
        return
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
