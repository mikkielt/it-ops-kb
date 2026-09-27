---
topic: agents/shared-ner-service
priority: P1
applies_to: "Presidio 2.2.364 (main, data-privacy-stack), Azure AI Language PII detection (Foundry Tools, 2026-08 docs), Amazon Comprehend, Google Sensitive Data Protection, GLiNER ONNX exports"
retrieved_utc: 2026-09-27
sources: [S2086, S2087, S2088, S2090, S2091, S2092, S2093, S2094, S2095, S2096, S2097, S2098, S2099, S2100, S2101, S2102, S2105, S2106, S2107, S2108, S2111, S2112, S-tks3v5p5, S-g33kybfp, S-gpnrqpjt, S-hocpkynn, S-azdam24d, S-blcom642, S-clgh6hxa]
status: partial
---

# Shared NER / PII-detection as a service: options, throughput, cost and pinning

## Summary
Every option surveyed — Presidio's own REST images, Azure AI Language's PII containers, Amazon
Comprehend, Google Sensitive Data Protection, and a GLiNER ONNX export — can run as a shared endpoint,
but each moves the trust boundary differently. Presidio's own containers are the only option that can
run fully offline with no metering call; Azure's on-prem container still phones home for billing every
10-15 minutes and stops serving after ~10 missed windows; Comprehend and Google DLP have no on-prem
container option in the sources found. None of the vendor pages fetched publish a throughput number
(requests/sec or documents/min) for the shared-service case — see `gaps.md`. An example project's own
choice (Presidio + spaCy `en_core_web_lg`, in-process) is not itself re-argued here.

## Facts

### QG30 — deployment shapes, throughput, limits, licensing, pinning
- **Presidio own service images.** New Presidio container releases publish to
  `ghcr.io/data-privacy-stack/presidio-analyzer` / `presidio-anonymizer`; the legacy
  `mcr.microsoft.com/presidio-*` images are no longer updated, so a consumer pinning the old registry
  path is pinning a frozen image; for production the installation guide prefers pinning an explicit
  release tag. Presidio is transitioning to a community-owned project under the Data Privacy Stack
  organization (`github.com/data-privacy-stack/presidio`); the Kubernetes Helm sample
  pulls the default images from `ghcr.io/data-privacy-stack`. [DOC S-azdam24d, S-clgh6hxa, S2087, S-g33kybfp] The sample and
  evaluation pages cited here now live under `presidio.dataprivacystack.org`; their old
  `microsoft.github.io/presidio/...` paths returned 404 on 2026-09-26. [DER S-tks3v5p5, S-g33kybfp, S-gpnrqpjt: direct fetch of old and new urls]
- Presidio's Docker sample exposes each service as a Flask REST endpoint: the analyzer on port 5002
  (`POST /analyze`) and the anonymizer on port 5001 (`POST /anonymize`). [DOC S-tks3v5p5, S2086]
- Presidio's documented deployment targets for the analyzer/anonymizer REST services are Docker Compose,
  Kubernetes/AKS, and Azure App Service; the App Service sample is also what the Presidio team uses for
  its own demo site and dev environment. [DOC S-azdam24d, S2088, S-g33kybfp]
- Presidio's Kubernetes sample installs locally with KIND or as a Helm-deployed service on Kubernetes 1.18+
  with RBAC (AKS enables RBAC by default), with an NGINX ingress by default; its only sizing guidance is a
  note to check the pods' CPU and memory requirements and plan the cluster accordingly — no autoscaling
  guidance and no published requests/sec or p95 latency figure. [DOC S-g33kybfp — no numeric throughput
  found, see `gaps.md`]
- Presidio's Azure Data Factory sample documents two batch shapes: the pipeline calls Presidio's analyzer
  and anonymizer REST endpoints (hosted on App Service, or another target such as Kubernetes) for each
  document, or a Databricks Spark job runs Presidio as a Python package over files in Azure Blob Storage
  when the dataset needs Databricks scale. [DOC S2090]
- Presidio is MIT-licensed (copyright `Presidio Contributors`). [DOC S-blcom642]
- So a shared internal Presidio deployment carries no per-call licence fee; the operating cost is
  host/cluster compute only. [DER S-blcom642: the MIT licence grants use free of charge]
- **Azure AI Language PII containers.** The on-premises container image is
  `mcr.microsoft.com/azure-cognitive-services/textanalytics/pii`; minimum host spec is 1 core/2 GB, the
  recommended spec is 4 cores/8 GB, and Microsoft recommends AVX-512 for best performance and accuracy —
  the only vendor-published hardware sizing figure found across the four cloud/managed options. [DOC S2091]
- The container exposes REST endpoints on port 5000: a home page (`/`), `/ready` and `/status` (both
  usable as Kubernetes liveness/readiness probes) and `/swagger` documentation. [DOC S2091]
- The container is **not** offline-capable by default: it must reach Azure's billing endpoint, reports
  usage every 10-15 minutes, retries up to 10 times at that interval, and **stops serving requests** if it
  cannot reach the billing endpoint within that window — a documented fail-closed behaviour on connectivity
  loss. [DOC S2091]
- A fully disconnected deployment exists but requires a separate application, an approved commitment
  plan, and a downloaded, time-limited licence file (`DownloadLicense=True`) mounted into the container;
  the licence has an expiration date after which the container stops validating. [DOC S2091]
- In disconnected mode the container writes usage records to a mounted output volume and reports them at `/records/usage-logs/` (and per month); the commitment plan runs for a calendar year, is charged in full at purchase and cannot be changed during the period, though more units can be bought pro rata. [DOC S2094]
- Per-call data limit for the synchronous Text PII container API: **5,120 characters per document, up to
  10 documents per call**. [DOC S2091]
- The cloud (non-container) service limits for PII: synchronous requests take up to 5,120 characters per
  document and 5 documents per request (1 MB per request); an over-length document gets an invalid-document
  error while the rest of the request is processed. Asynchronous requests take up to 125,000 characters
  across at most 25 documents, and one over-length document rejects the whole request with HTTP 400.
  Conversation PII caps at 1,000 characters per conversation *item* (not per whole conversation) and is
  asynchronous only. [DOC S2093]
- A cloud Text PII behaviour of analyzing only the first 50,000 characters with a warning, and a 10 MB
  document file-size limit, were recorded earlier from a search summary. [UNK: not in S2093 as re-read
  2026-09-27; see `conflicts.md`]
- The cloud Language service may store data sent in synchronous or asynchronous calls for up to 48 hours (encrypted, reachable only by on-call engineers for catastrophic-failure debugging); the `LoggingOptOut` parameter prevents this and defaults to true for the PII and health endpoints; data stays in the resource's region. [DOC S2106]
- Synchronous PII detection is stateless: nothing is stored in the account and results, including the input text with PII entities redacted, come back in the response; asynchronous results stay retrievable for 24 hours and are then purged. [DOC S2112]
- Explicit non-customization note: "Analysis is performed as-is, with no customization to the model used
  on your data" for the cloud PII feature family (text, conversation, document). [DOC S2092]
- Text PII lists two supported API versions, stable **2026-05-01** (GA) and **2026-05-15-preview**, and marks
  some entity types as preview (among them Password, ZipCode, Airport, DateOfBirth, PassportNumber, CVV and
  VIN) — a concrete example of model/version drift a shared consumer must pin against. [DOC S2096]
- Pricing model: **text records** (1,000 characters = 1 record), 5,000 records/month free across
  several Language features including PII, then per-1,000-record tiered pricing that steps down at
  0.5M-2.5M / 2.5M-10M / 10M+ volumes; the container/commitment path prices annual disconnected licences
  by total yearly record volume (documented tiers, e.g. ~120M or ~36M records/year) rather than per call.
  Exact currency amounts were not retrieved (pricing calculator gated). [DOC S2095 — see `gaps.md` for
  the unresolved dollar figures]
- Microsoft's stated no-retention posture: "Foundry Tools containers don't send customer data, such as
  the image or text that's being analyzed, to Microsoft" — billing telemetry only, not payload. [DOC
  S2091]
- **Amazon Comprehend** offers two relevant calls: `ContainsPiiEntities` (boolean/coarse) and
  `DetectPiiEntities` (per-entity offsets) over a single document; there is no Comprehend on-premises
  container in the sources found — it is API-only. [DOC S2097, S2098]
- Comprehend PII coverage: 36 entity types, the 22 it had before 2022-05 (financial, personal,
  technical-security and national categories, e.g. credit card number, name, email, password, SSN,
  passport number) plus 14 added on 2022-05-23 with localized types for the US, UK, Canada and India
  (e.g. US ITIN, UK Unique Taxpayer Reference, Canada SIN, India Aadhaar) and others such as VIN, SWIFT
  code and IBAN. [DOC S2097, S2107]
- Comprehend pricing unit is 100 characters (1 unit), with a 3-unit (300-character) minimum charge per
  request — i.e. even a very short document is billed as at least 300 characters. [DOC S2099]
- **Google Sensitive Data Protection** (the current name for Cloud DLP; API name unchanged) ships over
  200 built-in infoType detectors. [DOC S2100, S2108]
- Google's published rate schedule (USD, per GiB per month per account, first GiB free in each
  schedule) is by bytes and by mode: **content methods** (`content.inspect`/`deidentify`/`reidentify`,
  `image.redact`) US$3.00 inspected and US$2.00
  transformed up to 1 TiB, then US$2.00 / US$1.00, with a 1 KB minimum per request; **hybrid jobs**
  (data from any source) US$3.00 then US$2.00 above 1 TiB; **storage inspection/transformation jobs**
  US$1.00 up to 50 TiB, US$0.75 to 500 TiB, US$0.60 above; **discovery** (data profiling) US$0.03 per GB
  profiled in consumption mode, or US$2,500 per subscription unit. [DOC S2101]
- No on-premises container or disconnected deployment for Google Sensitive Data Protection was found in
  the sources checked; it is presented in vendor docs as a Google Cloud-hosted API only. [UNK — 3 search
  attempts made, no container doc found]
- **GLiNER serving.** Community ONNX exports of GLiNER (e.g. `onnx-community/gliner_multi-v2.1`,
  `jugaadsrl/gliner2-multi-v1-onnx`, formerly `SemplificaAI/gliner2-multi-v1-onnx`, a fragmented export for the
  `gliner2-rs` Rust engine) exist on Hugging Face; a fused ("v2") export variant reportedly
  cuts inference latency by roughly 30% on discrete GPUs by keeping tensors resident in device memory via
  ONNX Runtime IO binding — a community-reported, not vendor-benchmarked, figure. [COMMUNITY S2102, S-hocpkynn]
- No first-party GLiNER "service" or REST deployment image (analogous to Presidio's analyzer/anonymizer
  containers) was found; GLiNER serving is assembled by the deployer from a model export plus a generic
  inference runtime (ONNX Runtime, Rust engine, etc.), unlike Presidio or Azure's pre-built containers.
  [DER from S2102, S-hocpkynn: only model artifacts found, no first-party server image]
- **Model/version pinning across consumers.** Presidio's own evaluation tooling
  (`presidio-evaluator`/`presidio-research`, MIT) computes precision/recall/F-β for a recognizer or NER
  model and is the documented method for comparing detection quality between versions or between
  deployments, but the fetched docs describe single-run evaluation, not a continuous drift-monitoring
  pipeline between multiple independent consumers of one shared endpoint; the evaluation page recommends
  F-beta with β=2 because recall usually matters more than precision in PII detection. [DOC S-gpnrqpjt, S2105, S2111]

## Reference
| Option | On-prem/offline container | Fail mode on connectivity loss | Per-call payload limit | Licence |
|---|---|---|---|---|
| Presidio (own images) | yes, no metering call | n/a (self-hosted, no phone-home) | not published | MIT |
| Azure AI Language PII container | yes, needs billing endpoint (or approved disconnected licence) | stops serving after ~10 failed 10-15 min retries | 5,120 chars/doc, 10 docs/call | commercial, metered |
| Amazon Comprehend | no (API only) | n/a (cloud API) | 100 KB of UTF-8 text per real-time call (min 300-char billing unit) [DOC S2097, S2098, S2099] | commercial, metered |
| Google Sensitive Data Protection | not found | n/a (cloud API) | not found | commercial, metered (per GB) |
| GLiNER (ONNX export) | yes, self-hosted, any runtime | n/a (self-hosted) | not published (deployer-defined) | model-card dependent |

## Examples
A hypothetical shared endpoint serving both an example project's agent and another team's agent, presented with the fixture
text "engineer jan.kowalski opened a case for PL-LT-00123 at corp.example.com", would need the same API
version and recognizer set pinned on both sides to guarantee identical entity spans; a version bump like
Azure's 2026-04-15-preview addition of new entity types is exactly the kind of drift this file's QG32
counterpart discusses. Not run against a live service.
