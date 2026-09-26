---
topic: windows/event-forwarding-sysmon
priority: P2
applies_to: "Windows Event Forwarding/Collector (Vista+, Server 2008 R2+), Sysmon (Sysinternals v15.22, and built-in Windows 11/Server 2025 optional feature), docs ms.date through 2026-09"
retrieved_utc: 2026-09-26
sources: [S-xbogq5nf, S-5pkzlomo, S-uzewrile, S-odr3mgme, S-zcba3zc7, S-iuugqauq, S-benv5fbb, S-k5vpsayn]
status: partial
files: [windows/sysmon-events.csv]
---

# Windows Event Forwarding/Collector and Sysmon

## Summary
Windows Event Forwarding (WEF) reads events already logged on a device and forwards them over WS-Management to a
Windows Event Collector (WEC) server, into the local `ForwardedEvents` log by default; it is passive and cannot
enable event channels, resize logs, or change audit policy itself. Subscriptions are collector-initiated (pull,
sources named on the WEC server) or source-initiated (push, GPO `SubscriptionManager` names the collector); both
are managed with `wecutil`. Sysmon is a separate driver/service that generates rich, filterable telemetry (29
numbered event types plus an error event) to its own channel, commonly consumed via WEF; as of a 2026-02 change it
also ships as a built-in Windows 11/Server 2025 optional feature, disabled by default, that cannot coexist with the
standalone Sysinternals tool. Event ID table: `sysmon-events.csv`. Related sources: `logs/sources.md` (channel
inventory), `logs/otel-collector-receivers.md` (collecting Sysmon/forwarded events with the OTel windowseventlog
receiver), `defender/advanced-hunting.md` (querying ingested device events centrally).

## Facts

### WEF/WEC subscriptions
- Two subscription types: collector-initiated (pull; the WEC server's subscription lists the source computers, whose credentials must have event-log read access) and source-initiated (push; sources are configured via GPO and the collector's subscription defines who may connect via an ACL). [DOC S-iuugqauq, S-odr3mgme]
- `wecutil qc` (quick-config) enables the `ForwardedEvents` channel if disabled, sets the Windows Event Collector service (wecsvc) to delayed start, and starts it if not running. [DOC S-zcba3zc7]
- `wecutil {cs|create-subscription} <ConfigFile.xml> [/cun:<user> /cup:<pass>]` creates a subscription from an XML file; `{gs|get-subscription} <SubId>` shows its configuration; `{qc|quick-config}` configures the collector service; `{es|enum-subscription}` lists subscription names. [DOC S-zcba3zc7]
- Source-initiated GPO client setting: Computer Configuration > Administrative Templates > Windows Components > Event Forwarding > "Configure target Subscription Manager", enabled, value `Server=http://<fqdn-of-collector>:5985/wsman/SubscriptionManager/WEC,Refresh=<seconds>` (example uses `Refresh=10`; another example `Refresh=60`); apply with `gpupdate /force`. [DOC S-benv5fbb]
- Forwarding the Security log requires adding the NETWORK SERVICE account (source-initiated) to the built-in **Event Log Readers** group; for collector-initiated pull, the collector-side credentials need equivalent read access on each source. [DOC S-iuugqauq]
- Three built-in event delivery/optimization options: **Normal** (pull, reliable, batches 5 items, 15-minute batch timeout), **Minimize Bandwidth** (push, 6-hour batch timeout and 6-hour heartbeat interval), **Minimize Latency** (push, 30-second batch timeout). A fourth, **Custom**, is set only via `wecutil ss <SubId> /cm:Custom` plus `/dmi:<count>` (DeliveryMaxItems) and `/dmlt:<ms>` (DeliveryMaxLatencyTime, milliseconds). [DOC S-odr3mgme]
- `wecutil ss "<SubName>" /cf:Events` switches forwarded-event content format from the default "Rendered Text" (localized description included, roughly doubling/tripling event size) to "Events"/binary (raw event XML, more compact). [DOC S-odr3mgme]
- WEC scalability: general guidance is up to ~3,000 events/second per WEC server on commodity hardware, limited by disk I/O (writing to the local EVTX), open TCP connections, and registry size (one key per unique lifetime source per subscription). Event Viewer's Subscriptions node becomes sluggish past 1,000 lifetime sources per subscription, is unusable past 50,000 (use `wecutil` instead), and past 100,000 the collector's registry becomes unreadable and likely needs rebuilding. [DOC S-odr3mgme]
- WEF connections are mutually authenticated regardless of HTTP/HTTPS; Kerberos is used by default with NTLM fallback (NTLM can be disabled via GPO to force Kerberos only); HTTPS is used when certificate-based authentication is required instead of Kerberos. [DOC S-odr3mgme]
- The WEC server tracks each source's delivery bookmark and last heartbeat time in its own registry (not a cache with a documented TTL); on reconnect the source resumes from its last bookmark. If the local event log wraps before reconnecting, forwarded events are lost silently (no gap notification). [DOC S-odr3mgme]
- Approximate scaling guide for a downstream data store by ingest rate: 0-5,000 events/sec -> SQL or SIEM/SEM; 5,000-50,000 -> SEM; 50,000+ -> Hadoop/HDInsight/Data Lake style system. [DOC S-odr3mgme]
- Three parameters control connection frequency for a custom subscription: the GPO `Refresh=` value (how often a client polls `/WEC` for its subscription list), `DeliveryMaxLatency` (batch timeout), and `HeartbeatInterval` (inactivity threshold in the collector's Runtime Status view); set with `wecutil ss <SubName> /cm:"Custom"` then `wecutil ss <SubName> /dmlt:<ms>` and `/hi:<ms>` (values in milliseconds, e.g. `7200000` = 2 hours). [DOC S-k5vpsayn]
- The **Eventlog-ForwardingPlugin/Operational** channel on the source logs WEF subscription success/warning/error events; a WEF client shows no UI and has no measurable performance impact even when a subscription is failing. [DOC S-odr3mgme]
- Recommended minimum client prerequisite for a WEF deployment: an audit policy at least as broad as the guide's baseline (e.g. Logon success/failure, Process Creation success, Security Group/User/Computer Account Management, Policy Change categories) plus enabling any disabled event channels the subscription queries, since WEF only reads events that already exist and cannot itself turn on auditing or channels. [DOC S-odr3mgme]

### Sysmon (standalone, Sysinternals)
- Install: `sysmon64 -accepteula -i [<configfile>]` (or `sysmon -i` on the matching-bitness binary); update config: `sysmon -c [<configfile>]`, dumps current config if no file given, resets to defaults with `sysmon -c --`; install event manifest only: `sysmon -m`; print config schema: `sysmon -s [<schemaversion>|all]`; uninstall: `sysmon -u [force]`. Neither install nor uninstall requires a reboot; configuration updates via `-c` apply immediately without a restart. [DOC S-xbogq5nf]
- Events are written to `Applications and Services Logs/Microsoft/Windows/Sysmon/Operational` (Vista and later); on pre-Vista systems they went to the `System` log. Event timestamps are UTC. [DOC S-xbogq5nf]
- Configuration file root is `<Sysmon schemaversion="X.YY">`; get the current schema version from `sysmon -s`. Filter rules live under `<EventFiltering>`, one tag per event type (e.g. `<ProcessCreate>`, `<NetworkConnect>`), each with `onmatch="include"` or `onmatch="exclude"`; exclude rules override include rules for the same tag, and multiple conditions on the same field are OR'd while different fields are AND'd (overridable per rule group with `groupRelation="and"|"or"`). [DOC S-xbogq5nf]
- Match conditions (case-insensitive): `is` (default), `is any`, `is not`, `contains`, `contains any`, `contains all`, `excludes`, `excludes any`, `excludes all`, `begin with`, `end with`, `not begin with`, `not end with`, `less than`, `more than`, `image` (matches full path or bare image name). [DOC S-xbogq5nf]
- Key configuration entries: `HashAlgorithms` (SHA1 default, also MD5/SHA256/IMPHASH/`*` for all; default `None` if omitted), `ArchiveDirectory` (default `Sysmon`, at each volume root, protected with a system ACL), `CheckRevocation` (default `True`), `CopyOnDeletePE` (default `False`), `DriverName`, `DnsLookup` (default `True`). [DOC S-xbogq5nf]
- Event ID 7 (ImageLoad) is disabled by default and enabled only via the `-l`/`ImageLoad` filter tag; enabling it can generate very high log volume. Event ID 3 (NetworkConnect) is also disabled by default. [DOC S-xbogq5nf]
- Event ID 23 (FileDelete, archived) copies the deleted file into `ArchiveDirectory`, which "under normal operating conditions... might grow to an unreasonable size"; event ID 26 (FileDeleteDetected) logs the same kind of delete without archiving the file. [DOC S-xbogq5nf]
- Standalone Sysmon "Runs on": Client Windows 11 and higher; Server Windows Server 2019 and higher (per the current Sysinternals page). [DOC S-xbogq5nf]
- Community configuration references named on the Microsoft page (not official Microsoft content): SwiftOnSecurity `sysmon-config`, Olaf Hartong `sysmon-modular`, Carlos Perez `SysmonCommunityGuide`. [COMMUNITY S-uzewrile]

### Sysmon: built-in Windows optional feature (status)
- Confirmed: Sysmon is now available as a built-in optional Windows feature. The `sysmon` command-reference page states "Starting February 2026, Sysmon is available as a built-in optional feature for Windows 11", and a dedicated overview page describes "Built-in System Monitor (Sysmon)" as "an optional Windows feature on Windows 11 and Windows Server 2025". [DOC S-xbogq5nf, S-5pkzlomo]
- Built-in Sysmon is disabled by default and must be explicitly enabled: `Enable-WindowsOptionalFeature -Online -FeatureName Sysmon`, then `sysmon -i [<configfile>]` to apply a configuration. [DOC S-uzewrile]
- Built-in and standalone Sysmon cannot coexist on the same device: standalone must be uninstalled before enabling the built-in feature, and if standalone is already present the built-in feature stays disabled even after a servicing update delivers it. Verify no standalone service is present with `Get-Service sysmon*` before enabling. [DOC S-uzewrile]
- Built-in Sysmon events are localized for display (rendered message text matches the device's configured language) while the underlying XML event data stays consistent across languages; this differs from standalone Sysmon and can require updating pipelines that parse rendered text instead of the XML. [DOC S-5pkzlomo]
- Non-security enhancements to built-in Sysmon ship through normal Windows quality updates (first in optional/preview updates, then broad rollout); binaries update whether or not Sysmon is enabled, and if enabled the new binaries take effect without a restart and preserve the existing configuration. Critical security fixes ship in the Update Tuesday cumulative release regardless of preview opt-in. [DOC S-5pkzlomo]
- Built-in Sysmon is explicitly documented as compatible with Windows Event Forwarding/Collection, Microsoft Defender for Endpoint/other EDR, and SIEM ingestion of its telemetry. [DOC S-5pkzlomo]
- Prerequisite for built-in Sysmon: a supported Windows 11 version (Windows Server 2025 is also named as a supported OS in the overview, though the how-to page's prerequisite step lists only Windows 11). [DOC S-uzewrile, S-5pkzlomo]

## Reference
- `sysmon-events.csv`: event_id, name, records, source_id -- all 29 numbered Sysmon event types plus the 255 Error event.
- Cross-links: `logs/sources.md` (channel/log inventory; this article's Sysmon channel name matches the `Microsoft-Windows-Sysmon/Operational` form used there), `logs/otel-collector-receivers.md` (the `windows_event_log`/`windowseventlog` receiver can tail the Sysmon or ForwardedEvents channels), `defender/advanced-hunting.md` (KQL over device events once ingested to Defender XDR/Sentinel).
- `logs/sources.md` Reference section has a back-link to this article for the WEF/Sysmon channels.

## Examples
GPO value on domain controllers to point clients at a collector `PL-SRV-0042.corp.example.com`:
```
Server=http://PL-SRV-0042.corp.example.com:5985/wsman/SubscriptionManager/WEC,Refresh=60
```
Prepare and inspect the collector:
```cmd
wecutil qc /q
wecutil es
wecutil gs "SysmonForward"
```
Install standalone Sysmon with a config file on `PL-LT-00123`:
```cmd
sysmon64 -accepteula -i C:\Sysmon\sysmonconfig.xml
```
Enable the built-in optional feature instead (no standalone installer):
```powershell
Get-Service sysmon*                       # confirm nothing is already installed
Enable-WindowsOptionalFeature -Online -FeatureName Sysmon
sysmon -i C:\Sysmon\sysmonconfig.xml
```
Query recent Sysmon process-create events on the local machine:
```
wevtutil qe "Microsoft-Windows-Sysmon/Operational" /q:"*[System[(EventID=1)]]" /c:20 /f:text
```
