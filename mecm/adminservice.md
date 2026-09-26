---
topic: mecm/adminservice
priority: P0
applies_to: "ConfigMgr current branch 2603"
retrieved_utc: 2026-09-26
sources: [S-o6f7ibqo, S-sldz4d6b, S-igpzfey7, S-wkltnypi, S-tjt262ke, S-uispggqe, S-2fob2ctx, S-7jumyiid, S-nejxr76b, S-dfkr7mdn, S-l2gdpfl2, S-6m7klb4f, S-ebuvm65r, S313, S-mckld2pr, S-qhlzdpie, S-6l4nubjq, S-actyzzlw, S-ounncxk4, S-2mbquiz2, S350]
status: partial
files: [mecm/adminservice-routes.csv]
---

# AdminService (administration service)

## Summary
The AdminService is an OData v4 REST API hosted by every SMS Provider on HTTPS 443, with two routes: `wmi` (generic access to SMS Provider WMI classes) and `v1.0` (newer, versioned features such as `Device`, CMPivot and custom properties).
Callers are ConfigMgr administrative users, and ConfigMgr RBAC applies to every call. Since 2509 it rejects NTLM, so on-premises calls need Kerberos.
Internet access goes through a CMG with an Entra ID account. The docs give a generic URL prefix for this, not a per-route support list. Microsoft publishes no OpenAPI/Swagger document.
Route table: `mecm/adminservice-routes.csv`.

## Facts
- The AdminService is a REST API based on OData v4, provided by the SMS Provider over HTTPS. [DOC S-o6f7ibqo]
- There are two routes: `https://<SMSProviderFQDN>/AdminService/wmi/<ClassName>` (GET and POST, over 700 classes) and `https://<SMSProviderFQDN>/AdminService/v1.0/<ClassName>` (new ConfigMgr functionality). [DOC S-o6f7ibqo]
- Class names are case-sensitive. [DOC S-o6f7ibqo] Since version 2006 the `wmi` route is case-insensitive (`sms_site` works). [DOC S-2fob2ctx] These two statements disagree for 2006 and later (see conflicts).
- To call the AdminService, the account must be an administrative user in ConfigMgr. Access through a CMG also needs an account in Entra ID. [DOC S-o6f7ibqo]
- The AdminService keeps using ConfigMgr's built-in role-based authorization when it is exposed to the internet. [DOC S-uispggqe]
- From 2010, IIS is not required on the SMS Provider. The site creates and binds a self-signed certificate, and HTTPS port 443 must be open. [DOC S-sldz4d6b]
- A PKI server-authentication certificate can be bound manually (IIS Edit Bindings, or `netsh http add sslcert ipport=0.0.0.0:443 ...`), after unbinding the site's self-signed certificate. [DOC S-sldz4d6b]
- The AdminService ignores the Enhanced HTTP site setting and always uses the site certificate, unless a PKI certificate is already bound to 443. [DOC S-sldz4d6b,S-2fob2ctx]
- SMS Provider prerequisites: .NET 4.6.2 (4.8 recommended) from 2107. [DOC S-o6f7ibqo]
- Verification: installation is logged in `RESTPROVIDERSetup.log`, health in `SMS_REST_PROVIDER.log`, and requests in `adminservice.log` on the SMS Provider (default `C:\Program Files\Microsoft Configuration Manager\logs`). Test with `GET /adminservice/v1.0/$metadata`. [DOC S-sldz4d6b]
- Starting in 2509, the AdminService rejects NTLM authentication and `AdminService.log` records "Rejecting NTLM authentication." [DOC S-7jumyiid]
- The SMS Provider authentication level (Windows, certificate, or Windows Hello for Business) also applies to the AdminService. With the Windows Hello for Business level, the token must carry a WHfB MFA claim. [DOC S-6m7klb4f]
- Scale: up to 5,000 requests per second per SMS Provider instance, and 200 requests per client IP address. [DOC S-l2gdpfl2]
- Internet access: in the SMS Provider role properties, enable "Allow Configuration Manager cloud management gateway traffic for administration service". Then replace the provider FQDN with the CMG endpoint, e.g. `https://<cmg>/CCM_Proxy_MutualAuth/<id>/AdminService`. [DOC S-sldz4d6b]
- Internet-based client management (IBCM) cannot expose the AdminService. A CMG is required. [DOC S-uispggqe]
- Conditional Access is supported and is "easiest" with Azure App Proxy. [DOC S-uispggqe]
- 2207 added the Azure Services option "Administration Service Management". It creates a separate cloud application that restricts access to AdminService endpoints only, and allows MFA enforcement. It is only for CMG VMSS (not classic CMG). [DOC S-nejxr76b,S-dfkr7mdn]
- Microsoft's token sample (linked from the docs) acquires a delegated Entra user token with MSAL (`AcquireTokenInteractive`, scope `api://<tenant>/<serverApp>/.default`). It calls `https://Provider_FQDN/AdminService_TokenAuth/v1.0/Device` with `Authorization: Bearer <token>`. [DOC S313]
- The docs list no routes as supported or unsupported through a CMG or with token auth. The only guidance is "use the CMG endpoint instead of the SMS Provider FQDN". [DER S-sldz4d6b,S-igpzfey7: usage.md applies the note to all examples and names no exclusions]
- `v1.0` route: `Device`, `Device(<id>)`, `AdminService.RunCMPivot` (POST, body `{"InputQuery": ...}`), `AdminService.CMPivotResult(OperationId=...)`, `ResourceCollectionMembership`, `Events`, `AvailableApplications`, `BoundaryGroups`, `Set/Get/DeleteExtensionData`, and `NotificationSubscription`. [DOC S-igpzfey7,S-wkltnypi,S-2fob2ctx,S-mckld2pr]
- `wmi` route: GET on any class, `$filter` with `startswith`/`endswith` (1910+), and static WMI methods through POST `/wmi/<Class>.<Method>` with a JSON body (1910+). [DOC S-2fob2ctx]
- No documented `v1.0` route runs a Run Script. A community sample uses `v1.0/Device(<id>)/AdminService.RunScript` (search result only, not verified). [COMMUNITY S350]
- The AdminService does not publish an OpenAPI (Swagger) document. [DOC S-uispggqe]
- The AdminService must be set up and working for tenant attach. [DOC S-ounncxk4]
- A console on a machine behind a proxy fails to connect to the AdminService unless the proxy is disabled or bypassed in `Microsoft.ConfigurationManagement.exe.config`. [DOC S-o6f7ibqo]
- 2303+: unauthorized AdminService requests are aggregated for 24 hours and shown as status message ID 11618. [DOC S-tjt262ke]
- 2603 fixes CMPivot-through-AdminService 400 errors (KustoParser) and updates `System.Linq.Dynamic.Core` to 1.7.1 (CVE-2023-32571). [DOC S-ebuvm65r]
- Security updates: KB35360093 (elevation of privilege, AdminService and CMPivot, 2403/2409). KB38982839 (SMS Provider and AdminService; 2603, and 2509/2503 with rollup). [DOC S-6l4nubjq,S-actyzzlw]
- Any device that calls the AdminService uses HTTPS port 443. [DOC S-2mbquiz2]

## Reference
- Route table: `mecm/adminservice-routes.csv` (23 rows: route, verb, layer, body, minimum version, purpose, CMG documented, source).
- Logs: `adminservice.log`, `SMS_REST_PROVIDER.log`, `RESTPROVIDERSetup.log`. The logs cited for tenant attach are `CMGatewayNotification.log` and `AdminService.log`.

## Examples
```powershell
# Kerberos (engineer's own identity), on-prem
Invoke-RestMethod -Uri "https://PL-SRV-0042.corp.example.com/AdminService/v1.0/Device(16777219)" -UseDefaultCredentials
# CMPivot on one device
Invoke-RestMethod -Method Post -UseDefaultCredentials -ContentType 'application/json' `
  -Uri "https://PL-SRV-0042.corp.example.com/AdminService/v1.0/Device(16777219)/AdminService.RunCMPivot" `
  -Body '{"InputQuery":"OS | project Device, Version"}'
```
