---
topic: arch/oxigraph-embedded-rdf
priority: P3
applies_to: "Oxigraph 0.5.11 (Rust crate oxigraph, pyoxigraph, oxigraph-cli; tag v0.5.11, released 2026-09-02) as an embedded RDF quad store with SPARQL 1.1; retrieved 2026-10-11"
retrieved_utc: 2026-10-11
sources: [S-z4kbze7e, S-bytyyxb4, S-5ty62hy3, S-rw3phgvf, S-c4gfzuad, S-4ucs6ogm, S-dcliqq63, S-3qbz2t4u, S-jgxzxayp, S-nxnd5tsp, S-bfv5hqkn, S-guwnayzo, S-fi3wa4vw, S-iqad4pe3, S-mzu53xnc, S-z2qagps6, S-uohdppyd, S-45qncmsz, S-axwbq3bp, S-a5hei6wa, S-coloiwrz, S-ifojpzaw, S-3etbob6s, S-mryj4twm]
status: partial
---

# Oxigraph as an embedded RDF store

## Summary
Oxigraph is a SPARQL graph database written in Rust, usable as a library (`oxigraph::store::Store`), from Python (`pyoxigraph`) or as a standalone server binary. It holds an RDF dataset as quads (default graph plus named graphs), in memory or on disk in RocksDB, and queries it with SPARQL 1.1 Query and Update. Its own pages call it "in heavy development", no 1.0 exists (newest version 0.5.11), and pyoxigraph is tagged Alpha on PyPI. The RocksDB part is a default Cargo feature that can be switched off; with it on, a build needs a C++20 compiler and Clang. The library documents "repeatable read" isolation, not ACID.

## Facts

### What it is, status, licence
- Oxigraph is a graph database implementing SPARQL, written in Rust, built on the RocksDB key-value store, with utilities to read and write RDF files; the README says it "is in heavy development and SPARQL query evaluation has not been optimized yet". [DOC S-z4kbze7e]
- The newest `oxigraph` version on crates.io is 0.5.11 (2026-09-02, MSRV 1.87) and its version list holds only 0.x entries, so no 1.0 release or vendor "stable" statement exists to cite. [DER S-uohdppyd: the registry's version list (newest 0.5.11, no 1.x entry) and the README's own "heavy development" wording]
- The README points to GitHub milestones for the roadmap; whether a 1.0 milestone or a stability promise exists there is not known, because the milestone list could not be read (the GitHub API answered with a rate-limit error). [UNK: logged in `_gaps.md`]
- Licence: the repository is dual-licensed Apache-2.0 or MIT at the user's option, and the `oxigraph` crate is `MIT OR Apache-2.0` on crates.io. [DOC S-z4kbze7e, S-uohdppyd]
- The project has four deliverables: the Rust library crate `oxigraph` (the `Store`), `pyoxigraph` (Python bindings), JavaScript/WebAssembly bindings, and the `oxigraph` binary from the crate `oxigraph-cli` (earlier called Oxigraph server), which serves the SPARQL 1.1 Protocol and Graph Store Protocol over HTTP with `oxigraph serve --location DIR`. [DOC S-z4kbze7e, S-3qbz2t4u]
- PyPI lists `pyoxigraph` 0.5.11 with the classifier `Development Status :: 3 - Alpha`, `requires_python >=3.8`, binary wheels for manylinux_2_28 (x86_64, aarch64), musllinux, macOS and Windows, and an sdist. [DOC S-45qncmsz]

### Embedding: in-memory, on disk, read-only, build
- `Store::new()` makes an in-memory store "without RocksDB"; `Store::open(path)` opens a read-write store and creates it if missing; `Store::open_with_options(path, StoreOptions)` adds RocksDB options such as `max_open_files`. The on-disk constructors exist only with the `rocksdb` feature on a non-wasm target, and only one read-write `Store` can exist at a time. [DOC S-bfv5hqkn]
- `Store::open_read_only(path: impl AsRef<Path>) -> Result<Self, StorageError>` opens an existing database read-only; the docs warn that opening read-only "while having an other process writing the database is undefined behavior". [DOC S-bfv5hqkn]
- pyoxigraph mirrors this: `Store(path=None)` calls `Store::open(path)` or, with no path, `Store::new()`, and the static method `Store.read_only(path)` calls `Store::open_read_only`. [CODE S-nxnd5tsp: python/src/store.rs#PyStore]
- The RocksDB backend can be dropped: "disabling the `rocksdb` default feature" (`default-features = false`) leaves only the in-memory fallback, which is the default when compiling to WASM. [DOC S-bytyyxb4]
- The crate's features are `default = ["rocksdb"]`, `http-client` (with `-native-tls`, `-rustls-webpki`, `-rustls-native` variants), `rocksdb-pkg-config`, `rdf-12`, `js` and `rocksdb-debug`. [CODE S-5ty62hy3: lib/oxigraph/Cargo.toml#features]
- Building with RocksDB needs "Clang for the RocksDB Rust bindings" besides Rust and Cargo, and by default the sys crate "builds RocksDB as part of this crate"; a shared RocksDB can be linked instead through the `pkg-config` feature. [DOC S-3qbz2t4u, S-4ucs6ogm]
- The sys crate's build script compiles the vendored RocksDB sources and the API shim with the `cc` crate as C++ with `-std=c++20`, generates bindings with `bindgen`, and in the `pkg-config` mode requires a system RocksDB of at least 9.10.0. [CODE S-rw3phgvf: oxrocksdb-sys/build.rs#build_rocksdb]
- The sys crate `oxrocksdb-sys` declares its licence as `GPL-2.0-only OR Apache-2.0`, a different expression from the `MIT OR Apache-2.0` of the other crates. [CODE S-c4gfzuad: oxrocksdb-sys/Cargo.toml#license]
- On-disk data format changes are migrated on first open: 0.2 migrates the version 0 format, and 0.5 migrates databases that held RDF-star triples ("automatically migrated on the first opening"), after which serialization output differs. [DOC S-dcliqq63]

### Named graphs and the default graph
- An RDF 1.1 dataset has exactly one unnamed default graph (which may be empty) and zero or more named graphs, each a pair of an IRI or blank node name and a graph; a SPARQL query runs against a dataset, `FROM` merges graphs into the default graph, `FROM NAMED` adds named graphs, and `GRAPH` makes the active graph one of the named graphs, while matching outside `GRAPH` uses the default graph. [DOC S-a5hei6wa, S-axwbq3bp]
- `Store` is a quad store: `insert(quad)` takes a `Quad` whose graph is `GraphName::DefaultGraph` or a named graph; `quads_for_pattern(s, p, o, graph)`, `named_graphs()`, `contains_named_graph`, `insert_named_graph`, `clear_graph` and `remove_named_graph` manage graphs, and `clear_graph` keeps the (empty) graph while `remove_named_graph` drops it. [DOC S-bfv5hqkn]
- In a query the default graph is by default "only the store default graph"; `QueryDatasetSpecification::set_default_graph_as_union()` makes it the union of all graphs, `set_default_graph(Vec<GraphName>)` picks graphs, and `set_available_named_graphs` limits what `GRAPH` can see; a `PreparedSparqlQuery` exposes it through `dataset_mut()`. [DOC S-fi3wa4vw, S-3etbob6s]
- In pyoxigraph, `Store.query(...)` takes `use_default_graph_as_union` (default false: "Disabled by default"), `default_graph` and `named_graphs` keyword arguments. [CODE S-nxnd5tsp: python/src/store.rs#PyStore]
- Loading: `load_from_reader` and `load_from_slice` are atomic but "quite slow and memory hungry"; `bulk_loader()` returns a `BulkLoader` whose loaded quads are saved only by `commit()`, with a memory target of about 2GB per thread and two threads by default, and `without_atomicity` lets it write during the load. A loaded Turtle file can be put into a named graph with `RdfParser::with_default_graph`. [DOC S-bfv5hqkn, S-mzu53xnc]

### SPARQL support
- The README and crate README claim SPARQL 1.1 Query, SPARQL 1.1 Update and SPARQL 1.1 Federated Query, plus the XML, JSON, CSV and TSV result formats; RDF 1.2 and SPARQL 1.2 are behind the `rdf-12` feature, described as "preliminary support for 1.2 RDF and SPARQL drafts". [DOC S-z4kbze7e, S-bytyyxb4]
- In 0.5.11 the entry point is `SparqlEvaluator::new().parse_query(q)?.on_store(&store).execute()?`, which returns `QueryResults::Solutions` (SELECT), `Boolean` (ASK) or `Graph` (CONSTRUCT and DESCRIBE); updates use `parse_update(u)`. `Store::query`, `Store::query_opt` and the alias `QueryOptions` are deprecated since 0.5.0 in favour of `SparqlEvaluator`. [DOC S-guwnayzo, S-mryj4twm, S-iqad4pe3]
- The parser crate `spargebra` 0.4.7 supports SPARQL 1.1 Query and Update, models property paths (`Reverse`, `Sequence`, `Alternative`, `ZeroOrMore`, `OneOrMore`, `ZeroOrOne`, `NegatedPropertySet`), and differs from the specification in not allowing `\uXXXX` escapes outside IRIs and string literals unless `standard-unicode-escaping` is enabled. [DOC S-ifojpzaw, S-coloiwrz]
- `SERVICE` calls use "a simple HTTP 1.1 client" only if the optional `http-client` feature is enabled; otherwise a custom `ServiceHandler` or `DefaultServiceHandler` must be supplied through `with_service_handler` or `with_default_service_handler`. [DOC S-guwnayzo]
- A running query is aborted with a `CancellationToken` passed to `with_cancellation_token`, and the CLI `query` command gained `--timeout-s` in 0.5.0-beta.5. [DOC S-dcliqq63, S-guwnayzo]
- The library has no general query timeout setting: `SparqlEvaluator` has no such method, its only timeout setter (`with_http_timeout`) exists only under `http-client` and bounds HTTP requests, and pyoxigraph's `Store.query` signature has no timeout argument. [DER S-guwnayzo, S-jgxzxayp, S-nxnd5tsp: method lists and the cfg-gated `with_http_timeout`; absence read from the docs of 0.5.11]
- What a `SERVICE` clause does in a build without `http-client` and without a handler (an error or a silent empty result) is not stated on the pages read. [UNK: logged in `_gaps.md`]

### Serialisation formats and crates
- `RdfFormat` (oxrdfio, re-exported as `oxigraph::io`) has the variants `N3`, `NQuads`, `NTriples`, `RdfXml`, `TriG`, `Turtle` and `JsonLd`, is non-exhaustive, and `supports_datasets()` tells graph formats from dataset formats. [DOC S-z2qagps6]
- JSON-LD 1.1 has been implemented and "enabled by default" since 0.5.5; the crate README at the 0.5.11 tag still lists only Turtle, TriG, N-Triples, N-Quads and RDF/XML, while the repository README adds JSON-LD. [DOC S-dcliqq63, S-z4kbze7e, S-bytyyxb4]
- The pieces are separate crates: `oxrdf` (data model), `oxrdfio` (parsers and serializers over `oxttl`, `oxrdfxml`, `oxjsonld`), `spargebra` (parser), `spareval` (evaluator), `sparopt` (optimizer), `sparesults` (result formats), `oxsdatatypes` and `spargeo` (partial GeoSPARQL); 0.5.11 pins oxrdfio 0.2.6, spargebra 0.4.7, sparesults 0.3.4 and spareval 0.2.7. [DOC S-z4kbze7e, S-bfv5hqkn]

### Concurrency, transactions, durability
- The store ensures "repeatable read" isolation: only committed changes are visible and the visible state does not change during one read operation or one SPARQL update; `start_transaction()` gives atomic transactions that keep "the complete set of changes into memory", so they are not for loading tens of millions of triples. `Store` is `Clone`, `Send` and `Sync`. [DOC S-bfv5hqkn]
- `flush()` "ensures that all writes are saved on disk", but flushes happen on background threads and "might lag a little bit"; `backup(dir)` creates an independent database openable with `Store::open`, using hard links when on the same file system. [DOC S-bfv5hqkn]
- Recent fixes touch the transaction layer: 0.5.8 fixed RocksDB transactions where reading your own writes did not work, and 0.5.9 made `Transaction` and `BulkLoader` `Send` and `Sync`. [DOC S-dcliqq63]
- The pages read use "repeatable read" and "atomic" and do not claim ACID, serializable isolation or crash-safety guarantees for the RocksDB store. [UNK: logged in `_gaps.md`]

### How it fits (a self-hosted CPU-only text-corpus service, Python over a Rust core)
- Embedding choices: a Python shell can use the `pyoxigraph` wheels (bundled RocksDB, no compiler on the target), while a Rust core links the `oxigraph` crate and can set `default-features = false` to drop RocksDB and the C++20 and Clang build requirements, at the price of an in-memory-only store. [DER S-45qncmsz, S-5ty62hy3, S-bytyyxb4, S-rw3phgvf: wheels exist for the platforms listed; build needs follow from the build script and the feature list]
- Offline operation: the default feature set contains no HTTP client, so a build without `http-client` has no code path that makes a federated `SERVICE` call over the network, and no model or GPU is involved. [DER S-5ty62hy3, S-guwnayzo: default = rocksdb only; the HTTP client is feature-gated]
- Process layout: one process holds the single read-write `Store`; a second process can serve reads from a `backup()` directory, which "operates independently", rather than from a read-only handle on a live writer, which the docs call undefined behaviour. [DER S-bfv5hqkn: open, open_read_only and backup documentation]
- Reproducibility: pin the exact crate or wheel version and keep the data rebuildable from an N-Quads dump (`dump_to_writer`), since the format has been migrated in place on open between 0.x releases and no downgrade path is documented. [DER S-bfv5hqkn, S-dcliqq63: dump is the documented move-away path; migration on first open]
- Provenance and rule versions as graphs: one named graph per source document or per rule-set version lets a `GRAPH` clause or `default_graph`/`named_graphs` scope a query, and one SPARQL update request applies "in a transactional manner", so a graph can be replaced in one request. [DER S-a5hei6wa, S-nxnd5tsp, S-fi3wa4vw: dataset model, transactional update docstring, per-query dataset specification]
- Scope: the lists of features, crates and specifications read name no full-text index, analyzer or vector index, so text search and embedding retrieval stay with the existing retrieval design (see `agents/hybrid-retrieval.md`) and Oxigraph holds the graph-shaped metadata. [DER S-z4kbze7e, S-5ty62hy3: absence in the feature and specification lists]

## Reference
| need | Rust (0.5.11) | pyoxigraph | source |
|---|---|---|---|
| in-memory store | `Store::new()` | `Store()` | S-bfv5hqkn, S-nxnd5tsp |
| on-disk read-write | `Store::open(path)` | `Store(path)` | S-bfv5hqkn, S-nxnd5tsp |
| read-only | `Store::open_read_only(path)` | `Store.read_only(path)` | S-bfv5hqkn, S-nxnd5tsp |
| query | `SparqlEvaluator::new().parse_query(q)?.on_store(&store).execute()` | `store.query(q, ...)` | S-guwnayzo, S-nxnd5tsp |
| union default graph | `prepared.dataset_mut().set_default_graph_as_union()` | `use_default_graph_as_union=True` | S-fi3wa4vw, S-nxnd5tsp |
| abort a query | `CancellationToken` | not shown | S-guwnayzo |
| bulk load | `store.bulk_loader()` then `commit()` | `store.bulk_load(...)` | S-mzu53xnc |
| drop RocksDB | `default-features = false` | n/a (wheels bundle it) | S-bytyyxb4, S-45qncmsz |

- Related kb topics: `agents/hybrid-retrieval.md` (text and vector retrieval), `arch/texts-catalogue-formats.md` (rules and texts kept as data), `arch/python-single-package-extras.md` (a Python package with optional extras).
- No anchor article exists for this topic; the back-link is left out.

## Examples
- SNIPPET: in-memory-only build of the Rust crate with RocksDB switched off; context: oxigraph 0.5.11, any target, no C++ toolchain needed; checked: syntax [DOC S-bytyyxb4]
```toml
[dependencies]
oxigraph = { version = "=0.5.11", default-features = false }
```
- SNIPPET: pyoxigraph on-disk store, a named graph per rule-set version, a query that treats all graphs as the default graph; context: pyoxigraph 0.5.11, Python 3.8 or newer, placeholder IRIs and path; checked: syntax [CODE S-nxnd5tsp: python/src/store.rs#PyStore]
```python
from pyoxigraph import Literal, NamedNode, Quad, Store

store = Store("/srv/corpus/rdf")  # Store() would be in-memory
graph = NamedNode("https://corp.example.com/graph/ruleset-2026-10")
store.add(
    Quad(
        NamedNode("https://corp.example.com/rule/PL-0001"),
        NamedNode("https://corp.example.com/vocab/pattern"),
        Literal("ul. Przykladowa 1"),
        graph,
    )
)
rows = store.query(
    "SELECT ?rule ?pattern WHERE { ?rule <https://corp.example.com/vocab/pattern> ?pattern }",
    use_default_graph_as_union=True,
)
for row in rows:
    print(row["rule"], row["pattern"])
```
- SNIPPET: Rust, union default graph on a prepared query; context: oxigraph 0.5.11 with `use oxigraph::sparql::SparqlEvaluator; use oxigraph::store::Store;` and a `Store` named `store`; checked: no [DER S-3etbob6s, S-fi3wa4vw: method signatures `dataset_mut` and `set_default_graph_as_union`]
```rust
let mut prepared = SparqlEvaluator::new().parse_query("SELECT * WHERE { ?s ?p ?o }")?;
prepared.dataset_mut().set_default_graph_as_union();
let results = prepared.on_store(&store).execute()?;
```
