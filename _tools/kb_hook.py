#!/usr/bin/env python3
"""UserPromptSubmit hook: answer `kb:` prompts from the kb without the model (stdlib only).

  kb: <question>    run the evidence pack (kbfacts.pack). coverage: good -> block the prompt and show the pack to the
                    user as the block reason: the model is never called and no tokens are spent; but a good pack
                    with a route (a `check:` line: a name the lead article never mentions, or key words spread over
                    separate facts, a possible false good; or a word nowhere in the kb) goes to the model, so it decides.
                    A pack with a route (weak and routed good: `split`; none: `web`, kbfacts.route_of) lets the prompt
                    through with the differential as context: an instruction to answer what the kb has from the pack
                    with path:line and urls, research only what it lacks in the live docs, label that part 'live docs,
                    not in the kb' with its url and never fill it from memory, then the pack (split) or only its
                    coverage, route:, kb has: and kb lacks: lines (web: no fact lines), cut so the context stays under
                    the 10,000 characters Claude Code keeps.
  kb+: <question>   always let the prompt through (the model reasons over it): a clean good pack attached with a short
                    instruction, a pack with a route as for kb:.
  backlog: [text]   run `backlog.py horizon` and `backlog.py next --all --any` (subprocesses; the text is not read) and
                    block the prompt with their output as the reason: no model call. A command that fails or times out
                    lets the prompt through with a note of what failed.
  backlog+: [text]  always let the prompt through: the same output as additionalContext with a short instruction, cut so
                    the context stays under the limit.
  anything else     no output: the prompt goes to the model unchanged.

The same script answers a PreToolUse event on Bash or PowerShell (a JSON event with `tool_input`): a command that reads a
kb article whole (cat, head, tail, sed -n or grep -n on a `kb/<root>/**/*.md` path, or a root's `_gaps.md`; under
PowerShell Get-Content, gc, cat, type, Select-String or sls, a backslash or slash in the path) gets additionalContext
naming the rag.py tools that print only the lines a lookup needs (raw_read_nudge). It never sets a permission decision,
so the command runs as it would without the hook; any other command, and any input it cannot read, gets no output.

Claude Code runs it from .claude/settings.json (a clone) and from the plugin's plugin.json (an installed plugin); it
reads the hook's JSON on stdin and prints the hook's JSON answer on stdout. `--test "kb: question"` prints what the
hook would answer, for a check from a shell (no query log row). It runs on every prompt of every session that has the
plugin, so a prompt without the prefix returns before kbfacts (and the kb) is loaded. A `kb:` or `kb+:` prompt also
writes one query log spool row (querylog.record: the question, the verdict, the articles and the kb lines
(path:line, tag, verdict) the pack returned, whether the hook answered it), after the answer is printed.
"""
import json, os, re, subprocess, sys

PREFIX = re.compile(r"^\s*kb(\+)?\s*:\s*(\S.*)$", re.I | re.S)
BACKLOG_PREFIX = re.compile(r"^\s*backlog(\+)?\s*:", re.I)
BACKLOG_PY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backlog.py")
BACKLOG_COMMANDS = (("horizon",), ("next", "--all", "--any"))  # the plain-words backlog question's two answers
BACKLOG_TIMEOUT = 60
LIMIT = 9500  # additionalContext is capped at 10,000 characters (kb/public/claude/hooks.md); keep the margin
HEAD_LINES = ("coverage:", "check:", "freshness:", "route:", "kb has:", "kb lacks:")
NOTE = ("\n\n(answered by the kb hook from the kb alone, without the model; ask again with `kb+:` to have Claude "
        "reason over these facts)")
BACKLOG_NOTE = ("\n\n(answered by the backlog hook from backlog.py alone, without the model; ask again with `backlog+:` "
                "to have Claude reason over this output)")


def answer(prompt):
    """The hook's JSON answer for a prompt, or None to let it through unchanged."""
    return respond(prompt)[0]


def respond(prompt):
    """(the hook's answer or None, the query log fields of a `kb:` prompt or None)."""
    b = BACKLOG_PREFIX.match(prompt or "")
    if b:  # no query log row: the answer is the backlog's own state, not a kb lookup
        return backlog_answer(bool(b.group(1))), None
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
    if res["verdict"] == "good" and not forward and not res.get("route"):  # a routed good (a check: line, a word not in the kb) goes on
        return {"decision": "block", "reason": res["text"] + NOTE}, dict(row, answered=True)
    if res.get("route"):  # weak, none, or a flagged good: the differential (the kb has part, the live docs the rest)
        return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": routed(res)}}, \
            dict(row, answered=False)
    context = (f"The kb: hook ran the kb evidence pack for this question (coverage: {res['verdict']}). Answer from "
               "it with path:line and source urls. Search the kb again only if the pack misses what was asked."
               + "\n\n" + res["text"])
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": context}}, dict(row, answered=False)


def backlog_output():
    """(the output of each BACKLOG_COMMANDS entry joined under its command line, None) or (None, what failed)."""
    parts = []
    for args in BACKLOG_COMMANDS:
        shown = "backlog.py " + " ".join(args)
        try:
            p = subprocess.run([sys.executable, BACKLOG_PY, *args], capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=BACKLOG_TIMEOUT, cwd=os.path.dirname(os.path.dirname(BACKLOG_PY)),
                               env=dict(os.environ, PYTHONUTF8="1"))
        except (OSError, subprocess.SubprocessError) as e:
            return None, f"`{shown}` could not run: {type(e).__name__}"
        if p.returncode != 0:
            last = ((p.stderr or p.stdout).strip().splitlines() or ["no output"])[-1]
            return None, f"`{shown}` exited {p.returncode}: {last}"
        parts.append(f"$ {shown}\n{p.stdout.rstrip()}")
    return "\n\n".join(parts), None


def backlog_answer(forward):
    """The answer to a `backlog:` prompt (block, the output as the reason) or `backlog+:` (the output as context)."""
    text, error = backlog_output()
    if text is None:  # never block a prompt on a tool that does not run
        return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                       "additionalContext": f"The backlog hook could not read the backlog: {error}"}}
    if not forward:
        return {"decision": "block", "reason": text + BACKLOG_NOTE}
    head = ("The backlog hook ran `backlog.py horizon` and `backlog.py next --all --any` for this question. Answer from "
            "their output, naming item ids; run another backlog.py command only if it misses what was asked.\n\n")
    lines = text.splitlines()
    while lines and len(head) + len("\n".join(lines)) > LIMIT:  # over 10,000 characters the context is saved to a file
        lines.pop()
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": head + "\n".join(lines)}}


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


PS_READS = ("get-content", "gc", "cat", "type", "select-string", "sls")  # PowerShell verbs (any case) that read a file
# a PowerShell assignment target, `$t`, `[string]$t` or `$env:X`, alone or glued to its operator and value (`$t=gc`)
PS_TARGET = re.compile(r"^(?:\[[^\s$=]*\])?\$[\w:{}]+(?:([-+*/%?]?=)(?!=)(.*))?$")
PS_OP = re.compile(r"^[-+*/%?]?=(?!=)(.*)$")  # the operator as a token of its own, perhaps glued to the value (`=gc`)


def _ps_unassign(seg):
    """The segment without a leading PowerShell assignment (`$t = gc x`, `[string]$t=gc x`): the command is what
    follows, so its verb is found. A `$t` alone or compared (`$t -eq 1`) is left as it is."""
    m = PS_TARGET.match(seg[0])
    if not m:
        return seg
    if m.group(1):  # `$t=value`: the value starts the command
        return ([m.group(2)] if m.group(2) else []) + seg[1:]
    op = PS_OP.match(seg[1]) if len(seg) > 1 else None
    if not op:
        return seg
    return ([op.group(1)] if op.group(1) else []) + seg[2:]


def _sed_options(args):
    """(quiet, in_place) from a sed command's arguments, wherever the options stand. A short bundle is read letter by
    letter: `n` is quiet, `i` (GNU, its suffix attached: -i.bak) or `I` (BSD) is in place and ends the bundle, as `e`,
    `f` and `l` end it with their argument, which is the next token when nothing follows them (sed -n -e p). Long
    forms: --quiet, --silent, --in-place, --in-place=SUFFIX."""
    quiet = in_place = False
    it = iter(args)
    for a in it:
        if a == "--quiet" or a == "--silent":
            quiet = True
        elif a == "--in-place" or a.startswith("--in-place="):
            in_place = True
        elif a.startswith("-") and not a.startswith("--") and len(a) > 1:
            for k, c in enumerate(a[1:], 1):
                if c == "n":
                    quiet = True
                elif c in "iI":
                    in_place = True
                    break
                elif c in "efl":
                    if k == len(a) - 1:
                        next(it, None)
                    break
                elif not c.isalpha():
                    break
    return quiet, in_place


def is_raw_read(command, powershell=False):
    """True when one command of a shell line reads a kb article or a root's _gaps.md with cat, head, tail, sed -n or
    grep -n; with `powershell` (a PowerShell tool event) with Get-Content, gc, cat, type, Select-String or sls, also
    after an assignment (`$t = gc ...`) or as `-Path:value`, and a backslash in a path is a separator. A path after `>` (a write), a command that merely names the path
    (rag.py show ...), a sed with -i or --in-place among its options (an edit, -n or not) and Set-Content are not."""
    if not isinstance(command, str):
        return False
    if powershell:
        command = command.replace("\\", "/")  # a backslash is no escape in PowerShell, and kb/... is the one path form
    if "kb/" not in command or ".md" not in command:
        return False  # the common case returns before shlex is loaded
    import shlex
    lex = shlex.shlex(command.replace("\n", " ; "), posix=not powershell, punctuation_chars=True)
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
        while seg and not powershell and (re.match(r"^\w+=", seg[0]) or seg[0] in ("sudo", "command", "time", "env")):
            seg = seg[1:]
        if seg and powershell:
            seg = _ps_unassign(seg)
        if not seg:
            continue
        verb, args, paths, skip = os.path.basename(seg[0]), seg[1:], [], False
        if powershell:  # quotes stay in the tokens; `a.md,b.md` is a list; the verb's case and module prefix do not matter;
            verb = verb.strip("'\"").lower()  # `-Path:value` is `-Path value`
            args = [re.sub(r"^-\w+:", "", x.strip("'\"")).strip("'\"") for a in args for x in a.split(",")]
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
        if powershell:
            if verb in PS_READS:
                return True
            continue
        shorts = [a[1:] for a in args if re.match(r"^-[A-Za-z]+$", a)]
        if verb in ("cat", "head", "tail"):
            return True
        if verb == "sed":
            quiet, in_place = _sed_options(args)
            if quiet and not in_place:
                return True
        if verb == "grep" and (any("n" in s for s in shorts) or "--line-number" in args):
            return True
    return False


def raw_read_nudge(event):
    """The PreToolUse answer for a Bash or PowerShell event whose command reads a kb article whole, else None (no
    output). Both tools send the command as tool_input.command (kb/public/claude/hooks.md)."""
    try:
        tool_input, tool = event.get("tool_input"), event.get("tool_name", "Bash")
        if tool in ("Bash", "PowerShell") and isinstance(tool_input, dict) \
                and is_raw_read(tool_input.get("command"), powershell=tool == "PowerShell"):
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
