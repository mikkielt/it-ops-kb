"""Merge-rule tests: .gitattributes union merges plus `kbgit.py fix` give a clean kb (`python3 _tools/tests.py -k merge`).

  TestMergeRules           kbgit.py functions on in-memory text (no git needed)
  TestMergeInGit           (marker git) a throwaway git repo (a copy of the kb without .git): two branches add sources, answers,
                           gaps and fetch state, both take the legacy id S9999 for different urls; merged with the
                           real .gitattributes, then `kbgit.py fix --base <merge-base>`. Skipped without git.
"""
import csv, io, os, re, shutil

import pytest

import kbgit, kbid
from conftest import KB, SOURCES_HEADER as HEADER, Repo, copy_kb, requires_git


def rows(text):
    return list(csv.DictReader(io.StringIO(text)))


class TestMergeRules:
    def test_strip_markers_is_union(self):
        t = "a\n<<<<<<< HEAD\nb\n||||||| base\nold\n=======\nc\n>>>>>>> other\nd\n"
        assert kbgit.strip_markers(t, "x") == ("a\nb\nc\nd\n", 1)
        assert kbgit.strip_markers("Title\n=======\n", "x") == ("Title\n=======\n", 0)  # a setext heading stays
        with pytest.raises(kbgit.Problem):
            kbgit.strip_markers("<<<<<<< HEAD\nb\n", "x")

    def test_sources_duplicates_and_field_merge(self):
        u = "https://learn.microsoft.com/en-us/a"
        old = f"S100,{u},Old title,Microsoft,,2026-01-01,v1,,,\n"
        new = f"S100,{u}/,New title,Microsoft,CC BY 4.0,2026-02-01,v2,,x.md,\n"
        report = []
        header, out, renames = kbgit.resolve_sources(HEADER + old + HEADER + new + old + "S2,https://e.example.com/,t,p,l,d,v,,,S100\n",
                                                     None, {}, report)
        assert [r["id"] for r in out] == ["S2", "S100"]
        r = out[1]
        assert (r["title"], r["licence"], r["retrieved_utc"], r["version_or_date"]) == ("New title", "CC BY 4.0", "2026-02-01", "v2")
        assert not renames
        assert any("title" in x and x.startswith("WARN") for x in report), report
        with pytest.raises(kbgit.Problem):  # same date, two titles: a human decides
            kbgit.resolve_sources(HEADER + old + old.replace("Old title", "Other"), None, {}, [])

    def test_sources_base_copy_yields_to_edit(self):
        u = "https://learn.microsoft.com/en-us/a"
        base = f"S100,{u},Title,Microsoft,,2026-01-01,v1,,,\n"
        edit = base.replace("Title", "Better title")
        base_rows = {r["id"]: r for r in rows(HEADER + base)}
        _, out, _ = kbgit.resolve_sources(HEADER + base + edit, base_rows, {}, [])
        assert [r["title"] for r in out] == ["Better title"]

    def test_collision_needs_base(self):
        t = HEADER + "S9999,https://a.example.com/x,a,p,l,2026-01-01,v,,,\nS9999,https://b.example.com/y,b,p,l,2026-01-01,v,,,\n"
        with pytest.raises(kbgit.Problem) as e:
            kbgit.resolve_sources(t, None, {}, [])
        assert "--base" in str(e.value)
        side = {"a": {"S9999": {"url": "https://a.example.com/x"}}, "b": {"S9999": {"url": "https://b.example.com/y"}}}
        _, out, renames = kbgit.resolve_sources(t, {}, side, [])
        assert sorted(r["id"] for r in out) == sorted([kbid.source_id("https://a.example.com/x"), kbid.source_id("https://b.example.com/y")])
        assert sorted(o for _, _, owners in renames["S9999"] for o in owners) == ["a", "b"]

    def test_repeated_header_and_short_row(self):
        """A union merge repeats the header line (dropped); a row short by a column is an error, not padded."""
        u = "https://learn.microsoft.com/en-us/a"
        report = []
        _, out, _ = kbgit.resolve_sources(HEADER + f"S100,{u},T,Microsoft,,2026-01-01,v1,,x.md,\n" + HEADER, None, {}, report)
        assert [r["id"] for r in out] == ["S100"]
        assert any("repeated header" in x for x in report), report
        with pytest.raises(kbgit.Problem):
            kbgit.resolve_sources(HEADER + "S102,https://c.example.com/,t,p,l,d,v,,\n".replace(",,\n", ",\n"), None, {}, [])

    def test_latest_row_wins_a_field_conflict(self):
        u = "https://github.com/o/r"
        current = f"S100,{u},T,P,Apache-2.0,2026-09-25,v; confirmed 2026-09-25: x,,a.md,\n"
        newer = f"S100,{u},T,P,MIT,2026-09-26,v2,,a.md,\n"
        for text in (HEADER + current + newer, HEADER + newer + current):
            report = []
            _, out, _ = kbgit.resolve_sources(text, None, {}, report)
            assert (out[0]["licence"], out[0]["version_or_date"]) == ("MIT", "v2")
            assert any(x.startswith("WARN") and "licence" in x for x in report), report
        with pytest.raises(kbgit.Problem):  # same date, different licence: a human decides
            kbgit.resolve_sources(HEADER + current + current.replace("Apache-2.0", "MIT"), None, {}, [])

    def test_pushed_side_keeps_a_colliding_id(self):
        a, b = "https://a.example.com/x", "https://b.example.com/y"
        t = HEADER + f"S9999,{a},a,p,l,2026-01-01,v,,,\nS9999,{b},b,p,l,2026-01-01,v,,,\n"
        side = {"up": {"S9999": {"url": a}}, "mine": {"S9999": {"url": b}}}
        _, out, renames = kbgit.resolve_sources(t, {}, side, [], upstream="up")
        assert {r["id"]: r["url"] for r in out} == {"S9999": a, kbid.source_id(b): b}
        assert renames == {"S9999": [(b, kbid.source_id(b), ["mine"])]}
        assert kbgit.source_plan(renames, out)["S9999"]["strict_base"] == False  # S9999 still names a's url

    def test_colliding_answer_ids_are_renamed(self):
        up = "# A\n\n## QK-shared. What does clone a ask?\n\nA. [DOC S1]\n"
        mine = "# A\n\n## QK-shared. What does clone b ask about sync?\n\nB.\n"
        merged = up + "\n## QK-shared. What does clone b ask about sync?\n\nB.\n"
        report, problems = [], []
        plan = kbgit.answer_plan(merged, "# A\n", up, {"up": up, "mine": mine}, report, problems)
        assert problems == []
        assert plan["QK-shared"]["by_side"] == {"mine": kbid.answer_id("What does clone b ask about sync?")}
        assert kbgit.renumbered("\n".join("  " + x for x in report)) == report
        # no base, no pushed side: the first heading keeps the id; a unique id is never touched
        plan = kbgit.answer_plan(merged, None, None, {"up": up, "mine": mine}, [], [])
        assert list(plan) == ["QK-shared"]
        assert kbgit.answer_plan(up, None, None, {}, [], []) == {}
        assert kbgit.answer_plan("## QK7. q\n", "## QK7. q\n", None, {}, [], []) == {}  # check.py's business

    def test_answer_mentions_follow_only_the_owning_side(self):
        """A renamed colliding id is rewritten on the owner's lines; the pushed side's own mention and docs stay."""
        assert not {"README.md", "AGENTS.md", "CLAUDE.md"} & set(kbgit.id_files())
        up = {"x/a.md": "# A\n- The other kb calls it QK-dup.\n", "_answers.md": "# A\n\n## QK-dup. Pushed question\n"}
        mine = {"x/a.md": "# A\n- Answer: `_answers.md` QK-dup.\n", "_answers.md": "# A\n\n## QK-dup. Local question\n"}
        merged = {"x/a.md": "# A\n- The other kb calls it QK-dup.\n- Answer: `_answers.md` QK-dup.\n",
                  "_answers.md": "# A\n\n## QK-dup. Pushed question\n\n## QK-dup. Local question\n"}
        revs = {"base": {"x/a.md": "# A\n", "_answers.md": "# A\n"}, "up": up, "mine": mine}
        saved = kbgit.id_files, kbgit.read, kbgit.show
        try:
            kbgit.id_files, kbgit.read = (lambda: sorted(merged)), merged.get
            kbgit.show = lambda rev, f: revs[rev].get(f)
            plan = kbgit.answer_plan(merged["_answers.md"], revs["base"]["_answers.md"], up["_answers.md"],
                                     {"up": up["_answers.md"], "mine": mine["_answers.md"]}, [], [])
            texts, problems = {}, []
            kbgit.rewrite_ids(plan, "base", {"up": "up", "mine": "mine"}, texts, set(), problems, [])
        finally:
            kbgit.id_files, kbgit.read, kbgit.show = saved
        new = kbid.answer_id("Local question")
        assert problems == []
        assert texts["x/a.md"] == f"# A\n- The other kb calls it QK-dup.\n- Answer: `_answers.md` {new}.\n"
        assert texts["_answers.md"] == f"# A\n\n## QK-dup. Pushed question\n\n## {new}. Local question\n"

    def test_fetch_state_one_row_per_id(self):
        h = "id,url,checked_utc,fetched_utc,changed_utc,sha256,text_sha256,bytes,error\n"
        a = "S100,https://x.example.com/,2026-03-01T00:00:00Z,2026-02-01T00:00:00Z,2026-01-01T00:00:00Z,old,old,1,timeout\n"
        b = "S100,https://x.example.com/,2026-02-15T00:00:00Z,2026-02-15T00:00:00Z,2026-02-15T00:00:00Z,new,new,2,\n"
        c = "S-aaaaaaaa,https://y.example.com/,2026-01-01T00:00:00Z,,,,,,\n"
        out = rows(kbgit.resolve_state(h + c + a + h + b, {}, []))
        assert [r["id"] for r in out] == ["S100", "S-aaaaaaaa"]
        r = out[0]
        assert (r["checked_utc"], r["error"]) == ("2026-03-01T00:00:00Z", "timeout")  # latest check
        assert (r["fetched_utc"], r["sha256"], r["bytes"]) == ("2026-02-15T00:00:00Z", "new", "2")  # latest fetch
        assert r["changed_utc"] == "2026-02-15T00:00:00Z"

    def test_markdown_dedupe(self):
        item = "- **A gap that both branches recorded.** Tried S100 and S101. [UNK]"
        text = (f"# Gaps\n\n## auth\n\n{item}\n- none\n- none\n{item}\n\n| a | b |\n|---|---|\n| 1 | 2 |\n| 1 | 2 |\n\n"
                f"| c |\n|---|\n```\n## not a heading\n## not a heading\n```\n\n## dsc\n\n- x\n\n## dsc\n\n- x\n")
        out = kbgit.resolve_md(text, "_gaps.md", [], [])
        assert out.count(item) == 1
        assert out.count("- none") == 2  # short items may repeat on purpose
        assert out.count("| 1 | 2 |") == 1
        assert out.count("|---|") == 2  # separators of two tables stay
        assert out.count("## dsc") == 1
        assert out.count("## not a heading") == 2  # code blocks are never deduplicated
        assert kbgit.resolve_md(out, "_gaps.md", [], []) == out  # idempotent

    def test_zealous_splice_is_repaired(self):
        """git keeps a footer both added blocks end with only once: the first answer loses it to the second."""
        a = "# A\n\n## QK-a. qa\n- a1 [DOC S1]\n\n_Agent: kb-research_\n\n## R1. r\n"
        b = "# A\n\n## QK-a. qb\n- b1 [DOC S2205]\n\n_Agent: kb-research_\n\n## R1. r\n"
        spliced = "# A\n\n## QK-a. qa\n- a1 [DOC S1]\n## QK-b. qb\n- b1 [DOC S-aaaaaaaa]\n\n_Agent: kb-research_\n\n## R1. r\n"
        whole = "# A\n\n## QK-a. qa\n- a1 [DOC S1]\n\n_Agent: kb-research_\n\n## QK-b. qb\n- b1 [DOC S-aaaaaaaa]\n\n_Agent: kb-research_\n\n## R1. r\n"
        report = []
        assert kbgit.resolve_md(spliced, "_answers.md", report, [], [a, b]) == whole  # ids renamed since: ignored
        assert any("restored 1 line(s)" in r for r in report), report
        assert kbgit.resolve_md(whole, "_answers.md", [], [], [a, b]) == whole  # idempotent
        assert kbgit.resolve_md(spliced, "_answers.md", [], []) == spliced  # sides unknown: left alone
        cut = spliced.replace("\n\n_Agent: kb-research_\n\n## R1", "\n\n## R1")  # the tail is not where the merge puts it
        assert kbgit.resolve_md(cut, "_answers.md", [], [], [a, b]) == cut

    def test_answer_id_clash_is_a_problem(self):
        problems = []
        kbgit.resolve_md("# A\n\n## QK-x. q\n\none\n\n## QK-x. q\n\ntwo\n", "_answers.md", [], problems)
        assert problems and "QK-x" in problems[0]
        problems = []
        out = kbgit.resolve_md("# A\n\n## QK-x. q\n\none\n\n## QK-x. q\n\none\n", "_answers.md", [], problems)
        assert (problems, out.count("## QK-x.")) == ([], 1)

    def test_gitattributes_pins_every_artifact(self):
        with open(os.path.join(KB, ".gitattributes"), encoding="utf-8") as f:
            attrs = f.read()
        with open(os.path.join(KB, "_artifacts.csv"), encoding="utf-8") as f:
            pinned = kbgit.pinned_paths(f.read())
        assert kbgit.resolve_attrs(attrs, pinned) == attrs, ".gitattributes pinned block is stale; run python3 _tools/kbgit.py fix"
        for name in ("_sources.csv", "_fetch_state.csv", "_answers.md", "_gaps.md", "_conflicts.md"):
            assert re.search(rf"(?m)^{re.escape(name)} merge=union$", attrs)
        assert not re.search(r"(?m)^README\.md .*merge=", attrs)


@requires_git
@pytest.mark.git
class TestMergeInGit:
    URL_A, URL_B = "https://learn.microsoft.com/en-us/merge-test/branch-a", "https://learn.microsoft.com/en-us/merge-test/branch-b"
    STATE_H = "id,url,checked_utc,fetched_utc,changed_utc,sha256,text_sha256,bytes,error\n"
    FOOTER = "_Agent: merge-test_"

    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def scenario(cls, tmp_path_factory):
        cls.tmp = tmp_path_factory.mktemp("kb-merge")
        cls.repo = Repo(copy_kb(cls.tmp / "kb", skip=("_fetch_state.csv",)))
        cls.repo.write("_fetch_state.csv", cls.STATE_H + "S100,https://x.example.com/,2026-01-01T00:00:00Z,2026-01-01T00:00:00Z,"
                  "2026-01-01T00:00:00Z,s0,t0,1,\nS101,https://y.example.com/,2026-01-01T00:00:00Z,,,,,,\n")
        cls.repo.git("init", "-q", "-b", "main")
        cls.repo.git("add", "-A")
        cls.repo.git("commit", "-q", "-m", "base")
        cls.base = cls.repo.git("rev-parse", "HEAD").strip()
        cls.dirty_after_init = cls.repo.git("status", "--porcelain")
        cls.branch("a", cls.URL_A, "2026-09-26T00:00:00Z")
        cls.repo.git("checkout", "-q", "main")
        cls.branch("b", cls.URL_B, "2026-09-27T00:00:00Z")
        cls.repo.git("checkout", "-q", "a")
        cls.merge = cls.repo.run_git("merge", "--no-edit", "b")
        cls.fix = cls.repo.kbgit("fix", "--base", cls.base)
        yield
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def branch(cls, name, url, checked):
        """A branch that adds the same legacy id S9999 (for its own url), a hash-id source, an article citing both,
        an answer, a gap and a fetch of S100, then rebuilds the index as a writer would."""
        cls.repo.git("checkout", "-q", "-b", name)
        extra = f"https://learn.microsoft.com/en-us/merge-test/extra-{name}"
        hid = kbid.source_id(extra)
        cls.repo.write("_sources.csv", f"S9999,{url},Merge test {name},Microsoft,MIT,2026-09-25,v,,,\n"
                                  f"{hid},{extra},Extra {name},Microsoft,MIT,2026-09-25,v,,,\n", "a")
        cls.repo.write(f"windows/merge-test-{name}.md",
                  f"---\ntopic: windows/merge-test-{name}\npriority: P3\napplies_to: [test]\nretrieved_utc: 2026-09-25\n"
                  f"sources: [S9999, {hid}]\nstatus: partial\n---\n# Merge test {name}\n\n## Summary\n\nTest.\n\n## Facts\n\n"
                  f"- Branch {name} says this. [DOC S9999]\n- And this. [DOC {hid}]\n\n## Reference\n\n## Examples\n")
        cls.repo.write("_answers.md", f"\n## QK-merge-test-{name}. Does branch {name} merge?\n\nYes, says branch {name} [DOC S9999].\n"
                                 f"\n{cls.FOOTER}\n", "a")  # the same last line on both branches: a plain merge splices
        cls.repo.write("_gaps.md", f"\n- **Merge test gap from branch {name}.** Tried nothing, cites S9999. [UNK]\n", "a")
        state = cls.repo.read("_fetch_state.csv").replace(
            "S100,https://x.example.com/,2026-01-01T00:00:00Z,2026-01-01T00:00:00Z,",
            f"S100,https://x.example.com/,{checked},{checked},")
        cls.repo.write("_fetch_state.csv", state)
        r = cls.repo.tool("build_index.py")
        assert r.returncode == 0, r.stdout + r.stderr
        cls.repo.git("add", "-A")
        cls.repo.git("commit", "-q", "-m", f"branch {name}")

    def test_attributes_keep_a_fresh_checkout_clean(self):
        assert self.dirty_after_init == "", "the committed tree is not stable under .gitattributes"
        with open(os.path.join(KB, "_artifacts.csv"), encoding="utf-8") as f:
            pinned = kbgit.pinned_paths(f.read())
        out = self.repo.git("check-attr", "text", "--", *pinned)
        assert [ln for ln in out.splitlines() if not ln.endswith(": text: unset")] == [], "pinned artifacts must be -text"
        assert "_sources.csv: merge: union" in self.repo.git("check-attr", "merge", "--", "_sources.csv")

    def test_union_ledgers_have_no_markers(self):
        conflicted = set(self.repo.git("diff", "--name-only", "--diff-filter=U").split()) if self.merge.returncode else set()
        assert conflicted <= {"README.md"}, self.merge.stdout  # only the generated README table may conflict

    def test_fix_resolves_everything(self):
        assert self.fix.returncode == 0, self.fix.stdout + self.fix.stderr
        for rel in ("_sources.csv", "_fetch_state.csv", "_answers.md", "_gaps.md", "_coverage.csv", "README.md",
                    "windows/merge-test-a.md", "windows/merge-test-b.md"):
            assert not kbgit.has_markers(self.repo.read(rel)), rel

    def test_collision_renumbered_and_citations_rewritten(self):
        src = {r["id"]: r for r in rows(self.repo.read("_sources.csv"))}
        ha, hb = kbid.source_id(self.URL_A), kbid.source_id(self.URL_B)
        assert "S9999" not in src
        assert (src[ha]["url"], src[hb]["url"]) == (self.URL_A, self.URL_B)
        for n in ("a", "b"):
            assert kbid.source_id(f"https://learn.microsoft.com/en-us/merge-test/extra-{n}") in src
        a, b = self.repo.read("windows/merge-test-a.md"), self.repo.read("windows/merge-test-b.md")
        assert f"[DOC {ha}]" in a
        assert f"[DOC {hb}]" in b
        assert "S9999" not in a + b
        assert src[ha]["used_in"] == "windows/merge-test-a.md"
        ans = self.repo.read("_answers.md")
        assert "QK-merge-test-a" in ans
        assert "QK-merge-test-b" in ans
        assert "S9999" not in ans + self.repo.read("_gaps.md"), "root ledgers were changed on both sides: their citations too"
        ids = [r["id"] for r in rows(self.repo.read("_sources.csv"))]
        assert ids == sorted(ids, key=kbid.sort_key)

    def test_answers_keep_their_shared_footer(self):
        ans = self.repo.read("_answers.md")
        for n in ("a", "b"):
            sec = ans[ans.index(f"## QK-merge-test-{n}."):]
            sec = sec[:sec.find("\n## ", 1) if "\n## " in sec[1:] else len(sec)].rstrip()
            assert sec.endswith(self.FOOTER), f"answer of branch {n} lost its footer:\n{sec}"
        assert "restored 1 line(s) a merge moved out of" in self.fix.stdout

    def test_fetch_state_merged(self):
        st = [r for r in rows(self.repo.read("_fetch_state.csv")) if r["id"] == "S100"]
        assert len(st) == 1
        assert st[0]["checked_utc"] == "2026-09-27T00:00:00Z"

    def test_result_passes_checks_and_fix_is_idempotent(self):
        for tool, args in (("check.py", ()), ("build_index.py", ("--check",)), ("kbgit.py", ("fix", "--check")),
                           ("fetch.py", ("--offline",))):
            r = self.repo.tool(tool, *args)
            assert r.returncode == 0, f"{tool}: " + (r.stdout + r.stderr)[-2000:]
