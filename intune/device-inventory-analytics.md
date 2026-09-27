---
topic: intune/device-inventory-analytics
priority: P2
applies_to: "Intune Endpoint analytics, Intune Advanced Analytics (Intune Suite), docs retrieved 2026-09-26"
retrieved_utc: 2026-09-26
sources: [S-7dabdnod, S-emqg5tvg, S-rjiy4cip, S-6jy3vnik, S-mldzfsv6, S-sbldpqec, S-mhtox7ch, S-v26wvp2b, S-uiolk6la, S-ylp2o7ml, S-tiumn4r3, S-nwf5cf5q, S-pnhn6vx2, S-x35diqus, S-boionyor, S-hr6egysd]
status: complete
---

# Endpoint analytics and Advanced Analytics (device inventory, scores, anomalies)

## Summary
Endpoint analytics scores managed Windows devices (Startup performance, Application reliability, Work from anywhere)
on a 0-100 scale against an "All organizations (median)" baseline, using data an Intune data collection policy
gathers and processes on a ~24 h cycle (max end-to-end latency 96 h). Advanced Analytics (an Intune Suite / add-on
licensed capability, built on endpoint analytics) adds Resource performance, Battery health, Anomalies, Device
timeline, Device scopes and Device query. Device-level hardware/software inventory itself (BIOS, disk, registry,
app inventory) is collected by the **properties catalog** device configuration profile — see `intune/device-query.md`
for that profile and for device query, which this article does not repeat.

## Facts
### Endpoint analytics core
- Endpoint analytics reports: Startup performance, Application reliability, Work from anywhere, and (with additional licensing) Advanced Analytics extensions. [DOC S-7dabdnod]
- Endpoint analytics contributes to the "technology experiences" category of Microsoft Adoption Score, with device-level insights that complement organizational productivity metrics. [DOC S-7dabdnod]
- That Adoption Score shows an organizational Endpoint analytics score, its 180-day trend, and Startup performance scores to roles outside Intune is not stated on the current page. [UNK: not in S-7dabdnod as re-read 2026-09-27]
- Device platform requirement: Windows Pro, Pro Education, Enterprise, or Education. [DOC S-7dabdnod]
- Supported device management: Intune-managed, co-managed (Intune + Configuration Manager), Configuration Manager via tenant attach, Microsoft Entra joined, Microsoft Entra hybrid joined; the Connected User Experiences and Telemetry (DiagTrack) service must be enabled and running. [DOC S-7dabdnod]
- Network requirement for Intune-managed/co-managed devices: `https://*.events.data.microsoft.com` reachable (functional data upload endpoint); ConfigMgr-managed devices instead need `https://graph.windows.net` and `https://*.manage.microsoft.com` reachable from the site server role, not from the client. [DOC S-7dabdnod]
- Licensing: devices enrolled in endpoint analytics need a valid Intune license; the Advanced Analytics extensions require additional licensing. [DOC S-7dabdnod]
- RBAC to configure endpoint analytics: School Administrator role, or a custom role with **Endpoint Analytics/Read**, **Endpoint Analytics/Create, Update, Delete**, **Organization/Read**, **Managed Devices/Read**, and **Device configurations/Create, Read, Assign**. [DOC S-7dabdnod]
- RBAC to read endpoint analytics reports: Help Desk Operator, Read Only Operator, Endpoint Security Manager, School Administrator, a custom role with **Endpoint Analytics/Read** + **Organization/Read** + **Managed Devices/Read**, or the Entra built-in role Reports Reader. [DOC S-7dabdnod]
- ConfigMgr requires tenant attach to use endpoint analytics; using multiple ConfigMgr hierarchies with a single endpoint analytics instance is not supported. [DOC S-7dabdnod]
- Data collection: an admin starts gathering data via the **Intune data collection policy** (assigned to All Devices by default, reassignable); Intune/co-managed devices send required functional data near-real-time, processed every 24 hours; ConfigMgr-managed devices send data to the site server every 24 hours and the tenant-attach connector forwards it to the cloud gateway service every hour; results (individual device + org aggregates) are published via Graph APIs; maximum end-to-end latency is 96 hours. [DOC S-sbldpqec]
- Startup score needs device reboots after policy assignment; it can take weeks after enrollment for a startup score to appear, since it depends on boot-time telemetry. [DOC S-sbldpqec, DOC S-rjiy4cip]

### Scores, baselines, insights
- Endpoint analytics scores range 0-100; lower scores indicate room for improvement. [DOC S-emqg5tvg]
- A device/model status of "insufficient data" means fewer than 5 devices are reporting for that scope. [DOC S-emqg5tvg]
- The built-in baseline is "All organizations (median)", computed from anonymized/aggregated scores across all enrolled tenants; admins can create custom baselines from current metrics to track progress or regressions; data sharing for the baseline can be stopped at any time (stop gathering data). [DOC S-emqg5tvg]
- Insights and recommendations is a prioritized list showing the point gain from completing each recommendation; entries are filtered to whatever report/subnode is open. [DOC S-emqg5tvg]
- Scores are shown per-tenant, per-device (Device scores tab / device's User experience page) and per-model (Model scores tab, useful for hardware-refresh planning) (S-emqg5tvg); on the Startup performance Device performance tab admins see only devices in their scope tags, while aggregated scores and insights use all enrolled devices (S-rjiy4cip). [DOC S-emqg5tvg, S-rjiy4cip]
- Known filter limits: Disk type filter doesn't support "Unknown"; filtering on Startup performance score from Overview > Device Scores returns devices whose score shows "--". [DOC S-emqg5tvg]

### Startup performance
- Startup score = weighted average of Boot score (power-on to sign-in; last boot per device, excluding update phases) and Sign-in score (credential entry to responsive desktop, excludes first sign-ins and sign-ins right after a feature update); each 0 (poor)-100 (excellent). [DOC S-rjiy4cip]
- A desktop counts as "responsive" once rendered and CPU usage drops below a moderate threshold, or the device responds to user actions. [DOC S-rjiy4cip]
- Retention for boot/sign-in events is 29 days; a device with no boot/sign-in event in the last 29 days drops out of the report. [DOC S-rjiy4cip]
- Model performance tab only shows models with ≥10 devices, so restart/Stop-error averages are statistically meaningful; it also shows average restarts and average Stop errors per model over the last 30 days. [DOC S-rjiy4cip]
- OS restart history (device drill-in) lists the 10 most recent restarts within 30 days, each with a restart category, and for Stop errors, the stop/bug-check code and a Failure bucket ID; this table updates faster (lower latency) than the 30-day daily aggregates on Device performance, so counts between the two can legitimately differ. [DOC S-rjiy4cip]
- Startup processes tab lists processes that delay "time to responsive desktop" and keep CPU above 50% post-render, limited to processes affecting ≥10 devices in the tenant; reports Device count, Median delay, Total delay per process. [DOC S-rjiy4cip]
- Restart categories: three abnormal (Stop errors, Long power button press, Unknown) and three normal (Update, Shutdown (no update), Restart (no update)); guidance targets roughly one Update restart per device per month (fewer implies missed patching, more implies excess disruption), and Restart (no update) close to zero. [DOC S-rjiy4cip]
- Hard-disk-drive insight: HDD boot drives typically give boot times 3-4x longer than SSD; the report estimates the startup-score gain from moving affected devices to SSD. [DOC S-rjiy4cip]
- Group Policy insight flags devices where GPO processing delays boot/sign-in; Microsoft recommends considering migration to Intune security baselines and cloud management (with Group Policy analytics) rather than only optimizing GPOs. [DOC S-rjiy4cip]

### Application reliability
- App reliability score (0-100) is derived per app from **Mean time to failure** (Total usage duration over 14 days ÷ Total crashes over 14 days) and Total usage duration; apps with 0 crashes in 14 days get "No crash events". [DOC S-6jy3vnik]
- App performance tab (14-day rolling window) includes only foreground apps meeting a usage threshold: active-device count > 5 OR > 2% of the tenant's enrolled devices, whichever is larger; apps with ≤~10 minutes total foreground usage on a device may be excluded from that device's data. [DOC S-6jy3vnik]
- Engagement time (used for usage duration) = interactive time + keep-alive time (e.g., presenting a deck or playing video counts as keep-alive). [DOC S-6jy3vnik]
- Crash events are capped at 10 per app, per device, per day, to stop outlier devices skewing reliability scores. [DOC S-6jy3vnik]
- App performance details drill-in has App versions (crashes / devices with crashes per version) and OS versions (Mean time to failure by Windows version) tabs. [DOC S-6jy3vnik]
- Device performance tab's "Total app crashes (14 days)" aggregates crashes from any app on that device, not one app; selecting a device opens a timeline of app crash/unresponsive events (up to 14 days, custom range via Filter). [DOC S-6jy3vnik]
- Known ConfigMgr issue: devices enrolled via ConfigMgr tenant attach can be missing from the report if they fail to download the ServiceCertificate policy (`CCM_PendingPolicyState`, PolicyID `B27D9CFC-84AD-0AF8-9DF1-23EE05E8C05D`); mitigation resets that pending-policy state via WMI so the certificate re-downloads, with up to 72 h before data reappears. [DOC S-6jy3vnik]

### Work from anywhere
- Work from anywhere score (0-100) is a weighted average of 4 metrics: Windows (supported OS version share), Cloud management (CMG/tenant-attach/co-management/Intune adoption share), Cloud identity (% Entra-joined or hybrid-joined), Cloud provisioning (% Windows 365 Cloud PCs or devices Autopilot-registered with a deployment profile assigned). [DOC S-mldzfsv6]
- A device counts as active for this report if it uploaded ≥1 endpoint analytics event (boot, sign-in, or app crash) in the past 29 days. [DOC S-mldzfsv6]
- Cloud provisioning credit requires an explicit (non-default/non-inherited) Autopilot deployment profile assignment; a device that only inherits the default profile from the "All Devices" group is not credited. [DOC S-mldzfsv6]
- Windows 11 hardware readiness (Capable / Not capable / Upgraded / Unknown, with a blocker breakdown) is shown under the Windows metric but does **not** affect the Work from anywhere score itself; "Unknown" status usually means the device is inactive. [DOC S-mldzfsv6]
- There is currently no "All organizations (median)" commercial baseline for the Work from anywhere subscore metrics. [DOC S-mldzfsv6]

### Advanced Analytics (Intune Suite add-on)
- Advanced Analytics requires a subscription in addition to Intune Plan 1 or Plan 2 and is automatically enabled tenant-wide once licensing requirements are met (up to 48 h to appear). [DOC S-mhtox7ch]
- Supported clouds: public (Global) and sovereign GCC High and DoD; in DoD, Device query and the Resource performance report are **not** supported. [DOC S-mhtox7ch]
- Device configuration support mirrors endpoint analytics: Intune-managed, co-managed, Entra joined, Entra hybrid joined Windows devices. [DOC S-mhtox7ch]
- With Advanced Analytics enabled: endpoint analytics reports gain Resource performance, Battery health, Anomalies, and Device scopes; single-device views gain Battery health, Device timeline (which **replaces** the per-device Application reliability tab), Resource performance, and Device query; the Devices node gains Device query for multiple devices; a STIG audit baseline becomes available. [DOC S-mhtox7ch]
- Device query for multiple devices additionally requires a properties catalog policy configured and deployed (see `intune/device-query.md`). [DOC S-mhtox7ch]
- Device query for multiple devices can export results to a .csv file (all or selected columns, up to 50,000 results). [DOC S-x35diqus]
- That Advanced Analytics has no export connector to external monitoring tools is not stated on the current page. [UNK: not in S-mhtox7ch as re-read 2026-09-27]
- Endpoint analytics data from Intune/co-managed devices is processed every 24 hours (S-sbldpqec); clients need a restart to fully enable all analytics (S-rjiy4cip); device query retrieves live device data for troubleshooting (S-mhtox7ch). [DOC S-sbldpqec, S-rjiy4cip, S-mhtox7ch]

### Anomalies report
- Monitors application hangs, app crashes, and Stop Error Restarts to flag device health regressions before they reach the help desk; correlates deployment/configuration changes to suggest root causes and groups affected/at-risk devices into device correlation groups (only generated for medium/high-severity anomalies). [DOC S-v26wvp2b]
- Four detection models: threshold-based heuristic (fixed, non-customizable thresholds), paired t-tests (before/after a change on the same device), population Z-score (outlier devices/apps across the fleet, needs large datasets), time-series Z-score (sliding-window mean/stdev for temporal patterns). [DOC S-v26wvp2b]
- That a high event volume is usually needed before something is flagged anomalous (so low-usage devices can show no anomalies) is not stated on the current page. [UNK: not in S-v26wvp2b as re-read 2026-09-27]

### Device timeline
- Per-device history of events (boot, sign-in, app crash/unresponsive, detected anomalies) reached via **Devices > Windows > (device) > User Experience > Device Timeline**; filterable by date, device, user, event source, event level. [DOC S-uiolk6la]
- Replaces the per-device Application reliability tab when Advanced Analytics is enabled (but that tab is where the per-device app-reliability *score* still lives, via Device performance search). [DOC S-uiolk6la]
- Most events surface within 24 hours; delayed events (e.g., a Stop error before a delayed reboot) upload at the next opportunity but keep their original timestamp; timestamps are localized to the viewing admin's time zone. [DOC S-uiolk6la]
- Device timeline is available only for Intune-managed (incl. co-managed) devices, not for ConfigMgr-only devices even with Advanced Analytics enabled. [DOC S-uiolk6la]

### Battery health
- Battery health score = weighted average of Battery capacity score (0-100, from maximum capacity = full-charge capacity ÷ design capacity, e.g. 35 Wh full-charge / 70 Wh design = 50% max capacity) and Battery runtime score (0-100, from estimated device runtime on a full charge under comparable usage). [DOC S-ylp2o7ml]
- Insights: Low battery capacity (<60% = most impacted, 60-80% = moderately impacted), Low estimated runtime (<3 hours = most impacted), and Good capacity but poor runtime (power-hungry apps draining an otherwise healthy battery, or a battery designed for low capacity by procurement choice). [DOC S-ylp2o7ml]
- Report tabs: Device performance (incl. cycle count — full discharge equivalents, possibly fractional across sessions; shows `0*` for new batteries with limited data), Model performance, OS performance, App impact (cumulative battery drain per app over 14 days). [DOC S-ylp2o7ml]
- A battery count >2 devices (external/UPS battery) is flagged with an asterisk; unavailable data points show as `Not available` in the UI and `-1` in the exported CSV. [DOC S-ylp2o7ml]

### Device inventory (properties catalog) — see intune/device-query.md
- The properties catalog is the Windows device configuration profile (Platform: Windows 10 and later; Profile type: Properties catalog) used to collect hardware, configuration (registry) and application properties from managed Windows devices. [DOC S-tiumn4r3]
- Splitting app and device inventory across policies, and "collect" winning over "don't collect" when several policies target one device, is not stated on the current page. [UNK: not in S-tiumn4r3 as re-read 2026-09-27]
- Required Application Properties (collected automatically with any property of that category): App Name, App Version, Architectures, Install Scope, Install Scope Platform User ID, Install Scope User ID, Publisher. [DOC S-tiumn4r3]
- Optional app-inventory properties (Install location, Install date, Estimated size, Platform-specific app ID, Uninstall command, Modify command, Languages, Install Scope User Name) are not listed on the current page. [UNK: not in S-tiumn4r3 as re-read 2026-09-27]
- Registry key inventory (a properties catalog capability): supports single value, non-recursive all-values-under-a-key, and same-value-across-immediate-subkeys collection; includes detection logic that skips values flagged as potentially sensitive; initial-release limits are HKLM-only, 6 KB per value, 100 registry keys per device. [DOC S-tiumn4r3]
- Client-side properties catalog logs are at `C:\Program Files\Microsoft Device Inventory Agent\Logs`, collectible via the Collect diagnostics remote action (see `intune/collect-diagnostics.md`). [DOC S-tiumn4r3]
- Collection can only be stopped at the category level (remove every property in that category from the profile); deleting the whole policy still leaves the last-collected Device Inventory data visible for up to 28 days. [DOC S-tiumn4r3]

The full property list, KQL device-query entities/limits, and single-/multi-device query RBAC and rate limits are covered in `intune/device-query.md`; this article does not repeat them.

### Graph API (beta)
- Endpoint/Advanced Analytics data is exposed under `deviceManagement/userExperienceAnalytics*` beta Graph resources, e.g. `userExperienceAnalyticsAnomaly` and `userExperienceAnalyticsDeviceTimelineEvents`. [DOC S-nwf5cf5q, S-pnhn6vx2]
- Further `userExperienceAnalytics*` beta resources named in earlier notes (`...RegressionSummary`, `...ResourcePerformance`, `...ImpactingProcess`, `...AppHealthAppPerformanceByAppVersion`, `...RemoteConnection`, `...NotAutopilotReadyDevice`) are not listed on the two pages cited above. [UNK: not in S-nwf5cf5q or S-pnhn6vx2 as re-read 2026-09-27]
- Permissions differ per endpoint: `GET` of a `userExperienceAnalyticsDeviceTimelineEvents` item accepts `DeviceManagementConfiguration.Read.All`/`.ReadWrite.All` or `DeviceManagementManagedDevices.Read.All`/`.ReadWrite.All` (delegated or application); listing `userExperienceAnalyticsAnomaly` accepts only the two `DeviceManagementManagedDevices` scopes. [DOC S-pnhn6vx2, S-boionyor]
- `GET /deviceManagement/userExperienceAnalyticsAnomaly` (list) is available in Global, US Government L4, US Government L5 (DOD), and China (21Vianet) national clouds. [DOC S-boionyor]
- The `userExperienceAnalyticsAnomaly` resource page exists only for `/beta` (a request for its v1.0 view falls back to `view=graph-rest-beta`). [DOC S-nwf5cf5q]
- Some `userExperienceAnalytics*` resources do have v1.0 pages, e.g. `userExperienceAnalyticsDeviceStartupHistory` (List, Get, Create, Update, Delete). [DOC S-hr6egysd]

## Reference
| Report | Belongs to | Score range | Refresh | Extra licence |
|---|---|---|---|---|
| Startup performance | Endpoint analytics | 0-100 | ~24 h, 96 h max latency | No |
| Application reliability | Endpoint analytics | 0-100 | ~24 h | No |
| Work from anywhere | Endpoint analytics | 0-100 | ~24 h | No |
| Resource performance | Advanced Analytics | n/a | ~24 h | Yes (Intune Suite/add-on) |
| Battery health | Advanced Analytics | 0-100 | ~24 h | Yes |
| Anomalies | Advanced Analytics | n/a (severity) | near real-time flag, model-dependent | Yes |
| Device timeline | Advanced Analytics | n/a | most events <24 h | Yes |
| Device query (single/multi) | Advanced Analytics | n/a | live (single) / collected (multi) | Yes; see `intune/device-query.md` |

Cross-links: `intune/device-query.md` (properties catalog fields, KQL entities, device query RBAC/limits — read that article for inventory collection detail), `intune/collect-diagnostics.md` (Device Inventory Agent log collection), `intune/co-management.md` and `intune/tenant-attach.md` (ConfigMgr data paths into endpoint analytics).

## Examples
List anomalies for a tenant (Graph beta, delegated `DeviceManagementManagedDevices.Read.All`):
```
GET https://graph.microsoft.com/beta/deviceManagement/userExperienceAnalyticsAnomaly
Authorization: Bearer <token>
```

Get one device's timeline events:
```
GET https://graph.microsoft.com/beta/deviceManagement/userExperienceAnalyticsDeviceTimelineEvents/{userExperienceAnalyticsDeviceTimelineEventsId}
Authorization: Bearer <token>
```

WMI check for the ConfigMgr ServiceCertificate policy issue (Application reliability, device `PL-LT-00123`), run locally on the device with an elevated PowerShell prompt:
```powershell
$query = "SELECT * FROM CCM_PendingPolicyState WHERE PolicyID=""B27D9CFC-84AD-0AF8-9DF1-23EE05E8C05D"""
Get-WmiObject -Query $query -Namespace "root\ccm\policyagent"
```
