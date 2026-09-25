---
topic: dsc/schemas
priority: P0
applies_to: "Microsoft DSC 3.3.0 (binary-generated) and the repo schema files on release/v3.3 @ ea572fa"
retrieved_utc: 2026-09-25
sources: [S116, S117, S137, S146, S147, S148, S149, S150, S151, S152, S153, S154, S155, S145]
status: complete
files: [dsc/schemas/]
---

# DSC JSON schemas: configuration document, resource manifest, outputs

## Summary
- There are two sets. (1) `schemas/generated-3.3.0/` and `schemas/generated-3.4.0-preview.1/`: the output of `dsc schema -t <type> -o pretty-json` for all 22 types, run on each release binary. This is what the engine validates against. (2) `schemas/repo-release-v3.3/`: the static bundled schema files published in the repo (the `aka.ms/dsc/schemas/v3/...` targets), pinned to commit ea572fa.
- The static repo schemas are **stale**. Their build config says `version: v3.1.0`, and the bundled configuration document schema has no `directives` property. The 3.3.0 binary schema has it.
- The 3.3.0 binary accepts `$schema` values up to `v3.2.3` plus `v3`, `vNext`, and the `raw.githubusercontent.com/PowerShell/DSC/main/...` forms. A `v3.3` URI is not in its enum.
- There is no static "export output" schema in the repo. Use `generated-*/configuration-export-result.json`.

## Facts
- `dsc schema --type` values (3.3.0): adapted-dsc-resource-manifest, configuration, configuration-export-result, configuration-get-result, configuration-set-result, configuration-test-result, dsc-resource, extension-discover-result, extension-manifest, function-definition, get-result, include, manifest-list, resolve-result, resource, resource-get-result, resource-set-result, resource-test-result, resource-manifest, restart-required, set-result, test-result. [DOC S116]
- Generated `configuration.json` (3.3.0): JSON Schema draft 2020-12; required `$schema`, `resources`; top-level properties `$schema`, `contentVersion`, `directives`, `executionInformation`, `functions`, `metadata`, `outputs`, `parameters`, `resources`, `variables`. [DOC S116]
- Generated `resource-manifest.json` (3.3.0): required `$schema`, `type`, `version`; properties include `get`, `set`, `whatIf`, `test`, `delete`, `export`, `resolve`, `validate`, `adapter`, `exitCodes`, `schema`, `condition`, `deprecationMessage`, `kind`, `tags`, `metadata`. [DOC S116]
- Generated `configuration-export-result.json` properties: `executionInformation`, `metadata`, `result`, `messages`, `hadErrors`, `outputs`. `configuration-set-result.json`: `executionInformation`, `metadata`, `results`, `messages`, `hadErrors`, `outputs`. [DOC S116]
- The `$schema` enum in the 3.3.0 generated configuration schema lists v3, v3.0.x, v3.1.x, v3.2.x (up to v3.2.3) and vNext URIs (aka.ms and raw GitHub `main` forms). It has no v3.3 entry. [DOC S116]
- All 22 generated schema files differ in bytes between 3.3.0 and 3.4.0-preview.1. [DER S116,S117: file compare]
- The repo `schemas/schemas.config.yaml` on release/v3.3 has `version: v3.1.0` and `prefix: PowerShell/DSC/main/schemas`. [DOC S137]
- The repo bundled `config/document.json` has `$id` `https://raw.githubusercontent.com/PowerShell/DSC/main/schemas/v3/config/document.json` and top-level properties `$schema`, `parameters`, `variables`, `resources`, `metadata` only (no `directives`). [DOC S146]
- The Learn schema reference (`view=dsc-3.0`) documents the 3.0 document shape. [DOC S145]

## Reference
| File | What |
|---|---|
| `schemas/generated-3.3.0/configuration.json` | configuration document (engine truth, 3.3.0) |
| `schemas/generated-3.3.0/resource-manifest.json` | resource manifest |
| `schemas/generated-3.3.0/configuration-{get,set,test,export}-result.json` | `dsc config` outputs |
| `schemas/generated-3.3.0/resource-{get,set,test}-result.json`, `get-result.json`, `set-result.json`, `test-result.json` | `dsc resource` outputs |
| `schemas/repo-release-v3.3/bundled/...` | published static bundles (stale, v3.1.0 shape) |

sha256 of every file: `_parts/dsc/artifacts.csv`.

## Examples
```powershell
dsc schema -t configuration-test-result -o json > test-result.schema.json
```
