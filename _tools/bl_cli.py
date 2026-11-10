"""The subcommand registry of backlog.py (kb/_self/backlog.md, Working on items; kb/_self/tools.md): each module that
owns a command registers its parser and its handler here when it is imported, `backlog.py` puts the registry in its
usage order (`order`), and `backlog.main` builds the parser from the registry and dispatches, so a new subcommand
adds a `register` call in its module, its name in backlog.py's USAGE and no line to `main`.

Standard library only; imports `bl_base` (for `COMMITS` and the project settings) and never `backlog`."""
import argparse
import inspect
import os
import re
import subprocess
import sys
from pathlib import Path

from bl_base import COMMITS, kinds, withhold

COMMANDS = {}  # subcommand name -> (handler, add_arguments, help), in registration order
GROUP = {}  # command name -> module of the group that added or replaced it (`load_group_commands`)
_LOADING = []  # (layer, group name) while the group's modules are imported: their register and extend calls are the group's


def _note(text):
    print(withhold(f"backlog.py: {text}"), file=sys.stderr)


def _caller():
    """The name of the module that called `register` or `extend`: the group module being imported."""
    return sys._getframe(2).f_globals.get("__name__", "?")


def _group_of(name):
    """The module that holds the command `name` as a group command, or None for a shipped one."""
    return GROUP.get(name)


def _args_form(handler):
    """A group handler may take `(bl, args)` as a shipped one does or `(args)` alone: the one-parameter form is called
    with the arguments only."""
    try:
        params = list(inspect.signature(handler).parameters.values())
    except (TypeError, ValueError):
        return handler
    plain = [p for p in params if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    if len(plain) == 1 and not any(p.kind == p.VAR_POSITIONAL for p in params):
        return lambda bl, args: handler(args)
    return handler


def _noticed(name, handler, module, layer):
    """The handler that says, on stderr, once each time it runs, that a group module's command stands in for `name`."""
    def run(bl, args):
        _note(f"command {name} is the group's: module {module} replaces or extends it (layer {layer})")
        return handler(bl, args)
    return run


def _marked(help, group):
    return f"{help} [group {group}]" if help else f"[group {group}]"


def register(name, handler, add_arguments=None, help=None, registry=None):
    """Add the subcommand `name`: `handler(bl, args)` runs it, `add_arguments(parser)` gives its parser its
    arguments (a command with none passes nothing), `help` is the line the top-level usage shows for it (none by
    default). A name registered twice is refused. Called from a group module (`load_group_commands`), the handler may
    take `(args)` alone, a name that a shipped command or another module holds is replaced, running the replacement
    prints one stderr line naming the command, the module and the layer, and `help` is marked with the group's name."""
    if _LOADING and registry is None:
        (layer, group), module = _LOADING[-1], _caller()
        if _group_of(name) == module:
            raise ValueError(f"subcommand {name!r} is registered twice")
        handler = _args_form(handler)
        if name in COMMANDS:
            handler = _noticed(name, handler, module, layer)
        COMMANDS[name] = (handler, add_arguments, _marked(help, group))
        GROUP[name] = module
        return
    registry = COMMANDS if registry is None else registry
    if name in registry:
        raise ValueError(f"subcommand {name!r} is registered twice")
    registry[name] = (handler, add_arguments, help)


def extend(name, wrap, add_arguments, registry=None):
    """Add options to the registered subcommand `name`: `add_arguments(parser)` gives its parser the extra arguments
    after its own, and `wrap(handler)` returns the handler that runs in its place (it calls `handler` for the
    original behaviour). A command that is not registered is refused. Called from a group module, it replaces a
    command that is not the module's own as `register` does: one stderr line each time it runs, the help marked."""
    group_call = bool(_LOADING) and registry is None
    registry = COMMANDS if registry is None else registry
    if name not in registry:
        raise ValueError(f"subcommand {name!r} is not registered")
    handler, own, help = registry[name]

    def both(p):
        if own:
            own(p)
        add_arguments(p)

    new = wrap(handler)
    if group_call:
        (layer, group), module = _LOADING[-1], _caller()
        if _group_of(name) != module:
            new = _noticed(name, new, module, layer)
            help = _marked(help, group) if _group_of(name) is None else help
            GROUP[name] = module
    registry[name] = (new, both, help)


def order(names, registry=None):
    """Put the registry in the usage order `names` (backlog.py's USAGE), which must name each registered command once:
    the modules register at import, in import order, and the usage text keeps its own order."""
    registry = COMMANDS if registry is None else registry
    if sorted(names) != sorted(registry) or len(set(names)) != len(names):
        missing, extra = sorted(set(registry) - set(names)), sorted(set(names) - set(registry))
        raise ValueError(f"usage order and registry differ: not in the order {missing}, not registered {extra}")
    items = {n: registry[n] for n in names}
    registry.clear()
    registry.update(items)


def build_parser(description, root, registry=None):
    """The top-level parser with one subparser for each registered command, in registration order; a command that
    commits the item files it wrote (`bl_base.COMMITS`) also gets `--commit` and `--trailer`."""
    registry = COMMANDS if registry is None else registry
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--root", default=root)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, (handler, add_arguments, help) in registry.items():
        p = sub.add_parser(name, **({} if help is None else {"help": help}))
        if add_arguments:
            add_arguments(p)
        if name in COMMITS:
            p.add_argument("--commit", action="store_true",
                           help="commit the item files this command wrote, and only them, with a fixed subject and KB-Work")
            p.add_argument("--trailer", action="append", default=[], metavar="'KEY: VALUE'",
                           help="a trailer of the session's own after KB-Work in the commit (--commit only; repeatable)")
    return ap


def id_shape():
    """The project's id prefixes (the settings of the root the command runs on) with the id's 8 characters."""
    return re.compile("(?:" + "|".join(kinds().values()) + r")-[a-z2-7]{8}")


ID_LIST_OPTIONS = ("--depends", "--add-depends", "--relates", "--add-relates")  # one id per flag in the parsers
# A command agents reach for that the backlog does not have: what to run instead.
NO_COMMAND = {
    "repro": "a bug's repro: `backlog.py show ID` prints it, `backlog.py done ID --dry-run` runs it",
    "gates": "gates: `backlog.py show ID` lists an item's, `backlog.py horizon --sprint ID` what waits on which",
}
EXTRA_HINT = {
    "check": "check validates every item and takes no id: run `backlog.py check`; one item: `backlog.py show ID`",
    "show": "show takes one id: run it once per id",
}


def command_of(argv):
    """The subcommand word of an argv: its first word that is no option and no `--root` value."""
    skip = False
    for w in argv:
        if skip:
            skip = False
        elif w == "--root":
            skip = True
        elif not w.startswith("-"):
            return w
    return None


def spread_ids(argv):
    """`--depends A B C` as `--depends A --depends B --depends C`: the ids that follow an id-list option's value, each
    given its own flag; any other word ends the run."""
    out, opt, after_value = [], None, False
    shape = id_shape()
    for w in argv:
        if w in ID_LIST_OPTIONS:
            out.append(w)
            opt, after_value = w, False
        elif opt and not after_value:
            out.append(w)
            after_value = True
        elif opt and shape.fullmatch(w):
            out += [opt, w]
        else:
            out.append(w)
            opt = None
    return out


def root_of(argv, default):
    """The root a command line runs on: the value of `--root` (before the command, as the parser takes it, in either
    spelling) or DEFAULT. Read before the parser is built, since the project's settings (the kinds the parsers
    offer) are those of that root."""
    skip = False
    for w in argv:
        if skip:
            return w
        if w == "--root":
            skip = True
        elif w.startswith("--root="):
            return w[len("--root="):]
        elif not w.startswith("-"):
            break
    return default


def default_root(tool_root, cwd=None):
    """The root a command runs on when `--root` is not given: the git toplevel of the working directory, which is
    the project, unless the tool's own checkout is a git working tree (the kb's clone, or a worktree of it) and the
    working directory is in that clone or one of its worktrees, where it is the tool's own checkout; TOOL_ROOT when
    the working directory is no repository. A working directory whose nearest `.git` is the tool's own checkout needs
    no git process, which the hooks that start `backlog.py` on every session rely on."""
    def git(*args, at):
        try:
            p = subprocess.run(["git", *args], cwd=at, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=30)
        except (OSError, subprocess.SubprocessError):
            return ""
        return p.stdout.strip() if p.returncode == 0 else ""

    own = (Path(tool_root) / ".git").exists()
    if own and not os.environ.get("GIT_DIR") and not os.environ.get("GIT_WORK_TREE"):
        here = Path(os.path.realpath(cwd or os.getcwd()))
        nearest = next((p for p in (here, *here.parents) if (p / ".git").exists()), None)
        if nearest is not None and nearest == Path(os.path.realpath(tool_root)):
            return str(tool_root)
    top = git("rev-parse", "--show-toplevel", at=cwd)
    if not top:
        return str(tool_root)
    if own:
        def common(at):
            d = git("rev-parse", "--git-common-dir", at=at)
            return os.path.realpath(os.path.join(at, d)) if d else ""

        own_common = common(tool_root)
        if not own_common or common(top) == own_common:
            return str(tool_root)
    return top


def parse(ap, argv=None):
    """`ap.parse_args(argv)` with the usage errors agents repeat answered: several ids after one of
    ID_LIST_OPTIONS are each taken as given with its own flag (an accepted form); an id after `check` or a second
    one after `show` (EXTRA_HINT) and a command in NO_COMMAND are refused naming what to run instead (exit 2)."""
    argv = sys.argv[1:] if argv is None else list(argv)
    cmd = command_of(argv)
    if cmd in NO_COMMAND and cmd not in COMMANDS:
        ap.error(f"no command {cmd!r}; {NO_COMMAND[cmd]}")
    a, extra = ap.parse_known_args(argv)
    if not extra:
        return a
    if all(id_shape().fullmatch(w) for w in extra) and any(w in ID_LIST_OPTIONS for w in argv):
        spread = spread_ids(argv)
        if spread != argv:
            b, rest = ap.parse_known_args(spread)
            if not rest:
                return b
    hint = EXTRA_HINT.get(a.cmd)
    ap.error(f"unrecognized arguments: {' '.join(extra)}" + (f"; {hint}" if hint else ""))


def handler_of(name, registry=None):
    registry = COMMANDS if registry is None else registry
    return registry[name][0]


def group_name(root):
    """The `group` name of the settings layers of ROOT (the last layer that sets one), `group` when none does."""
    import kbsettings
    try:
        layers = kbsettings.layer_files(root)
    except kbsettings.SettingsError:
        return "group"
    return next((d["group"] for _, _, d in reversed(layers) if isinstance(d.get("group"), str) and d["group"]), "group")


class group_loading:
    """The state `backlog.py` has while it imports a group's modules, for a caller that is not `backlog.py` (`kbext.py
    verify`, which imports `backlog` first so the shipped commands are registered): inside the `with`, a module's
    `register` and `extend` calls count as the group's, in LAYER, as `load_group_commands` makes them. On leaving, the
    registry and the group marks are as they were."""

    def __init__(self, root, layer):
        self.root, self.layer = root, layer

    def __enter__(self):
        self.before = (dict(COMMANDS), dict(GROUP))
        _LOADING.append((self.layer, group_name(self.root)))
        return self

    def __exit__(self, *exc):
        _LOADING.pop()
        COMMANDS.clear(), GROUP.clear()
        COMMANDS.update(self.before[0]), GROUP.update(self.before[1])


def load_group_commands(root):
    """Import each module `extensions.backlog_commands` lists in the settings layers of ROOT, or, with no such setting, the
    module of the one entry point of group `it_ops_kb.backlog_commands` (`kbext` is imported only for one), after the shipped modules,
    through `kbext.load_all` (kb/_self/extending.md): a module adds or replaces commands through `register` and `extend`
    as it is imported, the module being the one that calls them. A module that `kbext` refuses (it cannot be imported,
    declares no API version this one meets, raises) is named on stderr with its layer and file and every command the
    group's modules registered is taken back, so the shipped commands run as before. Returns the loaded modules."""
    import kbsettings
    try:
        layers = kbsettings.layer_files(root)
        merged, source = kbsettings.layered(root, "extensions")
        paths = kbsettings.layered(root, "extension_paths")[0]
    except kbsettings.SettingsError as e:
        _note(f"group commands not loaded: {e}")
        return []
    if "backlog_commands" in merged:
        layer = source["backlog_commands"]
    else:
        from importlib import metadata  # kbext is imported only when a group installed an entry point of this point
        if paths:  # a distribution may sit under one of these directories: they are on sys.path before the look
            import kbext
            try:
                kbext.add_paths(root)
            except kbext.ExtensionError as e:
                _note(f"group commands not loaded: {e}")
                return []
        if not metadata.entry_points(group="it_ops_kb.backlog_commands"):
            return []
        layer = "entry point"
    import kbext
    group = group_name(root)
    before = (dict(COMMANDS), dict(GROUP))
    _LOADING.append((layer, group))
    try:
        return kbext.load_all("backlog_commands", root)
    except kbext.ExtensionError as e:
        COMMANDS.clear(), GROUP.clear()
        COMMANDS.update(before[0]), GROUP.update(before[1])
        _note(f"group commands not loaded: {e}")
        return []
    finally:
        _LOADING.pop()
