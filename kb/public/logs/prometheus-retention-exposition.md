---
topic: logs/prometheus-retention-exposition
priority: P3
applies_to: "Prometheus v3.15.0 (released 2026-09-24); Python prometheus_client 0.26.0; Rust prometheus 0.14.0, prometheus-client 0.25.1, metrics-exporter-prometheus 0.18.3; prometheus/docs at commit 605cf81f"
retrieved_utc: 2026-10-11
sources: [S-cgscrv4s, S-one7nth5, S-fpf6c56i, S-42nwx5i6, S-a3vg5qlu, S-fauxu5ws, S-bfvveghs, S-eo46iizs, S-zirdyvds, S-ptmbzpgw, S-5tvo6y34, S-zbmhggt3, S-4hvb3m5w, S-bpsk5rak, S-dn4wxw4r, S-wr47t6mb, S-4gvbwjju, S-3ylk7y4h, S-f5e4slzj, S-fr4rpivt, S-lggz7o42, S-fmkur47t, S-uc4rdiul, S-ced5z4pp, S-4dcfdr4h, S-rm4q4usy, S-pf4gtprf, S-sxme5fjq, S744]
status: partial
---

# Prometheus: TSDB retention, exposition format, scrape config and client libraries

## Summary
Prometheus keeps samples in a local TSDB of two-hour blocks plus a write-ahead log; retention is set by time
(default 15 days) and optionally by size, and a block goes only when it has fully expired. Targets expose metrics
as text (`text/plain; version=0.0.4`, or OpenMetrics ending in `# EOF`) that Prometheus pulls from `/metrics`
on `scrape_interval`. Python (`prometheus_client`) and Rust (`prometheus`, `prometheus-client`,
`metrics-exporter-prometheus`) libraries produce that text. The scrape
endpoints have no authentication unless the operator adds TLS or basic auth. Claude Code's `prometheus` metrics
exporter (`claude/otel-monitoring.md`) is one such scrape target.

## Facts

### TSDB layout and retention
- Ingested samples are grouped into two-hour blocks; each block directory holds a `chunks` subdirectory (segment files of up to 512 MB by default), a metadata file and an `index`. The block being filled lives in memory and is protected by a write-ahead log in the `wal` directory (128 MB segments; at least three files kept, more on busy servers to cover two hours of raw data). [DOC S-cgscrv4s]
- `--storage.tsdb.path` defaults to `data/`. `--storage.tsdb.retention.time` defaults to `15d` only when neither it nor `--storage.tsdb.retention.size` is set; its units are y, w, d, h, m, s and ms. [DOC S-cgscrv4s, S-one7nth5]
- `--storage.tsdb.retention.size` caps the bytes of blocks kept; it is off by default (`0`), takes units B to EB in powers of 2 (for example `512MB`), and removes the oldest data first. [DOC S-cgscrv4s]
- Size retention deletes only persistent blocks but counts WAL and m-mapped head chunks in the total, so the disk must hold at least the peak of `wal` plus `chunks_head` (peaks every two hours). Source blocks and the compacted block coexist for a while, so disk use can briefly exceed the size limit. [DOC S-cgscrv4s]
- When time and size retention are both set, whichever triggers first wins. Cleanup runs in the background, can take up to two hours, and removes a block only when it is fully expired. [DOC S-cgscrv4s]
- Compaction merges the two-hour blocks into longer ones that span up to 10% of the retention time or 31 days, whichever is smaller. [DOC S-cgscrv4s]
- In v3.15.0 the command-line page marks both retention flags `[DEPRECATED]` in favour of `retention.time` and `retention.size` under `storage: tsdb:` in the configuration file. The file fields take precedence, apply on reload (deletion by the new policy follows within one minute or at the next compaction), and `retention.percentage` is an experimental alternative to size. [DOC S-one7nth5, S-fpf6c56i]
- Disk sizing: needed space is retention seconds times ingested samples per second times bytes per sample, with an average of 1 to 2 bytes per sample; the page says to use a local POSIX filesystem and that NFS is not supported. [DOC S-cgscrv4s]

### Exposition format and naming
- The text format is line-oriented UTF-8 over HTTP with `Content-Type: text/plain` and `version=0.0.4` (gzip optional). `# HELP` and `# TYPE` lines give the docstring and the type (`counter`, `gauge`, `histogram`, `summary`, `untyped`), at most one of each per metric name; `TYPE` must come before the first sample, and a metric without it is untyped. [DOC S-fauxu5ws]
- In the text format a histogram named `x` is `x_bucket{le="..."}` samples plus `x_sum` and `x_count`, and the `{le="+Inf"}` bucket must equal `x_count`; a summary is `x{quantile="..."}` samples plus `x_sum` and `x_count`. [DOC S-fauxu5ws]
- A counter only goes up (or resets to zero on restart) and a gauge goes up and down. Classic histogram buckets are cumulative; a summary computes quantiles over a sliding window. The server keeps the type only in the exposition, flattening all but native histograms to untyped floats. [DOC S-eo46iizs]
- The OpenMetrics text format uses `application/openmetrics-text` with `version=1.0.0` and ends the exposition with `# EOF`; the exposition-formats page lists an OpenMetrics 2.0 as a draft. [DOC S-fauxu5ws]
- The OpenMetrics 1.0.0 specification requires an exposition to end with EOF, requires a counter's total sample to carry the `_total` suffix, and requires a non-empty unit to be both a suffix of the family name and declared in a `# UNIT` line. [DOC S-4hvb3m5w]
- Since Prometheus 3.0 a scrape target must return a valid `Content-Type`; a missing, unparsable or unsupported one makes the scrape fail. [DOC S-fauxu5ws]
- Metric names should match `[a-zA-Z_:][a-zA-Z0-9_:]*` and label names `[a-zA-Z_][a-zA-Z0-9_]*`; any UTF-8 is allowed from v3.0 with quoting, label names starting with `__` are reserved, and colons are reserved for recording rules. [DOC S-zirdyvds]
- Naming practice: a single-word application prefix, one unit per name in base units (`seconds`, `bytes`), the unit as a plural suffix and `_total` on accumulating counts (`http_requests_total`, `process_cpu_seconds_total`). The page says these are conventions, not requirements. [DOC S-bfvveghs]
- Labels distinguish characteristics of one measured thing; every distinct label set is a new series, so unbounded values such as user ids or email addresses must not be labels. [DOC S-bfvveghs]

### Scrape configuration
- `scrape_configs` entries need a `job_name`; `scrape_interval` defaults to `1m` and `scrape_timeout` to `10s` (never above the interval), both overridable per job; `metrics_path` defaults to `/metrics` and `scheme` to `http`; targets come from `static_configs` (a `targets` list and a `labels` map) or service discovery. [DOC S-fpf6c56i]
- `honor_labels` defaults to `false`: labels in scraped data that clash with server-side ones are renamed `exported_<label>`; `true` keeps the scraped values, which the docs recommend for federation and the Pushgateway. [DOC S-fpf6c56i]
- With native histograms off, the default `scrape_protocols` order offered to a target is OpenMetricsText1.0.0, OpenMetricsText0.0.1, PrometheusText1.0.0, PrometheusText0.0.4. [DOC S-fpf6c56i]

### Client libraries
- Python `prometheus_client` 0.26.0: `start_http_server(port)` serves metrics from a daemon thread and returns the server and thread so it can be shut down; `make_wsgi_app()` returns a WSGI application that gzips when the client sends `Accept-Encoding: gzip` (`disable_compression=True` turns that off). [DOC S-bpsk5rak, S-dn4wxw4r]
- `start_http_server` is an alias of `start_wsgi_server`, whose `addr` defaults to `'0.0.0.0'` (all interfaces). [CODE S-3ylk7y4h: prometheus_client/exposition.py#start_wsgi_server]
- The WSGI app answers a GET on any path, not only `/metrics`; with no `Accept` header it replies `text/plain; version=0.0.4; charset=utf-8`, and an `Accept` for `application/openmetrics-text` selects the OpenMetrics encoder. [CODE S-3ylk7y4h: prometheus_client/exposition.py#choose_encoder]
- A Python `Counter` strips a trailing `_total` from its name and appends it on exposition; a `Histogram` uses default buckets from `.005` to `10` seconds plus `+Inf`, can take custom `buckets`, and reserves `le` as a label name. [DOC S-wr47t6mb, S-4gvbwjju]
- `prometheus_client` 0.26.0 declares `Apache-2.0 AND BSD-2-Clause` and `requires-python >=3.9`. [CODE S-f5e4slzj: pyproject.toml#project]
- The Prometheus client-library page lists `prometheus/client_rust` as the official Rust library and the Python, Go, Java, Node.js and Ruby clients beside it; the `prometheus` crate from TiKV is in neither its official nor its unofficial list. [DOC S-zbmhggt3]
- The `prometheus` crate 0.14.0 (tikv/rust-prometheus) is `Apache-2.0`, needs Rust 1.81, has `protobuf` as its only default feature and `process` and `push` as optional ones. [CODE S-fr4rpivt: Cargo.toml#package]
- Its `TextEncoder` reports the format constant `text/plain; version=0.0.4`. [CODE S-fmkur47t: src/encoder/text.rs#TEXT_FORMAT]
- Its crate docs describe an application endpoint that calls `gather` and passes the result through an `Encoder`, and name no HTTP listener of the crate's own. [CODE S-lggz7o42: src/lib.rs#crate-docs]
- `prometheus-client` 0.25.1 (prometheus/client_rust) is `Apache-2.0 OR MIT`, with protobuf support behind opt-in features. [CODE S-rm4q4usy: Cargo.toml#package]
- Its crate docs show `encode` writing the registry in the text format into a buffer when a monitoring system scrapes; the crate docs name no listener, so the application serves the buffer. [CODE S-pf4gtprf: src/lib.rs#crate-docs]
- `metrics-exporter-prometheus` 0.18.3 is `MIT AND Apache-2.0` in its Cargo.toml (the repository `LICENSE` file holds MIT text), and its default features are `http-listener` and `push-gateway`; `uds-listener` and `protobuf` are opt-in. [CODE S-ced5z4pp: Cargo.toml#features]
- Its HTTP listener responds to GET on any path, defaults to `0.0.0.0:9000`, and is mutually exclusive with push-gateway mode. [CODE S-4dcfdr4h: metrics-exporter-prometheus/src/exporter/builder.rs#with_http_listener]
- `with_recommended_naming(true)` (default `false`) appends `_total` to counters and unit suffixes to names; the older `set_enable_unit_suffix` is deprecated since 0.18.0. [CODE S-4dcfdr4h: metrics-exporter-prometheus/src/exporter/builder.rs#with_recommended_naming]
- The crate docs say the listener answers in text by default and in protobuf when the `Accept` header asks for it (with the `protobuf` feature), and that invalid characters in metric names and label keys are replaced by underscores at runtime. [CODE S-uc4rdiul: metrics-exporter-prometheus/src/lib.rs#crate-docs]
- Whether the TiKV `prometheus` crate adds `_total` or unit suffixes, or rewrites invalid names, was not read: only its format constant and crate docs were. [UNK]

### Security
- The security page says Prometheus endpoints, including the `/metrics` endpoint of instrumented binaries, should not be exposed to publicly accessible networks. It presumes untrusted users can reach the HTTP endpoint and read all stored series. [DOC S-ptmbzpgw]
- `--web.config.file` (TLS and authentication) is labelled `[EXPERIMENTAL]` on the command-line page and the HTTPS page calls basic auth and TLS experimental; the stability page lists server-side HTTPS and basic authentication under features not covered by the 3.x stability promise. [DOC S-one7nth5, S-42nwx5i6, S-a3vg5qlu]
- The web configuration file is read on every HTTP request. `tls_server_config` takes `cert_file` and `key_file`; `client_auth_type` defaults to `NoClientCert` and the docs say only `RequireAndVerifyClientCert` enforces client certificates; `min_version` defaults to `TLS12`; `basic_auth_users` holds bcrypt hashes. [DOC S-42nwx5i6]
- Basic authentication works without TLS but then sends usernames and passwords in cleartext. `--web.enable-admin-api` and `--web.enable-lifecycle` default to `false`. [DOC S-ptmbzpgw, S-one7nth5]
- The Python client serves only HTTP by default; `certfile` and `keyfile` turn on HTTPS, and `client_auth_required=True` (with `client_cafile` or `client_capath`) requires the Prometheus server to present a client certificate. [DOC S-bpsk5rak]
- The Rust `metrics-exporter-prometheus` builder offers an IP allowlist for its scrape endpoint, which its docs call insufficient on its own because of DNS rebinding; the builder methods read have no listener-side TLS or basic-auth option (basic-auth credentials appear only for the push gateway). [DER S-4dcfdr4h: public builder methods `add_allowed_address`, `with_push_gateway` and its doc comment]

### OTLP into Prometheus
- `--web.enable-otlp-receiver` ("Enable API endpoint accepting OTLP write requests") defaults to `false`. [DOC S-one7nth5]
- The OpenTelemetry guide says the receiver is off by default because Prometheus can run without authentication; enabled, it serves OTLP metrics over HTTP at `/api/v1/otlp/v1/metrics`, so a sender must use `http/protobuf` rather than the usual gRPC default. [DOC S-5tvo6y34]
- The stability page lists the "OTLP receiver endpoint" among things considered stable for 3.x; the guide says OTLP delta-temporality handling needs the feature flag `otlp-deltatocumulative` and is experimental. [DOC S-a3vg5qlu, S-5tvo6y34]
- The `otlp:` configuration block sets `translation_strategy`, default `UnderscoreEscapingWithSuffixes` (dots become underscores, unit and `_total` suffixes are added); `NoTranslation` is marked experimental with known collision risks. [DOC S-fpf6c56i]
- Claude Code's `OTEL_METRICS_EXPORTER=prometheus` is scraped from `http://localhost:9464/metrics`; when `prometheus` is the only metrics exporter it omits the `USD`, `tokens` and `s` units so the scrape stays valid Prometheus text. [DOC S744]

### How it fits (self-hosted corpus service, Python shell over a Rust core, CPU-only, offline-capable)
- Both library paths bind all interfaces by default (Python `addr='0.0.0.0'`, Rust `0.0.0.0:9000`) and Prometheus documents no authentication on `/metrics`, so a service that must stay on one host sets the loopback address explicitly (`start_http_server(port, addr="127.0.0.1")`, `with_http_listener`) or adds the web config file. [DER S-3ylk7y4h, S-4dcfdr4h, S-ptmbzpgw: default addresses plus the no-auth statement]
- Prometheus is one process with a local TSDB and a pull model, so it needs no runtime cloud call; disk is bounded by `retention.time` and `retention.size`, sized with the documented formula (for example 1,000 series scraped every 15 s kept 15 days is about 86 million samples, so roughly 86 to 173 MB at 1 to 2 bytes per sample). [DER S-cgscrv4s, S-fpf6c56i: formula, defaults and 66.7 samples/s times 1,296,000 s]
- One naming scheme across the shell and the core follows from the naming page: the Python client adds `_total` itself, while the Rust exporter does so only after `with_recommended_naming(true)`, so both sides set it to keep `_total` and `_seconds` or `_bytes` names identical. [DER S-bfvveghs, S-wr47t6mb, S-4dcfdr4h: naming rules plus the two libraries' behaviour]
- The Prometheus release publishes a `sha256sums.txt` with one SHA-256 per archive, including `linux-amd64`, `linux-arm64` and `windows-amd64`, so the server binary can be pinned by hash like other artifacts, and retention is a YAML field that applies on reload, so it can live as data beside the scrape jobs. [DER S-sxme5fjq, S-fpf6c56i: checksum file listing and the runtime-reloadable retention note]
- A Prometheus job for a Claude Code session on the same host needs only a `static_configs` target `127.0.0.1:9464`, because `metrics_path` already defaults to `/metrics`. [DER S744, S-fpf6c56i: exporter port and path plus the scrape defaults]

## Reference
| Setting | Where | Default | Source |
|---|---|---|---|
| `--storage.tsdb.path` | flag | `data/` | S-one7nth5 |
| `--storage.tsdb.retention.time` / `storage.tsdb.retention.time` | flag (deprecated), config file | `15d` when neither limit is set | S-cgscrv4s, S-fpf6c56i |
| `--storage.tsdb.retention.size` / `storage.tsdb.retention.size` | flag (deprecated), config file | `0` (off) | S-cgscrv4s, S-fpf6c56i |
| `--web.config.file` | flag | none, experimental | S-one7nth5 |
| `--web.enable-otlp-receiver` | flag | `false` | S-one7nth5 |
| `scrape_interval` / `scrape_timeout` | `global`, per job | `1m` / `10s` | S-fpf6c56i |
| `metrics_path` / `scheme` / `honor_labels` | per job | `/metrics` / `http` / `false` | S-fpf6c56i |

| Library | Version | Licence | Listener |
|---|---|---|---|
| `prometheus_client` (Python) | 0.26.0 | Apache-2.0 AND BSD-2-Clause | `start_http_server`, `make_wsgi_app` |
| `prometheus` (Rust, TiKV) | 0.14.0 | Apache-2.0 | none named in crate docs; encode and serve yourself |
| `prometheus-client` (Rust, official) | 0.25.1 | Apache-2.0 OR MIT | none named in crate docs; encode and serve yourself |
| `metrics-exporter-prometheus` | 0.18.3 | MIT AND Apache-2.0 | HTTP listener or push gateway |

Related: `claude/otel-monitoring.md` (Claude Code's `prometheus` exporter and OTLP events).
Source pages: Prometheus docs at tag v3.15.0 (storage, command line, configuration, HTTPS, stability) and
prometheus/docs at commit 605cf81f (exposition formats, naming, metric types, data model, security, OpenTelemetry guide).

## Examples
- SNIPPET: scrape one local target with the default path and interval; context: Prometheus 3.x `prometheus.yml`, target and job name are placeholders; checked: no [DER S-fpf6c56i: keys and defaults from the scrape_config reference]
```yaml
global:
  scrape_interval: 1m
scrape_configs:
  - job_name: corpus-service
    static_configs:
      - targets: ["127.0.0.1:8000"]
```
- SNIPPET: expose a Python counter and histogram on loopback only; context: prometheus_client 0.26.0, Python 3.9 or later; checked: syntax [DER S-bpsk5rak, S-wr47t6mb, S-4gvbwjju, S-3ylk7y4h: `start_http_server`, `Counter`, `Histogram` signatures and the `addr` parameter]
```python
from prometheus_client import Counter, Histogram, start_http_server

REQUESTS = Counter("requests", "Requests handled", ["route"], namespace="corpus")
LATENCY = Histogram("request_duration_seconds", "Request latency", namespace="corpus")

start_http_server(8000, addr="127.0.0.1")
REQUESTS.labels(route="search").inc()
LATENCY.observe(0.042)
```
- SNIPPET: what a scrape returns for the counter above; context: text format 0.0.4 as documented, sample values illustrative; checked: no [DER S-fauxu5ws, S-wr47t6mb: `# HELP`/`# TYPE` lines and the `_total` suffix rule]
```
# HELP corpus_requests_total Requests handled
# TYPE corpus_requests_total counter
corpus_requests_total{route="search"} 1.0
```
