#!/usr/bin/env python3
"""SessionStart, SessionEnd and PreToolUse hook: announce a session's work through coord.py and show overlapping
sessions, leaving the choice to the operator (stdlib only).

Registered in .claude/settings.json only, so it runs in a clone of this repository and never in a host project. It is
one client of the coordination protocol (`kb/_self/tools.md`, coord.py): every call to the store is a `coord.py`
command, and the hook adds no state of its own beyond the lease token coord.py shows only once.

  SessionStart    takes the presence lease `session/<session id>` (renewed when this session still holds it), posts an
                  `intent` with fields session and item (the item of a `work/<id>` branch and the items this session
                  claimed earlier; not again after /compact), then prints the `coord.py digest` lines for those items
  PreToolUse Bash a `backlog.py claim ID` command: the digest lines for ID, then an intent for ID, so the session's
                  claimed items are announced too; any other command returns at once, touching nothing
  PreToolUse Skill a `/kb-research` start: the digest lines for this session's items
  SessionEnd      releases the presence lease and forgets the token

A digest line is another session's: this session's own intent and lease are left out. The output is at most ten lines:
a first line, up to eight digest lines, and a line telling Claude to ask the operator whether to wait, join or
proceed; as one JSON object, its `systemMessage` (the operator's terminal) and `hookSpecificOutput.additionalContext`
(Claude's context). With no other session overlapping, a hook prints nothing. No hook blocks or exits 2: an overlap
informs, the operator decides; a missing store, an unreadable payload or any error ends in silence and exit 0.

The store is `KB_COORD_STORE`, else `kb-coord/coord.sqlite` in the clone's common git directory, which the clone's
worktrees share. The lease token and items of a session sit in `_cache/coord_hook/<session id>.json` until its end.
"""
import json, os, re, subprocess, sys

HOME = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COORD = os.path.join(HOME, "_tools", "coord.py")
STATE = os.path.join(HOME, "_cache", "coord_hook")  # one file per session: its lease token and items
LEASE_SECONDS = 6 * 3600  # a session that ends without SessionEnd (a crash) drops out of `list` after this
SHOWN = 8  # digest lines shown: with the first and last line, ten in all
ITEM = r"[A-Za-z]{2}-[a-z0-9]{8}"
CLAIM = re.compile(r"\bbacklog\.py\s+claim\s+(" + ITEM + r")\b")
WORK_BRANCH = re.compile(r"work/(" + ITEM + r")")
UNSAFE = re.compile(r"[^A-Za-z0-9_.:/#@-]")  # what a coord.py field value may not hold
FOOTER = ("Claude: ask the operator whether to wait, join or proceed before starting this work; the operator decides, "
          "do not choose alone.")


def safe(text):
    return UNSAFE.sub("_", str(text))[:120]


def coord(*args):
    """(exit code, stdout) of one coord.py command; (None, "") when it cannot run."""
    env = dict(os.environ)
    if not env.get("KB_COORD_STORE"):
        try:
            p = subprocess.run(["git", "-C", HOME, "rev-parse", "--git-common-dir"], capture_output=True, text=True,
                               encoding="utf-8", timeout=10)
            common = os.path.join(HOME, p.stdout.strip())
        except (OSError, subprocess.TimeoutExpired):
            return None, ""
        env["KB_COORD_STORE"] = os.path.join(common, "kb-coord", "coord.sqlite")
    try:
        p = subprocess.run([sys.executable, COORD, *args], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=env, timeout=8)
    except (OSError, subprocess.TimeoutExpired):
        return None, ""
    return p.returncode, p.stdout


def state_path(sid):
    return os.path.join(STATE, safe(sid)[:80].replace("/", "_") + ".json")


def load(sid):
    try:
        with open(state_path(sid), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(sid, state):
    os.makedirs(STATE, exist_ok=True)
    with open(state_path(sid), "w", encoding="utf-8", newline="\n") as f:
        json.dump(state, f)


def branch_item(cwd):
    """The item id of a `work/<id>` branch checked out in cwd, else None."""
    try:
        p = subprocess.run(["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True,
                           encoding="utf-8", timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = WORK_BRANCH.fullmatch(p.stdout.strip())
    return m.group(1) if m else None


def lease(sid, state):
    """Hold the presence lease session/<sid>: renew it with the saved token, else claim it."""
    key = "session/" + sid
    if state.get("token"):
        if coord("renew", key, "--token", state["token"], "--ttl", str(LEASE_SECONDS))[0] == 0:
            return
        state.pop("token")
    rc, out = coord("claim", key, "--ttl", str(LEASE_SECONDS), "--holder", sid)
    if rc == 0:
        state["token"] = json.loads(out)["token"]


def announce(sid, items):
    if items:
        coord("post", "--kind", "intent", "--field", "session=" + sid, "--field", "item=" + ",".join(items)[:120])


def overlaps(sid, keys):
    """The digest lines of other sessions for keys (this session's own intent and lease left out), without repeats."""
    if not keys:
        return []
    args = ["digest", "--lines", "10"] + [a for k in keys for a in ("--key", k)]
    lines = []
    for line in coord(*args)[1].splitlines():
        words = line.split()
        if line.strip() and "session=" + sid not in words and "holder=" + sid not in words and line not in lines:
            lines.append(line)
    return lines


def show(event, keys, lines):
    if not lines:
        return
    text = "\n".join([f"coord: other sessions overlap this session's work ({', '.join(keys)[:80]}), newest first:",
                      *lines[:SHOWN], FOOTER])
    print(json.dumps({"systemMessage": text, "hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}))


def session_start(payload, sid):
    state = load(sid)
    branch = branch_item(payload.get("cwd") or os.getcwd())
    items = list(state.get("items", []))
    if branch and branch not in items:
        items.append(branch)
    state["items"] = items
    lease(sid, state)
    if payload.get("source") != "compact":
        announce(sid, items)
    save(sid, state)
    show("SessionStart", items, overlaps(sid, items))


def session_end(sid):
    state = load(sid)
    if state.get("token"):
        coord("release", "session/" + sid, "--token", state["token"])
    try:
        os.remove(state_path(sid))
    except OSError:
        pass


def pre_tool_use(payload, sid):
    tool, given = payload.get("tool_name"), payload.get("tool_input") or {}
    if tool == "Bash":
        found = CLAIM.search(given.get("command") or "")
        if not found:
            return
        claimed = found.group(1)
        state = load(sid)
        lines = overlaps(sid, [claimed])
        if claimed not in state.get("items", []):
            state["items"] = [*state.get("items", []), claimed]
            announce(sid, [claimed])
        lease(sid, state)
        save(sid, state)
        show("PreToolUse", [claimed], lines)
    elif tool == "Skill":
        name = str(given.get("skill") or given.get("name") or given.get("command") or "")
        if name.rsplit(":", 1)[-1].lstrip("/") != "kb-research":
            return
        state = load(sid)
        items = list(state.get("items", []))
        branch = branch_item(payload.get("cwd") or os.getcwd())
        if branch and branch not in items:
            items.append(branch)
        lease(sid, state)
        save(sid, {**state, "items": items})
        show("PreToolUse", items, overlaps(sid, items))


def main():
    try:
        payload = json.load(sys.stdin)
        sid = safe(payload.get("session_id") or "")
        event = payload.get("hook_event_name")
        if not sid:
            return 0
        if event == "SessionStart":
            session_start(payload, sid)
        elif event == "SessionEnd":
            session_end(sid)
        elif event == "PreToolUse":
            pre_tool_use(payload, sid)
    except Exception:  # a hook never breaks a session: any error ends in silence
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
