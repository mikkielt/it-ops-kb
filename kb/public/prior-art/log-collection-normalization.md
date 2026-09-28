---
topic: prior-art/log-collection-normalization
priority: P2
applies_to: "reading CMTrace/CCM logs and Windows event logs via ConfigMgr"
retrieved_utc: 2026-09-28
sources: [S1020, S1021, S-5ub6genn, S-unpitz6t, S-mblcg5ds, S-d7pjd3ma, S-4wx4xn7t, S-7z56t65g]
status: complete
---

## Summary
OTel Collector and Fluent Bit are established, vendor-neutral log collection/normalization pipelines;
both support structured receivers/inputs and a plugin model for custom parsers, so a CMTrace-format
parser could be added as a custom input/receiver rather than being provided out of the box. Neither
repository tree contains a CMTrace or CCM log parser; both ship Windows Event Log inputs. NXLog CE's
reference manual (v3.2) documents Windows Event Log input modules but no CMTrace parser either.

## Facts
- OpenTelemetry Collector is described in its own repository as a vendor-agnostic way to receive,
  process and export telemetry data; licensed Apache-2.0, written in Go. Each pipeline is a set of
  receivers that collect the data, optional processors that take the data from the receivers and process
  it, and exporters that send it on. [DOC S1020, S-5ub6genn]
- Fluent Bit is described as a "Fast and Lightweight Logs, Metrics and Traces processor for Linux,
  BSD, OSX and Windows"; licensed Apache-2.0, written in C; it explicitly lists Windows as a supported
  platform, relevant to collecting Windows Event Log and CCM/CMTrace-format log files from a Windows
  device. [DOC S1021]
- Neither this session's fetch of the OpenTelemetry Collector nor Fluent Bit repository metadata
  found a named, built-in CMTrace-format parser; both projects' plugin/config models (receivers/
  inputs) are documented (at repository-description level) as extensible, which is the mechanism by
  which a CMTrace parser would be added, but no such parser ships by default per the metadata fetched. [DER S1020,S1021]
- OpenTelemetry Collector contrib ships a Windows Event Log receiver (`windowseventlogreceiver`) and Fluent Bit a Windows Event Log input (`in_winevtlog`, beside `in_winlog`). [CODE S-4wx4xn7t: receiver/windowseventlogreceiver/factory.go#NewFactory; CODE S-7z56t65g: plugins/in_winevtlog/in_winevtlog.c#in_winevtlog_plugin]
- The contrib stanza parsers at that commit are `container`, `csv`, `jsonarray`, `jsonparser`, `keyvalue`, `regex`, `scope`, `severity`, `syslog`, `timeparser`, `trace` and `uri`; Fluent Bit has `in_tail` and a `filter_parser` for custom formats. [DER S-unpitz6t, S-mblcg5ds: directory listings of the repository trees]
- No path in either repository tree mentions CMTrace, so a CMTrace line needs a custom `regex_parser` operator (OpenTelemetry) or a parser definition for `filter_parser`/`in_tail` (Fluent Bit). [DER S-unpitz6t, S-mblcg5ds: case-insensitive search of the full, untruncated trees]
- The NXLog Community Edition Reference Manual (v3.2, April 2023) documents `im_msvistalog` for the Windows Vista and later Event Log API (and `im_mseventlog` for XP/2003), plus extension modules such as `xm_multiline`, `xm_json` and `xm_kvp`; its module list names no CMTrace parser. [DOC S-d7pjd3ma]

## Reference
| project | platform coverage (Windows) | licence | language | built-in CMTrace parser |
|---|---|---|---|---|
| OpenTelemetry Collector | via receivers (not confirmed Windows-log-specific this session) | Apache-2.0 | Go | not found |
| Fluent Bit | explicitly listed | Apache-2.0 | C | not found |
| NXLog CE | documented (not fetched) | UNK | UNK | UNK |

## Examples
No fixture data required.
