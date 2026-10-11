---
topic: python/typer-cli
priority: P3
applies_to: "Typer 0.27.3 (released 2026-10-06, Python 3.10+); Typer 0.26.0 and later vendor Click"
retrieved_utc: 2026-10-11
sources: [S-dnzxfcsw, S-ztkyr3zd, S-nw2nd4rv, S-syffw7l6, S-hrjguqt3, S-y3grqgpf, S-2txegwyx, S-5j3dqrn3, S-2qjh4vyl, S-tustm6ll, S-y5yampfx, S-fhhfxz7n, S-ioxs4z7o, S-4ykun7b2, S-dggjvarz, S-zzvrhdyd]
status: partial
---

# Typer CLIs: no prompt without a TTY, JSON output, exit codes

## Summary
Typer is a library for building command-line programs from type-annotated Python functions. This
article collects what Typer 0.27.3 documents and implements about prompts, termination and exit
codes, stdout versus stderr, Rich output, environment variables and testing, for a CLI that must
never wait on a prompt when there is no terminal and that prints JSON for scripts. No official page
defines "never prompt without a TTY" or a JSON output mode: those two behaviours are derived below
from the documented pieces and are marked `DER`. The repository's own pattern for JSON output from
a command-line tool is in `python/stdlib-argparse-json.md` and is not restated here.

## Facts
- Typer 0.27.3 was released on 2026-10-06; since 0.26.0 Typer no longer depends on Click as a
  third-party package but vendors (includes) Click's source, so Click-specific plug-ins and types
  are no longer supported. The release notes call this a breaking change in 0.26.0. [DOC S-5j3dqrn3]
- The Typer docs recommend asking for interactive input through a CLI option with a prompt rather
  than `typer.prompt()`, because options let the program also be used non-interactively (the page
  names a Bash script as the example). [DOC S-dnzxfcsw]
- `typer.Option(prompt=True)` asks for the value in the terminal only when it was not given on the
  command line; `prompt="some text"` customises the prompt text; `confirmation_prompt=True` makes the
  user type the value twice and re-asks on a mismatch (it is a repeat-to-confirm prompt, not a
  yes/no flag). [DOC S-ztkyr3zd]
- In the 0.27.3 code an option prompts only when its value source is "none" or "default", a prompt is
  set, and the option is required or `prompt_required` is true. [CODE S-tustm6ll: typer/core.py#TyperOption.consume_value]
- Because that check names only the "none" and "default" sources, and the parameter-source enum
  also has separate command-line and environment members, a value supplied through the command line
  or through `envvar=` is not prompted for: an environment variable is a way to answer a prompted
  option in an unattended run. [DER S-tustm6ll, S-ioxs4z7o: the consume_value condition and `ParameterSource` members]
- `typer.prompt()` and `typer.confirm()` read with Python's `input()` (or `getpass` for hidden
  input) and do not call `isatty`; on `EOFError` or `KeyboardInterrupt` they raise `Abort`. Their
  `err` parameter defaults to `False`, so the prompt text goes to stdout unless `err=True`. [CODE S-2qjh4vyl: typer/_click/termui.py#prompt, typer/_click/termui.py#confirm]
- `typer.confirm(..., abort=True)` raises `Abort` when the answer is no; the documented result is
  the text `Aborted!` after the command's own output. [DOC S-dnzxfcsw]
- `typer.Abort` (and an `EOFError` that escapes a command) ends the program with exit status 1 after
  writing `Aborted!` to stderr (plain, or through a Rich stderr console); `KeyboardInterrupt` ends
  it with `typer.Exit(130)`; `typer.Exit` and Click-style usage errors exit with the exception's own
  code. [CODE S-tustm6ll: typer/core.py#_main]
- `typer.Exit(code=...)` terminates the command and skips the code after it; `code` defaults to 0
  (success), a non-zero value signals an error, and the docs note that scripts that run the program
  can use that code. `typer.Abort` works like `Exit` but prints `Aborted!`. [DOC S-nw2nd4rv]
- Typer's rich-formatted usage errors and the abort message are printed on a Rich console created
  with `stderr=True`. [CODE S-fhhfxz7n: typer/rich_utils.py#rich_format_error]
- Rich ships with Typer by default, and the printing page shows writing to standard error by
  creating a Rich `Console` with `stderr=True`; it notes that PowerShell may not show standard
  error in the terminal. [DOC S-syffw7l6]
- `typer.echo()` is a small print helper; the docs advise plain `print()` or Rich instead for most
  uses, and warn that `echo` preserves terminal control sequences, so untrusted text should be
  escaped first; `color=False` disables styling but does not sanitise all control sequences.
  [DOC S-syffw7l6]
- Rich output is controlled globally with the `TYPER_USE_RICH` environment variable (read with
  default true); `pretty_exceptions_enable=False` on `typer.Typer()` turns pretty exceptions off, and
  `TYPER_STANDARD_TRACEBACK=1` forces the standard traceback for any Typer program. Local variables
  are not shown in pretty tracebacks by default since 0.23.0, to avoid leaking a password, key or
  token into CI logs. [DOC S-y3grqgpf]
- Typer's own colour handling forces a terminal when `GITHUB_ACTIONS`, `FORCE_COLOR` or `PY_COLORS`
  is set and disables it when `_TYPER_FORCE_DISABLE_TERMINAL` is set; the Typer source read does not
  reference `NO_COLOR`, and no page read says whether Rich or Typer honours it. [CODE S-fhhfxz7n: typer/rich_utils.py#FORCE_TERMINAL]
- `envvar=` lets a parameter fall back to an environment variable (a list tries several in order),
  command-line values take precedence, and the help shows `[env var: NAME]` unless
  `show_envvar=False`; the docs page shows this for `typer.Argument`. [DOC S-2txegwyx]
- `typer.Typer()` apps are nested with `add_typer`, as with `git remote`, to make subcommand groups.
  [DOC S-4ykun7b2]
- `typer.testing.CliRunner().invoke(app, ["arg", ...])` runs the app; `result.exit_code`,
  `result.stdout` and `result.stderr` are checked separately, and `input="text\n"` simulates stdin
  for prompts. [DOC S-hrjguqt3]
- Under `CliRunner` the prompt functions read from the supplied input stream and raise `EOFError`
  when it is exhausted, which becomes `Abort` and exit status 1; a test with no `input` therefore
  does not hang on a prompt. [CODE S-y5yampfx: typer/testing.py#CliRunner.isolation]
- `IOBase.isatty()` returns `True` if the stream is interactive, that is connected to a
  terminal/tty device (CPython 3.14.7 docs); `sys.stdin.isatty()` is the standard check. [DOC S-dggjvarz]
- "Never prompt without a TTY" is derived, not documented: Typer's prompts do not test `isatty` and
  simply call `input()`, so a command that must not wait has to test `sys.stdin.isatty()` itself and
  fail with a non-zero `typer.Exit` and a stderr message, or accept an explicit `--yes`-style bool
  option; with stdin closed or empty, the unguarded prompt ends in `Abort` and exit 1 rather than
  hanging. [DER S-dggjvarz, S-2qjh4vyl, S-tustm6ll: isatty definition, prompt code and Abort handling]
- JSON output is derived, not a Typer feature (none of the docs pages read has a JSON flag):
  serialise with `json.dumps` and write only that to stdout, send prompts and diagnostics to stderr
  (`err=True`), and signal failure by exit code. The Rich `print` shown in the printing page renders
  Python data with single-quoted keys, which is not valid JSON, so it is not a machine-output
  writer. [DER S-syffw7l6, S-zzvrhdyd, S-2qjh4vyl: `err` parameter, Rich print sample, json.dumps]
- A `--yes` option is not a documented Typer feature in the pages read; it is an ordinary bool
  option that the command checks before calling `typer.confirm`. [UNK]

## Reference
| Need | Typer 0.27.3 mechanism | Tag |
| --- | --- | --- |
| Ask only when value missing | `typer.Option(prompt=True)` | DOC |
| Type twice | `confirmation_prompt=True` | DOC |
| Yes/no, stop on no | `typer.confirm(msg, abort=True)` | DOC |
| Prompt text to stderr | `err=True` on `prompt`/`confirm` | CODE |
| Exit with a code | `raise typer.Exit(code=n)` | DOC |
| Abort (exit 1, "Aborted!") | `raise typer.Abort()` | DOC / CODE |
| Interrupt | exit 130 | CODE |
| Disable Rich | `TYPER_USE_RICH`, `pretty_exceptions_enable=False` | DOC |
| Test with stdin | `CliRunner().invoke(app, args, input="...\n")` | DOC |

## Examples
- SNIPPET: a command that never prompts without a terminal, prints JSON on stdout and diagnostics on stderr; context: Typer 0.27.3, Python 3.10+, `sys.stdin.isatty()`; checked: run [DER S-dggjvarz, S-2qjh4vyl, S-nw2nd4rv: isatty, `err=True`, `typer.Exit(code=)`]

```python
import json
import sys

import typer

app = typer.Typer()


@app.command()
def delete(host: str, yes: bool = typer.Option(False, "--yes")) -> None:
    if not yes:
        if not sys.stdin.isatty():
            typer.echo("refusing to prompt: stdin is not a terminal; pass --yes", err=True)
            raise typer.Exit(code=2)
        typer.confirm(f"Delete {host}?", abort=True, err=True)
    typer.echo(json.dumps({"host": host, "deleted": True}, sort_keys=True))


if __name__ == "__main__":
    app()
```

With stdin from `/dev/null` and no `--yes` the program wrote the refusal to stderr and exited 2;
with `--yes` it printed `{"deleted": true, "host": "PL-LT-00123"}` and exited 0.
