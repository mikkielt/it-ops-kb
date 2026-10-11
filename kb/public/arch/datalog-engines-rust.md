---
topic: arch/datalog-engines-rust
priority: P3
applies_to: "Embeddable Datalog engines for Rust: crepe 0.2.0, ascent 0.8.1, datafrog 2.0.1 (crates.io latest at retrieval 2026-10-11); polonius-engine 0.13.0 as a datafrog user"
retrieved_utc: 2026-10-11
sources: [S-vebfsq3a, S-tnv3dwqy, S-lpnwfh7p, S-o2h35tvo, S-tmiyxzib, S-qwtlpuec, S-qtsiwo4d, S-kneimuih, S-cjeqjcrh, S-gixrekn4, S-34fj2zgp, S-wn6nwfee, S-k3cjuiam, S-4mwzuy4t, S-vy6ewhyh]
status: partial
---

# Embeddable Datalog engines for Rust: Crepe, Ascent, Datafrog

## Summary
Three Rust crates run Datalog-style rules inside an ordinary program: Crepe and Ascent as procedural macros that turn a rule block into Rust at compile time, and Datafrog as a small library whose caller writes the iteration loop by hand. All three compute a fixed point such as a transitive closure in process, on the CPU, with no server. Crepe and Ascent support stratified negation; Ascent adds lattices, aggregation and parallel evaluation; Datafrog offers an anti-join but leaves stratification to the caller. None of the three documents loading rules at runtime, and only Datafrog returns its results in a defined (sorted) order. The versions are the latest on crates.io at retrieval; this topic compares the engines and does not choose one.

## Facts
### Crepe
- Crepe is a library for writing declarative logic programs in Rust with a Datalog-like syntax, supplied as a procedural macro (`crepe!`) that generates the code and interoperates with ordinary Rust. [DOC S-vebfsq3a]
- The README lists as features semi-naive evaluation, stratified negation, automatic generation of relation indices, calling Rust functions from rules, a typesafe way to initialise `@input` relations, and compilation together with the rest of the Rust code. [DOC S-vebfsq3a]
- crates.io lists 0.2.0 (published 2025-12-14) as the latest version, not yanked, under `MIT OR Apache-2.0`; the release before it, 0.1.8, dates from 2023-03-19. [DOC S-lpnwfh7p]
- A relation is a tuple `struct`; `@input` marks one that is fed through `extend`, `@output` one that `run` returns, and an unmarked one is intermediate; a rule that derives an `@input` relation is a macro error. [CODE S-tnv3dwqy: src/lib.rs#Context::new]
- Relations automatically derive `Eq`, `PartialEq`, `Hash`, `Copy` and `Clone`, so column types must be `Copy` (references stand in for owned data). [CODE S-tnv3dwqy: src/lib.rs#crepe]
- Rules may contain Rust expressions, boolean conditions in parentheses, `let` bindings and `for` iteration over an iterator; the generated code is split into strata for stratified negation. [CODE S-tnv3dwqy: src/lib.rs#crepe]
- A negation whose relation lies in the same strongly connected component as the rule head is rejected while the macro expands, with the message that it "creates a dependency cycle and cannot be stratified". [CODE S-tnv3dwqy: src/lib.rs#Context::new]
- `run()` consumes the runtime and returns a tuple of `HashSet<Rel>`, one per `@output` relation; it calls `run_with_hasher` with `std::collections::hash_map::RandomState`, and `run_with_hasher::<S>()` accepts another `BuildHasher + Default`. [CODE S-tnv3dwqy: src/lib.rs#run, run_with_hasher]
- The crate documentation and README name no aggregation construct (count, sum, min, max); counting or grouping is done in Rust over the returned sets. [DER S-vebfsq3a, S-tnv3dwqy: the README feature list and the macro documentation list none]

### Ascent
- Ascent calls itself a logic programming language (similar to Datalog) embedded in Rust via macros; its paper describes procedural macros that compile rules to Rust, using index generation and semi-naive evaluation. [DOC S-qwtlpuec, S-gixrekn4]
- crates.io lists 0.8.1 (published 2026-08-29) as the latest version, under `MIT`, with a minimum Rust version of 1.85. [DOC S-o2h35tvo]
- The manifest enables the `par` feature (rayon and dashmap, for the parallel macros) by default and declares `license = "MIT"`. [CODE S-qtsiwo4d: ascent/Cargo.toml#features, package]
- The README documents lattices (a `lattice` whose last column implements `Lattice`), stratified negation and aggregation (`sum`, `min`, `max`, `count`, `mean`, plus user-defined aggregators), generative clauses (`for`, `if`), and `ascent_source!` with `include_source!` to compose rule sets. [DOC S-qwtlpuec]
- `ascent_run!` evaluates the program where it is invoked so local variables are in scope; `ascent_par!` and `ascent_run_par!` produce parallel code on `rayon` and need `Send + Sync` columns; `#[ds(...)]` backs a relation with a custom data structure (BYODS), for example from the `ascent-byods-rels` crate. [DOC S-qwtlpuec]
- The paper stratifies rules into strongly connected components before execution, evaluates each semi-naively, and compares performance with Datafrog, Flix and Soufflé; it also reimplements the Rust borrow checker in Ascent. [DOC S-gixrekn4]
- In serial mode a default relation is a `Vec` of tuples and its indices are hash maps keyed with the fixed `FxHasher`; parallel mode uses `boxcar::Vec` and `DashMap`. [CODE S-kneimuih: ascent/src/rel.rs#rel; S-cjeqjcrh: ascent/src/internal.rs#RelIndexType1]
- Whether the README or release notes promise the same row order from run to run, in serial or parallel mode, is not stated. [UNK]

### Datafrog
- Datafrog describes itself as a lightweight Datalog engine to embed in other Rust programs; it has no runtime and relies on the caller to build and repeatedly apply the update rules. [DOC S-34fj2zgp]
- crates.io lists 2.0.1 (published 2019-01-02) as the latest version under `Apache-2.0/MIT`; the repository head at retrieval is a merge dated 2026-08-19 that replaced an archived CI action. [DOC S-tmiyxzib, S-k3cjuiam]
- A `Relation` is a sorted, deduplicated `Vec` of tuples (`from_vec` sorts and dedups); a `Variable` is a monotonically increasing set whose tuples pass through to-add, recent and stable stages as `Iteration::changed()` is called. [CODE S-wn6nwfee: src/lib.rs#Relation, Variable]
- Operations on a `Variable` include `from_join`, `from_map`, `from_antijoin` (against a fixed `Relation`) and leapfrog `from_leapjoin` with `extend_with`, `extend_anti`, `filter_with` and `filter_anti` leapers. [CODE S-wn6nwfee: src/lib.rs#Variable::from_join, from_antijoin, from_leapjoin]
- Negation is limited to an anti-join against a fixed `Relation`; the source has no stratification step, so ordering a negation after the relation it reads is the caller's work, and the API has no aggregation primitive. [DER S-wn6nwfee: `from_antijoin` takes `&Relation<K>`; no stratification or aggregate item in src/lib.rs]
- `Variable::complete()` returns a `Relation`, so the result comes back sorted by the tuple's `Ord`, whatever hashing was used. [CODE S-wn6nwfee: src/lib.rs#Variable::complete]
- `polonius-engine` 0.13.0, the core of the Rust borrow-checker model, lists `datafrog = "2.0.0"` as a dependency. [CODE S-4mwzuy4t: polonius-engine/Cargo.toml#dependencies]

### Rules at runtime and result order
- Rust's `HashSet` iterates in arbitrary order and its default hasher is randomly seeded, so the sets Crepe's `run()` returns are not in a stable order from one process to the next unless the caller sorts them or passes a fixed hasher. [DER S-vy6ewhyh, S-tnv3dwqy: `HashSet` docs state arbitrary order and random seeding; `run()` uses `RandomState`]
- Crepe and Ascent take their rules as the tokens of a macro invocation, expanded when the crate is built, and Datafrog's rules are Rust statements in the caller's loop; none of the READMEs describes reading rules from a file or string at runtime. [DER S-vebfsq3a, S-qwtlpuec, S-34fj2zgp: macros expand at compile time; Datafrog "has no runtime"]
- Whether any of the three plans or rules out loading rules at runtime is not stated in the READMEs or crate documentation read. [UNK]

### How it fits
- For a CPU-only, offline service the three engines are alike: each is a Rust library compiled into the host program, so no daemon, network call or model file is involved at runtime. [DER S-vebfsq3a, S-qwtlpuec, S-34fj2zgp: "compiled directly with the rest of your Rust code", "embedded in Rust via macros", "intended to be embedded"]
- Rules kept as data, read from a file by a running service, fit none of the engines directly: a rule change with Crepe or Ascent means regenerating Rust and rebuilding, and with Datafrog it means writing an interpreter that maps data rules onto `from_join` and `from_antijoin` calls. [DER S-vebfsq3a, S-qwtlpuec, S-34fj2zgp: rules are compile-time macro input or hand-written Rust]
- A closure rule (transitive closure over an edge relation) is the first example in each README, and a contradiction rule that needs "no such fact" needs negation: Crepe and Ascent provide it as stratified negation, Datafrog as an anti-join the caller orders. [DER S-vebfsq3a, S-qwtlpuec, S-34fj2zgp: the README closure examples and each engine's negation facts above]
- A conflict report that must be byte-identical between runs needs its own ordering step with Crepe (unordered sets) and possibly Ascent (order not promised); Datafrog's output is already sorted. [DER S-vy6ewhyh, S-tnv3dwqy, S-wn6nwfee: unordered `HashSet` results, no stated Ascent order, sorted `Relation`]

## Reference
| engine | version (crates.io, 2026-10-11) | licence | rule definition time | negation | aggregation | status |
|---|---|---|---|---|---|---|
| Crepe | 0.2.0 (2025-12-14) | MIT OR Apache-2.0 | compile time (`crepe!` macro) | stratified; cycle is a macro error | none documented | releases 2023-03-19 and 2025-12-14; no status word in README |
| Ascent | 0.8.1 (2026-08-29) | MIT | compile time (`ascent!`, `ascent_run!` macros) | stratified | `sum`, `min`, `max`, `count`, `mean`, user-defined | 0.7.0 2024-10-06, 0.8.0 2025-03-02, 0.8.1 2026-08-29; no status word in README |
| Datafrog | 2.0.1 (2019-01-02) | Apache-2.0/MIT | Rust code in the caller's loop | anti-join on a fixed relation; no stratifier | none in the API | last release 2019; repository head 2026-08-19 (CI change); no status word in README |

- Sources by engine: Crepe https://github.com/ekzhang/crepe (tag v0.2.0), https://crates.io/crates/crepe; Ascent https://github.com/s-arash/ascent (tag ascent-v0.8.1), https://crates.io/crates/ascent, CC 2022 paper https://s-arash.github.io/ascent/cc22main-p95-seamless-deductive-inference-via-macros.pdf; Datafrog https://github.com/rust-lang/datafrog (tag v2.0.1), https://crates.io/crates/datafrog.
- The BYODS paper the Ascent README cites is https://dl.acm.org/doi/pdf/10.1145/3622840 (not read here).

## Examples
- SNIPPET: transitive closure with Crepe over an edge relation; context: crepe 0.2.0, README example; checked: no [DOC S-vebfsq3a]
```rust
use crepe::crepe;

crepe! {
    @input
    struct Edge(i32, i32);

    @output
    struct Reachable(i32, i32);

    Reachable(x, y) <- Edge(x, y);
    Reachable(x, z) <- Edge(x, y), Reachable(y, z);
}
```
- SNIPPET: the same closure with Ascent; context: ascent 0.8.1, README example; checked: no [DOC S-qwtlpuec]
```rust
ascent! {
   relation edge(i32, i32);
   relation path(i32, i32);

   path(x, y) <-- edge(x, y);
   path(x, z) <-- edge(x, y), path(y, z);
}
```
