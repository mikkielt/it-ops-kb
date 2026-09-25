---
topic: logs/ecs-log-fields
priority: P1
applies_to: "Elastic Common Schema main @9868ff5 (version file 9.6.0-dev)"
retrieved_utc: 2026-09-24
sources: [S644, S645]
status: complete
files: [logs/ecs-log.yml]
---
# Elastic Common Schema (ECS) log.* fields

<!-- Source: elastic/ecs schemas/log.yml, Apache-2.0, (c) Elasticsearch B.V. Saved unmodified as ecs-log.yml.
     Vendor-official for Elastic; not on the PROMPT allow-list, tagged DOC as vendor documentation per coordinator. -->

## Summary
ECS `log` field set: core `log.level`, `log.logger`; extended `log.file.path`, `log.origin.file.name`,
`log.origin.file.line`, `log.origin.function`, and `log.syslog.*` (severity, facility, priority, version, hostname,
appname, procid, msgid, structured_data). Pinned YAML: `ecs-log.yml`. Licence Apache-2.0.

## Facts
- `log.level` keyword, core: log level of the event. [DOC S644]
- `log.logger` keyword, core: name of the logger. [DOC S644]
- `log.file.path` keyword, extended: full path to the log file the event came from. [DOC S644]
- `log.origin.file.name` keyword, `log.origin.file.line` long, `log.origin.function` keyword; extended: code origin. [DOC S644]
- `log.syslog` object with `severity.code` (long), `severity.name`, `facility.code` (long), `facility.name`, `priority` (long), `version`, `hostname`, `appname`, `procid`, `msgid` (keyword), `structured_data` (flattened). [DOC S644]
- Repository licence: Apache License 2.0. [DOC S645]
- Base fields (`@timestamp`, `message`) and `event.*` were not fetched. [UNK]

## Reference
| ECS | OTel equivalent (by meaning; DER) |
|---|---|
| log.level | SeverityText [DER S644,S639] |
| log.file.path | log.file.path [DER S644,S640] |
| log.origin.file.name | code.file.path [DER S644,S641] |
| log.origin.file.line | code.line.number [DER S644,S641] |
| log.origin.function | code.function.name [DER S644,S641] |

## Examples
`{"log": {"level": "error", "file": {"path": "C:\\Windows\\CCM\\Logs\\CcmExec.log"}}, "host": {"name": "PL-LT-00123"}}`
