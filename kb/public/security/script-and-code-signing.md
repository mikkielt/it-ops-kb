---
topic: security/script-and-code-signing
priority: P1
applies_to: "PowerShell 5.1/7.5 under ConfigMgr AllSigned; DSC v3.3.0/3.4.0-preview.1; WDAC/App Control"
retrieved_utc: 2026-09-27
sources: [S1513, S1514, S1515, S-utrhfg57, S1517, S1518, S1519, S-5kvx24wm, S-i4uarhme, S-zokdk7aw, S-fywaejcb, S118, S119]
status: complete
---

# Script and code signing (extends windows/execution-policy-signing, mecm/run-scripts)

## Summary
This extends `windows/execution-policy-signing.md` and `mecm/run-scripts.md`, which already cover the
ConfigMgr *PowerShell execution policy* client setting, `Set-AuthenticodeSignature`, and the CMPivot
signing certificate. New here: what a certificate must be to work at all under `AllSigned`, why
timestamping matters, whether DSC v3 has its own manifest-signing mechanism (it does not; signing
is an open request in the DSC repository), and how WDAC/App Control for Business treats PowerShell and `dsc.exe`.

## Facts
- A code-signing certificate must have **code-signing authority** (the Code Signing EKU); `Set-AuthenticodeSignature`
  fails if the certificate is not valid or does not have code-signing authority. [DOC S1515]
- `-TimestampServer` on `Set-AuthenticodeSignature` adds a timestamp from a trusted timestamp server, so users
  and programs can verify that the certificate was valid at signing time; this prevents the script from failing
  **when the signing certificate expires**. [DOC S1515]
- Microsoft's Authenticode guidance: without a time stamp the signature becomes invalid when the signing
  certificate expires, and Windows treats the file as unsigned; always time-stamp (RFC 3161, `/tr` with
  `/td SHA256`, SHA-256 digests). [DOC S-5kvx24wm]
- So under `AllSigned` a script whose untimestamped signature has expired is refused like an unsigned
  script: `AllSigned` needs a valid signature, and an expired untimestamped one no longer is. [DER S-5kvx24wm,
  S1515: Authenticode validity rule applied to the AllSigned requirement]
- Implication for any team signing its own PowerShell content (CI scripts, Run Scripts payloads): the
  signature needs a timestamp to survive the certificate's renewal cycle without re-signing every script.
  [DER S1515: renewal-cycle implication]
- `about_Signing` documents the general Windows PowerShell signing model: the signing certificate must be
  issued by a CA the computer trusts, self-signed certificates must be installed in the computer's Trusted
  Root Certificates store, and self-signed certificates are for testing only; CA-issued code-signing
  certificates are the path for scripts shared with other computers, because those computers already trust
  the CA. [DOC S-utrhfg57]
- DSC v3 has no manifest-signing or checksum-pinning mechanism yet: signing resource manifests (issue #327,
  opened 2024-02-24 by the DSC maintainer, asking that a manifest carry a hash or signature thumbprint of its
  executable) and signing configurations (#210, opened 2023-09-27) are both **open enhancement requests** on
  2026-09-27. [DOC S-zokdk7aw, S-fywaejcb]
- Neither the manifest schema (no signature field) nor the 3.3.0 and 3.4.0-preview.1 release notes (no
  signing item, read 2026-09-27) add one, so integrity has to come from how the files are delivered.
  [DER S1517, S118, S119, S-zokdk7aw: schema and release notes read with the open issues]
- The DSC v3 command-based resource manifest schema defines each operation (get, set, test, export and so on)
  as an `executable` command that DSC calls, and has no signing requirement or signature field for those
  executables. [DOC S1517]
- The DSC 3.0.0 general-availability announcement describes resources that can be written in any language, each with a manifest that defines its properties as a JSON schema and how DSC invokes it, and says DSC can use existing PowerShell 7 and Windows PowerShell DSC resources; it mentions no signing of resources or manifests. [DOC S1518]
- When a system-wide App Control for Business (WDAC) or AppLocker policy is enforced, PowerShell enters
  System Lockdown mode and the policy determines each runspace's language mode; **ConstrainedLanguage mode**
  limits the cmdlets and .NET types a session may use. [DOC S1513]
- So a `dsc.exe`-invoking wrapper script that the policy does not trust, and that relies on those types, can
  break under WDAC even if `AllSigned`/ConfigMgr's own execution policy is satisfied. [DER S1513: language
  mode set by the application control policy, not by execution policy]
- Microsoft's script-enforcement page: script enforcement is on in every App Control policy unless option
  **11 Disabled:Script Enforcement** is set (unsupported on Server 2016 and Windows 10 1607 LTSB); policies must
  allow every `.ps1`, `.psm1` and `.psd1` (and dependent modules) for Full Language, module functions must be
  exported by name, disallowed scripts still run in Constrained Language Mode, and signed scripts are
  validated with WinVerifyTrust, so the signing root must be in the device's trusted root store **and**
  allowed by the policy. [DOC S-i4uarhme]
- App Control does not control scripts run by an unenlightened script host (many third-party Java or Python
  engines): allowing such a host allows every script it runs; cmd.exe batch files are not controlled either,
  though what they launch is. [DOC S-i4uarhme]
- For DSC this means `dsc.exe` and each command-based resource executable are ordinary executables under the
  policy's file rules, configuration documents are data they read, not scripts, and only PowerShell-based
  resources and adapters meet script enforcement through PowerShell. No Microsoft page discusses `dsc.exe`
  under App Control directly. [DER S-i4uarhme, S1517: executables per manifest, script enforcement per host]
- Worked policy-authoring detail: the base policy needs `0 Enabled:UMCI` and must not carry
  `11 Disabled:Script Enforcement`; every `.psm1`/`.psd1` of a module meant to run must be signed, the
  signing certificate trusted, and its root added as a User-mode Signer rule, preferably in a supplemental
  policy; no hash-rule workaround is described. [COMMUNITY S1519]
- Applying WDAC CLM to a `dsc.exe`-based pipeline is a **separate control from ConfigMgr's PowerShell
  execution-policy setting**: `AllSigned` governs whether a `.ps1` runs at all; WDAC/CLM governs what a
  running (even signed) script is allowed to *do*. Both would need to independently trust the same
  publisher/certificate for a signed CI or Run Scripts payload to run in Full Language Mode under WDAC.
  [DER S1513,S1514,S1519: composing execution-policy scope with CLM scope]

## Reference
| Control | Governs | Trust anchor | Relevance |
|---|---|---|---|
| ConfigMgr *PowerShell execution policy* = AllSigned | whether a `.ps1`/`.psm1`/etc. runs at all | Trusted Publishers store (per `windows/execution-policy-signing.md`) | CI scripts, Run Scripts payloads |
| Authenticode timestamping (`-TimestampServer`) | signature validity after cert expiry | RFC 3161 timestamp authority | signing certificate renewal planning |
| WDAC / App Control CLM | what a running script may call (.NET, COM, etc.) | WDAC policy's publisher/hash rules | any wrapper script invoking `dsc.exe` on a WDAC-enforced device |
| DSC v3 manifest/config integrity | none yet (issues #327, #210 open) | n/a | no native signing to rely on — integrity must come from a configuration repository's MR + CI pipeline chain, not DSC itself |

## Examples
A CI-signed Run Scripts payload for `PL-LT-00123` must be (a) Authenticode-signed by a certificate with
the Code Signing EKU, timestamped, and issued by a CA in the device's Trusted Root/Trusted Publishers
stores, and (b) allowed to run in Full Language Mode by any WDAC policy enforced on that device — two
independent checks, not one.
