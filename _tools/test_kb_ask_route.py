"""kb_ask.py routes by the pack's `route:` line, tested on planted packs and a planted `claude -p` (never the real CLI).

  TestKbAskRoute   plan() reads route, kb has, kb lacks and the nearest articles from the pack; claude_argv's researcher
                   and reader; each part of several where its own route sends it (a covered part beside an
                   uncovered one, planted and in the real kb); a web run's prompt, its printed result and error result; --route's lines; a split run's
                   reader and researcher, its one answer, the costs -v prints and sums, the reader's INSUFFICIENT and
                   the error results; a `kb has: -` or `kb lacks: -` line read as empty (one part and several); a clean good plan, argv and run stay as they were
"""
import json, subprocess, sys

import pytest

import kb_ask

WEB_PACK = """coverage: none (best article matches 2 of 3 key words: set, wi-fi); not in the kb: aggressiveness, roam
The kb does not cover this. Do not answer from the hits below; say so, or research it with /kb-research.
route: web
kb has: Wi-Fi, setting
kb lacks: Roaming, Aggressiveness

## public/intune/network-profiles.md  Intune network profiles: Wi-Fi, wired 802.1X, VPN  [complete, retrieved 2026-09-27]
- public/intune/network-profiles.md:25 Profile types (DOC S1)
## public/windows/wlan.md  Windows WLAN AutoConfig  [complete, retrieved 2026-09-27]
- public/windows/wlan.md:9 A profile names the SSID (DOC S2)
## public/windows/wifi-drivers.md  Wi-Fi driver settings  [partial, retrieved 2026-09-27]
- public/windows/wifi-drivers.md:3 Drivers (DOC S3)
## public/auth/kerberos.md  Kerberos  [complete, retrieved 2026-09-27]
- public/auth/kerberos.md:1 A fourth article (DOC S4)

sources:
  -> S1  https://learn.microsoft.com/example"""

SPLIT_PACK = """coverage: weak (best article matches 3 of 5 key words: laps, password, length)
route: split
kb has: LAPS, password
kb lacks: Okta, rotation

## public/windows/laps.md  Windows LAPS  [complete, retrieved 2026-09-27]
- public/windows/laps.md:12 The default password length is 14 (DOC S9)"""

GOOD_PACK = """coverage: good (best article matches 4 of 4 key words)

## public/windows/laps.md  Windows LAPS  [complete, retrieved 2026-09-27]
- public/windows/laps.md:12 The default password length is 14 (DOC S9)"""

MULTI_PACK = """route: split
# Q1: default LAPS password length
coverage: good
## public/windows/laps.md  Windows LAPS  [complete, retrieved 2026-09-27]
- public/windows/laps.md:12 The default password length is 14 (DOC S9)

# Q2: Okta rotation
coverage: none
route: web
kb has: rotation
kb lacks: Okta
## public/auth/scim.md  SCIM provisioning  [partial, retrieved 2026-09-27]
- public/auth/scim.md:4 A line (DOC S5)"""

MIXED_PACK = """route: split
# Q1: default LAPS password length
coverage: good
## public/windows/laps.md  Windows LAPS  [complete, retrieved 2026-09-27]
- public/windows/laps.md:12 The default password length is 14 (DOC S9)

# Q2: LAPS password rotation in Okta
coverage: weak
route: split
kb has: LAPS, password
kb lacks: Okta
## public/windows/laps.md  Windows LAPS  [complete, retrieved 2026-09-27]
- public/windows/laps.md:14 Rotation (DOC S9)

# Q3: Kubernetes autoscaler on EKS
coverage: none
route: web
kb has: Kubernetes
kb lacks: autoscaler, EKS
## public/arch/k8s.md  Kubernetes  [complete, retrieved 2026-09-27]
- public/arch/k8s.md:4 A line (DOC S5)"""

Q = "What is the Intel Wi-Fi Roaming Aggressiveness setting?"


def plant(monkeypatch, text, verdict):
    monkeypatch.setattr(kb_ask.kbfacts, "pack_many", lambda parts, **kw: {"verdict": verdict, "results": [], "text": text})


def flag(argv, name):
    return argv[argv.index(name) + 1]


def all_values(argv, name):
    """Every value after `name` up to the next flag (a variadic option)."""
    out = []
    for a in argv[argv.index(name) + 1:]:
        if a.startswith("--"):
            break
        out.append(a)
    return out


def result(**kw):
    return json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "the answer",
                       "total_cost_usd": 0.0123, **kw})


class Claude:
    """A planted `claude -p`: records each argv and stdin, answers with the next planted stdout."""

    def __init__(self, monkeypatch, *outs):
        self.calls, self.outs = [], list(outs)
        monkeypatch.setattr(kb_ask.shutil, "which", lambda name: "/planted/claude")
        monkeypatch.setattr(subprocess, "run", self.run)

    def run(self, argv, **kw):
        assert argv[0] == "claude" and kw.get("input") is not None, argv
        self.calls.append((argv, kw["input"]))
        return subprocess.CompletedProcess(argv, 0, self.outs.pop(0), "")


def ask(monkeypatch, capsys, *args):
    monkeypatch.setattr(sys, "argv", ["kb_ask.py", *args])
    row = {}
    code = kb_ask.run(row)
    out = capsys.readouterr()
    return code, out.out, out.err, row


class TestKbAskRoute:
    def test_plan_web_reads_the_route_has_lacks_and_three_leads(self, monkeypatch):
        plant(monkeypatch, WEB_PACK, "none")
        p = kb_ask.plan(Q)
        assert (p["kind"], p["route"], p["verdict"], p["model"]) == ("web", "web", "none", "sonnet")
        assert p["has"] == ["Wi-Fi, setting"] and p["lacks"] == ["Roaming, Aggressiveness"]
        assert p["leads"] == [("public/intune/network-profiles.md", "Intune network profiles: Wi-Fi, wired 802.1X, VPN"),
                              ("public/windows/wlan.md", "Windows WLAN AutoConfig"),
                              ("public/windows/wifi-drivers.md", "Wi-Fi driver settings")], "the first three articles"

    def test_plan_split(self, monkeypatch):
        plant(monkeypatch, SPLIT_PACK, "weak")
        p = kb_ask.plan("What is the default LAPS password length and its Okta rotation?")
        assert (p["kind"], p["route"], p["model"]) == ("split", "split", "sonnet")
        assert p["has"] == ["LAPS, password"] and p["lacks"] == ["Okta, rotation"]

    def test_plan_a_pack_of_several_parts_follows_its_overall_route_line(self, monkeypatch):
        plant(monkeypatch, MULTI_PACK, "none")
        p = kb_ask.plan("(1) default LAPS password length; (2) Okta rotation")
        assert p["kind"] == "split", p
        assert p["has"] == ["default LAPS password length"] and p["lacks"] == ["Okta rotation"], \
            "the covered part to the reader, the web part whole to the researcher, never its kb has words to the reader"

    def test_plan_sends_each_part_of_several_where_its_own_route_sends_it(self, monkeypatch):
        plant(monkeypatch, MIXED_PACK, "none")
        p = kb_ask.plan("(1) default LAPS password length (2) LAPS password rotation in Okta (3) Kubernetes autoscaler on EKS")
        assert p["kind"] == "split"
        assert p["has"] == ["default LAPS password length", "LAPS, password"], p
        assert p["lacks"] == ["Okta", "Kubernetes autoscaler on EKS"], p
        assert "Kubernetes" not in " ".join(p["has"]), "a web part's kb has words never go to the reader"
        reader = kb_ask.split_prompt("q", p).split("The kb lacks")[0].split("Answer only")[-1]
        assert "default LAPS password length" in reader and "Kubernetes" not in reader

    def test_plan_a_pack_of_several_web_parts_gives_every_part_to_the_researcher(self, monkeypatch):
        text = MULTI_PACK.replace("# Q1: default LAPS password length\ncoverage: good\n",
                                  "# Q1: default LAPS password length\ncoverage: none\nroute: web\nkb has: LAPS\nkb lacks: length\n")
        plant(monkeypatch, text.replace("route: split", "route: web", 1), "none")
        p = kb_ask.plan("(1) default LAPS password length; (2) Okta rotation")
        assert (p["kind"], p["has"], p["lacks"]) == ("web", [], ["default LAPS password length", "Okta rotation"]), p

    def test_the_real_pack_of_a_covered_part_beside_an_uncovered_one_reads_the_covered_part(self):
        q = ("(1) What is the default Windows LAPS password length? (2) How do I run the Kubernetes Cluster Autoscaler "
             "on AWS EKS with spot instances?")
        p = kb_ask.plan(q)
        assert p["kind"] == "split" and len(p["parts"]) == 2, p
        assert any("LAPS" in h for h in p["has"]) and not any("Kubernetes" in h for h in p["has"]), p["has"]
        assert any("Autoscaler" in x for x in p["lacks"]), p["lacks"]

    def test_plan_a_weak_or_none_pack_without_a_route_line_is_split(self, monkeypatch):
        for verdict in ("weak", "none"):
            plant(monkeypatch, f"coverage: {verdict}\n\n## public/windows/laps.md  Windows LAPS  [complete, x]\n", verdict)
            p = kb_ask.plan(Q)
            assert (p["kind"], p["route"], p["has"], p["lacks"]) == ("split", "split", [], [])

    def test_a_clean_good_plan_is_unchanged(self, monkeypatch):
        plant(monkeypatch, GOOD_PACK, "good")
        p = kb_ask.plan(Q)
        assert (p["kind"], p["route"], p["model"], p["text"]) == ("good", None, "haiku", GOOD_PACK)
        assert p["has"] == [] and p["lacks"] == []
        assert kb_ask.plan(Q, "opus")["model"] == "opus"

    def test_the_real_pack_of_a_covered_question_plans_good(self):
        p = kb_ask.plan("Does deleting an Entra device also delete its BitLocker recovery keys?")
        assert (p["kind"], p["route"], p["model"]) == ("good", None, "haiku")

    def test_researcher_argv(self):
        argv = kb_ask.claude_argv("sonnet", True, output="json")
        assert argv[:2] == ["claude", "-p"] and flag(argv, "--model") == "sonnet" and flag(argv, "--effort") == "low"
        assert flag(argv, "--tools") == "WebSearch,WebFetch" and flag(argv, "--output-format") == "json"
        assert all_values(argv, "--allowedTools")[:2] == ["WebSearch", "WebFetch"]
        assert all_values(argv, "--allowedTools")[2:] == kb_ask.DOCS
        assert argv.count("--mcp-config") == 1 and flag(argv, "--mcp-config") == kb_ask.DOCS_MCP, "the docs servers only"
        assert "--strict-mcp-config" in argv and "--setting-sources" in argv
        blob = " ".join(argv)
        assert "mcp__kb" not in blob and "kb_mcp" not in blob and '"kb"' not in blob, "no kb server"
        assert "submit_feedback" not in blob
        assert '"disableAllHooks"' in blob, "hooks off"

    def test_researcher_argv_leaves_the_output_format_to_a_caller_that_sets_its_own(self):
        assert "--output-format" not in kb_ask.claude_argv("sonnet", True)  # agent_bench.route adds stream-json

    def test_reader_argv_has_no_effort_and_no_tools(self):
        argv = kb_ask.claude_argv("haiku", tools=False)
        assert "--effort" not in argv and "--mcp-config" not in argv and "--allowedTools" not in argv
        assert flag(argv, "--tools") == "" and flag(argv, "--model") == "haiku"
        assert argv == ["claude", "-p", "--no-session-persistence", "--model", "haiku", *kb_ask.LEAN, "--tools", ""]
        assert kb_ask.claude_argv("haiku", False, output="json")[-2:] == ["--output-format", "json"]

    def test_web_prompt_carries_the_question_the_lacks_line_and_the_leads(self, monkeypatch):
        plant(monkeypatch, WEB_PACK, "none")
        text = kb_ask.web_prompt(Q, kb_ask.plan(Q))
        assert text.startswith(f"Question: {Q}\n\nThe kb lacks: Roaming, Aggressiveness\n")
        assert "- Windows WLAN AutoConfig (public/windows/wlan.md)" in text
        assert "Kerberos" not in text and "kb_evidence" not in text and "public/windows/wlan.md:9" not in text, \
            "the leads are titles, not the pack"

    def test_route_prints_kind_web_with_the_route_has_and_lacks_lines(self, monkeypatch, capsys):
        plant(monkeypatch, WEB_PACK, "none")
        code, out, _, row = ask(monkeypatch, capsys, "--route", Q)
        assert code == 0 and row["route"] == "plan"
        assert out.splitlines() == ["kind=web verdict=none parts=1 model=sonnet", f"part 1: {Q}", "route: web",
                                    "kb has: Wi-Fi, setting", "kb lacks: Roaming, Aggressiveness"]

    def test_route_prints_kind_split_and_a_clean_good_plan_prints_no_route_lines(self, monkeypatch, capsys):
        plant(monkeypatch, SPLIT_PACK, "weak")
        out = ask(monkeypatch, capsys, "--route", Q)[1]
        assert out.startswith("kind=split verdict=weak parts=1 model=sonnet") and "route: split" in out
        assert "kb has: LAPS, password" in out and "kb lacks: Okta, rotation" in out
        plant(monkeypatch, GOOD_PACK, "good")
        assert ask(monkeypatch, capsys, "--route", Q)[1].splitlines() == [
            "kind=good verdict=good parts=1 model=haiku", f"part 1: {Q}"]

    def test_a_web_run_prints_the_result_and_runs_one_researcher(self, monkeypatch, capsys):
        plant(monkeypatch, WEB_PACK, "none")
        claude = Claude(monkeypatch, result())
        code, out, err, row = ask(monkeypatch, capsys, "-v", Q)
        assert code == 0 and out == "the answer\n"
        assert "total_cost_usd=0.0123" in err
        (argv, stdin), = claude.calls
        assert flag(argv, "--model") == "sonnet" and flag(argv, "--effort") == "low" and flag(argv, "--output-format") == "json"
        assert flag(argv, "--append-system-prompt") == kb_ask.WEB_RESEARCHER and "mcp__kb" not in " ".join(argv)
        assert stdin == kb_ask.web_prompt(Q, kb_ask.plan(Q))
        assert row["route"] == "web" and "cost" not in row and not any("cost" in k for k in row), row

    def test_a_web_run_honours_the_model_override(self, monkeypatch, capsys):
        plant(monkeypatch, WEB_PACK, "none")
        claude = Claude(monkeypatch, result())
        ask(monkeypatch, capsys, "--model", "opus", Q)
        assert flag(claude.calls[0][0], "--model") == "opus"

    def test_a_web_error_result_prints_its_errors_and_exits_1(self, monkeypatch, capsys):
        plant(monkeypatch, WEB_PACK, "none")
        Claude(monkeypatch, json.dumps({"type": "result", "subtype": "error_max_turns", "is_error": True,
                                        "errors": ["ran out of turns", "second"], "total_cost_usd": 0.5}))
        code, out, err, _ = ask(monkeypatch, capsys, Q)
        assert code == 1 and out == "" and err == "ran out of turns\nsecond\n"

    def test_a_web_run_without_a_json_result_stops(self, monkeypatch, capsys):
        plant(monkeypatch, WEB_PACK, "none")
        Claude(monkeypatch, "not json")
        with pytest.raises(SystemExit):
            ask(monkeypatch, capsys, Q)

    def test_a_split_run_reads_the_kb_part_researches_the_rest_and_prints_one_answer(self, monkeypatch, capsys):
        plant(monkeypatch, SPLIT_PACK, "weak")
        claude = Claude(monkeypatch, result(result="The default length is 14 (public/windows/laps.md:12, DOC S9).",
                                            total_cost_usd=0.001),
                        result(result="Okta rotation: see https://example.com/okta", total_cost_usd=0.02))
        code, out, err, row = ask(monkeypatch, capsys, "-v", Q)
        (r_argv, r_in), (w_argv, w_in) = claude.calls
        p = kb_ask.plan(Q)
        assert code == 0 and out == ("The default length is 14 (public/windows/laps.md:12, DOC S9).\n\n"
                                     "Live docs, not in the kb:\nOkta rotation: see https://example.com/okta\n")
        assert flag(r_argv, "--model") == "haiku" and "--effort" not in r_argv and flag(r_argv, "--tools") == ""
        assert flag(r_argv, "--output-format") == "json" and flag(r_argv, "--append-system-prompt") == kb_ask.SPLIT_READER
        assert r_in == kb_ask.split_prompt(Q, p) and SPLIT_PACK in r_in
        assert "Answer only the part the kb has: LAPS, password" in r_in and "The kb lacks: Okta, rotation" in r_in
        assert flag(w_argv, "--model") == "sonnet" and flag(w_argv, "--effort") == "low"
        assert flag(w_argv, "--append-system-prompt") == kb_ask.WEB_RESEARCHER and "mcp__kb" not in " ".join(w_argv)
        assert w_in == kb_ask.web_prompt(Q, p) and "kb_evidence" not in w_in and "The kb lacks: Okta, rotation" in w_in
        assert "reader haiku total_cost_usd=0.001" in err and "researcher sonnet total_cost_usd=0.02" in err
        assert "total_cost_usd=0.021 (reader + researcher)" in err
        assert row["route"] == "split" and "escalated" not in row and not any("cost" in k for k in row), row

    def test_a_split_run_of_several_parts_reads_the_covered_part_and_researches_the_web_part(self, monkeypatch, capsys):
        plant(monkeypatch, MULTI_PACK, "none")
        q = "(1) default LAPS password length; (2) Okta rotation"
        claude = Claude(monkeypatch, result(result="14 (public/windows/laps.md:12)."), result(result="Okta: live"))
        code, out, _, row = ask(monkeypatch, capsys, q)
        (_, r_in), (_, w_in) = claude.calls
        assert code == 0 and out == "14 (public/windows/laps.md:12).\n\nLive docs, not in the kb:\nOkta: live\n"
        assert "Answer only the part the kb has: default LAPS password length. The kb lacks: Okta rotation." in r_in
        assert "The kb lacks: Okta rotation" in w_in and "kb_evidence" not in w_in and row["route"] == "split"

    def test_a_split_run_without_v_prints_no_cost(self, monkeypatch, capsys):
        plant(monkeypatch, SPLIT_PACK, "weak")
        Claude(monkeypatch, result(), result())
        assert "total_cost_usd" not in ask(monkeypatch, capsys, Q)[2]

    def test_a_split_run_honours_the_model_override_for_the_researcher_only(self, monkeypatch, capsys):
        plant(monkeypatch, SPLIT_PACK, "weak")
        claude = Claude(monkeypatch, result(), result())
        ask(monkeypatch, capsys, "--model", "opus", Q)
        assert [flag(argv, "--model") for argv, _ in claude.calls] == ["haiku", "opus"]

    def test_a_split_reader_insufficient_sends_the_whole_question_to_the_researcher(self, monkeypatch, capsys):
        plant(monkeypatch, SPLIT_PACK, "weak")
        claude = Claude(monkeypatch, result(result="INSUFFICIENT: the length of the LAPS password", total_cost_usd=0.001),
                        result(result="live answer, https://example.com/laps", total_cost_usd=0.03))
        code, out, err, row = ask(monkeypatch, capsys, "-v", Q)
        (_, _), (w_argv, w_in) = claude.calls
        assert code == 0 and out == "live answer, https://example.com/laps\n", "the researcher's answer only"
        assert row["route"] == "split" and row["escalated"] is True
        assert w_in.startswith(f"Question: {Q}") and "The kb lacks" not in w_in, "the whole question, not the lacks part"
        assert "INSUFFICIENT: the length of the LAPS password" in w_in and "kb_evidence" not in w_in
        assert flag(w_argv, "--append-system-prompt") == kb_ask.WEB_RESEARCHER and flag(w_argv, "--effort") == "low"
        assert "total_cost_usd=0.031 (reader + researcher)" in err

    def test_a_split_reader_error_result_stops_before_the_researcher(self, monkeypatch, capsys):
        plant(monkeypatch, SPLIT_PACK, "weak")
        claude = Claude(monkeypatch, json.dumps({"type": "result", "subtype": "error_during_execution", "is_error": True,
                                                 "errors": ["reader failed"], "total_cost_usd": 0.001}))
        code, out, err, row = ask(monkeypatch, capsys, Q)
        assert code == 1 and out == "" and err == "reader failed\n" and len(claude.calls) == 1 and row["route"] == "split"

    def test_a_split_researcher_error_result_keeps_the_kb_part_and_exits_1(self, monkeypatch, capsys):
        plant(monkeypatch, SPLIT_PACK, "weak")
        Claude(monkeypatch, result(result="The default length is 14."),
               json.dumps({"type": "result", "subtype": "error_max_turns", "is_error": True, "errors": ["ran out of turns"],
                           "total_cost_usd": 0.5}))
        code, out, err, _ = ask(monkeypatch, capsys, "-v", Q)
        assert code == 1 and out == "The default length is 14.\n" and "ran out of turns\n" in err
        assert "total_cost_usd=0.5" in err, "the failed run still costs"

    def test_a_split_run_without_a_json_result_stops(self, monkeypatch, capsys):
        plant(monkeypatch, SPLIT_PACK, "weak")
        Claude(monkeypatch, "The default length is 14.\n")  # a plain-text reader answer is not a result object
        with pytest.raises(SystemExit):
            ask(monkeypatch, capsys, Q)

    def test_cost_sum_skips_a_run_without_a_cost(self):
        assert kb_ask.cost_sum(0.1, 0.2) == 0.3 and kb_ask.cost_sum(None, 0.2) == 0.2 and kb_ask.cost_sum(None, None) is None

    def test_a_split_pack_without_a_has_or_lacks_line_is_read_whole_and_escalates_on_insufficient(self, monkeypatch, capsys):
        text = "coverage: weak\n\n## public/windows/laps.md  Windows LAPS  [complete, x]\n- public/windows/laps.md:12 A (DOC S9)"
        plant(monkeypatch, text, "weak")
        claude = Claude(monkeypatch, "The default length is 14.\n")
        code, out, _, row = ask(monkeypatch, capsys, Q)
        (argv, stdin), = claude.calls
        assert code == 0 and out == "The default length is 14.\n" and row["route"] == "split"
        assert argv == kb_ask.claude_argv("haiku", False) + ["--append-system-prompt", kb_ask.READER]
        assert stdin == kb_ask.prompt(Q, text)
        claude = Claude(monkeypatch, "INSUFFICIENT: the port\n", result())
        code, out, _, row = ask(monkeypatch, capsys, Q)
        assert code == 0 and out == "the answer\n" and row["escalated"] is True and row["route"] == "split"
        assert [flag(argv, "--model") for argv, _ in claude.calls] == ["haiku", "sonnet"]

    def test_a_dash_has_or_lacks_line_is_empty_and_the_split_pack_is_read_whole(self, monkeypatch, capsys):
        for side in ("has", "lacks"):
            text = SPLIT_PACK.replace(f"kb {side}: " + ("LAPS, password" if side == "has" else "Okta, rotation"),
                                      f"kb {side}: -")
            assert f"kb {side}: -" in text
            plant(monkeypatch, text, "weak")
            p = kb_ask.plan(Q)
            assert p["kind"] == "split" and "-" not in p["has"] + p["lacks"], p
            assert p[side] == [] and p["lacks" if side == "has" else "has"] != [], p
            claude = Claude(monkeypatch, "The default length is 14.\n")
            code, out, _, row = ask(monkeypatch, capsys, Q)
            (argv, stdin), = claude.calls
            assert code == 0 and out == "The default length is 14.\n" and row["route"] == "split"
            assert argv == kb_ask.claude_argv("haiku", False) + ["--append-system-prompt", kb_ask.READER], \
                "read whole, not divided"
            assert stdin == kb_ask.prompt(Q, text)
            route = ask(monkeypatch, capsys, "--route", Q)[1]
            assert f"kb {side}: -" not in route and "kb has: -" not in route and "kb lacks: -" not in route, route

    def test_a_web_pack_with_a_dash_lacks_line_never_tells_the_researcher_the_kb_lacks_dash(self, monkeypatch):
        text = WEB_PACK.replace("kb has: Wi-Fi, setting", "kb has: -").replace("kb lacks: Roaming, Aggressiveness",
                                                                               "kb lacks: -")
        plant(monkeypatch, text, "none")
        p = kb_ask.plan(Q)
        assert (p["kind"], p["has"], p["lacks"]) == ("web", [], []), p
        prompt = kb_ask.web_prompt(Q, p)
        assert "The kb lacks" not in prompt and prompt.startswith(f"Question: {Q}\n\nNearest kb articles"), prompt

    def test_a_split_part_of_several_with_a_dash_side_gives_only_its_other_side(self, monkeypatch, capsys):
        text = MIXED_PACK.replace("kb has: LAPS, password\nkb lacks: Okta\n", "kb has: LAPS, password\nkb lacks: -\n")
        text += ("\n\n# Q4: Okta rotation\ncoverage: weak\nroute: split\nkb has: -\nkb lacks: Okta, rotation\n"
                 "## public/auth/scim.md  SCIM provisioning  [partial, x]\n- public/auth/scim.md:4 A line (DOC S5)")
        plant(monkeypatch, text, "none")
        p = kb_ask.plan("(1) a (2) b (3) c (4) d")
        assert p["has"] == ["default LAPS password length", "LAPS, password"], p
        assert p["lacks"] == ["Kubernetes autoscaler on EKS", "Okta, rotation"], p
        sp = kb_ask.split_prompt("q", p).split("<kb_evidence>")[0]
        assert "The kb lacks: Kubernetes autoscaler on EKS; Okta, rotation." in sp and "; -" not in sp and ": -" not in sp
        assert "The kb lacks: -" not in kb_ask.web_prompt("q", p)
        claude = Claude(monkeypatch, result(result="kb part"), result(result="live part"))
        code, out, _, _ = ask(monkeypatch, capsys, "(1) a (2) b (3) c (4) d")
        (_, r_in), (_, w_in) = claude.calls
        assert code == 0 and "kb part" in out and "live part" in out
        assert "The kb lacks: -" not in r_in.split("<kb_evidence>")[0] and "The kb lacks: -" not in w_in

    def test_a_clean_good_run_still_reads_and_escalates_on_insufficient(self, monkeypatch, capsys):
        plant(monkeypatch, GOOD_PACK, "good")
        claude = Claude(monkeypatch, "The default length is 14 (public/windows/laps.md:12).\n")
        code, out, _, row = ask(monkeypatch, capsys, Q)
        (argv, stdin), = claude.calls
        assert code == 0 and out.startswith("The default length is 14")
        assert argv == kb_ask.claude_argv("haiku", False) + ["--append-system-prompt", kb_ask.READER]
        assert stdin == kb_ask.prompt(Q, GOOD_PACK) and row["route"] == "good" and "escalated" not in row
        claude = Claude(monkeypatch, "INSUFFICIENT: the port\n", result())
        code, out, _, row = ask(monkeypatch, capsys, Q)
        assert code == 0 and out == "the answer\n" and row["escalated"] is True and row["model"] == "sonnet"
        (_, _), (argv2, stdin2) = claude.calls
        assert flag(argv2, "--model") == "sonnet" and "--tools" in argv2 and "mcp__kb" not in " ".join(argv2)
        assert stdin2.startswith(kb_ask.prompt(Q, GOOD_PACK)) and "INSUFFICIENT: the port" in stdin2
