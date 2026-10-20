"""otel_prom: serve kbmon's metric points at /metrics through the OpenTelemetry SDK's Prometheus reader.

Used by kbmon_otel.py (`--prometheus-port N`). The listener binds loopback only: `loopback()` refuses any other
host, and `serve()` always passes the address to the server itself, since prometheus_client binds every interface
when none is given. The reader writes to a registry of its own, never prometheus_client's global one, so /metrics carries
kbmon's points and not the Python process and GC collectors; any path but /metrics answers 404. The Prometheus packages
are imported in `reader()` and `serve()`, so the rest of the adapter runs without them.
"""

import ipaddress
import socket
import wsgiref.simple_server

_registry = None


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
    """The SDK's Prometheus metric reader, on a registry of its own; it answers each scrape from the meter provider it is added to."""
    global _registry
    from opentelemetry.exporter.prometheus import PrometheusMetricReader
    from prometheus_client import CollectorRegistry

    _registry = CollectorRegistry()
    return PrometheusMetricReader(registry=_registry)


class _Quiet(wsgiref.simple_server.WSGIRequestHandler):
    def log_message(self, format, *args):
        pass


def _app(registry):
    from prometheus_client import make_wsgi_app

    metrics = make_wsgi_app(registry)

    def app(environ, start_response):
        if environ.get("PATH_INFO") != "/metrics":
            start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
            return [b"not found; the points are at /metrics\n"]
        return metrics(environ, start_response)

    return app


def serve(port: int, host: str = "127.0.0.1"):
    """Start the /metrics listener on loopback; returns (server, url). `port` 0 takes a free port. `reader()` runs first."""
    import threading

    from prometheus_client import CollectorRegistry
    from prometheus_client.exposition import ThreadingWSGIServer

    host = loopback(host)

    class Server(ThreadingWSGIServer):
        address_family = socket.AF_INET6 if ":" in host else socket.AF_INET

    server = wsgiref.simple_server.make_server(host, port, _app(_registry or CollectorRegistry()), Server, handler_class=_Quiet)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, metrics_url(host, server.server_port)
