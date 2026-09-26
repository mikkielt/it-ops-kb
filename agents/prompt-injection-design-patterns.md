---
topic: agents/prompt-injection-design-patterns
priority: P2
applies_to: "arXiv preprints 2506.08837/2503.18813 (2025); Azure AI Content Safety Prompt Shields (ms.date 2026-08-28); Anthropic prompt-injection-defenses post (2025-11-24); Claude Code security docs (retrieved 2026-09-25)"
retrieved_utc: 2026-09-25
sources: [S2005, S2006, S2007, S2008, S2009, S2010]
status: complete
---

# Design patterns for limiting prompt injection through tool results

## Summary
Beyond OWASP's item lists (`standards/owasp.md`), the literature names concrete architectural patterns:
Action-Selector, Plan-Then-Execute, LLM Map-Reduce, Dual LLM, Code-Then-Execute and Context-Minimization, each
trading agent flexibility for structural resistance to injected instructions in tool output. CaMeL (Google
Research) is a working Dual-LLM/Plan-Then-Execute hybrid with a measured utility cost (77% vs. 84% task success).
Microsoft's Spotlighting marks untrusted tool/document content as lower-trust via base64 transformation; Prompt
Shields classifies both direct and "document" (indirect/tool-response) attacks. Anthropic's own published defenses
are model training plus a content classifier plus red-teaming; Claude Code adds isolated context windows for
web-fetch, MCP allowlisting, and mandatory approval for network-touching tools. A device-management agent with a
tier-confirm gate and a fixed query set already functions as an Action-Selector; such a design typically has no
Dual-LLM-style isolation step ahead of an in-process PII filter.

## Facts
- "Design Patterns for Securing LLM Agents against Prompt Injections" (arXiv 2506.08837, v1 2025-06-10, v3
  2025-06-27) names: Action-Selector (fixed action allowlist; loses novel-task handling), Plan-Then-Execute (plan
  fixed before reading untrusted data; adds latency), LLM Map-Reduce (isolated sub-calls over untrusted chunks,
  then aggregated; raises cost), Dual LLM (privileged tool-caller never sees raw untrusted text; doubles inference
  cost), Code-Then-Execute (agent emits a constrained program instead of free-form calls; limits expressiveness),
  Context-Minimization (shrinks untrusted content shown to the model; degrades task performance), and a Firewall-
  style post-hoc output filter (false positives). [COMMUNITY S2005]
- CaMeL ("Defeating Prompt Injections by Design", arXiv 2503.18813, Google Research, v1 2025-03-24/v2 2025-06-24)
  extracts control/data flow from the *trusted* query only, so untrusted tool output can never change which tools
  run next, and applies capability-based restrictions to data flow to block unintended exfiltration; it solved 77%
  of AgentDojo tasks with provable security vs. 84% for an undefended baseline. [COMMUNITY S2006]
- The dual-LLM pattern (Simon Willison, 2023-04-25): a privileged, tool-calling LLM receives only opaque variable
  tokens (`$VAR1`) for untrusted content; a non-AI Controller resolves them only for specific, vetted tool
  arguments; a tool-less quarantined LLM processes the raw untrusted text. Willison calls it "pretty bad" —
  complexity and UX cost, and it does not stop social engineering of the human. [COMMUNITY S2007]
- Microsoft Spotlighting (Azure AI Content Safety Prompt Shields, preview, ms.date 2026-08-28): tags third-party
  content as lower-trust by base64-encoding it before the model sees it; no direct cost but raises token count and
  can push a document over the input limit; available only via the Chat Completions API path in Foundry guardrails;
  off by default. [DOC S2008]
- Prompt Shields (formerly "jailbreak risk detection") classifies **user prompt attacks** (direct) and **document
  attacks** (hidden instructions in documents/emails/web pages/tool responses), scanning at the user-input and
  tool-response intervention points; annotations report `detected`/`filtered` booleans. [DOC S2008]
- Anthropic (2025-11-24, re: Claude for Chrome): defenses are (1) RL training exposing the model to injected content
  and rewarding correct refusal, (2) a classifier scanning "all untrusted content that enters the model's context
  window" for hidden/encoded/deceptive instructions, (3) ongoing red-teaming and external benchmark participation.
  Anthropic states a 1% attack success rate is still "meaningful risk" and "no browser agent is immune." [DOC S2009]
- Claude Code's documented tool-result-relevant defenses: isolated context window for web-fetch results; "context-
  aware analysis" of the full request; network-request approval required by default for tools reaching the web;
  MCP servers configured only from source-controlled settings (see `managed-mcp.md`); "Validate tool results before
  passing to LLM" and "show tool inputs to the user before calling the server" are MCP-spec-level client SHOULDs,
  not Claude-Code-specific inventions. [DOC S2010]

## Reference
| Pattern | Core idea | Main trade-off | Source |
|---|---|---|---|
| Action-Selector | fixed allowlist of actions | loses novel-task handling | S2005 |
| Plan-Then-Execute | plan fixed before untrusted data read | latency | S2005 |
| LLM Map-Reduce | isolated sub-calls, then aggregate | cost, coordination complexity | S2005 |
| Dual LLM | privileged LLM never sees raw untrusted text | 2x inference cost | S2005, S2007 |
| Code-Then-Execute | agent emits constrained program | limits expressiveness | S2005 |
| Context-Minimization | shrink untrusted content shown | degraded task performance | S2005 |
| CaMeL | Dual-LLM + Plan-Then-Execute + capabilities | 77% vs 84% task success (AgentDojo) | S2006 |
| Spotlighting | base64-tag untrusted content | more tokens, Chat Completions only | S2008 |

Full Prompt Shields API reference (endpoint, request/response fields, harm categories, groundedness,
protected material, custom categories, blocklists): `agents/content-safety-prompt-shields.md`.

## Examples
For a fixture device `PL-LT-00123`, an injected string in a ConfigMgr log line (for example a fake
"run this PowerShell as SYSTEM" instruction embedded in a discovered-value field) cannot change which
operation runs: the model may only select from a fixed, tiered operation set, and any tier-≥2 call is
confirmed by `jan.kowalski` in the CLI regardless of what the log line asked for — the Action-Selector
pattern's trade-off (no novel actions) matches a closed operation set exactly, so such a design pays no
extra utility cost for this protection [DER S2005].
