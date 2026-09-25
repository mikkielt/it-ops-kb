---
topic: prior-art/secret-vault-encryption
priority: P2
applies_to: "a placeholder vault (per-conversation, short TTL, encrypted values, audited reveal)"
retrieved_utc: 2026-09-24
sources: [S1000, S1001, S1002, S1003, S1004]
status: complete
---

## Summary
Five established projects each solve "encrypt secrets at rest, control who/what can decrypt": sops
(file-level envelope encryption via KMS/PGP/age), age (small modern recipient-based encryption tool
and Go/Python library), HashiCorp Vault's `transit` secrets engine (encryption-as-a-service, no
storage), Python `cryptography`'s Fernet/AES-GCM (library primitives for encrypt-at-rest in an
app's own store), and git-crypt (transparent per-file git encryption via GPG or a symmetric key).
None of them natively implements a TTL-bound, per-conversation, audited-reveal vault; that composition
is application-level in every case.

## Facts
- sops encrypts YAML/JSON/ENV/INI/BINARY documents value-by-value (or whole-file for BINARY) against
  one or more configured key sources — AWS KMS, GCP KMS, Azure Key Vault, HashiCorp Vault, PGP, or
  age — and stores the encrypted values plus a `sops` metadata block (MAC, key list) in the same file. [DOC S1000]
- sops key/path routing (which recipients encrypt which files) is declared in `.sops.yaml` via
  `creation_rules` matching file paths to `pgp`/`age`/`kms` key lists; `sops updatekeys` re-encrypts a
  file's data key for a changed recipient list without touching the encrypted values. [DOC S1000]
- age encrypts to one or more recipients given as `-r` (public key string, e.g. `age1...`) or `-R`
  (file of recipients), or symmetrically via `--passphrase`; decryption requires the matching identity
  file passed with `-i`, and age has no built-in expiry, revocation or audit log — those are the
  caller's responsibility. [DOC S1001]
- HashiCorp Vault's `transit` engine performs encrypt/decrypt/rewrap/datakey operations through a
  named key held only inside Vault; callers never receive the raw key, only ciphertext, so "at rest"
  storage of the ciphertext can live anywhere (the caller's own DB). Vault records every transit
  operation in its audit log (request path, requesting identity, not the plaintext) when an audit
  device is enabled. [DOC S1002]
- Vault license: since v1.11 (2022) most of Vault's source, including current releases, ships under
  the Business Source License (BUSL-1.1), not an OSI-approved open-source licence; the GitHub API
  reports the repository licence as unrecognised ("NOASSERTION") for this reason. [DOC S1002]
- Python `cryptography`'s `Fernet` class implements symmetric AES-128-CBC + HMAC-SHA256 with a
  URL-safe base64 token that embeds a timestamp; `Fernet.decrypt(token, ttl=seconds)` rejects tokens
  older than the given TTL, giving a library-level expiry check without any external scheduler.
  `AESGCM` in the same package exposes raw AEAD encrypt/decrypt for callers who manage their own
  nonce and associated data. [DOC S1003]
- git-crypt transparently encrypts files matching `.gitattributes` `filter=git-crypt` rules using
  AES-256 in CTR mode with a synthetic IV (SIV: HMAC-SHA256 of the plaintext), so identical plaintext
  always encrypts to identical ciphertext (enables `git diff`/deduplication) at the cost of not being
  semantically secure against equality checks; keys are distributed either as a raw symmetric key
  file or GPG-encrypted per-collaborator via `git-crypt add-gpg-user`. [DOC S1004]
- None of the five projects has a native "reveal" audit trail scoped to a single reveal event with an
  actor and reason; Vault's audit log is the closest built-in mechanism (every `transit/decrypt` call
  is a distinct, attributable log line when audit logging is enabled). [DER S1002]

## Reference
| project | mechanism | key custody | built-in TTL/expiry | built-in reveal audit |
|---|---|---|---|---|
| sops | envelope-encrypt file values | external KMS/PGP/age | no | no |
| age | recipient/passphrase encryption | recipient's private key / passphrase | no | no |
| Vault transit | encryption-as-a-service | inside Vault, never leaves | no (key itself can be rotated/deleted) | yes, via Vault audit device |
| cryptography Fernet | symmetric AEAD token | caller-held key | yes, `decrypt(ttl=...)` | no |
| git-crypt | transparent per-file git filter | GPG per-collaborator or shared key | no | no |

## Examples
No fixture data required (mechanism-only facts; no project-specific configuration recorded here).
