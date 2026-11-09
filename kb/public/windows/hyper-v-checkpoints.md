---
topic: windows/hyper-v-checkpoints
priority: P3
applies_to: "Hyper-V on Windows 10/11 and Windows Server (Windows Server 2016 to 2025 for the troubleshooting pages); Hyper-V PowerShell module; Microsoft Learn pages updated 2025-05 to 2026-02"
retrieved_utc: 2026-11-09
sources: [S-jm73ioph, S-zaodq75u, S-vmvrdxj2, S-vmamynim, S-ftfjuu42, S-4ukx2dgj, S-3rvh2ao3]
status: partial
---
# Hyper-V checkpoints: standard and production, AVHDX files, deleting and merging

## Summary
A Hyper-V checkpoint (formerly snapshot) freezes a VM's disk state in a read-only parent and sends new writes to an
**.avhdx** differencing disk beside the VM's .vhdx. A **production** checkpoint (the default) uses VSS in the guest or file
system freeze on Linux and keeps no memory state; a **standard** checkpoint saves memory and device state and is not
application consistent. Deleting a checkpoint makes Hyper-V merge the .avhdx into its parent and then delete it; never delete
the .avhdx files by hand. Orphaned .avhdx files, usually left by backup software, are merged by shutting the VM down, or with
`Merge-VHD`, which is an offline operation. Back up before any manual merge and leave room to merge.

## Facts
### Types
- Windows 10 and 11 Hyper-V has two checkpoint types, **Standard** (VM and memory state at the moment of the checkpoint) and **Production** (data-consistent backup using Volume Shadow Copy Service, or File System Freeze on Linux, with no memory state); before Windows 10 only standard checkpoints existed, then called snapshots. [DOC S-jm73ioph]
- A standard checkpoint is not a full backup and can cause data consistency problems for systems that replicate between nodes, with Active Directory the page's example. [DOC S-jm73ioph]
- Production checkpoints are the default; applying one leaves the VM off, and unlike a standard checkpoint the guest's open applications are not restored. [DOC S-jm73ioph]
- `Set-VM -Name <vmname> -CheckpointType` takes `Standard`, `Production` (falls back to a standard checkpoint if the production one fails) or `ProductionOnly` (no checkpoint if the production one fails). [DOC S-jm73ioph]
- The same type can be chosen in Hyper-V Manager under VM **Settings** > **Management** > **Checkpoints**, where **Enable Checkpoints** is on by default. [DOC S-jm73ioph]
- Optional **automatic checkpoints** create a checkpoint when a VM starts and merge it when the VM stops. [DOC S-4ukx2dgj]
- The cmdlets use the term checkpoint with snapshot aliases (`Get-VMSnapshot`, `Remove-VMSnapshot`); `Remove-VMSnapshot` is the cmdlet name for deleting a checkpoint. [DOC S-jm73ioph, S-vmamynim]

### Files and chains
- Checkpoints are stored as .avhdx files in the same location as the VM's .vhdx files; checkpoint configuration and saved state files default to `%systemroot%\ProgramData\Microsoft\Windows\Hyper-V\Snapshots`, and that location can be changed only while the VM has no checkpoints. [DOC S-jm73ioph]
- A differencing disk is a disk created on a parent: changes go to the differencing disk and leave the parent untouched. [DOC S-4ukx2dgj]
- The chain can be read with `Get-VMHardDiskDrive -VMName <VMName> | ForEach-Object { Get-VHD -Path $_.Path | Select-Object Path, ParentPath, VHDType }`. [DOC S-zaodq75u]
- Checkpoints are not supported for pass-through disks, shared VHDX or synthetic Fibre Channel; Learn suggests converting to .vhdx or using the backup vendor's own method. [DOC S-zaodq75u]
- The option to expand a disk is greyed out while an active differencing or child disk exists; Learn says to merge all checkpoints first. [DOC S-zaodq75u]
- With more than 50 checkpoints Learn advises scheduled downtime and merging in sequence from youngest to oldest. [DOC S-zaodq75u]

### Deleting a checkpoint and the merge
- Deleting a checkpoint in Hyper-V Manager (**Delete**, or **Delete Checkpoint Subtree** on the earliest checkpoint to remove it and later ones) or with `Remove-VMCheckpoint -VMName <VM> -Name <checkpoint>` makes Hyper-V merge the .avhdx and .vhdx and then remove the .avhdx file. [DOC S-jm73ioph]
- Learn says not to delete .avhdx files directly. [DOC S-jm73ioph]
- `Remove-VMSnapshot` deletes a checkpoint; `-IncludeAllChildSnapshots` removes the children with it, and examples delete by name wildcard or by creation time older than 90 days. [DOC S-vmamynim]
- When the merge runs: Learn says the differencing disk files typically merge as part of the VM shutdown process, and that after a failed delete a shutdown "triggers an auto-merge, if possible"; automatic checkpoints are merged when the VM stops. [DOC S-vmvrdxj2, S-zaodq75u, S-4ukx2dgj]
- Whether a merge after deleting a checkpoint of a running VM happens live, and how long it takes, is not stated on the pages read. [UNK]
- A merge needs free space, ideally equal to the disk size, on the volume holding the .vhdx, .avhdx, .mrt and .rct files. [DOC S-zaodq75u]
- Delete order for a long chain, from the Learn page on rapid disk growth: back up the whole VM, delete the latest checkpoint at the end of the subtree first so it merges into the previous one, repeat step by step, with the VM turned off for the whole operation. [DOC S-3rvh2ao3]

### Merging manually
- Visible but undeletable checkpoints: **Delete** or the Del key in Hyper-V Manager, then `Get-VMSnapshot -VMName <VMName> | Remove-VMSnapshot`, then shut the VM down and retry, then Hyper-V Manager **Edit Disk** > the .avhdx > **Merge** > **To parent virtual disk**, repeating for a chain. [DOC S-zaodq75u]
- Checkpoints missing from Hyper-V Manager but with .avhdx files in the folder (usually backup software that did not clean up): shut the VM down and inspect the chain; shutdown typically merges the files; otherwise `Merge-VHD -Path <path-to-avhdx> -DestinationPath <parent-vhdx>`, then point the VM at the merged .vhdx if necessary. [DOC S-zaodq75u, S-vmvrdxj2]
- `Merge-VHD` is an offline operation: the virtual hard disk chain must not be attached when it starts; `-Path` is the child that is the source, and `-DestinationPath` the chain member that receives the merge (the cmdlet page says "child"; the troubleshooting page passes the parent .vhdx). [DOC S-ftfjuu42, S-zaodq75u]
- The `Merge-VHD` reference example merges Child4 into Child2 of a five-disk chain; Child4.vhdx and Child3.vhdx are not deleted but are no longer valid virtual hard disk files afterwards. [DOC S-ftfjuu42]
- When the VM cannot be shut down, Learn describes an online merge: back up all differencing disk files, run a `Get-VHDChain` function and fix any chain errors by removing the affected differencing disks, generate `Merge-VHD -Path "<child>" -Destination "<parent>"` lines, run them in order from the first pair, change the VM settings to the merged parent and start the VM, whose successful start shows the merge worked. [DOC S-vmvrdxj2]
- Chain corruption (manual deletion, failed merge, storage or host failure mid-merge): back up all files first, merge differencing disks one by one from child to parent with Hyper-V Manager **Edit Disk**, and if the VM still does not start create a new VM and attach the final merged disk. [DOC S-zaodq75u]
- A missing base or differencing disk is restored from backup, else a new VM takes the remaining healthy .vhdx. [DOC S-zaodq75u]

### Cautions and failure causes
- Failure causes for create, merge or delete: orphaned or stale checkpoints (usually from backup software), broken parent and child relationships, file locks by backup or antivirus processes, too little space, and unsupported disks. [DOC S-zaodq75u]
- Checks before manual work: the VM is not in a saved, creating checkpoint or stopping state, all expected disk files are present, antivirus excludes Hyper-V files, and `NT VIRTUAL MACHINE\Virtual Machines` has the "Log on as a service" right and folder permissions. [DOC S-zaodq75u]
- Error symptoms listed: `0x80070020` is a file lock or sharing violation (find the process with ProcMon or Resource Monitor, restart VSS, Hyper-V or backup services), `0x80070032` or a broken chain means find the merge order or create a new VM, and a VM stuck at "creating checkpoint" points at `SnapshotTask` or `VMDeltaSync`. [DOC S-zaodq75u]
- A VM left with unmerged checkpoints that has run out of space may not start: free space, or attach other storage, merge and export. [DOC S-zaodq75u]
- Back up before merges or deletions on critical VMs, and always before touching a damaged chain. [DOC S-zaodq75u, S-vmvrdxj2]

### How it fits
- For a lab or test VM that must be disposable, a checkpoint is the quick reverse; for a VM that replicates or holds directory data, the standard type's memory-state revert is the risky choice and production or none is the safer one. [DER S-jm73ioph: standard checkpoints can cause consistency problems for replicating systems like Active Directory]
- A script that cleans up checkpoints should call `Remove-VMSnapshot` (so Hyper-V merges) and never remove files, and it should not run `Merge-VHD` against a disk a VM still uses. [DER S-jm73ioph, S-ftfjuu42: files must not be deleted directly; merge needs the chain detached]

## Reference
- Learn: Using checkpoints (`https://learn.microsoft.com/windows-server/virtualization/hyper-v/checkpoints`), AVHDX troubleshooting guidance, merging checkpoints with many differencing disks, `Remove-VMSnapshot`, `Merge-VHD`, Hyper-V features and terminology.
- See `windows/windows-sandbox.md` for the lightweight disposable-VM alternative and `agents/agent-sandboxes.md` for Hyper-V isolated containers.

## Examples
- SNIPPET: list the checkpoints of a VM and delete the ones older than 90 days so Hyper-V merges their differencing disks; context: Hyper-V PowerShell module on the host, VM name is a placeholder; checked: no [DER S-vmamynim: the page's second example]
```powershell
Get-VMSnapshot -VMName PL-SRV-0042 | Where-Object { $_.CreationTime -lt (Get-Date).AddDays(-90) } | Remove-VMSnapshot
```
- SNIPPET: show the parent chain of a VM's disks before merging an orphaned .avhdx; context: Hyper-V host, VM shut down first; checked: no [DER S-zaodq75u: the page's chain command]
```powershell
Get-VMHardDiskDrive -VMName PL-SRV-0042 | ForEach-Object { Get-VHD -Path $_.Path | Select-Object Path, ParentPath, VHDType }
```
