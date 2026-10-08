---
topic: python/interpreter-startup
priority: P3
applies_to: "CPython 3.14.7 command-line options and environment variables that change what the interpreter does at start (documentation at the v3.14.7 tag); Popen on Windows versus POSIX; compile-time warnings and the warnings filter (CPython 3.14.8 documentation and source)"
retrieved_utc: 2026-10-08
sources: [S-d77lvlq4, S-dabwnzz5, S-ew7mucsg, S-uhm2nnel, S-nidh245i, S-q5frtccp, S-4yatj52m, S-6wxmp67t, S-j7sjakc5]
status: partial
---

# CPython interpreter start: options that change start-up work, and process creation per platform

## Summary
A test suite that starts `python` as a subprocess hundreds of times pays the interpreter's start-up each time:
creating the process, importing `site`, and importing whatever the script imports. CPython documents the switches
that change that work (`-S` skips `site`, `-I` isolates from the user's environment, `-B` skips writing `.pyc`
files, `-X frozen_modules`, `-X importtime` to see where import time goes) and the override for the CPU count
that parallel runners read (`-X cpu_count`, `PYTHON_CPU_COUNT`, 3.13+). `subprocess` starts children with
`CreateProcess()` on Windows, while on Linux it uses `vfork()` or `posix_spawn()` when it can, which the docs say
is much faster. The per-process cost on a given Windows host is not documented; measure it there.
Compiling source can also emit warnings: an invalid escape sequence such as `"\d"` gives a `SyntaxWarning`
(3.12+) on stderr at compile time, and `-W error` (or an `"error"` warnings filter around `compile()`) turns it
into a `SyntaxError`.

## Facts
### Start-up options
- `-S` disables the import of the `site` module and the site-dependent changes to `sys.path`, also when `site` is imported later (unless `site.main()` is called). [DOC S-d77lvlq4]
- `-I` runs Python in isolated mode, implying `-E`, `-P` and `-s`: `sys.path` holds neither the script's directory nor the user's site-packages, and all `PYTHON*` environment variables are ignored (3.4+). [DOC S-d77lvlq4]
- `-B` stops Python from writing `.pyc` files when it imports source modules (also `PYTHONDONTWRITEBYTECODE`). [DOC S-d77lvlq4]
- `-X frozen_modules=on|off` decides whether the import system uses frozen modules; the default is `on` for an installed Python and `off` when run from a source tree, and `importlib._bootstrap` and `importlib._bootstrap_external` are always frozen (3.11+, also `PYTHON_FROZEN_MODULES` from 3.13). [DOC S-d77lvlq4]
- `-X importtime` prints how long each import takes (module name, cumulative time including nested imports, self time), for example `python -X importtime -c 'import asyncio'`; `-X importtime=2` (3.14) also marks modules already loaded as `cached`. [DOC S-d77lvlq4]
- `-X cpu_count=N` (3.13+) overrides `os.cpu_count()`, `os.process_cpu_count()` and `multiprocessing.cpu_count()`, and `PYTHON_CPU_COUNT` does the same for the first two; the docs name limiting CPU use in a container as the use. [DOC S-d77lvlq4, S-ew7mucsg]

### Process creation per platform
- On POSIX, `Popen` runs the child with `os.execvpe()`-like behaviour; on Windows it calls `CreateProcess()`, which takes one command-line string. [DOC S-dabwnzz5]
- Since 3.8 `Popen` can use `os.posix_spawn()` for better performance, and on Linux `subprocess` defaults to `vfork()` instead of `fork()` when it is safe, which the docs say greatly improves performance; neither applies on Windows. [DOC S-dabwnzz5]
- `-S`, `-I` and `-X frozen_modules` change the interpreter's own start-up work, not the cost of creating the process; the Windows side of that cost (process creation, plus antivirus scanning of what the new process loads and opens) is not quantified in the Python or Microsoft docs. [UNK: no figure in cmdline.rst, subprocess.rst or the CreateProcess reference; measured per host in the report kb/_self/reports/test-suite-speed.md]
- A test that runs a stdlib-only tool as `python tool.py` can often import the tool and call its `main(argv)` in the pytest process instead; that saves one interpreter start per call, but gives up what only a real process checks (exit status of the interpreter, `sys.argv[0]` and `__main__` handling, environment and working-directory isolation, output encoding), so it is a choice per test, not a blanket change. [DER S-dabwnzz5, S-d77lvlq4: the process-start work above is what is saved; the listed properties come only from a real child process]

### Compile-time warnings and turning them into errors
- Python leaves an unrecognized escape sequence in a string literal unchanged, backslash included (`'\q'` is
  `\q`); since 3.12 such a sequence produces a `SyntaxWarning` (a `DeprecationWarning` from 3.6 to 3.11), and
  the docs say a future version will raise a `SyntaxError`. [DOC S-uhm2nnel]
- Octal escapes with a value above `0o377` also produce a `SyntaxWarning` since 3.12 (a `DeprecationWarning`
  in 3.11), with the same future `SyntaxError`. [DOC S-uhm2nnel]
- `SyntaxWarning` is the base class for warnings about dubious syntax, typically emitted when compiling source
  and usually not reported when already compiled code runs, so a module loaded from its `.pyc` cache does
  not warn again. [DOC S-q5frtccp]
- The warnings module's category table says `SyntaxWarning` is emitted at compile time "and hence may not be
  suppressed by runtime filters". [DOC S-nidh245i]
- Warnings are written to `sys.stderr` by default; the warnings filter is an ordered list of (action,
  message, category, module, lineno) entries, the first match decides, and the `"error"` action turns
  matching warnings into exceptions. [DOC S-nidh245i]
- A release build's default filter ignores `DeprecationWarning` (except in `__main__`),
  `PendingDeprecationWarning`, `ImportWarning` and `ResourceWarning`, and is empty in a debug build; it does
  not name `SyntaxWarning`, so the warning is printed by default. [DOC S-nidh245i]
- The filter is initialized from the `-W` options and `PYTHONWARNINGS`; `-Werror` converts every warning to
  an exception, and the full form `action:message:category:module:lineno` narrows it, e.g. `-W
  error::SyntaxWarning`, where the category matches subclasses too. [DOC S-d77lvlq4, S-nidh245i]
- The parser emits the invalid-escape warning with `PyErr_WarnExplicitObject`, and when the filter turns it into an exception it
  replaces the warning with a `SyntaxError` at the escape's position "to get a more accurate error report".
  [CODE S-4yatj52m: Parser/string_parser.c#warn_invalid_escape_sequence]
- CPython's shared helper for emitting a `SyntaxWarning`, `_PyErr_EmitSyntaxWarning`, does the same: a
  `SyntaxWarning` raised as an error is replaced with a `SyntaxError`. [CODE S-6wxmp67t:
  Python/errors.c#_PyErr_EmitSyntaxWarning]
- `py_compile.compile(file, doraise=True)` raises `PyCompileError` on a compile error; with the default
  `doraise=False` it writes an error string to `sys.stderr` and returns `None`, and `quiet=2` writes
  nothing. [DOC S-j7sjakc5]
- So a check that must fail on an invalid escape runs the compile with the warning as an error: `python -W
  error::SyntaxWarning -m py_compile FILE` (exit non-zero), or in-process `with warnings.catch_warnings():
  warnings.simplefilter("error", SyntaxWarning)` around `compile(source, path, "exec")`, which then raises
  `SyntaxError`; compiling from source matters, since a cached `.pyc` does not warn. [DER S-d77lvlq4,
  S-nidh245i, S-4yatj52m, S-q5frtccp, S-j7sjakc5]
- Observed 2026-10-08 with CPython 3.13.2 on macOS, non-interactive shell: `python3 -I -W error::SyntaxWarning
  -c` running `compile('x = "\\d"', 'f.py', 'exec')` exited 1 with `SyntaxError: invalid escape sequence
  '\d'` pointing at `f.py` line 1; 3.14 and Windows were not run. [DER S-4yatj52m: one run of ours, matching
  the replacement in string_parser.c, not a rule]

## Reference
- Related: `python/stdlib-windows-portability.md` (command-line length, detached processes, interpreter names on Windows), `python/pytest-xdist.md` (worker count from `os.cpu_count()`), `python/uv-projects.md` (`uv run` locks and syncs before it runs a command), `gitlab/git-test-repositories.md`, `windows/dev-drive.md`.
- SNIPPET: see which imports dominate a tool's start-up; context: CPython 3.7+ (`-X importtime`); checked: syntax [DOC S-d77lvlq4: `-X importtime` output columns]
```sh
python3 -X importtime -c "import sys; sys.path.insert(0, '_tools'); import rag" 2> importtime.txt
sort -t'|' -k2 -n importtime.txt | tail -15
```

## Examples
- A helper that starts `python -c "..."` 200 times in a test run can pass `-S` when the snippet needs no site-packages, and `-I` when the test must not see the developer's `PYTHON*` variables; neither avoids the process creation itself.
