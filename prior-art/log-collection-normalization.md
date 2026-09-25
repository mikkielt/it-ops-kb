---
topic: prior-art/log-collection-normalization
priority: P2
applies_to: "reading CMTrace/CCM logs and Windows event logs via ConfigMgr"
retrieved_utc: 2026-09-24
sources: [S1020, S1021]
status: partial
---

## Summary
OTel Collector and Fluent Bit are established, vendor-neutral log collection/normalization pipelines;
both support structured receivers/inputs and a plugin model for custom parsers, so a CMTrace-format
parser could be added as a custom input/receiver rather than being provided out of the box. Neither
project's fetched repository metadata documents a built-in CMTrace or CCM log parser. NXLog CE was
named in the brief but has no public GitHub repository to fetch structured metadata from (it is
distributed from nxlog.co as a closed-source-adjacent "Community Edition" binary); it is recorded as
a gap rather than fetched.

## Facts
- OpenTelemetry Collector is described in its own repository as "OpenTelemetry Collector"; licensed
  Apache-2.0, written in Go; the project's architecture (per its own naming, not fetched in depth this
  session) is receivers → processors → exporters, where a receiver ingests a given log/metric/trace
  format and a processor can transform/normalize records before export. [DOC S1020]
- Fluent Bit is described as a "Fast and Lightweight Logs, Metrics and Traces processor for Linux,
  BSD, OSX and Windows"; licensed Apache-2.0, written in C; it explicitly lists Windows as a supported
  platform, relevant to collecting Windows Event Log and CCM/CMTrace-format log files from a Windows
  device. [DOC S1021]
- Neither this session's fetch of the OpenTelemetry Collector nor Fluent Bit repository metadata
  found a named, built-in CMTrace-format parser; both projects' plugin/config models (receivers/
  inputs) are documented (at repository-description level) as extensible, which is the mechanism by
  which a CMTrace parser would be added, but no such parser ships by default per the metadata fetched. [DER S1020,S1021]
- NXLog Community Edition (nxlog.co) was named in the brief as a candidate CMTrace/Windows-event
  normalizer but has no public GitHub repository; its documentation is not on the allowed-source list
  for structured GitHub-API fetches used by this agent, so no facts were gathered about it this
  session. [UNK]

## Reference
| project | platform coverage (Windows) | licence | language | built-in CMTrace parser |
|---|---|---|---|---|
| OpenTelemetry Collector | via receivers (not confirmed Windows-log-specific this session) | Apache-2.0 | Go | not found |
| Fluent Bit | explicitly listed | Apache-2.0 | C | not found |
| NXLog CE | documented (not fetched) | UNK | UNK | UNK |

## Examples
No fixture data required.
