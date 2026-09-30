"""The benchmarks' install scenarios: /kb-ingest on a sample repository, a host plugin with team roots,
the hook launcher's start-up and a new model against the one it replaces (stdlib only).

benchmarks.py registers these scenarios in SCENARIOS and holds the command line; the harness is bench_core.py
(kb/_self/code.md, Layout and Imports; the scenarios are described in kb/_self/reports/benchmarks.md). This
module imports no facade.
"""
import json, platform, re, shutil, statistics, subprocess, sys

import agent_bench
from bench_core import (HOME, OK_PROMPT, TOOLS, claude_json, git, mcp_session, need_sh, no_plugin_env, stat_rows,
                        stream_run, task_argv, time_runs)
from kbcommon import NO_HOOKS


INGEST_REPO = ("https://github.com/pypa/sampleproject.git", "621e4974ca25ce531773def586ba3ed8e736b3fc")


def s_ingest(b):
    """/kb-ingest on a sample repository (a public one at a pinned commit): kbingest.py's survey, then the skill in a
    headless Sonnet session in a throwaway clone (query log off, local origin), its questions answered in the prompt."""
    url, sha = INGEST_REPO
    repo = b.scratch / "sample-repo"
    if not (repo / ".git").exists():
        shutil.rmtree(repo, ignore_errors=True)
        git("clone", "-q", url, str(repo), cwd=b.scratch)
    git("checkout", "-q", "--detach", sha, cwd=repo)
    secs = time_runs([sys.executable, str(TOOLS / "kbingest.py"), "survey", str(repo), "--rev", sha, "--files"], 3, HOME)
    stat_rows(b, "ingest", "kbingest.py survey", "sampleproject", secs)
    out = subprocess.run([sys.executable, str(TOOLS / "kbingest.py"), "survey", str(repo), "--rev", sha, "--files"],
                         capture_output=True, text=True, encoding="utf-8").stdout
    keep = sum(ln.startswith("keep\t") for ln in out.splitlines())
    skip = sum(ln.startswith("skip\t") for ln in out.splitlines())
    b.row("ingest", "kbingest.py survey", "sampleproject", "files_kept", keep, 1)
    b.row("ingest", "kbingest.py survey", "sampleproject", "files_left_out", skip, 1)
    clone = b.clone("kb-ingest", "off")
    prompt = (f"/kb-ingest {repo} sample\n\nThe answers to the skill's questions, agreed in advance: the root is a new "
              "root named `sample`, prefix SMP, visibility public, description \"The PyPA sample project\"; the "
              f"repository is public on GitHub and pinned at {sha}; the topic plan is one topic, "
              "`python/sampleproject`, covering its packaging layout, build backend, entry points, tests and CI. "
              "Write it now without asking again. Do not commit or push.")
    r = stream_run(["claude", "-p", "--output-format", "stream-json", "--verbose", "--no-session-persistence", *NO_HOOKS,
                    "--model", "sonnet", "--permission-mode", "bypassPermissions", "--max-budget-usd", "4"], prompt, clone)
    if "error" in r:
        b.row("ingest", "/kb-ingest", "sonnet", "errors", 1, 1, note=r["error"][:80])
        return
    b.bench_rows("ingest", [{**r, "cfg": "sonnet", "scen": "/kb-ingest", "checks": []}])
    p = subprocess.run([sys.executable, "_tools/rag.py", "audit", "sample"], cwd=clone, capture_output=True, text=True)
    facts = sum(int(m.group(1)) for m in re.finditer(r"^\| \S+ \| \w+ \| (\d+) \|", p.stdout, re.M))
    b.row("ingest", "/kb-ingest", "sonnet", "facts_written", facts, 1)
    chk = subprocess.run([sys.executable, "_tools/check.py"], cwd=clone, capture_output=True, text=True).stdout
    m = re.search(r"errors=(\d+)", chk)
    b.row("ingest", "/kb-ingest", "sonnet", "check_errors", int(m.group(1)) if m else "", 1)


TEAM_ARTICLE = """---
topic: intune/compliance-naming
priority: P2
applies_to: "The team's Intune compliance policies"
retrieved_utc: {date}
sources: [TM-unavfdbc]
status: complete
---

# Team Intune compliance policy naming

## Summary
How the team names its Intune compliance policies and sets the grace period of the built-in noncompliance action.

## Facts
- Team naming rule: every Intune compliance policy is named `CMP-<platform>-<ring>-<purpose>`, for example `CMP-WIN-PROD-Baseline`. [DOC TM-unavfdbc]
- The ring part is one of `PILOT`, `BROAD` or `PROD`, and a policy is assigned to the group of its ring only. [DOC TM-unavfdbc]
- The team sets the schedule of the built-in "Mark device noncompliant" action to 1 day on every `CMP-*-PROD-*` policy, as a grace period. [DOC TM-unavfdbc]

## Reference
- The team wiki page on compliance naming.

## Examples
- `CMP-WIN-PILOT-Encryption`
"""
ROOTS_Q = ("what is our team's naming rule for Intune compliance policies, and can the built-in Mark device "
           "noncompliant action be removed?")
ROOTS_CHECKS = [r"CMP-", r"(?i)can.?not be removed|can't be removed|cannot remove|can't remove|not be removed",
                # a citation from each root: its path or its source id or url
                r"team/intune/compliance-naming|TM-unavfdbc|intune-compliance-naming",
                r"compliance-policies\.md|S-u3qwumeu|actions-for-noncompliance"]


def s_host_roots(b):
    """A host plugin with team roots: a fork (a throwaway clone) with a `team` root beside public, asked one question
    spanning both roots with the plugin loaded by --plugin-dir and with the team root served by KB_ROOTS; and the
    server over stdio (no model). The installed-plugin mode is not run: it writes the installed plugin's data
    directory under ~/.claude."""
    fork = b.clone("kb-fork", "off")
    py = sys.executable
    subprocess.run([py, "_tools/kbroot.py", "add", "team", "--prefix", "TM", "--visibility", "internal"], cwd=fork,
                   capture_output=True, env=no_plugin_env())
    art = fork / "kb" / "team" / "intune" / "compliance-naming.md"
    art.parent.mkdir(parents=True, exist_ok=True)
    art.write_text(TEAM_ARTICLE.format(date=b.date), encoding="utf-8", newline="\n")
    with open(fork / "kb" / "team" / "_sources.csv", "a", encoding="utf-8", newline="\n") as f:
        f.write(f"TM-unavfdbc,https://wiki.corp.example.com/endpoint/intune-compliance-naming,Intune compliance naming,"
                f"Endpoint team,internal,quote,{b.date},,,,\n")
    subprocess.run([py, "_tools/build_index.py"], cwd=fork, capture_output=True, env=no_plugin_env())
    chk = subprocess.run([py, "_tools/check.py"], cwd=fork, capture_output=True, text=True, env=no_plugin_env()).stdout
    m = re.search(r"errors=(\d+)", chk)
    b.row("host-roots", "fork", "check.py", "errors", int(m.group(1)) if m else "", 1)
    host = b.scratch / "host-roots"
    shutil.rmtree(host, ignore_errors=True)
    host.mkdir()
    git("init", "-q", cwd=host)
    env = no_plugin_env({"ENABLE_CLAUDEAI_MCP_SERVERS": "false", "KB_INDEX": str(b.scratch / "index-fork")})
    teamdir = b.scratch / "team-root"
    shutil.rmtree(teamdir, ignore_errors=True)
    shutil.copytree(fork / "kb" / "team", teamdir / "team")
    lookup = b.lookup()
    mcp = json.dumps({"mcpServers": {"kb": {"command": py, "args": [str(lookup / "_tools" / "kb_mcp.py")],
                                            "env": {"KB_ROOTS": str(teamdir / "team")}}}})
    modes = (("--plugin-dir", ["--setting-sources", "project", "--plugin-dir", str(fork), "--allowedTools", "mcp__plugin_it-ops-kb_kb"]),
             ("KB_ROOTS", ["--setting-sources", "project", "--mcp-config", mcp, "--strict-mcp-config", "--allowedTools", "mcp__kb"]))
    for mode, extra in modes:
        runs = []
        for _ in range(max(2, b.reps)):
            r = stream_run(task_argv("haiku", extra), ROOTS_Q, host, env)
            if "error" not in r:
                r["checks"] = [bool(re.search(c, r["answer"])) for c in ROOTS_CHECKS]
            runs.append({**r, "cfg": mode, "scen": "both roots"})
        b.bench_rows("host-roots", runs)
    _, _, texts = mcp_session(fork, [("kb_status", {}), ("kb_pack", {"question": ROOTS_Q})])
    pack = texts[-1] if texts else ""
    b.row("host-roots", "server over stdio", "no model", "coverage", (re.search(r"coverage: (\w+)", pack) or [None, "?"])[1], 1)
    b.row("host-roots", "server over stdio", "no model", "roots_in_pack",
          sum(x in pack for x in ("team/intune/compliance-naming.md", "public/intune/compliance-policies.md")), 1)


def s_kbpy(b):
    """The hook launcher's start-up: a no-op script run by `sh _tools/kbpy` against the same script run by the
    interpreter directly, on this OS."""
    sh = need_sh()
    d = b.scratch / "kbpy" / "_tools"
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(TOOLS / "kbpy", d / "kbpy")
    (d.parent / "noop.py").write_text("pass\n", encoding="utf-8")
    osname = platform.system()
    n = max(50, b.reps)
    direct = time_runs([shutil.which("python3") or sys.executable, str(d.parent / "noop.py")], n, d.parent)
    via = time_runs([sh, str(d / "kbpy"), "noop.py"], n, d.parent)
    stat_rows(b, "kbpy", "python3 noop.py", osname, direct)
    stat_rows(b, "kbpy", "sh _tools/kbpy noop.py", osname, via)
    b.row("kbpy", "launcher overhead", osname, "median_ms", (statistics.median(via) - statistics.median(direct)) * 1000, n)


NEW_MODEL = ("sonnet-5-5", "sonnet-5")  # agent_bench.py configs: the new model, then the one it replaces
NEW_MODEL_KB = ["s1_fact", "s3_multi", "s5_none", "s6_falsegood", "s8_falsegood2", "h1_gmsa", "h2_applock", "h3_mggraph",
                "x1_synth", "o1_offkb"]
NEW_MODEL_WEB = ["s1_fact", "x1_synth", "o1_offkb"]
NEW_MODEL_HOST = ["p1_partial", "n1_newer", "k1_stale"]


def s_new_model(b):
    """A new model against the one it replaces, pinned by id in one batch: the kb arm on ten questions (facts,
    false goods, off-kb, how-to snippets, a synthesis), the bare web arm on three, the host scenarios for partial
    knowledge, a newer version and a stale copy, and the fixed context of "ok" in an empty directory and the clone."""
    new, old = NEW_MODEL
    runs = b.bench([new, old], NEW_MODEL_KB, b.reps, "new-model", parallel=True)
    runs += b.bench([f"web-{new}", f"web-{old}"], NEW_MODEL_WEB, 1, "new-model", parallel=True)
    runs += b.bench([new, old], NEW_MODEL_HOST, 1, "new-model", parallel=True)
    b.bench_rows("new-model", runs)
    for cfg in (new, old):
        for case, scens in (("kb (10)", NEW_MODEL_KB), ("host (3)", NEW_MODEL_HOST)):
            rs = [r for r in runs if r["cfg"] == cfg and r["scen"] in scens and "error" not in r]
            if not rs:
                continue
            n = len(rs)
            b.row("new-model", case, cfg, "cost", sum(r["cost"] for r in rs) / n, n)
            b.row("new-model", case, cfg, "wall_s", sum(r["wall_s"] for r in rs) / n, n)
            b.row("new-model", case, cfg, "input", sum(r["in_uncached"] + r["cache_write"] + r["cache_read"]
                                                        for r in rs) / n, n)
            b.row("new-model", case, cfg, "out", sum(r["out"] for r in rs) / n, n)
            b.row("new-model", case, cfg, "tool_calls", sum(sum(r.get("tools", {}).values()) for r in rs) / n, n)
            b.row("new-model", case, cfg, "checks", f"{sum(sum(map(bool, r['checks'])) for r in rs)}/"
                  f"{sum(len(r['checks']) for r in rs)}", n)
            b.row("new-model", case, cfg, "fully_right", f"{sum(all(r['checks'] or [False]) for r in rs)} of {n}", n)
    empty = b.scratch / "empty"
    empty.mkdir(exist_ok=True)
    for cfg in (new, old):
        model = agent_bench.MODEL[cfg]
        for arm, cwd in (("an empty directory", empty), ("the clone", b.lookup())):
            vals = [v for v in (claude_json(["claude", "-p", "--no-session-persistence", "--model", model, *NO_HOOKS],
                                            OK_PROMPT, cwd) for _ in range(2)) if "error" not in v]
            if vals:
                b.row("new-model", f"ok in {arm}", cfg, "start_ctx", max(v["input"] for v in vals), len(vals), model,
                      note="; ".join(str(v["input"]) for v in vals))
                b.row("new-model", f"ok in {arm}", cfg, "out", max(v["usage"]["output_tokens"] for v in vals),
                      len(vals), model)
                b.row("new-model", f"ok in {arm}", cfg, "cost", sum(v["total_cost_usd"] for v in vals) / len(vals),
                      len(vals), model)
