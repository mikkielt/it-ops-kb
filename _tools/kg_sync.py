"""The sync run of kbgit.py (kb/_self/git.md, Workflow): fetch, rebase onto the remote branch (its conflicts in the
mechanical paths resolved with `fix`), fix, the gate and the push, `kbgit.py sync` and the rebase `bridge` reuses. Runs
git in KB, this module's own copy of the repository directory (a caller may point it at a scratch clone), and the
`kbgit.py` and checks of that tree as subprocesses. What belongs to the trailers and the hooks (the trailer audit, the
message of the fix commit, whether the commit hooks are installed) comes in as a `Host` the facade builds, since this
module imports no facade. Standard library only; kbgit.py imports it.
"""
import csv, datetime, json, os, re, shlex, subprocess, sys, time
from collections import namedtuple
from pathlib import Path

import kbcommon
import kbpublic
import kg_lane
import kg_lock
import kg_merge
from kg_base import BASELINE, KB, repo_roots
from kg_merge import has_markers

# What sync takes from the facade: audit(rng, quiet=False, work_state_on=True) is kbgit's trailer_audit, message(body)
# the commit message with its KB-* trailers computed for the staged change, hooks_ok(core.hooksPath) whether the commit
# hooks are installed.
Host = namedtuple("Host", "audit message hooks_ok")


def git_run(*args, stdin=None):
    return kg_merge.git_run(*args, stdin=stdin, kb=KB)


def git(*args, stdin=None):
    return kg_merge.git(*args, stdin=stdin, kb=KB)


def read(rel):
    return kg_merge.read(rel, kb=KB)


def rev_parse(rev):
    return (git("rev-parse", "-q", "--verify", rev + "^{commit}") or "").strip() or None


def git_path(name):
    p = (git("rev-parse", "--git-path", name) or "").strip()
    return os.path.join(KB, p) if p else None


# Paths whose rebase conflicts are resolved mechanically: the union ledgers and the generated files. `fix` rebuilds
# them (the coverage page only when its markers are inside the table; otherwise fix reports it and sync stops).
def mechanical():
    """Every root's union ledgers, _coverage.csv and coverage page, and the lint baseline (repository paths)."""
    out = {BASELINE}
    try:
        rs = repo_roots()
    except kbcommon.RootError:
        rs = []  # a malformed root: sync still resolves the public root's ledgers; check.py names the root
    for r in rs or [None]:
        path = r.path if r else kbcommon.PUBLIC
        L = lambda n: kbcommon.repo_rel(n, path)  # noqa: E731
        out |= {L(kbcommon.SOURCES), L(kbcommon.STATE), L(kbcommon.ANSWERS), L(kbcommon.GAPS), L(kbcommon.CONFLICTS),
                L(kbcommon.COVERAGE_CSV), L(kbcommon.COVERAGE_MD)}
    return frozenset(out)


MECHANICAL = mechanical()
IN_PROGRESS = (("rebase-merge", "a rebase", "git rebase --continue, or git rebase --abort"),
               ("rebase-apply", "a rebase", "git rebase --continue, or git rebase --abort"),
               ("MERGE_HEAD", "a merge", "git merge --continue, or git merge --abort"),
               ("CHERRY_PICK_HEAD", "a cherry-pick", "git cherry-pick --continue, or git cherry-pick --abort"),
               ("REVERT_HEAD", "a revert", "git revert --continue, or git revert --abort"))
NO_EDITOR = {"GIT_EDITOR": "true", "GIT_SEQUENCE_EDITOR": "true"}
# Every rebase sync runs or tells a human to run. git's union driver (and plain conflicts) merge at the "zealous" level:
# lines both sides end (or start) with are pulled out of the conflict and kept once. Two answers that end in the same
# `_Agent: kb-research_` footer then interleave: the second is spliced into the first, above its footer, and the
# rebased commit edits the other side's section (its KB-Answers trailer names it). diff3 caps the level at "eager",
# which keeps each side's block whole (and adds the base to conflict markers, which fix and /kb-git-sync read anyway).
MERGE_CFG = ("-c", "merge.conflictStyle=diff3")
REBASE = (*MERGE_CFG, "rebase")
REBASE_HINT = "git -c merge.conflictStyle=diff3 rebase"
FIX_COMMIT = "chore(kb): kbgit fix after sync"
REJECTED = re.compile(r"\[rejected\]|non-fast-forward|fetch first|stale info|cannot lock ref .* but expected", re.I)
# A push rejected because the remote moved is tried again, after a pause that doubles: PUSH_TRIES rounds in all (the
# first included), PUSH_PAUSE_S seconds before the second, doubling up to PUSH_PAUSE_MAX_S. The environment overrides
# them (tests set the pause to 0 and never sleep).
PUSH_TRIES = 6
PUSH_PAUSE_S = 2.0
PUSH_PAUSE_MAX_S = 30.0


def env_number(name, default, cast=float):
    """The environment variable NAME as a number, DEFAULT when it is unset or not one (a negative is 0)."""
    try:
        return max(cast(os.environ[name]), 0)
    except (KeyError, ValueError):
        return default


def push_tries():
    return max(int(env_number("KB_SYNC_PUSH_TRIES", PUSH_TRIES, int)), 1)


def push_pause(n):
    """Seconds to wait after the Nth rejected try (1-based): PUSH_PAUSE_S doubling, capped at PUSH_PAUSE_MAX_S."""
    first = env_number("KB_SYNC_PUSH_PAUSE_S", PUSH_PAUSE_S)
    return min(first * 2 ** (n - 1), max(env_number("KB_SYNC_PUSH_PAUSE_MAX_S", PUSH_PAUSE_MAX_S), first))


def pause(seconds):
    if seconds > 0:
        time.sleep(seconds)


def gitx(*args, env=None):
    """(exit code, stdout + stderr text) of a git command in the kb; (127, message) when git cannot be started."""
    try:
        p = subprocess.run(["git", *args], cwd=KB, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env={**os.environ, **(env or {})})
    except OSError as e:
        return 127, str(e)
    return p.returncode, p.stdout + p.stderr


def gitx_net(*args, env=None):
    """gitx for a network call (fetch, push) with the bounded wait of kg_lock.run_git_bounded: past it git's process
    group is ended and the result is (124, the timeout message), which the callers report as a failed fetch or push;
    nothing is pushed by a run that gave up."""
    try:
        p = kg_lock.run_git_bounded(args, KB, f"kbgit.py sync: git {args[0]}", env={**os.environ, **(env or {})})
    except kg_lock.GitNetworkTimeout as e:
        return 124, str(e)
    except OSError as e:
        return 127, str(e)
    return p.returncode, p.stdout + p.stderr


def tool(name, *args, env=None):
    """(exit code, output) of a kb tool in this checkout (the files on disk, which a rebase may have updated). The
    re-run marker (REEXEC_ENV) and the sides it carries (SIDES_ENV) are not passed on: they belong to this sync, not to
    a sync a tool starts."""
    base = {k: v for k, v in os.environ.items() if k not in (REEXEC_ENV, SIDES_ENV)}
    p = subprocess.run([sys.executable, os.path.join(KB, "_tools", name), *args], cwd=KB, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env={**base, **(env or {})})
    return p.returncode, p.stdout + p.stderr


# A rebase that brings a new kbgit.py, or a new version of a _tools module it loaded (kblane, kbpublic, kg_merge...),
# leaves this process running the code it loaded before. sync then re-runs itself once, as a new process with the same
# arguments on the rebased tree, so the new rules (lanes, the gate) decide the push that brought them; the re-run finds
# nothing behind and goes on. REEXEC_ENV marks the re-run: a re-run whose own rebase (the remote moved again) changed
# the code once more stops with exit 3 instead of a second re-run, and so does a sync with no command line to repeat.
# The re-run sees its tree already rebased (nothing behind), so it cannot tell the merge's sides: SIDES_ENV carries the
# rebase's base, upstream and the HEAD it started from, and the re-run gives them to fix while the upstream is the same,
# so an id both sides added is still renumbered, not left as exit 3 `sides unknown`.
REEXEC_ENV = "KB_SYNC_REEXEC"
SIDES_ENV = "KB_SYNC_SIDES"


def inherited_sides(up):
    """(base, orig) the sync that re-ran this one rebased from, when this is a re-run and UP is the upstream that sync
    rebased onto; else None (the remote moved again, or this is no re-run, or the value is not what rerun_sync wrote)."""
    if os.environ.get(REEXEC_ENV) != "1":
        return None
    try:
        d = json.loads(os.environ.get(SIDES_ENV, ""))
    except ValueError:
        return None
    ok = isinstance(d, dict) and up and d.get("up") == up and all(isinstance(d.get(k), str) and d[k] for k in ("base", "orig"))
    return (d["base"], d["orig"]) if ok else None


def loaded_tools():
    """The repository paths (`_tools/NAME.py`) of the _tools modules this process has loaded, sorted."""
    tools = Path(KB, "_tools").resolve()
    out = set()
    for m in list(sys.modules.values()):
        f = getattr(m, "__file__", None)
        if f and f.endswith(".py") and Path(f).resolve().parent == tools:
            out.add("_tools/" + Path(f).name)
    return sorted(out)


def code_changed(before, after="HEAD"):
    """The loaded _tools modules (loaded_tools) whose files differ between BEFORE and AFTER, sorted. BEFORE is the
    commit the code was loaded from: sync refuses a dirty tree, so the files on disk were BEFORE's."""
    out = git("diff", "--name-only", "-z", before, after, "--", *loaded_tools()) or ""
    return sorted(p for p in out.split("\0") if p)


def rerun_sync(a, r, changed, sides=None):
    """The rebase changed CHANGED, code this process runs: run sync again, once, with the rebased code and return its
    exit code. SIDES, (base, upstream, orig) of the rebase, goes to the re-run in SIDES_ENV. Inside a re-run already, or
    without a command line to repeat (sync started by bridge): exit 3."""
    print("the rebase changed the code sync runs: " + ", ".join(changed))
    argv = getattr(a, "rerun", None)
    if not argv or os.environ.get(REEXEC_ENV) == "1":
        print("stopped: the rebase is complete; nothing fixed, committed or pushed. Run the same kbgit.py sync command "
              "again, so the rebased code decides the push")
        r["pushed"] = "no (rerun sync: the rebase changed its code)"
        return 3
    print("re-running sync once with the rebased code", flush=True)
    sys.stderr.flush()
    env = {**os.environ, REEXEC_ENV: "1"}
    env.pop(SIDES_ENV, None)
    if sides:
        env[SIDES_ENV] = json.dumps(dict(zip(("base", "up", "orig"), sides)))
    p = subprocess.run([sys.executable, *argv], cwd=KB, env=env)
    r["rerun"] = p.returncode
    return p.returncode


def in_progress():
    for name, what, how in IN_PROGRESS:
        p = git_path(name)
        if p and os.path.exists(p):
            return what, how
    return None


def rebasing():
    return any(os.path.isdir(git_path(n) or "") for n in ("rebase-merge", "rebase-apply"))


def dirty_paths():
    """(staged, unstaged) tracked paths that differ from HEAD / the index (untracked files do not count)."""
    return names("diff", "--cached", "--name-only"), names("diff", "--name-only")


def names(*args):
    return sorted(p for p in (git(*args, "-z") or "").split("\0") if p)


def short(rev):
    return (rev or "")[:9]


# The session that runs sync, matched against the `Claude-Session: <url>` trailer Claude Code adds to the commits of a
# cloud or Remote Control session. In order: --session, KB_SESSION (set but empty: unknown), a cloud session's
# CLAUDE_CODE_REMOTE_SESSION_ID (`cse_<id>`, the url's `session_<id>`), a Remote Control session's
# CLAUDE_CODE_BRIDGE_SESSION_ID. A session that sets none of them writes no such trailer either: unknown, never refused.
SESSION_TRAILER = "Claude-Session"
SESSION_ENV = ("CLAUDE_CODE_REMOTE_SESSION_ID", "CLAUDE_CODE_BRIDGE_SESSION_ID")


def session_key(value):
    """The comparable form of a session: the url's last path segment, `cse_` read as `session_`; "" when empty."""
    v = (value or "").strip().rstrip("/").rsplit("/", 1)[-1]
    return "session_" + v[len("cse_"):] if v.startswith("cse_") else v


def current_session(arg=None, env=None):
    """The session sync runs in (session_key form), or "" when unknown."""
    env = os.environ if env is None else env
    if arg is not None:
        return session_key(arg)
    if "KB_SESSION" in env:
        return session_key(env["KB_SESSION"])
    return next((session_key(env[k]) for k in SESSION_ENV if env.get(k, "").strip()), "")


def foreign_session_commits(rev, remote, up, session):
    """[(short, subject, sessions)] of REV's commits not on REMOTE (UP, the remote's tracking refs) whose
    Claude-Session trailers name a session other than SESSION; [] when SESSION is unknown. A commit with no such
    trailer (a person's, a tool's) is never foreign."""
    if not session:
        return []
    out = git("log", f"--format=%h%x1f%s%x1f%(trailers:key={SESSION_TRAILER},valueonly,unfold,separator=%x1d)%x1e",
              rev, "--not", *([up] if up else []), f"--remotes={remote}") or ""
    found = []
    for rec in out.split("\x1e"):
        parts = rec.strip("\n").split("\x1f")
        if len(parts) != 3:
            continue
        sessions = [session_key(s) for s in parts[2].split("\x1d") if s.strip()]
        if sessions and session not in sessions:
            found.append((parts[0], parts[1], sessions))
    return found


def fix_args(base, up, orig):
    """kbgit.py fix arguments after rebasing orig onto up: up is already pushed, so its ids and answer ids stay."""
    return ["fix"] + (["--base", base, "--upstream", up, "--side", orig] if base else [])


def renumbered(output):
    """fix's report lines about renumbered source ids and renamed answer ids."""
    return [ln.strip() for ln in output.splitlines() if " collision: " in ln]


def conflict_help(r, up, base, orig, manual, mech, step):
    fix_cmd = "python3 _tools/kbgit.py " + " ".join(fix_args(base, up, orig))
    print(f"CONFLICT rebasing onto {r['target']}, at local commit {step}")
    for p in manual:
        print(f"needs-human: {p}")
    for p in mech:
        print(f"mechanical: {p}  (kbgit.py fix rebuilds it)")
    print(f"sync-state: base={base} upstream={up} orig_head={orig}")
    print("The rebase is still in progress; nothing was pushed. Never resolve article text by taking one side blindly.")
    print("Resolve (or run /kb-git-sync), one command at a time:")
    print("  edit the needs-human files: keep both sides' facts, no conflict markers left")
    print(f"  {fix_cmd}")
    print("  git add <the resolved paths>")
    print(f"  GIT_EDITOR=true {REBASE_HINT} --continue   (later local commits may stop again)")
    print("  python3 _tools/kbgit.py sync" + (" --push" if r.get("push") else ""))
    print(f"Or give up: git rebase --abort  (back to {short(orig)}, nothing lost)")


def do_rebase(r, up, base, orig, since=None):
    """Rebase HEAD onto up, resolving conflicts in MECHANICAL paths with fix. 0 done, 2 git refused, 3 manual. SINCE
    (the bridge): only the commits after it, `git rebase --onto up since`."""
    code, out = gitx(*REBASE, *(["--onto", up, since] if since else [up]), env=NO_EDITOR)
    for _ in range(1000):
        if not rebasing():
            if code:
                print("git rebase failed:\n" + out.rstrip())
                return 2
            return 0
        conflicted = names("diff", "--name-only", "--diff-filter=U")
        stopped = git("log", "-1", "--format=%h %s", "REBASE_HEAD") or ""
        step = stopped.strip() or "(unknown)"
        if not conflicted:
            if git_run("diff", "--cached", "--quiet", "HEAD").returncode == 0 and \
                    git_run("diff", "--quiet").returncode == 0:
                code, out = gitx(*REBASE, "--skip", env=NO_EDITOR)
                r["notes"].append(f"dropped {step}: empty after the rebase")
            else:
                code, out = gitx(*REBASE, "--continue", env=NO_EDITOR)
                if code and rebasing() and not names("diff", "--name-only", "--diff-filter=U"):
                    print(out.rstrip())
                    conflict_help(r, up, base, orig, ["(rebase stopped without a conflict; see git's message above)"], [], step)
                    return 3
            continue
        manual = [p for p in conflicted if p not in MECHANICAL]
        mech = [p for p in conflicted if p in MECHANICAL]
        if manual:
            conflict_help(r, up, base, orig, manual, mech, step)
            return 3
        fcode, fout = tool("kbgit.py", *fix_args(base, up, orig))
        if fcode:
            print(fout.rstrip())
            probs = [ln[len("PROBLEM "):] for ln in fout.splitlines() if ln.startswith("PROBLEM ")]
            conflict_help(r, up, base, orig, [p for p in mech if any(p in x for x in probs)] or mech, [], step)
            return 3
        left = [p for p in conflicted if has_markers(read(p))]
        if left:
            conflict_help(r, up, base, orig, left, [], step)
            return 3
        r["renumbered"] += renumbered(fout)
        r["auto"].append(f"{step}: {', '.join(mech)}")
        gitx("add", "-u")
        code, out = gitx(*REBASE, "--continue", env=NO_EDITOR)
    print("git rebase did not finish after 1000 steps; inspect with git status")
    return 3


def commit_fix(r, host):
    """Commit what fix changed as its own small commit, with KB-* trailers computed here (hook or not)."""
    gitx("add", "-u")
    body = f"{FIX_COMMIT}\n\nkbgit.py fix after rebasing onto {r['target']}: " + \
           ("renumbered colliding ids and their citations; " if r["renumbered"] else "") + \
           "merged the union-merged ledger rows and rebuilt the generated index.\n"
    msg = host.message(body)
    p = subprocess.run(["git", "commit", "-q", "--no-verify", "--cleanup=whitespace", "-F", "-"], cwd=KB,
                       input=msg, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        print("git commit of the fix failed:\n" + (p.stdout + p.stderr).rstrip())
        return False
    r["fix_commit"] = rev_parse("HEAD")
    return True


def refresh_trailers(r, up, host):
    """Rewrite the KB-* trailers of the unpushed commits whose trailers no longer match their diff
    (a rebase that resolved conflicts or renumbered ids changes the diffs). Only up..HEAD is touched."""
    audit = host.audit(f"{up}..HEAD", quiet=True, work_state_on=False)
    if not audit or not audit[2]:
        return True
    exe = " ".join(shlex.quote(x) for x in (sys.executable, os.path.join(KB, "_tools", "kbgit.py"), "trailers", "--amend"))
    code, out = gitx(*REBASE, "--exec", exe, up, env=NO_EDITOR)
    if code or rebasing():
        print("refreshing trailers failed:\n" + out.rstrip())
        if rebasing():
            gitx("rebase", "--abort")
        return False
    r["refreshed"] = len(audit[2])
    return True


def gate_paths(up):
    """The paths the gate judges: changed from UP's merge base to HEAD, plus the working tree (the pre-push hook
    checks it too); None when there is no UP (a new branch), which runs every check. A rename lists its old and
    its new path (--no-renames), so a test file renamed out of _tools/test_*.py still counts as a changed test."""
    if not up:
        return None
    base = (git("merge-base", up, "HEAD") or "").strip()
    if not base:
        return None
    staged, unstaged = dirty_paths()
    return set(names("diff", "--name-only", "--no-renames", base, "HEAD")) | set(staged) | set(unstaged)


def artifact_paths():
    """Every root's pinned artifact files (_artifacts.csv `path`), as repository paths."""
    out = set()
    for root in kbcommon.roots():
        p = os.path.join(root.path, "_artifacts.csv")
        if os.path.exists(p):
            with open(p, encoding="utf-8", newline="") as f:
                out |= {kbcommon.repo_rel(row["path"], root.path) for row in csv.DictReader(f) if row.get("path")}
    return out


TEST_FILE = re.compile(r"_tools/test_[^/]*\.py")


def gate_needs(paths):
    """{check: the reason it runs, or None to skip}. Each check runs only when a path it reads changed; with no
    known paths (None) every check runs."""
    if paths is None:
        return {k: "no base to compare with" for k in ("check", "fetch", "doc2query", "selfdoc", "backlog", "querylog",
                                                       "dropped", "selectors")}
    ps = {p.replace("\\", "/") for p in paths}
    kb = {p for p in ps if p.startswith("kb/")}
    tools = {p for p in ps if p.startswith("_tools/")}
    items = {p for p in kb if p.startswith(kbcommon.repo_rel(kbcommon.SELF) + "/backlog/")}
    store = {p for p in kb if p.startswith("kb/_querylog/")}
    content = kb - items - store
    arts = artifact_paths()

    def why(hit, what):
        return f"{what} changed: {sorted(hit)[0]}" + (f" (+{len(hit) - 1})" if len(hit) > 1 else "") if hit else None
    root = {p for p in ps if "/" not in p}  # README.md, AGENTS.md: check.py validates their citations too
    return {"check": why(content | tools | root, "kb content, a root file or a tool"),
            "fetch": why({p for p in ps if p in arts or p.endswith(("/_artifacts.csv", "/_sources.csv")) or p == "_tools/fetch.py"},
                         "a pinned artifact or its row"),
            "doc2query": why({p for p in content if p.endswith(".md") or "/doc2query/" in p} | ({"_tools/doc2query.py"} & ps),
                             "an article or its expansions"),
            "selfdoc": why(ps - content - items - store, "a file kb/_self describes"),
            "backlog": why(items | ({"_tools/backlog.py"} & ps), "a backlog item"),
            "querylog": why(store, "the query log store"),
            "dropped": why(ps & {"_tools/test_ids_dropped.txt", "_tools/perfcheck.py"}, "the dropped test ids"),
            "selectors": why({p for p in tools if TEST_FILE.fullmatch(p)}, "a test file")}  # a deleted or renamed one too


EVAL_SETS = ("lookup_eval.csv", "lookup_heldout.csv")  # the tuned eval set and the held-out one beside it
HELDOUT_SET = EVAL_SETS[1]


def heldout_checks(paths):
    """[(repository path of a lookup_heldout.csv, why its reword check runs)]: the held-out file beside each changed
    eval set (PATHS None: the held-out file of every root). `rag.py eval --file` on it prints a REWORD line, and exits
    1, for a held-out row that rewords a tuned row, which nothing else in a landing reads."""
    if paths is None:
        found = {kbcommon.repo_rel(os.path.join(kbcommon.DATA_DIR, HELDOUT_SET), r.path): "no base to compare with"
                 for r in kbcommon.roots()}
    else:
        changed = [p.replace("\\", "/") for p in paths]
        found = {p.rpartition("/")[0] + "/" + HELDOUT_SET: f"an eval set changed: {p}"
                 for p in sorted(changed) if p.rpartition("/")[2] in EVAL_SETS and "/" in p}
    return [(p, why) for p, why in sorted(found.items()) if Path(KB, p).is_file()]


GATE_NOTE = re.compile(r"tests\.py --changed \S+: (no test can be affected by the changed paths"
                       r"|kb content only, the suite without the git scenarios|the whole suite)")


def gate_name(label):
    """A check's label as a row token: lower case, one dash for each run of other characters, no revision."""
    first = "check-trailers" if label.startswith("check-trailers") else label.split(" --since")[0]
    return (re.sub(r"[^a-z0-9_.]+", "-", first.lower()).strip("-") or "check")[:40]


GATE_DIR = Path("_cache", "gate")  # under the repository: where a failed check's whole output is kept (git-ignored)
GATE_KEEP = 10  # files kept there, the newest by modification time
GATE_TAIL = 25  # lines of a failed check's output printed in the gate's own output
FAILED_ID = re.compile(r"^(?:FAILED|ERROR) ", re.M)  # a test id line of pytest's short summary


def gate_output_file(label, out):
    """Write OUT, the whole output of the failed check LABEL, to a new file `<UTC time>-<n>-<check>.txt` (n has three digits) under
    _cache/gate (n counts up until the name is free, so a retry in the same second never overwrites an earlier file),
    keep the GATE_KEEP newest files there, and return (path, the count of FAILED and ERROR lines in OUT). Best effort:
    an unwritable directory gives one stderr note and None, never an exception."""
    try:
        d = Path(KB) / GATE_DIR
        d.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        for n in range(1, 1000):
            path = d / f"{stamp}-{n:03d}-{gate_name(label)}.txt"
            try:
                with open(path, "x", encoding="utf-8", newline="\n") as f:
                    f.write(out)
                break
            except FileExistsError:
                continue
        else:
            raise OSError("no free file name")
        try:
            old = sorted(d.glob("*.txt"), key=lambda p: (p.stat().st_mtime_ns, p.name), reverse=True)[GATE_KEEP:]
        except OSError:
            old = []
        for p in old:
            try:
                p.unlink()
            except OSError:
                pass
        return path, len(FAILED_ID.findall(out))
    except OSError as e:
        print(f"note: could not keep the output of {label} under {GATE_DIR.as_posix()}: {e}", file=sys.stderr)
        return None


def gate_mark(r, label, why=None, code=None, since=None):
    """Append the row of one check to r["gate_rows"]: skipped (WHY, a token) or ran (its exit and the ms since SINCE)."""
    row = {"name": gate_name(label), "ran": why is None}
    if why:
        row["why"] = why
    else:
        row.update(exit=code, ms=int((time.monotonic() - since) * 1000))
    r.setdefault("gate_rows", []).append(row)


def gate_scope(r, skipped, out):
    """r["scope"] (a closed token) and r["scope_line"] (what a reader needs) of the gate's tests.py step: SKIPPED
    names why it did not run, else OUT is its output, whose `--changed` line gives the selection."""
    m = GATE_NOTE.search(out or "")
    if skipped:
        r["scope"], r["scope_line"] = ("skipped", "tests.py did not run (KB_SYNC_NO_TESTS=1)") if skipped == "no-tests-env" else (
            "none", "tests.py did not run, no path it reads changed")
    elif m:
        r["scope"] = "none" if m.group(1).startswith("no test") else "changed" if m.group(1).startswith("kb") else "all"
        r["scope_line"] = m.group(0)
    else:
        r["scope"], r["scope_line"] = "all", "the suite without the git scenarios"


def record_gate(r, code):
    """Append the ops row `sync.gate` of this sync run (r["gate_rows"] of its last gate, the ms of every gate run, the
    scope, the count of paths the gate read, the push outcome, the exit); best effort: nothing when no gate ran or
    capture is off, no exception and no output."""
    try:
        if not r.get("gate_rows"):
            return None
        import ql_capture
        pushed = r.get("pushed", "")
        push = "pushed" if pushed.startswith("yes") else "rejected" if "rejected" in pushed else "none"
        return ql_capture.record("ops", event="sync.gate", ms=int(r.get("gate_ms", 0)), checks=r["gate_rows"][:40],
                                 scope=r.get("scope"), files=r.get("gate_files"), push=push, exit=code)
    except Exception:  # noqa: BLE001 - a sync never fails for its log
        return None


SELECTOR_ROW = re.compile(r"^\s*\S+\s+(?P<flag>NONE|error)\s+.+?\s(?P<id>(?:EP|ST|TK|SB|BG)-[a-z2-7]{8})\s[“(]")


def item_done(iid):
    """True when the item file of IID says `status` done; an unreadable file is not done."""
    try:
        with open(Path(KB, kbcommon.repo_rel(kbcommon.SELF), "backlog", f"{iid}.json"), encoding="utf-8") as f:
            return json.load(f).get("status") == "done"
    except (OSError, ValueError, AttributeError):
        return False


def selector_gate(out):
    """(exit code, output) of the gate's `backlog.py selectors` run, whose own exit is always 0. A NONE row (the
    selector selects no test) of a done item refuses: `selectors` lists a done item only when its sprint is active, and
    the sprint review reruns its check. A NONE row of any other item prints a warning (an open item's test may be yet to
    write), and so does an `error` row (a failed collection: the suite run beside it fails on a test file that does not
    collect)."""
    refused, warned = [], []
    for ln in out.splitlines():
        m = SELECTOR_ROW.match(ln)
        if not m:
            continue
        if m["flag"] == "error":
            warned.append("warning: a selector failed to collect, not refused: " + ln.strip())
        elif item_done(m["id"]):
            refused.append("refused: the check of a done item selects no test (restore the test or point the check at "
                           "one that exists): " + ln.strip())
        else:
            warned.append("warning: the selector of an item not done selects no test, not refused: " + ln.strip())
    for ln in warned:
        print(ln)
    return int(bool(refused)), "\n".join(refused + [f"selectors: refused={len(refused)} warned={len(warned)}"])


def gate(r, up, host, fix_check=False, since=None):
    """The checks the changed paths (gate_paths) can break, then check-trailers on up..HEAD:
    check.py for kb content, a root file (README.md, AGENTS.md) or a tool, fetch.py --offline for a pinned artifact or its row, doc2query.py stale for an
    article or its expansions, selfdoc.py stale --since UP for a file kb/_self describes (a `Self-Reviewed:` trailer
    clears a doc), backlog.py check for backlog items, backlog.py selectors for a changed, deleted or renamed
    _tools/test_*.py file (selector_gate: refused for a done item whose check selects no test), querylog.py check for the
    query log store, rag.py eval --file on the lookup_heldout.csv beside a changed lookup_eval.csv or
    lookup_heldout.csv (heldout_checks: refused for a REWORD line), and tests.py
    --changed UP (KB_TESTS_FAST=1: nothing for backlog items and the query log store, the suite without the git
    scenarios for kb content only, the whole suite for any other path).
    `fix_check` (the pre-push hook) adds `fix --check` and build_index.py --check first; sync runs fix itself, which
    rebuilds the generated files, so its gate has neither. A skipped check is listed with why.
    SINCE (a retry after a rejected push): the commit the last green gate judged. Each check then reads only the paths
    that differ between SINCE and HEAD, so a rebase that changed none of them re-runs nothing but check-trailers."""
    results, t_gate = [], time.monotonic()
    r["gate_rows"], r["gate_outputs"], r["scope"] = [], [], None
    paths = gate_paths(up)
    if since:
        staged, unstaged = dirty_paths()
        paths = set(names("diff", "--name-only", "--no-renames", since, "HEAD")) | set(staged) | set(unstaged)
    r["gate_files"] = None if paths is None else len(paths)
    need = gate_needs(paths)
    if since:
        need["tests"] = "always" if any(need[k] for k in ("check", "fetch", "doc2query", "selfdoc")) else None
    checks = [("kbgit.py fix --check", "kbgit.py", ["fix", "--check"], None, "pre-push"),
              ("build_index.py --check", "build_index.py", ["--check"], None, "pre-push")] if fix_check else []
    checks += [("check.py", "check.py", [], None, need["check"]),
               ("fetch.py --offline", "fetch.py", ["--offline"], None, need["fetch"]),
               ("doc2query.py stale", "doc2query.py", ["stale"], None, need["doc2query"]),
               ("backlog.py check", "backlog.py", ["check"], None, need["backlog"]),
               ("backlog.py selectors", "backlog.py", ["selectors"], None, need["selectors"]),
               ("querylog.py check", "querylog.py", ["check"], None, need["querylog"])]
    heldout = heldout_checks(paths)
    for rel, why in heldout or [(None, None)]:  # --min 1: a held-out row that fails to answer is the measurement, not a refusal
        checks.append((f"rag.py eval --file {rel}" if rel else "rag.py eval (held-out reword check)", "rag.py",
                       ["eval", "--file", rel, "--min", "1"] if rel else [], None, why))
    if up:
        checks.append((f"selfdoc.py stale --since {short(up)}", "selfdoc.py", ["stale", "--since", up], None, need["selfdoc"]))
        checks.append((f"perfcheck.py dropped --since {short(up)}", "perfcheck.py", ["dropped", "--since", up], None,
                       need["dropped"]))  # warns (exit 0) of a dropped test file whose live modules' tests went nowhere
    checks.append(("tests.py (changed)" if up else "tests.py (fast)", "tests.py", ["--changed", up] if up else [],
                   {"KB_TESTS_FAST": "1"}, need.get("tests", "always")))
    for label, name, args, env, reason in checks:
        if name == "tests.py" and os.environ.get("KB_SYNC_NO_TESTS") == "1":
            results.append((label, "skipped (KB_SYNC_NO_TESTS=1)", True))
            gate_mark(r, label, "no-tests-env"), gate_scope(r, "no-tests-env", "")
            continue
        if not reason:
            results.append((label, "skipped: no path it reads changed", True))
            gate_mark(r, label, "no-path-changed")
            if name == "tests.py":
                gate_scope(r, "no-path-changed", "")
            continue
        t0 = time.monotonic()
        code, out = tool(name, *args, env=env)
        if args[:1] == ["selectors"] and not code:
            code, out = selector_gate(out)
        gate_mark(r, label, code=code, since=t0)
        if name == "tests.py":
            gate_scope(r, None, out)
        tail = [ln for ln in out.strip().splitlines() if ln.strip()][-1:] or [""]
        results.append((label, ("ok" if code == 0 else f"FAILED (exit {code})") + f": {tail[0][:100]}", code == 0))
        if code:
            print(f"--- {label} output (last lines)\n" + "\n".join(out.strip().splitlines()[-GATE_TAIL:]))
            kept = gate_output_file(label, out)
            if kept:
                line = f"{kept[1]} test ids"
                r["gate_outputs"].append((label, f"{kept[0]} ({line})"))
                print(f"--- {label} whole output: {kept[0]} ({line})")
    rng = f"{up}..HEAD" if up else "HEAD"
    t0 = time.monotonic()
    audit = host.audit(rng, quiet=True)
    gate_mark(r, f"check-trailers {rng}", code=int(audit is None or bool(audit[2])), since=t0)
    if audit is None:
        results.append((f"check-trailers {rng}", "FAILED: not a valid range", False))
    else:
        for _, lines in audit[2]:
            print("\n".join(lines))
        results.append((f"check-trailers {r['target']}..HEAD", f"{'ok' if not audit[2] else 'FAILED'}: commits={audit[0]} bad={len(audit[2])}",
                        not audit[2]))
    r["gate"] = results
    r["gate_ms"] = r.get("gate_ms", 0) + int((time.monotonic() - t_gate) * 1000)
    return all(ok for _, _, ok in results)


NO_PUSH_OPTIONS = re.compile(r"receiving end does not support push options", re.I)


def push_options(target):
    """The merge-request push options of a code branch, in the order they are sent."""
    return ["merge_request.create", f"merge_request.target={target}", "merge_request.auto_merge",
            "merge_request.remove_source_branch"]


def push_branch(a, r, branch, target):
    """Push HEAD as BRANCH (code/<id>) with the merge-request push options; a server without push options gets the
    same push without them. An existing branch that is not an ancestor of HEAD is replaced with a lease on the tip
    fetched here (code/* only: main is never forced). Returns an exit code."""
    if not branch.startswith(kg_lane.CODE_BRANCH_PREFIX):
        print(f"refused: {branch} is not a {kg_lane.CODE_BRANCH_PREFIX}* branch")
        return 2
    ref = f"refs/heads/{branch}"
    tracking = f"refs/remotes/{a.remote}/{branch}"
    code, out = gitx_net("fetch", "--quiet", a.remote, f"+{ref}:{tracking}")
    if code and not re.search(r"couldn't find remote ref", out, re.I):
        print(f"git fetch {a.remote} {branch} failed:\n" + out.rstrip())
        return 2
    tip = None if code else rev_parse(tracking)
    argv = ["push"]
    if tip and gitx("merge-base", "--is-ancestor", tip, "HEAD")[0] != 0:
        argv.append(f"--force-with-lease={ref}:{tip}")
        print(f"{branch} on {a.remote} is not an ancestor of the rebased work; replacing it with a lease on {short(tip)}")
    elif not tip:
        argv.append(f"--force-with-lease={ref}:")  # expects no such branch
    opts = push_options(a.branch)
    sent = [x for o in opts for x in ("-o", o)]
    dest = [a.remote, f"HEAD:{ref}"]
    code, out = gitx_net(*argv, *sent, *dest, env={"KB_GATE_DONE": "1"})  # gated above
    if code and NO_PUSH_OPTIONS.search(out):
        code, out = gitx_net(*argv, *dest, env={"KB_GATE_DONE": "1"})
        opts = None
    if code:
        if REJECTED.search(out):
            print(f"push of {branch} refused: it moved on {a.remote} since it was fetched, nothing was overwritten:\n" + out.rstrip())
            r["pushed"] = f"no ({branch} moved on {a.remote})"
        else:
            print("git push failed:\n" + out.rstrip())
            r["pushed"] = "no (push failed)"
        return 1
    r["pushed"] = f"yes: branch {branch} on {a.remote} ({short(rev_parse('HEAD'))}); {target} did not move"
    if opts:
        r["notes"].append(f"merge request for {a.branch} requested with push options: {', '.join(opts)}")
    else:
        r["notes"].append(f"{a.remote} does not support push options: open a merge or pull request from {branch} "
                          f"into {a.branch}")
    r["notes"].append(f"local {a.branch} is unchanged; the commits stay local until the merge request merges, a later "
                      "sync then finds them on the integration branch")
    return 0


def sync_once(a, r, host):
    """One fetch -> rebase -> fix -> gate -> push round. Returns an exit code, or "retry" when the push was rejected."""
    target = f"{a.remote}/{a.branch}"
    r["target"] = target
    code, out = gitx_net("fetch", "--quiet", a.remote, f"+refs/heads/{a.branch}:refs/remotes/{target}")
    missing = code and re.search(r"couldn't find remote ref", out, re.I)
    if code and not missing:
        print(f"git fetch {a.remote} failed:\n" + out.rstrip())
        return 2
    up = None if missing else rev_parse(f"refs/remotes/{target}")
    orig = rev_parse("HEAD")
    if up:
        base = (git("merge-base", up, orig) or "").strip()
        if not base:
            print(f"refused: HEAD and {target} share no history")
            return 2
        behind, ahead = (int(x) for x in (git("rev-list", "--left-right", "--count", f"{up}...{orig}") or "0 0").split())
    else:
        base, behind = None, 0
        ahead = int((git("rev-list", "--count", orig) or "0").strip())
    r.update(ahead=ahead, behind=behind)
    print(f"{target}: local {ahead} ahead, {behind} behind" + ("" if up else f" ({a.branch} does not exist on {a.remote} yet)"))

    session = current_session(getattr(a, "session", None))
    foreign = foreign_session_commits(orig, a.remote, up, session) if a.push else []
    if foreign:
        print(f"refused: {len(foreign)} local commit(s) were made by another Claude session in this checkout (this one: "
              f"{session}); the session that made them pushes them, each session from its own clone or worktree; when that "
              f"session no longer exists (a restarted or resumed orchestrator landing its own earlier commits), name it "
              f"with --session <its {SESSION_TRAILER} url> or KB_SESSION=<url>:")
        for h, subject, sessions in foreign:
            print(f"  {h} {subject} ({SESSION_TRAILER}: {', '.join(sessions)})")
        print("nothing rebased, fixed or pushed")
        r["pushed"] = "no (another session's commits)"
        return 1

    if a.dry_run:
        lane, branch = kg_lane.lane_plan(KB, up, orig, a.branch)
        print(f"lane: {lane or f'not routed (a push to {a.branch})'}; " + (f"would push branch {branch} with merge-request push options, {a.branch} would not move"
                                    if branch else f"would push to {target}"))
        if behind:
            incoming, local = names("diff", "--name-only", base, up), names("diff", "--name-only", base, orig)
            both = sorted(set(incoming) & set(local))
            print(f"incoming commits ({behind}):")
            print("  " + "\n  ".join((git("log", "--format=%h %s", "-n", "20", f"{orig}..{up}") or "").splitlines()))
            if ahead:
                print(f"would rebase {ahead} local commit(s) onto {target}; files changed on both sides: {len(both)}")
                for p in both:
                    print(f"  {'mechanical (fix)' if p in MECHANICAL else 'needs a human if it conflicts'}: {p}")
            else:
                print(f"would fast-forward to {target}")
        else:
            print("nothing incoming" + (f"; would push {ahead} commit(s) after the gate" if ahead else "; nothing to push"))
        print("dry run: nothing rebased, fixed, committed or pushed")
        return 0

    if up and behind:
        code = do_rebase(r, up, base, orig)
        if code:
            return code
        r["rebased"] += ahead
        changed = code_changed(orig)
        if changed:
            return rerun_sync(a, r, changed, (base, up, orig) if ahead else None)
    both_sides = bool(up and behind and ahead)
    fix_base, fix_orig = (base, orig) if both_sides else inherited_sides(up) or (None, orig)
    code, out = tool("kbgit.py", *fix_args(fix_base, up, fix_orig))
    if code:
        print(out.rstrip())
        print("kbgit.py fix needs a human (listed above); the rebase is complete and nothing was written or pushed. "
              "Resolve, commit, then rerun python3 _tools/kbgit.py sync --push (or use /kb-git-sync)")
        return 3
    r["renumbered"] += renumbered(out)
    fixed = [ln[len("wrote "):] for ln in out.splitlines() if ln.startswith("wrote ")]
    if fixed:
        r["fixed"] += fixed
        if not commit_fix(r, host):
            return 1
    if up and not refresh_trailers(r, up, host):
        return 1
    since = r.get("gated") if up and r.get("gated") and gitx("cat-file", "-e", r["gated"])[0] == 0 else None
    if not gate(r, up, host, since=since):
        print("gate failed: nothing pushed")
        return 1
    r["gated"] = rev_parse("HEAD")
    if since and all("skipped" in res for lab, res, _ in r["gate"] if not lab.startswith("check-trailers")):
        r["notes"].append("gates not re-run after the rejected push: the rebase changed no path they read")
    if not a.push:
        r["pushed"] = "no (without --push)"
        return 0
    now_ahead = int((git("rev-list", "--count", f"{up}..HEAD" if up else "HEAD") or "0").strip())
    if not now_ahead:
        r["pushed"] = "nothing to push"
        return 0
    lane, branch = kg_lane.lane_plan(KB, up, "HEAD", a.branch)
    if branch:
        print(f"lane: code; pushing branch {branch}, {a.branch} does not move")
        return push_branch(a, r, branch, target)
    code, out = gitx_net("push", a.remote, f"HEAD:refs/heads/{a.branch}", env={"KB_GATE_DONE": "1"})  # gated above
    if code:
        if REJECTED.search(out):
            print(f"push rejected ({target} moved):\n" + out.rstrip())
            return "retry"
        print("git push failed:\n" + out.rstrip())
        r["pushed"] = "no (push failed)"
        return 1
    r["pushed"] = f"yes: {now_ahead} commit(s) to {target} ({short(rev_parse('HEAD'))})"
    return 0


def new_report(push):
    return {"push": push, "ahead": 0, "behind": 0, "rebased": 0, "auto": [], "fixed": [], "renumbered": [], "refreshed": 0,
            "fix_commit": None, "gate": [], "pushed": "no", "notes": []}


def sync_rounds(a, r, host):
    """sync_once, again after each rejected push (the remote moved) with a doubling pause, up to push_tries() rounds
    in all. r["tries"] counts the rounds made; the exit is 1 when the last one was rejected too."""
    tries = push_tries()
    code = None
    for n in range(1, tries + 1):
        r["tries"] = n
        code = sync_once(a, r, host)
        if code != "retry":
            return code
        if n < tries:
            wait = push_pause(n)
            print(f"fetching again and rebasing once more after {wait:g} s (try {n} of {tries} rejected)", flush=True)
            pause(wait)
    print(f"push rejected {tries} times ({a.remote}/{a.branch} keeps moving); giving up, nothing lost locally")
    r["pushed"] = f"no (rejected {tries} times)"
    return 1


def cmd_sync(a, host, r=None):
    a.remote = a.remote or kbpublic.integration_remote(KB)
    if git("rev-parse", "--is-inside-work-tree") is None or not rev_parse("HEAD"):
        print("refused: not a git clone with commits (or git is missing)")
        return 2
    if git("check-ref-format", "--branch", a.branch) is None or git("remote", "get-url", a.remote) is None:
        print(f"refused: no remote {a.remote!r}, or {a.branch!r} is not a valid branch name")
        return 2
    busy = in_progress()
    if busy:
        print(f"refused: {busy[0]} is in progress; finish it first ({busy[1]})")
        return 2
    if kbpublic.is_public(a.remote, KB) and kbpublic.private_commits("HEAD", KB, limit=1):
        print(f"refused: {a.remote} is the public home and HEAD's history touches {', '.join(kbpublic.PRIVATE)}; "
              "sync pushes to the integration remote, publish to the public one (python3 _tools/kbgit.py publish)")
        return 2
    staged, unstaged = dirty_paths()
    refuse = None
    if staged or unstaged:
        lines = ["refused: uncommitted changes; commit them (git commit) or stash them (git stash) first"]
        lines += [f"  staged:   {p}" for p in staged] + [f"  unstaged: {p}" for p in unstaged]
        refuse = "\n".join(lines)
        if not a.dry_run:
            print(refuse)
            return 2
    if not host.hooks_ok(git("config", "--get", "core.hooksPath")):
        print("note: commit hooks not installed (python3 _tools/kbgit.py install-hooks, once for the clone and every "
              "worktree of it); sync repairs trailers of what it rebases")
    r = r if r is not None else new_report(a.push)
    if a.push and not a.dry_run:  # a push moves the integration main: one runner on the host at a time
        try:
            with kg_lock.guarded("kbgit.py sync --push", clone=KB):
                code = sync_rounds(a, r, host)
        except kg_lock.MainLockTimeout as e:  # nothing was fetched, rebased or pushed
            print(f"kbgit.py sync: {e}")
            return 1
    else:
        code = sync_rounds(a, r, host)
    if "rerun" in r:
        return code  # the re-run with the rebased code printed its own report
    if a.dry_run:
        if refuse:
            print(refuse)
            return 2
        return code
    record_gate(r, code)
    print("--- sync report")
    print(f"target: {r.get('target')}; was {r['ahead']} ahead, {r['behind']} behind; commits rebased: {r['rebased']}")
    if r["auto"]:
        print("conflicts resolved mechanically: " + "; ".join(r["auto"]))
    print("fix: " + (f"{len(r['fixed'])} file(s) ({', '.join(r['fixed'])}), committed as {short(r['fix_commit'])} {FIX_COMMIT!r}"
                     if r["fixed"] else "nothing to change"))
    print("ids renumbered: " + ("; ".join(r["renumbered"]) if r["renumbered"] else "none"))
    if r["refreshed"]:
        print(f"trailers refreshed on {r['refreshed']} commit(s)")
    for n in r["notes"]:
        print("note: " + n)
    for label, result, _ in r["gate"]:
        print(f"gate {label}: {result}")
    for label, kept in r.get("gate_outputs", []):
        print(f"gate {label} whole output: {kept}")
    if r.get("scope"):
        print(f"gate scope: {r['scope']} ({r['scope_line']})")
    print(f"pushed: {r['pushed']}")
    print(f"sync: exit {code}, {r.get('tries', 1)} push {'try' if r.get('tries', 1) == 1 else 'tries'}")
    return code
