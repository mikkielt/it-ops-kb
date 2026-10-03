"""The items a run landed are counted up to the integration main, not the runner worktree's HEAD: a run that lands an
item through a code/<id> merge request leaves the done commit on the integration remote's main only, so
`autopilot.run_landed` (the count runs.jsonl records) and `runner-status` (what it prints) read `<remote>/main` after
one bounded fetch. The tests named run_landed_counts_origin_main are the bug's checks. Throwaway repositories with a
local bare remote; no network, no process but git."""
import subprocess, types

import pytest

import autopilot, bl_base
from conftest import Repo, git_env
from test_autopilot import SP, T1, OUTSIDE, world as _world_fixture

ITEMS = [f"TK-{c}{'a' * 7}" for c in "bcdefghijkmn"]  # sprint items, eight characters after the prefix
OTHERS = [f"TK-{c}{'z' * 7}" for c in "bcdefg"]  # items of no sprint the test counts

world = _world_fixture


def done_msg(iid):
    return f'chore(backlog): done {iid} "t"\n\nKB-Work: {iid}'


def claim_msg(iid):
    return f'chore(backlog): claim {iid} "t"\n\nKB-Work: {iid}'


class Land:
    """A clone on the branch orch with a bare remote origin, and a second clone that lands commits on origin's main the
    way a code/<id> merge request does: the runner's own branch never gets them."""

    def __init__(self, tmp_path):
        env = git_env()
        self.remote = Repo(tmp_path / "remote.git", env)
        (tmp_path / "remote.git").mkdir()
        self.remote.git("init", "--bare", "-b", "main")
        self.clone = Repo(tmp_path / "clone", env)
        (tmp_path / "clone").mkdir()
        self.clone.git("init", "-b", "main")
        self.clone.git("remote", "add", "origin", str(tmp_path / "remote.git"))
        self.clone.git("commit", "-q", "--allow-empty", "-m", "seed")
        self.clone.git("push", "-q", "origin", "main")
        self.clone.git("checkout", "-q", "-b", "orch")
        self.other = Repo(tmp_path / "other", env)
        subprocess.run(["git", "clone", "-q", str(tmp_path / "remote.git"), str(tmp_path / "other")], env=env,
                       check=True, capture_output=True)
        self.bl = types.SimpleNamespace(sprint_items=lambda s: list(ITEMS))

    def start(self):
        return self.clone.rev("HEAD")

    def land(self, *msgs):
        """Each MSG as an empty commit on origin's main, made by the other clone and pushed."""
        self.other.git("pull", "-q", "origin", "main")
        for m in msgs:
            self.other.git("commit", "-q", "--allow-empty", "-m", m)
        self.other.git("push", "-q", "origin", "HEAD:main")

    def runner(self, *msgs):
        """Each MSG as an empty commit on the runner's own branch, unpushed."""
        for m in msgs:
            self.clone.git("commit", "-q", "--allow-empty", "-m", m)

    def landed(self, start):
        return autopilot.run_landed(self.clone.path, self.bl, "SP-xxxxxxxx", start)

    def old_count(self, start):
        """The count before the fix: the done commits on the runner's HEAD."""
        return len(autopilot.landed_items(self.clone.path, set(ITEMS), start))


@pytest.fixture
def land(tmp_path):
    return Land(tmp_path)


@pytest.mark.parametrize("n", range(1, 8))
@pytest.mark.parametrize("claims", [0, 1, 2, 5])
def test_run_landed_counts_origin_main_for_done_commits_only_there(land, n, claims):
    """(1) n done commits only on origin's main, however many claim commits the runner's branch holds: n; the planted
    failure (5) is the HEAD-based count, which says 0."""
    land.runner(*[claim_msg(ITEMS[i]) for i in range(claims)])
    start = land.start()
    land.runner(*[claim_msg(ITEMS[i]) for i in range(n)])
    land.land(*[done_msg(ITEMS[i]) for i in range(n)])
    assert land.old_count(start) == 0
    assert land.landed(start) == n


@pytest.mark.parametrize("claims", range(0, 6))
def test_run_landed_counts_origin_main_zero_for_a_blocked_run(land, claims):
    """(2) a blocked run: claims and releases on the branch, an unrelated commit landed, no done commit: 0."""
    start = land.start()
    land.runner(*[claim_msg(ITEMS[i]) for i in range(claims)])
    land.land("docs: unrelated change")
    assert land.landed(start) == 0


@pytest.mark.parametrize("before", range(1, 6))
@pytest.mark.parametrize("after", range(0, 4))
def test_run_landed_counts_origin_main_leaves_out_done_commits_before_the_start(land, before, after):
    """(3) done commits on origin's main before the run's start ref are not the run's: only the `after` ones count."""
    land.land(*[done_msg(ITEMS[i]) for i in range(before)])
    land.clone.git("pull", "-q", "--ff-only", "origin", "main")
    start = land.start()
    land.land(*[done_msg(ITEMS[before + i]) for i in range(after)])
    assert land.landed(start) == after


@pytest.mark.parametrize("sprint_n", range(0, 5))
@pytest.mark.parametrize("other_n", range(0, 4))
def test_run_landed_counts_origin_main_only_the_sprints_items(land, sprint_n, other_n):
    """(4) ids that are not items of the sprint are not counted, interleaved with the sprint's."""
    start = land.start()
    msgs = []
    for i in range(max(sprint_n, other_n)):
        if i < other_n:
            msgs.append(done_msg(OTHERS[i]))
        if i < sprint_n:
            msgs.append(done_msg(ITEMS[i]))
    land.land(*msgs)
    assert land.landed(start) == sprint_n


def test_run_landed_counts_origin_main_counts_an_item_once(land):
    start = land.start()
    land.land(done_msg(ITEMS[0]), done_msg(ITEMS[0]), done_msg(ITEMS[1]))
    assert land.landed(start) == 2


def test_run_landed_counts_origin_main_the_runners_own_unpushed_done_commit_is_not_landed(land):
    """The integration main is where an item is landed: a done commit left only on the runner's branch is not counted."""
    start = land.start()
    land.runner(done_msg(ITEMS[0]))
    assert land.landed(start) == 0


def test_run_landed_counts_origin_main_uses_the_local_ref_when_the_fetch_fails(land, tmp_path):
    """No remote to fetch from (the remote is gone), but a local refs/remotes/origin/main that holds the done commit."""
    start = land.start()
    land.land(done_msg(ITEMS[0]), done_msg(ITEMS[1]))
    land.clone.git("fetch", "-q", "origin")
    (tmp_path / "remote.git").rename(tmp_path / "gone.git")
    assert land.clone.run_git("fetch", "origin").returncode != 0
    assert land.landed(start) == 2


def test_run_landed_counts_origin_main_uses_the_local_ref_without_any_remote(tmp_path):
    """The bug's repro shape: no remote at all, a ref set by update-ref."""
    repo = Repo(tmp_path / "r", git_env())
    (tmp_path / "r").mkdir()
    repo.git("init", "-b", "orch")
    repo.git("commit", "-q", "--allow-empty", "-m", "start")
    start = repo.rev("HEAD")
    repo.git("commit", "-q", "--allow-empty", "-m", claim_msg(ITEMS[0]))
    head = repo.rev("HEAD")
    repo.git("commit", "-q", "--allow-empty", "-m", done_msg(ITEMS[0]))
    repo.git("update-ref", "refs/remotes/origin/main", repo.rev("HEAD"))
    repo.git("reset", "-q", "--hard", head)
    bl = types.SimpleNamespace(sprint_items=lambda s: [ITEMS[0]])
    assert autopilot.run_landed(repo.path, bl, "SP-xxxxxxxx", start) == 1


def test_run_landed_counts_origin_main_falls_back_to_head_when_the_ref_is_missing(tmp_path):
    """No remote and no remote-tracking ref: the runner's HEAD, as before; a start ref git does not know: 0."""
    repo = Repo(tmp_path / "r", git_env())
    (tmp_path / "r").mkdir()
    repo.git("init", "-b", "orch")
    repo.git("commit", "-q", "--allow-empty", "-m", "start")
    start = repo.rev("HEAD")
    repo.git("commit", "-q", "--allow-empty", "-m", done_msg(ITEMS[0]))
    assert autopilot.integration_tip(repo.path) == "HEAD"
    bl = types.SimpleNamespace(sprint_items=lambda s: [ITEMS[0]])
    assert autopilot.run_landed(repo.path, bl, "SP-xxxxxxxx", start) == 1
    assert autopilot.run_landed(repo.path, bl, "SP-xxxxxxxx", "0" * 40) == 0


def test_run_landed_counts_origin_main_fetch_is_bounded_and_asks_for_nothing(land, monkeypatch):
    """The fetch has a timeout and no terminal prompt, names one branch, and a timeout leaves the local ref in use."""
    start = land.start()
    land.land(done_msg(ITEMS[0]))
    land.clone.git("fetch", "-q", "origin")
    seen = []
    real = subprocess.run

    def spy(argv, *a, **kw):
        if argv[:2] == ["git", "fetch"]:
            seen.append((argv, kw))
            raise subprocess.TimeoutExpired(argv, kw.get("timeout"))
        return real(argv, *a, **kw)

    monkeypatch.setattr(autopilot.subprocess, "run", spy)
    assert land.landed(start) == 1
    (argv, kw), = seen
    assert argv[-2:] == ["origin", "main"] and kw["timeout"] == autopilot.FETCH_TIMEOUT_S
    assert 0 < autopilot.FETCH_TIMEOUT_S <= 120 and kw["env"]["GIT_TERMINAL_PROMPT"] == "0"


def test_run_landed_counts_origin_main_fetch_changes_only_the_remote_tracking_ref(land):
    land.land(done_msg(ITEMS[0]))
    before = land.clone.git("for-each-ref", "--format=%(refname) %(objectname)", "refs/heads", "refs/tags")
    status = land.clone.git("status", "--porcelain", "-uall")
    autopilot.integration_tip(land.clone.path)
    assert land.clone.git("for-each-ref", "--format=%(refname) %(objectname)", "refs/heads", "refs/tags") == before
    assert land.clone.git("status", "--porcelain", "-uall") == status
    assert land.clone.rev("refs/remotes/origin/main") == land.other.rev("HEAD")


def test_run_landed_counts_origin_main_follows_the_integration_remote_name(land):
    """The remote is the one with the integration role, never the name origin by assumption."""
    land.clone.git("remote", "rename", "origin", "upstream")
    land.clone.git("config", "kb.integrationRemote", "upstream")
    start = land.start()
    land.land(done_msg(ITEMS[0]))
    assert autopilot.integration_tip(land.clone.path) == "refs/remotes/upstream/main"
    assert land.landed(start) == 1


# ---------------------------------------------------------------- one count in runs.jsonl and runner-status

def test_run_landed_counts_origin_main_in_runs_jsonl_and_runner_status(world, monkeypatch, capsys):
    """A run whose item lands through the code lane (the done commit pushed to origin's main by another clone, the
    runner worktree's HEAD left at its claim): runs.jsonl records 1 and runner-status prints `landed 1`."""
    lander = Repo(world.tmp / "lander", git_env())
    (world.tmp / "lander").mkdir()
    subprocess.run(["git", "clone", "-q", str(world.tmp / "origin.git"), str(lander.path)], env=git_env(), check=True,
                   capture_output=True)

    def supervise(argv, wt, keep, err):  # the child lands T1 through a merge request: origin's main moves, the branch does not
        lander.git("commit", "-q", "--allow-empty", "-m", done_msg(T1))
        lander.git("commit", "-q", "--allow-empty", "-m", done_msg(OUTSIDE))
        lander.git("push", "-q", "origin", "HEAD:main")
        return {"compaction": False, "result": {"result": "x\nsprint-runner: landed-limit"}, "exit_code": 0}

    monkeypatch.setattr(autopilot, "supervise", supervise)
    world.start(landed=1)
    assert bl_base.read_runs(world.root, SP) == [(1, "landed-limit")]
    assert autopilot.run_landed(world.wt(), bl_base.Backlog(world.wt()), SP, world.status()["start_ref"]) == 1
    monkeypatch.setattr(autopilot, "ROOT", world.root)
    assert autopilot.main(["runner-status", SP]) == 0
    out = capsys.readouterr().out
    assert f"landed 1: {T1}" in out and OUTSIDE not in out
    assert world.status()["start_ref"][:10] in out
