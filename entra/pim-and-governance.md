---
topic: entra/pim-and-governance
priority: P2
applies_to: "Microsoft Entra Privileged Identity Management (PIM) for Entra roles and Azure resource roles, Entitlement Management access packages, Access reviews (docs current 2026-09-26)"
retrieved_utc: 2026-09-26
sources: [S-h6zdsnii, S-jpsjsa5i, S-5hprvqbx, S-aioepkro, S-xnr7ugsj, S-upv53vkh, S-kzv67wmw, S-bcq2wujf, S-byjcvmyn, S-6psxvqdi, S-a2iaeb54, S-2ooklp7p, S-ay5o5ism, S-efsglmmy, S-tksnvnpk]
status: partial
---

# PIM for Entra roles, access packages, and access reviews

## Summary
- PIM separates **eligible** assignments (must be activated to use) from **active** assignments (usable immediately, no action needed); activation is always time-bound, up to a per-role maximum of 8 hours by default. [DOC S-xnr7ugsj]
- Per-role PIM policies (role settings, called "rules" in Graph) control activation maximum duration (1-24 hours), MFA/Conditional Access authentication context/justification/ticket/approval requirements on activation, and separate rules for active-assignment creation. [DOC S-5hprvqbx]
- Graph manages eligibility via `unifiedRoleEligibilityScheduleRequest` (admins assign, update, remove, extend or renew eligible roles) and active assignments via `unifiedRoleAssignmentScheduleRequest`; to activate an eligible role, the eligibility resource page points to creating a `unifiedRoleAssignmentScheduleRequest` (action `selfActivate`). [DOC S-upv53vkh, S-kzv67wmw, S-bcq2wujf]
- PIM for Entra roles/Azure resources/Entra ID Governance access reviews all require Microsoft Entra ID P2 or Microsoft Entra ID Governance (or Microsoft Entra Suite) licensing; entitlement management's core capability also needs P2/Governance, with several capabilities (agent identities, SAP IAG, Entra role access packages) gated to Governance/Suite/Agent 365 only. [DOC S-ay5o5ism]
- This article does not repeat PIM for Groups' cloud/on-prem AD sync latency (covered in `auth/entra-intune-rbac.md`) or AD's native TTL group membership (PAM optional feature, covered in `auth/ad-jit-membership.md`); it covers Entra-role/Azure-resource PIM activation policy, alerts, and Entitlement Management/access reviews as the surrounding ID Governance layer.

## Facts
- **Eligible vs active**: an eligible assignment requires the principal to activate it (self-service or with approval) before use; an active assignment grants the role immediately with no activation step. Both can be permanent or time-bound (start/end dates). [DOC S-xnr7ugsj, S-h6zdsnii]
- Role activation is always time-bound, for a maximum of 8 hours by default; the per-role policy can lower this maximum but not raise it above 24 hours. [DOC S-xnr7ugsj, S-5hprvqbx]
- **Activation maximum duration** (role setting) accepts 1-24 hours. [DOC S-5hprvqbx]
- Per-role PIM policies can require, independently for eligible-role **activation**: MFA, a Conditional Access authentication context, justification text, ticket information (free-text, not validated against any ticketing system), and approval by one or more named approvers (recommended: at least two; if none configured, active Privileged Role Administrators/Global Administrators become default approvers). [DOC S-5hprvqbx]
- Separately, **active assignment creation** (an admin directly assigning a role as active, not eligible) can require MFA and/or justification on the admin performing the assignment — PIM cannot enforce MFA at the moment the user *uses* an already-active role, only when the assignment is created. [DOC S-5hprvqbx]
- Conditional Access authentication context on activation: when a user reauthenticates to satisfy it, a 10-minute grace window applies tenant-wide across Entra roles, Azure resource roles, and PIM for Groups activations — a second activation within that window does not re-prompt. If no CA policy targets the configured authentication context, PIM falls back to requiring MFA as backup protection (not triggered if the CA policy is disabled, report-only, or the user is excluded from it). [DOC S-5hprvqbx]
- Assignment duration settings are configured per assignment type: eligible assignments can be "Allow permanent eligible assignment" or "Expire eligible assignment after" (fixed start/end); active assignments have the same permanent-or-expiring choice independently. [DOC S-5hprvqbx]
- Managing role settings/policies via Graph uses `unifiedRoleManagementPolicy` (the container, one per role) and `unifiedRoleManagementPolicyAssignment`; individual rules (MFA required, max duration, approval required, etc.) are read/updated through these resources — Graph calls role settings "rules." Listing the policies requires a `$filter` on scopeId and scopeType: for Entra roles scopeId `/` with scopeType `Directory` or `DirectoryRole`, e.g. `GET /policies/roleManagementPolicies?$filter=scopeId eq '/' and scopeType eq 'DirectoryRole'&$expand=rules`. [DOC S-xnr7ugsj, S-efsglmmy]
- `unifiedRoleEligibilityScheduleRequest.action` values listed on the resource page: `adminAssign`, `adminUpdate`, `adminRemove`, `selfActivate`, `selfDeactivate`, `adminExtend`, `adminRenew`, `selfExtend`, `selfRenew`, `unknownFutureValue`; even so, the page says to activate an eligible role assignment with the Create `unifiedRoleAssignmentScheduleRequest` API (`action: selfActivate`). [DOC S-upv53vkh, S-bcq2wujf]
- `POST /roleManagement/directory/roleAssignmentScheduleRequests` with `action: selfActivate`, `principalId` (the caller's own id), `roleDefinitionId`, a `scheduleInfo` duration (e.g. 5 hours), and justification/ticket info if the role's policy requires it, self-activates an eligible role; the caller must have MFA already enforced/challenged in the current session to call this API for themselves. [DOC S-bcq2wujf, S-byjcvmyn]
- `POST /roleManagement/directory/roleEligibilityScheduleRequests` creates or manages an eligibility itself (e.g. `adminAssign` to grant eligibility); request body fields: `principalId` (required), `roleDefinitionId` (required), `scheduleInfo` (the eligibility period; optional only for `adminRemove`), `justification` (optional/required depending on the role's linked policy; optional for `selfDeactivate`/`adminRemove`), `ticketInfo` (same conditionality), `isValidationOnly` (dry-run check without submitting). [DOC S-kzv67wmw]
- To discover which eligible roles a signed-in user can activate: `GET /roleManagement/directory/roleEligibilityScheduleRequests/filterByCurrentUser(on='principal')`; this does **not** return eligibility a user holds only via group membership. [DOC S-jpsjsa5i]
- On Entra role activation, PIM adds the active assignment within seconds, and removes it within seconds on deactivation or expiry; whether an application reflects the change depends on its own caching of the user's roles, and signing out and in again can help. [DOC S-jpsjsa5i]
- **PIM for Groups and role-assignable groups**: a role-assignable group cannot have another group actively nested inside it (active membership); a group *can* be an **eligible** member of another group, even if one is role-assignable — activating eligibility in the outer group only elevates the individual activating user, not the whole inner group. [DOC S-6psxvqdi]
- To give a group of users just-in-time access to a role that reaches SharePoint, Exchange, or Microsoft Purview portal permissions (e.g. Exchange Administrator), make the users' membership in the group **active** and assign the **group** to the role as eligible-for-activation — the reverse pattern (active group-to-role assignment, eligible user-to-group membership) can cause significant delay before all of the role's downstream permissions are actually usable. [DOC S-6psxvqdi]
- **PIM security alerts** (Entra roles) — only Global Administrator, Privileged Role Administrator, Global Reader, Security Administrator, and Security Reader can read them: "Administrators aren't using their privileged roles" (low; configurable day threshold 0-100 without activation), "Roles don't require MFA for activation" (low), "Organization doesn't have Entra ID P2/Governance" (low), "Potential stale accounts in a privileged role" (medium; configurable 1-365 days without sign-in — no longer based on last password change date), "Roles are being assigned outside of PIM" (high), "Too many Global Administrators" (low; configurable minimum count 2-100 AND minimum percentage 0-100%, both thresholds must be met), "Roles are being activated too frequently" (low; configurable renewal timeframe and activation count 2-100 within it). [DOC S-aioepkro]
- Notification emails: a single PIM event can fan out to at most 1000 recipients; if more than 1000 would be notified, only the first 1000 receive the email (does not block anyone's actual permissions). [DOC S-5hprvqbx, S-aioepkro]
- **Licensing for PIM**: requires Microsoft Entra ID P2 or Microsoft Entra ID Governance (or Microsoft Entra Suite, which includes Governance) for every user with an eligible/time-bound PIM assignment (Entra/Azure roles or PIM for Groups member/owner), every approver, and everyone assigned to or performing an access review. [DOC S-ay5o5ism]
- If the P2/Governance license lapses or a trial ends: permanent active assignments are unaffected; active **time-bound** assignments become permanent active (stop expiring); all eligible role assignments are removed outright (users can no longer activate); any in-progress access reviews of Entra roles end and their PIM configuration is removed; PIM stops sending assignment-change and alert emails; the Entra admin center PIM UI, Graph API, and PowerShell interfaces for activating/managing PIM become unavailable. [DOC S-ay5o5ism]
- **Entitlement Management** (access packages) requires Microsoft Entra ID Governance or Microsoft Entra Suite for the organization's users; some of its capabilities can run with Microsoft Entra ID P2. [DOC S-a2iaeb54]
- In the licensing table, entitlement-management capabilities marked for Governance/Suite but not P2 include Entra roles as resources (preview), SAP IAG business roles (preview), eligible PIM-for-Groups ownership/membership as a resource, custom-extension (Logic Apps) approval logic and custom extensions, auto-assignment policies, Verified ID integration, and ID Protection and Purview Insider Risk Management integration; API permissions in access packages are marked for Microsoft Agent 365 only. [DOC S-ay5o5ism]
- Access packages can hold membership of security groups and Microsoft 365 groups/Teams, enterprise application assignments, SharePoint Online site membership, and in preview API permissions for agents/service principals and SAP IAG business roles; Entra roles can be governed by putting role-assignable groups in an access package. [DOC S-a2iaeb54]
- Automatic assignment policies assign an access package from a membership rule over user attributes (supported properties plus extension attributes); a policy can include at most 15,000 identities in its rule, and the feature needs Microsoft Entra ID Governance or Microsoft Entra Suite licenses. [DOC S-tksnvnpk]
- Access reviews of access packages can be scheduled periodically to catch stale assignments; enabling them requires Microsoft Entra ID Governance or Microsoft Entra Suite. [DOC S-2ooklp7p]
- Licensing is counted per in-scope user, not per license assigned to that specific feature: e.g. an access review of a 500-member group with 3 owners as reviewers needs 503 Governance/P2 licenses (500 reviewed users + 3 reviewer owners); a self-review of the same group needs only 500 (reviewers are the reviewed users themselves). [DOC S-ay5o5ism]
- Agent identity governance (service-principal/agent access via Entitlement Management, agent sponsorship in Lifecycle Workflows) requires either Microsoft 365 E7 (bundles Agent 365 + Entra Suite) or a Microsoft Agent 365 license paired with at least Entra ID P1 or Microsoft 365 E3 — this is a separate prerequisite track from the P2/Governance track used for PIM and standard entitlement management. [DOC S-ay5o5ism]
- Managing PIM role settings in the portal requires at least the Privileged Role Administrator role; settings are defined per role, and all assignments of that role share the same policy. [DOC S-5hprvqbx]
- A tenant lockout risk is explicitly called out: if every Privileged Role Administrator/Global Administrator only has an *eligible* (not active) assignment, activation for that role requires approval, and no specific approvers are configured, no one can approve the first activation — mitigated by configuring emergency access (break-glass) accounts and always naming specific approvers. [DOC S-5hprvqbx]

## Reference
- `auth/audit-log-apis.md` — retrieving PIM's role-activation/approval trail programmatically: it lands in
  Entra `directoryAudits`, retrievable via the Graph Purview Audit Search API or exported via diagnostic settings.

| Resource / setting | Value | Tag |
|---|---|---|
| Default/max activation duration | 8 hours default, configurable 1-24h | DOC S-xnr7ugsj, S-5hprvqbx |
| CA auth-context reauth grace window | 10 minutes, shared across Entra roles / Azure resource roles / PIM for Groups | DOC S-5hprvqbx |
| Max notification recipients per PIM event | 1000 (extras silently not emailed) | DOC S-5hprvqbx |
| Graph: self-activate eligible role | `POST roleManagement/directory/roleAssignmentScheduleRequests`, `action: selfActivate` | DOC S-bcq2wujf |
| Graph: grant/manage eligibility | `POST roleManagement/directory/roleEligibilityScheduleRequests`, `action: adminAssign` etc. | DOC S-kzv67wmw |
| Graph: list my activatable eligible roles | `GET roleManagement/directory/roleEligibilityScheduleRequests/filterByCurrentUser(on='principal')` (excludes group-inherited eligibility) | DOC S-jpsjsa5i |
| Graph: role policy container | `unifiedRoleManagementPolicy` / `unifiedRoleManagementPolicyAssignment`, `GET policies/roleManagementPolicies?$filter=scopeId eq '/' and scopeType eq 'DirectoryRole'&$expand=rules` | DOC S-xnr7ugsj, S-efsglmmy |
| PIM licensing | Entra ID P2, Entra ID Governance, or Entra Suite | DOC S-ay5o5ism |
| Access-package review of access packages | Requires Governance/Suite specifically | DOC S-2ooklp7p |
| Agent identity governance | Microsoft 365 E7, or Agent 365 + (Entra P1 / M365 E3) | DOC S-ay5o5ism |
| Alert: too many Global Admins | needs BOTH min count (2-100) AND min percentage (0-100%) breached | DOC S-aioepkro |
| Alert: stale privileged account | configurable 1-365 days without sign-in | DOC S-aioepkro |
| PIM for Groups + role-assignable group nesting | active nesting not allowed; eligible nesting allowed (activation elevates only the activating user) | DOC S-6psxvqdi |
| License expiry effect on PIM | active time-bound -> permanent active; eligible -> removed; ongoing role access reviews end | DOC S-ay5o5ism |

## Examples
- SNIPPET: self-activate an eligible Entra role via Graph (placeholders); context: Graph v1.0, `action: selfActivate`, caller must already have MFA enforced/challenged in the session; checked: no [DOC S-bcq2wujf, S-byjcvmyn]
```http
POST https://graph.microsoft.com/v1.0/roleManagement/directory/roleAssignmentScheduleRequests
Content-Type: application/json
Authorization: Bearer {token}

{
  "action": "selfActivate",
  "principalId": "00000000-0000-0000-0000-000000000000",
  "roleDefinitionId": "88d8e3e3-8f55-4a1e-953a-9b9898b8876b",
  "directoryScopeId": "/",
  "justification": "Incident CONTOSO-INC-00042: rotating a compromised service credential",
  "scheduleInfo": {
    "startDateTime": "2026-09-26T09:00:00Z",
    "expiration": { "type": "afterDuration", "duration": "PT5H" }
  },
  "ticketInfo": { "ticketNumber": "CONTOSO-INC-00042", "ticketSystem": "ServiceNow" }
}
```
- User `jan.kowalski` first finds what he can activate (excludes anything he only holds via group eligibility): `GET https://graph.microsoft.com/v1.0/roleManagement/directory/roleEligibilityScheduleRequests/filterByCurrentUser(on='principal')`, then submits the `selfActivate` request above with the returned `roleDefinitionId`.
- Grant a new eligible assignment as an admin (`adminAssign`) to `PL-LT-00123`'s owner for 180 days: `POST roleManagement/directory/roleEligibilityScheduleRequests` with `action: adminAssign`, `principalId`, `roleDefinitionId`, and `scheduleInfo.expiration` set to `afterDateTime` 180 days out.

See also: `auth/entra-intune-rbac.md` (PIM for Groups' effect on group membership propagation timing to on-prem AD, ~20 min Cloud Sync writeback, and token-caching latency after activation — assumed here, not repeated); `auth/ad-jit-membership.md` (the on-prem AD-native equivalent: PAM optional feature TTL group membership, independent of Entra PIM); `auth/enterprise-access-model.md` (tiering/control-plane context for a PIM-eligible role like Global Administrator or Privileged Role Administrator); `entra/agent-id.md` (agent identity governance via Entitlement Management/Agent 365 licensing, referenced above).

## Open items
- Exact end-to-end timing for an Entra-role PIM activation to be reflected in a fresh Graph token is not stated: S-jpsjsa5i gives only "within seconds" for the directory-level active assignment and warns that application caching can delay the effect. [UNK: lab check if exact SLA matters]
