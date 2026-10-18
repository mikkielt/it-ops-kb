"""The multi-agent benchmark's sandbox, plan and run: `benchmarks.py multi setup`, `multi probe`, `multi inputs` and `multi run`
(stdlib only).

A sandbox is a directory DIR holding one bare copy of one pinned commit (DIR/origin.git: the commit alone, no history,
and on it one base commit that empties `lane_module` in backlog.json, so the sandbox has no code lane and an item lands on
the bare as content), N agent clones of it whose only remote is that bare, and the coordination store of the agents: the
one file DIR/coord/coord.sqlite under `--coord shared`, a file of each agent's own under `--coord isolated`. Every agent's
clone has its query log `off` and an mcp-config file of its own; `agent_env` is the session environment of an agent
(bench_repro.instance_env's, with `KB_COORD_STORE` the agent's store). The clones sit under bench_core's scratch
directory, as the clones of bench_repro do, in a directory of their own for each DIR. `probe` builds a two-agent sandbox
of each coordination mode in a temporary directory, lands one `_gaps.md` commit from each clone of the shared one on its
bare through `kbgit.py sync --push` and proves the landing and the stores stayed inside the sandbox. Nothing but `execute`
(`multi run` without `--dry-run`) starts a model or reads the network, and under `--replay` it starts bench_replay.py, a
scripted stand-in for `claude`, instead: no model call. This module imports bench_repro for its instance helpers
(kb/_self/code.md, Layout); benchmarks.py holds the command line.
"""
import base64, hashlib, json, os, re, shlex, shutil, signal, subprocess, sys, threading, time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import agent_bench
import bench_pool
import bench_repro
import kbpublic
from bench_core import HOME, PRICE, RESULTS, isolate, pinned, read_rows, resolve_model, scratch_dir, spent_run, transcript
from bench_repro import (Refused, failure_of, inside, instance_env, lock_dir, mcp_config, reset_clone, run_git, same_path, sh,
                         utc_now)

COORDS = ("shared", "isolated")
MANIFEST = "sandbox.json"  # DIR/sandbox.json: the pinned commit and each agent's paths
BACKLOG = "backlog.json"  # the project's backlog configuration, which the sandbox's base commit changes
BASE_MESSAGE = "chore: sandbox base commit, backlog.json with no code lane"
CLAIM_KEY = "multi-probe"  # the key the probe's two agents claim in turn
INPUTS = "kb/_self/reports/multi_bench.csv"  # the frozen inputs of the scenarios, one row per agent and input
INPUT_COLUMNS = ("scenario", "agent", "role", "input")
SCENARIOS = ("lookups", "research", "mixed")
ROLES = ("lookup", "research", "code")
SPEC_KEYS = ("title", "goal", "touches", "check", "gate")  # the keys of a code agent's input, an item spec in json
ITEM_DIR = "kb/_self/backlog"  # where setup writes a planted item: bl_base's item_dir of this project
TOOL_SETS = {"kb": ["mcp__kb"], "files": ["Read", "Grep", "Glob"]}  # --tools: the lookup agent's tools
MANAGERS = ("code", "session")  # --manager: this tool starts the agents, or a model session does
DEFAULT_MODELS = {"lookup": "haiku-5-5", "research": "sonnet-5-5", "code": "sonnet-5-5"}
MANAGER_MODEL = "sonnet-5-5"
RUN_RESULTS = "results.jsonl"  # DIR/results.jsonl: one json line per agent of a run
BIN = "bin"  # DIR/bin: the claude wrapper dispatch's worker starts through
OPERATOR = "operator"  # who the harness answers a gate as
PACK_BUDGET = 1200  # kb_pack's default budget in tokens; its limits are the next two
PACK_LIMITS = (200, 6000)
LOOKUP_LIMITS = {"max_turns": 40, "usd": 3.0}  # the turns and dollars one lookup agent's session may use
CODE_ITEM_USD = 1.0  # what one code item costs on RECORDED_MODEL: about the mean of the usage rows of a worker's session
RECORDED_MODEL = "claude-sonnet-5-5"  # the model the recorded repro rows and the code figure were taken on
DEFAULT_USAGE = {"input_tokens": 120, "output_tokens": 30000, "cache_creation_input_tokens": 150000, "cache_read_input_tokens": 6000000,
                 "num_turns": 80}  # what a replayed code agent prints, and a role with no recorded row: about one worker session
REPLAY = "_tools/bench_replay.py"  # the scripted stand-in of `--replay`, run from this checkout in the agents' clones
POOL_ARM = re.compile(r"[a-z]+-\d+(?:-\d+)*(?::default)?(/session)?")  # a kb arm of the pool at its default effort
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


def plan_lines(root, coord, count, rev, why, items=()):
    return [f"multi setup: {count} agent(s), coord {coord}", f"dir: {root}", f"rev: {rev} ({why})", f"bare: {origin_path(root)}",
            f"base: {base_message(items)} (one commit on {rev[:12]}, the bare's main)",
            *([f"planted sprint {items[0][2]['sprint']}, started, with its review story and the items below"] if items else []),
            *(f"planted item {iid} for {agent}: {item['title']}" for agent, iid, item in items),
            *agent_lines(root, coord, count)]


def base_message(items):
    return BASE_MESSAGE + (f" and {len(items)} planted backlog item(s)" if items else "")


def base_commit(root, bare, items=(), scenario=None):
    """Put one commit on the bare's main that empties `lane_module` in backlog.json, so the sandbox has no code lane and an
    item lands on the bare as content (bl_land, unlanded_code), and adds each of `items` ((agent, id, item) of `planted`) as an
    item file under ITEM_DIR, with the started sprint of `scenario` they belong to: made in a throwaway clone, hooks skipped.
    The commit's sha."""
    work = Path(root) / "base-work"
    shutil.rmtree(work, ignore_errors=True)
    try:
        run_git("clone", "-q", str(bare), str(work), cwd=root)
        path = work / BACKLOG
        config = json.loads(path.read_text(encoding="utf-8"))
        config["lane_module"] = ""
        path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8", newline="\n")
        files = [BACKLOG]
        if items:
            sid = items[0][2]["sprint"]
            rel = f"{ITEM_DIR}/{sid}.json"
            (work / rel).write_text(json.dumps(sprint_of(sid, scenario), ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
            review = review_of(sid)
            (work / ITEM_DIR / f"{review['id']}.json").write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
            files += [rel, f"{ITEM_DIR}/{review['id']}.json"]
        for _, iid, item in items:
            rel = f"{ITEM_DIR}/{iid}.json"
            (work / rel).write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
            files.append(rel)
        run_git("add", "--", *files, cwd=work)
        run_git("-c", "user.name=multi sandbox", "-c", "user.email=jan.kowalski@corp.example.com", "commit", "-q", "--no-verify",
                "-m", base_message(items), cwd=work)
        run_git("push", "-q", "--no-verify", "origin", "HEAD:refs/heads/main", cwd=work)
        return run_git("rev-parse", "HEAD", cwd=work)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def setup(count, coord, root=None, start=None, dry_run=False, out=print, scenario=None):
    """Build the sandbox: print the plan and every path. Returns 0, or raises Refused. With dry_run nothing is created. With a
    `scenario` the base commit also plants the backlog item of each of its code agents (`planted`); `count` None is the
    scenario's agent count."""
    if scenario is not None and scenario not in SCENARIOS:
        raise Refused(f"no scenario {scenario}; one of {', '.join(SCENARIOS)}")
    items = planted(scenario) if scenario else []
    if count is None and scenario:
        count = len(agents_of(load_inputs(), scenario))
    if count is None or count < 1:
        raise Refused("--agents needs 1 or more")
    if coord not in COORDS:
        raise Refused(f"--coord is one of {', '.join(COORDS)}")
    root = (Path(root) if root else default_dir()).resolve()
    sha, why = pinned(start)
    if dry_run:
        for ln in plan_lines(root, coord, count, sha, why, items):
            out(ln)
        return 0
    bare = origin_path(root)
    for d in (bare, root / "coord", *(lock_dir(root, n) for n in range(1, count + 1)),
              *(clone_path(root, n) for n in range(1, count + 1))):
        shutil.rmtree(d, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    run_git("init", "-q", "--bare", "--initial-branch=main", str(bare), cwd=root)
    run_git("fetch", "-q", "--depth", "1", "--no-tags", str(HOME), f"+{sha}:refs/heads/main", cwd=bare)
    base = base_commit(root, bare, items, scenario)
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
    manifest = {"rev": sha, "base": base, "coord": coord, "bare": str(bare), "scenario": scenario,
                "items": {agent: iid for agent, iid, _ in items}, "agents": [
        {"n": n, "clone": str(clone_path(root, n)), "mcp_config": str(mcp_path(root, n)),
         "coord_store": str(store_path(root, coord, n)), "lock_dir": str(lock_dir(root, n))} for n in range(1, count + 1)]}
    (root / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    for ln in plan_lines(root, coord, count, sha, why, items):
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


def sync_push(root, coord, a, out, no_tests=False):
    """Run `kbgit.py sync --push` in agent A's clone under its environment: the exit code. `no_tests` skips the gate's test run
    (a replay's), as the KB_SYNC_NO_TESTS of the caller's own environment does."""
    clone, env = Path(a["clone"]), agent_env(root, coord, a["n"])
    if os.environ.get("KB_SYNC_NO_TESTS") or no_tests:  # the tool's own tests skip the gate's test run, as repro check does
        env["KB_SYNC_NO_TESTS"] = os.environ.get("KB_SYNC_NO_TESTS", "1")
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


# ------------------------------------------------------------------------------------------------------- the inputs

def load_inputs(path=None):
    """The rows of the inputs file (INPUTS, or the csv at `path`) as dicts of INPUT_COLUMNS, in file order; [] when it is missing."""
    return [{c: r.get(c, "") for c in INPUT_COLUMNS} for r in bench_repro.read_csv(path or HOME / INPUTS)]


def agents_of(rows, scenario):
    """[{"agent", "role", "inputs"}] of the agents of `scenario`, in the order the rows first name them."""
    out = OrderedDict()
    for r in rows:
        if r["scenario"] == scenario:
            out.setdefault(r["agent"], {"agent": r["agent"], "role": r["role"], "inputs": []})["inputs"].append(r["input"])
    return list(out.values())


def pool_questions():
    """{id: question} of the rows of the pool file and the evaluation file, which a lookup agent's input may name."""
    out = {r["id"]: r["question"] for r in bench_repro.read_csv(HOME / bench_pool.EVAL_FILE)}
    out.update({r["id"]: bench_pool.question_of(r) for r in bench_repro.read_csv(HOME / bench_pool.PUBLIC_FILE)})
    return out


def spec_of(text):
    """The item spec a code agent's input holds (json), or a string naming why it is none."""
    try:
        spec = json.loads(text)
    except ValueError as e:
        return f"not json ({e})"
    return spec if isinstance(spec, dict) else "not a json object"


def spec_problems(spec):
    """One phrase per defect of an item spec: a missing or empty title or goal, touches that are no list of relative paths, a
    check that is no argv, a gate without a question, two options and a recommendation that is one of them."""
    out = [f"no {k}" for k in ("title", "goal") if not str(spec.get(k) or "").strip()]
    touches = spec.get("touches")
    if not isinstance(touches, list) or not touches or not all(
            isinstance(t, str) and t and not t.startswith("/") and ".." not in Path(t).parts for t in touches):
        out.append("touches is no list of relative paths")
    check = spec.get("check")
    if not isinstance(check, list) or not check or not all(isinstance(c, str) for c in check):
        out.append("check is no argv")
    gate = spec.get("gate")
    if not isinstance(gate, dict):
        return out + ["no gate"]
    if not str(gate.get("question") or "").strip():
        out.append("the gate has no question")
    options = gate.get("options")
    if not isinstance(options, list) or len(options) < 2 or not all(isinstance(o, str) and o for o in options):
        out.append("the gate has no two options")
    elif gate.get("recommendation") not in options:
        out.append("the gate's recommendation is none of its options")
    return out + [f"unknown key {k}" for k in spec if k not in SPEC_KEYS]


def input_problems(rows, questions, areas):
    """One line per row whose scenario, role or input does not resolve: a lookup's input is the id of a pool or evaluation
    row (`questions`), a research agent's the area of a brief (`areas`), a code agent's an item spec (`spec_problems`); an
    agent named under two roles is one too."""
    out, roles = [], {}
    for n, r in enumerate(rows, 1):
        label = f"row {n} ({r['scenario']}/{r['agent']}, {r['role']})"
        if r["scenario"] not in SCENARIOS:
            out.append(f"{label}: scenario is none of {', '.join(SCENARIOS)}")
        if not r["agent"].strip():
            out.append(f"{label}: no agent")
        elif roles.setdefault((r["scenario"], r["agent"]), r["role"]) != r["role"]:
            out.append(f"{label}: the agent has another role in an earlier row")
        if r["role"] not in ROLES:
            out.append(f"{label}: role is none of {', '.join(ROLES)}")
        elif r["role"] == "lookup" and r["input"] not in questions:
            out.append(f"{label}: input {r['input']!r} is the id of no row of {bench_pool.PUBLIC_FILE} or {bench_pool.EVAL_FILE}")
        elif r["role"] == "research" and r["input"] not in areas:
            out.append(f"{label}: input {r['input']!r} is the area of no row of {bench_repro.BRIEFS}")
        elif r["role"] == "code":
            spec = spec_of(r["input"])
            for why in [spec] if isinstance(spec, str) else spec_problems(spec):
                out.append(f"{label}: item spec {why}")
    return out


def inputs(path=None, out=print):
    """`multi inputs`: check the frozen inputs against the pool, the evaluation rows and the briefs; print each problem.
    Returns 0 when every row resolves, else 1."""
    rows = load_inputs(path)
    name = path or INPUTS
    if not rows:
        out(f"FAIL: no rows: {name} is missing or empty")
        return 1
    problems = input_problems(rows, pool_questions(), {b["area"].strip() for b in bench_repro.load_briefs()})
    for ln in problems:
        out(f"FAIL: {ln}")
    shapes = ", ".join(f"{s} {len(agents_of(rows, s))} agent(s)" for s in SCENARIOS)
    out("multi inputs: " + (f"{len(problems)} problem(s)" if problems else f"every one of {len(rows)} rows resolves ({shapes})"))
    return 1 if problems else 0


# -------------------------------------------------------------------------------------------------- planted items

def item_id(scenario, agent):
    """The id of the backlog item planted for a code agent: ST- and 8 base32 characters of the hash of the two names."""
    return "ST-" + base64.b32encode(hashlib.sha1(f"{scenario}/{agent}".encode("utf-8")).digest()[:5]).decode().lower()


def sprint_id(scenario):
    """The id of the sprint planted with a scenario's code items: SP- and 8 base32 characters of the hash of the scenario."""
    return "SP-" + base64.b32encode(hashlib.sha1(f"{scenario}/sprint".encode("utf-8")).digest()[:5]).decode().lower()


def sprint_of(sid, scenario):
    """The started sprint (a dict, in the field order of an item file) the planted code items belong to: a commit's `KB-Work`
    names only items of a started sprint (kbgit.py check-trailers), so a worker's commit passes the sandbox's hooks."""
    return {"id": sid, "kind": "sprint", "title": f"The planted code items of the {scenario} scenario", "status": "active",
            "goal": f"The code items of the {scenario} scenario of the multi-agent benchmark are worked and landed in this sandbox.",
            "gates": [{"id": "start", "kind": "blocking", "question": "Approve this sprint's goal and committed items?",
                       "options": ["approve", "change", "cancel"], "recommendation": "approve", "answer": "approve", "by": OPERATOR}]}


def review_of(sid):
    """The review story a sprint needs (backlog.py check): a draft of the sprint, which nothing in a sandbox works."""
    rid = "ST-" + base64.b32encode(hashlib.sha1(f"{sid}/review".encode("utf-8")).digest()[:5]).decode().lower()
    return {"id": rid, "kind": "story", "title": f"Review sprint: {sid}", "status": "draft", "sprint": sid, "review": True,
            "priority": "P1", "rank": 999999, "goal": "Every committed item is done or dropped.",
            "checks": [{"run": ["python3", "_tools/backlog.py", "check"]}]}


def item_of(spec, iid, sprint=None):
    """The backlog item (a dict, in the field order of an item file) an item spec stands for: a ready story with the spec's
    check, touches and one blocking gate whose every option names this item as the work that carries it out, in `sprint`."""
    gate = spec["gate"]
    return {"id": iid, "kind": "story", "title": spec["title"], "status": "todo", **({"sprint": sprint} if sprint else {}),
            "priority": "P2", "rank": 0, "goal": spec["goal"],
            "checks": [{"run": spec["check"]}], "touches": spec["touches"],
            "gates": [{"id": "g1", "kind": "blocking", "question": gate["question"], "options": gate["options"],
                       "recommendation": gate["recommendation"], "do": {o: iid for o in gate["options"]}, "class": "design"}]}


def planted(scenario, rows=None):
    """[(agent, item id, item)] of the code agents of `scenario`: the items `setup --scenario` plants."""
    out = []
    for a in agents_of(rows if rows is not None else load_inputs(), scenario):
        if a["role"] == "code":
            spec = spec_of(a["inputs"][0])
            if isinstance(spec, str) or spec_problems(spec):
                raise Refused(f"the item spec of {scenario}/{a['agent']} does not resolve: python3 _tools/benchmarks.py multi inputs")
            iid = item_id(scenario, a["agent"])
            out.append((a["agent"], iid, item_of(spec, iid, sprint_id(scenario))))
    return out


# ----------------------------------------------------------------------------------------------- the plan and its cost

def parse_models(spec):
    """{role: model} of `--model`: ROLE=MODEL pairs, comma separated, over DEFAULT_MODELS (and `manager`), or one MODEL for every
    role. Raises Refused on a role or a model it does not know."""
    models = dict(DEFAULT_MODELS, manager=MANAGER_MODEL)
    for part in [p.strip() for p in (spec or "").split(",") if p.strip()]:
        role, sep, model = part.partition("=")
        if not sep:
            role, model = None, part
        if role is not None and role not in models:
            raise Refused(f"--model {part}: the roles are {', '.join(models)}")
        if model not in agent_bench.MODEL:
            raise Refused(f"--model {part}: no model {model}; one of {', '.join(agent_bench.MODEL)}")
        for r in [role] if role else list(DEFAULT_MODELS):
            models[r] = model
    return models


def model_price_id(model):
    """The pinned model id `model` is priced at (bench_core.resolve_model); Refused when bench_core.PRICE has none."""
    mid = resolve_model(agent_bench.MODEL[model])
    if mid not in PRICE:
        raise Refused(f"no price for model {mid!r}: add it to bench_core.PRICE")
    return mid


def price_ratio(mid):
    """The input list price per MTok of `mid`'s first tier over RECORDED_MODEL's: how a recorded figure scales to another model."""
    return PRICE[mid][0][1] / PRICE[RECORDED_MODEL][0][1]


def recorded_means(rows):
    """What the recorded rows give the estimate: {model id: (mean cost of one question, runs, session shape)} of the
    pool's kb arms at their default effort (the session shape's where a model has it), and the mean cost and wall seconds of
    the `repro` rows of an area, a stopped area counted at its zero. `rows` are the results file's."""
    pool = {}
    for shape in (False, True):
        for r in rows:
            m = POOL_ARM.fullmatch(r["arm"])
            if r["scenario"] == "pool" and r["metric"] == "cost" and r["case"] == "all" and m and bool(m.group(1)) == shape:
                runs = float(r["runs"] or 0)
                tot, n = pool.get((r["model"], shape), (0.0, 0.0))
                pool[(r["model"], shape)] = (tot + float(r["value"]) * runs, n + runs)
    out = {}
    for (mid, shape), (tot, n) in pool.items():
        if n and (shape or mid not in out):
            out[mid] = (tot / n, int(n), shape)
    repro = {m: [float(r["value"]) for r in rows if r["scenario"] == "repro" and r["metric"] == m] for m in ("cost", "wall_s")}
    return {"pool": out, "repro": {m: sum(v) / len(v) for m, v in repro.items() if v}, "repro_runs": len(repro["cost"])}


def recorded_usage(rows, mid):
    """{role: {usage key: mean}} of what a replayed agent prints as its usage: for a lookup agent the mean of one question of the
    pool's kb arms at their default effort (`mid`'s cell, else RECORDED_MODEL's), for a research agent the mean of one `repro`
    area (a stopped area at its zero), as `recorded_means` selects them; a code agent has no recorded row, and
    a role whose rows are missing, so both take DEFAULT_USAGE. `rows` are the results file's."""
    keys = {"input": "input_tokens", "out": "output_tokens", "cache_write": "cache_creation_input_tokens",
            "cache_read": "cache_read_input_tokens", "turns": "num_turns"}

    def mean(sel, total=False):
        """The means of `sel`'s rows; `total`: the pool's `input` counts the cache tokens too, so they are taken off."""
        got = {}
        for r in sel:
            if r["metric"] in keys and r["value"] != "":
                tot, runs = got.get(r["metric"], (0.0, 0.0))
                weight = float(r["runs"] or 1)
                got[r["metric"]] = (tot + float(r["value"]) * weight, runs + weight)
        if len(got) < len(keys):
            return None
        out = {keys[m]: round(tot / runs) for m, (tot, runs) in got.items() if runs}
        if total:
            out["input_tokens"] -= out["cache_creation_input_tokens"] + out["cache_read_input_tokens"]
        return {key: max(1, val) for key, val in out.items()}

    pool = [r for r in rows if r["scenario"] == "pool" and r["case"] == "all" and POOL_ARM.fullmatch(r["arm"])]
    cell = [r for r in pool if r["model"] == mid] or [r for r in pool if r["model"] == RECORDED_MODEL]
    return {"lookup": mean(cell, True) or DEFAULT_USAGE, "research": mean([r for r in rows if r["scenario"] == "repro"]) or DEFAULT_USAGE,
            "code": DEFAULT_USAGE}


def question_usd(means, mid):
    """(US dollars of one lookup question on `mid`, its basis): the recorded mean of that model's pool cell, else the nearest
    recorded model's scaled by the input price."""
    if mid in means["pool"]:
        usd, runs, shape = means["pool"][mid]
        return usd, f"the mean of {runs} recorded pool runs of {mid} at the default effort, {'session' if shape else 'fresh'} shape"
    ref = means["pool"].get(RECORDED_MODEL)
    if not ref:
        raise Refused(f"no recorded pool cost for {mid} or {RECORDED_MODEL}: run the pool scenario first")
    return ref[0] * price_ratio(mid), f"the recorded mean of {RECORDED_MODEL} x {price_ratio(mid):.3g} (the input price ratio)"


def lookup_prompt(questions, tools, budget):
    """The prompt of a lookup agent's session: its questions, answered one after the other from the kb's tools or from files."""
    how = (f"Answer from the kb: call kb_pack first, with budget {budget} tokens, and cite path:line and the source url of each fact."
           if tools == "kb" else "Answer from the files of this clone with Read, Grep and Glob (no kb tool), citing the file and line of each fact.")
    return how + " Answer the questions one after the other.\n\n" + "\n".join(f"{n}. {q}" for n, q in enumerate(questions, 1)) + "\n"


def session_argv(model, max_turns, usd, mcp, tools=None):
    """The argv of one agent's session: bench_repro.session_argv's (the two plugins off, the agent's own mcp-config), at effort
    high; with `tools` ("kb" or "files"), the lookup agent's: no effort flag and its allowed tools."""
    argv = bench_repro.session_argv(model, bench_repro.DEFAULTS["effort"], max_turns, usd, mcp)
    if tools:
        i = argv.index("--effort")
        del argv[i:i + 2]  # the lookup agent runs at the model's default effort, as the pool cells its estimate reads do
        argv += ["--allowedTools", *TOOL_SETS[tools]]
        if tools == "files":
            argv += ["--disallowedTools", "mcp__kb"]
    return argv


def dispatch_argv(root, n, iid, model, max_turns):
    """The argv that makes agent N's code item's worker: `backlog.py dispatch` in the agent's clone, which starts a headless
    session on the item's brief (the worker's own claude argv is dispatch's; the wrapper in DIR/bin adds the session
    settings, the agent's mcp-config and the dollar cap)."""
    return [sys.executable, str(clone_path(root, n) / "_tools" / "backlog.py"), "dispatch", iid, "--model", bench_repro.model_id(model),
            "--max-turns", str(max_turns)]


def agent_plan(agent, scenario, n, root, knobs, models, means, questions, briefs):
    """The plan of one agent, the Nth of its scenario: its role, model, argv, prompt, coordination store and estimate. Raises Refused."""
    role, mcp = agent["role"], mcp_path(root, n)
    model, mid = models[role], model_price_id(models[role])
    d = bench_repro.DEFAULTS
    plan = {"agent": agent["agent"], "role": role, "model": model, "mid": mid, "store": store_path(root, knobs["coord"], n),
            "wall": None, "n": n, "turns": d["max_turns"], "cap": d["area_usd"]}
    if role == "lookup":
        qs = [questions[i] for i in agent["inputs"]]
        plan["argv"] = session_argv(model, LOOKUP_LIMITS["max_turns"], LOOKUP_LIMITS["usd"], mcp, knobs["tools"])
        plan["turns"], plan["cap"] = LOOKUP_LIMITS["max_turns"], LOOKUP_LIMITS["usd"]
        plan["prompt"] = lookup_prompt(qs, knobs["tools"], knobs["pack_budget"])
        one, why = question_usd(means, mid)
        plan["usd"], plan["basis"] = one * len(qs), f"{len(qs)} question(s) x ${one:.4f}, {why}"
        plan["what"] = f"{len(qs)} question(s): {', '.join(agent['inputs'])}"
        plan["questions"] = qs
    elif role == "research":
        brief = next(b for b in briefs if b["area"].strip() == agent["inputs"][0])
        plan["argv"] = session_argv(model, d["max_turns"], d["area_usd"], mcp)
        plan["prompt"] = bench_repro.area_prompt(brief)
        cost = means["repro"].get("cost")
        if cost is None:
            raise Refused("no recorded repro rows: the estimate of a research agent reads them")
        plan["usd"] = cost * price_ratio(mid)
        plan["basis"] = (f"the mean cost of {means['repro_runs']} recorded repro area runs (${cost:.2f}, a stopped one at its zero)"
                         + (f" x {price_ratio(mid):.3g} (the input price ratio)" if mid != RECORDED_MODEL else ""))
        plan["wall"] = means["repro"].get("wall_s") if mid == RECORDED_MODEL else None
        plan["what"] = f"area {agent['inputs'][0]}"
        plan["area"] = agent["inputs"][0]
    else:
        spec = spec_of(agent["inputs"][0])
        iid = item_id(scenario, agent["agent"])
        plan["item"] = iid
        plan["argv"] = dispatch_argv(root, n, iid, model, d["max_turns"])
        plan["prompt"] = f"the brief `backlog.py brief {iid}` prints, on the stdin of the worker `dispatch` starts\n"
        plan["usd"] = CODE_ITEM_USD * price_ratio(mid)
        plan["basis"] = f"about ${CODE_ITEM_USD:.2f} for one code item on {RECORDED_MODEL}" + (
            f" x {price_ratio(mid):.3g} (the input price ratio)" if mid != RECORDED_MODEL else "")
        plan["what"] = f"item {iid} ({spec['title']}), touches {', '.join(spec['touches'])}"
    return plan


def replay_argv(plan, usage, k):
    """The argv that stands in for plan's `claude` session under --replay: bench_replay.py of this checkout with the planted usage
    (a lookup agent's scaled to its questions) and the plan's estimate as the cost. A code agent's is made by the wrapper in
    DIR/bin, which `dispatch` starts in place of claude (`write_wrapper`), so its argv stays the dispatch's."""
    n = len(plan.get("questions", [])) or 1
    planted = {key: val * n for key, val in usage[plan["role"]].items()} if plan["role"] == "lookup" else usage[plan["role"]]
    plan["usage"], plan["cost"] = planted, plan["usd"]
    if plan["role"] == "code":
        return plan["argv"]
    argv = [sys.executable, str(HOME / REPLAY), plan["role"], "--usage", json.dumps(planted), "--cost", f"{plan['usd']:.4f}",
            "--holder", f"agent{plan['n']}"]
    if plan["role"] == "lookup":
        return argv + ["--budget", str(k["pack_budget"])] + [x for q in plan["questions"] for x in ("--question", q)]
    return argv + ["--area", plan["area"]]


def money(usd):
    return f"${usd:.2f}" if usd >= 0.1 else f"${usd:.3f}"


def run(scenario, root=None, dry_run=False, knobs=None, out=print):
    """`multi run SCENARIO`: with `dry_run`, print each agent's role, model, argv and coordination store, the knob values and
    an estimate in US dollars, and create nothing and start no model. Returns 0, or 1 when an input does not resolve. Without
    it, `execute` runs the scenario: the sandbox of DIR (built when DIR holds none), every agent's session, the operator's
    steps and DIR/results.jsonl; the knob `replay` makes each session a bench_replay.py run (`replay_argv`). Raises Refused on
    an unknown scenario, knob or model."""
    if scenario not in SCENARIOS:
        raise Refused(f"no scenario {scenario}; one of {', '.join(SCENARIOS)}")
    k = {"sequential": False, "coord": "shared", "stagger": 0.0, "model": "", "pack_budget": PACK_BUDGET, "tools": "kb", "manager": "code",
         "max_usd": None, "timeout": bench_repro.DEFAULTS["timeout"], "replay": False, **(knobs or {})}
    bad = [f"--coord is one of {', '.join(COORDS)}"] if k["coord"] not in COORDS else []
    bad += [f"--tools is one of {', '.join(TOOL_SETS)}"] if k["tools"] not in TOOL_SETS else []
    bad += [f"--manager is one of {', '.join(MANAGERS)}"] if k["manager"] not in MANAGERS else []
    bad += ["--stagger needs 0 or more seconds"] if k["stagger"] < 0 else []
    bad += ["--max-usd needs more than 0"] if k["max_usd"] is not None and k["max_usd"] <= 0 else []
    bad += ["--timeout needs 1 or more seconds"] if k["timeout"] < 1 else []
    bad += [f"--pack-budget is {PACK_LIMITS[0]} to {PACK_LIMITS[1]} tokens"] if not PACK_LIMITS[0] <= k["pack_budget"] <= PACK_LIMITS[1] else []
    if bad:
        raise Refused("; ".join(bad))
    models = parse_models(k["model"])
    root = (Path(root) if root else default_dir()).resolve()
    rows, questions = load_inputs(), pool_questions()
    briefs = bench_repro.load_briefs()
    problems = input_problems([r for r in rows if r["scenario"] == scenario], questions, {b["area"].strip() for b in briefs})
    agents = agents_of(rows, scenario)
    if problems or not agents:
        for ln in problems or [f"no rows of scenario {scenario} in {INPUTS}"]:
            out(f"FAIL: {ln}")
        return 1
    recorded = read_rows(RESULTS)
    means = recorded_means(recorded)
    plans = [agent_plan(a, scenario, n, root, k, models, means, questions, briefs) for n, a in enumerate(agents, 1)]
    if k["replay"]:
        for p in plans:
            p["argv"] = replay_argv(p, recorded_usage(recorded, p["mid"]), k)
    if not dry_run:
        return execute(scenario, root, k, plans, out)
    order = "one at a time (--sequential)" if k["sequential"] else f"at once, {k['stagger']:g} s apart (--stagger)"
    out(f"multi run {scenario} --dry-run: {len(plans)} agent(s), started {order}, coord {k['coord']}, manager {k['manager']}"
        + (", replay (scripted agents, no model call)" if k["replay"] else ""))
    out(f"dir: {root} (nothing is created)")
    out(f"knobs: --sequential {'on' if k['sequential'] else 'off'}, --coord {k['coord']}, --stagger {k['stagger']:g}, --model "
        + ",".join(f"{r}={m}" for r, m in models.items()) + f", --pack-budget {k['pack_budget']}, --tools {k['tools']}, --manager {k['manager']}")
    total = sum(p["usd"] for p in plans)
    if k["manager"] == "session":
        one, why = question_usd(means, model_price_id(models["manager"]))
        out(f"manager: a {models['manager']} session starts the agents and answers their gates; argv: "
            + shlex.join(session_argv(models["manager"], LOOKUP_LIMITS["max_turns"], LOOKUP_LIMITS["usd"], root / "manager-mcp.json")))
        out(f"  estimate {money(one)}: one session at the cost of one question, {why}")
        total += one
    else:
        out("manager: code (this tool starts the sessions and answers the gates)")
    for p in plans:
        out(f"agent {p['agent']}: {p['role']}, model {p['model']} ({p['mid']}), {p['what']}")
        out(f"  argv: {shlex.join(p['argv'])}")
        out(f"  KB_COORD_STORE {p['store']}")
        out(f"  estimate {money(p['usd'])}: {p['basis']}")
        for ln in p["prompt"].splitlines()[:3]:
            out(f"  | {ln}")
    walls = [p["wall"] for p in plans if p["wall"]]
    out(f"estimate: {money(total)} for the scenario, from bench_core.PRICE and the recorded rows' means")
    if walls:
        out(f"wall: about {sum(walls) if k['sequential'] else max(walls):.0f} s for the {len(walls)} research agent(s) at the recorded mean "
            f"of {means['repro']['wall_s']:.0f} s per area; the others have no recorded wall time")
    return 0


# ------------------------------------------------------------------------------------------------------- a real run

STEP_TIMEOUT = 7200  # seconds one operator command (claim, answer, land) may take
WRAPPER = """#!{python}
import os, sys
here = os.path.dirname(os.path.abspath(__file__))
for d in os.environ.get("PATH", "").split(os.pathsep):
    found = os.path.join(d, "claude")
    if d and os.path.abspath(d) != here and os.path.isfile(found) and os.access(found, os.X_OK):
        extra = ["--settings", os.environ["MULTI_SETTINGS"], "--mcp-config", os.environ["MULTI_MCP_CONFIG"], "--strict-mcp-config",
                 "--max-budget-usd", os.environ["MULTI_MAX_USD"]]
        os.execv(found, [found, *sys.argv[1:], *extra])
sys.exit("claude is not on PATH")
"""  # DIR/bin/claude: the claude `dispatch` starts, with the run's session settings, the agent's mcp-config and the dollar cap added


REPLAY_WRAPPER = """#!{python}
import os, sys
os.execv({python!r}, [{python!r}, {replay!r}, "code", "--usage", os.environ["MULTI_REPLAY_USAGE"], "--cost", os.environ["MULTI_REPLAY_COST"]])
"""  # DIR/bin/claude under --replay: bench_replay.py as the code agent's worker, which makes no model call


def write_wrapper(root, replay=False):
    """Write DIR/bin/claude, the wrapper a code agent's dispatch finds first on PATH: the session wrapper, or under `replay` the
    scripted worker."""
    path = Path(root) / BIN / "claude"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = REPLAY_WRAPPER.format(python=sys.executable, replay=str(HOME / REPLAY)) if replay else WRAPPER.format(python=sys.executable)
    path.write_text(text, encoding="utf-8", newline="\n")
    path.chmod(0o755)


def run_group(argv, cwd, env, timeout):
    """(exit code, stdout, stderr, timed out) of `argv` run in its own process group, which a timeout ends whole."""
    p = subprocess.Popen(argv, cwd=str(cwd), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                         errors="replace", start_new_session=True)
    try:
        out, err = p.communicate(timeout=timeout)
        return p.returncode, out, err, False
    except subprocess.TimeoutExpired:
        if hasattr(os, "killpg"):
            os.killpg(p.pid, signal.SIGKILL)
        else:
            p.kill()
        out, err = p.communicate()
        return p.returncode, out, err, True


def filled(stdout):
    """`stdout` with the keys of its result event that agent_bench.result_of reads and a stream may lack (the duration, the
    cost, the turns and the four token counts) defaulted to 0, so a short stream is parsed as the full one is."""
    lines = []
    for ln in stdout.splitlines():
        try:
            ev = json.loads(ln)
        except ValueError:
            ev = None
        if isinstance(ev, dict) and ev.get("type") == "result":
            for key in ("duration_api_ms", "total_cost_usd", "num_turns"):
                ev.setdefault(key, 0)
            ev["usage"] = {k: 0 for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens",
                                          "cache_read_input_tokens")} | (ev.get("usage") or {})
            ln = json.dumps(ev)
        lines.append(ln)
    return "\n".join(lines) + "\n"


def event_steps(stdout):
    """The `steps` a replayed agent's result event holds (the commands it ran); [] for a stream with none."""
    for ln in reversed(stdout.splitlines()):
        try:
            ev = json.loads(ln)
        except ValueError:
            continue
        if isinstance(ev, dict) and ev.get("type") == "result":
            return [s for s in ev.get("steps") or [] if isinstance(s, str)]
    return []


def run_session(argv, prompt, cwd, env, timeout):
    """One agent's session parsed as bench_core.stream_run parses it (agent_bench.result_of over the stream, `filled`), and
    its cost counted in the run's spend; the whole `env` is the session's environment. A replayed agent's commands are the
    result's `steps`."""
    t = time.time()
    try:
        p = subprocess.run(argv, cwd=str(cwd), input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, env=env)
        r = agent_bench.result_of(filled(p.stdout), p.stderr, time.time() - t)
        r["steps"] = event_steps(p.stdout)
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else e.stdout
        r = {**agent_bench.unfinished(out, "timeout", time.time() - t, always=True), "timeout_s": timeout}
    spent_run(r)
    return r


def backlog_cmd(clone, *args, root=None):
    """The argv of `backlog.py` of `clone` with `args`, against the checkout `root` when given."""
    return [sys.executable, str(Path(clone) / "_tools" / "backlog.py"), *(["--root", str(root)] if root else []), *args]


def operator_env(env):
    """`env` for an operator command: KB_SYNC_NO_TESTS of this process kept, as sync_push keeps it."""
    return {**env, **({"KB_SYNC_NO_TESTS": os.environ["KB_SYNC_NO_TESTS"]} if os.environ.get("KB_SYNC_NO_TESTS") else {})}


def open_gates(item):
    """The gates of an item (a dict) with no answer and a recommendation."""
    return [g for g in item.get("gates", []) if isinstance(g, dict) and not g.get("answer") and g.get("recommendation")]


def answer_gates(clone, where, item, env):
    """Answer each open gate of `item` by its recommendation as the operator (`backlog.py answer --by operator --commit`) in
    the checkout `where` of `clone`: the step of each. Raises Refused when an answer is refused."""
    steps = []
    for g in open_gates(item):
        argv = backlog_cmd(clone, "answer", item["id"], g["id"], "--answer", g["recommendation"], "--by", OPERATOR, "--commit",
                           root=None if Path(where) == Path(clone) else where)
        p = sh(argv, where, operator_env(env))
        if p.returncode:
            raise Refused(f"the answer of gate {g['id']} of {item['id']} exited {p.returncode}: {(p.stdout + p.stderr).strip()[-300:]}")
        steps.append(f"answered gate {g['id']}")
    return steps


def operator_pass(root, coord, manifest, plans, out, replay=False):
    """Before any agent starts: answer every open gate of each planted item in the first code agent's clone and sync it to the
    bare (`kbgit.py sync --push`, without its test run under `replay`). {item id: [steps]}. Raises Refused when the sync stops."""
    codes = [p for p in plans if p["role"] == "code"]
    if not codes:
        return {}
    a = manifest["agents"][codes[0]["n"] - 1]
    clone, env = Path(a["clone"]), agent_env(root, coord, a["n"])
    steps = {p["item"]: answer_gates(clone, clone, json.loads((clone / ITEM_DIR / f"{p['item']}.json").read_text(encoding="utf-8")), env)
             for p in codes}
    if any(steps.values()) and sync_push(root, coord, a, out, replay):
        raise Refused("the operator's gate answers did not reach the bare: kbgit.py sync --push stopped")
    return steps


class Budget:
    """--max-usd: the recorded spend and the estimates of the agents started and not yet recorded."""

    def __init__(self, cap, spent):
        self.cap, self.spent, self.held, self.lock = cap, spent, 0.0, threading.Lock()

    def reserve(self, estimate):
        """(True, spend) and hold `estimate` when the spend plus it stays within the cap, else (False, spend)."""
        with self.lock:
            total = self.spent + self.held
            if self.cap is not None and total + estimate > self.cap + 1e-9:
                return False, total
            self.held += estimate
            return True, total

    def settle(self, estimate, cost):
        with self.lock:
            self.held -= estimate
            self.spent += cost


def blank_line(plan, scenario, k):
    return {"scenario": scenario, "agent": plan["agent"], "role": plan["role"], "item": plan.get("item", ""), "model": bench_repro.model_id(plan["model"]),
            "coord": k["coord"], "sequential": k["sequential"], "started": "", "ended": "", "failure": "", "subtype": "", "wall_s": 0,
            "cost": 0, "input_tokens": 0, "output_tokens": 0, "cache_write_tokens": 0, "cache_read_tokens": 0, "turns": 0,
            "max_turns": plan["turns"], "tool_calls": 0, "steps": [], "commit": "", "land": ""}


def session_fields(r, plan, wall, tool_calls=None):
    """The result-line fields of a parsed session `r` (agent_bench.execute's): a session that timed out or ended with no result
    event states no cost, so it is recorded at the agent's dollar cap, the most it can have spent."""
    fail = failure_of(r)
    out = {"failure": fail, "subtype": r.get("subtype") or ("success" if not fail else fail), "wall_s": round(wall, 1),
           "cost": plan["cap"] if r.get("cost_unknown") else r.get("cost") or 0, "input_tokens": r.get("in_uncached", 0),
           "output_tokens": r.get("out", 0), "cache_write_tokens": r.get("cache_write", 0), "cache_read_tokens": r.get("cache_read", 0),
           "turns": r.get("turns", 0),
           "tool_calls": sum(r.get("tools", {}).values()) + sum(r.get("sub_tools", {}).values()) if tool_calls is None else tool_calls}
    if r.get("cost_unknown"):
        out["cost_unknown"] = True
    if fail:
        out["error"] = str(r.get("error", ""))[:300]
    return out


def transcript_tools(session):
    """The tool calls of a persisted session, its subagents' included; 0 when it has no transcript."""
    try:
        main, subs = transcript(session)
    except (OSError, ValueError):
        return 0
    return sum(len(r["tools"]) for r in main) + sum(len(r["tools"]) for reqs in subs.values() for r in reqs)


def land_result(code, out, err, timed):
    """What the record's `land` says of a `backlog.py land` run: `ok`, the step it stopped at, or its last line."""
    if timed:
        return "timeout"
    if code == 0:
        return "ok"
    text = (out + "\n" + err).strip().splitlines()
    stop = next((ln for ln in text if ln.startswith("land stopped at step")), "")
    return (stop.split(":")[0] if stop else f"exit {code}: {text[-1] if text else ''}")[:200]


def branch_exists(root, branch):
    """True when the sandbox's bare holds the branch `branch`."""
    return sh(["git", "rev-parse", "-q", "--verify", f"refs/heads/{branch}"], origin_path(root), os.environ).returncode == 0


def merge_request(root, branch, tries=5):
    """Merge `branch` of the sandbox's bare into its main as the forge's merge request would: a merge commit made in a throwaway
    clone and pushed, again after a push of another agent moved main in between. Raises Refused when it cannot be pushed."""
    work = Path(root) / ("merge-" + branch.replace("/", "-"))
    shutil.rmtree(work, ignore_errors=True)
    try:
        run_git("clone", "-q", str(origin_path(root)), str(work), cwd=root)
        for _ in range(tries):
            run_git("fetch", "-q", "origin", "+refs/heads/main:refs/remotes/origin/main", f"+refs/heads/{branch}:refs/remotes/origin/{branch}", cwd=work)
            run_git("checkout", "-q", "-B", "main", "refs/remotes/origin/main", cwd=work)
            run_git("-c", "user.name=multi sandbox", "-c", "user.email=jan.kowalski@corp.example.com", "merge", "-q", "--no-ff",
                    "--no-verify", "-m", f"Merge branch '{branch}' into 'main'", f"refs/remotes/origin/{branch}", cwd=work)
            if sh(["git", "push", "-q", "--no-verify", "origin", "HEAD:refs/heads/main"], work, os.environ).returncode == 0:
                return
        raise Refused(f"the merge of {branch} into main was rejected {tries} times")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def code_agent(plan, ctx, rec):
    """A code agent, the operator's side of it: claim the item, `dispatch` its worker in the clone, answer the gates the worker
    left open, `land` the item; a land that left the code on its `code/<id>` branch (sync --push routes a code-lane path there)
    is followed by the merge request (`merge_request`) and a second land. Fills `rec` (the session's fields are the worker's)."""
    clone, env, iid, steps = ctx.clone(plan), ctx.env(plan), plan["item"], rec["steps"]
    steps += ctx.gate_steps.get(iid, [])
    p = sh(backlog_cmd(clone, "claim", iid, "--by", f"multi-agent{plan['n']}", "--commit"), clone, env)
    if p.returncode:
        raise Refused(f"claim of {iid} exited {p.returncode}: {(p.stdout + p.stderr).strip()[-300:]}")
    steps.append("claimed")
    denv = {**env, "PATH": str(ctx.root / BIN) + os.pathsep + env.get("PATH", ""), "MULTI_SETTINGS": bench_repro.SETTINGS,
            "MULTI_MCP_CONFIG": str(mcp_path(ctx.root, plan["n"])), "MULTI_MAX_USD": f"{plan['cap']:g}",
            **({"MULTI_REPLAY_USAGE": json.dumps(plan["usage"]), "MULTI_REPLAY_COST": f"{plan['cost']:.4f}"} if ctx.k["replay"] else {})}
    rec["started"] = utc_now()
    t = time.time()
    code, out, err, timed = run_group(plan["argv"], clone, denv, ctx.timeout)
    wall = time.time() - t
    steps.append("dispatched")
    line = next((ln for ln in out.splitlines() if ln.startswith("dispatched")), "")
    found = re.search(r", output (\S+)\s*$", line)
    text, session = "", None
    if found and Path(found.group(1)).is_file():
        text = Path(found.group(1)).read_text(encoding="utf-8", errors="replace")
        try:
            data = json.loads(text)
            session = data.get("session_id") if isinstance(data, dict) else None
        except ValueError:
            pass
    r = agent_bench.unfinished(text, "timeout", wall, always=True) if timed else agent_bench.result_of(filled(text), err or out, wall)
    worked = event_steps(text)  # a replayed worker's commands
    steps += worked
    rec.update(session_fields(r, plan, wall, transcript_tools(session) if session else len(worked) or None))
    wt = clone / ".claude" / "worktrees" / f"agent-{iid}"
    shown = sh(["git", "show", f"work/{iid}:{ITEM_DIR}/{iid}.json"], clone, env)
    if shown.returncode == 0 and wt.is_dir():
        for step in answer_gates(clone, wt, json.loads(shown.stdout), env):
            steps.append(step + " on the worker's branch")
    t = time.time()
    branch = f"code/{iid}"
    for attempt in (1, 2):
        code, lout, lerr, timed = run_group(backlog_cmd(clone, "land", iid), clone, operator_env(env), STEP_TIMEOUT)
        rec["land"] = land_result(code, lout, lerr, timed)
        steps.append("land: " + rec["land"])
        if rec["land"] == "ok" or attempt == 2 or not branch_exists(ctx.root, branch):
            break
        merge_request(ctx.root, branch)  # sync --push put the code on a branch; the forge's merge request is the operator's
        steps.append(f"merged {branch} into main")
    if rec["land"] != "ok":
        rec["land_detail"] = (lout + "\n" + lerr).strip()[-600:]
    rec["land_s"] = round(time.time() - t, 1)


def session_agent(plan, ctx, rec):
    """A lookup or research agent: one session in the agent's clone with its prompt, argv and environment."""
    clone, env = ctx.clone(plan), ctx.env(plan)
    rec["started"] = utc_now()
    t = time.time()
    r = run_session(plan["argv"], plan["prompt"], clone, env, ctx.timeout)
    worked = r.get("steps", [])
    rec.update(session_fields(r, plan, time.time() - t, len(worked) or None))
    rec["steps"] += worked or ["session"]


class Context:
    """What the agents of one run share: the sandbox, its manifest, the results file and the budget."""

    def __init__(self, scenario, root, k, manifest, budget, steps):
        self.scenario, self.root, self.k, self.manifest, self.budget, self.gate_steps = scenario, root, k, manifest, budget, steps
        self.timeout, self.path, self.lock = k["timeout"], root / RUN_RESULTS, threading.Lock()

    def clone(self, plan):
        return Path(self.manifest["agents"][plan["n"] - 1]["clone"])

    def env(self, plan):
        """The agent's environment; under replay the sync gate skips its test run, as the sandbox's code is this checkout's, which
        the replayed changes do not touch."""
        env = agent_env(self.root, self.k["coord"], plan["n"])
        if self.k["replay"]:
            env["KB_SYNC_NO_TESTS"] = "1"
        return env

    def fresh(self, plan):
        """A lookup agent's clone is as setup made it; the others start from the bare's main."""
        if plan["role"] != "lookup":
            reset_clone(self.clone(plan), self.env(plan))

    def append(self, rec, out):
        with self.lock, open(self.path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(rec, sort_keys=True) + "\n")
            f.flush()
        out(f"agent {rec['agent']}: {rec['failure'] or 'ok'}, ${rec['cost']:.2f}, {rec['turns']} turns, {rec['wall_s']:.0f} s"
            + (f", land {rec['land']}" if rec["land"] else ""))

    def one(self, plan, out):
        """Run one agent and append its line: its session, its operator steps, or, when the spend would pass --max-usd, the line
        that records it with the failure budget. A harness error is a line with failure `error`: it ends no other agent."""
        rec = blank_line(plan, self.scenario, self.k)
        ok, spent = self.budget.reserve(plan["usd"])
        if not ok:
            rec.update(failure="budget", subtype="budget", started=utc_now(), ended=utc_now(),
                       error=f"recorded spend ${spent:.2f} plus the estimate ${plan['usd']:.2f} passes --max-usd {self.budget.cap:g}")
            self.append(rec, out)
            return rec
        try:
            (code_agent if plan["role"] == "code" else session_agent)(plan, self, rec)
        except Exception as e:  # noqa: BLE001 - a harness error is the agent's line, never the run's end
            rec.update(failure="error", subtype="error", error=f"harness: {e}"[:300])
            rec["started"] = rec["started"] or utc_now()
        try:
            rec["commit"] = run_git("rev-parse", "HEAD", cwd=self.clone(plan))
        except Refused:
            pass
        rec["ended"] = utc_now()
        self.budget.settle(plan["usd"], rec["cost"])
        self.append(rec, out)
        return rec


def execute(scenario, root, k, plans, out):
    """The real `multi run`: the sandbox of `root` (built when it holds none), the operator's answers to the planted items'
    gates, every agent's session (all at once, one thread each, `--stagger` apart; one after the other with `--sequential`) and
    each agent's line appended to DIR/results.jsonl. Returns 0 when every agent finished and every code item landed, else 1.
    Raises Refused on a refusal."""
    if k["manager"] == "session":
        raise Refused("--manager session is not supported by a real run: the harness code starts the agents (--manager code)")
    if not k["replay"] and not shutil.which(bench_repro.CLAUDE[0]):
        raise Refused(f"{bench_repro.CLAUDE[0]} is not on PATH")
    if not (root / MANIFEST).exists():
        setup(None, k["coord"], root, scenario=scenario, out=out)
    manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    if manifest.get("scenario") != scenario or manifest.get("coord") != k["coord"] or len(manifest["agents"]) != len(plans):
        raise Refused(f"{root} holds the sandbox of scenario {manifest.get('scenario')}, coord {manifest.get('coord')}, "
                      f"{len(manifest['agents'])} agent(s): remove it or use another --dir")
    write_wrapper(root, k["replay"])
    path = root / RUN_RESULTS
    ctx = Context(scenario, root, k, manifest, Budget(k["max_usd"], sum(r.get("cost") or 0 for r in bench_repro.read_results(path))),
                  operator_pass(root, k["coord"], manifest, plans, out, k["replay"]))
    out(f"multi run {scenario}: {len(plans)} agent(s), " + ("one at a time" if k["sequential"] else "all at once")
        + f", coord {k['coord']}, results {path}")
    recs = []
    if k["sequential"]:
        for i, plan in enumerate(plans):
            time.sleep(k["stagger"] if i else 0)
            ctx.fresh(plan)
            recs.append(ctx.one(plan, out))
    else:
        for plan in plans:
            ctx.fresh(plan)

        def start(i, plan):
            time.sleep(i * k["stagger"])
            return ctx.one(plan, out)
        with ThreadPoolExecutor(max_workers=len(plans)) as pool:
            recs = [f.result() for f in [pool.submit(start, i, p) for i, p in enumerate(plans)]]
    failed = [r for r in recs if r["failure"] or (r["role"] == "code" and r["land"] != "ok")]
    out(f"multi run {scenario}: {len(recs) - len(failed)} of {len(recs)} agent(s) finished" + ("" if not failed else f", {len(failed)} failed: "
        + ", ".join(f"{r['agent']} ({r['failure'] or r['land']})" for r in failed)) + f", ${ctx.budget.spent:.2f} recorded in {path}")
    return 1 if failed else 0
