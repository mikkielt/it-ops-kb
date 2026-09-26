---
topic: defender/advanced-hunting
priority: P2
applies_to: "Microsoft Defender XDR advanced hunting (Defender portal, Graph security API, legacy MDE advancedqueries API), docs ms.date through 2026-09"
retrieved_utc: 2026-09-26
sources: [S-a7zqfimk, S-oq2hykox, S-gstozrro, S-5nnb4rik, S-l5g4lirw, S-zaka5sgl, S-fnmkxefn, S627, S621, S-bw46kqrh, S-v5mr4bu5, S-osk3cbyu, S-vjtqqsri, S-x7sbbxju, S-4w7mhn5x, S-ktfxaivl, S-bvp2lhfv, S-yjjcwawd, S-r7vkbj73, S-cctucraa, S-3itm74ex, S-jh7vdeyt, S-tnlgchd2, S-elscbjku]
status: complete
files: [defender/advanced-hunting-tables.csv]
---

# Defender XDR advanced hunting

## Summary
Advanced hunting is the KQL query surface over Defender XDR's raw event and entity tables (30-day native retention),
usable interactively in the Defender portal, from custom detection rules, and via two APIs: the current
Graph `POST /security/runHuntingQuery` and the legacy MDE `POST /api/advancedqueries/run` (retiring, migrate to
Graph). Query quotas (100,000 rows, 10-minute timeout, 64 MB result size, tenant CPU quota per 15 minutes) apply to
both manual queries and custom detection rules; the legacy API additionally caps calls per minute/hour and total
running time per day. Custom detection rules turn a saved query into a scheduled or continuous (near-real-time)
job that can generate alerts and trigger response actions (isolate device, quarantine file, disable user, etc.).
Table reference: `advanced-hunting-tables.csv`.

## Facts

### Overview, quotas, retention
- Advanced hunting queries up to 30 days of raw Defender XDR data; onboarding a Sentinel workspace also allows querying analytics-tier data per that workspace's configured retention. [DOC S-a7zqfimk]
- Event/activity tables (alerts, security events, system events) are updated almost immediately after sensors transmit data; entity tables (users, devices) are updated every hour with the latest full record. [DOC S-a7zqfimk]
- Quota: date range up to 30 days for native Defender XDR data (every query). [DOC S-a7zqfimk]
- Quota: result set up to 100,000 rows (every query). [DOC S-a7zqfimk]
- Quota: timeout 10 minutes per query; the service returns an error if a query does not complete within that time. [DOC S-a7zqfimk]
- Quota: CPU resources are allocated per tenant, refreshed every 15 minutes; the portal warns above 10% of allocated resources in a run and blocks further queries once the tenant reaches 100% until the next 15-minute cycle. [DOC S-a7zqfimk]
- Quota: overall result size limit 64 MB; if exceeded, the portal returns as many records as fit within the limit and flags the results as partial. [DOC S-a7zqfimk]
- Advanced hunting queries use UTC for all data; results are converted to the tenant's configured time zone for display. [DOC S-a7zqfimk]
- A separate set of quotas and parameters applies to advanced hunting performed through the API (the legacy MDE `advancedqueries` API below has its own limits). [DOC S-a7zqfimk]
- To retain Defender XDR hunting tables beyond 30 days, onboard a Sentinel workspace and configure analytics-tier retention for the tables, or stream data out via the Defender XDR Streaming API or the MDE Raw Data Streaming API. [DOC S-a7zqfimk]
- The query resources report (Advanced hunting page or Reports > General) shows per-query CPU resource usage (Low/Medium/High), state (completed/failed/throttled), interface (portal, custom detections, API), and query time, for the last 30 days of queries; only Entra Security Reader-and-above roles see all users' queries. [DOC S-oq2hykox]

### Schema and tables
- The schema groups tables by device (`Device*`), email/collaboration (`Email*`, `Message*`), identity (`Identity*`, `EntraId*`), alert (`AlertInfo`, `AlertEvidence`), cloud app (`CloudAppEvents`), vulnerability management (`DeviceTvm*`), and several preview tables (e.g. `AgentsInfo`, `BehaviorInfo`, `OAuthAppInfo`). [DOC S-gstozrro]
- `DeviceTvm*` (Threat and Vulnerability Management) tables are exposed in Microsoft Sentinel only for schema visibility (autocomplete/query validation); Sentinel accepts queries against them but returns no data — TVM data is available only when the query runs in Defender XDR advanced hunting. [DOC S-cctucraa, S-r7vkbj73, S-3itm74ex]
- Table reference (kind, what it records, key columns, source): see `advanced-hunting-tables.csv`, covering `DeviceInfo` [DOC S627], `DeviceFileEvents` [DOC S-v5mr4bu5], `DeviceNetworkEvents` [DOC S-osk3cbyu], `DeviceRegistryEvents` [DOC S-x7sbbxju], `DeviceEvents` [DOC S-4w7mhn5x], `DeviceImageLoadEvents` [DOC S-ktfxaivl], `DeviceFileCertificateInfo` [DOC S-bvp2lhfv], `DeviceNetworkInfo` [DOC S-yjjcwawd] and `AlertEvidence` [DOC S-tnlgchd2].
- `DeviceLogonEvents` collection is not supported on Windows 7 or Windows Server 2008 R2 devices onboarded to Defender for Endpoint. [DOC S-vjtqqsri]
- `DeviceLogonEvents.AdditionalFields` carries access-token privilege context (e.g. `TokenHasDomainAdminSid`, `TokenHasEnterpriseAdminSid`, `NumberOfSidsInDomainAdminToken`) for token-creation events where `InitiatingProcessFileName == "lsass.exe"`, derived from the token's SID list at logon time; the recorded privileges may not match current directory state. [DOC S-vjtqqsri]
- `DeviceProcessEvents.SHA256` and equivalent `InitiatingProcess*SHA256` columns are usually not populated; use the `SHA1` columns when available. [DOC S-bw46kqrh]
- `ProcessUniqueId` / `InitiatingProcessUniqueId` (equal to the Windows Process Start Key) uniquely identify a specific process instance without combining `ProcessId` + `ProcessCreationTime`, since PIDs are recycled. [DOC S-bw46kqrh]
- To get created-process signing info (not covered by `InitiatingProcessSignatureStatus`, which describes the initiating process), join `DeviceProcessEvents.SHA1` to `DeviceFileCertificateInfo`. [DOC S-bw46kqrh]
- `DeviceTvmSecureConfigurationAssessment` joins to `DeviceTvmSecureConfigurationAssessmentKB` on `ConfigurationId` for the human-readable configuration name/description/risk. [DOC S-3itm74ex]
- `AlertInfo` joins to `AlertEvidence` on `AlertId` to get the entities/evidence for each alert. [DOC S-jh7vdeyt]

### Best practices (query performance)
- Apply time and other filters before parsing/transform functions (`substring()`, `parse_json()`, etc.); use `has`/`has_cs` rather than `contains` to avoid substring scans; avoid unscoped `search`/`union` (use `search in (Table1, Table2) "term"`); avoid `*` wildcarded column search; case-sensitive operators (`==`, `has_cs`) are faster than case-insensitive ones. [DOC S-5nnb4rik]
- `join`: put the smaller/more-filtered table on the left; the default and `innerunique` join flavors deduplicate the left table by join key (use `kind=inner` to keep all matches); filter both sides by time window before joining; `hint.shufflekey` helps high-cardinality join keys, `hint.strategy = broadcast` helps when the left table is small (up to 100,000 records) and the right is very large. [DOC S-5nnb4rik]
- `summarize`: prefer `project` over `summarize by` on non-repetitive columns; use `hint.shufflekey` for high-cardinality `summarize by` columns. [DOC S-5nnb4rik]
- Avoid terms of three characters or fewer in filters/comparisons — they are not indexed. [DOC S-5nnb4rik]

### Custom detection rules
- A custom detection rule is a saved advanced hunting query set to run on a schedule (or continuously) that can generate alerts and take response actions. [DOC S-l5g4lirw]
- Each rule can generate at most 150 alerts per run. [DOC S-l5g4lirw]
- Recommended query output columns: `Timestamp`/`TimeGenerated` (sets the generated alert's time); for MDE tables, `DeviceId` and `ReportId` (device-group scoping and process-tree view); for other Defender tables, `Timestamp` and `ReportId` from the same event (entity scope and alert timeline). [DOC S-l5g4lirw]
- Frequency options: Continuous (NRT), every hour, every 3 hours, every 12 hours, every 24 hours, or Custom (Sentinel-only data, 5 minutes to 14 days). [DOC S-l5g4lirw]
- Fixed lookback by frequency for rules using Defender XDR data: 24h frequency -> 30-day lookback; 12h -> 48h lookback; 3h -> 12h lookback; hourly -> 4h lookback. [DOC S-l5g4lirw]
- Continuous (NRT) frequency requires: the query references exactly one table, uses only supported KQL features, has no `join`/`union`/`externaldata`, and has no comment lines. [DOC S-l5g4lirw]
- Tables supporting Continuous (NRT) include (Defender XDR side) `AlertEvidence`, `DeviceEvents`, `DeviceFileEvents`, `DeviceProcessEvents`, `DeviceNetworkEvents`, `DeviceRegistryEvents`, `DeviceLogonEvents`, `DeviceImageLoadEvents`, `DeviceInfo`, `DeviceNetworkInfo`, `DeviceFileCertificateInfo`, `EmailEvents` (except `LatestDeliveryLocation`/`LatestDeliveryAction`), `EmailAttachmentInfo`, `EmailPostDeliveryEvents`, `EmailUrlInfo`, `IdentityDirectoryEvents`, `IdentityLogonEvents`, `IdentityQueryEvents`, `UrlClickEvents`. [DOC S-l5g4lirw]
- Custom details: at most 20 key-value pairs per rule; combined size of all custom details and values per alert is 4 KB (exceeding it drops the whole custom-details array). [DOC S-l5g4lirw]
- Actions on devices (from `DeviceId` results): isolate device, collect investigation package, run antivirus scan, initiate investigation, restrict app execution. [DOC S-l5g4lirw]
- Actions on files: allow/block (needs *Remediate* permission and a file hash such as SHA-1) and quarantine file (from `SHA1`/`SHA256`/`InitiatingProcess*` hash columns). [DOC S-l5g4lirw]
- Actions on users: mark as compromised, disable user, reset user authentication (need `AccountObjectId` for Entra identities, or SID columns for on-prem); SaaS governance actions (Box, Google Workspace, Salesforce disable/reset) are in preview via `CloudAppEvents`. [DOC S-l5g4lirw]
- Actions on emails: move to mailbox folder or delete (soft/hard); require `NetworkMessageId` and `RecipientEmailAddress` in the query output. [DOC S-l5g4lirw]
- Required permissions to manage custom detections on Defender data: Microsoft Defender **Security settings (manage)**, or Entra **Security Administrator**, or **Security Operator** (Security Operator needs the Defender for Endpoint **Manage Security Settings** permission too when RBAC is on). Sentinel data instead needs the **Microsoft Sentinel Contributor** Azure role (or higher). [DOC S-l5g4lirw]
- Managing a rule that queries `Email*` tables needs Defender for Office 365 manage permissions; `Identity*` tables need Defender for Identity/Cloud Apps manage permissions; `IdentityLogonEvents` needs manage permissions for both, since it holds data from both services. [DOC S-l5g4lirw]
- Custom detections evaluate `ingestion_time()` (not the event `Timestamp`) to account for ingestion delay, so events older than the lookback can still be included; duplicate alerts from overlapping lookback/frequency windows are grouped and deduplicated automatically. [DOC S-l5g4lirw]

### Graph runHuntingQuery vs legacy MDE advancedqueries API
- Graph `POST /security/runHuntingQuery`: least-privileged permission `ThreatHunting.Read.All`, both delegated and application; no higher-privileged alternative is offered. [DOC S-zaka5sgl]
- Request body: `Query` (required, KQL string), `Timespan` (optional ISO 8601 interval/duration, default 30 days back from now), `workspaceId` (optional GUID of a specific Log Analytics workspace; falls back to the caller's primary workspace if omitted, not found, or not accessible). [DOC S-zaka5sgl]
- If a time filter appears in both the query and `Timespan`, the shorter of the two spans is applied. [DOC S-zaka5sgl]
- Response is a `200 OK` with a `huntingQueryResults` object: `schema` (column name/type array) and `results` (row objects). [DOC S-zaka5sgl]
- Graph `runHuntingQuery` is available in the Global service and US Government L4/L5 (DOD) national clouds, not in China operated by 21Vianet. [DOC S-zaka5sgl]
- Legacy MDE `POST https://api.security.microsoft.com/api/advancedqueries/run`: body `{"Query": "<kql>"}`; permission `AdvancedQuery.Read.All` (application) or `AdvancedQuery.Read` (delegated); delegated tokens also need the Entra **View Data** role and device-group access. [DOC S-fnmkxefn]
- Legacy API limits: query data window 30 days; max 100,000 result rows; max query result size 50 MB (HTTP 400 "Query execution has exceeded the allowed result size" if exceeded); rate limit 45 calls/minute and 1,500 calls/hour per tenant; running-time budget 10 minutes per hour and 3 hours per day per tenant; a single request's max execution time is 200 seconds; HTTP 429 signals either the request-count or the CPU quota was reached. [DOC S-fnmkxefn]
- The MDE advanced hunting (`advancedqueries`) API is being retired in favor of the Graph security API's advanced hunting; retirement began January 2026, and after retirement completes the legacy API stops functioning — new and existing integrations should migrate to `runHuntingQuery`. [DOC S-fnmkxefn]
- The legacy API's regional low-latency hosts mirror the machine API's (`us.`, `eu.`, `uk.`, `au.`, `swa.`, `ina.`, `aea.` `api.security.microsoft.com`). [DOC S-fnmkxefn]
- The `advancedqueries` rate limit (45 calls/min) is lower than the machine API's 100 calls/min documented in `defender/permissions-limits.md`; both share the 1,500 calls/hour figure. [DER S-fnmkxefn, S621: comparing the two cited limits]

## Reference
- `defender/machine-resource.md` — `DeviceInfo` join columns (`AadDeviceId`, `JoinType`) for the `Machine` REST resource; see its Reference section for the back-link to this article.
- `defender/permissions-limits.md` — MDE API base URI, regional hosts, `WindowsDefenderATP` resource, and the machine-API rate limit (100/min, 1,500/h) that the legacy `advancedqueries` limits (45/min, 1,500/h) sit alongside; see its Reference section for the back-link to this article.
- Table reference: `advanced-hunting-tables.csv` (table, kind, what it records, key columns, source).
- `defender/asr-and-antivirus.md` — ASR rule GUIDs/modes/exclusions and the `AsrX...Audited`/`Blocked` advanced-hunting `ActionType` values this article's `DeviceEvents` query pattern matches; see its Reference section for the back-link to this article.
- Re-confirmed 2026-09-26: no distinct retention or refresh cycle is documented anywhere for `DeviceTvmSoftwareVulnerabilitiesKB` (or the other KB-suffixed tables) versus its non-KB counterpart — the table's own reference page states only that it is "populated by records from Microsoft Defender for Endpoint" and, like `DeviceTvmSoftwareVulnerabilities`, is **not ingested into Microsoft Sentinel** (exposed there for schema visibility/autocomplete only, so Sentinel queries against it return no results); both tables otherwise follow the standard advanced-hunting 30-day raw-data retention. [DOC S-elscbjku]
- `windows/event-forwarding-sysmon.md` — WEF/WEC subscription setup and Sysmon event IDs/channel for devices whose events land in advanced hunting's `DeviceEvents`/`DeviceProcessEvents`-style tables via a SIEM or Sentinel pipeline; see its Reference section for the back-link to this article.
- `security/vulnerability-prioritization.md` — CVSS/EPSS/KEV/SSVC and the CVE data APIs (NVD, MSRC CVRF) that complement the `DeviceTvm*` exposure/severity data in this article; see its Reference section for the back-link to this article.
- `logs/microsoft-sentinel.md` — Sentinel analytics rules (Scheduled/NRT), data tiers/retention and ASIM normalization that sit alongside this article's Defender XDR advanced-hunting surface and the XDR default tier's 30-day retention; see its Reference section for the back-link to this article.

## Examples
KQL — latest known state per device (entity table pattern):
```kusto
DeviceInfo
| extend IngestionTime = ingestion_time()
| where isnotempty(OSPlatform)
| summarize arg_max(IngestionTime, *) by DeviceId
```

KQL — failed interactive/RDP logons in the last day:
```kusto
DeviceLogonEvents
| where Timestamp > ago(1d)
| where ActionType == "LogonFailed"
| where LogonType in ("Interactive", "RemoteInteractive")
| project Timestamp, DeviceName, AccountName, AccountDomain, RemoteIP, FailureReason
```

KQL — PowerShell launching with an encoded command:
```kusto
DeviceProcessEvents
| where Timestamp > ago(7d)
| where FileName in~ ("powershell.exe", "pwsh.exe")
| where ProcessCommandLine has "-EncodedCommand" or ProcessCommandLine has "-enc"
| project Timestamp, DeviceName, AccountName, ProcessCommandLine, InitiatingProcessFileName
```

KQL — devices with critical unpatched CVEs (TVM):
```kusto
DeviceTvmSoftwareVulnerabilities
| where VulnerabilitySeverityLevel == "Critical"
| where isnotempty(RecommendedSecurityUpdateId)
| summarize CriticalCves = dcount(CveId) by DeviceId, DeviceName
| order by CriticalCves desc
```

Python (Graph `runHuntingQuery`, client-credentials placeholders):
```python
import requests

tenant_id = "00000000-0000-0000-0000-000000000000"
client_id = "00000000-0000-0000-0000-000000000000"
client_secret = "<client-secret>"

token = requests.post(
    f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
    data={
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://graph.microsoft.com/.default",
    },
).json()["access_token"]

query = (
    "DeviceProcessEvents "
    "| where InitiatingProcessFileName =~ 'powershell.exe' "
    "| project Timestamp, DeviceName, FileName, InitiatingProcessFileName "
    "| order by Timestamp desc | limit 10"
)
resp = requests.post(
    "https://graph.microsoft.com/v1.0/security/runHuntingQuery",
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    json={"Query": query, "Timespan": "P7D"},
)
resp.raise_for_status()
print(resp.json()["results"])
```

PowerShell (`Microsoft.Graph.Security`), engineer `jan.kowalski`:
```powershell
Import-Module Microsoft.Graph.Security
Connect-MgGraph -Scopes "ThreatHunting.Read.All"

$params = @{
    Query = "DeviceInfo | where DeviceName == 'PL-LT-00123.corp.example.com' | project Timestamp, DeviceId, OSPlatform, JoinType"
}
Start-MgSecurityHuntingQuery -BodyParameter $params
```
