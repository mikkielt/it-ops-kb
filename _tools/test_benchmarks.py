"""_tools/benchmarks.py without a paid run: the report's generated tables and README.md's numbers against the results
file, the isolation of every run (hooks off, throwaway clones with a local origin, a plugin copy whose hooks write
under the scratch directory), the transcript reader and the scenario list the report names."""
import json, os, re, subprocess
from pathlib import Path

import pytest

import agent_bench, benchmarks as bm, kb_ask
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
    text = bm.render(REPORT, ROWS)
    assert "| s1 | kb-haiku | $0.030 / $0.032 -> $0.029 (-8%) | 10 s |" in text
    assert "| 2026-09-28 | 2026-09-28 | e4f5a6b | 2.1.290 | 271 | 1 | $0.03 |" in text
    assert bm.render(text, ROWS) == text  # a second render changes nothing
    planted = text.replace("$0.029 (-8%)", "$0.019 (-37%)")
    assert bm.render(planted, ROWS) != planted  # what `report --check` compares


def test_check_fails_on_a_table_that_disagrees(tmp_path, monkeypatch, capsys):
    results, report, readme = tmp_path / "r.csv", tmp_path / "b.md", tmp_path / "README.md"
    bm.write_rows(ROWS, results)
    report.write_text(bm.render(REPORT, ROWS), encoding="utf-8")
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
    assert bm.readme_misses("costs $0.029 and 10 s, 271 topics, on 2.1.290; Haiku 4.5, Apache-2.0", ROWS) == []
    assert bm.readme_misses("costs $0.29 per question", ROWS) == ["$0.29"]
    assert bm.readme_misses("about 28k tokens", ROWS) == ["28k"]
    assert bm.readme_misses("3.8M characters", ROWS) == ["3.8M"]  # a row of 9.8 is not 3.8M


def test_the_committed_report_and_readme_agree_with_the_results():
    rows = bm.read_rows()
    assert rows, "kb/_self/reports/benchmarks.csv is empty"
    text = bm.REPORT.read_text(encoding="utf-8")
    assert bm.render(text, rows) == text, "python3 _tools/benchmarks.py report rewrites the tables"
    assert bm.readme_misses(bm.README.read_text(encoding="utf-8"), rows) == []


def test_the_report_names_every_scenario_and_its_command():
    text = bm.REPORT.read_text(encoding="utf-8")
    for name, (section, _) in bm.SCENARIOS.items():
        assert f"python3 _tools/benchmarks.py run {name}`" in text, name
    for m in bm.BLOCK.finditer(text):
        scen = m.group(3).split()[0] if m.group(3).strip() else ""
        assert m.group(2) == "spend" or scen in bm.SCENARIOS or any(r["scenario"] == scen for r in bm.read_rows()), scen


def test_results_rows_are_complete():
    for r in bm.read_rows():
        assert r["scenario"] and r["record"] and r["metric"], r
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}|", r["date"]), r


def _hooks_off(argv):
    i = next((i for i, a in enumerate(argv) if a == NO_HOOKS[0] and argv[i:i + 2] == NO_HOOKS), None)
    return i is not None


def test_every_claude_run_turns_hooks_off():
    argvs = [agent_bench.kb_argv(c) for c in ("haiku", "opus+delegate", "haiku+escalate", "sonnet+strict")]
    argvs += [agent_bench.web_argv("haiku"), agent_bench.host_argv("haiku", "/kb"), kb_ask.claude_argv("haiku", True),
              kb_ask.claude_argv("haiku", False), bm._task_argv("sonnet")]
    assert all(_hooks_off(a) for a in argvs)
    assert not _hooks_off(["claude", "-p", "--model", "haiku"])  # a run without it is caught


def test_merge_replaces_a_scenario_record():
    new = [dict(ROWS[1], value="0.03")]
    merged = bm.merge_rows(ROWS, new)
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
    bm.isolate(repo.path, "local", bare)
    assert json.loads((Path(repo.path) / "_private" / "querylog.json").read_text(encoding="utf-8"))["mode"] == "local"
    assert repo.git("remote", "get-url", "origin").strip() == str(bare)


def test_plugin_copy_sends_every_hook_to_the_scratch_data_directory(tmp_path):
    src = tmp_path / "src"
    (src / ".claude-plugin").mkdir(parents=True)
    (src / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "it-ops-kb", "hooks": {
        "Stop": [{"hooks": [{"type": "command", "command": "sh \"${CLAUDE_PLUGIN_ROOT}/_tools/kbpy\" _tools/querylog.py capture"}]}],
        "SessionEnd": [{"hooks": [{"type": "command", "command": "sh x launch"}]}]}}), encoding="utf-8")
    data = tmp_path / "data"
    dest = bm.plugin_copy(src, tmp_path / "copy", data)
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
    reqs = bm._requests(f)
    s = bm.usage_sum(reqs)
    assert (s["requests"], s["start_ctx"], s["input"], s["out"]) == (2, 3903, 3903 + 4010, 100)
    assert [t for r in reqs for t in r["tools"]] == ["mcp__kb__kb_pack"] and bm.span_s(reqs) == 6.0
    assert round(bm.est_cost("haiku", s), 6) == round((13 * 1 + 4000 * 1.25 + 3900 * 0.1 + 100 * 5) / 1e6, 6)


def test_the_shims_are_executable_scripts(tmp_path):
    d = bm.shim_dir(tmp_path / "fail")
    start = ["sh"] if os.name == "nt" else []  # Windows cannot exec a #! script; Git for Windows' sh runs it
    assert subprocess.run([*start, str(d / "claude"), "-p"]).returncode == 1
    d = bm.shim_dir(tmp_path / "log", tmp_path / "log.jsonl")
    assert "--output-format" in (d / "claude").read_text(encoding="utf-8")


# ---- route-by-verdict

def test_route_by_verdict_is_listed_with_its_section(capsys):
    assert bm.main(["list"]) == 0
    assert re.search(r"^route-by-verdict\s+Routing by verdict against the bare agent$", capsys.readouterr().out, re.M)
    assert bm.SCENARIOS["route-by-verdict"][0] != bm.SCENARIOS["router"][0]  # the older section keeps its name
    assert "route-by-verdict" in bm.__doc__.split("Paid scenarios")[1].split("The rest run no model")[0]
    for case in bm.RBV_CASES:
        assert case in agent_bench.S and case in agent_bench.WEB_Q, case
    for arm in bm.RBV_ARMS:
        cfg = arm[4:] if arm.startswith("web-") else arm
        assert cfg == "router-pinned" or cfg in agent_bench.MODEL, arm


def test_the_bar_on_a_web_pack_is_110_percent_of_the_bare_arm():
    assert bm.verdict_bar("web", 0.11, 0.10, 0.20) == (True, pytest.approx(0.11 / 0.11))
    holds, ratio = bm.verdict_bar("web", 0.111, 0.10, 0.20)  # planted: one tenth of a cent over the limit
    assert holds is False and ratio > 1
    assert bm.verdict_bar("web", None, 0.10, 0.20) == (None, None) and bm.verdict_bar("web", 0.05, None, 0.2) == (None, None)


def test_the_bar_on_a_split_pack_is_below_both_other_arms():
    assert bm.verdict_bar("split", 0.05, 0.10, 0.08)[0] is True
    assert bm.verdict_bar("split", 0.09, 0.10, 0.08)[0] is False  # planted: below the web arm, not the kb arm
    assert bm.verdict_bar("split", 0.08, 0.10, 0.08)[0] is False  # equal is not below
    assert bm.verdict_bar("split", 0.05, 0.10, None) == (None, None)


def test_the_bar_on_a_good_pack_is_the_reader_route_without_escalation():
    assert bm.verdict_bar("good", 0.01, 0.2, 0.1) == (True, None)
    assert bm.verdict_bar("good", 0.06, 0.2, 0.1, escalated=True) == (False, None)  # planted: it escalated
    assert bm.verdict_bar("tool", 0, 0.2, 0.1) == (None, None)


def test_pack_route_reads_the_first_pack_step():
    assert bm.pack_route([{"route": ["pack:web", "researcher:m"]}]) == "web"
    assert bm.pack_route([{"route": ["kb_ask:tool"]}]) == "tool"
    assert bm.pack_route([{"route": []}, {"error": "x"}]) == ""


def _run(cfg, scen, cost, route=(), wall=10.0):
    return {"cfg": cfg, "scen": scen, "cost": cost, "wall_s": wall, "in_uncached": 10, "cache_write": 0, "cache_read": 0,
            "out": 5, "turns": 2, "tools": {"WebSearch": 1}, "checks": [True], "route": list(route),
            "models": {"claude-sonnet-5-5": cost}}


def _bench(runs):
    b = bm.Bench.__new__(bm.Bench)  # no claude call: the record's identity is planted
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
    bm.s_route_by_verdict(b)
    assert seen == [(bm.RBV_ARMS, bm.RBV_CASES, 1, "route-by-verdict", True)]
    got = {(r["case"], r["arm"], r["metric"]): r["value"] for r in b.rows}
    assert got[("s5_none", "router-pinned", "pack_route")] == "web" and got[("s5_none", "router-pinned", "bar")] == "holds"
    assert got[("s8_falsegood2", "router-pinned", "pack_route")] == "split"
    assert got[("s8_falsegood2", "router-pinned", "bar")] == "misses"  # 0.09 is not below the kb arm's 0.08
    assert got[("s1_fact", "router-pinned", "bar")] == "holds" and ("s1_fact", "router-pinned", "limit_ratio") not in got
    assert got[("s5_none", "web-sonnet-5-5", "cost")] == 0.05
    assert {r["scenario"] for r in b.rows} == {"route-by-verdict"}
    assert "0.91x" in bm.table(b.rows, "route-by-verdict", ["limit_ratio"], cases=["s5_none"])


def test_the_scenario_says_no_data_when_an_arm_failed():
    runs = [_run("router-pinned", "s5_none", 0.05, ["pack:web"]), {"cfg": "web-sonnet-5-5", "scen": "s5_none", "error": "x"},
            _run("sonnet-5-5", "s5_none", 0.06)]
    b, _ = _bench(runs)
    bm.s_route_by_verdict(b)
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
