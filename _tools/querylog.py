#!/usr/bin/env python3
"""The query log pipeline for kb lookups (stdlib only): capture, distill, learn, apply and delivery, and its digest.
kb/_self/querylog.md describes it; this file is the one entry point the hooks and people run, and the stages live in
the ql_*.py modules beside it.

  querylog.py capture   the capture hook (UserPromptSubmit, PostToolUse, PostToolUseFailure and Stop, async, in
                        .claude/settings.json and the plugin): reads one hook event as JSON on stdin and appends at
                        most one row to the spool; prints nothing and exits 0 whatever happens (a logging hook must
                        never get in the way of a prompt)
  querylog.py launch    the SessionEnd and SessionStart hook: marks the ended session closed, then starts a detached
                        `distill --settle LAUNCH_SETTLE_S` when a closed session waits and no distill holds the lock
                        (SessionEnd with the session's transcript: always, with --session and --transcript); prints
                        nothing and exits 0
  querylog.py distill [--replay FILE] [--settle S] [--session ID --transcript PATH]
                        the closed sessions of the spool -> one run file in the local store (the `store` directory
                        beside the spool, laid out as kb/_querylog/): per lookup the question the kb was asked (never
                        the prompt) after the rules and the leak scan, the path:line citations of the kb lines it
                        returned (never the reply), and Haiku's judgement in capped batches (no text of Haiku's is
                        stored); an entry a local run file already holds is not distilled again. It reads every row
                        format capture has written (querylog.md, Spool), and skips and counts a row it cannot read.
                        Mode `local` deletes the spool rows of the entries written or dropped. Mode `auto` (in a
                        clone, or in a plugin host from its managed clone) deletes those of dropped entries only, then
                        runs `apply --push` under the same lock, which deletes the others once their run file is on
                        origin/main. --replay answers the Haiku calls from a recorded reply file ({"replies": [...]})
                        instead of `claude -p`. --session and --transcript first write a `usage` row (token counts
                        read from the transcript, never text or the path) for each kb prompt of that session, waiting
                        for the lock. Exit 0 done (or nothing to do), 1 the push of mode `auto` failed, 3 another
                        distill holds the lock
  querylog.py learn [--store DIR]
                        the store's run files and the kb at HEAD -> findings (default: the local store): every judged
                        miss re-run with pack first (`fixed-since` when it now passes), then eval, alias, expansion,
                        gap-candidate and report-only source findings; writes one findings file,
                        findings/<yyyy-mm>/<run-id>.jsonl, holding only the records that change a finding's state
                        (none: no file). Exit 0
  querylog.py apply [--store DIR] [--hold ID ...] [--clone DIR] [--plugin-data DIR] [--replay-research FILE]
                        the store's open eval findings (default: the local store) -> changes in this clone's working
                        tree, never committed or pushed: each eval row is written together with its fix (alias rows,
                        or the question as a doc2query expansion of one of the article's facts), the first candidate
                        with which every `rag.py eval` question passes, the mean pack of the eval questions does not
                        grow and off-kb `good` does not rise; an alias term already in an alias file or held by the kb
                        is refused. No accepted fix: the miss becomes a gap candidate (`no-fix`) and its fix
                        `rejected`. The gap step: an open gap candidate whose miss the pack still reproduces, with an
                        article in the lead (for a `none` pack, only a lead that matches more than half of the
                        question's key words the kb knows; for a `weak` pack, only a lead that holds the question's
                        subject: one line of its topic holding more than half of those words), becomes a dated
                        entry under that article's topic in its root's _gaps.md (candidate-gap -> gap); one off the
                        kb's domains (no lead, a lead no article holds, a stray `none` lead, a `weak` lead without the
                        subject) is `rejected` at candidate-gap. Research, only when the user's
                        config turns it on (`research`, `research_daily`; --clone DIR reads that clone's config and
                        daily count,
                        --plugin-data DIR a plugin host's): at most the day's runs left and RESEARCH_RUNS_PER_APPLY,
                        one `claude -p` (hooks off) per gap finding, whose candidate facts are kept only when their
                        quote is on the page (quotecheck); accepted facts and their source rows are added (gap ->
                        candidate-fact -> claim), a disagreement becomes a _conflicts.md entry, and nothing existing
                        is edited (build_index and check.py errors=0 after, else every file is put back).
                        --replay-research FILE answers the runs and page fetches from a recorded file. Source findings
                        are left alone, and so are the findings named by --hold and those recorded `apply-failed`
                        (FAILED_RETRIES). One findings file records each outcome (none: no file). Exit 0, 1 when
                        `rag.py eval` fails before an eval change
  querylog.py quotecheck URL QUOTE [--page FILE [--ctype TYPE]]
                        whether QUOTE (QUOTE_MIN_WORDS to QUOTE_MAX_WORDS words) is on the page at URL, fetched as
                        fetch.py fetches (or read from a recorded FILE) and reduced by fetch.py's to_text; entities,
                        whitespace, quote marks, Markdown links and emphasis normalized on both sides. Exit 0 on the
                        page, 1 not (the reason on stdout)
  querylog.py apply --push
                        the direct push, from a clone (explicit in every mode but `off`), under the distill lock:
                        fetch origin; check the CI of the last automatic commit on origin/main with `glab` or `gh`
                        (skipped with a note when neither is signed in; the host comes from origin's url, else
                        FALLBACK_GITLAB_HOST): a finished failure is red and gets a revert commit (KB-Auto: revert)
                        that keeps the store's files and records its findings `apply-failed`, an unfinished pipeline
                        stops the run; then, in the worktree beside the spool reset to origin/main: the local store's
                        run files that origin/main lacks, and its findings files that hold only learn's states for
                        findings origin/main does not record yet, copied into kb/_querylog and gated by `check` and
                        the leak scan; the worktree's learn and apply on that store; one commit of the copied files
                        and what learn and apply changed, with the KB-Auto values of its paths (querylog among
                        them), pushed once by `kbgit.py sync --push` (gate, rebase on origin/main, push to origin
                        only). Once the run files are on origin/main, the spool rows of their entries
                        are deleted (a failed push deletes nothing). A conflict sync cannot resolve pushes
                        querylog/<run-id> with `-o merge_request.create -o merge_request.target=main`, main unchanged,
                        and later runs leave that branch's findings alone until main holds them. In a plugin host the
                        same push runs from a managed clone of the plugin's install source (known_marketplaces.json)
                        under ${CLAUDE_PLUGIN_DATA}/querylog/clone, and a push the remote refuses for want of rights
                        (GitLab's `You are not allowed to push code ...`, GitHub's `Permission to ... denied` or
                        `GH006`, an HTTP 403) writes DISABLED and deletes the spool; a network error or a red gate
                        does not. In a cloud session (CLAUDE_CODE_REMOTE=true) the push goes to the branch the clone
                        has checked out, the only one its git proxy takes. Exit 0 (pushed, nothing to push, CI
                        pending, conflict branch pushed), 1 a step failed, 2 refused, 3 the lock
  querylog.py queue [N] [--store DIR]
                        the research queue for `/kb-research --queue` (default: the committed store kb/_querylog): each
                        open gap finding with its _gaps.md entry re-run with pack on HEAD first, one that passes now
                        recorded `fixed-since` (one findings file) and left out; an entry whose newest `Tried` note is
                        younger than QUEUE_TRIED_DAYS on HEAD's commit day waits; the rest one item per question,
                        ranked by the logged lookups that asked it, then the oldest lookup, and the top N printed by
                        topic with the question and each of its finding ids with its entry's path:line. The same store
                        and HEAD print the same lines in any clone. Exit 0, 1 when a closed gap reappears (a later
                        record after its claim, or its entry without a Resolved note)
  querylog.py close F-ID [F-ID ...] (--claim | --tried NOTE | --reject) [--store DIR]
                        records what `/kb-research --queue` did with the gap findings of one queue item: --claim once
                        each _gaps.md entry carries a `Resolved <date>:` note (gap -> claim, by kb-research); --tried
                        writes the note `Tried <date>: NOTE` under each entry and records the day; --reject once each
                        entry was removed as off the kb's domains (-> candidate-gap, `rejected`, as the gap step
                        records one). One findings file per finding; no older file is edited. Exit 0, 1 when one was
                        refused
  querylog.py check [DIR]  the store gates over DIR (default kb/_querylog): header and provenance fields, entry fields,
                        identifiers, fetch entries, duplicate ids and the findings files; one line per problem, exit 1
                        when there is any
  querylog.py where     prints the mode, the config file, the spool directory and whether capture writes
  querylog.py digest [--store DIR] [--week YYYY-Www]
                        the week's numbers from the committed store (default kb/_querylog): lookups by surface,
                        verdicts, judgements, misses and how many are fixed, fetches and their result characters, run
                        files and dropped entries, finding records written, and findings by kind and state at the
                        week's end. The week defaults to the ISO week of the store's newest entry; only the store and
                        the week go in, so every clone at one commit prints the same lines. Exit 0, 2 a bad week
  querylog.py digest --hook
                        the SessionStart hook (synchronous, `timeout` DIGEST_HOOK_TIMEOUT_S): at the first
                        SessionStart of an ISO week (the marker `digest-week` beside the spool), last week's digest
                        as one JSON line {"systemMessage": ...}, which Claude Code shows the person; nothing when
                        logging is off, the week is empty or reading the store took over DIGEST_BUDGET_S. Exit 0
  querylog.py status [--store DIR]
                        open source findings of the committed store, most result characters first; open merge
                        requests from querylog/ branches on origin's forge (glab or gh, skipped with a note when not
                        signed in); automatic commits reverted (KB-Auto: revert in git log). Exit 0

Modules: ql_base.py (places, config, the lock, commands), ql_capture.py (the capture hook and `record`, which
kb_hook.py, kb_ask.py, fetch.py and census.py call), ql_distill.py (distill and the launcher), ql_store.py (run and
findings files, and the store gates), ql_learn.py, ql_apply.py, ql_research.py (research, the quote check and the
research queue),
ql_deliver.py (apply --push, plugin hosts, cloud sessions) and ql_report.py (digest and status).

Where (querylog.md, Spool and Configuration): in a clone `_cache/querylog/spool/<session_id>.jsonl` (rows without a
session: `tools-<yyyy-mm-dd>.jsonl`), the config file `_private/querylog.json` and the marker
`_cache/querylog/DISABLED`; in a plugin host (the hook runs this copy as CLAUDE_PLUGIN_ROOT) the same names under
`${CLAUDE_PLUGIN_DATA}/querylog/`, with `config.json`. No environment variable configures anything. Nothing is
written when the mode is `off` (or the config file cannot be read: fail closed), when the DISABLED marker exists, or
when Claude Code does not run the hooks (`--settings '{"disableAllHooks": true}'`, which every `claude -p` the pipeline
starts carries).
"""
import argparse, datetime, sys


def off(verb):
    """Whether a learn or apply on the default local store has nothing to do because logging is off (said so)."""
    from ql_base import logging_off, places
    if logging_off(*places()):
        print(f"{verb}: logging is off")
        return True
    return False


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["capture"]:
        import ql_base, ql_capture
        return ql_base.stdin_hook(ql_capture.capture)
    if argv == ["where"]:
        import ql_capture
        return ql_capture.where()
    if argv == ["launch"]:
        import ql_base, ql_distill
        return ql_base.stdin_hook(ql_distill.launch)
    if argv[:1] == ["check"] and len(argv) <= 2:
        import ql_store
        return ql_store.check(argv[1] if len(argv) > 1 else None)
    if argv[:1] == ["learn"]:
        ap = argparse.ArgumentParser(prog="querylog.py learn")
        ap.add_argument("--store", help="the store to learn from and write findings to (default: the local store)")
        a = ap.parse_args(argv[1:])
        if a.store is None and off("learn"):
            return 0
        import ql_learn
        return ql_learn.learn(a.store)
    if argv[:1] == ["apply"]:
        ap = argparse.ArgumentParser(prog="querylog.py apply")
        ap.add_argument("--store", help="the store whose findings to apply and record (default: the local store)")
        ap.add_argument("--hold", action="append", default=[], metavar="ID",
                        help="leave this finding alone (a finding pending on a conflict branch; repeatable)")
        ap.add_argument("--push", action="store_true",
                        help="apply in the worktree beside the spool on origin/main's kb/_querylog, commit, and push "
                             "to origin through kbgit.py sync")
        ap.add_argument("--clone", metavar="DIR",
                        help="the clone whose per-user config (_private/querylog.json) turns research on and whose "
                             "_cache/querylog counts the day's research runs (apply --push names its own clone)")
        ap.add_argument("--plugin-data", metavar="DIR",
                        help="the plugin host's querylog directory whose config.json turns research on and which "
                             "counts the day's research runs (the push from a host names it)")
        ap.add_argument("--replay-research", metavar="FILE",
                        help="answer the research runs and the quote check's page fetches from this recorded file "
                             '({"replies": [...], "pages": {url: file}})')
        a = ap.parse_args(argv[1:])
        if a.push and (a.store or a.clone or a.plugin_data or a.replay_research):
            print("apply --push: refused: the store is the worktree's kb/_querylog and the clone is this one; "
                  "--store, --clone, --plugin-data and --replay-research are for a local apply", file=sys.stderr)
            return 2
        if a.store is None and off("apply"):
            return 0
        if a.push:
            import ql_deliver
            return ql_deliver.push()
        import ql_apply, ql_research
        day = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        rq, rcfg = ql_research.research_places(a.clone, a.plugin_data)
        runs = min(ql_research.research_budget(rq, rcfg, day), ql_research.RESEARCH_RUNS_PER_APPLY)
        research = None
        if runs:
            replay = ql_research.ResearchReplay(a.replay_research) if a.replay_research else None
            research = ql_research.Researcher(runs, call=replay, fetcher=replay.fetch if replay else None,
                                              counted=lambda: ql_research.count_research(rq, day))
        return ql_apply.apply(a.store, hold=set(a.hold), research=research, day=day)
    if argv[:1] == ["quotecheck"]:
        ap = argparse.ArgumentParser(prog="querylog.py quotecheck")
        ap.add_argument("url")
        ap.add_argument("quote")
        ap.add_argument("--page", metavar="FILE", help="read the page from this recorded file instead of the url")
        ap.add_argument("--ctype", default="", help="the recorded page's content type (default: from its suffix)")
        a = ap.parse_args(argv[1:])
        import ql_research
        ok, why = ql_research.quotecheck(a.url, a.quote, ql_research.page_file(a.page, a.ctype) if a.page else None)
        print(f"quotecheck: {why}")
        return 0 if ok else 1
    if argv[:1] == ["queue"]:
        ap = argparse.ArgumentParser(prog="querylog.py queue")
        ap.add_argument("n", nargs="?", type=int, help="list the top N gaps (default: all)")
        ap.add_argument("--store", help="the store to read and record in (default: kb/_querylog, the committed store)")
        a = ap.parse_args(argv[1:])
        import ql_research
        return ql_research.queue(a.store, a.n if a.n and a.n > 0 else None)
    if argv[:1] == ["close"]:
        ap = argparse.ArgumentParser(prog="querylog.py close")
        ap.add_argument("finding", nargs="+", help="the gap findings' ids (F-<12 hex>) of one queue item")
        how = ap.add_mutually_exclusive_group(required=True)
        how.add_argument("--claim", action="store_true", help="its _gaps.md entry is resolved: promote it to claim")
        how.add_argument("--tried", metavar="NOTE", help="not settled: add the dated note NOTE under its entry")
        how.add_argument("--reject", action="store_true", help="its _gaps.md entry was removed as off the kb's "
                         "domains: record it rejected at candidate-gap")
        ap.add_argument("--store", help="the store to record in (default: kb/_querylog, the committed store)")
        a = ap.parse_args(argv[1:])
        import ql_research
        return max(ql_research.close(f, claim=a.claim, tried=a.tried, store=a.store, reject=a.reject)
                   for f in a.finding)
    if argv[:1] == ["digest"]:
        ap = argparse.ArgumentParser(prog="querylog.py digest")
        ap.add_argument("--store", help="the store to read (default: kb/_querylog, the committed store)")
        ap.add_argument("--week", help="the ISO week YYYY-Www (default: the week of the store's newest entry)")
        ap.add_argument("--hook", action="store_true", help="the SessionStart hook: last week's digest as a "
                        "systemMessage, once per ISO week")
        a = ap.parse_args(argv[1:])
        import ql_report
        if a.hook:
            return ql_report.hook_digest()
        try:
            _, lines, _ = ql_report.digest(a.store, a.week)
        except ValueError as e:
            print(f"digest: {e}", file=sys.stderr)
            return 2
        print("\n".join(lines))
        return 0
    if argv[:1] == ["status"]:
        ap = argparse.ArgumentParser(prog="querylog.py status")
        ap.add_argument("--store", help="the store to read (default: kb/_querylog, the committed store)")
        a = ap.parse_args(argv[1:])
        import ql_report
        return ql_report.status(a.store)
    if argv[:1] == ["distill"]:
        ap = argparse.ArgumentParser(prog="querylog.py distill")
        ap.add_argument("--replay", help="answer the Haiku calls from this recorded reply file")
        ap.add_argument("--settle", type=float, default=0.0, help="seconds to wait after taking the lock")
        ap.add_argument("--session", help="the session whose usage rows are written first (with --transcript)")
        ap.add_argument("--transcript", help="that session's transcript, read for its kb prompts' token usage")
        a = ap.parse_args(argv[1:])
        if bool(a.session) != bool(a.transcript):
            ap.error("--session and --transcript go together")
        import ql_base, ql_distill
        return ql_distill.distill(haiku=ql_base.Replay(a.replay) if a.replay else None, settle=a.settle,
                                  usage_from=(a.session, a.transcript) if a.session else None)
    if argv in (["-h"], ["--help"]):
        print(__doc__.strip())
        return 0
    print(__doc__.strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
