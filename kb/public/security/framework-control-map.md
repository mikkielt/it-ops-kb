---
topic: security/framework-control-map
priority: P2
applies_to: "ISO/IEC 27001:2022 Annex A; NIST CSF 2.0; CIS Controls v8.1; NIS2 Art. 21(2), as of 2026-09-24"
retrieved_utc: 2026-09-24
sources: [S1552, S-fr4o3437, S1562, S1563, S-n3ela3o4, S-riwffp3c]
status: partial
---

# Framework-to-control digest

## Summary
Full table is `framework-control-map.csv` (framework, control_id, title, control_example, sources). This file gives
the shape and licence notes only. ISO/IEC 27001:2022 clause text is paid, so the csv gives Annex A control ids
(confirmed against NIST's crosswalk) with short own-words names. CIS Controls v8.1 is CC BY-NC-ND 4.0 (attribution, no derivatives,
non-commercial) [DOC S1563], so safeguard IDs and titles are cited but not modified or excerpted at length.

## Facts
- The csv's ISO/IEC 27001:2022 Annex A ids 5.15, 5.18, 8.2, 8.8, 8.9, 8.15, 8.16 and 8.32 each appear (written
  A.5.15 etc.) as reference elements in NIST's SP 800-53 Rev. 5 to ISO/IEC 27001:2022 crosswalk (OLIR, file dated
  2023-10-12). It maps, for example, A.5.18 from AC-02, A.8.8 from RA-03/RA-05/SI-02/SI-05, A.8.15 from AU-02/AU-03/
  AU-06/AU-12 and A.8.32 from CM-03/CM-05/SA-10/SI-02. [DOC S-n3ela3o4]
- The csv titles (Access control, Access rights, Privileged access rights, ...) and the grouping of Annex A into four
  themes (organizational, people, physical, technological; 93 controls) are not confirmed: the NIST crosswalk lists
  ids without titles, and iso.org is not readable here. [UNK: titles and themes not in S-n3ela3o4; iso.org unreadable]
- NIST CSF 2.0 (CSWP 29, published 2024-02-26) organizes its Core into six Functions: Govern, Identify, Protect,
  Detect, Respond and Recover; the csv's CSF subcategory ids and short titles come from it. [DOC S-riwffp3c]
- That Govern is the one Function added to the five of CSF 1.1. [UNK: not in S1562 as re-read 2026-09-27]
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
