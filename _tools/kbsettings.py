#!/usr/bin/env python3
"""The coordination settings (stdlib only): defaults, a workspace's settings.json, a kb root's settings.json.

  kbsettings.py show --root WS [--kb-root NAME] [--json]   print the effective coordination settings

`effective(root, kb_root=None)` is the one reader: the coord hook, kbmon and the explain command call it, never the
files. It merges key by key, later over earlier: DEFAULTS, then `<WS>/settings.json`, then
`<WS>/kb/<NAME>/settings.json` when a kb root is named. A file holds `{"coordination": {"announce": {...},
"strategy": {...}}}`; a missing file is no error, and a key of another top-level object is not read. An unknown key,
or a value outside its closed set, raises `SettingsError` (a ValueError whose message names the file, the key and the
allowed values); `show` prints it on stderr and exits 2. Exit 0 printed; 2 a bad setting or argument.

announce (what a session says about its work):
  when                 list of start, claim, midrun, edit: the moments a session announces itself
  to_other_sessions    true or false: tell the other sessions on the clone
  operator             list of terminal, kbmon, needs_you: where the operator is told
  needs_you_after_min  whole minutes (0 or more) an open question waits before it shows as needing the operator
strategy (what a session does when another item is in the state the key names):
  working, landing, blocked, returned   the other item's run state
  same_item                             another session already holds the same item
  each one of wait, ask, after, join, proceed
  decide               operator or claude: who picks the strategy when none of the above settles it
"""
import argparse, json, sys
from pathlib import Path

STRATEGIES = ("wait", "ask", "after", "join", "proceed")
RUN_STATES = ("working", "landing", "blocked", "returned")

DEFAULTS = {
    "announce": {
        "when": ["start", "claim"],
        "to_other_sessions": True,
        "operator": ["terminal", "kbmon"],
        "needs_you_after_min": 10,
    },
    "strategy": {
        "same_item": "ask",
        "working": "ask",
        "landing": "wait",
        "blocked": "proceed",
        "returned": "proceed",
        "decide": "operator",
    },
}

# key -> ("list", allowed) | ("one", allowed) | ("bool",) | ("minutes",)
SCHEMA = {
    "announce": {
        "when": ("list", ("start", "claim", "midrun", "edit")),
        "to_other_sessions": ("bool",),
        "operator": ("list", ("terminal", "kbmon", "needs_you")),
        "needs_you_after_min": ("minutes",),
    },
    "strategy": {
        **{k: ("one", STRATEGIES) for k in ("same_item", *RUN_STATES)},
        "decide": ("one", ("operator", "claude")),
    },
}


class SettingsError(ValueError):
    """A settings file that holds an unknown key or a value outside its closed set."""


def _valid(kind, value):
    if kind[0] == "bool":
        return isinstance(value, bool)
    if kind[0] == "minutes":
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0
    if kind[0] == "one":
        return isinstance(value, str) and value in kind[1]
    return isinstance(value, list) and len(set(map(str, value))) == len(value) and all(
        isinstance(v, str) and v in kind[1] for v in value)


def _allowed(kind):
    if kind[0] == "bool":
        return "true or false"
    if kind[0] == "minutes":
        return "a whole number of minutes, 0 or more"
    return ("a list of " if kind[0] == "list" else "one of ") + ", ".join(kind[1])


def _read(path):
    """The validated `coordination` object of PATH; empty when the file is missing."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as e:
        raise SettingsError(f"{path}: cannot read: {e}")
    try:
        data = json.loads(text)
    except ValueError as e:
        raise SettingsError(f"{path}: not JSON: {e}")
    if not isinstance(data, dict):
        raise SettingsError(f"{path}: the file must hold a JSON object")
    coord = data.get("coordination", {})
    if not isinstance(coord, dict):
        raise SettingsError(f"{path}: key coordination must be an object")
    for group, body in coord.items():
        if group not in SCHEMA:
            raise SettingsError(f"{path}: unknown key coordination.{group}; allowed: {', '.join(SCHEMA)}")
        if not isinstance(body, dict):
            raise SettingsError(f"{path}: key coordination.{group} must be an object")
        for key, value in body.items():
            kind = SCHEMA[group].get(key)
            if kind is None:
                raise SettingsError(f"{path}: unknown key coordination.{group}.{key}; allowed: "
                                    f"{', '.join(SCHEMA[group])}")
            if not _valid(kind, value):
                raise SettingsError(f"{path}: key coordination.{group}.{key} has value {json.dumps(value)}; "
                                    f"allowed: {_allowed(kind)}")
    return coord


def effective(root, kb_root=None):
    """`{"coordination": {"announce": {...}, "strategy": {...}}}` for workspace ROOT and the kb root named KB_ROOT."""
    root = Path(root)
    files = [root / "settings.json"] + ([root / "kb" / kb_root / "settings.json"] if kb_root else [])
    merged = json.loads(json.dumps(DEFAULTS))
    for path in files:
        for group, body in _read(path).items():
            merged[group].update(body)
    return {"coordination": merged}


def _text(settings):
    lines = []
    for group, body in settings["coordination"].items():
        lines.append(group)
        lines += [f"  {key}: {json.dumps(value) if not isinstance(value, str) else value}"
                  for key, value in body.items()]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="The coordination settings: defaults, workspace and kb root files.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sh = sub.add_parser("show", help="print the effective coordination settings")
    sh.add_argument("--root", required=True, help="the workspace directory (holds settings.json and kb/)")
    sh.add_argument("--kb-root", help="a kb root's name: kb/NAME/settings.json overrides the workspace's")
    sh.add_argument("--json", action="store_true", help="print one JSON object")
    args = ap.parse_args(argv)
    try:
        settings = effective(args.root, args.kb_root)
    except SettingsError as e:
        print(f"kbsettings: {e}", file=sys.stderr)
        return 2
    print(json.dumps(settings, indent=2, sort_keys=True) if args.json else _text(settings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
