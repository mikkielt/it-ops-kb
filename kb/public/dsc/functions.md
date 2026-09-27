---
topic: dsc/functions
priority: P0
applies_to: "Microsoft DSC 3.0.0 to 3.4.0-preview.1 (list generated from the 3.3.0 binary)"
retrieved_utc: 2026-09-26
sources: [S116, S117, S124, S129, S130, S131, S100]
status: complete
files: [dsc/functions-3.3.0.csv]
---

# Configuration expression functions

## Summary
- `dsc function list -o json` on 3.3.0 returns 83 functions. 3.4.0-preview.1 returns the same 83 names.
- By version: 3.0.0 has 17 functions; 3.1.0 has 20 (adds `equals`, `format`, `if`); 3.2.0 has 81; 3.3.0 adds `restartRequired` and `stateChanged` (83).
- Full table: `functions-3.3.0.csv` (name, category, since_version, min/max args, return types, syntax, description). The output is from the dsc binary (MIT).
- Environment access is `envvar(name)`, available since 3.0.0. There is no function named `env()`.

## Facts
- 3.3.0 binary `dsc function list` lists 83 functions in categories: string 28, array 19, object 12, numeric 9, logical 7, comparison 6, system 6, lambda 4, deployment 4, cidr 3, resource 2, date 1 (some functions are in more than one category). [DOC S116]
- The function name set is identical in 3.3.0 and 3.4.0-preview.1. [DER S116,S117: sorted name lists compared]
- Functions registered at v3.0.0 (18): add, base64, concat, createArray, div, envvar, int, max, min, mod, mul, parameters, path, reference, resourceId, sub, systemRoot, variables. [CODE S129: dsc_lib/src/functions/mod.rs#FunctionDispatcher::new]
- v3.1.0 adds equals, format, if. [CODE S130: dsc_lib/src/functions/mod.rs#FunctionDispatcher::new]
- v3.2.0 adds 60 functions (81 registered), including secret, context, stdout, tryWhich, utcNow, uniqueString, the lambda functions (lambda, map, filter, lambdaVariables), the cidr functions (parseCidr, cidrHost, cidrSubnet) and the string/array/object helpers. [CODE S131: lib/dsc-lib/src/functions/mod.rs#FunctionDispatcher::new]
- 3.3.0 adds `restartRequired(<process|service|system>, [name])` → boolean and `stateChanged(<resourceId>)` → boolean. [DER S116,S131: in the 3.3.0 `function list`, not registered in v3.2.0 functions/mod.rs]
- `envvar(<string>)`: category system, returns string, "Retrieves the value of an environment variable". [DOC S116]
- `secret(<name>, [vault])`: category deployment; needs an extension with the `secret` capability (see `secrets.md`). [CODE S124: lib/dsc-lib/src/functions/secret.rs#get_metadata]
- `dsc function list` filters: positional name, `-c/--category` (repeatable, all must match), `-d/--description` (help text: accepts wildcards). [DOC S100, S116]
- The positional function name also takes wildcards: on the 3.3.0 binary `dsc function list 'to*'` returns toLower and toUpper. [DER S116: local run 2026-09-27]

## Reference
See `functions-3.3.0.csv`. Categories: array, cidr, comparison, date, deployment, lambda, logical, numeric, object, resource, string, system.

## Examples
- SNIPPET: build a path from an environment variable with the `path` and `envvar` functions; context: dsc 3.0.0+; checked: no [DER S116, S117: `functions-3.3.0.csv` rows for `envvar` and `path`, generated from the 3.3.0 binary's function list]
```yaml
resources:
- name: PL-LT-00123 temp path
  type: Microsoft.DSC.Debug/Echo
  properties:
    output: "[path(envvar('SystemRoot'), 'Temp')]"
```
