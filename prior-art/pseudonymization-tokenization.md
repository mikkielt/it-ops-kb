---
topic: prior-art/pseudonymization-tokenization
priority: P2
applies_to: "model-only pseudonymization before any data reaches the LLM"
retrieved_utc: 2026-09-26
sources: [S1005, S1006, S1007, S827, S-nvdbj7bz, S-mn7nbj7n]
status: complete
---

## Summary
Presidio (Microsoft-originated, now `data-privacy-stack/presidio`) is the reference open-source
implementation of detect-then-replace PII handling: `presidio-analyzer` finds entities,
`presidio-anonymizer` replaces them with configurable operators, and a separate deanonymize path can
reverse a subset of operators. LLM Guard builds an "Anonymize"/"Deanonymize" scanner pair directly on
top of Presidio, adding an explicit in-memory "vault" that maps placeholders back to original values
for a single interaction. Format-preserving encryption (FF3/FF3-1) is a separate, lower-level
primitive some pipelines use instead of random placeholders when the replaced value must keep its
original format (e.g. a digit string staying the same length).

## Facts
- `presidio-analyzer` identifies PII entities in text with predefined or custom recognizers (named
  entity recognition, regular expressions, rule-based logic and checksums, with context), returning
  results with entity type, start/end offsets and a score; `presidio-anonymizer` then replaces each span
  using a per-entity `OperatorConfig` (e.g. `replace`, `redact`, `mask`, `hash`, `encrypt`) with no fixed
  vocabulary of substitutes required. [DOC S1005, S827]
- Presidio's `encrypt`/`decrypt` operator pair is the built-in *reversible* path: the `encrypt`
  anonymizer encrypts the value with a caller-supplied key, and the `decrypt` deanonymizer
  (`DeanonymizeEngine`) restores the original text with the same key — this is the closest first-party
  Presidio mechanism to a reveal/reverse step. [DOC S827]
- Presidio is licensed MIT and is documented as "an open-source framework for detecting, redacting,
  masking, and anonymizing sensitive data (PII) across text, images, and structured data"; it ships
  separate analyzer, anonymizer and image-redactor modules that a caller composes. [DOC S1005]
- LLM Guard provides an `Anonymize` input scanner and a matching `Deanonymize` output scanner; the
  `Anonymize` scanner uses the Presidio Analyzer (plus its own patterns) for detection, replaces each
  entity with a placeholder such as `[REDACTED_PERSON_1]`, and records the original values in a `Vault`
  object (an LLM Guard class) passed to the scanner; `Deanonymize` looks up placeholders found in the
  model's *output* in that same `Vault` to put the original values back. [DOC S-nvdbj7bz, S-mn7nbj7n, S1006]
- The LLM Guard vault's default lifetime and scope is the lifetime of the Python `Vault` object the
  caller constructs and passes to both scanners — LLM Guard's own docs do not define a TTL or
  encryption-at-rest for the vault; both are left to the embedding application. [DER S-nvdbj7bz, S-mn7nbj7n: both scanner pages only construct `Vault()` and mention no TTL or encryption]
- FF3/FF3-1 format-preserving encryption (NIST SP 800-38G / 800-38G Rev.1 draft) encrypts a value over
  a fixed alphabet (radix) into a ciphertext over the *same* alphabet and of the same length, so a
  replaced value is reversible with the same key and keeps a shape a downstream parser or human
  expects (e.g. a 10-digit string stays 10 digits); the `python-fpe` package (PyPI name `ff3`)
  implements this and cites the NIST specifications directly. Its README notes that NIST has since
  withdrawn FF3 and FF3-1 because of published vulnerabilities. [DOC S1007]

## Reference
| project | detect | replace/anonymize | reverse | vault/mapping storage |
|---|---|---|---|---|
| presidio-analyzer + presidio-anonymizer | yes (analyzer) | yes, `OperatorConfig` | via `encrypt`/`decrypt` operator pair, same key | caller-managed (Presidio does not persist mappings itself) |
| LLM Guard Anonymize/Deanonymize | delegates to Presidio-style detection | placeholder substitution | via `Deanonymize` scanner + shared `Vault` object | in-process `Vault` object, caller-scoped lifetime |
| python-fpe (ff3) | n/a (encryption primitive, not a detector) | format-preserving ciphertext, same alphabet/length | yes, same key decrypts | caller-managed |

## Examples
No fixture data required (mechanism-only facts).
