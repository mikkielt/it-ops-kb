---
topic: mecm/sql-views-compliance
priority: P0
applies_to: "ConfigMgr current branch 2603 (SQL views docs ms.date 2019-04-30, memdocs 4b5429df)"
retrieved_utc: 2026-09-26
sources: [S-mmydokhp, S-tnbxhz6o, S-7hxddhnw, S-6qn22dge, S-qqxrnbd5, S-ava6e5jq, S-rljokguo, S-6war5y2t, S234]
status: partial
---

## Summary
Table: `sql-views-compliance.csv` (68 views: view, doc section, description, documented columns, source). The SQL views
reference describes each view and its join columns but **does not publish full column lists**. Compliance state per CI
per device is in `v_CICurrentComplianceStatus` (`ComplianceState` = state ID for topic type 401). No SQL view is documented
as holding a script CI's discovered (current) value; the only documented "discovered value" field is `DiscoveredValue` on the
SMS Provider WMI class `SMS_DCMDeploymentCompliantDetailsPerAsset`. `v_CIComplianceStatusReificationDetail` holds before/after
values of remediated settings.

## Facts
- The compliance settings views doc lists views and join columns only ("key compliance settings views and columns"); no per-view column tables. [DOC S-tnbxhz6o]
- `v_CICurrentComplianceStatus`: compliance and enforcement states per CI and resource, applicability, compliance/evaluation info; joins on CI_ID, ResourceID, CI_UniqueID, ModelName, ComplianceState, LastEnforcementMessageID. `ComplianceState` = state ID of topic type 401; `LastEnforcementMessageID` = state ID of topic type 402. [DOC S-tnbxhz6o,S-7hxddhnw]
- `v_CIComplianceStatusDetail`: CIs in a baseline assigned to a client with state **Non-Compliant**; joins CI_ID, CI_UniqueID, ResourceID, ModelName; sample query uses `Netbios_Name0`, `RuleSeverity`, `LastComplianceMessageTime`. [DOC S-tnbxhz6o,S-6qn22dge]
- `v_CICurrentSettingsComplianceStatusDetail`: CIs in a baseline reporting a validation error or noncompliance; includes NetBIOS name, CI name, setting name/type/description, constraint name/description and validation rule. [DOC S-tnbxhz6o]
- `v_CIComplianceStatusComplianceDetail`: per deployed CI, the compliance status of each setting. [DOC S-tnbxhz6o]
- `v_CIComplianceStatusReificationDetail`: by ModelID, instances where ConfigMgr remediated settings, including setting ID and the value before and after remediation. [DOC S-tnbxhz6o]
- `v_CIComplianceStatusErrorDetail`, `v_CI_CurrentErrorDetails`, `v_CIErrorDetails`: errors from evaluation (error type, setting info, error code). [DOC S-tnbxhz6o]
- `v_CIComplianceStatusConflictsDetail`: rule conflicts (joins ResourceID). [DOC S-tnbxhz6o]
- `v_CICurrentRuleDetail`: current compliance status of CI rules by record ID. [DOC S-tnbxhz6o]
- `v_CI_CurrentComplianceStatus` and `v_SMSCICurrentComplianceStatus` are further current-status views (join CI_ID/ResourceID and CI_CurrentComplianceStatusID respectively). [DOC S-tnbxhz6o]
- `v_CIComplianceHistory`: compliance start/end dates per CI and resource. [DOC S-tnbxhz6o]
- `v_CIAssignmentStatus`: last enforcement/evaluation state messages per assignment and resource. [DOC S-tnbxhz6o]
- `v_AssignmentSummaryPerTopic`: state types 300 (deployment compliance), 301 (enforcement), 302 (evaluation); names in `v_StateNames`. [DOC S-tnbxhz6o]
- `v_CIComplianceSummary`: counts per baseline (targeted, compliant, failed, noncompliant). [DOC S-tnbxhz6o]
- `v_CIRemediationHistory` (2002+, when "Track remediation history" enabled): `RemediationDate` (UTC), `ResourceID`. [DOC S-mmydokhp]
- Which SQL view exposes a script CI's discovered/current value is not documented; none of the view descriptions mention a discovered or current value column (only before/after values of remediation). [DER S-tnbxhz6o: searched all 67 descriptions]
- WMI class `SMS_DCMDeploymentCompliantDetailsPerAsset` has `DiscoveredValue` ("value of the setting that was discovered and reported when the rule is non-compliant"), `PreviousValue` (value at prior evaluation), `InstanceData` (discovered path), plus `RuleStateDisplay` (Compliant/Non-compliant/Error/Conflict), `ResourceID`-equivalent `ItemKey`, `CI_ID`, `Setting_ID`, `Rule_ID`. [DOC S-qqxrnbd5]
- `SMS_CI_CurrentComplianceStatus` columns: CI_ID, CI_UniqueID, CIVersion, ComplianceState, ComplianceStateName, ComplianceStatusDetails, ComplianceValidationRuleFailures, DesiredState, EnforcementState, EnforcementStateName, IsApplicable, IsDetected, LastComplianceMessageTime, LastEnforcementMessageTime, MaxNoncomplianceCriticality, ModelName, ResourceID, SDMPackageVersion, UserName. [DOC S-ava6e5jq]
- The underlying SQL view that backs `SMS_DCMDeploymentCompliantDetailsPerAsset` is not documented. [UNK]
- Built-in reports (category Compliance and Settings Management, 22 reports) include "Details of non-compliant rules of configuration items in a configuration baseline for an asset", "Details of compliant rules...", "Details of remediated rules...", "List of unknown assets for a configuration baseline". [DOC S-rljokguo]
- Report "validation criteria" fields show raw SML. [DOC S-6war5y2t]

## Reference
See `sql-views-compliance.csv`. Key views for drift reads:

| Need | View / class | Tag |
|---|---|---|
| Compliance state per CI per device | v_CICurrentComplianceStatus.ComplianceState (topic 401) | [DOC S-tnbxhz6o] |
| Noncompliant setting details | v_CICurrentSettingsComplianceStatusDetail | [DOC S-tnbxhz6o] |
| Per-setting status | v_CIComplianceStatusComplianceDetail | [DOC S-tnbxhz6o] |
| Remediated before/after value | v_CIComplianceStatusReificationDetail | [DOC S-tnbxhz6o] |
| Discovered value (WMI) | SMS_DCMDeploymentCompliantDetailsPerAsset.DiscoveredValue | [DOC S-qqxrnbd5] |
| State names | v_StateNames (TopicType 401) | [DOC S-6qn22dge] |

## Examples
Documented join (S-6qn22dge), fixture filter added:
```sql
SELECT s.Netbios_Name0, p.DisplayName, n.StateName
FROM v_CICurrentComplianceStatus c
JOIN v_LocalizedCIProperties p ON c.CI_ID = p.CI_ID
JOIN v_StateNames n ON c.ComplianceState = n.StateID AND n.TopicType = 401
JOIN v_R_System s ON c.ResourceID = s.ResourceID
WHERE s.Netbios_Name0 = 'PL-LT-00123';
```
