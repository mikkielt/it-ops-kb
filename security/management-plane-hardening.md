---
topic: security/management-plane-hardening
priority: P1
applies_to: "ConfigMgr current branch 2603; SQL Server 2022/2025; GitLab self-managed; Windows GitLab Runner"
retrieved_utc: 2026-09-24
sources: [S1480, S1481, S1482, S1483, S1484, S1485, S1486, S1487, S1488, S1489, S1490, S1491]
status: partial
---

# Management-plane hardening

## Summary
ConfigMgr, its SQL Server site database, GitLab (a configuration repository) and the Windows GitLab Runner are systems a device-management tool depends on but does not own. Each has official Microsoft/GitLab hardening guidance; CIS benchmarks exist for SQL Server (several versions) and for GitLab, but not (found) for ConfigMgr itself. Admin-workstation hardening (PAW / enterprise access model) is covered in [[enterprise-access-model]] and linked, not duplicated here.

## Facts
### ConfigMgr (constrains a scheduled-sync host, and any engineer using a CLI/MCP role against it)
- Microsoft's site-administration security guidance recommends IPsec between site systems, and keeping site system roles off the site server rather than co-locating them, as security/operational-resilience best practices. [DOC S1480]
- Client security guidance: deploy the ConfigMgr client only to trusted devices; site property lets you require HTTPS-only for site systems. [DOC S1483]
- **MFA for SMS Provider calls** (constrains any interactive identity that reaches AdminService/SDK): available since ConfigMgr current branch 1702. When enabled, the SMS Provider and AdminService require the caller's token to carry an MFA claim from Windows Hello for Business (smart card or Hello for Business PIN/biometric) — this is a Windows sign-in MFA claim, not SMS-based OTP despite the setting's name. It is a global, hierarchy-wide setting; only a Full Administrator scoped to All can set it. [DOC S1482]
- **Enhanced HTTP vs PKI HTTPS** (constrains a site's client communication config): sites allowing plain HTTP client communication are deprecated from ConfigMgr 2103 onward. Microsoft recommends PKI-certificate HTTPS for its finer-grained, enterprise-class controls; Enhanced HTTP is the fallback when PKI/HTTPS is not available. [DER S1480,S1483: general HTTPS-only guidance plus the deprecation note]
- **NTLM fallback / client push** (constrains a site's push-install config, and is a documented attack surface against the site's own machine account): when automatic client push installation is enabled without a PKI client-auth certificate, NTLM authentication from the management point can be coerced to an attacker-controlled name. From ConfigMgr current branch 1806, the site can require Kerberos mutual authentication and refuse NTLM fallback. From version 2207 (hotfix KB15498768), "Allow connection fallback to NTLM" is **disabled by default on new site installations**, and Microsoft recommends disabling it on existing hierarchies. [DOC S1484]
- No CIS benchmark for Configuration Manager itself was found on the public CIS benchmark list. [UNK]
- Microsoft's cloud security benchmark privileged-access guidance treats control-plane, management-plane and data-workload-plane administrative accounts as separate tiers to limit blast radius, and calls for regular review of the access granted for each plane. [DOC S1491] No page was found that names ConfigMgr explicitly as "Tier 0"; Microsoft's general enterprise access model (linked, not duplicated here — see [[enterprise-access-model]]) treats systems that can control identity or execute code across the estate, which a ConfigMgr site fits by function, as control-plane assets. [DER S1491: general control-plane tiering principle applied to a site that can push code to devices; UNK for an explicit "ConfigMgr = Tier 0" statement]
- AdminService exposure, CMPivot and Run Scripts approval permissions are covered in the existing [[../mecm/run-scripts]] and `mecm/rbac` topics (not duplicated here); this file adds only the hardening framing above.

### SQL Server (constrains the database)
- Prefer Windows/Entra authentication over SQL authentication; if SQL logins are unavoidable, require strong unique passwords. [DOC S1488]
- SQL Server 2022+: use **Force Strict Encryption** (TDS 8.0) rather than the older Force Encryption. [DOC S1488]
- Transparent Data Encryption (TDE) protects database, backup and tempdb files at rest. [DOC S1488]
- Run SQL Server services under the lowest-privilege account feasible; restrict physical/host access. [DOC S1488]
- A CIS benchmark exists for Microsoft SQL Server: separate benchmarks per major version, including **CIS Microsoft SQL Server 2022 Benchmark** (versions seen up to v1.3.0) and **CIS Microsoft SQL Server 2025 Benchmark v1.0.0**. Exact current version/date needs the CIS benchmark list page (no registration required to see the list; PDF is free for non-commercial use). [DOC S1486]

### GitLab self-managed (constrains a no-domain-identity CI runner and the configuration repository)
- A **CIS GitLab Benchmark** exists (first published by GitLab with CIS, announced 2024-04-17), with 125+ recommended configuration checks. An open-source scanner (`gitlabcis`) implements it against the benchmark's checks. [DOC S1487]
- The GitLab-authored scanner project is a live reference for the benchmark's check IDs even where the benchmark PDF itself needs a CIS account. [DOC S1489]
- GitLab publishes CC BY-SA 4.0-licensed hardening-relevant docs (merge request approval rules, protected branches, runner security) under `docs.gitlab.com`; those specific to CI approvals and branch protection are already covered by other kb parts — this file adds only the CIS-benchmark existence fact.

### Windows GitLab Runner host (constrains the CI runner's host)
- Runner installation and shell/service-account guidance for Windows is in the runner docs; already partly captured in [[../windows/gitlab-runner-windows]] (not duplicated). [DOC S1490]

### Admin workstations / PAW
- See [[../auth/enterprise-access-model]] for the privileged-access-workstation and tiering model; this file does not duplicate it. An engineer workstation running a CLI/MCP client should be evaluated against that model's device-trust tier for whatever it authenticates to (AdminService, Graph).

## Reference
| Guidance area | Component constrained | Source |
|---|---|---|
| MFA for SMS Provider | interactive client role, any AdminService/SDK caller | S1482 |
| Enhanced HTTP / PKI HTTPS | site system config | S1480,S1483 |
| NTLM fallback / client push | push install config | S1484 |
| SQL Server hardening + CIS benchmark | the store database | S1486,S1488 |
| GitLab CIS benchmark | CI runner, configuration repository | S1487,S1489 |
| Privileged-access tiering | all identities | S1491 |

## Examples
No fixture-specific configuration; these are host/site-level settings applied once per environment, not per-device (`PL-LT-00123` etc. do not apply).
