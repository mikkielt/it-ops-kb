---
topic: auth/oauth-pkce-oidc-id-token
priority: P3
applies_to: "OAuth 2.0 authorization code with PKCE (RFC 7636) for a public client, OIDC id_token validation (OpenID Connect Core 1.0), and what Discord documents for each"
retrieved_utc: 2026-10-11
sources: [S-cc7tmfsl, S-z7jhscsu, S-utofkpju, S-btzqf4mj, S-fhpwukk7, S-xrzcvqcp]
status: partial
---

# OAuth2 with PKCE for a public client, OIDC id_token validation and Discord

## Summary
PKCE binds an authorization code to a secret the client holds, so a stolen code is useless on its own; it is how a client with no secret (a public client) uses the authorization code grant. An OIDC `id_token` is a signed statement about the sign-in that the client must validate claim by claim; `iss` plus `sub` is the stable user key. Discord documents PKCE through its Social SDK guides and OIDC through its requirements for external identity providers; its general OAuth2 page lists neither.

## Facts

### PKCE (RFC 7636)
- Public clients that use the authorization code grant are exposed to the authorization code interception attack, which PKCE addresses; a client binary cannot be considered confidential. [DOC S-cc7tmfsl]
- The client makes a fresh `code_verifier` for each authorization request: 43 to 128 characters from `A-Z a-z 0-9 - . _ ~`, and the RFC recommends base64url of 32 random octets (43 characters); at least 256 bits of entropy SHOULD be used. [DOC S-cc7tmfsl]
- `code_challenge` is `BASE64URL(SHA256(ASCII(code_verifier)))` for `S256` or the verifier itself for `plain`; a client able to use `S256` MUST, and MUST NOT downgrade to `plain` after trying `S256`. [DOC S-cc7tmfsl]
- The authorization request carries `code_challenge` (required for PKCE) and `code_challenge_method` (optional and defaulting to `plain` when absent, so a client sets `S256` explicitly); the token request carries `code_verifier`. [DOC S-cc7tmfsl]
- The server stores the challenge and method with the code, recomputes the challenge from the verifier at the token endpoint and answers `invalid_grant` on a mismatch. [DOC S-cc7tmfsl]
- A server that supports PKCE is required to support `S256`; `plain` exists for compatibility with constrained clients and SHOULD NOT be used in new implementations that can do `S256`. [DOC S-cc7tmfsl]

### OIDC id_token validation
- The `iss` claim must exactly match the OpenID Provider's issuer identifier, and `aud` must contain the client's own `client_id`; a token that does not list the client, or lists audiences the client does not trust, is rejected. [DOC S-z7jhscsu]
- When `azp` is present the client should check that it is its own `client_id`. [DOC S-z7jhscsu]
- The signature is validated with the issuer's keys using the algorithm in the JWT header (default `RS256` or the one registered); for a MAC algorithm the key is the client secret; validating the TLS server may replace the signature check only for an id_token received directly from the token endpoint. [DOC S-z7jhscsu]
- The current time must be before `exp`; `iat` may be used to reject a token issued too far in the past, which also bounds how long nonces must be kept, with an acceptable range left to the client. [DOC S-z7jhscsu]
- If a `nonce` was sent in the authentication request, the id_token must carry the same `nonce`, and the client should also check it for replay. [DOC S-z7jhscsu]
- `iss` together with `sub` is the only stable identifier of an end user across issuers, because `sub` is locally unique and never reassigned within an issuer; other claims such as a name or an email carry no such guarantee. [DOC S-z7jhscsu]
- Checks that a signed `exp` and `aud` do not replace: the id_token authenticates the sign-in at the client that started it, so a server must not accept an id_token addressed to another `aud` as a login for itself. [DER S-z7jhscsu: aud must contain the receiving client's client_id]

### Discord
- Discord's OAuth2 topic page lists the authorization code, implicit and client credentials grants and bot and webhook flows; token calls use HTTP Basic or `client_id` and `client_secret` in the form body, and the page's examples show `expires_in` 604800 with a refresh token. [DOC S-utofkpju]
- That page does not mention `code_challenge`, `code_verifier` or PKCE. [DOC S-utofkpju: the page read has no PKCE parameter]
- The Social SDK account-linking guide uses a code challenge and verifier: `Client::CreateAuthorizationCodeVerifier` makes both, the challenge goes in the authorization arguments and the verifier into the token exchange. [DOC S-btzqf4mj]
- A backend with a client secret may exchange the code itself by posting `grant_type=authorization_code`, `code`, `redirect_uri` and `code_verifier` with Basic authentication; an app with no backend enables **Public Client** and calls `Client::GetToken` with the verifier. [DOC S-btzqf4mj]
- Discord says public clients cannot securely store client secrets, recommends confidential clients with proper secret management for production, and warns most games will not want Public Client enabled. [DOC S-fhpwukk7]
- The default scope helpers of the Social SDK return `openid sdk.social_layer_presence` and `openid sdk.social_layer`, so the `openid` scope is part of the documented SDK flow. [DOC S-fhpwukk7]
- Discord as a relying party for an external OIDC provider requires: an issuer URL over HTTPS (no query, fragment, credentials, IP address or private TLD) whose discovery document sits at `{issuer}/.well-known/openid-configuration` (no redirects followed, including for the JWKS), a JWT header `kid` that matches a JWKS key, `iss` equal to the configured issuer, `sub` present, `aud` including the configured client ID, `exp` not past, and `iat` within the past seven days. [DOC S-xrzcvqcp]
- It accepts `RS`, `ES` and `PS` families (256, 384, 512) and does not support HMAC algorithms such as HS256. [DOC S-xrzcvqcp]
- Open: whether Discord's plain HTTP `/oauth2/authorize` accepts `code_challenge` and `code_challenge_method=S256` for a bot-less web app is not stated on the pages read; only the SDK flow is documented. [UNK: not stated on the OAuth2 topic page or account-linking guides]
- Open: the claims and signing keys of an `id_token` that Discord itself issues for the `openid` scope are not described on the pages read. [UNK: the identity-provider page covers tokens Discord receives, not tokens it issues]

## Reference
| Check | Claim or parameter | Source |
|---|---|---|
| Issuer | `iss` equals the issuer identifier | S-z7jhscsu |
| Audience | `aud` contains our `client_id` (and no untrusted audience) | S-z7jhscsu |
| Signature | JWS with the issuer's key, expected `alg` only | S-z7jhscsu |
| Expiry | now is before `exp` | S-z7jhscsu |
| Age | `iat` not older than our limit (Discord's: 7 days) | S-z7jhscsu, S-xrzcvqcp |
| Replay | `nonce` equals the one sent, and is seen once | S-z7jhscsu |
| User key | `iss` + `sub` | S-z7jhscsu |
| PKCE | `S256` challenge, 256-bit verifier, `invalid_grant` on mismatch | S-cc7tmfsl |

## Examples
- SNIPPET: make a PKCE verifier and S256 challenge; context: Python standard library, per-request values kept server side with the `state`; checked: no [DOC S-cc7tmfsl: sections 4.1 and 4.2]
```python
import base64, hashlib, secrets

verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")
challenge = base64.urlsafe_b64encode(
    hashlib.sha256(verifier.encode("ascii")).digest()
).rstrip(b"=").decode("ascii")
```
