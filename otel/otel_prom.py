"""otel_prom: serve kbmon's metric points at /metrics through the OpenTelemetry SDK's Prometheus reader.

Used by kbmon_otel.py (`--prometheus-port N`). The listener binds loopback only: `loopback()` refuses any other
host, and `serve()` always passes the address to the server itself, since prometheus_client binds every interface
when none is given. The Prometheus packages are imported in `serve()`, so the rest of the adapter runs without them.
"""

import ipaddress


def loopback(host: str) -> str:
    """The loopback address `host` names ('localhost' is 127.0.0.1); raises ValueError for any other host."""
    if host.strip().lower() == "localhost":
        return "127.0.0.1"
    try:
        address = ipaddress.ip_address(host.strip())
    except ValueError:
        address = None
    if address is None or not address.is_loopback:
        raise ValueError(f"--prometheus-bind takes a loopback address (127.0.0.1, ::1 or localhost), not {host!r}")
    return str(address)


def metrics_url(host: str, port: int) -> str:
    return f"http://[{host}]:{port}/metrics" if ":" in host else f"http://{host}:{port}/metrics"


def reader():
    """The SDK's Prometheus metric reader; it answers each scrape from the meter provider it is added to."""
    from opentelemetry.exporter.prometheus import PrometheusMetricReader

    return PrometheusMetricReader()


def serve(port: int, host: str = "127.0.0.1"):
    """Start the /metrics listener on loopback; returns (server, url). `port` 0 takes a free port."""
    from prometheus_client import start_http_server

    host = loopback(host)
    server, _thread = start_http_server(port, addr=host)
    return server, metrics_url(host, server.server_port)
