#!/usr/bin/env python3
"""A group's extenders for the kb's extension points (stdlib only).

  kbext.py resolve POINT --root WS [--kb-root NAME]                 print the point, the extender (module:attr), the
                                                                    layer that names it and that layer's file; exit 0
  kbext.py call POINT --root WS [--kb-root NAME] --json ARGS        call the extender with the JSON list ARGS as its
                                                                    arguments and print its answer as JSON

`API_VERSION` is the version of the extension API (MAJOR.MINOR.PATCH). `load(point, root, kb_root=None)` returns the
extender of an extension point, found in this order:
  1. `extensions.<point>` of the settings layers (`kbsettings.layered`: group, clone, kb root, user, later over earlier),
     written `module:attr` (the attribute, dotted when nested) or `module` alone (the module is the extender);
  2. with no such setting, the one entry point of group `it_ops_kb.<point>` that `importlib.metadata.entry_points` finds.
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
Use: python3 _tools/kbext.py resolve|call POINT --root WS
"""
import argparse, importlib, json, re, sys
from importlib import metadata
from pathlib import Path

import kbsettings

API_VERSION = "0.1.0"
POINT_RE = re.compile(r"[a-z][a-z0-9_]*")
BOUND_RE = re.compile(r"\s*(>=|<=|==|>|<)\s*(\d+)\.(\d+)\s*")
GROUP = "it_ops_kb"


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


def resolve(point, root, kb_root=None):
    """The extender of POINT for workspace ROOT: a dict with `point`, `spec` (module:attr), `layer` (`default`...`user`
    or `entry point`), `file` (the settings file relative to ROOT, or the distribution name), `module` and `extender`;
    raises ExtensionError (one line naming the point, the module and the layer) when it cannot be used."""
    if not POINT_RE.fullmatch(str(point)):
        raise ExtensionError(f"point {point!r}: a name of lower-case letters, digits and underscores is expected")
    _add_paths(root, kb_root)
    setting = _named(root, kb_root, "extensions", point)
    if setting is not None:
        spec, layer, file = setting
        if not isinstance(spec, str) or not spec:
            raise ExtensionError(f"point {point}: extensions.{point} in the {layer} layer ({file}) must be "
                                 f"module:attr or a module name")
    else:
        found = _entry_point(point)
        if found is None:
            raise ExtensionError(f"point {point}: no extensions.{point} setting in any layer and no entry point of "
                                 f"group {GROUP}.{point}")
        (spec, file), layer = found, "entry point"
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


def load(point, root, kb_root=None):
    """The extender of POINT (the attribute `module:attr` names, or the module); see `resolve` for the refusals."""
    return resolve(point, root, kb_root)["extender"]


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
