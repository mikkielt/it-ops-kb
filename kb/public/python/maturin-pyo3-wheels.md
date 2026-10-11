---
topic: python/maturin-pyo3-wheels
priority: P3
applies_to: "maturin 1.15.0, PyO3 0.29.3, maturin-action 1.51.0 (release tags read 2026-10-11); CPython wheels for linux x86_64/aarch64 and macOS arm64"
retrieved_utc: 2026-10-11
sources: [S-c6fbhzyz, S-hec62m7j, S-26hqxvrn, S-hisnadiu, S-cr3vzki4, S-oeklvsgw, S-romblyjt, S-yfykoru4, S-pyhwnq4g, S-65rohhd6, S-g5ef7rue, S-sne3yj7b, S-xpr6ww5t]
status: partial
---

# maturin and PyO3: building abi3 wheels for a mixed Python/Rust package

## Summary
maturin is the PEP 517 build backend (and CLI) that compiles a Rust crate using PyO3 into a Python
wheel; PyO3 is the Rust crate that provides the Python bindings. For a "Python shell with a Rust core"
the documented layout is a mixed project: a Python package directory beside `Cargo.toml`, configured
under `[tool.maturin]` in `pyproject.toml`. Enabling a PyO3 `abi3-pyXY` feature makes one wheel per
OS and architecture cover every newer CPython, so a Linux x86_64, Linux aarch64 and macOS arm64
release needs three binary wheels plus an sdist. Linux wheels must be built in a manylinux container
or with zig for PyPI. The macOS `universal2` wheel is not documented in the maturin guide. This
article records the vendor statements; the project's choices are not recorded here. For the uv side
(workspace, lock, `uv build`) see `python/uv-projects.md`.

## Facts
- maturin (guide read at tag 1.15.0) is used as a build backend by putting
  `requires = ["maturin>=1.0,<2.0"]` and `build-backend = "maturin"` under `[build-system]` in a
  `pyproject.toml` next to `Cargo.toml`; `pip install .` then builds the package, and `-v` shows the
  cargo output. [DOC S-c6fbhzyz]
- Mixed Rust/Python layout: add a directory named like the package (matching `lib.name` in
  `Cargo.toml`) holding the Python source. In such a project maturin does not modify the existing
  `__init__.py`, so the Rust module is imported as `from my_project import my_project`. [DOC S-hec62m7j]
- `tool.maturin.python-source = "python"` moves the Python package under a `python/` directory; the
  guide recommends this layout to avoid a common `ImportError` pitfall (a local package shadowing the
  installed one). maturin also detects a `src`-layout automatically when the Rust crate sits in a
  `rust/` folder beside a `src/<package>` Python tree. [DOC S-hec62m7j]
- `module-name = "my_package._native"` under `[tool.maturin]` installs the compiled extension as a
  submodule of the Python package (dotted names are accepted); the `#[pymodule]` function name or a
  `#[pyo3(name = "...")]` attribute must match the last segment. [DOC S-hisnadiu]
- Type information in a mixed project: files in the Python source directory that are not in
  `.gitignore` are included in the sdist and wheel, so `.pyi` stubs go there; the empty `py.typed`
  marker must be added by hand. [DOC S-hec62m7j]
- maturin detects pyo3 bindings automatically when `pyo3` is a dependency in `Cargo.toml`;
  `-b`/`--bindings` (or `bindings` under `[tool.maturin]`) accepts `pyo3`, `pyo3-ffi`, `cffi`,
  `uniffi` and `bin`. [DOC S-26hqxvrn]
- abi3 is opted into with a PyO3 feature naming the minimum Python version, for example
  `pyo3 = { version = "0.29.0", features = ["abi3-py310"] }`; the maturin guide states an `abi3-py310`
  wheel supports all GIL-enabled CPython versions from 3.10 and newer. [DOC S-26hqxvrn]
- PyO3's `abi3-pyXY` features set the minimum version of the wheel (`abi3-py38` to `abi3-py314` are
  listed in the features reference); with several set, the lowest wins; maturin names the wheel like
  `my-extension-1.0-cp38-abi3-manylinux2020_x86_64.whl`. [DOC S-pyhwnq4g]
- The plain `abi3` feature (no `pyXY` suffix) targets the stable ABI of the host interpreter, needs
  that interpreter present, and the features page says it cannot be used for cross-compilation; the
  `abi3-pyXY` form is the one to pin the minimum. [DOC S-65rohhd6]
- By PyO3's description the advantage of the limited API is that a vendor builds and distributes a
  single copy for each OS and architecture, installable on all Python versions from the minimum up.
  [DOC S-pyhwnq4g]
- abi3 limits (PyO3 0.29.3): `text_signature` on classes needs Python 3.10 or newer; the `dict` and
  `weakref` class options need 3.9 or newer; the buffer API needs 3.11 or newer; subclassing native
  types such as `PyException` needs 3.12 or newer; and optimisations that rely on the exact Python
  version are lost. [DOC S-pyhwnq4g]
- Building abi3 needs a host interpreter at least as new as the minimum: with `abi3-py39` and a host
  Python 3.8 the build fails; setting `PYO3_NO_PYTHON` builds without calling an interpreter. [DOC S-pyhwnq4g]
- maturin's tutorial output for an abi3 project says an interpreter is only required on Windows
  with abi3 (`Not using a specific python interpreter`). [DOC S-cr3vzki4]
- The free-threaded CPython build cannot load `abi3` wheels; PyO3 0.29.3 adds an `abi3t` flavour
  (Python 3.15 and newer, both builds) and says maturin 1.14 or newer supports `abi3t` wheels. [DOC S-pyhwnq4g]
- A single maturin build selects at most one stable ABI family: with `abi3-py310` plus `abi3t-py315`
  features, separate `maturin build --interpreter ...` runs are needed for each, and free-threaded
  3.14 gets a version-specific `cp314-cp314t` wheel. [DOC S-26hqxvrn]
- PyO3 disables libpython linking for distributable extension modules through the
  `PYO3_BUILD_EXTENSION_MODULE` environment variable, which maturin 1.9.4 or newer sets itself; the old
  `extension-module` feature is called out as the historical mechanism. [DOC S-pyhwnq4g]
- The features page marks `extension-module` deprecated (remove it and use maturin 1.9.4 or newer or
  setuptools-rust 1.12 or newer). [DOC S-65rohhd6]
- maturin's tutorial says PyO3 0.26 or earlier needs `features = ["pyo3/extension-module"]` under
  `[tool.maturin]`, and that this is automatic in PyO3 0.27. [DOC S-cr3vzki4]
- Cross compiling a PyO3 module needs a target Python interpreter and the `PYO3_CROSS*` variables in
  general, but the target interpreter is optional for abi3 extension modules, and
  `PYO3_CROSS_LIB_DIR` can often be omitted for Unix, macOS and Windows targets. [DOC S-pyhwnq4g]
- PyO3 0.29.3 supports CPython 3.8 or newer, PyPy 7.3 (Python 3.11+) and GraalPy 25.0 or newer
  (Python 3.12+), and requires Rust 1.83 or newer. [DOC S-g5ef7rue]
- PyPI-bound Linux wheels must come from a manylinux docker image or be built with zig. Since Rust
  1.64 requires glibc 2.17, the minimum is manylinux2014; maturin checks the library for manylinux
  compliance (an auditwheel reimplementation), tags the wheel, and gives the plain `linux` tag when
  the build system's glibc is too new. [DOC S-c6fbhzyz]
- `--compatibility` (or `compatibility` under `[tool.maturin]`) controls the platform tag:
  `pypi` accepts only tags PyPI allows on every platform, `manylinux2014`/`manylinux_2_28` style values
  pin the Linux tag, and the default is the lowest compatible manylinux tag or plain `linux` if
  nothing matched. [DOC S-c6fbhzyz]
- Cross compiling Linux aarch64 with zig: `maturin build --release --target aarch64-unknown-linux-gnu
  --zig`. Zig linking was added in maturin 0.12.7, is regularly tested for Linux only, installs with
  `pip install maturin[zig]` or `pip install ziglang`, and defaults to manylinux2014 (`manylinux_2_17`)
  when no `--compatibility` is given. [DOC S-c6fbhzyz]
- The other documented Linux cross-compile route is Docker: the guide points to the
  `rust-cross/manylinux-cross` images and to maturin-action. [DOC S-c6fbhzyz]
- maturin-action's default containers: x86_64 uses `quay.io/pypa/manylinux2014_x86_64` or
  `manylinux_2_28_x86_64`; aarch64 uses `ghcr.io/rust-cross/manylinux2014-cross:aarch64` or
  `ghcr.io/rust-cross/manylinux_2_28-cross:aarch64`; the `container` input overrides this and
  `off` builds on the host. Official manylinux images for non-x86 architectures need QEMU. [DOC S-sne3yj7b]
- `maturin generate-ci github > .github/workflows/CI.yml` writes a GitHub Actions workflow (GitHub is
  the only CI provider listed); the flags `--platform`, `--pytest`, `--zig` and `--skip-attestation`
  are marked deprecated in favour of `[tool.maturin.generate-ci.github]` in `pyproject.toml`.
  [DOC S-c6fbhzyz]
- Per-platform generate-ci settings live under `[tool.maturin.generate-ci.github.linux]` and
  `...macos` (also `musllinux`, `windows`, `emscripten`, `android`) with `targets = ["x86_64",
  "aarch64"]` or a detailed `[[...target]]` array, plus `runner`, `manylinux`, `container`,
  `before-script-linux` and `args` keys. [DOC S-hisnadiu]
- The generated abi3 workflow at 1.15.0 builds Linux x86_64, x86, aarch64, armv7, s390x and ppc64le on
  `ubuntu-22.04` with maturin-action `manylinux: auto`, macOS x86_64 on `macos-15-intel` and aarch64 on
  `macos-latest`, and publishes with `uv publish` on a tag. This is the repository's test snapshot of
  the generator output, not a promise. [CODE S-romblyjt: src/ci/github/__snapshot__/github_abi3.yml#jobs.linux.strategy.matrix]
- maturin's platform page lists wheels and binaries released for Windows (x86, x86_64, arm64), Linux
  (x86, x86_64, armv7, aarch64, ppc64le, s390x) and macOS (x86_64, aarch64), and says all architectures
  included in manylinux are supported. [DOC S-yfykoru4]
- The macOS deployment target SDK version is configurable per triple for `x86_64-apple-darwin` and
  `aarch64-apple-darwin` with `[tool.maturin.target.<triple>] macos-deployment-target = "11.0"`; no
  other per-target option exists yet. [DOC S-hisnadiu]
- `maturin develop` builds in debug mode by default and installs the package into the current
  virtualenv; `--uv` installs with uv instead of pip. [DOC S-oeklvsgw]
- `maturin build` writes wheels to a `wheels` directory under the target directory unless `--out` is
  given, `--sdist` also builds an sdist and builds wheels from it, and `maturin sdist` builds only the
  source distribution (it needs a `[build-system]` table in `pyproject.toml`). [DOC S-c6fbhzyz]
- `maturin publish` exists in the 1.15.0 CLI behind the `upload` Cargo feature ("Build and publish the
  crate as python packages to pypi"), while the guide's tutorial points to `uv publish` or
  `twine upload`. [CODE S-xpr6ww5t: src/main.rs#Command::Publish]
- Derivation for a Linux x86_64, Linux aarch64, macOS arm64 matrix with `abi3-py39`: three native
  wheel builds named `cp39-abi3-<platform tag>` (for example `manylinux_2_28_x86_64`,
  `manylinux_2_28_aarch64`, `macosx_11_0_arm64`) plus one sdist, each wheel covering CPython 3.9 and
  newer GIL-enabled builds. The platform tags are inferred from the examples above, not stated for
  these exact targets. [DER S-pyhwnq4g, S-c6fbhzyz, S-yfykoru4: abi3 naming and manylinux tagging
  pattern applied to the three targets]
- A `universal2` macOS wheel (`--target universal2-apple-darwin`) is not mentioned in the maturin
  guide at 1.15.0 that was read, so whether and how maturin produces one is not confirmed here. [UNK]

## Reference
- SNIPPET: Cargo.toml and pyproject.toml for a mixed project built as one abi3 wheel with minimum Python 3.9; context: maturin 1.15.0, PyO3 0.29.x; checked: no [DER S-26hqxvrn, S-hec62m7j, S-hisnadiu: key names and the abi3-pyXY feature as documented; crate and package names are placeholders]
```toml
# Cargo.toml
[package]
name = "example-core"
version = "0.1.0"
edition = "2021"

[lib]
name = "_native"
crate-type = ["cdylib"]

[dependencies]
pyo3 = { version = "0.29.0", features = ["abi3-py39"] }
```
```toml
# pyproject.toml
[build-system]
requires = ["maturin>=1.0,<2.0"]
build-backend = "maturin"

[project]
name = "example-shell"
requires-python = ">=3.9"

[tool.maturin]
python-source = "python"
module-name = "example_shell._native"
```
- SNIPPET: the maturin commands for the three-target matrix; context: maturin 1.15.0; checked: no [DER S-c6fbhzyz, S-yfykoru4: `--target`, `--zig`, `--compatibility` as documented; `x86_64-unknown-linux-gnu` and `aarch64-apple-darwin` follow the Rust triple naming of the documented example]
```console
$ maturin develop                      # debug build into the active virtualenv
$ maturin build --release --target x86_64-unknown-linux-gnu --compatibility manylinux_2_28
$ maturin build --release --target aarch64-unknown-linux-gnu --zig --compatibility manylinux_2_28
$ maturin build --release --target aarch64-apple-darwin   # on a macOS arm64 runner
$ maturin sdist                        # source distribution only
$ maturin generate-ci github > .github/workflows/CI.yml
```

| Item | Value (version read) |
|---|---|
| maturin | 1.15.0, guide and source at tag `v1.15.0` |
| PyO3 | 0.29.3, guide at tag `v0.29.3` |
| maturin-action | 1.51.0, README at tag `v1.51.0` |
| PyO3 abi3 minimum features | `abi3-py38` .. `abi3-py314` (features page); `abi3t-py315` |
| Wheel tag pattern | `cp<min>-abi3-<platform>` (for example `cp38-abi3-manylinux2020_x86_64`) |

## Examples
- A release job on a Linux amd64 runner runs `maturin build --release --compatibility manylinux_2_28`
  inside `quay.io/pypa/manylinux_2_28_x86_64`, a second job on a Linux arm64 runner or with zig builds
  the aarch64 wheel, and a macOS arm64 runner builds `aarch64-apple-darwin`; the three wheels and the
  sdist from `maturin sdist` are uploaded to the internal index for `PL-SRV-0042`.
- A developer on `PL-LT-00123` runs `maturin develop --uv` after editing Rust code, then `pytest`
  against the installed package.
