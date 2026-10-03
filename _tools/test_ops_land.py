"""land's ops rows (bl_land.py; kb/_self/tools.md, backlog.py land): `backlog.py land` appends one `land.step` row per
step it runs (item, step token, exit, milliseconds) and one `land.end` row at every end (item, exit, total, lane), and
warns when the item has no `work` row in this host's spool or in the committed work sidecars
(`kb/_querylog/work`).

  ops_land_rows                              a content landing writes a row for fetch, rebase, done and the sync
                                             step, then `land.end` with lane content and exit 0; a stop at a heavy
                                             step writes its row with the step's own exit, no row for a step after
                                             it, and `land.end` exit 1 (planted: LAND_FAIL); a code item's first run
                                             ends with lane code; an early stop (a dirty tree) writes only `land.end`
  ops_land_rows_capture_failure_changes_nothing
                                             a spool that cannot be written, and a capture that raises, leave land's
                                             exit and output as they were
  land_warns_when_item_has_no_work_rows      the warning line after a landing with no work row of the item, none with
                                             one (planted: the same landing with a claim row in the spool), exit 0
                                             either way

The landing fixture is test_bl_land.py's (a throwaway clone with a bare remote and stub steps). Every run writes under
a temporary plugin data directory, never the clone's own spool.
"""
import json

import pytest

import backlog
import bl_land
import bl_testkit
import ql_capture
import test_bl_land
from conftest import KB, querylog_env

bl_testkit.bind(backlog)
repo, sprint, no_git_location, gate_jobs = bl_testkit.repo, bl_testkit.sprint, bl_testkit.no_git_location, bl_testkit.gate_jobs

WARNING = "landed with no work rows"


ROW_ID = "-".join(("5d0f6c1e", "0000", "4000", "8000", "000000000001"))  # built from parts: this file holds no GUID

class TestOpsLand:
    CO = test_bl_land.TestBacklogLand.CO
    out = staticmethod(test_bl_land.TestBacklogLand.out)
    landing = test_bl_land.TestBacklogLand.landing
    work = test_bl_land.TestBacklogLand.work
    land = test_bl_land.TestBacklogLand.land

    @pytest.fixture(autouse=True)
    def own_spool(self, tmp_path_factory, monkeypatch):
        data = tmp_path_factory.mktemp("qldata")
        for k in ("CLAUDE_PLUGIN_ROOT", "CLAUDE_PLUGIN_DATA"):
            monkeypatch.setenv(k, querylog_env(data, home=KB)[k])
        self.spool = data / "querylog" / "spool"

    def rows(self, event=None):
        out = [json.loads(ln) for f in sorted(self.spool.glob("*.jsonl")) for ln in f.read_text(encoding="utf-8").splitlines()]
        return [r for r in out if r["surface"] == "ops" and event in (None, r["event"])]

    def plant_work_row(self, tk):
        self.spool.mkdir(parents=True, exist_ok=True)
        row = {"id": ROW_ID, "ts": "2026-09-28T12:00:00Z", "surface": "work", "v": 1,
               "session_id": "s1", "item": tk, "action": "claim"}
        (self.spool / "s1.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")

    def test_ops_land_rows_content_item(self, landing):
        ld = landing
        self.work(ld, ["kb/public/x/a.md"], "kb/public/x/a.md")
        code, out = self.land(ld)
        assert code == 0 and "landed" in out, out
        steps = self.rows("land.step")
        assert [(r["step"], r["exit"]) for r in steps] == [("fetch", 0), ("rebase", 0), ("done", 0),
                                                           ("kbgit.py-sync-push", 0)]
        assert all(r["item"] == ld["tk"] and isinstance(r["ms"], int) and "session_id" not in r for r in steps)
        (end,) = self.rows("land.end")
        assert (end["item"], end["exit"], end["lane"]) == (ld["tk"], 0, "content") and isinstance(end["ms"], int)

    def test_ops_land_rows_stop_at_a_failing_step(self, landing, monkeypatch):
        ld = landing
        self.work(ld, ["_tools/b.py", "src/b.txt"], "src/b.txt")
        monkeypatch.setenv("LAND_FAIL", "rag.py eval")  # planted
        code, out = self.land(ld)
        assert code == 1 and "land stopped at step rag.py eval" in out, out
        assert [(r["step"], r["exit"]) for r in self.rows("land.step")] == [
            ("fetch", 0), ("rebase", 0), ("stress_test.py", 0), ("rag.py-eval", 1)]
        (end,) = self.rows("land.end")
        assert (end["exit"], end["lane"]) == (1, "code")

    def test_ops_land_rows_code_item_first_run_has_lane_code(self, landing):
        ld = landing
        self.work(ld, ["_tools/b.py", "src/b.txt"], "src/b.txt")
        code, out = self.land(ld)
        assert code == 0 and "not done yet" in out, out
        (end,) = self.rows("land.end")
        assert (end["exit"], end["lane"]) == (0, "code")
        assert self.rows("land.step")[-1]["step"] == "kbgit.py-sync-push"

    def test_ops_land_rows_early_stop_writes_only_the_end_row(self, landing):
        ld = landing
        self.work(ld, ["kb/public/x/a.md"], "kb/public/x/a.md")
        (ld["repo"] / "dirty.txt").write_text("x\n", encoding="utf-8")  # planted: an uncommitted file
        code, out = self.land(ld)
        assert code == 1 and "land stopped at step clean tree" in out, out
        assert self.rows("land.step") == []
        (end,) = self.rows("land.end")
        assert end["exit"] == 1 and "lane" not in end

    def test_ops_land_rows_capture_failure_changes_nothing(self, landing, monkeypatch, capsys):
        ld = landing
        self.work(ld, ["kb/public/x/a.md"], "kb/public/x/a.md")
        blocked = ld["repo"].parent / "not-a-dir"
        blocked.write_text("file\n", encoding="utf-8")
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(blocked))  # no spool can be made here
        code, out = self.land(ld)
        assert code == 0 and "landed" in out and WARNING not in out, out
        sh_raise = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("capture broke"))  # noqa: E731
        monkeypatch.setattr(ql_capture, "record", sh_raise)
        monkeypatch.setattr(ql_capture, "spool_dir", sh_raise)
        bl_land.LAND_OPS.update(step="fetch", item=ld["tk"])
        bl_land.ops_close()  # a raising capture is swallowed
        assert bl_land.ops_no_work_rows(ld["repo"], ld["tk"]) is False

    def test_land_warns_when_item_has_no_work_rows(self, landing):
        ld = landing
        self.work(ld, ["kb/public/x/a.md"], "kb/public/x/a.md")
        code, out = self.land(ld)
        assert code == 0 and "landed" in out, out
        assert f"warning: {ld['tk']} {WARNING} (a worker started without the capture hooks?)" in out, out

    def test_a_work_row_silences_land_warns_when_item_has_no_work_rows(self, landing):
        ld = landing
        self.work(ld, ["kb/public/x/a.md"], "kb/public/x/a.md")
        self.plant_work_row(ld["tk"])  # planted: the same landing with a claim row
        code, out = self.land(ld)
        assert code == 0 and "landed" in out and WARNING not in out, out
