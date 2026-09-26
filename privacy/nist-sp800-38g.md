---
topic: privacy/nist-sp800-38g
priority: P0
applies_to: "NIST SP 800-38G (2016, updated 2016-08-04) and SP 800-38G Rev. 1 drafts"
retrieved_utc: 2026-09-23
sources: [S865, S866, S867, S868, S869]
status: complete
---
# NIST SP 800-38G (format-preserving encryption) status

## Summary
- **SP 800-38G Rev. 1 is still a draft.** The second public draft was published 2025-02-03, and its comments closed 2025-04-04. There is no final Rev. 1 page (404).
- The current final is SP 800-38G of March 2016, updated 2016-08-04. It specifies FF1 and FF3.
- The Rev. 1 drafts change the FF3 story. The first draft (2019) specified FF1 and **FF3-1**. The second draft (2025) **drops FF3 entirely**, keeps FF1 with a larger minimum domain size, and bans floating-point arithmetic in FF1 implementations.

## Facts
- SP 800-38G (03/29/2016) is marked "Withdrawn on August 04, 2016" and superseded by SP 800-38G `upd1`. [DOC S865]
- The current SP 800-38G page: "Date Published: March 2016 (Updated August 4, 2016)". It specifies FF1 and FF3, and has a planning note (2019-02-28) about the draft revision. [DOC S866]
- Rev. 1 initial public draft: published February 2019, comments due 2019-04-15 (closed). It specifies FF1 and FF3-1, updated for small domain sizes. The page marks it obsoleted on 2025-02-03 by the second public draft. [DOC S867]
- Rev. 1 second public draft: published 2025-02-03, comments due 2025-04-04 (closed). Authors Dworkin and Mouha. [DOC S868]
- 2PD changes: larger FF1 domain size; FF3 no longer specified; the inverse AES function may no longer be CIPH; floating-point arithmetic is disallowed in FF1. [DOC S868]
- Document history for Rev. 1: 02/28/19 draft, 02/03/25 draft. No final entry. [DOC S868]
- `https://csrc.nist.gov/pubs/sp/800/38/g/r1/final` returned HTTP 404 on 2026-09-23 and again on 2026-09-26. [DOC S869]
- No final SP 800-38G Rev. 1 had been published by 2026-09-26. [DER S868,S869: history ends with the 2025 draft; the final URL is 404]
- The FF3-1 method appears only in the 2019 draft. It is not in the current final (FF3) and not in the 2025 draft. [DER S866,S867,S868]

## Reference
| Document | Status | Date | Methods |
|---|---|---|---|
| SP 800-38G (orig.) | Withdrawn | 2016-03-29 → 2016-08-04 | FF1, FF3 |
| SP 800-38G (upd1) | Final (current) | 2016-08-04 | FF1, FF3 |
| SP 800-38G Rev. 1 ipd | Draft, obsoleted by 2pd 2025-02-03 | 2019-02 | FF1, FF3-1 |
| SP 800-38G Rev. 1 2pd | Draft (closed) | 2025-02-03 | FF1 only |

## Examples
Not applicable.
