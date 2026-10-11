---
topic: auth/enrolment-tokens
priority: P3
applies_to: "Short-lived enrolment (bootstrap) tokens for joining a host to a service: Kubernetes bootstrap tokens and kubeadm token TTL, with GitLab runner authentication tokens for comparison"
retrieved_utc: 2026-10-11
sources: [S-gblkbdxn, S-x6ikrxdb, S-ionrxcnv, S-fsqu2grq, S-ytnvr75r, S-ssfsxd2n, S-5ohrrj7d]
status: complete
---

# Short-lived enrolment tokens: Kubernetes bootstrap tokens and GitLab runner tokens

## Summary
An enrolment token lets a new machine prove it was invited. Kubernetes bootstrap tokens are expiring, scoped bearer credentials with a default 24-hour life; GitLab runner authentication tokens expire between 5 minutes and 15 days when set. Neither is single-use by design: a token works for every join until it expires or is deleted. A one-time property has to come from minting one token per host with a short TTL and deleting it after the join.

## Facts

### Kubernetes bootstrap tokens
- A bootstrap token is a Secret of type `bootstrap.kubernetes.io/token` in `kube-system`, named `bootstrap-token-<token id>`; the API server's Bootstrap Authenticator reads it and the TokenCleaner controller removes expired ones. [DOC S-gblkbdxn]
- The token is `[a-z0-9]{6}.[a-z0-9]{16}`: the first part is a public token ID, the second the secret used for authentication. [DOC S-gblkbdxn]
- With `--enable-bootstrap-token-auth` the API server accepts the token as a bearer credential, authenticating as `system:bootstrap:<token id>` in the group `system:bootstrappers` plus any extra groups in the Secret, which must start with `system:bootstrappers:`. [DOC S-gblkbdxn]
- The Secret's `expiration` field is optional and an absolute RFC 3339 UTC time; an expired token is rejected for authentication and ignored for signing, and the `tokencleaner` controller must be enabled to delete it. [DOC S-gblkbdxn]
- `usage-bootstrap-authentication` and `usage-bootstrap-signing` limit what a token may be used for: authenticating requests, or signing the `cluster-info` ConfigMap. [DOC S-gblkbdxn]
- The signed `cluster-info` ConfigMap in `kube-public` carries a detached JWS (HS256 with the token secret) over a kubeconfig that holds the cluster CA, so a joining node can trust the API server before it has a credential; users must check that HS256 is the algorithm. [DOC S-gblkbdxn]
- The page warns that any holder of a bootstrap token can create a valid signature for it, so sharing one token among many clients lets a compromised client impersonate the cluster to another. [DOC S-gblkbdxn]
- `kubeadm init` creates an initial token with a 24-hour TTL, and `kubeadm token` creates, lists and deletes others. [DOC S-ionrxcnv]
- `kubeadm token create` takes `--ttl` (default 24h0m0s; `0` means the token never expires), `--usages` (default `signing,authentication`), `--groups` (default `system:bootstrappers:kubeadm:default-node-token`), `--description` and `--print-join-command`. [DOC S-x6ikrxdb]
- The documented token fields are an id, a secret, an optional expiration, usages and groups; none counts uses, so a token admits any number of joins until it expires or is deleted. [DER S-gblkbdxn, S-x6ikrxdb: the field and flag lists contain no use limit]

### GitLab runner authentication tokens
- A runner created with `POST /user/runners` returns a `glrt-` authentication token that cannot be fetched again; `token_expires_at` (5 minutes to 15 days ahead, Premium, within any instance, group or project limit) applies to the first token only. [DOC S-fsqu2grq]
- The same authentication token registered on several host machines reuses one runner configuration, so it is not consumed by registration. [DOC S-ssfsxd2n]
- `POST /runners/reset_authentication_token` and `POST /runners/:id/reset_authentication_token` return a new token and its `token_expires_at`; `POST /runners/verify` answers `200` or `403` for a token. [DOC S-ytnvr75r]
- Runner registration tokens and several registration arguments are deprecated for removal in GitLab 20.0; the authentication token stays on the runner machine and anyone who reads `config.toml` can clone the runner. [DOC S-ssfsxd2n, S-5ohrrj7d]

### Using them for a small fleet
- Neither mechanism gives single-use enrolment; the closest is one token per host with the shortest workable TTL (kubeadm `--ttl 5m`; GitLab `token_expires_at` at least 5 minutes ahead), deleted or reset once the host has joined. [DER S-x6ikrxdb, S-fsqu2grq, S-ssfsxd2n: tokens are reusable until expiry; the TTL floor on the GitLab side]
- A true one-time token is something the enrolling service enforces: it records the token's id as spent on first use and refuses a second presentation. [DER S-gblkbdxn, S-ssfsxd2n: neither issuer burns a token on use]
- A token that doubles as the long-term credential (the GitLab runner token) is a different design from one that only buys a first request, after which the host gets its own key; the Kubernetes token authenticates as a group with limited rights, and the node then gets certificates. [DER S-gblkbdxn: tokens authenticate as `system:bootstrappers`; the page treats bootstrapping, not steady state]

## Reference
| Property | Kubernetes bootstrap token | GitLab runner authentication token |
|---|---|---|
| Form | `abcdef.0123456789abcdef` (id.secret) | `glrt-...` |
| Lifetime control | `expiration` field; kubeadm `--ttl` (default 24h, 0 = never) | `token_expires_at`, 5 minutes to 15 days (Premium) |
| Single use | no | no |
| Revocation | delete the Secret or `kubeadm token delete` | `reset_authentication_token`, `DELETE /runners/:id` |
| Rights | `system:bootstrappers` (+ extra groups) | authenticates the runner only; jobs run with the job token |
| Source | S-gblkbdxn, S-x6ikrxdb | S-fsqu2grq, S-ytnvr75r |

## Examples
- SNIPPET: mint one short-lived join token for one host and print the join command; context: kubeadm on a control-plane node, host id is a placeholder; checked: no [DOC S-x6ikrxdb: `--ttl`, `--description`, `--print-join-command`]
```console
$ kubeadm token create --ttl 15m --description "join PL-SRV-0042" --print-join-command
$ kubeadm token delete <token-id>
```
