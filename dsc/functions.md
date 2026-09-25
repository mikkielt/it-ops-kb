---
topic: dsc/functions
priority: P0
applies_to: "Microsoft DSC 3.0.0 to 3.4.0-preview.1 (list generated from the 3.3.0 binary)"
retrieved_utc: 2026-09-23
sources: [S116, S117, S124, S129, S130, S131, S100]
status: complete
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
- Functions registered at v3.0.0: add, concat, createArray, div, envvar, int, max, min, mod, mul, parameters, path, reference, resourceId, sub, systemRoot, variables. [DOC S129]
- v3.1.0 adds equals, format, if. [DOC S130]
- v3.2.0 adds 61 functions, including secret, context, stdout, tryWhich, utcNow, uniqueString, the lambda functions (lambda, map, filter, lambdaVariables), the cidr functions (parseCidr, cidrHost, cidrSubnet) and the string/array/object helpers. [DOC S131]
- 3.3.0 adds `restartRequired(<process|service|system>, [name])` → boolean and `stateChanged(<resourceId>)` → boolean. [DOC S116]
- `envvar(<string>)`: category system, returns string, "Retrieves the value of an environment variable". [DOC S116]
- `secret(<name>, [vault])`: category deployment; needs an extension with the `secret` capability (see `secrets.md`). [DOC S124]
- `dsc function list` filters: positional name (wildcards), `-c/--category` (repeatable, all must match), `-d/--description` (wildcards). [DOC S100]

## Reference
See `functions-3.3.0.csv`. Categories: array, cidr, comparison, date, deployment, lambda, logical, numeric, object, resource, string, system.

## Examples
```yaml
resources:
- name: PL-LT-00123 temp path
  type: Microsoft.DSC.Debug/Echo
  properties:
    output: "[path(envvar('SystemRoot'), 'Temp')]"
```
