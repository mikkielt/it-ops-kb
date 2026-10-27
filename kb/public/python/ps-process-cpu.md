---
topic: python/ps-process-cpu
priority: P3
applies_to: "POSIX.1-2024 ps; procps-ng ps(1) (Linux, man page dated 2025-04-23); Apple ps(1) at adv_cmds-237 (macOS); Windows PowerShell 7.6 Get-Process, Get-Counter and the Win32_Process class"
retrieved_utc: 2026-10-27
sources: [S-tldzr3mf, S-glwifmco, S-ggxrmcqc, S-5syx7mel, S-js22cswf, S-wh6i6rv4, S-v6442u3l, S-ocglo5m3, S-d4mf4bbv]
status: partial
---

# ps: one portable process listing with CPU and command line, and what %CPU means on each platform

## Summary
`ps -A -o pid=,pcpu=,args=` is a listing of every process with three columns and no header line, and each
part of it is in the POSIX `ps` specification, so one argument list serves macOS and Linux. The `pcpu` column
is not the same number on the two: POSIX leaves "recently" and "CPU time available" unspecified, procps-ng on
Linux reports CPU time over the whole life of the process, and Apple's `ps` reports a decaying average over up to
a minute. A sum of the column can exceed 100% on both. Windows has no `ps` listing with that column: the
`Get-Process` CPU value is seconds of processor time, not a percentage, a percentage needs two samples of the
`\Process(*)\% Processor Time` counter, and the command line is a `Win32_Process` property.

## Facts
### POSIX: what the argument list means
- `-A` writes information for all processes, and `-e` is its equivalent; by default `ps` selects only the
  processes with the invoker's effective user ID and controlling terminal. [DOC S-tldzr3mf]
- `-o` takes a list of names whose default headers an `=` and text overrides; if all header texts are null no
  header line is written, so `-o pid=,pcpu=,args=` prints bare rows. [DOC S-tldzr3mf]
- The `pcpu` name is the ratio of CPU time used recently to CPU time available in the same period, as a
  percentage; the specification leaves "recently" and the CPU time available unspecified. [DOC S-tldzr3mf]
- `pid`, `pcpu` and `args` are all names the specification lists, and only `comm` and `args` may hold blanks,
  so a row with `args` last splits as two numbers and then the rest of the line. [DOC S-tldzr3mf]
- The rationale says historical counterparts of `pcpu` showed use in the recent past, such as the preceding
  minute, and that these values frequently did not add up to 100% over all processes. [DOC S-tldzr3mf]
- `time` is the cumulative CPU time of the process, in the POSIX locale in the form `[dd-]hh:mm:ss`, and `etime` is
  the elapsed time since the process started, in the form `[[dd-]hh:]mm:ss`; both are whole-second clock texts, not
  numbers of seconds. [DOC S-tldzr3mf]
- The specification's keyword list holds no resident-set name: a search of the page for `rss` finds nothing, so
  `rss` is an extension of the two implementations below, not a portable name. [DER S-tldzr3mf: the page's text
  searched for the keyword on 2026-10-27, no match]

### Linux (procps-ng)
- `-A` selects all processes and is identical to `-e`; `ps -Ao pid,tt,user,fname,tmout,f,wchan` is one of the
  page's own examples of the `-A` plus `-o` form. [DOC S-glwifmco]
- If all column headers are empty (`ps -o pid= -o comm=`) the header line is not output. [DOC S-glwifmco]
- `pcpu` is an alias of `%cpu`, and `args` is a keyword (aliases `cmd`, `command`) for the command with its
  arguments. [DOC S-glwifmco]
- `%cpu` is the CPU time used divided by the time the process has been running, expressed as a percentage; the
  page says it will not add up to 100%. [DOC S-glwifmco]
- The page's BUGS section says CPU usage is currently the percentage of time spent running during the entire
  lifetime of a process, not ideal and not conforming to the standards `ps` otherwise follows. [DOC S-glwifmco]
- `rss` (aliases `rssize`, `rsz`) is the resident set size, "the non-swapped physical memory that a task has used",
  in kibibytes; the page adds that the SIZE and RSS fields do not count some parts of a process, among them the page
  tables and the kernel stack. [DOC S-glwifmco]
- `cputime` (alias `time`) is the cumulative CPU time in the form `[DD-]hh:mm:ss`, whole seconds, and `cputimes`
  (alias `times`) is the same total in seconds; `etime` is the time since the process started in the form
  `[[DD-]hh:]mm:ss` and `etimes` the same in seconds. [DOC S-glwifmco]

### macOS (Apple ps)
- `-A` displays all processes and `-e` is identical to it; keywords take an `=` and a header string, and when
  every keyword has an empty header text no header line is written. [DOC S-ggxrmcqc]
- `pcpu` is an alias of `%cpu`, "percentage CPU usage", and `args` is "command and arguments". [DOC S-ggxrmcqc]
- `%cpu` is a decaying average over up to a minute of previous real time; because the time base varies, for
  example for very young processes, the sum of all `%cpu` fields can exceed 100%. [DOC S-ggxrmcqc]
- `rss` is "the real memory (resident set) size of the process (in 1024 byte units)", so a value is kibibytes, as on
  Linux; the keyword table says only "resident set size". [DOC S-ggxrmcqc]
- `time` (alias `cputime`) is the accumulated CPU time, user plus system, and `etime` is the elapsed running time;
  the page gives no clock format for either. `utime` (alias `putime`) is the user CPU time alone. [DOC S-ggxrmcqc]
- `-S` "Change the way the process time is calculated by summing all exited children to their parent process", so
  with it a parent's `time` includes the CPU of children that have already exited. [DOC S-ggxrmcqc]

### Windows
- `Get-Process` returns a `Process` object per process; its alias `ps` exists on Windows only, `gps` on all
  platforms. [DOC S-5syx7mel]
- The CPU(s) column of `Get-Process` is the processor time the process has used on all processors, in seconds,
  a running total, not a percentage. [DOC S-5syx7mel]
- A percentage per process comes from the `\Process(*)\% Processor Time` counter, which `Get-Counter` reads
  with a one-second interval between samples unless `SampleInterval` says otherwise. [DOC S-wh6i6rv4]
- That counter is the sum over all threads of the process, so its range is 0 through 100 times the processor
  count; the percentage is computed from two samples, and the counter set can mix up the samples of processes
  that share an instance name. [DOC S-js22cswf]
- The command line of a process is the `CommandLine` property of the `Win32_Process` class, read with
  `Get-CimInstance -ClassName Win32_Process`; the page's example of this runs PowerShell as administrator, and
  it says that without it the query it shows returns no results. [DOC S-v6442u3l]

### What follows for a check that groups CPU consumers by command line
- One `ps -A -o pid=,pcpu=,args=` call is the same argument list on macOS and Linux, and its rows are bare
  `pid`, `pcpu`, `args`; there is no header to skip and the command line is the rest of each row. [DER S-tldzr3mf,
  S-glwifmco, S-ggxrmcqc: the three pages accept `-A`, `-o` with empty headers and the `pcpu` and `args` names]
- The same `pcpu` number means different things: on Linux a process that burned CPU an hour ago and is idle now
  still shows a share of its whole life, while on macOS the share fades within about a minute. A report states
  which it shows, and a Linux value is a poor signal for what is loading the host now. [DER S-glwifmco,
  S-ggxrmcqc: lifetime ratio against a decaying average over up to a minute]
- Neither value is a share of the host: both can add up to more than 100% over all processes, so a group's
  percentage is a share of the listing's own sum, or a figure read against the CPU count, not of 100%. [DER
  S-glwifmco, S-ggxrmcqc, S-tldzr3mf: the sum of the column is not bounded by 100%]
- A listing with the command line has no Windows counterpart in one call: `Get-Process` has seconds of CPU
  time and no command line, the counter gives a percentage over a sampling interval, and the command line
  needs a `Win32_Process` query, so a Windows host needs its own collector. [DER S-5syx7mel, S-wh6i6rv4,
  S-v6442u3l: three different sources for the three values]
- FreeBSD's `ps(1)` page accepts the same argument list: `-A` ("information about all processes in the
  system", equivalent to `-a` plus `-x`), `-o` keywords with `=` header texts (a header line is not written when
  every keyword has an empty header text), `pcpu` as an alias of `%cpu` and `args` as "command and arguments". [DOC S-ocglo5m3]
- BusyBox's command help lists for `ps` only `-o col1,col2=header` ("select columns for display") and `-T`
  (show threads): it names no `-A` and no column names, so whether a BusyBox `ps` accepts `-A`, `pcpu` and
  `args` is not stated by that page and needs a run on such an image. [DOC S-d4mf4bbv]
- So the one argument list is documented for procps-ng (Linux), Apple's `ps` and FreeBSD's; a BusyBox applet
  documents the `=header` form and nothing else of it, and a script for a minimal image checks for failure. [DER S-ocglo5m3, S-d4mf4bbv: the FreeBSD page against the BusyBox help]
- A sampler of a process tree can read `ps -A -o pid=,ppid=,rss=,time=,args=` on macOS and Linux: `rss` is in
  kibibytes on both pages, so one division by 1024 gives MiB for both, and on Linux `time` is a `[DD-]hh:mm:ss`
  clock text whose finest step is one second, so a CPU figure from it moves in one-second steps and a short window
  sees a change only after a second of CPU. [DER S-glwifmco, S-ggxrmcqc: `rss` units on the two pages and the
  procps-ng `time` format; the one-second step follows from the `hh:mm:ss` form and was not run]
- Without `-S` a parent's `time` on macOS does not include children that have exited, so a sampler that sums `time`
  over the live processes of a tree loses the CPU of a child that ends between two samples, and under-counts a tree
  that starts many short processes. [DER S-ggxrmcqc: the `-S` description, which names exited children summed into
  the parent only with that option; the Linux page was not read for an equivalent]
- Apple's `ps` page states no clock format for `time` or `etime`, and no run of either `ps` here checked the text of
  its `time` column. [UNK: the adv_cmds-237 page gives only "accumulated CPU time, user + system"]
- A Linux image whose `ps` is a BusyBox applet was not run for `-A`, empty headers or `pcpu`. [UNK: BusyBox's page lists too few options to settle it]

## Reference
- Related: `python/stdlib-os-loadavg.md` (the kernel's run-queue average and how to read it against the CPU
  count), `python/stdlib-windows-portability.md` (what the stdlib lacks on Windows), `claude/powershell-tool.md`
  (`ps` among the read-only commands).
- Sources: the POSIX.1-2024 `ps` page, the procps-ng `ps(1)` page on man7.org, Apple's `ps.1` at tag
  `adv_cmds-237`, and the Learn pages for `Get-Process`, `Get-Counter`, Collecting Performance Data and decoding
  a PowerShell command from a running process.

## Examples
- SNIPPET: one POSIX listing with no header, parsed into pid, CPU percent and command line; context: macOS and
  Linux, Python 3.x, the standard library only; checked: syntax [DER S-tldzr3mf: the argument list is the
  specification's `-A` and `-o` with empty headers]
```python
import subprocess

out = subprocess.run(
    ["ps", "-A", "-o", "pid=,pcpu=,args="], capture_output=True, text=True, check=True
).stdout
rows = []
for line in out.splitlines():
    pid, pcpu, args = line.split(None, 2)
    rows.append((int(pid), float(pcpu), args))
```
- SNIPPET: the Windows percentages per process, from two one-second samples; context: PowerShell 7 on
  Windows, counter names are localised; checked: no [DER S-wh6i6rv4: the page's own `Get-Counter` example with
  `\Process(*)\% Processor Time`]
```powershell
$s = Get-Counter -Counter '\Process(*)\% Processor Time' -SampleInterval 1 -MaxSamples 2
$s[1].CounterSamples | Sort-Object CookedValue -Descending | Select-Object InstanceName, CookedValue -First 5
```
