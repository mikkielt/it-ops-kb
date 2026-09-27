---
topic: security/script-and-code-signing
priority: P1
applies_to: "PowerShell 5.1/7.5 under ConfigMgr AllSigned; DSC v3.3.0/3.4.0-preview.1; WDAC/App Control"
retrieved_utc: 2026-09-27
sources: [S1513, S1514, S1515, S-utrhfg57, S1517, S1518, S1519]
status: partial
---

# Script and code signing (extends windows/execution-policy-signing, mecm/run-scripts)

## Summary
This extends `windows/execution-policy-signing.md` and `mecm/run-scripts.md`, which already cover the
ConfigMgr *PowerShell execution policy* client setting, `Set-AuthenticodeSignature`, and the CMPivot
signing certificate. New here: what a certificate must be to work at all under `AllSigned`, why
timestamping matters, whether DSC v3 has its own manifest-signing mechanism (it does not, as far as
official docs show), and how WDAC/App Control for Business treats PowerShell and `dsc.exe`.

## Facts
- A code-signing certificate must have **code-signing authority** (the Code Signing EKU); `Set-AuthenticodeSignature`
  fails if the certificate is not valid or does not have code-signing authority. [DOC S1515]
- `-TimestampServer` on `Set-AuthenticodeSignature` adds a timestamp from a trusted timestamp server, so users
  and programs can verify that the certificate was valid at signing time; this prevents the script from failing
  **when the signing certificate expires**. [DOC S1515]
- That under `AllSigned` a script whose untimestamped signature has expired fails the same way an unsigned
  script does. [UNK: not in S1513 as re-read 2026-09-27]
- Implication for any team signing its own PowerShell content (CI scripts, Run Scripts payloads): the
  signature needs a timestamp to survive the certificate's renewal cycle without re-signing every script.
  [DER S1515: renewal-cycle implication]
- `about_Signing` documents the general Windows PowerShell signing model: the signing certificate must be
  issued by a CA the computer trusts, self-signed certificates must be installed in the computer's Trusted
  Root Certificates store, and self-signed certificates are for testing only; CA-issued code-signing
  certificates are the path for scripts shared with other computers, because those computers already trust
  the CA. [DOC S-utrhfg57]
- No official DSC v3 documentation was found describing a manifest-signing, checksum-pinning or other
  supply-chain-integrity mechanism for `*.dsc.resource.json`/`*.dsc.manifests.json` files or for bundled
  configuration documents; the manifest schema reference documents structure and validation rules only,
  no signature field. [UNK: no official mechanism found, the S1517 schema has no signature field; 3 searches tried: "DSC v3 manifest signing", "dsc.exe code signing",
  "DSC v3 supply chain integrity" — none surfaced an official mechanism]
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
| DSC v3 manifest/config integrity | none found | n/a | no native signing to rely on — integrity must come from a configuration repository's MR + CI pipeline chain, not DSC itself |

## Examples
A CI-signed Run Scripts payload for `PL-LT-00123` must be (a) Authenticode-signed by a certificate with
the Code Signing EKU, timestamped, and issued by a CA in the device's Trusted Root/Trusted Publishers
stores, and (b) allowed to run in Full Language Mode by any WDAC policy enforced on that device — two
independent checks, not one.
