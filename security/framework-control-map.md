---
topic: security/framework-control-map
priority: P2
applies_to: "ISO/IEC 27001:2022 Annex A; NIST CSF 2.0; CIS Controls v8.1; NIS2 Art. 21(2), as of 2026-09-24"
retrieved_utc: 2026-09-24
sources: [S1552, S1560, S1561, S1562, S1563]
status: partial
---

# Framework-to-control digest

## Summary
Full table is `framework-control-map.csv` (framework, control_id, title, control_example, sources). This file gives
the shape and licence notes only. ISO/IEC 27001:2022 Annex A has 93 controls in 4 themes; full clause text is paid,
so only numbers and public titles are used here. CIS Controls v8.1 is CC BY-NC-ND 4.0 (attribution, no derivatives,
non-commercial) [DOC S1563], so safeguard IDs and titles are cited but not modified or excerpted at length.

## Facts
- ISO/IEC 27001:2022 Annex A groups controls under four themes: organizational, people, physical, technological.
  5.15, 5.18, 8.2, 8.8, 8.9, 8.15, 8.16, 8.32 are covered in the csv (all technological/organizational controls
  relevant to a tool that manages device configuration). [DOC S1560][DOC S1561]
- NIST CSF 2.0 (published 2024-02-26) added the "Govern" function to the five prior functions (Identify, Protect,
  Detect, Respond, Recover). [DOC S1562]
- CIS Controls v8.1 (March 2025) has 18 Controls and 153 Safeguards across three Implementation Groups; licensed
  CC BY-NC-ND 4.0 (no derivatives). The csv therefore cites safeguard IDs only, with a short own-words paraphrase
  in place of the official safeguard title, rather than reproducing CIS wording. [DOC S1563]

## Reference
### Notes (design notes and cross-references, no external source)
- NIS2 Art. 21(2) letters (a)-(j) are quoted in `privacy-compliance.md`; the crosswalk here selects the letters
  that map to a device-configuration tool's own controls (configuration management, supply chain, access control, MFA).

See `framework-control-map.csv`. Row count: 22 (8 ISO, 5 NIST CSF, 5 CIS, 4 NIS2).

## Examples
Not applicable (reference table).
