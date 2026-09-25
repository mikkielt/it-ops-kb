---
topic: security/script-and-code-signing
priority: P1
applies_to: "PowerShell 5.1/7.5 under ConfigMgr AllSigned; DSC v3.3.0/3.4.0-preview.1; WDAC/App Control"
retrieved_utc: 2026-09-24
sources: [S1513, S1514, S1515, S1516, S1517, S1518, S1519]
status: partial
---

# Script and code signing (extends windows/execution-policy-signing, mecm/run-scripts)

## Summary
This extends `kb/windows/execution-policy-signing.md` and `kb/mecm/run-scripts.md`, which already cover the
ConfigMgr *PowerShell execution policy* client setting, `Set-AuthenticodeSignature`, and the CMPivot
signing certificate. New here: what a certificate must be to work at all under `AllSigned`, why
timestamping matters, whether DSC v3 has its own manifest-signing mechanism (it does not, as far as
official docs show), and how WDAC/App Control for Business treats PowerShell and `dsc.exe`.

## Facts
- A code-signing certificate must carry the **Code Signing Enhanced Key Usage (EKU)**; `Set-AuthenticodeSignature`
  fails if the certificate is not valid or does not have code-signing authority. [DOC S1513]
- `-TimestampServer` on `Set-AuthenticodeSignature` timestamps the signature with a trusted third-party
  timestamp server; this is what lets the signature stay valid **after the signing certificate itself
  expires**. Without a timestamp, a script's signature becomes invalid once the certificate expires, and
  under `AllSigned` an expired signature fails the same way an unsigned script does. [DOC S1513]
  Implication for any team signing its own PowerShell content (CI scripts, Run Scripts payloads): the
  signing certificate needs a timestamp to survive its own renewal cycle without re-signing every script.
  [DER S1513: renewal-cycle implication]
- `about_Signing` documents the general Windows PowerShell signing model: self-signed certificates must be
  installed in the local computer's Trusted Root store to be honored, and public/enterprise CA-issued
  code-signing certificates are the normal path for production use because they chain to a root already
  trusted enterprise-wide. [DOC S1516]
- No official DSC v3 documentation was found describing a manifest-signing, checksum-pinning or other
  supply-chain-integrity mechanism for `*.dsc.resource.json`/`*.dsc.manifests.json` files or for bundled
  configuration documents; the manifest schema reference documents structure and validation rules only,
  no signature field. [UNK S1515; 3 searches tried: "DSC v3 manifest signing", "dsc.exe code signing",
  "DSC v3 supply chain integrity" — none surfaced an official mechanism]
- The DSC v3 announcement describes DSC resources as executable programs invoked by `dsc.exe`, with no
  mention of a signing requirement for those executables distinct from normal Windows code-signing/AppLocker/WDAC
  controls on any executable. [DOC S1517]
- Under WDAC / App Control for Business, PowerShell enforces **Constrained Language Mode (CLM)** for
  scripts that are not allowed to run in Full Language Mode by the active WDAC policy — in practice,
  scripts not signed by a publisher the WDAC policy trusts. CLM blocks calls into .NET types, COM objects
  and other capabilities scripts need for anything beyond basic automation, so an unsigned `dsc.exe`-invoking
  wrapper script that relies on those APIs breaks under WDAC even if `AllSigned`/ConfigMgr's own execution
  policy is satisfied. [DOC S1513 (PowerShell security features, WDAC/CLM interaction); COMMUNITY S1519
  for worked policy-authoring detail: a WDAC supplemental policy scoped to specific script hashes is the
  documented workaround for vendor scripts that cannot be signed, keeping CLM enforced everywhere else]
- Applying WDAC CLM to a `dsc.exe`-based pipeline is a **separate control from ConfigMgr's PowerShell
  execution-policy setting**: `AllSigned` governs whether a `.ps1` runs at all; WDAC/CLM governs what a
  running (even signed) script is allowed to *do*. Both would need to independently trust the same
  publisher/certificate for a signed CI or Run Scripts payload to run in Full Language Mode under WDAC.
  [DER S1513,S1514,S1519: composing execution-policy scope with CLM scope]

## Reference
| Control | Governs | Trust anchor | Relevance |
|---|---|---|---|
| ConfigMgr *PowerShell execution policy* = AllSigned | whether a `.ps1`/`.psm1`/etc. runs at all | Trusted Publishers store (per `kb/windows/execution-policy-signing.md`) | CI scripts, Run Scripts payloads |
| Authenticode timestamping (`-TimestampServer`) | signature validity after cert expiry | RFC 3161 timestamp authority | signing certificate renewal planning |
| WDAC / App Control CLM | what a running script may call (.NET, COM, etc.) | WDAC policy's publisher/hash rules | any wrapper script invoking `dsc.exe` on a WDAC-enforced device |
| DSC v3 manifest/config integrity | none found | n/a | no native signing to rely on — integrity must come from a configuration repository's MR + CI pipeline chain, not DSC itself |

## Examples
A CI-signed Run Scripts payload for `PL-LT-00123` must be (a) Authenticode-signed by a certificate with
the Code Signing EKU, timestamped, and issued by a CA in the device's Trusted Root/Trusted Publishers
stores, and (b) allowed to run in Full Language Mode by any WDAC policy enforced on that device — two
independent checks, not one.
