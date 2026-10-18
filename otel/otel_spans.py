"""otel_spans: send the spans of `kbmon.py --events` as OTLP spans through the OpenTelemetry SDK.

Used by kbmon_otel.py. Each span of kbmon's `--events` object (`{name, id, trace, parent?, start, end, status, attributes}`)
becomes one SDK span with the ids kbmon gave it (so a span sent twice has the same id), its start and end time (Unix
nanoseconds), its attributes and an error status when kbmon's `status` is `error`. A span with a `parent` is created in the
context of that parent, so a landing's steps are children of the landing's span in its trace. The endpoint and the headers
are the SDK exporter's own (OTEL_EXPORTER_OTLP_TRACES_ENDPOINT or OTEL_EXPORTER_OTLP_ENDPOINT, which gets `v1/traces`
appended). Docs: kb/_self/monitoring.md.
"""

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.id_generator import IdGenerator
from opentelemetry.trace import NonRecordingSpan, SpanContext, Status, StatusCode, TraceFlags

QUEUE = 8192  # more than one round holds (1000 coord events and 4000 ops rows on the first), so none is dropped
FLUSH_MS = 30_000


class Exporter(OTLPSpanExporter):
    """The SDK's OTLP/HTTP span exporter, remembering whether every export since the last reset worked."""

    ok = True

    def export(self, spans):
        result = super().export(spans)
        if result.name != "SUCCESS":
            self.ok = False
        return result


class GivenIds(IdGenerator):
    """Ids the caller sets before a span is made, so a span keeps the id kbmon gave it."""

    trace_id = span_id = 1

    def generate_span_id(self) -> int:
        return self.span_id

    def generate_trace_id(self) -> int:
        return self.trace_id


def hex_id(value) -> int:
    """The integer of a hex id, 0 (an invalid id) for anything else."""
    try:
        return int(str(value), 16)
    except ValueError:
        return 0


class Spans:
    """One tracer provider that lives across rounds."""

    def __init__(self, resource):
        self.ids = GivenIds()
        self.exporter = Exporter()
        self.provider = TracerProvider(resource=resource, id_generator=self.ids, shutdown_on_exit=False)
        self.provider.add_span_processor(
            BatchSpanProcessor(self.exporter, schedule_delay_millis=FLUSH_MS, max_queue_size=QUEUE,
                               max_export_batch_size=QUEUE))
        self.tracer = self.provider.get_tracer("kbmon")

    def make(self, item: dict) -> bool:
        """Send one kbmon span; False when it lacks a name, ids or times."""
        name, start, end = item.get("name"), item.get("start"), item.get("end")
        span_id, trace_id = hex_id(item.get("id")), hex_id(item.get("trace"))
        if not (isinstance(name, str) and span_id and trace_id and isinstance(start, int) and isinstance(end, int)):
            return False
        self.ids.span_id, self.ids.trace_id = span_id, trace_id
        context = None
        parent = hex_id(item.get("parent"))
        if parent:
            context = trace.set_span_in_context(NonRecordingSpan(
                SpanContext(trace_id=trace_id, span_id=parent, is_remote=False, trace_flags=TraceFlags(1))))
        span = self.tracer.start_span(name, context=context, start_time=start, attributes=item.get("attributes") or {})
        span.set_status(Status(StatusCode.ERROR if item.get("status") == "error" else StatusCode.OK))
        span.end(end_time=end)
        return True

    def send(self, snapshot: dict) -> bool:
        """Send the spans of one `--events` object; True when every one was exported."""
        self.exporter.ok = True
        for item in snapshot.get("spans", []):
            if isinstance(item, dict):
                self.make(item)
        flushed = self.provider.force_flush(FLUSH_MS)
        return bool(flushed and self.exporter.ok)

    def close(self):
        self.provider.shutdown()
        self.exporter.shutdown()
