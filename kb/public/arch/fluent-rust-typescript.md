---
topic: arch/fluent-rust-typescript
priority: P3
applies_to: "fluent-bundle 0.16.0, fluent 0.17.0, fluent-syntax 0.12.0 (Rust); @fluent/bundle 0.19.1, @fluent/syntax 0.19.0, @fluent/langneg 0.7.0 (npm); moz-fluent-linter 0.4.10; Fluent Syntax 1.0"
retrieved_utc: 2026-10-11
sources: [S1709, S-c7rozbcf, S-ey42zwsk, S-vktfavae, S-v5arxcqi, S-6dmythvr, S-fte52rkq, S-qetvxk3e, S-puf5y636, S-un2vqcl3, S-fi73q2gh, S-pkdj2ggv, S-3zcwxrkd, S-2msclknw, S-ewnl7di2, S-f67paqny, S-ihysyyjh, S-j6vzyt5y, S-ueumbn4x, S-5ehlhbmd, S-xxelwvq6, S-adkxxbxo, S-sui7jilt, S-2ctin4w5, S-34inydkn, S-yf4y3ooe, S-yxzyna3l, S-lj3rgbhb, S-ngxalogc, S-zqefeiow, S-zsnubksc, S-qucwxqjo, S-u5ks3e5h, S-v5hog4zh, S-fnbm2hx6, S-edmvqoen, S-ejm4457f, S-wo2rtyeb, S-2viytftj, S-tj5gqic5, S-jm4q5smn, S-ccvjl7yh, S-5bmxcoy4, S-mobvrkio, S-nqeg3xk3, S-wxarrmdh, S-5qwcsz2g, S-l53lrqoz, S-nmwvmitf]
status: partial
---

# Fluent in Rust and TypeScript: crates, @fluent/bundle, typed accessors, FTL linters

## Summary
Project Fluent publishes Rust crates (`fluent-rs` workspace: `fluent`, `fluent-bundle`, `fluent-syntax`, `fluent-fallback`, `fluent-resmgr`, plus `fluent-langneg` in its own repository) and npm packages (`@fluent/bundle`, `@fluent/syntax`, `@fluent/langneg`). The npm packages are Apache-2.0 and the crates Apache-2.0 OR MIT; both runtimes can hand formatting errors back to the caller in an array, and both wrap interpolated values in Unicode isolation marks by default. Neither project ships a generator of typed message accessors or an FTL linter: the closest are community packages (`fluent-typed`, `fluent-ts`) and Mozilla's `moz-fluent-linter` (Python, MPL-2.0). The official syntax parsers report invalid entries (`Junk`, `ParserError`), which is the only built-in validity check. Python runtime and FTL syntax are in [texts-catalogue-formats.md](texts-catalogue-formats.md).

## Facts
### Rust crates (fluent-rs)
- The fluent-rs workspace contains `fluent` (umbrella crate with convenience macros), `fluent-bundle` (low-level collection of messages for one locale), `fluent-fallback` (bundle management with locale fallback), `fluent-resmgr` (resource files to bundles), `fluent-syntax` (parser, AST, serializer), `fluent-pseudo`, `fluent-testing`, `intl-memoizer` and a `fluent-cli` tools folder. [DOC S-ey42zwsk]
- crates.io lists `fluent` 0.17.0 (published 2025-05-23), `fluent-bundle` 0.16.0, `fluent-syntax` 0.12.0, `fluent-fallback` 0.7.2 and `fluent-resmgr` 0.0.8 (all 2025-05-22), `fluent-langneg` 0.14.2 (2025-10-24) and `unic-langid` 0.9.6 (2025-05-09); all declare `Apache-2.0 OR MIT` (`unic-langid`: `MIT OR Apache-2.0`), and crates.io has no crate named `fluent-resource`. [DOC S-pkdj2ggv, S-3zcwxrkd, S-2msclknw, S-ewnl7di2, S-f67paqny, S-ihysyyjh, S-j6vzyt5y, S-ueumbn4x]
- `FluentResource` is a type of `fluent-bundle` (its `resource.rs`), not a package of its own. [DER S-ueumbn4x, S-v5arxcqi: crates.io answers 404 for `fluent-resource`; the type is defined in fluent-bundle's resource.rs]
- The workspace manifest sets `license = "Apache-2.0 OR MIT"` and a minimum Rust version of 1.67.0, requires `fluent-langneg = "0.13"` although 0.14.2 is out, and excludes `fluent-cli` from the workspace members. [CODE S-qetvxk3e: Cargo.toml#workspace.package]
- fluent-rs is not archived (last push 2026-09-27), and the 0.15.3 changelog entry calls that release a safe-harbor release before bringing on non-Mozilla community maintainers. [DOC S-5ehlhbmd, S-puf5y636]
- `fluent-langneg` 0.14.2 was relicensed to dual Apache-2.0 OR MIT; its README says the implementation is complete against its test corpus and that the path to 1.0 needs field experience. [DOC S-2ctin4w5, S-34inydkn]
- `FluentResource::try_new(String)` parses with the runtime parser and returns `Result<Self, (Self, Vec<ParserError>)>`: on syntax errors it still hands back the parsed resource together with the error list. [CODE S-v5arxcqi: fluent-bundle/src/resource.rs#FluentResource::try_new]
- `FluentBundle::new(Vec<LanguageIdentifier>)` uses the first locale for plural rules and the rest as fallback for date/time formatters, and its doc says it panics if no formatters can be found; `add_resource` takes anything that borrows a `FluentResource` (value, reference, `Rc`, `Arc`) and returns `Result<(), Vec<FluentError>>`, ignoring an id that is already present and reporting `FluentError::Overriding` (`add_resource_overriding` replaces it instead). [CODE S-vktfavae: fluent-bundle/src/bundle.rs#FluentBundle::add_resource]
- `get_message(&str)` returns `Option<FluentMessage>`, `FluentMessage::value()` returns an optional pattern, and `format_pattern(pattern, Option<&FluentArgs>, &mut Vec<FluentError>)` returns a `Cow<str>` while pushing resolver problems into the vector; the doc calls them non-fatal but to be logged or reported. [CODE S-vktfavae: fluent-bundle/src/bundle.rs#FluentBundle::format_pattern]
- The umbrella `fluent` crate re-exports `fluent_bundle::*` and adds a `fluent_args!` macro that builds a `FluentArgs` (name to value map filled with `set`). [CODE S-un2vqcl3: fluent/src/lib.rs#fluent_args]
- A bundle wraps interpolated values in Unicode first-strong and pop directional isolates (U+2068, U+2069) by default; `set_use_isolating(false)` turns this off, which the doc suggests for testing. [CODE S-vktfavae: fluent-bundle/src/bundle.rs#FluentBundle::set_use_isolating]
- `fluent_bundle::concurrent::FluentBundle` is the same struct over a Mutex-based memoizer, built with `FluentBundle::new_concurrent(locales)`; the default `FluentBundle::new` uses a RefCell-based memoizer. [CODE S-6dmythvr: fluent-bundle/src/concurrent.rs#FluentBundle::new_concurrent]
- docs.rs shows the default `IntlLangMemoizer` as neither `Send` nor `Sync` and the `concurrent::IntlLangMemoizer` as both, and `FluentBundle<R, M>` implements `Send` and `Sync` only when its resource vector and its memoizer `M` do. [DOC S-adkxxbxo, S-sui7jilt, S-xxelwvq6]
- `fluent_syntax::parser::parse` keeps comments and `parse_runtime` strips them; both are lenient, return the AST plus a vector of `ParserError` (position, slice, error kind), and put unparsed input into `ast::Entry::Junk`. [CODE S-fi73q2gh: fluent-syntax/src/parser/mod.rs#parse_runtime]

### @fluent/bundle and the JavaScript packages
- The npm registry lists `@fluent/bundle` 0.19.1 (published 2025-04-02) under Apache-2.0, with `types` `./esm/index.d.ts`, `main` `./index.js`, `module` `./esm/index.js`, Node `>=18.0.0` and no `exports` field. [DOC S-yf4y3ooe]
- The changelog states the TypeScript sources compile to ES2018 files in `esm/` that are bundled into one UMD `index.js` (0.16.0), that `esm/` carries `"type": "module"` (0.17.0) and that 0.19.0 added Temporal support and required Node 18. [DOC S-zqefeiow]
- Fluent Syntax 1.0 was released in April 2019, and `@fluent/bundle` (then `fluent`) 0.13.0 announced support for it. [DOC S-c7rozbcf, S-zqefeiow]
- The README requires `Intl.DateTimeFormat`, `Intl.NumberFormat` and `Intl.PluralRules` from the host, and notes that syntax errors are per message and do not break the whole resource. [DOC S-yxzyna3l]
- `new FluentBundle(locales, {functions, useIsolating = true, transform})` registers `NUMBER` and `DATETIME`; `formatPattern(pattern, args, errors)` appends problems to `errors` and still returns a string, and throws the first error when `errors` is omitted. [CODE S-lj3rgbhb: fluent-bundle/src/bundle.ts#FluentBundle.formatPattern]
- `addResource(res, {allowOverrides = false})` returns an array of `Error` (duplicate ids are skipped with an error), ids starting with `-` are private terms that `getMessage` cannot return, and ids and argument names are plain `string` keys: `getMessage(id: string): Message | undefined`, args `Record<string, FluentVariable> | null`. [CODE S-lj3rgbhb: fluent-bundle/src/bundle.ts#FluentBundle.addResource]
- The runtime `FluentResource` constructor reports no syntax errors: it skips to the next message start, may accept a few messages the reference parser rejects, and its comment advises validating translations with the `fluent-syntax` parser before runtime. [CODE S-ngxalogc: fluent-bundle/src/resource.ts#FluentResource]
- `@fluent/langneg` 0.7.0 and `@fluent/syntax` 0.19.0 (both published 2023-03-13) are Apache-2.0 packages with bundled `.d.ts` types and the same `main`/`module` layout. [DOC S-qucwxqjo, S-v5hog4zh]
- `negotiateLanguages(requested, available, {defaultLocale, strategy})` offers the strategies filtering (default), matching and lookup. [DOC S-u5ks3e5h]
- `@fluent/syntax` represents invalid entries as `Junk` nodes with a content string and a list of annotations (code, arguments, message). [CODE S-fnbm2hx6: fluent-syntax/src/ast.ts#Junk]
- Polish needs more plural variants than English: the Fluent site shows a Polish translation that adds `[few]` and `[many]` to the `[one]` and `[other]` of the English one. [DOC S-c7rozbcf]

### Typed accessors
- No Fluent project repository or package generates typed accessors or key types from FTL: the projectfluent organisation lists 16 repositories (implementations, spec, playground, editor grammars, a dashboard), the fluent.js README lists seven packages and the fluent-rs README the crates above, and none is a generator. [DER S-edmvqoen, S-zsnubksc, S-ey42zwsk: absence from the three lists]
- `fluent-typed` 0.9.0 (MIT, crates.io 2026-08-14, minimum Rust 1.88, pre-1.0 with breaking minor releases) generates one typed Rust function per message from a `build.rs` call; it infers argument types from comments, `NUMBER()` calls and plural selectors, warns about unused messages, generates an accessor only for messages present in every locale, and has lint levels `Off`, `Warn`, `Deny`, `Strict`. [COMMUNITY S-jm4q5smn, S-ccvjl7yh]
- `i18n-embed-fl` 0.10.1 (MIT) provides the `fl!` macro that checks a message id and its named arguments at compile time against the fallback language's FTL file, on top of the `i18n-embed` loader; `fluent-templates` 0.15.1 (MIT/Apache-2.0, repository under XAMPPRocky) is described as templating for Fluent. [COMMUNITY S-5bmxcoy4, S-mobvrkio]
- For JavaScript, `fluent-ts` (MIT, last release 1.0.4 on 2020-08-17) generates `.d.ts` typings from `.ftl` files, and `fluent-transpiler` 0.8.0 (MIT, 2026-08-27) turns FTL into ES modules with an error-on-`Junk` option that defaults to on. [COMMUNITY S-nqeg3xk3, S-wxarrmdh]

### Linting
- Mozilla's `moz-fluent-linter` 0.4.10 (Mozilla l10n team, not a projectfluent repository; MPL-2.0; Python `>=3.7`, requires `fluent.syntax ~= 0.19.0`) checks reference `.ftl` files for short or invalid identifiers and wrong characters, can disable syntax features, and is wired as a pre-commit hook; it is based on the linter in mozilla-central. [DOC S-ejm4457f, S-tj5gqic5]
- Its rule ids are ID01 and ID02 (identifier form and minimum length), CO01 and CO02 (brand names, prohibited words), TE01 to TE05 (typography), SY01 to SY06 (disabled syntax features), GC and RC (group and resource comments), VC (variable comments) and PS01 (placeable spacing); the shipped config lists ID01, ID02 and CO01 as disabled. [CODE S-wo2rtyeb: src/fluent_linter/config.yml#ID01]
- The linter reports a `JUNK` finding for a syntax error, an `MI02` finding for a missing final empty line, reads `.ftl` files under the given directories, and exits with 1 when any finding exists. [CODE S-2viytftj: src/fluent_linter/linter.py#lint]
- ESLint's `no-restricted-syntax` rule disallows user-defined syntax given as ESTree node types or AST selectors with an optional custom message, and works with any language ESLint lints, including TypeScript through typescript-eslint. [DOC S-5qwcsz2g]
- `eslint-plugin-i18next` 6.1.5 has a `no-literal-string` rule that aims to stop literal strings from being shown to users without translation; its repository LICENSE file is MIT while its `package.json` says ISC. [COMMUNITY S-l53lrqoz, S-nmwvmitf]
- Whether an ESLint or Clippy rule can find hard-coded user-visible strings: no official page read here states it for ESLint core rules or for Clippy lints. [UNK]
- Which Fluent Syntax version the fluent-rs crates implement: no README, changelog or crate doc read here states it. [UNK]

### How it fits (self-hosted corpus service, Python shell over a Rust core)
- The Rust core can fail closed on a bad catalogue: `FluentResource::try_new` returns the error list with the resource, so startup can reject any resource with a `ParserError`, whereas the JavaScript runtime parser drops bad messages silently and needs a separate `@fluent/syntax` pass. [DER S-v5arxcqi, S-ngxalogc: try_new returns errors; the JS constructor reports none]
- One FTL file can serve both layers: `fluent.runtime` in the Python shell and `fluent-bundle` in the Rust core read the same syntax (Fluent Syntax 1.0 for the Python runtime and the JS packages; the Rust version statement is `UNK`). [DER S1709, S-c7rozbcf, S-vktfavae: Python runtime supports spec 1.0; the site names Rust among the implementations]
- Polish and English need one bundle per locale, with `pl` first for plural rules, because the first locale selects the plural rules and Polish needs `[few]` and `[many]` variants. [DER S-vktfavae, S-c7rozbcf: first locale drives plural rules; Polish variants shown on the site]
- A multi-threaded Rust core needs either `concurrent::FluentBundle` or one default bundle per thread, because the default memoizer is neither `Send` nor `Sync`. [DER S-adkxxbxo, S-sui7jilt, S-xxelwvq6: auto-trait impls of the memoizers and of `FluentBundle<R, M>`]
- Formatted strings carry U+2068 and U+2069 around every placeable unless isolation is turned off, so text destined for logs, JSON or CSV output needs `set_use_isolating(false)` (Rust) or `useIsolating: false` (JS). [DER S-vktfavae, S-lj3rgbhb: isolation is on by default in both libraries]
- Offline and CPU-only operation needs nothing beyond the crate set: `fluent-bundle` depends on `fluent-syntax`, `fluent-langneg`, `intl_pluralrules`, `unic-langid`, `intl-memoizer`, `rustc-hash`, `self_cell` and `smallvec`, with no network or model crate in that list. [DER S-fte52rkq: the dependency list]
- Because no official generator exists, message ids stay runtime strings in both libraries (`get_message(&str)`, `getMessage(id: string)`), so a missing or renamed key shows up as `None` or `undefined` at runtime; a project-side check that compares the ids found in the FTL AST with the ids used in code, or a community generator under MIT, is what closes the gap. [DER S-edmvqoen, S-vktfavae, S-lj3rgbhb: no official generator; id parameters are plain strings]

## Reference
- Rust sources (tags): https://github.com/projectfluent/fluent-rs at `fluent-bundle@0.16.0`, `fluent@0.17.0`, `fluent-syntax@0.12.0`; docs.rs: https://docs.rs/fluent-bundle/0.16.0/fluent_bundle/; language negotiation: https://github.com/projectfluent/fluent-langneg-rs (commit 945d2d8).
- JavaScript sources (tags): https://github.com/projectfluent/fluent.js at `@fluent/bundle@0.19.1`, `@fluent/syntax@0.19.0`, `@fluent/langneg@0.7.0`; API reference: https://projectfluent.org/fluent.js/bundle.
- Linter: https://github.com/mozilla-l10n/moz-fluent-linter (commit d8341d5, version 0.4.10; PyPI `moz-fluent-linter`); command `moz-fluent-lint --config linter_config.yml l10n/en/`.
- Rust signatures at fluent-bundle 0.16.0: `FluentResource::try_new(String) -> Result<FluentResource, (FluentResource, Vec<ParserError>)>`; `FluentBundle::new(Vec<LanguageIdentifier>)`; `add_resource(R) -> Result<(), Vec<FluentError>>`; `get_message(&str) -> Option<FluentMessage>`; `format_pattern(&Pattern, Option<&FluentArgs>, &mut Vec<FluentError>) -> Cow<str>`; `FluentError` variants `Overriding`, `ParserError`, `ResolverError`. The fluent-bundle README example at that tag reads `msg.value` as a field, while the code defines `FluentMessage::value()` as a method, so that README snippet does not compile against 0.16.0.
- Python runtime and FTL syntax: [texts-catalogue-formats.md](texts-catalogue-formats.md).

## Examples
- SNIPPET: format one message with an argument in the Rust core and collect resolver errors; context: fluent-bundle 0.16.0 plus `unic-langid` 0.9 with the `macros` feature for `langid!`; checked: no [DER S-vktfavae, S-fte52rkq: bundle.rs doc example; the macros feature appears in the bundle's dev-dependencies]
```rust
use fluent_bundle::{FluentArgs, FluentBundle, FluentResource};
use unic_langid::langid;

let source = "intro = Welcome, { $name }.".to_string();
let resource = match FluentResource::try_new(source) {
    Ok(resource) => resource,
    Err((_partial, errors)) => panic!("FTL syntax errors: {errors:?}"),
};
let mut bundle = FluentBundle::new(vec![langid!("en-US")]);
bundle.set_use_isolating(false);
bundle.add_resource(resource).expect("duplicate message ids");

let message = bundle.get_message("intro").expect("no such message");
let pattern = message.value().expect("message has no value");
let mut args = FluentArgs::new();
args.set("name", "jan.kowalski");
let mut errors = vec![];
let text = bundle.format_pattern(&pattern, Some(&args), &mut errors);
assert!(errors.is_empty());
assert_eq!(text, "Welcome, jan.kowalski.");
```
- SNIPPET: the same message in TypeScript with an errors array; context: @fluent/bundle 0.19.1, ESM import; checked: no [DER S-yxzyna3l, S-lj3rgbhb: README usage with the `useIsolating` option from bundle.ts]
```typescript
import { FluentBundle, FluentResource } from "@fluent/bundle";

const bundle = new FluentBundle("en-US", { useIsolating: false });
const problems = bundle.addResource(new FluentResource("intro = Welcome, { $name }."));
const message = bundle.getMessage("intro");
const errors: Error[] = [];
if (message?.value) {
  const text = bundle.formatPattern(message.value, { name: "jan.kowalski" }, errors);
}
```
