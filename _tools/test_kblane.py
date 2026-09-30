"""Lane tests: `python3 _tools/tests.py -k TestLanes` and `-k TestCheckLanes`.

  TestLanes  the path classifier's boundaries (kb roots, the query log, backlog items, kb/_self process docs, the two
             tool data files, everything else code), every path ql_deliver.auto_kinds accepts and every
             kbgit.MECHANICAL path content, and (marker git) planted commits in a throwaway repository: a
             content-only, a code-only, a mixed, a merge and a backlog-item commit, and a root commit; `kbgit.py lane`
             prints them. Planted failures: a code path in a content commit and a content path in a code one flip the lane.
  TestCheckLanes  check_lanes and `kbgit.py check-lanes` in a throwaway repository against an injected opener and a stub
             forge on loopback: a direct code commit listed, a merged one (GitLab merge request, GitHub pull request
             with merged_at) passing, an unmerged pull request listed, a merge commit judged by the commits it brings
             in, an API failure (status, body, missing variables, no forge) exiting 2 and never passing, and the
             pre-push hook refusing a code-lane commit for the integration main with no API call. The fixture drops
             every forge variable a CI job sets and fails any request off loopback (planted: a GitLab job's variables).
"""
import argparse, ast, io, json, re, threading, urllib.error, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

import kblane, kbgit, ql_deliver
from conftest import Repo, requires_git

HERE = Path(__file__).resolve().parent


def commit(repo, files, msg):
    for rel, text in files.items():
        repo.write(rel, text)
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", msg)
    return repo.rev("HEAD")


def lane_of(repo, rev):
    (short, lane, code), = kblane.commit_lanes(repo.path, kblane.spec_of(rev))
    return lane, code


class TestLanes:
    CONTENT = ["kb/public/auth/kerberos.md", "kb/public/_sources.csv", "kb/team/_retrieval/aliases.csv",
               "kb/_querylog/runs/x.json", "kb/_self/backlog/TK-abcdefgh.json", "kb/_self/git.md",
               "_tools/aliases.csv", "_tools/lint_baseline.txt"]
    CODE = ["_tools/kbgit.py", "_tools/kblane.py", "kb/_self/map.csv", "kb/_self/sub/x.md", "kb/_self/backlog/README.md",
            "kb/_other.md", "kb/_x/y.md", ".claude/settings.json", ".githooks/pre-push", ".gitlab-ci.yml", "AGENTS.md",
            "README.md", "_tools/aliases.csv.bak", "kb/public"]

    def test_boundaries(self):
        assert [p for p in self.CONTENT if kblane.path_lane(p) != "content"] == []
        assert [p for p in self.CODE if kblane.path_lane(p) != "code"] == []

    def test_writers_and_mechanical_paths_are_content(self):
        auto = ["kb/_querylog/runs/x.json", "kb/public/_retrieval/lookup_eval.csv", "kb/_self/backlog/BG-abcdefgh.json",
                "_tools/aliases.csv", "kb/public/_retrieval/aliases.csv", "kb/public/_retrieval/doc2query/expansions.csv",
                "kb/public/_gaps.md", "kb/public/_sources.csv", "kb/public/_conflicts.md", "kb/public/_coverage.csv",
                "kb/public/auth/kerberos.md"]
        for p in auto:
            ql_deliver.auto_kinds([p])  # raises when the writers do not accept it
            assert kblane.path_lane(p) == "content", p
        assert kbgit.MECHANICAL
        assert [p for p in kbgit.MECHANICAL if kblane.path_lane(p) != "content"] == []

    def test_lane_of_paths(self):
        assert kblane.paths_lane([]) == ("content", [])
        assert kblane.paths_lane(["kb/public/a/b.md", "_tools/x.py", "kb/_self/map.csv"]) == \
            ("code", ["_tools/x.py", "kb/_self/map.csv"])

    def test_imports_neither_kbgit_nor_backlog(self):
        tree = ast.parse((HERE / "kblane.py").read_text(encoding="utf-8"))
        names = {n.name.split(".")[0] for x in ast.walk(tree) if isinstance(x, ast.Import) for n in x.names}
        names |= {x.module.split(".")[0] for x in ast.walk(tree) if isinstance(x, ast.ImportFrom) and x.module}
        assert not names & {"kbgit", "backlog", "kbcommon", "ql_deliver"}

    @pytest.mark.git
    @requires_git
    def test_planted_commits(self, tmp_path):
        r = Repo(tmp_path)
        r.git("init", "-q", "-b", "main")
        root = commit(r, {"README.md": "x\n"}, "root")
        assert lane_of(r, root) == ("code", ["README.md"])  # a root commit against the empty tree
        content = commit(r, {"kb/public/a/b.md": "a\n", "kb/_self/git.md": "g\n"}, "content")
        assert lane_of(r, content) == ("content", [])
        code = commit(r, {"_tools/x.py": "1\n"}, "code")
        assert lane_of(r, code) == ("code", ["_tools/x.py"])
        mixed = commit(r, {"kb/public/a/c.md": "c\n", "kb/_self/map.csv": "d\n"}, "mixed")
        assert lane_of(r, mixed) == ("code", ["kb/_self/map.csv"])
        item = commit(r, {"kb/_self/backlog/TK-abcdefgh.json": "{}\n"}, "item")
        assert lane_of(r, item) == ("content", [])
        # a merge: judged against its first parent
        r.git("checkout", "-q", "-b", "side", root)
        commit(r, {"_tools/side.py": "s\n"}, "side code")
        r.git("checkout", "-q", "main")
        r.git("merge", "-q", "--no-ff", "-m", "merge code", "side")
        assert lane_of(r, "HEAD") == ("code", ["_tools/side.py"])
        r.git("checkout", "-q", "-b", "cside", "main")
        commit(r, {"kb/public/a/d.md": "d\n"}, "side content")
        r.git("checkout", "-q", "main")
        commit(r, {"kb/public/z.md": "z\n"}, "main content")
        r.git("merge", "-q", "--no-ff", "-m", "merge content", "cside")
        assert lane_of(r, "HEAD") == ("content", [])  # a merge whose first-parent diff has no code path
        # planted failures: the lane follows the paths, both ways
        assert lane_of(r, content)[0] != lane_of(r, code)[0]
        bad = commit(r, {"kb/public/a/e.md": "e\n", "_tools/aliases.csv.bak": "z\n"}, "content plus one code file")
        assert lane_of(r, bad) == ("code", ["_tools/aliases.csv.bak"])
        # the range form, oldest first, and the CLI
        rows = kblane.commit_lanes(r.path, [f"{root}..{item}"])
        assert [x[1] for x in rows] == ["content", "code", "code", "content"]
        assert kblane.commit_lanes(r.path, ["no-such-rev^!"]) is None

    @pytest.mark.git
    @requires_git
    def test_cli_prints_lane(self):
        import subprocess, sys
        p = subprocess.run([sys.executable, str(HERE / "kbgit.py"), "lane", "HEAD"], capture_output=True, text=True,
                           encoding="utf-8")
        assert p.returncode == 0 and re.search(r"\b(content|code)\b", p.stdout), p.stdout + p.stderr
        bad = subprocess.run([sys.executable, str(HERE / "kbgit.py"), "lane", "no-such-rev"], capture_output=True,
                             text=True, encoding="utf-8")
        assert bad.returncode == 2


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def opener_of(answers, seen=None):
    """An injected opener: answers[sha] is a list (the JSON body) or an exception to raise; every request is noted."""
    def opener(req):
        if seen is not None:
            seen.append(req)
        sha = req.full_url.split("/commits/")[1].split("/")[0]
        got = answers.get(sha, [])
        if isinstance(got, Exception):
            raise got
        return Resp(got if isinstance(got, bytes) else json.dumps(got).encode())
    return opener


class Stub(BaseHTTPRequestHandler):
    """A stub GitLab: the commit named in `answers` gets its list or status; the JOB-TOKEN header is noted."""
    answers, seen = {}, []

    def do_GET(self):
        type(self).seen.append((self.path, self.headers.get("JOB-TOKEN")))
        sha = self.path.split("/commits/")[1].split("/")[0]
        got = type(self).answers.get(sha, [])
        body = json.dumps(got if isinstance(got, list) else []).encode()
        self.send_response(got if isinstance(got, int) else 200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


# Every variable kblane.forge_associate reads: a GitLab or GitHub job sets them, and a test that kept them would ask
# the real forge (a Windows container without its CA got an SSL error instead of the missing-variables message).
FORGE_VARS = ("GITLAB_CI", "CI_API_V4_URL", "CI_PROJECT_ID", "CI_JOB_TOKEN",
              "GITHUB_ACTIONS", "GITHUB_API_URL", "GITHUB_REPOSITORY", "GITHUB_TOKEN")


class NetworkReached(AssertionError):
    pass


def loopback_only(urlopen):
    """urlopen for the stub forge on 127.0.0.1 only: a request to any other host fails the test (not a ForgeError,
    which the code under test would turn into exit 2 and hide)."""
    def guarded(req, *a, **kw):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if urllib.parse.urlsplit(url).hostname not in ("127.0.0.1", "localhost"):
            raise NetworkReached(f"a test reached the network: {url}")
        return urlopen(req, *a, **kw)
    return guarded


@pytest.mark.git
@requires_git
class TestCheckLanes:
    @pytest.fixture
    def repo(self, tmp_path, monkeypatch):
        (tmp_path / "origin.git").mkdir()
        Repo(tmp_path / "origin.git").git("init", "-q", "--bare", "-b", "main")
        (tmp_path / "w").mkdir()
        r = Repo(tmp_path / "w")
        r.git("init", "-q", "-b", "main")
        r.base = commit(r, {"kb/public/a.md": "a\n"}, "base")
        r.git("remote", "add", "origin", str(tmp_path / "origin.git"))
        r.git("push", "-q", "origin", "main")
        r.git("fetch", "-q", "origin")
        r.code = commit(r, {"_tools/x.py": "1\n"}, "code")
        r.content = commit(r, {"kb/public/b.md": "b\n"}, "content")
        monkeypatch.setattr(kbgit, "KB", r.path)
        monkeypatch.setattr(kbgit, "default_range", lambda: f"{r.base}..HEAD")
        for k in ("CI_COMMIT_SHA", "CI_COMMIT_BEFORE_SHA", *FORGE_VARS):
            monkeypatch.delenv(k, raising=False)
        monkeypatch.setattr(kblane.urllib.request, "urlopen", loopback_only(kblane.urllib.request.urlopen))
        return r

    def run(self, argv, capsys):
        forge = argv[argv.index("--forge") + 1] if "--forge" in argv else "auto"
        rng = next((x for x in argv if x != forge and x != "--forge"), None)
        rc = kbgit.cmd_check_lanes(argparse.Namespace(range=rng, forge=forge))
        return rc, capsys.readouterr().out

    def lanes(self, repo, assoc):
        return kblane.check_lanes(repo.path, [f"{repo.base}..HEAD"], assoc)

    def test_direct_code_commit_is_listed_and_content_is_not(self, repo, capsys):
        rc, out = self.run(["--forge", "none"], capsys)
        assert rc == 1 and repo.code[:7] in out and "_tools/x.py" in out and repo.content[:7] not in out
        assert "unmerged_code_commits=1" in out
        # planted failure: a range of content commits alone passes
        rc, out = self.run([f"{repo.code}..HEAD", "--forge", "none"], capsys)
        assert rc == 0 and "unmerged_code_commits=0" in out

    def test_a_merged_commit_passes_and_an_unmerged_one_is_listed(self, repo):
        seen = []
        merged = kblane.gitlab_associate(
            {"CI_API_V4_URL": "https://gl.example.com/api/v4/", "CI_PROJECT_ID": "42", "CI_JOB_TOKEN": "tok"},
            opener_of({repo.code: [{"iid": 3, "state": "merged"}]}, seen))
        assert self.lanes(repo, merged) == []
        req = seen[0]
        assert req.full_url == f"https://gl.example.com/api/v4/projects/42/repository/commits/{repo.code}/merge_requests?state=merged"
        assert req.get_header("Job-token") == "tok"
        opened = kblane.gitlab_associate(
            {"CI_API_V4_URL": "https://gl.example.com/api/v4", "CI_PROJECT_ID": "42", "CI_JOB_TOKEN": "tok"},
            opener_of({repo.code: [{"iid": 3, "state": "opened"}]}))
        assert [s for s, _ in self.lanes(repo, opened)] == [repo.code[:7]]
        assert self.lanes(repo, kblane.forge_associate("none", {})) == self.lanes(repo, lambda sha: False)

    def test_github_counts_only_a_merged_pull_request(self, repo):
        env = {"GITHUB_API_URL": "https://api.example.com", "GITHUB_REPOSITORY": "o/r", "GITHUB_TOKEN": "t"}
        seen = []
        assert self.lanes(repo, kblane.github_associate(env, opener_of({repo.code: [{"merged_at": "2026-01-01T00:00:00Z"}]}, seen))) == []
        assert seen[0].full_url == f"https://api.example.com/repos/o/r/commits/{repo.code}/pulls"
        assert seen[0].get_header("Authorization") == "Bearer t"
        assert len(self.lanes(repo, kblane.github_associate(env, opener_of({repo.code: [{"merged_at": None}]})))) == 1

    def test_a_merge_commit_is_judged_by_the_commits_it_brings_in(self, repo):
        repo.git("checkout", "-q", "-b", "side", repo.base)
        side = commit(repo, {"_tools/side.py": "s\n"}, "side code")
        repo.git("checkout", "-q", "main")
        repo.git("merge", "-q", "--no-ff", "-m", "merge side", "side")
        merge = repo.rev("HEAD")
        asked = []

        def assoc(sha):
            asked.append(sha)
            return sha == side or sha == repo.code
        assert self.lanes(repo, assoc) == []
        assert merge not in asked and side in asked  # the merge commit is not judged, its side is
        # planted failure: the side commit unmerged is listed, the merge commit is still not
        rows = self.lanes(repo, lambda sha: sha == repo.code)
        assert [c for c, _ in rows] == [side[:7]]

    def test_an_api_error_exits_2_and_never_passes(self, repo, capsys, monkeypatch):
        for err in (urllib.error.HTTPError("u", 500, "boom", {}, None), urllib.error.URLError("down"), OSError("x"),
                    b"not json", b"{}"):
            assoc = kblane.gitlab_associate({"CI_API_V4_URL": "http://h/api", "CI_PROJECT_ID": "1", "CI_JOB_TOKEN": "t"},
                                            opener_of({repo.code: err}))
            with pytest.raises(kblane.ForgeError):
                self.lanes(repo, assoc)
        with pytest.raises(kblane.ForgeError):
            kblane.gitlab_associate({"CI_API_V4_URL": "http://h"})
        rc, out = self.run([], capsys)  # no CI variables: no forge to ask
        assert rc == 2 and "nothing passes" in out
        monkeypatch.setenv("GITLAB_CI", "true")
        rc, out = self.run([], capsys)  # GitLab CI without its API variables
        assert rc == 2 and "CI_JOB_TOKEN" in out
        rc, out = self.run(["no-such-rev", "--forge", "none"], capsys)
        assert rc == 2

    def test_a_ci_job_leaves_no_forge_variable_and_reaches_no_network(self, repo, capsys, monkeypatch):
        """The fixture removes every variable the forge lookup reads (the names come from kblane's own
        missing-variables errors), and its guard fails a test that would ask a real forge. Planted: a GitLab job's
        variables set after the fixture make check-lanes call out, and the guard stops it."""
        for forge in ("gitlab", "github"):
            with pytest.raises(kblane.ForgeError) as e:
                kblane.forge_associate(forge, {})
            needed = str(e.value).removeprefix("missing ").split(", ")
            assert needed and set(needed) <= set(FORGE_VARS), needed
        for k, v in (("GITLAB_CI", "true"), ("CI_API_V4_URL", "https://gitlab.example.com/api/v4"),
                     ("CI_PROJECT_ID", "1"), ("CI_JOB_TOKEN", "t")):
            monkeypatch.setenv(k, v)
        with pytest.raises(NetworkReached, match="gitlab.example.com"):
            self.run([], capsys)

    def test_a_stub_forge_on_loopback(self, repo, capsys, monkeypatch):
        Stub.answers, Stub.seen = {repo.code: [{"state": "merged"}]}, []
        srv = HTTPServer(("127.0.0.1", 0), Stub)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            for k, v in (("GITLAB_CI", "true"), ("CI_API_V4_URL", f"http://127.0.0.1:{srv.server_port}/api/v4"),
                         ("CI_PROJECT_ID", "7"), ("CI_JOB_TOKEN", "secret")):
                monkeypatch.setenv(k, v)
            rc, out = self.run([], capsys)
            assert rc == 0 and "unmerged_code_commits=0" in out
            assert Stub.seen == [(f"/api/v4/projects/7/repository/commits/{repo.code}/merge_requests?state=merged", "secret")]
            Stub.answers = {repo.code: []}  # planted: nothing merged introduced it
            rc, out = self.run([], capsys)
            assert rc == 1 and repo.code[:7] in out
            Stub.answers = {repo.code: 500}  # planted: the API fails
            rc, out = self.run([], capsys)
            assert rc == 2 and "unmerged_code_commits" not in out
        finally:
            srv.shutdown()
            srv.server_close()

    def hook(self, repo, capsys, remote_ref, local, remote_sha=None, remote="origin", monkeypatch=None):
        rc = kbgit.hook_pre_push([remote], f"refs/heads/main {local} {remote_ref} {remote_sha or '0' * 40}\n")
        return rc, capsys.readouterr().err

    def test_pre_push_refuses_a_code_lane_commit_for_main(self, repo, capsys, monkeypatch):
        monkeypatch.setenv("KB_GATE_DONE", "1")  # sync's own push: the gate is skipped, the lane refusal is not
        monkeypatch.setattr(kblane, "urllib", None)  # any API call would fail loudly: the hook makes none
        head = repo.rev("HEAD")
        rc, err = self.hook(repo, capsys, "refs/heads/main", head)  # a new ref
        assert rc == 1 and repo.code[:7] in err and "_tools/x.py" in err and "sync --push" in err
        rc, err = self.hook(repo, capsys, "refs/heads/main", head, repo.base)
        assert rc == 1 and repo.code[:7] in err
        # planted failures: content only, another branch, another remote and a delete are not refused
        rc, _ = self.hook(repo, capsys, "refs/heads/main", head, repo.code)
        assert rc == 0
        rc, _ = self.hook(repo, capsys, "refs/heads/code/TK-x", head, repo.base)
        assert rc == 0
        rc, _ = self.hook(repo, capsys, "refs/heads/main", head, repo.base, remote="other")
        assert rc == 0
        rc, _ = self.hook(repo, capsys, "refs/heads/main", "0" * 40, repo.base)
        assert rc == 0
        # a code commit the remote already has is not new
        repo.git("push", "-q", "origin", "HEAD:main")
        repo.git("fetch", "-q", "origin")
        rc, _ = self.hook(repo, capsys, "refs/heads/main", head)
        assert rc == 0
