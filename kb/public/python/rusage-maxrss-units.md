---
topic: python/rusage-maxrss-units
priority: P3
applies_to: "Python 3 resource.getrusage and os.wait4 (docs.python.org/3, Unix only); Linux getrusage(2) in man-pages 6.19; macOS getrusage(2) at xnu-12377.121.6"
retrieved_utc: 2026-10-26
sources: [S-2ua7dl2m, S-5brdhqgo, S-d3vrqlxp, S-l7f6hp46]
status: partial
---

# ru_maxrss: the unit of peak memory in the rusage that Python returns, on Linux and on macOS

## Summary
`resource.getrusage` and `os.wait4` hand back the C `rusage` fields, and Python's pages name `ru_maxrss` ("maximum
resident set size") without a unit, deferring to the `getrusage(2)` man page. That page says kibibytes on Linux and
bytes on macOS, so the same integer is 1024 times apart for the same memory use, and a portable benchmark converts
by platform. For a child waited for, the value is the peak of the largest single child, not of the tree.

## Facts
### What Python says
- `resource.getrusage(who)` returns an object for the current process or its children; the fields after the two
  time floats are integers, and the page tells the reader to consult the `getrusage(2)` man page for detailed
  information about them. [DOC S-2ua7dl2m]
- The page's table lists `ru_maxrss` as "maximum resident set size" and states no unit for it. [DOC S-2ua7dl2m]
- `os.wait4(pid, options)` returns a 3-element tuple of the child's process id, its exit status indication and
  resource usage information, and refers to `resource.getrusage()` for what that information is; the page is
  Unix-only (not WASI, Android or iOS). [DOC S-5brdhqgo]
- `RUSAGE_CHILDREN` covers child processes of the caller that have terminated and been waited for; `RUSAGE_SELF`
  is the sum over all threads of the calling process. [DOC S-2ua7dl2m]

### Linux
- `ru_maxrss` is "the maximum resident set size used (in KiB)", and exists since Linux 2.6.32. [DOC S-d3vrqlxp]
- For `RUSAGE_CHILDREN` it is the resident set size of the largest child, not the maximum resident set size of the
  process tree. [DOC S-d3vrqlxp]
- `RUSAGE_CHILDREN` statistics "will include the resources used by grandchildren, and further removed descendants",
  if all the intervening descendants waited on their terminated children; `ru_utime` is the time spent executing in
  user mode and `ru_stime` the system CPU time. [DOC S-d3vrqlxp]

### macOS
- `ru_maxrss` is "the maximum resident set size utilized (in bytes)". [DOC S-l7f6hp46]
- The page defines `ru_utime` as the total time spent executing in user mode and `ru_stime` as time in the system on
  behalf of the process, and states no rule for descendants of a child. [DOC S-l7f6hp46]

### What follows for a measurement
- The same `ru_maxrss` integer is kibibytes on Linux and bytes on macOS, so a figure read from `os.wait4` or
  `getrusage` is divided by 1024 on Linux and by 1048576 on macOS to give MiB; a table that mixes hosts converts
  per platform and records the unit. [DER S-d3vrqlxp, S-l7f6hp46, S-2ua7dl2m: the two man pages state different units
  and Python passes the field through]
- `RUSAGE_CHILDREN` is a maximum over children (Linux page), so it cannot give a per-run figure for each of several
  children: a record per run calls `os.wait4` on that child's pid and reads the usage in its result. [DER
  S-d3vrqlxp, S-5brdhqgo: the aggregate is a maximum; `os.wait4` takes a pid and returns usage information]
- CPU seconds follow the same wait chain: a child that a hook shell started and waited for (such as `git`) counts in
  the usage of the hook shell's own `wait4` result or, summed, in `RUSAGE_CHILDREN` of the caller, so the hook's figure
  already holds that child's CPU and a separate row for the child counts it twice. [DER S-d3vrqlxp: descendants are
  included when each intervening process waited]
- Whether the macOS kernel includes waited-for grandchildren in `RUSAGE_CHILDREN` is not stated on the page used here.
  [UNK: S-l7f6hp46 names no descendant rule; the Linux statement is not taken to hold there]
- One run on this kind of host (macOS, Python 3.13.2, 2026-10-26): a forked child that touched 200 MiB, waited for
  with `os.wait4`, returned a `struct_rusage` whose `ru_maxrss` was 212549632, about 202.7 MiB when divided by
  1048576, so the integer is bytes there as the Apple page says. [DER S-l7f6hp46: one run of our own, one host]
- The Linux unit rests on the man page only; no Linux host was run for this. [UNK: not run on Linux]

## Reference
- Related: `python/ps-process-cpu.md` (the other portable per-process figure, CPU percent, and its platform
  differences).
- Sources: Python's `resource` and `os` pages, the man7.org `getrusage(2)` page, and Apple's `getrusage.2` at tag
  `xnu-12377.121.6`.

## Examples
- SNIPPET: peak memory of one waited-for child in MiB on macOS and Linux; context: Python 3.x on Unix; checked: syntax
  [DER S-d3vrqlxp, S-l7f6hp46: bytes on macOS, KiB on Linux]
```python
import os
import subprocess
import sys

proc = subprocess.Popen(["python3", "-c", "pass"])
_, status, usage = os.wait4(proc.pid, 0)
unit = 1048576 if sys.platform == "darwin" else 1024
peak_mib = usage.ru_maxrss / unit
```
