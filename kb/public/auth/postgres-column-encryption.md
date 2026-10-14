---
topic: auth/postgres-column-encryption
priority: P3
applies_to: "Envelope encryption of PostgreSQL columns with per-site data keys (pgcrypto or client side) and blind indexes (keyed HMAC under a separate key) with their leakage"
retrieved_utc: 2026-10-14
sources: [S-byvcl63n, S-alffetzh, S-yvalenhr, S-qt7piebc, S-rqc6efd7, S-r3t6wvk5, S-rxmbolsc]
status: partial
---

# Envelope encryption of Postgres columns, per-site data keys and blind indexes

## Summary
Encrypting a column in PostgreSQL protects against a stolen disk or backup, not against a server administrator, because pgcrypto runs inside the server and sees both key and plaintext. Envelope encryption keeps one data key per scope (here per site, which departs from Google's advice of a new data key per write and never one key for two users), wraps it under a key that stays outside the database, and rotates the wrapping key without touching the rows. A blind index makes an encrypted column searchable for equality by storing a truncated keyed hash; it leaks which rows are equal and how often, and the leak is bounded by the truncation. Extends `auth/key-management-options.md` and `prior-art/secret-vault-encryption.md`.

## Facts

### What pgcrypto does and does not protect
- PostgreSQL's own encryption page names `pgcrypto` for storing certain fields encrypted: the client supplies the decryption key, the data is decrypted on the server and then sent, and for that moment the plaintext and key can be read by someone with complete access to the server such as the system administrator. [DOC S-byvcl63n]
- If the server's administrator cannot be trusted, the same page says the client must encrypt the data so unencrypted data never appears on the database server. [DOC S-byvcl63n]
- All pgcrypto functions run inside the database server, so data and passwords move between pgcrypto and the client in clear text; the page requires a local or SSL connection and trust in both the system and database administrator. [DOC S-alffetzh]
- The implementation does not resist side-channel attacks (decryption time varies among ciphertexts of one size), and every function returns NULL when any argument is NULL, which the page calls a security risk on careless use. [DOC S-alffetzh]
- The PGP functions `pgp_sym_encrypt` and `pgp_pub_encrypt` (and `_bytea` forms) take a password or key and options such as `cipher-algo=aes256`; the symmetric one derives its key from the password with a string-to-key function that is purposely slow and uses a random salt. [DOC S-alffetzh]
- The raw `encrypt` and `decrypt` functions use the supplied key directly as the cipher key, give no integrity check, leave IV handling to the caller and are discouraged; `ecb` mode is for testing only. [DOC S-alffetzh]
- `hmac(data, key, type)` computes a keyed hash that can be recalculated only with the key; `gen_random_bytes(count)` returns random bytes for a key. [DOC S-alffetzh]
- pgcrypto's PGP code has no signing and no several-subkey support, and the page says not to use regular GPG keys with it. [DOC S-alffetzh]
- The `ignore-cipher-failure` decryption option is documented as dangerous: it restores the pre-fix behavior for messages encrypted while the cipher was unavailable, and such faulty messages decrypt without the correct key. [DOC S-alffetzh]

### Envelope encryption and per-site keys
- In envelope encryption the key that encrypts data is a data encryption key (DEK) and a key encryption key (KEK) wraps (encrypts) the DEK; the encrypted data and the wrapped DEK are stored together and the plaintext DEK is not. [DOC S-yvalenhr]
- Google's practices for DEKs: generate them locally, always keep them encrypted at rest, store them near the data they encrypt, use a new DEK for each write so DEKs need no rotation, and never use one DEK for data of two different users. [DOC S-yvalenhr]
- Practices for KEKs: store them centrally, choose the DEK granularity by use case (one KEK may wrap many DEKs), and rotate them regularly and after a suspected incident; fewer KEKs than DEKs keeps the central key store small. [DOC S-yvalenhr]
- Decryption retrieves the data and the wrapped DEK, asks the KEK holder to unwrap the DEK, and decrypts locally; in that design the KEK never leaves the key service. [DOC S-yvalenhr]
- A per-site layout follows, and it departs from Google's DEK practices (departure and costs in the next facts): one DEK per site, reused across the site's writes and shared by its users, stored wrapped in a key table beside the site's rows with the id of the KEK that wrapped it, and a ciphertext column that names its DEK; rotating the KEK means re-wrapping the site keys, while rotating a site's DEK means re-encrypting that site's rows. [DER S-yvalenhr: DEK per scope wrapped by a KEK, stored near the data; KEK rotation affects only wrapped DEKs]
- The per-site layout departs from both of Google's DEK practices: one DEK is reused for every write of the site (Google: a new DEK each write) and is shared by all of the site's users (Google: not the same DEK for data from two different users); the page names no reason for either practice beyond "no need to rotate", so the layout is this kb's design choice, not a variant Google describes. [DER S-yvalenhr: the two DEK practices against the per-site layout]
- What the reuse costs, first: a new DEK per write is what makes DEK rotation unnecessary on Google's page, so a reused site DEK has to be rotated, and every rotation re-encrypts all of the site's rows; the cost grows with the site's data. [DER S-yvalenhr: "you don't need to rotate the DEKs" follows from a new DEK per write]
- What the reuse costs, second: one wrapped DEK unwrapped once opens all of a site's users' rows, where Google's rule keeps one unwrap from exposing two users; and a single user's rows cannot be made unreadable alone by destroying a key, only by re-encrypting the site's rows under a new DEK. [DER S-yvalenhr: DEK scope equals the set of rows one key opens]
- NIST SP 800-38D (November 2007) limits one GCM key: for random IVs, and for deterministic IVs of a length other than 96 bits, the total number of invocations of the authenticated encryption function "shall not exceed 2^32, including all IV lengths and all instances of the authenticated encryption function with the given key". [DOC S-rxmbolsc]
- The same document says that across all instances with one key "if even one IV is ever repeated", the implementation "may be vulnerable to the forgery attacks"; it is a uniqueness rule on the key's whole life. [DOC S-rxmbolsc]
- What the reuse costs, third: with AES-GCM column ciphertext, a site DEK reused for all of the site's writes counts every write of every user against the one key's 2^32 limit and its no-repeated-IV rule, so the writers need random IVs counted against the limit or one shared counter, where a DEK per write is invoked once; the pages read do not say the limit applies to pgcrypto's PGP functions. [DER S-rxmbolsc: the key limit and the IV uniqueness rule applied to a DEK shared by all writes]
- Where the KEK or DEK passes through SQL arguments to pgcrypto, the database server and its administrator see it, so an untrusted server needs wrapping and column encryption in the application with only ciphertext and wrapped keys in the database. [DER S-byvcl63n, S-alffetzh: key and plaintext are present on the server during pgcrypto calls]
- A KEK that is an age identity or a sops-managed file is a file-level KEK with the rotation properties in `auth/sops-age-recipients.md` (no revocation of past commits), not a service that can deny an unwrap call. [DER S-yvalenhr, S-r3t6wvk5: KEK must stay out of the database; what age and sops can revoke]

### Blind indexes
- A blind index is a deterministic one-way keyed hash (or KDF output) of the plaintext, truncated to a chosen number of bits and used as a Bloom filter for lookups; a field can have several, each over a transformed form of the plaintext. [DOC S-qt7piebc]
- CipherSweet's fast index is HMAC-SHA384 (FIPS profile) or keyed BLAKE2b and its slow one PBKDF2-SHA384 (default 50,000 iterations) or Argon2id (32 MB memory limit, 4 operations); every index has its own key derived with HKDF-HMAC-SHA256, from which others cannot be derived; the two pages disagree on the FIPS fast index: the security page (S-qt7piebc) says HMAC-SHA384, the blind-index internals page (S-rqc6efd7) says PBKDF2-SHA384 with 1 iteration, and the kb states both. [DOC S-qt7piebc, S-rqc6efd7]
- Truncation makes false positives ("coincidences") deliberate, so two equal index values do not prove equal plaintexts; but if many indexes (the page's example: 100) on one field are identical for two rows, their plaintexts can be inferred to be identical. [DOC S-qt7piebc]
- The page's leakage model: the chance of a coincidence for one index is 2^-min(L, K) for output length L and input keyspace K, and the expected number of coincidences is C = R / 2^(sum of min(L_i, K_i)) for R records; the advice is to keep 2 <= C < sqrt(R) and to use as few and as short indexes as possible. [DOC S-qt7piebc]
- The same page assumes the database is curious and malicious, and recommends the row's primary key as additional authenticated data on every encrypted field so a ciphertext cannot be moved between rows. [DOC S-qt7piebc]
- An index over a small domain (a status, a country, a role) has K small, so `min(L, K)` is K and the index is effectively a full deterministic fingerprint: the database learns which rows share a value and how many do, whatever the key. [DER S-qt7piebc: the formula's min(L, K) term; deterministic output]
- A blind index also leaks the equality pattern across rows and the frequency of each value to anyone who can read the index column, and, with a candidate list, lets the holder of the index key test guesses offline; the HMAC key is therefore a secret of the same class as the data key and kept separate from it. [DER S-qt7piebc, S-alffetzh: keyed deterministic output; hmac recalculable only with the key]
- Open: whether key arguments to pgcrypto functions can reach server logs or statistics views is not stated on the pgcrypto page. [UNK: the page covers cleartext transit, not logging]

## Reference
| Layer | Holds | Rotates by | Leaks to a database administrator |
|---|---|---|---|
| Wrapping key (KEK) | outside the database (KMS, age/sops file, HSM) | rewrap site DEKs | n/a |
| Site DEK | wrapped, in a key table | re-encrypt that site's rows | nothing if wrapping and use are client side |
| Column ciphertext | `pgp_sym_encrypt`, AEAD blob or similar | follows its DEK | length, row count, access pattern |
| Blind index | truncated keyed hash per field | new index key, recompute | equality pattern and value frequency |

## Examples
- SNIPPET: an equality blind index computed with `hmac` and truncated to 16 bits; context: PostgreSQL with pgcrypto, key shown as a placeholder (it passes through the server, see the facts above); checked: no [DOC S-alffetzh: `hmac()`; S-qt7piebc: truncated blind index]
```sql
-- 16-bit blind index of a lower-cased value, key from the application
SELECT substring(hmac(lower('jan.kowalski@corp.example.com'), '<index-key>', 'sha256') from 1 for 2) AS bidx;
```
