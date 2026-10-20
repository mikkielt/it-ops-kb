"""kbmon's bench panel (kb/_self/monitoring.md): a paid multi-agent benchmark run's progress, its spend against the cap and
the disk its agents' sandboxes hold.

The data is read from `_cache/bench-multi` of the main worktree of the clone `--root` names (`bl_base.main_worktree`), where
`benchmarks.py multi run` keeps its run: `progress.json` (the plan, the pid and the times of the run) and `results.jsonl`
(a line for each finished agent and arm, from which `done` and `spend_usd` are counted as `bench_multi.progress` counts them).
The keys: `planned` and `done` (runs for each arm, `kb` and `bare`), `spend_usd`, `max_usd` (None without a cap), `pid`, `running`
(whether the pid is a live process: None where the host cannot tell, and False once the run has an `ended` time), `started`,
`ended`, `updated`, `sandbox_bytes` (the agents' clones and scratch directories and the bare twins' sandboxes, walked for
`SECONDS` at most) and `approximate` (the walk was cut). No path is in the data or the text. A clone with no `progress.json`
has no run: the panel is `absent`.

The panel reads and writes nothing. Imports `mon_base`; `bl_base`, `bl_clean`, `bench_repro` and `bench_multi` where it reads.
"""
import json
import os
from pathlib import Path

import mon_base

REFRESH_S = 30  # seconds the live view serves the last result: a run moves by the minute, and the walk of the sandboxes is slow
SECONDS = 4  # the longest the walks of the sandboxes take together, so the panel stays inside its timeout


def pid_running(pid):
    """Whether PID is a live process; None where this host cannot tell (not POSIX: `os.kill` would end the process there)."""
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0 or os.name != "posix":
        return None
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def read_progress(run):
    try:
        doc = json.loads((run / "progress.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def sandbox_bytes(run):
    """(bytes under the agents' sandbox directories of the run in RUN, whether the walk was cut): the directory that holds the clones
    and scratch directories of the run, and its bare twins' sandboxes."""
    import bench_multi
    import bl_clean
    total, approximate = 0, False
    for where in (bench_multi.clone_path(run, 1).parent, run / bench_multi.BARE):
        size, cut = bl_clean.tree_bytes(where, SECONDS / 2)
        total += size
        approximate = approximate or cut
    return total, approximate


def count(doc, key):
    """The runs for each arm that DOC[KEY] holds, 0 for an arm it lacks or holds not as a whole number."""
    value = doc.get(key) if isinstance(doc.get(key), dict) else {}
    return {arm: value[arm] if isinstance(value.get(arm), int) and not isinstance(value[arm], bool) else 0 for arm in ("kb", "bare")}


def collect(ctx):
    import bench_multi
    import bench_repro
    import bl_base
    run = Path(bl_base.main_worktree(ctx.root)) / "_cache" / "bench-multi"
    doc = read_progress(run)
    if doc is None:
        raise mon_base.Absent("no paid benchmark run")
    planned, done = count(doc, "planned"), count(doc, "done")
    max_usd, spend = doc.get("max_usd"), doc.get("spend_usd")
    lines = bench_repro.read_results(run / bench_multi.RUN_RESULTS)
    if lines:  # the result lines are the newer record: the file is written when a run ends, the lines as each agent finishes
        found = bench_multi.progress({"agents": range(planned["kb"])}, lines, planned["bare"] > 0, max_usd)
        done, spend = found["done"], found["spend_usd"]
    size, approximate = sandbox_bytes(run)
    ended = doc.get("ended") or ""
    return {"planned": planned, "done": done, "spend_usd": spend if isinstance(spend, (int, float)) else 0,
            "max_usd": max_usd if isinstance(max_usd, (int, float)) and not isinstance(max_usd, bool) else None,
            "pid": doc.get("pid"), "running": False if ended else pid_running(doc.get("pid")),
            "started": doc.get("started") or "", "ended": ended, "updated": doc.get("updated") or "",
            "sandbox_bytes": size, "approximate": approximate}


def lines(data):
    """The body rows: the pid and the times, the runs done of the planned for each arm, the spend against the cap, the sandboxes' disk."""
    import bl_clean
    state = {True: "running", False: "not running", None: "state unknown"}[data.get("running")]
    when = f", ended {data['ended']}" if data.get("ended") else f", started {data['started']}" if data.get("started") else ""
    arms = "  ".join(f"{arm} {data['done'].get(arm, 0)}/{n}" for arm, n in data.get("planned", {}).items() if n)
    cap = data.get("max_usd")
    spend = data.get("spend_usd") or 0
    money = f"${spend:.2f} of ${cap:.2f} ({spend / cap:.0%})" if cap else f"${spend:.2f}, no cap"
    size = bl_clean.fmt_size(data.get("sandbox_bytes", 0)) + (" or more" if data.get("approximate") else "")
    return [f"pid {data.get('pid')} {state}{when}", f"runs {arms or '-'}  (done/planned)", f"spend {money}", f"sandbox disk {size}"]
