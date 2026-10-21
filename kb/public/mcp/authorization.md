---
topic: mcp/authorization
priority: P1
applies_to: "MCP specification 2026-07-28"
retrieved_utc: 2026-10-21
sources: [S707, S701, S702, S-neu52zjd, S-e5aahjao]
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
- A scope value is "a list of space-delimited, case-sensitive strings" whose strings "are defined by the authorization server"; their order does not matter and each string adds one access range. [DOC S-e5aahjao]
- RFC 6750 adds that scope values are implementation defined and that "there is no centralized registry for them", so a namespace such as `files:write` or one per team is the service's own choice. [DOC S-neu52zjd]
- A scope string is one or more characters from `%x21`, `%x23-5B` and `%x5D-7E`: no space, no double quote and no backslash, while `:` and `/` are allowed (RFC 6750 repeats the set for the `scope` attribute). [DOC S-e5aahjao, S-neu52zjd]
- The authorization server "MAY fully or partially ignore the scope requested", and when the scope it issues differs from the request it MUST return the `scope` response parameter with what was granted. [DOC S-e5aahjao]
- RFC 6750 error codes of a protected-resource failure: `invalid_request` (malformed request, SHOULD be 400), `invalid_token` (expired, revoked, malformed or otherwise invalid token, SHOULD be 401, the client MAY get a new token and retry) and `insufficient_scope` (the request needs higher privileges than the token has, SHOULD be 403, MAY carry the `scope` attribute with the scope needed). A request with no authentication information SHOULD get no error code. [DOC S-neu52zjd]
- The MCP revision repeats the 403 rule for a call whose token lacks scope: `WWW-Authenticate: Bearer` with `error="insufficient_scope"`, `scope="..."`, `resource_metadata` and an optional `error_description`; the `scope` attribute names what the operation needs, and the server is not required to repeat the scopes the client already holds. [DOC S707]
- The server SHOULD put every scope the current operation needs into one challenge (not one missing scope per retry) and be consistent about which scopes it lists; clients acting for a user SHOULD try step-up authorization, and a `client_credentials` client MAY step up or abort. [DOC S707]
- Servers MUST account for scope hierarchies, where a broader scope implies narrower ones, when deciding whether a token is sufficient. [DOC S707]
- So a service with its own bearer tokens maps a token (a key file, a database row) to the identity it was issued to, and a team-wide scope that implies each operator's narrower scope is the hierarchy the revision asks servers to honour; the OAuth documents fix the scope syntax and the error codes, not the token's storage or a file layout. [DER S707, S-neu52zjd, S-e5aahjao: hierarchy rule, reference-token text and free scope namespace read together]
- The RFC names `insufficient_scope` only for a token that is too weak, a case a step-up can cure; for a caller that must never reach a resource (another team's keys), it gives no separate error code, so a refusal of that kind is a plain 403 and adding `insufficient_scope` with a `scope` attribute would invite a step-up that cannot succeed. [DER S-neu52zjd, S707: the error-code definitions and the step-up flow]

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
