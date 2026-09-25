---
topic: reuse/device-identity-correlation
priority: P2
applies_to: "a cross-plane device identity graph: merge keys, stale thresholds, temporal history"
retrieved_utc: 2026-09-24
sources: [S1011, S1012, S1013, S1014, S1105]
status: complete
---

## Summary
All four surveyed CMDB/asset/inventory tools are a `no` for reuse into a device-identity merge problem.
Two are wrong domain (NetBox: IPAM/DCIM; GLPI/Snipe-IT: ITSM/asset-licence tracking, not a multi-plane
Windows identity merge), and none of the four documents a merge-key/precedence algorithm at the depth
fetched that would add anything beyond a hand-specified table (strong keys: Entra `deviceId`, AD SID,
Intune id, ZTDID; medium: serial with OEM-junk rejection; hostname never merges). GLPI and Snipe-IT are
also copyleft-licensed (GPL-3.0, AGPL-3.0), so even a documented algorithm could only be read, not
copied.

## Facts
- GLPI (GPL-3.0, PHP) and Snipe-IT (AGPL-3.0, PHP) are both licensed such that no source may be copied
  regardless of fit; their scope (ITIL service desk / asset-licence tracking) does not overlap with a
  cross-plane device merge problem either. [DOC S1011,S1012]
- NetBox (Apache-2.0, Python) would permit copying by licence, but its documented scope is IPAM/DCIM
  (IP addresses, racks, interfaces) -- a different data model from a device-centric merge across
  AD/Entra/Intune/Autopilot/ConfigMgr/Defender. [DOC S1013]
- Fleet's core is confirmed MIT by direct fetch of its repository `LICENSE` (docs under CC BY-SA 4.0,
  the `ee/` directory under a separate licence, client JS under MIT Expat) -- resolving a prior
  "NOASSERTION" flag for the MIT-licensed core specifically. Licence would permit copying the core, but
  Fleet is a full client+server service (osquery-based endpoint management), and running or embedding
  it would add an always-on service, which a no-always-on-service constraint would forbid; no
  Fleet-specific merge-key algorithm was found documented at the depth fetched either. [DOC S1105]
- None of the four projects' fetched documentation states an explicit merge-key precedence or
  duplicate-resolution algorithm comparable to a hand-specified table (strong keys merge, serial is
  medium-confidence with OEM-duplicate rejection, hostname never merges) -- there is nothing here to
  borrow as either logic or pattern beyond such a table. [DER S1011,S1012,S1013,S1105]

## Reference
| project | domain | licence | copying permitted | reuse verdict |
|---|---|---|---|---|
| GLPI | ITSM/asset | GPL-3.0 | no | no |
| Snipe-IT | asset/licence tracking | AGPL-3.0 | no | no |
| NetBox | IPAM/DCIM | Apache-2.0 | yes | no (wrong domain) |
| Fleet | endpoint device mgmt (core) | MIT (core; confirmed) | yes | no (always-on service) |

## Examples
No fixture data required (mechanism-only facts).
