---
topic: windows/robocopy
priority: P3
applies_to: "Robocopy (robocopy.exe) in Windows and Windows Server: copy, mirror, retry, logging, ACL, timestamp and attribute options, exit codes and multithreaded copy, with xcopy for comparison, as documented on Microsoft Learn (Windows Commands reference, robocopy page ms.date 03/17/2025, xcopy page ms.date 05/28/2024; read 2026-10-15)"
retrieved_utc: 2026-10-15
sources: [S-3lm4tsvh, S-w4neuhkd, S-7varc2ty]
status: partial
---

# Robocopy: copy and mirror options, retry and logging, ACLs, exit codes and multithreaded copy

## Summary
`robocopy <source> <destination> [<file>...] [<options>]` copies directory trees. Its defaults are a copy of
data, attributes and timestamps (`/COPY:DAT`), every file (`*.*`), a million retries thirty seconds apart and,
with `/MT`, eight threads. Directories are only walked recursively with `/S` or `/E`. `/MIR` is `/E` plus
`/PURGE`, so it deletes what the destination holds beyond the source. The listed exit codes read as sums of
bit flags (1 copied, 2 extra files, 4 mismatches, 8 failures), which is why success is `< 8`, not `0`. `xcopy`
is the older command with a different option set, different defaults for hidden files and read-only flags, and
an exit code in which 1 means "nothing to copy". The Learn page does not state the long-path limit, exit values
above 8 or what `/MIR` does with files that `/XF` and `/XD` exclude; they are listed as open items.

## Facts
### What it copies by default
- The syntax is `robocopy <source> <destination> [<file>[ ...]] [<options>]`; the options come in groups on the page: copy, file selection, copy-file throttling, retry, logging and job options. [DOC S-3lm4tsvh]
- Without a `<file>` parameter robocopy uses `*.*`; wildcards `*` and `?` are supported. [DOC S-3lm4tsvh]
- If data is copied from the root of a device, the destination directory takes on the hidden and system attributes during the copy. [DOC S-3lm4tsvh]
- `/L` only lists: files are not copied, deleted or time-stamped. `/QUIT` stops after processing the command line, to view the parameters. [DOC S-3lm4tsvh]
- `/S` copies subdirectories and leaves empty directories out; `/E` copies subdirectories including empty ones; `/LEV:<n>` copies only the top n levels of the source tree. [DOC S-3lm4tsvh]
- `/Z` copies in restartable mode (an interrupted file is resumed, not recopied); `/B` copies in backup mode, in which robocopy overrides file and folder permissions (ACLs) that might block access; `/ZB` is restartable mode and falls back to backup mode if access is denied. [DOC S-3lm4tsvh]
- `/J` copies with unbuffered I/O and is recommended for large files; `/COMPRESS` requests network compression "if applicable"; `/NOOFFLOAD` copies without the Windows Copy Offload mechanism; `/NOCLONE` does not attempt block cloning. [DOC S-3lm4tsvh]
- `/SPARSE:<y|n>` enables or disables retaining a file's sparse state; with no value it is yes. [DOC S-3lm4tsvh]
- `/CREATE` creates the directory tree and zero-length files only; `/FAT` creates destination names as 8.3 FAT names only; `/256` turns off support for paths longer than 256 characters. [DOC S-3lm4tsvh]
- `/MOV` moves files and deletes them from the source after copying; `/MOVE` does the same for files and directories. [DOC S-3lm4tsvh]
- `/SJ` copies junctions as junctions instead of their targets, `/SL` copies symbolic links as links instead of following them; `/XJ`, `/XJD` and `/XJF` exclude junction points (all, for directories, for files), which are included by default. [DOC S-3lm4tsvh]
- `/MON:<n>` re-runs when more than n changes are seen in the source and `/MOT:<m>` re-runs in m minutes if changes are seen; `/RH:hhmm-hhmm` gives the hours in which new copies may start and `/PF` checks that per file, not per pass. `/IPG:<n>` sets an inter-packet gap to free bandwidth on slow lines. [DOC S-3lm4tsvh]

### Mirror and purge
- `/PURGE` deletes destination files and directories that no longer exist in the source. [DOC S-3lm4tsvh]
- `/MIR` mirrors a directory tree and is documented as equivalent to `/E` plus `/PURGE`. [DOC S-3lm4tsvh]
- The page says `/PURGE` used with `/E` and a destination directory lets the destination directory's security settings stay unchanged, while `/MIR` used with `/E` and a destination directory overwrites them. [DOC S-3lm4tsvh]
- `/XX` excludes "extra" files and directories (in the destination, not the source) and does not delete anything from the destination; `/XL` excludes "lonely" files (in the source, not the destination), so no new files are added. [DOC S-3lm4tsvh]
- `/NOCOPY` copies no file information and is described as useful with `/PURGE`. [DOC S-3lm4tsvh]
- On the root of a volume, `/PURGE` and `/MIR` formerly acted on `System Volume Information` too; robocopy now skips files or directories of that name in the top-level source and destination directories of the session. [DOC S-3lm4tsvh]
- The page's mirror example (its source path shown here with a placeholder user) is `robocopy C:\Users\jan.kowalski\Records D:\Backup /MIR /R:2 /W:5 /LOG:C:\Logs\Backup.log`, described as deleting destination files that are not in the source. It recommends a log file for every run so the result can be checked afterwards. [DOC S-3lm4tsvh]

### Which files are selected
- `/XO` excludes source files older than the destination copy, `/XN` excludes source files newer than it, and `/XC` excludes existing files with the same timestamp but a different size. `/XC /XN /XO` together skip every file that already exists in the destination. [DOC S-3lm4tsvh]
- `/IS` includes "same" files (identical name, size, times and all attributes), `/IT` includes "tweaked" files (same name, size and times, different attributes), `/IM` includes modified files (differing change times). [DOC S-3lm4tsvh]
- The modified-files class applies only when both file systems support change timestamps (such as NTFS) and the files differ in change time but are otherwise the same; such files are not copied by default, `/IM` includes them. [DOC S-3lm4tsvh]
- `/XF` and `/XD` exclude files and directories by name or path (wildcards allowed for files); `/MAX:<n>` and `/MIN:<n>` exclude files bigger or smaller than n bytes; `/MAXAGE:<n>` and `/MINAGE:<n>` exclude files older or newer than n days or a date, by last-modified time; `/MAXLAD` and `/MINLAD` do the same by last access date, where a value below 1900 is days and otherwise a date `YYYYMMDD`. [DOC S-3lm4tsvh]
- `/A` copies only files with the Archive attribute set; `/M` does the same and resets the Archive attribute. `/IA:` includes and `/XA:` excludes files by any of the attributes `RASHCNETO`. [DOC S-3lm4tsvh]
- `/FFT` assumes FAT file times with two-second precision and `/DST` compensates for one-hour DST differences. [DOC S-3lm4tsvh]

### ACLs, timestamps and attributes
- `/COPY:<flags>` picks what is copied for files: `D` data, `A` attributes, `T` timestamps, `X` skip alternate data streams, `S` NTFS ACL, `O` owner, `U` auditing information. The default is `DAT`. The `X` flag is ignored with `/B` or `/ZB`. [DOC S-3lm4tsvh]
- `/SEC` is equivalent to `/COPY:DATS`; `/COPYALL` is equivalent to `/COPY:DATSOU`. [DOC S-3lm4tsvh]
- `/DCOPY:<flags>` picks what is copied for directories: `D`, `A`, `T`, `E` (extended attributes) and `X`. The default is `DA`; the `/NODCOPY` row reads "Copies no directory info (the default /dcopy:DA is done)", which contradicts itself; the page does not say which half holds. [DOC S-3lm4tsvh]
- `/DCOPY:E` tries to copy extended attributes of directories and carries on if they cannot be copied; it is not part of `/COPYALL`. [DOC S-3lm4tsvh]
- `/SECFIX` fixes file security on all files, even skipped ones, and `/TIMFIX` fixes file times on all files, even skipped ones. `/SECFIX` must be combined with one of `/COPYALL`, `/COPY:O`, `/COPY:S`, `/COPY:U` or `/SEC`, which name the kind of security information. [DOC S-3lm4tsvh]
- `/A+:[RASHCNET]` adds and `/A-:[RASHCNETO]` removes attributes on the copied files; the letters are Read-only, Archive, System, Hidden, Compressed, Not content indexed, Encrypted, Temporary (and Offline for removal). [DOC S-3lm4tsvh]
- `/EFSRAW` copies encrypted files in EFS RAW mode and cannot be combined with `/MT` or `/IPG`. [DOC S-3lm4tsvh]

### Retry and wait
- `/R:<n>` is the number of retries on a failed copy; the default is 1,000,000. `/W:<n>` is the wait between retries in seconds; the default is 30. [DOC S-3lm4tsvh]
- `/REG` saves the `/R` and `/W` values as the defaults in the registry. `/TBD` waits for share names to be defined (retry on error 67). [DOC S-3lm4tsvh]
- `/LFSM` (low free space mode) pauses a copy whenever it would take the destination volume's free space below a floor; the floor is 10% of the volume unless `/LFSM:<n>[KMG]` names one. The mode is incompatible with `/MT` and `/EFSRAW`. [DOC S-3lm4tsvh]
- `/IOMAXSIZE`, `/IORATE` and `/THRESHOLD` (each `<n>[KMG]`) turn on throttling; the smallest throttled bandwidth is 524288 bytes per second even if a lower value is given, and files under the threshold are not throttled. [DOC S-3lm4tsvh]

### Logging
- `/LOG:<file>` writes the status output to a log file and overwrites an existing one; `/LOG+:<file>` appends. `/UNILOG:<file>` and `/UNILOG+:<file>` write Unicode text, overwriting or appending. [DOC S-3lm4tsvh]
- `/TEE` writes the output to the console and the log file. `/NJH` and `/NJS` leave out the job header and the job summary; `/NP` leaves out the progress; `/NFL` and `/NDL` leave out file names and directory names; `/NS` and `/NC` leave out sizes and classes. [DOC S-3lm4tsvh]
- `/V` gives verbose output with skipped files; `/X` reports all extra files, not just selected ones; `/TS` and `/FP` add source timestamps and full paths; `/BYTES` prints sizes in bytes; `/ETA` shows the estimated time of arrival of copied files. [DOC S-3lm4tsvh]
- `/SAVE:<jobname>` writes the parameters to a job file and `/JOB:<jobname>` reads them back; all copy, retry and logging options must come before `/SAVE`. `/NOSD` and `/NODD` mean no source or no destination directory is given. [DOC S-3lm4tsvh]

### Multithreaded copy
- `/MT:<n>` copies with n threads; n is an integer from 1 to 128 and the default is 8. The page advises redirecting output with `/LOG` for better performance. [DOC S-3lm4tsvh]
- `/MT` cannot be used with `/IPG` or `/EFSRAW`, and `/LFSM` is incompatible with it. `/MT` was introduced in Windows Server 2008 R2 and applies to current Windows Server versions. [DOC S-3lm4tsvh]
- The page's multithreaded example (placeholder user) is `robocopy C:\Users\jan.kowalski\Records D:\Backup /S /E /COPY:DAT /MT:16 /LOG:C:\Logs\Backup.log`. [DOC S-3lm4tsvh]

### Exit codes
- The page lists: 0 nothing copied, no failure, no mismatch (files already in the destination); 1 all files copied; 2 extra files in the destination, nothing copied; 3 some files copied, extra files present, no failure; 5 some copied, some mismatched, no failure; 6 extra and mismatched files, nothing copied; 7 files copied, a mismatch and extra files; 8 several files did not copy. [DOC S-3lm4tsvh]
- Any value equal to or greater than 8 indicates at least one failure during the copy. [DOC S-3lm4tsvh]
- The listed values fit one set of bit flags: 1 = at least one file copied, 2 = extra files in the destination, 4 = mismatches, 8 = failures; the page itself does not list 4 or any value above 8 and gives no table of flags. [DER S-3lm4tsvh: the table rows 0, 1, 2, 3, 5, 6, 7 and 8 are exactly the sums of those flags that the descriptions imply]
- `if errorlevel <n>` is true when the exit code is `n` or greater, so `if errorlevel 8` detects a failure and `if not errorlevel 8` is the "success or only benign differences" test. [DER S-7varc2ty, S-3lm4tsvh: the `if errorlevel` rule and the "8 or greater" note]

### Differences from xcopy
- `xcopy` takes `/s` and `/e` for subdirectories and adds `/d`, `/u`, `/i`, `/y`, `/exclude`; its syntax line has no mirror or purge, no retry, no log file and no thread-count option. [DOC S-w4neuhkd]
- By default `xcopy` does not copy hidden or system files (`/h` includes them), removes the read-only attribute on the destination (`/k` keeps it) and creates destination files with the archive attribute set whether or not the source had it. [DOC S-w4neuhkd]
- `xcopy /o` copies ownership and DACL information and `/x` copies audit settings and SACL information (implies `/o`); robocopy does the same with `/COPY` flags `S`, `O` and `U`. [DOC S-w4neuhkd, S-3lm4tsvh]
- `/b` means "copy the symbolic link instead of the files" in `xcopy` (since Windows Vista) but backup mode in robocopy; `/z` is restartable mode in both. [DOC S-w4neuhkd, S-3lm4tsvh]
- `xcopy` exit codes are 0 files copied without error, 1 no files found to copy, 2 CTRL+C, 4 initialization error (memory, disk space, invalid drive or syntax), 5 disk write error. Exit code 1 is therefore "nothing to copy" for `xcopy` and "all files copied" for robocopy. [DOC S-w4neuhkd, S-3lm4tsvh]
- The `xcopy` page says an "insufficient memory" error may occur when the path of a file or folder is longer than 255 characters; robocopy's page names a `/256` switch that turns off support for paths longer than 256 characters. [DOC S-w4neuhkd, S-3lm4tsvh]
- `xcopy` and robocopy both have `/compress`, `/noclone` and a sparse-file switch, and both have `/j` for unbuffered copying. [DOC S-w4neuhkd, S-3lm4tsvh]

### How it fits
- A pipeline step or script that runs robocopy must not treat every non-zero exit code as a failure: 1, 2, 3, 5, 6 and 7 are copies or differences, only 8 and above are failures. The check is `if errorlevel 8` in a batch file or `exit code >= 8` in a runner. [DER S-3lm4tsvh, S-7varc2ty: exit-code table and the errorlevel comparison]
- `/MIR` and `/PURGE` delete in the destination, so an agent that proposes or runs one treats it as a destructive step: a `/L` run first lists the planned work without copying or deleting, and the live run names `/LOG` so the result can be read afterwards. [DER S-3lm4tsvh: `/PURGE` deletes, `/L` lists only, the page recommends a log]
- A copy that must keep ACLs says so: the default `/COPY:DAT` leaves out the NTFS ACL, owner and audit information, so `/SEC` or `/COPYALL` (and `/DCOPY:DAT` for directory timestamps) are needed. [DER S-3lm4tsvh: the `/COPY` default and the flag meanings; the page does not state what ACL a copied file then gets]
- `/MT` together with `/LOG` is the page's own pairing for a faster copy, and the page's default of 8 threads is the value for `/MT` given without a number. [DER S-3lm4tsvh: the `/MT` row, its default and its advice about `/LOG`]

### Open
- The maximum path length robocopy handles is not stated: the page names only the `/256` switch that turns off support for paths longer than 256 characters. [UNK: see `_gaps.md`]
- The page's exit-code table has no 4 and no value above 8, and does not describe the bit flags or a fatal-error code. [UNK: see `_gaps.md`]
- Whether files that `/XF` or `/XD` exclude are protected from `/MIR` and `/PURGE` in the destination is not stated. [UNK: see `_gaps.md`]
- What ACL a file gets in the destination when `S` is not in `/COPY` is not described on the page. [UNK: see `_gaps.md`]

## Reference
- Related: `windows/cmd-exe-variables-expansion-errorlevel.md` (`if errorlevel`, exit codes in batch files), `windows/cmd-exe-syntax-quoting-redirection.md` (quoting of paths with spaces, the 8191-character command line).
- Microsoft pages: "robocopy" and "xcopy" under Windows Commands on Microsoft Learn.

## Examples
- Mirror a share to a backup volume, two retries five seconds apart, with a log (dry run first with `/L`): `robocopy \\PL-SRV-0042\Records D:\Backup /MIR /R:2 /W:5 /LOG:C:\Logs\Backup.log`.
- Copy the tree with data, attributes, timestamps and 16 threads: `robocopy C:\Users\jan.kowalski\Records D:\Backup /S /E /COPY:DAT /MT:16 /LOG:C:\Logs\Backup.log`.
- Treat only failures as errors in a batch file: `robocopy C:\Src D:\Dst /E /LOG+:C:\Logs\copy.log` followed by `if errorlevel 8 exit /b 1`.
