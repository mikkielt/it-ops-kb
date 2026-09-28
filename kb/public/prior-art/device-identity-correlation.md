---
topic: prior-art/device-identity-correlation
priority: P2
applies_to: "one device record across AD/Entra/Intune/Autopilot/ConfigMgr/Defender"
retrieved_utc: 2026-09-28
sources: [S1011, S1012, S1013, S1014, S-awv4qk3v, S-53yzqgkc, S-y47upe33]
status: complete
---

## Summary
GLPI, Snipe-IT, NetBox and Fleet are open-source inventory/CMDB tools; each keeps one canonical
record per asset/device and exposes an API others can key off. GLPI documents an ordered, first-match
import-and-link rule list (serial, name, domain, IP and inventory-tool fields) and Fleet one
configurable host-identity key (`uuid` recommended); neither documents a ranked multi-key precedence
like ServiceNow's Identification and Reconciliation Engine (IRE), which was not fetched.

## Facts
- GLPI ("GLPI is a Free Asset and IT Management Software package, Data center management, ITIL
  Service Desk, licenses tracking and software auditing") is GPL-3.0 licensed, written in PHP, and
  bundles both an asset/CMDB module and an ITIL service-desk module in one application. [DOC S1011]
- Snipe-IT (current org `grokability/snipe-it`, formerly `snipe/snipe-it`) is described as "a free
  open source IT asset/license management system," AGPL-3.0 licensed, written in PHP; its README scopes it to IT
  asset management (who has which laptop, purchase dates for depreciation, software licences). [DOC S1012]
- NetBox describes itself as "the premier source of truth powering network automation," Apache-2.0
  licensed, written in Python; its README presents it as a successor to IPAM and DCIM applications,
  built for modeling network infrastructure (racks, devices, cables, IP addresses, VLANs, circuits), so
  device records there are network centric, not endpoint-management centric. [DOC S1013]
- Fleet ("Open device management") is written in Go and scoped to endpoint (osquery-based) device management with its own device inventory API; the GitHub API reports its licence as unrecognised ("NOASSERTION"). [DOC S1014]
- Fleet's `LICENSE` puts the repository under MIT except `docs/` (CC BY-SA 4.0), `ee/` (its own licence in `ee/LICENSE`) and third-party components (their own licences); client-side JavaScript is MIT. [DOC S-y47upe33]
- GLPI passes each inventoried computer through an entity-assignment engine and then an import-and-link engine whose rules either import it into its entity, link it to a computer already in GLPI, or refuse it. Criteria include name, serial number, domain, IP address, subnet and inventory-tool fields; the engine stops at the first matching rule, and the search for an existing machine covers only the destination entity. [DOC S-awv4qk3v]
- Fleet decides host uniqueness with `osquery_host_identifier`: `provided` (default, the identifier osquery sends), `uuid`, `hostname` or `instance`; the docs call `uuid` the best option in most deployments, and `osquery_enroll_cooldown` rate-limits re-enrolment of hosts that share one identifier. [DOC S-53yzqgkc]
- So GLPI documents an ordered, first-match rule list over several keys and Fleet a single configurable identity key; neither documents a ranked multi-key precedence with independent and dependent attributes like ServiceNow's IRE. Snipe-IT and NetBox were not found to document one either. [DER S-awv4qk3v, S-53yzqgkc, S1012, S1013: compared against the IRE design]

## Reference
| project | primary domain | licence | language |
|---|---|---|---|
| GLPI | IT asset + ITIL service desk | GPL-3.0 | PHP |
| Snipe-IT | asset/licence tracking | AGPL-3.0 | PHP |
| NetBox | IPAM/DCIM network source of truth | Apache-2.0 | Python |
| Fleet | endpoint/device management (osquery-based) | source-available (not independently confirmed) | Go |

## Examples
No fixture data required (mechanism-only facts).
