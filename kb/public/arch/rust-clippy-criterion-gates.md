---
topic: arch/rust-clippy-criterion-gates
priority: P3
applies_to: "Clippy book at rust-clippy commit 51a5a0b (2026-10-11, Cargo 1.97 guidance); rustfmt README at commit ff02051 (2026-10-10); Criterion.rs 0.7.0 (book, README and manifest at the release tag)"
retrieved_utc: 2026-10-11
sources: [S-ly5mrvjt, S-beipcwki, S-j673gwjb, S-42h57lgl, S-ffsltmbi, S-4cuivnem, S-ba2xucuh, S-hqm43pk6, S-luxqgdxs, S-n33p6asx, S-a6r5knm6, S-wgv6gj2w, S-cqq3yuwa, S-zz5esdao, S-5b57smet]
status: partial
---

# Rust gates: cargo clippy -D warnings, cargo fmt --check, criterion benchmarks

## Summary
Clippy and rustfmt are pass/fail gates that need no tuning: Clippy exits non-zero once warnings are
elevated to errors (`-D warnings`, or `CARGO_BUILD_WARNINGS=deny` since Cargo 1.97), and
`cargo fmt -- --check` exits `1` when formatting would change. Criterion.rs benchmarks are a different
kind of check: they run on stable Rust and compare against a stored baseline, but Criterion's own FAQ
advises against relying on benchmark results from virtualised cloud CI, and the docs read here do not say
that a detected regression changes the exit status. For a PyO3 extension crate, Criterion also needs an
`rlib` next to a `cdylib` (see `python/maturin-pyo3-wheels.md` for the extension layout). The Python-side
counterpart of these gates is in `python/mypy-strict.md` and `python/ruff.md`.

## Facts
- `cargo clippy` runs the default lint set, the `clippy::all` group; Clippy can also run without Cargo
  as `clippy-driver`, taking the same arguments as `rustc`. Lint levels are set on the command line
  (`cargo clippy -- -Aclippy::style -Dclippy::perf`), in source, or in `Cargo.toml`. [DOC S-ly5mrvjt]
- Lint categories and default levels: `clippy::correctness` is deny; `suspicious`, `style`, `complexity`
  and `perf` are warn (together `clippy::all`); `pedantic`, `restriction`, `nursery` and `cargo` are allow
  by default. The README says the whole `restriction` category should not be enabled. [DOC S-beipcwki]
- To fail CI on lint output, warnings are elevated to errors, which makes Clippy exit with a code other
  than `0`. For Cargo 1.97 and later the page recommends `CARGO_BUILD_WARNINGS=deny cargo clippy` or
  `[build] warnings = "deny"` in `.cargo/config.toml`; for older Cargo, `cargo clippy -- -Dwarnings`,
  which the page says invalidates build caches and is therefore not recommended. [DOC S-ly5mrvjt]
- `-D warnings` and `CARGO_BUILD_WARNINGS=deny` fail on any warning, rustc's `dead_code` included; to
  fail only on Clippy lints the README suggests `#![deny(clippy::all)]` in the code or `-D clippy::all`
  on the command line. [DOC S-beipcwki]
- The CI chapter recommends running Clippy in CI with `-Dwarnings`, `RUSTFLAGS="-Dwarnings"` to apply the
  same to every `cargo` command, and Clippy from the same toolchain that compiles the crate; new lints
  land first in nightly Clippy. [DOC S-j673gwjb]
- The book's GitLab CI example uses the `rust:latest` image, a global `RUSTFLAGS: "-Dwarnings"` variable,
  `rustup component add clippy`, and the command `cargo clippy --all-targets --all-features`. [DOC S-42h57lgl]
- `cargo clippy --fix` applies suggestions automatically and implies `--all-targets`; by default
  `cargo clippy` also lints workspace members that a package depends on, and `-- --no-deps` limits it
  to the selected package. [DOC S-ly5mrvjt]
- Source-level control: `#![deny(clippy::all)]`, `#![warn(clippy::all, clippy::pedantic)]`, or
  `[lints.clippy]` with e.g. `enum_glob_use = "deny"` in `Cargo.toml`; a `deny` makes Clippy exit with an
  error code, which the page calls most useful in CI scripts. [DOC S-ffsltmbi]
- `clippy.toml` or `.clippy.toml` is searched in `CLIPPY_CONF_DIR`, then `CARGO_MANIFEST_DIR`, then the
  current directory, then each parent; it configures lint parameters (for example `msrv = "1.30.0"`),
  cannot allow or deny lints, and the page notes the configuration file is unstable and may be
  deprecated. The MSRV can also come from `rust-version` in `Cargo.toml`. [DOC S-ffsltmbi]
- `cargo fmt` formats all binary and library targets; with `--check` rustfmt exits `0` when nothing would
  change and `1` when it would, and prints the differences; the README's CI example is
  `cargo fmt --all -- --check`. In other modes rustfmt exits `1` on an error such as a parse failure. [DOC S-4cuivnem]
- `rustfmt.toml` or `.rustfmt.toml` is read from the project or a parent directory; `cargo fmt` takes
  `edition` and the style edition from `Cargo.toml`, plain `rustfmt` defaults to 2015, so both should be
  set in `rustfmt.toml` to get identical results. [DOC S-4cuivnem]
- Criterion.rs wiring (0.7.0 book): add `criterion` under `[dev-dependencies]`, declare
  `[[bench]] name = "my_benchmark"` with `harness = false` so the default harness does not conflict, put
  the file in `benches/`, generate the entry point with `criterion_group!` and `criterion_main!`, run
  `cargo bench`. The page still shows `criterion = "0.5.1"` in its example. [DOC S-ba2xucuh]
- The Criterion 0.7.0 manifest declares `rust-version = "1.80"` as the minimum supported Rust. [CODE S-5b57smet: Cargo.toml#package.rust-version]
- Criterion advertises that it works without installing nightly Rust, and its README lists `bencher`
  as "a port of the libtest benchmark runner to stable Rust", so the in-tree `#[bench]` harness is not
  available on stable. No page read here says "nightly-only" for `cargo bench` with libtest in those
  words, and the README prose still names Rust 1.59 as the minimum, older than the manifest value. [DER S-zz5esdao: README feature "Stable-compatible: benchmark your code without installing nightly Rust" and the bencher description]
- Criterion stores results in `target/criterion` and compares each run with the previous run; the HTML
  report is `target/criterion/reports/index.html`, needs the `html_reports` feature (the book says it
  must be enabled explicitly since 0.4.0), and is drawn with gnuplot if installed, else the `plotters`
  crate. [DOC S-a6r5knm6]
- The 0.7.0 manifest defines `html_reports` as an empty feature and a `stable` feature set that
  includes it; default features are `rayon`, `plotters` and `cargo_bench_support`; the manifest also
  carries a badge `maintenance = { status = "passively-maintained" }`. [CODE S-5b57smet: Cargo.toml#features]
- Command-line options: `--noplot` disables plot generation; `--save-baseline <name>` compares then
  overwrites the named baseline; `--baseline <name>` compares without overwriting and fails if the
  baseline lacks any benchmark; `--baseline-lenient <name>` does not fail on missing results and is
  described as useful for comparing branches in CI; `--load-baseline <name>`; `--quick` trades
  statistical guarantees for speed; `cargo test --benches` checks the benchmarks run without measuring
  (named as the CI-setting smoke test). [DOC S-hqm43pk6]
- With the default harness still enabled for a lib or bin target, `cargo bench -- --save-baseline x`
  makes the implicit libtest harness panic on the unknown option; workarounds are
  `cargo bench --bench my_benchmark -- <options>` or `bench = false` under `[lib]` and `[[bin]]`. [DOC S-luxqgdxs]
- The Criterion FAQ answers "How should I run Criterion.rs benchmarks in a CI pipeline?" with "You
  probably shouldn't (or, if you do, don't rely on the results)": virtualisation on cloud CI adds noise
  that the statistics cannot remove, and it names Iai (instruction counts under Cachegrind) as the more
  reliable alternative. If run anyway: benchmark the main branch first as baseline, then the pull
  request branch against it. [DOC S-luxqgdxs]
- Criterion reports changes statistically: it prints "Performance has regressed." or "improved" only
  with strong statistical evidence, treats differences within a noise threshold (default +-2%) as noise,
  and its "note of caution" describes a laptop switching between battery and wall power producing
  reported improvements and regressions without any code change. [DOC S-wgv6gj2w]
- The FAQ adds that a change can be reported even when nothing changed, because detection is
  statistical: lowering the false-detection rate also lowers sensitivity to small changes, and large
  suites should expect several spurious detections per run. [DOC S-luxqgdxs]
- Whether a "Performance has regressed" result makes `cargo bench` or the benchmark binary exit
  non-zero is not stated on the pages read, so a regression gate must parse output or compare
  Criterion's saved data itself. [UNK]
- Limits that matter for a library-plus-extension layout: benchmarks cannot be placed in `src/`, cannot
  call non-`pub` functions, cannot benchmark a binary crate, and need the crate to provide an `rlib`. [DOC S-n33p6asx]
- The FAQ says a crate configured as a `cdylib` must also generate an `rlib` to be benchmarked, and
  recommends a thin binary wrapper over a library crate for applications. [DOC S-luxqgdxs]
- A PyO3 extension crate declaring only `crate-type = ["cdylib"]` (as the kb's maturin example does)
  would therefore need `rlib` added to be benchmarked, or its pure-Rust core moved into a separate
  library crate that the extension wraps. [DER S-luxqgdxs, S-n33p6asx: Criterion's rlib requirement applied to the cdylib-only layout in python/maturin-pyo3-wheels.md]
- `cargo-criterion` is an experimental Cargo extension that can replace `cargo bench`
  (`cargo install cargo-criterion`, then `cargo criterion`); the book describes it as stable, says it
  did not support baselines, and says it adds machine-readable output via `--message-format=json`. [DOC S-cqq3yuwa]

## Reference
| Gate | Command | Exit status |
|---|---|---|
| Clippy, all warnings denied | `CARGO_BUILD_WARNINGS=deny cargo clippy --all-targets --all-features` (Cargo 1.97+) | non-zero on any warning |
| Clippy, older Cargo | `cargo clippy --all-targets --all-features -- -D warnings` | non-zero on any warning |
| Clippy, only Clippy lints | `cargo clippy -- -D clippy::all` | non-zero on a Clippy lint |
| rustfmt | `cargo fmt --all -- --check` | `0` formatted, `1` would change |
| Criterion smoke run | `cargo test --benches` | benchmarks run in test mode, no measurement |
| Criterion comparison | `cargo bench --bench NAME -- --baseline main` | not documented for regressions |

## Examples
- SNIPPET: a GitLab CI skeleton for the Rust gates (formatting, Clippy, benchmark smoke run); context: Clippy book at rust-clippy 51a5a0b, `rust:latest` image as in the book's GitLab page, job names are placeholders; checked: no [DER S-42h57lgl, S-4cuivnem, S-hqm43pk6: the book's GitLab job extended with the rustfmt `--check` command and the Criterion `cargo test --benches` smoke run]
```yaml
variables:
  RUSTFLAGS: "-Dwarnings"

rust_fmt:
  image: rust:latest
  script:
    - rustup component add rustfmt
    - cargo fmt --all -- --check

rust_clippy:
  image: rust:latest
  script:
    - rustup component add clippy
    - cargo clippy --all-targets --all-features

rust_bench_smoke:
  image: rust:latest
  script:
    - cargo test --benches
```
- SNIPPET: the Cargo.toml entries and benchmark file for one Criterion benchmark; context: Criterion.rs 0.7.0 getting-started page (the dependency version is the one the page prints), `mycrate` is a placeholder; checked: no [DER S-ba2xucuh: the getting-started `Cargo.toml` and `benches/my_benchmark.rs` content]
```toml
[dev-dependencies]
criterion = "0.5.1"

[[bench]]
name = "my_benchmark"
harness = false
```
```rust
use criterion::{criterion_group, criterion_main, Criterion};
use std::hint::black_box;
use mycrate::fibonacci;

fn criterion_benchmark(c: &mut Criterion) {
    c.bench_function("fib 20", |b| b.iter(|| fibonacci(black_box(20))));
}

criterion_group!(benches, criterion_benchmark);
criterion_main!(benches);
```
- SNIPPET: comparing a branch against a stored baseline of the main branch; context: Criterion.rs 0.7.0 command-line options page and the FAQ's main-then-branch procedure, benchmark name `my_benchmark` is a placeholder; checked: no [DER S-hqm43pk6, S-luxqgdxs: `--save-baseline` and `--baseline` options applied to the FAQ's two-step procedure]
```console
$ git checkout main
$ cargo bench --bench my_benchmark -- --save-baseline main
$ git checkout feature
$ cargo bench --bench my_benchmark -- --baseline main
```
