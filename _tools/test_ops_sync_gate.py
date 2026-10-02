"""The ops row `sync.gate` of `kbgit.py sync` (`python3 _tools/tests.py -k ops_sync_gate_row`): one row for each sync run
that ran a gate, with each check's name, ran flag, skip reason, exit and ms, the tests scope, the count of paths the gate
read and the push outcome; printed once as `gate scope:` in the sync report. The row is best effort: a capture failure
changes neither sync's exit nor its output.

  unit (no git)    the check-name token, the scope tokens over the tests.py outputs, the push outcome and the closed row
  scenario (git)   a real `sync --push` of a clone against a throwaway remote, the row read from the clone's own spool;
                   planted: a spool that cannot be written leaves the exit and the report as they were, with no row
"""
import json, os

import pytest

import kbid, kg_sync, ql_capture
from conftest import Repo, git_env, requires_git
from test_sync import SyncScenario, clones

URL = "https://learn.microsoft.com/en-us/sync-test/ops-gate-a"
TAIL = {"gate_rows": [{"name": "check.py", "ran": True, "exit": 0, "ms": 5}], "gate_ms": 7, "gate_files": 3}


@pytest.fixture
def spool(tmp_path, monkeypatch):
    """ql_capture writes under tmp_path, never the real spool."""
    monkeypatch.setattr(ql_capture, "places", lambda: (tmp_path / "ql", tmp_path / "ql" / "config.json"))
    ql_capture.spool_dir.cache_clear()
    yield tmp_path / "ql" / "spool"
    ql_capture.spool_dir.cache_clear()


def spooled(spool_dir):
    return [json.loads(ln) for f in sorted(spool_dir.glob("*.jsonl")) for ln in f.read_text(encoding="utf-8").splitlines()]


def test_ops_sync_gate_row_check_names_are_tokens_without_a_revision():
    labels = ["kbgit.py fix --check", "build_index.py --check", "check.py", "fetch.py --offline", "doc2query.py stale",
              "selfdoc.py stale --since abc1234", "tests.py (changed)", "tests.py (fast)", "check-trailers origin/main..HEAD",
              "check-trailers HEAD", "x" * 80, "!!"]
    for label in labels:
        name = kg_sync.gate_name(label)
        assert ql_capture.OPS_TOKEN.fullmatch(name), (label, name)
    assert kg_sync.gate_name("selfdoc.py stale --since abc1234") == "selfdoc.py-stale"
    assert kg_sync.gate_name("check-trailers origin/main..HEAD") == "check-trailers"
    assert kg_sync.gate_name("tests.py (changed)") == "tests.py-changed"


def test_ops_sync_gate_row_scope_tokens_follow_what_tests_py_printed():
    cases = [("tests.py --changed origin/main: 12 of 340 test files or classes\n", "changed"),
             ("tests.py --changed origin/main: 12 of 340 test files or classes, the git scenarios of 3 kept\n", "changed-git"),
             ("tests.py --changed origin/main: no test can be affected by the changed paths (testmap.py explain)\n", "none"),
             ("..... 55 passed\n", "all")]
    for out, want in cases:
        r = {}
        kg_sync.gate_scope(r, None, out)
        assert r["scope"] == want and ql_capture.OPS_TOKEN.fullmatch(r["scope"]) and r["scope_line"], (out, r)
    for why, want in (("no-tests-env", "skipped"), ("no-path-changed", "none")):
        r = {}
        kg_sync.gate_scope(r, why, "")
        assert r["scope"] == want, r


def test_ops_sync_gate_row_push_outcome_exit_and_shape(spool):
    for pushed, want in (("yes: 1 commit(s) to origin/main (abc1234)", "pushed"), ("no (rejected 3 times)", "rejected"),
                         ("no (without --push)", "none"), ("no (push failed)", "none"), ("nothing to push", "none")):
        row = kg_sync.record_gate({**TAIL, "scope": "changed", "pushed": pushed}, 1)
        assert row["push"] == want and row["exit"] == 1 and row["scope"] == "changed" and row["files"] == 3, row
        assert row["ms"] == 7 and row["checks"] == TAIL["gate_rows"] and not ql_capture.ops_problems(
            {k: v for k, v in row.items() if k not in ("id", "ts", "surface", "v")}), row
    assert len(spooled(spool)) == 5
    assert kg_sync.record_gate({"pushed": "no"}, 0) is None  # no gate ran: no row


def test_ops_sync_gate_row_a_capture_failure_raises_nothing(monkeypatch):
    monkeypatch.setattr(ql_capture, "record", lambda *a, **k: 1 / 0)
    assert kg_sync.record_gate({**TAIL, "pushed": "no"}, 0) is None


def test_ops_sync_gate_row_more_checks_than_the_event_takes_are_cut_not_refused(spool):
    r = {"gate_rows": [{"name": "check.py", "ran": True, "exit": 0, "ms": 1}] * 41, "gate_ms": 1, "pushed": "no"}
    row = kg_sync.record_gate(r, 0)
    assert row is not None and len(row["checks"]) == 40 and len(spooled(spool)) == 1


@requires_git
@pytest.mark.git
class TestOpsSyncGateRowInGit(SyncScenario):
    """`sync --push` of clone A (the gate's tests.py skipped: no recursive test run) against a bare remote."""

    @pytest.fixture
    def world(self, tmp_path, kb_seed):
        env = git_env(KB_SYNC_NO_TESTS="1", KB_SYNC_PUSH_PAUSE_S="0")
        remote, (a,), base = clones(kb_seed, str(tmp_path), env, ("a",))
        self.add_source(a, "S-", URL, "ops-gate-a")
        self.article(a, "ops-gate-a", [kbid.source_id(URL)], ["Ops gate fact."])
        self.commit(a, "docs(kb): ops gate row test")
        return a

    @staticmethod
    def spool_of(a):
        return os.path.join(a.path, "_cache", "querylog", "spool")

    def rows(self, a):
        d = self.spool_of(a)
        out = []
        for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            with open(os.path.join(d, f), encoding="utf-8") as fh:
                out += [json.loads(ln) for ln in fh if ln.strip()]
        return [r for r in out if r.get("event") == "sync.gate"]

    def test_ops_sync_gate_row_one_row_per_sync_with_checks_scope_and_push(self, world):
        r = world.kbgit("sync", "--push")
        assert r.returncode == 0, r.stdout + r.stderr
        rows = self.rows(world)
        assert len(rows) == 1, rows
        row = rows[0]
        by = {c["name"]: c for c in row["checks"]}
        assert row["surface"] == "ops" and row["push"] == "pushed" and row["exit"] == 0 and row["scope"] == "skipped", row
        assert row["files"] >= 2 and isinstance(row["ms"], int), row
        assert by["check.py"]["ran"] is True and by["check.py"]["exit"] == 0 and by["check.py"]["ms"] >= 0, by
        assert by["querylog.py-check"] == {"name": "querylog.py-check", "ran": False, "why": "no-path-changed"}, by
        assert by["tests.py-changed"]["ran"] is False and by["tests.py-changed"]["why"] == "no-tests-env", by
        assert by["check-trailers"]["ran"] is True and by["check-trailers"]["exit"] == 0, by
        assert r.stdout.count("gate scope:") == 1 and "gate scope: skipped (" in r.stdout, r.stdout
        assert ql_capture.ops_problems({k: v for k, v in row.items() if k not in ("id", "ts", "surface", "v")}) == []

    def test_ops_sync_gate_row_planted_unwritable_spool_leaves_exit_and_report_unchanged(self, world, tmp_path):
        """Planted: the spool path is a file, so no row can be written: sync still exits 0, pushes and reports as before."""
        os.makedirs(os.path.dirname(self.spool_of(world)), exist_ok=True)
        with open(self.spool_of(world), "w", encoding="utf-8") as f:
            f.write("not a directory\n")
        r = world.kbgit("sync", "--push")
        assert r.returncode == 0, r.stdout + r.stderr
        assert "pushed: yes" in r.stdout and "gate scope: skipped (" in r.stdout and "Traceback" not in r.stdout + r.stderr
        assert self.rows(world) == []
        assert Repo(os.path.join(str(tmp_path), "remote.git"), world.env).git("rev-parse", "main").strip() == world.rev("HEAD")
