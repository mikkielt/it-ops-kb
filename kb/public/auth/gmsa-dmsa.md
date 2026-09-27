---
topic: auth/gmsa-dmsa
priority: P0
applies_to: "Windows Server 2025 (dMSA), extends windows/gmsa.md"
retrieved_utc: 2026-09-27
sources: [S1204, S-bxqr5u5d, S-z73kk7xf, S-mifutdb3, S-ffangyfp]
status: complete
---

# dMSA (Windows Server 2025), extending `windows/gmsa.md`

## Summary
- Delegated Managed Service Accounts (dMSA) are new in Windows Server 2025: migrate a legacy service account to a machine-bound, fully randomized-key account, disabling the old account's password. [DOC S1204]
- Not a drop-in replacement for gMSA for an existing `site`/`ci` service account design: dMSA is aimed at *migrating existing standalone service accounts* onto a managed identity tied to specific machines, and needs a Windows Server 2025 DC plus domain admin rights to set up. [DER S1204, S-bxqr5u5d, S-z73kk7xf]
- For a design that already uses standard gMSA and prefers to avoid exotic dependencies, dMSA is not required now (a gMSA cannot be migrated to a dMSA anyway); record it as an option only if a legacy password-based service account needs migrating later. [DER S1204: design judgement from the migration rules]

## Facts
- gMSA password length and rotation (the baseline this page compares against): gMSA passwords are 240-byte random values that Windows changes every 30 days; Microsoft's Kerberoasting guidance gives them as 120 characters long. [DOC S-mifutdb3, S-ffangyfp]
- dMSA authentication is tied to device identity: only machine identities mapped to the dMSA in AD can access the account; it reuses gMSA concepts to limit where it can be used, and its secret (derived from the machine account credential) is held only on the DC and cannot be retrieved elsewhere. [DOC S1204]
- dMSA needs at least one Windows Server 2025 DC, discoverable by the client or member server; extending the schema alone is not enough. [DOC S-bxqr5u5d]
- Creating or migrating to a dMSA needs membership of Domain Admins or Enterprise Admins, or equivalent AD permissions. [DOC S-z73kk7xf]
- Migration timing: the `groupMSAMembership`/migration state is checked and updated at every Kerberos ticket renewal and at every logon of the original account; sites with replication delay longer than the default ticket renewal window (10 hours) need special care. [DOC S1204]
- Microsoft's guidance: wait at least two ticket lifetimes (about 14 days) after changing the security descriptor before completing migration, and recommends keeping an account in the "start migration" state for about four ticket lifetimes (28 days). [DOC S1204]
- Migration needs a writable DC (RWDC) to query/modify the account's security descriptor. [DOC S1204]
- An MSA or gMSA cannot be migrated to a dMSA, and all machines that use the migrated service account must support dMSA, or they fail authentication once the old account is disabled. [DOC S1204]

## Reference
| Aspect | gMSA (baseline design) | dMSA |
|---|---|---|
| Purpose | New service identity for `site`/`ci` | Migrate an *existing* standalone service account |
| DC requirement | Any DC supporting gMSA (2012+) | At least one Server 2025 DC |
| Key exchange | KDS root key, `Get-ADServiceAccount` | Same KDS mechanism, plus device-mapped retrieval |
| Migration effort | N/A (created fresh) | 2-4 week migration window recommended |

## Examples
- A design can keep its `site`/`ci` service accounts as ordinary gMSA (see `windows/gmsa.md`); dMSA is out of scope unless a legacy account needs migrating.
