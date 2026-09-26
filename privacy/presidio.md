---
topic: privacy/presidio
priority: P0
applies_to: "Presidio 2.2.364 (latest release) and main @ e9895a5 (2026-09-23)"
retrieved_utc: 2026-09-26
sources: [S800, S801, S802, S803, S804, S805, S806, S807, S808, S809, S834, S842]
status: complete
---
# Presidio: releases, UUID recognizer, packaging

## Summary
- Latest Presidio release is **2.2.364** (GitHub release 2026-07-22; PyPI upload 2026-07-22). No release after it exists as of 2026-09-23.
- `UuidRecognizer` (entity `UUID`) is **not** in 2.2.364. It was merged to `main` on 2026-07-27 and sits in the `[unreleased]` changelog section.
- On `main` it is listed in `default_recognizers.yaml` with no `enabled: false`, so it is on by default there; it filters out the nil UUID.
- Packages are MIT-licensed and declare `requires_python <3.15,>=3.10`.

## Facts
- GitHub releases list: newest tag `2.2.364` published 2026-07-22T08:30:12Z; previous `2.2.363` 2026-06-28. [DOC S801]
- PyPI `presidio-analyzer` and `presidio-anonymizer` latest version is 2.2.364, uploaded 2026-07-22T07:54:34. [DOC S802]
- `presidio-anonymizer` PyPI latest is also 2.2.364. [DOC S803]
- Tag `2.2.364` points at commit `779dbd286d5ef4d1fbe2514275fb1bce358f2417`. [DOC S804]
- At tag 2.2.364, `predefined_recognizers/generic/` has no `uuid_recognizer.py` (files: credit_card, crypto, date, email, iban, ip, mac, phone, url). [DOC S805]
- `default_recognizers.yaml` at tag 2.2.364 contains no `Uuid` entry (0 matches). [DOC S806]
- The only commit touching `uuid_recognizer.py` is `e069216` "feat: Add UuidRecognizer for detecting UUIDs (v1-v8) (#2175)", dated 2026-07-27, after the 2.2.364 release. [DOC S807]
- Therefore no released Presidio version contains `UuidRecognizer`. [DER S801,S807: newest release 2026-07-22 < merge 2026-07-27, and absent from the tag tree S805]
- `UuidRecognizer` matches `\b[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\b` with score 0.5, context words `uuid`, `guid`, `unique identifier`, language `en`. [DOC S808]
- It invalidates matches whose version nibble is not 1-8, whose variant nibble is not 8/9/a/b, and the nil UUID `00000000-0000-0000-0000-000000000000`. [DOC S808]
- So the fixture tenant id `00000000-0000-0000-0000-000000000000` would not be detected as `UUID`. [DER S808: nil UUID explicitly invalidated]
- Only the hyphenated 8-4-4-4-12 form is matched; there is no pattern for unhyphenated 32-hex GUIDs. [DER S808: single pattern in PATTERNS]
- On `main`, `default_recognizers.yaml` lists `UuidRecognizer` as `type: predefined` without `enabled: false`. [DOC S809]
- The CHANGELOG's `[unreleased]` section lists `UuidRecognizer`, South African recognizers, `NoOpNlpEngine`, per-recognizer score thresholds, and `BatchDeanonymizeEngine`; there is no `[2.2.364]` heading even though some of those items shipped in 2.2.364. [DOC S800] (see conflicts)
- `batch_deanonymize_engine.py` is present in `presidio_anonymizer/` at tag 2.2.364. [DOC S834]
- Licence: MIT, copyright "Presidio Contributors" (changed from "Microsoft Corporation"). [DOC S842, S800]
- PyPI metadata: licence MIT, `requires_python <3.15,>=3.10`, classifiers include Python 3.10-3.14. [DOC S802]

## Reference
| Release | GitHub published | PyPI upload |
|---|---|---|
| 2.2.364 | 2026-07-22 | 2026-07-22 |
| 2.2.363 | 2026-06-28 | 2026-06-28 |
| 2.2.362 | 2026-03-18 | 2026-03-15 |
| 2.2.361 | 2026-02-12 | 2026-02-12 |
| 2.2.360 | 2025-09-09 | 2025-09-09 |

## Examples
Text `Device PL-LT-00123 has Entra id 3f2b8c1e-5d4a-4b7c-9e1f-2a3b4c5d6e7f` on `main` would give a `UUID` result for the id (version nibble 4, variant 9). This follows from the pattern and validation above; it was not run.
