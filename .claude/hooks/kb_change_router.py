#!/usr/bin/env python3
"""UserPromptSubmit hook: route a request to change the kb to the skill that does it (stdlib only).

Registered in .claude/settings.json only, so it runs in a clone of this repository and never in a host project (the
plugin ships only kb_hook.py: a host cannot change the kb). The change skills are model-invocable; this hook makes the
routing deterministic instead of relying on the model to match a skill description.

  a prompt with a change verb (add, update, fix, refresh, research, commit, push, ..., or "work the query log")
  whose words name a change skill
                  -> additional context naming the likely skill(s) from the prompt's words, then the one-line routing
                     for any change; the model decides (a question that only uses such a word can ignore it)
  the same skill set again in one session (a follow-up such as "commit it" after "commit and push this")
                  -> no output: a marker per session_id under _cache/change_router/ records the sets already named
  kb: / kb+: prompts, slash commands, a single question, prompts without a change verb or whose words name no change
  skill, and messages from the harness (a subagent's report, a task notification: they start with `<`, `[` or
  "Another Claude session")
                  -> no output: the prompt goes to the model unchanged

`--reset` (a SessionStart hook with matcher compact|clear): removes that session's marker, so the first change request
after /compact or /clear is routed again (the conversation no longer holds the earlier routing line); always silent,
exit 0, nothing on stdout (a SessionStart hook's stdout becomes context), and a missing marker or directory is a no-op.

`--test "<prompt>"` prints what the hook would add, for a check from a shell (no session, so no marker).
"""
import json, os, re, sys

SECTION = "python3 _tools/selfdoc.py section maintaining"  # one section of kb/_self/maintaining.md, never the whole file
CONDUCT = f'`{SECTION} "Conduct for changes"`'  # the rules and the gate, read before any change
MARKERS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "_cache",
                       "change_router")  # one file per session: the skill sets already named in it
SAFE_SESSION = re.compile(r"[A-Za-z0-9_-]{1,80}")  # a session id that is safe as a file name

CHANGE = re.compile(r"\b(?:add|create|write|update|edit|change|modify|fix|correct|remove|delete|rename|move|refactor|"
                    r"implement|improve|extend|replace|commit|push|sync|merge|rebase|refresh|re-?verify|research|"
                    r"investigate|census|verify|bump|upgrade|set ?up|install|ingest|import|put|plan|schedule|triage)\b|"
                    r"\bwork (?:through )?(?:the )?query[ -]?log|\bfile (?:a |an )?(?:bug|defect)\b|"
                    r"\b(?:start|run|close|work on|pick up) (?:(?:the|a|this|next) )*(?:sprint|item|story|task|bug)\b|"
                    r"\b(?:EP|ST|TK|SB|BG|SP)-[a-z2-7]{8}\b", re.I)
QUESTION = re.compile(r"(?:how|what|why|when|where|which|who|does|do|did|is|are|was|can|could|should|would)\b[^\n]*\?\s*$",
                      re.I | re.S)  # a single question ("how do I fix error X?") is a lookup, not a change request
HARNESS = re.compile(r"[<\[]|Another Claude session sent a message")  # a subagent's report or a task notification,
# delivered as a prompt: not a person's request
ROUTES = (  # (skill, when, pattern): the first three that match are named, in this order
    ("kb-sprint", "plan, start, run, review or close a sprint", r"\bsprints?\b"),
    ("kb-item", "work on one backlog item", r"\b(?:EP|ST|TK|SB|BG)-[a-z2-7]{8}\b|\b(?:backlog|work) item\b|"
     r"\b(?:work on|pick up) (?:(?:the|a|this|next) )*(?:item|story|task|bug)\b"),
    ("kb-backlog", "plan epics, stories and tasks, file or triage a bug", r"\bbacklog\b|\bepics?\b|\bstor(?:y|ies)\b|"
     r"\bsubtasks?\b|\b(?:file|triage) (?:a |an |the )?(?:bug|defect)s?\b"),
    ("kb-census", "confirm every source", r"\bcensus\b|\ball (?:the |kb )?sources\b|\bevery source\b"),
    ("kb-refresh", "facts of an existing topic, file or source id", r"\brefresh|\bre-?verify|\bre-?check|\boutdated\b|"
     r"\b(?:update|fix|correct)\b[^.\n]*\b(?:article|topic|facts?)\b|\bstale\b|\bout of date\b|\bsources? (?:has |have )?(?:changed|moved)\b|\bS-[a-z2-7]{8}\b|\bS\d{3,4}\b"),
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
          f"stops); a change to tools, skills, hooks, plugin or rules also /kb-self. Rules: {CONDUCT}.")


def routes(prompt):
    """The (skill, when) pairs a change request's words name, at most three; [] for anything else."""
    if not isinstance(prompt, str):
        return []  # a malformed event (a number, a list, null) carries no request
    p = prompt.strip()
    if not p or p.startswith("/") or re.match(r"kb\+?\s*:", p, re.I) or HARNESS.match(p) or not CHANGE.search(p) \
            or QUESTION.match(p):
        return []
    return [(s, w) for s, w, rx in ROUTES if re.search(rx, p, re.I)][:3]


def answer(prompt):
    """The hook's JSON answer for a prompt, or None to let it through unchanged (no session state: see emit)."""
    hits = routes(prompt)
    if not hits:
        return None
    likely = "; ".join(f"/{s} ({w})" for s, w in hits)
    text = ("it-ops-kb change routing (from the prompt's words; ignore it if the prompt only asks a question): make a "
            "change to the kb through its skill, invoked with the Skill tool, not by editing freehand. Likely: "
            f"{likely}. {ALWAYS}")
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": text}}


def emit(event, markers=MARKERS):
    """The answer for a hook event, or None when the prompt routes nowhere or its skill set was already named in the
    event's session. A marker that cannot be read or written never blocks the prompt: the answer is given."""
    prompt = event.get("prompt", "") if isinstance(event, dict) else ""
    out = answer(prompt)
    sid = event.get("session_id") if isinstance(event, dict) else None
    if out is None or not (isinstance(sid, str) and SAFE_SESSION.fullmatch(sid)):
        return out
    key = "+".join(sorted(s for s, _ in routes(prompt)))
    path = os.path.join(markers, sid + ".txt")
    try:
        with open(path, encoding="utf-8") as f:
            if key in f.read().split():
                return None
    except (OSError, ValueError):
        pass
    try:
        os.makedirs(markers, exist_ok=True)
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(key + "\n")
    except OSError:
        pass
    return out


def reset(event, markers=MARKERS):
    """Remove the event's session marker (a compaction or clear dropped the routing line from the conversation).
    Nothing else is touched; an unsafe or missing session id, a missing marker or an unreadable directory is a no-op."""
    sid = event.get("session_id") if isinstance(event, dict) else None
    if isinstance(sid, str) and SAFE_SESSION.fullmatch(sid):
        try:
            os.remove(os.path.join(markers, sid + ".txt"))
        except OSError:
            pass


def main():
    # the hook's JSON is UTF-8 on every OS; Windows would otherwise read and write the locale code page (cp1252)
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    if sys.argv[1:2] == ["--test"]:
        print(json.dumps(answer(" ".join(sys.argv[2:])), indent=1, ensure_ascii=False))
        return
    try:
        event = json.load(sys.stdin)
    except (ValueError, RecursionError):
        return  # not our input: never block a prompt on a parse error
    if sys.argv[1:2] == ["--reset"]:
        reset(event)
        return  # silent: a SessionStart hook's stdout becomes context
    out = emit(event)
    if out is not None:
        print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
