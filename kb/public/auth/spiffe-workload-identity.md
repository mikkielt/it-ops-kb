---
topic: auth/spiffe-workload-identity
priority: P3
applies_to: "SPIFFE standards (spiffe/spiffe@f97c46df), SPIRE 1.15.3, Kubernetes projected ServiceAccount tokens (stable since v1.20; kubernetes/website@e91eff3b): workload identity for agents outside Entra"
retrieved_utc: 2026-10-15
sources: [S-xc5uusz2, S-goybn4yq, S-c5bctcpw, S-yp5feoc6, S-zwfvgfuh, S-i256dvri, S-2vob2pwv, S-b6gp3bv7, S-ugw52imj, S-y3sapuqy, S-fpedei7j, S-qatk6hho, S-2eo2ncgf, S-322kmkky]
status: complete
---

# Workload identity outside Entra: SPIFFE, SPIRE and Kubernetes projected service account tokens

## Summary
A SPIFFE ID is a `spiffe://<trust domain>/<path>` URI that names a workload; an SVID is the signed document (an X.509 certificate or a JWT) that carries it, valid when an authority of that trust domain signed it. SPIRE, a CNCF graduated project, issues SVIDs only after two attestations: the agent proves its node to the server, then the agent inspects the calling process (kernel, kubelet) and matches its selectors against registration entries. SVIDs are short-lived (SPIRE defaults: X.509-SVID 1 hour, JWT-SVID 5 minutes) and the agent rotates X.509-SVIDs at half their life, streaming each new one to the workload through the Workload API. Verifiers check X.509-SVIDs by RFC 5280 path validation against the trust bundle plus leaf checks, and JWT-SVIDs by signature, `aud` and `exp` against the bundle of the subject's trust domain. Kubernetes gives a pod a comparable identity of its own: a projected ServiceAccount token is a JWT with a chosen audience and lifetime (default 1 hour, at least 10 minutes), bound to the pod, which the kubelet refreshes before it expires.

## Facts

### SPIFFE ID and SVID
- A SPIFFE ID is an RFC 3986 URI whose authority is the trust domain name and whose path names the workload; the scheme must be `spiffe`, the trust domain non-empty, and no query or fragment is allowed. [DOC S-xc5uusz2]
- The trust domain is the trust root of a system (an organisation, environment or department running its own SPIFFE infrastructure); identities from one trust domain fail validation in another unless the two federate. [DOC S-xc5uusz2]
- The path's meaning is left to the administrator; it may mirror a platform identity such as a Kubernetes service account or stay opaque, with metadata held in a separate registry. [DOC S-xc5uusz2]
- Implementations must accept SPIFFE IDs up to 2048 bytes and should not generate longer ones; scheme and trust domain are case-insensitive, the path case-sensitive. [DOC S-xc5uusz2]
- An SVID is how a workload presents its SPIFFE ID to a resource or caller; it is valid when signed by an authority within the SPIFFE ID's trust domain, and it carries at least a SPIFFE ID and a valid signature. [DOC S-xc5uusz2]
- An SVID is not a document type of its own: the standards define X.509-SVID, JWT-SVID and WIT-SVID encodings; the Workload API makes X.509-SVID and JWT-SVID mandatory and WIT-SVID optional. [DOC S-xc5uusz2, S-yp5feoc6]
- The Workload API does not authenticate its clients directly; the Workload Endpoint implementation identifies the caller out of band and serves the identities that caller is entitled to. [DOC S-yp5feoc6]

### SPIRE attestation
- SPIRE is a CNCF graduated project and one implementation of the SPIFFE APIs; it performs node and workload attestation to issue SVIDs to workloads and to verify the SVIDs of other workloads. [DOC S-fpedei7j]
- A SPIRE deployment is one SPIRE Server, the signing authority of its trust domain that holds the registration entries and signing keys, and a SPIRE Agent on every node that runs an identified workload. [DOC S-i256dvri]
- A registration entry maps a SPIFFE ID to selectors, the properties a workload must have to be issued that identity. [DOC S-i256dvri]
- Attestation runs in two phases: node attestation verifies the node the agent runs on, then workload attestation verifies the process on that node; only agents take part in workload attestation. [DOC S-i256dvri]
- In node attestation the agent presents proof of its node (for example a cloud instance identity document) over TLS authenticated by its bootstrap bundle; the server validates it, issues the agent its own SVID, and the agent then uses that SVID as its mTLS client certificate. [DOC S-i256dvri]
- The node attestors SPIRE ships cover AWS (instance identity document), Azure (IMDS and managed identity tokens), GCP (instance identity token), Kubernetes (projected service account tokens), TPM DevID, SSH and X.509 certificates, and server-generated join tokens. [DOC S-b6gp3bv7]
- A SPIRE join token is a pre-shared key the server generates to verify an agent at start, and it expires immediately after use. [DOC S-i256dvri]
- `spire-server token generate` makes a join token whose `-ttl` defaults to 600 seconds. [DOC S-2vob2pwv]
- The `k8s_psat` server node attestor validates the agent's projected service account token through the Kubernetes TokenReview API, with audience `spire-server` by default, and can reject tokens of service accounts outside an allow list. [DOC S-ugw52imj]
- In workload attestation the agent gets the caller's process ID from the kernel, its workload attestors look up more about that process (for Kubernetes, from the local kubelet), and the agent compares the resulting selectors with registration entries before returning the cached SVID. [DOC S-i256dvri]
- The `k8s` workload attestor finds the pod from the process's cgroup membership and queries the kubelet; its selectors include `k8s:ns`, `k8s:sa`, `k8s:pod-label`, `k8s:container-image` and `k8s:pod-uid`. [DOC S-y3sapuqy]
- SPIRE Agent can run as a Windows service and then serves the Workload API on a named pipe (the `experimental` setting `named_pipe_name`, default `\spire-agent\public\api`); the workload attestors it lists are docker, k8s, unix, systemd and slurm, none of them Windows-specific. [DOC S-b6gp3bv7]

### Rotation and verification of SVIDs
- SPIRE Server defaults: `default_x509_svid_ttl` 1h, `default_jwt_svid_ttl` 5m, `ca_ttl` 24h, `agent_ttl` equal to the X.509-SVID TTL; a registration entry can override the SVID TTLs. [DOC S-2vob2pwv]
- The agent rotates an X.509-SVID at half its lifetime by default; with `availability_target` (at least 24h) it rotates when the remaining lifetime reaches that target, which does not apply to JWT-SVIDs. [DOC S-b6gp3bv7]
- The Workload API streams responses: each message carries the full set of SVIDs and bundles, sent again on events such as an SVID rotation, and a bundle missing from a message is to be unloaded by the client. [DOC S-yp5feoc6]
- SPIRE Server rotates its signing authorities in steps: `localauthority x509 prepare` (or `jwt prepare`) puts a new key into the bundle, `activate` makes it sign, and the old one can then be tainted and revoked. [DOC S-2vob2pwv]
- An X.509-SVID carries exactly one URI SAN, its SPIFFE ID; leaf SVIDs have `cA` false, must set `digitalSignature` and must not set `keyCertSign` or `cRLSign`. [DOC S-goybn4yq]
- Validating an X.509-SVID is RFC 5280 path validation against the trust bundle plus checks that it is a leaf (`cA` false, no `keyCertSign` or `cRLSign`), that the scheme is `spiffe` and that the ID has a path. [DOC S-goybn4yq]
- A JWT-SVID is a JWS in compact serialization: `sub` is the SPIFFE ID, `aud` and `exp` are required, and validators reject a token without them or whose audience does not name the validator. [DOC S-c5bctcpw]
- JWT-SVIDs are bearer tokens open to replay: a token with several audiences can be replayed by one audience to another, so the standard advises one audience, a short `exp` and a confidential channel. [DOC S-c5bctcpw]
- A JWT-SVID is validated with the JWT bundle of the subject's trust domain; with no bundle for that trust domain the token is untrusted. [DOC S-yp5feoc6]
- A SPIFFE bundle is a JWK set whose keys are marked `x509-svid` or `jwt-svid`; `spiffe_refresh_hint` tells consumers how often to re-fetch it, which bounds how fast keys are rotated or withdrawn. [DOC S-zwfvgfuh, S-goybn4yq, S-c5bctcpw]

### Kubernetes projected service account tokens
- ServiceAccount token volume projection is stable since Kubernetes v1.20; the kubelet requests a token through the TokenRequest API and projects it into the pod with the audience and validity the pod asks for. [DOC S-qatk6hho]
- The projected token is a JWT whose claims include `aud`, `exp`, `iss` (the first `--service-account-issuer` value), `sub` `system:serviceaccount:<namespace>:<name>` and a `kubernetes.io` claim naming the pod, node and service account. [DOC S-qatk6hho]
- `audience` names the token's intended recipient, who should reject a token not addressed to it, and defaults to the API server; `expirationSeconds` defaults to 1 hour and must be at least 600 seconds. [DOC S-2eo2ncgf]
- `--service-account-max-token-expiration` on the API server caps the lifetime a pod may request. [DOC S-2eo2ncgf]
- The kubelet refreshes the token once it is older than 80% of its TTL or older than 24 hours; the application must reload the file, for example every 5 minutes. [DOC S-qatk6hho]
- TokenRequest tokens are bound tokens: they become invalid against the API when the pod or service account they are bound to is deleted. [DOC S-qatk6hho, S-322kmkky]
- Kubernetes recommends verifying a service account token with the TokenReview API, which fails as soon as the bound pod is deleted; OIDC discovery validation keeps accepting it until `exp`. [DOC S-322kmkky]
- An application should name the audience it accepts and check that the token's audiences match it, so the token can be used nowhere else. [DOC S-322kmkky]
- With the issuer discovery feature (stable since v1.21) the cluster serves `{issuer}/.well-known/openid-configuration` so external relying parties can validate its tokens. [DOC S-qatk6hho]

### How it fits
- An agent pod can get a per-call identity with no stored secret either way: a projected service account token for an audience it names, or a JWT-SVID for that audience from the SPIRE agent; both are short-lived and audience-bound. [DER S-2eo2ncgf, S-qatk6hho, S-c5bctcpw, S-yp5feoc6]
- SPIFFE adds what the bare service account token lacks: mutual TLS between services with X.509-SVIDs, identity across clusters and non-Kubernetes hosts in one trust domain, and federation between trust domains. [DER S-xc5uusz2, S-goybn4yq, S-i256dvri]
- A service that receives agent tokens should accept one audience, its own, and prefer TokenReview over offline OIDC checks where deleting the agent's pod must cut its access at once. [DER S-322kmkky, S-c5bctcpw]
- Unlike a kubeadm bootstrap token or a GitLab runner token (`auth/enrolment-tokens.md`), a SPIRE join token is burnt on first use, so it fits one-time enrolment of a host. [DER S-i256dvri: join tokens expire immediately after use]
- To reach Entra-protected resources the same projected token is exchanged through Entra workload identity federation (`arch/workload-identity-onprem-k8s.md`); SPIFFE identities serve services that trust the SPIFFE bundle. [DER S-qatk6hho, S-yp5feoc6]

## Reference
| Question | Answer | Source |
|---|---|---|
| SPIFFE ID form | `spiffe://<trust-domain>/<path>`, no query or fragment, up to 2048 bytes | S-xc5uusz2 |
| SVID formats | X.509-SVID, JWT-SVID (mandatory in the Workload API), WIT-SVID (optional) | S-xc5uusz2, S-yp5feoc6 |
| SPIRE default TTLs | X.509-SVID 1h, JWT-SVID 5m, CA 24h, join token 600 s | S-2vob2pwv |
| X.509-SVID rotation | at 1/2 of lifetime, or at `availability_target` | S-b6gp3bv7 |
| Projected token lifetime | default 1h, at least 600 s, capped by `--service-account-max-token-expiration` | S-2eo2ncgf |
| Projected token refresh | older than 80% of TTL or 24h | S-qatk6hho |
| Verify a projected token | TokenReview (recommended) or OIDC discovery | S-322kmkky |

Related: `arch/workload-identity-onprem-k8s.md` (Entra federation of the same tokens), `auth/workload-identity.md`, `auth/enrolment-tokens.md`.

## Examples
- SNIPPET: a pod that projects a service account token for one audience with a one-hour life; context: Kubernetes v1.20 or later, names are placeholders; checked: no [DOC S-2eo2ncgf: `serviceAccountToken` with `audience`, `expirationSeconds`, `path`]
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: agent-runner
spec:
  serviceAccountName: agent-sa
  containers:
  - name: agent
    image: registry.corp.example.com/agent:1.0
    volumeMounts:
    - name: agent-token
      mountPath: /var/run/secrets/tokens
      readOnly: true
  volumes:
  - name: agent-token
    projected:
      sources:
      - serviceAccountToken:
          audience: inventory-api
          expirationSeconds: 3600
          path: agent-token
```
