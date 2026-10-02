#!/usr/bin/env python3
"""Which of the kb's own docs (kb/_self/, AGENTS.md, README.md) are behind the files they describe (stdlib only).

  selfdoc.py stale                 docs whose described files changed in a commit after the doc's last commit, or in
                                   the working tree while the doc did not; exit 1 when any
  selfdoc.py stale --since REV     docs whose described files differ between REV and the working tree (untracked files
                                   included) while the doc does not: the check before a commit or a push
                                   (`--since @{upstream}`); exit 1 when any
  selfdoc.py stale --work ID [--work ID ...]
                                   only the staleness the commits whose `KB-Work` trailer names an ID cause: a doc
                                   such a commit's described files changed while neither that commit nor a later one
                                   changed or reviewed the doc; a backlog item's check, which a commit of another item
                                   or sprint cannot fail; exit 1 when any
  selfdoc.py map PATH [PATH ...]   the docs that describe these paths
  selfdoc.py check                 map rows naming a missing doc or matching no file, kb/_self/*.md docs with no row,
                                   and dead section references; exit 1 when any
  selfdoc.py section DOC HEADING [DOC HEADING ...]
                                   the section under each heading, down to the next heading of the same or a higher
                                   level, each line with its line number; exit 1 when a heading matches none, naming
                                   it and its doc's headings (the other pairs still print)

kb/_self/map.csv (doc,pattern) says what each doc describes: one row per doc and glob, repository-relative paths; `*` stays within a
directory, `**` crosses directories. A pattern of `-` marks a doc that describes no file: it is never
stale. Reports under kb/_self/reports/ are measurements, each section stating its setup, and need no row. /kb-self is the
runbook that updates what `stale` lists. A doc that was checked against a change and needed no edit is recorded
with a commit trailer, `Self-Reviewed: kb/_self/plugin.md, AGENTS.md`: from that commit on, `stale` counts it as up to
date for everything before. A repository tool like kbgit.py: it reads this clone, never KB_ROOT.
Exit 0 nothing to do, 1 stale docs or map problems, 2 bad arguments, no git, or an unreadable map.

A section reference is `(kb/_self/<doc>.md, <Section>)` or `(<doc>.md, <Section>)`, the doc in backticks or not, in
kb/_self/*.md, AGENTS.md, .claude/skills/*/SKILL.md and the docstrings and comments of _tools/*.py. `check` names each
whose kb/_self doc has no heading of that text (`path:line: (doc, Section) names no heading of ...`); the text may be a
heading's first words (`Ledgers` for `Ledgers and retrieval data`) or `A and B` / `A, B` for several sections.

`section` reads one file, so a skill or an agent takes the part of a doc it needs, not the whole. DOC is a path from the
repository root or an absolute path, else a name under kb/_self (`maintaining` or `maintaining.md`). HEADING is the
heading's text, matched without regard to case or repeated spaces; a leading `##` also pins the level. Lines in fenced
code blocks and a YAML front matter are never headings. A subsection belongs to its section; a heading that occurs more
than once prints every section with that text. Several DOC HEADING pairs print their sections in one call, in the
order given, so a skill that reads several sections names them in one command. It needs no git.

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


WORK = "KB-Work"  # commit trailer: the backlog items a commit works on


def work_commits(root, ids):
    """[(hash, {changed paths})] newest first: the commits of HEAD's history whose `KB-Work` trailer, as git reads
    trailers, names one of IDS."""
    fmt = f"%H%x1f%(trailers:key={WORK},valueonly,separator=%x2C)%x1e"
    out = []
    for rec in git(root, "log", f"--format={fmt}", "HEAD").split("\x1e"):
        h, _, names = rec.strip().partition("\x1f")
        if h and {n.strip() for n in names.replace("\n", ",").split(",")} & set(ids):
            out.append((h, set(lines(git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", "--root", h)))))
    return out


def stale_work(root, ids, docs):
    """stale() limited to the commits that name IDS: a doc counts as behind when such a commit changed a file it
    describes and neither that commit nor a later one (to HEAD, whatever its trailer) changed the doc or names it in
    `Self-Reviewed:`. A doc another item's commit left stale is not this item's to fail."""
    out, seen = [], set()
    for h, paths in work_commits(root, ids):  # newest first: each doc is judged against its newest such commit
        for doc, hit in describing(docs, sorted(paths)).items():
            if doc in seen:
                continue  # judged against a newer commit of the item already
            seen.add(doc)
            if doc in paths or lines(git(root, "rev-list", "-1", f"{h}..HEAD", "--", doc)):
                continue  # edited in the change or after it
            if any(doc in names for r in (f"{h}^!", f"{h}..HEAD") for _, names in reviews(root, r)):
                continue  # reviewed in the change or after it
            out.append((doc, h[:12], hit))
    return out


def stale(root=KB, since=None, work=None):
    """[(doc, reference, [changed described paths])]: the docs that are behind what they describe. A doc edited in
    the change, or named in a `Self-Reviewed:` trailer of a commit since, counts as up to date. WORK (item ids) limits
    it to the changes of the commits whose `KB-Work` trailer names one of them (stale_work)."""
    docs = load_map(root)
    if work:
        return stale_work(root, work, docs)
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
    problems += dead_section_refs(root, files)
    return problems


# A section reference: `(kb/_self/querylog.md, Delivery)` or `(querylog.md, Spool and Distill)`, the doc in backticks
# or not, the section a capitalised heading text up to the closing parenthesis (a `;` before the doc is allowed).
SECTION_REF_RX = re.compile(r"(?<![\w/.-])`?(?P<doc>(?:kb/_self/)?[\w-]+\.md)`?,\s+(?P<sec>[A-Z][^()`;:\n]{0,60}?)\)")


def ref_sources(root, files):
    """[(path, [(first line no, text)])]: where section references are read. kb/_self/*.md, AGENTS.md and the skills'
    SKILL.md whole; _tools/*.py only in docstrings and comments, so a test's planted string is not a reference."""
    out = []
    for f in sorted(files):
        path = pathlib.Path(root, f)
        is_doc = (f.startswith(SELF_REL + "/") and "/" not in f[len(SELF_REL) + 1:] and f.endswith(".md")) \
            or f == "AGENTS.md" or (f.startswith(".claude/skills/") and f.endswith("/SKILL.md"))
        is_tool = f.startswith(TOOLS_REL + "/") and "/" not in f[len(TOOLS_REL) + 1:] and f.endswith(".py")
        if not (is_doc or is_tool) or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if is_doc:
            out.append((f, [(1, text)]))
            continue
        parts = []
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, *DEFS)) and node.body and isinstance(node.body[0], ast.Expr) \
                    and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                parts.append((node.body[0].lineno, node.body[0].value.value))
        try:
            for tok in tokenize.generate_tokens(io.StringIO(text).readline):
                if tok.type == tokenize.COMMENT:
                    parts.append((tok.start[0], tok.string))
        except (tokenize.TokenError, SyntaxError):
            pass
        out.append((f, sorted(parts)))
    return out


def heading_keys(text_lines):
    """The names a reference may give a doc's heading: its text, and its text without a trailing `(...)` note."""
    keys = set()
    for _, _, text in headings(text_lines):
        keys.add(norm_heading(text))
        keys.add(norm_heading(re.sub(r"\s*\([^()]*\)\s*\Z", "", text)))
    return keys


HEADING_TAIL_RX = re.compile(r"\s*[:;,.(/–—-]|\s+and\s")


def names_heading(sec, keys):
    """Whether SEC names one of the heading KEYS: the whole text, or its first words when what follows them starts a
    note or a joined clause (`Ledgers` for `Ledgers and retrieval data`, `Staging levels` for `Staging levels: what you
    must know at each`). A leading word that cuts a phrase (`The` for `The research queue`) names nothing."""
    s = norm_heading(sec)
    return bool(s) and any(k == s or (k.startswith(s) and bool(HEADING_TAIL_RX.match(k, len(s)))) for k in keys)


def dead_section_refs(root=KB, files=None):
    """`path:line: (doc, Section)` problems for each section reference whose doc under kb/_self has no heading of that
    text. `Spool and Distill` or `Routing, Packs` name several sections: each must exist when the whole does not."""
    if files is None:
        files = set(lines(git(root, "ls-files"))) | set(lines(git(root, "ls-files", "--others", "--exclude-standard")))
    cache, problems = {}, []
    for f, parts in ref_sources(root, files):
        for first, text in parts:
            for m in SECTION_REF_RX.finditer(text):
                doc = m["doc"]
                name = doc if doc.startswith(SELF_REL + "/") else f"{SELF_REL}/{doc}"
                if name not in cache:
                    p = pathlib.Path(root, name)
                    try:
                        cache[name] = heading_keys(p.read_text(encoding="utf-8").splitlines()) if p.is_file() else None
                    except (OSError, UnicodeDecodeError):
                        cache[name] = None
                keys = cache[name]
                sec = " ".join(m["sec"].split())
                line = first + text.count("\n", 0, m.start())
                if keys is None:
                    if doc.startswith(SELF_REL + "/"):
                        problems.append(f"{f}:{line}: ({doc}, {sec}) names a doc that does not exist")
                    continue  # a bare name that is no kb/_self doc (README.md of the repository, say) is not ours
                if re.search(r"\.\w", sec):
                    continue  # `(README.md, AGENTS.md)`: a list of files, not a section
                if names_heading(sec, keys) or all(names_heading(p, keys) for p in re.split(r",\s*|\s+and\s+", sec) if p.strip()):
                    continue
                problems.append(f"{f}:{line}: ({doc}, {sec}) names no heading of {name}")
    return problems


HEADING_RX = re.compile(r" {0,3}(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*\Z")
FENCE_RX = re.compile(r" {0,3}(`{3,}|~{3,})")


def resolve_doc(name, root=KB):
    """The file DOC names: a path from the repository root (or absolute), else a name under kb/_self, with or without
    `.md`. A file outside the repository is refused, so the command's allow rule opens no read beyond the clone."""
    base = pathlib.Path(root)
    inside = base.resolve()
    for cand in (name, f"{SELF_REL}/{name}"):
        for path in (base / cand, base / (cand + ".md")):
            if path.is_file() and inside in path.resolve().parents:
                return path
    raise SelfdocError(f"no such doc: {name} (a file in the repository, from its root or under {SELF_REL}/)")


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
    """Heading text compared without case, runs of spaces or backticks, so a command can name a heading that has code
    spans without quoting a backtick (PowerShell's escape character)."""
    return " ".join(text.replace("`", "").split()).casefold()


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


def print_sections(pairs, root=KB):
    """Print the sections of each (doc, heading) pair in order, a blank line between pairs; a heading that matches
    none prints `NO SECTION` with its doc's headings. 0 when every heading matched, else 1."""
    missing = 0
    for n, (doc, heading) in enumerate(pairs):
        if n:
            print()
        found, heads = section(doc, heading, root)
        if not found:
            missing += 1
            print(f"NO SECTION {heading!r} in {doc}; headings:")
            for h in heads:
                print(f"  {h}")
            continue
        for block in found:
            print(f"{doc}:{block[0][0]}-{block[-1][0]}")
            for no, ln in block:
                print(f"{no}: {ln}")
    return 1 if missing else 0


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


def lf_lines(text):
    """The lines of TEXT split on LF alone, as the tokenizer and `ast` count them: `str.splitlines` also breaks at U+2028,
    U+2029, U+0085, form feed and the other separators, which would shift every line number after one in a string."""
    lines_ = text.split("\n")
    if lines_[-1] == "":
        lines_.pop()
    return lines_


def first_line(doc):
    """The first line of a docstring, cut to DOC_MAX characters; empty for none."""
    lines_ = lf_lines((doc or "").strip())
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
                src[path] = lf_lines((base / path).read_text(encoding="utf-8"))
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
    w = s.add_mutually_exclusive_group()
    w.add_argument("--since", metavar="REV", help="compare REV with the working tree instead of each doc's last commit")
    w.add_argument("--work", metavar="ID", action="append",
                   help="only what the commits whose KB-Work trailer names ID changed (repeatable): an item's check")
    m = sub.add_parser("map", help="the docs that describe these paths")
    m.add_argument("paths", nargs="+")
    sub.add_parser("check", help="map rows naming a missing doc or matching no file; _self docs with no row; "
                                   "(doc, Section) references to a missing heading")
    c = sub.add_parser("section", help="sections of docs, with line numbers: one or more DOC HEADING pairs")
    c.add_argument("pairs", nargs="+", metavar="DOC HEADING",
                   help="DOC: path from the repository root, or a name under kb/_self; HEADING: the heading's text "
                        "(case-insensitive), `## text` pins the level")
    t = sub.add_parser("map-tools", help="the symbols and tests of _tools/*.py, with file:line")
    t.add_argument("file", metavar="FILE", nargs="?", help="one file: a path, or a name under _tools (`rag`)")
    a = ap.parse_args(argv)
    if a.cmd == "section" and len(a.pairs) % 2:
        c.error(f"section takes DOC HEADING pairs; {a.pairs[-1]!r} has no HEADING")
    try:
        if a.cmd == "map-tools":
            out = map_tools(a.file)
            print("\n".join(out))
            kinds = [MAP_LINE_RX.match(ln)["kind"] for ln in out]
            print(f"files={kinds.count('module') + kinds.count('unparsed')} symbols={len(kinds) - kinds.count('module') - kinds.count('unparsed')}")
            return 0
        if a.cmd == "section":
            return print_sections(list(zip(a.pairs[::2], a.pairs[1::2])))
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
        result = stale(since=a.since, work=a.work)
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
