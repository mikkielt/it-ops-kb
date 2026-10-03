"""Intake's drift detector counts an item whose check is not one of its read-only forms apart from one whose check runs
the whole suite: `Drift.refused` and its own note line, never the heavy count (kb/_self/backlog.md)."""
import bl_intake


def plant(monkeypatch, found):
    ran = []
    monkeypatch.setattr(bl_intake, "check_result", lambda root, c, t: ran.append(c) or "pass")
    monkeypatch.setattr(bl_intake, "eligible", lambda root, items: found)
    monkeypatch.setattr(bl_intake, "rotation", lambda root: 0)
    monkeypatch.setattr(bl_intake, "read_cursor", lambda root: None)
    return ran


FOUND = [("BG-aaaaaaaa", [{"run": ["python3", "_tools/tests.py"]}]),  # the whole suite: heavy
         ("BG-bbbbbbbb", [{"run": ["python3", "_tools/backlog.py", "check"]}]),  # not a read-only form: refused
         ("BG-cccccccc", [{"run": ["python3", "_tools/check.py"]}])]  # runs


def test_drift_refused_apart_from_heavy(tmp_path, monkeypatch):
    ran = plant(monkeypatch, FOUND)
    drift = bl_intake.Drift()
    bl_intake.passing_open(str(tmp_path), {}, 30, drift, 60)
    assert drift.heavy == ["BG-aaaaaaaa"] and drift.refused == ["BG-bbbbbbbb"]
    assert [c["run"] for c in ran] == [["python3", "_tools/check.py"]] and drift.passing == {"BG-cccccccc": 1}


def test_drift_refused_apart_from_heavy_in_the_notes(tmp_path, monkeypatch):
    plant(monkeypatch, FOUND)
    monkeypatch.setattr(bl_intake, "stale_doing", lambda root, items, hours: {})
    monkeypatch.setattr(bl_intake, "load_items", lambda root: {})
    monkeypatch.setattr(bl_intake, "write_cursor", lambda root, last: None)
    notes = bl_intake.drift_detector(str(tmp_path))[0].notes
    heavy = next(n for n in notes.split("; ") if "whole test suite" in n)
    refused = next(n for n in notes.split("; ") if "drift does not run" in n)
    assert heavy.startswith("1 item(s)") and refused.startswith("1 item(s)") and "BG-bbbbbbbb" in refused
    assert "BG-bbbbbbbb" not in heavy
