---
topic: reuse/log-collection-normalization
priority: P2
applies_to: "reading and normalizing CMTrace/CCM/event logs from an on-workstation search/tail/collect tool"
retrieved_utc: 2026-09-24
sources: [S1020, S1021]
status: complete
---

## Summary
Both OpenTelemetry Collector and Fluent Bit are `no` for direct reuse: their deployment model is an
always-on collector process/service, which a no-always-on-service constraint (CLI + stdio MCP only)
would forbid, and neither ships a built-in CMTrace parser. Log fetch/normalize is better kept as inline
library code invoked per-call, not a piped collector.

## Facts
- OpenTelemetry Collector (Apache-2.0, Go) uses a receivers -> processors -> exporters architecture
  that is, by its own naming, extensible via custom receivers/processors -- the mechanism by which a
  CMTrace parser would be added, but no such parser ships by default. Deploying it means running a
  standing collector process, not calling a library. [DOC S1020]
- Fluent Bit (Apache-2.0, C) explicitly lists Windows as a supported platform and is similarly
  extensible via inputs/parsers, but likewise ships no built-in CMTrace parser and is deployed as a
  standing process. [DOC S1021]
- Both licences (Apache-2.0) would permit copying a parser design if one existed, but neither project
  documents one at the depth fetched, and the deployment model (always-on collector) does not match a
  per-call, on-workstation execution model regardless. [DER S1020,S1021]

## Reference
| project | Windows support | built-in CMTrace parser | licence | reuse verdict |
|---|---|---|---|---|
| OpenTelemetry Collector | via receivers (not confirmed log-specific) | none found | Apache-2.0 | no (always-on service model) |
| Fluent Bit | explicit | none found | Apache-2.0 | no (same) |

## Examples
No fixture data required (mechanism-only facts).
