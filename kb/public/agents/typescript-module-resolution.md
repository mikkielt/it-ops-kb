---
topic: agents/typescript-module-resolution
priority: P3
applies_to: "TypeScript 5.x to 7.0: the module and moduleResolution options (node16, node18, node20, nodenext, preserve, esnext, bundler, node10, classic), module format detection, paths and baseUrl, package.json exports, verbatimModuleSyntax and isolatedModules; handbook pages pinned at TypeScript-Website commit 6556b08"
retrieved_utc: 2026-10-15
sources: [S-e5r3w2iq, S-ipmh5e4a, S-eofsccvy, S-sc6whm2s, S-xkdynti4, S-lq5mn2bc, S-sp2a6svk, S-eq3gt72a, S-sipjyeoi]
status: complete
---

# TypeScript module output and module resolution

## Summary
Two options decide how an import is understood: `module` says which module format the compiler would emit (and, for the Node modes, how each file's format is detected), and `moduleResolution` says how a module specifier is turned into a file. They are used as a pair: `nodenext` and `bundler` are the two modes the TypeScript team recommends in 2026, `node10` and `classic` are deprecated in 6.0 and unsupported in 7.0. The difference between the modes is mostly four things: whether package.json `exports` is honoured, whether relative imports need a file extension, whether a directory resolves to its `index` file, and which condition names (`import`, `require`) are matched.

## Facts

### module: the output format
- `module` sets the module system of the program. The reference recommends `nodenext` for modern Node.js projects and `preserve` or `esnext` for code that will be bundled. [DOC S-e5r3w2iq]
- Changing `module` affects `moduleResolution`, because TypeScript's type checking and resolution follow the module format it would emit, even when `noEmit` is set. [DOC S-e5r3w2iq]
- `node16`, `node18`, `node20` and `nodenext` integrate with Node's native ES module support; the emitted JavaScript is CommonJS or ES2020 depending on the file extension and the `type` field of the nearest `package.json`. [DOC S-e5r3w2iq]
- `node16` is available from TypeScript 4.7, `node18` from 5.8 (adds import attributes), `node20` adds `require(esm)`, and `nodenext` follows the latest stable Node.js and implies the floating `--target esnext`. [DOC S-e5r3w2iq]
- These modes are the only `module` values that emit both CommonJS and ESM files in one compilation, based on each file's detected format; every other value forces a single format. The page calls them "the only correct `module` options" for code intended to run on Node.js 12 or later, whether or not it uses ES modules. [DOC S-eofsccvy]
- Format detection: `.mts`, `.mjs` and `.d.mts` are always ES modules; `.cts`, `.cjs` and `.d.cts` are always CommonJS; `.ts`, `.tsx`, `.js`, `.jsx` and `.d.ts` are ES modules only when the nearest ancestor `package.json` has `"type": "module"`, else CommonJS. A project of `.ts` files therefore emits CommonJS under `nodenext` until `"type": "module"` is added. [DOC S-eofsccvy]
- Interop: an ES module can default-import a CommonJS module's `module.exports`; whether named imports work depends on Node's static analysis, which TypeScript cannot see from a declaration file and optimistically assumes succeeds. In `node16` and `node18` a `require` cannot reference an ES module; `nodenext` allows it (reflecting Node.js 22.12.0 and later) and does not detect a top-level `await` in the target. [DOC S-eofsccvy]
- Differences among the three Node modes: `node16` implies `target es2022`, `moduleResolution node16`, no import attributes and no `require(esm)`; `node18` adds import attributes and requires `type "json"` for JSON imports; `nodenext` implies `target esnext`, `moduleResolution nodenext` and allows `require(esm)`. All three imply `esModuleInterop`. [DOC S-eofsccvy]
- `preserve` (since 5.4) keeps each import and export in the format it was written: ES `import` and `export` stay as they are, `import x = require()` and `export =` are emitted as `require` and `module.exports`. It implies `moduleResolution bundler` and `esModuleInterop`. [DOC S-eofsccvy]
- `esnext`, `es2015`, `es2020` and `es2022` emit ES modules only; `es2020` adds `import()` and `import.meta`, `es2022` adds top-level `await`. The reference says not to use them for Node.js, and to pair `esnext` with `moduleResolution bundler` for bundlers, Bun and tsx. [DOC S-eofsccvy]
- `system` is designed for the SystemJS loader, and `amd` and `umd` are described as modes you probably should not use ("Use a bundler instead"). [DOC S-eofsccvy]
- 6.0 deprecates the `amd`, `umd`, `systemjs` and `none` values of `module` because ESM is supported in browsers and Node.js and bundlers and import maps fill the gaps. [DOC S-sp2a6svk]
- 7.0 lists `module: amd, umd, systemjs, none` as no longer supported, recommending `esnext` or `preserve` with bundlers. [DOC S-eq3gt72a]

### moduleResolution: the modes
- `node16` and `nodenext` pick, per import, the ES `import` algorithm or the CommonJS `require` algorithm from the importing file's format and the syntax used. [DOC S-ipmh5e4a]
- `moduleResolution node16` and `nodenext` must be paired with a `node16`, `node18`, `node20` or `nodenext` `module`. [DOC S-eofsccvy]
- `bundler` supports package.json `exports` and `imports` like the Node modes but never requires a file extension on a relative import. [DOC S-ipmh5e4a]
- `bundler` also supports directory modules and extensionless paths like CommonJS, must be paired with `module esnext` or `preserve`, and implies `allowSyntheticDefaultImports`. [DOC S-eofsccvy]
- `node10` (the old name `node` stays an alias since 5.0) models Node.js before version 12: no `exports`, no `imports`, extensionless paths and directory modules supported. The reference says it should no longer be used. [DOC S-eofsccvy]
- `classic` is the resolution TypeScript used before 1.6, and the reference says it "should not be used". [DOC S-ipmh5e4a]
- Feature matrix of `nodenext`: `exports` and `imports` are matched with the conditions `types`, `node` and `import` (for an import) or `types`, `node` and `require` (for a require); extensionless relative paths and directory modules work only for `require`, not for `import`. [DOC S-eofsccvy]
- The default of `moduleResolution` as the live reference states it: `Node10` if `module` is `CommonJS`, `Node16` for `Node16`, `Node18` or `Node20`, `NodeNext` for `NodeNext`, `Bundler` for `Preserve`, `Classic` otherwise. [DOC S-lq5mn2bc]
- In the 7.0.2 source the default is "nodenext if module is nodenext, node16 if module is node16 or node18, otherwise bundler". [CODE S-sipjyeoi: internal/tsoptions/declscompiler.go#OptionsDeclarations]
- 6.0 deprecates `node10` (migrate to `nodenext` for Node.js or `bundler` for a bundler) and removes `classic`. [DOC S-sp2a6svk]
- 7.0 lists `moduleResolution: node` / `node10` and `classic` as no longer supported, recommending `nodenext` and `bundler`. [DOC S-eq3gt72a]
- `resolvePackageJsonExports` and `resolvePackageJsonImports` default to true when `moduleResolution` is `node16`, `nodenext` or `bundler`, otherwise false. [DOC S-lq5mn2bc]

### Common resolution rules
- Extension substitution: for a specifier that would make the runtime look up `/mod.js`, TypeScript tries `/mod.ts`, `/mod.tsx`, `/mod.d.ts`, then `/mod.js` and `/mod.jsx`; `.mjs` maps to `.mts`, `.d.mts`, `.mjs`; `.cjs` maps to `.cts`, `.d.cts`, `.cjs`. This is why `import "./mod.js"` resolves to `mod.ts` and why the written extension should be the output one. [DOC S-eofsccvy]
- TypeScript never supports omitting a `.mjs`/`.mts` or `.cjs`/`.cts` extension, even where a runtime or bundler does. [DOC S-eofsccvy]
- `paths` overrides resolution for bare specifiers, takes at most one `*` wildcard per pattern (the longest matching prefix wins), and accepts several fallback locations. [DOC S-eofsccvy]
- `paths` does not change the import path in emitted JavaScript, so an alias TypeScript accepts can crash at runtime; the reference advises that published libraries must not use it. [DOC S-eofsccvy]
- `paths` should not be used to point at `node_modules` or monorepo packages, because it overrides `main`, `types`, `exports` and `typesVersions`; workspaces are the recommended mechanism. [DOC S-eofsccvy]
- `baseUrl` was designed for AMD loaders; since 4.1 `paths` no longer needs it, and a `baseUrl` lookup has higher precedence than a `node_modules` lookup. [DOC S-eofsccvy]
- 6.0 deprecates `baseUrl` and stops treating it as a lookup root; a project that used it as a prefix moves the prefix into its `paths` entries. [DOC S-sp2a6svk]
- 7.0 does not support `baseUrl`. [DOC S-eq3gt72a]
- With package.json `exports` read, TypeScript always matches the `types` and `default` conditions, plus a versioned `types@{selector}` condition and any `customConditions`; the presence of `exports` blocks every subpath that is not listed. [DOC S-eofsccvy]
- Without `exports`, TypeScript tries package.json `types`, then `typings`, then `main` (with extension substitution) for a package's main module. [DOC S-eofsccvy]
- `verbatimModuleSyntax` (5.0) leaves every import or export without a `type` modifier in the output and drops those with it; an ES import then is never rewritten to `require`, and under a CommonJS-format file the compiler reports an error instead. It replaces `importsNotUsedAsValues` and `preserveValueImports`, which are deprecated in its favour. [DOC S-sc6whm2s]
- `isolatedModules` makes TypeScript warn about code a single-file transpiler (Babel, `ts.transpileModule`) cannot interpret: re-exporting a type without `type`, a namespace in a non-module file, a reference to an ambient `const enum` member. It does not change emit or checking. [DOC S-xkdynti4]

### How it fits
- For a Node.js service that emits its own JavaScript, `module` and `moduleResolution` are both `nodenext`; for a bundled app that only type-checks (`noEmit`), `module preserve` with `moduleResolution bundler` mirrors the bundler. A pair that disagrees with the real runtime makes TypeScript resolve to a file the runtime will not find. [DER S-e5r3w2iq, S-eofsccvy: the module setting informs resolution and checking even with noEmit]
- An agent that is asked "why does this import not resolve" checks, in order: the detected format of the importing file (extension and nearest `package.json` `type`), whether the written extension is the output one, whether the package has `exports` blocking a subpath, and whether a `paths` entry shadows it. [DER S-eofsccvy: detection, extension substitution, exports blocking, paths precedence]

## Reference
- Options and defaults: [typescript-tsconfig-and-compiler-options.md](typescript-tsconfig-and-compiler-options.md).
- Declaration files and project references: [typescript-projects-declarations-incremental.md](typescript-projects-declarations-incremental.md).
- Native compiler differences: [typescript-native-compiler.md](typescript-native-compiler.md).
- Sources: https://www.typescriptlang.org/docs/handbook/modules/reference.html , https://www.typescriptlang.org/tsconfig#moduleResolution .

## Examples
- SNIPPET: the pair for a Node.js ES module project, and the pair for code processed by a bundler; context: TypeScript 5.4 or later (`preserve`), 6.0 and 7.0 accept both; checked: syntax [DER S-e5r3w2iq, S-eofsccvy: the recommended pairings]

```json
{
  "compilerOptions": {
    "module": "nodenext",
    "moduleResolution": "nodenext"
  }
}
```

```json
{
  "compilerOptions": {
    "module": "preserve",
    "moduleResolution": "bundler",
    "noEmit": true
  }
}
```
