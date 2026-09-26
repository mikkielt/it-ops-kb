---
topic: entra/conditional-access-devices
priority: P1
applies_to: "Microsoft Entra Conditional Access, device-based grant controls and Filter for devices condition, Microsoft Graph v1.0 conditionalAccessPolicy (docs retrieved 2026-09-26)"
retrieved_utc: 2026-09-26
sources: [S-2gcjipq5, S-tkmjbvgn, S-bpayn5ic, S-isovad24, S-frxelebk, S-r7wru3uo, S-evafm3dr, S-hk7ngup4, S-ovycuo7g, S-lsnr7k3y, S504, S-ac6jmj3f, S-qu7z6wlo, S-nuh4ep7w]
status: complete
files: [entra/ca-device-filter-properties.csv]
---

# Conditional Access for devices

## Summary
- Two independent device mechanisms in a Conditional Access policy: a **grant control** ("Require device to be marked as compliant", "Require Microsoft Entra hybrid joined device") decides pass/fail for the whole policy, while the **Filter for devices condition** narrows *which* devices the policy (any grant) applies to, using a rule expression over device properties. [DOC S-tkmjbvgn, S-2gcjipq5]
- "Require device to be marked as compliant" reads Intune's (or a supported non-Microsoft MDM's) compliance verdict; "Require Microsoft Entra hybrid joined device" reads `trustType`; both require the device to be registered in Entra ID first. [DOC S-tkmjbvgn]
- Device state (deprecated) has been replaced by Filter for devices, which can express the same and more via `trustType` and `isCompliant`; the two conditions can't be combined in one policy. [DOC S-r7wru3uo]
- New: Conditional Access **for agents** — agent user sessions get only a restricted grant set (Block access, or Grant + Require device to be marked as compliant), and agent identities (non-interactive) support only Block access; licensed via Entra ID P1/P2 plus a Microsoft Agent 365 license per user (enforcement "coming soon" as of retrieval). Cross-link `entra/agent-id.md`. [DOC S-tkmjbvgn, S-ovycuo7g]

## Facts

### Grant controls
- Grant control options: Require multifactor authentication, Require authentication strength, Require device to be marked as compliant (Intune), Require Microsoft Entra hybrid joined device, Require approved client app, Require app protection policy, Require password change, Require terms of use; combine with "require all" (AND, default) or "require one" (OR). [DOC S-tkmjbvgn]
- "Require device to be marked as compliant" supports Windows 10+, iOS, Android, macOS and Linux Ubuntu devices registered in Entra ID and enrolled in Intune (or reporting compliance via a supported non-Microsoft MDM, Windows only); Microsoft Edge InPrivate mode on Windows is always treated as noncompliant. [DOC S-tkmjbvgn]
- The control doesn't block Intune enrollment itself: a device can still enroll even when "Require device to be marked as compliant" is scoped to All users / All resources. [DOC S-bpayn5ic]
- Policies requiring a compliant device can prompt macOS/iOS/Android users to pick a device certificate during evaluation even though compliance isn't enforced yet (report-only) or not the deciding factor; these prompts can repeat until the device becomes compliant — exclude those platforms from report-only compliance-check policies to avoid the prompts. [DOC S-isovad24, S-2gcjipq5]
- Block access is a separate, powerful control (deny outright) and combines with Filter for devices to scope which devices are blocked; block-statement policies need careful testing (report-only/What If) before enabling. [DOC S-tkmjbvgn]

### Filter for devices condition
- The Filter for devices condition targets or excludes specific devices via a rule expression over device properties, authored with the rule builder or the same rule syntax used for dynamic-membership group rules; it is an optional condition alongside user/sign-in-risk/locations/client apps/device platforms. [DOC S-2gcjipq5]
- Maximum filter rule length: **3,072 characters**. [DOC S-2gcjipq5]
- For a device unregistered in Entra ID, all device properties evaluate as null (the device doesn't exist in the directory); Microsoft recommends targeting unregistered devices with a **negative** operator (a positive operator only ever matches an existing, attribute-matching device). [DOC S-2gcjipq5]
- Full supported property/operator/example table: `entra/ca-device-filter-properties.csv` (16 rows: deviceId, displayName, deviceOwnership, trustType, isCompliant, manufacturer, model, operatingSystem, operatingSystemVersion, physicalIds, profileType, systemLabels, enrollmentProfileName, mdmAppId, extensionAttribute1-15). [DOC S-2gcjipq5]
- `Contains`/`NotContains` behave differently by attribute type: for string attributes (`operatingSystem`, `model`) it's substring match; for string-collection attributes (`physicalIds`, `systemLabels`) it matches one whole string in the collection. [DOC S-2gcjipq5]
- `extensionAttribute1-15` values are only populated at policy-evaluation time if the device is Intune managed, compliant, or Entra hybrid joined. [DOC S-2gcjipq5]
- For agents' user accounts, the Filter for devices condition applies only when the agent session is initiated from an endpoint; combine with the "Agent execution environments" condition to target specific approved devices for agents. [DOC S-r7wru3uo]
- `trustType` values match the Graph `device.trustType` enum used elsewhere in the kb: `AzureAD`/`AzureAd` = Entra joined, `ServerAD`/`ServerAd` = Entra hybrid joined, `Workplace` = Entra registered — same three states as `entra/device-identity.md`. [DER S-2gcjipq5, S504]

### Report-only mode and What If
- Report-only is a policy enablement state (alongside On/Off) that evaluates a policy during sign-in and logs the outcome without enforcing grant or session controls; users are never prompted (no MFA challenge, no ToU). [DOC S-isovad24]
- Per-sign-in report-only evaluation results: **Report-only: Success**, **Report-only: Failure** (conditions met but a required grant/session control wasn't satisfied, e.g. device failed the compliance check), **Report-only: User action required** (grant/session control would need user interaction, e.g. MFA, not prompted), **Report-only: Not applied** (policy conditions not met, e.g. user excluded). [DOC S-isovad24]
- Report-only results surface in the sign-in log's **Report-only** tab; the Conditional Access insights and reporting workbook needs Entra ID P1 plus an Azure Monitor Log Analytics workspace receiving streamed sign-in logs. [DOC S-isovad24]
- Recommended rollout: build the new/changed policy in report-only alongside existing enforced policies, compare in the Insights workbook, then flip Report-only -> On. [DOC S-isovad24]
- The **What If tool** (backed by the Graph `conditionalAccessRoot: evaluate` What If Evaluation API) simulates a sign-in for a user, agent identity, or single-tenant service principal against configured conditions (apps, user actions/authentication context, sign-in conditions) and reports which enabled or report-only policies would apply; it does not evaluate Conditional Access service dependencies (e.g. a Teams policy result ignores an Exchange Online dependency policy). Only enabled or report-only policies are included in an evaluation run. [DOC S-frxelebk]

### Licensing and permissions
- Conditional Access (device-based grant controls and Filter for devices included) requires Microsoft Entra ID P1; Microsoft 365 Business Premium licenses also grant access to Conditional Access features; risk-based conditions (sign-in/user risk) additionally require Entra ID P2 (Identity Protection). [DOC S-ovycuo7g]
- Conditional Access for agents requires Entra ID P1 or P2 **and** a Microsoft Agent 365 license per user (or Microsoft 365 E7, which bundles Agent 365 and the Entra Suite); enforcement of the Agent 365 licensing requirement is described as "coming soon" at retrieval. [DOC S-ovycuo7g, S-tkmjbvgn]
- When Conditional Access licenses expire, existing policies are neither auto-disabled nor deleted (a graceful degrade); admins can still view/delete them but not update them. [DOC S-ovycuo7g]
- Graph `conditionalAccessPolicy` create/update least-privileged permission: **Policy.Read.All + Policy.ReadWrite.ConditionalAccess** (delegated or application; personal Microsoft accounts not supported); a higher-privileged alternative is Application.Read.All + Policy.ReadWrite.ConditionalAccess. Built-in Entra roles that satisfy delegated calls: Security Administrator, Conditional Access Administrator. A documented known issue means this call may prompt for consent to additional permissions. [DOC S-evafm3dr]
- `POST /identity/conditionalAccess/policies` requires the request body to include at least one of: an `application` rule (e.g. `includeApplications: 'none'`), a `user` rule (e.g. `includeUsers: 'none'`), or a grant/session control. [DOC S-evafm3dr]

### Device signals in sign-in logs and workload identities
- Graph `signIn.deviceDetail` (populated for Entra-registered devices): `deviceId`, `displayName`, `browser`, `operatingSystem`, `isCompliant` (bool), `isManaged` (bool), `trustType` (string: workplace-joined / Entra-joined / domain-joined wording). [DOC S-hk7ngup4]
- The sign-in log's Device info tab surfaces whether the device is compliant, managed, or Entra hybrid joined, alongside browser/OS; PowerShell `Get-EntraAuditSignInLog -Filter "deviceDetail/isCompliant eq false"` lists sign-ins from noncompliant devices (needs Global Reader/Reports Reader/Security Administrator/Security Operator/Security Reader). [DOC S-hk7ngup4]
- Conditional Access for workload identities targets service principals (not users): assignment is by "Select service principals" under Workload identities, the only Grant option is **Block access** (no compliant-device or hybrid-join grant exists for workload identities), and the only usable condition is service principal risk (requires Identity Protection); report-only mode is supported the same way as user policies. [DOC S-lsnr7k3y]
- CA policies scoped to users don't block calls made by service principals/service accounts; Microsoft recommends excluding service accounts (and the Entra Connect Sync account) from user-targeted policies and, where device or compliance-style control over non-interactive callers is needed, use Conditional Access for workload identities or managed identities instead. [DOC S-tkmjbvgn]

## Reference
| Mechanism | What it does | Grant/condition | Applies to | Source |
|---|---|---|---|---|
| Require device to be marked as compliant | Grant control: pass/fail on Intune (or partner MDM) compliance | Grant | Users, agent user sessions (restricted) | S-tkmjbvgn |
| Require Microsoft Entra hybrid joined device | Grant control: pass/fail on `trustType=ServerAD/ServerAd` | Grant | Users | S-tkmjbvgn |
| Filter for devices | Condition: include/exclude specific devices by rule expression over device properties | Condition | Users, agent user sessions from an endpoint | S-2gcjipq5, S-r7wru3uo |
| Device state | Deprecated; replaced by Filter for devices (`trustType`, `isCompliant`); can't combine with Filter for devices | Condition (deprecated) | n/a | S-r7wru3uo |
| Report-only | Evaluates and logs without enforcing | Policy state | All (except most User Actions scope) | S-isovad24 |
| What If tool / evaluate API | Simulates a sign-in against configured/report-only policies | Diagnostic | User, agent identity, single-tenant SP | S-frxelebk |

- `intune/compliance-policies.md`: the compliance-state machine (`complianceState` values, grace period, evaluation timing) that "Require device to be marked as compliant" reads — see that article's Reference for the back-link.
- `entra/device-identity.md`: the three join types and `trustType` values that both "Require Microsoft Entra hybrid joined device" and the Filter for devices `trustType`/`profileType` properties key off — see that article's Reference for the back-link.
- `auth/token-lifetimes-cae.md`: Continuous Access Evaluation revocation timing is a separate mechanism from device-based grant controls; a CAE critical event (e.g. `revokeSignInSessions`) does not itself re-run a device compliance check, it revokes tokens on CAE-aware resources.
- `auth/msal-public-client.md`: Token Protection (a Conditional Access session control, not covered in this article) binds tokens to a registered device for native-app clients; the client-type/WAM-integration boundary discussed there is orthogonal to the grant controls and filters documented here.
- `entra/agent-id.md`: Conditional Access for agents (agent user sessions vs. agent identities, licensing via Microsoft Agent 365, `howto-target-agent-identities`) builds directly on the grant/condition restrictions in this article's Summary.
- `intune/remote-help.md`: Remote Help is one of the few features that lets a Conditional Access policy gate helper/sharer sign-in directly — but only for attended sessions on Windows and macOS, never for unattended control.
- `intune/app-protection-mam.md`: the "Require app protection policy" grant control (MAM path for unmanaged/BYOD devices, including Windows Edge MAM) that combines with this article's device-based grant controls — typically OR'd with "Require device to be marked as compliant" so either an app-protected unmanaged device or a compliant managed device can pass.

## Examples
Create a report-only Conditional Access policy requiring a compliant device for a placeholder line-of-business app, excluding a break-glass account, for tenant `00000000-0000-0000-0000-000000000000` (least-privileged permission `Policy.Read.All` + `Policy.ReadWrite.ConditionalAccess`):
```http
POST https://graph.microsoft.com/v1.0/identity/conditionalAccess/policies
Content-Type: application/json

{
  "displayName": "CA-LOB01 - Require compliant device (report-only)",
  "state": "enabledForReportingButNotEnforced",
  "conditions": {
    "users": {
      "includeUsers": ["All"],
      "excludeUsers": ["00000000-0000-0000-0000-000000000011"]
    },
    "applications": {
      "includeApplications": ["00000000-0000-0000-0000-000000000012"]
    },
    "clientAppTypes": ["all"]
  },
  "grantControls": {
    "operator": "OR",
    "builtInControls": ["compliantDevice"]
  }
}
```
- `00000000-0000-0000-0000-000000000011` is a placeholder object id for a break-glass/emergency-access account; `00000000-0000-0000-0000-000000000012` is a placeholder app registration id for the target line-of-business app.
- A Filter for devices exclusion could be added under `conditions.devices` with a rule such as `device.extensionAttribute1 -eq "SAW"` to exempt privileged-access workstations, per the create-policy walkthrough. [DOC S-2gcjipq5]
- Flip to enforced once report-only results (sign-in log **Report-only** tab, or the Insights workbook) look correct: `PATCH .../policies/{id}` with `"state": "enabled"`. [DOC S-evafm3dr, S-isovad24]

## Additional facts
- `conditions.devices` is a `conditionalAccessDevices` object with one property, `deviceFilter` (type `conditionalAccessFilter`): `{"deviceFilter": {"@odata.type": "microsoft.graph.conditionalAccessFilter"}}`. `conditionalAccessFilter` has `mode` (`include`/`exclude`) and `rule` (a dynamic-group-membership-rule-style string, e.g. `device.deviceOwnership -eq "Company"`): `{"mode": "String", "rule": "String"}`. [DOC S-ac6jmj3f, S-qu7z6wlo]
- Full `builtInControls` enum (on `conditionalAccessGrantControls`): `block`, `mfa`, `compliantDevice`, `domainJoinedDevice`, `approvedApplication`, `compliantApplication`, `passwordChange`, `riskRemediation` (added January 2026, requires the `Prefer: include-unknown-enum-members` header), `unknownFutureValue`; `operator` is `AND`/`OR`; `passwordChange` must pair with `mfa` via `AND`, and `riskRemediation` must pair with `authenticationStrength` via `AND` and target `all` applications with only `users`/`applications`/`userRiskLevels` conditions. [DOC S-nuh4ep7w]
- Token Protection's device-binding mechanics are intentionally not repeated here; see `auth/msal-public-client.md`. [DOC S-tkmjbvgn]
