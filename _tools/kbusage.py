#!/usr/bin/env python3
"""Exact token usage of one prompt, read from a Claude Code session transcript (kb/_self/usage.md). Standard library
only; no model and no network.

  kbusage.py TRANSCRIPT [--prompt PROMPT_ID]   the usage record of each prompt of a transcript (or of one), as JSON
                                               lines: the numbers the query log's sidecar keeps, nothing else
  kbusage.py tree PATH [--format json] [--top N]
                                               tool results of a transcript with its subagents/*.jsonl, or of every
                                               transcript of a project directory: calls and characters by tool, Bash
                                               command head, file path and agent, with the totals checked against the
                                               transcripts' usage (exit 1 when they do not add up, 2 for no input);
                                               then, per tick (a prompt of the main transcript), the compactions with
                                               their preTokens, the tokens and the files read more than once

prompt_usage(transcript_path, prompt_id) is what the query log's distill calls: a dict of counts, tool groups and
model ids, or None when the transcript cannot be read or holds no request of the prompt. A subagent that worked on a
`work/<id>` branch is counted under `routed`, by that item id, not under `sub`.
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
          "it-ops-kb:kb-lookup": "kb-lookup", "kb-reviewer": "kb-reviewer", "it-ops-kb:kb-reviewer": "kb-reviewer",
          "kb-worker": "kb-worker", "it-ops-kb:kb-worker": "kb-worker"}
OTHER_AGENT = "other"
GROUPS = ("tool", "bash", "class", "file", "agent")
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
WORK_BRANCH = re.compile(r"work/((?:EP|ST|TK|SB|BG|SP)-[a-z2-7]{8})")  # a worker's branch: `work/` and backlog.py's id
# a hand-made worker worktree in a command: `<clone>/.claude/worktrees/<id>` (a worker whose working directory stays its
# session's, so no record of it names a work branch)
WORK_WORKTREE = re.compile(r"[/\\]\.claude[/\\]worktrees[/\\]((?:EP|ST|TK|SB|BG|SP)-[a-z2-7]{8})(?![\w-])")
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


def work_item(records):
    """The item id of a subagent transcript's records: the one `work/<id>` branch they name in `gitBranch` (the
    branch a worker's worktree is on; a worker's earlier records name the branch it started on, which is no work
    branch). A worker whose worktree was made by hand keeps its session's working directory, so no record names a work
    branch: then the one item whose `.claude/worktrees/<id>` directory its shell commands name. None when they name
    none or two different ones. The branch and the commands are read in memory; only the id leaves."""
    ids = set()
    for r in records:
        b = r.get("gitBranch")
        m = WORK_BRANCH.fullmatch(b) if isinstance(b, str) else None
        if m:
            ids.add(m.group(1))
    if ids:
        return next(iter(ids)) if len(ids) == 1 else None
    for r in records:
        msg = r.get("message")
        for block in msg.get("content") if isinstance(msg, dict) and isinstance(msg.get("content"), list) else ():
            cmd = block.get("input", {}).get("command") if isinstance(block, dict) and block.get("type") == "tool_use" \
                and isinstance(block.get("input"), dict) else None
            if isinstance(cmd, str):
                ids.update(WORK_WORKTREE.findall(cmd))
    return next(iter(ids)) if len(ids) == 1 else None


def prompt_usage(transcript_path, prompt_id):
    """The usage record of one prompt: `main` and `sub` ({model: counts}, `sub` by agent group), `routed` ({item id:
    the `sub` shape}, for the subagents that worked on a `work/<id>` branch, work_item, which `sub` then leaves out),
    `start` (the input of the prompt's first request), `steps` (at most STEPS_MAX, with `cut` counting the rest);
    None when the transcript cannot be read or holds no request of the prompt."""
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
    sub, routed = {}, {}
    for group, f in subagent_files(transcript_path, prompt_id):
        records = read_all(f)
        item = work_item(records)
        for _, model, c in requests(records, sidechain=True):
            add((routed.setdefault(item, {}) if item else sub).setdefault(group, {}), model, c)
    st = steps(mine)
    rec = {"main": main, "start": total_input(reqs[0][2])}
    if sub:
        rec["sub"] = sub
    if routed:
        rec["routed"] = routed
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


# The closed class of a shell command (command_class): a token, never command text or a path, shared by the ops row
# `call.tool` (ql_capture) and the tree's `class` group, so the two agree on one session.
KNOWN_COMMANDS = frozenset((
    "ls", "cat", "head", "tail", "wc", "grep", "rg", "find", "sed", "awk", "sort", "uniq", "cut", "tr", "diff", "echo",
    "printf", "test", "mkdir", "rm", "cp", "mv", "touch", "chmod", "ln", "curl", "wget", "tar", "unzip", "zip", "jq",
    "make", "node", "npx", "pwsh", "powershell", "sleep", "kill", "ps", "which", "date", "env", "xargs", "tee", "du",
    "df", "stat", "file", "basename", "dirname", "realpath", "readlink", "open", "dig", "nslookup", "ssh", "scp",
    "rsync", "python", "pytest", "ruff"))
CLASS_TOKEN = re.compile(r"[a-z][a-z0-9_.-]{0,39}")
CLASS_SUBCOMMANDS = {  # the subcommands `command_class` names per SUBCOMMANDS tool; any other word gives the tool alone
    "git": set("""add am apply bisect blame branch cat-file check-ignore cherry cherry-pick clean clone commit config
        count-objects describe diff fetch for-each-ref format-patch fsck gc grep hash-object init log ls-files ls-remote
        ls-tree merge merge-base mv notes pull push range-diff rebase reflog remote reset restore rev-list rev-parse
        revert rm shortlog show show-ref stash status submodule switch symbolic-ref tag update-ref worktree""".split()),
    "gh": set("api auth browse cache gist issue label pr release repo run search secret status workflow".split()),
    "glab": set("api auth ci issue job mr pipeline project release repo variable".split()),
    "docker": set("""build compose cp exec image images info inspect login logs network ps pull push rm rmi run start stop
        system tag version volume""".split()),
    "kubectl": set("apply config create delete describe edit exec get logs port-forward rollout scale top version".split()),
    "npm": set("audit ci exec init install ls outdated pack publish run test uninstall update version view".split()),
    "pip": set("check download freeze index install list show uninstall wheel".split()),
    "uv": set("add build cache export init lock pip publish python remove run sync tool tree venv".split()),
    "cargo": set("add bench build check clean clippy doc fmt init install new publish run test tree update".split()),
    "go": set("build env fmt generate get install list mod run test tool version vet work".split()),
    "claude": set("agents config doctor install mcp plugin setup-token update".split()),
}
CLASS_SUBCOMMANDS["pip3"] = CLASS_SUBCOMMANDS["pip"]
TOOL_SCRIPT = re.compile(r"_tools/([a-z][a-z0-9_]{0,30})\.py")


def command_class(command):
    """The closed class of a shell command: `tools.<stem>` for a script of this repository's `_tools/`, `python-c`,
    `python-m` or `python-script` for any other Python, `<tool>.<subcommand>` for the tools in SUBCOMMANDS when
    CLASS_SUBCOMMANDS names the subcommand (else the tool alone: no free word of a prompt or an argument), the
    command's own name when it is in KNOWN_COMMANDS, `none` for no command and `other` for the rest."""
    head = command_head(command)
    if head == "(none)":
        return "none"
    first, _, rest = head.partition(" ")
    if PYTHON.fullmatch(first):
        word = rest.split(" ", 1)[0]
        m = TOOL_SCRIPT.fullmatch(word)
        if m:
            return "tools." + m.group(1)
        if word == "-c":
            return "python-c"
        if word.startswith("-m"):
            return "python-m"
        return "python-script" if word else "python"
    if first in SUBCOMMANDS:
        sub = rest.split(" ", 1)[0]
        return f"{first}.{sub}" if sub in CLASS_SUBCOMMANDS.get(first, ()) else first
    return first if first in KNOWN_COMMANDS else "other"


SIZE_CLASSES = ((0, "empty"), (1000, "lt1k"), (10000, "lt10k"), (100000, "lt100k"))


def size_class(chars):
    """The class of a result's size in characters: `empty`, `lt1k`, `lt10k`, `lt100k` or `ge100k`."""
    n = chars if isinstance(chars, int) and chars >= 0 else 0
    if n == 0:
        return "empty"
    for top, name in SIZE_CLASSES[1:]:
        if n < top:
            return name
    return "ge100k"


def call_group(name):
    """A tool's group as a token (tool_group in lower case, `:` as `.`)."""
    return tool_group(name).lower().replace(":", ".")


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
            self.row("class", command_class(inp.get("command")), chars, error)
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
            "bash": of(SHELLS), "class": of(SHELLS), "file": of(FILE_TOOLS)}
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
    lines += rot_text(rep.get("rot") or {"ticks": []})
    lines += ["", "check: " + ("ok" if rep["check"]["ok"] else "FAILED")]
    lines += [f"  {p}" for p in rep["check"]["problems"]]
    return lines


# ---------------------------------------------------------------- context rot: compactions, tokens, repeated reads

def pre_tokens(rec):
    """The preTokens of a compact_boundary record (`compactMetadata.preTokens`); 0 when the record gives none."""
    m = rec.get("compactMetadata")
    return _int(m["preTokens"]) if isinstance(m, dict) and "preTokens" in m else 0


class Rot:
    """One tick (a prompt of a main transcript): the compactions it saw, the tokens its requests used and the
    files its Read calls named, by agent. `tokens` is in + cache write + cache read + out of every request, once each."""

    def __init__(self):
        self.pre, self.reqs, self.reads, self.uses = [], {}, {}, set()

    def boundary(self, rec):
        self.pre.append(pre_tokens(rec))

    def request(self, rid, c):
        if rid not in self.reqs or c["out"] > self.reqs[rid]["out"]:
            self.reqs[rid] = c

    def read(self, agent, key, use):
        """One Read call, once by its tool use id: a message's events can repeat a block."""
        if use in self.uses:
            return
        self.uses.add(use)
        self.reads[(agent, key)] = self.reads.get((agent, key), 0) + 1

    def row(self):
        tokens = sum(c["in"] + c["cw"] + c["cr"] + c["out"] for c in self.reqs.values())
        return {"compactions": len(self.pre), "pre_tokens": list(self.pre), "tokens": tokens, "requests": len(self.reqs),
                "reads": sum(self.reads.values()), "repeated_reads": sum(n - 1 for n in self.reads.values()),
                "repeated_files": sum(1 for n in self.reads.values() if n > 1)}


def is_boundary(rec):
    return rec.get("type") == "system" and rec.get("subtype") == "compact_boundary"


def read_uses(rec):
    """[(tool use id, file path)] of the Read tool uses of an assistant record."""
    msg = rec.get("message") if isinstance(rec.get("message"), dict) else {}
    content = msg.get("content") if isinstance(msg.get("content"), list) else []
    return [(b.get("id"), b["input"]["file_path"]) for b in content
            if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Read"
            and isinstance(b.get("input"), dict) and isinstance(b["input"].get("file_path"), str) and b["input"]["file_path"]]


def tick_rows(path):
    """[row] per tick of a main transcript: a tick is one prompt, the records from its first user record to the
    next prompt's (a loop firing is one prompt). Its subagents' requests (the transcripts whose first record names the
    prompt) count in its tokens; a file is read twice when two Read calls of the main chain name it (a worktree's path
    folded into the project's, as `by file` keys it). A transcript with no prompt gives no rows."""
    order, ticks, mine, current = [], {}, {}, None
    for r in read_all(path):
        pid = r.get("promptId")
        if r.get("type") == "user" and isinstance(pid, str) and not r.get("isSidechain"):
            current = pid
            if pid not in ticks:
                order.append(pid)
                ticks[pid], mine[pid] = Rot(), []
        if current is None or r.get("isSidechain"):
            continue
        mine[current].append(r)
        if is_boundary(r):
            ticks[current].boundary(r)
        elif r.get("type") == "assistant":
            for use, p in read_uses(r):
                ticks[current].read("main", file_key(p, r.get("cwd")), use)
    out = []
    for pid in order:
        t = ticks[pid]
        for rid, _, c in requests(mine[pid]):
            t.request(("main", rid), c)
        for _, f in subagent_files(path, pid):
            for rid, _, c in requests(read_all(f), sidechain=True):
                t.request((str(f), rid), c)
        out.append(t.row())
    return out


def rot_rows(files):
    """{"ticks": [...]}: a row per tick of each main transcript (`transcript` its number, `tick` the tick's, both
    from 1)."""
    ticks = []
    for i, (scope, f) in enumerate([x for x in files if x[0] == "main"], 1):
        ticks += [{"transcript": i, "tick": j, **row} for j, row in enumerate(tick_rows(f), 1)]
    return {"ticks": ticks}


def rot_text(rot):
    """Lines of the `by tick` table; every count prints, a tick with no compaction as 0."""
    rows = rot["ticks"]
    if not rows:
        return []
    lines = ["", f"by tick: {'compactions':>11} {'pre_tokens':>11} {'tokens':>12} {'reads':>6} {'repeated':>8}"]
    for r in rows:
        pre = ",".join(map(str, r["pre_tokens"])) if r["pre_tokens"] else "0"
        lines.append(f"  {r['compactions']:>11} {pre:>11} {r['tokens']:>12} {r['reads']:>6} {r['repeated_reads']:>8}  "
                     f"t{r['transcript']}.{r['tick']}")
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
    rep["rot"] = rot_rows(files)
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
