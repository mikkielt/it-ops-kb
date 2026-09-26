#!/usr/bin/env python3
"""`kb`: a read-only MCP server over stdio for this knowledge base (stdlib only). The Claude Code plugin starts it.

  python3 _tools/kb_mcp.py            serve on stdin/stdout (newline-delimited JSON-RPC 2.0); logs go to stderr
  python3 _tools/kb_mcp.py --status   print kb_status once and exit (a quick check from a shell)
  python3 _tools/kb_mcp.py --register-local   in a clone: register this server as `kb` and the three documentation
                                     servers of .claude-plugin/it-ops-kb-docs/.mcp.json at local scope (`claude mcp
                                     add --scope local`: this machine and this clone only), skipping names already there

Tools (all read-only; they wrap rag.py and kbfacts.py and read the kb files, never the network):
  kb_pack    the evidence pack for a question, like `rag.py pack`: a coverage verdict (good, weak, none), the best fact
             lines grouped by article with path:line and tag, and one footer of the cited sources' urls. Call it first.
             `questions` (1-6) batches the parts of a multi-part question: a section per part, one shared footer.
             Always loaded (`anthropic/alwaysLoad`): the first lookup needs no tool-search round trip.
  kb_search  BM25 search, like `rag.py search -u`: hits with path:line, heading and text, one footer of the cited
             source ids and their urls, and rag.py's notes ("not found anywhere", "weak match")
  kb_facts   fact lines under a path prefix, optionally only some tag kinds, like `rag.py facts`
  kb_audit   per article: status, retrieved_utc, fact counts by tag kind, linked gap/conflict entries, like `rag.py audit`
  kb_show    lines of a kb file, like `rag.py show PATH:LINE -n N`
  kb_source  source rows by id (legacy S123 or hash S-xxxxxxxx), with superseded_by, like `rag.py src`; `cited`
             adds every file line that names each id
  kb_status  how current this copy is: its commit and date, the latest census-* tag (or _census/ log), source and
             topic counts, the newest retrieved_utc
  kb_topics_for  kb topics that code touches, like `rag.py topics-for`: the curated signals of _tools/signals.csv
             found in the files or text given (paths relative to the host project, CLAUDE_PROJECT_DIR or the cwd)

response_format: `concise` or `detailed` on kb_pack (default detailed: answers need the urls), kb_facts, kb_audit
and kb_search (default concise). Every tool description starts with "Documentation facts from it-ops-kb", so a
host that also has live MECM/AD/Graph tools does not mistake the kb for live data.

Protocol: dual-era, as the MCP stdio transport describes for 2026-07-28. A legacy client's `initialize` gets the
version it asked for when this server knows it (else 2025-11-25), then `tools/list` and `tools/call`; a 2026-07-28
client's `server/discover` gets supportedVersions, and each modern request's `_meta` protocol version is checked
(-32022 UnsupportedProtocolVersionError otherwise). Every result carries `resultType: "complete"`, which 2026-07-28
requires. Only JSON-RPC messages go to stdout; the server exits on EOF.
"""
import contextlib, csv, io, json, os, re, subprocess, sys, threading

TOOLS = os.path.dirname(os.path.abspath(__file__))
KB = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import rag, kbfacts  # noqa: E402

NAME, VERSION = "kb", "1.2.0"
MODERN = "2026-07-28"
LEGACY = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
SUPPORTED = [MODERN, *LEGACY]
PV_KEY = "io.modelcontextprotocol/protocolVersion"
MAX_LINES = 400
INSTRUCTIONS = (
    "it-ops-kb: facts from official sources on Windows endpoint management (DSC v3, ConfigMgr, Intune, Autopilot, "
    "Entra ID, AD, Graph, GPO, Defender, SQL Server, Power BI, GitLab CI, Ansible, security baselines, identity, "
    "Presidio, MCP, Claude Code, AI agents). Call kb_pack with the question first: one call returns a coverage verdict "
    "and the cited fact lines. coverage: good -> answer from the pack; weak -> one reworded kb_pack or one kb_show; "
    "none -> say the kb does not cover it and add nothing from memory. Every fact ends in one tag: DOC (official), DER "
    "(derived), COMMUNITY (non-official) or UNK (not confirmed); UNK and COMMUNITY are leads, not answers. Counts, "
    "lists and 'which files cite X' are kb_audit, kb_facts and kb_source with cited=true, not searches. Cite path:line "
    "and the url from the pack's sources footer. Single facts: call kb_pack yourself; several parts: one kb_pack with "
    "questions=[...]. Use the kb-lookup agent only for multi-part research. Never start a general-purpose agent for a "
    "kb lookup. These tools hold documentation facts, not live device or directory data.")
DOCS = "Documentation facts from it-ops-kb (not live device or directory data). "
FORMAT = {"type": "string", "enum": ["concise", "detailed"],
          "description": "concise: fact lines with path:line and tag, no url footer; detailed: full text and urls"}

READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
TOOL_LIST = [
    {"name": "kb_pack", "title": "Evidence pack for a question",
     "description": DOCS + "Start here. Ranks the kb's fact lines for a question and returns a coverage verdict "
                    "(good, weak, none), the best facts grouped by article with path:line and tag, and one footer of "
                    "the cited sources' urls, within a token budget. A question with several parts: pass them all in "
                    "`questions` (one call, a verdict per part).",
     "inputSchema": {"type": "object", "properties": {
         "question": {"type": "string", "description": "the question as asked, or 3-10 keywords"},
         "questions": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 6,
                       "description": "the parts of a multi-part question, one pack each (instead of question)"},
         "budget": {"type": "integer", "minimum": 200, "maximum": 6000, "default": 1200, "description": "about this many tokens per question"},
         "domain": {"type": "string", "description": "limit to one domain directory, e.g. 'auth'"},
         "response_format": {**FORMAT, "default": "detailed"}},
         "additionalProperties": False},
     "annotations": {"title": "Evidence pack for a question", **READ_ONLY},
     "_meta": {"anthropic/alwaysLoad": True}},
    {"name": "kb_facts", "title": "Fact lines by prefix and tag",
     "description": DOCS + "Every fact line under a path prefix (a domain like 'agents', a topic like 'auth/kerberos', or "
                    "a file), optionally only facts carrying some tag kinds (e.g. UNK, COMMUNITY).",
     "inputSchema": {"type": "object", "properties": {
         "prefix": {"type": "string"},
         "tags": {"type": "array", "items": {"type": "string", "enum": ["DOC", "DER", "COMMUNITY", "UNK"]}},
         "response_format": {**FORMAT, "default": "concise"}},
         "required": ["prefix"], "additionalProperties": False},
     "annotations": {"title": "Fact lines by prefix and tag", **READ_ONLY}},
    {"name": "kb_audit", "title": "Audit articles",
     "description": DOCS + "Per article under a prefix: status, fact counts by tag kind, and the _gaps.md and "
                    "_conflicts.md entries linked to it (named, or via its sources). Use for counts and weak spots.",
     "inputSchema": {"type": "object", "properties": {
         "prefix": {"type": "string", "description": "a domain or topic path; omit for the whole kb"},
         "status": {"type": "string", "enum": ["complete", "partial", "unknown"]},
         "entries": {"type": "boolean", "default": False, "description": "also list the linked ledger entries"},
         "response_format": {**FORMAT, "default": "concise"}},
         "additionalProperties": False},
     "annotations": {"title": "Audit articles", **READ_ONLY}},
    {"name": "kb_search", "title": "Search the kb",
     "description": DOCS + "BM25 search over the kb's articles and data rows. Returns the best chunks with path:line, "
                    "heading, text and cited source ids (urls with detailed), and notes when the match is weak or words "
                    "are found nowhere. Prefer kb_pack.",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string", "description": "3-8 keywords, e.g. 'pim activation latency'"},
         "k": {"type": "integer", "minimum": 1, "maximum": 20, "default": 8, "description": "number of hits"},
         "domain": {"type": "string", "description": "limit to one domain directory, e.g. 'auth' or 'dsc'"},
         "index": {"type": "boolean", "default": False,
                   "description": "also search the root files: _answers.md, _gaps.md, _conflicts.md, README.md"},
         "response_format": {**FORMAT, "default": "concise"}},
         "required": ["query"], "additionalProperties": False},
     "annotations": {"title": "Search the kb", **READ_ONLY}},
    {"name": "kb_show", "title": "Show kb lines",
     "description": DOCS + "Lines of a kb file, numbered: read around a pack or search hit.",
     "inputSchema": {"type": "object", "properties": {
         "path": {"type": "string", "description": "kb-relative path, optionally with :LINE (e.g. 'auth/kerberos.md:42')"},
         "line": {"type": "integer", "minimum": 1, "description": "first line (overrides :LINE)"},
         "n": {"type": "integer", "minimum": 1, "maximum": MAX_LINES, "default": 40, "description": "number of lines"}},
         "required": ["path"], "additionalProperties": False},
     "annotations": {"title": "Show kb lines", **READ_ONLY}},
    {"name": "kb_source", "title": "Resolve source ids",
     "description": DOCS + "Rows of _sources.csv by id (legacy S123 or hash S-xxxxxxxx): url, title, publisher, licence, "
                    "retrieved_utc, version_or_date, superseded_by and the files that cite it.",
     "inputSchema": {"type": "object", "properties": {
         "ids": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 50},
         "cited": {"type": "boolean", "default": False, "description": "also list every file line that names each id"}},
         "required": ["ids"], "additionalProperties": False},
     "annotations": {"title": "Resolve source ids", **READ_ONLY}},
    {"name": "kb_status", "title": "kb freshness",
     "description": DOCS + "How current this copy of the kb is: commit and date, latest census (the date the kb was "
                    "confirmed current), number of sources and topics, newest retrieved_utc.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
     "annotations": {"title": "kb freshness", **READ_ONLY}},
    {"name": "kb_topics_for", "title": "kb topics for code",
     "description": DOCS + "Maps code to kb topics: finds the curated code signals (MSAL classes, AdminService routes, "
                    "Negotiate/SPN, LDAP libraries, Graph scopes, ...) in the files or text given and returns the kb "
                    "topics ranked, with each signal's first path:line. Then kb_facts or kb_pack per topic.",
     "inputSchema": {"type": "object", "properties": {
         "paths": {"type": "array", "items": {"type": "string"}, "maxItems": 200,
                   "description": "files or directories of the code (absolute, or relative to the project directory)"},
         "text": {"type": "string", "description": "code or keywords to map instead of (or as well as) files"}},
         "additionalProperties": False},
     "annotations": {"title": "kb topics for code", **READ_ONLY}},
]


class ToolError(Exception):
    """A tool-level failure: reported to the model as a result with isError, not as a protocol error."""


@contextlib.contextmanager
def guarded():
    """rag.py reports some failures with sys.exit(message); turn those into ToolError and keep its stdout quiet."""
    try:
        with contextlib.redirect_stdout(sys.stderr):
            yield
    except SystemExit as e:
        raise ToolError(str(e.code) if e.code not in (None, 0) else "failed")


# ---------------------------------------------------------------- tools

def kb_search(args):
    query = str(args.get("query") or "").strip()
    if not query:
        raise ToolError("query is empty")
    k = min(max(int(args.get("k") or 8), 1), 20)
    notes = []
    fmt = fmt_of(args, "concise")
    with guarded():
        hits = rag.search(query, k, args.get("domain") or None, bool(args.get("index")), notes)
        if fmt == "detailed":
            rag.add_urls(hits)
    out = [f"note: {n}" for n in notes]
    if not hits:
        out.append(f"no match for {query!r}" + (f" in {args['domain']}/" if args.get("domain") else "")
                   + ": the kb does not cover this (try other words, or index=true for _answers.md and _gaps.md)")
    out.append(rag.format_hits(hits, fmt))
    return "\n".join(out).strip()


def fmt_of(args, default):
    fmt = args.get("response_format") or default
    if fmt not in rag.FORMATS:
        raise ToolError(f"response_format must be one of {', '.join(rag.FORMATS)}")
    return fmt


def kb_pack(args):
    questions = [str(q).strip() for q in (args.get("questions") or []) if str(q).strip()]
    if str(args.get("question") or "").strip():
        questions.insert(0, str(args["question"]).strip())
    if not questions:
        raise ToolError("question is empty")
    if len(questions) > kbfacts.MAX_QUESTIONS:
        raise ToolError(f"at most {kbfacts.MAX_QUESTIONS} questions per call")
    budget = min(max(int(args.get("budget") or 1200), 200), 6000)
    with guarded():
        return kbfacts.pack_many(questions, budget, args.get("domain") or None, fmt_of(args, "detailed"))["text"]


def kb_facts(args):
    prefix = str(args.get("prefix") or "").strip()
    if not prefix:
        raise ToolError("prefix is empty")
    kinds = {str(k).upper() for k in (args.get("tags") or [])}
    fmt = fmt_of(args, "concise")
    with guarded():
        us = [u for u in kbfacts.units(prefix) if u["tags"] and (not kinds or kinds & set(kbfacts.kinds_of(u["tags"])))]
    return rag.format_facts(us, fmt, limit=400)


def kb_audit(args):
    with guarded():
        rows = kbfacts.audit(args.get("prefix") or None, args.get("status") or None)
    if not rows:
        raise ToolError("no article matches")
    return rag.format_audit(rows, bool(args.get("entries")), fmt_of(args, "concise"))


def kb_show(args):
    target = str(args.get("path") or "")
    path, _, line = target.partition(":")
    if args.get("line"):
        line = str(args["line"])
    if line and not line.isdigit():
        raise ToolError(f"{line!r}: line must be a positive number")
    n = min(max(int(args.get("n") or 40), 1), MAX_LINES)
    root = os.path.realpath(KB)
    full = os.path.realpath(os.path.join(root, path))
    if not path or os.path.commonpath([full, root]) != root:
        raise ToolError(f"{path!r}: not a path inside the kb")
    rel = os.path.relpath(full, root)
    if rel.split(os.sep)[0] in (".git", "_private", "_cache") or not os.path.isfile(full):
        raise ToolError(f"{path}: no such kb file")
    with guarded():
        text = rag.read_text(rel)
    if text is None:
        raise ToolError(f"{path}: not readable as UTF-8 text")
    lines = text.splitlines()
    start = max(int(line or 1), 1)
    if start > len(lines):
        raise ToolError(f"{path} has {len(lines)} lines")
    body = [f"{i:>5}  {lines[i - 1]}" for i in range(start, min(start + n, len(lines) + 1))]
    return f"# {rel.replace(os.sep, '/')} lines {start}-{start + len(body) - 1} of {len(lines)}\n" + "\n".join(body)


def kb_source(args):
    ids = [str(i).strip() for i in (args.get("ids") or []) if str(i).strip()]
    if not ids:
        raise ToolError("ids is empty")
    with guarded():
        rows = rag.sources(ids[:50])
        cited = kbfacts.cited_lines([r["id"] for r in rows]) if args.get("cited") else {}
    out = []
    for r in rows:
        if "url" not in r:
            out.append(f"{r['id']}  UNKNOWN id (not in _sources.csv)")
            continue
        out.append(f"{r['id']}  {r.get('title', '')}\n  url: {r['url']}\n  publisher: {r.get('publisher', '')}; "
                   f"licence: {r.get('licence', '')}\n  retrieved_utc: {r.get('retrieved_utc', '')}; "
                   f"version_or_date: {r.get('version_or_date', '')}"
                   + (f"\n  superseded by: {r['superseded_by']}" if (r.get("superseded_by") or "").strip() else "")
                   + (f"\n  used in: {r['used_in'].replace(';', ', ')}" if r.get("used_in") else "")
                   + ("\n" + rag.format_cited(cited.get(r["id"], [])) if args.get("cited") else ""))
    return "\n".join(out)


def git(*args, cwd=KB):
    try:
        p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return p.stdout.strip() if p.returncode == 0 else None


def status():
    """{key: value} describing this copy: a git clone reports its HEAD; an installed plugin copy (no .git, in
    plugins/cache/<marketplace>/<plugin>/<version>/) reports its version, and reads commit dates and tags from the
    marketplace clone Claude Code keeps beside the cache, when that clone has the commit."""
    info = {"kb_root": KB}
    commit = git("rev-parse", "HEAD") if os.path.exists(os.path.join(KB, ".git")) else None
    repo = KB if commit else None
    parts = os.path.normpath(KB).split(os.sep)
    if not commit and len(parts) >= 4 and parts[-4] == "cache":
        info["installed_as"] = f"plugin {parts[-2]}@{parts[-3]}, version {parts[-1]}"
        mkt = os.path.join(os.sep.join(parts[:-4]), "marketplaces", parts[-3])
        if re.fullmatch(r"[0-9a-f]{7,40}", parts[-1]) and os.path.isdir(os.path.join(mkt, ".git")):
            commit = git("rev-parse", "--verify", "-q", parts[-1] + "^{commit}", cwd=mkt)
            repo = mkt if commit else None
            if not commit:
                info["commit"] = parts[-1]
    if commit:
        info["commit"] = commit[:12]
        info["commit_date"] = git("show", "-s", "--format=%cI", commit, cwd=repo) or "unknown"
        info["census_tag"] = git("describe", "--tags", "--abbrev=0", "--match", "census-*", commit, cwd=repo) or "none"
    info.setdefault("commit", "unknown (not a git clone or an installed plugin copy)")
    census_dir = os.path.join(KB, "_census")
    logs = sorted(f[:-4] for f in os.listdir(census_dir) if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.csv", f)) if os.path.isdir(census_dir) else []
    info["census_log"] = f"_census/{logs[-1]}.csv" if logs else "none"
    try:
        with open(os.path.join(KB, "_sources.csv"), encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        dates = sorted(r.get("retrieved_utc", "")[:10] for r in rows if r.get("retrieved_utc"))
        info["sources"] = f"{len(rows)} ({sum(1 for r in rows if (r.get('superseded_by') or '').strip())} superseded)"
        info["newest_retrieved_utc"] = dates[-1] if dates else "none"
        info["oldest_retrieved_utc"] = dates[0] if dates else "none"
    except OSError:
        info["sources"] = "unreadable"
    try:
        with open(os.path.join(KB, "_coverage.csv"), encoding="utf-8", newline="") as f:
            info["topics"] = str(sum(1 for _ in csv.DictReader(f)))
    except OSError:
        pass
    return info


def kb_status(_args):
    return "\n".join(f"{k}: {v}" for k, v in status().items())


def kb_topics_for(args):
    paths = [str(p) for p in (args.get("paths") or []) if str(p).strip()]
    text = str(args.get("text") or "")
    if not paths and not text.strip():
        raise ToolError("give paths or text")
    base = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    with guarded():
        return kbfacts.format_topics_for(kbfacts.topics_for(paths, text, base))


HANDLERS = {"kb_pack": kb_pack, "kb_facts": kb_facts, "kb_audit": kb_audit, "kb_search": kb_search, "kb_show": kb_show, "kb_source": kb_source, "kb_status": kb_status,
            "kb_topics_for": kb_topics_for}


# ---------------------------------------------------------------- protocol

def result(msg_id, res):
    """A JSON-RPC result. 2026-07-28 requires `resultType` on every result (a client drops a tools/list without it);
    earlier revisions allow extra fields, so every result carries it."""
    return {"jsonrpc": "2.0", "id": msg_id, "result": {**res, "resultType": "complete"}}


def error(msg_id, code, message, data=None):
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": msg_id, "error": err}


def server_info():
    return {"name": NAME, "title": "it-ops-kb", "version": VERSION}


def handle(msg):
    """The response to one JSON-RPC message, or None for a notification."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
        return error(msg.get("id") if isinstance(msg, dict) else None, -32600, "Invalid Request")
    method, msg_id, params = msg["method"], msg.get("id"), msg.get("params") or {}
    if "id" not in msg:
        return None  # notifications/initialized, notifications/cancelled, ...: nothing to answer
    if not isinstance(params, dict):
        return error(msg_id, -32602, "params must be an object")
    requested = (params.get("_meta") or {}).get(PV_KEY)
    if requested is not None and requested not in SUPPORTED:
        return error(msg_id, -32022, f"Unsupported protocol version {requested}",
                     {"supported": SUPPORTED, "requested": requested})
    caps = {"tools": {"listChanged": False}}
    if method == "initialize":  # legacy handshake
        want = params.get("protocolVersion")
        return result(msg_id, {"protocolVersion": want if want in LEGACY else LEGACY[0], "capabilities": caps,
                               "serverInfo": server_info(), "instructions": INSTRUCTIONS})
    if method == "server/discover":
        return result(msg_id, {"supportedVersions": SUPPORTED, "capabilities": caps, "instructions": INSTRUCTIONS,
                               "ttlMs": 3600000, "cacheScope": "public",
                               "_meta": {"io.modelcontextprotocol/serverInfo": server_info()}})
    if method == "ping":
        return result(msg_id, {})
    if method == "tools/list":
        return result(msg_id, {"tools": TOOL_LIST, "ttlMs": 3600000, "cacheScope": "public"})
    if method == "tools/call":
        name, args = params.get("name"), params.get("arguments") or {}
        if name not in HANDLERS:
            return error(msg_id, -32602, f"Unknown tool: {name}")
        if not isinstance(args, dict):
            return error(msg_id, -32602, "arguments must be an object")
        try:
            text, is_error = HANDLERS[name](args), False
        except ToolError as e:
            text, is_error = f"error: {e}", True
        except (TypeError, ValueError) as e:
            text, is_error = f"error: bad arguments ({e})", True
        return result(msg_id, {"content": [{"type": "text", "text": text}], "isError": is_error})
    return error(msg_id, -32601, f"Method not found: {method}")


def serve(stdin=None, stdout=None):
    stdin = stdin or io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace")
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            reply = error(None, -32700, "Parse error")
        else:
            if isinstance(msg, list):  # JSON-RPC batches are not part of MCP
                reply = error(None, -32600, "Invalid Request: batches are not supported")
            else:
                try:
                    reply = handle(msg)
                except Exception as e:  # noqa: BLE001 - one bad request must not end the server
                    print(f"kb_mcp: internal error: {type(e).__name__}: {e}", file=sys.stderr)
                    reply = error(msg.get("id") if isinstance(msg, dict) else None, -32603, "Internal error")
        if reply is not None:
            stdout.write(json.dumps(reply, ensure_ascii=False, separators=(",", ":")) + "\n")
            stdout.flush()


DOCS_MCP = os.path.join(KB, ".claude-plugin", "it-ops-kb-docs", ".mcp.json")


def register_local():
    """A clone gets the servers a host gets from the plugins, under the names the clone's settings allow: `kb`
    (tools mcp__kb__*) and the docs servers (mcp__microsoft-learn__*, ...). The root has no .mcp.json because a
    plugin sourced from the root would load it. Returns the exit code."""
    with open(DOCS_MCP, encoding="utf-8") as f:
        servers = {"kb": {"command": sys.executable, "args": [os.path.join(TOOLS, "kb_mcp.py")]}, **json.load(f)["mcpServers"]}
    code = 0
    for name, cfg in servers.items():
        try:
            have = subprocess.run(["claude", "mcp", "get", name], cwd=KB, capture_output=True, text=True, timeout=60)
        except OSError:
            print("the claude CLI is not installed: nothing registered", file=sys.stderr)
            return 1
        if have.returncode == 0:
            print(f"{name}: already registered")
            continue
        p = subprocess.run(["claude", "mcp", "add-json", "--scope", "local", name, json.dumps(cfg)], cwd=KB,
                           capture_output=True, text=True, timeout=60)
        print(f"{name}: " + ("registered (local scope)" if p.returncode == 0 else f"failed: {(p.stderr or p.stdout).strip()}"))
        code = code or p.returncode
    return code


def main():
    if "--register-local" in sys.argv[1:]:
        sys.exit(register_local())
    if "--status" in sys.argv[1:]:
        print(kb_status({}))
        return
    threading.Thread(target=warm, daemon=True).start()
    serve()


def warm():
    """Load (or build) the pack index while the client is still connecting, so the first kb_pack does not wait."""
    try:
        kbfacts.store()  # prints nothing: stdout carries only JSON-RPC (no redirect here, it would be process-wide)
    except Exception as e:  # noqa: BLE001 - a failed warm-up only means the first call builds it
        print(f"kb_mcp: index warm-up failed: {type(e).__name__}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
