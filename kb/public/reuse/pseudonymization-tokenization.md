---
topic: reuse/pseudonymization-tokenization
priority: P2
applies_to: "a model-boundary pseudonymization layer: schema-aware tokenizing, strict restore, token kinds"
retrieved_utc: 2026-09-26
sources: [S1005, S1006, S1007, S827, S-rxee6wqu]
status: complete
---

## Summary
Presidio is a commonly chosen, pinnable dependency for PII detection and replacement. LLM Guard's
`Vault` object (placeholder<->value mapping shared between an `Anonymize` and a `Deanonymize` scanner)
is a close structural match for a pseudonymization vault object generally and is MIT licensed, so its
shape is a `logic`-level candidate to port (not its whole scanner pipeline, when a detector such as
Presidio already does detection). FF3 format-preserving encryption is a `pattern`-only reference: bespoke
partial-preserving rules per token kind may already cover the need without full FPE, and NIST's 2025
draft withdrew FF3 and FF3-1.

## Facts
- Presidio (`data-privacy-stack/presidio`, MIT) is a common detect/replace engine, pinnable at
  `presidio-analyzer==2.2.364` / `presidio-anonymizer==2.2.364`. [DOC S1005]
- Presidio's built-in operators table lists `encrypt` (caller-supplied `key`) and the deanonymize
  operator `decrypt`, which reverses it with the same key; this is the closest first-party Presidio
  mechanism to a reveal/reverse step. [DOC S827]
- A design that wants "strict: unknown placeholders refuse the call" restore semantics and a separate
  TTL-bound vault needs more than Presidio provides -- the vault stays custom regardless of which
  detector is used. [DER S827: the built-in operators table has no placeholder-mapping store or TTL]
- LLM Guard's `Anonymize` scanner replaces detected entities with placeholders and records them in a
  `Vault` object; the matching `Deanonymize` scanner looks placeholders up in that `Vault` to restore
  the originals in the model's output. [DOC S-rxee6wqu]
- LLM Guard is MIT licensed, so this `Vault` class shape (not its Presidio-style detection layer,
  when a detector is already chosen separately) can be copied with an attribution header. [DOC S1006]
- LLM Guard's own docs do not define a TTL or encryption-at-rest for its `Vault` -- both are left to
  the embedding application, i.e. LLM Guard's vault is a mapping-object pattern only, not a solved
  TTL/encryption-at-rest implementation (see `reuse/secret-vault-encryption.md` for that). [DER S-rxee6wqu: the Vault is described only as remembering the Anonymize changes; no TTL or encryption setting is documented]
- `python-fpe` (PyPI `ff3`, Apache-2.0) implements the FF3 and FF3-1 format-preserving encryption
  algorithms of NIST SP 800-38G and its Revision 1 draft: ciphertext keeps the plaintext's alphabet
  (radix) and length, and `decrypt` with the same key and tweak restores it. [DOC S1007]
- The `python-fpe` README warns that NIST's February 2025 Draft 2 withdrew FF3 and FF3-1 from the
  standard because of published vulnerabilities. [DOC S1007]
- Bespoke per-token-kind partial-preserving rules (e.g. an IPv4 network keeping its /24, a domain SID
  keeping its RID) rather than full FPE are recorded elsewhere as a design choice, so FPE is a
  `pattern`-only fallback, not a current gap. [UNK: not in S1007 as re-read 2026-09-27]

## Reference
| project | what it would replace | licence | verdict |
|---|---|---|---|
| Presidio | detection + operator-based replace | MIT | dependency |
| LLM Guard `Vault` class shape | the mapping-object half of a pseudonymization vault | MIT | logic (port the class shape, not the pipeline) |
| python-fpe (ff3) | a format-preserving alternative to bespoke per-token-kind rules | Apache-2.0 | pattern (no current gap) |

## Examples
No fixture data required (mechanism-only facts).
