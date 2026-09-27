# OSConfig artifacts (digest)

| File | Source | sha256 | What it is |
|---|---|---|---|
| `SecurityBaseline_WindowsServer_2025-2606.csv` | S1598 | `e6f00dfd0ca8…` | Verbatim (MIT, © Microsoft) OSConfig security baseline for Windows Server 2025, version 2606, from `microsoft/osconfig` at commit `82a54b9e`. It has 361 rows. |

- Columns:
  - `Name, ExtraId (CCE), Control Name`;
  - `Registry Key, Registry Value, Registry Value Type`;
  - `CSP Name, CSP Path, CSP Value Type`;
  - `Default Value` and `Expected Value` for Domain Controller, Member Server and Workgroup Member;
  - `Allowed Value, Severity, Availability, Category, Description`;
  - `CIS RuleID, CIS Control, STIG ID, NIST SP 800-53 Rev 5`;
  - `Security Impact, Change Risk Level`.
- Counts: categories Registry 216, Security Options 56, Security Policy 52, Audit Policy 34, SecuredCore 3. 271 rows have a registry key and 152 a CSP path. 329 rows carry a CIS RuleID, 147 a STIG id (`WN25-…`). Change risk: 235 Low, 126 Medium.
- The CIS RuleIDs are Microsoft's mapping to a CIS Windows Server 2025 benchmark. The benchmark version is not stated in the file.
- Earlier versions in the same folder: 2409, 2411, 2504, 2510.
