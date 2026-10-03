"""The autopilot's sprint runner (kb/_self/tools.md, The autopilot runner): one headless `claude -p` run of
`/kb-sprint run SP --headless` in a worktree of its own, with its stream kept and its end recorded, and a short
report of what the run did.

  autopilot.py runner start SP [--landed K]   make or reuse the worktree .claude/worktrees/runner-SP on the branch
                                              orch/SP (a clean one is brought to origin/main by a fast-forward; one
                                              with uncommitted files is refused, naming them) and run the sprint
                                              there. The worktree's own .claude/settings.json is passed by
                                              --settings and each plugin the project loads by --plugin-dir; no
                                              --permission-mode and no --dangerously-skip-permissions, so the
                                              project's allow and deny rules govern the run, with RUNNER_DENY added
                                              by --disallowedTools (no answer recorded as the operator's) and
                                              KB_HEADLESS_RUNNER set (no publish). Every line of the stream is
                                              written, as it arrives, to _cache/autopilot/SP/<UTC stamp>.jsonl. The
                                              runner ends the child at the first system compact_boundary event, and
                                              records the end in _cache/autopilot/SP/status.json with the start ref.
                                              The child is bounded: --max-turns MAX_TURNS in its command and a
                                              wall-clock deadline DEADLINE_S from its start, past which the runner
                                              ends its process tree and records the cause `timeout`; the
                                              environment variables KB_RUNNER_MAX_TURNS and KB_RUNNER_DEADLINE_S
                                              replace the two (a value that is not a positive number is ignored).
                                              Each run's end also adds one line to _cache/autopilot/SP/runs.jsonl
                                              (`{"sprint", "cause", "landed", "time"}`, one append), the history
                                              `backlog.py bounds stop` reads for no-progress.
  autopilot.py runner reset SP                free the worktree a refused start names: refused while a live runner holds SP;
                                              a worktree with uncommitted files has them kept in a git stash of the clone
                                              (`autopilot reset SP STAMP`), one whose branch diverged from the integration
                                              main has the branch kept as `stale/SP-STAMP` and the worktree removed, so
                                              the next `runner start` makes it afresh at origin/main; one that is clean and
                                              not diverged is left alone. It names the cause either way.
  autopilot.py runner-status SP               print, in under 1000 characters, the sprint's items the run landed (done
                                              commits with KB-Work since the start ref), the gates it added or left
                                              open on them, the bugs filed since the start ref and the exit cause

Exit cause (status.json `cause`): `compaction` (the child was ended at its first compact_boundary), else read from the
run's own final result and the child's exit code: `timeout` (the child was ended at its deadline), `error` (the child
could not start, no result, an error result, which a run past its turn limit gives, a non-zero exit, or a result that
names no cause), else the cause the result's last `sprint-runner: <cause>` line names: `landed-limit` (K
items landed), `sprint-done` (nothing ready is left) or `blocked` (what is ready waits on a gate or trigger). While the
run lives the cause is `running`. A runner that gets SIGTERM or SIGHUP (`backlog.py procs --end`, its manager's exit)
ends the child's process tree and writes `error` with the signal's name as the detail, also before the child runs, over the previous run's status.json.

At most bl_base.MAX_RUNNERS runners live on a host, whatever their clone. Each records itself while it runs in the host
lock directory (`kb-runner.<pid>.json`: pid, sprint, clone, start time and the touches of the sprint's open items), and
status.json carries the same pid, the run's start, its deadline and its turn limit. A third `runner start` is refused naming the two, a start of a sprint a live runner
holds is refused, and so is one whose committed touches overlap those of another sprint's runner, naming the globs and
the holder (the same check `backlog.py start` makes). A record whose process is gone is ignored and removed.

Exit codes: `runner start` 0 the run ended with a named cause other than `error` and `timeout`, 1 it ended in one of
those two, or it was refused as operator-present only (a not-done item of the sprint touches files that
`kb_hook.headless_guard` denies a headless run, `bl_authority.guarded_touches`; no worktree, no child), 2 refused (a
bad sprint id, no git clone, a dirty or diverged worktree, no settings file, two runners already live, a sprint held by
a runner, touches that overlap another runner's); `runner reset` 0 reset or nothing to reset, 2 refused (a bad sprint
id, a live runner holds the sprint, git failed); `runner-status` 0 printed, 1 no run was recorded for the sprint, 2 a bad
sprint id. `runner-status` and `status` show a run's age (`age 2h05m`, from the child's start; `ran ...` once it ended)
and mark a run still `running` past its deadline `stalled`. Standard library only.

  autopilot.py status [--hook]                the manager's state in one capped command: runners (live records of the host
                                              lock directory, and the cause of each ended run's status.json; a status.json that says `running` while no live
                                              runner holds the sprint is listed as `ended error`), each active
                                              sprint (done of all, reachable, next item), the operator's open blocking
                                              gates, the autopilot's active decisions the operator has not ratified, and the
                                              last tick's actions. Each section prints a count and its first entries; a
                                              section with nothing prints nothing. --hook prints the same under 1000
                                              characters (cut with `...`), reads only, always exits 0, and prints the one
                                              line `autopilot status unavailable` when anything fails.
  The last tick is read from _cache/autopilot/state.json, `{"tick": N, "actions": [str or {"action"|"text": str}]}`, else
  from the last line of _cache/autopilot/ticks.jsonl of the same shape; a missing, corrupt or differently shaped file
  is not an error and prints nothing.
  autopilot.py precompact                     the PreCompact hook: reads the hook's JSON on stdin and exits 2, naming
                                              the holder and its step on stderr, while a live process of this clone
                                              (CLAUDE_PROJECT_DIR, else the repository) holds the host main lock
                                              (kg_lock: land's fetch and rebase, sync --push); 0 when the lock is
                                              free, its holder's pid is gone, the holder is another clone's, or
                                              anything fails, so a session is never kept from compacting past that step.
  .claude/settings.json runs `status --hook` on SessionStart with the `compact` matcher and `precompact` on PreCompact.
"""
import argparse, contextlib, datetime, json, os, re, signal, subprocess, sys, threading
from pathlib import Path

import bl_base
import bl_plan
import kbpublic
from bl_intake import end_tree

ROOT = Path(__file__).resolve().parent.parent
CLAUDE = ["claude"]  # the command that starts Claude Code; a test replaces it with a fake
# The prompt the runner sends. The skill's headless path (.claude/skills/kb-sprint/SKILL.md) reads this string:
# `{sprint}` is the sprint id, `{landed}` is LANDED_FLAG with K, or empty when `--landed` was not given.
PROMPT = "/kb-sprint run {sprint} --headless{landed}"
LANDED_FLAG = " --landed {k}"
# The last line of the run's final result names why the run ended, one of CAUSES_FROM_RESULT.
CAUSE_MARKER = "sprint-runner: {cause}"
# A second layer, not the guard: a deny rule matches text, so it misses an argument order (`answer --by operator ID ...`)
# and an option abbreviation (`--b operator`). The guard is `backlog.py answer` and `kbdecide.py` themselves, which refuse
# the operator's acts whenever HEADLESS_ENV is set, whatever the text. The project's settings leave the answers to the
# operator-present manager session, which has the variable unset.
RUNNER_DENY = tuple(f"{shell}(python3 _tools/backlog.py answer * {by}*)" for shell in ("Bash", "PowerShell")
                    for by in ("--by operator", "--by=operator"))
HEADLESS_ENV = kbpublic.HEADLESS_ENV  # set in the run's environment, so its session's publish --hook pushes nothing
RUNNER_SPRINT_ENV = "KB_RUNNER_SPRINT"  # the sprint the run works: backlog.py merge (bl_land) merges only its items
# The child's environment holds no way to authenticate to a git host, an agent or a registry: child_env drops these
# names and any name CREDENTIAL_RE matches, so code the child runs cannot push or publish with the operator's session.
CREDENTIAL_NAMES = frozenset({"SSH_AUTH_SOCK", "SSH_AGENT_PID", "GIT_ASKPASS", "SSH_ASKPASS", "SSH_ASKPASS_REQUIRE",
                              "GITLAB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN", "GLAB_TOKEN", "GITLAB_ACCESS_TOKEN",
                              "CI_JOB_TOKEN", "NPM_TOKEN"})
CREDENTIAL_PREFIXES = ("PYPI_", "TWINE_")
CREDENTIAL_RE = re.compile(r"(?i)(token|secret|password|passwd|credential|api[_-]?key|private[_-]?key)")
# Kept although CREDENTIAL_RE matches (CLAUDE_CODE_OAUTH_TOKEN, ANTHROPIC_API_KEY): the claude child needs them to
# authenticate to the model, and without them the headless run cannot start.
MODEL_AUTH_PREFIXES = ("CLAUDE_", "ANTHROPIC_")
NO_PUSH_URL = "file:///dev/null/no-push-from-a-runner"  # the pushurl of the public remote in the runner's worktree
CAUSES_FROM_RESULT = ("landed-limit", "sprint-done", "blocked")
CAUSE_LINE = re.compile(r"^sprint-runner: (" + "|".join(CAUSES_FROM_RESULT) + r")[ \t]*$", re.M)
SPRINT_ID = re.compile(r"^SP-[a-z2-7]{8}$")
STATUS_MAX = 1000  # runner-status prints fewer characters than this
GRACE_S = 5  # seconds a child gets to end after SIGTERM before its process group is killed
TIMER = threading.Timer  # the deadline's timer class; a test replaces it to watch only the timers its own run started
TIMER_JOIN_S = GRACE_S + 5  # supervise waits this long for its cancelled deadline timer's thread to end
MAX_TURNS = 500  # --max-turns of the headless child: a loop guard well above what a run takes before its first compaction
DEADLINE_S = 6 * 3600  # seconds a child lives at most; past it the runner ends its process tree (cause `timeout`)
TURNS_ENV = "KB_RUNNER_MAX_TURNS"  # environment overrides of the two bounds, for tests and a host that wants other ones
DEADLINE_ENV = "KB_RUNNER_DEADLINE_S"
FAIL_CAUSES = ("error", "timeout")  # the causes `runner start` exits 1 for
DETAIL_CHARS = 120
DIRTY_FILES = 8  # files a dirty-worktree refusal names
RUNS_FILE = bl_base.RUNS_FILE  # the sprint's history of ended runs in its cache directory (bl_base.append_run)
DONE_SUBJECT = "chore(backlog): done "
KB_WORK = re.compile(r"^KB-Work: (.+)$", re.M)


# ---------------------------------------------------------------- paths and the status file

def cache_dir(root, sprint):
    return Path(root) / "_cache" / "autopilot" / sprint


def worktree_path(root, sprint):
    return Path(root) / ".claude" / "worktrees" / f"runner-{sprint}"


def branch_name(sprint):
    return f"orch/{sprint}"


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def write_status(path, data):
    """status.json written whole or not at all: a reader (runner-status) never sees half of it."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def read_status(root, sprint):
    try:
        data = json.loads((cache_dir(root, sprint) / "status.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def open_stream(directory, stamp):
    """The stream file of this run, `<stamp>.jsonl`, created new (a second run in the same second gets `-2`, ...)."""
    n = 1
    while True:
        name = f"{stamp}.jsonl" if n == 1 else f"{stamp}-{n}.jsonl"
        try:
            return name, open(directory / name, "x", encoding="utf-8", newline="\n")
        except FileExistsError:
            n += 1


# ---------------------------------------------------------------- the worktree

def git_ok(repo, *args):
    """True when `git ARGS` in REPO exits 0 (an ancestor test), whatever it prints."""
    return subprocess.run(["git", *args], cwd=repo, capture_output=True).returncode == 0


def child_env(environ=None):
    """The environment of the claude child: ENVIRON (the runner's own when None) without CREDENTIAL_NAMES, the
    CREDENTIAL_PREFIXES and any name CREDENTIAL_RE matches, except the MODEL_AUTH_PREFIXES; GIT_TERMINAL_PROMPT=0
    and HEADLESS_ENV set."""
    env = {k: v for k, v in (os.environ if environ is None else environ).items()
           if k.startswith(MODEL_AUTH_PREFIXES)
           or not (k.upper() in CREDENTIAL_NAMES or k.upper().startswith(CREDENTIAL_PREFIXES) or CREDENTIAL_RE.search(k))}
    return {**env, "GIT_TERMINAL_PROMPT": "0", HEADLESS_ENV: "1"}


def block_public_push(root, wt):
    """Give the worktree WT, for the public remote of the clone ROOT, a pushurl that fails: in the worktree's own config
    (`extensions.worktreeConfig`, `git config --worktree`), as a worktree shares the clone's `.git/config` and the clone's
    own `kbgit.py publish` must still push. Does nothing without a public remote, or when it is the integration one."""
    public = kbpublic.publish_remote(str(root))
    if not public or public == kbpublic.integration_remote(str(root)) or public not in bl_base.git(root, "remote").split():
        return
    bl_base.git(root, "config", "extensions.worktreeConfig", "true")
    bl_base.git(wt, "config", "--worktree", f"remote.{public}.pushurl", NO_PUSH_URL)


def prepare_worktree(root, sprint):
    """The runner's worktree at origin/main and the ref it starts from: made on the branch orch/SP when missing,
    else reused. A clean one is fast-forwarded to origin/main (one already ahead of it is kept as it is); one with
    uncommitted files, or whose branch diverged from origin/main, is refused."""
    wt, branch = worktree_path(root, sprint), branch_name(sprint)
    remote = kbpublic.integration_remote(str(root))  # never the name origin: the remote with the integration role
    main = f"{remote}/main"
    bl_base.git(root, "fetch", remote)
    if not wt.exists():
        have = git_ok(root, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}")
        add = ["worktree", "add", str(wt), branch] if have else ["worktree", "add", "-b", branch, str(wt), main]
        bl_base.git(root, *add)
    block_public_push(root, wt)
    dirty = [ln[3:] for ln in bl_base.git(wt, "status", "--porcelain", "-uall").splitlines() if ln.strip()]
    if dirty:
        more = f" and {len(dirty) - DIRTY_FILES} more" if len(dirty) > DIRTY_FILES else ""
        raise bl_base.Refused(f"the runner's worktree {wt} has uncommitted files, so it is not brought to {main}: "
                              + ", ".join(dirty[:DIRTY_FILES]) + more)
    if not git_ok(wt, "merge-base", "--is-ancestor", main, "HEAD"):  # not at or ahead of the integration main
        if not git_ok(wt, "merge-base", "--is-ancestor", "HEAD", main):
            raise bl_base.Refused(f"the runner's worktree {wt} (branch {branch}) has commits {main} lacks and "
                                  f"lacks commits {main} has: bring it to {main} by hand")
        bl_base.git(wt, "merge", "--ff-only", main)
    return wt, bl_base.git(wt, "rev-parse", "HEAD").strip()


def worktree_state(wt, main):
    """(uncommitted files, whether the branch diverged from MAIN) of the runner's worktree WT: what prepare_worktree
    refuses by."""
    dirty = [ln[3:] for ln in bl_base.git(wt, "status", "--porcelain", "-uall").splitlines() if ln.strip()]
    diverged = (not git_ok(wt, "merge-base", "--is-ancestor", main, "HEAD")
                and not git_ok(wt, "merge-base", "--is-ancestor", "HEAD", main))
    return dirty, diverged


def headless_refusal(command):
    """Refuse COMMAND (bl_base.Refused) inside a headless run (HEADLESS_ENV): only the manager session starts or resets
    runners, so no runner's child is started outside its parent's process group and deadline."""
    if os.environ.get(HEADLESS_ENV):
        raise bl_base.Refused(f"{command} runs only in the manager session, not inside a headless run ({HEADLESS_ENV})")


def reset_worktree(root, sprint):
    """The recovery for a start prepare_worktree refused: name the cause and free the worktree without losing what is in
    it. Uncommitted files go into a git stash of the clone; a diverged branch is kept as `stale/SP-STAMP` and the
    worktree removed, so the next start makes both afresh at the integration main. A worktree that is clean and not
    diverged is left as it is. Refused while a live runner holds SP, and in a headless run. Returns 0."""
    headless_refusal("runner reset")
    held = [r for r in bl_base.live_runners() if r.get("sprint") == sprint]
    if held:
        raise bl_base.Refused(f"{sprint} has a live runner (pid {held[0].get('pid')}, clone {held[0].get('clone')}): "
                              "its worktree is not reset")
    wt, branch = worktree_path(root, sprint), branch_name(sprint)
    if not wt.exists():
        print(f"{sprint}: no runner worktree at {wt}, nothing to reset")
        return 0
    remote = kbpublic.integration_remote(str(root))
    main = f"{remote}/main"
    bl_base.git(root, "fetch", remote)
    dirty, diverged = worktree_state(wt, main)
    if not dirty and not diverged:
        print(f"{sprint}: the worktree {wt} is clean and not diverged from {main}, nothing to reset")
        return 0
    stamp = now().strftime("%Y%m%dT%H%M%SZ")
    done = []
    if dirty:
        bl_base.git(wt, "stash", "push", "--include-untracked", "-m", f"autopilot reset {sprint} {stamp}")
        done.append(f"{len(dirty)} uncommitted files ({', '.join(dirty[:DIRTY_FILES])}) kept in the stash "
                    f"'autopilot reset {sprint} {stamp}'")
    if diverged:
        stale = f"stale/{sprint}-{stamp}"
        bl_base.git(root, "branch", "-m", branch, stale)
        bl_base.git(root, "worktree", "remove", "--force", str(wt))
        done.append(f"branch {branch} diverged from {main}: kept as {stale}, worktree removed")
    print(f"{sprint}: " + "; ".join(done) + f"; the next runner start makes the worktree afresh at {main}")
    return 0


def plugin_dirs(worktree):
    """The plugins the project loads, as --plugin-dir values: the project itself when it has a plugin manifest, and
    each directory under .claude-plugin/ that has one of its own, in name order."""
    wt = Path(worktree)
    found = [wt] if (wt / ".claude-plugin" / "plugin.json").is_file() else []
    base = wt / ".claude-plugin"
    if base.is_dir():
        found += [d for d in sorted(base.iterdir()) if (d / ".claude-plugin" / "plugin.json").is_file()]
    return [str(d) for d in found]


def bound(env_name, default, cast):
    """The positive number the environment variable ENV_NAME holds, as CAST makes it; DEFAULT when unset, unreadable or
    not above zero (a bad override never stops a run)."""
    try:
        value = cast(os.environ.get(env_name, ""))
    except ValueError:
        return default
    return value if value > 0 and value == value and value != float("inf") else default


def max_turns():
    return bound(TURNS_ENV, MAX_TURNS, int)


def deadline_s():
    return bound(DEADLINE_ENV, DEADLINE_S, float)


def claude_argv(worktree, sprint, landed=None):
    """The `claude -p` command of a run: the prompt, stream-json output, the turn limit, the worktree's settings file
    and each plugin by --plugin-dir, all explicit. No permission flag: the project's allow rules govern the run."""
    prompt = PROMPT.format(sprint=sprint, landed=LANDED_FLAG.format(k=landed) if landed else "")
    argv = [*CLAUDE, "-p", prompt, "--output-format", "stream-json", "--verbose", "--max-turns", str(max_turns()),
            "--settings", str(Path(worktree) / ".claude" / "settings.json"), "--disallowedTools", *RUNNER_DENY]
    for d in plugin_dirs(worktree):
        argv += ["--plugin-dir", d]
    return argv


# ---------------------------------------------------------------- the run

def one_line(text, n=DETAIL_CHARS):
    return " ".join(str(text).split())[:n]


def supervise(argv, cwd, keep, stderr, deadline=None):
    """Run ARGV in CWD with its stdout read line by line into the open file KEEP (each line written and flushed as it
    arrives) and its stderr into the open file STDERR. The child is ended at the first system compact_boundary event,
    after DEADLINE seconds (deadline_s() when None: SIGTERM, then its process tree after GRACE_S), and on any
    interrupt. Returns {"compaction": bool, "timeout": bool, "result": the last result event or None, "exit_code": int}."""
    group = {"start_new_session": True} if os.name == "posix" else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    proc = subprocess.Popen(argv, cwd=str(cwd), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=stderr,
                            text=True, encoding="utf-8", errors="replace", env=child_env(), **group)
    out = {"compaction": False, "timeout": False, "result": None}

    def expire():  # runs in a timer thread: the child has outlived its deadline
        if out["compaction"]:
            return
        out["timeout"] = True
        proc.terminate()
        try:
            proc.wait(GRACE_S)
        except subprocess.TimeoutExpired:
            pass
        end_tree(proc)  # the child's group in any case: a subagent or a shell command it left holds the pipe open

    timer = TIMER(deadline_s() if deadline is None else deadline, expire)
    timer.daemon = True
    timer.start()
    try:
        for line in proc.stdout:
            keep.write(line if line.endswith("\n") else line + "\n")
            keep.flush()
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if not isinstance(ev, dict):
                continue
            if ev.get("type") == "result":
                out["result"] = ev
            elif ev.get("type") == "system" and ev.get("subtype") == "compact_boundary":
                out["compaction"] = True
                proc.terminate()
                try:
                    proc.wait(GRACE_S)
                except subprocess.TimeoutExpired:
                    pass
                break
        if not out["compaction"]:
            proc.wait()
    finally:
        timer.cancel()
        end_tree(proc)  # the child's process group, which subagents and shell commands belong to
        proc.wait()
        timer.join(TIMER_JOIN_S)  # the cancelled timer's thread is gone, or a fired expire() has finished, on return
    out["exit_code"] = proc.returncode
    return out


class RunnerEnded(Exception):
    """Raised in the runner by SIGTERM or SIGHUP; NAME is the signal's name."""

    def __init__(self, name):
        super().__init__(name)
        self.name = name


@contextlib.contextmanager
def ends_on_signals():
    """Within the block SIGTERM and SIGHUP (`backlog.py procs --end`, a manager that exits) raise RunnerEnded in the
    runner instead of killing it where it stands, so supervise's cleanup ends the child's process tree and the status
    is written. A second signal while it ends is ignored; the previous handlers come back at the end. Outside the main
    thread nothing is installed."""
    sigs = [getattr(signal, n) for n in ("SIGTERM", "SIGHUP") if hasattr(signal, n)]
    old = {}

    def handler(signum, frame):
        for sig in sigs:
            signal.signal(sig, signal.SIG_IGN)
        raise RunnerEnded(signal.Signals(signum).name)

    try:
        for sig in sigs:
            old[sig] = signal.signal(sig, handler)
    except ValueError:  # not the main thread
        pass
    try:
        yield
    finally:
        for sig, previous in old.items():
            signal.signal(sig, previous if previous is not None else signal.SIG_DFL)


def exit_cause(run):
    """(cause, detail) of a finished run, from supervise's dict: compaction when the child was ended at one, else from
    its final result and exit code."""
    if run["compaction"]:
        return "compaction", ""
    if run.get("timeout"):
        return "timeout", f"the child was ended at its deadline of {run.get('deadline_s'):g}s"
    res = run["result"]
    if res is None:
        return "error", f"no result event, exit {run['exit_code']}"
    text = res.get("result") if isinstance(res.get("result"), str) else ""
    if run["exit_code"] != 0 or res.get("is_error") or str(res.get("subtype") or "").startswith("error"):
        return "error", one_line(text) or f"exit {run['exit_code']}, subtype {res.get('subtype')}"
    named = CAUSE_LINE.findall(text)
    if named:
        return named[-1], ""
    return "error", "the final result names no cause: its last line is not " + CAUSE_MARKER.format(cause="<cause>")


def parse_time(text):
    """The datetime of `YYYY-MM-DDTHH:MM:SSZ`; None when TEXT is not one."""
    try:
        return datetime.datetime.strptime(str(text), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        return None


def seconds_since(started, end=None):
    """Whole seconds from STARTED (`YYYY-MM-DDTHH:MM:SSZ`) to END (the same form, default now), never below 0; None when
    either does not read."""
    t0, t1 = parse_time(started), (now() if end is None else parse_time(end))
    return None if t0 is None or t1 is None else max(0, int((t1 - t0).total_seconds()))


def age_text(seconds):
    """A span as `45s`, `7m`, `2h05m` or `3d04h`."""
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h{seconds % 3600 // 60:02d}m"
    return f"{seconds // 86400}d{seconds % 86400 // 3600:02d}h"


def age_label(st, pid=None):
    """`age 2h05m` of the run status.json ST records while it runs (with `stalled` past its deadline), `ran 2h05m` once it
    ended; `` when the run's start or end does not read, or PID is given and is not the runner that wrote ST."""
    if not isinstance(st, dict) or (pid is not None and st.get("pid") != pid):
        return ""
    if st.get("cause") == "running":
        age = seconds_since(st.get("started"))
        if age is None:
            return ""
        deadline = st.get("deadline_s")
        past = isinstance(deadline, (int, float)) and not isinstance(deadline, bool) and age > deadline
        return f"age {age_text(age)}" + (" stalled" if past else "")
    age = seconds_since(st.get("started"), st.get("ended")) if st.get("ended") else None
    return "" if age is None else f"ran {age_text(age)}"


def register_runner(root, sprint):
    """Claim a runner slot of the host for SPRINT: write this process's record, then look at the live runners. When
    this process is not among the first MAX_RUNNERS (oldest first), or a live runner already holds the sprint, the
    record is removed and the start refused, naming the live runners. Returns the record's path."""
    now_s = now().strftime("%Y-%m-%dT%H:%M:%SZ")
    path = bl_base.runner_record_path(os.getpid())
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {"pid": os.getpid(), "sprint": sprint, "clone": str(root), "started": now_s, "touches": []}
    write_status(path, rec)
    live = bl_base.live_runners()
    others = [r for r in live if r.get("pid") != os.getpid()]
    names = ", ".join(f"{r.get('sprint')} (pid {r.get('pid')}, clone {r.get('clone')})" for r in others)
    held = [r for r in others if r.get("sprint") == sprint]
    if held:
        path.unlink(missing_ok=True)
        raise bl_base.Refused(f"{sprint} already has a live runner on this host: {names}")
    if [r.get("pid") for r in live].index(os.getpid()) >= bl_base.MAX_RUNNERS:
        path.unlink(missing_ok=True)
        raise bl_base.Refused(f"{bl_base.MAX_RUNNERS} sprint runners already run on this host, so a third is not "
                              f"started: {names}; start {sprint} when one has ended")
    return path


def write_early_status(root, sprint, name):
    """The status of a run a signal ended before run_in_slot kept its own (while the slot was claimed or the worktree
    prepared): cause `error`, the signal's NAME as the detail, written over the previous run's status.json so it does
    not stand for this run, in the shape run_in_slot writes."""
    directory = cache_dir(root, sprint)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = now().strftime("%Y-%m-%dT%H:%M:%SZ")
    write_status(directory / "status.json", {
        "sprint": sprint, "pid": os.getpid(), "worktree": str(worktree_path(root, sprint)),
        "branch": branch_name(sprint), "start_ref": None, "started": stamp, "stream": None, "landed_limit": None,
        "cause": "error", "detail": f"runner ended by {name}", "exit_code": None, "ended": stamp,
        "deadline_s": deadline_s(), "max_turns": max_turns()})
    bl_base.runner_record_path(os.getpid()).unlink(missing_ok=True)


def guarded_refusal(root, sprint):
    """The lines naming each not-done item of SPRINT (read from the clone ROOT, before any worktree is made) whose
    touches headless_guard denies a headless run, as `backlog.py start` warns of them; [] when there is none, and
    when the sprint is unknown (a bad id is refused later)."""
    try:
        bl = bl_base.Backlog(root)
        if sprint not in bl.items:
            return []
        return [bl_plan.guarded_line(bl, i, g) for i, g in bl_plan.guarded_items(bl, sprint)]
    except (OSError, ValueError):
        return []


def runner_start(sprint, landed=None, root=ROOT):
    """Run the sprint headless in its worktree; returns the exit code (the module docstring). Refused inside a headless
    run (headless_refusal)."""
    headless_refusal("runner start")
    root = Path(root)
    held = guarded_refusal(root, sprint)
    if held:
        print(f"refused: {sprint} is operator-present only: a headless runner cannot edit the files of its items:\n  "
              + "\n  ".join(held), file=sys.stderr)
        return 1
    kept = []  # run_in_slot adds to it once its own status is kept, from then on the status names the end itself
    try:
        with ends_on_signals():
            record = register_runner(root, sprint)
            try:
                return run_in_slot(sprint, landed, root, record, kept)
            finally:
                record.unlink(missing_ok=True)
    except RunnerEnded as e:
        if not kept:  # the signal came before the run's own status: this one replaces the previous run's
            write_early_status(root, sprint, e.name)
            record_run(root, sprint, "error", 0)
        print(f"{sprint}: error (runner ended by {e.name})")
        return 1


def record_run(root, sprint, cause, landed, ended=None):
    """Append the end of this run to the sprint's runs.jsonl (bl_base.append_run), by the tool and not the model; a
    write that fails is said on stderr and never changes the run's exit."""
    try:
        bl_base.append_run(root, sprint, cause, landed, ended or now().strftime("%Y-%m-%dT%H:%M:%SZ"))
    except OSError as e:
        print(f"{sprint}: cannot record the run in {RUNS_FILE}: {e}", file=sys.stderr)


def run_landed(repo, bl, sprint, start):
    """The count of the sprint's items the run landed (landed_items); 0 when git cannot say."""
    try:
        return len(landed_items(repo, set(bl.sprint_items(sprint)), str(start or "")))
    except (bl_base.Refused, OSError, ValueError, KeyError):
        return 0


def run_in_slot(sprint, landed, root, record, kept=None):
    """runner_start's body, once the host's runner slot is held: the worktree, the overlap check against the other
    runners, the run and its status."""
    wt, start = prepare_worktree(root, sprint)
    bl = bl_base.Backlog(wt)
    held = bl_plan.runner_conflicts(bl, sprint)
    if held:
        raise bl_base.Refused(f"{sprint}'s committed touches overlap those of a sprint a runner holds on this "
                              "host:\n  " + "\n  ".join(held))
    rec = json.loads(record.read_text(encoding="utf-8"))
    rec["touches"] = sorted({t for i in bl.sprint_items(sprint) if bl.items[i].get("status") not in ("done", "dropped")
                             for t in bl_base.scope(bl, i) if isinstance(t, str) and t})
    write_status(record, rec)
    if not (wt / ".claude" / "settings.json").is_file():
        raise bl_base.Refused(f"{wt / '.claude' / 'settings.json'} is missing: a run takes the project's own settings")
    directory = cache_dir(root, sprint)
    directory.mkdir(parents=True, exist_ok=True)
    started = now()
    name, keep = open_stream(directory, started.strftime("%Y%m%dT%H%M%SZ"))
    status = {"sprint": sprint, "pid": os.getpid(), "worktree": str(wt), "branch": branch_name(sprint), "start_ref": start,
              "started": started.strftime("%Y-%m-%dT%H:%M:%SZ"), "stream": name, "landed_limit": landed,
              "cause": "running", "detail": "", "exit_code": None, "ended": None, "deadline_s": deadline_s(),
              "max_turns": max_turns()}
    write_status(directory / "status.json", status)
    argv = claude_argv(wt, sprint, landed)
    run = {"compaction": False, "result": None, "exit_code": -1}
    detail = "the runner stopped before the child ended"
    if kept is not None:
        kept.append(True)
    try:
        with keep, open(directory / (name[:-len(".jsonl")] + ".stderr"), "w", encoding="utf-8", newline="\n") as err:
            try:
                before = os.environ.get(RUNNER_SPRINT_ENV)
                os.environ[RUNNER_SPRINT_ENV] = sprint  # child_env passes it on: backlog.py merge reads it
                try:
                    run = supervise(argv, wt, keep, err)
                finally:
                    if before is None:
                        os.environ.pop(RUNNER_SPRINT_ENV, None)
                    else:
                        os.environ[RUNNER_SPRINT_ENV] = before
                run["deadline_s"] = status["deadline_s"]
                detail = None
            except OSError as e:  # claude not found, or not runnable
                detail = one_line(f"cannot start {argv[0]}: {e}")
            except RunnerEnded as e:  # SIGTERM or SIGHUP: supervise's cleanup has ended the child's tree
                detail = f"runner ended by {e.name}"
    finally:
        cause, why = exit_cause(run) if detail is None else ("error", detail)
        status.update(cause=cause, detail=why, exit_code=run["exit_code"],
                      ended=now().strftime("%Y-%m-%dT%H:%M:%SZ"))
        write_status(directory / "status.json", status)
        record_run(root, sprint, cause, run_landed(wt, bl, sprint, start), status["ended"])
    print(f"{sprint}: {cause}" + (f" ({why})" if why else "") + f"; stream {directory / name}")
    return 1 if cause in FAIL_CAUSES else 0


# ---------------------------------------------------------------- the report

def landed_items(repo, ids, start):
    """The sprint items (IDS) whose done commits, with KB-Work, lie between START and HEAD of REPO, oldest first."""
    out = []
    for msg in bl_base.git(repo, "log", "--reverse", "--format=%B%x1e", f"{start}..HEAD").split("\x1e"):
        msg = msg.strip()
        if not msg.startswith(DONE_SUBJECT):
            continue
        for m in KB_WORK.findall(msg):
            for iid in re.split(r"[,\s]+", m.strip()):
                if iid in ids and iid not in out:
                    out.append(iid)
    return out


def gates_of_run(repo, bl, ids, start):
    """[`ITEM/GATE=answer-or-open`] for each gate of the sprint items the run added since START or that is still open."""
    out = []
    for iid in sorted(ids):
        gates = [g for g in bl.items[iid].get("gates") or [] if isinstance(g, dict)]
        if not gates:
            continue
        p = subprocess.run(["git", "show", f"{start}:{bl_base.REL_DIR}/{iid}.json"], cwd=repo, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        try:
            before = {g.get("id") for g in json.loads(p.stdout).get("gates") or []} if p.returncode == 0 else set()
        except (ValueError, AttributeError):
            before = set()
        for g in gates:
            answer = g.get("answer")
            if g.get("id") not in before or answer is None:
                out.append(f"{iid}/{g.get('id')}=" + (one_line(answer, 16) if answer is not None else "open"))
    return out


def bugs_filed(repo, bl, start):
    """The bug items whose files the run added since START."""
    names = bl_base.git(repo, "diff", "--name-only", "--diff-filter=A", start, "HEAD", "--", bl_base.REL_DIR)
    ids = sorted(Path(n).stem for n in names.splitlines() if n.endswith(".json"))
    return [i for i in ids if bl.items.get(i, {}).get("kind") == "bug"]


def fit(label, items, budget):
    """`LABEL N: a, b, ... +K more` within BUDGET characters."""
    head, shown = f"{label} {len(items)}", []
    if not items:
        return head
    for i, it in enumerate(items):
        more = f" +{len(items) - i - 1} more" if i < len(items) - 1 else ""
        if len(head) + 2 + len(", ".join(shown + [it])) + len(more) > budget:
            return f"{head}: {', '.join(shown)} +{len(items) - len(shown)} more" if shown else f"{head}: +{len(items)} more"
        shown.append(it)
    return f"{head}: {', '.join(shown)}"


def status_text(sprint, root=ROOT):
    """The report of a recorded run, under STATUS_MAX characters; None when no run was recorded for SPRINT."""
    st = read_status(root, sprint)
    if st is None:
        return None
    cause = str(st.get("cause") or "unknown")
    head = f"{sprint} exit cause {cause}" + (f": {one_line(st['detail'])}" if st.get("detail") else "")
    lines = [head, f"start {str(st.get('start_ref') or '')[:10]}, started {st.get('started')}"
             + "".join(", " + x for x in [age_label(st)] if x)]
    repo = Path(st["worktree"]) if st.get("worktree") and Path(st["worktree"]).is_dir() else Path(root)
    try:
        bl = bl_base.Backlog(repo)
        ids = set(bl.sprint_items(sprint))
        start = str(st.get("start_ref") or "")
        lines += [fit("landed", landed_items(repo, ids, start), 240), fit("gates", gates_of_run(repo, bl, ids, start), 240),
                  fit("bugs", bugs_filed(repo, bl, start), 160)]
    except bl_base.Refused as e:
        lines.append("git: " + one_line(e, 160))
    return "\n".join(lines)[:STATUS_MAX - 1]


def runner_status(sprint, root=ROOT):
    text = status_text(sprint, root)
    if text is None:
        print(f"{sprint}: no run recorded")
        return 1
    print(text)
    return 0


# ---------------------------------------------------------------- status: the manager's state

HOOK_MAX = 1000  # `status --hook` prints at most this many characters, `...` included
SHOW = 3  # entries a section of `status` names; the rest is a count
HOOK_SHOW = 2
TICK_TAIL = 65536  # bytes of ticks.jsonl read from its end


def listing(label, items, show):
    """`LABEL N: a, b, c +K more`: the count, then the first SHOW entries."""
    if not items:
        return None
    shown = items[:show]
    more = f" +{len(items) - len(shown)} more" if len(items) > len(shown) else ""
    return f"{label} {len(items)}: " + ", ".join(shown) + more


def runner_lines(root, show):
    """Live runner records (read, never removed) and the cause of each ended run recorded under _cache/autopilot."""
    live, items = set(), []
    for p in sorted(bl_base.runner_dir().glob(bl_base.RUNNER_PREFIX + "*.json")):
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
            pid = int(rec["pid"])
            if bl_base.pid_alive(pid):
                live.add(str(rec.get("sprint")))
                sp = str(rec.get("sprint"))
                age = age_label(read_status(root, sp), pid) if SPRINT_ID.match(sp) else ""
                items.append(f"{rec.get('sprint')} pid {pid} alive worktree {Path(str(rec.get('clone'))).name}"
                             + (f" {age}" if age else ""))
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue
    return [listing("runners", items + ended_runs(root, live), show)]


def ended_runs(root, live):
    """`SP ended CAUSE` of each recorded run no live runner holds: the failed ones (`error`, `timeout`; a `running` no live
    runner holds was killed, so it ended in error) before the others, each group newest first. Where the root has item
    files, a sprint without its item file (closed) is left out; a root with none (a bare cache) lists every record."""
    base = Path(root) / "_cache" / "autopilot"
    try:
        have = {q.stem for q in (Path(root) / bl_base.REL_DIR).glob("SP-*.json")}
        filtered = any((Path(root) / bl_base.REL_DIR).glob("*.json"))
    except OSError:
        have, filtered = set(), False
    rows = []
    for p in base.glob("SP-*/status.json"):
        sp = p.parent.name
        st = read_status(root, sp)
        if not st or sp in live or not SPRINT_ID.match(sp) or (filtered and sp not in have):
            continue
        cause = "error" if st.get("cause") == "running" else st.get("cause")
        try:
            stamp = str(st.get("ended") or st.get("started") or "") or datetime.datetime.fromtimestamp(
                p.stat().st_mtime, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except OSError:
            stamp = ""
        rows.append((stamp, sp, cause))
    rows.sort(reverse=True)  # newest first, the sprint id breaking a tie
    rows.sort(key=lambda r: r[2] not in FAIL_CAUSES)  # stable: the failed runs lead
    return [f"{sp} ended {cause}" for _, sp, cause in rows]


def sprint_lines(root, show):
    import backlog  # the facade holds horizon and ready; loaded here so a failure costs only this section
    bl = bl_base.Backlog(root)
    out = []
    for sid in sorted(i for i, it in bl.items.items() if it.get("kind") == "sprint" and it.get("status") == "active"):
        items = bl.sprint_items(sid)
        done = sum(1 for i in items if bl.items[i].get("status") in ("done", "dropped"))
        reach = backlog.horizon(bl, sid)[0]
        nxt = backlog.ready(bl, sid)
        out.append(f"{sid} {done}/{len(items)} done, {len(reach)} reachable" + (f", next {nxt[0]}" if nxt else ""))
    return [listing("sprints", out, show)]


def gate_lines(root, show):
    """The operator's open blocking gates, and the autopilot's active decisions (kb/_self/_decisions.csv) that no
    operator decision has superseded yet."""
    import csv
    bl = bl_base.Backlog(root)
    gates = [f"{i}/{g.get('id')}" for i, it in sorted(bl.items.items()) if it.get("status") not in ("done", "dropped")
             for g in bl_base.open_gates(it)]
    out = [listing("gates", gates, show)]
    try:
        with open(Path(root) / "kb" / "_self" / "_decisions.csv", encoding="utf-8", newline="") as f:
            rows = [r for r in csv.DictReader(f) if r.get("status") == "active" and r.get("by") == "autopilot"]
    except OSError:
        rows = []
    return out + [listing("unratified", [r.get("id", "?") for r in rows], show)]


def last_tick(root):
    """The newest tick record: state.json, else the last readable line of ticks.jsonl; None when neither gives a dict."""
    base = Path(root) / "_cache" / "autopilot"
    try:
        data = json.loads((base / "state.json").read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, ValueError):
        pass
    try:
        with open(base / "ticks.jsonl", "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - TICK_TAIL))
            lines = f.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return None
    for ln in reversed(lines):
        try:
            data = json.loads(ln)
        except ValueError:
            continue
        if isinstance(data, dict):
            return data
    return None


def tick_lines(root, show):
    data = last_tick(root)
    acts = data.get("actions") if data else None
    if not isinstance(acts, list) or not acts:
        return []
    names = [one_line(a.get("action") or a.get("text") or "" if isinstance(a, dict) else a, 60) for a in acts]
    return [listing(f"tick {one_line(data.get('tick', '?'), 12)} actions", names, show)]


def status_report(root, show):
    """The status sections as lines; a section that fails prints `NAME unavailable` and leaves the others."""
    lines = []
    for name, fn in (("runners", runner_lines), ("sprints", sprint_lines), ("gates", gate_lines), ("tick", tick_lines)):
        try:
            lines += [x for x in fn(root, show) if x]
        except Exception as e:  # noqa: BLE001 - one section never takes the others down
            lines.append(f"{name} unavailable: {one_line(e, 60)}")
    return lines or ["autopilot idle: no runner, active sprint, pending gate or tick"]


def status(hook=False, root=ROOT):
    """Print the state. `--hook`: under HOOK_MAX characters, always 0, on any error one line and 0."""
    try:
        text = "\n".join(status_report(root, HOOK_SHOW if hook else SHOW))
        if hook and len(text) >= HOOK_MAX:
            text = text[:HOOK_MAX - 4] + "..."
        print(text)
    except Exception:  # noqa: BLE001
        print("autopilot status unavailable")
        return 0 if hook else 1
    return 0


def main_lock_holder(clone):
    """The live holder of the host main lock (kg_lock: `backlog.py land`'s fetch and rebase, `kbgit.py sync --push`)
    whose clone is CLONE, as {pid, clone, started, step}; None when the lock is free, its record unreadable, its pid
    gone or its clone another one."""
    import kg_lock
    import tests as tests_py  # the lock's helpers, as kg_lock uses them
    path = os.path.join(tests_py.host_lock_dir(), kg_lock.LOCK_NAME)
    text = tests_py.read_lock(path)
    holder = tests_py.parse_holder(text) if text else None
    if not holder or not tests_py.pid_alive(holder["pid"]):
        return None
    try:
        same = os.path.samefile(holder["clone"], clone)
    except OSError:
        same = False
    return {**holder, "step": kg_lock.holder_step(text)} if same else None


def precompact(root=ROOT, stdin=None):
    """The PreCompact hook: exit 2, saying why on stderr, while a land or sync of this clone holds the host main lock,
    so the session that runs it keeps its state through the step; else 0. Bounded: a free lock, a holder whose pid is
    gone, another clone's holder or any error lets compaction run."""
    try:
        try:
            trigger = json.loads((stdin or sys.stdin).read() or "{}").get("trigger", "?")
        except (ValueError, AttributeError):
            trigger = "?"
        held = main_lock_holder(str(os.environ.get("CLAUDE_PROJECT_DIR") or root))
    except Exception:  # noqa: BLE001 - a hook that fails never blocks compaction
        return 0
    if not held:
        return 0
    print(f"compaction ({trigger}) waits: this clone's {held['step']} holds the host main lock (pid {held['pid']}, "
          f"since {held['started']}); it is released when that step ends", file=sys.stderr)
    return 2


# ---------------------------------------------------------------- the command line

def sprint_arg(text):
    if not SPRINT_ID.match(text):
        raise argparse.ArgumentTypeError(f"{text!r} is not a sprint id (SP-xxxxxxxx)")
    return text


def positive(text):
    if not text.isdigit() or int(text) < 1:
        raise argparse.ArgumentTypeError(f"{text!r} is not a positive number")
    return int(text)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    runner = sub.add_parser("runner", help="run a sprint headless in a worktree of its own").add_subparsers(
        dest="action", required=True)
    st = runner.add_parser("start", help="start the run")
    st.add_argument("sprint", type=sprint_arg)
    runner.add_parser("reset", help="free the worktree a refused start names: stash its files, keep a diverged branch"
                      ).add_argument("sprint", type=sprint_arg)
    st.add_argument("--landed", type=positive, metavar="K", help="the run stops after K landed items")
    rs = sub.add_parser("runner-status", help="what the recorded run did, in under 1000 characters")
    rs.add_argument("sprint", type=sprint_arg)
    sa = sub.add_parser("status", help="the manager's state in one capped command")
    sa.add_argument("--hook", action="store_true", help="under 1000 characters, never fails")
    sub.add_parser("precompact", help="the PreCompact hook: exit 2 while a land or sync of this clone holds the lock")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "status":
            return status(a.hook, ROOT)
        if a.cmd == "precompact":
            return precompact(ROOT)
        if a.cmd == "runner-status":
            return runner_status(a.sprint, ROOT)
        if a.action == "reset":
            return reset_worktree(ROOT, a.sprint)
        return runner_start(a.sprint, a.landed, ROOT)
    except bl_base.Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
