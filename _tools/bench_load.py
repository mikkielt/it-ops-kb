"""The benchmarks' session-load scenario: what one Claude Code session of this clone costs the host, measured with no
model (stdlib only).

benchmarks.py registers the scenario in SCENARIOS and holds the command line; the harness is bench_core.py
(kb/_self/code.md, Layout and Imports; the scenario is described in kb/_self/reports/benchmarks.md). It replays the hook
events of one session through the hook commands of the throwaway clone's own .claude/settings.json, started as Claude
Code starts them (`sh -c`, the event as JSON on stdin, CLAUDE_PROJECT_DIR set), and measures every process it starts with
`os.wait4` (CPU and peak memory, which include the children the process waited for) and, for the processes those start,
with a sampler of `ps` (their memory) and a `sitecustomize` audit hook that logs each process a Python program starts
(their number and programs). This module imports no facade; `mon_host` is imported where a process is given its class.
"""
import json, os, re, shutil, statistics, subprocess, sys, threading, time, uuid
from pathlib import Path

from bench_core import Skip, git, need_sh, no_plugin_env, shim_dir

ARMS = ("A", "C", "D")  # A: every hook; C: coord_hook.py and the querylog.py hooks left out; D: no hook
PHASES = ("idle", "working")  # idle: SessionStart then SessionEnd; working: a fixed script of events between them
LEFT_OUT = {"A": (), "C": ("coord_hook.py", "querylog.py"), "D": None}  # a hook command naming one of these is not run
NOMINAL_S = {"idle": 60, "working": 300}  # the seconds of session a replay stands for: the divisor of spawns_per_min
CLASSES = ("kbmon", "fseventsd", "tests", "kb-tools", "claude", "other", "git", "lsof")  # mon_host's, then two more
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


def reset(clone):
    """The clone's working tree as the checkout left it, whatever a replay's hooks wrote, and the intake hook's drift
    cursor removed, so each replay's drift scan starts at the same item instead of where the replay before it stopped."""
    git("checkout", "-q", "--", ".", cwd=clone)
    git("clean", "-fdq", cwd=clone)
    (Path(clone) / git("rev-parse", "--git-path", "kb-intake-drift", cwd=clone)).unlink(missing_ok=True)


class Replay:
    """One replay of a session's events in `clone`: the hook processes it started and the sampler's view of their children."""

    def __init__(self, clone, env, hooks):
        self.clone, self.env, self.hooks = Path(clone), env, hooks
        self.roots, self.threads = [], []  # one dict per hook command run

    def start(self, name, target, payload, command, is_async, sampler):
        cmd = command.replace("${CLAUDE_PROJECT_DIR}", str(self.clone))
        rec = {"event": name, "tool": target if name.endswith("ToolUse") else "", "label": label(command), "async": is_async,
               "class": process_class("sh " + cmd, self.clone)}
        t0 = time.perf_counter()
        p = subprocess.Popen(["sh", "-c", command], cwd=str(self.clone), env=self.env, stdin=subprocess.PIPE,
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
        for name, target, payload in events(phase, self.clone, sid):
            for ev, matcher, is_async, command in self.hooks:
                if ev == name and matches(matcher, target):
                    self.start(name, target, payload, command, is_async, sampler)
        for th in self.threads:
            th.join()
        wall = time.perf_counter() - t0
        sampler.stop.set()
        if self.hooks:
            sampler.join()
        settle(self.clone)
        return self.summary(sampler, wall)

    def started(self):
        """The class of each process a Python program of the replay started (the sitecustomize's log)."""
        log = Path(self.env["BENCH_STARTS_LOG"])
        text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
        return [process_class(" ".join(rec.split("\x1f")), self.clone) for rec in text.split("\x1e") if rec]

    def summary(self, sampler, wall):
        """{class: {cpu_s, spawns, peak, rss_mean_mb}} with `all`, the hook commands' timings and the failed ones. A hook
        command is one start and the processes the Python programs of the tree started the rest; the peak memory is the
        largest of the processes' own peaks and of the sampled sums, the mean the sampled sums' mean."""
        per = {}

        def cell(c):
            return per.setdefault(c, {"cpu_s": 0.0, "spawns": 0, "peak": 0.0, "mean": []})
        for r in self.roots:
            c = cell(r["class"])
            c["cpu_s"] += r["cpu_s"]
            c["spawns"] += 1
            c["peak"] = max(c["peak"], r["maxrss_mb"])
        for cls in self.started():
            cell(cls)["spawns"] += 1
        for cls, kb in sampler.seen.values():
            cell(cls)["peak"] = max(cell(cls)["peak"], kb / 1024)
        for tick in sampler.ticks:
            for cls, kb in tick.items():
                cell(cls)["mean"].append(kb / 1024)
                cell(cls)["peak"] = max(cell(cls)["peak"], kb / 1024)
        per["all"] = {"cpu_s": sum(c["cpu_s"] for c in per.values()), "spawns": sum(c["spawns"] for c in per.values()),
                      "peak": max([r["maxrss_mb"] for r in self.roots] + [sum(t.values()) / 1024 for t in sampler.ticks] + [0.0]),
                      "mean": [sum(t.values()) / 1024 for t in sampler.ticks]}
        for c in per.values():
            if not c["mean"]:  # nothing sampled: the processes' own peaks stand for their size
                c["mean"] = [c["peak"]]
            c["rss_mean_mb"] = statistics.mean(c["mean"])
        return {"classes": per, "wall_s": wall, "hooks": self.roots,
                "failed": [r for r in self.roots if r.get("rc") not in (0, None)]}


def plant(b, clone, name):
    """The scratch directories of one replay: a query log home with mode `local`, a coord store of its own, a `claude`
    that fails at once and the sitecustomize that logs the processes Python starts; the environment the hooks run in
    (CLAUDE_PLUGIN_DATA and CLAUDE_PLUGIN_ROOT both set, else the capture hook writes the real spool)."""
    data = b.scratch / "session-load-data" / name
    shutil.rmtree(data, ignore_errors=True)
    (data / "querylog").mkdir(parents=True)
    (data / "querylog" / "config.json").write_text(json.dumps({"mode": "local", "research": False}) + "\n", encoding="utf-8",
                                                   newline="\n")
    site = b.scratch / "session-load-site"
    site.mkdir(parents=True, exist_ok=True)
    (site / "sitecustomize.py").write_text(SITE, encoding="utf-8", newline="\n")
    fail = shim_dir(b.scratch / "fail-shim")
    path = os.pathsep.join(x for x in (str(site), os.environ.get("PYTHONPATH", "")) if x)
    return no_plugin_env({"CLAUDE_PLUGIN_ROOT": str(clone), "CLAUDE_PLUGIN_DATA": str(data), "CLAUDE_PROJECT_DIR": str(clone),
                          "KB_INDEX": str(clone / "_cache"), "KB_COORD_STORE": str(data / "coord.sqlite"),
                          "BENCH_STARTS_LOG": str(data / "starts.log"), "PYTHONPATH": path,
                          "PATH": f"{fail}{os.pathsep}{os.environ.get('PATH', '')}"})


def replay(b, clone, hooks, arm, phase, name):
    reset(clone)
    env = plant(b, clone, name)
    load = os.getloadavg()[0] if hasattr(os, "getloadavg") else 0.0
    out = Replay(clone, env, arm_hooks(hooks, arm)).run(phase, str(uuid.uuid4()))
    out["load"] = load
    return out


def host_note(loads):
    """What a cpu_s row says of the host: its cores, the 1-minute load at the replays' start and that the caches were warm."""
    return (f"{os.cpu_count()} cores, load {statistics.mean(loads):.1f} (1 min at the start of each rep), warm: one "
            "unmeasured replay first; a hook's tree CPU (os.wait4) is charged to the class of its command")


def s_session_load(b):
    """One session's hook cost on the host, no model: the hook events of a session replayed through this clone's own hook
    commands in a throwaway clone (query log in mode `local` under a scratch plugin data directory, a `claude` that fails
    at once), in arm A (every hook), C (coord_hook.py and the querylog.py hooks left out) and D (no hook), each in an idle
    phase (SessionStart, SessionEnd) and a working phase (the events of WORKING between them). Per phase, arm and process
    class: the CPU seconds, peak and mean resident memory in MiB and the starts per minute of a session of NOMINAL_S; per
    synchronous hook command its median milliseconds (a run of an async hook is `async_ms`: Claude Code does not wait for
    it). Each rep runs every arm and phase once, the medians of the reps are the rows."""
    if not hasattr(os, "wait4"):
        raise Skip("no os.wait4 (Windows): run it on macOS or Linux")
    need_sh()
    arms = list(getattr(b, "load_arms", None) or ARMS)
    clone = b.clone("session-load", "local")
    hooks = hook_commands(clone)
    replay(b, clone, hooks, "A", "working", "warm")  # the caches of Python, the pack index and git, not measured
    got = {(arm, phase): [] for arm in arms for phase in PHASES}
    for rep in range(max(1, b.reps)):
        for arm in arms:
            for phase in PHASES:
                got[(arm, phase)].append(replay(b, clone, hooks, arm, phase, f"{arm}-{phase}-{rep}"))
    seen = [c for c in CLASSES if any(r["classes"].get(c, {}).get("spawns") for rs in got.values() for r in rs)]
    for (arm, phase), reps in got.items():
        note = host_note([r["load"] for r in reps])
        med = lambda cls, key: statistics.median(r["classes"].get(cls, {}).get(key, 0.0) for r in reps)  # noqa: E731
        for cls in [*seen, "all"]:
            case = f"{phase} {cls}"
            b.row("session-load", case, arm, "cpu_s", med(cls, "cpu_s"), len(reps), note=note)
            b.row("session-load", case, arm, "rss_peak_mb", med(cls, "peak"), len(reps))
            b.row("session-load", case, arm, "rss_mean_mb", med(cls, "rss_mean_mb"), len(reps))
            b.row("session-load", case, arm, "spawns_per_min", med(cls, "spawns") / (NOMINAL_S[phase] / 60), len(reps),
                  note=f"a session of {NOMINAL_S[phase]} s")
        b.row("session-load", f"{phase} replay", arm, "wall_s", statistics.median(r["wall_s"] for r in reps), len(reps))
        b.row("session-load", f"{phase} replay", arm, "hook_failures", statistics.median(len(r["failed"]) for r in reps),
              len(reps), note="hook commands that exited non-zero")
    timings = {}
    for (arm, phase), reps in got.items():
        for r in reps:
            for h in r["hooks"]:
                key = (arm, f"{h['event']} {h['label']}" + (f" ({h['tool']})" if h["tool"] else ""), h["async"])
                timings.setdefault(key, []).append(h["wall_s"] * 1000)
    for (arm, case, is_async), ms in timings.items():
        b.row("session-load", case, arm, "async_ms" if is_async else "sync_ms", statistics.median(ms), len(ms))
