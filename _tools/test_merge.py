#!/usr/bin/env python3
"""Merge-rule tests (stdlib only): .gitattributes union merges plus `kbgit.py fix` give a clean kb. tests.py runs them.

  test_merge.py            run them on their own
  MergeRules               kbgit.py functions on in-memory text (no git needed; CI runs these)
  MergeInGit               a throwaway git repo (a copy of the kb without .git): two branches add sources, answers,
                           gaps and fetch state, both take the legacy id S9999 for different urls; merged with the
                           real .gitattributes, then `kbgit.py fix --base <merge-base>`. Skipped when git is missing
                           (the CI image has none).
"""
import csv, io, os, re, shutil, subprocess, sys, tempfile, unittest

TOOLS = os.path.dirname(os.path.abspath(__file__))
KB = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import kbgit, kbid  # noqa: E402

HEADER = "id,url,title,publisher,licence,retrieved_utc,version_or_date,artifact_sha256,used_in,superseded_by\n"


def rows(text):
    return list(csv.DictReader(io.StringIO(text)))


class MergeRules(unittest.TestCase):
    def test_strip_markers_is_union(self):
        t = "a\n<<<<<<< HEAD\nb\n||||||| base\nold\n=======\nc\n>>>>>>> other\nd\n"
        self.assertEqual(kbgit.strip_markers(t, "x"), ("a\nb\nc\nd\n", 1))
        self.assertEqual(kbgit.strip_markers("Title\n=======\n", "x"), ("Title\n=======\n", 0))  # a setext heading stays
        with self.assertRaises(kbgit.Problem):
            kbgit.strip_markers("<<<<<<< HEAD\nb\n", "x")

    def test_sources_duplicates_and_field_merge(self):
        u = "https://learn.microsoft.com/en-us/a"
        old = f"S100,{u},Old title,Microsoft,,2026-01-01,v1,,,\n"
        new = f"S100,{u}/,New title,Microsoft,CC BY 4.0,2026-02-01,v2,,x.md,\n"
        report = []
        header, out, renames = kbgit.resolve_sources(HEADER + old + HEADER + new + old + "S2,https://e.example.com/,t,p,l,d,v,,,S100\n",
                                                     None, {}, report)
        self.assertEqual([r["id"] for r in out], ["S2", "S100"])
        r = out[1]
        self.assertEqual((r["title"], r["licence"], r["retrieved_utc"], r["version_or_date"]), ("New title", "CC BY 4.0", "2026-02-01", "v2"))
        self.assertFalse(renames)
        self.assertTrue(any("title" in x and x.startswith("WARN") for x in report), report)
        with self.assertRaises(kbgit.Problem):  # same date, two titles: a human decides
            kbgit.resolve_sources(HEADER + old + old.replace("Old title", "Other"), None, {}, [])

    def test_sources_base_copy_yields_to_edit(self):
        u = "https://learn.microsoft.com/en-us/a"
        base = f"S100,{u},Title,Microsoft,,2026-01-01,v1,,,\n"
        edit = base.replace("Title", "Better title")
        base_rows = {r["id"]: r for r in rows(HEADER + base)}
        _, out, _ = kbgit.resolve_sources(HEADER + base + edit, base_rows, {}, [])
        self.assertEqual([r["title"] for r in out], ["Better title"])

    def test_collision_needs_base(self):
        t = HEADER + "S9999,https://a.example.com/x,a,p,l,2026-01-01,v,,,\nS9999,https://b.example.com/y,b,p,l,2026-01-01,v,,,\n"
        with self.assertRaises(kbgit.Problem) as e:
            kbgit.resolve_sources(t, None, {}, [])
        self.assertIn("--base", str(e.exception))
        side = {"a": {"S9999": {"url": "https://a.example.com/x"}}, "b": {"S9999": {"url": "https://b.example.com/y"}}}
        _, out, renames = kbgit.resolve_sources(t, {}, side, [])
        self.assertEqual(sorted(r["id"] for r in out), sorted([kbid.source_id("https://a.example.com/x"), kbid.source_id("https://b.example.com/y")]))
        self.assertEqual(sorted(o for _, _, owners in renames["S9999"] for o in owners), ["a", "b"])

    def test_older_layout_is_padded(self):
        """A branch from before superseded_by existed, union-merged: two headers, 9- and 10-field rows (CRLF too)."""
        old_h = HEADER.replace(",superseded_by", "")
        u = "https://learn.microsoft.com/en-us/a"
        new_row, old_row = f"S100,{u},T,Microsoft,,2026-01-01,v1,,x.md,\n", f"S100,{u},T,Microsoft,,2026-01-01,v1,,x.md\r\n"
        extra = "S101,https://b.example.com/,t,p,l,2026-01-02,v,,,\r\n".replace(",,,\r", ",,\r")
        for text in (HEADER + new_row + old_h.replace("\n", "\r\n") + old_row + extra, old_h + old_row + extra + HEADER + new_row):
            report = []
            header, out, _ = kbgit.resolve_sources(text, None, {}, report)
            self.assertEqual(header[-1], "superseded_by")
            self.assertEqual([(r["id"], r["superseded_by"]) for r in out], [("S100", ""), ("S101", "")])
            self.assertTrue(any("older layout" in x for x in report), report)
        with self.assertRaises(kbgit.Problem):  # a row short by a column that is not a later one stays an error
            kbgit.resolve_sources(HEADER + "S102,https://c.example.com/,t,p,l,d,v,,\n".replace(",,\n", ",\n"), None, {}, [])

    def test_pushed_side_keeps_a_colliding_id(self):
        a, b = "https://a.example.com/x", "https://b.example.com/y"
        t = HEADER + f"S9999,{a},a,p,l,2026-01-01,v,,,\nS9999,{b},b,p,l,2026-01-01,v,,,\n"
        side = {"up": {"S9999": {"url": a}}, "mine": {"S9999": {"url": b}}}
        _, out, renames = kbgit.resolve_sources(t, {}, side, [], upstream="up")
        self.assertEqual({r["id"]: r["url"] for r in out}, {"S9999": a, kbid.source_id(b): b})
        self.assertEqual(renames, {"S9999": [(b, kbid.source_id(b), ["mine"])]})
        self.assertEqual(kbgit.source_plan(renames, out)["S9999"]["strict_base"], False)  # S9999 still names a's url

    def test_answer_ids_invalid_or_colliding_are_renamed(self):
        up = "# A\n\n## QK-shared. What does clone a ask?\n\nA. [DOC S1]\n"
        mine = "# A\n\n## QK-shared. What does clone b ask about sync?\n\nB.\n\n## QK1. Old style question from clone b\n\nC.\n"
        merged = up + "\n## QK-shared. What does clone b ask about sync?\n\nB.\n\n## QK1. Old style question from clone b\n\nC.\n"
        report, problems = [], []
        plan = kbgit.answer_plan(merged, "# A\n", up, {"up": up, "mine": mine}, report, problems)
        self.assertEqual(problems, [])
        self.assertEqual(plan["QK1"]["default"], kbid.answer_id("Old style question from clone b"))
        self.assertEqual(plan["QK-shared"]["by_side"], {"mine": kbid.answer_id("What does clone b ask about sync?")})
        self.assertEqual(kbgit.renumbered("\n".join("  " + x for x in report)), report)
        # no base, no pushed side: the first heading keeps the id; a valid, unique id is never touched
        plan = kbgit.answer_plan(merged.replace("## QK1.", "## QK-old."), None, None, {"up": up, "mine": mine}, [], [])
        self.assertEqual(list(plan), ["QK-shared"])
        self.assertEqual(kbgit.answer_plan(up, None, None, {}, [], []), {})
        # an invalid id already published is left alone
        report = []
        self.assertEqual(kbgit.answer_plan("## QK7. q\n", "## QK7. q\n", None, {}, report, []), {})
        self.assertTrue(report and report[0].startswith("WARN"))

    def test_fetch_state_one_row_per_id(self):
        h = "id,url,checked_utc,fetched_utc,changed_utc,sha256,text_sha256,bytes,error\n"
        a = "S100,https://x.example.com/,2026-03-01T00:00:00Z,2026-02-01T00:00:00Z,2026-01-01T00:00:00Z,old,old,1,timeout\n"
        b = "S100,https://x.example.com/,2026-02-15T00:00:00Z,2026-02-15T00:00:00Z,2026-02-15T00:00:00Z,new,new,2,\n"
        c = "S-aaaaaaaa,https://y.example.com/,2026-01-01T00:00:00Z,,,,,,\n"
        out = rows(kbgit.resolve_state(h + c + a + h + b, {}, []))
        self.assertEqual([r["id"] for r in out], ["S100", "S-aaaaaaaa"])
        r = out[0]
        self.assertEqual((r["checked_utc"], r["error"]), ("2026-03-01T00:00:00Z", "timeout"))  # latest check
        self.assertEqual((r["fetched_utc"], r["sha256"], r["bytes"]), ("2026-02-15T00:00:00Z", "new", "2"))  # latest fetch
        self.assertEqual(r["changed_utc"], "2026-02-15T00:00:00Z")

    def test_markdown_dedupe(self):
        item = "- **A gap that both branches recorded.** Tried S100 and S101. [UNK]"
        text = (f"# Gaps\n\n## auth\n\n{item}\n- none\n- none\n{item}\n\n| a | b |\n|---|---|\n| 1 | 2 |\n| 1 | 2 |\n\n"
                f"| c |\n|---|\n```\n## not a heading\n## not a heading\n```\n\n## dsc\n\n- x\n\n## dsc\n\n- x\n")
        out = kbgit.resolve_md(text, "_gaps.md", [], [])
        self.assertEqual(out.count(item), 1)
        self.assertEqual(out.count("- none"), 2)  # short items may repeat on purpose
        self.assertEqual(out.count("| 1 | 2 |"), 1)
        self.assertEqual(out.count("|---|"), 2)  # separators of two tables stay
        self.assertEqual(out.count("## dsc"), 1)
        self.assertEqual(out.count("## not a heading"), 2)  # code blocks are never deduplicated
        self.assertEqual(kbgit.resolve_md(out, "_gaps.md", [], []), out)  # idempotent

    def test_answer_id_clash_is_a_problem(self):
        problems = []
        kbgit.resolve_md("# A\n\n## QK-x. q\n\none\n\n## QK-x. q\n\ntwo\n", "_answers.md", [], problems)
        self.assertTrue(problems and "QK-x" in problems[0])
        problems = []
        out = kbgit.resolve_md("# A\n\n## QK-x. q\n\none\n\n## QK-x. q\n\none\n", "_answers.md", [], problems)
        self.assertEqual((problems, out.count("## QK-x.")), ([], 1))

    def test_gitattributes_pins_every_artifact(self):
        with open(os.path.join(KB, ".gitattributes"), encoding="utf-8") as f:
            attrs = f.read()
        with open(os.path.join(KB, "_artifacts.csv"), encoding="utf-8") as f:
            pinned = kbgit.pinned_paths(f.read())
        self.assertEqual(kbgit.resolve_attrs(attrs, pinned), attrs, ".gitattributes pinned block is stale; run python3 _tools/kbgit.py fix")
        for name in ("_sources.csv", "_fetch_state.csv", "_answers.md", "_gaps.md", "_conflicts.md"):
            self.assertRegex(attrs, rf"(?m)^{re.escape(name)} merge=union$")
        self.assertNotRegex(attrs, r"(?m)^README\.md .*merge=")


GIT = shutil.which("git")


@unittest.skipUnless(GIT, "git is not installed")
class MergeInGit(unittest.TestCase):
    URL_A, URL_B = "https://learn.microsoft.com/en-us/merge-test/branch-a", "https://learn.microsoft.com/en-us/merge-test/branch-b"
    STATE_H = "id,url,checked_utc,fetched_utc,changed_utc,sha256,text_sha256,bytes,error\n"

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="kb-merge-")
        cls.kb = os.path.join(cls.tmp, "kb")
        shutil.copytree(KB, cls.kb, ignore=shutil.ignore_patterns(".git", "_cache", "_private", "__pycache__", "_fetch_state.csv"))
        cls.env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t",
                   "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
        cls.write("_fetch_state.csv", cls.STATE_H + "S100,https://x.example.com/,2026-01-01T00:00:00Z,2026-01-01T00:00:00Z,"
                  "2026-01-01T00:00:00Z,s0,t0,1,\nS101,https://y.example.com/,2026-01-01T00:00:00Z,,,,,,\n")
        cls.git("init", "-q", "-b", "main")
        cls.git("add", "-A")
        cls.git("commit", "-q", "-m", "base")
        cls.base = cls.git("rev-parse", "HEAD").strip()
        cls.dirty_after_init = cls.git("status", "--porcelain")
        cls.branch("a", cls.URL_A, "2026-09-26T00:00:00Z")
        cls.git("checkout", "-q", "main")
        cls.branch("b", cls.URL_B, "2026-09-27T00:00:00Z")
        cls.git("checkout", "-q", "a")
        cls.merge = subprocess.run(["git", "merge", "--no-edit", "b"], cwd=cls.kb, env=cls.env, capture_output=True, text=True)
        cls.fix = cls.tool("kbgit.py", "fix", "--base", cls.base)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def git(cls, *args):
        return subprocess.run(["git", *args], cwd=cls.kb, env=cls.env, capture_output=True, text=True, check=True).stdout

    @classmethod
    def tool(cls, name, *args):
        return subprocess.run([sys.executable, os.path.join(cls.kb, "_tools", name), *args], cwd=cls.kb, env=cls.env,
                              capture_output=True, text=True, errors="replace")

    @classmethod
    def read(cls, rel):
        with open(os.path.join(cls.kb, rel), encoding="utf-8") as f:
            return f.read()

    @classmethod
    def write(cls, rel, text, mode="w"):
        with open(os.path.join(cls.kb, rel), mode, encoding="utf-8", newline="") as f:
            f.write(text)

    @classmethod
    def branch(cls, name, url, checked):
        """A branch that adds the same legacy id S9999 (for its own url), a hash-id source, an article citing both,
        an answer, a gap and a fetch of S100, then rebuilds the index as a writer would."""
        cls.git("checkout", "-q", "-b", name)
        extra = f"https://learn.microsoft.com/en-us/merge-test/extra-{name}"
        hid = kbid.source_id(extra)
        cls.write("_sources.csv", f"S9999,{url},Merge test {name},Microsoft,MIT,2026-09-25,v,,,\n"
                                  f"{hid},{extra},Extra {name},Microsoft,MIT,2026-09-25,v,,,\n", "a")
        cls.write(f"windows/merge-test-{name}.md",
                  f"---\ntopic: windows/merge-test-{name}\npriority: P3\napplies_to: [test]\nretrieved_utc: 2026-09-25\n"
                  f"sources: [S9999, {hid}]\nstatus: partial\n---\n# Merge test {name}\n\n## Summary\n\nTest.\n\n## Facts\n\n"
                  f"- Branch {name} says this. [DOC S9999]\n- And this. [DOC {hid}]\n\n## Reference\n\n## Examples\n")
        cls.write("_answers.md", f"\n## QK-merge-test-{name}. Does branch {name} merge?\n\nYes, says branch {name} [DOC S9999].\n", "a")
        cls.write("_gaps.md", f"\n- **Merge test gap from branch {name}.** Tried nothing, cites S9999. [UNK]\n", "a")
        state = cls.read("_fetch_state.csv").replace(
            "S100,https://x.example.com/,2026-01-01T00:00:00Z,2026-01-01T00:00:00Z,",
            f"S100,https://x.example.com/,{checked},{checked},")
        cls.write("_fetch_state.csv", state)
        r = cls.tool("build_index.py")
        assert r.returncode == 0, r.stdout + r.stderr
        cls.git("add", "-A")
        cls.git("commit", "-q", "-m", f"branch {name}")

    def test_attributes_keep_a_fresh_checkout_clean(self):
        self.assertEqual(self.dirty_after_init, "", "the committed tree is not stable under .gitattributes")
        with open(os.path.join(KB, "_artifacts.csv"), encoding="utf-8") as f:
            pinned = kbgit.pinned_paths(f.read())
        out = self.git("check-attr", "text", "--", *pinned)
        self.assertEqual([ln for ln in out.splitlines() if not ln.endswith(": text: unset")], [], "pinned artifacts must be -text")
        self.assertIn("_sources.csv: merge: union", self.git("check-attr", "merge", "--", "_sources.csv"))

    def test_union_ledgers_have_no_markers(self):
        conflicted = set(self.git("diff", "--name-only", "--diff-filter=U").split()) if self.merge.returncode else set()
        self.assertLessEqual(conflicted, {"README.md"}, self.merge.stdout)  # only the generated README table may conflict

    def test_fix_resolves_everything(self):
        self.assertEqual(self.fix.returncode, 0, self.fix.stdout + self.fix.stderr)
        for rel in ("_sources.csv", "_fetch_state.csv", "_answers.md", "_gaps.md", "_coverage.csv", "README.md",
                    "windows/merge-test-a.md", "windows/merge-test-b.md"):
            self.assertFalse(kbgit.has_markers(self.read(rel)), rel)

    def test_collision_renumbered_and_citations_rewritten(self):
        src = {r["id"]: r for r in rows(self.read("_sources.csv"))}
        ha, hb = kbid.source_id(self.URL_A), kbid.source_id(self.URL_B)
        self.assertNotIn("S9999", src)
        self.assertEqual((src[ha]["url"], src[hb]["url"]), (self.URL_A, self.URL_B))
        for n in ("a", "b"):
            self.assertIn(kbid.source_id(f"https://learn.microsoft.com/en-us/merge-test/extra-{n}"), src)
        a, b = self.read("windows/merge-test-a.md"), self.read("windows/merge-test-b.md")
        self.assertIn(f"[DOC {ha}]", a)
        self.assertIn(f"[DOC {hb}]", b)
        self.assertNotIn("S9999", a + b)
        self.assertEqual(src[ha]["used_in"], "windows/merge-test-a.md")
        ans = self.read("_answers.md")
        self.assertIn("QK-merge-test-a", ans)
        self.assertIn("QK-merge-test-b", ans)
        self.assertNotIn("S9999", ans + self.read("_gaps.md"), "root ledgers were changed on both sides: their citations too")
        ids = [r["id"] for r in rows(self.read("_sources.csv"))]
        self.assertEqual(ids, sorted(ids, key=kbid.sort_key))

    def test_fetch_state_merged(self):
        st = [r for r in rows(self.read("_fetch_state.csv")) if r["id"] == "S100"]
        self.assertEqual(len(st), 1)
        self.assertEqual(st[0]["checked_utc"], "2026-09-27T00:00:00Z")

    def test_result_passes_checks_and_fix_is_idempotent(self):
        for tool, args in (("check.py", ()), ("build_index.py", ("--check",)), ("kbgit.py", ("fix", "--check")),
                           ("fetch.py", ("--offline",))):
            r = self.tool(tool, *args)
            self.assertEqual(r.returncode, 0, f"{tool}: " + (r.stdout + r.stderr)[-2000:])


if __name__ == "__main__":
    unittest.main(verbosity=2)
