---
topic: ad/fsmo-roles
priority: P2
applies_to: "Active Directory Domain Services (all supported Windows Server versions); ActiveDirectory PowerShell module (Move-ADDirectoryServerOperationMasterRole); Ntdsutil.exe"
retrieved_utc: 2026-10-12
sources: [S-qbxv7o56, S-hnfdk22k, S-3ya57dju, S-uyoeu33z]
status: complete
---

# FSMO (operations master) roles: placement, transfer and seizure

## Summary
- Five FSMO (flexible single master operations, also called operations master) roles exist: **schema master** and **domain naming master** once per forest, **PDC emulator**, **RID master** and **infrastructure master** once per domain.
- To move FSMO roles with PowerShell, run `Move-ADDirectoryServerOperationMasterRole` from any domain-joined computer that has the ActiveDirectory module: `-Identity` is the domain controller that receives the roles, `-OperationMasterRole` lists them. This is a **transfer**, the recommended option, and needs the current holder online.
- To **seize** with the same cmdlet, repeat the command with `-Force`; it still tries a graceful transfer first and seizes only when the transfer is not possible. `Ntdsutil.exe` does the same with `roles` / `transfer <role>` / `seize <role>`.
- Transfer when the current holder is reachable (graceful demotion, planned maintenance). Seize only when the holder is failed or gone for good and cannot transfer; a former holder that returns is rebuilt, not restored from backup.
- A seized RID master costs RID space: the cmdlet raises the next RID pool by 30,000 and Ntdsutil by 10,000, so seize it only when the old holder cannot come back.
- A new holder (after transfer or seizure) does not act at once: it waits for one successful inbound replication cycle of the role's naming context.

## Facts
- Five FSMO roles exist: schema master, domain naming master, RID master, PDC emulator and infrastructure master; the first two are forest-level roles (one per forest) and the last three are domain-level roles (one per domain). [DOC S-3ya57dju]
- The schema master governs changes to the schema naming context, and there is only one schema master in an AD DS forest. The domain naming master adds and removes domain and application directory partitions and keeps domain names unique in the forest. [DOC S-3ya57dju]
- The RID master allocates RID pools to domain controllers so new security principals get unique SIDs. The PDC emulator receives preferential replication of password changes, processes account lockouts, and in the forest root domain is the authoritative W32time source for the forest. [DOC S-3ya57dju]
- The infrastructure master manages references from objects in its domain to objects in other domains. [DOC S-3ya57dju]
- When a forest is created, all five roles go to the first domain controller of the forest root domain; creating a child or tree domain assigns the three domain-wide roles to that domain's first domain controller. [DOC S-hnfdk22k]
- The ActiveDirectory PowerShell cmdlet `Move-ADDirectoryServerOperationMasterRole` transfers or seizes FSMO roles by moving one or more operation master roles to another domain controller, the directory server given by `-Identity`; `-OperationMasterRole` accepts `PDCEmulator`, `RIDMaster`, `InfrastructureMaster`, `SchemaMaster` and `DomainNamingMaster` (or 0 to 4), as a comma-separated list. [DOC S-qbxv7o56]
- The cmdlet offers two options: role **transfer**, described as the recommended option, and role **seizure**, which runs the cmdlet a second time with the same parameters plus `-Force`; `-Force` marks a seize, and the operation still attempts a graceful transfer first, then seizes if transfer is not possible. [DOC S-qbxv7o56]
- Unlike Ntdsutil, the cmdlet can be run remotely from any domain-joined computer with the Active Directory module, so neither the transfer nor the seizure has to be started locally on a role holder. [DOC S-qbxv7o56]
- Known issue: the cmdlet fails when a fully qualified domain name is given directly as `-Identity`; get the object first with `Get-ADDomainController` and pass that object. [DOC S-qbxv7o56]
- The cmdlet does not work with an Active Directory snapshot or with a read-only domain controller; it supports `-WhatIf`, `-Confirm`, `-Credential` and `-PassThru`, and returns nothing by default. [DOC S-qbxv7o56]
- Transfer when the current holder is operational and reachable by the new owner, when gracefully demoting a role-holding domain controller, or when the holder goes offline for scheduled maintenance (most important for the PDC emulator). [DOC S-hnfdk22k]
- Seize when the holder has an operational error that prevents a role-dependent operation and the role cannot be transferred, when the holder was force-demoted (`Uninstall-ADDSDomainController -ForceRemoval` or `dcpromo /forceremoval`, which can leave roles in an invalid state), or when the original holder's operating system no longer exists or was reinstalled. [DOC S-hnfdk22k]
- Microsoft recommends seizing all roles only when the previous role holder is not returning to the domain. [DOC S-hnfdk22k]
- Seizing the RID master increments the next available RID in the pool to avoid duplicate SIDs, which can consume RID ranges quickly ("RID burn"): the cmdlet increases the next RID pool by 30,000 from what it finds in Active Directory, and `Ntdsutil.exe` with the `roles` commands by 10,000. [DOC S-hnfdk22k]
- A restarted or newly assigned role holder first waits for inbound replication of the role's naming context (the domain partition for the three domain roles, the schema or configuration partition for the forest roles) before it acts; one that learns another domain controller holds the role relinquishes it. [DOC S-hnfdk22k]
- The best candidate for a new role holder is in the same domain as the previous holder and has the most recent replicated writable copy of the role's partition; for the schema master that is a domain controller in the forest root domain, preferably in the same site as the current holder. [DOC S-hnfdk22k]
- Ntdsutil path: sign in to a DC (or RSAT member), run `ntdsutil`, then `roles`, `connections`, `connect to server <new holder>`, `q`, and then `transfer <role>` or `seize <role>`; the syntax exceptions are `seize pdc` and `seize naming master`, and `seize rid master`, `seize schema master`, `seize infrastructure master` follow the role names. [DOC S-hnfdk22k, S-uyoeu33z]
- Credentials for the Ntdsutil path: Enterprise Admins for the schema master and domain naming master, Domain Admins of the domain for the PDC emulator, RID master and infrastructure master. The forest-recovery seize table lists Schema Admins (not Enterprise Admins) for seizing the schema master; the pages differ. [DOC S-hnfdk22k, S-uyoeu33z]
- After a seizure, Ntdsutil lists each role with the LDAP name of the server that now holds it, and `netdom query fsmo` from an elevated prompt verifies the current role holders. [DOC S-uyoeu33z]
- If the computer seizing the RID master was not the RID master before, it tries to synchronize with a replication partner first; when it is isolated this fails, and the dialog asking whether to continue is answered Yes. [DOC S-uyoeu33z]
- After seizing the infrastructure master, a later `Adprep /Rodcprep` may report an error (the forest-recovery page points to KB 949257). [DOC S-uyoeu33z]
- After a seizure the previous holder should be repaired only if roles were transferred; otherwise rebuild it from scratch (format and reinstall, or force-demote) and clean its metadata with Ntdsutil from another DC before repromoting. A restore from backup would bring it back as a role holder. [DOC S-hnfdk22k]
- In isolated replication islands, duplicate schema masters, domain naming masters and RID masters can create conflicting objects, domains or RID pools and must be reduced to one each before reconnecting; duplicate PDC emulators and infrastructure masters cause no long-term issue. [DOC S-hnfdk22k]
- The infrastructure master has no work when every domain controller in the domain is a global catalog or the AD Recycle Bin is enabled, but the role should still point at a valid domain controller to avoid monitoring errors; if still needed it must not sit on a global catalog server. [DOC S-hnfdk22k]
- Placement guidelines: keep the forest-level roles together on a domain controller in the forest root domain, put the domain-level roles on a high-performance domain controller, name another DC as standby holder for each group, and place role holders where network reliability is high; the PDC emulator has the highest performance impact of the five. [DOC S-3ya57dju]
- Agent handling: a plain transfer is reversible (run it again towards the old holder), a seizure is not; run the transfer first, treat its failure as the signal to ask for approval, and add `-Force` only on that approval, using `-WhatIf` to show the target first. [DER S-qbxv7o56, S-hnfdk22k]

## Reference
| Role | Scope | Naming context | Ntdsutil seize command | Cmdlet `-OperationMasterRole` value |
|---|---|---|---|---|
| Schema master | Forest | `CN=Schema,CN=Configuration,DC=<forest root>` | `seize schema master` | `SchemaMaster` |
| Domain naming master | Forest | `CN=Configuration,DC=<forest root>` | `seize naming master` | `DomainNamingMaster` |
| PDC emulator | Domain | `DC=<domain>` | `seize pdc` | `PDCEmulator` |
| RID master | Domain | `DC=<domain>` | `seize rid master` | `RIDMaster` |
| Infrastructure master | Domain | `DC=<domain>` | `seize infrastructure master` | `InfrastructureMaster` |

| Fact | Value | Source |
|---|---|---|
| RID pool bump on seizure | +30,000 (cmdlet), +10,000 (Ntdsutil `roles`) | S-hnfdk22k |
| Transfer vs seize switch in the cmdlet | `-Force` | S-qbxv7o56 |
| Verify holders | `netdom query fsmo` | S-uyoeu33z |
| Duplicate holders harmful | schema, domain naming, RID | S-hnfdk22k |
| Duplicate holders harmless | PDC emulator, infrastructure | S-hnfdk22k |

## Examples
- Transfer the PDC emulator and RID master to `PL-SRV-0042` from any management host with the ActiveDirectory module (the holder must be online): `Move-ADDirectoryServerOperationMasterRole -Identity "PL-SRV-0042" -OperationMasterRole PDCEmulator,RIDMaster`. [DOC S-qbxv7o56]
- Transfer all five roles by object, so no FQDN is passed as `-Identity`: `$dc = Get-ADDomainController -Identity "PL-SRV-0042.corp.example.com"` then `Move-ADDirectoryServerOperationMasterRole -Identity $dc -OperationMasterRole SchemaMaster,DomainNamingMaster,PDCEmulator,RIDMaster,InfrastructureMaster`. [DOC S-qbxv7o56]
- Seize three roles when the holder is gone for good: `Move-ADDirectoryServerOperationMasterRole -Identity "PL-SRV-0042" -OperationMasterRole RIDMaster,InfrastructureMaster,DomainNamingMaster -Force`. [DOC S-qbxv7o56]
- Ntdsutil seizure of the RID master on the new holder: `ntdsutil`, `roles`, `connections`, `connect to server PL-SRV-0042`, `q`, `seize rid master`, `q`, `q`. [DOC S-hnfdk22k, S-uyoeu33z]
