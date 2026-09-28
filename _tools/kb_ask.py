#!/usr/bin/env python3
"""Ask the kb from a shell or a script, routed by the kb's own tools instead of by a model (stdlib only).

  kb_ask.py "<question>"             answer it the cheapest way that works:
                                     1. a count or list over the kb ("how many intune articles are partial", "which
                                        files cite S1216") is answered by the audit and source tools: no model;
                                     2. a question with numbered parts or several questions is split, one pack per
                                        part (up to 6);
                                     3. coverage good -> Haiku reads the packs with no tools, in a `claude -p` without
                                        the user's plugins and MCP servers;
                                        if the facts are only about something related it answers INSUFFICIENT and
                                        the question goes on to step 4 (the verdict counts words, not meaning);
                                     4. weak or none -> Sonnet at low effort with the kb and the live-docs servers.
  kb_ask.py --route "<question>"     print the plan (kind, parts, verdict, model), run nothing
  kb_ask.py --no-model "<question>"  print a good pack, or a count answer, without calling a model
  kb_ask.py --model M "<question>"   override the routed model of step 3 or 4
  kb_ask.py -v "<question>"          also print the route to stderr

Every run writes one query log spool row (kb/_self/querylog.md, Capture): the question, the route taken (`tool`,
`good`, `weak`, `plan` for --route, with `escalated` when the reader answered INSUFFICIENT), the verdict, the kb
lines of the pack (path:line, tag, verdict) and the model. Its own `claude -p` runs with hooks off, so the session it starts never logs itself.

Why (kb/_self/reports/benchmarks.md, "Routing by verdict"): a Haiku session costs a fifth of a Sonnet one and an eighth of an
Opus one with the same answers, but a Haiku manager told to hand work to Sonnet did so once in four runs. The kb's
verdict and a one-line INSUFFICIENT reply cannot ignore the rule. A `claude -p` start carries about 30k tokens of
Claude Code context; skipping user plugins and MCP servers takes it to 25k, and no tools to 10k.
"""
import argparse, json, os, re, shutil, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kbcommon, kbfacts  # noqa: E402
import ql_capture  # noqa: E402

HOME = kbfacts.kbcommon.HOME  # this repository: the docs servers' config, the kb server, the sessions' cwd
DOCS_MCP = os.path.join(HOME, ".claude-plugin", "it-ops-kb-docs", ".mcp.json")
DOCS = ["mcp__microsoft-learn__microsoft_docs_search", "mcp__microsoft-learn__microsoft_docs_fetch",
        "mcp__claude-code-docs__search_claude_code_docs", "mcp__mcp-docs__search_model_context_protocol"]
# claude -p without the user's plugins and MCP servers (project and local settings still apply) and with every hook
# off, so the query log's capture hooks never log kb_ask.py's own session (it writes its own row)
LEAN = ["--setting-sources", "project,local", "--strict-mcp-config", *kbcommon.NO_HOOKS]
SENTINEL = "INSUFFICIENT"
RULES = ("Answer from the kb evidence below: lead with the answer, then each supporting fact with its path:line, tag "
         "and source url. COMMUNITY and UNK facts are leads, not answers; a CODE fact is implementation read from "
         "source code, not a documented promise: say so; a `(no tag)` line is untagged article "
         "content. Never fill gaps from memory.")
READER = RULES + (f" If the facts are about something related but do not answer what was asked, reply with one line "
                  f"only: `{SENTINEL}: <what is missing>`.")
RESEARCHER = RULES + (" If the evidence does not answer the question, or only a related one, research the missing part "
                      "in the live docs (Microsoft Learn, Claude Code docs, MCP docs; web search last) and label it "
                      "'live docs, not in the kb' with its url.")

# ---------------------------------------------------------------- questions the tools answer without a model

COUNT = re.compile(r"\b(how many|count|number of|list|which|what)\b.*\b(articles?|topics?)\b", re.I | re.S)
CITE = re.compile(r"\b(cit\w*|us\w* by|refer\w*)\b", re.I)
STATUS = re.compile(r"\b(partial|complete|unknown)\b", re.I)


def domains():
    """The domain names of every root, bare (`intune`): a question names a domain, not a root."""
    return sorted({kbfacts.bare(p).split("/", 1)[0] for p in kbfacts.articles()})


def tool_answer(question):
    """The answer text for a count/list question over the kb's articles or a 'who cites source X' question, or None."""
    ids = kbfacts.ID.findall(question)
    if ids and CITE.search(question):
        lines = kbfacts.cited_lines(ids)
        srcs = kbfacts.source_rows()
        out = []
        for i in ids:
            cid = kbid_canonical(i)
            row = srcs.get(cid) or {}
            out.append(f"{cid}  {row.get('url', '(no _sources.csv row)')}")
            hits = lines.get(cid, [])
            out += [f"  {p}:{n}" for p, n in hits] or ["  (no file cites it)"]
            out.append(f"  cited by {len(hits)} line(s)")
        return "\n".join(out)
    if not COUNT.search(question):
        return None
    words = {w.lower() for w in kbfacts.WORD.findall(question)}
    doms = [d for d in domains() if d.lower() in words]
    if not doms and not re.search(r"\b(kb|all|every)\b", question, re.I):
        return None  # "which articles cover X" is a lookup, not a count
    m = STATUS.search(question)
    import rag  # the same table rag.py audit prints
    rows = [r for d in (doms or [None]) for r in kbfacts.audit(d, m.group(1).lower() if m else None)]
    return rag.format_audit(rows, fmt="concise")


def kbid_canonical(i):
    import kbid
    return kbid.canonical_id(i)


# ---------------------------------------------------------------- several parts in one question

NUMBERED = re.compile(r"(?:^|\s)\(?(\d{1,2})[).]\s+")


def split_parts(question):
    """The parts of a question: numbered items ("(1) ... (2) ...", "1. ... 2. ...") or several sentences ending in
    '?' (other sentences, such as instructions, are left out of the split); one part when neither applies. At most kbfacts.MAX_QUESTIONS."""
    marks = list(NUMBERED.finditer(question))
    nums = [int(m.group(1)) for m in marks]
    if len(marks) >= 2 and nums == list(range(nums[0], nums[0] + len(nums))):
        parts = [question[m.end():(marks[k + 1].start() if k + 1 < len(marks) else len(question))]
                 for k, m in enumerate(marks)]
    else:  # only the sentences that ask something: "... length? Answer with citations." is one question
        parts = [p for p in re.split(r"(?<=\?)\s+", question) if p.rstrip().endswith("?")]
    parts = [p.strip(" ;,\n") for p in parts if kbfacts.key_terms(p)]
    return parts[:kbfacts.MAX_QUESTIONS] if len(parts) > 1 else [question.strip()]


# ---------------------------------------------------------------- routing

def plan(question, model=None):
    """{kind: tool|good|weak, parts, verdict, text (the packs), model}."""
    parts = split_parts(question)
    res = kbfacts.pack_many(parts)
    kind = "good" if res["verdict"] == "good" else "weak"
    return {"kind": kind, "parts": parts, "verdict": res["verdict"], "text": res["text"],
            "model": model or ("haiku" if kind == "good" else "sonnet")}


def prompt(question, pack_text):
    return f"Question: {question}\n\n<kb_evidence>\n{pack_text}\n</kb_evidence>"


def claude_argv(model, tools):
    argv = ["claude", "-p", "--no-session-persistence", "--model", model, *LEAN]
    if tools:
        argv += ["--mcp-config", DOCS_MCP, "--mcp-config", json.dumps({"mcpServers": {"kb": {
            "command": sys.executable, "args": [os.path.join(HOME, "_tools", "kb_mcp.py")]}}}),
                 "--effort", "low", "--allowedTools", "mcp__kb", *DOCS]
    else:
        argv += ["--tools", ""]
    return argv


def read(model, system, user):
    """The reader's answer: a tool-less claude -p."""
    p = subprocess.run(claude_argv(model, tools=False) + ["--append-system-prompt", system], cwd=HOME, input=user,
                       capture_output=True, text=True, encoding="utf-8")
    if p.returncode:
        raise SystemExit(p.stderr or f"claude -p exited {p.returncode}")
    return p.stdout


VERBOSE = False


def log(msg):
    if VERBOSE:
        print(f"kb_ask: {msg}", file=sys.stderr)


def main():
    row = {}
    try:
        return run(row)
    finally:
        if row.get("question"):
            ql_capture.record("kb_ask", **row)


def run(row):
    global VERBOSE
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("question", nargs="+")
    ap.add_argument("--route", action="store_true", help="print the plan, run nothing")
    ap.add_argument("--no-model", action="store_true", help="print a good pack or a count answer without a model")
    ap.add_argument("--model", help="override the routed model")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    VERBOSE = a.verbose
    q = " ".join(a.question)
    row.update(question=q, route="tool")
    tool = tool_answer(q)
    if tool is not None:
        print("kind=tool (audit and source tools, no model)" if a.route else tool)
        return 0
    p = plan(q, a.model)
    row.update(route="plan" if a.route else p["kind"], verdict=p["verdict"], parts=len(p["parts"]),
               lines=ql_capture.pack_lines(p["text"]))
    line = f"kind={p['kind']} verdict={p['verdict']} parts={len(p['parts'])} model={p['model']}"
    log(line)
    if a.route:
        print(line)
        for i, part in enumerate(p["parts"], 1):
            print(f"part {i}: {part}")
        return 0
    row["model"] = None if a.no_model and p["kind"] == "good" else p["model"]
    if a.no_model and p["kind"] == "good":
        print(p["text"])
        return 0
    if not shutil.which("claude"):
        print("kb_ask: the claude CLI is not on PATH; the evidence follows\n", file=sys.stderr)
        print(p["text"])
        return 2
    note = ""
    if p["kind"] == "good":
        text = read(p["model"], READER, prompt(q, p["text"]))
        if not text.lstrip().startswith(SENTINEL):
            print(text.strip())
            return 0
        note = f"\n\nA first reader of this evidence said: {text.strip().splitlines()[0]}"
        log(f"reader said {SENTINEL}; escalating to sonnet")
        p["model"] = "sonnet" if not a.model else a.model
        row.update(escalated=True, model=p["model"])
    argv = claude_argv(p["model"], tools=True) + ["--append-system-prompt", RESEARCHER]
    return subprocess.run(argv, cwd=HOME, input=prompt(q, p["text"]) + note, text=True, encoding="utf-8").returncode


if __name__ == "__main__":
    sys.exit(main())
