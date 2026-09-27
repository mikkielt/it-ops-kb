---
topic: auth/key-management-options
priority: P1
applies_to: "Windows 11/Server 2025, SQL Server 2022/2025, mssql-python (main branch 2026-09), pyodbc + ODBC Driver 18, age/sops (pure-Python)"
retrieved_utc: 2026-09-27
sources: [S1340, S1341, S1342, S1343, S1349, S1350, S1351, S1000, S1001, S-53ajdzoj, S402, S-kqm5iv43, S-3acopzkn, S-sp6pux45, S-ax3gmu7j, S-duamtyj7, S-ftk5lzj7, S-wk6ahp72, S-zb4abl74]
status: complete
---

## Summary
Extends [[secret-vault-encryption]] (reuse/secret-vault-encryption.md) with options for
protecting a pseudonymization vault's AES-256-GCM key and HMAC key: DPAPI-NG group descriptors, CNG
KSP+TPM, SQL Always Encrypted, SQL symmetric keys/EKM, and age+sops. The load-bearing finding is that
Microsoft's own pure-Python driver (`mssql-python`, the natural fit for a pure-Python package) does **not** support
Always Encrypted and has no roadmap item for it; only `pyodbc` + ODBC Driver 18 does. DPAPI-NG group
descriptors have no documented Python binding on non-Windows and only a community (unofficial) one on
Windows.

## Facts
- **SQL Always Encrypted, driver support (QA12):** the Microsoft ODBC Driver for SQL Server (13.1+)
  supports Always Encrypted, enabled with the connection-string keyword `ColumnEncryption=Enabled`; the
  driver transparently encrypts parameters that target encrypted columns and decrypts result data. [DOC S1340]
- `pyodbc` hands the connection string to ODBC Driver 18, so a `pyodbc` client gets Always Encrypted
  through that keyword. [DER S1340: driver-level connection-string keyword]
- A column master key (CMK) can be a certificate in the Windows Certificate Store (*local machine* or
  *current user* location); the ODBC driver's built-in provider for it is `MSSQL_CERTIFICATE_STORE`,
  not available on macOS or Linux. [DOC S1341,S1340]
- A local key store and its key must be replicated to each computer running the application (and
  redeployed on rotation); a centralized key store such as Azure Key Vault avoids per-machine copies. [DOC S1341]
- For a workstation CLI with a certificate-store CMK, that means every client workstation that reads the
  encrypted columns holds a copy of the key. [DER S1341: local key store replicated per machine]
- Microsoft's own Python driver **`mssql-python`** (the driver Microsoft ships specifically for Python,
  a natural fit for a pure-Python package) lists no Always Encrypted / column-encryption item, done or
  planned, in its public roadmap as of the commit fetched. [DOC S1350] Its Learn overview page is the
  canonical feature reference and should be re-checked at each dependency bump. [DOC S1351]
- **Conclusion:** Always Encrypted is usable from Python today only via `pyodbc` + ODBC
  Driver 18, not via `mssql-python`. [DER S1340,S1350: ODBC driver supports it; the mssql-python roadmap lists no such item]
- **Design note (not a "pure Python" violation):** a "pure Python package, no Rust" policy is about
  a project's own source, not its dependency graph -- `pyodbc` is a C-extension *dependency*, the same
  category as `cryptography` or the ODBC driver itself, not code the project writes or vendors. So choosing
  `pyodbc` over `mssql-python` to get Always Encrypted does not itself trigger such a policy; the real
  trade-off is operational (a native ODBC driver + unixODBC/Microsoft ODBC Driver 18 install on every host
  that needs it) versus staying on Microsoft's newer, install-simpler `mssql-python`, which has no
  Always Encrypted support to trade in for. [DER S1340,S1350]
- **DPAPI-NG `SID=` group descriptor:** a rule string `SID=<group-or-principal-SID>` (keyword not
  case-sensitive) protects to an AD group or principal identity; the rule string (or a registered display
  name) is passed to `NCryptCreateProtectionDescriptor`. [DOC S1342, S1343]
- DPAPI-NG group keys come from the Group Key Distribution Protocol (MS-GKDI): the server on a domain
  controller evaluates the caller's security context against the protection descriptor's security
  descriptor and returns a seed key, only a public key, or an error, so only principals the descriptor
  admits get the key needed to decrypt. [DOC S-53ajdzoj]
- GKDI servers are Active Directory domain controllers at DC functional level `DS_BEHAVIOR_WIN2012` or
  higher. [DOC S-53ajdzoj]
- Domain controllers wait up to 10 hours after a KDS root key is created before using it, so replication
  can converge; `-EffectiveImmediately` makes it usable only on the target DC until replication, and
  deleting and re-creating the root key can leave the old key cached (restart the KDC on all DCs).
  [DOC S402] That page is written for gMSA; DPAPI-NG uses the same KDS root keys through MS-GKDI.
  [DER S402, S-53ajdzoj]
- Clients SHOULD cache group keys per domain and security descriptor and look in the cache before
  asking a DC, so a user removed from the group may still decrypt with a key already cached on that
  machine until the cache entry goes; Windows' cache lifetime is not published (lab check in `_gaps.md`),
  and behaviour after the group is deleted is not documented. [DER S-53ajdzoj: client cache rule]
- **Python access to DPAPI-NG (QA11):** no first-party (Microsoft) Python binding was found. A
  community package, `dpapi-ng` (jborean93, MIT), implements the MS-GKDI protocol in Python and is built
  to encrypt and decrypt DPAPI-NG blobs **on non-Windows hosts** (replicating `NCryptProtectSecret` /
  `NCryptUnprotectSecret`), either with an offline copy of the domain root key or with the supplied user's
  credentials over RPC to a DC; only the `SID` protection descriptor is supported. It is unofficial and not
  audited by Microsoft. [COMMUNITY S1349] Using it from a `client` instance
  (which does run on Windows) would still need to call into CNG (`NCryptProtectSecret`/
  `NCryptUnprotectSecret`) for the encrypt/decrypt calls themselves, which needs either `ctypes`/`cffi`
  bindings (not pure Python) or the community RPC-based library. [DER S1342,S1349]
- **age + sops (reuse):** confirmed again from [[secret-vault-encryption]]: neither has a native rotation
  hook tied to group membership; both are file-encryption tools, not a live per-request grant/revoke
  mechanism, so a membership change (e.g. removal from a role group) does not by itself revoke a
  previously-decrypted vault key -- revocation requires re-encrypting to a new recipient list and
  distributing it, exactly as for any static-recipient scheme. [DER S1000,S1001]
- The Microsoft Platform Crypto Provider key storage provider (`MS_PLATFORM_CRYPTO_PROVIDER`) keeps private
  keys in the TPM so they cannot be extracted, and is used through CNG (`NCryptOpenStorageProvider`). [DOC S-kqm5iv43]
- SQL Server symmetric keys: to open one the caller needs some permission on the key, must not be denied
  `VIEW DEFINITION`, and needs `CONTROL` on the certificate or asymmetric key that decrypts it; open keys are
  bound to the session, not the security context, and stay open until closed or the session ends. [DOC S-3acopzkn]
- `ALTER SYMMETRIC KEY` only adds or drops the encryption that protects the key (`ADD`/`DROP ENCRYPTION BY`);
  it has no regenerate option, so rotating key material means a new key and re-encrypting the data. [DOC S-sp6pux45] [DER S-sp6pux45: rotation path]
- age's README points to `rage`, a Rust implementation, and `pyrage` provides Python bindings for it: a
  community, Rust-backed binding, not pure Python. [DOC S-ax3gmu7j; COMMUNITY S-duamtyj7]
- MSAL Python accepts a pre-signed client assertion in `client_credential={"client_assertion": ...}`
  (added in 1.13.0) [DOC S-ftk5lzj7], and in 1.39.0 also a no-argument callable it calls only when it sends a
  token request [CODE S-wk6ahp72: msal/application.py#ClientApplication.__init__]; Entra's assertion is a JWT
  signed with the registered certificate, carrying an `x5t#S256` header, and any JWT library can build it.
  [DOC S-zb4abl74] So a CNG/TPM-backed signer can build the assertion while MSAL only carries it; that Entra
  accepts one signed by a non-exportable key end to end is a lab check (`_gaps.md`). [DER S-ftk5lzj7, S-zb4abl74]

## Reference
| Option | Who can decrypt | Effect of membership change | Rotation | Python path | Sources |
|---|---|---|---|---|---|
| DPAPI-NG `SID=` group descriptor | members of the AD group (GKDI access check on a DC at the 2012 functional level or higher) | a group key already cached on the client may still decrypt (clients SHOULD cache keys; lifetime unpublished) | re-encrypt to new descriptor | `ctypes`/`cffi` to CNG, or community `dpapi-ng` off-Windows | S1342, S1343, S1349, S-53ajdzoj (DER) |
| CNG KSP + TPM | the machine (non-exportable key in the Microsoft Platform Crypto Provider) | n/a (machine-bound, not group-bound) | re-provision key in TPM | `ctypes`/`cffi` to CNG (`NCryptOpenStorageProvider`); no pure-Python path documented | S-kqm5iv43 |
| SQL Always Encrypted (CMK in cert store) | holders of the CMK certificate's private key | revoking cert access revokes decrypt | re-encrypt CEK to new CMK | `pyodbc`+ODBC 18 only; not `mssql-python` | S1340, S1341, S1350 |
| SQL symmetric keys | principals with some permission on the key, not denied `VIEW DEFINITION`, plus `CONTROL` on the certificate or asymmetric key that decrypts it | `REVOKE` applies to the next `OPEN`; a key already open stays open for the session | no `REGENERATE` for symmetric keys (`ALTER SYMMETRIC KEY` only adds or drops encryption); rotate by creating a new key and re-encrypting the data | any SQL driver (T-SQL-level, no client crypto) | S-3acopzkn, S-sp6pux45 (EKM not researched) |
| age + sops | holders of the recipient's private key file | none automatic; must re-encrypt | manual re-encrypt to new recipients | both are Go tools; age points to `rage` (Rust) as a port, and `pyrage` is a community Python binding over it, so not pure Python | S1000, S1001, S-ax3gmu7j, S-duamtyj7 (COMMUNITY) |

## Examples
No fixture-specific configuration; mechanism-only facts, applicable uniformly to a pseudonymization vault key and
HMAC key regardless of tenant.
