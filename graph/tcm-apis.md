---
topic: graph/tcm-apis
priority: P3
applies_to: "Microsoft Graph v1.0 and beta, Tenant Configuration Management (docs-contrib @ 4ad99fd3, metadata @ b8cbef92)"
retrieved_utc: 2026-09-25
sources: [S940, S941, S942, S943, S944, S945, S946, S947, S948, S949, S950, S951, S952, S953, S954, S955, S956, S957]
status: complete
files: [graph/tcm-csdl-v1.0.xml, graph/tcm-csdl-beta.xml]
---

# Microsoft Graph Tenant Configuration Management (TCM) APIs

## Summary
TCM monitors tenant settings (Defender, Entra, Exchange, Intune, Purview, Teams) against a declarative baseline and reports drift;
snapshot jobs export current settings. It lives under `/admin/configurationManagement` and is present in **both v1.0 and beta**
(CSDL and reference pages). Monitors run every 6 hours at fixed GMT times; max 30 monitors and 800 monitored resources/day per tenant;
snapshots max 20,000 resources/month, 12 visible jobs, 7-day retention. It covers cloud tenant settings, not device-local state.

## Facts
- Supported workloads: Microsoft Defender, Microsoft Entra, Exchange Online, Intune, Purview, Teams. [DOC S940]
- Resources exist in v1.0 (`Namespace: microsoft.graph`) as well as beta; the v1.0 and beta API overview pages differ only in the beta disclaimer. [DOC S942, S943]
- The v1.0 and beta CSDL both define `configurationMonitor`, `configurationMonitoringResult`, `configurationDrift`, `configurationSnapshotJob`, `configurationBaseline`, `driftedProperty`. [DOC S956, S957]
- Admins must first add the TCM service principal (appId `03b07b79-c5bc-4b5e-9bfa-13acf4a99998`) to the tenant and grant it permissions; the `M365 Admin Services` SP (`6b91db1b-f05b-405a-a0b2-e3f60b28d645`) must also exist. [DOC S941]
- The setup page says this service principal step applies "during public preview". [DOC S941]
- Graph permissions: monitor management — delegated any privileged role, or application `ConfigurationMonitoring.Read.All` / `ConfigurationMonitoring.ReadWrite.All`; snapshots — `ConfigurationMonitoring.ReadWrite.All`. [DOC S941]
- List drifts: least-privileged `ConfigurationMonitoring.Read.All` (delegated work/school and application); personal accounts not supported. [DOC S951]
- Create monitor and create snapshot: `ConfigurationMonitoring.ReadWrite.All` only. [DOC S952, S954]
- Up to 30 `configurationMonitor` objects per tenant. [DOC S942]
- Each monitor runs at a fixed six-hour interval; frequency cannot be changed. [DOC S942]
- Monitors are picked up at 06:00, 12:00, 18:00 and 00:00 GMT; a new or updated monitor runs at the next slot. [DOC S944]
- Up to 800 monitored configuration resources per day per tenant across all monitors (resources per cycle × 4 cycles). [DOC S942]
- Updating a monitor's baseline deletes all its previous monitoring results and drifts. [DOC S942]
- Active drifts are retained; a fixed drift is deleted 30 days after it is resolved. [DOC S942]
- Snapshots: max 20,000 resources extracted per tenant per month (cumulative), no per-day snapshot count limit, max 12 visible snapshot jobs (delete to create more), each snapshot kept at most 7 days. [DOC S942]
- `configurationMonitor.mode` has only `monitorOnly` (plus `unknownFutureValue`); default `monitorOnly`. [DOC S944]
- `configurationMonitor.status`: v1.0 doc lists `active`, `inactive`; the beta doc lists only `active`; both CSDLs include `inactive`. [DOC S944, S945, S956, S957] (see conflicts)
- `configurationDrift` fields: `baselineResourceDisplayName`, `driftedProperties` (`$select` only), `firstReportedDateTime`, `monitorId`, `resourceInstanceIdentifier` (`$select` only), `resourceType`, `status` (`active`, `fixed`), `tenantId`. [DOC S947]
- `driftedProperty`: `propertyName`, `currentValue` (Json), `desiredValue` (Json). [DOC S950]
- `configurationMonitoringResult`: `driftsCount`, `errorDetails`, `monitorId`, `runInitiationDateTime`, `runCompletionDateTime`, `runStatus` (`successful`, `partiallySuccessful`, `failed`). [DOC S948]
- `configurationSnapshotJob.status`: `notStarted`, `running`, `succeeded`, `failed`, `partiallySuccessful`; `resourceLocation` is the snapshot file URL (`$select` only). [DOC S946]
- Create snapshot: `POST /admin/configurationManagement/configurationSnapshots/createSnapshot` with `displayName` (required), `description`, `resources` (required, resource type names); runs asynchronously. [DOC S953, S946]
- Baseline resources use `resourceType` names such as `microsoft.exchange.accepteddomain` and a `properties` object. [DOC S954]
- Intune resource types documented for TCM: 68 include sections; the complete schema is published at `https://json.schemastore.org/utcm-monitor.json`. [DOC S955]
- TCM covers Microsoft 365 tenant configuration, not Windows device-local settings; nothing in these pages mentions ConfigMgr or on-device DSC. [DER S940,S942] (workload list is cloud services only)

## Reference
Endpoints (v1.0 and beta; base `https://graph.microsoft.com/{v1.0|beta}`) [S942, S953, S954]:

| Method | Path |
|---|---|
| GET/POST | /admin/configurationManagement/configurationMonitors |
| GET/PATCH/DELETE | /admin/configurationManagement/configurationMonitors/{id} |
| GET | /admin/configurationManagement/configurationMonitors/{id}/baseline |
| GET | /admin/configurationManagement/configurationMonitoringResults[/{id}] |
| GET | /admin/configurationManagement/configurationDrifts[/{id}] |
| GET | /admin/configurationManagement/configurationSnapshotJobs[/{id}] ; DELETE /{id} |
| GET | /admin/configurationManagement/configurationSnapshots |
| POST | /admin/configurationManagement/configurationSnapshots/createSnapshot |

Artifacts: `tcm-csdl-v1.0.xml`, `tcm-csdl-beta.xml` (CSDL excerpts, TCM types only). Differences between them: `monitorMode`
member values (v1.0 `monitorOnly=0, unknownFutureValue=1`; beta `monitorOnly=1, unknownFutureValue=5`) and `baselineResource.resourceType`
Nullable=false only in v1.0.

Per-workload resource pages: `concepts/utcm-{entra,exchange,intune,securityandcompliance,teams}-resources.md` in docs-contrib (Intune page = S955).

## Examples
```http
GET https://graph.microsoft.com/v1.0/admin/configurationManagement/configurationDrifts?$filter=status eq 'active'&$select=id,resourceType,baselineResourceDisplayName,driftedProperties
```
Tenant `00000000-0000-0000-0000-000000000000`.
