---
topic: auth/http-message-signatures
priority: P3
applies_to: "Ed25519 request signing over HTTP with RFC 9421 HTTP Message Signatures: created, expires, nonce and replay; relation of an Ed25519 key to an age X25519 identity"
retrieved_utc: 2026-10-11
sources: [S-vm4x5dhi, S-s3lqlvdi, S-n3swpr6x, S-xzzrbowg, S-bi6fdfos, S-ax3gmu7j, S-r3t6wvk5]
status: partial
---

# Ed25519 request signing over HTTP (RFC 9421) and its relation to age keys

## Summary
RFC 9421 signs chosen parts of an HTTP message and carries the result in two fields, `Signature-Input` and `Signature`; `ed25519` is a registered algorithm. Replay defence is not built in: the signer supplies `created`, `expires` and a `nonce`, and the verifier decides the window and keeps the nonces. An age X25519 identity is not a signing key: the documented conversion runs from Ed25519 to X25519, and the X25519 public key does not determine one Ed25519 public key.

## Facts

### The signature
- A signature uses two fields, `Signature-Input` (a Dictionary Structured Field naming the covered components and the parameters) and `Signature`; both MUST be present, and several labelled signatures may share a message. [DOC S-vm4x5dhi]
- The signature parameters are `created` (Unix timestamp, integer seconds, RECOMMENDED), `expires` (integer), `nonce` (a random unique string), `alg`, `keyid` and `tag`; they are serialized into `@signature-params`, which is always the last line of the signature base. [DOC S-vm4x5dhi]
- Request components include `@method`, `@target-uri`, `@authority`, `@path`, `@query` and header fields; a body is covered by signing a `Content-Digest` header that carries its digest. [DOC S-vm4x5dhi]
- The `ed25519` algorithm applies Ed25519 from RFC 8032 section 5.1.6 to the signature base as the message, with no prehash, and the signature is the 64-octet concatenation of R and S; `alg` may name it at run time. [DOC S-vm4x5dhi]
- The RFC registers other algorithms as well (RSASSA-PSS, ECDSA P-256 and P-384, HMAC-SHA256, JWS); a verifier may forbid the `alg` parameter when the key already fixes the algorithm. [DOC S-vm4x5dhi]

### Time, nonce and replay
- The RFC states only baseline checks; examples of application requirements it lists are a maximum signature age counted from `created`, rejecting a signature past `expires`, requiring a set of covered headers, enforcing nonce uniqueness and requiring an application `tag`. [DOC S-vm4x5dhi]
- `expires` is the signer's hint: a verifier can always reject a signature before it. [DOC S-vm4x5dhi]
- Against replay the RFC advises covering enough of the message to tell it from others, using `nonce` so the verifier can detect a repeated value, and giving `created` and `expires` to limit a captured signature's use. [DOC S-vm4x5dhi]
- A verifier that wants a fresh signature can send `Accept-Signature` with a new `nonce`; a replaying attacker cannot produce a signature over the chosen nonce. [DOC S-vm4x5dhi]
- Time-window checks should use `created`, not the `Date` header, and an application may bound the skew between the two. [DOC S-vm4x5dhi]
- The RFC sets no number for the window, the clock skew or the nonce store; all are application policy. [DER S-vm4x5dhi: they appear only among the "application requirements" examples]
- A nonce check needs state on the verifier, but only for the accepted time window: a nonce older than the maximum age is already rejected by the time check, so entries can be dropped after that age. [DER S-vm4x5dhi: max age and nonce uniqueness are both verifier requirements]
- Signed components decide what a replay can change: a signature that covers no body digest, or no `@method` and `@path`, can be attached to another request. [DOC S-vm4x5dhi]

### Ed25519 and an age X25519 identity
- An age X25519 identity is 32 bytes from a CSPRNG, and its recipient is `X25519(identity, basepoint)`; an age identity file or recipient list can also hold ssh keys, and an `ssh-ed25519` public key is accepted as a recipient. [DOC S-bi6fdfos, S-ax3gmu7j]
- RFC 7748 gives the birational map between the Montgomery curve of X25519 and the twisted Edwards curve of Ed25519: `u = (1+y)/(1-y)` and `(x, y) = (sqrt(-486664)*u/v, (u-1)/(u+1))`. [DOC S-s3lqlvdi]
- The age Go code converts the other way for ssh keys: `ed25519PublicKeyToCurve25519` takes the Ed25519 point to its Montgomery form (`BytesMontgomery`) and the private key to a Curve25519 scalar, then the recipient stanza mixes in an HKDF tweak bound to the ssh key. [CODE S-xzzrbowg: agessh/agessh.go#ed25519PublicKeyToCurve25519, #Ed25519Recipient.Wrap]
- libsodium documents the same direction: `crypto_sign_ed25519_pk_to_curve25519` and `crypto_sign_ed25519_sk_to_curve25519` (the latter reads only the 32-byte seed) so one pair can sign and encrypt, while still recommending distinct keys for signing and encryption. [DOC S-n3swpr6x]
- The map's `u` depends only on `y`, so the sign of the Edwards `x` coordinate is lost: two Ed25519 public keys map to one X25519 public key, and an age recipient does not identify one Ed25519 public key. [DER S-s3lqlvdi: u = (1+y)/(1-y) has no x]
- An Ed25519 signing key is made from a 32-byte seed by hashing; the scalar of an X25519 identity alone has no seed or nonce prefix, so no standard operation turns an age identity into the signing key that matches its recipient. [DER S-n3swpr6x, S-bi6fdfos: libsodium converts from the 32-byte seed; an age identity is a bare 32-byte scalar source]
- Two ways remain: keep the Ed25519 key as the root and let age use its converted X25519 form (age and sops read `ssh-ed25519` identities), or give the signer its own key; using the age identity's 32 bytes as an Ed25519 seed gives a valid but unrelated key pair and puts one secret under two algorithms. [DER S-xzzrbowg, S-r3t6wvk5, S-n3swpr6x: ssh-ed25519 identities are accepted; libsodium advises distinct keys]
- Open: no source read prescribes a derivation of an Ed25519 signing key from an age identity (for example HKDF with a domain-separation label). [UNK: not stated on the age, libsodium or RFC pages read]

## Reference
| Parameter | Type | Role in replay defence | Verifier action |
|---|---|---|---|
| `created` | integer seconds | start of the time window | reject if older than the maximum age or in the future by more than the skew |
| `expires` | integer seconds | signer's end of validity | reject after it (may reject earlier) |
| `nonce` | string | single-use marker | store until the window ends, reject a repeat |
| `keyid` | string | selects the verification key | must resolve to the expected key |
| `tag` | string | application scope | require the application's value |

Verifier actions in the last column are application policy; the RFC lists them only as examples (S-vm4x5dhi).

## Examples
- SNIPPET: the two fields of an Ed25519-signed request with a time window and a nonce; context: placeholders for key id, nonce and signature bytes; checked: no [DOC S-vm4x5dhi: field syntax and parameters]
```http
POST /v1/sites/PL-SRV-0042/jobs HTTP/1.1
Host: api.corp.example.com
Content-Digest: sha-256=:<base64-digest>:
Signature-Input: sig1=("@method" "@authority" "@path" "content-digest");created=1760000000;expires=1760000060;nonce="<random-nonce>";keyid="<key-id>";alg="ed25519"
Signature: sig1=:<base64-64-byte-signature>:
```
