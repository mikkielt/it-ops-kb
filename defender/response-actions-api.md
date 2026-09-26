---
topic: defender/response-actions-api
priority: P1
applies_to: "Microsoft Defender for Endpoint API v1.0 (api.security.microsoft.com), docs retrieved 2026-09-26"
retrieved_utc: 2026-09-26
sources: [S-ipjyevd4, S-7zqska24, S-irvlwznc, S-drrejdmz, S-uv2mdacd, S-o76pzpoe, S-x3it6rkh, S-4ccloker, S-hvfrvt73, S-kw755ajt, S-yksr3dnu, S-4qod6hyu, S-ad63a4vv, S-mcsdxl4e]
status: partial
files: [defender/machine-actions.csv]
---
# Defender for Endpoint API: machine response actions (isolate, scan, live response)

## Summary
Each response action is a `POST /api/machines/{id}/<action>` call that returns **201 Created** with a
`MachineAction` object (async; poll `GET /api/machineactions/{id}` for `status`). All actions share the
100 calls/minute, 1,500 calls/hour rate limit from `defender/permissions-limits.md` except live response,
which has its own 10 calls/minute cap and a 50-concurrent-session ceiling. Body parameters are case-sensitive
(`defender/permissions-limits.md:25`). Full call table: `machine-actions.csv`.

## Facts
- Isolate: `POST /api/machines/{id}/isolate`, body `Comment` (required) + `IsolationType` (required: `Full`, `Selective`, or `UnManagedDevice`); permission `Machine.Isolate` (app or delegated, display name "Isolate machine"). [DOC S-ipjyevd4]
- Full isolation: Windows 10 1703+/Windows 11, and all supported Linux devices; Selective isolation: Windows 10 1709+/Windows 11. [DOC S-ipjyevd4]
- Calling isolate on an unmanaged device triggers "contain device from the network"; `IsolationType` must be `UnManagedDevice`. [DOC S-ipjyevd4]
- Isolate/restrict/scan/quarantine delegated calls additionally require portal role **Active remediation actions** and device-group access. [DOC S-ipjyevd4]
- Unisolate: `POST /api/machines/{id}/unisolate`, body `Comment` (required); same `Machine.Isolate` permission; repeat calls return "pending machine action" or HTTP 400 "Action is already in progress". [DOC S-7zqska24]
- RestrictCodeExecution: `POST /api/machines/{id}/restrictCodeExecution`, body `Comment` (required); permission `Machine.RestrictExecution`; requires Windows 10 1709+/Windows 11, Microsoft Defender Antivirus in use, and a WDAC-compliant code integrity policy. [DOC S-irvlwznc]
- UnrestrictCodeExecution ("Remove app restriction"): `POST /api/machines/{id}/unrestrictCodeExecution`, body `Comment` (required); permission `Machine.RestrictExecution`. [DOC S-drrejdmz]
- RunAntiVirusScan: `POST /api/machines/{id}/runAntiVirusScan`, body `Comment` (required) + `ScanType` (required: `Quick` or `Full`); permission `Machine.Scan`; supported on Windows 10 1709+/11, Linux servers, macOS; runs even if Defender AV is in passive mode alongside another AV. [DOC S-uv2mdacd]
- CollectInvestigationPackage: `POST /api/machines/{id}/collectInvestigationPackage`, body `Comment` (required); permission `Machine.CollectForensics`; delegated role needed is **Alerts Investigation** (not Active remediation actions); returns 400 if a collection is already running. [DOC S-o76pzpoe]
- Offboard: `POST /api/machines/{id}/offboard`, body `Comment` (required, 400 if missing); permission `Machine.Offboard`; on Windows the API only stops the sensor service and does not remove onboarding registry info the way an offboarding script does. [DOC S-x3it6rkh]
- Offboard supported OS: Windows 11/10 1703+, Windows Server 2019+ (and Server 2012 R2/2016 with the new unified agent), macOS 14+, supported Linux distributions. [DOC S-x3it6rkh]
- StopAndQuarantineFile: `POST /api/machines/{id}/StopAndQuarantineFile`, body `Comment` (required) + `Sha1` (required, SHA1 of the file); permission `Machine.StopAndQuarantine` **or** `Machine.ReadWrite.All` (application); requires Windows 10 1703+/11, file not trusted-publisher/Microsoft-signed, and Defender AV at least in passive mode. [DOC S-4ccloker]
- CancelMachineAction: `POST /api/machineactions/{machineactionid}/cancel`, body `Comment` (optional), cancels an action not yet in a final state; permission is any one of Machine.CollectForensics/Isolate/RestrictExecution/Scan/Offboard/StopAndQuarantine/LiveResponse; returns 200 OK with the action, or 404 if the action id isn't found. [DOC S-4qod6hyu]
- MachineAction resource: `id`, `type` (RunAntiVirusScan/Offboard/LiveResponse/CollectInvestigationPackage/Isolate/Unisolate/StopAndQuarantineFile/RestrictCodeExecution/UnrestrictCodeExecution), `scope` (Full/Selective for isolation, Quick/Full for AV scan), `requestor`, `requestorComment`, `cancellationRequestor`, `cancellationComment`, `status` (Pending/InProgress/Succeeded/Failed/TimeOut/Cancelled), `machineId`, `computerDnsName`, `creationDateTimeUtc`, `cancellationDateTimeUtc`, `lastUpdateDateTimeUtc`, `title`, `externalID`, `requestSource`, `commands`, `relatedFileInfo` (`fileIdentifier` + `fileIdentifierType`: Sha1/Sha256/Md5). [DOC S-hvfrvt73]
- List machine actions: `GET /api/machineactions`, permission `Machine.ReadWrite.All` (app) / `Machine.ReadWrite` (delegated, role **View Data**); OData `$filter` on id, status, machineId, type, requestor, creationDateTimeUtc; `$top` max 10,000, `$skip`; same 100/min 1,500/h limit. [DOC S-kw755ajt]
- Get machine action by ID: `GET /api/machineactions/{id}`, same permissions as list; returns 404 if not found. [DOC S-yksr3dnu]
- Live response run: `POST /api/machines/{machine_id}/runliveresponse`, body `Comment` + `Commands` array of `PutFile`/`RunScript`/`GetFile` (must appear in that order, no repetition limit); permission `Machine.LiveResponse`. [DOC S-ad63a4vv]
- Live response API rate limit is **10 calls/minute** (not the general 100/min) and 50 concurrently running sessions; excess requests get HTTP 429. [DOC S-ad63a4vv]
- If the target machine is offline, a live response run request is queued for up to 2 hours; commands run one at a time (can't be queued within a session); a `RunScript` command times out after 10 minutes; a second live response request on a machine already running one returns HTTP 400 `ActiveRequestAlreadyExists`. [DOC S-ad63a4vv]
- Live response actions initiated from the device page in the portal are not visible in/available via the `machineactions` API. [DOC S-ad63a4vv, S-mcsdxl4e]
- Live response session UI limits (distinct from the API launch call): sessions inactive-timeout after 30 minutes, max 50 live response sessions at a time (the page does not say per tenant or per user), a user can start up to 5 concurrent sessions, a device can only be in one session at a time. [DOC S-mcsdxl4e]
- Live response individual command time limit is 10 minutes, except `getfile`, `findfile`, and `run`, which allow 30 minutes. [DOC S-mcsdxl4e]
- Live response file size limits: `getfile` 3 GB, `fileinfo` 30 GB, `library` 250 MB (5 MB default in US Government cloud), `putfile` 300 MB on Windows / 10 MB on other platforms. [DOC S-mcsdxl4e]
- Live response requires the capability enabled on the Advanced features settings page (only admins/users with "Manage Portal Settings" can enable it); unsigned PowerShell script execution is a separate opt-in toggle (signature check applies to PowerShell scripts only). [DOC S-mcsdxl4e]
- Portal RBAC: response actions need role **Active remediation actions** for isolate/unisolate/restrict/unrestrict/scan/quarantine, and **Alerts Investigation** for collectInvestigationPackage; list/get machine actions need **View Data**; offboard needs an appropriate assigned role, least-privilege recommended over Global Administrator. [DOC S-ipjyevd4,S-o76pzpoe,S-kw755ajt,S-x3it6rkh]
- All these action calls are subject to the base rate limit and error codes documented in `defender/permissions-limits.md` (429 with `Retry-After`, 403 Forbidden/DisabledFeature/DisallowedOperation, 401 Unauthorized) except live response's own tighter 10/min cap. [DOC S-ad63a4vv; see defender/permissions-limits.md]
- No Microsoft Graph security API equivalent for these MDE machine response actions is documented on these pages; Graph exposes `security.deviceEvidence` read-only data (`defender/machine-resource.md:29`) but not isolate/scan/live-response actions. [UNK]

## Reference
See `machine-actions.csv` (action, endpoint, app_permission, delegated_permission, body_params, rate_limit, source_id).
See `defender/permissions-limits.md` for the base MDE API rate limits (100/min, 1,500/h), error codes, and access modes — this article documents the per-action exceptions (live response 10/min, 50 concurrent sessions) and request bodies.
See `defender/machine-resource.md` for the `Machine` entity that these actions operate on (`{id}` in the URL) and its `GET /api/machines` filters.

## Examples
Isolate a device:
```http
POST https://api.security.microsoft.com/api/machines/1e5bc9d7e413ddd7902c2932e418702b84d0cc07/isolate
Content-Type: application/json
Authorization: Bearer <token>

{
  "Comment": "Isolate machine due to alert 1234",
  "IsolationType": "Full"
}
```
Poll the action:
```http
GET https://api.security.microsoft.com/api/machineactions/{machineactionid}
```
Live response: put a file, run a script, retrieve output (rate limit 10 calls/minute):
```json
POST https://api.security.microsoft.com/api/machines/PL-LT-00123/runliveresponse
{
  "Commands": [
    {"type": "RunScript", "params": [{"key": "ScriptName", "value": "minidump.ps1"}, {"key": "Args", "value": "OfficeClickToRun"}]},
    {"type": "GetFile", "params": [{"key": "Path", "value": "C:\\windows\\TEMP\\OfficeClickToRun.dmp.zip"}]}
  ],
  "Comment": "Testing Live Response API"
}
```
