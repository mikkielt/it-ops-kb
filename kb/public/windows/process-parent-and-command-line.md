---
topic: windows/process-parent-and-command-line
priority: P3
applies_to: "Windows desktop (Win32 Toolhelp, the native NtQueryInformationProcess and the PEB, WMI Win32_Process) for finding a process's parent and a process's command line, as documented on Microsoft Learn (read 2026-10-07)"
retrieved_utc: 2026-10-07
sources: [S-u6fzpqel, S-fvl2zjrg, S-xppzzo3g, S-vav6jyoa, S-kgfngudi, S-rstjssao, S-kgv326f5, S-hgt26zgs]
status: partial
---

# Windows: a process's parent and command line

## Summary
Windows documents three ways to learn a process's parent, and two of them also reach a command line.
The Toolhelp snapshot (`CreateToolhelp32Snapshot` with `TH32CS_SNAPPROCESS`, then `Process32First` and
`Process32Next`) lists every process with its `th32ParentProcessID` and the executable's file name, but no
command line. The native `NtQueryInformationProcess` returns the parent in `PROCESS_BASIC_INFORMATION`; the
command line sits in the target's own memory, behind the PEB and `RTL_USER_PROCESS_PARAMETERS`, so reading it
means opening the target with read rights. WMI's `Win32_Process` class has both `ParentProcessId` and
`CommandLine` as read-only properties. A parent id says nothing about whether that parent is still the process
that created the child, because identifiers are reused. What the Python standard library offers on top
(`os.getppid`, `ctypes`) is not read here; see the gap entry.

## Facts
### Toolhelp snapshot (documented, kernel32)
- `CreateToolhelp32Snapshot(dwFlags, th32ProcessID)` with `TH32CS_SNAPPROCESS` includes all processes in the system; `th32ProcessID` is used only with the heap and module flags and is ignored otherwise. The entries are walked with `Process32First` and `Process32Next`, and the snapshot handle is destroyed with `CloseHandle`. [DOC S-u6fzpqel]
- A `PROCESSENTRY32` entry holds `th32ProcessID`, `th32ParentProcessID` ("the identifier of the process that created this process") and `szExeFile`, the executable's file name (a full path needs `Module32First`, or `QueryFullProcessImageName` from a 32-bit caller for a 64-bit process); `dwSize` must be set to the structure's size before `Process32First` or the call fails; `cntUsage`, `th32DefaultHeapID`, `th32ModuleID` and `dwFlags` are no longer used and read zero. [DOC S-fvl2zjrg]
- `PROCESSENTRY32` has no command-line member, so a Toolhelp snapshot answers "who is my parent and what image is it" but not "with which arguments". [DER S-fvl2zjrg: the member list above]
- When the snapshot names one process for heaps or modules, the call fails with `ERROR_ACCESS_DENIED` for the Idle process and the CSRSS processes and with `ERROR_PARTIAL_COPY` (299) when a 32-bit caller names a 64-bit process; the page states no privilege for a plain `TH32CS_SNAPPROCESS` snapshot. [DOC S-u6fzpqel]
- A snapshot lists the parent id of every process at one moment, so one call is enough to walk from a process through all its ancestors. [DER S-u6fzpqel: "includes all processes in the system"; S-fvl2zjrg: each entry carries `th32ParentProcessID`]

### NtQueryInformationProcess and the PEB (native API)
- `NtQueryInformationProcess` (`winternl.h`, `ntdll.dll`) "may be altered or unavailable in future versions of Windows"; it has no import library, so the page tells callers to use `LoadLibrary` and `GetProcAddress` on `Ntdll.dll`, and to prefer the public functions it names. [DOC S-xppzzo3g]
- With `ProcessBasicInformation` (0) it fills a `PROCESS_BASIC_INFORMATION`: `PebBaseAddress`, `UniqueProcessId` and `InheritedFromUniqueProcessId`, which "contains a unique identifier for the parent process"; the page prefers `GetProcessId` for the process's own id. [DOC S-xppzzo3g]
- The information classes the page lists are `ProcessBasicInformation` (0), `ProcessDebugPort` (7), `ProcessWow64Information` (26), `ProcessImageFileName` (27), `ProcessBreakOnTermination` (29), `ProcessTelemetryIdInformation` (64) and `ProcessSubsystemInformation` (75); none returns a command line. [DOC S-xppzzo3g]
- The documented route to a command line is through the PEB: `PEB.ProcessParameters` points to an `RTL_USER_PROCESS_PARAMETERS` that holds `ImagePathName` and `CommandLine`, both `UNICODE_STRING`; Microsoft marks both structures "may be altered in future versions of Windows" and keeps most PEB fields as `Reserved`. [DOC S-vav6jyoa, S-kgfngudi]
- The PEB and the parameter block live in the target process's memory, so another process's command line is read with `ReadProcessMemory` on a handle that has `PROCESS_VM_READ`; the page of `NtQueryInformationProcess` itself names no access right the handle needs. [DER S-vav6jyoa, S-kgfngudi, S-kgv326f5: `PebBaseAddress` is an address in the target; `PROCESS_VM_READ` is the right "to read memory in a process using ReadProcessMemory"]

### Opening another process (what needs elevation)
- `OpenProcess` checks the requested access against the target's security descriptor, and a caller that has enabled `SeDebugPrivilege` is granted the requested access regardless; Microsoft says opening another local process "with full access rights" needs that privilege. The System and CSRSS processes fail with `ERROR_ACCESS_DENIED`, the Idle process with `ERROR_INVALID_PARAMETER`. [DOC S-rstjssao]
- `PROCESS_QUERY_LIMITED_INFORMATION` (0x1000) is the smaller right that covers `GetExitCodeProcess`, `GetPriorityClass`, `IsProcessInJob` and `QueryFullProcessImageName`, and `PROCESS_QUERY_INFORMATION` (0x0400) grants it automatically; reading memory needs `PROCESS_VM_READ` (0x0010). A protected process refuses `PROCESS_QUERY_INFORMATION` and `PROCESS_VM_READ` from other processes but still allows `PROCESS_QUERY_LIMITED_INFORMATION`. [DOC S-kgv326f5]
- The default security descriptor of a new process takes its ACLs from the primary or impersonation token of its creator, and the handle `CreateProcess` returns has `PROCESS_ALL_ACCESS`. [DOC S-kgv326f5]
- Whether a standard (non-elevated) user can read the command line of its own parent, a process of the same user, through `OpenProcess` plus `ReadProcessMemory` is not stated on these pages. [UNK: the access-rights and `OpenProcess` pages give the rights and the `SeDebugPrivilege` rule, not a worked same-user case; test on the host, elevated and not]

### WMI Win32_Process
- `Win32_Process` (namespace `Root\CIMV2`, Windows Vista and Windows Server 2008 and later) has `ParentProcessId` (`uint32`, read-only, mapped to `InheritedFromUniqueProcessId`) and `CommandLine` (`string`, read-only, "Command line used to start a specific process, if applicable"). [DOC S-hgt26zgs]
- Microsoft warns that process identifiers are reused: the process named by `ParentProcessId` may have ended, or the id may now belong to an unrelated process, and the `CreationDate` property tells whether the named parent was created after the child. [DOC S-hgt26zgs]
- The class page's remarks say the calling process "must have the SE_RESTORE_NAME privilege on the computer in which the registry resides"; it does not say whether a non-elevated user's query returns `CommandLine` for another user's process or for its own. [UNK: the class page has no per-property access note; test on the host]

### How it fits
- A caller that has only the Python standard library reaches these through `ctypes` (`kernel32` for Toolhelp, `ntdll` for the native call) or by starting a PowerShell or other process that queries WMI; the WMI route costs a process start, the `ctypes` routes do not. [DER S-u6fzpqel, S-xppzzo3g, S-hgt26zgs: the three interfaces above; the `ctypes` binding itself is not read, see the gap entry]
- For a hook that needs its ancestors' command lines, the parent chain comes cheaply from one Toolhelp snapshot, and each ancestor's command line from `Win32_Process.CommandLine` (documented) or from the PEB (documented structures, "may be altered"); a parent id whose entry is missing from the snapshot, or whose creation time is later than the child's, is a reused id, which `Win32_Process.CreationDate` can test and `PROCESSENTRY32` cannot. [DER S-fvl2zjrg, S-hgt26zgs, S-vav6jyoa, S-kgfngudi: the member lists above and the reuse warning]
- Python's `os.getppid()` on Windows, the `ctypes.wintypes` names for `PROCESSENTRY32`, and what the Python documentation says about parent-id reuse are not recorded here. [UNK: CPython documentation could not be read in this session; see the gap entry]

## Reference
- Related: `python/stdlib-windows-portability.md` (stdlib on Windows: detached processes, interpreter names), `gitlab/git-trailers-and-hooks.md` (the hooks that need a parent's arguments), `windows/event-forwarding-sysmon.md` (Sysmon event 1 records the parent's command line when a process starts).
- Microsoft pages: `CreateToolhelp32Snapshot`, `PROCESSENTRY32`, `NtQueryInformationProcess`, `PEB`, `RTL_USER_PROCESS_PARAMETERS`, `OpenProcess`, "Process Security and Access Rights" and `Win32_Process` on Microsoft Learn.

## Examples
- A commit hook started by `git commit` on `PL-LT-00123` takes one Toolhelp snapshot, finds its own entry, follows `th32ParentProcessID` upward, and for each ancestor reads the command line to see whether `--amend` and `-F` appear.
