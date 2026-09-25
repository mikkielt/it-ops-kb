---
topic: dsc/cli-reference
priority: P0
applies_to: "Microsoft DSC 3.3.0 (binary --help output; source release/v3.3 @ ea572fa)"
retrieved_utc: 2026-09-23
sources: [S100, S101, S116, S117, S118, S128, S135, S136, S141]
status: complete
---

# `dsc` 3.3.0 command-line reference

## Summary
- Top-level commands: `completer`, `config`, `extension`, `function`, `server` (alias `mcp`), `resource`, `schema`. Hidden: `config validate`, `config resolve`, plus internal flags `--as-group`, `--as-assert`, `--as-include`, `--as-get`, `--as-config`.
- Global options: `-l/--trace-level`, `-t/--trace-format`, `-p/--progress-format`, `--ignore-settings-file`, `-h`, `-V`.
- Output formats: `json`, `pretty-json`, `yaml`. `resource get` adds `json-array` and `pass-through`. The `list` commands add `table-no-truncate`; with no `-o` on a terminal, `list` prints a table.
- Exit codes 0 to 10 (below). A version or security-context failure in a document is exit 2.
- Full verbatim `--help` output for every subcommand: `cli/help-3.3.0.txt` and `cli/help-3.4.0-preview.1.txt`.

## Facts
- Top-level `dsc --help` on 3.3.0 lists: completer, config, extension, function, server ("Use DSC as a server over JSON-RPC (useful as MCP server)"), resource, schema. [DOC S116]
- The `server` subcommand has alias `mcp`. In 3.2.x the subcommand was named `mcp`. [DOC S100,S134]
- Global options: `-l, --trace-level <error|warn|info|debug|trace>`, `-t, --trace-format <default|plaintext|json>` (a hidden `pass-through` value also exists), `-p, --progress-format <default|none|json>`, `--ignore-settings-file` (sets env `DSC_IGNORE_SETTINGS_FILE=1`). [DOC S100,S128,S116]
- `dsc config` options: `-p/--parameters <JSON|YAML>`, `-f/--parameters-file <path>`, `-r/--system-root <path>`. In 3.3.0, `--parameters` and `--parameters-file` may be given together and are merged. In 3.0/3.1 they conflicted. [DOC S100,S128,S132,S133]
- `config get|set|test|export|validate|resolve` each take `-i/--input` or `-f/--file` (`-` = stdin; mutually exclusive) and `-o/--output-format <json|pretty-json|yaml>`. `set` adds `-w/--what-if` (`--dry-run`, `--noop`). [DOC S100,S116]
- `resource get` options: `-a/--all`, `-r/--resource`, `-v/--version <VERSION>`, `-i`, `-f`, `-o <json|json-array|pass-through|pretty-json|yaml>`. [DOC S116]
- `resource set|delete` take `-r`, `-v`, `-i`, `-f`, `-o`, `-w/--what-if`. `resource test|export` take `-r`, `-v`, `-i`, `-f`, `-o`. `resource schema` takes `-r`, `-v`, `-o`. [DOC S116]
- `resource list [RESOURCE_NAME]` takes `-a/--adapter`, `-d/--description`, `-t/--tags`, `-o <json|pretty-json|yaml|table-no-truncate>`. `extension list [NAME]` takes `-o`. `function list [NAME]` takes `-c/--category` (repeatable, AND), `-d/--description`, `-o`. [DOC S100,S116]
- In the 3.3.0 binary the resource version option is `-v, --version <VERSION>` ("The version of the resource to invoke in semver format"). In 3.4.0-preview.1 it is `-v, --required-version <REQUIRED_VERSION>` with hidden alias `--version`. [DOC S116,S117]
- `dsc schema -t/--type <type> [-o]`. Types: adapted-dsc-resource-manifest, configuration, configuration-export-result, configuration-get-result, configuration-set-result, configuration-test-result, dsc-resource, extension-discover-result, extension-manifest, function-definition, get-result, include, manifest-list, resolve-result, resource, resource-get-result, resource-set-result, resource-test-result, resource-manifest, restart-required, set-result, test-result. [DOC S116]
- `dsc completer <bash|elvish|fish|powershell|zsh>` writes a completion script to stdout. [DOC S116]
- Exit codes (constants): 0 success, 1 invalid args, 2 DSC error (resource/engine error, including directive validation and security context), 3 JSON error, 4 invalid input, 5 validation failed, 6 Ctrl+C, 7 resource not found, 8 assertion failed, 9 server failed, 10 Bicep failed. [DOC S101]
- The Learn page (ms.date 2025-03-25) documents only exit codes 0 to 6. [DOC S135]
- On Windows, if dsc.exe's parent process is `sihost.exe` or `explorer.exe` (for example, launched from the Store or by double-click), it prints a message, waits for a keypress and exits with code 1. [DOC S128]
- On Ctrl+C, dsc kills its child process tree and exits with 6. [DOC S128]
- Env vars read by the CLI: `DSC_TRACE_LEVEL` and `DSC_CONFIG_ROOT` (constants in dsc util.rs), and `DEBUG_DSC` (debug builds only). [DOC S101,S128]

## Reference
| Code | Meaning (constant) |
|---|---|
| 0 | EXIT_SUCCESS |
| 1 | EXIT_INVALID_ARGS |
| 2 | EXIT_DSC_ERROR |
| 3 | EXIT_JSON_ERROR |
| 4 | EXIT_INVALID_INPUT |
| 5 | EXIT_VALIDATION_FAILED |
| 6 | EXIT_CTRL_C |
| 7 | EXIT_DSC_RESOURCE_NOT_FOUND |
| 8 | EXIT_DSC_ASSERTION_FAILED |
| 9 | EXIT_SERVER_FAILED |
| 10 | EXIT_BICEP_FAILED |

Subcommand history (from `args.rs` at each tag): 3.0.0 has completer, config, resource, schema. 3.1.0 adds `extension`. 3.2.0 adds `function` and `mcp`. 3.3.0 renames `mcp` to `server` (alias `mcp`) and adds `--ignore-settings-file`. [DER S132,S133,S134,S100]

## Examples
```powershell
dsc -l warn -t json config test -f .\baseline.dsc.yaml -o json > result.json
dsc resource get -r Microsoft.Windows/Service -i '{"name":"Spooler"}'
dsc resource list 'Microsoft.Windows/*' -o table-no-truncate
dsc schema -t configuration -o pretty-json
```
