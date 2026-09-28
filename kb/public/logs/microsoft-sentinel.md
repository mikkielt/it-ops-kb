---
topic: logs/microsoft-sentinel
priority: P2
applies_to: "Microsoft Sentinel (Defender portal unified SecOps and Azure portal), docs ms.date through 2026-09"
retrieved_utc: 2026-09-28
sources: [S-qmi72hvd, S-56eqdqa6, S-btmphtyp, S-6c6jslfs, S-cmyl6p5v, S-guca45p3, S-etccrdda, S-hya3uz6p, S-34uiuy35, S-tf6fezvb, S-vjefvouf, S-ur2l6cs3, S-luprngvc, S-me4bxp52, S-ycrujjsf, S-5kjwbj3c, S-ofreafga, S-w47nempm, S-3dcvyq2z, S-r4klpeuf, S-apxtyshr, S-hvr4bpb2, S-qkyfycn6, S-vicgida6, S-bxionmbk]
status: complete
---

# Microsoft Sentinel

## Summary
Microsoft Sentinel is a cloud-native SIEM built on a Log Analytics workspace, now available (and, for most new
customers, mandatory) in the unified Microsoft Defender portal alongside Defender XDR; the Azure portal experience
retires 2027-03-31. Data arrives via data connectors (native Sentinel connectors, the Defender XDR integration, or
Azure Monitor Agent/DCR-based connectors such as Windows Security Events via AMA and Syslog/CEF via AMA) into
tables held in one of two tiers — Analytics (hot, full feature set) or Data Lake (cold, KQL/notebook access only) —
plus a separate always-free 30-day XDR default tier for Defender XDR hunting tables. Threat detection runs as
analytics rules (Scheduled or NRT) or is inherited from Defender XDR custom detections; ASIM normalizes queries
across sources. AMA/DCR mechanics are in `logs/azure-monitor-agent.md`; the KQL hunting surface and Defender XDR
tables are in `defender/advanced-hunting.md`.

## Facts

### Unified SecOps platform and portal retirement
- Microsoft Sentinel is generally available in the Microsoft Defender portal, including for customers without
  Microsoft Defender XDR or an E5 license — you can use Sentinel in the Defender portal even without other Defender
  services. [DOC S-56eqdqa6]
- After **March 31, 2027**, Microsoft Sentinel will no longer be supported in the Azure portal and will be
  available only in the Microsoft Defender portal; all Azure-portal customers are redirected to the Defender
  portal. [DOC S-56eqdqa6]
- Starting **July 2025**, a new customer onboarding their tenant's first workspace to Sentinel, who holds
  subscription **Owner** or **User access administrator** permissions and is not an Azure Lighthouse-delegated
  user, has that workspace automatically onboarded to the Defender portal at the same time as Sentinel onboarding;
  such users then use Sentinel in the Defender portal only. [DOC S-56eqdqa6]
- Existing customers creating additional workspaces in an already-Sentinel-enabled tenant, and Azure
  Lighthouse-delegated users, are never auto-onboarded to the Defender portal (no redirection links shown either).
  [DOC S-56eqdqa6]
- Manual onboarding to the Defender portal: **System > Settings > Microsoft Sentinel > Connect a workspace**, pick
  the workspace(s), designate one **Primary workspace**, then **Connect**; the Defender portal supports one primary
  workspace plus multiple secondary workspaces per Entra tenant. [DOC S-qmi72hvd]
- Onboarding a single workspace requires an Azure account role assignment; for onboarding itself, the **Owner**
  role assignment must be **unconditional** at the subscription scope. [DOC S-qmi72hvd]
- Onboarding a Log Analytics workspace to Sentinel (Azure portal): search **Microsoft Sentinel**, **Create**, pick
  the workspace, **Add**; Defender for Cloud's own default workspaces cannot host Sentinel, and once deployed on a
  workspace, Sentinel does not support moving that workspace to another resource group or subscription. [DOC
  S-r4klpeuf]
- Integrating Defender XDR with Sentinel (Azure-portal-only customers) streams all Defender XDR incidents and
  advanced hunting events into Sentinel and keeps incidents bi-directionally synced between the Azure and Defender
  portals. [DOC S-tf6fezvb]

### Data connectors
- Out-of-the-box data connectors ship packaged with Sentinel solutions (content hub) and cover Microsoft/Azure
  sources (Entra ID, Azure Activity, Azure Storage, etc.) plus non-Microsoft ecosystem sources via Common Event
  Format, Syslog or a REST API; sources without a dedicated connector use a custom connector. [DOC S-56eqdqa6]
- Two AMA/DCR-based connectors feed Sentinel-specific tables: **Windows Security Events via AMA** (populates
  `SecurityEvent`, offers prebuilt Common/Minimal event sets or custom XPath) and **Syslog/CEF via AMA**
  (`Microsoft-Syslog` / `Microsoft-CommonSecurityLog` streams); see `logs/azure-monitor-agent.md` for DCR structure,
  XPath syntax and installation. [DOC S-luprngvc, S-me4bxp52, S-3dcvyq2z]
- Installing the Azure Activity solution's connector is the quickstart's example flow: **Content hub** page, find
  and select the solution, **Install**, then configure the data connector from the Defender or Azure portal. [DOC
  S-r4klpeuf]
- Data normalization (see ASIM below) runs at both query time and ingestion time to translate varied connector
  sources into a uniform, normalized view. [DOC S-56eqdqa6]

### Data tiers and retention
- Two Sentinel-manageable tiers: **Analytics tier** (hot; two states — Analytics retention, and Total retention
  mirrored to the data lake) and **Data Lake tier** (cold; lake-only, not available for real-time analytics/
  hunting). A separate **XDR default tier** holds Defender XDR threat-hunting data. [DOC S-btmphtyp]
- Analytics retention defaults to **30 days** for both Sentinel and Defender XDR; extendable to **up to 2 years**
  at a prorated monthly long-term-retention charge; Sentinel solution tables can be extended to **90 days for
  free**. [DOC S-btmphtyp]
- Total retention (data mirrored to the data lake) defaults to match Analytics retention and can be extended to up
  to **12 years** at low cost. [DOC S-btmphtyp]
- XDR threat-hunting data is always available in the Analytics tier for 30 days by default; extendable to 90 days
  in the Analytics tier (Sentinel ingestion costs apply, no extra storage cost up to 90 days); beyond 90 days,
  storage costs also apply; XDR data can also be ingested directly and exclusively into the Data Lake tier (still
  30 days free via advanced hunting). [DOC S-btmphtyp]
- Comparison table (Analytics tier vs Data Lake tier): Analytics tier retention "90 days for Microsoft Sentinel, 30
  days for Microsoft Defender XDR" (extendable to 2 years); Data Lake tier retention matches analytics by default,
  extendable to 12 years; Data Lake tier lacks query price inclusion, optimized query performance, full real-time
  analytics features (analytics rules, hunting queries, parsers, watchlists, workbooks, playbooks), Restore, and
  Data export, while both tiers support Search jobs and Summary rules. [DOC S-btmphtyp]
- Changing a table's tier from Analytics to Data Lake stops all real-time analytics and hunting queries on it
  immediately. Shortening total retention: Microsoft waits **30 days** before deleting data (revertible).
  Increasing total retention applies to already-ingested, not-yet-removed data. Changing analytics retention on an
  existing table takes effect immediately. [DOC S-btmphtyp]
- Resetting analytics retention and total retention on an XDR table to the default 30 days **disables its
  connector** in the Azure portal. [DOC S-btmphtyp]
- MMA/OMS (legacy Log Analytics agent) custom tables are **not** mirrored to the data lake; tables created via the
  Logs Ingestion API or AMA/DCR-based custom tables **are** mirrored. [DOC S-34uiuy35]
- Once a tenant onboards the Sentinel data lake, auxiliary log tables disappear from Defender XDR Advanced Hunting
  and from the Azure portal's Sentinel UI; their data remains queryable only via data lake exploration KQL/Jupyter
  notebooks in the Defender portal. [DOC S-34uiuy35]
- The Sentinel data lake stores data as open-format Parquet files in a single copy, with storage and compute
  separated and multiple analytics engines (KQL queries, Jupyter notebooks) supported. [DOC S-hya3uz6p]
- A tenant has one data lake usable with multiple Microsoft Security products; onboarding provisions it in the same
  region as the primary Sentinel workspace and also enables graph capabilities. [DOC S-w47nempm, S-apxtyshr]
- Deleting the billing subscription or resource group that hosts the data lake suspends data-lake experiences and
  stops ingestion after **3 days**; restoring requires re-running data lake setup (previously ingested data is
  restored). [DOC S-w47nempm]

### Analytics rules (Scheduled)
- Analytics rule types: **Scheduled** rules (by far the most common; KQL query run on an interval against a
  lookback window, alert fires if result count passes a threshold), **Near-real-time (NRT)** rules, Anomaly rules
  and Microsoft security rules, plus specialized templates that each create one rule instance (Threat intelligence,
  Fusion multistage attack detection, ML behavior analytics). [DOC S-ur2l6cs3]
- Scheduled rule query scheduling: **Run query every** (interval) and **Lookup data from the last** (lookback), both
  ranging **5 minutes to 14 days**; the interval must be ≤ the lookback (rule validation blocks a longer interval,
  which would leave coverage gaps). [DOC S-6c6jslfs]
- Scheduled rules run on a built-in **5-minute delay** from their scheduled time to absorb source-to-ingestion
  latency (see `logs/azure-monitor-agent.md` DCR data flow for the upstream pipeline); a "Start running" preview
  setting can delay a new/enabled rule's first execution by **10 minutes to 30 days** after creation. [DOC
  S-6c6jslfs]
- Rule query text: **1 to 10,000 characters**, must not contain `search *` or `union *`; recommended to build on an
  ASIM unifying parser instead of a native table so the rule automatically covers any current/future source for
  that schema. [DOC S-6c6jslfs]
- Event grouping: default groups all matching events into one alert per run; "trigger an alert for each event"
  generates one alert per result up to **150** — beyond that, the first 149 events each get an alert and the 150th
  alert summarizes the remainder (parity with the custom-detection cap documented in
  `defender/advanced-hunting.md`). [DOC S-6c6jslfs]
- Alert grouping into incidents: default time frame **5 hours** after the first alert (configurable 5 minutes to
  7 days); up to **150 alerts** can be grouped into one incident — beyond that, a new incident is spun up for the
  excess. [DOC S-6c6jslfs]
- Suppression ("stop running query after alert is generated") can pause a rule for up to **24 hours** after it
  fires. [DOC S-6c6jslfs]
- If a Sentinel workspace is onboarded to the Defender portal, incident creation is handled by Defender XDR's
  correlation engine, which can override rule-customized alert names; the rule's own "reopen closed incidents on
  new matching alert" option is unavailable once onboarded to the Defender portal. [DOC S-6c6jslfs]
- Classic "Alert automation" playbook triggers (pre-automation-rules mechanism) are due for deprecation in
  **March 2026**; migrate them to automation rules using the alert-created trigger. [DOC S-6c6jslfs]

### NRT (near-real-time) rules
- NRT rules are hard-coded to run **once per minute** with a fixed **one-minute lookback**; query scheduling and
  alert threshold are not configurable (an alert is always generated on a match). [DOC S-cmyl6p5v, S-guca45p3]
- NRT rules run on a **2-minute delay** (vs the 5-minute delay for scheduled rules) by querying on ingestion time
  rather than the source `TimeGenerated`, avoiding the scheduled-rule ingestion-delay tradeoff. [DOC S-cmyl6p5v]
- NRT event grouping caps at **30 events** per run when "alert per event" is chosen: the first 29 events each get
  an alert, and a 30th alert summarizes the remaining events in the result set; NRT alerts should use `project` to
  include only necessary fields since alert size is limited. [DOC S-guca45p3]
- Custom-detection vs. analytics-rule comparison: Sentinel analytics-rule NRT tests events **after ingestion**
  and analytics rules do **not** support Defender XDR data (Sentinel analytics tier only), whereas Defender custom
  detections support NRT streaming (events tested as they stream, not sensitive to ingestion delays) and Defender
  XDR data; conversely, only analytics rules support "determine rule's first run," Sentinel automation rules with
  incident and alert triggers, and customizable alert-grouping logic. [DOC S-hvr4bpb2]

### ASIM (Advanced Security Information Model)
- ASIM normalizes source-specific tables into standard schemas at **query time** (KQL user-defined-function
  parsers) and, for higher performance on select schemas, at **ingest time** into dedicated normalized tables (for
  example `ASimAuthenticationEventLogs`, `ASimDnsActivityLogs`, `ASimNetworkSessionLogs`, `ASimProcessEventLogs`,
  `ASimRegistryEventLogs`, `ASimFileEventLogs`, `ASimDhcpEventLogs`, `ASimAuditEventLogs`,
  `ASimUserManagementActivityLogs`, `ASimWebSessionLogs`). [DOC S-etccrdda]
- Twelve ASIM normalized schemas: Agent Event, Alert Event, Audit Event, Authentication Event, DHCP Activity, DNS
  Activity, File Activity, Network Session, Process Event, Registry Event, User Management, Web Session; plus a
  separate Asset Entity schema for normalizing asset inventories and change feeds. [DOC S-etccrdda]
- Query-time parsers avoid modifying source data (parser fixes apply retroactively to existing data) but can slow
  queries on large datasets; this is why ASIM complements them with ingest-time normalization for the schemas
  listed above. [DOC S-etccrdda]
- Built-in parsers ship in every workspace, with the unifying parser named `_Im_<schema>`; custom parsers are
  named `vim<Schema><Vendor><Product>` (filtering) or `ASim<Schema><Vendor><Product>` (parameter-less) and are
  added to the schema's unifying parser (the Authentication schema's are `imAuthentication` and
  `ASimAuthentication`). [DOC S-qkyfycn6, S-vicgida6]
- Analytics rule query best practice: prefer an ASIM unifying parser over a native table name so the rule
  automatically extends to any current or future data source for that schema, without rule changes. [DOC S-6c6jslfs]

### Pricing concept
- Analytics tier billing: **pay-as-you-go** (default; based on the data volume stored, measured in GB of 10^9
  bytes, plus optional retention beyond 90 days) or **commitment tiers** (formerly Capacity Reservations), starting
  at **100 GB/day**; usage above the committed level bills at that tier's discounted effective per-GB rate. [DOC
  S-vjefvouf]
- Commitment tier changes: the tier can be increased at any time, but lowering it is allowed only every **31 days**;
  ingestion and analysis are billed daily. [DOC S-vjefvouf]
- Free trial: the first **10 GB/day** ingested via the Analytics logs plan is free for **31 days** on a Log
  Analytics workspace with Sentinel enabled (waives both Log Analytics ingestion and Sentinel analysis charges up
  to that limit); capped at **20 workspaces per Azure tenant**. [DOC S-vjefvouf]
- Data Lake tier billing has five separate meters: ingestion (per GB, tables retained in the data-lake tier only),
  data processing (per GB, transformations like redaction/splitting/filtering/normalization), storage (per GB per
  month for data past analytics-tier retention, billed at a uniform **6:1** compression ratio), query (per GB of
  uncompressed data scanned by KQL/KQL jobs), and advanced data insights (per compute-hour for notebook
  sessions/jobs, pools of **12, 32 or 80 vCores**). [DOC S-vjefvouf]
- Ingestion and data-processing charges for the Data Lake tier do **not** apply when a table's retention includes
  both the analytics and data lake tiers (i.e., mirroring is free) — they apply only to data-lake-only tables.
  [DOC S-vjefvouf]

### Infrastructure as code (Terraform azurerm provider)
- `azurerm_log_analytics_workspace` creates the Log Analytics workspace that a Sentinel deployment onboards onto;
  key arguments `sku` (allowed values `PerGB2018`, `PerNode`, `Premium`, `Standalone`, `Standard`,
  `CapacityReservation`, `LACluster`, `Unlimited`; default `PerGB2018`), `retention_in_days` (allowed range 30-730,
  optional), plus required `resource_group_name` and `location`. [DOC S-ycrujjsf]
- `azurerm_sentinel_log_analytics_workspace_onboarding` is the resource that actually enables Microsoft Sentinel on
  a workspace (Terraform has no single "create a Sentinel instance" resource — onboarding is a separate resource
  layered on the workspace); required argument `workspace_id`, optional `customer_managed_key_enabled` (default
  `false`). [DOC S-5kjwbj3c]
- `azurerm_monitor_data_collection_rule` provisions a DCR (see `logs/azure-monitor-agent.md` for DCR/DCE concepts);
  optional `kind` (`Linux`, `Windows`, `AgentDirectToStore`, `WorkspaceTransforms` — changing it after creation
  forces a new resource), required `data_flow` block(s) (routes streams to named destinations, with optional KQL
  transform) and required `destinations` block (e.g. `log_analytics` sub-block with `workspace_resource_id` and a
  destination `name`). [DOC S-ofreafga]

## Reference
- `auth/audit-log-apis.md` — the diagnostic-settings export path (`AuditLogs`/`SigninLogs` categories) that
  feeds the `SigninLogs`/`AuditLogs` Sentinel tables, and the Office 365 Management Activity API as an
  alternative ingestion source for Exchange/SharePoint/Entra audit content.
- `logs/azure-monitor-agent.md` — DCR/DCRA/DCE structure, Windows Event/Syslog data source config, XPath syntax and
  AMA installation that back the Windows Security Events via AMA and Syslog/CEF via AMA connectors cited above; see
  its Reference section for the back-link to this article.
- `defender/advanced-hunting.md` — the KQL hunting surface, Defender XDR table schema (`DeviceEvents`,
  `AlertEvidence`, etc.), the 30-day XDR native retention and the 150-alert-per-run custom-detection cap that
  parallels this article's analytics-rule alert cap; see its Reference section for the back-link to this article.
- Table insights (Defender portal, Microsoft Sentinel > Configuration > Tables) is a visualization surface for investigation, not a billing-grade or alerting surface; alerting on table health needs a scheduled analytics rule on `SentinelHealth` or a KQL query on `Usage`. [DOC S-btmphtyp, S-bxionmbk]
- Its limits: ingestion volume cards cover the last 30 days; fluctuations compare the last 24 hours with the same day a week earlier and need at least a 10 percent and 1 MB change (tables under 1 MB a day are not evaluated); **Est. daily ingestion cost** uses public list price for the tier and region, without commitment-tier discounts, reservations or private pricing; one workspace at a time. [DOC S-bxionmbk]
- The pages give no refresh cadence for Table insights. [DER S-btmphtyp, S-bxionmbk: no refresh interval stated]

## Examples
- SNIPPET: KQL — mirrors the AMA-fed `SecurityEvent`/`DeviceEvents` cross-source hunting pattern (placeholders only); context: Sentinel analytics/hunting KQL; checked: no [DOC S-qkyfycn6, S-vicgida6: `imAuthentication` is the Authentication schema's unifying parser]
```kusto
// Failed sign-ins followed by a success, per account, last 24h (ASIM authentication schema)
imAuthentication
| where EventResult == "Failure"
| where TargetUsername == "jan.kowalski"
| summarize FailedCount = count(), LastFailure = max(TimeGenerated) by TargetUsername, SrcIpAddr
| where FailedCount > 5
```

Onboard a workspace via ARM template snippet — simplified pricing at a 300 GB/day commitment tier (placeholders):
```json
{
  "type": "Microsoft.OperationsManagement/solutions",
  "properties": { "sku": { "name": "Unified" } },
  "plan": { "product": "OMSGallery/SecurityInsights" }
}
```
Set `capacityReservationLevel` to `300` on the paired `Microsoft.OperationalInsights/workspaces` resource for
tenant `00000000-0000-0000-0000-000000000000`, workspace resource group `rg-PL-SRV-0042`.

- SNIPPET: Terraform (azurerm provider) — workspace + Sentinel onboarding (placeholders); context: azurerm provider; checked: no [DOC S-5kjwbj3c: `workspace_id` and `customer_managed_key_enabled` arguments]
```hcl
resource "azurerm_log_analytics_workspace" "example" {
  name                = "law-PL-SRV-0042"
  resource_group_name = "rg-PL-SRV-0042"
  location            = "westeurope"
  sku                 = "PerGB2018"
  retention_in_days   = 90
}

resource "azurerm_sentinel_log_analytics_workspace_onboarding" "example" {
  workspace_id                 = azurerm_log_analytics_workspace.example.id
  customer_managed_key_enabled = false
}
```
