---
topic: dsc/cli-reference
priority: P0
applies_to: "Microsoft DSC 3.3.0 (binary --help output; source release/v3.3 @ ea572fa)"
retrieved_utc: 2026-09-27
sources: [S100, S101, S116, S117, S118, S128, S132, S133, S134, S135, S136, S141, S-mmshotst]
status: complete
files: [dsc/cli/]
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
- The `server` subcommand has alias `mcp`. In 3.2.x the subcommand was named `mcp`. [CODE S100: dsc/src/args.rs#SubCommand; CODE S134: dsc/src/args.rs#SubCommand]
- Global options: `-l, --trace-level <error|warn|info|debug|trace>`, `-t, --trace-format <default|plaintext|json>` (a hidden `pass-through` value also exists), `-p, --progress-format <default|none|json>`, `--ignore-settings-file` (sets env `DSC_IGNORE_SETTINGS_FILE=1`). [DOC S100,S128,S116]
- `dsc config` options: `-p/--parameters <JSON|YAML>`, `-f/--parameters-file <path>`, `-r/--system-root <path>`. In 3.3.0, `--parameters` and `--parameters-file` may be given together and are merged. In 3.0/3.1 they conflicted. [CODE S100: dsc/src/args.rs#SubCommand; CODE S128: dsc/src/main.rs#merge_parameters; CODE S132: dsc/src/args.rs#SubCommand; CODE S133: dsc/src/args.rs#SubCommand]
- `config get|set|test|export|validate|resolve` each take `-i/--input` or `-f/--file` (`-` = stdin; mutually exclusive) and `-o/--output-format <json|pretty-json|yaml>`. `set` adds `-w/--what-if` (`--dry-run`, `--noop`). [DOC S100,S116]
- `resource get` options: `-a/--all`, `-r/--resource`, `-v/--version <VERSION>`, `-i`, `-f`, `-o <json|json-array|pass-through|pretty-json|yaml>`. [DOC S116]
- `resource set|delete` take `-r`, `-v`, `-i`, `-f`, `-o`, `-w/--what-if`. `resource test|export` take `-r`, `-v`, `-i`, `-f`, `-o`. `resource schema` takes `-r`, `-v`, `-o`. [DOC S116]
- `resource list [RESOURCE_NAME]` takes `-a/--adapter`, `-d/--description`, `-t/--tags`, `-o <json|pretty-json|yaml|table-no-truncate>`. `extension list [NAME]` takes `-o`. `function list [NAME]` takes `-c/--category` (repeatable, AND), `-d/--description`, `-o`. [DOC S100,S116]
- In the 3.3.0 binary the resource version option is `-v, --version <VERSION>` ("The version of the resource to invoke in semver format"). In 3.4.0-preview.1 it is `-v, --required-version <REQUIRED_VERSION>` with hidden alias `--version`. [DOC S116,S117]
- The 3.3.0 release notes list "(GH-1393) Rename `--version` to `--required-version` for resource commands" (PR #1610), yet the 3.3.0 binary still takes `--version`: the notes include main-only work (see `dsc/releases-feature-matrix.md` and `_conflicts.md`). [DOC S118]
- `dsc schema -t/--type <type> [-o]`. Types: adapted-dsc-resource-manifest, configuration, configuration-export-result, configuration-get-result, configuration-set-result, configuration-test-result, dsc-resource, extension-discover-result, extension-manifest, function-definition, get-result, include, manifest-list, resolve-result, resource, resource-get-result, resource-set-result, resource-test-result, resource-manifest, restart-required, set-result, test-result. [DOC S116]
- The help strings come from `dsc/locales/en-us.toml`: `serverAbout` is "Use DSC as a server over JSON-RPC (useful as MCP server)" and `ignoreSettingsFile` is "Ignore the settings file when running the command". [CODE S141: dsc/locales/en-us.toml#serverAbout]
- The repository's command reference page for this subcommand (`docs/reference/cli/server/index.md`, ms.date 2026-06-17) is still titled `dsc mcp`: it says the command starts DSC as a long-running MCP server and documents only `-h/--help`. [DOC S136]
- `dsc completer <bash|elvish|fish|powershell|zsh>` writes a completion script to stdout. [DOC S116]
- Exit codes (constants): 0 success, 1 invalid args, 2 DSC error, 3 JSON error, 4 invalid input, 5 validation failed, 6 Ctrl+C, 7 resource not found, 8 assertion failed, 9 server failed, 10 Bicep failed. [CODE S101: dsc/src/util.rs#L68-L78]
- The Learn page (ms.date 2025-03-25) documents only exit codes 0 to 6. [DOC S135]
- On Windows, if dsc.exe's parent process is `sihost.exe` or `explorer.exe` (for example, launched from the Store or by double-click), it prints a message, waits for a keypress and exits with code 1. [CODE S128: dsc/src/main.rs#L201-L226]
- On Ctrl+C, dsc kills its child process tree and exits with 6. [CODE S128: dsc/src/main.rs#L155-L174]
- Env vars read by the CLI: `DSC_TRACE_LEVEL` and `DSC_CONFIG_ROOT` (constants in dsc util.rs), and `DEBUG_DSC` (debug builds only). [CODE S101: dsc/src/util.rs#L80-L81; CODE S128: dsc/src/main.rs#L181]

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

Subcommand history (from `args.rs` at each tag): 3.0.0 has completer, config, resource, schema. 3.1.0 adds `extension`. 3.2.0 adds `function` and `mcp`. 3.3.0 renames `mcp` to `server` (alias `mcp`) and adds `--ignore-settings-file`. The 3.2 line got the flag later as a backport: tag v3.2.3 defines it as `-i, --ignore-settings-file` and still names the subcommand `mcp`. [DER S132,S133,S134,S100,S-mmshotst]

## Examples
- SNIPPET: run a config, get/list resources and print a schema; context: dsc 3.3.0, dsc.exe on PATH; checked: no [DER S116, S117: subcommand and flag syntax from the 3.3.0/3.4.0-preview.1 binaries' --help and schema output]
```powershell
dsc -l warn -t json config test -f .\baseline.dsc.yaml -o json > result.json
dsc resource get -r Microsoft.Windows/Service -i '{"name":"Spooler"}'
dsc resource list 'Microsoft.Windows/*' -o table-no-truncate
dsc schema -t configuration -o pretty-json
```

## Related
- `windows/azure-arc-servers.md` (Azure Machine Configuration relation to DSC): Azure Machine Configuration
  (formerly Guest Configuration) validates/remediates using its own side-loaded PowerShell DSC engine
  (DSC v2 on Windows, DSC v3 on Linux) — a different DSC version/build than this `dsc` 3.3.0 binary and
  its `dsc config`/`dsc resource` model documented above.
