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
import argparse, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kbpublic  # noqa: E402
import kg_bridge  # noqa: E402
import kg_hooks  # noqa: E402
import kg_lane  # noqa: E402
import kg_sync  # noqa: E402
import kg_trailers  # noqa: E402
from kg_base import KB, Problem  # noqa: E402
from kg_history import cmd_asof, cmd_blame, cmd_log, cmd_tag_census  # noqa: E402,F401
from kg_hooks import HOOKS, cmd_install_hooks, hooks_path_is_ours  # noqa: E402
from kg_trailers import (AUTO, AUTO_VALUES, INDEX, KEY_LINE, STRAY_WORK, WORK, apply_trailers, blob,  # noqa: E402,F401
                         changed_paths, cmd_check_trailers, cmd_trailers, compute, default_range, is_content, log_records,
                         message_trailers, parse_trailers, source_rows_of, stray_work, trailer_audit,
                         valid_date, work_state)
from kg_merge import FB, canon_csv, has_markers, id_key, lf, run, strip_markers  # noqa: E402,F401


FIX_COMMIT = kg_sync.FIX_COMMIT  # ql_deliver.py reads it: the subject of the commit sync makes from what fix changed


# ---------------------------------------------------------------- sync (kg_sync.py): the facade gives it the trailer code


def sync_host():
    """What kg_sync takes from this module: the trailer audit, the fix commit's message and the hooks check, read when
    sync runs."""
    return kg_sync.Host(trailer_audit, lambda body: apply_trailers(body, compute(kg_trailers.rev_parse("HEAD") or "", INDEX)),
                        hooks_path_is_ours)


def gate(r, up, fix_check=False):
    """kg_sync.gate with this module's trailer audit (the pre-push hook adds `fix_check`)."""
    return kg_sync.gate(r, up, sync_host(), fix_check)


def cmd_sync(a, r=None):
    return kg_sync.cmd_sync(a, sync_host(), r)


def hook_pre_push(args, stdin):
    return kg_hooks.hook_pre_push(args, stdin, gate, kg_sync.dirty_paths)


def cmd_hook(a):
    return kg_hooks.cmd_hook(a, gate, kg_sync.dirty_paths)


def cmd_lane(a):
    return kg_lane.cmd_lane(a, default_range)


def cmd_check_lanes(a):
    return kg_lane.cmd_check_lanes(a, default_range)


def cmd_bridge(a):
    return kg_bridge.cmd_bridge(a, cmd_sync)


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
