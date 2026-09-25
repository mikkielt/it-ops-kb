---
topic: logs/otel-log-semconv
priority: P1
applies_to: "OpenTelemetry semantic conventions main @838e414 (CHANGELOG top v1.44.0)"
retrieved_utc: 2026-09-25
sources: [S640, S641, S642, S643, S646]
status: complete
files: [logs/otel-semconv-log-registry.yaml, logs/otel-semconv-code-registry.yaml]
---
# OpenTelemetry log semantic conventions (log.*, code.*, exception.*)

<!-- Summarised from open-telemetry/semantic-conventions, Apache-2.0, (c) OpenTelemetry Authors.
     Verbatim registry YAML saved beside this file: otel-semconv-log-registry.yaml, otel-semconv-code-registry.yaml (unmodified bytes; licence Apache-2.0, attribution as above). -->

## Summary
`log.*` attributes (all **Development**): log.iostream, log.file.name/.name_resolved/.path/.path_resolved,
log.record.original, log.record.uid. `code.*` (all **Stable**): code.file.path, code.line.number, code.column.number,
code.function.name, code.stacktrace; older code.filepath/lineno/column/function/namespace are deprecated.

## Facts
- `log.iostream` string, values stdout / stderr; Development. [DOC S640]
- `log.file.name` basename of the file the record was emitted to (e.g. `audit.log`); `log.file.path` full path; `*_resolved` variants resolve symlinks; all Development. [DOC S640]
- `log.record.original`: complete original record; MAY be added when the Body doesn't hold the same value (e.g. syslog, file read). [DOC S640]
- `log.record.uid`: records with the same ID are duplicates and can be removed; distinct records MUST have different values. [DOC S640]
- `code.file.path` (string), `code.line.number` (int), `code.column.number` (int), `code.function.name` (fully-qualified, no arguments), `code.stacktrace` (string); Stable; MUST NOT be used on the Profile signal. [DOC S641]
- Deprecated: `code.column`→`code.column.number`, `code.filepath`→`code.file.path`, `code.lineno`→`code.line.number`, `code.function` and `code.namespace`→ folded into `code.function.name`. [DOC S641]
- Exceptions in logs: `exception.message` and `exception.type` Conditionally Required, `exception.stacktrace` Recommended; all Stable. [DOC S646]

## Reference
| Attribute | Type | Stability |
|---|---|---|
| log.iostream | enum string | Development |
| log.file.name / .name_resolved | string | Development |
| log.file.path / .path_resolved | string | Development |
| log.record.original | string | Development |
| log.record.uid | string | Development |
| code.file.path | string | Stable |
| code.line.number / code.column.number | int | Stable |
| code.function.name | string | Stable |
| code.stacktrace | string | Stable |

## Examples
Record read from `C:\Windows\CCM\Logs\CcmExec.log` on `PL-LT-00123`: `log.file.name = "CcmExec.log"`, `log.file.path = "C:\\Windows\\CCM\\Logs\\CcmExec.log"`.
