---
topic: windows/smart-app-control
priority: P1
applies_to: "Windows 11 (build 22572 or later; docs cite 22H2 onward), Intune-managed and unmanaged devices"
retrieved_utc: 2026-09-28
sources: [S2198, S2199, S2200, S2201, S2202, S2203, S2204, S-5zawgrph, S-jxor524z, S-n2kx46hd, S-sy623dvx]
status: complete
---

# Smart App Control (Windows 11)

## Summary
- Smart App Control (SAC) is a Windows 11 app-execution control that allows code only if Microsoft's cloud reputation service predicts it is safe or it is signed by a CA in the Trusted Root Program. It is built on App Control for Business (WDAC).
- Three states: Evaluation (learning, does not block), On (enforcement) and Off. Windows decides the starting state; on enterprise-managed devices evaluation ends in Off within 48 hours unless the user turned it on.
- Off and On were one-way in the Settings app, and getting back to a working SAC after Off needed a clean install or reset. The March 2026 optional update KB5079391 begins rolling out an on/off switch that needs no clean install; the Learn developer pages still describe the old behaviour.
- IT can manage App Control for Business policies centrally (Intune, Group Policy, script). No documented setting manages SAC's own state, apart from a registry value that turns it off.

## Facts
- SAC combines Microsoft's app intelligence with Windows code integrity. It runs an app if the service predicts it safe, or if the app is signed by a CA in the Trusted Root Program when no prediction exists. Malware, potentially unwanted apps and unknown unsigned code are blocked. [DOC S2198]
- SAC can only be enabled on a clean install of Windows 11 build 22572 or later; resetting the device counts as a clean install. It is enabled only in certain regions (the page does not list them). [DOC S2198]
- Evaluation mode: SAC observes activity on the device and judges whether the device suits the protection, based on the variety of apps installed and used. Enforcement mode: apps not recognised by the service and not signed with a trusted certificate cannot run. [DOC S2198]
- In most cases SAC turns itself on automatically. If Windows detects usage that would clash with SAC (the page names corporate users and developers as examples), it turns SAC off automatically. A toast notification appears when SAC enters enforcement. [DOC S2198]
- On enterprise-managed devices SAC starts in evaluation mode and switches off within 48 hours unless the user turns it on first. [DOC S2200]
- No page read defines "enterprise managed" for the 48-hour rule (domain join, Entra join or MDM enrolment): the App Control page and the consumer FAQ use the term without a definition. [DER S2200, S-n2kx46hd: the term is used, not defined]
- The consumer FAQ lists reasons SAC is off: the device is enterprise-managed or has developer mode configured, a user turned it off, Windows runs in S mode, or optional diagnostic data is off. [DOC S-n2kx46hd]
- Windows Settings > Privacy & security > Windows Security > App & browser control shows the mode: On is enforcement, Evaluation is evaluation, Off means SAC is not running. [DOC S2198, S2199]
- Setting SAC to Off or On in Windows Settings is one-way. Settings only lets you change mode while the current setting is Evaluation. [DOC S2199]
- Turning SAC back on after Off on a build without the change below: Settings offers no path and SAC can only be enabled on a clean install, so the route is a reset or reinstall of Windows 11. [DER S2198, S2199]
- The March 26, 2026 optional update KB5079391 (OS builds 26200.8116 and 26100.8116) begins rolling out the ability to turn SAC on or off in Windows Security without a clean install. [DOC S-5zawgrph]
- The change first appeared for Insider build 26220.7070 (2025-11-07, gradual rollout) and in the January 2026 update KB5074105, whose note Microsoft later withdrew as planned for a future release. [DOC S-sy623dvx, S-jxor524z]
- The registry `VerifiedAndReputablePolicyState` (DWORD under `HKLM\SYSTEM\CurrentControlSet\Control\CI\Policy`) uses 0 = Off, 1 = Enforce, 2 = Evaluation. To turn SAC off across an organisation, set it and run `CiTool.exe -r` to apply. [DOC S2200]
- A documented way to force any mode (including back to On or Evaluation) edits the registry offline from the recovery command prompt: it suspends BitLocker protectors for two reboots, removes Defender dynamic signatures, writes `VerifiedAndReputablePolicyState`, `VerifiedAndReputablePolicyStateMinValueSeen` and `SacLearningModeSwitch=0`, then restarts. Microsoft labels this for testing only and warns it can weaken protection. [DOC S2199]
- The offline registry method stays labelled for testing only; on builds with KB5079391 the Windows Security switch is the documented way back to On. [DER S2199, S-5zawgrph]
- Check the mode with `citool.exe -lp`: Friendly Name `VerifiedAndReputableDesktopEvaluation` with Is Currently Enforced true is evaluation; `VerifiedAndReputableDesktop` with Is Currently Enforced true is enforcement. [DOC S2199]
- Events go to Event Viewer > Applications and Services Logs > Microsoft > Windows > CodeIntegrity > Operational: ID 3076 for evaluation (audit) and 3077 for enforcement. The default evaluation policy writes no audit events; Microsoft offers two sample audit policies (with and without the reputation service) for evaluation-mode testing. [DOC S2199]
- SAC is built entirely on App Control for Business. The reputation service it uses is the Intelligent Security Graph (ISG), which App Control for Business can also use. [DOC S2200]
- A policy with SAC's security and compatibility, plus trust for your line-of-business apps, can be built as an App Control for Business policy. SAC's policy ships with the App Control Wizard and as the example `%windir%\schemas\CodeIntegrity\ExamplePolicies\SmartAppControl.xml`. Before reusing it, remove the option `Enabled:Conditional Windows Lockdown Policy`. [DOC S2200]
- The Wizard's "Signed and Reputable" template trusts everything Allow Microsoft mode trusts, plus files from managed installers and files with good ISG reputation. [DOC S2203]
- SAC is aimed at consumers and some small businesses with simple app portfolios; Microsoft calls it the ideal starting point for most organisations, since an App Control for Business policy can match it and also trust line-of-business apps. [DOC S2200]
- With SAC on, or with App Control plus ISG, Microsoft Defender Antivirus goes to passive or hybrid mode where a non-Microsoft antivirus provides real-time protection. This is expected behaviour. [DOC S2200]
- App Control for Business is supported on Windows Pro, Enterprise, Pro Education/SE and Education. [DOC S2200]
- Intune manages App Control for Business (not SAC) through Endpoint security > App Control for Business, using the ApplicationControl CSP. A policy uses XML or built-in controls (trust Windows components and Store apps; optionally reputable apps via ISG; optionally managed installers). Assignments apply to devices only. [DOC S2201]
- Custom App Control policies can be deployed from Intune with a custom OMA-URI `./Vendor/MSFT/ApplicationControl/Policies/<Policy GUID>/Policy` (Base64 of the binary policy, GUID without braces, 350,000-byte limit). [DOC S2202]
- App Control for Business deployment options: MDM such as Intune, Configuration Manager, script, and Group Policy. [DOC S2204]
- No Intune setting, ADMX/Group Policy setting or CSP node that sets SAC's mode (Off/On/Evaluation) is documented: the App Control, Intune App Control and ApplicationControl CSP pages name none, and a Policy CSP search (2026-09-28) found none; the org-wide lever is the registry value above. [DER S2200, S2201, S2202: no SAC mode setting on any of them]
- No page read says whether a domain or Intune policy stops a user from switching SAC in Windows Security; the new switch in KB5079391 is described with no management control. [DER S2199, S-n2kx46hd, S-5zawgrph: none mentions such a policy]

## Reference
Related: `windows/app-control.md` (full App Control for Business policy rule options table, file rule levels, multiple/supplemental policies, CiTool, managed installer, ISG, events, and the AppLocker comparison).
Related: `defender/asr-and-antivirus.md` (Attack Surface Reduction rules and Defender Antivirus core settings; a separate Defender AV control layer that runs alongside Smart App Control).

| Mode | Settings label | Registry value | `citool -lp` Friendly Name | Event ID |
|---|---|---|---|---|
| Evaluation | Evaluation | 2 | VerifiedAndReputableDesktopEvaluation | 3076 |
| Enforcement | On | 1 | VerifiedAndReputableDesktop | 3077 |
| Off | Off | 0 | not stated | not stated |

| Question | Answer | Source |
|---|---|---|
| Who decides the starting mode | Windows: evaluates the device, turns SAC on or off itself | S2198 |
| Managed-device default | Evaluation, then Off within 48 h unless user turned it on | S2200 |
| Settings can change mode from | Evaluation only | S2199 |
| Back on after Off | Clean install or reset (supported); offline registry (testing only) | S2198, S2199 |
| Central control of SAC state | Only the registry Off switch documented | S2200 |
| Central control of app trust | App Control for Business via Intune, Group Policy, script, ConfigMgr | S2201, S2204 |

## Examples
- SNIPPET: read Smart App Control's current mode from `citool.exe -lp`; context: Windows 11 22H2+, elevated prompt; checked: no [DOC S2199: `citool.exe -lp` Friendly Name `VerifiedAndReputableDesktopEvaluation`/`VerifiedAndReputableDesktop` with Is Currently Enforced indicates the mode]
```powershell
citool.exe -lp | Select-String 'VerifiedAndReputable|Currently Enforced'
```
- SNIPPET: turn Smart App Control off on a fleet member, as Microsoft documents it (this removes the protection); context: Windows 11 22H2+, elevated prompt, one-way change; checked: no [DOC S2200: same `VerifiedAndReputablePolicyState` registry value (0 = Off) under `HKLM\SYSTEM\CurrentControlSet\Control\CI\Policy`, applied with `CiTool.exe -r`]
```powershell
reg add "HKLM\SYSTEM\CurrentControlSet\Control\CI\Policy" /v VerifiedAndReputablePolicyState /t REG_DWORD /d 0 /f
citool.exe -r
```
