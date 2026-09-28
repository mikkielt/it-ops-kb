#!/usr/bin/env python3
"""Exact token usage of one prompt, read from a Claude Code session transcript (kb/_self/usage.md). Standard library
only; no model and no network.

  kbusage.py TRANSCRIPT [--prompt PROMPT_ID]   the usage record of each prompt of a transcript (or of one), as JSON
                                               lines: the numbers the query log's sidecar keeps, nothing else

prompt_usage(transcript_path, prompt_id) is what the query log's Stop capture calls: a dict of counts, tool groups and
model ids, or None when the transcript cannot be read or holds no request of the prompt.
"""
import argparse, json, os, re, sys
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


def main(argv=None):
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
