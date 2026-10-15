"""The research-reproducibility benchmark's isolated instances: `benchmarks.py repro setup` (stdlib only).

Each instance is a full bare copy of one pinned commit's history (DIR/originN.git, its main at REV), a working clone of
it outside the checkout (under bench_core's scratch directory) whose only remote is that bare path, a query log of mode
`off` in the clone, and an mcp-config file of its own for `claude -p --mcp-config FILE --strict-mcp-config`, so no
instance writes ~/.claude.json. `instance_env` is the session environment of an instance. This module imports bench_core
and kbpublic only (kb/_self/code.md, Layout); benchmarks.py holds the command line.
"""
import hashlib, json, os, shutil, subprocess, sys
from pathlib import Path

import kbpublic
from bench_core import HOME, isolate, no_plugin_env, scratch_dir

ADDED = "kb/public/_retrieval/repro_bench.csv"  # the file whose first commit's parent is the default REV
DOCS_MCP = Path(".claude-plugin") / "it-ops-kb-docs" / ".mcp.json"
MANIFEST = "instances.json"
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
    """The working clone of instance N: under the scratch directory, in a directory of its own for each DIR."""
    return scratch_dir() / ("repro-" + hashlib.sha1(str(Path(root).resolve()).encode("utf-8")).hexdigest()[:8]) / f"instance{n}"


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
