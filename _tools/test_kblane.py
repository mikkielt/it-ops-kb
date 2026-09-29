"""Lane tests: `python3 _tools/tests.py -k TestLanes`.

  TestLanes  the path classifier's boundaries (kb roots, the query log, backlog items, kb/_self process docs, the two
             tool data files, everything else code), every path ql_deliver.auto_kinds accepts and every
             kbgit.MECHANICAL path content, and (marker git) planted commits in a throwaway repository: a
             content-only, a code-only, a mixed, a merge and a backlog-item commit, and a root commit; `kbgit.py lane`
             prints them. Planted failures: a code path in a content commit and a content path in a code one flip the lane.
"""
import ast, re
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
