"""The subcommand registry of backlog.py (kb/_self/backlog.md, Working on items; kb/_self/tools.md): each module that
owns a command registers its parser and its handler here, `backlog.main` builds the parser from the registry in
registration order and dispatches, so a new subcommand adds a `register` call and no line to `main`.

Standard library only; imports `bl_base` (for `COMMITS`) and never `backlog`."""
import argparse

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


def handler_of(name, registry=None):
    registry = COMMANDS if registry is None else registry
    return registry[name][0]
