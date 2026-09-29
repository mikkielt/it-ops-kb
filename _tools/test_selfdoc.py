"""selfdoc.py tests: which kb docs are behind the files they describe (`python3 _tools/tests.py -k selfdoc`).

TestSelfdocRules   map globs (`*` within a directory, `**` across, `-` never), the map reader, describing().
TestSelfdocSection section DOC HEADING: the section down to the next heading of its level, subsections kept, fenced
                   code and front matter never headings, case-insensitive, `##` pins the level, no match exits 1.
TestSelfdocToolsMap map-tools: modules, classes, defs, methods and tests with file:line and the first docstring line,
                   FILE narrows it, a mapped name missing from the code (or a def missing from the map) fails
                   check_map, and every _tools file of this repository parses and holds.
TestSelfdocInGit   (marker git) a throwaway repo with a map, two docs and the files they describe: a commit to a
                   described file makes its doc stale, editing or committing the doc clears it, --since compares a
                   revision with the working tree, and check reports a missing doc, a dead pattern and an unmapped doc.
"""
import functools, os

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


DOC = """\
---
name: demo
# a front matter comment, not a heading
---

# Title

intro

## Alpha

alpha text
```
# not a heading, in a fence
## Alpha
```

### Alpha detail   ##

detail text

## Beta  Section

beta text

~~~
```
## still fenced
~~~

## alpha

second alpha
"""


class TestSelfdocSection:
    @pytest.fixture
    def root(self, tmp_path):
        os.makedirs(tmp_path / S)
        (tmp_path / S / "demo.md").write_text(DOC, encoding="utf-8", newline="\n")
        return str(tmp_path)

    def test_selfdoc_section_runs_to_the_next_heading_of_its_level(self, root):
        found, _ = selfdoc.section("demo", "Beta Section", root)
        assert found == [[(22, "## Beta  Section"), (23, ""), (24, "beta text"), (25, ""), (26, "~~~"), (27, "```"),
                          (28, "## still fenced"), (29, "~~~")]], "fenced lines belong to the section and never end it"

    def test_selfdoc_section_keeps_subsections_and_ignores_fences_and_front_matter(self, root):
        found, heads = selfdoc.section(f"{S}/demo.md", "alpha", root)
        assert [(b[0][0], b[-1][0]) for b in found] == [(10, 20), (31, 33)], "both headings of that text, any case"
        assert (18, "### Alpha detail   ##") in found[0], "a subsection is part of its section"
        assert (15, "## Alpha") in found[0] and (14, "# not a heading, in a fence") in found[0]
        assert heads == ["# Title", "## Alpha", "### Alpha detail", "## Beta  Section", "## alpha"]

    def test_selfdoc_section_pins_the_level(self, root):
        found, _ = selfdoc.section("demo", "### alpha detail", root)
        assert [(b[0][0], b[-1][0]) for b in found] == [(18, 20)], "a higher heading (## Beta) ends a ### section"
        assert selfdoc.section("demo", "#### alpha detail", root)[0] == []
        assert [b[0][0] for b in selfdoc.section("demo", "## Alpha", root)[0]] == [10, 31]

    def test_selfdoc_section_no_match_names_the_headings(self, root):
        found, heads = selfdoc.section("demo", "# a front matter comment, not a heading", root)
        assert found == [] and heads[0] == "# Title", "front matter comments are not headings"
        found, heads = selfdoc.section("demo", "Gamma", root)
        assert found == [] and "## Beta  Section" in heads

    def test_selfdoc_section_bad_doc_is_an_error(self, root):
        with pytest.raises(selfdoc.SelfdocError, match="no such doc"):
            selfdoc.section("nope", "x", root)

    def test_selfdoc_section_refuses_a_file_outside_the_repository(self, root, tmp_path_factory):
        """The planted failure: an absolute path or a `../` path to a file outside the repository is no doc."""
        outside = tmp_path_factory.mktemp("outside") / "secret.md"
        outside.write_text("# Host Database\nvalue\n", encoding="utf-8", newline="\n")
        for name in (str(outside), os.path.relpath(outside, root)):
            with pytest.raises(selfdoc.SelfdocError, match="no such doc"):
                selfdoc.section(name, "Host Database", root)
        assert selfdoc.section(os.path.join(root, S, "demo.md"), "alpha", root)[0], "an absolute path inside still works"

    def test_selfdoc_section_ignores_backticks_in_headings(self, root):
        doc = os.path.join(root, S, "ticks.md")
        with open(doc, "w", encoding="utf-8", newline="\n") as f:
            f.write("# T\n\n## 6. Roots beside `kb/public`\n\ntext\n")
        for heading in ("6. Roots beside kb/public", "6. Roots beside `kb/public`"):
            assert [b[0][0] for b in selfdoc.section("ticks", heading, root)[0]] == [3], heading

    def test_selfdoc_section_cli_no_match_exits_1_and_lists_headings(self, capsys):
        """The planted failure: a heading the doc does not have."""
        assert selfdoc.main(["section", f"{S}/backlog.md", "No Such Heading"]) == 1
        out = capsys.readouterr().out
        assert "NO SECTION 'No Such Heading'" in out and "  ## Definition of done" in out

    def test_selfdoc_section_cli_prints_line_numbers(self, capsys):
        assert selfdoc.main(["section", "backlog", "definition of DONE"]) == 0
        out = capsys.readouterr().out.splitlines()
        assert out[0].startswith("backlog:") and out[1].endswith(": ## Definition of done") and out[1].split(":")[0].isdigit()
        assert not any("## Working on items" in ln for ln in out)
        assert selfdoc.main(["section", "nope", "x"]) == 2

SAMPLE = '''\
"""Sample tool: does one thing.

More about it."""
import sys


def top(a):
    """Top function.

    Long text."""
    def inner():
        """Not listed: a detail of top."""
    return inner


@staticmethod
def decorated():
    pass


async def fetch():
    """Async one."""


class Box:
    """A box."""

    def size(self):
        """Its size."""

    class Lid:
        def close(self):
            pass


if sys.platform == "win32":
    def only_here():
        pass
'''
TEST_SAMPLE = '''\
"""Tests of sample."""


def helper():
    pass


class TestBox:
    def test_size(self):
        """Size is right."""

    def check_helper(self):
        pass


def test_top():
    pass
'''


class TestSelfdocToolsMap:
    @pytest.fixture
    def root(self, tmp_path):
        tools = tmp_path / "_tools"
        (tools / "__pycache__").mkdir(parents=True)
        (tools / "sample.py").write_text(SAMPLE, encoding="utf-8", newline="\n")
        (tools / "test_sample.py").write_text(TEST_SAMPLE, encoding="utf-8", newline="\n")
        (tools / "broken.py").write_text("def f(:\n", encoding="utf-8", newline="\n")
        (tools / "__pycache__" / "cached.py").write_text("def hidden(): pass\n", encoding="utf-8", newline="\n")
        return tmp_path

    def test_tools_map_lists_symbols_with_line_kind_and_first_docstring_line(self, root):
        assert selfdoc.map_tools(root=root) == [
            "_tools/broken.py:1 unparsed broken — SyntaxError",
            "_tools/sample.py:1 module sample — Sample tool: does one thing.",
            "_tools/sample.py:7 def top — Top function.",
            "_tools/sample.py:17 def decorated",
            "_tools/sample.py:21 async fetch — Async one.",
            "_tools/sample.py:25 class Box — A box.",
            "_tools/sample.py:28 method Box.size — Its size.",
            "_tools/sample.py:31 class Box.Lid",
            "_tools/sample.py:32 method Box.Lid.close",
            "_tools/sample.py:37 def only_here",
            "_tools/test_sample.py:1 module test_sample — Tests of sample.",
            "_tools/test_sample.py:4 def helper",
            "_tools/test_sample.py:8 class TestBox",
            "_tools/test_sample.py:9 test TestBox.test_size — Size is right.",
            "_tools/test_sample.py:12 method TestBox.check_helper",
            "_tools/test_sample.py:16 test test_top",
        ], "nested defs are left out, a decorated def is at its def line, caches are skipped, a broken file is one line"

    def test_tools_map_file_narrows_and_names_resolve(self, root):
        only = ["_tools/test_sample.py:1 module test_sample — Tests of sample."]
        for name in ("test_sample", "test_sample.py", "_tools/test_sample.py", str(root / "_tools" / "test_sample.py")):
            assert selfdoc.map_tools(name, root)[0] == only[0], name
            assert all(ln.startswith("_tools/test_sample.py:") for ln in selfdoc.map_tools(name, root))
        for bad in ("nope", "sample.txt", "../outside", "_tools"):
            with pytest.raises(selfdoc.SelfdocError, match="no such tool file"):
                selfdoc.map_tools(bad, root)

    def test_tools_map_long_docstring_line_is_cut(self, tmp_path):
        os.makedirs(tmp_path / "_tools")
        (tmp_path / "_tools" / "long.py").write_text('def f():\n    """' + "word " * 60 + '"""\n', encoding="utf-8", newline="\n")
        line = selfdoc.map_tools("long", tmp_path)[1]
        assert line.endswith("…") and len(line.split(" — ", 1)[1]) == selfdoc.DOC_MAX

    def test_tools_map_every_mapped_name_is_in_the_code(self, root):
        lines = selfdoc.map_tools(root=root)
        assert selfdoc.check_map(lines, root) == []

    def test_tools_map_a_name_missing_from_the_code_fails_the_check(self, root):
        """The planted failure: a map line naming a symbol the code does not have, or at the wrong line."""
        lines = selfdoc.map_tools(root=root)
        renamed = [ln.replace("def top", "def gone") for ln in lines]
        assert selfdoc.check_map(renamed, root) == ["_tools/sample.py:7: `gone` (def) is not at that line",
                                                    "_tools/sample.py:7: `top` is in the code and not in the map"]
        moved = [ln.replace("sample.py:28 method", "sample.py:29 method") for ln in lines]
        assert any(p.startswith("_tools/sample.py:29: `Box.size`") for p in selfdoc.check_map(moved, root))
        assert selfdoc.check_map([ln.replace("class Box ", "def Box ") for ln in lines], root), "a class is not a def"
        assert selfdoc.check_map(lines + ["_tools/sample.py:99 def late"], root) == [
            "_tools/sample.py:99: past the end of the file (mapped: late)"]
        assert selfdoc.check_map(lines + ["_tools/absent.py:3 def x"], root) == ["_tools/absent.py: no such file (mapped: x)"]
        assert selfdoc.check_map(lines + ["garbage"], root) == ["not a map line: garbage"]

    def test_tools_map_a_symbol_left_out_of_the_map_fails_the_check(self, root):
        lines = [ln for ln in selfdoc.map_tools(root=root) if " def top " not in ln]
        assert selfdoc.check_map(lines, root) == ["_tools/sample.py:7: `top` is in the code and not in the map"]

    def test_tools_map_cli_prints_lines_and_a_count(self, root, capsys, monkeypatch):
        monkeypatch.setattr(selfdoc, "map_tools", functools.partial(selfdoc.map_tools, root=root))
        assert selfdoc.main(["map-tools", "sample"]) == 0
        out = capsys.readouterr().out.splitlines()
        assert out[0].startswith("_tools/sample.py:1 module sample") and out[-1] == "files=1 symbols=8"

    def test_tools_map_cli_bad_file_exits_2(self, capsys):
        assert selfdoc.main(["map-tools", "no-such-tool"]) == 2
        assert "no such tool file" in capsys.readouterr().err

    def test_tools_map_this_repository_parses_and_holds(self):
        """Every _tools Python file is mapped, none unparsed, and each line is at its def or class in the code."""
        lines = selfdoc.map_tools()
        files = {ln.split(":", 1)[0] for ln in lines}
        assert files == {p.relative_to(selfdoc.KB).as_posix() for p in selfdoc.tool_files()}
        assert "_tools/selfdoc.py:1 module selfdoc" in "\n".join(ln.split(" — ")[0] for ln in lines)
        assert not [ln for ln in lines if " unparsed " in ln.split(" — ")[0]]
        assert selfdoc.check_map(lines) == []
        assert any(ln.split(" — ")[0].endswith(" def check_map") for ln in lines)

    def test_tools_map_this_repository_lists_every_test_function(self):
        tests = {ln.split(" ")[0] for ln in selfdoc.map_tools() if ln.split(" ")[1] == "test"}
        found = set()
        for p in selfdoc.tool_files():
            if p.name.startswith("test_"):
                for no, _, name in selfdoc.def_tokens(p.read_text(encoding="utf-8")):
                    if name.startswith("test_"):  # read from the tokens, so a `def test_x` inside a string does not count
                        found.add(f"{p.relative_to(selfdoc.KB).as_posix()}:{no}")
        assert tests == found and found

    def test_tools_map_this_repository_tampered_map_fails(self):
        lines = selfdoc.map_tools("selfdoc")
        tampered = [ln.replace(" def check_map", " def check_map_gone") for ln in lines]
        assert selfdoc.check_map(tampered) and not selfdoc.check_map(lines)


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
