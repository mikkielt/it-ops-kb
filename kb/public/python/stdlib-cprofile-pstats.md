---
topic: python/stdlib-cprofile-pstats
priority: P3
applies_to: [python, cProfile, pstats, runpy]
retrieved_utc: 2026-10-09
sources: [S-5y7wwygh, S-tkdyngyx, S-vydvtba3, S-4ydukkiy]
status: partial
---

# stdlib cProfile and pstats (reading a profile's entries, and code run through runpy or exec)

## Summary
`cProfile` records every function call, return and exception of the code it runs and `pstats.Stats` holds and
formats the result. The documented surface is the printed report (`ncalls`, `tottime`, `cumtime`, `percall`);
the shape of `Stats.stats`, the dict a tool reads to get the numbers itself, is documented only in the
CPython source (`Lib/pstats.py`, `Lib/cProfile.py`), so those facts are `CODE`. Code that a profiler runs
through `exec`, `runpy.run_module` or `runpy.run_path` is counted like any other code, with the `exec` call
and the `runpy` helpers as extra entries above the target's own `<module>` entry.

## Facts
- `cProfile` and `profile` give deterministic profiling (every call, return and exception is monitored);
  `cProfile` is a C extension with lower overhead and the recommended one, `profile` is pure Python;
  `pstats` formats the result. The profilers are for finding where a program spends time, not for
  benchmarking (`timeit` is). [DOC S-5y7wwygh]
- The first line of a printed report gives the number of calls monitored and, in parentheses, the number
  of *primitive* calls: calls not induced through recursion. In the `ncalls` column, `3/1` means a function
  recursed: the total number of calls first, the primitive calls second; a non-recursive function prints one figure. [DOC S-5y7wwygh]
- `tottime` is the time in the function itself, excluding sub-functions; `cumtime` is the time in the
  function and all its sub-functions and is accurate even for recursive functions; the first `percall` is
  `tottime` divided by `ncalls`, the second is `cumtime` divided by the primitive calls. [DOC S-5y7wwygh]
- `cProfile.run(command, filename=None, sort=-1)` executes `exec(command, __main__.__dict__, __main__.__dict__)`
  and `runctx(command, globals, locals, ...)` executes `exec(command, globals, locals)`; `Profile.run`,
  `Profile.runctx` and `Profile.runcall(func, /, *args, **kwargs)` do the same on a profiler object, and a
  `cProfile.Profile` is also a context manager (3.8+). The docs' own example report lists
  `{built-in method builtins.exec}` and `<string>:1(<module>)` as the first two entries of a profiled string. [DOC S-5y7wwygh]
- Results exist only if the profiled command returns: a `sys.exit()` call inside it ends the interpreter
  and no profile is printed. [DOC S-5y7wwygh]
- `pstats.Stats(*filenames or profile, stream=sys.stdout)` loads one or more profile files or a `Profile`
  object; several files are merged, statistics of identical functions being added together (the same for
  `Stats.add`); no compatibility is guaranteed between profiler versions, other profilers, or the same profiler
  on another operating system. `strip_dirs()` drops the path from file names and merges entries it makes indistinguishable. [DOC S-5y7wwygh]
- `Stats.print_callers()` under `cProfile` prints, for each caller of a function, three numbers: how many
  times that caller called it, and the total and cumulative time spent in the function while called by that
  caller; under `profile` it prints a call count in parentheses and one time. [DOC S-5y7wwygh]
- `python -m cProfile [-o output_file] [-s sort_order] (-m module | myscript.py)` profiles a script or, with `-m`
  (3.7+), a module; without `-o` it prints the report sorted by `-s`. [DOC S-5y7wwygh]
- `Stats.stats` is a dict. Its key is `(filename, lineno, funcname)`; a built-in function has the key
  `('~', 0, name)`, with `name` such as `<built-in method builtins.exec>`. Its value is a 5-tuple
  `(cc, nc, tt, ct, callers)`: `cc` the primitive calls, `nc` the total calls, `tt` the time in the function itself
  (the `tottime` column), `ct` the cumulative time (`cumtime`), `callers` a dict. `Stats.total_calls` is the sum of every
  `nc` and `Stats.prim_calls` the sum of every `cc`. [CODE S-tkdyngyx: Lib/pstats.py#Stats.get_top_level_stats]
- `Profile.snapshot_stats` of `cProfile` fills it as `nc = callcount`, `cc = nc - reccallcount`, `tt = inlinetime`
  and `ct = totaltime` of the underlying `_lsprof` entry, so `cc` is `nc` minus the recursive calls. [CODE S-vydvtba3: Lib/cProfile.py#Profile.snapshot_stats]
- Under `cProfile`, a `callers` dict maps each caller's key to a 4-tuple `(nc, cc, tt, ct)` for the calls made
  from that caller. The order is `nc` before `cc`, the reverse of the entry's own `(cc, nc, ...)`. The `profile` module
  puts a single call count there instead of a tuple. [CODE S-vydvtba3: Lib/cProfile.py#Profile.snapshot_stats; CODE S-tkdyngyx: Lib/pstats.py#Stats.print_call_line]
- `Stats(profile_object)` calls `create_stats()`, takes the object's `stats` dict and sets the object's own to `{}`; given a file
  name it reads the file with `marshal.load`, and `dump_stats` writes the dict with `marshal.dump`. [CODE S-tkdyngyx: Lib/pstats.py#Stats.load_stats]
- `Profile.runctx` calls `enable()`, then `exec(cmd, globals, locals)`, then `disable()` in a `finally`; `runcall` does the same for a
  call. The command line form wraps `-m` as the string `run_module(modname, run_name='__main__')` and runs a script as compiled code with a
  fresh `__main__` module's namespace, both through `runctx`. [CODE S-vydvtba3: Lib/cProfile.py#Profile.runctx, #main]
- `runpy.run_module` and `run_path` execute the code of the target through `_run_code`, which calls the built-in `exec(code, run_globals)`
  in a new namespace. [CODE S-4ydukkiy: Lib/runpy.py#_run_code]
- One probe (Python 3.13.2, macOS, 2026-10-09, a 9-line module whose recursive function is called 67 times, run with
  `cProfile.Profile().enable()` around `runpy.run_module("target_mod", run_name="__main__")`): the target's top level was one entry
  `(<path of the file>, 1, '<module>')` with `nc` 1, called from `('~', 0, '<built-in method builtins.exec>')`, called from
  `('<frozen runpy>', 65, '_run_code')`, called from `run_module`; the recursive function had `nc` 67 and `cc` 1, and a `callers` entry for
  itself of `(nc, cc) = (66, 2)`. `run_path` gave the same chain below `('<frozen runpy>', 91, '_run_module_code')`.
  Other Python versions were not run. [DER S-tkdyngyx, S-vydvtba3, S-4ydukkiy: probe read against the entry layout and `_run_code`]
- The same probe: `exec` of source text compiled in the profiled code (`exec(compile(open(p).read(), p, 'exec'), {})`, run with
  `Profile.runctx`) gave `nc` 2 and `cc` 1 for `builtins.exec`: the command is itself run by `exec`, so the inner `exec` counts as
  recursion, and the target's `<module>` entry is called from the inner `exec`, which the `<string>:1(<module>)` entry
  of the outer one calls. With `Profile.run("x = sum(range(3))")` the `exec` entry had an empty `callers` dict, since the profiler was enabled just
  before it. Python 3.13.2, macOS; other versions not run. [DER S-5y7wwygh, S-vydvtba3: probe read against `runctx` and the primitive-call definition]
- The same probe: modules imported while the profiler is on (`pkgutil` and `warnings` the first time `run_path` ran in the process) add one
  `('<path>', 1, '<module>')` entry each, called from `builtins.exec`, and the first `run_module` of a module with no cached bytecode also
  counted the bytecode-writing calls (`get_code`, `_cache_bytecode`, `_write_atomic`), so the total call count of a first run is larger than a later one.
  `Profile.runcall` also counted its own `disable()` as an entry. Python 3.13.2, macOS. [DER S-5y7wwygh, S-vydvtba3: probe read against `runctx` and `runcall`]
- The docs name the `Stats` methods and the printed columns but do not describe `Stats.stats` or its tuple layout as an interface, so a tool that reads
  it depends on CPython's current source, not on a documented promise. [UNK: the docs state no layout for `Stats.stats`; checked on 3.14.7's `profile.rst`]

## Reference
- SNIPPET: read the entries of a profile instead of printing a report; context: CPython 3.12+ `cProfile`/`pstats`, layout as in `Lib/pstats.py` at 3.14.7; checked: run (Python 3.13.2, macOS) [CODE S-tkdyngyx: Lib/pstats.py#Stats.get_top_level_stats]
```python
import cProfile
import pstats

pr = cProfile.Profile()
pr.runcall(sorted, range(10))
st = pstats.Stats(pr)
for (filename, lineno, name), (cc, nc, tt, ct, callers) in st.stats.items():
    print(name, cc, nc, tt >= 0, ct >= tt, len(callers))
print(st.total_calls, st.prim_calls)
```
- Related: `python/imports-and-modules.md` (how `runpy`, `-m` and `__main__` locate and run code), `python/interpreter-startup.md` (start-up cost the
  profiler measures), `python/stdlib-sqlite3-csv.md` (the sqlite3 module a profiled index build calls).

## Examples
- A tool that profiles another script should treat the `exec` and `runpy` frames as overhead of its own harness: the first entries of a
  report from `runpy.run_module` or `run_path` are `run_module`/`run_path`, `_run_code` and `builtins.exec`, and the target's work starts at its
  `<module>` entry.
- A tool that sums the call count of a function reads `nc` for the total and `cc` for the primitive calls: for a recursive function the two differ, and the
  printed `ncalls` shows `nc/cc`.
