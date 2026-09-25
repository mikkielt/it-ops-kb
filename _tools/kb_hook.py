#!/usr/bin/env python3
"""UserPromptSubmit hook: answer `kb:` prompts from the kb without the model (stdlib only).

  kb: <question>    run the evidence pack (kbfacts.pack). coverage: good -> block the prompt and show the pack to the
                    user as the block reason: the model is never called and no tokens are spent. weak -> let the
                    prompt through with the pack attached as context, so the model starts from the evidence and does
                    not search again. none -> let it through with one line of context: the kb has no coverage for the
                    missing words; say so and add nothing from memory.
  kb+: <question>   always let the prompt through with the pack attached (the model reasons over it).
  anything else     no output: the prompt goes to the model unchanged.

Claude Code runs it from .claude/settings.json (a clone) and from the plugin's plugin.json (an installed plugin); it
reads the hook's JSON on stdin and prints the hook's JSON answer on stdout. `--test "kb: question"` prints what the
hook would answer, for a check from a shell. It runs on every prompt of every session that has the plugin, so a
prompt without the prefix returns before kbfacts (and the kb) is loaded.
"""
import json, os, re, sys

PREFIX = re.compile(r"^\s*kb(\+)?\s*:\s*(\S.*)$", re.I | re.S)
NOTE = ("\n\n(answered by the kb hook from the kb alone, without the model; ask again with `kb+:` to have Claude "
        "reason over these facts)")


def answer(prompt):
    """The hook's JSON answer for a prompt, or None to let it through unchanged."""
    m = PREFIX.match(prompt or "")
    if not m:
        return None
    forward, question = bool(m.group(1)), m.group(2).strip()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import kbfacts
    res = kbfacts.pack(question)
    if res["verdict"] == "good" and not forward:
        return {"decision": "block", "reason": res["text"] + NOTE}
    if res["verdict"] == "none":
        words = [w for w in kbfacts.WORD.findall(question) if kbfacts.stem(w.lower()) in res["missing"]]
        what = ", ".join(dict.fromkeys(words)) or question
        return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext":
                f"it-ops-kb has no coverage for: {what}; say so and add nothing from memory"}}
    context = (f"The kb: hook ran the kb evidence pack for this question (coverage: {res['verdict']}). Answer from "
               "it with path:line and source urls. Search the kb again only if the pack misses what was asked."
               "\n\n" + res["text"])
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": context}}


def main():
    if sys.argv[1:2] == ["--test"]:
        print(json.dumps(answer(" ".join(sys.argv[2:])), indent=1, ensure_ascii=False))
        return
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return  # not our input: never block a prompt on a parse error
    out = answer(event.get("prompt", "") if isinstance(event, dict) else "")
    if out is not None:
        print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
