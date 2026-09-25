---
topic: agents/api-tokens-issue-and-store
priority: P1
applies_to: "GitLab (docs current 2026-09), python keyring 25.7.0, msal-extensions (main branch 2026-09), Azure Key Vault (docs 2025-12), HashiCorp Vault (docs current 2026-09), Claude Code 2.1.x"
retrieved_utc: 2026-09-25
sources: [S449, S740, S1297, S2041, S2043, S2044, S2046, S2047, S2048, S2049, S2054, S2055, S2056, S2057]
status: complete
---

# Issuing and storing API tokens and secrets for agents

Extends, does not repeat, `auth/workload-identity.md` (Entra FIC, Azure Arc managed identity),
`auth/msal-public-client.md` (MSAL Python WAM/CAE), `auth/key-management-options.md` (SQL Always
Encrypted, DPAPI-NG, age/sops) and `mcp/authorization.md` (MCP OAuth 2.1, DCR deprecation, CIMD).

## Summary
- For issuing: OBO and GitLab PATs/project tokens are the two mechanisms this part adds; both vendors'
  own guidance steers *automation* away from long-lived, human-shaped credentials (PATs, static secrets)
  toward workload identity or scoped machine credentials (GitLab CI job tokens; Vault AppRole).
- For storing: every OS-keychain wrapper this part checked (`keyring`, `msal-extensions`) documents its
  own gap — macOS Keychain's per-executable ACL, or a silent unencrypted fallback on Linux — so "stored in
  the OS keychain" is not, by itself, a verified security property without checking which backend actually
  engaged.
- Azure Key Vault and HashiCorp Vault both give the alternative these gaps argue for: an external,
  network-scoped secret store with its own access control, rather than filesystem/OS-keychain storage on
  every workstation.

## Facts

### Issuing
- **OBO** (On-Behalf-Of): exchanges a token issued to a middle-tier API for a downstream-API token,
  preserving the *user's* delegated scopes only ("roles remain attached to the principal... never to the
  application"); works only for user (delegated) tokens, not app-only/service-principal tokens (those use
  client-credentials instead); relaying the middle-tier's own access token onward to the original caller
  is explicitly warned against (interception risk; breaks Conditional Access step-up and device-based
  policy enforcement on the downstream call). [DOC S1297]
- **GitLab personal access tokens (PATs)**: default expiry 365 days; a feature-flagged **400-day maximum**
  shipped in **GitLab 17.6**; admins can set a lower tenant/instance maximum; expire at midnight UTC on
  the expiry date. **Rotation** creates a new token with the same scope and immediately deactivates the
  original; **revocation** immediately invalidates a token; both are irreversible. GitLab's own guidance
  recommends **CI/CD job tokens with fine-grained permissions** over a PAT for pipeline authentication,
  specifically because a PAT is a long-lived, human-owned, broadly-scoped credential unsuited to
  unattended automation. Project/group access tokens attach to the project/group rather than a user
  account, as the documented service-account alternative to a personal PAT. [DOC S2046]
- **General implication**: combined with `auth/workload-identity.md`'s Entra FIC federation (no stored
  secret at all) and a policy that a merge request is the change record and MR code never runs with a
  domain identity, GitLab's own stated preference for job tokens over PATs for automation reinforces that a
  PAT should not be a CI/scheduled-job credential of choice. [DER S2046, auth/workload-identity.md]

### Storing: OS keychains via Python `keyring`
- `keyring` (25.7.0, 2025-11-16, MIT) wraps macOS Keychain, Linux Freedesktop Secret Service (GNOME) /
  KDE KWallet, and Windows Credential Locker, via `set_password`/`get_password`/`delete_password`/
  `get_credential`. [DOC S2043]
- **Documented gap, macOS**: "any Python script or application can access secrets created by keyring from
  that same Python executable without the operating system prompting the user for a password" — the
  Keychain ACL is keyed to the Python interpreter binary, not the calling script, so co-located Python
  processes using the same interpreter can silently read each other's `keyring` secrets unless the user
  manually restricts Python's own Keychain access-control entry. Threat covered: casual/accidental access
  by an unrelated process is *not* prevented by default. [DOC S2043]
- **Documented gap, other backends**: "no analysis has been performed" on the security properties of
  Linux Secret Service, KDE KWallet, or Windows Credential Locker as used by this library — i.e. no
  vendor-asserted threat model for the backends most Windows engineer workstations would use.
  [DOC S2043]

### Storing: MSAL token cache persistence via `msal-extensions`
- Backs onto Windows **DPAPI**, macOS **Keychain**, and Linux **libsecret** encryption with an **explicit
  plaintext fallback**; MIT licence. [DOC S2044]
- **Documented failure mode**: on Linux, when libsecret encryption is unavailable, the library logs
  "Encryption unavailable. Opting in to plain text" and silently stores the token cache **unencrypted**
  rather than failing closed. Threat covered: none, by default, in this fallback state — the caller must
  detect which backend actually engaged. [DOC S2044] The general "unknown is never treated as absent/safe"
  rule applies by analogy: a component reading this cache should treat "plaintext fallback silently
  engaged" as a condition to detect and refuse, not a transparent degrade. [DER S2044]
- Documented scope of intended use: "public client applications such as desktop apps only," explicitly
  cautioned against for web applications ("potential scale and performance issues") — matches a CLI-only
  client case, where a web-facing deployment is out of scope regardless. [DOC S2044]

### Storing: Claude Code's own credential handling (a fourth workstation option)
- Claude Code's own login/API credentials: macOS Keychain, or `~/.claude/.credentials.json` (mode `0600`)
  on Linux/Windows (Windows inherits the user-profile ACL) as the fallback when the Keychain write fails
  (e.g. locked in an SSH session). [DOC S2041]
- `apiKeyHelper`: a configurable shell script returning an API key, re-run on a 5-minute default TTL
  (`CLAUDE_CODE_API_KEY_HELPER_TTL_MS` to change it) — documented explicitly for "dynamic or rotating
  credentials, such as short-lived tokens fetched from a vault," a directly reusable integration point for
  wiring a Vault- or Key-Vault-backed secret into the CLI process without an argv or static-env-var
  credential. [DOC S2041]
- MCP server OAuth tokens (distinct from Claude Code's own login) are stored "securely" in the system
  credential store (macOS Keychain) or a credentials file on other platforms, never in `.mcp.json` /
  `~/.claude.json`, and scoped per MCP server endpoint — authenticating one server does not authenticate
  another. [DOC S740]

### External secret stores: Azure Key Vault and HashiCorp Vault
- **Azure Key Vault**: authentication via Microsoft Entra ID; authorization via **Azure RBAC** (covers
  both vault management and data access) or the older **access-policy** model (data access only);
  Standard tier = FIPS 140 Level 1 software crypto, Premium tier = FIPS 140-3 Level 3 HSM-protected keys;
  Microsoft states "Key Vault is designed so that Microsoft doesn't see or extract your data." [DOC S2047]
  Threat covered: a single machine-local secret (e.g. a CMK certificate) needing replication to every
  workstation that decrypts it — Key Vault centralizes that instead, matching the gap already flagged in
  `auth/key-management-options.md`. [DER S2047, auth/key-management-options.md]
- **HashiCorp Vault**: "centralized, well-audited privileged access and secret management" for
  credentials, encryption keys, authentication certificates, across on-prem/cloud/hybrid. [DOC S2048]
- **Vault AppRole** auth method: two-part credential — `RoleID` (stable, low-sensitivity role selector)
  plus `SecretID` (the actual secret, with configurable `secret_id_ttl` e.g. 10 minutes and
  `secret_id_num_uses` e.g. 40 uses) — documented as "oriented to automated workflows (machines and
  services)... less useful for human operators." **Pull mode** (Vault generates the `SecretID`
  server-side) is preferred over **Push mode** (caller supplies its own value) "in most cases"; Vault's
  own guidance recommends short-lived **batch tokens** with AppRole. Threat covered: a long-lived static
  credential handed to a CI job or service — AppRole bounds both the credential's lifetime and its use
  count instead. [DOC S2049]
- Vault's dynamic-secrets/database-secrets-engine mechanics (e.g. for a rotating SQL Server credential)
  were not fetched in this pass. [UNK, see gaps.md]

### GitLab CI/CD variables: a leakage path a secrets-declaration policy has to guard against
- "Masking a CI/CD variable is not a guaranteed way to prevent malicious users from accessing variable
  values"; variables "could be accidentally exposed in a job log, or maliciously sent to a third-party
  server." GitLab's own mitigation is reviewing every `.gitlab-ci.yml` change before merge (especially
  from forks); its own stated alternative is to "connect with an external secrets management provider to
  store and retrieve secrets" rather than hold the raw secret as a CI variable. **Protected variables**
  restrict a variable to pipelines on protected branches/tags only. [DOC S449]
- Applied to a "secrets never on argv, in a child process's environment, or in output" policy: a GitLab
  CI variable is, by default, exactly a child-process environment variable every job step inherits — the
  concrete mechanism that policy has to override, not merely a hypothetical. A `headersHelper`-style
  callback or a file-path secret avoids inheriting it as plain environment state. [DER S449]

### Deepening: Vault dynamic secrets (closing the prior gap)
- **Vault's database secrets engine** generates unique database credentials per request via a plugin
  interface rather than sharing one static password across services; default **1-hour TTL, 24-hour max
  TTL** (adjustable per role). Vault's stated reasoning: "every service is accessing the database with
  unique credentials, it makes auditing much easier when questionable data access is discovered."
  Credentials are revoked automatically at lease expiry by Vault's own internal revocation system, or
  renewed before expiry. Supports 20+ database engines (PostgreSQL, MySQL/MariaDB, MSSQL, Oracle,
  MongoDB, Cassandra, Redis, Snowflake, etc.); root-credential rotation is available for all supported
  plugins except MongoDB Atlas. Static roles instead offer a 1-to-1 mapping with scheduled, cron-style
  password rotation and a configurable password policy (default: 20 characters, mixed case, numbers,
  special characters). [DOC S2054]
- **General implication**: for a design that makes SQL Server the identity/assignment store with long
  temporal history, a scheduled sync job's write identity into that store (under a policy that "shared
  state is written only by scheduled sync jobs under read-only identities") could, as a future design
  option, be a Vault-issued dynamic MSSQL credential on a short TTL rather than a static service-account
  password — stated here as a documented capability, not a recommendation. [DER S2054]

### Deepening: GitLab's native secrets integration (closing the prior gap)
- **`docs.gitlab.com/ci/secrets/`** documents GitLab's own external-secrets integration, supporting four
  providers natively: **HashiCorp Vault, Google Cloud Secret Manager, Azure Key Vault, AWS Secrets
  Manager** — authenticated via GitLab's own **`id_tokens`** (OIDC JWTs), the same mechanism
  `auth/workload-identity.md` documents for Entra FIC federation; a job can also authenticate manually
  to any other OIDC-compliant provider. [DOC S2055]
- The documented operational difference from an ordinary CI/CD variable: "secrets must be explicitly
  requested by a job," fetched at run time, versus a CI/CD variable which is "always available in jobs"
  and injected into every job's environment by default whether that job needs it or not. GitLab's docs do
  not explicitly rank this as more secure than a masked/protected variable, but the on-demand model
  structurally narrows which jobs a given secret's value ever reaches — a concrete GitLab-native
  alternative to the CI/CD-variable leakage path this file already documents from S449. [DOC S2055, DER
  against S449]
- **Vault's JWT/OIDC auth method** is the mechanism a GitLab `id_tokens` JWT would present against a
  self-hosted Vault: a role configured with `bound_audiences` (must exactly match the JWT's `aud` claim)
  and optional `bound_claims` (arbitrary claim/value matching, e.g. restricting by GitLab project path or
  ref), then `vault write auth/jwt/login role=<name> jwt=<token>` exchanges the JWT for a Vault token
  scoped to that role's policies and TTL. [DOC S2056] Combined with a "one job per runner and trigger"
  policy and "MR code never runs with a domain identity," this is a concrete non-PAT, non-static-secret
  path for a protected scheduled job to reach Vault-issued dynamic secrets. [DER S2056]

### Deepening: Claude Code `apiKeyHelper` hot-reload behaviour
- Claude Code's settings system reloads `apiKeyHelper` (and other credential helpers, alongside
  `permissions` and `hooks`) into a **running session without a restart**: "Claude Code watches your
  settings files and reloads them when they change, so it applies most edits to the running session
  without a restart, including edits to... credential helpers such as `apiKeyHelper`." Practically, a
  Vault- or Key-Vault-driven rotation of the secret an `apiKeyHelper` script reads reaches a running
  CLI process on the helper's own TTL (`CLAUDE_CODE_API_KEY_HELPER_TTL_MS`, default 5 minutes)
  without needing the operator to restart the CLI — closing the gap between "external store rotates a
  credential" and "the running process picks it up," with no static value stored at any point in between.
  [DOC S2057] `managed-settings.json` (S2042, `agent-rbac.md`) sits above project/user settings in
  precedence and can pin or forbid a project's own `apiKeyHelper` value organization-wide.

## Reference: each option's threat and what it does not cover
| Option | What it protects against | What it does not cover | Source |
|---|---|---|---|
| Python `keyring` (macOS backend) | secret not in a plaintext file | any process under the *same Python interpreter* reading it without a prompt | S2043 |
| Python `keyring` (Linux/Windows backends) | OS-native storage used | no vendor-asserted threat model published for these backends | S2043 |
| `msal-extensions` (Windows/macOS) | DPAPI/Keychain-encrypted cache | n/a (documented, working case) | S2044 |
| `msal-extensions` (Linux, libsecret unavailable) | nothing — silent plaintext fallback | detecting the fallback is the caller's job | S2044 |
| Azure Key Vault | one centralized, RBAC-scoped, HSM-backed store instead of per-machine secrets | still needs a workload identity (FIC/managed identity) to authenticate to it | S2047 |
| GitLab CI/CD protected + masked variables | exposure on unprotected branches; casual log display | not a guarantee against a malicious job's own printing of the value | S449 |
| GitLab job tokens (vs PAT) | a long-lived, human-scoped credential used by automation | scope/lifetime details for the fine-grained job-token model itself | S2046 |
| HashiCorp Vault AppRole | a static, unbounded machine credential | dynamic secrets specifics for a project's own backends — [UNK] | S2049 |
| Claude Code `apiKeyHelper` | a static API key on the CLI's own credential path | the script's own storage of what it fetches (delegates back to one of the above) | S2041 |

## Examples
- A CI role in GitLab: authenticates via Entra FIC (no stored secret, `auth/workload-identity.md`)
  rather than a project access token; any short-lived value the pipeline still needs (e.g. a versioned
  content artifact's signing material) would be pulled through a masked, protected CI variable only as a
  last resort, per the GitLab guidance above, with an external secrets provider preferred.
- A client on `PL-LT-00123`: an MSAL token cache persisted via `msal-extensions`, backed by Windows
  DPAPI (the documented, working case, not the Linux plaintext-fallback path).

## Open items
- QG27: OBO and GitLab PAT/project-token issuance, lifetimes, rotation, revocation — answered above; a
  full lifetime/rotation/revocation/audit/storage table for every credential kind in this part is now
  `agents/api-tokens.csv`.
- QG28: OS keychains via `keyring`, `msal-extensions`, Key Vault, GitLab CI variables and native secrets
  integration, HashiCorp Vault (AppRole and dynamic database secrets), Claude Code `apiKeyHelper`'s
  hot-reload behaviour, and a general "secrets never on argv/env/output, and secrets readable only from a
  file path" policy — answered above and in `agents/secret-storage-options.csv` (one row per option, threat covered, gap not covered). Vault's generic 1h/24h TTL default
  is confirmed for a future SQL Server credential; an MSSQL-specific worked example was not fetched
  (narrowed, not blocking — see gaps.md).
