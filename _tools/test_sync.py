#!/usr/bin/env python3
"""Sync tests (stdlib only): `kbgit.py sync` against a throwaway remote. tests.py runs them.

  test_sync.py             run them on their own
  SyncRules                sync's argument handling and path classes (no git needed)
  SyncInGit                a copy of the kb committed into a temp repo, a bare clone of it as the "remote" (never the
                           real origin) and two clones A and B with the hooks installed. In order:
                           1. A adds a source row and an article and pushes with `sync --push`; B (now behind) adds
                              another source row and an answer: `sync --dry-run` changes nothing, a dirty tree is
                              refused (exit 2), then `sync --push` rebases, fixes, passes the gate and pushes;
                           2. A and B both take the legacy id S9999 for different urls, both head an answer
                              QK-sync-shared (different questions) and both add a pre-QK-<slug> answer QK1: A's pushed
                              S9999 and QK-sync-shared stay, B's sync renumbers its own (citations and mentions follow),
                              both QK1 become QK-<slug>, trailers are refreshed and check.py passes;
                           3. A and B edit the same article line: B's sync stops with exit 3, the rebase in progress.
                           The gate skips tests.py here (KB_SYNC_NO_TESTS=1: no recursive test run). Skipped without git.
"""
import csv, io, os, shutil, subprocess, sys, tempfile, unittest

TOOLS = os.path.dirname(os.path.abspath(__file__))
KB = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import kbgit, kbid  # noqa: E402

GIT = shutil.which("git")


def rows(text):
    return {r["id"]: r for r in csv.DictReader(io.StringIO(text))}


class SyncRules(unittest.TestCase):
    def test_mechanical_paths(self):
        for p in ("_sources.csv", "_fetch_state.csv", "_answers.md", "_gaps.md", "_conflicts.md", "_coverage.csv",
                  "_tools/lint_baseline.txt", "README.md"):
            self.assertIn(p, kbgit.MECHANICAL)
        for p in ("auth/kerberos.md", "_tools/kbgit.py", "AGENTS.md", ".gitattributes", "_artifacts.csv"):
            self.assertNotIn(p, kbgit.MECHANICAL)

    def test_fix_args_and_renumber_lines(self):
        self.assertEqual(kbgit.fix_args(None, "u", "o"), ["fix"])
        self.assertEqual(kbgit.fix_args("b", "u", "o"), ["fix", "--base", "b", "--upstream", "u", "--side", "o"])
        out = "  _sources.csv: S9999 collision: https://a.example.com/ -> S-aaaaaaaa (hash id)\n  wrote _sources.csv\n"
        self.assertEqual(kbgit.renumbered(out), ["_sources.csv: S9999 collision: https://a.example.com/ -> S-aaaaaaaa (hash id)"])

    def test_push_rejection_patterns(self):
        self.assertTrue(kbgit.REJECTED.search(" ! [rejected]        HEAD -> main (fetch first)"))
        self.assertTrue(kbgit.REJECTED.search("Updates were rejected because the tip ... non-fast-forward"))
        self.assertFalse(kbgit.REJECTED.search("fatal: Could not read from remote repository."))


@unittest.skipUnless(GIT, "git is not installed")
class SyncInGit(unittest.TestCase):
    URL_A1, URL_B1 = "https://learn.microsoft.com/en-us/sync-test/a1", "https://learn.microsoft.com/en-us/sync-test/b1"
    URL_A2, URL_B2 = "https://learn.microsoft.com/en-us/sync-test/a2", "https://learn.microsoft.com/en-us/sync-test/b2"
    Q_B = "Does the sync test answer survive a rebase?"
    Q_SHARED_A, Q_SHARED_B = "What does clone a ask?", "What does clone b ask about sync?"
    Q_OLD_A, Q_OLD_B = "Old style question from clone a", "Old style question from clone b"

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="kb-sync-")
        seed = os.path.join(cls.tmp, "seed")
        shutil.copytree(KB, seed, ignore=shutil.ignore_patterns(".git", "_cache", "_private", "__pycache__", "_fetch_state.csv"))
        cls.env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t",
                   "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
                   "KB_SYNC_NO_TESTS": "1"}
        for k in ("KB_VERIFIED", "KB_TESTS_FAST", "CI_COMMIT_SHA", "CI_COMMIT_BEFORE_SHA", "GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"):
            cls.env.pop(k, None)
        cls.git(seed, "init", "-q", "-b", "main")
        cls.git(seed, "add", "-A")
        cls.git(seed, "commit", "-q", "-m", "base")
        cls.remote = os.path.join(cls.tmp, "remote.git")
        cls.git(cls.tmp, "clone", "-q", "--bare", seed, cls.remote)
        cls.a, cls.b = os.path.join(cls.tmp, "a"), os.path.join(cls.tmp, "b")
        for d in (cls.a, cls.b):
            cls.git(cls.tmp, "clone", "-q", cls.remote, d)
            assert cls.kbgit(d, "install-hooks").returncode == 0
        cls.base = cls.git(cls.a, "rev-parse", "HEAD").strip()

        # 1. A: a source row + an article; B: another source row + an answer
        cls.add_source(cls.a, "S-", cls.URL_A1, "a1")
        cls.article(cls.a, "a", [kbid.source_id(cls.URL_A1)], ["The first fact from clone a."])
        cls.commit(cls.a, "docs(kb): sync test a1")
        cls.push_a1 = cls.kbgit(cls.a, "sync", "--push")
        hb = kbid.source_id(cls.URL_B1)
        cls.add_source(cls.b, "S-", cls.URL_B1, "b1")
        cls.append(cls.b, "_answers.md", f"\n## {kbid.answer_id(cls.Q_B)}. {cls.Q_B}\n\nYes, it does. [DOC {hb}]\n")
        cls.commit(cls.b, "docs(kb): sync test b1")
        cls.b_head_before = cls.rev(cls.b, "HEAD")
        cls.b_sources_before = cls.read(cls.b, "_sources.csv")
        cls.dry = cls.kbgit(cls.b, "sync", "--dry-run", "--push")
        cls.b_after_dry = (cls.rev(cls.b, "HEAD"), cls.git(cls.b, "status", "--porcelain"), cls.read(cls.b, "_sources.csv"))
        cls.append(cls.b, "README.md", "x\n")
        cls.git(cls.b, "add", "README.md")
        cls.append(cls.b, "_gaps.md", "x\n")
        cls.dirty = cls.kbgit(cls.b, "sync", "--push")
        cls.git(cls.b, "reset", "-q", "--hard", "HEAD")
        cls.push_b1 = cls.kbgit(cls.b, "sync", "--push")

        # 2. both clones take the legacy id S9999 for different urls
        cls.add_source(cls.a, "S9999", cls.URL_A2, "a2")
        cls.article(cls.a, "a2", ["S9999"], ["Clone a cites its S9999."])
        cls.append(cls.a, "_answers.md", f"\n## QK-sync-shared. {cls.Q_SHARED_A}\n\nClone a answers. [DOC S9999]\n"
                                         f"\n## QK1. {cls.Q_OLD_A}\n\nOld style a.\n")
        cls.commit(cls.a, "docs(kb): sync test a2 with S9999")
        cls.push_a2 = cls.kbgit(cls.a, "sync", "--push")
        cls.add_source(cls.b, "S9999", cls.URL_B2, "b2")
        cls.article(cls.b, "b2", ["S9999"], ["Clone b cites its S9999.", "Answer: `_answers.md` QK-sync-shared and QK1."])
        cls.append(cls.b, "_answers.md", f"\n## QK-sync-shared. {cls.Q_SHARED_B}\n\nClone b answers. [DOC S9999]\n"
                                         f"\n## QK1. {cls.Q_OLD_B}\n\nOld style b.\n")
        cls.commit(cls.b, "docs(kb): sync test b2 with S9999")
        cls.push_b2 = cls.kbgit(cls.b, "sync", "--push")
        cls.b2_checks = {t: cls.tool(cls.b, t, *args) for t, args in
                         (("check.py", ()), ("build_index.py", ("--check",)), ("kbgit.py", ("fix", "--check")))}
        cls.b2_trailers = cls.kbgit(cls.b, "check-trailers", f"{cls.base}..HEAD")

        # 3. the same article line edited on both sides
        cls.pull_a = cls.kbgit(cls.a, "sync")
        for d, who in ((cls.a, "clone a now words it"), (cls.b, "clone b words it")):
            cls.write(d, "windows/sync-test-a.md", cls.read(d, "windows/sync-test-a.md").replace(
                "The first fact from clone a.", f"The first fact, as {who}."))
            cls.commit(d, "docs(kb): reword the first fact")
        cls.push_a3 = cls.kbgit(cls.a, "sync", "--push")
        cls.b3_head = cls.rev(cls.b, "HEAD")
        cls.push_b3 = cls.kbgit(cls.b, "sync", "--push")
        cls.b3_rebasing = os.path.isdir(os.path.join(cls.b, ".git", "rebase-merge")) or os.path.isdir(os.path.join(cls.b, ".git", "rebase-apply"))
        cls.b3_again = cls.kbgit(cls.b, "sync", "--push")
        cls.git(cls.b, "rebase", "--abort")
        cls.b3_after_abort = cls.rev(cls.b, "HEAD")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # ---------------------------------------------------------------- helpers

    @classmethod
    def git(cls, cwd, *args):
        return subprocess.run(["git", *args], cwd=cwd, env=cls.env, capture_output=True, text=True, check=True).stdout

    @classmethod
    def rev(cls, d, r):
        return cls.git(d, "rev-parse", r).strip()

    @classmethod
    def tool(cls, d, name, *args):
        return subprocess.run([sys.executable, os.path.join(d, "_tools", name), *args], cwd=d, env=cls.env,
                              capture_output=True, text=True, errors="replace")

    @classmethod
    def kbgit(cls, d, *args):
        return cls.tool(d, "kbgit.py", *args)

    @classmethod
    def read(cls, d, rel):
        with open(os.path.join(d, rel), encoding="utf-8") as f:
            return f.read()

    @classmethod
    def write(cls, d, rel, text):
        with open(os.path.join(d, rel), "w", encoding="utf-8", newline="") as f:
            f.write(text)

    @classmethod
    def append(cls, d, rel, text):
        with open(os.path.join(d, rel), "a", encoding="utf-8", newline="") as f:
            f.write(text)

    @classmethod
    def add_source(cls, d, sid, url, tag):
        sid = kbid.source_id(url) if sid == "S-" else sid
        buf = io.StringIO()
        csv.writer(buf, lineterminator="\n").writerow([sid, url, f"Sync test {tag}", "Microsoft", "MIT", "2026-09-25", "v", "", "", ""])
        cls.append(d, "_sources.csv", buf.getvalue())

    @classmethod
    def article(cls, d, name, sids, facts):
        cls.write(d, f"windows/sync-test-{name}.md",
                  f"---\ntopic: windows/sync-test-{name}\npriority: P3\napplies_to: [test]\nretrieved_utc: 2026-09-25\n"
                  f"sources: [{', '.join(sids)}]\nstatus: partial\n---\n# Sync test {name}\n\n## Summary\n\nTest.\n\n## Facts\n\n"
                  + "".join(f"- {f} [DOC {sids[0]}]\n" for f in facts) + "\n## Reference\n\n## Examples\n")

    @classmethod
    def commit(cls, d, msg):
        r = cls.tool(d, "build_index.py")
        assert r.returncode == 0, r.stdout + r.stderr
        cls.git(d, "add", "-A")
        cls.git(d, "commit", "-q", "-m", msg)

    def remote_file(self, rel):
        return subprocess.run(["git", "--git-dir", self.remote, "show", f"main:{rel}"], env=self.env, capture_output=True,
                              text=True, check=True).stdout

    # ---------------------------------------------------------------- tests

    def test_clones_only_know_the_temp_remote(self):
        for d in (self.a, self.b):
            self.assertEqual(self.git(d, "remote", "get-url", "origin").strip(), self.remote)
            self.assertTrue(os.path.realpath(d).startswith(os.path.realpath(self.tmp)))

    def test_first_push_needs_no_rebase(self):
        r = self.push_a1
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("local 1 ahead, 0 behind", r.stdout)
        self.assertIn("pushed: yes", r.stdout)

    def test_dry_run_changes_nothing(self):
        r = self.dry
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("local 1 ahead, 1 behind", r.stdout)
        self.assertIn("would rebase 1 local commit(s)", r.stdout)
        self.assertIn("mechanical (fix): _sources.csv", r.stdout)
        self.assertEqual(self.b_after_dry, (self.b_head_before, "", self.b_sources_before))
        self.assertNotIn("pushed: yes", r.stdout)

    def test_dirty_tree_is_refused(self):
        r = self.dirty
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("staged:   README.md", r.stdout)
        self.assertIn("unstaged: _gaps.md", r.stdout)
        self.assertIn("git stash", r.stdout)

    def test_clean_rebase_is_fixed_gated_and_pushed(self):
        r = self.push_b1
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("commits rebased: 1", r.stdout)
        self.assertRegex(r.stdout, r"gate check.py: ok")
        self.assertRegex(r.stdout, r"gate check-trailers origin/main\.\.HEAD: ok")
        self.assertIn("gate tests.py (fast): skipped", r.stdout)
        self.assertIn("pushed: yes", r.stdout)
        src = rows(self.remote_file("_sources.csv"))
        ha, hb = kbid.source_id(self.URL_A1), kbid.source_id(self.URL_B1)
        self.assertIn(ha, src)
        self.assertIn(hb, src)
        self.assertEqual(src[ha]["used_in"], "windows/sync-test-a.md")
        self.assertIn(kbid.answer_id(self.Q_B), self.remote_file("_answers.md"))
        ids = list(rows(self.remote_file("_sources.csv")))
        self.assertEqual(ids, sorted(ids, key=kbid.sort_key))

    def test_collision_renumbered_with_trailers_refreshed(self):
        self.assertEqual(self.push_a2.returncode, 0, self.push_a2.stdout + self.push_a2.stderr)
        r = self.push_b2
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertRegex(r.stdout, r"ids renumbered: .*S9999")
        self.assertRegex(r.stdout, r"ids renumbered: .*QK-sync-shared collision")
        self.assertIn("trailers refreshed on", r.stdout)
        self.assertIn("pushed: yes", r.stdout)
        src = rows(self.remote_file("_sources.csv"))
        hb = kbid.source_id(self.URL_B2)
        self.assertEqual((src["S9999"]["url"], src[hb]["url"]), (self.URL_A2, self.URL_B2))  # pushed ids are never renumbered
        self.assertIn("[DOC S9999]", self.remote_file("windows/sync-test-a2.md"))
        b2 = self.remote_file("windows/sync-test-b2.md")
        qb, qa_old, qb_old = (kbid.answer_id(q) for q in (self.Q_SHARED_B, self.Q_OLD_A, self.Q_OLD_B))
        self.assertIn(f"[DOC {hb}]", b2)
        self.assertIn(f"`_answers.md` {qb} and {qb_old}.", b2)
        ans = self.remote_file("_answers.md")
        for want in (f"## QK-sync-shared. {self.Q_SHARED_A}\n\nClone a answers. [DOC S9999]",
                     f"## {qb}. {self.Q_SHARED_B}\n\nClone b answers. [DOC {hb}]",
                     f"## {qa_old}. {self.Q_OLD_A}", f"## {qb_old}. {self.Q_OLD_B}"):
            self.assertIn(want, ans)
        self.assertNotIn("## QK1.", ans)
        for t, p in self.b2_checks.items():
            self.assertEqual(p.returncode, 0, f"{t}: " + (p.stdout + p.stderr)[-2000:])
        self.assertEqual(self.b2_trailers.returncode, 0, self.b2_trailers.stdout)

    def test_same_line_edit_needs_a_human(self):
        self.assertEqual(self.pull_a.returncode, 0, self.pull_a.stdout + self.pull_a.stderr)
        self.assertIn("pushed: no (without --push)", self.pull_a.stdout)
        self.assertEqual(self.push_a3.returncode, 0, self.push_a3.stdout + self.push_a3.stderr)
        r = self.push_b3
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("needs-human: windows/sync-test-a.md", r.stdout)
        self.assertIn("git rebase --abort", r.stdout)
        self.assertRegex(r.stdout, r"sync-state: base=[0-9a-f]{40} upstream=[0-9a-f]{40} orig_head=[0-9a-f]{40}")
        self.assertTrue(self.b3_rebasing, "the rebase must be left in progress")
        self.assertEqual(self.b3_again.returncode, 2, self.b3_again.stdout)
        self.assertIn("rebase is in progress", self.b3_again.stdout)
        self.assertEqual(self.b3_after_abort, self.b3_head)
        self.assertNotIn("clone b words it", self.remote_file("windows/sync-test-a.md"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
