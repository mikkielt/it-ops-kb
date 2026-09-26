---
topic: graph/delta-query
priority: P1
applies_to: "Microsoft Graph v1.0 and beta"
retrieved_utc: 2026-09-25
sources: [S500, S501, S502, S503, S510, S511]
status: complete
---

# Delta query support for device resources

## Summary
- `devices` (Entra): delta supported in v1.0 and beta (`GET /devices/delta`).
- `managedDevices` (Intune) and `windowsAutopilotDeviceIdentities`: no delta function in v1.0 or beta CSDL, and not in the delta supported-resources list.
- Directory delta tokens are valid for seven days; `410 Gone` means restart with a full sync.

## Facts
- The delta supported-resources table lists `device` with the `device: delta` function; it lists no Intune or Autopilot resource. [DOC S510]
- In both v1.0 and beta CSDL, the only `delta` function bound to a device-related collection is bound to `Collection(graph.device)`. [DOC S502,S503]
- The CSDL ChangeTracking annotation (`Supported=true`) targets `microsoft.graph.device`; none targets `managedDevice` or `windowsAutopilotDeviceIdentity`. [DOC S500,S501]
- Therefore `managedDevices` and `windowsAutopilotDeviceIdentities` have no documented delta query in v1.0 or beta. [DER S502,S503,S510: no bound function + not in supported list]
- `devices/delta` supports `$select` (id always returned) and only `$filter=id eq '{value}'` (optionally or-ed ids, limited by URL length). [DOC S511]
- Delta tokens for directory objects expire after seven days; expiry returns a 40X error such as `syncStateNotFound`. [DOC S510]
- A `410 Gone` with a `Location` header holding an empty `$deltatoken` means the client must restart with full synchronization. [DOC S510]
- Replays (the same change in later responses) are possible; changes can appear with replication delay. [DOC S510]

## Reference
| Resource | v1.0 delta | beta delta | Evidence |
|---|---|---|---|
| devices | yes | yes | S510, S502, S503, S511 |
| deviceManagement/managedDevices | no | no | S502, S503, S510 |
| deviceManagement/windowsAutopilotDeviceIdentities | no | no | S502, S503, S510 |

## Examples
- `GET https://graph.microsoft.com/v1.0/devices/delta?$select=deviceId,displayName,trustType,approximateLastSignInDateTime`

## Related
- `graph/batching-and-query.md`: change-notification subscriptions have the same undocumented-support gap for `device`, `managedDevice` and `windowsAutopilotDeviceIdentity`.
