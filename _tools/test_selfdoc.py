"""selfdoc.py tests: which kb docs are behind the files they describe (`python3 _tools/tests.py -k selfdoc`).

TestSelfdocRules   map globs (`*` within a directory, `**` across, `-` never), the map reader, describing().
TestSelfdocSection section DOC HEADING: the section down to the next heading of its level, subsections kept, fenced
                   code and front matter never headings, case-insensitive, `##` pins the level, no match exits 1;
                   several DOC HEADING pairs print in order in one call, a missing one exits 1, the rest still print;
                   every section command the skills and kb-worker.md name exits 0 and holds no backtick or `$(`
                   (read differently by Bash and PowerShell) (`-k skill_section_headings`).
TestSelfdocToolsMap map-tools: modules, classes, defs, methods and tests with file:line and the first docstring line,
                   FILE narrows it, a mapped name missing from the code (or a def missing from the map) fails
                   check_map, and every _tools file of this repository parses and holds.
TestSelfdocInGit   (marker git) a throwaway repo with a map, two docs and the files they describe: a commit to a
                   described file makes its doc stale, editing or committing the doc clears it, --since compares a
                   revision with the working tree, and check reports a missing doc, a dead pattern and an unmapped doc;
                   the gate judges the pushed range, so backlog-item and query-log commits need no Self-Reviewed
                   trailer while code without its doc update still fails (`-k selfdoc_range_review`); an item's
                   check `stale --work ID` fails only on a doc its own commits left stale, never on another
                   item's (`-k foreign_stale_doc`).
"""
import functools, glob, os, pathlib, re, shlex

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

    def test_selfdoc_sections_several_pairs_print_in_order(self, root, capsys):
        assert selfdoc.print_sections([("demo", "Beta Section"), (f"{S}/demo.md", "### alpha detail")], root) == 0
        out = capsys.readouterr().out.splitlines()
        assert out[0] == "demo:22-29" and out[1] == "22: ## Beta  Section" and out[8] == "29: ~~~"
        assert out[9] == "" and out[10] == f"{S}/demo.md:18-20", "a blank line, then the next pair's section"
        assert out[11] == "18: ### Alpha detail   ##" and len(out) == 14

    def test_selfdoc_sections_a_missing_heading_exits_1_and_the_others_still_print(self, root, capsys):
        """The planted failure: one heading of three matches nothing."""
        pairs = [("demo", "Beta Section"), ("demo", "Gamma"), ("demo", "### alpha detail")]
        assert selfdoc.print_sections(pairs, root) == 1
        out = capsys.readouterr().out
        assert "NO SECTION 'Gamma' in demo; headings:" in out and "  ## Beta  Section" in out
        assert "22: ## Beta  Section" in out and "18: ### Alpha detail   ##" in out, "the matched pairs still print"

    def test_selfdoc_sections_cli_pairs(self, capsys):
        assert selfdoc.main(["section", "backlog", "Definition of done", "maintaining", "Conduct for changes"]) == 0
        out = capsys.readouterr().out.splitlines()
        assert out[0].startswith("backlog:") and out[1].endswith(": ## Definition of done")
        assert any(ln.startswith("maintaining:") for ln in out) and any(ln.endswith(": ## Conduct for changes") for ln in out)
        assert selfdoc.main(["section", "backlog", "Definition of done", "maintaining", "No Such Heading"]) == 1
        assert "NO SECTION 'No Such Heading' in maintaining" in capsys.readouterr().out
        with pytest.raises(SystemExit) as e:
            selfdoc.main(["section", "backlog", "Definition of done", "maintaining"])
        assert e.value.code == 2 and "has no HEADING" in capsys.readouterr().err, "an odd count is a usage error"

    def test_skill_section_headings_resolve_and_parse_in_both_shells(self, capsys):
        """Every `selfdoc.py section` command in a skill or in kb-worker.md, read from the files as they are now, is
        DOC HEADING pairs that exits 0 (a renamed heading breaks it) and holds no character Bash and PowerShell read
        differently; a skill that reads several sections names them in one command."""
        files = sorted(glob.glob(os.path.join(selfdoc.KB, ".claude", "skills", "*", "SKILL.md")))
        files.append(os.path.join(selfdoc.KB, ".claude", "agents", "kb-worker.md"))
        seen = 0
        for f in files:
            with open(f, encoding="utf-8") as fh:
                text = fh.read()
            rel = os.path.relpath(f, selfdoc.KB).replace(os.sep, "/")
            assert not re.search(r"^- `python3 _tools/selfdoc\.py section [^`]+`.*\n- `python3 _tools/selfdoc\.py section ",
                                 text, re.M), f"{rel} lists several section reads as separate commands"
            cmds = section_commands(text)
            assert len(cmds) == text.count(SECTION_CMD), f"{rel}: a section command outside a code span or fence"
            for cmd in cmds:
                assert not shell_problems(cmd), f"{rel}: {cmd!r} holds {shell_problems(cmd)}"
                code, out = run_section(cmd, capsys)
                assert code == 0, f"{rel}: {cmd!r} exits {code}: {out[-300:]}"
                seen += 1
        assert seen, "no section command found in the skills"

    def test_skill_section_headings_finds_commands_in_spans_and_fences(self):
        text = ('Read `python3 _tools/selfdoc.py section backlog "Git"` first.\n'
                '- ``python3 _tools/selfdoc.py section plugin "roots beside \\`kb/public\\`"`` (escaped)\n'
                '```\npython3 _tools/selfdoc.py section maintaining "Conduct for changes" git "Workflow"\n```\n'
                'Prose `selfdoc.py section` is no command.\n')
        assert section_commands(text) == [
            'python3 _tools/selfdoc.py section backlog "Git"',
            'python3 _tools/selfdoc.py section plugin "roots beside \\`kb/public\\`"',
            'python3 _tools/selfdoc.py section maintaining "Conduct for changes" git "Workflow"']

    def test_skill_section_headings_planted_renamed_heading_fails(self, capsys):
        """The planted failure: a skill names a heading its doc does not have (one renamed since)."""
        code, out = run_section('python3 _tools/selfdoc.py section backlog "Definition of finished"', capsys)
        assert code == 1 and "NO SECTION 'Definition of finished'" in out
        code, _ = run_section('python3 _tools/selfdoc.py section backlog "Definition of done" maintaining', capsys)
        assert code != 0, "an odd count is no DOC HEADING pairs"
        assert run_section('python3 _tools/selfdoc.py section backlog "Definition of done"', capsys)[0] == 0

    @pytest.mark.parametrize("cmd, problem", [
        ('python3 _tools/selfdoc.py section plugin "roots beside \\`kb/public\\`"', "backslash-escaped backtick"),
        ('python3 _tools/selfdoc.py section plugin "roots beside `kb/public`"', "backtick"),
        ('python3 _tools/selfdoc.py section backlog "$(whoami)"', "$("),
    ])
    def test_skill_section_headings_planted_shell_specific_command_fails(self, cmd, problem):
        """The planted failure: a command that parses in one shell only (the kb-ingest command BG-v2xwgr6m fixed)."""
        assert problem in shell_problems(cmd)
        assert not shell_problems('python3 _tools/selfdoc.py section plugin "6. A team\'s own knowledge: roots beside kb/public"')


SECTION_CMD = "python3 _tools/selfdoc.py section"
# what Bash and PowerShell read differently: the backtick is PowerShell's escape character (so a backslash-escaped
# backtick escapes the character after it, a closing quote included), and `$(` runs a subexpression in both
SHELL_SPECIFIC = (("\\`", "backslash-escaped backtick"), ("`", "backtick"), ("$(", "$("))


def section_commands(text):
    """The `selfdoc.py section` commands in Markdown TEXT as written: a fenced line starting with one, or the content of
    an inline code span of any backtick run that holds one (from the command on), so an escaped backtick stays in."""
    cmds, fence = [], None
    for line in text.splitlines():
        m = re.match(r"\s*(`{3,}|~{3,})", line)
        if m and (fence is None or (m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence))):
            fence = m.group(1) if fence is None else None
            continue
        if fence is not None:
            if line.strip().startswith(SECTION_CMD):
                cmds.append(line.strip())
            continue
        for m in re.finditer(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)", line):
            body = m.group(2)
            if SECTION_CMD in body:
                cmds.append(body[body.index(SECTION_CMD):].strip())
    return cmds


def shell_problems(cmd):
    """The names of what CMD holds that Bash and PowerShell read differently; [] when it holds none."""
    found, rest = [], cmd
    for chars, name in SHELL_SPECIFIC:
        if chars in rest:
            found.append(name)
            rest = rest.replace(chars, "")
    return found


def run_section(cmd, capsys):
    """(exit code, output) of a `selfdoc.py section` command run with the argv a POSIX shell splits it into."""
    capsys.readouterr()
    try:
        args = shlex.split(cmd[len(SECTION_CMD):])
    except ValueError as e:
        return 2, f"does not split: {e}"
    try:
        code = selfdoc.main(["section", *args])
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 2
    out = capsys.readouterr()
    return code, out.out + out.err


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

    @pytest.mark.parametrize("sep", ["\u2028", "\u2029", "\u0085", "\x0c"])
    def test_selfdoc_map_lines_by_lf(self, tmp_path, sep):
        """A line separator other than LF inside a string or a docstring moves no line number: map_tools and check_map agree
        with the LF numbering, and a docstring keeps its first line whole; the planted failure is `str.splitlines`, which does break there."""
        src = f'def a():\n    s = "x{sep}y"\n    return s\n\n\ndef b():\n    """Doc{sep}more."""\n\n\ndef c():\n    pass\n'
        assert len(src.splitlines()) > len(selfdoc.lf_lines(src)), "the planted character is a splitlines break"
        os.makedirs(tmp_path / "_tools")
        (tmp_path / "_tools" / "sep.py").write_text(src, encoding="utf-8", newline="\n")
        lines = selfdoc.map_tools("sep", tmp_path)
        assert lines == ["_tools/sep.py:1 module sep", "_tools/sep.py:1 def a", "_tools/sep.py:6 def b — Doc more.",
                         "_tools/sep.py:10 def c"]
        assert selfdoc.check_map(lines, tmp_path) == []
        assert selfdoc.check_map(["_tools/sep.py:11 def c"], tmp_path) == ["_tools/sep.py:11: `c` (def) is not at that line"]

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

    @staticmethod
    def backlog_rows(text):
        """The command cell of each `backlog.py` row of a tools.md table, split into its subcommands."""
        rows = []
        for ln in text.splitlines():
            m = re.match(r"\| `python3 _tools/backlog\.py ([^`]*)` \|", ln)
            if m and m.group(1) != "SUBCOMMAND ...":
                rows.append([a.strip() for a in m.group(1).split("\\|")])
        return rows

    @staticmethod
    def backlog_row_problems(rows, known):
        problems = [f"row lists {len(r)} subcommands" for r in rows if len(r) > 5]
        names = [a.split(" --")[0] for r in rows for a in r]
        problems += [f"{n} is no backlog.py subcommand" for n in names if n not in known]
        if len(rows) < 12:
            problems.append(f"only {len(rows)} rows")
        return problems

    def test_tools_md_backlog_row_per_subcommand(self):
        """tools.md gives backlog.py one row per subcommand (a few share a row), so edits to different ones touch
        different lines. Planted: the old single row naming them all fails."""
        known = set(re.findall(r'add_parser\("([a-z-]+)"\)', pathlib.Path(selfdoc.KB, "_tools", "backlog.py").read_text(encoding="utf-8")))
        known.add("gate add")
        text = pathlib.Path(selfdoc.KB, S, "tools.md").read_text(encoding="utf-8")
        rows = self.backlog_rows(text)
        assert self.backlog_row_problems(rows, known) == []
        merged = "| `python3 _tools/backlog.py new\\|find\\|check\\|show\\|next\\|claim\\|done` | the backlog |"
        assert self.backlog_row_problems(self.backlog_rows(merged), known), "planted: one row for many subcommands"
        assert self.backlog_row_problems(self.backlog_rows(text.replace("backlog.py find`", "backlog.py findx`")), known)

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

    def test_selfdoc_range_review_over_the_pushed_range(self, repo):
        """The gate runs `stale --since UP` over the pushed range: a commit that changes only backlog items or the
        query log needs no Self-Reviewed trailer, a doc edit or review anywhere in the range clears the code change
        before it, and a range whose code change lacks its doc update still fails."""
        import kbgit
        root, up = repo.path, repo.rev("HEAD")
        items, store = [f"{S}/backlog/ST-00000000.json"], "kb/_querylog/2026-09/x.jsonl"
        assert kbgit.gate_needs(items + [store])["selfdoc"] is None, "item and store paths skip the selfdoc check"
        assert kbgit.gate_needs(items + ["src/tool.py"])["selfdoc"], "a code path runs it"
        assert selfdoc.describing(selfdoc.load_map(), items + [store]) == {}, "this repository's map describes neither"
        repo.write(items[0], "{}\n")
        repo.write(store, "{}\n")
        repo.git("add", "-A")
        repo.git("commit", "-q", "-m", "claim the item")  # no trailer
        assert selfdoc.stale(root, since=up) == []
        repo.write("src/tool.py", "print(6)\n")
        repo.git("commit", "-qam", "change the tool")  # the doc update comes in a later commit of the range
        assert [d for d, _, _ in selfdoc.stale(root, since=up)] == [f"{S}/tools.md"], "planted: code without its doc"
        repo.write(items[0], '{"status": "done"}\n')
        repo.git("commit", "-qam", "done the item")  # item-only, no trailer: does not clear the code change
        assert [d for d, _, _ in selfdoc.stale(root, since=up)] == [f"{S}/tools.md"]
        repo.write(f"{S}/tools.md", "tools v6\n")
        repo.git("commit", "-qam", "update the doc")
        repo.write(store, '{"q": 1}\n')
        repo.git("commit", "-qam", "log a query")  # item-only commits after the doc update, still no trailer
        assert selfdoc.stale(root, since=up) == [], "the doc update anywhere in the range clears it"

    @pytest.mark.parametrize("entry", ["sync_gate_selfdoc_stale_over_pushed_range",
                                       "pre_push_selfdoc_stale_over_pushed_range"])
    def test_selfdoc_gate_passes_since(self, entry, monkeypatch):
        """Both entry points of the gate (sync's, and the pre-push hook for a plain `git push`) run
        `selfdoc.py stale --since UP` with the upstream they judge: without `--since` the check reads only the
        last commit, and the range judgement above (test_selfdoc_range_review_over_the_pushed_range) is never
        reached. The check list is read from the tool calls the gate makes, so dropping the argument from
        kbgit.py fails here; the planted failure strips it from the call and the same assertion catches it."""
        import kbgit
        up, head = "a" * 40, "b" * 40
        for k in (*LEAKY, "KB_GATE_DONE", "KB_SYNC_NO_TESTS"):
            monkeypatch.delenv(k, raising=False)

        def run_gate(strip_since):
            calls = []

            def tool(name, *args, env=None):
                if strip_since and name == "selfdoc.py":
                    args = tuple(a for a in args if a not in ("--since", up))
                calls.append((name, list(args)))
                return 0, "ok\n"
            monkeypatch.setattr(kbgit, "tool", tool)
            monkeypatch.setattr(kbgit, "gate_paths", lambda _up: None)  # no path filter: every check runs
            monkeypatch.setattr(kbgit, "trailer_audit", lambda *_a, **_k: (0, 0, []))
            if entry.startswith("sync_gate"):
                assert kbgit.gate({"target": "origin"}, up)
            else:
                monkeypatch.setattr(kbgit.kbpublic, "guard_push", lambda *_a, **_k: [])
                monkeypatch.setattr(kbgit, "lane_refusals", lambda *_a, **_k: [])
                monkeypatch.setattr(kbgit, "rev_parse", lambda _rev: head)
                monkeypatch.setattr(kbgit, "git", lambda *_a, **_k: "")
                monkeypatch.setattr(kbgit, "dirty_paths", lambda: ([], []))
                stdin = f"refs/heads/main {head} refs/heads/main {up}\n"
                assert kbgit.hook_pre_push(["origin"], stdin) == 0
            return calls

        def assert_since(calls):
            stale = [args for name, args in calls if name == "selfdoc.py"]
            assert stale == [["stale", "--since", up]], f"selfdoc.py must run `stale --since {up}`, ran {stale}"

        assert_since(run_gate(strip_since=False))
        with pytest.raises(AssertionError, match="--since"):
            assert_since(run_gate(strip_since=True))  # planted: the call without --since is caught

    def test_foreign_stale_doc_does_not_fail_done(self, repo):
        """An item's check `selfdoc.py stale --work ID`, run as `backlog.py done` runs it, fails only on a doc the
        item's own commits left stale: another item's commit that left a doc stale (TK-uxm5arrb and 17d0f58 in
        SP-v5xagbyv) does not fail it, while plain `stale` still lists that doc. The planted failure: the item's own
        code change without its doc."""
        import backlog
        for name in ("selfdoc.py", "kbcommon.py"):  # the tool reads the clone it sits in
            repo.write(f"_tools/{name}", (pathlib.Path(selfdoc.__file__).parent / name).read_text(encoding="utf-8"))
        repo.append(f"{S}/map.csv", f"{S}/agents.md,lib/*.py\n")
        repo.write(f"{S}/agents.md", "agents\n")
        repo.write("lib/hook.py", "print(0)\n")
        repo.git("add", "-A")
        repo.git("commit", "-q", "-m", "tools and a second doc")
        root, mine = repo.path, ["python3", "_tools/selfdoc.py", "stale", "--work", "ST-mine"]

        def commit(msg, item):
            repo.git("add", "-A")
            repo.git("commit", "-q", "-m", f"{msg}\n\nbecause\n\nKB-Work: {item}")

        repo.write("lib/hook.py", "print(1)\n")
        commit("foreign change, no doc", "ST-other")  # leaves agents.md stale
        assert backlog.run_check(root, {"run": mine})[0], "no commit of the item yet: nothing of its own is stale"
        repo.write("src/tool.py", "print(7)\n")
        repo.write(f"{S}/tools.md", "tools v7\n")
        commit("the item's change with its doc", "ST-mine")
        assert [d for d, _, _ in selfdoc.stale(root)] == [f"{S}/agents.md"], "plain stale still lists the foreign doc"
        ok, code, out = backlog.run_check(root, {"run": mine})
        assert ok and code == 0 and "stale=0" in out, out
        assert selfdoc.stale(root, work=["ST-mine"]) == []

        repo.write("src/tool.py", "print(8)\n")
        commit("the item's change without its doc", "ST-mine, TK-sub")
        ok, code, out = backlog.run_check(root, {"run": mine})
        assert not ok and code == 1 and f"STALE {S}/tools.md" in out and "agents.md" not in out, out
        assert [d for d, _, _ in selfdoc.stale(root, work=["TK-sub"])] == [f"{S}/tools.md"], "any id of the trailer"
        assert selfdoc.stale(root, work=["ST-none"]) == []
        repo.git("commit", "-q", "--allow-empty", "-m", f"review\n\nSelf-Reviewed: {S}/tools.md\nKB-Work: ST-other")
        assert selfdoc.stale(root, work=["ST-mine"]) == [], "a later review, whoever's, clears it"
        repo.write("src/tool.py", "print(9)\n")
        commit("again", "ST-mine")
        assert [d for d, _, _ in selfdoc.stale(root, work=["ST-mine"])] == [f"{S}/tools.md"], "a later change needs more"
        repo.write(f"{S}/tools.md", "tools v9\n")
        commit("the doc, by a later commit", "ST-third")
        assert selfdoc.stale(root, work=["ST-mine"]) == [], "a later doc edit clears it"
        with pytest.raises(SystemExit) as e:
            selfdoc.main(["stale", "--work", "ST-mine", "--since", "HEAD"])
        assert e.value.code == 2, "--work and --since are one or the other"

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
