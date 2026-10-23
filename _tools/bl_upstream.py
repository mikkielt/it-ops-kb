"""`backlog.py upstream-report` and `upstream-import` (kb/_self/backlog.md, Item commands, Upstream reports): the
clone's own items written as one issue body for the upstream, in the sections of
`.github/ISSUE_TEMPLATE/upstream-report.yml`, and, in the upstream, that body read back into draft stories. The report
writes a file and posts nothing; the operator pastes the file into a new issue or runs `gh issue create --body-file`
themselves. The import reads a saved file and files drafts; it fetches nothing.

Standard library only; imports `bl_base`, `bl_check` (the leak scan) and `bl_cli`, never `backlog`. It registers
its command with `bl_cli` itself when imported, and `backlog.py`'s USAGE puts it in the usage order."""
import re
import shlex
from pathlib import Path

import bl_cli
from bl_base import TEXT_MAX, Backlog, Refused, Rejected, clone_id, commit_written, new_id, say, withhold
from bl_check import item_leak_hits

TEMPLATE = ".github/ISSUE_TEMPLATE/upstream-report.yml"
NONE_RECORDED = "none recorded"
NOTE_LINES = {"premise": re.compile(r"^\s*Premise:\s*(.+)$", re.M), "local": re.compile(r"^\s*Local change:\s*(.+)$", re.M)}


def note_line(it, key):
    """The text after the first `Premise:` (or `Local change:`) line of an item's notes, or ''."""
    m = NOTE_LINES[key].search(it.get("notes") or "")
    return m.group(1).strip() if m else ""


def premise_text(it):
    """What shows the problem now: a bug's repro command (with its reason), else the notes' `Premise:` line."""
    if it.get("repro"):
        run = it["repro"].get("run") if isinstance(it["repro"], dict) else it["repro"]
        cmd = run if isinstance(run, str) else shlex.join(map(str, run or []))
        reason = f"\n\n{it['repro_reason']}" if it.get("repro_reason") else ""
        return f"Repro, which fails now:\n\n```\n{cmd}\n```{reason}"
    return note_line(it, "premise") or NONE_RECORDED


def local_change_text(it):
    """The clone's change made meanwhile: the notes' `Local change:` line, else a done item's touches."""
    got = note_line(it, "local")
    if got:
        return got
    if it.get("status") == "done" and it.get("touches"):
        return "Done in this clone, touching: " + ", ".join(f"`{t}`" for t in it["touches"])
    return NONE_RECORDED


def story_sections(it):
    """The four sections of one user story, as the issue form renders its fields."""
    parts = (("Title", it.get("title", "")), ("Goal", it.get("goal") or NONE_RECORDED),
             ("Premise or repro", premise_text(it)), ("Local change made meanwhile", local_change_text(it)))
    return "\n\n".join(f"### {label}\n\n{text}" for label, text in parts)


def scope_of(root):
    import kbpublic
    return kbpublic.clone_scope(str(root)) or "unset"


def clone_allowlist(root):
    """The clone's leak-scan allowlist (_tools/tests_allowlist.txt), or {} when it has none."""
    import kbpublic
    path = Path(root) / kbpublic.ALLOWLIST_PATH
    try:
        return kbpublic.parse_allowlist(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, UnicodeDecodeError):
        return {}


def report_body(bl, ids):
    """The issue body for the clone's items IDS: the clone's scope once, then each item's story sections, split by a rule."""
    for iid in ids:
        if iid not in bl.items:
            raise Rejected(f"no item {iid} in this clone (`backlog.py find WORD` names the items)")
        if bl.items[iid].get("kind") == "sprint":
            raise Rejected(f"{bl.label(iid)} is a sprint: report its stories or bugs")
        if bl.is_upstream(iid):
            raise Refused(f"{bl.label(iid)} arrived from the upstream main: an upstream report holds this clone's own "
                          "items (the upstream already has that one)")
    stories = "\n\n---\n\n".join(story_sections(bl.items[i]) for i in ids)
    body = f"### Clone scope\n\n{scope_of(bl.root)}\n\n{stories}\n"
    kinds = sorted({k for k, _ in item_leak_hits(body, clone_allowlist(bl.root))})
    if kinds:
        raise Refused(f"the report holds a leak-scan hit ({', '.join(kinds)}; value not printed): write a placeholder "
                      "in the item instead (kb/_self/backlog.md, Writing about items)")
    return withhold(body)


def cmd_upstream_report(bl: Backlog, a):
    ids = list(dict.fromkeys(a.ids))
    body = report_body(bl, ids)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    for iid in ids:
        say(f"upstream-report: {bl.label(iid)}")
    say(f"upstream-report: wrote {len(ids)} user stor{'y' if len(ids) == 1 else 'ies'} to {out}; nothing was posted: "
        "paste the file into a new issue (form: " + TEMPLATE + ") or run `gh issue create --body-file "
        f"{out}` yourself")
    return 0


def args_upstream_report(p):
    p.add_argument("ids", nargs="+", metavar="ID", help="this clone's items to report")
    p.add_argument("--out", required=True, metavar="FILE", help="the file the issue body is written to")


FIELDS = {"title": "Title", "goal": "Goal", "premise": "Premise or repro", "local": "Local change made meanwhile"}
NO_RESPONSE = {"", "_no response_", NONE_RECORDED}
SCOPE_HEADING = "Clone scope"


def sections(text):
    """[(heading, content)] of the `### ` sections of an issue body, in order; a `### ` line inside a code fence is text.
    What precedes the clone scope section (the metadata `gh issue view` prints) is dropped."""
    rows, fenced = [], False
    for line in text.replace("\r\n", "\n").split("\n"):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        m = None if fenced else re.match(r"^### (.+?)\s*$", line)
        if m:
            rows.append([m.group(1), []])
        elif rows:
            rows[-1][1].append(line)
    out = []
    for heading, lines in rows:
        body = re.sub(r"\n*^---\s*$\s*\Z", "", "\n".join(lines).strip(), flags=re.M).strip()
        out.append((heading, "" if body.lower() in NO_RESPONSE else body))
    return out


def parse_report(text):
    """(clone scope, [{title, goal, premise, local}]) of an upstream-report issue body; Rejected when it is not one."""
    rows = sections(text)
    scope = next((c for h, c in rows if h == SCOPE_HEADING), None)
    if scope is None:
        raise Rejected(f"the file holds no `### {SCOPE_HEADING}` section: it is not an upstream-report issue body "
                       f"({TEMPLATE})")
    stories, key_of = [], {v: k for k, v in FIELDS.items()}
    for heading, content in rows:
        key = key_of.get(heading)
        if key == "title":
            stories.append({"title": content})
        elif key and stories:
            stories[-1][key] = content
    if not stories:
        raise Rejected("the issue body holds no `### Title` section: it has no user story")
    for n, s in enumerate(stories, 1):
        for key in ("title", "goal"):
            if not s.get(key):
                raise Rejected(f"user story {n} has no {FIELDS[key]} section text: fix the issue or the file")
        if "\n" in s["title"]:
            raise Rejected(f"user story {n}: the Title is one line")
    return (scope.splitlines() or ["unset"])[0].strip(), stories


def imported_ids(bl, url):
    """The items whose links name the issue URL (the first word of a link), as the import wrote them."""
    key = url.rstrip("/")
    return [i for i, it in bl.items.items()
            if any(isinstance(x, str) and x.split()[:1] and x.split()[0].rstrip("/") == key for x in it.get("links") or [])]


def story_notes(s, issue):
    """The notes of an imported draft: where it came from, then the premise and local change as the clone reported them
    (the `Premise:` and `Local change:` lines `upstream-report` reads back)."""
    lines = [f"Imported from upstream-report issue {issue}."]
    for label, key in (("Premise", "premise"), ("Local change", "local")):
        if s.get(key):
            lines.append(f"{label}: {s[key]}")
    return "\n\n".join(lines)[:TEXT_MAX]


def cmd_upstream_import(bl, a):
    path = Path(a.file)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise Rejected(f"cannot read {path} as UTF-8 text: {e}") from e
    url = a.issue.strip()
    if not re.match(r"^https?://\S+$", url):
        raise Rejected(f"--issue {url!r} is not the issue's url")
    have = imported_ids(bl, url)
    if have:
        say(f"upstream-import: {url} was imported as {', '.join(bl.label(i) for i in have)}: nothing filed")
        return 0
    scope, stories = parse_report(text)
    allow = clone_allowlist(bl.root)
    for s in stories:
        kinds = sorted({k for k, _ in item_leak_hits(" ".join(s.values()), allow)})
        if kinds:
            raise Refused(f"the issue holds a leak-scan hit ({', '.join(kinds)}; value not printed) in user story "
                          f"{s['title']!r}: nothing filed; edit the file to a placeholder first")
    filed_in = clone_id(bl.root, create=True)
    ids = []
    for s in stories:
        it = {"id": new_id("story"), "kind": "story", "title": s["title"][:TEXT_MAX], "status": "draft",
              "priority": "P2", "rank": 0, "goal": s["goal"][:TEXT_MAX],
              "links": [f"{url} (upstream-report, clone scope: {scope})"], "notes": story_notes(s, url)}
        if filed_in:
            it["filed_in"] = filed_in
        bl.save(it)
        ids.append(it["id"])
        say(f"upstream-import: draft story {bl.label(it['id'])}")
    say(f"upstream-import: filed {len(ids)} draft stor{'y' if len(ids) == 1 else 'ies'} outside any sprint from {url} "
        f"(clone scope {scope}); triage them as any other draft")
    commit_written(bl, a, "file", ids[0], ids)
    return 0


def args_upstream_import(p):
    p.add_argument("file", metavar="FILE", help="the issue body, a saved file (gh issue view --json body -q .body, or its plain output)")
    p.add_argument("--issue", required=True, metavar="URL", help="the issue's url, which every draft links")
    p.add_argument("--commit", action="store_true", help="commit the item files written, alone, with KB-Work naming them")
    p.add_argument("--trailer", action="append", default=[], metavar="'KEY: VALUE'",
                   help="a trailer of the session's own after KB-Work in the --commit commit (repeatable)")


bl_cli.register("upstream-import", cmd_upstream_import, args_upstream_import,
                help="file the user stories of a saved upstream-report issue as draft stories that link the issue")
bl_cli.register("upstream-report", cmd_upstream_report, args_upstream_report,
                help="write this clone's items as an upstream issue body (user stories); posts nothing")
