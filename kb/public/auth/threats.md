---
topic: auth/threats
priority: P2
applies_to: "Windows 11 24H2, Server 2025, Entra ID"
retrieved_utc: 2026-09-26
sources: [S1352, S1353, S1347, S-7o47ht7q]
status: partial
---

## Summary
Defensive-only digest: attack class, the identity flow it touches,
the official Microsoft mitigation, and how to detect it. No exploitation steps or tooling are recorded.
See `threats.csv` for the full table; several rows are left `[UNK]` because they belong to topics other
agents in this run own (workload-identity, gmsa-dmsa, ldap-smb-signing) and this agent did not duplicate
that research.

## Facts
- NTLM (LANMAN, NTLMv1, NTLMv2) is deprecated (announced June 2024), and NTLMv1 is removed starting in
  Windows 11 24H2 and Windows Server 2025. [DOC S-7o47ht7q]
- Windows 11 24H2 and Windows Server 2025 add enhanced NTLM auditing in `Microsoft-Windows-NTLM/Operational`
  (who, why, where; client events 4020/4021, server 4022/4023, DC 4030-4033) that flags NTLMv1, unsupported EPA
  or a missing MIC at Warning level, in preparation for NTLM deprecation; rollout is gradual, 24H2 first, then
  Server 2025. [DOC S1352]
- Microsoft has rolled out Extended Protection for Authentication (channel binding for TLS-backed
  protocols, SPN-based service binding otherwise) as a default mitigation against NTLM relay across
  Exchange, AD CS and LDAP, with a stated direction of enabling EPA by default more broadly. [DOC S1353]
- CAE's claim-challenge mechanism (a resource provider's 401 response telling a client its cached-but-
  not-yet-expired token was rejected) is the documented Microsoft pattern for revoking a token that has
  already been issued, relevant to detecting/limiting token replay for CAE-covered resources. [DOC S1347]

## Reference
See `threats.csv`.

## Examples
No fixture-specific configuration; class names and mitigations only, no exploitation detail.
