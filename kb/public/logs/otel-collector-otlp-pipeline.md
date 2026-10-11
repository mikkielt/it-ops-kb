---
topic: logs/otel-collector-otlp-pipeline
priority: P3
applies_to: "OpenTelemetry Collector core v0.162.0 (modules v1.68.0, 2026-09-28) and contrib v0.162.0; OTLP specification (opentelemetry-proto v1.11.1); Prometheus v3.15.0; Loki v3.7.8; Tempo v3.1.0"
retrieved_utc: 2026-10-11
sources: [S-2k6jmt4p, S-42ulxlwb, S-iylg5wv4, S-idpr2htc, S-fghrnot6, S-oodxsnls, S-ixy3elbb, S-tb2kr6j6, S-v4swo5wh, S-ypu7twsm, S-zgo6e6dk, S-gkgmlv5b, S-ix5z63av, S-h52nhp55, S-jdyoyfwa, S-p23y4jgk, S-2blrcu72, S-j5eil3ej, S-o36nadfz, S-e4bf6k75, S-hbpi7gg6, S-a6ldut5r, S-vnjcetlc, S-r3lv4n27, S-ina32am5, S-xvaz44vc, S-v2wnj4qk, S-5tvo6y34, S-one7nth5, S-j7chz4co, S-n4qvimrb, S-wpvglutf, S-su2aihea, S-f2cwt6i6]
status: partial
---

# OpenTelemetry Collector: OTLP pipeline, processors and Prometheus, Loki and Tempo backends

## Summary
The Collector wires receivers, processors and exporters into one pipeline per signal (traces, metrics, logs). OTLP is stable for those three signals in the specification and in the `otlp` receiver and the `otlp_grpc` / `otlp_http` exporters.
At v0.162.0 the docs name these exporters `otlp_grpc` and `otlp_http`; the older `otlp` and `otlphttp` names are deprecated aliases.
Metrics reach Prometheus by scrape (`prometheus` exporter), by remote write (`prometheus_remote_write`) or by Prometheus's own OTLP receiver behind a flag; Loki takes OTLP logs over HTTP at `/otlp`, and Tempo takes OTLP traces on its distributor (gRPC 4317, HTTP 4318).
The Collector's own telemetry is Prometheus metrics on port 8888 and logs on stderr (console or JSON). File and Windows Event Log receivers are covered in `logs/otel-collector-receivers`.

## Facts
### Release, stability and distributions
- Latest Collector core release at 2026-10-11 is `v1.68.0/v0.162.0` (release title), published 2026-09-28; the docs site pins Collector version 0.162.0. [DOC S-xvaz44vc, S-fghrnot6]
- The Collector's overall status is "mixed": each component's README states its stability per signal, from development through alpha, beta and stable to deprecated and unmaintained. [DOC S-fghrnot6, S-j5eil3ej]
- The OTLP specification marks the trace, metric and log signals Stable and the profiles signal Development. [DOC S-v2wnj4qk]
- The `otlp` receiver and the OTLP gRPC and HTTP exporters are stable for traces, metrics and logs and alpha for profiles; the gRPC exporter's component type is `otlp_grpc` with `otlp` as its deprecated type. [DOC S-oodxsnls, S-ixy3elbb, S-tb2kr6j6]
- The distributions repository lists six distributions: `otelcol`, `otelcol-contrib`, `otelcol-k8s`, `otelcol-otlp`, `otelcol-prometheus` and `otelcol-ebpf-profiler`; each ships binaries, container images and rpm/deb packages. [DOC S-vnjcetlc]
- The v0.162.0 `otelcol` (core) manifest includes the `otlp` receiver, the `debug`, `otlp`, `otlphttp` exporters, and from contrib the `file`, `prometheus` and `prometheusremotewrite` exporters plus `batch` and `memory_limiter` processors. [CODE S-r3lv4n27: distributions/otelcol/manifest.yaml#exporters]
- The contrib changelog records that the Loki exporter was removed from the repository in v0.131.0, after being deprecated since 9 July 2024, and tells its users to move to an OTLP exporter. [DOC S-a6ldut5r]
- The v0.162.0 contrib manifest lists a `lokireceiver` and a `prometheusremotewritereceiver` among its receivers and no Loki exporter among its exporters. [DER S-ina32am5, S-a6ldut5r: absence of an exporter entry in the manifest, consistent with the removal in the changelog]
- A custom distribution is built with the `ocb` builder from a YAML manifest (a `dist` section plus lists of receivers, processors, exporters and extensions); `ocb` needs Go and is published under `cmd/builder` release tags. [DOC S-iylg5wv4, S-idpr2htc]

### Configuration and the OTLP pipeline
- A configuration has `receivers`, `processors`, `exporters`, `connectors`, `extensions` and `service`; defining a component does not enable it, only listing it under `service.pipelines` (or `service.extensions`) does, and ids use `type[/name]`. [DOC S-2k6jmt4p]
- `service.pipelines` accepts `traces`, `metrics` and `logs` (plus `type/name` copies); processor order in a pipeline is the processing order, and a processor used in several pipelines gets one instance per pipeline. [DOC S-2k6jmt4p]
- `--config` takes a file path or a `file:`, `env:`, `yaml:`, `http:` or `https:` URI, may be given several times (the parts are merged), and `otelcol validate` checks a file. [DOC S-2k6jmt4p]
- The `otlp` receiver listens by default on `localhost:4317` (gRPC) and `localhost:4318` (HTTP); a protocol is enabled only when listed; HTTP paths default to `/v1/traces`, `/v1/metrics`, `/v1/logs` and can be changed with `traces_url_path`, `metrics_url_path`, `logs_url_path`. [DOC S-oodxsnls]
- The OTLP specification gives 4317 as the OTLP/gRPC default port, 4318 for OTLP/HTTP, POST to `/v1/traces`, `/v1/metrics`, `/v1/logs`, protobuf or JSON bodies, and recommends a 64 MiB request limit answered with HTTP 413. [DOC S-v2wnj4qk]
- The docs' examples bind `0.0.0.0` for convenience while the Collector itself defaults to `localhost`. [DOC S-2k6jmt4p]
- The `otlp_grpc` exporter needs an `endpoint`, requires TLS unless `tls.insecure` is set, and compresses with gzip by default; the `otlp_http` exporter takes a base `endpoint` and appends `/v1/<signal>`, can override each signal with `traces_endpoint`, `metrics_endpoint`, `logs_endpoint`, and sends `proto` (or `json`) with a 30 s timeout; `otlphttp` is a deprecated alias "removed in a future version". [DOC S-ixy3elbb, S-v4swo5wh]
- Exporters built on the exporter helper have the sending queue and retry on by default (queue 1000 batches, 10 consumers; retry 5 s initial, 30 s max interval, 300 s max elapsed); data that cannot enter a full queue is dropped, and an optional persistent queue uses a storage extension. [DOC S-h52nhp55]

### memory_limiter and batch
- `memory_limiter` (beta) needs `limit_mib` or `limit_percentage`; the soft limit is `limit_mib - spike_limit_mib`; above it the processor refuses data with a non-permanent error and receivers are expected to retry, and above the hard limit it also forces garbage collection. [DOC S-zgo6e6dk]
- The `memory_limiter` README advises making it the first processor in a pipeline, setting `GOMEMLIMIT` to 80% of the hard limit, a 1 s `check_interval` (default 0s) and a spike limit near 20% of the hard limit; data is lost if the component before it does not retry. [DOC S-zgo6e6dk]
- A memory limiter extension (beta, listed in no distribution) refuses requests in the receivers' HTTP and gRPC middleware before they are converted, and "will potentially replace" the processor. [DOC S-gkgmlv5b]
- `batch` (beta) defaults to `send_batch_size` 8192, `timeout` 200 ms and no `send_batch_max_size`; it belongs after `memory_limiter` and after sampling and filtering processors, because batching clears the request context and should not batch data that is later dropped. [DOC S-ypu7twsm, S-ix5z63av]
- The processor README's recommended order is `memory_limiter`, dropping processors, context-dependent processors, transform and enrich processors, then `batch`, and prefers the exporter's own batching when available; the exporter helper's `sending_queue.batch` is disabled unless `batch: {}` is set (defaults `min_size` 8192, `flush_timeout` 200 ms). [DOC S-ix5z63av, S-h52nhp55]

### Metrics to Prometheus
- The `prometheus` exporter (beta, metrics) serves `/metrics` on its `endpoint` for a Prometheus server to scrape; samples expire after `metric_expiration` (5m); resource attributes go to `target_info` unless promoted. [DOC S-o36nadfz]
- The `prometheus_remote_write` exporter (beta, metrics; alias `prometheusremotewrite`) pushes to remote-write backends such as Cortex, Mimir and Thanos, requires TLS by default, drops non-cumulative monotonic, histogram and summary metrics, uses its own `remote_write_queue` and an optional WAL. [DOC S-e4bf6k75]
- Prometheus's OTLP receiver is off by default and enabled with `--web.enable-otlp-receiver`; it serves OTLP/HTTP metrics at `/api/v1/otlp/v1/metrics` and is off by default because Prometheus can run without authentication; the remote-write receiver is a separate flag, also false by default. [DOC S-5tvo6y34, S-one7nth5]
- The Prometheus OTLP guide suggests `out_of_order_time_window: 30m` because several batching Collector replicas can deliver samples out of order. [DOC S-5tvo6y34]
- The guide documents only a metrics path; whether Prometheus accepts OTLP logs or traces on any other path is not stated on the pages read. [UNK]

### Logs and traces to Loki and Tempo
- Loki ingests OTLP logs natively over HTTP: use the Collector's `otlphttp` exporter with `endpoint: http://<loki-addr>/otlp`, and keep `limits_config.allow_structured_metadata` true (the default since Loki 3.0), or Loki rejects the payload; the Loki tutorial points the exporter at `http://loki:3100/otlp`. [DOC S-j7chz4co, S-wpvglutf]
- Loki maps 17 listed resource attributes (such as `service.name`, `k8s.namespace.name`) to index labels and stores the rest as structured metadata; dots become underscores; Grafana calls the native endpoint "the recommended way" and is moving Loki exporter users to it. [DOC S-j7chz4co, S-n4qvimrb]
- The Loki pages read name only the HTTP `otlphttp` exporter path; whether Loki's OTLP endpoint accepts gRPC is not stated there. [UNK]
- Tempo's distributor takes OTLP (and Jaeger, Zipkin, Kafka) receivers with defaults of `localhost:4317` and `localhost:4318`; since Tempo 2.7 the OTLP receiver defaults to localhost, so containers need `0.0.0.0:4317`; Tempo 3.0 removed the OpenCensus receiver; a tenant is set with the `x-scope-orgid` header. [DOC S-su2aihea, S-f2cwt6i6]

### Collector telemetry and local sinks
- By default the Collector serves its own metrics for scraping on port 8888 (`http://127.0.0.1:8888/metrics`); `service::telemetry::metrics::level` is `none`, `basic`, `normal` (default) or `detailed`; the `address` setting has been ignored since v0.123.0 (a `readers` list sets the Prometheus port or an OTLP push instead). [DOC S-42ulxlwb]
- Internal logs go to `stderr` by default; `service::telemetry::logs` has `level` (default `INFO`), `encoding` (default `console`, other value `json`), `output_paths` (default `["stderr"]`) and sampling; log formatting and tracing carry no stability guarantee. [DOC S-42ulxlwb]
- The Collector passes `encoding` and `output_paths` to a zap logger configuration, and zap treats the scheme-less paths `stdout` and `stderr` as the process streams. [CODE S-p23y4jgk: service/telemetry/otelconftelemetry/logger.go#createLogger; CODE S-2blrcu72: writer.go#Open]
- The `debug` exporter (alpha) prints telemetry with `verbosity` `basic` (default), `normal` or `detailed`, through the Collector's internal logger unless `use_internal_logger: false`, and its output format may change without notice; the `file` exporter (alpha) writes JSON lines by default (or `proto`), with rotation and zstd. [DOC S-jdyoyfwa, S-hbpi7gg6]

### How it fits
- The service's metrics can reach Prometheus with no inbound port on Prometheus: the Collector's `prometheus` exporter exposes a scrape endpoint, which avoids the two receiver flags, whereas remote write or direct OTLP needs the matching receiver enabled on Prometheus and its own out-of-order settings. [DER S-o36nadfz, S-e4bf6k75, S-5tvo6y34, S-one7nth5: scrape needs no Prometheus receiver flag; push paths need `--web.enable-remote-write-receiver` or `--web.enable-otlp-receiver`]
- Logs and traces for a self-hosted Loki and Tempo go through one OTLP HTTP exporter and one OTLP exporter on a single Collector; no Loki-specific exporter is needed, since the Loki exporter was removed and Loki has a native endpoint. [DER S-j7chz4co, S-su2aihea, S-a6ldut5r: native OTLP endpoints on both, Loki exporter removed in v0.131.0]
- A pinned binary is possible because the distribution manifests pin every component to one version and `ocb` assembles a custom set from Go modules (with Go needed at build time); component type names have been renamed (`otlp` to `otlp_grpc`), so a configuration is only checked against the version it was written for. [DER S-r3lv4n27, S-iylg5wv4, S-tb2kr6j6: manifest pins, ocb build, deprecated aliases]
- JSON logs on stdout need `encoding: json` and `output_paths: [stdout]` together, since the stated default destination is stderr; this was not run here. [DER S-42ulxlwb, S-p23y4jgk, S-2blrcu72: documented defaults plus the zap stream rule]

## Reference
- Receivers for files and the Windows Event Log: `logs/otel-collector-receivers`. Log data model: `logs/otel-log-data-model`. Claude Code's own OTLP export: `claude/otel-monitoring`.
- Component stability definitions: development, alpha, beta, stable, deprecated, unmaintained (S-j5eil3ej). OTLP specification: S-v2wnj4qk.
- Defaults at a glance: OTLP gRPC 4317, OTLP HTTP 4318, Collector metrics 8888, Loki OTLP path `/otlp`, Prometheus OTLP path `/api/v1/otlp/v1/metrics`, Prometheus flag `--web.enable-otlp-receiver`.

## Examples
- SNIPPET: one Collector receiving OTLP and fanning metrics, logs and traces to Prometheus (scrape), Loki and Tempo, with JSON logs on stdout; context: Collector v0.162.0 type names, hosts are placeholders; checked: no [DOC S-oodxsnls, S-zgo6e6dk, S-ypu7twsm, S-o36nadfz, S-v4swo5wh, S-ixy3elbb, S-j7chz4co, S-su2aihea, S-42ulxlwb: receiver, processor, exporter and telemetry options as read]
```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: localhost:4317
      http:
        endpoint: localhost:4318
processors:
  memory_limiter:
    check_interval: 1s
    limit_mib: 1000
    spike_limit_mib: 200
  batch:
exporters:
  prometheus:
    endpoint: localhost:8889
  otlp_http/loki:
    endpoint: http://PL-SRV-0042:3100/otlp
  otlp_grpc/tempo:
    endpoint: PL-SRV-0042:4317
    tls:
      insecure: true
service:
  telemetry:
    logs:
      encoding: json
      output_paths: [stdout]
  pipelines:
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [prometheus]
    logs:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [otlp_http/loki]
    traces:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [otlp_grpc/tempo]
```
- SNIPPET: Prometheus accepting OTLP metrics directly from a Collector exporter; context: Prometheus v3.15.0 started with the flag; the exporter appends `/v1/metrics` to the endpoint; checked: no [DER S-5tvo6y34, S-v4swo5wh: path `/api/v1/otlp/v1/metrics` is the base `/api/v1/otlp` plus the appended signal path]
```yaml
exporters:
  otlp_http/prometheus:
    endpoint: http://PL-SRV-0042:9090/api/v1/otlp
```
