---
topic: auth/audit-log-apis
priority: P2
applies_to: "Office 365 Management Activity API, Microsoft Purview Audit (Standard/Premium), Microsoft Graph auditLogQuery (security namespace), Intune deviceManagement/auditEvents, Entra ID directoryAudits/signIns; docs retrieved 2026-09-26"
retrieved_utc: 2026-09-26
sources: [S-2xp7a2zn, S-5mkng6kh, S-vkmx3p22, S-pzhjwitg, S-p7uijoop, S-ojti56n4, S-wsetw6to, S-llv35yw5, S-tmpjr3zu, S-otcf27ix, S-mubyxer3, S-kt6usubu, S-s7cz6clh, S-iaxywacb, S-raqjhvyk, S-p26bti63, S-n5ozkko3, S-5kbhtctd, S-htpihbqv]
status: complete
---

# Audit log APIs: retrieving and exporting audit data

## Summary
Four distinct, complementary ways to pull audit data out of Microsoft 365/Entra/Intune programmatically: the
Office 365 Management Activity API (content-blob subscription model over five content types), the
`Search-UnifiedAuditLog` Exchange Online PowerShell cmdlet and the newer Graph `security/auditLog/queries`
(Purview Audit Search) API over the same unified audit log, Intune's `deviceManagement/auditEvents` Graph
resource for Intune-specific admin changes, and Entra ID's own `directoryAudits`/`signIns` Graph resources
with their much shorter licence-gated retention. This article covers retrieval/export mechanics and limits;
`auth/audit-events.md` covers the underlying event catalogs (Windows Security log, Entra sign-in categories,
ConfigMgr status messages, SQL Server Audit, GitLab).

## Facts

### Office 365 Management Activity API
- The API aggregates tenant events into content blobs classified by **content type**: `Audit.AzureActiveDirectory`,
  `Audit.Exchange`, `Audit.SharePoint`, `Audit.General` (all other workloads), and `DLP.All` (DLP events across
  workloads); a client subscribes per content type per tenant via `POST /subscriptions/start?contentType={ContentType}`.
  [DOC S-2xp7a2zn]
- After a subscription is created it can take **up to 12 hours** for the first content blobs to become available;
  blobs are not guaranteed to appear in event order because they are aggregated across servers/datacenters, so a
  later blob can contain earlier events than one already retrieved. [DOC S-2xp7a2zn]
- Starting a subscription is throttled: after a subscription request, a **15-minute** waiting period is required
  before another request can be made; this throttle does not apply to `/stop`. [DOC S-2xp7a2zn]
- `GET /subscriptions/content?contentType={ContentType}&startTime={t0}&endTime={t1}` lists available content; `startTime`
  and `endTime` must both be given or both omitted, must be no more than **24 hours apart**, and `startTime` no more
  than **7 days in the past**; omitting both defaults to the last 24 hours. Results are paged via a `NextPageUri`
  response header. [DOC S-2xp7a2zn]
- A `PublisherIdentifier` (the calling vendor's tenant GUID) should be included on every request to get a dedicated
  throttling quota; requests without it share one common quota. [DOC S-2xp7a2zn]
- The API root URL varies by cloud: `manage.office.com` (Enterprise/commercial), `manage-gcc.office.com` (GCC),
  `manage.office365.us` (GCC High), `manage.protection.apps.mil` (DoD). [DOC S-5mkng6kh]
- Access requires an Entra ID access token containing the `ActivityFeed.Read` claim (app permission
  "Read activity data for an organization"), and the tenant's **unified audit log must be turned on** (enabling it
  can take up to 60 minutes to take effect); if it is not, requests fail with a
  `Microsoft.Office.Compliance.Audit.DataServiceException: Tenant <tenantID> does not exist` error. [DOC S-2xp7a2zn, S-5mkng6kh]
- DLP event content (sensitive-data details) in the feed is restricted to callers granted "Read DLP sensitive data"
  permissions. [DOC S-2xp7a2zn]
- Audit (Premium) licensing gives about **twice the API bandwidth** of Audit (Standard): both start with a baseline
  of 2,000 requests/minute that scales with seat count and licence. [DOC S-vkmx3p22]

### Microsoft Purview Audit (Search-UnifiedAuditLog / Audit Search)
- **Audit (Standard)** default retention: audit records generated on/after **17 October 2023** are retained
  **180 days**; records generated before that date kept the older **90-day** default. **Audit (Premium)** retains
  Entra ID, Exchange, OneDrive and SharePoint records for **1 year** by default (via a built-in retention policy
  matching those four `Workload` values); an add-on **10-year retention licence** extends coverage further for
  users it's assigned to (not retroactive), while non-user-entity records (service principal/system/application
  activity) are fixed at 1 year and not covered by custom retention policies. All other Audit (Premium)-covered
  records default to 180 days unless a custom audit log retention policy is created (up to 10 years). [DOC S-vkmx3p22]
- `Search-UnifiedAuditLog` (Exchange Online PowerShell) returns **100 records by default**; `-ResultSize` raises
  this to a maximum of **5,000 records** per call. To page through more, set `-SessionId` plus
  `-SessionCommand ReturnLargeSet` (unsorted, up to **50,000 records** per session) or
  `-SessionCommand ReturnNextPreviewPage` (sorted by date, capped at 5,000 records); mixing the two
  `SessionCommand` values for the same `SessionId` limits total output to 10,000 results. [DOC S-pzhjwitg, S-p7uijoop]
- Running `Search-UnifiedAuditLog -RecordType ExchangeAdmin` can take **up to 30 minutes** after an Exchange cmdlet
  runs before the corresponding entry appears in results. [DOC S-iaxywacb]
- Search-UnifiedAuditLog requires the **View-Only Audit Logs** or **Audit Logs** role (part of the Compliance
  Management / Organization Management role groups). [DOC S-p7uijoop]
- For programmatic downloads from the Microsoft 365 audit log, Microsoft recommends the Microsoft 365 Management
  Activity API (a REST web service) instead of `Search-UnifiedAuditLog` in a PowerShell script; the cmdlet page does
  not mention the Graph Purview Audit Search API (covered below from its own sources). [DOC S-pzhjwitg]
- `Set-AdminAuditLogConfig -UnifiedAuditLogIngestionEnabled $false`/`$true` (Exchange Online PowerShell) turns
  auditing off/on for the organization (enabling can take up to 60 minutes to take effect); turning it on or off
  needs the Exchange Online *Audit Logs* role. [DOC S-raqjhvyk]
- With Audit (Premium), Entra ID, Exchange, OneDrive and SharePoint records get **1-year** retention by default
  through a built-in default audit log retention policy, without creating one; Audit (Standard) keeps records
  for 180 days. [DOC S-vkmx3p22]

### Microsoft Graph Purview Audit Search API (`security/auditLog/queries`)
- The newer async query model: `POST /security/auditLog/queries` creates an `auditLogQuery` with optional
  `displayName`, `filterStartDateTime`, `keywordFilter` (free-text over non-indexed properties),
  `serviceFilter` (the `Workload` value), `operationFilters`, `userPrincipalNameFilters`, `ipAddressFilters`,
  `objectIdFilters` and `administrativeUnitIdFilters`; the object's `status` is one of `notStarted`, `running`,
  `succeeded`, `failed` or `cancelled`. [DOC S-ojti56n4, S-wsetw6to]
- `GET /security/auditLog/queries/{id}` reads the query object (including its `status`);
  `GET /security/auditLog/queries/{id}/records` (the `records` navigation property) returns the
  `auditLogRecord` objects the query retrieved. [DOC S-ojti56n4, S-llv35yw5]
- Least-privileged Graph permission to create/list queries is `AuditLogsQuery-Entra.Read.All` (delegated or
  application); higher-privileged, broader options are `AuditLogsQuery-CRM.Read.All`,
  `AuditLogsQuery-Endpoint.Read.All`, `AuditLogsQuery-Exchange.Read.All`, `AuditLogsQuery-OneDrive.Read.All`,
  `AuditLogsQuery-SharePoint.Read.All` or the umbrella `AuditLogsQuery.Read.All`; personal Microsoft accounts are
  not supported. [DOC S-wsetw6to] Reading an already-created `auditLogQuery` object (`GET .../queries/{id}`) uses
  the separate `ThreatIntelligence.Read.All` permission. [DOC S-p26bti63]
- The API is available in the global service cloud only -- not in US Gov L4, US Gov L5 (DOD) or the China
  (21Vianet) cloud. [DOC S-wsetw6to, S-llv35yw5]

### Intune audit events (Graph `deviceManagement/auditEvents`)
- `GET /deviceManagement/auditEvents` / `GET /deviceManagement/auditEvents/{id}` (v1.0) list/read Intune's
  audit events; least-privileged permission is `DeviceManagementApps.Read.All` (or the broader
  `DeviceManagementApps.ReadWrite.All`), delegated or application; the Graph API for Intune requires an active
  Intune licence on the tenant. Personal Microsoft accounts are not supported. [DOC S-tmpjr3zu, S-otcf27ix]
- The resource exposes `getAuditCategories()` and `getAuditActivityTypes()` functions, each returning a string
  collection (the page gives no further description). [DOC S-tmpjr3zu]
- Listing audit events is available in all four national cloud deployments (global, US Gov L4, US Gov L5/DOD,
  China 21Vianet) -- unlike the Graph Purview Audit Search API above. [DOC S-otcf27ix]
- Example (Cloud PKI audit): `GET https://graph.microsoft.com/beta/deviceManagement/auditEvents?$filter=activityType eq 'Create CloudCertificationAuthority'`,
  or filtered by date range with `activityDateTime gt ... and activityDateTime le ...&$orderby=activityDateTime desc`;
  in the admin center the same logs are under **Tenant Administration > Audit Logs**. [DOC S-n5ozkko3]
- The `auditEvents` endpoint is not specific to Cloud PKI: it is Intune's general audit-event resource, so the
  same query pattern applies to other Intune workloads. [DER S-n5ozkko3, S-tmpjr3zu: the Cloud PKI page queries
  the generic Intune `auditEvent` resource]

### Entra ID audit/sign-in Graph resources and export
- Entra's own audit trail is split into `directoryAudits` (the history of every task performed in the tenant,
  by a user or a service) and `signIns` (interactive, non-interactive, service-principal and managed-identity
  sign-ins) -- see `entra/pim-and-governance.md` and `auth/audit-events.md` for what each records.
  [DOC S-mubyxer3]
- Default Graph/admin-center retention by licence: **Free** = 7 days for both audit logs and sign-ins; **P1**
  and **P2** = 30 days for both. Microsoft Graph activity logs (a separate log of Graph API calls
  themselves) require P1 or P2 and are not retained at all unless archived to storage or an analytics tool.
  Risky sign-ins retention also varies by licence (7/30/90 days for Free/P1/P2); risky users has no limit. [DOC S-kt6usubu]
- Audit and sign-in data can be kept longer than the default retention by routing it out of Entra (for example to
  an Azure storage account via Azure Monitor). [DOC S-kt6usubu]
- **Diagnostic settings** (Entra admin center > Entra ID > Monitoring & health > Diagnostic settings; needs
  Security Administrator) send the selected log categories to a Log Analytics workspace, an event hub or a
  storage account; the destination must exist first, and logs can take up to three days to start appearing
  there. [DOC S-s7cz6clh]
- Integrating Microsoft Entra logs with Azure Monitor (Log Analytics) automatically enables the Microsoft Entra
  data connector in Microsoft Sentinel. [DOC S-5kbhtctd]
- Custom security attribute audit logs are a subset of the standard audit logs with their own diagnostic
  settings (the **Custom security attributes** tab); Microsoft recommends keeping them separate from directory
  audit logs so attribute assignments are not revealed inadvertently; configuring them needs the
  **Attribute Log Administrator** role active. [DOC S-s7cz6clh]
- Tenants with Microsoft 365 E5 / Purview Suite / E5 eDiscovery-and-Audit licensing can instead route Entra ID
  audit logs into Purview Audit (Premium) retention policies as an alternative to exporting to storage. [DOC S-kt6usubu]
- Entra admin center downloads (CSV or JSON) hold up to 250,000 audit records or 100,000 sign-in/provisioning
  records per file, and the browser download times out on large data sets; for large downloads use the
  reporting API or send the logs to an endpoint through diagnostic settings instead. [DOC S-htpihbqv]

## Reference
- `auth/audit-events.md` -- the event catalogs these APIs surface (Windows Security log ids, Entra sign-in log
  categories, ConfigMgr status messages, SQL Server Audit action groups, GitLab audit events); this article adds
  the back-link below.
- `entra/pim-and-governance.md` -- PIM activation/audit trail is itself a `directoryAudits` category this API
  family retrieves (role activation, approval, alerts); cross-linked there.
- `logs/microsoft-sentinel.md` -- ingesting `SigninLogs`/`AuditLogs`/`DeviceEvents` (Defender XDR connector) as
  Sentinel analytics tables is the SIEM side of the diagnostic-settings export path documented above.
- `intune/remote-actions.md` -- remote actions issued against a managed device are themselves Intune audit
  events retrievable via `deviceManagement/auditEvents`.

## Examples
- SNIPPET: Search-UnifiedAuditLog paged export using ReturnLargeSet; context: Exchange Online PowerShell, up to 50,000 unsorted records per session; checked: no [DOC S-pzhjwitg, S-p7uijoop]
```powershell
# Search-UnifiedAuditLog with paging for a large export (Exchange Online PowerShell)
$sessionId = "audit-export-2026-09-26"
$results = @()
do {
    $batch = Search-UnifiedAuditLog -StartDate (Get-Date).AddDays(-7) -EndDate (Get-Date) `
        -SessionId $sessionId -SessionCommand ReturnLargeSet -ResultSize 5000
    $results += $batch
} while ($batch.Count -eq 5000)
```

- SNIPPET: start an Office 365 Management Activity API content-type subscription; context: Entra app-only token with the ActivityFeed.Read claim, tenant's unified audit log must be on; checked: no [DOC S-2xp7a2zn]
```http
# Start an Office 365 Management Activity API subscription (Entra app-only token, ActivityFeed.Read claim)
POST https://manage.office.com/api/v1.0/00000000-0000-0000-0000-000000000000/activity/feed/subscriptions/start?contentType=Audit.AzureActiveDirectory&PublisherIdentifier=00000000-0000-0000-0000-000000000000
Authorization: Bearer <token>
```

- SNIPPET: create a Graph Purview Audit Search auditLogQuery, then list its records; context: Graph v1.0, `AuditLogsQuery-Entra.Read.All` (or broader `AuditLogsQuery.Read.All`) to create/list, `ThreatIntelligence.Read.All` to read the query object, global service cloud only; checked: no [DOC S-ojti56n4, S-wsetw6to, S-p26bti63]
```http
# Graph Purview Audit Search: create a query, then list its records
POST https://graph.microsoft.com/v1.0/security/auditLog/queries
Content-Type: application/json

{
  "displayName": "sign-in changes for jan.kowalski",
  "filterStartDateTime": "2026-09-19T00:00:00Z",
  "filterEndDateTime": "2026-09-26T00:00:00Z",
  "userPrincipalNameFilters": ["jan.kowalski@corp.example.com"]
}

GET https://graph.microsoft.com/v1.0/security/auditLog/queries/{auditLogQueryId}/records
```

- SNIPPET: list Intune deviceManagement/auditEvents filtered by date range; context: Graph beta, `DeviceManagementApps.Read.All` (or broader `.ReadWrite.All`), Intune licence required; checked: no [DOC S-n5ozkko3, S-tmpjr3zu]
```http
# Intune audit events for a managed device's PL-LT-00123 role assignment change, last 24h
GET https://graph.microsoft.com/beta/deviceManagement/auditEvents?$filter=activityDateTime gt 2026-09-25T00:00:00Z&$orderby=activityDateTime desc
```
