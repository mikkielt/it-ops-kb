"""The multi-agent benchmark's sandbox: `benchmarks.py multi setup` and `multi probe` (stdlib only).

A sandbox is a directory DIR holding one bare copy of one pinned commit (DIR/origin.git: the commit alone, no history,
and on it one base commit that empties `lane_module` in backlog.json, so the sandbox has no code lane and an item lands on
the bare as content), N agent clones of it whose only remote is that bare, and the coordination store of the agents: the
one file DIR/coord/coord.sqlite under `--coord shared`, a file of each agent's own under `--coord isolated`. Every agent's
clone has its query log `off` and an mcp-config file of its own; `agent_env` is the session environment of an agent
(bench_repro.instance_env's, with `KB_COORD_STORE` the agent's store). The clones sit under bench_core's scratch
directory, as the clones of bench_repro do, in a directory of their own for each DIR. `probe` builds a two-agent sandbox
of each coordination mode in a temporary directory, lands one `_gaps.md` commit from each clone of the shared one on its
bare through `kbgit.py sync --push` and proves the landing and the stores stayed inside the
sandbox. Nothing here starts a model or reads the network. This module imports bench_repro for its instance helpers
(kb/_self/code.md, Layout); benchmarks.py holds the command line.
"""
import hashlib, json, os, shutil, sys
from pathlib import Path

import bench_repro
import kbpublic
from bench_core import HOME, isolate, scratch_dir
from bench_repro import Refused, inside, instance_env, lock_dir, mcp_config, run_git, same_path, sh

COORDS = ("shared", "isolated")
MANIFEST = "sandbox.json"  # DIR/sandbox.json: the pinned commit and each agent's paths
BACKLOG = "backlog.json"  # the project's backlog configuration, which the sandbox's base commit changes
BASE_MESSAGE = "chore: sandbox base commit, backlog.json with no code lane"
CLAIM_KEY = "multi-probe"  # the key the probe's two agents claim in turn
GAP = ("\n## multi-probe-agent{n}\n\n- **A probe entry that multi probe commits and syncs from agent {n}.** Nothing was tried; "
       "the entry exists to be pushed to the sandbox's bare. [UNK] (topic: {topic})\n")


def default_dir():
    """_cache/bench-multi of the clone's main worktree, so a run from a linked worktree leaves it where later items find it."""
    import kbfacts
    return Path(kbfacts.clone_home()) / "_cache" / "bench-multi"


def origin_path(root):
    return Path(root) / "origin.git"


def clone_path(root, n):
    """The working clone of agent N: under the scratch directory, in a directory of its own for each DIR."""
    return scratch_dir() / ("multi-" + hashlib.sha1(str(Path(root).resolve()).encode("utf-8")).hexdigest()[:8]) / f"agent{n}"


def mcp_path(root, n):
    return clone_path(root, n) / "_private" / "mcp-config.json"


def store_path(root, coord, n):
    """The coordination store of agent N: the one file of DIR under shared, the agent's own under isolated."""
    base = Path(root) / "coord"
    return base / "coord.sqlite" if coord == "shared" else base / f"agent{n}" / "coord.sqlite"


def agent_env(root, coord, n):
    """The session environment of agent N: bench_repro.instance_env's with KB_COORD_STORE its store."""
    env = instance_env(root, n)
    env["KB_COORD_STORE"] = str(store_path(root, coord, n))
    return env


def pinned(start):
    """(sha, why) of the commit every agent starts at: START, else this checkout's HEAD. The bare holds that one commit, not its
    history (a clone made with --filter=blob:none lacks the blobs of the history, which a copy would fetch from its remote)."""
    ref = start or "HEAD"
    p = sh(["git", "rev-parse", "--verify", "-q", f"{ref}^{{commit}}"], HOME, os.environ)
    if p.returncode:
        raise Refused(f"no such commit: {ref}")
    return p.stdout.strip(), (f"--start {start}" if start else "HEAD of this checkout")


def agent_lines(root, coord, count):
    out = []
    for n in range(1, count + 1):
        out += [f"agent {n}: clone {clone_path(root, n)}", f"  mcp-config {mcp_path(root, n)} (use with --strict-mcp-config)",
                f"  KB_COORD_STORE {store_path(root, coord, n)}", f"  KB_HOST_LOCK_DIR {lock_dir(root, n)}"]
    return out


def plan_lines(root, coord, count, rev, why):
    return [f"multi setup: {count} agent(s), coord {coord}", f"dir: {root}", f"rev: {rev} ({why})", f"bare: {origin_path(root)}",
            f"base: {BASE_MESSAGE} (one commit on {rev[:12]}, the bare's main)",
            *agent_lines(root, coord, count)]


def base_commit(root, bare):
    """Put one commit on the bare's main that empties `lane_module` in backlog.json, so the sandbox has no code lane and an
    item lands on the bare as content (bl_land, unlanded_code): made in a throwaway clone, hooks skipped. The commit's sha."""
    work = Path(root) / "base-work"
    shutil.rmtree(work, ignore_errors=True)
    try:
        run_git("clone", "-q", str(bare), str(work), cwd=root)
        path = work / BACKLOG
        config = json.loads(path.read_text(encoding="utf-8"))
        config["lane_module"] = ""
        path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8", newline="\n")
        run_git("-c", "user.name=multi sandbox", "-c", "user.email=jan.kowalski@corp.example.com", "commit", "-q", "--no-verify",
                "-m", BASE_MESSAGE, "--", BACKLOG, cwd=work)
        run_git("push", "-q", "--no-verify", "origin", "HEAD:refs/heads/main", cwd=work)
        return run_git("rev-parse", "HEAD", cwd=work)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def setup(count, coord, root=None, start=None, dry_run=False, out=print):
    """Build the sandbox: print the plan and every path. Returns 0, or raises Refused. With dry_run nothing is created."""
    if count < 1:
        raise Refused("--agents needs 1 or more")
    if coord not in COORDS:
        raise Refused(f"--coord is one of {', '.join(COORDS)}")
    root = (Path(root) if root else default_dir()).resolve()
    sha, why = pinned(start)
    if dry_run:
        for ln in plan_lines(root, coord, count, sha, why):
            out(ln)
        return 0
    bare = origin_path(root)
    for d in (bare, root / "coord", *(lock_dir(root, n) for n in range(1, count + 1)),
              *(clone_path(root, n) for n in range(1, count + 1))):
        shutil.rmtree(d, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    run_git("init", "-q", "--bare", "--initial-branch=main", str(bare), cwd=root)
    run_git("fetch", "-q", "--depth", "1", "--no-tags", str(HOME), f"+{sha}:refs/heads/main", cwd=bare)
    base = base_commit(root, bare)
    for n in range(1, count + 1):
        clone = clone_path(root, n)
        clone.parent.mkdir(parents=True, exist_ok=True)
        run_git("clone", "-q", str(bare), str(clone), cwd=clone.parent)
        isolate(clone, "off", bare)
        p = sh([sys.executable, str(clone / "_tools" / "kbgit.py"), "install-hooks"], clone, agent_env(root, coord, n))
        if p.returncode:
            raise Refused(f"agent {n}: install-hooks exited {p.returncode}: {(p.stdout + p.stderr).strip()[-300:]}")
        cfg = mcp_config(clone)
        cfg["mcpServers"]["kb"]["env"] = {"KB_COORD_STORE": str(store_path(root, coord, n))}
        mcp_path(root, n).write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8", newline="\n")
        lock_dir(root, n).mkdir(parents=True, exist_ok=True)
        store_path(root, coord, n).parent.mkdir(parents=True, exist_ok=True)
    manifest = {"rev": sha, "base": base, "coord": coord, "bare": str(bare), "agents": [
        {"n": n, "clone": str(clone_path(root, n)), "mcp_config": str(mcp_path(root, n)),
         "coord_store": str(store_path(root, coord, n)), "lock_dir": str(lock_dir(root, n))} for n in range(1, count + 1)]}
    (root / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    for ln in plan_lines(root, coord, count, sha, why):
        out(ln)
    out(f"manifest: {root / MANIFEST}")
    return 0


def remove(root):
    """Remove a sandbox: its directory and the directory its clones sit in."""
    shutil.rmtree(clone_path(root, 1).parent, ignore_errors=True)
    shutil.rmtree(root, ignore_errors=True)


def store_checks(root, coord):
    """The (name, ok, detail) of each property of the stores of the sandbox at `root`: the agents' KB_COORD_STORE follow
    `coord`, their mcp-configs name it, and a claim of one key by each agent in turn is refused to the second under
    shared and granted under isolated, in the file KB_COORD_STORE names."""
    agents = json.loads((Path(root) / MANIFEST).read_text(encoding="utf-8"))["agents"]
    stores = [a["coord_store"] for a in agents]
    want = 1 if coord == "shared" else len(agents)
    res = [(f"{coord}: the agents' KB_COORD_STORE are {want} file(s) inside the sandbox",
            len(set(stores)) == want and all(inside(s, root) for s in stores),
            ", ".join(str(Path(s).relative_to(Path(root).resolve())) for s in dict.fromkeys(stores)))]
    envs = [agent_env(root, coord, a["n"]) for a in agents]
    res.append((f"{coord}: each agent's environment names its manifest store",
                [e["KB_COORD_STORE"] for e in envs] == stores, "env and manifest"))
    seen = [json.loads(Path(a["mcp_config"]).read_text(encoding="utf-8"))["mcpServers"]["kb"].get("env", {}).get("KB_COORD_STORE")
            for a in agents]
    res.append((f"{coord}: each agent's mcp-config names its store", seen == stores, "mcp-config env and manifest"))
    codes = []
    for a, env in zip(agents, envs):
        clone = a["clone"]
        p = sh([sys.executable, str(Path(clone) / "_tools" / "coord.py"), "claim", CLAIM_KEY, "--ttl", "60", "--holder",
                f"agent{a['n']}"], clone, env)
        codes.append(p.returncode)
    expect = [0] + [1] * (len(agents) - 1) if coord == "shared" else [0] * len(agents)
    res.append((f"{coord}: a claim of one key by each agent in turn exits {expect}", codes == expect, f"exits {codes}"))
    res.append((f"{coord}: the store files exist", all(Path(s).is_file() for s in stores), f"{sum(Path(s).is_file() for s in stores)} of {len(stores)}"))
    return res


def ref_sha(ref):
    """The sha of `ref` in this clone, "" when it is not there."""
    p = sh(["git", "rev-parse", "--verify", "-q", ref], HOME, os.environ)
    return p.stdout.strip() if p.returncode == 0 else ""


def on_ref(sha, repo, ref):
    """True when commit `sha` is in the history of `ref` of `repo` (False when the object is not there)."""
    if sh(["git", "cat-file", "-e", f"{sha}^{{commit}}"], repo, os.environ).returncode:
        return False
    return sh(["git", "merge-base", "--is-ancestor", sha, ref], repo, os.environ).returncode == 0


def commit_gap(root, coord, a):
    """Append agent A's _gaps.md entry in its clone and commit it: the commit's sha."""
    clone, env = Path(a["clone"]), agent_env(root, coord, a["n"])
    topic = next(f"{x.parent.name}/{x.stem}" for x in sorted((clone / "kb" / "public").glob("*/*.md"))
                 if not x.name.startswith("_"))  # a gap names a topic the root has
    with open(clone / "kb" / "public" / "_gaps.md", "a", encoding="utf-8", newline="\n") as f:
        f.write(GAP.format(n=a["n"], topic=topic))
    run_git("add", "kb/public/_gaps.md", cwd=clone)
    p = sh(["git", "commit", "-q", "-m", f"docs(kb): multi probe gap of agent {a['n']}"], clone, env)
    if p.returncode:
        raise Refused(f"agent {a['n']}'s commit exited {p.returncode}: {(p.stdout + p.stderr).strip()[-300:]}")
    return run_git("rev-parse", "HEAD", cwd=clone)


def sync_push(root, coord, a, out):
    """Run `kbgit.py sync --push` in agent A's clone under its environment: the exit code."""
    clone, env = Path(a["clone"]), agent_env(root, coord, a["n"])
    if os.environ.get("KB_SYNC_NO_TESTS"):  # the tool's own tests skip the gate's test run, as repro check does
        env["KB_SYNC_NO_TESTS"] = os.environ["KB_SYNC_NO_TESTS"]
    p = sh([sys.executable, str(clone / "_tools" / "kbgit.py"), "sync", "--push"], clone, env)
    if p.returncode:
        for ln in (p.stdout + p.stderr).strip().splitlines()[-15:]:
            out(f"  agent {a['n']} sync: {ln}")
    return p.returncode


def landing_checks(root, coord, out):
    """Land one _gaps.md commit from each of the first two agents of the sandbox at `root` on its bare through `kbgit.py
    sync --push`, the second after a rebase; the (name, ok, detail) of each property of the landing."""
    manifest = json.loads((Path(root) / MANIFEST).read_text(encoding="utf-8"))
    first, second = manifest["agents"][:2]
    bare = Path(manifest["bare"])
    ref = f"refs/remotes/{kbpublic.integration_remote(HOME)}/main"
    start = run_git("rev-parse", "refs/heads/main", cwd=bare)
    commit_gap(root, coord, first)
    code1 = sync_push(root, coord, first, out)
    mid = run_git("rev-parse", "refs/heads/main", cwd=bare)
    planned = commit_gap(root, coord, second)
    code2 = sync_push(root, coord, second, out)
    tip = run_git("rev-parse", "refs/heads/main", cwd=bare)
    heads = [run_git("rev-parse", "HEAD", cwd=a["clone"]) for a in (first, second)]
    res = [("the first agent's sync --push exits 0 and moves the bare's main", code1 == 0 and mid != start,
            f"exit {code1}, main {start[:12]} -> {mid[:12]}"),
           ("the second agent's sync --push exits 0 and moves the bare's main", code2 == 0 and tip != mid,
            f"exit {code2}, main {mid[:12]} -> {tip[:12]}"),
           ("both agents' commits are on the bare's main", all(on_ref(h, bare, "refs/heads/main") for h in heads),
            f"heads {heads[0][:12]} {heads[1][:12]}, main {tip[:12]}"),
           ("the second agent's commit was rebased onto the first's", heads[1] != planned and on_ref(mid, second["clone"], "HEAD"),
            f"commit {planned[:12]} -> {heads[1][:12]}")]
    res.append(("neither commit reached the clone's own origin/main ref",  # the ref moves when the real origin is fetched or pushed
                not any(on_ref(h, HOME, ref) for h in heads), f"{ref} {ref_sha(ref)[:12] or '(none)'}"))
    remotes = [(run_git("remote", cwd=a["clone"]).split(), run_git("config", "--get", "remote.origin.url", cwd=a["clone"]))
               for a in (first, second)]
    lanes = [json.loads((Path(a["clone"]) / BACKLOG).read_text(encoding="utf-8")).get("lane_module") for a in (first, second)]
    res.append(("the sandbox has no code lane: lane_module is empty in each clone's backlog.json", lanes == ["", ""], f"lane_module {lanes}"))
    res.append(("each agent's only remote is the sandbox's bare",
                all(names == ["origin"] and same_path(url, bare) for names, url in remotes), f"origin is {bare.name}"))
    return res


def probe(out=print):
    """Build a two-agent sandbox of each coordination mode in a temporary directory, check its stores, and in the shared
    one land a commit from each clone (landing_checks); remove the sandboxes. Returns 0 when every property holds, 1 when
    one fails, or raises Refused."""
    base = scratch_dir() / f"multi-probe-{os.getpid()}"
    res = []
    try:
        for coord in COORDS:
            root = base / coord
            setup(2, coord, root, out=lambda line: None)
            res += store_checks(root, coord)
            if coord == "shared":
                res += landing_checks(root, coord, out)
    finally:
        for coord in COORDS:
            remove(base / coord)
        shutil.rmtree(base, ignore_errors=True)
    for name, ok, detail in res:
        out(f"{'ok' if ok else 'FAIL'}: {name} ({detail})")
    failed = [name for name, ok, _ in res if not ok]
    out("multi probe: " + ("the sandbox held" if not failed else f"{len(failed)} failed: " + "; ".join(failed)))
    return 1 if failed else 0
