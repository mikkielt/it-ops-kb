#!/usr/bin/env python3
"""UserPromptSubmit hook: answer `kb:` prompts from the kb without the model (stdlib only).

  kb: <question>    run the evidence pack (kbfacts.pack). coverage: good -> block the prompt and show the pack to the
                    user as the block reason: the model is never called and no tokens are spent; but a good pack
                    with a `check:` line (a name the lead article never mentions, or key words spread over separate
                    facts: a possible false good) goes to the model as context, like weak, so the model decides.
                    A pack with a route (weak and flagged good: `split`; none: `web`, kbfacts.route_of) lets the prompt
                    through with the differential as context: an instruction to answer what the kb has from the pack
                    with path:line and urls, research only what it lacks in the live docs, label that part 'live docs,
                    not in the kb' with its url and never fill it from memory, then the pack (split) or only its
                    coverage, route:, kb has: and kb lacks: lines (web: no fact lines), cut so the context stays under
                    the 10,000 characters Claude Code keeps.
  kb+: <question>   always let the prompt through (the model reasons over it): a clean good pack attached with a short
                    instruction, a pack with a route as for kb:.
  anything else     no output: the prompt goes to the model unchanged.

The same script answers a PreToolUse event on Bash (a JSON event with `tool_input`): a command that reads a kb article
whole (cat, head, tail, sed -n or grep -n on a `kb/<root>/**/*.md` path, or a root's `_gaps.md`) gets additionalContext
naming the rag.py tools that print only the lines a lookup needs (raw_read_nudge). It never sets a permission decision,
so the command runs as it would without the hook; any other command, and any input it cannot read, gets no output.

Claude Code runs it from .claude/settings.json (a clone) and from the plugin's plugin.json (an installed plugin); it
reads the hook's JSON on stdin and prints the hook's JSON answer on stdout. `--test "kb: question"` prints what the
hook would answer, for a check from a shell (no query log row). It runs on every prompt of every session that has the
plugin, so a prompt without the prefix returns before kbfacts (and the kb) is loaded. A `kb:` or `kb+:` prompt also
writes one query log spool row (querylog.record: the question, the verdict, the articles and the kb lines
(path:line, tag, verdict) the pack returned, whether the hook answered it), after the answer is printed.
"""
import json, os, re, sys

PREFIX = re.compile(r"^\s*kb(\+)?\s*:\s*(\S.*)$", re.I | re.S)
LIMIT = 9500  # additionalContext is capped at 10,000 characters (kb/public/claude/hooks.md); keep the margin
HEAD_LINES = ("coverage:", "check:", "freshness:", "route:", "kb has:", "kb lacks:")
NOTE = ("\n\n(answered by the kb hook from the kb alone, without the model; ask again with `kb+:` to have Claude "
        "reason over these facts)")


def answer(prompt):
    """The hook's JSON answer for a prompt, or None to let it through unchanged."""
    return respond(prompt)[0]


def respond(prompt):
    """(the hook's answer or None, the query log fields of a `kb:` prompt or None)."""
    m = PREFIX.match(prompt or "")
    if not m:
        return None, None
    forward, question = bool(m.group(1)), m.group(2).strip()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import kbcommon, kbfacts
    try:
        res = kbfacts.pack(question)
    except kbcommon.RootError as e:  # a malformed ROOT_FILE or a clash between roots: never block the prompt on it
        return ({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                        "additionalContext": f"it-ops-kb could not read its roots: {e}"}},
                {"question": question, "forward": forward, "verdict": "error"})
    row = {"question": question, "forward": forward, "verdict": res["verdict"], "articles": res["paths"][:20],
           "pack": res["text"]}  # main keeps the pack's kb lines (ql_capture.pack_lines), never its text
    if res["verdict"] == "good" and not forward and not res.get("unmatched") and not res.get("spread"):
        return {"decision": "block", "reason": res["text"] + NOTE}, dict(row, answered=True)
    if res.get("route"):  # weak, none, or a flagged good: the differential (the kb has part, the live docs the rest)
        return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": routed(res)}}, \
            dict(row, answered=False)
    context = (f"The kb: hook ran the kb evidence pack for this question (coverage: {res['verdict']}). Answer from "
               "it with path:line and source urls. Search the kb again only if the pack misses what was asked."
               + "\n\n" + res["text"])
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": context}}, dict(row, answered=False)


def routed(res):
    """The context for a pack with a route (`web` or `split`): the differential instruction, then the pack (split) or
    only its coverage, check:, freshness:, route:, kb has: and kb lacks: lines (web: no fact lines), cut to LIMIT."""
    route, lines = res["route"], res["text"].splitlines()
    live = ("research only what the kb lacks in the live docs (the docs servers when available, else the official "
            "documentation on the web) and label that part 'live docs, not in the kb' with its url; never fill it "
            "from memory. Do not search the kb again.")
    if route == "web":
        lines = [ln for ln in lines[:lines.index("")] if ln.startswith(HEAD_LINES)] if "" in lines else \
            [ln for ln in lines if ln.startswith(HEAD_LINES)]
        what = "The kb has no coverage for this question, so no fact lines follow. State what it has and lacks from " \
               "the lines below, then " + live
    else:
        what = ("The kb covers part of this question. Answer what it has from the pack below with path:line and "
                "source urls, then " + live
                + (" The pack's check: line flags a possible false good: if no cited line answers the question "
                   "itself, treat the whole question as what the kb lacks."
                   if res.get("unmatched") or res.get("spread") else ""))
    head = (f"The kb: hook ran the kb evidence pack for this question (coverage: {res['verdict']}, route: {route}). "
            f"{what}\n\n")
    while lines and len(head) + len("\n".join(lines)) > LIMIT:  # over 10,000 characters the context is saved to a file
        lines.pop()
    return head + "\n".join(lines)


KB_MD = re.compile(r"(?:^|/)kb/([^/]+)/(.+\.md)$")  # a root's article or _gaps.md; roots starting `_` (_self, _querylog) are not
RAW_NUDGE = ("This command reads a kb article as a whole file. For a lookup the rag.py tools print only what is needed: "
             "`python3 _tools/rag.py show PATH:LINE -n 30` (the lines around one fact), `rag.py facts PREFIX --tag TAG` "
             "(facts of an article, by tag), `rag.py audit PREFIX` (tag counts, linked gaps and conflicts per article) "
             "and `rag.py search \"<keywords>\" --index` (also finds the gaps, answers and conflicts indexes). Try "
             "`rag.py pack \"<question>\"` first. The command runs unchanged; read the whole file only to edit it.")


def is_raw_read(command):
    """True when one command of a shell line reads a kb article or a root's _gaps.md with cat, head, tail, sed -n or
    grep -n. A path after `>` (a write), a command that merely names the path (rag.py show ...) and sed -i are not."""
    if not isinstance(command, str) or "kb/" not in command or ".md" not in command:
        return False  # the common case returns before shlex is loaded
    import shlex
    lex = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    try:
        tokens = list(lex)
    except ValueError:  # an unbalanced quote: not a command we can read
        return False
    segments, cur = [], []
    for t in tokens:
        if set(t) <= set(";&|()"):
            segments.append(cur)
            cur = []
        else:
            cur.append(t)
    segments.append(cur)
    for seg in segments:
        while seg and (re.match(r"^\w+=", seg[0]) or seg[0] in ("sudo", "command", "time", "env")):
            seg = seg[1:]
        if not seg:
            continue
        verb, args, paths, skip = os.path.basename(seg[0]), seg[1:], [], False
        for a in args:
            if skip:  # the target of a redirect
                skip = False
            elif ">" in a and set(a) <= set("<>&"):
                skip = True  # `>`, `>>`, `>&`: shlex makes them tokens of their own
            else:
                m = KB_MD.search(a)
                if m and not m.group(1).startswith("_"):
                    paths.append(a)
        if not paths:
            continue
        shorts = [a[1:] for a in args if re.match(r"^-[A-Za-z]+$", a)]
        if verb in ("cat", "head", "tail"):
            return True
        if verb == "sed" and (any("n" in s and "i" not in s for s in shorts) or "--quiet" in args or "--silent" in args):
            return True
        if verb == "grep" and (any("n" in s for s in shorts) or "--line-number" in args):
            return True
    return False


def raw_read_nudge(event):
    """The PreToolUse answer for a Bash event whose command reads a kb article whole, else None (no output)."""
    try:
        tool_input = event.get("tool_input")
        if event.get("tool_name", "Bash") == "Bash" and isinstance(tool_input, dict) \
                and is_raw_read(tool_input.get("command")):
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": RAW_NUDGE}}
    except Exception:  # a hint is never worth breaking a command over
        pass
    return None


def main():
    # the hook's JSON is UTF-8 on every OS; Windows would otherwise read and write the locale code page (cp1252)
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    if sys.argv[1:2] == ["--test"]:
        print(json.dumps(answer(" ".join(sys.argv[2:])), indent=1, ensure_ascii=False))
        return
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return  # not our input: never block a prompt on a parse error
    event = event if isinstance(event, dict) else {}
    if event.get("hook_event_name") == "PreToolUse" or "tool_input" in event:
        out = raw_read_nudge(event)
        if out is not None:
            print(json.dumps(out, ensure_ascii=False))
        return
    out, row = respond(event.get("prompt", ""))
    if out is not None:
        print(json.dumps(out, ensure_ascii=False))
    if row is not None:  # a kb: prompt: one spool row (kb/_self/querylog.md, Capture); a plain prompt loads nothing
        import ql_capture
        row["lines"] = ql_capture.pack_lines(row.pop("pack", ""))
        ql_capture.record("kb_hook", event.get("session_id"), prompt_id=event.get("prompt_id"), **row)


if __name__ == "__main__":
    main()
