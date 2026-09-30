"""census.py tests, no network (`python3 _tools/tests.py -k census`).

TestCensusRules    url classification, release-series comparison (tag families, shapes, dates, pre-releases).
TestCensusInGit    check_pin / check_ref / check_release against a local repository with a pinned file, a changed file,
                   a deleted and a renamed file, and release tags (local and fast: no `git` marker); skipped without git.
TestCensusLedger   record, confirm (dates and evidence only for confirmed sources; an article re-dated only when all its
                   sources are), sample and summary on a throwaway copy of the kb.
"""
import csv, glob, io, json, os, re, shutil

import pytest

import census
from conftest import P, Repo, copy_kb, git_env, requires_git


class TestCensusRules:
    def test_root_option(self):
        """census.py and fetch.py work on one of this repository's roots: an unknown one is a usage error."""
        import subprocess, sys
        from conftest import TOOLS
        for args in (["census.py", "--root", "no-such-root", "summary", "x.csv"], ["fetch.py", "--offline", "--root", "no-such-root"]):
            p = subprocess.run([sys.executable, os.path.join(TOOLS, args[0]), *args[1:]], capture_output=True, text=True, encoding="utf-8")
            assert p.returncode == 2 and "no such root" in p.stderr, p.stderr
        p = subprocess.run([sys.executable, os.path.join(TOOLS, "fetch.py"), "--offline", "--root", "public"],
                           capture_output=True, text=True, encoding="utf-8")
        assert p.returncode == 0 and p.stdout.startswith("ok="), p.stdout + p.stderr

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
            assert (c["kind"], c["repo"], c["pin"], c["path"]) == want, url
        assert census.classify("https://github.com/PowerShell/DSC/tree/release/v3.3")["refparts"] == ["release", "v3.3"]

    def test_learn_page_updated_at(self, monkeypatch):
        # updated_at decides, never ms.date (the author's review date, earlier in the head and lagging)
        head = ('<meta name="ms.date" content="2026-02-06T00:00:00Z" />'
                '<meta name="updated_at" content="{}T22:34:00Z" />'
                '<meta name="git_commit_id" content="a60f43f6f562ded6195ddd8d888335f2d8e11e73" />')
        pages = {"https://learn.microsoft.com/en-us/intune/a": (200, head.format("2026-07-01"), "https://learn.microsoft.com/en-us/intune/b"),
                 "https://learn.microsoft.com/en-us/intune/c": (200, head.format("2026-09-20"), "https://learn.microsoft.com/en-us/intune/c"),
                 "https://learn.microsoft.com/en-us/intune/d": (200, "<html></html>", "https://learn.microsoft.com/en-us/intune/d"),
                 "https://learn.microsoft.com/en-us/intune/e": (404, "", "https://learn.microsoft.com/en-us/intune/e")}
        monkeypatch.setattr(census, "fetch", lambda url, **k: pages[url])
        st, res = census.check_learn_page("https://learn.microsoft.com/en-us/intune/a", "2026-09-10")
        assert res["bucket"] == "OK" and "updated_at 2026-07-01, git_commit_id a60f43f6f562" == res["proof"], res
        assert "redirected to https://learn.microsoft.com/en-us/intune/b" in res["evidence"]
        assert census.check_learn_page("https://learn.microsoft.com/en-us/intune/c", "2026-09-10")[1]["bucket"] == "CHANGED"
        res = census.check_learn_page("https://learn.microsoft.com/en-us/intune/d", "2026-09-10")[1]
        assert res["bucket"] == "NEEDS-READING" and res["note"] == "learn"
        assert census.check_learn_page("https://learn.microsoft.com/en-us/intune/e", "2026-09-10")[1]["bucket"] == "GONE"

    def test_release_series(self):
        tags = ["v1.2.0", "v1.3.0", "v1.3.1-rc.1", "v1.3.0-fork.2", "v2.0.0-preview.1", "sdk/v9.0.0", "20220215", "v1.4.0.1", "v0.9.0"]
        when = {t: f"2026-0{i % 9 + 1}-01" for i, t in enumerate(tags)}
        when["v0.9.0"] = "2025-01-01"
        assert census.newer_tags("v1.2.0", tags, when) == ["v1.3.0"]  # no rc, fork, date, 4-part or sdk/ tags
        assert census.newer_tags("v1.3.0", tags, when) == []
        assert "v2.0.0-preview.1" in census.newer_tags("v1.3.1-rc.1", tags, when)  # a pre-release sees pre-releases
        assert census.newer_tags("sdk/v9.0.0", tags, when) == []
        assert census.newer_tags("latest", tags, when) is None
        assert census.norm_date("September 3, 2026") == "2026-09-03"
        assert census.norm_date("2026-09-03T10:00:00Z") == "2026-09-03"


@requires_git
class TestCensusInGit:
    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def scenario(cls, tmp_path_factory):
        cls.tmp = str(tmp_path_factory.mktemp("kb-census"))
        src = Repo(os.path.join(cls.tmp, "src"), git_env())
        os.makedirs(src.path)
        git = src.git
        git("init", "-q", "-b", "main")
        for f, t in (("same.md", "same\n"), ("edit.md", "one\n"), ("gone.md", "bye\n"), ("move.md", "a long enough text to rename\n" * 5)):
            src.write(f, t)
        git("add", "-A")
        git("commit", "-q", "-m", "one")
        git("tag", "v1.0.0")
        cls.pin = git("rev-parse", "HEAD").strip()
        src.write("edit.md", "two\n")
        git("rm", "-q", "gone.md")
        git("mv", "move.md", "moved.md")
        git("commit", "-q", "-am", "two")
        git("tag", "v1.1.0")
        cls.d, err = census.repo_dir(src.path, base=os.path.join(cls.tmp, "repos"))
        assert cls.d, err
        yield
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_pins(self):
        assert census.check_pin(self.d, self.pin, "same.md")["bucket"] == "OK"
        assert census.check_pin(self.d, self.pin, "edit.md")["bucket"] == "CHANGED"
        assert census.check_pin(self.d, self.pin, "gone.md")["bucket"] == "GONE"
        moved = census.check_pin(self.d, self.pin, "move.md")
        assert (moved["bucket"], moved["note"]) == ("CHANGED", "renamed=moved.md")
        assert census.check_pin(self.d, "b" * 40, "same.md")["bucket"] == "GONE"

    def test_refs_and_releases(self):
        assert census.check_release(self.d, "v1.1.0")["bucket"] == "OK"
        assert census.check_release(self.d, "v1.0.0")["bucket"] == "NEWER-VERSION"
        assert census.check_ref(self.d, "v1.0.0", "same.md", "2026-01-01")["bucket"] == "OK"  # identical in v1.1.0
        assert census.check_ref(self.d, "v1.0.0", "edit.md", "2026-01-01")["bucket"] == "NEWER-VERSION"
        assert census.check_ref(self.d, "main", "same.md", "2099-01-01")["bucket"] == "OK"
        assert census.check_ref(self.d, "main", "edit.md", "2000-01-01")["bucket"] == "CHANGED"
        assert census.split_ref(self.d, ["main", "edit.md"]) == ("main", "edit.md")


@requires_git
class TestHookEnvironment:
    def test_planted_git_dir_leaves_its_repository_alone(self, tmp_path):
        """A pre-push hook sets GIT_DIR (and in a worktree GIT_WORK_TREE) for the run it starts. A process that imports
        conftest, as pytest does before any test, then runs census.repo_dir (its `fetch --force origin
        +refs/heads/*:refs/heads/*`) leaves the repository those variables name as it was: without conftest's cleanup
        git follows GIT_DIR and fetches that repository's origin over its branches and tags."""
        import subprocess, sys
        from conftest import TOOLS

        def repo(name, text, *branches):
            r = Repo(tmp_path / name)
            os.makedirs(r.path)
            r.git("init", "-q", "-b", branches[0])
            r.write("a.md", text)
            r.git("add", "-A")
            r.git("commit", "-q", "-m", text)
            for b in branches[1:]:
                r.git("branch", b)
            return r

        upstream = repo("upstream", "upstream\n", "main")
        upstream.git("tag", "v9.9.9")
        hooked = repo("hooked", "hooked\n", "work", "main")  # its checked-out branch is one upstream lacks
        hooked.git("remote", "add", "origin", upstream.path)
        refs = ("for-each-ref", "--format=%(refname) %(objectname)")
        before = hooked.git(*refs)
        src = repo("src", "src\n", "main")
        code = "import sys, conftest, census; d, err = census.repo_dir(sys.argv[1], base=sys.argv[2]); print(d or err)"
        env = git_env(GIT_DIR=os.path.join(hooked.path, ".git"), GIT_WORK_TREE=hooked.path)
        p = subprocess.run([sys.executable, "-c", code, src.path, str(tmp_path / "repos")], cwd=TOOLS, env=env,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        assert p.returncode == 0, p.stdout + p.stderr
        assert hooked.git(*refs) == before, f"the planted GIT_DIR's repository changed: {p.stdout}{p.stderr}"
        assert os.path.isdir(os.path.join(p.stdout.strip(), "refs")), p.stdout  # the clone is where census put it


class TestCensusLedger:
    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def scenario(cls, tmp_path_factory):
        cls.tmp = str(tmp_path_factory.mktemp("kb-census-ledger"))
        cls.kb = copy_kb(os.path.join(cls.tmp, "kb"), skip=("_census", "_fetch_state.csv"))
        cls.repo = Repo(cls.kb, dict(os.environ))
        with open(os.path.join(cls.kb, P("_sources.csv")), encoding="utf-8", newline="") as f:
            cls.rows = {r["id"]: r for r in csv.DictReader(f)}
        # an article with exactly two sources: confirm one, then both (the first such article, so edits to any
        # one article's source list do not break the scenario)
        cls.article, cls.ids = None, []
        for rel in sorted(glob.glob(os.path.join(cls.kb, P("*/*.md")))):
            fm = census.build_index.front_matter(open(rel, encoding="utf-8").read()) or {}  # _snapshots/README.md has none
            ids = re.findall(r"S-[a-z2-7]{8}|S\d+", fm.get("sources", "") or "")
            if len(ids) == 2 and "S100" not in ids and all(i in cls.rows for i in ids):
                cls.article, cls.ids = os.path.relpath(rel, cls.kb), ids
                break
        assert cls.article, "no article with exactly two sources"
        cls.log = os.path.join(cls.tmp, "log.csv")
        rows = []
        for sid, bucket in ((cls.ids[0], "OK"), (cls.ids[1], "CHANGED"), ("S100", "NEEDS-READING")):
            rows.append({c: "" for c in census.COLS} | {"id": sid, "url": cls.rows[sid]["url"], "bucket": bucket,
                                                         "evidence": f"ev {sid}", "proof": "HEAD@abc123" if bucket == "OK" else ""})
        census.write_log(cls.log, rows)
        yield
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def tool(self, *args):
        return self.repo.tool("census.py", *args)

    def sources(self):
        with open(os.path.join(self.kb, P("_sources.csv")), encoding="utf-8", newline="") as f:
            return {r["id"]: r for r in csv.DictReader(f)}

    def test_1_confirm_only_what_is_confirmed(self):
        p = self.tool("confirm", self.log, "--date", "2031-01-02")
        assert p.returncode == 0, p.stdout + p.stderr
        s = self.sources()
        assert s[self.ids[0]]["retrieved_utc"] == "2031-01-02"
        assert s[self.ids[0]]["version_or_date"].endswith("confirmed 2031-01-02: HEAD@abc123")
        assert s[self.ids[1]]["retrieved_utc"] == self.rows[self.ids[1]]["retrieved_utc"]  # CHANGED, unread
        assert s["S100"]["retrieved_utc"] == self.rows["S100"]["retrieved_utc"]
        assert "retrieved_utc: 2031-01-02" not in open(os.path.join(self.kb, self.article), encoding="utf-8").read()
        with open(os.path.join(self.kb, P("_fetch_state.csv")), encoding="utf-8") as f:
            st = {r["id"]: r for r in csv.DictReader(f)}
        assert (st[self.ids[0]]["checked_utc"], st[self.ids[0]]["fetched_utc"]) == ("2031-01-02T00:00:00Z", "")
        assert self.ids[1] not in st
        # a source merely dated today by other work does not make its article confirmed
        assert self.ids[1] not in [r["id"] for r in census.read_log(self.log) if census.confirmed(r)]

    def test_2_record_then_confirm_redates_the_article(self):
        res = os.path.join(self.tmp, "res.json")
        json.dump([{"id": self.ids[1], "outcome": "confirmed", "note": "re-read in full"}, {"id": "S1", "outcome": "nope"}],
                  open(res, "w", encoding="utf-8", newline="\n"))
        p = self.tool("record", self.log, "--from", res)
        assert p.returncode == 1, p.stdout  # one bad item reported
        assert "recorded 1 outcome(s), skipped 1" in p.stdout
        p = self.tool("confirm", self.log, "--date", "2031-01-02")
        assert p.returncode == 0, p.stdout + p.stderr
        assert "retrieved_utc: 2031-01-02" in open(os.path.join(self.kb, self.article), encoding="utf-8").read()
        v = self.sources()[self.ids[0]]["version_or_date"]
        assert v.count("confirmed 2031-01-02") == 1, "a second confirm replaces the suffix"
        r = self.repo.tool("check.py")
        assert r.returncode == 0, r.stdout[-2000:]

    def test_3_sample_and_summary(self):
        p = self.tool("sample", self.log, "--seed", "3")
        rows = list(csv.DictReader(io.StringIO(p.stdout)))
        assert {r["group"] for r in rows} == {"ok"}
        p = self.tool("summary", self.log)
        assert "sources=3 OK=1 CHANGED=1" in p.stdout


def test_factdiff_verdicts(tmp_path):
    """A fact diff log feeds the census: unchanged or all verbatim -> OK, gone -> GONE, facts to review -> CHANGED,
    pinned left to the git checks."""
    import factdiff
    log = tmp_path / "factdiff.csv"
    base = {c: "" for c in factdiff.LOG_COLS}
    rows = [{**base, "source_id": "S1", "verdict": "unchanged", "signal": "etag", "evidence": "304"},
            {**base, "source_id": "S2", "verdict": "changed"}, {**base, "source_id": "S2", "verdict": "changed", "fact": "a", "outcome": "verbatim"},
            {**base, "source_id": "S3", "verdict": "changed"}, {**base, "source_id": "S3", "verdict": "changed", "fact": "b", "outcome": "modified"},
            {**base, "source_id": "S4", "verdict": "gone", "evidence": "HTTP 404"}, {**base, "source_id": "S4", "verdict": "gone", "fact": "c", "outcome": "dead"},
            {**base, "source_id": "S5", "verdict": "pinned"}]
    census.kbcommon.write_csv(str(log), factdiff.LOG_COLS, rows)
    rows[0]["content_date"] = "2031-01-01"
    rows[1]["baseline_utc"] = "2031-01-01T00:00:00Z"
    census.kbcommon.write_csv(str(log), factdiff.LOG_COLS, rows)
    retrieved = {s: "2031-01-02" for s in ("S1", "S2", "S3", "S4", "S5")}
    got = {k: v[1]["bucket"] for k, v in census.factdiff_verdicts(str(log), retrieved).items()}
    assert got == {"S1": "OK", "S2": "OK", "S3": "CHANGED", "S4": "GONE"}
    # compared with a text newer than the last confirmation: left to the census's own checks
    got = {k: v[1]["bucket"] for k, v in census.factdiff_verdicts(str(log), {s: "2030-12-01" for s in retrieved}).items()}
    assert got == {"S3": "CHANGED", "S4": "GONE"}
