"""The runbook `Starting the autopilot` (kb/_self/backlog.md) says what a first unattended run needs and claims no more
than the code enforces: its seven numbered steps in order under that exact title, the prerequisites of step 2, what the
rehearsal does not test, a way to hold a started sprint back, the digest warning, the recovery commands and the list of
what is enforced and what is not. Its section references name real headings and every `python3 _tools/<script>.py
<subcommand>` it prints names a script and a subcommand that exist (read from the script's own `--help`: no network, no
real run).

Each rule has a planted failure: a copy of the live text with one phrase removed, a step moved or dropped, a dead
heading reference or an unknown script or subcommand added, which `runbook_problems` must name.
"""
import os
import re
import subprocess
import sys

import selfdoc
from conftest import KB, TOOLS

DOC = "kb/_self/backlog.md"
TITLE = "Starting the autopilot"
# what the first unattended run needs the text to say, each as a phrase of the section
PHRASES = {
    "KB_NO_PUBLISH_HOOK": "the manager session exports KB_NO_PUBLISH_HOOK",
    "glab auth status": "the integration remote's sign-in is checked",
    "claude mcp list": "the MCP servers are checked Connected",
    "/kb-setup": "setup is a prerequisite",
    "does not test": "what the rehearsal does not test",
    "hold one back": "how to hold a started sprint back from the first tick",
    "dirties the manager's clone": "the digest command rewrites a tracked file",
    "procs --end": "the recovery of an orphaned runner",
    "Enforced today": "step 7 lists what is enforced",
    "Not enforced": "step 7 lists what is not",
}
CMD_RX = re.compile(r"python3 _tools/(?P<script>[\w-]+\.py)(?: (?P<sub>[a-z][\w-]*))?")
HELP = {}


def section(text):
    """The lines of the section TITLE: from its `## ` heading to the next one, or None when there is no such heading."""
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln == f"## {TITLE}"), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


def help_of(script):
    """The text `python3 _tools/<script> --help` prints (cached), None when it does not run."""
    if script not in HELP:
        p = subprocess.run([sys.executable, os.path.join(TOOLS, script), "--help"], capture_output=True, text=True,
                           encoding="utf-8", timeout=60, cwd=KB)
        HELP[script] = p.stdout + p.stderr if p.returncode == 0 else None
    return HELP[script]


def ref_problems(sec):
    """Each `(kb/_self/<doc>.md, Heading)` reference of SEC whose doc or heading does not exist."""
    problems, cache = [], {}
    for m in selfdoc.SECTION_REF_RX.finditer(sec):
        doc = m["doc"]
        name = doc if doc.startswith("kb/_self/") else f"kb/_self/{doc}"
        if name not in cache:
            path = os.path.join(KB, name)
            cache[name] = selfdoc.heading_keys(open(path, encoding="utf-8").read().splitlines()) if os.path.isfile(path) else None
        keys, ref = cache[name], " ".join(m["sec"].split())
        if keys is None:
            problems.append(f"({doc}, {ref}) names a doc that does not exist")
        elif not selfdoc.names_heading(ref, keys):
            problems.append(f"({doc}, {ref}) names no heading of {name}")
    return problems


def command_problems(sec):
    """Each `python3 _tools/<script> <word>` of SEC whose script is no file of _tools or whose word is no subcommand in
    the script's `--help` (a script with no subcommands lists none: a word it does not show is then an argument)."""
    problems = []
    for m in CMD_RX.finditer(sec):
        script, sub = m["script"], m["sub"]
        if not os.path.isfile(os.path.join(TOOLS, script)):
            problems.append(f"{script}: no such script in _tools/")
            continue
        text = help_of(script)
        if text is None:
            problems.append(f"{script}: --help does not run")
        elif sub and re.search(r"\{[^}]*\}", text) and not re.search(rf"[{{,\s]{re.escape(sub)}[,}}\s]", text):
            problems.append(f"{script} {sub}: not a subcommand its --help lists")
    return problems


def runbook_problems(text):
    """What is wrong with the runbook in TEXT (a copy of backlog.md): empty when it holds every rule."""
    sec = section(text)
    if sec is None:
        return [f"no `## {TITLE}` section"]
    problems = [f"missing: {why} ({phrase!r})" for phrase, why in PHRASES.items() if phrase not in sec]
    numbers = [int(n) for n in re.findall(r"^(\d+)\. \*\*", sec, re.M)]
    if numbers != list(range(1, 8)):
        problems.append(f"the numbered steps are {numbers}, not 1 to 7 in order")
    return problems + ref_problems(sec) + command_problems(sec)


def live():
    with open(os.path.join(KB, DOC), encoding="utf-8") as f:
        return f.read()


def planted(text, old, new):
    """TEXT with OLD replaced by NEW once inside the section; the planting itself must change the text."""
    sec = section(text)
    assert old in sec, f"the planted failure needs {old!r} in the section"
    return text.replace(sec, sec.replace(old, new, 1), 1)


def test_autopilot_runbook_first_run_holds_every_rule():
    assert runbook_problems(live()) == []


def test_autopilot_runbook_first_run_title_is_exact_and_unique():
    text = live()
    assert text.count(f"\n## {TITLE}\n") == 1
    assert runbook_problems(text.replace(f"\n## {TITLE}\n", f"\n## {TITLE} (draft)\n")) == [f"no `## {TITLE}` section"]


def test_autopilot_runbook_first_run_each_phrase_is_planted_and_caught():
    text = live()
    sec = section(text)
    for phrase in PHRASES:
        assert phrase in sec, phrase
        gone = text.replace(sec, sec.replace(phrase, "gone"), 1)
        assert any(repr(phrase) in p for p in runbook_problems(gone)), phrase
        # the check reads the section only: the phrase in another section of the doc does not stand in for it
        elsewhere = gone + f"\n## Another section\n\n{phrase}\n"
        assert any(repr(phrase) in p for p in runbook_problems(elsewhere)), phrase


def test_autopilot_runbook_first_run_steps_are_seven_in_order():
    text = live()
    sec = section(text)
    assert re.findall(r"^(\d+)\. \*\*", sec, re.M) == [str(n) for n in range(1, 8)]
    dropped = planted(text, "5. **Read what it did**", "**Read what it did**")
    assert any("not 1 to 7" in p for p in runbook_problems(dropped))
    moved = planted(planted(text, "6. **Stop it**", "9. **Stop it**"), "7. **What the autopilot", "6. **What the autopilot")
    assert any("not 1 to 7" in p for p in runbook_problems(moved))


def test_autopilot_runbook_first_run_section_references_resolve():
    sec = section(live())
    assert ref_problems(sec) == []
    assert selfdoc.SECTION_REF_RX.search(sec), "the section names no (doc, Heading) reference to check"
    bad = "(`kb/_self/git.md`, No Such Heading)"
    assert ref_problems(sec + "\n" + bad) == ["(kb/_self/git.md, No Such Heading) names no heading of kb/_self/git.md"]
    gone = "(`kb/_self/no-such-doc.md`, Anything)"
    assert ref_problems(sec + "\n" + gone) == ["(kb/_self/no-such-doc.md, Anything) names a doc that does not exist"]


def test_autopilot_runbook_first_run_commands_name_real_scripts_and_subcommands():
    sec = section(live())
    found = CMD_RX.findall(sec)
    assert {s for s, _ in found} >= {"autopilot_rehearse.py", "backlog.py", "autopilot.py"}, found
    assert command_problems(sec) == []
    assert command_problems("run `python3 _tools/no_such_tool.py go`") == ["no_such_tool.py: no such script in _tools/"]
    assert command_problems("run `python3 _tools/backlog.py nosuchsub`") == ["backlog.py nosuchsub: not a subcommand its --help lists"]
    assert command_problems("run `python3 _tools/autopilot.py runner-status SP`") == []
    assert command_problems("run `python3 _tools/autopilot.py runnerstatus SP`") == ["autopilot.py runnerstatus: not a subcommand its --help lists"]
