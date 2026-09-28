---
topic: reuse/pseudonymization-tokenization
priority: P2
applies_to: "a model-boundary pseudonymization layer: schema-aware tokenizing, strict restore, token kinds"
retrieved_utc: 2026-09-28
sources: [S1005, S1006, S1007, S827, S-rxee6wqu, S-7t5ulcii, S-h2cmbqvf, S-dcjdn73r]
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
- In the source, LLM Guard's `Vault` is an in-memory list of `(placeholder, original)` tuples with `append`, `extend`, `remove`, `get` and `placeholder_exists`; it has no persistence, expiry or encryption code, which confirms the class is a mapping pattern only. [CODE S-7t5ulcii: llm_guard/vault.py#Vault]
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
- Since NIST's draft withdrew FF3 and FF3-1, a tokenizer that keeps chosen parts of a value by its own per-kind rules (an IPv4 network keeping its /24, a domain SID keeping its RID) should not depend on them: FPE is a `pattern` to borrow, not a dependency. [DER S1007: the README's withdrawal warning]
- A SID's string form is `S-R-X-Y1-Y2-...-Yn`: revision, identifier authority, then subauthorities; all subauthorities but the last form the domain identifier and the last is the RID. Example: `S-1-5-32-544` is built-in Administrators (authority 5, NT Authority; domain 32, Builtin; RID 544). [DOC S-h2cmbqvf]
- Domain accounts' SIDs carry a per-domain identifier after `S-1-5-21-` (the page's example is three 32-bit values, `S-1-5-21-<a>-<b>-<c>-512` for Domain Admins); no two domains in an enterprise share it, and SIDs are never reused. [DOC S-h2cmbqvf]
- Well-known SIDs are constant on every system: universal ones such as `S-1-1-0` (World), `S-1-5-18` (LocalSystem), `S-1-5-32-5xx` built-in groups and `S-1-5-80-0` (All Services); domain-relative ones reuse fixed RIDs (500 Administrator, 512 Domain Admins, 513 Domain Users). Capability SIDs start `S-1-15-3`. [DOC S-h2cmbqvf]
- Active Directory also gives every object a 128-bit GUID in `objectGUID`, which never changes, while a user who moves domains gets a new SID and keeps the old one in `SIDHistory`. [DOC S-h2cmbqvf]
- A UPN is `<user account name>@<UPN suffix>`: implicit as `UserName@DNSDomainName`, or explicit with a name and suffix an administrator chose. The other domain credential format, the down-level logon name, is `DOMAIN\UserName` with the NetBIOS domain name. [DOC S-dcjdn73r]
- For redaction, a well-known SID or a built-in `S-1-5-32-*` SID identifies no one and can stay, while the domain identifier of an `S-1-5-21-*` SID names the organisation's domain and must go (the RID alone is a per-domain counter); a user must be matched both as a UPN (`name@suffix`) and as a down-level logon name (`DOMAIN\name`), and an explicit UPN's suffix need not be the DNS domain, so a suffix allowlist cannot be derived from DNS names alone. [DER S-h2cmbqvf, S-dcjdn73r: SID structure and well-known values; UPN forms]

## Reference
| project | what it would replace | licence | verdict |
|---|---|---|---|
| Presidio | detection + operator-based replace | MIT | dependency |
| LLM Guard `Vault` class shape | the mapping-object half of a pseudonymization vault | MIT | logic (port the class shape, not the pipeline) |
| python-fpe (ff3) | a format-preserving alternative to bespoke per-token-kind rules | Apache-2.0 | pattern (no current gap) |

## Examples
No fixture data required (mechanism-only facts).
