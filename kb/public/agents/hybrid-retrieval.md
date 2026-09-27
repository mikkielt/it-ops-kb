---
topic: agents/hybrid-retrieval
priority: P2
applies_to: "Azure AI Search hybrid/vector/semantic search (api-version 2026-04-01, retrieved 2026-09-26); Anthropic Contextual Retrieval (engineering post, retrieved 2026-09-26); pgvector (README/LICENSE at master, retrieved 2026-09-26); Elasticsearch RRF retriever (docs, retrieved 2026-09-26); Claude API search result blocks (retrieved 2026-09-27); doc2query and Doc2Query-- papers; Model2Vec v0.9.0; Sufficient Context paper; Anthropic reduce-hallucinations guide; Azure AI Search traffic analytics (retrieved 2026-09-27)"
retrieved_utc: 2026-09-27
sources: [S-pgtfj4fh, S-btrwp2yj, S-dh75h5qt, S-jt6qyh46, S-jaycbw5k, S-net4uvqm, S-idqwhfg2, S-z7wh2sbr, S-4hditql5, S-524t5qtl, S-76smovmo, S-fn6fxrr5, S-4c46o537, S2135, S-qpqoaaqj, S-jnq56sj3, S-sqbfbcyk, S-aqnin65g, S-yi5xka25, S-fovhkyzc, S-enf2tnxi]
status: complete
---

# Hybrid retrieval for agents and RAG

## Summary
Hybrid retrieval combines a lexical ranker (BM25 or Elasticsearch's equivalent) with a vector (embedding) search and fuses the two ranked lists with Reciprocal Rank Fusion (RRF); a second-stage reranker (Azure's semantic ranker, which uses deep learning models adapted from Bing) can then rescore the fused top results [DOC S-pgtfj4fh, S-btrwp2yj, S-jt6qyh46]. Anthropic's Contextual Retrieval improves the inputs to that pipeline rather than the fusion itself: prepending a short LLM-written context string to each chunk before embedding and before BM25 indexing, at about $1.02 per million document tokens with prompt caching [DOC S-4hditql5]. pgvector adds HNSW/IVFFlat vector indexes and L2, inner-product, cosine and L1 distance operators (plus Hamming and Jaccard for binary vectors) to Postgres under a PostgreSQL-style permissive licence [DOC S-524t5qtl, S-76smovmo]. Elasticsearch exposes RRF as a top-level `retriever` that fuses two or more child retrievers with the same `1/(k+rank)` formula Azure uses, defaulting `rank_constant` to 60 [DOC S-fn6fxrr5]. This kb's own `rag.py pack` is a single-signal BM25-over-facts ranker with a doc2query expansion layer, not a hybrid or RRF system [DER — see Reference]. Around the ranker: document expansion (doc2query, filtered as Doc2Query--) widens lexical recall at index time [DOC S-jnq56sj3, S-sqbfbcyk]; static embedding models (Model2Vec) give a vector signal without a transformer at query time [DOC S-aqnin65g]; a sufficiency check before answering lets a reader abstain when the retrieved context does not answer the question [DOC S-yi5xka25, S-fovhkyzc]; and search traffic analytics logs user queries and clicks to find zero-result queries [DOC S-enf2tnxi].

## Facts

### Azure AI Search: hybrid query and RRF
- A hybrid query is one request with both a `search` (full-text) parameter and one or more `vectorQueries`; the two run in parallel and Azure AI Search merges the ranked lists with RRF into a single `@search.score` per document [DOC S-pgtfj4fh].
- Full-text scoring uses BM25 (no fixed upper bound on `@search.score`); vector scoring uses HNSW or exhaustive KNN (eKNN) with a similarity metric, ranging 0.333-1.00 for cosine or 0-1 for Euclidean/dotProduct; RRF's fused `@search.score` is bounded by the number of fused queries, each contributing up to about `1/k` [DOC S-pgtfj4fh, S-dh75h5qt, S-btrwp2yj].
- RRF formula: for each document, `score = 1/(rank + k)` per ranked list it appears in, summed across lists; Azure's documentation says experiments show RRF performs best with a small `k` such as 60, and this `k` is unrelated to the vector query's `k` (nearest-neighbor count) [DOC S-btrwp2yj].
- Parallel query count multiplies fast: one full-text query plus one vector query = 2 executions; one full-text query plus two vector queries over 5 fields = 11 executions, since RRF fuses every one of them [DOC S-btrwp2yj].
- A vector query weight (`weight`, default 1.0) multiplies that query's contribution to the RRF sum before summing, letting a vector or text signal count for more or less in the fused score [DOC S-btrwp2yj].
- Hybrid query defaults: without pagination, up to the top 50 highest-ranked full-text matches and the top `k` vector matches feed the fusion; `top` controls page size of the fused response; full-text recall is capped at 1,000 matches by default, raisable via `maxTextRecallSize` [DOC S-btrwp2yj].
- Recommended request shape sets `vectorQueries[].k: 50` when semantic ranker is also used, to maximize its input pool, and omits `orderby` because an explicit sort order overrides relevance ranking [DOC S-pgtfj4fh].

### HNSW / eKNN vector index (Azure AI Search)
- Azure AI Search uses HNSW as its ANN algorithm; fields indexed for HNSW also support exhaustive KNN per-query via `"exhaustive": true`, but fields indexed only for `exhaustiveKnn` cannot later run HNSW queries [DOC S-dh75h5qt].
- Build-time HNSW parameters: `m` (max connections per node) and `efConstruction`, whose default is 400 with an allowed range of 100 to 1,000; higher `efConstruction` produces denser local neighborhoods at higher build cost [DOC S-dh75h5qt].
- Query-time HNSW parameter: `efSearch` sizes the candidate priority queue during graph traversal; the `k` request parameter sets the number of nearest neighbors to return [DOC S-dh75h5qt].
- Similarity metrics: `cosine` (angle only; matches Azure OpenAI embeddings), `dotProduct` (equivalent to cosine for normalized vectors, slightly faster), and `euclidean`/L2 [DOC S-dh75h5qt].

### Semantic ranker (L2 reranking)
- Semantic ranker reranks only the top 50 results of a prior BM25 or RRF ranking; it cannot rerun the query over the full corpus and only reorders that existing set [DOC S-jt6qyh46].
- Per-document input to the summarization step is capped at 2,000 tokens (~10 characters/token), built from `title` (128 tokens), `keywords` (128 tokens) and `content` (remaining tokens) fields in priority order from the semantic configuration; the resulting summary string sent to the ranker is capped at 2,048 tokens (raised from 256 tokens as of November 2024) [DOC S-jt6qyh46].
- `@search.rerankerScore` ranges 0.0-4.0 (4.0 = highly relevant and complete answer, 0.0 = irrelevant), reported separately from the RRF/BM25 `@search.score` [DOC S-jt6qyh46, S-btrwp2yj].
- Semantic ranker offers a free monthly quota with pay-as-you-go billing beyond it; it is billed only when `queryType=semantic` and the search string is non-empty (`search=*` incurs no charge even under `queryType=semantic`) [DOC S-jt6qyh46].
- Query rewrite (preview) generates up to 10 semantically similar query variants before scoring, run through the same BM25/RRF pipeline and then reranked [DOC S-jt6qyh46].
- Throttling: semantic ranker uses a per-tier queue (e.g. Basic: 2 concurrent requests and a queue of 4 per search unit; S1: 3 concurrent and a queue of 6; S2/S3/S3 HD/L1/L2: 4 concurrent and a queue of 8; Serverless Developer: 4 and 8 per service), beyond which requests are rejected and must be retried [DOC S-jaycbw5k].

### Integrated vectorization, chunking, embeddings
- Integrated vectorization is an indexer-pipeline feature that chunks and embeds content during indexing and can also vectorize the query string at search time, via a skillset with a chunking skill (Text Split or Azure Content Understanding) followed by an embedding skill [DOC S-net4uvqm].
- Recommended chunking drivers: keep chunks under the embedding/chat model's max input tokens (e.g. `text-embedding-3-small` accepts up to 8,191 input tokens, roughly 6,000 words), and add overlap to preserve context across chunk boundaries [DOC S-idqwhfg2].
- Azure OpenAI Embedding skill supports `text-embedding-ada-002` (fixed 1,536 dimensions), `text-embedding-3-large` (1-3,072 dimensions via the optional `dimensions` parameter) and `text-embedding-3-small` (1-1,536 dimensions); the vector field's `dimensions` property must match the skill's `dimensions` setting [DOC S-z7wh2sbr].

### Azure AI Search tier and vector index limits
- Vector index size is a hard per-partition quota (Dedicated) or per-index quota (Serverless); exceeding it fails further indexing until vectors are deleted, dimensionality is reduced, or (Dedicated) partitions are added [DOC S-jaycbw5k].
- Vector quota per partition (services created after May 17, 2024): Basic 5 GB, S1 35 GB, S2 150 GB, S3/S3 HD 300 GB, L1 150 GB, L2 300 GB; Serverless Developer caps vector index size at 300 MB per index (about 30% of that tier's total index storage) [DOC S-jaycbw5k].
- Maximum dimensions per vector field: 4,096, across every tier including Serverless Developer [DOC S-jaycbw5k].
- Maximum vector fields per query: 10 [DOC S-jaycbw5k].
- Maximum indexes per service: Basic 5 or 15 (creation-date dependent), S1 50, S2/S3 200, S3 HD 1,000/partition or 3,000/service, L1/L2 10, Serverless Developer 30 [DOC S-jaycbw5k].
- Maximum index size for S2 1.88 TB, S3 2.34 TB, S3 HD 100 GB, Serverless Developer 1 GB (services created after April 3, 2024) [DOC S-jaycbw5k].
- Search-query throttling on Serverless: 50 queries/sec aggregate per index; on Dedicated it varies by search-unit count and query complexity [DOC S-jaycbw5k].

### Anthropic Contextual Retrieval
- Baseline top-20-chunk retrieval failure rate on Anthropic's evaluation set was 5.7% [DOC S-4hditql5].
- Contextual Embeddings alone (prepending a short LLM-generated, chunk-specific context string before embedding) reduced the failure rate by 35%, to 3.7% [DOC S-4hditql5].
- Contextual Embeddings + Contextual BM25 (the same contextualization applied before BM25 indexing too) reduced the failure rate by 49%, to 2.9% [DOC S-4hditql5].
- Contextual Embeddings + Contextual BM25 + reranking reduced the failure rate by 67%, to 1.9% [DOC S-4hditql5].
- The context-generation prompt (run once per chunk, via Claude 3 Haiku in Anthropic's test) produces roughly 50-100 tokens of prepended context per chunk; using prompt caching for the shared document context, the one-time cost to contextualize a corpus is about $1.02 per million document tokens [DOC S-4hditql5].

### Claude API citations from search results
- `search_result` content blocks let Claude cite an application's own retrieved content like web search results; they are part of the standard Messages API (no beta header) and every active model supports them except Claude Haiku 3 [DOC S-4c46o537].
- A `search_result` block needs `type`, `source` (any stable string: a URL or an internal id such as `kb://article-1234`), `title` and `content` (an array of non-empty text blocks, text only); `citations` and `cache_control` are optional, and citations are off unless `citations.enabled` is `true`, with one setting for all search results in a request [DOC S-4c46o537].
- Search results can come from a custom tool's `tool_result` or be placed directly in a user message; a `tool_result` that contains any `search_result` block must contain only `search_result` blocks, and assistant messages cannot carry them [DOC S-4c46o537].
- Each citation is a `search_result_location` with `source`, `title`, `cited_text` (not counted as output tokens), `search_result_index` (0-based across all search results in the request) and `start_block_index`/`end_block_index`; Claude cites whole text blocks, so smaller blocks give finer citations [DOC S-4c46o537].
- Search result blocks are available on the Claude API, Amazon Bedrock and Google Cloud [DOC S-4c46o537].
- MCP's tool result content types are text, image, audio, resource links and embedded resources (2026-07-28 revision); the protocol has no search-result or citation content type [DOC S2135].
- A client that wants citations from an MCP server's results has to convert them into `search_result` blocks itself: the search-results page takes such blocks only from the caller's own `tool_result` content and never mentions MCP, the MCP connector page's `mcp_tool_result` example carries only a text block, and no Claude Code or Agent SDK page read on 2026-09-27 documents a conversion [DER S-4c46o537, S-qpqoaaqj, S2135: documented block sources compared; absence on the pages read].
- A kb fact line (path:line, tag, source url) maps directly onto one `search_result` block (`source` = the source url, `title` = the article, one text block per fact), which would let an API client get per-fact citations from `rag.py pack` output [DER S-4c46o537: block fields compared with the pack's line format].

### pgvector
- pgvector's `LICENSE` file is the PostgreSQL-style permissive licence: Portions Copyright the PostgreSQL Global Development Group and the Regents of the University of California, with permission to use, copy, modify and distribute without fee as long as the copyright notice and the licence paragraphs are kept [DOC S-76smovmo].
- Vector type maximum dimensions: 16,000 for `vector` and `halfvec`; `bit` (binary vectors) up to 64,000 dimensions; `sparsevec` up to 16,000 non-zero elements [DOC S-524t5qtl].
- Distance operators: `<->` L2/Euclidean distance, `<=>` cosine distance, `<#>` negative inner product (use for max inner product ranking), `<+>` L1/taxicab distance [DOC S-524t5qtl].
- Without an index, pgvector performs exact nearest-neighbor search (perfect recall); adding an HNSW or IVFFlat index switches to approximate search, trading some recall for speed [DOC S-524t5qtl].
- HNSW build parameters: `m` (max connections per graph layer, default 16) and `ef_construction` (build-time candidate list size, default 64) [DOC S-524t5qtl].
- HNSW query-time parameter: `hnsw.ef_search` (candidate list size at search time, default 40) [DOC S-524t5qtl].
- IVFFlat build parameter: `lists` (number of inverted lists; guidance is `rows / 1000` for up to 1M rows, `sqrt(rows)` above that); query-time parameter `ivfflat.probes` (lists searched per query, default 1; guidance starts at `sqrt(lists)`) [DOC S-524t5qtl].

### Elasticsearch RRF retriever
- RRF is exposed as a top-level `rrf` retriever that fuses two or more child retrievers (e.g. a `standard` BM25 retriever and a `knn` retriever) using the same formula as Azure: `score += 1.0 / (k + rank(result(q), d))`, summed per document across each retriever's ranked list [DOC S-fn6fxrr5].
- Defaults: `rank_constant` = 60 (higher values increase the influence of lower-ranked documents); `rank_window_size` defaults to the request's `size` and sets how many results per child retriever are pooled for fusion [DOC S-fn6fxrr5].
- A minimum of two child retrievers is required; `scroll`, `sort` and `rescore` cannot be combined with the RRF retriever, and supplying a point-in-time explicitly is discouraged because RRF creates its own internally [DOC S-fn6fxrr5].
- Every child retriever carries equal weight in the RRF sum [DOC S-fn6fxrr5].
- Azure AI Search's RRF instead accepts a per-vector-query `weight` (default 1.0) that scales a query's contribution before summing — a per-retriever knob Elasticsearch's RRF retriever does not document [DER S-fn6fxrr5, S-btrwp2yj: contrast between the two vendors' documented RRF parameters].

### Document expansion: doc2query and Doc2Query--
- doc2query expands each document before indexing with queries a sequence-to-sequence model predicts it answers, the model being trained on pairs of queries and relevant documents; with a re-ranker it set the state of the art on two retrieval tasks, and without re-ranking it approached the effectiveness of neural re-rankers at much lower latency. [DOC S-jnq56sj3]
- Doc2Query-- argues that the generated queries include hallucinated content that harms retrieval and inflates the index, and filters them before indexing with a relevance model: up to 16% better retrieval effectiveness than Doc2Query, 23% lower mean query execution time and a 33% smaller index. [DOC S-sqbfbcyk]
- This kb's filter is a variant: it keeps a generated question only when `pack` without expansion already routes it to the fact's article, a lexical self-consistency test rather than a relevance model, so an expansion can re-rank lines inside an article the lexical ranker already reaches but cannot bridge vocabulary it does not. [DER S-sqbfbcyk: filter compared with `kb/_self/doc2query.md`]

### Static embeddings: Model2Vec
- Model2Vec turns a sentence transformer into a static embedding model: the README states models up to 50 times smaller and up to 500 times faster, "with a small drop in performance". [DOC S-aqnin65g]
- Distillation forward-passes a vocabulary through the sentence transformer to create static embeddings for the individual tokens, then post-processes them; it needs no dataset, only a vocabulary and a model, and takes about 30 seconds on a CPU. [DOC S-aqnin65g]
- The base `model2vec` package's only major dependency is `numpy`; the README gives about 30 MB on disk for its best model and about 8 MB for its smallest, and a 2025-05-01 update says models can be quantized to int8 at 25% of the original size without loss of performance. [DOC S-aqnin65g]
- Published models at v0.9.0 (2026-08-12, MIT) include `potion-base-2M`, `-4M`, `-8M` and `-32M` (English, distilled from `bge-base-en-v1.5`), `potion-retrieval-32M` (a retrieval fine-tune of `potion-base-32M`) and `potion-multilingual-128M` (101 languages, from `bge-m3`). [DOC S-aqnin65g]
- Because the vectors are per token and precomputed, a query embedding needs a token lookup rather than a transformer forward pass; a table of such vectors could be shipped as data beside a lexical index as a second, RRF-fusable signal, though the package itself needs `numpy`. [DER S-aqnin65g, S-btrwp2yj: static token vectors plus the RRF fusion rule above]

### Answer sufficiency and abstention
- The Sufficient Context paper separates RAG errors into a model failing to use the context and the context being insufficient, with a method to classify whether a query-context pair has enough information to answer. [DOC S-yi5xka25]
- It finds larger models (Gemini 1.5 Pro, GPT 4o, Claude 3.5) answer well when the context is sufficient but often answer incorrectly instead of abstaining when it is not, while smaller models (Mistral 3, Gemma 2) hallucinate or abstain often even with sufficient context. [DOC S-yi5xka25]
- A selective-generation method that uses the sufficiency signal for guided abstention raised the fraction of correct answers among responses by 2-10% for Gemini, GPT and Gemma. [DOC S-yi5xka25]
- Anthropic's guidance to reduce hallucinations: explicitly allow Claude to say "I don't know"; for documents over 20k tokens, have it extract word-for-word quotes before the task; have it cite a supporting quote for each claim and retract claims it cannot support; best-of-N comparison flags inconsistencies. [DOC S-fovhkyzc]
- `_tools/kb_ask.py` applies this pattern: its tool-less reader answers `INSUFFICIENT` when the packed facts are only related to the question, and the router escalates instead of answering. [DER S-yi5xka25, S-fovhkyzc: compared with `kb/_self/tools.md`, "`kb_ask.py` routing"]

### Query logging: search traffic analytics
- Azure AI Search's search traffic analytics pattern collects telemetry on user interactions (clickstream events, keyboard inputs) to measure clickthrough rate and find which query inputs yield zero results; it sends custom events to Application Insights. [DOC S-enf2tnxi]
- Log only user-initiated searches: requests that populate facets or fetch internal information skew or bias the results. [DOC S-enf2tnxi]
- Search and click events are correlated through a search id sent as the `x-ms-client-request-id` header; each search event carries `SearchId`, `SearchServiceName`, `IndexName`, `SearchText` and `ResultCount`. [DOC S-enf2tnxi]
- The portal's Search Traffic Analytics page is outdated and references an obsolete client library; the page points to the `azure-search-traffic-analytics` samples instead, and recommends service logs (no code, including search terms) for all scenarios. [DOC S-enf2tnxi]
- For a kb lookup tool the same log maps onto a pack call: the question as `SearchText`, the verdict (`none` as the zero-result case) and top article in place of `ResultCount`, and the answer's outcome (answered, escalated, corrected) in place of a click. [DER S-enf2tnxi: event schema mapped onto `pack` output]

## Reference
- This kb's own lookup tool, `_tools/rag.py pack` (and the `kb_pack` MCP tool), ranks fact bullets and table rows with a single BM25-style score over the kb's tagged facts, then optionally widens recall with LLM-generated `doc2query` expansion questions matched against the same index; it runs one ranker, not two independently-ranked lists, so it has no RRF fusion step and no separate reranking pass — it is closer to Azure's or Elasticsearch's lexical (BM25) leg alone, extended by doc2query rather than by a vector leg or a cross-encoder reranker [DER — `_self/reports/token-usage.md`, "Lookup tools against reading files" and "doc2query", describing `rag.py`'s design and measured behavior, not an external DOC source].
- `_self/reports/token-usage.md`'s doc2query measurement: in round 1 expansion raised pilot facts found in the pack from 36/40 to 39/40, with the weight tuned on those test questions; on fresh articles in round 2 it found 38/40 with and without expansion. It never changed a verdict and made packs slightly smaller; the two rounds' expansions stay indexed and the rest of the kb is not expanded [DER — same report, "doc2query"].
- See `agents/agent-caching.md` for Anthropic prompt caching mechanics (breakpoints, TTLs, invalidation order) that make Contextual Retrieval's context-generation step cost about $1.02/million document tokens rather than the uncached full input-token price.
- See `agents/doc-lookup-sources.md` for how this kb finds and reads current official pages (including the Microsoft Learn MCP server used for the Azure AI Search facts above); this article's own sources were fetched the same way.
- Azure semantic ranker's L2 rerank step and Anthropic's Contextual Retrieval reranking step both add a second, more expensive scoring pass after an initial cheap ranking (RRF or BM25/vector) — the same "rerank the top-N" pattern, with different rerankers (Microsoft's Bing-derived semantic ranking models vs. the Cohere reranker in Anthropic's evaluation) [DER S-jt6qyh46, S-4hditql5: comparing the two rerank steps described independently].

## Examples

- SNIPPET: Azure AI Search hybrid query combining full-text `search` and a `vectorQueries` entry, fused by
  RRF and semantic-reranked; context: `api-version=2026-04-01`, index with a searchable text field and a
  vector field; checked: no [DOC S-pgtfj4fh: request shape, keys and api-version from the hybrid-query
  example]
```http
# Azure AI Search hybrid query: BM25 + vector, fused by RRF, then semantic-reranked
POST https://{{searchServiceName}}.search.windows.net/indexes/kb-docs/docs/search?api-version=2026-04-01
Content-Type: application/json

{
  "search": "how does hybrid search rank results",
  "vectorQueries": [
    { "kind": "vector", "vector": [ /* embedding of the query */ ], "k": 50, "fields": "contentVector" }
  ],
  "queryType": "semantic",
  "semanticConfiguration": "kb-semantic-config",
  "select": "title,content",
  "top": 10
}
```

- SNIPPET: pgvector HNSW index build (cosine distance, tuned `m`/`ef_construction`), a query-time
  `hnsw.ef_search` and a nearest-neighbor query; context: pgvector, PostgreSQL; checked: no
  [DOC S-524t5qtl: `CREATE INDEX ... USING hnsw`, `WITH (m=, ef_construction=)`, `SET hnsw.ef_search`,
  `<=>` operator]
```sql
-- pgvector: HNSW index (cosine distance) and a tuned query
CREATE INDEX ON kb_chunks USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

SET hnsw.ef_search = 100;

SELECT id, content
FROM kb_chunks
ORDER BY embedding <=> '[0.01, -0.02, ...]'::vector
LIMIT 10;
```

- SNIPPET: Elasticsearch RRF retriever fusing a `standard` (BM25) child retriever and a `knn` child
  retriever in one search request; context: Elasticsearch, top-level `retriever` search parameter;
  checked: no [DOC S-fn6fxrr5: `retriever.rrf`, `retrievers` array, `standard`/`knn` shapes,
  `rank_constant`]
```json
// Elasticsearch: RRF retriever fusing BM25 and kNN, PL-LT-00123-style placeholder index
{
  "retriever": {
    "rrf": {
      "retrievers": [
        { "standard": { "query": { "match": { "content": "contextual retrieval" } } } },
        { "knn": { "field": "embedding", "query_vector": [0.01, -0.02], "k": 50, "num_candidates": 200 } }
      ],
      "rank_constant": 60,
      "rank_window_size": 50
    }
  },
  "size": 10
}
```
