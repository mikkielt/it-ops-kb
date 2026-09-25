---
topic: reuse/secret-vault-encryption
priority: P2
applies_to: "a per-conversation, short-TTL, encrypted-at-rest, audited-reveal secret vault, and long-lived site secrets committed to a repository"
retrieved_utc: 2026-09-24
sources: [S1000, S1001, S1002, S1003, S1004, S1102, S1103]
status: complete
---

## Summary
Two different problems hide under "secret vault": (1) a per-conversation, short-TTL, audited-reveal
placeholder vault, and (2) long-lived site secrets committed to a repository (credentials in a
`site.toml`-adjacent file, encrypted). sops+age fit (2) as a pattern; neither sops nor age has a native
TTL or reveal audit, so neither is a `dependency` fit for (1) as-is. `cryptography`'s
`Fernet.decrypt(ttl=...)` is a direct `dependency` fit for the TTL check in (1).

## Facts
- sops encrypts file values against KMS/PGP/age recipients and records recipients + MAC in the same
  file (`.sops.yaml` `creation_rules`); this matches a need for git-committed, per-path recipient rules
  for site secrets, but sops has no concept of a TTL or a per-reveal audit event -- those stay
  application-level. [DOC S1000]
- age has no built-in expiry, revocation or audit log (caller responsibility), confirmed by its own
  docs; licence BSD-3-Clause. [DOC S1001]
- HashiCorp Vault's `transit` engine is licensed BUSL-1.1 (confirmed by direct fetch of the repository
  `LICENSE`, superseding the GitHub API's "NOASSERTION"); BUSL-1.1 is not OSI-approved and does not
  permit copying the source. Running Vault itself would also add a new always-on service, which a
  no-always-on-service constraint would forbid. [DOC S1002,S1102]
- Python `cryptography`'s repository `LICENSE` (fetched directly) confirms dual licensing under
  Apache-2.0 OR BSD-3-Clause (contributions under both), resolving a prior "UNK (GitHub reports
  NOASSERTION)" flag; both licences permit use/copying with attribution. [DOC S1103]
- `cryptography.fernet.Fernet.decrypt(token, ttl=seconds)` rejects a token older than `ttl` seconds at
  decrypt time -- this is exactly the "reveal fails after N hours" behaviour a short-TTL pseudonymization
  vault needs, with no external scheduler or cleanup job required. [DOC S1003]
- git-crypt is GPL-3.0 (confirmed licence, unchanged from prior-art fetch), so no code from it may be
  copied into a no-GPL codebase; its transparent per-file git-filter model (identical plaintext ->
  identical ciphertext, via SIV) is also not a fit for a runtime, per-reveal-audited vault. [DOC S1004]

## Reference
| candidate | native TTL | native reveal audit | licence | fits a short-TTL conversation vault as-is |
|---|---|---|---|---|
| sops | no | no | MPL-2.0 | no (fits long-lived site secrets instead) |
| age | no | no | BSD-3-Clause | no (same) |
| Vault transit | no (key rotation only) | yes, via audit device | BUSL-1.1 (no copying; also a new service) | no |
| `cryptography` Fernet | yes, `decrypt(ttl=...)` | no (caller logs the call) | Apache-2.0 OR BSD-3-Clause | yes, for the TTL check |
| git-crypt | no | no | GPL-3.0 (no copying) | no |

## Examples
No fixture data required (mechanism-only facts; no project-specific configuration recorded here).
