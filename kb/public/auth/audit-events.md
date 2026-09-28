---
topic: auth/audit-events
priority: P1
applies_to: "AD DS, Entra ID, Microsoft Graph, ConfigMgr, SQL Server, GitLab"
retrieved_utc: 2026-09-28
sources: [S1357, S1358, S1359, S1360, S1361, S1362, S1363, S1364, S1365, S1366, S1367, S1368, S1369, S1370, S1371, S1372, S1373, S1374, S-2lkr2v7m, S-vudqagwn, S-2gxpfnjz, S-rm7qmev7, S-srnmxykl, S-h2gj3bko, S-fzswb76a, S-mubyxer3, S-m2yttazv]
status: complete
---

## Summary
Full table now in `audit-events.csv`: Windows Security-log event ids for logon, Kerberos, NTLM fallback and
account/group-management auditing; the four Entra sign-in log categories (interactive, non-interactive,
service principal, managed identity) plus the directory audit log; ConfigMgr's audit status messages;
SQL Server Audit action groups for login and role/object access; GitLab audit events and their tier gate.
The Microsoft Graph activity logs row is sourced from its Learn page.

## Facts
- Microsoft Graph activity logs record every HTTP request the Graph service processes for the tenant (caller app, service principal or user, method, URI, status, scopes and roles), sent through Entra diagnostic settings to Log Analytics, Storage or Event Hubs; they need Entra ID P1/P2, and delivery is usually within 30 minutes, sometimes up to 2 hours. [DOC S-m2yttazv]
- Windows's `Audit Security Group Management` subcategory covers the create/change/delete/member-add/
  member-remove events for local (4731-4735), global (4727-4730, 4737) and universal (4754-4758) security
  groups; 4728/4729 are the global-group member add/remove events, 4732/4733 the local-group ones, and
  4756/4757 the universal-group ones -- the global and universal variants have the same fields, XML and
  recommendations as the local-group events, differing only by group type, and are generated only for
  domain groups. [DOC S1363]
- `Audit User Account Management` covers account create/enable/disable/delete/change/lock-out/unlock (4720,
  4722, 4725, 4726, 4738, 4740, 4767), rename (4781), password change/reset attempts (4723, 4724), SID
  History (4765, 4766), the ACL set on members of administrators groups (4780) and the DSRM administrator
  password (4794); some of these (4722, 4724, 4725, 4781) are also generated for computer accounts, not
  just user accounts. [DOC S1364]
- `Audit Logon` records 4624 (an account logged on) and 4625 (logon failure). Credential validation, including
  NTLM validation of domain accounts, is 4776 under `Audit Credential Validation`, logged by the authoritative
  computer (the DC for domain accounts); `Audit Other Account Logon Events` contains no events and is reserved
  for future use. [DOC S1367, S-vudqagwn, S1368]
- `Audit Kerberos Authentication Service` covers 4768 (TGT requested) and 4771 (Kerberos pre-authentication
  failed); `Audit Kerberos Service Ticket Operations` covers 4769 (service ticket requested) -- these are
  the DC-side events a workstation client's Kerberos authentication to AdminService/SQL would generate.
  [DOC S1365, S1366]
- `Audit Directory Service Changes` (event 5136) can record the old and new properties of a modified AD
  object and generates events only for objects with a configured SACL, on domain controllers only;
  `Audit Directory Service Access` (event 4662, "an operation was performed on an object") is generated
  only when a matching SACL is set on the AD object, and its Properties field lists the classes or
  property sets operated on; so security-sensitive groups need an explicit SACL to get 5136/4662 coverage
  beyond the simpler 4728/4729/4732/4733/4756/4757 events. [DOC S1369, S1370, S-2lkr2v7m]
- With the three `Network security: Restrict NTLM` audit policies enabled, NTLM use is logged to the
  dedicated `Applications and Services Logs > Microsoft > Windows > NTLM > Operational` channel, separate
  from the Security log: events 8001-8006 (8001 outgoing on the client; 8002 incoming without DC validation;
  8003 member server with a domain account; 8004-8006 on domain controllers), replaced by 4001-4006 once
  blocking is enforced. Windows 11 24H2 / Server 2025 add richer events (4020, 4022, 4030, 4032 for use;
  4021, 4023, 4031, 4033 for blocks) that also record why NTLM was chosen. [DOC S1371]
- Microsoft Entra ID's Sign-in events page has four distinct log categories -- interactive user,
  non-interactive user, service principal, and managed identity sign-ins -- surfaced separately because a
  `client` engineer's interactive Kerberos/MSAL sign-in, a `site` instance's app-only certificate sign-in,
  and any managed-identity-based sign-in (Appendix A / Arc, if ever adopted) land in different log
  categories that must each be watched. [DOC S1360, S1361, S1362]
- The sign-in logs preview has four log types (interactive user, non-interactive user, service principal,
  managed identity); the legacy sign-in log experience shows only interactive user sign-ins. Managed identity
  sign-ins are aggregated into one row per managed identity, status and resource, and sign-in log entries are
  system generated and can't be changed or deleted. [DOC S-h2gj3bko, S-fzswb76a]
- Each sign-in log entry shows whether continuous access evaluation (CAE) was applied; one authentication makes
  several sign-in requests and CAE shows true on only one of them, on the interactive or the non-interactive tab.
  The correlation ID groups the sign-ins of one session but comes from client parameters, so its accuracy is not
  guaranteed; the request ID corresponds to an issued token. [DOC S1358]
- Directory changes (group, role, application, service principal and user operations) land in the Entra
  directory audit log, whose `activityDisplayName` values are listed in the audit activity reference; programs
  read both logs through Microsoft Graph `auditLogs/directoryAudits` and `auditLogs/signIns`. [DOC S1359, S-mubyxer3]
- ConfigMgr's audit status messages (`SMS_StatusMessage.MessageType` 768) are a trail of actions taken
  by the ConfigMgr administrator, including operations that add, modify or delete objects, and the SMS
  Provider generates them automatically. [DOC S-2gxpfnjz]
- Status messages are read by querying the SMS Provider for `SMS_StatusMessage` instances [DOC S1372];
  the console's Status Message Queries show when an object was modified and the account used (for
  example the built-in "Collections Created, Modified, or Deleted" query). [DOC S-rm7qmev7] The
  specific numeric id ranges most audit actions fall into (commonly cited as beginning around 30000) come
  from Microsoft-authored TechCommunity guidance rather than a single enumerated Learn reference table, so
  that detail is tagged `COMMUNITY` here pending a primary source. [COMMUNITY S1373]
- SQL Server Audit action groups `SUCCESSFUL_LOGIN_GROUP` / `FAILED_LOGIN_GROUP` record logins,
  `SERVER_ROLE_MEMBER_CHANGE_GROUP` and `DATABASE_ROLE_MEMBER_CHANGE_GROUP` record role membership changes, and
  `SCHEMA_OBJECT_ACCESS_GROUP` records the use of an object permission; an audit writes to a file, the Windows
  Security log or the Windows Application log. [DOC S1357, S-srnmxykl]
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
