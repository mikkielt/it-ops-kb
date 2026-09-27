---
topic: graph/batching-and-query
priority: P1
applies_to: "Microsoft Graph v1.0 and beta"
retrieved_utc: 2026-09-26
sources: [S-l6y7tegw, S-6jt4shfp, S-onem7my3, S-v5rdr5la, S530, S-z2jpontw, S-mutvll3h, S-xtkia775, S529, S-lxgocwmb, S525, S-w5dgb6zq, S501]
status: complete
files: [graph/change-notification-lifetimes.csv]
---

# Graph JSON batching, paging, advanced queries and change notifications

## Summary
- `$batch`: up to 20 requests per JSON batch POST to `/v1.0/$batch` or `/beta/$batch`; `dependsOn` sequences requests; each individual request is throttled and evaluated separately (see `graph/throttling.md`).
- Paging: server-side (`@odata.nextLink`) is the default; client-side uses `$top`/`$skip`/`$skiptoken`; default/max page sizes vary per resource (`/users`: 100 default, 999 max, 500 when `signInActivity` is selected/filtered).
- Advanced queries on directory objects (`ConsistencyLevel: eventual` + `$count`) enable `$search`, `not`/`ne`/`endsWith` on `$filter`, and `/$count`; not needed for a plain `eq` filter.
- `$select`/`$expand` limits: `$expand` on directory-object relationships returns at most 20 items (100 for `registeredDevices`), no `@odata.nextLink`, no nested query parameters, and is not supported at all together with advanced queries.
- Change notifications (subscriptions): `device`, `managedDevice` and `windowsAutopilotDeviceIdentity` are absent from the supported-resources table, same gap pattern as delta query (`graph/delta-query.md`); `user`/`group`/other directory resources max lifetime 41,760 minutes (under 29 days); full table in `change-notification-lifetimes.csv`.

## Facts
### $batch
- A JSON batch request is a POST to `$batch` with a `requests` array; each item needs `id` (unique in the batch) and `method`; `url` is relative (e.g. `/users`, not the full origin); `headers` is required when `body` is present. [DOC S-l6y7tegw]
- "Microsoft Graph supports batching up to 20 requests into the JSON object." [DOC S-l6y7tegw]
- `dependsOn` is an array of `id` strings that orders execution; if a request a later one depends on fails, the dependent request fails with `424 Failed Dependency`; Microsoft recommends a batch be either fully sequential or fully parallel. [DOC S-l6y7tegw]
- Batching can work around URL-length limits: a long `$filter` clause becomes part of the JSON body instead of the URL. [DOC S-l6y7tegw]
- The batch response's top-level `status` is typically `200` (parseable) or `400` (malformed batch); a `200` on the envelope does not mean every individual request succeeded — each item in `responses` carries its own `status`. [DOC S-l6y7tegw]
- Requests in a batch are evaluated individually against throttling limits; a throttled item returns `429` inside a batch response that itself is `200`; the SDKs do not auto-retry a throttled item that was part of a batch, unlike a standalone throttled request. [DOC S529]
- The Microsoft Graph SDKs' `BatchRequestContent`/`BatchRequestStep`/`BatchResponseContent` classes build/parse batch payloads and automatically split a caller's requests into multiple batches of 20 when the limit is exceeded. [DOC S-lxgocwmb]
- Outlook and JSON batching: for a batch of unordered requests to the Outlook service, Graph passes up to four of them to Outlook at a time (whatever the target mailboxes), which keeps the batch within Outlook's four-concurrent-requests-per-app-and-mailbox limit; with `dependsOn`, Graph sends them one at a time in order. [DOC S525]

### Paging
- Server-side paging returns a default page (e.g. `GET /users` defaults to 100 results) and includes `@odata.nextLink` when more pages remain; the client must keep following `@odata.nextLink` until it is absent. [DOC S-6jt4shfp]
- Client-side paging uses `$top`, `$skip` or `$skiptoken`; support varies per API (`/users` supports `$top` but not `$skip`). [DOC S-6jt4shfp]
- Use the entire `@odata.nextLink` URL as given; do not extract and reuse only the `$skiptoken`/`$skip` value in a different request. [DOC S-6jt4shfp]
- `directoryRole` queries (the role objects and role members) do not support paging at all. [DOC S-6jt4shfp]
- When paging directory resources, custom request headers other than `Authorization`/`Content-Type` (e.g. `ConsistencyLevel`) are not automatically carried to subsequent page requests; the caller must set them again explicitly. [DOC S-6jt4shfp]
- With `$count=true` against directory resources, `@odata.count` is returned only on the first page. [DOC S-6jt4shfp, S-onem7my3]
- `DirectoryPageTokenNotFoundException`: never use a retry response's token for the next page; persist and reuse the token from the last successful (non-retry) response. [DOC S-6jt4shfp]
- `GET /users`: default page size 100, maximum page size 999; maximum drops to 500 when `$select=signInActivity` or `$filter=signInActivity` is used (a `$top` above 500 in that case returns pages of up to 500). [DOC S-xtkia775]
- `GET /users` by default returns only `businessPhones, displayName, givenName, id, jobTitle, mail, mobilePhone, officeLocation, preferredLanguage, surname, userPrincipalName`; other properties need `$select`. `$skip` isn't supported on `/users`. [DOC S-xtkia775]

### Advanced queries (directory objects)
- Advanced query capabilities add `not`, `ne` and `endsWith` on `$filter` for Microsoft Entra ID (directory) objects; they require the `ConsistencyLevel: eventual` header, and (except for `$search`) the `$count` query parameter. [DOC S530]
- A plain `$filter=accountEnabled eq false` works without the advanced-query header/parameter; only the added operators, `$search`, and `/$count` require them. [DOC S530]
- `$search` on directory-object collections works only as an advanced query; without `ConsistencyLevel: eventual` it returns an error, and `$search` does no substring "contains" matching: it tokenizes `displayName` and `description` values on spaces, numbers, casing changes (lowercase-to-uppercase) and symbols (other string properties behave like `startswith`). [DOC S530, S-w5dgb6zq]
- `GET /users/$count` (or `?$count=true`) without `ConsistencyLevel: eventual` errors on the `/$count` segment or is silently ignored as a query string parameter. [DOC S530]
- `in` filter expressions default to a 15-expression limit, or a 2,048-character URL length limit when using advanced queries; `eq` on `displayName`-like properties is limited to a 120-character match value by default, or the 2,048-character URL length limit under advanced queries. [DOC S-onem7my3]
- `$filter` on `/attachments` is ignored if present; cross-workload `$filter`/`$search` isn't supported; `$search`/`$count` aren't available in Azure AD B2C tenants. [DOC S-onem7my3]

### $select / $expand limits
- `$select` is required to get properties outside the default subset on `directoryObject`-derived resources (`user`, `group`) in v1.0. [DOC S-v5rdr5la]
- `$expand` on a directory-object relationship returns a maximum of 20 objects, except `/users?$expand=registeredDevices`, which returns up to 100; there is no `@odata.nextLink` for the expanded set, no more than one level of expand, and no nested `$filter`/`$select` inside the `$expand`. [DOC S-onem7my3, S-v5rdr5la]
- `$expand` is not supported at all together with advanced queries. [DOC S-v5rdr5la]
- An unsupported `$expand` (e.g. `user/photo`) returns an `ExpandNotSupported` error; other unsupported query parameters or combinations can fail silently, so the response payload must still be checked. [DOC S-v5rdr5la]

### Change notifications (subscriptions)
- The change-notifications supported-resources table lists `driveItem`, `group`, `list`, Outlook `message`/`event`/`contact`, `printer`, `printTaskDefinition`, security `alert`, `todoTask`, `user`, and several Teams/Copilot resources; it lists no `device`, `managedDevice` or `windowsAutopilotDeviceIdentity` resource path. [DOC S-z2jpontw]
- Therefore Entra devices and Intune-managed/Autopilot devices have no documented change-notification subscription, the same gap already recorded for delta query. [DER S-z2jpontw: resource absent from the supported table; see graph/delta-query.md]
- `user`/`group`/other directory resources: maximum subscription lifetime 41,760 minutes (under 29 days); `user` and `group` subscription quotas: 50,000 per app across all tenants, 1,000 per tenant across all apps, 100 per app+tenant combination. [DOC S-z2jpontw]
- Any `expirationDateTime` under 45 minutes from the request time is automatically raised to 45 minutes after the request time. [DOC S-mutvll3h]
- `changeType` for `user`/`group` supports `updated` and `deleted`; `updated` also fires on creation and on soft delete, `deleted` fires only on permanent deletion. [DOC S-mutvll3h]
- `lifecycleNotificationUrl` is required for Teams resources when `expirationDateTime` is more than 1 hour from now, and optional otherwise. [DOC S-mutvll3h]
- `notificationUrl` and `lifecycleNotificationUrl` must use HTTPS; `clientState` (max 128 characters in v1.0, 255 in the beta model) lets the receiver verify the notification came from the subscribed service. [DOC S-mutvll3h, S501]
- Rich notifications (`includeResourceData: true`) require `encryptionCertificate` (base64 certificate whose public key encrypts the resource data); `encryptionCertificateId` is an optional app-chosen identifier for the decryption certificate. [DOC S-mutvll3h]
See `change-notification-lifetimes.csv` for the full per-resource lifetime and quota table (data only, no new tag needed).

## Reference
| Feature | Limit | Source |
|---|---|---|
| `$batch` requests per call | 20 | S-l6y7tegw |
| `$filter ... in (...)` expressions (default) | 15 | S-onem7my3 |
| `$filter ... in (...)` / advanced query URL length | 2,048 chars | S-onem7my3 |
| `$filter=prop eq 'value'` match length (default) | 120 chars | S-onem7my3 |
| `$expand` on directory-object relationship | 20 objects (100 for `registeredDevices`) | S-onem7my3, S-v5rdr5la |
| `GET /users` page size | default 100, max 999 (500 with `signInActivity`) | S-xtkia775 |
| Subscription `expirationDateTime` floor | 45 min from request | S-mutvll3h |
| `user`/`group` subscription max lifetime | 41,760 min (~29 days) | S-z2jpontw |

Related articles: `graph/throttling.md` (per-request throttling inside a batch, 429/Retry-After); `graph/delta-query.md` (same undocumented-support gap for `device`/`managedDevice`/`windowsAutopilotDeviceIdentity`, for delta instead of change notifications); `graph/csdl-device.md` (`device` properties and which support `$filter`/`$search`); `graph/powershell-sdk.md` (PowerShell SDK equivalents `-Top`, `-Property`, `-Expand`, `-ConsistencyLevel`, `-CountVariable`).

## Examples
- SNIPPET: JSON batch request with `dependsOn` sequencing a dependent call; context: Graph v1.0, `POST /$batch`, up to 20 requests per batch; checked: no [DOC S-l6y7tegw]
```json
POST https://graph.microsoft.com/v1.0/$batch
{
  "requests": [
    { "id": "1", "method": "GET", "url": "/devices?$select=id,displayName&$filter=deviceId eq '00000000-0000-0000-0000-000000000000'" },
    { "id": "2", "method": "GET", "url": "/users/jan.kowalski@corp.example.com", "dependsOn": ["1"] }
  ]
}
```
- SNIPPET: advanced query with `$count=true` over directory objects; context: Graph v1.0, `ConsistencyLevel: eventual` header required for `$count`/`$search`/added filter operators; checked: no [DOC S530]
```http
GET https://graph.microsoft.com/v1.0/devices?$filter=approximateLastSignInDateTime le 2026-01-01T00:00:00Z&$count=true
ConsistencyLevel: eventual
```
- SNIPPET: create a `user` change-notification subscription near the maximum lifetime; context: Graph v1.0, `notificationUrl` must be HTTPS, `clientState` max 128 chars in v1.0, max lifetime 41,760 minutes; checked: no [DOC S-z2jpontw, S-mutvll3h]
```json
POST https://graph.microsoft.com/v1.0/subscriptions
{
  "changeType": "updated",
  "notificationUrl": "https://sub.corp.example.com/notify",
  "resource": "/users",
  "expirationDateTime": "2026-10-25T00:00:00Z",
  "clientState": "PL-SRV-0042"
}
```

