"""The three test tiers a sprint runs, as the agent, the skills and the runbook state them.

test_three_tiers_documented: kb-worker.md says a worker runs the narrow tier only (its item's checks, the ruff and
tools_map tests and the focused tests of its files) and never `tests.py --changed`, the full `tests.py` or
`stress_test.py`; kb-sprint's skill states the three tiers once, briefs workers with the narrow tier and has the
review story run the heavy suites; kb-item's skill gives the narrow tier before landing; the runbook states each
tier once (narrow per task, the gate per landing, the heavy suites once at sprint end); none still says a worker runs
`--changed`, the fast tests, or that `land` or the orchestrator runs `stress_test.py` before the sprint's end.
test_three_tiers_documented_planted_failures: each required sentence taken out, and each old rule put back, fails.
"""
import os
import re

from conftest import KB

KB_WORKER = ".claude/agents/kb-worker.md"
KB_SPRINT = ".claude/skills/kb-sprint/SKILL.md"
KB_ITEM = ".claude/skills/kb-item/SKILL.md"
RUNBOOK = "kb/_self/backlog.md"
DOCS = (KB_WORKER, KB_SPRINT, KB_ITEM, RUNBOOK)

NARROW = 'python3 _tools/tests.py -k "ruff or tools_map"'

# what each text must say: the tier or tiers it owns
REQUIRED = {
    KB_WORKER: [
        "the narrow tier of the three test tiers",
        NARROW,
        "Never run `tests.py --changed`, `python3 _tools/stress_test.py` or the full `python3 _tools/tests.py`",
        "The sync gate runs `tests.py --changed origin/main` once per landing",
        "the review story runs `stress_test.py` with the full `tests.py` once at sprint end",
    ],
    KB_SPRINT: [
        "Tests run in three tiers",
        "narrow per task",
        "the gate per landing",
        "the `tests.py --changed origin/main` of `sync --push`",
        "the heavy suites once at sprint end",
        "run only the narrow tier",
        "never `tests.py --changed`, `python3 _tools/stress_test.py` or the full `tests.py`",
        "Its checks run the heavy tier once, `stress_test.py` with the full `tests.py`",
    ],
    KB_ITEM: [
        "only the narrow tier of the three test tiers",
        '`-k "ruff or tools_map"`',
        "never `tests.py --changed` (the sync gate runs it once per landing)",
        "the sprint's review story runs them once",
    ],
    RUNBOOK: [
        "**Three test tiers**",
        "Narrow, per task: a worker runs only its item's own `checks`",
        NARROW,
        "never `tests.py --changed`, the full `tests.py` or `stress_test.py`",
        "The gate, per landing: the sync gate's `tests.py --changed origin/main` is the one mapped run per landing",
        "the stale check, the lookup eval and the lint around it, and no stress run",
        "Heavy, once at sprint end: `stress_test.py` with the full `tests.py` runs once, as the review story's checks",
        "before the review and the retrospective",
    ],
}

# wordings of the old rule: a worker runs the mapped tests, land or the orchestrator runs the stress suite
FORBIDDEN = (
    "the fast tests",
    "before the stress run",
    "The orchestrator runs `stress_test.py` once",
    "`backlog.py land` runs it",
    "land runs `stress_test.py`",
)

# a sentence that names `--changed` in a worker's text names the gate or forbids it
CHANGED_OK = ("never", "sync gate", "the gate", "per landing")


def tier_problems(texts):
    """What is wrong with the way `texts` (path to text, for the paths in DOCS) state the three test tiers: [] when
    nothing."""
    problems = []
    for rel in DOCS:
        text = texts[rel]
        # the agent states its tier in its done bar (rule 3), which rule 4 also names the ruff tests in
        scope = next((l for l in text.splitlines() if l.startswith("3. **Done bar.**")), "") if rel == KB_WORKER else text
        for phrase in REQUIRED[rel]:
            if phrase not in scope:
                problems.append(f"{rel} does not say {phrase!r}")
        for phrase in FORBIDDEN:
            if phrase in text:
                problems.append(f"{rel} still says {phrase!r}")
        if rel != RUNBOOK:
            for sentence in re.split(r"(?<=[.;:]) ", text):
                if "--changed" in sentence and not any(word in sentence.lower() for word in CHANGED_OK):
                    problems.append(f"{rel} has a sentence naming --changed with no gate or never: {sentence.strip()[:100]!r}")
    review = texts[KB_SPRINT].split("\n## review SP", 1)[-1].split("\n## ", 1)[0]
    if "heavy tier" not in review:
        problems.append(f"{KB_SPRINT}'s review section does not say its checks run the heavy tier")
    return problems


def load_texts():
    texts = {}
    for rel in DOCS:
        with open(os.path.join(KB, rel), encoding="utf-8") as f:
            texts[rel] = f.read()
    return texts


def test_three_tiers_documented():
    assert tier_problems(load_texts()) == []


def test_three_tiers_documented_planted_failures():
    """Each required sentence taken out of its text, and each old rule put back, makes the problem list non-empty."""
    texts = load_texts()
    plants = []
    for rel in DOCS:
        for phrase in REQUIRED[rel]:
            plants.append((rel, phrase, ""))
        for phrase in FORBIDDEN:
            plants.append((rel, "", " " + phrase))
    plants += [
        (KB_WORKER, NARROW, "the fast tests, `python3 _tools/tests.py --changed origin/main`"),
        (KB_WORKER, "Never run `tests.py --changed`,", "Run `tests.py --changed origin/main`,"),
        (KB_SPRINT, "run only the narrow tier: ", "run the item's checks and `tests.py --changed origin/main`; "),
        (KB_ITEM, "never `tests.py --changed` (the sync gate runs it once per landing)", "then `tests.py --changed origin/main`"),
        (RUNBOOK, "and no stress run", "and the stress run"),
    ]
    for rel, old, new in plants:
        planted = dict(texts)
        planted[rel] = texts[rel].replace(old, new, 1) if old else texts[rel] + new
        assert planted[rel] != texts[rel], f"plant does not apply: {rel} {old!r}"
        assert tier_problems(planted), f"not caught: {rel} {old!r} -> {new!r}"
