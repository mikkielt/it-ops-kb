"""kbmon_otel: send kbmon's metric points, event records and spans over OTLP/HTTP with the OpenTelemetry Python SDK.

Run it from the clone's root, with the SDK pinned in otel/uv.lock:

    uv run --frozen --project otel python otel/kbmon_otel.py [--once] [--count N] [--interval S] [--panel NAME]
        [--store PATH] [--url URL --key-file PATH] [--from-snapshot FILE] [--prometheus-port N [--prometheus-bind HOST]]

The points come from `python3 _tools/kbmon.py --metrics` and the events from `--events` (otel_logs.py: one OTLP log
record each, and otel_spans.py: one span each, the cursor kept in memory), run as child processes (the stdlib tools
import no OpenTelemetry package). The SDK reads the endpoints and the headers itself, from OTEL_EXPORTER_OTLP_ENDPOINT
(or the _METRICS_, _LOGS_ and _TRACES_ variant of each signal) and OTEL_EXPORTER_OTLP_HEADERS (or its variants); the adapter takes no
flag or file for either and prints and logs no header value. With no endpoint set it sends nothing and says export
is off. `--prometheus-port N` also serves the same points at /metrics through the SDK's
Prometheus reader, on loopback only (otel_prom.py); it is off unless the flag is given. Docs: kb/_self/monitoring.md.

Exit codes: 0 sent (or export off), 1 a send failed, 2 kbmon gave no points or events or a bad argument (a
--prometheus-bind that is not loopback included).
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

import otel_logs
import otel_prom
import otel_spans
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.metrics import Observation
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader, MetricExportResult
from opentelemetry.sdk.resources import Resource

ROOT = Path(__file__).resolve().parent.parent
KBMON = ROOT / "_tools" / "kbmon.py"
HEADER_VARS = tuple(f"OTEL_EXPORTER_OTLP_{signal}HEADERS" for signal in ("METRICS_", "LOGS_", "TRACES_", ""))


def endpoint(signal: str = "METRICS") -> str:
    """The endpoint the SDK exporter of a signal (METRICS, LOGS or TRACES) would send to, or "" when none is set."""
    for var in (f"OTEL_EXPORTER_OTLP_{signal}_ENDPOINT", "OTEL_EXPORTER_OTLP_ENDPOINT"):
        if os.environ.get(var, "").strip():
            return os.environ[var].strip()
    return ""


def shown_endpoint(url: str) -> str:
    """The scheme and host of an endpoint, without credentials, a path or a query."""
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.hostname}" + (f":{parts.port}" if parts.port else "") if parts.hostname else "(set)"


def header_values() -> list[str]:
    """Every value of the headers variables, which no output may hold."""
    values = []
    for var in HEADER_VARS:
        for pair in os.environ.get(var, "").split(","):
            value = pair.partition("=")[2].strip()
            if value:
                values.append(value)
    return sorted(set(values), key=len, reverse=True)


class Scrub(logging.Filter):
    """Replace every header value in a log record before any handler writes it."""

    def __init__(self, values: list[str]):
        super().__init__()
        self.values = values

    def filter(self, record: logging.LogRecord) -> bool:
        text = record.getMessage()
        for value in self.values:
            text = text.replace(value, "***")
        record.msg, record.args = text, None
        return True


def run_kbmon(args, mode: list[str], what: str) -> dict:
    """The JSON object of one kbmon run; raises RuntimeError when kbmon gives none."""
    cmd = [sys.executable, str(KBMON), *mode, "--root", args.root]
    for flag, value in (("--store", args.store), ("--url", args.url), ("--key-file", args.key_file)):
        if value:
            cmd += [flag, value]
    env = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_")}
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env, timeout=args.timeout)
    if proc.returncode not in (0, 1):
        raise RuntimeError("kbmon exit %s: %s" % (proc.returncode, (proc.stderr.strip().splitlines() or [""])[-1][:200]))
    try:
        return json.loads(proc.stdout)
    except ValueError:
        raise RuntimeError(f"kbmon printed no {what}") from None


def collect(args) -> list[dict]:
    """The metric points of one kbmon snapshot; raises RuntimeError when kbmon gives none."""
    mode = ["--metrics"]
    for panel in args.panel:
        mode += ["--panel", panel]
    if args.from_snapshot:
        mode += ["--from-snapshot", args.from_snapshot]
    try:
        return run_kbmon(args, mode, "metric points")["points"]
    except (KeyError, TypeError):
        raise RuntimeError("kbmon printed no metric points") from None


def collect_events(args, cursor) -> dict:
    """The `--events` object newer than `cursor` (None: the first round); raises RuntimeError when kbmon gives none."""
    mode = ["--events"] + (["--since", cursor] if cursor else [])
    got = run_kbmon(args, mode, "events")
    if not isinstance(got, dict) or not isinstance(got.get("events"), list):
        raise RuntimeError("kbmon printed no events")
    return got


class Exporter(OTLPMetricExporter):
    """The SDK's OTLP/HTTP exporter, remembering whether the last export worked."""

    ok = True

    def export(self, metrics_data, timeout_millis: float = 10_000, **kwargs):
        result = super().export(metrics_data, timeout_millis=timeout_millis, **kwargs)
        self.ok = result == MetricExportResult.SUCCESS
        return result


class Sender:
    """One meter provider that lives across exports; each export reads the latest points."""

    def __init__(self, export: bool = True, extra_readers=()):
        self.latest: dict[str, list[dict]] = {}
        self.created: set[str] = set()
        self.reader = InMemoryMetricReader()
        resource = Resource.create({"service.name": os.environ.get("OTEL_SERVICE_NAME", "kbmon")})
        self.provider = MeterProvider(metric_readers=[self.reader, *extra_readers], resource=resource)
        self.meter = self.provider.get_meter("kbmon")
        self.exporter = Exporter() if export else None

    def _callback(self, name: str):
        def observe(options):
            return [Observation(p["value"], p.get("attributes") or {}) for p in self.latest.get(name, [])]

        return observe

    def send(self, points: list[dict]) -> bool:
        latest: dict[str, list[dict]] = {}
        for point in points:
            latest.setdefault(point["name"], []).append(point)
        self.latest = latest
        for name, group in latest.items():
            if name not in self.created:
                make = self.meter.create_observable_counter if group[0].get("kind") == "sum" else self.meter.create_observable_gauge
                make(name, callbacks=[self._callback(name)], unit=group[0].get("unit", ""))
                self.created.add(name)
        if self.exporter is None:
            return True
        data = self.reader.get_metrics_data()
        if data is None:
            return True
        self.exporter.export(data)
        return self.exporter.ok

    def close(self):
        self.provider.shutdown()
        if self.exporter is not None:
            self.exporter.shutdown()


class Cursor:
    """The `--events` cursor, kept in memory: it moves only when every signal of a round was sent."""

    value = None


def send_events(args, cursor: Cursor, logs, spans) -> int:
    """One round of event records and spans: 0 sent, 1 a send failed (the cursor stays), 2 kbmon gave no events."""
    try:
        got = collect_events(args, cursor.value)
    except (RuntimeError, subprocess.TimeoutExpired) as e:
        print(f"kbmon_otel: {e}", file=sys.stderr)
        return 2
    for problem in got.get("problems") or []:
        print(f"kbmon_otel: {problem}", file=sys.stderr)
    code = 0
    if logs:
        if logs.send(got):
            print(f"kbmon_otel: sent {len(got['events'])} log records", flush=True)
        else:
            print("kbmon_otel: log export failed", file=sys.stderr)
            code = 1
    if spans:
        if spans.send(got):
            print(f"kbmon_otel: sent {len(got.get('spans') or [])} spans", flush=True)
        else:
            print("kbmon_otel: span export failed", file=sys.stderr)
            code = 1
    if code == 0:
        cursor.value = got.get("cursor") or cursor.value
    return code


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Send kbmon's metric points over OTLP/HTTP (docs: kb/_self/monitoring.md).")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--panel", action="append", default=[], help="a kbmon panel whose points to send (repeatable; default: all)")
    ap.add_argument("--store", metavar="PATH", help="the coord store kbmon reads (default: kbmon's)")
    ap.add_argument("--url", metavar="URL", help="the coord server kbmon reads (with --key-file)")
    ap.add_argument("--key-file", metavar="PATH", help="the key file for --url")
    ap.add_argument("--from-snapshot", metavar="FILE", help="send the points of a saved kbmon --json snapshot (no events)")
    ap.add_argument("--once", action="store_true", help="send one snapshot and exit")
    ap.add_argument("--count", type=int, default=0, metavar="N", help="send N snapshots and exit (default 0: no limit)")
    ap.add_argument("--interval", type=float, default=60.0, metavar="S", help="seconds between sends (default 60)")
    ap.add_argument("--timeout", type=float, default=60.0, metavar="S", help="seconds kbmon may take (default 60)")
    ap.add_argument("--prometheus-port", type=int, metavar="N", help="also serve /metrics on loopback port N (0: a free port; default: not served)")
    ap.add_argument("--prometheus-bind", default="127.0.0.1", metavar="HOST", help="the loopback address /metrics binds (default 127.0.0.1)")
    args = ap.parse_args(argv)
    if args.interval < 1 or args.timeout < 1:
        ap.error("--interval and --timeout are 1 or more")
    if args.count < 0:
        ap.error("--count is 0 or more")
    if args.once:
        args.count = 1
    if args.prometheus_port is not None and not 0 <= args.prometheus_port <= 65535:
        ap.error("--prometheus-port is 0 to 65535")
    try:
        args.prometheus_bind = otel_prom.loopback(args.prometheus_bind)
    except ValueError as e:
        ap.error(str(e))

    url = endpoint("METRICS")
    logs_url = "" if args.from_snapshot else endpoint("LOGS")
    spans_url = "" if args.from_snapshot else endpoint("TRACES")
    if not url and not logs_url and not spans_url and args.prometheus_port is None:
        print("kbmon_otel: export is off (no OTEL_EXPORTER_OTLP_ENDPOINT set); nothing sent")
        return 0

    logging.basicConfig(level=logging.ERROR)
    scrub = Scrub(header_values())
    for handler in logging.getLogger().handlers:
        handler.addFilter(scrub)

    if url or logs_url or spans_url:
        targets = [f"{kind} to {shown_endpoint(u)}"
                   for kind, u in (("metrics", url), ("logs", logs_url), ("traces", spans_url)) if u]
        print(f"kbmon_otel: export is on, {', '.join(targets)}")
    else:
        print("kbmon_otel: export is off (no OTEL_EXPORTER_OTLP_ENDPOINT set); /metrics only")
    prom = otel_prom.reader() if args.prometheus_port is not None else None
    sender = Sender(export=bool(url), extra_readers=[prom] if prom else []) if url or prom else None
    resource = Resource.create({"service.name": os.environ.get("OTEL_SERVICE_NAME", "kbmon")})
    logs = otel_logs.Logs(resource) if logs_url else None
    spans = otel_spans.Spans(resource) if spans_url else None
    cursor = Cursor()
    server = None
    code = 0
    sent = 0
    try:
        if prom:
            server, metrics = otel_prom.serve(args.prometheus_port, args.prometheus_bind)
            print(f"kbmon_otel: serving {metrics}", flush=True)
        while True:
            code = 0
            if sender:
                try:
                    points = collect(args)
                except (RuntimeError, subprocess.TimeoutExpired) as e:
                    print(f"kbmon_otel: {e}", file=sys.stderr)
                    code = 2
                else:
                    if sender.send(points):
                        print(f"kbmon_otel: {'sent' if url else 'read'} {len(points)} points", flush=True)
                    else:
                        print("kbmon_otel: export failed", file=sys.stderr)
                        code = 1
            if logs or spans:
                code = max(code, send_events(args, cursor, logs, spans))
            sent += 1
            if args.count and sent >= args.count:
                return code
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return code
    finally:
        if sender:
            sender.close()
        if logs:
            logs.close()
        if spans:
            spans.close()
        if server:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    sys.exit(main())
