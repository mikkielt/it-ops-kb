---
topic: security/supply-chain
priority: P1
applies_to: "a Python 3.13 package built with uv; GitLab self-managed CI/CD"
retrieved_utc: 2026-09-27
sources: [S1501, S1502, S-paztzzud, S1504, S1505, S1506, S1507, S1508, S1509, S1510, S1511, S1512, S1517, S1522, S1523, S1524, S1525, S1597, S-sxp3exzp, S-dlc2x6gf, S-5ry5zerr, S-5t26tmbz, S-cos7wdpw, S-l6ia2wz4, S-7d4nrwpk, S-hvhro6n5]
status: complete
---

# Supply-chain security for a Python package and its CI

## Summary
NIST SSDF (SP 800-218 v1.1, plus the 800-218A generative-AI companion profile) and SLSA v1.2 give the vocabulary; OpenSSF Scorecard and SPDX/CycloneDX give the tooling. `uv`/`pip` can enforce hash-pinned installs. PyPI's user docs still say Trusted Publishing supports only gitlab.com projects, but PyPI's own blog (2025-11-10) opened a **beta** for GitLab Self-Managed instances, onboarded by hand by PyPI staff. This matters only if the package is ever published to public PyPI; an internal design that names no public package publishing avoids the issue entirely. GitLab's own SLSA level 3 attestation is an Ultimate, GitLab.com-only experiment that requires a **public** project, which an internal repository is not.

## Facts
- NIST SSDF (Secure Software Development Framework), SP 800-218, is at version 1.1 ("Recommendations for Mitigating the Risk of Software Vulnerabilities"); no newer core revision was found as of 2026-09-24. [DOC S1501]
- SP 800-218A, "Secure Software Development Practices for Generative AI and Dual-Use Foundation Models: An SSDF Community Profile", is a finalized companion profile (2024), not a revision of SP 800-218 — it extends SSDF practices to the development of generative-AI/foundation-model software, which is a closer fit to an MCP-server component than the base SSDF. [DOC S1502]
- SLSA's current spec is version 1.2 (v1.0 pages now carry a banner pointing to it); 1.2 reintroduces a Source track alongside the Build track. The Build track levels are L0-L3: L0 no guarantees; L1 provenance exists, generated automatically by the build platform; L2 adds a hosted build platform that signs the provenance, which consumers validate; L3 adds hardened builds, with strong controls stopping runs from influencing each other and keeping signing secrets from user-defined build steps. [DOC S-paztzzud]
- OpenSSF Scorecard is an automated tool that scores an open-source project (0-10) across security-practice checks (branch protection, pinned dependencies, CI permissions, etc.); source at github.com/ossf/scorecard, Apache-2.0 licensed. [DOC S1504]
- SPDX (Software Package Data Exchange) is at spec version 3.0.x, restructured around profiles (core, software, security, build, AI, dataset, licensing, lite). SPDX 2.2.1 corresponds to the ratified ISO/IEC 5962:2021 standard; SPDX 3.0's ISO/IEC submission was still in draft status (DIS) as of this research pass. [DOC S1505]
- CycloneDX is an OWASP-project SBOM format; the 1.x line has continued to add fields (cryptographic assurance, IP visibility) through recent releases. [DOC S1506]
- `uv pip compile` locks dependencies to exact versions in a `requirements.txt` or PEP 751 `pylock.toml` output file, and `--generate-hashes` adds distribution hashes to that file. [DOC S1522, S-dlc2x6gf]
- `pip install`/`pip download --require-hashes` puts pip into hash-checking mode: installation fails unless every requirement, including transitive dependencies, carries a matching hash. [DOC S1507]
- PyPI Trusted Publishing lets a CI job obtain a short-lived PyPI API token via OIDC instead of storing a long-lived token as a secret; the minted token is project-scoped and valid for 15 minutes. Supported OIDC issuers are GitHub Actions, GitLab CI/CD, Google Cloud and ActiveState. [DOC S1508,S1597]
- PyPI added GitLab CI/CD, Google Cloud and ActiveState as Trusted Publishing providers on 2024-04-17, beside GitHub Actions; the announcement describes the exchange of short-lived OIDC identity tokens for short-lived, tightly scoped PyPI API tokens that never need to be stored. [DOC S1509]
- PyPI's *Adding a Trusted Publisher* page states, for GitLab: "Currently, only projects hosted on https://gitlab.com are supported. Self-managed instances are not supported." [DOC S1597]
- PyPI's own blog (2025-11-10) announced Trusted Publishing for **GitLab Self-Managed in beta**: PyPI staff onboard each organization's instance by hand (by email to PyPI support, giving the instance URL and confirming its `/.well-known/openid-configuration` and `/oauth/discovery/keys` endpoints are reachable). The *Adding a Trusted Publisher* page above and the troubleshooting page were not updated and still say only gitlab.com is supported. A Socket post (S1510) reported the same. [DOC S-5ry5zerr, S1597]
- In Warehouse (PyPI's code) the GitLab publisher stores an `issuer_url` per publisher and supports custom issuers, and a token's `iss` must equal the registered issuer, so a self-managed instance can only match publishers registered for that instance. [CODE S-5t26tmbz: warehouse/oidc/models/gitlab.py#GitLabPublisherMixin]
- PyPI's 2025 review says Trusted Publishing was expanded to GitLab Self-Managed instances and custom OIDC issuers for organizations, and that more than 50,000 projects use it. [DOC S-cos7wdpw]
- Registering a GitLab Trusted Publisher on PyPI requires the repository's namespace, the repository's name and the file path of the top-level GitLab CI/CD pipeline definition (e.g. `.gitlab-ci.yml`) authorized to upload; a GitLab environment name is optional but strongly recommended. [DOC S1597]
- The publishing CI job requests an OIDC token with GitLab's `id_tokens:` keyword (named `PYPI_ID_TOKEN` in PyPI's example) with audience `pypi` (`testpypi` for TestPyPI); twine then uploads with no token configured and exchanges the OIDC token for a PyPI API token. [DOC S1525]
- GitLab's SLSA Build Level 3 provenance/attestation feature (behind the `slsa_provenance_statement` flag and the `ATTEST_BUILD_ARTIFACTS` CI/CD variable) requires the **project to be public**, and the attested artifact must be 100 MB or smaller. [DOC S1523]
- Tier gates as of GitLab docs commit 9f1632e (2026-09-27): SLSA level 3 provenance attestations are **Ultimate, GitLab.com only, status Experiment** (introduced in 18.3 behind a flag that is off by default, not ready for production); Sigstore keyless signing is Free, Premium and Ultimate but **GitLab.com only**; runner artifact provenance metadata (`RUNNER_GENERATE_ARTIFACTS_METADATA`, an in-toto v0.1 statement with an SLSA 1.0 provenance predicate) is on every tier and offering, self-managed included. [DOC S-l6ia2wz4, S-7d4nrwpk, S-hvhro6n5]
- A 2022 GitLab blog post says the platform then supported SLSA Levels 1 and 2 (the Runner writes provenance metadata when `RUNNER_GENERATE_ARTIFACTS_METADATA: true` is set) and that features such as signing the attestation were planned for Levels 3 and 4; it predates SLSA v1.x build levels. [DOC S1524]
- GitLab's dependency scanning using SBOM (Ultimate; GitLab.com, Self-Managed and Dedicated; generally available in GitLab 19.0) has its analyzer emit a CycloneDX SBOM for each directory with a supported lockfile, manifest or dependency graph, and scans it for known vulnerabilities; third-party CycloneDX SBOMs supplied as CI/CD artifact reports are technically possible but documented as subject to change, and must comply with CycloneDX spec 1.4, 1.5 or 1.6 and GitLab's CycloneDX property taxonomy (the page does not state which spec version the analyzer itself emits). [DOC S1511]
- GitLab's pipeline security guidance says to always use SHA digests for job images (`image: <name>@sha256:<digest>`) instead of tags like `:latest`, for client-side integrity verification, and to prefer registries with protected repositories and protected tags; the `image` keyword accepts `<image-name>@<digest>`. [DOC S-sxp3exzp, S1512]
- DSC v3's resource manifest format has no supply-chain integrity field of its own (see `security/script-and-code-signing.md`); any provenance for a DSC resource distributed with a package has to come from the package/CI supply chain above, not from DSC itself. [DER S1517: manifest schema has no signing/checksum field, so package-level provenance is the only lever]

## Reference
| Mechanism | Relevance | Source |
|---|---|---|
| SSDF SP 800-218 / 800-218A | secure-development baseline; 218A fits an MCP-server component | S1501,S1502 |
| SLSA v1.2 build levels | target level for a configuration repository's/package's CI builds | S-paztzzud |
| PyPI Trusted Publishing | gitlab.com GA; self-managed GitLab only as a hand-onboarded beta; relevant only if the package is published to public PyPI | S1508,S1597,S-5ry5zerr |
| GitLab SLSA attestation | Ultimate, GitLab.com only, Experiment; needs a **public** project, so internal repos cannot use it | S1523,S-l6ia2wz4 |
| GitLab runner provenance metadata | every tier and offering, including self-managed | S-hvhro6n5 |
| uv/pip hash pinning | available today, no GitLab-tier dependency | S1522,S-dlc2x6gf,S1507 |
| GitLab image digest pinning | available today (CI/CD YAML syntax), no GitLab-tier dependency | S-sxp3exzp, S1512 |

## Examples
No fixture-specific configuration; these are packaging/CI-pipeline facts independent of device or tenant fixtures.
