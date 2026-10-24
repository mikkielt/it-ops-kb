"""`backlog.py selfcheck`: the orchestrator's check of its own tools, rules, hooks and host, run before `/kb-sprint run`
dispatches work (kb/_self/backlog.md, Self-check; kb/_self/tools.md; the kb-sprint skill, Self-check).

  selfcheck            print, read only, one line when every check passes, else one line for each check that failed
                       or could not be read, with the remedy the kb-sprint skill names (exit 0 passing, 1 a failure)
  selfcheck --full     the same without the cap on the output
  selfcheck --json     the results as one JSON object

The eight checks, each independent and each a result {name, state, detail, remedy}, `state` being `ok`, `fail` or
`unknown` (an input that cannot be read, never a guess and never a failure):

  allow-rules  every command the skills run (`SKILL_COMMANDS`, the list this module keeps as the source of truth, and
               `SKILL_TOOLS`) is covered by an allow rule of `.claude/settings.json` or `.claude/settings.local.json`;
               a `Bash(PATTERN)` rule covers a command that PATTERN matches whole, `*` standing for any text and a
               trailing ` *` also for no arguments, as Claude Code reads it; a `deny` rule is not read; a bare `Bash` rule covers every command;
               in a host project (a root that is not the plugin's own checkout, `own_checkout`) only the sprint loop's
               commands (`LOOP_COMMANDS`), the commands its `backlog.json` names (`land_push`, `land_stale`, `land_eval`,
               `land_lint`) and its forge's CLI command, when the file sets `forge`, are required, and settings that
               are missing or unreadable read `unknown`
  checkout     the clone is no linked worktree of another checkout (`git rev-parse --git-common-dir` is its own
               `--git-dir`), or is one whose workers `land` accepts (`bl_base.main_worker_dir`: the other checkout's
               `.claude/worktrees/`, named with the clone's own in the detail); a linked worktree whose workers it
               refuses fails, and one git cannot be read for is `unknown`
  hooks        `core.hooksPath` runs this checkout's `.githooks` (or the `.githooks` of another worktree of the clone)
               and each hook script is there; the plugin manifest parses and the files it names exist; in a host
               project the check is skipped, said so, unless `core.hooksPath` is set, and then it needs only that path
               to exist, and the plugin manifest is not read
  host         the 5-minute load average is under SUITE_LOAD_PER_CORE times the cores (the load a whole-suite
               tests.py run fits its seconds ceiling at, which `done` of a review story reads too, naming the host;
               it is lower than LOAD_PER_CORE, so a load over that one fails it as well, in one short detail with
               one remedy that names both), no host lock (`kb-tests.lock`,
               `kb-main.lock`) has a live holder older than `bl_stall.HOST_LOCK_WAIT_S` (pid and clone named; a
               holder that is gone is cleared by the next taker and is no failure)
  claims       no `doing` item shows `claim-no-commit`, `returned-no-commit`, `returned-staged` or `mr-dead`
               (`bl_stall.collect`'s signals, read from the claims, git, the worktrees' processes and one read of
               each claimed item's `code/<id>` request through `bl_forge`, the one network call of this command; a
               read that fails is `unknown:forge`, no failure; a project with no forge, an empty `forge` setting,
               reads none and has no `unknown:forge`)
  orphans      no process in a checkout of the clone runs on after its parent is gone (`bl_procs.snapshot`'s
               `orphan`: a background run a session left behind, named, never signaled; a foreign process is a live
               session's and no failure, nor is a `hook`, a session-end run of the query log's distill that holds
               the distill lock or is younger than `ql_distill.USAGE_LOCK_WAIT_S` plus `bl_procs.HOOK_MARGIN_S`,
               named with its age in the result's detail); `unknown` on a host that cannot list working directories
  main         the newest `ci.pipeline` row (`bl_stall.main_state`, the row `red-pipeline` writes) is not red;
               `unknown` with no row, which `backlog.py red-pipeline --status` reads from the forge (this check reads
               the rows only and makes no forge call of its own)
  leftovers    the recorded leftovers `backlog.py tidy` lists (`leftovers`, read through `bl_clean.safe_to_remove`):
               the detail names how many `remove` and the bytes they free; it fails only when the free space of the
               clone's volume is under tidy's disk-pressure limit (`bl_clean.DISK_FREE_GB`), else it is `ok`; `unknown`
               when the coord store, the integration main or git cannot be read

The output is capped: each check prints at most one line of at most LINE_MAX characters, a list in it names its first
SHOW entries and a count of the rest (`+K more`), and the whole is under MAX_CHARS characters, whole lines dropped
from the end with a last line that says how many; `--full` lifts the cap. Standard library only; imports `bl_base`,
`bl_cli`, `bl_procs` and `bl_stall` at load and never `backlog` (a layer rule); `tests`, `kg_hooks` and `bl_clean` are
imported where used. `leftovers` is also what kbmon's cleanup panel (`mon_clean.py`) reads. It registers its own subcommand when imported, so `backlog.py` carries only the import.
"""
import json
import os
import platform
import re
import subprocess
import time
from pathlib import Path

import bl_cli
import bl_procs
import bl_stall
from bl_base import Refused, Rejected, main_worker_dir, say, worker_dir, worker_dirs

LOAD_PER_CORE = 1.5  # the 5-minute load average, per core, above which the host is too busy to take more workers
SUITE_LOAD_PER_CORE = 0.5  # the same load, per core, above which a whole-suite tests.py run no longer fits its darwin
#                            seconds ceiling: the host check fails over it and a review story's `done` refuses over it
SHOW = 3  # entries of a list a line names; the rest is `+K more`
LINE_MAX = 330  # characters of one line
MAX_CHARS = 1500  # characters of the whole output; whole lines past it are dropped and counted
CLAIM_SIGNALS = ("claim-no-commit", "returned-no-commit", "returned-staged", "mr-dead")  # the stall signals of a claim
LOCKS = ("kb-tests.lock", "kb-main.lock")  # the host's locks, in tests.HOST_LOCK_NAME and kg_lock.LOCK_NAME
BYTES_BUDGET_S = 3  # the longest all the walks that measure what the removable leftovers free take together

# The commands the skills run (the kb-sprint, kb-item, kb-backlog and kb-verify skills, the runbook's Working on items
# and Definition of done), each as one real command line; the allow rules are matched against them whole. A command a
# skill starts to run is added here with its skill in the same change. LOOP_COMMANDS are the sprint loop's own, which
# every project runs; KB_COMMANDS are the kb's gate and check scripts, which a host project names in its backlog.json
# (`land_*`) or does not run; FORGE_COMMANDS is the request read of the project's forge, by its `forge` setting.
LOOP_COMMANDS = (
    "python3 _tools/backlog.py horizon --sprint SP",
    "python3 _tools/backlog.py next --sprint SP --all",
    "python3 _tools/backlog.py claim ST-00000000 --by s --commit",
    "python3 _tools/backlog.py land ST-00000000",
    "python3 _tools/backlog.py selfcheck",
    "python3 _tools/backlog.py stalled",
    "python3 _tools/backlog.py procs",
    "python3 _tools/backlog.py held --ref origin/main",
    "git fetch origin",
    "git status --short",
    "git log --grep KB-Work",
    "git merge-base --is-ancestor origin/main HEAD",
    "git rebase origin/main",
    "git add file",
    "git commit -m message",
    "git worktree add path -b branch origin/main",
    "git -C clone fetch origin",
    "python3 _tools/backlog.py merge ST-00000000",
)
KB_COMMANDS = (
    "python3 _tools/kbgit.py sync --push",
    "python3 _tools/kbgit.py fix --check",
    "python3 _tools/tests.py --changed origin/main",
    "python3 _tools/check.py",
    "python3 _tools/rag.py eval",
    "python3 _tools/selfdoc.py section backlog Heading",
    "python3 _tools/selfdoc.py stale --since origin/main",
    "python3 .claude/skills/kb-verify/lint.py",
)
FORGE_COMMANDS = {"gitlab": ("glab mr view code/ST-00000000 -F json",), "github": ("gh pr view code/ST-00000000 --json state",)}
SKILL_COMMANDS = LOOP_COMMANDS + KB_COMMANDS + FORGE_COMMANDS["gitlab"]  # all of them: what the kb's own checkout needs
LAND_SETTINGS = ("land_push", "land_stale", "land_eval", "land_lint")  # the backlog.json commands a host names
SKILL_TOOLS = ("Agent", "SendMessage", "Edit", "Write")  # tools the sprint's loop calls: each needs an allow rule

# The remedies, in the words of the kb-sprint skill's Self-check.
REMEDY = {
    "allow-rules": "ask the operator: the settings are the operator's; release the item, name the refused command, "
                   "never edit them",
    "checkout": "use a standalone `git clone` as the orchestrator's clone",
    "hooks": "run /kb-setup (`python3 _tools/kbgit.py install-hooks`) before any commit",
    "hooks-host": "make the directory core.hooksPath names, or unset it (`git config --unset core.hooksPath`)",
    "host-load": "dispatch fewer workers and give the tests a `-k` selection, which takes no host lock",
    "suite-load": "wait for the load to fall (another application or sibling workers hold the CPU) and run the "
                  "whole suite then; a `-k` selection takes no host lock and no ceiling",
    "both-load": "wait for the load to fall and run the whole suite then; dispatch fewer workers; a `-k` selection "
                 "takes no host lock",
    "host-lock": "wait for the holder or narrow the tests to a `-k` selection; end the holder only when it is yours "
                 "and stuck",
    "claims": "ask its worker, or release it (`backlog.py release ID`) and dispatch it again with the failure named in "
              "the brief; for mr-dead its work is pushed, so read its request first",
    "orphans": "end it if it is yours (`python3 _tools/backlog.py procs` lists each with its pid and checkout); "
               "nothing ends it for you",
    "main": "file the red pipeline as a bug (`backlog.py red-pipeline`) and take the next ready item",
    "main-unknown": "read it by hand: `python3 _tools/backlog.py red-pipeline --status` (needs the network)",
    "leftovers": "run `python3 _tools/backlog.py tidy --apply`, which removes the leftovers it lists as `would remove` "
                 "(never --force); free more space by hand if none is removable",
    "leftovers-unknown": "read them by hand: `python3 _tools/backlog.py tidy`",
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


def own_checkout(root):
    """Whether ROOT is the plugin's own checkout, the one that holds the kb's gate script `_tools/kbgit.py`; any other
    root is a host project, which the plugin serves and whose checks only its own inputs decide."""
    return (Path(root) / "_tools" / "kbgit.py").is_file()


def host_commands(root):
    """The commands a host project at ROOT needs allowed: the sprint loop's, those its backlog.json names in
    `LAND_SETTINGS` (a first element ending in `.py` runs under python3; the `land_stale` step takes the integration
    main as its last argument) and its forge's, only when the file sets `forge`."""
    import bl_base
    values, sources, _, _ = bl_base.read_settings(root)
    commands = list(LOOP_COMMANDS)
    for key in LAND_SETTINGS:
        argv = list(values[key])
        if argv:
            if argv[0].endswith(".py"):
                argv.insert(0, "python3")
            if key == "land_stale":
                argv.append("origin/main")
            commands.append(" ".join(argv))
    if sources["forge"] == "file":
        commands += FORGE_COMMANDS.get(values["forge"], ())
    return list(dict.fromkeys(commands))


SKILL_TEXT_GLOBS = ("skills/*/SKILL.md", "agents/worker.md")  # the text the sprint, item and backlog skills and the worker hold
SKILL_TEXT_SCRIPT = re.compile(r"python3 (?:\$\{CLAUDE_PLUGIN_ROOT\}/)?(_tools/[a-z0-9_]+\.py)")


def skill_text_scripts(root):
    """The `_tools` scripts the skills' text under ROOT runs as `python3 SCRIPT` (with or without the plugin
    variable, which a clone without the plugin never substitutes), each once and in text order."""
    scripts = {}
    for pattern in SKILL_TEXT_GLOBS:
        for path in sorted(Path(root).glob(pattern)):
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            scripts.update(dict.fromkeys(SKILL_TEXT_SCRIPT.findall(text)))
    return list(scripts)


def script_allowed(script, commands, rules):
    """Whether some allow rule lets `python3 SCRIPT` run: it covers the bare command, or covers a command of COMMANDS
    that runs the script (a rule listing one subcommand is the operator's choice, the script is then allowed)."""
    head = f"python3 {script}"
    return any(rule_covers(r, head) for r in rules) or any(
        c.startswith(head + " ") and any(rule_covers(r, c) for r in rules) for c in commands)


def check_allow(root, commands=None, tools=SKILL_TOOLS):
    host = not own_checkout(root)
    if commands is None:
        commands = host_commands(root) if host else SKILL_COMMANDS
    rules, why = read_allow(root)
    if rules is None:
        return result("allow-rules", "unknown" if host else "fail", why, REMEDY["allow-rules"])
    commands = list(commands)
    missing = [c for c in commands if not any(rule_covers(r, c) for r in rules)]
    text_scripts = [s for s in skill_text_scripts(root) if not script_allowed(s, commands, rules)]
    missing += [f"python3 {s} (skill text)" for s in text_scripts]
    commands += [f"python3 {s}" for s in text_scripts]
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


def check_checkout(root):
    other = linked_worktree_of(root)
    if other is None:
        return result("checkout", "ok", "the clone is not a linked worktree")
    try:
        own = sorted(worker_dirs(root))
        main = main_worker_dir(root)
    except Refused as e:
        return result("checkout", "unknown", f"the worker directories `land` expects cannot be read: {e}")
    if main is None:
        return result("checkout", "fail", f"this clone is a linked worktree of the checkout {other}, whose "
                      f"{'/'.join(worker_dir())} `land` does not accept a worker under", REMEDY["checkout"])
    return result("checkout", "ok", f"the clone is a linked worktree of {other}: `land` of one item's branch "
                  f"accepts a worker's worktree under {main} or {' or '.join(str(d) for d in own)}")


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


def host_hooks_problem(root):
    """(skipped, problem) of a host project's `core.hooksPath`: skipped when it is unset, else the problem is None when
    the path exists and a line naming it when it does not."""
    p = subprocess.run(["git", "config", "--get", "core.hooksPath"], cwd=root, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    cur = p.stdout.strip()
    if not cur:
        return True, None
    return False, None if (Path(root) / cur).is_dir() else f"core.hooksPath {cur} does not exist"


def check_hooks(root):
    if not own_checkout(root):
        skipped, problem = host_hooks_problem(root)
        if skipped:
            return result("hooks", "ok", "skipped: core.hooksPath is not set in this project")
        if problem:
            return result("hooks", "fail", problem, REMEDY["hooks-host"])
        return result("hooks", "ok", "core.hooksPath exists")
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


def suite_load_problem(load=None, cores=None):
    """The line that names this host when its 5-minute load average is over SUITE_LOAD_PER_CORE times the cores, the
    load above which a whole-suite tests.py run no longer fits its seconds ceiling; None at or under it, and with no
    load average to read. LOAD and CORES stand in for the host's own (a test plants them); `done` of a review story
    reads this too, before it starts the whole-suite run."""
    try:
        load = os.getloadavg()[1] if load is None else load
    except (OSError, AttributeError):
        return None
    cores = cores or os.cpu_count() or 1
    if load > SUITE_LOAD_PER_CORE * cores:
        return (f"host {platform.node() or 'this host'} is too loaded for a whole-suite tests.py run to fit its "
                f"seconds ceiling: load {load:.1f} over {SUITE_LOAD_PER_CORE:g} per core of {cores}")
    return None


def check_host(now=None, load=None, cores=None):
    now = time.time() if now is None else now
    try:
        load = os.getloadavg()[1] if load is None else load
    except (OSError, AttributeError):
        load = None
    cores = cores or os.cpu_count() or 1
    problems, remedy = [], []
    suite = None if load is None else suite_load_problem(load, cores)
    busy = load is not None and load > LOAD_PER_CORE * cores
    if suite and busy:  # over both limits: one short problem and one remedy, so the line stays within LINE_MAX
        problems.append(f"load {load:.1f} over {SUITE_LOAD_PER_CORE:g} (a whole-suite run) and {LOAD_PER_CORE:g} "
                        f"(more workers) per core of {cores}")
        remedy.append(REMEDY["both-load"])
    elif suite:
        problems.append(suite)
        remedy.append(REMEDY["suite-load"])
    elif busy:
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
    """The eight results, in the order above. One `bl_stall.collect` serves the claims and main."""
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
    out.append(check_leftovers(bl))
    return out


# ---------------------------------------------------------------- the leftovers

def leftovers(bl, seconds=BYTES_BUDGET_S):
    """What `backlog.py tidy` lists, as one dict, read without a change: `rows` (tidy's rows, `bl_clean.safe_to_remove`'s
    verdict, reason and the bytes a removal frees; `approximate` where a walk was cut), `counts` ({class: {"remove": n,
    "keep": n}}), `removable` (the `remove` rows), `bytes` (what they free, a nested path counted once), `approximate`,
    `free_gib` of the clone's volume, `limit_gib` (tidy's disk-pressure limit) and `pressure`. The bytes of all the
    `remove` rows are walked for SECONDS together, a row past it keeps 0 bytes and is `approximate`. Raises
    `bl_base.Rejected` where there is no integration main or the coord store cannot be read, `bl_clean.CoordLocked`."""
    import bl_clean
    snap = bl_clean.take_snapshot(bl)
    state = bl_clean.coord_state()
    cands = bl_clean.candidates(snap, state)
    deadline = time.monotonic() + seconds
    rows = []
    for cls in bl_clean.TIDY_CLASSES:
        for cand in cands[cls]:
            verdict, reason = bl_clean.safe_to_remove(cand, snap, state)
            row = bl_clean.row_of(cand, verdict, reason)
            if verdict == bl_clean.REMOVE and cls == "worktree":
                snap["planned"].add(cand["path"])
            if verdict == bl_clean.REMOVE and cls != "branch" and os.path.isdir(cand["path"]):
                left = deadline - time.monotonic()
                row["bytes"], approx = bl_clean.tree_bytes(cand["path"], min(bl_clean.BYTES_SECONDS, max(left, 0)))
                if approx:
                    row["approximate"] = True
            if cls == "sandbox" and "disk pressure" in reason:
                row["_pressure"] = True
            rows.append(row)
    rows.sort(key=lambda r: 0 if r.get("_pressure") else 1)
    gone = [r for r in rows if r["verdict"] == bl_clean.REMOVE]
    paths = [r["path"] for r in gone if "path" in r]
    size = sum(r["bytes"] for r in gone if not any(o != r.get("path") and bl_clean.inside(o, r.get("path", "")) for o in paths))
    counts = {cls: {v: sum(1 for r in rows if r["class"] == cls and r["verdict"] == v)
                    for v in (bl_clean.REMOVE, bl_clean.KEEP)} for cls in bl_clean.TIDY_CLASSES}
    free = bl_clean.free_gib(snap, bl.root)
    return {"rows": [bl_clean.public(r) for r in rows], "counts": counts, "removable": len(gone), "bytes": size,
            "approximate": any(r.get("approximate") for r in gone),
            "free_gib": None if free == float("inf") else round(free, 1), "limit_gib": snap["free_gb"],
            "pressure": free < snap["free_gb"]}


def check_leftovers(bl):
    try:
        found = leftovers(bl)
    except Exception as e:  # noqa: BLE001 - a read that fails is unknown, never an error of the check
        return result("leftovers", "unknown", f"the leftovers could not be read ({type(e).__name__})",
                      REMEDY["leftovers-unknown"])
    import bl_clean
    size = f"{bl_clean.fmt_size(found['bytes'])}{' or more' if found['approximate'] else ''}"
    total = sum(sum(v.values()) for v in found["counts"].values())
    detail = f"{found['removable']} removable ({size}) of {total} leftovers"
    if found["pressure"]:
        return result("leftovers", "fail", f"{detail}; {found['free_gib']:g} GiB free, under tidy's "
                      f"{found['limit_gib']:g} GiB disk-pressure limit", REMEDY["leftovers"])
    return result("leftovers", "ok", detail)


# ---------------------------------------------------------------- the output

def line_of(r, cap=True):
    text = f"{r['state'].upper()} {r['name']}: {r['detail']}" + (f" -> {r['remedy']}" if r["remedy"] else "")
    return text if not cap or len(text) <= LINE_MAX else text[:LINE_MAX - 6] + " [cut]"


def render(results, full=False):
    """The lines of the output: one when nothing failed and nothing is unknown, else the header and a line for each
    check not ok, whole lines dropped from the end past MAX_CHARS (named in the last line) unless FULL."""
    bad = [r for r in results if r["state"] != "ok"]
    failed = sum(r["state"] == "fail" for r in bad)
    skipped = [f"{r['name']} {r['detail']}" for r in results if r["detail"].startswith("skipped")]
    if not bad:
        return [f"selfcheck: ok ({len(results)} checks passed" + "".join(f"; {x}" for x in skipped) + ")"]
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
