#!/usr/bin/env python3
"""SessionStart, SessionEnd, PreToolUse and UserPromptExpansion hook: announce a session's work through coord.py and show overlapping
sessions, leaving the choice to the operator (stdlib only).

Registered in .claude/settings.json only, so it runs in a clone of this repository and never in a host project. It is
one client of the coordination protocol (`kb/_self/tools.md`, coord.py): every call to the store is a `coord.py`
command, and the hook adds no state of its own beyond the lease token coord.py shows only once.

  SessionStart    takes the presence lease `session/<session id>` (renewed when this session still holds it), posts an
                  `intent` with fields session and item (the item of a `work/<id>` branch and the items this session
                  claimed earlier; not again after /compact), then prints the `coord.py digest` lines for those items
  PreToolUse Bash a `backlog.py claim ID` command: the digest lines for ID, then an intent for ID (topic backlog-claim,
                  which the worker dispatched on `work/ID` skips at its SessionStart), so the session's claimed items
                  are announced too; any other command only renews the lease when it is due (below)
  PreToolUse Skill a `/kb-research` start Claude made: the digest lines for this session's items
  UserPromptExpansion a `/kb-research` the person typed, which bypasses PreToolUse: the same lines
  SessionEnd      releases the presence lease and forgets the token; a release that could not run (the store busy past
                  the call's timeout) keeps the token, and the next SessionStart of any session retries it

A tool event (Bash or Skill) of a live session renews its lease once less than half of LEASE_SECONDS is left, so the
session's intents keep showing in other sessions' digests however long it runs. The state file keeps the expiry the
last renew from a tool event returned, and the event reads that, so most events make no coord call; a SessionStart
keeps none, so the first tool event after a start renews once and takes the expiry from the store. A call that timed
out or failed for a busy store says nothing about the lease: the token stays, and the next try comes a minute later.
Only a refusal (exit 1: the token no longer holds the lease) drops the token.

A digest line is another session's: this session's own intent and lease are left out. The output is at most ten lines:
a first line, up to eight digest lines, and a line telling Claude to ask the operator whether to wait, join or
proceed; as one JSON object, its `systemMessage` (the operator's terminal) and `hookSpecificOutput.additionalContext`
(Claude's context). With no other session overlapping, a hook prints nothing. No hook blocks or exits 2: an overlap
informs, the operator decides; a missing store, an unreadable payload or any error ends in silence and exit 0.

The store is coord.py's own: `KB_COORD_STORE`, else `kb-coord/coord.sqlite` in the clone's common git directory, which
the clone's worktrees share. The lease token and items of a session sit in `_cache/coord_hook/<session id>.json` until its end.
"""
import json, os, re, subprocess, sys, time

HOME = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COORD = os.path.join(HOME, "_tools", "coord.py")
STATE = os.path.join(HOME, "_cache", "coord_hook")  # one file per session: its lease token and items
LEASE_SECONDS = 6 * 3600  # a session that ends without SessionEnd (a crash) drops out of `list` after this
RETRY_SECONDS = 60  # after a renew that could not run, the next tool event waits this long
SHOWN = 8  # digest lines shown: with the first and last line, ten in all
ITEM = r"[A-Za-z]{2}-[a-z0-9]{8}"
CLAIM = re.compile(r"\bbacklog\.py\s+claim\s+(" + ITEM + r")\b")
WORK_BRANCH = re.compile(r"work/(" + ITEM + r")")
CLAIM_TOPIC = "backlog-claim"  # the topic of the intent posted at a `backlog.py claim`, which a dispatched worker skips
UNSAFE = re.compile(r"[^A-Za-z0-9_.:/#@-]")  # what a coord.py field value may not hold
FOOTER = ("Claude: ask the operator whether to wait, join or proceed before starting this work; the operator decides, "
          "do not choose alone.")


def safe(text):
    return UNSAFE.sub("_", str(text))[:120]


def coord(*args):
    """(exit code, stdout) of one coord.py command; (None, "") when it cannot run."""
    try:
        p = subprocess.run([sys.executable, COORD, *args], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=8)
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
    path = state_path(sid)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)  # the lease token: owner-only
    os.chmod(path, 0o600)  # a file an earlier version made keeps its mode through the open
    with open(fd, "w", encoding="utf-8", newline="\n") as f:
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
    """Hold the presence lease session/<sid>: renew it with the saved token, else claim it. A renew that could not run
    (not exit 0 or 1) leaves the token: only a refusal means the lease is gone."""
    key = "session/" + sid
    if state.get("token"):
        rc = coord("renew", key, "--token", state["token"], "--ttl", str(LEASE_SECONDS))[0]
        if rc != 1:
            return
        state.pop("token")
    rc, out = coord("claim", key, "--ttl", str(LEASE_SECONDS), "--holder", sid)
    if rc == 0:
        state["token"] = json.loads(out)["token"]


def renew_if_due(sid, state):
    """On a tool event: renew the lease when less than half of LEASE_SECONDS is left by the expiry the state kept, or
    none is kept; the state is saved only when the lease changed."""
    if not state.get("token") or state.get("lease_until", 0) - time.time() >= LEASE_SECONDS / 2:
        return
    rc, out = coord("renew", "session/" + sid, "--token", state["token"], "--ttl", str(LEASE_SECONDS))
    if rc == 0:
        state["lease_until"] = json.loads(out)["expires"]
    elif rc != 1:
        state["lease_until"] = time.time() + LEASE_SECONDS / 2 + RETRY_SECONDS
    else:
        state.pop("token")
        state.pop("lease_until", None)
        lease(sid, state)
        state["lease_until"] = time.time() + LEASE_SECONDS if state.get("token") else 0
    save(sid, state)


def announce(sid, items, topic=None):
    if items:
        extra = ["--field", "topic=" + topic] if topic else []
        coord("post", "--kind", "intent", "--field", "session=" + sid, "--field", "item=" + ",".join(items)[:120], *extra)


def overlaps(sid, keys, dispatched=None):
    """The digest lines of other sessions for keys (this session's own intent and lease left out), without repeats.
    A worker's SessionStart passes the item of its `work/<id>` branch as dispatched: the claim intent the dispatching
    session posted for that item is no overlap, so that line is left out too."""
    if not keys:
        return []
    args = ["digest", "--lines", "10"] + [a for k in keys for a in ("--key", k)]
    lines = []
    for line in coord(*args)[1].splitlines():
        words = line.split()
        if dispatched and "topic=" + CLAIM_TOPIC in words and "item=" + dispatched in words:
            continue
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
    retry_releases(sid)
    state = load(sid)
    state.pop("ending", None)
    branch = branch_item(payload.get("cwd") or os.getcwd())
    items = list(state.get("items", []))
    if branch and branch not in items:
        items.append(branch)
    state["items"] = items
    lease(sid, state)
    state.pop("lease_until", None)
    if payload.get("source") != "compact":
        announce(sid, items)
    save(sid, state)
    show("SessionStart", items, overlaps(sid, items, branch))


def forget(path):
    try:
        os.remove(path)
    except OSError:
        pass


def session_end(sid):
    state = load(sid)
    if state.get("token") and coord("release", "session/" + sid, "--token", state["token"])[0] not in (0, 1):
        state["ending"] = sid  # the release could not run: a later SessionStart retries it with this token
        save(sid, state)
        return
    forget(state_path(sid))


def retry_releases(own):
    """At a SessionStart: release the lease of each session whose SessionEnd could not (its state file says ending),
    so its intents leave other sessions' digests once the store is free. The first release that cannot run ends the
    pass; a file older than the lease holds nothing and is removed."""
    try:
        names = sorted(os.listdir(STATE))
    except OSError:
        return
    for name in names:
        path = os.path.join(STATE, name)
        if path == state_path(own) or not name.endswith(".json"):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                state = json.load(f)
            old = time.time() - os.path.getmtime(path) > LEASE_SECONDS
        except (OSError, ValueError):
            continue
        if not isinstance(state, dict) or not state.get("ending"):
            continue
        if state.get("token") and not old:
            rc = coord("release", "session/" + str(state["ending"]), "--token", state["token"])[0]
            if rc not in (0, 1):
                return
        forget(path)


def pre_tool_use(payload, sid):
    tool, given = payload.get("tool_name"), payload.get("tool_input") or {}
    if tool == "Bash":
        found = CLAIM.search(given.get("command") or "")
        state = load(sid)
        if not found:
            renew_if_due(sid, state)
            return
        claimed = found.group(1)
        lines = overlaps(sid, [claimed])
        if claimed not in state.get("items", []):
            state["items"] = [*state.get("items", []), claimed]
            announce(sid, [claimed], CLAIM_TOPIC)
        lease(sid, state)
        state.pop("lease_until", None)
        save(sid, state)
        show("PreToolUse", [claimed], lines)
    elif tool == "Skill":
        if not research_start(payload, sid, "PreToolUse",
                              given.get("skill") or given.get("name") or given.get("command")):
            renew_if_due(sid, load(sid))


def research_start(payload, sid, event, name):
    """A `/kb-research` start, whether Claude called the Skill tool (PreToolUse) or the person typed it
    (UserPromptExpansion): the digest lines for this session's items. False when name is no `/kb-research`."""
    if str(name or "").rsplit(":", 1)[-1].lstrip("/") != "kb-research":
        return False
    state = load(sid)
    items = list(state.get("items", []))
    branch = branch_item(payload.get("cwd") or os.getcwd())
    if branch and branch not in items:
        items.append(branch)
    lease(sid, state)
    state.pop("lease_until", None)
    save(sid, {**state, "items": items})
    show(event, items, overlaps(sid, items))
    return True


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
        elif event == "UserPromptExpansion":
            research_start(payload, sid, event, payload.get("command_name"))
    except Exception:  # a hook never breaks a session: any error ends in silence
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
