---
topic: python/interpreter-startup
priority: P3
applies_to: "CPython 3.14.7 command-line options and environment variables that change what the interpreter does at start (documentation at the v3.14.7 tag); Popen on Windows versus POSIX"
retrieved_utc: 2026-09-29
sources: [S-d77lvlq4, S-dabwnzz5, S-ew7mucsg]
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

## Reference
- Related: `python/stdlib-windows-portability.md` (command-line length, detached processes, interpreter names on Windows), `python/pytest-xdist.md` (worker count from `os.cpu_count()`), `python/uv-projects.md` (`uv run` locks and syncs before it runs a command), `gitlab/git-test-repositories.md`, `windows/dev-drive.md`.
- SNIPPET: see which imports dominate a tool's start-up; context: CPython 3.7+ (`-X importtime`); checked: syntax [DOC S-d77lvlq4: `-X importtime` output columns]
```sh
python3 -X importtime -c "import sys; sys.path.insert(0, '_tools'); import rag" 2> importtime.txt
sort -t'|' -k2 -n importtime.txt | tail -15
```

## Examples
- A helper that starts `python -c "..."` 200 times in a test run can pass `-S` when the snippet needs no site-packages, and `-I` when the test must not see the developer's `PYTHON*` variables; neither avoids the process creation itself.
