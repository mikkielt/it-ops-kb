"""_tools/agent_bench.py without a paid run: the stream parser (tool counts, urls a kb tool returned, urls fetched
again), the checks, and the scratch kb copies the host scenarios load (a planted older release, a clone behind its
remote)."""
import json, os

import pytest

import agent_bench as ab
from conftest import Repo, git_env


def ev(kind, content, parent=None):
    return json.dumps({"type": kind, "parent_tool_use_id": parent, "message": {"content": content}})


STREAM = "\n".join([
    ev("assistant", [{"type": "tool_use", "id": "1", "name": "mcp__plugin_it-ops-kb_kb__kb_pack", "input": {"question": "q"}}]),
    ev("user", [{"type": "tool_result", "tool_use_id": "1", "content": [{"type": "text", "text":
        "coverage: good\nsources:\n  -> S1  https://learn.microsoft.com/entra/identity/monitoring-health/reference-reports-data-retention\n"}]}]),
    ev("assistant", [{"type": "tool_use", "id": "2", "name": "WebSearch", "input": {"query": "intune audit log retention"}}]),
    ev("assistant", [{"type": "tool_use", "id": "3", "name": "WebFetch", "input": {
        "url": "https://learn.microsoft.com/en-us/entra/identity/monitoring-health/reference-reports-data-retention/", "prompt": "p"}}]),
    ev("assistant", [{"type": "tool_use", "id": "4", "name": "mcp__plugin_it-ops-kb-docs_microsoft-learn__microsoft_docs_fetch",
                      "input": {"url": "https://learn.microsoft.com/intune/fundamentals/monitor-audit-logs"}}]),
    ev("assistant", [{"type": "tool_use", "id": "5", "name": "Read", "input": {}}], parent="x"),
    "not json",
    json.dumps({"type": "result", "result": "30 days; one year", "total_cost_usd": 0.01}),
])


def test_parse_counts_tools_and_finds_urls_fetched_again():
    seen, res = ab.parse(STREAM)
    assert res["result"] == "30 days; one year"
    assert seen["tools"]["WebFetch"] == 1 and seen["sub_tools"] == {"Read": 1}
    assert seen["searches"] == 1 and len(seen["fetched"]) == 2 and seen["kb_urls"] == 1
    assert seen["refetched"] == ["learn.microsoft.com/entra/identity/monitoring-health/reference-reports-data-retention"]


def test_norm_url_ignores_scheme_locale_query_and_slash():
    assert ab.norm_url("https://www.Learn.microsoft.com/en-us/a/b/?view=x#y") == ab.norm_url("http://learn.microsoft.com/a/b")


def test_checks():
    r = {"answer": "It was added in 2.1.76.", "tools": {"mcp__plugin_it-ops-kb_kb__kb_status": 1},
         "fetched": [], "searches": 0, "refetched": []}
    assert ab.check(r"2\.1\.76", r) and ab.check("tool:kb_status", r) and ab.check("no-refetch", r)
    assert not ab.check("web", r) and not ab.check("tool:kb_show", r)
    assert not ab.check("no-refetch", {**r, "refetched": ["x"]})
    for scen in ab.HOST:
        assert scen in ab.S and ab.HOST[scen] in ("current", "planted", "stale")


def test_plant_rewrites_the_release_only_in_the_copy(tmp_path):
    pub = tmp_path / "kb" / "public"
    (pub / "privacy").mkdir(parents=True)
    (pub / "privacy" / "presidio.md").write_text("latest 2.2.364 (2026-07-22), before it 2.2.363\nretrieved_utc: 2026-09-26\n", encoding="utf-8", newline="\n")
    (pub / "other.md").write_text("Presidio 2.2.364 of 2026-07-22\nsomething else of 2026-07-22\n", encoding="utf-8", newline="\n")
    (pub / "_sources.csv").write_text("id,url,retrieved_utc\nS802,https://pypi.org/pypi/presidio-analyzer/json,2026-09-26\n"
                                      "S900,https://example.com,2026-09-26\n", encoding="utf-8", newline="\n")
    ab.plant(str(tmp_path))
    assert (pub / "privacy" / "presidio.md").read_text(encoding="utf-8") == "latest 2.2.361 (2026-02-12), before it 2.2.360\nretrieved_utc: 2026-02-20\n"
    assert (pub / "other.md").read_text(encoding="utf-8") == "Presidio 2.2.361 of 2026-02-12\nsomething else of 2026-07-22\n"
    assert (pub / "_sources.csv").read_text(encoding="utf-8") == ("id,url,retrieved_utc\nS802,https://pypi.org/pypi/presidio-analyzer/json,2026-02-20\n"
                                                  "S900,https://example.com,2026-09-26\n")


def test_count_checks_read_the_kb_at_check_time(monkeypatch):
    r = {"answer": "There are 2 partial Intune articles: remediations and win32-apps.", "tools": {}}
    monkeypatch.setattr(ab, "partial_articles", lambda d, s: ["public/intune/remediations.md", "public/intune/win32-apps.md"])
    assert ab.check("count:intune:partial", r) and ab.check("list:intune:partial", r)
    monkeypatch.setattr(ab, "partial_articles", lambda d, s: ["public/intune/remediations.md"] * 3)
    assert not ab.check("count:intune:partial", r)
    monkeypatch.setattr(ab, "partial_articles", lambda d, s: [])
    assert ab.check("count:intune:partial", {"answer": "None of them: no intune article is partial.", "tools": {}})
    assert ab.check("list:intune:partial", r)


@pytest.mark.git
def test_stale_puts_the_remote_branch_ahead(tmp_path, monkeypatch):
    for k, v in git_env().items():
        monkeypatch.setenv(k, v)
    repo = Repo(tmp_path)
    repo.git("init", "-q", "-b", "main")
    repo.git("commit", "-q", "--allow-empty", "-m", "kb")
    head = repo.rev("HEAD")
    ab.stale(repo.path, 3)
    assert repo.rev("HEAD") == head
    assert repo.git("rev-list", "--count", "HEAD..origin/main").strip() == "3"
    assert os.listdir(tmp_path) == [".git"]


# ---- route: kb_ask.py's routing as a benchmark run, with `claude` stubbed (no model is called)

PLAN = {"good": {"kind": "good", "verdict": "good", "text": "PACK-GOOD", "route": None, "has": [], "lacks": [],
                 "leads": [], "model": "haiku"},
        "web": {"kind": "web", "verdict": "none", "text": "PACK-WEB", "route": "web", "has": [],
                "lacks": ["Kubernetes autoscaling"], "leads": [("public/x/y.md", "Some title")], "model": "sonnet"},
        "split": {"kind": "split", "verdict": "weak", "text": "PACK-SPLIT", "route": "split", "has": ["LAPS length"],
                  "lacks": ["the Elicitation hook"], "leads": [], "model": "sonnet"}}


@pytest.fixture
def routed(monkeypatch):
    """route() with kb_ask.plan planted and execute recording each run's argv and input, answering from a queue."""
    import kb_ask
    for attr, value in (("READER_MODEL", "haiku"), ("SPLIT_READER", kb_ask.READER + " part"),
                        ("split_prompt", lambda q, p: f"SPLIT {q} has={p['has']} lacks={p['lacks']} {p['text']}")):
        if not hasattr(kb_ask, attr):  # names of the split route, when this tree does not have it yet
            monkeypatch.setattr(kb_ask, attr, value, raising=False)
    web_prompt = kb_ask.web_prompt
    if "whole" not in web_prompt.__code__.co_varnames:
        monkeypatch.setattr(kb_ask, "web_prompt", lambda q, p, whole=False: web_prompt(
            q, {**p, "lacks": [] if whole else p["lacks"]}), raising=False)
    calls = []

    def go(kind, answers, **plan):
        monkeypatch.setattr(kb_ask, "plan", lambda q, model=None: {**PLAN[kind], **plan})
        monkeypatch.setattr(kb_ask, "tool_answer", lambda q: None)
        queue = list(answers)

        def execute(argv, prompt, **kw):
            calls.append((argv, prompt))
            a = queue.pop(0)
            return a if isinstance(a, dict) else {"wall_s": 1, "api_s": 1, "cost": 0.01, "turns": 1, "in_uncached": 1,
                                                  "cache_write": 0, "cache_read": 0, "out": 1, "models": {"m": 0.01},
                                                  "tools": {}, "sub_tools": {}, "route": [], "answer": a}
        monkeypatch.setattr(ab, "execute", execute)
        return calls
    return go


def _model(argv):
    return argv[argv.index("--model") + 1]


def test_route_web_asks_the_no_kb_researcher_with_the_question_and_what_the_kb_lacks(routed):
    import kb_ask
    calls = routed("web", ["live answer"])
    r = ab.route("How do I autoscale?", ab.PIN)
    (argv, prompt), = calls
    assert "--mcp-config" in argv and _model(argv) == "claude-sonnet-5-5" and kb_ask.WEB_RESEARCHER in argv
    assert "The kb lacks: Kubernetes autoscaling" in prompt and "Some title" in prompt and "PACK-WEB" not in prompt
    assert r["route"] == ["pack:web", "researcher:claude-sonnet-5-5"] and r["answer"] == "live answer"
    assert "--verbose" in argv and argv[argv.index("--output-format") + 1] == "stream-json"


def test_route_good_stays_on_the_reader_and_escalates_on_insufficient(routed):
    import kb_ask
    calls = routed("good", ["14 characters"])
    r = ab.route("q")
    assert len(calls) == 1 and "--mcp-config" not in calls[0][0] and _model(calls[0][0]) == "haiku"
    assert r["route"] == ["pack:good", "reader:haiku"]
    calls.clear()
    routed("good", ["INSUFFICIENT: only related", "live answer"])
    r = ab.route("q", ab.PIN)
    assert [_model(a) for a, _ in calls] == ["claude-haiku-4-5", "claude-sonnet-5-5"]
    assert kb_ask.RESEARCHER in calls[1][0] and "PACK-GOOD" in calls[1][1] and "INSUFFICIENT: only related" in calls[1][1]
    assert r["route"] == ["pack:good", "reader:claude-haiku-4-5", "escalate", "researcher:claude-sonnet-5-5"]
    assert r["cost"] == 0.02 and r["turns"] == 2  # the two runs are summed


def test_route_split_reads_the_kb_part_and_researches_the_lacks_part(routed):
    import kb_ask
    calls = routed("split", ["kb part", "live part"])
    r = ab.route("q", ab.PIN)
    (ra, rp), (sa, sp) = calls
    assert _model(ra) == "claude-haiku-4-5" and "--mcp-config" not in ra and "PACK-SPLIT" in rp and "LAPS length" in rp
    assert _model(sa) == "claude-sonnet-5-5" and kb_ask.WEB_RESEARCHER in sa
    assert "The kb lacks: the Elicitation hook" in sp and "PACK-SPLIT" not in sp
    assert r["route"] == ["pack:split", "reader:claude-haiku-4-5", "and", "researcher:claude-sonnet-5-5"]
    assert r["cost"] == 0.02 and r["answer"] == "live part"


def test_route_split_reader_insufficient_gives_the_whole_question_to_the_researcher(routed):
    calls = routed("split", ["INSUFFICIENT: nothing", "live all"])
    r = ab.route("q")
    assert "The kb lacks" not in calls[1][1] and "INSUFFICIENT: nothing" in calls[1][1]
    assert r["route"][2] == "escalate"


def test_route_split_without_a_has_or_lacks_line_is_read_whole_like_good(routed):
    import kb_ask
    calls = routed("split", ["INSUFFICIENT: x", "live"], lacks=[])
    ab.route("q")
    assert calls[0][1] == kb_ask.prompt("q", "PACK-SPLIT") and kb_ask.RESEARCHER in calls[1][0]


def test_route_of_several_parts_reads_the_covered_part_and_researches_the_web_part(monkeypatch):
    """kb_ask's own plan over a planted pack: a covered part beside an uncovered one."""
    import kb_ask
    pack = ("route: split\n# Q1: default LAPS password length\ncoverage: good\n"
            "## public/windows/laps.md  Windows LAPS  [complete, x]\n- public/windows/laps.md:12 14 (DOC S9)\n\n"
            "# Q2: Kubernetes autoscaler on EKS\ncoverage: none\nroute: web\nkb has: Kubernetes\nkb lacks: autoscaler, EKS\n"
            "## public/arch/k8s.md  Kubernetes  [complete, x]\n- public/arch/k8s.md:4 A (DOC S5)")
    monkeypatch.setattr(kb_ask.kbfacts, "pack_many", lambda parts, **kw: {"verdict": "none", "results": [], "text": pack})
    monkeypatch.setattr(kb_ask, "tool_answer", lambda q: None)
    calls = []

    def execute(argv, prompt, **kw):
        calls.append((argv, prompt))
        return {"wall_s": 1, "api_s": 1, "cost": 0.01, "turns": 1, "in_uncached": 1, "cache_write": 0, "cache_read": 0,
                "out": 1, "models": {"m": 0.01}, "tools": {}, "sub_tools": {}, "route": [], "answer": "a"}
    monkeypatch.setattr(ab, "execute", execute)
    r = ab.route("(1) default LAPS password length (2) Kubernetes autoscaler on EKS")
    (_, rp), (_, sp) = calls
    reader = rp.split("The kb lacks")[0].split("Answer only")[-1]
    assert "default LAPS password length" in reader and "Kubernetes" not in reader, rp
    assert "The kb lacks: Kubernetes autoscaler on EKS" in sp and "kb_evidence" not in sp
    assert r["route"] == ["pack:split", "reader:haiku", "and", "researcher:sonnet"]


def test_route_returns_a_failed_run_instead_of_going_on(routed):
    calls = routed("split", [{"error": "boom"}])
    assert ab.route("q") == {"error": "boom"} and len(calls) == 1
    calls.clear()
    routed("web", [{"error": "boom"}])
    assert "error" in ab.route("q")


def test_the_pinned_arms_and_the_bare_question_of_s5_none():
    assert ab.PIN == {"haiku": "claude-haiku-4-5", "sonnet": "claude-sonnet-5-5"}
    assert ab.MODEL["sonnet-5-5"] == "claude-sonnet-5-5"
    q = ab.WEB_Q["s5_none"]
    assert "kubernetes cluster autoscaler" in q.lower() and "Use the kb" not in q and q.endswith("Cite the source urls.")
    assert ab.S["s5_none"][0].startswith(q.replace(" Cite the source urls.", ""))
