---
topic: intune/reports-export-api
priority: P2
applies_to: "Microsoft Intune reporting infrastructure, Microsoft Graph v1.0 and beta deviceManagementExportJob, docs retrieved 2026-09-26"
retrieved_utc: 2026-09-26
sources: [S-ls7jnt2q, S-7cnzcrhl, S-zh4stzuw, S-35rheh4q, S-vlctroci, S-scwd7dap, S-lqfdn2f7]
status: complete
files: [intune/export-report-names.csv]
---

# Intune report export API (Graph exportJobs)

## Summary
Intune reports migrated to its newer reporting infrastructure are exported through one top-level Graph endpoint, `deviceManagement/reports/exportJobs`, following a create-poll-download pattern: POST a job naming a `reportName` plus optional `filter`/`select`/`format`/`localizationType`, GET the job by `id` until `status` is `completed`, then download the file directly from the returned `url` (a short-lived Azure Blob Storage SAS URL delivering a compressed CSV or JSON). The report catalogue (`intune/export-report-names.csv`) lists the `reportName` values that back the same reports visible in the admin center under Reports/Devices/Apps, including compliance, device inventory, discovered apps, and Windows Update reports. A separate, older `deviceManagementReports` action surface (`getCachedReport`, `getCompliancePolicyNonComplianceReport`, etc.) returns cached per-request report streams without the job/poll pattern, for smaller or interactive queries. The legacy Intune Data Warehouse OData feed and its Power BI connector v1 are being retired (transition began April 2026); new Power BI integrations should use the OData Feed connector or Graph `exportJobs` instead.

## Facts

### exportJobs endpoint and create/poll/download flow
- Intune exports reports through `https://graph.microsoft.com/beta/deviceManagement/reports/exportJobs` and `https://graph.microsoft.com/v1.0/deviceManagement/reports/exportJobs`. [DOC S-ls7jnt2q]
- Create: `POST /deviceManagement/reports/exportJobs` with a JSON body naming `reportName`; the response is a `deviceManagementExportJob` with `status: notStarted` and `url: null`. [DOC S-ls7jnt2q, S-zh4stzuw]
- A successful create returns `201 Created`. [DOC S-zh4stzuw]
- Poll: `GET /deviceManagement/reports/exportJobs('{exportJobId}')` (or `/exportJobs/{exportJobId}`) repeatedly until the response's `status` becomes `completed`; possible `deviceManagementReportStatus` values are `unknown`, `notStarted`, `inProgress`, `completed`, `failed`. [DOC S-ls7jnt2q, S-zh4stzuw]
- On completion the job's `url` field is a temporary, presigned Azure Blob Storage URL (observed as `https://<account>.blob.core.windows.net/<container>/<jobId>.zip?sv=...&sig=...`); download it directly to get a compressed CSV (or JSON if `format: "json"` was requested). [DOC S-ls7jnt2q]
- `expirationDateTime` on the completed job gives the deadline for downloading the `url` before it expires; an uncompleted job shows `expirationDateTime: 0001-01-01T00:00:00Z`. [DOC S-ls7jnt2q]
- The `deviceManagementExportJob` resource supports the full CRUD method set: List, Get, Create, Update and Delete `deviceManagementExportJob`; in practice only Create (to start a job) and Get (to poll it) are needed for the export flow. [DOC S-35rheh4q]

### Request body parameters (deviceManagementExportJob create)
- `reportName` (String, required): the report to export; max length 2000 characters. [DOC S-zh4stzuw]
- `filter` (String, optional for most reports): OData-style filter string, e.g. `"(OwnerType eq '1')"`; max length 2000 characters. [DOC S-zh4stzuw, S-ls7jnt2q]
- `select` (String collection, optional): columns to include; max 256 column names, each up to 1000 characters; only column names valid for the given `reportName` are accepted. Microsoft's own guidance: always pass `select` explicitly rather than relying on default columns, because default columns of any report export are not a stable contract. [DOC S-zh4stzuw, S-ls7jnt2q]
- `format` (`deviceManagementReportFileFormat`, optional): `csv` (default) or `json`; the v1.0 enum additionally lists `pdf` and `unknownFutureValue` as possible values though the export flow itself only documents csv/json. [DOC S-zh4stzuw]
- `localizationType` (`deviceManagementExportJobLocalizationType`, optional): `localizedValuesAsAdditionalColumn` (default) or `replaceLocalizableValues`. [DOC S-zh4stzuw, S-ls7jnt2q]
- `snapshotId` (String, optional): identifies a subset of the dataset (a `sessionId` or a `CachedReportConfiguration` id); when a `sessionId` is given, `filter`/`select`/`orderBy` apply to that session's data; `filter`/`select`/`orderBy` cannot be combined with a `CachedReportConfiguration` id; max length 128 characters. [DOC S-zh4stzuw]
- Read-only response properties: `id`, `status`, `url`, `requestDateTime`, `expirationDateTime`. [DOC S-zh4stzuw]

### Localization behavior
- `localizedValuesAsAdditionalColumn` (default): each localizable column is duplicated as `<Column>` (a stable enum/number, locale-independent) and `<Column>_loc` (a human-readable, locale-dependent string) - e.g. `OS=1` alongside `OS_loc=Windows`. [DOC S-ls7jnt2q]
- `replaceLocalizableValues`: returns a single column per localizable attribute, containing the localized value directly (e.g. `OS=Windows`) instead of the raw enum. [DOC S-ls7jnt2q]
- The `Devices` and `DevicesWithInventory` report types do not honor `localizationType` at all, for legacy compatibility reasons. [DOC S-ls7jnt2q]

### Permissions (create deviceManagementExportJob)
- Delegated (work or school account) and Application: one of `DeviceManagementConfiguration.ReadWrite.All`, `DeviceManagementApps.ReadWrite.All`, `DeviceManagementManagedDevices.ReadWrite.All`. [DOC S-zh4stzuw]
- Delegated (personal Microsoft account): not supported. [DOC S-zh4stzuw]
- Reading/polling an export job (`Get`/`List deviceManagementExportJob`) additionally accepts the matching `.Read.All` scopes (`DeviceManagementConfiguration.Read.All`, `DeviceManagementManagedDevices.Read.All`, `DeviceManagementApps.Read.All`) alongside the ReadWrite scopes, per the equivalent `Get-MgDeviceManagementReportExportJob` cmdlet's documented permission table. [DOC S-vlctroci]
- Requires an active Intune license on the tenant, same as other Intune Graph APIs. [DOC S-zh4stzuw]
- Available in Global service, US Government L4, US Government L5 (DOD), and China operated by 21Vianet national cloud deployments. [DOC S-zh4stzuw]

### Report catalogue (reportName values)
- The full `reportName` -> admin center report mapping is a large reference table on Microsoft Learn; a curated subset covering compliance, devices, apps, Windows Update, Autopilot, co-management, certificates, enrollment, and remediation scripts is in `intune/export-report-names.csv` (columns: `reportName`, `contains`, `associated_admin_center_report`, `notes`, `source`). [DOC S-7cnzcrhl]
- Report names commonly appear with `V3`, `WithPF` (per-setting/policy-filter), and `WithPFV3` suffix variants for the same underlying report family (e.g. `DeviceConfigurationPolicyStatuses` / `...V3` / `...WithPF` / `...WithPFV3`); the CSV notes column flags known variants but does not enumerate every suffix combination. [DOC S-7cnzcrhl]
- Example: exporting the `Devices` report accepts columns such as `DeviceName`, `managementAgent`, `ownerType`, `complianceState`, `OS`, `OSVersion`, `LastContact`, `UPN`, `DeviceId` via `select`. [DOC S-ls7jnt2q]

### getCachedReport and other deviceManagementReports actions (no job/poll pattern)
- `deviceManagementReports` (the `deviceManagement/reports` singleton) exposes actions that stream a report directly without the create/poll/download pattern: `getCachedReport`, `getCompliancePolicyNonComplianceSummaryReport`, `getCompliancePolicyNonComplianceReport`, `getComplianceSettingNonComplianceReport`, `getHistoricalReport`, plus the `exportJobs` relationship documented above. [DOC S-vlctroci]
- `getCachedReport`: `POST /deviceManagement/reports/getCachedReport` with body properties `id`, `select`, `groupBy`, `orderBy`, `search`, `skip`, `top`; returns `200 OK` with a Stream. Same permission set as export job creation, plus the matching `.Read.All` scopes. [DOC S-vlctroci]
- These actions suit smaller, interactive, already-cached report queries; the `exportJobs` pattern is preferred for full/bulk dataset export because it is not limited by pagination and delivers the whole dataset as one file. [DOC S-vlctroci]

### Throttling
- The `exportJobs` API supports up to 100 requests per tenant per minute across all users and apps in the tenant. [DOC S-ls7jnt2q]
- Per user (delegated): up to 8 requests per minute; additional requests by the same user in that minute are throttled. [DOC S-ls7jnt2q]
- Per app (application permissions): up to 48 requests per minute; additional requests by the same app in that minute are throttled. [DOC S-ls7jnt2q]

### Intune Data Warehouse / Power BI (legacy, being retired)
- The Intune Data Warehouse is a separate, older OData-based reporting surface (daily-refreshed historical data), reachable via a per-tenant reporting service feed URL (`https://fef.{tenant}.manage.microsoft.com/ReportingService/DataWarehouseFEService/...?api-version=v1.0` or `=beta`), independent from the `exportJobs` Graph API. [DOC S-scwd7dap]
- The Intune Data Warehouse (beta) connector v1 in Power BI is being retired; the transition began in late April 2026 and runs gradually over two weeks. Power BI reports created after November 2025 already use connector v2 and are unaffected; older reports must migrate to connector v2 or the OData Feed connector before the transition completes, or lose data access through the beta connector. [DOC S-scwd7dap]
- Migration from connector v1: in Power BI Desktop, Transform Data > (each Intune query) > Advanced Editor; a data source of the form `Intune.Contents(x)` indicates connector v1 and must be replaced with `OData.Feed("<reporting_service_endpoint>", null, [Implementation="2.0", Query=[#"api-version"="v1.0"]])`; an optional `?maxHistoryDays=<n>` query parameter on the endpoint limits historical data pulled. [DOC S-lqfdn2f7]
- ConfigMgr-only co-managed data is not in the Intune Data Warehouse; ConfigMgr-side reporting needs the ConfigMgr AdminService / SQL views instead (cross-link `powerbi/configmgr-views.md`). [DOC S-scwd7dap]

## Reference
- `intune/compliance-policies.md`: the compliance policy settings, evaluation states and `windows10CompliancePolicy` Graph resource that the `DeviceCompliance`, `DeviceNonCompliance`, `DevicesWithoutCompliancePolicy` and `PolicyNonComplianceAgg` report families in `intune/export-report-names.csv` surface in bulk-exportable form; see that article's Reference for the back-link to this one.
- `windows/windows-update-management.md`: the update-ring, feature-update and quality-update (hotpatch/expedite) policy surface whose per-device rollout state the `FeatureUpdateDeviceState`, `FeatureUpdatePolicyStatusSummary`, `QualityUpdateDeviceStatusByPolicy` and `DriverUpdatePolicyStatusSummary` reports export.
- `powerbi/scheduled-refresh.md`, `powerbi/configmgr-views.md`, `powerbi/on-prem-gateway-sql.md`, `powerbi/row-level-security.md`: once an exported CSV/JSON or the OData Feed connector lands data in Power BI, those articles cover the semantic-model refresh cadence, ConfigMgr-side SQL views for co-managed data, on-prem gateway auth and RLS options for the resulting report.
- `graph/batching-and-query.md`: the `exportJobs` create/poll/download calls are ordinary single Graph requests, not eligible for `$batch` sequencing across the polling wait; a fleet of parallel export jobs across many `reportName` values should still respect the per-tenant/per-app throttling described in that article's general Graph throttling guidance (see also `graph/throttling.md`).
- `intune/co-management.md`: `ComanagedDeviceWorkloads` and `ComanagementEligibilityTenantAttachedDevices` export the co-management workload and eligibility state that article documents from the ConfigMgr/Intune split-management side.

## Examples
Create an export job for the Devices report (Python, `requests`, delegated token in `token`; tenant `00000000-0000-0000-0000-000000000000`, placeholders only):
```python
import time
import requests

GRAPH = "https://graph.microsoft.com/beta"
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# 1. Create the export job
create_body = {
    "reportName": "DeviceNonCompliance",
    "format": "csv",
    "localizationType": "replaceLocalizableValues",
    "select": [
        "DeviceName",
        "UPN",
        "OS",
        "OSVersion",
        "InGracePeriodUntilDateTime",
    ],
}
resp = requests.post(f"{GRAPH}/deviceManagement/reports/exportJobs", headers=headers, json=create_body)
resp.raise_for_status()
job = resp.json()
job_id = job["id"]

# 2. Poll until completed
while True:
    poll = requests.get(f"{GRAPH}/deviceManagement/reports/exportJobs('{job_id}')", headers=headers)
    poll.raise_for_status()
    job = poll.json()
    if job["status"] == "completed":
        break
    if job["status"] == "failed":
        raise RuntimeError(f"export job {job_id} failed")
    time.sleep(5)

# 3. Download the compressed report from the temporary blob URL
download = requests.get(job["url"])
download.raise_for_status()
with open(f"/tmp/{job_id}.zip", "wb") as fh:
    fh.write(download.content)
```

Same flow with the Microsoft Graph PowerShell SDK (placeholders only):
```powershell
Connect-MgGraph -Scopes "DeviceManagementConfiguration.Read.All"

$body = @{
    reportName = "FeatureUpdateDeviceState"
    format     = "csv"
    select     = @("DeviceName", "UPN", "FeatureUpdateVersion", "LastUpdatedAlertStatusDateTimeUTC")
}
$job = New-MgDeviceManagementReportExportJob -BodyParameter $body

do {
    Start-Sleep -Seconds 5
    $job = Get-MgDeviceManagementReportExportJob -DeviceManagementExportJobId $job.Id
} while ($job.Status -eq "inProgress" -or $job.Status -eq "notStarted")

if ($job.Status -eq "completed") {
    Invoke-WebRequest -Uri $job.Url -OutFile "C:\reports\$($job.Id).zip"
}
```
