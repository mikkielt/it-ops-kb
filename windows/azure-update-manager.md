---
topic: windows/azure-update-manager
priority: P2
applies_to: "Azure Update Manager for Azure VMs and Azure Arc-enabled servers (Windows/Linux); docs current 2026-09-26"
retrieved_utc: 2026-09-26
sources: [S-e6petnio, S-icfvnq2h, S-fync3qzc, S-kemkbiwb, S-5sy3a7ev, S-4gkojj4d, S-ci26bqyc, S-bbya5ebc, S-qpjly7jd, S-wvznmns5, S-horf4w6m, S-h3kjbi2l, S-deu5qnsc, S-q3ieo6m5, S-nd4cmnsq, S-umxt7njc, S-b5urflpf, S-vgw6qot7, S-5g472jm4, S-hvijyhte, S-nyw5rvsw, S-oo4lrs7s, S-5c4oo5gx]
status: complete
---

# Azure Update Manager: periodic assessment, maintenance configurations, orchestration, and hotpatch

## Summary
- Azure Update Manager (AUM, formerly Update Management Center) is a native, no-onboarding-dependency service that assesses and patches Windows/Linux Azure VMs and Azure Arc-enabled servers (plus VMware, SCVMM, Azure Local machines) from a single pane; it doesn't depend on Log Analytics or Azure Automation. [DOC S-e6petnio, S-qpjly7jd]
- Periodic assessment fetches available updates every 24 hours automatically and can be enabled per machine or at scale via built-in Azure Policy definitions; on-demand ("check for updates now") assessment is also available. [DOC S-icfvnq2h, S-fync3qzc]
- Scheduled patching uses **maintenance configurations** (Microsoft.Maintenance) rather than AUM's own scheduler; **dynamic scoping** groups machines by subscription/resource group/location/type/OS/tags so a schedule's membership is re-evaluated at run time. [DOC S-kemkbiwb, S-ci26bqyc]
- Patch orchestration has four modes on Azure VMs (`AutomaticByPlatform`, `AutomaticByOS`, `Manual`, `ImageDefault`) plus `AutomaticByPlatform` + `BypassPlatformSafetyChecksOnUserSchedule=true` ("Customer Managed Schedules") required for scheduled patching; Arc-enabled servers have no patch-orchestration prerequisite for scheduled patching. [DOC S-b5urflpf, S-kemkbiwb, S-ci26bqyc]
- AUM is free for Azure VMs; for Azure Arc-enabled servers it's billed per-server, per-day, prorated monthly, with several no-charge exemptions (ESU-enabled, Defender for Servers Plan 2, Software Assurance/pay-as-you-go Windows Server licensing). [DOC S-qpjly7jd]
- Hotpatch for Windows Server 2025 on Arc-enabled servers is a separate, no-extra-cost benefit (as of 2026-05-19, billing stopped entirely) layered on top of AUM's scheduling; it delivers monthly no-reboot updates with a quarterly reboot-required baseline. [DOC S-5g472jm4, S-vgw6qot7]
- All assessment/installation results land in Azure Resource Graph tables `patchassessmentresources` (7-day retention) and `patchinstallationresources` (30-day retention), queryable with KQL-style Resource Graph queries. [DOC S-wvznmns5, S-horf4w6m]

## Facts

### Periodic assessment
- Periodic assessment is a per-machine setting that enables automatic checking for available updates every 24 hours; Microsoft recommends enabling it so AUM can report machine compliance without a manual check. [DOC S-icfvnq2h]
- Assessments only retrieve updates for Azure VMs in the **Running** state; VMs in **Stopped** or **Stopped (deallocated)** states aren't scanned. [DOC S-icfvnq2h]
- For Arc-enabled servers, the subscription the Arc server is onboarded into must be registered to the `Microsoft.Compute` resource provider for periodic assessment to work. [DOC S-icfvnq2h]
- At-scale enablement uses built-in Azure Policy definitions in the **Azure Update Manager** category: "Configure periodic checking for missing system updates on Azure virtual machines" (Windows/Linux, separate policies) and the Arc-enabled-server equivalent; both default the **Assessment mode** parameter to `AutomaticByPlatform` and support a remediation task to apply to existing resources. [DOC S-fync3qzc]
- A companion audit-only policy, "Machines should be configured to periodically check for missing system updates," reports compliance without a remediation step. [DOC S-fync3qzc]
- On-demand assessment ("Check for updates now") is available per VM or for multiple selected machines at once from the AUM **Machines** view or a VM's **Updates** blade. [DOC S-icfvnq2h]

### Maintenance configurations and scheduled patching
- AUM doesn't build its own scheduler: scheduled patching is implemented on top of Azure **Maintenance Configurations** (`Microsoft.Maintenance`), the same "maintenance control" construct used for platform-managed updates elsewhere in Azure. [DOC S-kemkbiwb]
- A maintenance configuration schedule supports daily, weekly, or hourly cadence, and specifies the target machines and the updates (classifications, and include/exclude KB IDs) to install; it can be attached to one or many machines, and one machine can only run one schedule at a time (concurrent/conflicting schedules serialize: one runs, the other waits). [DOC S-kemkbiwb, S-5sy3a7ev]
- Schedule timing constraints: **Repeats** must be at least 6 hours; a new schedule's start time must be at least 15 minutes after creation; recommended buffer of 15 minutes before a scheduled run for any membership changes (add/remove VM, edit dynamic scope); avoid creating/editing schedules in the 23:45/23:57-00:00 window because of a 15-minute (new) / 3-minute (existing) trigger-evaluation delay that can cause a missed or unresponsive run. [DOC S-5sy3a7ev]
- Maintenance configurations support two scheduled-patching modes for the guest scope: **Static Mode** (a fixed machine list; the default when no dynamic scope is configured) and **Dynamic Scope** mode. [DOC S-5sy3a7ev]
- Maintenance-window budget: before scanning/downloading/installing, a run checks remaining window time -- all update types except Windows service packs need 15 minutes + a reserved 10 minutes for reboot (25 minutes total); Windows service pack updates need 20 + 10 = 30 minutes; if the remaining time is under these thresholds the run is marked **Failed** with `Maintenance window exceeded: true` and skips the scan/install. [DOC S-5c4oo5gx]
- A concurrent or conflicting schedule on the same machine only triggers one run; the other is deferred until the first finishes; a newly created Azure VM's first schedule can see up to a 15-minute trigger delay; a machine deleted and re-created with the same resource ID within 8 hours can fail scheduled patching with a `ShutdownOrUnresponsive` error until that 8-hour window passes. [DOC S-5c4oo5gx]
- Machines must be powered on at least 15 minutes before a scheduled update, or they can lose their maintenance-configuration/schedule association; moving a VM to a different resource group or subscription breaks its scheduled maintenance configuration (unsupported scenario) -- static scope requires removing and re-creating the resource assignment after the move, dynamic scope requires waiting for/triggering the next scheduled run first. [DOC S-5c4oo5gx]
- Pre-download of updates ahead of the maintenance window isn't supported for either Azure VMs or Arc-enabled machines. [DOC S-nd4cmnsq]

### Patch orchestration modes
- Four VM `patchMode` values exist: `AutomaticByPlatform` (Azure-orchestrated; Windows and Linux; Azure assesses and installs, writes results to Resource Graph; sets registry `HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU\NoAutoUpdate=1` on Windows; required for availability-first/automatic VM guest patching), `AutomaticByOS` (Windows only; native Windows Automatic Updates; default for Windows VMs when unspecified; sets `NoAutoUpdate=0`), `Manual` (Windows only; disables Automatic Updates; default patch behavior is up to the admin), and `ImageDefault` (Linux only; honors the image's own patching config; default for Linux VMs when unspecified). [DOC S-b5urflpf]
- Switching patch modes on Windows is constrained by the create-time-only property `osProfile.windowsConfiguration.enableAutomaticUpdates`: `AutomaticByPlatform` <-> `Manual` is supported only when that property is `false`; `AutomaticByPlatform` <-> `AutomaticByOS` only when it's `true`; `AutomaticByOS` <-> `Manual` is never supported. [DOC S-b5urflpf]
- "Customer Managed Schedules" (the AUM portal's scheduled-patching prerequisite for Azure VMs) sets `patchMode=AutomaticByPlatform` and `BypassPlatformSafetyChecksOnUserSchedule=true` on the VM, with the user's consent, so automatic patching is bypassed in favor of the user-defined schedule. [DOC S-kemkbiwb, S-bbya5ebc]
- For Azure Arc-enabled VMs there's no patch-orchestration prerequisite for scheduled patching (dynamic scoping doc explicitly notes "no prerequisites"), but a schedule must still be associated with the machine. [DOC S-ci26bqyc]
- The AUM "Machines" list shows a `Patch orchestration`/status column with values **Customer Managed Schedules**, **Azure Managed - Safe Deployment** (= `AutomaticByPlatform`, automatic VM guest patching, not applicable to Arc-enabled servers), **Automatic by OS** / **OS orchestrated**, **Image Default** (Linux), and **Manual**. [DOC S-4gkojj4d]
- A known issue: once a Windows Azure VM has patch orchestration `AutomaticByOS`, the portal's "Change update settings" UI can't switch it directly to Manual; the supported workaround is switching to Customer Managed Schedules / `AutomaticByPlatform` + `BypassPlatformSafetyChecksOnUserSchedule` and simply not attaching a schedule, which halts all patching until explicitly changed. [DOC S-5c4oo5gx]

### Dynamic scoping
- Dynamic scoping groups machines by subscription, resource group, location, resource type, OS type, and tags; membership criteria are evaluated at the scheduled run time, so the machine list at create/edit time can differ from the list actually patched. [DOC S-ci26bqyc]
- Removing a machine from a dynamic scope's matching criteria (e.g. removing a tag) automatically drops its association with the schedule, at scale, with no manual per-machine edit needed. [DOC S-ci26bqyc]
- Recommended per-dynamic-scope service limits (guest scope only): 1,000 resource associations, 50 tag filters, 50 resource-group filters. [DOC S-ci26bqyc]
- Dynamic scoping requires subscription-level **Write** permission to create/modify a schedule and subscription-level **Read** permission to assign or read one. [DOC S-ci26bqyc]
- Providing consent to apply updates under dynamic scoping happens automatically when setting Patch orchestration to Customer Managed Schedules via "Change update settings," or explicitly via the "Azure-orchestrated" option on VM create (which sets `patchMode=AutomaticByPlatform` and `BypassPlatformSafetyChecksOnUserSchedule=true`); there are no prerequisites for Arc-enabled VMs. [DOC S-bbya5ebc]

### Pricing (Arc-enabled servers)
- Update Manager is free for Azure VMs and for Azure Arc-enabled Azure Local VMs created through an Arc resource bridge; all other Azure Arc-enabled servers are billed per server, per month, at a daily prorated rate (assuming a 31-day month), charged only for days the machine is connected. [DOC S-qpjly7jd]
- An Arc-enabled server counts as "managed by Update Manager" for a given day only if **both**: (1) its Arc connectivity status was **Connected** at some point that day, and (2) an update operation was triggered (on-demand or scheduled patch/assess) or it's associated with a schedule. [DOC S-qpjly7jd]
- No-charge exemptions for an Arc-enabled server otherwise managed by AUM: the machine has Extended Security Updates enabled by Azure Arc; Microsoft Defender for Servers Plan 2 is enabled on the hosting subscription (not via a security connector); or the machine's Windows Server license has active Software Assurance, a Windows Server subscription license, or Windows Server pay-as-you-go enabled by Azure Arc. [DOC S-qpjly7jd]
- Servers already using Automation Update Management for free as of 2023-09-01 aren't charged for that existing usage; any new Arc-enabled machine onboarded to Update Manager in the same subscription is charged normally. [DOC S-qpjly7jd]
- Defender for Servers Plan 2 customers aren't charged specifically to remediate the two AUM recommendations "Periodic assessment should be enabled on your machines" and "System updates should be installed on your machines"; any other Defender for Servers plan is charged the normal per-server daily rate for Arc-enabled machines. [DOC S-qpjly7jd]
- There's no extra data-transfer cost for AUM patch-management operations. [DOC S-qpjly7jd]
- Windows Server Management enabled by Azure Arc (attestation or pay-as-you-go enrollment) includes Azure Update Manager, Azure Change Tracking and Inventory, and Azure Machine Configuration at no extra cost beyond networking/storage/log-ingestion; eligibility must be explicitly attested (or via pay-as-you-go) and isn't inferred just from Arc enablement. [DOC S-nyw5rvsw]

### Hotpatch integration
- Hotpatch for Windows Server 2025 on Arc-enabled servers requires: Windows Server 2025 build 26100.1742+ (Standard, Datacenter, or Datacenter: Azure Edition -- the Azure Edition SKU doesn't need to be Arc-enabled since hotpatch is already on by default there), Server with Desktop Experience or Server Core, Virtualization-based Security (UEFI + Secure Boot at minimum; Generation 2 VM on Hyper-V), an Azure subscription, and the Connected Machine agent prerequisites met. [DOC S-vgw6qot7]
- Enabling hotpatch on an Arc-enabled Windows Server 2025 machine is done from the Azure Arc portal (**Machines > select machine > Hotpatch > Confirm**), takes about 10 minutes to apply, and can also be enabled/disabled at scale from AUM's "Change update settings" flow (Hotpatch dropdown: Enable/Disable/Reset). [DOC S-vgw6qot7, S-oo4lrs7s]
- Once enrolled, hotpatch updates are delivered monthly with no reboot; a reboot is required only for the quarterly Cumulative Update baseline; Update Manager manages the hotpatch cycle end to end, and admins can still choose all classifications or security-only, plus include/exclude individual (hotpatch) KB IDs in a schedule or one-time update. [DOC S-nyw5rvsw, S-5g472jm4]
- As of 2026-05-19, Hotpatch on Arc-enabled Windows Server 2025 Standard/Datacenter is free: no per-core meter, no hourly charge, no separate invoice line item; existing enrolled servers had billing stopped automatically and remain enrolled; new enrollments incur no hotpatch charge regardless of underlying environment (VMware, Hyper-V, AWS, GCP, other) or edition. [DOC S-5g472jm4]
- Supported OS list for Update Manager-managed hotpatch on Arc-enabled machines: Windows Server 2025 Standard Edition and Windows Server 2025 Datacenter Edition only; Windows Server 2022 hotpatch is supported only on specific Azure/Azure Local marketplace image SKUs (e.g. `2022-Datacenter-Azure-Edition-Hotpatch`), not via Arc enrollment. [DOC S-5g472jm4, S-hvijyhte]
- Known issue: hotpatch enablement via Azure Arc on new machines can stall "In Progress"; on machines previously enrolled, the feature license can expire and block the next hotpatch (forcing a reboot-requiring update instead) unless a Local/Group Policy remediation (KB5062660 ADMX template) is applied before the affected Patch Tuesday cycle; Datacenter: Azure Edition machines aren't affected. [DOC S-vgw6qot7]

### Azure Resource Graph queries
- AUM pushes every assessment and installation result to Azure Resource Graph via two tables: `patchassessmentresources` (pending-update / assessment data, retained 7 days) and `patchinstallationresources` (installation-run results, retained 30 days); both tables can `join` other Resource Graph tables. [DOC S-wvznmns5, S-horf4w6m]
- Underlying resource types behind `patchassessmentresources`: `microsoft.compute/virtualmachines/patchassessmentresults[/softwarepatches]`, `microsoft.hybridcompute/machines/patchassessmentresults[/softwarepatches]` (Arc-enabled servers), and `microsoft.connectedvmwarevsphere/virtualmachines/patchassessmentresults[/softwarepatches]`; `patchinstallationresources` has the matching `patchinstallationresults[/softwarepatches]` set for the same three provider namespaces. [DOC S-horf4w6m]
- Key `patchinstallationresults`/`patchassessmentresults` properties: `patchServiceUsed` (`WU-WSUS` for Windows, or `YUM`/`APT`/`Zypper` for Linux), `osType` (`Windows`/`Linux`), `rebootPending`/`rebootRequired`, `classifications`, `Kbid` (Windows KB ID) or `version` (Linux package version), `patchName`, `startedBy`, `errorDetails` (first five error messages). [DOC S-horf4w6m]
- Example: list Windows update installations from the last 7 days (Azure Resource Graph / KQL):
  ```kql
  PatchAssessmentResources
  | where type has 'softwarepatches' and properties !has 'version'
  | extend machineName = tostring(split(id, '/', 8)),
           resourceType = tostring(split(type, '/', 0)),
           rgName = tostring(split(id, '/', 4)),
           RunID = tostring(split(id, '/', 10))
  | extend prop = parse_json(properties)
  | extend lTime = todatetime(prop.lastModifiedDateTime),
           patchName = tostring(prop.patchName),
           kbId = tostring(prop.kbId),
           installationState = tostring(prop.installationState),
           classifications = tostring(prop.classifications)
  | where lTime > ago(7d)
  | project lTime, RunID, machineName, rgName, resourceType, patchName, kbId, classifications, installationState
  | sort by RunID
  ```
  [DOC S-horf4w6m]
- Example: the equivalent for Linux (packages carry `version` instead of `kbId`) filters `properties has 'version'` and projects `version` in place of `kbId`. [DOC S-horf4w6m]
- If patch history must be retained longer than Resource Graph's 7/30-day windows, the recommended pattern is exporting query results to an external store (no built-in longer retention). [DOC S-horf4w6m]

### Pre and post events
- AUM uses **Azure Event Grid** (system topics + event subscriptions) to fire **Pre Maintenance Event** and **Post Maintenance Event** notifications around a scheduled maintenance-configuration run, invoking handlers such as Azure Automation runbooks (via webhook), Azure Functions, Logic Apps, storage queues, or event hubs. [DOC S-h3kjbi2l, S-deu5qnsc]
- Execution order for a schedule with both events configured: (1) pre-event runs *outside* the maintenance window, e.g. to power on machines; (2) an optional cancellation step -- the pre-event's own code must explicitly call the cancellation API if it wants to abort the run (AUM never cancels automatically on pre-event failure); (3) updates install inside the defined maintenance window; (4) the post-event runs immediately after installation, which can be inside or outside the window depending on how much time installation used; (5) the schedule's reported success/failure reflects only the update-installation step, not the pre/post events -- except that a successful cancellation call reports the run as **canceled**. [DOC S-h3kjbi2l]
- To cancel a run, the pre-event handler must call the cancellation API at least 10 minutes before the schedule's start time. [DOC S-h3kjbi2l]
- Event Grid delivers at-least-once, so pre/post event handlers must be idempotent (a handler can be invoked more than once for the same event). [DOC S-h3kjbi2l]
- Multiple pre-events and/or post-events can be attached to one schedule; a pre/post event is created either while creating a new maintenance configuration (Events tab, "Add Event Subscription") or added later to an existing one (Maintenance Configuration > Settings > Events); delivery/matched/published event counts and per-event trigger times are visible as Event Grid system-topic metrics. [DOC S-deu5qnsc, S-h3kjbi2l]
- A cloud-native patch-management pattern layered on pre/post events: sequence maintenance configurations with time offsets so web servers patch before app servers before database servers, and use update include/exclude lists to hold back a known-bad update or restrict to security-only content. [DOC S-nyw5rvsw]

### Update sources (WSUS) and supported OS
- AUM honors the machine's own locally configured update source and never itself publishes updates: for Windows, whatever the Windows Update Agent (WUA) is configured for -- the public Windows Update repository (default), the Microsoft Update repository, or an on-prem **WSUS** server; for Linux, whatever repository (public YUM/APT/Zypper or a local mirror) the package manager points at. [DOC S-wvznmns5, S-q3ieo6m5]
- WSUS is a fully supported update source for both Azure VMs and Arc-enabled machines; configure it via Group Policy (set the WSUS server location under **Configure Automatic Updates**), ensure updates are approved in WSUS (unapproved updates cause AUM deployments to fail), and optionally enable "Do not connect to any Windows Update Internet locations" to fully restrict internet access. [DOC S-nd4cmnsq]
- On Windows, AUM uses the locally configured repository (Windows Update or WSUS); third-party applications and custom updates reach it only by importing and publishing them into WSUS. Driver updates show up in assessment, but AUM does not currently support installing them. For Linux, any third-party repository configured in the package manager is scanned automatically, and a package becomes unavailable for assessment/installation the moment its repository is removed. [DOC S-q3ieo6m5]
- To also patch other Microsoft products (e.g. SQL Server, Office) alongside the OS, the "Give me updates for other Microsoft products" Microsoft Update service must be registered: on Azure-orchestrated VMs, `New-Object -com "Microsoft.Update.ServiceManager"` then `AddService2($ServiceId,7,"")` with service id `7971f918-a847-4430-9279-4a52d1efe18d`; on Arc-enabled/OS-orchestrated machines this is done via the Group Policy **Configure Automatic Updates** setting's "Install updates for other Microsoft products" checkbox. [DOC S-nd4cmnsq]
- The support-matrix page splits the same setting by OS version instead: the `AddService2` PowerShell script for Windows Server versions earlier than 2016, and Group Policy (latest Administrative Templates) for Windows Server 2016 or later; it also gives `RemoveService($ServiceId)` to turn Microsoft application updates off again. [DOC S-q3ieo6m5]
- Registry differences by management mode: for Azure-orchestrated VMs, AUM itself may set `HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU\AUOptions`, `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired`, and `HKLM\...\WindowsUpdate\Services\ServiceID`; for Arc-enabled machines AUM never modifies the registry, and Group Policy fully controls update behavior instead. [DOC S-nd4cmnsq]
- Group Policy can silently override or conflict with AUM settings: a GP-set `AUOptions` can block AUM's timing control, GP/registry reboot keys can force or block reboots regardless of AUM's Never/Always Reboot setting, and GP can restrict updates to WSUS or block Microsoft Update outright, breaking AUM deployments. [DOC S-nd4cmnsq]
- Supported update types: OS updates (Windows and Linux); driver updates are visible during assessment but **cannot** currently be installed through AUM. [DOC S-umxt7njc]
- AUM explicitly doesn't support patching Windows 10 or Windows 11 (same limitation Automation Update Management had); Microsoft's recommendation for those client OSes is Microsoft Intune. [DOC S-qpjly7jd]
- Supported Windows Server marketplace/custom-image OS versions for AUM's on-demand/periodic-assessment/scheduled-patching operations: Windows Server 2025, 2022, 2019, 2016, 2012 R2, and 2012. [DOC S-umxt7njc]
- AUM doesn't require or depend on the Azure Monitor Agent; every AUM operation instead pushes a dedicated update-management VM extension that talks to the Azure VM agent (Azure VMs) or the Connected Machine agent (Arc-enabled machines). [DOC S-qpjly7jd]
- Programmatic access exists for both Azure VMs and Arc-enabled machines via REST API, Azure CLI, and Azure PowerShell. [DOC S-qpjly7jd]

## Reference
- `windows/windows-update-management.md` covers Intune's client-side Update CSP, Windows Autopatch, and Graph `windowsUpdates` for Windows 10/11 client devices -- AUM explicitly does not patch Windows 10/11 clients (see Facts above); use that article for client patching and this one for server fleets in Azure/Arc/on-prem/multicloud. A back-link has been added there.
- `windows/azure-arc-servers.md` covers the Connected Machine agent (`azcmagent`), onboarding, networking, and Azure Machine Configuration that Arc-enabled servers need before AUM can manage them; this article's pricing and hotpatch sections assume that onboarding is already complete.
- `mecm/software-updates.md` is the on-premises ConfigMgr/WSUS patch pipeline (SUP sync, ADRs, maintenance windows); AUM can consume the same WSUS server as its update source (Facts above) instead of, or alongside, ConfigMgr-managed clients.

## Examples
List patch-installation results for a resource group's Windows machines in the last 30 days:
```kql
PatchInstallationResources
| where resourceGroup =~ 'PL-SRV-0042-rg'
| where type has 'patchinstallationresults' and properties !has 'version'
| extend prop = parse_json(properties)
| extend installedTime = todatetime(prop.lastModifiedDateTime),
         patchServiceUsed = tostring(prop.patchServiceUsed),
         rebootStatus = tostring(prop.rebootStatus)
| where installedTime > ago(30d)
| project installedTime, id, patchServiceUsed, rebootStatus
| sort by installedTime desc
```
[DOC S-horf4w6m]

Enable Azure-orchestrated scheduled patching on an existing Azure VM (Azure CLI), a prerequisite for attaching a maintenance configuration:
```bash
az vm update \
  --resource-group PL-SRV-0042-rg \
  --name PL-SRV-0042 \
  --set osProfile.windowsConfiguration.patchSettings.patchMode=AutomaticByPlatform \
        osProfile.windowsConfiguration.patchSettings.automaticByPlatformSettings.bypassPlatformSafetyChecksOnUserSchedule=true
```
[DOC S-b5urflpf, S-kemkbiwb]

