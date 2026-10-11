---
topic: auth/sops-age-recipients
priority: P3
applies_to: "sops 3.13.x with age 1.3.x recipients: .sops.yaml creation_rules, key groups, updatekeys and rotate, what a committed encrypted file keeps"
retrieved_utc: 2026-10-11
sources: [S-r3t6wvk5, S-ax3gmu7j, S-bi6fdfos]
status: complete
---

# sops with age: recipients per file, key groups, updatekeys and rotate

## Summary
`.sops.yaml` picks the recipients of a new file by path; the age recipients are public keys, so anyone can encrypt, and only holders of an identity can decrypt. `sops updatekeys` changes who can read a file without touching its data key; `sops rotate` replaces the data key. Removing a recipient does not unread the versions of the file already committed: only rotating the secrets inside them does. This extends `auth/key-management-options.md` (no rotation hook tied to group membership) and `prior-art/secret-vault-encryption.md`.

## Facts
- The config file must be named `.sops.yaml` (not `.sops.yml`); sops looks for it in the current working directory and its parents and uses the first one found, and `--config` or `SOPS_CONFIG` names another file. [DOC S-r3t6wvk5]
- The lookup starts from the working directory, not from the directory of the file being encrypted, and `path_regex` is matched against the file's path relative to the `.sops.yaml`. [DOC S-r3t6wvk5]
- `creation_rules` are evaluated in order and the first rule whose `path_regex` matches is used; a rule with no `path_regex` matches every file, so it is the catch-all and goes last. [DOC S-r3t6wvk5]
- The config file is ignored when KMS or PGP parameters are passed on the sops command line or in environment variables; the page does not repeat this for age, whose recipients can also be given with `--age` or `SOPS_AGE_RECIPIENTS`. [DOC S-r3t6wvk5]
- In a creation rule `age` is a comma-separated string or a list of age public keys; the same keys can sit in a rule directly (one key group) or under `key_groups`, and when `key_groups` is given the rule's individual key settings are ignored. [DOC S-r3t6wvk5]
- Each key group holds identities of any type (`age`, `pgp`, `kms`, `gcp_kms`, `azure_keyvault`, `hc_vault`, `hckms`), and a `merge` list in a key group concatenates keys of the same type from other groups. [DOC S-r3t6wvk5]
- With key groups, sops splits the data key with Shamir's secret sharing so that each key group holds one fragment, any key of a group can recover that group's fragment, and a threshold number of fragments rebuilds the data key. [DOC S-r3t6wvk5]
- The threshold defaults to the number of key groups, so with three groups one master key from each group is needed; `shamir_threshold` in a creation rule (an integer, default 0 meaning off, otherwise at least 2) or `--shamir-secret-sharing-threshold` on the command line lowers it, and it counts key groups, not individual keys. [DOC S-r3t6wvk5]
- `sops groups add` and `sops groups delete` change the key groups of an existing file; groups are zero-indexed. [DOC S-r3t6wvk5]
- `sops updatekeys FILE` reads `.sops.yaml` and adds or removes the file's recipients to match it, showing the change and asking first (`-y` skips the prompt); the sops team recommends this route and it keeps the data key. [DOC S-r3t6wvk5]
- `sops rotate` generates a new data key and re-encrypts every value with it; `--add-*` and `--rm-*` flags change recipients at the same time (the page lists them for kms, pgp, gcp-kms, hckms and azure-kv; its age examples use `updatekeys`). [DOC S-r3t6wvk5]
- When a key is removed another way (direct editing), the page recommends rotating the data key because the owner of the removed key "may have had access to the data key in the past". [DOC S-r3t6wvk5]
- For a compromised key the documented order is: remove it from the key group in `.sops.yaml`, run `sops updatekeys FILE`, then `sops rotate --in-place FILE`, commit and push; only after that rotate the secrets inside the file. [DOC S-r3t6wvk5]
- The reverse order leaves the compromised key with access in two cases: the file is committed between the two calls, or the key sits with a cloud provider that is itself compromised and so keeps the data key it was asked to encrypt. [DOC S-r3t6wvk5]
- Running `sops rotate` periodically is recommended anyway. [DOC S-r3t6wvk5]
- sops finds age identities in `SOPS_AGE_KEY_FILE`, `SOPS_AGE_KEY` or the output of `SOPS_AGE_KEY_CMD`, else in `keys.txt` under the user's sops/age configuration directory; ssh keys (`ssh-rsa`, `ssh-ed25519`, not password protected) are read from `SOPS_AGE_SSH_PRIVATE_KEY_FILE`, `SOPS_AGE_SSH_PRIVATE_KEY_CMD` or `~/.ssh`. [DOC S-r3t6wvk5]
- An age identity file holds one or more `AGE-SECRET-KEY-1...` lines (or an ssh key), `#` lines are comments, and a recipient is an `age1...` public key or an `ssh-ed25519` or `ssh-rsa` public key; `age-keygen -y` prints the recipient of an identity file. [DOC S-ax3gmu7j]
- An age X25519 identity is 32 bytes from a CSPRNG, written in Bech32 with the prefix `AGE-SECRET-KEY-`; the recipient is `X25519(identity, basepoint)` in Bech32 with the prefix `age`. [DOC S-bi6fdfos]
- Encrypting to an ssh key embeds a public key tag in the file, so files encrypted to one ssh key can be linked; age's README says such keys may not be protected long term because they are revocable when used only for authentication. [DOC S-ax3gmu7j]
- Since age 1.3.0 `age-keygen -pq` makes hybrid post-quantum identities (`AGE-SECRET-KEY-PQ-1...`) with `age1pq1...` recipients of about 2000 characters; whether sops accepts such recipients is not stated on the sops pages read. [DOC S-ax3gmu7j]
- What git history keeps: every earlier commit of an encrypted file stays encrypted to its own recipient set and data key, and the sops page advises rotating the data key and then the secrets because a removed key's owner may already hold the data key; so a recipient removed today can still decrypt the versions committed while it was a recipient, and only changing the secret values themselves makes those versions useless. [DER S-r3t6wvk5: rotation order and "may have had access in the past"; commits are immutable]
- A removal by `updatekeys` alone is therefore access control going forward, not erasure; it needs `rotate` on the same file and a new value at the issuer of each secret inside. [DER S-r3t6wvk5: the compromised-key procedure]

## Reference
| Task | Command or setting | Data key | Source |
|---|---|---|---|
| Choose recipients by path | `creation_rules[].path_regex` + `age` | n/a (new file) | S-r3t6wvk5 |
| Require several groups | `key_groups` + `shamir_threshold` | split in fragments | S-r3t6wvk5 |
| Apply a changed recipient list | `sops updatekeys FILE` | kept | S-r3t6wvk5 |
| New data key | `sops rotate -i FILE` | replaced | S-r3t6wvk5 |
| Drop a compromised key | remove it, `updatekeys`, `rotate`, commit, then rotate the secrets | replaced | S-r3t6wvk5 |

## Examples
- SNIPPET: creation rules by path with age recipients and a key group threshold; context: `.sops.yaml` at the repository root, recipients are placeholders; checked: no [DOC S-r3t6wvk5: creation_rules, key_groups, shamir_threshold]
```yaml
creation_rules:
  - path_regex: \.prod\.yaml$
    shamir_threshold: 2
    key_groups:
      - age:
          - <age-recipient-operator-a>
      - age:
          - <age-recipient-operator-b>
      - age:
          - <age-recipient-ci>
  - age: <age-recipient-operator-a>
```
