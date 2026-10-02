"""_tools/benchmarks.py without a paid run: the report's generated tables and README.md's numbers against the results
file, the isolation of every run (hooks off, throwaway clones with a local origin, a plugin copy whose hooks write
under the scratch directory), the transcript reader and the scenario list the report names."""
import json, os, re, shutil, subprocess
from pathlib import Path

import pytest

import agent_bench, bench_core, bench_install, bench_lookup, bench_querylog, bench_report, benchmarks as bm, kb_ask
from conftest import GIT, Repo, git_env
from kbcommon import NO_HOOKS

ROWS = [
    {"scenario": "demo", "record": "a1b2c3d", "date": "2026-09-26", "commit": "a1b2c3d", "claude_code": "2.1.283",
     "kb_topics": "265", "case": "s1", "arm": "kb-haiku", "model": "", "metric": "cost", "value": "$0.030 / $0.032",
     "runs": "2", "note": ""},
    {"scenario": "demo", "record": "2026-09-28", "date": "2026-09-28", "commit": "e4f5a6b", "claude_code": "2.1.290",
     "kb_topics": "271", "case": "s1", "arm": "kb-haiku", "model": "claude-haiku-4-5", "metric": "cost",
     "value": "0.0285", "runs": "1", "note": ""},
    {"scenario": "demo", "record": "2026-09-28", "date": "2026-09-28", "commit": "e4f5a6b", "claude_code": "2.1.290",
     "kb_topics": "271", "case": "s1", "arm": "kb-haiku", "model": "claude-haiku-4-5", "metric": "wall_s",
     "value": "9.8", "runs": "1", "note": ""},
]
REPORT = "intro\n<!-- bench:table demo metrics=cost,wall_s -->\nold\n<!-- /bench -->\n<!-- bench:records demo -->\n<!-- /bench -->\n"


def test_tables_are_generated_from_the_results_and_a_typed_cell_fails_the_check():
    text = bench_report.render(REPORT, ROWS)
    assert "| s1 | kb-haiku | $0.030 / $0.032 -> $0.029 (-8%) | 10 s |" in text
    assert "| 2026-09-28 | 2026-09-28 | e4f5a6b | 2.1.290 | 271 | 1 | $0.03 |" in text
    assert bench_report.render(text, ROWS) == text  # a second render changes nothing
    planted = text.replace("$0.029 (-8%)", "$0.019 (-37%)")
    assert bench_report.render(planted, ROWS) != planted  # what `report --check` compares


def test_check_fails_on_a_table_that_disagrees(tmp_path, monkeypatch, capsys):
    results, report, readme = tmp_path / "r.csv", tmp_path / "b.md", tmp_path / "README.md"
    bench_core.write_rows(ROWS, results)
    report.write_text(bench_report.render(REPORT, ROWS), encoding="utf-8")
    readme.write_text("Haiku with the kb: $0.029 and 10 s per question (Claude Code 2.1.290, 271 topics).\n", encoding="utf-8")
    monkeypatch.setattr(bm, "RESULTS", results)
    monkeypatch.setattr(bm, "REPORT", report)
    monkeypatch.setattr(bm, "README", readme)
    monkeypatch.setattr(bm, "HOME", tmp_path)
    assert bm.main(["report", "--check"]) == 0
    report.write_text(report.read_text(encoding="utf-8").replace("10 s", "11 s"), encoding="utf-8")
    assert bm.main(["report", "--check"]) == 1
    assert "differs" in capsys.readouterr().out


def test_every_readme_number_must_match_a_row():
    assert bench_report.readme_misses("costs $0.029 and 10 s, 271 topics, on 2.1.290; Haiku 4.5, Apache-2.0", ROWS) == []
    assert bench_report.readme_misses("costs $0.29 per question", ROWS) == ["$0.29"]
    assert bench_report.readme_misses("about 28k tokens", ROWS) == ["28k"]
    assert bench_report.readme_misses("3.8M characters", ROWS) == ["3.8M"]  # a row of 9.8 is not 3.8M


def test_the_committed_report_and_readme_agree_with_the_results():
    rows = bench_core.read_rows()
    assert rows, "kb/_self/reports/benchmarks.csv is empty"
    text = bm.REPORT.read_text(encoding="utf-8")
    assert bench_report.render(text, rows) == text, "python3 _tools/benchmarks.py report rewrites the tables"
    assert bench_report.readme_misses(bm.README.read_text(encoding="utf-8"), rows) == []


def test_the_report_names_every_scenario_and_its_command():
    text = bm.REPORT.read_text(encoding="utf-8")
    for name, (section, _) in bm.SCENARIOS.items():
        assert f"python3 _tools/benchmarks.py run {name}`" in text, name
    for m in bench_report.BLOCK.finditer(text):
        scen = m.group(3).split()[0] if m.group(3).strip() else ""
        assert m.group(2) == "spend" or scen in bm.SCENARIOS or any(r["scenario"] == scen for r in bench_core.read_rows()), scen


def test_results_rows_are_complete():
    for r in bench_core.read_rows():
        assert r["scenario"] and r["record"] and r["metric"], r
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}|", r["date"]), r


def _hooks_off(argv):
    i = next((i for i, a in enumerate(argv) if a == NO_HOOKS[0] and argv[i:i + 2] == NO_HOOKS), None)
    return i is not None


def test_every_claude_run_turns_hooks_off():
    argvs = [agent_bench.kb_argv(c) for c in ("haiku", "opus+delegate", "haiku+escalate", "sonnet+strict")]
    argvs += [agent_bench.web_argv("haiku"), agent_bench.host_argv("haiku", "/kb"), kb_ask.claude_argv("haiku", True),
              kb_ask.claude_argv("haiku", False), bench_core.task_argv("sonnet")]
    assert all(_hooks_off(a) for a in argvs)
    assert not _hooks_off(["claude", "-p", "--model", "haiku"])  # a run without it is caught


def test_merge_replaces_a_scenario_record():
    new = [dict(ROWS[1], value="0.03")]
    merged = bench_core.merge_rows(ROWS, new)
    assert [r["value"] for r in merged if r["record"] == "2026-09-28"] == ["0.03"]
    assert merged[0] == ROWS[0]


@pytest.mark.skipif(not GIT, reason="git is not installed")
@pytest.mark.git
def test_isolate_turns_the_query_log_down_and_points_origin_at_a_local_bare_repo(tmp_path, monkeypatch):
    for k, v in git_env().items():
        monkeypatch.setenv(k, v)
    (tmp_path / "c").mkdir()
    repo = Repo(tmp_path / "c")
    repo.git("init", "-q", "-b", "main")
    repo.git("remote", "add", "origin", "git@gitlab.example.com:team/kb.git")
    bare = tmp_path / "o.git"
    bench_core.isolate(repo.path, "local", bare)
    assert json.loads((Path(repo.path) / "_private" / "querylog.json").read_text(encoding="utf-8"))["mode"] == "local"
    assert repo.git("remote", "get-url", "origin").strip() == str(bare)


def test_plugin_copy_sends_every_hook_to_the_scratch_data_directory(tmp_path):
    src = tmp_path / "src"
    (src / ".claude-plugin").mkdir(parents=True)
    (src / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "it-ops-kb", "hooks": {
        "Stop": [{"hooks": [{"type": "command", "command": "sh \"${CLAUDE_PLUGIN_ROOT}/_tools/kbpy\" _tools/querylog.py capture"}]}],
        "SessionEnd": [{"hooks": [{"type": "command", "command": "sh x launch"}]}]}}), encoding="utf-8")
    data = tmp_path / "data"
    dest = bench_core.plugin_copy(src, tmp_path / "copy", data)
    spec = json.loads((dest / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    cmds = [h["command"] for g in spec["hooks"].values() for x in g for h in x["hooks"]]
    assert cmds and all(c.startswith(f"CLAUDE_PLUGIN_DATA='{data}' ") for c in cmds)
    assert spec["name"] == "it-ops-kb"  # the texts a session loads stay the same
    assert json.loads((data / "querylog" / "config.json").read_text(encoding="utf-8"))["mode"] == "local"


def test_transcript_requests_are_counted_once(tmp_path):
    lines = [
        {"type": "assistant", "requestId": "r1", "timestamp": "2026-09-28T10:00:00Z", "message": {"model": "m", "usage": {
            "input_tokens": 3, "cache_creation_input_tokens": 3900, "cache_read_input_tokens": 0, "output_tokens": 5},
            "content": [{"type": "tool_use", "name": "mcp__kb__kb_pack"}]}},
        {"type": "assistant", "requestId": "r1", "timestamp": "2026-09-28T10:00:01Z", "message": {"model": "m", "usage": {
            "input_tokens": 3, "cache_creation_input_tokens": 3900, "cache_read_input_tokens": 0, "output_tokens": 40},
            "content": [{"type": "text", "text": "x"}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "content": "coverage: good"}]}},
        {"type": "assistant", "requestId": "r2", "timestamp": "2026-09-28T10:00:06Z", "message": {"model": "m", "usage": {
            "input_tokens": 10, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 3900, "output_tokens": 60},
            "content": [{"type": "text", "text": "14"}]}},
    ]
    f = tmp_path / "agent-1.jsonl"
    f.write_text("\n".join(json.dumps(x) for x in lines) + "\nnot json\n", encoding="utf-8")
    reqs = bench_core.read_requests(f)
    s = bench_core.usage_sum(reqs)
    assert (s["requests"], s["start_ctx"], s["input"], s["out"]) == (2, 3903, 3903 + 4010, 100)
    assert [t for r in reqs for t in r["tools"]] == ["mcp__kb__kb_pack"] and bench_core.span_s(reqs) == 6.0
    assert round(bench_core.est_cost("haiku", s), 6) == round((13 * 1 + 4000 * 1.25 + 3900 * 0.1 + 100 * 5) / 1e6, 6)


def test_the_shims_are_executable_scripts(tmp_path):
    d = bench_core.shim_dir(tmp_path / "log", tmp_path / "log.jsonl")
    assert "--output-format" in (d / "claude").read_text(encoding="utf-8")
    d = bench_core.shim_dir(tmp_path / "fail")
    assert (d / "claude").read_text(encoding="utf-8").startswith("#!/bin/sh\n")
    if os.name == "nt" and not shutil.which("sh"):  # PowerShell or cmd: Git for Windows puts no usr/bin tool on PATH
        pytest.skip("no sh on PATH (Windows without Git Bash) to run the failing shim")
    start = ["sh"] if os.name == "nt" else []  # Windows cannot exec a #! script; Git for Windows' sh runs it
    assert subprocess.run([*start, str(d / "claude"), "-p"]).returncode == 1


def _fake_real(where):
    """A stand-in for the real claude that prints one result event, so no test reaches the real CLI."""
    where.mkdir(parents=True, exist_ok=True)
    event = '{"result": "from-fake", "total_cost_usd": 0.5, "is_error": false}'
    if os.name == "nt":
        exe = where / "fake-claude.cmd"
        exe.write_text(f"@echo {event}\r\n", encoding="utf-8", newline="")
    else:
        exe = where / "fake-claude"
        exe.write_text(f"#!/bin/sh\ncat >/dev/null\necho '{event}'\n", encoding="utf-8", newline="\n")
        exe.chmod(0o755)
    return exe


def test_the_shim_is_the_claude_that_path_resolves_and_runs(tmp_path):
    # Windows resolves a command only by a PATHEXT extension: an extensionless shim is skipped and the real claude
    # further down PATH runs instead, so which() must find the shim itself, and running what it found runs the shim
    fail = bench_core.shim_dir(tmp_path / "fail")
    found = shutil.which("claude", path=str(fail))
    assert found and Path(found).parent == fail
    assert subprocess.run([found, "-p"], input="", capture_output=True).returncode == 1
    log = tmp_path / "log.jsonl"
    sd = bench_core.shim_dir(tmp_path / "log", log, real=str(_fake_real(tmp_path / "real")))
    found = shutil.which("claude", path=str(sd))
    assert found and Path(found).parent == sd
    p = subprocess.run([found, "-p", "--model", "haiku", "--output-format", "text"], input='{"i": 1}',
                       capture_output=True, text=True)
    assert (p.returncode, p.stdout) == (0, "from-fake")
    [call] = [json.loads(ln) for ln in log.read_text(encoding="utf-8").splitlines()]
    assert (call["items"], call["cost"], call["argv"][:3]) == (1, 0.5, ["-p", "--model", "haiku"])


def test_a_scenario_without_sh_is_skipped_with_the_reason(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(bench_install.shutil, "which", lambda *a, **k: None)
    for scenario in (bench_install.s_kbpy, bench_querylog.s_querylog_hooks):
        with pytest.raises(bench_core.Skip, match="no sh on PATH"):
            scenario(None)

    class FakeBench:  # no Bench: its start asks the real claude for its version
        def __init__(self, scratch, reps):
            self.scratch, self.rows, self.date = Path(scratch), [], "2026-01-01"

        def close(self):
            pass

    monkeypatch.setattr(bm, "Bench", FakeBench)
    monkeypatch.setitem(bench_core.RAW, "path", None)
    monkeypatch.setenv("BENCH_SCRATCH", str(tmp_path / "scratch"))
    out = tmp_path / "results.csv"
    assert bm.main(["run", "kbpy", "--out", str(out)]) == 0
    assert "kbpy: skipped: no sh on PATH" in capsys.readouterr().out
    assert bench_core.read_rows(out) == []


# ---- route-by-verdict

def test_route_by_verdict_is_listed_with_its_section(capsys):
    assert bm.main(["list"]) == 0
    assert re.search(r"^route-by-verdict\s+Routing by verdict against the bare agent$", capsys.readouterr().out, re.M)
    assert bm.SCENARIOS["route-by-verdict"][0] != bm.SCENARIOS["router"][0]  # the older section keeps its name
    assert "route-by-verdict" in bm.__doc__.split("Paid scenarios")[1].split("The rest run no model")[0]
    for case in bench_lookup.RBV_CASES:
        assert case in agent_bench.S and case in agent_bench.WEB_Q, case
    for arm in bench_lookup.RBV_ARMS:
        cfg = arm[4:] if arm.startswith("web-") else arm
        assert cfg == "router-pinned" or cfg in agent_bench.MODEL, arm


def test_the_bar_on_a_web_pack_is_110_percent_of_the_bare_arm():
    assert bench_lookup.verdict_bar("web", 0.11, 0.10, 0.20) == (True, pytest.approx(0.11 / 0.11))
    holds, ratio = bench_lookup.verdict_bar("web", 0.111, 0.10, 0.20)  # planted: one tenth of a cent over the limit
    assert holds is False and ratio > 1
    assert bench_lookup.verdict_bar("web", None, 0.10, 0.20) == (None, None) and bench_lookup.verdict_bar("web", 0.05, None, 0.2) == (None, None)


def test_the_bar_on_a_split_pack_is_below_both_other_arms():
    assert bench_lookup.verdict_bar("split", 0.05, 0.10, 0.08)[0] is True
    assert bench_lookup.verdict_bar("split", 0.09, 0.10, 0.08)[0] is False  # planted: below the web arm, not the kb arm
    assert bench_lookup.verdict_bar("split", 0.08, 0.10, 0.08)[0] is False  # equal is not below
    assert bench_lookup.verdict_bar("split", 0.05, 0.10, None) == (None, None)


def test_the_bar_on_a_good_pack_is_the_reader_route_without_escalation():
    assert bench_lookup.verdict_bar("good", 0.01, 0.2, 0.1) == (True, None)
    assert bench_lookup.verdict_bar("good", 0.06, 0.2, 0.1, escalated=True) == (False, None)  # planted: it escalated
    assert bench_lookup.verdict_bar("tool", 0, 0.2, 0.1) == (None, None)


def test_pack_route_reads_the_first_pack_step():
    assert bench_lookup.pack_route([{"route": ["pack:web", "researcher:m"]}]) == "web"
    assert bench_lookup.pack_route([{"route": ["kb_ask:tool"]}]) == "tool"
    assert bench_lookup.pack_route([{"route": []}, {"error": "x"}]) == ""


def _run(cfg, scen, cost, route=(), wall=10.0):
    return {"cfg": cfg, "scen": scen, "cost": cost, "wall_s": wall, "in_uncached": 10, "cache_write": 0, "cache_read": 0,
            "out": 5, "turns": 2, "tools": {"WebSearch": 1}, "checks": [True], "route": list(route),
            "models": {"claude-sonnet-5-5": cost}}


def _bench(runs):
    b = bench_core.Bench.__new__(bench_core.Bench)  # no claude call: the record's identity is planted
    b.rows, b.reps, b.date, b.record, b.commit, b.cc, b.topics = [], 1, "2026-09-29", "2026-09-29", "abc1234", "2.1.290", "280"
    seen = []
    b.bench = lambda cfgs, scens, reps, tag, parallel=False: seen.append((cfgs, scens, reps, tag, parallel)) or runs
    return b, seen


def test_the_scenario_records_each_cases_route_arms_and_bar():
    runs = []
    for case, kind, router, web, kb in (("s5_none", "web", 0.05, 0.05, 0.06), ("s8_falsegood2", "split", 0.09, 0.10, 0.08),
                                        ("s1_fact", "good", 0.004, 0.06, 0.10)):
        runs += [_run("router-pinned", case, router, [f"pack:{kind}", "reader:m"]), _run("web-sonnet-5-5", case, web),
                 _run("sonnet-5-5", case, kb)]
    b, seen = _bench(runs)
    bench_lookup.s_route_by_verdict(b)
    assert seen == [(bench_lookup.RBV_ARMS, bench_lookup.RBV_CASES, 1, "route-by-verdict", True)]
    got = {(r["case"], r["arm"], r["metric"]): r["value"] for r in b.rows}
    assert got[("s5_none", "router-pinned", "pack_route")] == "web" and got[("s5_none", "router-pinned", "bar")] == "holds"
    assert got[("s8_falsegood2", "router-pinned", "pack_route")] == "split"
    assert got[("s8_falsegood2", "router-pinned", "bar")] == "misses"  # 0.09 is not below the kb arm's 0.08
    assert got[("s1_fact", "router-pinned", "bar")] == "holds" and ("s1_fact", "router-pinned", "limit_ratio") not in got
    assert got[("s5_none", "web-sonnet-5-5", "cost")] == 0.05
    assert {r["scenario"] for r in b.rows} == {"route-by-verdict"}
    assert "0.91x" in bench_report.table(b.rows, "route-by-verdict", ["limit_ratio"], cases=["s5_none"])


def test_navigation_files_read_one_decimal_like_turns_and_tool_calls():
    assert [bench_report.fmt(m, "1.666667") for m in ("files_read", "turns", "tool_calls")] == ["1.7"] * 3
    assert bench_report.fmt("files_read", "2.0") == "2" and bench_report.fmt("files_read", "5.666667") == "5.7"


def test_the_scenario_says_no_data_when_an_arm_failed():
    runs = [_run("router-pinned", "s5_none", 0.05, ["pack:web"]), {"cfg": "web-sonnet-5-5", "scen": "s5_none", "error": "x"},
            _run("sonnet-5-5", "s5_none", 0.06)]
    b, _ = _bench(runs)
    bench_lookup.s_route_by_verdict(b)
    got = {(r["arm"], r["metric"]): r["value"] for r in b.rows if r["case"] == "s5_none"}
    assert got[("router-pinned", "bar")] == "no data" and got[("web-sonnet-5-5", "errors")] == 1


def test_the_routed_runs_have_hooks_off_and_pinned_models(monkeypatch):
    seen = []
    monkeypatch.setattr(agent_bench, "execute", lambda argv, prompt, **kw: seen.append(argv) or {"error": "stop"})
    monkeypatch.setattr(kb_ask, "tool_answer", lambda q: None)
    monkeypatch.setattr(kb_ask, "plan", lambda q, model=None: {"kind": "web", "text": "", "lacks": [], "leads": [], "has": [],
                                                                "model": "sonnet", "verdict": "none", "route": "web"})
    agent_bench.route("q", agent_bench.PIN)
    assert seen and all(_hooks_off(a) for a in seen) and "claude-sonnet-5-5" in seen[0]


# ---- navigation

RIGHT = {"N1": "Functions: ql_deliver.job_verdict\nTests: test_a_timed_out_or_stuck_job_is_red",
         "N2": "Functions: kbgit.lane_plan\nTests: TestLanes::test_branch_id_is_the_first_work_id",
         "N3": "Functions: verdict_bar\nTests: test_the_bar_on_a_split_pack_is_below_both_other_arms"}


def _nav_stream(uses, answer, turns=3, **extra):
    events = [{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": str(i), "name": n, "input": inp}]}}
              for i, (n, inp) in enumerate(uses)]
    events.append({"type": "result", "is_error": False, "result": answer, "num_turns": turns, "total_cost_usd": 0.05,
                   "duration_api_ms": 4000, "usage": {"input_tokens": 10, "cache_creation_input_tokens": 100,
                                                      "cache_read_input_tokens": 1000, "output_tokens": 40},
                   "modelUsage": {"claude-sonnet-5-5": {"costUSD": 0.05}}, **extra})
    return "\n".join(json.dumps(e) for e in events) + "\n"


def test_navigation_is_listed_and_the_report_gives_its_command(capsys):
    assert bm.main(["list"]) == 0
    assert re.search(r"^navigation\s+\S", capsys.readouterr().out, re.M)
    assert "python3 _tools/benchmarks.py run navigation --arm" in bm.REPORT.read_text(encoding="utf-8")
    assert "navigation" in bm.__doc__.split("Paid scenarios")[1].split("The rest run no")[0]


def test_navigation_answers_are_checked_by_function_and_test_names():
    assert {c: bench_lookup.nav_check(c, a) for c, a in RIGHT.items()} == {c: [True, True] for c in bench_lookup.NAV}
    # planted wrong answers: a neighbouring function, a test of another rule, a path instead of names
    wrong = "Functions: ql_deliver.pipeline_verdict\nTests: test_pipeline_verdict_is_red_on_failed"
    assert bench_lookup.nav_check("N1", wrong) == [False, False]
    assert bench_lookup.nav_check("N1", "Functions: job_verdict\nTests: test_job_ran_is_not_a_test_of_this") == [True, False]
    assert bench_lookup.nav_check("N2", "Functions: push_branch\nTests: test_branch_id_is_the_first_work_id") == [False, True]
    assert bench_lookup.nav_check("N3", "_tools/benchmarks.py and _tools/test_benchmarks.py") == [False, False]
    assert bench_lookup.nav_check("N3", "") == [False, False] and bench_lookup.nav_check("N3", None) == [False, False]
    assert bench_lookup.nav_check("N1", "Functions: job_verdicts\nTests: xtest_a_timed_out_or_stuck_job_is_red") == [False, False]  # whole names


def test_navigation_answers_name_code_that_exists_and_the_prompts_do_not_name_it():
    # no backlog tool file: an in-flight change to it is no concern of these names
    text = "\n".join(p.read_text(encoding="utf-8") for p in sorted(bench_core.TOOLS.glob("*.py"))
                     if p.name not in ("backlog.py", "test_backlog.py"))
    for case, spec in bench_lookup.NAV.items():
        assert spec["functions"] and spec["tests"], case
        for name in spec["functions"] + spec["tests"]:
            assert re.search(rf"^\s*def {name}\(", text, re.M), f"{case}: no def {name}"
            assert not bench_lookup.nav_named(name, spec["prompt"] + bench_lookup.NAV_ASK), f"{case}: the prompt names {name}"
        assert all(t.startswith("test_") for t in spec["tests"]) and not any(f.startswith("test_") for f in spec["functions"])


def test_navigation_files_read_are_the_distinct_files_the_tool_calls_name(tmp_path):
    root = tmp_path / "navigation"
    uses = [("Read", {"file_path": str(root / "_tools" / "ql_deliver.py")}), ("Read", {"file_path": "_tools/ql_deliver.py"}),
            ("Grep", {"pattern": "def x", "path": "_tools"}), ("Grep", {"pattern": "y", "path": "_tools/kbgit.py"}),
            ("Glob", {"pattern": "**/*.py"}),
            ("Bash", {"command": "grep -n \"def lane_plan\" _tools/kbgit.py _tools/test_sync.py"}),
            ("Bash", {"command": "sed -n '10,20p' ./kb/_self/backlog.md"}),
            ("Bash", {"command": "grep -rn x _tools/*.py"}), ("Bash", {"command": "echo \"unterminated _tools/x.csv"}),
            ("Read", {"file_path": "_tools/kbgit.py:120"}), ("Read", {}), ("WebFetch", {"url": "https://example.com/a.md"}),
            ("Bash", {}), ("Read", None)]
    assert bench_lookup.nav_files(uses, root) == ["_tools/ql_deliver.py", "_tools/kbgit.py", "_tools/test_sync.py",
                                        "kb/_self/backlog.md", "_tools/x.csv"]


def test_navigation_result_reads_turns_tools_files_and_input_from_the_stream(tmp_path):
    uses = [("Grep", {"pattern": "job_verdict"}), ("Read", {"file_path": "_tools/ql_deliver.py"}),
            ("Read", {"file_path": "_tools/test_querylog.py"})]
    r = bench_lookup.nav_result(_nav_stream(uses, RIGHT["N1"], turns=4), tmp_path / "navigation", 12.34)
    assert (r["turns"], sum(r["tools"].values()), r["files_read"], r["wall_s"]) == (
        4, 3, ["_tools/ql_deliver.py", "_tools/test_querylog.py"], 12.3)
    assert r["in_uncached"] + r["cache_write"] + r["cache_read"] == 1110 and r["out"] == 40 and r["answer"] == RIGHT["N1"]
    assert bench_lookup.nav_result("not json\n", tmp_path, 0) == {"error": "no result event"}
    refused = _nav_stream([], "hit a limit", is_error=True)
    assert bench_lookup.nav_result(refused, tmp_path, 0) == {"error": "hit a limit"}  # a refused run is void, not a cheap answer


def test_navigation_runs_with_hooks_off_read_only_tools_and_no_servers():
    argv = bench_lookup.nav_argv()
    assert _hooks_off(argv) and "--strict-mcp-config" in argv and argv[argv.index("--model") + 1] == "sonnet"
    allowed = argv[argv.index("--allowedTools") + 1:argv.index("--disallowedTools")]
    denied = argv[argv.index("--disallowedTools") + 1:]
    assert not {"Edit", "Write", "NotebookEdit", "Agent", "Task", "WebFetch", "WebSearch"} & set(allowed)
    assert {"Edit", "Write", "Agent", "Task", "WebSearch"} <= set(denied)
    assert not any(w in a for a in allowed for w in ("rm ", "mv ", "tee ", ">", "git commit", "git push"))


def test_navigation_run_takes_the_answer_from_a_fake_claude(tmp_path, monkeypatch):
    seen = {}

    def fake(argv, **kw):
        seen.update(argv=argv, **kw)
        return subprocess.CompletedProcess(argv, 0, _nav_stream([("Read", {"file_path": "_tools/kbgit.py"})], RIGHT["N2"]), "")

    monkeypatch.setattr(bench_lookup.subprocess, "run", fake)
    monkeypatch.setitem(bench_core.RAW, "path", None)
    for k in ("usd", "input", "out", "runs"):
        monkeypatch.setitem(bench_core.SPEND, k, 0)
    r = bench_lookup.nav_run(bench_lookup.nav_argv(), "question", tmp_path / "navigation")
    assert r["answer"] == RIGHT["N2"] and r["files_read"] == ["_tools/kbgit.py"]
    assert seen["input"] == "question" and seen["cwd"] == str(tmp_path / "navigation") and _hooks_off(seen["argv"])
    assert "CLAUDE_PLUGIN_ROOT" not in seen["env"] and bench_core.SPEND["runs"] == 1
    monkeypatch.setattr(bench_lookup.subprocess, "run", lambda argv, **kw: subprocess.CompletedProcess(argv, 1, "", "boom"))
    assert bench_lookup.nav_run(bench_lookup.nav_argv(), "q", tmp_path)["error"] == "no result event: boom"


def _nav_bench(tmp_path, arm="before", reps=1):
    b = bench_core.Bench.__new__(bench_core.Bench)  # no claude call: the record's identity is planted
    b.rows, b.reps, b.date, b.record, b.commit, b.cc, b.topics = [], reps, "2026-09-30", "2026-09-30", "abc1234", "2.1.290", "280"
    b.arm = arm
    b.clone = lambda name, mode="off", **kw: tmp_path / name
    return b


def test_navigation_records_each_cases_checks_files_turns_calls_and_input_under_its_arm(tmp_path, monkeypatch):
    answers = dict(RIGHT, N2="Functions: push_branch\nTests: test_content_only_goes_to_main")  # planted: the wrong code
    files = {"N1": ["_tools/ql_deliver.py", "_tools/test_querylog.py"], "N2": ["_tools/kbgit.py"], "N3": ["_tools/benchmarks.py"]}

    def fake(argv, prompt, cwd):
        case = next(c for c, s in bench_lookup.NAV.items() if prompt.startswith(s["prompt"]))
        return {"wall_s": 5.0, "api_s": 4.0, "cost": 0.05, "turns": 3, "in_uncached": 10, "cache_write": 100,
                "cache_read": 1000, "out": 40, "models": {"claude-sonnet-5-5": 0.05}, "tools": {"Read": len(files[case]) + 1},
                "route": ["Grep"], "files_read": files[case], "answer": answers[case]}

    monkeypatch.setattr(bench_lookup, "nav_run", fake)
    b = _nav_bench(tmp_path)
    bench_lookup.s_navigation(b)
    got = {(r["case"], r["arm"], r["metric"]): r["value"] for r in b.rows}
    assert {r["scenario"] for r in b.rows} == {"navigation"} and {r["arm"] for r in b.rows} == {"before"}
    assert [got[(c, "before", "checks")] for c in ("N1", "N2", "N3")] == ["2/2", "0/2", "2/2"]  # the planted answer: none
    assert [got[(c, "before", "files_read")] for c in ("N1", "N2", "N3")] == [2, 1, 1]
    assert got[("N1", "before", "turns")] == 3 and got[("N1", "before", "tool_calls")] == 3
    assert got[("N1", "before", "input")] == 1110 and got[("N1-N3", "before", "files_read")] == 4
    assert got[("N1-N3", "before", "tool_calls")] == 3 + 2 + 2 and got[("N1-N3", "before", "turns")] == 9
    monkeypatch.setattr(bench_lookup, "nav_run", lambda argv, prompt, cwd: {"error": "boom"})
    b = _nav_bench(tmp_path, arm="after")
    bench_lookup.s_navigation(b)
    got = {(r["case"], r["arm"], r["metric"]): r["value"] for r in b.rows}
    assert got[("N1", "after", "errors")] == 1 and ("N1-N3", "after", "turns") not in got  # no sum from a failed case


def test_navigation_arm_defaults_and_three_runs_are_one_row_each(tmp_path, monkeypatch):
    monkeypatch.setattr(bench_lookup, "nav_run", lambda argv, prompt, cwd: {
        "wall_s": 1.0, "api_s": 1.0, "cost": 0.01, "turns": 2, "in_uncached": 1, "cache_write": 0, "cache_read": 9, "out": 1,
        "models": {}, "tools": {"Read": 2}, "route": [], "files_read": ["a.py", "b.py"],
        "answer": RIGHT[next(c for c, s in bench_lookup.NAV.items() if prompt.startswith(s["prompt"]))]})
    b = _nav_bench(tmp_path, reps=3)
    del b.arm  # a bench with no arm set, as the tests' fakes have
    bench_lookup.s_navigation(b)
    rows = [r for r in b.rows if r["case"] == "N1" and r["metric"] in ("checks", "files_read")]
    assert {(r["arm"], r["metric"], r["value"], r["runs"]) for r in rows} == {("current", "checks", "6/6", 3),
                                                                             ("current", "files_read", 2, 3)}


class _FakeBench(bench_core.Bench):
    def __init__(self, scratch, reps):
        self.scratch, self.reps, self.rows, self.registered, self.arm = Path(scratch), reps, [], [], ""
        self.date = self.record = "2026-09-30"
        self.commit, self.cc, self.topics = "abc1234", "2.1.290", "280"


def test_run_navigation_replaces_only_the_named_arms_rows(tmp_path, monkeypatch):
    calls = []

    def scenario(b):
        calls.append(b.arm)
        b.row("navigation", "N1", b.arm, "turns", len(calls), 1)
        bench_core.spent(1.0, 100, 10)

    monkeypatch.setattr(bm, "Bench", _FakeBench)
    monkeypatch.setitem(bench_core.RAW, "path", None)
    monkeypatch.setitem(bm.SCENARIOS, "navigation", ("Finding the code", scenario))
    monkeypatch.setenv("BENCH_SCRATCH", str(tmp_path / "scratch"))
    for k in ("usd", "input", "out", "runs"):
        monkeypatch.setitem(bench_core.SPEND, k, 0)
    out = tmp_path / "results.csv"
    for arm in ("before", "after", "before"):
        assert bm.main(["run", "navigation", "--arm", arm, "--out", str(out)]) == 0
    assert bm.main(["run", "navigation", "--out", str(out)]) == 0
    assert calls == ["before", "after", "before", "current"]  # the default arm is current
    rows = bench_core.read_rows(out)
    turns = {r["arm"]: r["value"] for r in rows if r["metric"] == "turns"}
    assert turns == {"before": "3", "after": "2", "current": "4"}  # the second `before` replaced the first
    assert sorted(r["arm"] for r in rows if r["metric"] == "spend_usd") == ["after", "before", "current"]
    assert "| navigation | 2026-09-30 | 3 | 300 | 30 | $3.00 |" in bench_report.spend_table(rows)  # one record: every arm's spend
    old = [dict(r, scenario="router") for r in rows if r["arm"] == "before"]
    new = [dict(r, scenario="router", arm="after") for r in rows if r["arm"] == "before"]
    assert bench_core.merge_rows(old, new) == new  # a scenario that is not ARMED is replaced whole, whatever its arms


def test_bench_records_every_arm_of_an_armed_record():
    base = {"scenario": "navigation", "record": "2026-09-30", "date": "2026-09-30", "claude_code": "2.1.286",
            "kb_topics": "292", "case": "all paid runs", "model": "", "runs": "3", "note": ""}
    rows = [dict(base, arm=arm, commit=commit, metric="spend_usd", value=usd)
            for arm, commit, usd in (("before", "aaaaaaa", "0.50"), ("after", "bbbbbbb", "0.25"))]
    text = bench_report.records_table(rows, "navigation")
    assert "| 2026-09-30 (before) | 2026-09-30 | aaaaaaa | 2.1.286 | 292 | - | $0.50 |" in text
    assert "| 2026-09-30 (after) | 2026-09-30 | bbbbbbb | 2.1.286 | 292 | - | $0.25 |" in text
    assert bench_report.ARMED == bench_core.ARMED  # the report module imports no sibling, so the list is copied
    plain = [dict(r, scenario="demo") for r in rows]
    assert bench_report.records_table(plain, "demo").count("\n") == 2  # not armed: one line per record, as before
