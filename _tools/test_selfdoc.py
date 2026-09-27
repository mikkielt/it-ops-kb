"""selfdoc.py tests: which kb docs are behind the files they describe (`python3 _tools/tests.py -k selfdoc`).

TestSelfdocRules   map globs (`*` within a directory, `**` across, `-` never), the map reader, describing().
TestSelfdocInGit   (marker git) a throwaway repo with a map, two docs and the files they describe: a commit to a
                   described file makes its doc stale, editing or committing the doc clears it, --since compares a
                   revision with the working tree, and check reports a missing doc, a dead pattern and an unmapped doc.
"""
import os

import pytest

import selfdoc
from conftest import LEAKY, Repo, requires_git


class TestSelfdocRules:
    def test_globs(self):
        m = selfdoc.matches
        assert m("_tools/*.py", "_tools/rag.py") and not m("_tools/*.py", "_tools/doc2query/x.py")
        assert m(".claude-plugin/**", ".claude-plugin/it-ops-kb-docs/.mcp.json")
        assert m(".claude/skills/*/SKILL.md", ".claude/skills/kb-self/SKILL.md")
        assert m("a?.md", "ab.md") and not m("a?.md", "a/.md")
        assert not m("-", "-") and not m("_tools/rag.py", "_tools/rag.pyc")

    def test_map_and_describing(self, tmp_path):
        os.makedirs(tmp_path / "_self")
        (tmp_path / "_self" / "map.csv").write_text("doc,pattern\n_self/a.md,src/*.py\n_self/a.md,_self/a.md\n_self/b.md,-\n")
        docs = selfdoc.load_map(str(tmp_path))
        assert docs == {"_self/a.md": ["src/*.py", "_self/a.md"], "_self/b.md": ["-"]}
        assert selfdoc.describing(docs, ["src/x.py", "_self/a.md", "other.txt"]) == {"_self/a.md": ["src/x.py"]}

    def test_bad_map(self, tmp_path):
        with pytest.raises(selfdoc.SelfdocError, match="cannot read"):
            selfdoc.load_map(str(tmp_path))
        os.makedirs(tmp_path / "_self")
        (tmp_path / "_self" / "map.csv").write_text("path,glob\nx,y\n")
        with pytest.raises(selfdoc.SelfdocError, match="doc,pattern"):
            selfdoc.load_map(str(tmp_path))


@pytest.mark.git
@requires_git
class TestSelfdocInGit:
    @pytest.fixture
    def repo(self, tmp_path, monkeypatch):
        for k in LEAKY:
            monkeypatch.delenv(k, raising=False)
        r = Repo(tmp_path)
        r.git("init", "-q")
        r.write("_self/map.csv", "doc,pattern\n_self/tools.md,src/*.py\n_self/state.md,-\n")
        r.write("_self/tools.md", "tools\n")
        r.write("_self/state.md", "state\n")
        r.write("src/tool.py", "print(1)\n")
        r.git("add", "-A")
        r.git("commit", "-q", "-m", "init")
        return r

    def test_stale_follows_commits(self, repo):
        root = repo.path
        assert selfdoc.stale(root) == []
        repo.write("src/tool.py", "print(2)\n")
        repo.git("commit", "-qam", "change the tool")
        [(doc, _, hit)] = selfdoc.stale(root)
        assert (doc, hit) == ("_self/tools.md", ["src/tool.py"])
        repo.write("_self/tools.md", "tools, updated\n")
        assert selfdoc.stale(root) == [], "a doc being edited counts as updated"
        repo.git("commit", "-qam", "update the doc")
        assert selfdoc.stale(root) == []
        repo.write("src/new.py", "x\n")  # untracked, described by the same glob
        assert [d for d, _, _ in selfdoc.stale(root)] == ["_self/tools.md"]

    def test_since_compares_with_the_working_tree(self, repo):
        root, base = repo.path, repo.rev("HEAD")
        assert selfdoc.stale(root, since=base) == []
        repo.write("src/tool.py", "print(3)\n")
        assert [(d, h) for d, _, h in selfdoc.stale(root, since=base)] == [("_self/tools.md", ["src/tool.py"])]
        repo.write("_self/tools.md", "tools v3\n")
        assert selfdoc.stale(root, since=base) == []
        with pytest.raises(selfdoc.SelfdocError):
            selfdoc.stale(root, since="no-such-rev")

    def test_self_reviewed_trailer_clears_a_doc(self, repo):
        repo.append("_self/map.csv", "_self/design.md,_self/tools.md\n")  # a doc that describes a reviewed doc
        repo.write("_self/design.md", "design\n")
        repo.git("add", "-A")
        repo.git("commit", "-q", "-m", "design doc")
        root, base = repo.path, repo.rev("HEAD")
        repo.write("src/tool.py", "print(4)\n")
        repo.git("commit", "-qam", "change the tool")
        assert [d for d, _, _ in selfdoc.stale(root)] == ["_self/tools.md"]
        repo.git("commit", "-q", "--allow-empty", "-m", "review\n\nSelf-Reviewed: _self/tools.md, _self/state.md")
        assert selfdoc.stale(root) == [], "a review after the change is the doc's new reference"
        assert selfdoc.stale(root, since=base) == [], "--since counts docs reviewed in REV..HEAD as updated, and a " \
            "reviewed doc is not a changed file (design.md describes tools.md)"
        repo.write("src/tool.py", "print(5)\n")
        repo.git("commit", "-qam", "change it again")
        assert [d for d, _, _ in selfdoc.stale(root)] == ["_self/tools.md"], "a later change needs a new review"

    def test_check(self, repo):
        root = repo.path
        assert selfdoc.check(root) == []
        repo.write("_self/map.csv", "doc,pattern\n_self/tools.md,src/*.py\n_self/tools.md,gone/*.py\n_self/missing.md,src/*.py\n")
        problems = selfdoc.check(root)
        assert "_self/tools.md: pattern gone/*.py matches no file" in problems
        assert "_self/missing.md: the doc does not exist" in problems
        assert any(p.startswith("_self/state.md: no row") for p in problems)

    def test_cli_on_this_repository(self, capsys):
        assert selfdoc.main(["map", "_tools/rag.py"]) == 0
        out = capsys.readouterr().out
        assert "_self/tools.md: _tools/rag.py" in out and "AGENTS.md: _tools/rag.py" in out
        assert selfdoc.main(["stale", "--since", "no-such-rev"]) == 2
