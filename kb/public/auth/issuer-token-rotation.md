---
topic: auth/issuer-token-rotation
priority: P3
applies_to: "Credential ceilings and rotation at the issuer: GitLab access tokens (rotate API), Cloudflare API tokens (TTL, roll), R2 S3 credentials, Discord bot token reset"
retrieved_utc: 2026-10-11
sources: [S-mhouxzvy, S-tef353hj, S-pu7alvhx, S-i7k2yzu3, S-mk66h6ri, S-olzs5pbh, S-pj2f4zxz, S-gvnx776h, S-agqpl4si, S-34drdif4, S-xaij2xlf, S-azsoi3uw, S-jnot5rsp, S-utofkpju, S-fsqu2grq, S-ytnvr75r]
status: partial
---

# Issuer-side ceilings and rotation of API credentials

## Summary
The four issuers differ in what they let a holder do to a credential: GitLab rotates a token in one call and revokes the old one at once, Cloudflare rolls a token's secret in place (the old value dies at once) or lets a token carry its own expiry, R2's S3 key pair is a function of a Cloudflare API token, and Discord's bot token is replaced from the developer portal. None keeps the old value valid for an overlap, so a rotation is a cut-over: write the new value to every consumer, then verify by using it. Extends `agents/api-tokens-issue-and-store.md` and `gitlab/deploy-keys-and-tokens.md`.

## Facts

### GitLab
- Personal, group, project and impersonation access tokens expire at midnight UTC on their expiry date, and an expired token cannot be reactivated; a new token must be created. [DOC S-mhouxzvy]
- A token created without an expiry date gets 365 days from today; an administrator can turn the requirement off, after which new tokens without a date never expire. [DOC S-mhouxzvy]
- In GitLab Ultimate administrators can set a maximum allowable lifetime; the limit was extended to 400 days in 17.6 behind the feature flag `buffered_token_expiration_limit`, off by default. [DOC S-mhouxzvy]
- A personal access token of a service account can be created with no expiry date and then never expires. [DOC S-mhouxzvy]
- Expiry emails go out seven days before expiry, and from 17.6 also 30 and 60 days before (generally available in 17.7). [DOC S-mhouxzvy]
- `POST /personal_access_tokens/:id/rotate` revokes the previous token and creates a new one that expires after one week unless `expires_at` is given; `id` may be `self`, which needs the `api` or `self_rotate` scope. [DOC S-tef353hj]
- A rotate call answers `401` when the token has expired or was revoked, so a token cannot rotate itself after its expiry date; it is replaced by creating a new one with another credential. [DOC S-tef353hj]
- GitLab links a rotated token to its predecessor as a token family: rotating a token that was already revoked revokes every active token of that family, which limits a leaked old value. [DOC S-tef353hj]
- `POST /projects/:id/access_tokens/:token_id/rotate` revokes the old project token immediately and returns a new one (default expiry one week); another token needs a personal access token with `api`, and a project token rotates itself through `/self/rotate`. [DOC S-pu7alvhx]

### Cloudflare API tokens and R2
- A token can be restricted at creation by client IP address and by TTL; through the API the TTL is `not_before` and `expires_on`, UTC timestamps such as `2018-07-01T05:20:00Z`. [DOC S-i7k2yzu3, S-pj2f4zxz]
- The token secret is shown once at creation; `GET /user/tokens/verify` with the token as bearer returns its `id` and `status`. [DOC S-i7k2yzu3]
- Rolling a token regenerates its secret, invalidates the previous value, and keeps the same access and permissions; the new value uses the scannable format. [DOC S-mk66h6ri]
- The roll call is `PUT /user/tokens/{token_id}/value`, needs the `API Tokens Write` permission and returns the new value as the result. [DOC S-34drdif4]
- Scannable formats are `cfut_` (user token), `cfat_` (account token) and `cfk_` (global API key) followed by 40 characters and a checksum; tokens created or rolled now use them. [DOC S-olzs5pbh]
- A leaked token in a public GitHub repository is revoked by Cloudflare through GitHub secret scanning with an email to the owner; for a private repository GitHub only notifies. [DOC S-olzs5pbh]
- An account API token acts as a service principal with its own permissions and keeps working after the user who made it has left, and the dashboard form takes an optional expiration date; a user token acts for one user and becomes inactive if that user is removed from the account. [DOC S-gvnx776h, S-xaij2xlf]
- R2 describes account tokens as valid until manually revoked or until a preset expiration date. [DOC S-xaij2xlf]
- An R2 S3 key pair is derived from an API token: the Access Key ID is the token's `id` and the Secret Access Key is the SHA-256 hash of the token `value`; the Secret Access Key is shown once. [DOC S-xaij2xlf]
- R2 temporary credentials are issued from a parent token, expire automatically, carry a session token in `X-Amz-Security-Token`, are bound to one bucket and its permitted operations, and never exceed the parent's permissions; revoking the parent stops them at once. [DOC S-azsoi3uw]
- Temporary credentials can be minted through the API or locally by signing an HS256 JWT with the parent's secret access key; the temporary secret is the SHA-256 hex digest of the signed JWT and the parent's key id is reused. [DOC S-azsoi3uw]
- The temporary-credentials page advises the shortest `ttlSeconds` that fits and gives a 15-minute credential as the blast-radius example. [DOC S-azsoi3uw]

### Discord
- A bot token comes from the app's **Bot** page: "Reset Token" generates a new bot token, and a token cannot be viewed again unless it is regenerated, so it is copied at that moment. [DOC S-jnot5rsp]
- The same page warns that the token authorizes API requests with the app's permissions and must never be shared or checked into version control. [DOC S-jnot5rsp]
- OAuth2 token responses in the docs show `expires_in` of 604800 seconds (seven days) with a `refresh_token`, and `POST /oauth2/token/revoke` revokes an access or refresh token; the client secret is sent with HTTP Basic or in the form body. [DOC S-utofkpju]
- The implicit grant returns no refresh token, so the user re-authorizes when the token expires. [DOC S-utofkpju]
- The app's **Public Key** (General Information) verifies that HTTP requests come from Discord, and is separate from the bot token. [DOC S-jnot5rsp]

### Rotation by minting at the issuer, then verifying by use
- Because GitLab rotate and Cloudflare roll invalidate the old value in the same call, a consumer holding the old value fails from that moment; rotation is a cut-over, not an overlap. [DER S-tef353hj, S-pu7alvhx, S-mk66h6ri: the old token is revoked or invalidated by the call]
- An overlap needs a second credential: mint a new Cloudflare token (or GitLab token with another credential), switch consumers, check it with a read-only call, then delete or revoke the old one; `GET /user/tokens/verify` is the documented check for Cloudflare. [DER S-i7k2yzu3, S-mk66h6ri: tokens are independent objects; the verify endpoint]
- A token must be rotated before its expiry: a GitLab token that has expired answers `401` to its own rotate call, and an R2 key pair follows its Cloudflare token's lifetime. [DER S-tef353hj, S-xaij2xlf: expiry blocks self-rotation; key pair is a function of the token]
- Rolling a Cloudflare token that backs an R2 key pair changes the Secret Access Key (a hash of the new value) while the Access Key ID stays the same, so every S3 client holding the pair needs the new secret. [DER S-xaij2xlf, S-mk66h6ri: Secret Access Key = SHA-256 of the token value; roll replaces the value]
- Short-lived delegation that never leaves the issuer's reach is cheaper than rotating: R2 temporary credentials die with their TTL or with the parent. [DER S-azsoi3uw: expiry and revocation behaviour]
- Open: the documents read give no maximum or minimum for a Cloudflare token's `expires_on` or for R2 `ttlSeconds`. [UNK: not stated on the pages read]
- Open: whether the previous Discord bot token stops working at the moment of "Reset Token", or after a grace period, is not stated in the developer docs read. [UNK: not stated on the getting-started or OAuth2 pages]

## Reference
| Issuer credential | Default or ceiling | Rotation | Old value afterwards | Source |
|---|---|---|---|---|
| GitLab personal, group, project token | 365 days if unset; 400 days max behind a flag (Ultimate limit) | `rotate` API, `self` allowed; new token one week by default | revoked at once; family revoked on reuse | S-mhouxzvy, S-tef353hj, S-pu7alvhx |
| GitLab runner authentication token | `token_expires_at` 5 minutes to 15 days (see `gitlab/runner-registration.md`) | `reset_authentication_token` | replaced | S-fsqu2grq, S-ytnvr75r |
| Cloudflare user or account API token | optional TTL (`not_before`, `expires_on`); no ceiling stated | roll in place | invalidated at once | S-i7k2yzu3, S-mk66h6ri, S-34drdif4 |
| R2 S3 key pair | follows its API token | roll the token; secret = SHA-256 of the new value | old secret invalid | S-xaij2xlf |
| R2 temporary credential | `ttlSeconds` per credential | none: mint again | expires or dies with parent | S-azsoi3uw |
| Discord bot token | none stated | "Reset Token" in the portal | not stated | S-jnot5rsp |
| Discord OAuth2 access token | `expires_in` 604800 in the docs' examples | refresh grant, revoke endpoint | per revoke | S-utofkpju |

## Examples
- SNIPPET: roll a Cloudflare API token and check the new value; context: curl against the Cloudflare API with a token that holds `API Tokens Write`; ids and secrets are placeholders; checked: no [DOC S-34drdif4: roll endpoint; S-i7k2yzu3: verify endpoint]
```console
$ curl -X PUT "https://api.cloudflare.com/client/v4/user/tokens/<token-id>/value" \
    --header "Authorization: Bearer <tokens-write-token>"
$ curl "https://api.cloudflare.com/client/v4/user/tokens/verify" \
    --header "Authorization: Bearer <new-token-value>"
```
