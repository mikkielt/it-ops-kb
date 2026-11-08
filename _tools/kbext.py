#!/usr/bin/env python3
"""A group's extenders for the kb's extension points (stdlib only).

  kbext.py resolve POINT --root WS [--kb-root NAME]                 print the point, the extender (module:attr), the
                                                                    layer that names it and that layer's file; exit 0
  kbext.py call POINT --root WS [--kb-root NAME] --json ARGS        call the extender with the JSON list ARGS as its
                                                                    arguments and print its answer as JSON
  kbext.py surface [--json]                                         print API_VERSION and `SURFACE`, the public
                                                                    extension API: each point and settings key with its
                                                                    signature and the version that added it; exit 0

`API_VERSION` is the version of the extension API (MAJOR.MINOR.PATCH). `SURFACE` is the one registry of the public API (a
literal: dicts with `name`, `signature`, `added`, and `deprecated` / `removed` for a deprecated one); anything not in it
is internal, and `selfdoc.py check` fails when `kb/_self/extending.md`'s table differs from it. `load(point, root, kb_root=None)` returns the
extender of an extension point, found in this order:
  1. `extensions.<point>` of the settings layers (`kbsettings.layered`: group, clone, kb root, user, later over earlier),
     written `module:attr` (the attribute, dotted when nested) or `module` alone (the module is the extender);
  2. with no such setting, the one entry point of group `it_ops_kb.<point>` that `importlib.metadata.entry_points` finds.
`load_all(point, root, kb_root=None)` is the same for a point whose setting may be a list of `module:attr`, as `mcp_tools`'s:
it returns the extenders in order, with the refusals of `load`. `load_spec(point, spec, root, kb_root=None)` loads one
`module:attr` a tool read from its own object-valued setting (`ingest_mappers`: language to `module:attr`), with the
same `extension_paths`, `KBEXT_REQUIRES` and refusals, and returns the dict `resolve` does.
Each directory a settings file lists under `extension_paths` is read relative to the directory of the file that names it
(an absolute path stays) and put on `sys.path` before the module is imported; the later layer's comes first.

The module declares which API versions it takes in `KBEXT_REQUIRES`, a string of comma-separated bounds on MAJOR.MINOR
(`>=0.1,<2.0`; the operators are `>=`, `>`, `<=`, `<` and `==`): `API_VERSION`'s MAJOR.MINOR must meet each. A module
without it is refused.

`load` raises `ExtensionError` and the command exits 2, with one line on stderr that names the point, the module and
the layer (`entry point` for an entry point), for a missing module, a missing attribute, a version outside
`KBEXT_REQUIRES`, a missing or malformed `KBEXT_REQUIRES`, a bad setting, an extender that is no callable (for `call`) and
an extender that raises. Two entry points for one point exit 2 naming both distributions; no setting and no entry point
exit 2 naming the point. A bad argument exits 2 too; the commands never exit 1.

Answers: how a group's extender for an extension point is found, loaded and checked against the API version
Answers: which extension points and settings keys are the public extension API, and its version
Use: python3 _tools/kbext.py resolve|call POINT --root WS | surface [--json]
"""
import argparse, importlib, json, re, sys
from importlib import metadata
from pathlib import Path

import kbsettings

API_VERSION = "0.1.0"
POINT_RE = re.compile(r"[a-z][a-z0-9_]*")
BOUND_RE = re.compile(r"\s*(>=|<=|==|>|<)\s*(\d+)\.(\d+)\s*")
GROUP = "it_ops_kb"


# The public extension API: the one registry of what a group may rely on, a literal `ast.literal_eval` reads.
# Everything not listed here is internal. `points` are the extension points (the key of `extensions.<name>`), `settings`
# the keys of a settings file an extender or a group sets. Each entry is a dict with `name`, `signature` and `added` (the
# API_VERSION that introduced it); a deprecated one also has `deprecated` and, once it stops working, `removed`, each an
# API_VERSION. `kb/_self/extending.md` holds the same table and `selfdoc.py check` fails when they differ.
SURFACE = {
    "points": [
        {"name": "lane", "signature": "module with path_lane(path) -> str and commit_paths(repo, sha) -> list",
         "added": "0.1.0"},
        {"name": "forge", "signature": "Adapter(target, run, cwd=None) with request, pipelines, pipeline, jobs, trace, "
                                       "set_description, merge", "added": "0.1.0"},
        {"name": "ranker", "signature": "rank(question, candidates) -> list of candidate paths", "added": "0.1.0"},
        {"name": "mcp_tools", "signature": "list of dicts with name, description, inputSchema and call(arguments) -> str",
         "added": "0.1.0"},
        {"name": "ingest_mappers", "signature": "module with SUFFIXES and mapper(repo_dir, rev, files) -> dict",
         "added": "0.1.0"},
        {"name": "leak_scan", "signature": "file_hits(path, text, allow, pinned=()) -> list", "added": "0.1.0"},
        {"name": "backlog_commands", "signature": "list of modules adding or replacing a command through bl_cli.register(name, "
                                              "handler, add_arguments=None, help=None) or bl_cli.extend(name, wrap, "
                                              "add_arguments)", "added": "0.1.0"},
    ],
    "settings": [
        {"name": "extensions", "signature": "object: point name -> module:attr", "added": "0.1.0"},
        {"name": "extension_paths", "signature": "list of directories put on sys.path", "added": "0.1.0"},
        {"name": "backlog", "signature": "object overriding backlog.json key by key", "added": "0.1.0"},
        {"name": "gate_checks", "signature": "list of argument lists run after the shipped gate", "added": "0.1.0"},
        {"name": "group", "signature": "string: the group's name", "added": "0.1.0"},
        {"name": "leak", "signature": "object with shapes: list of kind and regular expression", "added": "0.1.0"},
        {"name": "locked", "signature": "list of key names a later layer may not set", "added": "0.1.0"},
    ],
}


def surface():
    """The public extension API as a dict: `api_version`, `points` and `settings` (the entries of SURFACE)."""
    return {"api_version": API_VERSION, "points": [dict(e) for e in SURFACE["points"]],
            "settings": [dict(e) for e in SURFACE["settings"]]}


def _surface_text(info):
    out = [f"API_VERSION {info['api_version']}"]
    for title, key in (("extension points", "points"), ("settings keys", "settings")):
        out.append(f"{title}:")
        for e in info[key]:
            note = "".join(f", {k} {e[k]}" for k in ("deprecated", "removed") if e.get(k))
            out.append(f"  {e['name']}  {e['signature']}  (added {e['added']}{note})")
    return "\n".join(out)


class ExtensionError(ValueError):
    """An extender that cannot be found, imported or used; the message is one line."""


def _version(text):
    major, minor = text.split(".")[:2]
    return int(major), int(minor)


def _check_requires(requires, where):
    """Raise ExtensionError unless API_VERSION's MAJOR.MINOR meets every bound of REQUIRES."""
    if not isinstance(requires, str) or not requires.strip():
        raise ExtensionError(f"{where}: KBEXT_REQUIRES must be a string of bounds such as \">=0.1,<2.0\"")
    have = _version(API_VERSION)
    for part in requires.split(","):
        m = BOUND_RE.fullmatch(part)
        if not m:
            raise ExtensionError(f"{where}: KBEXT_REQUIRES {requires!r} is not bounds on MAJOR.MINOR such as "
                                 f"\">=0.1,<2.0\"")
        op, want = m.group(1), (int(m.group(2)), int(m.group(3)))
        ok = {">=": have >= want, ">": have > want, "<=": have <= want, "<": have < want, "==": have == want}[op]
        if not ok:
            raise ExtensionError(f"{where}: needs API {requires.strip()} but API_VERSION is {API_VERSION}")


def _named(root, kb_root, name, key):
    """The setting `name.key` and where it came from: (value, layer, shown file) or None when no layer sets it."""
    try:
        merged, source = kbsettings.layered(root, name, kb_root)
        layers = kbsettings.layer_files(root, kb_root)
    except kbsettings.SettingsError as e:
        raise ExtensionError(str(e))
    if key not in merged:
        return None
    layer = source[key]
    files = [p for which, p, data in layers if which == layer and key in (data.get(name) or {})]
    return merged[key], layer, kbsettings.shown_path(files[-1], root)


def _add_paths(root, kb_root):
    """Put the extension_paths directories of every settings layer on sys.path, each relative to the file naming it."""
    try:
        layers = kbsettings.layer_files(root, kb_root)
    except kbsettings.SettingsError as e:
        raise ExtensionError(str(e))
    for _, path, data in layers:
        listed = data.get("extension_paths", [])
        if isinstance(listed, dict):
            listed = list(listed.values())
        if not isinstance(listed, list) or not all(isinstance(d, str) and d for d in listed):
            raise ExtensionError(f"{kbsettings.shown_path(path, root)}: key extension_paths must be a list of directories")
        for d in listed:
            full = str(Path(d) if Path(d).is_absolute() else Path(path).parent / d)
            if full not in sys.path:
                sys.path.insert(0, full)


def _entry_point(point):
    """(spec, distribution) of the one entry point of group it_ops_kb.POINT, or None; two raise ExtensionError."""
    found = sorted(metadata.entry_points(group=f"{GROUP}.{point}"), key=lambda e: (e.dist.name, e.name))
    if not found:
        return None
    if len(found) > 1:
        names = " and ".join(f"{e.dist.name} ({e.name} = {e.value})" for e in found)
        raise ExtensionError(f"point {point}: {len(found)} entry points of group {GROUP}.{point}: {names}; "
                             f"install one or name the extender in extensions.{point}")
    return found[0].value, found[0].dist.name


def _find(point, root, kb_root, many):
    """(specs, layer, file) of the extender of POINT: the one `module:attr` of the setting or entry point, or, with MANY, the
    list of them a setting may hold; raises ExtensionError when none is named or the setting is malformed."""
    if not POINT_RE.fullmatch(str(point)):
        raise ExtensionError(f"point {point!r}: a name of lower-case letters, digits and underscores is expected")
    _add_paths(root, kb_root)
    setting = _named(root, kb_root, "extensions", point)
    if setting is not None:
        value, layer, file = setting
        specs = value if many and isinstance(value, list) else [value]
        if not specs or not all(isinstance(s, str) and s for s in specs):
            raise ExtensionError(f"point {point}: extensions.{point} in the {layer} layer ({file}) must be "
                                 f"module:attr or a module name{' or a list of them' if many else ''}")
        return specs, layer, file
    found = _entry_point(point)
    if found is None:
        raise ExtensionError(f"point {point}: no extensions.{point} setting in any layer and no entry point of "
                             f"group {GROUP}.{point}")
    return [found[0]], "entry point", found[1]


def _import(point, spec, layer, file):
    """The dict `resolve` returns for the one SPEC."""
    name, _, attr = spec.partition(":")
    where = f"point {point}: module {name or spec}, layer {layer} ({file})"
    try:
        module = importlib.import_module(name)
    except ImportError as e:
        raise ExtensionError(f"{where}: cannot import: {e}")
    except Exception as e:
        raise ExtensionError(f"{where}: importing it raised {type(e).__name__}: {e}")
    if not hasattr(module, "KBEXT_REQUIRES"):
        raise ExtensionError(f"{where}: no KBEXT_REQUIRES: the module must declare which API versions it takes")
    _check_requires(module.KBEXT_REQUIRES, where)
    extender = module
    for part in filter(None, attr.split(".")):
        try:
            extender = getattr(extender, part)
        except AttributeError:
            raise ExtensionError(f"{where}: no attribute {attr}")
    return {"point": point, "spec": spec, "layer": layer, "file": file, "module": module, "extender": extender,
            "where": where}


def resolve(point, root, kb_root=None):
    """The extender of POINT for workspace ROOT: a dict with `point`, `spec` (module:attr), `layer` (`default`...`user`
    or `entry point`), `file` (the settings file relative to ROOT, or the distribution name), `module` and `extender`;
    raises ExtensionError (one line naming the point, the module and the layer) when it cannot be used."""
    specs, layer, file = _find(point, root, kb_root, False)
    return _import(point, specs[0], layer, file)


def load_all(point, root, kb_root=None):
    """The extenders of POINT as a list, in the order the setting names them: `extensions.<point>` may be one `module:attr`
    or a list of them (an entry point gives one). Each is loaded and checked as `resolve` does, and the first that cannot
    be used raises ExtensionError; none named raises it too (ask `configured` first)."""
    specs, layer, file = _find(point, root, kb_root, True)
    return [_import(point, spec, layer, file)["extender"] for spec in specs]


def load(point, root, kb_root=None):
    """The extender of POINT (the attribute `module:attr` names, or the module); see `resolve` for the refusals."""
    return resolve(point, root, kb_root)["extender"]


def load_spec(point, spec, root, kb_root=None):
    """The dict `resolve` returns (`module`, `extender`, `where`...) for the one SPEC (`module:attr`, or a module name) that a
    caller read from its own setting of POINT: a point whose value is an object (`ingest_mappers`: language to `module:attr`)
    is read by the tool, which loads each entry here. The `extension_paths` of the settings layers are put on `sys.path`
    first and the module is checked as `resolve` checks it (KBEXT_REQUIRES, an attribute that is there); it raises
    ExtensionError with its layer shown as `settings`."""
    if not POINT_RE.fullmatch(str(point)):
        raise ExtensionError(f"point {point!r}: a name of lower-case letters, digits and underscores is expected")
    if not isinstance(spec, str) or not spec:
        raise ExtensionError(f"point {point}: extensions.{point} must name module:attr or a module name")
    _add_paths(root, kb_root)
    return _import(point, spec, "settings", f"extensions.{point}")


def configured(point, root, kb_root=None):
    """True when a group names an extender for POINT: an `extensions.<point>` in a settings layer or an entry point of
    group `it_ops_kb.<point>`. A shipped tool asks it to fall back to its own default only when none is named, so a
    named extender that cannot be loaded is a refusal of `load`, never a silent fall back."""
    if not POINT_RE.fullmatch(str(point)):
        raise ExtensionError(f"point {point!r}: a name of lower-case letters, digits and underscores is expected")
    return _named(root, kb_root, "extensions", point) is not None or _entry_point(point) is not None


def call(point, root, args, kb_root=None):
    """The answer of the extender of POINT called with the list ARGS."""
    found = resolve(point, root, kb_root)
    if not callable(found["extender"]):
        raise ExtensionError(f"{found['where']}: {found['spec']} is not callable")
    try:
        return found["extender"](*args)
    except Exception as e:
        raise ExtensionError(f"{found['where']}: the extender raised {type(e).__name__}: {e}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="A group's extenders for the kb's extension points.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("surface", help="print API_VERSION and the public extension API (points and settings keys)")
    sp.add_argument("--json", action="store_true", dest="as_json", help="print one JSON object")
    for name, help_ in (("resolve", "print the extender of POINT, its layer and file"),
                        ("call", "call the extender of POINT with a JSON list and print its answer")):
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("point", help="the extension point, e.g. ranker")
        sp.add_argument("--root", required=True, help="the workspace directory (holds settings.json)")
        sp.add_argument("--kb-root", help="a kb root's name: kb/NAME/settings.json is a layer too")
        if name == "call":
            sp.add_argument("--json", dest="args_json", default="[]", metavar="ARGS",
                            help="a JSON list: the extender's arguments")
    args = ap.parse_args(argv)
    if args.cmd == "surface":
        print(json.dumps(surface(), indent=2, sort_keys=True) if args.as_json else _surface_text(surface()))
        return 0
    try:
        if args.cmd == "call":
            try:
                given = json.loads(args.args_json)
            except ValueError as e:
                raise ExtensionError(f"point {args.point}: --json is not JSON: {e}")
            if not isinstance(given, list):
                raise ExtensionError(f"point {args.point}: --json must be a JSON list of arguments")
            answer = call(args.point, args.root, given, args.kb_root)
            try:
                out = json.dumps(answer, sort_keys=True)
            except (TypeError, ValueError) as e:
                raise ExtensionError(f"point {args.point}: the answer is not JSON: {e}")
        else:
            found = resolve(args.point, args.root, args.kb_root)
            where = (f"entry point of distribution {found['file']}" if found["layer"] == "entry point"
                     else f"layer {found['layer']}, file {found['file']}")
            out = f"{found['point']} {found['spec']} ({where})"
    except ExtensionError as e:
        print(f"kbext: {e}", file=sys.stderr)
        return 2
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
