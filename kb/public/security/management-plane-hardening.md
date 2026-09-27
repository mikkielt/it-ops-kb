---
topic: security/management-plane-hardening
priority: P1
applies_to: "ConfigMgr current branch 2603; SQL Server 2022/2025; GitLab self-managed; Windows GitLab Runner"
retrieved_utc: 2026-09-26
sources: [S1480, S1481, S1482, S1483, S1484, S1485, S1486, S1487, S1488, S1489, S1490, S1491, S-thjpegto, S-psoai6ce]
status: partial
---

# Management-plane hardening

## Summary
ConfigMgr, its SQL Server site database, GitLab (a configuration repository) and the Windows GitLab Runner are systems a device-management tool depends on but does not own. Each has official Microsoft/GitLab hardening guidance; CIS benchmarks exist for SQL Server (several versions) and for GitLab, but not (found) for ConfigMgr itself. Admin-workstation hardening (PAW / enterprise access model) is covered in [[enterprise-access-model]] and linked, not duplicated here.

## Facts
### ConfigMgr (constrains a scheduled-sync host, and any engineer using a CLI/MCP role against it)
- Microsoft's site-administration security guidance recommends IPsec between site systems, and keeping site system roles off the site server rather than co-locating them, as security/operational-resilience best practices. [DOC S1480]
- Client security guidance: deploy the ConfigMgr client only to trusted devices; site property lets you require HTTPS-only for site systems. [DOC S1483]
- **MFA for SMS Provider calls** (constrains any interactive identity that reaches the SMS Provider): available since ConfigMgr current branch 1702 (SMS here is Systems Management Server, not text messages). It is set with the `SMS_Site` method `SetAuthenticationLevel`: `AuthenticationLevel` 0 (default) adds no second layer, 10 allows provider calls only from users signed in with a PIN or smart card, 20 only from users signed in with a PIN; SIDs in `ExceptionList` (such as service accounts) bypass it. It is a global setting used on all primary sites; only a Full Administrator with the All scope can set it, signed in with the same method being enabled. [DOC S1482]
- Whether the AdminService REST API enforces the same SMS Provider authentication level. [UNK: not in S1482 as re-read 2026-09-27]
- **Enhanced HTTP vs PKI HTTPS** (constrains a site's client communication config): sites allowing plain HTTP client communication are deprecated from ConfigMgr 2103 onward; configure the site for HTTPS or Enhanced HTTP. [DOC S1480,S1483]
- Microsoft recommends HTTPS for all ConfigMgr communication paths and calls PKI-based HTTPS the more secure configuration; where HTTPS is not possible, it recommends Enhanced HTTP, which uses site-issued self-signed certificates. PKI stays the option for all-HTTPS client communication and advanced control of the signing infrastructure. [DOC S-thjpegto]
- **NTLM fallback / client push** (constrains a site's push-install config): from ConfigMgr current branch 1806, the site can require Kerberos mutual authentication for client push by not allowing fallback to NTLM; from version 2207, "Allow connection fallback to NTLM" is **disabled by default on new site installations**, and Microsoft recommends disabling it in existing environments. [DOC S-psoai6ce]
- Hotfix KB15498768 (versions 2103-2207, resolves CVE-2022-37972) fixes a case where disabling the fallback was not honored: after Kerberos failures the push account, or the site server computer account, still tried NTLM. Without an upgrade, disabling automatic and manual client push removes the exposure. [DOC S1484]
- That NTLM authentication from client push can be coerced to an attacker-controlled name when no PKI client-auth certificate is used. [UNK: not in S1484 as re-read 2026-09-27]
- No CIS benchmark for Configuration Manager itself was found on the public CIS benchmark list. [UNK]
- Microsoft's cloud security benchmark privileged-access guidance (PA-1) says to limit the number of privileged accounts in the control, management and data/workload planes, and to restrict privileged accounts in system management tools with agents installed on business-critical systems, because attackers who compromise such tools can weaponize them; PA-4 calls for regular review that granted access is valid for each plane. [DOC S1491]
- A ConfigMgr site is such a system management tool (its client agent runs on managed devices), so its administrative accounts fall under PA-1's restriction. [DER S1491: PA-1's "system management tools with agents" applied to ConfigMgr]
- No page was found that names ConfigMgr explicitly as "Tier 0"; see [[enterprise-access-model]] for the general tiering model. [UNK]

### SQL Server (constrains the database)
- Prefer Windows/Entra authentication over SQL authentication; if SQL logins are unavoidable, require strong unique passwords. [DOC S1488]
- SQL Server 2022+: use **Force Strict Encryption** (TDS 8.0) rather than the older Force Encryption. [DOC S1488]
- Transparent Data Encryption (TDE) protects database, backup and tempdb files at rest. [DOC S1488]
- Use group managed service accounts (gMSA) for SQL Server services: Windows manages and rotates their passwords without service restarts. Minimize the DBA account's rights, separating duties such as access to the VM, OS sign-in, log changes and software installs. [DOC S1488]
- A CIS benchmark exists for Microsoft SQL Server: separate benchmarks per major version, including **CIS Microsoft SQL Server 2022 Benchmark** (versions seen up to v1.3.0) and **CIS Microsoft SQL Server 2025 Benchmark v1.0.0**. Exact current version/date needs the CIS benchmark list page (no registration required to see the list; PDF is free for non-commercial use). [DOC S1486]

### GitLab self-managed (constrains a no-domain-identity CI runner and the configuration repository)
- A **CIS GitLab Benchmark** exists (first published by GitLab with CIS, announced 2024-04-17), with 125+ recommended configuration checks. [DOC S1487]
- `gitlabcis`, an open-source Python package from GitLab's security OSS group, audits a GitLab project against the CIS GitLab Benchmark, with its recommendations kept as YAML. [DOC S1489]
- The GitLab-authored scanner project is a live reference for the benchmark's check IDs even where the benchmark PDF itself needs a CIS account. [DOC S1489]

### Windows GitLab Runner host (constrains the CI runner's host)
- Runner installation and shell/service-account guidance for Windows is in the runner docs; already partly captured in [[../windows/gitlab-runner-windows]] (not duplicated). [DOC S1490]

## Reference
### Notes (design notes and cross-references, no external source)
- AdminService exposure, CMPivot and Run Scripts approval permissions are covered in the existing [[../mecm/run-scripts]] and `mecm/rbac` topics (not duplicated here); this file adds only the hardening framing above.
- GitLab publishes CC BY-SA 4.0-licensed hardening-relevant docs (merge request approval rules, protected branches, runner security) under `docs.gitlab.com`; those specific to CI approvals and branch protection are already covered by other kb parts — this file adds only the CIS-benchmark existence fact.
- See [[../auth/enterprise-access-model]] for the privileged-access-workstation and tiering model; this file does not duplicate it. An engineer workstation running a CLI/MCP client should be evaluated against that model's device-trust tier for whatever it authenticates to (AdminService, Graph).

| Guidance area | Component constrained | Source |
|---|---|---|
| MFA for SMS Provider | interactive client role, any AdminService/SDK caller | S1482 |
| Enhanced HTTP / PKI HTTPS | site system config | S1480,S1483,S-thjpegto |
| NTLM fallback / client push | push install config | S1484,S-psoai6ce |
| SQL Server hardening + CIS benchmark | the store database | S1486,S1488 |
| GitLab CIS benchmark | CI runner, configuration repository | S1487,S1489 |
| Privileged-access tiering | all identities | S1491 |

## Examples
No fixture-specific configuration; these are host/site-level settings applied once per environment, not per-device (`PL-LT-00123` etc. do not apply).
