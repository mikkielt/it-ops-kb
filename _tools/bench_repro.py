"""The research-reproducibility benchmark's isolated instances: `benchmarks.py repro setup`, `repro check`, `repro
questions`, `repro run` and `repro status` (stdlib only).

Each instance is a full bare copy of one pinned commit's history (DIR/originN.git, its main at REV), a working clone of
it outside the checkout (under bench_core's scratch directory) whose only remote is that bare path, a query log of mode
`off` in the clone, and an mcp-config file of its own for `claude -p --mcp-config FILE --strict-mcp-config`, so no
instance writes ~/.claude.json. `instance_env` is the session environment of an instance. `check` builds one such
instance as a probe, runs `kbgit.py sync --push` in it and proves the push landed on the probe's own bare and nowhere
else. `load_briefs` and `brief_problems` read and check the briefs file, `question_problems` the frozen questions
against it, and `status` names each instance's commits since the start commit and the ones a fresh fetch of the real
origin's main holds. `run` starts every instance's headless `/kb-research` sessions at once, one per area in the
briefs' order, and appends each area's result as a json line to DIR/results.jsonl (`session_argv` is the one argv,
`area_prompt` the one prompt). This module imports bench_core and kbpublic, and kbfacts where it reads the routing and
the clone home (kb/_self/code.md, Layout); benchmarks.py holds the command line.
"""
import csv, datetime, hashlib, json, os, shlex, shutil, subprocess, sys, tempfile, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import agent_bench
import kbpublic
from bench_core import HOME, isolate, no_plugin_env, scratch_dir, stream_run

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
             "GIT_SHALLOW_FILE", "GIT_REPLACE_REF_BASE", "GIT_NO_REPLACE_OBJECTS", "GIT_PREFIX", "GIT_NAMESPACE")


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
    KB_SESSION empty, KB_DOCS_CACHE unset, ENABLE_CLAUDEAI_MCP_SERVERS=false and KB_HOST_LOCK_DIR under DIR."""
    env = no_plugin_env()
    for k in LEAKY_ENV:
        env.pop(k, None)
    env.pop("KB_DOCS_CACHE", None)
    env.update({"KB_SESSION": "", "ENABLE_CLAUDEAI_MCP_SERVERS": "false", "KB_HOST_LOCK_DIR": str(lock_dir(root, n))})
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
    error), origin's main fetched, the work tree reset to it and what a session left untracked removed (ignored files,
    _private and _cache among them, stay)."""
    sh(["git", "rebase", "--abort"], clone, env)
    sh_git(clone, env, "fetch", "-q", "origin", "+refs/heads/main:refs/remotes/origin/main")
    sh_git(clone, env, "checkout", "-q", "-f", "main")
    sh_git(clone, env, "reset", "-q", "--hard", "refs/remotes/origin/main")
    sh_git(clone, env, "clean", "-q", "-f", "-d")


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


def run_problems(root, insts, rev, count, briefs, questions_path):
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
    if not shutil.which(CLAUDE[0]):
        refusals.append(f"{CLAUDE[0]} is not on PATH")
    return refusals, brief_problems(briefs)


def todo_of(briefs, results, n):
    """The briefs of instance `n` with no finished result, in the briefs' order."""
    last = latest(results)
    return [b for b in briefs if last.get((n, b["area"].strip()), {}).get("failure", "x")]


def estimate(todo, area_usd, instance_usd):
    """The most one instance can spend: every area at the area cap, but no area starts once the cap of the instance is
    reached, so at most the instance cap plus one area."""
    return min(todo * area_usd, instance_usd + area_usd)


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
    rec.update(failure=fail, subtype=r.get("subtype") or ("success" if not fail else fail), wall_s=wall,
               cost=r.get("cost") or 0, input_tokens=r.get("in_uncached", 0), output_tokens=r.get("out", 0),
               cache_write_tokens=r.get("cache_write", 0), cache_read_tokens=r.get("cache_read", 0),
               turns=r.get("turns", 0), tool_calls=sum(r.get("tools", {}).values()) + sum(r.get("sub_tools", {}).values()),
               model_usage=r.get("model_usage", {}))
    if fail:
        rec["error"] = str(r.get("error", ""))[:300]
    return rec


def run_instance(inst, briefs, results, opts, root, path, lock, out):
    """Every area of one instance, in order, until its recorded spend reaches the instance cap: the areas left are
    recorded as failures named budget. Each result is appended as soon as it exists."""
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
        if spent >= opts["instance_usd"]:
            for left in todo[i:]:
                append({"instance": n, "area": left["area"].strip(), "started": utc_now(), "model": model_id(opts["model"]),
                        "effort": opts["effort"], "settings": SETTINGS, "bare_before": "", "bare_after": "",
                        "failure": "budget", "subtype": "budget", "wall_s": 0, "cost": 0, "input_tokens": 0,
                        "output_tokens": 0, "cache_write_tokens": 0, "cache_read_tokens": 0, "turns": 0,
                        "tool_calls": 0, "model_usage": {},
                        "error": f"instance spend ${spent:.2f} reached --instance-usd {opts['instance_usd']:g}"})
            break
        rec = area_record(inst, brief, opts, env, argv, area_prompt(brief), opts["timeout"])
        spent += rec["cost"]
        append(rec)


def run(count=None, root=None, dry_run=False, briefs_path=None, questions_path=None, out=print, **limits):
    """`repro run`: start every instance's area sessions at once (one thread each, the areas of an instance in the
    briefs' order) and append each result to DIR/results.jsonl; a run again skips the areas with a result and retries
    the failed ones. `limits` are DEFAULTS' keys. With `dry_run` nothing starts: the argv, the estimate and every
    refusal are printed; returns 0, or 1 for a briefs problem. A real run raises Refused on a refusal or a briefs
    problem and returns 0 when every area has a result, else 1."""
    opts = {**DEFAULTS, **{k: v for k, v in limits.items() if v is not None}}
    if opts["effort"] not in EFFORTS:
        raise Refused(f"--effort {opts['effort']}: one of {', '.join(EFFORTS)}")
    root = Path(root) if root else default_dir()
    briefs = load_briefs(briefs_path)
    insts, rev = instances_of(root, count)
    refusals, bad = run_problems(root, insts, rev, count, briefs, questions_path)
    path = root / RESULTS
    results = read_results(path)
    areas = len(briefs)
    plan = [(i, todo_of(briefs, results, i["n"])) for i in insts]
    note = {k: opts[k] for k in ("model", "effort", "max_turns", "area_usd", "timeout")}
    note["argv"] = session_argv(opts["model"], opts["effort"], opts["max_turns"], opts["area_usd"], "MCP-CONFIG")
    record = Path(root) / RUN_RECORD
    if record.exists() and not refusals:
        old = json.loads(record.read_text(encoding="utf-8"))
        if old.get("argv") != note["argv"] or old.get("timeout") != note["timeout"] or old.get("settings") != SETTINGS:
            refusals.append(f"{record} holds other settings or limits than this run's: remove it with {path} to start over")
    if dry_run:
        out(f"repro run: {len(insts)} instance(s), {areas} area(s), dir {root}")
        out(f"settings: {SETTINGS}")
        total = 0.0
        for i, todo in plan:
            argv = session_argv(opts["model"], opts["effort"], opts["max_turns"], opts["area_usd"], i["mcp_config"])
            up = estimate(len(todo), opts["area_usd"], opts["instance_usd"])
            total += up
            out(f"instance {i['n']}: clone {i['clone']}")
            out(f"  argv: {shlex.join(argv)}")
            out(f"  areas to run: {len(todo)} of {areas}, estimate up to ${up:.2f} (--area-usd {opts['area_usd']:g} each, "
                f"no area starts once ${opts['instance_usd']:g} is recorded)")
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
    record.write_text(json.dumps({**note, "settings": SETTINGS}, indent=2) + "\n", encoding="utf-8", newline="\n")
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=len(insts)) as pool:
        futures = [pool.submit(run_instance, i, briefs, results, opts, root, path, lock, out) for i in insts]
        for f in futures:
            f.result()
    last = latest(read_results(path))
    failed = [k for i in insts for b in briefs if (k := (i["n"], b["area"].strip())) in last and last[k].get("failure")]
    spent = sum(r.get("cost") or 0 for r in read_results(path))
    out(f"repro run: {len(insts) * areas - len(failed)} of {len(insts) * areas} area(s) finished, {len(failed)} failed, "
        f"${spent:.2f} recorded in {path}")
    return 1 if failed else 0
