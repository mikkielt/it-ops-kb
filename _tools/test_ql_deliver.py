"""Query log tests, deliver (kb/_self/querylog.md, Apply and Delivery; `python3 _tools/tests.py -k TestApply`,
and the other classes below).

  TestApply         in a kb copy, `learn` then `apply` on the fixture store (a paraphrase and an unknown word): each
                    eval row lands with its expansion or alias, `rag.py eval` passes, the mean pack and off-kb `good`
                    do not rise; a miss with no accepted fix becomes a gap candidate and its fix `rejected`, as new
                    records; a second apply and learn change nothing; planted: an eval row without its fix fails
  TestApplyGates    apply with stub gates: planted failures for an eval row without its fix finding, a fix that fails
                    the gates (files put back), an alias term colliding with an existing term, source findings
                    (never applied), a red eval before any change; convergence
  TestPushRules     apply --push without git: the host and forge from origin's url (GitLab.com when it names none);
                    only a finished failure is red (planted: each GitLab and GitHub state); the CI check is skipped
                    with a note when glab or gh is not signed in, and the glab and gh calls; the KB-Auto values of a
                    commit's paths, research's articles, sources, conflicts and coverage included (planted: a tool,
                    a kb/_self doc, the answers or anchors are refused); an edited fact line is refused at commit
  TestRetry         a finding recorded apply-failed is not applied again when a later record opens it (planted:
                    FAILED_RETRIES=1 applies it); findings named by --hold are left alone
  TestKbAutoTrailer (marker git) check-trailers reads a commit's KB-Auto trailer (planted: an unknown value, a second
                    line), in a clone of the shared seed; the pushes themselves are test_querylog_e2e.py's scenarios
  TestDeliverRules  distill with a stub push: mode `local` never pushes and deletes the spool rows at once; mode
                    `auto` keeps them while the push fails (planted), distills nothing twice, and spool_delivered
                    deletes only the delivered entries' rows; the leak scan over store files (planted: an address in
                    a field `check` never reads)
  TestWorkSidecarDelivery  `apply --push` copies the work sidecar with its run file, as it copies the usage sidecar
                    (`-k work_sidecar`), counts it in the commit's words, copies none that origin/main holds, and
                    refuses the copy when the worktree's `querylog.py check` flags it (planted: a session id)
  TestHostRules     push_refusal on each refusal shape (GitLab project and protected branch, GitHub denied and GH006,
                    HTTP 403) and on what is no refusal (a generic declined hook, DNS, connection, remote failure);
                    the install url from known_marketplaces.json (git, github) or the marketplace clone's origin;
                    cloud_session from CLAUDE_CODE_REMOTE; `apply --push` in a plugin host runs host_push; the
                    host's apply names its data directory for research
  TestHost*InGit    (marker git) a plugin host in mode `auto` with a fake plugins directory and a local bare remote:
                    the push runs from the managed clone under the data directory and lands on main (TestHostInGit);
                    a remote whose pre-receive hook refuses with GitLab's or GitHub's message writes DISABLED and
                    deletes the spool, and distill then logs nothing (TestHostRefusalsInGit); planted: an unreachable
                    remote at clone and a red gate (TestHostInGit), a generic declined hook and an unreachable remote
                    at push (TestHostNoRefusalInGit) write no DISABLED and keep the spool
  TestCloudInGit    (marker git) a cloud session whose remote takes pushes to the checked-out branch only: the
                    automatic commits land on that branch and main stays; a second run pushes nothing; a detached
                    HEAD is refused
  TestNoGateJobs    with no job named in ql_deliver.GATE_JOBS a pipeline nobody ran is not red, and the gate
                    jobs of a stub list decide the verdict
  TestJobVerdict    ql_deliver.job_verdict reads a pipeline by its jobs: red, unverified or green, each job state
                    planted
  TestJobStateTable job_ran and job_verdict over every job status, started or not, and each failure reason the code
                    names (`-k job_state_table`, with test_backlog.py's red-pipeline rows); a row an open bug breaks is
                    a strict xfail naming it
  the revert's bug  the fingerprint of a red automatic push's pipeline is backlog.py's, and a second pipeline
                    that fails the same way joins the open bug (planted, and on recorded real GitLab.com logs)
Every run writes under a temporary plugin data directory (conftest.querylog_env), never the clone's own spool, and no
test calls the real `claude`: Haiku is the recorded reply file or a stub. The git scenarios clone the run's shared
seed (conftest.kb_seed), and a worktree's `querylog.py check` runs in the test process (ql_testkit.run_here). The
helpers the classes share are in ql_testkit.py.
"""
import json, os, re, subprocess, sys
from pathlib import Path

import pytest

import querylog, ql_apply, ql_base, ql_deliver, ql_distill, ql_learn, ql_research, ql_store
from conftest import copy_kb, D, GIT, git_env, KB, P, querylog_env, Repo, TOOLS
from ql_testkit import (ALIAS_Q, apply_store, auto_config, by_id, E, findings, FIXTURES, golden_store, jsonl, LAPS,
                        learn_store, NOW, PARAPHRASE_Q, PASSED, passing, plant_spool, plant_staging, plugins_dir, QL,
                        QUOTA, run_here, RUN_ID, run_learn, S_ENDED, S_IDLE, S_OPEN, signed_out, store_files, tree)
from ql_testkit import staging_planted  # noqa: F401  (autouse: the planted registry and routes table)


KB_DATA = ("kb/public/_retrieval/lookup_eval.csv", "kb/public/_retrieval/doc2query/expansions.csv",
           "_tools/aliases.csv")


@pytest.fixture(scope="module")
def applied(tmp_path_factory):
    """A kb copy and the apply store after `learn` then `apply` in the copy: (home, store, env, apply's output,
    the copy's kb data files before)."""
    base = tmp_path_factory.mktemp("apply")
    home = Path(copy_kb(str(base / "kb")))
    web_sources = home / "kb" / "_self" / "web-sources.md"
    plant_staging(home / "_tools" / "providers.csv", web_sources, web_sources)  # findings=10 whatever the clone stages
    store = apply_store(base)
    env = querylog_env(base / "data", home=str(home), base={**os.environ, "KB_INDEX": str(home / "_cache")})
    before = {f: (home / f).read_bytes() for f in KB_DATA}
    ql = [sys.executable, str(home / "_tools" / "querylog.py")]
    said = []
    for cmd in ("learn", "apply"):
        p = subprocess.run([*ql, cmd, "--store", str(store)], capture_output=True, text=True, encoding="utf-8",
                           env=env, cwd=home, timeout=600)
        assert p.returncode == 0, p.stdout + p.stderr
        said.append(p.stdout.strip())
    return home, store, env, said, before


def kb_rows(home, rel):
    return ql_apply.csv_rows(Path(home) / rel)


class TestApply:
    def test_eval_rows_come_with_their_fixes(self, applied):
        home, store, env, said, before = applied
        assert said[1].startswith("apply: run=") and "applied=4 rejected=2 no-fix=1" in said[1], said  # a4 off the kb
        m = re.search(r"eval=(\d+)/(\d+) mean-pack=(\d+)->(\d+) offkb-good=(\d+)->(\d+)", said[1])
        passed, n, mean0, mean1, good0, good1 = map(int, m.groups())
        assert passed == n and mean1 <= mean0 and good1 <= good0, said[1]  # the doc2query.md measurements
        added = {rel: kb_rows(home, rel)[len(ql_apply.csv_rows(Path(KB) / rel)):] for rel in KB_DATA}
        import kbfacts, kbid
        assert added["kb/public/_retrieval/lookup_eval.csv"] == [
            [kbid.eval_id(PARAPHRASE_Q), PARAPHRASE_Q, "windows/laps.md", "good", ""],
            [kbid.eval_id(ALIAS_Q), ALIAS_Q, "windows/laps.md", "good", ""]]
        assert added["_tools/aliases.csv"] == [["zqxlapsor", "laps"]]  # into the existing laps group
        ((key, q),) = added["kb/public/_retrieval/doc2query/expansions.csv"]
        facts = {kbfacts.fact_key(u["text"]) for u in kbfacts.units(LAPS) if u["path"] == LAPS and u["tags"]}
        assert q == PARAPHRASE_Q and key in facts
        p = subprocess.run([sys.executable, str(home / "_tools" / "rag.py"), "eval"], capture_output=True, text=True,
                           encoding="utf-8", env=env, cwd=home, timeout=600)
        assert p.returncode == 0 and f"questions={n} passed={n}" in p.stdout, p.stdout[-400:]
        p = subprocess.run([sys.executable, str(home / "_tools" / "doc2query.py"), "stale"], capture_output=True,
                           text=True, encoding="utf-8", env=env, cwd=home, timeout=600)
        assert p.returncode == 0, p.stdout

    def test_outcomes_are_new_records(self, applied):
        home, store, env, said, before = applied
        (_, learned), (_, outcomes) = findings(store)
        now = by_id(store)
        kinds = {(r["kind"], r.get("entry")): r for r in now.values()}
        for n in ("a1", "a2"):
            assert kinds[("eval", E(n))]["state"] == "applied"
        assert kinds[("expansion", E("a1"))]["state"] == "applied" and kinds[("alias", E("a2"))]["state"] == "applied"
        miss = kinds[("eval", E("a3"))]  # no accepted fix: a gap candidate, the promotion on the finding
        assert (miss["state"], miss["stage"]) == ("no-fix", "candidate-gap")
        assert miss["promotions"] == [{"from": "miss", "to": "candidate-gap", "by": "apply"}]
        assert kinds[("expansion", E("a3"))]["state"] == "rejected" and kinds[("expansion", E("a3"))]["observed"]["gate"]
        assert not [r for r in outcomes if r["kind"] == "source"]  # left alone
        gap = kinds[("gap", E("a4"))]  # VMware Horizon: a none pack whose lead holds half its key words or fewer
        assert (gap["state"], gap["stage"], gap["observed"]["gate"]) == ("rejected", "candidate-gap",
                                                                          ["off the kb's domains"])
        assert {r["id"] for r in learned} >= {r["id"] for r in outcomes}  # the learn file is not edited
        assert ql_store.store_problems(store) == []

    def test_a_second_apply_changes_nothing(self, applied):
        home, store, env, said, before = applied
        tree_before = tree(store), {f: (home / f).read_bytes() for f in KB_DATA}
        ql = [sys.executable, str(home / "_tools" / "querylog.py")]
        for cmd, want in (("apply", "apply: nothing to apply"), ("learn", "learn: nothing new (findings=10)")):
            p = subprocess.run([*ql, cmd, "--store", str(store)], capture_output=True, text=True, encoding="utf-8",
                               env=env, cwd=home, timeout=600)
            assert (p.returncode, p.stdout.strip()) == (0, want), p.stdout + p.stderr
        assert (tree(store), {f: (home / f).read_bytes() for f in KB_DATA}) == tree_before

    def test_an_eval_row_without_its_fix_fails_the_eval(self, tmp_path):
        import kbid, rag  # planted: the row alone, on this clone, which has no zqxlapsor alias
        f = tmp_path / "lookup_eval.csv"
        f.write_text(f"id,question,expect_paths,expect_verdict,allow_weak\n{kbid.eval_id(ALIAS_Q)},{ALIAS_Q},"
                     "windows/laps.md,good,\n", encoding="utf-8", newline="\n")
        assert rag.run_eval(str(f))["passed"] == 0

    def test_cli_off(self, tmp_path):
        (tmp_path / "data" / "querylog").mkdir(parents=True)
        (tmp_path / "data" / "querylog" / "config.json").write_text('{"mode": "off"}', encoding="utf-8")
        p = subprocess.run([sys.executable, QL, "apply"], capture_output=True, text=True, encoding="utf-8",
                           env=querylog_env(tmp_path / "data"), timeout=120)
        assert (p.returncode, p.stdout) == (0, "apply: logging is off\n")


class StubGate(ql_apply.Gate):
    """The kb gates on three files in a temporary directory: the eval set, the aliases and the expansions. A new eval
    row passes when `works` and some fix row was written with it; `measure` counts its calls."""

    def __init__(self, d, works=True, unknown=("zqxlapsor", "plomkinator")):
        import kbfacts
        self.files = {"eval": d / "lookup_eval.csv", "aliases": d / "aliases.csv", "expansions": d / "expansions.csv"}
        self.files["eval"].write_text("id,question,expect_paths,expect_verdict,allow_weak\nEV-old,Old?,a/b.md,good,\n",
                                      encoding="utf-8", newline="\n")
        self.files["aliases"].write_text("term,canonical\nsccm,configmgr\nconfigmgr,configmgr\nlaps,laps\n",
                                         encoding="utf-8", newline="\n")
        self.files["expansions"].write_text("key,question\n", encoding="utf-8", newline="\n")
        self.first = {k: p.read_bytes() for k, p in self.files.items()}
        self.works, self.missing, self.measured = works, [kbfacts.stem(w) for w in unknown], 0

    def fresh(self):
        pass

    def pack(self, question):
        return {"verdict": "none", "paths": [], "missing": self.missing}

    def measure(self):
        self.measured += 1
        rows = ql_apply.csv_rows(self.files["eval"])
        fixed = any(self.files[k].read_bytes() != self.first[k] for k in ("aliases", "expansions"))
        passed = len(rows) if self.works and fixed else 1
        return {"n": len(rows), "passed": passed, "failed": [r[0] for r in rows[passed:]],
                "chars": {r[0]: 100 for r in rows}, "offkb_good": 0}

    def targets(self, article):
        return {"root": "public", **self.files}

    def facts(self, article):
        return [(10, "PasswordLength default 14 characters."), (11, "Password age default 30 days.")]

    def title(self, article):
        return "Windows LAPS: policy"


def unknown_pack(q):
    import kbfacts
    return {"verdict": "none", "paths": [], "missing": [kbfacts.stem(w) for w in ("zqxlapsor", "plomkinator")]}


@pytest.fixture
def stub_store(tmp_path):
    """The fixture store after one learn where every miss fails and zqxlapsor and plomkinator are unknown words:
    eval findings for a1, a2 and a3, an alias for a2, expansions for a1 and a3, a gap and source findings."""
    store = learn_store(tmp_path)
    run_learn(store, unknown_pack)
    return store


def run_apply(store, gate):
    said = []
    rc = ql_apply.apply(store, gate=gate, kb_commit="0" * 40, out=said.append)
    return rc, said


class TestApplyGates:
    def test_applied_with_stub_gates_then_converges(self, stub_store, tmp_path):
        gate = StubGate(tmp_path)
        rc, said = run_apply(stub_store, gate)
        assert rc == 0 and "applied=6 rejected=1 no-fix=0" in said[0], said  # the gap: off the kb's domains
        assert [r[0] for r in ql_apply.csv_rows(gate.files["aliases"])][-3:] == ["laps", "zqxlapsor", "plomkinator"]
        first = tree(stub_store), {k: p.read_bytes() for k, p in gate.files.items()}
        n = gate.measured
        assert run_apply(stub_store, gate) == (0, ["apply: nothing to apply"])
        assert (tree(stub_store), {k: p.read_bytes() for k, p in gate.files.items()}) == first
        assert gate.measured == n  # nothing open: no gate ran
        assert ql_store.store_problems(stub_store) == []

    def test_an_eval_row_is_never_written_without_its_fix(self, stub_store, tmp_path):
        (p,) = ql_store.findings_files(stub_store)  # planted: learn's fix records gone
        objs = jsonl(p)
        objs = [objs[0]] + [o for o in objs[1:] if o["kind"] not in ql_store.FIX_KINDS]
        objs[0]["counts"]["findings"] = len(objs) - 1
        p.write_text("".join(json.dumps(o) + "\n" for o in objs), encoding="utf-8", newline="\n")
        gate = StubGate(tmp_path)
        rc, said = run_apply(stub_store, gate)
        assert rc == 0 and "applied=0 rejected=1 no-fix=3" in said[0], said  # the gap: off the kb's domains
        assert {k: p.read_bytes() for k, p in gate.files.items()} == gate.first
        recs = [r for r in by_id(stub_store).values() if r["kind"] == "eval"]
        assert all(r["observed"]["gate"] == ["no fix finding"] and r["stage"] == "candidate-gap" for r in recs)

    def test_a_fix_that_fails_the_gates_is_put_back(self, stub_store, tmp_path):
        gate = StubGate(tmp_path, works=False)  # planted: no fix makes the new eval row pass
        rc, said = run_apply(stub_store, gate)
        assert rc == 0 and "applied=0 rejected=4 no-fix=3" in said[0], said  # two fixes and one alias, the gap
        assert {k: p.read_bytes() for k, p in gate.files.items()} == gate.first  # every file as it was
        assert ql_store.store_problems(stub_store) == []

    @pytest.mark.parametrize("unknown,terms,problem", [
        (("sccm",), ["sccm"], "alias sccm: already a term of configmgr"),
        ((), ["password"], "alias password: a word the kb holds"),
    ])
    def test_an_alias_colliding_with_an_existing_term_is_refused(self, tmp_path, unknown, terms, problem):
        store = learn_store(tmp_path)
        run_learn(store, unknown_pack)
        (p,) = ql_store.findings_files(store)
        objs = jsonl(p)
        for o in objs[1:]:
            if o["kind"] == "alias":
                o["terms"] = terms  # planted: a term an alias file or the kb already holds
        p.write_text("".join(json.dumps(o) + "\n" for o in objs), encoding="utf-8", newline="\n")
        gate = StubGate(tmp_path, unknown=unknown)
        run_apply(store, gate)
        assert gate.files["aliases"].read_bytes() == gate.first["aliases"]
        rec = next(r for r in by_id(store).values() if r["kind"] == "alias")
        assert rec["state"] == "rejected" and problem in rec["observed"]["gate"], rec
        miss = by_id(store)[ql_store.finding_id("eval", E("a2"))]
        assert (miss["state"], miss["stage"]) == ("no-fix", "candidate-gap")

    def test_alias_problems(self):
        existing = {"sccm": "configmgr", "configmgr": "configmgr", "laps": "laps"}
        assert ql_apply.alias_problems(["zqx"], "laps", existing, ["zqx"]) == []
        assert ql_apply.alias_problems(["sccm"], "laps", existing, ["sccm"]) == ["alias sccm: already a term of configmgr"]
        assert ql_apply.alias_problems(["laps"], "laps", existing, []) == ["alias laps: already a term of laps"]
        assert ql_apply.alias_problems(["zqx"], "laps", existing, []) == ["alias zqx: a word the kb holds"]
        assert ql_apply.alias_problems(["zqx"], "sccm", existing, ["zqx"]) == ["alias sccm: a term of configmgr"]

    def test_source_findings_are_never_applied(self, tmp_path):
        store = learn_store(tmp_path)
        run_learn(store, passing)  # every miss passes: only source findings stay open
        assert {r["kind"] for r in by_id(store).values() if r["state"] == "open"} == {"source"}
        gate = StubGate(tmp_path)
        before = tree(store)
        assert run_apply(store, gate) == (0, ["apply: nothing to apply"])
        assert tree(store) == before and gate.measured == 0
        assert {k: p.read_bytes() for k, p in gate.files.items()} == gate.first

    def test_a_red_eval_before_any_change_applies_nothing(self, stub_store, tmp_path):
        gate = StubGate(tmp_path)
        gate.measure = lambda: {"n": 2, "passed": 1, "failed": ["EV-x"], "chars": {}, "offkb_good": 0}
        before = tree(stub_store)
        rc, said = run_apply(stub_store, gate)
        assert rc == 1 and "nothing applied" in said[0] and tree(stub_store) == before


# --- apply --push (Query log item 7) --------------------------------------------------------------------------------

class TestPushRules:
    @pytest.mark.parametrize("url,want", [
        ("git@gitlab.com:grp/proj.git", ("gitlab", "gitlab.com", "grp/proj")),
        ("https://gitlab.corp.example.com:8443/a/b/c.git", ("gitlab", "gitlab.corp.example.com", "a/b/c")),
        ("ssh://git@gitlab.corp.example.com:2222/a/b.git", ("gitlab", "gitlab.corp.example.com", "a/b")),
        ("https://github.com/o/r.git", ("github", "github.com", "o/r")),
        ("git@github.com:o/r.git", ("github", "github.com", "o/r")),
        ("/tmp/x/remote.git", ("gitlab", ql_deliver.FALLBACK_GITLAB_HOST, "x/remote")),
        ("C:\\work\\x\\remote.git", ("gitlab", ql_deliver.FALLBACK_GITLAB_HOST, "x/remote")),
        ("file:///srv/x/remote.git", ("gitlab", ql_deliver.FALLBACK_GITLAB_HOST, "x/remote")),
    ])
    def test_the_host_comes_from_origins_url(self, url, want):
        assert ql_deliver.origin_forge(url) == want

    @pytest.mark.parametrize("status,want", [
        ("failed", "red"), ("success", "ok"), ("manual", "ok"), ("skipped", "ok"), ("canceled", "ok"),
        ("created", "pending"), ("pending", "pending"), ("running", "pending"), ("waiting_for_resource", "pending"),
        ("preparing", "pending"), ("scheduled", "pending"), ("canceling", "pending"),
    ])
    def test_only_a_finished_failure_is_red_on_gitlab(self, status, want):
        assert ql_deliver.pipeline_verdict("gitlab", [status]) == want

    @pytest.mark.parametrize("runs,want", [
        ([("completed", "failure")], "red"), ([("completed", "timed_out")], "red"),
        ([("completed", "success"), ("completed", "startup_failure")], "red"),
        ([("completed", "cancelled")], "ok"), ([("completed", "skipped")], "ok"), ([("completed", "success")], "ok"),
        ([("in_progress", None)], "pending"), ([("queued", None), ("completed", "success")], "pending"),
    ])
    def test_only_a_finished_failure_is_red_on_github(self, runs, want):
        assert ql_deliver.pipeline_verdict("github", runs) == want

    def test_the_ci_check_is_skipped_when_no_cli_is_signed_in(self):
        calls = []

        def run(argv, cwd=None):
            calls.append(argv)
            return 1, "", "not logged in"
        verdict, detail = ql_deliver.ci_status("git@gitlab.corp.example.com:grp/proj.git", "a" * 40, run)
        assert verdict == "skip" and "glab is not signed in to gitlab.corp.example.com" in detail
        assert calls == [["glab", "auth", "status", "--hostname", "gitlab.corp.example.com"]]  # no API call

    def test_glab_and_gh_calls(self):
        calls = []

        def run(argv, cwd=None):
            calls.append(argv)
            if argv[1:3] == ["auth", "status"]:
                return 0, "", ""
            if argv[0] == "gh":
                return 0, json.dumps([{"status": "completed", "conclusion": "failure"}]), ""
            if "/jobs?" in argv[-1]:
                return 0, json.dumps([{"id": 9, "name": "kb-trailers", "status": "success"},
                                      {"id": 8, "name": "kb-tests", "status": "success"},
                                      {"id": 10, "name": "kb-tests-windows", "status": "manual"}]), ""
            return 0, json.dumps([{"id": 7, "status": "manual"}]), ""
        sha = "b" * 40
        assert ql_deliver.ci_status("git@gitlab.corp.example.com:grp/sub/proj.git", sha, run)[0] == "ok"
        assert calls[-2:] == [["glab", "api", "--hostname", "gitlab.corp.example.com",
                               f"projects/grp%2Fsub%2Fproj/pipelines?sha={sha}&per_page={ql_deliver.SHA_PIPELINES}"],
                              ["glab", "api", "--hostname", "gitlab.corp.example.com",
                               "projects/grp%2Fsub%2Fproj/pipelines/7/jobs?per_page=100"]]
        assert ql_deliver.ci_status("https://github.com/o/r.git", sha, run)[0] == "red"
        assert calls[-1][:6] == ["gh", "run", "list", "--commit", sha, "-R"] and calls[-1][6] == "github.com/o/r"

    def test_a_failed_or_empty_api_answer(self):
        def run(argv, cwd=None):
            return (0, "", "") if argv[1] == "auth" else (0, "[]", "")
        assert ql_deliver.ci_status("/x/y.git", "c" * 40, run)[0] == "none"

        def broken(argv, cwd=None):
            return (0, "", "") if argv[1] == "auth" else (1, "", "HTTP 404")
        assert ql_deliver.ci_status("/x/y.git", "c" * 40, broken) == ("skip", "glab api failed (HTTP 404)")


DEFAULT_GATE = ql_deliver.GATE_JOBS


class TestNoGateJobs:
    """Every job is manual, so no job is a gate by default: a pipeline is never `unverified` for a job nobody
    started, and a job whose script ran and failed still makes it red."""

    def test_no_job_is_a_gate_by_default(self):
        assert DEFAULT_GATE == ()

    @pytest.mark.parametrize("jobs", [
        [{"name": "kb-tests", "status": "manual"}, {"name": "kb-trailers", "status": "manual"}],
        [{"name": "kb-tests", **QUOTA}, {"name": "kb-trailers", "status": "skipped"}],
        [{"name": "kb-tests", "status": "canceled"}], [],
    ])
    def test_a_pipeline_whose_jobs_never_ran_is_ok(self, jobs):
        assert ql_deliver.job_verdict(jobs) == ("ok", [], [])

    def test_a_failed_script_is_red_and_an_unreadable_list_is_unverified(self):
        failed = {"name": "kb-tests-windows", "status": "failed", "failure_reason": "script_failure"}
        assert ql_deliver.job_verdict([failed, {"name": "kb-tests", "status": "manual"}]) == (
            "red", ["kb-tests-windows"], [])
        assert ql_deliver.job_verdict(None)[0] == "unverified"

    @pytest.mark.parametrize("reason", ["job_execution_timeout", "stuck_or_timeout_failure"])
    def test_a_timed_out_or_stuck_job_is_red(self, reason):
        job = {"name": "kb-tests-windows", "status": "failed", "failure_reason": reason}
        assert ql_deliver.job_ran(job)
        assert ql_deliver.job_verdict([job]) == ("red", ["kb-tests-windows"], [])

    @pytest.mark.parametrize("job,ran", [
        ({"status": "manual"}, False), ({"status": "skipped"}, False), ({"status": "created"}, False),
        ({"status": "canceled"}, False), ({**QUOTA}, False), ({"status": "canceled", "started_at": "t"}, False),
        ({"status": "success"}, True), ({"status": "running"}, True),
        ({"status": "failed", "failure_reason": "script_failure"}, True),
    ])
    def test_job_ran(self, job, ran):
        assert ql_deliver.job_ran(job) is ran

    def test_the_revert_check_reads_the_newest_pipeline_of_the_commit_where_a_job_ran(self):
        """Planted: a red started pipeline of the commit, then newer ones where no job ran."""
        jobs = {9: [{"name": "kb-tests", "status": "manual"}], 8: [],
                7: [{"name": "kb-tests", "status": "failed", "failure_reason": "script_failure"}]}

        def run(argv, cwd=None):
            if argv[1:3] == ["auth", "status"]:
                return 0, "", ""
            if "/jobs?" in argv[-1]:
                return 0, json.dumps(jobs[int(argv[-1].split("/pipelines/")[1].split("/")[0])]), ""
            return 0, json.dumps([{"id": i, "status": "manual"} for i in (9, 8, 7)]), ""
        verdict, detail, pipe = ql_deliver.ci_pipeline("https://gitlab.example.com/team/kb.git", "d" * 40, run)
        assert (verdict, pipe["id"]) == ("red", 7) and "the newest where a job ran" in detail, detail
        jobs[7] = [{"name": "kb-tests", "status": "manual"}]  # no job ran in any: the newest is read, and is ok
        verdict, _, pipe = ql_deliver.ci_pipeline("https://gitlab.example.com/team/kb.git", "d" * 40, run)
        assert (verdict, pipe["id"]) == ("ok", 9)


# ---- the job-state table: every GitLab job status, started or not, and every failure reason the code names
# (RAN_AND_FAILED, ci_quota_exceeded, runner_system_failure from BG-vsqfchgz, none). The expected value of each row
# comes from the documented rules (job_ran's and job_verdict's docstrings, kb/_self/backlog.md, red-pipeline), not
# from the code. A row that hits an open bug is a strict xfail naming it, so the fix must flip it. SP-z7a5c76b:
# TK-zutzzklq's checks passed on states its author chose while two S2 defects sat in states none planted.

JOB_STATUSES = ("created", "pending", "running", "success", "failed", "canceled", "skipped", "manual")
JOB_REASONS = ql_deliver.RAN_AND_FAILED + ("ci_quota_exceeded", "runner_system_failure", None)


def job_states():
    """[(status, started, failure_reason)]: each status started or not; a failed job with each reason."""
    return [(s, started, r) for s in JOB_STATUSES for started in (False, True)
            for r in (JOB_REASONS if s == "failed" else (None,))]


def job_of(status, started, reason, name="kb-tests"):
    j = {"id": 1, "name": name, "status": status, "allow_failure": True}
    if started:
        j["started_at"] = "2026-09-30T08:00:00Z"
    if reason:
        j["failure_reason"] = reason
    return j


def state_id(st):
    status, started, reason = st
    return f"{status}-{'started' if started else 'unstarted'}" + (f"-{reason}" if reason else "")


def own_failure(status, reason):
    return status == "failed" and reason in ql_deliver.RAN_AND_FAILED


def ran_rows():
    """job_ran: a start time, success, running or a failure of its own; a canceled job never counts (BG-sim2fdaa's
    goal: a job someone started and canceled is no verdict on it)."""
    rows = []
    for st in job_states():
        status, started, reason = st
        rows.append(pytest.param(st, status != "canceled" and (
            started or status in ("success", "running") or own_failure(status, reason)), id=state_id(st)))
    return rows


class TestJobStateTable:
    """ql_deliver.job_ran and job_verdict over the whole job-state table (`-k job_state_table`)."""

    def test_job_state_table_covers_every_status_and_reason(self):
        states = job_states()
        assert {s for s, _, _ in states} == set(JOB_STATUSES)
        assert {r for s, _, r in states if s == "failed"} >= set(ql_deliver.RAN_AND_FAILED) | {"ci_quota_exceeded"}
        assert all((s, not st, r) in states for s, st, r in states)

    @pytest.mark.parametrize("st,want", ran_rows())
    def test_job_state_table_job_ran(self, st, want):
        assert ql_deliver.job_ran(job_of(*st)) is want

    @pytest.mark.parametrize("st", job_states(), ids=state_id)
    def test_job_state_table_job_verdict_with_no_gate(self, st):
        """No gate job (the default): red only when the job failed on its own account, else ok."""
        status, _, reason = st
        want = ("red", ["kb-tests"], []) if own_failure(status, reason) else ("ok", [], [])
        assert ql_deliver.job_verdict([job_of(*st)], gate=()) == want

    @pytest.mark.parametrize("st", job_states(), ids=state_id)
    def test_job_state_table_job_verdict_with_the_job_a_gate(self, st):
        """The job a gate: red on its own failure, ok on success, pending while unfinished, else unverified naming
        its status (and failure reason)."""
        status, _, reason = st
        verdict, failed, unpassed = ql_deliver.job_verdict([job_of(*st)], gate=("kb-tests",))
        if own_failure(status, reason):
            assert (verdict, failed) == ("red", ["kb-tests"])
        elif status == "success":
            assert (verdict, failed, unpassed) == ("ok", [], [])
        else:
            assert verdict == ("pending" if status in ql_deliver.GITLAB_UNFINISHED else "unverified")
            assert failed == [] and unpassed == [f"kb-tests {status}" + (f" ({reason})" if reason else "")]


@pytest.fixture
def gate_jobs(monkeypatch):
    """The two jobs that were once gates, named again, for the tests of the gate mechanism."""
    monkeypatch.setattr(ql_deliver, "GATE_JOBS", ("kb-tests", "kb-trailers"))


@pytest.mark.usefixtures("gate_jobs")
class TestJobVerdict:
    """A GitLab pipeline read by its jobs (recorded job lists, no network), with GATE_JOBS named: every job is manual
    with allow_failure, so the pipeline's status says success whatever the jobs did."""

    @pytest.mark.parametrize("jobs,want", [
        (PASSED, ("ok", [], [])),
        (PASSED + [{"name": "kb-tests-windows", "status": "manual"}, {"name": "tool-stress", **QUOTA},
                   {"name": "kb-tests-floor", "status": "skipped"}], ("ok", [], [])),
        ([{"name": "kb-trailers", **QUOTA}, {"name": "kb-tests", **QUOTA}, {"name": "kb-tests-floor", **QUOTA}],
         ("unverified", [], ["kb-tests failed (ci_quota_exceeded)", "kb-trailers failed (ci_quota_exceeded)"])),
        ([{"name": "kb-trailers", "status": "manual"}, {"name": "kb-tests", "status": "manual"}],
         ("unverified", [], ["kb-tests manual", "kb-trailers manual"])),
        ([{"name": "kb-trailers", "status": "success"}, {"name": "kb-tests", "status": "skipped"}],
         ("unverified", [], ["kb-tests skipped"])),
        ([{"name": "kb-trailers", "status": "canceled"}, {"name": "kb-tests", "status": "success"}],
         ("unverified", [], ["kb-trailers canceled"])),
        ([{"name": "kb-tests", "status": "failed"}, {"name": "kb-trailers", "status": "success"}],
         ("unverified", [], ["kb-tests failed"])),  # no failure_reason: not shown to have run
        ([{"name": "kb-tests", "status": "success"}], ("unverified", [], ["kb-trailers not in the pipeline"])),
        ([], ("unverified", [], ["kb-tests not in the pipeline", "kb-trailers not in the pipeline"])),
        (None, ("unverified", [], ["the pipeline's jobs could not be read"])),
        ([{"name": "kb-tests", "status": "running"}, {"name": "kb-trailers", "status": "manual"}],
         ("pending", [], ["kb-tests running", "kb-trailers manual"])),
        ([{"name": "kb-tests", "status": "failed", "failure_reason": "script_failure", "allow_failure": True},
          {"name": "kb-trailers", "status": "success"}], ("red", ["kb-tests"], ["kb-tests failed (script_failure)"])),
        (PASSED + [{"name": "kb-tests-windows", "status": "failed", "failure_reason": "script_failure"}],
         ("red", ["kb-tests-windows"], [])),
        ([{"name": "kb-tests", "status": "success"}, {"name": "kb-tests", **QUOTA}, {"name": "kb-trailers", "status": "success"}],
         ("ok", [], [])),  # the newest entry of a name counts (the API lists newest first)
    ])
    def test_gate_jobs_decide(self, jobs, want):
        assert ql_deliver.job_verdict(jobs) == want

    def run(self, pipeline_status, jobs):
        calls = []

        def run(argv, cwd=None):
            calls.append(argv)
            if argv[1:3] == ["auth", "status"]:
                return 0, "", ""
            if "/jobs?" in argv[-1]:
                return (0, json.dumps(jobs), "") if jobs is not None else (1, "", "HTTP 500")
            return 0, json.dumps([{"id": 7, "status": pipeline_status}]), ""
        return ql_deliver.ci_pipeline("git@gitlab.corp.example.com:grp/proj.git", "d" * 40, run), calls

    def test_a_success_pipeline_whose_gate_never_ran_is_unverified(self):
        jobs = [{"name": "kb-tests-windows", "status": "manual"}, {"name": "kb-trailers", **QUOTA},
                {"name": "tool-stress", **QUOTA}, {"name": "kb-tests-floor", **QUOTA}, {"name": "kb-tests", **QUOTA}]
        (verdict, detail, pipe), _ = self.run("success", jobs)
        assert verdict == "unverified" and pipe["id"] == 7, detail
        assert detail.endswith("success; kb-tests failed (ci_quota_exceeded), kb-trailers failed (ci_quota_exceeded)")
        assert self.run("manual", [{"name": "kb-tests", "status": "manual"}])[0][0] == "unverified"
        assert self.run("success", None)[0][0] == "unverified"
        assert self.run("success", PASSED)[0][0] == "ok"

    def test_a_failed_script_under_allow_failure_is_red(self):
        (verdict, detail, _), _ = self.run("success", PASSED + [{"name": "tool-stress", "status": "failed",
                                                                  "failure_reason": "script_failure"}])
        assert verdict == "red" and detail.endswith("script failed in tool-stress"), detail

    @pytest.mark.parametrize("status,want", [("failed", "red"), ("running", "pending"), ("pending", "pending")])
    def test_the_pipeline_status_still_decides_a_failure_or_an_unfinished_run(self, status, want):
        (verdict, _, _), calls = self.run(status, None)
        assert verdict == want and not any("/jobs?" in c[-1] for c in calls)  # no job list needed

    def test_the_revert_fingerprint_names_a_script_that_ran(self):
        import backlog
        jobs = [{"id": 1, "name": "kb-lint", **QUOTA},
                {"id": 2, "name": "kb-tests", "status": "failed", "failure_reason": "script_failure"}]
        run = fingerprint_forge(jobs, {2: "FAILED _tools/test_x.py::test_a - assert 1 == 2\n"})
        failure, fp = ql_deliver.pipeline_failure("https://gitlab.example.com/team/kb.git", {"id": 3}, run)
        assert fp == backlog.failure_fingerprint("kb-tests", "_tools/test_x.py::test_a"), failure

    @pytest.mark.parametrize("job,named", [
        ({"id": 2, "name": "kb-tests", "status": "failed", "failure_reason": "script_failure"}, True),
        ({"id": 2, "name": "kb-tests", **QUOTA}, False),
        ({"id": 2, "name": "kb-tests", "status": "failed", "failure_reason": "runner_system_failure",
          "started_at": "2026-09-30T08:00:00Z"}, False),
    ])
    def test_the_revert_repro_names_a_job_only_when_its_script_ran_and_failed(self, job, named):
        """BG-vsqfchgz: a job that failed without running gets the plain `--status` repro, not `--job`."""
        run = fingerprint_forge([job], {2: "ERROR: Job failed\n"})
        pipe = {"id": 3}
        _, fp = ql_deliver.pipeline_failure("https://gitlab.example.com/team/kb.git", pipe, run)
        assert fp and pipe.get("job") == ("kb-tests" if named else None), pipe

    def test_auto_kinds(self):
        import kbgit
        paths = ["kb/_querylog/findings/2026-09/x.jsonl", "_tools/aliases.csv", "kb/public/_retrieval/lookup_eval.csv",
                 "kb/public/_retrieval/doc2query/expansions.csv", "kb/team/_retrieval/aliases.csv", "kb/public/_gaps.md"]
        assert ql_deliver.auto_kinds(paths) == ["alias", "eval", "expansion", "gap", "querylog"]
        assert set(ql_deliver.auto_kinds(paths)) <= set(kbgit.AUTO_VALUES)
        research = ["kb/public/windows/laps.md", "kb/public/_sources.csv", "kb/public/_conflicts.md",
                    "kb/public/_coverage.csv", "kb/public/_coverage.md", "kb/team/infra/dns/zones.md"]
        assert ql_deliver.auto_kinds(paths + research) == ["alias", "eval", "expansion", "gap", "querylog", "research"]
        assert ql_deliver.auto_kinds(["kb/_self/backlog/BG-abcdefgh.json"]) == ["revert"]  # a revert's bug item
        for p in ("_tools/kbfacts.py", "kb/_self/tools.md", "kb/_self/backlog.md", "kb/_self/backlog/x/y.json", "kb/public/_answers.md", "kb/public/_anchors.csv",
                  "README.md", "kb/public/_retrieval/signals.csv", "kb/public/_snapshots/S100.txt"):
            with pytest.raises(ValueError, match=re.escape(p)):  # planted: a path apply never writes
                ql_deliver.auto_kinds(paths + [p])

    def test_an_edited_line_is_refused_at_commit(self, tmp_path):
        """apply --push checks the worktree's change against HEAD: added lines pass, an edited fact line, ledger
        entry or source row is refused (planted)."""
        old = "---\ntopic: a/b\n---\n## Facts\n- One fact. [DOC S100]\n"
        f = tmp_path / ql_deliver.WORKTREE_NAME / "kb" / "public" / "a" / "b.md"
        f.parent.mkdir(parents=True)

        def run(argv, cwd=None):
            if argv[:3] == ["git", "cat-file", "-e"]:
                return 0, "", ""  # the file is at HEAD
            return (0, old, "") if argv[:3] == ["git", "cat-file", "blob"] else (1, "", "")
        p = ql_deliver.Pusher(tmp_path, tmp_path, run, None, print)
        f.write_text(old + "- Two facts. [DOC S101]\n", encoding="utf-8", newline="\n")
        assert p.edited(["kb/public/a/b.md"]) == []
        f.write_text(old.replace("One fact.", "One fact, edited."), encoding="utf-8", newline="\n")
        (why,) = p.edited(["kb/public/a/b.md"])
        assert "removes or edits an existing fact line" in why


def reopen(store, ids):
    """Planted: a later findings file that records `ids` open again, as a parallel learn in another clone could."""
    last = ql_store.finding_states(store)
    recs = [{**{k: v for k, v in last[i].items() if k != "observed"}, "state": "open"} for i in ids]
    ql_store.write_findings(store, ql_store.store_entries(store), recs, ql_store.LEARN_STATES, "0" * 40)


class TestRetry:
    def test_a_failed_finding_is_never_applied_again(self, stub_store, tmp_path, monkeypatch):
        (tmp_path / "a").mkdir()
        assert run_apply(stub_store, StubGate(tmp_path / "a"))[0] == 0
        applied = {i: r for i, r in by_id(stub_store).items() if r["state"] == "applied"}
        assert len(applied) == 6
        failed = [{**{k: v for k, v in r.items() if k != "observed"}, "state": ql_store.APPLY_FAILED,
                   "observed": {"ci": "failed", "commit": "0" * 12}} for r in applied.values()]
        ql_store.write_findings(stub_store, ql_store.store_entries(stub_store), failed, (ql_store.APPLY_FAILED,),
                                "0" * 40)
        assert ql_store.store_problems(stub_store) == []
        reopen(stub_store, list(applied))
        (tmp_path / "b").mkdir()
        gate = StubGate(tmp_path / "b")
        assert run_apply(stub_store, gate) == (0, ["apply: nothing to apply"])
        assert gate.measured == 0 and {k: p.read_bytes() for k, p in gate.files.items()} == gate.first
        monkeypatch.setattr(ql_apply, "FAILED_RETRIES", 1)  # planted: one retry allowed, and it is taken
        rc, said = run_apply(stub_store, gate)
        assert rc == 0 and "applied=6" in said[0], said

    def test_held_findings_are_left_alone(self, stub_store, tmp_path):
        gate = StubGate(tmp_path)
        hold = {i for i, r in by_id(stub_store).items() if r["kind"] in ("eval", "gap") + ql_store.FIX_KINDS}
        said = []
        assert ql_apply.apply(stub_store, gate=gate, kb_commit="0" * 40, out=said.append, hold=hold) == 0
        assert said == ["apply: nothing to apply"] and gate.measured == 0

    def test_the_command_line(self, stub_store, capsys):
        # the gap held too: this apply runs on the clone's own kb, which it must not write
        hold = sorted(i for i, r in by_id(stub_store).items() if r["kind"] in ("eval", "gap") + ql_store.FIX_KINDS)
        argv = ["apply", "--store", str(stub_store)]
        for i in hold:
            argv += ["--hold", i]
        assert querylog.main(argv) == 0 and capsys.readouterr().out.strip() == "apply: nothing to apply"
        assert querylog.main(["apply", "--push", "--store", str(stub_store)]) == 2  # the push has its own store


class RepoGate(ql_apply.Gate):
    """apply's gate on a worktree: the clone's real alias terms, facts and titles, a pack that misses, and a measure
    under which every candidate passes (the gates themselves are tested above); the files written are the
    worktree's."""

    def __init__(self, wt):
        self.wt = Path(wt)

    def fresh(self):
        pass

    def pack(self, question):
        return unknown_pack(question)

    def targets(self, article):
        return {"root": "public", "eval": self.wt / D("lookup_eval.csv"), "aliases": self.wt / "_tools" / "aliases.csv",
                "expansions": self.wt / D("doc2query/expansions.csv")}

    def measure(self):
        rows = ql_apply.csv_rows(self.targets(None)["eval"])
        return {"n": len(rows), "passed": len(rows), "failed": [], "chars": {r[0]: 100 for r in rows}, "offkb_good": 0}


def repo_step(wt, store, hold, out):
    return ql_apply.apply(store, gate=RepoGate(wt), kb_commit="0" * 40, out=out, hold=hold)


@pytest.mark.skipif(not GIT, reason="git is not installed")
@pytest.mark.git
class TestKbAutoTrailer:
    """kbgit.py check-trailers on a commit's KB-Auto trailer, in a clone of the shared seed (conftest.kb_seed)."""

    @pytest.fixture(scope="class")
    @classmethod
    def clone(cls, kb_seed, tmp_path_factory):
        c = Repo(tmp_path_factory.mktemp("ql-trailer") / "a")
        Repo(Path(c.path).parent).git("clone", "-q", str(kb_seed[0]), c.path)
        return c, kb_seed[1]

    @pytest.mark.parametrize("value,ok", [("eval", True), ("alias, eval", True), ("bogus", False),
                                          ("eval\nKB-Auto: alias", False)])
    def test_check_trailers_reads_kb_auto(self, clone, value, ok):
        c, base = clone
        c.git("checkout", "-q", "-B", "t-trailer", base)
        c.append("README.md", "x\n")
        c.git("commit", "-q", "-a", "--no-verify", "-m", "chore: x", "-m", f"KB-Auto: {value}")
        p = c.kbgit("check-trailers", "HEAD")
        c.git("checkout", "-q", "main")
        assert (p.returncode == 0) is ok, p.stdout
        if not ok:
            assert "KB-Auto: has " in p.stdout and "expected once, of querylog|eval|" in p.stdout, p.stdout


# --- the local store's run files and findings delivered to origin/main -------------------------------------------


def spool_names(qdir):
    sp = Path(qdir) / "spool"
    return sorted(p.name for p in sp.iterdir()) if sp.is_dir() else []


CLOSED = sorted([f"{S_ENDED}.jsonl", f"{S_ENDED}.end", f"{S_IDLE}.jsonl", "tools-2026-09-27.jsonl"])


class TestDeliverRules:
    """distill's spool rules for the push of mode `auto`, with a stub push (no git)."""

    def distill(self, q, mode, calls, rc=0):
        def deliver(qdir, out):
            calls.append(spool_names(qdir))
            return rc
        said = []
        got = ql_distill.distill(qdir=q, cfg=auto_config(q, mode), haiku=ql_base.Replay(FIXTURES / "haiku.json"),
                                 now_dt=NOW, run_id=RUN_ID, kb_commit="0" * 40, out=said.append, deliver=deliver)
        return got, said

    def test_local_never_pushes_and_deletes_the_rows_at_once(self, tmp_path):
        q = tmp_path / "querylog"
        plant_spool(q)
        calls = []
        rc, said = self.distill(q, "local", calls)
        assert rc == 0 and calls == [] and said == [f"distill: run={RUN_ID} entries=6 dropped=1 waiting=0"], said
        assert spool_names(q) == [f"{S_OPEN}.jsonl"]

    def test_auto_keeps_the_rows_until_their_run_file_is_on_main(self, tmp_path):
        q = tmp_path / "querylog"
        plant_spool(q)
        calls = []
        rc, said = self.distill(q, "auto", calls, rc=1)  # planted: the push fails
        assert rc == 1 and len(calls) == 1, said
        assert "distill: the spool keeps the rows of 6 entries until their run file is on origin/main" in said
        assert set(CLOSED) <= set(calls[0]) and set(CLOSED) <= set(spool_names(q))  # nothing deleted
        (run,) = store_files(q)
        before = run.read_bytes()
        rc, said = self.distill(q, "auto", calls, rc=1)  # the next run distills nothing twice
        assert rc == 1 and said[0] == "distill: nothing to write (waiting=0)", said
        assert store_files(q) == [run] and run.read_bytes() == before
        ids = [e["id"] for e in jsonl(run)[1:]]
        assert ql_distill.spool_delivered(q, ids[:0], NOW) == 0 and set(CLOSED) <= set(spool_names(q))
        assert ql_distill.spool_delivered(q, ids, NOW) == 6
        assert spool_names(q) == [f"{S_OPEN}.jsonl"]  # the open session is never touched

    def test_one_delivered_entry_leaves_the_others(self, tmp_path):
        q = tmp_path / "querylog"
        plant_spool(q)
        self.distill(q, "auto", [], rc=1)
        (run,) = store_files(q)
        entries = jsonl(run)[1:]
        sessions = {S_ENDED: (q / "spool" / f"{S_ENDED}.jsonl").read_text(encoding="utf-8"),
                    S_IDLE: (q / "spool" / f"{S_IDLE}.jsonl").read_text(encoding="utf-8")}
        one = next(e["id"] for e in entries if e["id"] in sessions[S_ENDED])
        assert ql_distill.spool_delivered(q, [one], NOW) == 1
        left = (q / "spool" / f"{S_ENDED}.jsonl").read_text(encoding="utf-8")
        assert one not in left and (q / "spool" / f"{S_IDLE}.jsonl").read_text(encoding="utf-8") == sessions[S_IDLE]
        rc, said = self.distill(q, "auto", [], rc=1)
        assert said[0] == "distill: nothing to write (waiting=0)" and store_files(q) == [run], said

    def test_the_leak_scan_over_store_files(self, tmp_path):
        store = tmp_path / "store"
        golden_store(store)
        rel = f"2026-09/{RUN_ID}.jsonl"
        assert ql_store.leak_problems(store, [rel]) == []
        objs = jsonl(FIXTURES / "golden.jsonl")
        objs[1]["tools"] = objs[1]["tools"] + ["anna.nowak" + "@" + "acme-corp.pl"]  # planted: a field check never reads
        golden_store(store, objs)
        (hit,) = ql_store.leak_problems(store, [rel])
        assert hit == f"{rel}:2: the leak scan flags an identifier (email)", hit


class TestWorkSidecarDelivery:
    """`apply --push` copies the work sidecar with its run file, as it copies the usage sidecar (`-k work_sidecar`)."""

    LINES = [{"item": "TK-aaaaaaaa", "prompts": 2, "main": {"claude-opus-5-5": {
        "requests": 2, "in": 5, "cw": 100, "cw1h": 0, "cr": 900, "out": 40}}}]

    def pusher(self, tmp_path):
        q = tmp_path / "querylog"
        local = golden_store(q / "store")
        ql_store.write_work(local, RUN_ID, self.LINES, 0, 1)
        pusher = ql_deliver.Pusher(tmp_path, q, None, lambda *a: 0, print, cloud=False)

        def gate(name, *args):  # the worktree's own querylog.py check, here this clone's
            p = subprocess.run([sys.executable, QL, *args], capture_output=True, text=True, encoding="utf-8",
                               timeout=120)
            return p.returncode, p.stdout, p.stderr
        pusher.tool = gate
        return q, pusher

    def test_work_sidecar_is_copied_with_its_run_file(self, tmp_path):
        q, pusher = self.pusher(tmp_path)
        _, new, kept = pusher.local_files()
        assert sorted(rel for _, rel, _ in new) == [f"2026-09/{RUN_ID}.jsonl", f"work/2026-09/{RUN_ID}.jsonl"]
        assert kept == []
        assert pusher.brought(new) == ("1 run file(s), 1 work sidecar(s)", [RUN_ID])
        code = pusher.bring(new, kept)  # copied into the worktree's store, then gated there
        assert code == 0
        copied = pusher.wt / ql_deliver.STORE_REL / "work" / "2026-09" / f"{RUN_ID}.jsonl"
        assert copied.read_bytes() == ql_store.work_files(q / "store")[0].read_bytes()

    def test_work_sidecar_already_on_main_is_not_copied_again(self, tmp_path):
        q, pusher = self.pusher(tmp_path)
        for rel in (f"2026-09/{RUN_ID}.jsonl", f"work/2026-09/{RUN_ID}.jsonl"):
            there = pusher.wt / ql_deliver.STORE_REL / rel
            there.parent.mkdir(parents=True, exist_ok=True)
            there.write_text("{}\n", encoding="utf-8")
        _, new, _ = pusher.local_files()
        assert new == []

    def test_work_sidecar_a_gate_failure_stops_the_copy_before_any_commit(self, tmp_path):
        q, pusher = self.pusher(tmp_path)
        path = ql_store.work_files(q / "store")[0]
        objs = jsonl(path)
        objs[1]["session_id"] = "3f2a4c1e-0000-4000-8000-00000000abcd"  # planted
        path.write_text("".join(json.dumps(o) + "\n" for o in objs), encoding="utf-8", newline="\n")
        said = []
        pusher.out = said.append
        _, new, kept = pusher.local_files()
        assert pusher.bring(new, kept) == 1
        assert said and "refused: the store gates fail" in said[0] and "session_id" in said[0], said


def learn_then_apply(wt, store, hold, out):
    """learn (pack: every question misses) and apply with the repo gate, in the worktree on its store."""
    rc = ql_learn.learn(store, pack=unknown_pack, kb_commit="0" * 40, out=out)
    return rc or repo_step(wt, store, hold, out)


# --- plugin hosts and cloud sessions -------------------------------------------------------------------------------

GITLAB_PROJECT = "GitLab: You are not allowed to push code to this project."
GITLAB_PROTECTED = "GitLab: You are not allowed to push code to protected branches on this project."
GITHUB_DENIED = "Permission to grp/proj.git denied to jan-kowalski."
GITHUB_GH006 = "error: GH006: Protected branch update failed for refs/heads/main.\nerror: Changes have been requested."
PUSH_RULE = "GitLab: Commit message does not follow the pattern '^(feat|fix):'"
UNREACHABLE = "http://127.0.0.1:9/grp/proj.git"  # a closed local port: a connection error, never the network


def reject_hook(message):
    """A pre-receive hook that prints `message` (each line, as a forge does) and refuses the push."""
    lines = "".join(f"echo {json.dumps(ln)} >&2\n" for ln in message.splitlines())
    return f"#!/bin/sh\n{lines}exit 1\n"


class TestHostRules:
    @pytest.mark.parametrize("text,kind", [
        (f"remote: {GITLAB_PROJECT}\nfatal: Could not read from remote repository.", "gitlab"),
        (f"remote: {GITLAB_PROTECTED}\n ! [remote rejected] main -> main (pre-receive hook declined)", "gitlab"),
        ("remote: GitLab: You are not allowed to force push code to a protected branch on this project.", "gitlab"),
        (f"ERROR: {GITHUB_DENIED}\nfatal: Could not read from remote repository.", "github"),
        ("remote: " + GITHUB_GH006.replace("\n", "\nremote: "), "github"),
        ("remote: Permission to grp/proj.git denied to jan-kowalski.\nfatal: unable to access "
         "'https://github.com/grp/proj.git/': The requested URL returned error: 403", "github"),
        ("fatal: unable to access 'https://gitlab.corp.example.com/grp/proj.git/': The requested URL returned "
         "error: 403", "http-403"),
    ])
    def test_a_refusal_for_want_of_rights(self, text, kind):
        assert ql_deliver.push_refusal(text).startswith(kind + ": "), ql_deliver.push_refusal(text)

    @pytest.mark.parametrize("text", [
        f"remote: {PUSH_RULE}\n ! [remote rejected] main -> main (pre-receive hook declined)",
        " ! [remote rejected] main -> main (pre-receive hook declined)",
        "fatal: unable to access 'https://gitlab.com/grp/proj.git/': Could not resolve host: gitlab.com",
        "ssh: Could not resolve hostname gitlab.com: nodename nor servname provided, or not known",
        "fatal: unable to access 'http://127.0.0.1:9/x.git/': Failed to connect to 127.0.0.1 port 9: Connection refused",
        " ! [remote failure] main -> main (remote failed to report status)",
        "fatal: unable to access 'https://gitlab.com/grp/proj.git/': The requested URL returned error: 503",
        "git@gitlab.corp.example.com: Permission denied (publickey).\nfatal: Could not read from remote repository.",
        "",
    ])
    def test_no_refusal(self, text):
        assert ql_deliver.push_refusal(text) is None

    def test_the_install_url(self, tmp_path, monkeypatch):
        root = plugins_dir(tmp_path / "a", {"source": "git", "url": "git@gitlab.corp.example.com:grp/proj.git"})
        assert ql_deliver.install_url(root) == "git@gitlab.corp.example.com:grp/proj.git"
        root = plugins_dir(tmp_path / "b", {"source": "github", "repo": "grp/proj"})
        assert ql_deliver.install_url(root) == "https://github.com/grp/proj.git"
        assert ql_deliver.install_url(tmp_path / "not-a-cache" / "x") is None
        monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
        assert ql_deliver.install_url(None) is None

    @pytest.mark.skipif(not GIT, reason="git is not installed")
    def test_the_install_url_from_the_marketplace_clone(self, tmp_path):
        root = plugins_dir(tmp_path, {"source": "url", "url": "https://corp.example.com/marketplace.json"})
        mkt = Repo(tmp_path / "plugins" / "marketplaces" / "mkt", git_env())
        os.makedirs(mkt.path)
        mkt.git("init", "-q")
        assert ql_deliver.install_url(root) is None  # a clone without origin names nothing
        mkt.git("remote", "add", "origin", "https://gitlab.corp.example.com/grp/proj.git")
        assert ql_deliver.install_url(root) == "https://gitlab.corp.example.com/grp/proj.git"

    def test_a_cloud_session(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_CODE_REMOTE", "true")
        assert ql_deliver.cloud_session()
        monkeypatch.setenv("CLAUDE_CODE_REMOTE", "false")
        assert not ql_deliver.cloud_session()
        monkeypatch.delenv("CLAUDE_CODE_REMOTE")
        assert not ql_deliver.cloud_session()

    def test_apply_push_in_a_plugin_host(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path))
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(ql_base.HOME))
        seen = []

        def host_push(qdir, run, apply_step, out, now_dt, root):
            seen.append(Path(qdir))
            return 0
        monkeypatch.setattr(ql_deliver, "host_push", host_push)
        assert querylog.main(["apply", "--push"]) == 0 and seen == [tmp_path / "querylog"]
        assert querylog.main(["apply", "--push", "--plugin-data", str(tmp_path)]) == 2  # the push names its own

    def test_a_host_without_an_install_source_is_refused(self, tmp_path):
        said = []
        assert ql_deliver.host_push(tmp_path, lambda argv, cwd=None: (1, "", ""), None, said.append,
                                    root=tmp_path / "x") == 2
        assert "install source is not recorded" in said[0] and not (tmp_path / ql_base.DISABLED_NAME).exists()

    def test_the_hosts_apply_reads_research_from_its_data_directory(self, tmp_path):
        calls = []

        def run(argv, cwd=None):
            calls.append(argv)
            return 0, "", ""
        p = ql_deliver.Pusher(tmp_path / "clone", tmp_path, run, None, print, research=["--plugin-data", str(tmp_path)])
        assert p.learn_and_apply(tmp_path / "wt", tmp_path / "wt" / "store", {"F-1"}, print) == 0
        assert calls[1][-4:] == ["--plugin-data", str(tmp_path), "--hold", "F-1"]
        assert ql_research.research_places(None, tmp_path) == (tmp_path, tmp_path / "config.json")
        p = ql_deliver.Pusher(tmp_path / "clone", tmp_path, run, None, print)
        calls.clear()
        p.learn_and_apply(tmp_path / "wt", tmp_path / "wt" / "store", set(), print)
        assert calls[1][-2:] == ["--clone", str(tmp_path / "clone")]


HOST_REFUSALS = {"gitlab-project": GITLAB_PROJECT, "gitlab-protected": GITLAB_PROTECTED,
                 "github-denied": GITHUB_DENIED, "github-gh006": GITHUB_GH006}


class HostCase:
    """A plugin host in mode `auto`: a fake plugins directory whose known_marketplaces.json names a local bare remote
    (a clone of the shared seed, conftest.kb_seed), a data directory with the fixture spool, distill with host_push;
    glab signed out, learn and apply in-process, kbgit.py sync's gate without tests.py (KB_SYNC_NO_TESTS=1). One case
    per test."""

    def run_case(self, case, kb_seed, env, tmp):
        top = Repo(tmp, env)
        bare = Repo(tmp / "remote.git", env)
        top.git("clone", "-q", "--bare", str(kb_seed[0]), bare.path)
        hook = Path(bare.path) / "hooks" / "pre-receive"
        if case in HOST_REFUSALS or case == "push-rule":
            hook.write_text(reject_hook(HOST_REFUSALS.get(case, PUSH_RULE)), encoding="utf-8", newline="\n")
            hook.chmod(0o755)
        if case == "red-gate":  # planted: main on the remote fails check.py (a fact citing no source row)
            planter = Repo(tmp / "planter", env)
            top.git("clone", "-q", bare.path, planter.path)
            planter.append(P("claude/plugins.md"), "- A planted fact. [DOC S-zzzzzzzz]\n")
            planter.git("commit", "-q", "-a", "--no-verify", "-m", "chore: planted")
            planter.git("push", "-q", "origin", "HEAD:main")
        url = UNREACHABLE if case == "unreachable-at-clone" else bare.path
        root = plugins_dir(tmp, {"source": "git", "url": url})
        q = tmp / "data" / "querylog"
        plant_spool(q)

        def run(argv, cwd=None):
            if argv[0] in ("glab", "gh"):
                return signed_out(argv)
            return run_here(argv, cwd=cwd, env=env)
        if case == "unreachable-at-push":  # the fetch works, the push meets a closed port
            clone = ql_deliver.managed_clone(q, bare.path, run, print)
            Repo(clone, env).git("config", "remote.origin.pushurl", UNREACHABLE)
        said = []
        rc = ql_distill.distill(qdir=q, cfg=auto_config(q), haiku=ql_base.Replay(FIXTURES / "haiku.json"),
                                now_dt=NOW, run_id=RUN_ID, kb_commit="0" * 40, out=said.append,
                                deliver=lambda qd, out: ql_deliver.host_push(qd, run, learn_then_apply, out, NOW, root))
        return rc, said, q, bare

    def case(self, case, kb_seed, tmp_path):
        rc, said, q, bare = self.run_case(case, kb_seed, git_env(KB_SYNC_NO_TESTS="1"), tmp_path)
        text = "\n".join(said)
        disabled = q / ql_base.DISABLED_NAME
        base = kb_seed[1]
        if case == "delivers":
            assert rc == 0, text
            assert (q / ql_deliver.CLONE_NAME / ".git").is_dir() and (q / ql_deliver.WORKTREE_NAME / ".git").exists()
            files = bare.git("ls-tree", "-r", "--name-only", "main", "--", ql_base.STORE_REL).split()
            assert f"{ql_base.STORE_REL}/2026-09/{RUN_ID}.jsonl" in files, files
            assert spool_names(q) == [f"{S_OPEN}.jsonl"] and not disabled.exists()
            return
        assert rc == 1, text
        if case == "red-gate":
            assert "gate check.py: FAILED" in text and "kbgit.py sync exit 1: nothing pushed to main" in text, text
        if case in HOST_REFUSALS:
            kind = case.split("-")[0]
            assert disabled.exists(), text
            why = disabled.read_text(encoding="utf-8")
            assert why.startswith("push refused for want of rights on ") and f": {kind}: " in why, why
            assert not (q / "spool").exists(), spool_names(q)
            assert "wrote DISABLED and deleted the spool" in text, text
            again = []
            assert ql_distill.distill(qdir=q, cfg=auto_config(q), out=again.append) == 0
            assert again == ["distill: logging is off"]
        else:
            assert not disabled.exists(), text
            assert set(CLOSED) <= set(spool_names(q)), spool_names(q)
        if case != "red-gate":
            assert bare.rev("main") == base  # nothing pushed
        assert bare.git("for-each-ref", "--format=%(refname)", "refs/heads").split() == ["refs/heads/main"]


@pytest.mark.skipif(not GIT, reason="git is not installed")
@pytest.mark.git
class TestHostInGit(HostCase):
    @pytest.mark.parametrize("case", ["delivers", "unreachable-at-clone", "red-gate"])
    def test_case(self, case, kb_seed, tmp_path):
        self.case(case, kb_seed, tmp_path)


@pytest.mark.skipif(not GIT, reason="git is not installed")
@pytest.mark.git
class TestHostRefusalsInGit(HostCase):
    @pytest.mark.parametrize("case", ["gitlab-project", "gitlab-protected", "github-denied", "github-gh006"])
    def test_case(self, case, kb_seed, tmp_path):
        self.case(case, kb_seed, tmp_path)


@pytest.mark.skipif(not GIT, reason="git is not installed")
@pytest.mark.git
class TestHostNoRefusalInGit(HostCase):
    @pytest.mark.parametrize("case", ["push-rule", "unreachable-at-push"])
    def test_case(self, case, kb_seed, tmp_path):
        self.case(case, kb_seed, tmp_path)


@pytest.mark.skipif(not GIT, reason="git is not installed")
@pytest.mark.git
class TestCloudInGit:
    """A cloud session: a clone on the branch `claude/work` of a bare remote whose pre-receive hook takes pushes to
    that branch only (as the session's git proxy does); distill in mode `auto` with a Pusher told it is a cloud
    session."""

    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def scenario(cls, tmp_path_factory, kb_seed):
        cls.tmp = Path(tmp_path_factory.mktemp("ql-cloud"))
        cls.env = git_env(KB_SYNC_NO_TESTS="1")
        cls.base = kb_seed[1]
        top = Repo(cls.tmp, cls.env)
        cls.bare = Repo(cls.tmp / "remote.git", cls.env)
        top.git("clone", "-q", "--bare", str(kb_seed[0]), cls.bare.path)
        hook = Path(cls.bare.path) / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\nwhile read old new ref; do\n  [ \"$ref\" = refs/heads/claude/work ] || "
                        "{ echo \"push to $ref refused: the session pushes to claude/work only\" >&2; exit 1; }\n"
                        "done\n", encoding="utf-8", newline="\n")
        hook.chmod(0o755)
        cls.a = Repo(cls.tmp / "a", cls.env)
        top.git("clone", "-q", cls.bare.path, cls.a.path)
        cls.a.git("checkout", "-q", "-b", "claude/work")
        cls.q = Path(cls.a.path) / "_cache" / "querylog"
        plant_spool(cls.q)
        cls.first = cls.distill()
        cls.branch1 = cls.bare.rev("claude/work")
        cls.again = cls.distill()
        cls.branch2 = cls.bare.rev("claude/work")
        cls.a.git("checkout", "-q", "--detach")
        cls.detached = []
        cls.detached_rc = ql_deliver.Pusher(cls.a.path, cls.q, cls.runner(), learn_then_apply, cls.detached.append, NOW,
                                            cloud=True)()

    @classmethod
    def runner(cls):
        def run(argv, cwd=None):
            if argv[0] in ("glab", "gh"):
                return signed_out(argv)
            return run_here(argv, cwd=cwd, env=cls.env)
        return run

    @classmethod
    def distill(cls):
        said = []

        def deliver(qdir, out):
            return ql_deliver.Pusher(cls.a.path, qdir, cls.runner(), learn_then_apply, out, NOW, cloud=True)()
        rc = ql_distill.distill(qdir=cls.q, cfg=auto_config(cls.q), haiku=ql_base.Replay(FIXTURES / "haiku.json"),
                                now_dt=NOW, run_id=RUN_ID, kb_commit="0" * 40, out=said.append, deliver=deliver)
        return rc, said

    def test_the_commits_land_on_the_working_branch(self):
        rc, said = self.first
        assert rc == 0, "\n".join(said)
        assert "apply --push: cloud session: automatic commits go to its working branch claude/work" in said
        files = self.bare.git("ls-tree", "-r", "--name-only", "claude/work", "--", ql_base.STORE_REL).split()
        assert f"{ql_base.STORE_REL}/2026-09/{RUN_ID}.jsonl" in files, files
        assert self.bare.rev("main") == self.base
        assert "apply --push: deleted the spool rows of 6 entries whose run file is on origin/claude/work" in said
        assert spool_names(self.q) == [f"{S_OPEN}.jsonl"]

    def test_a_second_run_starts_from_the_branch_and_pushes_nothing(self):
        rc, said = self.again
        assert rc == 0 and "apply --push: nothing to push" in said, said
        assert self.branch2 == self.branch1

    def test_a_detached_head_is_refused(self):
        assert self.detached_rc == 2 and "HEAD is detached" in self.detached[0], self.detached


# ---- the revert's bug carries the failure fingerprint (backlog.py's) and joins an open bug with the same one

def fingerprint_forge(jobs, logs):
    """A signed-in glab stub for the revert's pipeline: its failed jobs and their traces (no network)."""
    def run(argv, cwd=None):
        if argv[1:3] == ["auth", "status"]:
            return 0, "", "Logged in"
        if "/jobs?scope=failed" in argv[-1]:
            return 0, json.dumps(jobs), ""
        m = re.search(r"/jobs/(\d+)/trace$", argv[-1])
        return (0, logs.get(int(m.group(1)), ""), "") if m else (1, "", "unexpected call")
    return run


def fingerprint_pusher(tmp_path, run):
    (tmp_path / "worktree" / "kb" / "_self" / "backlog").mkdir(parents=True)
    return ql_deliver.Pusher(tmp_path, tmp_path / "q", run, None, lambda *_: None, cloud=False)


def test_revert_fingerprint_is_backlogs_and_a_second_pipeline_joins_the_open_bug(tmp_path):
    import backlog
    url = "https://gitlab.example.com/team/kb.git"
    jobs = [{"id": 11, "name": "lint", "status": "failed"}, {"id": 10, "name": "check", "status": "failed"}]
    log = "2026-09-01T10:00:00Z FAILED _tools/test_x.py::test_a - assert 3 == 4\n"
    run = fingerprint_forge(jobs, {10: log, 11: "lint error\n"})
    failure, fp = ql_deliver.pipeline_failure(url, {"id": 901}, run)
    assert failure == "_tools/test_x.py::test_a"
    assert fp == backlog.failure_fingerprint("check", "_tools/test_x.py::test_a")  # the first failed job by name
    pusher = fingerprint_pusher(tmp_path, run)
    pipe = {"id": 901, "url": "https://x/901", "status": "failed", "failure": failure, "fingerprint": fp}
    first = pusher.file_bug("a" * 40, {"F1": {}}, pipe)
    bl = backlog.Backlog(pusher.wt)
    assert list(bl.items) == [first] and bl.items[first]["severity"] == "S2"  # no open bug: exactly one S2 bug
    assert bl.items[first]["links"] == ["pipeline 901", f"fingerprint {fp}"]
    # planted: a later revert's pipeline that fails the same way (other job id, time and numbers) joins that bug
    log2 = "2026-09-03T08:15:42Z FAILED _tools/test_x.py::test_a - assert 7 == 9\n"
    run2 = fingerprint_forge([{"id": 20, "name": "check", "status": "failed"}], {20: log2})
    failure2, fp2 = ql_deliver.pipeline_failure(url, {"id": 902}, run2)
    assert fp2 == fp
    again = pusher.file_bug("b" * 40, {}, {"id": 902, "failure": failure2, "fingerprint": fp2})
    bl = backlog.Backlog(pusher.wt)
    assert again == first and list(bl.items) == [first]  # no second bug
    assert bl.items[first]["links"] == ["pipeline 901", f"fingerprint {fp}", "pipeline 902"]
    assert pusher.file_bug("c" * 40, {}, {"id": 902, "fingerprint": fp}) is None  # the pipeline is already named
    # a different failure files a second bug
    other = pusher.file_bug("d" * 40, {}, {"id": 903, "fingerprint": backlog.failure_fingerprint("check", "other")})
    assert other not in (None, first) and len(backlog.Backlog(pusher.wt).items) == 2


def test_revert_fingerprint_unreadable_pipeline_files_a_bug_without_one(tmp_path):
    import backlog
    url = "https://gitlab.example.com/team/kb.git"
    run = fingerprint_forge([], {})
    assert ql_deliver.pipeline_failure(url, {"id": 5}, run) == ("", None)
    assert ql_deliver.pipeline_failure(url, {}, run) == ("", None)
    pusher = fingerprint_pusher(tmp_path, run)
    bug = pusher.file_bug("e" * 40, {}, {"id": 5, "failure": "", "fingerprint": None})
    assert backlog.Backlog(pusher.wt).items[bug]["links"] == ["pipeline 5"]


def test_revert_fingerprint_of_a_real_forge_log_names_its_first_failing_test(tmp_path):
    """The revert reads recorded real GitLab.com job logs (_tools/fixtures/forge_logs/: timestamps, stream markers,
    CRs and colour codes as the forge sent them): each real failure gets the fingerprint of the test that failed
    first, and two real failures of one job file two bugs, not one (BG-jam2lysj)."""
    import backlog
    url = "https://gitlab.example.com/team/kb.git"
    logs = {}
    for jid, name in ((40, "gitlab-com-kb-tests-windows"), (41, "gitlab-com-kb-tests")):
        doc = json.loads((Path(TOOLS) / "fixtures" / "forge_logs" / f"{name}.json").read_text(encoding="utf-8"))
        logs[jid] = "".join(doc["lines"])
    want = {40: "_tools/test_kb_mcp.py::test_status_says_how_far_an_installed_plugin_is_behind_its_marketplace",
            41: "_tools/test_kb_http.py::test_kb_http_roots_default_serves_public_only"}
    pusher = fingerprint_pusher(tmp_path, fingerprint_forge([], {}))
    filed = []
    for pid, jid in ((911, 40), (912, 41)):
        job = {"id": jid, "name": "kb-tests-windows", "status": "failed", "failure_reason": "script_failure"}
        run = fingerprint_forge([job], logs)
        failure, fp = ql_deliver.pipeline_failure(url, {"id": pid}, run)
        assert failure == want[jid]
        assert fp == backlog.failure_fingerprint("kb-tests-windows", want[jid])
        filed.append(pusher.file_bug(f"{pid:040d}", {}, {"id": pid, "failure": failure, "fingerprint": fp}))
    assert None not in filed and filed[0] != filed[1] and len(backlog.Backlog(pusher.wt).items) == 2
