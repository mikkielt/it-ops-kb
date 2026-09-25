---
topic: logs/otel-collector-receivers
priority: P3
applies_to: "opentelemetry-collector-contrib v0.161.0 (released 2026-09-15)"
retrieved_utc: 2026-09-25
sources: [S960, S961, S962, S963, S964]
status: complete
files: [logs/otel-filelogreceiver.config.csv, logs/otel-windowseventlogreceiver.config.csv, logs/otel-filelogreceiver.metadata.yaml, logs/otel-windowseventlogreceiver.metadata.yaml]
---

# OpenTelemetry Collector: filelog and windowseventlog receivers

## Summary
Both receivers ship in the contrib distribution (filelog also in k8s). In v0.161.0 their component types were renamed:
`file_log` (deprecated alias `filelog`, stability **beta** for logs) and `windows_event_log` (deprecated alias `windowseventlog`,
stability **alpha**, Windows only). Full option tables are saved as CSV beside this file; `metadata.yaml` files are saved verbatim.

## Facts
- Latest contrib release at retrieval: `v0.161.0`, published 2026-09-15. [DOC S960]
- File log receiver: type `file_log`, deprecated type `filelog`, stability beta (logs), distributions contrib and k8s. [DOC S962]
- Windows Event Log receiver: type `windows_event_log`, deprecated type `windowseventlog`, stability alpha (logs), distribution contrib, unsupported on darwin and linux. [DOC S964]
- The deprecated type `windowseventlog` is still accepted in configuration. [DOC S963]
- filelog: `include` (glob list) is required; `start_at` defaults to `end`, so by default nothing is read from a file that is not being written to. [DOC S961]
- filelog: `include_file_name` defaults true (`log.file.name`); `include_file_path` defaults false (`log.file.path`); owner/group/permission attributes are not supported on Windows. [DOC S961]
- filelog: `encoding` default `utf-8`; also `utf-16le`, `utf-16be`, `ascii`, `nop`, `utf-8-raw`, `big5`. [DOC S961]
- filelog: `poll_interval` 200ms; `fingerprint_size` 1000 bytes (min 16); `max_log_size` 1MiB with `max_log_size_behavior` split|truncate; `max_concurrent_files` 1024. [DOC S961]
- filelog: `multiline` needs exactly one of `line_start_pattern` / `line_end_pattern`. [DOC S961]
- filelog: supports move/create and copy/truncate rotation, tracking files by identity and fingerprint; `on_truncate` ignore|read_whole_file|read_new. [DOC S961]
- filelog: `storage` (storage extension id) persists file offsets across restarts; without it offsets are in memory only. [DOC S961]
- filelog: feature gate `filelog.windows.caseInsensitive` (beta, from v0.142.0) makes include/exclude matching case-insensitive on Windows. [DOC S961]
- windowseventlog: `channel` required; `start_at` default `end`; `poll_interval` 1s; `max_reads` 100; `raw` false (structured body) or true (XML string). [DOC S963]
- windowseventlog: `query` takes an XML event query (Windows Query Schema); `path` reads an EVTX archive file; `exclude_providers` filters providers. [DOC S963]
- windowseventlog: `storage` persists bookmarks across restarts; otherwise bookmarks are in memory. [DOC S963]
- windowseventlog: `remote` (server, username, password, optional domain) reads from a remote machine; `discover_domain_controllers` (feature gate `domainControllers.autodiscovery`, alpha, from v0.150.0). [DOC S963, S964]
- windowseventlog: `resolve_sids.enabled` (default false) resolves SIDs via LSA with an LRU cache (10000 entries, 15m TTL). [DOC S963]
- windowseventlog: `event_driven_scraping` (default false, experimental; same as feature gate `stanza.windows.eventDrivenScraping`, alpha) wakes on Windows API signals; `wait_timeout` 5s safety-net poll. [DOC S963]
- windowseventlog: `ignore_channel_errors` false by default, so failing to open a channel stops the collector unless set true. [DOC S963]
- Both: `retry_on_failure` (disabled by default; 1s initial, 30s max interval, 5m max elapsed; `0` = retry forever; then data is discarded). [DOC S961, S963]

## Reference
- `otel-filelogreceiver.config.csv` (51 fields), `otel-windowseventlogreceiver.config.csv` (29 fields): field, default, description (Apache-2.0, from the README at v0.161.0).
- `otel-filelogreceiver.metadata.yaml`, `otel-windowseventlogreceiver.metadata.yaml`: verbatim, Apache-2.0, © OpenTelemetry Authors.

## Examples
```yaml
receivers:
  file_log/ccm:
    include: ['C:\Windows\CCM\Logs\*.log']
    start_at: beginning
    encoding: utf-8
    include_file_path: true
    storage: file_storage
  windows_event_log/dsc:
    channel: Microsoft-Windows-DSC/Operational
    start_at: end
    storage: file_storage
```
(host PL-LT-00123; paths/channels illustrative — see `logs/sources.csv` for verified channel names.)
