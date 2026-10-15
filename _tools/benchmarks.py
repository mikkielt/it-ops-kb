#!/usr/bin/env python3
"""The kb's benchmarks: every measurement of kb/_self/reports/benchmarks.md, run again by one command (stdlib only).

  benchmarks.py list                        the scenarios, each with its report section
  benchmarks.py run [SCENARIO ...] [--reps N] [--arm ARM] [--out FILE] [--arms A,B] [--kinds K,K] [--effort L,L] [--dry-run]
                    [--shape fresh|session|fresh,session] [--seed N] [--jobs N] [--max-usd X] [--sample N]
                    [--arm-reps ARM=N,...] [--arm-kinds ARM=K+K,...]
                                            run every scenario, or the named ones, and write their rows to the results
                                            file (kb/_self/reports/benchmarks.csv; rows of the same scenario and date
                                            are replaced), or to FILE; prints each scenario's rows and the spend;
                                            --arm names the arm of `navigation` (default `current`): a run replaces
                                            only its own arm's rows; `pool` runs the question pool (bench_pool.py)
                                            on the --arms (default bench_pool.DEFAULT_ARMS, and opus-5-5 when named, on
                                            its sanity subset of four kinds unless --kinds or --arm-kinds name others;
                                            --arm-kinds opus-5-5=all runs every row),
                                            the --kinds (default every kind) and the --effort levels (default low,default) and replaces the rows of the
                                            arms it ran; --dry-run prints its plan and starts no model, and with any other
                                            scenario, or none named, exits 2 naming those that have a plan; --shape
                                            session runs the pool in groups of six questions, each group in one
                                            session (the kb arms haiku-5-5 and sonnet-5-5, seed --seed) and records
                                            per position the marginal input and the cache-read share; --jobs N
                                            runs up to N of its `claude -p` runs at once (a session's questions stay in
                                            order), the rows and their order the same as with 1; --max-usd X starts no
                                            new run once the finished runs, those in flight and the run to start, each at
                                            the mean cost of its kind, would pass X (those in flight finish), records
                                            a `spend_stopped` row per arm naming the runs not started and exits 1;
                                            --dry-run also prints an estimate of the spend, each kind at its own cost; --shape fresh,session runs both
                                            shapes in one run under the one --max-usd; --arm-reps and --arm-kinds give an
                                            arm (or ARM/session, in the session shape only) its own reps and kinds, the
                                            arms not named taking --reps and --kinds, and an arm they name that the run
                                            does not run is an error; --sample N keeps N rows of each kind, seeded by
                                            --seed; `freshness` looks up each answerable pool row (route `good`, the
                                            --sample rows of each kind) with the cited sources revalidated live and
                                            records per provider host and for all the printed DOC lines current, moved,
                                            not found, source-dated only and not checked, the requests made and the
                                            wall time per question (no model; --dry-run prints the sources and requests)
  benchmarks.py pool build [--querylog] [--seed N] [--out FILE] [--ask] [--redo ID]... [--dry-run]
                                            [--replies FILE]
                                            write the stratified question pool, with a check per row, to
                                            kb/public/_retrieval/bench_pool.csv, or with --querylog the redacted
                                            query-log questions to kb/_querylog/bench/pool.csv (bench_pool.py);
                                            the rows of kb/public/_retrieval/bench_scenarios.csv join the public
                                            pool as the kinds sc_present, sc_partial, sc_absent, sc_offkb and
                                            sc_stale, six each;
                                            the paid call for the eval rows the file lacks is made only with --ask
                                            or --redo; without either the build lists those rows and the estimated
                                            spend, writes nothing and exits 1;
                                            --redo asks the paid call again for the eval rows it names (a pool row
                                            id or an eval case id), --dry-run lists the rows it would ask and the
                                            estimated spend, and asks nothing; --replies FILE answers the --redo
                                            rows from the first check of the same rows in a pool csv, no model
  benchmarks.py pool check [--querylog] [FILE]
                                            exit 1 on a pool row without a usable check, a held-out row with text, a
                                            leak, a kind off its count or a scenario row whose expected route is not
                                            the route `rag.py pack` prints for its question
  benchmarks.py pool verify [--file F] [--record R]
                                            exit 1, naming each, when the pool record R (default the newest) of the results
                                            file F breaks one of the record's consistency properties (bench_pool.py,
                                            verify_problems); the rows it reads are the record's own
  benchmarks.py pool respend [--file F] [--record R]
                                            narrow the spend rows of the pool record R (default the newest) of the results
                                            file F that name an arm label a later spend row of the record also names (a
                                            same-day rerun replaced that label's runs), totalling each from the record's
                                            own rows; no paid run (bench_pool.py, settle_spend); a run does this itself
  benchmarks.py repro setup --instances N [--start REV] [--dir DIR] [--dry-run]
                                            build N isolated instances of one pinned commit (bench_repro.py): a
                                            bare copy DIR/originN.git of REV's history (default REV: the parent of
                                            the first commit that added kb/public/_retrieval/repro_bench.csv, else
                                            the integration main's tip; DIR: _cache/bench-repro of the clone's main
                                            worktree), a working clone of it under the scratch directory whose only
                                            remote is that bare, its query log `off` and an mcp-config file of its
                                            own (use it with --strict-mcp-config); prints each path; --dry-run
                                            prints the plan and starts nothing; exit 2 on a refusal
  benchmarks.py repro check                 build one probe instance as `repro setup` does, commit one _gaps.md entry in
                                            it, run `kbgit.py sync --push` there and exit 0 only when the probe's bare
                                            main moved to that commit, the commit is not in a fresh fetch of the real
                                            origin's main, its mcp-config names its own kb_mcp.py whose --status prints
                                            its kb_dir, its query log mode is off and its claims ledger and _cache are
                                            its own; then removes the probe; exit 1 naming each failure, 2 on a refusal
  benchmarks.py repro questions [--briefs FILE] [--file FILE]
                                            check the frozen questions (kb/public/_retrieval/repro_bench.csv) against
                                            the briefs (repro_briefs.csv): exit 1 naming each area without 3 to 5 rows,
                                            a duplicate id, a row with no expect_re, expect_text or expect_paths and a
                                            question that kbfacts.routed routes to a tool, or no brief rows at all
  benchmarks.py repro run [--instances N] [--model M] [--effort E] [--max-turns T] [--area-usd A] [--instance-usd C]
                          [--timeout S] [--dir DIR] [--dry-run]
                                            start every instance of DIR's instances.json at the same time, each running one
                                            headless `claude -p` /kb-research session per area of repro_briefs.csv in the
                                            briefs' order, in the instance's clone with its env and mcp-config, the
                                            project's hooks on, the gitkraken and caveman plugins off by --settings, the
                                            same argv and prompt for every instance; each area's clone is reset to its
                                            bare's main first and the bare's main sha is recorded before and after;
                                            appends one json line per area to DIR/results.jsonl (cost, tokens, turns, tool
                                            calls, wall time, model usage, failure: budget, turns, timeout or error, and
                                            the shas); an instance starts no further area once its recorded spend
                                            reaches --instance-usd and records the areas left as failures named budget;
                                            a run again skips the areas with a result and retries the failed ones;
                                            --dry-run starts nothing and prints each argv, the estimate and each refusal,
                                            exit 0 (1 for a briefs problem); a real run exits 2 on a refusal (no
                                            instances.json, `repro questions` failing, the start commit holding
                                            repro_bench.csv) and 1 when an area failed
  benchmarks.py repro record [--dir DIR] [--file FILE] [--briefs FILE] [--questions FILE] [--dry-run]
                                            merge the json lines of DIR/results.jsonl (the newest of each instance and
                                            area) into the results file (kb/_self/reports/benchmarks.csv) as the scenario
                                            `repro`: record the first 7 characters of the start sha of DIR's
                                            instances.json, arm `instance-N`, case the area, and the metrics cost,
                                            input, out, cache_read, cache_write, turns, tool_calls, wall_s, models,
                                            failure (`none` when the area finished), main_before and main_after; the
                                            note holds the start sha and the sha256 of the briefs and of the questions
                                            files; it replaces the rows of that record and a second run of it changes
                                            nothing; --dry-run prints the rows and writes nothing; exit 0 with no lines,
                                            2 on a refusal (no instances.json, no briefs or questions file)
  benchmarks.py repro compare [--dir DIR] [--record] [--file FILE] [--questions FILE] [--dry-run]
                                            measure how alike the instances' research is: each instance's bare main
                                            against the start commit in a detached checkout of its own, area by area
                                            by the shas `repro run` recorded, its own tools run by subprocess; per
                                            instance and area the articles, facts and sources added and the tag mix
                                            of `rag.py audit`; per pair of instances the Jaccard overlap of the added
                                            source urls and of the added facts (one claim: a difflib ratio of at
                                            least bench_repro.SAME_CLAIM on one article path), and the conflicts (a
                                            matched pair whose numbers differ, both lines listed); per instance the
                                            check.py and kb-verify lint errors and the passed rows and verdicts of the
                                            frozen questions (`rag.py eval`); per area the agreement; --record merges
                                            the numbers into the results file as the scenario `repro-compare`;
                                            --dry-run prints the metrics and the instances it would read; exit 0 also
                                            with no instances.json, 2 on a refusal
  benchmarks.py repro status [--dir DIR]    print per instance of DIR's instances.json the commits on its bare since the
                                            start commit and whether each is in a fresh fetch of the real origin's
                                            main; exit 1 when any is, 2 on a refusal; exit 0 with no instances.json
  benchmarks.py report [--check]            write the report's generated tables from the results file; --check writes
                                            nothing and exits 1 when a table, or a number in README.md, disagrees with
                                            the results file, or a `bench:` marker names a scenario with no rows in it

The results file has one row per scenario, record, case, arm and metric: `record` names one measurement (the date of a
run of this tool, or the commit of a historical number taken from the reports it replaced), with its date, commit,
Claude Code version and kb size (topics). The report's tables sit between `<!-- bench:table SCENARIO metrics=... -->`
and `<!-- /bench -->` (a cell is each record's value in date order and the change of the newest from the one before),
and its records tables between `<!-- bench:records SCENARIO -->` and `<!-- /bench -->`.

Isolation: model runs start `claude -p` with hooks off (kbcommon.NO_HOOKS) from a throwaway clone of HEAD under the
scratch directory (BENCH_SCRATCH, default <temp>/it-ops-kb-bench) whose query log is `off` and whose origin is a local
bare repository; the scenarios that measure the query log's hooks run them in a throwaway clone in mode `local` with a
local bare origin, or as a plugin copy whose hooks write under the scratch directory. Nothing a run does reaches this
clone's spool, a plugin data directory of ~/.claude or a real remote. A clone gets the servers of `kb_mcp.py
--register-local` for its own path; they are removed at the end of the run.

Paid scenarios (each a `claude -p` per case): headless, subagents, models, router, route-by-verdict, howto, partial, files-subagents,
files-headless, host-lookups, new-model, always-on, kb-lookup-agent, retrieval and doc2query (their blind questions), research,
ingest, host-roots, navigation (three prompts per arm), querylog-pipeline (one real Haiku batch). The rest run no
model.
"""
import argparse, sys, time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import bench_pool  # noqa: E402
import bench_repro  # noqa: E402
from bench_core import (ARMED, HOME, RAW, RESULTS, SLOTTED, SPEND, Bench, Skip, merge_rows, read_rows,  # noqa: E402
                        scratch_dir, write_rows)
from bench_report import empty_markers, readme_misses, render  # noqa: E402
from bench_install import s_host_roots, s_ingest, s_kbpy, s_new_model  # noqa: E402
from bench_lookup import (s_always_on, s_files_headless, s_files_subagents, s_headless, s_host_lookups, s_howto,
                          s_kb_lookup_agent, s_models, s_navigation, s_partial, s_route_by_verdict, s_router,
                          s_subagents)  # noqa: E402
from bench_querylog import s_querylog_hooks, s_querylog_pipeline, s_redaction, s_research  # noqa: E402
from bench_retrieval import s_doc2query, s_freshness, s_retrieval, s_tool_speed, s_verdict  # noqa: E402

REPORT = HOME / "kb" / "_self" / "reports" / "benchmarks.md"
README = HOME / "README.md"


SCENARIOS = {  # name: (report section, function)
    "headless": ("Bare agent against agent with the kb: headless sessions", s_headless),
    "subagents": ("Bare agent against agent with the kb: subagents", s_subagents),
    "models": ("Models and hand-off patterns", s_models),
    "router": ("Routing by verdict", s_router),
    "route-by-verdict": ("Routing by verdict against the bare agent", s_route_by_verdict),
    "howto": ("How-to questions and SNIPPET units", s_howto),
    "partial": ("Partial knowledge, newer versions and stale copies", s_partial),
    "files-subagents": ("Reading files without the lookup tools", s_files_subagents),
    "files-headless": ("Lookup tools against reading files", s_files_headless),
    "host-lookups": ("Plugin in a host project", s_host_lookups),
    "always-on": ("Always-on cost", s_always_on),
    "kb-lookup-agent": ("kb-lookup agent start context", s_kb_lookup_agent),
    "retrieval": ("Retrieval quality", s_retrieval),
    "verdict": ("Verdict corrections", s_verdict),
    "doc2query": ("doc2query", s_doc2query),
    "tool-speed": ("Tool speed", s_tool_speed),
    "freshness": ("Freshness of the cited sources", s_freshness),
    "querylog-hooks": ("Query log hooks", s_querylog_hooks),
    "querylog-pipeline": ("Distill, learn and apply", s_querylog_pipeline),
    "redaction": ("Redaction speed", s_redaction),
    "research": ("Research cost per accepted fact", s_research),
    "ingest": ("/kb-ingest on a sample repository", s_ingest),
    "host-roots": ("A host plugin with team roots", s_host_roots),
    "kbpy": ("Hook launcher start-up", s_kbpy),
    "new-model": ("A new model against the one it replaces", s_new_model),
    "navigation": ("Finding the code", s_navigation),
    "pool": ("A question pool over the kb, router, hook and web arms", bench_pool.s_pool),
}
PLANNED = ("pool", "freshness")  # the scenarios that read `b.dry`: they print a plan and start no model, the others have no plan


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    r = sub.add_parser("run")
    r.add_argument("scenarios", nargs="*")
    r.add_argument("--reps", type=int, default=1)
    r.add_argument("--arm", default="current", help="the arm of the navigation scenario's rows (default: current)")
    r.add_argument("--out")
    r.add_argument("--arms", help="the arms of `pool`, comma separated (default: " + ",".join(bench_pool.DEFAULT_ARMS) + "; also "
                   + ",".join(bench_pool.OPT_IN) + ", named here only)")
    r.add_argument("--kinds", help="the pool kinds `pool` runs, comma separated (default: every kind; the opus-5-5 arm: its sanity subset, "
                   + "+".join(bench_pool.SUBSET_KINDS["opus-5-5"]) + ")")
    r.add_argument("--effort", help="the effort levels of the kb arms of `pool`, comma separated (default: "
                   + ",".join(bench_pool.EFFORTS) + ")")
    r.add_argument("--dry-run", action="store_true", help="print the plan of `pool` or `freshness` and start no model or request (another scenario has no plan: exit 2)")
    r.add_argument("--shape", default="fresh",
                   help="`pool`: a fresh session per question, or groups of six questions in one session, or both, comma "
                   "separated (default: fresh)")
    r.add_argument("--seed", type=int, default=bench_pool.SEED, help="the seed that orders the groups of `pool --shape session`")
    r.add_argument("--jobs", type=int, default=1, help="`pool`: runs at once (default: 1)")
    r.add_argument("--max-usd", type=float, help="`pool`: start no new run once the finished runs, those in flight and the run to start, each at the mean cost of its kind, would pass this many US dollars")
    r.add_argument("--sample", type=int, help="`pool`, `freshness`: keep this many rows of each kind, drawn with --seed (default: every row)")
    r.add_argument("--arm-reps", action="append", metavar="ARM=N",
                   help="`pool`: the reps of an arm (ARM/session: of the session shape), comma separated or repeated; the arms "
                   "not named take --reps")
    r.add_argument("--arm-kinds", action="append", metavar="ARM=K+K",
                   help="`pool`: the kinds of an arm (ARM/session: of the session shape), K+K, or all for every kind, comma "
                   "separated or repeated; the arms not named take --kinds")
    pool = sub.add_parser("pool").add_subparsers(dest="pool_cmd", required=True)
    pb = pool.add_parser("build")
    pb.add_argument("--querylog", action="store_true")
    pb.add_argument("--seed", type=int, default=bench_pool.SEED)
    pb.add_argument("--out")
    pb.add_argument("--ask", action="store_true",
                    help="make the paid call for the eval rows the --out file lacks (without --ask or --redo the build lists them and exits 1)")
    pb.add_argument("--redo", action="append", metavar="ID",
                    help="ask again for the check of this eval row (a pool row id or an eval case id); repeatable")
    pb.add_argument("--replies", metavar="FILE", help="with --redo: take the new checks from the eval rows of this pool csv, no model")
    pb.add_argument("--dry-run", action="store_true", help="list the rows a build would ask and the estimated spend; write nothing")
    pc = pool.add_parser("check")
    pc.add_argument("--querylog", action="store_true")
    pc.add_argument("file", nargs="?")
    pv = pool.add_parser("verify")
    pv.add_argument("--file", help="the results file (default: kb/_self/reports/benchmarks.csv)")
    pv.add_argument("--record", help="the pool record to check (default: the newest of the file)")
    ps = pool.add_parser("respend")
    ps.add_argument("--file", help="the results file (default: kb/_self/reports/benchmarks.csv)")
    ps.add_argument("--record", help="the pool record to repair (default: the newest of the file)")
    rep = sub.add_parser("report")
    rep.add_argument("--check", action="store_true")
    rp = sub.add_parser("repro").add_subparsers(dest="repro_cmd", required=True)
    rs = rp.add_parser("setup")
    rs.add_argument("--instances", type=int, required=True, help="the number of instances (1 or more)")
    rs.add_argument("--start", metavar="REV", help="the commit every instance starts at (default: the parent of the first "
                    "commit that added " + bench_repro.ADDED + ", else the integration main's tip)")
    rs.add_argument("--dir", help="where the bare origins go (default: _cache/bench-repro of the clone's main worktree)")
    rs.add_argument("--dry-run", action="store_true", help="print the plan and start nothing")
    rp.add_parser("check")
    rq = rp.add_parser("questions")
    rq.add_argument("--briefs", metavar="FILE", help="the briefs file (default: " + bench_repro.BRIEFS + ")")
    rq.add_argument("--file", metavar="FILE", help="the frozen questions (default: " + bench_repro.ADDED + ")")
    rr = rp.add_parser("run")
    d = bench_repro.DEFAULTS
    rr.add_argument("--instances", type=int, help="the instances to run, the first N of instances.json (default: all)")
    rr.add_argument("--model", default=d["model"], help=f"the model of every session (default: {d['model']})")
    rr.add_argument("--effort", default=d["effort"], help=f"the effort of every session (default: {d['effort']})")
    rr.add_argument("--max-turns", type=int, default=d["max_turns"], help=f"turns of one area's session (default: {d['max_turns']})")
    rr.add_argument("--area-usd", type=float, default=d["area_usd"], help=f"US dollars of one area's session (default: {d['area_usd']:g})")
    rr.add_argument("--instance-usd", type=float, default=d["instance_usd"],
                    help=f"start no further area of an instance once its recorded spend reaches this (default: {d['instance_usd']:g})")
    rr.add_argument("--timeout", type=int, default=d["timeout"], help=f"seconds of one area's session (default: {d['timeout']})")
    rr.add_argument("--dir", help="the instances' directory (default: _cache/bench-repro of the clone's main worktree)")
    rr.add_argument("--dry-run", action="store_true", help="start nothing: print each instance's argv, the estimate and each refusal")
    rc = rp.add_parser("record")
    rc.add_argument("--dir", help="the instances' directory (default: _cache/bench-repro of the clone's main worktree)")
    rc.add_argument("--file", metavar="FILE", help="the results file (default: kb/_self/reports/benchmarks.csv)")
    rc.add_argument("--briefs", metavar="FILE", help="the briefs file whose sha256 goes in the note (default: " + bench_repro.BRIEFS + ")")
    rc.add_argument("--questions", metavar="FILE",
                    help="the frozen questions whose sha256 goes in the note (default: " + bench_repro.ADDED + ")")
    rc.add_argument("--dry-run", action="store_true", help="print the rows it would merge and write nothing")
    rm = rp.add_parser("compare")
    rm.add_argument("--dir", help="the instances' directory (default: _cache/bench-repro of the clone's main worktree)")
    rm.add_argument("--record", action="store_true", help="merge the numbers into the results file as the scenario repro-compare")
    rm.add_argument("--file", metavar="FILE", help="with --record: the results file (default: kb/_self/reports/benchmarks.csv)")
    rm.add_argument("--questions", metavar="FILE", help="the frozen questions (default: " + bench_repro.ADDED + ")")
    rm.add_argument("--dry-run", action="store_true", help="start nothing: print the metrics and the instances it would read")
    rt = rp.add_parser("status")
    rt.add_argument("--dir", help="the instances' directory (default: _cache/bench-repro of the clone's main worktree)")
    a = ap.parse_args(argv)
    if a.cmd == "list":
        for name, (section, _) in SCENARIOS.items():
            print(f"{name:18} {section}")
        return 0
    if a.cmd == "pool":
        return bench_pool.cli(a)
    if a.cmd == "repro":
        if a.repro_cmd == "setup" and a.instances < 1:
            print("--instances needs 1 or more", file=sys.stderr)
            return 2
        if a.repro_cmd == "run":
            bad = [f"{flag} needs {what}" for flag, v, what in (
                ("--instances", a.instances, "1 or more"), ("--max-turns", a.max_turns, "1 or more"),
                ("--timeout", a.timeout, "1 or more"), ("--area-usd", a.area_usd, "more than 0"),
                ("--instance-usd", a.instance_usd, "more than 0")) if v is not None and v < (1 if what == "1 or more" else 1e-9)]
            if bad:
                print("; ".join(bad), file=sys.stderr)
                return 2
        try:
            if a.repro_cmd == "check":
                return bench_repro.check()
            if a.repro_cmd == "questions":
                return bench_repro.questions(a.briefs, a.file)
            if a.repro_cmd == "status":
                return bench_repro.status(a.dir)
            if a.repro_cmd == "record":
                return bench_repro.record_results(a.dir, a.file, a.briefs, a.questions, a.dry_run)
            if a.repro_cmd == "compare":
                return bench_repro.compare(a.dir, a.record, a.file, a.questions, a.dry_run)
            if a.repro_cmd == "run":
                return bench_repro.run(a.instances, a.dir, a.dry_run, model=a.model, effort=a.effort, max_turns=a.max_turns,
                                       area_usd=a.area_usd, instance_usd=a.instance_usd, timeout=a.timeout)
            return bench_repro.setup(a.instances, a.start, a.dir, a.dry_run)
        except bench_repro.Refused as e:
            print(f"repro {a.repro_cmd}: {e}", file=sys.stderr)
            return 2
    if a.cmd == "report":
        rows = read_rows(RESULTS)
        text = REPORT.read_text(encoding="utf-8")
        new = render(text, rows)
        misses = readme_misses(README.read_text(encoding="utf-8"), rows)
        if a.check:
            bad = new != text
            if bad:
                print(f"{REPORT.relative_to(HOME)}: a generated table differs from {RESULTS.relative_to(HOME)}; "
                      "python3 _tools/benchmarks.py report rewrites it")
            for m in misses:
                print(f"README.md: {m!r} matches no row of {RESULTS.relative_to(HOME)}")
            empty = empty_markers(text, rows)
            for m in empty:
                print(f"{REPORT.relative_to(HOME)}: {m}")
            return 1 if bad or misses or empty else 0
        REPORT.write_text(new, encoding="utf-8", newline="\n")
        for m in misses:
            print(f"README.md: {m!r} matches no row of {RESULTS.relative_to(HOME)}")
        return 0
    names = a.scenarios or list(SCENARIOS)
    unknown = [n for n in names if n not in SCENARIOS]
    if unknown:
        print(f"unknown scenario: {', '.join(unknown)} (benchmarks.py list)", file=sys.stderr)
        return 2
    if a.dry_run and (not a.scenarios or any(n not in PLANNED for n in a.scenarios)):
        # a scenario that never reads b.dry would start its paid runs
        unplanned = ", ".join(n for n in a.scenarios if n not in PLANNED)
        what = f"no plan for {unplanned}" if unplanned else "no scenario named, so every one would run"
        print(f"--dry-run: {what}; the scenarios that have one: {', '.join(PLANNED)}", file=sys.stderr)
        return 2
    if a.jobs < 1 or (a.max_usd is not None and a.max_usd <= 0):
        print("--jobs needs 1 or more, --max-usd more than 0", file=sys.stderr)
        return 2
    arms, efforts = (x.split(",") if x else None for x in (a.arms, a.effort))
    shapes = bench_pool.shapes_of(a.shape)
    kinds = a.kinds.split(",") if a.kinds else None
    arm_reps, bad_reps = bench_pool.parse_arm_map(a.arm_reps, "--arm-reps", bench_pool.reps_value)
    arm_kinds, bad_kinds = bench_pool.parse_arm_map(a.arm_kinds, "--arm-kinds", bench_pool.kinds_value)
    problems = [f"--shape: unknown {s} (one of {', '.join(bench_pool.SHAPES)}, or both, comma separated)"
                for s in shapes if s not in bench_pool.SHAPES] + bad_reps + bad_kinds
    for flag, got, known in (("--arms", arms, bench_pool.ARMS if "fresh" in shapes else bench_pool.SESSION_ARMS),
                             ("--effort", efforts, bench_pool.EFFORTS), ("--kinds", kinds, bench_pool.KINDS)):
        bad = [x for x in got or [] if x not in known]
        if bad:
            problems.append(f"{flag}: unknown {', '.join(bad)} (one of {', '.join(known)})")
    if a.sample is not None and a.sample < 1:
        problems.append("--sample needs 1 or more")
    if not problems:
        by_shape = bench_pool.arms_by_shape(arms, shapes)
        problems = (bench_pool.unrun_problems("--arm-reps", arm_reps, by_shape)
                    + bench_pool.unrun_problems("--arm-kinds", arm_kinds, by_shape))
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 2
    b = Bench(scratch_dir(), a.reps)
    b.arm = a.arm
    b.arms, b.efforts, b.dry, b.shape, b.seed = arms, efforts, a.dry_run, a.shape, a.seed
    b.jobs, b.max_usd, b.sample = a.jobs, a.max_usd, a.sample
    b.kinds, b.arm_reps, b.arm_kinds = kinds, arm_reps, arm_kinds
    out = Path(a.out) if a.out else RESULTS
    try:
        for n in names:
            arm = b.arm if n in ARMED else ""  # the arm of the rows the runner itself adds
            start = len(b.rows)
            t = time.time()
            RAW["path"] = b.scratch / "raw" / f"{n}-{b.date}-runs.jsonl"
            RAW["path"].parent.mkdir(parents=True, exist_ok=True)
            try:
                SCENARIOS[n][1](b)
            except Skip as e:  # nothing measured, so no row: an errors row would read as a failed run
                print(f"{n}: skipped: {e}", flush=True)
                continue
            except Exception as e:  # one failed scenario does not lose the others' rows
                b.row(n, "run", arm, "errors", 1, 1, note=f"{type(e).__name__}: {e}"[:200])
            if SPEND["runs"]:
                if n in SLOTTED and n not in ARMED:  # a same-day run of other arms keeps its own spend rows beside these
                    arm = "paid: " + ",".join(sorted({r["arm"] for r in b.rows[start:]}))
                b.row(n, "all paid runs", arm, "spend_usd", SPEND["usd"], SPEND["runs"])
                b.row(n, "all paid runs", arm, "spend_input_tokens", SPEND["input"], SPEND["runs"])
                b.row(n, "all paid runs", arm, "spend_output_tokens", SPEND["out"], SPEND["runs"])
            mine = b.rows[start:]
            print(f"{n}: {len(mine)} rows, ${SPEND['usd']:.2f} in {SPEND['runs']} paid runs, "
                  f"{time.time() - t:.0f} s", flush=True)
            SPEND.update(usd=0.0, input=0, out=0, runs=0)
            merged = merge_rows(read_rows(out), mine)
            if n == "pool":  # a same-day run of arm labels takes their runs out of an earlier spend row that counted them
                for record in dict.fromkeys(r["record"] for r in mine):
                    merged, lines = bench_pool.settle_spend(merged, record)
                    for line in lines:
                        print(f"{n}: {line}", flush=True)
            write_rows(merged, out)
    finally:
        b.close()
    return b.status


if __name__ == "__main__":
    sys.exit(main())
