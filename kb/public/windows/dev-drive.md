---
topic: windows/dev-drive
priority: P3
applies_to: "Windows 11 Dev Drive (ReFS developer volume) and Microsoft Defender Antivirus performance mode, as documented on Microsoft Learn (read 2026-09-29)"
retrieved_utc: 2026-09-29
sources: [S-mmdoupim, S-zhrbtrgz, S-rxcgi365, S-wnoqgewy, S-et27ccvn]
status: partial
---

# Dev Drive and Defender performance mode

## Summary
Dev Drive is a Windows 11 storage volume type built on ReFS for developer workloads: source repositories,
package caches, build output and temp folders. A Dev Drive is marked *trusted* when it is formatted, and on a
trusted Dev Drive Microsoft Defender Antivirus runs real-time protection in *performance mode*: files are
opened first and scanned asynchronously ("open now, scan later") instead of scanned while the open waits.
Microsoft presents this as the safer alternative to folder exclusions, which skip scanning altogether. It needs
a second volume (the C: drive cannot be one), local administrator rights, at least 50 GB, and Defender as the
primary antivirus with real-time protection on. In an enterprise, Group Policy must enable Dev Drive first.
Exclusions themselves are in `defender/asr-and-antivirus.md`.

## Facts
### What a Dev Drive is
- Dev Drive is a storage volume type for key developer workloads, built on ReFS, with file-system optimizations and control over trust, antivirus configuration and which file-system filters attach. [DOC S-mmdoupim]
- Microsoft lists as Dev Drive content: source code repositories and project files, package caches, and build output and intermediate files; it recommends against installing applications on a Dev Drive, and says developer tools (Visual Studio, MSBuild, .NET SDK, Windows SDK) belong on C:. [DOC S-mmdoupim]
- Prerequisites: Windows 11 build 10.0.22621.2338 or later, 16 GB memory recommended (8 GB minimum), at least 50 GB free space, local administrator permissions; available on all Windows SKUs. [DOC S-mmdoupim]
- The C: drive cannot be designated a Dev Drive, an existing volume cannot be converted (the designation happens only at format time, and reformatting destroys its content), and removable or hot-pluggable disks, a VHD hosted on one, and dynamic disks are not supported. [DOC S-mmdoupim]
- A Dev Drive can be a disk partition (generally faster, less flexible) or a VHD/VHDX (slightly slower from the virtual disk layer, easier to resize and move; VHDX recommended, dynamically expanding recommended; minimum size 50 GB). [DOC S-mmdoupim]
- From an elevated command line: `Format D: /DevDrv /Q` or `Format-Volume -DriveLetter D -DevDrive`. [DOC S-mmdoupim]
- In business environments, the Dev Drive option is off until an administrator enables it through Group Policy ("Configure Dev Drive security policy"). [DOC S-mmdoupim]
- Since Windows 11 24H2 and Windows Server 2025 a Dev Drive supports ReFS block cloning, which copies a range of file bytes as a metadata operation instead of reading and writing the data, for faster copies and less I/O. [DOC S-mmdoupim]
- Microsoft suggests considering moving `%TEMP%` and `%TMP%` to a Dev Drive, which then also needs the `WinSetupMon` filter for Windows Update. [DOC S-mmdoupim]
- WSL project files see no performance gain from a Dev Drive (WSL runs in its own VHD), and the WSL `metadata` mount option is not supported on ReFS. [DOC S-mmdoupim]

### Trust and filters
- A Dev Drive is marked *trusted* by a registry flag at format time; a Dev Drive moved to another machine is an ordinary volume there until it is trusted again with `fsutil devdrv trust <drive>:` (elevated); `fsutil devdrv query <drive>:` shows the state. [DOC S-mmdoupim]
- Antivirus filters (the `FSFilter Anti-Virus` altitude range 320000-329999), Defender's and third-party ones, attach to a Dev Drive by default; Filter Manager turns every other filter off on a Dev Drive unless it is on the allow list (`fsutil devdrv setfiltersallowed`). [DOC S-mmdoupim]
- `fsutil devdrv enable /disallowAv` detaches antivirus filters from all Dev Drives on the system; Microsoft warns that this removes the drive from standard scans and should be done only with confidence that its files are not exposed to attack. [DOC S-mmdoupim]
- The filter list names `bindFlt` and `wcifs` as needed to run Docker containers out of a Dev Drive; `WdFilter` (Defender) is attached by default. [DOC S-mmdoupim]

### Defender performance mode
- Performance mode is a Microsoft Defender Antivirus capability on Windows 11 that runs only on a trusted Dev Drive, needs real-time protection on, and is on by default when a Dev Drive is created; it does not change real-time protection on the system volume or other NTFS or FAT32 volumes. [DOC S-zhrbtrgz]
- Requirements: Defender Antivirus as the primary antivirus, real-time protection on, antimalware platform 4.18.2303.8 or later, security intelligence 1.385.1455.0 or later. [DOC S-zhrbtrgz]
- In performance mode the scan is deferred until after the file open completes ("open now, scan later", asynchronous); with it off the open waits for the scan ("open now, scan now"). Microsoft says this gives less protection than synchronous scanning but significantly better protection than folder exclusions, which block scans altogether. [DOC S-zhrbtrgz]
- An untrusted Dev Drive runs synchronous real-time protection like any other volume. [DOC S-zhrbtrgz]
- Performance mode is managed with Intune (`./Device/Vendor/MSFT/Defender/Configuration/PerformanceModeStatus`, integer, `0` enable (default), `1` disable), Group Policy (**Configure performance mode status** under Real-time Protection, in the Windows 11 24H2 administrative templates) or `Set-MpPreference -PerformanceModeStatus Enabled`. [DOC S-zhrbtrgz]
- Performance mode does not address high CPU or memory use of the Defender service itself (`MsMpEng.exe`); for that Microsoft points to the performance analyzer and exclusions. [DOC S-zhrbtrgz]
- Performance mode is a Defender feature: with another antivirus product it does not apply, and only the filter allow list can be tuned. [DOC S-mmdoupim]

### How it fits
- For a test suite on Windows that creates many short-lived files (throwaway git repositories, copied trees), a trusted Dev Drive keeps Defender scanning those files while taking the scan off the file-open path, which a folder exclusion does not do (it stops scanning). Pointing the suite's temp root at the Dev Drive needs no exclusion and no Defender setting change beyond the default. [DER S-zhrbtrgz, S-rxcgi365: performance mode versus exclusions; the temp root settings are in `python/pytest.md`]
- How much a Dev Drive shortens a Python and git test run on a given host is not stated by Microsoft (it links a Visual Studio blog for average measurements); it has to be measured on the host. [UNK: Microsoft Learn gives no figures for this workload; see the gap entry]

### Windows containers on a CI runner machine
- Microsoft supports Windows Defender on the machine that runs containers, where it is optimized to protect them, but does not support Windows Defender running inside Windows Server containers; with a third-party antivirus, the vendor's documentation decides. [DOC S-wnoqgewy]
- A container's system volume overlays its image layers through placeholders (the `wcifs.sys` isolation filter); a file the container modifies is copied on write, and new or modified files in the container's scratch location are to be scanned normally by the antivirus outside the container. [DOC S-et27ccvn]
- For a hypervisor-isolated container, the image packages are remote to the utility VM that runs the container and are scanned on the physical machine when the utility VM reads them over SMB loop-back; the redundant-scan optimization Microsoft recommends covers those packages, but needs more work for a running hypervisor-isolated container. [DOC S-et27ccvn]
- Whether real-time protection outside the utility VM scans each file a test writes inside a hypervisor-isolated container's scratch disk is not stated, so a Defender exclusion or Dev Drive on the runner machine may not reach those writes. [UNK: the page describes filter behaviour for image layers and scratch files, not per-file scanning of writes inside a utility VM; measure on the runner machine (`New-MpPerformanceRecording` during a job)]

## Reference
- Related: `defender/asr-and-antivirus.md` (exclusion types, what not to exclude, performance analyzer), `python/pytest.md` (`--basetemp`, `PYTEST_DEBUG_TEMPROOT`), `gitlab/git-test-repositories.md`, `windows/gitlab-runner-windows.md` (CI containers).
- SNIPPET: create and check a Dev Drive from an elevated PowerShell (the volume letter is an example); context: Windows 11 22621.2338+, administrator; checked: syntax [DOC S-mmdoupim: `Format-Volume -DevDrive`, `fsutil devdrv query`; DOC S-zhrbtrgz: `PerformanceModeStatus`]
```powershell
Format-Volume -DriveLetter D -DevDrive
fsutil devdrv query D:
Set-MpPreference -PerformanceModeStatus Enabled
```

## Examples
- A developer workstation `PL-LT-00123` with a 100 GB dynamically expanding VHDX mounted as `D:` holds the repository clone and `D:\tmp`; the test runner sets `PYTEST_DEBUG_TEMPROOT=D:\tmp`, so every `tmp_path` lands on the trusted Dev Drive.
