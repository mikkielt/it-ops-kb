---
topic: intune/assignment-filters-and-rbac
priority: P1
applies_to: "Microsoft Intune admin center, current channel (docs current 2026-09-26)"
retrieved_utc: 2026-09-26
sources: [S-4ls6gbe6, S-hddmxunx, S-ljhugmcx, S-bh6rnbtj, S-kv5b4jlr, S-lsavpnha, S-guis2g6u, S-gjnpib5p, S-cunjuxe3]
status: complete
---

# Assignment filters and Intune RBAC

## Summary
Assignment filters narrow which managed devices or managed apps receive a policy/app assignment, using a
rule syntax evaluated on top of an existing group assignment (include or exclude mode); they don't
replace groups. Intune RBAC controls who can do what: built-in or custom roles (permission
category + action) are assigned to admin groups together with scope groups (who is managed) and
optional scope tags (which objects are visible); scope tags are also stamped on individual objects.
Multi Admin Approval (MAA) adds a second-approver gate on top of RBAC for specific resource types,
including role changes themselves. Several Microsoft Entra roles (Global Administrator, Intune
Administrator/"Intune Service Administrator") carry Intune permissions independent of Intune RBAC.

## Facts

### Assignment filters
- Assignment filters apply to **managed devices** (enrolled in Intune) and **managed apps** (MAM,
  typically unenrolled personal devices); for managed apps they apply only to app protection and app
  configuration policies, not compliance or device configuration profiles. [DOC S-4ls6gbe6]
- Managed-device filter platforms: Android device administrator, Android Enterprise, Android (AOSP),
  iOS/iPadOS, macOS, Windows. Managed-app filter platforms: Android, iOS/iPadOS, Windows. [DOC S-4ls6gbe6]
- Limits: up to **200 assignment filters per tenant**; each filter's rule is limited to **3,072
  characters**. [DOC S-4ls6gbe6]
- A filter is evaluated at device enrollment, at check-in with the Intune service, or at any other time a
  policy evaluates — not just once. [DOC S-4ls6gbe6]
- Filters don't require group-membership processing, so policy targeting isn't affected by group size,
  rule complexity, or membership evaluation timing (unlike dynamic groups). Use filters for
  Intune-specific device targeting (OS, model, manufacturer, ownership, category); use dynamic groups for
  cross-workload targeting (Conditional Access, licensing, Autopilot profile assignment, user-based
  grouping). [DOC S-4ls6gbe6]
- A filter is applied to an assignment in one of two modes: **Include filtered devices** (only matching
  devices/apps receive the app/policy) or **Exclude filtered devices** (matching devices/apps are
  excluded); the third choice is **Do not apply a filter** (all targeted users/devices receive it). [DOC S-4ls6gbe6]
- Rule syntax form: `([entity].[property] [operator] [value])`, e.g.
  `(device.osVersion -eq "10.0.18362") and (device.manufacturer -eq "Microsoft")`; properties, operators
  and values are case-insensitive; parentheses and nested parentheses are supported, but some advanced
  syntax such as nested parentheses is available only in the **rule syntax editor**, and using it there
  disables the basic **rule builder**.
  [DOC S-hddmxunx]
- Supported operators (all value types unless noted): `-or`/`or`, `-and`/`and`, `-eq`/`eq`, `-ne`/`ne`,
  `-startsWith`/`startsWith` (string), `-in`/`in` (array), `-notIn`/`notIn` (array), `-contains`/`contains`
  (string), `-notContains`/`notContains` (string). `operatingSystemVersion` additionally supports
  `-gt`/`gt`, `-lt`/`lt`, `-ge`/`ge`, `-le`/`le`, but not `-startsWith`/`-contains`/`-in`. `Null`/`$Null`
  can be used as a value with `-eq`/`-ne`. [DOC S-hddmxunx]
- Full property list and per-property allowed operators/values: `intune/assignment-filter-properties.csv`.
  Notable items: `osVersion` is **deprecated** in favor of `operatingSystemVersion` (existing filters using
  it keep working; for managed-app filters you can no longer create new ones using it); `cpuArchitecture`
  is not yet evaluated during enrollment scenarios; `operatingSystemSKU` (Windows only) takes named SKU
  values (e.g. `Enterprise`, `EnterpriseN`, `ProfessionalWorkstation`) that the admin center itself
  doesn't display, only documented — get a device's numeric SKU via
  `Get-WmiObject -Class Win32_OperatingSystem | select operatingsystemSKU`. [DOC S-hddmxunx]
- Preview property: `app.deviceModel -startsWith "RealityDevice"`, supported only for the Microsoft Teams
  app on visionOS conditional-launch settings. [DOC S-hddmxunx]
- Filter preview (device list) is unavailable for a rule using an experimental/preview property (admin
  center shows "You cannot use Filter preview with experimental properties"), but the property can still
  be used in the filter itself. [DOC S-4ls6gbe6]
- Deleting a filter requires first removing it from every policy assignment that references it, else
  Intune returns `Unable to delete assignment filter – An assignment filter is associated with existing
  assignments. Delete all the assignments for the filter and try again.` [DOC S-4ls6gbe6]
- Graph resource: `deviceAndAppManagementAssignmentFilter` (beta), created with
  `POST /deviceManagement/assignmentFilters`; key properties `displayName`, `description`, `platform`
  (`windows10AndLater`, `iOS`, `macOS`, `androidWorkProfile`, `androidAOSP`, `windowsMobileApplicationManagement`,
  etc.), `rule` (string), `roleScopeTags`, `assignmentFilterManagementType` (`devices` default, or `apps`).
  Required permission (delegated or application): **`DeviceManagementConfiguration.ReadWrite.All`**.
  [DOC S-guis2g6u, S-gjnpib5p]

### Intune RBAC: roles, assignments, scope
- An Intune role = a set of permissions, each permission a management category (e.g. *Device
  configuration*, *Audit data*) plus sets of actions (e.g. *Read*, *Write*, *Update*, *Delete*). Built-in roles are identical across all tenants and
  can't have their description, type, or permissions edited. [DOC S-ljhugmcx]
- Built-in roles (fixed set, plus Cloud PC roles when Windows 365 is licensed):
  Application Manager, Endpoint Privilege Manager, Endpoint Privilege Reader, Endpoint Security Manager,
  Help Desk Operator, Intune Role Administrator, Policy and Profile Manager, Read Only Operator, School
  Administrator (Intune for Education), plus Cloud PC Administrator / Cloud PC Reader. Purpose and key
  permissions per role: `intune/rbac-built-in-roles.csv`. [DOC S-ljhugmcx, S-kv5b4jlr]
- **Intune Role Administrator** is the only Intune built-in role that can assign permissions to
  administrators (i.e. manage other role assignments); it's also the least-privileged built-in role
  sufficient to manage RBAC roles/assignments (`assign-role.md` states this explicitly, as an alternative
  to a custom role with Roles Assign/Create/Delete/Read/Update + Organization Read). [DOC S-lsavpnha, S-ljhugmcx]
- Custom roles can combine any Intune RBAC permission for finer-grained least privilege; see
  `create-custom-role` (out of scope here) for the full permission/action catalog. [DOC S-ljhugmcx]
- A role **assignment** = Members (admin groups whose users get the role's permissions) + Scope
  (Groups) (the users/devices those admins may manage — use specific groups, never *Add all users*/*Add
  all devices*, to keep scope tight) + Scope (Tags) (which objects, already tagged, those admins can see).
  Roles and role assignments are both assigned to **groups**, never individual users. [DOC S-ljhugmcx]
- Scope tags are free-text values added both to a role assignment (controls which *objects* the assigned
  admins can see) and to individual objects (policies, apps, devices); a scope tag on the role itself
  (not the assignment) controls visibility of the role. A **default scope tag** is auto-applied to every
  untagged object that supports scope tags. Maximum **100 scope tags per role assignment** and **100
  scope tags per object**. [DOC S-bh6rnbtj, S-ljhugmcx]
- If a role assignment carries no scope tag, that admin can see all objects their permissions otherwise
  allow — "admins that have no scope tags essentially have all scope tags." An admin can only apply a
  scope tag that's present in their own role assignment, and can only target groups already in their
  Scope (Groups). [DOC S-bh6rnbtj]
- Multiple role assignments for one admin: permissions in the same category merge (default behavior) —
  Read from one assignment + Read/Write from another on the same object type yields effective Read/Write
  provided both assignments' scope tags match the object. Create/Read/Update/Delete permissions and scope
  tags apply per object type across all the admin's assignments; permissions for one object type never
  grant access to another type. [DOC S-ljhugmcx]
- **Scoped permissions** (opt-in public preview, introduced March 2026): changes the default merge so each
  role assignment's permissions apply only within its own scope-tag context (no more accidental broadened
  access from merging across scope tags); it's enabled tenant-wide via **Tenant administration > Roles >
  Settings**, is **irreversible**, and should be previewed first with the **Permissions Assessment
  Report** (same Settings page) which lists exactly which security groups/resources would lose merged
  permissions. Enabling it requires a custom role with the **Update** action on **Organization**, or the
  Intune Administrator Entra role (no built-in Intune role includes Organization/Update). [DOC S-bh6rnbtj]
- Objects that don't currently support scope tags: Corp Device Identifiers, Windows Autopilot Devices,
  Device compliance locations, Jamf devices. [DOC S-bh6rnbtj]
- Not licensed with a required Intune permission but assigned an Intune role: unlicensed admin access has
  been supported since **June 2021** — accounts created after that date don't need an Intune license to
  administer Intune; accounts (or nested-group admins) created before that date still do. [DOC S-ljhugmcx]

### Entra roles that grant Intune access
- **Global Administrator**: full read/write access to Intune; Microsoft recommends never using it for
  routine Intune administration (a few features, like some Mobile Threat Defense connectors, require it).
  [DOC S-ljhugmcx]
- **Intune Administrator** (shown as **Intune Service Administrator** in Graph and PowerShell): a
  privileged Entra role granting global Intune read/write, narrower than Global Administrator but still
  broader than almost any day-to-day task needs; Microsoft recommends a least-privileged built-in or
  custom Intune role instead, with PIM (Entra ID P2/Governance) for time-bound elevation when Intune
  Administrator truly is required. [DOC S-ljhugmcx]
- Intune RBAC does **not** apply to Microsoft Entra roles — e.g. Intune Administrator has full admin
  access to Intune regardless of any scope tags. [DOC S-bh6rnbtj]
- Other Entra roles with partial Intune access: Conditional Access Administrator (none directly to Intune
  data), Security Administrator (read-only, full write on Endpoint Security node), Security
  Operator/Reader (read-only), Compliance Administrator/Compliance Data Administrator (audit data read
  only), Global Reader (read-only), Helpdesk Administrator (read-only; equivalent to Intune's Help Desk
  Operator role), Reports Reader (audit data read only). [DOC S-ljhugmcx]
- Two JIT elevation methods for the Intune Administrator role or an Intune RBAC role, with different
  latency: (1) Entra PIM on the built-in **Intune Administrator** role — elevation typically applies
  within **~10 seconds**; (2) PIM for Groups backing an Intune RBAC role assignment — typically takes up
  to **~15 minutes** to apply. [DOC S-ljhugmcx] (Compare the group-provisioning latency regimes in
  `auth/entra-intune-rbac.md`, which documents PIM-for-Groups write vs. SCIM-provisioning vs. token-cache
  latency in more depth for the general case.)

### Multi Admin Approval (MAA)
- MAA (access policies) requires a second, different administrator to approve a change to a protected
  resource type before Intune applies it; an admin can never approve their own request, including a
  Global Administrator or Intune Administrator's own request. [DOC S-cunjuxe3]
- Protected resource (profile) types: Apps (deployments only, not app protection policies), Compliance
  policies, Configuration policies (settings catalog), Device actions (wipe, retire, delete), Role-based
  access control (role permission/admin-group/member-group changes), Scripts (deploying scripts to Windows devices),
  Access Policies (MAA policies themselves — always protected, not selectable), Tenant Configuration
  (device categories). [DOC S-cunjuxe3]
- MAA enforcement covers both interactive (delegated) admin actions and **application-authenticated
  (app-auth) Microsoft Graph API calls** — service principals/automation/third-party apps hitting a
  protected resource are intercepted too, unless the specific enterprise application is explicitly
  excluded on that access policy (exclusions apply to app-auth calls only; delegated calls are always
  enforced regardless of exclusion). [DOC S-cunjuxe3]
- Three MAA participant roles: (1) **Access policy manager** — creates/manages MAA policies, via a custom
  role with Multi Admin Approval Create/Read/Update/Delete-access-policy permissions, or the Intune
  Administrator Entra role; (2) **Approver** — must be a direct member (not nested) of a **security
  group** (distribution lists, M365 groups, mail-enabled security groups silently fail to resolve) that is
  itself directly assigned as a member group on an Intune role assignment, and must hold the
  resource-specific **Read** permission for the policy type being approved (e.g. `ManagedDevices/Read` to
  approve a device delete); (3) **Change requestor** — needs the ordinary Intune RBAC permission for the
  action (e.g. `MobileApps/Create`, `RemoteTasks/Wipe`) and both submits the request and completes it
  after approval. [DOC S-cunjuxe3]
- Known deadlock: an access policy on the **Role** type protects all role/assignment changes, including
  the RBAC assignment MAA itself needs — if misconfigured, admins can become unable to fix RBAC without
  MAA approval they cannot obtain. Recovery: delete the Role access policy, wait 3–5 minutes for
  propagation, fix the RBAC assignment, then optionally recreate the Role access policy. Configure and
  verify all other MAA policies before enabling one for Role. [DOC S-cunjuxe3]
- Request states: Needs approval, Approved (processing), Completed, Rejected, Canceled; Intune sends no
  notifications on state changes — urgent requests need an out-of-band ping to an approver. Intune audit
  logs record MAA requests and approvals. [DOC S-cunjuxe3]

## Reference
| Scope object | Controls | Limit | Source |
|---|---|---|---|
| Assignment filter | which devices/apps an assignment reaches | 200/tenant, 3,072 chars/rule | S-4ls6gbe6 |
| Role assignment: Members | who gets the role's permissions | — | S-ljhugmcx |
| Role assignment: Scope (Groups) | which users/devices can be managed | — | S-ljhugmcx |
| Role assignment: Scope (Tags) | which tagged objects are visible | 100 tags/assignment | S-bh6rnbtj |
| Object scope tag | visibility of that one object | 100 tags/object | S-bh6rnbtj |

Full property/operator table: `intune/assignment-filter-properties.csv`. Full built-in role table:
`intune/rbac-built-in-roles.csv`.

See also: `intune/remote-actions.md` (the Graph `managedDevice` remote actions, several of which map to the
**Remote tasks** permission category in a custom role here, and the wipe action which Multi Admin Approval's
Device actions protected-resource type can gate), `intune/tenant-attach.md` (tenant-attach RBAC — ConfigMgr-attached devices get only the default
scope tag and can't be re-tagged; ConfigMgr RBAC is enforced alongside Intune RBAC unless **Enforce
Role-based Access Control** is unchecked), `agents/agent-rbac.md` (RBAC for AI-agent/service-principal
identities calling Graph — app-role-on-service-principal pattern applies equally to an automation account
calling the `deviceAndAppManagementAssignmentFilter` or Intune RBAC Graph endpoints), `auth/entra-intune-rbac.md`
(sync/PIM-for-Groups latency detail behind the ~15-minute PIM-for-Groups elevation figure above),
`intune/remote-help.md` (a dedicated Remote Help permission category — View screen, Take full control,
Elevation, Android/Windows unattended control — layered on top of the RBAC roles/scopes documented here).

## Examples
- SNIPPET: rule syntax combining two managed-device properties, saved on a filter named `Win-Corp-Enterprise`, then used in **Include filtered devices** mode on a compliance policy assignment; context: Intune assignment filter rule syntax editor; checked: no [DOC S-hddmxunx]
```
(device.deviceOwnership -eq "Corporate") and (device.operatingSystemSKU -in ["Enterprise","EnterpriseN"])
```

- SNIPPET: create the filter via Graph; context: Graph beta `deviceManagement/assignmentFilters`, needs `DeviceManagementConfiguration.ReadWrite.All`; checked: no [DOC S-guis2g6u]
```http
POST https://graph.microsoft.com/beta/deviceManagement/assignmentFilters
Content-Type: application/json

{
  "displayName": "Win-Corp-Enterprise",
  "platform": "windows10AndLater",
  "rule": "(device.deviceOwnership -eq \"Corporate\") and (device.operatingSystemSKU -in [\"Enterprise\",\"EnterpriseN\"])",
  "assignmentFilterManagementType": "devices"
}
```

RBAC scenario: engineer `jan.kowalski` is a member of the `SG-Seattle-ITAdmins` group, assigned the
**Policy and Profile Manager** role scoped to Scope (Groups) `SG-Seattle-Users` and Scope (Tags)
`Seattle`; `jan.kowalski` can edit configuration profiles tagged `Seattle` for devices in
`SG-Seattle-Users`, but not an unrelated profile tagged `Default` or devices outside that scope group. A
device wipe on `PL-LT-00123` submitted by a Help Desk Operator would additionally need MAA approval from a
different admin if the tenant has an access policy protecting **Device actions**.
