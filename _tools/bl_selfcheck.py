"""`backlog.py selfcheck`: the orchestrator's check of its own tools, rules, hooks and host, run before `/kb-sprint run`
dispatches work (kb/_self/backlog.md, Self-check; kb/_self/tools.md; the kb-sprint skill, Self-check).

  selfcheck            print, read only, one line when every check passes, else one line for each check that failed
                       or could not be read, with the remedy the kb-sprint skill names (exit 0 passing, 1 a failure)
  selfcheck --full     the same without the cap on the output
  selfcheck --json     the results as one JSON object

The seven checks, each independent and each a result {name, state, detail, remedy}, `state` being `ok`, `fail` or
`unknown` (an input that cannot be read, never a guess and never a failure):

  allow-rules  every command the skills run (`SKILL_COMMANDS`, the list this module keeps as the source of truth, and
               `SKILL_TOOLS`) is covered by an allow rule of `.claude/settings.json` or `.claude/settings.local.json`;
               a `Bash(PATTERN)` rule covers a command that PATTERN matches whole, `*` standing for any text and a
               trailing ` *` also for no arguments, as Claude Code reads it; a `deny` rule is not read; a bare `Bash` rule covers every command
  checkout     the clone is no linked worktree of another checkout (`git rev-parse --git-common-dir` is its own
               `--git-dir`): workers dispatched there get their isolation worktrees in that other checkout
  hooks        `core.hooksPath` runs this checkout's `.githooks` (or the `.githooks` of another worktree of the clone)
               and each hook script is there; the plugin manifest parses and the files it names exist
  host         the 5-minute load average is under LOAD_PER_CORE times the cores, no host lock (`kb-tests.lock`,
               `kb-main.lock`) has a live holder older than `bl_stall.HOST_LOCK_WAIT_S` (pid and clone named; a
               holder that is gone is cleared by the next taker and is no failure)
  claims       no `doing` item shows `claim-no-commit`, `returned-no-commit` or `returned-staged` (`bl_stall.collect`'s
               signals, read from the claims, git and the worktrees' processes)
  orphans      no process in a checkout of the clone runs on after its parent is gone (`bl_procs.snapshot`'s
               `orphan`: a background run a session left behind, named, never signaled; a foreign process is a live
               session's and no failure, nor is a `hook`, a session-end run of the query log's distill younger than
               `bl_procs.HOOK_GRACE_S`, named with its age in the result's detail); `unknown` on a host that cannot
               list working directories
  main         the newest `ci.pipeline` row (`bl_stall.main_state`, the row `red-pipeline` writes) is not red;
               `unknown` with no row, which `backlog.py red-pipeline --status` reads from the forge (the one network
               call, never made here, so the check is offline and fast)

The output is capped: each check prints at most one line of at most LINE_MAX characters, a list in it names its first
SHOW entries and a count of the rest (`+K more`), and the whole is under MAX_CHARS characters, whole lines dropped
from the end with a last line that says how many; `--full` lifts the cap. Standard library only; imports `bl_base`,
`bl_cli`, `bl_procs` and `bl_stall` at load and never `backlog` (a layer rule); `tests` and `kg_hooks` are imported where
used. It registers its own subcommand when imported, so `backlog.py` carries only the import.
"""
import json
import os
import re
import subprocess
import time
from pathlib import Path

import bl_cli
import bl_procs
import bl_stall
from bl_base import Rejected, say

LOAD_PER_CORE = 1.5  # the 5-minute load average, per core, above which the host is too busy to take more workers
SHOW = 3  # entries of a list a line names; the rest is `+K more`
LINE_MAX = 330  # characters of one line
MAX_CHARS = 1500  # characters of the whole output; whole lines past it are dropped and counted
CLAIM_SIGNALS = ("claim-no-commit", "returned-no-commit", "returned-staged")  # the stall signals of a stale claim
LOCKS = ("kb-tests.lock", "kb-main.lock")  # the host's locks, in tests.HOST_LOCK_NAME and kg_lock.LOCK_NAME

# The commands the skills run (the kb-sprint, kb-item, kb-backlog and kb-verify skills, the runbook's Working on items
# and Definition of done), each as one real command line; the allow rules are matched against them whole. A command a
# skill starts to run is added here with its skill in the same change.
SKILL_COMMANDS = (
    "python3 _tools/backlog.py horizon --sprint SP",
    "python3 _tools/backlog.py next --sprint SP --all",
    "python3 _tools/backlog.py claim ST-00000000 --by s --commit",
    "python3 _tools/backlog.py land ST-00000000",
    "python3 _tools/backlog.py selfcheck",
    "python3 _tools/backlog.py stalled",
    "python3 _tools/backlog.py procs",
    "python3 _tools/backlog.py held --ref origin/main",
    "python3 _tools/kbgit.py sync --push",
    "python3 _tools/kbgit.py fix --check",
    "python3 _tools/tests.py --changed origin/main",
    "python3 _tools/check.py",
    "python3 _tools/rag.py eval",
    "python3 _tools/selfdoc.py section backlog Heading",
    "python3 _tools/selfdoc.py stale --since origin/main",
    "python3 .claude/skills/kb-verify/lint.py",
    "git fetch origin",
    "git status --short",
    "git log --grep KB-Work",
    "git merge-base --is-ancestor origin/main HEAD",
    "git rebase origin/main",
    "git add file",
    "git commit -m message",
    "git worktree add path -b branch origin/main",
    "git -C clone fetch origin",
    "glab mr view code/ST-00000000 -F json",
    "python3 _tools/backlog.py merge ST-00000000",
)
SKILL_TOOLS = ("Agent", "SendMessage", "Edit", "Write")  # tools the sprint's loop calls: each needs an allow rule

# The remedies, in the words of the kb-sprint skill's Self-check.
REMEDY = {
    "allow-rules": "ask the operator: the settings are the operator's; release the item, name the refused command, "
                   "never edit them",
    "checkout": "use a standalone `git clone` as the orchestrator's clone",
    "hooks": "run /kb-setup (`python3 _tools/kbgit.py install-hooks`) before any commit",
    "host-load": "dispatch fewer workers and give the tests a `-k` selection, which takes no host lock",
    "host-lock": "wait for the holder or narrow the tests to a `-k` selection; end the holder only when it is yours "
                 "and stuck",
    "claims": "ask its worker, or release it (`backlog.py release ID`) and dispatch it again with the failure named in "
              "the brief",
    "orphans": "end it if it is yours (`python3 _tools/backlog.py procs` lists each with its pid and checkout); "
               "nothing ends it for you",
    "main": "file the red pipeline as a bug (`backlog.py red-pipeline`) and take the next ready item",
    "main-unknown": "read it by hand: `python3 _tools/backlog.py red-pipeline --status` (needs the network)",
}


def result(name, state, detail, remedy=None):
    return {"name": name, "state": state, "detail": detail, "remedy": remedy if state != "ok" else None}


def listing(entries, show=SHOW):
    """`a, b, c +K more`: the first SHOW entries and the count of the rest."""
    entries = list(entries)
    more = f" +{len(entries) - show} more" if len(entries) > show else ""
    return ", ".join(entries[:show]) + more


# ---------------------------------------------------------------- the allow rules

def read_allow(root):
    """([rule], why): the allow rules of `.claude/settings.json` and `.claude/settings.local.json` under ROOT, or
    (None, why) when the project settings cannot be read as JSON; the local file is optional."""
    rules = []
    for i, name in enumerate(("settings.json", "settings.local.json")):
        path = Path(root) / ".claude" / name
        if not path.is_file():
            if i == 0:
                return None, f".claude/{name} is missing"
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            allow = data.get("permissions", {}).get("allow", [])
            rules += [r for r in allow if isinstance(r, str)]
        except (OSError, ValueError, AttributeError):
            return None, f".claude/{name} is not readable JSON"
    return rules, None


def rule_covers(rule, command):
    """Whether the allow rule `Bash(PATTERN)` (or the bare `Bash`) covers COMMAND: PATTERN matches the whole command,
    `*` standing for any text."""
    if rule == "Bash":
        return True
    m = re.fullmatch(r"Bash\((.*)\)", rule, re.S)
    if not m:
        return False
    pattern = m.group(1)
    if pattern.endswith(" *") and command == pattern[:-2]:  # `cmd *` takes the command with no arguments too
        return True
    return re.fullmatch(".*".join(re.escape(p) for p in pattern.split("*")), command, re.S) is not None


def check_allow(root, commands=SKILL_COMMANDS, tools=SKILL_TOOLS):
    rules, why = read_allow(root)
    if rules is None:
        return result("allow-rules", "fail", why, REMEDY["allow-rules"])
    missing = [c for c in commands if not any(rule_covers(r, c) for r in rules)]
    missing += [f"tool {t}" for t in tools if t not in rules and f"{t}(*)" not in rules]
    if missing:
        return result("allow-rules", "fail", f"{len(missing)} of {len(commands) + len(tools)} not covered: "
                      + listing(missing), REMEDY["allow-rules"])
    return result("allow-rules", "ok", f"{len(commands) + len(tools)} covered")


# ---------------------------------------------------------------- the checkout

def linked_worktree_of(root):
    """The other checkout (the parent of the common git dir) when ROOT is a linked worktree of it, else None; None too
    when git cannot say. Paths are resolved against ROOT, as `git rev-parse` may print them relative."""
    dirs = []
    for opt in ("--git-common-dir", "--git-dir"):
        p = subprocess.run(["git", "rev-parse", opt], cwd=root, capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        if p.returncode != 0 or not p.stdout.strip():
            return None
        dirs.append((Path(root) / p.stdout.strip()).resolve())
    return dirs[0].parent if dirs[0] != dirs[1] else None


def linked_worktree_message(root):
    """What is wrong when ROOT is a linked worktree of another checkout, else None."""
    other = linked_worktree_of(root)
    if other is None:
        return None
    return f"this clone is a linked worktree of the checkout {other}, so its workers' worktrees land there"


def check_checkout(root):
    msg = linked_worktree_message(root)
    if msg:
        return result("checkout", "fail", msg, REMEDY["checkout"])
    return result("checkout", "ok", "the clone is not a linked worktree")


# ---------------------------------------------------------------- the commit hooks and the plugin

def hooks_problem(root):
    """Why the commit hooks do not run in ROOT, or None."""
    try:
        import kg_hooks
        hooks, hdir = kg_hooks.HOOKS, kg_hooks.HOOKS_DIR
    except ImportError:
        return "the hook module cannot be loaded"
    p = subprocess.run(["git", "config", "--get", "core.hooksPath"], cwd=root, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    cur = p.stdout.strip()
    if not cur:
        return "core.hooksPath is not set"
    mine = (Path(root) / hdir).resolve()
    where = (Path(root) / cur).resolve()
    others = {(Path(w) / hdir).resolve() for w, _ in (bl_stall.worktrees(root) or [])}
    if where != mine and where not in others:
        return f"core.hooksPath {cur} is not this clone's {hdir}"
    absent = [h for h in hooks if not (where / h).is_file()]
    return f"{hdir} lacks {', '.join(absent)}" if absent else None


def plugin_problem(root):
    """Why the plugin does not load from ROOT, or None: its manifest parses and the paths it names are there."""
    path = Path(root) / ".claude-plugin" / "plugin.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ".claude-plugin/plugin.json is missing or not JSON"
    named = [p for k in ("skills", "agents") for p in manifest.get(k, []) if isinstance(p, str)]
    for server in (manifest.get("mcpServers") or {}).values():
        named += [a.replace("${CLAUDE_PLUGIN_ROOT}/", "") for a in server.get("args", []) if "CLAUDE_PLUGIN_ROOT" in a]
    gone = [p for p in named if not (Path(root) / p).exists()]
    return f"the plugin names {listing(gone)}, which are not there" if gone else None


def check_hooks(root):
    problems = [p for p in (hooks_problem(root), plugin_problem(root)) if p]
    if problems:
        return result("hooks", "fail", "; ".join(problems), REMEDY["hooks"])
    return result("hooks", "ok", "the commit hooks run and the plugin loads")


# ---------------------------------------------------------------- the host

def lock_facts(now, names=LOCKS):
    """[(name, pid, clone, age seconds)] of the host locks a live process holds."""
    import tests
    found = []
    for name in names:
        holder = tests.read_holder(os.path.join(tests.host_lock_dir(), name))
        if holder is None or not tests.pid_alive(holder["pid"]):
            continue
        started = bl_stall.iso_epoch(holder["started"].replace("Z", ".000Z"))
        found.append((name, holder["pid"], Path(holder["clone"]).name, 0 if started is None else max(0, int(now - started))))
    return found


def check_host(now=None, load=None, cores=None):
    now = time.time() if now is None else now
    try:
        load = os.getloadavg()[1] if load is None else load
    except (OSError, AttributeError):
        load = None
    cores = cores or os.cpu_count() or 1
    problems, remedy = [], []
    if load is not None and load > LOAD_PER_CORE * cores:
        problems.append(f"load {load:.1f} over {LOAD_PER_CORE:g} per core of {cores}")
        remedy.append(REMEDY["host-load"])
    old = [f"{n} held by pid {pid} (clone {clone}) for {age}s" for n, pid, clone, age in lock_facts(now)
           if age > bl_stall.HOST_LOCK_WAIT_S]
    if old:
        problems.append(listing(old))
        remedy.append(REMEDY["host-lock"])
    if problems:
        return result("host", "fail", "; ".join(problems), " | ".join(remedy))
    if load is None:
        return result("host", "unknown", "no load average on this host; the locks are within their limits",
                      REMEDY["host-load"])
    return result("host", "ok", "within its load and lock limits")


# ---------------------------------------------------------------- the claims, the orphans, main

def check_claims(report):
    stale = [r for r in report["items"] if r["state"] == "doing" and any(s in CLAIM_SIGNALS for s in r["signals"])]
    if not stale:
        return result("claims", "ok", "no claim is stale")
    each = [f"{r['label']} " + "/".join(s for s in r["signals"] if s in CLAIM_SIGNALS) for r in stale]
    return result("claims", "fail", f"{len(stale)} stale: " + listing(each), REMEDY["claims"])


def check_orphans(root, snapshot=bl_procs.snapshot):
    procs, _, why = snapshot(root)
    if procs is None:
        return result("orphans", "unknown", f"this host cannot list processes by working directory ({why})",
                      REMEDY["orphans"])
    orphans = [p for p in procs if p["kind"] == bl_procs.ORPHAN]
    if orphans:
        return result("orphans", "fail", f"{len(orphans)} orphan(s): "
                      + listing(f"pid {p['pid']} {p['comm']} in {p['where']}" for p in orphans), REMEDY["orphans"])
    hooks = [p for p in procs if p["kind"] == bl_procs.HOOK]
    if hooks:  # a session-end hook delivering, its parent gone for a few seconds: in flight, not left behind
        now = time.time()
        return result("orphans", "ok", "no orphan runs in a checkout of this clone; hook(s) in flight: " + listing(
            f"pid {p['pid']} {p['comm']} age {bl_procs.age_text(now - p['start'])}" for p in hooks))
    return result("orphans", "ok", "no orphan runs in a checkout of this clone")


def check_main(report):
    state, ts = report["main"]["state"], report["main"]["ts"]
    if state == "red":
        return result("main", "fail", f"the newest ci.pipeline row ({ts}) is red", REMEDY["main"])
    if state == "unknown":
        return result("main", "unknown", "no ci.pipeline row read", REMEDY["main-unknown"])
    return result("main", "ok", f"the newest ci.pipeline row ({ts}) is not red")


def run_checks(bl, now=None):
    """The seven results, in the order above. One `bl_stall.collect` serves the claims and main."""
    root = str(bl.root)
    try:
        report = bl_stall.collect(bl, now)
    except Exception as e:  # noqa: BLE001 - a read that fails is unknown, never an error of the check
        report = None
        why = type(e).__name__
    out = [check_allow(root), check_checkout(root), check_hooks(root), check_host(now)]
    out += [check_claims(report), check_orphans(root), check_main(report)] if report else [
        result("claims", "unknown", f"the claims could not be read ({why})", REMEDY["claims"]),
        check_orphans(root),
        result("main", "unknown", f"the pipeline row could not be read ({why})", REMEDY["main-unknown"])]
    return out


# ---------------------------------------------------------------- the output

def line_of(r, cap=True):
    text = f"{r['state'].upper()} {r['name']}: {r['detail']}" + (f" -> {r['remedy']}" if r["remedy"] else "")
    return text if not cap or len(text) <= LINE_MAX else text[:LINE_MAX - 6] + " [cut]"


def render(results, full=False):
    """The lines of the output: one when nothing failed and nothing is unknown, else the header and a line for each
    check not ok, whole lines dropped from the end past MAX_CHARS (named in the last line) unless FULL."""
    bad = [r for r in results if r["state"] != "ok"]
    failed = sum(r["state"] == "fail" for r in bad)
    if not bad:
        return [f"selfcheck: ok ({len(results)} checks passed)"]
    lines = [f"selfcheck: {failed} failed, {len(bad) - failed} unknown of {len(results)} checks"]
    lines += [line_of(r, not full) for r in bad]
    if full:
        return lines
    kept, size = [], 0
    for ln in lines:
        if size + len(ln) + 1 > MAX_CHARS - 80 and kept:
            break
        kept.append(ln)
        size += len(ln) + 1
    if len(kept) < len(lines):
        kept.append(f"selfcheck: {len(lines) - len(kept)} line(s) dropped; `selfcheck --full` prints all")
    return kept


def args_selfcheck(p):
    p.add_argument("--full", action="store_true", help="print every line without the cap")
    p.add_argument("--json", action="store_true", help="print the results as one JSON object")


def cmd_selfcheck(bl, a):
    if a.full and a.json:
        raise Rejected("selfcheck: --full and --json are alternatives")
    results = run_checks(bl)
    failed = any(r["state"] == "fail" for r in results)
    if a.json:
        print(json.dumps({"ok": not failed, "checks": results}, indent=2, sort_keys=True))
    else:
        for ln in render(results, a.full):
            say(ln)
    return 1 if failed else 0


bl_cli.register("selfcheck", cmd_selfcheck, args_selfcheck,
                help="check the orchestrator's tools, rules, hooks and host; one line when all hold, each failure with its remedy")
