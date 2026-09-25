---
topic: dsc/directives
priority: P0
applies_to: "Microsoft DSC 3.3.0 (release/v3.3 @ ea572fa); behaviour re-checked on the 3.4.0-preview.1 binary"
retrieved_utc: 2026-09-25
sources: [S102, S103, S104, S105, S111, S112, S116, S117, S123, S140]
status: complete
---

# Configuration and resource directives

## Summary
- Document-level `directives` has three keys: `version`, `securityContext`, `resourceDiscovery`. Resource-level `directives` has `requireAdapter` and `securityContext`.
- `directives.version` takes a semver requirement: comparators joined by commas, all of which must match (logical AND). An upper bound is written `'>=3.3, <3.4'`.
- A mismatch fails the whole document before any resource runs: exit code 2, message `Validation: Configuration requires DSC version '<req>', but the current version is '<ver>'`.
- **Defect in 3.3.0 and 3.4.0-preview.1:** the check compares against the dsc-lib crate version, which is `3.2.0` in both builds, not the dsc version. On a real 3.3.0 binary `'>=3.3, <3.4'` fails and `'>=3.2, <3.3'` passes.
- `securityContext` is `current` (the default), `elevated` or `restricted`. It is checked before a resource runs; a mismatch gives exit code 2 (`Security context: ...`).

## Facts
- `ConfigDirective` fields are `resourceDiscovery` (`preDeployment` | `duringDeployment`), `securityContext` and `version` (type `SemanticVersionReq`). `ResourceDirective` fields are `requireAdapter` (fully qualified type name) and `securityContext`. [DOC S103]
- `SecurityContextKind` values: `current`, `elevated`, `restricted`. [DOC S103]
- `validate_config` parses the running version from `env!("CARGO_PKG_VERSION")` inside dsc-lib and returns `DscError::Validation` with message `configure.mod.versionNotSatisfied` when `version_req.matches()` is false. [DOC S102,S140]
- dsc-lib's `Cargo.toml` says `version = "3.2.0"` on release/v3.3, while `dsc/Cargo.toml` says `3.3.0`. So the directive is compared against 3.2.0. [DER S102,S111,S112: `env!` inside dsc-lib expands to dsc-lib's crate version]
- Observed on the 3.3.0 macOS arm64 binary (same source as the Windows build): `version: '>=3.3, <3.4'` → exit 2, "Configuration requires DSC version '>=3.3, <3.4', but the current version is '3.2.0'"; `version: '>=3.2, <3.3'` → exit 0. The 3.4.0-preview.1 binary gives the same results. [DER S116,S117: ran `dsc config get` with an Echo document, 2026-09-23]
- The Pester test for the directive checks `'=999.0.0'` (fails, exit 2) and `'>=3.1'` (passes). Neither catches a lib/CLI version mismatch. [DOC S123]
- Requirement syntax as documented in the type: comparators separated by `,`; every comparator must match (AND); there is no OR; a major segment is required; `*` is the only wildcard; `^1.2` → `>=1.2.0, <2.0.0`; `=1.2` → `>=1.2.0, <1.3.0`; prerelease versions match only comparators that carry a prerelease on the same major.minor.patch (`>=2.0.0-0` matches any 2.0.0 prerelease). [DOC S104]
- The type docs say DSC forbids a comparator without an operator, forbids build metadata, and forbids `x`/`X` wildcards. The 3.3.0 binary accepts all three when they appear in `directives.version`: `'3.3'` is echoed as `'^3.3'`, `'1.x'` as `'1.*'`, `'3.3.0+abc'` as `'^3.3.0'`, and `'*'` passes. [DER S104,S116: observed binary output differs from the type docs]
- Security context check order: document `directives.securityContext` (and the deprecated `metadata.Microsoft.DSC.securityContext`, with a warning) is checked in `validate_config`. If both are set and differ, the error is `conflictingSecurityContext`. `elevated` requires an Administrator token and `restricted` requires a non-admin token. [DOC S102]
- Resource-level `directives.securityContext` is checked per resource in get/set/test/export, the same way. [DOC S102]
- Separately, a manifest's `requireSecurityContext` on an operation (for example `Microsoft.Windows/Service` set = `elevated`) fails that operation with `securityContextRequired` when the process lacks that context. [DOC S105]
- Observed: `directives.securityContext: elevated`, run non-elevated on 3.3.0 → exit 2, "Security context: Elevated security context required". [DER S116: local run 2026-09-23]
- Document-level `resourceDiscovery: duringDeployment` skips the up-front discovery pass and refreshes the discovery cache during the run. The default is `preDeployment`. [DOC S102]

## Reference
| Directive | Scope | Values | Failure |
|---|---|---|---|
| `version` | document | semver requirement, e.g. `'>=3.2, <3.3'` | exit 2, `Validation: Configuration requires DSC version ...` |
| `securityContext` | document, resource | `current` / `elevated` / `restricted` | exit 2, `Security context: ...` |
| `resourceDiscovery` | document | `preDeployment` (default) / `duringDeployment` | n/a |
| `requireAdapter` | resource | adapter type name | exit 2, `Adapter not found` |

Observed matrix (3.3.0 binary, which reports lib version 3.2.0):

| `directives.version` | exit |
|---|---|
| `'>=3.2, <3.3'` | 0 |
| `'>=3.3, <3.4'` | 2 |
| `'^3.3'` / `'3.3'` | 2 |
| `'=3.3.0'` | 2 |
| `'>=3.4'` | 2 |
| `'*'` | 0 |

## Examples
```yaml
$schema: https://aka.ms/dsc/schemas/v3/bundled/config/document.json
directives:
  version: '>=3.2, <3.3'      # passes on dsc 3.3.0 because the check uses lib version 3.2.0
  securityContext: elevated
resources:
- name: PL-LT-00123 spooler
  type: Microsoft.Windows/Service
  properties:
    name: Spooler
    startType: Automatic
```
