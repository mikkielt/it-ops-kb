---
topic: agents/typescript-tsconfig-and-compiler-options
priority: P3
applies_to: "TypeScript 5.x, 6.0 (2026-03-23) and 7.0 (2026-07-08, native compiler): tsconfig.json structure (files, include, exclude, extends), compilerOptions defaults and how 6.0 changed them, the strict family, deprecations, the tsc command line; website reference pages pinned at TypeScript-Website commit 6556b08"
retrieved_utc: 2026-10-15
sources: [S-jdmnhjds, S-eumnm3tn, S-4bj5u3yk, S-ff6may7t, S-3e3kl7vi, S-34pqpd75, S-7nvzlf7l, S-iudxgieq, S-f2d7bode, S-huriuyvo, S-4gncoeuv, S-pgt5grct, S-el5lfrsb, S-2yfpg4cd, S-iyxaeenu, S-2oseqdau, S-fdzam7lv, S-5egapxtq, S-sp2a6svk, S-eq3gt72a, S-lq5mn2bc, S-sipjyeoi, S-j645b5a2, S-4xfmso3u, S-jfnkownz, S-yuhdbie6, S-ybwhbhxi, S-vdfo2blu, S-cblfylm6, S-gssvmwmg]
status: complete
---

# TypeScript: tsconfig.json, compiler options, the strict family and the tsc command line

## Summary
A `tsconfig.json` has three file-selection properties (`files`, `include`, `exclude`), an `extends` chain and `compilerOptions`; which files are in the program is decided by those properties plus whatever the program imports, not by `exclude` alone. The meaning of an option that is not written depends on the compiler version: TypeScript 6.0 changed the defaults of `strict`, `module`, `target`, `rootDir`, `types` and others, and 7.0 (the native compiler) adopted them, while the website's tsconfig reference page still prints the older defaults. `strict` is an umbrella for eight checks (nine counting `alwaysStrict`), and two popular extra checks (`exactOptionalPropertyTypes`, `noUncheckedIndexedAccess`) are not in it. For a mapper or an agent the safe route is `tsc --version` then `tsc --showConfig` (see [codebase-mapping.md](codebase-mapping.md)), never a reading of defaults from a table without the version.

## Facts

### File selection: files, include, exclude, extends
- `files` is an allowlist of files for the program; it takes no glob patterns, and an error occurs when a listed file cannot be found. [DOC S-jdmnhjds]
- `include` patterns are resolved relative to the directory that holds the `tsconfig.json`; `*` and `?` match within one path segment, `**/` matches directories to any depth. A last segment with no extension and no wildcard is treated as a directory, and the files with supported extensions inside it are taken (`.ts`, `.tsx`, `.d.ts`, plus `.js` and `.jsx` with `allowJs`). [DOC S-eumnm3tn]
- The default of `include` is `[]` when `files` is specified and `**/*` otherwise; the default of `exclude` is `node_modules`, `bower_components`, `jspm_packages` and the `outDir`. [DOC S-lq5mn2bc]
- `exclude` only filters what `include` finds. A file it names can still enter the program through an `import`, a `types` entry, a `/// <reference` directive or the `files` list, so it is not a way to keep a file out of a build. [DOC S-4bj5u3yk]
- In `extends`, the base file loads first and the inheriting file overrides it; `files`, `include` and `exclude` of the inheriting file overwrite (do not merge with) the base's, a circular chain is not allowed, and the path may use Node.js-style resolution. [DOC S-ff6may7t]
- The handbook's tsconfig page says `tsc` without input files looks for `tsconfig.json` in the current directory and then each parent directory, and that a `tsconfig.json` is ignored when input files are named on the command line. [DOC S-3e3kl7vi]

### The strict family
- `strict` switches on the whole "strict mode family" of checks, and each member can be turned off individually afterwards. Future releases may add further checks under `strict`, so an upgrade can bring new type errors with no change to the config. [DOC S-7nvzlf7l]
- The members the website's reference script relates to `strict` are `alwaysStrict`, `strictNullChecks`, `strictBindCallApply`, `strictBuiltinIteratorReturn`, `strictFunctionTypes`, `strictPropertyInitialization`, `noImplicitAny`, `noImplicitThis` and `useUnknownInCatchVariables`; each one's documented default is "true if `strict`, false otherwise". [CODE S-34pqpd75: packages/tsconfig-reference/scripts/tsconfigRules.ts#relatedTo, defaultsForOptions]
- In the 7.0.2 native compiler eight options carry the strict flag (`noImplicitAny`, `strictNullChecks`, `strictFunctionTypes`, `strictBindCallApply`, `strictPropertyInitialization`, `strictBuiltinIteratorReturn`, `noImplicitThis`, `useUnknownInCatchVariables`), each described as "true unless strict is false"; `alwaysStrict` is declared separately with default `true`. [CODE S-sipjyeoi: internal/tsoptions/declscompiler.go#OptionsDeclarations]
- `noImplicitAny` makes the compiler report an error wherever it would have inferred `any` for lack of an annotation. [DOC S-iudxgieq]
- With `strictNullChecks` false, `null` and `undefined` are effectively ignored by the language; with it true they are distinct types and using them where a concrete value is expected is a type error. [DOC S-f2d7bode]
- `strictFunctionTypes` makes assignment of functions check parameters and return values for subtype compatibility, so an unsafe assignment such as a `(x: string) => void` to a `(ns: string | number) => void` is rejected. [DOC S-huriuyvo]
- `strictBindCallApply` checks that `bind`, `call` and `apply` are invoked with arguments that match the underlying function; without it they accept anything and return `any`. [DOC S-4gncoeuv]
- `strictPropertyInitialization` reports a class property that is declared but not set in the constructor. [DOC S-pgt5grct]
- `noImplicitThis` reports `this` expressions whose type is implicitly `any`. [DOC S-el5lfrsb]
- `useUnknownInCatchVariables` types a `catch` clause variable as `unknown` instead of `any` (available since TypeScript 4.0), so it must be narrowed before use. [DOC S-2yfpg4cd]
- `alwaysStrict` makes files parse in ECMAScript strict mode and emits `"use strict"` for each source file. [DOC S-iyxaeenu]
- `strictBuiltinIteratorReturn` instantiates built-in iterators with a `TReturn` of `undefined` instead of `any`. [DOC S-2oseqdau]
- `exactOptionalPropertyTypes` makes an optional property mean "absent or the declared type", so an explicit `undefined` is no longer accepted unless the type includes it. [DOC S-fdzam7lv]
- `noUncheckedIndexedAccess` adds `undefined` to a type read through an index signature or an index. [DOC S-5egapxtq]
- The website's reference script lists `exactOptionalPropertyTypes` in its "recommended" set apart from the strict-flag options. [CODE S-34pqpd75: packages/tsconfig-reference/scripts/tsconfigRules.ts#recommended]
- Neither of those two options is among the eight strict-flag options of the 7.0.2 compiler, so `"strict": true` does not turn them on. [DER S-sipjyeoi, S-34pqpd75: not in the strict-flag set]

### Defaults that TypeScript 6.0 changed (and 7.0 keeps)
- `strict` is true by default in 6.0; a project that relied on the old default of false must write `"strict": false`. [DOC S-sp2a6svk]
- `module` defaults to `esnext`, and `target` defaults to the most recent supported ECMAScript version, a floating target that was `es2025` at the 6.0 release. [DOC S-sp2a6svk]
- `target` decides which JavaScript features are downleveled and which are left intact (an arrow function `() => this` becomes an equivalent `function` expression at ES5 or lower) and changes the default of `lib`. The special `ESNext` value is the highest version the installed TypeScript supports, so it does not mean the same thing between TypeScript versions and makes upgrades less predictable. [DOC S-gssvmwmg]
- `noUncheckedSideEffectImports` is true by default and `libReplacement` is false by default. [DOC S-sp2a6svk]
- `rootDir` defaults to the directory that holds the `tsconfig.json`; it is only inferred when `tsc` runs from the command line with no `tsconfig.json`. A project whose sources sit in `src/` and that relied on the inferred common root must now set `"rootDir": "./src"`, or its output moves to `dist/src/`. [DOC S-sp2a6svk]
- `types` defaults to `[]`: `node_modules/@types` packages are no longer all pulled into the global scope, and a project that needs `process`, `describe` and the like must list `"types": ["node"]` or similar. `["*"]` restores the 5.9 behaviour. [DOC S-sp2a6svk]
- When `types` is specified, only the listed packages from `node_modules/@types` (that folder of any enclosing directory) enter the global scope: the others add no globals such as `process` or `expect` and no auto-import suggestions, but a module an `import` reaches stays fully typed. `typeRoots` is the option that selects folders rather than exact packages. [DOC S-cblfylm6]
- 7.0 states that it adopts the 6.0 defaults and gives hard errors for the flags and constructs 6.0 deprecated; `target` defaults to the current stable ECMAScript version just before `esnext`, and `stableTypeOrdering` is true and cannot be turned off. [DOC S-eq3gt72a]
- The website's live tsconfig reference still prints pre-6.0 defaults: `module` is "CommonJS if target is ES5; ES6/ES2015 otherwise" and `target` is "ES5 otherwise". The 6.0 and 7.0 announcements and the 7.0.2 source disagree with it. [DOC S-lq5mn2bc]
- In the 7.0.2 source `strict`, `alwaysStrict` and `allowSyntheticDefaultImports` are declared with default `true`, `composite` with `false`, and `moduleResolution` with "nodenext if module is nodenext, node16 if module is node16 or node18, otherwise bundler". [CODE S-sipjyeoi: internal/tsoptions/declscompiler.go#OptionsDeclarations]
- The pinned reference data still says `allowSyntheticDefaultImports` and `esModuleInterop` depend on `module` and `moduleResolution`; 6.0 no longer lets either be set to false. [DER S-34pqpd75, S-sp2a6svk: conditional default in the pinned data, fixed in 6.0]

### Deprecations in 6.0 and removals in 7.0
- Deprecated in 6.0: `target: es5` (the lowest target becomes ES2015), `downlevelIteration`, `moduleResolution: node` / `node10`, the `amd`, `umd`, `systemjs` and `none` values of `module`, `baseUrl`, `moduleResolution: classic`, `esModuleInterop: false`, `allowSyntheticDefaultImports: false`, `alwaysStrict: false`, `outFile` (the post's own text says it "has been removed"), the `module` keyword for namespaces, the `asserts` keyword on imports and `no-default-lib` directives. [DOC S-sp2a6svk]
- In 6.0 these can be silenced with `"ignoreDeprecations": "6.0"`, and 7.0 will not support any of them. [DOC S-sp2a6svk]
- 7.0 lists the deprecated options as hard errors with no-op behaviour; "baseUrl is no longer supported, and paths can be updated to be relative to the project root". [DOC S-eq3gt72a]

### Output location and emit switches
- `outDir` sends `.js`, `.d.ts` and `.js.map` files to that directory and preserves the source directory structure; without it, emitted files sit next to their sources. [DOC S-jfnkownz]
- `rootDir` defaults (pinned reference) to the longest common path of the non-declaration inputs, or to the `tsconfig.json` directory with `composite`. It does not affect which files are in the compilation, and it is an error when a file to emit lies outside it. [DOC S-yuhdbie6]
- `noEmit` writes no JavaScript, source maps or declarations, so another tool (Babel, swc) can do the transform while TypeScript only type-checks. [DOC S-4xfmso3u]
- `noEmitOnError` defaults to false, so output is written even when type errors are reported. [DOC S-vdfo2blu]
- `skipLibCheck` skips type checking of all declaration files, which saves time at the price of type-system accuracy (for example when two copies of a library's types disagree). [DOC S-ybwhbhxi]

### The tsc command line
- `tsc` compiles the closest project found through a backward look for `tsconfig.json`; `--project` takes a configuration file or a folder; `--init` creates a `tsconfig.json`; `--showConfig` prints the final configuration instead of building; `--listFilesOnly` prints the files of the compilation and stops; `--version` prints the compiler version. [DOC S-j645b5a2]
- The same page documents `--ignoreConfig` ("Ignore the tsconfig found and build with commandline options and files"), while its introduction still says a `tsconfig.json` is ignored when input files are specified. [DOC S-j645b5a2]
- Since 6.0, `tsc foo.ts` in a directory that contains a `tsconfig.json` is an error (TS5112) that names `--ignoreConfig` as the way to skip the file; before 6.0 the config was silently ignored. [DOC S-sp2a6svk]
- 7.0 keeps it: a command-line build cannot take file paths when the current directory holds a `tsconfig.json`, unless `--ignoreConfig` is passed. [DOC S-eq3gt72a]
- `--build`, `--clean`, `--dry`, `--force`, `--verbose` and `--watch` belong to build mode, described in [typescript-projects-declarations-incremental.md](typescript-projects-declarations-incremental.md). [DOC S-j645b5a2]

### How it fits
- A mapper that wants the effective options of a TypeScript project reads `tsc --version` first and then `tsc --showConfig` with no file arguments: an option that is absent from the config means a different value under 5.x, 6.x and 7.x, so a table of defaults without the version is wrong for one of them. [DER S-sp2a6svk, S-lq5mn2bc, S-j645b5a2: defaults moved in 6.0, `--showConfig` prints the final configuration]
- A build that passed under 5.x with no `types` and no `rootDir` can fail or move its output under 6.x or 7.x; the first things to check are `types`, `rootDir`, `strict` and the deprecated options above. [DER S-sp2a6svk: defaults changed and deprecations]

## Reference
- Config discovery, `--showConfig` and `extends` inside a repository survey: [codebase-mapping.md](codebase-mapping.md).
- Module and resolution options: [typescript-module-resolution.md](typescript-module-resolution.md).
- Project references, incremental builds and declaration output: [typescript-projects-declarations-incremental.md](typescript-projects-declarations-incremental.md).
- The native compiler: [typescript-native-compiler.md](typescript-native-compiler.md).
- Sources: https://www.typescriptlang.org/tsconfig , https://devblogs.microsoft.com/typescript/announcing-typescript-6-0/ , https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/ .

## Examples
- SNIPPET: a tsconfig that keeps a 5.x project's layout under 6.0 and later (explicit `types` and `rootDir`, `strict` left at its default); context: TypeScript 6.0 or 7.0, sources under `src/`, Node.js project; checked: syntax [DER S-sp2a6svk: the two migration edits the announcement names]

```json
{
  "compilerOptions": {
    "rootDir": "./src",
    "outDir": "./dist",
    "types": ["node"]
  },
  "include": ["./src"]
}
```
