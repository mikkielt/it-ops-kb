---
topic: python/stdlib-windows-portability
priority: P3
applies_to: "CPython 3.14.7 documentation (release tag); stdlib behaviour on Windows versus POSIX for detached processes, file locks, text files and interpreter names"
retrieved_utc: 2026-10-18
sources: [S-vfd5kpka, S-hlwenztu, S-kyzwo2d6, S-2cf7ptty, S-dabwnzz5, S-ew7mucsg, S-oavxfpsn, S-f5bnvamj, S-ntbllsvy, S-sjuwcuhk, S-6bobcclf, S-e4zz24dq, S-ttcgrkbl, S-obrkrr52, S-hjy5rcb2, S743, S-5brdhqgo, S-jwv5eevl, S-ymqlfpgy, S-ujjrcinq, S-t5ahy22o, S-qz6kfi4i, S-qo63gfo7, S-edjp43o7, S-oqrlzkwe, S-ip5ugdeb, S-5qbsemqm, S-7ctlvynr, S-inakn5ad, S-qvjkxdub, S-kkrnrh7n, S-j6wqryzp, S-iv3usyoz, S-ctjl4gek, S-4a5xeg5l, S-zch3x2zi]
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
commands are `python` and `py`; `python3` exists only as a compatibility alias. Escape sequences printed to the Windows
console act only when `ENABLE_VIRTUAL_TERMINAL_PROCESSING` is set on the screen buffer, which CPython reads but does not
set; `ESC [ H` then `ESC [ 2 J` homes the cursor and erases the display. Bold red text is `ESC [ 31 ; 1 m` and the reset is
`ESC [ 0 m`; the NO_COLOR convention (no-color.org) asks software that adds ANSI colour by default to add none when the
variable is set to a non-empty value.

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
- Observed on Claude Code 2.1.294 (Windows 11, Python 3.14.7, one interactive session started from Windows PowerShell 5.1 in its own console, 2026-10-08), not documented behaviour: after `/exit`, the query log's `SessionEnd` launcher had written its `.end` marker and started the detached distill (`DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`, `CREATE_BREAKAWAY_FROM_JOB` tried first, then the call without it on an `OSError`) by 0.66 s, `claude.exe` had exited at 1.14 s, and the distill wrote its run file at 14.16 s, 13 s after the session's process had ended; the launcher alone returned in 0.098 to 0.143 s over five planted runs. The run did not read the hook's job, and the launcher does not record which of its two calls started the child, so it shows that the detached child outlived the session, not whether `CreateProcess` accepted, refused or ignored the breakaway flag. It covers one interactive session, not a headless one, another version or another way of starting the session. [DER S-ymqlfpgy, S-ujjrcinq: the flag and the job association rules above, read against the recorded run]
- Win32 `DETACHED_PROCESS` (0x00000008): for console processes, the new process does not inherit its parent's console, and it can call `AllocConsole` later to create one; it cannot be used with `CREATE_NEW_CONSOLE`. [DOC S-ymqlfpgy]
- Win32 `CREATE_NEW_PROCESS_GROUP` (0x00000200): the new process is the root of a new process group whose identifier is the process identifier `CreateProcess` returns; process groups serve `GenerateConsoleCtrlEvent` to send CTRL+BREAK to a group of console processes, and CTRL+C is disabled for all processes in the new group; the flag is ignored with `CREATE_NEW_CONSOLE`. [DOC S-ymqlfpgy]
- Win32 `CREATE_BREAKAWAY_FROM_JOB` (0x01000000): "the child processes of a process associated with a job are not associated with the job"; it has no effect when the calling process is in no job, and when the caller is in a job, "the job must set the `JOB_OBJECT_LIMIT_BREAKAWAY_OK` limit". [DOC S-ymqlfpgy]
- By default a child that a process in a job creates with `CreateProcess` is associated with the job too, a process's association with a job cannot be broken once made, and a child created through `Win32_Process.Create` is not associated with the job. [DOC S-ujjrcinq]
- Two job limits change that default: with `JOB_OBJECT_LIMIT_BREAKAWAY_OK`, a child created with `CREATE_BREAKAWAY_FROM_JOB` is outside the job; with `JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK`, children of any process in the job are outside it, without the flag. [DOC S-ujjrcinq]
- A job is destroyed when its last handle is closed and all its processes have ended; with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, closing the last handle ends all associated processes first. [DOC S-ujjrcinq]
- The two flags the launcher passes besides breakaway are described only in terms of the console and Ctrl signals; neither page says either flag changes which job a process belongs to. So a child that must outlive a parent's job object leaves the job only through `CREATE_BREAKAWAY_FROM_JOB` (when the job sets `JOB_OBJECT_LIMIT_BREAKAWAY_OK`) or a job with `JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK`; `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP` alone leave it in a job that ends its processes on close, and add nothing in a job that does not. [DER S-ymqlfpgy, S-ujjrcinq: the flag descriptions and the job association rules above]
- Open: what `CreateProcess` returns when `CREATE_BREAKAWAY_FROM_JOB` is passed from a process whose job lacks `JOB_OBJECT_LIMIT_BREAKAWAY_OK` is not stated; the page says only that the job "must set" the limit, so a launcher that retries without the flag on failure rests on that unstated behaviour; the 2.1.294 run above does not show which call started the child. [UNK: see `_gaps.md`]
- Open: the two pages word the flag's effect differently (the flags page: the caller's children; the Job Objects page: a parent "created with" the flag has unassociated children, while its process-tree section passes the flag when creating the child that should leave); the kb reads the flag as acting on the child being created, as the process-tree section does; the 2.1.294 run above, which read no job, does not settle it. [UNK: see `_gaps.md`]

### Directory held as a working directory
- Each process has a single current directory, made of a disk designator (a drive letter and colon, or `\\server\share`) and a directory on it, shared by all threads of the process; `SetCurrentDirectory` stores the full path calculated from the path it is given. [DOC S-qz6kfi4i]
- "The current directory for a process is locked while the process is executing. That prevents the directory from being deleted, moved, or renamed." [DOC S-qz6kfi4i]
- With a null `lpCurrentDirectory`, `CreateProcess` gives the new process the same current drive and directory as the calling process, so a child started without a directory argument holds its parent's working directory in turn. [DOC S-6bobcclf]
- `RemoveDirectory` needs an empty directory and delete access, and "marks a directory for deletion on close": the directory is not removed until the last handle to it is closed. With a POSIX delete the directory goes while handles remain open, and later `CreateDirectory` calls to open it fail with `ERROR_FILE_NOT_FOUND`. [DOC S-t5ahy22o]
- `ERROR_SHARING_VIOLATION` is code 32 (0x20): "The process cannot access the file because it is being used by another process." [DOC S-ttcgrkbl]
- So Windows refuses to remove or rename a directory that is the working directory of a live process, its children included, until that process ends or changes directory; a tool that deletes worktrees on Windows ends or waits out such processes first, or reports them, before it deletes anything. [DER S-qz6kfi4i, S-6bobcclf, S-t5ahy22o: the lock note, cwd inheritance and delete-on-close]
- One run on a Windows 11 host (Python 3.14.7, 2026-10-08): a child process sleeping with `cwd` set to a git worktree directory (started by `subprocess.Popen`), and `os.rename` of that directory to a sibling name raised `PermissionError` with `winerror` 32, `ERROR_SHARING_VIOLATION`; the directory and its tracked files stayed in place. The message text came in the host's display language, so a check matches `winerror` or the exception class, not the text. The run covered a rename of one directory only: not `RemoveDirectory` or a recursive delete, not a directory held by an open file instead of a working directory, not another Windows version. [DER S-qz6kfi4i, S-ttcgrkbl: the lock note and error code 32, read against the recorded run]
- Open: whether `RemoveDirectory` or a recursive delete of a current directory returns the same code, and whether a tree is left partly deleted, is not recorded: the run above covers the rename only. [UNK: see `_gaps.md`]
- On POSIX, `rmdir` of "the root directory or the current working directory of any process" is left open: "it is unspecified whether the function succeeds", or fails with `EBUSY`; the standard's rationale says removing a process's current directory "should be an allowed error". [DOC S-vfd5kpka]
- Linux `rmdir(2)` (man-pages 6.19) gives `EBUSY` for a path "currently used as a mount point or is the root directory of the calling process", which is not another process's working directory; it adds that NFS protocol "infelicities" can make directories that are still in use disappear unexpectedly. [DOC S-hlwenztu]
- Linux `getcwd(3)` fails with `ENOENT` when "the current working directory has been unlinked", the state of a process whose directory another process removed. [DOC S-kyzwo2d6]
- Apple's `rmdir(2)` page (Developer Library Archive) lists `EBUSY` only for "the mount point for a mounted file system" and says nothing about a process's working directory. [DOC S-2cf7ptty]
- One run on macOS 26.5.2 (arm64, Python 3.13.2, 2026-10-13): a child Python process started by `subprocess.Popen` with `cwd` set to an empty directory, then `os.rename` of that directory and `os.rmdir` of the renamed one from the parent both succeeded; the child's `os.getcwd()` then raised `FileNotFoundError` (errno 2) and its `open("newfile.txt", "w")` by relative name raised the same. The run covered an empty directory on the local file system only: not Linux, not another macOS version or file system, not `shutil.rmtree` of a tree, not a directory held open by a file descriptor instead of as a working directory. [DER S-vfd5kpka, S-kyzwo2d6, S-2cf7ptty: the unspecified case and the `ENOENT` state above, read against the recorded run]
- So on Linux and macOS, unlike Windows, a directory that is another process's working directory can be renamed and removed while that process runs (documented as not an `EBUSY` case on Linux, observed once on macOS); the holder is not stopped, and a removal reports no holder; the holder's `getcwd` fails with `ENOENT` (documented for Linux, shown by the one macOS run), while a relative-path open failing with `ENOENT` was shown in the one macOS run only and no Linux page documents it; so a tool that must not strand a process finds holders before it removes a tree, on every system, and not only on Windows. [DER S-qz6kfi4i, S-vfd5kpka, S-hlwenztu, S-kyzwo2d6, S-2cf7ptty: the Windows lock note above, the POSIX, Linux and Apple rmdir pages and `getcwd` `ENOENT`]
- Open: whether a Linux or macOS kernel other than the ones documented or run here ever answers `EBUSY` for a working directory is not stated: POSIX leaves it unspecified and Apple's page is silent; the Linux claim rests on the man page's wording, not on a run. [UNK: see `_gaps.md`]

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

### Splitting text into lines: `str.splitlines` and `bytes.splitlines`
- `str.splitlines()` breaks at these line boundaries, "a superset of universal newlines": `\n`, `\r`, `\r\n`, `\v` (`\x0b`), `\f` (`\x0c`), `\x1c`, `\x1d`, `\x1e`, `\x85` (U+0085, Next Line), `U+2028` (Line Separator) and `U+2029` (Paragraph Separator); `\v` and `\f` were added in 3.2. [DOC S-5qbsemqm]
- Line breaks stay out of the result unless `keepends` is true; unlike `split('\n')`, `splitlines()` returns `[]` for the empty string and a terminal line break adds no empty last element (`"One line\n".splitlines()` is `['One line']`, `'Two lines\n'.split('\n')` is `['Two lines', '']`). [DOC S-5qbsemqm]
- `bytes.splitlines()` and `bytearray.splitlines()` differ from the `str` method in their boundaries: they break "at ASCII line boundaries" by the universal-newlines approach, and the page's example splits `\n`, `\r` and `\r\n` only; it does not list the other characters, and the empty-input and terminal-break rules are the same as for `str`. [DOC S-5qbsemqm]
- In the implementation the `bytes` method uses the shared splitting template with `STRINGLIB_ISLINEBREAK(x)` defined as `x == '\n' || x == '\r'`, and `bytesobject.c` includes that definition file before `stringlib/split.h`, so a `bytes` value splits only at `\n`, `\r` and `\r\n` (a `\r` followed by `\n` is one break); `\x0b`, `\x0c`, `\x1c` to `\x1e` and `\x85` do not split it. [CODE S-7ctlvynr: Objects/stringlib/stringdefs.h#STRINGLIB_ISLINEBREAK; CODE S-inakn5ad: Objects/bytesobject.c#STRINGLIB_MUTABLE, the includes of stringdefs.h and split.h]
- Run on CPython 3.13.2 (not 3.14.7) with the string `'a\x0bb\x0cc\x1cd\x1de\x1ef\x85gU+2028hU+2029i\r\nj'`, `str.splitlines()` returned ten items `a` to `j` (every listed boundary split, `\r\n` once), while the same bytes without the two Unicode separators (they have no Latin-1 byte), encoded as Latin-1, gave `[b'a\x0bb\x0cc\x1cd\x1de\x1ef\x85ghi', b'j']`: only `\r\n` split it. [DER S-5qbsemqm, S-7ctlvynr: the two tables above, checked by the local run]
- So a tool that splits a file's text into records one per line, and must not break a record at a form feed, a `\x85` or a Unicode line separator that its data may hold, splits with `split("\n")` or splits the `bytes` before decoding (that splits only at `\n`, `\r` and `\r\n`); `str.splitlines()` on decoded text splits at all of them. [DER S-5qbsemqm, S-7ctlvynr: the `str` boundary list against the `bytes` one]

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
- `os.link(src, dst)` creates a hard link named *dst* to *src* and is available on Unix and on Windows (since Python 3.2); the `os.link` entry does not say what it raises when the two paths are on different filesystems. [DOC S-5brdhqgo]
- The `os` module's rule for its errors: "All functions in this module raise `OSError` (or subclasses thereof)" for invalid or inaccessible paths and for arguments the operating system does not accept, so `os.link` failing on a pair of paths surfaces as `OSError` or a subclass. [DOC S-5brdhqgo]
- The `errno` module defines `EXDEV` as "Cross-device link"; symbols not used on the current platform are not defined by the module, so `errno.EXDEV` is not guaranteed on every platform. [DOC S-qo63gfo7]
- POSIX `link()` fails with `[EXDEV]` when the file named by `path1` and the directory that is to hold the entry `path2` "are on different file systems and the implementation does not support hard links between file systems". [DOC S-edjp43o7]
- POSIX allows the other case: "Some implementations do allow hard links between file systems", so a cross-filesystem `os.link` that succeeds on one POSIX system can fail with `EXDEV` on another. [DOC S-edjp43o7]
- For `os.copy_file_range` the `os` page states the mapping with a kernel condition: "In Linux kernel older than 5.3, the files pointed to by `src` and `dst` must reside in the same filesystem, otherwise an `OSError` is raised with `errno` set to `errno.EXDEV`"; the function's availability is Linux >= 4.5 with glibc >= 2.27, and the entry does not say what a cross-filesystem copy does on kernel 5.3 or later. [DOC S-5brdhqgo]
- The `os.link` entry has no such sentence. On a POSIX system whose `link()` refuses a cross-filesystem pair, `os.link` raises `OSError` and its `errno` is `errno.EXDEV` (a `link()` failure surfaces as `OSError` under the module's error rule, with the `errno` the C call sets); the `os` page does not name `link()` as the call underneath, so this is derived, not stated. [DER S-5brdhqgo, S-edjp43o7, S-qo63gfo7: the module's error rule, the `link()` error list and the `EXDEV` symbol]
- Win32 `CreateHardLink` has the same limit in its own words: "all hard links to a file must be on the same volume". [DOC S-oqrlzkwe]
- The Win32 overview adds that hard links "can't reference files on different volumes", and its examples forbid linking `C:\dira\ethel.txt` to `D:\dirb\lucy.txt` and to a mapped network drive `Z:`; a hard link also cannot reference a directory, only a file. [DOC S-ip5ugdeb]
- `CreateHardLinkW` "is only supported on the NTFS file system, and only for files, not directories"; on failure it returns zero and the reason is read with `GetLastError`. [DOC S-oqrlzkwe]
- The same page caps a file at 1023 hard links ("If more than 1023 links are created for a file, an error results"), and in Windows 8 and Windows Server 2012 lists ReFS as not supported for this function. [DOC S-oqrlzkwe]
- So a tool that hard-links files from a source tree into a copy puts both on one volume (one drive letter and one NTFS filesystem on Windows; on POSIX one filesystem is the safe choice, since `link()` may refuse a cross-filesystem pair and some implementations allow it), and treats `OSError` from `os.link` as the signal to copy the file instead, whatever the platform's error number. [DER S-5brdhqgo, S-edjp43o7, S-oqrlzkwe, S-ip5ugdeb: the same-volume and NTFS-only rules on Windows, the implementation-dependent cross-filesystem rule of POSIX `link()`, `OSError` as the error type]
- `shutil.copytree(src, dst, copy_function=...)` copies each file with the callable it is given, called with the source and the destination path (default `shutil.copy2`); with `dirs_exist_ok=True` it continues into existing directories and overwrites files there. [DOC S-jwv5eevl]
- So a test that copies a tree it only partly writes can pass `copy_function=os.link` (falling back to a copy where the link fails, such as across filesystems) and replace each file it writes with a fresh copy before writing, since a write through a hard link changes every name of the file. [DER S-5brdhqgo, S-jwv5eevl]
- `shutil.copy2` is `copy` that also attempts to preserve file metadata, through `copystat`, which copies the permission bits, last access time, last modification time and flags; `copy2` never raises because it could not preserve metadata. [DOC S-jwv5eevl]
- So a cache keyed on files' modification times (`st_mtime_ns`) still matches after a `copytree` with the default `copy2`, but not after a plain `shutil.copy`, which leaves them out; a key that must survive a copy at another path hashes the files' content and their paths relative to the root instead. [DER S-jwv5eevl: copy2 keeps the times, copy does not]
- Open: what modification time a fresh `git clone` or `git worktree add` gives the files it checks out is not stated on a git page the kb cites. [UNK: see `_gaps.md`]
- Open: the Windows error number (`winerror` or `errno`) that `os.link` raises when the two paths are on different volumes, or on a filesystem other than NTFS, is not stated on the `os` page or on the Win32 pages, which say only that the function fails and `GetLastError` has the code. [UNK: see `_gaps.md`]

### Console escape sequences (ANSI/VT output on the Windows console)
- The console host intercepts the VT sequences (cursor movement, colour and the rest) written to the output stream only "if the ENABLE_VIRTUAL_TERMINAL_PROCESSING flag is set on the screen buffer handle" with `SetConsoleMode`; the flag is 0x0004, and `WriteFile` and `WriteConsole` are the writes it applies to. [DOC S-qvjkxdub, S-kkrnrh7n]
- `SetConsoleMode` says `ENABLE_PROCESSED_OUTPUT` "should be enabled when using control sequences" and must be set with `ENABLE_VIRTUAL_TERMINAL_PROCESSING`; the mode belongs to one screen buffer, since "setting the output modes of one screen buffer does not affect the output modes of other screen buffers". [DOC S-kkrnrh7n]
- The suggested way to turn the flag on, in the page's own samples, is `GetConsoleMode` on the standard output handle, OR the flag into the mode and `SetConsoleMode` back, failing when either call fails; neither page says the flag is already on in a new console, and its output-mode sentence "both output modes are enabled by default" precedes a table of five output flags. [DOC S-qvjkxdub, S-kkrnrh7n]
- CPython 3.14.7 does not set the flag in the two files read: the Windows console writer in `winconsoleio.c` writes with `WriteConsoleW`, and neither it nor `posixmodule.c` calls `SetConsoleMode`. Its colour check `_colorize.can_colorize` on `win32` returns false unless `nt._supports_virtual_terminal()` is true, and that function only reads the standard error handle's mode and returns whether `ENABLE_VIRTUAL_TERMINAL_PROCESSING` is in it. [CODE S-iv3usyoz: Modules/_io/winconsoleio.c#_io__WindowsConsoleIO_write_impl; S-ctjl4gek: Modules/posixmodule.c#os__supports_virtual_terminal_impl; S-4a5xeg5l: Lib/_colorize.py#can_colorize]
- So `print("\x1b[...")` on Windows reaches the console as characters, and CPython leaves it to the program, or to whatever started the console, to have turned processing on: a tool that prints escape sequences calls `GetConsoleMode`/`SetConsoleMode` itself (through `ctypes`, standard library) or checks the flag first, and writes none when stdout is not a console. What a console host does with a sequence while the flag is off, and which console hosts and Windows versions start with it on, are not stated on the pages read. [DER S-qvjkxdub, S-kkrnrh7n, S-iv3usyoz, S-ctjl4gek, S-4a5xeg5l: flag set by the caller; CPython reads, never sets it]
- Every CSI sequence starts with ESC (0x1B) then `[` (0x5B), which is `"\x1b["` in a Python string. `ESC [ <y> ; <x> H` (CUP, Cursor Position) moves the cursor to row `<y>`, column `<x>` of the viewport; the page's rule for the cursor sequences is that an omitted or 0 parameter "will be treated as a 1", and the cursor stays inside the viewport. [DOC S-qvjkxdub]
- xterm's control-sequence list gives the same default: `CSI Ps ; Ps H` is "Cursor Position [row;column] (default = [1,1])". So `ESC [ H`, with no parameters, puts the cursor at the top left. [DOC S-j6wqryzp]
- `ESC [ <n> J` (ED, Erase in Display) replaces the text of the current viewport with spaces: 0 from the cursor (inclusive) to the end of the display, 1 from the start up to and including the cursor, 2 the whole display; `ESC [ <n> K` (EL) does the same for the cursor's line. The page lists only 0, 1 and 2 and does not say that ED moves the cursor. [DOC S-qvjkxdub]
- xterm lists a fourth ED value, `Ps = 3  -> Erase Saved Lines, xterm`, which the Windows page does not list. [DOC S-j6wqryzp]
- So the sequence that clears the screen and starts a redraw at the top left is `ESC [ H` plus `ESC [ 2 J` (`"\x1b[H\x1b[2J"`), the two together because ED 2 is not documented to move the cursor and CUP does not erase; `ESC [ 2 J` alone erases but leaves the cursor where it was. [DER S-qvjkxdub, S-j6wqryzp: CUP default 1;1, ED 2, no cursor move stated for ED]
- A full-screen program can switch to the alternate screen buffer with `ESC [ ? 1 0 4 9 h`, "so that they can modify the entire contents of the buffer, without affecting the application that started them"; the alternate buffer is the window's size, with no scrollback. [DOC S-qvjkxdub]
- Open: whether the Windows console honours `ESC [ 3 J` (xterm's erase of saved lines) is not stated on the page read; the flag's default per console host and Windows version, and the effect of the sequences with the flag off, are not stated either; no Windows host was available to probe them. [UNK: see `_gaps.md`]

### Bold and red text (SGR) and the NO_COLOR convention
- Text styling is the SGR sequence (Set Graphics Rendition), a CSI sequence ending in `m` whose `<n>` takes 0 to 16 parameters separated by semicolons; with no parameter it is treated as a single 0. The page calls these commands "generally equivalent to calling" `SetConsoleTextAttribute` for all later writes. [DOC S-qvjkxdub]
- The Windows page's value table: 0 "Returns all attributes to the default state prior to modification", 1 Bold/Bright "Applies brightness/intensity flag to foreground color", 22 No bold/bright, 31 Foreground Red ("non-bold/bright red"), 39 Foreground Default (only the foreground part of the defaults), and 91 Bright Foreground Red ("bold/bright red"). [DOC S-qvjkxdub]
- xterm's list gives the same codes: `CSI Pm m` is "Character Attributes (SGR)" with `Ps = 0` Normal, `1` Bold, `22` "Normal (neither bold nor faint)", `31` "Set foreground color to Red" and `39` "Set foreground color to default"; `91` is the aixterm bright red, present only where 16-colour support is compiled. [DOC S-j6wqryzp]
- Parameters of one sequence are applied left to right, and a later competing option wins ("the right-most option taking precedence"); the page's sample prints red with `"\x1b[31m"`, adds bold with `"\x1b[1m"` ("to affect the previous color setting"), resets with `"\x1b[m"` (implicit SGR 0) or `"\x1b[0m"`, and restores only the foreground with `"\x1b[39m"`. [DOC S-qvjkxdub]
- So bold red text is `"\x1b[31;1m"` and the reset after it is `"\x1b[0m"`, or `"\x1b[m"` for the same; a reset that leaves other styling alone uses `22` for bold and `39` for the colour. The Windows page orders red before bold in its sample and does not say what `1;31` gives there, since its 31 is "non-bold/bright", so the sequence that follows the page is red first, then bold. [DER S-qvjkxdub, S-j6wqryzp: SGR 0, 1, 22, 31, 39; left-to-right rule; the Windows sample's order]
- The NO_COLOR page (no-color.org, "Last updated: 2026-10-12") states an informal standard "proposed in 2017": command-line software that "adds ANSI color to its output by default" should check for a `NO_COLOR` environment variable that, "when present and not an empty string (regardless of its value)", prevents the addition of ANSI color. [DOC S-zch3x2zi]
- The page's C sample reads `getenv("NO_COLOR")` and turns colour off only when the result is neither NULL nor an empty string; so `NO_COLOR=1` disables it and `NO_COLOR=` (empty) does not. Software that does not add colour by default "does not need to care about NO_COLOR". [DOC S-zch3x2zi]
- NO_COLOR is "a hint to the software running in the terminal to suppress addition of color", not to the terminal; user-level configuration files and per-instance command-line arguments "should override the NO_COLOR environment variable", so a user can export `NO_COLOR=1` and still enable colour for one program. [DOC S-zch3x2zi]
- NO_COLOR does not turn off other styling: asked whether it should disable bold, underline and italic, the page answers "No", since the standard "only signals the user's intention regarding adding ANSI color". [DOC S-zch3x2zi]
- The convention is published at no-color.org, whose pages link the GitHub repository `jcs/no_color` for pull requests that add software to the list; the page names no standards body, person or organisation as author and states no licence. [DOC S-zch3x2zi]
- CPython 3.14.7 follows it in its own colour check: `_colorize.can_colorize` returns false when `NO_COLOR` is set to a non-empty value, tested after `PYTHON_COLORS` (`0` or `1`, which win, unless `-E` ignores the environment) and before `FORCE_COLOR` (a non-empty value turns colour on), then `TERM=dumb`, the Windows virtual-terminal flag and `os.isatty` of the stream. [CODE S-4a5xeg5l: Lib/_colorize.py#can_colorize]
- So a stdlib-only tool that prints a loud alert line writes the colour only when the stream is a terminal (`isatty`), on Windows only once the virtual-terminal flag is on, and `NO_COLOR` is unset or empty; with `NO_COLOR` set it prints the same text without the colour (bold may stay, by the page's answer), and a plain-text marker such as `ALERT:` carries the alert wherever colour is off. [DER S-zch3x2zi, S-4a5xeg5l, S-qvjkxdub: the NO_COLOR rule, CPython's order of checks, the console flag]
- Open: who maintains no-color.org (a person or organisation) is not stated on the pages read, and neither is its licence; whether the Windows console renders `1;31` (bold before red) as bright red is not stated. [UNK: see `_gaps.md`]

## Reference
| Need | POSIX | Windows | Source |
|---|---|---|---|
| Detach a child | `start_new_session=True` | `creationflags=DETACHED_PROCESS \| CREATE_NEW_PROCESS_GROUP` | S-dabwnzz5 |
| Exclusive lock file | `os.open(p, O_CREAT \| O_EXCL \| O_WRONLY)` | same | S-ew7mucsg |
| Lock directory | `os.mkdir(p)` (`FileExistsError`) | same | S-ew7mucsg |
| Advisory lock | `fcntl.flock` | `msvcrt.locking` | S-oavxfpsn, S-f5bnvamj |
| Is PID alive | `os.kill(pid, 0)` | not `os.kill` (terminates) | S-ew7mucsg |
| Interpreter | `python3` | `python`, `py -3` | S-sjuwcuhk |
| Hard link (`os.link`) | one filesystem is the safe choice; across filesystems `OSError` with `errno.EXDEV` where `link()` refuses (derived), and some implementations allow it | one NTFS volume; `OSError` (error number not stated) | S-edjp43o7, S-oqrlzkwe, S-ip5ugdeb |
| Longest command line | not this limit | 32,767 characters (`CreateProcessW`); 8191 through `cmd.exe` | S-6bobcclf, S-e4zz24dq |

Related: `python/windows-python-install.md` (installing Python and the Store `python3` shortcut); `python/stdlib-sqlite3-csv.md` (csv files open with `newline=''`); `claude/hooks.md` (how Claude Code runs
hook commands on Windows); `gitlab/hosted-runners-windows.md` (a Windows CI job for these tools); `python/interpreter-startup.md`
(what starting a child costs: `CreateProcess()` versus `vfork`/`posix_spawn`, and the start-up options);
`windows/cmd-exe-syntax-quoting-redirection.md` and `windows/cmd-exe-variables-expansion-errorlevel.md` (what `cmd.exe`
does with quoting, `%`/`!` expansion, redirection, errorlevel and the 8191-character limit that `shell=True` runs into).

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
