---
topic: dsc/releases-feature-matrix
priority: P0
applies_to: "Microsoft DSC 3.0.0 to 3.4.0-preview.1"
retrieved_utc: 2026-09-26
sources: [S110, S111, S112, S113, S114, S115, S116, S117, S118, S119, S120, S121, S122, S129, S130, S131, S132, S133, S134, S143, S144, S-mmshotst, S-g4krsgp2, S-6hlzzfeg]
status: complete
---

# Releases 3.0 → 3.4.0-preview.1 and what actually ships

## Summary
- The **git tag `v3.3.0` does not point at the 3.3.0 code.** The release was created with `target_commitish: main`. The tag sits on main commit 4b49240, whose `dsc/Cargo.toml` says `3.4.0-preview.1`. The 3.3.0 binaries match branch `release/v3.3` (head ea572fa, "Update version and dependencies for 3.3.0", Cargo `3.3.0`).
- As a result, the 3.3.0 release notes (auto-generated `v3.3.0-rc.2...v3.3.0`) list main-only work that is **not** in the 3.3.0 binaries: MCP `what_if`, the Group Policy template adapter, the environment variable resources, File/Content, UpdateList `--what-if`, and the `--required-version` rename.
- In 3.4.0-preview.1: MCP `what_if`, EnvironmentVariable(List), File/Content and UpdateList what-if ship. The Group Policy adapter is built from source but **not packaged** in the zip. `Microsoft.Windows/Personalization` ships in neither version.
- Repo `CHANGELOG.md` stops at v3.1.1 on release/v3.3 and at v3.2.2 on main. GitHub release notes are the only per-release list for 3.2.3 onward.

## Facts
- GitHub release v3.3.0: created 2026-09-16T21:00:15Z, published 2026-09-17T14:53:40Z, `target_commitish: main`, not a prerelease. v3.4.0-preview.1: created 2026-09-09, published 2026-09-10, `target_commitish: main`, prerelease. v3.3.0-rc.1 and rc.2: `target_commitish: release/v3.3`. [DOC S113]
- The tag v3.3.0 resolves to commit 4b492407 ("(GH-538) Set URI and docs keywords for `DscRepoSchema` types (#1699)"), where `dsc/Cargo.toml` has `version = "3.4.0-preview.1"`. [DOC S110]
- Branch release/v3.3 head ea572fa (2026-09-01) has `dsc/Cargo.toml` `version = "3.3.0"` and no `adapters/group_policy_template`, `resources/environment_variable` or `resources/filecontent`. [DOC S111,S144]
- `dsc --version` on the 3.3.0 release binary prints `dsc 3.3.0`. The 3.3.0 dsc.exe contains `3.3.0` and not `3.4.0-preview.1`. [DOC S116,S114]
- The 3.3.0 release notes open "These release notes describe updates to DSC since the `v3.3.0-rc.2` release". They list under Added: rename `--version` to `--required-version` (#1610), UpdateList `--what-if` (#1616), Group Policy template adapter (#1686), Windows environment variable resource (#1675), File/Content (#1676), MCP `--what-if` (#1697). [DOC S118]
- The 3.4.0-preview.1 release notes list the same six items. [DOC S119]
- The 3.3.0 binary still uses `-v, --version` for resource commands. 3.4.0-preview.1 uses `-v, --required-version`. [DOC S116,S117]
- `--ignore-settings-file` was backported to the 3.2 line: `args.rs` at tag v3.2.3 (2026-07-16) defines it as a global flag with the short form `-i`. The matrix's 3.2.0 column describes the v3.2.0 tag only. [DOC S-mmshotst, S113]
- The dsc-lib crate version is `3.2.0` in both 3.3.0 and 3.4.0-preview.1. This breaks `directives.version` (see `directives.md`). [DOC S112, S-g4krsgp2]
- `data.build.json` in 3.4.0-preview.1 packages `environment_variable.exe`, `environment_variable.dsc.manifests.json`, `filecontent.exe`, `filecontent.dsc.resource.json` and has no `group_policy_template` entry. [DOC S120]
- `Microsoft.Adapter/GroupPolicyTemplate` 0.1.0 ("Adapts Windows Group Policy ADMX templates into DSC resources") exists as a source manifest at v3.4.0-preview.1. [DOC S121]
- `Microsoft.Windows/Personalization` is an adapted-resource YAML (needs `Microsoft.Windows.Adapter/Registry`) present in source on release/v3.3 and v3.4.0-preview.1, and absent from both zips. [DOC S122,S-6hlzzfeg,S114,S115]

## Reference
Feature matrix (verified against code at each tag or branch and against the release zips/binaries):

| Feature | 3.0.0 | 3.1.0 | 3.2.0 | 3.3.0 (shipped) | 3.4.0-preview.1 |
|---|---|---|---|---|---|
| `dsc extension` | no | yes | yes | yes | yes |
| `dsc function list` | no | no | yes | yes | yes |
| MCP server | no | no | `dsc mcp`, 5 tools | `dsc server` (alias `mcp`), 8 tools | 8 tools |
| MCP `what_if` param | – | – | no | **no** (notes say yes) | yes |
| `--what-if` aliases `--dry-run`/`--noop` | no | no | yes | yes | yes |
| `resource delete --what-if` | no | no | yes | yes | yes |
| `--ignore-settings-file` | no | no | no | yes | yes |
| Policy settings file, `DSC_RESOURCE_PATH` | yes | yes | yes | yes | yes |
| `DSC_RESTRICTED_PATH` | no | no | no | yes | yes |
| `directives` (version/securityContext/resourceDiscovery) | no | no | yes | yes (version check uses lib 3.2.0) | same defect |
| `secret()` function | no | no | yes | yes | yes |
| Functions count | 17 | 20 | 81 | 83 | 83 |
| `-v/--required-version` rename | – | – | – | **no** (`--version`) | yes |
| `Microsoft.Windows/UpdateList` native what-if | – | – | no | **no** (0.1.0) | yes (0.1.1) |
| `Microsoft.Windows/EnvironmentVariable(List)` | no | no | no | **no** | yes |
| `Microsoft.Filesystem.File/Content` | no | no | no | **no** | yes |
| Group Policy template adapter | no | no | no | **no** | **no** (source only, not in zip) |
| `Microsoft.Windows/Personalization` | no | no | no | no (source only) | no (source only) |
| Windows Service / FirewallRuleList resources | no | no | yes | yes | yes |

Rows for 3.0.0 to 3.2.0 come from `args.rs`, `functions/mod.rs` and the `resources/` directory at those tags. The 3.2.0 resource row is from source, not from a zip. [DER S132,S133,S134,S129,S130,S131]

Release dates (GitHub, published): 3.0.0 2025-02-28 (CHANGELOG), 3.1.0 2025-06-18, 3.2.0 2026-04-29, 3.2.3 2026-07-16, 3.3.0 2026-09-17, 3.4.0-preview.1 2026-09-10. [DOC S113,S143]

## Examples
```powershell
# Confirm what a host really runs before trusting release notes
dsc --version
dsc resource list Microsoft.Windows/EnvironmentVariable -o json   # empty on 3.3.0
```
