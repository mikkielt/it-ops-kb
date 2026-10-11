---
topic: privacy/morfeusz-polish-lemmatisation
priority: P3
applies_to: "Morfeusz 2 1.99.15 (PyPI morfeusz2 1.99.15; dictionaries SGJP and Polimorf 2026-08-24 builds); spaCy 3.8.x with pl_core_news_sm/md/lg 3.8.0 and spacy-lookups-data 1.0.5"
retrieved_utc: 2026-10-11
sources: [S-fkosk2vn, S-lbstvu2m, S-v6tu47om, S-caclcxya, S-zfdnyluh, S-xz7r3unc, S-jhuny2li, S-d3lsp242, S-jvn5jnee, S-g6zhzddt, S-te5pgsg3, S-haoeqge5, S-pxcitvg3, S-sirpm4j2, S-fgod2hh4, S-tzw22ffl, S-7mdjthbr, S-ix7uqv2r, S-ohpwxaqx, S-igmmjjid, S-u2shnqdn, S-kpfntmtz, S-c3pmsz4l, S-i6a2ijlk, S-2b4qw6yv, S-c2dp6hok, S850]
status: partial
---

# Morfeusz 2 and Polish lemmatisation (with the spaCy fallback)

## Summary
- Morfeusz 2 (IPI PAN) is a dictionary-based morphological analyser and generator for Polish. Its PyPI package `morfeusz2` 1.99.15 is a wheel-only, self-contained binding: the SGJP dictionary is inside the library, so it needs no download at runtime. Wheels exist for CPython 3.10 and later on Linux x86_64, macOS (universal2) and Windows x86_64 only.
- Program and the SGJP and Polimorf inflection data are BSD 2-clause. The lemmas carry a homonym suffix after a colon (`piec:S`) that a consumer strips, but not every colon is a suffix.
- Without Morfeusz, the Polish spaCy pipelines `pl_core_news_sm/md/lg` 3.8.0 lemmatise with a trainable edit-tree lemmatizer (lemma accuracy 93.02 to 94.19 on the vendor's test set), but they are licensed GPL-3.0, unlike the MIT `en_core_web_lg`. The rule-based `PolishLemmatizer` (lookup tables derived from Morfeusz data) needs a POS tag from another component.

## Facts

### Morfeusz 2: output and tagset
- Morfeusz 2 is IPI PAN's C++ analyser and generator for Polish, shipped as a dynamic library with C, Java and Python interfaces. It has no module for guessing unknown words, so it behaves as an inflectional dictionary. [DOC S-v6tu47om]
- The latest PyPI `morfeusz2` is 1.99.15 (uploaded 2026-06-01); the official site's 20260823 release carries the same library version 1.99.15 in its artifact names. [DOC S-caclcxya, S-jvn5jnee]
- In Python, `Morfeusz().analyse(text)` returns edges of an analysis graph as `(start_node, end_node, interpretation)`; the interpretation is a 5-tuple of form, lemma, tag, a list of proper-name classes and a list of stylistic or domain qualifiers. [DOC S-v6tu47om]
- The wheel's `analyse` builds that tuple from `orth, lemma, tag, name, labels`. By default (`expand_tags=False`, `expand_dag=False`) packed dotted tags such as `adj:pl:nom.voc:f.n:pos` stay packed and a flat edge list is returned; `expand_dag=True` returns paths without node ids. [CODE S-zfdnyluh: morfeusz2.py#Morfeusz.analyse]
- Analysis ignores context: every interpretation of a segment is returned (the sample `mam` gets lemmas `mama`, `mamić`, `mieć`), and a segment can split in several ways, which is why the result is a graph and not a list. Choosing one interpretation is left to a tagger. [DOC S-v6tu47om]
- A segment unknown to the dictionary gets the tag `ign` and a lemma equal to its form; punctuation gets `interp`, digit strings `dig`, symbols such as emoji `sym`. [DOC S-v6tu47om]
- Tags are positional: the first position is the part-of-speech class (`subst`, `adj`, `fin`, ...), later positions depend on the class; the system is the IPI PAN corpus tagset with small changes. [DOC S-fkosk2vn, S-v6tu47om]
- The shipped tagset file is `pl.sgjp.morfeusz-0.8.0`; counting its entries gives 45 distinct classes, among them `part`, `ign` and `sp` but not `qub`, `burk`, `numcol` or `xxx`. [CODE S-xz7r3unc: Morfeusz/input/morfeusz-sgjp.tagset#TAGSET-ID]

### Lemma disambiguation suffixes
- Where lexemes are homonyms, the lemma gets a colon and a distinguishing element: a coarse class (`piec:S` noun, `piec:V` verb), gender or other features (`pływak:Sm1`) or a differing ending (`napaść:Vp~dnę`). Older versions used numbers (`słać:v1`). The authors note that most users drop these marks. [DOC S-v6tu47om]
- In the SGJP export of 2026-08-24, 76,530 of 387,398 distinct lemmas carry a colon suffix; none has a second colon or starts with one. One run of ours on the pinned file; the count is not a rule. [DER S-te5pgsg3, S-v6tu47om: lemmas counted in column 2 of sgjp-20260823.tab.gz]
- Not every colon is a suffix: the additional-segment table has the punctuation lemma `:` (tag `interp`), 22 `sym` emoticons such as `:-)`, and one real suffix (`to:V`, tag `pred`). [CODE S-xz7r3unc: Morfeusz/input/dodatki.tab#:]

### Dictionaries, selection and licence
- Three inflectional data variants exist: SIaT (oldest, archival only), SGJP (default) and Polimorf (SGJP plus community Morfologik/sjp.pl data); the manual says Morfeusz ships with SGJP and Polimorf. [DOC S-fkosk2vn, S-v6tu47om]
- A dictionary is chosen with `Morfeusz(dict_name=..., dict_path=...)`; the library holds a list of search paths, loads the first dictionary of that name and keeps one file for analysis and one for synthesis. [DOC S-v6tu47om]
- The file name is `<name>-a.dict` (analysis) or `<name>-s.dict` (synthesis); a missing one raises "Failed to load analyzer dictionary". [CODE S-xz7r3unc: Morfeusz/morfeusz/DictionariesRepository.cpp#DictionariesRepository::getDictionaryFilename]
- The 20260823 release has separate dictionary archives `morfeusz2-dictionary-sgjp-20260823.tgz` and `...-polimorf-20260823.tgz`; each holds `<name>-a.dict` and `<name>-s.dict` with an embedded id (`pl.sgjp.sgjp-2026.08.24`, `pl.waw.ipipan.polimorf-2026.08.24`) and BSD notice. [DER S-jvn5jnee, S-jhuny2li, S-d3lsp242: archive listing and the id and notice read from the files]
- The program and the inflection data of SGJP and Polimorf are released under the 2-clause BSD licence; IPI PAN owns the program and Polimorf, the SGJP authors the SGJP data. Only the form list is BSD, not the whole SGJP dictionary, and SIaT keeps its older terms. [DOC S-lbstvu2m]
- The authors chose BSD because analysis output contains dictionary fragments and so is a derivative of the dictionary; a copyleft dictionary licence would reach tagged corpora. BSD asks only to keep authorship notices. [DOC S-lbstvu2m]
- The wheel holds only the two shared libraries, the SWIG-generated Python module and dist-info, with no licence file; the source tarball's `License.txt` is a one-line stub. The BSD notice therefore reaches a consumer through `dict_copyright()` or the licence page. [DER S-zfdnyluh, S-xz7r3unc: archive listings]

### The Python binding and its distribution
- PyPI `morfeusz2` 1.99.15 has only wheels, no source distribution: `cp310-abi3` for `macosx_11_0_universal2`, `manylinux_2_28_x86_64` and `win_amd64`; the package declares no `requires_python`. [DOC S-caclcxya]
- Derivation: the abi3 tag means CPython 3.10 or later on exactly those three platforms; Linux aarch64, musl and 32-bit Windows have no 1.99.15 wheel and, with no sdist, `pip` cannot build one. The PyPI file list has no aarch64 file and the official `manylinux_2_28` directory lists only Linux-amd64 files. Import was not run here. [DER S-caclcxya, S-g6zhzddt: wheel tags and directory listing]
- The wheel is self-sufficient and embeds the SGJP dictionary; PyPI is updated by hand every few months, while the SGJP database is checked weekly and packages are rebuilt on change, so newer wheels appear on the official site first. [DOC S-v6tu47om, S-jvn5jnee]
- The PyPI 1.99.15 wheel (build 20260601) embeds dictionary id `pl.sgjp.sgjp-2026.06.01` and library version 1.99.15 in `libmorfeusz2.so`, not the 2026-08-24 data of the site. [DER S-zfdnyluh, S-jvn5jnee: strings of the pinned wheel]
- One `Morfeusz` object may be used by one thread at a time; instances are created in one thread (loading is not safe in parallel) and handed to workers. [DOC S-v6tu47om]

### The fallback: spaCy Polish pipelines
- GitHub releases `pl_core_news_sm`, `_md` and `_lg` 3.8.0 (2024-09-30): licence GNU GPL 3.0, author Explosion, spaCy `>=3.8.0,<3.9.0`, size 19, 47 and 547 MB. [DOC S-haoeqge5, S-pxcitvg3, S-sirpm4j2]
- Their lemmatizer is the trainable one: `config.cfg` sets `factory = "trainable_lemmatizer"` with `backoff = "orth"`. [CODE S-fgod2hh4: pl_core_news_sm/pl_core_news_sm-3.8.0/config.cfg#components.lemmatizer]
- Vendor test-set LEMMA_ACC is 93.02 (sm), 93.71 (md) and 94.19 (lg); the training sources are UD Polish PDB v2.8 and the National Corpus of Polish, both listed under GNU GPL 3.0 in `LICENSES_SOURCES`. [DOC S-haoeqge5, S-pxcitvg3, S-sirpm4j2, S-fgod2hh4]
- `compatibility.json` lists only 3.8.0 of the three Polish packages, for spaCy 3.8; PyPI `spacy` is 3.8.16 (2026-08-24). The Hugging Face repos `spacy/pl_core_news_*` stay at card version 3.7.0 (sha `d9f6ef1` for sm, modified 2023-10-10), also `gpl-3.0`. [DOC S-7mdjthbr, S-ix7uqv2r, S-tzw22ffl]
- spaCy's `Polish` language class registers a `lemmatizer` factory whose default mode is `pos_lookup` and which builds a `PolishLemmatizer`. [CODE S-igmmjjid: spacy/lang/pl/__init__.py#make_lemmatizer]
- `PolishLemmatizer`'s own comment says it does lookup lemmatisation based on the Morfeusz dictionary; it needs the tables `lemma_lookup_adj`, `_adp`, `_adv`, `_aux`, `_noun`, `_num`, `_part`, `_pron` and `_verb`. [CODE S-ohpwxaqx: spacy/lang/pl/lemmatizer.py#PolishLemmatizer.get_lookups_config]
- `PolishLemmatizer` picks its table from `token.pos_` (PROPN uses the noun table) and returns the lowercased form when there is no table. [CODE S-ohpwxaqx: spacy/lang/pl/lemmatizer.py#PolishLemmatizer.pos_lookup_lemmatize]
- The tables are not in spaCy: `Lemmatizer.initialize` loads them from `spacy-lookups-data` when none are given, and `load_lookups` raises an error if the package is absent. [CODE S-u2shnqdn: spacy/pipeline/lemmatizer.py#Lemmatizer.initialize]
- `spacy-lookups-data` 1.0.5 (2023-07-28) is MIT, and its `pl_license.txt` gives BSD-style notices for Polimorf `2020.05.03` and SGJP `2020.05.03`: so the Polish tables date from a 2020 snapshot of the same data, six years behind the site's dictionaries. [DER S-kpfntmtz, S-c3pmsz4l: dictionary ids named in the licence file read with the release date of the package]
- The noun, verb and adjective tables hold 1,551,066, 1,838,029 and 386,314 form-to-lemma entries, one lemma per form and none with a colon suffix. One run of ours on the pinned files. [DER S-i6a2ijlk, S-2b4qw6yv, S-c2dp6hok: entries counted and values scanned for ":"]

### How it fits (derived)
- Offline, CPU-only Morfeusz arm: the wheel carries the dictionary and needs no network at run time; pin the wheel by sha256 and log `dict_id()` next to each lemma batch, because the dictionary build date differs between PyPI and the site and lemmas change with it. [DER S-caclcxya, S-zfdnyluh, S-v6tu47om: wheel hash and embedded dictionary id]
- One lemma per token needs a tagger: Morfeusz returns all candidates. The spaCy tagger labels (`QUB`, `BURK`, `NUMCOL`, `XXX`) differ from Morfeusz classes (`part`, `ign`), so a mapping layer is needed to select an interpretation by tag. [DER S-haoeqge5, S-xz7r3unc: label scheme of the release against the tagset classes]
- The spaCy lookup lemmatizer cannot lemmatise raw text alone: with no `pos_` it finds no table and returns the lowercased form, and the only pretrained Polish tagger from Explosion is the GPL-3.0 `pl_core_news_*`. [DER S-ohpwxaqx, S-haoeqge5: pos_lookup_lemmatize read with the model licence]
- The licence duties differ per arm: BSD notices for Morfeusz and its dictionaries, GPL-3.0 for `pl_core_news_*`, while `en_core_web_lg` is MIT (see `privacy/spacy-model-licence.md`). A mixed Polish and English service therefore has two licence regimes to review. [DER S-lbstvu2m, S-haoeqge5, S850: licence statements side by side]
- Whether the edit-tree model (trained on UD Polish PDB lemmas) and Morfeusz give the same lemma for the same word is not confirmed, so a lemma-keyed rule set cannot assume the arms agree. [UNK: agreement between the two arms was not measured]
- Suffix rule: strip after the first colon only when the head is not empty and the tag class is not `ign`, `interp`, `sym`, `dig` or `romandig`, which keep colons in their lemmas. [DER S-xz7r3unc, S-te5pgsg3: dodatki.tab and the SGJP export]
- Throughput and memory of one `Morfeusz` instance, and the terms of the SIaT variant, are not in the pages read. [UNK]

## Reference
| Item | Value |
|---|---|
| `morfeusz2` on PyPI | 1.99.15, 2026-06-01, wheels only, `cp310-abi3` |
| Wheel platforms | `macosx_11_0_universal2`, `manylinux_2_28_x86_64`, `win_amd64` |
| Morfeusz licence | 2-clause BSD (program, SGJP, Polimorf data) |
| Dictionary ids (site, 20260823) | `pl.sgjp.sgjp-2026.08.24`, `pl.waw.ipipan.polimorf-2026.08.24` |
| Dictionary id in the PyPI wheel | `pl.sgjp.sgjp-2026.06.01` |
| `pl_core_news_sm` / `md` / `lg` | 3.8.0, GPL-3.0, 19 / 47 / 547 MB, lemma acc 93.02 / 93.71 / 94.19 |
| Wheel sha256 (`pl_core_news_sm` 3.8.0) | `9b536db854b0cdb9132a74f68b392b8112ab6030f971bb03282462362a940dbb` |
| `spacy-lookups-data` | 1.0.5, MIT, Polish tables from Polimorf and SGJP 2020.05.03 |

See also `privacy/spacy-model-licence.md` (licence and checksums of `en_core_web_lg`).

## Examples
- SNIPPET: list analysis edges for a Polish sentence with the default (SGJP) dictionary; context: `morfeusz2` 1.99.15 wheel, CPython 3.10 or later; checked: syntax [DER S-v6tu47om, S-zfdnyluh: constructor and tuple layout from the manual and the wheel's module]

```python
import morfeusz2

morf = morfeusz2.Morfeusz()
print(morf.dict_id())
for start, end, (orth, lemma, tag, name, labels) in morf.analyse("Mam próbkę analizy morfologicznej."):
    print(start, end, orth, lemma, tag, name, labels)
```

- SNIPPET: drop the homonym suffix of a Morfeusz lemma except for classes whose lemma may hold a colon; context: rule derived from the SGJP export and `dodatki.tab` of release 20260823; checked: syntax [DER S-xz7r3unc, S-te5pgsg3: classes taken from dodatki.tab and the lemma count]

```python
KEEP_WHOLE = {"ign", "interp", "sym", "dig", "romandig"}


def base_lemma(lemma: str, tag: str) -> str:
    cls = tag.split(":", 1)[0]
    if cls in KEEP_WHOLE:
        return lemma
    head, sep, _suffix = lemma.partition(":")
    return head if sep and head else lemma
```
