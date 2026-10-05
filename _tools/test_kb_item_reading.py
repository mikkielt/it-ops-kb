"""What the kb-item skill makes a session read first, and how it ends.

test_kb_item_reading_bound: the `selfdoc.py section` command at the top of the kb-item skill prints at most
READING_BOUND bytes over the live kb/_self docs: the runbook sections that working one item needs, with the reference
material (landing mechanics, sprint rules, bug intake, processes, self-check, stalled work) under headings of its own.
test_kb_item_reading_bound_planted_failures: a fixture doc whose section is over the bound fails, and so do a skill
with no reading command and a command naming a heading the doc lacks.
test_kb_item_land_and_session / _planted_failures: step 7 starts `land` in the background with the longest timeout,
since a foreground command is lost at the 10-minute limit, and step 8 starts the next item in a fresh session.
"""
import contextlib
import io
import os
import re
import shlex

import selfdoc
from conftest import KB

KB_ITEM = ".claude/skills/kb-item/SKILL.md"
READING_BOUND = 30000  # bytes the kb-item reading command may print; each byte stays in context on every later turn
COMMAND_RX = re.compile(r"(?m)^python3 _tools/selfdoc\.py section .+$")


def skill_text():
    with open(os.path.join(KB, KB_ITEM), encoding="utf-8") as f:
        return f.read()


def reading_pairs(skill):
    """[(doc, heading)] of the skill's first `selfdoc.py section` command, or None when it has none."""
    m = COMMAND_RX.search(skill)
    if not m:
        return None
    args = shlex.split(m.group(0))[3:]
    return list(zip(args[0::2], args[1::2])) if args and len(args) % 2 == 0 else None


def reading_problems(skill, root=KB, bound=READING_BOUND):
    """What is wrong with the skill's reading command over the docs under ROOT: [] when it prints every section it
    names in at most BOUND bytes."""
    pairs = reading_pairs(skill)
    if not pairs:
        return ["the kb-item skill has no `selfdoc.py section DOC HEADING ...` reading command"]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = selfdoc.print_sections(pairs, root)
    problems = [] if code == 0 else [f"the reading command names a heading its doc lacks: {out.getvalue()[:200]!r}"]
    size = len(out.getvalue().encode("utf-8"))
    if size > bound:
        problems.append(f"the kb-item reading command prints {size} bytes, over the bound of {bound}: move reference "
                        "material out of the sections it names, under headings of its own")
    return problems


def test_kb_item_reading_bound():
    assert reading_problems(skill_text()) == []


def write_doc(root, rel, text):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def test_kb_item_reading_bound_planted_failures(tmp_path):
    root = str(tmp_path)
    skill = "Read:\n\n```\npython3 _tools/selfdoc.py section backlog \"Working on items\"\n```\n"
    small = "# Backlog\n\n## Working on items\n\n- claim it.\n\n## Landing\n\n" + "reference. " * 4000 + "\n"
    write_doc(root, f"{selfdoc.SELF_REL}/backlog.md", small)
    assert reading_problems(skill, root) == [], "a small section under the bound passes"
    big = "# Backlog\n\n## Working on items\n\n" + "- a rule a worker of one item does not need.\n" * 800
    write_doc(root, f"{selfdoc.SELF_REL}/backlog.md", big)
    assert any("over the bound" in p for p in reading_problems(skill, root)), "a section over the bound fails"
    assert reading_problems("no command here", root), "a skill with no reading command fails"
    gone = skill.replace("Working on items", "No Such Heading")
    write_doc(root, f"{selfdoc.SELF_REL}/backlog.md", small)
    assert any("lacks" in p for p in reading_problems(gone, root)), "a heading the doc lacks fails"


def test_kb_item_reading_mapped(monkeypatch):
    """A change to a doc the reading command names, or to the skill, selects this test; another doc does not."""
    import testmap
    me = "_tools/test_kb_item_reading.py"
    for path in ("kb/_self/backlog.md", "kb/_self/maintaining.md", KB_ITEM):
        sel = testmap.select([path])[0]
        assert sel == testmap.ALL or me in sel, (path, sel)
    assert me not in testmap.select(["kb/_self/git.md"])[0]
    docs = {f"{doc if '/' in doc else selfdoc.SELF_REL + '/' + doc}" for doc, _ in reading_pairs(skill_text())}
    docs = {d if d.endswith(".md") else d + ".md" for d in docs}
    assert docs <= testmap.KB_ITEM_READING, docs - testmap.KB_ITEM_READING
    monkeypatch.setattr(testmap, "KB_ITEM_READING", set())  # planted: the map without the rule
    assert me not in testmap.select(["kb/_self/backlog.md"])[0]


def steps(skill):
    """(step 7's text, step 8's text) of the kb-item skill."""
    s7 = re.search(r"(?ms)^7\. \*\*Prove and land\*\*.*?(?=^8\. )", skill)
    s8 = re.search(r"(?ms)^8\. \*\*Report\*\*.*?(?=^\S|\Z)", skill)
    return (s7.group(0) if s7 else ""), (s8.group(0) if s8 else "")


def land_session_problems(skill):
    s7, s8 = steps(skill)
    problems = []
    for phrase in ("in the background", "longest `timeout`", "7200000", "10-minute limit"):
        if phrase not in s7:
            problems.append(f"kb-item step 7 does not say {phrase!r} for `land`")
    for phrase in ("one session works one item", "fresh session"):
        if phrase not in s8:
            problems.append(f"kb-item step 8 does not say {phrase!r}")
    return problems


def test_kb_item_land_and_session():
    assert land_session_problems(skill_text()) == []


def test_kb_item_land_and_session_planted_failures():
    skill = skill_text()
    for old, new in (("in the background", "in the foreground"), ("7200000", "the default"),
                     ("10-minute limit", "limit"), ("one session works one item", "a session works items"),
                     ("fresh session", "same session")):
        planted = skill.replace(old, new, 1)
        assert planted != skill, f"plant does not apply: {old!r}"
        assert land_session_problems(planted), f"not caught: {old!r} -> {new!r}"
