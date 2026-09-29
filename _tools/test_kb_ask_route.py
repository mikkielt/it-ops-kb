"""kb_ask.py routes by the pack's `route:` line, tested on planted packs and a planted `claude -p` (never the real CLI).

  TestKbAskRoute   plan() reads route, kb has, kb lacks and the nearest articles from the pack; claude_argv's researcher
                   and reader; a web run's prompt, its printed result and error result; --route's lines; a clean good
                   plan, argv and run stay as they were
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
        assert p["kind"] == "split" and p["has"] == ["rotation"] and p["lacks"] == ["Okta"], p

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

    def test_a_split_run_still_gives_the_researcher_the_whole_pack(self, monkeypatch, capsys):
        plant(monkeypatch, SPLIT_PACK, "weak")
        claude = Claude(monkeypatch, result())
        code, out, _, row = ask(monkeypatch, capsys, Q)
        (argv, stdin), = claude.calls
        assert code == 0 and out == "the answer\n" and row["route"] == "split"
        assert stdin == kb_ask.prompt(Q, SPLIT_PACK) and flag(argv, "--append-system-prompt") == kb_ask.RESEARCHER

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
