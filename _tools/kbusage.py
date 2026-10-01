#!/usr/bin/env python3
"""Exact token usage of one prompt, read from a Claude Code session transcript (kb/_self/usage.md). Standard library
only; no model and no network.

  kbusage.py TRANSCRIPT [--prompt PROMPT_ID]   the usage record of each prompt of a transcript (or of one), as JSON
                                               lines: the numbers the query log's sidecar keeps, nothing else
  kbusage.py tree PATH [--format json] [--top N]
                                               tool results of a transcript with its subagents/*.jsonl, or of every
                                               transcript of a project directory: calls and characters by tool, Bash
                                               command head, file path and agent, with the totals checked against the
                                               transcripts' usage (exit 1 when they do not add up, 2 for no input)

prompt_usage(transcript_path, prompt_id) is what the query log's distill calls: a dict of counts, tool groups and
model ids, or None when the transcript cannot be read or holds no request of the prompt.
"""
import argparse, json, os, re, shlex, sys
from pathlib import Path

READER_VERSION = 1
STEPS_MAX = 30
BLOCK = 1 << 16
COUNT_KEYS = ("requests", "in", "cw", "cw1h", "cr", "out")
MODEL = re.compile(r"claude-[a-z0-9][a-z0-9.-]{0,60}(?:\[1m\])?")
KB_TOOL = re.compile(r"mcp__(?:kb|plugin_it-ops-kb_kb)__(\w+)$")
DOCS_TOOL = re.compile(r"mcp__(?:plugin_it-ops-kb-docs_)?(microsoft-learn|claude-code-docs|mcp-docs)__\w+$")
BUILTIN = ("Agent", "Task", "Bash", "PowerShell", "Read", "Write", "Edit", "MultiEdit", "NotebookEdit", "Glob", "Grep",
           "WebFetch", "WebSearch", "Skill", "ToolSearch", "TodoWrite", "LSP")
AGENTS = {"general-purpose": "general-purpose", "Explore": "Explore", "Plan": "Plan", "kb-lookup": "kb-lookup",
          "it-ops-kb:kb-lookup": "kb-lookup", "kb-reviewer": "kb-reviewer", "it-ops-kb:kb-reviewer": "kb-reviewer"}
OTHER_AGENT = "other"
GROUPS = ("tool", "bash", "file", "agent")
SHELLS = ("Bash", "PowerShell")
FILE_TOOLS = {"Read": "file_path", "Write": "file_path", "Edit": "file_path", "MultiEdit": "file_path",
              "NotebookEdit": "notebook_path"}
CHARS_PER_TOKEN = 4  # the estimate shown for result characters
TOKEN_SPAN_MAX = 16  # the most characters one token spans on average: the bound the totals check uses
TREE_DOC = "Tool results of a transcript tree, by tool, Bash command head, file path and agent."
ASSIGN = re.compile(r"[A-Za-z_]\w*=.*")
PREFIXES = ("sudo", "time", "env", "nohup", "command", "exec")
SKIPPED = ("cd", "pushd", "export", "set", "unset", "source", ".", "true", "false", ":")
PYTHON = re.compile(r"py(?:thon[\d.]*)?(?:\.exe)?")
SUBCOMMANDS = ("git", "gh", "glab", "docker", "kubectl", "npm", "pip", "pip3", "uv", "cargo", "go", "claude")
SUBWORD = re.compile(r"[a-z][a-z-]*")
WORKTREE = re.compile(r"/\.claude/worktrees/[^/]+")
TOOL_GROUP = re.compile(r"kb_\w{1,40}|docs:(?:microsoft-learn|claude-code-docs|mcp-docs)|mcp:other|other|"
                        + "|".join(BUILTIN))


def tool_group(name):
    """The group a tool name is kept as: a kb tool's own name, `docs:<server>` for the three documentation
    servers, a built-in tool's name, `mcp:other` for any other MCP tool, else `other`."""
    name = name if isinstance(name, str) else ""
    m = KB_TOOL.fullmatch(name)
    if m:
        return m.group(1)
    m = DOCS_TOOL.fullmatch(name)
    if m:
        return "docs:" + m.group(1)
    if name in BUILTIN:
        return name
    return "mcp:other" if name.startswith("mcp__") else "other"


def model_of(m):
    return m if isinstance(m, str) and MODEL.fullmatch(m) else "other"


def agent_group(agent_type):
    return AGENTS.get(agent_type, OTHER_AGENT)


def _int(v):
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else 0


def counts_of(usage):
    """The counts of one request's `usage`: uncached input, cache write (and its one-hour part), cache read,
    output."""
    u = usage if isinstance(usage, dict) else {}
    cc = u.get("cache_creation") if isinstance(u.get("cache_creation"), dict) else {}
    return {"in": _int(u.get("input_tokens")), "cw": _int(u.get("cache_creation_input_tokens")),
            "cw1h": _int(cc.get("ephemeral_1h_input_tokens")), "cr": _int(u.get("cache_read_input_tokens")),
            "out": _int(u.get("output_tokens"))}


def total_input(c):
    return c["in"] + c["cw"] + c["cr"]


def loads(line):
    try:
        obj = json.loads(line)
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def tail_lines(path):
    """The lines of a file, last first, read from the end in blocks."""
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        pos, rest = f.tell(), b""
        while pos > 0:
            step = min(BLOCK, pos)
            pos -= step
            f.seek(pos)
            chunk = f.read(step) + rest
            parts = chunk.split(b"\n")
            rest = parts[0]
            for p in reversed(parts[1:]):
                if p.strip():
                    yield p.decode("utf-8", "replace")
        if rest.strip():
            yield rest.decode("utf-8", "replace")


def prompt_slice(path, prompt_id):
    """The records of the main transcript from the last user record of another prompt before `prompt_id`'s records to
    the end, in file order."""
    got, seen = [], False
    for line in tail_lines(path):
        r = loads(line)
        if r is None:
            continue
        got.append(r)
        pid = r.get("promptId")
        if r.get("type") == "user" and isinstance(pid, str):
            if pid == prompt_id:
                seen = True
            elif seen:
                break
    got.reverse()
    return got if seen else []


def owned(records, prompt_id):
    """The records a prompt owns: every record after a user record of the prompt and before a user record of another
    prompt."""
    current = None
    for r in records:
        pid = r.get("promptId")
        if r.get("type") == "user" and isinstance(pid, str):
            current = pid
        if current == prompt_id:
            yield r


def requests(records, sidechain=False):
    """[(request id, model, counts)] in the order the requests first appear; a request's several records (one per
    content block) count once, with the most output any of them reports. Records without an API request (a
    synthetic model, no usage) are left out, and so are sidechain records unless `sidechain` (a subagent's file)."""
    order, by = [], {}
    for r in records:
        if r.get("type") != "assistant" or bool(r.get("isSidechain")) != sidechain:
            continue
        msg = r.get("message") if isinstance(r.get("message"), dict) else {}
        rid, usage = r.get("requestId"), msg.get("usage")
        if not isinstance(rid, str) or not isinstance(usage, dict) or msg.get("model") == "<synthetic>":
            continue
        c = counts_of(usage)
        if rid not in by:
            order.append(rid)
            by[rid] = (model_of(msg.get("model")), c)
        elif c["out"] > by[rid][1]["out"]:
            by[rid] = (by[rid][0], c)
    return [(rid, *by[rid]) for rid in order]


def add(models, model, c):
    m = models.setdefault(model, dict.fromkeys(COUNT_KEYS, 0))
    m["requests"] += 1
    for k in COUNT_KEYS[1:]:
        m[k] += c[k]


def result_chars(content):
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(len(b.get("text", "")) for b in content if isinstance(b, dict) and isinstance(b.get("text"), str))
    return 0


def steps(records):
    """[{tools, grow}] of the main chain: per request that tool results answered, each result's tool group, whether it
    succeeded and its length in characters, and `grow`, how much the next request's input (uncached + cache write +
    cache read) exceeds this one's; no `grow` for the last request or when the context shrank (a compaction)."""
    names, events, seen = {}, [], set()
    for r in records:
        if r.get("isSidechain"):
            continue
        msg = r.get("message") if isinstance(r.get("message"), dict) else {}
        content = msg.get("content") if isinstance(msg.get("content"), list) else []
        if r.get("type") == "assistant":
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_use" and isinstance(b.get("id"), str):
                    names[b["id"]] = b.get("name")
            rid = r.get("requestId")
            if isinstance(rid, str) and rid not in seen and isinstance(msg.get("usage"), dict) \
                    and msg.get("model") != "<synthetic>":
                seen.add(rid)
                events.append(("req", total_input(counts_of(msg["usage"]))))
        elif r.get("type") == "user":
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    events.append(("res", {"tool": tool_group(names.get(b.get("tool_use_id"))),
                                           "ok": not b.get("is_error"), "chars": result_chars(b.get("content"))}))
    out, cur = [], None
    for kind, v in events:
        if kind == "req":
            if cur is not None and cur["tools"]:
                if v >= cur["_at"]:
                    cur["grow"] = v - cur["_at"]
                out.append(cur)
            cur = {"tools": [], "_at": v}
        elif cur is not None:
            cur["tools"].append(v)
    if cur is not None and cur["tools"]:
        out.append(cur)
    return [{k: s[k] for k in ("tools", "grow") if k in s} for s in out]


def subagent_files(path, prompt_id):
    """[(agent group, file)] of the subagent transcripts beside a main transcript whose first record belongs to the
    prompt."""
    d = Path(path).with_suffix("") / "subagents"
    out = []
    try:
        files = sorted(d.glob("agent-*.jsonl"))
    except OSError:
        return out
    for f in files:
        try:
            with open(f, encoding="utf-8", errors="replace") as fh:
                first = loads(fh.readline() or "")
        except OSError:
            continue
        if not first or first.get("promptId") != prompt_id:
            continue
        meta = {}
        try:
            meta = json.loads(f.with_suffix(".meta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        out.append((agent_group(meta.get("agentType") if isinstance(meta, dict) else None), f))
    return out


def read_all(path):
    out = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                r = loads(line)
                if r is not None:
                    out.append(r)
    except OSError:
        pass
    return out


def prompt_usage(transcript_path, prompt_id):
    """The usage record of one prompt: `main` and `sub` ({model: counts}, `sub` by agent group), `start` (the input of
    the prompt's first request), `steps` (at most STEPS_MAX, with `cut` counting the rest); None when the transcript
    cannot be read or holds no request of the prompt."""
    if not (isinstance(transcript_path, str) and transcript_path and isinstance(prompt_id, str) and prompt_id):
        return None
    try:
        mine = list(owned(prompt_slice(transcript_path, prompt_id), prompt_id))
    except OSError:
        return None
    reqs = requests(mine)
    if not reqs:
        return None
    main = {}
    for _, model, c in reqs:
        add(main, model, c)
    sub = {}
    for group, f in subagent_files(transcript_path, prompt_id):
        for _, model, c in requests(read_all(f), sidechain=True):
            add(sub.setdefault(group, {}), model, c)
    st = steps(mine)
    rec = {"main": main, "start": total_input(reqs[0][2])}
    if sub:
        rec["sub"] = sub
    if st:
        rec["steps"] = st[:STEPS_MAX]
    if len(st) > STEPS_MAX:
        rec["cut"] = len(st) - STEPS_MAX
    return rec


def prompt_ids(path):
    """The prompt ids of a main transcript's user records, in order, each once."""
    out = []
    for r in read_all(path):
        pid = r.get("promptId")
        if r.get("type") == "user" and not r.get("isSidechain") and isinstance(pid, str) and pid not in out:
            out.append(pid)
    return out


def subagent_scope(f):
    """The agent group of a subagent transcript, from the meta file beside it."""
    try:
        meta = json.loads(f.with_suffix(".meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        meta = None
    return agent_group(meta.get("agentType") if isinstance(meta, dict) else None)


def tree_files(path):
    """[(scope, file)] of a tree: each main transcript (`main`) followed by its subagents' transcripts (their agent
    group), for one transcript or for every `*.jsonl` directly in a directory."""
    path = Path(path)
    mains = sorted(path.glob("*.jsonl")) if path.is_dir() else [path]
    out = []
    for f in mains:
        out.append(("main", f))
        try:
            subs = sorted((f.with_suffix("") / "subagents").glob("agent-*.jsonl"))
        except OSError:
            subs = []
        out += [(subagent_scope(s), s) for s in subs]
    return out


def _segments(command):
    """The words of each simple command of a shell command line, split at newlines and at `; & | ( ) < >`."""
    for line in command.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        lex = shlex.shlex(line, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        try:
            words = list(lex)
        except ValueError:
            words = line.split()
        seg = []
        for w in words:
            if w and set(w) <= set(lex.punctuation_chars):
                if seg:
                    yield seg
                    seg = []
            else:
                seg.append(w)
        if seg:
            yield seg


def command_head(command):
    """What a shell command is called in a rollup: its first command with `cd`, `export`, assignments and `sudo` left
    out; for Python the script (last two path parts) or `-m module` and a bare subcommand word after it, for the tools
    in SUBCOMMANDS the subcommand."""
    for seg in _segments(command if isinstance(command, str) else ""):
        while seg and (ASSIGN.fullmatch(seg[0]) or seg[0].replace("\\", "/").rsplit("/", 1)[-1] in PREFIXES):
            seg = seg[1:]
        if not seg or seg[0] in SKIPPED:
            continue
        first = seg[0].replace("\\", "/").rsplit("/", 1)[-1]
        rest = seg[1:]
        if PYTHON.fullmatch(first):
            head = [first]
            while rest:
                w, rest = rest[0], rest[1:]
                if w == "-m" and rest:
                    return " ".join(head + ["-m " + rest[0]])
                if w == "-c":
                    head.append("-c")
                    return " ".join(head)
                if w.startswith("-"):
                    continue
                head.append("/".join(w.replace("\\", "/").split("/")[-2:]))
                break
            else:
                return " ".join(head)
            if rest and SUBWORD.fullmatch(rest[0]):
                head.append(rest[0])
            return " ".join(head)
        if first in SUBCOMMANDS:
            sub, i = None, 0
            while i < len(rest):
                if rest[i] in ("-C", "-c"):  # git's options with a value
                    i += 2
                elif rest[i].startswith("-"):
                    i += 1
                else:
                    sub = rest[i]
                    break
            return first + (" " + sub if sub and SUBWORD.fullmatch(sub) else "")
        return first
    return "(none)"


def file_key(path, cwd):
    """A file path as a rollup keys it: `/` separators, a worktree's directory collapsed into the project's, and
    relative to the session's working directory when it lies under it."""
    p = WORKTREE.sub("", path.replace("\\", "/"))
    c = WORKTREE.sub("", cwd.replace("\\", "/")).rstrip("/") if isinstance(cwd, str) else ""
    return p[len(c) + 1:] if c and p.startswith(c + "/") else p


def tool_key(name):
    """The tool of a rollup row: the usage groups' name, but an MCP tool of no group by its own name."""
    g = tool_group(name)
    return name if g in ("mcp:other", "other") and isinstance(name, str) and name else g


class Tree:
    """The tally of a tree's tool results: rows by group, results by tool use, requests once each."""

    def __init__(self):
        self.rows, self.uses_seen, self.rids = {}, set(), set()
        self.transcripts = {"main": 0, "sub": 0}
        self.calls = self.chars = self.errors = self.unmatched = self.no_result = 0
        self.usage = {"main": dict.fromkeys(COUNT_KEYS, 0), "sub": dict.fromkeys(COUNT_KEYS, 0)}

    def row(self, group, key, chars, error):
        r = self.rows.setdefault((group, key), [0, 0, 0])
        r[0] += 1
        r[1] += chars
        r[2] += int(error)

    def scan(self, scope, path):
        records = read_all(path)
        side = "main" if scope == "main" else "sub"
        self.transcripts[side] += 1
        uses = {}
        for r in records:
            if scope == "main" and r.get("isSidechain"):
                continue
            msg = r.get("message") if isinstance(r.get("message"), dict) else {}
            content = msg.get("content") if isinstance(msg.get("content"), list) else []
            for b in content:
                if not isinstance(b, dict):
                    continue
                if r.get("type") == "assistant" and b.get("type") == "tool_use" and isinstance(b.get("id"), str):
                    uses[b["id"]] = (b.get("name"), b.get("input") if isinstance(b.get("input"), dict) else {},
                                     r.get("cwd"))
                elif r.get("type") == "user" and b.get("type") == "tool_result":
                    self.result(scope, uses, b)
        self.no_result += sum(1 for i in uses if i not in self.uses_seen)
        for rid, model, c in requests(records, sidechain=side == "sub"):
            if rid not in self.rids:
                self.rids.add(rid)
                u = self.usage[side]
                u["requests"] += 1
                for k in COUNT_KEYS[1:]:
                    u[k] += c[k]

    def result(self, scope, uses, b):
        tid = b.get("tool_use_id")
        if isinstance(tid, str):
            if tid in self.uses_seen:
                return
            self.uses_seen.add(tid)
        name, inp, cwd = uses.get(tid, (None, {}, None))
        if tid not in uses:
            self.unmatched += 1
        chars, error = result_chars(b.get("content")), bool(b.get("is_error"))
        self.calls += 1
        self.chars += chars
        self.errors += int(error)
        self.row("tool", tool_key(name), chars, error)
        self.row("agent", scope, chars, error)
        if name in SHELLS:
            self.row("bash", command_head(inp.get("command")), chars, error)
        if name in FILE_TOOLS:
            p = inp.get(FILE_TOOLS[name])
            self.row("file", file_key(p, cwd) if isinstance(p, str) and p else "(no path)", chars, error)

    def report(self):
        rows = [{"group": g, "key": k, "calls": v[0], "chars": v[1], "errors": v[2]}
                for (g, k), v in self.rows.items()]
        rows.sort(key=lambda r: (GROUPS.index(r["group"]), -r["chars"], r["key"]))
        u = {s: dict(c) for s, c in self.usage.items()}
        u["all"] = {k: u["main"][k] + u["sub"][k] for k in COUNT_KEYS}
        fresh = u["all"]["in"] + u["all"]["cw"]
        rep = {"totals": {"transcripts": self.transcripts["main"], "subagent_transcripts": self.transcripts["sub"],
                          "calls": self.calls, "chars": self.chars, "errors": self.errors,
                          "unmatched": self.unmatched, "no_result": self.no_result,
                          "result_tokens_est": self.chars // CHARS_PER_TOKEN, "fresh_input": fresh},
               "usage": u, "rows": rows}
        problems = tree_problems(rep)
        rep["check"] = {"ok": not problems, "problems": problems}
        return rep


def tree_problems(rep):
    """What does not add up in a rollup: a group whose rows do not sum to what they split (every result by tool and by
    agent; the shell results by command head, the file tools' by path), and result characters that more than
    TOKEN_SPAN_MAX characters a token could not have brought into the transcripts' fresh input (input + cache write)."""
    t = rep["totals"]
    sums = {}
    for r in rep["rows"]:
        s = sums.setdefault(r["group"], [0, 0, 0])
        s[0] += r["calls"]
        s[1] += r["chars"]
        s[2] += r["errors"]
    def of(names):
        return [sum(r[k] for r in rep["rows"] if r["group"] == "tool" and r["key"] in names)
                for k in ("calls", "chars", "errors")]

    want = {"tool": [t["calls"], t["chars"], t["errors"]], "agent": [t["calls"], t["chars"], t["errors"]],
            "bash": of(SHELLS), "file": of(FILE_TOOLS)}
    out = []
    for g, w in want.items():
        got = sums.get(g, [0, 0, 0])
        if got != w:
            out.append(f"{g} rows hold {got[0]} calls, {got[1]} characters, {got[2]} errors; "
                       f"what they split holds {w[0]}, {w[1]}, {w[2]}")
    if t["chars"] > TOKEN_SPAN_MAX * t["fresh_input"]:
        out.append(f"{t['chars']} result characters cannot come from {t['fresh_input']} fresh input tokens "
                   f"(at most {TOKEN_SPAN_MAX} characters a token)")
    return out


def tree_text(rep, top):
    t, u = rep["totals"], rep["usage"]
    lines = [f"tree: {t['transcripts']} transcripts, {t['subagent_transcripts']} subagent transcripts; "
             f"{t['calls']} tool results, {t['chars']} characters (~{t['result_tokens_est']} tokens at "
             f"{CHARS_PER_TOKEN} characters a token), {t['errors']} errors, {t['unmatched']} without a tool use, "
             f"{t['no_result']} tool uses without a result",
             "usage: " + "; ".join(f"{s} {u[s]['requests']} requests, in {u[s]['in']}, cache write {u[s]['cw']}, "
                                   f"cache read {u[s]['cr']}, out {u[s]['out']}" for s in ("main", "sub")),
             f"results against usage: ~{t['result_tokens_est']} tokens of {t['fresh_input']} fresh input "
             f"(input + cache write)" + (f", {round(100 * t['result_tokens_est'] / t['fresh_input'])}%"
                                         if t["fresh_input"] else "")]
    for g in GROUPS:
        rows = [r for r in rep["rows"] if r["group"] == g]
        if not rows:
            continue
        lines += ["", f"by {g}: {'calls':>6} {'chars':>10} {'errors':>6}"]
        shown = rows[:top] if top else rows
        lines += [f"  {r['calls']:>6} {r['chars']:>10} {r['errors']:>6}  {r['key']}" for r in shown]
        if len(shown) < len(rows):
            lines.append(f"  ... {len(rows) - len(shown)} more rows (--top 0 shows all)")
    lines += ["", "check: " + ("ok" if rep["check"]["ok"] else "FAILED")]
    lines += [f"  {p}" for p in rep["check"]["problems"]]
    return lines


def tree_main(argv):
    ap = argparse.ArgumentParser(prog="kbusage.py tree", description=TREE_DOC)
    ap.add_argument("path", help="a transcript (with its subagents/*.jsonl) or a project directory of transcripts")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    ap.add_argument("--top", type=int, default=15, help="rows per group in text (0: all; default 15)")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    if not Path(a.path).exists():
        print(f"kbusage tree: {a.path}: no such file or directory", file=sys.stderr)
        return 2
    files = tree_files(a.path)
    if not files:
        print(f"kbusage tree: {a.path}: no transcripts (*.jsonl)", file=sys.stderr)
        return 2
    tree = Tree()
    for scope, f in files:
        tree.scan(scope, f)
    rep = tree.report()
    if a.format == "json":
        print(json.dumps(rep, indent=1, sort_keys=True))
    else:
        print("\n".join(tree_text(rep, a.top)))
    return 0 if rep["check"]["ok"] else 1


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv and argv[0] == "tree":
        return tree_main(argv[1:])
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("transcript")
    ap.add_argument("--prompt", help="one prompt id (default: every prompt of the transcript)")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    ids = [a.prompt] if a.prompt else prompt_ids(a.transcript)
    for i, pid in enumerate(ids, 1):
        rec = prompt_usage(a.transcript, pid)
        print(json.dumps({"prompt": i, **(rec or {"usage": None})}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
