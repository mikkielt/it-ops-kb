---
topic: privacy/gliner-glirel-zero-shot
priority: P3
applies_to: "gliner 0.2.29 (tag v0.2.29), glirel 1.2.1 (tag v1.2.1), gline-rs 1.1.0 (tag v1.1.0); Hugging Face repos at the shas cited in each source row"
retrieved_utc: 2026-10-11
sources: [S-7bjdu5bv, S-rvd2zkel, S-y42nqxiw, S-hfifhdhx, S-sislku4q, S-w7vp7g4j, S-vdhsig6s, S-ewb6gt73, S-sw4xvzwh, S-wrx2q5ya, S-7ke3sttd, S-pvemvpkp, S-hpdsbqwa, S-dwg2wis7, S-2fmzqhdr, S-gzvx6zzv, S-kd2ecakr, S-snmqzq62, S-zmg7nlby, S-gtbynljf, S-7w6x3tvz, S-z3khz6q6, S-zeyni7ox, S-7p4fya6x, S-vqqlqtwg, S-pefl6gq2, S-fxeklpmh, S-bfttmynz, S-n5dkd37b, S-7aohd7sc, S-ulch3bqh, S-o4aom6i2, S-qkyjirm6, S-ngy65th6, S-uu7ov3pw, S-edkar7xu, S-pjp4rzor, S-gc45kgud, S-eu53rrws, S-w6u6mtcx, S-nshkwezk, S-hesowhet, S-bzhegec5, S-gtp7oa24]
status: partial
---

# GLiNER and GLiREL as general zero-shot NER and relation extraction: API, limits, multilingual cards, CPU and ONNX

## Summary
- GLiNER (library 0.2.29, Apache-2.0) takes a text and a list of label strings at call time and returns entity spans; it is built on PyTorch, runs on CPU by default and can export to and load ONNX.
- Input is cut to the first `max_len` word tokens (384 by default, set per checkpoint) with only a warning; the library does not window long text.
- `urchade/gliner_multi-v2.1` (mDeBERTa-v3-base encoder, Apache-2.0) is the general multilingual card but names no language; of the cards read, only `knowledgator/gliner-x-*` (mT5 encoders, Apache-2.0, ONNX files in the repo) lists Polish.
- GLiREL (1.2.1) classifies relations between entity spans you supply; its licence is stated two ways (CC BY-NC-SA 4.0 and Apache-2.0), it has no ONNX path, and Polish is not stated. GLiNER's own relation architecture (`gliner-relex-*`) is the alternative.

## Facts

### GLiNER library
- Release 0.2.29 is the latest on PyPI (uploaded 2026-09-08); the metadata gives Apache-2.0 and Python 3.10 or newer, and the `LICENSE` file at tag v0.2.29 is the Apache License 2.0. [DOC S-7bjdu5bv, S-sw4xvzwh]
- A plain install pulls `torch` (2.0.0 or newer), `transformers` (4.51.3 up to below 5.17.0), `huggingface_hub`, `safetensors` and `sentencepiece`; `onnxruntime` is the optional `onnx` extra, `onnxruntime-gpu` the `gpu` extra, and `stanza` and `langdetect` come with the `stanza` extra. [DOC S-7bjdu5bv]
- API: `pip install gliner`, then `GLiNER.from_pretrained("<repo or local dir>")` and `model.predict_entities(text, labels, threshold=0.5)`; the README loop reads `entity["text"]` and `entity["label"]`. [DOC S-rvd2zkel]
- `predict_entities(text, labels, flat_ner=True, threshold=0.5, multi_label=False, ...)` returns dicts with `start` and `end` (character positions), `text`, `label` and `score`; `inference` takes several texts and `batch_predict_entities` is deprecated. [CODE S-w7vp7g4j: gliner/model.py#BaseEncoderGLiNER.predict_entities]
- Labels are free strings chosen per call, or a dict of label to description; `inference` also takes one label set per text, and a list of dicts means one dict per text, not several labels for one text. [DOC S-y42nqxiw]
- The README says the uni-encoder architecture "supports up to ~50 entity types", and `max_types` (25 in the urchade checkpoints) is documented as the number of types per batch. [DOC S-rvd2zkel, S-sislku4q]
- `max_len` is the number of tokens from GLiNER's own word splitter (punctuation counts as separate tokens; not subwords, not characters); text beyond it is dropped after a `UserWarning`, the result carries no truncation flag, and the docs say the library does not split long documents, so overlapping windows with offset shifting are the caller's job. [DOC S-y42nqxiw, S-sislku4q]
- `max_width` (12 in every GLiNER checkpoint config read) is the largest candidate span in tokens, and `max_len` is saved per checkpoint: 384 for `urchade/gliner_multi-v2.1`, 768 for `gliner-community/gliner_small-v2.5`, 1024 for `knowledgator/gliner-x-base` and 2048 for `knowledgator/gliner-relex-multi-v1.0`. [DOC S-sislku4q, S-pvemvpkp, S-n5dkd37b, S-vqqlqtwg, S-o4aom6i2]
- The word splitter is a checkpoint setting (`words_splitter_type`, default `whitespace`); the `gliner-x-*` configs set `stanza`, and the Stanza splitter downloads a missing language model on first use unless `download_on_missing` is turned off. [CODE S-vdhsig6s: gliner/data_processing/tokenizer.py#StanzaWordsSplitter]

### Multilingual and general models
- `urchade/gliner_multi-v2.1` (sha 443d26d, last modified 2025-12-08): card `license: apache-2.0`, `language: multilingual`, its model table lists it as "Multilingual" with 209M parameters, the config names `microsoft/mdeberta-v3-base` as encoder, and the HF API reports 288,949,504 F32 parameters in a 1,155,830,112-byte `model.safetensors` (plus a `pytorch_model.bin`). [DOC S-7ke3sttd, S-pvemvpkp, S-wrx2q5ya]
- The English siblings are `gliner_small-v2.1`, `gliner_medium-v2.1` (780,735,696-byte safetensors) and `gliner_large-v2.1` (only a 1,782,044,554-byte `pytorch_model.bin`, `microsoft/deberta-v3-large` encoder); all Apache-2.0. The large card's front matter says `multilingual` while its own table says English. [DOC S-kd2ecakr, S-gzvx6zzv, S-dwg2wis7, S-hpdsbqwa, S-2fmzqhdr]
- `urchade/gliner_multi-v2.1` names no language beyond "multilingual", and its mDeBERTa encoder card lists 15 languages (en, ar, bg, de, el, es, fr, hi, ru, sw, th, tr, ur, vi, zh) without Polish, trained on CC100. [DER S-7ke3sttd, S-qkyjirm6: Polish absent from both cards' language statements]
- Whether `urchade/gliner_multi-v2.1` recognises Polish entities, and how well, is not stated or measured in any card read. [UNK]
- `knowledgator/gliner-x-small`, `-base` and `-large` (shas d51a098, a6c7a8f, 4a4437f; Apache-2.0): front matter and text list 22 languages including `pl` and Polish, with a Polish example; the configs name `google/mt5-small`, `-base`, `-large` as encoders, and the HF API reports 300,175,808, 493,905,024 and 864,609,792 parameters. [DOC S-7p4fya6x, S-vqqlqtwg, S-pefl6gq2, S-zeyni7ox, S-fxeklpmh]
- The `gliner-x` card's F1 table covers eight datasets (Danish, German, English, Portuguese, Swedish and Chinese sets) and none is Polish; `gliner-x-large` scores above `urchade/gliner_multi-v2.1` on all eight, the small and base models do not on `zh_pud`. [DOC S-7p4fya6x]
- `gliner-community/gliner_small-v2.5` (Apache-2.0) carries `language: multilingual` while its config names `microsoft/deberta-v3-small`; the tag alone is not evidence of a language. [DOC S-bfttmynz, S-n5dkd37b]
- `knowledgator/gliner-multitask-large-v0.5` (sha 7a95e16): Apache-2.0, language `en`, `microsoft/deberta-v3-large` encoder, a 1,761,073,550-byte `pytorch_model.bin` plus fp16 and bf16 safetensors of about 880 MB; the card has NER and relation extraction (labels written `A <> relation`) in one model. [DOC S-zmg7nlby, S-snmqzq62, S-gtbynljf]

### CPU and ONNX
- The README describes GLiNER as "optimized to run on CPUs and consumer hardware"; the docs give `quantize="int8"` on CPU as FBGEMM kernels with about 1.6x speedup, with accuracy loss for stock DeBERTa models not trained for quantisation. [DOC S-rvd2zkel, S-y42nqxiw]
- `from_pretrained` defaults `map_location` to `cpu`, and `compile_torch_model=True` compiles only when the location is CUDA (a CPU request warns and skips). [CODE S-w7vp7g4j: gliner/model.py#BaseGLiNER.from_pretrained]
- Export: `model.export_to_onnx(save_dir, onnx_filename="model.onnx", quantize=False, opset=19)` needs the `onnx` package and writes `model.onnx`, `gliner_config.json` and the tokenizer files; `quantize=True` adds a dynamically quantised file under `quantized_filename`, skipped with a warning if quantisation fails. [DOC S-hfifhdhx]
- Load: `GLiNER.from_pretrained(dir, runtime="onnxruntime", runtime_model_file="model.onnx")` (the older form is `load_onnx_model=True, onnx_model_file=...`); CPU execution is the default and the artifact name is resolved relative to the model directory. [DOC S-hfifhdhx]
- ONNX export covers uni- and bi-encoder span and token models and the relation-extraction models, not the generative decoder or streaming architectures; an exported model cannot be re-exported, rejects `dtype`, `variant` and `quantize`, and cannot return entity vectors. [DOC S-hfifhdhx, S-y42nqxiw]
- Loading builds the encoder from a config (`backbone_from_pretrained=False`), takes the tokenizer from the model directory when `tokenizer_config.json` is there and otherwise from the Hub id in `config.model_name`, and takes the encoder config from `AutoConfig` when the checkpoint config has none; weights come from `model.safetensors`, else `pytorch_model.bin` read with `weights_only=True`. [CODE S-w7vp7g4j: gliner/model.py#BaseGLiNER._load_tokenizer, #BaseGLiNER._resolve_model_file, #BaseGLiNER._load_state_dict; S-ewb6gt73: gliner/modeling/encoder.py#Transformer]
- `onnx-community/gliner_multi-v2.1` (sha 6ddaeb9, last modified 2024-10-08): front matter has `base_model` and `library_name: transformers.js` but no licence; `onnx/model.onnx` is 1,157,129,714 bytes, with `model_fp16` (579,717,643), `model_int8` and `model_quantized` (both 349,120,924), `model_uint8`, `model_q4`/`model_bnb4` (893,933,650) and `model_q4f16`; the card calls the separate ONNX repo "a temporary solution". [DOC S-z3khz6q6, S-7w6x3tvz]
- `knowledgator/gliner-x-base` ships `onnx/model.onnx` (1,207,693,659 bytes) and `onnx/model_quantized.onnx` (302,646,302 bytes) in the model repo, with the large model's two files at 2,434,814,051 and 610,122,400 bytes; the card does not describe how to load them. [DOC S-zeyni7ox, S-fxeklpmh]
- Whether the ONNX files in `knowledgator/gliner-x-*` and `onnx-community/gliner_multi-v2.1` load in the `gliner` Python library as shipped was not tested; the library's guide documents loading its own exports only. [UNK]
- `gline-rs` 1.1.0 (crates.io, 2026-08-05, Apache-2.0) is a separate Rust inference engine for GLiNER ONNX models, inference only, with span and token modes and ready NER and relation-extraction pipelines; its README measures 6.67 sequences per second against 1.61 for GLiNER.py on its author's 8-core CPU (gline-rs 0.9.0, three labels, 100 texts) and lists `gliner-x-large` among models with ONNX files. [DOC S-hesowhet, S-gtp7oa24]
- `gline-rs` depends on `orp`, `tokenizers`, `ndarray` and `ort`, which its manifest pins to the release candidate `=2.0.0-rc.9`. [CODE S-bzhegec5: Cargo.toml#dependencies]

### Relations: GLiREL and the GLiNER relex models
- GLiREL 1.2.1 (PyPI 2025-04-11; first release 0.1.0 on 2024-06-07) classifies relations between entities you pass: `model.predict_relations(tokens, labels, threshold, ner=[[start, end, type, text], ...], top_k=...)`, with inclusive token indices, labels as a list or a dict giving `allowed_head` and `allowed_tail` types, and results with `head_pos`, `tail_pos`, `head_text`, `tail_text`, `label`, `score`. [DOC S-ngy65th6, S-pjp4rzor]
- `jackboyla/glirel-large-v0` (sha 40a523e, last modified 2025-01-08): a single 1,866,504,702-byte `pytorch_model.bin` (no safetensors), `microsoft/deberta-v3-large` encoder, `max_len` 512. [DOC S-eu53rrws, S-nshkwezk]
- `GLiREL.from_pretrained` downloads `pytorch_model.bin` and `glirel_config.json` and reads the weights with `torch.load(..., map_location=...)`, passing no `weights_only` argument. [CODE S-edkar7xu: glirel/model.py#GLiREL._from_pretrained]
- The GLiREL licence is stated two ways: the README and the model card text say CC BY-NC-SA 4.0, while `pyproject.toml` and the PyPI metadata say Apache-2.0; the v1.2.1 source archive has no `LICENSE` file and the model card has no licence field. [DER S-ngy65th6, S-w6u6mtcx, S-uu7ov3pw, S-pjp4rzor: the statements differ and no licence file settles them]
- GLiREL declares only `torch`, `transformers`, `huggingface_hub`, `seqeval`, `tqdm` and `datasets` (no spaCy), and a plain string input is split by the library's own regex, so spaCy is not needed to run it. [CODE S-uu7ov3pw: pyproject.toml#dependencies; S-edkar7xu: glirel/model.py#GLiREL.batch_predict_relations]
- GLiREL has no ONNX path at v1.2.1: neither the README nor `glirel/` mentions ONNX, and pull request 10 "Begins support for ONNX" is a draft. [DER S-ngy65th6, S-edkar7xu, S-gc45kgud: no ONNX in the tagged files; the PR page shows state draft]
- No language is stated for GLiREL or `glirel-large-v0`, so Polish support is not confirmed. [UNK]
- How GLiREL treats input longer than the checkpoint's `max_len` (512) is not stated in the README, and `glirel/model.py` at v1.2.1 does not use `max_len`. [UNK]
- `knowledgator/gliner-relex-multi-v1.0` (sha e990d9b, Apache-2.0, created 2026-03-12) extracts entities and relations in one pass through `model.inference(texts, labels, relations, return_relations=True)`; its config names `microsoft/mdeberta-v3-base`, `max_len` 2048 and `max_types` 100, and the repo is a 1,275,472,292-byte `model.safetensors`. The card states no language and says "ONNX export support" although no ONNX file is in the repo. [DOC S-ulch3bqh, S-7aohd7sc, S-o4aom6i2]

### How it fits
- Only `knowledgator/gliner-x-*` among the general cards read names Polish; `urchade/gliner_multi-v2.1`, the relex models and GLiREL do not, so a Polish and English corpus service has one documented candidate family and must measure the rest itself. [DER S-7p4fya6x, S-7ke3sttd, S-ulch3bqh, S-w6u6mtcx: Polish named only in the gliner-x card]
- CPU-only fits the GLiNER Python library (CPU is the default device), but the library requires `torch` even for an ONNX file, whereas `gline-rs` runs the same ONNX artifacts with ONNX Runtime from a Rust core and has no Python ML stack. [DER S-7bjdu5bv, S-w7vp7g4j, S-hesowhet: torch is a hard requirement; inference builds a torch data loader]
- Offline and pinned by hash: a load needs the model repo plus, for `urchade/gliner_multi-v2.1` (no tokenizer files in the repo), the config and tokenizer of `microsoft/mdeberta-v3-base`, and for `gliner-x-*` Stanza language models; the HF API gives a SHA-256 for each large file, so a mirror can pin them and load with `local_files_only`. [DER S-wrx2q5ya, S-w7vp7g4j, S-vdhsig6s, S-zeyni7ox: files the loader asks for and the hashes the API lists]
- Long documents need a chunking layer in the service, because over-length input is silently truncated; labels and relation labels are call-time data, so a rule set can be a versioned file of label strings or label-to-description dicts. [DER S-y42nqxiw, S-sislku4q: truncation behaviour and call-time labels]
- Licence screen: the library and the cards read are Apache-2.0, the `onnx-community` repo declares none, and GLiREL's two statements disagree and include an NC clause, so it needs a decision before use. [DER S-7bjdu5bv, S-7ke3sttd, S-z3khz6q6, S-ngy65th6, S-pjp4rzor: licence fields as read]

## Reference
- Anchor: `privacy/gliner-models.md` covers the PII cards (`urchade/gliner_multi_pii-v1`, `knowledgator/gliner-pii-base-v1.0`, `nvidia/gliner-PII`); this topic covers the library, the general cards, ONNX and GLiREL.
- Related: `agents/shared-ner-service.md` (serving shapes, community ONNX exports); `privacy/spacy-model-licence.md` (spaCy model licences).
- Library docs at tag v0.2.29: `docs/usage.md` (input limits and truncation), `docs/configs.md`, `docs/convert_to_onnx.md`.
- Hugging Face repos are cited at their `sha` as read through the HF API with `?blobs=true` (file sizes and SHA-256).

## Examples
- SNIPPET: load the multilingual card on CPU and extract entities with call-time labels; context: gliner 0.2.29, model files fetched on first call (or `local_files_only=True` after a mirror), Polish quality unconfirmed; checked: syntax [DER S-rvd2zkel, S-7ke3sttd: call shape from the README and card]
```python
from gliner import GLiNER

model = GLiNER.from_pretrained("urchade/gliner_multi-v2.1", map_location="cpu")
text = "Jan Kowalski podpisal umowe z firma Example Sp. z o.o. w Warszawie."
labels = ["person", "organization", "location"]
for entity in model.predict_entities(text, labels, threshold=0.5):
    print(entity["text"], entity["label"], round(entity["score"], 2))
```
- SNIPPET: refuse input longer than the checkpoint's `max_len` instead of truncating silently; context: gliner 0.2.29, `prepare_batch` as shown in the library docs; checked: syntax [DER S-y42nqxiw: preflight pattern from the library docs]
```python
def too_long(model, text, labels):
    prepared = model.prepare_batch(text, labels)
    tokens = prepared["tokens"][0] if prepared["tokens"] else []
    return len(tokens) > model.config.max_len
```
- SNIPPET: export a checkpoint to ONNX and load it back on CPU; context: gliner 0.2.29 with `gliner[onnx]` and `onnx` installed, run once on a machine that can reach the model repo; checked: syntax [DER S-hfifhdhx: calls from convert_to_onnx.md]
```python
from gliner import GLiNER

model = GLiNER.from_pretrained("urchade/gliner_multi-v2.1")
paths = model.export_to_onnx(
    save_dir="exports/onnx",
    onnx_filename="model.onnx",
    quantized_filename="model_int8.onnx",
    quantize=True,
)
onnx_model = GLiNER.from_pretrained(
    "exports/onnx",
    runtime="onnxruntime",
    runtime_model_file="model.onnx",
    local_files_only=True,
)
```
- SNIPPET: classify relations between two given entity spans with GLiREL; context: glirel 1.2.1, `glirel-large-v0`, token indices inclusive, licence unresolved (see Facts); checked: syntax [DER S-ngy65th6: call shape from the README]
```python
from glirel import GLiREL

model = GLiREL.from_pretrained("jackboyla/glirel-large-v0")
tokens = ["Jan", "Kowalski", "founded", "Example", "Ltd", "."]
ner = [[0, 1, "PERSON", "Jan Kowalski"], [3, 4, "ORG", "Example Ltd"]]
labels = ["founder", "no relation"]
relations = model.predict_relations(tokens, labels, threshold=0.0, ner=ner, top_k=1)
```
