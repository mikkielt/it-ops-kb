---
topic: agents/typescript-projects-declarations-incremental
priority: P3
applies_to: "TypeScript 3.0 to 7.0: project references and composite projects, tsc --build (build mode), incremental builds and .tsbuildinfo, declaration output (declaration, declarationDir, declarationMap, emitDeclarationOnly, isolatedDeclarations); handbook pages pinned at TypeScript-Website commit 6556b08"
retrieved_utc: 2026-10-15
sources: [S-fzozdweh, S-7sglzzpd, S-xgfiu5jf, S-fe6375ln, S-hhmjdvsd, S-6a5dvcgm, S-mghofndm, S-trc6i7ti, S-rklpxnqt, S-ff6may7t, S-lq5mn2bc, S-vdfo2blu, S-sp2a6svk, S-eq3gt72a, S-e6jwgvmc, S-mtnr5emw]
status: complete
---

# TypeScript project references, build mode, incremental builds and declaration output

## Summary
A large TypeScript codebase is split into several `tsconfig.json` projects that point at each other with `references`; every referenced project must be `composite`, which constrains it so that its `.d.ts` output can stand in for its source. `tsc --build` (`-b`) is a separate entry point that finds the referenced projects, decides which are out of date, and builds them in dependency order; a plain `tsc` does not build references. Incremental state is kept in `.tsbuildinfo` files. Declaration output (`.d.ts`) is a set of options of its own, and `composite` turns `declaration` on.

## Facts

### Project references and composite
- `tsconfig.json` has a top-level `references` array of `{ "path": ... }` objects; a path names a directory with a `tsconfig.json` or the config file itself, which may have any name. [DOC S-rklpxnqt]
- Importing a module from a referenced project loads that project's output declaration file, and build mode builds the referenced project first when it is out of date. [DOC S-rklpxnqt]
- A referenced project must set `composite`. With it on, `rootDir` defaults to the directory of the `tsconfig.json`, every implementation file must be matched by `include` or listed in `files` (otherwise `tsc` names the files left out), and `declaration` defaults to true. [DOC S-fzozdweh]
- `references` is the one top-level property that `extends` does not inherit. [DOC S-ff6may7t]
- A "solution" `tsconfig.json` that only lists `references` should set `files` to an empty array; otherwise it compiles the files a second time. Since 3.0 an empty `files` is not an error when at least one reference exists. [DOC S-rklpxnqt]
- The handbook recommends centralising shared options in a base file used through `extends`, and for relative-module layouts either an explicit `outDir` subfolder per project or a `rootDir` set to the common root. [DOC S-rklpxnqt]
- Dependent projects read `.d.ts` files built from their dependencies, so a fresh clone shows spurious errors in an editor until the dependencies are built or the outputs are checked in; VS Code generates declarations in memory to mitigate it, which `disableSourceOfProjectReferenceRedirect` turns off for very large projects. [DOC S-rklpxnqt]
- `declarationMap` generates source maps for `.d.ts` files so "Go to Definition" lands in the `.ts` source; the reference says to strongly consider it with project references. [DOC S-6a5dvcgm]

### Build mode (tsc --build)
- `tsc --build` (`-b`) is a build orchestrator: it finds all referenced projects, detects whether each is up to date, and builds out-of-date projects in the right order. `tsc` without `--build` never builds dependencies. [DOC S-rklpxnqt]
- `tsc -b` takes any number of config paths (`tsc -b src test`) and reorders them so dependencies build first; with no argument it uses the `tsconfig.json` in the current directory. [DOC S-rklpxnqt]
- Build-mode flags: `--verbose` (explain what is happening), `--dry` (show what would be done), `--clean` (delete the outputs of the projects, combinable with `--dry`), `--force` (act as if every project were out of date) and `--watch`, which cannot be combined with anything except `--verbose`. [DOC S-rklpxnqt]
- `tsc -b` behaves as if `noEmitOnError` were on for all projects, because an incremental system that wrote outputs for a dependency with an error would show the error only once. [DOC S-rklpxnqt]
- If build outputs are checked in, a `--force` build may be needed after a source-control operation that does not preserve timestamps. [DOC S-rklpxnqt]
- MSBuild projects enable build mode with `<TypeScriptBuildMode>true</TypeScriptBuildMode>`, and then ignore TypeScript project properties in favour of the `tsconfig.json`. [DOC S-rklpxnqt]
- `noEmitOnError` itself defaults to false. [DOC S-vdfo2blu]

### Incremental builds
- `incremental` saves information about the project graph from the last compilation in `.tsbuildinfo` files next to the output; the files are not used at runtime and can be deleted safely. [DOC S-7sglzzpd]
- `incremental` defaults to true when `composite` is on, and to false otherwise. [DOC S-lq5mn2bc]
- `tsBuildInfoFile` names the file; when it is not set the default is `<outFile>.tsbuildinfo` with `outFile`, else `<outDir>/<config name>.tsbuildinfo` (relative to `rootDir` when both `rootDir` and `outDir` are set), else `<config name>.tsbuildinfo` beside the config. [DOC S-xgfiu5jf]
- A `.tsbuildinfo` file is a cache of one project's state, so a CI job that keeps it between runs has to treat it as disposable: a suspect file is cured by deleting it or by `tsc -b --force`. [DER S-7sglzzpd, S-rklpxnqt: the file is safe to delete; `--force` rebuilds every project]
- The 6.0 announcement removes `outFile`, so the `<outFile>.tsbuildinfo` case exists only up to 5.x. [DOC S-sp2a6svk]

### Declaration output
- `declaration` emits a `.d.ts` for every TypeScript or JavaScript file, describing the module's external API; with JavaScript inputs it is advisable to combine it with `emitDeclarationOnly` or an `outDir` so source files are not overwritten. [DOC S-fe6375ln]
- `declarationDir` sets the root directory for emitted declaration files; for example `./types` puts `index.d.ts` under `types/` while the `.js` stays where `outDir` (or the source) puts it. [DOC S-hhmjdvsd]
- `emitDeclarationOnly` writes only `.d.ts` files and no `.js`; it is meant for the case where another tool produces the JavaScript, or where TypeScript only generates declarations for consumers. [DOC S-mghofndm]
- `isolatedDeclarations` (since 5.5) requires enough annotation on exports for other tools to generate declaration files trivially, one file at a time. [DOC S-trc6i7ti]
- In the native compiler's repository, declaration emit from `.js` input has substantially changed behaviour on purpose, and matching the old compiler's output exactly is a non-goal. [DOC S-e6jwgvmc]
- The native compiler's README lists "Declaration emit", "Build mode / project references" and "Incremental build" as done. [DOC S-mtnr5emw]
- The native compiler runs several type-checkers per project (default `--checkers 4`, `--singleThreaded` turns this off) and in build mode `--builders` bounds parallel project builders; the announcement describes `--checkers` and `--builders` as experimental. [DOC S-eq3gt72a]

### How it fits
- For a monorepo mapping, `references` give the project dependency graph without running a build: read each project's own `tsconfig.json` for `references` and `composite`, because `references` is never inherited through `extends` and so a base file cannot supply it. [DER S-ff6may7t, S-rklpxnqt: references are declared per file and not inherited]
- `tsc -b --dry` shows what a build would do without writing anything, and dependents consume the declaration output of a referenced project, so a referenced project is built (not only type-checked) before its dependents are checked. [DER S-rklpxnqt, S-fzozdweh: dry run; dependents load `.d.ts` output]

## Reference
- Options, defaults and the strict family: [typescript-tsconfig-and-compiler-options.md](typescript-tsconfig-and-compiler-options.md).
- Module resolution: [typescript-module-resolution.md](typescript-module-resolution.md).
- Native compiler status for build mode and incremental builds: [typescript-native-compiler.md](typescript-native-compiler.md).
- Sources: https://www.typescriptlang.org/docs/handbook/project-references.html , https://www.typescriptlang.org/tsconfig .

## Examples
- SNIPPET: a solution config with one referenced composite project; context: TypeScript 3.0 or later, build with `tsc -b`; checked: syntax [DER S-rklpxnqt, S-fzozdweh: references array, empty files array, composite]

```json
{
  "files": [],
  "references": [{ "path": "./packages/core" }]
}
```

```json
{
  "compilerOptions": {
    "composite": true,
    "declarationMap": true,
    "outDir": "./dist"
  },
  "include": ["src"]
}
```
