---
topic: mecm/client-notification
priority: P0
applies_to: "ConfigMgr current branch 2603"
retrieved_utc: 2026-09-23
sources: [S318, S326, S327, S328, S329, S330, S331, S332, S333, S334, S340, S352]
status: partial
files: [mecm/client-operation-types.csv]
---

# Client notification and SMS_ClientOperation

## Summary
Client notification actions (the "Client notification" menu) need **Notify Resource** on the collection. They run over the fast channel and are tracked as client operations (`SMS_ClientOperation`, `SMS_ClientOperationStatus`; Monitoring > Client Operations).
The SDK documents `InitiateClientOperation(Type, TargetCollectionID, RandomizationWindow, TargetResourceIDs[]) -> OperationID` but gives **no Type value table**. The only numeric Types in official docs are 135 (Run Script) and 145 (CMPivot), both from log samples. `InitiateClientOperationEx` is not in current Microsoft docs.
`Invoke-CMClientAction -ActionType` lists 26 enum names without numeric values. Tables: `mecm/client-operation-types.csv`.

## Facts
- Client notification actions: Download computer policy, Download user policy, Collect discovery data, Collect software inventory, Collect hardware inventory, Evaluate application deployments, Evaluate software update deployments, Switch to the next software update point, Evaluate device health attestation, Check Conditional Access compliance, Wake Up, Restart. [DOC S326]
- Client diagnostics actions: Enable verbose logging, Disable verbose logging, Collect Client Logs (compressed size limit 100 MB). [DOC S326]
- Endpoint Protection actions: Full Scan, Quick Scan, Download Definition. They need Enforce Security on the Collection. [DOC S326]
- Ribbon actions outside the menu: Install client (Modify Resource + Read), Run script (Run Script), Start CMPivot (Run CMPivot). [DOC S326]
- All actions under the Client notification menu need the Notify Resource permission on the Collection object (since 1810). [DOC S326,S340]
- The Restart notification shows a Software Center notification, and the restart occurs after 90 minutes by default (client setting Computer restart). [DOC S327]
- Operations are monitored in Monitoring > Client Operations. Some can be cancelled, and they can be deleted from view. [DOC S326]
- Once started, a collection-level task cannot be stopped from the console. [DOC S327]
- On the client, policy retrieval can be triggered with `Invoke-WmiMethod -Namespace root\ccm -Class sms_client -Name TriggerSchedule '{00000000-0000-0000-0000-000000000021}'`. This is a client-side schedule ID, not a server-side operation Type. [DOC S327]
- `SMS_ClientOperation` properties: Actions[], CollectionID, CreatedBy, DependentClientOperations[], Filter, FilterType, ID (key), IsActionsDependent, PrimaryActionTargetObjectID/Name/Type, PrimaryActionType, Priority, RequestedTime, SourceSite, State, TargetCollectionName, TargetResourceIDs[], TargetType, UniqueID. [DOC S328]
- `SMS_ClientOperation` methods: AllowThreat, CancelClientOperation(OperationID), DeleteClientOperation(OperationID), ExcludeScanPaths, IsClientOperationAllowed(Type, TargetCollectionID, TargetResourceIDs[]), IsClientOperationUpdateAllowed(OperationID), InitiateClientOperation, RestoreQuarantinedItem. [DOC S328,S331,S332,S333]
- `InitiateClientOperation`: in `Type` (UInt32), `TargetCollectionID` (String), `RandomizationWindow` (UInt32, optional) and `TargetResourceIDs` (UInt32[], optional). Out: `OperationID` (UInt32). The descriptions only repeat the parameter names. [DOC S329]
- `InitiateClientOperationEx` does not appear in the current MicrosoftDocs/memdocs SDK reference. Its parameters are not officially documented. [UNK]
- `PrimaryActionType` values 1–8 (Full Scan, Quick Scan, Download Definition, Evaluate Software Update, Exclude Scan Path, Override Default Action, Restore Quarantine Items, RequestPolicyNow) are documented on the class. [DOC S328] These are primary-action codes, not `InitiateClientOperation` Type values. [DER S328,S329: separate property, and the Type parameter has no table]
- `TargetType`: 0 current members of a collection, 1 specific clients in a collection, 2 members of a collection, 3 members matching criteria. [DOC S328]
- `State`: 0 Inactive, 1 Active, 2 Decommission. [DOC S328]
- `SMS_ClientOperationStatus` adds the counters CompletedClients, FailedClients, OfflineClients, UnknownClients, TotalClients, plus IsExpired and LastSummaryTime. Its `State` values are 0 Unknown, 1 Not Applicable, 2 Failed, 3 Succeeded. [DOC S330]
- Official docs show client operation Type 135 for Run Script (and CMPivot in 1902 and earlier) and Type 145 for CMPivot (1906+), in smsprov.log samples. [DOC S318]
- The Type values for machine policy, hardware inventory, application evaluation and software update evaluation are not officially documented. Community blogs publish values, but they were not verified here and are not repeated. [COMMUNITY S352]
- `Invoke-CMClientAction` targets `-Collection`, `-CollectionId`, `-CollectionName`, `-Device`, `-DeviceId` or `-DeviceName`. `-ActionType <ClientActionType>` accepts 26 names. `-NotificationType <ClientNotificationType>` accepts RequestMachinePolicyNow and RequestUsersPolicyNow. The alias is `Invoke-CMClientNotification`. [DOC S334]
- ClientActionType names include RequestScriptExecution and RequestCMPivotExecution. Their numeric values are not documented. [DOC S334]

## Reference
- `mecm/client-operation-types.csv`: every enum and value, with its status and source.

## Examples
```powershell
Invoke-CMClientAction -DeviceName 'PL-LT-00123' -ActionType ClientNotificationRequestMachinePolicyNow
Invoke-CMClientAction -DeviceName 'PL-LT-00123' -ActionType ClientNotificationRequestHWInvNow
```
