"""The autopilot's sprint runner (kb/_self/tools.md, The autopilot runner): one headless `claude -p` run of
`/kb-sprint run SP --headless` in a worktree of its own, with its stream kept and its end recorded, and a short
report of what the run did.

  autopilot.py runner start SP [--landed K]   make or reuse the worktree .claude/worktrees/runner-SP on the branch
                                              orch/SP (a clean one is brought to origin/main by a fast-forward; one
                                              with uncommitted files is refused, naming them) and run the sprint
                                              there. The worktree's own .claude/settings.json is passed by
                                              --settings and each plugin the project loads by --plugin-dir; no
                                              --permission-mode and no --dangerously-skip-permissions, so the
                                              project's allow rules govern the run. Every line of the stream is
                                              written, as it arrives, to _cache/autopilot/SP/<UTC stamp>.jsonl. The
                                              runner ends the child at the first system compact_boundary event, and
                                              records the end in _cache/autopilot/SP/status.json with the start ref.
  autopilot.py runner-status SP               print, in under 1000 characters, the sprint's items the run landed (done
                                              commits with KB-Work since the start ref), the gates it added or left
                                              open on them, the bugs filed since the start ref and the exit cause

Exit cause (status.json `cause`): `compaction` (the child was ended at its first compact_boundary), else read from the
run's own final result and the child's exit code: `error` (the child could not start, no result, an error result or a
non-zero exit, or a result that names no cause), else the cause the result's last `sprint-runner: <cause>` line names: `landed-limit` (K
items landed), `sprint-done` (nothing ready is left) or `blocked` (what is ready waits on a gate or trigger). While the
run lives the cause is `running`.

At most bl_base.MAX_RUNNERS runners live on a host, whatever their clone. Each records itself while it runs in the host
lock directory (`kb-runner.<pid>.json`: pid, sprint, clone, start time and the touches of the sprint's open items), and
status.json carries the same pid. A third `runner start` is refused naming the two, a start of a sprint a live runner
holds is refused, and so is one whose committed touches overlap those of another sprint's runner, naming the globs and
the holder (the same check `backlog.py start` makes). A record whose process is gone is ignored and removed.

Exit codes: `runner start` 0 the run ended with a named cause other than `error`, 1 it ended in `error`, 2 refused (a
bad sprint id, no git clone, a dirty or diverged worktree, no settings file, two runners already live, a sprint held by
a runner, touches that overlap another runner's); `runner-status` 0
printed, 1 no run was recorded for the sprint, 2 a bad sprint id. Standard library only.
"""
import argparse, datetime, json, os, re, subprocess, sys
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
CAUSES_FROM_RESULT = ("landed-limit", "sprint-done", "blocked")
CAUSE_LINE = re.compile(r"^sprint-runner: (" + "|".join(CAUSES_FROM_RESULT) + r")[ \t]*$", re.M)
SPRINT_ID = re.compile(r"^SP-[a-z2-7]{8}$")
STATUS_MAX = 1000  # runner-status prints fewer characters than this
GRACE_S = 5  # seconds a child gets to end after SIGTERM before its process group is killed
DETAIL_CHARS = 120
DIRTY_FILES = 8  # files a dirty-worktree refusal names
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


def plugin_dirs(worktree):
    """The plugins the project loads, as --plugin-dir values: the project itself when it has a plugin manifest, and
    each directory under .claude-plugin/ that has one of its own, in name order."""
    wt = Path(worktree)
    found = [wt] if (wt / ".claude-plugin" / "plugin.json").is_file() else []
    base = wt / ".claude-plugin"
    if base.is_dir():
        found += [d for d in sorted(base.iterdir()) if (d / ".claude-plugin" / "plugin.json").is_file()]
    return [str(d) for d in found]


def claude_argv(worktree, sprint, landed=None):
    """The `claude -p` command of a run: the prompt, stream-json output, the worktree's settings file and each plugin
    by --plugin-dir, all explicit. No permission flag: the project's allow rules govern the run."""
    prompt = PROMPT.format(sprint=sprint, landed=LANDED_FLAG.format(k=landed) if landed else "")
    argv = [*CLAUDE, "-p", prompt, "--output-format", "stream-json", "--verbose",
            "--settings", str(Path(worktree) / ".claude" / "settings.json")]
    for d in plugin_dirs(worktree):
        argv += ["--plugin-dir", d]
    return argv


# ---------------------------------------------------------------- the run

def one_line(text, n=DETAIL_CHARS):
    return " ".join(str(text).split())[:n]


def supervise(argv, cwd, keep, stderr):
    """Run ARGV in CWD with its stdout read line by line into the open file KEEP (each line written and flushed as it
    arrives) and its stderr into the open file STDERR. The child is ended at the first system compact_boundary event,
    and on any interrupt. Returns {"compaction": bool, "result": the last result event or None, "exit_code": int}."""
    group = {"start_new_session": True} if os.name == "posix" else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    proc = subprocess.Popen(argv, cwd=str(cwd), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=stderr,
                            text=True, encoding="utf-8", errors="replace", **group)
    out = {"compaction": False, "result": None}
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
        end_tree(proc)  # the child's process group, which subagents and shell commands belong to
        proc.wait()
    out["exit_code"] = proc.returncode
    return out


def exit_cause(run):
    """(cause, detail) of a finished run, from supervise's dict: compaction when the child was ended at one, else from
    its final result and exit code."""
    if run["compaction"]:
        return "compaction", ""
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


def runner_start(sprint, landed=None, root=ROOT):
    """Run the sprint headless in its worktree; returns the exit code (the module docstring)."""
    root = Path(root)
    record = register_runner(root, sprint)
    try:
        return run_in_slot(sprint, landed, root, record)
    finally:
        record.unlink(missing_ok=True)


def run_in_slot(sprint, landed, root, record):
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
              "cause": "running", "detail": "", "exit_code": None, "ended": None}
    write_status(directory / "status.json", status)
    argv = claude_argv(wt, sprint, landed)
    run = {"compaction": False, "result": None, "exit_code": -1}
    detail = "the runner stopped before the child ended"
    try:
        with keep, open(directory / (name[:-len(".jsonl")] + ".stderr"), "w", encoding="utf-8", newline="\n") as err:
            try:
                run = supervise(argv, wt, keep, err)
                detail = None
            except OSError as e:  # claude not found, or not runnable
                detail = one_line(f"cannot start {argv[0]}: {e}")
    finally:
        cause, why = exit_cause(run) if detail is None else ("error", detail)
        status.update(cause=cause, detail=why, exit_code=run["exit_code"],
                      ended=now().strftime("%Y-%m-%dT%H:%M:%SZ"))
        write_status(directory / "status.json", status)
    print(f"{sprint}: {cause}" + (f" ({why})" if why else "") + f"; stream {directory / name}")
    return 1 if cause == "error" else 0


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
    lines = [head, f"start {str(st.get('start_ref') or '')[:10]}, started {st.get('started')}"]
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
    st = sub.add_parser("runner", help="run a sprint headless in a worktree of its own").add_subparsers(
        dest="action", required=True).add_parser("start", help="start the run")
    st.add_argument("sprint", type=sprint_arg)
    st.add_argument("--landed", type=positive, metavar="K", help="the run stops after K landed items")
    rs = sub.add_parser("runner-status", help="what the recorded run did, in under 1000 characters")
    rs.add_argument("sprint", type=sprint_arg)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "runner-status":
            return runner_status(a.sprint, ROOT)
        return runner_start(a.sprint, a.landed, ROOT)
    except bl_base.Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
