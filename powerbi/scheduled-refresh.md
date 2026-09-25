---
topic: powerbi/scheduled-refresh
priority: P2
applies_to: "Power BI service, docs retrieved 2026-09-23"
retrieved_utc: 2026-09-23
sources: [S900, S901, S902, S911]
status: complete
---

# Power BI scheduled refresh

## Summary
Only Import-mode (and the import part of composite) semantic models need a data refresh; DirectQuery/live connection query the source.
Scheduled refreshes per day: Pro / shared capacity 8, PPU / Premium / Fabric capacity 48 (the brief's numbers are confirmed).
Refresh must finish in 2 h on shared capacity, 5 h on Premium. Four consecutive failures disable the schedule; two months without
report views pause it.

## Facts
- Pro: up to 8 scheduled refreshes per day; PPU and Premium/Fabric capacity (F, EM, P SKUs): up to 48 per day. [DOC S901]
- Shared capacity limit is eight scheduled daily refreshes; the eight time values use the model's selected time zone; the quota resets daily at 12:01 AM local time. [DOC S900]
- The shared-capacity daily limit covers scheduled refreshes and REST API-triggered refreshes; manual "Refresh now" from the UI is not counted. [DOC S900]
- On Premium/PPU/Fabric, API refreshes have no fixed numeric limit (governed by capacity resources); with XMLA read-write, programmatic (TMSL/PowerShell) refreshes are effectively unlimited. [DOC S900]
- "Refresh more than eight times a day" is listed as a Premium feature. [DOC S911]
- Maximum refresh duration: under 2 hours on shared capacity; 5 hours on Premium; XMLA endpoint refresh can bypass the 5-hour limit. [DOC S900]
- The service aims to start within 15 minutes of the slot, may be up to one hour late, and may start up to five minutes early. [DOC S901]
- After two months with no dashboard/report views, scheduled refresh is paused and shown Disabled; the owner is emailed. [DOC S901]
- The schedule is deactivated after four consecutive failures or an unrecoverable error (for example expired credentials); the threshold cannot be changed. [DOC S901]
- There is no monthly refresh interval option. [DOC S901]
- Only Import mode semantic models require a source data refresh; DirectQuery and live connection models do not import data. [DOC S900]
- With the enterprise (standard) gateway, credentials are defined on the data source by the gateway admin, not in the model settings. [DOC S901]
- Refresh history (status, start, duration, error) is under the semantic model's Refresh > Refresh history. [DOC S901]
- A Pro workspace on shared capacity therefore gets at most 8 scheduled slots per day, i.e. one per 3 hours on average. [DER S900,S901] (8 slots / 24 h)

## Reference
| Licence / capacity | Scheduled refreshes/day | Max duration |
|---|---|---|
| Pro (shared capacity) | 8 [S901, S900] | < 2 h [S900] |
| PPU | 48 [S901] | 5 h (Premium) [S900] |
| Premium / Fabric capacity | 48 [S901] | 5 h; XMLA can bypass [S900] |

## Examples
Model `drift-status` on a Pro workspace: slots 06:00 and 18:00 (Europe/Warsaw) through the gateway connection to
`PL-SRV-0042.corp.example.com` / `driftdb` (example names).
