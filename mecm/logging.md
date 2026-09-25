---
topic: mecm/logging
priority: P0
applies_to: "ConfigMgr current branch 2603 (memdocs 4b5429df)"
retrieved_utc: 2026-09-23
sources: [S214, S215, S225, S234, S221]
status: partial
---

## Summary
Logs are plain text in "CCM format", best read with CMTrace, OneTrace or Support Center. A `.log` rolls to `.lo_` at max
size (default 250,000 bytes). Client/MP logging is set under `HKLM\SOFTWARE\Microsoft\CCM\Logging\@Global` (LogLevel,
LogMaxHistory, LogMaxSize) and `...\Logging\DebugLogging`; site server under `HKLM\SOFTWARE\Microsoft\SMS\Tracing[\<Component>]`;
site roles under `HKLM\SOFTWARE\Microsoft\SMS\<Component>\Logging`. The CCM line format is not formally specified;
only examples are published.

## Facts
- Log files use `.log`/`.lo_`; when `.log` reaches max size it is copied to `.lo_` (overwritten on next roll); some components append a timestamp instead. [DOC S214]
- Client install properties for logging: CCMENABLELOGGING, CCMDEBUGLOGGING, CCMLOGLEVEL, CCMLOGMAXHISTORY, CCMLOGMAXSIZE. [DOC S214]
- After registry changes restart CcmExec (client) or SMS Executive (server). [DOC S214]
- Client/MP `@Global` REG_DWORD: LogLevel 0 Verbose / 1 Default / 2 Warnings and errors / 3 Errors only; LogMaxHistory >= 0 (default 1); LogMaxSize >= 10,000 bytes (default 250,000). [DOC S214]
- `HKLM\SOFTWARE\Microsoft\CCM\Logging\DebugLogging` REG_SZ `Enabled` = True/False. [DOC S214]
- Site server `HKLM\SOFTWARE\Microsoft\SMS\Tracing`: SqlEnabled (DWORD), ArchiveEnabled (DWORD), ArchivePath (SZ); per component `...\Tracing\<ComponentName>`: LoggingLevel, LogMaxHistory, MaxFileSize (default 250,000), DebugLogging. These don't apply to modern components such as SMS_MESSAGE_PROCESSING_ENGINE. [DOC S214]
- Site system role: `HKLM\SOFTWARE\Microsoft\SMS\<ComponentName>\Logging` (e.g. `...\SMS\DP\Logging`): LogLevel, LogMaxHistory, LogMaxSize. [DOC S214]
- Console AdminUI.log verbosity: `switchValue` in `Microsoft.ConfigurationManagement.exe.config`. [DOC S214]
- Console Client Diagnostics actions Enable/Disable verbose logging change global CCM log level and debug logging, not size or history. [DOC S221]
- Hardware inventory class Client Diagnostics (`CCM_ClientDiagnostics`, 2107+, off by default) collects Debug Logging Enabled, Logging Enabled, Log Level, History File Count, Max Log File Size. [DOC S214]
- SDK method `SMS_Client.SetGlobalLoggingConfiguration(LogLevel, LogMaxSize, LogMaxHistory, DebugLogging)` documents LogLevel 0 Verbose, 1 Normal, 2 No logging (conflicts with registry doc, see conflicts). [DOC S225]
- CMTrace reads CCM-format logs and plain ASCII/Unicode text; in CCM format each entry has an explicit type value marking error or warning; for other formats it matches "error"/"warn" text. [DOC S215]
- CMTrace installed at `C:\Windows\CCM\CMTrace.exe` (client), `C:\SMS_CCM\CMTrace.exe` (MP), `cd.latest\SMSSETUP\Tools`, boot images `X:\sms\bin\x64`. [DOC S215]
- CCM line shape from published examples: `<![LOG[text]LOG]!><time="HH:MM:SS.mmm+bias" date="MM-DD-YYYY" component="..." context="" type="1" thread="N" file="src.cpp:line">`. [DOC S234]
- The numeric meaning of `type` (1/2/3) and the sign/unit of the time bias are not officially specified. [UNK]

## Reference
| Key | Values | Default |
|---|---|---|
| CCM\Logging\@Global\LogLevel | 0-3 | 1 |
| CCM\Logging\@Global\LogMaxHistory | >=0 | 1 |
| CCM\Logging\@Global\LogMaxSize | >=10000 bytes | 250000 |
| CCM\Logging\DebugLogging\Enabled | True/False | (absent) |
| SMS\Tracing\<Comp>\MaxFileSize | >=10000 bytes | 250000 |

## Examples
Parse regex (derived from examples): `<!\[LOG\[(?P<msg>.*?)\]LOG\]!><time="(?P<time>[^"]+)" date="(?P<date>[^"]+)" component="(?P<comp>[^"]*)" context="[^"]*" type="(?P<type>\d)" thread="(?P<thread>\d+)" file="(?P<file>[^"]*)">` (messages may span lines).
