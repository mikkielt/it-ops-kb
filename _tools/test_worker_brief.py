"""The clauses of the kb-worker brief and of the sprint skill's claim step that the first retrospectives asked for: each
test names the phrases one clause needs, and fails on a copy of the text that lacks any of them (a planted failure)."""
from pathlib import Path

KB = Path(__file__).resolve().parent.parent
BRIEF = (KB / ".claude" / "agents" / "kb-worker.md").read_text(encoding="utf-8")
SKILL = (KB / ".claude" / "skills" / "kb-sprint" / "SKILL.md").read_text(encoding="utf-8")


def missing(text, phrases):
    return [p for p in phrases if p not in text]


def pinned(text, phrases):
    """The phrases the text lacks, after checking that taking any one of them out of the text is seen."""
    for p in phrases:
        assert text.count(p) >= 1, f"the text lacks {p!r}"
        assert missing(text.replace(p, ""), phrases) == [p], f"removing {p!r} is not seen"
    return missing(text, phrases)


def test_worker_brief_self_reviewed_in_last_paragraph():
    """Self-Reviewed sits inside the last trailer paragraph, the only one git reads; an amend is rewritten whole."""
    phrases = ["git reads trailers from the last paragraph only", "`Self-Reviewed:` line outside it is not read",
               "git commit --amend -F <file>", "kbgit.py check-trailers", "puts a blank line before `KB-Work`"]
    assert pinned(BRIEF, phrases) == []


def test_worker_brief_runs_tests_in_foreground():
    """A worker runs checks and tests in the foreground with a timeout and never waits for a background notice."""
    phrases = ["in the foreground with a timeout of 600000 ms", "never wait for a background notice"]
    assert pinned(BRIEF, phrases) == []


def test_worker_brief_runs_leak_scan_for_new_test_files():
    """A test or fixture file is checked with the leak selection, and no GUID-shaped literal (a session id counts)
    stays in a test file."""
    phrases = ["-k 'leaks or test_no_private_ipv4'", "`--changed` may wait on the host lock",
               "holds no GUID-shaped literal",
               "a session id counts as one", "build such a value from parts"]
    assert pinned(BRIEF, phrases) == []


def test_worker_brief_names_trailer_order_and_no_done():
    """The trailer order is Co-Authored-By, Session, Self-Reviewed, KB-Work last; the worker never runs done."""
    phrases = ["in this order: `Co-Authored-By`, `Session`, `Self-Reviewed`, then `KB-Work: <id>` last",
               "Never run `backlog.py done` yourself"]
    assert pinned(BRIEF, phrases) == []


def test_worker_brief_names_background_timeout_and_stale_scope():
    """The orchestrator's background land has its own long timeout, and the worker reads every doc the stale
    pre-check lists, which mixes docs of other items' changes."""
    phrases = ["a timeout of 7200000 ms", "selfdoc.py stale --since origin/main",
               "the list mixes docs of other items' changes", "names only the docs your change touches and you read"]
    assert pinned(BRIEF, phrases) == []


def test_worker_brief_maps_goal_clauses_to_checks():
    """Each goal clause is mapped to the check or assertion that proves it, and a repro that runs as a done check
    names only something the fix really contains."""
    phrases = ["map each goal clause to the check or test assertion that proves it",
               "a check narrower than its clause leaves the clause unproven",
               "A bug's repro runs as a `done` check", "names only something the fix really contains"]
    assert pinned(BRIEF, phrases) == []


def test_worker_brief_plants_valid_lookalikes():
    """A rejection rule is planted with valid look-alikes, a shared fixture with every test file that uses it, and a
    new file that cites a doc with the cohesion selection."""
    phrases = ["plants valid look-alikes in its test", "running every test file that uses it",
               "grep the fixture's name", "needs `-k cohesion` too"]
    assert pinned(BRIEF, phrases) == []


def test_sprint_skill_claim_step_greps_tests_and_lists_skills_in_touches():
    """Before a claim the orchestrator lists the tests and docs the behaviour touches, and the skill the work edits,
    in the item's touches."""
    phrases = ["`grep -rn` the existing tests", "selfdoc.py stale", "with any skill the work edits, up front",
               "`done` refuses a file outside the touches"]
    assert pinned(SKILL, phrases) == []


def test_sprint_skill_claim_step_fetches_and_looks_for_a_work_branch():
    """Right before a claim: fetch, and no local work/<id> branch, since two sessions can pass held together."""
    phrases = ["Right before the claim run `git fetch origin`", "no local `work/<id>` branch exists",
               "two sessions can pass `held` together"]
    assert pinned(SKILL, phrases) == []


def test_sprint_skill_land_runs_stale_first_and_in_the_background_with_a_long_timeout():
    """The skill names the stale pre-check as land's first step and the 7200000 ms background timeout."""
    phrases = ["selfdoc.py stale --since origin/main` first", "`timeout` 7200000 ms"]
    assert pinned(SKILL, phrases) == []
