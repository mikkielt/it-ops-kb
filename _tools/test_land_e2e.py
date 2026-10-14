"""`backlog.py land ID` end to end in a scenario clone, in three scenarios on three workers (a class each), and the step
that frees a worker's worktree in a fourth class. One: an item whose branch sits in a finished worker's worktree that holds an untracked intake draft lands on origin/main: `land` moves
the draft aside and says so, and still refuses any other untracked file; a research story's `done` needs its note on
outside facts; a checkout that holds commits of its own names them before the push, as staying local, and after it
rebases those that change item files only onto origin/main, or names the `git rebase` command for one that changes
another file. Two: a commit of an item that changes a mapped tool and no doc is refused at `done` with stale-docs, and a
`Self-Reviewed:` trailer naming the docs clears that; an item whose check fails stops `land` at its step and leaves
origin/main where it was; a content landing that adds a CODE tag with no pointer to an article stops at step `lint`,
which ran on that article's path alone, and a stop at a step after land removed the finished worker's worktree (that
lint, a failed push) names the `git worktree add` command that checks the branch out again at the same path. Three: the checkout `land` runs in holds untracked intake drafts and nothing else:
`land` moves them aside and says so before its clean tree step, keeps them there when it stops at a later step, and
refuses at clean tree, moving nothing, when another file or an item that is no filed draft is there; the same scenario
holds `check`'s moved-or-deleted touch rule, which counts a path as gone by the integration main's history and not by
a work branch's own add and removal of it. The fourth class,
on a throwaway repository: a finished worker's worktree that a session-end hook's run (its parent gone, its standard
output the clone's distill.log) still holds is waited for and then removed; the wait is bounded by
`bl_procs.HOOK_GRACE_S` and skipped for a process whose parent lives; the same class holds the landing of a
multi-repository item (`multirepo_land`): each repository's request read once, a request that is not merged refused by
repository and state, a dirty, locked or live-process worktree refused by name with none removed, the clean ones
removed, the branches on the default branch deleted, each merge commit written as evidence, and the leftovers close
removes. A class of its own, so it has a worker of its own, holds a code-lane item's land without `--wait-merge`, which
names the lane and the rerun before its push."""
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from conftest import KB, Repo, git_env, requires_git, seed_files

pytestmark = [pytest.mark.git, requires_git]

NOSYNC = {"KB_SYNC_NO_TESTS": "1"}
PLAN = "kb/_self/backlog"


@pytest.fixture(scope="session", autouse=True)
def real_git():
    """macOS's /usr/bin/git only starts the Command Line Tools' git, which costs three git starts' time (9 ms for 3 ms
    here), and a landing runs about 75 git commands: the real binary first on PATH for these scenarios and every tool
    they run, where the shim is what `git` would resolve to. Any other host runs the `git` it has."""
    found = shutil.which("git")
    real = None
    if sys.platform == "darwin" and found == "/usr/bin/git":
        p = subprocess.run([found, "--exec-path"], capture_output=True, text=True)
        cand = Path(p.stdout.strip()).parents[1] / "bin" / "git" if p.returncode == 0 and p.stdout.strip() else None
        real = cand if cand and cand.is_file() else None
    with pytest.MonkeyPatch.context() as mp:
        if real:
            mp.setenv("PATH", os.pathsep.join([str(real.parent), os.environ.get("PATH", "")]))
        yield


def import_seed(bare):
    """The commit of seed_files() in the bare repository BARE, as conftest's kb_seed makes it, but written as one
    uncompressed pack by `git fast-import` (a file's bytes, its mode and a link's target): the 1.2 s of `git add` and
    repack that conftest pays make every scenario of this file wait that long for the seed. A file holding a carriage
    return is hashed by git itself, through the attributes, so a line-ending rule applies as `git add` applies it."""
    entries = []  # (rel, mode, bytes), or (rel, mode, None) for a file git hashes itself
    for rel in seed_files():
        path = os.path.join(KB, rel)
        if os.path.islink(path):
            mode, data = b"120000", os.readlink(path).encode("utf-8")
        else:
            with open(path, "rb") as f:
                data = f.read()
            mode = b"100755" if os.name != "nt" and os.stat(path).st_mode & 0o111 else b"100644"
        entries.append((rel, mode, None if b"\r" in data else data))
    held = [rel for rel, _, data in entries if data is None]
    shas = {}
    if held:
        env = git_env(GIT_DIR=str(bare), GIT_WORK_TREE=KB)
        p = subprocess.run(["git", "-c", "core.autocrlf=false", "hash-object", "-w", "--stdin-paths"], cwd=KB, env=env,
                           input="\n".join(held) + "\n", capture_output=True, text=True, encoding="utf-8")
        assert p.returncode == 0, p.stderr
        shas = dict(zip(held, p.stdout.split()))
    stream = [b"commit refs/heads/main\ncommitter t <t@example.com> 0 +0000\ndata 4\nbase\n"]
    for rel, mode, data in entries:
        name = rel.encode("utf-8")
        if data is None:
            stream.append(b"M %s %s %s\n" % (mode, shas[rel].encode("ascii"), name))
        else:
            stream.append(b"M %s inline %s\ndata %d\n%s\n" % (mode, name, len(data), data))
    stream.append(b"done\n")
    p = subprocess.run(["git", "-c", "core.compression=0", "-c", "pack.compression=0", "fast-import", "--quiet",
                        "--done"], cwd=bare, env=git_env(), input=b"".join(stream), capture_output=True)
    assert p.returncode == 0, p.stderr.decode("utf-8", "replace")
    return Repo(bare).rev("HEAD")


@pytest.fixture(scope="session")
def kb_seed(tmp_path_factory):
    """conftest's kb_seed for this file's scenarios, built by import_seed: the same directory and hand-over file, so a
    run holds one seed whichever test asks for it first."""
    base = tmp_path_factory.getbasetemp()
    tmp = (base.parent if os.environ.get("PYTEST_XDIST_WORKER") else base) / "kb-seed"
    done = tmp / "seed.json"
    try:
        tmp.mkdir()
    except FileExistsError:
        deadline = time.monotonic() + 300
        while not done.exists():
            assert time.monotonic() < deadline, f"no seed at {tmp}"
            time.sleep(0.05)
        got = json.loads(done.read_text(encoding="utf-8"))
        assert "error" not in got, got
        return Path(got["bare"]), got["base"]
    got = {"error": "not built"}
    try:
        bare = tmp / "seed.git"
        Repo(tmp).git("init", "-q", "--bare", "-b", "main", str(bare))
        got = {"bare": str(bare), "base": import_seed(bare)}
    finally:
        part = done.with_suffix(".part")
        part.write_text(json.dumps(got), encoding="utf-8")
        os.replace(part, done)
    return Path(got["bare"]), got["base"]


def bl(repo, *args, env=NOSYNC):
    p = repo.tool("backlog.py", *args, env=env)
    return p.returncode, p.stdout + p.stderr


def plain_push(repo, tmp_path, **changes):
    """NOSYNC and a KB_BACKLOG_CONFIG that names a copy of the clone's backlog.json with CHANGES applied (a `land_push`
    of one plain push: the landing's own steps stay, the sync gate that the own-checkout scenario covers does not)."""
    cfg = tmp_path / "backlog.json"
    cfg.write_text(json.dumps({**json.loads(repo.read("backlog.json")), **changes}), encoding="utf-8")
    return {**NOSYNC, "KB_BACKLOG_CONFIG": str(cfg)}


def ok(repo, *args):
    code, out = bl(repo, *args)
    assert code == 0, f"backlog.py {' '.join(args)}: {out}"
    return out


def new_id(out):
    return re.search(r"\b((?:ST|SP|TK|BG)-[a-z0-9]+)\b", out).group(1)


def origin_main(scenario):
    return scenario.origin.rev("main")


def item(scenario, iid):
    return json.loads(scenario.origin.git("show", f"main:{PLAN}/{iid}.json"))


def work(repo, iid, rel):
    """One commit on a local branch work/<iid>, made from the pushed planning, changing one kb doc."""
    repo.git("checkout", "-q", "-b", f"work/{iid}", "main")
    repo.write(rel, f"# {iid}\n\nWork of the item.\n")
    repo.git("add", rel)
    repo.git("commit", "-q", "-m", f"docs(kb): {iid} work", "-m", f"KB-Work: {iid}")


BATCH = """import contextlib, io, json, re, sys
sys.path.insert(0, sys.argv[1])
import backlog
ids, done = [], []
for argv in json.loads(sys.argv[2]):
    argv = [ids[a["id"]] if isinstance(a, dict) else a for a in argv]
    raw = io.BytesIO()
    out = io.TextIOWrapper(raw, encoding="utf-8", newline="\\n")
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        try:
            code = backlog.main(argv)
        except SystemExit as e:
            code = e.code
    out.flush()
    found = re.search(r"\\b((?:ST|SP|TK|BG)-[a-z0-9]+)\\b", raw.getvalue().decode("utf-8"))
    ids.append(found.group(1) if found else None)
    done.append([code, raw.getvalue().decode("utf-8")])
sys.__stdout__.write(json.dumps(done))
"""


def batch(repo, *steps, env=NOSYNC):
    """STEPS (each a `backlog.py` argument list) run one after another in a single process of the clone's own
    `backlog.main`, the 0.1 s of start-up paid once: [(exit code, output)] for each. An argument `{"id": N}` is the
    id that step N printed. What a step runs (git, checks) is a subprocess of it, as in a run of its own."""
    p = subprocess.run([sys.executable, "-c", BATCH, repo.file("_tools"), json.dumps(steps)], cwd=repo.path,
                       env={**repo.env, **env}, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert p.returncode == 0, p.stdout + p.stderr
    return [tuple(r) for r in json.loads(p.stdout)]


def planned(scenario, *stories, hooks=True):
    """A clone whose backlog is the fixture one (the live items removed, so a planning slip in one of them cannot fail
    `backlog.py check` inside a scenario) and whose started sprint has the stories ((name, kb path, check) each)
    claimed and pushed to origin/main: (clone, sprint id, story ids). The fixture is one process, one commit and one
    plain push, and a scenario whose landing never reaches the real sync passes `hooks=False`: the commit hooks cost
    0.2 s a commit."""
    repo = scenario.clone(hooks=hooks)
    repo.git("config", "core.fileMode", "false")
    shutil.rmtree(repo.file(PLAN))  # the commit below records the removal
    steps = [("new", "sprint", "--title", "Landing sprint")]
    steps += [("new", "story", "--title", f"Landing {n}", "--sprint", {"id": 0}, "--goal", f"The doc {n}.md exists.",
               "--touch", rel, "--check", chk) for n, rel, chk in stories]
    steps += [("answer", {"id": 0}, "start", "--answer", "approve", "--by", "operator"), ("start", {"id": 0})]
    steps += [("claim", {"id": i + 1}, "--by", "t") for i in range(len(stories))]
    results = batch(repo, *steps)
    for step, (code, out) in zip(steps, results):
        assert code == 0, f"backlog.py {' '.join(map(str, step))}: {out}"
    sp, ids = new_id(results[0][1]), [new_id(out) for _, out in results[1:1 + len(stories)]]
    repo.git("add", "-A", PLAN)
    repo.git("commit", "-q", "--no-verify", "-m", f"chore(backlog): plan {sp}")
    repo.git("push", "-q", "--no-verify", "origin", "main")
    return repo, sp, ids


# One class each: tests.py hands pytest-xdist whole scopes (a file, or a class in it), so the two scenarios run on
# two workers instead of one after the other.
class TestLandedItem:
    def test_land_names_unpushed_commits_before_its_push_land_rebases_local_item_commits_and_moves_intake_draft_then_fast_forwards_and_done_checks_notes(
            self, scenario, tmp_path):
        stories = [(n, f"kb/_self/{n}.md", "python3 _tools/backlog.py list --kind sprint") for n in ("good", "other", "third")]
        repo, sp, (good, other, third) = planned(scenario, *stories, hooks=False)
        env = plain_push(repo, tmp_path, land_push=["git", "push", "--no-verify", "origin", "HEAD:main"], land_lint=[])
        before = origin_main(scenario)

        for iid, n in ((good, "good"), (other, "other"), (third, "third")):
            work(repo, iid, f"kb/_self/{n}.md")
            repo.git("checkout", "-q", "main")  # land runs on main, whose upstream is origin/main: it ends level with it
        worker = Path(repo.file(f".claude/worktrees/agent-{good}"))
        repo.git("worktree", "add", "-q", str(worker), f"work/{good}")
        draft, stray = "kb/_self/backlog/ST-0d1e2f3a.json", "kb/_self/stray.md"
        for rel in (draft, stray):  # an intake draft the worker's session filed, and a file that is no draft
            (worker / rel).write_text("{}\n", encoding="utf-8", newline="\n")
        code, out = bl(repo, "land", good, env=env)
        assert code != 0 and "uncommitted changes" in out and (worker / draft).is_file(), out  # nothing moves on a refusal
        (worker / stray).unlink()
        code, out = bl(repo, "land", good, env=env)
        assert code == 0 and "landed" in out and "fast-forwarded main" in out and "not on origin/main" not in out, out
        kept = Path(repo.file("_cache/intake-drafts")) / worker.name / Path(draft).name
        assert "moved the untracked intake draft ST-0d1e2f3a.json" in out and kept.is_file() and not worker.exists(), out
        assert repo.rev("main") == origin_main(scenario) and repo.git("branch", "--show-current").strip() == "main"
        assert item(scenario, good)["status"] == "done" and item(scenario, good).get("evidence"), item(scenario, good)
        log = scenario.origin.git("log", "--format=%B", f"{before}..main")
        assert f"KB-Work: {good}" in log and f"done {good}" in log, log
        assert scenario.origin.git("show", "main:kb/_self/good.md").startswith(f"# {good}")
        assert origin_main(scenario) != before

        research = re.search(r"(ST-[a-z0-9]+)\s.*Research sprint goal", ok(repo, "list", "--sprint", sp)).group(1)
        # a commit of the checkout's own that changes an item file: named before the push as staying local (the push is
        # the item's branch alone), and rebased onto the pushed main after it, never pushed by land
        note = "chore(backlog): note on the research story"
        ok(repo, "set", research, "--notes", "Local note.")
        repo.git("add", "-A", PLAN)
        repo.git("commit", "-q", "--no-verify", "-m", note)
        code, out = bl(repo, "land", other, env=env)
        assert code == 0 and "main holds 1 commit(s) not on origin/main" in out and f"{note} (stays local)" in out, out
        assert re.search(r"stays local.*landed", out, re.S) and "rebased main's 1 local commit(s), item files only" in out, out
        assert repo.git("rev-list", "--count", "origin/main..main").strip() == "1", out
        assert repo.git("rev-list", "--count", "main..origin/main").strip() == "0", out
        assert note not in scenario.origin.git("log", "--format=%s", "main"), "land pushed the checkout's own commit"

        # a commit that changes another file is named and the command given, the checkout left as it was
        repo.write("kb/_self/local-note.md", "# local\n")
        repo.git("add", "kb/_self/local-note.md")
        repo.git("commit", "-q", "--no-verify", "-m", "docs(kb): local note")
        tip = repo.rev("main")
        code, out = bl(repo, "land", third, env=env)
        assert code == 0 and "landed" in out and "main holds 2 commit(s) not on origin/main" in out, out
        assert "one changes kb/_self/local-note.md, not an item file; git rebase origin/main)" in out, out
        assert repo.rev("main") == tip and repo.git("rev-list", "--count", "main..origin/main").strip() == "2", out

        cases = ((None, False), ("No outside facts:", False), ("Other. No outside facts: the goal is internal.", True))
        steps = [("claim", research, "--by", "t", "--commit")]
        for notes, _ in cases:
            steps += ([("set", research, "--notes", notes)] if notes else []) + [("done", research, "--dry-run")]
        results = batch(repo, *steps)  # no commit changes a non-item file: only the note lets a done pass
        assert all(code == 0 for step, (code, _) in zip(steps, results) if step[0] != "done"), results
        for (notes, accepted), (code, out) in zip(cases, [r for step, r in zip(steps, results) if step[0] == "done"]):
            assert (code == 0 and "would be done" in out) == accepted and (accepted or "KB-Work" in out), out


class TestStoppedLand:
    def test_land_runs_lint_on_content_item_then_planted_failures_and_land_stop_after_release_names_worktree_add(
            self, scenario, tmp_path):
        article = "kb/public/agents/codebase-mapping.md"
        nested = "kb/_self/lane/host.md"  # a code-lane path of the kb's lanes
        repo, sp, (bad, lint, host) = planned(
            scenario, ("bad", "kb/_self/bad.md", "python3 _tools/backlog.py show ST-00000000"),
            ("lint", article, "python3 _tools/backlog.py list --kind sprint"),
            ("host", nested, "python3 _tools/backlog.py list --kind sprint"), hooks=False)
        moved = origin_main(scenario)

        work(repo, bad, "kb/_self/bad.md")
        # planted failure of done's docs check: a commit of the item changes a mapped tool and no doc
        tool = "_tools/provider.py"
        repo.write(tool, Path(repo.file(tool)).read_text(encoding="utf-8") + "# changed\n")
        repo.git("commit", "-q", "-am", f"fix(kb): {bad} tool", "-m", f"KB-Work: {bad}")
        code, out = bl(repo, "done", bad, "--dry-run")
        assert code != 0 and "stale-docs:" in out and f"kb/_self/tools.md is older than {tool}" in out, out
        reviewed = "kb/_self/tools.md, kb/_self/code.md, kb/_self/web-sources.md"  # read and still correct: not stale
        repo.git("commit", "-q", "--allow-empty", "-m", f"docs(kb): {bad} review",
                 "-m", f"Self-Reviewed: {reviewed}\nKB-Work: {bad}")
        code, out = bl(repo, "done", bad, "--dry-run")
        assert "stale-docs" not in out and "outside touches" in out, out
        repo.git("reset", "-q", "--hard", "HEAD~2")
        code, out = bl(repo, "land", bad)
        assert code != 0 and "land stopped at step done" in out and "check(s) failed" in out, out
        assert origin_main(scenario) == moved
        assert item(scenario, bad)["status"] == "doing"

        # planted failure of the lint step: a content landing (no _tools/) adds a CODE tag with no path#symbol pointer
        repo.git("checkout", "-q", "-b", f"work/{lint}", "main")
        repo.write(article, Path(repo.file(article)).read_text(encoding="utf-8") + "\n- Planted fact. [CODE S0000001]\n")
        repo.git("commit", "-q", "-am", f"docs(kb): {lint} work", "-m", f"KB-Work: {lint}")
        repo.git("checkout", "-q", "main")
        lint_worker = Path(repo.file(f".claude/worktrees/agent-{lint}"))  # the finished worker's worktree: land removes it
        repo.git("worktree", "add", "-q", str(lint_worker), f"work/{lint}")
        code, out = bl(repo, "land", lint)
        assert code != 0 and "land stopped at step lint" in out, out
        assert "CODE tag without a path#symbol pointer" in out and f"lint.py {article[3:]} exited 1" in out, out
        assert origin_main(scenario) == moved and item(scenario, lint)["status"] == "doing"
        # the stop after the removal names the command that checks the branch out again at the same path (relative to
        # the checkout: backlog.py never prints the user's name, which an absolute path holds), and it works
        back = re.search(r"^  git (worktree add .+)$", out, re.M)
        assert back and not lint_worker.exists() and shlex.split(back.group(1)) == [
            "worktree", "add", f".claude/worktrees/agent-{lint}", f"work/{lint}"], out
        repo.git(*shlex.split(back.group(1)))
        assert lint_worker.is_dir() and repo.git("-C", str(lint_worker), "branch", "--show-current").strip() == f"work/{lint}"

        # a host project of the plugin: no code lane (`lane_module` empty: a commit of a code path lands as content,
        # no merge request) and its own push (`land_push`); a push that exits 3 stops land at that step, `done` already
        # made, and the same landing with a working push lands the item
        repo.git("checkout", "-q", "-b", f"work/{host}", "main")
        repo.write(nested, f"# {host}\n\nWork of the item.\n")
        repo.git("add", nested)
        repo.git("commit", "-q", "-m", f"docs(kb): {host} work", "-m", f"KB-Work: {host}")
        repo.git("checkout", "-q", "main")
        host_worker = Path(repo.file(f".claude/worktrees/agent-{host}"))
        repo.git("worktree", "add", "-q", str(host_worker), f"work/{host}")

        def land_host(push):
            env = plain_push(repo, tmp_path, lane_module="", land_stale=[], land_eval=[], land_lint=[], land_push=push)
            return bl(repo, "land", host, env=env)

        code, out = land_host(["python3", "-c", "import sys; sys.exit(3)"])
        assert code != 0 and "land stopped at step python3 -c" in out and "exited 3" in out, out
        assert "No such file" not in out and origin_main(scenario) == moved and item(scenario, host)["status"] == "doing"
        assert f"git worktree add .claude/worktrees/agent-{host} work/{host}" in out and not host_worker.exists(), out
        code, out = land_host(["git", "push", "--no-verify", "origin", "HEAD:main"])
        assert code == 0 and "landed" in out, out
        assert "merge request" not in out and item(scenario, host)["status"] == "done", out
        assert scenario.origin.git("show", f"main:{nested}").startswith(f"# {host}") and origin_main(scenario) != moved


class TestOwnCheckoutDrafts:
    def test_land_moves_own_checkout_drafts_then_refuses_other_files_and_check_stale_touch_branch_added_removed(
            self, scenario, tmp_path):
        repo, sp, (good,) = planned(scenario, ("good", "kb/_self/good.md", "python3 _tools/backlog.py list --kind sprint"),
                                    hooks=False)
        env = plain_push(repo, tmp_path, land_lint=[])  # the default push stays: the sync gate lints the landing itself
        before = origin_main(scenario)
        work(repo, good, "kb/_self/good.md")
        repo.git("checkout", "-q", "main")  # land runs on main in this checkout, which holds the hook's drafts
        aside = Path(repo.file("_cache/intake-drafts")) / Path(repo.path).name

        def plant(name, links):
            doc = {"id": name, "kind": "bug", "title": "A finding", "status": "draft", "links": links}
            repo.write(f"{PLAN}/{name}.json", json.dumps(doc) + "\n")
            return f"{PLAN}/{name}.json"

        filed = ["fingerprint 0123456789ab", "detector drift"]
        draft, handmade, stray = plant("BG-0a1b2c3d", filed), plant("BG-0e1f2a3b", ["parked: later"]), "kb/_self/stray.md"
        repo.write(stray, "# stray\n")
        for other in (stray, handmade):  # one file that is no filed draft keeps every draft where it is
            code, out = bl(repo, "land", good, env=env)
            assert code != 0 and "land stopped at step clean tree" in out and "moved the untracked" not in out, out
            assert Path(repo.file(draft)).is_file() and not aside.exists(), out
            (Path(repo.file(other))).unlink()

        # a later step stops it: the drafts stay aside
        code, out = bl(repo, "land", good, "--branch", "work/ST-00000000", env=env)
        assert code != 0 and "land stopped at step branch" in out, out
        assert "moved the untracked intake draft BG-0a1b2c3d.json out of this checkout" in out, out
        assert (aside / "BG-0a1b2c3d.json").is_file() and not Path(repo.file(draft)).exists(), out
        assert origin_main(scenario) == before and repo.git("status", "--porcelain").strip() == ""

        second = plant("BG-4c5d6e7f", ["fingerprint ba9876543210", "detector trailers"])
        code, out = bl(repo, "land", good, env=env)
        assert code == 0 and "landed" in out, out
        assert "moved the untracked intake draft BG-4c5d6e7f.json out of this checkout" in out, out
        assert (aside / "BG-4c5d6e7f.json").is_file() and (aside / "BG-0a1b2c3d.json").is_file(), out
        assert not Path(repo.file(second)).exists() and item(scenario, good)["status"] == "done"
        assert repo.rev("main") == origin_main(scenario) != before

        # `check`'s moved-or-deleted touch rule reads the integration main's history: a file the branch added and
        # removed before it reached main is no error, one main has and the branch removed is
        ghost, held = "kb/_self/ghost.md", "kb/_self/good.md"
        for rel in (ghost, held):
            ok(repo, "new", "story", "--title", f"Touch {Path(rel).stem}", "--goal", "The doc.", "--touch", rel)
        repo.commit("test: two stories outside a sprint", PLAN)
        repo.git("checkout", "-q", "-b", "work/branch-only", "main")
        repo.write(ghost, "# ghost\n")
        repo.commit("test: the branch adds a doc", ghost)
        repo.git("rm", "-q", ghost, held)
        repo.commit("test: the branch removes it and a doc main has")
        code, out = bl(repo, "check")
        assert f"touches names {held}, which git history has and the working tree lacks" in out, out
        assert ghost not in out, out


def test_done_research_carried_item_takes_the_research_commit_as_evidence_and_refuses_one_that_changed_no_touched_file(
        scenario):
    """An item with no KB-Work commit of its own is done when a KB-Work commit of the sprint's goal research story
    changed a file of its touches and its checks pass: the evidence commit is that commit, its `carried_by` the story.
    Planted failures, each refused as having no work commit: no commit of the research story yet, a research commit
    that changed no file of the item's touches, and a sibling whose touches the research commit did not change."""
    carried, bare = "kb/public/agents/carried.md", "kb/_self/bare.md"
    check = "python3 _tools/backlog.py list --kind sprint"
    repo, sp, (mine, other) = planned(scenario, ("carried", carried, check), ("bare", bare, check), hooks=False)
    research = re.search(r"(ST-[a-z0-9]+)\s.*Research sprint goal", ok(repo, "list", "--sprint", sp)).group(1)

    code, out = bl(repo, "done", mine, "--dry-run")  # no commit of the research story yet
    assert code != 0 and "no commit on HEAD carries the trailer KB-Work" in out, out

    repo.write("kb/public/agents/other-note.md", "# note\n")  # a research commit that changed no file of the touches
    repo.git("add", "kb/public/agents/other-note.md")
    repo.git("commit", "-q", "-m", "docs(kb): research", "-m", f"KB-Work: {research}")
    code, out = bl(repo, "done", mine, "--dry-run")
    assert code != 0 and "no commit on HEAD carries the trailer KB-Work" in out, out

    repo.write(carried, "# carried\n\nThe research wrote the fact.\n")
    repo.git("add", carried)
    repo.git("commit", "-q", "-m", "docs(kb): research", "-m", f"KB-Work: {research}")
    sha = repo.rev("HEAD")
    code, out = bl(repo, "done", other, "--dry-run")  # its touches are not the research commit's
    assert code != 0 and "no commit on HEAD carries the trailer KB-Work" in out, out
    code, out = bl(repo, "done", mine, "--dry-run")
    assert code == 0 and "would be done" in out and f"the evidence is {sha[:10]}" in out, out
    code, out = bl(repo, "done", mine)
    assert code == 0 and f"done {mine}" in out and f"at {sha[:10]}" in out, out
    done = json.loads(repo.read(f"{PLAN}/{mine}.json"))
    assert done["status"] == "done" and done["evidence"]["commit"] == sha, done
    assert done["evidence"]["carried_by"] == research and done["evidence"]["checks"][0]["exit"] == 0, done


class TestCodeLaneLand:
    def test_land_code_lane_without_wait_merge_names_the_lane_and_the_rerun_before_its_push_and_with_the_flag_does_not(
            self, scenario, tmp_path):
        """A land of an item whose commits go through the code lane, run without --wait-merge, says before its push
        that the lane is code and that `land ID --wait-merge SECONDS` finishes it in one run; with the flag it does not."""
        nested = "kb/_self/lane/host.md"  # a code-lane path of the kb's lanes
        repo, sp, (iid,) = planned(scenario, ("lane", nested, "python3 _tools/backlog.py list --kind sprint"), hooks=False)
        work(repo, iid, nested)
        repo.git("checkout", "-q", "main")
        env = plain_push(repo, tmp_path, land_stale=[], land_eval=[], land_lint=[], land_push=["python3", "-c", "pass"])
        code, out = bl(repo, "land", iid, env=env)
        notice = f"goes through the code lane: this run pushes the merge request of branch code/{iid}"
        assert code == 0 and notice in out and f"backlog.py land {iid} --wait-merge SECONDS" in out, out
        assert out.index(notice) < out.index("is not done yet"), out
        code, out = bl(repo, "land", iid, "--wait-merge", "0", env=env)
        assert "goes through the code lane" not in out and "--wait-merge SECONDS" not in out, out


def test_empty_selection_refused_gone_once_done_dry_run_gone_and_reopened_refs(monkeypatch, capsys, scenario):
    """Planted failure: tests.py -k zzz_no_such_test exits 2 before any worker starts, names its selector in one line
    and records exit 2 with selected 0; a done item's check that collects nothing is found gone once, kept in its
    evidence and named by close's summary, and the next rerun does not run it. Then, in a scenario, a review's
    `done --dry-run` records no gone evidence and leaves the tree clean, and its `done --commit` commits that record
    with the review's own, so the tree is clean again. On the same finished sprint, the reopen refs
    (`refs/kb-reopened/ID`, shared by every worktree of the clone): a drop inside a sprint prunes nothing; a drop
    outside one in a worktree that branched before an item was filed on main deletes the ref of the item it
    removes and of one already gone, and keeps that of an item the checkout holds and of the one filed on main
    since; with no origin/main it prunes nothing; `close` deletes the refs of the items it removes and keeps a
    live item's."""
    import bl_land
    import tests as kbtests
    rows = []
    monkeypatch.setattr(kbtests, "record_run", lambda mode, entry, args, workers=None: rows.append(
        kbtests.run_fields(mode, entry, workers, False)))
    monkeypatch.setattr(kbtests, "run_pytest", lambda args: pytest.fail("a worker run started"))
    assert kbtests.run_main(["-k", "zzz_no_such_test"]) == 2
    said = capsys.readouterr().err.strip().splitlines()
    assert len(said) == 1 and "`-k zzz_no_such_test` collects no test in _tools/" in said[0], said
    assert [(r["mode"], r["exit"], r["selected"], r["workers"]) for r in rows] == [("keyword", 2, 0, 0)], rows
    assert bl_land.selected_nothing(2, said[0]) and not bl_land.selected_nothing(2, "usage: x\nx: error: y")

    check = {"run": ["python3", "_tools/tests.py", "-k", "zzz_no_such_test"]}
    done = {"id": "ST-00000001", "kind": "story", "title": "Done", "status": "done", "checks": [check],
            "evidence": {"commit": "0" * 40, "checks": []}}

    class FakeBacklog:
        root, items, saved = Path("."), {done["id"]: done}, []

        def sprint_items(self, sid):
            return [done["id"]]

        def save(self, it):
            self.saved.append(it["id"])

        def ancestors(self, iid):
            return []

        def label(self, iid):
            return iid

    runs = []
    monkeypatch.setattr(bl_land, "run_check", lambda root, c: runs.append(c) or (False, 2, said[0]))
    fake = FakeBacklog()
    assert bl_land.rerun_done_checks(fake, "SP-00000001") == [] and len(runs) == 1 and fake.saved == [done["id"]]
    assert bl_land.rerun_done_checks(fake, "SP-00000001") == [] and len(runs) == 1, runs  # not run again
    assert "gone check: python3 _tools/tests.py -k zzz_no_such_test" in bl_land.summary_line(fake, done["id"], set())

    # the check passes while the doc exists and prints pytest's `no tests ran` once a later commit deletes it
    gone = ("python3 -c \"import pathlib, sys; ok = pathlib.Path('kb/_self/good.md').is_file(); "
            "ok or print('no tests ran'); sys.exit(not ok)\"")
    exits = "python3 -c \"import sys; sys.exit(0)\""
    probe = "python3 -c \"import sys; sys.exit(1)  # reads kb/_querylog/ops\""
    repo, sp, (good, rows, probe_id) = planned(
        scenario, ("good", "kb/_self/good.md", gone), ("rows", "kb/_querylog/rows.jsonl", exits),
        ("probe", "_tools/probe.py", probe), hooks=False)
    (code, out), dropped = batch(repo, ("precheck", sp), ("drop", probe_id, "--why", "only its precheck line was read"))
    warned = [ln for ln in out.splitlines() if ln.startswith("warning: ") and "query-log" in ln]
    # a code-lane item whose check reads the store: only a delivery after the merge
    assert code == 0 and len(warned) == 1 and f"{probe_id}" in warned[0] and "after the merge" in warned[0], out
    assert dropped[0] == 0, dropped
    # a story of the store only has no KB-Work commit: the automatic delivery that is on origin/main is its evidence
    repo.write("kb/_querylog/rows.jsonl", "{}\n")
    repo.git("add", "kb/_querylog/rows.jsonl")
    repo.git("commit", "-q", "--no-verify", "-m", "chore(kb): query log store, 1 run file(s)", "-m", "KB-Auto: querylog")
    code, out = bl(repo, "done", rows, "--dry-run")  # planted failure: the delivery is not on origin/main yet
    assert code == 1 and "no commit on HEAD carries the trailer KB-Work" in out and "KB-Auto: querylog" in out, out
    repo.git("push", "-q", "--no-verify", "origin", "main")
    code, out = bl(repo, "done", rows, "--dry-run")
    assert code == 0 and "the evidence is the automatic query-log delivery" in out and "would be done" in out, out
    ok(repo, "done", rows, "--commit")
    work(repo, good, "kb/_self/good.md")
    repo.git("checkout", "-q", "main")
    repo.git("merge", "-q", "--ff-only", f"work/{good}")
    ok(repo, "done", good, "--commit")
    repo.git("rm", "-q", "kb/_self/good.md")
    repo.git("commit", "-q", "--no-verify", "-m", "test: the doc the check reads is deleted")
    stories = ok(repo, "list", "--sprint", sp)
    research = re.search(r"(ST-[a-z0-9]+)\s.*Research sprint goal", stories).group(1)
    review = re.search(r"(ST-[a-z0-9]+)\s.*Review sprint", stories).group(1)
    results = batch(repo, ("claim", research, "--by", "t", "--commit"),
                    ("set", research, "--notes", "No outside facts: the goal is internal."),
                    ("done", research, "--commit"),
                    ("set", review, "--check", "python3 _tools/backlog.py list --kind sprint"))  # not the whole suite
    assert all(code == 0 for code, _ in results), results
    repo.git("add", "-A")
    repo.git("commit", "-q", "--no-verify", "-m", "test: a cheap review check")
    assert repo.git("status", "--porcelain").strip() == ""

    code, out = bl(repo, "done", review, "--dry-run")
    assert code == 0 and "would be done" in out and f"gone rerun {good}" in out, out
    assert repo.git("status", "--porcelain").strip() == "", out  # the dry run wrote no evidence
    code, out = bl(repo, "done", review, "--commit")
    assert code == 0 and f"gone rerun {good}" in out, out
    assert repo.git("status", "--porcelain").strip() == "", out  # the evidence went into the commit of the done
    evidence = json.loads(repo.read(f"{PLAN}/{good}.json"))["evidence"]
    assert evidence["gone"] == [["python3", "-c", gone.split('"')[1]]], evidence
    assert json.loads(repo.read(f"{PLAN}/{review}.json"))["status"] == "done"

    def story_step(*more):
        return ("new", "story", "--title", "Reopen refs", "--goal", "The doc.", "--touch", "kb/_self/good.md", *more)

    def story(*more):
        return new_id(ok(repo, *story_step(*more)))

    def marks():
        return set(repo.git("for-each-ref", "--format=%(refname:strip=2)", "refs/kb-reopened/").split())

    def mark(*ids):
        blob = repo.git("hash-object", "-w", f"{PLAN}/{good}.json").strip()
        for i in ids:
            repo.git("update-ref", f"refs/kb-reopened/{i}", blob)

    two = batch(repo, story_step(), story_step())
    assert all(code == 0 for code, _ in two), two
    first, second = (new_id(out) for _, out in two)
    repo.commit("test: two stories outside a sprint", PLAN)
    old = Repo(Path(repo.path).parent / "older", repo.env)
    repo.git("worktree", "add", "-q", "-b", "older", old.path, "main")  # branched before `late` is filed
    late = story("--sprint", sp)
    repo.commit("test: a story filed on main after the worktree branched", PLAN)
    repo.git("push", "-q", "--no-verify", "origin", "main")
    earlier = "ST-0e1f2a3b"  # a removal an earlier command left a mark of: no file anywhere
    mark(earlier, first, second, late, good)
    every = {earlier, first, second, late, good}

    code, out = bl(repo, "drop", late, "--why", "a story of the sprint")
    assert code == 0 and "reopen mark" not in out and marks() == every, out  # inside a sprint: nothing pruned
    repo.commit("test: the dropped story stays in its sprint", PLAN)

    main = repo.rev("origin/main")
    repo.git("update-ref", "-d", "refs/remotes/origin/main")
    code, out = bl(old, "drop", first, "--why", "no origin/main to judge by")
    assert code == 0 and "reopen mark" not in out and marks() == every, out
    repo.git("update-ref", "refs/remotes/origin/main", main)

    code, out = bl(old, "drop", second, "--why", "outside a sprint, in the older worktree")
    assert code == 0 and "deleted 3 reopen mark(s) of removed items" in out, out
    assert marks() == {late, good}, out  # `late` is filed on main since the worktree branched: kept

    mark(first)  # the main checkout still holds it
    code, out = bl(repo, "close", sp, "--commit")
    assert code == 0 and "deleted 2 reopen mark(s) of removed items" in out, out
    assert marks() == {first}, out  # `good` and `late` went with the sprint


def test_land_names_why_no_work_rows_late_or_missing_and_undelivered_land_names_first_gate_error_and_land_names_check_trailers_refusal_and_manual_push_logs_distill(tmp_path, monkeypatch, capsys):
    """A landing that exits 0 with no line of the item in the committed work sidecars says which of three it is: a
    worker's row in the spool (rows late, a `land:` line naming the session and its state, no warning), a work sidecar
    naming the item that sits in a local store the integration main lacks (undelivered, the store named), or no worker's
    row anywhere (missing, the claim of the orchestrator's own session not counting as one, and the line saying why: the
    state of the spool file of the session `dispatch` recorded, or that the item was claimed and worked in the
    orchestrator's own session, whose window `backlog.py cost` attributes); a sidecar the checkout holds says
    nothing, and the exit is 0 in each. A push run by hand (the default `out`) writes its lines to that distill.log
    too, so the warning names the failed gate of the last run, not an older automatic run's; a run whose standard
    output already is that file writes each line once."""
    import types

    import bl_base
    import bl_land
    import kbpublic
    import ql_capture
    iid, other, sid = "TK-aaaaaaaa", "TK-bbbbbbbb", "c0ffee11-worker-session"
    spool, store, root = tmp_path / "home" / "spool", tmp_path / "home" / "store", tmp_path / "clone"
    spool.mkdir(parents=True)
    (root / "kb" / "_querylog" / "work" / "2026-10").mkdir(parents=True)
    monkeypatch.setattr(ql_capture, "spool_dir", lambda: spool)
    monkeypatch.setattr(bl_base, "main_worktree_spool", lambda r: None)
    monkeypatch.setattr(kbpublic, "integration_remote", lambda r: "origin")
    monkeypatch.setattr(bl_land, "Backlog", lambda r: types.SimpleNamespace(descendants=lambda i: []))

    def rows(item, action):
        return json.dumps({"id": f"{item}-{action}", "ts": "2026-10-10T10:00:00Z", "surface": "work",
                           "session_id": sid, "prompt_id": "p1", "action": action, "item": item}) + "\n"

    def landed():
        code = bl_land.ops_land(lambda bl, a: 0)(types.SimpleNamespace(root=root), types.SimpleNamespace(id=iid))
        assert code == 0
        return capsys.readouterr().out.strip().splitlines()

    session = spool / f"{sid}.jsonl"
    session.write_text(rows(iid, "branch"), encoding="utf-8")
    out = landed()
    assert len(out) == 1 and out[0].startswith(f"land: {iid}'s work rows are late: session {sid[:8]}"), out
    assert "still open" in out[0] and "landed with no work rows" not in out[0], out
    session.with_suffix(".end").write_text("", encoding="utf-8")
    assert "closed and not distilled" in landed()[0]
    session.with_suffix(".end").unlink()

    session.write_text(rows(iid, "agent-stop"), encoding="utf-8")  # a worker started with the Agent tool
    assert landed()[0].startswith(f"land: {iid}'s work rows are late")
    session.write_text(rows(iid, "claim") + rows(other, "branch"), encoding="utf-8")  # the orchestrator's own claim
    out = landed()
    assert len(out) == 1 and out[0].startswith(f"warning: {iid} landed with no work rows (missing)"), out
    assert f"claimed and worked in the orchestrator's own session {sid[:8]} (still open in " in out[0], out
    assert f"`backlog.py cost {iid}` attributes the prompts of that claim's window" in out[0], out
    assert "dispatch recorded" not in out[0] and "a worker started without the capture hooks" not in out[0], out
    # that window is the item's in `backlog.py cost`: the open session's claim row gives the item a line
    item_file = root / "kb" / "_self" / "backlog" / f"{iid}.json"
    item_file.parent.mkdir(parents=True)
    item_file.write_text(json.dumps({"id": iid, "kind": "task", "status": "doing"}), encoding="utf-8")
    import bl_cost
    import kbusage
    model, counts = "claude-sonnet-5-5", {"requests": 2, "in": 100, "cw": 0, "cw1h": 0, "cr": 0, "out": 1}
    usage = {"id": "u1", "ts": "2026-10-10T10:00:01Z", "surface": "usage", "session_id": sid, "prompt_id": "p1",
             "reader": kbusage.READER_VERSION, "usage": {"main": {model: counts}, "start": 0}}
    with open(session, "a", encoding="utf-8") as f:
        f.write(json.dumps(usage) + "\n")
    lines, info = bl_cost.open_lines(root)
    assert info and info[0]["worked"] == {iid} and info[0]["session"] == sid, info
    assert [x["item"] for x in lines] == [iid] and lines[0]["direct"][model]["in"] == 100, lines
    assert "orchestrator's own session" in landed()[0]  # the usage row changes nothing the warning says
    session.write_text(rows(other, "claim"), encoding="utf-8")  # planted: a claim of another item names nothing here
    out = landed()
    assert out[0].startswith(f"warning: {iid} landed with no work rows (missing)"), out
    assert "orchestrator's own session" not in out[0] and "a worker started without the capture hooks" in out[0], out
    assert bl_cost.open_lines(root) == ([], [])  # and `cost` attributes nothing of that session to the item

    # dispatch recorded the worker's session: the warning names what its spool file is, or that none is in the spools
    worker, ledger = "deadbeef-dispatched-worker", tmp_path / "claims.json"
    ledger.write_text(json.dumps({iid: {"by": "t", "session": sid, "worker_session": worker}}), encoding="utf-8")
    monkeypatch.setattr(bl_land, "claims_ledger", lambda r: (str(root), ledger))
    out = landed()
    assert len(out) == 1 and out[0].startswith(f"warning: {iid} landed with no work rows (missing)"), out
    assert f"dispatch recorded worker session {worker[:8]} for it: no spool file of it in " in out[0], out
    assert "distill already took it and no committed work sidecar names the item" in out[0], out
    wfile = spool / f"{worker}.jsonl"
    wfile.write_text(rows(other, "branch").replace(sid, worker), encoding="utf-8")  # its prompt was on another branch
    out = landed()
    assert f"dispatch recorded worker session {worker[:8]} for it: its spool file " in out[0], out
    assert f"{worker}.jsonl is still open and holds no branch, agent-start or agent-stop row naming it" in out[0], out
    wfile.with_suffix(".end").write_text("", encoding="utf-8")
    assert f"{worker}.jsonl is closed and not distilled and holds no branch" in landed()[0]
    wfile.with_suffix(".end").unlink()
    wfile.write_text(rows(iid, "branch").replace(sid, worker), encoding="utf-8")  # its branch row: late, no warning
    out = landed()
    assert len(out) == 1 and out[0].startswith(f"land: {iid}'s work rows are late: session {worker[:8]}"), out
    wfile.unlink()
    session.write_text(rows(iid, "claim") + rows(other, "branch"), encoding="utf-8")
    out = landed()  # both reasons at once: the worker's absent file and the orchestrator's claim
    assert "no spool file of it in" in out[0] and "orchestrator's own session" in out[0], out
    ledger.unlink()  # no ledger record of the dispatch: only the claim
    assert "dispatch recorded" not in landed()[0]

    sidecar = store / "work" / "2026-10" / "20261010T100000Z-0a1b2c3d.jsonl"
    sidecar.parent.mkdir(parents=True)
    counts = {"requests": 1, "in": 1, "cw": 0, "cw1h": 0, "cr": 0, "out": 1}
    sidecar.write_text(json.dumps({"run": sidecar.stem, "reader": 1, "counts": {"items": 1}}) + "\n" + json.dumps(
        {"item": iid, "prompts": 0, "main": {}, "sub": {"kb-worker": {"claude-sonnet-5-5": counts}}}) + "\n",
        encoding="utf-8")
    out = landed()
    assert len(out) == 1 and out[0].startswith(f"warning: {iid} landed with no work rows on origin/main (undelivered)")
    assert f"{store.parent.name}/store holds 1 work sidecar(s) naming it" in out[0], out  # say() redacts the user name
    assert "origin/main lacks" in out[0] and "apply --push" in out[0], out
    assert "its last run did not deliver" not in out[0], out  # no distill.log: the warning stands as it was

    log = store.parent / "distill.log"  # the last run's gate stopped it: the warning names the gate and its first error
    log.write_text("apply --push: pushed 0a1b2c3d4 to origin/main\napply: run=1 records=2\n"
                   "  gate check.py: FAILED (exit 1): ERROR public/_gaps.md:7 cites kb/public/_gaps.md:1058, a file "
                   "that is not in root public\n  gate doc2query.py stale: FAILED (exit 1): stale=1\n"
                   "  gate querylog.py check: ok: problems=0\n"
                   "apply --push: kbgit.py sync exit 1: nothing pushed to main\n", encoding="utf-8")
    out = landed()
    assert len(out) == 1 and "its last run did not deliver, gate check.py: ERROR public/_gaps.md:7 cites" in out[0], out
    assert "and 1 other gate(s) failed" in out[0], out

    kept = tmp_path / "worktree" / "_cache" / "gate" / "20261010T100000Z-001-tests.py-changed.txt"
    kept.parent.mkdir(parents=True)  # the gate's whole output, which the log names: its first error line, not its last
    kept.write_text("tests.py: waiting for the host test lock\n.....F....F.\n=== FAILURES ===\n"
                    "    assert code == 0, out\nE       AssertionError: sources=3 errors=1\nE       assert 1 == 0\n"
                    "FAILED _tools/test_live_kb.py::test_check_py - AssertionError\n"
                    "FAILED _tools/test_other.py::test_other - assert False\n", encoding="utf-8")
    planted = ("  gate tests.py (changed): FAILED (exit 1): ===== 2 failed, 40 passed in 9.1s =====\n"
               f"  gate tests.py (changed) whole output: {kept} (2 test ids)\n"
               "apply --push: kbgit.py sync exit 1: nothing pushed to main\n")
    log.write_text(planted, encoding="utf-8")
    out = landed()
    assert len(out) == 1 and "its last run did not deliver, gate tests.py (changed): AssertionError: sources=3 errors=1" \
        in out[0], out
    assert "2 failed, 40 passed" not in out[0] and "other gate" not in out[0], out
    kept.unlink()  # the file is gone (the newest ten are kept): the summary line stands
    assert "gate tests.py (changed): ===== 2 failed, 40 passed in 9.1s =====" in landed()[0]

    log.write_text("  gate check-trailers origin/main..HEAD: FAILED: commits=3 bad=1\n"  # no (exit N), the gate's last
                   "apply --push: kbgit.py sync exit 1: nothing pushed to main\n", encoding="utf-8")
    out = landed()
    assert len(out) == 1 and "its last run did not deliver, gate check-trailers origin/main..HEAD: commits=3 bad=1" \
        in out[0], out
    assert "kbgit.py sync exit 1" not in out[0], out
    log.write_text(log.read_text(encoding="utf-8") + "apply --push: pushed 5e6f7a8b9 to origin/main\n", encoding="utf-8")
    assert "its last run did not deliver" not in landed()[0]  # a push after the failure: nothing to name

    (root / "kb" / "_querylog" / "work" / "2026-10" / sidecar.name).write_text(sidecar.read_text(encoding="utf-8"),
                                                                              encoding="utf-8")
    assert landed() == []

    import ql_deliver  # a push run by hand leaves its lines in that distill.log, as the detached automatic one does
    qdir = store.parent
    log.write_text("apply --push: pushed 0a1b2c3d4 to origin/main\n", encoding="utf-8")  # an older automatic run
    assert bl_land.last_push_failure(store) is None

    class Failing:
        def __init__(self, home, qdir, run, apply_step, out, now_dt=None):
            self.out = out

        def __call__(self):
            self.out("apply: run=1 records=2")
            self.out("  gate check.py: FAILED (exit 1): ERROR public/_gaps.md:7 cites a file that is not in root public")
            self.out("apply --push: kbgit.py sync exit 1: nothing pushed to main")
            return 1

    monkeypatch.setattr(ql_deliver, "Pusher", Failing)
    capsys.readouterr()
    assert ql_deliver.push(home=tmp_path, qdir=qdir) == 1
    said = capsys.readouterr().out
    assert "gate check.py: FAILED (exit 1)" in said, said  # still on the standard output
    assert log.read_text(encoding="utf-8").count("apply --push: kbgit.py sync exit 1") == 1
    assert bl_land.last_push_failure(store) == "gate check.py: ERROR public/_gaps.md:7 cites a file that is not in root public"

    log.write_text("", encoding="utf-8")
    kept_stdout = sys.stdout
    with open(log, "a", encoding="utf-8") as detached:  # standard output already the log, as a hook's run has it
        monkeypatch.setattr(sys, "stdout", detached)
        try:
            assert ql_deliver.push(home=tmp_path, qdir=qdir) == 1
        finally:
            monkeypatch.setattr(sys, "stdout", kept_stdout)
    assert log.read_text(encoding="utf-8").count("apply: run=1 records=2") == 1


def test_precheck_plan_reword_names_anchors_of_a_root_whose_article_a_reworded_doc_fact_item_touches_and_research_rows_sibling_eval_touch(
        tmp_path, monkeypatch, capsys):
    """`precheck` warns of an item whose goal words a DOC fact reworded or added and whose touches name an article of a
    kb root (a directory with its `_root.md`) with no touch that covers that root's `_anchors.csv`, naming the root and
    the file to add. Planted failures: the item with only the article is warned of; a touch of the file, or a glob that
    covers it, a goal without the words, a `.csv` of the root and a doc outside a kb root are not. It also warns of an
    item whose touches name a kb/_self doc that a row the sprint's goal research story added (a commit with its
    KB-Work) names in expect_paths, without the _self eval file: the doc a row of an earlier commit names, the file
    itself, a glob that covers it, a row of another item's commit and the research story are not."""
    import bl_land
    from bl_base import Backlog
    for rel in ("kb/public/_root.md", "kb/_self/backlog.md"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("x\n", encoding="utf-8", newline="\n")
    article = "kb/public/ad/topic.md"
    cases = {"ST-aaaaaaa1": ("A DOC fact of the article is reworded.", [article]),
             "ST-aaaaaaa2": ("A DOC fact of the article is reworded.", [article, "kb/public/_anchors.csv"]),
             "ST-aaaaaaa3": ("The article rewords a fact.", [article, "kb/public/_*.csv"]),
             "ST-aaaaaaa4": ("The article holds a new fact.", [article]),
             "ST-aaaaaaa5": ("A DOC fact of the table is added.", ["kb/public/ad/table.csv"]),
             "ST-aaaaaaa6": ("A DOC fact of the doc is reworded.", ["kb/_self/backlog.md"]),
             "ST-aaaaaaa7": ("A DOC fact of the article is added.", ["kb/public/ad/*.md"])}
    plan = Backlog(tmp_path)
    plan.save({"id": "SP-aaaaaaa0", "kind": "sprint", "title": "Sprint", "status": "planned"})
    for iid, (goal, touches) in cases.items():
        plan.save({"id": iid, "kind": "story", "title": iid, "status": "todo", "sprint": "SP-aaaaaaa0", "goal": goal,
                   "touches": touches})
    monkeypatch.setattr(bl_land, "precheck_rows", lambda bl, sid: [])
    assert bl_land.cmd_precheck(Backlog(tmp_path), type("A", (), {"sprint": "SP-aaaaaaa0"})) == 0
    warned = {ln.split(":")[1].split()[0] for ln in capsys.readouterr().out.splitlines()
              if ln.startswith("warning: ") and "_anchors.csv" in ln}
    assert warned == {"ST-aaaaaaa1", "ST-aaaaaaa7"}, warned
    one = bl_land.bl_plan.anchors_warnings(plan, ["ST-aaaaaaa1"])
    assert len(one) == 1 and "kb root public" in one[0] and "add kb/public/_anchors.csv to its touches" in one[0], one

    eval_file = "kb/_self/_retrieval/lookup_eval.csv"
    head = "id,question,expect_paths,expect_verdict,allow_weak,expect_text,sets\n"
    repo = Repo(tmp_path)
    repo.git("init", "-q", "-b", "main")
    repo.write(eval_file, head + 'SE-001,"what does land refuse, and when",git.md,good,yes,it refuses,kb-item:land\n')
    repo.commit("base")
    repo.write("kb/_self/tools.md", "x\n")
    repo.commit("another item\n\nKB-Work: ST-aaaaaaby")
    repo.append(eval_file, "SE-002,what does a section window hold,tools.md;code.md,good,yes,a window,kb-item:land\n")
    repo.commit("research rows\n\nKB-Work: ST-aaaaaabz")
    assert bl_land.research_rows(Backlog(tmp_path), "SP-aaaaaaa0") == []  # no research story yet
    plan.save({"id": "ST-aaaaaabz", "kind": "story", "title": "Research", "status": "done", "sprint": "SP-aaaaaaa0",
               "goal_research": True, "goal": "Research.", "touches": [eval_file]})
    assert bl_land.research_rows(Backlog(tmp_path), "SP-aaaaaaa0") == ["kb/_self/code.md", "kb/_self/tools.md"]
    doc_cases = {"ST-aaaaaab2": ["kb/_self/tools.md"],
                 "ST-aaaaaab3": ["kb/_self/tools.md", eval_file],
                 "ST-aaaaaab4": ["kb/_self/git.md"],
                 "ST-aaaaaab5": ["kb/_self/code.*"],
                 "ST-aaaaaab6": ["kb/_self/tools.md", "kb/_self/_retrieval/*.csv"],
                 "ST-aaaaaab7": ["kb/_self/backlog.md"]}
    for iid, touches in doc_cases.items():
        plan.save({"id": iid, "kind": "story", "title": iid, "status": "todo", "sprint": "SP-aaaaaaa0",
                   "goal": "The doc says so.", "touches": touches})
    capsys.readouterr()
    assert bl_land.cmd_precheck(Backlog(tmp_path), type("A", (), {"sprint": "SP-aaaaaaa0"})) == 0
    warned = {ln.split(":")[1].split()[0] for ln in capsys.readouterr().out.splitlines()
              if ln.startswith("warning: ") and eval_file in ln}
    assert warned == {"ST-aaaaaab2", "ST-aaaaaab5"}, warned


def orphan_in(cwd, log, release, give_up=120):
    """The pid of a python process that stays in the directory CWD until the file RELEASE exists (or GIVE_UP seconds
    pass), its standard output appended to LOG and its parent (the launcher that started it) already gone: what a
    session-end hook's distill is while land looks at it. It ends on the test's signal, never after a fixed time, so a
    host too loaded to look within a second still finds it there."""
    stay = ("import os, sys, time; end = time.time() + float(sys.argv[2])\n"
            "while not os.path.exists(sys.argv[1]) and time.time() < end: time.sleep(0.05)")
    launcher = ("import subprocess, sys; log = open(sys.argv[2], 'ab'); p = subprocess.Popen([sys.executable, '-c', "
                "sys.argv[5], sys.argv[3], sys.argv[4]], cwd=sys.argv[1], stdin=subprocess.DEVNULL, "
                "stdout=log, stderr=log, start_new_session=True); print(p.pid)")
    started = subprocess.run([sys.executable, "-c", launcher, str(cwd), str(log), str(release), str(give_up), stay],
                             capture_output=True, text=True)
    return int(started.stdout.strip())


@pytest.mark.skipif(os.name == "nt", reason="Windows exposes no process's working directory")
class TestHookWait:
    def test_land_waits_hook_process_outlives_a_slow_look_of_a_finished_session_then_removes_its_worktree_and_multirepo_land_cleans_per_repository(
            self, tmp_path, capsys, monkeypatch):
        """The step of `land` that frees a finished worker's worktree, on a real worktree whose only process is a run
        its session's end hook started: it waits for it, removes the worktree, and says so. The process stays until
        land has looked at its standard output (the file `release`, made after that look), however long the look
        takes on a loaded host."""
        import bl_land
        import bl_procs
        repo = Repo(tmp_path / "clone")
        os.makedirs(repo.path)
        repo.git("init", "-q", "-b", "main")
        repo.write("a.txt", "a\n")
        repo.commit("base")
        worker = Path(repo.file(".claude/worktrees/agent-ST-00000001"))
        repo.git("worktree", "add", "-q", "-b", "work/ST-00000001", str(worker))
        log = Path(repo.file("_cache/querylog/distill.log"))  # the standard output of the run a SessionEnd starts
        log.parent.mkdir(parents=True)
        release = tmp_path / "land-has-looked"
        looked = bl_procs.hook_pids

        def look(root, pids, bases=None):
            found = looked(root, pids, bases)
            release.write_text("", encoding="utf-8")  # the orphan may end now: land has read what it holds
            return found

        monkeypatch.setattr(bl_procs, "hook_pids", look)
        pid = orphan_in(worker, log, release)
        try:
            why = bl_land.release_worker_worktree(Path(repo.path), worker, None, "work/ST-00000001")
        finally:
            try:
                os.kill(pid, 15)
            except OSError:
                pass
        said = capsys.readouterr().out
        assert why is None and not worker.exists(), (why, said)
        assert "land: waited " in said and "for the session-end hook to end" in said, said
        self.multirepo_land(tmp_path / "multi", capsys, monkeypatch)

    def multirepo_land(self, base, capsys, monkeypatch):
        """multirepo_land, on throwaway repositories built once with few git calls (empty commits, clones of bare
        origins): a workspace holding one item and three repositories, each with the worktree dispatch makes at
        `<worker dir>/<id>/<repo>` on `work/<id>`: api merged with a merge commit, web fast-forwarded, docs
        fast-forwarded and then given a commit its default branch lacks. The forge answers each repository's request
        from a table; `land_repositories` is `land`'s step of that name, and what it returns is read, not git."""
        import argparse

        import bl_base
        import bl_forge
        import bl_land
        iid = "ST-aaaaaaaa"
        ws, names = Repo(base / "ws"), {"api": "repos/api", "web": "repos/web", "docs": "repos/docs"}
        os.makedirs(ws.path)
        for k, v in (("NAME", "t"), ("EMAIL", "t@example.com")):  # the commits cmd_done makes in this process
            monkeypatch.setenv(f"GIT_AUTHOR_{k}", v)
            monkeypatch.setenv(f"GIT_COMMITTER_{k}", v)
        item = {"id": iid, "kind": "story", "title": "Multi", "status": "doing", "goal": "Merged in each repository.",
                "checks": [{"run": ["python3", "-c", "print('checked')"]}], "claimed_by": "t",
                "touches": [f"{n}/{n}.txt" for n in names], "repos": list(names)}
        ws.write(f"kb/_self/backlog/{iid}.json", json.dumps(item, indent=2) + "\n")
        ws.git("init", "-q", "-b", "main")
        ws.git("add", "-A")
        ws.git("commit", "-q", "-m", "plan")
        config = base / "config.json"
        config.write_text(json.dumps({"repositories": names, "item_dir": PLAN}), encoding="utf-8")
        monkeypatch.setattr(bl_base, "_LOADED", [])  # this workspace's settings, for this test only
        bl_base.load_settings(Path(ws.path), env={"KB_BACKLOG_CONFIG": str(config)})
        checkouts, trees = {}, {}
        for name, rel in names.items():
            origin = base / "origins" / f"{name}.git"
            ws.git("init", "-q", "-b", "main", "--bare", str(origin))
            ws.git("clone", "-q", str(origin), rel)
            checkouts[name] = Repo(Path(ws.path) / rel)
            checkouts[name].git("commit", "-q", "--allow-empty", "-m", "first")
            checkouts[name].git("push", "-q", "origin", "main")
            trees[name] = Repo(Path(ws.path) / ".claude" / "worktrees" / iid / name)
            checkouts[name].git("worktree", "add", "-q", "-b", f"work/{iid}", trees[name].path)
            trees[name].git("commit", "-q", "--allow-empty", "-m", f"{iid}: {name} work")
        states, seen = {}, []

        def request(root, branch=None, title_prefix=None, run=None):
            name = Path(root).name
            seen.append((name, title_prefix))
            return None if name not in states else bl_forge.Request(
                states[name], 7, f"{iid}: work", f"work/{iid}", f"https://gitlab.example.com/grp/{name}/-/merge_requests/7",
                None, None, False, False, None, "")

        monkeypatch.setattr(bl_forge, "read_request", request)
        bl = bl_base.Backlog(Path(ws.path))

        def refused(**states_now):
            states.clear()
            states.update(states_now)
            seen.clear()
            capsys.readouterr()
            with pytest.raises(bl_base.Refused) as e:
                bl_land.land_repositories(bl, iid)
            return str(e.value)

        # one request open and one missing: refused at `requests`, naming each repository and its state
        why = refused(api="merged", web="opened")
        assert "land stopped at step requests" in why and "nothing was removed or changed" in why, why
        assert "repository 'web': merge request !7" in why and "is opened, not merged" in why, why
        assert f"repository 'docs': no merge request titled '{iid}:' (state none)" in why and "'api'" not in why, why
        assert sorted(seen) == [(n, f"{iid}:") for n in sorted(names)], seen  # each request read once
        assert all(Path(t.path).is_dir() for t in trees.values())

        # the forge merges: api with a merge commit, web and docs by fast-forward; docs' worktree commits once more
        checkouts["api"].git("merge", "-q", "--no-ff", "-m", f"Merge branch 'work/{iid}' into 'main'", f"work/{iid}")
        for n in ("web", "docs"):
            checkouts[n].git("merge", "-q", "--ff-only", f"work/{iid}")
        for n in names:
            checkouts[n].git("push", "-q", "origin", "main")
        trees["docs"].git("commit", "-q", "--allow-empty", "-m", f"{iid}: docs more")  # a tip origin/main lacks
        merged = {n: "merged" for n in names}
        trees["web"].git("worktree", "lock", "--reason", "another tool", trees["web"].path)
        Path(trees["api"].file("dirty.txt")).write_text("uncommitted\n", encoding="utf-8")
        holder = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], cwd=trees["docs"].path)
        try:  # a dirty, a locked and a live-process worktree (a session that still runs): each named, none removed
            why = refused(**merged)
        finally:
            holder.kill()
            holder.wait()
        assert "land stopped at step repositories" in why and "nothing was removed" in why, why
        assert "repository 'api': its worktree" in why and "has uncommitted changes" in why, why
        assert "repository 'web': its worktree" in why and "locked (another tool)" in why, why
        assert "repository 'docs': its worktree" in why and f"pid {holder.pid}" in why, why
        assert all(Path(t.path).is_dir() for t in trees.values()), why
        trees["web"].git("worktree", "unlock", trees["web"].path)
        Path(trees["api"].file("dirty.txt")).unlink()

        seen.clear()
        repos = bl_land.land_repositories(bl, iid)
        assert [r.name for r in repos] == list(names) and len(seen) == 3, (repos, seen)  # read once more, once each
        assert not any(Path(t.path).exists() for t in trees.values()) and all(r.tip for r in repos)
        evidence = bl_land.repo_evidence(repos)
        merge_line = checkouts["api"].git("rev-list", "--parents", "-1", "HEAD").split()
        assert len(merge_line) == 3  # the merge commit and its two parents
        assert evidence == {
            "api": {"request": "https://gitlab.example.com/grp/api/-/merge_requests/7", "commit": merge_line[0]},
            "web": {"request": "https://gitlab.example.com/grp/web/-/merge_requests/7",
                    "commit": checkouts["web"].rev("HEAD")},  # a fast-forward: the branch's tip itself
            "docs": {"request": "https://gitlab.example.com/grp/docs/-/merge_requests/7", "commit": ""}}, evidence
        said = capsys.readouterr().out
        assert "repository docs: no merge commit found" in said and "repository api: removed its worktree" in said, said

        # done: the work is merged in the repositories, so land's evidence stands in for a commit of the workspace
        args = dict(id=iid, commit=True, trailer=[])
        with pytest.raises(bl_base.Refused, match=r"merged in its repositories.*run land"):
            bl_land.cmd_done(bl, argparse.Namespace(dry_run=True, **args))
        assert bl_land.cmd_done(bl, argparse.Namespace(dry_run=False, repositories=evidence, **args)) == 0
        saved = json.loads(Path(ws.file(f"kb/_self/backlog/{iid}.json")).read_text(encoding="utf-8"))
        assert saved["status"] == "done" and saved["evidence"]["repositories"] == evidence, saved
        committed = ws.git("log", "-1", "--format=%s", "--name-only").splitlines()
        assert committed[0].startswith(f"chore(backlog): done {iid}") and f"kb/_self/backlog/{iid}.json" in committed

        # after the landing the branches on the default branch go (api's here; docs' is kept and said), and close's
        # helper removes what is left: web's worktree, one more worktree of its merged branch, and then the branch
        assert bl_land.delete_repo_branches([repos[0], repos[2]], iid) == ["api"]
        assert "repository docs: kept work/" in capsys.readouterr().out
        checkouts["web"].git("worktree", "add", "-q", trees["web"].path, f"work/{iid}")
        kept = bl_land.clean_repository_leftovers(Path(ws.path), iid, [(n, Path(checkouts[n].path)) for n in names])
        assert kept == 1 and not Path(trees["web"].path).exists() and not Path(trees["web"].path).parent.exists()
        said = capsys.readouterr().out
        assert "close: repository web: deleted the landed branch" in said and "close: repository docs: kept" in said, said

    def test_land_waits_hook_at_most_the_bound_and_not_for_a_process_whose_parent_lives(self, monkeypatch):
        import bl_land
        import bl_procs
        now = [0.0]
        looks = []
        monkeypatch.setattr(bl_land, "live_processes", lambda path: looks.append(now[0]) or ([(4242, "python3")], None))
        monkeypatch.setattr(bl_procs, "hook_pids", lambda root, pids: {4242})

        def table(parent):
            return {4242: (parent, 0, "python3"), 1: (0, 0, "launchd"), 77: (1, 0, "claude")}

        monkeypatch.setattr(bl_procs, "process_table", lambda: table(1))  # its parent is gone: a hook in flight
        sleeps = []
        procs, waited, hooks = bl_land.wait_for_hooks(
            Path("w"), [(4242, "python3")], clock=lambda: now[0], sleep=lambda s: (sleeps.append(s), now.__setitem__(
                0, now[0] + s)))
        assert procs == [(4242, "python3")] and waited == bl_procs.HOOK_GRACE_S == 60 and hooks == {4242}, procs
        assert len(sleeps) == 60 and looks[-1] == 60.0, (len(sleeps), looks[-1])  # it looked each second, then gave up

        monkeypatch.setattr(bl_procs, "process_table", lambda: table(77))  # a live session's own process: no wait
        now[0], sleeps[:] = 0.0, []
        procs, waited, _ = bl_land.wait_for_hooks(Path("w"), [(4242, "python3")], clock=lambda: now[0],
                                                  sleep=lambda s: sleeps.append(s))
        assert procs == [(4242, "python3")] and waited == 0 and sleeps == []


def test_stage_back_commits_the_copies_alone_and_refuses_a_differing_base_and_a_stale_doc_not_named_and_check_commits_nothing(
        scenario, tmp_path):
    """`stage-back ID` on a worker's worktree with two staging copies (a changed file and a new one): a copy whose
    recorded base differs is refused, a stale doc `--self-reviewed` does not name is refused, `--check` puts the
    worktree back as it was, and the run that names the docs adds one commit that holds the two files only."""
    skill, new = ".claude/skills/kb-gap/SKILL.md", ".claude/skills/demo/SKILL.md"
    repo, sp, (iid,) = planned(scenario, ("gap", skill, "python3 _tools/selfdoc.py check"), hooks=False)
    ok(repo, "set", iid, "--add-touch", new)
    repo.commit("test: the second touch", PLAN)
    wt = Path(repo.path) / ".claude" / "worktrees" / f"agent-{iid}"
    repo.git("worktree", "add", "-q", "-b", f"work/{iid}", str(wt), "main")
    tree = Repo(wt, repo.env)
    # the checks read the worktree's docs and the one tool they run: the other tools are left out of it (tracked, not
    # checked out), so the docs check does not parse every tool of the clone three times over
    bulk = [f for f in tree.git("ls-files", "_tools").splitlines()
            if f.endswith(".py") and f.count("/") == 1 and f not in ("_tools/selfdoc.py", "_tools/kbcommon.py")]
    tree.git("update-index", "--skip-worktree", *bulk)
    for f in bulk:
        (wt / f).unlink()
    # the docs check must pass whatever the working tree's docs hold: a dead section reference the seed carries is
    # mended in the worktree (one commit before its base is read), so the check's verdict is the staged copies' alone
    p = subprocess.run([sys.executable, "_tools/selfdoc.py", "check"], cwd=wt, capture_output=True, text=True)
    dead = re.findall(r"^PROBLEM (\S+?):\d+: \(\S+, (.+?)\) names no heading", p.stdout, re.M)
    for path, heading in dead:
        tree.write(path, tree.read(path).replace(heading, "Sprints"))
    if dead:
        tree.commit("test: mend dead section references", *sorted({path for path, _ in dead}))
    scratch = Path(repo.path) / "_cache" / "scratch" / iid
    # the brief's rules section is not what is read here, and its kb pack would build a cold index of the whole kb
    code, out = bl(repo, "brief", iid, env=plain_push(repo, tmp_path, kb_root=""))  # the report's problems=0 command
    assert code == 0 and f"stage-back {iid} --check`" in out and "`problems=` count for what you staged" in out, out
    original = (wt / skill).read_bytes()
    for rel, text in ((skill, original.decode("utf-8") + "\nA line the worker added.\n"), (new, "# demo\n")):
        copy = scratch / "staging" / rel
        copy.parent.mkdir(parents=True, exist_ok=True)
        copy.write_text(text, encoding="utf-8", newline="\n")
    bases = scratch / "staging-bases.json"
    good = {skill: hashlib.sha256(original).hexdigest(), new: None}
    head = tree.rev("HEAD")

    def untouched():
        assert tree.rev("HEAD") == head and tree.git("status", "--porcelain").strip() == "", tree.git("status")
        assert (wt / skill).read_bytes() == original and not (wt / new).exists()

    bases.write_text(json.dumps({**good, skill: "0" * 64}), encoding="utf-8")  # the worktree's file is not its base
    code, out = bl(repo, "stage-back", iid)
    assert code == 1 and f"{skill}: the worktree's file is not the one its copy was made from" in out, out
    untouched()

    bases.write_text(json.dumps(good), encoding="utf-8")
    code, out = bl(repo, "stage-back", iid, "--check")
    assert code == 0 and "selfdoc.py check: problems=0" in out, out
    stale = re.search(r"selfdoc\.py stale --since HEAD: (.+)", out).group(1).split(", ")
    assert "AGENTS.md" in stale and "committed" not in out, out
    untouched()

    code, out = bl(repo, "stage-back", iid)  # the stale docs are not named: refused, nothing committed
    assert code == 1 and "not named by --self-reviewed" in out and "refused" in out, out
    untouched()

    args = [x for d in stale for x in ("--self-reviewed", d)]
    code, out = bl(repo, "stage-back", iid, *args, "--trailer", "Session: stage-back test")
    assert code == 0 and re.search(r"committed \w+ chore\(backlog\): stage-back", out), out
    assert tree.git("rev-list", "--count", f"{head}..HEAD").strip() == "1", out
    assert sorted(tree.git("show", "--name-only", "--format=", "HEAD").split()) == sorted([new, skill])
    trailers = tree.git("log", "-1", "--format=%(trailers:only,unfold)").splitlines()
    assert f"KB-Work: {iid}" in trailers and f"Self-Reviewed: {', '.join(stale)}" in trailers, trailers
    assert "Session: stage-back test" in trailers and (wt / new).read_text(encoding="utf-8") == "# demo\n"
    assert tree.git("status", "--porcelain").strip() == ""
