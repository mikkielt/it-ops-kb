---
topic: windows/execution-policy-signing
priority: P0
applies_to: "Windows PowerShell 5.1, PowerShell 7.5; ConfigMgr current branch client settings"
retrieved_utc: 2026-09-26
sources: [S420, S421, S422, S-pm6pjuef, S1483, S-f26o3j3w, S-2z2zfj3l, S-mmydokhp, S407]
status: complete
---

# PowerShell execution policy and script signing (as ConfigMgr uses them)

## Summary
- Execution policy is "not a security boundary". It is defence in depth, enforced only on Windows. Scopes in precedence order: MachinePolicy, UserPolicy (both Group Policy), Process, CurrentUser, LocalMachine.
- ConfigMgr client setting **PowerShell execution policy** (Computer agent): Bypass, Restricted or All Signed. The default is **All Signed**, and it applies to CI discovery scripts and script deployments.
- Unsigned scripts under All Signed fail with `0x87D00327` "Script is not signed" (DcmWmiProvider.log).
- Signing: Authenticode with a code-signing certificate that chains to a CA the computer trusts. Timestamping keeps the signature valid after the certificate expires.

## Facts
- The execution policy isn't a security boundary: users can type script contents at the prompt. [DOC S420]
- On non-Windows platforms the policy is Unrestricted and can't be changed. [DOC S420]
- Policies are AllSigned, Bypass, Default, RemoteSigned, Restricted, Undefined and Unrestricted. AllSigned requires all scripts and configuration files to be signed by a trusted publisher, including locally written ones. [DOC S420]
- If every scope is Undefined, the effective policy is Restricted on Windows clients and RemoteSigned on Windows Server. [DOC S420,S421]
- `Default` means Restricted on clients and RemoteSigned on servers (5.1 page). The 7.5 page says RemoteSigned for clients and servers (see conflicts). [DOC S421,S420]
- Precedence: Group Policy (MachinePolicy, then UserPolicy) overrides everything. Then Process (env `PSExecutionPolicyPreference`), CurrentUser, LocalMachine. [DOC S420]
- Storage: in 7.x, CurrentUser and LocalMachine are stored in `powershell.config.json`. In 5.1 they are in the registry: `HKCU:`/`HKLM:\Software\Microsoft\PowerShell\1\ShellIds\Microsoft.PowerShell`, value `ExecutionPolicy`. [DOC S420,S421]
- The Group Policy setting "Turn on Script Execution" maps: Allow all scripts → Unrestricted; Allow local scripts and remote signed scripts → RemoteSigned; Allow only signed scripts → AllSigned; Disabled → Restricted-equivalent. [DOC S420]
- `pwsh.exe -ExecutionPolicy <p>` sets the policy for that session and its child sessions. [DOC S420]
- The GitLab Runner starts job scripts with `-ExecutionPolicy Bypass`. [DOC S407]
- Signature checks cover `.ps1`, `.psm1`, `.psd1`, `.ps1xml`, `.cdxml` and `.xaml` (Windows only). [DOC S422]
- A signed script needs a signature from a trusted publisher. The code-signing certificate must come from a CA trusted on the computer. Self-signed certificates must be in Trusted Root. [DOC S422]
- `Set-AuthenticodeSignature` appends a signature block that starts and ends with `# SIG #`. [DOC S422]
- Before PowerShell 7.2, signed scripts had to be ASCII or UTF8NoBOM. 7.2 and later accept any encoding. [DOC S422]
- A signature stays valid until the certificate expires, or longer if a timestamp server confirms it was signed while the certificate was valid. [DOC S422]
- ConfigMgr **PowerShell execution policy** client setting: Bypass (unsigned scripts run), Restricted (uses the client's own PowerShell configuration), All Signed (only scripts signed by a trusted publisher, whatever the local configuration). The default is All Signed. It needs Windows PowerShell 2.0 or later. It applies to "detection in configuration items for compliance settings" and to scripts sent in a deployment. [DOC S-pm6pjuef]
- Failure signals: Monitoring error `0x87D00327` "Script is not signed"; reports show "Discovery Error", with `0x87D00327` or `0x87D00320` "The script host has not been installed yet"; `DcmWmiProvider.log` shows "Script is not signed (Error: 87D00327; Source: CCM)". [DOC S-pm6pjuef]
- Security guidance: don't set Bypass broadly. If Bypass is needed, use a custom client setting scoped to the computers that need unsigned scripts. [DOC S1483]
- WMI `SMS_ConfigMgrClientAgentConfig.PowerShellExecutionPolicy` (UInt32) documents only 0 = Bypass and 1 = Restricted. There is no value for All Signed (see conflicts). [DOC S-f26o3j3w]
- CMPivot (and the Edge installer) are signed with "Microsoft Code Signing PCA 2011". Under AllSigned, import that code-signing certificate into the machine **Trusted Publishers** store. [DOC S-2z2zfj3l]
- For a signed PowerShell CI script, load it with **Open**. Copy and paste into the CI editor breaks the signature. [DOC S-mmydokhp]

## Reference
| ConfigMgr setting value | Effect | WMI value (S-f26o3j3w) |
|---|---|---|
| Bypass | unsigned runs | 0 |
| Restricted | follows local PowerShell policy | 1 |
| All Signed (default) | trusted-publisher signature required | not documented |

- See also `windows/powershell-7.md`: PowerShell 7.x lifecycle (LTS/STS), side-by-side install with
  Windows PowerShell 5.1, and `-ExecutionPolicy` at install/session start. [DER: cross-link, no new fact]

## Examples
```powershell
Get-ExecutionPolicy -List
$cert = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert | Select-Object -First 1
Set-AuthenticodeSignature -FilePath .\Test-DriftCheck.ps1 -Certificate $cert -TimestampServer http://timestamp.corp.example.com
```
