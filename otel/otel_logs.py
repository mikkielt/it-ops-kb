"""otel_logs: send the records of `kbmon.py --events` as OTLP log records through the OpenTelemetry SDK.

Used by kbmon_otel.py. Each event of kbmon's `--events` object (`{name, time, attributes, severity?}`) becomes one log
record: `name` is the record's event name, `time` its timestamp (Unix nanoseconds) and `attributes` its attributes, which
kbmon already limited to numbers, flags and identifiers. The record has no body. The endpoint and the headers are the
SDK exporter's own (OTEL_EXPORTER_OTLP_LOGS_ENDPOINT or OTEL_EXPORTER_OTLP_ENDPOINT, which gets `v1/logs` appended).
The cursor is kept in memory between rounds, so a round gives back only what is newer than the last one that was sent.
Docs: kb/_self/monitoring.md.
"""

from opentelemetry._logs import SeverityNumber
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

QUEUE = 8192  # more than one round holds (1000 coord events and 4000 ops rows on the first), so none is dropped
FLUSH_MS = 30_000


class Exporter(OTLPLogExporter):
    """The SDK's OTLP/HTTP log exporter, remembering whether every export since the last reset worked."""

    ok = True

    def export(self, batch):
        result = super().export(batch)
        if result.name != "SUCCESS":
            self.ok = False
        return result


def severity(event: dict):
    """(number, text) of an event: WARN for severity `warn`, else INFO."""
    if event.get("severity") == "warn":
        return SeverityNumber.WARN, "WARN"
    return SeverityNumber.INFO, "INFO"


class Logs:
    """One logger provider that lives across rounds, and the cursor of the events already sent."""

    def __init__(self, resource):
        self.cursor = None
        self.exporter = Exporter()
        self.provider = LoggerProvider(resource=resource, shutdown_on_exit=False)
        self.provider.add_log_record_processor(
            BatchLogRecordProcessor(self.exporter, schedule_delay_millis=FLUSH_MS, max_queue_size=QUEUE))
        self.logger = self.provider.get_logger("kbmon")

    def send(self, snapshot: dict) -> bool:
        """Send the events of one `--events` object; the cursor moves to its cursor only when every record was sent."""
        events = [e for e in snapshot.get("events", []) if isinstance(e, dict) and isinstance(e.get("name"), str)]
        self.exporter.ok = True
        for event in events:
            number, text = severity(event)
            self.logger.emit(timestamp=event.get("time"), severity_number=number, severity_text=text,
                             attributes=event.get("attributes") or {}, event_name=event["name"])
        flushed = self.provider.force_flush(FLUSH_MS)
        if not (flushed and self.exporter.ok):
            return False
        self.cursor = snapshot.get("cursor") or self.cursor
        return True

    def close(self):
        self.provider.shutdown()
        self.exporter.shutdown()
