---
topic: arch/gorules-zen-engine
priority: P3
applies_to: "GoRules ZEN Engine (zen-engine, zen-expression) 2.1.3 and the JDM decision format: Rust crate, Python wheel (zen-engine), Node.js; GoRules docs as read 2026-10-11"
retrieved_utc: 2026-10-11
sources: [S-kvbchryu, S-jq7z2od2, S-5jpgqrfy, S-trcil35r, S-z4pp6bkj, S-su332252, S-heikuvcn, S-wgtknkrb, S-ltzwimxf, S-dxj7zgns, S-ccvh7i4b, S-ipghmg2f, S-osv63lk3, S-2fdfhonb, S-kwztlqad, S-ywjkyve4, S-zuff3zj3, S-mrvrg4c7, S-xfsmauei, S-cdmzxvsn, S-kwehxqwf, S-5dy4gz6x, S-k5bcjgda, S-ytvtdwbp, S-3tbh2eg2, S-dxo62u4b, S-yi5pmj5x, S-y7nfpahm, S-ibnjc3rf, S-enz7mrzn, S-z2auesug, S-q6ajn7wa, S-g6tbk57j, S-ujerrwih, S-i3rxlppy]
status: partial
---

# GoRules ZEN Engine and the JSON Decision Model (JDM)

## Summary
ZEN Engine is an MIT-licensed business rules engine written in Rust that runs decisions stored as JSON (the JSON Decision Model, JDM): a graph of typed nodes joined by edges. It is embedded in-process through a Rust crate and Python, Node.js and Go bindings, and the JSON can be loaded from anywhere. A decision can hold function nodes, which are JavaScript run in QuickJS and can make HTTP calls; at release 2.1.3 no engine option, crate feature or binding setting was found that refuses them. Expressions (the ZEN language) have no I/O but include a random and a clock function. The open-source engine has no version or effective-date concept for decisions; release versioning exists in the commercial BRMS.

## Facts

### What it is
- ZEN Engine describes itself as a cross-platform open-source business rules engine written in Rust, with bindings for Node.js, Python, Go, Java, Kotlin and .NET; decisions are stored as portable JSON and "loading the JSON is up to you". [DOC S-kvbchryu]
- The README calls version 2.0 the first stable release of the new engine line (policy documents, workspace analysis, per-column collect, pre-compiled engine), and the project accepts no code contributions at present. [DOC S-kvbchryu]
- The repository LICENSE at the 2.1.3 tag is the MIT licence text. [DOC S-jq7z2od2]
- At the retrieval date crates.io lists zen-engine 2.1.3 (published 2026-10-09, licence MIT), PyPI lists zen-engine 2.1.3 and npm lists @gorules/zen-engine 2.1.4. [DOC S-ywjkyve4, S-zuff3zj3, S-mrvrg4c7]
- The engine's own version string is a compile-time constant taken from the crate version. [CODE S-trcil35r: core/engine/src/lib.rs#ENGINE_VERSION]

### The JDM file
- A JDM file has two sections, `nodes` and `edges`; the engine ignores unknown top-level fields, so tools may add metadata, and only `nodes` and `edges` are part of the format. [DOC S-xfsmauei]
- A node has `id`, `type`, `name`, `position` and a type-specific `content`; an edge has `id`, `sourceId`, `targetId` and `sourceHandle`. [DOC S-cdmzxvsn]
- The Rust type `DecisionNodeKind` is a `type`-tagged enum with eight camelCase variants (`inputNode`, `outputNode`, `functionNode`, `decisionNode`, `decisionTableNode`, `expressionNode`, `switchNode`, `customNode`) and no catch-all variant. [CODE S-heikuvcn: core/types/src/decision/mod.rs#DecisionNodeKind]
- The docs list seven node types and omit `customNode`, which carries a `kind` string and a `config` object and is handled by a host-supplied adapter. [DER S-cdmzxvsn, S-heikuvcn: the docs table has seven rows; the enum has eight variants]
- A decision table has `hitPolicy` `first` (default) or `collect`; an output field ending in `[]` collects across all matching rows while the rest of the table stays first-hit, and an empty rule cell matches any value. [DOC S-cdmzxvsn]
- An expression node is a list of key and ZEN-expression pairs and `$` refers to a value computed earlier in the same node; a switch node holds conditions whose statement ids are the edge `sourceHandle`s; a decision node names another decision by `key`. [DOC S-cdmzxvsn]
- The docs call the `passThrough` property true by default, while the Rust struct marks it `#[serde(default)]` on a `bool`, which is false when the key is absent; the effective default was not run. [UNK: logged in `_gaps.md`]
- Content is either a graph or a policy document: a JSON object with a `blocks` key is read as a policy and anything else as a graph. [CODE S-q6ajn7wa: core/engine/src/model/decision_content.rs#DecisionContent]
- `create_decision` refuses policy content with a content-kind error; a policy is evaluated by key through a loader. [CODE S-z4pp6bkj: core/engine/src/engine.rs#DecisionEngine]
- The docs say a complete JSON Schema for JDM files is in the zen repository; no such file is in the repository tree at the tag, and the JDM editor package is documented to export a Zod schema for validation. [UNK: logged in `_gaps.md`]

### Function nodes and I/O
- A function node holds JavaScript `source` that exports a `handler`; the docs list the built-in modules `dayjs`, `big.js`, `zod`, `http` and `zen` and a default execution timeout of 5000 ms. [DOC S-kwehxqwf]
- The function runtime is created with rquickjs 0.10, which describes itself as high-level bindings to the QuickJS JavaScript engine. [DER S-5jpgqrfy, S-g6tbk57j: Cargo.toml dependency line plus the crate description]
- The `http` module that a function node can import offers get, head, post, patch, put and delete; it goes through a host callback `__executeHttp` when one is registered and otherwise through a native reqwest client. [CODE S-wgtknkrb: core/engine/src/nodes/function/v2/module/http/mod.rs#execute_http]
- `DecisionEngine` keeps an optional HTTP handler that is `None` by default and is set with `with_http_handler`. [CODE S-z4pp6bkj: core/engine/src/engine.rs#DecisionEngine]
- The Python binding's engine options are only `loader` and `customHandler`, and its evaluate options are `max_depth` and `trace`, so a Python host has no HTTP handler to register. [CODE S-2fdfhonb: bindings/python/zen.pyi#ZenEngineOptions]
- The engine-wide settings are three atomics (`nodes_in_context`, `function_timeout_millis`, `http_auth`); none switches function nodes off. [CODE S-su332252: core/engine/src/config.rs#ZenConfig]
- The Node.js binding documents `overrideConfig` with `functionTimeoutMillis` (default 5000), `nodesInContext` (default true) and `httpAuth` (default true, IAM-signed requests from the `http` module). [DOC S-ujerrwih]
- That `override_config` function only stores its three optional values into the process-wide `ZEN_CONFIG` and offers no switch for function nodes. [CODE S-osv63lk3: bindings/nodejs/src/config.rs#override_config]
- The crate's Cargo features are `default = []`, `bindgen` and `arbitrary_precision`; none concerns function nodes, and the HTTP client and JSON-schema libraries are compiled in on non-wasm targets. [CODE S-5jpgqrfy: core/engine/Cargo.toml#features]
- Node dispatch in the graph walker is a fixed `match` on the node kind (`FunctionNode` goes to `FunctionNodeHandler`), and `Decision::validate` checks only that there is exactly one input node and no cycle. [CODE S-ltzwimxf: core/engine/src/decision_graph/graph.rs#DecisionGraph]
- No loader, engine setting, crate feature, `NodeHandler` override or validation hook that rejects function nodes was found at 2.1.3; the observable route is to inspect each node's `type` before loading (a Rust host can match `DecisionNodeKind::FunctionNode` on the parsed model, a Python host scans the JSON), and sub-decisions named by `decisionNode` and `zen.evaluate` must be scanned too. [DER S-5jpgqrfy, S-su332252, S-ltzwimxf, S-heikuvcn: absence over the manifest, config, dispatch and node types read]
- Whether a later release, the BRMS or the GoRules Agent adds a switch to disable function nodes is not in the pages read. [UNK: logged in `_gaps.md`]

### Expression language
- ZEN has a standard mode (expression and switch nodes, output cells) and a unary-test mode (decision table input cells with a field name, for example `>= 100` or `'US', 'CA'`); `#` is the current element in closures and `$` the tested value. [DOC S-ytvtdwbp]
- The operators are `+ - * / % ^`, comparison, `and or not`, ternary, `??` and range tests such as `x in [1..10]`; division or modulo by zero yields null and numeric overflow is an error. [DOC S-k5bcjgda]
- The built-in functions are math, string (including `matches`, `extract`, `fuzzyMatch`), array (`map`, `filter`, `some`, `all`, `count`, `merge`), date (`d`, `duration`) and type functions; none of them is an I/O function. [DOC S-5dy4gz6x]
- `rand(n)` draws from a random generator and `d()` with no argument reads the current clock, so an expression that uses either is not a pure function of its input. [CODE S-ccvh7i4b: core/expression/src/functions/internal.rs#rand]
- The expression crate's dependencies include no HTTP client, network or file-system library, so expressions do no I/O; the engine reaches I/O only through a loader, a function node's `http` module or `zen.evaluate`. [DER S-dxj7zgns, S-5dy4gz6x, S-wgtknkrb: manifest, function list and function-node module]

### Versions, loading and bindings
- The in-memory model `GraphContent` has `nodes`, `edges`, optional `imports` and compiled caches and no version or date field, and the docs tell a standalone user that storing, versioning and distributing JDM files is their job; the engine therefore has no version or effective-date concept for a decision. [DER S-q6ajn7wa, S-dxo62u4b: struct fields read plus the standalone note]
- The BRMS publishes releases as immutable snapshots with semantic versions (patch, minor, major), drafts without a version, and environments that each serve one release; v2 (git-like) projects add branches and commit history. [DOC S-3tbh2eg2, S-z2auesug]
- Whether the BRMS can schedule a release to take effect at a date is not stated on the release and project-version pages read. [UNK: logged in `_gaps.md`]
- A self-hosted BRMS needs a licence key from the vendor's portal and outbound HTTPS for validation (`LICENSE_MODE` online or offline), whereas the JDM Editor React component and the standalone editor repository carry MIT licence files. [DOC S-y7nfpahm, S-ibnjc3rf, S-enz7mrzn]
- `LoaderConfig` builds a static (in-memory), filesystem or zip loader, and a zip loader turns every `.json` entry into a decision keyed by its path, which the docs pair with BRMS release ZIPs. [CODE S-ipghmg2f: core/engine/src/loader/config.rs#LoaderConfig]
- In Python, `zen.ZenEngine().create_decision(json_text)` returns a decision whose `evaluate(context, {"trace": True})` result has `result`, `performance` and a per-node `trace`; loaders are static, `fs`, `zip` or a callback. [DOC S-yi5pmj5x]
- In Rust, `evaluate_with_opts` with `EvaluationOptions { trace: true, .. }` returns the per-node trace and the total time. [DOC S-i3rxlppy]
- The Rust default evaluation depth is 10 and the Python binding falls back to 5 when none is given. [DER S-z4pp6bkj, S-kwztlqad: EvaluationOptions default and PyZenEvaluateOptions default]
- PyPI release 2.1.3 ships abi3 wheels for manylinux (x86_64, aarch64), macOS (x86_64, arm64) and Windows (amd64) plus an sdist, each file with a SHA-256 in the JSON. [DOC S-zuff3zj3]
- The README support matrix marks the Python and Go bindings unsupported on linux musl and lists Python on linux, macOS and Windows only. [DOC S-kvbchryu]

### How it fits
- For a Python shell over a Rust core the zen-engine wheel is the same Rust core in-process: no server, no model and no GPU dependency, and the one runtime network path in a graph is a function node's `http` call. [DER S-zuff3zj3, S-5jpgqrfy, S-wgtknkrb: abi3 wheels, manifest, function-node http module]
- Rules kept as data and pinned by hash fit the static or filesystem loader: the JDM file is plain JSON with a stable byte form to hash, and loading it needs no cloud call. [DER S-xfsmauei, S-ipghmg2f: JSON file format plus loader config]
- Refusing function nodes and `customNode` is the caller's job: scan `type` before `create_decision`, refuse `functionNode` (and, if unused, `customNode`), and follow `decisionNode` keys. [DER S-heikuvcn, S-ltzwimxf: node enum and fixed dispatch]
- Effective dating has to live outside the engine, for example a manifest that maps a rule-set id and a valid-from date to a file hash which the host selects before loading; the BRMS release number is not an effective date. [DER S-q6ajn7wa, S-3tbh2eg2: no date field in the model; releases are semantic versions]
- To keep results reproducible, pass the evaluation date in the input rather than calling `d()`, and avoid `rand`. [DER S-ccvh7i4b, S-5dy4gz6x: clock and random functions]

## Reference
- Node types (docs table at S-cdmzxvsn, enum at S-heikuvcn):

| `type` | content | in docs list |
|---|---|---|
| `inputNode` | optional `schema` (JSON Schema string) | yes |
| `outputNode` | optional `schema` | yes |
| `decisionTableNode` | `hitPolicy`, `inputs`, `outputs`, `rules`, transform attributes | yes |
| `expressionNode` | `expressions` (id, key, value), transform attributes | yes |
| `functionNode` | `source` (JavaScript) | yes |
| `switchNode` | `hitPolicy`, `statements` (id, condition) | yes |
| `decisionNode` | `key` of another decision, transform attributes | yes |
| `customNode` | `kind`, `config` | no |

- Transform attributes (`inputField`, `outputPath`, `executionMode` single or loop, `passThrough`) are shared by table, expression and decision nodes (S-cdmzxvsn, S-heikuvcn).
- Engine settings: `function_timeout_millis` 5000, `nodes_in_context` true, `http_auth` true (S-su332252); the Node.js names are `functionTimeoutMillis`, `nodesInContext` and `httpAuth` (S-osv63lk3).
- Code read at git tag `zen-engine-v2.1.3` (S-5jpgqrfy and the other file rows); GoRules docs pages as retrieved 2026-10-11 (not versioned).
- Go: the README links the separate `gorules/zen-go` repository (S-kvbchryu).

## Examples
- SNIPPET: a minimal JDM graph with an input node, an expression node and an output node; context: ZEN Engine 2.1.3 (field names from the node-type docs, `passThrough` set explicitly); checked: syntax [DER S-xfsmauei, S-cdmzxvsn: file structure and node properties from the docs]
```json
{
  "nodes": [
    {"id": "in", "type": "inputNode", "name": "Request", "position": {"x": 0, "y": 0}, "content": {"schema": ""}},
    {"id": "calc", "type": "expressionNode", "name": "Total", "position": {"x": 200, "y": 0},
     "content": {"expressions": [{"id": "e1", "key": "total", "value": "price * quantity"}], "passThrough": true}},
    {"id": "out", "type": "outputNode", "name": "Response", "position": {"x": 400, "y": 0}, "content": {"schema": ""}}
  ],
  "edges": [
    {"id": "a", "sourceId": "in", "targetId": "calc", "type": "edge"},
    {"id": "b", "sourceId": "calc", "targetId": "out", "type": "edge"}
  ]
}
```
- SNIPPET: load a decision from text and evaluate it with tracing; context: `pip install zen-engine` 2.1.3; checked: syntax [DOC S-yi5pmj5x: create_decision, evaluate and the trace option as documented]
```python
import zen

with open("./rules/pricing.json", "r") as handle:
    content = handle.read()

engine = zen.ZenEngine()
decision = engine.create_decision(content)
response = decision.evaluate({"price": 10, "quantity": 3}, {"trace": True})
print(response["result"], response["performance"])
```
- SNIPPET: refuse function and custom nodes before loading; context: standard-library `json` and a graph document with a top-level `nodes` list; checked: syntax [DER S-heikuvcn, S-xfsmauei: node `type` strings and file structure]
```python
import json

REFUSED = {"functionNode", "customNode"}

def refused_nodes(text: str) -> list[str]:
    document = json.loads(text)
    if not isinstance(document, dict) or not isinstance(document.get("nodes"), list):
        raise ValueError("not a JDM graph")
    return [str(n.get("id")) for n in document["nodes"] if n.get("type") in REFUSED]
```
