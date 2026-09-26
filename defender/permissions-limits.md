---
topic: defender/permissions-limits
priority: P1
applies_to: "Microsoft Defender for Endpoint API v1.0, docs 2020-12-18 .. 2026-06-28"
retrieved_utc: 2026-09-26
sources: [S621, S622, S623, S624, S625, S626]
status: complete
---
# Defender for Endpoint API: permissions and rate limits (machine APIs)

## Summary
Machine APIs use the `WindowsDefenderATP` resource. List machines: `Machine.Read.All` / `Machine.ReadWrite.All`
(application) or `Machine.Read` / `Machine.ReadWrite` (delegated) + the user's **View Data** role and device-group scope.
Rate limit: 100 calls/minute and 1,500 calls/hour per API; 429 with `Retry-After`. Base URI `https://api.security.microsoft.com/api`,
regional hosts available. Some APIs still need tokens for the legacy resource `https://api.securitycenter.microsoft.com`.

## Facts
- List machines permissions: Application Machine.Read.All ('Read all machine profiles') or Machine.ReadWrite.All; Delegated Machine.Read ('Read machine information') or Machine.ReadWrite. [DOC S621]
- Delegated: user needs at least role permission **View Data**; responses include only devices the user can access via device groups (device groups exist in Plan 1 and Plan 2). [DOC S621]
- Get machine by ID lists only Machine.ReadWrite.All (application) and Machine.ReadWrite (delegated). [DOC S622]
- Rate limit, list machines: 100 calls per minute and 1,500 calls per hour; max page size 10,000. [DOC S621]
- Rate limit, get machine by ID: 100 calls per minute and 1500 calls per hour. [DOC S622]
- Throttling returns HTTP 429 TooManyRequests ("quota limit either by number of requests or by CPU") with a `Retry-After` header in seconds; resubmitting sooner yields 429 again. [DOC S623]
- 403 codes: Forbidden (insufficient permission), DisabledFeature, DisallowedOperation; 401 Unauthorized for invalid/expired token; error body carries `target` correlation id. [DOC S623]
- Body parameters are case-sensitive. [DOC S623]
- Base URI `https://api.security.microsoft.com`, `/api` prefix, current version V1.0 (`/api/v1.0/...`); no version = latest; regional hosts us., eu., uk., au., swa., ina., aea.api.security.microsoft.com. [DOC S624]
- Access modes: application context (recommended, daemon) or user context (delegated, native app). [DOC S625]
- User context: register app, add API permission from **WindowsDefenderATP** (type the name; not in the default list), grant consent; the user also needs matching portal RBAC ("if you can do it in the portal you can do it in the API"). [DOC S626]
- Some MDE APIs still require tokens for legacy resource `https://api.securitycenter.microsoft.com`; audience mismatch gives 403 even on api.security.microsoft.com. [DOC S626]

## Reference
| Call | App permission | Delegated permission | Limit |
|---|---|---|---|
| GET /api/machines | Machine.Read.All, Machine.ReadWrite.All | Machine.Read, Machine.ReadWrite | 100/min, 1,500/h [S621] |
| GET /api/machines/{id} | Machine.ReadWrite.All | Machine.ReadWrite | 100/min, 1,500/h [S622] |

See `defender/advanced-hunting.md` for the legacy `advancedqueries` hunting API's own rate limit (45/min, 1,500/h — lower per-minute than the machine API above) and the current Graph `runHuntingQuery` endpoint.
See `defender/response-actions-api.md` for the machine response action APIs (isolate, restrictCodeExecution, runAntiVirusScan, collectInvestigationPackage, offboard, StopAndQuarantineFile, live response) that reuse this article's base rate limit and error codes.

## Examples
Engineer `jan.kowalski` (delegated token, permission Machine.Read) calls `GET https://eu.api.security.microsoft.com/api/machines?$filter=computerDnsName eq 'pl-lt-00123.corp.example.com'`; on 429 wait `Retry-After` seconds.
