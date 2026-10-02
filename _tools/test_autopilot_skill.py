"""The /kb-autopilot skill (.claude/skills/kb-autopilot/SKILL.md), the manager's one tick under /loop, holds its contract:

- it is well formed: the front matter names the directory, the description starts with its trigger, `AGENTS.md` lists
  the skill and stays under its cap, and the tick's steps come in order (`-k autopilot_skill_well_formed`);
- each command it names exists: its script, its subcommand and each `--flag` it gives parse with `--help`
  (`-k autopilot_skill_commands`);
- each judgment step runs in a subagent whose JSON keys the skill names, it holds a Compact Instructions section, and
  PushNotification is named only in the notify step, which keeps it to the gates the autopilot may not answer
  (`-k autopilot_skill_contract`);
- it holds no instruction to write memory (`-k autopilot_skill_no_memory`);
- the change router routes a request to run the autopilot to it, and one that only names autopilot.py elsewhere
  (`-k autopilot_skill_routed`).

Each rule is a function over the skill's text, so a planted failure (the text with a part removed or a bad part added)
proves the rule fails when broken."""
import importlib.util
import os
import re
import shlex

import pytest

from conftest import KB, run, text

SKILL = ".claude/skills/kb-autopilot/SKILL.md"
CAP = 4096
STEPS = ["Orient", "Intake", "Exited runners", "Open gates", "Refill to two runners", "Orphans", "Digest", "Notify",
         "Record the tick"]
KEYS = {  # subagent -> the keys of the one JSON object it returns
    "triage": ["keep", "drop", "merge", "why"],
    "review": ["verdict", "confirm", "change", "gaps"],
    "retrospective": ["stories", "no_change"],
    "plan": ["sprint", "goal", "items", "stop"],
    "research": ["sprint", "done", "gaps"],
}
NEEDED = ["intake --file --network", "procs --record", "procs --end", "answer ITEM GATE --confirm --by autopilot",
          "--by autopilot --record", "runner start", "run_in_background", "autopilot.py status", "kbdecide.py digest"]
NEGATION = re.compile(r"\b(never|no|not|without)\b|n't", re.I)
MEMORY = re.compile(r"memor|MEMORY\.md|\.claude/projects", re.I)


def skill_text():
    return text(SKILL) or ""


def front_matter(skill):
    return skill.split("\n---", 1)[0] if skill.startswith("---\n") else ""


def step(skill, name):
    """The tick's step NAME: from its numbered line to the next numbered line or heading."""
    m = re.search(rf"(?m)^\d+\. \*\*{re.escape(name)}\.\*\*.*?(?=^\d+\. \*\*|^## |\Z)", skill, re.S)
    return m.group(0) if m else ""


def well_formed_problems(skill, agents):
    out = []
    fm = front_matter(skill)
    if not fm:
        return ["no front matter"]
    name = re.search(r"(?m)^name:\s*(\S+)", fm)
    if not name or name.group(1) != "kb-autopilot":
        out.append("name is not kb-autopilot (the directory's)")
    desc = re.search(r"(?m)^description:\s*(.+)", fm)
    if not desc or not desc.group(1).startswith("Use ") or len(desc.group(1)) < 40:
        out.append("description missing, short, or not starting with its trigger (Use when ...)")
    if re.search(r"(?m)^disable-model-invocation: true$", fm):
        out.append("a skill that changes the kb stays model-invocable")
    if "kb/_self/" not in skill:
        out.append("names no kb/_self/ doc it follows")
    if "`/kb-autopilot`" not in agents:
        out.append("AGENTS.md does not list /kb-autopilot")
    if len(agents.encode("utf-8")) > CAP:
        out.append(f"AGENTS.md is over {CAP} bytes")
    at = [skill.find(f"**{s}.**") for s in STEPS]
    if -1 in at or at != sorted(at):
        out.append("the tick's steps are missing or out of order: " + ", ".join(STEPS))
    if "/loop" not in skill:
        out.append("does not say it runs under /loop")
    for part in ("/kb-sprint review", "/kb-sprint close"):
        if part not in skill:
            out.append(f"does not point to {part}")
    return out


def commands(skill):
    """Every `python3 _tools/X.py ...` or `X.py ...` in a code span of the skill: (script, subcommand words, flags).
    The selfdoc section command is left to test_selfdoc's skill-section checks."""
    found = []
    for span in re.findall(r"`((?:python3 _tools/)?[a-z_]+\.py [^`]+)`", skill):
        try:
            words = shlex.split(span)
        except ValueError:
            words = span.split()
        if words[0] == "python3":
            words = words[1:]
        else:  # `backlog.py procs --end`: the tool's name without its directory
            words[0] = "_tools/" + words[0]
        script, args = words[0], words[1:]
        if script.endswith("selfdoc.py"):
            continue
        subs = []
        for w in args:
            if len(subs) < 2 and re.fullmatch(r"[a-z][a-z-]*", w):
                subs.append(w)
            else:
                break
        found.append((script, tuple(subs), tuple(w for w in args if re.fullmatch(r"--[a-z][a-z-]*", w))))
    return found


def help_text(script, subs):
    """(the --help text of the command, None), or (None, what is wrong): the script, its first subcommand and, when the
    first one has nested subcommands (`{a,b}` in its help), the second must each parse."""
    if not subs:
        rc, out = run(script, "--help")
        return (out, None) if rc == 0 else (None, "does not parse with --help")
    rc, out = run(script, subs[0], "--help")
    if rc != 0:
        return None, f"{subs[0]} does not parse with --help"
    if len(subs) == 2:
        rc2, out2 = run(script, *subs, "--help")
        if rc2 == 0:
            return out2, None
        if re.search(r"\{[^}]*\}", out):
            return None, f"unknown subcommand {subs[1]}"
    return out, None


def command_problems(skill):
    out = []
    found = commands(skill)
    if not found:
        return ["no command found"]
    helps = {}
    for script, subs, flags in found:
        key = (script, subs)
        if key not in helps:
            helps[key] = help_text(script, subs)
        h, bad = helps[key]
        label = " ".join((script, *subs))
        if bad:
            out.append(f"{label}: {bad}")
            continue
        out += [f"{label}: no flag {f}" for f in flags if f not in h]
    out += [f"does not name `{n}`" for n in NEEDED if n not in skill]
    return out


def bullet(skill, name):
    m = re.search(rf"(?m)^- \*\*{re.escape(name)}\*\*.*(?:\n(?!- |\n|#).*)*", skill)
    return m.group(0) if m else ""


def contract_problems(skill):
    out = []
    for name, keys in KEYS.items():
        b = bullet(skill, name)
        if not b:
            out.append(f"no subagent bullet for {name}")
            continue
        out += [f"{name}: does not name the key `{k}`" for k in keys if f"`{k}`" not in b]
    if "JSON object" not in skill:
        out.append("does not ask each subagent for one JSON object")
    compact = skill.split("## Compact Instructions", 1)[1] if "## Compact Instructions" in skill else ""
    if not compact:
        out.append("no Compact Instructions section")
    else:
        out += [f"Compact Instructions does not keep {w}" for w in ("tick number", "runners", "gates") if w not in compact]
    notify = step(skill, "Notify")
    if not notify:
        out.append("no Notify step")
    elif not all(w in notify for w in ("kept gate", "`secrets`", "`push`", "Only for")):
        out.append("the Notify step does not keep PushNotification to the gates the autopilot may not answer")
    elif "ToolSearch" not in notify:
        out.append("the Notify step does not load PushNotification with ToolSearch")
    elif not re.search(r"Never for", notify):
        out.append("the Notify step does not say what it is never used for")
    rest = skill.replace(notify, "") if notify else skill
    if "PushNotification" in rest:
        out.append("PushNotification is named outside the Notify step")
    return out


def memory_problems(skill):
    out = []
    for n, line in enumerate(skill.splitlines(), 1):
        for clause in re.split(r"[.;:](?:\s|$)", line):
            if MEMORY.search(clause) and not NEGATION.search(clause):
                out.append(f"line {n}: a clause names memory with no refusal: {clause.strip()!r}")
    if not re.search(r"Never write auto-memory", skill):
        out.append("does not say it never writes auto-memory")
    return out


@pytest.fixture(scope="module")
def skill():
    s = skill_text()
    assert s, f"{SKILL} is missing"
    return s


@pytest.fixture(scope="module")
def agents():
    return text("AGENTS.md") or ""


def test_autopilot_skill_well_formed(skill, agents):
    assert well_formed_problems(skill, agents) == []


@pytest.mark.parametrize("plant, want", [
    (lambda s, a: (s.replace("name: kb-autopilot", "name: kb-autopilote"), a), "name is not kb-autopilot"),
    (lambda s, a: (s.replace("description: Use when", "description: When"), a), "description"),
    (lambda s, a: (s.replace("name: kb-autopilot\n", "name: kb-autopilot\ndisable-model-invocation: true\n"), a),
     "model-invocable"),
    (lambda s, a: (s, a.replace("`/kb-autopilot`", "")), "does not list /kb-autopilot"),
    (lambda s, a: (s, a + "x" * CAP), "over 4096 bytes"),
    (lambda s, a: (s.replace("**Notify.**", "**Tell.**"), a), "out of order"),
    (lambda s, a: (s.replace("**Intake.**", "**Zed.**").replace("**Digest.**", "**Intake.**"), a), "out of order"),
    (lambda s, a: (s.replace("/kb-sprint close", "the close"), a), "does not point to /kb-sprint close"),
    (lambda s, a: (s.replace("kb/_self/", "docs/"), a), "kb/_self/"),
    (lambda s, a: ("no front matter here", a), "no front matter"),
])
def test_autopilot_skill_well_formed_planted_failures(skill, agents, plant, want):
    s, a = plant(skill, agents)
    assert any(want in p for p in well_formed_problems(s, a)), want


def test_autopilot_skill_commands_parse(skill):
    assert command_problems(skill) == []


def test_autopilot_skill_commands_found(skill):
    """The commands the goal names are among those the check reads, so it cannot pass over an empty set."""
    found = {(script_name(s), subs) for s, subs, _ in commands(skill)}
    for want in [("autopilot.py", ("status",)), ("autopilot.py", ("runner", "start")), ("backlog.py", ("intake",)),
                 ("backlog.py", ("procs",)), ("backlog.py", ("answer",)), ("kbdecide.py", ("digest",)),
                 ("backlog.py", ("selfcheck",)), ("kbgit.py", ("sync",))]:
        assert want in found, want


def script_name(script):
    return script.rsplit("/", 1)[-1]


@pytest.mark.parametrize("old, new, want", [
    ("procs --record", "procs --recrod", "no flag --recrod"),
    ("procs --end", "procs --finish", "no flag --finish"),
    ("python3 _tools/backlog.py intake --file", "python3 _tools/backlog.py intak --file", "does not parse"),
    ("python3 _tools/autopilot.py status", "python3 _tools/autopilot.py statuz", "does not parse"),
    ("python3 _tools/autopilot.py runner start SP", "python3 _tools/autopilot.py runner begin SP", "unknown subcommand begin"),
    ("python3 _tools/kbdecide.py digest", "python3 _tools/nosuchtool.py digest", "does not parse"),
    ("intake --file --network", "intake --file", "does not name"),
    ("run_in_background", "the foreground", "does not name"),
])
def test_autopilot_skill_commands_planted_failures(skill, old, new, want):
    assert old in skill, old
    problems = command_problems(skill.replace(old, new, 1))
    assert any(want in p for p in problems), (want, problems)


def test_autopilot_skill_contract(skill):
    assert contract_problems(skill) == []


@pytest.mark.parametrize("name, keys", sorted(KEYS.items()))
def test_autopilot_skill_contract_names_each_key(skill, name, keys):
    """Each subagent's bullet names each of its keys: a key removed from the bullet fails, whatever it is."""
    for k in keys:
        planted = bullet(skill, name).replace(f"`{k}`", "x")
        assert planted != bullet(skill, name)
        assert any(f"`{k}`" in p for p in contract_problems(skill.replace(bullet(skill, name), planted))), (name, k)


@pytest.mark.parametrize("plant, want", [
    (lambda s: s.replace("## Compact Instructions", "## Notes"), "no Compact Instructions"),
    (lambda s: s.replace("the tick number;", "a number;"), "tick number"),
    (lambda s: s.replace("- **plan**", "- **planner**"), "no subagent bullet for plan"),
    (lambda s: s.replace("JSON object", "reply"), "one JSON object"),
    (lambda s: s + "\nCall PushNotification when a sprint ends.\n", "outside the Notify step"),
    (lambda s: s.replace("Only for a kept gate:", "For every gate:"), "does not keep PushNotification"),
    (lambda s: s.replace("(`secrets`, `push`;", "(none;"), "does not keep PushNotification"),
    (lambda s: s.replace("ToolSearch", "the tool list"), "ToolSearch"),
    (lambda s: s.replace("Never for", "Also for"), "never used for"),
])
def test_autopilot_skill_contract_planted_failures(skill, plant, want):
    assert any(want in p for p in contract_problems(plant(skill))), want


def test_autopilot_skill_no_memory(skill):
    assert memory_problems(skill) == []


@pytest.mark.parametrize("plant, want", [
    (lambda s: s + "\nSave what you learn to your auto-memory.\n", "names memory with no refusal"),
    (lambda s: s + "\nWrite the tick to MEMORY.md after each step.\n", "names memory with no refusal"),
    (lambda s: s + "\nNever write a log; save the state to memory.\n", "names memory with no refusal"),
    (lambda s: s + "\nKeep notes under .claude/projects for the next tick.\n", "names memory with no refusal"),
    (lambda s: s.replace("Never write auto-memory", "Keep to the state file"), "never writes auto-memory"),
])
def test_autopilot_skill_no_memory_planted_failures(skill, plant, want):
    assert any(want in p for p in memory_problems(plant(skill))), want


def router():
    spec = importlib.util.spec_from_file_location("kb_change_router", os.path.join(KB, ".claude", "hooks", "kb_change_router.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def likely(prompt):
    a = router().answer(prompt)
    return "" if a is None else a["hookSpecificOutput"]["additionalContext"].split("Likely: ", 1)[1].split(". Any change", 1)[0]


@pytest.mark.parametrize("prompt", [
    "run the autopilot",
    "start the autopilot manager loop",
    "start the manager loop",
    "update the manager tick",
])
def test_autopilot_skill_routed(prompt):
    assert "/kb-autopilot (" in likely(prompt), likely(prompt)


@pytest.mark.parametrize("prompt", [
    "fix autopilot.py",
    "run autopilot.py status and fix it",
    "what does the autopilot do?",
    "edit the autopilot runner's docstring",
])
def test_autopilot_skill_not_routed_for_the_tool(prompt):
    assert "/kb-autopilot (" not in likely(prompt), likely(prompt)
