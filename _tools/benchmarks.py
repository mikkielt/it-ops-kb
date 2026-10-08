#!/usr/bin/env python3
"""The kb's benchmarks: every measurement of kb/_self/reports/benchmarks.md, run again by one command (stdlib only).

  benchmarks.py list                        the scenarios, each with its report section
  benchmarks.py run [SCENARIO ...] [--reps N] [--arm ARM] [--out FILE] [--arms A,B] [--kinds K,K] [--effort L,L] [--dry-run]
                    [--shape fresh|session] [--seed N]
                                            run every scenario, or the named ones, and write their rows to the results
                                            file (kb/_self/reports/benchmarks.csv; rows of the same scenario and date
                                            are replaced), or to FILE; prints each scenario's rows and the spend;
                                            --arm names the arm of `navigation` (default `current`): a run replaces
                                            only its own arm's rows; `pool` runs the question pool (bench_pool.py)
                                            on the --arms (default all of bench_pool.ARMS), the --kinds (default all)
                                            and the --effort levels (default low,default) and replaces the rows of the
                                            arms it ran; --dry-run prints its plan and starts no model; --shape
                                            session runs the pool in groups of six questions, each group in one
                                            session (the kb arms haiku-5-5 and sonnet-5-5, seed --seed) and records
                                            per position the marginal input and the cache-read share
  benchmarks.py pool build [--querylog] [--seed N] [--out FILE]
                                            write the stratified question pool, with a check per row, to
                                            kb/public/_retrieval/bench_pool.csv, or with --querylog the redacted
                                            query-log questions to kb/_querylog/bench/pool.csv (bench_pool.py)
  benchmarks.py pool check [--querylog] [FILE]
                                            exit 1 on a pool row without a usable check, a held-out row with text, a
                                            leak or a kind off its count
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
import argparse, os, sys, tempfile, time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import bench_pool  # noqa: E402
from bench_core import (ARMED, HOME, RAW, RESULTS, SPEND, Bench, Skip, merge_rows, read_rows,  # noqa: E402
                        write_rows)
from bench_report import empty_markers, readme_misses, render  # noqa: E402
from bench_install import s_host_roots, s_ingest, s_kbpy, s_new_model  # noqa: E402
from bench_lookup import (s_always_on, s_files_headless, s_files_subagents, s_headless, s_host_lookups, s_howto,
                          s_kb_lookup_agent, s_models, s_navigation, s_partial, s_route_by_verdict, s_router,
                          s_subagents)  # noqa: E402
from bench_querylog import s_querylog_hooks, s_querylog_pipeline, s_redaction, s_research  # noqa: E402
from bench_retrieval import s_doc2query, s_retrieval, s_tool_speed, s_verdict  # noqa: E402

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


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    r = sub.add_parser("run")
    r.add_argument("scenarios", nargs="*")
    r.add_argument("--reps", type=int, default=1)
    r.add_argument("--arm", default="current", help="the arm of the navigation scenario's rows (default: current)")
    r.add_argument("--out")
    r.add_argument("--arms", help="the arms of `pool`, comma separated (default: " + ",".join(bench_pool.ARMS) + ")")
    r.add_argument("--kinds", help="the pool kinds `pool` runs, comma separated (default: all)")
    r.add_argument("--effort", help="the effort levels of the kb arms of `pool`, comma separated (default: "
                   + ",".join(bench_pool.EFFORTS) + ")")
    r.add_argument("--dry-run", action="store_true", help="print the plan of `pool` and start no model")
    r.add_argument("--shape", choices=bench_pool.SHAPES, default="fresh",
                   help="`pool`: a fresh session per question, or groups of six questions in one session (default: fresh)")
    r.add_argument("--seed", type=int, default=bench_pool.SEED, help="the seed that orders the groups of `pool --shape session`")
    pool = sub.add_parser("pool").add_subparsers(dest="pool_cmd", required=True)
    pb = pool.add_parser("build")
    pb.add_argument("--querylog", action="store_true")
    pb.add_argument("--seed", type=int, default=bench_pool.SEED)
    pb.add_argument("--out")
    pc = pool.add_parser("check")
    pc.add_argument("--querylog", action="store_true")
    pc.add_argument("file", nargs="?")
    rep = sub.add_parser("report")
    rep.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "list":
        for name, (section, _) in SCENARIOS.items():
            print(f"{name:18} {section}")
        return 0
    if a.cmd == "pool":
        return bench_pool.cli(a)
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
    arms, efforts = (x.split(",") if x else None for x in (a.arms, a.effort))
    for flag, got, known in (("--arms", arms, bench_pool.SESSION_ARMS if a.shape == "session" else bench_pool.ARMS),
                             ("--effort", efforts, bench_pool.EFFORTS)):
        bad = [x for x in got or [] if x not in known]
        if bad:
            print(f"{flag}: unknown {', '.join(bad)} (one of {', '.join(known)})", file=sys.stderr)
            return 2
    b = Bench(os.environ.get("BENCH_SCRATCH") or Path(tempfile.gettempdir()) / "it-ops-kb-bench", a.reps)
    b.arm = a.arm
    b.arms, b.efforts, b.dry, b.shape, b.seed = arms, efforts, a.dry_run, a.shape, a.seed
    b.kinds = a.kinds.split(",") if a.kinds else None
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
                b.row(n, "all paid runs", arm, "spend_usd", SPEND["usd"], SPEND["runs"])
                b.row(n, "all paid runs", arm, "spend_input_tokens", SPEND["input"], SPEND["runs"])
                b.row(n, "all paid runs", arm, "spend_output_tokens", SPEND["out"], SPEND["runs"])
            mine = b.rows[start:]
            print(f"{n}: {len(mine)} rows, ${SPEND['usd']:.2f} in {SPEND['runs']} paid runs, "
                  f"{time.time() - t:.0f} s", flush=True)
            SPEND.update(usd=0.0, input=0, out=0, runs=0)
            write_rows(merge_rows(read_rows(out), mine), out)
    finally:
        b.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
