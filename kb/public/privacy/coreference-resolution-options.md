---
topic: privacy/coreference-resolution-options
priority: P3
applies_to: "spacy-experimental 0.6.4; fastcoref 2.1.6 (PyPI) and main @ae22413; coreferee 1.5.0; herference @657eda2; CorPipe 24 @aaf90f0; allennlp 2.10.1; neuralcoref 4.0.0; IPI PAN Ruler and Bartek"
retrieved_utc: 2026-10-11
sources: [S-gz6vychk, S-kp4hr5hg, S-zymyxmg5, S-2icfoxql, S-35hkzfyb, S-5twstxnc, S-ocgbnk4i, S-wd6aqhk3, S-ix7uqv2r, S-ygt5635t, S-ix32u5vu, S-lvf4vsum, S-oetpt5t7, S-cbfcxnwp, S-m6gdqyyo, S-7f4d52ha, S-xf7ynxdt, S-ixa2vaqw, S-yydpfutu, S-mxdbr2k2, S-blq5nxf2, S-6qgprb3q, S-fvrqnhop, S-xg33uza6, S-chminfqh, S-kdsj7amh, S-zcu63phy, S-lva6e5k2, S-h5hcpb6z, S-2egs3y3u, S-6j4ijcxo, S-el226szq, S-uznr3g4z, S-gur4fjbl, S-ukgogmmx, S-zynjjt6b, S-vfwwrhjc, S-537stu5l, S-6owdinqk, S-p6ormh2r, S-zt6artnx, S-6wb3kouw, S-rarraofb, S-hodbmqjs, S-36c52acv, S-5qzwrdja, S-c6kvn3ps, S-oa5ipfj6, S-xhyyf6km, S-36nisfrm, S-mo3khkbn]
status: partial
---

# Coreference resolution options for Polish and English text

## Summary
- Nine options were read at pinned tags or commits: spaCy's experimental `coref` and `span_resolver`, fastcoref, coreferee, Herference, CorPipe 24, the IPI PAN tools Ruler and Bartek, AllenNLP, neuralcoref and crosslingual-coreference.
- Polish support is stated by coreferee (English, French, German and Polish), Herference (Polish only), CorPipe 24 (multilingual, Polish among its training corpora) and the IPI PAN tools (Polish only). The spaCy experimental pipeline, fastcoref, AllenNLP and neuralcoref state English only.
- Licence terms differ a lot: Herference weights are CC BY-NC 4.0, the CorPipe model is CC BY-NC-SA 4.0, and the Polish spaCy models coreferee and Herference rely on are GPL-3.0.
- The comparison table is in the Reference section. No option is recommended here.

## Facts
### spaCy `coref` and `span_resolver` (spacy-experimental)
- The `coref` component is documented as experimental and "not yet integrated into spaCy core": it comes from the `spacy-experimental` package (0.6.0 onward) and is used as factory `experimental_coref`; the `SpanResolver` is the matching `experimental_span_resolver`, meant to expand its single-token output into spans. [DOC S-2icfoxql, S-35hkzfyb]
- The package README warns "Components and features may be modified or removed in any release", so an exact version is to be pinned. The newest release on PyPI is 0.6.4 (2023-11-02, MIT), and the latest commit on master is dated 2023-11-03; the README has no other status statement. [DOC S-kp4hr5hg, S-gz6vychk, S-wd6aqhk3]
- Release 0.6.4 declares `spacy>=3.3.0,<3.8.0`. [CODE S-zymyxmg5: setup.cfg#options.install_requires]
- The only pretrained pipeline is the demonstration pipeline `en_coreference_web_trf` 3.4.0a2 (spacy-experimental release v0.6.1, "for demonstration purposes"): English, MIT, spaCy `>=3.3.0,<3.5.0`, needs `spacy-transformers`, built on roberta-base and trained on OntoNotes 5 (licensed to Explosion), COREF_F 72.58. [DOC S-5twstxnc, S-ocgbnk4i]

### fastcoref
- The newest PyPI release is 2.1.6 (2023-05-26, MIT). The README presents the repository as the official implementation of the F-COREF paper, with the models `FCoref` and the larger `LingMessCoref` and a spaCy v3 component named `fastcoref` that accepts `'device': 'cpu'`. [DOC S-ygt5635t, S-ix32u5vu]
- Both model cards (`biu-nlp/f-coref`, `biu-nlp/lingmess-coref`) state `license: mit` and `language: en`, with OntoNotes among the training data; the README names training on other data as the way to additional languages. [DOC S-xf7ynxdt, S-ixa2vaqw, S-ix32u5vu]
- With no `device` argument the model runs on CUDA when it is available and on CPU otherwise; the model name defaults to the Hugging Face id `biu-nlp/f-coref` and the tokenizer spaCy model to `en_core_web_sm`. [CODE S-oetpt5t7: fastcoref/modeling.py#CorefModel._set_device]
- The spaCy component's default configuration has `"device": None` (commented as defaulting to cuda), model `biu-nlp/f-coref` and `FCoref`. [CODE S-cbfcxnwp: fastcoref/spacy_component/spacy_component.py#FastCorefResolver]
- Release 2.1.6 requires `spacy>=3.0.6`, `torch>=1.10.0`, `transformers>=4.11.3` and `datasets>=2.5.2` for Python 3.7 or newer. [CODE S-lvf4vsum: setup.py#install_requires]
- Commit ae22413 on the default branch declares version 2.2.3 and requires Python `>=3.11,<3.14`, `spacy>=3.8.14`, `torch>=2.12.0` and `transformers>=5.9.0`. [CODE S-m6gdqyyo: pyproject.toml#project.dependencies]
- That commit is dated 2026-05-21 while PyPI's newest release is 2.1.6, so the 2.2.x line was not on PyPI at retrieval. [DER S-7f4d52ha, S-ygt5635t: commit feed date against the PyPI release list]
- The F-Coref card gives timings on one NVIDIA V100 only (2.8K OntoNotes documents in 25 seconds at 4.0 GiB with leftover batching). [DOC S-xf7ynxdt]

### coreferee
- The README states "Coreferee is maintained for compatibility with current spaCy releases", names Python 3.10 to 3.13 and spaCy 3.7 to 3.8 for the current release, and covers English, French, German and Polish. Version 1.5.0 reached PyPI on 2026-09-15 and declares `spacy` as its only dependency. [DOC S-mxdbr2k2, S-yydpfutu]
- The manifest sets `requires-python = ">=3.10,<3.14"`, `spacy>=3.2.0,<3.9.0`, licence MIT, and registers the spaCy factory `coreferee` by entry point. [CODE S-blq5nxf2: pyproject.toml#project.dependencies]
- For Polish it ships models for `pl_core_news_lg` and `pl_core_news_md` only (`pl_core_news_sm` unsupported since 1.1.0, no transformer pipeline), trained on the Polish Coreference Corpus (548,268 words); the README reports anaphor accuracy 72 to 76 (lg) and 70 to 75 (md) on held-out data it calls "indicative rather than fully independent". Zero anaphors are covered for subjects only. [DOC S-mxdbr2k2]
- The rules cover anaphors, with only limited noun-phrase coreference, and mentions are single tokens or coordinated token lists, not spans. [DOC S-mxdbr2k2]
- The Polish model config maps Coreferee models to spaCy pipeline (model) versions 3.0.0 to 3.5.0, 3.7.0 to 3.7.5 and 3.8.0 to 3.8.11, for the `lg` and `md` pipelines. [CODE S-fvrqnhop: coreferee/lang/pl/config.cfg#lg_3_8_0]
- `python -m coreferee install pl` pip-installs `coreferee_model_pl.zip` from the `raw/master/models` path of the GitHub repository (a branch, not a tag) unless a checkout holds a `models` directory. [CODE S-6qgprb3q: coreferee/__main__.py#DOWNLOAD_URL]
- The Polish archive at tag v1.5.0 holds `lg` and `md` model directories for pipeline versions 3_2_0, 3_7_0 and 3_8_0, 72,938,566 bytes, sha256 `2d3e2516f3bbc22f51fb10a44859c9cbd14c961ad287b539f6666ea2f947ec10`; the README's "20GB-30GB" per language does not match it. [DER S-xg33uza6, S-mxdbr2k2: archive listing and size at the tag against the README sentence]
- The Polish pipelines it needs are licensed GPL-3.0 (card `spacy/pl_core_news_lg`, trained on UD Polish PDB and the National Corpus of Polish). [DOC S-chminfqh]
- The Polish training corpus is released by IPI PAN under CC BY-NC 4.0 on its own page; whether that term reaches the model weights in the Coreferee archive is not stated. [UNK]

### Herference (IPI PAN, CLARIN-PL)
- The README describes "Coreference Resolution for Polish language", with a spaCy component `herference` that takes `"device": "cpu"`; CLARIN-PL runs the same tool as a service on a HerBERT-based model with a 512-token input limit. [DOC S-vfwwrhjc, S-rarraofb]
- The repository is GPL-3.0 and the weights `ipipan/herference-large` carry `license: cc-by-nc-4.0`. The latest commit is 2024-09-19 and no maintenance status is stated. [DOC S-6owdinqk, S-6wb3kouw, S-hodbmqjs]
- The manifest requires Python `>=3.9,<3.13`, `torch>=2.0.0` (not 2.0.1 or 2.1.0), `transformers ^4.35.0`, `spacy ^3.7.2` and `spacy-transformers ^1.3.5`. [CODE S-537stu5l: pyproject.toml#tool.poetry.dependencies]
- The default model id is `ipipan/herference-large` and the default spaCy model is `pl_core_news_lg`. [CODE S-zt6artnx: herference/config.py#Config]
- Device defaults to CUDA when available, else CPU; the tokenizer is always loaded from the default model id; a missing spaCy model is downloaded at run time. [CODE S-p6ormh2r: herference/manager.py#Herference.__init__]

### CorefUD and CorPipe 24
- The CorefUD v1.4 licence page says each corpus has its own terms and lists Polish-PCC as CC BY 3.0; the PCC page itself says CC BY-NC 4.0, so the two pages disagree. [DOC S-el226szq, S-kdsj7amh]
- CorPipe 24 is an mT5-large-based multilingual model trained on 21 CorefUD 1.2 corpora, including `pl_pcc`, `en_gum` and `en_litbank`; the model is CC BY-NC-SA 4.0, the code MPL-2.0, and the README reports 75.2 on the Polish test set. [DOC S-uznr3g4z, S-gur4fjbl]
- The predictor asserts at least as many GPUs as loaded models and places each on `/gpu:i`, so the script as shipped has no CPU path. [CODE S-ukgogmmx: corpipe24.py#ModelEnsemble.__init__]
- It pins `tensorflow~=2.12.0` and `transformers~=4.29.0`. [CODE S-zynjjt6b: requirements.txt#tensorflow]
- Plain text must first be converted to CoNLL-U; the README does it through the UDPipe 2 web service. [DOC S-gur4fjbl]
- A local, offline route for that conversion was not read. [UNK]

### IPI PAN Ruler and Bartek
- Ruler (rule-based) and Bartek (statistical, default models trained on the full PCC) are Polish tools released under CC BY 3.0 as Maven artifacts (version 1.3); the Ruler page's demo chain feeds them mentions from other IPI PAN Polish tools. The pages were last edited in 2016. [DOC S-h5hcpb6z, S-lva6e5k2, S-zcu63phy]
- The Bartek repository has 14 commits, no tags and no README, the last on 2019-04-10. [DOC S-6j4ijcxo]
- Its manifest has version 1.4 and `java.version` 1.8. [CODE S-2egs3y3u: pom.xml#java.version]

### Archived or stale options
- AllenNLP states "The AllenNLP library is now in maintenance mode" (README at v2.10.1) and the repository was archived on 2022-12-16. The `coref-spanbert` model card has a `license` of null, trains on OntoNotes 5.0 and gives install instructions that pin `allennlp==2.1.0`. [DOC S-36c52acv, S-c6kvn3ps, S-5qzwrdja]
- neuralcoref: the README says it is an extension for spaCy 2.1+ that "comes with a pre-trained statistical model for English only", under MIT; PyPI's last release is 4.0 (2019-04-08); the repository banner says it was archived on 2026-09-17. [DOC S-oa5ipfj6, S-xhyyf6km, S-36nisfrm]
- crosslingual-coreference 0.3.1 (2023-06-19, MIT) requires `allennlp>=2.9,<2.10`, `spacy>=3.1,<3.2` and Python below 3.12; its README trains on English data and says cross-lingual embeddings "should work for languages with similar sentence structures", without naming Polish. [DOC S-mo3khkbn]

### Not confirmed
- A pretrained spaCy pipeline named `en_coref_lg` was not found; only `en_coreference_web_trf` exists in the sources read. [UNK]
- Throughput of any option on CPU: the sources give no CPU timings. [UNK]
- The `ipipan/herference-base` model named in the Herference README example returned no public API record (HTTP 401) on 2026-10-11. [UNK]

### How it fits
- Context: a self-hosted Polish and English text-corpus service, Python over a Rust core, CPU-only, offline-capable, model artifacts pinned by hash. Options with stated Polish support are coreferee, Herference, CorPipe 24 and Ruler/Bartek; English-only are the spaCy experimental pipeline, fastcoref, AllenNLP and neuralcoref. [DER S-mxdbr2k2, S-vfwwrhjc, S-uznr3g4z, S-lva6e5k2, S-ocgbnk4i, S-xf7ynxdt, S-oa5ipfj6, S-36c52acv: language statements of each source]
- CPU: the shipped CorPipe script has no CPU path; fastcoref and Herference fall back to CPU when no CUDA device exists; the Coreferee pages state no GPU requirement and its manifest depends only on spaCy. [DER S-ukgogmmx, S-oetpt5t7, S-p6ormh2r, S-blq5nxf2: device handling and dependencies read above]
- Offline: fastcoref and Herference load weights by Hugging Face id, Herference also downloads a spaCy model and loads its tokenizer by the default id, coreferee installs a zip from a GitHub branch and neuralcoref downloads weights on first import; each needs a prior fetch and a hash check of the local copy. [DER S-oetpt5t7, S-p6ormh2r, S-6qgprb3q, S-oa5ipfj6, S-xg33uza6: where each tool fetches its weights]
- Licence: Herference weights (CC BY-NC 4.0), the CorPipe model (CC BY-NC-SA 4.0) and PCC on its own page (CC BY-NC 4.0) carry non-commercial terms, while Herference code and `pl_core_news_lg` are GPL-3.0; each constrains a service, and the licence read at retrieval has to be rechecked per artifact. [DER S-6wb3kouw, S-gur4fjbl, S-kdsj7amh, S-6owdinqk, S-chminfqh: licence statements read above]
- spaCy version: spaCy 3.8.16 is the newest release on PyPI; it is inside the ranges of coreferee (`<3.9.0`) and Herference (`^3.7.2`), outside the `<3.8.0` cap of the newest spacy-experimental, and the demonstration coref pipeline is capped at `<3.5.0`. [DER S-ix7uqv2r, S-blq5nxf2, S-537stu5l, S-zymyxmg5, S-ocgbnk4i: version ranges compared]

## Reference
Status is as each source states it; "no statement" means none was found in the pages read.

| Option | Status as stated | Languages stated | Licence (code / weights) | CPU / offline | spaCy requirement |
|---|---|---|---|---|---|
| spacy-experimental `experimental_coref` + `experimental_span_resolver` 0.6.4 | "experimental", may change or go in any release; last release 2023-11-02 | pretrained pipeline English only; components are trainable | MIT / pipeline MIT (trained on OntoNotes 5) | not stated; pipeline wheel from a GitHub release | `>=3.3.0,<3.8.0`; pipeline `>=3.3.0,<3.5.0` |
| fastcoref 2.1.6 (PyPI), main at 2.2.3 | no statement; PyPI 2023-05-26, commits to 2026-05-21 | English (cards) | MIT / MIT | CPU fallback when no CUDA; weights by hub id | `>=3.0.6` (2.1.6), `>=3.8.14` (main) |
| coreferee 1.5.0 | "maintained for compatibility with current spaCy releases" | English, French, German, Polish | MIT / models in the MIT repository; PCC corpus terms unconfirmed | no GPU requirement stated; models zip from a GitHub branch | `>=3.2.0,<3.9.0`; Polish needs `pl_core_news_lg` or `md` |
| Herference (IPI PAN, CLARIN-PL) | no statement; last commit 2024-09-19 | Polish | GPL-3.0 / CC BY-NC 4.0 | CPU fallback; hub id, spaCy model downloaded at run time | `^3.7.2` |
| CorPipe 24 (UFAL) | no statement; repository snapshot of 2024-10-17 | 21 corpora incl. Polish and English | MPL-2.0 / CC BY-NC-SA 4.0 | shipped script asserts GPUs; TensorFlow 2.12 | none (CoNLL-U in and out) |
| IPI PAN Ruler and Bartek | no statement; pages 2016, last commit 2019-04-10 | Polish | CC BY 3.0 (page) | Java 8 and Maven; no GPU | none |
| AllenNLP coref (`coref-spanbert`) | archived 2022-12-16, maintenance mode | English (OntoNotes) | Apache-2.0 / not stated (null) | not stated | none |
| neuralcoref 4.0 | archived 2026-09-17; last release 2019-04-08 | English only | MIT / MIT | weights downloaded on first import | `>=2.1.0` (spaCy 2.1+) |
| crosslingual-coreference 0.3.1 | no statement; 2023-06-19 | English trained, cross-lingual claim, Polish not named | MIT / n/a | not stated | `>=3.1,<3.2` |

See also `privacy/spacy-model-licence.md` (the licence of the English spaCy model `en_core_web_lg`).

## Examples
- SNIPPET: Coreferee on a Polish text through the spaCy pipeline; context: coreferee 1.5.0, spaCy 3.7 or 3.8, `pl_core_news_lg` installed and `python -m coreferee install pl` run; checked: syntax [DOC S-mxdbr2k2]

```python
import spacy

nlp = spacy.load("pl_core_news_lg")
nlp.add_pipe("coreferee")
doc = nlp("Anna wzięła książkę, bo ona ją lubiła.")
doc._.coref_chains.print()
```
