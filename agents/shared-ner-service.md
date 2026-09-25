---
topic: agents/shared-ner-service
priority: P1
applies_to: "Presidio 2.2.364 (main, data-privacy-stack), Azure AI Language PII detection (Foundry Tools, 2026-08 docs), Amazon Comprehend, Google Sensitive Data Protection, GLiNER ONNX exports"
retrieved_utc: 2026-09-25
sources: [S2085, S2086, S2087, S2088, S2089, S2090, S2091, S2092, S2093, S2094, S2095, S2096, S2097, S2098, S2099, S2100, S2101, S2102, S2103, S2104, S2105, S2106, S2107, S2108, S2111, S2112]
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
  path is pinning a frozen image. [DOC S2085, S2086, S2087]
- Presidio's documented deployment targets for the analyzer/anonymizer REST services are Docker Compose,
  Kubernetes/AKS, and Azure App Service; the App Service sample is also what the Presidio team uses for
  its own demo site and dev environment. [DOC S2086, S2088, S2089]
- Presidio's Kubernetes sample can be installed locally with KIND or as a service on AKS; the fetched
  guidance for high-throughput workloads is qualitative only — "set resource limits and horizontal pod
  autoscaling" — with no published requests/sec or p95 latency figure. [DOC S2089 — no numeric throughput
  found, see `gaps.md`]
- Presidio documents a batch path distinct from its REST service: a Spark/Azure Data Factory sample that
  anonymizes files at rest in Azure Blob Storage for large-dataset (Databricks-scale) jobs, i.e. batch
  and the interactive REST endpoint are two separate documented deployment shapes, not one endpoint doing
  both. [DOC S2090]
- Presidio and its images are MIT-licensed (`Presidio Contributors`), so a shared internal deployment
  carries no per-call licence fee; the operating cost is host/cluster compute only. [DOC S2085, S2086]
- **Azure AI Language PII containers.** The on-premises container image is
  `mcr.microsoft.com/azure-cognitive-services/textanalytics/pii`; minimum host spec is 1 core/2 GB, the
  recommended spec is 4 cores/8 GB, and Microsoft recommends AVX-512 for best performance and accuracy —
  the only vendor-published hardware sizing figure found across the four cloud/managed options. [DOC S2091]
- The container exposes REST endpoints on port 5000 (`/`, `/ready`, `/status`, `/swagger`) usable as
  Kubernetes liveness/readiness probes, so it is designed to be run as a shared internal service, not
  just a demo. [DOC S2091]
- The container is **not** offline-capable by default: it must reach Azure's billing endpoint, reports
  usage every 10-15 minutes, retries up to 10 times at that interval, and **stops serving requests** if it
  cannot reach the billing endpoint within that window — a documented fail-closed behaviour on connectivity
  loss. [DOC S2091]
- A fully disconnected deployment exists but requires a separate application, an approved commitment
  plan, and a downloaded, time-limited licence file (`DownloadLicense=True`) mounted into the container;
  the licence has an expiration date after which the container stops validating. [DOC S2091]
- Per-call data limit for the synchronous Text PII container API: **5,120 characters per document, up to
  10 documents per call**. [DOC S2091]
- The cloud (non-container) Text PII API analyzes only the first 50,000 characters of an over-length
  input and issues a warning rather than failing; conversational PII caps at 1,000 characters per
  conversation *item* (not per whole conversation); document file-size limit is up to 10 MB. [DOC S2093
  — figures as summarized via search index, not independently re-verified against the live page]
  *(see `conflicts.md` for the 50,000-char figure's provenance)*
- Explicit non-customization note: "Analysis is performed as-is, with no customization to the model used
  on your data" for the cloud PII feature family (text, conversation, document). [DOC S2092]
- Text PII added preview entity types (Password, PIN code, Zip code, Airport code) in the
  **2026-04-15-preview** API version — a concrete example of model/version drift a shared consumer must
  pin against, since a caller built on an older API version would not see these categories. [DOC S2096]
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
- Comprehend PII coverage: 22 universal entity types (name, age, email, IP/MAC address, AWS access key,
  etc.) plus 14 country-specific types (e.g. US SSN, UK taxpayer reference), added in a 2022-05
  announcement extending coverage to the US, UK, Canada and India. [DOC S2097, S2107]
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
  `SemplificaAI/gliner2-multi-v1-onnx`) exist on Hugging Face; a fused ("v2") export variant reportedly
  cuts inference latency by roughly 30% on discrete GPUs by keeping tensors resident in device memory via
  ONNX Runtime IO binding — a community-reported, not vendor-benchmarked, figure. [COMMUNITY S2102, S2103]
- No first-party GLiNER "service" or REST deployment image (analogous to Presidio's analyzer/anonymizer
  containers) was found; GLiNER serving is assembled by the deployer from a model export plus a generic
  inference runtime (ONNX Runtime, Rust engine, etc.), unlike Presidio or Azure's pre-built containers.
  [DER from S2102, S2103: only model artifacts found, no first-party server image]
- **Model/version pinning across consumers.** Presidio's own evaluation tooling
  (`presidio-evaluator`/`presidio-research`, MIT) computes precision/recall/F-β for a recognizer or NER
  model and is the documented method for comparing detection quality between versions or between
  deployments, but the fetched docs describe single-run evaluation, not a continuous drift-monitoring
  pipeline between multiple independent consumers of one shared endpoint. [DOC S2104, S2105, S2111]

## Reference
| Option | On-prem/offline container | Fail mode on connectivity loss | Per-call payload limit | Licence |
|---|---|---|---|---|
| Presidio (own images) | yes, no metering call | n/a (self-hosted, no phone-home) | not published | MIT |
| Azure AI Language PII container | yes, needs billing endpoint (or approved disconnected licence) | stops serving after ~10 failed 10-15 min retries | 5,120 chars/doc, 10 docs/call | commercial, metered |
| Amazon Comprehend | no (API only) | n/a (cloud API) | not found (min 300-char billing unit) | commercial, metered |
| Google Sensitive Data Protection | not found | n/a (cloud API) | not found | commercial, metered (per GB) |
| GLiNER (ONNX export) | yes, self-hosted, any runtime | n/a (self-hosted) | not published (deployer-defined) | model-card dependent |

## Examples
A hypothetical shared endpoint serving both an example project's agent and another team's agent, presented with the fixture
text "engineer jan.kowalski opened a case for PL-LT-00123 at corp.example.com", would need the same API
version and recognizer set pinned on both sides to guarantee identical entity spans; a version bump like
Azure's 2026-04-15-preview addition of new entity types is exactly the kind of drift this file's QG32
counterpart discusses. Not run against a live service.
