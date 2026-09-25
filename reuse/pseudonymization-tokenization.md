---
topic: reuse/pseudonymization-tokenization
priority: P2
applies_to: "a model-boundary pseudonymization layer: schema-aware tokenizing, strict restore, token kinds"
retrieved_utc: 2026-09-25
sources: [S1005, S1006, S1007]
status: complete
---

## Summary
Presidio is a commonly chosen, pinnable dependency for PII detection and replacement. LLM Guard's
`Vault` object (placeholder<->value mapping shared between an `Anonymize` and a `Deanonymize` scanner)
is a close structural match for a pseudonymization vault object generally and is MIT licensed, so its
shape is a `logic`-level candidate to port (not its whole scanner pipeline, when a detector such as
Presidio already does detection). FF3 format-preserving encryption is a `pattern`-only reference: bespoke
partial-preserving rules per token kind may already cover the need without full FPE.

## Facts
- Presidio (`data-privacy-stack/presidio`, MIT) is a common detect/replace engine, pinnable at
  `presidio-analyzer==2.2.364` / `presidio-anonymizer==2.2.364`. [DOC S1005]
- Presidio's own `encrypt`/`decrypt` `OperatorConfig` pair (AES, caller-supplied key) is the closest
  first-party Presidio mechanism to a reveal/reverse step, but a design that wants "strict: unknown
  placeholders refuse the call" restore semantics and a separate TTL-bound vault needs more than
  Presidio provides -- the vault stays custom regardless of which detector is used. [DOC S1005]
- LLM Guard's `Anonymize` scanner replaces detected entities with placeholders and stores the mapping
  in a `Vault` object it passes to a matching `Deanonymize` scanner that restores originals in the
  model's output; LLM Guard is MIT licensed, so this `Vault` class shape (not its Presidio-style
  detection layer, when a detector is already chosen separately) is legally copyable with an
  attribution header. [DOC S1006]
- LLM Guard's own docs do not define a TTL or encryption-at-rest for its `Vault` -- both are left to
  the embedding application, i.e. LLM Guard's vault is a mapping-object pattern only, not a solved
  TTL/encryption-at-rest implementation (see `reuse/secret-vault-encryption.md` for that). [DER S1006]
- `python-fpe` (PyPI `ff3`, Apache-2.0) implements NIST SP 800-38G(-Rev.1) format-preserving
  encryption: same alphabet and length in and out, reversible with the same key. Apache-2.0 permits
  copying with notice. Bespoke per-token-kind partial-preserving rules (e.g. an IPv4 network keeping
  its /24, a domain SID keeping its RID) rather than full FPE are recorded elsewhere as a design
  choice, so this is a `pattern`-only fallback, not a current gap. [DOC S1007]

## Reference
| project | what it would replace | licence | verdict |
|---|---|---|---|
| Presidio | detection + operator-based replace | MIT | dependency |
| LLM Guard `Vault` class shape | the mapping-object half of a pseudonymization vault | MIT | logic (port the class shape, not the pipeline) |
| python-fpe (ff3) | a format-preserving alternative to bespoke per-token-kind rules | Apache-2.0 | pattern (no current gap) |

## Examples
No fixture data required (mechanism-only facts).
