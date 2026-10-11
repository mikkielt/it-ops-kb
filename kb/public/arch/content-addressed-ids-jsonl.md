---
topic: arch/content-addressed-ids-jsonl
priority: P3
applies_to: "JSON Lines (jsonlines.org source @d5ba812), NDJSON 1.0.0, RFC 8259, RFC 8785, RFC 4648; FIPS 180-4 and FIPS 202 (Aug 2015), SP 800-107 Rev. 1; BLAKE3 1.8.7, sha2 0.11.0; Python 3.14.7 hashlib and json; multihash @b43ec10, CID (ipfs/specs @3000be6), multibase @d7406cd, multicodec @8d9e9b3; Git v2.55.0 (retrieved 2026-10-11)"
retrieved_utc: 2026-10-11
sources: [S-wux7hanj, S-5m7fpuo3, S-f2cirt63, S-4rjxcq6v, S-wtlhziak, S-zzvrhdyd, S-2lsfwean, S-c5k5fslm, S-y6p3nnub, S-tvrordiw, S-6icauyji, S-ndrgfovo, S-5p5nwact, S-y6i5zuly, S-zf4axfjq, S-k4oiaaw2, S-hqrgt5kx, S-pn5cpaof, S-szv7ubhm, S-22wqxchx, S-7lqazmox, S-dgbl4wgb, S-eperpanz, S-silsshto, S-dbs2gjpc, S-za3ghpu4, S-3yvyv65p, S-nv6io42x, S-2wxyobvm, S-h7eqeryo]
status: partial
---

# Content-addressed ids for JSON Lines records: formats, canonical JSON, hashes, encodings

## Summary
A record in a JSON Lines file can be given a stable id by hashing its canonical JSON bytes. The pieces
have official specifications: JSON Lines (and the older NDJSON) frame one JSON value per line;
RFC 8785 (JCS) defines a canonical byte form for hashing; SHA-256 (FIPS 180-4) is the standardised
hash, with SHA3-256 (FIPS 202) as the alternative and BLAKE3 as a fast, public-domain, non-FIPS choice;
multihash and CID show the self-describing id form; RFC 4648 defines the text encodings of a digest.
The Python `json` module does not produce JCS output for floats or for keys outside the BMP, so a
Python shell and a Rust core must restrict the record shape or use a real JCS serialiser. The Facts
below separate what each text states from the derivation of an id recipe.

## Facts
### JSON Lines and NDJSON
- JSON Lines has three requirements: UTF-8 with no byte order mark, each line a valid JSON value (any value is allowed, `null` is valid, a blank line is not), and `\n` as the line terminator (`\r\n` also works because surrounding whitespace is ignored); a terminator after the last value is strongly recommended but not required, and if present it must be the last byte. [DOC S-wux7hanj]
- JSON Lines files may use the extension `.jsonl` (`.jsonl.gz`, `.jsonl.bz2` when compressed); the page says the MIME type "may be `application/jsonl`, but this is not yet standardized". [DOC S-wux7hanj]
- NDJSON 1.0.0 (last update 2014-10-19) requires each JSON text to conform to RFC 8259, be followed by `\n` (optionally preceded by `\r`) and contain no newline or carriage return, with UTF-8 throughout; a parser must accept `\n` and `\r\n` and may silently ignore empty lines if it documents that; the media type should be `application/x-ndjson` and the extension `.ndjson`. [DOC S-5m7fpuo3]
- The two formats frame records the same way and differ at the edges: JSON Lines calls a blank line invalid and makes the final terminator optional, NDJSON lets a parser skip empty lines (documented) and requires a newline after every text; the extension (`.jsonl` or `.ndjson`) and the unstandardised media type (`application/jsonl` or `application/x-ndjson`) differ, and neither text is an IETF standards-track document. [DER S-wux7hanj, S-5m7fpuo3: the two requirement lists compared]
- The IANA `application` media type registry (CSV retrieved 2026-10-11) lists `application/json` (RFC 8259) and `application/json-seq` (RFC 7464) and has no entry for `jsonl` or `ndjson`. [DER S-f2cirt63: absence in the registry file on that date]

### JSON itself (RFC 8259)
- Object member names SHOULD be unique; with duplicate names the receiving software's behaviour is unpredictable (many report the last pair, others fail, some report all), and parsing libraries differ in whether they expose member order. [DOC S-4rjxcq6v]
- Section 6 lets implementations limit range and precision; software that implements IEEE 754 binary64 interoperates well, a number such as `1E400` or `3.141592653589793238462643383279` may signal an interoperability problem, and integers in [-(2**53)+1, (2**53)-1] are interoperable (implementations agree exactly). [DOC S-4rjxcq6v]
- JSON text exchanged outside a closed ecosystem MUST be UTF-8 and MUST NOT start with a byte order mark; the grammar admits an unpaired surrogate such as `"\uDEAD"`, and the behaviour of software receiving one is unpredictable. [DOC S-4rjxcq6v]

### Canonical JSON for hashing (RFC 8785, JCS)
- RFC 8785 is an Informational Independent Submission (June 2020), not an IETF standard; it defines a "hashable" canonical form of JSON and constrains input to I-JSON: no duplicate property names, strings expressible as Unicode, numbers expressible as IEEE 754 double precision, with larger numbers recommended as JSON strings. [DOC S-wtlhziak]
- JCS emits no whitespace between tokens, serialises strings as ECMAScript does (U+0000 to U+001F as lowercase `\uhhhh` except `\b \t \n \f \r`, only `"` and `\` otherwise escaped), serialises numbers per ECMA-262 section 7.1.12.1, preserves Unicode as is (no normalisation), and terminates with an error on NaN, Infinity or a lone surrogate. [DOC S-wtlhziak]
- JCS sorts object properties recursively on their raw names as arrays of UTF-16 code units compared as unsigned integers, independent of locale, leaves array order unchanged, and encodes the result as UTF-8; the RFC notes that sorting UTF-8 or UTF-32 gives a different order for some names and is compatible only when names are effectively 7-bit ASCII. [DOC S-wtlhziak]
- Python's `json.dumps` has `sort_keys` (sort dictionaries by key), `separators=(',', ':')` (no whitespace), `ensure_ascii=False` (characters output as is except the required escapes) and `allow_nan=False` (ValueError on nan and inf); by default NaN and Infinity are written, and a repeated name keeps only the last pair when loading. [DOC S-zzvrhdyd]
- Python compares `str` values by Unicode code point, while JCS sorts by UTF-16 code unit, so `sort_keys=True` can order keys differently from JCS when a key has a character above U+FFFF next to one in U+E000 to U+FFFF. [DER S-2lsfwean, S-wtlhziak: code point order versus UTF-16 code unit order]
- On Python 3.13.2 (macOS, 2026-10-11, `json.dumps(..., sort_keys=True)`), the RFC 8785 sorting test data came out in a different order from the RFC's expected one (the emoji key last), and `json.dumps` matched the serialisation in only 5 of the 12 Appendix B number rows tried (`1e-06`, `9007199254740992.0`, `-0.0`, `2.9514790517935283e+20` differ); the probe did not run on Python 3.14. [DER S-wtlhziak, S-zzvrhdyd: RFC 8785 section 3.2.3 and Appendix B compared with the probe]
- RFC 8785 delegates number serialisation to the ECMA-262 algorithm; that algorithm's text was not read for this topic and no Rust or Python JCS library was surveyed. [UNK]

### Hash functions and their status
- FIPS 180-4 (August 2015) specifies SHA-256 with a 256-bit digest for messages shorter than 2^64 bits, and in section 7 truncation by taking the leftmost bits, referring to SP 800-107 for the security implications; the CSRC page carries a planning note (03/07/2023) that NIST "has decided to revise FIPS 180-4". [DOC S-c5k5fslm, S-y6p3nnub]
- FIPS 202 (August 2015) defines SHA3-256 (256-bit digests); its Table 4 gives SHA-256 and SHA3-256 128 bits of collision strength and 256 of preimage strength, and it says a random function with a d-bit output cannot give more than d/2 bits against collision attacks; the CSRC page carries a planning note (03/13/2025) that NIST has decided to update it. [DOC S-tvrordiw, S-6icauyji]
- SP 800-107 Rev. 1 (August 2012) section 5.1: a truncated digest takes the left-most lambda bits and cuts the expected collision resistance from L/2 to lambda/2 (a 96-bit truncation of SHA-256 gives 48 bits); lambda should be at least twice the required collision strength; and all parties must know the truncation and the hash function with no ambiguity. Its page carries a planning note (12/20/2022) that NIST has decided to withdraw it and moved supplementary material to its hash functions page. [DOC S-ndrgfovo, S-5p5nwact]
- BLAKE3's README (tag 1.8.7) claims it is much faster than MD5, SHA-1, SHA-2, SHA-3 and BLAKE2 and secure against length extension; the default output size is 256 bits; it is released under CC0 1.0 or, alternatively, Apache 2.0 or Apache 2.0 with LLVM exceptions; it is "not a password hashing algorithm"; and it is specified in the C2SP project. [DOC S-y6i5zuly]
- BLAKE3 is not one of the functions FIPS 180-4 (SHA-1, SHA-2 family) or FIPS 202 (SHA-3, SHAKE) specify, and the Python 3.14 `hashlib` constructor list has `blake2b` and `blake2s` but no BLAKE3. [DER S-c5k5fslm, S-tvrordiw, S-7lqazmox: absence from the standards' function lists and the constructor list]
- Rust crates: `blake3` 1.8.7 (crates.io newest, published 2026-08-20) is licensed `CC0-1.0 OR Apache-2.0 OR Apache-2.0 WITH LLVM-exception`, enables `std` by default and gates `rayon` and `mmap` behind off-by-default features, and gives no SemVer guarantee for `traits-preview`; `sha2` 0.11.0 (published 2026-03-25, rust-version 1.85) is `MIT OR Apache-2.0`, a pure Rust SHA-224/256/384/512 family implementation that uses the x86 SHA-NI or AArch64 `sha2` backend when detected at runtime and otherwise a portable `soft` backend. [DOC S-zf4axfjq, S-k4oiaaw2, S-pn5cpaof, S-szv7ubhm, S-22wqxchx]
- In `blake3` 1.8.7 `OUT_LEN` is 32 bytes, `Hash::to_hex` returns lowercase hexadecimal (64 characters), `Hash::from_hex` accepts upper and lower case and rejects any length other than 64, and `Hash` equality is constant-time. Implementation, not a promise. [CODE S-hqrgt5kx: src/lib.rs#Hash::to_hex]
- Python 3.14 `hashlib`: `sha256`, `sha3_256`, `blake2b` and `blake2s` are always present (`algorithms_guaranteed`), `digest()` returns bytes of `digest_size` and `hexdigest()` a string of double length; `blake2b` takes `digest_size` up to 64 bytes (default 64) and `blake2s` up to 32; `file_digest(fileobj, digest)` (3.11) hashes a binary file object. [DOC S-7lqazmox]

### Self-describing ids and digest encodings
- Multihash is `<varint hash function code><varint digest size in bytes><digest>`; in the multicodec table `sha2-256` is `0x12` and `sha3-256` `0x16` (both `permanent`) and `blake3` is `0x1e` with status `draft` (default 32-byte output); the multihash README adds that the first two bytes bias the value and that non-cryptographic hashes are unsuitable for content addressing. [DOC S-dgbl4wgb, S-eperpanz]
- A CIDv1 is `<version varint><content-type multicodec><multihash>`; its text form prepends one multibase code point (`b` base32, `f` base16, `z` base58btc, and implementations SHOULD support at least base58btc, base32, base16 and base36); the maintained specification is `src/cid.md` of ipfs/specs (maturity `permanent`, 2026-06-26), while the multiformats/cid repository is marked outdated and kept for historical reference. [DOC S-silsshto, S-dbs2gjpc]
- The multibase table lists `f` base16 (lowercase, `final`), `b` base32 and `B` base32upper ("RFC4648 case-insensitive - no padding", `final`), `u` base64url ("RFC4648 no padding", `final`) and the `base32hex` variants as `experimental`. [DOC S-za3ghpu4]
- Git's object name is the hash of the object's type, length, a nul byte and the content, written as 40 hexadecimal digits (SHA-1) or 64 (SHA-256); the project picked SHA-256 in late 2018 as the successor, selects it per repository with `extensions.objectFormat`, `git init --object-format` takes `sha1` (default) or, if enabled, `sha256`, and there is at present no interoperability between SHA-256 and SHA-1 repositories. [DOC S-3yvyv65p, S-nv6io42x, S-2wxyobvm]
- RFC 4648: base16 is the standard case-insensitive hex encoding and needs no padding; base32 (alphabet A to Z and 2 to 7, 5 bits per character) is designed for forms that must be case insensitive but need not be human readable; `base32hex` keeps the sort order of the encoded data under bitwise comparison; base64url swaps `+` and `/` for `-` and `_` and its `=` padding may be skipped when the length is known implicitly. [DOC S-h7eqeryo]
- RFC 4648 section 3.4 notes that `+` and `/` are treated as word breaks by legacy search tools and are troublesome in file names and URLs, and section 3.5 requires pad bits to be zero (a decoder MAY reject otherwise) because without that several strings decode to the same bytes. [DOC S-h7eqeryo]

### How it fits (derivation for a CPU-only corpus service)
- A recipe for a stable record id: serialise the record as JCS bytes (UTF-8), hash them with SHA-256, encode the 32-byte digest. The encodings are 64 characters in lowercase hex, 52 in base32 without padding (56 with `=`), or 43 in base64url without padding. The id field itself stays out of the hashed bytes, since a digest cannot cover itself. [DER S-wtlhziak, S-c5k5fslm, S-h7eqeryo: JCS bytes, FIPS 180-4 digest size, RFC 4648 group sizes]
- Because JCS emits no whitespace and escapes U+0000 to U+001F, a canonical record contains no raw newline and is therefore a valid single line of JSON Lines and of NDJSON; the same bytes serve as the stored line and as the hash input. [DER S-wtlhziak, S-wux7hanj, S-5m7fpuo3: JCS output rules against the line framing rules]
- Keeping the algorithm in the id (a `sha256-` prefix, or a multihash or CID form) lets a later change of hash function coexist with old ids; SP 800-107 asks that the hash and any truncation be unambiguous to all parties, and Git's SHA-1 to SHA-256 plan has to carry both name forms during the move. [DER S-ndrgfovo, S-dgbl4wgb, S-3yvyv65p: unambiguity requirement, self-identifying hash form, dual naming]
- Truncating an id to lambda bits leaves about lambda/2 bits of collision resistance (a 128-bit prefix gives about 64), so a shortened display form should be a view of the full digest, never the stored key. [DER S-ndrgfovo, S-tvrordiw: the lambda/2 rule applied to 128 bits]
- With the Python stdlib on both sides of the line, an id is only as stable as the record shape: floats, `-0.0` and keys above U+FFFF are where `json.dumps` and JCS part ways, so records meant to be hashed should hold strings, booleans, null and integers within +/-(2**53)-1 (or carry larger numbers as strings, as RFC 8785 Appendix D recommends), and both the Python and the Rust serialiser should pass the RFC's sorting and number samples. [DER S-wtlhziak, S-4rjxcq6v, S-zzvrhdyd: the differences above and the interoperable integer range]
- SHA-256 needs no network and no model, is standardised, is guaranteed in `hashlib` and is a pure Rust crate with hardware backends; BLAKE3 would add speed and a public-domain licence at the price of a non-FIPS, non-`hashlib` function and a `draft` multicodec entry, so SHA-256 is the conservative default for record ids and BLAKE3 a candidate for large-artifact digests. [DER S-c5k5fslm, S-7lqazmox, S-pn5cpaof, S-y6i5zuly, S-eperpanz: standards status, library availability, licence and registry status]

## Reference
- JSON Lines: https://jsonlines.org/ ; NDJSON: https://github.com/ndjson/ndjson-spec
- RFC 8259: https://www.rfc-editor.org/rfc/rfc8259 ; RFC 8785: https://www.rfc-editor.org/rfc/rfc8785 ; RFC 4648: https://www.rfc-editor.org/rfc/rfc4648
- FIPS 180-4: https://csrc.nist.gov/pubs/fips/180-4/upd1/final ; FIPS 202: https://csrc.nist.gov/pubs/fips/202/final ; SP 800-107 Rev. 1: https://csrc.nist.gov/pubs/sp/800/107/r1/final
- BLAKE3: https://github.com/BLAKE3-team/BLAKE3 ; crates: https://docs.rs/blake3/1.8.7/blake3/ , https://docs.rs/sha2/0.11.0/sha2/
- Python: https://docs.python.org/3.14/library/hashlib.html , https://docs.python.org/3.14/library/json.html
- Multihash: https://github.com/multiformats/multihash ; CID: https://specs.ipfs.tech/cid/ ; multibase: https://github.com/multiformats/multibase
- Git: https://github.com/git/git/blob/v2.55.0/Documentation/technical/hash-function-transition.adoc
- Related: `agents/codebase-mapping.md` (Universal Ctags JSON Lines output, versioned and may change); `arch/texts-catalogue-formats.md`; `agents/hybrid-retrieval.md`; `security/supply-chain.md` (digest pinning); `python/stdlib-argparse-json.md`.

## Examples
- SNIPPET: a record id from sorted-key compact JSON, SHA-256 and lowercase base32 without padding (59 characters with the `sha256-` prefix); context: Python 3.13.2 stdlib on macOS, valid for records of strings, integers, booleans and null with keys in the BMP (not for floats, see above); checked: run [DER S-zzvrhdyd, S-7lqazmox, S-h7eqeryo: `json.dumps` parameters, `hashlib.sha256`, base32 alphabet]
```python
import base64
import hashlib
import json


def record_id(record: dict) -> str:
    canonical = json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    digest = hashlib.sha256(canonical).digest()
    return "sha256-" + base64.b32encode(digest).decode("ascii").rstrip("=").lower()
```
- Observed on Python 3.13.2 (macOS, 2026-10-11): the record `{"doc": "PL-DOC-0001", "line": 7, "text": "zółw"}` serialises to `{"doc":"PL-DOC-0001","line":7,"text":"zółw"}`, whose SHA-256 in hex is `2060c8190028b8f4867bb4a394e21f6f96e9df0ed7502e46cf54a0ba1ebc1c30`; the same record with its keys in another order gives the same id, and `nan` raises `ValueError` while a lone surrogate raises `UnicodeEncodeError`. [DER S-zzvrhdyd, S-7lqazmox: the snippet above run once]
- SNIPPET: the same digest in Rust with the two crates at the versions above; context: `sha2` 0.11.0, `blake3` 1.8.7, `canonical` holds the JCS bytes; checked: no [DOC S-pn5cpaof, S-y6i5zuly]
```rust
use sha2::{Digest, Sha256};

let canonical: &[u8] = br#"{"doc":"PL-DOC-0001","line":7}"#;
let sha256_digest = Sha256::digest(canonical);
let blake3_hex = blake3::hash(canonical).to_hex();
```
