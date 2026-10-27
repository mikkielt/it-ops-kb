"""The benchmarks' session-load scenario: what one Claude Code session of this clone costs the host, measured with no
model (stdlib only).

benchmarks.py registers the scenario in SCENARIOS and holds the command line; the harness is bench_core.py
(kb/_self/code.md, Layout and Imports; the scenario is described in kb/_self/reports/benchmarks.md). It replays the hook
events of one session through the hook commands of the throwaway clone's own .claude/settings.json, started as Claude
Code starts them (`sh -c`, the event as JSON on stdin, CLAUDE_PROJECT_DIR set), and measures every process it starts with
`os.wait4` (CPU and peak memory, which include the children the process waited for) and, for the processes those start,
with a sampler of `ps` (their memory) and a `sitecustomize` audit hook that logs each process a Python program starts
(their number and programs). Arm B adds the commands the kbmon-pane mod runs in an interactive session, on the mod's schedule.
This module imports no facade; `mon_host` is imported where a process is given its class.
"""
import json, os, re, shutil, statistics, subprocess, sys, threading, time, uuid
from pathlib import Path

from bench_core import Skip, git, need_sh, no_plugin_env, shim_dir

ARMS = ("A", "B", "C", "D")  # A: every hook; B: A and the kbmon pane's commands; C: coord_hook.py and querylog.py left out; D: none
DEFAULT_ARMS = ("A", "C", "D")  # B runs only when named: it adds WINDOW_S seconds to each phase
PHASES = ("idle", "working")  # idle: SessionStart then SessionEnd; working: a fixed script of events between them
LEFT_OUT = {"A": (), "B": (), "C": ("coord_hook.py", "querylog.py"), "D": None}  # a hook command naming one of these is not run
NOMINAL_S = {"idle": 60, "working": 300}  # the seconds of session a replay stands for: the divisor of spawns_per_min
CLASSES = ("kbmon", "fseventsd", "tests", "kb-tools", "claude", "other", "git", "lsof")  # mon_host's, then two more
CHILD_CLASSES = ("git", "lsof")  # classes whose processes only hook (or pane) commands start, so wait4 charges them to the parent
PANE_ARMS = ("B",)  # the arms that run the kbmon pane's commands
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
SAMPLE_S = 0.02  # the sampler's pause between two `ps` listings
SETTLE_S = 30  # seconds a replay waits for the processes it left running in the clone
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
      ("Bash", {"command": "python3 _tools/rag.py show public/windows/laps.md:1"}, {"stdout": "line"})],
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
    return re.sub(r'^sh "\$\{CLAUDE_PROJECT_DIR\}/_tools/kbpy"\s*', "", command)


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

    def __init__(self, clone):
        super().__init__(daemon=True)
        self.clone, self.roots, self.stop, self.lock = str(clone), {}, threading.Event(), threading.Lock()
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
            self.stop.wait(SAMPLE_S)

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
    """Wait, at most SETTLE_S, until no process names the clone's path in its command line (a detached distill ends)."""
    end = time.monotonic() + SETTLE_S
    while time.monotonic() < end:
        if not [1 for pid, _, _, args in listing() if pid != os.getpid() and str(clone) in args]:
            return
        time.sleep(0.2)


def pin_drift(clone):
    """Make no item of the clone eligible for the intake hook's drift scan, so that hook does the same work in every replay.
    The hook stops waiting for its detectors after INTAKE_HOOK_BUDGET_S, and its drift scan runs the checks of the draft or
    todo items whose touches changed since their file did, within a wall-clock budget of its own: the checks that fit, and so
    the processes started, move with the host's speed and load. One commit on the clone that changes the mode of each item file
    (no content) makes the newest commit of every item file the clone's HEAD, so no item is eligible and the scan only
    reads the items; what the real hook costs in a clone where checks do run is not measured here."""
    item_dir = json.loads((Path(clone) / "backlog.json").read_text(encoding="utf-8"))["item_dir"]
    files = git("ls-files", "--", item_dir, cwd=clone).splitlines()
    git("update-index", "--chmod=+x", "--", *files, cwd=clone)
    git("-c", "user.name=bench", "-c", "user.email=bench@example.com", "commit", "-q", "--no-verify", "-m",
        "bench: the item files' mode", cwd=clone)


def reset(clone):
    """The clone's working tree as the checkout left it, whatever a replay's hooks wrote, and the intake hook's drift
    cursor removed, so each replay's drift scan starts at the same item instead of where the replay before it stopped."""
    git("checkout", "-q", "--", ".", cwd=clone)
    git("clean", "-fdq", cwd=clone)
    (Path(clone) / git("rev-parse", "--git-path", "kb-intake-drift", cwd=clone)).unlink(missing_ok=True)


class Replay:
    """One replay of a session's events in `clone`: the hook processes it started and the sampler's view of their children."""

    def __init__(self, clone, env, hooks, pane=None):
        self.clone, self.env, self.hooks = Path(clone), env, hooks
        self.pane = pane  # None, or (first_s, every_s, window_s): the kbmon pane's schedule
        self.roots, self.threads = [], []  # one dict per hook command run
        self.panes = []  # one dict per pane command run (a pane run is each of PANE_COMMANDS once)
        self.pane_runs = 0

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
        sampler = Sampler(self.clone)
        if self.hooks:
            sampler.start()
        t0 = time.perf_counter()
        if self.pane:
            pane = threading.Thread(target=self.run_pane, args=(sampler, t0))
            pane.start()
            self.threads.append(pane)
        for name, target, payload in events(phase, self.clone, sid):
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
        return self.summary(sampler, wall)

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


def replay(b, clone, hooks, arm, phase, name, pane=None):
    reset(clone)
    env = plant(b, clone, name)
    load = os.getloadavg()[0] if hasattr(os, "getloadavg") else 0.0
    out = Replay(clone, env, arm_hooks(hooks, arm), pane if arm in PANE_ARMS else None).run(phase, str(uuid.uuid4()))
    out["load"] = load
    return out


def host_note(loads):
    """What a cpu_s row says of the host: its cores, the 1-minute load at the replays' start and that the caches were warm."""
    return (f"{os.cpu_count()} cores, load {statistics.mean(loads):.1f} (1 min at the start of each rep), warm: one "
            "unmeasured replay first; a hook's tree CPU (os.wait4) is charged to the class of its command")


def row_note(metric, cls, arm, loads, window):
    """The note of a cpu_s, rss_peak_mb or rss_mean_mb row: cpu_s says the host (host_note) and, for a class that only ever
    runs as a child of a hook command, that its CPU is charged to the parent; a row of an arm with the pane's commands says
    it is over the pane window, not over a session."""
    note = host_note(loads) if metric == "cpu_s" else ""
    if metric == "cpu_s" and cls in CHILD_CLASSES:
        note += (f"; {cls} runs only as a child of a hook command (arm B: or a pane command), so its CPU is charged to its "
                 "parent's class, not to this one, and this row holds none of it")
    if arm in PANE_ARMS:
        note += f"{'; ' if note else ''}over the pane window: the replay plus the pane's {window:g} s window, not a session"
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


def s_session_load(b):
    """One session's hook cost on the host, no model: the hook events of a session replayed through this clone's own hook
    commands in a throwaway clone (query log in mode `local` under a scratch plugin data directory, a `claude` that fails
    at once), in arm A (every hook), B (A and the commands of the kbmon-pane mod), C (coord_hook.py and the querylog.py
    hooks left out) and D (no hook), each in an idle phase (SessionStart, SessionEnd) and a working phase (the events of
    WORKING between them). Arm B runs, over a window of `b.window` seconds per phase, the pane's commands the mod's way:
    the first after its FIRST_MS and then one every `b.pane_every` seconds (default its REFRESH_MS). Per phase, arm and
    process class: the CPU seconds, peak and mean resident memory in MiB and the starts per minute of a session of
    NOMINAL_S (the pane's own starts per minute of the window); per synchronous hook command its median milliseconds (a
    run of an async hook is `async_ms`: Claude Code does not wait for it). Each rep runs every arm and phase once, the
    medians of the reps are the rows. With `b.capture` (run --fs-usage FILE) it only writes the file reads of that capture;
    otherwise it prints the `sudo fs_usage` command the operator runs by hand, which this tool never runs."""
    if getattr(b, "capture", None):  # --fs-usage FILE: count a capture, start no replay
        return capture_rows(b)
    if not hasattr(os, "wait4"):
        raise Skip("no os.wait4 (Windows): run it on macOS or Linux")
    need_sh()
    print(f"session-load: for the file reads of a session, run `{FS_COMMAND}` by hand beside it (macOS, needs root; stop it with "
          "Ctrl-C), then `python3 _tools/benchmarks.py run session-load --fs-usage fs_usage.txt`", flush=True)
    arms =list(getattr(b, "load_arms", None) or DEFAULT_ARMS)
    clone = b.clone("session-load", "local")
    pin_drift(clone)
    hooks = hook_commands(clone)
    first_s, refresh_s = pane_schedule(clone)
    window = getattr(b, "window", None) or WINDOW_S
    every = getattr(b, "pane_every", None) or refresh_s
    pane = (first_s, every, window)
    replay(b, clone, hooks, "A", "working", "warm")  # the caches of Python, the pack index and git, not measured
    if any(arm in PANE_ARMS for arm in arms):
        warm_pane(b, clone)
    got = {(arm, phase): [] for arm in arms for phase in PHASES}
    for rep in range(max(1, b.reps)):
        for arm in arms:
            for phase in PHASES:
                got[(arm, phase)].append(replay(b, clone, hooks, arm, phase, f"{arm}-{phase}-{rep}", pane))
    seen = [c for c in CLASSES if any(r["classes"].get(c, {}).get(k) for rs in got.values() for r in rs
                                      for k in ("spawns", "pane_spawns"))]
    for (arm, phase), reps in got.items():
        loads = [r["load"] for r in reps]
        med =lambda cls, key: statistics.median(r["classes"].get(cls, {}).get(key, 0.0) for r in reps)  # noqa: E731
        for cls in [*seen, "all"]:
            case = f"{phase} {cls}"
            for metric, key in (("cpu_s", "cpu_s"), ("rss_peak_mb", "peak"), ("rss_mean_mb", "rss_mean_mb")):
                b.row("session-load", case, arm, metric, med(cls, key), len(reps), note=row_note(metric, cls, arm, loads, window))
            rate = statistics.median(r["classes"].get(cls, {}).get("spawns", 0) / (NOMINAL_S[phase] / 60)
                                     + r["classes"].get(cls, {}).get("pane_spawns", 0) / (window / 60) for r in reps)
            b.row("session-load", case, arm, "spawns_per_min", rate, len(reps),
                  note=f"a session of {NOMINAL_S[phase]} s" + (f", the pane's starts per minute of its {window:g} s window"
                                                               if arm in PANE_ARMS else ""))
        if arm in PANE_ARMS:
            b.row("session-load", f"{phase} all", arm, "pane_runs", statistics.median(r["pane_runs"] for r in reps), len(reps),
                  note=f"{PANE_COMMANDS[0][0]} then {' '.join(PANE_COMMANDS[1])}, the first after {first_s:g} s, then every "
                  f"{every:g} s over a window of {window:g} s; a tick that falls during a run does nothing")
        b.row("session-load", f"{phase} replay", arm, "wall_s", statistics.median(r["wall_s"] for r in reps), len(reps))
        b.row("session-load", f"{phase} replay", arm, "hook_failures", statistics.median(len(r["failed"]) for r in reps),
              len(reps), note="hook commands that exited non-zero")
        if arm in PANE_ARMS:
            b.row("session-load", f"{phase} replay", arm, "pane_failures", statistics.median(len(r["pane_failed"]) for r in reps),
                  len(reps), note="pane commands that exited with 2 or more")
    starts = {}
    for (arm, phase), reps in got.items():
        for i, r in enumerate(reps):
            for h in r["hooks"]:
                key = (arm, phase, h["label"])
                starts.setdefault(key, [0] * len(reps))[i] += 1 + len(h["children"])
    for (arm, phase, name), per in starts.items():
        b.row("session-load", f"{phase} hook {name}", arm, "spawns", statistics.median(per), len(per),
              note="the command and the processes Python programs of its tree started, per replay")
    timings = {}
    for (arm, phase), reps in got.items():
        for r in reps:
            for h in r["hooks"]:
                key = (arm, f"{h['event']} {h['label']}" + (f" ({h['tool']})" if h["tool"] else ""), h["async"])
                timings.setdefault(key, []).append(h["wall_s"] * 1000)
    for (arm, case, is_async), ms in timings.items():
        b.row("session-load", case, arm, "async_ms" if is_async else "sync_ms", statistics.median(ms), len(ms))
