---
topic: prior-art/device-identity-correlation
priority: P2
applies_to: "one device record across AD/Entra/Intune/Autopilot/ConfigMgr/Defender"
retrieved_utc: 2026-09-24
sources: [S1011, S1012, S1013, S1014]
status: partial
---

## Summary
GLPI, Snipe-IT, NetBox and Fleet are open-source inventory/CMDB tools; each keeps one canonical
record per asset/device and exposes an API others can key off, but none of their public docs were
fetched deeply enough this session to extract explicit "merge key / precedence / duplicate handling"
rules comparable to ServiceNow's Identification and Reconciliation Engine (IRE), which is the
canonical public documentation of that pattern but was not fetched this session (ServiceNow docs are
not in the allowed-source list for this agent's `tget` budget — flagged as a gap). Facts below are
limited to what each project's repository metadata states about its own scope and licence.

## Facts
- GLPI ("GLPI is a Free Asset and IT Management Software package, Data center management, ITIL
  Service Desk, licenses tracking and software auditing") is GPL-3.0 licensed, written in PHP, and
  bundles both an asset/CMDB module and an ITIL service-desk module in one application. [DOC S1011]
- Snipe-IT (current org `grokability/snipe-it`, formerly `snipe/snipe-it`) is described as "a free
  open source IT asset/license management system," AGPL-3.0 licensed, written in PHP; it is scoped to
  asset/licence tracking rather than network or service-topology modeling. [DOC S1012]
- NetBox describes itself as "the premier source of truth powering network automation," Apache-2.0
  licensed, written in Python; its documented scope is IP address management (IPAM) and data-center
  infrastructure management (DCIM) — device records there are primarily network/rack/interface
  centric, not endpoint-management centric. [DOC S1013]
- Fleet ("Open device management") is licensed under a source-available licence the GitHub API
  reports as unrecognised ("NOASSERTION" — Fleet's actual terms mix an Elastic-License-2.0-derived
  core with an MIT-licensed osquery-facing agent per its own repository, not independently confirmed
  this session); written in Go; scoped to endpoint (osquery-based) device management with its own
  device inventory API. [DOC S1014]
- None of GLPI, Snipe-IT, NetBox or Fleet's fetched repository metadata documents a cross-source
  "merge key" or duplicate-resolution precedence algorithm comparable to ServiceNow CMDB's IRE
  (identification rules ranked by precedence, independent vs. dependent CI attributes); that
  documentation was not retrieved this session. [UNK]

## Reference
| project | primary domain | licence | language |
|---|---|---|---|
| GLPI | IT asset + ITIL service desk | GPL-3.0 | PHP |
| Snipe-IT | asset/licence tracking | AGPL-3.0 | PHP |
| NetBox | IPAM/DCIM network source of truth | Apache-2.0 | Python |
| Fleet | endpoint/device management (osquery-based) | source-available (not independently confirmed) | Go |

## Examples
No fixture data required (mechanism-only facts).
