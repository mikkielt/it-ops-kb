---
topic: auth/audit-events
priority: P1
applies_to: "AD DS, Entra ID, Microsoft Graph, ConfigMgr, SQL Server, GitLab"
retrieved_utc: 2026-09-24
sources: [S1357, S1358, S1359, S1360, S1361, S1362, S1363, S1364, S1365, S1366, S1367, S1368, S1369, S1370, S1371, S1372, S1373, S1374, S1347]
status: complete
---

## Summary
Full table now in `audit-events.csv`: Windows Security-log event ids for logon, Kerberos, NTLM fallback and
account/group-management auditing; the four Entra sign-in log categories (interactive, non-interactive,
service principal, managed identity) plus the directory audit log; ConfigMgr's audit status messages;
SQL Server Audit action groups for login and role/object access; GitLab audit events and their tier gate.
One row (Microsoft Graph activity logs) stays `[UNK]` -- no dedicated Learn page was fetched by this agent
for it; it belongs to the base kb's `graph/` topic.

## Facts
- Windows's `Audit Security Group Management` subcategory covers the create/change/delete/member-add/
  member-remove events for local (4731-4735), global (4727-4730, 4737) and universal (4754-4758) security
  groups; 4728/4729 are the global-group member add/remove events, 4732/4733 the local-group ones, and
  4756/4757 the universal-group ones -- all four SID-scope variants share the same event schema, differing
  only by group type. [DOC S1363]
- `Audit User Account Management` covers account create/enable/disable/delete/change/lock/unlock (4720,
  4722, 4725, 4726, 4738, 4740, 4767) and password/SID-history/ACL events (4723, 4724, 4765, 4766, 4780,
  4781, 4794); some of these (4722, 4724, 4725, 4781) are also generated for computer accounts, not just
  user accounts. [DOC S1364]
- `Audit Kerberos Authentication Service` covers 4768 (TGT requested) and 4771 (Kerberos pre-authentication
  failed); `Audit Kerberos Service Ticket Operations` covers 4769 (service ticket requested) -- these are
  the DC-side events a workstation client's Kerberos authentication to AdminService/SQL would generate.
  [DOC S1365, S1366]
- `Audit Directory Service Changes` (event 5136) records the old and new values of a modified AD attribute,
  and `Audit Directory Service Access` (event 4662) records per-object/per-property access; both need a
  SACL configured on the object, so security-sensitive groups need an explicit SACL to get 5136/4662
  coverage of membership changes beyond the simpler 4728/4729/4732/4733/4756/4757 events. [DOC S1369, S1370]
- Windows 11 24H2 / Server 2025's NTLM auditing writes to the dedicated
  `Applications and Services Logs > Microsoft > Windows > NTLM > Operational` channel (events 8001-8004:
  outgoing-NTLM-would-be-blocked audit, incoming-NTLM-would-be-blocked audit on a member server, and the
  domain-controller equivalent), separate from the main Security log. [DOC S1371]
- Microsoft Entra ID's Sign-in events page has four distinct log categories -- interactive user,
  non-interactive user, service principal, and managed identity sign-ins -- surfaced separately because a
  `client` engineer's interactive Kerberos/MSAL sign-in, a `site` instance's app-only certificate sign-in,
  and any managed-identity-based sign-in (Appendix A / Arc, if ever adopted) land in different log
  categories that must each be watched. [DOC S1360, S1361, S1362]
- ConfigMgr's audit status messages are generated automatically by the SMS Provider whenever an
  administrative user's action adds, modifies or deletes an object; they are queryable as
  `SMS_StatusMessage` WMI instances or through the console's Status Message queries. [DOC S1372] The
  specific numeric id ranges most audit actions fall into (commonly cited as beginning around 30000) come
  from Microsoft-authored TechCommunity guidance rather than a single enumerated Learn reference table, so
  that detail is tagged `COMMUNITY` here pending a primary source. [COMMUNITY S1373]
- GitLab's sign-in audit events are available on every tier; group- and project-level audit events (the
  kind that would show a security-relevant membership or protected-branch change) need GitLab Premium or
  Ultimate. [DOC S1374]

## Reference
See `audit-events.csv`.
- `auth/audit-log-apis.md` — how to retrieve/export these events programmatically: Office 365 Management
  Activity API subscriptions, Purview `Search-UnifiedAuditLog`/Graph Audit Search, Intune `auditEvents`, and
  Entra `directoryAudits`/`signIns` retention and diagnostic-settings export.

## Examples
No fixture-specific configuration; mechanism-only facts.
