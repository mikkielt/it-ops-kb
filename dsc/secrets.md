---
topic: dsc/secrets
priority: P0
applies_to: "Microsoft DSC 3.3.0 (release/v3.3 @ ea572fa); leakage re-checked on 3.4.0-preview.1"
retrieved_utc: 2026-09-26
sources: [S105, S106, S114, S116, S117, S124, S125, S126, S142]
status: complete
---

# Secret handling: `secureString`, `secureObject`, `secret()`, trace leakage

## Summary
- Parameters of type `secureString` / `secureObject` travel inside dsc wrapped as `{"secureString": "<value>"}`. Result output replaces them with `<secureValue>`.
- `secret(name, [vault])` asks every installed extension with the `secret` capability. The 3.3.0 and 3.4.0-preview.1 Windows zips contain **no** such extension, so `secret()` fails unless one is installed.
- **Leak:** at `--trace-level trace`, 3.3.0 and 3.4.0-preview.1 write the plaintext secure value to stderr. The lines are "Desired state", "Verify JSON" and "Invoking command ... with args". At `debug` and `info` it was not seen.
- Secure values reach command resources as plain JSON on the command line (`--input <json>`) or on stdin, depending on the manifest.

## Facts
- `SECURE_VALUE_REDACTED = "<secureValue>"`. Parameter types `secureString` and `secureObject` are serialized as objects keyed `secureString` / `secureObject`. [DOC S125]
- `redact()` replaces any secure-value object with `<secureValue>`, recursively through maps and arrays. It is applied, for example, to `before_state` in set results. [DOC S142,S105]
- `secret()`: category deployment, 1 to 2 string args (name, optional vault). It queries all extensions whose capabilities include `secret`. Zero such extensions → error `functions.secret.noExtensions`. Two extensions returning different values → error `multipleSecrets`. An extension error is logged as a warning and skipped. The returned value is wrapped as a SecureString. [DOC S124]
- The extension capability `secret` is set when an extension manifest defines a `secret` operation. [DOC S106]
- Extensions in the 3.3.0 and 3.4.0-preview.1 Windows zips: `Microsoft.Windows.Appx/Discover` and `Microsoft.PowerShell/Discover`, both discover-only. [DOC S114,S115]
- Test on the 3.3.0 binary, 2026-09-23: document with a `secureString` parameter passed to `Microsoft.DSC.Debug/Echo`, value `Canary-7731`. Stdout of `config get`/`set` contained 0 occurrences. Stderr at `-l trace` contained 2 (get) / 6 (set). At `-l debug` and `-l info`: 0. The same counts on 3.4.0-preview.1. [DER S116,S117: grep of captured output]
- The leaking trace lines come from `dsc_lib::configure` ("Desired state: {...secureString: <plaintext>}") and `dsc_lib::dscresources::command_resource` ("Verify JSON for ..." and "Invoking command 'dscecho' with args [--input, {...}]"). [DER S116: captured trace lines]
- The trace level can be raised without a CLI flag through the `DSC_TRACE_LEVEL` env var or the `tracing` section of `dsc.settings.json` (`allowOverride`). See `settings-and-paths.md`. [DOC S101,S107]
- Open issue #1209 "Parameter `secureString` transforms input incorrectly on adapter" (Issue-Bug). [DOC S126]

## Reference
| Mechanism | Where the plaintext exists |
|---|---|
| `secureString` parameter | dsc memory; resource argv or stdin; trace-level log |
| `secret()` | extension stdout → dsc; then as above |
| Output (`-o json`) | redacted to `<secureValue>` where dsc applies `redact()` |

## Examples
```yaml
parameters:
  svcPassword:
    type: secureString
resources:
- name: PL-SRV-0042 app service
  type: Microsoft.DSC.Debug/Echo
  properties:
    output: "[parameters('svcPassword')]"
```
Run with `-l info` or lower. `-l trace` writes the value to stderr.
