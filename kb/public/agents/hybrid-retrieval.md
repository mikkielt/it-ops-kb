---
topic: agents/hybrid-retrieval
priority: P2
applies_to: "Azure AI Search hybrid/vector/semantic search (api-version 2026-04-01, retrieved 2026-09-26); Anthropic Contextual Retrieval (engineering post, retrieved 2026-09-26); pgvector (README/LICENSE at master, retrieved 2026-09-26); Elasticsearch RRF retriever (docs, retrieved 2026-09-26); Claude API search result blocks (retrieved 2026-09-27); doc2query and Doc2Query-- papers; Model2Vec v0.9.0; Sufficient Context paper; Anthropic reduce-hallucinations guide; Azure AI Search traffic analytics (retrieved 2026-09-27); Azure AI Search fuzzy search (retrieved 2026-10-11); RRF (SIGIR 2009), MoR, RouterRetriever, SPLADE, inference-free learned sparse, ColBERTv2, BEIR, BRIGHT and GraphRAG papers; GraphRAG query docs at commit 4c8ef97; query performance prediction papers (2023-2026)"
retrieved_utc: 2026-10-12
sources: [S-bfjgfchf, S-adb2hv5q, S-pgtfj4fh, S-btrwp2yj, S-dh75h5qt, S-jt6qyh46, S-jaycbw5k, S-net4uvqm, S-idqwhfg2, S-z7wh2sbr, S-4hditql5, S-524t5qtl, S-76smovmo, S-fn6fxrr5, S-4c46o537, S2135, S-qpqoaaqj, S-jnq56sj3, S-sqbfbcyk, S-aqnin65g, S-yi5xka25, S-fovhkyzc, S-enf2tnxi, S-5y6g7iij, S-dghvtpkr, S-yknt2enl, S-zapphi2u, S-fjxhj6uv, S-tjpagk62, S-3hg4s7nu, S-typv6xpp, S-lom3gqqn, S-63ms6dc7, S-ilzlwkww, S-tfxaexfl, S-rzdl5ab6, S-mtxzhduu, S-2w5ehbab, S-g2bbx2bz, S-hxd4fjjl, S-gcgkws5h, S-43qs4mfw, S-e6qw2drp, S-f2sg2wfn, S-w2g2bnsw, S-zrpjwjip, S-dmhfxnon, S-eow7dyxc, S-qsdk3esx, S-lsfxdurw, S-tiudfpoz, S-i6b6z3is, S-nhrhhimz]
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

### Retrieval granularity and chunk context
- The Dense X Retrieval paper (EMNLP 2024) reports that indexing a corpus by fine-grained units such as propositions significantly outperforms passage-level units in retrieval tasks [DOC S-bfjgfchf].
- Dense X defines a proposition, its proposed retrieval unit, as an atomic expression within the text that encapsulates one distinct factoid and is presented in a concise, self-contained natural-language format, which is what lets the small unit be read without its surrounding passage [DOC S-bfjgfchf].
- Microsoft's Azure Architecture Center warns that chunks too small to hold enough context to address the query can result in poor outcomes [DOC S-adb2hv5q].
- Azure AI Search guidance gives one remedy for context loss: with large documents, use variable-sized chunks and also append the document title to chunks from the middle of the document [DOC S-idqwhfg2].
- Anthropic states that splitting documents into smaller chunks can lead to problems when individual chunks lack sufficient context, the problem Contextual Retrieval (above) addresses [DOC S-4hditql5].

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
- `rank_constant` must be at least 1, and `rank_window_size` must be at least `size` and at least 1 [DOC S-fn6fxrr5].
- A document that one child retriever's window does not hold adds nothing from that retriever: the page's worked example scores a document found by only one of two queries as `0 + 1.0/(1+1)`, and ranks it by that sum alongside documents found by both [DOC S-fn6fxrr5].
- Fusion sees only each retriever's window: with the same two queries, a window of 5 gave the final order `[1, 4, 2, 3, 5]` and a window of 2 gave `[1, 5, 2, 4]`, so a changed `rank_window_size` can reorder results even at the same ranks [DOC S-fn6fxrr5].
- Azure AI Search's RRF instead accepts a per-vector-query `weight` (default 1.0) that scales a query's contribution before summing — a per-retriever knob Elasticsearch's RRF retriever does not document [DER S-fn6fxrr5, S-btrwp2yj: contrast between the two vendors' documented RRF parameters].

### Document expansion: doc2query and Doc2Query--
- doc2query expands each document before indexing with queries a sequence-to-sequence model predicts it answers, the model being trained on pairs of queries and relevant documents; with a re-ranker it set the state of the art on two retrieval tasks, and without re-ranking it approached the effectiveness of neural re-rankers at much lower latency. [DOC S-jnq56sj3]
- Doc2Query-- argues that the generated queries include hallucinated content that harms retrieval and inflates the index, and filters them before indexing with a relevance model: up to 16% better retrieval effectiveness than Doc2Query, 23% lower mean query execution time and a 33% smaller index. [DOC S-sqbfbcyk]
- This kb's filter is a variant: it keeps a generated question only when `pack` without expansion already routes it to the fact's article, a lexical self-consistency test rather than a relevance model, so an expansion can re-rank lines inside an article the lexical ranker already reaches but cannot bridge vocabulary it does not. [DER S-sqbfbcyk: filter compared with `kb/_self/doc2query.md`]

### Lexical ranking levers and the no-answer verdict
- Robertson and Zaragoza call the simplest extension of BM25 to weighted fields (streams) a weighted variant of the total term frequency. [DOC S-zapphi2u]
- Azure AI Search scoring profiles can be based on weighted string fields, where boosting rests on a match in a designated field. [DOC S-fjxhj6uv]
- An Elasticsearch `multi_match` field boost is written with a caret, and in the documented example the query multiplies the `subject` field's score by three and leaves the `message` field's score unchanged. [DOC S-tjpagk62]
- An Azure AI Search synonym map associates equivalent terms and so expands the scope of a query without the user having to provide the term. [DOC S-3hg4s7nu]
- Azure AI Search implements synonyms internally by rewriting the original query with the synonyms using the OR operator. [DOC S-3hg4s7nu]
- Microsoft's English analyzer in Azure AI Search performs lemmatization instead of stemming. [DOC S-typv6xpp]
- Elasticsearch's pinned query is typically used to guide searchers to curated documents that are promoted over and above any "organic" matches. [DOC S-lom3gqqn]
- A Microsoft Search bookmark result that does not meet the machine learning ranker threshold is suppressed in the Microsoft Teams client. [DOC S-63ms6dc7]
- Azure AI Search scores convey a general sense of relevance, reflecting the strength of match relative to other documents in the same result set. [DOC S-ilzlwkww]
- For custom code with minimum thresholds, or the threshold property on vector and hybrid queries, Microsoft advises not making the limits too granular. [DOC S-jt6qyh46]
- HyDE is reported to significantly outperform the unsupervised dense retriever Contriever and to perform comparably to fine-tuned retrievers across tasks (web search, QA, fact verification) and languages. [DOC S-rzdl5ab6]
- Robertson and Zaragoza: blind feedback is generally known to improve search results on average but tends to fail on some queries, particularly ones that are difficult to start with, where the top-ranked documents of the initial search may be poor. [DOC S-zapphi2u]
- Azure AI Search agentic retrieval can use LLM-based query planning (preview) to break a complex query into smaller, focused subqueries for better coverage. [DOC S-mtxzhduu]
- SQuAD 2.0 requires systems not only to answer when possible but to determine when no answer is supported by the paragraph and abstain from answering. [DOC S-tfxaexfl]
- Custom question answering recommends a confidence threshold of 50 as one that should work for most projects. [DOC S-2w5ehbab]
- To improve the confidence score of a particular response to a user query, custom question answering lets you add the user query to the project as an alternate question on that response. [DOC S-2w5ehbab]

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

### Retrieval routing and abstention: primary papers (abstracts read 2026-09-29)
- Self-RAG argues that retrieving a fixed number of passages regardless of whether retrieval is needed or the passages are relevant hurts versatility; it trains one LM to retrieve on demand and to critique passages and its own output with reflection tokens. [DOC S-5y6g7iij]
- Corrective RAG (CRAG) adds a lightweight retrieval evaluator that scores the retrieved documents for a query and returns a confidence degree; the confidence picks the retrieval action, and large-scale web search is the extension when the static corpus returns sub-optimal documents. [DOC S-dghvtpkr]
- Adaptive-RAG uses a smaller LM as a classifier of question complexity to choose between no retrieval, single-step and iterative retrieval, aiming to avoid overhead on simple queries and to cover multi-step ones. [DOC S-yknt2enl]
- These have the shape of a verdict router: a cheap signal from the pack (`good`, `weak`, `none` plus a check line) picks kb only, kb plus live docs, or live docs, and CRAG's corpus-then-web fallback matches the `none` and `weak` routes. The papers' evaluators are trained models, whereas the pack's signal is lexical, so their reported gains do not transfer as numbers. [DER S-5y6g7iij, S-dghvtpkr, S-yknt2enl, S-yi5xka25: mapping to the kb_ask routing in `kb/_self/tools.md`]

### Rank fusion: the original RRF paper
- Cormack, Clarke and Büttcher built RRF as a baseline for combining rankings and found that it "almost invariably improved on the best of the combined results"; as an unsupervised method it needs no training examples. [DOC S-g2bbx2bz]
- Their pilot fixed `k` = 60 and did not change it afterwards: the pilot "indicated that k = 60 was near-optimal, but that the choice was not critical" (MAP .2145 at 60, .2139 to .2147 for every `k` from 30 to 100). [DOC S-g2bbx2bz]
- Over the pilot and TREC experiments, "RRF outperforms Condorcet, CombMNZ and the best system by 4% to 5% on average"; on LETOR 3, CombMNZ edged RRF by a small margin that was not significant (p ≈ .2). [DOC S-g2bbx2bz]
- RRF needs no special voting algorithm or global information: ranks can be computed and summed one system at a time, without keeping all rankings in memory, and it combines ranks without regard to the systems' arbitrary scores. [DOC S-g2bbx2bz]
- The paper defines the score as the sum over the rankings of `1/(k + r(d))`, where each ranking is "a permutation on 1..|D|" of the one document set. [DOC S-g2bbx2bz]
- The paper's two pages hold no rule for a document a ranking lacks and none for documents with equal scores, and the Elasticsearch page documents no tie-break either (both read in full 2026-10-12); a fusion over partial lists such as this kb's experts therefore has to choose its own deterministic order for ties. [DER S-g2bbx2bz, S-fn6fxrr5: absence read in the paper and the retriever page]

### Mixture of retrievers and routing to expert retrievers
- MoR (2025) starts from retrievers giving complementary signals (BM25 lexical matches, dense retrievers semantic similarity) and argues that fixing one retriever by heuristics fails to generalize across diverse information needs; it selects and weights several retrievers per query as a zero-shot weighted combination. [DOC S-hxd4fjjl]
- MoR reports that a mixture totalling 0.8B parameters outperforms every individual retriever by +10.8% and larger 7B models by +3.9% on average, and that a human information source added as a retriever gave a 58.9% relative improvement over simulated humans alone. [DOC S-hxd4fjjl]
- RouterRetriever routes each query to the most appropriate of several domain-specific expert embedding models; experts can be added or removed without additional training. [DOC S-gcgkws5h]
- On BEIR, RouterRetriever outperforms a model trained on MSMARCO by +2.1 nDCG@10 and multi-task models by +3.2; its routing beats routing techniques common in language modelling by +1.8 on average, and the benefit holds on datasets that have no expert of their own. [DOC S-gcgkws5h]

### Learned sparse and late-interaction retrieval
- SPLADE learns sparse representations for documents and queries, keeping bag-of-words properties (exact term matching, inverted-index efficiency); explicit sparsity regularization and a log-saturation of term weights give highly sparse vectors, and the regularization's weight trades effectiveness against efficiency. [DOC S-43qs4mfw]
- Inference-free learned sparse retrievers run no model at query time, so retrieval is an inverted-index lookup; the 2024 paper's IDF-aware penalty and ensemble distillation gain 3.3 nDCG@10 on BEIR over the previous best inference-free model, with relevance comparable to siamese sparse retrievers and client-side latency 1.1 times BM25's. [DOC S-e6qw2drp]
- Late interaction (ColBERT) encodes queries and documents as one vector per token and scores relevance with token-level computations, which is more effective than single-vector retrieval but inflates the index by an order of magnitude; ColBERTv2's residual compression cuts the footprint 6-10 times while setting the state of the art within and outside its training domain. [DOC S-f2sg2wfn]

### Retrieval benchmarks: where lexical ranking holds and where it fails
- BEIR evaluated 10 lexical, sparse, dense, late-interaction and re-ranking systems on 18 datasets: BM25 is a robust baseline, re-ranking and late-interaction models give the best zero-shot results on average at high computational cost, and dense and sparse models often underperform. [DOC S-w2g2bnsw]
- BRIGHT (1,384 real-world queries in domains such as economics, mathematics and coding) needs reasoning to find the relevant documents: the leading MTEB model, SFR-Embedding-Mistral (59.0 nDCG@10 on MTEB), scores 18.3 on it, and explicit reasoning about the query improves retrieval by up to 12.2 points. [DOC S-zrpjwjip]

### Graph-based retrieval: GraphRAG
- The GraphRAG paper states that plain RAG fails on global questions about a whole corpus ("What are the main themes in the dataset?"), a query-focused summarization task; GraphRAG has an LLM build an entity knowledge graph, pregenerate summaries of communities of related entities, answer from each summary and summarize the partial answers. [DOC S-dmhfxnon]
- For global sensemaking questions over datasets of about 1 million tokens, GraphRAG improved the comprehensiveness and diversity of answers over a conventional RAG baseline. [DOC S-dmhfxnon]
- GraphRAG's query engine offers local search (knowledge-graph data plus raw text chunks, for questions about specific entities), global search (map-reduce over all community reports, resource-intensive, for questions about the dataset as a whole), DRIFT search, and a basic top-k vector search for comparison. [DOC S-eow7dyxc]

### Typo tolerance: fuzzy matching
- Azure AI Search fuzzy search expands each whole query term into a graph of up to 50 similarly composed terms and matches within a Damerau-Levenshtein distance of at most 2 (inserted, deleted, substituted or transposed characters); `~1` allows one edit and `~0` none. [DOC S-qsdk3esx]
- Fuzzy terms skip lexical analysis (only lower-casing), so semantically unrelated words such as "universe" and "inverse" match each other, and fuzzy search is inherently slower than other query forms. [DOC S-qsdk3esx]
- Microsoft names two alternatives: n-gram (bigram and trigram) indexing, often faster but storage-intensive with much bigger indexes, and a synonym map that lists the most egregious misspellings of a term. [DOC S-qsdk3esx]

### Query performance prediction (QPP)
- QPP predicts a search system's retrieval quality for a query without relevance judgements; supervised QPP methods clearly beat unsupervised ones only when a large-scale training set exists, and retrieval-score-based unsupervised methods assessed a conversational dense retriever well. [DOC S-i6b6z3is]
- A 2025 evaluation of QPPs (NQC, UQC, learning-to-rank features, dense-based predictors) over sparse, hybrid and dense rankers found predictor accuracy varies most with the collection and next with the ranker: sparse predictors that work on TREC Robust and GOV2 do not generalize to WT10G and MS MARCO. [DOC S-lsfxdurw]
- The same paper finds QPP-driven selective query processing gives only marginal gains. [DOC S-lsfxdurw]
- QPPs, which usually rest on lexical features of queries and corpora, perform statistically significantly worse on neural IR systems than on bag-of-words ones, by as much as 10% where semantic signals dominate. [DOC S-nhrhhimz]
- Using a distribution of QPP estimates over several rankers' top documents as fusion priors gave improvements of over 4.5% against unweighted CombSUM and RRF, and that downstream effectiveness did not correlate well with the standard correlation-based QPP evaluation. [DOC S-tiudfpoz]

### How these map onto a deterministic toolset
- The pool record of 2026-10-09 (Claude Code 2.1.293, 150 rows, `kb/_self/reports/benchmarks.md`) gives one observation of `pack` with no model behind it (the hook arm): right in 128 of 150 runs, but 0 of 3 `count` rows, 0 of 2 `decision`, 0 of 2 `conflict`, 2 of 5 `gap` and 8 of 10 `variant_typo` rows; the Haiku 5.5, Sonnet 5.5, Opus 5.5 and router arms answered every `count` row (Haiku 4.5 two of three), and the router arm also missed both `decision` and both `conflict` rows. [DER S-hxd4fjjl, S-gcgkws5h: the record's matrix read against the per-query routing the two papers describe]
- The same report's retrieval scenario of 2026-10-08 puts the fact's line in the pack for 67 of 72 blind questions with no false `none`, while 15 of 106 off-kb questions get a false `good`: on this corpus the measured misses are question kinds the pack does not serve and verdict precision, more than lexical recall. [DER S-w2g2bnsw: BEIR's BM25-as-robust-baseline finding read with the kb's own record]
- A deterministic analogue of MoR and RouterRetriever routes a question by its kind (counts and lists, decisions, conflicts, gaps, source citations, facts) to the tool that already answers that kind, and fuses the lists when more than one expert fires with RRF, which needs no score calibration, no training and only one ranking in memory at a time, so it fits a standard-library tool. [DER S-hxd4fjjl, S-gcgkws5h, S-g2bbx2bz: per-query expert selection plus the paper's stated RRF properties]
- A router's experts return partial lists of different lengths (a count is one row, a gap hit a few entries, `pack` a pooled window), so a fusion of them follows the Elasticsearch reading: each expert adds `1/(k + rank)` only for the items in its own list, with ranks from 1, so an item that one expert alone returns still ranks, scored by that one term. Equal fused scores need a rule the sources do not give, such as the better best rank, then the item key, to keep the output deterministic. [DER S-g2bbx2bz, S-fn6fxrr5: the formula and the partial-list example applied to the router's lists]
- A typo leg that expands only query words missing from the index vocabulary to the indexed terms within one or two edits, ranked as a second list and fused by RRF, would follow Azure's fuzzy rule without its cost on correctly spelled queries; the probe below found no typo miss for it to fix and one version string it would break, so it earns a place only with a typo row that `pack` misses. [DER S-qsdk3esx, S-g2bbx2bz: the fuzzy distance rule plus RRF fusion]
- Dense, late-interaction and cross-encoder rerankers need a model at query time, so they sit outside a standard-library toolset; the inference-free learned sparse shape (a model expands or weights documents at index time only) keeps query time a lexical lookup, which is the shape doc2query already has here. [DER S-e6qw2drp, S-f2sg2wfn, S-jnq56sj3: query-time cost of each family compared]
- GraphRAG builds its graph with an LLM because its corpus is unstructured; this kb's articles, tags, source ids and ledgers are already structured, so its "global" questions (counts, coverage, who cites what) are aggregations a tool computes, not summaries a model writes. [DER S-dmhfxnon, S-eow7dyxc: GraphRAG's global-question class compared with the kb's structured ledgers]
- BRIGHT's reasoning-intensive queries are the class where neither lexical nor dense retrieval holds and reasoning about the query helps, so they are the queries a router should hand to a model rather than to another tool. [DER S-zrpjwjip]
- An offline probe on 2026-10-11 (kb commit 8a50427 plus this article's edit, Python 3.13.2 on macOS, no model) routed the pool's rows by question kind to the existing tools: `count` rows went from 0 of 3 with `pack` alone to 3 of 3 by `rag.py audit`, `decision` from 0 of 2 to 2 of 2 by `kbdecide.py list`, and `gap` from 2 of 5 to 5 of 5 by a `_gaps.md` hit of `rag.py search --index`; `conflict` stayed 0 of 2 because `search` cuts the ledger entry before its source ids, which a whole-entry print fixes. The same probe found `pack` already right on 10 of 10 typo variants, and a closest-word typo fixer broke a `false_good` row by rewriting `24H2`. [DER S-hxd4fjjl, S-gcgkws5h, S-qsdk3esx: the routing and fuzzy rules above tried on the kb's own pool]
- In the same probe, no single QPP-style feature of `pack` (spread of the top ten BM25 scores as in NQC, rarest key word's IDF, top score, key-word count, domains of the top three articles) demoted any of the off-kb list's 15 `good` verdicts without demoting an eval `good`; the best pair (top three articles in two or more domains and top score under 18) caught 12 of 15 at a cost of 10 of 205 eval `good` rows, and 3 of the 15 (Okta SCIM, the Terraform Log Analytics resource, FileVault key escrow) are questions the kb now answers, two of them `good` rows of `lookup_eval.csv`. [DER S-lsfxdurw, S-i6b6z3is: collection-specific predictors calibrated on the kb's own labelled sets]
- A flag for a possible false `good` is, in these papers' terms, a score-based predictor cut at a threshold into a pass-on signal rather than a ranking input; the caution the 2025 evaluation gives for any predictor applies to it: accuracy follows the collection first and the ranker next, so the threshold is fitted on the collection's own labelled questions and re-read after those sets change, never carried over from another corpus. [DER S-lsfxdurw, S-i6b6z3is: the predictor evaluation and the unsupervised score-based finding read against the kb's `check:` note]

### Query logging: search traffic analytics
- Azure AI Search's search traffic analytics pattern collects telemetry on user interactions (clickstream events, keyboard inputs) to measure clickthrough rate and find which query inputs yield zero results; it sends custom events to Application Insights. [DOC S-enf2tnxi]
- Log only user-initiated searches: requests that populate facets or fetch internal information skew or bias the results. [DOC S-enf2tnxi]
- Search and click events are correlated through a search id sent as the `x-ms-client-request-id` header; each search event carries `SearchId`, `SearchServiceName`, `IndexName`, `SearchText` and `ResultCount`. [DOC S-enf2tnxi]
- The portal's Search Traffic Analytics page is outdated and references an obsolete client library; the page points to the `azure-search-traffic-analytics` samples instead, and recommends service logs (no code, including search terms) for all scenarios. [DOC S-enf2tnxi]
- For a kb lookup tool the same log maps onto a pack call: the question as `SearchText`, the verdict (`none` as the zero-result case) and top article in place of `ResultCount`, and the answer's outcome (answered, escalated, corrected) in place of a click. [DER S-enf2tnxi: event schema mapped onto `pack` output]

## Reference
- This kb's own lookup tool, `_tools/rag.py pack` (and the `kb_pack` MCP tool), ranks fact bullets and table rows with a single BM25-style score over the kb's tagged facts, then optionally widens recall with LLM-generated `doc2query` expansion questions matched against the same index; it runs one ranker, not two independently-ranked lists, so it has no RRF fusion step and no separate reranking pass — it is closer to Azure's or Elasticsearch's lexical (BM25) leg alone, extended by doc2query rather than by a vector leg or a cross-encoder reranker [DER — `_self/reports/benchmarks.md`, "Lookup tools against reading files" and "doc2query", describing `rag.py`'s design and measured behavior, not an external DOC source].
- `_self/reports/benchmarks.md`'s doc2query measurement: in round 1 expansion raised pilot facts found in the pack from 36/40 to 39/40, with the weight tuned on those test questions; on fresh articles in round 2 it found 38/40 with and without expansion. It never changed a verdict and made packs slightly smaller; the two rounds' expansions stay indexed and the rest of the kb is not expanded [DER — same report, "doc2query"].
- See `agents/agent-caching.md` for Anthropic prompt caching mechanics (breakpoints, TTLs, invalidation order) that make Contextual Retrieval's context-generation step cost about $1.02/million document tokens rather than the uncached full input-token price.
- See `agents/doc-lookup-sources.md` for how this kb finds and reads current official pages (including the Microsoft Learn MCP server used for the Azure AI Search facts above); this article's own sources were fetched the same way.
- See `agents/mmlw-e5-polish-embeddings.md` for the Polish MMLW-e5 embedding models (dimensions, `query: `/`passage: ` prefixes, licence, ONNX status) and how their sizes sit under pgvector's index dimension limits.
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
