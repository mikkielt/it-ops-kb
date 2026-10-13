---
topic: agents/onnx-runtime-rust-ort
priority: P3
applies_to: "ort 2.0.0-rc.13 (pykeio/ort, ONNX Runtime 1.28 API), ONNX Runtime 1.28.3 release assets, ONNX 1.23.2 model format, Hugging Face Hub API as of 2026-10-11"
retrieved_utc: 2026-10-13
sources: [S-wl3gkg3g, S-d7xuprcc, S-5bx2p3mo, S-miwhfdzy, S-7zyahsl3, S-jdu5egnj, S-bzhegec5, S-msk5qtcf, S-jpjnjgqg, S-pwbxp7jw, S-gs7u2ou5, S-m5r2fcso, S-mw6rc3qq, S-o3nqheje, S-vzhh6a43, S-5xaderxo, S-3mftdvfg, S-ktoxup5h, S-xt54q2gr, S-l3go6sje, S-6z4pv23l, S-omvw5ahk, S-45rrlyyd, S-cxzftyij, S-7srl2gyq, S-ah7l36rr, S-togouwq3, S-u3hzriiy, S-x6bpplvz, S-a7uyxlhd, S-atc7uhx5, S-xjm5bsys, S-gzswlsft, S-i65jlupl, S-ujreltcp, S-yliumtdz, S-co3g3h4o, S-hmcb2gfz, S-ixcjfodz, S-rlepjcn5, S-7o37zl5s, S-anwc4b5l, S-y7gpyp7l, S-rmgaatpo]
status: partial
---

# ONNX Runtime from Rust with the `ort` crate: status, binaries, CPU-only builds, session options, pinned model files

## Summary
`ort` is the Rust binding for Microsoft's ONNX Runtime. At retrieval its only installable versions on crates.io are the `2.0.0-rc.*` release candidates (latest `2.0.0-rc.13`, targeting ONNX Runtime 1.28); the project's own docs call that version production-ready and tell users to pin it exactly. By default a build downloads a statically linked, hash-checked ONNX Runtime archive from the vendor's CDN, so an offline or hash-pinned build must switch that off (`load-dynamic`, `ORT_LIB_PATH`, or a pre-filled cache). Accelerator execution providers are separate Cargo features, none on by default, and registration failures fall back to the CPU silently unless `error_on_failure()` is set. The `none` ONNX Runtime build for Linux has no accelerator; the default Windows and macOS builds carry DirectML and CoreML. Session options give thread counts and graph optimisation level, but `with_deterministic_compute` is documented upstream for GPU kernels only. ONNX files carry producer and version metadata but no content hash, so a model is pinned by repository commit and file sha256.

## Facts

### What `ort` is and where it stands
- `ort` is a Rust interface for hardware-accelerated inference and training on ONNX models; its README says it is "primarily a wrapper for Microsoft's ONNX Runtime library" and that it also supports other pure-Rust runtimes. [DOC S-jpjnjgqg]
- crates.io lists `2.0.0-rc.13` (published 2026-07-28) as the highest version and has no stable version (`max_stable_version` is null): the only versions not yanked are `2.0.0-rc.0` (2024-02-06) to `2.0.0-rc.13`, and every `1.x` release and the `2.0.0-alpha.*` ones are yanked. [DOC S-msk5qtcf]
- The docs site for `2.0.0-rc.13` says "This version is production-ready and we recommend new & existing projects use it", and its install snippet pins the exact version `ort = "=2.0.0-rc.13"`; the README names no release-candidate caveat. [DOC S-gs7u2ou5]
- The manifest of tag `v2.0.0-rc.13` declares `rust-version = "1.88"`, edition 2024, `license = "MIT OR Apache-2.0"` and a maintenance badge `actively-developed`. [CODE S-pwbxp7jw: Cargo.toml#package]
- The minimum supported Rust version rose with the release candidates: 1.70 for `rc.0` to `rc.9`, 1.81 for `rc.10`, 1.88 for `rc.11` to `rc.13`; each of these versions is listed with the licence `MIT OR Apache-2.0`. [DOC S-msk5qtcf]
- Version mapping: `ort` v2.0.0 and later uses ONNX Runtime v1.28.0 (ONNX opset 24, ML opset 4); the used ONNX Runtime version "may occur on minor version updates", and the docs advise a tilde requirement on the minor version to hold it. [DOC S-3mftdvfg]
- The docs say `ort` supports ONNX Runtime 1.17 to 1.28, with the minimum API version chosen by the `api-17` to `api-28` features, and that the latest level, `api-28`, is on by default; the manifest's `default` list at the same tag contains `api-27`, not `api-28`, so the docs and the manifest disagree on the default API level. [DOC S-o3nqheje]
- With `load-dynamic`, `ort` compares the minor version of the loaded library with the API minor it was built for: a lower library version is an error (`BadVersion`), a higher one only logs that compatibility problems are possible. [CODE S-45rrlyyd: src/lib.rs#load_dynamic::init]

### Where the ONNX Runtime binaries come from
- Default features are `std`, `ndarray`, `tracing`, `download-binaries`, `tls-native`, `copy-dylibs` and `api-27`; `load-dynamic`, `pkg-config`, `lax-feature-matching`, `fetch-models`, `tls-rustls` and `tls-native-vendored` are opt-in. [CODE S-pwbxp7jw: Cargo.toml#features]
- `download-binaries` (default) "Downloads prebuilt binaries from pyke's CDN service for supported platforms" and needs a TLS feature (`tls-native` by default, `tls-rustls`, `tls-native-vendored`); `copy-dylibs` (default) symlinks, or on Windows copies, dynamic libraries such as the CUDA provider's next to the build output. [DOC S-m5r2fcso]
- The build script refuses to compile `download-binaries` without a TLS feature, fetches over HTTPS only with one redirect allowed, honours proxy environment variables and caps the download at 1 GiB; its error text for a 404 or 410 from the CDN says the version is no longer supported and points to custom linking. [CODE S-7srl2gyq: ort-sys/build/download/mod.rs#fetch_file]
- `dist.tsv` at the tag has 15 rows of target triple, feature set, `cdn.pyke.io` URL (path component `ms@1.28.0`) and SHA-256: Linux x86_64 has `none`, `webgpu`, `nvrtx` and `cuda13,tensorrt,nvrtx`; Linux aarch64 only `none`; Windows aarch64 only `directml`; Windows `x86_64-pc-windows-msvc` has four rows, `directml`, `webgpu` only (asset `ms@1.28.0/x86_64-pc-windows-msvc+webgpu.tar.lzma2`, no `directml`), `nvrtx,directml` and `cuda13,tensorrt,nvrtx,directml`; every Apple row includes `coreml`. [CODE S-togouwq3: ort-sys/build/download/dist.tsv#x86_64-unknown-linux-gnu]
- The build matches the enabled EP features to a row of that table; an inexact match is a link-time error unless `lax-feature-matching` is on, and when CUDA or TensorRT is requested it selects a `cuda13` build (CUDA 12 builds are not shipped). [CODE S-ah7l36rr: ort-sys/build/download/resolve.rs#resolve_dist]
- With no accelerator feature enabled no row matches exactly on Windows, so the resolver takes the first row of the target in table order: a default `x86_64-pc-windows-msvc` build takes the first, `directml` row and carries DirectML, while a build with only `webgpu` enabled matches the `webgpu` row exactly, which has no `directml`. [CODE S-ah7l36rr: ort-sys/build/download/resolve.rs#resolve_dist]
- The build script hashes the downloaded stream and compares it with the table's SHA-256, extracts to `<cache>/dfbin/<target>/<hash>` and skips the download when that directory exists; the result is linked as the static library `onnxruntime`. [CODE S-cxzftyij: ort-sys/build/main.rs#main]
- The cache directory is `ORT_CACHE_DIR` if set, else `$XDG_CACHE_HOME` when it is an absolute path or `~/.cache/ort.pyke.io` on Linux, `~/Library/Caches/ort.pyke.io` on macOS and a local-app-data `ort.pyke.io` folder on Windows. [CODE S-x6bpplvz: ort-sys/src/internal/dirs.rs#cache_dir]
- The variables `CARGO_NET_OFFLINE`, `ORT_SKIP_DOWNLOAD` and `ORT_OFFLINE` (value `1` or `true`) skip the download, and `ORT_LIB_PATH` or `ORT_LIB_LOCATION`, `ORT_LIB_PROFILE`, `ORT_PREFER_DYNAMIC_LINK`, `ORT_CXX_STDLIB` and `ORT_CUDA_VERSION` steer linking. [CODE S-u3hzriiy: ort-sys/build/vars.rs#SKIP_DOWNLOAD]
- In the build script, `DOCS_RS` or the `disable-linking` feature (which `load-dynamic` and `alternative-backend` switch on) returns before anything is linked or downloaded; then come `pkg-config`, the `ORT_LIB_PATH` directory, and only last the skip variables and the download. [CODE S-cxzftyij: ort-sys/build/main.rs#main]
- The linking page prefers static linking of a custom ONNX Runtime build (`ORT_LIB_PATH`, point it at the `.a`/`.lib` directory), offers compile-time dynamic linking with `ORT_PREFER_DYNAMIC_LINK=1`, and recommends `load-dynamic`, where `ORT_DYLIB_PATH` or `ort::init_from(path)` names the library and must run before any other `ort` call. [DOC S-mw6rc3qq]
- When `ORT_DYLIB_PATH` is unset or empty, `load-dynamic` falls back to `libonnxruntime.so`, `onnxruntime.dll` or `libonnxruntime.dylib`; a relative path is tried against the executable's directory first. [CODE S-45rrlyyd: src/lib.rs#setup_api]
- The vendor's prebuilt x86-64 binaries need an x86-64-v3 CPU (Haswell or later, any Ryzen), the Linux ones are built with Clang and depend on `libc++`, and since `rc.12` they carry GitHub build attestations checkable with `gh attestation verify --owner pykeio`. [DOC S-5xaderxo]
- `fetch-models` (off by default) adds `commit_from_url`, which downloads a model at run time into `<cache>/models/` under the SHA-256 of the URL, not of the bytes, and the code read performs no hash check of the downloaded content. [CODE S-6z4pv23l: src/session/builder/impl_commit.rs#download_model]
- Cargo's own dependency fetch is separate: `cargo vendor` copies all crates.io and git dependencies into a directory and prints the configuration that makes Cargo use it. [DOC S-y7gpyp7l]
- The ONNX Runtime project publishes its own CPU archives per release, for example `onnxruntime-linux-x64-1.28.3.tgz` and `onnxruntime-linux-aarch64-1.28.3.tgz`, with a SHA-256 digest per asset on the release page; the CUDA variants have separate `gpu_cuda12`/`gpu_cuda13` archives. [DOC S-atc7uhx5]

### Accelerator execution providers and CPU-only builds
- Accelerators are Cargo features of the manifest, none in `default`: `cuda`, `tensorrt`, `openvino`, `onednn`, `directml`, `nnapi`, `coreml`, `xnnpack`, `rocm`, `acl`, `armnn`, `tvm`, `migraphx`, `rknpu`, `vitis`, `cann`, `qnn`, `webgpu`, `azure`, `nvrtx`, `vsinpu`. [CODE S-pwbxp7jw: Cargo.toml#features]
- Each provider type is compiled only with its feature (`#[cfg(feature = "cuda")] pub mod cuda`), while `ep::CPU` always exists and always reports itself available, so without the feature a provider type cannot be named in code. [CODE S-ktoxup5h: src/ep/mod.rs#CPU]
- The release notes of `2.0.0-rc.13` say: "ort will now throw an error at link time if download-binaries is enabled and no binaries contain all of the requested EPs", where earlier versions silently built a CPU-only binary. [DOC S-a7uyxlhd]
- ONNX Runtime's own provider list includes a "Cloud - Azure" provider beside the hardware ones, and its docs say a package can be built with any combination of providers together with the default CPU provider. [DOC S-yliumtdz]
- Registration order is the priority order; a provider that cannot take an operator falls back to the next one or the CPU, and the docs state "ort will silently fail and fall back to executing on the CPU if all execution providers fail to register". [DOC S-vzhh6a43]
- In code, `ExecutionProviderDispatch::fail_silently()` is the default (log the error, continue), and `error_on_failure()` makes `with_execution_providers` return the registration error; `ExecutionProvider::is_available` only says ONNX Runtime was compiled with the provider, not that it can run. [CODE S-ktoxup5h: src/ep/mod.rs#ExecutionProviderDispatch]
- `SessionBuilder::new` sets an automatic device selection policy `MaxEfficiency` when `api-22` or later is on, and `with_execution_providers` or `with_auto_device` overrides it. [CODE S-omvw5ahk: src/session/builder/mod.rs#SessionBuilder::new]
- ONNX Runtime's automatic selection offers devices from execution provider libraries registered with the environment ("plugin" libraries); the page's example registers one before setting a policy. [DOC S-co3g3h4o]
- The CPU provider is "powered by MLAS"; `ep::CPU::default().with_arena_allocator(bool)` toggles the memory arena and its registration cannot fail. [CODE S-xt54q2gr: src/ep/cpu.rs#CPU]

### Session options for CPU inference
- ONNX Runtime defaults for the CPU provider: intra-op threads 0 (one per physical core), sequential execution mode, graph optimisation `ORT_ENABLE_ALL`, thread spinning on; inter-op threads only matter in parallel mode, and explicitly set thread counts get no core affinity. [DOC S-i65jlupl]
- In the C API header at v1.28.3, `SetIntraOpNumThreads` has "no effect" on thread count when ONNX Runtime was built with OpenMP, `SetInterOpNumThreads` is ignored in sequential mode, and `SetDeterministicCompute` defaults to false and "will enable deterministic compute for GPU kernels where possible", most likely at a performance cost. [DOC S-gzswlsft]
- `ort` wraps these as `with_intra_threads`, `with_inter_threads`, `with_parallel_execution` (disabled by default), `with_optimization_level` (`Disable`, `Level1`, `Level2`, `Level3`, `All` mapping to basic, extended, layout and all), `with_optimized_model_path` and `with_deterministic_compute`. [CODE S-l3go6sje: src/session/builder/impl_options.rs#SessionBuilder]
- Graph optimisation is online by default and can be saved offline; an offline-optimised file must be used on the same providers and hardware class, and with layout optimisations on, only on CPUs with the same instruction sets (the page's example is AVX2). [DOC S-ujreltcp]
- Whether CPU kernels in ONNX Runtime 1.28 give bit-identical outputs across intra-op thread counts, CPU microarchitectures or the optimisation levels is not stated on the pages read, and the `SetDeterministicCompute` text names GPU kernels only. [UNK]
- Whether the vendor's prebuilt CPU binary is built with OpenMP, which would make `with_intra_threads` have no effect, is not stated on the pages read. [UNK]

### Model files pinned by hash
- ONNX's `ModelProto` has `ir_version` (must be present), `opset_import` (at least one entry), `producer_name` and `producer_version` (should be present), `domain`, `model_version`, `doc_string` and `metadata_props` (named string pairs); the field list has no hash or signature of the model itself. [DOC S-hmcb2gfz]
- A tensor stored outside the model uses `external_data` keys `location`, `offset`, `length` and an optional `checksum` that is a SHA-1 digest of the file at `location`, so such a model is several files to pin. [DOC S-hmcb2gfz]
- The Hub API returns the repository commit as `sha` and, per Git LFS file, `lfs.sha256` and the size; non-LFS files such as the card and the JSON configs carry only a git blob id. For `onnx-community/gliner_multi-v2.1` at commit `6ddaeb9413b0e71ad8457da1aab378a165b24058`, `onnx/model_int8.onnx` is `995058c82c5f570601dd8a0ba74ee60a392f764268bc5f628455e44dd3b476ec`. [DOC S-ixcjfodz]
- A Git LFS pointer records the content as `oid sha256:<hex>`, and "only `sha256` is supported"; the Hub's OpenAPI description of the tree endpoint has the same value as `lfs.oid`. [DOC S-anwc4b5l]
- In that repository several file names are the same bytes: `model_int8.onnx` and `model_quantized.onnx` share one sha256, as do `model_q4.onnx` and `model_bnb4.onnx`, so a pin names the path and the digest. [DOC S-ixcjfodz]
- Model-card metadata carries the licence in a `license` key, with `other` plus `license_name` and `license_link` for custom terms; the card of the ONNX export above has only `base_model` and `library_name`, while its base model `urchade/gliner_multi-v2.1` declares `apache-2.0`. [DOC S-7o37zl5s, S-ixcjfodz, S-rmgaatpo]
- `SessionBuilder::commit_from_file` checks the path exists and hands it to ONNX Runtime; `commit_from_memory(&[u8])` loads from a byte slice, and `commit_from_memory_directly` borrows the slice and sets the use-ORT-bytes-directly options for the `.ort` format. [CODE S-6z4pv23l: src/session/builder/impl_commit.rs#commit_from_memory]
- The docs' examples load from a file with `commit_from_file`; the pages read give no recommendation between file and memory loading. [DOC S-gs7u2ou5]

### Feature unification: how a dependency turns on an `ort` provider
- Cargo builds a dependency that several packages use once, with the union of all features enabled on it by any of them; the book's example has `foo` enable `fileapi` and `handleapi` of `winapi` and `bar` enable `std` and `winnt`, giving a build with all four. [DOC S-wl3gkg3g]
- A package turns on a dependency's feature either in the dependency declaration (`features = [...]`) or in its own `[features]` table with the `"package-name/feature-name"` syntax; a `default-features = false` entry "may not ensure the default features are disabled" when another dependency names the crate without it. [DOC S-wl3gkg3g]
- When several workspace packages are built in one command (`--workspace` or several `-p` flags) the features of all their dependencies are unified; keeping them apart takes separate `cargo` invocations. [DOC S-d7xuprcc]
- The version `"2"` resolver does not unify features across these boundaries: platform-specific dependencies for targets not being built, build-dependencies and proc-macros with normal dependencies, and dev-dependencies unless the target being built needs them; everything else is still unified. [DOC S-wl3gkg3g]
- `gline-rs` 1.1.0 declares `ort` without `default-features = false` and forwards its own features to provider features of `ort` (`cuda = ["ort/cuda"]`, `tensorrt`, `directml`, `coreml`, `openvino` and others), and at `v2.0.0-rc.13` `ort`'s `cuda` is `["ort-sys/cuda"]`; by the union rule a build that enables `gline-rs/cuda` enables the CUDA provider feature of the one `ort` and `ort-sys` in the build, whichever package asked. The `ort` manifest at the `rc.9` pin that `gline-rs` names was not read, so the second hop is shown for `rc.13` only. [CODE S-bzhegec5: Cargo.toml#features; CODE S-pwbxp7jw: Cargo.toml#features]
- `cargo tree -e features` prints which package enabled each feature, `cargo tree -e features -i ort` inverts the tree so it shows how features flow into `ort`, and `cargo tree -f "{p} {f}"` prints the comma-separated features enabled on each package. [DOC S-wl3gkg3g]
- The `cargo tree` command page describes the same: `-e features` shows the features each dependency enables, `-i` shows how features flow into a package, and the `{f}` format placeholder is the comma-separated list of enabled features. [DOC S-5bx2p3mo]

### Two exact pins of `ort` in one build
- Cargo unifies the requirements two packages put on one crate when the versions are SemVer-compatible, and "will error" when two compatible versions cannot be unified; the book's example is one package requiring `log = "=0.4.11"` and another `log = "=0.4.8"`. Versions are compatible when their left-most non-zero major, minor or patch component is the same. [DOC S-miwhfdzy, S-7zyahsl3]
- In the resolver, the key that allows one activated version per crate is the package name, a `SemverCompatibility` value and the source; the value is `Major` when the major number is non-zero, else `Minor` when the minor is non-zero, else `Patch`, and no pre-release part is read, so `2.0.0-rc.9` and `2.0.0-rc.13` of one crate on one source both map to `Major(2)`. Implementation at Cargo @797e8a9, not a documented promise. [CODE S-jdu5egnj: core/resolver/types.rs#SemverCompatibility, ActivationsKey, PackageId::as_activations_key]
- `gline-rs` 1.1.0's manifest requires both `ort` and `ort-sys` at `=2.0.0-rc.9` (the `ort-sys` line points to an issue of the `ort` repository), and the `ort` `v2.0.0-rc.13` manifest requires `ort-sys` at `=2.0.0-rc.13`, so the two pins conflict on `ort-sys` as well as on `ort`. [CODE S-bzhegec5: Cargo.toml#dependencies; S-pwbxp7jw: Cargo.toml#dependencies]
- Whether the code of `gline-rs` 1.1.0 compiles against `ort` `2.0.0-rc.13` if its pin were loosened is neither stated by either project nor tested here. [UNK]

### How it fits (self-hosted corpus service, CPU-only, offline, hash-pinned)
- The default `ort` build fetches an archive at build time, so a build with no network needs one of three routes that the build script's order allows: `load-dynamic` with a library the operator supplies, `ORT_LIB_PATH` pointing at a local build, or a cache directory already filled (`ORT_CACHE_DIR`, no skip variable set, because the skip variables are checked before the cache). [DER S-cxzftyij, S-u3hzriiy, S-x6bpplvz, S-mw6rc3qq: build-script order and cache lookup read together]
- For a hash-pinned supply chain the `load-dynamic` route lets the deployer take the ONNX Runtime archive from the upstream release, verify its published digest and place the library next to the binary, instead of trusting the pyke CDN row in `dist.tsv`; the cost is that the build then ships no library and the runtime path must be set. [DER S-atc7uhx5, S-mw6rc3qq, S-togouwq3: digest on the release page versus `dist.tsv` row]
- The `ort` binaries use ONNX Runtime 1.28.0 (`ms@1.28.0` in the table) while upstream has since released 1.28.3, a patch release listing memory-safety and model-validation fixes, and 1.31.0; a `load-dynamic` build accepts a newer minor library with only a log line, so patches can be taken without a new `ort` release. [DER S-togouwq3, S-atc7uhx5, S-xjm5bsys, S-45rrlyyd: table version versus release pages and loader check]
- A CPU-only build leaves every accelerator feature off, uses the Linux `none` binary or a CPU archive, and registers `ep::CPU` with `error_on_failure()`; on Windows and macOS the downloaded default binaries still contain DirectML and CoreML code, and no setting found refuses a non-CPU provider at run time beyond not compiling or not registering one. [DER S-pwbxp7jw, S-togouwq3, S-5xaderxo, S-ktoxup5h: feature list, table rows and provider gating]
- Because a provider feature is additive and unifies, "no accelerator feature in my manifest" does not make a CPU-only build: a dependency's own feature or a forwarded `ort/cuda` can enable one. With `download-binaries` the enabled set selects the prebuilt archive (and an unmatched set is a link-time error since `rc.13`), so the check belongs in CI: `cargo tree -e features -i ort` and `-i ort-sys` must show none of the accelerator features, and at run time `is_available` on a provider type reports whether ONNX Runtime was compiled with it. [DER S-wl3gkg3g, S-5bx2p3mo, S-bzhegec5, S-pwbxp7jw, S-ah7l36rr, S-a7uyxlhd, S-ktoxup5h: union rule, tree options, forwarded features, archive selection and the availability check]
- Because every installable `ort` 2.x version is a release candidate and the default API level differs between docs and manifest, a service should pin `=2.0.0-rc.13` and name its `api-*` feature itself rather than rely on the default. [DER S-msk5qtcf, S-gs7u2ou5, S-o3nqheje, S-pwbxp7jw: no stable version, exact pin advice, doc and manifest defaults]
- A service that pins `ort = "=2.0.0-rc.13"` cannot also depend on `gline-rs` 1.1.0 in one Cargo build: an exact requirement admits one version, `=2.0.0-rc.9` and `=2.0.0-rc.13` of `ort` (and of `ort-sys`) fall in the same compatibility class, and the resolver allows one activated version per class, so it reports a conflict instead of building two copies, as the book's `log` example does. A `package = "ort"` rename does not change this, because the key is built from the package's name, not the local one. One of the two pins has to change: the service takes `=2.0.0-rc.9` and that release's API, or it leaves `gline-rs` out. [DER S-bzhegec5, S-pwbxp7jw, S-miwhfdzy, S-jdu5egnj: two exact pins of one crate with one resolver key]
- The Multiversioning page's `default-features = false` example lists `download-binaries` with no TLS feature, which the build script's `compile_error!` rejects; a build that keeps `download-binaries` with default features off must add one `tls-*` feature. [DER S-o3nqheje, S-7srl2gyq, S-m5r2fcso: docs example versus the build script's TLS check]
- A model file is pinned by repository commit, path and sha256; reading the file once, hashing those bytes and loading the same bytes with `commit_from_memory` removes the gap between the check and the load that `commit_from_file` leaves, and ONNX's `producer_name`, `model_version` and `metadata_props` stay descriptive, not integrity data. [DER S-ixcjfodz, S-anwc4b5l, S-hmcb2gfz, S-6z4pv23l: LFS digest, ONNX field list, load methods]
- The prebuilt x86-64 baseline and `libc++` dependency are host requirements to check before deployment, since a pre-Haswell host cannot run the vendor's binaries. [DER S-5xaderxo: baseline stated for all prebuilt x86-64 binaries]

## Reference
| Item | Value at `v2.0.0-rc.13` | Where |
|---|---|---|
| Crate | `ort` (and `ort-sys`), `2.0.0-rc.13`, MSRV 1.88, `MIT OR Apache-2.0` | Cargo.toml, crates.io |
| ONNX Runtime | 1.28 (`ms@1.28.0` binaries); accepts library minor 1.28 or newer with `load-dynamic` | version mapping, `dist.tsv` |
| Default features | `std`, `ndarray`, `tracing`, `download-binaries`, `tls-native`, `copy-dylibs`, `api-27` | manifest |
| Linking without the CDN | `load-dynamic` (nothing linked or downloaded), `ORT_LIB_PATH`, `pkg-config` (tried first, falls through when nothing is found) | build script |
| Download skip variables | `CARGO_NET_OFFLINE`, `ORT_SKIP_DOWNLOAD`, `ORT_OFFLINE` | `vars.rs` |
| Link variables | `ORT_LIB_PATH` / `ORT_LIB_LOCATION`, `ORT_LIB_PROFILE`, `ORT_PREFER_DYNAMIC_LINK`, `ORT_DYLIB_PATH` (run time), `ORT_CACHE_DIR` | `vars.rs`, `dirs.rs`, `lib.rs` |
| Accelerator features | `cuda`, `tensorrt`, `openvino`, `onednn`, `directml`, `nnapi`, `coreml`, `xnnpack`, `rocm`, `acl`, `armnn`, `tvm`, `migraphx`, `rknpu`, `vitis`, `cann`, `qnn`, `webgpu`, `azure`, `nvrtx`, `vsinpu` | manifest |
| Fallback switch | `ExecutionProviderDispatch::error_on_failure()`; default `fail_silently()` | `src/ep/mod.rs` |
| Session options | `with_intra_threads`, `with_inter_threads`, `with_parallel_execution`, `with_optimization_level`, `with_optimized_model_path`, `with_deterministic_compute` | `impl_options.rs` |
| Model loading | `commit_from_file`, `commit_from_memory`, `commit_from_memory_directly`, `commit_from_url` (`fetch-models`) | `impl_commit.rs` |

Related: the GLiNER ONNX exports and the serving options that use them are in `agents/shared-ner-service.md`; the GLiNER PII model cards, licences and Hub revisions are in `privacy/gliner-models.md`; the `gline-rs` crate, whose exact `ort` pin conflicts with this article's, is in `privacy/gliner-glirel-zero-shot.md`.

## Examples
- SNIPPET: Cargo dependency for a CPU-only build that downloads nothing at build time and loads a supplied ONNX Runtime library at run time; context: `ort` 2.0.0-rc.13, features per the manifest, the `api-*` level to be raised only as far as the code needs; checked: syntax [DER S-pwbxp7jw, S-o3nqheje, S-m5r2fcso: feature names and `default-features = false` from the manifest and the multiversion page]

```toml
[dependencies.ort]
version = "=2.0.0-rc.13"
default-features = false
features = ["std", "ndarray", "load-dynamic", "api-17"]
```

- SNIPPET: verify an ONNX Runtime CPU archive against the digest on the upstream release page and point `ort` at the library; context: Linux x86_64, release 1.28.3, paths are placeholders; checked: no [DER S-atc7uhx5, S-mw6rc3qq: digest from the release page, `ORT_DYLIB_PATH` from the linking page]

```sh
echo "db14e4863bd37893fc59729d986ab2a0d043d10b7d44da1913c4982b7e3d009c  onnxruntime-linux-x64-1.28.3.tgz" | sha256sum -c -
tar -xzf onnxruntime-linux-x64-1.28.3.tgz
ORT_DYLIB_PATH=/opt/corpus/onnxruntime-linux-x64-1.28.3/lib/libonnxruntime.so ./corpus-core
```

- SNIPPET: a CPU-only session loaded from bytes whose sha256 the caller has already checked; context: `ort` 2.0.0-rc.13, `ort::Result` as the error type, thread and optimisation values are examples, not recommendations; checked: no [DER S-ktoxup5h, S-l3go6sje, S-6z4pv23l: provider, option and loader methods read at the tag]

```rust
use ort::{
    ep,
    session::{builder::GraphOptimizationLevel, Session},
};

fn load(model_bytes: &[u8]) -> ort::Result<Session> {
    Session::builder()?
        .with_execution_providers([ep::CPU::default().build().error_on_failure()])?
        .with_parallel_execution(false)?
        .with_intra_threads(4)?
        .with_optimization_level(GraphOptimizationLevel::Level2)?
        .commit_from_memory(model_bytes)
}
```

- SNIPPET: list the files of a Hugging Face model at a commit with their LFS digests; context: public model id from the kb, any HTTP client, `blobs=true` adds sizes and `lfs`; checked: no [DER S-ixcjfodz, S-rlepjcn5: endpoint and fields as read in the API output and the OpenAPI description]

```sh
curl -s "https://huggingface.co/api/models/onnx-community/gliner_multi-v2.1/revision/6ddaeb9413b0e71ad8457da1aab378a165b24058?blobs=true"
```
