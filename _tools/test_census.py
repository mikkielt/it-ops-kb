#!/usr/bin/env python3
"""census.py tests (stdlib only, no network). tests.py runs them.

  test_census.py        run them on their own

CensusRules    url classification, release-series comparison (tag families, shapes, dates, pre-releases).
CensusInGit    check_pin / check_ref / check_release against a local repository with a pinned file, a changed file,
               a deleted and a renamed file, and release tags; skipped without git.
CensusLedger   record, confirm (dates and evidence only for confirmed sources; an article re-dated only when all its
               sources are), sample and summary on a throwaway copy of the kb.
"""
import csv, io, json, os, shutil, subprocess, sys, tempfile, unittest

TOOLS = os.path.dirname(os.path.abspath(__file__))
KB = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import census  # noqa: E402

GIT = shutil.which("git")


class CensusRules(unittest.TestCase):
    def test_classify(self):
        sha = "a" * 40
        cases = {
            f"https://raw.githubusercontent.com/PowerShell/DSC/{sha}/dsc/src/args.rs": ("raw-pin", "github.com/PowerShell/DSC", sha, "dsc/src/args.rs"),
            "https://raw.githubusercontent.com/o/r/main/a/b.md": ("raw-ref", "github.com/o/r", "main", "a/b.md"),
            f"https://gitlab.com/gitlab-org/gitlab-runner/-/raw/{sha}/docs/x.md": ("raw-pin", "gitlab.com/gitlab-org/gitlab-runner", sha, "docs/x.md"),
            "https://github.com/PowerShell/DSC/releases/tag/v3.3.0": ("release", "github.com/PowerShell/DSC", "v3.3.0", ""),
            "https://github.com/o/r/issues/12": ("gh-page", "", "", ""),
            "https://api.github.com/repos/o/r/releases?per_page=3": ("api-releases", "github.com/o/r", "", ""),
            "https://api.github.com/repos/o/r": ("api-repo", "github.com/o/r", "", ""),
            "https://api.github.com/repos/o/r/issues?state=open": ("api-other", "", "", ""),
            "https://learn.microsoft.com/en-us/entra/identity/x/y": ("learn", "github.com/MicrosoftDocs/entra-docs", "", "docs/identity/x/y"),
            "https://learn.microsoft.com/en-us/intune/intune-service/x": ("learn", "", "", ""),
            "https://code.claude.com/docs/en/hooks": ("live", "", "", ""),
        }
        for url, want in cases.items():
            c = census.classify(url)
            self.assertEqual((c["kind"], c["repo"], c["pin"], c["path"]), want, url)
        self.assertEqual(census.classify("https://github.com/PowerShell/DSC/tree/release/v3.3")["refparts"], ["release", "v3.3"])

    def test_release_series(self):
        tags = ["v1.2.0", "v1.3.0", "v1.3.1-rc.1", "v1.3.0-fork.2", "v2.0.0-preview.1", "sdk/v9.0.0", "20220215", "v1.4.0.1", "v0.9.0"]
        when = {t: f"2026-0{i % 9 + 1}-01" for i, t in enumerate(tags)}
        when["v0.9.0"] = "2025-01-01"
        self.assertEqual(census.newer_tags("v1.2.0", tags, when), ["v1.3.0"])  # no rc, fork, date, 4-part or sdk/ tags
        self.assertEqual(census.newer_tags("v1.3.0", tags, when), [])
        self.assertIn("v2.0.0-preview.1", census.newer_tags("v1.3.1-rc.1", tags, when))  # a pre-release sees pre-releases
        self.assertEqual(census.newer_tags("sdk/v9.0.0", tags, when), [])
        self.assertIsNone(census.newer_tags("latest", tags, when))
        self.assertEqual(census.norm_date("September 3, 2026"), "2026-09-03")
        self.assertEqual(census.norm_date("2026-09-03T10:00:00Z"), "2026-09-03")


@unittest.skipUnless(GIT, "git is not installed")
class CensusInGit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="kb-census-")
        cls.src = os.path.join(cls.tmp, "src")
        os.makedirs(cls.src)
        cls.env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t",
                   "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
        git = cls.git
        git("init", "-q", "-b", "main")
        for f, t in (("same.md", "same\n"), ("edit.md", "one\n"), ("gone.md", "bye\n"), ("move.md", "a long enough text to rename\n" * 5)):
            cls.write(f, t)
        git("add", "-A")
        git("commit", "-q", "-m", "one")
        git("tag", "v1.0.0")
        cls.pin = git("rev-parse", "HEAD").strip()
        cls.write("edit.md", "two\n")
        git("rm", "-q", "gone.md")
        git("mv", "move.md", "moved.md")
        git("commit", "-q", "-am", "two")
        git("tag", "v1.1.0")
        cls.d, err = census.repo_dir(cls.src, base=os.path.join(cls.tmp, "repos"))
        assert cls.d, err

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def git(cls, *args):
        return subprocess.run(["git", *args], cwd=cls.src, env=cls.env, capture_output=True, text=True, check=True).stdout

    @classmethod
    def write(cls, rel, text):
        with open(os.path.join(cls.src, rel), "w", encoding="utf-8") as f:
            f.write(text)

    def test_pins(self):
        self.assertEqual(census.check_pin(self.d, self.pin, "same.md")["bucket"], "OK")
        self.assertEqual(census.check_pin(self.d, self.pin, "edit.md")["bucket"], "CHANGED")
        self.assertEqual(census.check_pin(self.d, self.pin, "gone.md")["bucket"], "GONE")
        moved = census.check_pin(self.d, self.pin, "move.md")
        self.assertEqual((moved["bucket"], moved["note"]), ("CHANGED", "renamed=moved.md"))
        self.assertEqual(census.check_pin(self.d, "b" * 40, "same.md")["bucket"], "GONE")

    def test_refs_and_releases(self):
        self.assertEqual(census.check_release(self.d, "v1.1.0")["bucket"], "OK")
        self.assertEqual(census.check_release(self.d, "v1.0.0")["bucket"], "NEWER-VERSION")
        self.assertEqual(census.check_ref(self.d, "v1.0.0", "same.md", "2026-01-01")["bucket"], "OK")  # identical in v1.1.0
        self.assertEqual(census.check_ref(self.d, "v1.0.0", "edit.md", "2026-01-01")["bucket"], "NEWER-VERSION")
        self.assertEqual(census.check_ref(self.d, "main", "same.md", "2099-01-01")["bucket"], "OK")
        self.assertEqual(census.check_ref(self.d, "main", "edit.md", "2000-01-01")["bucket"], "CHANGED")
        self.assertEqual(census.split_ref(self.d, ["main", "edit.md"]), ("main", "edit.md"))


class CensusLedger(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="kb-census-ledger-")
        cls.kb = os.path.join(cls.tmp, "kb")
        shutil.copytree(KB, cls.kb, ignore=shutil.ignore_patterns(".git", "_cache", "_private", "__pycache__", "_census", "_fetch_state.csv"))
        with open(os.path.join(cls.kb, "_sources.csv"), encoding="utf-8", newline="") as f:
            cls.rows = {r["id"]: r for r in csv.DictReader(f)}
        # an article with exactly two sources: confirm one, then both
        cls.article = "auth/gitlab-ci-identity.md"
        text = open(os.path.join(cls.kb, cls.article), encoding="utf-8").read()
        fm = census.build_index.front_matter(text)
        cls.ids = __import__("re").findall(r"S-[a-z2-7]{8}|S\d+", fm["sources"])
        assert len(cls.ids) == 2, cls.ids
        cls.log = os.path.join(cls.tmp, "log.csv")
        rows = []
        for sid, bucket in ((cls.ids[0], "OK"), (cls.ids[1], "CHANGED"), ("S100", "NEEDS-READING")):
            rows.append({c: "" for c in census.COLS} | {"id": sid, "url": cls.rows[sid]["url"], "bucket": bucket,
                                                         "evidence": f"ev {sid}", "proof": "HEAD@abc123" if bucket == "OK" else ""})
        census.write_log(cls.log, rows)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def tool(self, *args):
        return subprocess.run([sys.executable, os.path.join(self.kb, "_tools", "census.py"), *args], cwd=self.kb,
                              capture_output=True, text=True)

    def sources(self):
        with open(os.path.join(self.kb, "_sources.csv"), encoding="utf-8", newline="") as f:
            return {r["id"]: r for r in csv.DictReader(f)}

    def test_1_confirm_only_what_is_confirmed(self):
        p = self.tool("confirm", self.log, "--date", "2031-01-02")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        s = self.sources()
        self.assertEqual(s[self.ids[0]]["retrieved_utc"], "2031-01-02")
        self.assertTrue(s[self.ids[0]]["version_or_date"].endswith("confirmed 2031-01-02: HEAD@abc123"))
        self.assertEqual(s[self.ids[1]]["retrieved_utc"], self.rows[self.ids[1]]["retrieved_utc"])  # CHANGED, unread
        self.assertEqual(s["S100"]["retrieved_utc"], self.rows["S100"]["retrieved_utc"])
        self.assertNotIn("retrieved_utc: 2031-01-02", open(os.path.join(self.kb, self.article), encoding="utf-8").read())
        with open(os.path.join(self.kb, "_fetch_state.csv"), encoding="utf-8") as f:
            st = {r["id"]: r for r in csv.DictReader(f)}
        self.assertEqual((st[self.ids[0]]["checked_utc"], st[self.ids[0]]["fetched_utc"]), ("2031-01-02T00:00:00Z", ""))
        self.assertNotIn(self.ids[1], st)
        # a source merely dated today by other work does not make its article confirmed
        self.assertNotIn(self.ids[1], [r["id"] for r in census.read_log(self.log) if census.confirmed(r)])

    def test_2_record_then_confirm_redates_the_article(self):
        res = os.path.join(self.tmp, "res.json")
        json.dump([{"id": self.ids[1], "outcome": "confirmed", "note": "re-read in full"}, {"id": "S1", "outcome": "nope"}],
                  open(res, "w"))
        p = self.tool("record", self.log, "--from", res)
        self.assertEqual(p.returncode, 1, p.stdout)  # one bad item reported
        self.assertIn("recorded 1 outcome(s), skipped 1", p.stdout)
        p = self.tool("confirm", self.log, "--date", "2031-01-02")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("retrieved_utc: 2031-01-02", open(os.path.join(self.kb, self.article), encoding="utf-8").read())
        v = self.sources()[self.ids[0]]["version_or_date"]
        self.assertEqual(v.count("confirmed 2031-01-02"), 1, "a second confirm replaces the suffix")
        r = subprocess.run([sys.executable, os.path.join(self.kb, "_tools", "check.py")], cwd=self.kb, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout[-2000:])

    def test_3_sample_and_summary(self):
        p = self.tool("sample", self.log, "--seed", "3")
        rows = list(csv.DictReader(io.StringIO(p.stdout)))
        self.assertEqual({r["group"] for r in rows}, {"ok"})
        p = self.tool("summary", self.log)
        self.assertIn("sources=3 OK=1 CHANGED=1", p.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
