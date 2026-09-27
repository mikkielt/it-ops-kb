---
topic: defender/response-actions-api
priority: P1
applies_to: "Microsoft Defender for Endpoint API v1.0 (api.security.microsoft.com), docs retrieved 2026-09-26"
retrieved_utc: 2026-09-27
sources: [S-ipjyevd4, S-7zqska24, S-irvlwznc, S-drrejdmz, S-uv2mdacd, S-o76pzpoe, S-x3it6rkh, S-4ccloker, S-hvfrvt73, S-kw755ajt, S-yksr3dnu, S-4qod6hyu, S-ad63a4vv, S-mcsdxl4e, S623, S-x6wwggq6, S-mx6w5ffh, S-bxbx2kp5]
status: complete
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
- Isolate: `POST /api/machines/{id}/isolate`, body `Comment` (required) + `IsolationType` (allowed values `Full`, `Selective`, `UnManagedDevice`; the page does not mark it required); permission `Machine.Isolate` (app or delegated, display name "Isolate machine"). [DOC S-ipjyevd4]
- Full isolation: Windows 10 1703+/Windows 11, and all supported Linux devices; Selective isolation: Windows 10 1709+/Windows 11. [DOC S-ipjyevd4]
- Calling isolate on an unmanaged device triggers "contain device from the network"; `IsolationType` must be `UnManagedDevice`. [DOC S-ipjyevd4]
- Isolate/restrict/scan/quarantine delegated calls additionally require portal role **Active remediation actions** and device-group access. [DOC S-ipjyevd4, S-irvlwznc, S-uv2mdacd, S-4ccloker]
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
- Get machine action by ID: `GET /api/machineactions/{id}`, permission `Machine.ReadWrite.All` (app) / `Machine.ReadWrite` (delegated, role **View Data**); returns 404 if not found. [DOC S-yksr3dnu]
- Live response run: `POST /api/machines/{machine_id}/runliveresponse`, body `Comment` + `Commands` array of `PutFile`/`RunScript`/`GetFile` (must appear in that order, no repetition limit); permission `Machine.LiveResponse`. [DOC S-ad63a4vv]
- Live response API rate limit is **10 calls/minute** and 50 concurrently running sessions; excess requests get HTTP 429. [DOC S-ad63a4vv]
- If the target machine is offline, a live response run request is queued for up to 2 hours; commands run one at a time (can't be queued within a session); a `RunScript` command times out after 10 minutes; a second live response request on a machine already running one returns HTTP 400 `ActiveRequestAlreadyExists`. [DOC S-ad63a4vv]
- Live response actions initiated from the device page in the portal are not visible in/available via the `machineactions` API. [DOC S-ad63a4vv, S-mcsdxl4e]
- Live response session UI limits (distinct from the API launch call): sessions inactive-timeout after 30 minutes, max 50 live response sessions at a time (the page does not say per tenant or per user), a user can start up to 5 concurrent sessions, a device can only be in one session at a time. [DOC S-mcsdxl4e]
- Live response individual command time limit is 10 minutes, except `getfile`, `findfile`, and `run`, which allow 30 minutes. [DOC S-mcsdxl4e]
- Live response file size limits: `getfile` 3 GB, `fileinfo` 30 GB, `library` 250 MB (5 MB default in US Government cloud), `putfile` 300 MB on Windows / 10 MB on other platforms. [DOC S-mcsdxl4e]
- Live response requires the capability enabled on the Advanced features settings page (only admins/users with "Manage Portal Settings" can enable it); unsigned PowerShell script execution is a separate opt-in toggle (signature check applies to PowerShell scripts only). [DOC S-mcsdxl4e]
- Portal RBAC: response actions need role **Active remediation actions** for isolate/unisolate/restrict/unrestrict/scan/quarantine, and **Alerts Investigation** for collectInvestigationPackage; list/get machine actions need **View Data**; offboard needs an appropriate assigned role, least-privilege recommended over Global Administrator. [DOC S-ipjyevd4, S-7zqska24, S-irvlwznc, S-drrejdmz, S-uv2mdacd, S-4ccloker, S-o76pzpoe, S-kw755ajt, S-yksr3dnu, S-x3it6rkh]
- The isolate, unisolate, restrict, unrestrict, scan, collect, offboard, stop-and-quarantine and get-action pages each state 100 calls/minute and 1,500 calls/hour; the live response page states 10 calls/minute instead. [DOC S-ipjyevd4, S-7zqska24, S-irvlwznc, S-drrejdmz, S-uv2mdacd, S-o76pzpoe, S-x3it6rkh, S-4ccloker, S-yksr3dnu, S-ad63a4vv]
- Error codes any MDE API call may return: 429 TooManyRequests with `Retry-After` in seconds, 403 Forbidden/DisabledFeature/DisallowedOperation, 401 Unauthorized (see `defender/permissions-limits.md`). [DOC S623]
- Graph's current device response actions are in the **beta** custom detection rules API: a `detectionRule`'s `detectionAction.automatedActions` run against entities its hunting query returns, with `deviceAction`, `isolateDeviceAction` and `stopAndQuarantineFileAction` among the derived types (the device is named by a query-result column). Beta APIs are not supported for production use. [DOC S-bxbx2kp5, S-mx6w5ffh]
- The older beta `incidentTaskResponseAction` family (isolate, unisolate, restrict/unrestrict app execution, antivirus scan, collect investigation package, stop and quarantine file) is deprecated and removed on 2026-10-01, replaced by `automatedAction` on `detectionAction`; the rule's `responseActions` property goes on the same date. [DOC S-x6wwggq6, S-bxbx2kp5]
- So an agent that must isolate or scan one named device on demand calls the MDE API above: after 2026-10-01 the Graph beta types left act only on devices a detection rule's query matches, and none of the listed types covers live response. [DER S-bxbx2kp5, S-mx6w5ffh, S-x6wwggq6: derived from the listed action types and removal date]

## Reference
See `machine-actions.csv` (action, endpoint, app_permission, delegated_permission, body_params, rate_limit, source_id).
See `defender/permissions-limits.md` for the base MDE API rate limits (100/min, 1,500/h), error codes, and access modes — this article documents the per-action exceptions (live response 10/min, 50 concurrent sessions) and request bodies.
See `defender/machine-resource.md` for the `Machine` entity that these actions operate on (`{id}` in the URL) and its `GET /api/machines` filters.

## Examples
- SNIPPET: isolate a device (full isolation); context: MDE API v1.0, `Machine.Isolate` permission, body `Comment` + `IsolationType`; checked: no [DOC S-ipjyevd4]
```http
POST https://api.security.microsoft.com/api/machines/1e5bc9d7e413ddd7902c2932e418702b84d0cc07/isolate
Content-Type: application/json
Authorization: Bearer <token>

{
  "Comment": "Isolate machine due to alert 1234",
  "IsolationType": "Full"
}
```
- SNIPPET: poll a machine action's status; context: MDE API v1.0, `GET /api/machineactions/{id}`; checked: no [DOC S-hvfrvt73]
```http
GET https://api.security.microsoft.com/api/machineactions/{machineactionid}
```
- SNIPPET: run a live response session (RunScript then GetFile); context: MDE API v1.0, `Machine.LiveResponse` permission, 10 calls/minute rate limit, commands run in listed order; checked: no [DOC S-ad63a4vv]
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
