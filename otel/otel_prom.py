"""otel_prom: serve kbmon's metric points at /metrics through the OpenTelemetry SDK's Prometheus reader.

Used by kbmon_otel.py (`--prometheus-port N`). The listener binds loopback only: `loopback()` refuses any other
host, and `serve()` always passes the address to the server itself, since prometheus_client binds every interface
when none is given. The reader writes to a registry of its own, never prometheus_client's global one, so /metrics carries
kbmon's points and not the Python process and GC collectors; any path but /metrics answers 404. The Prometheus packages
are imported in `reader()` and `serve()`, so the rest of the adapter runs without them. `served_names()` reads the names
the registry would serve without a listener, and `rule_exprs()` and `rule_names()` read the kbmon_ names a rules file uses
(`kbmon_otel.py --check-rules`).
"""

import ipaddress
import re
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


def served_names() -> set[str]:
    """The metric names /metrics would serve now: every sample name the reader's registry collects. `reader()` runs first."""
    return {sample.name for family in _registry.collect() for sample in family.samples}


def rule_exprs(text: str) -> list[str]:
    """The `expr:` values of a Prometheus rules file, one string each: a plain value, a single- or double-quoted YAML
    value (unquoted to the expression) or a `|` / `>` block."""
    lines = text.splitlines()
    exprs = []
    for i, line in enumerate(lines):
        match = re.match(r"^(\s*)(?:-\s+)?expr:\s*(.*)$", line)
        if not match:
            continue
        value = match.group(2).strip()
        quoted = re.match(r"'((?:[^']|'')*)'|\"((?:[^\"\\]|\\.)*)\"", value)
        if quoted:
            value = quoted.group(1).replace("''", "'") if quoted.group(1) is not None else re.sub(r"\\([\"\\])", r"\1", quoted.group(2))
        else:
            value = re.sub(r"\s#.*$", "", value).strip()
        if not quoted and value[:1] in ("|", ">"):
            block = []
            for follow in lines[i + 1:]:
                if follow.strip() and len(follow) - len(follow.lstrip()) <= len(match.group(1)):
                    break
                block.append(follow.strip())
            value = " ".join(part for part in block if part)
        exprs.append(value)
    return exprs


def rule_names(exprs: list[str]) -> list[str]:
    """The kbmon_ metric names the expressions use, sorted and without repeats: a name in a `__name__="kbmon_x"` matcher
    counts, a quoted label value does not, and a recording-rule name with a colon (`kbmon_x:rate5m`) is no served metric."""
    names = set()
    for expr in exprs:
        names.update(m[0] or m[1] for m in re.findall(r"__name__\s*=\s*(?:\"(kbmon_\w+)\"|'(kbmon_\w+)')", expr))
        names.update(re.findall(r"(?<![\w:])kbmon_\w+(?![\w:])", re.sub(r'"[^"]*"|\'[^\']*\'', "", expr)))
    return sorted(names)


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
