---
topic: agents/typescript-native-compiler
priority: P3
applies_to: "TypeScript 6.0 (JavaScript-based, last of that line) against TypeScript 7.0 (native compiler written in Go, microsoft/typescript-go, npm typescript 7.0.2): compatibility, new flags, intentional differences, feature status and what is not ready"
retrieved_utc: 2026-10-15
sources: [S-eq3gt72a, S-sp2a6svk, S-mtnr5emw, S-e6jwgvmc, S-sipjyeoi, S-7elpuzi2]
status: partial
---

# TypeScript 7.0 native compiler against the JavaScript-based compiler

## Summary
TypeScript 6.0 is the last release of the JavaScript-based compiler and a bridge: it deprecates what 7.0 drops and changes the defaults 7.0 adopts. TypeScript 7.0 (announced 2026-07-08) is a port to Go, developed in the microsoft/typescript-go repository, with the same type checking and command-line behaviour as 6.0 and the same `tsc` command. What differs is speed and parallelism flags, a rebuilt `--watch`, a reworked treatment of JavaScript files and JSDoc, and what is missing: there is no stable programmatic API yet, and editor integrations for embedded languages stay on 6.0. The repository README at tag `typescript/v7.0.2` is behind the announcement on at least one point (watch mode).

## Facts

### Relationship to 6.0
- TypeScript 6.0 is called a transition release for 7.0: it stays API compatible with 5.9, deprecates options (silenced with `"ignoreDeprecations": "6.0"`), and 7.0 will not support those options. [DOC S-sp2a6svk]
- 7.0 is built to match 6.0's type-checking and command-line behaviour: code that compiles cleanly under 6.0 with `stableTypeOrdering` on and no `ignoreDeprecations` should compile identically under 7.0. [DOC S-eq3gt72a]
- 7.0 adopts the 6.0 defaults (`strict` true, `module` esnext, `rootDir` the config directory, `types` `[]`, and so on) and turns every flag and construct that 6.0 deprecated into a hard error; the list is in [typescript-tsconfig-and-compiler-options.md](typescript-tsconfig-and-compiler-options.md). [DOC S-eq3gt72a]
- The command is `tsc`: the preview was `tsgo` from the npm package `@typescript/native-preview`, and "for TypeScript 7.0 RC and later, the command name is `tsc`". [DOC S-mtnr5emw]
- Long term the repository's contents are expected to be merged into `microsoft/TypeScript`, after which the typescript-go repository and its issue tracker will be closed. [DOC S-mtnr5emw]

### New and changed command-line behaviour
- `--checkers` sets the number of type-checking workers (default 4; `--checkers 1` is effectively single-threaded and removes duplicate work), `--builders` sets the number of parallel project-reference builders under `--build`, and `--singleThreaded` turns parallelism off. The announcement calls `--checkers` and `--builders` experimental. [DOC S-eq3gt72a]
- The 7.0.2 source declares `checkers` with the default "4 unless singleThreaded is passed" and a minimum of 1, plus `singleThreaded`, `quiet` and `pprofDir` among its command-line-only options. [CODE S-sipjyeoi: internal/tsoptions/declscompiler.go#OptionsDeclarations]
- The build-mode options of the 7.0.2 source add `builders` (the number of projects to build concurrently, default "4 unless singleThreaded is passed", minimum 1) and `stopBuildOnErrors` (skip downstream projects after an error in an upstream project, default false) to `verbose`, `dry`, `force` and `clean`. [CODE S-7elpuzi2: internal/tsoptions/declsbuild.go#OptionsForBuild]
- Whether the 7.0 announcement or any handbook page documents `stopBuildOnErrors` was not found: the announcement text read on 2026-10-15 names `--checkers`, `--builders` and `--singleThreaded` only, and the website reference pages at commit 6556b08 predate it. [UNK]
- Varying `--checkers` may in rare cases produce order-dependent results, so the announcement suggests fixing one number across build environments. [DOC S-eq3gt72a]
- `--builders` and `--checkers` multiply: `--checkers 4 --builders 4` allows up to 16 type-checkers at once. Varying builders should not change results. [DOC S-eq3gt72a]
- `--watch` is rebuilt on a new file-watching foundation based on the Parcel bundler's watcher. [DOC S-eq3gt72a]
- `tsc` with file arguments in a directory that contains a `tsconfig.json` is an error and needs `--ignoreConfig`, the 6.0 behaviour; the 7.0.2 flow is described with the other mapping facts in [codebase-mapping.md](codebase-mapping.md). [DOC S-eq3gt72a]

### Feature status (repository README, tag typescript/v7.0.2)
- Marked done: program creation (same files and module resolution as 6.0, "not all resolution modes supported yet"), parsing and scanning, command-line and `tsconfig.json` parsing (error messages may be less helpful), type resolution, type checking (same errors and locations as 6.0; type printback in errors may display differently), JSX, declaration emit, JavaScript emit, build mode with project references, and incremental build. [DOC S-mtnr5emw]
- Marked "prototype": watch mode ("watches files and rebuilds, but no incremental rechecking"); "in progress": the language service (LSP); "not ready": the API. [DOC S-mtnr5emw]
- The announcement, dated later than the README table's "prototype" row, describes 7.0 as shipping a "completely rebuilt `--watch` mode" with resource improvements on all platforms. [DOC S-eq3gt72a]
- 7.0 does not yet expose a stable programmatic API; tools that embed TypeScript in their own compilers and language services, such as Volar, can currently rely only on 6.0. [DOC S-eq3gt72a]
- Vue, MDX, Astro, Svelte and similar embedded-language workflows are not yet able to use 7.0 for editor support and stay on 6.0; Angular projects can use 7.0 at the command line with 6.0 for the editor. [DOC S-eq3gt72a]
- The language server is LSP-based and multi-threaded; in VS Code a dedicated extension makes it the default, with "Disable TypeScript 7 Language Server" to go back to 6.0. [DOC S-eq3gt72a]
- 7.1 is announced as next, with new versions every three to four months. [DOC S-eq3gt72a]

### Intentional differences from 6.0
- JavaScript support was reworked to follow TypeScript's own rules: values are not accepted where types are expected (write `typeof value`), `@enum` and `@class` are no longer special, a standalone `?` type is not usable (use `any`), postfix `!` is not supported, and Closure-style `function(string): void` types are gone. [DOC S-eq3gt72a]
- Constructor functions with prototype assignment are no longer treated as classes in JavaScript files; the substitute is a `class` declaration. Nested undeclared expandos, `this` aliases and single-property `require` access are other removed patterns. [DOC S-e6jwgvmc]
- Declaration emit from `.js` input was rewritten and differs from 6.0 on purpose; the project says it is a non-goal to match the old output exactly, and that `.d.ts` emit in the presence of errors is not well defined. [DOC S-e6jwgvmc]
- Template literal type inference through an empty placeholder takes a full Unicode code point, so an emoji is no longer split into surrogate halves. [DOC S-e6jwgvmc]
- Scanner node positions use UTF-8 offsets from the start of the file instead of UTF-16 offsets, so positions in files with non-ASCII characters are greater than before. [DOC S-e6jwgvmc]
- With `"strict": false`, the native compiler no longer allows omitting arguments for parameters typed `undefined`, `unknown` or `any`; `void` parameters may still be omitted. [DOC S-e6jwgvmc]

### How it fits
- An agent that reads or runs a TypeScript project decides on the major version first (`tsc --version`): for 7.x the CLI flags of this article apply and no `typescript` module API can be loaded for custom analysis; for 6.x the module API exists but deprecated options need `ignoreDeprecations`. [DER S-eq3gt72a, S-sp2a6svk: no stable API in 7.0; deprecations in 6.0]
- Mapping with `tsc --showConfig`, `--listFilesOnly` and `--explainFiles` works the same under 6.x and 7.x because 7.0 keeps 6.0's command-line behaviour. [DER S-eq3gt72a, S-sipjyeoi: same command-line behaviour; the flags are declared in 7.0.2]

## Reference
- Options, defaults and deprecations: [typescript-tsconfig-and-compiler-options.md](typescript-tsconfig-and-compiler-options.md).
- Build mode and declaration output: [typescript-projects-declarations-incremental.md](typescript-projects-declarations-incremental.md).
- Config discovery and `--showConfig` in a repository survey: [codebase-mapping.md](codebase-mapping.md).
- Sources: https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/ , https://github.com/microsoft/typescript-go .

## Examples
- None: the native compiler is called as `tsc` with the same arguments as before; the new flags are listed above.
