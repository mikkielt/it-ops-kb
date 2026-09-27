---
topic: intune/mdmdiagnosticstool
priority: P1
applies_to: "Windows 10 1809+ / Windows 11, doc ms.date 2025-08-04"
retrieved_utc: 2026-09-26
sources: [S617, S618, S-6epv7qzl]
status: partial
---
# MdmDiagnosticsTool.exe

## Summary
Built-in Windows tool (`%windir%\system32\mdmdiagnosticstool.exe`) that collects MDM diagnostics into a zip or cab by
*area*. Documented areas seen in official pages: `DeviceEnrollment`, `DeviceProvisioning`, `Autopilot`, `TPM`.
No official page lists every accepted area.

## Facts
- Example: `mdmdiagnosticstool.exe -area "DeviceEnrollment;DeviceProvisioning;Autopilot" -zip "c:\users\public\documents\MDMDiagReport.zip"`. [DOC S617]
- Zip contents: DiagnosticLogCSP_Collector_Autopilot_* (Autopilot ETLs), DiagnosticLogCSP_Collector_DeviceProvisioning_* (provisioning ETLs), MDMDiagHtmlReport.html, MdmDiagLogMetadata.json, MDMDiagReport.xml, MdmDiagReport_RegistryDump.reg, MdmLogCollectorFootPrint.txt, *.evtx (main: devicemanagement-enterprise-diagnostics-provider admin). [DOC S617]
- Settings > Accounts > Access work or school > Info > Create report writes to `C:\Users\Public\Documents\MDMDiagnostics`. [DOC S617]
- `-area Autopilot;TPM -cab <path>` for self-deploying / pre-provisioning on physical devices; `-area DeviceProvisioning -cab <path>` for runtime provisioning on 1809+. [DOC S618]
- DiagnosticLog CSP can enable/export channels remotely, e.g. `./Vendor/MSFT/DiagnosticLog/EtwLog/Channels/Microsoft-Windows-DeviceManagement-Enterprise-Diagnostics-Provider%2FDebug/State`. [DOC S617]
- Intune Collect diagnostics runs `mdmdiagnosticstool.exe` and collects `%temp%\MDMDiagnostics\mdmlogs-<Date/Time>.cab`. [DOC S-6epv7qzl]
- Complete list of valid `-area` values: not documented. [UNK]

## Reference
| Area | Where documented |
|---|---|
| DeviceEnrollment | S617 |
| DeviceProvisioning | S617, S618 |
| Autopilot | S617, S618 |
| TPM | S618 |

## Examples
On `PL-LT-00123`: `mdmdiagnosticstool.exe -area "DeviceEnrollment;DeviceProvisioning;Autopilot" -zip "C:\Users\Public\Documents\PL-LT-00123-mdm.zip"`
