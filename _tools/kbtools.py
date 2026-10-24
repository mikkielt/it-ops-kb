"""The catalog of the kb's tools, and the few that answer a need (stdlib only; kb/_self/tools.md).

The catalog has one entry for each command-line tool of `_tools/` (a `_tools/*.py` with an `if __name__ == "__main__"`
guard), each skill (`.claude/skills/*/SKILL.md`), each agent (`.claude/agents/*.md`) and each tool the kb MCP server can serve, whatever the environment of the run (the
live-docs, coord and backlog-write tools included).
A tool's entry is read from the end of its module docstring with `ast`, never by importing it: the block from the first
`Answers:` line to the end holds `Answers:` lines (a question the tool answers, in plain words), `Use:` lines (its command)
and `MCP:` lines (the kb MCP tools that run it), an indented line continuing the line above it. A skill's or an agent's
entry is its frontmatter `description:`, a kb MCP tool's its listed description. `selfdoc.py check` and the kb panel of
`kbmon.py` read the same block through `tool_entries` and `missing_lines`.

A need is matched by words: lower-case words with their endings cut, the common ones dropped, each weighed by how few
entries hold it, a word of an entry's name counting double (a name of several words, `querylog.py`, holds the words of
the need that spell it, `query log`) and a word of a skill's, agent's or kb MCP tool's description counting less, the
longer the description is. The same need always gives the same entries, best first.
`answering` is the stricter read `kb_ask.py` routes by: it leaves the words that only ask for a tool (CUES) out of the
need, reads a tool's name and its own text (summary and `Answers:` lines) and the name alone of a skill, an agent or a kb
MCP tool (their descriptions list the products the kb covers), and reports how much of the need the catalog holds.

  kbtools.py [--json]            the catalog, one line for each entry: its name, its command and what it answers
  kbtools.py NEED [--json]       the best entries for NEED (at most 8, none for a need no entry shares a word with);
                                 --json prints {"need", "entries": [{"tool", "kind", "command", "answers", "mcp"}]}

Answers: which tool, skill, agent or kb MCP tool answers a need, in plain words
Answers: what the kb's command-line tools are and what each one answers
Use: python3 _tools/kbtools.py [NEED] [--json]
MCP: kb_tools names the tools, skills and agents that answer a need
"""
import argparse
import ast
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN_GUARD = re.compile(r"""__name__\s*==\s*['"]__main__['"]""")
KEYS = ("Answers", "Use", "MCP")
KEY_LINE = re.compile(r"\s*(Answers|Use|MCP):\s*(.*)")
WORD = re.compile(r"[a-z0-9]+")
STOP = frozenset("""a an the of to in on for and or is are was be been am it its i my me we our you your with without from by at as
that this these those there then than what which who whom whose when where why how do does did can could should would will may
might must not no so if about into onto over under up out all any each some""".split())
LIMIT = 8
CUES = frozenset("tool command script line find show list print give tell get run use".split())  # asks for a tool, names none
KIND_ORDER = {"tool": 0, "skill": 1, "agent": 2, "mcp": 3}
DESC_CAP = 0.6  # most a word of a skill's, agent's or kb MCP tool's description counts, against 1 for a tool's own text
DESC_REF = 16  # words of such a description from which each of its words counts less
WIDTH = 150  # characters of what an entry answers on a catalog line
BOILERPLATE = re.compile(r"^(Documentation facts from it-ops-kb \(not live device or directory data\)\.\s*)")


def read(path):
    return Path(path).read_text(encoding="utf-8")


def module_doc(path):
    """The module docstring of a file, read with `ast`; '' when it has none or the file does not parse."""
    try:
        return ast.get_docstring(ast.parse(read(path))) or ""
    except (OSError, SyntaxError, ValueError):
        return ""


def is_cli(path):
    """True for a file with an `if __name__ == "__main__"` guard: a command-line tool."""
    try:
        return bool(MAIN_GUARD.search(read(path)))
    except OSError:
        return False


def cli_files(root=ROOT):
    return [p for p in sorted(Path(root, "_tools").glob("*.py")) if is_cli(p)]


def tail_fields(doc):
    """{"Answers": [...], "Use": [...], "MCP": [...]} read from the first `Answers:` or `Use:` line of a docstring to its
    end; an indented line goes on the line above it. All three are empty when the docstring has neither line."""
    out = {k: [] for k in KEYS}
    lines = doc.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip().startswith(("Answers:", "Use:"))), None)
    last = None
    for line in lines[start:] if start is not None else []:
        m = KEY_LINE.match(line)
        if m:
            out[m.group(1)].append(m.group(2).strip())
            last = out[m.group(1)]
        elif line.strip() and line[:1].isspace() and last:
            last[-1] = f"{last[-1]} {line.strip()}".strip()
    return out


def missing_lines(doc):
    """The keys of Answers and Use that the end of a docstring lacks, in that order."""
    got = tail_fields(doc)
    return [k for k in ("Answers", "Use") if not any(got[k])]


def cut(text, width=WIDTH):
    text = " ".join(text.split())
    return text if len(text) <= width else text[:width - 3].rstrip() + "..."


def tool_entries(root=ROOT):
    """One entry for each command-line tool: name (the file name), the fields of its docstring tail and its first line."""
    out = []
    for p in cli_files(root):
        doc = module_doc(p)
        got = tail_fields(doc)
        out.append({"tool": p.name, "kind": "tool", "command": got["Use"][0] if got["Use"] else "",
                    "answers": got["Answers"], "mcp": got["MCP"], "summary": (doc.splitlines() or [""])[0].strip(),
                    "missing": missing_lines(doc)})
    return out


def front(path):
    """The single-line `key: value` pairs of a Markdown file's front matter."""
    m = re.match(r"---\n(.*?)\n---", read(path), re.S)
    return dict(re.findall(r"^([A-Za-z_-]+):[ \t]*(.*)$", m.group(1), re.M)) if m else {}


def description_entries(root=ROOT):
    """The skills (name: the directory's, else the frontmatter's) and agents (name: the frontmatter's) by their descriptions."""
    out = []
    for p in sorted(Path(root, ".claude", "skills").glob("*/SKILL.md")):
        f = front(p)
        out.append({"tool": f.get("name") or p.parent.name, "kind": "skill", "command": f"/{f.get('name') or p.parent.name}",
                    "answers": [f.get("description", "")], "mcp": [], "summary": ""})
    for p in sorted(Path(root, ".claude", "agents").glob("*.md")):
        f = front(p)
        out.append({"tool": f.get("name") or p.stem, "kind": "agent", "command": "agent",
                    "answers": [f.get("description", "")], "mcp": [], "summary": ""})
    return [e for e in out if e["answers"][0]]


def mcp_entries(root=ROOT):
    """Every tool the kb MCP server can serve, by their descriptions, whatever the environment; none when it cannot be loaded."""
    sys.path.insert(0, str(Path(root, "_tools")))
    try:
        import kb_mcp
        listed = kb_mcp.tool_list(every=True)
    except Exception:  # noqa: BLE001 - a server that does not load leaves its tools out of the catalog
        return []
    return [{"tool": t["name"], "kind": "mcp", "command": "MCP tool",
             "answers": [BOILERPLATE.sub("", t.get("description", ""))], "mcp": [], "summary": ""} for t in listed]


def catalog(root=ROOT):
    return tool_entries(root) + description_entries(root) + mcp_entries(root)


def answer_text(entry):
    return "; ".join(a for a in entry["answers"] if a)


def line_of(entry):
    """The one catalog line of an entry: name, command, what it answers (cut at WIDTH characters)."""
    names = [n for e in entry["mcp"] for n in re.findall(r"\b(?:kb|docs|coord)_\w+", e)]
    mcp = f" [MCP: {', '.join(names)}]" if names else ""
    return " ".join(f"{entry['tool']}  {entry['command']}  - {cut(answer_text(entry)) or 'no Answers: line'}{mcp}".split())


def stem(word):
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            word = word[:-len(suffix)]
            break
    if word.endswith("e") and len(word) > 3:
        word = word[:-1]
    return word[:-1] if len(word) > 3 and word[-1] == word[-2] and word[-1] not in "aeiouls" else word


def words(text):
    return {stem(w) for w in WORD.findall(text.lower().replace("_", " ")) if w not in STOP and len(w) > 1}


def name_words(name, need):
    """The words of an entry's name, and the words of NEED that spell a name of several words together: the name
    `querylog.py` holds `query` and `log` for the need `query log`, as `query_log` holds `querylog` for that need."""
    named, asked = WORD.findall(name.lower()), WORD.findall(need.lower())
    out = words(name)
    for size in (2, 3):
        for i in range(len(asked) - size + 1):
            if "".join(asked[i:i + size]) in named:
                out |= words(" ".join(asked[i:i + size]))
        for i in range(len(named) - size + 1):
            if "".join(named[i:i + size]) in asked:
                out |= words(" ".join(named[i:i + size]))
    return out


def text_weight(entry, text):
    """How much a word of an entry's own text counts: in full for a tool, whose `Answers:` lines list the needs it answers;
    for a skill, an agent or a kb MCP tool at most DESC_CAP, and less for each word of a description beyond DESC_REF
    words: it says when to use the entry and names whatever it mentions (long in `Long it-ops-kb research`)."""
    return 1.0 if entry["kind"] == "tool" else min(DESC_CAP, DESC_REF / max(len(text), 1))


def rank(need, want, docs):
    """The entries of `docs` ((entry, name words, text words) for each) that share a word of WANT, best first: the sum of
    each shared word's weight (rarer in the catalog weighs more; in an entry's name twice, in its text as text_weight
    says), ties broken by kind and name; entries under a third of the best score drop."""
    docs = [(e, name_words(e["tool"], need), text) for e, _, text in docs]
    df = {w: sum(1 for _, n, t in docs if w in n or w in t) for w in want}
    scored = []
    for e, name, text in docs:
        weight = text_weight(e, text)
        score = sum(math.log(1 + len(docs) / df[w]) * (2 if w in name else weight) for w in want if w in name or w in text)
        if score > 0:
            scored.append((-score, KIND_ORDER[e["kind"]], e["tool"], e))
    scored.sort(key=lambda x: x[:3])
    best = -scored[0][0] if scored else 0
    return [dict(e, score=round(-s, 3)) for s, _, _, e in scored if -s * 3 >= best][:LIMIT], df


def search(need, entries):
    """The entries that share a word with NEED, best first (`rank`)."""
    docs = [(e, words(e["tool"]), words(" ".join([e["summary"], *e["answers"]]))) for e in entries]
    return rank(need, words(need), docs)[0]


def answering(need, entries):
    """(entries, held, total): the entries that answer NEED by its content words, and how many of its content words (the
    words that remain once the CUES that only ask for a tool are left out) the catalog holds in an entry's name or own text.
    A tool is read by its name, summary and `Answers:` lines, a skill, an agent or a kb MCP tool by its name alone: their
    descriptions hold the names of the products the kb covers, which answer nothing about a tool. Ranked as `search` does."""
    want = words(need) - {stem(c) for c in CUES}
    docs = [(e, words(e["tool"]), words(" ".join([e["summary"], *e["answers"]])) if e["kind"] == "tool" else set())
            for e in entries]
    found, df = rank(need, want, docs)
    return found, sum(1 for w in want if df[w]), len(want)


def as_json(entry):
    keep = {k: entry[k] for k in ("tool", "kind", "command", "answers", "mcp")}
    return dict(keep, **({"score": entry["score"]} if "score" in entry else {}))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="kbtools.py", description="The catalog of the kb's tools, or the few that answer NEED.")
    ap.add_argument("need", nargs="*", help="what you need, in plain words; none prints the whole catalog")
    ap.add_argument("--json", action="store_true", help="print JSON, {entries: [...]}")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    need = " ".join(args.need).strip()
    entries = search(need, catalog()) if need else catalog()
    if args.json:
        print(json.dumps({"need": need, "entries": [as_json(e) for e in entries]}, indent=2, ensure_ascii=False))
    elif entries:
        print("\n".join(line_of(e) for e in entries))
    else:
        print(f"no tool, skill, agent or MCP tool shares a word with: {need}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
