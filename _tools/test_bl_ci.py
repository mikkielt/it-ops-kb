"""backlog.py red-pipeline and its CI readers (bl_ci.py): a planted red and a green pipeline on origin's main, glab and
gh replaced (no network); the failure fingerprint over planted and real forge logs; one bug per failure. The patches
name the module where the code looks the name up, `bl_ci` (its `run` and `run_check`).
"""
import json
import re
import subprocess
from pathlib import Path

import pytest

import backlog
import bl_ci
import bl_testkit
import ql_deliver
from bl_testkit import TOOLS, edit, sh
from test_ql_deliver import job_of, job_states, state_id  # the job-state table's rows

bl_testkit.bind(backlog)

repo, sprint, no_git_location, gate_jobs = bl_testkit.repo, bl_testkit.sprint, bl_testkit.no_git_location, bl_testkit.gate_jobs


# ---- red-pipeline: a planted red and a green pipeline on origin's main, glab and gh replaced (no network)

def forge(monkeypatch, repo, pipelines, jobs=(), signed_in=True, logs=None):
    """origin is a GitLab project; `glab` answers the given pipelines (newest first), their jobs (one list for every
    pipeline, or a dict pipeline id -> list) and job logs (`logs`: job id -> trace text). The lists and the dicts are
    read on every call: a test changes them in place."""
    sh(repo, "git", "remote", "add", "origin", "https://gitlab.example.com/team/kb.git")
    sh(repo, "git", "update-ref", "refs/remotes/origin/main", "HEAD")
    real = bl_ci.run

    def fake(argv, cwd=None):
        if argv[:2] == ["git", "fetch"]:
            return 0, "", ""
        if argv[0] in ("glab", "gh"):
            if argv[1] == "auth":
                return (0, "", "") if signed_in else (1, "", "not logged in")
            if argv[-1].endswith("/trace"):
                jid = int(argv[-1].split("/")[-2])
                return (0, logs[jid], "") if logs and jid in logs else (1, "", "404 Not Found")
            if "/jobs?" in argv[-1] and jobs is None:
                return 1, "", "500 Internal Server Error"
            if "/jobs?" in argv[-1] and isinstance(jobs, dict):
                return 0, json.dumps(jobs.get(int(argv[-1].split("/pipelines/")[1].split("/")[0]), [])), ""
            return 0, json.dumps(jobs if "/jobs?" in argv[-1] else pipelines), ""
        return real(argv, cwd=cwd)

    monkeypatch.setattr(bl_ci, "run", fake)
    monkeypatch.setattr(bl_ci, "run_check", lambda root, c: (False, 1, ""))  # the repro fails: main is red


def head(repo):
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()


def bugs(repo):
    return [it for it in backlog.Backlog(repo).items.values() if it["kind"] == "bug"]


def red_pipeline(repo, *a):
    return backlog.main(["--root", str(repo), "red-pipeline", *a])


def test_red_pipeline_files_one_s2_bug_per_pipeline(repo, monkeypatch, capsys):
    sha = head(repo)
    forge(monkeypatch, repo, [{"id": 902, "sha": sha, "status": "running"},
                              {"id": 901, "sha": sha, "status": "failed", "web_url": "https://x/901"},
                              {"id": 900, "sha": sha, "status": "success"}],
          jobs=[{"name": "kb-tests-windows", "status": "failed", "failure_reason": "script_failure"}])
    assert red_pipeline(repo) == 0
    (bug,) = bugs(repo)
    assert bug["severity"] == "S2" and bug["status"] == "draft" and "pipeline 901" in bug["title"]
    assert bug["repro"]["run"] == bl_ci.STATUS_REPRO + ["--job", "kb-tests-windows"]
    assert backlog.validate(backlog.Backlog(repo)) == []
    capsys.readouterr()
    assert red_pipeline(repo) == 0  # the same pipeline again: named by the bug, nothing filed
    assert "already filed" in capsys.readouterr().out
    assert len(bugs(repo)) == 1


def test_red_pipeline_gate_job_is_s1_and_joins_the_active_sprint(sprint, monkeypatch):
    repo = sprint["repo"]
    forge(monkeypatch, repo, [{"id": 77, "sha": head(repo), "status": "failed"}],
          jobs=[{"name": "kb-tests", "status": "failed"}])
    assert red_pipeline(repo) == 0
    (bug,) = [x for x in bugs(repo) if "pipeline 77" in x["title"]]
    assert bug["severity"] == "S1" and bug["sprint"] == sprint["sp"] and bug["status"] == "todo"


GATE_PASSED = [{"id": 3, "name": "kb-trailers", "status": "success"}, {"id": 2, "name": "kb-tests", "status": "success"}]


def test_red_pipeline_green_files_nothing(repo, monkeypatch, capsys):
    forge(monkeypatch, repo, [{"id": 5, "sha": head(repo), "status": "success"},
                              {"id": 4, "sha": head(repo), "status": "failed"}], jobs=GATE_PASSED)
    assert red_pipeline(repo) == 0
    assert bugs(repo) == [] and "green" in capsys.readouterr().out
    assert red_pipeline(repo, "--status") == 0


def test_red_pipeline_unrun_gate_is_not_green(repo, monkeypatch, capsys):
    """The job list of a main pipeline whose status says success while no job ran (every job manual with
    allow_failure, the CI minutes quota spent): unverified, never green; each planted gate state keeps it so."""
    quota = {"status": "failed", "failure_reason": "ci_quota_exceeded", "allow_failure": True}
    pipelines = [{"id": 61, "sha": head(repo), "status": "success"}]
    jobs = [{"id": 15, "name": "kb-tests-windows", "status": "manual", "allow_failure": True},
            {"id": 14, "name": "kb-trailers", **quota}, {"id": 13, "name": "tool-stress", **quota},
            {"id": 12, "name": "kb-tests-floor", **quota}, {"id": 11, "name": "kb-tests", **quota}]
    forge(monkeypatch, repo, pipelines, jobs=jobs)
    capsys.readouterr()
    assert red_pipeline(repo, "--status") == 1
    out = capsys.readouterr().out
    assert "pipeline 61 of main is unverified" in out, out
    assert "kb-tests failed (ci_quota_exceeded), kb-trailers failed (ci_quota_exceeded)" in out, out
    assert "kb-tests-floor" not in out and "tool-stress" not in out and "kb-tests-windows" not in out, out
    assert red_pipeline(repo) == 0 and bugs(repo) == []  # unverified is not red: nothing filed
    assert "unverified" in capsys.readouterr().out
    # planted: every other way a gate job does not pass, on a pipeline whose status is no failure
    for status, gate, said in (
            ("manual", [{"name": "kb-tests", "status": "manual"}, {"name": "kb-trailers", "status": "manual"}],
             "kb-tests manual, kb-trailers manual"),
            ("success", [{"name": "kb-tests", "status": "skipped"}, {"name": "kb-trailers", "status": "success"}],
             "kb-tests skipped"),
            ("canceled", [{"name": "kb-tests", "status": "canceled"}, {"name": "kb-trailers", "status": "success"}],
             "kb-tests canceled"),
            ("success", [{"name": "kb-tests", "status": "success"}], "kb-trailers not in the pipeline"),
            ("success", [{"name": "kb-tests", "status": "running"}, {"name": "kb-trailers", "status": "success"}],
             "kb-tests running")):
        pipelines[0]["status"] = status
        jobs[:] = [{"id": i, **j} for i, j in enumerate(gate)]
        assert red_pipeline(repo, "--status") == 1, (status, gate)
        out = capsys.readouterr().out
        assert "is unverified" in out and said in out, out
    assert red_pipeline(repo) == 0 and bugs(repo) == []
    # the gate ran and passed: the other jobs, manual or never started, leave main green
    pipelines[0]["status"] = "success"
    jobs[:] = [{"id": 15, "name": "kb-tests-windows", "status": "manual"}, {"id": 13, "name": "tool-stress", **quota},
               {"id": 14, "name": "kb-trailers", "status": "success"}, {"id": 11, "name": "kb-tests", "status": "success"}]
    capsys.readouterr()
    assert red_pipeline(repo, "--status") == 0
    assert "pipeline 61 of main is green" in capsys.readouterr().out
    # planted: a job list glab cannot read is no proof either
    monkeypatch.undo()
    sh(repo, "git", "remote", "remove", "origin")
    forge(monkeypatch, repo, pipelines, jobs=None)
    assert red_pipeline(repo, "--status") == 1
    assert "the pipeline's jobs could not be read" in capsys.readouterr().out


def test_red_pipeline_failed_script_under_allow_failure_is_red(sprint, monkeypatch):
    """A job whose script ran and failed under allow_failure leaves the pipeline's status success: its job list makes
    it red, S1 when it is kb-tests, and the fingerprint names that job, not the one that never started."""
    repo = sprint["repo"]
    forge(monkeypatch, repo, [{"id": 62, "sha": head(repo), "status": "success"}],
          jobs=[{"id": 14, "name": "kb-trailers", "status": "success"},
                {"id": 12, "name": "kb-tests-floor", "status": "failed", "failure_reason": "ci_quota_exceeded"},
                {"id": 11, "name": "kb-tests", "status": "failed", "failure_reason": "script_failure",
                 "allow_failure": True}],
          logs={11: "FAILED _tools/test_x.py::test_a - assert 1 == 2\n"})
    assert red_pipeline(repo, "--status") == 1
    assert red_pipeline(repo) == 0
    (bug,) = [x for x in bugs(repo) if "pipeline 62" in x["title"]]
    assert bug["severity"] == "S1" and bug["title"].endswith(": kb-tests"), bug["title"]
    assert f"fingerprint {bl_ci.failure_fingerprint('kb-tests', '_tools/test_x.py::test_a')}" in bug["links"]


def test_red_pipeline_reads_a_pipeline_where_a_job_ran(sprint, monkeypatch, capsys):
    """Every job is manual, so most pipelines of main are ones nobody started. Planted: a red started pipeline, then
    newer ones where no job ran; the red one is read, its bug's repro names its failed job and fails until that job
    passes again, not when another job passes or a push starts nothing; a timed-out or stuck job is red too."""
    repo = sprint["repo"]
    monkeypatch.setattr(ql_deliver, "GATE_JOBS", ())  # the default: no job is a gate
    manual = [{"id": 30, "name": "kb-tests", "status": "manual"}, {"id": 31, "name": "kb-trailers", "status": "manual"},
              {"id": 32, "name": "kb-lint", "status": "failed", "failure_reason": "ci_quota_exceeded"}]
    pipelines = [{"id": 73, "sha": head(repo), "status": "manual"}, {"id": 72, "sha": head(repo), "status": "skipped"},
                 {"id": 71, "sha": head(repo), "status": "success"}]
    jobs = {73: manual, 72: [],
            71: [{"id": 11, "name": "kb-tests", "status": "failed", "failure_reason": "script_failure",
                  "started_at": "2026-09-30T08:00:00Z"}, {"id": 12, "name": "kb-trailers", "status": "manual"}]}
    forge(monkeypatch, repo, pipelines, jobs=jobs, logs={11: "FAILED _tools/test_x.py::test_a - assert 1 == 2\n"})
    capsys.readouterr()
    assert red_pipeline(repo, "--status") == 1
    assert "pipeline 71 of main is red" in capsys.readouterr().out
    assert red_pipeline(repo) == 0
    (bug,) = [x for x in bugs(repo) if "pipeline 71" in x["title"]]
    assert bug["severity"] == "S1" and bug["repro"]["run"] == bl_ci.STATUS_REPRO + ["--job", "kb-tests"], bug
    # a newer pipeline where only another job ran and passed: main reads green, the bug's job is still red
    pipelines.insert(0, {"id": 74, "sha": head(repo), "status": "manual"})
    jobs[74] = [{"id": 40, "name": "kb-trailers", "status": "success"}, {"id": 41, "name": "kb-tests", "status": "manual"}]
    assert red_pipeline(repo, "--status") == 0
    assert red_pipeline(repo, "--status", "--job", "kb-tests") == 1
    assert "the newest kb-tests pipeline 71 of main is red" in capsys.readouterr().out
    # kb-tests runs again and passes: the bug's repro passes
    pipelines.insert(0, {"id": 75, "sha": head(repo), "status": "manual"})
    jobs[75] = [{"id": 50, "name": "kb-tests", "status": "success"}]
    assert red_pipeline(repo, "--status", "--job", "kb-tests") == 0
    # a job that ran past its timeout, or got stuck, is red
    for reason in ("job_execution_timeout", "stuck_or_timeout_failure"):
        pipelines.insert(0, {"id": 76, "sha": head(repo), "status": "success"})
        jobs[76] = [{"id": 60, "name": "kb-tests-windows", "status": "failed", "failure_reason": reason}]
        assert red_pipeline(repo, "--status") == 1, reason
        assert red_pipeline(repo, "--status", "--job", "kb-tests-windows") == 1, reason
        pipelines.pop(0)
    # no job ran in any pipeline: the newest finished one is read, and is green
    pipelines[:] = [{"id": 73, "sha": head(repo), "status": "manual"}, {"id": 72, "sha": head(repo), "status": "skipped"}]
    capsys.readouterr()
    assert red_pipeline(repo, "--status") == 0
    assert "no job ran in the last" in capsys.readouterr().out
    assert red_pipeline(repo, "--status", "--job", "kb-tests") == 1  # the job never ran: not checked


def test_red_pipeline_status_is_the_repro_of_a_red_main(repo, monkeypatch):
    forge(monkeypatch, repo, [{"id": 5, "sha": head(repo), "status": "failed"}])
    assert red_pipeline(repo, "--status") == 1


def test_red_pipeline_automatic_revert_covers_it(repo, monkeypatch):
    sh(repo, "git", "commit", "-q", "--allow-empty", "-m", "query log", "-m", "KB-Auto: apply")
    auto = head(repo)
    sh(repo, "git", "commit", "-q", "--allow-empty", "-m", "revert: query log commit",
       "-m", f"This reverts commit {auto}.", "-m", "KB-Auto: revert")
    forge(monkeypatch, repo, [{"id": 8, "sha": auto, "status": "failed"}])
    assert red_pipeline(repo) == 0
    assert bugs(repo) == []


def test_red_pipeline_revert_of_another_commit_does_not_cover_it(repo, monkeypatch):
    sh(repo, "git", "commit", "-q", "--allow-empty", "-m", "query log", "-m", "KB-Auto: apply")
    auto = head(repo)
    sh(repo, "git", "commit", "-q", "--allow-empty", "-m", "a human commit")
    human = head(repo)
    sh(repo, "git", "commit", "-q", "--allow-empty", "-m", "revert: query log commit",
       "-m", f"This reverts commit {auto}.", "-m", "KB-Auto: revert")
    forge(monkeypatch, repo, [{"id": 9, "sha": human, "status": "failed"}])
    assert red_pipeline(repo) == 0
    assert "pipeline 9" in bugs(repo)[0]["title"]


def test_red_pipeline_notes_when_not_signed_in(repo, monkeypatch, capsys):
    forge(monkeypatch, repo, [{"id": 5, "sha": head(repo), "status": "failed"}], signed_in=False)
    assert red_pipeline(repo) == 0
    assert "not signed in" in capsys.readouterr().out and bugs(repo) == []
    assert red_pipeline(repo, "--status") == 1


# ---- red-pipeline over the job-state table (test_ql_deliver.py's rows: every status, started or not, each reason)

# allow_failure: a failed job leaves its pipeline's status success; created, pending and running are unfinished
PIPELINE_OF = {"failed": "success"}


def job_repro_rows():
    """`--status --job kb-tests` passes only when the newest pipeline in which kb-tests reached a verdict passed it:
    a canceled, manual or skipped job someone started is no verdict (BG-sim2fdaa), so the older red run decides."""
    return [pytest.param(st, id=state_id(st)) for st in job_states()]


@pytest.mark.parametrize("st", job_repro_rows())
def test_job_state_table_red_pipeline_job_repro(repo, monkeypatch, st):
    """Pipeline 81 holds kb-tests in the row's state, the older 80 a kb-tests whose script failed."""
    sha = head(repo)
    forge(monkeypatch, repo, [{"id": 81, "sha": sha, "status": PIPELINE_OF.get(st[0], st[0])},
                              {"id": 80, "sha": sha, "status": "success"}],
          jobs={81: [job_of(*st)], 80: [job_of("failed", True, "script_failure")]})
    assert red_pipeline(repo, "--status", "--job", "kb-tests") == (0 if st[0] == "success" else 1)


@pytest.mark.parametrize("reason", ["ci_quota_exceeded", "runner_system_failure"])
def test_red_pipeline_files_a_red_status_whose_job_never_ran(repo, monkeypatch, reason):
    """BG-vsqfchgz: main's pipeline 85 failed by its status, its only failed job kb-tests failed without running; in
    the older 84 kb-tests passed. The bug is filed with plain `--status` as its repro (a `--job kb-tests` one would
    read 84 and pass), and that repro, run against the same forge, fails."""
    sha = head(repo)
    forge(monkeypatch, repo, [{"id": 85, "sha": sha, "status": "failed"}, {"id": 84, "sha": sha, "status": "success"}],
          jobs={85: [{"id": 41, "name": "kb-tests", "status": "failed", "failure_reason": reason}],
                84: [{"id": 40, "name": "kb-tests", "status": "success", "started_at": "2026-09-30T08:00:00Z"}]})
    monkeypatch.setattr(bl_ci, "run_check", lambda root, c: (
        lambda code: (code == 0, code, ""))(backlog.main(["--root", str(root), *c["run"][2:]])))
    assert red_pipeline(repo) == 0
    filed = [x for x in bugs(repo) if "pipeline 85" in x["title"]]
    assert filed and filed[0]["repro"]["run"] == bl_ci.STATUS_REPRO, filed
    assert red_pipeline(repo, "--status") == 1
    assert red_pipeline(repo, "--status", "--job", "kb-tests") == 0  # what a --job repro would have read


def test_red_pipeline_job_skips_a_canceled_run(repo, monkeypatch):
    """BG-sim2fdaa: someone starts kb-tests on main and cancels it; the newer pipeline holds no verdict on kb-tests,
    so a red-main bug's repro (`--status --job kb-tests`) still reads the older red run and fails."""
    sha = head(repo)
    pipelines = [{"id": 83, "sha": sha, "status": "canceled"}, {"id": 82, "sha": sha, "status": "success"}]
    jobs = {83: [{"id": 31, "name": "kb-tests", "status": "canceled", "started_at": "2026-09-30T09:00:00Z"}],
            82: [{"id": 30, "name": "kb-tests", "status": "failed", "failure_reason": "script_failure",
                  "started_at": "2026-09-30T08:00:00Z"}]}
    forge(monkeypatch, repo, pipelines, jobs=jobs)
    assert red_pipeline(repo, "--status", "--job", "kb-tests") == 1
    assert red_pipeline(repo, "--status") == 1  # without --job the canceled run hides nothing either
    jobs[83][0]["status"] = "manual"  # started, then left waiting: no verdict either
    pipelines[0]["status"] = "manual"
    assert red_pipeline(repo, "--status", "--job", "kb-tests") == 1
    jobs[83][0]["status"] = "success"  # a run that passed is the verdict
    pipelines[0]["status"] = "success"
    assert red_pipeline(repo, "--status", "--job", "kb-tests") == 0


def file_rows():
    """A main pipeline that failed is red whatever its job did, so red-pipeline files a bug: its repro must fail now.
    A failed job that never ran is not named by `--job`, which would read an older pass (BG-vsqfchgz)."""
    return [pytest.param(st, id=state_id(st)) for st in job_states()]


@pytest.mark.parametrize("st", file_rows())
def test_job_state_table_red_pipeline_files_a_failed_main(repo, monkeypatch, st):
    """Pipeline 91 failed with kb-tests in the row's state; in the older 90 kb-tests passed. The bug's repro runs
    against the same forge (not canned), as red-pipeline's second read does."""
    sha = head(repo)
    forge(monkeypatch, repo, [{"id": 91, "sha": sha, "status": "failed"}, {"id": 90, "sha": sha, "status": "success"}],
          jobs={91: [job_of(*st)], 90: [job_of("success", True, None)]})
    monkeypatch.setattr(bl_ci, "run_check", lambda root, c: (
        lambda code: (code == 0, code, ""))(backlog.main(["--root", str(root), *c["run"][2:]])))
    assert red_pipeline(repo) == 0
    assert [x for x in bugs(repo) if "pipeline 91" in x["title"]], "nothing filed for a failed main"


# ---- failure fingerprint: planted logs of red pipelines, the same failure twice and a different one

def test_fingerprint_names_the_first_failing_test_or_normalised_error_line():
    log = ("2026-09-01T10:00:00.1234567Z \x1b[31msection_start:1700000000:tests\x1b[0m\n"
           "_tools/test_a.py::test_one PASSED\n"
           "_tools/test_b.py::test_two FAILED\n"
           "FAILED _tools/test_c.py::test_three - assert 1 == 2\n")
    assert bl_ci.first_failure(log) == "_tools/test_b.py::test_two"
    a = bl_ci.first_failure("2026-09-01T10:00:00Z check: error in kb/x.md:12 (sha 0123abcd9)\nERROR: Job failed\n")
    b_ = bl_ci.first_failure("2026-09-02T11:30:01Z check: error in kb/x.md:57 (sha fedcba987)\nERROR: Job failed\n")
    assert a == b_ == "check: error in kb/x.md:<n> (sha <hex>)"
    assert bl_ci.first_failure("all good\n") == "" and bl_ci.first_failure(None) == ""
    fp = bl_ci.failure_fingerprint("kb-tests", a)
    assert len(fp) == 12 and int(fp, 16) >= 0
    assert fp == bl_ci.failure_fingerprint("kb-tests", b_)
    assert fp != bl_ci.failure_fingerprint("kb-tests-windows", a)  # another job
    assert fp != bl_ci.failure_fingerprint("kb-tests", "_tools/test_b.py::test_two")  # another failure


def _gitlab_com_log(failing):
    """A kb-tests-windows log as GitLab.com writes it: every line behind a timestamp and a stream marker."""
    return ("2026-09-29T01:06:30.100000Z 00O \x1b[0KRunning with gitlab-runner 18.4.0 (0123abcd)\n"
            "2026-09-29T01:06:31.200000Z 00O section_start:1759107991:step_script\r\x1b[0K\x1b[0K\x1b[36;1mExecuting\n"
            "2026-09-29T01:06:40.300000Z 01O _tools/test_a.py::test_ok PASSED\n"
            f"2026-09-29T01:06:40.889927Z 01O FAILED {failing} - AssertionError: 1 != 2\n"
            "2026-09-29T01:06:40.900000Z 01O+ continued output\n"
            "2026-09-29T01:06:40.950000Z 01O+continued output\n"
            "2026-09-29T01:06:41.000000Z 01E ERROR: Job failed: exit code 1\n")


def test_gitlab_com_continuation_forms_give_one_failure_and_fingerprint():
    ts = "2026-09-29T01:06:40.889927Z"
    tid = "_tools/test_a.py::test_x"
    forms = {"first line": "01O ", "spaced continuation": "01O+ ", "real continuation": "01O+"}
    logs = [f"{ts} 00O start\n{ts} {m}FAILED {tid} - x\n" for m in forms.values()]
    assert [bl_ci.first_failure(x) for x in logs] == [tid] * 3
    assert len({bl_ci.failure_fingerprint("kb-tests-windows", bl_ci.first_failure(x)) for x in logs}) == 1
    # the error-line fallback reads the three forms alike
    errs = [f"{ts} {m}ERROR: Job failed: exit code 1\n" for m in ("01E ", "01E+ ", "01E+")]
    assert {bl_ci.first_failure(x) for x in errs} == {"ERROR: Job failed: exit code <n>"}
    assert len({bl_ci.failure_fingerprint("kb-tests", bl_ci.first_failure(x)) for x in errs}) == 1
    # a marker glued to text without a + is no marker: the id is not read from it
    assert bl_ci.first_failure(f"{ts} 01OFAILED {tid} - x\n") != tid
    # the fixture carries both continuation forms and still reads its failing id
    assert "01O+continued" in _gitlab_com_log(tid) and "01O+ continued" in _gitlab_com_log(tid)
    assert bl_ci.first_failure(_gitlab_com_log(tid)) == tid


def test_fingerprint_strips_gitlab_com_timestamp_and_stream_marker():
    ids = ["_tools/test_a.py::test_x", "_tools/test_b.py::test_y", "_tools/test_c.py::test_z"]
    assert [bl_ci.first_failure(_gitlab_com_log(t)) for t in ids] == ids
    fps = {bl_ci.failure_fingerprint("kb-tests-windows", bl_ci.first_failure(_gitlab_com_log(t))) for t in ids}
    assert len(fps) == 3  # three different failures, three fingerprints
    # the error-line fallback strips the prefix too: the same error at another time and stream gives one line
    a = bl_ci.first_failure("2026-09-29T01:06:41.000000Z 01E ERROR: Job failed: exit code 1\n")
    b_ = bl_ci.first_failure("2026-09-30T08:00:00.5Z 02O+ ERROR: Job failed: exit code 1\n")
    assert a == b_ == "ERROR: Job failed: exit code <n>"
    # a line without the prefix keeps a leading stream-like token
    assert bl_ci.first_failure("01E error: x\n") == "<n>E error: x"


# ---- recorded real GitLab.com job logs (_tools/fixtures/forge_logs/): the synthetic logs above are the author's
# guess at the format; these are what the forge sent, CRs, colour codes and section markers included

FORGE_LOGS = Path(TOOLS) / "fixtures" / "forge_logs"
REAL_WIN_FIRST = "_tools/test_kb_mcp.py::test_status_says_how_far_an_installed_plugin_is_behind_its_marketplace"
REAL_LINUX_FIRST = "_tools/test_kb_http.py::test_kb_http_roots_default_serves_public_only"


def real_forge_log(name):
    """(job, log) of a recorded real job log: its lines joined byte for byte as the forge sent them."""
    doc = json.loads((FORGE_LOGS / f"{name}.json").read_text(encoding="utf-8"))
    return doc["job"], "".join(doc["lines"])


def test_real_forge_log_first_failure_is_its_first_failing_test(monkeypatch):
    win_job, win = real_forge_log("gitlab-com-kb-tests-windows")
    lin_job, lin = real_forge_log("gitlab-com-kb-tests")
    assert (win_job, lin_job) == ("kb-tests-windows", "kb-tests")
    assert re.search(r"^\d{4}-\d\d-\d\dT[\d:.]+Z \d\d[OE] ", win, re.M) and "\r\n" in win and "\x1b[" in lin
    assert bl_ci.first_failure(win) == REAL_WIN_FIRST
    assert bl_ci.first_failure(lin) == REAL_LINUX_FIRST
    # two real failures under one job name give two fingerprints, not the one every real log gave (BG-jam2lysj)
    fps = {bl_ci.failure_fingerprint("kb-tests-windows", bl_ci.first_failure(x)) for x in (win, lin)}
    assert len(fps) == 2
    # planted: the parser without the GitLab.com timestamp and stream-marker rule reads no test id from either, only
    # an error line with the runner's timestamp in it
    monkeypatch.setattr(bl_ci, "LOG_PREFIX_RE", re.compile(r"^\s*(?:section_(?:start|end):\d+:\S+\s*)?"))
    for log, test_id in ((win, REAL_WIN_FIRST), (lin, REAL_LINUX_FIRST)):
        assert bl_ci.first_failure(log) != test_id and bl_ci.first_failure(log).startswith("<n>-<n>-<n>T")


def test_real_forge_log_red_pipeline_files_one_bug_per_real_failure(repo, monkeypatch):
    """red-pipeline end to end over the recorded logs: each real failure of kb-tests-windows files its own bug, whose
    fingerprint names the test that failed first."""
    sha = head(repo)
    _, win = real_forge_log("gitlab-com-kb-tests-windows")
    _, lin = real_forge_log("gitlab-com-kb-tests")
    pipelines = [{"id": 801, "sha": sha, "status": "failed"}]
    jobs = [{"id": 30, "name": "kb-tests-windows", "status": "failed", "failure_reason": "script_failure"}]
    logs = {30: win}
    forge(monkeypatch, repo, pipelines, jobs=jobs, logs=logs)
    assert red_pipeline(repo) == 0
    (first,) = bugs(repo)
    assert f"fingerprint {bl_ci.failure_fingerprint('kb-tests-windows', REAL_WIN_FIRST)}" in first["links"]
    pipelines[:] = [{"id": 802, "sha": sha, "status": "failed"}]
    logs[30] = lin
    assert red_pipeline(repo) == 0
    (second,) = [x for x in bugs(repo) if x["id"] != first["id"]]
    assert f"fingerprint {bl_ci.failure_fingerprint('kb-tests-windows', REAL_LINUX_FIRST)}" in second["links"]


def test_fingerprint_same_failure_one_bug_different_failure_a_second(repo, monkeypatch, capsys):
    sha = head(repo)
    pipelines = [{"id": 901, "sha": sha, "status": "failed"}]
    jobs = [{"id": 11, "name": "lint", "status": "failed"}, {"id": 10, "name": "check", "status": "failed"}]
    logs = {10: "2026-09-01T10:00:00Z FAILED _tools/test_x.py::test_a - assert 3 == 4\n", 11: "lint error\n"}
    forge(monkeypatch, repo, pipelines, jobs=jobs, logs=logs)
    assert red_pipeline(repo) == 0
    (first,) = bugs(repo)
    fp = bl_ci.failure_fingerprint("check", "_tools/test_x.py::test_a")  # the first failed job by name
    assert first["links"] == ["pipeline 901", f"fingerprint {fp}"]
    assert "_tools/test_x.py::test_a" in first["notes"]
    # a later pipeline failing the same way (other job ids, times and numbers): no second bug, its pipeline is added
    pipelines[:] = [{"id": 902, "sha": sha, "status": "failed"}]
    jobs[:] = [{"id": 20, "name": "check", "status": "failed"}]
    logs.clear()
    logs[20] = "2026-09-03T08:15:42Z FAILED _tools/test_x.py::test_a - assert 7 == 9\n"
    capsys.readouterr()
    assert red_pipeline(repo) == 0
    assert "fails the same way" in capsys.readouterr().out
    (same,) = bugs(repo)
    assert same["id"] == first["id"] and same["links"] == ["pipeline 901", f"fingerprint {fp}", "pipeline 902"]
    assert backlog.validate(backlog.Backlog(repo)) == []
    assert red_pipeline(repo) == 0 and len(bugs(repo)) == 1  # 902 again: named in the links, nothing filed
    # a different failure: a second bug with its own fingerprint
    pipelines[:] = [{"id": 903, "sha": sha, "status": "failed"}]
    logs[20] = "FAILED _tools/test_y.py::test_b - KeyError\n"
    assert red_pipeline(repo) == 0
    second = [x for x in bugs(repo) if x["id"] != first["id"]]
    assert len(second) == 1
    assert second[0]["links"] == ["pipeline 903", f"fingerprint {bl_ci.failure_fingerprint('check', '_tools/test_y.py::test_b')}"]


def test_fingerprint_of_a_closed_bug_files_a_new_one(repo, monkeypatch):
    sha = head(repo)
    pipelines = [{"id": 31, "sha": sha, "status": "failed"}]
    forge(monkeypatch, repo, pipelines, jobs=[{"id": 5, "name": "check", "status": "failed"}],
          logs={5: "Traceback (most recent call last):\n"})
    assert red_pipeline(repo) == 0
    (old,) = bugs(repo)
    edit(repo, old["id"], status="dropped")  # planted: only an open bug takes the pipeline
    pipelines[:] = [{"id": 32, "sha": sha, "status": "failed"}]
    assert red_pipeline(repo) == 0
    new = [x for x in bugs(repo) if x["id"] != old["id"]]
    assert len(new) == 1 and "pipeline 32" in new[0]["links"] and new[0]["links"][1] == old["links"][1]
