---
topic: security/threat-model-inputs
priority: P2
applies_to: "STRIDE; LINDDUN; Microsoft Threat Modeling Tool; MITRE ATT&CK v19.2 (2026-08-06)"
retrieved_utc: 2026-09-26
sources: [S1564, S1565, S1566, S1567, S1568, S1569, S1570, S1571, S1572, S1573, S1574, S1576]
status: complete
files: [security/artifacts/mitre/attack-subset.csv, security/artifacts/mitre/attack-subset.md]
---

# Threat-modeling method and ATT&CK technique inputs

## Summary
Method references (STRIDE, LINDDUN, Microsoft Threat Modeling Tool) and seven ATT&CK techniques relevant to
a device-management tool's management-plane and identity surface, each with the component it touches, its official mitigation
ids (`M####`) and detection-strategy ids (`DET####`, with their analytic ids and log sources). Detailed threats
for the identity/auth surface already live in `auth/threats.md`; this file does not duplicate the narrative,
only adds the ATT&CK ids not already covered there and the modeling-method metadata. ATT&CK version at retrieval:
v19.2, released 2026-08-06 [DOC S1564]. Full mitigation/detection rows are in
`security/artifacts/mitre/attack-subset.csv`, extracted from the pinned STIX bundle (tag `v19.2`) rather than
retyped by hand [DOC S1576]. T1562 "Impair Defenses" is revoked in the v19.2 data model and replaced by T1685
"Disable or Modify Tools" — see Facts.

## Facts
- STRIDE (Spoofing, Tampering, Repudiation, Information disclosure, Denial of service, Elevation of privilege) is
  a threat-categorization mnemonic; OWASP's threat-modeling process page lists the six categories with a description
  and a security control for each. [DOC S1572] The Microsoft Threat Modeling Tool below applies it per element. [DOC S1574]
- LINDDUN (Linking, Identifying, Non-repudiation, Detecting, Data Disclosure, Unawareness, Non-compliance) is a privacy-focused
  threat-modeling method with a catalog of privacy threat types, threat trees, mitigation strategies and tool
  support, developed and maintained by KU Leuven's DistriNet research unit. [DOC S1573]
- The Microsoft Threat Modeling Tool is a core element of the Microsoft SDL, built for non-security experts; it
  gives guidance while drawing a model, guided STRIDE-per-element analysis of threats and mitigations, and reporting. [DOC S1574]
- T1072 Software Deployment Tools: adversaries may use centralized software suites (configuration management and
  software deployment, e.g. SCCM, Intune, Azure Arc) to execute commands and move laterally; SaaS-based services
  can also run commands on on-premises endpoints. Component touched: ConfigMgr baselines/Run Scripts, which is exactly this
  class of tool. [DOC S1565]
- T1484 Domain or Tenant Policy Modification: adversaries may modify domain or identity-tenant settings (e.g. AD
  GPOs, domain or federation trusts) to evade defenses or escalate privileges. Component touched:
  policy-precedence surface (GPO vs DSC vs MDM, see `security/policy-precedence.md`, part A). [DOC S1566]
- T1098 Account Manipulation: adversaries may add credentials, permissions or group memberships to maintain
  access. Component touched: the identity/RBAC surface covered in `auth/threats.md` — not duplicated here.
  [DOC S1567]
- T1558 Steal or Forge Kerberos Tickets: covers Kerberoasting, forged tickets (golden/silver), and related abuse
  of Kerberos authentication. Component touched: the interactive identity used for AdminService/Graph calls;
  already covered in `auth/threats.md` and `auth/kerberos.md` — not duplicated here. [DOC S1568]
- T1078 Valid Accounts: use of legitimate credentials (default, local, domain or cloud) to gain and maintain
  access, evading detections aimed at malware. Component touched: the engineer's delegated identity and any
  scheduled-job read-only identity; already covered in `auth/threats.md`. [DOC S1569]
- T1219 Remote Access Tools: legitimate remote-access tools
  used as an interactive command-and-control channel or for redundant access; installing them may add persistence. Component touched: not a direct function of a device-management tool, but relevant to the admin-workstation hardening
  covered in `management-plane-hardening.md` (part B). [DOC S1570]
- T1562 Impair Defenses: disabling or modifying security tools, including Defender exclusions and tampering
  protection bypass. In the v19.2 STIX data this technique id is revoked and replaced by T1685 "Disable or Modify
  Tools", which carries the current mitigations/detections. [DOC S1571][DOC S1576] Component touched:
  read-only visibility into Defender machine state (design scope); a tool built this way does not itself
  disable defenses (tier ≤3 only).
- Mitigation and detection-strategy ids for all 7 techniques (3-10 mitigations and one detection strategy with
  2-7 analytics each) are in `attack-subset.csv`; not retyped here to avoid transcription drift from the pinned
  bundle. [DOC S1576]

## Reference

| Technique | Name | Component | Mitigation ids (M####) | Detection strategy id (DET####) | Source |
|---|---|---|---|---|---|
| T1072 | Software Deployment Tools | ConfigMgr baselines / Run Scripts | M1029,M1033,M1017,M1030,M1027,M1018,M1026,M1032,M1015,M1051 (10) | DET0223 (5 analytics) | S1565,S1576 |
| T1484 | Domain or Tenant Policy Modification | GPO/DSC/MDM policy precedence (see policy-precedence.md, part A) | M1018,M1026,M1047 (3) | DET0270 (2 analytics) | S1566,S1576 |
| T1098 | Account Manipulation | identity/RBAC (see auth/threats.md) | M1028,M1030,M1018,M1022,M1026,M1032,M1042 (7) | DET0096 (6 analytics) | S1567,S1576 |
| T1558 | Steal or Forge Kerberos Tickets | interactive identity (see auth/threats.md, auth/kerberos.md) | M1015,M1043,M1041,M1027,M1047,M1026 (6) | DET0522 (3 analytics) | S1568,S1576 |
| T1078 | Valid Accounts | engineer + scheduled-job identities (see auth/threats.md) | M1013,M1017,M1027,M1018,M1026,M1032,M1015,M1036 (8) | DET0560 (5 analytics) | S1569,S1576 |
| T1219 | Remote Access Tools (renamed from "Remote Access Software") | admin workstation (see management-plane-hardening.md, part B) | M1031,M1037,M1034,M1038,M1042 (5) | DET0496 (3 analytics) | S1570,S1576 |
| T1562 → T1685 (revoked/replaced) | Impair Defenses → Disable or Modify Tools | Defender read-only visibility; the tool does not disable defenses (tier <=3) | M1038,M1018,M1022,M1024,M1054,M1047,M1042 (7) | DET0497 (7 analytics) | S1571,S1576 |

Full id lists, analytic ids and named log sources per detection strategy are in
`security/artifacts/mitre/attack-subset.csv` (machine-readable, extracted from the pinned STIX bundle). Only
ids/names/mitigations/detections are recorded — no attack procedures, tooling or payloads, per the "defensive
only" rule.

## Examples
Not applicable (reference list); device examples use `PL-LT-00123` / `corp.example.com` as elsewhere in the kb.
