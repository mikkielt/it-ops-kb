---
topic: privacy/presidio-recognizer-yaml
priority: P0
applies_to: "Presidio main @ e9895a5 (the format is also in 2.2.364)"
retrieved_utc: 2026-09-26
sources: [S821, S822, S823, S824, S825, S826, S809, S800, S801]
status: complete
files: [privacy/presidio-recognizer-registry.schema.json, privacy/presidio-example_recognizers.yaml]
---
# Presidio recognizer registry YAML and regex flags

## Summary
- `RecognizerRegistryProvider(conf_file=...)` loads a YAML file with `supported_languages`, `global_regex_flags` and `recognizers`. Each recognizer is `type: predefined` (an existing class) or `type: custom` (patterns or a deny-list).
- Artifacts: `presidio-recognizer-registry.schema.json` (JSON Schema generated from the pydantic models) and `presidio-example_recognizers.yaml` (the upstream example, verbatim, MIT, (c) Presidio Contributors).
- The default flags are `26` = `DOTALL | MULTILINE | IGNORECASE`. Matching uses the third-party `regex` module with a per-match timeout (default 60 s, env `REGEX_TIMEOUT_SECONDS`).

## Facts
- Top-level model `RecognizerRegistryConfig` has `supported_languages`, `global_regex_flags` (default 26) and `recognizers`, with `extra="forbid"`. [DOC S821]
- Recognizer fields: `name` (required), `class_name`, `enabled` (default true), `type`, `supported_language` / `supported_languages` (strings or `{language, context}` objects), `context`, `supported_entity` / `supported_entities`, `score_thresholds`. [DOC S821]
- Custom recognizers also take `patterns` (each needs `name`, `regex`, `score` in 0..1), `deny_list`, `deny_list_score`, `country_code`. At least one of `patterns` or `deny_list` is required. A custom name may not collide with a predefined class name. [DOC S821]
- `type` defaults to custom when omitted. For predefined recognizers `name` is the class name; for custom ones it is the display name. [DOC S823]
- `deny_list_score` defaults to 1.0. The docs say it used to default to 0.0 through `RecognizerRegistryProvider`. [DOC S823]
- The docs say `supported_languages` in the registry must be identical to the analyzer engine's. [DOC S823]
- `score_thresholds` per recognizer / per entity (e.g. `default: 0.4`, `CREDIT_CARD: 0.7`), with the analyzer's `default_score_threshold` as fallback, shipped in 2.2.364 (PR #2116 in the release notes), although the CHANGELOG lists it under `[unreleased]`. [DOC S801, S800]
- `supported_countries` (top level, ISO-3166-1 alpha-2) restricts predefined recognizers to those whose class has a matching `COUNTRY_CODE`. Locale-agnostic recognizers always load. [DOC S822, S809]
- `PatternRecognizer` compiles each pattern with `regex.compile(pattern, flags=flags)`, using the per-call flags or else its `global_regex_flags`. It matches with `finditer(text, timeout=REGEX_TIMEOUT_SECONDS)`. [DOC S825]
- `REGEX_TIMEOUT_SECONDS = int(os.environ.get("REGEX_TIMEOUT_SECONDS", 60))`. [DOC S825]
- `RecognizerRegistry(global_regex_flags=...)` defaults to `re.DOTALL | re.MULTILINE | re.IGNORECASE`. The docs show how to set flags for one recognizer or for all of them. [DOC S826, S824]
- 26 = DOTALL(16) + MULTILINE(8) + IGNORECASE(2). So by default, custom patterns are case-insensitive and `.` matches newlines. [DER S826: Python flag values]
- The JSON Schema does not express the validators (pattern field checks, patterns-or-deny_list, name-collision check). [DER S821: they are `field_validator` / `model_validator` code]

## Reference
| Key | Level | Notes |
|---|---|---|
| supported_languages | top | list of ISO 639-1 codes |
| global_regex_flags | top | int, default 26 |
| supported_countries | top | optional, alpha-2 list |
| recognizers[].name | rec | class name (predefined) or label (custom) |
| recognizers[].type | rec | predefined / custom |
| recognizers[].patterns[] | custom | name, regex, score |
| recognizers[].deny_list / deny_list_score | custom | list / float (default 1.0) |
| recognizers[].context | rec | list of words |
| recognizers[].score_thresholds | rec | from 2.2.364 |

## Examples
```yaml
supported_languages: [en]
global_regex_flags: 26
recognizers:
  - name: CorpHostRecognizer
    type: custom
    supported_entity: HOST
    supported_language: en
    patterns:
      - name: corp laptop name
        regex: "\\bPL-(LT|SRV)-\\d{4,5}\\b"
        score: 0.8
    context: [host, device, computer]
```
