"""The subcommand registry of backlog.py (kb/_self/backlog.md, Working on items; kb/_self/tools.md): each module that
owns a command registers its parser and its handler here when it is imported, `backlog.py` puts the registry in its
usage order (`order`), and `backlog.main` builds the parser from the registry and dispatches, so a new subcommand
adds a `register` call in its module, its name in backlog.py's USAGE and no line to `main`.

Standard library only; imports `bl_base` (for `COMMITS`) and never `backlog`."""
import argparse
import re
import sys

from bl_base import COMMITS

COMMANDS = {}  # subcommand name -> (handler, add_arguments, help), in registration order


def register(name, handler, add_arguments=None, help=None, registry=None):
    """Add the subcommand `name`: `handler(bl, args)` runs it, `add_arguments(parser)` gives its parser its
    arguments (a command with none passes nothing), `help` is the line the top-level usage shows for it (none by
    default). A name registered twice is refused."""
    registry = COMMANDS if registry is None else registry
    if name in registry:
        raise ValueError(f"subcommand {name!r} is registered twice")
    registry[name] = (handler, add_arguments, help)


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


ID_SHAPE = re.compile(r"(?:EP|ST|TK|SB|BG|SP)-[a-z2-7]{8}")
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
    for w in argv:
        if w in ID_LIST_OPTIONS:
            out.append(w)
            opt, after_value = w, False
        elif opt and not after_value:
            out.append(w)
            after_value = True
        elif opt and ID_SHAPE.fullmatch(w):
            out += [opt, w]
        else:
            out.append(w)
            opt = None
    return out


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
    if all(ID_SHAPE.fullmatch(w) for w in extra) and any(w in ID_LIST_OPTIONS for w in argv):
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
