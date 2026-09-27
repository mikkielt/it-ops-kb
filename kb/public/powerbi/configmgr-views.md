---
topic: powerbi/configmgr-views
priority: P2
applies_to: "ConfigMgr current branch reporting views"
retrieved_utc: 2026-09-26
sources: [S902, S907]
status: partial
---

# ConfigMgr compliance and CI views for Power BI (pointer)

## Summary
This file is a pointer only. The ConfigMgr SQL views for configuration items and baseline compliance
(for example `v_CICurrentComplianceStatus`, `v_CIComplianceStatusDetail`) and their columns are documented in
[`mecm/sql-views-compliance.md`](../mecm/sql-views-compliance.md), written by the mecm agent. Columns are not duplicated here.

## Facts
- The ConfigMgr site database is an on-premises SQL Server database, so Power BI service refresh of it goes through a gateway SQL Server connection, as in `on-prem-gateway-sql.md` (on-prem SQL needs a gateway [S902] + SQL Server connection rules [S907]). [DER S902,S907]

## Reference
- View names, columns, and which view exposes a script CI's discovered value: ../mecm/sql-views-compliance.md
- ./on-prem-gateway-sql.md

## Examples
None.
