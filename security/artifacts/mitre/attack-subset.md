---
topic: security/artifacts/mitre/attack-subset
priority: P2
applies_to: "MITRE ATT&CK Enterprise v19.2 (STIX bundle, tag v19.2)"
retrieved_utc: 2026-09-26
sources: [S1576]
status: complete
---

# ATT&CK subset: mitigations and detection strategies for endpoint-management techniques

## Summary
Extracted from the pinned `enterprise-attack.json` STIX 2.1 bundle at tag `v19.2` of
`mitre-attack/attack-stix-data`, sha256 `dc1639caa5501d720e280cf1cbd8fbe009884a0c9b3e6e9ed9d0c25166c3d8f4`. Covers
T1072, T1484, T1098, T1558, T1078, T1219, T1562 (7 requested techniques). T1562 "Impair Defenses" is revoked in
this data model and replaced by T1685 "Disable or Modify Tools" (see Facts) — its row is recorded under
`T1685 (replaces T1562)`. ATT&CK's current data model (introduced v17) replaced the old data-component `detects`
mapping with `x-mitre-detection-strategy` objects (`DET####`) that reference `x-mitre-analytic` objects
(`AN####`), each naming log sources. Mitigation ids remain `M####` as before.

## Facts
- Technique mitigation counts in this bundle: T1558 (6), T1219 (5), T1072 (9), T1098 (7), T1078 (8), T1484 (3),
  T1685/T1562 (7). [DOC S1576]
- Each of the 7 techniques has exactly one detection strategy object in this bundle, each referencing 2-7
  analytics and 3-9 named log sources (e.g. `WinEventLog:Security`, `WinEventLog:Sysmon`, `auditd:SYSCALL`,
  `azure:signinlogs`, `saas:okta`). [DOC S1576]
- T1562 (`attack-pattern--3d333250-30e4-4a82-9edc-756c68afc529`) has `revoked: true` in the v19.2 bundle and a
  `revoked-by` relationship to T1685 "Disable or Modify Tools". [DOC S1576]

## Reference
Full table: `attack-subset.csv` (columns: `technique_id, technique_name, record_type, id, name, log_sources`).
`record_type` is `mitigation` (id = `M####`) or `detection_strategy` (id = `DET####`, `log_sources` lists the
named log sources across its analytics, with analytic ids `AN####` in parentheses).

## Examples
Not applicable (reference extract); no fixture data involved.
