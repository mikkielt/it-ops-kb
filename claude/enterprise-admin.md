---
topic: claude/enterprise-admin
priority: P2
applies_to: "Claude Code docs and Anthropic help center (retrieved 2026-09-26)"
retrieved_utc: 2026-09-26
sources: [S-gxtvjkv7, S-hoagpet2, S-xsggrooz, S-fqe5wkdo, S-2ym4fr2c, S-dkaaodgp]
status: complete
---

# Claude Team/Enterprise administration: SSO, SCIM, roles, domain capture, audit

## Summary
Claude for Teams and Claude for Enterprise administration runs through the claude.ai admin console (Organization
settings), separate from the file/MDM-based managed-settings policy that `claude/settings-and-scopes.md` covers.
SSO is SAML-only per the setup guide (Okta, Entra ID, Google, OneLogin, JumpCloud, Duo), gated by domain
verification (DNS TXT record); provisioning is JIT or SCIM. Four built-in roles (Primary Owner, Owner, Admin,
User/Member) cover billing, membership and security; Enterprise adds custom roles. Enterprise-only domain capture
force-migrates every personal account on a verified domain into the org, one-way, with a 30-day window. Usage
analytics live in the claude.ai dashboard and the Enterprise Analytics API; org-wide activity/audit events are a
separate Enterprise-only Compliance API that explicitly excludes model inference content. Data retention and ZDR
scope are covered in `claude/data-retention.md` (not repeated here).

## Facts
### SSO and domain verification
- SSO is available for Team plans, Enterprise plans, and Console organizations; the setup guide documents SAML only (no OIDC), with named IdP guides for Okta, Entra ID (formerly Azure AD), Google, OneLogin, JumpCloud, and Duo. [DOC S-hoagpet2]
- Domain verification (a prerequisite for SSO) is done by adding the domain in organization settings and creating a DNS TXT record whose value begins `anthropic-domain-verification-`; verification typically completes within about 10 minutes of DNS propagation. [DOC S-hoagpet2]
- All domains inside one organization must use a single IdP; IdP-initiated login is unsupported for a Console org sharing SSO with a Team/Enterprise plan. [DOC S-hoagpet2]
- Setup order: review prerequisites, verify domain(s), configure SSO with the IdP, toggle "Require SSO" to enforce it, then choose a provisioning approach (invite-only, JIT, or SCIM). [DOC S-hoagpet2]
- SCIM directory sync is supported for automatic provisioning and deprovisioning, as an alternative to JIT; provisioning rules can auto-assign roles or seat tiers from IdP group membership. [DOC S-hoagpet2]
- Setup requires the Owner or Primary Owner role on Team/Enterprise, or the Admin role on a Console organization. [DOC S-hoagpet2]

### Roles
- Team and Enterprise organizations have four built-in roles: Primary Owner, Owner, Admin, and User (Member). [DOC S-2ym4fr2c]
- Primary Owner: exactly one per organization, uses one plan license, can be a service account, and has full access to billing, chat controls, features, membership management, security controls, and analytics. [DOC S-2ym4fr2c]
- Owner: can invite/remove members, admins, and other owners; can modify member roles; has billing, chat, features, and membership access; on Enterprise also gets prioritized support and security controls. [DOC S-2ym4fr2c]
- Admin: can invite and remove members and pending invitations, manage integrations/capabilities, and access billing, chat, and features (plus security/analytics on Enterprise); cannot modify roles or invite other Admins/Owners. [DOC S-2ym4fr2c]
- User/Member: most restricted role; can create/modify chats and use projects; on Enterprise can request data exports; no access to billing, membership management, or admin functions. [DOC S-2ym4fr2c]
- Enterprise plans support custom roles that override the built-in defaults entirely: a member assigned only a custom role has none of the built-in role's permissions, and custom roles can grant scoped admin access (e.g. billing, identity, or privacy) without making the member a full Owner. [DOC S-2ym4fr2c]
- Only Owners and Primary Owners can access Organization settings > Billing; Admins can manage members under Organization settings > Members but not billing. [DOC S-2ym4fr2c]

### Claude Code seats on Team/Enterprise
- Claude Code is included with every seat on Team plans and on new/self-serve Enterprise plans; Premium seats add more usage for heavier workloads. [DOC S-xsggrooz]
- Older Enterprise plans instead offer "Chat + Claude Code" seats (usage-based billing) and Premium seats (seat-based billing); usage-based Enterprise has no per-seat limits and is billed at API consumption rates. [DOC S-xsggrooz]
- Owners purchase or reassign seats in Organization settings; members authenticate to Claude Code with their Team/Enterprise OAuth account. Claude Code v2.1.273+ is required for automatic skill syncing from claude.ai (see `claude/settings-and-scopes.md` for `syncClaudeAiSkills`/`syncClaudeAiPlugins`). [DOC S-xsggrooz]
- Team/seat-based Enterprise members can turn on usage credits to keep working past the seat allowance; see `agents/agent-cost-governance.md` for spend-limit and per-user reporting mechanics shared with the API/cost model. [DOC S-xsggrooz]

### Domain capture (account migration)
- Domain claiming/migration ("domain capture") is supported on Claude Enterprise plans only; Team plans can verify a domain for SSO but cannot claim or migrate existing personal accounts on it. [DOC S-dkaaodgp]
- Prerequisites before domain capture can be enabled: restrict organization creation on the verified domain, complete DNS domain verification, actively enforce SSO (not just configure it), and enable JIT provisioning or SCIM. [DOC S-dkaaodgp]
- Enable at Organization settings > Organization and access > Security > "Migrate accounts using your domain"; the console shows a preview of affected accounts with CSV export before the admin confirms the claim. [DOC S-dkaaodgp]
- The action is irreversible ("a one-way door"); affected users get an immediate email and in-product banner notification. [DOC S-dkaaodgp]
- Migration window is a single 30-day deadline for every account covered by the claim (not a rolling per-user timer); during it each user can either merge and join (transfer chats, projects, files, and memory into the new Enterprise account) or join fresh (start clean). [DOC S-dkaaodgp]
- At the deadline, unmigrated personal accounts are deactivated; paid Pro/Max subscriptions are automatically canceled with a prorated refund, and remaining usage credits are refunded. [DOC S-dkaaodgp]
- A user who isn't provisioned in the organization's IdP is locked out after migration and cannot sign in. [DOC S-dkaaodgp]

### Usage analytics
- Team/Enterprise analytics dashboard (`claude.ai/analytics/claude-code`, viewable by Admins and Owners) shows usage metrics (lines of code accepted, suggestion accept rate, daily active users/sessions), GitHub-integrated contribution metrics (PRs/lines shipped with Claude Code, requires connecting a GitHub org, public beta), a top-10 leaderboard, and CSV export. [DOC S-gxtvjkv7]
- Contribution metrics are unavailable for organizations with Zero Data Retention enabled (dashboard then shows usage metrics only) and cover only users inside the claude.ai organization, not Console API or third-party-integration usage. [DOC S-gxtvjkv7]
- Contribution attribution matches PR diff lines against Claude Code session output for sessions active from 21 days before to 2 days after the PR's merge date; lines rewritten by a developer by more than 20% are not attributed; lock files, generated/minified code, build directories, and test fixtures are excluded; matched PRs get the GitHub label `claude-code-assisted`. [DOC S-gxtvjkv7]
- On Enterprise, the Claude Enterprise Analytics API (`platform.claude.com/docs/en/api/admin/analytics`) returns per-user engagement/usage/cost across Claude surfaces including Claude Code; a Primary Owner creates the key with the `read:analytics` scope at `claude.ai/analytics/api-keys`; not available on the Teams plan (Teams instead exports the spend-report CSV). [DOC S-gxtvjkv7]
- API/Console customers get a separate dashboard at `platform.claude.com/claude-code` (requires the UsageView permission, granted to Developer/Billing/Admin/Owner/Primary Owner roles) and the Claude Code Analytics API for daily per-user metrics; contribution/GitHub metrics are not available on this path. [DOC S-gxtvjkv7]

### Compliance API (org-wide audit, distinct from data retention/ZDR)
- The Compliance API is available to Enterprise plan organizations (excluding Public Sector) and to Claude Platform customers, covering Claude chats, Cowork (Claude, Desktop, Mobile), Claude Code (CLI and Desktop), and beta coverage of Claude for Microsoft 365 add-ins (Excel, Word, PowerPoint, Outlook) and Claude Science. [DOC S-fqe5wkdo]
- It explicitly excludes Claude Code cloud sessions, Claude Code via the Claude Platform, other Microsoft 365 apps, and Amazon Bedrock/Google Cloud Agent Platform sessions. [DOC S-fqe5wkdo]
- Only the organization's Primary Owner can enable the Compliance API, from Organization settings > API; once enabled, Primary Owners can create keys covering all linked organizations while Owners can create keys limited to their own organization, and Admins cannot access that settings page at all. [DOC S-fqe5wkdo]
- The API returns activity feed events, chat data, and file content across Claude deployments, plus audit log events covering login/logout, account setting updates, workspace changes, and other organizational events; it does not log inference activity (user prompts/model responses/model activity). [DOC S-fqe5wkdo]
- This audit surface is separate from ZDR/data-retention scope: `claude/data-retention.md` covers what's stored/retained per surface; the Compliance API is about pulling organizational activity events out, not about what Anthropic retains from inference. [DER S-fqe5wkdo, claude/data-retention.md]

## Reference
| Area | Console location / API | Role required |
|---|---|---|
| SSO setup | Organization settings > Organization and access | Owner/Primary Owner (Team/Enterprise), Admin (Console) |
| SCIM/JIT provisioning | Same SSO setup flow, provisioning step | Owner/Primary Owner |
| Domain capture | Organization settings > Organization and access > Security | Owner/Primary Owner (Enterprise only) |
| Seat purchase/reassignment | Organization settings | Owner |
| Billing | Organization settings > Billing | Owner, Primary Owner only |
| Members/invites | Organization settings > Members | Admin, Owner, Primary Owner |
| Compliance API enablement | Organization settings > API | Primary Owner only (key scope: Owner = own org, Primary Owner = all linked orgs) |
| Usage/contribution analytics | claude.ai/analytics/claude-code | Admin, Owner |
| Enterprise Analytics API key | claude.ai/analytics/api-keys | Primary Owner (`read:analytics` scope) |

Related: `claude/data-retention.md` — per-surface retention and ZDR scope (this article's Compliance API and
analytics facts do not repeat retention rules; ZDR's effect on contribution metrics is cross-cited here).
`claude/settings-and-scopes.md` — server-managed settings delivery, permission modes, and the `.claude` directory
(console-level org administration in this article is a separate control plane from that file/MDM-based policy
delivery; back-link added there). `agents/agent-cost-governance.md` — spend visibility/caps per purchase path,
`modelPricing`, and the Enterprise/Teams/Console/cloud-provider cost-reporting matrix (this article covers the org
roles and console surfaces that own those controls, not the cost mechanics themselves).

## Examples
An Enterprise Primary Owner enabling org-wide audit export: Organization settings > API > enable Compliance API,
then create an Admin API key scoped to `read:analytics`/compliance endpoints and pull the activity feed
periodically. Contact your Anthropic account team first — enablement is account-team-gated, not self-service.

A Team admin planning SSO for `corp.example.com`: add the domain in Organization settings, publish
`anthropic-domain-verification-<token>` as a DNS TXT record, wait for verification, configure SAML against the
IdP (e.g. Entra ID), toggle "Require SSO", then choose SCIM so a departing employee (`jan.kowalski`) is
deprovisioned automatically instead of relying on manual removal.
