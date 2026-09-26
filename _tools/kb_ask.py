#!/usr/bin/env python3
"""Ask the kb from a shell or a script, routed by the pack's verdict instead of by a model (stdlib only).

  kb_ask.py "<question>"             run the evidence pack (a few ms, no tokens), then one headless `claude -p`:
                                     coverage good -> ROUTES["good"] (Haiku) with the pack in the prompt, so it
                                     answers in one turn without calling a kb tool; weak or none -> ROUTES["weak"]
                                     (Sonnet) with the pack and the live-docs tools, to label what the kb lacks.
  kb_ask.py --route "<question>"     print the verdict and the command, run nothing
  kb_ask.py --no-model "<question>"  print the pack when it is good (like the `kb:` hook), else route as above
  kb_ask.py --model M "<question>"   override the routed model

Why a deterministic router (benchmark 2026-09-26, work-left.md): a Haiku session costs about a fifth of a Sonnet one
and an eighth of an Opus one for kb lookups with the same answers, but a Haiku *manager* told to hand live-docs work
to a Sonnet subagent did so only once in four runs, and an Opus session handing lookups to the Haiku kb-lookup agent
cost as much as answering itself and took twice as long. The verdict costs nothing and cannot ignore the rule.
Both routes keep the live-docs tools, so a `good` that is really about something else (the verdict counts words, not
meaning) can still be researched.
"""
import argparse, os, shutil, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kbfacts  # noqa: E402

KB = kbfacts.KB
DOCS = ["mcp__microsoft-learn__microsoft_docs_search", "mcp__microsoft-learn__microsoft_docs_fetch",
        "mcp__claude-code-docs__search_claude_code_docs", "mcp__mcp-docs__search_model_context_protocol"]
ROUTES = {
    "good": ("haiku", ["mcp__kb"] + DOCS),
    "weak": ("sonnet", ["mcp__kb", "WebSearch", "WebFetch"] + DOCS),
}
RULES = ("Answer from the kb evidence pack below: lead with the answer, then each supporting fact with its path:line, "
         "tag and source url. COMMUNITY and UNK facts are leads, not answers. Do not call kb_pack again for what the "
         "pack already covers. If the pack's facts are about something related rather than what was asked, or its "
         "coverage is weak or none, research only the missing part in the live docs (Microsoft Learn, Claude Code "
         "docs, MCP docs; web search last) and label that part 'live docs, not in the kb' with its url. Never fill "
         "gaps from memory.")


def route(question, model=None):
    """(verdict, pack text, argv of the claude command; the prompt goes on stdin)."""
    res = kbfacts.pack(question)
    m, tools = ROUTES["good" if res["verdict"] == "good" else "weak"]
    argv = ["claude", "-p", "--no-session-persistence", "--model", model or m, "--allowedTools", *tools]
    return res["verdict"], res["text"], argv


def prompt(question, pack_text):
    return f"{RULES}\n\nQuestion: {question}\n\n<kb_pack>\n{pack_text}\n</kb_pack>"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("question", nargs="+")
    ap.add_argument("--route", action="store_true", help="print the verdict and the command, run nothing")
    ap.add_argument("--no-model", action="store_true", help="print a good pack without calling a model")
    ap.add_argument("--model", help="override the routed model")
    a = ap.parse_args()
    q = " ".join(a.question)
    verdict, text, argv = route(q, a.model)
    if a.route:
        print(f"coverage: {verdict}\n{' '.join(argv)}")
        return 0
    if a.no_model and verdict == "good":
        print(text)
        return 0
    if not shutil.which("claude"):
        print("kb_ask: the claude CLI is not on PATH; the pack follows\n", file=sys.stderr)
        print(text)
        return 2
    return subprocess.run(argv, cwd=KB, input=prompt(q, text), text=True).returncode


if __name__ == "__main__":
    sys.exit(main())
