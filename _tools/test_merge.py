"""Merge-rule tests: .gitattributes union merges plus `kbgit.py fix` give a clean kb (`python3 _tools/tests.py -k merge`).

  TestMergeRules           kg_merge.py functions on in-memory text (no git needed)
  TestMergeInGit           (marker git) a throwaway git repo (a copy of the kb without .git): two branches add sources, answers,
                           gaps and fetch state, both take the legacy id S9999 for different urls; merged with the
                           real .gitattributes, then `kbgit.py fix --base <merge-base>`. Skipped without git.
"""
import csv, io, os, re, shutil

import pytest

import kbid, kg_merge, kg_sync, kg_trailers
import kbcommon
from conftest import KB, SOURCES_HEADER as HEADER, P, Repo, copy_kb, requires_git
# the generated coverage table's page, a repository path: one per root, or the one page an older build_index keeps
COVERAGE_PAGE = P(kbcommon.COVERAGE_MD)


def team(rel):
    """A repository path in the scenario's second root `team` (kb/team/)."""
    return f"{kg_trailers.KB_DIR_REL}/team/{rel}"


def tid(url):
    """The team root's id of a url: its prefix T and the url's hash."""
    return "T-" + kbid.source_id(url)[2:]


def rows(text):
    return list(csv.DictReader(io.StringIO(text)))


class TestMergeRules:
    def test_strip_markers_is_union(self):
        t = "a\n<<<<<<< HEAD\nb\n||||||| base\nold\n=======\nc\n>>>>>>> other\nd\n"
        assert kg_merge.strip_markers(t, "x") == ("a\nb\nc\nd\n", 1)
        assert kg_merge.strip_markers("Title\n=======\n", "x") == ("Title\n=======\n", 0)  # a setext heading stays
        with pytest.raises(kg_merge.Problem):
            kg_merge.strip_markers("<<<<<<< HEAD\nb\n", "x")

    def test_sources_duplicates_and_field_merge(self):
        u = "https://learn.microsoft.com/en-us/a"
        old = f"S100,{u},Old title,Microsoft,,copy,2026-01-01,v1,,,\n"
        new = f"S100,{u}/,New title,Microsoft,CC BY 4.0,copy,2026-02-01,v2,,x.md,\n"
        report = []
        header, out, renames = kg_merge.resolve_sources(HEADER + old + HEADER + new + old + "S2,https://e.example.com/,t,p,l,copy,d,v,,,S100\n",
                                                     None, {}, report)
        assert [r["id"] for r in out] == ["S2", "S100"]
        r = out[1]
        assert (r["title"], r["licence"], r["retrieved_utc"], r["version_or_date"]) == ("New title", "CC BY 4.0", "2026-02-01", "v2")
        assert not renames
        assert any("title" in x and x.startswith("WARN") for x in report), report
        with pytest.raises(kg_merge.Problem):  # same date, two titles: a human decides
            kg_merge.resolve_sources(HEADER + old + old.replace("Old title", "Other"), None, {}, [])

    def test_sources_base_copy_yields_to_edit(self):
        u = "https://learn.microsoft.com/en-us/a"
        base = f"S100,{u},Title,Microsoft,,copy,2026-01-01,v1,,,\n"
        edit = base.replace("Title", "Better title")
        base_rows = {r["id"]: r for r in rows(HEADER + base)}
        _, out, _ = kg_merge.resolve_sources(HEADER + base + edit, base_rows, {}, [])
        assert [r["title"] for r in out] == ["Better title"]

    def test_collision_needs_base(self):
        t = HEADER + "S9999,https://a.example.com/x,a,p,l,copy,2026-01-01,v,,,\nS9999,https://b.example.com/y,b,p,l,copy,2026-01-01,v,,,\n"
        with pytest.raises(kg_merge.Problem) as e:
            kg_merge.resolve_sources(t, None, {}, [])
        assert "--base" in str(e.value)
        side = {"a": {"S9999": {"url": "https://a.example.com/x"}}, "b": {"S9999": {"url": "https://b.example.com/y"}}}
        _, out, renames = kg_merge.resolve_sources(t, {}, side, [])
        assert sorted(r["id"] for r in out) == sorted([kbid.source_id("https://a.example.com/x"), kbid.source_id("https://b.example.com/y")])
        assert sorted(o for _, _, owners in renames["S9999"] for o in owners) == ["a", "b"]

    def test_repeated_header_and_short_row(self):
        """A union merge repeats the header line (dropped); a row short by a column is an error, not padded."""
        u = "https://learn.microsoft.com/en-us/a"
        report = []
        _, out, _ = kg_merge.resolve_sources(HEADER + f"S100,{u},T,Microsoft,,copy,2026-01-01,v1,,x.md,\n" + HEADER, None, {}, report)
        assert [r["id"] for r in out] == ["S100"]
        assert any("repeated header" in x for x in report), report
        with pytest.raises(kg_merge.Problem):
            kg_merge.resolve_sources(HEADER + "S102,https://c.example.com/,t,p,l,copy,d,v,,\n".replace(",,\n", ",\n"), None, {}, [])

    def test_latest_row_wins_a_field_conflict(self):
        u = "https://github.com/o/r"
        current = f"S100,{u},T,P,Apache-2.0,copy,2026-09-25,v; confirmed 2026-09-25: x,,a.md,\n"
        newer = f"S100,{u},T,P,MIT,copy,2026-09-26,v2,,a.md,\n"
        for text in (HEADER + current + newer, HEADER + newer + current):
            report = []
            _, out, _ = kg_merge.resolve_sources(text, None, {}, report)
            assert (out[0]["licence"], out[0]["version_or_date"]) == ("MIT", "v2")
            assert any(x.startswith("WARN") and "licence" in x for x in report), report
        with pytest.raises(kg_merge.Problem):  # same date, different licence: a human decides
            kg_merge.resolve_sources(HEADER + current + current.replace("Apache-2.0", "MIT"), None, {}, [])

    def test_pushed_side_keeps_a_colliding_id(self):
        a, b = "https://a.example.com/x", "https://b.example.com/y"
        t = HEADER + f"S9999,{a},a,p,l,copy,2026-01-01,v,,,\nS9999,{b},b,p,l,copy,2026-01-01,v,,,\n"
        side = {"up": {"S9999": {"url": a}}, "mine": {"S9999": {"url": b}}}
        _, out, renames = kg_merge.resolve_sources(t, {}, side, [], upstream="up")
        assert {r["id"]: r["url"] for r in out} == {"S9999": a, kbid.source_id(b): b}
        assert renames == {"S9999": [(b, kbid.source_id(b), ["mine"])]}
        assert kg_merge.source_plan(renames, out)["S9999"]["strict_base"] == False  # S9999 still names a's url

    def test_colliding_answer_ids_are_renamed(self):
        up = "# A\n\n## QK-shared. What does clone a ask?\n\nA. [DOC S1]\n"
        mine = "# A\n\n## QK-shared. What does clone b ask about sync?\n\nB.\n"
        merged = up + "\n## QK-shared. What does clone b ask about sync?\n\nB.\n"
        report, problems = [], []
        plan = kg_merge.answer_plan(merged, "# A\n", up, {"up": up, "mine": mine}, report, problems)
        assert problems == []
        assert plan["QK-shared"]["by_side"] == {"mine": kbid.answer_id("What does clone b ask about sync?")}
        assert kg_sync.renumbered("\n".join("  " + x for x in report)) == report
        # no base, no pushed side: the first heading keeps the id; a unique id is never touched
        plan = kg_merge.answer_plan(merged, None, None, {"up": up, "mine": mine}, [], [])
        assert list(plan) == ["QK-shared"]
        assert kg_merge.answer_plan(up, None, None, {}, [], []) == {}
        assert kg_merge.answer_plan("## QK7. q\n", "## QK7. q\n", None, {}, [], []) == {}  # check.py's business

    def test_answer_mentions_follow_only_the_owning_side(self):
        """A renamed colliding id is rewritten on the owner's lines; the pushed side's own mention and docs stay."""
        assert not {"README.md", "AGENTS.md", "CLAUDE.md"} & set(kg_merge.id_files())
        up = {P("x/a.md"): "# A\n- The other kb calls it QK-dup.\n", P("_answers.md"): "# A\n\n## QK-dup. Pushed question\n"}
        mine = {P("x/a.md"): "# A\n- Answer: `_answers.md` QK-dup.\n", P("_answers.md"): "# A\n\n## QK-dup. Local question\n"}
        merged = {P("x/a.md"): "# A\n- The other kb calls it QK-dup.\n- Answer: `_answers.md` QK-dup.\n",
                  P("_answers.md"): "# A\n\n## QK-dup. Pushed question\n\n## QK-dup. Local question\n"}
        revs = {"base": {P("x/a.md"): "# A\n", P("_answers.md"): "# A\n"}, "up": up, "mine": mine}
        saved = kg_merge.id_files, kg_merge.read, kg_merge.show
        try:
            kg_merge.id_files, kg_merge.read = (lambda: sorted(merged)), merged.get
            kg_merge.show = lambda rev, f: revs[rev].get(f)
            ans = P("_answers.md")
            plan = kg_merge.answer_plan(merged[ans], revs["base"][ans], up[ans], {"up": up[ans], "mine": mine[ans]}, [], [])
            texts, problems = {}, []
            kg_merge.rewrite_ids(plan, "base", {"up": "up", "mine": "mine"}, texts, set(), problems, [])
        finally:
            kg_merge.id_files, kg_merge.read, kg_merge.show = saved
        new = kbid.answer_id("Local question")
        assert problems == []
        assert texts[P("x/a.md")] == f"# A\n- The other kb calls it QK-dup.\n- Answer: `_answers.md` {new}.\n"
        assert texts[P("_answers.md")] == f"# A\n\n## QK-dup. Pushed question\n\n## {new}. Local question\n"

    def test_fetch_state_one_row_per_id(self):
        h = "id,url,checked_utc,fetched_utc,changed_utc,sha256,text_sha256,bytes,error\n"
        a = "S100,https://x.example.com/,2026-03-01T00:00:00Z,2026-02-01T00:00:00Z,2026-01-01T00:00:00Z,old,old,1,timeout\n"
        b = "S100,https://x.example.com/,2026-02-15T00:00:00Z,2026-02-15T00:00:00Z,2026-02-15T00:00:00Z,new,new,2,\n"
        c = "S-aaaaaaaa,https://y.example.com/,2026-01-01T00:00:00Z,,,,,,\n"
        out = rows(kg_merge.resolve_state(h + c + a + h + b, {}, []))
        assert [r["id"] for r in out] == ["S100", "S-aaaaaaaa"]
        r = out[0]
        assert (r["checked_utc"], r["error"]) == ("2026-03-01T00:00:00Z", "timeout")  # latest check
        assert (r["fetched_utc"], r["sha256"], r["bytes"]) == ("2026-02-15T00:00:00Z", "new", "2")  # latest fetch
        assert r["changed_utc"] == "2026-02-15T00:00:00Z"

    def test_markdown_dedupe(self):
        item = "- **A gap that both branches recorded.** Tried S100 and S101. [UNK]"
        text = (f"# Gaps\n\n## auth\n\n{item}\n- none\n- none\n{item}\n\n| a | b |\n|---|---|\n| 1 | 2 |\n| 1 | 2 |\n\n"
                f"| c |\n|---|\n```\n## not a heading\n## not a heading\n```\n\n## dsc\n\n- x\n\n## dsc\n\n- x\n")
        out = kg_merge.resolve_md(text, "_gaps.md", [], [])
        assert out.count(item) == 1
        assert out.count("- none") == 2  # short items may repeat on purpose
        assert out.count("| 1 | 2 |") == 1
        assert out.count("|---|") == 2  # separators of two tables stay
        assert out.count("## dsc") == 1
        assert out.count("## not a heading") == 2  # code blocks are never deduplicated
        assert kg_merge.resolve_md(out, "_gaps.md", [], []) == out  # idempotent

    def test_zealous_splice_is_repaired(self):
        """git keeps a footer both added blocks end with only once: the first answer loses it to the second."""
        a = "# A\n\n## QK-a. qa\n- a1 [DOC S1]\n\n_Agent: kb-research_\n\n## R1. r\n"
        b = "# A\n\n## QK-a. qb\n- b1 [DOC S2205]\n\n_Agent: kb-research_\n\n## R1. r\n"
        spliced = "# A\n\n## QK-a. qa\n- a1 [DOC S1]\n## QK-b. qb\n- b1 [DOC S-aaaaaaaa]\n\n_Agent: kb-research_\n\n## R1. r\n"
        whole = "# A\n\n## QK-a. qa\n- a1 [DOC S1]\n\n_Agent: kb-research_\n\n## QK-b. qb\n- b1 [DOC S-aaaaaaaa]\n\n_Agent: kb-research_\n\n## R1. r\n"
        report = []
        assert kg_merge.resolve_md(spliced, kg_merge.ANSWERS, report, [], [a, b]) == whole  # ids renamed since: ignored
        assert any("restored 1 line(s)" in r for r in report), report
        assert kg_merge.resolve_md(whole, kg_merge.ANSWERS, [], [], [a, b]) == whole  # idempotent
        assert kg_merge.resolve_md(spliced, kg_merge.ANSWERS, [], []) == spliced  # sides unknown: left alone
        cut = spliced.replace("\n\n_Agent: kb-research_\n\n## R1", "\n\n## R1")  # the tail is not where the merge puts it
        assert kg_merge.resolve_md(cut, kg_merge.ANSWERS, [], [], [a, b]) == cut

    def test_answer_id_clash_is_a_problem(self):
        problems = []
        kg_merge.resolve_md("# A\n\n## QK-x. q\n\none\n\n## QK-x. q\n\ntwo\n", kg_merge.ANSWERS, [], problems)
        assert problems and "QK-x" in problems[0]
        problems = []
        out = kg_merge.resolve_md("# A\n\n## QK-x. q\n\none\n\n## QK-x. q\n\none\n", kg_merge.ANSWERS, [], problems)
        assert (problems, out.count("## QK-x.")) == ([], 1)

    def test_gitattributes_pins_every_artifact(self):
        with open(os.path.join(KB, ".gitattributes"), encoding="utf-8") as f:
            attrs = f.read()
        with open(os.path.join(KB, P("_artifacts.csv")), encoding="utf-8") as f:
            pinned = kg_merge.pinned_paths(f.read())
        assert kg_merge.resolve_attrs(attrs, pinned) == attrs, ".gitattributes pinned block is stale; run python3 _tools/kbgit.py fix"
        for name in ("_sources.csv", "_fetch_state.csv", "_answers.md", "_gaps.md", "_conflicts.md"):
            assert re.search(rf"(?m)^{re.escape(name)} merge=union$", attrs)
        assert not re.search(r"(?m)^README\.md .*merge=", attrs)


@requires_git
@pytest.mark.git
class TestMergeInGit:
    URL_A, URL_B = "https://learn.microsoft.com/en-us/merge-test/branch-a", "https://learn.microsoft.com/en-us/merge-test/branch-b"
    STATE_H = "id,url,checked_utc,fetched_utc,changed_utc,sha256,text_sha256,bytes,error\n"
    FOOTER = "_Agent: merge-test_"
    T_BOTH = "https://t.example.com/both"

    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def scenario(cls, tmp_path_factory):
        cls.tmp = tmp_path_factory.mktemp("kb-merge")
        cls.repo = Repo(copy_kb(cls.tmp / "kb", skip=("_fetch_state.csv",)))
        cls.repo.write(P("_fetch_state.csv"), cls.STATE_H + "S100,https://x.example.com/,2026-01-01T00:00:00Z,2026-01-01T00:00:00Z,"
                  "2026-01-01T00:00:00Z,s0,t0,1,\nS101,https://y.example.com/,2026-01-01T00:00:00Z,,,,,,\n")
        # a second root beside public: its own ledgers, id prefix T
        cls.repo.write(team("_root.md"), "---\nroot: team\nid_prefix: T\nvisibility: internal\ndescription: merge test\n---\n")
        cls.repo.write(team("_sources.csv"), HEADER + f"{tid('https://t.example.com/base')},https://t.example.com/base,Base,T,-,copy,2026-01-01,v,,,\n")
        for f in ("_answers.md", "_gaps.md", "_conflicts.md"):
            cls.repo.write(team(f), f"# {f[1:-3].title()}\n")
        cls.repo.write(team("_artifacts.csv"), "path,source_id,sha256,zip_member\n")
        cls.repo.tool("build_index.py")  # the team root's _coverage.csv and _coverage.md, as kbroot.py add leaves them
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
        cls.repo.write(P("_sources.csv"), f"S9999,{url},Merge test {name},Microsoft,MIT,copy,2026-09-25,v,,,\n"
                                  f"{hid},{extra},Extra {name},Microsoft,MIT,copy,2026-09-25,v,,,\n", "a")
        cls.repo.write(P(f"windows/merge-test-{name}.md"),
                  f"---\ntopic: windows/merge-test-{name}\npriority: P3\napplies_to: [test]\nretrieved_utc: 2026-09-25\n"
                  f"sources: [S9999, {hid}]\nstatus: partial\n---\n# Merge test {name}\n\n## Summary\n\nTest.\n\n## Facts\n\n"
                  f"- Branch {name} says this. [DOC S9999]\n- And this. [DOC {hid}]\n\n## Reference\n\n## Examples\n")
        cls.repo.write(P("_answers.md"), f"\n## QK-merge-test-{name}. Does branch {name} merge?\n\nYes, says branch {name} [DOC S9999].\n"
                                 f"\n{cls.FOOTER}\n", "a")  # the same last line on both branches: a plain merge splices
        cls.repo.write(P("_gaps.md"), f"\n- **Merge test gap from branch {name}.** Tried nothing, cites S9999. [UNK]\n", "a")
        turl = f"https://t.example.com/{name}"  # the second root: its own source, plus one row both branches add
        cls.repo.write(team("_sources.csv"), f"{tid(turl)},{turl},Team {name},T,-,copy,2026-09-25,v,,,\n"
                                             f"{tid(cls.T_BOTH)},{cls.T_BOTH},Both,T,-,copy,2026-09-25,v,,,\n", "a")
        if name == "a":
            cls.repo.write(team("mdm/enrol.md"),
                           f"---\ntopic: mdm/enrol\npriority: P3\napplies_to: [test]\nretrieved_utc: 2026-09-25\n"
                           f"sources: [{tid(turl)}]\nstatus: partial\n---\n# Enrol\n\n## Summary\n\nTest.\n\n## Facts\n\n"
                           f"- Team fact. [DOC {tid(turl)}]\n\n## Reference\n\n## Examples\n")
        state = cls.repo.read(P("_fetch_state.csv")).replace(
            "S100,https://x.example.com/,2026-01-01T00:00:00Z,2026-01-01T00:00:00Z,",
            f"S100,https://x.example.com/,{checked},{checked},")
        cls.repo.write(P("_fetch_state.csv"), state)
        r = cls.repo.tool("build_index.py")
        assert r.returncode == 0, r.stdout + r.stderr
        cls.repo.git("add", "-A")
        cls.repo.git("commit", "-q", "-m", f"branch {name}")

    def test_attributes_keep_a_fresh_checkout_clean(self):
        assert self.dirty_after_init == "", "the committed tree is not stable under .gitattributes"
        with open(os.path.join(KB, P("_artifacts.csv")), encoding="utf-8") as f:
            pinned = kg_merge.pinned_paths(f.read())
        out = self.repo.git("check-attr", "text", "--", *pinned)
        assert [ln for ln in out.splitlines() if not ln.endswith(": text: unset")] == [], "pinned artifacts must be -text"
        assert f"{P('_sources.csv')}: merge: union" in self.repo.git("check-attr", "merge", "--", P("_sources.csv"))

    def test_union_ledgers_have_no_markers(self):
        conflicted = set(self.repo.git("diff", "--name-only", "--diff-filter=U").split()) if self.merge.returncode else set()
        # only the generated coverage tables may conflict
        assert conflicted <= {COVERAGE_PAGE, team(kbcommon.COVERAGE_MD)}, self.merge.stdout

    def test_fix_resolves_everything(self):
        assert self.fix.returncode == 0, self.fix.stdout + self.fix.stderr
        for rel in [P(f) for f in ("_sources.csv", "_fetch_state.csv", "_answers.md", "_gaps.md", "_coverage.csv",
                                   "windows/merge-test-a.md", "windows/merge-test-b.md")] + [COVERAGE_PAGE]:
            assert not kg_merge.has_markers(self.repo.read(rel)), rel

    def test_collision_renumbered_and_citations_rewritten(self):
        src = {r["id"]: r for r in rows(self.repo.read(P("_sources.csv")))}
        ha, hb = kbid.source_id(self.URL_A), kbid.source_id(self.URL_B)
        assert "S9999" not in src
        assert (src[ha]["url"], src[hb]["url"]) == (self.URL_A, self.URL_B)
        for n in ("a", "b"):
            assert kbid.source_id(f"https://learn.microsoft.com/en-us/merge-test/extra-{n}") in src
        a, b = self.repo.read(P("windows/merge-test-a.md")), self.repo.read(P("windows/merge-test-b.md"))
        assert f"[DOC {ha}]" in a
        assert f"[DOC {hb}]" in b
        assert "S9999" not in a + b
        assert src[ha]["used_in"] == "windows/merge-test-a.md"
        ans = self.repo.read(P("_answers.md"))
        assert "QK-merge-test-a" in ans
        assert "QK-merge-test-b" in ans
        assert "S9999" not in ans + self.repo.read(P("_gaps.md")), "root ledgers were changed on both sides: their citations too"
        ids = [r["id"] for r in rows(self.repo.read(P("_sources.csv")))]
        assert ids == sorted(ids, key=kbid.sort_key)

    def test_second_root_ledgers_fixed(self):
        """The team root's union-merged _sources.csv: both branches' rows kept, the row both added once, sorted."""
        text = self.repo.read(team("_sources.csv"))
        assert not kg_merge.has_markers(text)
        ids = [r["id"] for r in rows(text)]
        want = {tid(u) for u in ("https://t.example.com/base", "https://t.example.com/a", "https://t.example.com/b", self.T_BOTH)}
        assert set(ids) == want and len(ids) == len(want), ids
        assert ids == sorted(ids, key=kg_merge.id_key)
        assert f"wrote {team('_sources.csv')}" in self.fix.stdout, self.fix.stdout  # fix, not the union, deduped it

    def test_second_root_topic_is_qualified(self):
        r = self.repo.kbgit("trailers", "a")
        assert r.returncode == 0, r.stdout + r.stderr
        assert "team/mdm/enrol" in r.stdout, r.stdout
        assert tid("https://t.example.com/a") in r.stdout, r.stdout

    def test_answers_keep_their_shared_footer(self):
        ans = self.repo.read(P("_answers.md"))
        for n in ("a", "b"):
            sec = ans[ans.index(f"## QK-merge-test-{n}."):]
            sec = sec[:sec.find("\n## ", 1) if "\n## " in sec[1:] else len(sec)].rstrip()
            assert sec.endswith(self.FOOTER), f"answer of branch {n} lost its footer:\n{sec}"
        assert "restored 1 line(s) a merge moved out of" in self.fix.stdout

    def test_fetch_state_merged(self):
        st = [r for r in rows(self.repo.read(P("_fetch_state.csv"))) if r["id"] == "S100"]
        assert len(st) == 1
        assert st[0]["checked_utc"] == "2026-09-27T00:00:00Z"

    def test_result_passes_checks_and_fix_is_idempotent(self):
        for tool, args in (("check.py", ()), ("build_index.py", ("--check",)), ("kbgit.py", ("fix", "--check")),
                           ("fetch.py", ("--offline",))):
            r = self.repo.tool(tool, *args)
            assert r.returncode == 0, f"{tool}: " + (r.stdout + r.stderr)[-2000:]
