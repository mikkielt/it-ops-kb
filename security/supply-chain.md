---
topic: security/supply-chain
priority: P1
applies_to: "a Python 3.13 package built with uv; GitLab self-managed CI/CD"
retrieved_utc: 2026-09-24
sources: [S1501, S1502, S1503, S1504, S1505, S1506, S1507, S1508, S1509, S1510, S1511, S1512, S1517, S1522, S1523, S1524, S1525, S1597]
status: partial
---

# Supply-chain security for a Python package and its CI

## Summary
NIST SSDF (SP 800-218 v1.1, plus the 800-218A generative-AI companion profile) and SLSA v1.0 give the vocabulary; OpenSSF Scorecard and SPDX/CycloneDX give the tooling. `uv`/`pip` can enforce hash-pinned installs. PyPI Trusted Publishing supports only gitlab.com projects, not self-managed GitLab. This matters only if the package is ever published to public PyPI; an internal design that names no public package publishing avoids the issue entirely. GitLab's own SLSA provenance/attestation feature requires a **public** project, which an internal repository is not.

## Facts
- NIST SSDF (Secure Software Development Framework), SP 800-218, is at version 1.1 ("Recommendations for Mitigating the Risk of Software Vulnerabilities"); no newer core revision was found as of 2026-09-24. [DOC S1501]
- SP 800-218A, "Secure Software Development Practices for Generative AI and Dual-Use Foundation Models: An SSDF Community Profile", is a finalized companion profile (2024), not a revision of SP 800-218 — it extends SSDF practices to the development of generative-AI/foundation-model software, which is a closer fit to an MCP-server component than the base SSDF. [DOC S1502]
- SLSA is at spec version 1.0. The Build track defines levels L0-L3: L1 requires provenance to exist; L2 requires a hosted, authenticated build platform generating that provenance; L3 additionally requires the build platform to be isolated and hardened against tampering. [DOC S1503]
- OpenSSF Scorecard is an automated tool that scores an open-source project (0-10) across security-practice checks (branch protection, pinned dependencies, CI permissions, etc.); source at github.com/ossf/scorecard, Apache-2.0 licensed. [DOC S1504]
- SPDX (Software Package Data Exchange) is at spec version 3.0.x, restructured around profiles (core, software, security, build, AI, dataset, licensing, lite). SPDX 2.2.1 corresponds to the ratified ISO/IEC 5962:2021 standard; SPDX 3.0's ISO/IEC submission was still in draft status (DIS) as of this research pass. [DOC S1505]
- CycloneDX is an OWASP-project SBOM format; the 1.x line has continued to add fields (cryptographic assurance, IP visibility) through recent releases. [DOC S1506]
- `uv pip compile --generate-hashes` emits a requirements file (or PEP 751 `pylock.toml`) with every dependency's version pinned and hash recorded. [DOC S1522]
- `pip install`/`pip download --require-hashes` puts pip into hash-checking mode: installation fails unless every requirement, including transitive dependencies, carries a matching hash. [DOC S1507]
- PyPI Trusted Publishing lets a CI job obtain a short-lived PyPI API token via OIDC instead of storing a long-lived token as a secret. Supported OIDC issuers include GitHub Actions, GitLab CI/CD, Google Cloud and ActiveState. [DOC S1508]
- PyPI's *Adding a Trusted Publisher* page states, for GitLab: "Currently, only projects hosted on https://gitlab.com are supported. Self-managed instances are not supported." [DOC S1597] A third-party report claiming support for self-managed instances is contradicted by this page. [COMMUNITY S1510]
- Trusted Publishing configuration on PyPI's side requires the namespace, project path and the exact top-level CI file path (e.g. `.gitlab-ci.yml`) authorized to publish, and the CI job must request an ID token with audience `pypi` via GitLab's `id_tokens:` keyword. [DOC S1525]
- GitLab's SLSA Build Level 3 provenance/attestation feature (behind the `slsa_provenance_statement` flag and the `ATTEST_BUILD_ARTIFACTS` CI/CD variable) requires the **project to be public**, and the attested artifact must be 100 MB or smaller. [DOC S1523]
- GitLab describes its own default DevSecOps pipeline behaviour as reaching SLSA Level 1-2 out of the box, with Level 3 requiring the explicit attestation feature above. [DOC S1524]
- GitLab's dependency-scanning-by-SBOM feature consumes CycloneDX-format SBOM reports produced by build tooling. [DOC S1511]
- GitLab documents pinning CI/CD job images by digest (`image: <name>@sha256:<digest>`) rather than by a mutable tag, because a tag can be overwritten by anyone with registry push access, letting a compromised or rogue image run inside a privileged CI job; pinning tag+digest together lets a bot still update the digest when the referenced image content changes. [DOC S1512]
- DSC v3's resource manifest format has no supply-chain integrity field of its own (see `kb/security/script-and-code-signing.md`); any provenance for a DSC resource distributed with a package has to come from the package/CI supply chain above, not from DSC itself. [DER S1517: manifest schema has no signing/checksum field, so package-level provenance is the only lever]

## Reference
| Mechanism | Relevance | Source |
|---|---|---|
| SSDF SP 800-218 / 800-218A | secure-development baseline; 218A fits an MCP-server component | S1501,S1502 |
| SLSA v1.0 build levels | target level for a configuration repository's/package's CI builds | S1503 |
| PyPI Trusted Publishing | not available for self-managed GitLab; relevant only if the package is published to public PyPI | S1508,S1597 |
| GitLab SLSA attestation | needs a **public** GitLab project; internal repos cannot use it as documented | S1523 |
| uv/pip hash pinning | available today, no GitLab-tier dependency | S1522,S1507 |
| GitLab image digest pinning | available today (CI/CD YAML syntax), no GitLab-tier dependency | S1512 |

## Examples
No fixture-specific configuration; these are packaging/CI-pipeline facts independent of device or tenant fixtures.
