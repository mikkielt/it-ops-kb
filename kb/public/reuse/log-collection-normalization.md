---
topic: reuse/log-collection-normalization
priority: P2
applies_to: "reading and normalizing CMTrace/CCM/event logs from an on-workstation search/tail/collect tool"
retrieved_utc: 2026-09-28
sources: [S1020, S1021, S-5ub6genn, S-knqivzgt, S-unpitz6t, S-mblcg5ds]
status: complete
---

## Summary
Both OpenTelemetry Collector and Fluent Bit are `no` for direct reuse: their deployment model is an
always-on collector process/service, which a no-always-on-service constraint (CLI + stdio MCP only)
would forbid, and neither ships a built-in CMTrace parser. Log fetch/normalize is better kept as inline
library code invoked per-call, not a piped collector.

## Facts
- OpenTelemetry Collector is Apache-2.0 licensed. [DOC S1020]
- The Collector is an executable whose pipelines chain receivers, optional processors and exporters;
  the docs cover building custom components, the mechanism by which a CMTrace parser would be added,
  and as an agent it runs as a daemon on the VM or container -- a standing process, not a library
  call. [DOC S-5ub6genn]
- Fluent Bit (Apache-2.0) is a telemetry agent for Linux, Windows, macOS, BSD and embedded systems,
  with pluggable input, filter and output plugins (plugins written in C). [DOC S-knqivzgt]
- The GitHub API metadata for `fluent/fluent-bit` gives licence Apache-2.0, primary language C and the description "Fast and Lightweight Logs, Metrics and Traces processor for Linux, BSD, OSX and Windows"; the repository is not archived. [DOC S1021]
- Neither OpenTelemetry Collector contrib nor Fluent Bit ships a CMTrace parser: no path in either full repository tree mentions CMTrace at the pinned commits. [DER S-unpitz6t, S-mblcg5ds: case-insensitive search of the untruncated trees]
- Both licences (Apache-2.0) would permit copying a parser design if one existed, but the deployment
  model (a standing agent or collector) does not match a per-call, on-workstation execution model
  regardless. [DER S-5ub6genn, S-knqivzgt: both are described as agents or executables that run continuously]

## Reference
| project | Windows support | built-in CMTrace parser | licence | reuse verdict |
|---|---|---|---|---|
| OpenTelemetry Collector | via receivers (not confirmed log-specific) | none found | Apache-2.0 | no (always-on service model) |
| Fluent Bit | explicit | none found | Apache-2.0 | no (same) |

## Examples
No fixture data required (mechanism-only facts).
