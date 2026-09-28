#!/usr/bin/env python3
"""UserPromptSubmit hook: answer `kb:` prompts from the kb without the model (stdlib only).

  kb: <question>    run the evidence pack (kbfacts.pack). coverage: good -> block the prompt and show the pack to the
                    user as the block reason: the model is never called and no tokens are spent; but a good pack
                    with a `check:` line (a name the lead article never mentions, or key words spread over separate
                    facts: a possible false good) goes to the model as context, like weak, so the model decides. weak -> let the
                    prompt through with the pack attached as context, so the model starts from the evidence and does
                    not search again. none -> let it through with one line of context: the kb has no coverage for the
                    missing words; say so and add nothing from memory.
  kb+: <question>   always let the prompt through with the pack attached (the model reasons over it).
  anything else     no output: the prompt goes to the model unchanged.

Claude Code runs it from .claude/settings.json (a clone) and from the plugin's plugin.json (an installed plugin); it
reads the hook's JSON on stdin and prints the hook's JSON answer on stdout. `--test "kb: question"` prints what the
hook would answer, for a check from a shell (no query log row). It runs on every prompt of every session that has the
plugin, so a prompt without the prefix returns before kbfacts (and the kb) is loaded. A `kb:` or `kb+:` prompt also
writes one query log spool row (querylog.record: the question, the verdict, the articles and the kb lines
(path:line, tag, verdict) the pack returned, whether the hook answered it), after the answer is printed.
"""
import json, os, re, sys

PREFIX = re.compile(r"^\s*kb(\+)?\s*:\s*(\S.*)$", re.I | re.S)
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
    if res["verdict"] == "none":
        words = [w for w in kbfacts.WORD.findall(question) if kbfacts.stem(w.lower()) in res["missing"]]
        what = ", ".join(dict.fromkeys(words)) or question
        return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext":
                f"it-ops-kb has no coverage for: {what}; say so and add nothing from memory"}}, dict(row, answered=False)
    context = (f"The kb: hook ran the kb evidence pack for this question (coverage: {res['verdict']}). Answer from "
               "it with path:line and source urls. Search the kb again only if the pack misses what was asked."
               + (" Its check: line flags a possible false good (a name the lead article never mentions, or key "
                  "words spread over separate facts): if no cited line answers the question itself, say the kb does "
                  "not cover it." if res.get("unmatched") or res.get("spread") else "")
               + "\n\n" + res["text"])
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": context}}, dict(row, answered=False)


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
    out, row = respond(event.get("prompt", ""))
    if out is not None:
        print(json.dumps(out, ensure_ascii=False))
    if row is not None:  # a kb: prompt: one spool row (kb/_self/querylog.md, Capture); a plain prompt loads nothing
        import ql_capture
        row["lines"] = ql_capture.pack_lines(row.pop("pack", ""))
        ql_capture.record("kb_hook", event.get("session_id"), prompt_id=event.get("prompt_id"), **row)


if __name__ == "__main__":
    main()
