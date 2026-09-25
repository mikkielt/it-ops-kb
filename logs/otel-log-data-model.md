---
topic: logs/otel-log-data-model
priority: P1
applies_to: "OpenTelemetry specification (main, CHANGELOG top v1.61.0 2026-09-14), Logs Data Model status Stable"
retrieved_utc: 2026-09-25
sources: [S639]
status: complete
---
# OpenTelemetry Logs Data Model

<!-- Content summarised from open-telemetry/opentelemetry-specification, Apache-2.0, (c) OpenTelemetry Authors. -->

## Summary
Stable data model: a LogRecord has 12 top-level fields (Timestamp, ObservedTimestamp, TraceId, SpanId, TraceFlags,
SeverityText, SeverityNumber, Body, Resource, InstrumentationScope, Attributes, EventName). SeverityNumber 1-24 in six
ranges (TRACE..FATAL), 0 = unspecified. A record with non-empty EventName is an Event.

## Facts
- Logs Data Model status: Stable. [DOC S639]
- Timestamp: uint64 nanoseconds since UNIX epoch, time at source, optional. [DOC S639]
- ObservedTimestamp: when the collection system observed the event; SHOULD be set once observed. [DOC S639]
- SeverityNumber ranges: 1-4 TRACE, 5-8 DEBUG, 9-12 INFO, 13-16 WARN, 17-20 ERROR, 21-24 FATAL; 0 MAY mean unspecified. [DOC S639]
- Mapping rule: a source level that alone matches a range should take the smallest value of the range (e.g. Informational → 9); several levels in a range are spread by importance (Error → 17, Critical → 18). [DOC S639]
- Body: AnyValue (string or structured), optional. [DOC S639]
- Resource: describes the source; may be recorded once per batch. InstrumentationScope: the emitting scope. [DOC S639]
- Attributes: per-occurrence data; exception details MUST follow the exception semantic conventions if included. [DOC S639]
- EventName: string identifying the event class; SHOULD uniquely identify the event structure. [DOC S639]

## Reference
| Field | Type | Note [S639] |
|---|---|---|
| Timestamp | uint64 ns | optional |
| ObservedTimestamp | uint64 ns | set when observed |
| TraceId / SpanId / TraceFlags | bytes / W3C flags | trace context |
| SeverityText | string | original level text |
| SeverityNumber | number 0-24 | normalised |
| Body | AnyValue | message |
| Resource | Resource | source entity |
| InstrumentationScope | scope | emitter |
| Attributes | map | per event |
| EventName | string | event class |

## Examples
CMTrace line from `PL-LT-00123` mapped: Timestamp = time in the log line, ObservedTimestamp = collection time, SeverityNumber 17 for CMTrace type 3 (error) — the CMTrace-to-severity mapping is an example, not an official mapping.
