---
topic: auth/threats
priority: P2
applies_to: "Windows 11 24H2, Server 2025, Entra ID"
retrieved_utc: 2026-09-27
sources: [S1352, S1353, S1347, S-7o47ht7q, S1227, S-mifutdb3, S-ffangyfp, S-7bjorbzz, S-6ca4b7bg, S-ft7nubbn, S-p6zdxvtp]
status: complete
---

## Summary
Defensive-only digest: attack class, the identity flow it touches,
the official Microsoft mitigation, and how to detect it. No exploitation steps or tooling are recorded.
See `threats.csv` for the full table (Kerberoasting, NTLM relay, token theft, consent phishing, SMB
coercion); every row cites its Microsoft sources.

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
- gMSA passwords are 240-byte random values that Windows changes every 30 days; Microsoft's Kerberoasting
  guidance gives them as 120 characters. [DOC S-mifutdb3, S-ffangyfp]
- Event 4769 records the ticket encryption type; Microsoft advises monitoring for types other than 0x11 and
  0x12 (AES), and Defender for Identity raises external ID 2410 for suspected Kerberos SPN exposure.
  [DOC S-7bjorbzz, S-ffangyfp, S-6ca4b7bg]
- Consent phishing tricks users into granting permissions to malicious cloud apps; Microsoft's mitigations
  are restricting user consent to verified publishers and low-risk permissions, publisher verification,
  the admin consent workflow and app governance policies. [DOC S-ft7nubbn]
- Domain controllers and AD admin systems should run with the Print Spooler service disabled, because any
  authenticated user can make a DC's spooler authenticate to another system; Defender for Identity raises
  external ID 2426 for a suspected DFSCoerce attack. [DOC S-p6zdxvtp, S-6ca4b7bg]

## Reference
See `threats.csv`.

## Examples
No fixture-specific configuration; class names and mitigations only, no exploitation detail.
