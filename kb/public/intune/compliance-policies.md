---
topic: intune/compliance-policies
priority: P2
applies_to: "Microsoft Intune device compliance policies, Windows 10 and later platform, docs retrieved 2026-09-26"
retrieved_utc: 2026-09-26
sources: [S-vpvd3h5f, S-u3qwumeu, S-qjd54t3z, S-yoeqntwt, S-4t5e7ocm, S-ogsl4hbo, S-wjex623z, S-ej25skuk, S-taatt73w, S-2hhj3k5f, S-o3fvldqn, S-sc3fvmp6, S-p7pe6fl3, S-5szcu5hb]
status: complete
---

# Intune compliance policies

## Summary
Intune compliance is split into tenant-wide **compliance policy settings** (a built-in policy every device receives) and per-platform **device compliance policies**. Compliance status validity period defaults to 30 days (range 1-120); devices with no assigned policy default to Compliant unless changed to Not compliant. Each policy always includes the built-in "Mark device noncompliant" action at 0 days; more actions (email, remote lock, retire, push notification) can be scheduled 0-365 days later. Windows compliance settings include Device Health Attestation (DHA) checks (BitLocker, Secure Boot, code integrity), device properties (OS version bounds), Configuration Manager compliance (co-managed only), System security (password, encryption, firewall, TPM, antivirus/antispyware, Defender), and Microsoft Defender for Endpoint machine risk score. Custom compliance settings let a PowerShell discovery script plus a JSON rule file extend built-in checks on Windows, macOS and Linux. The Graph `windows10CompliancePolicy` resource maps most Windows settings, but the beta version has many more properties (TPM, Defender, threat protection, VBS, firmware protection) than v1.0 — see Reference for the version discrepancy.

## Facts

### Compliance policy settings (tenant-wide)
- Compliance policy settings are configured at **Endpoint security > Device compliance > Compliance policy settings**, distinct from settings inside a device compliance policy. [DOC S-vpvd3h5f]
- "Mark devices with no compliance policy assigned as": **Compliant** (default; this security feature is off) or **Not compliant** (devices without an assigned compliance policy are treated as noncompliant). [DOC S-vpvd3h5f]
- "Compliance status validity period (days)": the period in which a device must successfully report on all its received compliance policies or be treated as noncompliant; default **30 days**, configurable range **1 to 120 days**. This setting shows as **Is active** in the Setting column under Devices > Monitor > Setting compliance. [DOC S-vpvd3h5f]

### Device compliance policies and evaluation
- A device compliance policy is a discrete set of platform-specific rules deployed to user or device groups; different platforms require separate policies. [DOC S-vpvd3h5f]
- Compliance policy settings can override device configuration policy settings on conflict; compliance policy settings always win, even if the configuration policy setting is more secure. [DOC S-vpvd3h5f, S-ej25skuk]
- If you deploy multiple compliance policies to a device, Intune uses the most secure of those policies. [DOC S-ej25skuk]
- For Windows devices, Intune also supports client-driven compliance evaluation (preview): supported devices can proactively request a re-evaluation when local state changes are detected. [DOC S-vpvd3h5f]
- Compliance evaluations depend on when the device checks in and on policy/profile refresh cycles. [DOC S-vpvd3h5f]
- Device compliance dashboard statuses: **Compliant** (met one or more policy settings), **In-grace period** (targeted but not yet compliant to all settings; still counted noncompliant), **Not evaluated** (initial state for new enrollments; also devices with no assigned policy and no trigger to check, devices not checked in since the policy last changed, devices without a specific user e.g. Apple DEP without affinity or Android Enterprise dedicated, or devices enrolled via a device enrollment manager account), **Not compliant** (failed one or more settings, or the user hasn't complied). [DOC S-ej25skuk]
- `managedDevice.complianceState` (Graph) possible values: `unknown`, `compliant`, `noncompliant`, `conflict`, `error`, `inGracePeriod`, `configManager`; default `unknown`. [DOC S-sc3fvmp6]
- When a compliance setting reports **Error**, the device's existing compliance state is held unchanged for up to **seven days** to allow re-evaluation; if the setting is still Error after 7 days, the device becomes Not compliant (or In grace period if a grace period is configured). [DOC S-ej25skuk]
- Checking a policy's Device status chart can take up to **24 hours** after the device is online before it appears, because the device must check in, process, and report back. [DOC S-ej25skuk]
- Company Portal enters an enrollment remediation flow when a user signs in and the device hasn't checked in for **30 days or more** (or is noncompliant due to Lost contact); Intune retries a check-in once, and if that fails, issues a retire command for manual re-enrollment. [DOC S-vpvd3h5f]

### Actions for noncompliance
- Every compliance policy includes the built-in default action **Mark device noncompliant**, scheduled at **0 days** (immediately); this schedule can be changed to grant a grace period, but the action itself can't be removed. [DOC S-u3qwumeu]
- Available actions for noncompliance: Mark device noncompliant (all platforms), Send email to end user (all platforms; sent from `microsoft-noreply@microsoft.com`, uses the profile email not UPN, expected within 6 hours of the device being marked noncompliant), Remotely lock the noncompliant device (Android DA, Android AOSP, Android Enterprise Fully Managed/Dedicated/COWP/POWP, iOS/iPadOS, macOS), Add device to retire list (same platforms plus Windows; device isn't retired until an admin explicitly confirms from the retire list), Send push notification to end user (Android DA, Android Enterprise Fully Managed/Dedicated/COWP/POWP, iOS/iPadOS; delivery isn't guaranteed and may be delayed hours). [DOC S-u3qwumeu]
- Send email / Remotely lock / Add device to retire list / Send push notification are not supported for devices managed by a third-party device compliance management partner. [DOC S-u3qwumeu]
- **Schedule (days after noncompliance)**: admin center accepts whole numbers and 0.25 increments (e.g. `0.25` = 6 hours, `0.5` = 12 hours); other decimals (e.g. `0.33` = 8 hours) require Microsoft Graph. Adding actions in the UI: schedule range is **0 to 365 days**. [DOC S-u3qwumeu]
- The same action can be added multiple times with different schedules (e.g. push notification at day 0 and again at day 3) to repeat while the device stays noncompliant; a single policy with duplicate push notifications scheduled for the same day sends only one notification that day, but separate policies with matching schedules each send their own. [DOC S-u3qwumeu]

### Windows Health Attestation Service (Device Health Attestation / DHA)
- Windows 10 devices (Intune commercial, US GCC High, DoD) use the Device Health Attestation (DHA) service to check boot-time state. [DOC S-qjd54t3z]
- **Require BitLocker**: Not configured (default) or Require; the setting is only measured at boot time, so a device that just finished BitLocker encryption needs a reboot before it's detected as compliant. Maps to Health Attestation CSP `BitLockerStatus`. [DOC S-qjd54t3z]
- **Require Secure Boot to be enabled on the device**: Not configured (default) or Require; supported on some TPM 1.2 and 2.0 devices — a device without TPM 2.0+ support shows Not Compliant. [DOC S-qjd54t3z]
- **Require code integrity**: Not configured (default) or Require; detects an unsigned driver/system file loaded into the kernel, or a system file altered by malware or an admin-privileged user. [DOC S-qjd54t3z]

### Device properties
- **Minimum OS version** / **Maximum OS version**: format `major.minor.build.revision` (from `ver` at a command prompt, e.g. `Microsoft Windows [Version 10.0.17134.1]`); below minimum reports noncompliant with an upgrade link, above maximum blocks resource access until the rule changes. [DOC S-qjd54t3z]
- **Minimum/Maximum OS required for mobile devices**: format `major.minor.build`. [DOC S-qjd54t3z]
- **Valid operating system builds**: a list of named min/max OS build ranges, each `major.minor.build.revision`, max field value **65535** per component; exportable as CSV. If a device's build falls outside all defined ranges, Company Portal's noncompliance message shows only the **first** range in the policy (a documented display limitation). [DOC S-qjd54t3z]

### Configuration Manager compliance (co-managed only)
- **Require device compliance from Configuration Manager**: Not configured (default, Intune skips ConfigMgr settings) or Require (all ConfigMgr configuration items must be compliant). Applies only to co-managed Windows devices; Intune-only devices return a "not available" status. [DOC S-qjd54t3z]

### System security: password, encryption, device security
- Password settings: Require a password to unlock (default Not configured), Simple passwords Block vs allow "1234"/"1111" (default allow), Password type Device default/Numeric/Alphanumeric (default Device default), Password complexity for Alphanumeric (digits+lowercase default; or +uppercase; or +uppercase+special), Minimum password length, Maximum minutes of inactivity before password required, Password expiration days (**1-730**), Number of previous passwords to block reuse, Require password when device returns from idle (Mobile/Holographic; default Not configured). [DOC S-qjd54t3z]
- **Encryption of data storage on a device**: Not configured (default) or Require; applies to all drives; maps to `DeviceStatus/Compliance/EncryptionCompliance` CSP; checks only for the presence of encryption (Intune supports the check via BitLocker) — for TPM-level validation use Require BitLocker instead, which needs a reboot to reflect compliance. [DOC S-qjd54t3z]
- **Firewall**: Not configured (default) or Require; maps to Firewall CSP; a device that syncs immediately after reboot/wake may show a transient Error; a conflicting Group Policy Object that allows all inbound traffic or disables the firewall overrides Intune and forces Not compliant even when Intune's own device configuration policy sets Firewall on. [DOC S-qjd54t3z]
- **Trusted Platform Module (TPM)**: Not configured (default, no TPM chip check) or Require (compliant if TPM chip version > 0; noncompliant with no TPM). Maps to `DeviceStatus/TPM/SpecificationVersion` CSP. [DOC S-qjd54t3z]
- **Antivirus** / **Antispyware**: Not configured (default) or Require; checks solutions registered with Windows Security Center (e.g. Symantec, Microsoft Defender); disabled or out-of-date software is noncompliant. Map to `DeviceStatus/Antivirus/Status` and `DeviceStatus/Antispyware/Status` CSPs. [DOC S-qjd54t3z]

### Defender and Microsoft Defender for Endpoint
- **Microsoft Defender Antimalware**: Not configured (default) or Require (turns the service on, blocks users from disabling it). [DOC S-qjd54t3z]
- **Microsoft Defender Antimalware minimum version**: a version string, e.g. `4.11.0.0`; blank (default) allows any version. [DOC S-qjd54t3z]
- **Microsoft Defender Antimalware security intelligence up-to-date**: Not configured (default) or Require; maps to `Defender/Health/SignatureOutOfDate` CSP. [DOC S-qjd54t3z]
- **Real-time protection**: Not configured (default) or Require; maps to `Policy CSP - Defender/AllowRealtimeMonitoring`. [DOC S-qjd54t3z]
- **Require the device to be at or under the machine risk score** (Microsoft Defender for Endpoint): Not configured (default), Clear (no threats allowed — most secure), Low (low-level threats tolerated), Medium (low/medium tolerated), High (all levels tolerated — least secure, useful for reporting-only). [DOC S-qjd54t3z]
- Surface Hubs running Windows Team OS don't support the Password or Microsoft Defender for Endpoint compliance categories; both must be left at their Not configured default on those devices. [DOC S-qjd54t3z]

### Compliance recalculation triggers (Windows)
- The Intune Management Extension (IME) periodically monitors compliance-related settings locally and compares them to a known baseline; a detected change triggers a device check-in, which triggers compliance re-evaluation. [DOC S-qjd54t3z]
- Real-time compliance monitoring watches these settings for immediate change detection and a proactive check-in request: Firewall, Antivirus, BitLocker, Microsoft Defender status, operating system build version, Real-time protection (RTP), Secure Boot. [DOC S-qjd54t3z]
- Intune throttles compliance-triggered reevaluations; if multiple changes occur in a short period, some updates may be processed in a later evaluation cycle. [DOC S-qjd54t3z]

### Custom compliance settings
- Custom compliance requires a discovery script (Windows: PowerShell; Linux: any language with an installed interpreter; macOS: Bash) plus a JSON rules file, both attached to the policy at creation. Each policy supports exactly one discovery script, and each script can discover multiple settings. [DOC S-4t5e7ocm, S-wjex623z]
- Windows custom compliance platform requirement: Windows, excluding Windows Home. [DOC S-4t5e7ocm]
- A discovery script assigned to a policy can't be deleted until it is unassigned from that policy; each discovery script can be used with only one compliance policy. [DOC S-wjex623z]
- When a Windows device receives a compliance policy with custom settings, it checks for the Intune Management Extension and installs it via MSI if missing; the IME then checks for new/updated PowerShell scripts every **8 hours**, runs discovery scripts every **8 hours**, and also runs them when a user selects Check Compliance — but a manual Check Compliance does not check for new/updated scripts. Push notifications can't trigger custom compliance on demand. [DOC S-4t5e7ocm]
- JSON rule fields: `SettingName` (case-sensitive), `Operator` (`IsEquals`, `NotEquals`, `GreaterThan`, `GreaterEquals`, `LessThan`, `LessEquals`), `DataType` (`Boolean`, `Int64`, `Double`, `String`, `DateTime`, `Version`), `Operand`, `MoreInfoURL`, `RemediationStrings` (at least one string for locale `en_US`; other locales optional). A policy can be up to **100 KB** and include up to **100 rules**. [DOC S-ogsl4hbo]
- Windows PowerShell discovery scripts must end with `return $hash | ConvertTo-Json -Compress` as the last line so results are returned as a single-line compressed JSON object. [DOC S-wjex623z]
- Discovery script limits: no larger than **1 MB** each; script output no larger than **1 MB**; run time limit **10 minutes** on Windows and macOS, **5 minutes** on Linux. [DOC S-wjex623z]
- Discovery script output is also limited to **2048 characters** per the create-policy article; output beyond this may be truncated into invalid JSON and raise error 65009. [DOC S-yoeqntwt]
- Custom compliance error codes: `65007` script returned failure, `65008` setting missing in the script result, `65009` invalid JSON for the discovered setting, `65010` invalid datatype for the discovered setting. [DOC S-4t5e7ocm]
- After a device fixes a custom-compliance issue, it can take up to **8 hours** for a subsequent sync to reflect the device as compliant again. [DOC S-4t5e7ocm]
- Users can manually trigger a re-check: Windows via the Company Portal website sync; Linux via Refresh in the Microsoft Intune app; macOS via Company Portal > Devices > Check Status. [DOC S-4t5e7ocm]
- Custom compliance settings can be used for Conditional Access decisions the same way as built-in settings, forming a compound rule set together. [DOC S-4t5e7ocm]

### Graph API
- `windows10CompliancePolicy` (v1.0) inherits from `deviceCompliancePolicy`; create with `POST /deviceManagement/deviceCompliancePolicies` and `@odata.type: "#microsoft.graph.windows10CompliancePolicy"`; permission (delegated work/school or application) `DeviceManagementConfiguration.ReadWrite.All`; not supported for personal Microsoft accounts. A successful create returns `201 Created`. [DOC S-o3fvldqn, S-taatt73w]
- `windows10CompliancePolicy` v1.0 properties: `passwordRequired`, `passwordBlockSimple`, `passwordRequiredToUnlockFromIdle`, `passwordMinutesOfInactivityBeforeLock`, `passwordExpirationDays`, `passwordMinimumLength`, `passwordMinimumCharacterSetCount`, `passwordRequiredType` (`deviceDefault`, `alphanumeric`, `numeric`), `passwordPreviousPasswordBlockCount`, `requireHealthyDeviceReport`, `osMinimumVersion`, `osMaximumVersion`, `mobileOsMinimumVersion`, `mobileOsMaximumVersion`, `earlyLaunchAntiMalwareDriverEnabled`, `bitLockerEnabled`, `secureBootEnabled`, `codeIntegrityEnabled`, `storageRequireEncryption`. [DOC S-taatt73w]
- `scheduledActionsForRule` (`deviceComplianceScheduledActionForRule` collection) is a required property when creating any per-platform compliance policy via Graph. [DOC S-taatt73w]
- `managedDevice.complianceGracePeriodExpirationDateTime` reports the DateTime when a device's compliance grace period expires. [DOC S-sc3fvmp6]

## Reference
- Co-management: `intune/co-management.md` covers the Compliance policies co-management workload and the ConfigMgr-side `SMS_Client_ComanagementState` fields; this article's "Require device compliance from Configuration Manager" setting is the Intune-side counterpart for co-managed devices. See `intune/co-management.md` Reference for the back-link.
- Graph API version discrepancy: the v1.0 `windows10CompliancePolicy` resource lists only 19 settable properties (password rules, DHA booleans `bitLockerEnabled`/`secureBootEnabled`/`codeIntegrityEnabled`/`earlyLaunchAntiMalwareDriverEnabled`, OS version bounds, `storageRequireEncryption`) [DOC S-taatt73w]; the beta resource adds `tpmRequired`, `activeFirewallRequired`, `defenderEnabled`, `defenderVersion`, `signatureOutOfDate`, `rtpEnabled`, `antivirusRequired`, `antiSpywareRequired`, `deviceThreatProtectionEnabled`, `deviceThreatProtectionRequiredSecurityLevel`, `configurationManagerComplianceRequired`, `validOperatingSystemBuildRanges`, `memoryIntegrityEnabled`, `kernelDmaProtectionEnabled`, `virtualizationBasedSecurityEnabled`, `firmwareProtectionEnabled`, `deviceCompliancePolicyScript`, `wslDistributions`, `roleScopeTagIds` [DOC S-2hhj3k5f] — the two Learn pages describe materially different object shapes for the same resource name; automate against beta if a v1.0-only integration needs Firewall/Antivirus/Defender/TPM/threat-protection settings. Logged in `_conflicts.md`.
- `intune/win32-apps.md` documents the separate Win32 app return-code and supersedence model; do not conflate with compliance policy status codes above.
- `entra/conditional-access-devices.md`: the "Require device to be marked as compliant" grant control reads the `complianceState`/`isCompliant` this article's evaluation logic produces; see that article for the Conditional Access grant, Filter for devices, report-only and What If detail.
- `defender/asr-and-antivirus.md`: this article's beta `windows10CompliancePolicy` `defenderEnabled`/`rtpEnabled`/`antivirusRequired` System security checks read the same Defender Antivirus state (`AMRunningMode`, cloud protection) that article documents in depth, including ASR rules layered on top of Defender AV.
- `intune/reports-export-api.md`: the `DeviceCompliance`, `DeviceNonCompliance`, `DevicesWithoutCompliancePolicy` and `PolicyNonComplianceAgg` Graph `exportJobs` report names bulk-export this article's per-device compliance evaluation states via the create/poll/download pattern; see that article for the request/response shape, permissions and throttling.
- `intune/ios-android-management.md`: defines the Android DA/Enterprise Fully Managed/Dedicated/COWP/POWP and iOS/iPadOS ownership-model names used above in the noncompliance-actions platform list; see that article's Reference for the back-link.
- `intune/linux-management.md`: the Linux counterpart to this article's compliance mechanism — Linux compliance policies are built from the settings catalog (Allowed Distributions, Device Encryption via dm-crypt/LUKS, Password Policy) rather than a predetermined template, and Linux custom compliance uses a POSIX-compliant/any-interpreter discovery script (5-minute run limit, runs in user context) instead of PowerShell, sharing the same `65007`-`65010` custom compliance error codes documented above.

## Examples
- SNIPPET: create a Windows compliance policy via Graph requiring BitLocker, Secure Boot and a minimum OS version, for tenant `00000000-0000-0000-0000-000000000000` (placeholders only); context: Graph v1.0 `deviceCompliancePolicies`, `windows10CompliancePolicy`; checked: no [DOC S-taatt73w; DER S-p7pe6fl3, S-5szcu5hb: `scheduledActionsForRule`/`scheduledActionConfigurations` shape and `actionType`/`gracePeriodHours`/`notificationTemplateId` fields from the `deviceComplianceScheduledActionForRule` and `deviceComplianceActionItem` resource pages]
```http
POST https://graph.microsoft.com/v1.0/deviceManagement/deviceCompliancePolicies
Content-Type: application/json

{
  "@odata.type": "#microsoft.graph.windows10CompliancePolicy",
  "displayName": "Contoso - Windows baseline compliance",
  "passwordRequired": true,
  "passwordMinimumLength": 8,
  "bitLockerEnabled": true,
  "secureBootEnabled": true,
  "codeIntegrityEnabled": true,
  "osMinimumVersion": "10.0.19045.0",
  "scheduledActionsForRule": [
    {
      "ruleName": "PasswordRequired",
      "scheduledActionConfigurations": [
        { "actionType": "block", "gracePeriodHours": 0, "notificationTemplateId": "" }
      ]
    }
  ]
}
```

- SNIPPET: Windows discovery script fragment (device `PL-LT-00123`) returning a compressed JSON hash for a custom compliance JSON rule on `TPMChipPresent`; context: Windows custom compliance discovery script, must end with `return $hash | ConvertTo-Json -Compress`; checked: no [DOC S-wjex623z]
```powershell
$TPM = Get-Tpm
$hash = @{ TPMChipPresent = $TPM.TpmPresent }
return $hash | ConvertTo-Json -Compress
```

- SNIPPET: matching custom compliance JSON rules file (`en_US` remediation string required); context: custom compliance JSON, up to 100 KB / 100 rules; checked: syntax [DOC S-ogsl4hbo]
```json
{
  "Rules": [
    {
      "SettingName": "TPMChipPresent",
      "Operator": "IsEquals",
      "DataType": "Boolean",
      "Operand": true,
      "MoreInfoUrl": "https://corp.example.com/help/tpm",
      "RemediationStrings": [
        { "Language": "en_US", "Title": "TPM chip is missing or disabled", "Description": "Enable the TPM chip in firmware, then re-run compliance check." }
      ]
    }
  ]
}
```
