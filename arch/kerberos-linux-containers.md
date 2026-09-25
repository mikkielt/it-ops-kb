---
topic: arch/kerberos-linux-containers
priority: P1
applies_to: "MIT Kerberos, SQL Server on Linux, msodbcsql18, Python gssapi/requests-gssapi (docs current 2026-09-24)"
retrieved_utc: 2026-09-24
sources: [S1604, S1605, S1606, S1607]
status: complete
---

# Kerberos from Linux containers (keytabs, kinit, adutil)

## Summary
- Linux/Python Kerberos never touches a gMSA's managed password directly: it authenticates as an ordinary AD account (human or service) using a keytab, obtained with a **password an administrator already knows**, not via `msDS-ManagedPassword` retrieval. [DOC S1607]
- The Microsoft-supported pattern for Linux/containers is keytab + `kinit`/PAM + periodic renewal via cron; no ODBC/driver-level automatic renewal exists. [DOC S1605]
- `adutil` (Microsoft, SQL-Server-scoped) automates AD account/SPN/keytab creation but requires the account's own password as input (`adutil keytab createauto ... --password '<password>'`) — it is built for regular AD service accounts, not gMSA. [DOC S1606]
- Python HTTP Negotiate/SPNEGO libraries (`requests-gssapi`, successor to `requests-kerberos`) work purely against the system Kerberos credential cache or a `KRB5_KTNAME` keytab; they do not fetch or manage gMSA passwords themselves. [DOC S1604]
- No official Microsoft page documents a way for Linux to retrieve a gMSA's `msDS-ManagedPassword` and turn it into a keytab; AWS's `credentials-fetcher` does this by directly reading gMSA credentials from AD over LDAP, but it is a third-party (AWS) open-source daemon, not a Microsoft-documented path. [COMMUNITY S1608]

## Facts
- ODBC Driver for SQL Server on Linux/macOS supports Kerberos integrated authentication via `Trusted_Connection=yes`; it uses MIT Kerberos KDC, GSSAPI and Kerberos v5 libraries, and requires the client already hold a valid TGT (via `kinit` or PAM) before connecting — the driver itself never manages credentials. [DOC S1605]
- Two `kinit` patterns are documented for a service that runs unattended: `kinit <principal> <password>`, or `kinit <principal> -t <keytab>` where the keytab was created with `ktutil`. [DOC S1605]
- "The ODBC driver does not renew credentials itself; ensure that there is a cron job or script that periodically runs to renew the credentials before their expiration." — Microsoft explicitly pushes renewal responsibility to the operator. [DOC S1605]
- If Kerberos authentication fails, the Linux/macOS ODBC driver does **not** fall back to NTLM. [DOC S1605]
- The SPN syntax the driver expects is the same `MSSQLSvc/<fqdn>:<port>` used on Windows; `ServerSPN`/`FailoverPartnerSPN` connection attributes are documented as **not supported** on Linux/macOS. [DOC S1605]
- `adutil` is described as "Support ... limited to SQL Server use cases only," must run from a host already domain-joined (or at least able to `kinit` a privileged account), and its keytab subcommand (`adutil keytab createauto -k <path> -p <port> -H <fqdn> --password '<password>' -s MSSQLSvc`) takes the account password as an explicit flag — there is no gMSA-aware variant or `msDS-ManagedPassword` retrieval option documented. [DOC S1606]
- `mssql-conf` can also create the SQL Server service keytab, and the adutil docs cross-reference it for the `useLdaps` / LDAPS configuration path, but the underlying account is still a conventional AD account with a password, created via `adutil user create` / `adutil spn addauto`. [DOC S1606]
- Python `requests-gssapi` (the maintained successor to `requests-kerberos`) needs a Kerberos TGT already present in a credential cache (`kinit`, or `$KRB5CCNAME` pointed at one); for unattended/service use it reads a keytab via the `KRB5_KTNAME` environment variable — "having a keytab is sufficient" for a service identity. [DOC S1604]
- HTTP Negotiate/SPNEGO itself is protocol-defined (RFC 4178 SPNEGO, RFC 4559 HTTP Negotiate), independent of any particular client library; `requests-gssapi`/`pyspnego`/`gssapi` all implement the same wire protocol against the system Kerberos libraries rather than reimplementing crypto. [DOC S1604]
- AWS's `credentials-fetcher` (Apache 2.0, AWS open source) is a Linux daemon that "retrieves gMSA credentials from Active Directory over LDAP" and creates/refreshes Kerberos tickets from them for containers; it supports both domain-joined and non-domain-joined hosts (non-domain-joined needs AD user credentials in a secret store to bootstrap). It is the closest thing to "gMSA on Linux," but it is AWS's own daemon (originating from and primarily documented for Amazon Linux 2023/Fargate/ECS), not a Microsoft product or Microsoft Learn page. [COMMUNITY S1608]
- No Microsoft Learn, MIT Kerberos, or SQL Server Linux doc found that states Python (`gssapi`/`pyspnego`/`requests-kerberos`) or any Microsoft-supported Linux tool can retrieve `msDS-ManagedPassword` for a gMSA directly — only `credentials-fetcher` (AWS, COMMUNITY) claims this. [UNK — no first-party Microsoft doc]

## Reference
| Question | Answer | Source |
|---|---|---|
| Can Python (gssapi/requests-gssapi/pyspnego) call an HTTP SPN via Negotiate using a keytab on Linux? | Yes — same TGT/keytab mechanism the ODBC driver uses; `KRB5_KTNAME` env var for a keytab | DOC S1604, S1605 |
| Can Python/Linux fetch a gMSA's managed password (`msDS-ManagedPassword`) via a Microsoft-documented path? | No first-party doc found; only AWS `credentials-fetcher` (COMMUNITY) does this, via LDAP | UNK / COMMUNITY S1608 |
| Does `adutil` support gMSA keytab creation? | No — requires the account's own password; built for ordinary AD service accounts | DOC S1606 |
| Does the ODBC driver on Linux renew Kerberos credentials itself? | No — operator must run a cron/script (kinit + keytab) before TGT expiry | DOC S1605 |

## Examples
```bash
# Fixture: a scheduled sync job on a Linux container, using a plain AD service account
# (not a gMSA) with a keytab mounted from a Secret
kinit -kt /var/run/secrets/sync-svc/sync-svc.keytab sync-svc@CORP.EXAMPLE.COM
export KRB5_KTNAME=/var/run/secrets/sync-svc/sync-svc.keytab
# Python: requests-gssapi picks up the TGT from the default ccache automatically
```

## Gaps
- No Microsoft-documented way to turn a real gMSA's rotating password into a Linux keytab; Microsoft's Linux/container Kerberos story (adutil, ODBC driver, mssql-conf) is built around conventional password-bearing AD accounts. See LAB note below.
