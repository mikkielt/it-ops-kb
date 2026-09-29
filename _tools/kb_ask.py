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
                                     4. a pack routed web (the kb lacks the question) -> one Sonnet researcher at low
                                        effort with the live-docs servers and WebSearch/WebFetch, no kb server; it gets
                                        the question, the pack's `kb lacks:` line and up to three nearest article titles
                                        as leads to verify; its `--output-format json` result is printed (an error
                                        result's errors go to stderr, exit 1);
                                     5. a pack routed split (the kb has part of it) -> the Haiku reader answers the `kb has:`
                                        part from the pack and the same researcher only the `kb lacks:` part, each with
                                        `--output-format json`; one answer is printed, the kb part first, then the live
                                        part under "Live docs, not in the kb:"; -v prints each run's total_cost_usd and
                                        their sum. A reader INSUFFICIENT sends the whole question to the researcher
                                        (`escalated`). A split pack that lacks its `kb has:` or `kb lacks:` line cannot be
                                        divided: the reader answers the whole question from the pack, as in step 3.
                                     A weak or none pack without a `route:` line plans split.
  kb_ask.py --route "<question>"     print the plan (kind, parts, verdict, model and, for web and split, the pack's
                                     route, kb has and kb lacks lines), run nothing
  kb_ask.py --no-model "<question>"  print a good pack, or a count answer, without calling a model
  kb_ask.py --model M "<question>"   override the routed model of step 3 or 4
  kb_ask.py -v "<question>"          also print the route to stderr

Every run writes one query log spool row (kb/_self/querylog.md, Capture): the question, the route taken (`tool`,
`good`, `web`, `split`, `plan` for --route, with `escalated` when the reader answered INSUFFICIENT), the verdict, the kb
lines of the pack (path:line, tag, verdict), the model and, for a web or split run, `sources`: the ids of the kb
sources whose urls the researcher's answer names (never the urls or the text), which learn reads as pages the lookup
fetched. Its own `claude -p` runs with hooks off, so the session it starts never logs itself and its fetches are never
logged.

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
WEB = ["WebSearch", "WebFetch"]  # the researcher's built-in tools: `--tools` limits them, `--allowedTools` approves them
SENTINEL = "INSUFFICIENT"
READER_MODEL = "haiku"
LIVE_LABEL = "Live docs, not in the kb:"
RULES = ("Answer from the kb evidence below: lead with the answer, then each supporting fact with its path:line, tag "
         "and source url. COMMUNITY and UNK facts are leads, not answers; a CODE fact is implementation read from "
         "source code, not a documented promise: say so; a `(no tag)` line is untagged article "
         "content. Never fill gaps from memory.")
READER = RULES + (f" If the facts are about something related but do not answer what was asked, reply with one line "
                  f"only: `{SENTINEL}: <what is missing>`.")
SPLIT_READER = READER + (" The kb covers only part of the question: answer the part you are told to and leave the rest to "
                         "the live-docs researcher.")
RESEARCHER = RULES + (" If the evidence does not answer the question, or only a related one, research the missing part "
                      "in the live docs (Microsoft Learn, Claude Code docs, MCP docs; web search last) and label it "
                      "'live docs, not in the kb' with its url.")

WEB_RESEARCHER = ("The kb does not cover this question, or the part named on the `kb lacks` line. Research it in the live "
                  "docs: Microsoft Learn, Claude Code docs and MCP docs first, web search last. WebSearch returns titles "
                  "and urls only: fetch a page with WebFetch (or a docs tool) before you state a fact from it. The "
                  "nearest kb articles are leads to verify, not answers. Answer with the source url of each fact and "
                  "label the answer 'live docs, not in the kb'. Never fill gaps from memory; if the live docs do not "
                  "answer, say so.")

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

ROUTE_LINE = re.compile(r"^route: (web|split)\s*$", re.M)
HAS_LINE = re.compile(r"^kb has: (.*\S)\s*$", re.M)
LACKS_LINE = re.compile(r"^kb lacks: (.*\S)\s*$", re.M)
ARTICLE_LINE = re.compile(r"^## (\S+)  (.+?)  \[", re.M)
MAX_LEADS = 3


def plan(question, model=None):
    """{kind: good|web|split, parts, verdict, text (the packs), route (web, split or None), has, lacks (the packs'
    `kb has:` and `kb lacks:` lines, one entry per line), leads ([(path, title)]: the up to 3 nearest articles), model}.
    The kind follows the pack's `route:` line (a pack of several parts starts with one overall line); a clean good
    pack has none and stays `good`. A weak or none pack without the line plans `split`, the route that keeps the kb's
    evidence in front of the model."""
    parts = split_parts(question)
    res = kbfacts.pack_many(parts)
    text = res["text"]
    m = ROUTE_LINE.search(text)
    route = m.group(1) if m else (None if res["verdict"] == "good" else "split")
    kind = route or "good"
    leads, seen = [], set()
    for path, title in ARTICLE_LINE.findall(text):
        if path not in seen:
            seen.add(path)
            leads.append((path, title))
    return {"kind": kind, "parts": parts, "verdict": res["verdict"], "text": text, "route": route,
            "has": HAS_LINE.findall(text), "lacks": LACKS_LINE.findall(text), "leads": leads[:MAX_LEADS],
            "model": model or ("haiku" if kind == "good" else "sonnet")}


def prompt(question, pack_text):
    return f"Question: {question}\n\n<kb_evidence>\n{pack_text}\n</kb_evidence>"


def split_prompt(question, p):
    """The split reader's input: the question, the part to answer (kb has), the part it leaves to the researcher (kb lacks)
    and the pack."""
    return (f"Question: {question}\n\nAnswer only the part the kb has: {'; '.join(p['has'])}. The kb lacks: "
            f"{'; '.join(p['lacks'])}. A live-docs researcher answers that part: do not answer it and do not say it is missing."
            f"\n\n<kb_evidence>\n{p['text']}\n</kb_evidence>")


def web_prompt(question, p, whole=False):
    """The web researcher's input: the question, what the kb lacks and the nearest articles as leads (not the pack).
    whole=True leaves the lacks line out: the whole question is the researcher's (a split reader said INSUFFICIENT)."""
    out = [f"Question: {question}"]
    if p["lacks"] and not whole:
        out += ["", "The kb lacks: " + "; ".join(p["lacks"])]
    if p["leads"]:
        out += ["", "Nearest kb articles, leads to verify in the live docs (not answers):"]
        out += [f"- {title} ({path})" for path, title in p["leads"]]
    return "\n".join(out)


def claude_argv(model, tools, output=None):
    """The claude -p argument list. tools=False: the reader (no tools, no --effort). tools=True: the researcher, the lean
    start: the docs servers' config only (no kb server), built-in tools limited to WebSearch and WebFetch (`--tools`;
    `--allowedTools` only approves), `--effort low`. output="json" adds `--output-format json` (one result object with
    `result`, `total_cost_usd`, `is_error`); left out, the caller sets its own format."""
    argv = ["claude", "-p", "--no-session-persistence", "--model", model, *LEAN]
    if tools:
        argv += ["--mcp-config", DOCS_MCP, "--tools", ",".join(WEB), "--effort", "low", "--allowedTools", *WEB, *DOCS]
    else:
        argv += ["--tools", ""]
    if output:
        argv += ["--output-format", output]
    return argv


def parse_result(stdout):
    """(text, cost, ok) of a `claude -p --output-format json` result, or None when stdout is not one. text is `result`, or
    for an error result (is_error, or an `error_*` subtype) its `errors` joined; cost is total_cost_usd or None."""
    try:
        r = json.loads(stdout)
    except ValueError:
        return None
    if not isinstance(r, dict):
        return None
    cost = r.get("total_cost_usd")
    cost = float(cost) if isinstance(cost, (int, float)) and not isinstance(cost, bool) else None
    if r.get("is_error") or str(r.get("subtype", "")).startswith("error"):
        errs = r.get("errors")
        errs = "\n".join(str(e) for e in errs) if isinstance(errs, list) else errs
        return str(errs or r.get("result") or r.get("subtype") or "claude -p failed"), cost, False
    return str(r.get("result") or ""), cost, True


def research(model, system, user):
    """The researcher's (text, cost, ok): a claude -p with the docs servers and WebSearch/WebFetch."""
    argv = claude_argv(model, tools=True, output="json") + ["--append-system-prompt", system]
    p = subprocess.run(argv, cwd=HOME, input=user, capture_output=True, text=True, encoding="utf-8")
    got = parse_result(p.stdout)
    if got is None:
        raise SystemExit(p.stderr or f"claude -p exited {p.returncode} without a JSON result")
    return got


def read(model, system, user, output=None):
    """The reader's answer: a tool-less claude -p. Its stdout, or with output="json" the (text, cost, ok) of its result."""
    p = subprocess.run(claude_argv(model, tools=False, output=output) + ["--append-system-prompt", system], cwd=HOME,
                       input=user, capture_output=True, text=True, encoding="utf-8")
    if output:
        got = parse_result(p.stdout)
        if got is None:
            raise SystemExit(p.stderr or f"claude -p exited {p.returncode} without a JSON result")
        return got
    if p.returncode:
        raise SystemExit(p.stderr or f"claude -p exited {p.returncode}")
    return p.stdout


VERBOSE = False


def log(msg):
    if VERBOSE:
        print(f"kb_ask: {msg}", file=sys.stderr)


def cost_sum(*costs):
    """The sum of the runs' total_cost_usd that reported one, rounded to the cent's millionth; None when none did."""
    known = [c for c in costs if c is not None]
    return round(sum(known), 6) if known else None


def note_sources(row, answer):
    """Put on the spool row the ids of the kb sources whose urls the researcher's `answer` names (querylog.md, Surfaces).
    Only ids go on the row, and a failure to read them never fails the answer."""
    try:
        import ql_learn
        ids = ql_learn.answer_sources(answer)
    except Exception:  # noqa: BLE001 - the log never fails a lookup
        return
    if ids:
        row["sources"] = ids


def split(q, p, row):
    """A split run: the reader answers the kb has part, the researcher the kb lacks part; one answer, the kb part first and
    the live part under its label. A reader INSUFFICIENT gives the whole question to the researcher (row escalated). An error
    result of either run prints its errors to stderr and exits 1 (the kb part, when there is one, still goes to stdout)."""
    kb_text, kb_cost, ok = read(READER_MODEL, SPLIT_READER, split_prompt(q, p), output="json")
    log(f"reader {READER_MODEL} total_cost_usd={kb_cost}")
    if not ok:
        print(kb_text, file=sys.stderr)
        return 1
    escalated = kb_text.lstrip().startswith(SENTINEL)
    if escalated:
        note = f"\n\nA first reader of the kb evidence said: {kb_text.strip().splitlines()[0]}"
        log(f"reader said {SENTINEL}; the whole question goes to the researcher")
        row.update(escalated=True)
        live, live_cost, ok = research(p["model"], WEB_RESEARCHER, web_prompt(q, p, whole=True) + note)
    else:
        live, live_cost, ok = research(p["model"], WEB_RESEARCHER, web_prompt(q, p))
    log(f"researcher {p['model']} total_cost_usd={live_cost}")
    log(f"total_cost_usd={cost_sum(kb_cost, live_cost)} (reader + researcher)")
    if not ok:
        if not escalated:
            print(kb_text.strip())
        print(live, file=sys.stderr)
        return 1
    note_sources(row, live)
    print(live.strip() if escalated else f"{kb_text.strip()}\n\n{LIVE_LABEL}\n{live.strip()}")
    return 0


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
        if p["route"]:
            print("\n".join([f"route: {p['route']}"] + [f"kb has: {h}" for h in p["has"]]
                            + [f"kb lacks: {x}" for x in p["lacks"]]))
        return 0
    row["model"] = None if a.no_model and p["kind"] == "good" else p["model"]
    if a.no_model and p["kind"] == "good":
        print(p["text"])
        return 0
    if not shutil.which("claude"):
        print("kb_ask: the claude CLI is not on PATH; the evidence follows\n", file=sys.stderr)
        print(p["text"])
        return 2
    if p["kind"] == "web":
        text, cost, ok = research(p["model"], WEB_RESEARCHER, web_prompt(q, p))
        log(f"researcher {p['model']} total_cost_usd={cost}")
        if ok:
            note_sources(row, text)
        print(text.strip(), file=sys.stdout if ok else sys.stderr)
        return 0 if ok else 1
    if p["kind"] == "split" and p["has"] and p["lacks"]:
        return split(q, p, row)
    # good, and a split pack that cannot be divided: the reader answers the whole question from the pack
    text = read(p["model"] if p["kind"] == "good" else READER_MODEL, READER, prompt(q, p["text"]))
    if not text.lstrip().startswith(SENTINEL):
        print(text.strip())
        return 0
    note = f"\n\nA first reader of this evidence said: {text.strip().splitlines()[0]}"
    log(f"reader said {SENTINEL}; escalating to {a.model or 'sonnet'}")
    p["model"] = "sonnet" if not a.model else a.model
    row.update(escalated=True, model=p["model"])
    text, cost, ok = research(p["model"], RESEARCHER, prompt(q, p["text"]) + note)
    log(f"researcher {p['model']} total_cost_usd={cost}")
    print(text.strip(), file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
