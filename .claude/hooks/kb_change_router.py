#!/usr/bin/env python3
"""UserPromptSubmit hook: route a request to change the kb to the skill that does it (stdlib only).

Registered in .claude/settings.json only, so it runs in a clone of this repository and never in a host project (the
plugin ships only kb_hook.py: a host cannot change the kb). The change skills are model-invocable; this hook makes the
routing deterministic instead of relying on the model to match a skill description.

  a prompt with a change verb (add, update, fix, refresh, research, commit, push, ..., or "work the query log")
                  -> additional context naming the likely skill(s) from the prompt's words, then the one-line routing
                     for any change; the model decides (a question that only uses such a word can ignore it)
  kb: / kb+: prompts, slash commands, a single question, prompts without a change verb, and messages from the
  harness (a subagent's report, a task notification: they start with `<`, `[` or "Another Claude session")
                  -> no output: the prompt goes to the model unchanged

`--test "<prompt>"` prints what the hook would add, for a check from a shell.
"""
import json, re, sys

SELF = "kb/_self"  # the kb's own docs

CHANGE = re.compile(r"\b(?:add|create|write|update|edit|change|modify|fix|correct|remove|delete|rename|move|refactor|"
                    r"implement|improve|extend|replace|commit|push|sync|merge|rebase|refresh|re-?verify|research|"
                    r"investigate|census|verify|bump|upgrade|set ?up|install|ingest|import|put)\b|"
                    r"\bwork (?:through )?(?:the )?query[ -]?log", re.I)
QUESTION = re.compile(r"(?:how|what|why|when|where|which|who|does|do|did|is|are|was|can|could|should|would)\b[^\n]*\?\s*$",
                      re.I | re.S)  # a single question ("how do I fix error X?") is a lookup, not a change request
HARNESS = re.compile(r"[<\[]|Another Claude session sent a message")  # a subagent's report or a task notification,
# delivered as a prompt: not a person's request
ROUTES = (  # (skill, when, pattern): the first three that match are named, in this order
    ("kb-census", "confirm every source", r"\bcensus\b|\ball (?:the |kb )?sources\b|\bevery source\b"),
    ("kb-refresh", "facts of an existing topic, file or source id", r"\brefresh|\bre-?verify|\bre-?check|\boutdated\b|"
     r"\bstale\b|\bout of date\b|\bsources? (?:has |have )?(?:changed|moved)\b|\bS-[a-z2-7]{8}\b|\bS\d{3,4}\b"),
    ("kb-ingest", "a team's repository into a root", r"\bingest|\bput (?:it|them) here\b|\brepo(?:sitor(?:y|ies))? into\b|"
     r"\b(?:source|import) (?:the |this |our |a |their )?(?:team'?s? )?(?:\S+ )?repo(?:sitor(?:y|ies))?\b"),
    ("kb-add-root", "a new knowledge root under kb/", r"\bnew (?:kb )?root\b|\b(?:add|create) (?:a |an )?(?:new )?(?:kb |knowledge )?root\b"),
    ("kb-add-topic", "a new topic, article or data table", r"\bnew (?:topic|article|domain|table)\b|"
     r"\b(?:add|write|create) (?:a |an )?(?:new )?(?:topic|article|domain|table)\b"),
    ("kb-probe", "measure a documentation provider's change signals", r"\bprobe\b|\bproviders?\b"),
    ("kb-research", "research a question and extend the topics; `--queue [N]` for the query log's gaps",
     r"\bresearch|\binvestigat|\bfind out\b|\bquery[ -]?log'?s?\b[^.\n]*\b(?:gaps?|queue)\b"),
    ("kb-git-sync", "commit, push, pull, merge", r"\bcommit\b|\bpush|\bpull\b|\bsync\b|\brebase\b|\bmerg|\bconflict"),
    ("kb-verify", "check a change before committing", r"\bverify\b|\bgate\b|\blint\b|\bbefore (?:the |a )?commit"),
    ("kb-setup", "a fresh clone", r"\bset ?up\b|\bfresh clone\b|\binstall (?:the )?hooks?\b"),
    ("kb-self", "after changing tools, skills, hooks, plugin, config or rules", r"_tools/|\.claude|\btools?\b|"
     r"\bskills?\b|\bhooks?\b|\bplugin\b|\btests?\b|\b_self\b|\bAGENTS\.md\b|\bREADME\b|\bdocs?\b|\.py\b"),
)
ALWAYS = ("Any change: /kb-verify before committing, then `python3 _tools/kbgit.py sync --push` (/kb-git-sync if it "
          f"stops); a change to tools, skills, hooks, plugin or rules also /kb-self. Rules: {SELF}/maintaining.md.")


def answer(prompt):
    """The hook's JSON answer for a prompt, or None to let it through unchanged."""
    p = (prompt or "").strip()
    if not p or p.startswith("/") or re.match(r"kb\+?\s*:", p, re.I) or HARNESS.match(p) or not CHANGE.search(p) \
            or QUESTION.match(p):
        return None
    hits = [(s, w) for s, w, rx in ROUTES if re.search(rx, p, re.I)][:3]
    likely = "; ".join(f"/{s} ({w})" for s, w in hits) or f"none named by the wording; pick from the list in {SELF}/maintaining.md"
    text = ("it-ops-kb change routing (from the prompt's words; ignore it if the prompt only asks a question): make a "
            "change to the kb through its skill, invoked with the Skill tool, not by editing freehand. Likely: "
            f"{likely}. {ALWAYS}")
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": text}}


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
    out = answer(event.get("prompt", "") if isinstance(event, dict) else "")
    if out is not None:
        print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
