"""bl_forge.py (kb/_self/backlog.md, Project settings): the one read of a merge request and of a pipeline, its jobs
and a job's log, the merge of the item's own request and the description it carries, through a glab arm and a gh arm
chosen by the `forge` setting and aimed at `forge_project`; land and merge (`bl_land`), the intake's CI detector
(`bl_intake.latest_pipeline`) and the query log's CI check (`ql_deliver.ci_pipeline`) call it with that one project.
The forge is a recorded one: answers of the shapes `glab api` and `gh pr list` / `gh run list` give (the gh ones as
`gh pr list --json` printed them on a merged pull request of a public repository, trimmed), served by a runner that
records each call; nothing here reaches a network or a CLI.

The settings files are throwaway directories under tmp_path."""
import json

import pytest

import bl_base
import bl_forge

GITLAB_URL = "https://git.corp.example.com/group/kb.git"
GITHUB_URL = "https://github.com/group/kb.git"
BRANCH = "code/TK-aaaaaaaa"


class Recorded:
    """A runner of bl_base.run's shape: `git remote get-url` answers URL, a forge call the first answer whose key is
    in the call's words (a string is the stdout, anything else is dumped as JSON); every call is kept."""

    def __init__(self, url, answers=()):
        self.url, self.answers, self.calls = url, list(answers), []

    def __call__(self, argv, cwd=None):
        self.calls.append(list(argv))
        if argv[:3] == ["git", "remote", "get-url"]:
            return 0, self.url + "\n", ""
        line = " ".join(argv)
        for key, answer in self.answers:
            if key in line:
                return 0, answer if isinstance(answer, str) else json.dumps(answer), ""
        return 1, "", "glab: no recorded answer"

    def forge_calls(self):
        return [c for c in self.calls if c[0] in ("glab", "gh")]


@pytest.fixture
def settings(tmp_path, monkeypatch):
    """`settings(**values)`: the process reads a backlog.json of those values at tmp_path; returns tmp_path."""
    monkeypatch.setattr(bl_base, "_LOADED", [])

    def load(**values):
        (tmp_path / "backlog.json").write_text(json.dumps(values), encoding="utf-8")
        bl_base.load_settings(tmp_path, env={})
        return tmp_path
    return load


def mr(iid, state, branch=BRANCH, **more):
    return {"id": 9000 + iid, "iid": iid, "title": f"chore(backlog): work TK-aaaaaaaa #{iid}", "state": state,
            "source_branch": branch, "target_branch": "main", "web_url": f"https://git.corp.example.com/group/kb/-/merge_requests/{iid}",
            "merged_at": None, **more}


def pr(number, state, checks, merge_state="BLOCKED", **more):
    return {"number": number, "title": f"chore(backlog): work TK-aaaaaaaa #{number}", "headRefName": BRANCH,
            "state": state, "url": f"https://github.com/group/kb/pull/{number}", "mergedAt": None,
            "mergeStateStatus": merge_state, "autoMergeRequest": None, "statusCheckRollup": checks, **more}


def run_check(name, status="COMPLETED", conclusion="SUCCESS"):
    return {"__typename": "CheckRun", "name": name, "status": status, "conclusion": conclusion,
            "workflowName": "Tests", "detailsUrl": "https://github.com/group/kb/actions/runs/1/job/2"}


def test_forge_arms_read_a_request_and_a_pipeline_in_one_vocabulary_forge_pipeline(settings):
    # glab arm: the project is forge_project, the open request is the one read, whatever else its branch has
    root = settings(forge_project="other/proj")
    listed = [mr(3, "closed"), mr(4, "merged", merged_at="2026-10-09T14:47:45Z"), mr(5, "opened")]
    single = mr(5, "opened", detailed_merge_status="mergeable", merge_when_pipeline_succeeds=True, description="Body",
                head_pipeline={"id": 77, "status": "skipped", "web_url": "https://git.corp.example.com/p/77"})
    run = Recorded(GITLAB_URL, [("merge_requests/5", single), ("merge_requests?source_branch=code%2FTK", listed),
                                ("merge_requests?search=chore", [mr(4, "merged", merged_at="2026-10-09T14:47:45Z")]),
                                ("pipelines?ref=main", [{"id": 78, "sha": "0" * 40, "status": "failed", "ref": "main",
                                                         "web_url": "https://git.corp.example.com/p/78"}])])
    req = bl_forge.read_request(root, branch=BRANCH, run=run)
    assert (req.state, req.iid, req.pipeline, req.merge_status, req.mergeable, req.auto_merge, req.description) == (
        "opened", 5, "skipped", "mergeable", True, True, "Body")
    assert all("projects/other%2Fproj/" in c[-1] for c in run.forge_calls())
    by_title = bl_forge.read_request(root, title_prefix="chore(backlog): work", run=run)
    assert (by_title.state, by_title.merged_at) == ("merged", "2026-10-09T14:47:45Z")
    assert bl_forge.read_pipeline(root, "main", run=run)[:3] == (78, "0" * 40, "failed")
    assert bl_forge.read_request(root, branch="code/TK-bbbbbbbb", run=Recorded(GITLAB_URL, [("merge_requests", [])])) is None
    with pytest.raises(bl_forge.ForgeError, match="glab api failed"):
        bl_forge.read_request(root, branch=BRANCH, run=Recorded(GITLAB_URL))  # not signed in: no recorded answer

    # gh arm: a failed check in the rollup is a failed pipeline, a blocked pull request is not mergeable
    root = settings(forge="github")
    listed = [pr(4, "MERGED", [run_check("lint", conclusion="SKIPPED")], merge_state="UNKNOWN", mergedAt="2026-10-09T14:47:45Z"),
              pr(5, "OPEN", [run_check("lint"), run_check("build", conclusion="FAILURE")], body="Body")]
    runs = [{"databaseId": 31, "headSha": "1" * 40, "status": "in_progress", "conclusion": "", "url": "https://github.com/group/kb/actions/runs/31"}]
    run = Recorded(GITHUB_URL, [("gh pr list", listed), ("gh run list", runs)])
    req = bl_forge.read_request(root, branch=BRANCH, run=run)
    assert (req.state, req.iid, req.pipeline, req.merge_status, req.mergeable, req.auto_merge, req.description) == (
        "opened", 5, "failed", "blocked", False, False, "Body")
    merged = bl_forge.read_request(root, title_prefix="chore(backlog): work", run=Recorded(GITHUB_URL, [("gh pr list", listed[:1])]))
    assert (merged.state, merged.pipeline, merged.merged_at) == ("merged", "skipped", "2026-10-09T14:47:45Z")
    assert bl_forge.read_pipeline(root, "main", run=run)[:3] == (31, "1" * 40, "running")
    assert all(c[0] == "gh" and c[c.index("-R") + 1] == "github.com/group/kb" for c in run.forge_calls())
    with pytest.raises(bl_forge.ForgeError, match="gh pr list failed"):
        bl_forge.read_request(root, branch=BRANCH, run=Recorded(GITHUB_URL))

    # the intake's CI detector and the delivery's CI check read pipelines, jobs and a log through the arm, with the
    # one forge_project (GitLab: a retried job counts by its newest attempt; no `auth status` call, no job list for
    # a pipeline whose status says failed)
    import bl_intake
    import ql_deliver
    fail = {"name": "lint", "status": "failed", "failure_reason": "script_failure", "started_at": "2026-10-09"}
    pipes = [{"id": 78, "sha": "0" * 40, "status": "success", "web_url": "https://git.corp.example.com/p/78"}]
    root = settings(forge_project="other/proj")
    run = Recorded(GITLAB_URL, [("jobs/5/trace", "FAILED a.py::t - boom\n"),
                                ("pipelines/78/jobs", [dict(fail, id=6, name="kb-tests", status="success"), dict(fail, id=5),
                                                     dict(fail, id=4, name="kb-tests")]),
                                ("pipelines?ref=main", pipes), ("pipelines?sha=", pipes)])
    got, note = bl_intake.latest_pipeline(root, None, run)
    assert (got["id"], got["red"], got["jobs"], got["failure"], got["calls"], note) == (
        78, True, ["lint"], "a.py::t", 1, "glab on git.corp.example.com")
    assert all("projects/other%2Fproj/" in " ".join(c) for c in run.forge_calls())
    verdict, detail, pipe = ql_deliver.ci_pipeline(GITLAB_URL, "0" * 40, run)
    assert (verdict, pipe["id"]) == ("red", 78) and "script failed in lint" in detail
    assert ql_deliver.pipeline_failure(GITLAB_URL, pipe, run)[0] == "a.py::t" and pipe["job"] == "lint"
    assert not any("auth" in c for c in run.forge_calls())
    assert bl_intake.latest_pipeline(root, "kb-tests", run)[0]["red"] is False  # the newest attempt succeeded
    assert ql_deliver.ci_pipeline(GITLAB_URL, "0" * 40, Recorded(GITLAB_URL))[0] == "skip"  # not signed in

    # GitHub: a failed run's jobs are GitLab-shaped, its log is read through gh api, and a project with no setting
    # reads the remote's url (github.com is GitHub, its project the url's)
    root = settings()
    jobs = {"jobs": [{"databaseId": 9, "name": "build", "status": "completed", "conclusion": "failure",
                      "startedAt": "2026-10-09T14:00:00Z"}]}
    runs = [{"databaseId": 31, "headSha": "1" * 40, "status": "completed", "conclusion": "failure",
             "url": "https://github.com/group/kb/actions/runs/31"}]
    run = Recorded(GITHUB_URL, [("actions/jobs/9/logs", "Traceback (most recent call last)\n"),
                                ("gh run view", jobs), ("gh run list", runs)])
    got, note = bl_intake.latest_pipeline(root, None, run)
    assert (got["id"], got["red"], got["jobs"], got["first"], got["calls"], note) == (
        31, True, ["build"], "build", 1, "gh on github.com")
    assert all(c[c.index("-R") + 1] == "github.com/group/kb" for c in run.forge_calls() if "-R" in c)
    assert ql_deliver.ci_pipeline(GITHUB_URL, "1" * 40, run)[:2] == ("red", "gh on github.com: failed")
    assert bl_intake.latest_pipeline(root, "build", run)[0]["red"] is True


def test_forge_arms_merge_on_the_glab_arm_only_forge_land_forge_one_project_forge_stalled(settings, monkeypatch,
                                                                                         capsys):
    root = settings(forge_project="other/proj")
    single = mr(5, "opened", detailed_merge_status="mergeable", head_pipeline={"id": 77, "status": "success"})
    run = Recorded(GITLAB_URL, [("merge_requests/5", single), ("merge_requests?source_branch", [mr(5, "opened")]),
                                ("glab mr merge", "Merged!")])
    outcome, req, _ = bl_forge.merge_own(root, BRANCH, run=run)
    assert (outcome, req.iid) == ("merged", 5)
    assert run.forge_calls()[-1] == ["glab", "mr", "merge", "5", "--auto-merge=false", "--yes", "-R",
                                     "https://git.corp.example.com/other/proj"]
    done = Recorded(GITLAB_URL, [("merge_requests?source_branch", [mr(5, "merged", merged_at="2026-10-09T14:47:45Z")])])
    assert bl_forge.merge_own(root, BRANCH, run=done)[0] == "already"
    assert not any(c[:3] == ["glab", "mr", "merge"] for c in done.forge_calls())
    other = Recorded(GITLAB_URL)
    with pytest.raises(bl_base.Refused, match="no item's own"):
        bl_forge.merge_own(root, "work/TK-aaaaaaaa", run=other)
    assert other.forge_calls() == []

    # the gh arm reads state and refuses to merge, before any forge call
    root = settings(forge="github")
    run = Recorded(GITHUB_URL, [("gh pr list", [pr(5, "OPEN", [run_check("lint")], merge_state="CLEAN")])])
    with pytest.raises(bl_base.Refused, match="only reads state"):
        bl_forge.merge_own(root, BRANCH, run=run)
    assert run.forge_calls() == []
    assert bl_forge.read_request(root, branch=BRANCH, run=run).mergeable is True

    # a github.com remote under the default forge setting is refused, and the setting takes two values only
    root = settings()
    with pytest.raises(bl_base.Refused, match='"forge": "github"'):
        bl_forge.read_pipeline(root, "main", run=Recorded(GITHUB_URL))
    problems = bl_base.read_settings(settings(forge="bitbucket"), env={})[3]
    assert len(problems) == 1 and "'forge'" in problems[0]

    # land and merge call it, with the one forge_project and one read of the request for each pass of land
    import bl_land
    from types import SimpleNamespace
    root = settings(forge_project="other/proj")
    single = mr(5, "opened", detailed_merge_status="mergeable", merge_when_pipeline_succeeds=True, description="Body",
                head_pipeline={"id": 77, "status": "skipped"})
    run = Recorded(GITLAB_URL, [("--method PUT", {}), ("merge_requests/5", single),
                                ("merge_requests?source_branch", [mr(5, "opened")]), ("glab mr merge", "Merged!")])
    monkeypatch.setattr(bl_land, "run", run)
    monkeypatch.setattr(bl_land, "need", lambda bl, iid: iid)
    bl = SimpleNamespace(root=root, items={"TK-aaaaaaaa": {"external": {"jira": ["PL-1"]}}}, descendants=lambda i: [])
    request = bl_land.read_code_request(root, BRANCH)  # the pass's one read, shared by both steps
    bl_land.describe_merge_request(bl, "TK-aaaaaaaa", request)
    line = bl_land.stuck_merge_request(request, BRANCH)
    assert "!5" in line and "skipped" in line and "backlog.py merge TK-aaaaaaaa" in line
    put = [c for c in run.forge_calls() if "PUT" in c]
    assert len(put) == 1 and put[0][-1].startswith("description=Body\n\n") and "jira PL-1" in put[0][-1]
    reads = [c for c in run.forge_calls() if "PUT" not in c]
    assert len(reads) == 2 and all("projects/other%2Fproj/" in " ".join(c) for c in run.forge_calls())
    run.calls.clear()
    assert bl_land.cmd_merge(bl, SimpleNamespace(id="TK-aaaaaaaa")) == 0
    assert all("other%2Fproj" in " ".join(c) or c[-1].endswith("/other/proj") for c in run.forge_calls())
    assert run.forge_calls()[-1][:4] == ["glab", "mr", "merge", "5"]
    assert "merged" in capsys.readouterr().out

    # a github remote's request is read, its description is refused with a line, and its merge exits 2 from the arm
    root = settings(forge="github")
    run = Recorded(GITHUB_URL, [("gh pr list", [pr(5, "OPEN", [run_check("lint")], merge_state="CLEAN", body="Body")])])
    monkeypatch.setattr(bl_land, "run", run)
    bl = SimpleNamespace(root=root, items=bl.items, descendants=lambda i: [])
    bl_land.describe_merge_request(bl, "TK-aaaaaaaa", bl_land.read_code_request(root, BRANCH))
    assert "could not set the description" in capsys.readouterr().out and len(run.forge_calls()) == 1
    with pytest.raises(bl_base.Refused, match="only reads state"):
        bl_land.cmd_merge(bl, SimpleNamespace(id="TK-aaaaaaaa"))

    # land --wait-merge sleeps WAIT_POLL between reads of the integration main, no loop of a session's own
    seen, slept = iter([False, False, True]), []
    monkeypatch.setattr(bl_land, "merged_on_main", lambda root, remote, shas: next(seen))
    assert bl_land.wait_merge(root, "origin", ["a" * 40], 600, sleep=slept.append) == 3
    assert slept == [bl_land.WAIT_POLL, bl_land.WAIT_POLL]

    # stalled reads each claimed item's code/<id> request once through the arm, with the one forge_project, and names
    # mr-dead for a pipeline that failed, was canceled, skipped or is manual, or a merge status waiting never clears;
    # a status not listed (a conflict still computing too), a merged request and no request are no signal; a read
    # that fails is unknown:forge, never a signal, and ends the reads; selfcheck's claims check lists mr-dead
    import bl_selfcheck
    import bl_stall
    monkeypatch.setattr(bl_stall, "ops_rows", lambda root: [])
    monkeypatch.setattr(bl_stall, "lock_state", lambda now: ("none", None))
    monkeypatch.setattr(bl_stall, "claim_signals", lambda root, iid, now: ([], []))
    cases = {"TK-aaaaaaaa": ("opened", "mergeable", "skipped"), "TK-bbbbbbbb": ("opened", "ci_still_running", "running"),
             "TK-cccccccc": ("opened", "discussions_not_resolved", "success"), "TK-dddddddd": ("merged", "not_open", None),
             "TK-eeeeeeee": ("opened", "conflict", "success"), "TK-ffffffff": ("opened", "mergeable", "manual")}
    answers = []
    for n, (iid, (state, merge_status, pipeline)) in enumerate(cases.items(), start=31):
        branch = f"code/{iid}"
        listed = mr(n, state, branch=branch, detailed_merge_status=merge_status)
        answers += [(f"merge_requests/{n}", mr(n, state, branch=branch, detailed_merge_status=merge_status,
                                               head_pipeline={"id": n, "status": pipeline}))]
        answers += [(f"merge_requests?source_branch=code%2F{iid}", [listed])]
    answers += [("merge_requests?source_branch=code%2FTK-gggggggg", [])]
    ids = [*cases, "TK-gggggggg"]
    root = settings(forge_project="other/proj")
    bl = SimpleNamespace(root=root, items={i: {"status": "doing", "claimed_by": "orch", "kind": "task"} for i in ids},
                         order_key=lambda i: i, label=lambda i: i)
    run = Recorded(GITLAB_URL, answers)
    report = bl_stall.collect(bl, now=0, run=run)
    assert {r["id"]: (r["signals"], r["unknown"]) for r in report["items"]} == {
        "TK-aaaaaaaa": (["mr-dead"], []), "TK-cccccccc": (["mr-dead"], []), "TK-ffffffff": (["mr-dead"], [])}
    reads = [c for c in run.forge_calls() if "merge_requests?" in c[-1]]
    assert report["forge_reads"] == len(ids) == len(reads)
    assert all("projects/other%2Fproj/" in c[-1] for c in run.forge_calls())
    claims = bl_selfcheck.check_claims(report)
    assert claims["state"] == "fail" and "TK-aaaaaaaa mr-dead" in claims["detail"]
    down = Recorded(GITLAB_URL)  # no recorded answer: a CLI not signed in
    report = bl_stall.collect(bl, now=0, run=down)
    assert [(r["signals"], r["unknown"]) for r in report["items"]] == [([], ["unknown:forge"])] * len(ids)
    assert report["forge_reads"] == 0 and len(down.forge_calls()) == 1
    assert bl_selfcheck.check_claims(report)["state"] == "ok"
    root = settings(forge="github")
    run = Recorded(GITHUB_URL, [("gh pr list", [pr(5, "OPEN", [run_check("build", conclusion="FAILURE")])])])
    bl = SimpleNamespace(root=root, items={"TK-aaaaaaaa": bl.items["TK-aaaaaaaa"]}, order_key=lambda i: i, label=lambda i: i)
    assert bl_stall.collect(bl, now=0, run=run)["items"][0]["signals"] == ["mr-dead"]
