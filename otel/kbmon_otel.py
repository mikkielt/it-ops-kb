"""kbmon_otel: send kbmon's metric points over OTLP/HTTP with the OpenTelemetry Python SDK.

Run it from the clone's root, with the SDK pinned in otel/uv.lock:

    uv run --frozen --project otel python otel/kbmon_otel.py [--once] [--interval S] [--panel NAME] [--from-snapshot FILE]

The points come from `python3 _tools/kbmon.py --metrics`, run as a child process (the stdlib tools import no
OpenTelemetry package). The SDK reads the endpoint and the headers itself, from OTEL_EXPORTER_OTLP_ENDPOINT
(or OTEL_EXPORTER_OTLP_METRICS_ENDPOINT) and OTEL_EXPORTER_OTLP_HEADERS (or OTEL_EXPORTER_OTLP_METRICS_HEADERS);
the adapter takes no flag or file for either and prints and logs no header value. With no endpoint set it sends
nothing and says export is off. Docs: kb/_self/monitoring.md.

Exit codes: 0 sent (or export off), 1 a send failed, 2 kbmon gave no points or a bad argument.
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

from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.metrics import Observation
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader, MetricExportResult
from opentelemetry.sdk.resources import Resource

ROOT = Path(__file__).resolve().parent.parent
KBMON = ROOT / "_tools" / "kbmon.py"
ENDPOINT_VARS = ("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", "OTEL_EXPORTER_OTLP_ENDPOINT")
HEADER_VARS = ("OTEL_EXPORTER_OTLP_METRICS_HEADERS", "OTEL_EXPORTER_OTLP_HEADERS")


def endpoint() -> str:
    for var in ENDPOINT_VARS:
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


def collect(args) -> list[dict]:
    """The metric points of one kbmon snapshot; raises RuntimeError when kbmon gives none."""
    cmd = [sys.executable, str(KBMON), "--metrics", "--root", args.root]
    for panel in args.panel:
        cmd += ["--panel", panel]
    if args.from_snapshot:
        cmd += ["--from-snapshot", args.from_snapshot]
    env = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_")}
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env, timeout=args.timeout)
    if proc.returncode not in (0, 1):
        raise RuntimeError("kbmon exit %s: %s" % (proc.returncode, (proc.stderr.strip().splitlines() or [""])[-1][:200]))
    try:
        return json.loads(proc.stdout)["points"]
    except (ValueError, KeyError, TypeError):
        raise RuntimeError("kbmon printed no metric points") from None


class Exporter(OTLPMetricExporter):
    """The SDK's OTLP/HTTP exporter, remembering whether the last export worked."""

    ok = True

    def export(self, metrics_data, timeout_millis: float = 10_000, **kwargs):
        result = super().export(metrics_data, timeout_millis=timeout_millis, **kwargs)
        self.ok = result == MetricExportResult.SUCCESS
        return result


class Sender:
    """One meter provider that lives across exports; each export reads the latest points."""

    def __init__(self):
        self.latest: dict[str, list[dict]] = {}
        self.created: set[str] = set()
        self.reader = InMemoryMetricReader()
        resource = Resource.create({"service.name": os.environ.get("OTEL_SERVICE_NAME", "kbmon")})
        self.provider = MeterProvider(metric_readers=[self.reader], resource=resource)
        self.meter = self.provider.get_meter("kbmon")
        self.exporter = Exporter()

    def _callback(self, name: str):
        def observe(options):
            return [Observation(p["value"], p.get("attributes") or {}) for p in self.latest.get(name, [])]

        return observe

    def send(self, points: list[dict]) -> bool:
        self.latest = {}
        for point in points:
            self.latest.setdefault(point["name"], []).append(point)
        for name, group in self.latest.items():
            if name not in self.created:
                make = self.meter.create_observable_counter if group[0].get("kind") == "sum" else self.meter.create_observable_gauge
                make(name, callbacks=[self._callback(name)], unit=group[0].get("unit", ""))
                self.created.add(name)
        data = self.reader.get_metrics_data()
        if data is None:
            return True
        self.exporter.export(data)
        return self.exporter.ok

    def close(self):
        self.provider.shutdown()
        self.exporter.shutdown()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Send kbmon's metric points over OTLP/HTTP (docs: kb/_self/monitoring.md).")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--panel", action="append", default=[], help="a kbmon panel to send (repeatable; default: all)")
    ap.add_argument("--from-snapshot", metavar="FILE", help="send the points of a saved kbmon --json snapshot")
    ap.add_argument("--once", action="store_true", help="send one snapshot and exit")
    ap.add_argument("--interval", type=float, default=60.0, metavar="S", help="seconds between sends (default 60)")
    ap.add_argument("--timeout", type=float, default=60.0, metavar="S", help="seconds kbmon may take (default 60)")
    args = ap.parse_args(argv)
    if args.interval < 1 or args.timeout < 1:
        ap.error("--interval and --timeout are 1 or more")

    url = endpoint()
    if not url:
        print("kbmon_otel: export is off (no OTEL_EXPORTER_OTLP_ENDPOINT set); nothing sent")
        return 0

    logging.basicConfig(level=logging.ERROR)
    scrub = Scrub(header_values())
    for handler in logging.getLogger().handlers:
        handler.addFilter(scrub)

    print(f"kbmon_otel: export is on, metrics to {shown_endpoint(url)}")
    sender = Sender()
    code = 0
    try:
        while True:
            try:
                points = collect(args)
            except (RuntimeError, subprocess.TimeoutExpired) as e:
                print(f"kbmon_otel: {e}", file=sys.stderr)
                code = 2
            else:
                if sender.send(points):
                    print(f"kbmon_otel: sent {len(points)} points")
                    code = 0
                else:
                    print("kbmon_otel: export failed", file=sys.stderr)
                    code = 1
            if args.once:
                return code
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return code
    finally:
        sender.close()


if __name__ == "__main__":
    sys.exit(main())
