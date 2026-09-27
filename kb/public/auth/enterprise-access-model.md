---
topic: auth/enterprise-access-model
priority: P2
applies_to: "Microsoft Enterprise Access Model (current guidance)"
retrieved_utc: 2026-09-27
sources: [S1210, S1212, S1224, S1225, S1226, S-gigu3bqb, S-7nbamxyc]
status: complete
---

# Enterprise access model: tiering, PAWs, LAPS, KB5014754, and ConfigMgr

## Summary
- Microsoft's enterprise access model defines a control plane (Tier 0), management plane, and data/workload plane; PAW device guidance and Windows LAPS are separate pages; no page names ConfigMgr as Tier 0, but the AD DS tier model puts systems that patch or run agents on Tier 0 identity systems in Tier 0, so ConfigMgr's tier follows what it manages. [DER S1210, S-7nbamxyc]
- KB5014754's certificate strong-mapping enforcement reached **Full Enforcement mode on 2025-02-11**: domain controllers deny authentication for certificates that fail strong (secure) mapping, unless an admin has explicitly kept Compatibility mode (the option to return to it ended with the 2025-09-09 update, after which the StrongCertificateBindingEnforcement key is no longer supported) or moved to Enforcement mode earlier. [DOC S1224]

## Facts
- The enterprise access model organizes access around a control plane, a management plane and a data/workload plane, plus user access and app access pathways; it builds on the AD tier model: Tier 0 expands into the control plane, Tier 1 splits into the management and data/workload planes, and Tier 2 into user access and app access. [DOC S1210]
- A privileged access workstation (PAW) is the highest-security device profile, for extremely sensitive roles whose compromise would materially impact the organization: it removes local admin rights, blocks email and general web browsing (deny-by-default URL list), enforces application control, and uses Credential Guard and BitLocker. [DOC S1225]
- Windows LAPS (Local Administrator Password Solution) automatically rotates and backs up the password of a local administrator account, to Microsoft Entra ID (for Entra-joined devices) or AD (for AD-joined clients and servers); a hybrid-joined device backs up to one of the two, not both. [DOC S1226]
- Microsoft's legacy PAW guidance recommends LAPS to manage the local Administrator password on all workstations, including PAWs (it predates Windows LAPS and refers to legacy LAPS). [DOC S-gigu3bqb]
- KB5014754 timeline: Compatibility mode began 2022-05-10 (audit only, no impact on existing certificates); **Full Enforcement mode began with the 2025-02-11 update** — authentication is denied for a certificate that fails strong-mapping criteria unless it was explicitly held back; the option to stay in Compatibility mode was removed with the 2025-09-09 update (the KB changelog of 2025-09-10 corrected the date from September 10). [DOC S1224]
- The AD DS tier model (2026) puts in Tier 0 the systems that operate or manage Tier 0 identity systems, including backup, monitoring, patching, hypervisor, antivirus and EDR solutions; IT infrastructure management solutions that control Tier 1 servers are Tier 1; it warns against collapsing everything into Tier 0. [DOC S-7nbamxyc]
- So ConfigMgr is Tier 0 when it patches or has agents on domain controllers or other Tier 0 systems, and Tier 1 when it manages only member servers and workstations. [DER S-7nbamxyc: tier definitions applied to ConfigMgr]
- No page reviewed (S1210, S1212, S1225, S1226, S-7nbamxyc) names ConfigMgr/SCCM itself; the enterprise access model defines the control plane as access control based on centralized enterprise identity systems and the management plane as enterprise-wide IT management functions, so on that page's wording alone a device-management system like ConfigMgr reads as management plane; the tier model above is the more specific test. [DER S1210: plane definitions applied to ConfigMgr; no explicit ConfigMgr statement found]
- MFA for SMS Provider calls has been available since ConfigMgr current branch version 1702, as the concrete lever if an organization chooses to treat ConfigMgr as control-plane-equivalent. [DOC S1212]

## Reference
| Item | Fact | Tag |
|---|---|---|
| KB5014754 Compatibility mode start | 2022-05-10 | DOC |
| KB5014754 Full Enforcement start | 2025-02-11 | DOC |
| KB5014754 Compatibility mode option removed | 2025-09-09 update | DOC |
| Windows LAPS scope | Entra-joined and AD domain-joined devices, incl. servers | DOC |
| ConfigMgr named as Tier 0 by Microsoft | Not named; Tier 0 if it patches or runs agents on Tier 0 systems, else Tier 1 | DER |
| Windows LAPS policy settings, CSP nodes, events, schema | see `windows/laps.md` | DOC |

- `intune/certificates-pki.md` — how Intune SCEP/PKCS certificate profiles implement KB5014754 strong mapping (`OnPremisesSecurityIdentifier` SAN variable / connector registry flag), the certificate connector, and Microsoft Cloud PKI.

## Examples
- `PL-SRV-0042` (the SMS Provider host in the fixture estate) should carry a strongly-mapped certificate if certificate-based authentication is used anywhere in its chain, given KB5014754 Full Enforcement is already in effect as of this research date (2026-09-24).
