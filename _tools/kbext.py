#!/usr/bin/env python3
"""A group's extenders for the kb's extension points (stdlib only).

  kbext.py resolve POINT --root WS [--kb-root NAME]                 print the point, the extender (module:attr), the
                                                                    layer that names it and that layer's file; exit 0
  kbext.py call POINT --root WS [--kb-root NAME] --json ARGS        call the extender with the JSON list ARGS as its
                                                                    arguments and print its answer as JSON
  kbext.py surface [--json]                                         print API_VERSION and `SURFACE`, the public
                                                                    extension API: each point and settings key with its
                                                                    signature and the version that added it; exit 0
  kbext.py lint [--root REPO]                                       compare `SURFACE` at the newest `ext-v` tag with the
                                                                    working tree's: exit 1 naming each break, 0 when none
  kbext.py verify --root WS [--kb-root NAME] [--timeout S]          call each extender the settings layers name with its
                                                                    point's samples in a child process and check the shape
                                                                    of the answer: one line each, exit 1 when one fails
  kbext.py guards --root WS [--kb-root NAME]                        print each shipped guard a group's extender replaces
                                                                    (point, module, layer) and the leak shapes it added,
                                                                    or one line saying the shipped guards run; exit 0
  kbext.py init-team DIR --group NAME --upstream URL [--ref TAG]    write a group's overlay repository into DIR (below)
  kbext.py rehearse --team DIR (--upstream URL --from TAG --to TAG | --plant [--break]) [--fork]
                                                                    dry-run the group's move from one upstream ext tag to
                                                                    the next in temporary directories (below): exit 0 only
                                                                    with no conflict, no shipped file changed, every extender ok

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
exit 2 naming the point. A bad argument exits 2 too; `resolve`, `call` and `surface` never exit 1.

`verify` is the check a group's CI runs after each upstream pull. For each point of `SURFACE` that `extensions.<point>`
names in a settings layer (an object-valued setting such as `ingest_mappers` and a list such as `mcp_tools` count each
entry) it loads the extender and calls it with the point's `samples`, each in a child process that `--timeout` (default
30 seconds) bounds, and checks each answer with the sample's `shape` (`SHAPES`). It prints one line per extender, `ok` or
`FAIL` with the point, the module and the layer, and exits 1 when any failed (a module that does not load, a
`KBEXT_REQUIRES` the API does not meet, a call that raises or times out, an answer of another shape, a key of
`extensions` that is no point of `SURFACE`), else 0, also when none is configured; a bad argument exits 2.

`init-team` writes a group's overlay repository: `.claude-plugin/marketplace.json` lists `it-ops-kb` with a `url` source at
URL and the tag TAG (default `ext-v` and `API_VERSION`) beside the group's own plugin, whose source is the marketplace
root; `.claude-plugin/plugin.json` names that plugin, with `skills/`, `agents/` and `hooks/` directories for the group's
own; `settings/group.json` names the group, `extension_paths` `../ext` and `extensions.ranker`, a sample ranker in
`ext/` that `verify` passes. A file that is there with the same text is left alone, so a second run changes nothing; one
that holds other text exits 2 naming it on stderr, and nothing is written.

`rehearse` is the dry run of a group's upgrade, in temporary directories it removes (also on a failure). It clones URL at the
tag FROM into a copy whose `main` it then moves to TO, takes the group's `TEAM/settings/group.json` as the group layer
(`KB_GROUP_SETTINGS`), with `--fork` makes a commit that adds the group's root with `kbroot.py add`, lists the shipped files
(tracked at FROM) that the group's setup modified or deleted, takes TO with the clone's own `kbgit.py upstream` (scope `team`,
a merge) and, when it left no conflict, runs the clone's `kbext.py verify`. It prints the conflicting paths, the shipped
files changed and verify's lines. Exit 0 only with no conflict, no shipped file changed and every extender verified, 1 for
any of them, 2 for a rehearsal that could not be made (a tag or file missing, a git or tool failure). `--plant` builds the
upstream from the running checkout's tracked `_tools` (what kbgit.py, kbroot.py and kbext.py import, no tests) as two commits
tagged `ext-v` and `API_VERSION` and the next minor; with `--break` the second removes the `ranker` point, which `verify`
reports by name.

`leak_shapes(root, kb_root=None)` reads `leak.shapes` of the settings layers (a list of objects with `kind` and `pattern`, each
layer's own) for `kbcommon.leak_hits`, which refuses them with its shipped shapes. A shape that is no object of exactly
those keys, whose kind is not lower-case letters, digits and single hyphens or is one of the shipped kinds (`SHIPPED_KINDS`)
or starts `private-`, whose pattern does not compile or matches the empty string, raises ExtensionError naming `leak.shapes`,
the layer and its file. `replaced_guards` and `guard_lines` name each shipped guard (`GUARDS`: `leak_scan` stands in for
`kbpublic.file_hits`) that an extender replaces, from the settings and entry points alone, importing nothing. `guards`
prints those lines and exits 0, or 2 with the refusal of `leak_shapes` or of a bad `extensions` setting.

`lint` is the gate on the API's compatibility. A repository with no tag `ext-vMAJOR.MINOR.PATCH` prints one line and exits 0.
Otherwise it reads `API_VERSION` and `SURFACE` of `_tools/kbext.py` at the newest such tag (`git show`) and of the working
tree with `ast`, never importing either file, and exits 1 with one line per problem: an entry removed or with a changed
signature that `surface_breaks` does not let pass, an `API_VERSION` lower than the tag's, and a changed `API_VERSION` with no
entry in `kb/_self/extension-changelog.md` (`changelog_problems`). `deprecated(name, since, removed_in)` is what a deprecated
entry calls when it is used.

Answers: how a group's extender for an extension point is found, loaded and checked against the API version
Answers: which extension points and settings keys are the public extension API, and its version
Answers: whether a change removes or changes a public extension entry without a major API version, a deprecation and a changelog entry
Answers: which shipped guards a group's extender replaces in this clone and which leak shapes the group added
Answers: whether each extender a group configured still loads and answers its point's sample inputs in the shape the API promises
Answers: how to start a group's overlay repository that pins it-ops-kb by an ext tag and holds the group's plugin and extenders
Answers: whether a group's overlay and fork take the next upstream ext tag with no conflict, no shipped file edited and every extender verified
Use: python3 _tools/kbext.py resolve|call POINT --root WS | surface [--json] | lint [--root REPO] | verify --root WS | guards --root WS | init-team DIR --group NAME --upstream URL | rehearse --team DIR --plant|--upstream URL --from TAG --to TAG
"""
import argparse, ast, collections, importlib, json, os, re, shutil, subprocess, sys, tempfile
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
# API_VERSION. `kb/_self/extending.md` holds the same table and `selfdoc.py check` fails when they differ. A point also
# has `answer` (its answer in words) and `samples`, which `verify` runs: each a dict with `shape` (a key of SHAPES, the
# check of the answer) and either `call` (the attribute to call, "" for the extender itself) with `args` (a JSON list;
# the strings $REPO, $SHA, $EMPTY, $TARGET, $RUN and $CWD stand for objects `verify` makes) or `value` (the attribute to
# read, "" for the extender itself).
SURFACE = {
    "points": [
        {"name": "lane", "signature": "module with path_lane(path) -> str and commit_paths(repo, sha) -> list",
         "added": "0.1.0", "answer": "path_lane answers a string, commit_paths a list",
         "samples": [{"call": "path_lane", "args": ["_tools/example.py"], "shape": "str"},
                     {"call": "commit_paths", "args": ["$REPO", "$SHA"], "shape": "list"}]},
        {"name": "forge", "signature": "Adapter(target, run, cwd=None) with request, pipelines, pipeline, jobs, trace, "
                                       "set_description, merge", "added": "0.1.0",
         "answer": "an object with the seven methods as callables",
         "samples": [{"call": "", "args": ["$TARGET", "$RUN", "$CWD"], "shape": "adapter"}]},
        {"name": "ranker", "signature": "rank(question, candidates) -> list of candidate paths", "added": "0.1.0",
         "answer": "a list of path strings",
         "samples": [{"call": "", "args": ["how do I enroll a device in Intune",
                                            ["public/intune/enroll.md", "public/autopilot/overview.md"]],
                      "shape": "list_of_str"}]},
        {"name": "mcp_tools", "signature": "list of dicts with name, description, inputSchema and call(arguments) -> str",
         "added": "0.1.0", "answer": "a tool dict, or a list of them, each with name, description, inputSchema and call",
         "samples": [{"value": "", "shape": "tools"}]},
        {"name": "ingest_mappers", "signature": "module with SUFFIXES and mapper(repo_dir, rev, files) -> dict",
         "added": "0.1.0", "answer": "SUFFIXES lists suffixes, the mapper function answers a dict of optional lists",
         "samples": [{"value": "SUFFIXES", "shape": "suffixes"},
                     {"call": "", "args": ["$EMPTY", "HEAD", []], "shape": "mapping"}]},
        {"name": "leak_scan", "signature": "file_hits(path, text, allow, pinned=()) -> list", "added": "0.1.0",
         "answer": "a list of hits",
         "samples": [{"call": "", "args": ["docs/example.md", "A note about corp.example.com.\n", [], []],
                      "shape": "list"}]},
        {"name": "backlog_commands", "signature": "list of modules adding or replacing a command through bl_cli.register(name, "
                                              "handler, add_arguments=None, help=None) or bl_cli.extend(name, wrap, "
                                              "add_arguments)", "added": "0.1.0", "answer": "each extender is a module",
         "samples": [{"value": "", "shape": "module"}]},
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


_WARNED = set()


def deprecated(name, since, removed_in):
    """Warn once per process, on stderr, that the public entry NAME is deprecated since API version SINCE and goes in the
    major API version REMOVED_IN. An entry marked `deprecated` in `SURFACE` calls it where it is used."""
    if name in _WARNED:
        return
    _WARNED.add(name)
    print(f"kbext: deprecated since API {since}, removed in API {removed_in}: {name}", file=sys.stderr)


def _numbers(text):
    """(major, minor, patch) of a MAJOR.MINOR[.PATCH] string; ValueError for anything else."""
    m = re.fullmatch(r"\s*(\d+)\.(\d+)(?:\.(\d+))?\s*", str(text))
    if not m:
        raise ValueError(f"{text!r} is not a MAJOR.MINOR.PATCH version")
    return int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)


def _generation(text):
    """The compatibility generation of an API version: its major, and while the major is 0 its minor too, since a 0.x
    version promises no compatibility before 1.0 (a higher minor counts as a higher major)."""
    major, minor, _ = _numbers(text)
    return (major, minor if major == 0 else 0)


def _entries(info):
    """{(section, name): entry} of a surface dict: every key whose value is a list of dicts with a `name`."""
    return {(key, e["name"]): e for key, value in sorted(info.items()) if isinstance(value, list)
            for e in value if isinstance(e, dict) and "name" in e}


def surface_breaks(old, new):
    """The breaks between two surfaces (dicts with `api_version` and lists of entries: `points`, `settings`...), one line
    each: a public entry of OLD that NEW lacks or gives another signature. A break passes only when NEW's API version is of
    a higher generation than OLD's (a higher major; while the major is 0, a higher minor) and OLD already marked the entry
    `deprecated`, so a group saw the warning in a release before the one that breaks it. An entry that NEW only adds, or
    changes in `added`, `deprecated` or `removed`, is no break."""
    try:
        later = _generation(new["api_version"]) > _generation(old["api_version"])
    except (KeyError, ValueError) as e:
        return [f"api_version of the surfaces cannot be compared: {e}"]
    now = _entries(new)
    out = []
    for (section, name), entry in _entries(old).items():
        found = now.get((section, name))
        if found is None:
            what = f"{section} entry {name} is removed"
        elif found.get("signature") != entry.get("signature"):
            what = f"{section} entry {name} changes its signature from {entry.get('signature')!r} to {found.get('signature')!r}"
        else:
            continue
        if not later:
            out.append(f"{what} without a higher API version (old {old['api_version']}, new {new['api_version']})")
        elif not entry.get("deprecated"):
            out.append(f"{what} but the old surface never marked it deprecated")
    return out


def changelog_problems(version, text):
    """[] when TEXT (kb/_self/extension-changelog.md) has an entry for API version VERSION, a heading `## VERSION` (a
    leading `v` and text after the version are allowed); else one line naming the version."""
    if re.search(rf"^##\s+v?{re.escape(str(version))}(?:\s|$)", text, re.M):
        return []
    return [f"API_VERSION {version} has no entry in kb/_self/extension-changelog.md (a heading `## {version}`)"]


TAG_RE = re.compile(r"ext-v(\d+)\.(\d+)\.(\d+)")
SOURCE = "_tools/kbext.py"
CHANGELOG = "kb/_self/extension-changelog.md"


def _literals(text):
    """{name: value} of the top-level `API_VERSION` and `SURFACE` assignments of the module source TEXT, read with `ast`
    and never run; a value that is no literal is left out."""
    found = {}
    for node in ast.parse(text).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ("API_VERSION", "SURFACE"):
                    try:
                        found[target.id] = ast.literal_eval(node.value)
                    except ValueError:
                        pass
    return found


def _read_surface(text, where):
    """The surface dict (`api_version` and the entry lists) of the kbext.py source TEXT; ValueError names WHERE."""
    try:
        found = _literals(text)
    except SyntaxError as e:
        raise ValueError(f"{where}: cannot be parsed: {e.msg} (line {e.lineno})")
    if not isinstance(found.get("API_VERSION"), str) or not isinstance(found.get("SURFACE"), dict):
        raise ValueError(f"{where}: no literal API_VERSION and SURFACE")
    return {"api_version": found["API_VERSION"], **found["SURFACE"]}


def _git(root, *args):
    """(exit code, stdout) of git in ROOT; (127, "") when git cannot be run."""
    try:
        p = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
    except OSError:
        return 127, ""
    return p.returncode, p.stdout


def newest_tag(root):
    """The newest tag `ext-vMAJOR.MINOR.PATCH` of the repository ROOT by version, or None."""
    code, out = _git(root, "tag", "--list", "ext-v*")
    tags = [(tuple(int(n) for n in m.groups()), m.group(0)) for m in map(TAG_RE.fullmatch, out.split()) if m] if not code else []
    return max(tags)[1] if tags else None


def lint(root):
    """(exit code, lines) of the compatibility check of the repository ROOT: 0 with one line when it has no `ext-v` tag
    or nothing breaks; 1 with a line per break, per lowered API_VERSION and per changed API_VERSION that has no changelog
    entry. The two surfaces are read from the source text of `_tools/kbext.py` at the tag and in the working tree."""
    root = Path(root)
    tag = newest_tag(root)
    if tag is None:
        return 0, [f"kbext lint: no ext-v tag in {root}, nothing to compare"]
    code, text = _git(root, "show", f"{tag}:{SOURCE}")
    if code:
        return 1, [f"kbext lint: {SOURCE} cannot be read at {tag}"]
    try:
        old = _read_surface(text, f"{SOURCE} at {tag}")
        path = root / SOURCE
        new = _read_surface(path.read_text(encoding="utf-8"), SOURCE)
    except (ValueError, OSError) as e:
        return 1, [f"kbext lint: {e}"]
    problems = surface_breaks(old, new)
    try:
        if _numbers(new["api_version"]) < _numbers(old["api_version"]):
            problems.append(f"API_VERSION {new['api_version']} is lower than {old['api_version']} of {tag}")
        elif new["api_version"] != old["api_version"]:
            log = root / CHANGELOG
            problems += changelog_problems(new["api_version"], log.read_text(encoding="utf-8") if log.is_file() else "")
    except (ValueError, OSError) as e:
        problems.append(f"API_VERSION cannot be compared: {e}")
    if problems:
        return 1, [f"kbext lint: {p}" for p in problems]
    return 0, [f"kbext lint: ok, no break since {tag}"]


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
        if key not in merged:
            return None
        layer = source[key]
        path = kbsettings.layer_path(root, layer, kb_root)
    except kbsettings.SettingsError as e:
        raise ExtensionError(str(e))
    return merged[key], layer, kbsettings.shown_path(path, root)


def _add_paths(root, kb_root):
    """Put the extension_paths directories of every settings layer on sys.path, each relative to the file naming it."""
    try:
        listed, layers = kbsettings.layered(root, "extension_paths", kb_root)
        homes = {layer: kbsettings.layer_path(root, layer, kb_root) for layer in set(layers)}
    except kbsettings.SettingsError as e:
        raise ExtensionError(str(e))
    for layer, d in zip(layers, listed):
        if not (isinstance(d, str) and d):
            raise ExtensionError(f"{kbsettings.shown_path(homes[layer], root)}: key extension_paths must be a list of "
                                 "directories")
        full = str(Path(d) if Path(d).is_absolute() else Path(homes[layer]).parent / d)
        if full not in sys.path:
            sys.path.insert(0, full)


def _entry_point(point):
    """(spec, distribution) of the one entry point of group it_ops_kb.POINT, or None; two raise ExtensionError."""
    from importlib import metadata  # imported here: a tool that only reads shapes pays nothing for it
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


# What a group may replace of the shipped guards: extension point -> the shipped function it stands in for.
GUARDS = {"leak_scan": "kbpublic.file_hits"}
SHIPPED_KINDS = ("secret", "home", "ip", "email", "guid")  # the kinds of the shipped leak scan; a group shape takes none of them
LEAK_KIND_RE = re.compile(r"[a-z][a-z0-9]*(-[a-z0-9]+)*")
_CACHE = {}


def _stat(path):
    try:
        st = os.stat(path)
    except OSError:
        return None
    return st.st_mtime_ns, st.st_size


def _cached(kind, root, kb_root, make):
    """MAKE(layers) for the settings layers of ROOT, kept for the process until one of the files that took part (or could
    have: the four fixed paths and the group file the environment names) changes, so a scan that asks once per line reads
    no file again. A SettingsError is raised as ExtensionError and never kept."""
    root = Path(root)
    key = (kind, str(root), kb_root, os.environ.get(kbsettings.GROUP_ENV))
    held = _CACHE.get(key)
    if held and all(_stat(p) == s for p, s in held[0]):
        return held[1]
    extra = [root / "settings.json", root / ".it-ops-kb" / "settings.json", root / "_private" / "settings.json"]
    if os.environ.get(kbsettings.GROUP_ENV):
        extra.append(Path(os.environ[kbsettings.GROUP_ENV]))
    before = {p: _stat(p) for p in extra}
    try:
        layers = kbsettings.layer_files(root, kb_root)
    except kbsettings.SettingsError as e:
        raise ExtensionError(str(e))
    for _, path, _ in layers:
        before.setdefault(path, _stat(path))
    value = make(layers)
    _CACHE[key] = (list(before.items()), value)
    return value


def leak_shapes(root, kb_root=None):
    """[(kind, compiled pattern, layer)] of the `leak.shapes` of every settings layer of ROOT (group, clone, kb root, user),
    each layer's in file order: a group's own shapes, added to those the shipped leak scan refuses (`kbcommon.leak_hits`).
    A shape is an object with `kind` (lower-case letters, digits and single hyphens, none of SHIPPED_KINDS and not
    `private-...`) and `pattern` (a regular expression that compiles and does not match the empty string). Anything else
    raises ExtensionError, one line naming `leak.shapes`, the layer, its file and the shape."""
    root = Path(root)

    def make(layers):
        found = []
        for layer, path, data in layers:
            body = data.get("leak", {})
            where = f"leak.shapes in the {layer} layer ({kbsettings.shown_path(path, root)})"
            if not isinstance(body, dict):
                raise ExtensionError(f"{where}: key leak must be an object")
            shapes = body.get("shapes", [])
            if not isinstance(shapes, list):
                raise ExtensionError(f"{where}: must be a list of objects with kind and pattern")
            for i, shape in enumerate(shapes, 1):
                at = f"{where}: shape {i}"
                if not isinstance(shape, dict) or set(shape) != {"kind", "pattern"}:
                    raise ExtensionError(f"{at} must be an object with exactly kind and pattern")
                kind, pattern = shape["kind"], shape["pattern"]
                if not isinstance(kind, str) or not LEAK_KIND_RE.fullmatch(kind) or kind in SHIPPED_KINDS \
                        or kind.startswith("private-"):
                    raise ExtensionError(f"{at}: kind {kind!r} must be lower-case letters, digits and single hyphens, "
                                         f"none of {', '.join(SHIPPED_KINDS)} and not private-...")
                if not isinstance(pattern, str) or not pattern:
                    raise ExtensionError(f"{at} ({kind}): pattern must be a non-empty string")
                try:
                    rx = re.compile(pattern)
                except re.error as e:
                    raise ExtensionError(f"{at} ({kind}): the pattern does not compile: {e}")
                if rx.search(""):
                    raise ExtensionError(f"{at} ({kind}): the pattern matches the empty string")
                found.append((kind, rx, layer))
        return found
    return _cached("leak_shapes", root, kb_root, make)


def leak_scan(root, kb_root=None):
    """The callable of extension point `leak_scan` for the clone ROOT (a group's `file_hits(path, text, allow, pinned=())`),
    or None when none is named and the shipped scan runs. It is loaded as `resolve` loads it and kept for the process
    until a settings file changes; a named one that cannot be loaded or is no callable raises ExtensionError."""
    def make(_):
        if not configured("leak_scan", root, kb_root):
            return None
        found = resolve("leak_scan", root, kb_root)
        if not callable(found["extender"]):
            raise ExtensionError(f"{found['where']}: {found['spec']} is not callable")
        return found["extender"]
    return _cached("leak_scan", root, kb_root, make)


def replaced_guards(root, kb_root=None):
    """[{point, spec, module, layer, file, replaces}] for each shipped guard (GUARDS) that a group's extender replaces in the
    clone ROOT, in GUARDS' order; empty when the shipped guards all run. It reads the settings and the entry points and
    imports nothing, so a group's code never runs to answer it. Raises ExtensionError for a refused setting."""
    out = []
    for point, replaces in GUARDS.items():
        if configured(point, root, kb_root):
            specs, layer, file = _find(point, root, kb_root, False)
            out.append({"point": point, "spec": specs[0], "module": specs[0].partition(":")[0], "layer": layer,
                        "file": file, "replaces": replaces})
    return out


def guard_lines(root, kb_root=None):
    """The lines `kbext.py guards` prints for ROOT: each replaced guard with its module and layer, the paths that run the
    shipped guards anyway, and the leak shapes a group added; `shipped guards run: ...` alone when nothing is replaced."""
    replaced = replaced_guards(root, kb_root)
    lines = [f"replaced  {g['point']}  {g['spec']}  module {g['module']}, layer {g['layer']} ({g['file']}): runs in place of "
             f"{g['replaces']} in this clone" for g in replaced]
    if replaced:
        lines.append("still shipped: kbgit.py contribute, kbgit.py publish and backlog.py upstream-report run the shipped "
                     "leak scan; the shared repository's own gate loads no group extender")
    else:
        lines.append("shipped guards run: no extension point replaces one in this clone")
    count = collections.Counter(layer for _, _, layer in leak_shapes(root, kb_root))
    if count:
        lines.append("leak.shapes added: " + ", ".join(f"{n} in the {layer} layer" for layer, n in count.items()))
    return lines


def call(point, root, args, kb_root=None):
    """The answer of the extender of POINT called with the list ARGS."""
    found = resolve(point, root, kb_root)
    if not callable(found["extender"]):
        raise ExtensionError(f"{found['where']}: {found['spec']} is not callable")
    try:
        return found["extender"](*args)
    except Exception as e:
        raise ExtensionError(f"{found['where']}: the extender raised {type(e).__name__}: {e}")


def _expect(ok, answer, wanted):
    return "" if ok else f"answered {type(answer).__name__}, expected {wanted}"


def _list_of(answer, kind):
    return isinstance(answer, list) and all(isinstance(x, kind) for x in answer)


def _tools_problem(answer):
    items = []
    for part in answer if isinstance(answer, list) else [answer]:
        items += part if isinstance(part, list) else [part]
    for tool in items:
        if not isinstance(tool, dict):
            return f"a tool is a {type(tool).__name__}, expected a dict"
        for key, kind in (("name", str), ("description", str), ("inputSchema", dict)):
            if not isinstance(tool.get(key), kind):
                return f"tool {tool.get('name', '?')}: key {key} is no {kind.__name__}"
        if not callable(tool.get("call")):
            return f"tool {tool['name']}: key call is not callable"
    return ""


def _adapter_problem(answer):
    missing = [m for m in ("request", "pipelines", "pipeline", "jobs", "trace", "set_description", "merge")
               if not callable(getattr(answer, m, None))]
    return f"the adapter has no method {', '.join(missing)}" if missing else ""


def _mapping_problem(answer):
    if not isinstance(answer, dict):
        return f"answered {type(answer).__name__}, expected a dict"
    for key in ("packages", "imports", "entry_points", "symbols"):
        if key in answer and not _list_of(answer[key], dict):
            return f"key {key} is no list of dicts"
    return ""


# The shape checks `samples` name: each takes the answer and returns "" when it fits or one line saying why not.
SHAPES = {
    "str": lambda a: _expect(isinstance(a, str), a, "a string"),
    "list": lambda a: _expect(isinstance(a, list), a, "a list"),
    "list_of_str": lambda a: _expect(_list_of(a, str), a, "a list of strings"),
    "suffixes": lambda a: _expect(_list_of(a, str) and a and all(x.startswith(".") for x in a), a,
                                  "a list of suffixes such as '.foo'"),
    "module": lambda a: _expect(isinstance(a, type(sys)), a, "a module"),
    "tools": _tools_problem,
    "adapter": _adapter_problem,
    "mapping": _mapping_problem,
}
Target = collections.namedtuple("Target", "forge host project")
MANY = ("mcp_tools", "backlog_commands")
MARK = "KBEXT-VERIFY "


def _sample_repo(tmp):
    """A repository with one empty commit under TMP: its path and the commit."""
    repo = Path(tmp) / "repo"
    repo.mkdir()
    for args in (("init", "-q"), ("-c", "user.name=kbext", "-c", "user.email=kbext@corp.example.com",
                                   "-c", "commit.gpgsign=false", "commit", "--allow-empty", "-q", "-m", "sample")):
        if _git(repo, *args)[0]:
            raise ExtensionError(f"cannot make the sample repository: git {args[0]} failed")
    return str(repo), _git(repo, "rev-parse", "HEAD")[1].strip()


def _sample_objects(tmp, root):
    """{placeholder: factory} for the strings the samples' arguments may hold."""
    made = {}

    def once(name, make):
        if name not in made:
            made[name] = make()
        return made[name]

    def empty():
        path = Path(tmp) / "empty"
        path.mkdir()
        return str(path)

    return {"$EMPTY": lambda: once("$EMPTY", empty),
            "$REPO": lambda: once("repo", lambda: _sample_repo(tmp))[0],
            "$SHA": lambda: once("repo", lambda: _sample_repo(tmp))[1],
            "$TARGET": lambda: Target("gitlab", "gitlab.corp.example.com", "group/project"),
            "$RUN": lambda: (lambda argv, cwd=None: (1, "", "kbext verify runs no command")),
            "$CWD": lambda: str(root)}


def _fill(value, objects):
    if isinstance(value, str) and value in objects:
        return objects[value]()
    if isinstance(value, list):
        return [_fill(v, objects) for v in value]
    return value


def _run_sample(sample, extender, module, objects):
    """One sample's answer shape problem ("" when it fits); an ExtensionError for a call that cannot be made."""
    name = sample.get("call", sample.get("value", ""))
    holders = [h for h in (extender, module) if not name or hasattr(h, name)]
    if not holders:
        raise ExtensionError(f"no attribute {name}")
    target = getattr(holders[0], name) if name else extender
    if "call" in sample:
        if not callable(target):
            raise ExtensionError(f"{name or 'the extender'} is not callable")
        try:
            target = target(*_fill(sample["args"], objects))
        except ExtensionError:
            raise
        except Exception as e:
            raise ExtensionError(f"{name or 'the extender'} raised {type(e).__name__}: {e}")
    return SHAPES[sample["shape"]](target)


def probe(point, spec, layer, file, root, kb_root=None):
    """(ok, one line) of the extender SPEC of POINT: it is loaded as `resolve` loads it and called with each sample of the
    point, and each answer is checked with the sample's shape. It runs in the child process `verify` starts."""
    entry = next((e for e in SURFACE["points"] if e["name"] == point), None)
    if entry is None:
        return False, (f"point {point}: module {spec.partition(':')[0]}, layer {layer} ({file}): "
                       f"not an extension point of kbext.SURFACE")
    try:
        _add_paths(root, kb_root)
        spec = spec if point != "ingest_mappers" or ":" in spec else spec + ":mapper"
        if point == "backlog_commands":  # backlog.py imports it with the shipped commands registered: so does the probe
            import backlog  # noqa: F401 - registers every shipped command
            import bl_cli
            with bl_cli.group_loading(root, layer):
                found = _import(point, spec, layer, file)
        else:
            found = _import(point, spec, layer, file)
        with tempfile.TemporaryDirectory() as tmp:
            objects = _sample_objects(tmp, root)
            for sample in entry["samples"]:
                try:
                    problem = _run_sample(sample, found["extender"], found["module"], objects)
                except ExtensionError as e:
                    raise ExtensionError(f"{found['where']}: {e}")
                if problem:
                    raise ExtensionError(f"{found['where']}: {problem}")
    except ExtensionError as e:
        return False, " ".join(str(e).split())
    return True, f"{point} {spec} (layer {layer}, file {file})"


def probe_main():
    """The child process of `verify`: reads the job as JSON on stdin and prints `MARK` and the JSON `[ok, line]`."""
    job = json.load(sys.stdin)
    ok, line = probe(job["point"], job["spec"], job["layer"], job["file"], job["root"], job["kb_root"])
    print(MARK + json.dumps([ok, line]))


def _configured_extenders(root, kb_root):
    """[(point, spec or None, layer, file, problem)] for every extender the settings layers name under `extensions`:
    the points of `SURFACE` in its order, then any other key; PROBLEM is set for a value that names no extender."""
    try:
        merged, _ = kbsettings.layered(root, "extensions", kb_root)
    except kbsettings.SettingsError as e:
        raise ExtensionError(str(e))
    order = [e["name"] for e in SURFACE["points"]]
    found = []
    for point in [p for p in order if p in merged] + sorted(set(merged) - set(order)):
        value, layer, file = _named(root, kb_root, "extensions", point)
        if point == "ingest_mappers" and isinstance(value, dict):
            specs = [value[k] for k in sorted(value)]
        else:
            specs = value if point in MANY and isinstance(value, list) else [value]
        wanted = ("an object: language to module:attr" if point == "ingest_mappers"
                  else "module:attr or a module name" + (" or a list of them" if point in MANY else ""))
        if not specs or not all(isinstance(s, str) and s for s in specs):
            found.append((point, None, layer, file, f"extensions.{point} must be {wanted}"))
        found += [(point, s, layer, file, "") for s in specs if isinstance(s, str) and s]
    return found


def verify(root, kb_root=None, timeout=30.0):
    """(exit code, lines) of the check of every extender the settings layers of ROOT name: one line each, `ok  ...` or
    `FAIL  point POINT: module MODULE, layer LAYER (FILE): why`, each extender probed in a child process of its own that
    TIMEOUT seconds bound; exit 1 when any line is a FAIL, else 0 (also with none configured)."""
    try:
        extenders = _configured_extenders(root, kb_root)
    except ExtensionError as e:
        return 1, [f"FAIL  {' '.join(str(e).split())}"]
    if not extenders:
        return 0, [f"kbext verify: no extender is configured in the settings layers of {root}"]
    lines, failed = [], False
    run = [sys.executable, "-c", "import sys; sys.path.insert(0, sys.argv[1]); import kbext; kbext.probe_main()",
           str(Path(__file__).resolve().parent)]
    for point, spec, layer, file, problem in extenders:
        where = f"point {point}: module {(spec or '').partition(':')[0] or '?'}, layer {layer} ({file})"
        if problem:
            ok, line = False, f"{where}: {problem}"
        else:
            job = json.dumps({"point": point, "spec": spec, "layer": layer, "file": file, "root": str(root),
                              "kb_root": kb_root})
            try:
                p = subprocess.run(run, input=job, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                   cwd=root if Path(root).is_dir() else None, timeout=timeout)
                answers = [json.loads(l[len(MARK):]) for l in p.stdout.splitlines() if l.startswith(MARK)]
                if answers:
                    ok, line = answers[-1]
                else:
                    last = next((l for l in reversed(p.stderr.splitlines()) if l.strip()), "no output")
                    ok, line = False, f"{where}: the child process exited {p.returncode}: {last.strip()[:200]}"
            except subprocess.TimeoutExpired:
                ok, line = False, f"{where}: no answer within {timeout:g} s"
            except OSError as e:
                ok, line = False, f"{where}: the child process cannot be started: {e}"
        failed |= not ok
        lines.append(f"ok    {line}" if ok else f"FAIL  {line}")
    return (1 if failed else 0), lines


SAMPLE_RANKER = '''"""The group's sample ranker: puts the candidates whose path holds most words of the question first."""
KBEXT_REQUIRES = ">=0.1"


def rank(question, candidates):
    words = [w for w in question.lower().split() if len(w) > 2]
    return sorted(candidates, key=lambda path: -sum(w in path.lower() for w in words))
'''
GROUP_NAME_RE = re.compile(r"[a-z][a-z0-9]*(-[a-z0-9]+)*")


def _json_text(value):
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def _team_files(group, upstream, ref):
    """{relative path: text} of the files `init-team` writes for the group GROUP."""
    plugins = [{"name": "it-ops-kb", "source": {"source": "url", "url": upstream, "ref": ref},
                "description": f"it-ops-kb at {ref}, the extension API tag the group has verified"},
               {"name": group, "source": ".", "description": f"{group}'s own skills, agents and hooks"}]
    return {".claude-plugin/marketplace.json": _json_text({"name": f"{group}-kb", "owner": {"name": group},
                                                           "plugins": plugins}),
            ".claude-plugin/plugin.json": _json_text({"name": group, "description": f"{group}'s own skills, agents and "
                                                      f"hooks beside it-ops-kb"}),
            "skills/.gitkeep": "", "agents/.gitkeep": "", "hooks/hooks.json": _json_text({"hooks": {}}),
            "settings/group.json": _json_text({"group": group, "extension_paths": ["../ext"],
                                               "extensions": {"ranker": "group_ranker:rank"}}),
            "ext/group_ranker.py": SAMPLE_RANKER}


def init_team(dest, group, upstream, ref):
    """(exit code, lines) of writing a group's overlay repository into the directory DEST: a marketplace that pins it-ops-kb
    at the tag REF of UPSTREAM beside the plugin of GROUP, that plugin's manifest and its `skills`, `agents` and `hooks`
    directories, `settings/group.json` and a sample ranker in `ext/`. A file that is there with the same text is left
    alone; one that holds other text, or a directory in its place, exits 2 naming each such file and nothing is written."""
    if not GROUP_NAME_RE.fullmatch(group) or group == "it-ops-kb":
        return 2, [f"init-team: --group {group!r}: a name of lower-case letters, digits and single hyphens, not it-ops-kb"]
    if not upstream.strip() or any(c.isspace() for c in upstream) or not ref.strip() or any(c.isspace() for c in ref):
        return 2, ["init-team: --upstream and --ref must be non-empty and hold no white space"]
    dest, files = Path(dest), _team_files(group, upstream, ref)
    held = []
    for rel, text in files.items():
        path = dest / rel
        try:
            if path.exists() and (not path.is_file() or path.read_text(encoding="utf-8") != text):
                held.append(rel)
        except (OSError, UnicodeDecodeError):
            held.append(rel)
    if held:
        return 2, [f"init-team: {rel} holds other content and is not overwritten" for rel in held]
    lines = []
    for rel, text in files.items():
        path = dest / rel
        if path.exists():
            lines.append(f"unchanged  {rel}")
            continue
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
        except OSError as e:
            return 2, lines + [f"init-team: cannot write {rel}: {e.strerror or type(e).__name__}"]
        lines.append(f"wrote      {rel}")
    return 0, lines


REHEARSE_SCRIPTS = ("kbgit", "kbroot", "kbext")  # the tools a rehearsal runs from the clone: a plant holds these and what they import
ISOLATED = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
            "PYTHONDONTWRITEBYTECODE": "1"}


def _step(argv, cwd=None, env=None, isolate=True):
    """(exit code, output lines) of the command ARGV, stderr after stdout; (127, [reason]) when it cannot be started.
    With ISOLATE no global or system git config applies and no bytecode is written."""
    try:
        p = subprocess.run([str(a) for a in argv], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env={**os.environ, **(ISOLATED if isolate else {}), **(env or {})})
    except OSError as e:
        return 127, [f"{argv[0]}: cannot be started: {e.strerror or type(e).__name__}"]
    return p.returncode, [l for l in (p.stdout + p.stderr).splitlines() if l.strip()]


def _gitc(repo, *args):
    """git in REPO with a fixed author and no signing: (exit code, output lines)."""
    return _step(["git", "-c", "user.name=kbext", "-c", "user.email=kbext@corp.example.com", "-c",
                  "commit.gpgsign=false", "-C", repo, *args])


def _import_closure(tools, names):
    """The module names under the directory TOOLS that the modules NAMES import, directly or not, NAMES included."""
    seen, todo = set(), list(names)
    while todo:
        name = todo.pop()
        path = Path(tools) / f"{name}.py"
        if name in seen or not path.is_file():
            continue
        seen.add(name)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                todo += [a.name.partition(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                todo.append(node.module.partition(".")[0])
    return seen


def _next_minor(version):
    major, minor, _ = _numbers(version)
    return f"{major}.{minor + 1}.0"


def plant(dest, broken=False):
    """(url, from tag, to tag) of an upstream repository built in the directory DEST from the running checkout: two commits
    on `main`, the first tagged `ext-v<API_VERSION>` and the second, which sets API_VERSION to the next minor and adds its
    changelog entry, tagged with that. The tree is the tracked `_tools` files that kbgit.py, kbroot.py and kbext.py import
    and the data files beside them (no tests, no fixtures) and the changelog. With BROKEN the second commit also removes
    the `ranker` point from `SURFACE` and keeps its API version a minor, so no deprecation or major version covers it."""
    home = Path(__file__).resolve().parent.parent
    code, listed = _step(["git", "-C", home, "ls-files", "--", "_tools", CHANGELOG])
    if code:
        raise ExtensionError(f"--plant needs a git checkout of the kb with tracked _tools files: {home}")
    want = _import_closure(home / "_tools", REHEARSE_SCRIPTS)
    keep = [p for p in listed if (home / p).is_file() and "/fixtures/" not in p and not Path(p).name.startswith("tests_")
            and (p == CHANGELOG or not p.endswith(".py") or Path(p).stem in want)]
    dest = Path(dest)
    dest.mkdir(parents=True)
    for rel in keep:
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(home / rel, dest / rel)
    first, second = f"ext-v{API_VERSION}", f"ext-v{_next_minor(API_VERSION)}"
    log = dest / CHANGELOG
    if not log.is_file():
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(f"# Extension API changelog\n\n## {API_VERSION}\n\nThe planted first release.\n", encoding="utf-8",
                       newline="\n")
    steps = [("init", "-q", "-b", "main"), ("add", "-A"), ("commit", "-q", "-m", f"plant: it-ops-kb at {first}"),
             ("tag", first)]
    for args in steps:
        if _gitc(dest, *args)[0]:
            raise ExtensionError(f"--plant: git {args[0]} failed in the planted upstream")
    source = dest / SOURCE
    text = source.read_text(encoding="utf-8")
    text, n = re.subn(r'^API_VERSION = "[^"]*"', f'API_VERSION = "{_next_minor(API_VERSION)}"', text, count=1, flags=re.M)
    if broken:
        start = text.find('        {"name": "ranker"')
        end = text.find('        {"name": ', start + 1)
        if start < 0 or end < 0:
            raise ExtensionError("--plant --break: the ranker point is not in SURFACE as a block of its own")
        text = text[:start] + text[end:]
    if not n:
        raise ExtensionError(f"--plant: no API_VERSION line in {SOURCE}")
    source.write_text(text, encoding="utf-8", newline="\n")
    with log.open("a", encoding="utf-8", newline="\n") as f:
        f.write(f"\n## {_next_minor(API_VERSION)}\n\nThe planted next minor release{' without the ranker point' if broken else ''}.\n")
    for args in (("add", "-A"), ("commit", "-q", "-m", f"plant: the next minor at {second}"), ("tag", second)):
        if _gitc(dest, *args)[0]:
            raise ExtensionError(f"--plant: git {args[0]} failed in the planted upstream")
    return str(dest), first, second


def _tag_commit(repo, tag):
    code, out = _step(["git", "-C", repo, "rev-parse", "--verify", "-q", f"refs/tags/{tag}^{{commit}}"])
    return out[0] if not code and out else None


def _rehearse_in(tmp, upstream, frm, to, team, fork):
    """(exit code, lines) of the rehearsal that works in the directory TMP; see `rehearse`."""
    team = Path(team).resolve()
    group_file = team / "settings" / "group.json"
    try:
        group = json.loads(group_file.read_text(encoding="utf-8")).get("group")
    except (OSError, ValueError, AttributeError) as e:
        return 2, [f"rehearse: {group_file} cannot be read as the group's settings: {e}"]
    if not isinstance(group, str) or not GROUP_NAME_RE.fullmatch(group):
        return 2, [f"rehearse: {group_file} has no `group` name of lower-case letters, digits and hyphens"]
    lines = [f"rehearse: upstream {upstream}, {frm} to {to}, group {group} ({group_file})"]
    src, clone = tmp / "src.git", tmp / "clone"
    code, out = _step(["git", "clone", "-q", "--bare", upstream, src], isolate=False)  # the user's git config: credentials
    if code:
        return 2, lines + [f"rehearse: git clone of {upstream} failed: {out[-1] if out else code}"]
    old, new = _tag_commit(src, frm), _tag_commit(src, to)
    for tag, sha in ((frm, old), (to, new)):
        if sha is None:
            return 2, lines + [f"rehearse: the upstream has no tag {tag}"]
    for args in (("symbolic-ref", "HEAD", "refs/heads/main"), ("update-ref", "refs/heads/main", old)):
        if _gitc(src, *args)[0]:
            return 2, lines + [f"rehearse: git {args[0]} failed in the upstream copy"]
    if _gitc(tmp, "clone", "-q", "--origin", "upstream", src, clone)[0]:
        return 2, lines + ["rehearse: the clone at the first tag failed"]
    for key, value in (("kb.scope", "team"), ("kb.upstreamRemote", "upstream"), ("user.name", "kbext"),
                       ("user.email", "kbext@corp.example.com"), ("commit.gpgsign", "false")):
        if _gitc(clone, "config", key, value)[0]:
            return 2, lines + [f"rehearse: git config {key} failed"]
    lines.append(f"cloned the upstream at {frm}; settings: KB_GROUP_SETTINGS={group_file}")
    py = sys.executable
    if fork:
        prefix = "".join(c for c in group.upper() if c.isalpha())[:4]
        add = ["kbroot.py", "add", group, "--prefix", prefix, "--description", f"{group}'s own knowledge"]
        code, out = _step([py, clone / "_tools" / add[0], *add[1:]], cwd=clone)
        lines.append(f"fork commit: python3 _tools/{' '.join(add)}: exit {code}")
        if code or _gitc(clone, "add", "-A")[0] or _gitc(clone, "commit", "-q", "-m", f"feat: add the group root {group}")[0]:
            return 2, lines + [f"  {l}" for l in out[-3:]] + ["rehearse: the planted fork commit could not be made"]
    code, out = _step(["git", "-C", clone, "diff", "--name-status", "--no-renames", old])
    shipped = sorted({l.split("\t", 1)[1] for l in out if l[:1] in "MDT" and "\t" in l}) if not code else None
    if shipped is None:
        return 2, lines + ["rehearse: git diff of the group's setup failed"]
    lines.append(f"shipped files the group's setup changed ({len(shipped)}): " + (", ".join(shipped) or "none"))
    if _gitc(src, "update-ref", "refs/heads/main", new)[0]:
        return 2, lines + ["rehearse: the upstream copy cannot move main to the second tag"]
    code, out = _step([py, clone / "_tools" / "kbgit.py", "upstream"], cwd=clone)
    lines.append(f"python3 _tools/kbgit.py upstream (take {to}): exit {code}")
    lines += [f"  {l}" for l in out]
    conflicts = []
    if code == 3:
        conflicts = sorted(set(_step(["git", "-C", clone, "diff", "--name-only", "--diff-filter=U"])[1]))
    elif code:
        return 2, lines + ["rehearse: kbgit.py upstream could not take the second tag"]
    lines.append(f"conflicting paths ({len(conflicts)}): " + (", ".join(conflicts) or "none"))
    failed = []
    if conflicts or code:
        failed.append("a conflict")
        lines.append("verify: skipped, the bring-in left a conflict in progress")
    else:
        vcode, vout = _step([py, clone / "_tools" / "kbext.py", "verify", "--root", clone],
                            env={"KB_GROUP_SETTINGS": str(group_file)})
        lines.append(f"python3 _tools/kbext.py verify --root CLONE (the clone at {to}): exit {vcode}")
        lines += [f"  {l}" for l in vout]
        if vcode:
            failed.append("an extender that no longer verifies")
    if shipped:
        failed.append("a shipped file the group's setup changed")
    lines.append("rehearse: " + (f"failed, {', '.join(failed)}" if failed else
                                 f"ok, no conflict, no shipped file changed, every extender verified from {frm} to {to}"))
    return (1 if failed else 0), lines


def rehearse(upstream, frm, to, team, fork=False, planted=False, broken=False):
    """(exit code, lines) of a dry run of a group's upgrade from the upstream tag FROM to the tag TO, in temporary
    directories this removes: the upstream is cloned at FROM (the copy of a `plant`ed upstream with PLANTED, whose two tags
    FROM and TO are then the planted ones and BROKEN removes the ranker point from the second), the group's settings at
    TEAM/settings/group.json are the group layer, with FORK a commit that adds the group's root by `kbroot.py add` is made,
    and the clone's own `kbgit.py upstream` takes TO. The lines name the conflicting paths, the shipped files the group's
    setup changed and the lines of the clone's `kbext.py verify`. Exit 0 with no conflict, no shipped file changed and every
    extender verified, 1 otherwise, 2 for a rehearsal that could not be made."""
    tmp = Path(tempfile.mkdtemp(prefix="kbext-rehearse-"))

    def forget(func, path, _):
        try:
            os.chmod(path, 0o700)
            func(path)
        except OSError:
            pass
    try:
        if planted:
            try:
                upstream, frm, to = plant(tmp / "plant", broken)
            except ExtensionError as e:
                return 2, [f"rehearse: {e}"]
        return _rehearse_in(tmp, upstream, frm, to, team, fork)
    finally:
        shutil.rmtree(tmp, onerror=forget)


def main(argv=None):
    ap = argparse.ArgumentParser(description="A group's extenders for the kb's extension points.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("surface", help="print API_VERSION and the public extension API (points and settings keys)")
    sp.add_argument("--json", action="store_true", dest="as_json", help="print one JSON object")
    sp = sub.add_parser("lint", help="refuse a break of the public extension API since the newest ext-v tag")
    sp.add_argument("--root", default=".", help="the repository (default: the working directory)")
    sp = sub.add_parser("init-team", help="write a group's overlay repository: a marketplace pinning it-ops-kb by ext tag, "
                                          "the group's plugin, its settings file and a sample ranker")
    sp.add_argument("dir", help="the overlay repository's directory (made when missing)")
    sp.add_argument("--group", required=True, help="the group's name: lower-case letters, digits and hyphens")
    sp.add_argument("--upstream", required=True, help="the git url of it-ops-kb the marketplace pins")
    sp.add_argument("--ref", default=f"ext-v{API_VERSION}", help="the ext tag to pin (default: ext-v%s)" % API_VERSION)
    sp = sub.add_parser("rehearse", help="dry-run a group's upgrade from one upstream ext tag to the next in temporary "
                                         "directories: conflicts, shipped files changed, extenders verified")
    sp.add_argument("--team", required=True, help="the group's overlay repository (init-team's): its settings/group.json")
    sp.add_argument("--upstream", help="the git url of it-ops-kb (not with --plant)")
    sp.add_argument("--from", dest="from_tag", metavar="TAG", help="the ext tag the group is at (not with --plant)")
    sp.add_argument("--to", dest="to_tag", metavar="TAG", help="the ext tag to take (not with --plant)")
    sp.add_argument("--fork", action="store_true", help="first commit a group root into the clone with kbroot.py add")
    sp.add_argument("--plant", action="store_true", help="build the upstream from this checkout's tracked tools as two "
                                                         "commits tagged ext-v<API_VERSION> and the next minor")
    sp.add_argument("--break", action="store_true", dest="broken", help="with --plant: the second commit removes the "
                                                                         "ranker point, keeping its API version a minor")
    sp = sub.add_parser("guards", help="print each shipped guard a group's extender replaces and the leak shapes it added")
    sp.add_argument("--root", required=True, help="the workspace directory (holds settings.json)")
    sp.add_argument("--kb-root", help="a kb root's name: kb/NAME/settings.json is a layer too")
    sp = sub.add_parser("verify", help="call each configured extender with its point's samples and check the answers")
    sp.add_argument("--root", required=True, help="the workspace directory (holds settings.json)")
    sp.add_argument("--kb-root", help="a kb root's name: kb/NAME/settings.json is a layer too")
    sp.add_argument("--timeout", type=float, default=30.0, metavar="S", help="seconds each extender may take (default 30)")
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
    if args.cmd == "lint":
        code, lines = lint(args.root)
        print("\n".join(lines))
        return code
    if args.cmd == "init-team":
        code, lines = init_team(args.dir, args.group, args.upstream, args.ref)
        print("\n".join(lines), file=sys.stderr if code else sys.stdout)
        return code
    if args.cmd == "rehearse":
        if args.plant == bool(args.upstream or args.from_tag or args.to_tag):
            ap.error("give --plant, or --upstream with --from and --to, not both and not neither")
        if not args.plant and not (args.upstream and args.from_tag and args.to_tag):
            ap.error("--upstream, --from and --to go together")
        if args.broken and not args.plant:
            ap.error("--break goes with --plant")
        code, lines = rehearse(args.upstream, args.from_tag, args.to_tag, args.team, args.fork, args.plant, args.broken)
        print("\n".join(lines), file=sys.stderr if code == 2 else sys.stdout)
        return code
    if args.cmd == "guards":
        try:
            print("\n".join(guard_lines(args.root, args.kb_root)))
        except ExtensionError as e:
            print(f"kbext: {' '.join(str(e).split())}", file=sys.stderr)
            return 2
        return 0
    if args.cmd == "verify":
        if Path(args.root).exists() and not Path(args.root).is_dir():
            ap.error(f"--root {args.root}: not a directory")
        if not args.timeout > 0:
            ap.error("--timeout must be above 0")
        code, lines = verify(args.root, args.kb_root, args.timeout)
        print("\n".join(lines))
        return code
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
