#!/usr/bin/env python3
"""Git helpers for the kb (stdlib only): post-merge cleanup, canonical ledger formatting, and a queryable history.

  kbgit.py fix [--check] [--base REV] [--upstream REV] [--side REV ...]   post-merge cleanup; safe any time, idempotent
  kbgit.py fmt [--check]                                   only canonical CSV formatting and order (never adds or drops a row)
  kbgit.py trailers [--staged | REV | --amend] [--verified YYYY-MM-DD]   the KB-* trailers of the staged change or a commit
  kbgit.py install-hooks [--uninstall]                     core.hooksPath=.githooks: KB-* trailers, and the gate on a plain push
  kbgit.py check-trailers [A..B | REV]                     exit 1 listing kb commits whose KB-* trailers are missing or wrong
  kbgit.py lane [A..B | REV]                               each commit's lane (content or code) and the code paths that decided it
  kbgit.py check-lanes [A..B | REV] [--forge F]           exit 1 listing code-lane commits no merged merge or pull request introduced
  kbgit.py log <S-id | topic | QK-id | path> [-n N]        commits that touched it (trailers first, then diff/path history)
  kbgit.py blame <path:line>                               the commit that wrote that line, and the sources it cites
  kbgit.py asof <YYYY-MM-DD | tag | rev> <path>            the file as of the last commit on or before that date (or at the tag)
  kbgit.py tag-census YYYY-MM-DD                           annotated tag census-YYYY-MM-DD on HEAD: "kb confirmed current" (no push)
  kbgit.py sync [--push] [--dry-run] [--remote R] [--branch main] [--session S]   fetch, rebase, fix, gate, push
  kbgit.py publish [--remote R] [--dry-run] [--rewrite] [--hook]    push the integration main without kb/_querylog to the public home
  kbgit.py bridge BRANCH [--push] [--dry-run] [--remote R]  a public-home branch to the integration remote: rebase, gate, push by lane
  kbgit.py check-public [REV]                              exit 1 when REV's history touches kb/_querylog (kbpublic.py)

Roots. Every root in this repository's kb/ (kb/public and any kb/<name>/ with a _root.md; KB_ROOTS roots belong to
other repositories) has its own ledgers: fix and fmt work on each root in turn, sync treats every root's ledgers and
coverage files as mechanical, and the pinned block of .gitattributes covers every root's artifacts. A root cites only
its own sources, so renumbering rewrites citations within that root. History arguments take a qualified name
(`public/auth/kerberos.md:42`, `team/mdm/enrol`, `team:QK-...`) or a bare one, which is the public root's.

History (trailers). Every commit that changes kb content ends with git trailers, so `git log` can answer "which commits
changed topic X / source S / answer QK-..." without reading diffs:
  KB-Topics:              qualified topic ids (`public/intune/win32-apps`) whose article or data files changed (the
                          topic -> files mapping of each root's _coverage.csv at both ends of the diff; an article not
                          in it counts under its own path)
  KB-Sources-Added:       _sources.csv ids of new rows
  KB-Sources-Changed:     ids of rows edited (used_in, which is generated, is ignored) or removed
  KB-Sources-Superseded:  ids whose superseded_by became non-empty (not also listed as changed)
  KB-Answers:             _answers.md answer ids (`<root>:<id>` outside public) whose section was added, edited or removed
  KB-Verified: YYYY-MM-DD only on request (`trailers --verified`, or KB_VERIFIED=YYYY-MM-DD in the hook's environment, or
                          `git commit --trailer "KB-Verified: 2026-09-25"`): the commit confirms its sources are current.
  KB-Auto:                written by querylog.py on its automatic commits, once, values from AUTO_VALUES (querylog,
                          eval, alias, expansion, gap, research, revert); never computed here. check-trailers flags a
                          second KB-Auto line or a value outside the list.
  KB-Work:                written by the agent on a commit that works on backlog items (kb/_self/backlog.md), once,
                          comma-separated item ids; never computed here. check-trailers flags a second line or an id
                          whose item file is in neither the commit nor its parent, and, on a commit not yet on
                          origin/main, an id whose item is not claimed (doing or done at the commit) or is not in a
                          started sprint (its sprint active at the commit). Exempt from that: a backlog-planning commit
                          (only kb/_self/backlog/*.json changed), a sprint and a sprint's review story. A claimed
                          research item of a planned sprint (its touches all inside kb roots) passes on a commit that
                          changes only kb content and item files, and is refused on one that changes anything else
                          (_tools/, .claude/, .githooks/, CI, kb/_self/ docs). On a commit
                          not yet on origin/main it also flags a KB-Work line git does not read as a trailer (outside
                          the message's last paragraph, e.g. a blank line before Co-Authored-By). The commit-msg
                          hook warns about these; the pre-push hook and sync's gate refuse them.
One line per key, values sorted and joined by ", ". A key with more than MAX_IDS (40) values is written as a count,
e.g. `KB-Sources-Added: 312 ids (see diff)`: trailers cannot wrap, and `log` finds such commits by their diff anyway.
A commit is diffed against its first parent (the empty tree for a root commit). Merge commits carry no trailers and
are not checked: their content is attributed to the commits they merge. Commits up to TRAILERS_SINCE (the last
commit before trailers existed) are exempt; history is never rewritten.

Hooks (`install-hooks`, once per clone): sets `git config core.hooksPath .githooks` (versioned scripts) in the config
every `git worktree` of the clone shares; git resolves the relative value against each worktree's top level, so each
runs its own .githooks. A clone whose value is an absolute path to the main clone's .githooks (set by hand) runs those
scripts in every worktree, and install-hooks and sync count it as installed there too (hooks_path_is_ours). commit-msg
replaces any KB-Topics/KB-Sources-*/KB-Answers lines with the computed ones via `git interpret-trailers` (so
re-running, `-m`, editor commits and --amend never duplicate them), skips merges, skips a rebase re-application whose
message already has KB-* trailers, and never blocks a commit (any error is a warning). prepare-commit-msg only
notes an --amend so commit-msg diffs against HEAD's parent. `git commit --no-verify` skips commit-msg: CI's
check-trailers catches that. pre-push runs the sync gate plus `fix --check` before a plain `git push` of the checked-out
branch and blocks it (exit 1) when a check fails; first, for any push, it refuses a ref whose history touches
kb/_querylog on its way to the public home (kbpublic.py); the gate skips sync's own push (KB_GATE_DONE=1), tags and deletes, and a
pushed ref that is not HEAD (with a note: the checks read the working tree). Before the gate (sync's push included) it
refuses a push to the integration main that carries a code-lane commit. `git push --no-verify` skips it. Fix unpushed commits with `trailers --amend` (HEAD) or
`git rebase --exec "python3 _tools/kbgit.py trailers --amend" @{upstream}`.

check-trailers without a range: in GitLab CI, CI_COMMIT_BEFORE_SHA..CI_COMMIT_SHA (only CI_COMMIT_SHA when the
before sha is all zeros or unknown); elsewhere @{upstream}..HEAD, or HEAD alone without an upstream.
Census tags: an annotated tag `census-YYYY-MM-DD` marks "the kb was confirmed current as of that date"; its message
counts the sources and the _fetch_state.csv checks. `asof census-2026-09-26 PATH` reads a file as of a census.

Sync (kg_sync.py; the only way to push; people push straight to main, CI is a safety net):
  a. refuses (exit 2) with uncommitted tracked changes (lists staged/unstaged: commit or stash them), or while a
     rebase/merge/cherry-pick/revert is in progress; untracked files do not count.
  b. git fetch REMOTE BRANCH; prints how far HEAD is ahead of / behind REMOTE/BRANCH. With --push (--dry-run too) it
     refuses (exit 1, nothing rebased or pushed) when a local commit not on REMOTE carries a `Claude-Session:` trailer
     naming a session other than the one sync runs in (--session, else KB_SESSION, else CLAUDE_CODE_REMOTE_SESSION_ID
     or CLAUDE_CODE_BRIDGE_SESSION_ID: current_session), listing each. An unknown session refuses nothing.
  c. git -c merge.conflictStyle=diff3 rebase REMOTE/BRANCH (diff3: see MERGE_CFG; merge commits are linearised: they
     would carry no trailers). A step that conflicts only
     in MECHANICAL paths (the union ledgers, _coverage.csv, _tools/lint_baseline.txt, the coverage table page) is
     resolved with `fix --base <merge-base> --upstream REMOTE/BRANCH --side <old HEAD>`, `git add -u`, `git rebase
     --continue`. Any other conflicted path (an article, a tool, docs, the coverage page outside the table) stops with exit 3
     and the rebase left in progress: `needs-human: PATH` lines, a `sync-state: base=.. upstream=.. orig_head=..` line
     and the commands to finish (or `git rebase --abort`). Article text is never resolved automatically.
     A rebase that changed kbgit.py or a _tools module it loaded (kblane, kbpublic, kg_merge...: code_changed, the
     loaded modules' files at the old HEAD against the rebased one) leaves this process on the old code: sync re-runs
     itself once, a new process with the same arguments (--session and all) on the rebased tree and KB_SYNC_REEXEC=1,
     and returns its exit code, so the new code decides the push; the re-run finds nothing behind. A re-run whose
     rebase changed the code again, or a sync with no command line to repeat (bridge's), stops with exit 3 instead.
  d. fix (with --base/--side when both sides had commits); what it changed is committed on its own as
     "chore(kb): kbgit fix after sync" with KB-* trailers. Unpushed commits whose trailers no longer match their diff
     (conflict resolution, renumbered ids) get them rewritten (`git rebase --exec "kbgit.py trailers --amend"`).
     Gate: build_index.py --check, check.py, fetch.py --offline, doc2query.py stale, selfdoc.py stale --since
     REMOTE/BRANCH (a `Self-Reviewed:` trailer clears a doc), tests.py --changed with KB_TESTS_FAST=1 (git scenarios only
     in the test files a changed tool or other code path selects; KB_SYNC_NO_TESTS=1 skips it, for the tool's own tests), check-trailers REMOTE/BRANCH..HEAD. A red gate: exit 1,
     nothing pushed.
  e. --push: git push REMOTE HEAD:BRANCH, never --force. Rejected because the remote moved: fetch and rebase once more,
     then give up (exit 1). A push to main whose range has a code-lane commit (kblane.py) goes instead as the branch
     code/<id> with merge-request push options, main not moving (lane_plan); code_branch picks <id>: the first KB-Work
     id of the range's first code-lane commit that has one, else the range's first KB-Work id, else HEAD's short hash.
  f. a report: commits rebased, conflicts resolved, fix, ids renumbered, trailers refreshed, gate, pushed or not.
  --dry-run fetches and reports ahead/behind, the incoming commits and the files both sides changed; nothing else.
Exit (sync): 0 done, 1 gate failed, push rejected/failed or another session's commits, 2 refused (dirty tree, operation in progress, bad
arguments, fetch failed), 3 a conflict or a fix problem needs a human or /kb-git-sync, or the rebase changed sync's
code where it cannot re-run itself (run it again). After a re-run, the re-run's exit code.

Why: `.gitattributes` merges the append-only ledgers with git's built-in union driver, so two branches that
each add rows or answers merge without conflict markers. Union keeps every line of both sides, so a row both
sides touched can appear twice. `fix` turns that into one clean, canonical state:

_sources.csv   conflict markers (a merge made without our .gitattributes) are dropped with union semantics; repeated
               header lines and exact duplicate rows are removed. Rows sharing an id:
               - same normalized url: merged field-wise. With --base, a row identical to the base's row is the stale
                 copy and yields to the edited one. retrieved_utc/version_or_date come from the row with the latest
                 retrieved_utc; a non-empty value beats an empty one; superseded_by is kept if either row has it.
                 Two different non-empty title/publisher/licence/reuse/artifact_sha256 values: the latest row wins and
                 the conflict is reported (a tie on retrieved_utc, or two different superseded_by, needs a human).
               - different urls: a real collision (two branches both took the next legacy number, e.g. S2205).
                 Needs --base: an id present at base keeps its base url, else the --upstream side's url keeps it
                 (it is already pushed: published ids are never renumbered); every other url gets its own id (the
                 existing id of that url if it has a row, else its hash id `kbid.py url`). Citations are rewritten
                 line by line: a line citing the id that only one side's version of the file has (and the base's
                 has not) belongs to that side; a line no side has (a resolved conflict) belongs to the one side
                 whose version of the file cites the id at all. A line on both sides, a new line in a file both
                 sides cite the id in, or an old citation of an id the base did not have, is ambiguous: reported,
                 exit 2, nothing written.
               Canonical form: legacy ids numerically, then hash ids sorted; csv module quoting; `\\n`; no BOM.
_anchors.csv   one row per (fact, path, source_id): the latest verified_utc wins (factdiff.py).
_fetch_state.csv  one row per id: checked_utc/error from the row with the latest check, the fetch columns
               (fetched_utc, sha256, text_sha256, bytes) from the row with the latest fetch, factdiff.py's columns
               (etag ... simhash, detected_utc) from the row with the latest detected_utc, changed_utc the max.
_answers.md, _gaps.md, _conflicts.md  conflict markers dropped (union semantics); verbatim duplicate `##`/`###`
               sections, duplicate list items (20+ characters) in one section and duplicate rows in one table removed.
               With the merge's sides known, a `##` section that a merge cut short is made whole: git keeps lines that
               two blocks added at one place both end with (an `_Agent: kb-research_` footer) only once, at the end
               of the second block (repair_splices; sync avoids it with diff3, see MERGE_CFG).
               Answer ids: one id heading two different
               questions: the heading at base or on --upstream keeps it (else the first), the others get their
               QK-<slug>, and lines naming the id follow their side (as citations do). The same heading twice
               with different bodies: reported, exit 2.
_tools/lint_baseline.txt  if a merge touched it (markers, unsorted or duplicate lines), it becomes the current lint
               errors that either side had accepted, sorted: a merge never accepts new lint debt by itself.
.gitattributes  the block between `# pinned:start` and `# pinned:end` lists every _artifacts.csv path as `-text`.
Then build_index.py regenerates _coverage.csv, the coverage table in kb/_self/coverage.md (conflict markers inside the
table go with it) and used_in. Conflict markers left anywhere else in a ledger, that page or an article: exit 2.
kb/_querylog/  one run file per distill run, never edited after it: an entry id in two run files (the same lookup
               distilled twice) is reported, exit 2 (querylog.duplicate_ids; kb/_self/querylog.md, Store).

Sides of the merge (for collisions): --side REV (repeatable), else MERGE_HEAD during a merge (HEAD + MERGE_HEAD),
else the parents of HEAD when HEAD is a merge commit. Base: --base REV (e.g. `git merge-base A B`). --upstream REV is
a side that is already pushed (sync passes REMOTE/BRANCH; after a cherry-pick or a rebase by hand, pass the branch you
put your commits on): its source and answer ids win a collision.

Exit (fix, fmt): 0 clean (or fixed), 1 --check and something would change, 2 a problem needs a human (nothing is written).
Exit (history): 0 ok; 1 check-trailers found bad commits, log found nothing, asof/blame found no such file or line;
2 bad arguments, not a git clone, or a git error. Hooks always exit 0.
"""
import argparse, csv, datetime, io, os, re, stat, sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kbcommon, kbid  # noqa: E402
import build_index  # noqa: E402
import kbpublic  # noqa: E402
import kblane  # noqa: E402
import kg_lane  # noqa: E402
import kg_merge  # noqa: E402
import kg_sync  # noqa: E402
from kg_base import KB, Problem, repo_roots  # noqa: E402
from kg_sync import do_rebase, gitx, in_progress, new_report  # noqa: E402
from kg_trailers import (AUTO, AUTO_VALUES, INDEX, KEY_LINE, STRAY_WORK, WORK, apply_trailers, blob,  # noqa: E402,F401
                         changed_paths, cmd_check_trailers, cmd_trailers, compute, default_range, is_content, log_records,
                         message_trailers, parse_trailers, source_rows_of, stray_work, trailer_audit,
                         valid_date, work_state)
from kg_merge import FB, canon_csv, has_markers, id_key, lf, run, strip_markers  # noqa: E402,F401


def user_path(arg):
    """A path given on the command line as a repository path: qualified (`public/auth/kerberos.md`), bare
    root-relative (`auth/kerberos.md`: the public root) or repository-relative; as given when it names nothing."""
    arg = arg[2:] if arg.startswith("./") else arg
    head, _, rest = arg.partition("/")
    for r in repo_roots():
        if head == r.name and rest and os.path.exists(os.path.join(r.path, rest)):
            return kbcommon.repo_rel(rest, r.path)
    return kbcommon.repo_rel(arg, kbcommon.PUBLIC) if os.path.exists(os.path.join(kbcommon.PUBLIC, arg)) else arg


def with_legacy(path):
    """[path] plus, for a file under the public root, its path before the kb moved (root-relative), for history."""
    rel = kbcommon.kb_rel(path, kbcommon.PUBLIC)
    return [path] + ([rel] if rel and rel != path else [])


# kg_merge's io and git helpers run in kg_base.KB; these run in this module's KB, which a caller may point elsewhere
# (a scratch clone): the history, hook and sync commands use them.
def git_run(*args, stdin=None):
    return kg_merge.git_run(*args, stdin=stdin, kb=KB)


def git(*args, stdin=None):
    return kg_merge.git(*args, stdin=stdin, kb=KB)


def read(rel):
    return kg_merge.read(rel, kb=KB)


def show(rev, rel):
    return kg_merge.show(rev, rel, kb=KB)


# ---------------------------------------------------------------- history: trailers

HOOKS_DIR = ".githooks"
HOOKS = ("prepare-commit-msg", "commit-msg", "pre-push")
ZERO = "0" * 40


def worktree_tops():
    """The top level of every worktree of this clone (`git worktree list --porcelain`), this checkout's included."""
    out = git("worktree", "list", "--porcelain") or ""
    return [ln[len("worktree "):] for ln in out.splitlines() if ln.startswith("worktree ")]


def hooks_path_is_ours(cur):
    """core.hooksPath CUR runs the kb's hooks in this checkout. git runs a commit hook in the worktree's top level and
    reads core.hooksPath from the config every `git worktree` of a clone shares, so a relative `.githooks` (what
    install-hooks sets) names each worktree's own scripts, and an absolute path (a clone set up by hand) names one
    directory for all of them. Ours: this checkout's .githooks, by either form, or the .githooks of another worktree
    of the clone that holds the hook scripts (a sprint worker's worktree under the main clone's absolute value)."""
    cur = (cur or "").strip()
    if not cur:
        return False
    if cur.rstrip("/") == HOOKS_DIR:
        return True
    d = (Path(KB) / Path(cur).expanduser()).resolve()
    if d == (Path(KB) / HOOKS_DIR).resolve():
        return True
    others = {(Path(t) / HOOKS_DIR).resolve() for t in worktree_tops()}
    return d in others and all((d / h).is_file() for h in HOOKS)
AMEND_MARK = "kb-trailers-base"


def rev_parse(rev):
    return (git("rev-parse", "-q", "--verify", rev + "^{commit}") or "").strip() or None


def git_path(name):
    p = (git("rev-parse", "--git-path", name) or "").strip()
    return os.path.join(KB, p) if p else None



# ---------------------------------------------------------------- history: hooks

def hook_prepare(args):
    """Note an --amend (git passes `commit HEAD`; -c/-C pass `commit <rev>`), so commit-msg diffs against HEAD's parent, not HEAD."""
    mark = git_path(AMEND_MARK)
    if mark and os.path.exists(mark):
        os.remove(mark)
    if mark and len(args) >= 3 and args[1] == "commit" and rev_parse(args[2]) == rev_parse("HEAD"):
        parents = (git("rev-list", "--parents", "-n", "1", "HEAD") or "").split()[1:]
        with open(mark, "w", encoding="utf-8", newline="\n") as f:
            f.write("merge" if len(parents) > 1 else (parents[0] if parents else "root"))


def hook_commit_msg(args):
    mark, base = git_path(AMEND_MARK), None
    if mark and os.path.exists(mark):
        with open(mark, encoding="utf-8") as f:
            base = f.read().strip()
        os.remove(mark)
    if base == "merge" or rev_parse("MERGE_HEAD"):
        return  # merge commits carry no trailers
    with open(args[0], encoding="utf-8", errors="replace", newline="") as f:
        msg = f.read()
    rebasing = any(os.path.isdir(p or "") for p in (git_path("rebase-merge"), git_path("rebase-apply")))
    if rebasing and any(KEY_LINE.match(ln) for ln in msg.splitlines()):
        return
    if base is None:
        base = rev_parse("HEAD") or ""
    elif base == "root":
        base = ""
    verified = os.environ.get("KB_VERIFIED", "").strip() or None
    if verified and not valid_date(verified):
        print(f"kbgit.py: KB_VERIFIED={verified!r} is not YYYY-MM-DD; not added", file=sys.stderr)
        verified = None
    new = apply_trailers(msg, compute(base, INDEX), verified)
    if new != msg:
        with open(args[0], "w", encoding="utf-8", newline="") as f:
            f.write(new)
    if stray_work(new):  # warnings only: the commit goes through, and check-trailers refuses it before a push
        print(f"kbgit.py commit-msg: {STRAY_WORK}; check-trailers (the pre-push hook, sync's gate) refuses this "
              "commit", file=sys.stderr)
    work = message_trailers(new)[1].get(WORK, [])
    if len(work) == 1:
        staged = lambda rel: blob(INDEX, rel) if blob(INDEX, rel) is not None else blob(base, rel)  # noqa: E731
        for why in work_state(work, changed_paths(base, INDEX), staged):
            print(f"kbgit.py commit-msg: {WORK}: {why}; check-trailers (the pre-push hook, sync's gate) refuses this "
                  "commit: work lands only for a claimed item of a started sprint", file=sys.stderr)


def cmd_hook(a):
    if a.name == "pre-push":
        return hook_pre_push(a.args, sys.stdin.read())
    try:
        (hook_prepare if a.name == "prepare-commit-msg" else hook_commit_msg)(a.args)
    except Exception as e:  # noqa: BLE001 - a hook must never block a commit
        print(f"kbgit.py {a.name}: KB trailers not added ({type(e).__name__}: {e})", file=sys.stderr)
    return 0


def lane_refusals(remote, stdin):
    """[(remote ref, short hash, code paths)] of the new code-lane commits pushed to the integration remote's main
    (pre-push stdin lines `local ref, local sha, remote ref, remote sha`): remote sha..local sha, or for a new ref
    (or a remote sha this clone lacks) the commits no remote-tracking ref of REMOTE reaches. Merge commits already on
    the remote are not new. No API call. Other remotes and branches are not judged."""
    if remote != kbpublic.integration_remote(KB):
        return []
    res = []
    for ln in stdin.splitlines():
        parts = ln.split()
        if len(parts) != 4 or parts[2] != f"refs/heads/{kg_lane.LANE_BRANCH}" or parts[1] == ZERO:
            continue
        _, local_sha, ref, remote_sha = parts
        if remote_sha != ZERO and git("cat-file", "-e", remote_sha + "^{commit}") is not None:
            spec = [f"{remote_sha}..{local_sha}"]
        else:
            spec = [local_sha, "--not", f"--remotes={remote}"]
        for short, lane, code in kblane.commit_lanes(KB, spec) or []:
            if lane == kblane.CODE:
                res.append((ref, short, code))
    return res


def hook_pre_push(args, stdin):
    """The pre-push hook: run the sync gate (plus `fix --check`, which sync runs itself) before a plain `git push` of
    a branch. Exit 1 blocks the push. Skipped when `sync` pushes (it gated already: KB_GATE_DONE=1), for tag-only and
    delete-only pushes, and with a note when the pushed commit is not HEAD (the checks read the working tree)."""
    remote = args[0] if args else kbpublic.integration_remote(KB)
    pushed = [(p[0], p[1]) for p in (ln.split() for ln in stdin.splitlines()) if len(p) == 4]
    blocked = kbpublic.guard_push(remote, args[1] if len(args) > 1 else None, pushed, KB)
    for ref, why in blocked:
        print(f"kb pre-push: refused: {remote} is the public home and {ref} {why}; publish with "
              "python3 _tools/kbgit.py publish (kb/_self/git.md, Public home)", file=sys.stderr)
    if blocked:
        return 1
    refused = lane_refusals(remote, stdin)
    for ref, short, code in refused:
        print(f"kb pre-push: refused: {short} is a code-lane commit ({' '.join(code)}) and {ref} of {remote} is main; "
              "code reaches main through a merge request: python3 _tools/kbgit.py sync --push sends it as a "
              f"{kg_lane.CODE_BRANCH_PREFIX}<id> branch", file=sys.stderr)
    if refused:
        return 1
    if os.environ.get("KB_GATE_DONE") == "1":
        return 0
    head = rev_parse("HEAD")
    ups, other = [], []
    for ln in stdin.splitlines():
        parts = ln.split()
        if len(parts) != 4 or not parts[2].startswith("refs/heads/") or parts[1] == ZERO:
            continue  # a tag, a delete or a malformed line (the local ref may be `HEAD` for `git push origin HEAD:main`)
        local_ref, local_sha, remote_ref, remote_sha = parts
        if local_sha != head:
            other.append(local_ref)
            continue
        if remote_sha != ZERO and git("cat-file", "-e", remote_sha + "^{commit}") is not None:
            ups.append(remote_sha)
        else:  # a new remote branch: gate against where it left the remote's main
            base = rev_parse(f"refs/remotes/{remote}/main")
            ups.append((git("merge-base", base, head) or "").strip() if base else None)
    for ref in other:
        print(f"kb pre-push: {ref} is not HEAD; not checked (the checks read the working tree). "
              "Check it out and push again, or use python3 _tools/kbgit.py sync --push", file=sys.stderr)
    if not ups:
        return 0
    staged, unstaged = dirty_paths()
    if staged or unstaged:
        print("kb pre-push: the working tree has uncommitted changes; the checks include them", file=sys.stderr)
    r = {"target": remote, "gate": []}
    ok = gate(r, ups[0], fix_check=True)
    for label, result, _ in r["gate"]:
        print(f"kb pre-push {label}: {result}", file=sys.stderr)
    if not ok:
        print("kb pre-push: a check failed; nothing pushed. Fix the cause (python3 _tools/kbgit.py sync --push "
              "fixes the ledgers itself); `git push --no-verify` skips this and CI reports it instead", file=sys.stderr)
        return 1
    return 0


def cmd_install_hooks(a):
    if git("rev-parse", "--git-dir") is None:
        print("not a git clone (or git is missing)")
        return 2
    cur = (git("config", "--get", "core.hooksPath") or "").strip()
    if a.uninstall:
        if hooks_path_is_ours(cur):
            git("config", "--unset", "core.hooksPath")
            print(f"uninstalled: core.hooksPath unset ({HOOKS_DIR}/ stays in the repo)")
        else:
            print("not installed" + (f" (core.hooksPath is {cur!r}; left alone)" if cur else ""))
        return 0
    for name in HOOKS:
        p = os.path.join(KB, HOOKS_DIR, name)
        if not os.path.isfile(p):
            print(f"{HOOKS_DIR}/{name} is missing from this checkout")
            return 2
        mode = os.stat(p).st_mode
        if not mode & stat.S_IXUSR:
            os.chmod(p, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    if cur and not hooks_path_is_ours(cur):
        print(f"core.hooksPath is already {cur!r}; not changed. Chain {HOOKS_DIR}/commit-msg and "
              f"{HOOKS_DIR}/prepare-commit-msg from there, or `git config --unset core.hooksPath` and rerun")
        return 2
    if cur:
        print(f"already installed (core.hooksPath={cur})")
        return 0
    old = git_path("hooks")  # .git/hooks while core.hooksPath is unset
    if old and os.path.isdir(old):
        own = sorted(f for f in os.listdir(old) if not f.endswith(".sample"))
        if own:
            print(f"WARN hooks in {os.path.relpath(old, KB)}/ stop running while core.hooksPath is set: {', '.join(own)}")
    if git("config", "core.hooksPath", HOOKS_DIR) is None:
        print("git config core.hooksPath failed")
        return 2
    print(f"installed: core.hooksPath={HOOKS_DIR} ({', '.join(HOOKS)}); kb commits now get KB-* trailers")
    return 0


# ---------------------------------------------------------------- history: check, log, blame, asof, census

def cmd_lane(a):
    rng = a.range or default_range()
    lanes = kblane.commit_lanes(KB, kblane.spec_of(rng))
    if lanes is None:
        print(f"{rng}: not a valid revision range here")
        return 2
    for short, lane, code in lanes:
        print(f"{short} {lane}" + (f" {' '.join(code)}" if code else ""))
    return 0


def cmd_check_lanes(a):
    rng = a.range or default_range()
    try:
        bad = kblane.check_lanes(KB, kblane.spec_of(rng), kblane.forge_associate(a.forge, os.environ))
    except kblane.ForgeError as e:
        print(f"check-lanes {rng}: cannot read the forge's association API, so nothing passes: {e}")
        return 2
    if bad is None:
        print(f"{rng}: not a valid revision range here")
        return 2
    for short, code in bad:
        print(f"{short} code {' '.join(code)}: no merged merge request or pull request introduced it")
    print(f"check-lanes {rng}: unmerged_code_commits={len(bad)}")
    if bad:
        print("code goes to main through a merge request: python3 _tools/kbgit.py sync --push")
    return 1 if bad else 0



def id_regex(sid):
    """POSIX ERE for a source id as a whole word (git log -G)."""
    return rf"(^|[^A-Za-z0-9_-]){re.escape(sid)}([^A-Za-z0-9_-]|$)"


def split_arg(arg):
    """(Root, rest) of a history argument: `<root>/<rest>` or `<root>:<answer id>` names that root; anything else is
    the public root's."""
    for sep in ("/", ":"):
        head, s, rest = arg.partition(sep)
        if s and rest:
            for r in repo_roots():
                if r.name == head:
                    return r, rest
    return kbcommon.public(), arg


def classify(arg):
    """(kind, what, root): a source id, an answer id, a topic (qualified or bare = public) or a path."""
    if kbid.is_source_id(kbid.canonical_id(arg)) and not os.path.exists(os.path.join(KB, user_path(arg))):
        sid = kbid.canonical_id(arg)
        return "source", sid, kbcommon.root_of_prefix(sid.split("-", 1)[0] if "-" in sid else "S") or kbcommon.public()
    r, rest = split_arg(arg)
    ans = kbcommon.read(os.path.join(r.path, kbcommon.ANSWERS)) or ""
    if (kbid.QK_ID.fullmatch(rest) and ":" in arg) or kbid.QK_ID.fullmatch(arg) or rest in kbid.answer_ids(ans):
        return "answer", rest, r
    topics = {x["topic"] for x in csv.DictReader(io.StringIO(lf(kbcommon.read(os.path.join(r.path, kbcommon.COVERAGE_CSV)) or "")))}
    if rest in topics or (os.path.isfile(os.path.join(r.path, rest + ".md"))
                          and is_content(kbcommon.repo_rel(rest + ".md", r.path))):
        return "topic", rest, r
    return "path", user_path(arg), None


def cmd_log(a):
    if rev_parse("HEAD") is None:
        print("not a git clone, or no commits")
        return 2
    kind, what, r = classify(a.target)
    keys = {"source": ("KB-Sources-Added", "KB-Sources-Changed", "KB-Sources-Superseded"),
            "topic": ("KB-Topics",), "answer": ("KB-Answers",), "path": ()}[kind]
    # trailer values: topics qualified (bare in commits from before roots), answers `<root>:<id>` outside public
    if kind == "topic":
        want = {f"{r.name}/{what}"} | ({what} if r.name == "public" else set())
    elif kind == "answer":
        want = {what} if r.name == "public" else {f"{r.name}:{what}"}
    else:
        want = {what}
    recs = log_records("HEAD") or []
    how = {}
    for sha, _, _, _, trailers in recs:
        t = parse_trailers(trailers)
        if any(want & {x.strip() for v in t.get(k, []) for x in v.split(",")} for k in keys):
            how[sha] = "trailer"
    fallback = []
    if kind == "source":
        fallback = [("diff", ["-G", id_regex(what)])]
    elif kind == "answer":
        fallback = [("diff", ["-G", rf"^## {re.escape(what)}\. ", "--",
                              *with_legacy(kbcommon.repo_rel(kbcommon.ANSWERS, r.path))])]
    elif kind == "topic":
        cov = lf(kbcommon.read(os.path.join(r.path, kbcommon.COVERAGE_CSV)) or "")
        row = {x["topic"]: x for x in csv.DictReader(io.StringIO(cov))}.get(what)
        files = [f for f in (row["files"].split(";") if row else [what + ".md"]) if f]
        fallback = [("path", ["--"] + [p for f in files for p in with_legacy(kbcommon.repo_rel(f, r.path))])]
    if kind == "topic":
        what = f"{r.name}/{what}"
    elif kind == "answer" and r.name != "public":
        what = f"{r.name}:{what}"
    if kind == "path":
        fallback = [("path", ["--follow", "--", what])]
    for label, args in fallback:
        for sha in (git("log", "--format=%H", "HEAD", *args) or "").split():
            how.setdefault(sha, label)
    hits = [r for r in recs if r[0] in how]
    print(f"# {kind} {what}: {len(hits)} commit(s)" + (f", newest {a.n}" if len(hits) > a.n else ""))
    for sha, short, date, subject, _ in hits[:a.n]:
        print(f"{short}  {date}  {subject[:80]}  [{how[sha]}]")
    return 0 if hits else 1


def blame_line(path, n, ignore_ws):
    args = ["blame", "--porcelain", "-M", "-C", "-L", f"{n},{n}"] + (["-w"] if ignore_ws else []) + ["--", path]
    out = git(*args)
    if not out:
        return None
    lines = out.splitlines()
    info = {"sha": lines[0].split()[0]}
    for ln in lines[1:]:
        if ln.startswith("\t"):
            info["text"] = ln[1:]
            break
        k, _, v = ln.partition(" ")
        info[k] = v
    return info


def cmd_blame(a):
    path, _, line = a.target.rpartition(":")
    if not path or not line.isdigit() or int(line) < 1:
        print(f"{a.target!r}: expected PATH:LINE")
        return 2
    shown = path[2:] if path.startswith("./") else path
    path = user_path(shown)
    if rev_parse("HEAD") is None:
        print("not a git clone, or no commits")
        return 2
    b = blame_line(path, int(line), True)
    if b is None:
        print(f"{shown}:{line}: no such tracked file or line")
        return 1
    zero = set(b["sha"]) == {"0"}
    when = datetime.datetime.fromtimestamp(int(b.get("author-time", "0")), datetime.timezone.utc).date() if not zero else ""
    print(f"{shown}:{line}: {b.get('text', '')}")
    if zero:
        print("  introduced by: not committed yet")
    else:
        rec = (log_records("-1", b["sha"]) or [("", b["sha"][:7], str(when), b.get("summary", ""), "")])[0]
        print(f"  introduced by: {rec[1]}  {rec[2]}  {rec[3][:80]}  ({b.get('author', '?')})"
              + (f"  [as {b['filename']}]" if b.get("filename") and b["filename"] != path else ""))
        plain = blame_line(path, int(line), False)
        later = int((git("rev-list", "--count", f"{b['sha']}..HEAD", "--", path) or "0").strip() or 0)
        if plain and plain["sha"] != b["sha"]:
            print(f"  touched since: whitespace only, in {plain['sha'][:7]}")
        else:
            print("  touched since: no" + (f" (the file changed in {later} later commit(s))" if later else ""))
    ids = sorted(set(build_index.CITE.findall(b.get("text", ""))), key=id_key)
    rows, ledgers = {}, []
    for root in (repo_roots() if ids else []):
        led = kbcommon.repo_rel(kbcommon.SOURCES, root.path)
        ledgers += with_legacy(led)
        rows.update((x.get("id"), x) for x in source_rows_of(read(led)).values())
    for sid in ids:
        r = rows.get(sid)
        added = (git("log", "--reverse", "--format=%h %cs", "-G", rf"^{re.escape(sid)},", "HEAD", "--", *ledgers) or "").split("\n")[0]
        sup = (r or {}).get("superseded_by", "").strip()
        print(f"  {sid}  {(r or {}).get('url') or 'UNKNOWN id'}" + (f"  superseded by {sup}" if sup else "")
              + (f"  (row added in {added})" if added else ""))
    return 0


def cmd_asof(a):
    if valid_date(a.when):
        rev = (git("rev-list", "-1", "--first-parent", f"--before={a.when} 23:59:59", "HEAD") or "").strip()
        if not rev:
            print(f"no commit on or before {a.when}", file=sys.stderr)
            return 1
    else:
        rev = rev_parse(a.when)
        if not rev:
            print(f"{a.when!r}: neither YYYY-MM-DD nor a tag or commit here", file=sys.stderr)
            return 2
    path = a.path[2:] if a.path.startswith("./") else a.path
    for cand in with_legacy(user_path(path)):  # before the kb moved, a root file sat at its root-relative path
        p = git_run("cat-file", "blob", f"{rev}:./{cand}")  # not `git show` (see show)
        if p is not None and not p.returncode:
            break
    rec = (log_records("-1", rev) or [("", rev[:7], "", "", "")])[0]
    if p is None or p.returncode:
        print(f"{path} did not exist at {rec[1]} ({rec[2]})", file=sys.stderr)
        return 1
    print(f"# {path} at {rec[1]}  {rec[2]}  {rec[3][:80]}", file=sys.stderr)
    sys.stdout.flush()
    sys.stdout.buffer.write(p.stdout)
    return 0


def census_message(date):
    lines = [f"kb confirmed current as of {date}", ""]
    rows = source_rows_of(blob("HEAD", kg_merge.SOURCES))
    sup = sum(1 for r in rows.values() if (r.get("superseded_by") or "").strip())
    lines.append(f"sources: {len(rows)} in {kg_merge.SOURCES} ({sup} superseded)")
    st = blob("HEAD", kg_merge.STATE)
    if st:
        state = list(csv.DictReader(io.StringIO(lf(st))))
        ok = [r for r in state if r.get("checked_utc") and not (r.get("error") or "").strip()]
        err = sum(1 for r in state if (r.get("error") or "").strip())
        latest = max((r.get("checked_utc", "") for r in state), default="")
        never = len(set(rows) - {r.get("id") for r in state})
        lines.append(f"fetch state: {len(ok)} sources verified (checked without error), {err} with an error, "
                     f"{never} never checked; latest check {latest[:10] or 'none'}")
    else:
        lines.append(f"fetch state: none ({kg_merge.STATE} is not committed)")
    return "\n".join(lines) + "\n"


def cmd_tag_census(a):
    if not valid_date(a.date):
        print(f"{a.date!r}: expected YYYY-MM-DD")
        return 2
    head = rev_parse("HEAD")
    if not head:
        print("not a git clone, or no commits")
        return 2
    name = f"census-{a.date}"
    if rev_parse(f"refs/tags/{name}"):
        print(f"tag {name} already exists")
        return 2
    if a.date > datetime.date.today().isoformat():
        print(f"WARN {a.date} is in the future")
    if (git("status", "--porcelain", "--untracked-files=no") or "").strip():
        print("WARN uncommitted changes are not part of the census (the tag is on HEAD)")
    msg = census_message(a.date)
    p = git_run("tag", "-a", name, "-F", "-", head, stdin=msg.encode("utf-8"))
    if p is None or p.returncode:
        print("git tag failed: " + (p.stderr.decode("utf-8", "replace") if p else "no git"))
        return 2
    print(f"created annotated tag {name} on {head[:12]}\n" + msg.rstrip())
    print(f"not pushed; to share it: git push {kbpublic.integration_remote(KB)} {name}")
    return 0


FIX_COMMIT = kg_sync.FIX_COMMIT  # ql_deliver.py reads it: the subject of the commit sync makes from what fix changed


def short(rev):
    return (rev or "")[:9]


def names(*args):
    return sorted(p for p in (git(*args, "-z") or "").split("\0") if p)


def dirty_paths():
    """(staged, unstaged) tracked paths that differ from HEAD / the index (untracked files do not count)."""
    return names("diff", "--cached", "--name-only"), names("diff", "--name-only")


# ---------------------------------------------------------------- sync (kg_sync.py): the facade gives it the trailer code


def sync_host():
    """What kg_sync takes from this module: the trailer audit, the fix commit's message and the hooks check, read when
    sync runs."""
    return kg_sync.Host(trailer_audit, lambda body: apply_trailers(body, compute(rev_parse("HEAD") or "", INDEX)),
                        hooks_path_is_ours)


def gate(r, up, fix_check=False):
    """kg_sync.gate with this module's trailer audit (the pre-push hook adds `fix_check`)."""
    return kg_sync.gate(r, up, sync_host(), fix_check)


def cmd_sync(a, r=None):
    return kg_sync.cmd_sync(a, sync_host(), r)


BRIDGE_PREFIX = "bridge/"


def bridge_dry_run(a, pub, main, tip, commits):
    """What bridge would do, from the public commits alone: their lane and the target branch."""
    print(f"dry run: {len(commits)} commit(s) of {pub}/{a.branch} not on {pub}/main")
    lane, branch = kg_lane.lane_plan(KB, main, tip)
    print(f"lane: {lane}; " + (f"would push branch {branch} with merge-request push options, main would not move"
                              if branch else f"would push to {a.remote}/main"))
    print("nothing checked out, rebased, fixed, committed or pushed")
    return 0


def cmd_bridge(a):
    """A branch of the public home to the integration remote (kb/_self/git.md, Public home): its commits not on the
    public main, rebased onto the integration main on a local branch bridge/BRANCH and sent through sync (gate, lane
    routing). Exit as sync: 0 pushed (or nothing to do, or no --push), 1 refused or gate red, 2 bad arguments, 3 conflict."""
    a.remote = a.remote or kbpublic.integration_remote(KB)
    pub = kbpublic.publish_remote(KB)
    if git("rev-parse", "--is-inside-work-tree") is None or not rev_parse("HEAD"):
        print("refused: not a git clone with commits (or git is missing)")
        return 2
    if pub and pub == a.remote:
        print(f"refused: {pub!r} is both the public home and the integration remote")
        return 2
    if git("remote", "get-url", a.remote) is None:
        print(f"refused: no integration remote {a.remote!r}")
        return 2
    busy = in_progress()
    if busy:
        print(f"refused: {busy[0]} is in progress; finish it first ({busy[1]})")
        return 2
    staged, unstaged = dirty_paths()
    if (staged or unstaged) and not a.dry_run:
        print("refused: uncommitted changes; commit them (git commit) or stash them (git stash) first")
        for p in staged:
            print(f"  staged:   {p}")
        for p in unstaged:
            print(f"  unstaged: {p}")
        return 2
    try:
        main_sha, tip, commits = kbpublic.bridge_range(pub, a.branch, KB)
    except kbpublic.BridgeError as e:
        print(f"refused: {e}")
        return e.code
    print(f"{pub}/{a.branch}: {len(commits)} commit(s) not on {pub}/main")
    if not commits:
        print("bridge: nothing to bridge")
        return 0
    if a.dry_run:
        return bridge_dry_run(a, pub, main_sha, tip, commits)
    code, o = gitx("fetch", "--quiet", a.remote, f"+refs/heads/main:refs/remotes/{a.remote}/main")
    if code:
        print(f"git fetch {a.remote} failed:\n" + o.rstrip())
        return 2
    up = rev_parse(f"refs/remotes/{a.remote}/main")
    if not up:
        print(f"refused: {a.remote}/main has no commit")
        return 2
    head = (git("symbolic-ref", "--quiet", "--short", "HEAD") or "").strip()
    was = head or rev_parse("HEAD")
    tmp = BRIDGE_PREFIX + a.branch
    code, o = gitx("checkout", "-q", "-B", tmp, tip)
    if code:
        print(f"git checkout {tmp} failed:\n" + o.rstrip())
        return 2
    r = new_report(a.push)
    r["target"] = f"{a.remote}/main"
    base = (git("merge-base", up, tip) or "").strip() or None
    code = do_rebase(r, up, base, tip, since=main_sha)
    if code == 3:
        print(f"The bridged commits are on {tmp}, the rebase is in progress. After resolving, run "
              "python3 _tools/kbgit.py sync --push there; your branch " + (head or short(was)) + " is untouched.")
        return 3
    if not code:
        r["rebased"] = len(commits)
        # session "": the bridged commits are the public home's, already pushed there, not a local session's
        a2 = argparse.Namespace(remote=a.remote, branch="main", push=a.push, dry_run=False, session="")
        code = cmd_sync(a2, r)
    if code == 3:
        return 3
    pushed = str(r["pushed"]).startswith("yes")
    listing = (git("log", "--reverse", "--format=%h", "-n", str(r["ahead"] + (1 if r["fixed"] else 0)), "HEAD") or "").split()
    gitx("checkout", "-q", *(["--detach"] if not head else []), was)
    if pushed:
        gitx("branch", "-D", tmp)
        print(f"public branch: {pub}/{a.branch}")
        print("integration commits: " + " ".join(listing))
        print(f"the pull request on the public home is closed by a person once publish brings these commits ({pub} was only read)")
    else:
        print(f"the bridged commits stay on {tmp}; {head or short(was)} is checked out again")
    return code


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fix", help="post-merge cleanup of the ledgers, then build_index.py")
    f.add_argument("--check", action="store_true", help="write nothing; exit 1 if fix would change something")
    f.add_argument("--base", help="the merge base (git merge-base A B); needed to renumber colliding legacy ids")
    f.add_argument("--side", action="append", default=[], help="a merged branch/commit (repeatable; default: MERGE_HEAD or HEAD's parents)")
    f.add_argument("--upstream", help="the side that is already pushed (sync: REMOTE/BRANCH): on a collision its source and answer ids stay")
    m = sub.add_parser("fmt", help="canonical CSV quoting, order and newlines of the ledgers")
    m.add_argument("--check", action="store_true", help="write nothing; exit 1 if fmt would change something")
    t = sub.add_parser("trailers", help="print the KB-* trailers of the staged change (default) or of a commit")
    t.add_argument("rev", nargs="?", help="a commit (diffed against its first parent)")
    t.add_argument("--staged", action="store_true", help="the staged change against HEAD (the default)")
    t.add_argument("--amend", action="store_true", help="rewrite HEAD's message with the correct trailers (no content change)")
    t.add_argument("--verified", metavar="YYYY-MM-DD", help="add KB-Verified: the commit confirms its sources are current")
    i = sub.add_parser("install-hooks", help="git config core.hooksPath .githooks (commit-msg adds KB-* trailers)")
    i.add_argument("--uninstall", action="store_true", help="unset core.hooksPath if it points at .githooks")
    c = sub.add_parser("check-trailers", help="exit 1 listing kb commits with missing or wrong KB-* trailers")
    c.add_argument("range", nargs="?", help="A..B or one commit (default: the CI push range, else @{upstream}..HEAD)")
    ln = sub.add_parser("lane", help="each commit's lane, content or code, and the code paths that decided it")
    ln.add_argument("range", nargs="?", help="A..B or one commit (default: the CI push range, else @{upstream}..HEAD)")
    cl = sub.add_parser("check-lanes", help="exit 1 listing code-lane commits no merged merge or pull request introduced")
    cl.add_argument("range", nargs="?", help="A..B or one commit (default: the CI push range, else @{upstream}..HEAD)")
    cl.add_argument("--forge", choices=("auto", "gitlab", "github", "none"), default="auto",
                    help="whom to ask (auto: the CI variables); none lists every code-lane commit")
    lg = sub.add_parser("log", help="commits that touched a source id, topic, answer id or path")
    lg.add_argument("target")
    lg.add_argument("-n", type=int, default=20, help="show at most N commits (default 20)")
    b = sub.add_parser("blame", help="the commit that introduced a line, and the sources it cites")
    b.add_argument("target", metavar="PATH:LINE")
    s = sub.add_parser("asof", help="a file as of a date (last commit on or before it) or a tag")
    s.add_argument("when", metavar="YYYY-MM-DD|TAG")
    s.add_argument("path")
    y = sub.add_parser("sync", help="fetch, rebase onto REMOTE/BRANCH, fix, run the gate, push with --push")
    y.add_argument("--push", action="store_true", help="push HEAD to REMOTE/BRANCH after a green gate (plain push, never --force)")
    y.add_argument("--dry-run", action="store_true", help="fetch and report what would happen; rebase, commit and push nothing")
    y.add_argument("--remote", help=f"the remote (default: the integration remote, git config {kbpublic.INTEGRATION_KEY}, else origin)")
    y.add_argument("--branch", default="main", help="the remote branch to rebase onto and push to (default main)")
    y.add_argument("--session", help="the Claude Code session sync runs in, as its Claude-Session url or id (default: "
                                     "KB_SESSION, else the session's environment; an empty value: unknown)")
    g = sub.add_parser("tag-census", help="annotated tag census-YYYY-MM-DD on HEAD (not pushed)")
    g.add_argument("date", metavar="YYYY-MM-DD")
    pb = sub.add_parser("publish", help="push the projection of the integration main (no kb/_querylog) to the public home")
    pb.add_argument("--remote", help=f"the public remote (default: git config {kbpublic.CONFIG_KEY})")
    pb.add_argument("--source", help="REMOTE/BRANCH to project (default: the integration remote's main)")
    pb.add_argument("--branch", default="main", help="the public remote's branch (default main)")
    pb.add_argument("--dry-run", action="store_true", help="fetch, project and report; push nothing")
    pb.add_argument("--rewrite", action="store_true", help="replace a public branch that is not an ancestor (force with lease)")
    pb.add_argument("--hook", action="store_true", help="the SessionStart form: print only a refusal or a failed push, exit 0 always")
    br = sub.add_parser("bridge", help="a branch of the public home to the integration remote: rebase its commits, gate, push by lane")
    br.add_argument("branch", help="the branch on the public home (its commits not on the public main)")
    br.add_argument("--push", action="store_true", help="push after a green gate (as sync --push); the public home is never written")
    br.add_argument("--dry-run", action="store_true", help="fetch and report the commits and the lane; check out and push nothing")
    br.add_argument("--remote", help=f"the integration remote (default: git config {kbpublic.INTEGRATION_KEY}, else origin)")
    cp = sub.add_parser("check-public", help="exit 1 listing commits of REV whose history touches kb/_querylog")
    cp.add_argument("rev", nargs="?", help="a commit (default HEAD)")
    h = sub.add_parser("hook", help="internal: run by the .githooks scripts")
    h.add_argument("name", choices=HOOKS)
    h.add_argument("args", nargs="*")
    a = ap.parse_args()
    if a.cmd == "sync":
        a.rerun = [os.path.abspath(__file__), *sys.argv[1:]]  # what rerun_sync repeats after a rebase changed this code
    cmds ={"trailers": cmd_trailers, "install-hooks": cmd_install_hooks, "check-trailers": cmd_check_trailers, "lane": cmd_lane, "check-lanes": cmd_check_lanes,
            "log": cmd_log, "blame": cmd_blame, "asof": cmd_asof, "tag-census": cmd_tag_census, "hook": cmd_hook,
            "sync": cmd_sync, "bridge": cmd_bridge, "publish": lambda a: (kbpublic.cmd_publish_hook if a.hook else kbpublic.cmd_publish)(a, KB),
            "check-public": lambda a: kbpublic.cmd_check_public(a, KB)}
    if a.cmd in cmds:
        try:
            sys.exit(cmds[a.cmd](a))
        except Problem as e:
            print(f"ERROR {e}")
            sys.exit(2)
    sys.exit(run(a))


if __name__ == "__main__":
    main()
