---
topic: prior-art/secret-vault-encryption
priority: P2
applies_to: "a placeholder vault (per-conversation, short TTL, encrypted values, audited reveal)"
retrieved_utc: 2026-09-28
sources: [S1000, S1001, S1002, S1003, S1004, S-r3t6wvk5, S-rirjtdlh, S-nijzofsq, S-b43o3ma3, S-6osxhfhb, S-yr2b636y, S-f4s2xnfz]
status: complete
---

## Summary
Five established projects each solve "encrypt secrets at rest, control who/what can decrypt": sops
(file-level envelope encryption via KMS/PGP/age), age (small modern recipient-based encryption tool
and Go library), HashiCorp Vault's `transit` secrets engine (encryption-as-a-service, no
storage), Python `cryptography`'s Fernet/AES-GCM (library primitives for encrypt-at-rest in an
app's own store), and git-crypt (transparent per-file git encryption via GPG or a symmetric key).
None of them natively implements a TTL-bound, per-conversation, audited-reveal vault; that composition
is application-level in every case.

## Facts
- sops encrypts YAML/JSON/ENV/INI documents value by value (a BINARY file is read as bytes, encrypted, and
  stored base64-encoded under `data` in a JSON file) against one or more key sources — AWS KMS, GCP KMS,
  Azure Key Vault, HuaweiCloud KMS, HashiCorp Vault transit, PGP, or age — and stores the encrypted data
  keys and a MAC over all values in a `sops` metadata block in the same file. [DOC S-r3t6wvk5]
- sops key/path routing (which recipients encrypt which files) is declared in `.sops.yaml` via
  `creation_rules` matching file paths (`path_regex`) to `pgp`/`age`/`kms`/`hc_vault_transit_uri` key
  lists; `sops updatekeys` applies a changed recipient list to an encrypted file without rotating the data
  key (`sops rotate` generates a new data key and re-encrypts all values). [DOC S-r3t6wvk5]
- sops can optionally write an audit record to a pre-configured PostgreSQL database each time a file is
  decrypted (timestamp, the user sops runs as, and the file); the configuration lives at the fixed path
  `/etc/sops/audit.yaml`. [DOC S-r3t6wvk5]
- age encrypts to one or more recipients given with `-r` (an `age1...` public key or an SSH public key)
  or `-R` (a file of recipients), or with a passphrase via `-p`/`--passphrase`; recipient-encrypted files
  are decrypted with identity files passed with `-i`. [DOC S1001]
- age has no built-in expiry, revocation or audit log; those are the caller's responsibility. The age format specification defines only a header (version line, recipient stanzas that each wrap the file key, header MAC) and an encrypted payload. [DER S-f4s2xnfz: no field for expiry, revocation or audit in the format]
- HashiCorp Vault's `transit` engine performs encrypt/decrypt/rewrap/datakey operations with a named key
  managed inside Vault; Vault does not store the data sent to it, so the caller stores the ciphertext in
  its own data store (for example its database) and sends it back to Vault to decrypt. [DOC S-rirjtdlh, S1002]
- Vault audit devices record every API request and response; auditing is disabled on a new cluster until
  an audit device is enabled, and by default most string values are written only as an HMAC-SHA256 keyed
  hash. [DOC S-nijzofsq]
- Vault licence: the repository `LICENSE` is the Business Source License 1.1 (BUSL-1.1) for Vault 1.15.0
  and later, not an OSI-approved open-source licence; the GitHub API reports the repository licence as
  unrecognised ("NOASSERTION"). [DOC S-b43o3ma3, S1002]
- Python `cryptography`'s `Fernet` recipe uses AES-128 in CBC mode with PKCS7 padding plus HMAC-SHA256;
  a token is URL-safe base64 and carries its creation time in plaintext; `Fernet.decrypt(token, ttl=seconds)`
  rejects tokens older than the given TTL, a library-level expiry check without any external scheduler.
  `AESGCM` in the same package exposes AEAD encrypt/decrypt for callers who manage their own nonce and
  associated data. [DOC S-6osxhfhb, S-yr2b636y]
- Repository metadata: sops (`getsops/sops`) is MPL-2.0 and written in Go; Python `cryptography`
  (`pyca/cryptography`) describes itself as exposing cryptographic primitives and recipes to Python
  developers, and the GitHub API reports its licence as unrecognised ("NOASSERTION"). [DOC S1000, S1003]
- git-crypt transparently encrypts files matching `.gitattributes` `filter=git-crypt` rules using
  AES-256 in CTR mode with a synthetic IV derived from the SHA-1 HMAC of the file; the encryption is
  deterministic (so git can tell whether a file changed) and leaks only whether two files are identical;
  keys are shared either as an exported symmetric key file (`git-crypt export-key`) or GPG-encrypted
  per collaborator via `git-crypt add-gpg-user`. [DOC S1004]
- None of the five projects records a reason with a reveal event: Vault's audit devices log each
  `transit/decrypt` request as its own entry, and sops can log each file decryption with the user, but
  neither captures why the value was revealed. [DER S-nijzofsq, S-r3t6wvk5: the audit fields each page lists include no reason]

## Reference
| project | mechanism | key custody | built-in TTL/expiry | built-in reveal audit |
|---|---|---|---|---|
| sops | envelope-encrypt file values | external KMS/PGP/age/Vault transit | no | optional decrypt log to PostgreSQL (timestamp, user, file) |
| age | recipient/passphrase encryption | recipient's private key / passphrase | no | no |
| Vault transit | encryption-as-a-service | inside Vault | no (key itself can be rotated/deleted) | yes, via Vault audit device |
| cryptography Fernet | symmetric authenticated token | caller-held key | yes, `decrypt(ttl=...)` | no |
| git-crypt | transparent per-file git filter | GPG per-collaborator or shared key | no | no |

## Examples
No fixture data required (mechanism-only facts; no project-specific configuration recorded here).
