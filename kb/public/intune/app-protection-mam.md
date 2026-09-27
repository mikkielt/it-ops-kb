---
topic: intune/app-protection-mam
priority: P2
applies_to: "Microsoft Intune app protection policies (APP/MAM) for iOS/iPadOS, Android and Windows; Microsoft Graph v1.0 managedAppPolicies (docs retrieved 2026-09-26)"
retrieved_utc: 2026-09-27
sources: [S-ngcvmu22, S-msbbtbup, S-qing6dzr, S-qjixnw4g, S-t4g3ekea, S-5cbvuypc, S-jgesqj52, S-eaeb5jdz, S-lu7ablj2, S-36mghzxu, S-27fiskhq, S-5fxhm5mr, S-qj62oq2o, S-xsnx4hlp, S-b3l5wbk6, S-p3vtkyrq, S-ssexz2ef, S-ehjdk3sn, S-gqqrls57, S-2jxyk3ra, S-j6tphfq3, S-x44btgzh]
status: complete
---

# App protection policies (Intune MAM)

## Summary
- Intune **app protection policies (APP)**, i.e. Mobile Application Management (MAM), protect organizational data inside an app independently of any MDM enrollment: they work on devices enrolled in Intune, devices enrolled in a non-Microsoft MDM, and devices not enrolled anywhere. The iOS/iPadOS settings page groups them into **Data relocation**, **Access requirements** and **Conditional launch**; Windows uses **Data protection** and **Health Checks**. [DOC S-qjixnw4g, S-eaeb5jdz]
- The **data protection framework** groups recommended settings into three levels — Enterprise basic (L1: PIN + encryption + selective wipe), Enterprise enhanced (L2: adds data-leakage prevention and min OS version — the level Microsoft recommends for most users), Enterprise high (L3: adds Mobile Threat Defense and stronger PIN rules) — each building on the previous. [DOC S-t4g3ekea, S-qjixnw4g]
- To be enforced, app protection should be paired with **Conditional Access** ("Require app protection policy" grant control; for Windows see the policy below): Microsoft says to use Conditional Access together with app protection policies to ensure the policies are enforced. [DOC S-qjixnw4g, S-36mghzxu]
- **Windows MAM ("MAM without enrollment" for Windows)** extends the same model to Windows 10/11 personal devices via Microsoft Edge and the Windows Security app: Application Configuration Policies customize the experience, app protection policies secure data and check device health, Windows Security app integrates as an MTD source, and a Conditional Access policy (grant: **Require app protection policy**, optionally OR'd with **Require device to be marked as compliant**) gates access. [DOC S-lu7ablj2, S-36mghzxu]
- **MAM without device enrollment** (MAM-WE) uses **app configuration policies** to deliver settings to unenrolled apps and **app protection policies** to protect their data; it needs no device enrollment, is commonly used for personal/BYOD devices, and is available on Android, iOS/iPadOS and Windows. [DOC S-qj62oq2o]

## Facts

### Platforms, licensing and requirements
- App protection policy platform support tracks Office mobile app platform support for iOS/iPadOS and Android; separate Windows-specific app protection policies exist for Windows devices. [DOC S-qjixnw4g]
- Company Portal is required on the device to receive app protection policies on **Android** (even when the device is not enrolled). [DOC S-qjixnw4g]
- A user needs a Microsoft Entra account, an assigned Intune license, and membership in a security group targeted by an app protection policy that also targets the app in use; the user must sign in with that Entra account. [DOC S-qjixnw4g]
- Windows app protection policy (Edge) requires Windows 11, or Windows 10 20H2+ with KB5031445. [DOC S-36mghzxu]
- Windows Home edition is supported for MAM for Windows. [UNK: not in S-b3l5wbk6 as re-read 2026-09-27]
- Windows MAM cross-tenant Edge support (clipboard, protected downloads, watermarking) requires Microsoft Edge for Business version 147+ and Entra ID P1 or P2 for Conditional Access; same-tenant managed devices are **not** supported in that cross-tenant configuration. [DOC S-ehjdk3sn]
- Any app integrating the **Intune App SDK**, or wrapped with the **Intune App Wrapping Tool**, can be managed by app protection policies; for wrapped line-of-business apps **all** app data counts as "corporate" (vs. only Exchange/OneDrive-for-work data for Microsoft 365 apps). [DOC S-qjixnw4g]
- BYOD devices with app protection but no MDM enrollment cannot receive app deployment via Intune, certificate profiles, or company Wi-Fi/VPN profiles — those still require enrollment. [DOC S-qjixnw4g]

### Conditional Access + app protection (Windows)
- Grant control **Require app protection policy** (Windows, Conditional Access) targets the Office 365 apps cloud app group, condition **device platform = Windows**, **client apps = Browser** only; combine with **Require device to be marked as compliant** using **"Require one of the selected controls"** (OR), because a device can only ever satisfy one of the two paths (MAM on unmanaged, or MDM-compliant on managed). [DOC S-36mghzxu]
- Using **"Require all the selected controls"**, or **Require app protection policy** alone without scoping to unmanaged devices, blocks access on already-MDM-managed devices: the policy can't assess app-protection compliance for a device it can't apply MAM to. [DOC S-36mghzxu]
- If a device is already MDM-managed, Intune MAM enrollment for that app is blocked and app protection settings don't apply; conversely, if a device becomes MDM-managed *after* MAM enrollment, app protection settings stop applying. [DOC S-36mghzxu]
- Recommended rollout: start the Windows app-protection Conditional Access policy in **Report-only**, verify via policy impact/report-only results, then switch to **On**; also exclude break-glass and service accounts, per the standard Conditional Access guidance. [DOC S-36mghzxu]
- First sign-in flow: user is prompted to switch/add the Edge profile with the work account; selecting **Yes** ("remember my account… sign in to all apps") enrolls the browser profile in MAM; selecting **No, sign in to the app only** blocks MAM enrollment; if an MDM-enrollment prompt appears, selecting **No** keeps it MAM-only (Yes would MDM-enroll the device instead). [DOC S-36mghzxu]
- Windows Edge sign-in/sync can also be blocked outright on unmanaged/noncompliant Windows, iOS and Android via a Conditional Access policy targeting the Edge app with MAM settings — this block is **not supported on iOS**. [UNK: not in S-ehjdk3sn as re-read 2026-09-27]
- Cross-tenant Windows MAM known limitations: if device-level **Endpoint DLP** is enabled, Intune App Protection (MAM) policies can't apply to the Edge work profile (profile switching breaks) unless a policy bypasses this; from Edge 149+, when both a **Microsoft Defender for Cloud Apps DLP** policy and an app protection (MAM) policy would apply to the same tenant, the MDCA DLP policy takes precedence over the MAM app protection policy (Conditional Access itself still applies). [DOC S-ehjdk3sn]

### Data protection settings (iOS/Android)
- **Allowed data transfer**: `allowedInboundDataTransferSources` / `allowedOutboundDataTransferDestinations` accept `allApps`, `managedApps`, `none` — controls which apps managed data may come from / go to. [DOC S-27fiskhq]
- **Clipboard**: `allowedOutboundClipboardSharingLevel` accepts `allApps`, `managedAppsWithPasteIn`, `managedApps`, `blocked`. [DOC S-27fiskhq]
- **Managed browser**: `managedBrowserToOpenLinksRequired` (bool) forces web links from managed apps to open in a managed browser; `managedBrowser` selects which one — `notConfigured` or `microsoftEdge` — and admins can require all links from Intune-managed apps to open in Microsoft Edge. [DOC S-27fiskhq, S-qjixnw4g]
- Other data-protection toggles: `saveAsBlocked`, `dataBackupBlocked`, `printBlocked`, `contactSyncBlocked`, `organizationalCredentialsRequired`. [DOC S-27fiskhq]

### Access requirements (data protection framework, L1/L2 baseline)
- PIN for access: **Require**, numeric, simple PIN **allowed**, minimum length **4**; biometric (Touch ID/Face ID) allowed instead of PIN; **Override biometrics with PIN after timeout = Require**, timeout **1440 minutes**. [DOC S-t4g3ekea]
- **App PIN when device PIN is set = Require** in the framework; for Intune-enrolled devices, admins can consider "Not required" when a device compliance policy enforces a strong device PIN. [DOC S-t4g3ekea]
- **Work or school account credentials for access = Not required**; **recheck access requirements after 30 minutes of inactivity**. [DOC S-t4g3ekea]

### Conditional launch (health checks)
- **Offline grace period — Block access**: default **1440 minutes (24 hours)**; going below ~30 minutes is not recommended (causes frequent re-auth interruptions); after the app requires network + Entra re-authentication. [DOC S-jgesqj52]
- **Offline grace period — Wipe data**: default **90 days**; after that many days offline the app requires network re-authentication: success resets the offline interval, failure makes the app **selectively wipe** the user's account and data. [DOC S-jgesqj52]
- **Max PIN attempts**: default **5**; on failure the configured action is **Reset PIN** (with MFA re-auth) or **Wipe data**. [DOC S-jgesqj52]
- **Require device lock** (Android): Low/Medium/High complexity; on Android 11 and earlier, any complexity value behaves as Low; actions: Warn, Block access, Wipe data. [DOC S-jgesqj52]
- **Min Company Portal version** (Android): format `Major.Minor[.Build[.Revision]]`; actions Block access / Wipe data / Warn; support for Android Company Portal versions before **5.0.5421.0** ended **October 1, 2025**. [DOC S-jgesqj52]
- iOS/iPadOS app protection settings are documented in three categories: **Data relocation**, **Access requirements**, **Conditional launch**. [DOC S-eaeb5jdz]
- For some conditional launch settings several **Actions** can be configured, e.g. Block access and Wipe data at different values; they are set in an editable Setting/Value/Action table under **Apps > Protection > Create policy > Configure required settings > Conditional launch**. [DOC S-5cbvuypc]

### Selective wipe
- **Selective (MAM) wipe** removes only org app data, distinct from full MDM device wipe and MDM "retire" selective wipe (which need MDM enrollment); MAM wipe applies on iOS/iPadOS, Android and Windows, requires the app to include the Intune App SDK and a licensed org account, and requires an app protection policy to be deployed to enable selective wipe on Android/iOS. [DOC S-xsnx4hlp, S-ssexz2ef]
- Wipe requests can be created **per device** (Apps > App selective wipe > Create wipe request) or **per user** (User-Level Wipe — issues wipe to all the user's devices/apps at every check-in until removed). [DOC S-xsnx4hlp]
- Timing: if the app is in use when wipe is initiated, the Intune App SDK polls for the wipe request **every 30 minutes**; it also checks on first launch/sign-in; the wipe can take up to 30 minutes after the request. [DOC S-xsnx4hlp, S-ssexz2ef]
- Completed wipe-request entries stay in the report for **4 days**; a pending (never-completed) request stays for **(configured "Wipe data" offline grace period in days) + 4 days** — 94 days total with the 90-day default. [DOC S-xsnx4hlp]
- On iOS 16+, the device name shown for all selective-wipe actions/status is a generic placeholder (Apple platform limitation), not the real device name. [DOC S-xsnx4hlp]
- Outlook-synced contacts pushed from the app to the native address book are removed on selective wipe; contacts synced onward from the native address book to another external source cannot be wiped. [DOC S-xsnx4hlp]

### App configuration policies
- **App configuration policies** deliver a set of custom key/value settings as-is to all users in the targeted security group; Graph object `targetedManagedAppConfiguration` (inherits `managedAppConfiguration`/`managedAppPolicy`) carries `customSettings` (string key/value pairs) plus `apps`, `assignments`, `deploymentSummary`. [DOC S-5fxhm5mr]
- A Managed apps app configuration policy uses the MAM channel, so apps built with the Intune App SDK (or wrapped) receive it whatever the device enrollment state; on Windows the only supported app is Microsoft Edge (settings catalog); values may use Intune tokens such as `{{userprincipalname}}`, `{{mail}}`, `{{partialupn}}`, `{{accountid}}`, `{{userid}}`, `{{username}}` and `{{PrimarySMTPAddress}}`; app protection and MAM-channel app configuration on Android need Android 10.0 or later. [DOC S-qing6dzr]
- `POST /deviceAppManagement/targetedManagedAppConfigurations` (Graph v1.0) creates one; least-privileged permission (delegated or application) is **DeviceManagementApps.ReadWrite.All**; not supported for personal Microsoft accounts. [DOC S-ngcvmu22]
- The Intune App SDK exposes a separate app-configuration delivery mechanism from Android Enterprise managed configurations; apps must read admin-configured values through the SDK, and this works on devices without Android Enterprise management. [DOC S-msbbtbup]

### Graph: targetedManagedAppProtection
- `targetedManagedAppProtection` (Graph v1.0, inherits `managedAppProtection`) is the policy object for detailed management settings targeted to specific security groups. Key properties beyond those in Data protection/Conditional launch above: `version`, `periodOfflineBeforeAccessCheck`, `periodOnlineBeforeAccessCheck`, `minimumRequiredOsVersion`, `minimumWarningOsVersion`, `minimumRequiredAppVersion`, `minimumWarningAppVersion`, `isAssigned`. [DOC S-27fiskhq]
- `maximumPinRetries` valid range: **1 to 65535**. [DOC S-27fiskhq]
- Relationship `assignments` (`targetedManagedAppPolicyAssignment` collection) lists the inclusion/exclusion groups the policy is deployed to; a `targetApps` action and an `assign` action are available on the resource. [DOC S-27fiskhq]

### Diagnostics
- **Microsoft Edge mobile diagnostics**: typing `about:intunehelp` or `edge://intunehelp/` in Edge for iOS/Android opens troubleshooting mode; **View Intune App Status** lists the apps and, per app, the APP settings currently active on the device; if only the app version/bundle and policy check-in timestamp show, no policy is applied to that app. [DOC S-b3l5wbk6, S-p3vtkyrq]
- The same screen's **Get Started** option collects logs about the APP-enabled apps, to attach to a Microsoft support case; Edge diagnostic-log saving respects the app protection policy, so diagnostic data can't be saved to the local device. [DOC S-b3l5wbk6, S-p3vtkyrq]
- Troubleshooting checklist for app protection deployment: the policy must be assigned to user groups (not device groups) that contain the user; the app must be in the Intune protected apps list (LOB apps on the latest Intune App SDK); the user must sign in to the app with the targeted corporate account (policies apply only in the work context); Android users need the latest Company Portal, which acts as the policy broker. [DOC S-b3l5wbk6]
- The iOS/iPadOS share extension can open work data in unmanaged apps even when data transfer is restricted, because app protection can't control it without device management; Intune encrypts "corporate" data before it leaves the app instead. [DOC S-qjixnw4g]
- Confirm Microsoft Authenticator is present when app-based Conditional Access is enabled. [UNK: not in S-b3l5wbk6 as re-read 2026-09-27]

## Reference
| Mechanism | Delivers | Applies to | Enrollment needed | Source |
|---|---|---|---|---|
| App protection policy (APP/MAM) | Data protection, access requirements, conditional launch | iOS/iPadOS, Android, Windows (Edge) | No | S-qjixnw4g |
| App configuration policy (managed apps) | Custom key/value settings to managed apps | iOS/iPadOS, Android, Windows (Edge only) | No | S-qing6dzr, S-5fxhm5mr |
| Conditional Access — Require app protection policy | Grant control gating sign-in on MAM enrollment | Office 365 apps / Windows browser client, iOS/Android apps | No (paired with unmanaged/BYOD) | S-36mghzxu |
| Conditional Access — Require device to be marked as compliant | Grant control gating sign-in on MDM compliance | Enrolled devices | Yes | see `entra/conditional-access-devices.md` |
| Selective (MAM) wipe | Removes org app data only | iOS/iPadOS, Android, Windows apps with Intune App SDK | No | S-xsnx4hlp |

- `entra/conditional-access-devices.md`: the Filter for devices condition and the device-based grant controls (compliant device, hybrid join) that combine with "Require app protection policy" in a Conditional Access policy — see that article's Reference for the back-link to this one.
- `intune/compliance-policies.md`: MDM device compliance, the alternative (device-based) grant control path for managed devices, contrasted here with the MAM/APP path for unmanaged devices.
- `intune/win32-apps.md`: app deployment to enrolled/managed devices; app protection policies apply independently of app deployment and do not themselves push apps to unenrolled devices.
- `intune/ios-android-management.md`: the iOS/iPadOS and Android enrollment/ownership models (Apple User Enrollment, Android Enterprise personally owned work profile, etc.) that app protection policies commonly pair with for BYOD/MAM-without-enrollment scenarios; see that article's Reference for the back-link.

## Examples
- SNIPPET: create an iOS app protection policy (Level 2 "Enterprise enhanced" baseline settings) via Graph; context: Graph v1.0 `iosManagedAppProtections`, needs `DeviceManagementApps.ReadWrite.All`; checked: no [DER S-27fiskhq, S-t4g3ekea, S-jgesqj52: properties from the `targetedManagedAppProtection` resource page, values from the data protection framework and Android conditional-launch defaults]
```http
POST https://graph.microsoft.com/v1.0/deviceAppManagement/iosManagedAppProtections
Content-Type: application/json

{
  "displayName": "APP-iOS-L2 - Enterprise enhanced data protection",
  "pinRequired": true,
  "minimumPinLength": 4,
  "periodOnlineBeforeAccessCheck": "PT30M",
  "periodOfflineBeforeWipeIsEnforced": "P90D",
  "allowedInboundDataTransferSources": "managedApps",
  "allowedOutboundDataTransferDestinations": "managedApps",
  "managedBrowserToOpenLinksRequired": true,
  "managedBrowser": "microsoftEdge"
}
```
- SNIPPET: assign that policy to a placeholder group via the generic managed-app-policy assign action; context: Graph v1.0 `managedAppPolicies/{id}/assign`, needs `DeviceManagementApps.ReadWrite.All`; checked: no [DOC S-x44btgzh]
```http
POST https://graph.microsoft.com/v1.0/deviceAppManagement/managedAppPolicies/{managedAppPolicyId}/assign
Content-Type: application/json

{
  "assignments": [
    {
      "target": {
        "@odata.type": "#microsoft.graph.groupAssignmentTarget",
        "groupId": "00000000-0000-0000-0000-000000000011"
      }
    }
  ]
}
```
- `00000000-0000-0000-0000-000000000011` is a placeholder Entra group object id. `PT30M` / `P90D` are ISO 8601 durations for the 30-minute recheck after inactivity (`periodOnlineBeforeAccessCheck`) and the 90-day offline wipe grace period (`periodOfflineBeforeWipeIsEnforced`). The assign body uses the documented `assignments`/`target` shape; the assign action itself is on `managedAppPolicies/{id}`, not on the type-specific collection. [DER S-t4g3ekea, S-jgesqj52: framework values expressed as the Graph `Duration` properties documented in S-27fiskhq]
- SNIPPET: create a targeted app configuration policy pushing a single custom key to Outlook; context: Graph v1.0 `targetedManagedAppConfigurations`, needs `DeviceManagementApps.ReadWrite.All`; checked: no [DOC S-ngcvmu22]
```http
POST https://graph.microsoft.com/v1.0/deviceAppManagement/targetedManagedAppConfigurations
Content-Type: application/json

{
  "displayName": "ACP-Outlook-OrganizationId",
  "customSettings": [
    { "name": "com.microsoft.outlook.OrganizationId", "value": "00000000-0000-0000-0000-000000000000" }
  ]
}
```
- `00000000-0000-0000-0000-000000000000` is a placeholder tenant id used as the pushed setting value.

## Open items
- Windows app protection is `windowsInformationProtectionPolicy` (v1.0, "WIP without MDM enrollment") or `mdmWindowsInformationProtectionPolicy` (the MDM-enrolled counterpart, sharing most inherited properties). Key properties inherited from the base `windowsInformationProtection` type: `enforcementLevel` (`noProtection`/`encryptAndAuditOnly`/`encryptAuditAndPrompt`/`encryptAuditAndBlock`), `enterpriseDomain`, `enterpriseProtectedDomainNames`/`enterpriseNetworkDomainNames`/`enterpriseIPRanges`/`enterpriseProxiedDomains` (protected-boundary definitions), `protectedApps`/`exemptApps` (and their AppLocker-XML relationship equivalents), `revokeOnUnenrollDisabled`, and `rightsManagementServicesTemplateId`/`azureRightsManagementServicesAllowed`. [DOC S-2jxyk3ra, S-j6tphfq3]
- Declared on `windowsInformationProtectionPolicy` itself (not inherited from the base type, and absent from `mdmWindowsInformationProtectionPolicy`): `windowsHelloForBusinessBlocked`, `pinMinimumLength` (default 4, 0-127), the PIN character and expiry settings, `numberOfPastPinsRemembered` (0-50), `passwordMaximumAttemptCount` (4-16 desktop / 0-999 mobile), `minutesOfInactivityBeforeDeviceLock` (0-999), `daysWithoutContactBeforeUnenroll` (0-999), `revokeOnMdmHandoffDisabled` and `mdmEnrollmentUrl`. CRUD is List/Get/Create/Update/Delete on `windowsInformationProtectionPolicy` (v1.0). [DOC S-2jxyk3ra, S-j6tphfq3]
- `androidManagedAppProtection` (beta; List/Get/Create/Update/Delete plus `hasPayloadLinks`) extends `targetedManagedAppProtection`/`managedAppProtection` with Android-specific properties: `screenCaptureBlocked`, `disableAppEncryptionIfDeviceEncryptionIsEnabled`, `encryptAppData`, `minimumRequiredPatchVersion`/`minimumWarningPatchVersion`/`minimumWipePatchVersion` (Android security patch level), `exemptedAppPackages`, `allowedAndroidDeviceManufacturers`, `requiredAndroidSafetyNetDeviceAttestationType` (`none`/`basicIntegrity`/`basicIntegrityAndDeviceCertification`), `requiredAndroidSafetyNetAppsVerificationType` (`none`/`enabled`), `appActionIfAndroidSafetyNetDeviceAttestationFailed`/`...AppsVerificationFailed`/`...DeviceManufacturerNotAllowed` (`block`/`wipe`/`warn`), `customBrowserPackageId`/`customBrowserDisplayName`, and `minimumRequired/WarningCompanyPortalVersion`/`minimumWipeCompanyPortalVersion`. It inherits the common `managedAppProtection` fields (pin policy, clipboard/data-transfer restrictions, offline-wipe period, OS/app version gating) shared with iOS's `iosManagedAppProtection`. [DOC S-gqqrls57]
