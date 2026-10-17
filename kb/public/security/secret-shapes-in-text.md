---
topic: security/secret-shapes-in-text
priority: P2
applies_to: "free text (a command line, a log line, a pasted note) that a redactor or scanner reads for credentials: HTTP Authorization headers, URL userinfo, PEM and OpenSSH private key blocks, key=value assignments, SQL Server connection strings"
retrieved_utc: 2026-10-17
sources: [S-wct3uoax, S-neu52zjd, S-3mhhoprh, S-bs6jgunr, S-kskf5yv7, S-as3c23xb, S-cr2wj4s2, S-xnlryf7y, S-lglgs6wg, S-k57sryj7, S-spzetxhy, S-d2kitjup, S-imedhmhc, S-bcbpadtc, S-4rjxcq6v]
status: partial
---

# Credential shapes in free text

## Summary
A credential in free text has a grammar its specification fixes, and that grammar does not depend on the value's length or randomness. An HTTP `Authorization` header carries `Bearer <token68>` or `Basic <base64 of user:password>`; a URL may carry `user:password@` before the host; a private key is a multi-line block between a `BEGIN ... PRIVATE KEY` line and an `END` line; an assignment is a key name, a separator and a value. The same text can reach a scanner in another spelling: inside a JSON string every quotation mark and backslash is escaped, and a URL path segment may carry `;key=value` parameters. The specifications say what the value looks like (which characters, how it ends); no specification lists the key names that mark an assignment as secret. Scanners keep their own lists, and the one read here (detect-secrets) is a community tool, not a standard.

## Facts
### HTTP Authorization header
- `Authorization = credentials` and `credentials = auth-scheme [ 1*SP ( token68 / #auth-param ) ]`; the scheme is a case-insensitive token, so `Bearer`, `bearer` and `BEARER` name one scheme. [DOC S-wct3uoax]
- `Proxy-Authorization` takes the same `credentials` grammar, so a credential in that header has the same shape as one in `Authorization`. [DOC S-wct3uoax]
- `token68` is one or more of letters, digits and `- . _ ~ + /` followed by optional `=` padding; it can hold base64, base64url, base32 or hex, and no whitespace. [DOC S-wct3uoax]
- The Bearer scheme is `credentials = "Bearer" 1*SP b64token`, where `b64token` has the same character set as `token68`. [DOC S-neu52zjd]
- The Basic scheme builds `user-id ":" password`, then Base64-encodes it; the first colon separates the two, so text after it, colons included, is the password. [DOC S-3mhhoprh]
- The RFC calls Basic not secure without an external system such as TLS, because the user-id and password are passed as cleartext inside the Base64. [DOC S-3mhhoprh]
- The Claude API takes its key as `Authorization: Bearer <token>` or, as a legacy fallback, in an `x-api-key` header. [DOC S-bcbpadtc]
- A Bearer or Basic credential has no minimum length or entropy: any non-empty `token68` is valid, and a Basic value is only the Base64 of `user:password`, so a short pair gives a short, low-entropy value. The shape (scheme word, then the token68) is what marks it, not the value. [DER S-wct3uoax, S-neu52zjd, S-3mhhoprh: grammar sets no length floor and Base64 adds no randomness]

### URL userinfo
- The `userinfo` part of a URI is `*( unreserved / pct-encoded / sub-delims / ":" )`, written before `@` in the authority. [DOC S-bs6jgunr]
- The `user:password` form in userinfo is deprecated: applications should not render the data after the first colon as clear text, and should reject storing it unencrypted. [DOC S-bs6jgunr]
- URIs are logged by browsers, proxies and bookmark stores, so the RFC says a producer should not put a secret password in one. [DOC S-bs6jgunr]
- Because userinfo allows percent-encoding and the sub-delimiters, a password can contain `! $ & ' ( ) * + , ; =` and `%XX` escapes; it ends at the `@` that closes the authority. [DER S-bs6jgunr: the userinfo grammar above]

### Private key blocks
- A PKIX textual encoding is a line `BEGIN <label>`, base64 text and a line `END <label>`, each marker line with exactly five hyphens on both ends and one space after `BEGIN` or `END`. [DOC S-kskf5yv7]
- The labels for private keys are `PRIVATE KEY` (PKCS #8) and `ENCRYPTED PRIVATE KEY`. [DOC S-kskf5yv7]
- Base64 lines are 64 characters, and unlike legacy PEM, OpenPGP armor and the OpenSSH key format the textual encoding permits no header lines; the older formats do carry them, so a block can hold lines that are not base64. [DOC S-kskf5yv7]
- OpenSSL's traditional format, which the RSA write routines still use, is a block labelled `RSA PRIVATE KEY`. [DOC S-as3c23xb]
- OpenSSH writes its own private key files between `BEGIN OPENSSH PRIVATE KEY` and `END OPENSSH PRIVATE KEY`, and still names a `SSH PRIVATE KEY FILE FORMAT 1.1` legacy header. [CODE S-cr2wj4s2: sshkey.c#MARK_BEGIN, sshkey.c#MARK_END, sshkey.c#LEGACY_BEGIN]
- The key material of every one of these formats sits on the lines between the two markers, over many lines, so replacing only the `BEGIN` line leaves the secret in the body. [DER S-kskf5yv7, S-cr2wj4s2: the body is between the markers, not on the marker line]
- Four labels end in `PRIVATE KEY` (`PRIVATE KEY`, `ENCRYPTED PRIVATE KEY`, `RSA PRIVATE KEY`, `OPENSSH PRIVATE KEY`); the label may be preceded by an algorithm word, so a match on the marker's last two words covers all four. [DER S-kskf5yv7, S-as3c23xb, S-cr2wj4s2: the labels listed above]

### Assignments and connection strings
- A SqlClient connection string is semicolon-separated keyword=value pairs; the password keyword is `Password` or `PWD`, and the page advises against it in favour of integrated security. [DOC S-xnlryf7y]
- A connection string value that contains a semicolon or a quote character must be enclosed in double quotation marks (single quotation marks when it holds a semicolon and a double quote), so a quoted value can hold a `;`. [DOC S-xnlryf7y]
- Connection string keywords are case-insensitive. [DOC S-lglgs6wg]
- Microsoft's Purview pattern for a SQL Server connection string takes the string `Password` or `pwd` (where `pwd` isn't preceded by a lowercase letter), an equal sign, then any combination of 7-128 characters that aren't a semicolon, forward slash or quotation mark. [DOC S-k57sryj7]
- The same detector ignores a value that is already a placeholder: `Password` or `pwd` followed by `=` and an asterisk, or by `=` and a `<...>` form of up to 200 letters, digits, `*`, hyphens, underscores or spaces. [DOC S-k57sryj7]
- The AWS documentation pairs an access key ID with a secret access key and exports the latter as the environment variable `AWS_SECRET_ACCESS_KEY`; its example value contains `/` characters. [DOC S-d2kitjup, S-imedhmhc]
- A value rule that stops at `/` therefore cuts an AWS secret access key at its first slash and leaves the rest in the text; a value rule for that key reads up to whitespace, a quote or the end of the assignment. [DER S-d2kitjup, S-imedhmhc: the documented example holds `/`]
- detect-secrets 1.5.0 flags a line when a deny-list word (`api_?key`, `auth_?key`, `service_?key`, `account_?key`, `db_?key`, `database_?key`, `priv_?key`, `private_?key`, `client_?key`, `db_?pass`, `database_?pass`, `key_?pass`, `password`, `passwd`, `pwd`, `secret`, plus two Spanish spellings of password) is followed by a value, case-insensitively and with any prefix and suffix of word characters around the word. [CODE S-spzetxhy: detect_secrets/plugins/keyword.py#DENYLIST]
- The same detector reads the separator as `:`, `:=`, `=`, `==`, `!=` or `===`, with the value quoted or bare, and a closing `]`, `'` or `"` allowed between the key and the separator. [CODE S-spzetxhy: detect_secrets/plugins/keyword.py#FOLLOWED_BY_COLON_REGEX, detect_secrets/plugins/keyword.py#FOLLOWED_BY_EQUAL_SIGNS_REGEX]
- No official source lists the key names that mark an assignment as secret: the deny-list above is one community tool's, and Microsoft's detector covers connection strings only. [UNK: no standard found]
- A longer key whose last word is on the deny-list (`DB_PASSWORD`, `aws_secret_access_key`, a prefixed environment variable) is therefore the same assignment as the bare word, in the scanner's reading. [DER S-spzetxhy: the prefix and suffix `\w*` of the deny-list regex]

### JSON string values
- A JSON string (RFC 8259, section 7) begins and ends with quotation marks, and the characters that must be escaped inside it are the quotation mark, the reverse solidus (backslash) and the control characters U+0000 to U+001F. [DOC S-4rjxcq6v]
- The two-character escapes are `\"` for the quotation mark and `\\` for the backslash (also `\/`, `\b`, `\f`, `\n`, `\r`, `\t`); any character may instead be written as `\u` and four hex digits, so one backslash is `"\\"` or `"\u005C"`. [DOC S-4rjxcq6v]
- The grammar of a string character is `unescaped / escape ( %x22 / %x5C / %x2F / %x62 / %x66 / %x6E / %x72 / %x74 / %x75 4HEXDIG )`, and `unescaped` is `%x20-21 / %x23-5B / %x5D-10FFFF`, which leaves out `"` (%x22) and `\` (%x5C): a bare one of them never sits inside a string value. [DOC S-4rjxcq6v]
- The RFC warns that an implementation comparing strings with the escapes unconverted may find `"a\\b"` and `"a\u005Cb"` unequal, so one value has more than one spelling in the text. [DOC S-4rjxcq6v]
- A string's closing quote is therefore the first `"` that is not the second character of an escape: a `"` preceded by an odd number of backslashes is data, one preceded by an even number (none included) ends the string. [DER S-4rjxcq6v: the escape grammar above, where `\\` consumes a backslash before the next character is read]
- JSON text carried as a string inside another JSON text (a log line whose field holds a payload that went through a logger) has every `"` of the inner text written `\"` and every `\` written `\\`, so `{"client_secret": "<secret>"}` appears as `{\"client_secret\": \"<secret>\"}`, and a secret that holds a quote or a backslash appears with that escape in it. A pattern written for bare quotes around the key and the value does not match this text, and a value rule that stops at the first quote or backslash ends inside the secret. [DER S-4rjxcq6v: the two-character escapes and the `unescaped` set above]

### URL path parameters
- A path segment is `*pchar` and `pchar = unreserved / pct-encoded / sub-delims / ":" / "@"`; the `sub-delims` set is `! $ & ' ( ) * + , ; =`, so a segment may hold `=` and `;` as they are, with no percent-encoding. [DOC S-bs6jgunr]
- The RFC calls a path segment opaque to the generic syntax and says producers often use `;` and `=` to delimit parameters and parameter values of that segment, with `name;v=1.1` as its example. [DOC S-bs6jgunr]
- A `key=value` pair can therefore ride in a URL's path, so no `?` or `&` need come before it, as in `https://api.corp.example.com/v1/jobs;token=<secret>/run`; its value runs to the next `/`, `?` or `#` (a `/` ends the segment, and a segment has no `/`), and may hold further `;` and `=`. [DER S-bs6jgunr: the `segment` and `pchar` grammar and the parameter example]
- A rule that looks for a key only after `?` or `&`, or that ends a value at the first `;`, therefore misses or cuts a credential carried as a path parameter. [DER S-bs6jgunr: the path grammar above allows `=` and `;` in a segment]

## Reference
Open gaps of this topic: `python3 _tools/rag.py audit security/secret-shapes-in-text --entries`; a gap is worked with /kb-research.

| Shape | Marker | Value | Source |
| --- | --- | --- | --- |
| Authorization Bearer | `Bearer` + space(s) | `b64token`, no length floor | RFC 6750 |
| Authorization Basic | `Basic` + space(s) | Base64 of `user-id:password` | RFC 7617 |
| URL userinfo | `scheme://user:` ... `@host` | pct-encoded text up to `@` | RFC 3986 |
| PKCS #8 / PEM key | `BEGIN [ENCRYPTED ]PRIVATE KEY` | base64 lines to the `END` line | RFC 7468 |
| Traditional RSA | `BEGIN RSA PRIVATE KEY` | base64 lines, may carry headers | OpenSSL |
| OpenSSH key | `BEGIN OPENSSH PRIVATE KEY` | base64 lines to the `END` line | sshkey.c |
| Connection string | `Password=` or `PWD=` | text up to `;`, or a quoted value | SqlClient docs |
| Environment line | `AWS_SECRET_ACCESS_KEY=` | may hold `/` and `+` | AWS docs |
| JSON string value, escaped | `\"key\": \"` inside another string | `\"` for a quote, `\\` for a backslash | RFC 8259 |
| URL path parameter | `;key=` inside a path segment | text up to `/`, `?` or `#` | RFC 3986 |

## Examples
- SNIPPET: placeholder inputs, one for each shape in the table, as a redaction test would plant them (build real-looking values at run time, never commit one); context: free text, any language; checked: no [DER S-wct3uoax, S-3mhhoprh, S-bs6jgunr, S-kskf5yv7, S-xnlryf7y, S-4rjxcq6v: the shapes the facts above give]

```text
Authorization: Bearer <token>
Authorization: Basic <base64 of user:password>
postgres://jan.kowalski:<password>@db.corp.example.com:5432/app
Server=db.corp.example.com;User Id=jan.kowalski;Password=<password>;
DB_PASSWORD=<password>
{"client_secret": "<secret>"}
{"msg": "{\"client_secret\": \"<secret>\"}"}
https://api.corp.example.com/v1/jobs;token=<secret>/run
```
