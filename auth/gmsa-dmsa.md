---
topic: auth/gmsa-dmsa
priority: P0
applies_to: "Windows Server 2025 (dMSA), extends windows/gmsa.md"
retrieved_utc: 2026-09-26
sources: [S1204]
status: partial
---

# dMSA (Windows Server 2025), extending `windows/gmsa.md`

## Summary
- Delegated Managed Service Accounts (dMSA) are new in Windows Server 2025: migrate a legacy service account to a machine-bound, fully randomized-key account, disabling the old account's password. [DOC S1204]
- Not a drop-in replacement for gMSA for an existing `site`/`ci` service account design: dMSA is aimed at *migrating existing standalone service accounts* onto a managed identity tied to specific machines, and needs a Windows Server 2025 DC plus domain admin rights to set up.
- For a design that already uses standard gMSA and prefers to avoid exotic dependencies, dMSA is not required now; record it as an option only if a legacy password-based service account needs migrating later.

## Facts
- dMSA authentication is tied to device identity: only machine identities mapped to the dMSA in AD can retrieve/use it, similar to gMSA's `PrincipalsAllowedToRetrieveManagedPassword` but built for account migration scenarios. [DOC S1204]
- Requires at least one Windows Server 2025 domain controller in the domain and domain admin rights to configure. [DOC S1204]
- Migration timing: the `groupMSAMembership`/migration state is checked and updated at every Kerberos ticket renewal and at every logon of the original account; sites with replication delay longer than the default ticket renewal window (10 hours) need special care. [DOC S1204]
- Microsoft's guidance: wait at least two ticket lifetimes (about 14 days) after changing the security descriptor before completing migration, and recommends keeping an account in the "start migration" state for about four ticket lifetimes (28 days). [DOC S1204]
- Migration needs a writable DC (RWDC) to query/modify the account's security descriptor. [DOC S1204]

## Reference
| Aspect | gMSA (baseline design) | dMSA |
|---|---|---|
| Purpose | New service identity for `site`/`ci` | Migrate an *existing* standalone service account |
| DC requirement | Any DC supporting gMSA (2012+) | At least one Server 2025 DC |
| Key exchange | KDS root key, `Get-ADServiceAccount` | Same KDS mechanism, plus device-mapped retrieval |
| Migration effort | N/A (created fresh) | 2-4 week migration window recommended |

## Examples
- A design can keep its `site`/`ci` service accounts as ordinary gMSA (see `windows/gmsa.md`); dMSA is out of scope unless a legacy account needs migrating.
