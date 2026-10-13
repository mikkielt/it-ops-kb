---
topic: auth/http-message-signatures
priority: P3
applies_to: "Ed25519 request signing over HTTP with RFC 9421 HTTP Message Signatures: created, expires, nonce and replay; relation of an Ed25519 key to an age X25519 identity, including XEdDSA signing with the X25519 identity itself"
retrieved_utc: 2026-10-13
sources: [S-vm4x5dhi, S-s3lqlvdi, S-n3swpr6x, S-xzzrbowg, S-bi6fdfos, S-ax3gmu7j, S-r3t6wvk5, S-lzpaeug7]
status: partial
---

# Ed25519 request signing over HTTP (RFC 9421) and its relation to age keys

## Summary
RFC 9421 signs chosen parts of an HTTP message and carries the result in two fields, `Signature-Input` and `Signature`; `ed25519` is a registered algorithm. Replay defence is not built in: the signer supplies `created`, `expires` and a `nonce`, and the verifier decides the window and keeps the nonces. Ed25519 key generation cannot produce the key that matches an age X25519 recipient, and the conversions age and libsodium document run from Ed25519 to X25519; XEdDSA (Signal's specification) is the published construction that signs with an X25519 private key, by fixing the Ed25519 sign bit at zero, at the price of randomized signatures, slower signing and one key under two protocols.

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
- The map's `u` depends only on `y`, so the sign of the Edwards `x` coordinate is lost: two Ed25519 public keys map to one X25519 public key, and an age recipient alone does not identify one Ed25519 public key unless a convention picks the sign. [DER S-s3lqlvdi: u = (1+y)/(1-y) has no x]
- An Ed25519 signing key is made from a 32-byte seed by hashing, so Ed25519 key generation cannot produce the key whose converted public key is an age recipient; the construction that starts from the X25519 scalar is XEdDSA (next facts). [DER S-n3swpr6x, S-bi6fdfos, S-lzpaeug7: libsodium converts from the seed; an age identity is a bare X25519 scalar]
- Signal's XEdDSA specification (Revision 1, 2016-10-20) creates EdDSA-compatible signatures with the private and public key formats of X25519, and says it "enables use of a single key pair format for both elliptic curve Diffie-Hellman and signatures"; XEd25519 is its Curve25519 instance. [DOC S-lzpaeug7]
- The signer's input is a Montgomery private key `k`, which the specification allows "to be any scalar"; the verifier's input is the Montgomery `u` coordinate. `calculate_key_pair` multiplies `k` by the Edwards base point and negates the scalar when needed so the public key's sign bit is zero, and verification forces that bit to zero because `u` carries no `v` to tell the two apart. [DOC S-lzpaeug7]
- An age identity can therefore sign with XEdDSA: the identity is the X25519 private key (`X25519(identity, basepoint)` from RFC 7748), the recipient's `u` is what `xeddsa_verify` takes, and one 32-byte public string serves as age recipient and as verification key. [DER S-lzpaeug7, S-bi6fdfos: the formats XEdDSA starts from are the ones age's X25519 identity and recipient use]
- XEd25519 signatures "are valid Ed25519 signatures [1] and vice versa, provided the public keys are converted with the birational map"; XEdDSA fixes its verification steps (it rejects `s` with excess bits and checks without cofactor multiplication), so it may accept or reject invalid signatures differently from some Ed25519 implementations. [DOC S-lzpaeug7]
- XEdDSA signatures are randomized, not deterministic: the caller passes a new random 64-byte value `Z` for each signature, and the nonce is `hash1(a || M || Z)`, which keeps the long-term key and the message in the hash; the specification shows that one nonce used for two messages reveals the private key. [DOC S-lzpaeug7]
- Calling `calculate_key_pair` for every signature "roughly doubles signing time compared to EdDSA"; a signer may cache the non-secret point `E`. The specification also asks for constant-time signing and names `calculate_key_pair` as needing care for its conditional branching. [DOC S-lzpaeug7]
- The specification calls it safe to use one key pair for XEdDSA and VXEdDSA signatures, but for signatures plus Diffie-Hellman under one key it says this is "a complicated topic requiring careful analysis" and outside its scope. [DOC S-lzpaeug7]
- Trade-off of signing with the age identity through XEdDSA, against a separate Ed25519 key: one secret and one public string instead of two keys to store and bind, but a RNG needed at every signature, about twice the signing time, a key that both decrypts and signs (one compromise exposes both, and the specification leaves their joint security out of scope, where libsodium advises distinct keys), and a verifier that needs the converted Edwards key and XEdDSA's verification rules. [DER S-lzpaeug7, S-n3swpr6x]
- A separate Ed25519 key signs deterministically under RFC 8032, fits the RFC 9421 `ed25519` algorithm with no key conversion, and keeps signing apart from decryption; it costs a second key to store, rotate and bind to the age recipient. [DER S-vm4x5dhi, S-n3swpr6x, S-lzpaeug7: XEdDSA is not among the RFC's registered algorithms; libsodium advises distinct keys]
- Routes for a signature tied to an age identity: sign with the identity through XEdDSA, keep an Ed25519 key as the root and let age use its converted X25519 form (age and sops read `ssh-ed25519` identities), or give the signer its own key; using the age identity's 32 bytes as an Ed25519 seed gives a valid but unrelated key pair and puts one secret under two algorithms. [DER S-lzpaeug7, S-xzzrbowg, S-r3t6wvk5, S-n3swpr6x]
- Open: the XEdDSA page does not say how the 32 bytes of an X25519 private key string become the scalar `k` (whether RFC 7748 clamping is applied first), names no age binding or library, and no age, sops or libsodium page read mentions XEdDSA. [UNK: not stated on the pages read]
- Open: no source read prescribes a key-separated derivation of an Ed25519 signing key from an age identity (for example HKDF with a domain-separation label); XEdDSA signs with the identity itself instead. [UNK: not stated on the age, libsodium, RFC 7748 or XEdDSA pages read]

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
