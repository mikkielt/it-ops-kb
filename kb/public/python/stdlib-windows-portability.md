---
topic: python/stdlib-windows-portability
priority: P3
applies_to: "CPython 3.14.7 documentation (release tag); stdlib behaviour on Windows versus POSIX for detached processes, file locks, text files and interpreter names"
retrieved_utc: 2026-10-05
sources: [S-dabwnzz5, S-ew7mucsg, S-oavxfpsn, S-f5bnvamj, S-ntbllsvy, S-sjuwcuhk, S-6bobcclf, S-e4zz24dq, S-ttcgrkbl, S-obrkrr52, S-hjy5rcb2, S743, S-5brdhqgo, S-jwv5eevl]
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
- `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` (0x00002000) causes all processes associated with a job to terminate when the last handle to the job is closed; with `JOB_OBJECT_LIMIT_BREAKAWAY_OK` (0x00000800) in effect, a child created with `CREATE_BREAKAWAY_FROM_JOB` is not associated with the job. [DOC S-obrkrr52]
- `IsProcessInJob` with a NULL job handle tests whether a process runs under any job; a process cannot open the job it runs in without its name, but `QueryInformationJobObject` with NULL returns that job's information. [DOC S-hjy5rcb2]
- Observed on Claude Code 2.1.285 (Windows 11 with Git for Windows, 2026-09-30), not documented behaviour: in a headless (`claude -p`) and an interactive session alike, a hook in shell form (run by Git Bash) was in no job, and a hook with `"shell": "powershell"` was in a job whose only limit was `BREAKAWAY_OK` (no `KILL_ON_JOB_CLOSE`); in the headless runs, children started with `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`, with or without `CREATE_BREAKAWAY_FROM_JOB`, were alive 11 to 12 seconds after Claude Code exited. The launcher keeps `CREATE_BREAKAWAY_FROM_JOB`, which a job would have to allow; another version is re-checked with the same probe. [DER S-hjy5rcb2, S-obrkrr52, S743: the hook called IsProcessInJob and QueryInformationJobObject(NULL) on itself and read LimitFlags against the flags above; hook shells per S743]

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

### Command-line length
- `CreateProcessW` takes the command line as one string, `lpCommandLine`, whose maximum length is 32,767 characters (written 32767 in shell scripts) including the terminating null character; with a null `lpApplicationName`, the module-name part is limited to `MAX_PATH`. [DOC S-6bobcclf]
- Command Prompt (`cmd.exe`) limits the string it processes to 8191 characters (8,191): the command line, individual environment variables inherited by other processes, and all variable expansions; the limit also applies to commands in a batch file it runs. [DOC S-e4zz24dq]
- Command Prompt ignores an inherited environment variable longer than 8191 characters even though the Win32 limit is 32,767; Microsoft's workaround is a parameter file named on the command line, with the program reading its parameters from it. [DOC S-e4zz24dq]
- When `args` is a sequence, `subprocess` converts it to one string using the MS C runtime quoting rules before `CreateProcess`, so quoting can make the string longer than the arguments alone. [DOC S-dabwnzz5]
- With `shell=True` on Windows, the shell is `%COMSPEC%` (normally `cmd.exe`), and the docs say `shell=True` is needed only for shell built-ins such as `dir` or `copy`, not for batch files or console executables. [DOC S-dabwnzz5]
- The system error code for a command line, path or extension that is too long is 206, `ERROR_FILENAME_EXCED_RANGE`: "The filename or extension is too long." A `[WinError 206]` from `subprocess` is therefore the string limit above, not a missing program. [DOC S-ttcgrkbl; DER S-6bobcclf: the 32,767-character maximum and the error code meaning]
- A child started with a list of arguments and `shell=False` faces the 32,767-character limit (and its quoted form counts); through `cmd /c` the 8191 limit applies. A test or tool that must pass more than about 30,000 characters to a Windows child sends it through stdin or a file, not argv. [DER S-6bobcclf, S-e4zz24dq, S-dabwnzz5: the two limits and `subprocess`'s conversion; the "about 30,000" margin allows for quoting and the program path]
- `os.link(src, dst)` creates a hard link named *dst* to *src* and is available on Unix and on Windows (since Python 3.2); the page does not say what it raises when the two paths are on different filesystems. [DOC S-5brdhqgo]
- `shutil.copytree(src, dst, copy_function=...)` copies each file with the callable it is given, called with the source and the destination path (default `shutil.copy2`); with `dirs_exist_ok=True` it continues into existing directories and overwrites files there. [DOC S-jwv5eevl]
- So a test that copies a tree it only partly writes can pass `copy_function=os.link` (falling back to a copy where the link fails, such as across filesystems) and replace each file it writes with a fresh copy before writing, since a write through a hard link changes every name of the file. [DER S-5brdhqgo, S-jwv5eevl]
- `shutil.copy2` is `copy` that also attempts to preserve file metadata, through `copystat`, which copies the permission bits, last access time, last modification time and flags; `copy2` never raises because it could not preserve metadata. [DOC S-jwv5eevl]
- So a cache keyed on files' modification times (`st_mtime_ns`) still matches after a `copytree` with the default `copy2`, but not after a plain `shutil.copy`, which leaves them out; a key that must survive a copy at another path hashes the files' content and their paths relative to the root instead. [DER S-jwv5eevl: copy2 keeps the times, copy does not]
- Open: what modification time a fresh `git clone` or `git worktree add` gives the files it checks out is not stated on a git page the kb cites. [UNK: see `_gaps.md`]
- Open: the error `os.link` raises across filesystems or volumes is not on the page. [UNK]

## Reference
| Need | POSIX | Windows | Source |
|---|---|---|---|
| Detach a child | `start_new_session=True` | `creationflags=DETACHED_PROCESS \| CREATE_NEW_PROCESS_GROUP` | S-dabwnzz5 |
| Exclusive lock file | `os.open(p, O_CREAT \| O_EXCL \| O_WRONLY)` | same | S-ew7mucsg |
| Lock directory | `os.mkdir(p)` (`FileExistsError`) | same | S-ew7mucsg |
| Advisory lock | `fcntl.flock` | `msvcrt.locking` | S-oavxfpsn, S-f5bnvamj |
| Is PID alive | `os.kill(pid, 0)` | not `os.kill` (terminates) | S-ew7mucsg |
| Interpreter | `python3` | `python`, `py -3` | S-sjuwcuhk |
| Longest command line | not this limit | 32,767 characters (`CreateProcessW`); 8191 through `cmd.exe` | S-6bobcclf, S-e4zz24dq |

Related: `python/windows-python-install.md` (installing Python and the Store `python3` shortcut); `python/stdlib-sqlite3-csv.md` (csv files open with `newline=''`); `claude/hooks.md` (how Claude Code runs
hook commands on Windows); `gitlab/hosted-runners-windows.md` (a Windows CI job for these tools); `python/interpreter-startup.md`
(what starting a child costs: `CreateProcess()` versus `vfork`/`posix_spawn`, and the start-up options).

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
