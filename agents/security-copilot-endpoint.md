---
topic: agents/security-copilot-endpoint
priority: P2
applies_to: "Microsoft Security Copilot embedded in Microsoft Intune (Copilot in Intune) and Intune's Security Copilot agents; Windows/Windows 365 endpoints; docs retrieved 2026-09-26"
retrieved_utc: 2026-09-26
sources: [S-wqwk4szg, S-w5rlacck, S-dge3w4di, S-ynnu52s5, S-ofjtvdgq, S-v2cnpcup, S-rnafxj57, S-qyv3zd3o, S-27puhgbj, S-tgliyduf, S-k27gpb6k, S-prhvpzpf, S-gi5rakio, S-5cjhp7co, S-no67bvqx, S-meh6fmlt, S-lnvgonfb, S-7jwkrwar, S-qbjmoh5m, S-h3bs4xjt, S-7x2lmxhr, S-27c7i7uy, S-gykoucrb]
status: partial
---

# Security Copilot for endpoint management (Intune)

## Summary
Microsoft Security Copilot reaches Intune two ways: **Copilot in Intune** (GA, embedded in the Intune admin center, IT admin/IT Pro focus, Intune-and-Windows-365-data only) and the **standalone Security Copilot portal** (SOC focus, spans Intune, Defender, Entra, Purview). Both use the same Graph APIs and the same Intune RBAC/scope tags an admin already has — Copilot never sees more than the signed-in admin's own permissions. Beyond the chat experience, Intune ships specialized **Security Copilot agents** — autonomous, scoped, admin-reviewed automations tied to their own Entra identity — for vulnerability remediation, policy configuration, change review and device offboarding; two of the four (Policy Configuration Agent and Change Review Agent) are already scheduled for retirement on 2026-08-31. Everything runs on **Security Compute Units (SCUs)**: Microsoft 365 E5/E7 tenants get free monthly inclusion capacity, everyone else provisions and is billed hourly (provisioned) or on demand (overage). Extensibility comes through **plugins**, including a preview **MCP plugin** type that lets an admin wire an external MCP server's tools into Security Copilot prompts, promptbooks and custom agents.

## Facts

### Copilot in Intune vs. standalone Security Copilot
- Two ways to reach Intune data with Copilot: **Copilot in Intune**, embedded in the Microsoft Intune admin center banner, Intune/Windows 365 Cloud PC data only, IT admin/IT Pro focus; and the standalone **Security Copilot portal**, which spans all enabled services (Intune, Defender, Entra ID, Purview, ...) with a SOC focus that IT admins can also use. [DOC S-wqwk4szg]
- The standalone Security Copilot experience for Intune (the Security Copilot portal, with the Intune plugin enabled) uses natural-language prompts to return device properties/hardware, app/compliance/configuration policy and assignment data, cross-device issue comparisons, and Cloud PC licensing/connection/configuration/performance insights; it uses the same Intune capabilities as Copilot in Intune, reachable alongside Defender/Entra/Purview data in one portal. [DOC S-w5rlacck, S-dge3w4di]
- Both experiences are built on the same Microsoft Graph APIs the Intune admin center itself uses — Security Copilot gives an admin no more Intune data access than they already have in the admin center. [DOC S-dge3w4di]
- Copilot in Intune reached **general availability in July 2025**; Copilot in Microsoft Entra reached GA the same month. [DOC S-h3bs4xjt]
- Copilot in Intune has no built-in open-prompt box (only suggested/built-in prompts as of this writing, with an open prompt planned, no ETA); the standalone Security Copilot portal supports open prompts and promptbooks, and keeps prompt/response history even for prompts submitted from the embedded experience. [DOC S-dge3w4di]
- Copilot in Intune use cases: natural-language data exploration, policy and setting management (summarize an existing policy's settings and security impact), device details/troubleshooting (installed apps, group membership, error-code analyzer, device comparison), Endpoint Privilege Management (EPM) request analysis, Microsoft Surface device troubleshooting (warranty, support tickets — public preview as of March 2025), and Windows 365 Cloud PC insights. [DOC S-wqwk4szg, S-ynnu52s5, S-h3bs4xjt]
- "Summarize with Copilot" on a selected device, and Copilot-generated KQL for the Intune **device query** feature (for one device or for many devices, limited to properties device query supports), are both part of Copilot in Intune's device troubleshooting. Device query itself requires a license that includes Advanced Analytics. [DOC S-ynnu52s5, S-wqwk4szg]
- Copilot in Intune for Windows 365 (its own sub-feature) needs the **Windows 365 plugin** enabled in Security Copilot in addition to Copilot in Intune; it covers Cloud PC performance optimization/resizing recommendations, connectivity/latency summaries, license-optimization (unused/underused Cloud PC detection), and provisioning/grace-period diagnostics (bulk analysis of up to 10 devices at once, or one Cloud PC or user). [DOC S-tgliyduf]

### Security Copilot agents in Intune
- Four Security Copilot agents ship for Intune: **Vulnerability Remediation Agent** (public preview), **Policy Configuration Agent**, **Change Review Agent** (public preview) and **Device Offboarding Agent**. All are reachable from the **Agents** node in the Intune admin center (Vulnerability Remediation is also reachable from Endpoint security); each is scoped to one use case, uses RBAC, and requires admin review/approval before acting. [DOC S-ofjtvdgq, S-v2cnpcup, S-qyv3zd3o, S-27puhgbj]
- **Starting 2026-08-31 the Policy Configuration Agent and the Change Review Agent are retired** from the Intune admin center; existing runs can finish and processes should be migrated before that date, with no replacement named. [DOC S-qyv3zd3o, S-27puhgbj]
- **Vulnerability Remediation Agent**: uses Microsoft Defender Vulnerability Management data to surface a prioritized list of CVEs on managed devices with a Copilot-summarized impact analysis, suggested actions, affected/exposed device counts and step-by-step Intune remediation guidance; suggestions can be marked **Applied** to track remediation over time. Supports Windows and apps in Intune only; public cloud only, no government cloud. [DOC S-v2cnpcup]
  - Licensing: Microsoft Intune Plan 1, Microsoft Security Copilot with sufficient SCUs, and Microsoft Defender Vulnerability Management (via Defender for Endpoint P2 or standalone). Plugins required: Microsoft Intune, Microsoft Defender. [DOC S-v2cnpcup]
  - To set up/manage: Security Copilot workspace **Owner** role plus Intune read permissions; then **Create new identity** provisions a dedicated agentic identity/user the agent runs as (recovering a deleted agent identity from Entra is possible; otherwise remove and re-set-up the agent). A **Run Readiness Check** validates delegated permissions before the Run button is enabled. [DOC S-v2cnpcup]
  - Roles to set up and manage the agent: Intune **Read Only Operator** (or custom role with Security Tasks/read, Mobile apps/read, Device configurations/read, Organization/read) plus Security Copilot **Copilot owner**. [DOC S-v2cnpcup]
  - As of the week of 2026-06-08, the agent is rolling out to use a **Microsoft Entra agentic identity** (`entra/agent-id.md`) instead of a human user identity by default when a new instance is set up — the agent then runs under the permissions delegated to that agentic user. It was previously in limited preview and is now in public preview for all customers. [DOC S-7x2lmxhr]
  - Agent logs (Security Copilot audit logs) record create/delete/run and permission failures, but not discovered vulnerabilities or applied remediations — use the in-product "Applied" marking for that. Common failure: running out of SCUs during a run. [DOC S-rnafxj57]
- **Policy Configuration Agent**: takes an uploaded document (STIG, NIST, internal baseline) or free-text requirements (e.g. "All laptops must have BitLocker enabled with AES-256 encryption"), parses each requirement with Security Copilot, maps it to settings-catalog settings, and produces a draft configuration profile the admin reviews (accept, adjust, exclude, or acknowledge unsupported items) before creating a normal Intune policy that still needs assignment. Windows only. [DOC S-27puhgbj]
  - Licensing: Intune Plan 1 + Security Copilot with sufficient SCUs. Plugin: Microsoft Intune (already enabled if Copilot in Intune is on). [DOC S-27puhgbj]
  - Roles to enable/configure: Security Copilot **Copilot owner** + Intune Read only operator (Device configurations/Read). Roles to generate suggestions: Copilot **Contributor** + same Intune read role. Roles to also **create** the policy: Copilot Contributor + Intune **Policy and Profile manager** (Device configurations/Create, /Update) or an equivalent custom role. [DOC S-27puhgbj]
  - The agent runs under the identity/permissions of the account used at setup (not a separate agentic identity); if the agent isn't used for **90 days**, authorization expires and runs fail until an admin selects **Renew authentication** (optionally switching identity). Only one agent instance is supported per tenant. [DOC S-27puhgbj]
- **Change Review Agent**: evaluates Multi Admin Approval requests for PowerShell scripts on Windows by aggregating Defender Vulnerability Management (threat), Entra ID (identity risk) and Intune (request/history) signals, then recommends **Approve / Reject / Needs more info** for up to 10 requests per run — the approve/reject decision itself stays with the admin. [DOC S-qyv3zd3o]
  - Licensing: Intune Plan 1, **Microsoft Entra ID P2**, Microsoft Defender Vulnerability Management, Security Copilot with sufficient SCUs. Plugins required: Microsoft Intune, Microsoft Entra, Microsoft Defender XDR, Microsoft Threat Intelligence. [DOC S-qyv3zd3o]
  - Roles to enable/configure: Entra **Intune Administrator** + **Security Reader** + Identity risk (Risky users) read, plus Defender Security Reader-equivalent RBAC, plus Security Copilot **Copilot owner**. Roles to use: Intune Read Only Operator, Entra Security Reader, the same Defender access, Security Copilot **Copilot contributor**. [DOC S-qyv3zd3o]
  - Like Policy Configuration Agent, it runs under the setup account's identity (refreshed each run) and expires after **90 consecutive days** without a run; only one instance per tenant/user context; an admin must manually start it and cannot pause it once started. [DOC S-qyv3zd3o]
- **Device Offboarding Agent**: identifies stale or misaligned devices across Intune and Microsoft Entra ID and requires admin approval before offboarding any device. [DOC S-ofjtvdgq]
- Broader Security Copilot agent catalogue touching endpoint/identity management (beyond the four Intune-node agents): **Conditional Access Optimization Agent** in Microsoft Entra (GA July 2025) — autonomously flags users/apps not covered by Conditional Access policy and recommends one-click remediations, all actions logged for audit; **Phishing Triage Agent** in Microsoft Defender (public preview July 2025, extended scope now called Security Alert Triage Agent, that extension itself in preview) — autonomously classifies user-reported phishing alerts as true/false positive using LLM reasoning plus Defender/Threat Intelligence tools, transparent per-alert rationale and decision tree, feedback loop; and **Threat Intelligence Briefing Agent** (public preview July 2025, standalone experience) — generates organization-specific threat briefings from industry, geography and attack-surface attributes. [DOC S-h3bs4xjt, S-qbjmoh5m]
- Phishing Triage Agent setup lets an admin pick **Create a new agent identity (recommended)** — provisions a Microsoft Entra Agent ID for the agent — or **connect an existing user account** whose access the agent then inherits; least-privilege custom RBAC roles are assigned explicitly (e.g. Alerts/manage, Email & collaboration content limited to emails tied to alerts). [DOC S-qbjmoh5m]

### Roles and access
- Security Copilot introduces exactly two platform roles that are **not** Microsoft Entra ID roles and by themselves grant no security-data access: **Copilot owner** (can publish/manage custom plugins for the tenant, manage capacity, data-sharing/feedback settings, view the usage dashboard) and **Copilot contributor** (can run sessions/promptbooks; cannot manage tenant-wide plugins or capacity by default). Security Copilot always enforces **at least two owners**, which cannot both be removed. [DOC S-no67bvqx]
- Several Entra, Intune and Purview roles automatically inherit **Copilot owner**: Entra Billing Administrator, (Entra) Compliance Administrator, Global Administrator, **Intune Administrator**, Security Administrator; the Intune-specific inheriting role is Intune Administrator; Purview Compliance Administrator / Data Governance Administrator / Organization Management also inherit it. All other built-in and custom Intune RBAC roles inherit **Copilot contributor**. [DOC S-no67bvqx, S-dge3w4di]
- Security Copilot never elevates a user's access: it "doesn't go beyond the access you have" — using the Intune plugin's data still requires the caller's own Intune RBAC role (e.g. Endpoint Security Manager) or scope tag, exactly as in the admin center; a caller without permission to a given device/policy gets "You don't have permission to access this feature." [DOC S-no67bvqx, S-dge3w4di]
- Capacity provisioning (creating/attaching SCUs) additionally needs **Azure Contributor or Owner** on the subscription/resource group plus **Security Administrator or higher** in the tenant. [DOC S-prhvpzpf]

### Security Compute Units (SCU) provisioning and billing
- **SCU** = the unit of compute Security Copilot charges for; consumed by the standalone portal, every embedded experience, Microsoft- and partner-built agent invocations, and other Copilot features. [DOC S-k27gpb6k]
- Non-E5/E7 tenants must provision capacity before use: **minimum 1 SCU, maximum 100 SCUs** provisioned; Microsoft recommends **3 SCUs with unlimited overage** for an introductory evaluation. [DOC S-prhvpzpf]
- **Provisioned capacity**: billed per full clock hour (fixed blocks like 9:00-10:00, not rolling); unused SCUs in an hour don't roll over; if provisioned SCUs are exhausted, requests stop unless overage is configured. Any usage inside an hour bills a full provisioned SCU for that hour regardless of exact start/end time. [DOC S-k27gpb6k]
- **Overage capacity**: consumed on demand above the provisioned baseline; configurable as a maximum limit or unlimited; billed to one decimal place of actual consumption (not rounded up). [DOC S-k27gpb6k]
- Worked example: 4 SCUs provisioned, 6 SCU overage cap; an hour's activity totaling 7.2 SCUs of consumption bills as 4 provisioned SCUs + 3.2 overage SCUs. [DOC S-k27gpb6k]
- Capacity changes (increase/decrease provisioned or overage SCUs) can be made in the Azure portal or the Security Copilot portal and take effect **within 30 minutes**; required role: Azure capacity owner/contributor who is also a Security Copilot owner. [DOC S-gi5rakio]
- SCUs cannot be shared across Security Copilot **workspaces** in the same tenant: each workspace is capped to its own provisioned + overage total. [DOC S-gykoucrb]
- **Microsoft 365 E5 and E7 customers are auto-provisioned and auto-onboarded** to Security Copilot with a **Default Security Copilot Capacity** — an inclusion capacity created automatically with a default workspace, tenant-wide, cannot be modified, shared across all users/experiences, not billed hourly (comes from the monthly E5/E7 inclusion bucket), and its UI cost figures are informational only. [DOC S-5cjhp7co, S-27c7i7uy]
- Inclusion sizing: **400 SCUs/month for every 1,000 paid user licenses**, up to a **10,000 SCU/month** cap, scaling proportionally below 1,000 licenses (example: 400 licenses -> 160 SCUs/month; 4,000 licenses -> 1,600 SCUs/month). [DOC S-5cjhp7co]
- Copilot in Intune itself carries **no separate licence or Intune-specific SKU** beyond Security Copilot/SCUs — access is governed purely by Security Copilot roles/SCUs plus existing Intune RBAC. [DOC S-wqwk4szg]
- FastTrack (Microsoft's onboarding assistance program) explicitly notes it will help provision SCUs and configure default environments for Copilot in Intune, but is out of scope for detailed pricing, standalone-experience walkthroughs, and creating new custom agents or deploying third-party agents. [DOC S-27c7i7uy]

### Data handling and privacy
- Security Copilot **runs queries as the calling user** — it never operates with elevated privileges beyond what that user already has. [DOC S-lnvgonfb]
- If a tenant opts in to share Customer Data for model improvement, that data is **not** shared with OpenAI, **not** used for sales, **not** shared with third parties, and **not** used to train the Azure OpenAI foundational model; captured feedback data may be used to build Microsoft's own security-specific models layered on top of Azure OpenAI / Microsoft models. [DOC S-lnvgonfb, S-7jwkrwar]
- Two independent, owner-configurable data-sharing toggles exist: allow Microsoft to capture data via human review to validate product performance, and allow Microsoft to capture/human-review data to build/validate Microsoft's security AI model; a Copilot owner can also disable feedback collection tenant-wide via a support ticket. [DOC S-lnvgonfb]
- All Security Copilot data at rest in Azure is encrypted (AES-256); the service meets Azure production data-compliance standards. [DOC S-lnvgonfb]
- Security Copilot's underlying models are Azure OpenAI LLMs (via Foundry Models) that are **not trained on Security Copilot Customer Data**; security-specific context reaches the model at inference time through plugins/grounding, not training. [DOC S-7jwkrwar]
- For Microsoft 365 data sources, an admin must separately enable Security Copilot in the Microsoft 365 sharing-preference option and users must enable the corresponding plugin; for other Microsoft services (e.g. Intune, Defender) the plugin is enabled by default and users can turn it off at any time. [DOC S-lnvgonfb]

### Plugins and MCP
- Security Copilot agents/prompts reach external data and services through **plugins**: Microsoft-built, partner-built, or custom (a YAML manifest uploaded as a file or as a link, for yourself or for the whole organization). Changing preinstalled plugins' availability and publishing custom plugins tenant-wide are Copilot **owner** capabilities by default. [DOC S-7jwkrwar, S-meh6fmlt, S-no67bvqx]
- **MCP plugins are a preview capability** (documented as relating to a "prereleased product"): connecting an existing MCP server exposes its tools as Security Copilot skills usable in standalone prompting, promptbooks, Logic Apps and custom agents. [DOC S-meh6fmlt]
- MCP plugin manifest fields under `SkillGroups[].Settings`: `Endpoint` (server URL, required), `UseStreamableHttp` (true for Streamable HTTP; false uses SSE, which the page calls less secure and due to be deprecated; required), `UsePluginAuth` (true for OAuth2/AADDelegated auth, false uses the caller's own credential, required), `TokenScope` (required only when `UsePluginAuth` is false), `TimeoutInSeconds` (optional, wait time for tool-list/tool-call completion), and `AllowedTools` (comma-separated allow-list; a server tool not listed here cannot be imported or called, required). [DOC S-meh6fmlt]
- MCP plugin known limitations: only MCP **tools** are supported — MCP resources, prompts and utilities are not; Security Copilot does **not** dynamically re-discover a server's tool changes (re-upload the manifest YAML to pick up added/edited tools); any tool whose `destructiveHint` annotation is `true` is refused at import even if listed in `AllowedTools`; tool inputs must use primitive data types only. [DOC S-meh6fmlt]
- Guidance: prefer MCP servers hosted by the trusted provider itself rather than a proxy, and track/review every MCP server connected to the tenant, since the customer is responsible for the tools and data it reaches through a non-Microsoft or external MCP server. [DOC S-meh6fmlt]

## Reference
- `entra/agent-id.md` — the Microsoft Entra agentic identity model the Vulnerability Remediation Agent (rolling out) and the Phishing Triage Agent's "Create a new agent identity" option provision; see its Reference for the back-link to this article.
- `intune/compliance-policies.md` — the compliance/device-risk data (BitLocker, DHA, threat-protection level) the Vulnerability Remediation Agent and Copilot in Intune prompts surface and reason about.
- `intune/configuration-policies.md` — the settings-catalog policy objects the Policy Configuration Agent creates and Copilot in Intune summarizes; see its Reference for the back-link to this article.
- `defender/advanced-hunting.md` — the KQL/advanced-hunting concepts behind Copilot in Intune's device-query KQL generation and the security telemetry the Phishing Triage/Vulnerability Remediation agents draw on.
- `mcp/spec-overview.md`, `mcp/transports-streamable-http.md` — the MCP transport and tool semantics (Streamable HTTP vs. SSE, `destructiveHint`) that the Security Copilot MCP plugin's `UseStreamableHttp` setting and destructive-tool refusal map onto.
- Whether the Device Offboarding Agent has its own dedicated Learn article with licensing/role/identity details (only the overview page's one-paragraph description was available on the pages read for this topic) was not found. [UNK]

## Examples

Example MCP plugin manifest fragment for a custom Security Copilot skill (placeholders only):

- SNIPPET: an MCP plugin manifest (`Descriptor` + one `MCP`-format `SkillGroups` entry) connecting a
  Streamable HTTP MCP server with OAuth2/AADDelegated auth and an explicit tool allow-list; context:
  Security Copilot MCP plugins (preview); checked: no [DOC S-meh6fmlt: `Descriptor`/`SupportedAuthTypes`
  fields and every MCP skill-group `Settings` key (`Endpoint`, `UseStreamableHttp`, `UsePluginAuth`,
  `TokenScope`, `TimeoutInSeconds`, `AllowedTools`)]
```yaml
Descriptor:
  Name: PL-SRV-0042-InventoryMcp
  DisplayName: PL-SRV-0042 device inventory MCP tools
  Description: Read-only device inventory lookups for corp.example.com
  DescriptionForModel: Look up managed device inventory by device or user
  SupportedAuthTypes:
    - AADDelegated
SkillGroups:
  - Format: MCP
    Settings:
      Endpoint: https://mcp.corp.example.com/mcp
      UseStreamableHttp: true
      UsePluginAuth: true
      TokenScope: api://00000000-0000-0000-0000-000000000000/.default
      TimeoutInSeconds: 60
      AllowedTools: get_device,list_devices_for_user
```

Copilot in Intune suggested prompts for device troubleshooting include "Summarize this device", "Analyze an error code", "Compare this device with another device" and "Show apps on this device"; each asks for the device name or ID (e.g. PL-LT-00123) or the error code when needed. [DOC S-ynnu52s5]
