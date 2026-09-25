# DISA STIG artifacts (digest)

| File | Source | sha256 | What it is |
|---|---|---|---|
| `U_MS_Windows_11_STIG_V2R9_Manual-xccdf.xml` | S1470 (zip member) | `2380c2fc11d2…` | XCCDF 1.1 benchmark "Microsoft Windows 11 Security Technical Implementation Guide", version 2, "Release: 9 Benchmark Date: 10 Aug 2026"; 257 rules |
| `U_MS_Windows_Server_2025_STIG_V1R3_Manual-xccdf.xml` | S1471 (zip member) | `82392ebcdff7…` | Windows Server 2025 STIG, version 1, release 3, benchmark date 10 Aug 2026; 291 rules |
| `stig-win11-v2r9-rules.csv` | S1470 | `b546afd190d0…` | parsed: `vid, stig_id, severity, title, hive, path, value_name, value_type, value` (registry fields filled for 123 rules) |
| `stig-ws2025-v1r3-rules.csv` | S1471 | `40b9ee47443c…` | same columns (registry fields filled for 96 rules) |

- Licence: US Government work, downloaded from the public (no-login) DISA host. The XCCDF `notice id="terms-of-use"` element is empty.
- Rule-id prefixes:
  - `-00-` general;
  - `-AC-` account policy;
  - `-AU-` audit;
  - `-CC-` computer configuration (ADMX);
  - `-SO-` security options;
  - `-UR-` user rights;
  - `-UC-` user configuration;
  - `-PK-` certificates;
  - `-EP-` exploit protection / DMA;
  - `-RG-` registry permissions;
  - Server 2025 adds `-DC-` (domain controller), `-MS-` (member server) and `-SH-`.
- Parser: registry fields come from the check text lines `Registry Hive:`, `Registry Path:`, `Value Name:`, `Value Type:`, `Value:`. Rules with several paths keep only the first.
- Re-verify: `python _tools/fetch.py --verify` re-downloads the zips and compares the member bytes.
