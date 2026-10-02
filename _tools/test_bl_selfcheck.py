"""Tests of `backlog.py selfcheck` (bl_selfcheck.py): the six checks (allow rules, hooks and plugin, host, claims,
owned orphans, main), each failing with the remedy the kb-sprint skill names, and the capped output. The tests named
selfcheck_names_remedy_* and selfcheck_capped_* are the item's checks. Every failure is planted: a settings file that
lacks a rule, a clone with no hooks, a lock held for hours, a third runner, a stale claim, an owned orphan, a red
pipeline row; a passing host prints one line. The host's lock directory is the test's own, and the main lock's holder
variable is cleared (a run inside the sync gate inherits it).
"""
import json
import os
import time
from pathlib import Path

import pytest

import backlog
import bl_base
import bl_procs
import bl_selfcheck as sc
import bl_stall
import bl_testkit
import kg_lock
from bl_testkit import b, sh

bl_testkit.bind(backlog)
repo = bl_testkit.repo

SKILL = Path(__file__).resolve().parent.parent / ".claude" / "skills" / "kb-sprint" / "SKILL.md"
LONG_AGO = "2020-01-01T00:00:00Z"


@pytest.fixture(autouse=True)
def host_dir(tmp_path, monkeypatch):
    d = tmp_path / "hostlocks"
    d.mkdir()
    monkeypatch.setenv("KB_HOST_LOCK_DIR", str(d))
    monkeypatch.delenv(kg_lock.HELD_ENV, raising=False)
    return d


def settings(root, allow):
    (Path(root) / ".claude").mkdir(exist_ok=True)
    (Path(root) / ".claude" / "settings.json").write_text(json.dumps({"permissions": {"allow": allow}}), encoding="utf-8")


def covering(skip=()):
    """Allow rules that cover every command and tool, but the commands in SKIP."""
    rules = [f"Bash({c})" for c in sc.SKILL_COMMANDS if c not in skip] + list(sc.SKILL_TOOLS)
    return rules


def lock(host, name, pid, clone, started):
    (host / name).write_text(f"pid={pid}\nclone={clone}\nstarted={started}\nstep=test\n", encoding="utf-8")


def report(items=(), main="ok", ts="2026-10-01T10:00:00.000Z"):
    return {"main": {"state": main, "ts": ts}, "lock": {"state": "none", "detail": None}, "ops_rows": 0,
            "items": list(items)}


def remedy_names(text):
    """The remedy names of the ladder (bl_stall.REMEDIES) that TEXT uses."""
    return {r for r in bl_stall.REMEDIES if r in text}


# ---------------------------------------------------------------- remedies

def test_selfcheck_names_remedy_allow_rules_missing_rule_is_named(repo):
    settings(repo, covering(skip=("git cherry origin/main branch",)))
    r = sc.check_allow(repo)
    assert r["state"] == "fail" and "git cherry origin/main branch" in r["detail"]
    assert "ask-operator" in r["remedy"] and "never edit" in r["remedy"]
    settings(repo, covering())
    assert sc.check_allow(repo)["state"] == "ok"


def test_selfcheck_names_remedy_allow_rules_missing_tool_and_missing_file(repo):
    settings(repo, [r for r in covering() if r != "SendMessage"])
    r = sc.check_allow(repo)
    assert r["state"] == "fail" and "tool SendMessage" in r["detail"]
    (repo / ".claude" / "settings.json").unlink()
    r = sc.check_allow(repo)
    assert r["state"] == "fail" and "missing" in r["detail"] and r["remedy"]
    (repo / ".claude" / "settings.json").write_text("{not json", encoding="utf-8")
    assert sc.check_allow(repo)["detail"].endswith("not readable JSON")


@pytest.mark.parametrize("rule,command,covers", [
    ("Bash(git fetch *)", "git fetch origin", True),
    ("Bash(git fetch *)", "git fetch", True),
    ("Bash(git fetch *)", "git fetchx", False),
    ("Bash(git fetch *)", "git push origin", False),
    ("Bash(python3 _tools/check.py)", "python3 _tools/check.py", True),
    ("Bash(python3 _tools/check.py)", "python3 _tools/check.py --x", False),
    ("Bash(python3 *tests.py *)", "python3 _tools/tests.py -k a", True),
    ("Bash", "anything at all", True),
    ("PowerShell(git fetch *)", "git fetch origin", False),
    ("Edit", "git fetch origin", False),
])
def test_selfcheck_names_remedy_allow_rule_matching(rule, command, covers):
    assert sc.rule_covers(rule, command) is covers


def test_selfcheck_names_remedy_allow_rules_of_this_repo_cover_the_skill_commands():
    root = Path(__file__).resolve().parent.parent
    r = sc.check_allow(root)
    assert r["state"] == "ok", r


def test_selfcheck_names_remedy_hooks_not_installed_names_setup(repo):
    r = sc.check_hooks(repo)
    assert r["state"] == "fail" and "core.hooksPath is not set" in r["detail"]
    assert "/kb-setup" in r["remedy"] and "install-hooks" in r["remedy"]


def test_selfcheck_names_remedy_hooks_path_checked_and_scripts_checked(repo):
    import kg_hooks
    sh(repo, "git", "config", "core.hooksPath", ".githooks")
    assert "lacks" in sc.hooks_problem(repo)  # the directory has no scripts
    (repo / ".githooks").mkdir()
    for h in kg_hooks.HOOKS:
        (repo / ".githooks" / h).write_text("#!/bin/sh\n", encoding="utf-8")
    assert sc.hooks_problem(repo) is None
    sh(repo, "git", "config", "core.hooksPath", "elsewhere")
    assert "not this clone's" in sc.hooks_problem(repo)


def test_selfcheck_names_remedy_plugin_missing_files_are_named(repo):
    assert "missing" in sc.plugin_problem(repo)
    (repo / ".claude-plugin").mkdir()
    (repo / ".claude-plugin" / "plugin.json").write_text(json.dumps(
        {"skills": ["./.claude/skills/none"], "mcpServers": {"kb": {"args": ["${CLAUDE_PLUGIN_ROOT}/_tools/none.py"]}}}),
        encoding="utf-8")
    problem = sc.plugin_problem(repo)
    assert "./.claude/skills/none" in problem and "_tools/none.py" in problem
    assert sc.plugin_problem(Path(__file__).resolve().parent.parent) is None


def test_selfcheck_names_remedy_host_load_lock_and_runners(host_dir):
    now = time.time()
    ok = sc.check_host(now, load=0.5, cores=4)
    assert ok["state"] == "ok"
    busy = sc.check_host(now, load=sc.LOAD_PER_CORE * 4 + 1, cores=4)
    assert busy["state"] == "fail" and "-k" in busy["remedy"] and "retry-narrower" in busy["remedy"]
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - bl_stall.HOST_LOCK_WAIT_S - 600))
    lock(host_dir, "kb-tests.lock", os.getpid(), "/clones/other", started)
    held = sc.check_host(now, load=0.1, cores=4)
    assert held["state"] == "fail" and f"pid {os.getpid()}" in held["detail"] and "clone other" in held["detail"]
    assert "lock-wait" in held["remedy"] and "file-blocker" in held["remedy"]
    (host_dir / "kb-tests.lock").unlink()
    young = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 30))
    lock(host_dir, "kb-main.lock", os.getpid(), "/clones/other", young)
    assert sc.check_host(now, load=0.1, cores=4)["state"] == "ok"  # held, but not for long
    lock(host_dir, "kb-main.lock", 2 ** 22 + 12345, "/clones/gone", LONG_AGO)
    assert sc.check_host(now, load=0.1, cores=4)["state"] == "ok"  # a holder that is gone is cleared by the next taker


def test_selfcheck_names_remedy_host_third_runner(host_dir):
    for i in range(bl_base.MAX_RUNNERS + 1):
        (host_dir / f"{bl_base.RUNNER_PREFIX}{os.getpid() + 0}.{i}.json").write_text("{}", encoding="utf-8")  # no pid: not live
    assert sc.check_host(time.time(), load=0.1, cores=4)["state"] == "ok"
    for i in range(bl_base.MAX_RUNNERS + 1):  # live records: this process's pid, thrice, in files of their own
        (host_dir / f"{bl_base.RUNNER_PREFIX}{i}.json").write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
    r = sc.check_host(time.time(), load=0.1, cores=4)
    assert r["state"] == "fail" and f"limit is {bl_base.MAX_RUNNERS}" in r["detail"] and "sprint runner" in r["remedy"]


def test_selfcheck_names_remedy_claims_stale_claim_names_its_ladder_step():
    stale = {"id": "ST-aaaaaaaa", "label": "ST-aaaaaaaa “A”", "state": "doing", "claimed_by": "s", "unknown": [],
             "signals": ["claim-no-commit", "red-main"], "next": {}}
    quiet = dict(stale, id="ST-bbbbbbbb", label="ST-bbbbbbbb “B”", signals=["done-refused"])
    ready = dict(stale, state="ready", signals=["claim-no-commit"])
    r = sc.check_claims(report([stale, quiet, ready]))
    assert r["state"] == "fail" and "ST-aaaaaaaa" in r["detail"] and "ST-bbbbbbbb" not in r["detail"]
    assert "claim-no-commit" in r["detail"] and "red-main" not in r["detail"]
    assert {"release-redispatch", "file-blocker", "ask-operator"} <= remedy_names(r["remedy"])
    assert sc.check_claims(report([quiet, ready]))["state"] == "ok"


def test_selfcheck_names_remedy_orphans_owned_orphan_fails_and_foreign_does_not():
    def proc(pid, kind):
        return {"pid": pid, "ppid": 1, "start": 1.0, "comm": "sleep", "where": "clone/sub", "kind": kind}
    snap = lambda procs: (lambda root: (procs, {}, None))  # noqa: E731
    r = sc.check_orphans("r", snap([proc(7, bl_procs.OWNED_ORPHAN), proc(8, bl_procs.FOREIGN), proc(9, bl_procs.ORPHAN)]))
    assert r["state"] == "fail" and "pid 7" in r["detail"] and "pid 8" not in r["detail"] and "pid 9" not in r["detail"]
    assert "procs --end" in r["remedy"]
    assert sc.check_orphans("r", snap([proc(8, bl_procs.FOREIGN)]))["state"] == "ok"
    unk = sc.check_orphans("r", lambda root: (None, None, "no lsof"))
    assert unk["state"] == "unknown" and "no lsof" in unk["detail"]


def test_selfcheck_names_remedy_main_red_names_file_blocker():
    r = sc.check_main(report(main="red"))
    assert r["state"] == "fail" and "red" in r["detail"]
    assert {"file-blocker", "ask-operator"} <= remedy_names(r["remedy"])
    unk = sc.check_main(report(main="unknown", ts=None))
    assert unk["state"] == "unknown" and "red-pipeline --status" in unk["remedy"]
    assert sc.check_main(report())["state"] == "ok"


def test_selfcheck_names_remedy_every_remedy_name_is_in_the_skill():
    text = SKILL.read_text(encoding="utf-8")
    used = set()
    for r in sc.REMEDY.values():
        used |= remedy_names(r)
    assert used and used <= set(bl_stall.REMEDIES)
    for name in used:
        assert f"`{name}`" in text, name
    assert "selfcheck" in text and "## Self-check" in text


def test_selfcheck_names_remedy_command_in_a_scratch_clone_fails_with_remedies(repo):
    code, out = b(repo, "selfcheck")
    assert code == 1, out
    assert out.splitlines()[0].startswith("selfcheck: ") and "failed" in out.splitlines()[0]
    assert "FAIL allow-rules" in out and "ask-operator" in out
    assert "FAIL hooks" in out and "/kb-setup" in out
    code, out = b(repo, "selfcheck", "--json")
    data = json.loads(out)
    assert code == 1 and data["ok"] is False and [c["name"] for c in data["checks"]] == [
        "allow-rules", "hooks", "host", "claims", "orphans", "main"]
    assert b(repo, "selfcheck", "--full", "--json")[0] == 2  # alternatives


def test_selfcheck_names_remedy_a_passing_host_prints_one_line():
    results = [sc.result(n, "ok", "fine") for n in ("allow-rules", "hooks", "host", "claims", "orphans", "main")]
    assert sc.render(results) == ["selfcheck: ok (6 checks passed)"]


# ---------------------------------------------------------------- the cap

def failing(n_lines, detail="x"):
    return [sc.result(f"check-{i}", "fail", detail, "ask-operator: a remedy") for i in range(n_lines)]


@pytest.mark.parametrize("n", list(range(0, 14)) + [15, 20, 24, 30, 33, 36, 60, 100])
def test_selfcheck_capped_listing_names_the_first_entries_and_counts_the_rest(n):
    entries = [f"e{i}" for i in range(n)]
    text = sc.listing(entries)
    assert text.startswith(", ".join(entries[:sc.SHOW]))
    if n > sc.SHOW:
        assert text.endswith(f"+{n - sc.SHOW} more")
        assert f"e{sc.SHOW}" not in text.split(" +")[0].split(", ")
    else:
        assert "more" not in text


@pytest.mark.parametrize("missing", [1, 2, 3, 4, 5, 6, 8, 12, 16, 24])
def test_selfcheck_capped_allow_rules_with_many_missing_commands(repo, missing):
    skip = sc.SKILL_COMMANDS[:missing]
    settings(repo, covering(skip=skip))
    r = sc.check_allow(repo)
    assert r["state"] == "fail" and f"{missing} of " in r["detail"]
    if missing > sc.SHOW:
        assert f"+{missing - sc.SHOW} more" in r["detail"]
    for c in skip[sc.SHOW:]:
        assert c not in r["detail"]
    assert len(sc.line_of(r)) <= sc.LINE_MAX


@pytest.mark.parametrize("n", [1, 2, 5, 7, 8, 9, 10, 11, 12, 14, 20, 25, 40])
def test_selfcheck_capped_output_is_under_the_cap_and_says_what_it_dropped(n):
    results = failing(n, detail="d" * 200)
    lines = sc.render(results)
    assert sum(len(ln) + 1 for ln in lines) <= sc.MAX_CHARS
    assert all(len(ln) <= sc.LINE_MAX for ln in lines)
    shown = [ln for ln in lines if ln.startswith("FAIL")]
    dropped = n - len(shown)
    if dropped:
        assert lines[-1] == f"selfcheck: {dropped} line(s) dropped; `selfcheck --full` prints all"
    else:
        assert not lines[-1].startswith("selfcheck: ") or "dropped" not in lines[-1]
    assert lines[0] == f"selfcheck: {n} failed, 0 unknown of {n} checks"
    full = sc.render(results, full=True)
    assert len(full) == n + 1 and not any("dropped" in ln for ln in full)  # the cap is lifted, nothing is dropped


def test_selfcheck_capped_a_long_line_is_cut_and_says_so():
    lines = sc.render(failing(1, detail="y" * 2000))
    assert len(lines[1]) == sc.LINE_MAX and lines[1].endswith(" [cut]")
    full = sc.render(failing(1, detail="y" * 2000), full=True)
    assert len(full[1]) > sc.LINE_MAX and "[cut]" not in full[1]


def test_selfcheck_capped_the_real_checks_stay_under_the_cap_when_all_fail(repo):
    settings(repo, [])
    stale = [{"id": f"ST-{i:08d}", "label": f"ST-{i:08d} “" + "t" * 60 + "”", "state": "doing", "claimed_by": "s",
              "unknown": [], "signals": ["returned-staged"], "next": {}} for i in range(40)]
    procs = [{"pid": i, "ppid": 1, "start": 1.0, "comm": "sleep", "where": "clone/" + "d" * 40, "kind": bl_procs.OWNED_ORPHAN}
             for i in range(30)]
    results = [sc.check_allow(repo), sc.check_hooks(repo), sc.check_host(time.time(), load=99, cores=1),
               sc.check_claims(report(stale)), sc.check_orphans("r", lambda root: (procs, {}, None)),
               sc.check_main(report(main="red"))]
    assert [r["state"] for r in results] == ["fail"] * 6
    lines = sc.render(results)
    assert sum(len(ln) + 1 for ln in lines) <= sc.MAX_CHARS and all(len(ln) <= sc.LINE_MAX for ln in lines)
    assert "+37 more" in "\n".join(lines) or "dropped" in lines[-1]
    assert len(sc.render(results, full=True)) == 7
