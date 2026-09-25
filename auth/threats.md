---
topic: auth/threats
priority: P2
applies_to: "Windows 11 24H2, Server 2025, Entra ID"
retrieved_utc: 2026-09-24
sources: [S1352, S1353, S1347]
status: partial
---

## Summary
Defensive-only digest: attack class, the identity flow it touches,
the official Microsoft mitigation, and how to detect it. No exploitation steps or tooling are recorded.
See `threats.csv` for the full table; several rows are left `[UNK]` because they belong to topics other
agents in this run own (workload-identity, gmsa-dmsa, ldap-smb-signing) and this agent did not duplicate
that research.

## Facts
- Windows 11 24H2 and Windows Server 2025 remove NTLMv1 and deprecate NTLMv2, and ship new NTLM auditing
  to show administrators which principals and services still negotiate NTLM. [DOC S1352]
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
