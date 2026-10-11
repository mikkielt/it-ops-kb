---
topic: logs/loki-tempo-grafana-retention
priority: P3
applies_to: "Grafana Loki v3.7.8, Grafana Tempo v3.1.0 (2.x noted), Grafana v13.2.3; single-binary self-hosted deployment"
retrieved_utc: 2026-10-11
sources: [S-olwlij2r, S-yz3o3jci, S-g36sus36, S-qyttpq2z, S-gsjmowie, S-jwoztkhv, S-minmacwi, S-wpvglutf, S-44skzn3g, S-sqfw3i4b, S-f2cwt6i6, S-a6zoom3b, S-cmpa7jl6, S-26xpxrvu, S-j4cjdcxk, S-ypvcpeth, S-pnnsdy4j, S-dvp4qcf3, S-qk6tvbrf, S-aodqvqxz, S-ud3mqhct, S-lajge47c, S-mygulbz4, S-coaeeb63, S-42oztc6t, S-jm3q4nrg, S-ssnqxfb6, S-rmnhrvck, S-drqcqer6, S-nfb3ytwd, S-47axdg7z, S-clqrp4oy, S-xpzp2unk, S-ffx6h64o, S-kx3xmf4o, S-nb36ls35, S-mri72d7r]
status: partial
---

# Loki, Tempo and Grafana: retention, single-binary storage, provisioning and JSON logs

## Summary
Loki keeps logs forever until the compactor is told to apply `retention_period`; Tempo deletes whole blocks older than
`block_retention` (14 days by default), and since Tempo 3.0 that setting lives under `backend_worker`, not `compactor`.
Both run as one process (`-target=all`) on local disk, and Grafana provisions Loki and Tempo as built-in data sources from YAML.
Loki and Tempo write JSON logs to stderr, Grafana to stdout. Not covered: Prometheus and the OpenTelemetry Collector.

## Facts
### Loki retention
- Retention is applied by the compactor; `compactor.retention-enabled` is not set by default, so ingested logs live forever. [DOC S-olwlij2r]
- Compactor keys: `retention_enabled` (default false), `retention_delete_delay` (default 2h), `delete_request_store` (required once retention is on) and `working_directory`; run the compactor as a single instance. [DOC S-olwlij2r, S-yz3o3jci]
- Retention needs a 24h index period; single-store TSDB and BoltDB require 24h anyway. The compactor does not support legacy index types, which use the deprecated Table Manager. [DOC S-olwlij2r]
- TSDB is the recommended index store from Loki 2.8; BoltDB (boltdb-shipper) is marked deprecated. [DOC S-qyttpq2z]
- The period is `limits_config.retention_period` (default `0s`, which disables deletion) or a `retention_stream` list of label-matcher selector, priority and period; each stream period must be at least 24h. [DOC S-olwlij2r, S-yz3o3jci]
- Precedence for one stream: per-tenant `retention_stream` (highest priority), global `retention_stream`, per-tenant `retention_period`, global `retention_period`, else keep forever; equal priority takes the shorter period. [DOC S-olwlij2r]
- Marked chunks are swept after `retention_delete_delay` so index gateways can fetch the rewritten index; marker files default to local disk and should be on persistent storage. [DOC S-olwlij2r]
- The page states that a changed retention period is "not retroactive" and does not apply to logs already ingested. [DOC S-olwlij2r]
- With the filesystem chunk store Loki never deletes by disk usage or free space, only by retention; `delete_request_store` is set to `filesystem`. [DOC S-gsjmowie]
- Grafana Labs does not support the filesystem object store for production, including under a support contract; it is unreplicated and fits single-binary or trial use. [DOC S-gsjmowie]

### Loki single binary and logs
- Monolithic mode is `-target=all`: every component in one process, suited to small volumes of about 20 GB per day; simple scalable mode is deprecated and goes away with Loki 4.0. [DOC S-g36sus36]
- The shipped single-binary config sets `auth_enabled: false`, port 3100, `common.storage.filesystem`, an in-memory ring, replication factor 1 and `tsdb` schema v13 with a 24h index period, and no `compactor` block. [CODE S-jwoztkhv: cmd/loki/loki-local-config.yaml#schema_config]
- Loki accepts OTLP logs on its native endpoint, `/otlp` on the HTTP port (the doc example posts to `http://loki:3100/otlp`). [DOC S-wpvglutf]
- Log format is `log_format` in the `server` block (flag `-log.format`), default `logfmt`; valid values are `logfmt` and `json`. [DOC S-yz3o3jci]
- Loki's logger is built on `os.Stderr`, so its own logs go to stderr, not stdout. [CODE S-minmacwi: pkg/util/log/log.go#newPrometheusLogger]

### Tempo retention and single binary
- Tempo 3.0 removed the `compactor` config section and component; the backend scheduler and worker now handle compaction and retention, and the Kafka-based ingest path is the only one. [DOC S-j4cjdcxk, S-cmpa7jl6]
- In the 2.10.8 configuration docs the key was `compactor.compaction.block_retention`, default `336h`. [DOC S-ypvcpeth]
- In 3.1.0 the Compaction block holds `block_retention` (default `336h`, 14 days) and `compacted_block_retention` (default `1h`); the manifest shows it under both `backend_scheduler.provider.compaction.compaction` and `backend_worker.compaction`. [DOC S-f2cwt6i6, S-a6zoom3b]
- The retention job runs in the worker and reads the worker's `compaction` block; the scheduler's compaction provider reads window, object and byte limits only, and a startup check compares the worker's `block_retention` with `blocklist_poll`. [DER S-pnnsdy4j, S-dvp4qcf3, S-aodqvqxz, S-ud3mqhct: processRetentionJob passes cfg.Compactor (yaml `compaction`); provider/compaction.go has no BlockRetention use]
- Retention marks a block as compacted when its end time is before now minus the retention (a non-zero per-tenant value wins), then clears marked blocks after `compacted_block_retention`. [CODE S-qk6tvbrf: tempodb/retention.go#retainTenant]
- Only block age drives deletion: `retainTenant` compares block end times and has no disk-usage or size branch. [DER S-qk6tvbrf: absence of a size criterion in retainTenant]
- Per-tenant retention is `overrides.defaults.compaction.block_retention` (0 falls back to the global value). [DOC S-f2cwt6i6]
- `storage.trace.backend` is one of gcs, s3, azure or `local`, and `local` (path under `storage.trace.local.path`) is supported only in monolithic mode, for development and testing; local and object storage cannot be mixed. [DOC S-f2cwt6i6]
- Monolithic mode is `-target=all` (the default) and needs no Kafka; more than one instance is unsupported because the backend scheduler is a singleton; the guide gives under 25-35 MB/s as its range. [DOC S-26xpxrvu]
- OTLP receivers sit under `distributor.receivers.otlp.protocols`: gRPC on 4317 and HTTP on 4318, bound to localhost unless an address is set; the HTTP API is on 3200. [DOC S-f2cwt6i6]
- The single-binary example sets `backend: local` with a WAL path and a blocks path, and OTLP endpoints on 4317 and 4318. [CODE S-lajge47c: example/docker-compose/single-binary/tempo.yaml#storage]
- The `server` block is dskit's server config; Tempo's go.mod pins a dskit commit whose `-log.format` flag lists `logfmt` and `json`, and the manifest default is `logfmt`. [DER S-mygulbz4, S-coaeeb63, S-a6zoom3b: go.mod pin; server/server.go#Config.RegisterFlags]
- Tempo builds its logger on `os.Stderr` and switches to the JSON encoder when `log_format` is `json`. [CODE S-42oztc6t: pkg/util/log/log.go#InitLogger]

### Grafana
- Data sources are provisioned by YAML files in `provisioning/datasources`: a `datasources` list (applied at startup, existing sources updated), `deleteDatasources` and `prune: true`; files may use `$ENV_VAR`. [DOC S-drqcqer6]
- Prometheus, Loki and Tempo are built-in core data sources; plugins are for sources not in core Grafana, so none is installed for these three. [DOC S-clqrp4oy]
- Loki and Tempo provisioning use `type: loki` with `url` port 3100 and `type: tempo` with port 3200, `access: proxy`; a provisioned data source cannot be edited in the UI. [DOC S-ffx6h64o, S-xpzp2unk]
- Any option is overridden with `GF_<SECTION>_<KEY>`, upper case with periods and dashes turned into underscores; the page says to override existing options, not add new ones. [DOC S-rmnhrvck]
- `http_port` defaults to 3000; the database defaults to embedded `sqlite3`, which the page does not recommend for production. [DOC S-rmnhrvck]
- Defaults file: `data = data`, SQLite `path = grafana.db` relative to data, `logs = data/log`, `provisioning = conf/provisioning`. [CODE S-47axdg7z: conf/defaults.ini#paths]
- Anonymous access is set in `[auth.anonymous]`: `enabled`, `org_name`, `org_role` (Viewer, Editor or Admin) and `device_limit`. [DOC S-nfb3ytwd]
- Anonymous access ships disabled (`enabled = false`), with org `Main Org.` and role `Viewer`. [CODE S-47axdg7z: conf/defaults.ini#auth.anonymous]
- Console logs: `[log] mode` defaults to `console file`; `[log.console] format` takes `text`, `console` or `json` and defaults to `console`. [DOC S-rmnhrvck]
- Grafana's console handler writes to `os.Stdout`, unlike Loki and Tempo. [CODE S-kx3xmf4o: pkg/infra/log/log.go#console handler]
- The Linux package data directory is not stated on the pages read; only the macOS path (`/usr/local/var/lib/grafana`) is. [UNK]

### Versions and licence
- Latest releases at 2026-10-11 (GitHub "Latest", not pre-release): Loki v3.7.8 (2026-09-17), Tempo v3.1.0 (2026-09-29), Grafana v13.2.3 (2026-09-29). [DOC S-44skzn3g, S-jm3q4nrg, S-nb36ls35]
- The Loki, Tempo and Grafana repositories carry the GNU AGPL v3 LICENSE. [DOC S-sqfw3i4b, S-ssnqxfb6, S-mri72d7r]

### How it fits
- Loki, Tempo and Grafana each run as one process on local disk with no object store, no Kafka and no external database (Loki `-target=all` with filesystem and TSDB, Tempo `-target=all` with `local`, Grafana SQLite), which suits a CPU-only offline host; the vendors mark filesystem and local storage as non-production. [DER S-g36sus36, S-gsjmowie, S-26xpxrvu, S-f2cwt6i6, S-rmnhrvck: monolithic modes and defaults]
- Loki keeps logs forever until `retention_enabled` and a period are set, while Tempo deletes after 14 days by default, so only Loki's disk growth is unbounded out of the box. [DER S-olwlij2r, S-a6zoom3b: Loki default 0s versus Tempo 336h]
- Disk must be sized to retention by the operator of the service, because neither store prunes by free space; Tempo's own sizing rule is ingested bytes per day times retention days. [DER S-gsjmowie, S-qk6tvbrf, S-f2cwt6i6: no disk-usage branch; sizing rule from the Tempo storage section]
- A reader of container output must read both streams: Loki and Tempo emit JSON on stderr, Grafana on stdout. [DER S-minmacwi, S-42oztc6t, S-kx3xmf4o: logger writers]

## Reference
- Related topic: `logs/otel-collector-receivers` (Collector receivers that read log streams like these).
- Loki: `operations/storage/retention.md`, `operations/storage/filesystem.md`, `shared/configuration.md` at v3.7.8; Tempo: `configuration/_index.md`, `configuration/manifest.md`, `reference-tempo-architecture/components/compaction.md` at v3.1.0; Grafana: `setup-grafana/configure-grafana/_index.md`, `administration/provisioning/index.md` at v13.2.3.
- Tempo 3.x configuration migration from 2.x is done with `tempo-cli migrate config`, per the 3.0 release notes (S-j4cjdcxk).

## Examples
- SNIPPET: Loki single binary on the filesystem with retention enabled and JSON logs; context: Loki v3.7.8; checked: no [DER S-olwlij2r, S-gsjmowie, S-jwoztkhv, S-yz3o3jci: keys and values taken from the retention page, the filesystem page, the shipped local config and the configuration reference]
```yaml
auth_enabled: false
server:
  http_listen_port: 3100
  log_format: json
common:
  instance_addr: 127.0.0.1
  path_prefix: /var/lib/loki
  storage:
    filesystem:
      chunks_directory: /var/lib/loki/chunks
      rules_directory: /var/lib/loki/rules
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory
schema_config:
  configs:
    - from: 2020-10-24
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h
compactor:
  working_directory: /var/lib/loki/compactor
  retention_enabled: true
  retention_delete_delay: 2h
  delete_request_store: filesystem
limits_config:
  retention_period: 744h
```
- SNIPPET: Tempo monolithic with OTLP on localhost, local blocks and a 14-day retention on the worker; context: Tempo v3.1.0; checked: no [DER S-f2cwt6i6, S-lajge47c, S-dvp4qcf3, S-a6zoom3b: receiver, storage and worker keys from the configuration page, the example and the worker config]
```yaml
server:
  http_listen_port: 3200
  log_format: json
distributor:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: "127.0.0.1:4317"
        http:
          endpoint: "127.0.0.1:4318"
storage:
  trace:
    backend: local
    wal:
      path: /var/tempo/wal
    local:
      path: /var/tempo/blocks
backend_worker:
  compaction:
    block_retention: 336h
```
- SNIPPET: Grafana data sources for Loki and Tempo, with JSON console logs set by environment variable `GF_LOG_CONSOLE_FORMAT=json`; context: Grafana v13.2.3; checked: no [DER S-ffx6h64o, S-xpzp2unk, S-rmnhrvck: provisioning shape and the GF_ naming rule]
```yaml
apiVersion: 1
datasources:
  - name: Loki
    type: loki
    access: proxy
    url: http://localhost:3100
  - name: Tempo
    type: tempo
    access: proxy
    url: http://localhost:3200
```
