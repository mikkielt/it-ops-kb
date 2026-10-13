---
topic: logs/python-rust-json-stdout-logs
priority: P3
applies_to: "Python 3.14 logging (CPython 3.14.7 docs); Rust tracing-subscriber 0.3.23 with its `json` feature"
retrieved_utc: 2026-10-13
sources: [S-7v3dgzq4, S-6l23ubol, S-2ciukzt5, S-zzvrhdyd, S-fmhy7rbl, S-bkz7cb64, S-md4evt46, S1720]
status: partial
---

# JSON log lines on stdout from a Python and a Rust service

## Summary
Neither runtime writes JSON log lines to stdout by default. Python's `logging.StreamHandler` writes to `sys.stderr` unless given a stream, the standard library has no JSON formatter (the cookbook's structured example prints `message >>> {json}`), and the default formatter appends a traceback after the message, so a one-object-per-line output needs a small `Formatter` subclass that calls `json.dumps`. In Rust, `tracing-subscriber`'s `fmt` subscriber already writes to stdout and its `json` feature (off by default) emits newline-delimited JSON objects with `timestamp`, `level`, `fields` and `target`. The two field layouts differ, so a shared log schema is something the Python formatter has to be written to match.

## Facts
### Python (`logging`)
- `StreamHandler` sends records to any object with `write` and `flush`; when no stream is given it uses `sys.stderr`, so `StreamHandler(sys.stdout)` has to be asked for. [DOC S-7v3dgzq4]
- The cookbook's structured-logging recipe wraps a message and keyword arguments in a class whose `__str__` returns the message, then ` >>> `, then `json.dumps` of the keyword arguments; the example output is `message 1 >>> {"fnum": 123.456, ...}`, which is text followed by JSON, not one JSON document per line. [DOC S-2ciukzt5]
- `Formatter.format` merges the message arguments, and when a record has exception information that text is "appended to the message", cached in `exc_text`; the default output of a logged exception therefore spans several lines. [DOC S-6l23ubol]
- `Formatter.formatException` returns the exception information as a string built by `traceback.print_exception`, and `LogRecord.getMessage` returns the message with its arguments merged, so a custom formatter can put both into JSON string values. [DOC S-6l23ubol]
- `json.dumps` inserts no newlines when `indent` is `None` (the default), and with `ensure_ascii=False` it still escapes quotation mark, reverse solidus and the control characters U+0000 to U+001F, so a dumped object is always one line. [DOC S-zzvrhdyd]

### Rust (`tracing-subscriber`)
- `tracing-subscriber` 0.3.23's default features are `smallvec`, `fmt`, `ansi`, `tracing-log` and `std`; `json` is a separate feature that pulls in `tracing-serde`, `serde` and `serde_json`. [CODE S-md4evt46: Cargo.toml#features]
- `SubscriberBuilder::json()` exists only with the `json` feature and its doc says it sets the subscriber "to use a JSON formatter". [CODE S-fmhy7rbl: src/fmt/mod.rs#SubscriberBuilder::json]
- The `fmt` subscriber's writer type defaults to `fn() -> io::Stdout`, its module doc says events are logged "to stdout", and `with_writer(io::stderr)` is the documented way to switch. [CODE S-fmhy7rbl: src/fmt/mod.rs#SubscriberBuilder::with_writer]
- The `Json` format is described as the newline-delimited JSON log format for machine consumers, not for reading; its sample lines have the keys `timestamp`, `level`, `fields` (with `message` inside), `target` and, inside spans, `spans`. [CODE S-bkz7cb64: src/fmt/format/json.rs#Json]
- Options of `Json`: `flatten_event` (off by default, event fields stay under `fields`), `with_current_span` and `with_span_list` (both on by default). [CODE S-bkz7cb64: src/fmt/format/json.rs#Json]

### How it fits (a Python shell and a Rust core on one host)
- The defaults point at different streams, `sys.stderr` for Python and stdout for Rust, so a collector or container log driver that reads only stdout sees the Rust core and misses the Python shell until `StreamHandler(sys.stdout)` is set. [DER S-7v3dgzq4, S-fmhy7rbl: documented default streams]
- A line-per-object contract holds on both sides only after a step on the Python side: the formatter's `format` must return `json.dumps` of a dict and carry the exception text as a field, because the default formatter and the cookbook recipe both emit non-JSON text. [DER S-2ciukzt5, S-6l23ubol, S-zzvrhdyd: default exception appending, cookbook output shape, single-line dumps]
- Field names are the library's on the Rust side (`level` in capitals as in the sample, the message under `fields.message`) and the author's on the Python side, so the Python formatter should emit the same top-level keys, or a collector must map both layouts. [DER S-bkz7cb64, S-6l23ubol: Rust sample keys; Python record attributes]
- Twelve-factor treats the event stream as written, unbuffered, to stdout and routing as the environment's job, which is the contract both settings above satisfy. [DER S1720, S-7v3dgzq4, S-fmhy7rbl: the factor's wording and the two stream settings]
- Whether a Python process writing to a pipe flushes each record and whether a `tracing-subscriber` stdout writer holds records back on exit are not stated on the pages read; the first is `StreamHandler.flush`'s contract only, and the non-blocking appender crate was not read. [UNK]
- Where a Rust panic message goes when a `tracing` JSON subscriber is the only one installed is not stated on the pages read. [UNK]

## Reference
| | Python `logging` (3.14.7) | Rust `tracing-subscriber` (0.3.23) |
|---|---|---|
| Default stream | `sys.stderr` | stdout |
| Choose stdout | `StreamHandler(sys.stdout)` | default; `with_writer(io::stderr)` switches away |
| JSON output | none built in; `Formatter` subclass + `json.dumps` | `json` feature, `.json()` on the builder |
| Exception text | default formatter appends a traceback; `formatException` gives it as a string | not read for this topic |
| One object per line | yes with `indent=None` | yes, newline-delimited |

Related: `arch/twelve-factor-readiness.md` (the logs factor), `logs/otel-log-data-model.md` and `logs/ecs-log-fields.md` (field names a shared schema can follow), `logs/otel-collector-otlp-pipeline.md` (the collector's own JSON on stdout) and `python/stdlib-argparse-json.md` (JSON output of command-line tools).

## Examples
- SNIPPET: a `logging.Formatter` that writes one JSON object per record to stdout, exception text in a field; context: Python 3.14 standard library only, field names are an example; checked: syntax [DER S-6l23ubol, S-7v3dgzq4, S-zzvrhdyd: `format`, `formatException`, `getMessage`, `StreamHandler(stream)`, `json.dumps`]

```python
import json
import logging
import sys


class JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonLineFormatter())
root = logging.getLogger()
root.addHandler(handler)
root.setLevel(logging.INFO)
```

- SNIPPET: the Rust side with the same stream and one JSON object per event; context: `tracing-subscriber` 0.3.23 with `features = ["json"]` in Cargo.toml and the `tracing` crate for the macros; checked: no [DER S-fmhy7rbl, S-bkz7cb64, S-md4evt46: `fmt()`, `.json()` and the `json` feature as the three sources name them]

```rust
tracing_subscriber::fmt().json().init();
tracing::info!(request_id = "PL-REQ-0001", "request handled");
```
