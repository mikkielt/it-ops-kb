---
topic: python/stdlib-os-loadavg
priority: P3
applies_to: "Python stdlib os.getloadavg (docs and source at CPython v3.14.7); its macOS path through Apple Libc-1752.120.2 and XNU xnu-12377.121.6; one run on Python 3.13.2, macOS, 2026-10-13"
retrieved_utc: 2026-10-13
sources: [S-ew7mucsg, S-ctjl4gek, S-pfq6vvwq, S-7bno7nz5, S-e6rzsvfi, S-fm6og32s, S-itsqgyii]
status: partial
---

# stdlib os.getloadavg: what the 1, 5 and 15 minute values count on macOS

## Summary
`os.getloadavg()` returns three floats: the system's load averages over the last 1, 5 and 15 minutes. On
macOS CPython calls the C library's `getloadavg`, which reads the kernel's `vm.loadavg` sysctl and divides
each fixed-point value by its scale; it does not divide by the number of CPUs. The kernel computes the
three values as exponentially weighted moving averages of a count of running threads, sampled every
5 seconds. A value is therefore a smoothed thread count for the whole host, to be read against the CPU
count and remembering that the 1-minute value still carries the last minute of load.

## Facts
### What the docs and the source say
- `os.getloadavg()` returns the number of processes in the system run queue averaged over the last 1, 5
  and 15 minutes, or raises `OSError` if the load average was unobtainable; the docs mark it available on
  Unix. [DOC S-ew7mucsg]
- The implementation passes a three-element `double` array to the C library's `getloadavg` and returns it
  as a tuple of three floats; when the call does not return 3 it raises `OSError` with the message "Load
  averages are unobtainable". The function exists only where the build has `getloadavg`. [CODE S-ctjl4gek: Modules/posixmodule.c#os_getloadavg_impl]
- The Apple `getloadavg(3)` page states the same: the number of processes in the system run queue
  averaged over various periods, at most 3 samples, "over the last 1, 5, and 15 minutes", and `-1` when the
  load average is unobtainable. [DOC S-pfq6vvwq]

### Where the number comes from on macOS
- Apple's `getloadavg` asks the kernel for the `vm.loadavg` sysctl (`CTL_VM`, `VM_LOADAVG`) and converts
  each of the three fixed-point entries to a `double` by dividing by the struct's `fscale`; there is no
  other scaling, so the values are not per CPU. [CODE S-7bno7nz5: gen/getloadavg.c#getloadavg]
- The kernel's `sysctl_loadavg` handler answers that sysctl from the global `averunnable`, for 64-bit and
  32-bit callers alike. [CODE S-e6rzsvfi: bsd/kern/kern_sysctl.c#sysctl_loadavg]
- `compute_averunnable` updates the three entries of `averunnable` as exponentially weighted averages whose
  constants the source comments as "averages over 1, 5, and 15 minutes when sampling at 5 second
  intervals" (`exp(-1/12)`, `exp(-1/60)`, `exp(-1/180)`); the sample `nrun` is its argument. [CODE S-fm6og32s: bsd/kern/kern_synch.c#compute_averunnable]
- `compute_averages` sets that sample, `sched_nrun`, to the scheduler's `TH_BUCKET_RUN` run count minus one,
  commented "Sample total running threads for the load average calculation", and the
  `compute_averunnable` entry of the scheduler's average table has a period of 5 seconds. [CODE S-itsqgyii: osfmk/kern/sched_average.c#compute_averages]

### What follows for a check of host load
- So on macOS the three values count threads, not processes as the man page says: a multi-threaded test
  worker adds one for each thread that is running or runnable, and no value is divided by the CPU count.
  A reading near the logical CPU count means the CPUs are about saturated, and a reading well above it
  means runnable threads queue for a CPU. [DER S-pfq6vvwq, S-7bno7nz5, S-fm6og32s, S-itsqgyii: the sample is a thread run count and the only division is by `fscale`]
- Each 5-second sample moves the 1-minute value by `1 - exp(-1/12)`, about 8% of the gap to the current
  count, so its time constant is 60 seconds: a run that ended a few seconds ago still shows in it, and a
  check made right after a heavy run reads the run's own load, not an idle host's. The 5-minute and
  15-minute values react 5 and 15 times more slowly. [DER S-fm6og32s: the three constants at 5-second sampling]
- The docs and the code read here do not say which waiting states leave the run count, so whether a thread
  blocked on I/O adds to the value is not confirmed; the sources name only running and runnable threads. [UNK: the thread states counted are not listed in the docs or the comments read]

## Reference
- Related: `python/pytest-xdist.md` (worker count: `os.cpu_count()` and `-n auto`, and the wall time of a
  `loadscope` run), `python/stdlib-windows-portability.md` (what the stdlib lacks on Windows),
  `python/interpreter-startup.md` (`-X cpu_count`), `python/ps-process-cpu.md` (which processes load the host:
  `ps` `pcpu` on macOS and Linux, and the Windows counterpart).
- Sources: the docs page for `os` at CPython v3.14.7 (`Doc/library/os.rst`), `Modules/posixmodule.c`, Apple
  `Libc` `gen/getloadavg.3` and `gen/getloadavg.c`, XNU `bsd/kern/kern_sysctl.c`,
  `bsd/kern/kern_synch.c` and `osfmk/kern/sched_average.c`.

## Examples
- SNIPPET: the 1-minute load average per logical CPU, to read against 1.0; context: Python 3.x on Unix
  (macOS, Linux), `os.getloadavg` raises `OSError` when the value is unobtainable and does not exist on Windows; checked: run [DER S-ew7mucsg: `os.getloadavg` and `os.cpu_count` as documented; run 2026-10-13 on Python 3.13.2, macOS]
```python
import os

one, five, fifteen = os.getloadavg()
per_cpu = one / (os.cpu_count() or 1)
```
- Run on this host (macOS, Python 3.13.2, 2026-10-13) `os.getloadavg()` returned a tuple of three floats,
  and `hasattr(os, "sched_getaffinity")` was `False`. [DER S-ew7mucsg: one run, one host]
