---
topic: python/stdlib-windows-portability
priority: P3
applies_to: "CPython 3.14.7 documentation (release tag); stdlib behaviour on Windows versus POSIX for detached processes, file locks, text files and interpreter names"
retrieved_utc: 2026-09-28
sources: [S-dabwnzz5, S-ew7mucsg, S-oavxfpsn, S-f5bnvamj, S-ntbllsvy, S-sjuwcuhk]
status: partial
---

# Python stdlib on Windows: detached processes, locks, text files, interpreter names

## Summary
A stdlib-only tool that must run on macOS, Linux and Windows meets four differences. Detaching a child uses
`start_new_session` (POSIX only) on one side and the `creationflags` `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`
on the other. `fcntl` is Unix-only, so a lock that works everywhere uses what both sides have: `os.open` with
`O_CREAT | O_EXCL`, or `os.mkdir`, which fails when the directory exists; `msvcrt.locking` is the Windows-only
byte-range lock. `open()` in text mode picks the locale encoding and translates `\n` to `os.linesep` unless told
otherwise, so every read and write passes `encoding="utf-8"` and writes `newline="\n"`. On Windows the documented
commands are `python` and `py`; `python3` exists only as a compatibility alias.

## Facts
### Detached processes
- `start_new_session=True` makes the child call `setsid()` before it runs; the parameter is POSIX only. [DOC S-dabwnzz5]
- `process_group` (3.11+) calls `setpgid(0, value)` in the child before it runs; POSIX only. [DOC S-dabwnzz5]
- `DETACHED_PROCESS` (3.7+) is a Popen `creationflags` value: the new process does not inherit its parent's console; it cannot be combined with `CREATE_NEW_CONSOLE`. [DOC S-dabwnzz5]
- `CREATE_NEW_PROCESS_GROUP` is a `creationflags` value that creates a new process group, needed for `os.kill` on the subprocess; it is ignored with `CREATE_NEW_CONSOLE`. [DOC S-dabwnzz5]
- `creationflags` values are passed to `CreateProcess`; the documented list also includes `CREATE_NO_WINDOW` and `CREATE_BREAKAWAY_FROM_JOB`. [DOC S-dabwnzz5]
- A launcher that must return at once and leave a child running uses `start_new_session=True` on POSIX and `creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP` on Windows, with stdin, stdout and stderr redirected (e.g. to `DEVNULL` or a log file) so the parent's pipes do not hold it. [DER S-dabwnzz5: the POSIX-only session parameter and the two Windows flags above]
- Whether Claude Code puts hook processes in a Windows job object that ends their children when the hook exits (which `CREATE_BREAKAWAY_FROM_JOB` would address) is not stated in the Python or Claude Code docs. [UNK: not in the hooks reference or the subprocess docs; a Windows test of the launcher decides]

### File locks without fcntl
- The `fcntl` module is available on Unix only (not WASI). [DOC S-oavxfpsn]
- `os.O_CREAT`, `os.O_EXCL` and the other basic `os.open` flags are available on Unix and Windows. [DOC S-ew7mucsg]
- `os.mkdir` raises `FileExistsError` when the directory already exists. [DOC S-ew7mucsg]
- `open()` mode `'x'` opens for exclusive creation and fails if the file already exists. [DOC S-ntbllsvy]
- `msvcrt.locking(fd, mode, nbytes)` locks a byte range of a file from the C runtime and raises `OSError` on failure; `LK_NBLCK` raises at once when the bytes cannot be locked; the module is Windows only. [DOC S-f5bnvamj]
- On Windows, `os.kill` sends only `CTRL_C_EVENT` and `CTRL_BREAK_EVENT` as signals; any other value terminates the process through `TerminateProcess` with that value as its exit code. [DOC S-ew7mucsg]
- A stale-lock check must not call `os.kill(pid, 0)` on Windows: 0 is "any other value", so the check would kill the lock holder. A portable lock is an `O_EXCL` file (or a directory from `os.mkdir`) holding the owner's PID and start time, with a staleness rule that does not signal the process, such as an age limit. [DER S-ew7mucsg, S-oavxfpsn: `os.kill` on Windows, `O_EXCL` and `mkdir` on both, `fcntl` Unix-only]

### Text files
- In text mode without `encoding`, `open()` uses the locale encoding from `locale.getencoding()`, which is platform dependent. [DOC S-ntbllsvy]
- When writing with `newline=None` (the default), each `\n` becomes `os.linesep`; with `newline=''` or `'\n'` no translation happens. [DOC S-ntbllsvy]
- A tool whose files must be identical on every OS opens them with `encoding="utf-8"` and writes with `newline="\n"`; otherwise Windows writes `\r\n` and a locale code page such as cp1252. [DER S-ntbllsvy: default encoding and newline translation above]

### Interpreter names on Windows
- With the Python install manager, the `python`, `py` and `pymanager` commands are available; `py` is recommended where several runtimes exist, and the versioned aliases (`python3.14.exe`) need an optional `PATH` entry. [DOC S-sjuwcuhk]
- A `python3` command is included to catch accidental uses of the POSIX name, and is not meant to be widely used or recommended. [DOC S-sjuwcuhk]
- `py` selects a runtime with `-V:<TAG>` given before any other option; for an official release whose tag starts with `3` the `V:` may be omitted, so `py -3` asks for a Python 3 runtime. [DOC S-sjuwcuhk]
- A script that must find the interpreter on every OS tries `python3`, then `python`, then `py -3`, and checks that the one it found runs (a `-c` probe), since a name on `PATH` can be an alias rather than the runtime. [DER S-sjuwcuhk: command names above]

## Reference
| Need | POSIX | Windows | Source |
|---|---|---|---|
| Detach a child | `start_new_session=True` | `creationflags=DETACHED_PROCESS \| CREATE_NEW_PROCESS_GROUP` | S-dabwnzz5 |
| Exclusive lock file | `os.open(p, O_CREAT \| O_EXCL \| O_WRONLY)` | same | S-ew7mucsg |
| Lock directory | `os.mkdir(p)` (`FileExistsError`) | same | S-ew7mucsg |
| Advisory lock | `fcntl.flock` | `msvcrt.locking` | S-oavxfpsn, S-f5bnvamj |
| Is PID alive | `os.kill(pid, 0)` | not `os.kill` (terminates) | S-ew7mucsg |
| Interpreter | `python3` | `python`, `py -3` | S-sjuwcuhk |

Related: `python/stdlib-sqlite3-csv.md` (csv files open with `newline=''`); `claude/hooks.md` (how Claude Code runs
hook commands on Windows); `gitlab/hosted-runners-windows.md` (a Windows CI job for these tools).

## Examples
- SNIPPET: start a detached child from a hook launcher on POSIX and Windows; context: Python 3.11+ stdlib; checked: syntax [DOC S-dabwnzz5: `start_new_session`, `DETACHED_PROCESS`, `CREATE_NEW_PROCESS_GROUP`]
```python
import subprocess
import sys


def launch(args, log_path):
    kw = {"stdin": subprocess.DEVNULL, "stderr": subprocess.STDOUT}
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    with open(log_path, "ab") as log:
        return subprocess.Popen(args, stdout=log, **kw).pid
```
- SNIPPET: a per-machine lock without fcntl; context: Python 3.11+ stdlib; checked: syntax [DER S-ew7mucsg: `O_CREAT | O_EXCL` on Unix and Windows; age-based staleness because `os.kill` terminates on Windows]
```python
import os
import time


def acquire(path, max_age=3600):
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        if time.time() - os.path.getmtime(path) < max_age:
            return False
        os.remove(path)
        return acquire(path, max_age)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"{os.getpid()} {time.time():.0f}\n")
    return True
```
