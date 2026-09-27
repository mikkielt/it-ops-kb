---
topic: agents/windows-agentic-platform
priority: P2
applies_to: "Windows on-device AI/agentic platform: MCP on Windows (ODR, preview), Copilot Actions agent workspace (preview), Foundry Local (preview CLI, GA SDK), Windows ML, Copilot+ PC requirements, Policy CSP WindowsAI"
retrieved_utc: 2026-09-26
sources: [S-w7egu7gh, S-hwvrdtxc, S-22dvomdp, S-qz6chi2l, S-jvu722ab, S-2ypn2ron, S-msz6m5qt, S-onenhsl2, S-x5pz6ywz, S-77pv663g, S-73vw637c, S-6kxfh4ff, S-yilkexx7, S-ewh6l73v, S-kpbxpz3h, S-7bcl2ob5]
status: complete
files: [agents/windows-ai-policies.csv]
---

# Windows agentic platform: MCP on Windows, Copilot Actions, Foundry Local, Windows ML, Copilot+ PC

## Summary
Windows is building a local "agentic OS" layer distinct from the cloud Foundry Agent Service / Windows 365
for Agents (`agents/foundry-agent-service.md`): an on-device MCP registry (ODR) that discovers and contains
MCP servers, a **Copilot Actions** preview that runs agents under separate **agent accounts** inside an
isolated **agent workspace**, a local model runtime stack (**Foundry Local** on top of **Windows ML**/ONNX
Runtime), and Copilot+ PC hardware requirements that gate most of the on-device AI APIs. IT admins control
these features almost entirely through the **Policy CSP `WindowsAI`** area (`agents/windows-ai-policies.csv`),
which also covers Recall and Click to Do. Everything under `windows/ai/mcp/*` and the agent-workspace/agent-
account model is explicitly **preview** and may change before GA; Recall and Click to Do policies split
between GA (24H2 + specific KBs) and preview (Windows Insider only) per-setting — status is called out on
every fact below. A Windows IT-pro blog url a manager considered for this topic was not fetched (no
`.md` frontmatter, community source not needed once Learn pages covered the same ground); nothing here is
sourced from it.

## Facts

### MCP on Windows / On-device Agent Registry (ODR)
- MCP on Windows provides the **Windows On-device Agent Registry (ODR)**, "a secure, manageable interface to
  discover and use agent connectors from local apps and remote servers using Model Context Protocol (MCP)".
  The overview page is explicitly marked as covering pre-released product that may change substantially.
  [DOC S-w7egu7gh] preview
- ODR benefits per the docs: broad standardized MCP support (local apps and remote servers), discoverability,
  security (servers contained in a separate environment by default), user/admin control via Windows Settings
  and Intune, logging/auditability, and built-in Windows connectors (e.g. a File Explorer MCP server). [DOC S-w7egu7gh] preview
- The command-line tool `odr.exe` manages on-device agents/MCP servers: `odr mcp run` (run an MCP server),
  `odr mcp list` (list registered servers), `odr mcp add <manifest file path>` (register),
  `odr mcp remove <server id>` (unregister), `odr mcp configure <server id>` (configure); global options
  `-?`/`-h`/`--help`, `--version`, `--verbose`. [DOC S-22dvomdp] preview
- Registering an MCP server with Windows depends on packaging: apps with **package identity** (MSIX, or
  unpackaged apps granted identity via packaging with external location) register automatically on
  install/uninstall via manifest metadata; apps **without** identity (bare .exe, MSI-packaged, or a standalone
  MCP bundle/.mcpb) can be installed directly but "can't run in the securely contained agent process and will
  not be accessible from the Windows on-device agent registry" unless the user enables "Reduce protections for
  agent connectors"; a third path is **manual registration** via the ODR CLI for remote servers or fine-grained
  local control. [DOC S-qz6chi2l] preview
- **MCP server containment**: by default, servers reached through the ODR run in an **agent session**, a
  separate Windows session under a separate **agent user account**, limited to approved resources — reducing
  exposure to threats such as cross-prompt injection. Only binary (.exe) servers with package identity via an
  MSIX package extension and a valid `manifest.json` (minimum fields `manifest_version`, `name`, `version`,
  `description`, `author`, `server`, and a `_meta` block with a `com.microsoft.windows` field defining both
  `static_responses` and `tools/list`) can run contained; servers packaged as MCP bundles currently cannot run
  contained. [DOC S-hwvrdtxc] preview
- The setting **Settings > System > Advanced > AI components > Reduce protections for agent connectors**
  lets a user run MCP servers accessed through the ODR with reduced protections (needed to run an unpackaged
  MCP bundle in the user session); Microsoft's own note: "This setting enables MCP servers to run with more
  access and privileges, and may expose your device to additional security threats." [DOC S-hwvrdtxc] preview
- **Agent connectors**: "a packaged integration point that allows an AI agent to connect to external
  capabilities through [MCP]... the bridge between the agent and an MCP server." Windows File Explorer ships
  its own MCP connector; other agents that support Windows MCP servers include the Windows Settings connector,
  Visual Studio GitHub Copilot agent mode, and VS Code GitHub Copilot agent mode; the Microsoft Agent Framework
  is a listed dev kit for building agents that use the ODR. [DOC S-w7egu7gh] preview
- Quickstart prerequisites for an MCP **host** app on Windows: Windows build **26220.7262** or higher, and
  (not yet enforced in public preview, but will be at GA) package identity for the host app. Sample flow:
  `odr.exe list` returns registered servers as JSON for the host to consume. Sample repo:
  `github.com/microsoft/mcp-on-windows-samples`. [DOC S-jvu722ab] preview
- Policy CSP `WindowsAI\AgentConnectorAccessPolicy` (device-only, Windows Insider Preview) allows listed
  MCP Server/Host connections via a JSON string matching a schema at
  `go.microsoft.com/fwlink/?LinkId=2363700`; `WindowsAI\ConfigureAgentConnectors` (device-only, Windows
  Insider Preview) can force-enable (1) or force-disable (2) agent connectors instead of leaving the user in
  control (0, default). See `agents/windows-ai-policies.csv` for the full CSP row set. [DOC S-2ypn2ron] preview

### Copilot Actions: agent accounts, agent workspace, security model
- **Copilot Actions** is Windows's local agentic-desktop feature; it is disabled by default and only enabled
  when a user toggles **Settings > System > AI components > Agent tools > Experimental agentic features**.
  [DOC S-kpbxpz3h] preview
- Security building blocks: (1) **User Control** — off by default, opt-in toggle; (2) **Agent accounts** — "a
  separate standard account on your device that agents use when acting on your behalf, enabling agent-level
  authorization and access control"; (3) **Agent workspace** — "a contained environment where agents can work
  in parallel with a human user, enabling runtime isolation and granular permissions," giving the agent its
  own desktop while limiting its visibility into the user's desktop; built on the security boundaries Microsoft
  defends under its Windows security servicing criteria; (4) **User Transparency** — lets the user authorize,
  monitor and take over agent actions in the agent workspace. Entra/MSA identity support for agents is
  described as "coming soon." [DOC S-kpbxpz3h] preview
- Applications and actions Copilot Actions drives run under the **agent account**, not the signed-in user's
  account, so agent work is clearly separated from user actions on the system; agent accounts are only
  provisioned once a user enables the agent workspace. [DOC S-kpbxpz3h] preview
- Policy CSP `WindowsAI\AgentConsentDuration` (device-only, Windows Insider Preview) sets how many hours an
  agent consent decision stays valid before Windows re-prompts the user: range 1–8760 hours, default **720**
  hours (30 days). [DOC S-2ypn2ron] preview
- `WindowsAI\OnDeviceRegistryLoggingLevel` (device-only, Windows Insider Preview) sets the log verbosity for
  on-device registry (agent/MCP) operations: 0 error-or-higher (default), 1 information-or-higher, 2
  debug-or-higher. [DOC S-2ypn2ron] preview

### Foundry Local
- **Foundry Local** runs LLMs locally on the Windows device, needs no special permissions or unlock tokens,
  and its native SDK runs inside the app process without the Foundry Local CLI or a separate local REST server;
  the CLI is optional (`winget install Microsoft.FoundryLocal`, then `foundry --version` to verify). [DOC S-msz6m5qt]
  preview (CLI) / not GA-labeled for SDK
- On macOS (Apple Silicon) the Foundry Local CLI installs with `brew tap microsoft/foundrylocal` then
  `brew install foundrylocal`. [DOC S-onenhsl2] preview
- The "Choose your Windows AI solution" page describes Foundry Local as open-source LLMs and speech models
  behind an OpenAI-compatible API, on any Windows hardware. [DOC S-ewh6l73v] preview
- Foundry Local prerequisites (Windows quickstart): Windows 11 version 24H2 (build 26100) or later, .NET 9.0
  SDK or later, an x64 or Arm64 device with enough memory/disk for the chosen model; a dedicated GPU, NPU or
  Copilot+ PC is **not** required when the model has a compatible CPU variant. [DOC S-msz6m5qt] preview
- Install exactly one of the conflicting Python packages: `foundry-local-sdk-winml` (Windows, includes
  hardware acceleration, recommended on Windows) or `foundry-local-sdk` (macOS/Linux, or Windows without
  hardware acceleration) — both pin different `onnxruntime-core` versions and cannot coexist; the .NET
  packages split the same way (`Microsoft.AI.Foundry.Local.WinML` for Windows with Windows ML integration,
  `Microsoft.AI.Foundry.Local` for non-Windows targets). [DOC S-msz6m5qt] preview
- Passing a model **alias** (not a full model ID) to `GetModelAsync`/`get_model` lets Foundry Local pick a
  compatible hardware variant (e.g. a QNN NPU variant on Snapdragon, a CUDA variant on NVIDIA, or a CPU
  variant); the Windows quickstart's example alias is `phi-4-mini` (Phi-4 Mini). [DOC S-msz6m5qt] preview
- CLI: `foundry chat <alias>` runs a model interactively (downloading it on first run), `foundry model list`
  shows the catalog, and `foundry server status` shows the local endpoint URL; an alias lets Foundry Local
  choose the best variant for the hardware. [DOC S-onenhsl2] preview
- The **Foundry Local CLI is explicitly "available in preview"**: "Public preview releases provide early
  access to features that are in active deployment... Features, approaches, and processes can change or have
  limited capabilities, before General Availability (GA)." [DOC S-onenhsl2] preview
- Recommended resilience pattern for a Windows AI feature: try **Windows AI APIs** first (fastest, most
  optimized, on supported hardware) -> fall back to **Foundry Local** (open model, runs on any Windows
  hardware) -> fall back to **Azure AI** in the cloud. [DOC S-ewh6l73v] preview (pattern spans preview/GA components)
- Phi Silica (the Windows AI API on-device SLM) remains a **Limited Access Feature requiring an unlock token**
  and is separate from Foundry Local's Phi-4 Mini; Phi Silica is scheduled to be replaced by "Aion Instruct,"
  which will not require a Limited Access Feature token. [DOC S-msz6m5qt] preview

### Windows ML
- **Windows ML** is "the unified and high-performance local AI inferencing framework for Windows, powered by
  ONNX Runtime," running models from PyTorch, TensorFlow/Keras, TFLite, scikit-learn etc., and accelerating
  inference via execution providers (EPs) for NPU, GPU and CPU that Windows installs and keeps current via
  Windows Update. [DOC S-x5pz6ywz] GA (framework itself; see EP hardware-support caveat below)
- System requirements: OS per whatever Windows App SDK supports; architecture x64 or Arm64; any hardware
  configuration. CPU and GPU (via DirectML) support works on all supported Windows versions; **hardware-
  optimized EPs for NPUs and specific GPU hardware require Windows 11 version 24H2 (build 26100) or later**.
  [DOC S-x5pz6ywz] GA
- Two deployment modes: **self-contained** (`Microsoft.Windows.AI.MachineLearning` or `Microsoft.WindowsAppSDK.ML`
  alone; adds ~41 MB to app size; doesn't auto-update) or **framework-dependent** (`Microsoft.WindowsAppSDK.ML`
  + `Microsoft.WindowsAppSDK.Runtime`; smaller app, auto-updates via the shared Windows App SDK runtime). [DOC S-77pv663g] GA
- The framework-dependent Windows ML Runtime is composed of `Microsoft.Windows.AI.MachineLearning.dll`
  (~1 MB, the Windows ML APIs), `onnxruntime.dll` (~20 MB, the ONNX Runtime engine) and `DirectML.dll`
  (~20 MB, the included GPU execution provider) — total **~41 MB**; vendor EPs (QNN, VitisAI, OpenVINO,
  NvTensorRtRtx, MIGraphX) are obtained separately via the `ExecutionProviderCatalog` API or bundled by the
  app. [DOC S-77pv663g] GA
- C# requirements: .NET 8+ with target framework moniker `net8.0-windows10.0.17763.0`+ for
  `Microsoft.WindowsAppSDK.ML`, or `net8.0-windows10.0.18362.0`+ for `Microsoft.Windows.AI.MachineLearning`;
  with .NET 6 only the install/EP-management APIs are available, not the full `Microsoft.ML.OnnxRuntime`
  surface. Python requirement: 3.10–3.13, x64 or Arm64, an unpackaged Python install (python.org or winget,
  not the Microsoft Store). [DOC S-77pv663g] GA

### Copilot+ PC hardware requirements
- Copilot+ PCs are defined by hardware: an **NPU with 40+ TOPS** (trillion operations per second), plus
  specific supported SoCs; most Windows AI APIs require a Copilot+ PC, though "a growing number of APIs (Phi
  Silica on GPU, Speech Recognition, Video Super Resolution) also run on non-Copilot+ Windows 11 PCs"; Copilot+
  is **not required** for Foundry Local or for Windows ML itself. [DOC S-ewh6l73v] GA (PC category); feature
  availability varies by API
- Copilot+ PC developer guidance repeats the same 40+ TOPS NPU threshold and lists example qualifying devices
  (Surface Laptop/Pro Copilot+ PC, HP OmniBook X 14, Dell Latitude 7455/XPS 13/Inspiron 14, Acer Swift 14 AI,
  Lenovo Yoga Slim 7x/ThinkPad T14s, Samsung Galaxy Book4 Edge, ASUS Vivobook S 15/ProArt PZ13, plus AMD Ryzen
  AI 300 series and Intel Core Ultra 200V series silicon). [DOC S-yilkexx7] GA
- **Recall** minimum requirements: a Copilot+ PC meeting the Secured-core standard, a 40 TOPS NPU, 16 GB RAM,
  8 logical processors, 256 GB storage (>=50 GB free to enable; snapshot saving auto-pauses below 25 GB free),
  Device Encryption or BitLocker enabled, and Windows Hello Enhanced Sign-in Security enrollment with at least
  one biometric option. [DOC S-73vw637c] GA (Recall itself GA on Copilot+ PCs since 2025-04-25 per the same
  domain's release note) [DOC S-7bcl2ob5]
- **Click to Do** minimum requirements: a Copilot+ PC (or eligible Cloud PC), 40 TOPS NPU, 16 GB RAM, 8 logical
  processors, 256 GB storage; Snipping Tool 11.2411.20.0+ needed to show the Click to Do entry point from
  Snipping Tool. Screenshot analysis for Click to Do "is always performed locally on the device." [DOC S-6kxfh4ff] GA
- Recall reached General Availability on Copilot+ PCs on **2025-04-25**; it was previewed with Click to
  Do to Windows Insiders in the Dev Channel on 2024-11-22 (the same update list has an earlier Recall preview
  post of 2024-06-07). [DOC S-7bcl2ob5] GA

### IT controls: Policy CSP `WindowsAI` (Recall, Click to Do, agentic features)
- All Recall, Click to Do and agent-connector/agent-consent settings live under one CSP area,
  `./Device/Vendor/MSFT/Policy/Config/WindowsAI/*` (and the `./User/...` mirror for the user-scoped ones), with
  Group Policy mapping under **Computer/User Configuration > Administrative Templates > Windows Components >
  Windows AI**, ADMX file `WindowsCopilot.admx`. The full policy/CSP table (path, allowed values, default,
  scope, minimum OS/KB, GA-vs-preview) is in `agents/windows-ai-policies.csv`. [DOC S-2ypn2ron]
- `AllowRecallEnablement` defaults to **1 (available)** at the CSP level, but Microsoft's Manage-Recall guidance
  states Recall is "disabled and removed for managed devices" by default and individual users cannot enable it
  themselves — i.e. commercial/managed devices ship with Recall off in practice even though the CSP default
  value is 1; requires **Windows 11 24H2 with KB5055627 (build 10.0.26100.3915)** or later. [DOC S-2ypn2ron,
  S-73vw637c] GA — see `_conflicts.md` for the apparent default-vs-practice discrepancy
- `DisableClickToDo` is still **Windows Insider Preview only** per the Policy CSP applicability table, even
  though the companion "Manage Click to Do" admin guide (which cites the same CSP node) describes deployment
  guidance as if generally available; treat the policy as preview until the CSP page lists a stable OS/KB
  requirement. [DOC S-2ypn2ron, S-6kxfh4ff] preview (per CSP applicability) — see `_conflicts.md`
- `RemoveMicrosoftCopilotApp` (Windows 11 24H2+) uninstalls the standalone Microsoft Copilot app only when
  Microsoft 365 Copilot and Microsoft Copilot are both installed, the app was not user-installed, and it has
  not been launched in the last 28 days; Enterprise, Pro and Education SKUs only. [DOC S-2ypn2ron] GA
- `TurnOffWindowsCopilot` is marked **deprecated** in the CSP ("may be removed in a future release") and
  explicitly does not apply to the newer Copilot experience rolling out to Windows 11/10. [DOC S-2ypn2ron] deprecated

## Reference
- `agents/foundry-agent-service.md` — the cloud-hosted Foundry Agent Service and Windows 365 for Agents
  (Entra agent identities, Cloud PC pools, session isolation); this article covers the on-device counterpart
  (ODR, Copilot Actions, Foundry Local) that runs on the user's own PC instead of a pooled Cloud PC.
- `mcp/registry-and-extensions.md` — the vendor-neutral MCP Registry (`registry.modelcontextprotocol.io`,
  `server.json`, `mcp-publisher`) and the extensions framework; the Windows ODR is a separate, OS-local
  registry for discovering and containing MCP servers on a single device, not an alternative implementation
  of the public registry. See that article's Reference for the back-link to this one.
- `mcp/transports-stdio.md` — the stdio transport an ODR-registered local MCP server uses when run as a child
  process (`odr mcp run`); this article does not re-document stdio framing, only Windows-specific packaging,
  containment and discovery. See that article's Reference for the back-link to this one.
- `security/ai-agent-guidelines.md` — general AI-agent/MCP security control mapping (NIST AI RMF, ISO 42001,
  Claude Code managed MCP); the agent-account/agent-workspace isolation model here is the Windows-specific
  implementation of the same "contain and least-privilege the agent" principle. See that article's Reference
  for the back-link to this one.
- `entra/agent-id.md` — the Microsoft Entra agentic identity model; Copilot Actions' local agent accounts are
  distinct from Entra agent identities, though Microsoft states Entra/MSA identity support for on-device agents
  is planned.

## Examples
List and inspect MCP servers registered with the Windows on-device agent registry on PL-LT-00123:

- SNIPPET: list, register and configure MCP servers with the Windows on-device agent registry CLI;
  context: `odr.exe`, Windows on-device MCP registry (preview); checked: no [DOC S-22dvomdp: `odr mcp
  list`, `odr mcp add <manifest file path>`, `odr mcp configure <server id>`]
```cmd
odr mcp list
odr mcp add C:\ProgramData\corp.example.com\mcp\file-tools\manifest.json
odr mcp configure file-tools
```

Restrict which MCP server/host connections an agent may use via Intune custom OMA-URI (tenant
`00000000-0000-0000-0000-000000000000`), targeting the device-scope CSP node:

- SNIPPET: an Intune custom OMA-URI restricting agent MCP server/host connections to an allow-listed
  connector; context: Policy CSP `WindowsAI\AgentConnectorAccessPolicy`, device-only, Windows Insider
  Preview; checked: no [DOC S-w7egu7gh: CSP node path and its JSON allow-list value]
```
OMA-URI: ./Device/Vendor/MSFT/Policy/Config/WindowsAI/AgentConnectorAccessPolicy
Data type: String (XML)
Value: {"allow":["io.github.contoso/file-tools"]}
```

Run a local model interactively with the Foundry Local CLI, then check the local endpoint:

- SNIPPET: install the Foundry Local CLI, chat with a local model interactively, and show the local
  endpoint URL; context: Foundry Local CLI (preview), Windows; checked: no [DOC S-msz6m5qt: `winget
  install Microsoft.FoundryLocal`; DOC S-onenhsl2: `foundry chat <alias>`, `foundry server status`]
```powershell
winget install Microsoft.FoundryLocal
foundry chat phi-4-mini
foundry server status   # shows the local endpoint URL
```

Block Recall on managed devices and cap snapshot retention, via Intune custom OMA-URI:

- SNIPPET: an Intune custom OMA-URI disabling Recall snapshot capture; context: Policy CSP
  `WindowsAI\AllowRecallEnablement`; checked: no [DOC S-2ypn2ron: CSP node path and integer value type]
```
OMA-URI: ./Device/Vendor/MSFT/Policy/Config/WindowsAI/AllowRecallEnablement
Data type: Integer
Value: 0
```
