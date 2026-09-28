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
