---
topic: agents/gitops-for-agents
priority: P3
applies_to: "OpenGitOps Principles and Glossary (open-gitops/documents at commit 747050b5); applied to Claude Code agent configuration (settings, CLAUDE.md, .mcp.json, skills, managed settings)"
retrieved_utc: 2026-10-14
sources: [S-43ycwzdw, S-5pzuphp4, S2057, S-rfpmkpck, S2158, S2042, S1802, S-fzkqxhmg]
status: partial
---

# GitOps for agent configuration

## Summary
OpenGitOps (a CNCF working group) defines GitOps as four principles for a system's desired state: declarative, versioned and immutable, pulled automatically, and continuously reconciled by software agents. Its glossary leaves persistent application data out of the desired state and asks the state store (git, canonically) for access control and auditing. Claude Code's project files (`.claude/settings.json`, `CLAUDE.md`, `.mcp.json`, skills, subagents) are declarative and can live in git, and Claude Code reloads several of them into a running session. Nothing in Claude Code itself pulls them from git, though, and local and user files can drift from the committed state. Only managed settings outrank every other layer. Agent memory, transcripts and task lists are runtime data, not desired state.

## Facts

### OpenGitOps principles and terms
- GitOps is defined as a set of principles for operating and managing software systems, rooted in widely adopted practice; the desired state of a GitOps-managed system must meet four principles. [DOC S-43ycwzdw]
- Principle 1, Declarative: the system's desired state is expressed declaratively; principle 2, Versioned and Immutable: it is stored so that immutability and versioning are enforced and a complete version history is kept. [DOC S-43ycwzdw]
- Principle 3, Pulled Automatically: software agents pull the desired state declarations from the source; principle 4, Continuously Reconciled: they keep observing the actual state and attempt to apply the desired state. [DOC S-43ycwzdw]
- The desired state is all configuration data sufficient to recreate the system so that instances behave indistinguishably; it generally excludes persistent application data such as database contents, though it often includes the credentials or recovery configuration for that data. [DOC S-5pzuphp4]
- A state store holds immutable versions of the desired state and should provide access control and auditing on changes to it; git is the canonical example, but any system meeting the criteria may serve. [DOC S-5pzuphp4]
- Pull is required rather than push so that agents can read the desired state at any time; unlike CI/CD's pre-set triggers, reconciliation runs whenever actual state diverges, whether by drift or by an intentional change. [DOC S-5pzuphp4]
- "Continuous" means reconciliation keeps happening, not that it is instantaneous; drift is actual state moving away from the desired state. [DOC S-5pzuphp4]
- A GitOps-managed software system includes its runtime environments, the management agents within each, and policies controlling access to and management of repositories, deployments and runtimes. [DOC S-5pzuphp4]

### Applied to Claude Code agent configuration
- Claude Code's shared project configuration is a set of declarative files that can be committed with the code: `.claude/settings.json`, `CLAUDE.md`, `.mcp.json` for team MCP servers, and `.claude/skills/`, `.claude/agents/` and `.claude/rules/`. A repository can therefore hold an agent's configuration under principles 1 and 2. [DER S2057, S-rfpmkpck, S-43ycwzdw: project-scope files are plain JSON/Markdown in the repository; principles 1 and 2 ask for declarative, versioned state]
- Claude Code reloads changed settings files into a running session, watches skill directories for edits, reloads a file-based `managed-settings.json` when it changes, checks MDM policy every 30 minutes and polls server-managed settings hourly. These apply a changed declaration to a running agent, but only from the files already on disk; nothing in Claude Code pulls the repository itself. [DER S2057, S2158, S2042, S-43ycwzdw: reload and poll intervals as documented; principle 3 asks agents to pull from the source]
- Project settings are not the highest layer: `.claude/settings.local.json`, `--settings` and managed settings override `.claude/settings.json`. A developer's local file is therefore drift from the committed state, and only managed settings (server-managed, MDM or `managed-settings.json`) win over every layer. [DER S2057, S-5pzuphp4: settings precedence; drift is actual state moving away from desired state]
- Policy that must not drift belongs in managed settings rather than the repository: the dev container page itself warns that anyone with write access can remove a Dockerfile step that installs `managed-settings.json`, and points to server-managed settings or MDM instead. [DER S-fzkqxhmg, S-5pzuphp4: repository writers can remove the step; the state store should control access to changes]
- Claude Code's GitLab CI/CD integration (marked beta, maintained by GitLab) runs each task in a container and sends every change through a merge request, so reviewers see the diff and approvals still apply. That is the review gate the state-store definition asks for, applied to the agent's output. [DOC S1802]
- Agent memory (auto-memory, subagent memory directories), session transcripts and team task lists are runtime data rather than desired state: the glossary keeps persistent application data out of the desired state, so these belong in backed-up storage, not in the reconciled configuration. [DER S-5pzuphp4, S2057: desired state excludes persistent application data; these files are written by sessions at run time]
- No page read from Anthropic or Microsoft describes GitOps for agent configuration as such, or a reconciler that pulls Claude Code configuration from git onto workstations. [UNK: looked in code.claude.com docs search and the OpenGitOps documents, 2026-10-14]

## Reference
- OpenGitOps principles: https://raw.githubusercontent.com/open-gitops/documents/747050b51302be3c0762a817fb912c2685cd3b2d/PRINCIPLES.md
- OpenGitOps glossary: https://raw.githubusercontent.com/open-gitops/documents/747050b51302be3c0762a817fb912c2685cd3b2d/GLOSSARY.md
- Related: `claude/settings-and-scopes.md` (settings layers, precedence, managed delivery), `claude/ci-and-headless.md` (GitLab CI flow, dev containers), `agents/docs-maintenance-agents.md` (committing machine-written data from automation).

## Examples
- A repository holds `.claude/settings.json`, `.mcp.json` and `.claude/skills/` and changes them only through reviewed merge requests, while the deny rules every engineer on `PL-LT-00123` must keep come from server-managed settings, which outrank the repository's files. [DER S2057, S1802: precedence puts managed settings above project settings; changes reach the repository through merge requests]
