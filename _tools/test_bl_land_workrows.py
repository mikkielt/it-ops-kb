"""The warning `backlog.py land` gives for an item landed with no work rows (bl_land.ops_no_work_rows, ops_land).

The warning means a worker started without the capture hooks, so it must read every place work rows live: this host's
spool, and the committed work sidecars, where distill moves them (an item line, or a shared line naming the item) and
empties the spool. Planted failures: a consumed spool whose rows are only in the store (no warning), a store and a
spool with nothing of the item (the warning), another item's rows, and a sidecar that breaks the store's work gates
(read as nothing, so the warning still fires). The patches name the module where the code looks the name up,
`ql_capture`.
"""
import json
from pathlib import Path

import pytest

import backlog
import bl_land
import bl_testkit
import ql_capture
import ql_store

bl_testkit.bind(backlog)

repo, sprint, no_git_location, gate_jobs = bl_testkit.repo, bl_testkit.sprint, bl_testkit.no_git_location, bl_testkit.gate_jobs

RUN = "20261001T100000Z-aaaaaaaa"
USAGE = {"requests": 1, "in": 1, "cw": 0, "cw1h": 0, "cr": 0, "out": 1}
MODEL = "claude-sonnet-4-6"
WARNING = "landed with no work rows"


@pytest.fixture
def spool(tmp_path_factory, monkeypatch):
    """This test's own spool, empty (what distill leaves): never the clone's."""
    d = tmp_path_factory.mktemp("querylog") / "spool"
    d.mkdir()
    monkeypatch.setattr(ql_capture, "spool_dir", lambda: d)
    return d


def plant_work_row(spool, item_id, action="claim", n=1):
    row = {"id": f"{n:08x}-1111-4111-8111-111111111111", "ts": "2026-10-01T10:00:00.000Z", "surface": "work", "v": 1,
           "session_id": "s1", "prompt_id": "p1", "item": item_id, "action": action}
    with open(spool / "tools-2026-10-01.jsonl", "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(row) + "\n")


def plant_sidecar(repo, lines, run=RUN):
    """A work sidecar in the clone's committed store, written with the store's own writer."""
    path = ql_store.write_work(Path(repo) / "kb" / "_querylog", run, lines, 0, 1)
    assert path is not None and path.is_file()
    return path


def item_line(item_id):
    return {"item": item_id, "prompts": 1, "main": {MODEL: dict(USAGE)}}


def shared_line(*ids):
    return {"items": list(ids), "prompts": 1, "main": {MODEL: dict(USAGE)}}


def landed(repo, iid, capsys):
    """What `land` of the item prints when it returns 0: the wrapped handler's output."""
    wrapped = bl_land.ops_land(lambda bl, a: 0)
    code = wrapped(backlog.Backlog(repo), type("A", (), {"id": iid})())
    assert code == 0
    return capsys.readouterr().out


def test_no_work_rows_after_distill(sprint, spool, capsys):
    """Distill consumed the spool: the rows are in the store only, and the landing says nothing; with no row in either
    place the same landing warns."""
    repo, tk, st = sprint["repo"], sprint["tk"], sprint["st"]
    assert bl_land.ops_no_work_rows(repo, tk) is True and WARNING in landed(repo, tk, capsys)  # planted: nowhere
    plant_sidecar(repo, [item_line(tk)])
    assert bl_land.ops_no_work_rows(repo, tk) is False
    assert WARNING not in landed(repo, tk, capsys)
    assert '"surface": "work"' not in "".join(f.read_text(encoding="utf-8") for f in spool.glob("*.jsonl"))  # only the store
    assert bl_land.ops_no_work_rows(repo, st) is False  # a descendant's line counts for its story, as a spool row does
    assert WARNING not in landed(repo, st, capsys)


@pytest.mark.parametrize("planted", ["item", "shared", "descendant"])
def test_no_work_rows_after_distill_every_kind_of_line(sprint, spool, planted):
    """An item line, a shared line that names the item among others, and a descendant's line each count."""
    repo, tk, st, bg = sprint["repo"], sprint["tk"], sprint["st"], sprint["bg"]
    assert bl_land.ops_no_work_rows(repo, st) is True
    plant_sidecar(repo, [{"item": item_line(st), "shared": shared_line(bg, st), "descendant": item_line(tk)}[planted]])
    assert bl_land.ops_no_work_rows(repo, st) is False


def test_no_work_rows_after_distill_other_items_rows_do_not_count(sprint, spool):
    """Planted failure: the store and the spool hold rows of the bug only, so the task still has none."""
    repo, tk, bg = sprint["repo"], sprint["tk"], sprint["bg"]
    plant_sidecar(repo, [item_line(bg), shared_line(bg)])
    plant_work_row(spool, bg)
    assert bl_land.ops_no_work_rows(repo, tk) is True
    assert bl_land.ops_no_work_rows(repo, bg) is False


def test_no_work_rows_after_distill_spool_rows_still_count(sprint, spool):
    """Rows not distilled yet (in the spool, none in the store) are still work rows; so is each action; a refused done
    is not one."""
    repo, tk = sprint["repo"], sprint["tk"]
    plant_work_row(spool, tk, "refused")
    assert bl_land.ops_no_work_rows(repo, tk) is True
    for n, action in enumerate(ql_capture.WORK_ACTIONS, 2):
        (spool / "tools-2026-10-01.jsonl").unlink(missing_ok=True)
        plant_work_row(spool, tk, action, n)
        assert bl_land.ops_no_work_rows(repo, tk) is False, action


def test_no_work_rows_after_distill_broken_sidecar_is_read_as_nothing(sprint, spool):
    """Planted failure: a sidecar that breaks the store's work gates is skipped whole by the store's reader, so the
    warning still fires and nothing raises."""
    repo, tk = sprint["repo"], sprint["tk"]
    path = plant_sidecar(repo, [item_line(tk)])
    objs = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines()]
    objs[1]["prompts"] = "many"
    path.write_text("".join(json.dumps(o) + "\n" for o in objs), encoding="utf-8", newline="\n")
    assert bl_land.ops_no_work_rows(repo, tk) is True
    path.write_bytes(b"\xff\xfe not json")
    assert bl_land.ops_no_work_rows(repo, tk) is True


def test_no_work_rows_after_distill_capture_off_says_nothing(sprint, monkeypatch):
    """With capture off there is no spool to judge by: no warning, as before, store or none."""
    repo, tk = sprint["repo"], sprint["tk"]
    monkeypatch.setattr(ql_capture, "spool_dir", lambda: None)
    assert bl_land.ops_no_work_rows(repo, tk) is False
