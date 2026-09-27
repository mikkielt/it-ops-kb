---
topic: ad/computer-attributes
priority: P1
applies_to: "Active Directory schema (Windows 2000 Server - Windows Server 2012+ pages, ms.date 05/31/2018)"
retrieved_utc: 2026-09-26
sources: [S560, S561, S562, S563, S564, S565, S566, S549, S552, S548]
status: complete
---

# AD computer attributes used for identity linking

## Summary
- `computer-attributes.csv`: schema facts (attribute id, schemaIDGUID, syntax, indexed, GC, single-valued) for `objectGUID`, `objectSid`, `lastLogonTimestamp`, `msDS-LogonTimeSyncInterval`, `dNSHostName`, `userCertificate`.
- `objectGUID` is 16 bytes, system-set at creation, never changes, indexed and in the GC.
- `lastLogonTimestamp` replicates only when older than now minus `msDS-LogonTimeSyncInterval` (days); initial update ~14 days minus up to 5 days random.

## Facts
- `objectGUID`: unique identifier for an object; 16 bytes; set by the system when the object is created and cannot be changed; system-only; indexed; in global catalog. [DOC S560]
- `objectSid`: binary SID of the security principal; set by the system when the account is created; indexed; in GC; range 0-28. [DOC S561]
- `lastLogonTimestamp`: large integer, 100-ns intervals since 1601-01-01 UTC; updated at logon only if older than `current_time - msDS-LogonTimeSyncInterval`; indexed and in GC from Windows Server 2008 on (neither in Windows Server 2003 / 2003 R2). [DOC S562]
- The first update after raising the domain functional level is 14 days minus a random percentage of 5 days. [DOC S562]
- `msDS-LogonTimeSyncInterval` sets, in days, how finely the last logon time in `lastLogonTimestamp` is replicated to all DCs in a domain; it is a domain-wide policy value. [DOC S563]
- `lastLogonTimestamp` lists class User; the computer class is a subclass of User. [DOC S562,S566]
- `dNSHostName`: computer name as registered in DNS; each label up to 63 chars, whole name up to 255; in GC; not indexed. [DOC S564]
- `userCertificate`: multi-valued DER-encoded X.509v3 certificates; in GC. [DOC S565]
- In a managed (non-federated) environment, the hybrid-join task writes a self-signed certificate to the computer's `userCertificate` over LDAP. [DOC S548]
- Entra Connect 1.4.xx.x syncs only Windows 10 computers carrying a hybrid-join `userCertificate`, recognised by a subject of `CN={ObjectGUID}`. [DOC S552]
- Entra Connect syncs computer `objectGUID` (as deviceID), `objectSID` (as onPremisesSecurityIdentifier), `operatingSystem`, `operatingSystemVersion`, `userCertificate`, `displayName`, `accountEnabled`. [DOC S549]
- The default value of `msDS-LogonTimeSyncInterval` when unset is not stated on the schema page. [UNK]

## Reference
- `computer-attributes.csv` (this directory).

## Examples
- `Get-ADComputer PL-LT-00123 -Properties objectGUID,objectSid,lastLogonTimestamp,dNSHostName,userCertificate` in `corp.example.com`.
