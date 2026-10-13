---
topic: auth/shamir-secret-sharing
priority: P3
applies_to: "Shamir secret sharing of a root key or identity among K of N holders: scheme limits and maintained split and combine tools (dsprenkels sss and sss-cli, SLIP-0039, Vault's shamir package, sops key groups)"
retrieved_utc: 2026-10-11
sources: [S-tmotj3si, S-eb3lde4q, S-ujdydznw, S-pidk4hju, S-qt5gzwb2, S-pkor3bz3, S-kanbehag, S-r3t6wvk5, S-bi6fdfos]
status: partial
---

# Shamir secret sharing of a root identity: K of N holders and the tools

## Summary
Shamir's scheme splits a secret into N shares of which any K rebuild it and fewer reveal nothing. It protects confidentiality only: a holder cannot check a share and a corrupt share is not detected unless the tool adds a check. Tools that wrap the split in authenticated encryption or a digest (sss and sss-cli, SLIP-0039) fail loudly on a bad share; Vault's package does not. sops uses the same scheme inside a file, splitting the data key across key groups (`auth/sops-age-recipients.md`).

## Facts
- Shamir's scheme builds a random polynomial whose lowest term is the secret and hands out points on it; with K points the polynomial, and so the secret, is interpolated. [DOC S-tmotj3si]
- Shares cannot be verified by their holders, so a dealer can hand out random strings and nobody learns it until the holders try to combine; the sss README says to use the scheme only if neither dealer nor holders have a reason to corrupt a share. [DOC S-tmotj3si]
- "Textbook" Shamir is safe only for a uniformly random secret (128 bits of entropy) and gives no integrity; the sss high-level API therefore wraps the secret in XSalsa20/Poly1305 under a random key and shares that, so shares are slightly larger than the secret. [DOC S-tmotj3si]
- `sss` (MIT) is written to be side-channel resistant and authenticated; its comparison table lists secrets of up to 64 bytes in the high-level API and bindings for several languages; a longer secret is handled by sharing a random key and encrypting the secret with it. [DOC S-tmotj3si]
- `sss-cli` wraps the library as `secret-share-split -n N -t K` and `secret-share-combine`, reading and writing text lines; it is built with `cargo install --git ... --branch v0.1`, and its shares are longer than the secret because an AEAD wrapper stops tampered shares from combining silently. [DOC S-eb3lde4q]
- Repository state read on 2026-10-11 from the GitHub API: `dsprenkels/sss` last pushed 2025-08-18 and `dsprenkels/sss-cli` last pushed 2025-10-26, neither archived, both MIT. [DOC S-qt5gzwb2, S-pkor3bz3]
- SLIP-0039 splits a master secret of at least 128 bits (a multiple of 16 bits; 128 and 256 must be supported) over GF(256) byte by byte, first encrypting it with a passphrase through a four-round Feistel network built on PBKDF2-HMAC-SHA256. [DOC S-ujdydznw]
- SLIP-0039 is two-level: the secret is split GT-of-G into group shares and each group share T-of-N into member shares, so unequal trust (for example 2 of 4 groups, one group of 3-of-5 friends) needs no one to hold several shares; a group with member threshold 1 should have size 1. [DOC S-ujdydznw]
- Each SLIP-0039 share carries a random 15-bit identifier shared by the set, the thresholds and indices, and an RS1024 checksum that detects any three or fewer word errors; the set's digest (the first four bytes of HMAC-SHA256 under a random key) is stored as one more point, so a wrong or forged set passes the check only with probability 2^-32. [DOC S-ujdydznw]
- A SLIP-0039 passphrase cannot be verified: any passphrase yields some master secret, which the format treats as a feature (plausible deniability) and which also means a typo gives a wrong secret without an error. [DOC S-ujdydznw]
- The SLIP-0039 reference implementation is `trezor/python-shamir-mnemonic` (MIT; last pushed 2024-05-16 on 2026-10-11, not archived); other implementations are listed on the SLIP page. [DOC S-ujdydznw, S-kanbehag]
- Vault's `shamir` package exposes `Split(secret, parts, threshold)` and `Combine(parts)`: parts and threshold each between 2 and 255, threshold at most parts, each share one byte longer than the secret because it carries its x-coordinate. [CODE S-pidk4hju: shamir/shamir.go#Split]
- In that package the polynomial coefficients come from `crypto/rand` and the x-coordinates from a time-seeded `math/rand` permutation; `Combine` checks only that there are at least two parts, of equal length and with distinct x-coordinates, and cannot tell a wrong share from a right one. [CODE S-pidk4hju: shamir/shamir.go#Split, #Combine]
- The file header of that package says MPL-2.0 while the repository's own `LICENSE` is BUSL-1.1 (`prior-art/secret-vault-encryption.md`), so copying the file and depending on the repository are different questions. [DOC S-pidk4hju: SPDX header of shamir/shamir.go]
- sops does not share an identity: it splits the per-file data key and puts one fragment under each key group, so a threshold of groups, each opened by any one of its own keys, is needed to decrypt. [DOC S-r3t6wvk5]
- An age X25519 identity is 32 random bytes, which fits the 256-bit master secret SLIP-0039 and the sss and Vault packages accept, so a root age identity can be split by any of these tools. [DER S-bi6fdfos, S-ujdydznw, S-tmotj3si: identity length against each tool's secret size]
- Splitting the identity and sharing the data key differ in what must happen at use: a split identity has to be recombined on one machine before every decrypt and replacing a holder means new shares of the same identity (or a new identity and re-encryption), while sops key groups never recombine an identity, keep each holder's own key, and change holders with `updatekeys` followed by `rotate`. [DER S-r3t6wvk5, S-tmotj3si: where the secret is reassembled and how a holder is replaced]
- Open: whether any of these tools can issue fresh shares for the same secret with a different K or N without first recombining it. [UNK: no page read states a resharing or proactive refresh operation]

## Reference
| Tool | What is split | Share check | K and N limits | Source |
|---|---|---|---|---|
| `sss` / `sss-cli` | random key that encrypts the secret (AEAD) | yes (AEAD, tamper-resistant) | sss README: at most 255 shares, secrets of 64 bytes, shares of 113 bytes each; the sss-cli README states no limit, and the sss README says sss-cli shares a random key to carry longer secrets, so its shares vary in length | S-tmotj3si, S-eb3lde4q |
| SLIP-0039 (`python-shamir-mnemonic`) | passphrase-encrypted master secret, two levels | yes (RS1024, digest) | 16 groups of 16 members | S-ujdydznw |
| Vault `shamir` package | raw secret bytes | no | 2 to 255 | S-pidk4hju |
| sops `key_groups` | per-file data key | MAC over the file | `shamir_threshold` of the groups | S-r3t6wvk5 |

## Examples
- SNIPPET: split a root secret 3 of 5 and combine three shares with the sss command line tools; context: `secret-share-split` and `secret-share-combine` from sss-cli, input on standard input, shares written one per line; checked: no [DOC S-eb3lde4q: README usage example]
```console
$ secret-share-split -n 5 -t 3 < root-identity.txt > shares.txt
$ head -n 3 shares.txt | secret-share-combine
```
