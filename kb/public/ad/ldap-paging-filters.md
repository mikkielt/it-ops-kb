---
topic: ad/ldap-paging-filters
priority: P1
applies_to: "Active Directory LDAP (Windows Server 2008 R2 and later)"
retrieved_utc: 2026-09-26
sources: [S567, S568, S569, S570, S571, S560]
status: complete
---

# LDAP paging and search filters (Active Directory)

## Summary
- Default `MaxPageSize` = 1,000 objects per search result; larger results need the paged results control (OID 1.2.840.113556.1.4.319).
- Hard-coded ceilings on Windows Server 2008 R2+: MaxPageSize 20,000, MaxValRange 5,000, MaxQueryDuration 1,200 s.
- Filter syntax: `= ~= <= >= & | !`, bitwise matching rules 1.2.840.113556.1.4.803/804, in-chain 1.2.840.113556.1.4.1941; binary values escaped as `\xx`.

## Facts
- `MaxPageSize` controls the maximum number of objects returned in a single search result; exceeding it requires the paged search control; default 1,000. [DOC S569]
- `MaxQueryDuration` default 120 s; on reaching it the DC returns `timeLimitExceeded`; longer searches must use the paged results control. [DOC S569]
- `MaxResultSetSize` default 262,144 bytes (intermediate data kept between pages). [DOC S569]
- `MaxValRange` (values returned per attribute) default 1,500. [DOC S569]
- Windows Server 2008 / 2008 R2 and later hard-code maxima that override higher policy values: MaxReceiveBuffer 20,971,520; MaxPageSize 20,000; MaxQueryDuration 1,200; MaxTempTableSize 100,000; MaxValRange 5,000. [DOC S570]
- `LDAP_PAGED_RESULT_OID_STRING` = 1.2.840.113556.1.4.319 (listed in RootDSE supportedControl). [DOC S571]
- ADSI: without paging, AD searches return at most the first 1,000 records; set `ADS_SEARCHPREF_PAGESIZE` if more are possible. [DOC S568]
- Filter operators: `=`, `~=`, `<=`, `>=`, `&`, `|`, `!`. [DOC S567]
- Matching rules: 1.2.840.113556.1.4.803 (bitwise AND), .804 (bitwise OR), .1941 (LDAP_MATCHING_RULE_IN_CHAIN, DN attributes only). [DOC S567]
- Escapes: `*` `\2a`, `(` `\28`, `)` `\29`, `\` `\5c`, NUL `\00`, `/` `\2f`; arbitrary binary data is encoded byte by byte as backslash plus two hex digits. [DOC S567]
- Filtering on a GUID (e.g. `objectGUID`) therefore uses the 16 raw bytes, each as `\xx`. [DER S560,S567: objectGUID is 16 bytes; binary escape rule]

## Reference
| LDAP policy | Default | Hard max (2008 R2+) | Source |
|---|---|---|---|
| MaxPageSize | 1,000 | 20,000 | S569, S570 |
| MaxQueryDuration | 120 s | 1,200 | S569, S570 |
| MaxValRange | 1,500 | 5,000 | S569, S570 |
| MaxResultSetSize | 262,144 bytes | - | S569 |

## Examples
- `(&(objectCategory=computer)(dNSHostName=PL-LT-00123.corp.example.com))`
- Security groups (from the doc): `(&(objectCategory=group)(groupType:1.2.840.113556.1.4.803:=2147483648))`
