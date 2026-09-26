---
topic: logs/azure-monitor-agent
priority: P2
applies_to: "Azure Monitor Agent (AMA), Data Collection Rules API 2024-03-11, docs ms.date through 2026-09"
retrieved_utc: 2026-09-26
sources: [S-luprngvc, S-me4bxp52, S-kguhudz7, S-6xjyyd4l, S-mix3xqam, S-m4gimryf, S-de5xdfvw, S-in4qr3cp, S-prybc22p, S-qvsjnnqo, S-r33zxv3s, S-5d3e2yck, S-3dcvyq2z]
status: complete
---

# Azure Monitor Agent (AMA) and Data Collection Rules

## Summary
Azure Monitor Agent (AMA) collects Windows event logs, performance counters, IIS/text/JSON log files and Syslog from
Azure VMs, Azure Arc-enabled servers and (via a separate MSI) Microsoft Entra-joined Windows clients, and delivers
them to Log Analytics per Data Collection Rule (DCR). A DCR declares `dataSources`, `destinations` and `dataFlows`
(with optional KQL `transformKql` transformations); it is linked to a target resource by a Data Collection Rule
Association (DCRA). A Data Collection Endpoint (DCE) is needed only for Private Link or a few data sources (Windows
Firewall Logs, Prometheus). The same DCR/DCE/DCRA plumbing also backs the Logs Ingestion API for direct REST
ingestion, and it fully replaces the retired Log Analytics agent (MMA/OMS). Event/channel names, WEF and Sysmon
config are `logs/sources.md` and `windows/event-forwarding-sysmon.md`; the vendor-neutral OTel `windows_event_log`
receiver is `logs/otel-collector-receivers.md`.

## Facts

### DCR structure and Windows event collection
- A DCR's `dataSources.windowsEventLogs` array collects Windows event log data; each entry has `name`, `streams`
  (`Microsoft-Event`, schema known so no stream declaration is needed) and `xPathQueries` (a list of XPath filters).
  [DOC S-luprngvc]
- Other DCR data source types: `iisLogs` (stream `Microsoft-W3CIISLog`, param `logDirectories`), `logFiles` (custom
  stream, params `filePatterns`, `format`: `json` or `text`), `performanceCounters` (streams `Microsoft-Perf` /
  `Microsoft-InsightsMetrics`, params `samplingFrequencyInSeconds`, `counterSpecifiers`), `syslog` (stream
  `Microsoft-Syslog` or `Microsoft-CommonSecurityLog` for CEF, params `facilityNames`, `logLevels`),
  `prometheusForwarder`, `eventHub`, and `extension` (extension-based, e.g. the AMA Sentinel connector). [DOC S-luprngvc]
- XPath entries are written `LogName!XPathQuery`, e.g. `Security!*[System[(EventID=4624 or EventID=4625)]]` or
  `Application!*[System[EventID=1035]]`. [DOC S-me4bxp52]
- AMA subscribes via the Windows `EvtSubscribe` API, so it cannot collect from Analytic/Debug channels (export to a
  workspace isn't possible for those). [DOC S-me4bxp52]
- AMA XPath queries support only XPath version 1.0. Test a query locally first with
  `Get-WinEvent -LogName 'Application' -FilterXPath $XPath`. [DOC S-3dcvyq2z, S-me4bxp52]
- `Get-WinEvent -FilterXPath` supports up to 23 expressions; Azure Monitor DCRs support up to 20 XPath expressions.
  [DOC S-me4bxp52]
- If the DCR's Windows Event data source includes the **Security** log, those events land in the `Event` table
  alongside System/Application events (not `SecurityEvent`); to get `SecurityEvent`-table events (used by Sentinel),
  enable the "Windows Security Events via AMA" connector, which uses the same AMA agent. [DOC S-me4bxp52]
- Sentinel's Windows Security Events via AMA connector offers prebuilt **Common** and **Minimal** event sets besides
  a fully custom XPath list. [DOC S-3dcvyq2z]
- Recommended baseline event levels: collect at least Critical/Error/Warning for Windows System and Application logs
  for alerting; add Information for trend analysis; Verbose is rarely useful. Equivalent guidance for Syslog:
  LOG_WARNING+ for alerting, Information for trends, LOG_DEBUG rarely useful. [DOC S-luprngvc]
- Use XPath filtering at the agent (not a downstream transformation) as the primary filter for efficiency and to
  avoid ingestion charges; a `dataFlows` transformation can still add calculated columns or further filtering.
  [DOC S-kguhudz7]

### Transformations
- A DCR transformation is a KQL query (`transformKql` on a `dataFlows` entry) that runs against each incoming record
  to filter, reshape, redact or enrich data before it reaches its destination; multi-stage transformations (preview)
  chain a client-side transformation on the data source with an ingestion-time transformation on the data flow.
  [DOC S-m4gimryf]
- Built-in processors include `parse.JsonPath` (columnName, `all` extraction list of `path`/`nameAs`/`typeAs`) and
  `parse.XmlPath` (same shape, `path` is XPath syntax, e.g. `/Event/System/EventID` or
  `/Event/EventData/Data[@Name='SubjectUserName']`) and `parse.CEFAttribute`. [DOC S-luprngvc]
- A **workspace transformation DCR** applies a transformation directly to a Log Analytics workspace/table for data
  collected outside a DCR-based method (e.g. legacy connectors); it is a different `dataFlows` mechanism than the
  DCR used by AMA or the Logs Ingestion API. [DOC S-m4gimryf]

### Associations, DCE and destinations
- A DCR association (DCRA) links a DCR to a target resource; the relationship is many-to-many — one DCR can have
  many resources, and one resource can have up to 30 DCRs associated. [DOC S-m4gimryf]
- AMA retrieves DCRs over a public endpoint by default; a Data Collection Endpoint (DCE) is required only when using
  Azure Monitor Private Link, or for two specific data sources: Windows Firewall Logs and Prometheus metrics
  (Container Insights) — other data sources on the same agent can keep using the public endpoint even if one DCR
  needs a DCE. [DOC S-in4qr3cp]
- A DCE has three endpoint components: logs ingestion endpoint (must be in the same region as the destination
  workspace), metrics ingestion endpoint (same region as the destination Azure Monitor workspace), and configuration
  access endpoint (same region as the monitored resources) — example forms
  `<id>.<region>-1.ingest`, `<id>.<region>-1.metrics.ingest`, `<id>.<region>-1.handler.control`. [DOC S-in4qr3cp]
- DCRs are stored/managed as Azure resources, replicated to the paired region and deployed across all availability
  zones in their region (zone-redundant); air-gapped clouds aren't yet supported for DCRs. [DOC S-m4gimryf]

### Installing AMA
- Installation methods: VM extension (`AzureMonitorWindowsAgent`/`AzureMonitorLinuxAgent`, publisher
  `Microsoft.Azure.Monitor`) via PowerShell/CLI/ARM; creating a DCR in the portal (auto-installs the agent and
  associates it); VM insights (auto-installs + creates a DCR you shouldn't hand-edit); Container insights
  (containerized agent); the Windows MSI client installer; and Azure Policy for install-at-scale with DCR
  association. [DOC S-mix3xqam]
- No reboot is needed to install, upgrade or uninstall AMA. Non-Azure machines need the Azure Arc Connected Machine
  agent installed before the AMA extension. [DOC S-mix3xqam]
- `Set-AzVMExtension -Name AzureMonitorWindowsAgent -ExtensionType AzureMonitorWindowsAgent -Publisher
  Microsoft.Azure.Monitor ... -EnableAutomaticUpgrade $true` (system-assigned identity) or with a
  `-SettingString '{"authentication":{"managedIdentity":{...}}}'` block for a user-assigned identity; on Arc servers
  use `New-AzConnectedMachineExtension` with the same extension type/publisher. [DOC S-mix3xqam]
- Verify AMA is reporting with a Log Analytics query: `Heartbeat | where Category == "Azure Monitor Agent" |
  where TimeGenerated > ago(5m)`. [DOC S-mix3xqam]
- On Linux, AMA creates dedicated non-interactive system accounts: `azuremonitoragent` (runs `mdsd`, the core
  collection service), `azureotelcollector` (OpenTelemetry data collection), `azuremetricsext` (Metrics Extension);
  none should be deleted or modified. [DOC S-mix3xqam]
- AMA is free; charges apply for Log Analytics data ingestion and retention only. [DOC S-6xjyyd4l]
- On Windows, AMA supports Event Logs, Performance, file-based logs and IIS logs, delivered to Azure Monitor Logs;
  it is required (not the legacy agent) for VM insights, Change tracking, SQL Best Practices Assessment, Azure
  Local, and (Sentinel scope-dependent) Microsoft Sentinel; Microsoft Defender for Cloud and Azure Update Manager no
  longer use either agent. [DOC S-6xjyyd4l]

### Windows client installer (Windows 10/11 desktops)
- The client installer and the VM extension install the same underlying AMA binary; the client installer uses
  Microsoft Entra device token authentication instead of managed identity, and DCRs associate to a tenant-wide
  **monitored object**, not to the individual device resource — granular per-device DCR targeting is not supported.
  [DOC S-de5xdfvw]
- Supported only on Windows 10/11 desktops/workstations/laptops (RS4+); not for VMs, scale sets or servers (those
  use the VM extension, with Azure Arc for on-premises). The device must be Microsoft Entra joined or hybrid joined;
  Azure Arc is not required for Entra-joined Windows client machines. [DOC S-de5xdfvw]
- Prerequisites: Visual C++ Redistributable 2015+; outbound HTTPS to `global.handler.control.monitor.azure.com`,
  `<region>.handler.control.monitor.azure.com`, and `<workspace-id>.ods.opinsights.azure.com`. [DOC S-de5xdfvw]
- Install silently: `msiexec /i AzureMonitorAgentClientSetup.msi /qn`; custom paths/proxy via properties
  `INSTALLDIR`, `DATASTOREDIR`, `PROXYUSE`, `PROXYADDRESS`, `PROXYUSEAUTH`, `PROXYUSERNAME`, `PROXYPASSWORD`,
  `CLOUDENV` (`Azure Commercial`/`Azure China`/`Azure US Gov`/`Azure USNat`/`Azure USSec`). Diagnostic logging:
  `msiexec /I AzureMonitorAgentClientSetup.msi /L*V <logfile>`. [DOC S-de5xdfvw]
- Limitations: no private link support for client devices, no Azure Monitor Metrics destination, and the agent
  isn't optimized for battery/network use on laptops. Settings can't be changed post-install without
  uninstall/reinstall. [DOC S-de5xdfvw]
- Setting up the tenant-wide association requires: (1) assign **Monitored Objects Contributor** at root scope
  (requires elevating to Azure tenant admin) to the operator, (2) `PUT
  .../providers/Microsoft.Insights/monitoredObjects/<tenantId>` with the DCR's region, (3) create a DCRA under that
  monitored object pointing at the DCR's resource id. [DOC S-de5xdfvw]
- Runtime data/logs default to `C:\Resources\Azure Monitor Agent\`, or the path in registry value
  `HKLM\SOFTWARE\Microsoft\AzureMonitorAgent\AMADataRootDirPath`; the `ServiceLogs` folder holds the AMA Windows
  service log, `AzureMonitorAgent.MonitoringDataStore` holds process data/logs. [DOC S-de5xdfvw]

### MMA/Log Analytics agent retirement
- The Log Analytics agent (MMA/OMS) — AMA's predecessor — was retired 2024-08-31; after that date Microsoft stopped
  portal installs and support, and no new OS/distro support is added; cloud ingestion for MMA can stop at any time
  without notice after 2026-03-02. Offline/extension-based MMA installs still technically work but are unsupported.
  [DOC S-5d3e2yck]
- MMA/OMS is replaced by AMA for both Windows and Linux, in Azure, other clouds and on-premises; AMA uses DCRs
  instead of the legacy agent's per-workspace configuration. [DOC S-5d3e2yck]
- MMA is not required for Microsoft Defender for Endpoint (on supported OS); AMA cannot substitute for Defender for
  Endpoint. Windows 8.1 Defender for Endpoint devices remain MMA-dependent. [COMMUNITY S-5d3e2yck]

### Logs Ingestion API
- The Logs Ingestion API sends data to a Log Analytics workspace via a REST call that names a DCR by its
  `immutableId`; the DCR defines the incoming schema, an optional transformation to match the target table, and the
  destination table — direct ingestion specifies the DCR per API call (unlike AMA, which uses a DCRA). [DOC S-prybc22p, S-m4gimryf]
- Call the Logs Ingestion API against either the DCR's own `logsIngestion` endpoint property, or a separate DCE if
  one is preferred (a DCE is mandatory only when the destination workspace uses Private Link). [DOC S-in4qr3cp]
- Authorize the caller (a Microsoft Entra app/service principal) by assigning it the **Monitoring Metrics Publisher**
  role, scoped to the DCR (or a custom role with `Microsoft.Insights/Telemetry/Write`); allow up to 30 minutes for
  the role assignment to propagate — sending data before that returns HTTP 403 Forbidden. [DOC S-qvsjnnqo]
- Logs Ingestion API limits: max API call size 1 MB (compressed or uncompressed); max field value size 64 KB (longer
  values truncated); max data per DCR 2 GB/minute; max requests per DCR 12,000/minute — both retriable per the
  response's `Retry-After` header. [DOC S-r33zxv3s]
- Setting up the API from scratch needs: a Microsoft Entra app registration + service principal + secret, a Data
  Collection Endpoint, and DCRs, with Contributor on the workspace/DCE/DCR resource groups plus Monitoring Metrics
  Publisher on the DCR resource group. [DOC S-prybc22p]

## Reference
- `logs/sources.md`: verified Windows event channel names and log file paths to target with `windowsEventLogs`
  XPaths or `logFiles`; back-link added there.
- `windows/event-forwarding-sysmon.md`: WEF/WEC subscription setup and Sysmon event IDs/channel — an alternative or
  upstream source for events an AMA DCR then collects locally (AMA reads local channels, including `ForwardedEvents`
  and `Microsoft-Windows-Sysmon/Operational`, the same way as any other Windows event channel).
- `logs/otel-collector-receivers.md`: the vendor-neutral `windows_event_log`/`windowseventlog` OTel receiver as an
  alternative to AMA for the same Windows event channels, with its own XPath-like `query` option.
- `windows/azure-arc-servers.md`: Arc-enabled servers Reference has a back-link to this article for the AMA
  extension deployed on Arc machines.
- `logs/microsoft-sentinel.md` — Sentinel data tiers/retention, analytics rules and pricing that consume the
  Windows Security Events via AMA and Syslog/CEF via AMA connectors documented here; see its Reference section for
  the back-link to this article.

## Examples
DCR JSON fragment collecting Security 4624/4625 and Sysmon Operational via XPath, sending to a Log Analytics
workspace (placeholder subscription `00000000-0000-0000-0000-000000000000`, resource group `PL-SRV-0042`):
```json
{
  "location": "eastus",
  "properties": {
    "dataSources": {
      "windowsEventLogs": [
        {
          "name": "securityLogonEvents",
          "streams": ["Microsoft-Event"],
          "xPathQueries": [
            "Security!*[System[(EventID=4624 or EventID=4625)]]",
            "Microsoft-Windows-Sysmon/Operational!*[System[(EventID=1 or EventID=3)]]"
          ]
        }
      ]
    },
    "destinations": {
      "logAnalytics": [
        {
          "workspaceResourceId": "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/PL-SRV-0042/providers/Microsoft.OperationalInsights/workspaces/PL-SRV-0042-law",
          "name": "law-dest"
        }
      ]
    },
    "dataFlows": [
      {
        "streams": ["Microsoft-Event"],
        "destinations": ["law-dest"],
        "transformKql": "source"
      }
    ]
  }
}
```
Install AMA on an Azure Arc server (managed identity auth) and check heartbeat:
```powershell
New-AzConnectedMachineExtension -Name AzureMonitorWindowsAgent -ExtensionType AzureMonitorWindowsAgent `
  -Publisher Microsoft.Azure.Monitor -ResourceGroupName PL-SRV-0042 -MachineName PL-SRV-0042 `
  -Location eastus -EnableAutomaticUpgrade
```
```kusto
Heartbeat | where Category == "Azure Monitor Agent" | where TimeGenerated > ago(5m)
```
Test an XPath query locally on `PL-LT-00123` before adding it to a DCR:
```powershell
$XPath = '*[System[(EventID=4624 or EventID=4625)]]'
Get-WinEvent -LogName 'Security' -FilterXPath $XPath
```
