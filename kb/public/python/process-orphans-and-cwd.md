---
topic: python/process-orphans-and-cwd
priority: P3
applies_to: "POSIX.1-2024 process model (orphaned process group, parent id after exit, setsid, ps ppid and pgid); Linux man-pages 6.19 (getppid, setsid, subreaper, /proc/PID/cwd); macOS reading of a process's working directory through lsof 4.99.5's manual and the xnu-12377.1.9 libproc headers"
retrieved_utc: 2026-10-21
sources: [S-w6stdctp, S-xp4b2g5v, S-tldzr3mf, S-dwwfdbtg, S-fcdwaly4, S-6xelj6je, S-vvqjpqvl, S-ppkjvumt, S-ifgjakdt, S-4qybivhq, S-dabwnzz5]
status: partial
---

# Processes whose parent is gone, detached process groups, and reading another process's working directory

## Summary
When a POSIX process ends, its children are not ended with it: each gets the id of a system process as its new
parent. On Linux that is `init`, or the nearest living ancestor that declared itself a "subreaper"; on other
systems the standard calls it an implementation-defined system process. So a parent id of 1 on its own says only
that the real parent is gone. A launcher that called `setsid()` (Python's `start_new_session=True`) is the
leader of its own session and process group, which is how a deliberately detached process differs from a
leftover that still sits in another process's group. The working directory of another process, the usual way to
tell which checkout a process belongs to, is a symbolic link under `/proc/PID/cwd` on Linux (access governed by
a ptrace check), a `cwd` file descriptor line of `lsof`, or a `proc_pidinfo` flavour on macOS.

## Facts
### POSIX: orphans and parent ids
- An orphaned process group is one in which the parent of every member is either itself a member of the group or
  is not a member of the group's session. [DOC S-w6stdctp]
- On exit, the parent id of all existing child processes and zombies of the exiting process is set to the id of an
  implementation-defined system process, which "inherits" them; the standard adds that ending a process does not
  directly end its children. [DOC S-xp4b2g5v]
- The rationale names that system process `init` with process id 1 as the historical case, not as a requirement.
  [DOC S-xp4b2g5v]
- A process group becomes orphaned when the last parent outside the group ends or when the last direct
  descendant of such a parent ends; a newly orphaned group that holds stopped processes is sent `SIGHUP` and
  `SIGCONT`. [DOC S-xp4b2g5v]
- The standard `ps` has the names `ppid` (parent process id) and `pgid` (process group id) for `-o`, so
  `ps -A -o pid=,ppid=,pgid=,args=` is a standard listing of each process with both ids. The Apple and procps-ng
  pages were not read for these two names. [DOC S-tldzr3mf]

### Sessions and process groups: setsid
- `setsid()` creates a new session when the caller is not a process group leader; the caller becomes the session
  leader and the leader of a new process group in it, alone in both, and the session starts without a
  controlling terminal. [DOC S-dwwfdbtg]
- `setsid()` fails with `EPERM` when any process's group id equals the caller's pid, so it fails for a process
  that is already a group leader; the page's way to be sure of success is `fork`, `_exit` in the parent and
  `setsid` in the child. [DOC S-dwwfdbtg]
- A child made by `fork` inherits its parent's session id, and the session id survives `execve`. [DOC S-dwwfdbtg]
- Python's `subprocess` documents `start_new_session=True` as making the child call `setsid()` before it runs,
  on POSIX only. [DOC S-dabwnzz5]
- So a child started with `start_new_session=True` has a process group id and a session id equal to its own pid
  and shares its group with nobody until it forks; a leftover process in the group of a parent that ended has a
  group id that is not its pid. [DER S-dwwfdbtg, S-dabwnzz5, S-tldzr3mf: the `setsid` effect, the Python flag and
  the `pgid` name]

### Linux: where an orphan goes
- `getppid()` returns the creator's id, or, if the creator has ended, the id of the process the caller was
  reparented to: `init` or a subreaper set with `prctl`; when the caller's parent is in another PID namespace it
  returns 0. [DOC S-fcdwaly4]
- `PR_SET_CHILD_SUBREAPER` makes the caller fill the role of `init` for its descendants: an orphan is reparented
  to the nearest living ancestor that is a subreaper, `getppid()` in the orphan then returns the subreaper's pid,
  and the subreaper gets the `SIGCHLD`. The attribute is not inherited by `fork` children and survives `execve`;
  the call exists since Linux 3.4. [DOC S-6xelj6je]
- The page says some `init` frameworks, `systemd` named, use a subreaper for similar reasons, so on a Linux host a
  leftover's parent id may be a subreaper's pid, not 1. [DER S-6xelj6je: subreaper reparenting and the `systemd`
  remark]

### Reading another process's working directory
- On Linux `/proc/PID/cwd` is a symbolic link to the process's current working directory (`cd /proc/20/cwd; pwd -P`
  is the page's example); in a multithreaded process the link is not available once the main thread has
  ended. [DOC S-vvqjpqvl]
- Permission to follow or `readlink` that link is governed by a ptrace access check, `PTRACE_MODE_READ_FSCREDS`, so
  the answer for another user's process depends on the caller's credentials and the host's ptrace
  policy. [DOC S-vvqjpqvl]
- `lsof` lists the current working directory as a file descriptor named `cwd`; `-d cwd` selects it, and `-a`
  makes all selection options combine with AND, which the manual's own example (`lsof -c ... -a -d cwd`) uses to list
  working directories of processes of one command. [DOC S-ppkjvumt]
- `lsof` prints `UNKNcwd` as the name for an unknown current working directory. [DOC S-ppkjvumt]
- On macOS, `proc_pidinfo(pid, flavor, arg, buffer, buffersize)` is declared in `libproc.h`, and the flavour
  `PROC_PIDVNODEPATHINFO` (9) fills a `proc_vnodepathinfo` holding `pvi_cdir` (current directory) and `pvi_rdir`
  (root directory), each a `vnode_info_path` with a path buffer of `MAXPATHLEN` characters whose source comment
  reads "tail end of it". [CODE S-ifgjakdt, S-4qybivhq: libproc.h#proc_pidinfo, proc_info.h#proc_vnodepathinfo]
- A tool that must say which checkout a process runs in therefore reads `/proc/PID/cwd` on Linux and an
  `lsof -a -d cwd -p PID`-style listing or `proc_pidinfo` on macOS; on Linux the ptrace check can refuse the read,
  so "no working directory read" has to be a state of its own, not "outside every checkout". [DER S-vvqjpqvl,
  S-ppkjvumt, S-4qybivhq: the ptrace access check and the read paths above]

### Not confirmed
- Which process becomes the parent of an orphan on macOS (a launchd pid, with or without a subreaper notion) is
  not stated on the POSIX page, which leaves it implementation-defined, and Apple's documentation was not read
  for it. [UNK: no Apple page read; Linux man-pages and POSIX only]
- Whether the `lsof` that ships with macOS accepts `-a -d cwd -p PID` as the 4.99.5 manual describes, and whether
  it reports the working directory of another user's process without elevation, was not read or run. [UNK: only the
  upstream 4.99.5 manual was read]
- Whether the `proc_pidinfo` call succeeds for another user's process without elevation is not stated in the
  headers. [UNK: the headers carry no access note]
- Whether Windows exposes a working directory for another process is not covered here; its parent id and command
  line are in `windows/process-parent-and-command-line.md`. [UNK: out of scope of the pages read]

## Reference
- Related: `python/ps-process-cpu.md` (the portable `ps -A -o` listing), `python/stdlib-windows-portability.md`
  (detached children on Windows and the `start_new_session` flag), `windows/process-parent-and-command-line.md`
  (parent id and command line on Windows).
- Sources: POSIX.1-2024 definitions (3.247 Orphaned Process Group) and `_Exit`, `ps`; man7.org pages `getppid(2)`,
  `setsid(2)`, `PR_SET_CHILD_SUBREAPER(2const)` and `proc_pid_cwd(5)`; the `lsof` 4.99.5 manual; the xnu
  `libproc.h` and `proc_info.h` at tag `xnu-12377.1.9`.

## Examples
- SNIPPET: list every process with its parent and group id, then pick the group leaders (group id equal to pid),
  which includes any `setsid` caller; context: POSIX `ps`, Python 3.x, the standard library only; checked: syntax
  [DER S-tldzr3mf, S-dwwfdbtg: `ppid` and `pgid` names; a `setsid` caller is its own group leader]
```python
import subprocess

out = subprocess.run(
    ["ps", "-A", "-o", "pid=,ppid=,pgid=,args="], capture_output=True, text=True, check=True
).stdout
rows = []
for line in out.splitlines():
    pid, ppid, pgid, args = line.split(None, 3)
    rows.append((int(pid), int(ppid), int(pgid), args))
group_leaders = [r for r in rows if r[0] == r[2]]
```
