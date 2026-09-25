#!/usr/bin/env python3
"""History tests (stdlib only): KB-* commit trailers, the commit-msg hook and the lookup commands. tests.py runs them.

  test_history.py          run them on their own
  TrailerRules             trailer computation and formatting on in-memory text (no git needed; CI runs these)
  HistoryInGit             a throwaway repo holding a tiny kb and a copy of _tools/ and .githooks/: install-hooks, then
                           commits with -m, the editor, --amend, KB_VERIFIED, a non-kb change and a --no-verify commit;
                           check-trailers, log, blame, asof, tag-census and `trailers --amend`. Skipped without git.
"""
import os, re, shutil, subprocess, sys, tempfile, unittest

TOOLS = os.path.dirname(os.path.abspath(__file__))
KB = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import kbgit, kbid  # noqa: E402

HEADER = "id,url,title,publisher,licence,retrieved_utc,version_or_date,artifact_sha256,used_in,superseded_by\n"
COVERAGE = ("topic,priority,status,files,n_sources\n"
            "windows/demo,P1,partial,windows/demo.md;windows/demo.csv,1\n"
            "dsc/manifests,P2,complete,dsc/manifests.md;dsc/raw/,1\n")


class TrailerRules(unittest.TestCase):
    def compute(self, old, new):
        paths = sorted(p for p in set(old) | set(new) if old.get(p) != new.get(p))
        return kbgit.trailers_from(paths, old.get, new.get)

    def test_topics_from_the_coverage_mapping(self):
        old = {"_coverage.csv": COVERAGE, "windows/demo.csv": "a\n1\n", "dsc/raw/x.json": "{}",
               "windows/loose.md": "---\ntopic: windows/loose\n---\n", "windows/notes.txt": "x", "_gaps.md": "g"}
        new = {**old, "windows/demo.csv": "a\n2\n", "dsc/raw/x.json": "{ }", "windows/loose.md": "---\ntopic: windows/loose\n---\nx\n",
               "windows/notes.txt": "y", "_gaps.md": "h", "README.md": "r"}
        self.assertEqual(self.compute(old, new), {"KB-Topics": ["dsc/manifests", "windows/demo", "windows/loose"]})

    def test_sources_added_changed_superseded(self):
        u = "https://learn.microsoft.com/en-us/x"
        hid = kbid.source_id(u)
        old = {"_sources.csv": HEADER.replace(",superseded_by", "") + "S100,https://e.example.com/a,A,p,l,2026-01-01,v,,a.md\n"
                                "S101,https://e.example.com/b,B,p,l,2026-01-01,v,,\nS102,https://e.example.com/c,C,p,l,2026-01-01,v,,\n"}
        new = {"_sources.csv": HEADER + "S100,https://e.example.com/a,A,p,l,2026-01-01,v,,b.md,\n"  # used_in + new empty column: no edit
                                "S101,https://e.example.com/b,B2,p,l,2026-02-01,v,,,\nS102,https://e.example.com/c,C,p,l,2026-01-01,v,,,"
                                f"{hid}\n{hid},{u},X,p,l,2026-02-01,v,,,\n"}
        self.assertEqual(self.compute(old, new), {"KB-Sources-Added": [hid], "KB-Sources-Changed": ["S101"],
                                                  "KB-Sources-Superseded": ["S102"]})

    def test_answers_added_and_edited(self):
        old = {"_answers.md": "# Answers\n\nintro\n\n## Q1. a?\n\nyes\n\n## Q2. b?\n\nno\n"}
        new = {"_answers.md": "# Answers\n\nintro changed\n\n## Q1. a?\n\nyes, really\n\n## Q2. b?\n\nno\n\n## QK-new-one. c?\n\nmaybe\n"}
        self.assertEqual(self.compute(old, new), {"KB-Answers": ["Q1", "QK-new-one"]})

    def test_format_threshold_and_matching(self):
        many = [f"S{n}" for n in range(100, 100 + kbgit.MAX_IDS + 1)]
        lines = kbgit.trailer_lines({"KB-Topics": ["b/y", "a/x"], "KB-Sources-Added": many}, "2026-09-25")
        self.assertEqual(lines, ["KB-Topics: b/y, a/x", f"KB-Sources-Added: {len(many)} ids (see diff)", "KB-Verified: 2026-09-25"])
        have = kbgit.parse_trailers("\n".join(lines) + "\nCo-Authored-By: x <noreply@example.com>\nkb-answers: QK-a")
        self.assertTrue(kbgit.values_match(have["KB-Sources-Added"], many))
        self.assertFalse(kbgit.values_match(have["KB-Sources-Added"], many[:-1]))
        self.assertTrue(kbgit.values_match(have["KB-Topics"], ["a/x", "b/y"]))
        self.assertEqual(have["KB-Answers"], ["QK-a"])  # keys are case-insensitive
        self.assertTrue(kbgit.values_match(None, []) and not kbgit.values_match(None, ["a/x"]))
        self.assertFalse(kbgit.values_match(["a/x", "a/x"], ["a/x"]))  # a key twice is wrong
        self.assertTrue(kbgit.valid_date("2026-02-28") and not kbgit.valid_date("2026-02-30") and not kbgit.valid_date("26-1-1"))


GIT = shutil.which("git")


@unittest.skipUnless(GIT, "git is not installed")
class HistoryInGit(unittest.TestCase):
    URL = "https://learn.microsoft.com/en-us/history-test/new-source"

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="kb-history-")
        cls.kb = os.path.join(cls.tmp, "kb")
        os.makedirs(os.path.join(cls.kb, "windows"))
        shutil.copytree(TOOLS, os.path.join(cls.kb, "_tools"), ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copytree(os.path.join(KB, ".githooks"), os.path.join(cls.kb, ".githooks"))
        cls.env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t",
                   "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
                   "GIT_EDITOR": "true"}
        for k in ("KB_VERIFIED", "CI_COMMIT_SHA", "CI_COMMIT_BEFORE_SHA", "GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"):
            cls.env.pop(k, None)
        cls.hid = kbid.source_id(cls.URL)
        cls.write("_sources.csv", HEADER + "S100,https://learn.microsoft.com/en-us/history-test/old,Old,Microsoft,MIT,2026-01-01,v,,,\n")
        cls.write("_answers.md", "# Answers\n\n## Q1. Is this old?\n\nYes. [DOC S100]\n")
        cls.write("_coverage.csv", COVERAGE.splitlines(keepends=True)[0] + COVERAGE.splitlines(keepends=True)[1])
        cls.article = ("---\ntopic: windows/demo\npriority: P1\napplies_to: [test]\nretrieved_utc: 2026-01-01\nsources: [S100]\n"
                       "status: partial\n---\n# Demo\n\n## Facts\n\n- The old fact. [DOC S100]\n")
        cls.write("windows/demo.md", cls.article)
        cls.write("windows/demo.csv", "a,b\n1,2\n")
        cls.git("init", "-q", "-b", "main")
        cls.git("add", "-A")
        cls.commit("2026-01-01", "-m", "base")
        cls.base = cls.rev("HEAD")
        cls.install = [cls.tool("install-hooks"), cls.tool("install-hooks")]

        # 1. a topic change + a new source row + a new QK answer, `git commit -m`, with a Co-Authored-By trailer
        cls.fact = f"- A new fact. [DOC {cls.hid}]"
        cls.write("windows/demo.md", cls.article + cls.fact + "\n")
        cls.write("windows/demo.csv", "a,b\n1,3\n")
        cls.write("_sources.csv", f"{cls.hid},{cls.URL},New,Microsoft,MIT,2026-03-01,v,,,\n", "a")
        cls.write("_answers.md", "\n## QK-history-test-question. Does it work?\n\nYes. [DOC S-aaaaaaaa]\n", "a")
        cls.git("add", "-A")
        cls.commit("2026-03-01", "-m", "docs(kb): add a fact\n\nWhy: testing.\n\nCo-Authored-By: T <noreply@example.com>")
        cls.c1 = cls.rev("HEAD")

        # 2. an editor commit (GIT_EDITOR=true keeps the template), then --amend adding an answer edit
        cls.write("windows/demo.csv", "a,b\n1,4\n")
        cls.commit("2026-03-02", "-a", "-e", "-m", "docs(kb): csv only")
        cls.msg_editor = cls.message("HEAD")
        cls.write("_answers.md", cls.read("_answers.md").replace("Yes. [DOC S100]", "Still yes. [DOC S100]"))
        cls.commit("2026-03-02", "-a", "--amend", "--no-edit")
        cls.c2 = cls.rev("HEAD")

        # 3. a non-kb change; 4. KB_VERIFIED + superseding a source; 5. a kb change with --no-verify
        cls.write("notes.txt", "not kb content\n")
        cls.git("add", "-A")
        cls.commit("2026-03-03", "-m", "chore: notes")
        cls.c3 = cls.rev("HEAD")
        cls.write("_sources.csv", cls.read("_sources.csv").replace("2026-01-01,v,,,", f"2026-01-01,v,,,{cls.hid}"))
        cls.commit("2026-03-04", "-a", "-m", "fix(kb): supersede S100", env={"KB_VERIFIED": "2026-03-04"})
        cls.c4 = cls.rev("HEAD")
        cls.write("windows/demo.md", cls.read("windows/demo.md") + "- Unhooked fact. [DOC S100]\n")
        cls.commit("2026-03-05", "-a", "--no-verify", "-m", "docs(kb): no hook")
        cls.c5 = cls.rev("HEAD")
        cls.check_bad = cls.tool("check-trailers", f"{cls.base}..HEAD")
        cls.check_before = cls.tool("check-trailers", f"{cls.base}..{cls.c4}")
        cls.amend = cls.tool("trailers", "--amend")
        cls.check_after = cls.tool("check-trailers", f"{cls.base}..HEAD")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def git(cls, *args, env=None):
        return subprocess.run(["git", *args], cwd=cls.kb, env={**cls.env, **(env or {})}, capture_output=True, text=True,
                              check=True).stdout

    @classmethod
    def commit(cls, date, *args, env=None):
        stamp = f"{date}T12:00:00+00:00"
        return cls.git("commit", "-q", *args, env={"GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp, **(env or {})})

    @classmethod
    def rev(cls, r):
        return cls.git("rev-parse", r).strip()

    @classmethod
    def message(cls, r):
        return cls.git("log", "-1", "--format=%B", r)

    @classmethod
    def tool(cls, *args):
        return subprocess.run([sys.executable, os.path.join(cls.kb, "_tools", "kbgit.py"), *args], cwd=cls.kb, env=cls.env,
                              capture_output=True, text=True, errors="replace")

    @classmethod
    def read(cls, rel):
        with open(os.path.join(cls.kb, rel), encoding="utf-8") as f:
            return f.read()

    @classmethod
    def write(cls, rel, text, mode="w"):
        with open(os.path.join(cls.kb, rel), mode, encoding="utf-8", newline="") as f:
            f.write(text)

    def trailers(self, r):
        return kbgit.parse_trailers(self.git("log", "-1", "--format=%(trailers:only,unfold)", r))

    def test_install_is_idempotent(self):
        self.assertEqual([p.returncode for p in self.install], [0, 0], [p.stdout for p in self.install])
        self.assertIn("already installed", self.install[1].stdout)
        self.assertEqual(self.git("config", "--get", "core.hooksPath").strip(), ".githooks")

    def test_hook_writes_trailers(self):
        t = self.trailers(self.c1)
        self.assertEqual(t, {"KB-Topics": ["windows/demo"], "KB-Sources-Added": [self.hid], "KB-Answers": ["QK-history-test-question"]})
        co = self.git("log", "-1", "--format=%(trailers:key=Co-Authored-By,valueonly)", self.c1).strip()
        self.assertEqual(co, "T <noreply@example.com>", "Co-Authored-By must stay a trailer")

    def test_editor_and_amend_do_not_duplicate(self):
        self.assertIn("KB-Topics: windows/demo", self.msg_editor)
        self.assertNotIn("#", self.msg_editor)
        msg = self.message(self.c2)
        self.assertEqual(self.trailers(self.c2), {"KB-Topics": ["windows/demo"], "KB-Answers": ["Q1"]})
        self.assertEqual(msg.count("KB-Topics:"), 1, msg)

    def test_non_kb_commit_and_verified(self):
        self.assertEqual(self.trailers(self.c3), {})
        self.assertEqual(self.trailers(self.c4), {"KB-Sources-Superseded": ["S100"], "KB-Verified": ["2026-03-04"]})

    def test_check_trailers_flags_no_verify(self):
        self.assertEqual(self.check_bad.returncode, 1, self.check_bad.stdout)
        bad = [ln for ln in self.check_bad.stdout.splitlines() if ln.startswith("BAD ")]
        self.assertEqual(len(bad), 1, self.check_bad.stdout)
        self.assertIn(self.c5[:7], bad[0])
        self.assertIn("expected KB-Topics: windows/demo", self.check_bad.stdout)
        self.assertEqual(self.check_before.returncode, 0, self.check_before.stdout)

    def test_trailers_amend_repairs_head(self):
        self.assertEqual(self.amend.returncode, 0, self.amend.stdout)
        self.assertEqual(self.check_after.returncode, 0, self.check_after.stdout)
        self.assertEqual(self.tool("trailers", "HEAD").stdout.strip(), "KB-Topics: windows/demo")

    def test_log_finds_by_id_topic_answer_and_path(self):
        c1 = self.c1[:7]
        for target in (self.hid, "windows/demo", "QK-history-test-question"):
            r = self.tool("log", target)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertRegex(r.stdout, rf"(?m)^{c1}\s.*\[trailer\]$", target)
        r = self.tool("log", "S100")
        self.assertRegex(r.stdout, r"\[diff\]")  # the base commit has no trailers
        self.assertRegex(self.tool("log", "notes.txt").stdout, rf"(?m)^{self.c3[:7]}\s.*\[path\]$")
        self.assertEqual(self.tool("log", "QK-no-such-answer").returncode, 1)

    def test_blame_resolves_sources(self):
        n = self.read("windows/demo.md").splitlines().index(self.fact) + 1
        r = self.tool("blame", f"windows/demo.md:{n}")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(f"introduced by: {self.c1[:7]}", r.stdout)
        self.assertIn(f"{self.hid}  {self.URL}", r.stdout)
        self.assertIn("touched since: no", r.stdout)
        self.assertEqual(self.tool("blame", "windows/demo.md:999").returncode, 1)
        self.assertEqual(self.tool("blame", "windows/demo.md").returncode, 2)

    def test_asof_returns_old_content(self):
        r = self.tool("asof", "2026-02-01", "windows/demo.md")
        self.assertEqual((r.returncode, r.stdout), (0, self.article))
        self.assertIn(self.fact, self.tool("asof", "2026-03-01", "windows/demo.md").stdout)
        self.assertEqual(self.tool("asof", "2025-01-01", "windows/demo.md").returncode, 1)

    def test_tag_census(self):
        r = self.tool("tag-census", "2026-03-06")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(self.git("cat-file", "-t", "census-2026-03-06").strip(), "tag")
        body = self.git("tag", "-l", "--format=%(contents)", "census-2026-03-06")
        self.assertIn("kb confirmed current as of 2026-03-06", body)
        self.assertRegex(body, r"sources: 2 in _sources.csv \(1 superseded\)")
        self.assertEqual(self.tool("tag-census", "2026-03-06").returncode, 2)  # never moves an existing tag
        self.assertIn(self.fact, self.tool("asof", "census-2026-03-06", "windows/demo.md").stdout)

    def test_uninstall(self):
        # runs last (alphabetical) and on a scratch clone, so the other tests keep their hooks
        clone = os.path.join(self.tmp, "clone")
        subprocess.run(["git", "clone", "-q", self.kb, clone], env=self.env, check=True)
        run = lambda *a: subprocess.run([sys.executable, os.path.join(clone, "_tools", "kbgit.py"), *a], cwd=clone,  # noqa: E731
                                        env=self.env, capture_output=True, text=True)
        self.assertEqual(run("install-hooks").returncode, 0)
        self.assertEqual(run("install-hooks", "--uninstall").returncode, 0)
        cfg = subprocess.run(["git", "config", "--get", "core.hooksPath"], cwd=clone, env=self.env, capture_output=True, text=True)
        self.assertEqual(cfg.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
