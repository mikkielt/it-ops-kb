---
topic: agents/github-copilot-admin
priority: P2
applies_to: "GitHub Copilot Business and Enterprise, organization/enterprise admin surfaces (2026-09)"
retrieved_utc: 2026-09-26
sources: [S-ovxxqqbw, S-tn4wwzyx, S-ftbeo3o7, S1805, S-unwwieso, S-udcaydkb]
status: partial
---

# GitHub Copilot Business/Enterprise administration

## Summary
Copilot admin controls span four surfaces: organization/enterprise **policies** (models, MCP servers,
coding-agent/partner-agent enablement, preview features), **content exclusion** (YAML path rules that hide
files from completions and github.com Chat, but not from agent mode or the coding agent), the **audit log**
(a single `copilot` category, 180-day retention), and the **usage metrics REST API** (daily/28-day report
downloads at org and enterprise scope). The coding agent additionally has its own outbound-traffic firewall,
separate from content exclusion, configured per organization or repository.

## Facts
### Policies
- Organization policies live under **Settings > Code, planning, and automation > Copilot > Policies**; a
  separate **Models** tab controls which models beyond the defaults are available. An enterprise owner can
  set a policy that organizations cannot then override at the organization level. [DOC S-ovxxqqbw]
- The **"MCP servers in Copilot"** policy controls general availability of MCP server support for Copilot in
  the organization; it does not control access to the GitHub MCP server from third-party applications
  (that is governed separately). [DOC S-ovxxqqbw]
- Enabling non-Copilot coding agents ("partner agents": Anthropic Claude, OpenAI Codex) inside GitHub's
  cloud-agent surface is a two-step opt-in: an enterprise admin must enable it at the enterprise level first,
  then an organization admin enables specific partner agents under **Copilot > Cloud agent**; enabled partner
  agents can use the same repositories as GitHub's own Copilot cloud agent. [DOC S-ovxxqqbw]
- Copilot in GitHub.com has its own toggles for user feedback collection and opting into preview
  ("editor preview") features, set at the organization level alongside the other policies. [DOC S-ovxxqqbw]
- For MCP servers configured through Copilot coding agent's own JSON block (`mcpServers`, pasted under
  **Settings > Copilot > MCP servers > MCP configuration**, not a repo file), see `agents/coding-agents-mcp.md`
  for the field-level schema. [DER agents/coding-agents-mcp.md, S-udcaydkb]

### Content exclusion
- Content exclusion can be set at repository, organization, or enterprise scope; org/enterprise rules apply
  to every repository seen by users with a Copilot seat in that org/enterprise, keyed by a repository
  reference (or `"*"` for all repositories). [DOC S-tn4wwzyx]
- Path rules are plain YAML lists of path strings matched with **fnmatch** pattern notation, case-insensitive,
  supporting `*`, `**`, and character sets such as `[dk]`; a repository-level list is a flat array, an
  org/enterprise-level document keys each array by repository reference (or `"*"`). [DOC S-tn4wwzyx]
- Content exclusion suppresses inline code completions and blocks the excluded files from being used as
  context or referenced in **Copilot Chat on github.com**. [DOC S-tn4wwzyx]
- Content exclusion explicitly does **not** apply to **agent mode in Copilot Chat in IDEs** — the docs state
  this in plain language, so agent-mode sessions can still read excluded files. [DOC S-tn4wwzyx]
- Changes to content exclusion take roughly 30 minutes to propagate to IDEs; VS Code, JetBrains IDEs, and
  Visual Studio expose a manual "reload" action to pick up new rules immediately, while Vim/Neovim clients
  poll and pick up changes automatically. [DOC S-tn4wwzyx]
- Organization and enterprise owners can manage content exclusion programmatically via the GitHub REST API,
  in addition to the settings UI. [DOC S-tn4wwzyx]

### Audit log
- Copilot admin and usage activity is recorded under a single audit-log category, `copilot`, described as
  containing "all activities related to your GitHub Copilot Business or GitHub Copilot Enterprise
  subscription." [DOC S-unwwieso]
- The organization/enterprise audit log retains events for **180 days**; events older than that are not
  retrievable through the audit log UI or API. [DOC S-unwwieso]

### Usage metrics API
- Usage metrics are retrieved as report-download links, not inline JSON: `GET /orgs/{org}/copilot/metrics/reports/*`
  and `GET /enterprises/{enterprise}/copilot/metrics/reports/*` return a `download_links` array of URIs to the
  actual report files, plus either a single `report_day` (daily reports) or `report_start_day`/`report_end_day`
  (28-day reports). [DOC S-ftbeo3o7]
- Each scope exposes: an org/enterprise daily-metrics report, a rolling "latest" 28-day report, a per-repository
  daily report, a daily user-team membership/join report, and per-user metrics (daily and 28-day). [DOC S-ftbeo3o7]
- Enterprise-level endpoints require enterprise owner or billing-manager status, or the fine-grained
  "View Enterprise Copilot Metrics" permission, with a token scoped `manage_billing:copilot` or `read:enterprise`.
  Organization-level endpoints require organization owner status or the fine-grained "View Organization Copilot
  Metrics" permission, with a token scoped `read:org`. [DOC S-ftbeo3o7]

### Coding agent firewall (network allowlist)
- GitHub's current docs call the coding agent "Copilot cloud agent"; the firewall pages use that name. [DOC S1805]
- The coding agent's outbound-traffic firewall is enabled by default with a recommended allowlist covering:
  OS package repositories (Debian, Ubuntu, Red Hat), container registries (Docker Hub, Azure Container
  Registry, AWS ECR), language package registries (npm/PyPI/Maven/RubyGems/crates.io/Go proxy-class
  registries), certificate authorities needed for TLS validation, and the browser hosts the Playwright MCP
  server needs. [DOC S1805]
- Organizations add custom allowed destinations under **Settings > Copilot > Internet access > Organization
  custom allowlist**, as either a bare domain (matches the domain and all subdomains) or a full URL (matches
  only that path and descendant paths); repositories can add their own custom allowlist entries only if the
  organization permits it, under repository **Settings > Copilot > Internet access**. [DOC S1805]
- The firewall can be disabled entirely at organization or repository level (if the organization allows the
  repository override); GitHub's own guidance warns that disabling it "will allow Copilot to connect to any
  host, increasing risks of exfiltration." [DOC S1805]
- The firewall applies only to processes the coding agent starts through its Bash tool, not to MCP servers it
  calls, and it operates only inside the GitHub Actions-based appliance the coding agent runs in — it is not a
  comprehensive network control. [DOC S1805]
- The coding agent itself runs from an assigned GitHub issue inside a GitHub Actions-powered, firewalled
  sandbox and can push only to the existing PR branch (when triggered via `@copilot`) or to a new
  `copilot/`-prefixed branch it creates — see `agents/headless-agent-runtimes.md` for the full runtime
  comparison. [DER agents/headless-agent-runtimes.md]

## Reference
- `agents/coding-agents-mcp.md` — Copilot coding agent's own MCP configuration JSON (`mcpServers` block,
  `COPILOT_MCP_`-prefixed secrets, no per-call approval). Cross-linked here for the MCP policy toggle.
- `agents/headless-agent-runtimes.md` — coding agent's unattended run model, sandbox, and branch/PR flow;
  add a back-link from there to this article for admin policy/audit/firewall detail.

## Examples
None — this topic is settings/API reference, not runnable code.

### Open UNKs
- Exact byte size / field-level schema of the downloaded usage-metrics report files (per-editor, per-model,
  per-language breakdown, premium-request counts) was not confirmed on the pages fetched — the API reference
  page describes only the wrapper (`download_links`, `report_day`/`report_start_day`/`report_end_day`). [UNK]
- Premium-request monthly allowance per plan, per-model request multipliers, and overage billing rate could
  not be confirmed: the billing overview and org-request-allowance pages fetched either 404'd or did not state
  the figures. [UNK]
- IDE proxy/certificate configuration for Copilot (corporate TLS-interception certs) and Copilot data-retention
  settings were not found on a docs.github.com page during this pass. [UNK]
