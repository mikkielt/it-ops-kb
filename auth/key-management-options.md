---
topic: auth/key-management-options
priority: P1
applies_to: "Windows 11/Server 2025, SQL Server 2022/2025, mssql-python (main branch 2026-09), pyodbc + ODBC Driver 18, age/sops (pure-Python)"
retrieved_utc: 2026-09-24
sources: [S1340, S1341, S1342, S1343, S1344, S1349, S1350, S1351, S1000, S1001, S1003]
status: partial
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
- **SQL Always Encrypted, driver support (QA12):** `pyodbc` with ODBC Driver 18 for SQL Server supports
  Always Encrypted via the connection-string attribute `Column Encryption Setting=Enabled`; the driver
  transparently encrypts parameters bound to encrypted columns and decrypts result data. [DOC S1340]
- A column master key (CMK) can be stored in the Windows Certificate Store (`LocalMachine` or
  `CurrentUser`), with the key store provider name `MSSQL_CERTIFICATE_STORE`
  (`SqlColumnEncryptionCertificateStoreProvider`); a certificate-backed CMK in the local machine store
  must be replicated to every machine that needs to decrypt, which for a workstation CLI means every
  client workstation that reads pseudonymized-adjacent columns, unless a shared key store (Azure Key Vault, an
  HSM, or SQL Server EKM) is used instead. [DOC S1341]
- Microsoft's own Python driver **`mssql-python`** (the driver Microsoft ships specifically for Python,
  a natural fit for a pure-Python package) lists no Always Encrypted / column-encryption item, done or
  planned, in its public roadmap as of the commit fetched. [DOC S1350] Its Learn overview page is the
  canonical feature reference and should be re-checked at each dependency bump. [DOC S1351]
- **Conclusion:** Always Encrypted is usable from Python today only via `pyodbc` + ODBC
  Driver 18, not via `mssql-python`. [DOC S1340, S1350]
- **Design note (not a "pure Python" violation):** a "pure Python package, no Rust" policy is about
  a project's own source, not its dependency graph -- `pyodbc` is a C-extension *dependency*, the same
  category as `cryptography` or the ODBC driver itself, not code the project writes or vendors. So choosing
  `pyodbc` over `mssql-python` to get Always Encrypted does not itself trigger such a policy; the real
  trade-off is operational (a native ODBC driver + unixODBC/Microsoft ODBC Driver 18 install on every host
  that needs it) versus staying on Microsoft's newer, install-simpler `mssql-python`, which has no
  Always Encrypted support to trade in for. [DER S1340,S1350]
- **DPAPI-NG `SID=` group descriptor:** requires the syntax `SID=<group-or-principal-SID>`
  (case-insensitive keyword), created via `NCryptCreateProtectionDescriptor`, and only the SID principal
  or a member of the SID group can decrypt with `NCryptUnprotectSecret`. [DOC S1342, S1343] The reference
  pages fetched do not state the KDS root key propagation delay, DC version floor, or behaviour on
  membership loss / group deletion; those remain [UNK] pending a page that documents MS-GKDI's server
  requirements explicitly. [UNK]
- **Python access to DPAPI-NG (QA11):** no first-party (Microsoft) Python binding was found. A
  community package, `dpapi-ng` (jborean93), implements the MS-GKDI client protocol in pure Python and
  is explicitly built to decrypt DPAPI-NG blobs **from non-Windows platforms** by talking GKDI over RPC to
  a DC; it is unofficial and not audited by Microsoft. [COMMUNITY S1349] Using it from a `client` instance
  (which does run on Windows) would still need to call into CNG (`NCryptProtectSecret`/
  `NCryptUnprotectSecret`) for the encrypt/decrypt calls themselves, which needs either `ctypes`/`cffi`
  bindings (not pure Python) or the community RPC-based library. [DER S1342,S1349]
- **age + sops (reuse):** confirmed again from [[secret-vault-encryption]]: neither has a native rotation
  hook tied to group membership; both are file-encryption tools, not a live per-request grant/revoke
  mechanism, so a membership change (e.g. removal from a role group) does not by itself revoke a
  previously-decrypted vault key -- revocation requires re-encrypting to a new recipient list and
  distributing it, exactly as for any static-recipient scheme. [DER S1000,S1001]

## Reference
| Option | Who can decrypt | Effect of membership change | Rotation | Python path | Sources |
|---|---|---|---|---|---|
| DPAPI-NG `SID=` group descriptor | members of the AD group (via GKDI) | [UNK]: not found whether a cached secret remains decryptable after removal without a new logon | re-encrypt to new descriptor | `ctypes`/`cffi` to CNG, or community `dpapi-ng` off-Windows | S1342, S1343, S1349 |
| CNG KSP + TPM | the machine (non-exportable key) | n/a (machine-bound, not group-bound) | re-provision key in TPM | `ctypes`/`cffi` to CNG; no pure-Python path found | S1343 |
| SQL Always Encrypted (CMK in cert store) | holders of the CMK certificate's private key | revoking cert access revokes decrypt | re-encrypt CEK to new CMK | `pyodbc`+ODBC 18 only; not `mssql-python` | S1340, S1341, S1350 |
| SQL symmetric keys / EKM | SQL principals granted `VIEW DEFINITION`/key permission on the key | `REVOKE`/`DROP` on the SQL principal | `ALTER ... REGENERATE`/re-key | any SQL driver (T-SQL-level, no client crypto) | S1341 (adjacent) |
| age + sops | holders of the recipient's private key file | none automatic; must re-encrypt | manual re-encrypt to new recipients | pure Python (`age.py`/`sops.py` wrappers) | S1000, S1001 |

## Examples
No fixture-specific configuration; mechanism-only facts, applicable uniformly to a pseudonymization vault key and
HMAC key regardless of tenant.
