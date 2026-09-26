---
topic: auth/enterprise-access-model
priority: P2
applies_to: "Microsoft Enterprise Access Model (current guidance)"
retrieved_utc: 2026-09-26
sources: [S1210, S1212, S1224, S1225, S1226]
status: partial
---

# Enterprise access model: tiering, PAWs, LAPS, KB5014754, and ConfigMgr

## Summary
- Microsoft's enterprise access model defines a control plane (Tier 0), management plane, and data/workload plane, and treats privileged access workstations (PAWs) and Windows LAPS as universal controls; it does not, in the pages reviewed, explicitly name ConfigMgr/Intune/SCCM as Tier 0 assets — that stays a derived judgement.
- KB5014754's certificate strong-mapping enforcement reached **Full Enforcement mode on 2025-02-11**: domain controllers deny authentication for certificates that fail strong (secure) mapping, unless an admin has explicitly kept Compatibility mode (the option to return to it ended with the 2025-09-09 update, after which the StrongCertificateBindingEnforcement key is no longer supported) or moved to Enforcement mode earlier. [DOC S1224]

## Facts
- The enterprise access model organizes access control around a control plane, a management plane, and data/workload planes, replacing the older tiered administration model. [DOC S1210]
- Privileged access workstations (PAWs) are described as hardened, policy-enforced devices used for privileged/control-plane and management-plane administration, and are treated as control-plane infrastructure in their own right. [DOC S1210,S1225]
- Windows LAPS (Local Administrator Password Solution) automatically rotates and securely stores each device's local administrator password, backing up to Microsoft Entra ID (for Entra-joined devices) or AD (for domain-joined devices/servers), and is recommended for all workstations including PAWs. [DOC S1226]
- KB5014754 timeline: Compatibility mode began 2022-05-10 (audit only, no impact on existing certificates); **Full Enforcement mode began with the 2025-02-11 update** — authentication is denied for a certificate that fails strong-mapping criteria unless it was explicitly held back; the option to stay in Compatibility mode was removed with the 2025-09-09 update (the KB changelog of 2025-09-10 corrected the date from September 10). [DOC S1224]
- No page reviewed this session (S1210, S1212, S1225, S1226) makes an explicit "ConfigMgr/SCCM is Tier 0" statement; the enterprise access model defines Tier 0/control-plane generically by blast radius (systems whose compromise grants control of the environment), which a device-management/configuration-control system like ConfigMgr plausibly fits, but this remains a derived reading, not a documented Microsoft classification. [DER S1210 general definition; UNK for an explicit ConfigMgr statement]
- MFA for SMS Provider calls has been available since ConfigMgr current branch version 1702, as the concrete lever if an organization chooses to treat ConfigMgr as control-plane-equivalent. [DOC S1212]

## Reference
| Item | Fact | Tag |
|---|---|---|
| KB5014754 Compatibility mode start | 2022-05-10 | DOC |
| KB5014754 Full Enforcement start | 2025-02-11 | DOC |
| KB5014754 Compatibility mode option removed | 2025-09-09 update | DOC |
| Windows LAPS scope | Entra-joined and AD domain-joined devices, incl. servers | DOC |
| ConfigMgr named as Tier 0 by Microsoft | Not found | UNK |
| Windows LAPS policy settings, CSP nodes, events, schema | see `windows/laps.md` | DOC |

- `intune/certificates-pki.md` — how Intune SCEP/PKCS certificate profiles implement KB5014754 strong mapping (`OnPremisesSecurityIdentifier` SAN variable / connector registry flag), the certificate connector, and Microsoft Cloud PKI.

## Examples
- `PL-SRV-0042` (the SMS Provider host in the fixture estate) should carry a strongly-mapped certificate if certificate-based authentication is used anywhere in its chain, given KB5014754 Full Enforcement is already in effect as of this research date (2026-09-24).
