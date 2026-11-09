---
topic: ansible/dsc3-module
priority: P3
applies_to: "ansible.windows collection 3.9.2 (dsc3 added in 3.4.0)"
retrieved_utc: 2026-11-09
sources: [S-qzrsiuyi, S-k3hrxazj, S-mt2qr2is, S-g5j4nkll, S-zxebbjve, S-vpn3gco3]
status: complete
---

# ansible.windows.dsc3 vs ansible.windows.win_dsc

## Summary
The DSC v3 module exists: its name is `ansible.windows.dsc3` (not `microsoft.dsc`), new in ansible.windows 3.4.0; current collection
3.9.2. It runs `dsc config set` with a whole configuration document; in check mode it runs
`dsc config set --what-if`. `win_dsc` is the
PowerShell DSC (v1/v2, PS 5.x) single-resource module; it does not run on PowerShell 7 and points users to `dsc3`.

## Facts
- `win_dsc` declares check-mode support: it always runs the resource's `Test` method and calls `Set` only when not in check mode, reporting `changed` when the resource is not in the desired state. [CODE S-g5j4nkll: plugins/modules/win_dsc.ps1#L480-L500]
- ansible.windows 3.9.2 lists two DSC modules: `dsc3` ("Sets or checks DSC v3 configuration state") and `win_dsc` ("Invokes a PowerShell DSC configuration"). [DOC S-qzrsiuyi]
- `dsc3` was added in ansible.windows 3.4.0; FQCN `ansible.windows.dsc3`. [DOC S-zxebbjve]
- `dsc3` calls `dsc config set` with `config` or `config_file` as the configuration document and is tested against Microsoft DSC 3.3; by default `dsc` must be discoverable through PATH, which dsc also uses to discover resources, and `executable` runs a specific `dsc.exe` while `resource_path` controls where resources are discovered. [DOC S-zxebbjve]
- Options: `config` (dict) or `config_file` (path; one of the two required), `parameters` (dict, maps to `--parameters`), `parameters_file`, `remote_config_file` (bool, default false), `trace_level` (error/warn/info/debug/trace, default warn), and, added in ansible.windows 3.9.0, `chdir`, `executable`, `ignore_settings_file` (needs DSC 3.3.0 or later), `resource_path` and `system_root`. [DOC S-zxebbjve]
- If `$schema` is omitted, the module sets `https://aka.ms/dsc/schemas/v3/bundled/config/document.json`. [DOC S-zxebbjve]
- A local `config_file` (remote_config_file=false) is copied to the target and removed afterwards; it cannot be used with async tasks. [DOC S-zxebbjve]
- Returns `rc` (dsc exit code), `result` (dsc output object), `metadata` (a deprecated copy of `result.executionInformation` since DSC 3.2.0), `results` (per resource), `stderr` and `stderr_lines`, and, added in 3.9.0, `execution_type` (`actual` or `whatIf`), `reboot_required`, `restart_requirements` and `security_context`; `msg` holds the exit code and last dsc error on failure. [DOC S-zxebbjve]
- In check mode `dsc3` runs `dsc config set --what-if` (needs DSC 3.1.0 or later): resources without native what-if support are simulated from their test operation, while group resources such as `Microsoft.DSC/Group` and `Microsoft.DSC/Include` and resources that declare `implementsPretest` fail the task with exit code 2. [DOC S-zxebbjve]
- The development code after 3.8.0 (commit 5814722a681f, notes mention 3.9.0 additions) already runs `dsc config set --what-if` in check mode, not `dsc config test`. [CODE S-mt2qr2is: plugins/modules/dsc3.ps1#L324-L326; CODE S-k3hrxazj: plugins/modules/dsc3.py#L119-L123]
- In that code the module invokes `dsc.exe --trace-format=plaintext --progress-format=none --trace-level=<level> [--ignore-settings-file] config [--parameters=<json>] [--parameters-file=<path>] [--system-root=<path>] set --file=<path or -> --output-format=json [--what-if]`, passing an inline document on stdin. [CODE S-mt2qr2is: plugins/modules/dsc3.ps1#L291-L326]
- In that code, non-zero dsc exit codes are named in the failure message: 1 invalid arguments, 2 DSC error, 3 JSON error, 4 invalid input, 5 validation failed, 6 interrupted, 7 resource not found, 8 assertion failed, 9 server failed, 10 bicep failed. [CODE S-mt2qr2is: plugins/modules/dsc3.ps1#L40-L52]
- In that code `changed` is true when any resource result (recursing into group resources) has non-empty `changedProperties`; diff mode lists each resource and, for changed ones, only the changed properties. [CODE S-mt2qr2is: plugins/modules/dsc3.ps1#L197-L253]
- That code defaults `remote_config_file` to false and adds options `chdir`, `executable`, `ignore_settings_file`, `parameters_file`, `resource_path`, `system_root` and returns `reboot_required`, `restart_requirements`, `security_context`, `execution_type`; the 3.9.2 doc page lists the same. [CODE S-mt2qr2is: plugins/modules/dsc3.ps1#L9-L26; CODE S-mt2qr2is: plugins/modules/dsc3.ps1#L377-L416]
- `win_dsc` invokes a single PowerShell DSC resource (`resource_name`, `module_version` default latest, free-form resource properties); requires PowerShell 5.0+; does not support PowerShell 7.x — use `dsc3` instead. [DOC S-vpn3gco3]
- `win_dsc` runs each task as SYSTEM (use `PsDscRunAsCredential` otherwise), needs the default HTTP WSMan listener, and recommends disabling the LCM. [DOC S-vpn3gco3]
- Licence of the collection source: GPL-3.0-or-later (header in `dsc3.py`); facts here are paraphrased. [CODE S-k3hrxazj: plugins/modules/dsc3.py#L4-L5]

## Reference
| | `win_dsc` [S-vpn3gco3] | `dsc3` [S-zxebbjve, S-mt2qr2is] |
|---|---|---|
| Engine | PowerShell DSC (PS 5.x, WinRM listener) | Microsoft DSC v3 `dsc.exe` |
| Unit | one resource per task | whole configuration document |
| Check mode | supported: runs `Test` only (source, S-g5j4nkll; not stated on the doc page) | `dsc config set --what-if` (DSC 3.1.0 or later) |
| PowerShell 7 | not supported | n/a (calls dsc.exe) |
| Added | (not stated on page) | ansible.windows 3.4.0 |

## Examples
- SNIPPET: run a DSC v3 config file in check mode via the dsc3 module; context: ansible.windows 3.9.2, dsc.exe on PATH; checked: no [DER S-zxebbjve: config_file, remote_config_file, trace_level options; check_mode runs dsc config set --what-if]
```yaml
- name: Preview example baseline document on PL-LT-00123 (check mode = dsc config set --what-if)
  ansible.windows.dsc3:
    config_file: C:\dsc\cfg\workstation.dsc.yaml
    remote_config_file: true
    trace_level: warn
  check_mode: true
```
