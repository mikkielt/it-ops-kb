"""An open item's repro and checks run without a shell (kb/_self/backlog.md): every `run` of a todo, draft or doing
item in kb/_self/backlog/ is a form `bl_intake.check_program_refusal` admits (python3 on a `_tools/` script or inline),
never `sh -c`, `git grep` or `grep`, so it runs the same way on every host.

Planted failure: a repro of `sh -c true` is refused, so the assertion over the real items would fail on it."""
import json
from pathlib import Path

import bl_intake

ROOT = Path(__file__).resolve().parent.parent
OPEN = ("todo", "draft", "doing")


def open_runs():
    """(item id, which part, run argv) for each repro and each check with a run of every open item."""
    out = []
    for path in sorted((ROOT / "kb" / "_self" / "backlog").glob("*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        if item.get("status") not in OPEN:
            continue
        parts = [("repro", item.get("repro"))] + [("check", c) for c in item.get("checks") or []]
        for name, part in parts:
            if isinstance(part, dict) and part.get("run"):
                out.append((item.get("id", path.stem), name, part["run"]))
    return out


def refused(runs):
    return [(i, n, bl_intake.check_program_refusal(r)) for i, n, r in runs if bl_intake.check_program_refusal(r)]


def test_open_repros_run_headless():
    assert refused(open_runs()) == []
    assert refused([("BG-planted", "repro", ["sh", "-c", "true"])])
