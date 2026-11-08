"""The benchmarks' session-load scenario: what one Claude Code session of this clone costs the host, measured with no
model, or with `--paid` with real Haiku 5.5 sessions (stdlib only).

benchmarks.py registers the scenario in SCENARIOS and holds the command line; the harness is bench_core.py
(kb/_self/code.md, Layout and Imports; the scenario is described in kb/_self/reports/benchmarks.md). It replays the hook
events of one session through the hook commands of the throwaway clone's own .claude/settings.json, started as Claude
Code starts them (`sh -c`, the event as JSON on stdin, CLAUDE_PROJECT_DIR set), and measures every process it starts with
`os.wait4` (CPU and peak memory, which include the children the process waited for) and, for the processes those start,
with a sampler of `ps` (their memory) and a `sitecustomize` audit hook that logs each process a Python program starts
(their number and programs). Arm B adds the commands the kbmon-pane mod runs in an interactive session, on the mod's schedule.
With `--paid` (paid_rows) it starts, per arm, phase, session count and rep, `claude -p` sessions instead, in the same
throwaway clones with the arm's settings, and samples their process trees into the same rows with the model column set.
This module imports no facade; `mon_host` is imported where a process is given its class.
"""
import json, os, re, shutil, signal, sqlite3, statistics, subprocess, sys, tempfile, threading, time, uuid
from pathlib import Path

from bench_core import (HOME, PRICE, RAW, RESULTS, Bench, Skip, git, need_sh, no_plugin_env, read_rows, shim_dir, spent, spent_usd,
                        write_rate)
from kbcommon import NO_HOOKS

ARMS = ("A", "B", "C", "D", "worker")  # A: every hook; B: A and the kbmon pane's commands; C: coord_hook.py and querylog.py left out; D: none; worker: A under a dispatched worker's environment
DEFAULT_ARMS = ("A", "C", "D")  # B and worker run only when named: B adds WINDOW_S seconds to each phase
PHASES = ("idle", "working")  # idle: SessionStart then SessionEnd; working: a fixed script of events between them
LEFT_OUT = {"A": (), "B": (), "C": ("coord_hook.py", "querylog.py"), "D": None, "worker": ()}  # a hook command naming one of these is not run
NOMINAL_S = {"idle": 60, "working": 300}  # the seconds of session a replay stands for: the divisor of spawns_per_min
CLASSES = ("kbmon", "fseventsd", "tests", "kb-tools", "claude", "other", "git", "lsof")  # mon_host's, then two more
CHILD_CLASSES = ("git", "lsof")  # classes whose processes only hook (or pane) commands start, so wait4 charges them to the parent
PANE_ARMS = ("B",)  # the arms that run the kbmon pane's commands
WORKER_ARMS = ("worker",)  # the arms whose hooks run in the environment bl_dispatch.worker_env gives a worker
SESSION_LEASE = "session/"  # coord.py's key prefix of a session's presence lease
WORKER_KEYS = ("KB_OPERATOR", "KB_ROLE", "KB_UNWATCHED")  # what that environment sets on top of the host's own
PANE_MOD = ".claude/skills/kbmon-pane/hooks/register.tsx"  # the mod whose FIRST_MS and REFRESH_MS the pane commands follow
PANE_COMMANDS = (("--once",), ("--status", "all"))  # what the mod's refresh runs, in order, as `python3 _tools/kbmon.py ...`
PANE_COLUMNS = "80"  # the mod's DEFAULT_COLUMNS: COLUMNS of a pane run
WINDOW_S = 150  # seconds of a phase of arm B: the pane's first run at FIRST_MS and then one every REFRESH_MS, so three runs
CAPTURE_CLASSES = ("kb-tools", "git", "lsof", "claude", "fseventsd", "other")  # the classes of an fs_usage capture, by process name
FS_COMMAND = "sudo fs_usage -w -f filesys > fs_usage.txt"  # what the operator runs by hand; no check or run of the tool calls sudo
READ_CALLS = ("read", "readv", "pread", "preadv", "RdData")  # descriptor reads and physical reads
DESCRIPTOR_CALLS = ("read", "readv", "pread", "preadv")  # the descriptor reads among them; RdData is the disk read
OPEN_CALLS = ("open", "open_extended", "open_dprotected_np", "openat")  # a read when the mode string starts with R
FS_LINE = re.compile(r"^\s*\d\d:\d\d:\d\d(?:\.\d+)?\s+(\S+)\s*(.*?)\s+\d+\.\d+(?:\s+W)?\s+(\S.*?)\.\d+\s*$")  # call, fields and path, process
INTAKE_REAL_CASE = "idle hook intake real"  # the case of `run session-load --intake-real`: the intake hook in an unpinned clone
SAMPLE_S = 0.02  # the sampler's pause between two `ps` listings (N sessions at once: N times it, so `ps` runs as often in all)
GATE_WAIT_S = 600  # seconds the replays of N sessions wait for each other before they start together
LOAD_SAMPLE_S = 0.5  # the pause between two reads of the host's 1-minute load while sessions run at once
LIVE_ARM = "live"  # the arm of the rows of `run session-load --live`
LIVE_TICK_S = 1.0  # the pause between two `ps` listings of a live run
LIVE_HEADLESS_ROLES = ("worker", "sprint runner", "reviewer", "benchmark agent", "bare twin", "observer")  # the roles of mon_sessions.ROLES that run headless: the others are interactive
LIVE_ITEM_ID = re.compile(r"[A-Z]{2}-[a-z2-7]{8}")  # a backlog item id, as kbtail keeps one
SETTLE_S = 30  # seconds a replay waits for the processes it left running in the clone
PAID_ARMS = ("A", "C", "D", "worker")  # the arms of `run session-load --paid`: B needs an interactive session; worker runs A's settings in a worker's environment
PAID_MODEL = "claude-haiku-5-5"  # the model of every paid session, pinned by id
PAID_RUN_USD = 0.50  # the --max-budget-usd of one paid session
PAID_TIMEOUT_S = 600  # seconds one paid session may run before its process group is killed
PAID_TICK_S = 0.2  # the pause between two `ps` listings while paid sessions run
PAID_TOOLS = "Read,Bash(git status:*),Bash(python3 _tools/rag.py:*)"  # what a paid session may call, so a working phase needs no prompt
PAID_PROMPTS = {  # the prompt of a paid session per phase: idle calls no tool, working calls three (the hooks of PreToolUse, PostToolUse and Stop run)
    "idle": "Reply with the single word ready and call no tool.",
    "working": "Run `git status --short`, then run `python3 _tools/rag.py search LAPS -k 1`, then read the first 20 lines of README.md "
               "with the Read tool, then answer in one sentence what this repository is."}
PAID_TOKENS = {  # the tokens of one paid session per phase an estimate assumes when the results hold no paid record: a session's cached start is mostly written once (1-hour rate)
    "idle": {"uncached": 2_000, "cache_write": 25_000, "cache_read": 0, "out": 200},
    "working": {"uncached": 6_000, "cache_write": 35_000, "cache_read": 120_000, "out": 800}}
SITE = '''# logs each process a Python program starts (the audit events of subprocess.Popen, os.posix_spawn and os.system) to the
# file BENCH_STARTS_LOG, then runs the sitecustomize this file shadows
import os, sys
_log = os.environ.get("BENCH_STARTS_LOG")


def _audit(event, args):
    if event in ("subprocess.Popen", "os.posix_spawn"):
        argv = args[1]
    elif event == "os.system":
        argv = ["sh", "-c", args[0]]
    else:
        return
    try:
        with open(_log, "a", encoding="utf-8") as f:
            f.write("\\x1f".join(str(a) for a in ([argv] if isinstance(argv, (str, bytes)) else argv)) + "\\x1e")
    except OSError:
        pass


if _log:
    sys.addaudithook(_audit)
_here = os.path.dirname(os.path.abspath(__file__))
for _d in sys.path:
    _f = os.path.join(_d or ".", "sitecustomize.py")
    if os.path.isfile(_f) and os.path.dirname(os.path.abspath(_f)) != _here:
        exec(compile(open(_f, encoding="utf-8").read(), _f, "exec"), {"__name__": "sitecustomize", "__file__": _f})
        break
'''

WORKING = [  # the script of a working phase: (prompt, [(tool, tool_input, tool_response)], last answer)
    ("kb: default Windows LAPS password length",
     [("mcp__plugin_it-ops-kb_kb__kb_pack", {"question": "LAPS password length"},
       [{"type": "text", "text": "coverage: good\n## public/windows/laps.md"}]),
      ("Bash", {"command": "python3 _tools/rag.py show public/windows/laps.md:1"}, {"stdout": "line"}),
      ("Bash", {"command": "python3 _tools/backlog.py release ST-aaaaaaaa"}, {"stdout": ""})],  # a work row, whatever the branch
     "The default is 14 characters."),
    ("How do I rename a branch?",
     [("Edit", {"file_path": "NOTES.md", "old_string": "a", "new_string": "b"}, {"ok": True}),
      ("Bash", {"command": "git branch -m new-name"}, {"stdout": ""})],
     "Use git branch -m."),
    ("kb: Intune remediation script limits",
     [("WebFetch", {"url": "https://learn.microsoft.com/mem/intune/", "prompt": "limits"}, {"result": "text"}),
      ("Skill", {"skill": "kb-lookup"}, {"ok": True})],
     "The limits are on the page."),
]


def hook_commands(clone):
    """[(event, matcher, async, command)] of the clone's .claude/settings.json in file order; a PowerShell command is left out."""
    spec = json.loads((Path(clone) / ".claude" / "settings.json").read_text(encoding="utf-8"))
    return [(ev, g.get("matcher") or "", bool(h.get("async")), h["command"])
            for ev, groups in spec.get("hooks", {}).items() for g in groups for h in g["hooks"]
            if h.get("type", "command") == "command" and "PSModuleAutoLoadingPreference" not in h["command"]]


def arm_hooks(hooks, arm):
    """The hook commands arm `arm` runs."""
    out = LEFT_OUT[arm]
    return [] if out is None else [h for h in hooks if not any(x in h[3] for x in out)]


def events(phase, clone, sid):
    """The session's events as (name, matcher target, payload): SessionStart, for a working phase the prompts, tool calls
    and stops of WORKING, and SessionEnd."""
    base = {"session_id": sid, "cwd": str(clone), "transcript_path": str(Path(clone) / "_cache" / "transcript.jsonl")}
    out = [("SessionStart", "startup", {**base, "hook_event_name": "SessionStart", "source": "startup"})]
    for i, (prompt, tools, answer) in enumerate(WORKING if phase == "working" else []):
        pid = f"p{i}"
        out.append(("UserPromptSubmit", "", {**base, "hook_event_name": "UserPromptSubmit", "prompt_id": pid, "prompt": prompt}))
        for name, tin, tout in tools:
            out.append(("PreToolUse", name, {**base, "hook_event_name": "PreToolUse", "prompt_id": pid, "tool_name": name,
                                             "tool_input": tin}))
            out.append(("PostToolUse", name, {**base, "hook_event_name": "PostToolUse", "prompt_id": pid, "tool_name": name,
                                              "tool_input": tin, "tool_response": tout}))
        out.append(("Stop", "", {**base, "hook_event_name": "Stop", "prompt_id": pid, "last_assistant_message": answer}))
    out.append(("SessionEnd", "other", {**base, "hook_event_name": "SessionEnd", "reason": "other"}))
    return out


def matches(matcher, target):
    """Whether a hook group's matcher selects the event's target (a tool name, a start source, an end reason)."""
    return not matcher or re.fullmatch(matcher, target) is not None


def label(command):
    """The hook command without its launcher: the script and its arguments."""
    return re.sub(r'^sh "\$\{CLAUDE_PROJECT_DIR\}/_tools/kbpy"\s*(?:--person\s+)?', "", command)


def maxrss_mb(ru):
    """ru_maxrss in MiB: bytes on macOS, KiB on Linux (kb/public/python/rusage-maxrss-units.md)."""
    return ru.ru_maxrss / (1048576 if sys.platform == "darwin" else 1024)


def pane_schedule(clone):
    """(first_s, refresh_s) of the kbmon-pane mod in `clone`: its FIRST_MS and REFRESH_MS in seconds."""
    text = (Path(clone) / PANE_MOD).read_text(encoding="utf-8")
    got = {k: re.search(rf"^const {k} = ([\d_]+)$", text, re.M) for k in ("FIRST_MS", "REFRESH_MS")}
    if not all(got.values()):
        raise RuntimeError(f"{PANE_MOD}: no FIRST_MS and REFRESH_MS constant to take the pane's schedule from")
    return tuple(int(got[k].group(1).replace("_", "")) / 1000 for k in ("FIRST_MS", "REFRESH_MS"))


def process_class(args, clone):
    """The host panel's class of a command line (mon_host.kind_of), with `git` and `lsof` for those programs."""
    import mon_host
    words = args.split()
    first = os.path.basename(words[0]) if words else ""
    return first if first in ("git", "lsof") else mon_host.kind_of(args, str(clone))[0]


def listing():
    """[(pid, ppid, rss_kb, args)] of one `ps -A` listing."""
    p = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,rss=,args="], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    out = []
    for ln in p.stdout.splitlines():
        w = ln.split(None, 3)
        if len(w) >= 3 and all(x.isdigit() for x in w[:3]):
            out.append((int(w[0]), int(w[1]), int(w[2]), w[3] if len(w) > 3 else ""))
    return out


class Sampler(threading.Thread):
    """Lists the processes every SAMPLE_S and follows the descendants of the root processes registered with `add` (until
    `finish`): per tick the memory of each class's live processes, per descendant its class and peak memory. A process
    that lives less than a listing is not seen, so the starts are not counted from here (the sitecustomize counts them);
    its CPU is in the root's `os.wait4` figure."""

    def __init__(self, clone, pause=SAMPLE_S):
        super().__init__(daemon=True)
        self.clone, self.roots, self.stop, self.lock = str(clone), {}, threading.Event(), threading.Lock()
        self.pause = pause
        self.ticks, self.seen = [], {}  # per tick {class: rss kb}; descendant pid -> [class, peak rss kb]

    def add(self, pid, cls):
        with self.lock:
            self.roots[pid] = cls

    def finish(self, pid):
        with self.lock:
            self.roots.pop(pid, None)

    def run(self):
        while not self.stop.is_set():
            with self.lock:
                roots = dict(self.roots)
            if roots:
                self.tick(roots)
            self.stop.wait(self.pause)

    def tick(self, roots):
        rows = {pid: (ppid, rss, args) for pid, ppid, rss, args in listing()}
        kids = {}
        for pid, (ppid, _, _) in rows.items():
            kids.setdefault(ppid, []).append(pid)
        per, todo = {}, [p for p in roots if p in rows]
        for p in todo:
            per[roots[p]] = per.get(roots[p], 0) + rows[p][1]
        while todo:
            for c in kids.get(todo.pop(), []):
                cls = process_class(rows[c][2], self.clone)
                per[cls] = per.get(cls, 0) + rows[c][1]
                cell = self.seen.setdefault(c, [cls, 0])
                cell[1] = max(cell[1], rows[c][1])
                todo.append(c)
        if per:
            self.ticks.append(per)


def settle(clone):
    """Wait, at most SETTLE_S, until no process names the clone's path in its command line (a detached distill ends); a
    path that goes on with a name character is another clone's (`session-load` and `session-load-1`)."""
    end = time.monotonic() + SETTLE_S
    named = re.compile(re.escape(str(clone)) + r"(?![\w.-])")
    while time.monotonic() < end:
        if not [1 for pid, _, _, args in listing() if pid != os.getpid() and named.search(args)]:
            return
        time.sleep(0.2)


def pin_drift(clone):
    """Make no item of the clone eligible for the intake hook's drift scan, so that hook does the same work in every replay.
    The hook stops waiting for its detectors after INTAKE_HOOK_BUDGET_S, and its drift scan runs the checks of the draft or
    todo items whose touches changed since their file did, within a wall-clock budget of its own: the checks that fit, and so
    the processes started, move with the host's speed and load. One commit on the clone that changes the mode of each item file
    (no content) makes the newest commit of every item file the clone's HEAD, so no item is eligible and the scan only
    reads the items; what the real hook costs in a clone where checks do run is `intake_real_rows`'s."""
    item_dir = json.loads((Path(clone) / "backlog.json").read_text(encoding="utf-8"))["item_dir"]
    files = git("ls-files", "--", item_dir, cwd=clone).splitlines()
    git("update-index", "--chmod=+x", "--", *files, cwd=clone)
    git("-c", "user.name=bench", "-c", "user.email=bench@example.com", "commit", "-q", "--no-verify", "-m",
        "bench: the item files' mode", cwd=clone)


def intake_hooks(hooks):
    """The SessionStart commands of the intake hook (`backlog.py intake`) among the clone's hook commands."""
    return [h for h in hooks if h[0] == "SessionStart" and "backlog.py intake" in h[3]]


def reset(clone):
    """The clone's working tree as the checkout left it, whatever a replay's hooks wrote, and the intake hook's drift
    cursor removed, so each replay's drift scan starts at the same item instead of where the replay before it stopped."""
    git("checkout", "-q", "--", ".", cwd=clone)
    git("clean", "-fdq", cwd=clone)
    (Path(clone) / git("rev-parse", "--git-path", "kb-intake-drift", cwd=clone)).unlink(missing_ok=True)


class Replay:
    """One replay of a session's events in `clone`: the hook processes it started and the sampler's view of their children."""

    def __init__(self, clone, env, hooks, pane=None, pause=SAMPLE_S):
        self.clone, self.env, self.hooks, self.pause = Path(clone), env, hooks, pause
        self.pane = pane  # None, or (first_s, every_s, window_s): the kbmon pane's schedule
        self.roots, self.threads = [], []  # one dict per hook command run
        self.panes = []  # one dict per pane command run (a pane run is each of PANE_COMMANDS once)
        self.pane_runs = 0
        self.lease = 0  # lease_written, read just before the SessionEnd event

    def start(self, name, target, payload, command, is_async, sampler):
        cmd = command.replace("${CLAUDE_PROJECT_DIR}", str(self.clone))
        rec = {"event": name, "tool": target if name.endswith("ToolUse") else "", "label": label(command), "async": is_async,
               "class": process_class("sh " + cmd, self.clone)}
        rec["log"] = Path(self.env["BENCH_STARTS_DIR"]) / f"{len(self.roots)}.log"  # the processes this command's tree starts
        t0 = time.perf_counter()
        p = subprocess.Popen(["sh", "-c", command], cwd=str(self.clone), env={**self.env, "BENCH_STARTS_LOG": str(rec["log"])},
                             stdin=subprocess.PIPE,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        sampler.add(p.pid, rec["class"])
        try:
            p.stdin.write(json.dumps(payload).encode("utf-8"))
            p.stdin.close()
        except OSError:  # a hook that exits without reading its input
            pass
        self.roots.append(rec)
        if not is_async:
            self.reap(p, rec, t0, sampler)
            return
        th = threading.Thread(target=self.reap, args=(p, rec, t0, sampler))
        th.start()
        self.threads.append(th)

    def pane_command(self, flags, sampler):
        """One run of `python3 _tools/kbmon.py FLAGS` as the mod starts it (an argument list, COLUMNS set, in the clone)."""
        argv = ["python3", "_tools/kbmon.py", *flags]
        rec = {"label": " ".join(argv[1:]), "class": process_class(" ".join(argv), self.clone)}
        rec["log"] = Path(self.env["BENCH_STARTS_DIR"]) / f"pane{len(self.panes)}.log"
        t0 = time.perf_counter()
        p = subprocess.Popen(argv, cwd=str(self.clone), env={**self.env, "COLUMNS": PANE_COLUMNS, "BENCH_STARTS_LOG": str(rec["log"])},
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        sampler.add(p.pid, rec["class"])
        self.panes.append(rec)
        self.reap(p, rec, t0, sampler)

    def run_pane(self, sampler, t0):
        """The mod's schedule: a refresh at `first_s` of the window and then at every multiple of `every_s`; a tick that
        falls while a refresh runs does nothing (the mod never starts a second one), so the next is the first multiple
        after the refresh ended. A refresh that starts before the window ends is waited for."""
        first_s, every_s, window_s = self.pane
        due = first_s
        while due < window_s:
            time.sleep(max(0.0, t0 + due - time.perf_counter()))
            for flags in PANE_COMMANDS:
                self.pane_command(flags, sampler)
            self.pane_runs += 1
            due = (int((time.perf_counter() - t0) // every_s) + 1) * every_s

    @staticmethod
    def reap(p, rec, t0, sampler):
        _, status, ru = os.wait4(p.pid, 0)
        rec["wall_s"] = time.perf_counter() - t0
        p.returncode = os.waitstatus_to_exitcode(status)
        rec.update(rc=p.returncode, cpu_s=ru.ru_utime + ru.ru_stime, maxrss_mb=maxrss_mb(ru))
        sampler.finish(p.pid)

    def run(self, phase, sid):
        sampler = Sampler(self.clone, self.pause)
        if self.hooks:
            sampler.start()
        t0 = time.perf_counter()
        if self.pane:
            pane = threading.Thread(target=self.run_pane, args=(sampler, t0))
            pane.start()
            self.threads.append(pane)
        for name, target, payload in events(phase, self.clone, sid):
            if name == "SessionEnd":  # the end hook releases the lease, which leaves nothing to read after it
                self.lease = lease_written(self.env["KB_COORD_STORE"], sid)
            for ev, matcher, is_async, command in self.hooks:
                if ev == name and matches(matcher, target):
                    self.start(name, target, payload, command, is_async, sampler)
        for th in self.threads:
            th.join()
        if self.pane:  # the window is the phase's length, whether or not the hooks and the pane used it
            time.sleep(max(0.0, t0 + self.pane[2] - time.perf_counter()))
        wall = time.perf_counter() - t0
        sampler.stop.set()
        if self.hooks:
            sampler.join()
        settle(self.clone)
        return {**self.summary(sampler, wall), "lease_written": self.lease}

    def started(self, rec):
        """The command line of each process a Python program of one hook command's tree started (the sitecustomize's log)."""
        text = rec["log"].read_text(encoding="utf-8", errors="replace") if rec["log"].exists() else ""
        return [" ".join(r.split("\x1f")) for r in text.split("\x1e") if r]

    def summary(self, sampler, wall):
        """{class: {cpu_s, spawns, pane_spawns, peak, rss_mean_mb}} with `all`, the hook commands' timings and the failed
        ones. A command is one start and the processes the Python programs of the tree started the rest (a pane command's
        are `pane_spawns`, since the pane's rate is per window and a hook's per session); the peak memory is the largest of
        the processes' own peaks and of the sampled sums, the mean the mean over every sampler tick of the phase, a tick with
        no process of the class counting as 0, so no class's mean exceeds that of `all`."""
        per = {}

        def cell(c):
            return per.setdefault(c, {"cpu_s": 0.0, "spawns": 0, "pane_spawns": 0, "peak": 0.0, "mean": 0.0})
        for r in self.roots + self.panes:
            c = cell(r["class"])
            c["cpu_s"] += r["cpu_s"]
            c["pane_spawns" if r in self.panes else "spawns"] += 1
            c["peak"] = max(c["peak"], r["maxrss_mb"])
        for r in self.roots + self.panes:
            r["children"] = self.started(r)
            for args in r["children"]:
                cell(process_class(args, self.clone))["pane_spawns" if r in self.panes else "spawns"] += 1
        for cls, kb in sampler.seen.values():
            cell(cls)["peak"] = max(cell(cls)["peak"], kb / 1024)
        for tick in sampler.ticks:
            for cls, kb in tick.items():
                cell(cls)["mean"] += kb / 1024 / len(sampler.ticks)
                cell(cls)["peak"] = max(cell(cls)["peak"], kb / 1024)
        procs = self.roots + self.panes
        per["all"] = {"cpu_s": sum(c["cpu_s"] for c in per.values()), "spawns": sum(c["spawns"] for c in per.values()),
                      "pane_spawns": sum(c["pane_spawns"] for c in per.values()),
                      "peak": max([r["maxrss_mb"] for r in procs] + [sum(t.values()) / 1024 for t in sampler.ticks] + [0.0]),
                      "mean": sum(sum(t.values()) / 1024 for t in sampler.ticks) / max(len(sampler.ticks), 1)}
        for c in per.values():
            # no tick at all: the processes' own peaks stand for their size
            c["rss_mean_mb"] = c["mean"] if sampler.ticks else c["peak"]
        return {"classes": per, "wall_s": wall, "hooks": self.roots, "pane_runs": self.pane_runs,
                "failed": [r for r in self.roots if r.get("rc") not in (0, None)],
                "pane_failed": [r for r in self.panes if r.get("rc") not in (0, 1)]}  # kbmon exits 1 while an alert is on


FORGE_SHIM = """#!/bin/sh
# a `glab` that answers the reads of the red-pipeline hook from canned JSON, no network: one finished pipeline of main
# with one job that ran and succeeded (a green main); every other call fails, as a `glab` not signed in does
case "$*" in
*"/pipelines?"*) printf '%s\\n' '{pipelines}' ;;
*"/pipelines/{pid}/jobs?"*) printf '%s\\n' '{jobs}' ;;
*) exit 1 ;;
esac
"""
FORGE_PIPELINE = {"id": 1, "sha": "0" * 40, "status": "success", "web_url": "https://gitlab.com/it-ops-kb-bench/session-load/-/pipelines/1"}
FORGE_JOB = {"id": 11, "name": "bench-job", "status": "success", "started_at": "2026-01-01T00:00:00.000Z"}


def forge_shim(where):
    """A directory holding a `glab` that answers the pipeline reads of the red-pipeline hook with a planted green pipeline
    of main and a `gh` that fails at once, so a replay's hooks read no forge: no request leaves the host and the hook's
    sync_ms and starts do not move with the network or the operator's sign-in. The hook still parses the answer as it
    does a real one; what it costs with a real pipeline's size and red logs is not measured here."""
    d = Path(where)
    d.mkdir(parents=True, exist_ok=True)
    body = FORGE_SHIM.format(pipelines=json.dumps([FORGE_PIPELINE]), jobs=json.dumps([FORGE_JOB]), pid=FORGE_PIPELINE["id"])
    for name, text in (("glab", body), ("gh", "#!/bin/sh\nexit 1\n")):
        (d / name).write_text(text, encoding="utf-8", newline="\n")
        (d / name).chmod(0o755)
    return d


def plant(b, clone, name):
    """The scratch directories of one replay: a query log home with mode `local`, a coord store of its own, a `claude`
    that fails at once, a `glab` that answers from a planted pipeline (forge_shim) and the sitecustomize that logs the
    processes Python starts; the environment the hooks run in (CLAUDE_PLUGIN_DATA and CLAUDE_PLUGIN_ROOT both set, else
    the capture hook writes the real spool)."""
    data = b.scratch / "session-load-data" / name
    shutil.rmtree(data, ignore_errors=True)
    (data / "querylog").mkdir(parents=True)
    (data / "starts").mkdir()
    (data / "querylog" / "config.json").write_text(json.dumps({"mode": "local", "research": False}) + "\n", encoding="utf-8",
                                                   newline="\n")
    site = b.scratch / "session-load-site"
    site.mkdir(parents=True, exist_ok=True)
    (site / "sitecustomize.py").write_text(SITE, encoding="utf-8", newline="\n")
    fail = shim_dir(b.scratch / "fail-shim")
    forge = forge_shim(b.scratch / "forge-shim")
    path = os.pathsep.join(x for x in (str(site), os.environ.get("PYTHONPATH", "")) if x)
    return no_plugin_env({"CLAUDE_PLUGIN_ROOT": str(clone), "CLAUDE_PLUGIN_DATA": str(data), "CLAUDE_PROJECT_DIR": str(clone),
                          "KB_INDEX": str(clone / "_cache"), "KB_COORD_STORE": str(data / "coord.sqlite"),
                          "BENCH_STARTS_DIR": str(data / "starts"), "PYTHONPATH": path,
                          "PATH": os.pathsep.join((str(forge), str(fail), os.environ.get("PATH", "")))})


def arm_env(env, arm):
    """ENV for arm `arm`: KB_UNWATCHED is the worker arms' alone, whatever session runs the benchmark, and a worker arm
    holds the keys of WORKER_KEYS that bl_dispatch.worker_env gives a worker (a placeholder operator id)."""
    env = {k: v for k, v in env.items() if k != "KB_UNWATCHED"}
    if arm in WORKER_ARMS:
        import bl_dispatch
        env.update({k: v for k, v in bl_dispatch.worker_env("op-00000000").items() if k in WORKER_KEYS})
    return env


def work_rows(data):
    """The `work` rows the replay's hooks wrote to the spool under the query log home DATA / "querylog"."""
    n = 0
    for f in (Path(data) / "querylog").rglob("*.jsonl"):
        n += sum(1 for ln in f.read_text(encoding="utf-8", errors="replace").splitlines() if re.search(r'"surface":\s*"work"', ln))
    return n


def lease_written(store, sid):
    """1 when the replay's own coord store (`store`, read without writing) holds the presence lease `session/SID` of the
    session now, else 0. The hook takes the lease in its own process, so no `coord.py claim` shows in the processes the
    replay logged; and the SessionEnd hook releases it, which leaves no row or event, so Replay.run reads it just before
    that event."""
    try:
        con = sqlite3.connect(Path(store).resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    except sqlite3.Error:
        return 0
    try:
        return int(con.execute("SELECT 1 FROM entries WHERE key = ? AND holder IS NOT NULL AND expires > ?",
                               (SESSION_LEASE + sid, time.time())).fetchone() is not None)
    except sqlite3.Error:  # no store yet: a replay whose hooks never opened it
        return 0
    finally:
        con.close()


class LoadPeak(threading.Thread):
    """The highest 1-minute load of the host (os.getloadavg) read every LOAD_SAMPLE_S from `start` to `finish`, the reads at
    both ends included. The 1-minute load moves slowly, so a run of seconds shows mostly the load it began in."""

    def __init__(self):
        super().__init__(daemon=True)
        self.peak, self.done = 0.0, threading.Event()

    def read(self):
        if hasattr(os, "getloadavg"):
            self.peak = max(self.peak, os.getloadavg()[0])

    def run(self):
        self.read()
        while not self.done.wait(LOAD_SAMPLE_S):
            self.read()

    def finish(self):
        self.done.set()
        self.join()
        self.read()
        return self.peak


def replay(b, clone, hooks, arm, phase, name, pane=None, gate=None, pause=SAMPLE_S):
    """One replay of arm `arm`, `phase` in `clone`; with a `gate` (a threading.Barrier) it waits there, its working tree
    and environment ready, for the replays that run beside it."""
    reset(clone)
    env = arm_env(plant(b, clone, name), arm)
    load = os.getloadavg()[0] if hasattr(os, "getloadavg") else 0.0
    sid = str(uuid.uuid4())
    if gate:
        gate.wait(GATE_WAIT_S)
    out = Replay(clone, env, arm_hooks(hooks, arm), pane if arm in PANE_ARMS else None, pause).run(phase, sid)
    out["load"] = load
    out["work_rows"] = work_rows(env["CLAUDE_PLUGIN_DATA"])
    return out


def together(outs, peak):
    """The replays of N sessions that ran at once as the one result of their run together: per class and for `all` the sums
    of the CPU, the starts and the memory (the sum of the sessions' peaks, which are not at the same moment, so at most
    the host's peak, and of their means), the longest `wall_s`, the hook commands and failures of all of them, the sums of
    `pane_runs`, `lease_written` and `work_rows`, the mean of the loads at their start and `load_peak`."""
    per = {}
    for o in outs:
        for cls, cell in o["classes"].items():
            sums = per.setdefault(cls, {})
            for k, v in cell.items():
                sums[k] = sums.get(k, 0.0) + v
    return {"classes": per, "wall_s": max(o["wall_s"] for o in outs), "hooks": [h for o in outs for h in o["hooks"]],
            "pane_runs": sum(o["pane_runs"] for o in outs), "failed": [h for o in outs for h in o["failed"]],
            "pane_failed": [h for o in outs for h in o["pane_failed"]], "load": statistics.mean(o["load"] for o in outs),
            "lease_written": sum(o["lease_written"] for o in outs), "work_rows": sum(o["work_rows"] for o in outs),
            "load_peak": peak}


def replay_together(b, clones, hooks, arm, phase, name, pane=None):
    """One replay in each of `clones` at once, each with its own session id, query log home and coord store, started
    together (a barrier) and merged by `together`; the result also holds `load_peak`."""
    if len(clones) == 1:
        return replay(b, clones[0], hooks, arm, phase, name, pane)
    peak = LoadPeak()
    gate = threading.Barrier(len(clones), action=peak.start)
    outs, errors = [None] * len(clones), []

    def one(i):
        try:
            outs[i] = replay(b, clones[i], hooks, arm, phase, f"{name}-s{i}", pane, gate, SAMPLE_S * len(clones))
        except Exception as e:  # a replay that fails before the gate would leave the others waiting for it
            errors.append(e)
            gate.abort()
    threads = [threading.Thread(target=one, args=(i,)) for i in range(len(clones))]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    if peak.is_alive():
        peak.finish()
    if errors:
        raise errors[0]
    return together(outs, peak.peak)


def host_note(loads):
    """What a cpu_s row says of the host: its cores, the 1-minute load at the replays' start and that the caches were warm."""
    return (f"{os.cpu_count()} cores, load {statistics.mean(loads):.1f} (1 min at the start of each rep), warm: one "
            "unmeasured replay first; a hook's tree CPU (os.wait4) is charged to the class of its command")


def row_note(metric, cls, arm, loads, window, sessions=1):
    """The note of a cpu_s, rss_peak_mb or rss_mean_mb row: cpu_s says the host (host_note) and, for a class that only ever
    runs as a child of a hook command, that its CPU is charged to the parent; a row of an arm with the pane's commands says
    it is over the pane window, not over a session; with `sessions` above 1 the figure is the sum of that many sessions
    that ran at once, and a peak is the sum of their peaks."""
    note = host_note(loads) if metric == "cpu_s" else ""
    if metric == "cpu_s" and cls in CHILD_CLASSES:
        note += (f"; {cls} runs only as a child of a hook command (arm B: or a pane command), so its CPU is charged to its "
                 "parent's class, not to this one, and this row holds none of it")
    if arm in PANE_ARMS:
        note += f"{'; ' if note else ''}over the pane window: the replay plus the pane's {window:g} s window, not a session"
    if sessions > 1:
        note += f"{'; ' if note else ''}the sum of {sessions} sessions that ran at once" + (
            ", their peaks not at one moment, so at most the host's peak" if metric == "rss_peak_mb" else "")
    return note


def warm_pane(b, clone):
    """One unmeasured run of each pane command, so the first measured run of arm B finds the caches warm as a long
    session's does."""
    env = {**plant(b, clone, "warm-pane"), "COLUMNS": PANE_COLUMNS}
    for flags in PANE_COMMANDS:
        subprocess.run(["python3", "_tools/kbmon.py", *flags], cwd=str(clone), env=env, stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def capture_class(name):
    """The class of an fs_usage process name (the part before the thread id): every Python program is `kb-tools`."""
    n = name.lower()
    if re.fullmatch(r"python[\d.]*", n):
        return "kb-tools"
    return n if n in CAPTURE_CLASSES else "other"


def read_capture(path):
    """Count the file reads of a capture of `fs_usage -w -f filesys` per process class (kb/public/python/macos-fs-usage-output.md).
    A read is an open whose mode string starts with R, a read, readv, pread or preadv, or an RdData; a write, a WrData and
    any other call is left out. One read of one file can show as an open, a descriptor read and a disk read, so each
    class also counts the three kinds apart. A RdData line prints a /dev token before an optionally empty path, and a
    line with no path adds none to the paths. Returns {"classes": {class: {"reads", "opens", "descriptor", "disk": n,
    "paths": set}}, "paths": set, "lines": n, "unread": n}; raises ValueError when no line of the file has the shape of a
    wide fs_usage line."""
    per = {c: {"reads": 0, "opens": 0, "descriptor": 0, "disk": 0, "paths": set()} for c in CAPTURE_CLASSES}
    every, lines, unread = set(), 0, 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for ln in f:
            m = FS_LINE.match(ln)
            if not m:
                unread += bool(ln.strip())
                continue
            lines += 1
            call = re.sub(r"(?:_nocancel)?(?:\[[^\]]*\])?$", "", m.group(1))
            mid = m.group(2)
            mode = re.search(r"\(([^)\s]*)\)", mid)
            is_open = call in OPEN_CALLS and bool(mode) and mode.group(1)[:1] == "R"
            if not (call in READ_CALLS or is_open):
                continue
            cell = per[capture_class(m.group(3))]
            cell["reads"] += 1
            cell["opens" if is_open else "disk" if call == "RdData" else "descriptor"] += 1
            where = re.sub(r"^(?:(?:[A-Z]=\S+|\([^)\s]*\)|\[[^\]]*\])\s*)+", "", mid)
            if call == "RdData":
                where = re.sub(r"^/dev/\S+(?:\s+|$)", "", where)
            if where:
                cell["paths"].add(where.strip())
                every.add(where.strip())
    if not lines:
        raise ValueError(f"{path}: no line of a wide fs_usage capture (a timestamp, the call, the fields, the time and process.thread)")
    return {"classes": per, "paths": every, "lines": lines, "unread": unread}


def capture_rows(b):
    """The rows of `run session-load --fs-usage FILE`: per process class and for all, `file_reads`, its three kinds
    (`opens_read`, `descriptor_reads`, `disk_reads`) and `distinct_paths`."""
    got = b.capture
    note = (f"open for reading (mode starts R), read, readv, pread, preadv and RdData lines of a capture of fs_usage -w -f filesys, "
            f"writes left out; {got['lines']} lines read, {got['unread']} not of that shape; a path is the last 28 bytes fs_usage prints; "
            "one read of one file can show as an open, a descriptor read and a disk read, so the three kinds do not add up to the files read")
    kinds = (("file_reads", "reads"), ("opens_read", "opens"), ("descriptor_reads", "descriptor"), ("disk_reads", "disk"))
    for cls in (*CAPTURE_CLASSES, "all"):
        cells = list(got["classes"].values()) if cls == "all" else [got["classes"][cls]]
        for metric, key in kinds:
            b.row("session-load", f"capture {cls}", "capture", metric, sum(c[key] for c in cells), 1,
                  note=note if cls == "all" and metric == "file_reads" else "")
        b.row("session-load", f"capture {cls}", "capture", "distinct_paths", len(got["paths"] if cls == "all" else cells[0]["paths"]), 1)


def intake_real_rows(b):
    """The rows of `run session-load --intake-real`: arm A's SessionStart intake hook alone, replayed in a clone left as
    the checkout is (no pin_drift), so its drift scan runs the checks of the draft and todo items whose touches changed
    since their file did, until the scan's budget is spent. Case INTAKE_REAL_CASE, arm A: the median over the reps of
    the hook command's `cpu_s` (os.wait4, its children included), `wall_s` (the command's own, not the replay's) and
    `spawns` (the command and the processes the Python programs of its tree started). One unmeasured replay first."""
    import bl_ci, bl_intake
    clone = b.clone("session-load-real", "local")
    hooks = intake_hooks(hook_commands(clone))
    if not hooks:
        raise RuntimeError("no SessionStart command of the intake hook in .claude/settings.json")
    replay(b, clone, hooks, "A", "idle", "warm-real")
    reps = [replay(b, clone, hooks, "A", "idle", f"real-{i}") for i in range(max(1, b.reps))]
    bad = [h["rc"] for r in reps for h in r["hooks"] if h.get("rc") != 0]
    if bad:
        raise RuntimeError(f"the intake hook exited with {bad[0]}: its figures would not stand for a session")
    runs = [r["hooks"][0] for r in reps]
    kids = [1 + len(h["children"]) for h in runs]
    note = (host_note([r["load"] for r in reps]) + f"; the clone is left as the checkout is, so the drift scan runs item checks until "
            f"its budget of {bl_intake.DRIFT_BUDGET_S} s is spent (the hook stops waiting for its detectors after "
            f"{bl_ci.INTAKE_HOOK_BUDGET_S} s): the checks that fit move with the host's speed and load")
    for metric, vals, n in (("cpu_s", [h["cpu_s"] for h in runs], note), ("wall_s", [h["wall_s"] for h in runs], ""),
                            ("spawns", kids, "the command and the processes Python programs of its tree started, per replay")):
        b.row("session-load", INTAKE_REAL_CASE, "A", metric, statistics.median(vals), len(vals), note=n)


def cpu_seconds(text):
    """The seconds of a `ps` time field (`[DD-][[HH:]MM:]SS[.cc]`)."""
    days, _, rest = text.rpartition("-")
    secs = 0.0
    for part in rest.split(":"):
        secs = secs * 60 + float(part)
    return secs + (int(days) * 86400 if days else 0)


def cpu_listing():
    """[(pid, ppid, rss_kb, cpu_s, args)] of one `ps -A` listing: `listing` with the CPU time each process has used."""
    p = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,rss=,time=,args="], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    out = []
    for ln in p.stdout.splitlines():
        w = ln.split(None, 4)
        if len(w) >= 4 and all(x.isdigit() for x in w[:3]) and re.fullmatch(r"(?:\d+-)?[\d:]+(?:\.\d+)?", w[3]):
            out.append((int(w[0]), int(w[1]), int(w[2]), cpu_seconds(w[3]), w[4] if len(w) > 4 else ""))
    return out


def live_class(args, clone):
    """The class of a live process: `process_class`, with `kbtail` (the follower of `kbtail.py`) and a `kbmon` named by its
    bare script name (a Python program started in `_tools` as `kbmon.py ...`, which `mon_host.kind_of` cannot place)."""
    words = [os.path.basename(w) for w in args.split()]
    python = bool(words) and re.fullmatch(r"python[\d.]*", words[0]) is not None
    if python and "kbtail.py" in words:
        return "kbtail"
    cls = process_class(args, clone)
    return "kbmon" if python and cls == "other" and "kbmon.py" in words else cls


def live_roots(b, rows):
    """({root pid: class}, [{"class", "role", "item"}]) of the processes whose trees `run session-load --live` follows: the
    live Claude Code sessions of this clone (`mon_sessions.live_sessions`: the class `claude headless` for a worker, sprint
    runner, reviewer, benchmark agent, bare twin or observer, `claude interactive` for the other roles), or the processes
    `--live-pids` names that are running (a class by their own command line, role None). An item is kept only as a backlog
    item id, else None: the raw suffix of a branch can be any text."""
    pids = getattr(b, "live_pids", None)
    if pids:
        found = [p for p in pids if p in rows]
        for p in pids:
            if p not in rows:
                print(f"session-load: --live-pids: no running process {p}", flush=True)
        return ({p: live_class(rows[p][4], HOME) for p in found},
                [{"class": live_class(rows[p][4], HOME), "role": None, "item": None} for p in found])
    import mon_sessions
    sessions = [s for s in mon_sessions.live_sessions(HOME) if s["pid"] in rows]
    cls = lambda s: "claude headless" if s["role"] in LIVE_HEADLESS_ROLES else "claude interactive"  # noqa: E731
    return ({s["pid"]: cls(s) for s in sessions},
            [{"class": cls(s), "role": s["role"], "item": s["item"] if LIVE_ITEM_ID.fullmatch(s["item"] or "") else None}
             for s in sessions])


class Live:
    """The ticks of `run session-load --live`: from each `cpu_listing`, the descendants of the roots (this process and its
    children left out) with, per tick, the memory of each class, and per process its class (from its command line when first
    seen, which the listing then drops), the CPU time it had at its first and last tick and its peak memory. A process that
    lives less than a tick is not seen."""

    def __init__(self, clone, roots):
        self.clone, self.roots = str(clone), dict(roots)
        self.ticks, self.times, self.procs = [], [], {}  # per tick {class: rss kb}, its time; pid -> cell

    def tick(self, listed, now):
        rows = {pid: (ppid, rss, cpu, args) for pid, ppid, rss, cpu, args in listed}
        kids = {}
        for pid, (ppid, _, _, _) in rows.items():
            kids.setdefault(ppid, []).append(pid)
        here = {p: self.roots[p] for p in self.roots if p in rows and p != os.getpid()}
        todo = list(here)
        while todo:
            for c in kids.get(todo.pop(), []):
                if c != os.getpid() and c not in here:
                    here[c] = self.procs[c]["class"] if c in self.procs else live_class(rows[c][3], self.clone)
                    todo.append(c)
        per, first = {}, not self.ticks
        for pid, cls in here.items():
            _, rss, cpu, _ = rows[pid]
            cell = self.procs.setdefault(pid, {"class": cls, "tick": len(self.ticks), "cpu0": cpu if first or pid in self.roots else 0.0,
                                               "cpu1": cpu, "peak": 0, "root": pid in self.roots})
            cell["cpu1"], cell["peak"] = cpu, max(cell["peak"], rss)
            per[cls] = per.get(cls, 0) + rss
        self.ticks.append(per)
        self.times.append(now)


def live_snapshot(live, roots, window):
    """The path of the JSON file `run session-load --live` keeps its per-tick figures in, under `_cache/` of this clone: per
    tick the seconds since the first and each class's memory in KiB, per process its class, tick of first sight, CPU
    seconds and peak memory, and the roots' classes, roles and item ids. No command line, session id or path."""
    path = HOME / "_cache" / "bench" / f"session-load-live-{time.strftime('%Y%m%dT%H%M%S')}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"window_s": window, "tick_s": LIVE_TICK_S, "roots": roots,
            "ticks": [{"t": round(t - live.times[0], 3), "rss_kb": per} for t, per in zip(live.times, live.ticks)],
            "processes": [{"class": c["class"], "tick": c["tick"], "root": c["root"], "cpu_s": round(c["cpu1"] - c["cpu0"], 3),
                           "rss_peak_kb": c["peak"]} for _, c in sorted(live.procs.items())]}
    path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8", newline="\n")
    return path


def live_rows(b):
    """The rows of `run session-load --live`: for `--window` seconds (default WINDOW_S) every LIVE_TICK_S the process trees of
    the live sessions (`live_roots`) are listed with `ps`, and per process class and for `all`, arm `live`, case `live
    <class>`: `cpu_s` (the CPU time the class's processes used over the window: from the first tick for a process that was
    running at it, all of it for one that began later), `rss_peak_mb` (the highest tick's sum), `rss_mean_mb` (the mean of
    the ticks' sums, a tick with no process of the class counting 0) and `spawns_per_min` (the processes first seen after
    the first tick, per minute of the window). The snapshot of the ticks is written under `_cache/` (live_snapshot) and its
    path printed."""
    if not shutil.which("ps"):
        raise Skip("no ps: run it on macOS or Linux")
    window = getattr(b, "window", None) or WINDOW_S
    roots, described = live_roots(b, {r[0]: r for r in cpu_listing()})
    if not roots:
        raise Skip("no running Claude Code session in this clone and no running --live-pids process to follow")
    live, load = Live(HOME, roots), os.getloadavg()[0] if hasattr(os, "getloadavg") else 0.0
    end = time.monotonic() + window
    while True:
        live.tick(cpu_listing(), time.monotonic())
        if time.monotonic() >= end:
            break
        time.sleep(min(LIVE_TICK_S, max(0.0, end - time.monotonic())))
    elapsed = live.times[-1] - live.times[0]
    note = (f"{os.cpu_count()} cores, load {load:.1f} at the start; {len(live.ticks)} ps listings over {elapsed:.0f} s of the process trees "
            f"of {len(roots)} roots ({', '.join(sorted({r['class'] for r in described}))}), this process left out; a process that "
            "lives less than a listing is not seen, and one that began before the window counts only its CPU since the first listing")
    for cls in [*sorted({c["class"] for c in live.procs.values()}), "all"]:
        cells = [c for c in live.procs.values() if cls in ("all", c["class"])]
        sums = [(sum(per.values()) if cls == "all" else per.get(cls, 0)) / 1024 for per in live.ticks]
        for metric, value in (("cpu_s", sum(c["cpu1"] - c["cpu0"] for c in cells)), ("rss_peak_mb", max(sums)),
                              ("rss_mean_mb", statistics.mean(sums)),
                              ("spawns_per_min", sum(1 for c in cells if c["tick"] > 0 and not c["root"]) / (elapsed / 60))):
            b.row("session-load", f"live {cls}", LIVE_ARM, metric, value, 1, note=note if metric == "cpu_s" and cls == "all" else "")
    print(f"session-load: live snapshot written to {live_snapshot(live, described, window)}", flush=True)


class PaidBench(Bench):
    """The Bench of `run session-load --paid`. `Bench` reads the Claude Code version with a `claude --version` of its own, and a
    paid run starts no `claude` that is not a capped session, so that one runs a `claude` that fails at once (the version
    stays `?`, then the init event of the first session names it, `paid_rows`)."""

    def __init__(self, scratch, reps):
        with tempfile.TemporaryDirectory() as d:
            path = os.environ.get("PATH", "")
            os.environ["PATH"] = os.pathsep.join((str(shim_dir(d)), path))
            try:
                super().__init__(scratch, reps)
            finally:
                os.environ["PATH"] = path


def arm_settings(clone, arm):
    """Write into `clone` the .claude/settings.json of `arm`: the project's own, less the hook commands the arm leaves out
    (LEFT_OUT, as `arm_hooks` does). Arm D has its hooks turned off by NO_HOOKS on the command line instead."""
    out = LEFT_OUT[arm]
    if not out:
        return
    path = Path(clone) / ".claude" / "settings.json"
    spec = json.loads(path.read_text(encoding="utf-8"))
    hooks = {}
    for ev, groups in spec.get("hooks", {}).items():
        kept = []
        for g in groups:
            left = [h for h in g["hooks"] if not any(x in h.get("command", "") for x in out)]
            if left:
                kept.append({**g, "hooks": left})
        if kept:
            hooks[ev] = kept
    spec["hooks"] = hooks
    path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8", newline="\n")


def paid_argv(arm):
    """The `claude -p` of one paid session of `arm`: Haiku 5.5, a budget cap, the project's and local settings only (the user's
    own hooks and plugins are not the clone's), the prompt on stdin."""
    return [shutil.which("claude") or "claude", "-p", "--model", PAID_MODEL, "--max-budget-usd", f"{PAID_RUN_USD:g}",
            "--output-format", "stream-json", "--verbose", "--no-session-persistence", "--setting-sources", "project,local",
            "--allowedTools", PAID_TOOLS, *(NO_HOOKS if arm == "D" else [])]


def read_stream(path):
    """(the result event, the Claude Code version of the init event) of a stream-json file; None and "" for what it lacks."""
    result, version = None, ""
    for ln in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            ev = json.loads(ln)
        except ValueError:
            continue
        if isinstance(ev, dict) and ev.get("type") == "result":
            result = ev
        elif isinstance(ev, dict) and ev.get("type") == "system" and ev.get("subtype") == "init":
            version = ev.get("claude_code_version") or version
    return result, version


class Ticker(threading.Thread):
    """The `ps` listings of one group of paid sessions: every PAID_TICK_S one `cpu_listing`, handed to the `Live` of each
    session still running (its root registered with `add` until `finish`), so N sessions at once cost one listing a tick."""

    def __init__(self, clones):
        super().__init__(daemon=True)
        self.lives, self.lock, self.stop = [Live(c, {}) for c in clones], threading.Lock(), threading.Event()

    def add(self, i, pid):
        with self.lock:
            self.lives[i].roots[pid] = "claude"

    def finish(self, i, pid):
        with self.lock:
            self.lives[i].roots.pop(pid, None)

    def run(self):
        while not self.stop.wait(PAID_TICK_S):
            with self.lock:
                if not any(live.roots for live in self.lives):
                    continue
            listed, now = cpu_listing(), time.monotonic()
            have = {row[0] for row in listed}
            with self.lock:
                for live in self.lives:
                    if have & set(live.roots):
                        live.tick(listed, now)


def paid_classes(live, cpu_s):
    """{class: {cpu_s, peak, mean, spawns}} of one paid session's ticks, and `all`: the CPU of the others is the difference of
    the `ps` times from a process's first listing to its last, `all`'s the `cpu_s` os.wait4 gave the session; the memory is
    in MiB, `spawns` the processes first seen after the first listing."""
    out = {}
    for cls in sorted({c["class"] for c in live.procs.values()}):
        mine = [c for c in live.procs.values() if c["class"] == cls]
        sums = [per.get(cls, 0) / 1024 for per in live.ticks]
        out[cls] = {"cpu_s": sum(c["cpu1"] - c["cpu0"] for c in mine), "peak": max(sums), "mean": statistics.mean(sums),
                    "spawns": sum(1 for c in mine if c["tick"] > 0 and not c["root"])}
    sums = [sum(per.values()) / 1024 for per in live.ticks] or [0.0]
    out["all"] = {"cpu_s": cpu_s, "peak": max(sums), "mean": statistics.mean(sums), "spawns": sum(c["spawns"] for c in out.values())}
    return out


def kill_group(pid):
    try:
        os.killpg(pid, signal.SIGKILL)
    except OSError:
        pass


def paid_run(clone, arm, phase, env, ticker, i, out):
    """One paid session in `clone`: its stdout to the file `out`, its process tree followed by `ticker`, killed after
    PAID_TIMEOUT_S. Its record: `classes` (paid_classes), `wall_s`, `failed` (1 when it exited non-zero, ended with no result
    event or with an error one), `cost`, `version`, and its tokens (spent, bench_core, counts it)."""
    t0 = time.perf_counter()
    with open(out, "w", encoding="utf-8", newline="\n") as f:  # a file, not a pipe: this waits in wait4 and a full pipe would stall the session
        p = subprocess.Popen(paid_argv(arm), cwd=str(clone), env=env, stdin=subprocess.PIPE, stdout=f, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        ticker.add(i, p.pid)
        timer = threading.Timer(PAID_TIMEOUT_S, kill_group, args=(p.pid,))
        timer.start()
        try:
            p.stdin.write(PAID_PROMPTS[phase].encode("utf-8"))
            p.stdin.close()
        except OSError:  # a claude that exits without reading its prompt
            pass
        _, status, ru = os.wait4(p.pid, 0)
        timer.cancel()
    wall = time.perf_counter() - t0
    p.returncode = os.waitstatus_to_exitcode(status)
    ticker.finish(i, p.pid)
    result, version = read_stream(out)
    use = (result or {}).get("usage") or {}
    cost = (result or {}).get("total_cost_usd") or 0.0
    spent(cost, (use.get("input_tokens") or 0) + (use.get("cache_creation_input_tokens") or 0) + (use.get("cache_read_input_tokens") or 0),
          use.get("output_tokens") or 0)
    failed = int(p.returncode != 0 or result is None or bool(result.get("is_error")) or str(result.get("subtype") or "").startswith("error_"))
    settle(clone)
    return {"classes": paid_classes(ticker.lives[i], ru.ru_utime + ru.ru_stime), "wall_s": wall, "failed": failed, "cost": cost,
            "version": version, "rc": p.returncode}


def paid_group(b, clones, arm, phase, rep):
    """N paid sessions at once, one in each of `clones`, each with its own session, query log home and coord store, merged as
    `together` merges replays: per class the sums of the CPU, memory and starts, the longest `wall_s`, the sum of the failures
    and of the cost, the mean of the loads at the start. The first session's Claude Code version is `b.cc` when it names one."""
    ticker = Ticker(clones)
    ticker.start()
    outs, errors = [None] * len(clones), []
    load = os.getloadavg()[0] if hasattr(os, "getloadavg") else 0.0

    def one(i):
        try:
            reset(clones[i])
            arm_settings(clones[i], arm)
            env = arm_env(plant(b, clones[i], f"paid-{arm}-{phase}-{rep}-s{i}"), arm)
            outs[i] = paid_run(clones[i], arm, phase, env, ticker, i, b.scratch / "session-load-data" / f"paid-{arm}-{phase}-{rep}-s{i}.jsonl")
        except Exception as e:
            errors.append(e)
    threads = [threading.Thread(target=one, args=(i,)) for i in range(len(clones))]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    ticker.stop.set()
    ticker.join()
    if errors:
        raise errors[0]
    for o in outs:
        if o["version"] and b.cc in ("", "?"):
            b.cc = o["version"]
    per = {}
    for o in outs:
        for cls, cell in o["classes"].items():
            sums = per.setdefault(cls, dict.fromkeys(("cpu_s", "peak", "mean", "spawns"), 0.0))
            for k, v in cell.items():
                sums[k] += v
    return {"classes": per, "wall_s": max(o["wall_s"] for o in outs), "failed": sum(o["failed"] for o in outs),
            "cost": sum(o["cost"] for o in outs), "costs": [o["cost"] for o in outs], "load": load}


def paid_plan(arms, sessions, reps):
    """[(rep, arm, phase, n)] of a paid run in the order it starts them: each rep every arm, each arm every phase, each phase
    every N of `sessions`; a group is N sessions at once, so the runs are the sum of the Ns."""
    return [(rep, arm, phase, n) for rep in range(reps) for arm in arms for phase in PHASES for n in sessions]


def paid_cost(history, phase):
    """(USD of one paid session of `phase`, its basis): the mean `cost` of the one-session case `<phase> all` of the newest
    record of the results `history` that holds a paid row, else PAID_TOKENS[phase] at the list price of PAID_MODEL."""
    mine = [r for r in history if r["scenario"] == "session-load" and r["model"] == PAID_MODEL and r["metric"] == "cost"
            and r["case"] == f"{phase} all"]
    if mine:
        record = max(r["record"] for r in mine)
        return statistics.mean(float(r["value"]) for r in mine if r["record"] == record), f"the mean cost of the record {record}"
    p, t = PRICE[PAID_MODEL][0], PAID_TOKENS[phase]
    return ((t["uncached"] * p[1] + t["cache_write"] * write_rate(p) + t["cache_read"] * p[4] + t["out"] * p[2]) / 1e6,
            "the default tokens at list price")


def paid_note(metric, cls, loads, n):
    """The note of a paid `cpu_s` row of `all` (what its figure is) or of a `spawns_per_min` row."""
    if metric == "spawns_per_min":
        return ("processes first seen after a session's first `ps` listing, per minute of its wall time: a process that lives "
                f"less than {PAID_TICK_S:g} s is missed, so a lower bound" + (f"; the sum of {n} sessions" if n > 1 else ""))
    return (f"{os.cpu_count()} cores, load {statistics.mean(loads):.1f} (1 min at the start of each group); the CPU os.wait4 gave "
            f"the claude process, its waited-for children included; a class's own row is the `ps` time from a process's first "
            f"listing to its last, every {PAID_TICK_S:g} s" + (f"; the sum of {n} sessions" if n > 1 else ""))


def paid_rows(b):
    """The rows of `run session-load --paid`: per arm, phase, N of `b.sessions` and rep one group of N `claude -p` sessions of
    PAID_MODEL at once (PAID_RUN_USD each; `paid_plan`'s order), each in a throwaway clone of its own, in arm A's settings
    (the clone's), C's (`arm_settings`) or D's (NO_HOOKS) with the prompt of PAID_PROMPTS[phase], its process tree sampled
    (`Ticker`). The rows are those of the replay (cases `<phase> <class>[ xN]`, `cpu_s`, `rss_peak_mb`, `rss_mean_mb`,
    `spawns_per_min`; `<phase> replay`'s `wall_s` and `run_failures`), the median over the reps, with the model column set, and
    `<phase> all`'s `cost` (USD, the sum of the N sessions). With `b.max_usd` no group starts once the spend so far and the
    group, each session at the mean cost of the finished ones of its phase (else of all, and the first group starts), would
    pass it: a `spend_stopped` row per arm names the sessions not started. With `b.dry` it prints the plan and starts no
    `claude`."""
    arms = list(getattr(b, "load_arms", None) or DEFAULT_ARMS)
    sessions = sorted(set(getattr(b, "sessions", None) or (1,)))
    plan, cap = paid_plan(arms, sessions, max(1, b.reps)), getattr(b, "max_usd", None)
    total = sum(n for _, _, _, n in plan)
    if getattr(b, "dry", False):
        history = read_rows(RESULTS)
        usd = 0.0
        print(f"session-load: {total} runs of {PAID_MODEL} ({len(arms)} arms {','.join(arms)} x {len(PHASES)} phases x sessions "
              f"{','.join(map(str, sessions))} = {sum(sessions)} runs per arm and phase x {max(1, b.reps)} reps), each `claude -p` "
              f"under --max-budget-usd {PAID_RUN_USD:g} in a throwaway clone", flush=True)
        for phase in PHASES:
            each, basis = paid_cost(history, phase)
            runs = sum(n for _, _, p, n in plan if p == phase)
            usd += runs * each
            print(f"session-load: {phase}: {runs} runs, estimate ${runs * each:.2f} at ${each:.4f} a run ({basis})", flush=True)
        print(f"session-load: estimate ${usd:.2f} in all, at most ${total * PAID_RUN_USD:.2f} by the budget cap of each run: an estimate, "
              "not a measurement" + (f"; over --max-usd ${cap:.2f}: a run would stop before the last groups start"
                                     if cap is not None and usd > cap else ""), flush=True)
        raise Skip(f"dry run: {total} runs, no claude started; estimated spend ${usd:.2f}")
    clones = []
    for i in range(sessions[-1]):  # one throwaway clone for each session beyond the first, as the replay has
        clones.append(b.clone("session-load" if i == 0 else f"session-load-{i}", "local"))
        pin_drift(clones[-1])
    (b.scratch / "session-load-data").mkdir(parents=True, exist_ok=True)
    got = {(arm, phase, n): [] for arm in arms for phase in PHASES for n in sessions}
    costs, base, stopped = {phase: [] for phase in PHASES}, spent_usd(), []
    for k, (rep, arm, phase, n) in enumerate(plan):
        every = costs[phase] or [c for cs in costs.values() for c in cs]
        if cap is not None and spent_usd() - base + n * (statistics.mean(every) if every else 0.0) > cap:
            stopped = plan[k:]
            break
        r = paid_group(b, clones[:n], arm, phase, rep)
        got[(arm, phase, n)].append(r)
        costs[phase] += r["costs"]
        if RAW.get("path"):
            with open(RAW["path"], "a", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps({"arm": arm, "phase": phase, "sessions": n, "rep": rep, "cost": r["cost"], "failed": r["failed"],
                                    "wall_s": round(r["wall_s"], 2)}) + "\n")
    seen = sorted({c for rs in got.values() for r in rs for c in r["classes"] if c != "all"}, key=lambda c: (c not in CLASSES, c))
    for (arm, phase, n), reps in got.items():
        if not reps:
            continue
        sfx, loads = (f" x{n}" if n > 1 else ""), [r["load"] for r in reps]
        for cls in [*seen, "all"]:
            case = f"{phase} {cls}{sfx}"
            get = lambda r, key: r["classes"].get(cls, {}).get(key, 0.0)  # noqa: E731
            for metric, key in (("cpu_s", "cpu_s"), ("rss_peak_mb", "peak"), ("rss_mean_mb", "mean")):
                b.row("session-load", case, arm, metric, statistics.median(get(r, key) for r in reps), len(reps), PAID_MODEL,
                      paid_note("cpu_s", cls, loads, n) if metric == "cpu_s" and cls == "all" else "")
            b.row("session-load", case, arm, "spawns_per_min", statistics.median(get(r, "spawns") / (r["wall_s"] / 60) for r in reps),
                  len(reps), PAID_MODEL, paid_note("spawns_per_min", cls, loads, n) if cls == "all" else "")
        b.row("session-load", f"{phase} replay{sfx}", arm, "wall_s", statistics.median(r["wall_s"] for r in reps), len(reps), PAID_MODEL,
              f"the longest of {n} sessions that ran at once" if n > 1 else "")
        b.row("session-load", f"{phase} replay{sfx}", arm, "run_failures", statistics.median(r["failed"] for r in reps), len(reps),
              PAID_MODEL, "sessions that exited non-zero, ended with no result event or with an error one (the budget cap included)")
        b.row("session-load", f"{phase} all{sfx}", arm, "cost", statistics.median(r["cost"] for r in reps), len(reps), PAID_MODEL,
              "USD the result events state" + (f"; the sum of {n} sessions" if n > 1 else ""))
    for arm in dict.fromkeys(a for _, a, _, _ in stopped):
        runs = sum(n for _, a, _, n in stopped if a == arm)
        b.row("session-load", "not started", arm, "spend_stopped", runs, runs, PAID_MODEL, "sessions the --max-usd cap left unstarted")
    if stopped:
        print(f"session-load: stopped at the --max-usd cap of ${cap:.4f} with {sum(n for _, _, _, n in stopped)} of {total} sessions "
              "not started; the rows `spend_stopped` name them", flush=True)


def s_session_load(b):
    """One session's hook cost on the host, no model: the hook events of a session replayed through this clone's own hook
    commands in a throwaway clone (query log in mode `local` under a scratch plugin data directory, a `claude` that fails
    at once), in arm A (every hook), B (A and the commands of the kbmon-pane mod), C (coord_hook.py and the querylog.py
    hooks left out), D (no hook) and worker (A in the environment of a dispatched worker, KB_UNWATCHED=1, so the hooks marked
    `kbpy --person` exit at once), each in an idle phase (SessionStart, SessionEnd) and a working phase (the events of
    WORKING between them). Arm B runs, over a window of `b.window` seconds per phase, the pane's commands the mod's way:
    the first after its FIRST_MS and then one every `b.pane_every` seconds (default its REFRESH_MS). Per phase, arm and
    process class: the CPU seconds, peak and mean resident memory in MiB and the starts per minute of a session of
    NOMINAL_S (the pane's own starts per minute of the window), `lease_written` (1 when the replay's coord store held the
    session's presence lease just before SessionEnd) and `work_rows` (the query log work rows the hooks wrote); per synchronous hook command its median milliseconds (a
    run of an async hook is `async_ms`: Claude Code does not wait for it). Each rep runs every arm and phase once, the
    medians of the reps are the rows. With `b.capture` (run --fs-usage FILE) it only writes the file reads of that capture;
    otherwise it prints the `sudo fs_usage` command the operator runs by hand, which this tool never runs. With
    `b.intake_real` (run --intake-real) it only replays the intake hook, in a clone no item is pinned in (intake_real_rows).
    With `b.sessions` (run --sessions N,N) each N is also run as N sessions at once (replay_together), each in a throwaway clone of
    its own with its own session id: for N above 1 the rows are the same, their case ending in ` xN`, each a sum over the
    sessions (`wall_s` the longest), and a `load_peak` row, the host's 1-minute load at its highest during the run. With `b.paid` (run --paid) it only runs
    real sessions (paid_rows)."""
    if getattr(b, "capture", None):  # --fs-usage FILE: count a capture, start no replay
        return capture_rows(b)
    if getattr(b, "live", False):  # --live: follow the host's running sessions, start no replay
        return live_rows(b)
    if not hasattr(os, "wait4"):
        raise Skip("no os.wait4 (Windows): run it on macOS or Linux")
    need_sh()
    if getattr(b, "intake_real", False):  # --intake-real: the intake hook in an unpinned clone, nothing else
        return intake_real_rows(b)
    if getattr(b, "paid", False):  # --paid: real Haiku 5.5 sessions per arm, phase and session count, no hook replay
        return paid_rows(b)
    print(f"session-load: for the file reads of a session, run `{FS_COMMAND}` by hand beside it (macOS, needs root; stop it with "
          "Ctrl-C), then `python3 _tools/benchmarks.py run session-load --fs-usage fs_usage.txt`", flush=True)
    arms =list(getattr(b, "load_arms", None) or DEFAULT_ARMS)
    sessions = sorted(set(getattr(b, "sessions", None) or (1,)))
    clone = b.clone("session-load", "local")
    pin_drift(clone)
    clones = [clone]
    for i in range(1, sessions[-1]):  # one more throwaway clone for each session beyond the first
        clones.append(b.clone(f"session-load-{i}", "local"))
        pin_drift(clones[-1])
    hooks = hook_commands(clone)
    first_s, refresh_s = pane_schedule(clone)
    window = getattr(b, "window", None) or WINDOW_S
    every = getattr(b, "pane_every", None) or refresh_s
    pane = (first_s, every, window)
    for i, c in enumerate(clones):  # the caches of Python, the pack index and git of every clone, not measured
        replay(b, c, hooks, "A", "working", "warm" if i == 0 else f"warm-{i}")
    if any(arm in PANE_ARMS for arm in arms):
        warm_pane(b, clone)
    got = {(arm, phase, n): [] for arm in arms for phase in PHASES for n in sessions}
    for rep in range(max(1, b.reps)):
        for arm in arms:
            for phase in PHASES:
                for n in sessions:
                    got[(arm, phase, n)].append(replay_together(b, clones[:n], hooks, arm, phase, f"{arm}-{phase}-{rep}", pane))
    seen = [c for c in CLASSES if any(r["classes"].get(c, {}).get(k) for rs in got.values() for r in rs
                                      for k in ("spawns", "pane_spawns"))]
    for (arm, phase, n), reps in got.items():
        sfx = f" x{n}" if n > 1 else ""  # N sessions at once: the same rows, their case ending in xN, each a sum over the sessions
        loads = [r["load"] for r in reps]
        med =lambda cls, key: statistics.median(r["classes"].get(cls, {}).get(key, 0.0) for r in reps)  # noqa: E731
        for cls in [*seen, "all"]:
            case = f"{phase} {cls}{sfx}"
            for metric, key in (("cpu_s", "cpu_s"), ("rss_peak_mb", "peak"), ("rss_mean_mb", "rss_mean_mb")):
                b.row("session-load", case, arm, metric, med(cls, key), len(reps), note=row_note(metric, cls, arm, loads, window, n))
            rate = statistics.median(r["classes"].get(cls, {}).get("spawns", 0) / (NOMINAL_S[phase] / 60)
                                     + r["classes"].get(cls, {}).get("pane_spawns", 0) / (window / 60) for r in reps)
            b.row("session-load", case, arm, "spawns_per_min", rate, len(reps),
                  note=f"a session of {NOMINAL_S[phase]} s" + (f", the pane's starts per minute of its {window:g} s window"
                                                               if arm in PANE_ARMS else "") + (f"; the sum of {n} sessions" if n > 1 else ""))
        if arm in PANE_ARMS:
            b.row("session-load", f"{phase} all{sfx}", arm, "pane_runs", statistics.median(r["pane_runs"] for r in reps), len(reps),
                  note=f"{PANE_COMMANDS[0][0]} then {' '.join(PANE_COMMANDS[1])}, the first after {first_s:g} s, then every "
                  f"{every:g} s over a window of {window:g} s; a tick that falls during a run does nothing")
        b.row("session-load", f"{phase} replay{sfx}", arm, "wall_s", statistics.median(r["wall_s"] for r in reps), len(reps),
              note=f"the longest of {n} sessions that ran at once" if n > 1 else "")
        b.row("session-load", f"{phase} replay{sfx}", arm, "hook_failures", statistics.median(len(r["failed"]) for r in reps),
              len(reps), note="hook commands that exited non-zero")
        for metric, note in (("lease_written", "1 when the replay's coord store held session/ID, the presence lease, just before SessionEnd"),
                             ("work_rows", "work rows in the replay's query log spool")):
            b.row("session-load", f"{phase} all{sfx}", arm, metric, statistics.median(r[metric] for r in reps), len(reps),
                  note=note + (f"; the sum of {n} sessions" if n > 1 else ""))
        if n > 1:
            b.row("session-load", f"{phase} all{sfx}", arm, "load_peak", statistics.median(r["load_peak"] for r in reps), len(reps),
                  note=f"the host's 1-minute load at its highest, read every {LOAD_SAMPLE_S:g} s while {n} sessions ran at once "
                  "(it moves slowly, so a short run shows mostly the load it began in); the median over the reps")
        if arm in PANE_ARMS:
            b.row("session-load", f"{phase} replay{sfx}", arm, "pane_failures", statistics.median(len(r["pane_failed"]) for r in reps),
                  len(reps), note="pane commands that exited with 2 or more")
    starts = {}
    for (arm, phase, n), reps in got.items():
        for i, r in enumerate(reps):
            for h in r["hooks"]:
                key = (arm, phase, h["label"], n)
                starts.setdefault(key, [0] * len(reps))[i] += 1 + len(h["children"])
    for (arm, phase, name, n), per in starts.items():
        b.row("session-load", f"{phase} hook {name}" + (f" x{n}" if n > 1 else ""), arm, "spawns", statistics.median(per), len(per),
              note="the command and the processes Python programs of its tree started, per replay" + (f", of all {n} sessions" if n > 1 else ""))
    timings = {}
    for (arm, phase, n), reps in got.items():
        for r in reps:
            for h in r["hooks"]:
                key = (arm, f"{h['event']} {h['label']}" + (f" ({h['tool']})" if h["tool"] else "") + (f" x{n}" if n > 1 else ""), h["async"])
                timings.setdefault(key, []).append(h["wall_s"] * 1000)
    for (arm, case, is_async), ms in timings.items():
        b.row("session-load", case, arm, "async_ms" if is_async else "sync_ms", statistics.median(ms), len(ms))
