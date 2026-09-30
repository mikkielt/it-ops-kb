#!/usr/bin/env python3
"""`kb`: a read-only MCP server over stdio for this knowledge base (stdlib only). The Claude Code plugin starts it.

  python3 _tools/kb_mcp.py            serve on stdin/stdout (newline-delimited JSON-RPC 2.0); logs go to stderr
  python3 _tools/kb_mcp.py --status   print kb_status once and exit (a quick check from a shell)
  python3 _tools/kb_mcp.py --roots NAME[,NAME]   serve (or --status) only the named roots, repository roots or
                                     KB_ROOTS directories; an unknown name stops the start with an error on stderr
  python3 _tools/kb_mcp.py --register-local   in a clone: register this server as `kb` and the three documentation
                                     servers of .claude-plugin/it-ops-kb-docs/.mcp.json at local scope (`claude mcp
                                     add --scope local`: this machine and this clone only), skipping names already there

Tools (all read-only; the kb_* tools wrap rag.py and kbfacts.py and read the kb files, never the network):
  kb_pack    the evidence pack for a question, like `rag.py pack`: a coverage verdict (good, weak, none), the best fact
             lines grouped by article with path:line and tag, and one footer of the cited sources' urls. Call it first.
             `questions` (1-6) batches the parts of a multi-part question: a section per part, one shared footer.
             Always loaded (`anthropic/alwaysLoad`): the first lookup needs no tool-search round trip.
  kb_search  line search on the pack index, like `rag.py search -u`: hits with path:line, heading and text, one footer of the cited
             source ids and their urls, and rag.py's notes ("not found anywhere", "weak match")
  kb_facts   fact lines under a path prefix, optionally only some tag kinds, like `rag.py facts`
  kb_audit   per article: status, retrieved_utc, fact counts by tag kind, linked gap/conflict entries, like `rag.py audit`
  kb_show    lines of a kb file, like `rag.py show PATH:LINE -n N`
  kb_source  source rows by id (legacy S123 or hash S-xxxxxxxx), with superseded_by, like `rag.py src`; `cited`
             adds every file line that names each id
  kb_status  how current this copy is: its commit and date, the latest census-* tag (or _census/ log), source and
             topic counts, the newest retrieved_utc, the roots it serves, and how many commits it is behind the branch
             it follows (a clone's upstream, or an installed plugin's marketplace clone; local refs, never the
             network) with the update command. When it is behind, kb_pack opens with one `kb copy:` line saying so.
             A server limited to named roots (--roots; kb_http.py always is) serves clients outside the team:
             kb_status and that line then name no local path and no update command (behind_note).
  kb_topics_for  kb topics that code touches, like `rag.py topics-for`: the curated signals of each root's signals.csv
             found in the files or text given (paths relative to the host project, CLAUDE_PROJECT_DIR or the cwd);
             imports=true matches only the packages the files declare (imports, manifests), not comments or strings;
             a server limited to named roots (--roots) refuses paths, which would read its own files, and takes text

Live docs (the unlimited stdio server only: off under --roots and with KB_LIVE_DOCS=0, and kb_http.py never serves them): two more tools call the remote
documentation servers of .claude-plugin/it-ops-kb-docs/.mcp.json over Streamable HTTP and keep each answer 7 days on disk
(`_cache/live-docs/`, or ${CLAUDE_PLUGIN_DATA}/live-docs; KB_DOCS_CACHE names another directory), keyed by server, tool
and arguments; an older entry is fetched again, an error is never stored:
  docs_search  server (microsoft-learn, claude-code-docs, mcp-docs) + query: the server's search tool
  docs_fetch   server + target: microsoft-learn's page fetch (target = page url), or the other two servers' read-only
               filesystem tool (target = a command such as `head -200 /path/page.mdx`)

One server serves every root (kb/public, a team's kb/<name>/, the KB_ROOTS directories), or only those --roots
names, in every tool and kb_status: paths and topics print qualified (`public/intune/x.md:12`), and kb_pack,
kb_search, kb_facts and kb_audit take an optional `root`, one of the served roots.

response_format: `concise` or `detailed` on kb_pack (default detailed: answers need the urls), kb_facts, kb_audit
and kb_search (default concise). Every tool description starts with "Documentation facts from it-ops-kb", so a
host that also has live MECM/AD/Graph tools does not mistake the kb for live data.

Protocol: dual-era, as the MCP stdio transport describes for 2026-07-28. A legacy client's `initialize` gets the
version it asked for when this server knows it (else 2025-11-25), then `tools/list` and `tools/call`; a 2026-07-28
client's `server/discover` gets supportedVersions, and each modern request's `_meta` protocol version is checked
(-32022 UnsupportedProtocolVersionError otherwise). Every result carries `resultType: "complete"`, which 2026-07-28
requires. Only JSON-RPC messages go to stdout; the server exits on EOF.
"""
import contextlib, csv, hashlib, http.client, io, json, os, re, subprocess, sys, threading, time
import urllib.error, urllib.request

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import rag, kbcommon, kbfacts  # noqa: E402

NAME, VERSION = "kb", "1.3.0"
MODERN = "2026-07-28"
LEGACY = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
SUPPORTED = [MODERN, *LEGACY]
PV_KEY = "io.modelcontextprotocol/protocolVersion"
MAX_LINES = 400
INSTRUCTIONS = (
    "it-ops-kb: cited facts from official sources on Windows endpoint management (ConfigMgr, Intune, Autopilot, "
    "Entra ID, AD, Graph, GPO, Defender, DSC v3, SQL Server, Power BI, GitLab CI, Ansible, Python tooling, baselines, "
    "identity, Presidio), MCP, Claude Code and AI agents. Call kb_pack first (several parts: questions=[...]). "
    "coverage good: answer from the pack (with a check: line, only if a cited line answers it); weak: one reworded "
    "kb_pack or one kb_show; none or a route: line: state what the kb has and lacks, research the rest in the live "
    "docs, label it live docs, not in the kb; never from memory. Tags: DOC official, CODE source code at a pinned "
    "commit (implementation, not a promise), DER derived; COMMUNITY and UNK are leads, not answers. Cite path:line "
    "and the footer url. Counts, lists, who cites X: kb_audit, kb_facts, kb_source cited=true. Never start a "
    "general-purpose agent for a lookup; the kb-lookup agent only for long research. Documentation facts, not live "
    "device or directory data.")
DOCS = "Documentation facts from it-ops-kb (not live device or directory data). "
ROOT = {"type": "string", "description": "one root, e.g. 'public'"}
FORMAT = {"type": "string", "enum": ["concise", "detailed"],
          "description": "concise: no url footer"}

READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
TOOL_LIST = [
    {"name": "kb_pack", "title": "Evidence pack for a question",
     "description": DOCS + "Start here: a coverage verdict (good, weak, none), the best fact lines by article "
                    "with path:line and tag, and a footer of source urls.",
     "inputSchema": {"type": "object", "properties": {
         "question": {"type": "string", "description": "the question, or 3-10 keywords"},
         "questions": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 6,
                       "description": "parts of a multi-part question, a verdict each (instead of question)"},
         "budget": {"type": "integer", "minimum": 200, "maximum": 6000, "default": 1200, "description": "tokens per part"},
         "domain": {"type": "string", "description": "one domain, e.g. 'auth'"},
         "root": ROOT,
         "response_format": {**FORMAT, "default": "detailed"}},
         "additionalProperties": False},
     "annotations": READ_ONLY,
     "_meta": {"anthropic/alwaysLoad": True}},
    {"name": "kb_facts", "title": "Fact lines by prefix and tag",
     "description": DOCS + "Every fact line under a path prefix (a domain like 'agents', a topic like 'auth/kerberos', or "
                    "a file), optionally only facts carrying some tag kinds (e.g. UNK, COMMUNITY).",
     "inputSchema": {"type": "object", "properties": {
         "prefix": {"type": "string"},
         "tags": {"type": "array", "items": {"type": "string", "enum": ["DOC", "CODE", "DER", "COMMUNITY", "UNK"]}},
         "root": ROOT,
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
         "root": ROOT,
         "response_format": {**FORMAT, "default": "concise"}},
         "additionalProperties": False},
     "annotations": {"title": "Audit articles", **READ_ONLY}},
    {"name": "kb_search", "title": "Search the kb",
     "description": DOCS + "Search over every line of the kb's articles and data rows (the pack's ranking, at most 2 "
                    "hits per file). Returns the best lines with path:line, heading, text and cited source ids (urls with detailed), and notes when the match is weak or words "
                    "are found nowhere. Prefer kb_pack.",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string", "description": "3-8 keywords, e.g. 'pim activation latency'"},
         "k": {"type": "integer", "minimum": 1, "maximum": 20, "default": 8, "description": "number of hits"},
         "domain": {"type": "string", "description": "limit to one domain directory, e.g. 'auth' or 'dsc'"},
         "root": ROOT,
         "index": {"type": "boolean", "default": False,
                   "description": "also search each root's ledgers (_answers.md, _gaps.md, _conflicts.md, _coverage.csv), README.md and the kb's own docs (kb/_self/)"},
         "response_format": {**FORMAT, "default": "concise"}},
         "required": ["query"], "additionalProperties": False},
     "annotations": {"title": "Search the kb", **READ_ONLY}},
    {"name": "kb_show", "title": "Show kb lines",
     "description": DOCS + "Lines of a kb file, numbered: read around a pack or search hit.",
     "inputSchema": {"type": "object", "properties": {
         "path": {"type": "string", "description": "a path as the tools print it, optionally with :LINE (e.g. 'public/auth/kerberos.md:42')"},
         "line": {"type": "integer", "minimum": 1, "description": "first line (overrides :LINE)"},
         "n": {"type": "integer", "minimum": 1, "maximum": MAX_LINES, "default": 40, "description": "number of lines"}},
         "required": ["path"], "additionalProperties": False},
     "annotations": {"title": "Show kb lines", **READ_ONLY}},
    {"name": "kb_source", "title": "Resolve source ids",
     "description": DOCS + "Rows of _sources.csv by id (legacy S123 or hash S-xxxxxxxx): url, title, publisher, licence, reuse, "
                    "retrieved_utc, version_or_date, superseded_by and the files that cite it.",
     "inputSchema": {"type": "object", "properties": {
         "ids": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 50},
         "cited": {"type": "boolean", "default": False, "description": "also list every file line that names each id"}},
         "required": ["ids"], "additionalProperties": False},
     "annotations": {"title": "Resolve source ids", **READ_ONLY}},
    {"name": "kb_status", "title": "kb freshness",
     "description": DOCS + "How current this copy of the kb is: commit and date, latest census (the date the kb was "
                    "confirmed current), number of sources and topics, newest retrieved_utc, the roots it serves, and how many "
                    "commits it is behind the kb it follows (as of the last fetch) with the update command.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
     "annotations": {"title": "kb freshness", **READ_ONLY}},
    {"name": "kb_topics_for", "title": "kb topics for code",
     "description": DOCS + "Maps code to kb topics: finds the curated code signals (MSAL classes, AdminService routes, "
                    "Negotiate/SPN, LDAP libraries, Graph scopes, ...) in the files or text given and returns the kb "
                    "topics ranked, with each signal's first path:line. Then kb_facts or kb_pack per topic.",
     "inputSchema": {"type": "object", "properties": {
         "paths": {"type": "array", "items": {"type": "string"}, "maxItems": 200,
                   "description": "files or directories of the code (absolute, or relative to the project directory)"},
         "text": {"type": "string", "description": "code or keywords to map instead of (or as well as) files"},
         "imports": {"type": "boolean", "description": "match only declared packages, not comments or strings"}},
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
    except kbcommon.RootError as e:  # a malformed ROOT_FILE, or two roots sharing a name or an id prefix
        raise ToolError(str(e))


# ---------------------------------------------------------------- tools

def kb_search(args):
    query = str(args.get("query") or "").strip()
    if not query:
        raise ToolError("query is empty")
    k = min(max(int(args.get("k") or 8), 1), 20)
    notes = []
    fmt = fmt_of(args, "concise")
    with guarded():
        hits = rag.search(query, k, domain_of(args), bool(args.get("index")), notes, root_of(args))
        if fmt == "detailed":
            rag.add_urls(hits)
    out = [f"note: {n}" for n in notes]
    if not hits:
        out.append(f"no match for {query!r}" + (f" in {args['domain']}/" if args.get("domain") else "")
                   + ": the kb does not cover this (try other words, or index=true for _answers.md and _gaps.md)")
    out.append(rag.format_hits(hits, fmt))
    return "\n".join(out).strip()


def root_of(args):
    """The `root` argument, checked against the roots this server serves (None when absent)."""
    name = str(args.get("root") or "").strip()
    if name and name not in {r.name for r in kbcommon.roots()}:
        raise ToolError(f"no root {name!r}; roots: {', '.join(r.name for r in kbcommon.roots())}")
    return name or None


def domain_of(args):
    """The `domain` argument as the kb spells it (`Intune` is `intune`), None when absent; a domain no path is
    under is an error that lists the domains, never a pack or search narrowed to nothing."""
    raw = str(args.get("domain") or "").strip()
    if not raw:
        return None
    d = kbfacts.domain_prefix(raw)
    if d is None:
        raise ToolError(f"no domain {raw!r}; omit domain, or use one of: {', '.join(kbfacts.domains())}")
    return d


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
        text = kbfacts.pack_many(questions, budget, domain_of(args), fmt_of(args, "detailed"), root_of(args))["text"]
    note = behind_note()
    return f"{note}\n\n{text}" if note else text


def behind_note():
    """One line for kb_pack when this copy is behind the branch it follows (local refs, no network), else "":
    a model asked how current the kb is answered from the facts' dates without calling kb_status ("Partial
    knowledge, newer versions and stale copies" in kb/_self/reports/benchmarks.md). Recomputed at most once a
    minute. KB_NO_UPSTREAM=1 turns it off: the tests pack on a checkout whose upstream moves on its own (CI).

    Who sees what: the team's own server (the plugin, a clone, no --roots) names the update command, which holds
    the clone's absolute path. A server limited to named roots (limited(): --roots, and kb_http.py always) answers
    clients outside the team, who can neither run that command nor need the path: its line keeps the staleness, so
    a remote agent still says newer facts may exist, and names no upstream, path or command."""
    if os.environ.get("KB_NO_UPSTREAM") == "1":
        return ""
    now = time.time()
    if now - _BEHIND[0] > 60:
        home, commit, repo, _ = copy_commit()
        up = upstream(repo, commit, plugin=repo != home) if commit else {}
        if not up.get("stale"):
            note = ""
        elif limited():
            note = f"kb copy: {up['behind_upstream']} behind the kb it follows; newer facts may exist. Tell the user."
        else:
            note = (f"kb copy: {up['behind_upstream']} behind {up['upstream']}; newer facts may exist. Tell the "
                    f"user, and to update: {up['update'].split(' (')[0]}.")
        _BEHIND[:] = [now, note]
    return _BEHIND[1]


def limited():
    """True when this server is limited to named roots (--roots; kb_http.py always is): its clients are outside the
    team, so kb_status and kb_pack name no local path and no update command."""
    return bool(kbcommon.serving())


_BEHIND = [0.0, ""]


def kb_facts(args):
    prefix = str(args.get("prefix") or "").strip()
    if not prefix:
        raise ToolError("prefix is empty")
    kinds = {str(k).upper() for k in (args.get("tags") or [])}
    fmt = fmt_of(args, "concise")
    with guarded():
        us = [u for u in kbfacts.units(kbfacts.scope(prefix, root_of(args)))
              if u["tags"] and (not kinds or kinds & set(kbfacts.kinds_of(u["tags"])))]
    return rag.format_facts(us, fmt, limit=400)


def kb_audit(args):
    with guarded():
        rows = kbfacts.audit(args.get("prefix") or None, args.get("status") or None, root_of(args))
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
    full = kbfacts.locate(path) if path else ""
    if not path or not kbfacts.showable(full):
        raise ToolError(f"{path!r}: not a path inside the kb")
    rel = shown_path(full)
    if {".git", "_private", "_cache"} & set(rel.split("/")) or not os.path.isfile(full):
        raise ToolError(f"{path}: no such kb file")
    with guarded():
        text = rag.read_text(full)
    if text is None:
        raise ToolError(f"{path}: not readable as UTF-8 text")
    lines = text.splitlines()
    start = max(int(line or 1), 1)
    if start > len(lines):
        raise ToolError(f"{path} has {len(lines)} lines")
    body = [f"{i:>5}  {lines[i - 1]}" for i in range(start, min(start + n, len(lines) + 1))]
    return f"# {rel} lines {start}-{start + len(body) - 1} of {len(lines)}\n" + "\n".join(body)


def shown_path(full):
    """How the tools name an absolute path: qualified inside a root (`public/auth/kerberos.md`), else relative to
    this repository (kb/_self docs, README.md)."""
    for r in kbcommon.roots():
        base = os.path.realpath(r.path)
        if os.path.commonpath([full, base]) == base:
            return kbcommon.qualify(r, os.path.relpath(full, base))
    return os.path.relpath(full, os.path.realpath(kbcommon.HOME)).replace(os.sep, "/")


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
                   f"licence: {r.get('licence', '')}; reuse: {r.get('reuse', '')}\n  retrieved_utc: {r.get('retrieved_utc', '')}; "
                   f"version_or_date: {r.get('version_or_date', '')}"
                   + (f"\n  superseded by: {r['superseded_by']}" if (r.get("superseded_by") or "").strip() else "")
                   + (f"\n  used in: {r['used_in'].replace(';', ', ')}" if r.get("used_in") else "")
                   + ("\n" + rag.format_cited(cited.get(r["id"], [])) if args.get("cited") else ""))
    return "\n".join(out)


# A local git call (no remote is contacted) that outlasts this is taken as failed. 10 s was too short on a loaded
# Windows host: a marketplace clone's rev-parse timed out and kb_status reported the version as the commit.
GIT_TIMEOUT_S = 60


def git(*args, cwd=kbcommon.HOME):
    """git's stripped stdout, or None when it fails, is missing or outlasts GIT_TIMEOUT_S."""
    try:
        p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                           timeout=GIT_TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return None
    return p.stdout.strip() if p.returncode == 0 else None


def copy_commit():
    """(home, commit, repo holding it, {installed_as, commit}) for this copy: a git clone's HEAD, or an installed
    plugin copy's version resolved in the marketplace clone Claude Code keeps beside the cache (plugins/cache/
    <marketplace>/<plugin>/<version>/); commit None when neither has it."""
    extra = {}
    home = kbcommon.HOME  # the clone or plugin copy that holds the kb
    commit = git("rev-parse", "HEAD", cwd=home) if os.path.exists(os.path.join(home, ".git")) else None
    repo = home if commit else None
    parts = os.path.normpath(home).split(os.sep)
    if not commit and len(parts) >= 4 and parts[-4] == "cache":
        extra["installed_as"] = f"plugin {parts[-2]}@{parts[-3]}, version {parts[-1]}"
        mkt = os.path.join(os.sep.join(parts[:-4]), "marketplaces", parts[-3])
        if re.fullmatch(r"[0-9a-f]{7,40}", parts[-1]):
            if os.path.isdir(os.path.join(mkt, ".git")):
                commit = git("rev-parse", "--verify", "-q", parts[-1] + "^{commit}", cwd=mkt)
                repo = mkt if commit else None
            if not commit:  # no marketplace clone has it (a local directory marketplace keeps none): the version is the commit
                extra["commit"] = parts[-1]
    return home, commit, repo, extra


def status():
    """{key: value} describing this copy: a git clone reports its HEAD; an installed plugin copy (no .git, in
    plugins/cache/<marketplace>/<plugin>/<version>/) reports its version, and reads commit dates and tags from the
    marketplace clone Claude Code keeps beside the cache, when that clone has the commit."""
    info = {} if limited() else {"kb_dir": kbcommon.KB_DIR}  # an absolute local path: the team's own server only
    home, commit, repo, extra = copy_commit()
    info.update(extra)
    if commit:
        info["commit"] = commit[:12]
        info["commit_date"] = git("show", "-s", "--format=%cI", commit, cwd=repo) or "unknown"
        info["census_tag"] = git("describe", "--tags", "--abbrev=0", "--match", "census-*", commit, cwd=repo) or "none"
        info.update((k, v) for k, v in upstream(repo, commit, plugin=repo != home).items() if k != "stale")
    info.setdefault("commit", "unknown (not a git clone or an installed plugin copy)")
    pub = kbcommon.public()
    census_dir = os.path.join(pub.path, kbcommon.CENSUS_DIR)
    served = pub in kbcommon.roots()  # a server limited to other roots (--roots) reports no public census log
    logs = sorted(f[:-4] for f in os.listdir(census_dir) if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.csv", f)) \
        if served and os.path.isdir(census_dir) else []
    info["census_log"] = kbcommon.qualify(pub, f"{kbcommon.CENSUS_DIR}/{logs[-1]}.csv") if logs else "none"
    try:
        rows = list(kbfacts.source_rows().values())
        dates = sorted(r.get("retrieved_utc", "")[:10] for r in rows if r.get("retrieved_utc"))
        info["sources"] = f"{len(rows)} ({sum(1 for r in rows if (r.get('superseded_by') or '').strip())} superseded)"
        info["newest_retrieved_utc"] = dates[-1] if dates else "none"
        info["oldest_retrieved_utc"] = dates[0] if dates else "none"
    except OSError:
        info["sources"] = "unreadable"
    counts = root_counts()
    if any(t is not None for t, _ in counts.values()):
        info["topics"] = str(sum(t or 0 for t, _ in counts.values()))
    info["roots"] = "; ".join(f"{r.name} (prefix {r.id_prefix}, {r.visibility}, {counts[r.name][0] or 0} topics, "
                              f"{counts[r.name][1]} sources)" for r in kbcommon.roots())
    return info


def upstream(repo, commit, plugin):
    """How far `commit` is behind the branch its copy follows, from local refs only (the tools never contact a
    remote): a clone's upstream branch (or origin/HEAD, origin/main), or the HEAD of the marketplace clone Claude
    Code keeps for an installed plugin, which marketplace updates move. {} when there is none. `stale` is True when
    it is behind; `update`, the command that brings it level, only on an unlimited server (limited()), since it
    names the clone's path. A clone detached at a census tag is told to check out the newest census tag, not to
    pull."""
    target = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}", cwd=repo)
    if not target:
        target = "HEAD" if plugin else next((r for r in ("origin/HEAD", "origin/main")
                                             if git("rev-parse", "--verify", "-q", r, cwd=repo)), None)
    counts = git("rev-list", "--left-right", "--count", f"{commit}...{target}", cwd=repo) if target else None
    if not counts:
        return {}
    ahead, behind = (int(n) for n in counts.split())
    gitdir = git("rev-parse", "--absolute-git-dir", cwd=repo) or ""
    marks = [os.path.join(gitdir, "FETCH_HEAD")] + ([os.path.join(gitdir, "logs", "refs", "remotes", *target.split("/"))]
                                                    if target != "HEAD" else [os.path.join(gitdir, "logs", "HEAD")])
    seen = max((os.path.getmtime(m) for m in marks if os.path.isfile(m)), default=None)
    name = "marketplace clone" if plugin and target == "HEAD" else target
    out = {"upstream": name + (f", last fetched {time.strftime('%Y-%m-%d', time.gmtime(seen))}" if seen else ""),
           "behind_upstream": f"{behind} commits" + (f", {ahead} ahead" if ahead else "")}
    if behind:
        out["stale"] = True
        if not limited():
            cmd = "/plugin marketplace update, then /reload-plugins" if plugin else \
                census_update(repo, commit) or f"git -C {repo} pull --ff-only"
            out["update"] = cmd + " (this copy is older than the kb it follows)"
    return out


def census_update(repo, commit):
    """The update command for a clone whose HEAD is detached at a census-* tag (a host pinned to a confirmed kb),
    where `pull` fails: check out the newest census tag it has, or fetch the tags first when it is at the newest.
    None when HEAD is on a branch or at no census tag."""
    here = (git("tag", "--points-at", commit, "--list", "census-*", cwd=repo) or "").split()
    if not here or git("symbolic-ref", "-q", "HEAD", cwd=repo):
        return None
    newest = (git("tag", "--list", "census-*", "--sort=-v:refname", cwd=repo) or "").split()[:1]
    if newest and newest[0] not in here:
        return f"git -C {repo} checkout {newest[0]}"
    return f"git -C {repo} fetch --tags, then check out the newest census-* tag"


def root_counts():
    """{root name: (topics in its _coverage.csv or None, rows in its _sources.csv)}."""
    out = {}
    for r in kbcommon.roots():
        topics = srcs = None
        for name in (kbcommon.COVERAGE_CSV, kbcommon.SOURCES):
            try:
                with open(os.path.join(r.path, name), encoding="utf-8-sig", newline="") as f:
                    n = sum(1 for _ in csv.DictReader(f))
            except OSError:
                n = None
            if name == kbcommon.COVERAGE_CSV:
                topics = n
            else:
                srcs = n or 0
        out[r.name] = (topics, srcs)
    return out


def kb_status(_args):
    return "\n".join(f"{k}: {v}" for k, v in status().items())


def kb_topics_for(args):
    paths = [str(p) for p in (args.get("paths") or []) if str(p).strip()]
    text = str(args.get("text") or "")
    if not paths and not text.strip():
        raise ToolError("give paths or text")
    if paths and limited():
        # a server limited by --roots answers clients outside the team: reading their paths would read the server's
        # own files, outside the served roots
        raise ToolError("paths is off on a server limited to named roots (--roots); give text")
    base = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    with guarded():
        return kbfacts.format_topics_for(kbfacts.topics_for(paths, text, base, imports=args.get("imports") is True))


HANDLERS = {"kb_pack": kb_pack, "kb_facts": kb_facts, "kb_audit": kb_audit, "kb_search": kb_search, "kb_show": kb_show, "kb_source": kb_source, "kb_status": kb_status,
            "kb_topics_for": kb_topics_for}


# ---------------------------------------------------------------- live docs

DOCS_TTL_S = 7 * 24 * 3600  # a cached answer is served for 7 days, then fetched again
DOCS_TIMEOUT_S = 60
DOCS_PROTOCOL = "2025-11-25"
# per server, the remote tool each kind of call reaches and the argument that carries the text. Only these are called:
# never a server's submit_feedback (it posts text outside this repository).
LIVE_SERVERS = {
    "microsoft-learn": {"search": ("microsoft_docs_search", "query"), "fetch": ("microsoft_docs_fetch", "url")},
    "claude-code-docs": {"search": ("search_claude_code_docs", "query"),
                         "fetch": ("query_docs_filesystem_claude_code_docs", "command")},
    "mcp-docs": {"search": ("search_model_context_protocol", "query"),
                 "fetch": ("query_docs_filesystem_model_context_protocol", "command")},
}


def live_enabled():
    """True for the team's own stdio server (main() sets LIVE_ON when no --roots limits it) unless KB_LIVE_DOCS=0;
    kb_http.py never sets it, so a remote client cannot make this machine fetch pages or fill its cache."""
    return LIVE_ON[0] and os.environ.get("KB_LIVE_DOCS") != "0"


LIVE_ON = [False]


def docs_urls():
    """{server: url} from the docs plugin's .mcp.json, the one place the urls live."""
    try:
        with open(DOCS_MCP, encoding="utf-8") as f:
            servers = json.load(f)["mcpServers"]
    except (OSError, ValueError, KeyError) as e:
        raise ToolError(f"cannot read the docs servers from {os.path.basename(DOCS_MCP)}: {e}")
    return {n: c["url"] for n, c in servers.items() if isinstance(c, dict) and c.get("url")}


def docs_cache_dir():
    where = os.environ.get("KB_DOCS_CACHE")
    return where or os.path.join(os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.join(kbcommon.HOME, "_cache"), "live-docs")


def docs_cache_key(server, tool, arguments):
    canonical = json.dumps([server, tool, arguments], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def docs_cache_read(key, now):
    """(text, fetched) stored under `key` when it is younger than DOCS_TTL_S (and not from the future), else None: a
    missing, unreadable or expired entry is fetched again."""
    try:
        with open(os.path.join(docs_cache_dir(), key + ".json"), encoding="utf-8") as f:
            entry = json.load(f)
        fetched, text = float(entry["fetched"]), entry["text"]
        return (text, fetched) if isinstance(text, str) and 0 <= now - fetched < DOCS_TTL_S else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def docs_cache_write(key, server, tool, arguments, text, now):
    """Store one answer with the time it was fetched. Best effort: a cache that cannot be written only costs a refetch."""
    entry = {"server": server, "tool": tool, "arguments": arguments, "fetched": now,
             "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)), "text": text}
    folder = docs_cache_dir()
    try:
        os.makedirs(folder, exist_ok=True)
        tmp = os.path.join(folder, f"{key}.{os.getpid()}.tmp")
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(entry, f, ensure_ascii=False)
        os.replace(tmp, os.path.join(folder, key + ".json"))
    except OSError as e:
        print(f"kb_mcp: live-docs cache not written: {e}", file=sys.stderr)


def sse_messages(body):
    """The JSON-RPC messages in a text/event-stream body: each event's `data:` lines joined by newlines."""
    out, data = [], []
    for line in body.splitlines() + [""]:
        if line.startswith("data:"):
            data.append(line[6:] if line.startswith("data: ") else line[5:])
        elif not line and data:
            try:
                out.append(json.loads("\n".join(data)))
            except ValueError:
                pass
            data = []
    return out


class RemoteMcp:
    """A minimal Streamable HTTP MCP client (the 2025-11-25 handshake): POST initialize; keep the `Mcp-Session-Id` the
    server returns and send it, with the negotiated `MCP-Protocol-Version`, on every later request; POST
    notifications/initialized; then tools/call. A reply is application/json or text/event-stream; either yields the
    JSON-RPC message whose id matches the request."""

    def __init__(self, url, timeout=DOCS_TIMEOUT_S):
        self.url, self.timeout, self.session, self.version, self.next_id = url, timeout, None, None, 0

    def post(self, message):
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                   "User-Agent": "it-ops-kb-live-docs/1"}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        if self.version:
            headers["MCP-Protocol-Version"] = self.version
        req = urllib.request.Request(self.url, data=json.dumps(message).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                body = r.read().decode("utf-8", "replace")
                ctype = (r.headers.get_content_type() or "").lower()
                session = r.headers.get("Mcp-Session-Id")
        except urllib.error.HTTPError as e:
            raise ToolError(f"{self.url}: HTTP {e.code}")
        except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError) as e:  # ValueError: a malformed url
            raise ToolError(f"{self.url}: {getattr(e, 'reason', e)}")
        if session:
            self.session = session
        if "id" not in message:  # a notification: 202, no body to read
            return None
        for m in sse_messages(body) if ctype == "text/event-stream" else self.json_messages(body):
            if isinstance(m, dict) and m.get("id") == message["id"]:
                return m
        raise ToolError(f"{self.url}: no reply to {message.get('method')}")

    @staticmethod
    def json_messages(body):
        try:
            data = json.loads(body)
        except ValueError:
            return []
        return data if isinstance(data, list) else [data]

    def request(self, method, params):
        self.next_id += 1
        reply = self.post({"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params})
        if "error" in reply:
            err = reply["error"]
            raise ToolError(f"{self.url}: {method}: {err.get('message', err) if isinstance(err, dict) else err}")
        return reply.get("result") or {}

    def start(self):
        init = self.request("initialize", {"protocolVersion": DOCS_PROTOCOL, "capabilities": {},
                                           "clientInfo": {"name": "it-ops-kb", "version": VERSION}})
        self.version = init.get("protocolVersion") or DOCS_PROTOCOL
        self.post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def call(self, tool, arguments):
        """The text of a tools/call result; an isError result or an empty one is a ToolError (never cached)."""
        res = self.request("tools/call", {"name": tool, "arguments": arguments})
        text = "\n".join(c.get("text", "") for c in res.get("content") or [] if isinstance(c, dict) and c.get("type") == "text")
        if res.get("isError"):
            raise ToolError(f"{self.url}: {tool} failed: {text.strip()[:300]}")
        if not text.strip():
            raise ToolError(f"{self.url}: {tool} returned no text")
        return text


def docs_call(args, kind):
    """One live-docs call: the cache first, else the remote server. The text comes under a one-line header naming the
    server, the fetch date and whether it came from the cache."""
    server = str(args.get("server") or "").strip()
    if server not in LIVE_SERVERS:
        raise ToolError(f"server must be one of {', '.join(LIVE_SERVERS)}")
    field = "query" if kind == "search" else "target"
    value = str(args.get(field) or "").strip()
    if not value:
        raise ToolError(f"{field} is empty")
    tool, arg_name = LIVE_SERVERS[server][kind]
    arguments = {arg_name: value}
    key, now = docs_cache_key(server, tool, arguments), time.time()
    hit = docs_cache_read(key, now)
    if hit:
        text, fetched, how = hit[0], hit[1], "from the cache, "
    else:
        url = docs_urls().get(server)
        if not url:
            raise ToolError(f"{server}: no url in {os.path.basename(DOCS_MCP)}")
        client = RemoteMcp(url)
        client.start()
        text, fetched, how = client.call(tool, arguments), now, ""
        docs_cache_write(key, server, tool, arguments, text, now)
    when = time.strftime("%Y-%m-%d", time.gmtime(fetched))
    return f"live docs, not in the kb: {server} {tool} ({how}fetched {when}; kept {DOCS_TTL_S // 86400} days)\n\n{text}"


def docs_search(args):
    return docs_call(args, "search")


def docs_fetch(args):
    return docs_call(args, "fetch")


LIVE_DOCS = "Live documentation from a remote docs server (not kb facts, not live device or directory data), kept 7 days on disk. "
SERVER_PROP = {"type": "string", "enum": list(LIVE_SERVERS),
               "description": "microsoft-learn (Microsoft products), claude-code-docs (Claude Code), mcp-docs (the MCP specification)"}
LIVE_ANNOTATIONS = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
LIVE_TOOL_LIST = [
    {"name": "docs_search", "title": "Search the live docs",
     "description": LIVE_DOCS + "Search one docs server; the same server and query again within 7 days is answered from "
                    "disk. Use when kb_pack has no answer; label the answer live docs, not in the kb.",
     "inputSchema": {"type": "object", "properties": {"server": SERVER_PROP, "query": {"type": "string", "description": "search text"}},
                     "required": ["server", "query"], "additionalProperties": False},
     "annotations": {"title": "Search the live docs", **LIVE_ANNOTATIONS}},
    {"name": "docs_fetch", "title": "Read a live docs page",
     "description": LIVE_DOCS + "Read one page: microsoft-learn takes the page url; claude-code-docs and mcp-docs take a "
                    "read-only command on their docs filesystem, e.g. `head -200 /path/page.mdx`. Cached like docs_search.",
     "inputSchema": {"type": "object", "properties": {"server": SERVER_PROP, "target": {
         "type": "string", "description": "microsoft-learn: the page url; the others: a command such as `head -200 /path/page.mdx`"}},
         "required": ["server", "target"], "additionalProperties": False},
     "annotations": {"title": "Read a live docs page", **LIVE_ANNOTATIONS}},
]
LIVE_HANDLERS = {"docs_search": docs_search, "docs_fetch": docs_fetch}


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
        return result(msg_id, {"tools": TOOL_LIST + (LIVE_TOOL_LIST if live_enabled() else []), "ttlMs": 3600000,
                               "cacheScope": "public"})
    if method == "tools/call":
        name, args = params.get("name"), params.get("arguments") or {}
        handlers = {**HANDLERS, **LIVE_HANDLERS} if live_enabled() else HANDLERS
        if name not in handlers:
            return error(msg_id, -32602, f"Unknown tool: {name}")
        if not isinstance(args, dict):
            return error(msg_id, -32602, "arguments must be an object")
        try:
            text, is_error = handlers[name](args), False
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


DOCS_MCP = os.path.join(kbcommon.HOME, ".claude-plugin", "it-ops-kb-docs", ".mcp.json")


def register_local():
    """A clone gets the servers a host gets from the plugins, under the names the clone's settings allow: `kb`
    (tools mcp__kb__*) and the docs servers (mcp__microsoft-learn__*, ...). The root has no .mcp.json because a
    plugin sourced from the root would load it. Returns the exit code."""
    with open(DOCS_MCP, encoding="utf-8") as f:
        servers = {"kb": {"command": sys.executable, "args": [os.path.join(TOOLS, "kb_mcp.py")]}, **json.load(f)["mcpServers"]}
    code = 0
    for name, cfg in servers.items():
        try:
            have = subprocess.run(["claude", "mcp", "get", name], cwd=kbcommon.HOME, capture_output=True, text=True, encoding="utf-8", timeout=60)
        except OSError:
            print("the claude CLI is not installed: nothing registered", file=sys.stderr)
            return 1
        if have.returncode == 0:
            print(f"{name}: already registered")
            continue
        p = subprocess.run(["claude", "mcp", "add-json", "--scope", "local", name, json.dumps(cfg)], cwd=kbcommon.HOME,
                           capture_output=True, text=True, encoding="utf-8", timeout=60)
        print(f"{name}: " + ("registered (local scope)" if p.returncode == 0 else f"failed: {(p.stderr or p.stdout).strip()}"))
        code = code or p.returncode
    return code


def main():
    # JSON-RPC over stdio is UTF-8 with "\n" line ends on every OS; Windows would otherwise write the locale code page
    # and "\r\n"
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    if "--register-local" in sys.argv[1:]:
        sys.exit(register_local())
    try:
        kbcommon.serve_only(roots_arg(sys.argv[1:]))
    except (ValueError, kbcommon.RootError) as e:
        print(f"kb_mcp: {e}", file=sys.stderr)
        sys.exit(2)
    if "--status" in sys.argv[1:]:
        print(kb_status({}))
        return
    # the team's own stdio server offers the live-docs tools; a server limited to named roots (--roots: a host's child, which
    # serves clients outside the team) and kb_http.py, which calls handle() alone, do not
    LIVE_ON[0] = not limited()
    threading.Thread(target=warm, daemon=True).start()
    serve()


def roots_arg(argv):
    """The names `--roots NAME[,NAME]` (or `--roots=...`) gives, [] without the flag; ValueError when it names
    none."""
    names = None
    for i, a in enumerate(argv):
        if a == "--roots":
            names = argv[i + 1] if i + 1 < len(argv) else ""
        elif a.startswith("--roots="):
            names = a.split("=", 1)[1]
    if names is None:
        return []
    out = [n.strip() for n in names.split(",") if n.strip()]
    if not out:
        raise ValueError("--roots needs one or more root names: --roots NAME[,NAME]")
    return out


def warm():
    """Load (or build) the pack index while the client is still connecting, so the first kb_pack does not wait."""
    try:
        kbfacts.store()  # prints nothing: stdout carries only JSON-RPC (no redirect here, it would be process-wide)
    except Exception as e:  # noqa: BLE001 - a failed warm-up only means the first call builds it
        print(f"kb_mcp: index warm-up failed: {type(e).__name__}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
