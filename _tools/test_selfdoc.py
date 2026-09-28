"""selfdoc.py tests: which kb docs are behind the files they describe (`python3 _tools/tests.py -k selfdoc`).

TestSelfdocRules   map globs (`*` within a directory, `**` across, `-` never), the map reader, describing().
TestSelfdocInGit   (marker git) a throwaway repo with a map, two docs and the files they describe: a commit to a
                   described file makes its doc stale, editing or committing the doc clears it, --since compares a
                   revision with the working tree, and check reports a missing doc, a dead pattern and an unmapped doc.
"""
import os

import pytest

import selfdoc
from conftest import LEAKY, SELF_REL as S, Repo, requires_git


class TestSelfdocRules:
    def test_globs(self):
        m = selfdoc.matches
        assert m("_tools/*.py", "_tools/rag.py") and not m("_tools/*.py", "_tools/doc2query/x.py")
        assert m(".claude-plugin/**", ".claude-plugin/it-ops-kb-docs/.mcp.json")
        assert m(".claude/skills/*/SKILL.md", ".claude/skills/kb-self/SKILL.md")
        assert m("a?.md", "ab.md") and not m("a?.md", "a/.md")
        assert not m("-", "-") and not m("_tools/rag.py", "_tools/rag.pyc")

    def test_map_and_describing(self, tmp_path):
        os.makedirs(tmp_path / S)
        (tmp_path / S / "map.csv").write_text(f"doc,pattern\n{S}/a.md,src/*.py\n{S}/a.md,{S}/a.md\n{S}/b.md,-\n", encoding="utf-8", newline="\n")
        docs = selfdoc.load_map(str(tmp_path))
        assert docs == {f"{S}/a.md": ["src/*.py", f"{S}/a.md"], f"{S}/b.md": ["-"]}
        assert selfdoc.describing(docs, ["src/x.py", f"{S}/a.md", "other.txt"]) == {f"{S}/a.md": ["src/x.py"]}

    def test_bad_map(self, tmp_path):
        with pytest.raises(selfdoc.SelfdocError, match="cannot read"):
            selfdoc.load_map(str(tmp_path))
        os.makedirs(tmp_path / S)
        (tmp_path / S / "map.csv").write_text("path,glob\nx,y\n", encoding="utf-8", newline="\n")
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
        r.write(f"{S}/map.csv", f"doc,pattern\n{S}/tools.md,src/*.py\n{S}/state.md,-\n")
        r.write(f"{S}/tools.md", "tools\n")
        r.write(f"{S}/state.md", "state\n")
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
        assert (doc, hit) == (f"{S}/tools.md", ["src/tool.py"])
        repo.write(f"{S}/tools.md", "tools, updated\n")
        assert selfdoc.stale(root) == [], "a doc being edited counts as updated"
        repo.git("commit", "-qam", "update the doc")
        assert selfdoc.stale(root) == []
        repo.write("src/new.py", "x\n")  # untracked, described by the same glob
        assert [d for d, _, _ in selfdoc.stale(root)] == [f"{S}/tools.md"]

    def test_since_compares_with_the_working_tree(self, repo):
        root, base = repo.path, repo.rev("HEAD")
        assert selfdoc.stale(root, since=base) == []
        repo.write("src/tool.py", "print(3)\n")
        assert [(d, h) for d, _, h in selfdoc.stale(root, since=base)] == [(f"{S}/tools.md", ["src/tool.py"])]
        repo.write(f"{S}/tools.md", "tools v3\n")
        assert selfdoc.stale(root, since=base) == []
        with pytest.raises(selfdoc.SelfdocError):
            selfdoc.stale(root, since="no-such-rev")

    def test_self_reviewed_trailer_clears_a_doc(self, repo):
        repo.append(f"{S}/map.csv", f"{S}/design.md,{S}/tools.md\n")  # a doc that describes a reviewed doc
        repo.write(f"{S}/design.md", "design\n")
        repo.git("add", "-A")
        repo.git("commit", "-q", "-m", "design doc")
        root, base = repo.path, repo.rev("HEAD")
        repo.write("src/tool.py", "print(4)\n")
        repo.git("commit", "-qam", "change the tool")
        assert [d for d, _, _ in selfdoc.stale(root)] == [f"{S}/tools.md"]
        repo.git("commit", "-q", "--allow-empty", "-m", f"review\n\nSelf-Reviewed: {S}/tools.md, {S}/state.md")
        assert selfdoc.stale(root) == [], "a review after the change is the doc's new reference"
        assert selfdoc.stale(root, since=base) == [], "--since counts docs reviewed in REV..HEAD as updated, and a " \
            "reviewed doc is not a changed file (design.md describes tools.md)"
        repo.write("src/tool.py", "print(5)\n")
        repo.git("commit", "-qam", "change it again")
        assert [d for d, _, _ in selfdoc.stale(root)] == [f"{S}/tools.md"], "a later change needs a new review"

    def test_check(self, repo):
        root = repo.path
        assert selfdoc.check(root) == []
        repo.write(f"{S}/map.csv", f"doc,pattern\n{S}/tools.md,src/*.py\n{S}/tools.md,gone/*.py\n{S}/missing.md,src/*.py\n")
        problems = selfdoc.check(root)
        assert f"{S}/tools.md: pattern gone/*.py matches no file" in problems
        assert f"{S}/missing.md: the doc does not exist" in problems
        assert any(p.startswith(f"{S}/state.md: no row") for p in problems)

    def test_cli_on_this_repository(self, capsys):
        assert selfdoc.main(["map", "_tools/rag.py"]) == 0
        out = capsys.readouterr().out
        assert f"{S}/tools.md: _tools/rag.py" in out and "AGENTS.md: _tools/rag.py" in out
        assert selfdoc.main(["stale", "--since", "no-such-rev"]) == 2
