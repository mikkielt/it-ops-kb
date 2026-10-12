"""The checks the kb's content lives by, over the live kb: check.py (sources, citations, tags), build_index.py --check
(the generated index), the lookup eval (rag.py eval), the pack format and the questions it routes by kind to the tool that holds the answer, and the plugin's one set of the sprint text. Each gate also fails on a planted input. The pack
index's unit cache is pinned on a planted fixture root, not on the live kb."""
import argparse, collections, csv, datetime, hashlib, json, math, os, re, sqlite3, subprocess, sys, time
from pathlib import Path

import pytest

import bench_pool, bench_retrieval, census, factdiff, fetch, kb_ask, kb_hook, kb_mcp, kbcommon, kbfacts, kbid, provider, rag, selfdoc
from conftest import TOOLS, Repo, requires_git, tool

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
          f"- Jobs are kept 14 days. (`print/queues.md:{fact}-{fact}`, `print/queues.md:{fact}-{heading}`) [DOC {SID}]\n"
          f"- Jobs are kept 14 days. (`print/queues.md:900`, `print/queues.md:900-920`) [DOC {SID}]\n")
    env = {**os.environ, "KB_ROOTS": str(root)}
    code, out = tool("check.py", "--root", "fixture", env=env)
    cited = re.findall(r"^ERROR fixture/_answers\.md:(\d+) cites (\S+)", out, re.M)
    assert code == 1 and cited == [("3", f"print/queues.md:{heading},"), ("4", f"print/queues.md:{fact}-{heading},"),
                                   ("5", "print/queues.md:900,"), ("5", "print/queues.md:900-920,")], out[-2000:]


@requires_git
def test_lint_names_a_facts_line_with_a_second_bullet_after_its_tag_and_warns_of_a_doc_fact_the_change_added_whose_anchor_quote_the_page_does_not_hold_and_not_of_an_old_one_and_factdiff_anchor_quote_locates_a_fact_by_its_quote_and_refuses_one_over_25_words(tmp_path):
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
    lint = os.path.join("..", ".claude", "skills", "kb-verify", "lint.py")
    code, out = tool(lint, "fixture/", env=env)
    flagged = re.findall(r"^ERROR (\S+): Facts line holds a second bullet", out, re.M)
    assert code == 1 and flagged == [f"fixture/print/queues.md:{at}"], out[-2000:]
    # the article given by its absolute path lints as the qualified one; an argument that names no file is refused,
    # named as given, and nothing is linted; a live article given from the repository (`kb/public/...`) is no refusal
    code, out = tool(lint, str(art), env=env)
    assert code == 1 and re.findall(r"^ERROR (\S+): Facts line holds a second bullet", out, re.M) == flagged, out[-2000:]
    missing_arg = "kb/public/no-such-dir/no-such-article.md"
    code, out = tool(lint, missing_arg, "fixture/", env=env)
    assert code == 1 and repr(missing_arg) in out and "Facts line" not in out, out[-2000:]
    live = next(Path(kbcommon.PUBLIC).glob("*/*.md")).relative_to(kbcommon.HOME).as_posix()
    code, out = tool(lint, live, env=env)
    assert code == 0 and "errors=0" in out, out[-2000:]
    # a DOC fact the change adds: anchored by the quote its page holds (located), or by none (no-match, warned of); the
    # old fact's anchor is no-match too, as 37% of the ledger's are, and raises nothing
    page = "Held jobs wait until an operator releases them. Queues pause without losing their jobs."
    old_fact, quoted, missing = "Finished jobs are kept for 14 days.", "Operators free a held job at will.", "Spooler retention is 14 days."
    quotes = {quoted: "wait until an operator releases them", missing: "retention is fourteen days by default"}

    def anchor(text):
        facts = [(kbfacts.fact_key(u["text"]), "print/queues.md", u["line"], u["text"])
                 for u in kbfacts.md_units("print/queues.md", text) if u["text"].startswith((old_fact, quoted, missing))]
        rows = factdiff.anchor_rows(SID, facts, {"status": 200, "text": page}, "copy", "2026-10-12")
        found, lost = factdiff.quote_rows(rows, facts, {"status": 200, "text": page}, "copy",
                                          {f[2]: quotes[f[3].split(" [DOC")[0]] for f in facts if f[3].split(" [DOC")[0] in quotes})
        kbcommon.write_csv(str(root / "_anchors.csv"), kbcommon.ANCHOR_COLS, rows)
        return [r["status"] for r in rows], found, lost

    repo = Repo(root)
    repo.git("init", "-q", "-b", "main")
    write(root / "_sources.csv", (root / "_sources.csv").read_text(encoding="utf-8")
          + f"{SID},https://example.com/print,Print queues,Example,MIT,copy,2026-09-26,,,,\n")
    assert anchor(art.read_text(encoding="utf-8")) == (["unlocated:no-match"], [], [])
    repo.commit("base")
    write(art, art.read_text(encoding="utf-8").replace(
        "## Reference", f"- {quoted} [DOC {SID}]\n- {missing} [DOC {SID}]\n\n## Reference"))
    text = art.read_text(encoding="utf-8")
    statuses, found, lost = anchor(text)
    assert statuses == ["unlocated:no-match", "located", "unlocated:no-match"] and len(found) == 1 and len(lost) == 1
    lines = text.split("\n")
    code, out = tool(lint, "fixture/", env=env)
    warned = re.findall(r"^WARN\s+(\S+): DOC fact added in this change: no passage of", out, re.M)
    assert warned == [f"fixture/print/queues.md:{lines.index(f'- {missing} [DOC {SID}]') + 1}"], out[-2000:]
    # the quote CSV: a fact line and its quote, at most 25 words, for a tagged fact of the one file
    got = tmp_path / "quotes.csv"
    wordy = " ".join(["word"] * 26)
    got.write_text(f"line,quote\n{lines.index(f'- {quoted} [DOC {SID}]') + 1},{quotes[quoted]}\n99,x y z\n"
                   f"{lines.index(f'- {missing} [DOC {SID}]') + 1},{wordy}\n", encoding="utf-8")
    facts = {SID: [(kbfacts.fact_key(u["text"]), "print/queues.md", u["line"], u["text"])
                   for u in kbfacts.md_units("print/queues.md", text)]}
    ok, bad = factdiff.read_quotes(str(got), "print/queues.md", facts)
    assert list(ok.values()) == [quotes[quoted]] and len(bad) == 2 and "no tagged fact" in bad[0] and "over 25 words" in bad[1], bad


def test_build_index_check_passes_on_the_live_kb():
    code, out = tool("build_index.py", "--check")
    assert code == 0, out[-3000:]


def kbid_licence_families(monkeypatch, tmp_path, capsys):
    """`kbid.py add` with no --licence and --reuse reads the source's own licence record by its family; each answer is
    stubbed (a url not listed raises), so no request leaves the process, and an unread licence writes nothing."""
    import types
    head = "id,url,title,publisher,licence,reuse,retrieved_utc,version_or_date,artifact_sha256,used_in,superseded_by\n"
    wiki = "https://wiki.corp.example.com/"
    write(tmp_path / "lic" / "_sources.csv", head + "".join(
        f"S-{c * 8},{wiki}{n},T,P,{lic},{reuse},2026-10-01,,,,\n"
        for c, n, lic, reuse in (("a", "x", "Corp wiki terms", "quote"), ("b", "y", "Corp wiki terms", "quote"), ("c", "z", "MIT", "copy"))))
    root = types.SimpleNamespace(path=str(tmp_path / "lic"), name="fixture", id_prefix="S")

    def abs_page(href):
        return f'<html><div class="abs-license"><a href="{href}" title="Rights to this article" class="has_license">license</a>'
    cc = "http://creativecommons.org/licenses/"
    gh, gl, files = "https://api.github.com/repos/", "https://gitlab.com/api/v4/projects/", "/contents/"
    page = lambda mirror: f'<html><head><meta name="github_feedback_content_git_url" content="https://github.com/{mirror}/blob/main/docs/a.md" />'  # noqa: E731
    repo = lambda spdx, **kw: json.dumps({"license": {"spdx_id": spdx} if spdx else None, **kw})  # noqa: E731
    names = lambda *n: json.dumps([{"name": x, "type": "file"} for x in n])  # noqa: E731
    learn = "https://learn.microsoft.com/en-us/test/"
    pages = {
        "https://arxiv.org/abs/2310.11511": (200, abs_page(cc + "by/4.0/")),
        "https://arxiv.org/abs/2411.04403": (200, abs_page(cc + "by-sa/4.0/")),
        "https://arxiv.org/abs/2107.05720": (200, abs_page(cc + "by-nc-sa/4.0/")),
        "https://arxiv.org/abs/2302.09947": (200, abs_page(cc + "by-nc-nd/4.0/")),
        "https://arxiv.org/abs/2406.99999": (200, abs_page("http://arxiv.org/licenses/nonexclusive-distrib/1.0/")),
        "https://arxiv.org/abs/2402.13350v2": (200, abs_page("http://creativecommons.org/publicdomain/zero/1.0/")),
        "https://arxiv.org/abs/2403.14403": (200, "<html><body>no licence here</body></html>"),
        gh + "Org/Repo": (200, repo("MIT")),
        gh + "Org/Source": (200, repo("BUSL-1.1")),
        gh + "Org/Nc": (200, repo("CC-BY-NC-4.0")),
        gh + "Org/None": (200, repo(None)),
        gh + "Org/Other": (200, repo("NOASSERTION")),
        gl + "grp%2Fsub%2Fproj?license=true": (200, json.dumps({"license": {"key": "apache-2.0", "name": "Apache License 2.0"}})),
        learn + "page-a": (200, page("Org/Docs")), gh + "Org/Docs": (200, repo("MIT", archived=False)),
        gh + "Org/Docs" + files: (200, names("LICENSE", "LICENSE-CODE", "README.md")),
        learn + "page-b": (200, page("Org/Old")), gh + "Org/Old": (200, repo("CC-BY-4.0", archived=True)),
        learn + "page-c": (200, page("Org/Private")), gh + "Org/Private": (404, "{}"),
        learn + "page-d": (200, page("Org/Graph")), gh + "Org/Graph": (200, repo("CC-BY-4.0", archived=False)),
        gh + "Org/Graph" + files: (200, names("LICENSE", "LICENSE.md", "README.md")),
        learn + "page-e": (200, "<html><head><title>no mirror</title>"),
        learn + "page-f": (200, page("Org/Cc")), gh + "Org/Cc": (200, repo("CC-BY-4.0", archived=False)),
        gh + "Org/Cc" + files: (403, "{}"),
    }
    asked = []

    def ask(url, headers=None, limit=20_000_000, method="GET"):
        asked.append((url, dict(headers or {})))
        status, body = pages[url]
        return {"status": status, "headers": {}, "body": body.encode(), "final": url, "hops": [], "error": ""}
    monkeypatch.setattr(provider, "request", ask)

    def add(url, **flags):
        ns = argparse.Namespace(url=url, title="T", publisher="P", licence=None, reuse=None, version="", sha256="")
        ns.__dict__.update(flags)
        code = kbid.cmd_add(ns, root)
        cap = capsys.readouterr()
        rows = [r for r in kbid.read_rows(root) if r["url"] == url]
        return code, cap.out.strip(), cap.err, ((rows[0]["licence"], rows[0]["reuse"]) if rows else None)
    via = " (licence link on the arXiv abstract page)"
    arx = "https://arxiv.org/abs/"
    # arXiv: the abstract page's licence link; CC BY and CC BY-SA copy, an NC or ND licence and the non-exclusive one quote
    code, out, err, got = add(arx + "2310.11511")
    assert code == 0 and out.startswith("S-") and got == ("CC BY 4.0" + via, "copy"), (code, out, err, got)
    assert err.startswith(f"licence read (arxiv, {arx}2310.11511): CC BY 4.0"), err
    assert add(arx + "2411.04403")[3] == ("CC BY-SA 4.0" + via, "copy")
    assert add(arx + "2107.05720")[3] == ("CC BY-NC-SA 4.0" + via, "quote")
    assert add(arx + "2302.09947")[3] == ("CC BY-NC-ND 4.0" + via, "quote")
    assert add(arx + "2406.99999")[3] == ("arXiv non-exclusive distribution licence (no reuse grant)", "quote")
    assert add("https://arxiv.org/pdf/2402.13350v2")[3] == ("CC0 1.0" + via, "copy")  # a PDF url is read at its abstract page
    assert asked[-1][0] == arx + "2402.13350v2"
    code, out, err, got = add(arx + "2403.14403")  # no licence link: nothing is written and the reason is named
    assert code == 2 and out == "" and got is None and "has no licence link" in err and "nothing written" in err, err
    # a GitHub or GitLab repository: its licence as the API gives it; NC, ND and source-available ids quote; an id the forge
    # does not recognise is unread
    assert add("https://github.com/Org/Repo/blob/main/docs/a.md")[3] == ("MIT (repository licence of Org/Repo, from the GitHub API)", "copy")
    assert add("https://github.com/Org/Source")[3][1] == "quote"
    code, out, err, got = add("https://raw.githubusercontent.com/Org/Nc/abc/x.md")
    assert got is not None and got[0].startswith("CC BY-NC 4.0 (repository licence of Org/Nc") and got[1] == "quote", got
    for u in ("https://github.com/Org/None", "https://github.com/Org/Other"):
        code, out, err, got = add(u)
        assert code == 2 and got is None and "recognises no licence" in err, (u, err)
    code, out, err, got = add("https://gitlab.com/grp/sub/proj/-/blob/main/README.md")
    assert got == ("Apache-2.0 (repository licence of grp/sub/proj, from the GitLab API)", "copy"), (code, err, got)
    # a Learn page: its public mirror's licence (the page's github_feedback_content_git_url); archived, private or in
    # conflict (LICENSE beside LICENSE.md, not beside LICENSE-CODE) it is `quote` under the Learn terms
    assert add(learn + "page-a")[3] == ("MIT (public mirror Org/Docs)", "copy")
    terms = "Microsoft Learn terms of use ("
    assert add(learn + "page-b")[3] == (terms + "public mirror Org/Old archived: its licence covers only the archived text)", "quote")
    assert add(learn + "page-c")[3] == (terms + "source repository Org/Private is not public: the GitHub API answers 404)", "quote")
    assert add(learn + "page-d")[3] == (terms + "public mirror Org/Graph: licence files LICENSE, LICENSE.md conflict)", "quote")
    for u, why in ((learn + "page-e", "names no GitHub mirror"), (learn + "page-f", "could not be listed")):
        code, out, err, got = add(u)  # no mirror named, or the listing is rate limited: no pair is guessed
        assert code == 2 and got is None and why in err, (u, err)
    # the fixed pair of code.claude.com and anthropic.com asks nothing
    n = len(asked)
    assert add("https://code.claude.com/docs/en/hooks")[3] == ("Anthropic terms (no open licence)", "quote")
    assert add("https://www.anthropic.com/news/x")[3] == ("Anthropic terms (no open licence)", "quote") and len(asked) == n
    # any other host: the host's most common pair marked check, nothing written, no request
    code, out, err, got = add(wiki + "new")
    assert code == 2 and out == "" and got is None and len(asked) == n, (code, out, err)
    assert "check: the usual pair of wiki.corp.example.com in fixture/_sources.csv is --licence 'Corp wiki terms' --reuse quote (2 of 3 rows)" in err
    assert "nothing written" in err, err
    code, out, err, got = add("https://other.corp.example.com/x")
    assert code == 2 and "check: fixture/_sources.csv holds no row of other.corp.example.com" in err, err
    assert add(wiki + "new", licence="Corp wiki terms", reuse="quote")[3] == ("Corp wiki terms", "quote")  # given, it is written
    # explicit flags always win and ask nothing; one flag alone is refused; a url already in the root is unchanged
    code, out, err, got = add("https://github.com/Org/Repo/blob/main/docs/b.md", licence="Own words", reuse="paraphrase")
    assert code == 0 and got == ("Own words", "paraphrase") and len(asked) == n, (code, err, got)
    code, out, err, got = add(arx + "2310.99999", licence="Own words")
    assert code == 2 and got is None and "together, or neither" in err and len(asked) == n, err
    code, out, err, got = add(arx + "2310.11511")
    assert code == 0 and out.startswith("S-") and "unchanged" in err and len(asked) == n, (code, err)
    assert all("Authorization" not in h for _, h in asked), asked


def test_lookup_eval_passes_on_the_live_kb_and_pack_revalidate_marks_only_the_printed_lines_from_stubbed_pages_and_freshness_lifetime_is_the_poisson_rate_of_a_sources_recorded_changes_else_a_fraction_of_its_page_age_and_kb_pack_and_kb_ask_revalidate_only_a_source_past_it_and_provider_read_maps_a_url_to_its_raw_form_and_prints_the_lines_holding_every_grep_word_and_provider_search_parses_each_providers_search_api_answer_to_date_title_and_url_and_kbid_licence_reads_each_source_family_from_stubbed_answers_and_detect_and_census_check_spare_a_source_a_lookup_revalidated_within_its_providers_pacing_census_lookup_hints(monkeypatch, tmp_path, capsys):
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
    # a stored result younger than the source's freshness lifetime (`reuse`) answers with no request, though the provider's
    # pacing is over; without it the source is asked again (and, here, cut short by the used-up budget)
    held = factdiff.revalidate(printed[:5], reuse={A: 3600})
    assert held["sources"][A]["state"] == "cached" and held["lines"][("public/dsc/a.md", 6)]["outcome"] == "moved", held
    assert factdiff.revalidate(printed[:5])["sources"][A]["state"] == "offline"
    # the census's and refresh's hints: the stored result of a lookup that found a source unchanged spares its request
    # within the provider's pacing (A was found changed, C and D no lookup answered); detect logs it `hinted`, writes
    # no state, and census.py check makes it a row nobody reads and nothing dates
    srcs, rows_p = kbfacts.source_rows(), provider.providers()
    monkeypatch.setattr(factdiff, "ROOT", kbcommon.root("public"))
    monkeypatch.setattr(provider, "pacing", lambda row: 3600)
    hints = factdiff.lookup_hints([A, B, C, D], srcs, rows_p)
    assert list(hints) == [B] and hints[B]["outcomes"] == {"current": 2} and hints[B]["checked_utc"][:10] == rev["date"], hints
    monkeypatch.setattr(provider, "request", request)  # the planted pages again, to see which are asked
    monkeypatch.setattr(factdiff, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(factdiff, "select_ids", lambda a, s: [B])
    monkeypatch.setattr(factdiff, "sources", lambda: srcs)
    monkeypatch.setattr(factdiff, "cited_facts", lambda: {B: [(facts[0][0], "dsc/b.md", 3, facts[0][2])]})
    flog = tmp_path / "factdiff-hint.csv"
    detect = lambda: factdiff.cmd_detect(argparse.Namespace(topic=None, dir=None, file=None, source=[B], date="2026-10-12", out=str(flog),  # noqa: E731
                                                            sitemaps=False, no_save=False), collections.Counter())
    asked.clear()
    detect()
    head = next(r for r in factdiff.read_log(str(flog)) if not r["fact"])
    assert head["verdict"] == "hinted" and head["signal"] == "lookup" and "no request" in head["evidence"] and not asked, (head, asked)
    got = census.factdiff_verdicts(str(flog), {B: "2026-10-01"})[B][1]
    assert got["bucket"] == "NEEDS-READING" and got["note"] == census.HINTED, got
    row = {c: "" for c in census.COLS} | {"id": B, "url": urls[B], **got}
    assert not census.confirmed(row) and census.phase2_rows([row]) == []  # not dated, not read
    census.write_log(str(tmp_path / "census.csv"), [row])
    capsys.readouterr()
    census.cmd_summary(argparse.Namespace(log=str(tmp_path / "census.csv"), factdiff=None), collections.Counter())
    assert re.search(r"^spared by a lookup hint .*: 1$", capsys.readouterr().out, re.M)
    # past the pacing the source is asked again, as it was
    monkeypatch.setattr(provider, "pacing", lambda row: 0)
    asked.clear()
    detect()
    assert any(u.startswith(urls[B]) for u in asked) and factdiff.read_log(str(flog))[0]["verdict"] == "unchanged"
    capsys.readouterr()
    monkeypatch.undo()
    question = good_row()["question"]
    # freshness lifetime: the estimate on a planted history of the state file (no request, no clone): two changes seen
    # give the modified Poisson estimate, one only a tenth of the time since the page date, none the provider's default,
    # a pinned url none; a Learn page's file commits count when the clone cache holds its repository
    stamp = lambda t: datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731
    now = provider.stamp_epoch("2026-10-12T00:00:00Z")
    base = now - 110 * provider.DAY  # its last check is 60 days before `now`
    S1, S2, S3, S4, S5, S7 = (f"S99901{n:02d}" for n in (1, 2, 3, 4, 5, 7))
    purl = {S1: "https://learn.microsoft.com/en-us/test/changing", S2: "https://learn.microsoft.com/en-us/test/once",
            S3: "https://learn.microsoft.com/en-us/test/quiet", S4: f"https://raw.githubusercontent.com/Org/Repo/{'b' * 40}/docs/f.md",
            S5: "https://learn.microsoft.com/en-us/test/always",
            S7: "https://learn.microsoft.com/en-us/entra/identity/orion"}
    hist = Repo(tmp_path / "hist")
    os.makedirs(hist.path)
    hist.git("init", "-q", "-b", "main")
    cols = "id,url,checked_utc,fetched_utc,changed_utc\n"
    for k in range(6):  # a check every 10 days; S1 changed at the third and fifth, S2 at the fourth, S5 at every check
        t = base + 10 * k * provider.DAY
        row = lambda sid, chg: f"{sid},{purl[sid]},{stamp(t)},{stamp(t)},{stamp(chg)}\n"  # noqa: E731
        hist.write("kb/public/_fetch_state.csv", cols + row(S1, base + 20 * provider.DAY * (k >= 2) + 20 * provider.DAY * (k >= 4))
                   + row(S2, base + 30 * provider.DAY * (k >= 3)) + row(S3, base) + row(S4, base)
                   + row(S5, t))
        hist.commit(f"state {k}", "kb/public/_fetch_state.csv")
    hist.write("kb/public/_sources.csv", "id,url,title,publisher,licence,reuse,retrieved_utc,version_or_date,artifact_sha256,used_in,superseded_by\n"
               + "".join(f"{sid},{u},,,,,,{'updated 2026-09-22' if sid == S2 else ''},,,\n" for sid, u in purl.items()))
    docs = tmp_path / "repos" / "github.com__MicrosoftDocs__entra-docs.git"  # the clone cache: this page's file has 3 commits
    os.makedirs(docs.parent)
    Repo(docs.parent).git("init", "-q", "-b", "main", str(docs))
    for n, when in enumerate(stamp(now - d * provider.DAY)[:10] for d in (100, 60, 20)):
        Repo(docs).write("docs/identity/orion.md", f"# Orion {n}\n")
        Repo(docs).git("add", "-A")
        Repo(docs).git("commit", "-q", "-m", f"edit {n}", env={"GIT_COMMITTER_DATE": when + "T12:00:00Z", "GIT_AUTHOR_DATE": when + "T12:00:00Z"})
    monkeypatch.setattr(census, "REPOS", str(docs.parent))
    monkeypatch.setattr(kbcommon, "HOME", hist.path)
    monkeypatch.setattr(provider, "_learn_memo", {})
    monkeypatch.setattr(provider, "request", lambda *a, **k: pytest.fail("a lifetime made a request"))
    proot = argparse.Namespace(path=os.path.join(hist.path, "kb", "public"), name="public")
    psrc = {r["id"]: r for r in csv.DictReader(open(os.path.join(proot.path, "_sources.csv"), encoding="utf-8"))}
    pstate = {r["id"]: r for r in csv.DictReader(open(os.path.join(proot.path, "_fetch_state.csv"), encoding="utf-8"))}
    life = provider.lifetimes(psrc, pstate, provider.providers(), proot, now, hist.path)
    mean = 10 / -math.log((5 - 2 + 0.5) / (5 + 0.5))  # 5 check intervals of 10 days, 2 changes: 22.1 days (the plain rate: 25)
    assert abs(life[S1]["days"] - provider.FRACTION * mean) < 1e-6 and life[S1]["changes"] == 2, life[S1]
    assert life[S1]["basis"] == "2 changes in 5 checks, one every 22 days (Poisson)", life[S1]
    assert life[S5]["days"] is not None and abs(life[S5]["days"] - provider.FRACTION * 10 / -math.log(0.5 / 5.5)) < 1e-6, life[S5]
    assert abs(life[S2]["days"] - provider.FRACTION * 20) < 1e-6 and life[S2]["basis"] == "10% of the 20 days since its page date", life[S2]
    assert life[S3]["days"] == 7.0 and life[S3]["basis"] == "provider default (learn)", life[S3]
    assert life[S4]["days"] is None and life[S4]["basis"].startswith("pinned"), life[S4]
    assert abs(life[S7]["days"] - provider.FRACTION * provider.WINDOW_DAYS / 3) < 1e-6 and life[S7]["changes"] == 3, life[S7]
    assert provider.modified_interval([0, 1, 2], [1]) is None and provider.modified_interval([0], []) is None  # one change is no rate
    # fetch.py --status prints each source's lifetime and age, offline; a source past its lifetime is marked
    monkeypatch.setattr(fetch, "KB", proot.path)
    monkeypatch.setattr(fetch, "read_state", lambda: pstate)
    fetch.status(argparse.Namespace(topic=[], dir=[], file=[], source=[], older_than=None, json=True), psrc)
    shown = {r["id"]: r for r in json.loads(capsys.readouterr().out)}
    assert shown[S1]["lifetime_days"] == round(life[S1]["days"], 1) and shown[S4]["lifetime_days"] is None
    assert shown[S1]["stale"] and shown[S3]["stale"] and not shown[S4]["stale"] and shown[S1]["lifetime_basis"] == life[S1]["basis"]
    fetch.status(argparse.Namespace(topic=[], dir=[], file=[], source=[S1, S4], older_than=None, json=False), psrc)
    out = capsys.readouterr().out.splitlines()
    assert re.search(rf"^{S1} +fetched \S+ +changed \S+ +age \d+\.\dd +lifetime 2\.2d STALE +\(2 changes in 5 checks", out[0]), out
    assert re.search(rf"^{S4} .* never stale +\(pinned", out[1]) and out[2].endswith("stale=1"), out
    # the history is kept: a second read asks git for the log only
    shown_revs = []
    real_git = provider._git
    monkeypatch.setattr(provider, "_git", lambda cwd, *a: shown_revs.append(a[0]) or real_git(cwd, *a))
    assert provider.state_history(proot, hist.path)[S1] == provider.state_history(proot, hist.path)[S1] and "show" not in shown_revs
    monkeypatch.undo()
    # kb_pack and kb_ask.py ask only the cited sources past their lifetime, stamp each stale and reuse a live check
    # younger than the lifetime; revalidate false, KB_NO_REVALIDATE and the kb: hook ask nothing
    monkeypatch.setenv("KB_NO_UPSTREAM", "1")
    monkeypatch.setattr(factdiff, "CACHE", str(tmp_path / "live" / "factdiff"))
    pre = kbfacts.pack_many([question])
    cited = list(dict.fromkeys(i for r in pre["results"] for p in r.get("printed", []) for i in p["ids"]))
    assert cited, pre["text"][-800:]
    plant = lambda late: {i: {"days": 7.0 if i == cited[0] and late else 365.0, "basis": "planted", "changes": 0} for i in cited}  # noqa: E731
    stage = {"late": True}
    monkeypatch.setattr(provider, "lifetimes", lambda srcs, *a, **k: {i: plant(stage["late"])[i] for i in srcs})
    real_state = kbfacts.fresh_state(cited)
    old = {i: {"checked_utc": "2026-01-01T00:00:00Z"} for i in cited}
    monkeypatch.setattr(kbfacts, "fresh_state", lambda sids: (real_state[0], {}, old))
    real_rows = kbfacts.ledger_rows()
    monkeypatch.setattr(kbfacts, "ledger_rows", lambda ids=None: {i: {**r, "version_or_date": ""} for i, r in real_rows.items()})
    first = kbfacts.pack_many([question])["text"]  # the offline pack, its stamps from the planted state
    asked_live = []

    def ask(printed, budget=None, reuse=None):
        ids = sorted({i for p in printed for i in p["ids"]})
        asked_live.append((ids, dict(reuse or {})))
        return {"date": "2026-10-12", "lines": {}, "sources": {i: {"state": "live", "verdict": "unchanged", "why": "",
                                                                    "checked_utc": "2026-10-12T00:00:00Z"} for i in ids}}
    monkeypatch.setattr(factdiff, "revalidate", ask)
    text = kb_mcp.kb_pack({"question": question})
    assert asked_live == [([cited[0]], {cited[0]: 7 * 86400})], asked_live
    lines = text.splitlines()
    stale_line = next(ln for ln in lines if ln.startswith(f"  -> {cited[0]}  "))
    assert re.search(r"  \[stale: \d+d old, lifetime 7d\]  \[live 2026-10-12: unchanged\]$", stale_line), stale_line
    assert not any("[stale" in ln or "[live" in ln for ln in lines if ln.startswith("  -> ") and f" {cited[0]} " not in ln)
    assert lines[-1] == (f"revalidate 2026-10-12: 1 of the {len(cited)} cited source(s) past their freshness lifetime: "
                         "1 source(s) asked live, 0 answered from a check younger than its freshness lifetime"), lines[-1]
    assert kb_mcp.kb_pack({"question": question, "revalidate": False}) == first and len(asked_live) == 1
    monkeypatch.setenv("KB_NO_REVALIDATE", "1")
    assert kb_mcp.kb_pack({"question": question}) == first and kb_ask.plan(question)["text"] == first and len(asked_live) == 1
    monkeypatch.delenv("KB_NO_REVALIDATE")
    assert kb_ask.plan(question, revalidate=False)["text"] == first and len(asked_live) == 1
    assert "[stale: " in kb_ask.plan(question)["text"] and len(asked_live) == 2  # kb_ask.py asks as kb_pack does
    monkeypatch.setattr(factdiff, "revalidate", lambda *a, **k: pytest.fail("the kb: hook revalidated"))
    res = kb_hook.answer("kb: " + question)
    assert res and res["decision"] == "block" and "[stale" not in res["reason"] and "revalidate" not in res["reason"]
    stage["late"] = False  # every source inside its lifetime: nothing is asked, and the last line says so
    monkeypatch.setattr(factdiff, "revalidate", ask)
    quiet = kb_mcp.kb_pack({"question": question}).splitlines()
    assert len(asked_live) == 2 and quiet[-1] == (f"revalidate {factdiff.today()}: none of the {len(cited)} cited source(s) is past "
                                                  "its freshness lifetime, none asked"), quiet[-1]
    monkeypatch.undo()
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
    # provider.py read: each family's url maps to its raw form; the page is fetched once, kept under the read cache and
    # printed as the lines that hold every grep word with the url to cite; a PDF and a miss are reported, not printed
    prov = provider.providers()
    raw = lambda u: provider.raw_url(u, provider.for_url(u, prov))[0]  # noqa: E731
    mapped = {"https://github.com/Org/Repo/blob/v1.2/docs/a.md?plain=1#L5": "https://raw.githubusercontent.com/Org/Repo/v1.2/docs/a.md",
              "https://gitlab.com/org/proj/-/blob/main/a.md": "https://gitlab.com/org/proj/-/raw/main/a.md",
              "https://arxiv.org/abs/2406.12045v2": "https://export.arxiv.org/api/query?id_list=2406.12045v2",
              "https://arxiv.org/abs/hep-th/9901001?context=hep-th": "https://export.arxiv.org/api/query?id_list=hep-th/9901001",
              "https://learn.microsoft.com/en-us/x": "https://learn.microsoft.com/en-us/x?accept=text/markdown",
              "https://code.claude.com/docs/en/hooks": "https://code.claude.com/docs/en/hooks.md",
              "https://modelcontextprotocol.io/specification/x": "https://modelcontextprotocol.io/specification/x.md",
              "https://github.com/Org/Repo/issues/7": "https://github.com/Org/Repo/issues/7",
              "https://example.com/p": "https://example.com/p"}
    assert {u: raw(u) for u in mapped} == mapped
    page = "# Guide\n\nThe Orion scheduler restarts every night.\n\n## Queue\n\nThe Orion queue holds ten thousand jobs.\nThe Orion queue refuses new jobs.\n"
    feed = ('<?xml version="1.0" encoding="UTF-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">'
            "<entry><id>http://arxiv.org/abs/2406.12045v2</id><title>Orion: a benchmark</title><published>2024-06-17T00:00:00Z</published>"
            "<summary>We study queues. The Orion queue holds ten thousand jobs.</summary><author><name>Jan Kowalski</name></author>"
            '<category term="cs.AI"/></entry></feed>')
    html = "<html><body><main><h1>Guide</h1><p>The Orion queue holds ten thousand jobs.</p></main></body></html>"
    blob, abstract, fetched = "https://github.com/Org/Repo/blob/main/docs/a.md", "https://arxiv.org/abs/2406.12045", []
    served = {raw(blob): (200, "text/plain; charset=utf-8", "---\nx: 1\n---\n" + page),
              raw(abstract): (200, "application/atom+xml", feed), "https://example.com/p": (200, "text/html", html),
              "https://arxiv.org/pdf/2406.12045": (200, "application/pdf", "%PDF-1.7\n1 0 obj"),
              "https://example.com/gone": (404, "text/html", "")}

    def serve(url, headers=None, limit=20_000_000, method="GET"):
        fetched.append(url)
        status, ctype, body = served[url]  # an unplanned url raises
        return {"status": status, "headers": {"content-type": ctype}, "body": body.encode(), "final": url, "hops": [], "error": ""}
    monkeypatch.setattr(provider, "request", serve)
    monkeypatch.setattr(provider, "READ_CACHE", str(tmp_path / "read"))

    def read(url, **kw):
        ns = argparse.Namespace(url=url, grep=None, context=0, limit=60, start=1, refresh=False)
        ns.__dict__.update(kw)
        code = provider.cmd_read(ns, prov)
        return code, capsys.readouterr().out
    code, out = read(blob + "#L3", grep="ORION queue", context=1)  # a repository file keeps its own line numbers
    assert code == 0 and out.startswith(f"cite: {blob}\nread: {raw(blob)} (200, text/plain; charset=utf-8, "), out
    assert out.splitlines()[3:] == ["9-", "10:The Orion queue holds ten thousand jobs.", "11:The Orion queue refuses new jobs."], out
    assert "lines: 2 of 11 hold every word of 'ORION queue'" in out
    code, out = read(blob, grep="orion queue")  # the second read is the cache's: no request
    assert code == 0 and "cache of " in out and fetched == [raw(blob)], (out, fetched)
    code, out = read(blob, grep="scheduler queue", refresh=True)  # no line holds both words: the counts of each say where to look
    assert code == 1 and "no line holds every word of 'scheduler queue'; lines holding each: scheduler 1, queue 3" in out
    assert fetched == [raw(blob)] * 2
    code, out = read(abstract, grep="ten thousand")  # an arXiv abstract is its entry of the export API, one sentence a line
    assert code == 0 and f"cite: {abstract}\nread: {raw(abstract)} (200, application/atom+xml, " in out
    assert "The Orion queue holds ten thousand jobs." in out.splitlines()[-1]
    code, out = read(abstract, start=1, limit=3)  # no grep: the text from a line, a few lines at a time
    assert code == 0 and "1:# Orion: a benchmark" in out and "3:authors: Jan Kowalski" in out and "more: raise --max, or --from 4" in out
    code, out = read("https://example.com/p", grep="ten thousand")  # any other page: its HTML reduced to text
    assert code == 0 and out.splitlines()[-1].endswith(":The Orion queue holds ten thousand jobs.")
    code, out = read("https://arxiv.org/pdf/2406.12045")
    assert code == 1 and provider.NOT_TEXT in out, out
    code, out = read("https://example.com/gone", grep="x")
    assert code == 1 and "not read: 404" in out
    assert len(os.listdir(tmp_path / "read")) == 4, os.listdir(tmp_path / "read")  # a 200 is kept (a PDF too), a miss is not
    # provider.py search: each provider's request is its search_api with the terms in the form that API reads, the answer is
    # parsed to date, title and url, and a 200 is kept 7 days (the second call asks nothing); a failure is named, not printed as hits
    answers = {
        "https://learn.microsoft.com/api/search?search=orion%20queue&locale=en-us&$top=10":
            (200, json.dumps({"results": [{"title": "Orion queue", "url": "https://learn.microsoft.com/en-us/orion/queue",
                                           "lastUpdatedDate": "2026-09-25T22:18:00+00:00"}, {"title": "no url"}]})),
        "https://export.arxiv.org/api/query?search_query=all:orion%20AND%20all:queue&max_results=10": (200, feed),
        "https://api.github.com/search/repositories?q=orion%20queue&per_page=10":
            (200, json.dumps({"items": [{"full_name": "Org/Repo", "description": "An  Orion\nqueue", "html_url": "https://github.com/Org/Repo",
                                         "pushed_at": "2026-07-20T10:00:00Z"}]})),
        "https://api.github.com/search/code?q=orion%20repo:Org%2FRepo&per_page=10":
            (200, json.dumps({"items": [{"repository": {"full_name": "Org/Repo"}, "path": "docs/a.md",
                                         "html_url": "https://github.com/Org/Repo/blob/abc/docs/a.md"}]})),
        "https://pypi.org/pypi/orion-queue/json":
            (200, json.dumps({"info": {"name": "orion-queue", "version": "1.2", "summary": "A queue",
                                       "package_url": "https://pypi.org/project/orion-queue/"},
                              "urls": [{"upload_time_iso_8601": "2026-08-01T09:00:00.1Z"}, {"upload_time_iso_8601": "2026-08-01T09:00:01.2Z"}]})),
        "https://pypi.org/pypi/orion-gone/json": (404, ""),
        "https://learn.microsoft.com/api/search?search=orion%20limited&locale=en-us&$top=10": (429, ""),
        "https://api.github.com/search/code?q=orion%20nowhere&per_page=10": (401, "{}"),
    }
    asked = []

    def ask(url, headers=None, limit=20_000_000, method="GET"):
        asked.append((url, dict(headers or {})))
        status, body = answers[url]  # an unplanned url raises
        return {"status": status, "headers": {}, "body": body.encode(), "final": url, "hops": [], "error": ""}
    monkeypatch.setattr(provider, "request", ask)
    monkeypatch.setattr(provider, "SEARCH_CACHE", str(tmp_path / "search"))
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_planted")  # no credential is read: no request carries one
    monkeypatch.setenv("GH_TOKEN", "ghp_planted")

    def find(name, *terms, **kw):
        ns = argparse.Namespace(name=name, terms=list(terms), limit=5, refresh=False)
        ns.__dict__.update(kw)
        code = provider.cmd_search(ns, prov)
        return code, capsys.readouterr().out.splitlines()
    code, out = find("learn", "orion", "queue")  # a hit with no url is dropped; the date is the day of lastUpdatedDate
    assert code == 0 and out[1:] == ["1. 2026-09-25  Orion queue", "   https://learn.microsoft.com/en-us/orion/queue"], out
    assert out[0].startswith("search: learn 'orion queue' (https://learn.microsoft.com/api/search?search=orion%20queue") and "fetched " in out[0]
    code, out = find("arxiv", "orion", "queue")  # every word is an `all:` term of the export API's search_query
    assert code == 0 and out[1:] == ["1. 2024-06-17  Orion: a benchmark", "   https://arxiv.org/abs/2406.12045v2"], out
    code, out = find("github", "orion queue")  # words in one argument or several are the same query; a description is one line
    assert code == 0 and out[1:] == ["1. 2026-07-20  Org/Repo: An Orion queue", "   https://github.com/Org/Repo"], out
    code, out = find("github-blob", "orion", "repo:Org/Repo")  # code search: a file of a repository, no date
    assert code == 0 and out[1:] == ["1. -  Org/Repo: docs/a.md", "   https://github.com/Org/Repo/blob/abc/docs/a.md"], out
    code, out = find("pypi", "orion", "queue")  # the terms joined by `-` are the project name; the newest upload is the date
    assert code == 0 and out[1:] == ["1. 2026-08-01  orion-queue 1.2: A queue", "   https://pypi.org/project/orion-queue/"], out
    assert len(asked) == 5, asked
    code, out = find("learn", "orion", "queue", limit=1)  # the same request again is the cache's: no request
    assert code == 0 and "cache of " in out[0] and len(asked) == 5
    code, out = find("pypi", "orion", "gone")  # a project that does not exist answers 404: no hit, and the answer is kept
    assert code == 1 and out[1:] == ["no hit"], out
    code, out = find("learn", "orion", "limited")
    assert code == 1 and out[1] == "not searched: 429; the API's rate limit, ask again later", out
    code, out = find("github-blob", "orion", "nowhere")
    assert code == 1 and out[1].startswith("not searched: 401") and "WebSearch" in out[1] and "GITHUB_TOKEN" not in out[1], out
    assert len(os.listdir(tmp_path / "search")) == 6, os.listdir(tmp_path / "search")  # the 200s and the 404 are kept, a 429 and a 401 are not
    find("github", "orion", "queue", refresh=True)  # a refreshed ask sends no Authorization header either
    assert asked[-1][0].startswith("https://api.github.com/") and all("Authorization" not in h for _, h in asked), asked
    code, out = find("generic", "orion")  # a row with no search_api is named, with the rows that have one
    assert code == 2 and "has no search_api" in out[0] and "learn" in out[0] and "pypi" in out[0], out
    kbid_licence_families(monkeypatch, tmp_path, capsys)


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


def test_pack_scatter_check_notes_a_scattered_weak_good_and_pack_routes_kind_to_its_tool_and_prints_coverage_fact_lines_and_pack_freshness_stamp_and_a_pinned_source_of_a_404_repository_is_gone_pinned_repo_gone_and_a_page_whose_other_section_changed_keeps_the_facts_of_the_rest_section_hash_and_router_broad_lookups_leave_each_question_whose_plain_pack_is_good_to_the_pack(monkeypatch, tmp_path, capsys):
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
    # the three further notes, a plain word the kb holds in a few lines of other topics while the lead article's facts
    # miss other key words (`passing`), a price asked with no amount in them (`priced`) and a multi-word name that no
    # printed fact holds beside the question's plain words (`parted`): each a `check:` line that routes `split` with
    # what the kb lacks and leaves the verdict, and no eval good carries one
    flagged = [q for q, p in packs.items() if p["passing"] or p["priced"] or p["parted"]]
    assert all(packs[q]["verdict"] == "good" and packs[q]["route"] == "split" and "\nkb lacks: " in packs[q]["text"]
               and re.search(r"^check: .*\n(?:.+\n)*route: split$", packs[q]["text"], re.M) for q in flagged), flagged
    assert not [q for q in flagged if q not in offkb], [q for q in flagged if q not in offkb]  # no eval good carries one
    # the eval counts each row expecting `good` whose pack prints a check: or route: line (`noted`, the totals line's
    # noted=N), and its default run fails above rag.NOTED_BASELINE: the count here is within it, and a planted file of
    # one noted and one clean good row counts the one
    carries = lambda q: re.search(r"^(check|route):", packs[q]["text"], re.M)
    goods = [r for r in eval_rows() if r["expect_verdict"] == "good"]
    held = [r for r in goods if carries(r["question"])]
    assert len(held) <= rag.NOTED_BASELINE, [r["id"] for r in held]
    plan = [r for r in held[:1]] + [next(r for r in goods if not carries(r["question"]))]
    plant = tmp_path / "noted.csv"
    with open(plant, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(plan[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(plan)
    res = rag.run_eval(str(plant))
    assert res["noted"] == len(held[:1]) and [r["noted"] for r in res["rows"]] == [True] * len(held[:1]) + [False], res["noted"]
    # planted: a root whose lead article holds the question's subject in passing, a price asked with no amount stated,
    # and a question its lead article answers outright, which stays clean
    fx = tmp_path / "passing"
    fixture_root(fx, SID)
    facts = {"hardening": ("Print server hardening", ["Encryption at rest protects the sweeper files of the Spooler service."]),
             "capacity": ("Print capacity", ["The recommended number of queues is 50 for the Spooler.",
                                             "Spooled files live on disk, and the Spooler keeps them."]),
             "licensing": ("Licensing", ["The Spooler service plan includes the sweeper licence per print server.",
                                         "A licence for the Spooler service plan is bought through the reseller."]),
             "labels": ("Labels", ["The price tag of an item is printed on its label."]),
             "sizing": ("Sizing", [f"The recommended number of {w} is {n}." for n, w in enumerate(
                 "gadgets widgets lamps fans pumps valves".split(), 2)]),
             "relay": ("Relay", ["The Relay Gateway service listens on port 9100 for print jobs.",
                                 "Archived queues keep a retention window of 30 days for the Spooler.",
                                 "The relay agent writes its logs to the local disk."]),
             "misc": ("Miscellany", [f"Item {w} behaves in its own way {n}." for n, w in enumerate(
                 "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma tau".split())])}
    for slug, (title, lines) in facts.items():
        write(fx / "print" / f"{slug}.md",
              f"---\ntopic: print/{slug}\npriority: P1\napplies_to: \"PL-SRV-0042 print servers\"\nretrieved_utc: 2026-09-26\n"
              f"sources: [{SID}]\nstatus: partial\n---\n\n# {title}\n\n## Summary\nA fixture.\n\n## Facts\n"
              + "".join(f"- {line} [DOC {SID}]\n" for line in lines) + "\n## Reference\n\n## Examples\n")
    env = {**os.environ, "KB_ROOTS": str(fx), "KB_INDEX": str(tmp_path / "packidx")}
    env.pop("KB_DOC2QUERY", None)

    def fixture_pack(question):
        p = subprocess.run([sys.executable, "-c", PACK_FIXTURE, TOOLS, question], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env)
        assert p.returncode == 0, p.stdout[-1500:] + p.stderr[-1500:]
        return p.stdout
    for question, kind in (("What is the recommended number of sweeper files for the Spooler?", "held by only a few lines"),
                           ("What is the price of the Spooler service plan licence?", "asks for a price"),
                           ("How do I set the Relay Gateway retention window for the Spooler queues?", "Relay Gateway beside")):
        out = fixture_pack(question)
        assert re.search(r"^coverage: good\b", out, re.M) and "check: " in out and kind in out, out[:1200]
        assert re.search(r"^route: split$", out, re.M) and re.search(r"^kb lacks: \S", out, re.M), out[:1200]
    # one key word of five missing from the lead's facts, its rare word printed there, is a paraphrase: clean
    for question in ("What is the recommended number of queues for the Spooler?",
                     "What is the recommended number of queues for the Spooler item?",
                     "What port does the Relay Gateway service listen on for print jobs?"):
        out = fixture_pack(question)
        assert re.search(r"^coverage: good\b", out, re.M) and not re.search(r"^(check|route):", out, re.M), out[:1200]
    assert not kbfacts.PRICE_ASK.search("What does it cost in resource units?")
    assert kbfacts.PRICE_ASK.search("How much is a licence per user per month?") and not kbfacts.PRICE_ASK.search("How much memory does it use?")
    assert kbfacts.PRICE_ASK.search("What does it cost per user?") and kbfacts.PRICE_ASK.search("What is the price in units of 5?")
    assert kbfacts.AMOUNT.search("It costs $36 per user a month") and kbfacts.AMOUNT.search("36 EUR")
    assert not kbfacts.AMOUNT.search("Windows 10/11 Enterprise E3/E5 licence") and kbfacts.PRICE_ASK.search("How much does it cost")
    code, out = tool("rag.py", "pack", good_row()["question"])
    assert code == 0, out[-1500:]
    assert re.search(r"^coverage: good\b", out, re.M), out[:1500]
    assert re.search(r"\S+\.md:\d+.*\[(DOC|CODE|DER|COMMUNITY|UNK)\b", out), out[:1500]
    assert kbfacts.routed(good_row()["question"]) is None  # a question of no kind a tool decides ranks as pack ranks it
    # router_broad_lookups: a kind expert never takes a question whose plain pack is good. The probe set is built from
    # the kb: one `What does the kb say about <title>?` per article (its topic where it has no heading), then the eval,
    # held-out and off-kb questions; each is named that kbfacts.routed answers while kbfacts.pack is good on an article
    class Text(str):  # the ledger scan splits its file again for each entry it holds: one split of a text here
        cut = None

        def splitlines(self, *a):
            if self.cut is None:
                self.cut = str.splitlines(self)
            return self.cut

    def hijacked(questions):
        out = []
        for q in dict.fromkeys(questions):
            res = kbfacts.routed(q)
            plain = kbfacts.pack(q) if res else None
            if res and plain["verdict"] == "good" and plain["paths"]:
                out.append(f"{q} (routed by kind: {', '.join(res['routed']['kinds'])}; pack good on {plain['paths'][0]})")
        return out

    def title_of(path, meta):
        head = re.search(r"^# (.+)$", kbfacts.read(path) or "", re.M)
        return head.group(1).strip() if head else meta["topic"].rsplit("/", 1)[-1].replace("-", " ")
    with open(heldout, encoding="utf-8", newline="") as f:
        held_rows = [r["question"] for r in csv.DictReader(f)]
    probe = [f"What does the kb say about {title_of(p, m)}?" for p, m in sorted(kbfacts.articles().items())]
    probe += [r["question"] for r in eval_rows()] + held_rows + offkb
    assert len(probe) > len(kbfacts.articles()) + len(eval_rows()), len(probe)
    memo = {}
    plain_read = kbfacts.read

    def read_once(path):
        if path not in memo:
            text = plain_read(path)
            memo[path] = Text(text) if text else text
        return memo[path]
    with monkeypatch.context() as mp:
        mp.setattr(kbfacts, "read", read_once)
        found = hijacked(probe)
        assert not found, found
        # planted: an expert whose cue shows on every question and that answers every one is named for a good pack
        loose = lambda q, domain, root, invalidated: [{"key": ("planted.md", 1), "kind": "gap", "path": "planted.md",  # noqa: E731
                                                       "title": "planted", "lacks": True, "lines": ["- planted.md:1 [gap]"]}]
        mp.setattr(kbfacts, "EXPERTS", (("gap", re.compile("."), loose),))
        named = hijacked([good_row()["question"]])
        assert len(named) == 1 and named[0].startswith(good_row()["question"] + " (routed by kind: gap;"), named
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
    # the stamp reads only the anchor and fetch-state rows of the sources it cites, the rows a whole read holds for
    # them; a url's signals come from a memo file once seen, with no provider call, and from provider alone otherwise
    cited = set(res["sources"])
    with monkeypatch.context() as mp:
        mp.setattr(kbfacts, "_FRESH", [None, {}, {}, {}, set(), 0, False])
        anchors, verified, state = kbfacts.fresh_state(cited)
        want_a, want_s = {}, {}
        for r in kbfacts.kbcommon.roots():
            for row in csv.DictReader(open(os.path.join(r.path, kbfacts.kbcommon.ANCHORS), encoding="utf-8-sig", newline="")):
                if row["source_id"] in cited:
                    want_a[(row["fact"], row["path"], row["source_id"])] = (row["status"] == "located", row["verified_utc"])
            for row in csv.DictReader(open(os.path.join(r.path, kbfacts.kbcommon.STATE), encoding="utf-8-sig", newline="")):
                if row["id"] in cited:
                    want_s[row["id"]] = row
        assert anchors == want_a and state == want_s and want_a and set(verified) <= cited, (len(anchors), len(want_a))
        assert {k[2] for k in anchors} <= cited and set(state) <= cited
        mp.setenv("KB_INDEX", str(tmp_path / "signals"))
        mp.setattr(kbfacts, "_SIGNALS", {})
        mp.setattr(kbfacts, "_SIGNALS_KEY", [None])
        urls = [u for _, u, _ in res["source_rows"]]
        want = {u: provider.signals(provider.for_url(u, provider.providers()) or {}, u) for u in urls}
        assert {u: kbfacts.provider_signals(u) for u in urls} == want and provider.ROOT_FILE == "_providers.csv"
        mp.setattr(kbfacts, "_SIGNALS", {})
        mp.setattr(kbfacts, "_SIGNALS_KEY", [None])
        mp.setattr(provider, "signals", lambda *a, **k: 1 / 0)
        assert {u: kbfacts.provider_signals(u) for u in urls} == want
    unit = next(u for u in kbfacts.units("public") if any(p["kind"] != "UNK" and p["ids"] for p in u["tags"]))
    sid = next(i for p in unit["tags"] if p["kind"] != "UNK" for i in p["ids"])
    key, rel = kbfacts.fact_key(unit["text"]), kbfacts.bare(unit["path"])
    rows = {sid: {"id": sid, "url": "https://example.com/p"}}

    def mark(anchor, changed):
        state = {sid: {"changed_utc": changed}}
        monkeypatch.setattr(kbfacts, "fresh_state", lambda sids: ({(key, rel, sid): anchor} if anchor else {}, {}, state))
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
