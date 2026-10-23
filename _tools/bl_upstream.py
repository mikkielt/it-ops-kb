"""`backlog.py upstream-report` (kb/_self/backlog.md, Item commands, Upstream reports): the clone's own items written as
one issue body for the upstream, in the sections of `.github/ISSUE_TEMPLATE/upstream-report.yml`. It writes a file and
posts nothing; the operator pastes the file into a new issue or runs `gh issue create --body-file` themselves.

Standard library only; imports `bl_base`, `bl_check` (the leak scan) and `bl_cli`, never `backlog`. It registers
its command with `bl_cli` itself when imported, and `backlog.py`'s USAGE puts it in the usage order."""
import re
import shlex
from pathlib import Path

import bl_cli
from bl_base import Backlog, Refused, Rejected, say, withhold
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


bl_cli.register("upstream-report", cmd_upstream_report, args_upstream_report,
                help="write this clone's items as an upstream issue body (user stories); posts nothing")
