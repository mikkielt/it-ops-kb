---
topic: graph/powershell-sdk
priority: P1
applies_to: "Microsoft Graph PowerShell SDK (Microsoft.Graph / Microsoft.Graph.Beta modules)"
retrieved_utc: 2026-09-26
sources: [S-5q4kuvo5, S-d7byvsls, S-qqaa5jqp, S-h7l5c7uo, S-v5rdr5la, S-6jt4shfp]
status: complete
---

# Microsoft Graph PowerShell SDK: connect, call, discover

## Summary
- Two parallel modules: `Microsoft.Graph` (v1.0 endpoint) and `Microsoft.Graph.Beta` (`/beta` endpoint); cmdlets exist only for the module installed.
- `Connect-MgGraph` must run before any Graph cmdlet; it supports delegated sign-in (`-Scopes`), app-only certificate auth (`-ClientId` + `-CertificateThumbprint`/`-CertificateSubjectName`/`-Certificate`), and managed identity (`-Identity`).
- `Invoke-MgGraphRequest` calls any Graph REST endpoint directly (method/URI/body) when no dedicated cmdlet exists yet.
- `Find-MgGraphCommand` and `Find-MgGraphPermission` discover, respectively, the cmdlet(s) and REST path for a task, and the permissions a cmdlet needs.
- PowerShell equivalents of OData query parameters: `-Property` (`$select`), `-Expand` (`$expand`), `-Top` (`$top`, page size), `-Filter`, `-ConsistencyLevel`/`-CountVariable` (advanced queries); paging beyond one page needs `-All` or manual `@odata.nextLink` handling.

## Facts
### Modules and versions
- The SDK ships two modules, `Microsoft.Graph` and `Microsoft.Graph.Beta`, calling the Graph v1.0 and beta REST APIs respectively; cmdlets are available only for the module that's installed. [DOC S-5q4kuvo5]
- Microsoft Graph PowerShell works with PowerShell 7 and later and is compatible with Windows PowerShell 5.1; it is cross-platform (Windows, macOS, Linux). [DOC S-h7l5c7uo]
- Microsoft Graph PowerShell permissions are not pre-authorized: the signed-in account or app must consent to each permission scope it needs, following least privilege. [DOC S-h7l5c7uo]

### Connect-MgGraph
- `Connect-MgGraph` must be invoked before any cmdlet that accesses Microsoft Graph; it acquires the access token via the Microsoft Authentication Library (MSAL). [DOC S-d7byvsls]
- Delegated sign-in: `Connect-MgGraph -Scopes "User.Read.All","Group.ReadWrite.All"`; the user signs in once per PowerShell session (until the window closes or `Disconnect-MgGraph` runs); repeat the command with new scopes to add permissions. [DOC S-5q4kuvo5]
- `UserParameterSet` (default) accepts `-Scopes`, `-TenantId`, `-ClientId`, `-ContextScope`, `-Environment`, `-UseDeviceCode`, `-ClientTimeout`, `-NoWelcome`, `-Break`. [DOC S-d7byvsls]
- `AppCertificateParameterSet` (app-only, certificate): `-ClientId` (required), plus `-CertificateSubjectName` (aliases `CertificateSubject`, `CertificateName`), `-CertificateThumbprint`, `-Certificate <X509Certificate2>`, `-SendCertificateChain <bool>`, `-TenantId`. [DOC S-d7byvsls]
- `IdentityParameterSet` (managed identity): `-Identity` switch, plus `-ClientId` (to target a user-assigned identity), `-ContextScope`, `-Environment`, `-ClientTimeout`, `-NoWelcome`, `-Break`. [DOC S-d7byvsls]
- `-Environment` selects the cloud (default: global public cloud); `Get-MgEnvironment` lists built-in environments including `China`, `USGov`, `USGovDoD`, each with its own `AzureADEndpoint`/`GraphEndpoint`. [DOC S-d7byvsls]
- `Disconnect-MgGraph` ends the session and revokes the token for that PowerShell session. [DOC S-5q4kuvo5]

### Invoke-MgGraphRequest
- `Invoke-MgGraphRequest` issues a REST request to any Graph API endpoint given a URI, method and optional body; it is the way to call an API for which no dedicated cmdlet yet exists. [DOC S-qqaa5jqp]
- Parameters include `-Method`, `-Uri` (required), `-Body`, `-Headers`, `-OutputFilePath`/`-InputFilePath`, `-ContentType`, `-SessionVariable`, `-ResponseHeadersVariable`, `-StatusCodeVariable`, `-OutputType`, `-InferOutputFileName`, `-PassThru`, `-SkipHeaderValidation`, `-SkipHttpErrorCheck`. [DOC S-qqaa5jqp]
- Example usage for an operation with no cmdlet coverage (`forceTakeover` on domain verification): `Invoke-MgGraphRequest -Method POST -Uri "https://graph.microsoft.com/v1.0/domains/<domain>/verify" -Body $body -ContentType "application/json"`. [DOC S-qqaa5jqp]

### Discovery: Find-MgGraphCommand / Find-MgGraphPermission
- `Find-MgGraphCommand -command Get-MgUser | Select -First 1 -ExpandProperty Permissions` lists the permissions (with `IsAdmin`, `Description`) usable to call a given cmdlet. [DOC S-5q4kuvo5]
- `Find-MgGraphCommand` also resolves the underlying Graph API path a cmdlet calls, for cross-checking against Graph Explorer or the REST reference. [DOC S-h7l5c7uo]
- `Find-MgGraphPermission` helps identify permissions required for a scenario, complementing `Find-MgGraphCommand`. [DOC S-h7l5c7uo]

### Query parameters as cmdlet parameters
- `-Property` returns a non-default property set (maps to `$select`); directory-object-derived resources (`User`, `Group`) return only a default subset without it. [DOC S-v5rdr5la]
- `-Top` sets page size; minimum 1, maximum depends on the API (matches the REST `$top` limit for that resource). [DOC S-v5rdr5la]
- `-Expand` includes a relationship (navigation property) in the result, e.g. `Get-MgGroup -GroupId <id> -Expand members`; a resource's properties and one relationship can be queried together, but not two relationships at once; not all relationships/resources support `-Expand`, and not all support `-Select` on the expanded items. [DOC S-v5rdr5la]
- `-ExpandProperty "children($select=id,name)"` nests a `$select` inside an `$expand` via the PowerShell parameter string. [DOC S-v5rdr5la]
- Advanced queries via PowerShell: `Get-MgUser -ConsistencyLevel eventual -Count userCount -Filter "startsWith(DisplayName, 'a')" -Top 1` — the `-ConsistencyLevel`/count-variable parameters map to the REST `ConsistencyLevel: eventual` header and `$count`. [DOC S-h7l5c7uo]
- Paging one page at a time uses `-Top`; `Import-Module Microsoft.Graph.Users; Get-MgUser -Top 5` returns the first 5 users (server-side paging still applies beyond that page via `@odata.nextLink`). [DOC S-6jt4shfp]

## Reference
| Cmdlet / parameter | Purpose | Source |
|---|---|---|
| `Connect-MgGraph -Scopes ...` | delegated sign-in | S-d7byvsls |
| `Connect-MgGraph -ClientId -CertificateThumbprint -TenantId` | app-only, certificate | S-d7byvsls |
| `Connect-MgGraph -Identity [-ClientId]` | managed identity | S-d7byvsls |
| `Invoke-MgGraphRequest -Method -Uri -Body` | raw REST call | S-qqaa5jqp |
| `Find-MgGraphCommand -Command <cmdlet>` | permissions/API path for a cmdlet | S-5q4kuvo5, S-h7l5c7uo |
| `Find-MgGraphPermission` | permissions for a scenario | S-h7l5c7uo |
| `Disconnect-MgGraph` | end session, revoke token | S-5q4kuvo5 |
| `-Property` / `-Expand` / `-Top` / `-Filter` / `-ConsistencyLevel` | `$select`/`$expand`/`$top`/`$filter`/advanced query equivalents | S-v5rdr5la |

Related: `graph/batching-and-query.md` (the REST-level `$batch`, paging, `$select`/`$expand` and advanced-query facts these cmdlets wrap); `graph/permissions.md` (least-privileged Graph permissions per device call, cross-checked with `Find-MgGraphPermission`).

## Examples
- App-only sign-in with a certificate and a direct Graph call:
```powershell
Connect-MgGraph -ClientId "00000000-0000-0000-0000-000000000000" `
  -TenantId "00000000-0000-0000-0000-000000000000" `
  -CertificateThumbprint "0000000000000000000000000000000000ABCD"

Invoke-MgGraphRequest -Method GET -Uri "https://graph.microsoft.com/v1.0/devices?`$filter=displayName eq 'PL-LT-00123'"
```
- Managed identity sign-in (e.g. from an Azure Automation runbook):
```powershell
Connect-MgGraph -Identity
Get-MgUser -Top 5
```
- Discover permissions before granting consent:
```powershell
Find-MgGraphCommand -Command Get-MgDevice | Select -First 1 -ExpandProperty Permissions
```
- Advanced query for a near-instant device count:
```powershell
Get-MgDevice -ConsistencyLevel eventual -CountVariable deviceCount -Filter "startsWith(DisplayName,'PL-LT')" -All
```
