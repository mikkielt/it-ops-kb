"""The research-reproducibility benchmark's isolated instances: `benchmarks.py repro setup`, `repro check`, `repro
questions`, `repro run`, `repro record`, `repro compare`, `repro status`, `repro pick` and `repro replay` (stdlib only).

Each instance is a full bare copy of one pinned commit's history (DIR/originN.git, its main at REV), a working clone of
it outside the checkout (under bench_core's scratch directory) whose only remote is that bare path, a query log of mode
`off` in the clone, and an mcp-config file of its own for `claude -p --mcp-config FILE --strict-mcp-config`, so no
instance writes ~/.claude.json. `instance_env` is the session environment of an instance. `check` builds one such
instance as a probe, runs `kbgit.py sync --push` in it and proves the push landed on the probe's own bare and nowhere
else. `load_briefs` and `brief_problems` read and check the briefs file, `question_problems` the frozen questions
against it, and `status` names each instance's commits since the start commit and the ones a fresh fetch of the real
origin's main holds. `run` starts every instance's headless `/kb-research` sessions at once, one per area, each instance in
its own rotation of the briefs' order (`area_order`) and an area only while `may_start` holds, and appends each area's result as a json line to DIR/results.jsonl (`session_argv` is the one argv,
`area_prompt` the one prompt). `claude_path` names the command it starts and refuses a wrapper script; a run also refuses
while the briefs or questions file differs from HEAD and records their sha256 in DIR/run.json. `record_results` merges those json lines into the results file as the scenario `repro`.
`compare` puts a detached checkout of each instance's bare at the shas of every area and reads it with that checkout's own
tools by subprocess (`state_of`, `error_counts`, `eval_rows`); `match_facts` and `overlap_and_conflicts` hold the
comparison of two instances' added facts and `compare_rows` the rows of the scenario `repro-compare`. `pick` applies the
landing rule to those rows and the `repro` cost rows (`standings`, `pick_key`); `replay` rebases one instance's commits
since the start commit onto the current branch from its bare by path, a `KB-Work` trailer on each, and neither touches
the real origin. This module imports bench_core and kbpublic, factdiff and ql_research where `compare` reads text, and kbfacts where it reads the routing and
the clone home (kb/_self/code.md, Layout); benchmarks.py holds the command line.
"""
import csv, datetime, hashlib, json, os, re, shlex, shutil, subprocess, sys, tempfile, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import agent_bench
import kbpublic
from bench_core import FIELDS, HOME, RESULTS as BENCH_RESULTS, isolate, merge_rows, no_plugin_env, read_rows, scratch_dir, \
    stream_run, write_rows

ADDED = "kb/public/_retrieval/repro_bench.csv"  # the file whose first commit's parent is the default REV
BRIEFS = "kb/public/_retrieval/repro_briefs.csv"  # one research brief per benchmark area
BRIEF_COLUMNS = ("area", "scope", "sources", "depth", "coverage", "leave_out")
BRIEF_FILLED = BRIEF_COLUMNS[:5]  # the cells a brief must fill: leave_out may be empty
COVERAGES = ("present", "partial", "absent")
QUESTIONS_PER_AREA = (3, 5)  # the frozen questions of one area, fewest and most
EXPECT_COLUMNS = ("expect_re", "expect_text", "expect_paths")  # a question row holds at least one
DOCS_MCP = Path(".claude-plugin") / "it-ops-kb-docs" / ".mcp.json"
MANIFEST = "instances.json"
RESULTS = "results.jsonl"  # DIR/results.jsonl: one json line per area result of a run
RUN_RECORD = "run.json"  # DIR/run.json: the argv, settings and limits the results of DIR were taken with
CLAUDE = ["claude"]  # the command a session starts with (a list: a test plants its own)
# What every session's --settings holds: the gitkraken plugin and the user's caveman plugin off.
SETTINGS = json.dumps({"enabledPlugins": {"gitkraken@synced": False, "caveman@caveman": False}}, separators=(",", ":"))
EFFORTS = ("low", "medium", "high", "xhigh", "max")
DEFAULTS = {"model": "sonnet-5-5", "effort": "high", "max_turns": 150, "area_usd": 8.0, "instance_usd": 40.0,
            "timeout": 3600}  # the limits of `run`: the seconds are one area's session
NO_ROWS = ("kb/public/_retrieval/lookup_eval.csv", "kb/public/_retrieval/lookup_heldout.csv",
           "kb/public/_retrieval/doc2query/")  # what a research session adds no row to
NO_READ = ("kb/_self/backlog/", "kb/_self/reports/")  # what it reads nothing under
CLAIMS_LEDGER = "kb-backlog-claims.json"  # bl_base.CLAIMS_LEDGER: the file in a clone's git dir that holds its claims
# The variables an instance's session must not inherit: the same names as conftest.LEAKY (test_bench.py compares them;
# a tool module never imports conftest, which clears them from os.environ when it is imported).
LEAKY_ENV = ("KB_VERIFIED", "KB_TESTS_FAST", "KB_SYNC_NO_TESTS", "KB_GATE_DONE", "KB_SESSION", "KB_MAIN_LOCK_HELD",
             "CI_COMMIT_SHA", "CI_COMMIT_BEFORE_SHA", "CLAUDE_CODE_REMOTE_SESSION_ID", "CLAUDE_CODE_BRIDGE_SESSION_ID",
             kbpublic.NO_HOOK_ENV, "GIT_DIR", "GIT_WORK_TREE", "GIT_IMPLICIT_WORK_TREE", "GIT_INDEX_FILE",
             "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_GRAFT_FILE",
             "GIT_SHALLOW_FILE", "GIT_REPLACE_REF_BASE", "GIT_NO_REPLACE_OBJECTS", "GIT_PREFIX", "GIT_NAMESPACE",
             "KB_ROOTS")
KEEP_IGNORED = ("_cache/kbindex-*", "_cache/kbunits*", "_private/querylog.json", "_private/mcp-config.json")  # what
# reset_clone leaves of a clone's ignored files: its pack index cache and the two files setup wrote in _private


class Refused(Exception):
    """Setup cannot do what was asked (a bad revision, a fetch that fails); the command exits 2."""


def default_dir():
    """_cache/bench-repro of the clone's main worktree, so a run from a linked worktree leaves it where later items find it."""
    import kbfacts
    return Path(kbfacts.clone_home()) / "_cache" / "bench-repro"


def origin_path(root, n):
    return Path(root) / f"origin{n}.git"


def clone_path(root, n):
    """The working clone of instance N: under the scratch directory, in a directory of its own for each DIR. The scratch
    directory is resolved (a temp directory can be a symlink, as /var is on macOS), so the clone's tools and its tests,
    which see the resolved path, agree on where the clone is."""
    return scratch_dir().resolve() / ("repro-" + hashlib.sha1(str(Path(root).resolve()).encode("utf-8")).hexdigest()[:8]) / f"instance{n}"


def mcp_path(root, n):
    return clone_path(root, n) / "_private" / "mcp-config.json"


def lock_dir(root, n):
    return Path(root) / f"lock{n}"


def run_git(*args, cwd):
    p = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8")
    if p.returncode:
        raise Refused(f"git {' '.join(args[:2])} failed: {(p.stderr or p.stdout).strip()[-300:]}")
    return p.stdout.strip()


def remote_url():
    """(remote name, url) of this clone's integration remote."""
    name = kbpublic.integration_remote(HOME)
    return name, run_git("config", "--get", f"remote.{name}.url", cwd=HOME)


def instance_env(root, n):
    """The session environment of instance N: bench_core.no_plugin_env's without the variables of LEAKY_ENV, with
    KB_SESSION empty, KB_DOCS_CACHE unset, ENABLE_CLAUDEAI_MCP_SERVERS=false, CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 (a
    session reads no memory an earlier area wrote; the --settings value stays SETTINGS) and KB_HOST_LOCK_DIR under
    DIR. KB_ROOTS, the one variable kbcommon reads to find roots outside the clone, is in LEAKY_ENV."""
    env = no_plugin_env()
    for k in LEAKY_ENV:
        env.pop(k, None)
    env.pop("KB_DOCS_CACHE", None)
    env.update({"KB_SESSION": "", "ENABLE_CLAUDEAI_MCP_SERVERS": "false", "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
                "KB_HOST_LOCK_DIR": str(lock_dir(root, n))})
    return env


def mcp_config(clone):
    """The --mcp-config JSON of a clone: its own kb server and the docs servers of the docs plugin's .mcp.json."""
    docs = json.loads((HOME / DOCS_MCP).read_text(encoding="utf-8"))["mcpServers"]
    kb = {"command": sys.executable, "args": [str(Path(clone) / "_tools" / "kb_mcp.py")]}
    return {"mcpServers": {"kb": kb, **docs}}


def instance_lines(count, root):
    out = []
    for n in range(1, count + 1):
        out += [f"instance {n}: bare {origin_path(root, n)}", f"  clone {clone_path(root, n)}",
                f"  mcp-config {mcp_path(root, n)} (use with --strict-mcp-config)",
                f"  KB_HOST_LOCK_DIR {lock_dir(root, n)}"]
    return out


def plan_lines(count, root, start, url):
    rev = start or f"the parent of the first commit that adds {ADDED}, else the fetched main tip"
    return [f"repro setup: {count} instance(s)", f"dir: {root}",
            f"source: {url} (fetched into {Path(root) / 'seed.git'}, deleted once REV is pushed into each bare)",
            f"rev: {rev}", *instance_lines(count, root)]


def pinned_rev(seed, start):
    """(sha, why): START resolved in the seed, else the parent of the first commit that added ADDED, else main's tip."""
    if start:
        p = subprocess.run(["git", "rev-parse", "--verify", "-q", f"{start}^{{commit}}"], cwd=str(seed),
                           capture_output=True, text=True, encoding="utf-8")
        if p.returncode:
            raise Refused(f"--start {start}: no such commit in the history of the integration main")
        return p.stdout.strip(), f"--start {start}"
    added = run_git("log", "--diff-filter=A", "--format=%H", "refs/heads/main", "--", ADDED, cwd=seed).split()
    if added:
        first = added[-1]  # the oldest commit that added it
        parents = run_git("rev-list", "--parents", "-n", "1", first, cwd=seed).split()[1:]
        if parents:
            return parents[0], f"the parent of {first[:12]}, the first commit that added {ADDED}"
    return run_git("rev-parse", "refs/heads/main", cwd=seed), f"the fetched main tip: no commit adds {ADDED}"


def setup(count, start=None, root=None, dry_run=False, out=print):
    """Build `count` instances; print the plan and every path. Returns 0, or raises Refused."""
    root = Path(root) if root else default_dir()
    _, url = remote_url()
    if dry_run:
        for ln in plan_lines(count, root, start, url):
            out(ln)
        return 0
    root.mkdir(parents=True, exist_ok=True)
    seed = root / "seed.git"
    shutil.rmtree(seed, ignore_errors=True)
    try:
        run_git("init", "-q", "--bare", "--initial-branch=main", str(seed), cwd=root)
        run_git("fetch", "-q", "--no-tags", url, "+refs/heads/main:refs/heads/main", cwd=seed)
        sha, why = pinned_rev(seed, start)
        for n in range(1, count + 1):
            bare, clone = origin_path(root, n), clone_path(root, n)
            for d in (bare, clone):
                shutil.rmtree(d, ignore_errors=True)
            run_git("init", "-q", "--bare", "--initial-branch=main", str(bare), cwd=root)
            run_git("push", "-q", str(bare), f"{sha}:refs/heads/main", cwd=seed)
            clone.parent.mkdir(parents=True, exist_ok=True)
            run_git("clone", "-q", str(bare), str(clone), cwd=clone.parent)
            isolate(clone, "off", bare)
            mcp_path(root, n).write_text(json.dumps(mcp_config(clone), indent=2) + "\n", encoding="utf-8", newline="\n")
            lock_dir(root, n).mkdir(parents=True, exist_ok=True)
    finally:
        shutil.rmtree(seed, ignore_errors=True)
    manifest = {"rev": sha, "source": url, "instances": [
        {"n": n, "bare": str(origin_path(root, n)), "clone": str(clone_path(root, n)), "mcp_config": str(mcp_path(root, n)),
         "lock_dir": str(lock_dir(root, n))} for n in range(1, count + 1)]}
    (root / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    out(f"rev: {sha} ({why})")
    out(f"dir: {root}")
    for ln in instance_lines(count, root):
        out(ln)
    out(f"manifest: {root / MANIFEST}")
    return 0


def sh(args, cwd, env):
    return subprocess.run(args, cwd=str(cwd), env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")


def same_path(a, b):
    return Path(a).resolve() == Path(b).resolve()


def inside(path, parent):
    return Path(path).resolve().is_relative_to(Path(parent).resolve())


def fetch_real(url, work):
    """A fresh bare under `work` holding main of `url`: the path of that bare."""
    real = Path(work) / "real.git"
    run_git("init", "-q", "--bare", "--initial-branch=main", str(real), cwd=work)
    run_git("fetch", "-q", "--no-tags", url, "+refs/heads/main:refs/heads/main", cwd=real)
    return real


def in_main(sha, real):
    """True when commit `sha` is in the main of the bare `real`."""
    if subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=str(real), capture_output=True).returncode:
        return False  # the object is not even there
    return subprocess.run(["git", "merge-base", "--is-ancestor", sha, "refs/heads/main"], cwd=str(real),
                          capture_output=True).returncode == 0


def reaches(sha, url, work):
    """True when commit `sha` is in a fresh fetch of main from `url` (into a new bare under `work`)."""
    return in_main(sha, fetch_real(url, work))


def probe_checks(root, url, out):
    """Run the probe's sync in instance 1 of `root`; the (name, ok, detail) of each property the check proves."""
    clone, bare, env = clone_path(root, 1), origin_path(root, 1), instance_env(root, 1)
    if os.environ.get("KB_SYNC_NO_TESTS"):  # the tool's own tests skip the gate's test run, as test_sync_e2e.py does
        env["KB_SYNC_NO_TESTS"] = os.environ["KB_SYNC_NO_TESTS"]
    before = run_git("rev-parse", "refs/heads/main", cwd=bare)
    p = sh([sys.executable, str(clone / "_tools" / "kbgit.py"), "install-hooks"], clone, env)
    if p.returncode:
        raise Refused(f"the probe's install-hooks exited {p.returncode}: {(p.stdout + p.stderr).strip()[-300:]}")
    topic = next(f"{a.parent.name}/{a.stem}" for a in sorted((clone / "kb" / "public").glob("*/*.md"))
                 if not a.name.startswith("_"))  # a gap names a topic the root has
    with open(clone / "kb" / "public" / "_gaps.md", "a", encoding="utf-8", newline="\n") as f:
        f.write("\n## repro-check-probe\n\n- **A probe entry that repro check commits and syncs.** Nothing was tried; the "
                f"entry exists to be pushed to the probe's own bare. [UNK] (topic: {topic})\n")
    run_git("add", "kb/public/_gaps.md", cwd=clone)
    p = sh(["git", "commit", "-q", "-m", "docs(kb): repro check probe gap"], clone, env)
    if p.returncode:
        raise Refused(f"the probe's commit exited {p.returncode}: {(p.stdout + p.stderr).strip()[-300:]}")
    sha = run_git("rev-parse", "HEAD", cwd=clone)
    p = sh([sys.executable, str(clone / "_tools" / "kbgit.py"), "sync", "--push"], clone, env)
    lines = (p.stdout + p.stderr).strip().splitlines()
    res = [("sync --push exits 0", p.returncode == 0, f"exit {p.returncode}")]
    if p.returncode:
        for ln in lines[-15:]:
            out(f"  sync: {ln}")
    moved = run_git("rev-parse", "refs/heads/main", cwd=bare)
    res.append(("the probe's bare main moved to the probe's commit", moved == sha != before,
                f"main {before[:12]} -> {moved[:12]}, commit {sha[:12]}"))
    remote = run_git("config", "--get", "remote.origin.url", cwd=clone)
    res.append(("the probe's only remote is its own bare", same_path(remote, bare) and not same_path(remote, url),
                f"origin is {remote}"))
    with tempfile.TemporaryDirectory(dir=str(root)) as work:
        res.append(("the commit is not in a fresh fetch of the real origin's main", not reaches(sha, url, work), url))
    cfg = json.loads(mcp_path(root, 1).read_text(encoding="utf-8"))["mcpServers"]["kb"]
    script = str(clone / "_tools" / "kb_mcp.py")
    res.append(("the mcp-config names the probe's kb_mcp.py", cfg["args"] == [script], f"args {cfg['args']}"))
    st = sh([cfg["command"], *cfg["args"], "--status"], clone, env)
    kb_dir = next((ln.split(":", 1)[1].strip() for ln in st.stdout.splitlines() if ln.startswith("kb_dir:")), "")
    res.append(("kb_mcp.py --status prints the probe's kb_dir", bool(kb_dir) and same_path(kb_dir, clone / "kb"),
                f"kb_dir {kb_dir or '(none)'}"))
    mode = json.loads((clone / "_private" / "querylog.json").read_text(encoding="utf-8")).get("mode")
    res.append(("the probe's query log mode is off", mode == "off", f"mode {mode}"))
    git_dir = run_git("rev-parse", "--absolute-git-dir", cwd=clone)
    ledger = Path(git_dir) / CLAIMS_LEDGER
    mine = run_git("rev-parse", "--absolute-git-dir", cwd=HOME)
    res.append(("the claims ledger is the probe's own", inside(ledger, clone) and not same_path(git_dir, mine), str(ledger)))
    c = sh([sys.executable, "-I", "-c", "import sys; sys.path.insert(0, sys.argv[1]); import kbfacts; "
            "print(kbfacts.index_dir())", str(clone / "_tools")], clone, env)
    cache = c.stdout.strip()
    res.append(("_cache is the probe's own", bool(cache) and inside(cache, clone) and not inside(cache, HOME),
                f"index dir {cache or '(none)'}"))
    for name, ok, detail in res:
        out(f"{'ok' if ok else 'FAIL'}: {name} ({detail})")
    return [name for name, ok, _ in res if not ok]


def check(out=print):
    """Build a probe instance as `setup` does, commit one _gaps.md entry in it, run `kbgit.py sync --push` there and prove
    the push stayed inside the probe (probe_checks); remove the probe. Returns 0 when every property holds, 1 when one
    fails, or raises Refused."""
    _, url = remote_url()
    root = scratch_dir().resolve() / f"repro-check-{os.getpid()}"
    try:
        setup(1, root=root, out=lambda line: None)
        failed = probe_checks(root, url, out)
    finally:
        shutil.rmtree(clone_path(root, 1).parent, ignore_errors=True)
        shutil.rmtree(root, ignore_errors=True)
    out("repro check: " + ("the probe's push stayed on its own bare" if not failed else f"{len(failed)} failed: " + "; ".join(failed)))
    return 1 if failed else 0


def read_csv(path):
    """The rows of a csv file as dicts of strings (a missing cell is ""), or [] when the file does not exist."""
    if not Path(path).exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return [{k: v or "" for k, v in r.items() if k is not None} for r in csv.DictReader(f)]


def load_briefs(path=None):
    """The rows of kb/public/_retrieval/repro_briefs.csv (or of the csv at `path`) as dicts of the BRIEF_COLUMNS, in file
    order; [] when the file does not exist."""
    rows = read_csv(path or HOME / BRIEFS)
    return [{c: r.get(c, "") for c in BRIEF_COLUMNS} for r in rows]


def brief_problems(rows):
    """One line per defect of the brief rows: an empty area, scope, sources, depth or coverage cell, a coverage that is
    none of COVERAGES, a duplicate area."""
    out, seen = [], {}
    for n, r in enumerate(rows, 1):
        area = (r.get("area") or "").strip()
        label = f"row {n} ({area})" if area else f"row {n}"
        for c in BRIEF_FILLED:
            if not (r.get(c) or "").strip():
                out.append(f"{label}: empty {c}")
        cov = (r.get("coverage") or "").strip()
        if cov and cov not in COVERAGES:
            out.append(f"{label}: coverage {cov!r} is none of {', '.join(COVERAGES)}")
        if area and area in seen:
            out.append(f"{label}: duplicate area, as row {seen[area]}")
        seen.setdefault(area, n)
    return out


def load_questions(path=None):
    """The rows of kb/public/_retrieval/repro_bench.csv (or of the csv at `path`), as dicts of its columns; [] when the
    file does not exist."""
    return read_csv(path or HOME / ADDED)


def routing_of(question):
    """The kinds of the experts that answer `question` as a tool decides it (kbfacts.routed), or [] when none does."""
    import kbfacts
    res = kbfacts.routed(question)
    return list(res["routed"]["kinds"]) if res else []


def question_problems(briefs, questions, routing=routing_of):
    """One line per defect of the frozen questions against the briefs: an area without 3 to 5 rows, a row of an area no
    brief names, a duplicate id, a row with none of EXPECT_COLUMNS filled, a question that `routing` returns kinds for
    (a tool answers it, so it measures no research)."""
    lo, hi = QUESTIONS_PER_AREA
    out, count, ids = [], {}, {}
    for n, q in enumerate(questions, 1):
        qid = (q.get("id") or "").strip()
        label = f"question {qid}" if qid else f"question row {n}"
        area = (q.get("area") or "").strip()
        count[area] = count.get(area, 0) + 1
        if qid and qid in ids:
            out.append(f"{label}: duplicate id, as row {ids[qid]}")
        ids.setdefault(qid, n)
        if not any((q.get(c) or "").strip() for c in EXPECT_COLUMNS):
            out.append(f"{label}: none of {', '.join(EXPECT_COLUMNS)} is filled")
        text = (q.get("question") or "").strip()
        kinds = routing(text) if text else []
        if kinds:
            out.append(f"{label}: routed by kind to a tool ({', '.join(kinds)}): {text[:80]}")
    areas = [b["area"].strip() for b in briefs if (b.get("area") or "").strip()]
    for area in dict.fromkeys(areas):
        if not lo <= count.get(area, 0) <= hi:
            out.append(f"area {area}: {count.get(area, 0)} question rows, {lo} to {hi} wanted")
    for area in count:
        if area not in areas:
            out.append(f"area {area or '(empty)'}: {count[area]} question row(s) of no brief's area")
    return out


def questions(briefs_path=None, questions_path=None, out=print):
    """Check the frozen questions against the briefs; print each problem. Returns 0 when there is none, else 1."""
    briefs = load_briefs(briefs_path)
    problems = question_problems(briefs, load_questions(questions_path)) if briefs else \
        [f"no brief rows: {briefs_path or HOME / BRIEFS} is missing or empty"]
    for ln in problems:
        out(f"FAIL: {ln}")
    out("repro questions: " + (f"{len(problems)} problem(s)" if problems else
                                f"every one of {len(briefs)} areas holds {QUESTIONS_PER_AREA[0]} to "
                                f"{QUESTIONS_PER_AREA[1]} questions, each with an expectation and none routed to a tool"))
    return 1 if problems else 0


def commits_since(bare, rev):
    """[(sha, subject)] of the commits on `bare`'s main since `rev`, newest first."""
    log = run_git("log", "--format=%H %s", f"{rev}..refs/heads/main", cwd=bare)
    return [tuple(ln.split(" ", 1)) for ln in log.splitlines()]


def status(root=None, out=print):
    """Print, per instance of DIR's manifest, the commits on its bare since the start commit and whether each is in a
    fresh fetch of the real origin's main. Returns 1 when any is, else 0; raises Refused on a bare that is gone."""
    root = Path(root) if root else default_dir()
    manifest = root / MANIFEST
    if not manifest.exists():
        out(f"repro status: {root} holds no {MANIFEST}: no instance was set up there, so no instance commit exists")
        return 0
    data = json.loads(manifest.read_text(encoding="utf-8"))
    rev = data["rev"]
    found = []
    for inst in data["instances"]:
        bare = Path(inst["bare"])
        if not bare.is_dir():
            raise Refused(f"instance {inst['n']}: its bare {bare} is gone")
        found.append((inst["n"], bare, commits_since(bare, rev)))
    real, reached = None, 0
    with tempfile.TemporaryDirectory(dir=str(root)) as work:
        if any(c for _, _, c in found):
            real = fetch_real(remote_url()[1], work)
        out(f"repro status: start {rev[:12]}, dir {root}")
        for n, bare, commits in found:
            out(f"instance {n}: {len(commits)} commit(s) on {bare} since {rev[:12]}")
            for sha, subject in commits:
                hit = in_main(sha, real)
                reached += hit
                out(f"  {sha[:12]} {subject} ({'IN the real origin main' if hit else 'not in the real origin main'})")
    out("repro status: " + (f"{reached} instance commit(s) are in a fresh fetch of the real origin's main" if reached else
                            "no instance commit is in a fresh fetch of the real origin's main"))
    return 1 if reached else 0


def sh_git(clone, env, *args):
    """git `args` in `clone` under the session environment `env`: stdout, or Refused with what git said."""
    p = sh(["git", *args], clone, env)
    if p.returncode:
        raise Refused(f"git {' '.join(args[:2])} failed in {clone}: {(p.stderr or p.stdout).strip()[-300:]}")
    return p.stdout.strip()


def reset_clone(clone, env):
    """Put `clone` on its bare's main as a fresh start: a rebase a session left is aborted (none in progress is no
    error), origin's main fetched, the work tree reset to it, the git worktrees registered under _cache removed and
    what a session left untracked or ignored removed (_cache and _private among them), except KEEP_IGNORED: the
    clone's pack index cache and the query log mode and mcp-config files setup wrote."""
    sh(["git", "rebase", "--abort"], clone, env)
    sh_git(clone, env, "fetch", "-q", "origin", "+refs/heads/main:refs/remotes/origin/main")
    sh_git(clone, env, "checkout", "-q", "-f", "main")
    sh_git(clone, env, "reset", "-q", "--hard", "refs/remotes/origin/main")
    cache = (Path(clone) / "_cache").resolve()
    for line in sh_git(clone, env, "worktree", "list", "--porcelain").splitlines():
        wt = Path(line[len("worktree "):]) if line.startswith("worktree ") else None
        if wt and cache in wt.resolve().parents:
            sh_git(clone, env, "worktree", "remove", "--force", "--force", str(wt))
    sh_git(clone, env, "worktree", "prune")
    sh_git(clone, env, "clean", "-q", "-f", "-f", "-d", "-x", *(f"--exclude={p}" for p in KEEP_IGNORED))


def area_prompt(brief):
    """The prompt of one area's session, built from its brief row alone: the same text for every instance."""
    area = brief["area"].strip()
    lines = [f"/kb-research {area}: {brief['scope'].strip()}", "", f"The research brief of the area `{area}`:",
             f"- Scope: {brief['scope'].strip()}", f"- Sources: {brief['sources'].strip()}",
             f"- Depth: {brief['depth'].strip()}", f"- Coverage of the kb today: {brief['coverage'].strip()}"]
    if brief.get("leave_out", "").strip():
        lines.append(f"- Leave out: {brief['leave_out'].strip()}")
    lines += ["", "Run /kb-research on this brief and finish it: nobody answers questions in this session.", "",
              "Rules of this session:",
              "- Push what you wrote with `python3 _tools/kbgit.py sync --push` when the research is done.",
              f"- Add no row to {', '.join(f'`{p}`' for p in NO_ROWS[:2])}, and no doc2query row under `{NO_ROWS[2]}`.",
              f"- Read nothing under {' or '.join(f'`{p}`' for p in NO_READ)}, and nothing outside this clone."]
    return "\n".join(lines) + "\n"


def model_id(model):
    """`model` as the full model id a session is started with: an agent_bench alias, else the name itself."""
    return agent_bench.MODEL.get(model, model)


def session_argv(model, effort, max_turns, area_usd, mcp_config):
    """The argv of one area's session, the same for every instance but its own --mcp-config file; the prompt is its stdin."""
    return [*CLAUDE, "-p", "--output-format", "stream-json", "--verbose", "--permission-mode", "bypassPermissions",
            "--settings", SETTINGS, "--mcp-config", str(mcp_config), "--strict-mcp-config", "--model", model_id(model),
            "--effort", effort, "--max-turns", str(max_turns), "--max-budget-usd", f"{area_usd:g}"]


def failure_of(r):
    """The failure a session's result names: timeout, turns, budget or error; "" for a finished session."""
    if "error" not in r:
        return ""
    sub = r.get("subtype", "")
    return {"timeout": "timeout"}.get(r["error"]) or {"error_max_turns": "turns", "error_max_budget_usd": "budget"}.get(sub, "error")


def read_results(path):
    """The json lines of the results file, in order ([] when there is none); a line that is not json is skipped."""
    out = []
    if Path(path).exists():
        for ln in Path(path).read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(ln)
            except ValueError:
                continue
            if isinstance(rec, dict):
                out.append(rec)
    return out


def latest(results):
    """{(instance, area): the newest result line of that area}."""
    return {(r.get("instance"), r.get("area")): r for r in results}


def instances_of(root, count):
    """(instances, rev): the manifest's first `count` instances (all when `count` is None) and its start commit, or, with
    no manifest, the paths `setup` would give `count or 1` instances and rev ""."""
    manifest = Path(root) / MANIFEST
    if manifest.exists():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        return data["instances"][:count] if count else data["instances"], data.get("rev", "")
    return [{"n": n, "bare": str(origin_path(root, n)), "clone": str(clone_path(root, n)),
             "mcp_config": str(mcp_path(root, n)), "lock_dir": str(lock_dir(root, n))}
            for n in range(1, (count or 1) + 1)], ""


def claude_path():
    """(path, problem): the resolved path of the command the instances start (CLAUDE[0] on PATH) and "" when it is the
    claude binary, else a text naming why not: it is not on PATH, or it is a script (a `#!` file), as a wrapper first on
    PATH is, which can add `--settings` the run does not record. An npm install's `.js` entry point is a script that is
    claude itself."""
    found = shutil.which(CLAUDE[0])
    if not found:
        return "", f"{CLAUDE[0]} is not on PATH"
    real = os.path.realpath(found)
    try:
        with open(real, "rb") as f:
            head = f.read(2)
    except OSError as e:
        return real, f"{real} cannot be read: {e}"
    if head == b"#!" and not real.endswith((".js", ".mjs", ".cjs")):
        return real, (f"{real} is a script, not the claude binary: a wrapper first on PATH can add --settings the run does "
                      f"not record (start it with the claude binary's directory first on PATH)")
    return real, ""


def run_problems(root, insts, rev, count, briefs, questions_path, briefs_path=None):
    """(refusals, brief problems) a real run would meet: each is a line."""
    refusals, manifest = [], Path(root) / MANIFEST
    if not manifest.exists():
        refusals.append(f"{root} holds no {MANIFEST}: no instance was set up there (repro setup)")
    elif count and count > len(json.loads(manifest.read_text(encoding="utf-8"))["instances"]):
        refusals.append(f"--instances {count}: {manifest} holds fewer instances")
    for i in insts if manifest.exists() else []:
        for what, path in (("bare", i["bare"]), ("clone", i["clone"]), ("mcp-config", i["mcp_config"])):
            if not Path(path).exists():
                refusals.append(f"instance {i['n']}: its {what} {path} is not there")
        log = Path(i["clone"]) / "_private" / "querylog.json"
        mode = json.loads(log.read_text(encoding="utf-8")).get("mode") if log.exists() else None
        if Path(i["clone"]).exists() and mode != "off":
            refusals.append(f"instance {i['n']}: its query log mode is {mode}, not off ({log})")
    if rev:
        bare = next((Path(i["bare"]) for i in insts if Path(i["bare"]).is_dir()), None)
        if bare and subprocess.run(["git", "cat-file", "-e", f"{rev}:{ADDED}"], cwd=str(bare),
                                   capture_output=True).returncode == 0:
            refusals.append(f"the start commit {rev[:12]} holds {ADDED}: the frozen questions must come after it")
    if briefs:
        found = question_problems(briefs, load_questions(questions_path))
        if found:
            refusals.append(f"repro questions fails ({len(found)} problem(s); first: {found[0]})")
    else:
        refusals.append(f"no brief rows: {HOME / BRIEFS} is missing or empty")
    for path in (briefs_path or HOME / BRIEFS, questions_path or HOME / ADDED):
        if Path(path).exists():
            r = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all", "--", Path(path).name],
                               cwd=str(Path(path).parent), capture_output=True, text=True, encoding="utf-8")
            if r.returncode != 0:
                refusals.append(f"{path} is not in a git checkout: its content cannot be compared with HEAD")
            elif r.stdout.strip():
                refusals.append(f"{path} differs from HEAD (commit or restore it): the run records its sha256")
    refusals.extend(why for _, why in [claude_path()] if why)
    return refusals, brief_problems(briefs)


def area_order(areas, n, count):
    """`areas` as instance `n` of `count` runs them: the list rotated left by (n-1) times len(areas)//count places, so
    instance 1 keeps the briefs' order and no area is the last of every instance."""
    if not areas:
        return []
    k = (n - 1) * (len(areas) // max(count, 1)) % len(areas)
    return [*areas[k:], *areas[:k]]


def may_start(spent, area_usd, instance_usd):
    """Whether an instance with `spent` dollars recorded may start one more area: the spend plus --area-usd, the most
    the area can add, stays within --instance-usd."""
    return spent + area_usd <= instance_usd + 1e-9


def cap_split(todo, spent, area_usd, instance_usd):
    """(areas the cap covers, areas it leaves out) of `todo`, in order, when every area costs --area-usd."""
    start = []
    for b in todo:
        if not may_start(spent + len(start) * area_usd, area_usd, instance_usd):
            break
        start.append(b)
    return start, todo[len(start):]


def todo_of(briefs, results, n):
    """The briefs of instance `n` with no finished result, in the order `briefs` gives."""
    last = latest(results)
    return [b for b in briefs if last.get((n, b["area"].strip()), {}).get("failure", "x")]


def estimate(todo, area_usd, instance_usd, spent=0.0):
    """The most one instance can spend from now on: every area `cap_split` covers at the area cap, so spent plus this
    never passes the instance cap."""
    return len(cap_split(range(todo), spent, area_usd, instance_usd)[0]) * area_usd


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def area_record(inst, brief, opts, env, argv, prompt, timeout):
    """Run one area's session in the instance's clone and return its result line (a dict). A harness error is a line
    with failure `error`: it ends no other instance."""
    n, area = inst["n"], brief["area"].strip()
    bare, clone = Path(inst["bare"]), Path(inst["clone"])
    rec = {"instance": n, "area": area, "started": utc_now(), "model": model_id(opts["model"]), "effort": opts["effort"],
           "settings": SETTINGS, "bare_before": "", "bare_after": ""}
    t = time.time()
    try:
        rec["bare_before"] = sh_git(bare, env, "rev-parse", "refs/heads/main")
        reset_clone(clone, env)
        r = stream_run(argv, prompt, clone, env, timeout=timeout, clean=True)
    except (Refused, OSError) as e:
        r = {"error": f"harness: {e}"[:300]}
    wall = round(time.time() - t, 1)
    try:
        rec["bare_after"] = sh_git(bare, env, "rev-parse", "refs/heads/main")
    except Refused:
        pass
    fail = failure_of(r)
    # a timed-out or result-less session states no cost: it is recorded at the area cap, the most it can have spent
    rec.update(failure=fail, subtype=r.get("subtype") or ("success" if not fail else fail), wall_s=wall,
               cost=opts["area_usd"] if r.get("cost_unknown") else r.get("cost") or 0, input_tokens=r.get("in_uncached", 0), output_tokens=r.get("out", 0),
               cache_write_tokens=r.get("cache_write", 0), cache_read_tokens=r.get("cache_read", 0),
               turns=r.get("turns", 0), max_turns=opts["max_turns"], turns_over_cap=r.get("turns", 0) > opts["max_turns"],
               tool_calls=sum(r.get("tools", {}).values()) + sum(r.get("sub_tools", {}).values()),
               model_usage=r.get("model_usage", {}))
    if r.get("cost_unknown"):
        rec["cost_unknown"] = True
    if fail:
        rec["error"] = str(r.get("error", ""))[:300]
    return rec


def run_instance(inst, briefs, results, opts, root, path, lock, out):
    """Every area of one instance, in the order `briefs` gives, while `may_start` holds for its recorded spend: the areas
    left are recorded as failures named budget. Each result is appended as soon as it exists."""
    n = inst["n"]
    env = instance_env(root, n)
    argv = session_argv(opts["model"], opts["effort"], opts["max_turns"], opts["area_usd"], inst["mcp_config"])
    spent = sum(r.get("cost") or 0 for r in results if r.get("instance") == n)
    todo = todo_of(briefs, results, n)

    def append(rec):
        with lock, open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(rec, sort_keys=True) + "\n")
            f.flush()
        out(f"instance {n}: {rec['area']}: {rec['failure'] or 'ok'}, ${rec['cost']:.2f}, {rec['turns']} turns, "
            f"{rec['wall_s']:.0f} s")

    for i, brief in enumerate(todo):
        if not may_start(spent, opts["area_usd"], opts["instance_usd"]):
            for left in todo[i:]:
                append({"instance": n, "area": left["area"].strip(), "started": utc_now(), "model": model_id(opts["model"]),
                        "effort": opts["effort"], "settings": SETTINGS, "bare_before": "", "bare_after": "",
                        "failure": "budget", "subtype": "budget", "wall_s": 0, "cost": 0, "input_tokens": 0,
                        "output_tokens": 0, "cache_write_tokens": 0, "cache_read_tokens": 0, "turns": 0,
                        "max_turns": opts["max_turns"], "turns_over_cap": False, "tool_calls": 0, "model_usage": {},
                        "error": f"instance spend ${spent:.2f} plus --area-usd {opts['area_usd']:g} passes --instance-usd "
                                 f"{opts['instance_usd']:g}"})
            break
        rec = area_record(inst, brief, opts, env, argv, area_prompt(brief), opts["timeout"])
        spent += rec["cost"]
        append(rec)


def run(count=None, root=None, dry_run=False, briefs_path=None, questions_path=None, out=print, **limits):
    """`repro run`: start every instance's area sessions at once (one thread each, the areas of an instance in its own
    `area_order` of the briefs, each only while `may_start` holds) and append each result to DIR/results.jsonl; a run again skips the areas with a result and retries
    the failed ones. `limits` are DEFAULTS' keys. With `dry_run` nothing starts: the argv, the estimate and every
    refusal are printed; returns 0, or 1 for a briefs problem. A real run raises Refused on a refusal or a briefs
    problem and returns 0 when every area has a result, else 1."""
    opts = {**DEFAULTS, **{k: v for k, v in limits.items() if v is not None}}
    if opts["effort"] not in EFFORTS:
        raise Refused(f"--effort {opts['effort']}: one of {', '.join(EFFORTS)}")
    root = Path(root) if root else default_dir()
    briefs = load_briefs(briefs_path)
    insts, rev = instances_of(root, count)
    refusals, bad = run_problems(root, insts, rev, count, briefs, questions_path, briefs_path)
    path = root / RESULTS
    results = read_results(path)
    areas = len(briefs)
    ordered = {i["n"]: area_order(briefs, i["n"], len(insts)) for i in insts}
    plan = [(i, todo_of(ordered[i["n"]], results, i["n"])) for i in insts]
    note = {k: opts[k] for k in ("model", "effort", "max_turns", "area_usd", "timeout")}
    note["orders"] = {str(n): [b["area"].strip() for b in order] for n, order in ordered.items()}
    note["argv"] = session_argv(opts["model"], opts["effort"], opts["max_turns"], opts["area_usd"], "MCP-CONFIG")
    record = Path(root) / RUN_RECORD
    if record.exists() and not refusals:
        old = json.loads(record.read_text(encoding="utf-8"))
        if old.get("argv") != note["argv"] or old.get("timeout") != note["timeout"] or old.get("settings") != SETTINGS:
            refusals.append(f"{record} holds other settings or limits than this run's: remove it with {path} to start over")
    if dry_run:
        out(f"repro run: {len(insts)} instance(s), {areas} area(s), dir {root}")
        out(f"settings: {SETTINGS}")
        out(f"claude: {claude_path()[0] or '(not found)'}")
        total = 0.0
        for i, todo in plan:
            argv = session_argv(opts["model"], opts["effort"], opts["max_turns"], opts["area_usd"], i["mcp_config"])
            spent = sum(r.get("cost") or 0 for r in results if r.get("instance") == i["n"])
            start, left = cap_split(todo, spent, opts["area_usd"], opts["instance_usd"])
            up = estimate(len(todo), opts["area_usd"], opts["instance_usd"], spent)
            total += up
            out(f"instance {i['n']}: clone {i['clone']}")
            out(f"  argv: {shlex.join(argv)}")
            out(f"  order: {', '.join(b['area'].strip() for b in ordered[i['n']]) or '(none)'}")
            out(f"  areas to run: {len(todo)} of {areas}, estimate up to ${up:.2f} (--area-usd {opts['area_usd']:g} each, "
                f"no area starts unless ${spent:.2f} recorded plus --area-usd stays within ${opts['instance_usd']:g})")
            out(f"  cap leaves out: {', '.join(b['area'].strip() for b in left) or '(none)'}")
        if plan and areas:
            out(f"estimate: up to ${total:.2f} for the run")
            out("prompt of the first area (stdin; the others differ in the brief only):")
            for ln in area_prompt(briefs[0]).splitlines():
                out(f"  | {ln}")
        for ln in refusals:
            out(f"refusal: {ln}")
        for ln in bad:
            out(f"briefs problem: {ln}")
        return 1 if bad else 0
    if refusals or bad:
        raise Refused("; ".join([*refusals, *(f"briefs problem: {b}" for b in bad)]))
    root.mkdir(parents=True, exist_ok=True)
    out(f"claude: {claude_path()[0]}")
    shas = {"briefs_sha256": file_sha256(briefs_path or HOME / BRIEFS),
            "questions_sha256": file_sha256(questions_path or HOME / ADDED)}
    record.write_text(json.dumps({**note, "settings": SETTINGS, **shas}, indent=2) + "\n", encoding="utf-8", newline="\n")
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=len(insts)) as pool:
        futures = [pool.submit(run_instance, i, ordered[i["n"]], results, opts, root, path, lock, out) for i in insts]
        for f in futures:
            f.result()
    last = latest(read_results(path))
    failed = [k for i in insts for b in briefs if (k := (i["n"], b["area"].strip())) in last and last[k].get("failure")]
    spent = sum(r.get("cost") or 0 for r in read_results(path))
    out(f"repro run: {len(insts) * areas - len(failed)} of {len(insts) * areas} area(s) finished, {len(failed)} failed, "
        f"${spent:.2f} recorded in {path}")
    return 1 if failed else 0


TURN_CAP_KEYS = ("max_turns", "turns_over_cap")  # keys a results line of an older run lacks
SCENARIO = "repro"  # the scenario of the rows `record_results` merges into the results file
RECORD_METRICS = (("cost", "cost"), ("input", "input_tokens"), ("out", "output_tokens"), ("cache_read", "cache_read_tokens"),
                  ("cache_write", "cache_write_tokens"), ("turns", "turns"), ("tool_calls", "tool_calls"),
                  ("wall_s", "wall_s"), ("max_turns", "max_turns"),
                  ("turns_over_cap", "turns_over_cap"))  # (metric, key of the json line) of the numbers a row holds; a line without a key has no row for it


def file_sha256(path):
    """The sha256 hex of a file's bytes; Refused when it is not there."""
    if not Path(path).is_file():
        raise Refused(f"{path} is not there: its sha256 is part of the record's note")
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def record_rows(results, rev, briefs_sha, questions_sha):
    """The results-file rows of a run's json lines: scenario `repro`, record the first 7 characters of the start sha `rev`,
    one case per area, one arm per instance (`instance-N`) and the metrics of RECORD_METRICS, then `models`, `failure`
    (`none` for a finished area), `main_before` and `main_after` (7 characters each). The date is the earliest start
    among the lines, so the same lines give the same rows. Only the newest line of an (instance, area) counts."""
    short = rev[:7]
    last = latest([r for r in results if r.get("instance") is not None and r.get("area")])
    date = min((r["started"][:10] for r in results if isinstance(r.get("started"), str) and r["started"]), default="")
    note = f"start {rev}; briefs sha256 {briefs_sha}; questions sha256 {questions_sha}"
    rows = []
    for inst, area in sorted(last, key=lambda k: (str(k[0]).zfill(6), str(k[1]))):
        r = last[(inst, area)]
        values = [(m, int(v) if isinstance(v, bool) else v) for m, key in RECORD_METRICS
                  if (v := r.get(key, None if key in TURN_CAP_KEYS else 0)) is not None]
        values += [("models", ",".join(sorted(r.get("model_usage") or {})) or r.get("model", "")),
                   ("failure", r.get("failure") or "none"), ("main_before", (r.get("bare_before") or "")[:7]),
                   ("main_after", (r.get("bare_after") or "")[:7])]
        for metric, value in values:
            if isinstance(value, float):
                value = round(value, 6)
            rows.append({"scenario": SCENARIO, "record": short, "date": date, "commit": short, "claude_code": "",
                         "kb_topics": "", "case": area, "arm": f"instance-{inst}", "model": r.get("model", ""),
                         "metric": metric, "value": value, "runs": 1, "note": note})
    return rows


def cells(row):
    return tuple(str(row.get(k, "")) for k in FIELDS)


def record_results(root=None, file=None, briefs_path=None, questions_path=None, dry_run=False, out=print):
    """`repro record`: merge the json lines of DIR/results.jsonl into the results file `file` (default
    kb/_self/reports/benchmarks.csv) as the scenario `repro` (record_rows), in place of the rows of the same start
    commit; the start commit is DIR's manifest's, the shas in the note are those of the briefs and the questions files
    as they are now. The same lines again change nothing. With `dry_run` the rows are printed and nothing is written.
    No lines is no error. Returns 0, or raises Refused (no manifest, no briefs or questions file)."""
    root = Path(root) if root else default_dir()
    results = read_results(root / RESULTS)
    if not results:
        out(f"repro record: {root / RESULTS} holds no result line: nothing to record")
        return 0
    manifest = root / MANIFEST
    if not manifest.exists():
        raise Refused(f"{root} holds no {MANIFEST}: the start commit of the result lines is unknown")
    rev = json.loads(manifest.read_text(encoding="utf-8")).get("rev", "")
    if not rev:
        raise Refused(f"{manifest} names no rev: the start commit of the result lines is unknown")
    rows = record_rows(results, rev, file_sha256(briefs_path or HOME / BRIEFS), file_sha256(questions_path or HOME / ADDED))
    target = Path(file) if file else BENCH_RESULTS
    old = read_rows(target)
    held = sorted(cells(r) for r in old if r["scenario"] == SCENARIO and r["record"] == rev[:7])
    same = held == sorted(cells(r) for r in rows)
    if dry_run:
        for r in rows:
            out(f"{r['scenario']} {r['record']} {r['date']} {r['case']} {r['arm']} {r['metric']}={r['value']}")
    elif not same:
        write_rows(merge_rows(old, rows), target)
    out(f"repro record: {len(rows)} row(s) of record {rev[:7]} " + (
        f"already in {target}: nothing changes" if same else
        f"would replace {len(held)} row(s) of {target}" if dry_run else f"merged into {target}, replacing {len(held)}"))
    return 0


COMPARE_SCENARIO = "repro-compare"  # the scenario of the rows `compare` merges into the results file
SAME_CLAIM = 0.8  # the difflib ratio at or above which two facts of one article path are the same claim
TOKEN_OVERLAP = 0.5  # the share of the words of two facts, on different article paths, that citing one source makes one claim
LEDGER_FILES = ("_gaps.md", "_conflicts.md", "_answers.md")  # the markdown ledgers whose entries end `(topic: domain/slug)`
TOPIC_MARK = re.compile(r"\(topic:\s*([^)\s]+)\)")
TAG_KINDS = ("DOC", "CODE", "DER", "COMMUNITY", "UNK")  # the tag mix `compare` counts, kbfacts.EVIDENCE_KINDS without DECISION
COMPARE_METRICS = ("articles_added", "facts_added", *(k.lower() for k in TAG_KINDS), "sources_added", "url_jaccard",
                   "fact_overlap", "conflicts", "paths_same", "ledger_rows_same", "source_rows_same", "check_errors", "lint_errors", "unanchored", "eval_passed", "eval_total",
                   "found_start", "found_end", "false_good_start", "false_good_end", "churn", "agreement",
                   "turns", "max_turns", "turns_over_cap")
LEARN_HOST = "learn.microsoft.com"  # a fact whose sources are all pages of it needs no anchor row (kb-research SKILL.md step 5)
LINT = Path(".claude") / "skills" / "kb-verify" / "lint.py"  # the contract lint of a checkout


def jaccard(a, b):
    """Plain set Jaccard of two sets: 1.0 for two empty sets (factdiff.jaccard's reading of two empty texts)."""
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a | b else 1.0


def claim(fact):
    """A fact line's claim text: its tags and notes removed (factdiff.fact_text)."""
    import factdiff
    return factdiff.fact_text(fact["text"])


def source_keys(fact):
    """The sources a fact line cites, as a set: the bare url of each id its checkout's _sources.csv resolves
    (`added_between` sets `urls`), else the id itself."""
    return set(fact.get("urls") or fact.get("ids") or ())


def match_facts(a, b):
    """[(i, j)] the facts of `a` and `b` that are one claim, whatever article each is written in: a pair on the same
    article path whose difflib ratio (factdiff.unit_sim of their claims) is at least SAME_CLAIM, or a pair, on any path,
    that cites one source (`source_keys`) and whose claims share at least TOKEN_OVERLAP of their words, taken best
    first, each fact in one pair at most. A pair whose ratio cannot reach SAME_CLAIM by its lengths or letters
    (difflib's two upper bounds) is judged by its words only."""
    import difflib, factdiff
    by_path, by_source = {}, {}
    for i, f in enumerate(a):
        by_path.setdefault(f["path"], []).append(i)
        for k in source_keys(f):
            by_source.setdefault(k, []).append(i)
    texts_a = [claim(f) for f in a]
    keys_a = [factdiff.words_key(t) for t in texts_a]
    norms_a = [factdiff.norm(t) for t in texts_a]
    sm = difflib.SequenceMatcher(None, autojunk=False)
    found = []
    for j, f in enumerate(b):
        text, key = claim(f), factdiff.words_key(claim(f))
        words = set(key.split())
        sm.set_seq2(factdiff.norm(text))
        near = set(by_path.get(f["path"], []))
        shared = {i for k in source_keys(f) for i in by_source.get(k, [])}
        for i in sorted(near | shared):
            if keys_a[i] == key:
                found.append((-1.0, i, j))
                continue
            sm.set_seq1(norms_a[i])
            ratio = 0.0
            if sm.real_quick_ratio() >= SAME_CLAIM and sm.quick_ratio() >= SAME_CLAIM:
                ratio = factdiff.unit_sim(texts_a[i], text)
            if ratio >= SAME_CLAIM:
                found.append((-ratio, i, j))
            elif i in shared:
                theirs = set(keys_a[i].split())
                share = len(words & theirs) / len(words | theirs) if words | theirs else 0.0
                if share >= TOKEN_OVERLAP:
                    found.append((-share, i, j))
    pairs, used_a, used_b = [], set(), set()
    for _, i, j in sorted(found):
        if i not in used_a and j not in used_b:
            pairs.append((i, j))
            used_a.add(i)
            used_b.add(j)
    return sorted(pairs)


def overlap_and_conflicts(a, b):
    """(overlap, conflicts) of two instances' added facts: the matched pairs over the union of the facts (a pair counts
    once), and the pairs whose claims' factdiff.numbers differ, as (fact of a, fact of b)."""
    import factdiff
    pairs = match_facts(a, b)
    union = len(a) + len(b) - len(pairs)
    return (len(pairs) / union if union else 1.0,
            [(a[i], b[j]) for i, j in pairs if factdiff.numbers(claim(a[i])) != factdiff.numbers(claim(b[j]))])


def checkout_path(root, n):
    """The detached checkout `compare` makes of instance N's bare: beside its clone, under the scratch directory."""
    return clone_path(root, n).parent / f"compare{n}"


def make_checkout(bare, dest, env):
    """A clone of `bare` at `dest` with no work tree, to put detached at each sha of an area."""
    shutil.rmtree(dest, ignore_errors=True)
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    sh_git(Path(dest).parent, env, "clone", "-q", "--no-checkout", str(bare), str(dest))


def put_at(checkout, sha, env):
    """The work tree of `checkout` detached at `sha`, clean of what a tool left (its _cache and _private)."""
    sh_git(checkout, env, "checkout", "-q", "-f", "--detach", sha)
    sh_git(checkout, env, "clean", "-q", "-f", "-f", "-d", "-x")


def tool_out(argv, checkout, env):
    """(exit code, stdout) of one of the checkout's own tools run by subprocess in it."""
    p = sh([sys.executable, *argv], checkout, env)
    return p.returncode, p.stdout


def json_of(text):
    """The json value that starts the first line of `text` that begins one, else None."""
    for pos in [m.start() for m in re.finditer(r"^[\[{]", text, re.M)]:
        try:
            return json.loads(text[pos:])
        except ValueError:
            continue
    return None


def unanchored(fact, key, anchored, sources):
    """Whether a fact line of `state_of` is a DOC fact with no `_anchors.csv` row of its file (`anchored`: {(fact key,
    root-relative path)}) that cites a source other than a Microsoft Learn page: one whose sources are all Learn pages is
    exempt from a quote, and so from an anchor row, by kb-research SKILL.md step 5."""
    import urllib.parse
    if "DOC" not in fact["kinds"] or (key, fact["rel"]) in anchored:
        return False
    hosts = {urllib.parse.urlsplit(sources.get(i, "")).hostname for i in fact["ids"]}
    return not (fact["ids"] and hosts == {LEARN_HOST})


def cells_text(cells):
    """The cells of one csv row joined as one text: two rows are the same when every cell is."""
    return "\x1f".join(cells)


def topic_key(root, path):
    """`root/path` without its .md or .csv extension: what the files, the rows and the entries of one article share."""
    return f"{root}/" + re.sub(r"\.(?:md|csv)$", "", path.strip().lstrip("/"))


def ledger_rows(base, root, into):
    """Add to `into` ({article: {row text}}) the ledger rows of the root directory `base`: each `_anchors.csv` row under
    its `path`, each `_coverage.csv` row under each of its `files`, and each entry of `_gaps.md`, `_conflicts.md` and
    `_answers.md` that names an article by `(topic: domain/slug)` under it; a row text starts with its ledger's name."""
    for name, column in (("_anchors.csv", "path"), ("_coverage.csv", "files")):
        for row in read_csv(base / name):
            paths = [p for p in re.split(r"[;\s]+", row.get(column, "")) if p]
            for p in paths:
                into.setdefault(topic_key(root, p), set()).add(name + "\x1e" + cells_text(row.values()))
    for name in LEDGER_FILES:
        path = base / name
        if not path.is_file():
            continue
        entry = []
        for ln in path.read_text(encoding="utf-8").splitlines() + ["- "]:
            if entry and (ln.startswith(("- ", "#")) or not ln.strip() or not ln.startswith(" ")):
                text = " ".join(x.strip() for x in entry)
                for m in TOPIC_MARK.finditer(text):
                    into.setdefault(topic_key(root, m.group(1)), set()).add(name + "\x1e" + text)
                entry = []
            if ln.startswith("- ") or (entry and ln.startswith(" ") and ln.strip()):
                entry.append(ln)


def state_of(checkout, env):
    """What the checkout at its sha holds, read with its own tools: `facts` (path, line, text, kinds of each fact line
    of each root, `rag.py --json facts`, and `unanchored`: a DOC fact with no row in its root's `_anchors.csv`, the facts
    whose sources are all Learn pages left out), `audit` ({article path: {kind: count}}, `rag.py --json audit`),
    `sources` ({source id: url} of each root's _sources.csv), `source_rows` ({source id: the row's cells joined}) and
    `ledgers` ({article: {ledger row}}: the rows of each root's _anchors.csv and _coverage.csv, and the entries of its
    `_gaps.md`, `_conflicts.md` and `_answers.md` that end `(topic: ...)`, each under its article, a path without its
    extension, `public/ad/x`). Refused when a tool printed no json."""
    import kbfacts
    tools = Path(checkout) / "_tools"
    roots = sorted(d.name for d in (Path(checkout) / "kb").iterdir() if (d / "_sources.csv").is_file()) \
        if (Path(checkout) / "kb").is_dir() else []
    sources, source_rows, ledgers = {}, {}, {}
    for r in roots:
        for row in read_csv(Path(checkout) / "kb" / r / "_sources.csv"):
            sources.setdefault(row.get("id", ""), row.get("url", ""))
            source_rows.setdefault(row.get("id", ""), cells_text(row.values()))
        ledger_rows(Path(checkout) / "kb" / r, r, ledgers)
    facts = []
    for r in roots:
        code, out = tool_out([str(tools / "rag.py"), "--json", "facts", r], checkout, env)
        rows = json_of(out)
        if not isinstance(rows, list):
            raise Refused(f"{checkout}: rag.py facts {r} printed no json (exit {code})")
        anchored = {(a.get("fact", ""), a.get("path", "")) for a in read_csv(Path(checkout) / "kb" / r / "_anchors.csv")}
        for f in rows:
            tags = f.get("tags") or []
            one = {"path": f["path"], "line": f["line"], "text": f["text"], "kinds": [t["kind"] for t in tags],
                   "ids": [i for t in tags for i in t.get("ids") or []], "rel": f["path"].split("/", 1)[-1]}
            one["unanchored"] = unanchored(one, kbfacts.fact_key(f["text"]), anchored, sources)
            facts.append(one)
    code, out = tool_out([str(tools / "rag.py"), "--json", "audit"], checkout, env)
    rows = json_of(out)
    if not isinstance(rows, list):
        raise Refused(f"{checkout}: rag.py audit printed no json (exit {code})")
    return {"facts": facts, "audit": {a["path"]: {k: a.get(k, 0) for k in TAG_KINDS} for a in rows}, "sources": sources,
            "source_rows": source_rows, "ledgers": ledgers}


def added_between(before, after):
    """What `after` holds that `before` did not: `articles` (paths), `facts` (those of `after` whose path and claim
    `before` lacks, each with `urls`, the bare urls its cited ids resolve to in `after`'s _sources.csv), `kinds` (the
    audit's count of each tag kind, after less before), `sources` ({id: bare url}), `ledger` ({article: {ledger row}}
    the rows of `after`'s ledgers that `before` lacks, under the articles of `state_of`) and `cited` ({bare url: the
    row of its source in `after`, the first of the ids that resolve to it} of the urls the added facts cite)."""
    import factdiff, ql_research
    bare = lambda i: ql_research.bare_url(after["sources"][i]) if i in after["sources"] else ""  # noqa: E731
    old = {(f["path"], factdiff.words_key(claim(f))) for f in before["facts"]}
    seen, facts, cited = set(), [], {}
    for f in after["facts"]:
        key = (f["path"], factdiff.words_key(claim(f)))
        if key not in old and key not in seen:
            seen.add(key)
            urls = sorted({bare(i) for i in f["ids"] if bare(i)})
            facts.append({**f, "urls": urls})
            for i in f["ids"]:
                if bare(i) and i in after["source_rows"]:
                    cited.setdefault(bare(i), after["source_rows"][i])
    total = lambda s, k: sum(c.get(k, 0) for c in s["audit"].values())  # noqa: E731
    ledger = {a: sorted(rows - before["ledgers"].get(a, set())) for a, rows in after["ledgers"].items()}
    return {"articles": sorted(set(after["audit"]) - set(before["audit"])), "facts": facts,
            "kinds": {k: total(after, k) - total(before, k) for k in TAG_KINDS},
            "sources": {i: ql_research.bare_url(u) for i, u in after["sources"].items() if i not in before["sources"]},
            "ledger": {a: rows for a, rows in ledger.items() if rows}, "cited": cited}


def pair_identity(da, db):
    """(paths_same, ledger_rows_same, source_rows_same) of two instances' `added_between` results for one area:
    whether the article paths of their facts and added articles are the same (1 or 0); of the ledger rows added for the
    articles either wrote, the share both hold byte for byte (None when neither added one); and of the source rows of the
    urls both cited, the share that is the same row (None when they cite no url in common)."""
    pa = {f["path"] for f in da["facts"]} | set(da["articles"])
    pb = {f["path"] for f in db["facts"]} | set(db["articles"])
    topics = {topic_key(*p.split("/", 1)) for p in pa | pb}
    ra = {(t, r) for t in topics for r in da["ledger"].get(t, ())}
    rb = {(t, r) for t in topics for r in db["ledger"].get(t, ())}
    both = sorted(set(da["cited"]) & set(db["cited"]))
    return (int(pa == pb), len(ra & rb) / len(ra | rb) if ra | rb else None,
            sum(1 for u in both if da["cited"][u] == db["cited"][u]) / len(both) if both else None)


def error_counts(checkout, rev, env):
    """(check.py errors, kb-verify lint errors) of the checkout as it is: each None when its tool printed no count.
    The lint counts the facts added since `rev`."""
    _, out = tool_out([str(Path(checkout) / "_tools" / "check.py")], checkout, env)
    m = re.search(r"\berrors=(\d+)", out)
    _, out = tool_out([str(Path(checkout) / LINT), "--json", "--base", rev], checkout, env)
    found = json_of(out)
    return (int(m.group(1)) if m else None,
            sum(1 for x in found if isinstance(x, dict) and x.get("level") == "ERROR") if isinstance(found, list) else None)


VERDICT_RANK = {"none": 0, "weak": 1, "good": 2}
FOUND_CHECKS = ("path", "text", "regex")  # the failed checks of a `rag.py eval` row that say its expectation is not in the pack


def frozen_pass(start_verdict, verdict, found):
    """Whether a frozen row passes: its `expect_re`, `expect_text` or `expect_paths` is `found` in the pack, else the
    verdict ranks (none, weak, good) at least the one measured at the start commit, not the row's `expect_verdict`. The
    row's own verdict check is no part of it: research that answers a row that was `none` at the start raises the
    figure, and one that lifts a `weak` to `good` keeps it."""
    return bool(found) or VERDICT_RANK.get(verdict, -1) >= VERDICT_RANK.get(start_verdict, 0)


def eval_rows(checkout, questions, env):
    """{row id: {verdict, regex_ok, found}} of the checkout's own `rag.py eval` over the frozen questions file, `found`
    true when none of the row's path, text and regex checks failed; None when it printed no json."""
    _, out = tool_out([str(Path(checkout) / "_tools" / "rag.py"), "--json", "eval", "--file", str(questions)], checkout, env)
    res = json_of(out)
    if not isinstance(res, dict) or "rows" not in res:
        return None
    return {r["id"]: {"verdict": r["verdict"], "regex_ok": "regex" not in r.get("failed", []),
                      "found": not set(r.get("failed", [])) & set(FOUND_CHECKS)}
            for r in res["rows"]}


def answer_counts(ids, rows):
    """(answer-found, false-good) counts of the frozen rows `ids` in one `eval_rows` result: found when none of the row's
    path, text and regex checks failed; false good when its verdict is `good` and its answer is not found. A row the
    result lacks counts in neither; (None, None) when `rows` is None."""
    if rows is None:
        return None, None
    mine = [rows[q] for q in ids if q in rows]
    return (sum(1 for r in mine if r["found"]),
            sum(1 for r in mine if r["verdict"] == "good" and not r["found"]))


def churn(ids, start, end):
    """How many of the frozen rows `ids` have a different verdict in `end` than in `start` (two `eval_rows` results);
    a row either result lacks is not counted; None when either is None."""
    if start is None or end is None:
        return None
    return sum(1 for q in ids if q in start and q in end and start[q]["verdict"] != end[q]["verdict"])


def agreement(areas, instances, asked, evals):
    """{area: share of its frozen rows on which every instance has the same verdict and the same expect_re outcome}
    over `areas`, the ones every instance finished; an area with no frozen row has none. `evals` is {instance: eval_rows}."""
    out = {}
    for area in areas:
        ids = [q["id"] for q in asked if q.get("area", "").strip() == area]
        if not ids:
            continue
        same = 0
        for qid in ids:
            seen = {(e[qid]["verdict"], e[qid]["regex_ok"]) if e and qid in e else None for e in (evals.get(i) for i in instances)}
            same += len(seen) == 1 and None not in seen
        out[area] = same / len(ids)
    return out


def turn_cap_metrics(rec):
    """{turns, max_turns, turns_over_cap (1 or 0)} of an area's json line `rec`; {} for a line of an older run, which
    holds no cap. `turns_over_cap` says num_turns passed --max-turns, not that the cap failed: a run the cap ends counts
    one turn past it."""
    if not rec or rec.get("max_turns") is None:
        return {}
    return {"turns": rec.get("turns", 0), "max_turns": rec["max_turns"], "turns_over_cap": int(bool(rec.get("turns_over_cap")))}


def compare_rows(rev, date, note, data):
    """The results-file rows of a comparison: `data` is a list of (case, arm, {metric: value}); a metric that is None
    is left out."""
    rows = []
    for case, arm, metrics in data:
        for metric in COMPARE_METRICS:
            value = metrics.get(metric)
            if value is None:
                continue
            if isinstance(value, float):
                value = round(value, 6)
            rows.append({"scenario": COMPARE_SCENARIO, "record": rev[:7], "date": date, "commit": rev[:7], "claude_code": "",
                         "kb_topics": "", "case": case, "arm": arm, "model": "", "metric": metric, "value": value, "runs": 1,
                         "note": note})
    return rows


def compare(root=None, record=False, file=None, questions_path=None, dry_run=False, out=print):
    """`repro compare`: measure each instance's bare main against the start commit, area by area by the shas of
    DIR/results.jsonl, in a detached checkout of its own whose tools run by subprocess; print per instance and area
    the articles, facts, tag mix and sources added, per pair the url Jaccard, the fact overlap (facts matched across
    the articles each instance wrote, `match_facts`) and the conflicts, and the identity of what they wrote
    (`pair_identity`: paths_same, ledger_rows_same, source_rows_same), per
    instance the check.py and lint errors and the frozen questions it passed, per area the agreement. The frozen
    questions are also run at the start commit: a row passes against the verdict measured there, not its
    `expect_verdict`; per instance and area it researched the answer-found and false-good (good without the answer)
    counts at start and at the instance's end are printed, and the DOC facts it added that no row of the root's
    _anchors.csv anchors (unanchored; a fact whose sources are all Learn pages is left out), per area it did not research
    the rows whose verdict moved (churn). With `record` the rows are merged into `file` (default kb/_self/reports/benchmarks.csv) as the scenario
    `repro-compare`, replacing the rows of the start commit. With `dry_run` it prints the metrics and the instances it
    would read and starts nothing. Returns 0, also with no instance or no result line; raises Refused (a bare or a sha
    that is gone, a tool that prints no json, also the eval at the start commit, no questions file)."""
    root = Path(root) if root else default_dir()
    manifest = root / MANIFEST
    if not manifest.exists():
        out(f"repro compare: {root} holds no {MANIFEST}: no instance was set up there, so no instance is read")
        if dry_run:
            out("metrics: " + ", ".join(COMPARE_METRICS))
        return 0
    data = json.loads(manifest.read_text(encoding="utf-8"))
    rev, insts = data.get("rev", ""), data.get("instances", [])
    last = latest(read_results(root / RESULTS))
    areas = list(dict.fromkeys(a for (_, a) in last if a))
    if dry_run:
        out(f"repro compare: start {rev[:12]}, dir {root}, {len(insts)} instance(s), {len(areas)} area(s) with a result")
        out("metrics: " + ", ".join(COMPARE_METRICS))
        for i in insts:
            mine = [a for a in areas if (i["n"], a) in last]
            out(f"instance {i['n']}: reads bare {i['bare']} in {checkout_path(root, i['n'])}, areas: {', '.join(mine) or '(none)'}")
        return 0
    if not last:
        out(f"repro compare: {root / RESULTS} holds no result line: no area to compare")
        return 0
    qpath = Path(questions_path) if questions_path else HOME / ADDED
    if not qpath.is_file():
        raise Refused(f"{qpath} is not there: the frozen questions of the agreement")
    asked = load_questions(qpath)
    ns = [i["n"] for i in insts]
    deltas, evals, errors, start = {}, {}, {}, None
    for inst in insts:
        if not Path(inst["bare"]).is_dir():
            raise Refused(f"instance {inst['n']}: its bare {inst['bare']} is gone")
    for inst in insts:
        n, env, bare = inst["n"], instance_env(root, inst["n"]), Path(inst["bare"])
        dest = checkout_path(root, n)
        make_checkout(bare, dest, env)
        try:
            if start is None:  # the start commit is one sha in every bare: its verdicts are measured once
                put_at(dest, rev, env)
                start = eval_rows(dest, qpath, env)
                if start is None:
                    raise Refused(f"{dest}: rag.py eval at the start commit {rev[:12]} printed no json")
            states = {}

            def at(sha):
                if sha not in states:
                    put_at(dest, sha, env)
                    states[sha] = state_of(dest, env)
                return states[sha]

            for area in areas:
                r = last.get((n, area))
                if not r:
                    continue
                before = r.get("bare_before") or rev
                deltas[(n, area)] = added_between(at(before), at(r.get("bare_after") or before))
            main = sh_git(bare, env, "rev-parse", "refs/heads/main")
            put_at(dest, main, env)
            errors[n] = error_counts(dest, rev, env)
            evals[n] = eval_rows(dest, qpath, env)
        finally:
            shutil.rmtree(dest, ignore_errors=True)
    out(f"repro compare: start {rev[:12]}, dir {root}, {len(insts)} instance(s), {len(areas)} area(s)")
    table = []  # (case, arm, {metric: value})
    for area in areas:
        ids = [q["id"] for q in asked if q.get("area", "").strip() == area]
        found_start, false_good_start = answer_counts(ids, start)
        for n in ns:
            d = deltas.get((n, area))
            if d is None:
                continue
            e = evals.get(n)
            passed = sum(1 for q in ids if e and q in e and q in start
                         and frozen_pass(start[q]["verdict"], e[q]["verdict"], e[q]["found"]))
            found_end, false_good_end = answer_counts(ids, e)
            m = {"articles_added": len(d["articles"]), "facts_added": len(d["facts"]), "sources_added": len(d["sources"]),
                 **{k.lower(): d["kinds"][k] for k in TAG_KINDS}, "eval_passed": passed, "eval_total": len(ids),
                 "found_start": found_start, "found_end": found_end, "false_good_start": false_good_start,
                 "false_good_end": false_good_end, "unanchored": sum(1 for f in d["facts"] if f["unanchored"]),
                 **turn_cap_metrics(last.get((n, area)))}
            table.append((area, f"instance-{n}", m))
            out(f"instance {n} area {area}: {m['articles_added']} article(s), {m['facts_added']} fact(s) added ("
                + ", ".join(f"{k} {d['kinds'][k]}" for k in TAG_KINDS) + f"), {m['sources_added']} source(s) added; "
                f"{passed} of {len(ids)} frozen row(s) passed"
                + (": " + " ".join(f"{q}={e[q]['verdict']}" for q in ids if e and q in e) if ids else ""))
            out(f"instance {n} area {area}: {m['unanchored']} DOC fact(s) added with no anchor row")
            if e is not None:
                out(f"instance {n} area {area}: answer found {found_start} at start, {found_end} at end; "
                    f"false good {false_good_start} at start, {false_good_end} at end")
        for k, a in enumerate(ns):
            for b in ns[k + 1:]:
                da, db = deltas.get((a, area)), deltas.get((b, area))
                if da is None or db is None:
                    continue
                fact_overlap, conflicts = overlap_and_conflicts(da["facts"], db["facts"])
                urls = jaccard(set(da["sources"].values()), set(db["sources"].values()))
                paths, ledger, cited = pair_identity(da, db)
                table.append((area, f"instance-{a}+instance-{b}",
                              {"url_jaccard": urls, "fact_overlap": fact_overlap, "conflicts": len(conflicts),
                               "paths_same": paths, "ledger_rows_same": ledger, "source_rows_same": cited}))
                out(f"pair {a}+{b} area {area}: url_jaccard {urls:.2f}, fact_overlap {fact_overlap:.2f}, "
                    f"{len(conflicts)} conflict(s)")
                out(f"pair {a}+{b} area {area}: paths_same {'yes' if paths else 'no'}, ledger_rows_same "
                    f"{'n/a' if ledger is None else f'{ledger:.2f}'}, source_rows_same "
                    f"{'n/a' if cited is None else f'{cited:.2f}'}")
                for fa, fb in conflicts:
                    out(f"  conflict: instance {a} {fa['path']}:{fa['line']}: {claim(fa)}")
                    out(f"            instance {b} {fb['path']}:{fb['line']}: {claim(fb)}")
    for area in dict.fromkeys(q.get("area", "").strip() for q in asked):  # rows of areas an instance did not research
        ids = [q["id"] for q in asked if q.get("area", "").strip() == area]
        for n in ns:
            moved = churn(ids, start, evals.get(n)) if area and ids and not last.get((n, area)) else None
            if moved is not None:
                table.append((area, f"instance-{n}", {"churn": moved}))
                out(f"instance {n} area {area} (not researched): {moved} of {len(ids)} frozen row(s) changed verdict "
                    "since the start commit")
    for n in ns:
        check_errors, lint_errors = errors[n]
        table.append(("all", f"instance-{n}", {"check_errors": check_errors, "lint_errors": lint_errors}))
        out(f"instance {n}: check.py errors {check_errors if check_errors is not None else 'not counted'}, lint errors "
            f"{lint_errors if lint_errors is not None else 'not counted'}"
            + ("" if evals[n] is not None else "; rag.py eval printed no json"))
    done = [a for a in areas if all(last.get((n, a)) and not last[(n, a)].get("failure") for n in ns)]
    shares = agreement(done, ns, asked, evals)
    for area, share in shares.items():
        table.append((area, "all", {"agreement": share}))
        out(f"area {area}: agreement {share:.2f} of {sum(1 for q in asked if q.get('area', '').strip() == area)} frozen row(s)")
    if not shares:
        out("agreement: no area every instance finished holds a frozen row")
    if not record:
        return 0
    date = min((r["started"][:10] for r in last.values() if isinstance(r.get("started"), str) and r["started"]), default="")
    note = f"start {rev}; questions sha256 {file_sha256(qpath)}"
    rows = compare_rows(rev, date, note, table)
    target = Path(file) if file else BENCH_RESULTS
    old = read_rows(target)
    held = sorted(cells(r) for r in old if r["scenario"] == COMPARE_SCENARIO and r["record"] == rev[:7])
    same = held == sorted(cells(r) for r in rows)
    if not same:
        write_rows(merge_rows(old, rows), target)
    out(f"repro compare: {len(rows)} row(s) of record {rev[:7]} " + (
        f"already in {target}: nothing changes" if same else f"merged into {target}, replacing {len(held)}"))
    return 0


INSTANCE_ARM = re.compile(r"instance-(\d+)")
ITEM_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*")
REPLAY_BRANCH = "repro-replay-instance{n}"  # the branch a replay rebases the instance's commits on, then folds into the current one
TRAILER = "KB-Work"


def number(value):
    """A results-file cell as a float, or None when it is empty or no number."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def standings(rows):
    """(record, date, {n: {"passed", "errors", "cost", "unanchored", "areas", "seen"}}, common) of the newest `repro-compare`
    record of `rows` (the greatest date, the later row on a tie). `seen` is the set of areas the record holds a row of the
    instance for, `areas` the set it finished: a seen one whose `repro` `failure` row, when it has one, is `none`. `common` is the set of
    areas every instance finished; per instance the sum of its eval_passed, the sum of its unanchored (None when no common
    area has the row) and the sum of the cost rows of the scenario `repro` of the same record (None when there is none)
    are over the common areas only, so an instance that finished fewer areas is not ranked by a lower cost. When no area
    is common the sums are over each instance's own finished areas. check_errors plus lint_errors (None when either is not
    there) are the instance's own. (None, None, {}, set()) when no row names an instance."""
    mine = [(k, r) for k, r in enumerate(rows) if r.get("scenario") == COMPARE_SCENARIO and INSTANCE_ARM.fullmatch(r.get("arm", ""))]
    if not mine:
        return None, None, {}, set()
    _, newest = max(mine, key=lambda kr: (kr[1].get("date", ""), kr[0]))
    record, date = newest.get("record", ""), newest.get("date", "")
    found, seen, failed = {}, {}, set()  # seen: n -> areas the record holds a row of; failed: (n, area) of a failure row
    per = {}  # (n, area, metric) -> summed value
    for r in rows:
        m = INSTANCE_ARM.fullmatch(r.get("arm", ""))
        if not m or r.get("record") != record or r.get("scenario") not in (COMPARE_SCENARIO, SCENARIO):
            continue
        n, area, metric, v = int(m.group(1)), r.get("case", ""), r.get("metric", ""), number(r.get("value"))
        d = found.setdefault(n, {"passed": 0.0, "check": None, "lint": None, "cost": None, "unanchored": None})
        if r["scenario"] == SCENARIO:
            if metric == "failure" and r.get("value", "") not in ("", "none"):
                failed.add((n, area))
            elif metric == "cost" and v is not None:
                per[(n, area, "cost")] = per.get((n, area, "cost"), 0.0) + v
                seen.setdefault(n, set()).add(area)
            continue
        if metric in ("check_errors", "lint_errors") and area == "all":
            if v is not None:
                d[metric[:-7]] = v
        elif metric in ("eval_passed", "unanchored") and v is not None:
            per[(n, area, metric)] = per.get((n, area, metric), 0.0) + v
            seen.setdefault(n, set()).add(area)
    finished = {n: {a for a in seen.get(n, set()) if (n, a) not in failed} for n in found}
    common = set.intersection(*finished.values()) if finished else set()
    for n, d in found.items():
        use = common or finished[n]
        for metric, key in (("eval_passed", "passed"), ("unanchored", "unanchored"), ("cost", "cost")):
            vals = [per[(n, a, metric)] for a in use if (n, a, metric) in per]
            if vals:
                d[key] = sum(vals)
    return record, date, {n: {"passed": d["passed"], "cost": d["cost"], "unanchored": d["unanchored"],
                              "errors": None if d["check"] is None or d["lint"] is None else d["check"] + d["lint"],
                              "areas": finished[n], "seen": seen.get(n, set())}
                          for n, d in found.items()}, common


def pick_key(d):
    """The landing rule as a sort key, smallest first: most eval_passed, then fewest errors, then lowest cost; a number
    that was not recorded ranks after every recorded one."""
    inf = float("inf")
    return (-d["passed"], inf if d["errors"] is None else d["errors"], inf if d["cost"] is None else d["cost"])


def pick(file=None, out=print):
    """`repro pick`: print, per instance of the newest `repro-compare` record of the results file `file` (default
    kb/_self/reports/benchmarks.csv), the numbers the landing rule reads over the areas every instance finished and the
    unanchored DOC facts it does not rank by, the areas left out of that comparison, then the instance it picks
    (standings). Returns 0, or 1 when the file holds no instance's row. Reads one file and nothing else."""
    target = Path(file) if file else BENCH_RESULTS
    record, date, found, common = standings(read_rows(target))
    if not found:
        out(f"repro pick: {target} holds no {COMPARE_SCENARIO} row of an instance: nothing to pick")
        return 1
    fmt = lambda v, f: "not recorded" if v is None else f.format(v)  # noqa: E731
    out(f"repro pick: record {record} ({date or 'no date'}), {len(found)} instance(s) in {target}")
    left = sorted(set().union(*(d["seen"] for d in found.values())) - common)
    if common:
        out(f"compared on {len(common)} area(s) every instance finished: {', '.join(sorted(common))}")
    else:
        out("no area every instance finished: each instance is compared on its own finished areas")
    for a in left:
        who = [str(n) for n in sorted(found) if a in found[n]["areas"]]
        out(f"left out of the comparison: area {a}, finished by " + (f"instance {', '.join(who)} only" if who else "no instance"))
    order = sorted(found, key=lambda n: (pick_key(found[n]), n))
    for n in order:
        d = found[n]
        out(f"instance-{n}: eval_passed {d['passed']:g}, check_errors+lint_errors {fmt(d['errors'], '{:g}')}, "
            f"unanchored {fmt(d['unanchored'], '{:g}')}, cost {fmt(d['cost'], '{:.2f}')}")
    best = order[0]
    why = "the only instance"
    if len(order) > 1:
        a, b = pick_key(found[best]), pick_key(found[order[1]])
        why = next((f"{('most eval_passed', 'fewest errors', 'lowest cost')[i]} over instance-{order[1]}"
                    for i in range(3) if a[i] != b[i]), f"a tie with instance-{order[1]}, the lowest number wins")
    out(f"picked: instance-{best} ({why})")
    return 0


def replay(instance, item, root=None, out=print):
    """`repro replay`: fetch main of instance `instance`'s bare (from DIR's manifest, by its path: no other remote is
    named) and rebase its commits since the start commit onto the current branch of the git work tree in the working
    directory (`git rebase --onto`), amending each with the trailer `KB-Work: ITEM`. The commits are rebased on the
    branch REPLAY_BRANCH, which is folded into the current branch with `--ff-only` and removed; on a conflict the
    rebase stays in progress there and the files in conflict are named. Returns 0 (also with no commit to replay), 1 on
    a conflict; raises Refused (no manifest, no such instance, a work tree with changes, a detached HEAD)."""
    if not ITEM_ID.fullmatch(item):
        raise Refused(f"--item {item!r}: an item id is letters, digits and hyphens")
    root = Path(root) if root else default_dir()
    manifest = root / MANIFEST
    if not manifest.exists():
        raise Refused(f"{root} holds no {MANIFEST}: no instance was set up there")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    inst = next((i for i in data.get("instances", []) if i["n"] == instance), None)
    if inst is None:
        raise Refused(f"--instance {instance}: {manifest} holds instance(s) " + ", ".join(str(i["n"]) for i in data.get("instances", [])))
    bare, rev, here = Path(inst["bare"]), data.get("rev", ""), Path.cwd()
    if not bare.is_dir():
        raise Refused(f"instance {instance}: its bare {bare} is gone")
    if not rev:
        raise Refused(f"{manifest} names no rev: the start commit is unknown")
    for name in ("rebase-merge", "rebase-apply"):
        if (here / run_git("rev-parse", "--git-path", name, cwd=here)).is_dir():
            raise Refused(f"a rebase is in progress in {here} (a replay's conflict, maybe): finish or abort it first")
    head = sh(["git", "symbolic-ref", "--short", "-q", "HEAD"], here, None)
    if head.returncode:
        raise Refused(f"{here} is no git work tree on a branch (a detached HEAD or none): the commits go on the current branch")
    branch = head.stdout.strip()
    if run_git("status", "--porcelain", "--untracked-files=no", cwd=here):
        raise Refused(f"{here} has uncommitted changes: commit or set them aside first")
    work = REPLAY_BRANCH.format(n=instance)
    if sh(["git", "rev-parse", "--verify", "-q", f"refs/heads/{work}"], here, None).returncode == 0:
        raise Refused(f"the branch {work} exists: a replay left it; finish it or remove it with git branch -D {work}")
    run_git("fetch", "-q", "--no-tags", str(bare), "refs/heads/main", cwd=here)
    tip = run_git("rev-parse", "--verify", "FETCH_HEAD^{commit}", cwd=here)
    if sh(["git", "merge-base", "--is-ancestor", rev, tip], here, None).returncode:
        raise Refused(f"the start commit {rev[:12]} is not in the history of instance {instance}'s main {tip[:12]}")
    commits = run_git("log", "--reverse", "--format=%h %s", f"{rev}..{tip}", cwd=here).splitlines()
    if not commits:
        out(f"repro replay: instance {instance}'s main {tip[:12]} holds no commit since {rev[:12]}: nothing to replay")
        return 0
    run_git("branch", work, tip, cwd=here)
    amend = f"git commit --amend --no-edit --no-verify -q --trailer '{TRAILER}: {item}'"
    p = sh(["git", "rebase", "--exec", amend, "--onto", branch, rev, work], here, None)
    if p.returncode:
        files = sh(["git", "diff", "--name-only", "--diff-filter=U"], here, None).stdout.split()
        if not files:
            raise Refused(f"git rebase failed on {work} in {here}: {(p.stderr or p.stdout).strip()[-300:]}; git rebase --abort "
                          f"then git checkout {branch} and git branch -D {work} undo it")
        out(f"repro replay: conflict replaying instance {instance}'s commits onto {branch}; files in conflict:")
        for f in files:
            out(f"  {f}")
        out(f"the rebase is in progress on {work}: resolve, git add, git rebase --continue, then git checkout {branch} and "
            f"git merge --ff-only {work}; or git rebase --abort, git checkout {branch} and git branch -D {work}")
        return 1
    run_git("checkout", "-q", branch, cwd=here)
    run_git("merge", "-q", "--ff-only", work, cwd=here)
    run_git("branch", "-q", "-D", work, cwd=here)
    out(f"repro replay: {len(commits)} commit(s) of instance {instance} since {rev[:12]} replayed onto {branch}, each with "
        f"{TRAILER}: {item}")
    for ln in commits:
        out(f"  {ln}")
    return 0
