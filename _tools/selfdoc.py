#!/usr/bin/env python3
"""Which of the kb's own docs (kb/_self/, AGENTS.md, README.md) are behind the files they describe (stdlib only).

  selfdoc.py stale                 docs whose described files changed in a commit after the doc's last commit, or in
                                   the working tree while the doc did not; exit 1 when any
  selfdoc.py stale --since REV     docs whose described files differ between REV and the working tree (untracked files
                                   included) while the doc does not: the check before a commit or a push
                                   (`--since @{upstream}`); exit 1 when any
  selfdoc.py map PATH [PATH ...]   the docs that describe these paths
  selfdoc.py check                 map rows naming a missing doc or matching no file, and kb/_self/*.md docs with no row;
                                   exit 1 when any
  selfdoc.py section DOC HEADING   the section under that heading, down to the next heading of the same or a higher
                                   level, each line with its line number; exit 1 naming the headings when none matches

kb/_self/map.csv (doc,pattern) says what each doc describes: one row per doc and glob, repository-relative paths; `*` stays within a
directory, `**` crosses directories. A pattern of `-` marks a doc that describes no file: it is never
stale. Reports under kb/_self/reports/ are measurements, each section stating its setup, and need no row. /kb-self is the
runbook that updates what `stale` lists. A doc that was checked against a change and needed no edit is recorded
with a commit trailer, `Self-Reviewed: kb/_self/plugin.md, AGENTS.md`: from that commit on, `stale` counts it as up to
date for everything before. A repository tool like kbgit.py: it reads this clone, never KB_ROOT.
Exit 0 nothing to do, 1 stale docs or map problems, 2 bad arguments, no git, or an unreadable map.

`section` reads one file, so a skill or an agent takes the part of a doc it needs, not the whole. DOC is a path from the
repository root or an absolute path, else a name under kb/_self (`maintaining` or `maintaining.md`). HEADING is the
heading's text, matched without regard to case or repeated spaces; a leading `##` also pins the level. Lines in fenced
code blocks and a YAML front matter are never headings. A subsection belongs to its section; a heading that occurs more
than once prints every section with that text. It needs no git.

  selfdoc.py map-tools [FILE]      every module, class, function and method of _tools/*.py, one line each:
                                   `path:line kind name — first docstring line`; FILE (a path, or a name such as `rag`)
                                   narrows it to one file; exit 2 when FILE is not a Python file under _tools

`map-tools` is built from `ast` on each run, and nothing of it is committed, so it cannot go stale. Kinds: `module`,
`class`, `def` (`async` for `async def`), `method` (a def inside a class, named `Class.method`), `test` (a `test*`
function or method of a `test_*.py` file). A file that does not parse is one `unparsed` line. `path:line` is the line of
the `def` or `class` keyword (a decorator line is not it), so `sed -n 'LINE,+30p' path` reads the symbol. It lists the
symbols so that a session reads the one it needs, not a whole tool.
"""
import argparse, ast, csv, functools, io, os, pathlib, re, subprocess, sys, tokenize, warnings

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kbcommon  # noqa: E402

KB = kbcommon.HOME  # this repository
SELF_REL = kbcommon.repo_rel(kbcommon.SELF)  # the kb's own docs, relative to the repository (`_self`)
MAP = f"{SELF_REL}/map.csv"
REVIEWED = "Self-Reviewed"  # commit trailer: docs checked against the change that needed no edit


class SelfdocError(Exception):
    pass


@functools.lru_cache(maxsize=None)
def glob_rx(pattern):
    """A compiled regex for a map glob: `**` any path, `*` any name part, `?` one character (never `/`)."""
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out) + r"\Z")


def matches(pattern, path):
    return pattern != "-" and bool(glob_rx(pattern).match(path))


def load_map(root=KB):
    """{doc: [pattern, ...]} in file order."""
    try:
        with open(os.path.join(root, MAP), encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
    except OSError as e:
        raise SelfdocError(f"cannot read {MAP}: {e.strerror}")
    if rows and not {"doc", "pattern"} <= rows[0].keys():
        raise SelfdocError(f"{MAP} needs the columns doc,pattern")
    out = {}
    for r in rows:
        doc, pat = (r.get("doc") or "").strip(), (r.get("pattern") or "").strip()
        if doc and pat:
            out.setdefault(doc, []).append(pat)
    return out


def describing(docs, paths):
    """{doc: [paths it describes]} for the given paths, docs without a match left out."""
    out = {}
    for doc, pats in docs.items():
        hit = [p for p in paths if p != doc and any(matches(pat, p) for pat in pats)]
        if hit:
            out[doc] = hit
    return out


def git(root, *args):
    p = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8")
    if p.returncode:
        raise SelfdocError(f"git {' '.join(args)}: {(p.stderr or p.stdout).strip()}")
    return p.stdout


def lines(text):
    return [ln for ln in text.splitlines() if ln]


def worktree_changes(root, rev="HEAD"):
    """Paths that differ between REV and the working tree (staged or not), plus untracked files."""
    return set(lines(git(root, "diff", "--name-only", rev))) | set(lines(git(root, "ls-files", "--others", "--exclude-standard")))


def reviews(root, rev_range=None):
    """[(short hash, {docs})] newest first: the commits (all of HEAD's history, or REV_RANGE) whose message carries
    a `Self-Reviewed: <doc>, <doc>` trailer (the docs were checked against the change and needed no edit)."""
    fmt = f"%h%x1f%(trailers:key={REVIEWED},valueonly,separator=%x2C)%x1e"
    out = []
    for rec in git(root, "log", f"--format={fmt}", *([rev_range] if rev_range else [])).split("\x1e"):
        h, _, docs = rec.strip().partition("\x1f")
        names = {d.strip() for d in docs.replace("\n", ",").split(",") if d.strip()}
        if h and names:
            out.append((h, names))
    return out


def stale(root=KB, since=None):
    """[(doc, reference, [changed described paths])]: the docs that are behind what they describe. A doc edited in
    the change, or named in a `Self-Reviewed:` trailer of a commit since, counts as up to date."""
    docs = load_map(root)
    out = []
    if since:
        git(root, "rev-parse", "--verify", "--quiet", since + "^{commit}")
        changed = worktree_changes(root, since)
        updated = changed | {d for _, names in reviews(root, f"{since}..HEAD") for d in names}  # a review is no change
        for doc, hit in describing(docs, sorted(changed)).items():
            if doc not in updated:
                out.append((doc, since, hit))
        return out
    local = worktree_changes(root)
    reviewed = reviews(root)
    for doc in docs:
        if doc in local:
            continue  # being edited now: the edit is the update
        last = git(root, "log", "-1", "--format=%h", "--", doc).strip()
        if not last:
            continue  # never committed: new, so not behind anything yet
        seen = next((h for h, names in reviewed if doc in names), None)
        if seen and subprocess.run(["git", "merge-base", "--is-ancestor", last, seen], cwd=root).returncode == 0:
            last = seen  # reviewed after its last edit: the review is the reference
        later = set(lines(git(root, "diff", "--name-only", last, "HEAD"))) | local
        hit = describing({doc: docs[doc]}, sorted(later)).get(doc)
        if hit:
            out.append((doc, last, hit))
    return out


def check(root=KB):
    """Problems with the map: missing docs, patterns that match no file, top-level _self docs with no row."""
    docs = load_map(root)
    files = set(lines(git(root, "ls-files"))) | set(lines(git(root, "ls-files", "--others", "--exclude-standard")))
    problems = []
    for doc, pats in docs.items():
        if not os.path.exists(os.path.join(root, doc)):
            problems.append(f"{doc}: the doc does not exist")
        for pat in pats:
            if pat != "-" and not any(matches(pat, f) for f in files):
                problems.append(f"{doc}: pattern {pat} matches no file")
    for f in sorted(files):
        if f.startswith(SELF_REL + "/") and "/" not in f[len(SELF_REL) + 1:] and f.endswith(".md") and f not in docs:
            problems.append(f"{f}: no row in {MAP} (pattern - if it describes no file)")
    return problems


HEADING_RX = re.compile(r" {0,3}(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*\Z")
FENCE_RX = re.compile(r" {0,3}(`{3,}|~{3,})")


def resolve_doc(name, root=KB):
    """The file DOC names: a path from the repository root (or absolute), else a name under kb/_self, with or without `.md`."""
    base = pathlib.Path(root)
    for cand in (name, f"{SELF_REL}/{name}"):
        for path in (base / cand, base / (cand + ".md")):
            if path.is_file():
                return path
    raise SelfdocError(f"no such doc: {name} (looked for it from the repository root and under {SELF_REL}/)")


def headings(text_lines):
    """[(index, level, text)] of the ATX headings of a doc, leaving out fenced code blocks and a YAML front matter."""
    out, fence, i = [], None, 0
    if text_lines and text_lines[0].strip() == "---":  # front matter: `# ...` lines in it are comments
        end = next((k for k in range(1, len(text_lines)) if text_lines[k].strip() in ("---", "...")), None)
        i = 0 if end is None else end + 1
    for k in range(i, len(text_lines)):
        ln = text_lines[k]
        m = FENCE_RX.match(ln)
        if fence:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) and not ln.strip().strip(fence[0]):
                fence = None
        elif m:
            fence = m.group(1)
        else:
            h = HEADING_RX.match(ln)
            if h:
                out.append((k, len(h.group(1)), h.group(2)))
    return out


def norm_heading(text):
    return " ".join(text.split()).casefold()


def sections(text_lines, heading):
    """[(first index, end index)] of each section whose heading matches: from its heading line down to the next
    heading of the same or a higher level (trailing blank lines left out). HEADING may start with `#`s that pin the level."""
    m = re.match(r"(#{1,6})[ \t]+(.*)\Z", heading.strip())
    level, want = (len(m.group(1)), m.group(2)) if m else (None, heading)
    heads = headings(text_lines)
    out = []
    for n, (i, lvl, text) in enumerate(heads):
        if norm_heading(text) != norm_heading(want) or level not in (None, lvl):
            continue
        end = next((j for j, l2, _ in heads[n + 1:] if l2 <= lvl), len(text_lines))
        while end > i + 1 and not text_lines[end - 1].strip():
            end -= 1
        out.append((i, end))
    return out


def section(doc, heading, root=KB):
    """([[(line no, line)] per matching section], [every heading of the doc, `##` marks and text]); line numbers start at 1."""
    path = resolve_doc(doc, root)
    try:
        text_lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as e:
        raise SelfdocError(f"cannot read {doc}: {getattr(e, 'strerror', None) or e}")
    found = [[(k + 1, text_lines[k]) for k in range(i, end)] for i, end in sections(text_lines, heading)]
    return found, [f"{'#' * lvl} {text}" for _, lvl, text in headings(text_lines)]


TOOLS_REL = "_tools"
DOC_MAX = 100  # a docstring's first line is cut here in the map
DEFS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
MAP_LINE_RX = re.compile(r"(?P<path>.+?):(?P<line>\d+) (?P<kind>\w+) (?P<name>\S+)(?: — .*)?\Z")
DEF_LINE_RX = re.compile(r"(?P<indent>\s*)(?P<kw>async\s+def|def|class)\s+(?P<name>\w+)")


def tool_files(root=KB):
    """[Path] of every Python file under _tools/, sorted, leaving out caches and hidden directories."""
    base = pathlib.Path(root) / TOOLS_REL
    return sorted(p for p in base.rglob("*.py") if p.is_file() and not any(
        part.startswith((".", "__")) for part in p.relative_to(base).parts[:-1]))


def resolve_tool(name, root=KB):
    """The _tools Python file FILE names: a path from the repository root (or absolute), or a name under _tools with
    or without `.py`."""
    base = pathlib.Path(root)
    tools = (base / TOOLS_REL).resolve()
    for cand in (name, f"{TOOLS_REL}/{name}"):
        for path in (base / cand, base / (cand + ".py")):
            if path.is_file() and path.suffix == ".py" and tools in path.resolve().parents:
                return path
    raise SelfdocError(f"no such tool file: {name} (a .py file under {TOOLS_REL}/)")


def first_line(doc):
    """The first line of a docstring, cut to DOC_MAX characters; empty for none."""
    lines_ = (doc or "").strip().splitlines()
    text = " ".join(lines_[0].split()) if lines_ else ""
    return text if len(text) <= DOC_MAX else text[:DOC_MAX - 1].rstrip() + "…"


def symbols_of(tree, is_test_file):
    """[(line, kind, qualified name, docstring first line)] of the classes, functions and methods of a module, by line.
    A def or class inside another def is a detail of it and is not listed; one under an `if` or `try` is."""
    out = []

    def visit(node, prefix, in_class):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, DEFS):
                name = prefix + child.name
                if isinstance(child, ast.ClassDef):
                    kind = "class"
                elif is_test_file and child.name.startswith("test_"):
                    kind = "test"
                elif in_class:
                    kind = "method"
                else:
                    kind = "async" if isinstance(child, ast.AsyncFunctionDef) else "def"
                out.append((child.lineno, kind, name, first_line(ast.get_docstring(child))))
                if isinstance(child, ast.ClassDef):
                    visit(child, name + ".", True)
            elif not isinstance(child, ast.expr):  # compound statements: if, try, with, for, match
                visit(child, prefix, in_class)

    visit(tree, "", False)
    return sorted(out, key=lambda s: s[0])


def file_map(path, root=KB):
    """[map line] of one file: its module line, then its symbols by line."""
    rel = pathlib.Path(path).resolve().relative_to(pathlib.Path(root).resolve()).as_posix()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # a file's own SyntaxWarning (an escape in a docstring) is not the map's
            tree = ast.parse(pathlib.Path(path).read_text(encoding="utf-8"), filename=rel)
    except (SyntaxError, ValueError, UnicodeDecodeError) as e:
        return [f"{rel}:{getattr(e, 'lineno', None) or 1} unparsed {pathlib.Path(rel).stem} — {type(e).__name__}"]
    out = [(1, "module", pathlib.Path(rel).stem, first_line(ast.get_docstring(tree)))]
    out += symbols_of(tree, pathlib.Path(rel).name.startswith("test_"))
    return [f"{rel}:{no} {kind} {name}" + (f" — {doc}" if doc else "") for no, kind, name, doc in out]


def map_tools(file=None, root=KB):
    """[map line] of every _tools Python file, or of FILE alone."""
    return [ln for p in ([resolve_tool(file, root)] if file else tool_files(root)) for ln in file_map(p, root)]


def def_tokens(text):
    """[(line, column, name)] of every `def` and `class` statement of Python source, read from its tokens (a `def` inside
    a string is no token of that kind), for the check that the map and the code agree; [] when the source does not tokenize."""
    out, prev, before = [], None, None
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.NAME and prev is not None and prev.string in ("def", "class"):
                first = before.start if prev.string == "def" and before is not None and before.string == "async" else prev.start
                out.append((first[0], first[1], tok.string))
            before, prev = prev, tok
    except (tokenize.TokenError, SyntaxError, IndentationError):
        return []
    return out


def check_map(map_lines, root=KB):
    """[problem] where a map line does not hold in the code: the file or the line is missing, the line is not the `def` or
    `class` of that name and kind, or a top-level def or class of a mapped file has no line in the map."""
    problems, mapped, base = [], {}, pathlib.Path(root)
    src = {}
    for ln in map_lines:
        m = MAP_LINE_RX.match(ln)
        if not m:
            problems.append(f"not a map line: {ln}")
            continue
        path, no, kind, name = m["path"], int(m["line"]), m["kind"], m["name"]
        if path not in src:
            try:
                src[path] = (base / path).read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                src[path] = None
        text = src[path]
        if text is None:
            problems.append(f"{path}: no such file (mapped: {name})")
        elif kind in ("module", "unparsed"):
            continue
        elif not 1 <= no <= len(text):
            problems.append(f"{path}:{no}: past the end of the file (mapped: {name})")
        else:
            d = DEF_LINE_RX.match(text[no - 1])
            want = "class" if kind == "class" else "def"
            if not d or d["name"] != name.rsplit(".", 1)[-1] or d["kw"].split()[-1] != want:
                problems.append(f"{path}:{no}: `{name}` ({kind}) is not at that line")
            else:
                mapped.setdefault(path, set()).add(no)
    for path, nos in mapped.items():
        for k, col, name in def_tokens("\n".join(src[path]) + "\n"):
            if col == 0 and k not in nos:
                problems.append(f"{path}:{k}: `{name}` is in the code and not in the map")
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stale", help="docs behind the files they describe")
    s.add_argument("--since", metavar="REV", help="compare REV with the working tree instead of each doc's last commit")
    m = sub.add_parser("map", help="the docs that describe these paths")
    m.add_argument("paths", nargs="+")
    sub.add_parser("check", help="map rows naming a missing doc or matching no file; _self docs with no row")
    c = sub.add_parser("section", help="one section of a doc, with line numbers")
    c.add_argument("doc", metavar="DOC", help="path from the repository root, or a name under kb/_self")
    c.add_argument("heading", metavar="HEADING", help="the heading's text (case-insensitive); `## text` pins the level")
    t = sub.add_parser("map-tools", help="the symbols and tests of _tools/*.py, with file:line")
    t.add_argument("file", metavar="FILE", nargs="?", help="one file: a path, or a name under _tools (`rag`)")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "map-tools":
            out = map_tools(a.file)
            print("\n".join(out))
            kinds = [MAP_LINE_RX.match(ln)["kind"] for ln in out]
            print(f"files={kinds.count('module') + kinds.count('unparsed')} symbols={len(kinds) - kinds.count('module') - kinds.count('unparsed')}")
            return 0
        if a.cmd == "section":
            found, heads = section(a.doc, a.heading)
            if not found:
                print(f"NO SECTION {a.heading!r} in {a.doc}; headings:")
                for h in heads:
                    print(f"  {h}")
                return 1
            for block in found:
                print(f"{a.doc}:{block[0][0]}-{block[-1][0]}")
                for no, ln in block:
                    print(f"{no}: {ln}")
            return 0
        if a.cmd == "map":
            found = describing(load_map(), [os.path.normpath(p).replace(os.sep, "/") for p in a.paths])
            for doc, hit in found.items():
                print(f"{doc}: {', '.join(hit)}")
            print(f"docs={len(found)}")
            return 0
        if a.cmd == "check":
            problems = check()
            for p in problems:
                print("PROBLEM", p)
            print(f"problems={len(problems)}")
            return 1 if problems else 0
        result = stale(since=a.since)
        for doc, ref, hit in result:
            more = f" +{len(hit) - 8} more" if len(hit) > 8 else ""
            print(f"STALE {doc} (since {ref}): {', '.join(hit[:8])}{more}")
        print(f"stale={len(result)}" + (" (update them: /kb-self)" if result else ""))
        return 1 if result else 0
    except SelfdocError as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 2
    except FileNotFoundError:
        print("ERROR git is not installed", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
