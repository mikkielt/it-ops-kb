---
topic: python/macos-fs-usage-output
priority: P3
applies_to: "macOS fs_usage(1) as in Apple's system_cmds-1042.120.1 (man page and source), used as `fs_usage -w -f filesys`"
retrieved_utc: 2026-10-26
sources: [S-iezgwy2f, S-bj2723hr]
status: partial
---

# macOS fs_usage -w -f filesys: the columns of a line, which calls are reads, and what the number after the process name is

## Summary
`fs_usage` traces filesystem system calls and needs root. With `-w` each line ends in `process-name.NNN`, and the
number is a thread id, not a pid (the man page says so and the source prints the thread id there). A line is the
timestamp, the call name, then fields chosen by the call (`F=` descriptor, `B=` byte count, `O=` offset, a
bracketed errno), the path, the elapsed time with an optional `W`, and the process name. The man page does not say
which calls are reads; the source marks an `open` as read access with an `R` in its first mode character, lists
`read`, `pread`, `readv` and `preadv` as descriptor reads, and prints physical reads as `RdData`.

## Facts
### The man page: options and columns
- `fs_usage` requires root privileges because of the kernel tracing facility it uses. [DOC S-iezgwy2f]
- By default the monitored activity includes all processes except the running `fs_usage`, Terminal, telnetd,
  telnet, sshd, rlogind, tcsh, csh, sh and zsh; a list of processes (pids or command names) limits the output to them,
  and `-e` excludes the listed ones. [DOC S-iezgwy2f]
- `-w` forces a wide display regardless of the window size, and `-f filesys` shows filesystem-related events; the
  page's own sample is `fs_usage -w -f filesys Mail`, all instances of processes named Mail. [DOC S-iezgwy2f]
- The data columns are TIMESTAMP, CALL, FILE DESCRIPTOR, BYTE COUNT, [ERRNO], PATHNAME, FAULT ADDRESS, DISK BLOCK
  NUMBER, OFFSET, SELECT RETURN, TIME INTERVAL(W) and PROCESS NAME. [DOC S-iezgwy2f]
- The file descriptor column is `F=x`, an input value or a return value depending on the call; the byte count is
  `B=x`, the number of bytes requested; on error the errno is shown in brackets; the offset is `O=0xnnnnnnnn`. [DOC S-iezgwy2f]
- The pathname is the file accessed, "up to the last 28 bytes" (the default trims from the left, `-F` trims from the
  right); the time interval is the elapsed time in the call, and a `W` after it means the process was scheduled out
  and the time includes the wait. [DOC S-iezgwy2f]
- The process name column is "the process that made the system call", and wide mode appends the thread id to it
  (`Mail.nnn`). [DOC S-iezgwy2f]
- Wide mode gives the timestamp microsecond granularity. [DOC S-iezgwy2f]
- The page does not say which calls count as reads and does not describe the open-mode letters. [DER S-iezgwy2f:
  the option, column and sample text of the page, read in full, names neither]

### The source: what the fields print
- The last field of a wide line is printed as the process name, a dot and an unsigned number taken from the trace
  event's thread id (`threadid`); the pid is held in a separate variable, used for filtering, and is not printed
  there. [CODE S-bj2723hr: fs_usage.c#format_print]
- Without `-w`, on a window of at most 132 columns the process name is printed in 12 characters and no thread id
  follows. [CODE S-bj2723hr: fs_usage.c#format_print]
- An `open`, `open_extended`, `open_dprotected_np` or `openat` line shows `F=<fd>` (or `[errno]` on failure) and a
  mode string whose first character is `R` for a read-only or read-write open, and whose second is `W` for a
  write-only or read-write open; the rest of the string marks create, append, truncate and similar flags. [CODE
  S-bj2723hr: fs_usage.c#print_open]
- `read`, `readv`, `pread` and `preadv` (and their no-cancel forms) are among the traced calls; a `read` or `readv`
  line prints `F=<fd>` and `B=0x<count>` (the code's comment calls the count an I/O completion count), a `pread` or
  `preadv` line adds the offset as `O=`, and on an error `F=<fd>[<errno>]` replaces the count. [CODE S-bj2723hr:
  fs_usage.c#format_print FMT_FD_IO, FMT_PREAD]
- A physical read is a separate line named `RdData` (metadata reads `RdMeta`, page-ins `PgIn`); with `-f filesys`
  the filter returns true for such a disk-I/O record, so it is shown beside the system calls. [CODE S-bj2723hr:
  fs_usage.c#diskio_print, check_filter_mode]
- A physical disk I/O line (`RdData`, `RdMeta`, `PgIn` and the write forms) prints ` D=0x<block number>`, ` B=0x<size>`
  and ` /dev/<disk name>` first, and only then the pathname column, taken from the I/O's vnode when the code can
  resolve one; a vnode it cannot resolve gives an empty pathname, so the line then ends in the device and no file
  path. [CODE S-bj2723hr: fs_usage.c#format_print FMT_DISKIO]
- For a metadata disk I/O the code looks a name up by block number only when the record is not a read; an `RdMeta`
  line takes no name from that lookup. [CODE S-bj2723hr: fs_usage.c#format_print FMT_DISKIO, `is_meta` branch]
- A disk I/O that completed with an error prints `D=0x<block number>  [<errno>]` instead, with no size and no `/dev/`
  token; CoreStorage records (`RdChunkCS`, `WrChunkCS`, `RdMetaCS`) print `D=`, `B=` and `/dev/<name>` and no
  pathname at all. [CODE S-bj2723hr: fs_usage.c#format_print FMT_DISKIO, FMT_DISKIO_CS]

### What follows for counting file reads per process class
- A count of "reads" is a choice among three line kinds that the man page does not rank: `open` lines with `R` in the
  mode, descriptor reads (`read`, `pread`, `readv`, `preadv`), and `RdData` physical reads, which are not the same
  count (a descriptor read and a disk read are different records). A counter says which kind it counts. [DER S-iezgwy2f, S-bj2723hr: the
  page lists columns only; the source defines the three line kinds]
- A counter of distinct file paths that takes the first `/`-token of a disk I/O line takes the `/dev/<disk>` device,
  not a file; it skips the token that follows `B=0x<size>` as a device and counts a path only when text follows it, so
  a `RdData` line with a device and no file path adds nothing to the set of paths. [DER S-bj2723hr: the device is
  printed before the pathname and the pathname may be empty]
- How often a `RdData` line of a real capture carries no resolved path was not measured. [UNK: no run of `fs_usage`,
  root is needed]
- The number after the process name identifies a thread, so grouping lines into a process class (hook shell,
  `node`, `python3`) goes by the process name before the dot, or by a pid operand to `fs_usage`, never by that
  number. [DER S-iezgwy2f, S-bj2723hr: the number is a thread id]
- The default exclusions include `sh` and `zsh`, so reads by a hook wrapper that runs under those shells are not in
  a default capture. [DER S-iezgwy2f: the page's default exclusion list]
- Whether naming `sh` or `zsh` as an operand brings their lines back was not run. [UNK: the page says the defaults can
  be overridden and does not show the operand form for an excluded name]
- Whether a pid appears in any column was not found: the man page's column list names none and the source prints the
  thread id; no capture was run here (root is needed). [UNK: no run of `fs_usage`]

## Reference
- Related: `python/rusage-maxrss-units.md` (the other host-cost figure), `python/ps-process-cpu.md` (per-process
  CPU).
- Sources: Apple's `fs_usage.1` and `fs_usage.c` at tag `system_cmds-1042.120.1`.

## Examples
- SNIPPET: count lines per process name from `fs_usage -w -f filesys` output on stdin; context: macOS, Python 3.x,
  names without blanks; checked: syntax [DER
  S-iezgwy2f: `-w -f filesys` and the dot before the thread id]
```python
import collections
import re
import sys

counts = collections.Counter()
for line in sys.stdin:
    m = re.search(r"(\S+)\.(\d+)\s*$", line)
    if m:
        counts[m.group(1)] += 1
```
