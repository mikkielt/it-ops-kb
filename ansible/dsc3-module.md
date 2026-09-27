---
topic: ansible/dsc3-module
priority: P3
applies_to: "ansible.windows collection 3.8.0 (dsc3 added in 3.4.0)"
retrieved_utc: 2026-09-26
sources: [S930, S931, S932, S934, S935]
status: complete
---

# ansible.windows.dsc3 vs ansible.windows.win_dsc

## Summary
The DSC v3 module exists: its name is `ansible.windows.dsc3` (not `microsoft.dsc`), new in ansible.windows 3.4.0; current collection
3.8.0. It runs `dsc config set`, or `dsc config test` in check mode, with a whole configuration document. `win_dsc` is the
PowerShell DSC (v1/v2, PS 5.x) single-resource module; it does not run on PowerShell 7 and points users to `dsc3`.

## Facts
- ansible.windows 3.8.0 lists two DSC modules: `dsc3` ("Sets or checks DSC v3 configuration state") and `win_dsc` ("Invokes a PowerShell DSC configuration"). [DOC S930]
- `dsc3` was added in ansible.windows 3.4.0; FQCN `ansible.windows.dsc3`. [DOC S931]
- `dsc3` calls `dsc config set` or `dsc config test` with `config` as the configuration document; `dsc` must be on PATH, and dsc uses PATH for resource discovery. [DOC S931]
- Options: `config` (dict) or `config_file` (path; one of the two required), `parameters` (dict, maps to `--parameters`), `remote_config_file` (bool, default true), `trace_level` (error/warn/info/debug/trace, default warn). [DOC S931]
- If `$schema` is omitted, the module sets `https://aka.ms/dsc/schemas/v3/bundled/config/document.json`. [DOC S931]
- A local `config_file` (remote_config_file=false) is copied to the target and removed afterwards; it cannot be used with async tasks. [DOC S931]
- Returns `rc` (dsc exit code), `result` (dsc output object), `metadata`, `results` (per resource), `stderr_lines`. [DOC S931]
- Check mode is supported and maps to `dsc config test`; otherwise `dsc config set`. [CODE S935: plugins/modules/dsc3.ps1#L36]
- The module invokes `dsc.exe --trace-format=plaintext --progress-format=none --trace-level=<level> config [--parameters=<json>] <set|test> --file=<path or -> --output-format=json`, passing an inline document on stdin. [CODE S935: plugins/modules/dsc3.ps1#L61-L69]
- Non-zero dsc exit codes 1-5 are reported as: 1 invalid arguments, 2 resource error, 3 JSON serialization error, 4 invalid input YAML/JSON, 5 schema validation failure. [CODE S935: plugins/modules/dsc3.ps1#L79-L86]
- `changed` is true when a resource's `_inDesiredState` is false or it has changed/differing properties; diff mode shows only changed properties per resource. [CODE S935: plugins/modules/dsc3.ps1#L92-L143]
- `dsc3` does not use `--what-if`. [DER S935] (argument list contains no what-if flag; check mode uses `test`)
- `win_dsc` invokes a single PowerShell DSC resource (`resource_name`, `module_version` default latest, free-form resource properties); requires PowerShell 5.0+; does not support PowerShell 7.x — use `dsc3` instead. [DOC S932]
- `win_dsc` runs each task as SYSTEM (use `PsDscRunAsCredential` otherwise), needs the default HTTP WSMan listener, and recommends disabling the LCM. [DOC S932]
- Licence of the collection source: GPL-3.0-or-later (header in `dsc3.py`); facts here are paraphrased. [CODE S934: plugins/modules/dsc3.py#L4-L5]

## Reference
| | `win_dsc` [S932] | `dsc3` [S931, S935] |
|---|---|---|
| Engine | PowerShell DSC (PS 5.x, WinRM listener) | Microsoft DSC v3 `dsc.exe` |
| Unit | one resource per task | whole configuration document |
| Check mode | (not stated on page) | `dsc config test` |
| PowerShell 7 | not supported | n/a (calls dsc.exe) |
| Added | (not stated on page) | ansible.windows 3.4.0 |

## Examples
```yaml
- name: Test example baseline document on PL-LT-00123 (check mode = dsc config test)
  ansible.windows.dsc3:
    config_file: C:\dsc\cfg\workstation.dsc.yaml
    remote_config_file: true
    trace_level: warn
  check_mode: true
```
