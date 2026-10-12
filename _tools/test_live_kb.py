"""The checks the kb's content lives by, over the live kb: check.py (sources, citations, tags), build_index.py --check
(the generated index), the lookup eval (rag.py eval), the pack format and the questions it routes by kind to the tool that holds the answer, and the plugin's one set of the sprint text. Each gate also fails on a planted input. The pack
index's unit cache is pinned on a planted fixture root, not on the live kb."""
import argparse, collections, csv, hashlib, json, os, re, sqlite3, subprocess, sys, time
from pathlib import Path

import pytest

import bench_pool, bench_retrieval, census, factdiff, kb_hook, kbcommon, kbfacts, kbid, provider, rag, selfdoc
from conftest import TOOLS, tool

EVAL_CSV = os.path.join(kbcommon.PUBLIC, kbcommon.DATA_DIR, "lookup_eval.csv")
SID = "FXT-" + "a" * 8  # not a source of the fixture root's _sources.csv
# the kb's entries for the sprint skills and the worker, each a link to the plugin's file: the text exists once
ONE_SET = {".claude/skills/kb-sprint/SKILL.md": "skills/sprint/SKILL.md",
           ".claude/skills/kb-item/SKILL.md": "skills/item/SKILL.md",
           ".claude/skills/kb-backlog/SKILL.md": "skills/backlog/SKILL.md",
           ".claude/agents/kb-worker.md": "agents/worker.md"}


def eval_rows():
    with open(EVAL_CSV, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def good_row():
    """A live eval row that expects one article and a good verdict."""
    return next(r for r in eval_rows() if r["expect_verdict"] == "good" and r["expect_paths"].count(";") == 0
                and r["expect_paths"] and not r["allow_weak"])


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def fixture_root(path, cited):
    """The smallest root check.py accepts: one article citing `cited`, an empty source ledger."""
    write(path / "_root.md", "---\nroot: fixture\nid_prefix: FXT\nvisibility: internal\ndescription: a test root\n---\n")
    write(path / "print" / "queues.md",
          "---\ntopic: print/queues\npriority: P1\napplies_to: \"PL-SRV-0042 print servers\"\nretrieved_utc: 2026-09-26\n"
          f"sources: [{cited}]\nstatus: partial\n---\n\n# Print queues\n\n## Summary\nKept 14 days.\n\n## Facts\n"
          f"- Finished jobs are kept for 14 days. [DOC {cited}]\n\n## Reference\n\n## Examples\n")
    write(path / "_sources.csv", "id,url,title,publisher,licence,reuse,retrieved_utc,version_or_date,artifact_sha256,"
                                 "used_in,superseded_by\n")
    for name in ("_answers.md", "_conflicts.md"):
        write(path / name, "# " + name + "\n")
    write(path / "_gaps.md", "# Gaps\n")


def test_check_py_passes_on_the_live_kb():
    code, out = tool("check.py")
    assert code == 0, out[-3000:]


def test_check_py_names_an_article_citing_an_unknown_source(tmp_path):
    root = tmp_path / "root"
    fixture_root(root, SID)
    env = {**os.environ, "KB_ROOTS": str(root)}
    code, out = tool("check.py", "--root", "fixture", env=env)
    assert code == 1 and "print/queues.md" in out and f"cites unknown source {SID}" in out, out[-2000:]


def test_check_py_names_a_ledger_citation_of_a_line_that_is_no_fact(tmp_path):
    root = tmp_path / "root"
    fixture_root(root, SID)
    lines = (root / "print" / "queues.md").read_text(encoding="utf-8").split("\n")
    fact, heading = (lines.index(x) + 1 for x in (f"- Finished jobs are kept for 14 days. [DOC {SID}]", "## Reference"))
    write(root / "_answers.md", f"# _answers.md\n\n- Jobs are kept 14 days. (`print/queues.md:{fact}`, `:{heading}`) [DOC {SID}]\n"
          f"- Jobs are kept 14 days. (`print/queues.md:{fact}-{fact}`, `print/queues.md:{fact}-{heading}`) [DOC {SID}]\n")
    env = {**os.environ, "KB_ROOTS": str(root)}
    code, out = tool("check.py", "--root", "fixture", env=env)
    cited = re.findall(r"^ERROR fixture/_answers\.md:(\d+) cites (\S+)", out, re.M)
    assert code == 1 and cited == [("3", f"print/queues.md:{heading},"), ("4", f"print/queues.md:{fact}-{heading},")], out[-2000:]


def test_lint_names_a_facts_line_with_a_second_bullet_after_its_tag(tmp_path):
    root = tmp_path / "root"
    fixture_root(root, SID)
    art = root / "print" / "queues.md"
    joined = f"- Held jobs stay until released. [DOC {SID}]- Paused queues keep their jobs. [DOC {SID}]"
    write(art, art.read_text(encoding="utf-8").replace(
        "## Reference", f"- Queues 1 - 3 are shared. [DOC {SID}]\n{joined}\n\n## Reference"))
    at = art.read_text(encoding="utf-8").split("\n").index(joined) + 1
    env = {**os.environ, "KB_ROOTS": str(root)}
    code, out = tool("build_index.py", "--root", "fixture", env=env)
    assert code == 0, out[-2000:]
    code, out = tool(os.path.join("..", ".claude", "skills", "kb-verify", "lint.py"), "fixture/", env=env)
    flagged = re.findall(r"^ERROR (\S+): Facts line holds a second bullet", out, re.M)
    assert code == 1 and flagged == [f"fixture/print/queues.md:{at}"], out[-2000:]


def test_build_index_check_passes_on_the_live_kb():
    code, out = tool("build_index.py", "--check")
    assert code == 0, out[-3000:]


def test_lookup_eval_passes_on_the_live_kb_and_pack_revalidate_marks_only_the_printed_lines_from_stubbed_pages(monkeypatch, tmp_path, capsys):
    code, out = tool("rag.py", "eval")
    m = re.search(r"^questions=(\d+) passed=(\d+) verdict_ok=\d+ found_ok=\d+", out, re.M)
    assert m, out[-1500:]
    assert code == 0 and int(m.group(1)) > 0 and m.group(1) == m.group(2), out[-3000:]
    # pack --revalidate asks the cited sources of the printed fact lines, resolves only those lines' anchors and marks
    # each; every response is planted (a url not listed raises), and nothing is written but under the cache directory
    real_request = provider.request
    with provider.budget(0):  # a request that cannot finish in the time left is not sent
        assert real_request("https://learn.microsoft.com/x")["error"] == provider.BUDGET_ERROR
    host, sha = "https://learn.microsoft.com/en-us/test/", "a" * 40
    A, B, C, D, P, G = "S9990011", "S9990012", "S9990013", "S9990014", "S9990015", "S9990016"
    urls = {A: host + "page-a", B: host + "page-b", C: host + "page-c", D: host + "page-d",
            P: f"https://raw.githubusercontent.com/Org/Repo/{sha}/docs/f.md", G: "https://github.com/Org/Repo/issues/7"}
    fill = "".join(f"## Part {i}\n\nOrion node {i} reports its health and its queue depth to the console every {i + 7} minutes.\n\n"
                   for i in range(12))
    old = fill + ("# Orion\n\n## Schedule\n\nThe Orion scheduler restarts every night at three o'clock.\n\n"
                  "## Queue\n\nThe Orion queue holds ten thousand jobs before it refuses new ones.\n\n"
                  "## Audit\n\nThe Orion audit log keeps ninety days of history for every tenant.\n\n"
                  "## Retry\n\nThe Orion retry worker waits four seconds between attempts at a failed job.\n")
    new = old.replace("ten thousand", "twenty thousand").replace(
        "## Audit\n\nThe Orion audit log keeps ninety days of history for every tenant.\n\n", "").replace(
        "## Retry\n\nThe Orion retry worker waits four seconds between attempts at a failed job.\n", "")
    audit = "# Audit\n\nThe Orion audit log keeps ninety days of history for every tenant.\n"
    facts = [("a1a1a1a1a1a1", 5, "The Orion scheduler restarts every night at three o'clock."),
             ("b2b2b2b2b2b2", 6, "The Orion queue holds ten thousand jobs before it refuses new ones."),
             ("c3c3c3c3c3c3", 7, "The Orion audit log keeps ninety days of history for every tenant."),
             ("d4d4d4d4d4d4", 8, "The Orion retry worker waits four seconds between attempts at a failed job."),
             ("e5e5e5e5e5e5", 9, "The Orion dashboard shows a green badge for a healthy node.")]
    when = {"text": old, "final": urls[A], "fetched_utc": "2026-10-01T00:00:00+00:00"}
    anchors = {}
    for sid, rel in ((A, "dsc/a.md"), (B, "dsc/b.md"), (B, "dsc/c.md")):
        for r in factdiff.anchor_rows(sid, [(k, rel, ln, t) for k, ln, t in facts], {"status": 200, "text": old}, "quote", "2026-10-01"):
            anchors[(r["fact"], r["path"], sid)] = r
    assert anchors[("e5e5e5e5e5e5", "dsc/a.md", A)]["status"] == "unlocated:no-match"
    state = {A: factdiff.baseline(A, urls[A], when, provider.providers()),
             B: {**factdiff.baseline(B, urls[B], when, provider.providers()), "etag": 'W/"1"'}}
    asked, resolved = [], []

    def respond(status=200, body=b"", headers=None, error=""):
        return {"status": status, "headers": {"content-type": "text/markdown", **(headers or {})}, "body": body,
                "final": "", "hops": [], "error": error}
    pages = {urls[A]: lambda h: respond(body=new.encode()),
             urls[B]: lambda h: respond(304) if h.get("If-None-Match") else respond(body=old.encode()),
             urls[C]: lambda h: respond(0, error="URLError: timed out"),
             urls[G]: lambda h: respond(403, headers={"x-ratelimit-remaining": "0"}),
             f"https://raw.githubusercontent.com/Org/Repo/{sha}/docs/f.md": lambda h: respond(404),
             "https://api.github.com/repos/Org/Repo": lambda h: respond(403, headers={"x-ratelimit-remaining": "0"}),
             host + "audit": lambda h: respond(body=audit.encode())}

    def request(url, headers=None, limit=20_000_000, method="GET"):
        asked.append(url)
        if "learn.microsoft.com/api/search" in url:
            return {**respond(headers={"content-type": "application/json"}, body=json.dumps({"results": [{"url": host + "audit"}]}).encode()), "final": url}
        return {**pages[url.split("?")[0]](headers or {}), "final": url}
    monkeypatch.setattr(provider, "request", request)
    monkeypatch.setattr(provider, "_repos", {})  # the repository answers and the GitHub request count are the process's
    monkeypatch.setattr(provider, "_gh_api", {"asked": 0, "left": None, "seen": 0.0})
    monkeypatch.setattr(factdiff, "CACHE", str(tmp_path / "cache" / "factdiff"))
    monkeypatch.setattr(kbfacts, "source_rows", lambda: {sid: {"id": sid, "url": u} for sid, u in {**urls, D: urls[D]}.items()})
    monkeypatch.setattr(factdiff, "read_state", lambda: state)
    monkeypatch.setattr(factdiff, "read_anchors", lambda: anchors)
    real_resolve = factdiff.resolve
    monkeypatch.setattr(factdiff, "resolve", lambda sid, src, v, doc, prev, fs, *a, **k: resolved.append((sid, [f[2] for f in fs])) or real_resolve(sid, src, v, doc, prev, fs, *a, **k))
    for name in ("write_state", "write_anchors", "write_snapshot"):  # a lookup writes no committed ledger
        monkeypatch.setattr(factdiff, name, lambda *a, **k: pytest.fail("a revalidation wrote a ledger"))
    line = lambda path, n, key, text, *ids: {"path": path, "line": n, "key": key, "text": text, "ids": list(ids)}  # noqa: E731
    printed = [line("public/dsc/a.md", n, k, t, A) for k, n, t in facts]  # D is in the ledger, cited by no printed line
    printed += [line("public/dsc/b.md", 3, facts[0][0], facts[0][2], B), line("public/dsc/c.md", 4, facts[0][0], facts[0][2], B, C),
                line("public/dsc/d.md", 2, "f6f6f6f6f6f6", "The Orion pin is fixed.", P), line("public/dsc/g.md", 2, "f7f7f7f7f7f7", "x", G)]
    rev = factdiff.revalidate(printed)
    by_line = {k: v["outcome"] for k, v in rev["lines"].items()}
    assert [by_line[("public/dsc/a.md", n)] for n in range(5, 10)] == ["current", "moved", "moved", "not found", "source-dated only"], by_line
    assert rev["lines"][("public/dsc/a.md", 6)]["passage"] == "The Orion queue holds twenty thousand jobs before it refuses new ones."
    assert rev["lines"][("public/dsc/a.md", 7)]["target"] == host + "audit" and "ninety days" in rev["lines"][("public/dsc/a.md", 7)]["passage"]
    assert by_line[("public/dsc/b.md", 3)] == "current" and rev["lines"][("public/dsc/b.md", 3)]["checked_utc"][:10] == rev["date"]
    # a line citing a source that could not be asked keeps the other's outcome and names the one it lacks
    assert by_line[("public/dsc/c.md", 4)] == "current" and list(rev["lines"][("public/dsc/c.md", 4)]["unchecked"]) == [C]
    assert rev["sources"][C] == {"state": "offline", "verdict": "error", "why": "network error: URLError: timed out", "checked_utc": rev["date"]}
    assert rev["sources"][P]["why"].startswith("pinned; its repository was not asked: github.com/org/repo: GitHub's unauthenticated limit")
    assert rev["sources"][G]["why"] == "rate limited: HTTP 403" and by_line[("public/dsc/g.md", 2)] == ""
    assert resolved == [(A, [5, 6, 7, 8, 9])] and not any(urls[D] in u for u in asked), (resolved, asked)  # printed lines of cited sources only
    assert sum(u.startswith(urls[A]) for u in asked) == 1 and sum(u.startswith(urls[B]) for u in asked) == 1
    # the marks the pack puts in: the live outcome replaces the offline ones; a line none of whose sources could be asked keeps them
    text = ("- public/dsc/a.md:6 [unanchored; source changed] The Orion queue holds ten thousand jobs. [DOC S9990011]\n"
            "- public/dsc/g.md:2 [unanchored] x [DOC S9990016]\n\nsources:\n  -> S9990011  " + urls[A] + "  [confirmed 2026-10-10, hash]\n"
            "  -> S9990016  " + urls[G] + "  [confirmed 2026-10-10, hash]")
    marked = kbfacts.revalidated(text, rev).split("\n")
    assert marked[0] == f"- public/dsc/a.md:6 [moved {rev['date']}] The Orion queue holds ten thousand jobs. [DOC S9990011]", marked[0]
    assert marked[1] == f'    now ({urls[A]}): "The Orion queue holds twenty thousand jobs before it refuses new ones."'
    assert marked[2] == "- public/dsc/g.md:2 [unanchored] x [DOC S9990016]" and marked[6].endswith("  [not checked live]")
    assert marked[5].endswith(f"  [live {rev['date']}: changed]") and marked[-1].startswith(f"revalidate {rev['date']}: 2 source(s) asked live, 0 answered")
    assert "not checked, the offline stamp stands: " in marked[-1] and "network error: URLError: timed out" in marked[-1]
    # a result younger than the provider's pacing is reused with no request; an offline source is asked again
    before = len(asked)
    monkeypatch.setattr(provider, "pacing", lambda row: 3600)
    again = factdiff.revalidate(printed)
    kept = [k for k in rev["lines"] if k[0] != "public/dsc/d.md" and k[0] != "public/dsc/g.md"]
    assert {k: again["lines"][k] for k in kept} == {k: rev["lines"][k] for k in kept}
    assert again["sources"][A]["state"] == again["sources"][B]["state"] == "cached"
    assert not any(u.startswith((urls[A], urls[B])) for u in asked[before:]), asked[before:]  # only C, G and P were asked again
    assert not [p for p in tmp_path.rglob("*") if p.is_file() and "revalidate" not in p.parts]  # only the stored results, under the cache
    # the time budget: a source asked after it is used up is not checked, and says so
    monkeypatch.setattr(provider, "pacing", lambda row: 0)
    monkeypatch.setattr(provider, "request", lambda url, headers=None, **k: {**respond(0, error=provider.BUDGET_ERROR), "final": url})
    cut = factdiff.revalidate(printed[:1])
    assert cut["sources"][A]["state"] == "offline" and cut["sources"][A]["why"] == provider.BUDGET_ERROR, cut
    # the pack: --revalidate is a flag of rag.py pack; over the live kb with every page failing it keeps the offline text
    # and says which sources it could not check; the kb: hook never goes to the network
    monkeypatch.undo()
    monkeypatch.setattr(factdiff, "CACHE", str(tmp_path / "live" / "factdiff"))
    question = good_row()["question"]
    offline = kbfacts.pack_many([question])["text"]
    monkeypatch.setattr(provider, "request", lambda url, headers=None, **k: {**respond(0, error="URLError: stubbed"), "final": url})
    monkeypatch.setattr(sys, "argv", ["rag.py", "pack", question, "--revalidate"])
    rag.main()
    live = capsys.readouterr().out.rstrip("\n")
    body, _, summary = live.rpartition("\nrevalidate ")
    assert body.replace("  [not checked live]", "") == offline and "not checked, the offline stamp stands: " in summary, live[-1500:]
    monkeypatch.setattr(factdiff, "revalidate", lambda *a, **k: pytest.fail("the kb: hook revalidated"))
    res = kb_hook.answer("kb: " + question)
    assert res and res["decision"] == "block" and "revalidate" not in res["reason"]


def test_lookup_eval_fails_on_a_wrong_expected_article(tmp_path):
    row = good_row()
    wrong = dict(row, id="EV-planted-wrong-article",
                 expect_paths="dsc/what-if.md" if row["expect_paths"] != "dsc/what-if.md" else "auth/kerberos.md")
    bad = tmp_path / "lookup_eval.csv"
    with open(bad, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row), lineterminator="\n")
        w.writeheader()
        w.writerows([wrong, row])
    code, out = tool("rag.py", "eval", "--file", str(bad))
    assert code == 1 and f"FAIL {wrong['id']}" in out and "questions=2 passed=1" in out, out[-1500:]
    assert f" {row['id']} " not in out, out[-1500:]  # a passing row is printed only with --all
    code, out = tool("rag.py", "eval", "--file", str(bad), "--min", "1", "--all")  # the held-out rate's form: at least N pass
    assert code == 0 and "questions=2 passed=1" in out and f"ok   {row['id']} " in out, out[-1500:]


def test_eval_offkb_overlap_and_heldout_reword_are_refused_naming_the_row(tmp_path):
    cols = ["id", "question", "expect_paths", "expect_verdict", "allow_weak"]
    head = ",".join(cols) + "\n"
    write(tmp_path / "lookup_eval.csv", head + "EV-planted,How do I expose the session id to a Bash command?,x/a.md,good,\n"
          + "EV-planted-offkb,Which port does the relay listen on?,x/a.md,good,\n"
          + "EV-planted-guard,how do I clear the cache,,weak,\n")  # a weak row on the off-kb list is a guard, not an overlap
    write(tmp_path / "lookup_heldout.csv", head
          + "HO-reworded,How do I expose the session id in a Bash command?,x/a.md,good,\n"
          + "HO-other-question,What does the retention setting delete first?,x/a.md,good,\n"
          + "HO-other-article,How do I expose the session id to a Bash command?,x/b.md,good,\n"
          + "HO-offkb,How do I rotate the signing key?,x/a.md,good,\n")
    write(tmp_path / "doc2query" / "offkb_questions.txt",
          "how do I rotate the signing  key\nWhich port does the relay listen on?\nHow do I clear the cache?\n")
    code, out = tool("rag.py", "eval", "--file", str(tmp_path / "lookup_heldout.csv"), "--min", "1")
    assert code == 1 and "REWORD HO-reworded ~ EV-planted (ratio 0.9" in out, out[-1500:]  # --min does not excuse it
    assert "OFFKB HO-offkb (lookup_heldout.csv): its question is line 1 of " in out, out[-1500:]
    assert "HO-other" not in out and "questions=" not in out, out[-1500:]  # refused before any pack runs
    code, out = tool("rag.py", "eval", "--file", str(tmp_path / "lookup_eval.csv"))
    assert code == 1 and "OFFKB EV-planted-offkb (lookup_eval.csv): its question is line 2 of " in out, out[-1500:]
    assert "EV-planted-guard" not in out and "EV-planted " not in out and "questions=" not in out, out[-1500:]


def test_lookup_eval_fails_on_a_phrase_the_self_docs_do_not_hold(tmp_path):
    with open(os.path.join(kbcommon.SELF, kbcommon.DATA_DIR, "lookup_eval.csv"), encoding="utf-8", newline="") as f:
        row = next(csv.DictReader(f))
    bad = tmp_path / "lookup_eval.csv"
    with open(bad, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row), lineterminator="\n")
        w.writeheader()
        w.writerow(dict(row, expect_text="a phrase no rule doc holds"))
    code, out = tool("rag.py", "eval", "--file", str(bad), "--root", "_self")
    assert code == 1 and f"FAIL {row['id']}" in out and "failed=anchor" in out, out[-1500:]


def test_pack_scatter_check_notes_a_scattered_weak_good_and_pack_routes_kind_to_its_tool_and_prints_coverage_fact_lines_and_pack_freshness_stamp_and_a_pinned_source_of_a_404_repository_is_gone_pinned_repo_gone_and_a_page_whose_other_section_changed_keeps_the_facts_of_the_rest_section_hash(monkeypatch, tmp_path, capsys):
    # the scatter check: the verdict benchmark's calibration runs pack over the tuned eval set's good rows and the
    # off-kb list, never over a held-out row, and the counts it prints are those of the notes the packs carry
    heldout = os.path.join(os.path.dirname(EVAL_CSV), rag.HELDOUT_FILE)
    with open(heldout, encoding="utf-8", newline="") as f:
        held_questions = {r["question"] for r in csv.DictReader(f)}
    real, asked, rows = kbfacts.pack, [], []
    monkeypatch.setattr(kbfacts, "pack", lambda q, *a, **k: asked.append(q) or real(q, *a, **k))

    class Rows:
        def row(self, scenario, case, arm, metric, value, runs="", model="", note=""):
            rows.append((case, arm, metric, value, note))
    bench_retrieval.scatter_rows(Rows())
    monkeypatch.setattr(kbfacts, "pack", real)
    offkb = rag.offkb_questions()
    assert held_questions and not held_questions & set(asked), held_questions & set(asked)
    assert set(asked) == {r["question"] for r in eval_rows() if r["expect_verdict"] == "good"} | set(offkb)
    packs = {q: real(q) for q in set(asked)}
    noted = {q: "check: the best articles lie in" in p["text"] for q, p in packs.items()}
    scatter = {(arm, metric): (value, note) for case, arm, metric, value, note in rows}
    off = [q for q in offkb if packs[q]["top_score"] is not None]  # a `good` the note applies to
    ev = [q for q in set(asked) - set(offkb) if packs[q]["top_score"] is not None]
    cur_off, cur_ev = (sum(noted[q] for q in group) for group in (off, ev))
    assert scatter["current", "threshold"][0] == kbfacts.SCATTER_SCORE and scatter["current", "off_kb_goods_flagged"] == (cur_off, f"of {len(off)}")
    assert scatter["current", "eval_goods_flagged"] == (cur_ev, f"of {len(ev)}")
    # the calibration is a best whole score: none flags more off-kb goods net of eval goods than it, the shipped one included
    cal = scatter["calibrated", "off_kb_goods_flagged"][0] - scatter["calibrated", "eval_goods_flagged"][0]
    assert cal >= cur_off - cur_ev and scatter["calibrated", "off_kb_goods_flagged"][1] == f"of {len(off)}"
    assert all(packs[q]["verdict"] == "good" and packs[q]["scatter"] for q in noted if noted[q])  # a note, never a verdict
    code, out = tool("rag.py", "pack", good_row()["question"])
    assert code == 0, out[-1500:]
    assert re.search(r"^coverage: good\b", out, re.M), out[:1500]
    assert re.search(r"\S+\.md:\d+.*\[(DOC|CODE|DER|COMMUNITY|UNK)\b", out), out[:1500]
    assert kbfacts.routed(good_row()["question"]) is None  # a question of no kind a tool decides ranks as pack ranks it
    # the pool's count, decision, conflict and gap rows: the kb: hook blocks on the answer of the tool that holds it,
    # each line with its path:line, and the row's own checks read it
    rows = bench_pool.load_pool(kinds={"count", "decision", "conflict", "gap"})
    assert {r["kind"] for r in rows} == {"count", "decision", "conflict", "gap"}
    for r in rows:
        res = kb_hook.answer("kb: " + r["question"])
        assert res and res["decision"] == "block", (r["id"], res)
        for check in json.loads(r["checks"]):
            assert re.search(check, res["reason"]), (r["id"], check, res["reason"][:800])
        assert r["kind"] == "count" or re.search(r"^- \S+:[1-9]\d* ", res["reason"], re.M), (r["id"], res["reason"][:800])
    # experts that both answer are fused by rank alone (k = 60): a key in both lists leads; equal scores go to the key
    fused = kbfacts.rrf([[("a.md", 1), ("b.md", 1)], [("b.md", 1), ("c.md", 1)]])
    assert [k for k, _ in fused] == [("b.md", 1), ("a.md", 1), ("c.md", 1)], fused
    assert [k for k, _ in kbfacts.rrf([[("z.md", 2)], [("a.md", 9)]])] == [("a.md", 9), ("z.md", 2)]
    # a question about one model: the pack leads with that model's row of the models table, not prose that names it
    code, out = tool("rag.py", "pack", "Claude Sonnet 5.5 model release capabilities pricing context window", "--budget", "300")
    assert code == 0, out[-1500:]
    assert re.search(r"^## (\S+)", out, re.M).group(1).endswith("claude/models.csv"), out[:1500]
    # the freshness stamp: each cited source's footer line ends with its last confirmation and signal, read with no
    # network; a printed fact whose anchor is not located, or was verified before its source changed, carries a mark
    import socket
    def no_network(*a, **k):
        raise AssertionError("pack opened a network connection")
    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket.socket, "connect", no_network)
    res = kbfacts.pack(good_row()["question"])
    footer = res["text"].split("\nsources:\n", 1)[1].splitlines()
    stamp = r"  \[(confirmed \d{4}-\d\d-\d\d|unconfirmed), (pinned|git|etag|lastmod|version|hash|no baseline)\]$"
    assert footer and all(re.search(stamp, ln) for ln in footer), footer
    assert all(kbfacts.source_stamp(i) in ln for i, ln in zip(res["sources"], footer))
    unit = next(u for u in kbfacts.units("public") if any(p["kind"] != "UNK" and p["ids"] for p in u["tags"]))
    sid = next(i for p in unit["tags"] if p["kind"] != "UNK" for i in p["ids"])
    key, rel = kbfacts.fact_key(unit["text"]), kbfacts.bare(unit["path"])
    rows = {sid: {"id": sid, "url": "https://example.com/p"}}

    def mark(anchor, changed):
        state = {sid: {"changed_utc": changed}}
        monkeypatch.setattr(kbfacts, "fresh_state", lambda: ({(key, rel, sid): anchor} if anchor else {}, {}, state))
        return kbfacts.fresh_mark(unit, rows)
    assert mark((True, "2026-10-10"), "") == ""
    assert mark((True, "2026-10-10"), "2026-10-09T08:00:00Z") == ""
    assert mark((True, "2026-10-10"), "2026-10-11T08:00:00Z") == "source changed"
    assert mark((False, "2026-10-10"), "") == "unanchored"
    assert mark(None, "2026-10-11T08:00:00Z") == "unanchored"
    # a pinned source whose repository answers 404 is gone with the signal `repository`, one request per repository and
    # run, and its facts are listed for re-sourcing as a dead source's are; a missing ref, a rate limit and a live
    # repository leave it pinned (planted: every url not listed raises, so an unplanned request fails the test)
    sha, api, asked = "a" * 40, "https://api.github.com/repos/Org/", []
    raw = lambda repo, name="f.md": f"https://raw.githubusercontent.com/Org/{repo}/{sha}/docs/{name}"  # noqa: E731
    gitlab = f"https://gitlab.com/org/gone/-/raw/{sha}/x.md"
    answers = {raw("Gone"): 404, api + "Gone": 404, raw("Moved"): 404, api + "Moved": 200, raw("Limited"): 404, api + "Limited": 403,
               raw("Live"): 200, "https://gitlab.com/api/v4/projects/org%2Fgone": 404}

    def request(url, headers=None, limit=20_000_000, method="GET"):
        asked.append(url)
        return {"status": answers[url], "headers": {}, "body": b"", "final": url, "hops": [], "error": ""}
    monkeypatch.setattr(provider, "request", request)
    monkeypatch.setattr(provider, "_repos", {})
    monkeypatch.setattr(provider, "_gh_api", {"asked": 0, "left": None})
    prov = provider.providers()
    got = {n: factdiff.detect_source("S9990001", {"url": u}, {}, prov)[:3] for n, u in (
        ("gone", raw("Gone")), ("same repository", raw("Gone", "g.md")), ("moved", raw("Moved")), ("limited", raw("Limited")),
        ("live", raw("Live")), ("gitlab", gitlab))}
    assert [n for n, v in got.items() if v[:2] == ("gone", "repository")] == ["gone", "same repository", "gitlab"], got
    assert all(v[0] == "pinned" and v[1] == "pin" for n, v in got.items() if n in ("moved", "limited", "live")), got
    assert got["gone"][2] == f"repository {api}Gone answers 404" and len(asked) == len(set(asked)) == 8, asked
    fact = ("0123456789ab", "dsc/d.md", 5, "The Orion scheduler restarts every night at three o'clock. [CODE S9990001]")
    found, _ = factdiff.resolve("S9990001", {"url": raw("Gone")}, "gone", None, None, [fact], {}, prov)
    assert [r["outcome"] for r in found] == ["dead"] and "dead" in factdiff.REVIEW
    monkeypatch.setattr(census, "repo_dir", lambda repo, base=None: (None, f"clone failed: {repo}"))
    check = lambda u: census.check_one({"url": u, "retrieved_utc": "2026-09-26"}, census.classify(u))[1]  # noqa: E731
    assert [check(u)["bucket"] for u in (raw("Gone"), gitlab, raw("Moved"), raw("Limited"))] == ["GONE", "GONE"] + ["NEEDS-READING"] * 2
    assert "answers 404" in check(raw("Gone"))["evidence"] and len(asked) == 8  # the census asked no repository again
    # a host whose only signal is the text hash: the page is compared per heading section. The baseline holds each
    # section's hash beside the page's; an edit in Beta moves Beta's and no other, so the fact of Alpha (its anchor
    # placed on an earlier text, so its passage is not word for word in the baseline) is kept by its section with the
    # row signal `section`, no passage search, and only the fact of the edited section is resolved
    page = ("# Guide\n\n## Alpha\n\nThe Orion scheduler restarts every night at three o'clock.\n\n"
            "## Beta\n\nThe Orion queue holds ten thousand jobs before it refuses new ones.\n")
    edited = page.replace("ten thousand", "twenty thousand")
    url, sid = "https://code.claude.com/docs/en/guide", "S9990003"
    monkeypatch.setattr(factdiff, "ROOT", kbcommon.root("public"))
    monkeypatch.setattr(factdiff, "CACHE", str(tmp_path / "cache"))
    facts = [("0123456789ab", "dsc/a.md", 5, "The Orion scheduler restarts every night at three o'clock."),
             ("ba9876543210", "dsc/b.md", 6, "The Orion queue holds ten thousand jobs before it refuses new ones.")]
    anchors = {(r["fact"], r["path"], sid): r for r in factdiff.anchor_rows(sid, facts, {"status": 200, "text": page}, "quote", "2026-10-01")}
    assert [r["heading"] for r in anchors.values()] == ["Guide > Alpha", "Guide > Beta"]
    anchors[("0123456789ab", "dsc/a.md", sid)]["sha"] = "0" * 16
    base = factdiff.baseline(sid, url, {"text": page, "final": url, "fetched_utc": "2026-10-01T00:00:00+00:00"}, prov)
    assert base["doc_sha256"] == hashlib.sha256(page.encode()).hexdigest() and base["sections"].count(":") == 4
    assert factdiff.section_counts(factdiff.sections(page), factdiff.sections(edited)) == (1, 3)
    # the stored set belongs to its text: another document's hash leaves it unread, and the previous fetch's text stands in
    assert factdiff.stored_sections(base, None) == factdiff.sections(page)
    assert factdiff.stored_sections({**base, "doc_sha256": "f" * 64}, None) == {}
    assert factdiff.stored_sections({**base, "sections": ""}, {"text": page}) == factdiff.sections(page)
    monkeypatch.setattr(provider, "document", lambda u, row=None, etag="", lastmod="": {
        "status": 200, "final": u, "hops": [], "etag": "", "lastmod": "", "error": "", "bytes": len(edited), "raw": None,
        "version": {}, "text": edited, "ctype": "text/markdown"})
    v, signal, ev, new, doc, prev = factdiff.detect_source(sid, {"url": url}, base, prov)
    assert (v, signal) == ("changed", "hash") and new["sections"] == factdiff.sections_column(edited, new["doc_sha256"])
    found, _ = factdiff.resolve(sid, {"url": url}, v, doc, {"text": page}, facts, anchors, prov,
                                (factdiff.stored_sections(base, None), factdiff.sections(edited)))
    assert [(r["outcome"], r.get("signal", "")) for r in found] == [("verbatim", factdiff.SECTION_SIGNAL), ("modified", "")], found
    # detect's source row counts the sections, the run's line totals them; apply trusts a fact kept by its section only
    # when the baseline is no newer than the last confirmation
    monkeypatch.setattr(factdiff, "sources", lambda: {sid: {"id": sid, "url": url, "reuse": "quote", "retrieved_utc": "2026-10-02"}})
    monkeypatch.setattr(factdiff, "cited_facts", lambda prefix=None: {sid: facts})
    monkeypatch.setattr(factdiff, "read_anchors", lambda: anchors)
    monkeypatch.setattr(factdiff, "read_state", lambda: {sid: base})
    monkeypatch.setattr(factdiff, "select_ids", lambda a, srcs: [sid])
    log = tmp_path / "log.csv"
    args = argparse.Namespace(date="2026-10-12", out=str(log), no_save=False, sitemaps=False)
    monkeypatch.setattr(factdiff, "write_state", lambda state: None)
    monkeypatch.setattr(factdiff, "write_snapshot", lambda *a, **k: None)
    assert factdiff.cmd_detect(args, collections.Counter()) == 1  # the fact of Beta waits for review
    assert "sections: changed=1 unchanged=3 (facts kept by section=1)" in capsys.readouterr().out
    head = factdiff.read_log(log)[0]
    assert head["verdict"] == "changed" and head["evidence"].endswith("sections: 1 changed, 3 unchanged"), head


def test_unit_cache_prune_drops_old_files_of_other_root_sets_and_shrinks_the_slack_pruned_file(tmp_path, monkeypatch):
    idx = tmp_path / "idx"
    idx.mkdir()
    monkeypatch.setenv("KB_INDEX", str(idx))
    monkeypatch.setattr(kbfacts, "_root_key", lambda: "")  # this repository's roots alone
    old = time.time() - kbfacts.PRUNE_OTHER_ROOTS - 86400
    current = f"kbindex-{'0' * 16}.sqlite"
    planted = {current: old, "kbunits.sqlite": old,  # this root set's: never pruned as another's
               f"kbindex-r00c0ffee-{'a' * 16}.sqlite": old, "kbunits-r00c0ffee.sqlite": old,  # a set unused for long
               f"kbindex-r00facade-{'b' * 16}.sqlite": old,  # a second one
               f"kbindex-r00c0ffee-{'c' * 16}.sqlite": time.time()}  # a set in use
    for name, mtime in planted.items():
        (idx / name).write_bytes(b"")
        os.utime(idx / name, (mtime, mtime))
    kbfacts.prune_indexes(str(idx), current)
    assert sorted(os.listdir(idx)) == sorted([current, "kbunits.sqlite", f"kbindex-r00c0ffee-{'c' * 16}.sqlite"])

    # more rows than the slack allows: the prune keeps the keys of this weighing and gives the pages back
    rows = {bytes([i // 256, i % 256]) * 8: os.urandom(2000) for i in range(300)}
    keys = sorted(rows)[:10]
    con = kbfacts._unit_cache_open()
    kbfacts._unit_cache_save(con, rows, list(rows))  # 300 rows <= UNIT_CACHE_SLACK * 300: nothing dropped
    con.close()
    path = idx / "kbunits.sqlite"
    full = path.stat().st_size
    con = kbfacts._unit_cache_open()
    kbfacts._unit_cache_save(con, {}, keys)  # 300 rows > UNIT_CACHE_SLACK * 10
    kept = sorted(k for (k,) in con.execute("SELECT k FROM u"))
    con.close()
    assert kept == keys and path.stat().st_size < full // 10, (len(kept), full, path.stat().st_size)


# rag.py pack on the fixture root alone (serve_only), so a cold index weighs one article and not the live kb
PACK_FIXTURE = ("import sys; sys.path.insert(0, sys.argv[1]); import kbcommon; kbcommon.serve_only(['fixture']); "
                "import rag; sys.argv = ['rag.py', 'pack', sys.argv[2]]; rag.main()")


def variant(orig):
    """A function that does what `orig` does with other code: _weigh_code() digests the code, not the behaviour."""
    def v(*args, **kwargs):
        return orig(*args, **kwargs)
    return v


def test_unit_cache_equals_a_fresh_weighing_re_weighs_on_each_key_input_and_finds_an_edited_fact(tmp_path, monkeypatch):
    cache = tmp_path / "idx" / kbfacts.UNIT_CACHE
    monkeypatch.setenv("KB_INDEX", str(cache.parent))
    monkeypatch.delenv("KB_DOC2QUERY", raising=False)
    monkeypatch.setattr(kbfacts, "UNIT_CACHE_SLACK", 1000)  # no pruning: a key that did not change is still a row
    summary = ["Kept 14 days."]
    monkeypatch.setattr(kbfacts, "summary_text", lambda rel: summary[0])
    base = dict(path="public/print/queues.md", section="Facts", text="Finished jobs are kept for 14 days.",
                tags=[{"kind": "DOC"}], lead="", anchors=[])
    metas = {base["path"]: {"title": "Print queues"}}
    exps = {kbfacts.fact_key(base["text"]): ["how long are print jobs kept"]}

    def weigh(unit=None, metas=metas, exps=exps):
        return kbfacts.weighed([dict(base, **(unit or {}))], metas, exps)[0]

    def keys():
        con = sqlite3.connect(cache)
        try:
            return {k for (k,) in con.execute("SELECT k FROM u")}
        finally:
            con.close()

    kbfacts._weigh_code.cache_clear()
    first = weigh()
    assert len(keys()) == 1 and first["tf"] and first["own"]
    with monkeypatch.context() as m:  # a hit weighs nothing, and equals a weighing with no cache (KB_INDEX=0)
        m.setattr(kbfacts, "_weigh", lambda *a: pytest.fail("the unit was weighed again"))
        hit = weigh()
    with monkeypatch.context() as m:
        m.setenv("KB_INDEX", "0")
        fresh = weigh()
    assert [hit[k] for k in ("len", "own", "tf")] == [fresh[k] for k in ("len", "own", "tf")]
    assert len(keys()) == 1

    cases = {  # each input _unit_key hashes: a change must make a new key, so the unit is weighed again
        "INDEX_VERSION": lambda m: m.setattr(kbfacts, "INDEX_VERSION", kbfacts.INDEX_VERSION + 1),
        "KB_DOC2QUERY": lambda m: m.setenv("KB_DOC2QUERY", "1"),
        "TITLE_WEIGHT": lambda m: m.setattr(kbfacts, "TITLE_WEIGHT", kbfacts.TITLE_WEIGHT + 1),
        "SUMMARY_WEIGHT": lambda m: m.setattr(kbfacts, "SUMMARY_WEIGHT", kbfacts.SUMMARY_WEIGHT + 1),
        "EXPANSION_WEIGHT": lambda m: m.setattr(kbfacts, "EXPANSION_WEIGHT", kbfacts.EXPANSION_WEIGHT + 1),
        "STOP": lambda m: m.setattr(kbfacts, "STOP", kbfacts.STOP | {"zzstop"}),
        "kbid.STOP": lambda m: m.setattr(kbid, "STOP", kbid.STOP | {"zzstop"}),
    }
    for name in ("WORD", "CAMEL", "NUMBER"):
        cases[name] = lambda m, name=name: m.setattr(kbfacts, name, re.compile(getattr(kbfacts, name).pattern + "|zz"))
    for name in ("_weigh", "terms", "stem", "bare"):
        cases[name + " code"] = lambda m, name=name: m.setattr(kbfacts, name, variant(getattr(kbfacts, name)))
    other = "public/print/other.md"
    inputs = {  # each case changes its one input: the new path's meta keeps the title, so only the path differs
        "path": {"unit": {"path": other}, "metas": {other: metas[base["path"]]}},
        "title": {"metas": {base["path"]: {"title": "Print queue"}}},
        "lead": {"unit": {"lead": "Jobs"}},
        "section": {"unit": {"section": "Reference"}},
        "text": {"unit": {"text": base["text"] + " Held jobs wait."}},
        "expansions": {"exps": {kbfacts.fact_key(base["text"]): ["how long are queued jobs kept"]}},
        "anchors": {"unit": {"anchors": [(1, "how long are print jobs kept")]}},
    }
    cases["summary"] = lambda m: summary.__setitem__(0, "Kept 21 days.")
    for name in sorted(cases) + sorted(inputs):
        before = keys()
        with monkeypatch.context() as m:
            try:
                if name in cases:
                    cases[name](m)
                    kbfacts._weigh_code.cache_clear()  # the digest is computed once: recompute it for the changed code
                weigh(**inputs.get(name, {}))
            finally:
                summary[0] = "Kept 14 days."
                kbfacts._weigh_code.cache_clear()
        assert keys() - before, f"a change to {name} reused the cached weighing"

    # a smaller root set's build writes its own file and leaves this root set's rows alone, even when it prunes
    whole = keys()
    with monkeypatch.context() as m:
        m.setattr(kbfacts, "_root_key", lambda: "r00c0ffee-")
        m.setattr(kbfacts, "UNIT_CACHE_SLACK", 0)
        weigh()
    assert keys() == whole and (cache.parent / "kbunits-r00c0ffee.sqlite").is_file()

    # an edited fact is found by rag.py pack: the unit cache holds the unit weighed before the edit
    root =tmp_path / "root"
    fixture_root(root, SID)
    art = root / "print" / "queues.md"
    env = {**os.environ, "KB_ROOTS": str(root), "KB_INDEX": str(tmp_path / "packidx")}
    env.pop("KB_DOC2QUERY", None)

    def pack():
        p = subprocess.run([sys.executable, "-c", PACK_FIXTURE, TOOLS, "which sweeper purges finished jobs"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
        assert p.returncode == 0, p.stdout[-1500:] + p.stderr[-1500:]
        return p.stdout

    assert not re.search(r"^coverage: good\b", pack(), re.M)
    write(art, art.read_text(encoding="utf-8").replace(
        "kept for 14 days.", "kept for 14 days, then purged by the sweeper."))
    out = pack()
    assert re.search(r"^coverage: good\b", out, re.M) and re.search(r"queues\.md:\d+ .*sweeper.*\[DOC ", out), out[:1500]


def one_set_problems(top, docs):
    """Why the plugin's four files are not the one set: an entry that is no relative link to its file (a checkout
    without symlink rights holds the target as the file's text), a file beside the link in its skill folder, or a
    plugin file the map does not describe by the docs that described the entry."""
    bad = []
    for link, target in ONE_SET.items():
        entry, want = top / link, os.path.relpath(top / target, (top / link).parent).replace(os.sep, "/")
        if entry.is_symlink():
            got = os.readlink(entry).replace(os.sep, "/")
        elif sys.platform == "win32" and entry.is_file() and entry.stat().st_size < 200:
            got = entry.read_text(encoding="utf-8").strip()
        else:
            got = None
        if got != want:
            bad.append(f"{link} is not a link to {want}")
        if entry.parent.parent.name == "skills" and list(entry.parent.iterdir()) != [entry]:
            bad.append(f"{entry.parent.name} holds a file beside the link")
        lost = set(selfdoc.describing(docs, [link])) - set(selfdoc.describing(docs, [target]))
        if lost:
            bad.append(f"{target} is not mapped to {sorted(lost)}")
    return bad


def test_plugin_sprint_one_set_the_kb_claude_entries_link_to_the_plugins_files_and_the_map_keeps_their_docs(tmp_path):
    assert one_set_problems(Path(kbcommon.HOME), selfdoc.load_map()) == []
    for link in ONE_SET:  # the planted failure: each entry a copy of the text, and a map that names only the old paths
        write(tmp_path / link, "the text of a skill\n" * 20)
    docs = {"AGENTS.md": [".claude/skills/*/SKILL.md"], "kb/_self/plugin.md": [".claude/agents/*.md"]}
    bad = one_set_problems(tmp_path, docs)
    assert all(f"{link} is not a link to " in " ".join(bad) for link in ONE_SET), bad
    assert any(b.endswith("is not mapped to ['AGENTS.md']") for b in bad) and any("plugin.md" in b for b in bad), bad
