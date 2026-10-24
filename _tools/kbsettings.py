#!/usr/bin/env python3
"""The coordination settings (stdlib only): defaults, a workspace's settings.json, a kb root's settings.json.

  kbsettings.py show --root WS [--kb-root NAME] [--json]            print the effective coordination settings
  kbsettings.py explain [KEY] --root WS [--kb-root NAME] [--json]   each setting (or KEY) with its value, the file that
                                                                    set it, its meaning and the doc line that states it
  kbsettings.py init --root WS [--set KEY=VALUE]...                 write the coordination section of <WS>/settings.json
                                                                    and turn the coord hook on in <WS>/backlog.json
  kbsettings.py check                                               exit 1 when the table below and the doc disagree

`effective(root, kb_root=None)` is the one reader: the coord hook, kbmon and the explain command call it, never the
files. It merges key by key, later over earlier: DEFAULTS, then `<WS>/settings.json`, then
`<WS>/kb/<NAME>/settings.json` when a kb root is named. A file holds `{"coordination": {"announce": {...},
"strategy": {...}}}`; a missing file is no error, and a key of another top-level object is not read. An unknown key,
or a value outside its closed set, raises `SettingsError` (a ValueError whose message names the file, the key and the
allowed values); `show` and `explain` print it on stderr and exit 2. Exit 0 printed; 1 `check` found a mismatch; 2 a
bad setting or argument. `explain` reads the settings files and the SETTINGS table and nothing else: no model, no
subprocess, no network, and not the doc, whose line numbers the table holds and `check` verifies.

`init` writes the whole `coordination` section: each key the file already holds keeps its value, each `--set KEY=VALUE`
(KEY as `group.name`; a list as comma-separated values, `start,claim`) sets one, and a key neither names takes its
default. Another top-level key of `settings.json` is kept. It adds `coord` to the `hooks` list of `<WS>/backlog.json`
(made with that list alone when the file is missing). A file whose content would not change is not written, so a second
run with the same values changes nothing.

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
import argparse, json, re, sys
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


DOC = "kb/_self/coordination.md"
# key -> (meaning in plain words, line of DOC that states the rule). The one place the meaning text lives: `explain`
# prints it and the doc's Settings section says the same in its own words (`check` compares the key, the default and
# the allowed values of each line).
SETTINGS = {
    "announce.when": ("The moments a session tells the other sessions and the operator what it is working on: when it "
                      "starts, when it claims an item, in the middle of a run, or on each edit.", 168),
    "announce.to_other_sessions": ("Whether a session announces its work to the other sessions on the clone, so they "
                                   "can see it before they touch the same item or files.", 169),
    "announce.operator": ("Where the operator is told about a session's work: in the terminal, on the kbmon panels, "
                          "or as a needs-you alert.", 170),
    "announce.needs_you_after_min": ("How many whole minutes an open question may wait before it shows as needing "
                                     "the operator.", 171),
    "strategy.same_item": ("What a session suggests when another session already holds the item it was about to take.",
                           172),
    "strategy.working": ("What a session suggests when another item that touches the same files is in the run state "
                         "working (a worker is running it).", 173),
    "strategy.landing": ("What a session suggests when another item that touches the same files is being landed.", 174),
    "strategy.blocked": ("What a session suggests when another item that touches the same files is blocked on a gate.",
                         175),
    "strategy.returned": ("What a session suggests when another item that touches the same files has returned from its "
                          "worker and waits to land.", 176),
    "strategy.decide": ("Who picks the strategy when none of the keys above settles it: the operator or the "
                        "session itself.", 177),
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


def _layers(root, kb_root=None):
    """[(path, coordination object)] for the workspace file, then the kb root's, validated; a missing file is {}."""
    root = Path(root)
    if kb_root is not None and not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", str(kb_root)):
        raise SettingsError(f"kb root name {str(kb_root)!r}: a plain directory name is expected")
    files = [root / "settings.json"] + ([root / "kb" / kb_root / "settings.json"] if kb_root else [])
    return [(path, _read(path)) for path in files]


def effective(root, kb_root=None):
    """`{"coordination": {"announce": {...}, "strategy": {...}}}` for workspace ROOT and the kb root named KB_ROOT."""
    merged = json.loads(json.dumps(DEFAULTS))
    for _, coord in _layers(root, kb_root):
        for group, body in coord.items():
            merged[group].update(body)
    return {"coordination": merged}


def explain(root, kb_root=None, key=None):
    """[{key, value, source, meaning, doc}] for each setting of `effective`, or for KEY alone (`group.name`): source is
    the file whose layer set the value last, or "default"; doc is `kb/_self/coordination.md:LINE`."""
    if key is not None and key not in SETTINGS:
        raise SettingsError(f"unknown key {key}; allowed: {', '.join(SETTINGS)}")
    value, source = {}, {}
    for group, body in DEFAULTS.items():
        for name, v in body.items():
            value[f"{group}.{name}"], source[f"{group}.{name}"] = json.loads(json.dumps(v)), "default"
    for path, coord in _layers(root, kb_root):
        for group, body in coord.items():
            for name, v in body.items():
                value[f"{group}.{name}"], source[f"{group}.{name}"] = v, str(path)
    return [{"key": k, "value": value[k], "source": source[k], "meaning": SETTINGS[k][0],
             "doc": f"{DOC}:{SETTINGS[k][1]}"} for k in SETTINGS if key in (None, k)]


def explain_text(rows):
    """ROWS of `explain` as lines: key = value (source), the meaning, the doc line."""
    out = []
    for r in rows:
        value = r["value"] if isinstance(r["value"], str) else json.dumps(r["value"])
        out += [f"{r['key']} = {value}  (source: {r['source']})", f"  {r['meaning']}", f"  doc: {r['doc']}"]
    return "\n".join(out)


def check(doc_text):
    """Problems between SETTINGS and the text of DOC: each key's line must hold the key, the words "Default:" and the
    default, and every allowed value of its closed set; one message per mismatch, empty when they agree."""
    lines, problems = doc_text.splitlines(), []
    if set(SETTINGS) != {f"{g}.{k}" for g, body in SCHEMA.items() for k in body}:
        problems.append("SETTINGS and SCHEMA do not name the same keys")
    for key, (_, number) in SETTINGS.items():
        group, name = key.split(".")
        line = lines[number - 1] if 0 < number <= len(lines) else ""
        kind, default = SCHEMA[group][name], DEFAULTS[group][name]
        shown = ", ".join(default) if isinstance(default, list) else json.dumps(default).strip('"')
        wants = [f"`{key}`", f"Default: `{shown}`"] + [f"`{v}`" for v in (kind[1] if len(kind) > 1 else ())]
        missing = [w for w in wants if w not in line]
        if missing:
            problems.append(f"{DOC}:{number}: the line for {key} lacks {', '.join(missing)}")
    return problems


def _parse_set(item):
    """(group, name, value) of one `group.name=VALUE` argument; a list takes comma-separated values."""
    key, eq, raw = item.partition("=")
    group, dot, name = key.partition(".")
    kind = SCHEMA.get(group, {}).get(name) if dot else None
    if not eq or kind is None:
        raise SettingsError(f"--set {item!r}: expected KEY=VALUE with KEY one of {', '.join(SETTINGS)}")
    if kind[0] == "bool":
        value = {"true": True, "false": False}.get(raw.lower(), raw)
    elif kind[0] == "minutes":
        value = int(raw) if re.fullmatch(r"\d+", raw) else raw
    elif kind[0] == "list":
        value = [v for v in raw.split(",") if v] if raw else []
    else:
        value = raw
    if not _valid(kind, value):
        raise SettingsError(f"--set {item!r}: key coordination.{group}.{name} allows {_allowed(kind)}")
    return group, name, value


def _write_json(path, doc):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")


def init(root, sets=()):
    """Write the whole coordination section of `<ROOT>/settings.json` (each key the file holds keeps its value, SETS
    (`group.name=VALUE`) set theirs, the rest take their defaults) and add `coord` to the `hooks` list of
    `<ROOT>/backlog.json`. Returns the names of the files it changed; a file whose content would not change is not
    written."""
    root = Path(root)
    changes = [_parse_set(item) for item in sets]
    path, hooks_path = root / "settings.json", root / "backlog.json"
    held = _read(path)
    section = json.loads(json.dumps(DEFAULTS))
    for group, body in held.items():
        section[group].update(body)
    for group, name, value in changes:
        section[group][name] = value
    doc = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    try:
        hooks_doc = json.loads(hooks_path.read_text(encoding="utf-8")) if hooks_path.exists() else {}
    except (OSError, ValueError) as e:
        raise SettingsError(f"{hooks_path}: cannot read as JSON: {e}")
    hooks = hooks_doc.get("hooks", []) if isinstance(hooks_doc, dict) else None
    if not isinstance(hooks, list):
        raise SettingsError(f"{hooks_path}: the file must hold an object whose key hooks is a list")
    written = []
    if doc.get("coordination") != section:
        doc["coordination"] = section
        _write_json(path, doc)
        written.append(path.name)
    if "coord" not in hooks:
        hooks_doc["hooks"] = hooks + ["coord"]
        _write_json(hooks_path, hooks_doc)
        written.append(hooks_path.name)
    return written


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
    for name, help_ in (("show", "print the effective coordination settings"),
                        ("explain", "print each setting (or KEY) with its value, source, meaning and doc line")):
        sp = sub.add_parser(name, help=help_)
        if name == "explain":
            sp.add_argument("key", nargs="?", help="one setting, e.g. strategy.working (default: all)")
        sp.add_argument("--root", required=True, help="the workspace directory (holds settings.json and kb/)")
        sp.add_argument("--kb-root", help="a kb root's name: kb/NAME/settings.json overrides the workspace's")
        sp.add_argument("--json", action="store_true", help="print JSON")
    sp = sub.add_parser("init", help="write the coordination section of settings.json and turn the coord hook on")
    sp.add_argument("--root", required=True, help="the workspace directory (holds settings.json and backlog.json)")
    sp.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                    help="one setting, e.g. strategy.working=ask or announce.when=start,claim (repeatable)")
    sub.add_parser("check", help="exit 1 when the SETTINGS table and the doc's Settings section disagree")
    args = ap.parse_args(argv)
    if args.cmd == "check":
        try:
            problems = check(Path(__file__).resolve().parent.parent.joinpath(DOC).read_text(encoding="utf-8"))
        except OSError as e:
            problems = [f"{DOC}: cannot read: {e}"]
        print("\n".join(problems) if problems else "kbsettings: the table and the doc agree")
        return 1 if problems else 0
    try:
        if args.cmd == "init":
            written = init(args.root, args.set)
            print(f"kbsettings: wrote {', '.join(written)}" if written else "kbsettings: nothing to change")
            return 0
        if args.cmd == "explain":
            rows = explain(args.root, args.kb_root, args.key)
            out = (json.dumps(rows[0] if args.key else rows, indent=2, sort_keys=True) if args.json
                   else explain_text(rows))
        else:
            settings = effective(args.root, args.kb_root)
            out = json.dumps(settings, indent=2, sort_keys=True) if args.json else _text(settings)
    except SettingsError as e:
        print(f"kbsettings: {e}", file=sys.stderr)
        return 2
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
