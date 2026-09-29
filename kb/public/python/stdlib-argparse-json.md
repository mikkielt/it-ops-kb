---
topic: python/stdlib-argparse-json
priority: P3
applies_to: [python, argparse, json]
retrieved_utc: 2026-09-29
sources: [S-w47ijsvq, S-zzvrhdyd]
status: complete
---

# stdlib argparse subcommands and json output (what this kb's command-line tools rely on)

## Summary
`_tools/` scripts are stdlib-only Python 3.11+ command-line programs that grow subcommands
(`set`, `add`, `show`) and read and write JSON. `argparse` gives one parser per subcommand, a way to
call the chosen handler, mutually exclusive option groups, and a fixed exit status 2 for a usage
error; `json.dumps` keeps dict order unless told to sort, escapes non-ASCII unless told not to, and
picks its separators from `indent`. Pages read at CPython 3.14.7.

## Facts
- `ArgumentParser.add_subparsers(*, title, description, prog, dest, required, help, metavar)` adds
  subcommands; `required` defaults to `False` (parameter added in 3.7), so without `required=True` a
  command line with no subcommand parses without error and the attribute is `None`. [DOC S-w47ijsvq]
- `dest='subparser_name'` on `add_subparsers` stores the chosen subcommand's name under that
  attribute (default: no value stored); `parser.parse_args(['2', 'frobble'])` then gives
  `Namespace(subparser_name='2', y='frobble')`. [DOC S-w47ijsvq]
- The documented way to run the chosen handler: `parser_foo.set_defaults(func=foo)` on each
  subparser, then call `args.func(args)` after `parse_args`; the docs call this "typically the
  easiest way to handle the different actions for each of your subparsers". [DOC S-w47ijsvq]
- `add_mutually_exclusive_group(required=False)` makes argparse check that at most one of its
  arguments is on the command line; giving two prints `PROG: error: argument --bar: not allowed with
  argument --foo`. With `required=True` at least one is needed, else `PROG: error: one of the
  arguments --foo --bar is required`. [DOC S-w47ijsvq]
- A mutually exclusive group takes no `title` or `description`, but can be added to an argument group
  that has them; calling `add_argument_group` or `add_mutually_exclusive_group` on a mutually exclusive
  group was deprecated in 3.11 and raises an exception from 3.14, the docs saying the nesting was never supported. [DOC S-w47ijsvq]
- `ArgumentParser.error(message)` prints the usage and the message to `sys.stderr` and terminates with
  status 2; this covers a missing required argument or subcommand and a mutually exclusive violation.
  `ArgumentParser.exit(status=0, message=None)` prints an optional message to `sys.stderr` and
  exits with `status`; a subclass may override it. [DOC S-w47ijsvq]
- An invalid argument list passed to `parse_args` prints a message to `sys.stderr` and exits with
  status 2; `exit_on_error=False` (added in 3.9) lets the caller catch `argparse.ArgumentError`
  instead. [DOC S-w47ijsvq]
- `default` is ignored for required arguments (positionals whose `nargs` is not `?` or `*`, and
  options with `required=True`). [DOC S-w47ijsvq]
- `json.dumps` and `json.dump` default to `sort_keys=False`, `ensure_ascii=True`, `indent=None` and
  `separators=None`; the module's encoder and decoder "preserve input and output order by default",
  so a dict serialises in its insertion order and order is lost only where the container is
  unordered. [DOC S-zzvrhdyd]
- `sort_keys=True` outputs dictionaries sorted by key; the docs give the use "regression tests to
  ensure that JSON serializations can be compared on a day-to-day basis". [DOC S-zzvrhdyd]
- `ensure_ascii=True` escapes all non-ASCII and non-printable characters; `False` outputs every
  character as is except quotation mark, reverse solidus and U+0000 to U+001F. [DOC S-zzvrhdyd]
- `indent` given as a positive integer indents that many spaces per level, a string (such as `"\t"`)
  is used per level, `0`, a negative number or `""` inserts only newlines, and `None` gives the most
  compact output. Strings for `indent` were added in 3.2. [DOC S-zzvrhdyd]
- `separators=None` means `(', ', ': ')` when `indent` is `None` and `(',', ': ')` otherwise (the
  no-trailing-space item separator since 3.4), so an indented dump has no trailing whitespace on
  lines; `separators=(',', ':')` gives the most compact form. [DOC S-zzvrhdyd]
- `json.dumps` does not write a trailing newline and `json.dump` writes to a text file object; the
  docs' examples do not add one, so a tool that writes a file and wants a final newline adds it
  itself. [DER S-zzvrhdyd: neither signature documents a newline parameter]

## Reference
- SNIPPET: subcommands with a handler, one exclusive group and stable JSON output; context: Python
  3.11+ stdlib; checked: syntax [DOC S-w47ijsvq: `add_subparsers(required=True)`, `set_defaults(func=...)`,
  `add_mutually_exclusive_group`; DOC S-zzvrhdyd: `sort_keys`, `indent`, `ensure_ascii`]
```python
import argparse
import json


def cmd_set(args):
    print(json.dumps({"id": args.id, "field": args.field}, sort_keys=True, indent=2, ensure_ascii=False))


parser = argparse.ArgumentParser(prog="tool")
sub = parser.add_subparsers(dest="cmd", required=True)
p_set = sub.add_parser("set")
p_set.add_argument("id")
group = p_set.add_mutually_exclusive_group(required=True)
group.add_argument("--field")
group.add_argument("--clear", action="store_true")
p_set.set_defaults(func=cmd_set)

args = parser.parse_args()  # usage errors exit with status 2
args.func(args)
```

## Examples
- A CLI whose new subcommand must fail with a message, not a traceback, on bad input calls
  `parser.error("...")` (status 2, usage on stderr) for argument-combination errors found after
  parsing, and `sys.exit(1)` or a custom status for runtime failures, keeping 2 for usage errors.
  [DER S-w47ijsvq: `error()` exits with 2; the split is our convention]
- A tool that rewrites a JSON file and must produce a small diff loads it (insertion order kept),
  changes one key and dumps with the same `indent` and `ensure_ascii` it was written with; adding
  `sort_keys=True` reorders keys of the whole file once. [DER S-zzvrhdyd]
