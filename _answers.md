# Answers to open research questions

Each answer bullet carries one tag and source ids. `QA` sections answer auth questions, `QS` security questions, `QR` architecture questions, `QG` agentic-tooling questions. `QK` questions researched with the `/kb-research` skill. `R` sections are reuse verdicts (evidence in `reuse/`).

## Q1. Officially documented `SMS_ClientOperation` Type values for machine policy, hardware inventory, app evaluation and software-update evaluation.
- The SDK method `InitiateClientOperation(Type, TargetCollectionID, RandomizationWindow, TargetResourceIDs[])` documents `Type` only as "Type", with no value table. [DOC S329]
- No official source gives Type numbers for machine policy, hardware inventory, application evaluation or software update evaluation. [UNK]
- The only numeric Types in official docs are 135 (Run Script, and CMPivot in 1902 and earlier) and 145 (CMPivot, 1906+), both from smsprov.log samples. [DOC S318]
- `SMS_ClientOperation.PrimaryActionType` value 4 "Evaluate Software Update" and value 8 "RequestPolicyNow" are documented, but as primary-action codes, not as Type values. [DER S328,S329: different property; Type has no table]
- `Invoke-CMClientAction -ActionType` documents the names ClientNotificationRequestMachinePolicyNow, ClientNotificationRequestHWInvNow, ClientNotificationAppDeplEvalNow and ClientNotificationSUMDeplEvalNow, without numeric values. [DOC S334]
- Community blogs publish numeric Type tables. These were not verified and are not official. [COMMUNITY S352]

_Agent: mecm2_

## Q2. CMPivot `datetime()` / `ago()` syntax, and the `CcmLog()` result columns.
- `ago(<timespan>)` subtracts the timespan from the current UTC time, e.g. `ago(1d)`, `ago(2h)`, `ago(7d)`. `now()` returns the current UTC time. [DOC S316, S-v5d6zvne]
- Datetime literals: `datetime(2015-12-31 23:59:59.9)`, ISO 8601 `yyyy-mm-dd HH:MM:ss`, always UTC, 1-second units. [DOC S316]
- Arithmetic: `now() + 1d`, `now() - 1h`. Also available: `datetime_diff('day', now(), X)`, `datetime_add()`, `bin(X, 1d)`. [DOC S317,S316]
- `CcmLog('<log name>'[, <timespan>])` defaults to the last 24 hours. Example: `CcmLog('Scripts',1h)`. Each client returns at most 128 KB, and `CcmLog('ciagent',120d)` is cited as likely to exceed it. [DOC S316]
- `CcmLog()` result columns are not documented in any official source found (memdocs clone at 4b5429df, all repos grepped). [UNK]

_Agent: mecm2_

## Q3. DSC 3.3 `directives.version`: the upper-bound syntax, and what happens on a mismatch.
- Syntax: a semver requirement string with comparators separated by commas, all of which must hold (logical AND). An upper bound is written `'>=3.3, <3.4'`. There is no OR. `^1.2` means `>=1.2.0, <2.0.0` and `=1.2` means `>=1.2.0, <1.3.0`. [DOC S104]
- Mismatch: `validate_config` returns `DscError::Validation` before any resource runs. dsc exits with code 2 and writes `Validation: Configuration requires DSC version '<req>', but the current version is '<ver>'` to stderr. [DOC S102,S123,S101]
- **Defect:** the running version is read with `env!("CARGO_PKG_VERSION")` inside dsc-lib, whose crate version is 3.2.0 in both 3.3.0 and 3.4.0-preview.1. So `'>=3.3, <3.4'` fails on the real 3.3.0 binary ("current version is '3.2.0'") and `'>=3.2, <3.3'` passes. [DER S102,S112,S116: code plus observed run 2026-09-23]
- The 3.3.0 binary also accepts forms the type docs say are forbidden: `'3.3'` (treated as `^3.3`), `'1.x'`, `'*'` and build metadata. [DER S104,S116]
- Related: `directives.securityContext` (`current` | `elevated` | `restricted`). A mismatch also gives exit 2 ("Security context: Elevated security context required"). [DOC S103,S102; DER S116]

_Agent: dsc_

## Q4. AdminService through CMG with **delegated** Entra tokens: which routes are supported?
- Docs: enable "Allow Configuration Manager cloud management gateway traffic for administration service", then replace the provider FQDN with the CMG endpoint (`https://<cmg>/CCM_Proxy_MutualAuth/<id>/AdminService`). An Entra ID account is required. [DOC S301,S300]
- No official page lists which routes are supported or unsupported through the CMG. The usage page says every example applies with the CMG endpoint substituted. [DER S302: note at top of usage.md covers all examples]
- Microsoft's sample (linked from the 2207 docs) obtains a delegated user token interactively with MSAL and calls `v1.0/Device` on `https://<Provider_FQDN>/AdminService_TokenAuth/`. This is the only route exercised with a bearer token in Microsoft material. [DOC S313]
- Since 2207, the "Administration Service Management" Azure service option segments admin access to AdminService endpoints only. It is available only for CMG VMSS. [DOC S308,S309]
- Answer: a per-route support list for CMG and delegated tokens is not documented. [UNK]

_Agent: mecm2_

## Q5. Which ConfigMgr SQL view exposes a script CI's discovered (current) value?
- No SQL view is documented as exposing a CI setting's discovered/current value; the SQL views reference gives descriptions and join columns only, and no description mentions a discovered or current value. [DER S206: all 67 compliance view descriptions checked]
- Closest documented SQL views: `v_CICurrentSettingsComplianceStatusDetail` (noncompliant/validation-error settings with setting, constraint and validation rule), `v_CIComplianceStatusComplianceDetail` (per-setting compliance status), `v_CIComplianceStatusReificationDetail` (value before and after remediation). [DOC S206]
- Compliance state per CI and device: `v_CICurrentComplianceStatus.ComplianceState` (state ID, topic type 401, join `v_StateNames`). [DOC S206,S208]
- The only documented field named for a discovered value is `DiscoveredValue` (plus `PreviousValue`, `InstanceData`) on SMS Provider WMI class `SMS_DCMDeploymentCompliantDetailsPerAsset`, described as reported "when the rule is non-compliant". [DOC S209]
- The SQL view or table behind that class is not documented. [UNK]

_Agent: mecm1_

## Q6. Does the client setting "script execution timeout" apply to compliance-setting scripts? What is its range?
- Yes: "Script Execution Timeout (seconds)" is in the **Compliance settings** client-settings group and is described as giving flexibility "for configuration items when you need to run scripts that may exceed the default of 60 seconds"; the CI doc's Script section points to it. [DOC S204,S200]
- Range 60-600 seconds; default 60 seconds; introduced in version 2207. [DOC S204,S205]
- Whether it also governs application detection scripts or global conditions is not stated. [UNK]

_Agent: mecm1_

## Q7. Collect client logs: storage location on the site, retrieval method, size limit.
- Storage: site server `Inboxes\sinv.box\FileCol` (software inventory file-collection store); no defined limit on number of versions. [DOC S221,S223]
- Transport: client notification triggers upload to the MP via the software inventory file-collection channel; software inventory need not be enabled. [DOC S221]
- Retrieval: console Resource Explorer > Diagnostic Files, file `Support_<guid>.zip` (Save / View file / Open Support Center). [DOC S222]
- Size limit: 100 MB for the compressed client logs. [DOC S221]
- Cleanup: "Delete Aged Collected Diagnostic Files", default 14 days (2010+). [DOC S223]
- Permission: Notify resource. [DOC S221]
- Programmatic retrieval (WMI/AdminService) of the diagnostic zip is not documented. [UNK]

_Agent: mecm1_

## Q8. Graph delta query support for `managedDevices` and `windowsAutopilotDeviceIdentities`.
- Not supported in v1.0 or beta: neither CSDL binds a `delta` function to `managedDevice` or `windowsAutopilotDeviceIdentity`; the only device-related `delta` is bound to `Collection(graph.device)`. [DOC S502,S503]
- The delta supported-resources table lists `device` and no Intune or Autopilot resource. [DOC S510]
- The CSDL ChangeTracking annotation targets `microsoft.graph.device` only. [DOC S500,S501]
- Conclusion: incremental change tracking via delta is documented only for Entra `devices` (`GET /devices/delta`, `Device.Read.All`, directory tokens valid 7 days, `410 Gone` means full resync). Intune and Autopilot need full reads. [DER S502,S503,S510,S511,S514]

_Agent: ident_

## Q9. Any official statement that a hybrid-joined device's Entra `deviceId` equals its AD `objectGUID`?
- No page says in words "deviceId equals objectGUID". [UNK]
- Microsoft Entra Connect's synchronized-attributes reference lists computer `objectGUID` with the comment "Also called deviceID". [DOC S549]
- Entra Cloud Sync device sync (preview) maps Entra `DeviceId` <- AD `objectGUID` (Direct). [DOC S550]
- The managed hybrid-join flow says Entra Connect sends `userCertificate`, object GUID and SID to DRS, which creates the device object, and later that DRS "creates a device ID"; Graph says `deviceId` is set by DRS at registration. [DOC S548,S504]
- Conclusion: two official sync references map `objectGUID` onto the device ID attribute for synced hybrid devices, so equality is the documented mapping for the sync path. No statement covers the AD FS-only path or the comparison format (byte order). See entra/hybrid-deviceid-objectguid.md. [DER S549,S550]

_Agent: ident_

## Q10. Is the Autopilot device identity `id` the ZTDID?
- Not documented. `windowsAutopilotDeviceIdentity.id` is described only as "The GUID for the object". [DOC S508]
- ZTDId is documented as a value stored in the Entra device `physicalIds` (`[ZTDId]:value`), "a unique value assigned to all imported Windows Autopilot devices". [DOC S553]
- No Graph, Intune or Entra page links the ZTDId value to `windowsAutopilotDeviceIdentity.id`. [UNK]

_Agent: ident_

## Q11. Is Defender `aadDeviceId` populated for hybrid-joined devices?
- Not documented. The Machine resource defines `aadDeviceId` only as "Microsoft Entra Device ID (when machine is Microsoft Entra joined)". It does not say whether "Microsoft Entra joined" includes Microsoft Entra hybrid joined devices. [UNK]
- The documented type is a nullable Guid, so a null value is a valid response. [DOC S620]
- `aadDeviceId` is filterable on `GET /api/machines`, so the docs cover looking a device up by its Entra device ID when the value exists. [DOC S621]
- Advanced hunting `DeviceInfo` has three separate columns: `AadDeviceId`, `IsAzureADJoined` and `JoinType` ("The device's Microsoft Entra ID join type"). The page does not list the JoinType values. [DOC S627]
- Graph `security.deviceEvidence.azureAdDeviceId` uses the same "when device is Microsoft Entra joined" wording. [DOC S630]
- Searched with no statement about hybrid join: machine, get-machines, get-machine-by-id, the DeviceInfo table, the device inventory overview and the OData samples page. [DOC S620,S621,S622,S627,S628,S629]
- Community report (macOS, not hybrid): the API returned `aadDeviceId: null` while the portal showed a value. Microsoft support called this expected because macOS is not a full Entra join type. [COMMUNITY S631]
- Consequence: a null `aadDeviceId` does not show that a device is not Entra-linked; treat it as `unknown` rather than `absent`. [DER S620]

_Agent: ops_

## Q12. Run Script parameters over the AdminService v1.0 route: documented?
- No. The official AdminService docs list no v1.0 Run Script action. The documented v1.0 device actions are RunCMPivot, CMPivotResult and Set/Get/DeleteExtensionData. [DOC S302,S303,S306]
- The documented way to pass parameters is `Invoke-CMScript -ScriptParameter <Hashtable>` (ConfigMgr 2010+). [DOC S335]
- A community sample uses `v1.0/Device(<id>)/AdminService.RunScript` with `ScriptGuid` and parameters. It was not verified and is not official. [COMMUNITY S350]

_Agent: mecm2_

## Q13. The feature matrix, DSC 3.3.0 vs 3.4.0-preview.1: MCP `what_if`, the Group Policy adapter, environment variables, `Personalization`.
- MCP `what_if`: **absent in 3.3.0** (no field on `invoke_dsc_config`/`invoke_dsc_resource`; an unknown key is ignored, so a set runs for real). **Present in 3.4.0-preview.1**. [DOC S108,S109; DER S114,S115]
- Group Policy template adapter (`Microsoft.Adapter/GroupPolicyTemplate`): **not in 3.3.0** (not on release/v3.3). In 3.4.0-preview.1 it is in source but **not packaged** (absent from `data.build.json` and the Windows x64 zip). [DOC S120,S121; DER S114,S115]
- Environment variables: the `Microsoft.Windows/EnvironmentVariable` and `EnvironmentVariableList` resources (0.1.0) ship **only in 3.4.0-preview.1**. The `envvar()` function has existed since 3.0.0. [DOC S114,S115,S129]
- `Microsoft.Windows/Personalization`: an adapted-resource YAML (Registry adapter, HKCU theme values) in source on both release/v3.3 and v3.4.0-preview.1, **shipped in neither zip**. [DOC S122; DER S114,S115]
- Also in 3.4.0-preview.1 only: `Microsoft.Filesystem.File/Content`, native what-if for `Microsoft.Windows/UpdateList` (0.1.1), and the `--required-version` option name. [DOC S114,S115,S116,S117]
- Root cause of the release-notes mismatch: GitHub release v3.3.0 was created with `target_commitish: main`, so tag `v3.3.0` points to main commit 4b49240 (Cargo `3.4.0-preview.1`), and the notes were generated from `v3.3.0-rc.2...v3.3.0`. The binaries match `release/v3.3` @ ea572fa (Cargo `3.3.0`). [DOC S113,S110,S111,S118]

_Agent: dsc_

## Q14. MCP Python SDK 2.x: can a stdio tool request elicitation (a confirmation) mid-call, and does Claude Code render it?

- SDK 2.x exists: v2.0.0 released 2026-07-28, latest v2.2.0 (2026-09-07); the server class is `MCPServer` (FastMCP renamed; old import raises). [DOC S731,S732]
- In protocol 2026-07-28 a server cannot send a request mid-call; it returns `InputRequiredResult` with `elicitation/create` entries, and the client retries the call with the answers. On stdio, servers MUST NOT write JSON-RPC requests to stdout. [DOC S710,S705]
- SDK: `await ctx.elicit(...)` is a live server-to-client request that works only on legacy (handshake, ≤ 2025-11-25) connections; on 2026-07-28 connections it raises `NoBackChannelError`. [DOC S720,S728]
- SDK: `Annotated[T, Resolve(fn)]` returning `Elicit(...)` works on both eras (live request on legacy, MRTR on 2026-07-28), so a confirmation can be written once. [DOC S720,S723]
- SDK stdio servers are dual-era (`serve_dual_era_loop`) and the migration guide says stdio workflows relying on push elicitation need a legacy-mode connection. So a legacy stdio session carries a mid-call elicitation. [DER S735,S728: dual-era stdio loop + "pass mode='legacy'" for stdio push elicitation]
- Claude Code renders elicitation: form mode as an interactive dialog, URL mode by opening the browser; supported since 2.1.76 (2026-03-14); no configuration needed; `Elicitation`/`ElicitationResult` hooks can auto-answer or override. [DOC S740,S746,S743]
- Claude Code (v2 runtime) keeps stdio servers on the earlier handshake protocol unless `MCP_PROTOCOL_NEGOTIATION=auto` is set; with the default, a Python SDK 2.x stdio server sees a legacy session, where both `ctx.elicit()` and `Resolve`/`Elicit` send a live `elicitation/create` that Claude Code shows as a dialog. [DER S740,S745,S720: default stdio = legacy → back-channel exists → dialog]
- With `MCP_PROTOCOL_NEGOTIATION=auto`, the stdio session may land on 2026-07-28; then `ctx.elicit()` fails and only `Resolve`/`InputRequiredResult` works. Claude Code's handling of form-mode MRTR is not stated explicitly (2.1.281 only mentions adding URL mode on 2026-07-28 connections). [UNK]
- No end-to-end test result (SDK 2.2.0 stdio + Claude Code 2.1.281) was found in official sources. [UNK]

_Agent: mcp_

## Q15. Presidio: any release after 2.2.364, and does it include the UUID recognizer?
- No. The newest GitHub release is 2.2.364 (2026-07-22), and PyPI `presidio-analyzer` / `presidio-anonymizer` latest is 2.2.364 as of 2026-09-23. [DOC S801, S802, S803]
- 2.2.364 does not include `UuidRecognizer`. The tag's `generic/` directory has no `uuid_recognizer.py`, and its `default_recognizers.yaml` has no UUID entry. [DOC S805, S806]
- `UuidRecognizer` (entity `UUID`) was merged to `main` on 2026-07-27 (commit e069216, PR #2175). It is listed under `[unreleased]` in the CHANGELOG, so the first release to contain it will be the one after 2.2.364. [DOC S807, S800]
- On `main` it is enabled by default. It matches only the hyphenated 8-4-4-4-12 form, requires version nibble 1-8 and variant 8/9/a/b, and excludes the nil UUID. [DOC S808, S809]
- Consequence: the fixture tenant `00000000-0000-0000-0000-000000000000` is never tagged `UUID`, and unhyphenated GUIDs are not matched. [DER S808: nil UUID invalidated; single hyphenated pattern]
- The release date of the next version is not announced. [UNK]

_Agent: privacy_

## Q16. SQL Server temporal history retention: which editions and versions support it?
- `HISTORY_RETENTION_PERIOD` is documented for SQL Server 2017 and later (Windows and Linux), Azure SQL Database, Azure SQL Managed Instance and Fabric SQL database. SQL Server 2016 is not in the retention article's scope. [DOC S460]
- Temporal tables themselves apply to SQL Server 2016 and later. [DOC S461]
- Edition feature tables list Temporal as "Yes" for every edition: Enterprise, Standard, Web, Express with Advanced Services and Express (2017/2019/2022); Enterprise, Standard and Express (2025). Developer and Evaluation editions have the Enterprise (or Standard) feature set. [DOC S463,S464,S465,S466]
- The retention article states no edition restriction, so retention is available in all editions of 2017+. [DER S460,S463-S466: the article has no edition limit and every edition supports temporal]
- Automatic cleanup needs the database flag `is_temporal_history_retention_enabled` = ON (default ON; turned OFF after a point-in-time restore). It also needs a clustered B-tree history index that starts with the period end column, or a clustered columnstore. [DOC S460]

_Agent: infra_

## Q17. GitLab: which tier provides *prevent approval by author* and approval rules?
- Premium or Ultimate, on GitLab.com, Self-Managed and Dedicated. This covers the approval settings page (Prevent approval by merge request creator, Prevent approvals by users who add commits, Prevent editing approval rules) and the approval rules page. [DOC S440,S442]
- Free: approvals exist but are optional and don't block merging. Any user with the Developer role or higher can approve. [DOC S441]
- Enforcing these settings instance-wide (Admin > Push rules > Merge request approvals) is Premium/Ultimate on Self-Managed and Dedicated only. On GitLab.com the top-level group setting cascades to projects and locks them. [DOC S443,S440]
- The default in the 19.5 docs: the author cannot approve (the checkbox is on by default). Committers can approve unless the committer setting is enabled. [DOC S440,S442]
- CODEOWNERS and "Require Code Owner approval" are also Premium/Ultimate. [DOC S450,S444]

_Agent: infra_

## Q18. Can a GitLab Runner on Windows run as a gMSA?
- GitLab's Windows install docs cover only the Built-in System Account (recommended) or a user account with `--user` and `--password`. The docs don't mention gMSA for the runner service. [DOC S406]
- The `install` command passes `--user`/`--password` to the Windows service config. Its help text marks `--password` as "(required)". [DOC S413]
- Microsoft: services configured through Service Control Manager, and Task Scheduler tasks, support gMSA logon identities. [DOC S400]
- GitLab issue 27895 (closed; milestone 15.5): the contributor says the runner service already works under a gMSA with `gitlab-runner install --user "DOMAIN\name$"` and no password. They ask for the docs to drop "(required)". The docs-update issue 30963 is still open. [COMMUNITY S414,S415]
- Conclusion: technically plausible, since the runner is an SCM service and SCM services accept gMSA. GitLab doesn't document or state support for it. Treat it as undocumented and verify on a lab host. [DER S400,S406,S413]
- Separately, gMSA **inside** `docker-windows` jobs is supported through `[runners.docker] security_opt` (credential spec, since 15.5). [DOC S408] [COMMUNITY S414]

_Agent: infra_

## Q19. ConfigMgr baselines: the minimum evaluation interval; the size limit on a CI script's output.
- Minimum evaluation interval: not documented. [UNK]
- The evaluation schedule is a schedule token; `SMS_ST_RecurInterval` allows MinuteSpan 0-59, HourSpan 0-23, DaySpan 0-31, so the token format can express minute intervals; no documented floor. [DER S231,S232]
- Actual run time: within a 2-hour randomization window of each scheduled start (device-targeted); first run may wait up to 24 h for idle/power launch conditions on Windows client; manual re-evaluation results cached 15 min. [DOC S202,S203]
- CI script output size limit: not documented. [UNK]
- For comparison only: Run Scripts output is truncated to 4 KB, and application detection scripts are limited to 32 KB of script text; neither is stated for CI scripts. [DOC S233,S227]

_Agent: mecm1_

## Q20. Can the DSC 3.3.0 `Microsoft.Windows/Service` and `FirewallRuleList` resources run `--what-if` from `dsc config set`?
- Yes, natively. Both 3.3.0 manifests put `{"whatIfArg": "--what-if"}` in `set.args` with `whatIfReturns: state`, so dsc passes `--what-if` to `windows_service.exe` / `windows_firewall.exe` and reports the SetWhatIf capability. [DOC S114,S106,S105]
- Both executables honour the flag and return projected state without applying it. The service resource routes `_exist: false` to a delete simulation. The firewall resource returns `_metadata.whatIf` messages for create/remove. [DOC S138,S139]
- Both declare `set.requireSecurityContext: elevated`, and dsc checks this before running what-if. A non-elevated `dsc config set --what-if` fails for these instances (exit 2). [DOC S105,S114]
- `FirewallRuleList` declares `implementsPretest: true`. This only matters for resources *without* native what-if (they get the "cannot process what-if" error). Firewall has native what-if, so it is not affected. [DOC S105,S114]
- For resources without native what-if and without pre-test, `dsc config set --what-if` returns the `test` result as the set result (synthetic what-if) and never runs set. With pre-test declared, it errors. [DOC S105,S140]
- Not exercised on a Windows host for this kb (the analysis is from code and manifests). [UNK]

_Agent: dsc_

## QA1. Does the AdminService require Kerberos, or fall back to NTLM?
- Since ConfigMgr 2509, the AdminService rejects NTLM outright and logs "Rejecting NTLM authentication"; Kerberos/Negotiate with a correct SPN and FQDN is required. [DOC S307]
- A community report confirms clients that previously relied on NTLM fallback (bad SPN, non-FQDN access) fail after upgrading past 2509 instead of degrading gracefully. [COMMUNITY S1213]

_Agent: auth_

## QA2. When does a new AD group→ConfigMgr role mapping take effect?
- Kerberos group SIDs are baked into the TGT's PAC at ticket-issue time, so generally a new logon/new TGT is needed. [DER S1218,S1344: SMS Provider resolves the caller's Windows identity; group SIDs travel in the ticket] Whether a TGT renewal (not a new logon) refreshes the group SIDs is not confirmed. [UNK, LAB in gaps.md]
- Role-based administration fundamentals confirms the SMS Provider computes an admin's effective scope (roles+scopes+collections) from the caller's Windows/AD identity via an `SMS_Admin` object, but does not state a provider-side cache or refresh interval on top of the Kerberos identity. [DOC S1218]
- Checked 3 distinct official pages (role-based administration fundamentals, configure role-based administration, plan for the SMS Provider) plus the `SMS_Admin` WMI class reference: none states a cache/refresh behaviour beyond the underlying Kerberos ticket. Confirmed UNK per the 3-attempt rule; a LAB line is recorded in `configmgr-rbac-auth.md` and `gaps.md`. [UNK]

_Agent: auth_

## QA3. Does Protected Users break a Kerberos-only, no-delegation client design?
- No NTLM and no delegation match a Kerberos-only, no-delegation client design. [DOC S1205]
- AES-only Kerberos is compatible with modern DCs/SPNs. [DOC S1205]
- The 4-hour, non-renewable TGT is the one real constraint: an engineer's Kerberos-backed session (AdminService, SQL) needs re-authentication every 4 hours; this does not break correctness but changes the UX (no all-day unattended session). [DOC S1205]
- Any leg that silently depends on NTLM fallback (IP address or short name instead of FQDN, missing `MSSQLSvc/` SPN for SQL) fails outright for a Protected Users member, since NTLM is not available to them. [DER S1205,S307]
- Implication for a similar client: audit every call path for a hidden NTLM fallback (non-FQDN endpoints, missing SPNs) before enrolling engineer accounts in Protected Users.

_Agent: auth_

## QA4. GitLab OIDC -> Entra federation: sub for protected tags, per-app FIC limit, flexible FIC status
- Flexible/mutable-subject federated identity credentials exist as a documented Entra feature, distinct from exact-subject FICs, letting one credential match a pattern of GitLab tags. [DOC S1278]
- Per-app/per-user-assigned-managed-identity limit: **20 federated identity credentials**; FICs don't consume the tenant service-principal quota. [DOC S1293]
- Flexible FIC status: **preview**. Supported issuers named explicitly: GitHub, GitLab, Terraform Cloud. Expression language matches claim/operator/comparand (for GitLab: `sub` plus `project_id`/`namespace_id`/`user_id`); manageable only via Graph or the Azure portal. [DOC S1294]
- Exact GitLab `sub` for a tag pipeline (confirmed against docs.gitlab.com, not just search snippets): `project_path:{group}/{project}:ref_type:tag:ref:{tag_name}`, or with the immutable-subject option, `project_id:{id}:ref_type:tag:ref:{tag_name}`. [DOC S1276]

_Agent: auth_

## QA5. MSAL Python + WAM on Windows 11/Server 2025; device code flow blocking
- `msal[broker]>=1.33,<2`; Windows 10+/Server 2019+ only; redirect URI `ms-appx-web://microsoft.aad.brokerplugin/<client_id>`; needs a window handle, with `CONSOLE_WINDOW_HANDLE` provided for CLI apps. [DOC S1270]
- IWA silent token acquisition works for public clients on a domain- or Entra-joined Windows machine, independent of WAM. [DOC S1271]
- Conditional Access has a dedicated "Authentication flows" condition that can target and Block device code flow specifically; Microsoft recommends blocking it wherever possible as high-risk. [DOC S1272][S1273]
- Explicit headless/jump-host WAM caveats beyond "supported OS": [UNK].

_Agent: auth_

## QA6. Token Protection and MSAL Python public clients
- Token Protection (Conditional Access) binds refresh tokens to the device via proof-of-possession; documented scope is desktop apps accessing Exchange Online/SharePoint Online on Windows. [DOC S1274][S1227]
- Whether it applies to a bespoke MSAL Python public client's Graph calls: [UNK] — not stated either way in the fetched deployment/concept pages.
- Token Protection: native apps only (Client Apps condition = "Mobile apps and desktop clients"); browser-based clients (MSAL.js, Teams Web) excluded and can be blocked if Client Apps is left unscoped to Browser. Windows is GA; macOS/iOS preview since early 2026. Requires Entra ID P1. [DOC S1274]
- No page names "MSAL Python" specifically; the boundary is by client type (native vs. browser), so a Windows MSAL Python CLI is architecturally the kind of client the feature targets, but this is derived, not stated. [DER S1274]
- `cp1`/CAE readiness in MSAL Python: `PublicClientApplication(client_id, client_capabilities=["cp1"])`; declares the client capable of handling claims challenges so Entra may issue CAE tokens for CAE-aware resources; app must decode a returned `claims` challenge and re-acquire with `claims=<value>`. Independent of Token Protection. [DOC S1296]

- P2 delegation findings (OBO, KCD/RBCD, App Proxy, MCP enterprise-managed authorization, Teams bot SSO) are in `auth/delegation-kcd-obo.md`. [DER S1297,S1298,S1299,S1301]

_Agent: auth_

## QA7. Group overage thresholds, recommended pattern, nested groups into app roles
- Token group-list caps: 200 (JWT), 150 (SAML); both counts include nested/transitive membership. [DOC S1284]
- "Groups assigned to the application" claim mode avoids overage but excludes nested-group members. [DOC S1285]
- Microsoft's recommended authorization pattern is app roles assigned to groups (smaller token, more secure, separates assignment from app config). [DOC S1285]
- Nested groups: no. Group-based assignment to an application (and so app roles assigned to a group) reaches only direct members: it does not cascade to nested groups, and it requires Entra ID P1 or P2. [DOC S1310]

_Agent: auth_

## QA8. Entra Connect Sync / Cloud Sync intervals; group writeback status
- Entra Connect Sync: 30-minute default and minimum supported cycle. [DOC S1279]
- Cloud Sync: user/group provisioning ~10-20 min; password hash sync 2-5 min. [DOC S1280]
- Group writeback via Cloud Sync: on-prem AD provisioning job runs ~every 20 minutes; the feature is live and documented as of this retrieval (2026-09-24), i.e. shipped, not preview. [DOC S1281]

_Agent: auth_

## QA9. PIM for Groups activation latency in tokens / checkMemberGroups; reach to on-prem AD
- PIM for Groups manages cloud-only Entra groups; on-prem AD is reached only via Cloud Sync group writeback, adding that job's own ~20-minute cycle on top of activation. [DOC S1282][S1283][S1281]
- A token already issued/cached does not reflect an activation until the client acquires a new token (no forced push-refresh of live tokens on activation). [DOC S1282]

_Agent: auth_

## QA10. AD temporary group membership: requirements, irreversibility, TTL vs Kerberos ticket lifetime
- Requires forest functional level 2016+; enabling the PAM optional feature is irreversible (schema extension, no disable). [DOC S1211]
- TTL vs Kerberos ticket lifetime, now confirmed: the "expiring links" feature (Windows Server 2016) propagates the group's TTL directly into the issued TGT's lifetime, capping it to the remaining TTL of the shortest-lived time-bound group the user belongs to. [DOC S1219]
- Remaining gap: whether an admin removing the TTL membership *before* natural expiry invalidates an already-issued (TTL-capped) ticket immediately, or only at its own expiry. [UNK, LAB — see gaps.md]

_Agent: auth_

## QA11. DPAPI-NG with a group `SID=` descriptor: requirements; Python access; behaviour when the user leaves the group; recovery if the group is deleted
- `SID=<group-or-principal-SID>` is a valid protection-descriptor rule string for `NCryptCreateProtectionDescriptor`; only that SID principal or a member of that SID group can decrypt with `NCryptUnprotectSecret`. [DOC S1342, S1343]
- No first-party Python binding exists; a community package (`dpapi-ng`) implements the MS-GKDI client protocol in pure Python, aimed at decrypting DPAPI-NG blobs from non-Windows hosts by talking to a DC over RPC; it is unofficial. [COMMUNITY S1349]
- Whether an already-decrypted secret stays usable after the user leaves the group without a new logon, and recovery behaviour if the group is deleted, were not found in the pages fetched. [UNK] -- see gaps.md.

_Agent: auth_

## QA12. SQL Server Always Encrypted with Microsoft's Python drivers (`mssql-python`, pyodbc + ODBC 18): supported? CMK in the Windows certificate store; limits
- `pyodbc` + ODBC Driver 18 supports Always Encrypted via `Column Encryption Setting=Enabled` in the connection string. [DOC S1340]
- A column master key can be a certificate in the Windows Certificate Store (`LocalMachine`/`CurrentUser`, provider `MSSQL_CERTIFICATE_STORE`); a machine-store certificate must be replicated to every machine that decrypts. [DOC S1341]
- Microsoft's own pure-Python-oriented driver, `mssql-python`, has no Always Encrypted item, done or planned, in its public roadmap. [DOC S1350] Its Learn overview is the canonical status page to recheck. [DOC S1351]
- Net: Always Encrypted is achievable from Python today, but only via `pyodbc` (a C-extension driver), not via `mssql-python`; neither path is "pure Python" in a strict sense. [DER S1340,S1350]

_Agent: auth_

## QA13. SQL Server 2022/2025 on-prem Entra authentication: Arc required? Groups supported?
- Yes, Azure Arc-enablement is required for on-prem Entra authentication; SQL Server 2025 (17.x) adds a "primary managed identity" model via the Azure Extension for SQL Server (portal steps differ from earlier versions). [DOC S1206]
- Entra security groups are supported for authorization, the same way AD groups map to Windows Authentication logins. [DOC S1206,S1207]

_Agent: auth_

## QA14. SMB signing/encryption defaults in Windows 11 24H2 / Server 2025: impact on gMSA and package-share reads
- Windows 11 24H2 Enterprise, Pro and Education require outbound and inbound SMB signing by default; Windows Server 2025 requires outbound signing only; 24H2 Home requires neither. [DOC S1202]
- SMB encryption is not mandatory by default. Windows 11 24H2 / Server 2025 add a client option to mandate encryption for all outbound connections; once enabled, the client connects only to SMB 3.0+ servers that support encryption. [DOC S1228]
- Impact: a gMSA-based CI runner or a workstation/device reading a network file share over SMB must support SMB signing (no unsigned fallback on 24H2 Enterprise/Pro/Education clients); encryption matters only if the client-side mandate or share-level encryption is turned on. [DER S1202,S1228]

_Agent: auth_

## QA15. LDAP signing/channel binding defaults in Server 2025; which Python LDAP libraries can bind with Kerberos + signing/sealing + channel binding on Windows?
- New AD deployments require LDAP signing by default; channel binding defaults to "when supported" with auditing on. [DOC S1201]
- `ldap3` (pure-Python, uses `gssapi`/`winkerberos`): supports Kerberos/GSSAPI bind and channel binding (via TLS/LDAPS), but does **not** implement SASL security-layer wrapping (sign/seal) for the LDAP protocol itself — it errors if the server insists on a security layer. [DOC S1208, COMMUNITY S1209]
- `python-ldap` documents a `sasl_gssapi_bind_s()` convenience method for GSSAPI binds, but is a thin wrapper over the platform's native LDAP/SASL library; its docs don't state whether the Windows build negotiates a true sign/seal security layer — this stays UNK pending a lab test. [DOC S1220 for the API; UNK for Windows sign/seal behaviour, LAB — see gaps.md]
- pywin32/ADSI (`ADsOpenObject`/`IADsOpenDSObject::OpenDSObject` via COM): Microsoft's own ADSI docs confirm `ADS_USE_SIGNING`/`ADS_USE_SEALING` flags (requiring `ADS_SECURE_AUTHENTICATION` and domain-joined Kerberos) provide documented sign/seal support — this is the one Microsoft-documented Python-reachable (via COM) path with confirmed sign+seal, at the cost of being Windows-only/COM-based rather than pure Python. [DOC S1221]
- General implication: prefer LDAPS (TLS) for a service host talking to AD with `ldap3` (Kerberos for the bind only), or pywin32/ADSI with `ADS_USE_SIGNING|ADS_USE_SEALING` if a true LDAP-layer security layer over plain `ldap://` is required; `python-ldap`'s Windows sign/seal behaviour needs a lab check before relying on it. [DER S1201,S1208,S1220,S1221]

_Agent: auth_

## QA16. NTLM deprecation timeline; RC4-in-Kerberos deprecation dates
- NTLM: NTLMv1-derived SSO credentials audited from the Sep 2025 updates (event 4024) and blocked later via `BlockNTLMv1SSO` (event 4025) [DOC S-q5hl3fyg]; the NTLM programme itself: auditing now, IAKerb + Local KDC in H2 2026, network NTLM off by default in the next major Windows Server release. [DOC S1200]
- RC4-in-Kerberos, now dated: a KDC-side change for service-account ticket issuance tied to CVE-2026-20833 ships in updates on/after 2026-01-13, KB5073381 (phased via `RC4DefaultDisablementPhase`); `DefaultDomainSupportedEncTypes` defaults to AES-only (0x18) on updates released on/after 2026-04-14; the audit-mode registry key is retired in the 2026-07 update, making AES-only unconditional. [DOC S1215,S1216,S1217]

_Agent: auth_

## QA17. Does Microsoft classify ConfigMgr as Tier 0 / control-plane? Official admin-security guidance?
- No explicit "ConfigMgr = Tier 0" statement found in the enterprise access model, PAW or Windows LAPS docs reviewed this session (S1210, S1212, S1225, S1226). [UNK]
- The enterprise access model generically defines a control plane whose compromise grants full environment control, and recommends PAWs + Windows LAPS + MFA universally; MFA for SMS Provider calls has been available since CB 1702 as the concrete lever. [DOC S1210,S1212,S1225,S1226]
- KB5014754 (certificate strong-mapping) reached Full Enforcement on 2025-02-11 — directly relevant admin-security guidance for any certificate-based auth touching the SMS Provider/domain controllers. [DOC S1224]
- Derived judgement (not an official Microsoft label): ConfigMgr's device/config control over the whole estate fits the control-plane definition. [DER S1210,S1212]

_Agent: auth_

## QA18. checkMemberGroups / getMemberGroups least privilege, limits, caching, CAE interplay
- `checkMemberGroups`: signed-in user (`/me`) delegated `User.Read` (no application support); other users `User.ReadBasic.All` + `GroupMember.Read.All` (delegated or application); any directory object `Directory.Read.All`. At most 20 group ids per call; membership is transitive. [DOC S1286]
- `getMemberGroups`: user target `User.ReadBasic.All` + `GroupMember.Read.All`; any object `Directory.Read.All`. [DOC S1287]
- So a client-side role check against a small fixed set of role groups fits one `/me/checkMemberGroups` call under `User.Read`. [DER S1286]
- Call-specific throttling limits, caching guidance and CAE interplay for these two methods specifically: [UNK] — not stated on the API reference pages fetched.

_Agent: auth_

## QA19. For each system (AdminService, Graph, SQL, SMB, GitLab), how long until an engineer loses access after (a) AD disable, (b) Entra disable + revokeSignInSessions, (c) removal from a role group?
- (a) AD account disable, corrected to three windows after re-checking MS-KILE per the lead's request: a brand-new sign-on (AS-REQ) is rejected immediately; a *new* service-ticket request on an existing TGT is rejected once Windows's MS-KILE account-revocation check fires -- **20 minutes** after the TGT was issued (`[MS-KILE]: Account Revocation Checking`, `[MS-KILE]: Check Account Policy for Every Session Ticket Request`) -- so no new AdminService/SQL/SMB session can be opened more than ~20 minutes after a disable; but a connection/session already open at disable time keeps working until its own service ticket expires, since the target server never calls back to the KDC to re-check revocation -- Microsoft's Kerberos policy page states plainly that "users whose accounts have been disabled might be able to continue accessing network services by using valid service tickets that were issued before their account was disabled," with the default `Maximum lifetime for service ticket` at 600 minutes (10 hours). [DOC S1378, S1379, S1376] This applies identically to SQL Server (Windows-auth login, existing connection) and SMB sessions, since both ride the same Kerberos service-ticket mechanism; only *new* SQL/SMB sessions are bounded by the 20-minute window, not existing ones. [DER S1376,S1378,S1379]
- (b) Entra disable + `revokeSignInSessions`: propagates in a few minutes for new sign-ins/refresh-token use. **Correction from this agent's first pass:** Microsoft Graph *is* a CAE resource and *does* enforce the documented critical events (account disable/delete, password change, admin token revocation, high risk) via a claims-challenge -- but only for a calling client that declares the `cp1` MSAL client capability. An MSAL client that declares `cp1` gets near-real-time revocation on Graph for these events; one that doesn't declare `cp1` gets ordinary tokens and keeps working until the default 1-hour access-token expiry. This is a concrete, low-cost design lever for any first-party MSAL client: declare `cp1`. [DOC S1345, S1347, S1354, S1355]
- (c) Removal from a role group: no effect on an already-issued Kerberos ticket's PAC, and *not* on the CAE critical-event list either (only account disable/delete, password change, explicit token revocation, and high risk are) -- so even a `cp1`-aware client does not get fast revocation for a bare group removal; it waits for the next token/ticket issuance that carries the group, per [[propagation-latency]].
- SQL Server: `ALTER LOGIN ... DISABLE` explicitly "doesn't affect the behavior of logins that are already connected," and disabled logins "retain their permissions and can still be impersonated" until an explicit `KILL` of the session. [DOC S1375]
- GitLab: an explicit personal-access-token revoke is immediate and synchronous; for an **Enterprise user** specifically, GitLab documents that blocking or deleting the account auto-revokes PATs. Plain-account block behaviour and the effect on CI job tokens / runner tokens / web sessions are `[UNK]`. [DOC S1377]
- Full per-system table is in `revocation.md`'s Reference table; several cells remain `[UNK]` where the fact belongs to another owned topic (`configmgr-rbac-auth.md`, `sql-authz.md` for Entra-auth-to-SQL, `gitlab-ci-identity.md`) and this pass did not duplicate that research.

_Agent: auth_

## QA20. On-prem runner Graph app-only tokens with no stored secret
- Yes, via Azure Arc-enabled server system-assigned managed identity: local endpoint `http://localhost:40342/metadata/identity/oauth2/token`, protected by a challenge-response step so an unprivileged local process cannot mint tokens for the identity. [DOC S1289][S1290]
- Also yes for the `ci` kind via GitLab OIDC → Entra workload identity federation: each job's `id_tokens` JWT is exchanged, no secret stored. Condition: Entra fetches the issuer's OIDC keys, so the GitLab instance's discovery and JWKS endpoints must be reachable by Entra ID; an internal-only GitLab cannot be the issuer. [DOC S1278,S1276,S1302]
- Trade-off: CAE for workload identities (fast revocation on SP disable/delete) covers single-tenant service principals, not managed identities, so the Arc path gives up CAE. [DOC S1306]
- Cost/requirement: Arc enrollment brings an Azure control-plane object, the Connected Machine agent as an additional always-on process on the host, and outbound HTTPS to Arc endpoints — a real cost for any design that intends no gateway/extra always-on service. [DER S1289]

_Agent: auth_

## QS1a. CIS benchmark versions and reuse terms (coordinator addendum)
- Microsoft's OSConfig Server 2025 baseline v2606 (MIT) publishes a `CIS RuleID` and `CIS Control` column for 329 of 361 settings. That is a Microsoft-published crosswalk to a CIS Windows Server 2025 benchmark; the benchmark version is not stated. [DOC S1598]
- `settings-crosswalk.csv` column `cis_ws2025_id_via_osconfig` carries 152 of these ids. No CIS text is copied. [DER S1598]

_Agent: security_

## QS1. CIS benchmark versions/dates and terms for reuse of IDs/titles
- CIS Microsoft Windows 11 Enterprise Benchmark current version is v5.1.0 (published 2026-09-16
  per publication-date digest; preceded by v5.0.0 in March 2026 and bugfix v5.0.1 in April 2026)
  [DOC S1405, S1406, S1407, S1408].
- A CIS Microsoft Intune for Windows 11 Benchmark v4.0.0 exists per a third-party mirror of CIS
  release notes; not confirmed directly on cisecurity.org this pass [COMMUNITY].
- Terms for reuse: non-member CIS Benchmark PDFs are distributed under **CC BY-NC-SA 4.0**
  (attribution, non-commercial, share-alike); CIS-SecureSuite members are separately barred from
  redistributing or creating derivative "images" of benchmark content [COMMUNITY — summarized via
  search digest of cisecurity.org's terms pages; a direct fetch of
  cisecurity.org/terms-of-use-for-non-member-cis-products returned HTTP 404 in this pass, so this
  needs a direct re-read before treating as `DOC`]. Under CC BY-NC-SA 4.0's attribution/share-alike
  terms, an ID plus a short (≤8-word) paraphrase with attribution is consistent with non-commercial
  internal use, but this pass does not treat that as confirmed (`settings-crosswalk.csv` still
  carries no CIS IDs — see `gaps.md`).

_Agent: security_

## QS2. Microsoft Windows 11 baseline: settings by mechanism, share native DSC v3 can express
- The latest package retrieved is the Windows 11 v24H2 Security Baseline (files dated 2024-09-30). It has **426 settings**:
  - 335 registry (Administrative Templates `registry.pol`; 135 of them in the IE11 GPOs);
  - 41 security policy (32 registry-backed security options + 9 account/system-access values);
  - 23 user rights;
  - 23 advanced-audit subcategories;
  - 4 services. [DOC S1472]
- Native DSC v3 (`Microsoft.Windows/Registry`, `Microsoft.Windows/Service`) can express **371 of 426 (87.1%)**, or **236 of 291 (81.1%)** without IE11. The other 55 need `SecurityPolicyDsc` or `AuditPolicyDsc` through the Windows PowerShell adapter. [DER S1472,S1473: classification in `security/settings-crosswalk.csv`]
- For comparison: DISA Windows 11 V2R9 is 131 of 257 native (51.0%); Server 2025 V1R3 is 97 of 291 (33.3%). [DER S1470,S1471]
- The 25H2 package was not retrieved (its file name on the download host was not found). The 25H2 changes are in `security/baselines-catalog.md`. [UNK]

_Agent: security_

## QS3. Maintained DSC resources for security policy, user rights, advanced audit under the v3 adapters
- `SecurityPolicyDsc` (dsccommunity, MIT):
  - four MOF resources: AccountPolicy, SecurityOption, SecurityTemplate, UserRightsAssignment;
  - not class-based;
  - last stable 2.10.0.0 (2019-09-19), last prerelease 3.0.0-preview0006 (2021-05-21);
  - repository active but no release since 2021. [DOC S1594,S1596]
- `AuditPolicyDsc`: MOF resources (AuditPolicySubcategory, GUID, Option, Csv); not class-based; last release 1.4.0.0 (2019-01-10); last push 2019-02-13. [DOC S1595,S1596]
- Script/MOF PSDSC resources can run only through the Windows PowerShell adapter. The PowerShell 7 adapter handles class-based resources only. [DOC S1473,S1474]
- The adapter has no what-if, so `set --what-if` returns an error for these resources. [DOC S114]
- No official page states that either module was tested with DSC v3. Running them needs a lab check. [UNK]

_Agent: security_

## QS4. GPO vs a DSC-managed registry value: what wins, when, and what `test` reports
- Group Policy applies local, then site, domain and OU GPOs. The GPO closest to the object wins unless a link is enforced. [DOC S1592]
- The background refresh runs every 90 minutes plus up to 30 random minutes (DCs: 5 minutes). [DOC S1592]
- By default, a client-side extension reapplies its settings only when its GPOs or its GPO list changed. [DOC S1592]
- So a DSC `set` that contradicts a GPO keeps its value until one of: a GPO change, a forced refresh, a foreground refresh at startup, or a "process even if unchanged" setting. After that, GPO wins. [DER S1592]
- `MDMWinsOverGP` is 0 by default. It covers only Policy CSP settings with a GP mapping, not plain registry values or other CSPs. [DOC S1412]
- Co-managed devices with the Device configuration workload on Intune evaluate ConfigMgr baselines only when the baseline has *Always apply this baseline even for co-managed clients*. [DOC S1593]
- DSC `test` compares the live value to the document and does not report who wrote it:
  - GPO value equal to the document: in desired state;
  - GPO value different: drift at every evaluation. [DER S1592, `dsc/manifests-diff.md`]
- Tattooing rules for `Policies` keys were not confirmed from an official page this pass. [UNK]

_Agent: security_

## QS5a. Microsoft baseline (GPO) vs Intune security baseline (coordinator addendum)
- The Intune "Security Baseline for Windows, version 24H2" states:
  - its settings come from the Windows 11 24H2 security baseline in the Security Compliance Toolkit;
  - it includes only the settings that apply to Windows devices managed through Intune. [DOC S1475]
- Intune Windows baseline versions: 25H2, 24H2, 23H2 and older formats. Each new version makes older profile instances read-only. [DOC S1475,S1476]
- 164 of the 335 registry settings of the GPO baseline appear by name in the Intune 24H2 pivot. Name matching undercounts, because some Intune settings use CSP names. [DER S1472,S1475]
- A security baseline delivered by Intune is subject to `MDMWinsOverGP`, which defaults to 0: GP wins for mapped settings. [DOC S1412]

_Agent: security_

## QS5. Microsoft baseline (GPO) vs. Intune security baseline differences
- Setting-by-setting comparison **not performed** this pass [UNK] — requires the SCT spreadsheet
  (still not downloaded by Part A; coordinator obtained a direct zip URL separately, see below) and
  Intune baseline profile exports (not fetched this pass).
- One documented product-level difference: the Intune Defender for Endpoint baseline is explicitly
  *not recommended* for virtual machines or VDI endpoints, a restriction that has no equivalent
  statement in the GPO-based Microsoft Security Baseline [DOC S1422]. Recorded in `gaps.md` that the
  full comparison still needs the machine-readable sources.

_Agent: security_

## QS6. Current DISA STIG for Windows 11 and Server 2025 (version, release, XCCDF location, licence)
- Windows 11 STIG: **V2R9**, XCCDF dated 2026-08-06, zip `U_MS_Windows_11_V2R9_STIG.zip` at
  `dl.dod.cyber.mil` (pinned artifact obtained by coordinator) [DOC S1470].
- Windows Server 2025 STIG: **V1R3**, zip `U_MS_Windows_Server_2025_V1R3_STIG.zip` (pinned artifact
  obtained by coordinator; exact XCCDF date not independently confirmed by Part A) [DOC S1471].
- Licence: unclassified DISA STIG content is publicly distributable without restriction —
  Distribution Statement A ("approved for public release, distribution unlimited") — posted at
  public.cyber.mil / dl.dod.cyber.mil with no sign-in required [DOC S1409, S1411 for the no-sign-in
  fact; the Distribution Statement A wording itself is `COMMUNITY` pending a direct read of a STIG
  zip's own Readme or DoDI 5230.24].

_Agent: security_

## QS7a. OSConfig baseline definitions for Server 2025 (coordinator addendum)
- **Yes, machine-readable.** `microsoft/osconfig/security/SecurityBaseline_WindowsServer_2025-<ver>.csv` exists for 2409, 2411, 2504, 2510 and 2606. Each row gives:
  - the registry key, value and type, or the CSP path;
  - default and expected values per role (DC, member, workgroup);
  - severity, CIS RuleID, STIG id, NIST 800-53 and change risk. [DOC S1598]
- Mapping: 271 of 361 rows (2606) name a registry key, so they map directly to `Microsoft.Windows/Registry`. The 52 Security Policy and 34 Audit Policy rows need `AccountPolicy`/`UserRightsAssignment`/`AuditPolicy`, which exist as OSConfig CLI resources but not as DSC v3 resources. [DOC S1598,S1599] [DER S114]

_Agent: security_

## QS7. OSConfig baseline definitions for Server 2025: machine-readable, mappable?
- OSConfig ships as the `Microsoft.OSConfig` PowerShell module (PowerShell Gallery), with three
  role-based baseline profiles (Domain Controller, Member Server, Workgroup Member) covering 300+
  settings including TLS 1.2+, SMB 3.0+ and credential protections [DOC S1424].
- OSConfig baselines are **remediating**, not test-only: once applied, settings are described as
  automatically protected from drift — i.e. OSConfig itself corrects deviations. [DOC S1424]. This is
  a meaningful framing difference for any test-mode drift-detection design built on ConfigMgr
  baselines: if a device already has an OSConfig baseline applied and remediating, a separate DSC
  `test` layer would observe a value OSConfig keeps re-asserting, similar in shape to the GPO-tattooing
  concern in `policy-precedence.md`.
- Whether OSConfig baseline definitions are published as structured data (JSON/YAML) that could be
  diffed against DSC v3 resource state, versus only exposed via the PowerShell module's own cmdlets,
  was **not confirmed** this pass — the `microsoft/osconfig` GitHub repository itself was not opened
  [UNK — see `gaps.md`].

_Agent: security_

## QS8. Microsoft's official ConfigMgr security guidance items relevant to hardening a management plane
- **AdminService**: exposed via CMG for internet access when the SMS Provider is explicitly configured to allow it (opt-in, not default); CMG requires mutual HTTPS with either a PKI client certificate or Microsoft Entra ID auth, and CMG only maps endpoints it is explicitly told to publish. [DOC S1483] (see also `mecm/run-scripts.md`, `auth/configmgr-rbac-auth.md` for route-level detail, not duplicated here)
- **CMPivot**: permission requirements were simplified from ConfigMgr current branch 2107 onward (no longer requires SMS Scripts read permission or a default security scope). [DOC S1480] (full entity/permission reference already in existing kb parts, not duplicated)
- **Run Scripts approval**: by default a script author cannot approve their own script; "Script authors require additional script approver" is a hierarchy setting that should only be relaxed in a lab, per Microsoft's own recommendation (already documented in `mecm/run-scripts.md`). No signing requirement is layered on top of approval — see QS18. [DOC S1520]
- **MFA for SMS Provider**: available since ConfigMgr current branch 1702; requires an MFA claim (Windows Hello for Business/smart card) on the caller's token for SMS Provider, console, SDK and AdminService calls; it is a hierarchy-wide, Full-Administrator-only setting. [DOC S1482]
- **NTLM and client push**: client push installation uses NTLM by default and is documented as the least-secure client install method; from ConfigMgr 1806 the site can require Kerberos mutual auth, and from 2207 "Allow connection fallback to NTLM" is disabled by default on new installs (Microsoft recommends disabling it on existing sites too). [DOC S1484]
- **Enhanced HTTP**: plain HTTP client communication has been deprecated since ConfigMgr 2103; Microsoft's stated preference is PKI-certificate HTTPS, with Enhanced HTTP (site-issued self-signed certs) as the fallback when full PKI is not deployed — Enhanced HTTP and PKI HTTPS can coexist site-system by site-system. [DOC S1480]
- Full detail is in `security/management-plane-hardening.md`.

_Agent: security_

## QS9. CIS benchmarks for SQL Server and for GitLab
- A CIS benchmark **exists for Microsoft SQL Server**, published per major version — CIS Microsoft SQL Server 2022 Benchmark (versions up to v1.3.0 seen) and a CIS Microsoft SQL Server 2025 Benchmark (v1.0.0 referenced). Exact current version/date needs direct confirmation on the CIS listing page (`gaps.md`). [DOC S1486]
- A CIS benchmark **exists for GitLab** — the CIS GitLab Benchmark, first published jointly by GitLab and CIS, announced 2024-04-17, with 125+ configuration recommendations; an open-source scanner (`gitlabcis`) implements its checks and is a live reference for check IDs. Exact current version/date likewise needs direct confirmation on the CIS listing page. [DOC S1487,S1489]

_Agent: security_

## QS10. Polish NIS2 transposition status, entity criteria, Art. 21 measures
- The KSC amendment transposing NIS2 was adopted 2026-01-23, published as Dz.U. 2026 poz. 252, in force
  2026-04-03, with a registration deadline of 2026-10-03 and security-management-system deadline 2027-04-03.
  [DOC S1553][COMMUNITY S1554]
- Poland missed the original 2024-10-17 deadline; the Commission opened infringement proceedings (reasoned
  opinion 2025-05-07). [COMMUNITY S1554]
- Entity criteria come from NIS2 Annexes I/II (sector) plus size thresholds; the Directive itself, not the kb,
  decides scope. [DOC S1552]
- Art. 21(2) letters touching configuration management (d, e), logging (a, g), access control (i, j) and supply
  chain (d) are listed in `security/privacy-compliance.md`. [DOC S1552]

_Agent: security_

## QS11. EDPB DPIA criteria applicable to a device-log/AI-processing flow
- WP248 rev.01's nine criteria are listed in `security/privacy-compliance.md`; criteria 3 (systematic
  monitoring), 4 (sensitive/highly personal data via employee-linked device logs) and 6 (matching/combining
  datasets, if pseudonymized data sent to an LLM is combined with other stores) are the ones most plausibly met
  by a device-log/AI-processing system of this general kind.
  [DOC S-xvc5ligo][DER S-xvc5ligo: derived by matching a typical device-log/AI-processing system's data flows to the nine criteria]
- Whether two or more criteria are actually met, and therefore whether a DPIA is required, is not decided here.

_Agent: security_

## QS12. EU AI Act classification and timeline for an internal IT-ops assistant
- The Act applies from 2024-08-01 with staggered dates: AI literacy/prohibited practices from 2025-02-02;
  GPAI-model obligations from 2025-08-02; most remaining obligations (including Annex III high-risk) originally
  from 2026-08-02. [DOC S1556][DOC S1557]
- The Digital Omnibus on AI (Regulation (EU) 2026/1744, in force 2026-07-27) defers high-risk Annex III
  obligations to 2027-12-02, and Annex I embedded-product obligations to 2028-08-02. [DOC S-qzdkyvqx]
- Whether a given model-boundary component falls under Annex III (e.g. employment-context use cases) depends on
  the specific use case and was not checked here. [UNK]

_Agent: security_

## QS13. OWASP MCP Top 10 status and identifiers
- Still "Phase 3 – Beta Release and Pilot Testing" as of 2026-09-24; ids `MCP01:2025`-`MCP10:2025` unchanged; the
  project page states no release date (re-read 2026-09-26). Matches the existing `standards/owasp.md` entry; no changes needed there beyond
  the confirmation appended. [DOC S1540]

_Agent: security_

## QS14. NIST AI 600-1 suggested actions for tool-using agents on production systems
- Restrict/monitor tool access granted to the model, log agent actions and outcomes, apply least-privilege to any
  credentials reachable by the agent, require human review before consequential actions. [DER S1542: restated from GOVERN 3.2 oversight roles, GAI incident-response actions and additional human review; not a verbatim list]
- Implication for a tiered-confirmation design: a confirm gate on consequential actions, an append-only operation audit table, and narrower agent device limits all satisfy this guidance. [DER S1542]

_Agent: security_

## QS15. MITRE ATT&CK mitigations/detections for T1072 as applied to ConfigMgr/Intune
- T1072 covers abuse of legitimate software-deployment/configuration-management tools for lateral movement and
  execution; ConfigMgr baselines and Run Scripts are exactly this class of tool. ATT&CK version at retrieval is
  v19.2 (2026-08-06). [DOC S1565][DOC S1564]
- T1072 has 9 official mitigations (M1029, M1033, M1017, M1030, M1027, M1018, M1026, M1032, M1015, M1051) and one
  detection strategy, DET0223 "Detection of Adversary Abuse of Software Deployment Tools," covering 5 analytics
  over log sources including `WinEventLog:Application`, `WinEventLog:Security`, `AWS:CloudTrail` and
  `auditd:SYSCALL`. Extracted from the pinned ATT&CK v19.2 STIX bundle into
  `security/artifacts/mitre/attack-subset.csv`. [DOC S1576]
- The same extraction covers all 7 requested techniques (T1072, T1484, T1098, T1558, T1078, T1219, T1562); see
  `security/threat-model-inputs.md` for the full id table. T1562 is revoked in v19.2 and replaced by T1685
  "Disable or Modify Tools," whose ids are used instead. [DOC S1576]

_Agent: security_

## QS16. Minimum log-retention recommendations, and AI-interaction-specific ones
- CIS Controls v8.1 Safeguard 8.10 recommends a **90-day minimum** for audit-log retention. [DOC S1492]
- NIST SP 800-92 (2006, still current/final; Rev.1 is only a 2023 draft) does not itself set a numeric retention figure found in this pass. [DOC S1493,S1494]
- Microsoft's Windows audit-policy guidance recommends *what* to audit, and sizes the Security event log (~192 MB minimum) rather than specifying retention in days. [DOC S1528,S1529]
- No AI-interaction-specific numeric retention figure was found from OWASP, NIST AI 600-1 or Microsoft/Anthropic; OWASP Agentic 2026 and Claude Code's OTel events cover *what* to log per tool call (inputs/outputs, tamper-evidently), NIST AI 600-1 covers provenance records, auditing and incident documentation; none says *how long* to keep it. [DOC S1526,S1527,S1498,S1500]
- A worked example (audit 400 days, device logs 30 days) is compared against the 90-day CIS minimum in `security/logging-monitoring.md`; a 30-day device-log figure falls short of it — see Conflicts.

_Agent: security_

## QS17. GitLab features for build provenance/attestation of a Python package, and tier needed
- GitLab's SLSA **Build Level 3** provenance/attestation feature (the `slsa_provenance_statement` flag plus the `ATTEST_BUILD_ARTIFACTS` CI/CD variable) requires the **project to be public** and the attested artifact to be ≤100 MB — a requirement independent of subscription tier as documented, but effectively unusable for an internal package unless the repo is made public. [DOC S1523]
- GitLab's default DevSecOps pipeline reaches SLSA Level 1-2 without the explicit attestation feature. [DOC S1524]
- GitLab dependency scanning using SBOM (GA in 19.0, Ultimate) generates CycloneDX SBOMs itself and scans them; consuming a third-party CycloneDX SBOM works but is documented as subject to change. [DOC S1511]
- The exact GitLab **subscription tier** required for Dependency Scanning, SLSA attestation, and artifact/container signing was **not confirmed** against the official tier-comparison page in this pass — see `gaps.md`. [UNK]

_Agent: security_

## QS18. Certificate requirements for signing PowerShell scripts under AllSigned, and whether timestamping matters
- The certificate must carry the code-signing Enhanced Key Usage OID `1.3.6.1.5.5.7.3.3` and chain to a CA trusted on the target machine; the signing certificate (or its issuer) must additionally be present in the **Trusted Publishers** store, not just Trusted Root, for AllSigned to accept the script. [DOC S1513, S-utrhfg57]
- Microsoft's Trusted Root Program requires code-signing CAs to keep code-signing, server-auth, S/MIME and timestamping as separate EKU hierarchies (no combined-purpose issuing CA), and requires an RFC 3161-compliant Time Stamp Authority for any CA issuing code-signing certificates. [DOC S1513]
- **Timestamping matters**: `Set-AuthenticodeSignature -TimestampServer` embeds an RFC 3161 timestamp, which keeps the signature (and therefore the script's ability to run under AllSigned) valid after the signing certificate itself expires; an untimestamped signature stops being valid the moment its certificate expires. [DOC S1515]
- ConfigMgr Run Scripts and CI script deployment do not add a separate console-side signing gate — the client-side AllSigned execution policy setting (documented in `windows/execution-policy-signing.md`) is the only enforcement point. [DOC S1520]

_Agent: security_

## QS19. Windows 11 versions with LSA protection and Credential Guard on by default
- **LSA protection** is on by default for client devices on Windows 11 22H2 or later when all of these hold:
  - a new installation, not an upgrade;
  - enterprise-joined (AD, Entra or hybrid);
  - HVCI-capable.

  It is enabled without a UEFI variable. Audit mode is on by default from 22H2. [DOC S1477]
- **Credential Guard** is on by default from Windows 11 22H2 and Windows Server 2025 when all of these hold:
  - domain-joined and not a domain controller;
  - Enterprise or Education licence (E3/E5/A3/A5), not Pro;
  - the hardware requirements are met (VBS; Secure Boot required for CG);
  - it was not explicitly disabled before the update.

  It is enabled without a UEFI lock. [DOC S1478]
- The Microsoft 24H2 baseline raises both to UEFI-locked (`LsaCfgFlags=1`, `RunAsPPL=1`). STIG `WN11-CC-000075` requires `LsaCfgFlags=1`. A UEFI lock cannot be undone by registry or policy. [DOC S1472,S1470,S1477]

_Agent: security_

## QS20. Baseline candidates: CIS L1 / Microsoft / STIG, compatibility risks, reboot
- C3 SMB1 absent:
  - Microsoft 24H2 sets it (server `SMB1=0`, client `MrxSmb10 Start=4`); STIG `WN11-00-000160/165/170` requires it; Intune 24H2 has it;
  - SMB1 is not installed by default on Windows 11;
  - removal needs a restart, and SMB1-only devices stop working. [DOC S1472,S1470,S1475,S1590]
- C5 PowerShell 2.0 absent: STIG only (`WN11-00-000155`; Server 2025 `WN25-00-000410`). The feature was removed from Windows 11 24H2 in the August 2025 update, and `-Version 2` calls start 5.1. [DOC S1470,S1471,S1479]
- C1 long paths: in neither baseline. It only affects longPathAware apps, all processes see it only after a reboot, and GP *Enable Win32 long paths* controls the same value. [DOC S1591,S1472,S1470]
- C2 `wuauserv` start type, C4 RDP denied, C6 Remote Registry disabled: in neither the Microsoft 24H2 baseline nor STIG V2R9. No compatibility or reboot statement was found. [DER S1472,S1470: absent from both machine-readable sets] [UNK for impact and reboot]
- C7 DSC version, C8 marker: no guideline applies. C7 has no native resource in 3.3.0. [DER S114]
- CIS L1 for every candidate: not confirmed; the benchmark needs registration. [UNK, see gaps]

_Agent: security_

## QR1. What is a simple architecture for a workstation CLI + stdio MCP server managing a Windows estate?
- A minimal box list: an engineer workstation (CLI + stdio MCP server), a Git-hosted CI system (MR runners, at least one protected Windows runner), SQL Server, ConfigMgr, Entra/Graph/AD/Defender, an artifact share, and a BI tool. [DER]
- MCP and CLI can be one program: the MCP server is a subprocess the client launches over stdio. [DOC S705]
- A general implication: a scheduled sync job and a release job can share one identity/host/lock when their trust boundary is the same, rather than adding a separate always-on component with its own consumer. [DOC S1700, S1701; DER]

## QR2. How many repositories, and how to separate ownership?
- A code-plus-docs split, with separate CODEOWNERS-based approvers inside one project (or two), can be achieved via CODEOWNERS with Require Code Owner approval (Premium) and per-pattern protected tags — no separate repository is required just to get separate approval gates. [DOC S444, S445, S450]
- GitLab Pages publishes a MkDocs site from a subdirectory of any project; `mkdocs build --strict` turns warnings into failures. [DOC S1733, S1732]

## QR3. Is a gMSA broker needed for containers?
- No. Windows containers get a gMSA through a credential spec: directly on a domain-joined host, or through `ccg.exe` and a plug-in on a non-domain-joined host; Kubernetes adds the `GMSACredentialSpec` CRD and admission webhooks; AKS ships a Key Vault CCG plug-in. [DOC S1600, S1601, S1602]
- Linux containers use keytabs of conventional accounts; `adutil` needs the account password and no Microsoft page turns a gMSA into a keytab; only AWS `credentials-fetcher` claims it. [DOC S1605, S1606; COMMUNITY S1608]
- Entra workload identity covers Graph only; AdminService, LDAP and SMB still need Kerberos; SQL Server needs Arc for Entra auth; on-prem clusters need Arc-enabled Kubernetes workload identity (preview) and an Entra-reachable issuer. [DOC S1206, S1207, S1302, S1609]

## QR4. What keeps later containerization cheap?
- Secrets as mounted files or env are both allowed by Kubernetes; a policy that forbids secrets in a child process's environment should prefer mounted files, which Kubernetes also supports. [DOC S1725, S1729]
- CronJob `concurrencyPolicy: Forbid` and Job `activeDeadlineSeconds` map cleanly onto an application-level applock and time ceiling, should one exist. [DOC S1726, S1727]
- `zoneinfo` needs the `tzdata` package on Windows. [DOC S1728]
- MCP stdio forbids non-protocol output on stdout, so logs go to stderr. [DOC S705]

## QR5. Which localization-catalogue format fits a Python + PowerShell + BI stack?
- Fluent has a Python runtime (`fluent.runtime` 0.4.0) but no PowerShell or Power BI runtime was found; PowerShell's native mechanism is `.psd1` with `Import-LocalizedData`; Power BI translations cover model metadata per culture. [DOC S1709, S1712, S1713, S1714; UNK for the absence]
- With one locale and code-only script output, a plain YAML catalogue can serve Python and docs, and a SQL `label` table can serve a BI tool. [DER]

## QG1. Which runtimes run an agent unattended on a schedule, and with what permissions, limits and costs?
- Six runtimes were surveyed: `claude -p` headless CLI, the Claude Code GitHub Action, Claude Code GitLab CI/CD, Claude Code "routines" (Anthropic-hosted cloud cron/API/GitHub-event agent, research preview since April 2026), GitHub Copilot coding agent, and GitLab Duo Agent Platform's external/managed agents. [DOC S1800,S1801,S1802,S1803,S1804,S1805,S1806,S1807]
- Auth for unattended use is uniformly either a stored secret/token (`ANTHROPIC_API_KEY`, `CLAUDE_CODE_OAUTH_TOKEN`, a GitLab CI/CD masked variable, `AI_FLOW_*` tokens) or OIDC/workload-identity federation to a cloud provider (Bedrock, Vertex, Foundry, AWS/GCP via GitLab OIDC) — no runtime surveyed defaults to a human's interactive login for its scheduled path. [DOC S1800,S1801,S1802,S1806]
- All six return output as a reviewable artifact rather than a direct commit to a protected branch: a PR/MR, an inline/summary comment, or (for `claude -p` and routines with no posting tool granted) a log/session transcript a human must act on. Every branch-writing path is either a fresh branch (`claude/…`, `copilot/…`) or explicitly blocked from protected branches. [DOC S1801,S1803,S1804,S1805,S1806]
- Cost/limits differ by shape: GitHub Actions and GitLab CI/CD bill runner minutes plus API tokens and are capped only by job `timeout:`/`--max-turns`/concurrency settings the repository owner sets; routines carry a **platform-enforced daily run cap** per account plus normal subscription usage, and a **minimum one-hour schedule interval**; Copilot coding agent and GitLab Duo agents are billed under their own product's seat/credit model (not itemized in the sources fetched). [DOC S1800,S1801,S1802,S1803]
- Tension for a team that keeps "all logic... in-repo" and caps job definitions at 30 lines: the routines and Duo Agent Platform models keep the trigger/schedule config server-side (on claude.ai or on GitLab's Duo platform config), outside the pipeline file such a review would inspect — a real gap between "one job per runner and trigger, defined in-repo" and a vendor cron that lives in a web UI. The Claude Code GitHub Action's own `schedule:` trigger is the one shape that *does* stay inside a normal, reviewable `.gitlab-ci.yml`/workflow file. [DER S1801,S1803,S1806: a policy that "all logic stays in-repo" is not met by a routine's or a Duo agent's server-side trigger config, only by an in-repo `schedule:`/`rules:` block]

_Agent: agents-wiki_

## QG1 (deepening pass, 2026-09-25)
- Correction (coordinator, 2026-09-25): Claude Code `-p` does expose a hard cost cap, `--max-budget-usd` (print mode only; subagent spend counts; `Budget limit reached` on further subagent spawn; v2.1.217+), next to `--max-turns`. CI runtimes add job `timeout`. [DOC S1824]
- GitHub Agentic Workflows (`gh-aw`, MIT, GitHub Next + Microsoft Research) adds a sixth runtime shape: Markdown workflows with YAML frontmatter compiled to ordinary GitHub Actions, with a `schedule:` trigger and a named "safe-outputs" guardrail (writes buffered, validated, and applied by a separate scoped-permission job; a scanning job blocks suspicious changes). Its trigger config lives inside the repository's own compiled workflow file — the one shape among all six surveyed whose trigger config a team requiring "all pipeline logic stays in a reviewable file" could fully audit, while still being a repository-defined recurring job with no human present at fire time (a general tension for any team whose policy is that a session never schedules its own future). [DOC S1818, S-qso27noq; DER]
- No vendor here publishes a fixed cost-per-unattended-run figure; every cost basis found is a unit rate (compute minutes, API tokens, seats/credits) rather than a total. [DOC S1800,S1801,S1802,S1804,S1806,S1818]

_Agent: agents-wiki_

## QG2. Prior art for self-updating documentation
- DeepWiki (Cognition AI) regenerates a wiki from repository code, PRs, git history and team discussions, framed as a continuous convergence loop between code and docs; its exact refresh trigger (push-driven vs. periodic) is not published. [DOC S1808] Cadence: [UNK]
- Mintlify auto-generates `llms.txt`/`llms-full.txt`/per-page Markdown "from your docs on every deploy" (a documentation-publish trigger, not a code-repository trigger), and separately advertises an "agent API" for code-diff-triggered doc PRs via GitHub Actions/n8n, though that page's specifics were not independently verified this session. [DOC S1811,S1812; COMMUNITY S1810 for the agent-API specifics]
- The `llms.txt` spec itself (Jeremy Howard, v1 2024-09-03, v2 2026-08-10) defines only the file format; staying current is left to whatever regenerates it (in Mintlify's case, deploy time), governed via a public GitHub repo, Discord and issue tracker rather than any vendor SLA. [DOC S1813]
- Swimm's Auto-sync/Verify features trigger "at any relevant pull, merge, or CI test," check code snippets/tokens/paths embedded in docs against current code, auto-commit simple syncs, and fail the CI check (forcing human review) for anything too impactful to auto-sync — the clearest example among the sources found of "drift trigger from a code diff + a review gate for anything non-trivial." [DOC S1814,S1815]
- GitHub Copilot Spaces (GA 2025-09-24) is a curated-context store for chat grounding, not a scheduled or merge-triggered doc generator; it answers "what the agent reads" for ad hoc Q&A but not "what triggers an update." [DOC S1816,S1817]
- No product surveyed here (DeepWiki, Mintlify's `llms.txt` export, Swimm) commits prose documentation straight to a protected branch with no human gate for anything but the most mechanical changes; Swimm is the only one that names an explicit escalation rule (auto-sync only for changes its patented check judges "simple," Verify fails otherwise). [DOC S1814,S1815]

_Agent: agents-wiki_

## QG2 (deepening pass, 2026-09-25)
- DeepWiki's steering file, `.devin/wiki.json`, is the one explicit, repo-committed trigger found for controlling what DeepWiki generates (page list, `repo_notes` prioritizing folders); regenerating after a config change is documented as "commit the file and regenerate your wiki" — a human-initiated action, not an automatic cadence. An automatic/scheduled refresh mechanism remains undocumented in the pages fetched (two attempts). [DOC S1809; UNK for auto-refresh cadence]
- Google Code Wiki (announced 2025-11-13) regenerates repository docs after each code change; public preview for open-source repositories; private-repo Gemini CLI extension waitlisted; no review gate described. It is the one surveyed generator whose trigger is every change, with no human in the loop. [DOC S1825]
- GitHub Agentic Workflows' gallery includes a "Documentation Maintenance" sample workflow, GitHub's own scheduled/event-triggered answer to "detect drift between code and documentation and propose reviewable updates" — the most direct GitHub-native counterpart to Swimm's Verify/Auto-sync and to a Claude Code routine's "Docs drift" example. [DOC S1818, S-qso27noq]
- The AGENTS.md standard (Linux Foundation, agents.md) and GitHub Copilot's recognition of `**/AGENTS.md`, `/CLAUDE.md`, and `/GEMINI.md` as native instruction-file formats are grounding conventions an agent *reads*, not a self-updating mechanism — they answer "what the agent reads," not "what triggers an update." Notably, Copilot's own docs state it reads `/CLAUDE.md` directly with no conversion, which is relevant for any project whose own rulebook file is `CLAUDE.md` and might be read by a Copilot coding-agent task run against that repository. [DOC S1820,S1821]

_Agent: agents-wiki_

## QG3. Guardrails that keep a docs agent honest
- Vendor-documented guardrails found: Swimm's Verify check (fails CI rather than silently drifting) and its impact threshold for what Auto-sync may touch unattended [DOC S1814,S1815]; Mintlify's deploy-time regeneration of `llms.txt` (idempotent — it always reflects the last successful deploy, so there is nothing to "commit when nothing changed") [DOC S1811,S1812]; the `llms.txt` spec's own single-most-specific-file rule for scoping ("where more than one file applies, agents should use the most specific one"), which is a grounding rule rather than a security guardrail [DOC S1813].
- Community-only guardrail claims (not independently vendor-confirmed at the level of specifics): Mintlify's code-diff "agent API" auto-merge-via-ruleset-bypass pattern, and any general claim that a given tool performs secret redaction on generated docs — no source fetched this session makes an explicit, vendor-documented secret-redaction claim for a documentation agent. [COMMUNITY S1810; UNK for secret redaction]
- A house guardrail vocabulary of "strict docs build, state the present, code-owner review, unknown is never X" is not itself something any surveyed vendor publishes as a named feature — it is closer to Swimm's Verify-fail behaviour than to DeepWiki's or Mintlify's always-publish behaviour: a "strict build, plain-Markdown, state the present" regime already functions like a Verify gate, just enforced by an in-house check rather than a vendor feature. [DER S1814,S1815]

_Agent: agents-wiki_

## QG3 (deepening pass, 2026-09-25)
- Two vendor-documented deterministic guardrails were added to the survey: Vale (MIT, prose style linter, `.vale.ini` + YAML rules, CI/pre-commit) and markdownlint (MIT, 60+ Markdown structure rules, CI/pre-commit/editor) — both are a "strict build" mechanism a docs home can adopt, applied to style/structure rather than content currency; neither detects doc-vs-code drift on its own. [DOC S1822,S1823]
- gh-aw's "safe-outputs" is the most explicit vendor-named guardrail pattern found this session for keeping an unattended docs agent from writing directly: the agent job is read-only/sandboxed by default, proposed writes are buffered, a separate job with scoped permissions applies them, and a dedicated scanning job blocks suspicious changes before they land — functionally the same "propose, don't commit" shape as Swimm's Verify-fail gate, but implemented as a pipeline mechanism rather than a product feature check. [DOC S1818, S-qso27noq]
- `lychee` (link checker, named in the brief) could not be verified this session (`lychee.cc` did not resolve to the tool's actual site); `doc-detective` was not fetched at all (out of this session's URL list). Both remain open community tool candidates, not confirmed guardrails. [UNK: lychee, doc-detective]

_Agent: agents-wiki_

## QG4. How a docs home can stay current with the least machinery
- A team that requires its docs home to be plain Markdown with a strict build and "state the present: no dates, task ids or history" is holding itself to a stricter bar than every generator surveyed (DeepWiki and Mintlify's `llms.txt` both embed structural/temporal metadata by default). [DER S1808, S1811]
- Routing `texts/` and `docs/` review to a plain-language reviewer with *Require Code Owner approval* on `main` matches the "human reviews by MR" gate that Swimm's Verify/Auto-sync and every vendor CI integration surveyed (GitHub Action, GitLab CI/CD) also converge on; none of the surveyed tools bypass a merge/PR step for anything but the most mechanical export (Mintlify's own `llms.txt`, which is regenerated output of already-reviewed prose, not new prose). [DER S1801,S1802,S1811,S1814]
- A "one job per runner and trigger, all logic stays in one script or in-repo" policy is satisfiable by a merge-request-pipeline check triggered on doc-directory changes (the same shape as a what-if job triggered by config-directory changes) — this is the same trigger shape Swimm and the Claude Code GitHub Action's own `schedule:`/event triggers use, and needs no new scheduled job outside the pipeline file. [DER S1801,S1802,S1814,S1815]
- A "a session never schedules its own future" rule is in direct tension with three of the six runtimes surveyed under QG1 (Claude Code routines, GitLab Duo Agent Platform's server-configured triggers, and any recurring `schedule:` cron a GitHub Action workflow defines) to the extent their trigger configuration lives outside a single reviewable pipeline file the next check run inspects — an MR-triggered check (à la Swimm, or a what-if-style job) does not have this tension, since it fires from a human's own merge request rather than a clock the agent set. [DER S1801,S1803,S1806,S1814]

## QG4 (deepening pass, 2026-09-25)
- Vale and markdownlint (both MIT) are two concrete, off-the-shelf mechanisms that satisfy a "strict build" requirement for a docs home (style/structure) without adding a new job class beyond an existing single-checks-job shape — a rule/style-set choice, not a new mechanism, per the general principle that every mechanism should be paid for by an observed failure. [DER S1822,S1823]
- gh-aw's "Documentation Maintenance" sample and its "safe-outputs" gate confirm, from a second independent vendor (GitHub, alongside Anthropic's routines and Cognition's DeepWiki), that every scheduled/self-operating docs-agent pattern found across both research passes proposes a reviewable change rather than committing directly — reinforcing that a code-owner-approval gate on a docs directory already matches every vendor's own guardrail, and no new review mechanism is implied by adopting any of them. [DER S1818, S-qso27noq]
- GitHub Copilot's native reading of `/CLAUDE.md` (alongside `AGENTS.md`/`GEMINI.md`) means a project whose own rulebook is already a `CLAUDE.md` file needs no duplication or format conversion if a Copilot coding-agent task is ever pointed at that repository — a fact for future flexibility, not a current requirement, for any project that names Claude Code as its own work-runner. [DER S1821]

## QG5. Which products emit an "instruction(s) limit exceeded" (or similarly worded) error, with exact text and limits?
- No product in scope publishes the literal phrase "instruction limit exceeded" as a documented, stable error string.
  [DER S1840,S1841,S1842,S1843,S1844,S1845,S1846,S1847,S1860: none of the fetched official pages use this exact
  phrase]
- The closest real match is Microsoft Copilot Studio's `OpenAIAdditionalInstructionsLengthExceededLimit`, reported
  when combined prompt instructions (main agent + node + system text) cross an internal threshold, even though the
  documented per-field cap (8,000 characters) is not itself exceeded. [COMMUNITY S1843]
- M365 Copilot declarative agents document `instructions` as a schema-validated field, "must ... be 8,000 characters
  or less" — a package-validation constraint, worded as a requirement, not phrased as a runtime "limit exceeded"
  error. [DOC S1840]
- GitHub Copilot custom instructions: no error at all — past-limit content was silently ignored (old 4,000-character
  cap, now removed). [DOC S1851, S1852]
- OpenAI's ChatGPT custom-GPT builder silently blocks saving past 8,000 characters, with no confirmed banner text
  captured in this pass. [COMMUNITY S1844]
- Gemini's closest published wording is generic 400 `INVALID_ARGUMENT: Request contains an invalid argument` for an
  oversized `systemInstruction` in one reported case, and, in other reported cases against a stated token ceiling,
  "The input token count (N) exceeds the maximum number of tokens allowed (32768)." — this second phrasing is the
  closest match anywhere in this research pass to the user's "exceeds the maximum length" wording, but it is
  reported via a developer forum, not fetched from an official Gemini error-reference page. [COMMUNITY S1846]
- Claude/Anthropic: no "instructions" error type exists in the documented API error taxonomy (`invalid_request_error`,
  `rate_limit_error`, `overloaded_error`, etc. — none instruction-specific). [DOC S1847] Claude Code silently
  truncates skill `description`+`when_to_use` past 1,536 characters rather than erroring. [DOC S1860]
- **Deepening pass correction**: the earlier "~40KB CLAUDE.md warning" claim in this part is now refuted, not merely
  unconfirmed — `code.claude.com/docs/en/memory` (fetched directly) documents a 200-line soft target and a 4 MiB hard
  skip threshold for `CLAUDE.md`, no KB-based number at all; the 200-line/25KB figure applies only to the separate
  auto-generated `MEMORY.md`. [DOC S1863] The OpenAI Assistants `instructions` character limit and the Gemini
  `systemInstruction` limit both remain unconfirmed by an official numeric page after directly fetching the current
  OpenAI function-calling/structured-outputs guides and the Gemini function-calling guide in this pass — neither page
  states a character/token ceiling for these fields. [DOC S1865, S1866, S1867 for what the pages do say; UNK for the
  missing numbers, see gaps.md]
- **General implication**: no project should assume any vendor will hand it a clean,
  parseable "instruction limit exceeded" signal to build a check around — every product studied either truncates
  silently, validates at build/package time, or returns a generic 4xx. A single checks job that wants to catch
  an oversized instructions file or skill file must measure size itself against the documented numeric caps in
  `agents/instruction-and-context-limits.csv`, not grep for vendor error text. [DER, all sources above: derived from
  the absence of a common error string]

_Agent: agents-errors_

## QG6. A catalogue of common errors when running agents and MCP servers, with cause and avoidance
See `agents/agent-error-catalogue.md` and `.csv` (48 rows). Covers the Claude API's full documented HTTP/error-type
taxonomy (400/401/402/403/404/409/413/429/500/504/529) [DOC S1847], the `tool_use`/`tool_result` pairing failure
after context compaction [COMMUNITY S1858], and the 128-character tool-name limit [COMMUNITY S1857]. Per the task
instructions this extends rather than repeats `claude/tool-output-limits.md`.

**Deepening pass (this session) closed the QG6 gaps:**
- **Stdout pollution in stdio MCP servers** is now grounded directly in the MCP spec's normative language: servers
  **MUST NOT** write non-message data to stdout, **MAY** log freely to stderr, and clients **MUST NOT** treat stderr
  output as an error signal. [DOC S1861]
- **MCP timeouts** (`MCP_TIMEOUT`, `MCP_TOOL_TIMEOUT`, per-server `timeout`, `CLAUDE_CODE_MCP_TOOL_IDLE_TIMEOUT`,
  `CLAUDE_CODE_MCP_STARTUP_WAIT_MS`) are now confirmed with their actual defaults and interactions (for example the
  ~28-hour effective default when `MCP_TOOL_TIMEOUT` is unset, and stdio's 30-minute vs HTTP's 5-minute idle-timeout
  default). [DOC S1862, S1864]
- **Headless permission denials** and **compaction effects** are now grounded in specific, dated Claude Code
  changelog entries (through v2.1.281) rather than general inference. [DOC S1864]
- **`stop_reason` values** `pause_turn`, `refusal`, and `model_context_window_exceeded` are recorded with their
  documented meaning, tagged DER since a single canonical stop-reason reference page was not independently
  re-fetched. [DER S-qso6o6wu]
- **Unsupported JSON Schema keywords / strict-tool-use restrictions per vendor**: OpenAI's `additionalProperties:
  false` + all-properties-`required` strict-mode rule [DOC S1865], Anthropic's strict-tool-use grammar-compilation
  model and its two toolset exclusions and PHI caching caveat [DOC S1869]; Gemini's page enumerates no such keyword
  list [UNK, gap remains].
- **Copilot Studio's error-codes page is now exhaustively parsed**: ~50 named codes plus 5 numbered channel codes
  were extracted into the CSV, including the full throttling/timeout/quota family
  (`HTTP429TooManyRequests`, `GenAISearchandSummarizeRateLimitReached`, `GenAIToolPlannerRateLimitReached`,
  `QuotaExceeded`, `EnforcementMessageC2`, `DataverseStructured429`, etc.). Notably, the community-reported
  `OpenAIAdditionalInstructionsLengthExceededLimit` string does **not** appear on the official page at all — this is
  now stated as a confirmed absence, not an unparsed page. [DOC S1842]
- **Power Platform / Power Automate throttling for agent flows** shares the same connector-level throttling codes as
  Copilot Studio (`HTTP429TooManyRequests`, `DataverseStructured429`, etc.); no agent-flow-specific throttling code
  distinct from the shared connector codes was found. [DOC S1842]

_Agent: agents-errors_

## QG7. How instruction volume affects adherence
- IFScale (arXiv, non-vendor): instruction-following accuracy measured against instruction count from 10 to 500,
  showing three degradation shapes across model families (threshold decay, linear decay, exponential decay), with
  reasoning models showing threshold decay and weaker/non-reasoning models showing exponential decay. [COMMUNITY
  S1854 — academic preprint, tagged COMMUNITY per rule 1 since the authors are not the vendor of the models tested]
- Anthropic's own vendor-authored guidance ("Effective context engineering for AI agents") describes an "attention
  budget" that every added token depletes, and recommends active curation (compaction, structured note-taking,
  sub-agent isolation) over assuming instructions past some length are simply ignored or truncated cleanly. [DOC
  S1855]
- Chroma's "Context Rot" study (published 2025-07-14, vendor of a retrieval product but not of the 18 LLMs it
  benchmarks — tagged COMMUNITY per rule 1) measured the *complementary* axis: raw input-length degradation
  independent of instruction count, across Anthropic/OpenAI/Google/Alibaba model families, on needle-in-haystack,
  distractor, LongMemEval, and repeated-words tasks, plus a rising task-refusal rate with length for several models.
  [COMMUNITY S1870] It does not contradict IFScale; the two studies measure different independent variables
  (instruction count vs. context length) with the same directional conclusion.
- Claude Code's own changelog shows this is an active engineering concern, not just a research finding: v2.1.275
  extended the large-CLAUDE.md startup notice to count combined instruction files (CLAUDE.md + imports + rules)
  together, "so many mid-sized files and @-imports are caught" — an implicit vendor acknowledgment that combined
  instruction volume, not just single-file size, degrades outcomes enough to warrant a warning. [DOC S1864]
- No official Anthropic-, OpenAI-, Google-, or Microsoft-authored published *measurement study* of instruction-count
  or context-length degradation specific to their own production models was found in this pass — IFScale and Chroma
  Context Rot are the two measurement studies surfaced, and both are third-party/non-model-vendor. [UNK, see
  gaps.md]

_Agent: agents-errors_

## QG8. A checklist, each line cited, for keeping a project's CLAUDE.md, skills and MCP tool definitions inside documented limits
See the "QG8 checklist" section of `agents/agent-error-catalogue.md`, built from a direct read of a repository's own files:
- A project's `CLAUDE.md`: 226 lines / 15,614 bytes in one example [DOC — direct file measurement].
- A skill's `SKILL.md`: 78 lines in one example, with logic pushed into `scripts/` [DOC — direct file
  measurement], well under Claude Code's documented ~500-line tip [DOC S1860].
- Both are comfortably inside every numeric limit found in `agents/instruction-and-context-limits.csv` today; the
  checklist exists so this stays true as such docs and skills grow (a rule that keeps everything outside `docs/`
  to code, data, generated reference and a short README keeps the pressure on `docs/`, not `CLAUDE.md`, but the
  same growth risk applies to `CLAUDE.md` and skills as a rulebook accretes rules over time).

_Agent: agents-errors_

## QG9. Tools and methods to evaluate and stress an agent through a self-hosted MCP server
- **MCP Inspector**: official protocol tool (Apache-2.0 new code / MIT legacy / CC-BY-4.0 docs); connects to
  a stdio server natively; CLI mode (`--cli`, `--format json`) is built for CI automation; measures protocol
  correctness (tool/resource/prompt listing and invocation), not task success. [DOC S1880, S1881]
- **Anthropic's "Writing effective tools for agents"** is design guidance, not a harness; its principles
  (namespacing, response context, token efficiency, pagination/truncation defaults) define what a stress
  test should check for in tool output. [DOC S1935]
- **promptfoo**: MIT-licensed; its MCP provider drives a stdio server via `command`/`args`/`path` and
  asserts per response; its red-team mode adds an MCP-specific plugin, jailbreak/multi-turn strategies,
  `bfla`/`bola` authorization probes, `pii` and `sql-injection` plugins, with "Tool Poisoning Attacks" named
  as the primary MCP-specific risk. [DOC S1883, S1884, S1885]
- **inspect_ai** (UK AISI, MIT): scores agents via built-in/ReAct/bridged agents and model-graded scorers,
  200+ pre-built evals; native stdio-MCP-target support was not confirmed in fetched pages. [DOC S1886,
  S1887; UNK on MCP-target specifics]
- **DeepEval** (Apache-2.0): purpose-built MCP metrics — `MCPTaskCompletion`, `MCPUse`, `MultiTurnMCPUse`,
  plus MCP-aware `ToolCorrectness`; connects via `MCPServer(transport="stdio")`. [DOC S1888, S1889]
- **OpenAI evals**: `openai/evals` (MIT) is the open framework/registry; the hosted Evals **platform** is
  being deprecated (read-only 2026-10-31, shut down 2026-11-30) — a live-fact caveat for anyone building on
  it going forward. [DOC S1893, S1894, S1895]
- **garak** (NVIDIA, Apache-2.0): a generic LLM vulnerability scanner (injection, leakage, jailbreak, toxicity)
  with no native MCP client; MCP exposure exists only via third-party wrappers/an open feature request.
  [DOC S1890, S1891; COMMUNITY S1903]
- **PyRIT** (Microsoft, MIT, v0.11.0): red-team orchestration with a custom-target interface and
  `XPIAOrchestrator` for cross/indirect prompt injection — the closest built-in mechanism to "inject via a
  tool result," even without a dedicated MCP target class. [DOC S1892]
- **MCP fuzzers/load tools** are community-only at this date (`mcp-fuzz`, `mcp-server-fuzzer`, `mcp-guard`,
  `mcpsec`); none are vendor-endorsed. [COMMUNITY S1901, S1902, S1904, S1905]
- Full licence/transport/measurement table: `agents/agent-evaluation.md` § Reference.

_Agent: agents-eval_

## QG10. Building a question baseline (golden set)
- **Size**: Anthropic recommends starting with 20-50 tasks drawn from real failures. [DOC S1896]
- **Grading**: three kinds — code-based (fast, objective, reproducible), model-based (rubric/NL assertions,
  flexible), human (SME/crowd/spot-check, gold standard); prefer deterministic where possible, LLM where
  necessary. [DOC S1896] Anthropic's platform docs add: write hard pass/fail rubrics, and for LLM grading,
  have the grader reason first then discard the reasoning before scoring. [DOC S1898]
- **Metrics**: `pass@k` (≥1 success in k) and `pass^k` (all k succeed, from τ-bench/Sierra), plus token
  usage, latency, cost and error rate. [DOC S1896, S1899]
- **Regression cadence**: graduated tasks join an ongoing regression suite that should run continuously and
  hold "nearly 100% pass rate" to catch drift; no numeric cadence (daily/weekly) is published by any source
  found. [DOC S1896; gap noted in gaps.md]
- **Contamination/flakiness**: isolate every trial from a clean environment; avoid shared state that
  correlates failures across trials. [DOC S1896]
- **OpenAI's guidance**: eval-driven development (evaluate early/often, scoped tests per stage), grade with
  a different (ideally stronger) model than the one graded, and validate model grading against human
  evaluation before scaling. [DOC S1894]
- τ-bench/τ2-bench (Sierra, MIT repo) is the origin of `pass^k` and defines task grading via
  `evaluation_criteria.actions` and a `reward_basis` gate; original paper reported a reliability gap
  (GPT-4o 61% pass@1 vs. 25% pass@8 on retail tasks). [DOC S1899, S1900]

_Agent: agents-eval_

## QG11. Stress dimensions for a device-management MCP server (general checklist)
A general checklist for stress-testing an MCP server that exposes device/config-management operations
(such as ConfigMgr): see `agents/mcp-stress-testing.md` for the full table; summary:
- **Tool-count scaling**: check a growing operation count against Anthropic's tool-design guidance for a
  growing tool set. [DER S1935]
- **Ambiguous/adversarial questions**: probe target types outside the server's declared target scope
  (e.g. device/collection/group). [DER]
- **Injection via tool results** (device names, log lines): closest general mechanisms are promptfoo's
  "Tool Poisoning" red-team plugin and PyRIT's `XPIAOrchestrator`; a server should confirm its log/query
  sinks are sanitized before reaching the model, not just structured PII fields. [DOC S1884, S1892; DER]
- **Oversized output**: a server should set explicit token/row/char truncation targets and test against them.
- **Timeouts / `unknown` handling**: directly testable against the rule that "unknown is never absent... zero
  rows where rows were expected has failed" using recorded exchanges (never a live site). [DOC; DER]
- **Confirmation bypass at higher tiers**: a server that requires confirmation for consequential actions
  needs its own custom harness/assertion, since no fetched tool encodes this rule generically. [DOC; DER]
- **Per-agent device limits**: an agent-specific operation limit (e.g. a fraction of the human limit),
  enforced as a code-level assertion, is a common mitigation. [DER]
- **Pseudonymization leakage**: a token-kind list and a 0-leak bar on a seeded document set is the same class
  of test DeepEval/promptfoo `pii` assertions perform, applied to MCP tool output. [DOC S1884, S1888]
- **Concurrency**: a single-writer lock and a concurrent-observe-loop cap have no vendor MCP-stress-tool
  coverage found; exercise with a scripted concurrent-caller harness. [DER]

_Agent: agents-eval_

## QG12. Draft question baseline
- A draft question baseline can hold ~50 rows across nine required categories (lookup, multi-step, ambiguous,
  out-of-scope, tier ≥2 confirm, over-limit, unknown/timeout, injection, pseudonymization), built from an
  operation table and a fixture estate of example names (`PL-LT-00123`, `PL-SRV-0042`, `corp.example.com`,
  `jan.kowalski`, plus invented fixtures in the same naming pattern).
- Such a baseline is marked `DER` and is a draft input for a future task to adopt, not a decision.
- Grading columns use `code` (deterministic: tool name, tier, limit, exit-code) or `model` (rubric/LLM- or
  human-graded), matching the two grader kinds Anthropic's guidance names as most load-bearing. [DER S1896]
- Design tensions worth testing for: rows that check an agent cannot be talked out of a mandatory
  confirmation; rows that test an unknown-vs-absent rule; rows that test that a deferred integration (e.g. a
  chat-bot front end) means no such tool exists to call in the first place.

_Agent: agents-eval_

## QG13. Official guidance on workflows vs agents and single vs multi-agent designs

- Anthropic defines **workflows** as "systems where LLMs and tools are orchestrated through predefined code paths" and **agents** as "systems where LLMs dynamically direct their own processes and tool usage." [DOC S1920]
- Anthropic's stated default: find the simplest solution first, and increase complexity — including whether to build an agentic system at all — only when a workflow demonstrably falls short; "agentic systems often trade latency and cost for better task performance." [DOC S1920]
- Anthropic's multi-agent research system (its own production Research feature): a lead agent (Claude Opus) plans and spawns **3-5 subagents in parallel** (Claude Sonnet), each with its own context window and 3+ parallel tool calls, followed by a separate citation/synthesis pass. [DOC S1921]
- Published token multipliers vs a single chat turn: **agents use about 4× the tokens of a chat interaction; multi-agent systems use about 15×**. [DOC S1921]
- Published performance number: the multi-agent configuration (Opus lead + Sonnet subagents) **outperformed single-agent Claude Opus 4 by 90.2%** on Anthropic's internal research eval. [DOC S1921]
- Published variance decomposition on the BrowseComp eval: **token usage alone explains ~80%** of performance variance; tool-call count and model choice explain most of the remaining ~15% (~95% total from three factors). [DOC S1921]
- Anthropic's stated cost-benefit rule for when multi-agent is worth it: the task's value must exceed the token cost; good fits are heavy parallelization, information that exceeds one context window, and complex tool interfacing; poor fits are coding tasks with tight coordination requirements and few parallelizable components. [DOC S1921]
- Anthropic's own named failure modes for its multi-agent system: excessive subagent spawning for simple queries, duplicated work from vague task descriptions, agents favoring SEO-heavy content over authoritative sources, and sequential (non-parallel) execution causing needless slowness. [DOC S1921]
- Code execution with MCP (Anthropic engineering post): presenting MCP tools as on-disk code (a directory the agent explores) plus letting the agent write code to call and filter tool outputs **cut one example task from 150,000 to 2,000 tokens (98.7% reduction)**, because intermediate tool results stay in the execution environment instead of round-tripping through the model. [DOC S1922]
- Independent replications of the code-execution pattern (not Anthropic's own numbers, so `COMMUNITY`): a 78.5% input-token cut (165K vs 771K) on one GPT-4.1 test; a token-usage drop from 43,588 to 27,297 (37%) on a complex research task; a separate report of code execution scaling from 58% savings at 96 tools to 92.8% at 508 tools. [COMMUNITY S1931, S1932, S1934]
- OpenAI's practical guide: start with a single agent with tools, and only split into multiple agents when there is complex conditional logic or overlapping tool responsibilities that a single agent's instructions can no longer express cleanly; it names two multi-agent patterns — **manager** (one central agent calls specialists as tools) and **decentralized** (peers hand off execution outright). [DOC S1924, S1941]
- Microsoft's Azure Architecture Center states a **complexity spectrum**: direct model call → single agent with tools → multi-agent orchestration, with the rule "use the lowest level of complexity that reliably meets your requirements." It lists sequential, concurrent, group-chat/maker-checker, handoff, and magentic orchestration patterns, and names the orchestrator-worker pattern (matching Anthropic's own architecture) as its top-ranked production pattern. [DOC S1925]
- Microsoft Agent Framework (GA 2026-04-03, open source, Python/.NET) ships stable Sequential, Group Chat, and Magentic-One orchestration patterns, with OpenTelemetry-based observability and middleware for injecting content-safety/logging/compliance checks into the execution loop without touching prompts. [DOC S1938, S1939; COMMUNITY (announcement date/detail) S1940]
- Notable community position against multi-agent designs: Cognition ("Don't Build Multi-Agents", 2025-06-12) argues subagents fail because they act on incomplete shared context — "actions carry implicit decisions, and conflicting decisions carry bad results" — and recommends single-threaded linear agents by default, compressing history with an LLM summarization layer only when a task exceeds one context window. [COMMUNITY S1926]
- Cognition's own later, undated follow-up softens this: it now reports multi-agent setups that work in production, where multiple agents contribute intelligence to a task but writes stay single-threaded (see `conflicts.md` — a vendor revising its own earlier position, tagged per PROMPT.md rule 6). [COMMUNITY S1927]

_Agent: agents-mcp_

## QG14. Decision signals for replacing a child agent with a deterministic tool

- **Stable tool-call sequence / repeatability across runs**: Anthropic's own tool-writing guidance treats a fixed multi-step sequence (e.g., `list_users` → `list_events` → `create_event`) as a signal to consolidate into one tool ("schedule_event") rather than let the agent re-derive the sequence every run — the same signal applies to collapsing a subagent whose job is always the same sequence into one MCP tool. [DOC S1935]
- **Token and latency cost**: measurable directly from the published multipliers — a workflow step done as one deterministic tool call costs the baseline chat-token rate; the same step done by a spawned subagent costs roughly 4× that, and by a multi-agent branch roughly 15× that. [DER from S1921: derivation — subagent/multi-agent multipliers published for whole-task token cost are the ceiling for any one step done that way instead of by a fixed tool call]
- **Error compounding / runaway cost**: Anthropic names "a subagent that recursively spawns more subagents" as an observed failure mode of its own architecture, and states the published architecture has no circuit breakers or per-run cap in the post itself; a secondary source puts a compounding runaway or oversized-result event at "another 10x or more" on top of the 15× baseline. [DOC S1921 for the named failure mode; COMMUNITY S1930 for the 10x compounding number]
- **Auditability**: community engineering commentary states plainly that "an LLM-based filter deciding something looks fine... doesn't generate a record that holds up in a SOC 2 audit," and recommends composing deterministic flows in code rather than in prompts, wrapping multi-step orchestration into single composite tools instead of relying on the model to sequence calls, to remove sequential-dependency errors and get a verifiable record. [COMMUNITY S1945, S1944]
- **Need for confirmation (a higher-tier/consequential-action case)**: MCP's own spec puts the human-in-the-loop requirement at the protocol level, independent of agent vs tool framing — servers "SHOULD" always keep a human able to deny invocations, and clients "SHOULD" prompt for confirmation on sensitive operations; a deterministic tool with a fixed, auditable input schema is easier to gate this way than a subagent whose exact call sequence is not known until it runs. [DOC S1928]
- **Eval pass rate as the trigger, not a raw threshold**: Anthropic's evals guidance measures agent tool use by generating realistic multi-step tasks, then tracking accuracy alongside runtime, tool-call count, token consumption and error rate — but does not publish a numeric pass-rate threshold that should trigger converting an agentic step to a deterministic tool; this is left to the adopting team's own eval baseline. No vendor number found for this specific threshold; recorded as a gap. [DOC S1935 for the *method*; UNK for a numeric trigger threshold, see gaps.md]
- **Measuring from transcripts / OTel data**: `claude/otel-monitoring.md` (already written, part `arch`, reused here) documents that Claude Code's own `claude_code.tool_result` and `claude_code.tool_decision` OTel events carry `duration_ms`, `success`, `tool_input_size_bytes`/`tool_result_size_bytes`, and (with `OTEL_LOG_TOOL_DETAILS=1`) the MCP server/tool name and arguments — these are the concrete fields to pull per-tool-call latency, error rate and payload size, the inputs to every decision signal above, without a new logging mechanism. [DOC S744, S745 — reused from `claude/otel-monitoring.md`, part `arch`/`claude`]

_Agent: agents-mcp_

## QG15. Migration patterns: agent logic to an MCP tool, prompts/resources, a skill with scripts, or code execution

- **Agent logic → MCP tool**: consolidate the fixed sequence of tool calls the subagent always performs into a single tool with a combined `inputSchema`; MCP's own spec supports this directly via `outputSchema` (an optional JSON Schema the server's `structuredContent` **MUST** conform to) so the caller (model or code) gets typed, validated output instead of free-text the model must re-parse each run. [DOC S1928]
- **Behavioral annotations replace some of what a subagent's judgment used to decide**: MCP tool `annotations` (`readOnlyHint`/`destructiveHint`/`idempotentHint`/`openWorldHint`) let a host auto-approve safe read-only tools and force confirmation on destructive ones, deterministically, instead of relying on a subagent (or the model) to reason about risk each time — though the spec warns annotations **MUST** be treated as untrusted unless the server itself is trusted. [DOC S1928]
- **Agent logic → a skill with scripts**: Anthropic's Agent Skills guidance draws the line explicitly: "certain operations are better suited for traditional code execution... sorting a list via token generation is far more expensive than simply running a sorting algorithm," and states many applications "require the deterministic reliability that only code can provide." A skill's `scripts/` directory runs deterministic operations (e.g., `validate.py`) whose *output* — not source — enters context, so a script that used to be a subagent's whole job can shrink to a ~20-token result instead of a full subagent invocation. [DOC S1936, S1937]
- **Progressive disclosure as an alternative to spawning a subagent for isolation**: a skill loads in three tiers — frontmatter metadata (always in context), the SKILL.md body (loaded once relevant), and referenced resource files (loaded only as needed) — giving "effectively unbounded" skill complexity without the fresh-context startup cost or lost conversation history of a subagent. [DOC S1936]
- **Agent logic → code execution over MCP**: rather than exposing every tool definition and round-tripping every intermediate result through the model, tools are exposed as files/modules the agent explores and then calls from written code; Anthropic measured this pattern's 150,000→2,000 token (98.7%) reduction on a Drive-to-Salesforce task specifically because intermediate results (the whole reason a subagent used to exist, to isolate noisy output) never re-enter the model's context at all. [DOC S1922]
- **Keeping behavior equal during migration — record, replay, compare**: no fetched vendor source publishes a named "record MCP transcripts and replay against a baseline" workflow for this specific migration (agent→tool), but the general technique is documented by third-party eval tooling: Promptfoo's coding-agent evaluation guide runs a fixed task set against an agent build and asserts on the outcome in CI; a community tool (AgentInspect) explicitly "diffs the full agent trajectory — tool calls, parameters, sequence, output, cost — against a golden baseline," which is the applicable pattern for proving a new deterministic tool reproduces what a removed subagent used to do. [COMMUNITY S1942, S1943]
- **What Claude Code's own subagent docs say about the same choice**: "Use one when a side task would flood your main conversation with search results, logs, or file contents you won't reference again," but "consider Skills instead when you want reusable prompts or workflows that run in the main conversation context rather than isolated subagent context" — i.e., the vendor's own decision rule is context-volume isolation, not task complexity; a subagent that does not produce large, disposable intermediate output has no isolation benefit to trade against its token/latency cost. [DOC S1923]

_Agent: agents-mcp_

## QG16. A worked case study: deterministic candidates in a task-picker skill

A general pattern, illustrated by a task-picker skill built from a prose skill file plus two helper scripts
(a picker and a post-landing verifier):

- **A picker script can already be a fully deterministic tool, not agent-driven.** A stdlib-only script invoked
  once, before the skill's prose is even loaded, reading only a small fixed set of plan/progress files, and
  returning one of a fixed set of verdicts (`eligible`, `blocked`, `gated`, `not-before`, `unparseable`, `done`)
  is a clean example of moving task selection out of model judgment entirely. [DER]
- **A house rule that a picker's verdict is never overruled from prose** is the concrete instance of "unknown is
  never eligible" applied to task selection: an unparseable header is `unparseable`, never guessed at by the
  model. [DOC]
- **A post-landing verifier script can likewise be fully deterministic**, explicitly justified as *replacing*
  model judgment ("a transcript claiming success is not evidence; this is"). Shelling out to `git` to check a
  README tick, a landed row with a resolvable merge-commit sha, that sha's ancestry on the main branch, a task
  trailer, a clean tree, and open planning debt — each check returning `True`/`False`/`None` (unknown), with
  **unknown counting as failing** — is a direct code-level instance of "unknown is never eligible." [DER]
- **A machine-readable task-header grammar is what makes this determinism possible, not merely convenient**: an
  exact header grammar that a picker can regex-parse, where an unparseable header is unknown and never eligible,
  is a rulebook constraint that a future agent-driven picker would violate — the header format exists
  specifically so a regex-based script, not a model, can resolve it. [DOC]
- **What stays model-driven, by contrast, inside the same skill**: judgment calls like folding open debt, asking
  gate questions, naming the failure a new mechanism pays for, and deciding whether a lab run is needed are all
  prose instructions followed by the agent, with no script backing them — these are the calls that "every
  mechanism is paid for by an observed failure" would require justifying before scripting, since nothing has yet
  broken there. [DER]
- **A one-job-runs-everywhere policy tension for any future headless/scheduled agent use**: picker/verifier
  scripts that already satisfy a "one checks job... the same command runs on a laptop" pattern for task selection
  and landing-verification, since they are plain scripts runnable identically in CI or on an engineer's machine,
  do not by themselves schedule their own future run; a skill invoked per-session by an operator is consistent
  with "a session finishes or names one blocker... no watch windows, no 'check back later' jobs." No mechanism
  here contradicts that rule when there is no autonomous trigger yet. [DER]
- **A named future deterministic candidate, per the same "paid for by an observed failure" test**: a skill step
  that batches every open gate and question into one confirmation prompt with options and a recommendation is
  currently prose-driven; absent an observed failure (a missed gate, a malformed batch) that would justify
  scripting it, it should stay model-driven until such a failure is recorded — a fact about the current state,
  not a recommendation to change it. [DER]

_Agent: agents-mcp_

## QG17. Copilot Studio's feature inventory as of now

- Copilot Studio ships three "harnesses" (execution engines) as of the current docs: the
  **GitHub Copilot harness** (reasoning-heavy, multi-step), the **standard harness** (rule-based
  topics/conversations — most of the feature surface below), and the **Copilot chat harness**
  (extends Microsoft 365 Copilot Chat with tenant knowledge). Harness choice changes billing and
  available features. [DOC S1962]
- **Topics and triggers**: authored visually or in a YAML **code editor**; trigger phrases up to
  200/topic; up to 1,000 topics/agent in Dataverse environments (250/agent in Dataverse-for-Teams
  before upgrade). [DOC S1960, S1963]
- **Generative orchestration**: an LLM-driven planning layer selects topics/tools/knowledge per
  turn, can auto-fill topic inputs from context, and generates follow-up questions. [DOC S1962; DER
  from search summary of S1983]
- **Instructions**: agent-level instructions capped at 8,000 characters. [DOC S1960]
- **Knowledge sources**: up to 500/agent across all types; SharePoint (25 site URLs max under
  generative orchestration, page-level PDF citations, 512 MB/file), OneDrive, Dataverse (max 2
  sources, 15 tables), Salesforce/Confluence/ServiceNow/Zendesk connectors (unlimited article
  count), all requiring per-user authentication at query time (no shared-credential sign-in). [DOC
  S1960]
- **Tools/actions/connectors**: up to 100 skills/agent; connector payload capped at 5 MB (450 KB in
  GCC); tools invoke Power Platform connectors, custom connectors, or MCP servers. [DOC S1960,
  S1964]
- **Agent flows / Power Automate**: agent flows are the native, deterministic (same-input-same-
  output) automation format inside Copilot Studio; a Power Automate cloud flow can be one-way
  converted into an agent flow to move it onto Copilot Studio capacity billing instead of Power
  Automate billing; every agent-flow action consumes Copilot Studio capacity. [DOC S1979]
- **MCP servers**: connected via an onboarding wizard (API key or OAuth 2.0 — dynamic discovery,
  dynamic, or manual DCR) or via a custom Power Apps connector built from an OpenAPI schema; only
  the **Streamable HTTP** transport is supported, SSE was dropped after August 2025; MCP access is
  governed by Power Platform **data policies** (DLP) the same as any connector. Standing up a new
  MCP server uses an MCP SDK from `github.com/modelcontextprotocol` in any supported language, with
  the same API-key/OAuth 2.0 authentication choices. [DOC S1964, S1965, S1974]
- **Adaptive cards**: channel-dependent — the customer-satisfaction survey renders as an adaptive
  card on a custom website but text-only in Teams/Facebook/Omnichannel; Teams renders up to 6
  suggested actions as a hero card, not a full adaptive card. [DOC S1977]
- **Channels**: Custom Website, Demo Website, Microsoft Teams, Microsoft 365 Copilot, SharePoint,
  WhatsApp, Mobile App (Direct Line), Facebook, and Azure Bot Service channels (Cortana, Slack,
  Telegram, Twilio, Line, Kik, GroupMe, Direct Line Speech, Email); admins can block individual
  channels via **Agent access channels** in the Power Platform admin center or via DLP. [DOC S1977]
- **Authentication and SSO**: agents default to **Authenticate with Microsoft** (zero-config Entra
  ID SSO for Teams/Power Apps/M365 Copilot) or can be set to manual Entra ID/generic-OAuth
  authentication for custom canvases; SSO for a custom web canvas needs two separate Entra app
  registrations (auth app + canvas app) and a token-exchange URL; SSO is **not** supported on Azure
  Bot Service channels, the demo website, Facebook, mobile app, or Power Apps portals. [DOC S1966,
  S1977]
- **Variables and state**: topic-scoped variables (can be marked to receive/return values across
  topic redirects) vs. global (bot-scoped) variables; environment variables can reference Azure Key
  Vault secrets, cached 5 minutes on success / 30 seconds on failed reads; a **Parse value** node
  converts untyped JSON/event payloads into typed Record variables. [DOC S1978]
- **Handoff**: implicit (agent can't match intent) or explicit (**Transfer conversation** node)
  escalation to a live-agent engagement hub (for example Dynamics 365 Omnichannel), carrying full
  conversation history plus named context variables (`va_Scope`, `va_LastTopic`, `va_AgentMessage`,
  etc.); escalated sessions are tagged in analytics. [DOC S1972]
- **Analytics**: a **Monitor** page distinguishes conversational-session analytics (DAU/MAU,
  resolution/escalation/abandonment outcomes, per-topic charts, satisfaction score) from
  event-triggered ("autonomous agent") session analytics; data retained up to 360 days, transcripts
  for 28 days; active-user metrics require the agent to require authentication. [DOC S1973]
- **ALM (solutions, pipelines)**: every Copilot Studio agent lives inside a Power Platform
  **solution**; the in-app solution manager (GA 2024-12-16) lets makers view/export/import
  solutions and run **pipeline deployments** across environments without leaving Copilot Studio,
  reusing general Power Platform ALM concepts. [DOC S1967]
- **DLP and governance**: Power Platform **data policies** gate connectors (certified, custom,
  virtual, and MCP connectors) at both design time (blocks saving) and runtime (blocks execution,
  quarantines existing flows/chatbots); policy propagation latency is "in most cases within an
  hour," up to 24 hours in extreme cases; Copilot-Studio-specific **virtual connectors** are
  migrating to their own dedicated governance rules separate from classic DLP. [DOC S1974]
- **Quotas and billing (Copilot Credits)**: message-throughput quotas are tiered by prepaid-pack
  count (for example 50 RPM/1,000 RPH at 1-10 packs, up to 100 RPM/2,000 RPH at 51-150 packs, plus
  +1 RPM/+20 RPH per extra 10 packs above 150); trial/dev environments capped at 10 RPM/200 RPH;
  pay-as-you-go and M365-Copilot-licensed usage both fixed at 100 RPM/2,000 RPH. Since **2025-09-01**
  the billed unit is **Copilot Credits** (previously "messages"), sold via pay-as-you-go Azure
  meters, a one-year prepurchase plan (Copilot Credit Commit Units), or Copilot Credit prepaid pack
  subscriptions; unused credits do not carry over month to month; exceeding purchased capacity
  triggers technical enforcement (agent becomes unavailable) after admin-configured notification and
  hard-stop thresholds. Microsoft 365 Copilot-licensed usage of classic/generative answers or tenant
  graph grounding inside Teams/SharePoint/Copilot Chat is zero-rated (doesn't consume the message
  pack/meter). [DOC S1960, S1961]

_Agent: agents-copilot_

## QG18. Export and migration paths

- **Solution export**: a Copilot Studio agent is always a component of a Power Platform solution;
  the in-app solution manager can export/import that solution and drive pipeline deployments across
  environments (dev/test/prod) — this is the primary "move an agent between environments" path, not
  a raw-file export. [DOC S1967]
- **Topic YAML**: individual topics can be opened in a **code editor** that shows/edits the topic as
  YAML (`kind: AdaptiveDialog`, node graph, conditions, knowledge-source links); Microsoft
  explicitly supports copy/pasting topic YAML between agents as a way to move logic without solution
  export, but warns that YAML syntax errors "can result in complex error messages or break the
  current conversation" and that "technical support teams can't help remediate code editor errors."
  This YAML is Copilot-Studio-internal — there is no published stand-alone schema for it outside the
  product. [DOC S1963]
- **Microsoft 365 Agents SDK**: the vendor-recommended target for agents built outside Copilot
  Studio's low-code surface. It is a channel- and AI-agnostic message-plumbing framework (not an
  orchestration engine, not a model) supporting C# (.NET 8), JavaScript (Node 18+), and Python
  (3.9-3.11 per the overview page; the Python repo's own README says 3.10+, 3.11+ recommended, 3.10-3.14 supported — a
  minor version-floor discrepancy between the two Microsoft pages). [DOC S1968, S1971, S1969]
- **Bot Framework SDK support status**: per the GitHub README, the Bot Framework SDK's final
  long-term support ends **2025-12-31**; after that it receives no updates, no new features, and no
  Azure-portal service-ticket support (though already-built bots keep functioning), and Microsoft
  plans to archive the repository no later than end of December 2025. Microsoft's stated replacement
  is the Microsoft 365 Agents SDK. [DOC S1976; DER — exact archive date not independently
  cross-checked, see gaps.md]
- **Teams AI library**: referenced by name in Microsoft's own agent-tooling ecosystem but its
  current docs page could not be fetched in this pass (404) and is not mentioned by the Agents SDK
  overview page fetched here; treat its current relationship to the Agents SDK as **[UNK]** pending
  a direct fetch (see gaps.md). Prior public knowledge (community-level, not verified against a live
  page in this session) positions it as a Teams-specific conversational-AI toolkit that predates and
  partially overlaps the Microsoft 365 Agents SDK. [UNK]
- **Azure AI Foundry (Microsoft Foundry) Agent Service**: a separate, code-first/managed agent
  platform (prompt agents, voice-based prompt agents, hosted agents) that is not a Copilot Studio
  export target but a parallel building surface; hosted agents can be built with Microsoft's own
  **Agent Framework**, LangGraph, the OpenAI Agents SDK, the Anthropic Agent SDK, or the GitHub
  Copilot SDK, then run by Foundry as a container with a managed endpoint and per-agent Entra
  identity. Foundry agents can be published to Microsoft Teams/Copilot and the Entra Agent Registry,
  and support the **A2A protocol** (v1.0 GA, v0.3 preview) for agent-to-agent calls. [DOC S1970]
- **"Bring your own agent" into Microsoft 365 Copilot**: Copilot Studio distinguishes a **custom
  agent** (built from scratch, publishable to Teams/M365 Copilot and other channels) from an
  **agent for Microsoft 365 Copilot** ("declarative agent" in M365 Copilot terminology — instructions
  + knowledge only, authored from the dedicated Microsoft 365 Copilot page, not automatically
  deployed on publish); availability options after publish include a shareable deep link, sharing to
  named users/security groups, submission to the org's Teams/M365 Copilot catalog, or **download as
  a .zip** for manual upload/admin review — the .zip is the closest thing to a portable export
  artifact for this agent type. [DOC S1975]
- **What is data vs. what must be rebuilt**: exportable as data — topic definitions (YAML),
  solution-packaged components (topics, flows, connections, knowledge-source references), variables/
  entities, and (for M365 Copilot declarative agents) the manifest .zip. Must be rebuilt in an
  external codebase — the generative-orchestration planning behavior, the managed knowledge-
  retrieval pipeline (SharePoint/Graph grounding, semantic search), the built-in analytics/Monitor
  pipeline, and MCP-onboarding-wizard authentication wiring (these are runtime services of Copilot
  Studio, not exportable artifacts). [DER from S1962, S1963, S1967, S1973, S1975]

_Agent: agents-copilot_

## QG19. Replicating each feature in own code

- Row-by-row replacement mapping is in `agents/copilot-studio-feature-map.csv`. Headline
  correspondences, each tied to a Microsoft 365 Agents SDK capability documented at S1968/S1971:
  - **Channel adapter** → the Agents SDK's channel-abstraction layer, which normalizes inbound/
    outbound messages to a common `Activity` format per channel (Teams, web chat, Slack, etc.),
    matching Copilot Studio's own multi-channel publish model. [DOC S1971]
  - **Dialogue/turn state** → the Agents SDK's built-in "turn" concept and state/storage management
    (a turn is one unit of conversational work); the Python package additionally ships Waterfall
    dialogs and prompts for multi-turn flows, and Azure Blob/CosmosDB storage backends. [DOC S1971,
    S1969]
  - **Orchestration by an LLM with tools** → explicitly **not** provided by the Agents SDK itself
    ("isn't an AI model, an orchestration engine, or a no-code builder" — S1971); a replacement built
    from this SDK supplies its own LLM loop and tool-calling logic, or delegates to Foundry Agent
    Service / Agent Framework / Semantic Kernel, which the Python SDK explicitly integrates
    components from. [DOC S1971, S1969]
  - **Knowledge retrieval** → not part of the Agents SDK; would be a separate retrieval component
    (vector store, Graph/SharePoint connector, or a Foundry "toolbox" tool) wired in by the
    developer. [DER from S1971, S1970]
  - **Adaptive cards** → channel-native rendering handled by the channel adapter/Activity protocol,
    same mechanism Copilot Studio itself uses per-channel (Teams hero cards, web adaptive cards).
    [DER from S1971, S1977]
  - **Human handoff** → not a built-in Agents SDK feature; would be custom code calling an external
    engagement-hub API (comparable to Copilot Studio's Transfer-conversation-node integration with
    Omnichannel). [DER from S1972, S1971]
  - **Analytics** → not built into the Agents SDK; would need custom OTel/App-Insights
    instrumentation (Foundry Agent Service offers this natively via Application Insights
    integration and agent tracing for its own agent types). [DOC S1970]
  - **Content safety** → not addressed by the Agents SDK docs fetched here; Foundry Agent Service
    documents integrated content filters mitigating prompt-injection (including cross-prompt/XPIA)
    as a platform feature of *that* service, not of the Agents SDK. [DOC S1970]
  - **ALM via git/CI** → the Agents SDK is plain source code (C#/JS/Python packages), so its natural
    ALM is git + CI, unlike Copilot Studio's Power-Platform-solution/pipeline model — this is the
    main axis on which "own code" is easier to fit into an existing GitLab-MR regime than Copilot
    Studio's low-code ALM is. [DER from S1971, S1967]
  - **MCP as the tool layer** → the Python Agents SDK ships a "Copilot Studio Client" for direct
    engine interaction with agents built in Copilot Studio, but its README (S1969) does not
    advertise a first-class MCP client/server component; Foundry Agent Service, by contrast,
    documents native MCP tool support (remote MCP servers, Azure-Functions-hosted MCP webhooks,
    key/Entra/OBO authentication) as a first-class "toolbox" concept. [DOC S1969, S1970]
- **A stdio-only MCP server serving both a CLI agent and a Teams front**: because Copilot Studio's own MCP
  onboarding wizard connects to *any* server that speaks the Streamable HTTP transport with API-key
  or OAuth 2.0 auth (S1964), and because Foundry Agent Service documents the same remote-MCP pattern
  with Entra/OBO authentication (S1970), a given stdio MCP server could in principle be registered
  a second time as a Copilot Studio/Foundry tool without code changes to the server, *if* it were
  exposed over a network transport instead of stdio. **Tension**: a design whose policy is "stdio only,
  no always-on service, no public endpoint, no gateway" cannot add a server as a Copilot Studio or Foundry
  tool without first building the network-facing, always-on component that policy currently forbids; this
  is a fact about what such an extension would need to supply, not a recommendation to build it. [DER from
  S1964, S1970]

_Agent: agents-copilot_

## QG20. Risks and costs of leaving

- **Licensing**: staying on Copilot Studio means buying into Copilot Credits (pay-as-you-go, a
  one-year prepurchase of Copilot Credit Commit Units, or prepaid packs) with monthly-only capacity
  enforcement and no rollover of unused credits (S1960, S1961); leaving means the licensing cost
  moves to whatever LLM-vendor API billing and hosting compute the "own chatbot" uses instead — a
  different, not obviously cheaper, cost model. No comparative price figures were fetched (see
  gaps.md), so a genuine cost delta is **[UNK]**.
- **Compliance features lost**: Copilot Studio's DLP/data-policy engine (S1974) enforces
  connector- and MCP-server-level blocking, quarantining, and design-time/runtime restriction across
  an entire Power Platform tenant, with an admin-configurable propagation SLA (within an hour,
  worst case 24 hours). An own-code chatbot has no equivalent tenant-wide governance
  layer unless one is built or borrowed from an existing control (for example the same Entra
  Conditional Access / Purview policies that already govern a workstation). Solution
  management/ALM (S1967) and the Monitor analytics/transcript pipeline (S1973, 360-day retention)
  are Copilot-Studio-native audit surfaces that would need a replacement (OTel, a ledger-style log,
  or a Purview/App-Insights integration) if left behind — none of this is addressed by
  the Agents SDK itself (S1971 explicitly scopes the SDK to message plumbing only, not analytics or
  governance).
- **Identity in an on-prem estate**: a policy that restricts a tool to CLI + stdio MCP on engineer
  workstations, with no always-on service and interactive calls under the engineer's own Kerberos/
  delegated identity, is in tension with Copilot Studio's Teams channel, which is built around
  always-on Entra-ID-authenticated bot identities (S1966, S1977) — publishing a Teams channel
  "provisions a bot resource... in your tenant's Microsoft Entra ID environment" (S1975). Adopting a
  Teams front for an own-code chatbot (QG19) would need that same kind of standing Entra bot
  identity, which is exactly the always-on, network-facing component such a policy would defer — a
  fact about the identity model, not a recommendation to build it. [DER from S1966, S1975, S1977]
- **Hosting**: a container-ready-but-container-free design (no image, chart, or broker built) is in
  tension with a Copilot-Studio replacement that is "hosted agents" on Foundry Agent Service, which
  is explicitly container-based (S1970: "Foundry runs it with a managed endpoint... container compute,
  Foundry-managed"); Bot-Framework-SDK-era or Agents-SDK bots are typically deployed to Azure Bot
  Service / App Service containers as well. Any migration path that lands on Foundry hosted agents or
  an Azure-hosted Agents SDK bot would cross that no-image/chart/broker boundary the same way a Teams
  channel would cross the no-always-on-service boundary — again a fact about what "leaving Copilot
  Studio" costs architecturally, not a call to do it. [DER from S1970]

_Agent: agents-copilot_

## QG21. Design patterns that limit prompt injection through tool results, beyond the OWASP lists

- The 2025 paper "Design Patterns for Securing LLM Agents against Prompt Injections" catalogues named patterns,
  each trading utility for provable/structural resistance: **Action-Selector** (agent picks from a predefined
  allowlist of actions rather than free-form tool calls; loses ability to handle novel tasks), **Plan-Then-Execute**
  (plan is fixed before untrusted data is read, so later injected content cannot change the plan; adds latency),
  **LLM Map-Reduce** (splits untrusted content across isolated sub-calls with no tool access, then aggregates;
  raises cost), **Dual LLM** (a privileged, tool-calling LLM never sees raw untrusted text, only a quarantined
  LLM does; doubles inference cost), **Code-Then-Execute** (the agent emits a constrained program instead of
  freeform tool calls; limits expressiveness), **Context-Minimization** (shrinks what untrusted content the model
  sees at all; degrades task performance), and a **Firewall** style output filter (blocks suspicious actions after
  the fact; false positives). [COMMUNITY S2005: arXiv preprint, non-vendor authors from Google DeepMind/ETH/Meta/
  Invariant Labs per the paper's own affiliations, but arXiv itself is not a product vendor, so tagged COMMUNITY
  per PROMPT-agents rule 1]
- **CaMeL** ("Defeating Prompt Injections by Design", Google Research) is a concrete Dual-LLM/Plan-Then-Execute
  hybrid: a privileged LLM extracts the control/data flow from the *trusted* user query only, so untrusted tool
  output can never alter which tools run next; a capability system then restricts what the extracted data flow may
  do (e.g. blocks unintended data exfiltration). On the AgentDojo benchmark CaMeL solved 77% of tasks with provable
  security against 84% for an undefended baseline. [COMMUNITY S2006: arXiv preprint, Google-authored but not a
  published Google product]
- The **dual-LLM pattern** (Simon Willison, 2023) is the community-origin version of the same idea: a privileged
  LLM with tool access never receives raw untrusted content; a non-AI Controller substitutes untrusted text with
  opaque variable tokens (`$VAR1`) that a quarantined, tool-less LLM processes; the Controller resolves variables
  only when passing them to specific, vetted tool arguments. Willison calls the mitigation itself "pretty bad" —
  it adds complexity, degrades UX, and does not stop social engineering of the human. [COMMUNITY S2007: personal
  blog, first documented source of the pattern name]
- **Microsoft Spotlighting** (in Azure AI Content Safety's Prompt Shields, preview as of the 2026-08-28 page) tags
  third-party/tool-response content as lower-trust by base64-encoding it before it enters the model's context, so
  the model treats it as data rather than instructions; it has no direct dollar cost but increases token count
  (and can push a long document over the input limit), and is available only through the Chat Completions API path
  in Azure AI Foundry guardrails. **Prompt Shields** (formerly "jailbreak risk detection") is the separate,
  non-preview classifier that scores both direct user-prompt attacks and "document attacks" (hidden instructions
  in documents/emails/web pages/tool responses) at two intervention points: user input and tool response. [DOC
  S2008: learn.microsoft.com, ms.date 2026-08-28, updated 2026-09-18]
- Anthropic's own published defenses (as of a 2025-11-24 post, in the context of Claude for Chrome / browser
  agents) are model-training-based (RL training against injected content), an improved content classifier that
  "scans all untrusted content that enters the model's context window" for hidden or encoded instructions, and
  ongoing red-teaming; Anthropic states even a 1% attack success rate is "meaningful risk" and that "no browser
  agent is immune." This post does not name a tool-result-specific sandboxing mechanism. [DOC S2009]
- Claude Code's own documented defenses that specifically address **tool results and MCP** (as opposed to bash/file
  permissions in general): "isolated context windows" for web-fetch results (a separate context window keeps
  fetched content from directly injecting the main conversation), "context-aware analysis" that inspects the full
  request for harmful instructions, a fixed MCP server allowlist configured in source-controlled settings (see
  `managed-mcp.md`, S741/S746 already in `claude/`), network-request approval requirements for tools that reach
  the web, and a requirement that clients validate tool results before passing them to the model (from the MCP
  spec itself, S2135 (identical URL already recorded under that id), plus the MCP
  `server/tools` page fetched fresh for this part). [DOC S2010]

### Applying these patterns to a device-management agent (DER)
- A **pseudonymization boundary** (NER before any data reaches the model) is a Context-Minimization-family
  control: it does not stop an injected instruction from being read by the model, but it stops the model from
  ever holding real identifiers to exfiltrate, which is the specific harm Dual-LLM/CaMeL target when they block
  "data flow to unintended sinks." It does not defend against an injected instruction changing *which* device is
  acted on. [DER S2005,S2006]
- A **tier ≥2 always-confirm gate written in code** is functionally an Action-Selector: the model
  can only ever propose a call from a fixed, tiered tool set, and any state-changing call is confirmed by a human
  regardless of what the model was told to do by injected content in a device name or log line — this is exactly
  the Action-Selector pattern's trade-off: the model cannot invent a new action, only pick among pre-approved
  ones, and loses no material flexibility when the operation set is already closed. [DER S2005]
- **Allow-listed CMPivot-style entities/queries** (a read shape returning `compliant` or failing resource ids
  only, via a fixed AdminService query) is the same Action-Selector logic applied to the read side: an injected
  instruction inside a device's discovered value cannot cause an arbitrary query, because the query itself
  is fixed by code, not assembled by the model. [DER S2005]
- A system that does **not** implement a Dual-LLM/CaMeL-style separation between a privileged, tool-calling
  session and a quarantined session that reads raw device data before pseudonymization — where NER runs
  in-process as a filter, not as a second, isolated model call — leaves open whether an injected string could
  survive pseudonymization and still steer a *tool choice* (as opposed to leaking data); this is a general,
  unmeasured gap for any such design. [DER: tension noted]

_Agent: agents-extra_

## QG22. OpenTelemetry GenAI semantic conventions for agents, tool calls and MCP

- GenAI semantic conventions **moved out of** `open-telemetry/semantic-conventions` into a dedicated repository,
  `open-telemetry/semantic-conventions-genai` (Apache-2.0); the general logs/code conventions already cited in
  `logs/` (S639-S646) are unaffected and remain in the original repo. [DOC S2000, S2001; see `conflicts.md`]
- **Agent spans** (all status "Development", i.e. not yet stable): `create_agent` — span name
  `"create_agent {gen_ai.agent.name}"`, kind CLIENT, required `gen_ai.operation.name=create_agent` and
  `gen_ai.provider.name`, conditionally-required `gen_ai.agent.name`/`.id`/`.description`/`.version`,
  `error.type` if failed, recommended `server.address`/`server.port`. `invoke_agent` comes in a CLIENT-span
  variant (adds `gen_ai.provider.name` requirement, `gen_ai.conversation.id`, token-usage and finish-reason
  attributes) and an INTERNAL-span variant for a purely in-process invocation (drops the provider-name
  requirement). [DOC S2002]
- **Tool-call spans**: `execute_tool` operation, span kind INTERNAL, name pattern
  `"{gen_ai.operation.name} {gen_ai.tool.name}"`; required `gen_ai.operation.name=execute_tool`,
  `gen_ai.tool.name`, `gen_ai.tool.type`; conditionally required `gen_ai.tool.call.id` (when available) and
  `error.type` (on failure); recommended `gen_ai.tool.description`. Status Development. [DOC S2004]
- **MCP-specific conventions** (all Development status): `mcp.method.name` (required; e.g. `tools/call`,
  `initialize`, `prompts/list`), `mcp.protocol.version` (recommended; e.g. `2025-06-18`), `mcp.session.id`
  (recommended), `mcp.resource.uri` (conditional). Two span kinds: `mcp.client` (CLIENT) for outbound requests,
  `mcp.server` (SERVER) for inbound processing; span name pattern `"{mcp.method.name} {target}"`. `network.transport`
  mapping: stdio → `"pipe"`; Streamable HTTP → `"tcp"`/`"quic"` with `network.protocol.name="http"`; a custom
  WebSocket transport → `"tcp"` with `network.protocol.name="websocket"`. Four histogram metrics, all Development:
  `mcp.client.operation.duration`, `mcp.server.operation.duration`, `mcp.client.session.duration`,
  `mcp.server.session.duration`. [DOC S2003]
- This extends, and does not duplicate, `claude/otel-monitoring.md`, which documents Claude Code's own
  proprietary `claude_code.*` events (`tool_result`, `tool_decision`, `mcp_server_connection`) — those are
  Anthropic-specific telemetry, not the vendor-neutral `gen_ai.*`/`mcp.*` semantic-convention attributes described
  here; a Python MCP server that wants vendor-neutral traces would emit the `mcp.*` spans/metrics above regardless
  of which client (Claude Code or another MCP host) it serves. [DER: a stdio MCP server could
  instrument `mcp.server` spans per `tools/call`, independent of whatever the calling client (Claude Code) reports
  on its own side]
- **How a Python MCP server would emit these**: no MCP-specific OTel Python instrumentation package is documented
  by either OTel or MCP as of this fetch; a server would need to manually create spans named per the pattern above
  around its `tools/call` handler, set `mcp.method.name`/`mcp.protocol.version`/`mcp.session.id`, and set
  `gen_ai.tool.*` attributes if it wants agent-visible tool-level spans as well. This is inferred from the
  attribute registry, not a documented "how-to" page. [DER S2003,S2004: no vendor how-to guide found; recorded
  also as a minor gap]

### Implication for a redaction policy
- A house policy that requires secrets to be declared and redacted at every sink, including logs, needs to treat
  `mcp.resource.uri` and `gen_ai.tool.call.id` as OTel attributes with the same care: they could carry device names
  or session identifiers if a server sets them from tool arguments, so a redaction filter needs to cover any OTel
  exporter path exactly as it already covers CLI/MCP/logs. [DER: an implementation note for any project adding OTel]

_Agent: agents-extra_

## QG23. MCP server lifecycle: versioning, deprecation, listChanged, registry, contract tests

- **`listChanged`**: a server declares `"capabilities": {"tools": {"listChanged": true}}` if it will notify
  clients when its tool set changes. Clients that have opened a `subscriptions/listen` stream with
  `toolsListChanged: true` receive `notifications/tools/list_changed` and are expected to re-issue `tools/list`
  to refresh their cached list. Servers **SHOULD** return tools in a deterministic order specifically so
  clients can cache the list and so LLM prompt caches (tool definitions are part of the cached system context)
  stay warm across calls when nothing has changed. [DOC S2135 via modelcontextprotocol.io/specification/
  2026-07-28/server/tools — cite the identical source already recorded elsewhere in this kb as S2135
  (`_sources.csv`) per the reuse rule]
- Tool identity/versioning fields in the current spec: `name` (unique within a server, 1-128 chars, restricted
  charset, case-sensitive), optional `title` (display name), `description`, `inputSchema`/`outputSchema` (JSON
  Schema, default draft 2020-12), `annotations` (untrusted unless the server is trusted). The spec has **no**
  explicit version field on an individual tool — versioning of tool *behavior* is left to the server author (e.g.
  encoding a version in the name, as the spec's own example `DATA_EXPORT_v2` shows) or to `server.json` at the
  server level (see below), not to a per-tool field. [DOC S2135]
- The **MCP Registry** (`github.com/modelcontextprotocol/registry`, community-run by a Registry Working Group,
  MIT-licensed) is a community-driven directory of MCP servers, similar in role to a package-manager registry. A
  `server.json` manifest is the unit of registration and carries at least `name`, `version`, `packages` (how to
  install/run the server) and `remotes` (remote endpoints), though the exact schema (required vs. optional fields,
  `$schema` URL) was not pinned as an artifact in this pass (see `gaps.md`). The registry entered a v0.1 "API
  freeze" (no breaking changes) on 2025-10-24 after launching in preview on 2025-09-08, and is not yet
  general-availability. [DOC S2012]
- **Contract tests for tool schemas** (a generated-contract file compared byte-for-byte in CI):
  the MCP spec's own security guidance obliges servers to validate all tool inputs and clients to validate
  structured results against `outputSchema` when one is declared — a generated-contract approach that turns this
  into a CI gate already goes further than the spec requires (the spec only "SHOULD" on schema validation).
  [DER S2135: a hard CI gate is stricter than the spec's own SHOULD-level guidance, which is a fact worth
  recording, not a gap]
- **How clients react to a changed tool description**: the spec's client guidance says clients **SHOULD** "show
  tool inputs to the user before calling the server" and periodically re-list tools; it does not mandate that a
  changed *description* alone re-triggers a permission re-prompt. Whether Claude Code specifically re-prompts a
  user/organization permission rule when an MCP tool's description changes (as distinct from its name, which is
  what `managed-mcp.json`'s `serverCommand`/`serverName` matching keys off) was not found in the fetched docs.
  [UNK: recorded in `gaps.md`]

### Implication for a single-repo, unpublished MCP server
- A "one job per runner and trigger, small job definitions" policy plus a generated-contract CI check together
  imply the contract check already covers the failure a registry's `listChanged`/versioning machinery exists
  to catch elsewhere (a client silently using a stale tool definition) — a single-repo, generated-contract
  approach may not need registry-style publishing at all, if the server is never published to any registry and is
  instead distributed as package data alongside the rest of the codebase. [DER]

_Agent: agents-extra_

## QG24. Cost governance for a team using Claude Code

- **Published cost baseline**: across enterprise deployments, Anthropic states an average cost of about **$13 per
  developer per active day** and **$150-250 per developer per month**, with costs staying below $30/active-day for
  90% of users. [DOC S2013 (code.claude.com/docs/en/costs, reused as S2132 already recorded by another part of this
  kb under the identical URL)]
- **Managed settings for spend/rate limits**: an org sets `modelPricing` (a managed-settings-only key, requires
  Claude Code v2.1.242+) so `/usage`, the status line, and OTel figures reflect contracted rates rather than list
  price; on the Claude Console (API) path, workspace spend limits and a per-workspace **rate-limit** cap are set in
  the Console, and Anthropic publishes **TPM/RPM-per-user recommendations that shrink as team size grows** (e.g.
  200-300k TPM / 5-7 RPM per user for 1-5 users, down to 10-15k TPM / 0.25-0.35 RPM per user for 500+ users),
  because concurrent usage share falls as headcount rises. [DOC S2013]
- **Usage/spend visibility paths** depend on how the org buys Claude Code: (a) Claude for Teams/Enterprise — a
  per-seat allowance on a rolling 5-hour/weekly window, a spend report CSV (daily), an analytics dashboard for
  adoption, and for Enterprise the **Enterprise Analytics API** (`read:analytics` scope, per-user usage/cost across
  Claude surfaces); (b) Claude Console (API) — workspace spend limits plus the **Claude Code Analytics API** for
  daily per-user metrics via an Admin API key; (c) cloud providers (Bedrock/Vertex/Foundry) — billed by the cloud
  account, with **OpenTelemetry export** as "the only option that streams per-user token and cost metrics into your
  own observability stack in near real time" on every setup, or a self-hosted "Claude apps gateway" / third-party
  LLM gateway (e.g. LiteLLM, unaffiliated with Anthropic) for per-key spend tracking. [DOC S2013]
- **The Admin Usage & Cost API** (`platform.claude.com`, Admin API key or `org:admin` OAuth scope) exposes
  `/v1/organizations/usage_report/messages` (token counts by model/workspace/API-key/service-tier/geo, bucket
  widths 1m/1h/1d, up to 1,440 1-minute buckets or 31 daily buckets) and `/v1/organizations/cost_report` (USD cost
  by workspace/description, daily buckets only); data lands within about 5 minutes of the API call completing, and
  the API supports polling once per minute for sustained use. Per-user Claude Code cost specifically is better
  served by the separate **Claude Code Analytics API**, which the Usage & Cost API's own docs recommend over
  slicing usage by many individual API keys. [DOC S2013]
- **Model choice per task**: vendor guidance is to default to Sonnet for coding and reserve Opus for complex
  architecture/reasoning, since Opus costs more; subagents can be pinned to a cheaper model (e.g. `model: haiku`)
  independently of the main session; a multi-instance "agent teams" feature is stated to use roughly **7x more
  tokens** than a standard session when teammates run in plan mode, because each teammate holds its own context
  window. [DOC S2013]
- **Cost attribution per engineer**: Claude Code's own `/usage` command attributes recent usage to skills,
  subagents, plugins, and *individual MCP servers* (a server's share counts only requests that consumed one of its
  tool results) — but attribution is by MCP **server**, not by individual **tool** within a server, so a project's
  planned MCP tool set would show as one line for the whole server, not broken out per operation. [DOC S2013;
  UNK/gap: no per-tool attribution found, recorded in `gaps.md`]

### Implication for a no-always-on-service, no-container design
- A "no always-on service... CLI and stdio MCP server only" policy plus a "no container, no broker" policy
  together mean such a design cannot rely on a central LLM gateway (e.g. LiteLLM) for per-engineer cost
  attribution the way the vendor docs suggest for cloud-provider billing — the only paths compatible with that
  kind of design are: (a) each engineer's own Claude Console/Enterprise account-level reporting (outside the
  adopting team's control), or (b) OpenTelemetry export from the engineer's own workstation, which such a policy
  would already permit as "no host state... logs as JSON lines on stderr" — cost governance here is a Claude
  Code/organization-admin concern, not something such a design's own instance needs to implement. [DER]

_Agent: agents-extra_

## QG25. RBAC for agents and MCP tools: which tool a caller may use, agent identity vs delegated identity, least privilege

- `mcp/authorization.md` (S707, pinned to the 2026-07-28 revision) already covers audience-bound tokens, RFC 9728 discovery and CIMD. **New in the draft revision fetched for this part** (S2045, later than S707): MCP servers **SHOULD** send a `scope` parameter in the `WWW-Authenticate: Bearer` header of a 401, naming exactly the scopes needed for the resource being called, "following the principle of least privilege and preventing clients from requesting excessive permissions" — this is the spec's own least-privilege mechanism for *which tool/resource a token may reach*, not just *which server*. [DOC S2045]
- The draft also formalizes **step-up (incremental) scope authorization** at runtime: a tool call with insufficient scope gets `403 Forbidden` + `WWW-Authenticate: Bearer error="insufficient_scope", scope="files:write", resource_metadata=..."`; the client is required to union newly-required scopes with previously-granted ones and re-authorize, rather than replacing them — this is the spec-level analogue of a tiered confirmation gate, but implemented as OAuth scope elevation rather than an interactive confirm prompt. [DOC S2045]
- MCP's `scopes_supported` field in Protected Resource Metadata is defined as "the minimal set of scopes necessary for basic functionality," with additional scopes meant to be requested incrementally — i.e., the spec's own worked example of scope minimization is exactly a tiered-access pattern (tier 0 read vs tier ≥2 write), just expressed as OAuth scopes rather than an application-level confirmation gate. [DER S2045]
- None of this changes `mcp/authorization.md`'s finding that **stdio transports SHOULD NOT follow the authorization spec at all** and take credentials from the environment (S707) — so the scope/step-up mechanism above applies only if/when a stdio MCP server is ever exposed over HTTP, not to a stdio-only server. [DER S707]
- **Claude Code's own tool-level RBAC** (not covered in `mcp/*`, which documents the *protocol* not a specific client): Claude Code supports a `permissions.mcp_tools` list of `{pattern, allowed}` rules matching `mcp__<server>__<tool>` (or, for a plugin-bundled server, `mcp__plugin_<plugin-name>_<server-name>__<tool-name>`), letting an operator allow or deny individual MCP tools by name pattern, independent of the server's own auth. [DOC S2041]
- Claude Code layers a **second, organization-level control on top of per-tool rules** for connectors managed by an organization: each tool on a managed connector can be set to `ask` (Claude Code always prompts, with the reason "Your organization requires approval for this tool," even in `acceptEdits`/`auto`/`bypassPermissions` modes, and is denied outright in `dontAsk` mode) or `blocked` (the tool is filtered out before the model ever sees it, identically in the desktop app and claude.ai chat). `/mcp` shows which of these settings applies to each tool on a connector. [DOC S2041]
- **`managed-settings.json`** is Claude Code's file-based policy mechanism: it "applies above every other level, so no user, project, local, or `--settings` value overrides them," apart from a short list of security-sensitive exceptions where a *stricter* value from a lower level still counts; it also carries `allowedMcpServers`/`deniedMcpServers` (allow/deny by server name or URL pattern), `managedMcpServers` (organization-provided server definitions) and `disabledMcpjsonServers` (reject specific project-scoped servers) — this is the kind of mechanism relevant to any instance-kind/role model, since it is a machine-level, non-overridable policy rather than a per-session choice. [DOC S2042]
- **Agent identity vs the user's delegated identity** (the core of QG25's second half) is now a *named, first-class Entra construct*, not just a design pattern some systems already follow by policy. Microsoft Entra Agent ID's **agent identity** is documented as "a special service principal... that represents an identity that the agent identity blueprint created and is authorized to impersonate," with three distinct token-acquisition modes stated explicitly: (a) an autonomous agent acquiring an **app token** where the token's subject is the agent identity itself; (b) an interactive agent called with a user token acquiring a **user token on behalf of the agent identity**, where the token's *subject is the user* and the *actor is the agent identity*; and (c) the agent identity requesting tokens where it itself is the audience. [DOC S2040]
- **Agent identities never hold their own credentials.** All credentials (federated identity credentials, certificates, or client secrets) live on the reusable **agent identity blueprint**, not on the individual agent identity; the blueprint acquires tokens on the agent identity's behalf. Agent identities are always single-tenant even when their blueprint is published as multitenant (a multitenant blueprint creates a separate tenant-local agent identity per tenant it's added to). [DOC S2040]
- **Consistent, fleet-wide policy is the blueprint's stated purpose**: because every agent identity of a "kind" (e.g. "Sales Assistant Agent") shares one blueprint, an Entra admin can "apply a conditional access policy to all [agents of that kind], disable all of them, or revoke a permission grant for all of them" in one action — this is Microsoft's own stated least-privilege/blast-radius argument for the blueprint model, distinct from OWASP's or NIST's framing (neither of which was independently confirmed to state this same point — see `gaps.md`). [DOC S2040]
- **This is directly relevant to a design's own agent-vs-user distinction.** A policy that "interactive calls use the engineer's own identity... shared state is written only by scheduled sync jobs under read-only identities" is architecturally the same split Entra Agent ID formalizes with agent-identity "actor" tokens (case b above) vs plain app tokens (case a). A design need not use Entra Agent ID for this split to hold, so this is a *naming and tooling* parallel, not something such a design currently consumes. [DER S2040]
- **Agent identity is in public preview**, delivered through "Microsoft Agent 365, available through Frontier," Microsoft's early-access program, from early 2026, with a stated roadmap of "more access management, security, and identity governance capabilities... over the next six months," plus support for Security Copilot, Microsoft 365 Copilot and third-party agents. [DOC S2051 — reached via WebSearch synthesis only, not independently WebFetched; see gaps.md]
- **App roles vs OAuth scopes, restated in agent terms**: `auth/group-claims.md` already establishes that app roles assigned to groups are Microsoft's recommended authorization pattern over raw `groups` claims (smaller token, decouples assignment from app config) — nothing fetched in this part contradicts or extends that specifically for agent identities; agent identity authorization instead runs through the blueprint's own Graph-permission grants (S2040's "read the signed-in user's calendar" example), which is a delegated-permission-consent model, not the app-role-on-group pattern `group-claims.md` covers. [DER S2040 vs auth/group-claims.md — different mechanism, not a conflict]

### Deepening (QG25): app roles assigned to groups vs group claims, restated for agent authorization specifically (closing a prior gap)
- **A documented, concrete gap in the app-role-on-group pattern for service principals**: "Currently, if you add a service principal to a group, and then assign an app role to that group, Microsoft Entra ID doesn't add the `roles` claim to tokens it issues." This means the app-roles-on-groups pattern `auth/group-claims.md` recommends for *users* does **not** work the same way for a service principal (the identity type an agent or a `site`/`ci` instance actually is) — a service principal's own direct app-role assignment, not group membership, is required for the `roles` claim to appear in its token. [DOC S2053]
- App roles are declared per application registration ("move with the application," removed if the app registration is removed) and can target `Users/Groups`, `Applications`, or both when defined; when targeting applications, an assignment becomes an **application permission** requiring admin consent, used by "daemon apps or back-end services that need to authenticate and make authorized API calls as themselves, without user interaction" — the shape of a `site` or `ci` instance's own token, as distinct from a user's delegated token. [DOC S2053]
- Microsoft's own stated reason to prefer app roles over group claims: an app role's `Value` string is fixed by the API's own app registration and portable across tenants, whereas "an app using groups for authorization will break in the next tenant as both the group ID and name could be different" — directly relevant if a single-tenant tool were ever distributed to another tenant, though such a tool may run in one tenant only by design. [DOC S2053]
- **Closing the QG25 gap on OWASP-specific agent-vs-user-identity guidance**: the OWASP **Non-Human Identities (NHI) Top 10** (2025) is the fetchable, structured OWASP artifact for this question (the "Agentic AI Threats and Mitigations" PDF remained unfetchable, see `gaps.md`). Its ten risks: NHI1 Improper Offboarding, NHI2 Secret Leakage, NHI3 Vulnerable Third-Party NHI, NHI4 Insecure Authentication, NHI5 Overprivileged NHI, NHI6 Insecure Cloud Deployment Configurations, NHI7 Long-Lived Secrets, NHI8 Environment Isolation, NHI9 NHI Reuse, NHI10 Human Use of NHI. [DOC S2058]
- Two entries map directly onto this part's own facts: **NHI7 (Long-Lived Secrets)** — "sensitive NHIs such as API keys, tokens, encryption keys, and certificates with expiration dates that are too far in the future or that don't expire at all" — is the same failure mode this part's GitLab-PAT and `keyring`/`msal-extensions` findings describe concretely; **NHI10 (Human Use of NHI)** — misuse of an application/service identity "for manual tasks that should be performed using individual human identities" — is the named OWASP risk that a policy of "interactive calls use the engineer's own identity; shared state written only by scheduled jobs under read-only identities" is itself a mitigation for, independent of and prior to OWASP's own list. [DOC S2058]

_Agent: agents-authz_

## QG26. Entra ID groups and PIM in an agent's authorization path

- `auth/entra-intune-rbac.md` already answers the core latency question this QG asks (PIM for Groups activation visible at next Graph token acquisition; on-prem AD only via Cloud Sync writeback, ~20 min) — not repeated here.
- **New precision on the write-side latency**: Microsoft's own PIM-for-Groups activation page states the active-assignment write itself, not just the eventual token visibility, happens "within seconds" in both directions — "Microsoft Entra PIM creates an active assignment... within seconds" on activation, and "removes the user's group membership or ownership within seconds as well" on deactivation (manual or by expiry). The page also warns explicitly that an *application* relying on cached group membership may not reflect either direction immediately, and that "signing out and signing back in might help" — this is Microsoft's own statement of exactly the token-cache gap `entra-intune-rbac.md` already derived. [DOC S1282, reused]
- **PIM-for-Groups eligible-ownership deactivation can be blocked for up to 30 days** by a documented rule: Entra ID will not remove the *last active owner* of a group, so if the sole active owner is removed from the tenant while an eligible owner has an active (PIM-activated) ownership, PIM retries deactivating that eligible owner's ownership for up to 30 days and gives up (leaving them permanently active) if no other active owner is added in that window. Relevant if role groups are ever owned via PIM rather than by a fixed administrative account. [DOC S1282]
- **Role-assignable groups**: a group must have `isAssignableToRole: true` set **at creation time only** — "creating a group to which Microsoft Entra roles can be assigned is a setting that cannot be changed later" — and needs Entra ID P1 or P2, `Privileged Role Administrator` to create, and cannot be a dynamic-membership group. A tenant is capped at **500 role-assignable groups**. [DOC S2050]
- Role-assignable groups are the prerequisite class of group PIM for Groups is designed to protect (an "eligible"/"active" Entra-role assignment on a group requires the group be role-assignable); this is the mechanism `auth/entra-intune-rbac.md`'s PIM-for-Groups facts implicitly assume but did not itself state the creation-time-only and 500-group-cap constraints for. [DER S2050, auth/entra-intune-rbac.md]
- **CAE / claims-challenge behaviour for a group-membership change is already fully answered** in `auth/revocation.md` §(c): group/role membership changes are not on Entra's CAE critical-event list, so a bare role-group removal does not get near-real-time enforcement even for a `cp1`-aware client; it waits for ordinary token/ticket expiry. Not repeated in detail here.
### Deepening (QG26): PIM for Groups activation-to-effect latency, with numbers (closing the prior gap)
- **Microsoft's own PIM-for-Groups page states concrete, numbered latency for the one scenario it documents in full: provisioning a PIM-activated group membership into a SCIM-provisioned application.** On ordinary (non-PIM) group-membership change, provisioning to the application waits for "the next synchronization cycle," which "runs every 40 minutes." On a **PIM activation**, the same group-membership provisioning instead completes in **2-10 minutes**, specifically for "the first five users within a 10-second period activating their group membership for a specific application"; a **sixth or later activation within that same 10-second window is throttled back to the 40-minute sync cycle instead** — an explicit, numbered rate limit ("five requests per 10 seconds," "per enterprise application") that is new to this deepening pass. [DOC S2052]
- This number answers a **different half of QG26's latency question than S1282 (reused) already answers**: S1282 states the PIM *active-assignment write itself* (the group-membership/ownership record) completes "within seconds"; S2052's 2-10-minute figure is the *downstream provisioning* of that membership into a target application via SCIM — a distinct, slower step that only applies to apps provisioned from the group (Entra roles, Azure roles and most Graph/token-claim consumers read the group membership directly and are governed by the ordinary token-cache behaviour `auth/entra-intune-rbac.md` already documents, not this SCIM-provisioning number). [DER S2052, S1282, auth/entra-intune-rbac.md — three distinct latency regimes, not one]
- Microsoft's own explicit warning against relying on PIM for Groups for role-scoped Microsoft 365 workloads: "to avoid activation delays, use PIM for Microsoft Entra roles instead of PIM for Groups to provide just-in-time access to SharePoint, Exchange, or Microsoft Purview portal" — a documented case where the group-mediated PIM path is *slower*, not just architecturally different, than assigning the role directly. [DOC S2052]
- **Role-assignable groups and PIM for Groups are independent properties, restated more precisely than `entra-intune-rbac.md`'s implicit assumption**: any non-dynamic, non-on-prem-synced group can be enabled in PIM for Groups regardless of whether it is role-assignable; only a **role-assignable** group can be assigned an actual Entra role, and the **500-role-assignable-group cap is per-tenant, not a cap on PIM-for-Groups-enabled groups generally** (more than 500 groups total can be PIM-for-Groups-enabled; the 500 cap applies only to the role-assignable subset). Role-assignable groups additionally cannot have another group nested inside them as an *active* member (an *eligible* nested membership is allowed). [DOC S2052]
- **PIM-for-Groups eligible-ownership deactivation blocked for up to 30 days** (S1282's finding) is restated identically on this page, confirming it as a stable, cross-referenced fact rather than a one-source claim. [DOC S2052, S1282]
- **Agent identities and PIM remain unconfirmed** — S2052 (like S2040/S2051) never mentions agent identities or service principals as PIM-for-Groups members/owners; this gap is not closed by this pass and is restated, narrowed, in `gaps.md`.

- **How a stdio tool running as the engineer reads "may this person run tier N"** — the concrete mechanisms (`checkMemberGroups`/`getMemberGroups`, the `groups` token claim and its overage behaviour, and Kerberos PAC group SIDs via AD) are already fully covered by `auth/role-source-options.md` and `auth/group-claims.md`; nothing fetched here adds a new mechanism. The one addition from this part is that **agent identities have their own, separate authorization surface** (Graph-permission grants on the blueprint, S2040) rather than reading Entra group membership the way a client/scheduled-job instance does — so a system that adopted Entra Agent ID for a scheduled-sync role would answer "may this instance run tier N" by the blueprint's granted permissions, not by a `checkMemberGroups` call against a role group. [DER S2040, auth/role-source-options.md]

_Agent: agents-authz_

## QG27. Issuing API tokens for agents and services

- `auth/workload-identity.md` already covers Entra federated identity credentials (exact-match and flexible/preview) for `ci` (GitLab OIDC) and Azure Arc managed identity for `site`, and `auth/msal-public-client.md`/`workload-identity.md` cover certificate credentials, their PEM/PFX requirement, and rotation guidance (180-day max lifetime) — not repeated here.
- `mcp/authorization.md` already covers MCP OAuth 2.1, RFC 8707 resource indicators, and DCR's deprecation in favour of Client ID Metadata Documents (CIMD) as of the 2026-07-28 revision (S702) — not repeated here.
- **On-behalf-of (OBO) flow, not previously detailed** (`auth/delegation-kcd-obo.md` exists per the sources grep but is outside this agent's read set — cited by id S1297 only): OBO exchanges a token *already issued to a middle-tier API* for a new token to call a *downstream* API, preserving the original user's identity and *delegated* scopes only — "roles remain attached to the principal (the user) and never to the application operating on the user's behalf, to prevent the user gaining permission to resources they shouldn't have access to." [DOC S1297]
- OBO **only works for user (delegated) tokens**; a service principal with only an app-only token cannot use OBO and must instead use the client-credentials flow — directly relevant if a client process ever fronted a second downstream API on the engineer's behalf, versus a scheduled-sync/CI instance doing app-only work, which cannot use OBO at all. [DOC S1297]
- OBO carries an explicit relay-token security warning: "DO NOT send access tokens that were issued to the middle tier to anywhere except the intended audience," because relaying access tokens to a client instead of letting the client acquire its own increases interception risk and breaks Conditional-Access step-up (MFA, sign-in frequency) and device-based policies (MDM, location) for the downstream call. [DOC S1297]
- **GitLab personal access tokens (PATs) and project/group access tokens**: default expiry is 365 days from creation; a documented feature-flagged extension to a **400-day maximum** landed in **GitLab 17.6**; administrators can set a tenant/instance-wide maximum lifetime lower than that; tokens expire at midnight UTC on the expiry date. [DOC S2046]
- **Rotation vs revocation are distinct, both irreversible actions**: "rotate" creates a new token with the same permissions/scope and immediately deactivates the original; "revoke" immediately invalidates the token and prevents further use; GitLab's own guidance steers automation toward **CI/CD job tokens with fine-grained permissions for pipeline authentication** instead of a PAT, precisely because a PAT is a long-lived, broadly-scoped, human-owned credential unsuited to unattended jobs. [DOC S2046]
- **Project/group access tokens** (as opposed to personal access tokens) are attached to the project or group itself rather than to a user account — the documented alternative to using a real engineer's PAT for a service account, though this part's single fetch did not surface their scope list or expiry rules distinctly from the personal-token page; flagged as a shallow answer, not a gap requiring a retry (the CI/CD job-token recommendation already answers the "don't use a PAT for automation" question generically). [DOC S2046]
- **General implication**: a policy that requires a merge request as the change record and forbids MR-code running with a domain identity, combined with the GitLab guidance above, means CI-role automation (S2046) and `auth/workload-identity.md`'s Entra FIC federation (no stored secret at all) are the two Microsoft/GitLab-documented alternatives to any GitLab PAT for a project's own CI needs — a PAT would be the wrong tool for a CI/protected-runner role per both vendors' own stated preference, tightening what `auth/workload-identity.md` already recommends. [DER S2046, auth/workload-identity.md]
- **New: a full lifetime/rotation/revocation/audit/storage table for every credential kind touched by this part** is now `agents/api-tokens.csv` (one row per kind: Entra FIC, Entra app cert, GitLab PAT, GitLab project token, GitLab CI job token, GitLab `id_tokens`, Vault AppRole SecretID, Vault dynamic DB credential, Azure Key Vault secret, Claude Code login credential, Claude Code MCP OAuth token, OBO downstream token). [DER, synthesizing S2041, S2046, S2047, S2049, S2054, S2055, S2056, S740, S1297, auth/workload-identity.md, auth/msal-public-client.md]

### Deepening (QG27): Vault dynamic secrets and GitLab CI's native secrets integration (closing prior gaps)
- **Vault's database secrets engine** generates unique, per-request database credentials dynamically via a plugin interface, rather than a single shared static password; default **1-hour TTL, 24-hour max TTL** (adjustable per role); Vault's own stated reason: "every service is accessing the database with unique credentials, it makes auditing much easier when questionable data access is discovered." Credentials are revoked automatically by Vault's own internal lease-revocation system at lease expiry, or renewed before expiry. Supports 20+ database engines (PostgreSQL, MySQL/MariaDB, MSSQL, Oracle, MongoDB, etc.); static roles offer scheduled/cron-style password rotation with a configurable password policy (default 20-character mixed-case/number/special) as the alternative to per-request dynamic credentials. [DOC S2054] This directly answers the prior gap for a rotating SQL Server credential: a `site` instance's SQL write identity (against a temporal-tables schema) could in principle be a Vault-issued dynamic MSSQL credential with a short TTL rather than a long-lived service account password — a fact for a future task to weigh, not a recommendation. [DER S2054]
- **GitLab's native secrets integration** (`ci/secrets/`) supports four providers out of the box — **HashiCorp Vault, Google Cloud Secret Manager, Azure Key Vault, AWS Secrets Manager** — authenticated via GitLab's own **`id_tokens`** (OIDC JWTs), the same mechanism `auth/workload-identity.md` already documents for Entra FIC; a job can also authenticate manually to any other OIDC-compliant secrets provider. The stated operational difference from ordinary CI/CD variables: "secrets must be explicitly requested by a job," fetched at run time, rather than "always available in jobs" the way every CI/CD variable is injected into every job's environment by default. GitLab's docs do not explicitly rank this as more secure than a masked/protected variable, but the on-demand model structurally reduces which jobs a given secret's value ever reaches. [DOC S2055]
- **Vault's JWT/OIDC auth method** is the concrete mechanism GitLab's `id_tokens` would use against a self-hosted Vault: a role bound with `bound_audiences` (must exactly match the JWT's `aud` claim) and optional `bound_claims` (arbitrary claim/value matching, e.g. restricting by GitLab project or ref), then `vault write auth/jwt/login role=<name> jwt=<token>` exchanges the GitLab-minted JWT for a Vault token scoped to the role's policies and TTL. [DOC S2056] Combined with a "one job per runner and trigger" rule and a policy that MR code never runs with a domain identity, this gives a concrete non-PAT path for a protected `sync` job to reach Vault-issued secrets without any static credential stored in GitLab. [DER S2056]

### Deepening (QG28): Claude Code `apiKeyHelper` behaviour, not previously detailed
- Claude Code's settings system **hot-reloads `apiKeyHelper` (and other credential helpers) mid-session without a restart**: "Claude Code watches your settings files and reloads them when they change, so it applies most edits to the running session without a restart, including edits to `permissions`, `hooks`, and credential helpers such as `apiKeyHelper`." This means a Vault- or Key-Vault-backed rotation of the underlying secret the helper script reads can propagate to a running CLI process without restarting it, once the helper's own TTL (`CLAUDE_CODE_API_KEY_HELPER_TTL_MS`, default 5 minutes) next elapses — closing the loop between "external secret store rotates a credential" and "the CLI picks it up" without a stored, static value at any point. [DOC S2057] `managed-settings.json` policy (S2042, already in `answers.md`) sits above this in precedence and can pin or forbid a project's own `apiKeyHelper` value organization-wide.

_Agent: agents-authz_

## QG28. Storing tokens and secrets on engineer workstations, CI and a future site host

- **Python `keyring`** (the OS-keychain abstraction library named in this topic) wraps: **macOS Keychain**, **Linux** Freedesktop Secret Service (GNOME) and KDE KWallet, and **Windows Credential Locker**; current release **25.7.0** (2025-11-16), MIT licence; core API is `set_password`/`get_password`/`delete_password`/`get_credential`. [DOC S2043]
- **`keyring`'s own documented threat gap on macOS**: "any Python script or application can access secrets created by keyring from that same Python executable without the operating system prompting the user for a password" — i.e. macOS Keychain's per-app ACL is keyed to the *Python interpreter binary*, not to the calling script, so any Python process using the same interpreter can silently read another Python program's `keyring`-stored secret unless the user manually restricts Python's Keychain access-control entry. [DOC S2043]
- **`keyring` explicitly states "no analysis has been performed"** on the security properties of its Linux Secret Service, KDE KWallet, or Windows Credential Locker backends — i.e., the library ships OS-native storage integrations without a documented, vendor-asserted threat model for most of the backends a `client` workstation would actually use. [DOC S2043]
- **`msal-extensions`** (MSAL Python's persistent token-cache library, already referenced without detail in `auth/msal-public-client.md`'s "SerializableTokenCache (or msal-extensions persistent cache)" line): backs onto **Windows DPAPI**, **macOS Keychain**, and **Linux libsecret encryption with an explicit plaintext fallback**; MIT licence. [DOC S2044]
- **`msal-extensions`'s own documented fallback warning**: on Linux, when libsecret encryption is unavailable, the library logs "Encryption unavailable. Opting in to plain text" and stores the token cache **unencrypted** rather than failing closed — a silent degrade from "OS keychain" to "plaintext file on disk" that a `client`/`site` deployment on a headless or misconfigured Linux host could hit without an explicit error. [DOC S2044] This is the same category of failure as a data-read rule that says "unknown is never absent," applied to secrets storage: a component reading `msal-extensions'` cache state should treat "plaintext fallback silently engaged" as a condition to detect and refuse, not a transparent degrade — stated here as a design-relevant fact. [DER S2044]
- **`msal-extensions`'s own documented scope for use**: recommended specifically for "public client applications such as desktop apps only," with explicit caution against using it in a web application "due to potential scale and performance issues" — directly matches a `client` (CLI on an engineer workstation) case and argues against reusing the same mechanism for a hypothetical always-on web-facing component (already out of scope for a CLI+stdio-MCP design regardless). [DOC S2044]
- **Azure Key Vault**: authentication via Microsoft Entra ID; authorization via **Azure RBAC** (can cover both vault management and data access) or the older **Key Vault access policy** model (data access only); Standard tier uses FIPS 140 Level 1 software crypto, Premium tier offers FIPS 140-3 Level 3 HSM-protected keys; "Key Vault is designed so that Microsoft doesn't see or extract your data." [DOC S2047]
- Key Vault's documented threat it addresses for the `key-management-options.md` gap: a **shared key store** (named there as an alternative to a certificate-backed CMK pinned to one machine's local cert store) — Key Vault's access-control model (RBAC/access-policy scoped per vault, per application) is exactly the mechanism `key-management-options.md` flagged as needed to avoid replicating a CMK certificate to every `client` workstation. [DER S2047, auth/key-management-options.md]
- **GitLab CI/CD variables**: "masking a CI/CD variable is not a guaranteed way to prevent malicious users from accessing variable values," and variables "could be accidentally exposed in a job log, or maliciously sent to a third-party server" — GitLab's own stated mitigation is reviewing every `.gitlab-ci.yml` change before merge (especially from forks), and its own stated alternative is to "connect with an external secrets management provider to store and retrieve secrets" rather than store the raw secret as a CI variable at all. Protected variables restrict a variable to pipelines on protected branches/tags only, directly matching a policy requirement that release content and any privileged secret stay off unprotected MR runners. [DOC S2046 note: this fact is drawn from the same fetch batch and documented on the GitLab CI/CD variables page, distinct URL from S449 already in `_sources.csv`/`_sources.csv` for the same topic — reused as S449] [DOC S449]
- **HashiCorp Vault**: positioned by its own docs as providing "centralized, well-audited privileged access and secret management" across on-prem/cloud/hybrid, for "credentials, encryption keys, authentication certificates." [DOC S2048] The fetched overview page is largely product framing and did not itself state dynamic-secrets/TTL mechanics in the passage retrieved — see `gaps.md`.
- **Vault's `AppRole` auth method** is the machine/CI-identity-shaped mechanism directly relevant to QG27/28's "options for issuing tokens to services": a two-part credential (`RoleID`, a stable, low-sensitivity role identifier, plus `SecretID`, the actual secret) with **configurable TTL and use-count limits on the `SecretID`** (example given: `secret_id_ttl=10m`, `secret_id_num_uses=40`), explicitly "oriented to automated workflows (machines and services)... less useful for human operators," with **Pull mode** (Vault generates the `SecretID` server-side) preferred over **Push mode** (caller supplies its own value) "in most cases," and a documented recommendation to use short-lived **batch tokens** with AppRole rather than standard (longer-lived, revocation-list-tracked) tokens. [DOC S2049]
- **What must never happen, restated from a "secrets never on argv/env/output" rule with the specific mechanisms above as the concrete failure modes it forbids**: such a rule states secrets are never put on argv, in a child process's environment, or in output. The mechanisms fetched here show two ways that rule is *routinely violated by default* in the tools a project is likely to use: (a) GitLab CI variables surface as literal environment variables in every job unless masked, and masking is explicitly "not a guaranteed way to prevent" leakage into logs (S2046/S449) — so a GitLab job that must call a token-holding process should pass the token by file path or via a `headersHelper`-style callback, never by exporting it as a job variable a subprocess inherits; (b) `msal-extensions`'s silent plaintext fallback on Linux (S2044) is a second concrete way a "secure OS keychain" claim quietly becomes "readable file on disk" without violating any explicit rule the library states — the caller must check which backend was actually used, not assume the intended one. [DER S2046, S449, S2044]
- **Claude Code's own credential handling as a fourth workstation option, not previously in `mcp/*` or `auth/*`**: Claude Code stores its own OAuth session/API credentials in the **macOS Keychain**, or in `~/.claude/.credentials.json` (mode `0600`) on Linux and Windows (inheriting the user-profile ACL) as a fallback when the Keychain is unavailable (e.g. locked in an SSH session); it also supports an `apiKeyHelper` script (re-run on a 5-minute default TTL, configurable via `CLAUDE_CODE_API_KEY_HELPER_TTL_MS`) as a documented escape hatch for "dynamic or rotating credentials, such as short-lived tokens fetched from a vault" — a directly reusable pattern for wiring a project's own vault-backed secrets into the same CLI process without putting them on argv or in a static env var. [DOC S2041] Separately, MCP server OAuth tokens in Claude Code are stored "securely" in the system credential store (macOS Keychain) or a credentials file on other platforms, never in `.mcp.json`/`~/.claude.json`, and are scoped per MCP server endpoint (authenticating one server does not authenticate another). [DOC S740, reused]

_Agent: agents-authz_

## QG29. What to dispatch to another agent or service vs keep in-process
- Vendor criteria converge on: a stable, independently owned domain boundary (Copilot Studio's
  "specialization"/"separation of concerns"), reuse by more than one caller ("reusability" — one
  specialist agent connected to several primaries), and isolation of verbose or sensitive intermediate
  output (Claude Code's "would flood your main conversation" signal). [DOC S2080, S2083]
- Latency is a documented reason **not** to dispatch: a non-fork subagent "starts fresh and may need
  time to gather context," and Copilot Studio connected-agent calls are usage-metered (Copilot Credits)
  on top of that latency. [DOC S2083, S2080]
- Topic 4 (`agents/subagents-vs-deterministic-tools.md`) already covers child-agent-vs-deterministic-tool
  signals (stable call sequence, eval pass rate, token/latency cost, error compounding, auditability,
  confirmation need); this topic does not repeat them. [DOC S1920, S1928 — cited by reference]
- A2A is named only as one transport for peer agent-to-agent handoff, complementary to MCP per the MCP
  roadmap; its protocol detail (spec version, governance, transports, auth) is topic 9's scope. [DOC S2110]
- Applied to an in-process NER step under a "no always-on service" policy:
  keeping detection in-process makes sense specifically when there is one caller
  and the data never needs to leave the workstation before pseudonymization — it fails Copilot Studio's
  own "reusability across callers" trigger for connecting out, when the step has a single consumer.
  [DER S2080: derivation — the vendor's own stated reason to connect an agent (reuse
  across multiple primaries) does not yet hold for a single-consumer NER step]

_Agent: agents-ner_

## QG30. Shared NER / PII-detection as a service: throughput, limits, licensing, pinning
- Presidio ships its own analyzer/anonymizer REST container images (now at
  `ghcr.io/data-privacy-stack/presidio-*`, MIT), deployable via Docker Compose, Kubernetes/AKS or Azure
  App Service, plus a separate documented batch path (Spark/Azure Data Factory over Blob Storage) for
  large datasets — REST and batch are two different documented shapes, not one endpoint. [DOC S-tks3v5p5,
  S2086, S2088, S-g33kybfp, S2090]
- No throughput number (req/s, docs/min, or p95 latency) for any of the five options was found in the
  sources fetched; Presidio's own k8s page only advises planning the cluster from pod CPU/memory
  requirements. [UNK — see `gaps.md`]
- Azure's on-prem PII container is the only option with a published hardware sizing table (1 core/2 GB
  minimum, 4 cores/8 GB recommended, AVX-512 recommended) and a published per-call payload limit (5,120
  chars/doc, 10 docs/call). [DOC S2091]
- Azure's container is metered even when "on-premises": it must reach a billing endpoint every 10-15
  minutes and stops serving after ~10 failed retries; a fully offline mode exists only behind a purchased
  commitment plan and a time-limited downloaded licence file. [DOC S2091]
- Comprehend (API-only, no on-prem container found) covers 22 universal + 14 country-specific PII entity
  types, billed per 100-character unit with a 300-character minimum per request. [DOC S2097, S2099, S2107]
- Google Sensitive Data Protection (Cloud DLP, renamed) ships 200+ infoType detectors, billed by GB
  processed (discovery ≈$1.00/GB, storage inspection ≈$1.50/GB, streaming ≈$0.05/GB per a fetched
  summary); no on-prem container was found. [DOC S2100, S2101; UNK for on-prem — 3 attempts, none found]
- GLiNER has no first-party server/container image; consumers assemble serving themselves from a
  Hugging Face ONNX export plus a generic runtime — a fused export is community-reported at ~30% lower
  GPU latency than the unfused version. [COMMUNITY S2102, S-hocpkynn]
- Version pinning is a real, documented risk: Azure's Text PII 2026-04-15-preview API version added new
  entity types (Password, PIN, Zip code, Airport code) that an older-pinned caller would not receive —
  the concrete mechanism behind "recognizer drift between copies" in QG32. [DOC S2096]
- Presidio's own `presidio-evaluator`/`presidio-research` (MIT) computes precision/recall for a
  recognizer or model version and is the documented tool for measuring such drift, though only as a
  point-in-time comparison, not a continuous cross-consumer monitor. [DOC S-gpnrqpjt, S2105, S2111]

_Agent: agents-ner_

## QG31. What a shared endpoint changes for privacy and security
- Moving detection out-of-process means raw (pre-pseudonymization) text crosses a network boundary to
  reach the shared endpoint — the opposite of an in-process design, where Presidio+spaCy run in-process
  before anything leaves the workstation (`reuse/pseudonymization-tokenization.md`).
  [DER from S2091: derivation — any of the surveyed remote options requires sending
  the document payload to the service process]
- GDPR's own attribution test (Recital 26, Art. 4(5)) turns on whether the receiving party holds or can
  obtain the "additional information" needed to re-identify — already documented in full in
  `privacy/gdpr-pseudonymisation.md`, not repeated here. Whether a shared NER endpoint is a GDPR
  *processor* (processing on the sending team's behalf under Art. 28) or a joint/independent controller
  depends on who decides purposes and means for the NER step; no source fetched for this topic addresses
  that split for a shared internal PII-detection endpoint specifically. [UNK — no vendor or EDPB source
  found stating controller/processor roles for an internal shared NER service; a house policy that
  "pseudonymisation is for the model only; humans see real data under normal RBAC" is a project-specific
  choice, not a GDPR requirement, and does not by itself answer the controller/processor question for a
  shared endpoint]
- Azure's container explicitly does **not** send the analyzed text to Microsoft for its own purposes
  (only billing telemetry) — a documented non-payload-logging claim for that one vendor's on-prem
  container; the equivalent claim was not found for Comprehend or Google Sensitive Data Protection (both
  cloud APIs) in the sources fetched. [DOC S2091; UNK for Comprehend/Google — not addressed by S2097-S2101]
- Consistent pseudonyms across teams (a shared vault/key vs per-team keys) is a linkability question:
  `privacy/gdpr-pseudonymisation.md` already records that EDPB Guidelines 01/2025 were adopted
  2025-01-16 only "as a version for public consultation," with no final version found as of 2026-09-23 —
  so no adopted EDPB text was available this session to test a shared-key design against. [DOC S873, S870
  — reused, see `privacy/gdpr-pseudonymisation.md`; not re-fetched]
- Multi-tenant recognizer configuration (one shared endpoint serving several teams' recognizer sets) is a
  real operational split documented for Presidio only as "customize the recognizer registry from a file"
  per deployment, not as a documented multi-tenant mode within one running service instance —
  `privacy/presidio-recognizer-yaml.md` already covers the file-based customization mechanism, not
  repeated here. [DER from `privacy/presidio-recognizer-yaml.md`, existing file: derivation — one
  registry file per process implies one tenant's recognizer set per running instance unless the deployer
  builds tenant routing themselves]
- Authentication of callers: Azure's container requires an `ApiKey`/`Billing` endpoint pair to start at
  all (S2091); Presidio's own images ship no built-in caller authentication in the fetched docs — an
  operator adding auth in front of a shared Presidio deployment would need to do so themselves (e.g. at
  the ingress/gateway layer), which is outside what was fetched. [DOC S2091 for Azure; UNK for
  Presidio's own auth — not found in S-tks3v5p5/S2086/S-g33kybfp]
- Failure mode on endpoint-down: Azure's container **fails closed for billing** (stops serving after
  connectivity loss) but this is a metering safeguard, not a security fail-closed by design; a house
  rule that "unknown is never absent... a failed, forbidden or timed-out read is unknown" is a
  project-specific rule for device data reads and is not itself a vendor requirement — applying it to a
  shared NER call means a caller must itself treat a down/timed-out endpoint as "detection unknown,"
  never as "no PII found," a design choice a team would have to make, not one any vendor page states
  as PII-detection convention.
  [DER S2091: derivation — none of the PII-detection vendor pages fetched state a
  fail-closed convention for the caller side]

_Agent: agents-ner_

## QG32. Triggers and measures for centralizing (facts and tensions only)
- General implication: a policy that "the tool runs on engineer workstations... there is no always-on
  service, no public endpoint and no gateway" directly opposes standing up or depending on a shared NER
  endpoint for itself; any centralization would be a different, separately-owned service the tool calls
  into, not one it owns. [DER]
- A policy that "pseudonymization is for the model only; humans see real data under normal RBAC" does
  not itself forbid a shared detection endpoint, but the QG31 finding that detection-before-pseudonymization
  means raw text leaves the workstation is in tension with the spirit of keeping the model boundary the
  only place raw data is exposed to a third process. [DER]
- A "secrets never on argv/env/output... one redaction filter covers every sink" rule extends naturally
  to a network payload once detection is remote: the payload sent to a shared endpoint is, by definition,
  the un-redacted original — a new sink such a rule's "every sink" language would need to cover if such
  an endpoint existed. [DER]
- A "no image, chart or broker... a container is a gate row citing a trigger" policy means a container
  image, even for an in-process Presidio component, is presently out of scope; a shared *external*
  service consumed via network call sidesteps building a container in the caller's own repo but does
  not sidestep a no-gateway rule if the caller itself were asked to expose or broker it. [DER]
- A design that gates always-on/network-facing roles as deferred, opened only by an explicit decision,
  treats a shared NER endpoint used by its own MCP server as architecturally the same "always-on
  network-facing capability" question already held closed, not a new gate. [DER]
- What a team would have to measure first, stated as facts about what tooling exists (not a
  recommendation): number of consumer teams/agents that would call the shared endpoint (not measured by
  any source found — a project-internal count, not a vendor fact); recognizer/version drift between
  independent Presidio (or other) deployments, measurable today with `presidio-evaluator`'s published
  precision/recall method [DOC S-gpnrqpjt, S2105, S2111]; detection-quality gaps against a fixed test set,
  the same tool's stated purpose ("evaluate Presidio as a system, a NER model, or a specific PII
  recognizer for precision, recall, and error analysis") [DOC S-gpnrqpjt]; and duplicated maintenance hours
  across teams each running their own Presidio/spaCy stack, which is an organizational measurement no
  vendor source addresses. [UNK for a published duplicated-maintenance-hours metric — not found]
- No source fetched in this session proposes a numeric trigger (e.g. "N consumers" or "X% detection gap")
  at which centralizing a shared NER endpoint is justified; every threshold in this file is either an
  a project-specific policy constraint or an available measurement method, never a vendor-recommended number. [UNK]

_Agent: agents-ner_

## QG33. The Agent2Agent (A2A) protocol

A2A is an Apache-2.0-licensed open protocol for opaque agent-to-agent task delegation, launched by Google in April 2025 and moved to the Linux Foundation on 2025-06-23 for vendor-neutral governance; current spec is v1.0.0 with a v1.0.1 extension mechanism [DOC S2120,S2123]. The normative definition is `specification/a2a.proto`; it is pinned in this kb at commit `43e0c874d3baba68ed84b98678d7f2268438e69f`, sha256 `945df6e34001b2bfd0fd62d9484b63094dfad9d78705e41e2873441c419ae2d1` (see `agents/a2a/a2a-proto-digest.md`) [DOC S2121,S2122]. Agent Cards are JSON discovery documents at a well-known URL describing identity, capabilities, skills and security schemes [DOC S2120,S2126]. Tasks move through an 8-state lifecycle (SUBMITTED/WORKING/INPUT_REQUIRED/AUTH_REQUIRED/COMPLETED/FAILED/CANCELED/REJECTED) [DOC S2120]. Three transports (JSON-RPC 2.0, gRPC, HTTP+JSON/REST); SSE streaming plus webhook push notifications plus polling; auth via API key, Basic/Bearer, OAuth 2.0, OIDC, mTLS [DOC S2120]. The official first-party SDK is Python (`a2a-sdk`, Apache-2.0, Python >=3.10) [DOC S2125]. Microsoft Copilot Studio has GA support (A2A agent connection type, ms.date 2026-08-26) [DOC S2126]; Google ADK supports it natively per WebSearch summary [COMMUNITY]. No Anthropic product was confirmed to speak A2A natively; the only Anthropic-published material found is a joint webinar with Google Cloud demonstrating Claude inside an A2A-orchestrated system via Vertex AI, not a first-party implementation [DOC S2129] — tagged **UNK** for native support. Full detail in `agents/a2a-protocol.md`.

_Agent: agents-a2a-cache_

## QG34. Caching in agent systems

Anthropic prompt caching: up to 4 breakpoints, TTL 5 min (default) or 1 h; minimum cacheable prefix is 512-4,096 tokens depending on model tier; cache writes cost 1.25x (5m) or 2x (1h) base input, cache reads cost ~0.1x (as low as 0.025x-0.05x for the newest tier per the fetched page, flagged for re-check) [DOC S2130,S2131]. Invalidation hierarchy is strictly **tools → system → messages**: a tool-definition change invalidates everything; an image or tool_choice change invalidates system+messages but leaves the tools-level cache; usage fields `cache_creation_input_tokens`/`cache_read_input_tokens` report exactly what was written/read [DOC S2130]. Claude Code (>=2.1.251) surfaces this via `/usage`'s `Prompt cache (main)` line, naming likely causes for misses (e.g. "tool definitions changed") from v2.1.260, and treats its own `/compact` and tool-result clearing as *expected* rebuilds rather than misses; effective cache lifetime drops from 1 h to 5 min once usage credits (rather than subscription/API-key baseline) are being drawn on [DOC S2132]. OpenAI and Azure OpenAI both use a 1,024-token minimum-prefix rule, automatic caching, and a roughly 90% discount on hits, but differ on TTL model (OpenAI: fixed 30 min for GPT-5.6+, or 5-10 min/24h for earlier; Azure: provider-managed, up to 100% discount on Provisioned deployments) [DOC S2133,S2134]. MCP's `tools/list` result already carries `ttlMs`/`cacheScope` (the `CacheableResult` mechanism `mcp/tools.md` cites) and the spec explicitly recommends deterministic tool ordering to raise LLM prompt-cache hit rates [DOC S2135,S2136]. Full detail in `agents/agent-caching.md`.

_Agent: agents-a2a-cache_

## QG35. Designing an MCP server and prompts to be cache-friendly

- Keep the tool list and each tool's name/description/schema byte-for-byte stable across requests; any edit invalidates the tools-level cache and everything below it [DOC S2130].
- Return tools in a deterministic order every time; the MCP spec ties this directly to prompt-cache hit rate, not just to client-side list caching [DOC S2135].
- Keep the system prompt free of timestamps, request ids, or other per-call values; put anything that varies per call into `messages`, since a breakpoint must sit on a block identical across requests [DOC S2130].
- Respect the ordering **tools → system → messages**: put the most stable content first and least stable last, matching Anthropic's own invalidation hierarchy [DOC S2130].
- Measure cache health with the built-in signals rather than a bespoke mechanism (a rule of thumb: "every mechanism is paid for by an observed failure"): Claude Code's `/usage` `Prompt cache (main)` line, or the raw `cache_creation_input_tokens`/`cache_read_input_tokens` usage fields via OTel export (link `claude/otel-monitoring.md`) [DOC S2130,S2132].
- Where an MCP server ever needs per-caller tool visibility (a future tiered tool list), remember the MCP spec permits variation by authorization/granted scope but forbids variation "as a side effect of other requests" — so any tier-based tool filtering must be a pure function of the caller's credentials, not of session history, or it will also fight the cache unpredictably [DOC S2135].

_Agent: agents-a2a-cache_

## QG36. Index of Anthropic's published materials useful to a device-management CLI + MCP tool

30 rows in `agents/anthropic-materials.csv`: 25 engineering-blog posts (2024-09-19 through 2026-04-23) spanning agents, tools, context engineering, evals, multi-agent, code execution with MCP, Claude Code best practices/safety, and skills [DOC S2137-S2154]; the MIT-licensed cookbook repo (`anthropic-cookbook`) with directories for the Agent SDK, tool use/evaluation, prompt caching, cost optimization and skills [DOC S-d5e5aem4]; the `courses` repository (found via WebSearch only, not independently fetched — see gaps) [COMMUNITY]; and three Claude Code / platform docs sections (subagents, skills, prompt caching) [DOC S2157,S2158,S2159]. Detail and one-line reasons per row are in the CSV; `agents/anthropic-materials.md` records how the index was built.

_Agent: agents-a2a-cache_

## QG37. Vendor and practitioner guidance on when not to use an LLM or agent (Anthropic, OpenAI, Microsoft, Google, Thoughtworks, cost/latency/error numbers)

Anthropic, OpenAI, Microsoft and Google each publish a first-order rule to try the simplest, non-agentic
solution before reaching for an agent, phrased slightly differently:
- Anthropic: "find the simplest solution possible, and only increas[e] complexity when needed... this
  might mean not building agentic systems at all"; names latency/cost tradeoff and "compounding errors" as
  the price of agentic complexity. [DOC S1920]
- OpenAI: an agent is justified only by complex judgement-based decisions, unmaintainable rulesets, or
  heavy unstructured-data reliance; otherwise "a deterministic solution may suffice." A single-turn LLM
  call, a simple chatbot or a sentiment classifier is explicitly *not* an agent by OpenAI's own definition.
  [DOC S1924]
- Microsoft (Azure Architecture Center): first question is "does the problem need natural language
  understanding or dynamic generation? If no — it's a deterministic system and you should stop"; recommends
  starting with deterministic orchestration and escalating only when predetermined logic is insufficient,
  with agents as "bounded leaf workers" under a deterministic workflow spine. [DOC S1925]
- Google (Cloud Architecture Center / "Agents Companion" whitepaper, content via search summary — see
  `gaps.md`): summarization, translation and classification "often" don't need an agentic workflow; a
  deterministic-and-stable task, or one where speed/reliability outweighs flexibility, is named as a
  non-fit. [DOC S2160, S2161]
- Thoughtworks Technology Radar Vol 34 (2026-04): places "Agent Skills" in Trial as a way to modularize
  context narrowly, and separately treats "permission-hungry agents" as a security concern requiring
  zero-trust/sandboxing as non-negotiable, and names ignoring "agent durability" as an antipattern that
  breaks agent workflows in production — both read as arguments for narrow, bounded agent scope rather
  than routing a whole task through one. [DOC S2164, S2165]

No vendor page fetched in this session publishes a single cross-product cost/latency/error benchmark for
"agent vs. deterministic tool." The numeric figures found are independent (COMMUNITY) cost/latency
write-ups: cost scaling roughly linearly with token volume ($1.50/day at 3,000 tokens/run × 50,000
runs/day vs. $15/day at 30,000 tokens/run) [COMMUNITY S2173], and a ~21x per-model latency spread on one
measured agentic task (613 ms–12,874 ms) [COMMUNITY S2174]. Anthropic's own multi-agent token multipliers
(~4x agent, ~15x multi-agent vs. a single chat turn) are reused from topic 4 (`agents/
subagents-vs-deterministic-tools.md`, S1921) rather than re-derived here. No official "post-mortem" naming
a specific over-routed-agent incident was found; the closest is a Microsoft blog post titled "Stop Letting
Agents Run the Workflow" whose body could not be retrieved this session (`gaps.md`). [UNK]

_Agent: agents-overuse_

## QG38. A catalogue of typical over-routed tasks with their deterministic replacements

See `agents/agent-overuse-patterns.csv` (26 rows: `task_shape,routed_to_agent,deterministic_tool,
signal_agent_not_needed,sources`) and the Facts/Reference sections of `agents/
agent-overuse-patterns.md`. Categories covered, each with an official or reused doc source for the named
deterministic tool: JSON/CSV/log parsing (`jq` 1.8 [DOC S2166]), regex/pattern entity extraction (Presidio
`PatternRecognizer` [DOC S825, reused]), schema-keyed field masking, date/timezone arithmetic, JSON Schema
validation, lint/format, code navigation (LSP 3.18 [DOC S2171]), dependency updates (Renovate [DOC S2167],
Dependabot [DOC S2168]), release notes/version bumps (conventional-commits v1.0.0 [DOC S2169],
semantic-release [DOC S2170]), CI failure triage by signature, ticket routing by keyword, fixed UI-string
translation via catalogue, config drift detection (`dsc config test` [DOC S150, S154, reused],
ConfigMgr baseline compliance), structured-store querying (CMPivot [DOC S315-317, reused], SQL/WQL),
recurring report generation (Power BI scheduled refresh [DOC S900, reused]), scheduling/retry, simple
chatbot/FAQ, fixed classification, sort/filter/aggregate (reused from topic 4, S1936), fixed multi-step
tool sequences (reused from topic 4, S1935), and two rows for a task-picker/post-landing-verifier script
pair (cross-referenced to topic 4's QG16, not re-derived).

_Agent: agents-overuse_

## QG39. Signals and measures that a task is over-routed

Four signals recur across the fetched sources: (1) **output fully determined by input** — matches
OpenAI's own exclusion of single-turn calls/classifiers from "agent" [DOC S1924]; (2) **same answer
recurs across runs** — the same consolidation signal topic 4 already documents for tool-call sequences,
applied one level up to the whole task [DOC S1935, reused]; (3) **a spec or grammar already exists** —
JSON, DSC documents, conventional commits and Presidio patterns are all named, published grammars, so a
parser suffices over an LLM [DER]; (4) **errors unacceptable / audit needs exact reproduction** — a
deterministic tool's output is reproducible by construction, while a model can silently vary run to run
(illustrated, not measured precisely, by the "95%/5%" framing) [COMMUNITY S2174]; and (5) **volume/latency**
— cost and latency both scale unfavourably for an LLM call at high volume or tight latency budgets per the
two published community figures above. No vendor page fetched here names a specific OTel query for
finding over-routed candidates; topic 4 already documents the concrete Claude Code OTel fields
(`claude_code.tool_result.duration_ms`, `tool_input_size_bytes`/`tool_result_size_bytes`) that would
surface a stable, low-variance tool-call sequence as the practical detection method, reused here by
reference rather than re-fetched. [DER]

_Agent: agents-overuse_

## QG40. Deterministic-tool patterns for reads, drift detection and task-eligibility gating (general implications)

- A read operation that only fetches a stored record, an object-store GET, or a normalized-log/catalog
  read is already a deterministic surface and needs no model in the loop.
- A three-way diff ("declared (source of truth) vs observed vs agent logs") is a deterministic drift-detection
  pattern, not a task for a model.
- Enforcing a confirmation gate and an agent-facing device/action-count limit in code rather than in a
  prompt keeps those guarantees outside the model's own judgment.
- Fixing a discovery tool's output to a small, closed vocabulary (a literal string, or a non-zero exit
  with a reason code for "unknown") is a deterministic-output pattern that supports a simple downstream
  rule ("equals compliant").
- A stdlib-only script that resolves task eligibility to a fixed verdict set, and treats an unparseable
  input as ineligible rather than guessed at, is a general instance of "unknown is never eligible" applied
  to task selection.
- A script that determines "done" from source-control ancestry, ticks, trailers and a clean working tree —
  rather than trusting a transcript's own claim of success — is a general instance of "a claimed outcome is
  not evidence; a checked one is."

_Agent: agents-overuse_

## R1. Reuse candidates

- **Highest leverage: `pydantic-settings` as a `dependency` for a project's config-file/env-var/flags
  resolution.** It already implements a typical layered-precedence order and gives unknown-key refusal via
  `extra="forbid"`; if `pydantic` is already a pinned dependency, this is close to a drop-in that
  shrinks part of a settings-resolution custom code path. [S1022]
- **`cryptography`'s `Fernet.decrypt(token, ttl=seconds)` as a `dependency` for a short-TTL
  pseudonymization vault's reveal check.** Confirmed dual Apache-2.0/BSD-3-Clause by direct LICENSE
  fetch; implements a TTL-based reveal-refusal behaviour with no custom scheduler. [S1003,S1103]
- **LLM Guard's MIT-licensed `Vault` class shape as a `logic` candidate** for the mapping-object half
  of such a vault (placeholder<->value), with Presidio as the detector. [S1006]
- **Everything else surveyed (Vault transit, git-crypt, GLPI, Snipe-IT, NetBox, Fleet, Rundeck,
  StackStorm, Teleport, AWX, OTel Collector, Fluent Bit, Puppet, InSpec, Microsoft365DSC,
  microsoft/mcp catalog, dynaconf, python-fpe) is `no` or `pattern`-only** — either wrong licence
  (BUSL-1.1, GPL-3.0, AGPL-3.0 — now confirmed by direct LICENSE fetch rather than "NOASSERTION" for
  Vault, InSpec, Fleet, AWX), wrong domain, an always-on service a no-gateway/no-service design
  forbids running, or a concept simple enough to cover directly without a dependency. See
  `reuse/matrix.csv` for the row-by-row verdicts.
- **sops/age do not cover a model-boundary vault requirement** (per-conversation, short TTL,
  audited reveal): neither has a native TTL or a per-reveal audit event; both leave that to the
  caller. They fit long-lived, encrypted-at-rest, git-committed site secrets, not
  a short-TTL model-boundary vault. [S1000,S1001]

_Agent: reuse_

