# Microsoft baseline artifacts (digest)

| File | Source | sha256 | What it is |
|---|---|---|---|
| `win11-24h2-baseline-policyrules.csv` | S1472 | `d2ece80aa3c6…` | Factual extract of `Documentation/MSFT-Win11-v24H2.PolicyRules` from the Windows 11 v24H2 Security Baseline package (files dated 2024-09-30). There is one row per element: `ComputerConfig` (330), `UserConfig` (5), `SecurityTemplate` (68) and `AuditSubcategory` (23). The `SourceFile` column (a Microsoft author's local build path) is dropped. The package itself is not redistributed. |
| `intune-baseline-ref-windows-mdm-settings.md` | S-oeh7ui3h | `f0f199019a39…` | Verbatim CC BY 4.0 page from MicrosoftDocs/memdocs at commit `4b5429df`, ms.date 2026-06-23. It has pivots for Windows MDM baseline versions 25H2 (lines 48-1936), 24H2 (1938-3816), 23H2 and older. Each setting is a `- **Name**` bullet followed by `Baseline default: *value*`. |
| `intune-baseline-overview.md` | S1421 | `3ed516fc1229…` | Verbatim CC BY 4.0 page (ms.date 2026-06-09). It lists baseline versions: Windows 25H2/24H2/23H2; Defender for Endpoint 24H1; Edge v139 (April 2026); Microsoft 365 Apps 2512 (June 2026); Windows 365; and a Windows 11 STIG SCAP audit baseline V2R7 (January 2026). |

- The `.PolicyRules` element types map to crosswalk mechanisms:
  - `ComputerConfig`/`UserConfig` → `registry`;
  - `SecurityTemplate` `MACHINE\…` → `security_policy` (registry-backed);
  - `Se*` → `user_rights`;
  - `"svc",4,""` → `service`;
  - other `SecurityTemplate` → `security_policy`;
  - `AuditSubcategory` (setting 1 = Success, 2 = Failure, 3 = both) → `audit_policy`.
- Attribution: © Microsoft, CC BY 4.0, https://github.com/MicrosoftDocs/memdocs.
