---
topic: agents/dataverse-mcp-server
priority: P2
applies_to: "Microsoft Dataverse MCP server (remote endpoint /api/mcp and preview endpoint /api/mcp_preview) and the clients that connect to it: Copilot Studio, GitHub Copilot in VS Code and Copilot CLI, Claude desktop, Claude Code; docs current 2026-10-08"
retrieved_utc: 2026-10-08
sources: [S-f6atlxlo, S-lv2haaxp, S-z3p44lkf, S-odxayrvf, S-evcdmlat, S-evy2xjad, S-oxdtvzaw]
status: complete
---

# Dataverse MCP server: what it is and how agents connect to it

## Summary
- Microsoft Dataverse can act as an MCP server that gives MCP clients access to tables and records; Microsoft names Copilot Studio agents, GitHub Copilot in Visual Studio Code, GitHub Copilot CLI, Claude desktop and Claude Code as clients. [DOC S-f6atlxlo]
- The remote server URL has the form `https://{dataverseOrgName}.crm.dynamics.com/api/mcp`; each environment has its own server and its own allowed-client list. [DOC S-f6atlxlo, S-oxdtvzaw]
- Before a client other than Copilot Studio can connect, a Power Platform administrator must allow that client for the environment in the Power Platform admin center; Copilot Studio is allowed by default. [DOC S-lv2haaxp]
- Three connection routes are documented: the Copilot Studio tool picker, a remote MCP entry in GitHub Copilot (VS Code or CLI), and, for non-Microsoft clients, either the `@microsoft/dataverse` local proxy or a direct connection with a custom Microsoft Entra app. [DOC S-f6atlxlo, S-odxayrvf, S-evcdmlat, S-z3p44lkf]

## Facts

### What the server is
- Microsoft describes the Dataverse MCP server as a centrally hosted, managed remote service, in contrast to local MCP setups that need an SDK, a proxy and manual environment access. [DOC S-f6atlxlo]
- The tool list on the overview page has fifteen tools: `search_data`, `search`, `create_record`, `update_record`, `delete_record`, `create_table`, `update_table`, `delete_table`, `read_query`, `describe`, `upsert_skill`, `delete_skill`, `init_file_upload`, `commit_file_upload`, `file_download`. [DOC S-f6atlxlo]
- `search_data` searches structured and unstructured data; `search` searches table schemas and business skills by keyword; `read_query` runs supported Dataverse SQL `SELECT` queries; `describe` returns details from search results for tables, records, schemas, skills and apps. [DOC S-f6atlxlo]
- `delete_record` and `delete_table` are described as deleting only after explicit user approval. [DOC S-f6atlxlo]
- `describe_table`, `list_tables` and `fetch` were removed and replaced by `describe`; the former `search` tool over data was renamed `search_data`, and the current `search` tool searches metadata. A client that keeps allow or deny lists by tool name must be updated. [DOC S-f6atlxlo, S-oxdtvzaw]
- `search_data` appears only when Dataverse search is enabled for the environment. [DOC S-oxdtvzaw]
- The server respects Dataverse security roles and row-level security: a user reaches only the tables and records their role permits, and no extra MCP-specific access control is needed. [DOC S-oxdtvzaw]
- Each environment can have its own server configuration; a client connects to several environments with one entry per environment URL, and Copilot Studio's MCP onboarding wizard can connect an agent to Dataverse MCP servers across environments. [DOC S-oxdtvzaw]

### Prerequisites and administration
- Changing the server's settings in the Power Platform admin center needs the Power Platform administrator role. [DOC S-lv2haaxp]
- Managing the server through advanced connector policies needs a Managed Environment. [DOC S-lv2haaxp]
- By default the Microsoft Copilot Studio client for Dataverse MCP is enabled in all environments; other clients must be enabled before they can connect. [DOC S-lv2haaxp]
- To enable other clients: Power Platform admin center, Manage, Environments, the environment, Settings, Product, Features, then under **Dataverse Model Context Protocol** make sure **Allow MCP clients to interact with Dataverse MCP server** is on, open **Advanced Settings**, open the client record (for example **Microsoft GitHub Copilot**), set **Is Enabled** to **Yes** and **Save & Close**. [DOC S-lv2haaxp]
- The allow-list applies only to the `/api/mcp` agent entry point; MCP-named custom APIs are ordinary Dataverse APIs and are not restricted by it. [DOC S-lv2haaxp]
- Clearing the **Allow MCP clients to interact with Dataverse MCP server** setting disables the server for the environment and stops every tool and agent that relies on it. [DOC S-lv2haaxp]
- Starting 2025-12-15, Dataverse MCP tools are charged when AI agents created outside Copilot Studio access them; Dynamics 365 Premium licences and a Microsoft 365 Copilot user subscription licence exempt access to Dynamics 365 data. `search_data` bills at the Tenant graph grounding Copilot Credit rate, and the other tools at the Text and generative AI tools (basic) per 10 responses rate. [DOC S-f6atlxlo, S-oxdtvzaw]

### Copilot Studio
- Prerequisite: the Microsoft Copilot Studio MCP client must be allowed in the environment, which is the default. [DOC S-odxayrvf, S-lv2haaxp]
- Steps: in Power Apps select the environment, Agents, Create new agent, then in the **Tools** section **+ Add tool**, **Model Context Protocol**, **Dataverse MCP Server**, and **Add to agent**; a Dataverse connection is requested when none exists. [DOC S-odxayrvf]
- The individual tools can be viewed and changed with **...**, **Edit** next to the tool. [DOC S-odxayrvf]
- Microsoft suggests testing with prompts such as "show me the tables in Dataverse", "describe the account table" or "how many accounts do I have". [DOC S-odxayrvf]

### GitHub Copilot in VS Code and Copilot CLI
- Prerequisites for VS Code: the **Microsoft GitHub Copilot** MCP client allowed in the environment, and VS Code with the GitHub Copilot extension. [DOC S-evcdmlat]
- VS Code steps: Command Palette, **MCP: Add Server**, **HTTP or Server Sent Events**, the instance URL with `/api/mcp` appended, a server name, **Global** or **workspace**, then agent mode in chat. The instance URL is under make.powerapps.com, Settings, Session details, Instance url. [DOC S-evcdmlat]
- Copilot CLI needs the **Microsoft GitHub Copilot** client allowed too; the server is added by hand in `~/.copilot/mcp-config.json` (global) or `.mcp/copilot/mcp.json` (project) as an `http` entry with url `<your org URL>/api/mcp`, then Copilot CLI is restarted. [DOC S-evcdmlat]
- A second CLI route is the Dataverse plugin from the Awesome Copilot marketplace, whose `/dataverse:mcp-configure` skill picks the environment and chooses between `/api/mcp` and `/api/mcp_preview`. [DOC S-evcdmlat]
- SNIPPET: Copilot CLI entry for the Dataverse MCP server; context: file `~/.copilot/mcp-config.json`, environment URL is a placeholder; checked: syntax [DOC S-evcdmlat]
```json
{
  "mcpServers": {
    "DataverseMcp": {
      "type": "http",
      "url": "https://yourorg.crm.dynamics.com/api/mcp"
    }
  }
}
```

### Claude desktop, Claude Code and other non-Microsoft clients
- Two approaches are documented: the local proxy (the `@microsoft/dataverse` npm package, which handles authentication and communication and is recommended for most non-Microsoft clients that can run local MCP servers) and the remote endpoint (`/api/mcp`, reached directly with a custom Microsoft Entra app). [DOC S-z3p44lkf]
- Prerequisites: the server enabled for the environment; for the local proxy, Node.js 18 or later; for the remote endpoint, permission to register an application in Microsoft Entra ID. [DOC S-z3p44lkf]
- Local proxy, step 1: a tenant administrator grants admin consent once per tenant for the Dataverse CLI app at `https://login.microsoftonline.com/{your-tenant-id}/adminconsent?client_id=<Dataverse CLI app id>`; the page states the app id, which this article does not repeat. [DOC S-z3p44lkf]
- Local proxy, step 2: in the admin center the **Dataverse CLI** client must have **Is Enabled** set to **Yes**; if it is missing from the list, a client entry with any name and the Dataverse CLI app id can be added. [DOC S-z3p44lkf]
- The proxy runs through `npx @microsoft/dataverse mcp <environment URL>` or after `npm install -g @microsoft/dataverse`; `--preview` points it at `/api/mcp_preview`. [DOC S-z3p44lkf]
- Claude desktop: File, Settings, Developer, Edit Config, add an `mcpServers` entry whose command is `npx` with args `-y`, `@microsoft/dataverse`, `mcp` and the environment URL, save, exit and reopen Claude desktop, sign in when prompted, and check the tools under **Search and tools**. Individual tools can be enabled or disabled per server there. [DOC S-z3p44lkf]
- Claude Code: `claude mcp add dataverse -t stdio -- npx -y @microsoft/dataverse mcp <environment URL>`, restart Claude Code, sign in when prompted and check the server's tools. With other MCP servers registered, naming *Dataverse* in the prompt picks this one. [DOC S-z3p44lkf]
- Remote endpoint, step 1: register an app in the Microsoft Entra admin center (App registrations, New registration) and note the Application (client) ID. [DOC S-z3p44lkf]
- Remote endpoint, step 2: under API permissions, Add a permission, Microsoft APIs, Dynamics CRM, select the **mcp.tools** permission. Which authentication flow the app uses depends on the MCP client. [DOC S-z3p44lkf]
- Remote endpoint, step 3: in the admin center add a client entry with that Application (client) ID, set **Is Enabled** to **Yes**, then point the client at `https://<your org URL>/api/mcp`, authenticating with the app's client ID. [DOC S-z3p44lkf]
- SNIPPET: Claude Code registration of the local proxy; context: Node.js 18 or later, Dataverse CLI client enabled and admin consent granted, environment URL is a placeholder; checked: no [DOC S-z3p44lkf]
```bash
claude mcp add dataverse -t stdio -- npx -y @microsoft/dataverse mcp https://yourorg.crm.dynamics.com
```
- SNIPPET: Claude desktop entry for the local proxy; context: file `claude_desktop_config.json`, friendly name and URL are placeholders; checked: syntax [DOC S-z3p44lkf]
```json
{
  "mcpServers": {
    "MyDataverseMCPServer": {
      "command": "npx",
      "args": ["-y", "@microsoft/dataverse", "mcp", "https://yourorg.crm.dynamics.com"]
    }
  }
}
```

### Preview endpoint
- `/api/mcp` carries the generally available tools; `/api/mcp_preview` adds preview tools, and preview does not need to be on to use the standard tool surface. [DOC S-evy2xjad, S-oxdtvzaw]
- An administrator turns preview on with **Allow MCP clients to interact with Dataverse MCP server (Preview version)** under the same Dataverse Model Context Protocol feature; once on, all users and copilots in the environment get the new tools, and the change can take a few minutes. [DOC S-evy2xjad]
- Copilot Studio uses a separate connector named **Microsoft Dataverse MCP Server (Preview)** for preview features; Claude, GitHub and other non-Microsoft clients use `https://<orgUrl>/api/mcp_preview`. [DOC S-evy2xjad]
- Preview tools are not covered by Microsoft support agreements, can change without notice and may not meet production reliability. [DOC S-evy2xjad]

### Troubleshooting
- For an authentication failure, confirm the environment URL in the client configuration (Power Apps, Settings, Session details) and that the client is enabled in the Power Platform admin center. [DOC S-oxdtvzaw]
- A tool error: rephrase the prompt more specifically, then check the user's Dataverse permissions for the operation. [DOC S-oxdtvzaw]
- Debug logging for the local proxy: add `--log-level Debug --log-file` to the `npx @microsoft/dataverse mcp` command; the log is written to the system temporary directory. [DOC S-oxdtvzaw]

## Reference

| Client | How it connects | Admin-center client to enable | Source |
| --- | --- | --- | --- |
| Copilot Studio | Add tool, Model Context Protocol, Dataverse MCP Server | Microsoft Copilot Studio (default on) | S-odxayrvf |
| GitHub Copilot in VS Code | MCP: Add Server, HTTP, `<instance URL>/api/mcp` | Microsoft GitHub Copilot | S-evcdmlat |
| GitHub Copilot CLI | `http` entry in `~/.copilot/mcp-config.json` | Microsoft GitHub Copilot | S-evcdmlat |
| Claude desktop | `npx @microsoft/dataverse mcp <URL>` in `claude_desktop_config.json` | Dataverse CLI | S-z3p44lkf |
| Claude Code | `claude mcp add dataverse -t stdio -- npx ...` | Dataverse CLI | S-z3p44lkf |
| Other non-Microsoft clients | Direct `/api/mcp` with a custom Entra app holding `mcp.tools` | A client entry with the app's client ID | S-z3p44lkf |

See also `agents/copilot-studio-mcp-client.md` for Copilot Studio's network path to MCP servers and `agents/coding-agents-mcp.md` for MCP configuration across coding-agent products.

## Examples
- A Claude Code user whose tenant has the Dataverse CLI client enabled and admin consent granted runs the `claude mcp add` line from the Facts, restarts, signs in and asks "describe the account table", one of the test prompts Microsoft suggests. [DER S-z3p44lkf: steps and test prompt from the non-Microsoft clients page]
