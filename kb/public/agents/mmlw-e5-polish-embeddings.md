---
topic: agents/mmlw-e5-polish-embeddings
priority: P3
applies_to: "sdadas/mmlw-e5-small, -base, -large at repo shas 2c03d4d83448, 9ba15feff8a1, a7d9af002b46 and intfloat/multilingual-e5-small, -base, -large at 614241f622f5, d12875059715, 3d7cfbdacd47 (Hugging Face model cards, configs and API, retrieved 2026-10-11); PIRB paper (arXiv v2); pgvector README at master@7db2345ed99b"
retrieved_utc: 2026-10-11
sources: [S-jwdbazk2, S-rd6qosor, S-pxbj347n, S-lbvzxugb, S-gh576tom, S-pbbsyo47, S-mskmsg2n, S-glyyxkhx, S-7chuxblv, S-mu7bkyzy, S-n3nnodaf, S-355aqkqx, S-m4jimv5l, S-6f3rjo5w, S-lgzmhh4v, S-dgww3las, S-fncwoz4o, S-tmatlfei, S-7v4o3ypv, S-ywnspvi2, S-fanrscfv, S-c6piuw5s, S-vk2qahbe, S-qhb5i45k, S-m6getpdd, S-4ptfxskc, S-sbuv7mtf, S-62hqvrkt, S-whovpca2, S-3rkj7rco, S-524t5qtl]
status: partial
---

# MMLW-e5: Polish text embeddings distilled from multilingual E5

## Summary
MMLW-e5 (`sdadas/mmlw-e5-small`, `-base`, `-large`) are three Polish sentence-embedding models, published under Apache-2.0 on Hugging Face, that the author trained from `intfloat/multilingual-e5-*` checkpoints by distilling English BGE teachers over 60 million Polish-English text pairs. They output 384, 768 and 1024 dimensional vectors, pool with the CLS token, truncate at 512 tokens and need the `query: ` and `passage: ` prefixes of the E5 family. No ONNX or quantised export exists in the author's repos; the base `multilingual-e5-*` repos do ship ONNX, int8 and OpenVINO files, but those carry the original E5 weights. The retrieval-tuned siblings (`mmlw-retrieval-e5-*`) are the models the PIRB paper's numbers show to be better for search. All dimensions sit under pgvector's 2,000-dimension index limit for `vector`. Where this matters for a CPU-only, offline text-corpus service, the derivations are grouped under "How it fits".

## Facts

### What MMLW-e5 is
- Each card opens "MMLW (muszę mieć lepszą wiadomość) are neural text encoders for Polish" and calls the model a distilled encoder for similarity, clustering and retrieval that can also be a base for fine-tuning; the cards give no English expansion of the acronym. [DOC S-jwdbazk2, S-rd6qosor, S-pxbj347n]
- Recipe on all three cards: initialised from a multilingual E5 checkpoint, then trained by multilingual knowledge distillation on 60 million Polish-English text pairs with English BGE (FlagEmbedding) models as teachers; the card links `BAAI/bge-base-en` for every size. [DOC S-jwdbazk2, S-rd6qosor, S-pxbj347n]
- The PIRB paper describes the distillation: the English teacher encodes the English text, the student encodes its translation and a mean-squared-error loss pulls the two together; pairs whose LaBSE similarity is below 0.7 were dropped; the teachers for the multilingual-e5 small, base and large students are `bge-small-en`, `bge-base-en` and `bge-large-en`. [DOC S-sbuv7mtf]
- The cards report NDCG@10 on the Polish Information Retrieval Benchmark of 47.64 (small), 53.56 (base) and 56.09 (large), and Polish MTEB averages of 55.84, 59.71 and 61.17; the PIRB paper's table gives 47.64, 53.56 and 56.00 for the distilled multilingual-e5 students before fine-tuning, so the repos are the distillation-stage models (the large value differs by 0.09). [DER S-jwdbazk2, S-rd6qosor, S-pxbj347n, S-sbuv7mtf: card figures compared with the paper's Table 3 "before fine-tuning" rows]
- The paper then fine-tunes the distilled students with a contrastive loss, raising NDCG@10 to 52.25 (small), 56.01 (base) and 58.03 (large). [DOC S-sbuv7mtf]
- The retrieval-tuned siblings are separate repos: the `mmlw-retrieval-e5-base` card says the model is optimized for information retrieval, adds fine-tuning with contrastive loss on Polish MS MARCO after the same distillation step, and notes a new version on 2023-12-26 with the previous one reachable by the `v1` tag. [DOC S-62hqvrkt]

### Sizes, dimensions, pooling
- The cards state 384, 768 and 1024 dimensional vectors; `1_Pooling/config.json` gives `word_embedding_dimension` 384, 768 and 1024 and `config.json` gives `hidden_size` 384, 768 and 1024 for small, base and large. [DOC S-jwdbazk2, S-rd6qosor, S-pxbj347n, S-mskmsg2n, S-glyyxkhx, S-7chuxblv, S-lbvzxugb, S-gh576tom, S-pbbsyo47]
- Architectures: small is a `BertModel` with 12 layers (vocabulary 250,037, tokenizer class `XLMRobertaTokenizer`, `_name_or_path` `intfloat/multilingual-e5-small`); base is an `XLMRobertaModel` with 12 layers and large an `XLMRobertaModel` with 24 layers, with `_name_or_path` the matching `multilingual-e5` repo. [DOC S-lbvzxugb, S-gh576tom, S-pbbsyo47]
- The Hugging Face API counts 117,653,760 (small), 278,043,648 (base) and 559,890,432 (large) float32 parameters, and the `model.safetensors` files are 470,637,416, 1,112,197,096 and 2,239,607,176 bytes. [DOC S-dgww3las, S-fncwoz4o, S-tmatlfei]
- Pooling is the CLS token (`pooling_mode_cls_token` true, mean false) in all three; `modules.json` lists only a `Transformer` and a `Pooling` module, with no `Normalize` module. [DOC S-mskmsg2n, S-glyyxkhx, S-7chuxblv, S-mu7bkyzy, S-n3nnodaf, S-355aqkqx]
- `sentence_bert_config.json` sets `max_seq_length` 512 and `do_lower_case` false; `max_position_embeddings` is 512 for small and 514 for base and large. [DOC S-m4jimv5l, S-6f3rjo5w, S-lgzmhh4v, S-lbvzxugb, S-gh576tom, S-pbbsyo47]
- The pipeline therefore returns the raw CLS vector; whether the CLS vectors are unit length by training is not stated in the cards. [UNK]
- The `multilingual-e5-small` repo differs: its `1_Pooling/config.json` selects mean pooling, its `modules.json` lists a `Normalize` module after pooling, and its card code average-pools then L2-normalises. [DOC S-m6getpdd, S-4ptfxskc, S-7v4o3ypv]

### Prefixes
- All three MMLW-e5 cards say queries should be prefixed with "query: " and passages with "passage: ", and their sentence-transformers example prepends `query: ` to the question and `passage: ` to every candidate answer. [DOC S-jwdbazk2, S-rd6qosor, S-pxbj347n]
- The warning on the cards speaks of "prefixes and suffixes", but only the two prefixes are defined; no suffix appears. [DOC S-rd6qosor]
- The MMLW-e5 cards give no rule for symmetric tasks (similarity between two texts of the same kind, clustering, classification features). [UNK]
- The `multilingual-e5` cards the MMLW models start from say every input should start with `query: ` or `passage: ` "even for non-English texts", that omitting them degrades performance, and give the rules: both prefixes for asymmetric retrieval, `query: ` for symmetric tasks and for embeddings used as features. [DOC S-7v4o3ypv, S-ywnspvi2, S-fanrscfv]

### Licence and library
- The three MMLW-e5 cards carry `license: apache-2.0` and the API tags the repos `license:apache-2.0`; the file lists hold no separate LICENSE file. [DOC S-jwdbazk2, S-rd6qosor, S-pxbj347n, S-dgww3las, S-fncwoz4o, S-tmatlfei]
- The `multilingual-e5-small`, `-base` and `-large` repos are tagged `license:mit`; the small card's metadata states `license: mit`. [DOC S-7v4o3ypv, S-c6piuw5s, S-vk2qahbe, S-qhb5i45k]
- The licences of the 60 million training pairs (OPUS, PELCRA, DGT, Wikipedia, translated questions) are not stated on the MMLW-e5 cards; the PIRB paper names the corpora but this kb did not read their terms. [UNK]
- The MMLW-e5 cards use `sentence-transformers`: `SentenceTransformer("sdadas/mmlw-e5-base")`, `model.encode(..., convert_to_tensor=True)` and `cos_sim` from `sentence_transformers.util`, with no version stated; the `multilingual-e5` cards pin `pip install sentence_transformers~=2.2.2`. [DOC S-rd6qosor, S-7v4o3ypv]

### ONNX, quantised and other exports
- At the three pinned shas the MMLW-e5 file lists hold `model.safetensors`, `pytorch_model.bin`, tokenizer files and the sentence-transformers configs, and no `onnx/` folder, no quantised file and no OpenVINO folder. [DER S-dgww3las, S-fncwoz4o, S-tmatlfei: absence from the API file lists]
- `multilingual-e5-small` and `-base` ship `onnx/model.onnx` (470,268,510 and 1,110,059,084 bytes), `onnx/model_O4.onnx` (235,052,531 and 554,948,118 bytes), `onnx/model_qint8_avx512_vnni.onnx` (118,346,824 and 278,686,411 bytes) and an `openvino/` folder; `-large` keeps its weights in `onnx/model.onnx_data` (2,235,363,328 bytes) beside a 545,850-byte `onnx/model.onnx`. [DOC S-c6piuw5s, S-vk2qahbe, S-qhb5i45k]
- A Hugging Face model search for "mmlw" lists two third-party ONNX repos, both of retrieval variants (`mmlw-retrieval-e5-small-onnx` and `mmlw-retrieval-roberta-base_onnx`); none is named for `mmlw-e5-*`, though a repo without "mmlw" in its name would not show. [DER S-3rkj7rco: search result list]
- That third-party card describes a dynamic int8 file of about 113 MB for fastembed and configures mean pooling, whereas the author's repo for the same model selects CLS pooling. [COMMUNITY S-whovpca2]

### pgvector fit
- The kb's pgvector facts give the type maximum (16,000 dimensions for `vector` and `halfvec`) at `kb/public/agents/hybrid-retrieval.md:80`; they do not give the lower index limits. [DER S-524t5qtl: kb line 80 read against the README]
- The pgvector README lists for both HNSW and IVFFlat indexes `vector` up to 2,000 dimensions, `halfvec` up to 4,000 and `bit` up to 64,000, and a `vector` row takes `4 * dimensions + 8` bytes. [DOC S-524t5qtl]
- MMLW-e5 vectors of 384, 768 and 1024 dimensions are below the 2,000-dimension limit for an indexed `vector` column and take 1,544, 3,080 and 4,104 bytes per row. [DER S-jwdbazk2, S-rd6qosor, S-pxbj347n, S-524t5qtl: dimensions inserted in the README's size formula]

### How it fits
Context for the derivations below: a self-hosted text-corpus service (Polish and English text) with a Python shell over a Rust core, CPU-only, offline-capable, model artifacts pinned by hash.

- Everything the encoder needs at run time is a file in the repo (weights, `tokenizer.json`, `sentencepiece.bpe.model`, pooling and module configs), so a model fetched once and pinned needs no network or cloud call to embed. [DER S-dgww3las, S-fncwoz4o, S-tmatlfei: repo file lists]
- The cards publish no CPU latency, throughput or memory figure; the weights alone are about 0.47, 1.1 and 2.2 GB in float32, so the size is chosen by measuring on the target host. [UNK]
- The only run path the cards document is Python with `sentence-transformers`; a Rust core would need its own ONNX export of the model, which no vendor repo supplies for MMLW-e5 (the E5 ONNX files hold the original E5 weights, not the distilled ones). [DER S-dgww3las, S-fncwoz4o, S-tmatlfei, S-c6piuw5s, S-vk2qahbe, S-qhb5i45k: file lists compared]
- A pin by hash fits the repos: the API returns a commit sha for the repo and a sha256 for each LFS file, and the retrieval card shows the author replaced the model under the same name in December 2023, so a name alone does not pin a version. [DER S-dgww3las, S-fncwoz4o, S-tmatlfei, S-62hqvrkt: sha fields and the card's update note]
- Prefix, pooling and dimension are part of the index contract: documents embedded with `passage: ` and CLS pooling are compared with `query: `-prefixed queries; an E5 recipe with mean pooling and normalisation does not carry over, and a change of model, prefix or pooling means re-embedding the corpus. [DER S-rd6qosor, S-mskmsg2n, S-glyyxkhx, S-7chuxblv, S-m6getpdd: MMLW and E5 settings compared]
- For retrieval over a corpus the measured candidates are the `mmlw-retrieval-e5-*` repos, since fine-tuning raised the paper's NDCG@10 by about 2 to 4.6 points over the distilled models; `mmlw-e5-*` is the fit for similarity and clustering and as a base for further fine-tuning. [DER S-sbuv7mtf, S-62hqvrkt, S-rd6qosor: paper's Table 3 and the cards' stated purposes]
- How MMLW-e5 performs on English passages is not stated: the cards and the PIRB paper evaluate Polish only, although training used Polish-English pairs. [UNK]

## Reference
- Pinned repos (Hugging Face; licence Apache-2.0 for `sdadas/*`, MIT for `intfloat/*`):

| model | repo sha | dim | layers | architecture | pooling | `model.safetensors` sha256 |
|---|---|---|---|---|---|---|
| `sdadas/mmlw-e5-small` | 2c03d4d83448f7c780ff13883eea63abfb897055 | 384 | 12 | BertModel | CLS | 1cc389cecd4b5458298bb8493f00de120a5b358caa4b3124c63bfcf2c529c9fd |
| `sdadas/mmlw-e5-base` | 9ba15feff8a15b0bb1433a49e10d64de2a1fe772 | 768 | 12 | XLMRobertaModel | CLS | f50cea47c8eb01dc5e84a45e72e4fef90fb9513e8e56979b6b9a6ed1ae023ecd |
| `sdadas/mmlw-e5-large` | a7d9af002b465bef87fca48845446311bb60a806 | 1024 | 24 | XLMRobertaModel | CLS | fce612437e77e406173a296ef5d1792f8ecf1edd6ee63348e59d9671df190ee7 |
| `intfloat/multilingual-e5-small` | 614241f622f53c4eeff9890bdc4f31cfecc418b3 | 384 | 12 | BertModel | mean + Normalize | 1a55775f53449dac10a2bcbc312469fac40b96d53198c407081a831f81c98477 |

- Hashes and sizes come from the Hugging Face API at each sha (`/api/models/<id>/revision/<sha>?blobs=true`); the pooling and layer columns of the `sdadas` rows come from the repos' `1_Pooling/config.json` and `config.json`.
- PIRB: the cards link the leaderboard (`huggingface.co/spaces/sdadas/pirb`) and cite "PIRB: A Comprehensive Benchmark of Polish Dense and Hybrid Text Retrieval Methods" (LREC-COLING 2024); the arXiv v2 text was read here (S-sbuv7mtf). The paper's arXiv text does not use the name MMLW.
- Retrieval siblings on Hugging Face: `sdadas/mmlw-retrieval-e5-small`, `-base`, `-large`; only the base card was read (its base model, prefixes and CLS pooling match the MMLW-e5 base repo).
- See `agents/hybrid-retrieval.md` for the pgvector operators, licence and the hybrid-retrieval context this embedding model feeds.

## Examples
- SNIPPET: the card's sentence-transformers usage, encoding one prefixed query against three prefixed passages and picking the best by cosine similarity; context: `sentence-transformers` installed, `sdadas/mmlw-e5-base` downloaded or cached, Python 3; checked: syntax [DOC S-rd6qosor: code from the card's "Usage (Sentence-Transformers)" section]
```python
from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim

query_prefix = "query: "
answer_prefix = "passage: "
queries = [query_prefix + "Jak dożyć 100 lat?"]
answers = [
    answer_prefix + "Trzeba zdrowo się odżywiać i uprawiać sport.",
    answer_prefix + "Trzeba pić alkohol, imprezować i jeździć szybkimi autami.",
    answer_prefix + "Gdy trwała kampania politycy zapewniali, że rozprawią się z zakazem niedzielnego handlu.",
]
model = SentenceTransformer("sdadas/mmlw-e5-base")
queries_emb = model.encode(queries, convert_to_tensor=True, show_progress_bar=False)
answers_emb = model.encode(answers, convert_to_tensor=True, show_progress_bar=False)

best_answer = cos_sim(queries_emb, answers_emb).argmax().item()
print(answers[best_answer])
```
- SNIPPET: a pgvector table and cosine HNSW index sized for 768-dimensional MMLW-e5-base vectors; context: PostgreSQL with the `vector` extension, a table name of our own; checked: no [DER S-524t5qtl, S-rd6qosor: README's `CREATE TABLE ... vector(N)` and `hnsw (embedding vector_cosine_ops)` forms with N set to the card's 768]
```sql
CREATE TABLE passages (id bigserial PRIMARY KEY, embedding vector(768));
CREATE INDEX ON passages USING hnsw (embedding vector_cosine_ops);
```
