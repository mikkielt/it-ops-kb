"""The autopilot's rehearsal (kb/_self/tools.md, The autopilot runner; kb/_self/backlog.md, Starting the autopilot):
one manager tick end to end in a throwaway clone, with a stubbed `claude`, so the operator sees the autopilot work
before it is started for real.

  autopilot_rehearse.py [--keep]    clone this repository's HEAD into a temporary directory (a bare repository there
                                    stands in for origin, so no real remote is reached), file a scratch planned sprint
                                    of two trivial items beside its goal research story, and run the tick's steps on it,
                                    one line each:

    clone        the bare origin and the clone, with a git environment of their own (no host config; the clone's own commit hooks, as `kbgit.py install-hooks` sets them)
    file-sprint  `new sprint`, two stories whose knowledge refs read sufficient, pushed
    selfcheck    `backlog.py selfcheck` passes in the clone
    research     the goal research story claimed, worked and done
    start-gate   the start gate answered `--by autopilot --record`
    start        `backlog.py start --commit` through that gate, pushed
    runner       `autopilot.py runner start SP`, with a stub `claude` first on PATH that claims, commits and `done`s each
                 ready item as a runner does, ending `sprint-runner: sprint-done`
    landed       `runner-status SP` names both items and the clone's backlog has both done
    bounds-stop  `backlog.py bounds stop --sprint SP` exits 1 with the cause `no-ready`
    digest       `kbdecide.py digest` writes the digest
    cleanup      no process of the clone and no runner record is left, the runner's worktree is removed and `git worktree
                 list` names the clone alone

  The tools it runs are the clone's own copy, at this repository's HEAD: a change not committed is not rehearsed. Every
  runner, git and backlog command of a step is bounded by STEP_TIMEOUT seconds (a hung step fails, its processes
  ended). The temporary directory and every process of the rehearsal are removed on success, on any failure and on
  SIGINT or SIGTERM; --keep leaves the directory (a test inspects it, then removes it). The host's runner records and
  locks are never touched: the clone's commands get a host lock directory of their own.

  Environment, for tests: KB_REHEARSE_STEP_TIMEOUT (seconds, a step's bound), KB_REHEARSE_STUB_PAUSE (seconds the stub
  waits before it works, default 0), KB_REHEARSE_FAIL=STEP (a planted fault: that step fails before it runs),
  A stub that waits longer than the bound (KB_REHEARSE_STUB_PAUSE above KB_REHEARSE_STEP_TIMEOUT) is the hung step.

Exit codes: 0 `rehearse: ok (N steps)`; 1 `rehearse: FAILED at step NAME: CAUSE` (the step, a bound, a signal); 2 bad
arguments. Standard library only.
"""
import argparse, contextlib, json, os, re, shlex, shutil, signal, stat, subprocess, sys, tempfile, time
from pathlib import Path

import kbpublic

ROOT = Path(__file__).resolve().parent.parent
STEP_TIMEOUT = 300  # seconds one command of a step may run before the step fails
TIMEOUT_ENV, PAUSE_ENV, FAIL_ENV = "KB_REHEARSE_STEP_TIMEOUT", "KB_REHEARSE_STUB_PAUSE", "KB_REHEARSE_FAIL"
STEPS = ("clone", "file-sprint", "selfcheck", "research", "start-gate", "start", "runner", "landed", "bounds-stop",
         "digest", "cleanup")
SCRATCH = "_rehearsal"  # the directory of the clone the scratch items write into
ITEMS = ("a", "b")
REFS = ("agents/agent-planning-and-done", "S-2wwcyoa4")  # kb references tried in turn: the first one that reads sufficient
GAP_ENTRY = ("\n## rehearsal\n\n- **Rehearsal note: the scratch sprint has no open question.** Nothing was researched; this entry "
             "gives the research story kb content to land. [UNK] (topic: agents/agent-planning-and-done)\n")
ENV_DROP = ("GIT_DIR", "GIT_WORK_TREE", "GIT_IMPLICIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY",
            "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_PREFIX", "CLAUDE_PROJECT_DIR", "KB_VERIFIED", "KB_TESTS_FAST",
            "KB_HEADLESS_RUNNER")
GRACE_S = 5  # seconds a signalled child gets before its process group is killed

# The stub `claude`: what a headless runner's run does for a sprint, in the shell of the runner's worktree. It claims each
# ready item, commits its file with `KB-Work`, pushes, marks it done and pushes again, then prints its final result.
STUB = '''import json, os, re, subprocess, sys, time
sprint = re.search(r"SP-[a-z2-7]{8}", " ".join(sys.argv)).group(0)
BL = [sys.executable, os.path.join("_tools", "backlog.py")]


def run(*argv):
    p = subprocess.run(list(argv), capture_output=True, text=True, encoding="utf-8")
    if p.returncode:
        sys.stdout.write(json.dumps({"type": "result", "subtype": "error_during_execution", "is_error": True,
                                     "result": " ".join(argv[-3:]) + ": " + (p.stdout + p.stderr).strip()[-300:]}) + "\\n")
        sys.exit(1)
    return p.stdout


print(json.dumps({"type": "system", "subtype": "init"}), flush=True)
time.sleep(float(os.environ.get("KB_REHEARSE_STUB_PAUSE") or 0))
run("git", "fetch", "origin")
ready = re.findall(r"\\bST-[a-z2-7]{8}\\b", run(*BL, "next", "--sprint", sprint, "--all"))
items = {i: json.load(open(os.path.join("kb", "_self", "backlog", i + ".json"), encoding="utf-8")) for i in set(ready)}
done = []
for iid in (i for i in dict.fromkeys(ready) if not items[i].get("review")):  # the review story is the manager's
    path = items[iid]["touches"][0]
    run(*BL, "claim", iid, "--by", "runner-" + sprint + "-" + iid, "--commit")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8", newline="\\n").write("scratch work of " + iid + "\\n")
    run("git", "add", path)
    run("git", "commit", "-q", "-m", "feat(rehearsal): write " + path, "-m", "KB-Work: " + iid)
    run("git", "push", "-q", "--no-verify", "origin", "HEAD:main")
    run(*BL, "done", iid, "--commit")
    run("git", "push", "-q", "--no-verify", "origin", "HEAD:main")
    done.append(iid)
    print(json.dumps({"type": "assistant", "message": "landed " + iid}), flush=True)
print(json.dumps({"type": "result", "subtype": "success", "is_error": False,
                  "result": "landed " + ", ".join(done) + "\\nsprint-runner: sprint-done"}), flush=True)
'''


class Failed(Exception):
    """A step that did not do what it must: the message is its cause."""


class Interrupted(Exception):
    """SIGINT or SIGTERM reached the rehearsal; the message names the signal."""


def one_line(text, n=200):
    return " ".join(str(text).split())[:n]


def step_timeout():
    try:
        return max(float(os.environ.get(TIMEOUT_ENV) or STEP_TIMEOUT), 0.1)
    except ValueError:
        return float(STEP_TIMEOUT)


class Rehearsal:
    def __init__(self, keep=False):
        self.keep = keep
        self.tmp = None
        self.env = None
        self.runner = None  # the Popen of `autopilot.py runner start`
        self.sprint = None
        self.items = []
        self.research = None
        self.say = print

    # ---------------------------------------------------------------- commands

    @property
    def bare(self):
        return self.tmp / "origin.git"

    @property
    def clone(self):
        return self.tmp / "clone"

    def build_env(self):
        env = {k: v for k, v in os.environ.items() if k not in ENV_DROP}
        stub = self.tmp / "bin"
        env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
                    "GIT_AUTHOR_NAME": "rehearsal", "GIT_AUTHOR_EMAIL": "rehearsal@example.com",
                    "GIT_COMMITTER_NAME": "rehearsal", "GIT_COMMITTER_EMAIL": "rehearsal@example.com",
                    "KB_HOST_LOCK_DIR": str(self.tmp / "hostlocks"), "PATH": str(stub) + os.pathsep + env.get("PATH", ""),
                    "PYTHONDONTWRITEBYTECODE": "1", "GIT_CONFIG_COUNT": "2", "GIT_CONFIG_KEY_0": "gc.auto",
                    "GIT_CONFIG_VALUE_0": "0", "GIT_CONFIG_KEY_1": "maintenance.auto", "GIT_CONFIG_VALUE_1": "false"})
        return env

    def run(self, argv, cwd=None, ok=(0,)):
        """(exit code, output) of ARGV, which must exit with a code in OK: else Failed with the command and its last
        output. Bounded by the step timeout; a command that outlives it has its process group ended."""
        argv = [str(a) for a in argv]
        code, out = self.capture(argv, cwd or self.clone)
        if code not in ok:
            raise Failed(f"{one_line(' '.join(shlex.quote(Path(a).name if os.sep in a else a) for a in argv[:4]), 80)} "
                         f"exited {code}: {one_line(out[-400:])}")
        return code, out

    def capture(self, argv, cwd):
        group = {"start_new_session": True} if os.name == "posix" else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        try:
            proc = subprocess.Popen(argv, cwd=str(cwd), env=self.env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", **group)
        except OSError as e:
            raise Failed(f"cannot start {argv[0]}: {e}")
        try:
            out, _ = proc.communicate(timeout=step_timeout())
        except subprocess.TimeoutExpired:
            end_group(proc)
            raise Failed(f"{Path(argv[0]).name} {' '.join(Path(a).name for a in argv[1:3])} ran past the step bound of "
                         f"{step_timeout():g}s")
        except BaseException:
            end_group(proc)
            raise
        return proc.returncode, out

    def git(self, *args, cwd=None):
        return self.run(["git", *args], cwd)[1]

    def backlog(self, *args, ok=(0,)):
        return self.run([sys.executable, self.clone / "_tools" / "backlog.py", *args], ok=ok)

    def tool(self, name, *args, ok=(0,)):
        return self.run([sys.executable, self.clone / "_tools" / name, *args], ok=ok)

    def item_files(self):
        return sorted((self.clone / "kb" / "_self" / "backlog").glob("*.json"))

    def item(self, iid):
        return json.loads((self.clone / "kb" / "_self" / "backlog" / f"{iid}.json").read_text(encoding="utf-8"))

    def find(self, title):
        for f in self.item_files():
            it = json.loads(f.read_text(encoding="utf-8"))
            if it.get("title") == title:
                return it["id"]
        raise Failed(f"no item titled {title!r} in the clone's backlog")

    @property
    def remote(self):
        """The clone's integration remote, asked of kbpublic and never named here."""
        return kbpublic.integration_remote(str(self.clone))

    def push(self):
        self.git("push", "-q", "--no-verify", self.remote, "HEAD:main")  # sync's own push, whose gate is not what is rehearsed

    # ---------------------------------------------------------------- the steps

    def step_clone(self):
        self.env = self.build_env()
        (self.tmp / "hostlocks").mkdir()
        sha = self.git("rev-parse", "HEAD", cwd=ROOT).strip()
        self.run(["git", "init", "-q", "--bare", "-b", "main", self.bare], cwd=self.tmp)
        self.git("fetch", "-q", str(ROOT), f"{sha}:refs/heads/main", cwd=self.bare)
        self.run(["git", "clone", "-q", self.bare, self.clone], cwd=self.tmp)
        self.git("config", "core.hooksPath", ".githooks", cwd=self.clone)  # as `kbgit.py install-hooks` sets it
        # an empty backlog: the real one's claimed or stalled items would fail the rehearsal's own selfcheck, whatever
        # state the repository is in when an operator runs it
        self.git("rm", "-q", "-r", "kb/_self/backlog", cwd=self.clone)
        self.git("commit", "-q", "--no-verify", "-m", "chore(backlog): an empty backlog for the rehearsal", cwd=self.clone)
        self.git("push", "-q", self.remote, "main", cwd=self.clone)
        (self.clone / "kb" / "_self" / "backlog").mkdir(parents=True, exist_ok=True)
        bindir = self.tmp / "bin"
        bindir.mkdir()
        (bindir / "claude_stub.py").write_text(STUB, encoding="utf-8", newline="\n")
        if os.name == "posix":
            wrapper = bindir / "claude"
            wrapper.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(bindir / "claude_stub.py"))} "$@"\n',
                               encoding="utf-8", newline="\n")
            wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        else:
            (bindir / "claude.cmd").write_text(f'@"{sys.executable}" "{bindir / "claude_stub.py"}" %*\r\n', encoding="utf-8",
                                               newline="")
        return f"origin {self.bare.name} at {sha[:10]}, clone {self.clone.name}"

    def sufficient(self, ids, ref):
        """Whether `show` reads every item of IDS' knowledge as sufficient with REF."""
        for iid in ids:
            path = self.clone / "kb" / "_self" / "backlog" / f"{iid}.json"
            it = json.loads(path.read_text(encoding="utf-8"))
            it["knowledge"] = {"refs": [ref]}
            path.write_text(json.dumps(it, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        self.backlog("fmt")
        states = [x for iid in ids for x in re.findall(r"knowledge (\w+)\s+ref:", self.backlog("show", iid)[1])]
        return len(states) == len(ids) and set(states) == {"sufficient"}

    def step_file_sprint(self):
        self.backlog("new", "sprint", "--title", "Rehearsal sprint", "--goal",
                     "both scratch items of the rehearsal land")
        self.sprint = self.find("Rehearsal sprint")
        self.research = self.find("Research sprint goal: Rehearsal sprint")
        # `python3`, never sys.executable: its path may hold this host's user name, which `check` refuses in an item
        check = shlex.join(["python3", "-c", "import pathlib, sys; sys.exit(not pathlib.Path(sys.argv[1]).is_file())"])
        for n in ITEMS:
            f = f"{SCRATCH}/{n}.txt"
            self.backlog("new", "story", "--title", f"Rehearsal item {n}", "--sprint", self.sprint, "--priority", "P1",
                         "--goal", f"{f} exists", "--touch", f, "--check", f"{check} {f}")
            self.items.append(self.find(f"Rehearsal item {n}"))
        for ref in REFS:
            if self.sufficient(self.items, ref):
                break
        else:
            raise Failed("no knowledge ref of this repository reads sufficient for the scratch items "
                         f"(tried {', '.join(REFS)}): the start check would refuse them")
        self.backlog("check")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "chore(backlog): file the rehearsal sprint")
        self.push()
        return f"{self.sprint} with {', '.join(self.items)}; knowledge ref {ref} sufficient"

    def step_selfcheck(self):
        """The clone's selfcheck must pass; a host that is merely busy (the `host` check on the real load average, the one
        input the rehearsal cannot set) is named and not held against the tick: the rehearsal's subject is the tick."""
        code, out = self.backlog("selfcheck", ok=(0, 1))
        first = one_line(out.splitlines()[0] if out.strip() else "selfcheck printed nothing", 120)
        if code == 0:
            return first
        failed = re.findall(r"^FAIL (\S+?):", out, re.M)
        if failed and set(failed) == {"host"}:
            return f"{first}; only the host check failed (the host is busy), run again when it is idle for a clean one"
        raise Failed(f"python3 backlog.py selfcheck exited {code}: {one_line(out, 300)}")

    def step_research(self):
        rs, gaps = self.research, "kb/public/_gaps.md"
        self.backlog("claim", rs, "--by", "rehearsal-manager", "--commit")
        with (self.clone / gaps).open("a", encoding="utf-8", newline="\n") as f:  # the research story writes kb content
            f.write(GAP_ENTRY)
        self.git("add", gaps)
        self.git("commit", "-q", "-m", "docs(kb): note that the rehearsal sprint has no open question", "-m", f"KB-Work: {rs}")
        self.push()
        self.backlog("done", rs, "--commit")
        self.push()
        return f"{rs} done"

    def step_start_gate(self):
        self.backlog("answer", self.sprint, "start", "--answer", "approve", "--by", "autopilot", "--record")
        g = next(g for g in self.item(self.sprint)["gates"] if g["id"] == "start")
        if g.get("by") != "autopilot" or g.get("answer") != "approve":
            raise Failed(f"the start gate reads {g.get('by')}/{g.get('answer')}, not autopilot/approve")
        return f"{self.sprint} gate start approve by autopilot"

    def step_start(self):
        out = self.backlog("start", self.sprint, "--commit")[1]
        self.push()
        if self.item(self.sprint)["status"] != "active":
            raise Failed(f"{self.sprint} is {self.item(self.sprint)['status']} after start")
        return one_line(out.splitlines()[0], 120)

    def step_runner(self):
        argv = [sys.executable, str(self.clone / "_tools" / "autopilot.py"), "runner", "start", self.sprint]
        env = {**self.env, PAUSE_ENV: os.environ.get(PAUSE_ENV, "0")}
        group = {"start_new_session": True} if os.name == "posix" else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        self.runner = subprocess.Popen(argv, cwd=str(self.clone), env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", **group)
        try:
            out, _ = self.runner.communicate(timeout=step_timeout())
        except subprocess.TimeoutExpired:
            end_group(self.runner)
            raise Failed(f"the runner ran past the step bound of {step_timeout():g}s")
        code = self.runner.returncode
        status = self.clone / "_cache" / "autopilot" / self.sprint / "status.json"
        cause = json.loads(status.read_text(encoding="utf-8")).get("cause") if status.is_file() else "no status.json"
        if code != 0 or cause != "sprint-done":
            raise Failed(f"the runner exited {code} with cause {cause}: {one_line(out[-300:])}")
        return f"runner ended {cause}"

    def step_landed(self):
        self.git("fetch", "-q", self.remote)
        self.git("merge", "-q", "--ff-only", f"{self.remote}/main")
        report = self.tool("autopilot.py", "runner-status", self.sprint)[1]
        for iid in self.items:
            if iid not in report:
                raise Failed(f"runner-status does not name {iid} as landed: {one_line(report, 200)}")
            if self.item(iid)["status"] != "done":
                raise Failed(f"{iid} is {self.item(iid)['status']} in the clone after the run")
        return f"{len(self.items)} items landed, both done"

    def step_bounds_stop(self):
        code, out = self.backlog("bounds", "stop", "--sprint", self.sprint, ok=(1,))
        first = out.strip().splitlines()[0] if out.strip() else ""
        if "stop no-ready" not in first:
            raise Failed(f"bounds stop did not stop on no-ready: {one_line(out, 200)}")
        return first

    def step_digest(self):
        out = self.tool("kbdecide.py", "digest")[1]
        digest = self.clone / "kb" / "_self" / "reports" / "autopilot-digest.md"
        if not digest.is_file() or "# Autopilot digest" not in digest.read_text(encoding="utf-8"):
            raise Failed("the digest file is missing or has no heading")
        return "autopilot-digest.md written, " + one_line(out.strip().split("\t")[1], 40)

    def step_cleanup(self):
        if self.runner is not None and self.runner.poll() is None:
            raise Failed("the runner process is still running")
        procs = self.tool("backlog.py", "procs")[1].strip()  # what runs on with a working directory in the clone or its worktrees
        found = re.match(r"procs: (\d+) process", procs)
        if "cannot list processes" in procs:  # a host that shows no working directories (Windows): the runner's exit is the proof
            pass
        elif not found or int(found.group(1)):
            raise Failed(f"a process of the clone is left: {one_line(procs, 300)}")
        wt = self.clone / ".claude" / "worktrees" / f"runner-{self.sprint}"
        if wt.exists():
            self.git("worktree", "remove", "--force", str(wt))
        self.git("worktree", "prune")
        trees = [ln for ln in self.git("worktree", "list", "--porcelain").splitlines() if ln.startswith("worktree ")]
        if len(trees) != 1:
            raise Failed(f"git worktree list names {len(trees)} worktrees after cleanup: {one_line(' '.join(trees), 200)}")
        left = [p.name for p in (self.tmp / "hostlocks").glob("*.json")]
        if left:
            raise Failed(f"runner records are left in the host lock directory: {', '.join(left)}")
        return "no process of the clone, the runner's worktree removed, one worktree listed"

    # ---------------------------------------------------------------- the run

    def execute(self, name):
        if os.environ.get(FAIL_ENV) == name:
            raise Failed("planted failure")
        return getattr(self, "step_" + name.replace("-", "_"))()

    def teardown(self):
        """Every process of the rehearsal ended, the clone's worktrees detached, the directory removed (kept with --keep)."""
        if self.runner is not None and self.runner.poll() is None:
            end_group(self.runner)
        if self.tmp is None:
            return
        if not self.keep:
            for path in sorted(self.tmp.glob("clone/.claude/worktrees/*")):
                with contextlib.suppress(Exception):
                    subprocess.run(["git", "worktree", "remove", "--force", str(path)], cwd=self.clone, env=self.env,
                                   capture_output=True, timeout=30)
            shutil.rmtree(self.tmp, ignore_errors=True)
            if self.tmp.exists():  # a file a dying process still held: once more after a moment
                time.sleep(0.5)
                shutil.rmtree(self.tmp, ignore_errors=True)

    def main(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-rehearse-")).resolve()
        done, name = 0, STEPS[0]
        try:
            with signals():
                self.say(f"rehearse: workdir {self.tmp}", flush=True)
                for name in STEPS:
                    detail = self.execute(name)
                    done += 1
                    self.say(f"rehearse: step {name}: {detail}", flush=True)
        except (Failed, Interrupted) as e:
            self.teardown()
            self.say(f"rehearse: FAILED at step {name}: {one_line(e, 400)}", flush=True)
            return 1
        except BaseException:
            self.teardown()
            raise
        self.teardown()
        self.say(f"rehearse: ok ({done} steps)", flush=True)
        return 0


def end_group(proc):
    """End PROC's process group (the command and what it started): terminate, a grace, then kill."""
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM) if os.name == "posix" else proc.terminate()
    except OSError:
        pass
    try:
        proc.wait(GRACE_S)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL) if os.name == "posix" else proc.kill()
        except OSError:
            pass
        proc.wait()


@contextlib.contextmanager
def signals():
    """Within the block SIGINT and SIGTERM raise Interrupted, so the rehearsal ends its processes and removes its
    directory; the previous handlers come back. Outside the main thread nothing is installed."""
    names = [n for n in ("SIGINT", "SIGTERM") if hasattr(signal, n)]
    old = {}

    def handler(signum, frame):
        raise Interrupted(f"interrupted by {signal.Signals(signum).name}")

    try:
        for n in names:
            old[n] = signal.signal(getattr(signal, n), handler)
    except ValueError:
        pass
    try:
        yield
    finally:
        for n, prev in old.items():
            signal.signal(getattr(signal, n), prev if prev is not None else signal.SIG_DFL)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--keep", action="store_true", help="leave the temporary directory (a test inspects it)")
    a = ap.parse_args(argv)
    return Rehearsal(keep=a.keep).main()


if __name__ == "__main__":
    sys.exit(main())
