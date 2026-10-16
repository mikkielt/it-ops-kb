---
topic: mcp/authorization
priority: P1
applies_to: "MCP specification 2026-07-28"
retrieved_utc: 2026-10-16
sources: [S707, S701, S702, S-neu52zjd]
status: complete
---
# Authorization (2026-07-28)

## Summary
Authorization is optional and defined for HTTP transports only (OAuth 2.1 subset). stdio implementations SHOULD NOT
follow it and should take credentials from the environment. 2026-07-28 adds RFC 9207 `iss` validation, requires
`application_type` in DCR, binds client credentials to their issuer, and deprecates Dynamic Client Registration in
favour of Client ID Metadata Documents.

## Facts
- Authorization is OPTIONAL; HTTP transports SHOULD conform; STDIO transports SHOULD NOT follow the spec and instead retrieve credentials from the environment. [DOC S707]
- Based on OAuth 2.1 draft-13, RFC 6750, RFC 8414, RFC 7591, RFC 8707, RFC 9728, RFC 9207, Client ID Metadata Documents draft, OIDC Discovery. [DOC S707]
- MCP servers MUST implement RFC 9728 Protected Resource Metadata; clients MUST use it for authorization-server discovery. [DOC S707]
- Clients MUST send the RFC 8707 `resource` parameter (canonical server URI) in authorization and token requests. [DOC S707]
- Servers MUST validate that access tokens were issued for them (audience) and MUST NOT accept or transit other tokens. [DOC S707]
- Access tokens MUST NOT be put in the URI query string. [DOC S707]
- AS SHOULD include `iss` in authorization responses; clients MUST validate a present `iss` against the recorded issuer before redeeming the code. [DOC S701]
- Clients MUST key persisted credentials by issuer and re-register when the authorization server changes. [DOC S701]
- Dynamic Client Registration (RFC 7591) is Deprecated as of 2026-07-28 in favour of Client ID Metadata Documents; earliest removal is the first revision on or after 2027-07-28. [DOC S702]
- The bearer-token rules the spec builds on (RFC 6750, Standards Track, October 2012): a bearer token is usable by any party that holds it, with no proof of possession, and the scheme is "a general HTTP authorization method" for bearer tokens "from any source", not only OAuth 2.0 flows. [DOC S-neu52zjd]
- A client sends the token as `Authorization: Bearer <token>`; resource servers MUST support that header, the form-encoded body parameter is a MAY for servers and SHOULD NOT be used where the header is available, and the query-parameter form is not recommended because URLs get logged. [DOC S-neu52zjd]
- A resource server that gets a request with no credentials, or with a token that does not grant access, MUST answer with a `WWW-Authenticate` response header using the `Bearer` scheme (optionally a `realm`, a `scope` and an `error` such as `invalid_token`), and the page's examples pair it with status 401. [DOC S-neu52zjd]
- RFC 6750 requires TLS for every request that carries a bearer token and says short-lived tokens (one hour or less) limit the damage of a leak; it does not fix the token's format, and says a token may be a reference that is infeasible to guess and resolved at the issuer. [DOC S-neu52zjd]
- So a service that issues its own long-lived per-operator tokens over plain HTTP carries a token any on-path party can replay; the RFC's rules assume TLS, so such a service binds to loopback or sits behind a TLS terminator, and revocation means deleting the server-side record of the token. [DER S-neu52zjd: the TLS requirement, the reference-token text and the leak-impact text read together]

## Reference
| Transport | Authorization spec applies |
|---|---|
| Streamable HTTP | SHOULD conform |
| stdio | SHOULD NOT; credentials from environment |
| other/custom | MUST follow established security best practices |

## Examples
an MCP server over stdio on PL-LT-00123 runs as jan.kowalski and uses that user's environment/credentials; no MCP OAuth flow applies.

See mcp/transports-streamable-http.md for the HTTP transport this authorization spec applies to (Origin validation,
localhost binding, header mirroring) and mcp/transports-stdio.md for the stdio transport it does not.
