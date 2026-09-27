---
topic: reuse/secret-vault-encryption
priority: P2
applies_to: "a per-conversation, short-TTL, encrypted-at-rest, audited-reveal secret vault, and long-lived site secrets committed to a repository"
retrieved_utc: 2026-09-26
sources: [S1000, S1001, S1002, S1003, S1004, S1102, S1103, S-3eg2zeqb, S-wqbnua3h, S-6osxhfhb]
status: complete
---

## Summary
Two different problems hide under "secret vault": (1) a per-conversation, short-TTL, audited-reveal
placeholder vault, and (2) long-lived site secrets committed to a repository (credentials in a
`site.toml`-adjacent file, encrypted). sops+age fit (2) as a pattern; neither sops nor age has a native
TTL (sops only offers an optional per-decrypt audit log to PostgreSQL), so neither is a `dependency`
fit for (1) as-is. `cryptography`'s
`Fernet.decrypt(ttl=...)` is a direct `dependency` fit for the TTL check in (1).

## Facts
- sops (MPL-2.0) edits encrypted YAML, JSON, ENV, INI and binary files, encrypting with AWS KMS, GCP
  KMS, Azure Key Vault, HuaweiCloud KMS, age and PGP. [DOC S1000]
- sops encrypts each value with a per-file data key, stores the data key (encrypted to each master key)
  and a MAC over the values in the file's `sops` metadata, and picks keys per path through
  `creation_rules` in `.sops.yaml`; this fits git-committed, per-path recipient rules for site
  secrets. [DOC S-3eg2zeqb]
- sops can write an audit log entry to a pre-configured PostgreSQL database each time a file is
  decrypted (timestamp, user name, file), configured in `/etc/sops/audit.yaml`. [DOC S-wqbnua3h]
- The sops docs describe no expiry or TTL for encrypted values, so a "reveal fails after N hours" rule
  stays application-level. [DER S-3eg2zeqb: no TTL or expiry setting in the reference or config-file keys]
- age is licensed BSD-3-Clause. [DOC S1001]
- age has no built-in expiry, revocation or audit log (caller responsibility). [UNK: not in S1001 as re-read 2026-09-27]
- Vault 1.15.0 and later is under the Business Source License 1.1 per the repository `LICENSE`, where
  the GitHub API reports "NOASSERTION". [DOC S1102, S1002]
- BUSL-1.1 grants the right to copy, modify, create derivative works, redistribute and make
  non-production use; Vault's Additional Use Grant allows production use except in an offering that
  competes with IBM's paid versions, and each version changes to MPL 2.0 four years after
  publication. [DOC S1102]
- Using Vault's encrypt/decrypt feature means running Vault itself, a new always-on service, which a
  no-always-on-service constraint would forbid. [DER S1002: the README describes applications asking
  Vault for secrets and Vault encrypting and decrypting data on request]
- BUSL-1.1 is not an OSI-approved licence. [UNK: not in S1102 as re-read 2026-09-27]
- Python `cryptography`'s repository `LICENSE` (fetched directly) makes the software available under
  either Apache-2.0 or BSD-3-Clause, with contributions made under both, resolving a prior "UNK (GitHub
  reports NOASSERTION)" flag. [DOC S1103]
- `cryptography.fernet.Fernet.decrypt(token, ttl=seconds)` raises `InvalidToken` when the token is
  older than `ttl` seconds from its creation, so the age check happens at decrypt time -- the "reveal
  fails after N hours" behaviour a short-TTL pseudonymization vault needs, with no scheduler for that
  check. [DOC S-6osxhfhb]
- git-crypt is GPL-3.0 (confirmed licence, unchanged from prior-art fetch), so no code from it may be
  copied into a no-GPL codebase; its transparent per-file git-filter model (identical plaintext ->
  identical ciphertext, via SIV) is also not a fit for a runtime, per-reveal-audited vault. [DOC S1004]

## Reference
| candidate | native TTL | native reveal audit | licence | fits a short-TTL conversation vault as-is |
|---|---|---|---|---|
| sops | no | optional, per-decrypt log to PostgreSQL | MPL-2.0 | no (fits long-lived site secrets instead) |
| age | no | no | BSD-3-Clause | no (same) |
| Vault transit | no (key rotation only) | yes, via audit device | BUSL-1.1 (non-production use; production per Additional Use Grant; also a new service) | no |
| `cryptography` Fernet | yes, `decrypt(ttl=...)` | no (caller logs the call) | Apache-2.0 OR BSD-3-Clause | yes, for the TTL check |
| git-crypt | no | no | GPL-3.0 (no copying) | no |

## Examples
No fixture data required (mechanism-only facts; no project-specific configuration recorded here).
