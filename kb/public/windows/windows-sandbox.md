---
topic: windows/windows-sandbox
priority: P3
applies_to: "Windows Sandbox on Windows 10 1903+ and Windows 11 (Pro, Enterprise, Education); .wsb configuration files; Policy CSP WindowsSandbox and WindowsSandbox.admx (Learn pages read 2026-09-28)"
retrieved_utc: 2026-09-28
sources: [S-woxmpwse, S-yexfxr4v, S-hlmmxoye, S-bgz3uymb]
status: complete
---
# Windows Sandbox: .wsb configuration and the WindowsSandbox policies

## Summary
Windows Sandbox (WSB) is a disposable, hypervisor-isolated Windows desktop included in Pro, Enterprise and Education.
A user shapes one sandbox with an XML `.wsb` file (vGPU, networking, mapped folders, logon command, audio and video
input, protected client, printer and clipboard redirection, memory in MB). An administrator caps what any sandbox may
do with the device-scoped Policy CSP `./Device/Vendor/MSFT/Policy/Config/WindowsSandbox/*` (Intune) or the matching
`WindowsSandbox.admx` settings under `HKLM\SOFTWARE\Policies\Microsoft\Windows\Sandbox` (Group Policy). Memory has no
policy: only the `.wsb` file's `<MemoryInMB>` sets it.

## Facts

### What it is and where it runs
- Windows Sandbox is a disposable VM isolated from the host by hypervisor-based virtualization with its own kernel; closing it deletes all software, files and state, each launch is a fresh instance, and host-installed software is not available inside it. [DOC S-woxmpwse]
- Since Windows 11 22H2, data persists through restarts initiated inside the sandbox; only one instance can run at a time. [DOC S-woxmpwse]
- Supported editions: Windows Pro, Enterprise, Pro Education/SE and Education (entitlement through Pro/Pro Education/SE, Enterprise E3/E5, Education A3/A5); Home is not supported. [DOC S-woxmpwse]
- Prerequisites: AMD64, or Arm64 on Windows 11 22H2 and later; virtualization enabled in firmware (nested virtualization in a VM); at least 4 GB RAM (8 GB recommended), 1 GB free disk (SSD recommended) and two CPU cores (four with hyper-threading recommended); Windows 10 1903 or later, or Windows 11. [DOC S-yexfxr4v]
- The optional feature name is `Containers-DisposableClientVM`, enabled from an elevated PowerShell with `Enable-WindowsOptionalFeature -FeatureName "Containers-DisposableClientVM" -All -Online`. [DOC S-yexfxr4v]
- Since Windows 11 24H2, inbox Store apps such as Calculator, Photos, Notepad and Terminal are not available inside the sandbox. [DOC S-yexfxr4v]

### Defaults of a sandbox started without a .wsb file
- A sandbox launched with default settings has a maximum of 4 GB memory, vGPU on (non-Arm64 devices), networking on through the Hyper-V default switch, audio input on, video input off, protected client off, printer redirection off and clipboard redirection on. [DOC S-hlmmxoye]
- Networking on by default can expose untrusted applications to the internal network; a custom `.wsb` file launches the sandbox with networking off. [DOC S-hlmmxoye, S-woxmpwse]

### The .wsb configuration file
- A `.wsb` file is XML with a `<Configuration>` root, supported on Windows 10 build 18342 or later and Windows 11; opening the file (double-click, or its name on a command line) starts the sandbox with its settings. The sandbox window size cannot be configured. [DOC S-hlmmxoye]
- `<vGPU>`, `<Networking>`, `<AudioInput>`, `<VideoInput>`, `<ProtectedClient>`, `<PrinterRedirection>` and `<ClipboardRedirection>` each take `Enable`, `Disable` or `Default`; `Default` means on for vGPU, networking, audio input and clipboard, and off for video input, protected client and printer redirection. [DOC S-hlmmxoye]
- `<MemoryInMB>` sets the memory the sandbox can use in megabytes; a value too small to boot is raised automatically to the 2048 MB minimum. [DOC S-hlmmxoye]
- With vGPU disabled the sandbox uses software rendering (WARP); Microsoft notes that enabling vGPU can increase the sandbox's attack surface. [DOC S-hlmmxoye]
- `<MappedFolders>` holds `<MappedFolder>` entries of `<HostFolder>` (must exist on the host or the sandbox fails to start), `<SandboxFolder>` (created if missing; default the desktop of `WDAGUtilityAccount`) and `<ReadOnly>` (`true`/`false`, default `false`); relative sandbox paths are not supported, environment variables work in paths since Windows 11 23H2, and folders are mapped before the logon command runs. [DOC S-hlmmxoye]
- Changes made in a writable mapped folder persist after the sandbox is closed, and files mapped from the host can be compromised by apps inside the sandbox. [DOC S-hlmmxoye]
- `<LogonCommand><Command>` runs one command after sign-in, as the container user; multi-step work belongs in a script mapped in through a shared folder. [DOC S-hlmmxoye]
- `<ProtectedClient>Enable</ProtectedClient>` runs the sandbox inside AppContainer Isolation; it may restrict copying files in and out. [DOC S-hlmmxoye]

### Policy CSP WindowsSandbox and Group Policy
- The WindowsSandbox Policy CSP is device-scoped only (Pro, Enterprise, Education, IoT Enterprise), at `./Device/Vendor/MSFT/Policy/Config/WindowsSandbox/<setting>`; each setting is an `int` (`0` not allowed, `1` allowed, default `1`) that maps to a Group Policy under Computer Configuration > Windows Components > Windows Sandbox, registry key `SOFTWARE\Policies\Microsoft\Windows\Sandbox`, ADMX file `WindowsSandbox.admx`. [DOC S-bgz3uymb]
- `AllowVGPU`, `AllowNetworking`, `AllowAudioInput`, `AllowVideoInput`, `AllowPrinterRedirection` and `AllowClipboardRedirection` apply from Windows 10 2004 (build 19041.4950) and Windows 11 21H2; `AllowMappedFolders` and `AllowWriteToMappedFolders` apply from Windows 11 24H2 (build 26100). The registry value name equals the setting name (e.g. `AllowClipboardRedirection`, `AllowVGPU`). [DOC S-bgz3uymb]
- A change to `AllowVGPU`, `AllowNetworking`, `AllowAudioInput`, `AllowVideoInput`, `AllowPrinterRedirection` or `AllowClipboardRedirection` takes effect only after Windows Sandbox is restarted. [DOC S-bgz3uymb]
- Not configured, vGPU, networking, audio input, clipboard sharing and mapped folders are enabled, while video input and printer redirection are described as disabled, although the page lists `Default Value` 1 for both (see `_conflicts.md`). [DOC S-bgz3uymb]
- `AllowWriteToMappedFolders` depends on `AllowMappedFolders` being `1`: with mapped folders allowed and write disabled, the sandbox can only read mapped files. [DOC S-bgz3uymb]
- No WindowsSandbox policy sets memory: the CSP has no memory setting, so a memory limit is set per sandbox by `<MemoryInMB>` in the `.wsb` file and cannot be enforced through Intune or Group Policy. [DER S-bgz3uymb, S-hlmmxoye: the CSP's full setting list and the .wsb memory element]
- In Intune the settings are delivered through the Policy CSP (e.g. a custom OMA-URI on `./Device/Vendor/MSFT/Policy/Config/WindowsSandbox/AllowVGPU` and the others); a policy set to `0` disables that capability even where a `.wsb` file asks for it. [DER S-bgz3uymb, S-hlmmxoye: policy disables the capability, and the .wsb element only chooses within it]

## Reference

| .wsb element | Policy CSP / GPO value | Default (unconfigured) | Applies from |
|---|---|---|---|
| `<vGPU>` | `AllowVGPU` | on | Win10 2004 / Win11 21H2 |
| `<Networking>` | `AllowNetworking` | on | Win10 2004 / Win11 21H2 |
| `<AudioInput>` | `AllowAudioInput` | on | Win10 2004 / Win11 21H2 |
| `<VideoInput>` | `AllowVideoInput` | off | Win10 2004 / Win11 21H2 |
| `<PrinterRedirection>` | `AllowPrinterRedirection` | off | Win10 2004 / Win11 21H2 |
| `<ClipboardRedirection>` | `AllowClipboardRedirection` | on | Win10 2004 / Win11 21H2 |
| `<MappedFolders>` | `AllowMappedFolders` | on | Win11 24H2 |
| `<ReadOnly>` | `AllowWriteToMappedFolders` | on | Win11 24H2 |
| `<MemoryInMB>` | (none) | 4 GB maximum | .wsb only |
| `<ProtectedClient>`, `<LogonCommand>` | (none) | off / none | .wsb only |

Registry key for every policy value: `HKLM\SOFTWARE\Policies\Microsoft\Windows\Sandbox` (`WindowsSandbox.admx`).

Related: `windows/app-control.md` (App Control for Business, another application-security layer on the same devices).

## Examples

- SNIPPET: a sandbox for opening an untrusted download: no network, no vGPU, no clipboard, 4 GB memory, the host's downloads folder mapped read-only; context: Windows 10 build 18342+ or Windows 11, host path is a placeholder; checked: no [DER S-hlmmxoye: elements and values from the configuration options section]

```xml
<Configuration>
  <vGPU>Disable</vGPU>
  <Networking>Disable</Networking>
  <ClipboardRedirection>Disable</ClipboardRedirection>
  <MemoryInMB>4096</MemoryInMB>
  <MappedFolders>
    <MappedFolder>
      <HostFolder>C:\Users\jan.kowalski\Downloads</HostFolder>
      <SandboxFolder>C:\Temp\Downloads</SandboxFolder>
      <ReadOnly>true</ReadOnly>
    </MappedFolder>
  </MappedFolders>
</Configuration>
```
