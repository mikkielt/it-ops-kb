---
topic: dsc/what-if
priority: P0
applies_to: "Microsoft DSC 3.3.0 (release/v3.3 @ ea572fa) and 3.4.0-preview.1"
retrieved_utc: 2026-09-26
sources: [S100, S102, S103, S105, S106, S108, S109, S114, S115, S138, S139, S140]
status: complete
---

# What-if (`--what-if`, `--dry-run`, `--noop`)

## Summary
- `dsc config set` and `dsc resource set|delete` accept `-w/--what-if` (aliases `--dry-run`, `--noop`). `dsc config get|test|export` do not.
- Per resource, dsc picks one of three paths: **native** (the manifest's `set.args` has a `whatIfArg`, so the resource simulates the change itself), **legacy** (a top-level `whatIf` operation; deprecated, prints a warning), or **synthetic** (dsc runs `test` and returns the test result as the set result).
- Synthetic what-if is refused when the resource declares `implementsPretest: true` and has no native what-if. The error is "cannot process what-if execution type, as resource implements pre-test and does not support what-if".
- `Microsoft.Windows/Service` and `Microsoft.Windows/FirewallRuleList` both have native what-if in 3.3.0. Both still need an elevated process, because the `set` operation's `requireSecurityContext: elevated` is checked in what-if mode too.
- MCP: the 3.3.0 `dsc server` tools have **no** `what_if` parameter. 3.4.0-preview.1 adds one (see `mcp-server.md`).

## Facts
- `--what-if` (`-w`, visible aliases `--dry-run`, `--noop`) is defined on `config set`, `resource set` and `resource delete` only. [CODE S100: dsc/src/args.rs#L134-L135,L252-L253,L280-L281]
- In `invoke_set` with execution kind WhatIf: if `set.args` contains a `whatIfArg`, dsc runs the set executable with that argument. Else, if the manifest has a top-level `whatIf` operation, dsc runs it and warns that it is deprecated (issue #1361). Else, dsc marks the call as synthetic what-if. [CODE S105: lib/dsc-lib/src/dscresources/command_resource.rs#invoke_set; CODE S140: lib/dsc-lib/locales/en-us.toml#whatIfWarning]
- Synthetic what-if: unless the resource declares `implementsPretest: true`, dsc runs `test` first and returns the test result converted to a set result. The set executable is never run. [CODE S105: lib/dsc-lib/src/dscresources/command_resource.rs#invoke_set]
- If the resource declares `implementsPretest: true` and has no native what-if, dsc returns `NotImplemented` ("cannot process what-if execution type, as resource implements pre-test and does not support what-if"). [CODE S105: lib/dsc-lib/src/dscresources/command_resource.rs#invoke_set; CODE S140: lib/dsc-lib/locales/en-us.toml#syntheticWhatIf]
- `validate_security_context(set.requireSecurityContext)` runs before the what-if branch is used. A what-if on an `elevated` set operation fails when dsc is not elevated. [CODE S105: lib/dsc-lib/src/dscresources/command_resource.rs#invoke_set]
- In what-if mode, the output shape follows `set.whatIfReturns`, falling back to `set.return`. [CODE S105: lib/dsc-lib/src/dscresources/command_resource.rs#invoke_set]
- For `resource delete --what-if`, or a config instance with `_exist: false` on a resource that implements delete: without a delete `whatIfArg`, dsc runs `test` and returns it as a synthetic what-if. [CODE S102: lib/dsc-lib/src/configure/mod.rs#invoke_set; CODE S105: lib/dsc-lib/src/dscresources/command_resource.rs#invoke_delete]
- In a configuration set, instances with `_exist: false` go to `delete` only when the resource lacks `setHandlesExist`. [CODE S102: lib/dsc-lib/src/configure/mod.rs#invoke_set]
- The what-if result's `executionInformation.executionType` / `metadata.Microsoft.DSC.executionType` is `whatIf`. [CODE S102: lib/dsc-lib/src/configure/mod.rs#invoke_set; CODE S103: lib/dsc-lib/src/configure/config_doc.rs#ExecutionKind; CODE S109: dsc/src/server/invoke_dsc_config.rs#InvokeDscConfigRequest.what_if]
- `Microsoft.Windows/Service` 0.1.1 (3.3.0 zip): `set.args` = `["set", {jsonInputArg: --input, mandatory}, {whatIfArg: "--what-if"}]`, `implementsPretest: false`, `whatIfReturns: state`, `requireSecurityContext: elevated`. [DOC S114]
- `windows_service.exe` reads `--what-if`/`-w` from its args. In what-if, `_exist: false` is routed to a delete simulation (`what_if_delete_service`); otherwise it calls `set_service(input, what_if)`. [CODE S138: resources/windows_service/src/main.rs#parse_what_if_flag]
- `Microsoft.Windows/FirewallRuleList` 0.3.0 (3.3.0 zip): `set.args` includes `{whatIfArg: "--what-if"}`, `implementsPretest: true`, `handlesExist: true`, `whatIfReturns: state`, `requireSecurityContext: elevated`. [DOC S114]
- `windows_firewall.exe` `set_rules(input, what_if)` in what-if returns projected rules instead of changing the store; create, remove, remove-unspecified and disable-unspecified cases carry a what-if message in the rule's metadata. [CODE S139: resources/windows_firewall/src/firewall.rs#set_rules]
- `Microsoft.Windows/UpdateList` has no what-if in 3.3.0 (0.1.0; synthetic path). Native what-if arrives in 3.4.0-preview.1 (0.1.1). [DOC S114,S115]

## Reference
What-if mode per type, from the saved 3.3.0 manifests (full table in `manifests-diff.csv`):

| Mode | Types (3.3.0) |
|---|---|
| native (`whatIfArg`) | Microsoft.Windows/Registry (set + delete), Microsoft.Windows/RegistryList, Microsoft.Windows/Service, Microsoft.Windows/FirewallRuleList, Microsoft.Windows/WindowsFeatureList, Microsoft.OpenSSH.SSHD/sshd_config, /Subsystem, /SubsystemList, /Windows |
| synthetic (test result) | Microsoft.Windows/UpdateList (3.3.0 only), Microsoft.Windows/OptionalFeatureList, Microsoft.Windows/FeatureOnDemandList, Microsoft.DSC.Debug/Echo, Microsoft.Windows.Adapter/Registry, Microsoft.Windows/WMI, Microsoft.Windows/WindowsPowerShell (deprecated) |
| error (pretest, no what-if) | Microsoft.Adapter/PowerShell, Microsoft.Adapter/WindowsPowerShell, Microsoft.DSC/PowerShell, Microsoft.DSC.Transitional/PowerShellScript, /WindowsPowerShellScript, /RunCommandOnSet, Microsoft.DSC/Group, /Assertion, /Include |
| n/a (no set) | Microsoft.Windows/RebootPending, Microsoft/OSInfo |

Adapter and group rows follow from their own manifests. Resources run *through* an adapter take the adapter's set path. [DER S105,S114: `invoke_set` takes the what-if path from the adapter's own manifest (`resource.manifest`), with the adapted resource passed as `target_resource`, plus the adapter manifest flags]

## Examples
```powershell
# Elevated PowerShell on PL-SRV-0042; nothing is changed
dsc config set --what-if --file .\baseline.dsc.yaml --output-format json
dsc resource set -r Microsoft.Windows/Service -w -i '{"name":"Spooler","startType":"Disabled"}'
```
