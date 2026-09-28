---
topic: windows/gmsa
priority: P0
applies_to: "Windows Server 2012 and later AD DS (docs current to Windows Server 2025)"
retrieved_utc: 2026-09-28
sources: [S400, S401, S402, S403, S404, S405, S-sav2ixtw]
status: complete
---

# Group Managed Service Accounts (gMSA)

## Summary
- A gMSA is an AD account whose password the domain controller computes and authorized hosts retrieve; no administrator enters or rotates it.
- Prerequisites: a KDS root key in the forest, domain/forest functional level 2012 or later for full support, and a security group (or computer list) allowed to retrieve the password.
- Create with `New-ADServiceAccount`, allow hosts with `-PrincipalsAllowedToRetrieveManagedPassword`, install on each host with `Install-ADServiceAccount`, check with `Test-ADServiceAccount`.
- Microsoft lists Service Control Manager services, IIS application pools and Task Scheduler tasks as supported consumers.
- No Microsoft page found that shows the exact scheduled-task registration syntax for a gMSA (see Gaps).

## Facts
- A gMSA gives automatic password management and simplified SPN management, and works across multiple servers. [DOC S401]
- The domain controller computes the gMSA password from a key provided by the Key Distribution Service (`kdssvc.dll`) and other attributes of the account; member hosts get the current and previous password values from a domain controller. [DOC S401]
- gMSAs don't apply to Windows versions earlier than Windows Server 2012. [DOC S401]
- The PowerShell commands that administer gMSAs need a 64-bit architecture. [DOC S401,S402]
- The DC uses the account's `msDS-SupportedEncryptionTypes` to choose ticket encryption; Microsoft advises always configuring AES for MSAs. [DOC S401]
- Principal comparison: a gMSA supports "Any Windows Server domain-joined server". The domain controller manages the password and the host retrieves it. [DOC S400]
- Consumers that support gMSA: the same APIs as sMSA; services that use Service Control Manager to set the logon identity; IIS application pools; tasks using Task Scheduler. [DOC S400]
- Failover clusters don't support gMSAs. Services on the Cluster service can use one if they are a Windows service, an app pool or a scheduled task. [DOC S400,S401]
- To manage gMSAs you need the Domain Admins or Enterprise Admins group, or delegated rights to create `msDS-GroupManagedServiceAccount` objects. Account Operators can't create them by default. [DOC S400]
- The domain and forest functional levels should be Windows Server 2012 or later. [DOC S400]
- A KDS root key must exist. You can confirm it through the KdsSvc Operational log, Event ID 4004. [DOC S400]
- gMSA names must be unique in the forest, not only in the domain. [DOC S400]
- Create: `New-ADServiceAccount -Name <n> -DNSHostName <n>.<domain> -PrincipalsAllowedToRetrieveManagedPassword <group>`. [DOC S400]
- The password change interval (`-ManagedPasswordIntervalInDays`, default 30 days) can only be set at creation. It is stored in `msDS-ManagedPasswordInterval`. [DOC S400,S403]
- `-RestrictToOutboundAuthenticationOnly` creates a gMSA for outbound authentication only. [DOC S400]
- `Test-ADServiceAccount -Identity <n>` checks whether the host can retrieve the password. `Install-ADServiceAccount` must run on each host where the service runs. [DOC S400]
- Kerberos requirements for services using a gMSA: correct SPNs, DNS, firewall rules that allow Kerberos, synchronized clocks, and support for the gMSA's Kerberos encryption types. [DOC S400]
- DCs wait up to 10 hours after the KDS root key is created before they allow a gMSA to be created. `Add-KdsRootKey -EffectiveImmediately` only works on the DC where it runs until replication completes. `-EffectiveTime ((Get-Date).AddHours(-10))` is documented for single-DC test labs only. [DOC S402]
- If a KDS root key is deleted and re-created, restart the KDC on all DCs. [DOC S402]
- `Reset-ADServiceAccountPassword` applies to sMSAs only, not gMSAs. [DOC S403]
- Task Scheduler logon types: `TASK_LOGON_PASSWORD`=1 (the password must be supplied at registration), `TASK_LOGON_S4U`=2 (no stored password; no network access), `TASK_LOGON_SERVICE_ACCOUNT`=5 (documented as Local System, Local Service or Network Service). [DOC S404]
- `New-ScheduledTaskPrincipal -LogonType` accepts None, Password, S4U, Interactive, Group, ServiceAccount, InteractiveOrPassword. [DOC S405]
- Microsoft's Engage Center guide moves a scheduled task to a gMSA with `New-ScheduledTaskPrincipal -UserId <DOMAIN>\<gmsa>$ -LogonType Password` and then `Set-ScheduledTask ... -Principal`: the `$`-suffixed account name and `LogonType Password`, with no password supplied. [DOC S-sav2ixtw]
- Service accounts table: the gMSA column shows "No" in the row "App runs on Windows Server". This contradicts S400 (see conflicts). [DOC S403]

## Reference
| Cmdlet | Purpose | Source |
|---|---|---|
| `Add-KdsRootKey` | Create the forest KDS root key (once) | S402 |
| `New-ADServiceAccount` | Create a gMSA | S400 |
| `Set-ADServiceAccount` | Change properties (not the password interval) | S400 |
| `Add-ADGroupMember` / `Add-ADPrincipalGroupMembership` | Allow a host by group membership | S400 |
| `Install-ADServiceAccount` / `Uninstall-ADServiceAccount` | Install or remove the gMSA on a host | S400 |
| `Test-ADServiceAccount` | Check that the host can retrieve the password | S400 |

## Examples
- SNIPPET: create a gMSA, allow a host group to retrieve its password, then install and test it on the host; context: AD DS, domain/forest functional level 2012+, run as Domain/Enterprise Admins or a delegated account; checked: no [DOC S400: same `New-ADServiceAccount -PrincipalsAllowedToRetrieveManagedPassword`, `Add-ADGroupMember`, `Install-ADServiceAccount`, `Test-ADServiceAccount` cmdlets]
```powershell
# Fixture names only
New-ADServiceAccount -Name app-sync -DNSHostName app-sync.corp.example.com `
  -PrincipalsAllowedToRetrieveManagedPassword 'app-sync-hosts'
Add-ADGroupMember -Identity 'app-sync-hosts' -Members 'PL-SRV-0042$'
# on PL-SRV-0042
Install-ADServiceAccount -Identity app-sync
Test-ADServiceAccount -Identity app-sync
```
