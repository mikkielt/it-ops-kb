---
topic: privacy/spacy-pipeline-pinning
priority: P3
applies_to: "spaCy 3.8.16 (tag release-v3.8.16), weasel 1.0.0, pip 26.2.1"
retrieved_utc: 2026-10-11
sources: [S-pxs757ky, S-pmc3phpi, S-kcn56y7v, S-7dzxtyeg, S-yo4p2wby, S-y7fy5phu, S-afy77hze, S-eem3ebzg, S-2rokayfc, S-kmhasvx6, S-w2iwn6ac, S-mvtjqg65, S-7cypj7la, S-tzx4jroa, S-ufedwopa, S-uyjpiflf, S-q6tsebaa, S-szqctyjx, S-b5ddf5wg, S-eqnfvpps, S-ix7uqv2r, S-kzxs7o5q, S-fpqwvm77, S-5wch47ce, S-bdjuufne, S-umcvzek3, S-zd7e6qfm]
status: partial
---

# Pinning a spaCy pipeline: spaCy version, package metadata, wheel and install

## Summary
- A spaCy trained pipeline is an ordinary Python package. `spacy package` turns a saved pipeline directory into a wheel or sdist, and the package's `meta.json` carries a `spacy_version` range.
- That range is **advisory**: the loader only warns when the running spaCy is outside it. What pip enforces is the package's `requirements` (the generated `install_requires`) and, with `--require-hashes`, the file hash.
- The default range is `>=<packaging spaCy's full version>,<next minor>`, so spaCy 3.8.16 writes `>=3.8.16,<3.9.0`. An exact-patch pin is a deliberate edit of `meta.json`.
- spaCy records no digest of training inputs in the pipeline. The nearest things are `spacy project` asset checksums and the `project.lock` file (both MD5, which pip's hash mode does not accept) and the transient `_sourced_vectors_hashes`.

## Facts

### Versions and compatibility
- A pipeline package version `a.b.c` means: `a` spaCy major, `b` spaCy minor, `c` the model version (different data, parameters, iterations or vectors); the third number is not spaCy's patch number. [DOC S-7dzxtyeg]
- PyPI lists spaCy 3.8.0 (2024-09-11) through 3.8.16 (2026-08-24) as the patch releases of minor 3.8; 3.8.16 declares Python `>=3.9,<3.15`. [DOC S-ix7uqv2r]
- The meta field `spacy_version` defaults to the version used to create the pipeline "up to next minor version"; the docs' example is a pipeline trained with v3.0.0 getting `>=3.0.0,<3.1.0`. [DOC S-yo4p2wby]
- The range is built from the full running version: `>={version},<{major}.{minor+1}.0`. [CODE S-eem3ebzg: spacy/util.py#get_minor_version_range]
- `__version__` of the tagged source is `3.8.16`, so a pipeline packaged on it and left at the default carries `>=3.8.16,<3.9.0`; running 3.8.15 against it is outside the range. [DER S-eem3ebzg, S-uyjpiflf: the range formula applied to `about.__version__`]
- On load, `load_meta` calls `warnings.warn` with W095 when the running spaCy is outside `spacy_version`; it raises nothing and returns the meta, so loading goes on. A constraint that does not parse counts as incompatible. [CODE S-eem3ebzg: spacy/util.py#load_meta]
- W095 says the pipeline "may not be 100% compatible with the current version" and points to `python -m spacy validate`; W094 warns about an under-constrained requirement (one `>=` only) and suggests a range with a lower and an upper pin. [CODE S-ufedwopa: spacy/errors.py#Warnings.W095]
- A `spacy_version` that is a bare version is read as `==<version>`; otherwise it is a PEP 440 specifier set, and pre-releases are accepted by default. [CODE S-eem3ebzg: spacy/util.py#is_compatible_version]
- `meta.json` no longer builds the `nlp` object (since spaCy 3.0): it holds reference information and feeds `spacy package`, and `config.cfg` is the single source of truth for loading. [DOC S-yo4p2wby]
- `spacy validate` checks every installed pipeline package against the installed spaCy, lists upgrade commands, and returns exit code 1 if an incompatible package is found, so it can serve as a build or test gate. [DOC S-pmc3phpi]
- `validate` fetches the compatibility table from the URL in `about.__compatibility__` and exits with an error if it cannot (status other than 200), so it needs network access. [CODE S-2rokayfc: spacy/cli/validate.py#get_model_pkgs]
- The compatibility table is keyed by spaCy minor version (`3.8`, `3.7`, ...) and lists package versions per model name, newest first; at the commit read, `3.8` maps `en_core_web_lg`, `en_core_web_sm` and `pl_core_news_lg` to `3.8.0`. [DOC S-eqnfvpps]
- `validate` tests `package in compat`, where `compat` is keyed by spaCy version, so for a model package the else branch decides: the package's own `spacy_version` against the running spaCy. [DER S-2rokayfc, S-eqnfvpps: the key shape of the table read against the membership test]
- `spacy info` prints the spaCy version, location, platform, Python version and the installed pipelines with their versions; `spacy info <pipeline>` prints that pipeline's `meta.json` plus its `source` path and, if pip left a `direct_url.json`, its `download_url`. [CODE S-w2iwn6ac: spacy/cli/info.py#info_spacy]
- `spacy validate` and `spacy info` list only packages that register in the `spacy_models` entry-point group; the generated `setup.py` registers `{lang}_{name}` there. [DER S-eem3ebzg, S-afy77hze: `get_installed_models` reads `registry.models`, whose comment says packages built by `spacy package` advertise themselves; the template sets `entry_points={'spacy_models': ...}`]

### Packaging with `spacy package`
- Command: `python -m spacy package [input_dir] [output_dir] [--code] [--meta-path] [--create-meta] [--build] [--name] [--version] [--force]`; `--name` and `--version` override the meta, `--force` overwrites an existing folder in the output directory. [DOC S-pmc3phpi]
- `--build` takes `sdist` (the default), `wheel`, both comma-separated, or `none`; the docs call the wheel the artifact that "installs more efficiently". [DOC S-pmc3phpi]
- `--code` takes comma-separated Python files with registered functions; they are copied into the package root and imported in its `__init__.py`; external packages they need must be listed in `requirements`. [DOC S-pxs757ky]
- The CLI source has one more option, `--require-parent/--no-require-parent` (default on), which the CLI docs table does not list; it adds `spacy` with the meta's `spacy_version` to `requirements`. [CODE S-afy77hze: spacy/cli/package.py#package_cli]
- The output directory gets `<lang>_<name>-<version>/` holding `meta.json`, `setup.py`, `MANIFEST.in`, a `README.md` (generated unless the data directory has one), `LICENSE` and `LICENSES_SOURCES` if present, the package directory `<lang>_<name>/` with `__init__.py` and a copy of the data in `<lang>_<name>-<version>/`, and `dist/` after the build. [CODE S-afy77hze: spacy/cli/package.py#package]
- A `--name` must be a Python identifier and a permitted PEP 426 name; a name not starting with `<lang>_` gets that prefix; the meta is validated before anything is written, and the wheel file name squashes runs of underscores. [CODE S-afy77hze: spacy/cli/package.py#package]
- The build runs `python -m build . --sdist` and/or `--wheel` in the package directory and falls back to `setup.py` if that fails; a wheel needs `build` (or the deprecated `wheel`) installed. [CODE S-afy77hze: spacy/cli/package.py#package]
- The docs warn against editing `config.cfg` after training because changed architectures or hyperparameters can make the trained weights incompatible. [DOC S-pxs757ky]
- `meta.json` fields (docs): `lang`, `name`, `version`, `spacy_version`, `parent_package`, `requirements`, `description`, `author`, `email`, `url`, `license`, `sources`, `vectors`, `pipeline`, `labels`, `performance`, `speed`, `spacy_git_version`, and any other custom keys, which are preserved in `nlp.meta`. [DOC S-yo4p2wby]
- When saving, `Language.meta` fills `vectors` (`width`, `vectors`, `keys`, `name`, `mode`), `labels`, `pipeline`, `components`, `disabled` and `spacy_git_version`; `to_disk` writes `meta.json` and `config.cfg`. [CODE S-mvtjqg65: spacy/language.py#Language.meta]
- Packaging adds to `requirements` every third-party package behind a registered function in the config's runtime sections, as `>=<installed>,<next minor>`, and skips `spacy`, `spacy-legacy`, `spacy-nightly`, `thinc` and `srsly`. [CODE S-afy77hze: spacy/cli/package.py#get_third_party_dependencies]
- The packaging spaCy's own range is written first and then overridden by what the `meta.json` file holds, so a `spacy_version` already in the file wins; `sources` is never computed. [CODE S-afy77hze: spacy/cli/package.py#get_meta]
- The generated `setup.py` passes `requirements` (and `setup_requires`) as `install_requires`; this is what pip enforces at install time. [CODE S-afy77hze: spacy/cli/package.py#TEMPLATE_SETUP]
- To pin a pipeline to one patch: put `"spacy_version": "==3.8.16"` in the `meta.json` given to `--meta-path`; `get_meta` then appends `spacy==3.8.16` to `requirements` itself, as it concatenates `spacy` and the range, so a bare `3.8.16` there would produce the invalid requirement `spacy3.8.16`. [DER S-afy77hze, S-eem3ebzg: `about.__title__ + meta["spacy_version"]` against `is_compatible_version`'s bare-version rule]
- A gate that must stop on a mismatch has to check for itself (`spacy validate`'s exit code, or `nlp.meta["spacy_version"]` against the running spaCy), because the loader only warns. [DER S-pmc3phpi, S-eem3ebzg: validate returns 1; load_meta only warns]

### What records the pipeline's inputs
- When a component is sourced from another pipeline, `Language.from_config` stores `nlp.meta["_sourced_vectors_hashes"][<component>]` as Python's built-in `hash()` of the source vectors' bytes. [CODE S-mvtjqg65: spacy/language.py#Language.from_config]
- `init_vocab` pops `_sourced_vectors_hashes` from the meta while initialising, compares it with the hash of the current vectors and warns W113 if they differ, so the key is a check during training and not a stamp in the saved meta. [CODE S-7cypj7la: spacy/training/initialize.py#init_vocab]
- Python salts `bytes` hashes with a random value that is stable within one process only, so a `hash()` value cannot be compared between runs. [DOC S-zd7e6qfm]
- The meta schema holds `lang`, `name`, `version`, `spacy_version`, `parent_package`, `requirements`, `pipeline`, `description`, `license`, author fields, `sources`, `vectors`, `labels`, `performance` and `spacy_git_version`; `sources` is free text and `vectors` is shape information. [CODE S-tzx4jroa: spacy/schemas.py#ModelMetaSchema]
- Neither the meta schema, the meta field table nor the config sections read hold a digest of the training data, the config or the weights; the pipeline directory is stamped by `version`, `spacy_git_version` and the vector shape, not by content. [DER S-tzx4jroa, S-yo4p2wby: field lists read for a hash field, none found]
- `spacy project` asset entries take an optional `checksum`: a download is skipped if a local file already matches, and a mismatch after download is an error; an asset without `url` is "private" and only checked. [DOC S-pmc3phpi]
- `project assets` compares the `checksum` field with the local file's checksum before and after a download, and for a private asset (no `url`) reports a match or a mismatch without fetching anything; the mismatch messages are `msg.fail` calls with no `exits` argument. [CODE S-q6tsebaa: weasel/cli/assets.py#fetch_asset]
- The checksum is the MD5 of a file's bytes; for a directory it is one MD5 over the bytes of its files in sorted order (paths not included). [CODE S-szqctyjx: weasel/util/hashing.py#get_checksum]
- `project.lock` keeps, per command, `cmd`, `script`, and `deps` and `outs` as path and `md5`; a command re-runs when its entry changes. [CODE S-b5ddf5wg: weasel/cli/run.py#get_lock_entry]
- The docs give the purpose of asset checksums as letting you "verify that someone else running your project will use the same files". [DOC S-y7fy5phu]
- A project asset checksum or lock entry is MD5, and pip's hash-checking mode excludes md5, sha1 and sha224, so those values cannot be reused as `--hash`; a sha256 for the install has to be computed on the built wheel. [DER S-szqctyjx, S-kzxs7o5q: md5 in weasel; pip's list of excluded algorithms]

### Installing from a private index, offline, with hashes
- Official pipeline packages are hosted on GitHub Releases of `explosion/spacy-models` and installed from the URL or a local path of the wheel or archive; `spacy info <name> --url` prints the URL of the newest compatible one and needs the internet. [DOC S-kcn56y7v]
- `about.__download_url__` is the GitHub releases download prefix and `about.__compatibility__` the `compatibility.json` on the repository's `master` branch. [CODE S-uyjpiflf: spacy/about.py#__download_url__]
- `spacy download` is "mostly intended as a convenient, interactive wrapper"; for automated builds the docs recommend a direct pip install or an internal PyPI. [DOC S-pmc3phpi]
- `--direct` skips the compatibility check and needs `name-version`; every other argument is passed to `pip install`. [CODE S-kmhasvx6: spacy/cli/download.py#download]
- In 3.8.16 the URL passed to pip must start with the default GitHub prefix: `download_model` raises `ValueError` otherwise, and a `--url` without a trailing slash is replaced by the default prefix; the CLI table calls `--url` a mirror repository. [CODE S-kmhasvx6: spacy/cli/download.py#download_model]
- Pipeline packages "are typically not suitable" for public pypi.python.org (binary data, files over 50 MB), but an internal PyPI installation can hold them. [DOC S-pxs757ky]
- A `requirements.txt` can name a pipeline by package name (served by an internal index) or by a direct `name @ <url>` wheel URL, and "all pipeline packages are versioned and specify their spaCy dependency". [DOC S-kcn56y7v]
- pip searches PyPI or the `--index-url` index, the local filesystem and any `--find-links` or `--extra-index-url` location together; there is no priority, the best matching version wins. [DOC S-fpqwvm77]
- `--index-url` names the index to search instead of PyPI; `--extra-index-url` adds one, and pip's own warning calls using it for private packages unsafe: dependency confusion, where a public package of the same name may be chosen. [DOC S-fpqwvm77]
- `--no-index --find-links /local/dir/` installs from a flat directory of archives without scanning any index. [DOC S-fpqwvm77]
- Hash-checking mode uses `--hash=sha256:...` per requirement; a hash on any requirement turns it on for the whole run, and then every requirement and every dependency must be hashed and pinned (`==`, URL or path). [DOC S-kzxs7o5q]
- `--require-hashes` forces the mode and shows the hashes of fetched files; sha256 is recommended and md5, sha1 and sha224 are excluded; pip 26.2 added `--no-require-hashes`; a `#sha256=` fragment served by an index does not count as a local hash. [DOC S-kzxs7o5q]
- `pip hash <file>` prints the `--hash=sha256:...` line for a downloaded or built archive; a package with a wheel and an sdist needs a hash for each archive pip might pick. [DOC S-umcvzek3]
- A requirements file may hold the lines `--index-url`, `--extra-index-url`, `--no-index`, `--find-links`, `--require-hashes` and `--no-require-hashes`; per requirement only `--hash` and `--config-settings` are allowed. [CODE S-bdjuufne: src/pip/_internal/req/req_file.py#SUPPORTED_OPTIONS]
- The docs list per-requirement options as `--config-settings` and `--hash` and put the global options (such as `--no-index` and `--find-links`) on their own lines. [DOC S-5wch47ce]

### How it fits
- Context: a self-hosted corpus service, a Python shell over a Rust core, CPU-only, offline-capable, text in Polish and English. Runtime needs no network for a pipeline: `util.py` has no HTTP client, and the network uses read are `spacy download`, `spacy validate` and `spacy info --url`. [DER S-eem3ebzg, S-kmhasvx6, S-2rokayfc, S-w2iwn6ac: modules read for requests calls]
- An exact-patch pin sits in three places that are not equally strong: the host's `spacy==3.8.16` with its hash, the pipeline's `requirements` entry (enforced at install), and `spacy_version` (warning only). The pipeline wheel's own sha256 is the only content stamp, and it is taken after the build. [DER S-afy77hze, S-eem3ebzg, S-kzxs7o5q: install_requires and hash mode enforce; load_meta warns]
- A Polish pipeline from Explosion exists for the 3.8 line (`pl_core_news_lg` in the compatibility table), so both languages can use packaged pipelines under one pin. [DER S-eqnfvpps: the table's `3.8` entry]
- Rules kept as data fit beside the wheel, not inside it: `--code` copies Python files into the package and `meta.json` accepts custom keys, but spaCy offers no field that stamps an external rules file, so its hash has to live in the service's own lock data. [DER S-pxs757ky, S-yo4p2wby, S-tzx4jroa: what the package can carry against the meta schema]
- Offline install: build once, `pip hash` the wheel, store the wheel and the hash in the lock, and install with `--no-index --find-links <dir> --require-hashes`; a private index adds only a place to fetch from, and pip's hash check is what binds the bytes. [DER S-fpqwvm77, S-kzxs7o5q, S-umcvzek3: index and hash options as documented]

### Not confirmed
- Whether `python -m build`, which `spacy package` runs, needs network access for its build requirements: no page read states it. [UNK: not read, logged in `_gaps.md`]
- Whether two `spacy package` runs over the same input give a byte-identical wheel: not stated in the pages or source read. [UNK: not read, logged in `_gaps.md`]
- Whether `spacy project assets` ends with a non-zero exit status on a checksum mismatch: the weasel code calls `msg.fail` without `exits`, and wasabi's behaviour was not read. [UNK: not read, logged in `_gaps.md`]
- Whether a patch release within one minor can change tokenizer or component output for the same pipeline weights: the docs set the default range to the next minor but make no statement. [UNK: not read, logged in `_gaps.md`]

## Reference
| Item | Value | Where |
|---|---|---|
| Version read | spaCy 3.8.16, weasel 1.0.0, pip 26.2.1 | tags `release-v3.8.16`, `release-v1.0.0`, `26.2.1` |
| Default `spacy_version` | `>=<running version>,<next minor>` | `spacy/util.py#get_minor_version_range` |
| Mismatch at load | warning W095 | `spacy/util.py#load_meta` |
| Package build | `python -m build` (sdist default, `--build wheel`) | `spacy/cli/package.py#package` |
| Compatibility table | `compatibility.json` of `explosion/spacy-models` | `spacy/about.py` |
| Asset and lock checksums | MD5 | `weasel/util/hashing.py#get_checksum` |
| Install hashes | sha256 via `--hash` and `--require-hashes` | pip secure installs |

See also `privacy/spacy-model-licence.md` (licence and published checksums of `en_core_web_lg`), `gitlab/package-registries.md` (a private PyPI index and its hashes), `security/supply-chain.md` (hash pinning) and `python/uv-projects.md`.

## Examples
- SNIPPET: package a trained pipeline as a wheel with an exact-patch `spacy_version`; context: spaCy 3.8.16, `build` installed, `./training/model-best` from `spacy train`; checked: no [DER S-pmc3phpi, S-afy77hze: options from the CLI table, `<lang>_` prefixing from `package()`]
```bash
python -m spacy package ./training/model-best ./packages \
  --name corpus_ner --version 1.4.0 --build wheel \
  --meta-path ./meta.json --force
```
- SNIPPET: the `meta.json` given to `--meta-path`; context: spaCy 3.8.16, language `pl`, package name becomes `pl_corpus_ner`; checked: syntax [DER S-afy77hze, S-eem3ebzg: field names from `get_meta`, bare-version rule of `is_compatible_version`]
```json
{
  "lang": "pl",
  "name": "corpus_ner",
  "version": "1.4.0",
  "spacy_version": "==3.8.16",
  "license": "MIT"
}
```
- SNIPPET: install the wheel offline with hash checking; context: pip 26.2, wheel and the wheels of spaCy's dependencies in `/srv/wheelhouse`, each with its sha256 in `requirements.txt`; checked: no [DER S-fpqwvm77, S-kzxs7o5q, S-umcvzek3: `--no-index`, `--find-links`, `--require-hashes` and `pip hash` as documented]
```bash
python -m pip hash ./packages/pl_corpus_ner-1.4.0/dist/pl_corpus_ner-1.4.0-py3-none-any.whl
python -m pip install --no-index --find-links /srv/wheelhouse --require-hashes -r requirements.txt
```
- SNIPPET: a `requirements.txt` for a private index with the pipeline pinned by hash; context: pip 26.2, index at a placeholder host, every dependency of spaCy also listed with its hash; checked: no [DER S-bdjuufne, S-kzxs7o5q: option lines and the `--hash` form]
```text
--index-url https://pypi.corp.example.com/simple/
spacy==3.8.16 \
    --hash=sha256:<sha256 of the spacy wheel>
pl_corpus_ner==1.4.0 \
    --hash=sha256:<sha256 printed by pip hash>
```
- SNIPPET: check installed pipelines after pinning; context: spaCy 3.8.16, network for `validate`; checked: no [DER S-pmc3phpi, S-w2iwn6ac: `validate` exit code and `info` output]
```bash
python -m spacy validate
python -m spacy info pl_corpus_ner
```
