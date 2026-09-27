---
topic: powerbi/on-prem-gateway-sql
priority: P2
applies_to: "Power BI service + on-premises data gateway (standard mode), docs retrieved 2026-09-23"
retrieved_utc: 2026-09-26
sources: [S902, S903, S904, S905, S906, S907, S908, S909]
status: complete
---

# Power BI to on-premises SQL Server through the on-premises data gateway

## Summary
Power BI reaches an on-premises SQL Server only through an on-premises data gateway: a Windows service that makes outbound-only
connections to Azure Relay. Standard mode serves many users and services; personal mode is Power BI-only and single-user.
A gateway "connection" (data source) holds the SQL credentials (Windows or Basic); server and database names must match the
Power BI Desktop file exactly. Kerberos SSO can run DirectQuery (and refresh) as the Power BI user instead of the stored account.
Source pages are Microsoft Learn HTML (the repo `powerbi-docs-pr` is not public); facts are paraphrased.

## Facts
- A Power BI semantic model that imports from an on-premises SQL Server needs a data gateway in the Power BI service; Desktop connects directly. [DOC S902]
- Gateway types: on-premises data gateway in standard mode (centrally managed connections that many users share; the choice for shared sources, DirectQuery, live connections and high-availability clusters), personal mode (one Power BI user, not shareable; refreshes that user's own import semantic models), and the VNet data gateway (a Microsoft-managed service for sources inside a virtual network, no local install). [DOC S903]
- The gateway needs no inbound ports; it opens outbound connections and receives cloud requests as responses to polling over them. [DOC S904]
- Outbound ports: TCP 80, 443, 433, 5671, 5672 and 9350-9354; relay endpoints are `*.servicebus.windows.net` (5671-5672 AMQP; 443 and 9350-9354 relay). Full FQDN table in Reference. [DOC S905]
- Microsoft supports only the last six gateway releases; a new release ships monthly. [DOC S904]
- Limits: 1,000 data sources per gateway cluster; DirectQuery uncompressed response limit 16 MB; read requests 2 MB request / 8 MB compressed response. [DOC S904]
- Gateway caches data-source credentials client-side for hours; changed credentials can take about 5 hours to be used. [DOC S904]
- Minimum OS: Windows 10/11, Windows Server 2019/2022/2025, .NET Framework 4.8, 4 GB disk for performance logs; recommended 8 cores, 8 GB RAM, 64-bit Windows Server, SSD. [DOC S906]
- Not supported: Server Core, Windows containers, domain controllers; installer must be local admin; one standard and one personal gateway per computer at most. [DOC S906]
- For Windows authentication, the gateway machine must be in the same environment as the data sources; for a remote domain it must be domain-joined with a trust to the target domain. [DOC S906]
- A cluster (extra gateways on other computers, joined with the recovery key) removes the single point of failure; members should run the same version. [DOC S906]
- The recovery key is needed to recover, move or change the service account of a gateway; Microsoft cannot retrieve it. [DOC S906, S909]
- The gateway Windows service runs as `NT SERVICE\PBIEgwService` by default; this is not the account used to connect to data sources. [DOC S909]
- The service account can be changed to a domain account or a gMSA (documented steps: `Add-KdsRootKey`, `New-ADServiceAccount`, `Install-ADServiceAccount`, set logon in services.msc with trailing `$` and no password). [DOC S909]
- SQL Server connection authentication in the gateway: Windows or Basic (Basic = SQL authentication); queries run with these stored credentials unless Kerberos SSO is enabled. [DOC S907]
- The tutorial also lists OAuth2 as an authentication method choice for the SQL Server connection. [DOC S902]
- DirectQuery through the gateway supports SQL Server 2012 SP1 and later. [DOC S907]
- Server and database names in the gateway connection must match the Power BI Desktop values exactly (IP vs name, `SERVER\INSTANCE`); matching is case-sensitive. [DOC S907]
- To use a gateway connection for scheduled refresh or to publish DirectQuery models, the user must be listed under the connection's Users. [DOC S907]
- Privacy level on the connection applies to scheduled refresh only, not DirectQuery. [DOC S907]
- SSO options: Kerberos constrained delegation, SAML, Microsoft Entra SSO. SQL Server supports SSO via Kerberos. [DOC S908]
- With SSO on DirectQuery, queries run as the interacting Power BI user; with SSO on refresh, queries run as the semantic model owner. Refresh with SSO is only for Kerberos constrained delegation sources. [DOC S908]
- Microsoft Entra SSO through the gateway supports DirectQuery only; SSO is not supported for dataflows. [DOC S908]
- The gateway app is recommended over services.msc for changing the service account, yet the gMSA procedure uses services.msc. [DER S909] (both statements in the same page; see conflicts)

## Reference

| FQDN (public cloud) | Port | Purpose [S905] |
|---|---|---|
| `*.download.microsoft.com` | 443 | installer, version/region check |
| `*.powerbi.com`, `*.analysis.windows.net` | 443 | identify Power BI cluster |
| `*.login.windows.net`, `login.live.com`, `aadcdn.msauth.net`, `login.microsoftonline.com`, `*.microsoftonline-p.com` | 443 | Entra ID / OAuth2 sign-in |
| `*.servicebus.windows.net` | 5671-5672 | AMQP |
| `*.servicebus.windows.net` | 443, 9350-9354 | Azure Relay over TCP |
| `*.msftncsi.com` | 80 | internet connectivity test |
| `*.dc.services.visualstudio.com` | 443 | AppInsights telemetry |
| `ecs.office.com` | 443 | ECS config (Mashup) |
| `gatewayadminportal.azure.com` | 443 | gateway management |
| `*.cloudapp.azure.com` | 1443 | Azure Cloud Services / VMs |

## Examples
Gateway connection for a device-inventory store (example names): Connection type `SQL Server`, Server `PL-SRV-0042.corp.example.com`,
Database `driftdb`, Authentication `Windows` (a read-only account), gateway service logon `CORP\gmsa-pbigw$`.
The Power BI Desktop file must use exactly `PL-SRV-0042.corp.example.com` / `driftdb` too [S907].
