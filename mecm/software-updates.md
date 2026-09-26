---
topic: mecm/software-updates
priority: P1
applies_to: "ConfigMgr current branch (sum/* docs, checked 2026-09-26)"
retrieved_utc: 2026-09-26
sources: [S-3srrd54u, S-52r2vxes, S-qhg622vy, S-o6zrfc26, S-db7ytzl6, S-kwxqaq5a, S-clekmxkf, S-zmtevvp6, S-z37n7cfj, S-n25n5lgu, S-ydpvgyqk, S-f62oqjxw, S-7opbzkmt, S-2w3gpaiz, S-fq4xtwh3, S-ix237xay]
status: complete
---

# ConfigMgr software updates: SUP, sync, ADRs, maintenance windows, WSUS maintenance

## Summary
Software updates flow: software update point (SUP) syncs classifications/products metadata from Microsoft Update (or
an upstream WSUS/site) on a schedule -> clients scan against WSUS-published metadata -> updates are deployed manually
or via an automatic deployment rule (ADR), which builds/refreshes a software update group and a deployment. Maintenance
windows gate when updates (and task sequences) install; WSUS/Configuration Manager maintenance declines and expires
superseded/expired updates after each sync. Third-party catalogs and orchestration groups extend the same pipeline.
Client-side deadline/grace-period/execution-timeout behavior is documented in `mecm/client-settings.md`; the client
and site-server log files for every stage below are already in `mecm/log-files.csv` (cited by row, not re-added here).

## Facts

### Software update point, sync, classifications/products
- The top-level site's SUP retrieves metadata from Microsoft Update, an upstream WSUS server, or (disconnected) an export/import method; classifications and products are configured only at the top-level site and replicate to child sites via database replication. [DOC S-qhg622vy, S-o6zrfc26]
- Two sync types: full sync (matches the whole WSUS catalog against the current subscription) and delta sync (only adds/removals since the last successful sync); a sync escalates to full when the default SUP, subscription, or supersedence mode/window changes, and periodically every 7 days (configurable "Full Sync Interval (days)" in the site control file). [DOC S-o6zrfc26]
- Update classifications available for sync: Critical Updates, Definition Updates, Feature Packs, Security Updates, Service Packs, Tools, Update Rollups, Updates, Upgrade (feature updates for Windows 10+; requires WSUS on a currently supported Windows Server version). [DOC S-qhg622vy]
- Best practice: clear all classifications and products before the very first sync at the top-level site, then select the desired ones and re-sync; selecting unnecessary products enlarges the WSUS metadata catalog and slows client scans. [DOC S-qhg622vy]
- Windows 10, version 1903 and later is its own Microsoft Update product (separate from "Windows 10"); enabling it also requires updating any ADRs and servicing plans that reference "Windows 10" to include the new product (automatic starting in ConfigMgr 1906 if "Windows 10" was already selected). [DOC S-qhg622vy]
- Sync schedule is configured only at the top-level site's SUP (simple or custom schedule); a common pattern is scheduling shortly after Patch Tuesday, or daily if Endpoint Protection/Defender definitions are delivered via software updates. [DOC S-2w3gpaiz, S-o6zrfc26]
- Manual sync: **Software Library > All Software Updates / Software Update Groups > Synchronize Software Updates** on the top-level site console. [DOC S-o6zrfc26]

### Automatic deployment rules (ADRs)
- An ADR automates deploying updates that meet defined search criteria (e.g. classification, product, date released/revised, architecture) into a software update group, avoiding manual addition; typical uses are monthly "Patch Tuesday" deployments and Endpoint Protection definition updates. [DOC S-3srrd54u]
- Before creating the first ADR, verify the site has completed software updates sync; classification strings display in English before the first sync and localized after, so rules created pre-sync can silently stop matching post-sync on non-English sites. [DOC S-3srrd54u]
- "Add to existing software update group": when an ADR runs, it removes all updates from the target group and re-adds only the updates currently matching its criteria -- the group's membership is fully replaced each run, not appended to. [DOC S-3srrd54u]
- ADR evaluation schedule can run up to three times per day; the schedule should never exceed the SUP's own sync schedule frequency (the wizard displays the sync schedule to help size this). Manual run: select the rule, **Run Now**. [DOC S-3srrd54u]
- The software-update search-criteria limit for a single ADR is 1000 software updates. [DOC S-3srrd54u]
- Starting in version 2203, an ADR-created deployment's **Software available time** and **Installation deadline** are calculated from when the ADR evaluation is scheduled/starts (previously: when evaluation completed), making deployment timing predictable. [DOC S-3srrd54u]
- Deployment type (Required vs. Available) is only selectable per ADR deployment starting in version 2107; before that, every ADR deployment was Required. [DOC S-3srrd54u]
- Installation deadline "Specific time" adds randomization of up to two hours to the displayed deadline to spread client install load; the client setting **Disable deadline randomization** (see `mecm/client-settings.md`) does not override this ADR-level randomization. [DOC S-3srrd54u]
- **No deployment package** option lets clients pull content straight from Microsoft Update / peer cache / Delivery Optimization without a distribution-point package; once applied it cannot be changed back. [DOC S-3srrd54u]
- Additional deployments can be added to an existing ADR from the console (**Add Deployment**) or programmatically with `New-CMSoftwareUpdateDeployment`. [DOC S-3srrd54u]
- `New-CMSoftwareUpdateAutoDeploymentRule` creates an ADR; run ConfigMgr cmdlets from the site PSDrive (e.g. `PS XYZ:\>`). Key parameters include `-CollectionName`/`-CollectionId`, `-DeploymentPackageName`, `-Name`, `-ArticleId`, `-UpdateClassification`, `-Language`/`-LanguageSelection`, `-RunType` (e.g. `RunTheRuleOnSchedule`, `DoNotRunThisRuleAutomatically`), `-Schedule` (from `New-CMSchedule`), `-AddToExistingSoftwareUpdateGroup`, `-EnabledAfterCreate`, `-DeadlineImmediately`/`-DeadlineTime`/`-DeadlineTimeUnit`, `-AvailableImmediately`/`-AvailableTime`/`-AvailableTimeUnit`. The cmdlet's return object corresponds to the `SMS_AutoDeployment` server WMI class. [DOC S-52r2vxes]
- `Invoke-CMSoftwareUpdateSummarization` runs software update status summarization immediately without resetting the next scheduled summarization time; `Get-CMSoftwareUpdateSummarizationSchedule`/`Set-CMSoftwareUpdateSummarizationSchedule` read/change that schedule. [DOC S-f62oqjxw]

### Maintenance windows
- A maintenance window is a client-side gate (collection property) on when Configuration Manager may run impacting tasks: application/package deployments, software update deployments, compliance settings evaluation/deployment, and OS/custom task sequence deployments; it cannot be created on the built-in **All Systems** collection. [DOC S-db7ytzl6]
- Window duration: minimum 5 minutes, maximum 24 hours (console enforced); default is 3 hours, 01:00-04:00; UTC mode (disabled by default) makes the window fire simultaneously across time zones instead of per device local time. [DOC S-db7ytzl6]
- **Apply this schedule to** scopes a window to **All deployments** (default), **Software updates**, or **Task sequences**; starting in version 2207, monthly recurrence can be offset (e.g. two days after the second Tuesday) to align with Patch Tuesday releases. [DOC S-db7ytzl6]
- Overlapping windows on the same device merge into one continuous window spanning both; non-overlapping windows are treated independently. [DOC S-db7ytzl6]
- With multiple maintenance windows on a device, software updates install only during a **Software Update**-typed window by default, ignoring any **All deployments** window unless it's the only window available; the client setting **Enable installation of software updates in "All deployments" maintenance window when "Software Update" maintenance window is available** (Software updates group, default No) changes this, and also applies to windows scoped to **Task sequences**. [DOC S-db7ytzl6]
- A deployment only runs in a window if its maximum allowed run time fits within the window's duration; if it can't run, the client alerts and retries at the next window with available time. Once a task sequence starts inside a window, it keeps running even if the window closes. [DOC S-db7ytzl6]
- Distinction: a *maintenance window* applies to a client (device collection); a *service window* applies to a site server. [DOC S-db7ytzl6]

### Software updates maintenance (WSUS/SUP cleanup)
- Starting in version 1810, ConfigMgr's WSUS cleanup runs after every sync: it expires updates in WSUS on CAS/primary/secondary sites, builds a list of superseded updates from supersedence-rule behavior configured in SUP component properties, expires the matching configuration items in the console, and declines them in WSUS; a separate 7-day cleanup removes unneeded update configuration items from the console (never removing an expired update that is still deployed). [DOC S-kwxqaq5a]
- "Months to wait before a superseded update is expired" is measured from the creation date of the *superseding* update, not the superseded one. [DOC S-kwxqaq5a]
- Starting in version 1906, the **WSUS Maintenance** tab adds **Decline expired updates in WSUS according to supersedence rules** (declines expired/superseded updates per Configuration Manager's own supersedence rules) and **Remove obsolete updates from the WSUS database** (cleans up unused updates/revisions in SUSDB); Microsoft recommends enabling both at the top-level site so ConfigMgr, not a manual WSUS Cleanup Wizard run, maintains SUSDB. [DOC S-kwxqaq5a]
- **Add non-clustered indexes to the WSUS database** (WSUS Maintenance tab) speeds up ConfigMgr's own cleanup by indexing `tbLocalizedPropertyForRevision` and `tbRevisionSupersedesUpdate`; when the WSUS SQL instance is remote, the SUP's WSUS connection account (or the site server computer account if none is set) needs permission to create indexes. [DOC S-kwxqaq5a]
- The **Computers not contacting the server** and **Unneeded update files** options in the standalone WSUS Server Cleanup Wizard are not relevant when ConfigMgr manages content/devices, unless WSUS reporting events are enabled. [DOC S-clekmxkf]
- A SQL query against SUSDB (`Select COUNT(UpdateID) from vwMinimalUpdate where IsSuperseded=1 and Declined=0`) is used to check superseded-update backlog; more than roughly 1500 undeclined superseded updates is flagged as a threshold that can cause client/server scan and sync issues. [DOC S-clekmxkf]
- Cleanup progress is visible in `wsyncmgr.log` (row already in `mecm/log-files.csv`): `Calling WSUS Cleanup.` (start), `Successfully completed WSUS Cleanup.` (expired-updates cleanup done), `Cleanup processed <n> total updates and declined <n>` (supersedence decline done), `Deleting old expired updates...` / `Deleted <n> expired updates total` (ConfigMgr console cleanup). [DOC S-kwxqaq5a]

### Express installation files / content delivery
- Configuration Manager no longer supports Express Updates ("Express installation files"); the feature has been fully replaced by the Unified Update Platform (UUP), and Express-related options should not be selected in the console. [DOC S-zmtevvp6]
- On-premises Windows 11 22H2+ (and Server 2025) quality updates are delivered via UUP, which interoperates with WSUS/ConfigMgr; UUP requires roughly an extra 10 GB of storage per Windows version/processor architecture. [DOC S-2w3gpaiz]
- Delivery Optimization integration with ConfigMgr boundary groups (client setting) auto-assigns a Delivery Optimization Group ID per boundary group so peers can source content from each other; Delivery Optimization itself must stay enabled (default) and not be overridden by a domain GPO when ConfigMgr manages updates. [DOC S-zmtevvp6]
- Starting in version 2203, the Delta Download client setting must have **Allow clients to download delta content when available** set to **No**, with the delta-content receive port left at its default (8005) or a custom value. [DOC S-zmtevvp6]
- Delta-download troubleshooting log files: `WUAHandler.log` and `DeltaDownload.log` (both already rows in `mecm/log-files.csv`). [DOC S-zmtevvp6]

### Third-party update catalogs
- Third-party updates must first be enabled once per hierarchy: top-level site > **Configure Site Components > Software Update Point > Third-Party Updates** tab > **Enable third-party software updates**; this must be redone if the top-level SUP's WSUS server is ever replaced. [DOC S-z37n7cfj]
- Subscribing to a catalog syncs its metadata into the SUPs' WSUS servers and requires reviewing/approving a **Third-party Software Updates Catalog**-type certificate (managed under **Administration > Security > Certificates**); custom catalogs must be served over HTTPS with digitally signed update content. [DOC S-z37n7cfj]
- V3 catalogs (categorized) additionally offer **Select Categories** (sync all vs. selected categories) and **Stage Content** (don't stage / auto-stage selected categories to the top-level SUP's WSUSContent directory) options not available for non-v3 catalogs. [DOC S-z37n7cfj]
- After a catalog downloads, product metadata must be synced from the WSUS database into the ConfigMgr database (manual sync), then the desired product(s) must be enabled under classifications/products, then synced again to pull the actual update metadata. [DOC S-z37n7cfj]
- Third-party sync is handled by the `SMS_ISVUPDATES_SYNCAGENT` component on the top-level default SUP; its log, `SMS_ISVUPDATES_SYNCAGENT.log`, is already a row in `mecm/log-files.csv`. [DOC S-z37n7cfj]

### Orchestration groups
- Orchestration groups (evolution of the older "Server Groups" feature; no longer pre-release starting in version 2111) let admins update devices by percentage, explicit count, or an explicit ordered sequence, with optional pre-/post-install PowerShell scripts run on each member around the deployment (and any required restart). [DOC S-n25n5lgu]
- Orchestration groups apply only to software update deployments, not to other deployment types; normal maintenance windows and deployment schedules still apply on top of orchestration-group rules. [DOC S-ydpvgyqk]
- Orchestration starts automatically for the whole group the moment any member client tries to install a software update at its deadline or during a maintenance window; it can also be started manually (**Start Orchestration**, optionally **Ignore all applicable windows for the members** to bypass maintenance windows, added in version 2103) or reset per member (**Reset Orchestration Group Member**) after a *Failed* state. [DOC S-ydpvgyqk]
- Member states: Idle, Waiting (queued for its install-lock turn), In progress, Failed, Reboot pending; a `Sequence Number` column shows a member's queue position. [DOC S-ydpvgyqk]
- Pre-/post-scripts: max length 50,000 bytes (25,000 Unicode characters), must return `0` for success, and cannot take parameters; starting in version 2111 they require separate approval before they take effect, and editing an approved script resets it to **Waiting for approval**. [DOC S-ydpvgyqk]

### Windows servicing / feature updates via WSUS and OSD
- The **Install Software Updates** task sequence step scans for and deploys applicable updates during OS deployment/upgrade; recommended mitigations for its known long-timeout/missed-update issues are offline-servicing the image first, reducing the WIM to a single index, and shrinking image size, plus declining unnecessary classifications/products/languages and reindexing the site database to shrink the update catalog the client scans against. [DOC S-7opbzkmt]
- Task sequences targeting Windows Embedded write-filter devices need the **Write filter handling for Windows Embedded devices** client setting (Computer Agent group; see `mecm/client-settings.md`) configured so update changes commit at the deadline or during a maintenance window and persist through a restart. [DOC S-3srrd54u]
- Starting in version 2002 (Windows Server support added 2006), when a servicing stack update (SSU) is bundled with other updates in a single non-user-initiated install, ConfigMgr installs the SSU first, then runs a software-update evaluation cycle to install the rest without an extra restart or maintenance window. [DOC S-2w3gpaiz]

### Co-management interplay
- Co-management's Windows Update policies workload moves control of Windows Update client behavior from ConfigMgr client settings/WSUS-based deployments to the Intune Update CSP surface (update rings, feature/quality/driver update policies); see `windows/windows-update-management.md` for that CSP-level detail and `intune/co-management.md` for the workload switch itself. [DOC S-2w3gpaiz]

## Reference
- `mecm/client-settings.md` documents the client-side Software updates and Computer Agent group settings this article's ADR/deployment/maintenance-window behavior interacts with (deadline grace period, deadline randomization override, script execution timeout, write-filter handling); that article already lists "Software updates" as an unexpanded client-settings group, and this article is the detailed SUM reference for it.
- `windows/windows-update-management.md` covers the Intune/cloud side of Windows Update (Update CSP, Autopatch, hotpatch, WUfB reports); this article covers the on-premises ConfigMgr/WSUS side. Cross-linked from there under co-management.
- `windows/azure-update-manager.md` covers Azure Update Manager for Azure VMs and Arc-enabled servers, which can use the same on-premises WSUS server as its update source (see that article's Facts, "Update sources (WSUS) and supported OS") as an alternative or complement to ConfigMgr-managed clients.
- `intune/co-management.md` lists the Windows Update policies workload that moves control between the two surfaces documented in this article and `windows/windows-update-management.md`.
- `windows/delivery-optimization.md` documents the Delivery Optimization CSP settings and Microsoft Connected Cache for Enterprise referenced by the boundary-group DO Group ID client setting above (Facts, "Delivery Optimization integration").
- `mecm/log-files.csv` has the full log reference for every component named above (WUAHandler.log, UpdatesDeployment.log, UpdatesHandler.log, UpdatesStore.log, WCM.log, wsyncmgr.log, ruleengine.log, ScanAgent.log, ServiceWindowManager.log, PatchDownloader.log, SUPSetup.log, WSUSCtrl.log, SMS_ISVUPDATES_SYNCAGENT.log, DeltaDownload.log, StateMessage.log) -- cited by row above rather than duplicated here.
- `SMS_AutoDeployment` (the ADR WMI class) key properties: `AutoDeploymentID` (key, SInt32), `Name`, `Description`, `AutoDeploymentEnabled` (Boolean, default `true`), `AutoDeploymentProperties`/`ContentTemplate`/`DeploymentTemplate`/`UpdateRuleXML` (XML strings), `IsServicingPlan` (Boolean, default `true`), `Schedule`, `LastRunTime`, `LastErrorCode`/`LastErrorTime` (default error code `0`); its two methods are `EvaluateAutoDeployment` and `EvaluateAllAutoDeployment`. The related `SMS_ADRDeploymentSettings` class carries per-deployment ADR settings: `RuleID`, `AssociatedDeploymentID`, `CollectionID`/`CollectionName`, `DeploymentNumber`, `DeploymentTemplate`, `Enabled`. Per-version history of every ADR wizard page option, and a distinct `SMS_SUPComponent` class, were not found on the fetched WMI reference pages (not exhaustively reviewed). [DOC S-fq4xtwh3]
- Orchestration groups are configured via `Set-CMOrchestrationGroup` (module `ConfigurationManager`; parameters `-Name`/`-Id`, `-NewName`, `-Description`, `-OrchestrationType` [`Number`/`Percentage`/`Sequence`], `-OrchestrationValue`, `-OrchestrationTimeOutMin`, `-MaxLockTimeOutMin`, `-PreScript`/`-PreScriptTimeoutSec`, `-PostScript`/`-PostScriptTimeoutSec`, `-MemberResourceIds`) alongside `Get-`/`New-`/`Remove-CMOrchestrationGroup`; the cmdlet returns an `SMS_MachineOrchestrationGroup` WMI object. No separate Graph automation surface for orchestration groups was found — they are PowerShell/WMI/console-only. [DOC S-ix237xay]

## Examples
- Create a scheduled Patch Tuesday-style ADR that adds Critical/Security updates for Windows Server to an existing deployment package, on a weekly schedule (fixture names, collection `PL-SRV-0042`'s collection):
  ```powershell
  $Schedule = New-CMSchedule -DayOfWeek Wednesday
  New-CMSoftwareUpdateAutoDeploymentRule -Name "Monthly-Server-Updates" `
    -CollectionName "All Servers" -DeploymentPackageName "Updates-2026-09" `
    -AddToExistingSoftwareUpdateGroup $true -UpdateClassification "Critical Updates","Security Updates" `
    -DateReleasedOrRevised LastMonth -RunType RunTheRuleOnSchedule -Schedule $Schedule `
    -DeadlineTime $true -DeadlineTimeUnit Days -AlertTime 4 -AlertTimeUnit Weeks -EnabledAfterCreate $true
  ```
- Run software update summarization on demand instead of waiting for the schedule, then check the schedule:
  ```powershell
  Invoke-CMSoftwareUpdateSummarization
  Get-CMSoftwareUpdateSummarizationSchedule
  ```
- Add a follow-up required deployment to an existing ADR (fixture package/collection names):
  ```powershell
  New-CMSoftwareUpdateDeployment -SoftwareUpdateGroupName "Monthly-Server-Updates" `
    -CollectionName "Pilot Servers" -DeploymentName "Pilot-2026-09" -DeploymentType Required `
    -SendWakeUpPacket $true -UserNotification DisplayAll
  ```
- Check the WSUS superseded-update backlog before enabling automatic supersedence decline (run against SUSDB):
  ```sql
  SELECT COUNT(UpdateID) FROM vwMinimalUpdate WHERE IsSuperseded = 1 AND Declined = 0;
  ```
- Confirm ADR-driven WSUS cleanup completed, by tailing `wsyncmgr.log` on the top-level site server for `PL-SRV-0042`:
  ```powershell
  Get-Content "$env:ProgramFiles\Microsoft Configuration Manager\Logs\wsyncmgr.log" -Tail 50 |
    Select-String "Cleanup processed|Successfully completed WSUS Cleanup"
  ```
