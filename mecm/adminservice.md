---
topic: mecm/adminservice
priority: P0
applies_to: "ConfigMgr current branch 2603"
retrieved_utc: 2026-09-23
sources: [S300, S301, S302, S303, S304, S305, S306, S307, S308, S309, S310, S311, S312, S313, S314, S344, S345, S346, S347, S348, S350]
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
- The AdminService is a REST API based on OData v4, provided by the SMS Provider over HTTPS. [DOC S300]
- There are two routes: `https://<SMSProviderFQDN>/AdminService/wmi/<ClassName>` (GET and POST, over 700 classes) and `https://<SMSProviderFQDN>/AdminService/v1.0/<ClassName>` (new ConfigMgr functionality). [DOC S300]
- Class names are case-sensitive. [DOC S300] Since version 2006 the `wmi` route is case-insensitive (`sms_site` works). [DOC S306] These two statements disagree for 2006 and later (see conflicts).
- To call the AdminService, the account must be an administrative user in ConfigMgr. Access through a CMG also needs an account in Entra ID. [DOC S300]
- The AdminService keeps using ConfigMgr's built-in role-based authorization when it is exposed to the internet. [DOC S305]
- From 2010, IIS is not required on the SMS Provider. The site creates and binds a self-signed certificate, and HTTPS port 443 must be open. [DOC S301]
- A PKI server-authentication certificate can be bound manually (IIS Edit Bindings, or `netsh http add sslcert ipport=0.0.0.0:443 ...`), after unbinding the site's self-signed certificate. [DOC S301]
- The AdminService ignores the Enhanced HTTP site setting and always uses the site certificate, unless a PKI certificate is already bound to 443. [DOC S301,S306]
- SMS Provider prerequisites: .NET 4.6.2 (4.8 recommended) from 2107. [DOC S300]
- Verification: installation is logged in `RESTPROVIDERSetup.log`, health in `SMS_REST_PROVIDER.log`, and requests in `adminservice.log` on the SMS Provider (default `C:\Program Files\Microsoft Configuration Manager\logs`). Test with `GET /adminservice/v1.0/$metadata`. [DOC S301]
- Starting in 2509, the AdminService rejects NTLM authentication and `AdminService.log` records "Rejecting NTLM authentication." [DOC S307]
- The SMS Provider authentication level (Windows, certificate, or Windows Hello for Business) also applies to the AdminService. With the Windows Hello for Business level, the token must carry a WHfB MFA claim. [DOC S311]
- Scale: up to 5,000 requests per second per SMS Provider instance, and 200 requests per client IP address. [DOC S310]
- Internet access: in the SMS Provider role properties, enable "Allow Configuration Manager cloud management gateway traffic for administration service". Then replace the provider FQDN with the CMG endpoint, e.g. `https://<cmg>/CCM_Proxy_MutualAuth/<id>/AdminService`. [DOC S301]
- Internet-based client management (IBCM) cannot expose the AdminService. A CMG is required. [DOC S305]
- Conditional Access is supported and is "easiest" with Azure App Proxy. [DOC S305]
- 2207 added the Azure Services option "Administration Service Management". It creates a separate cloud application that restricts access to AdminService endpoints only, and allows MFA enforcement. It is only for CMG VMSS (not classic CMG). [DOC S308,S309]
- Microsoft's token sample (linked from the docs) acquires a delegated Entra user token with MSAL (`AcquireTokenInteractive`, scope `api://<tenant>/<serverApp>/.default`). It calls `https://Provider_FQDN/AdminService_TokenAuth/v1.0/Device` with `Authorization: Bearer <token>`. [DOC S313]
- The docs list no routes as supported or unsupported through a CMG or with token auth. The only guidance is "use the CMG endpoint instead of the SMS Provider FQDN". [DER S301,S302: usage.md applies the note to all examples and names no exclusions]
- `v1.0` route: `Device`, `Device(<id>)`, `AdminService.RunCMPivot` (POST, body `{"InputQuery": ...}`), `AdminService.CMPivotResult(OperationId=...)`, `ResourceCollectionMembership`, `Events`, `AvailableApplications`, `BoundaryGroups`, `Set/Get/DeleteExtensionData`, and `NotificationSubscription`. [DOC S302,S303,S306,S314]
- `wmi` route: GET on any class, `$filter` with `startswith`/`endswith` (1910+), and static WMI methods through POST `/wmi/<Class>.<Method>` with a JSON body (1910+). [DOC S306]
- No documented `v1.0` route runs a Run Script. A community sample uses `v1.0/Device(<id>)/AdminService.RunScript` (search result only, not verified). [COMMUNITY S350]
- The AdminService does not publish an OpenAPI (Swagger) document. [DOC S305]
- The AdminService must be set up and working for tenant attach. [DOC S347]
- A console on a machine behind a proxy fails to connect to the AdminService unless the proxy is disabled or bypassed in `Microsoft.ConfigurationManagement.exe.config`. [DOC S300]
- 2303+: unauthorized AdminService requests are aggregated for 24 hours and shown as status message ID 11618. [DOC S304]
- 2603 fixes CMPivot-through-AdminService 400 errors (KustoParser) and updates `System.Linq.Dynamic.Core` to 1.7.1 (CVE-2023-32571). [DOC S312]
- Security updates: KB35360093 (elevation of privilege, AdminService and CMPivot, 2403/2409). KB38982839 (SMS Provider and AdminService; 2603, and 2509/2503 with rollup). [DOC S345,S346]
- Any device that calls the AdminService uses HTTPS port 443. [DOC S348]

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
