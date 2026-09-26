---
topic: dsc/settings-and-paths
priority: P0
applies_to: "Microsoft DSC 3.3.0 (release/v3.3 @ ea572fa)"
retrieved_utc: 2026-09-26
sources: [S101, S106, S107, S114, S126, S127, S128]
status: complete
---

# Settings files, resource discovery paths, environment variables

## Summary
- dsc reads settings in this order: `dsc_default.settings.json` (next to dsc.exe, keyed by schema version `"1"`), then `dsc.settings.json` (next to dsc.exe), then the **policy** file `%ProgramData%\dsc\dsc.settings.json` (Linux/macOS: `/etc/dsc/dsc.settings.json`). A policy value wins over a settings value.
- The policy file is used only if its folder is writable by SYSTEM and Administrators alone (Linux: root only). Otherwise dsc warns and ignores it.
- `--ignore-settings-file` or env `DSC_IGNORE_SETTINGS_FILE` skips **all three** files, the policy file included.
- Resource discovery: `DSC_RESTRICTED_PATH` (search only there, and dsc also replaces `PATH` with it) takes precedence over `DSC_RESOURCE_PATH`. Both apply only when `resourcePath.allowEnvOverride` is true. Otherwise dsc searches `resourcePath.directories`, then `PATH` if `appendEnvPath`, then dsc.exe's own folder.

## Facts
- File names and order: `dsc_default.settings.json` (value read under root key `"1"`), then `dsc.settings.json`; both are looked up in the folder of the dsc executable (symlinks are resolved). [DOC S107]
- Policy path on Windows: `$env:ProgramData\dsc\dsc.settings.json`. On other OSes: `/etc/dsc/dsc.settings.json`. [DOC S107]
- If the policy folder exists but `verify_windows_acl` fails (write access must be only SYSTEM and Administrators), dsc warns "Policy folder '<path>' is not secure, settings file will not be used" and ignores it. [DOC S107]
- `DSC_IGNORE_SETTINGS_FILE` (set to `1` by `--ignore-settings-file`) makes `get_setting` return empty before any file, including the policy file, is read. [DER S107,S128: early return precedes the policy lookup]
- Shipped defaults (both zips): `resourcePath: {allowEnvOverride: true, appendEnvPath: true, directories: []}`, `tracing: {level: WARN, format: Default, allowOverride: true}`. [DOC S127,S114]
- Resource path resolution: a policy `resourcePath` replaces the settings one. Then, if `allowEnvOverride` and `DSC_RESTRICTED_PATH` is set, dsc searches only those paths and sets process `PATH` to them. Else, if `allowEnvOverride` and `DSC_RESOURCE_PATH` is set, dsc searches those paths and adds its own folder to `PATH`. Else it searches `directories`, plus `PATH` when `appendEnvPath`, plus its own folder. [DOC S106]
- Tracing level precedence: settings/policy `tracing`, then `DSC_TRACE_LEVEL` env var if `allowOverride`, then command-line `-l`/`-t`. The command line does not override a policy. [DOC S107,S101]
- `DSC_CONFIG_ROOT` is set by dsc to the folder of the configuration file (used by path functions). [DOC S101]
- Open issue #1053 "Doc: DSC_RESOURCE_PATH" (Issue-Bug label). [DOC S126]

## Reference
| Env var | Effect (3.3.0) |
|---|---|
| `DSC_RESTRICTED_PATH` | only these paths are searched; `PATH` is replaced (needs `allowEnvOverride`) |
| `DSC_RESOURCE_PATH` | these paths are searched instead of `directories`/`PATH` (needs `allowEnvOverride`) |
| `DSC_TRACE_LEVEL` | trace level if `tracing.allowOverride` |
| `DSC_IGNORE_SETTINGS_FILE` | ignore every settings file, policy included |
| `DSC_CONFIG_ROOT` | set by dsc: folder of the config document |
| `DEBUG_DSC` | debug builds only: wait for a debugger |

Saved copies: `zip-extras/<version>/dsc.settings.json` and `dsc_default.settings.json`.

## Examples
Policy file `C:\ProgramData\dsc\dsc.settings.json` on PL-SRV-0042 that pins discovery and blocks env overrides:
```json
{
  "resourcePath": { "allowEnvOverride": false, "appendEnvPath": false, "directories": ["C:\\Program Files\\DSC"] },
  "tracing": { "level": "WARN", "format": "Json", "allowOverride": false }
}
```
