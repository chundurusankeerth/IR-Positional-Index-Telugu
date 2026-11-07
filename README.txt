Information Retrieval Assignment 1: Positional Inverted Index
Roll number: S20240010050

About the project

This project builds a positional inverted index for Telugu Wikipedia articles.
For each word, it stores the document frequency, collection frequency and all
positions where the word occurs. It supports single-word and exact-phrase searches.

Dataset

The dataset is the Telugu Wikipedia articles dump:
tewiki-latest-pages-articles-multistream.xml.bz2

Official download link:
https://dumps.wikimedia.org/tewiki/latest/tewiki-latest-pages-articles-multistream.xml.bz2

The full compressed file was processed without a document limit. Only articles in
the main namespace were selected. Redirects and pages with no usable text were
skipped. Wikipedia page IDs are used as document IDs, and titles are also stored.

Results from the run:
  Pages read:                 240,452
  Articles indexed:           130,236
  Non-main-namespace pages:    72,289
  Redirects skipped:          37,915
  Pages with no tokens:       12
  Vocabulary size:            2,909,293
  Total token occurrences:    58,044,470
  Term-document postings:     34,465,765

The dump is 276,043,990 bytes. Its SHA-256 is:
83ff53f5b3f8447ad5c4abaef0f8d3e6d7af48a71e04ebaa954859ffe6a4e519

The download link points to the latest dump, so a later download may give different
results. The checksum above identifies the file used for this submission.
Wikipedia content retains its source licence and attribution requirements. An
article can be found at https://te.wikipedia.org/?curid= followed by its page ID.

Files

src/extract_articles.py  Reads the compressed XML and writes cleaned articles.
src/tokenizer.py         Contains the tokenizer used for indexing and searching.
src/build_index.py       Builds the SQLite index and checks DF, CF and positions.
src/search.py            Retrieves word postings and exact-phrase matches.
src/generate_tests.py    Runs five tests and selects ten rare-term examples.
src/main.py              Provides the extract, build, search and test commands.
src/package_submission.py Earlier packaging helper for the separate-report layout.
src/requirements.txt     Lists the required Python packages and their versions.

How to run

The project was run using Python 3.9.6 on macOS. Extract the source ZIP and run
these commands from the folder containing src/:

  python3 -m venv .venv
  .venv/bin/python -m pip install -r src/requirements.txt
  mkdir -p data index output

If .venv already exists, reuse it. Place the compressed Wikipedia dump in data/.
There is no need to decompress the file manually.

For a small run with 100 articles:

  .venv/bin/python src/main.py extract --limit 100 --output data/smoke_articles.jsonl
  .venv/bin/python src/main.py build --articles data/smoke_articles.jsonl --db index/smoke.sqlite
  .venv/bin/python src/main.py test --articles data/smoke_articles.jsonl --db index/smoke.sqlite --output-dir output/smoke

For the full collection:

  .venv/bin/python src/main.py extract
  .venv/bin/python src/main.py build
  .venv/bin/python src/main.py test

The default extraction limit is 0, which means all valid articles. Use --limit N
to select a smaller number. Extraction and indexing do not overwrite existing
files. For another run, choose new paths with --output, --articles and --db.
If a run is interrupted, rerun it with a fresh output path instead of using its
partial files. Test reports are replaced when the test command is run again.

Search examples:

  .venv/bin/python src/main.py search "మూలాలు" --limit 3
  .venv/bin/python src/main.py search "షడ్వర్గం" --limit 0
  .venv/bin/python src/main.py search "షడ్వర్గం అంటారు" --phrase

Search displays DF, CF, document IDs, term frequencies and positions. It shows
up to 20 postings by default; --limit 0 displays all of them. A missing word gives
DF=0, CF=0 and a "No matches" message. Use --help to see each command's options.

Text extraction and tokenization

The XML is read as a stream using bz2 and ElementTree.iterparse, with one page
processed at a time. mwparserfromhell removes Wiki markup. References, media links,
category links and non-prose tags are removed. Templates are stripped rather than
expanded, so the cleaned text may differ from the page displayed in a browser.
Each JSONL line contains the page ID, title and cleaned article text.

Text is normalized using Unicode NFC. The regex tokenizer keeps letters, combining
marks and numerals together, including Telugu vowel signs. Non-Telugu words and
numbers are retained, and case is preserved. No stemming or stop-word removal is
applied. Punctuation is not counted as a token.

Positions start at 0 in the cleaned article body. The title is stored separately
and is not added to the body tokens. Indexing and queries use the same tokenizer.

Index storage

DF is the number of documents containing a term. CF is the total number of times
the term occurs across all documents. A posting contains the document ID, the term
frequency in that document (TF), and its complete position list. Positions are
sorted and do not repeat. DF equals the number of postings for the term, and CF
equals the sum of their TF values.

The database is stored at index/positional.sqlite. It has four tables:
  documents:  Page ID, title and token count.
  vocabulary: Term, DF and CF.
  postings:   Term, document ID, TF and positions as a JSON list.
  metadata:   Build totals, validation result and source collection checksum.

The postings primary key is (term, doc_id). This supports indexed term lookup and
prevents duplicate postings. Document IDs are also unique.

During construction, only one article's positions are collected in Python memory
at a time. They are inserted into SQLite, with a commit every 500 articles.
SQLite uses a 32 MiB cache target and disk storage for temporary data. Large
articles can still need more memory while being parsed and tokenized.

When search starts, the entire vocabulary is loaded into a Python dictionary in
RAM. The complete postings remain on disk and are retrieved only when needed.
The search connection uses an 8 MiB SQLite cache target. Phrase search reads the
requested terms' postings in document order and checks for adjacent positions,
keeping one current posting per phrase token in memory.

Testing and results

All five tests passed:
  1. Common Telugu term: మూలాలు
  2. Rare Telugu term: షడ్వర్గం
  3. Nonexistent term: అసలులేనిపరీక్షాపదం
  4. Repeated occurrences of మూలాలు in one document
  5. Exact phrase: షడ్వర్గం అంటారు

The tests retokenize the source articles and compare the selected terms' positions
with the stored postings. They also check DF, CF and phrase matches against the
source text. The common-term report shows three documents, but the check covers
all its documents. Each test includes the input, expected condition, actual result
and PASS or FAIL in test_results.txt.

Ten distinct rare Telugu terms are included with their complete postings. These
are selected from the collection, preferring terms found in an article's title
and at least twice in its body, with DF=1. If a small collection has fewer than
ten such terms, the remaining terms are selected by DF, CF and Unicode order.

One example from the output:
  Term: షడ్వర్గం
  DF: 1
  CF: 3
  Document ID: 10426
  TF: 3
  Positions: [2, 9, 262]

The builder also checked every posting for valid TF and sorted, unique positions,
compared DF and CF with database totals, and passed SQLite's integrity check.
There were no source-validation errors. The 100-article smoke run passed as well.
The source ZIP was extracted into a fresh folder and run again; its smoke collection
and postings matched the original smoke run.

Generated files and submission

  data/articles.jsonl          Cleaned article collection
  data/articles.stats.json     Extraction counts and skip reasons
  index/positional.sqlite      Full vocabulary and positional index
  index/positional.stats.json  Build statistics
  output/test_results/test_results.txt  Separate report of the five tests
  output/rare_terms/rare_terms.txt      Separate report of the ten rare terms
  output.txt                           Combined report for submission

The test command creates these two separate report folders. Use --output-dir to
choose a different parent folder.

The cleaned collection is 1,158,156,593 bytes and the index is 1,655,816,192 bytes.
The original compressed dump is unchanged. The dataset and index are available
as GitHub Release assets using the links below. They are excluded from Git history
and the submission ZIP, along with .venv, caches, logs and temporary files.
The extraction and indexing commands above can also regenerate them.

S20240010050-src.zip contains the source files and requirements.txt.
S20240010050-A1-PostIndex-IR-M2026.zip contains exactly:
  README.txt
  S20240010050-src.zip
  output.txt

For this submission, the two reports are combined in output.txt. The source code
is unchanged; its packaging helper produces the earlier separate-report layout.

GitHub repository and downloads

Repository:
https://github.com/chundurusankeerth/IR-Positional-Index-Telugu

Release:
https://github.com/chundurusankeerth/IR-Positional-Index-Telugu/releases/tag/assignment-data-v1

Original compressed dataset (276043990 bytes):
https://github.com/chundurusankeerth/IR-Positional-Index-Telugu/releases/download/assignment-data-v1/tewiki-latest-pages-articles-multistream.xml.bz2

Generated positional index (1655816192 bytes):
https://github.com/chundurusankeerth/IR-Positional-Index-Telugu/releases/download/assignment-data-v1/positional.sqlite

Index SHA-256:
1a9f3da5f4afcae063bfcd0c3eab89d437bb92f1e3ad5513bbab981761afa549

Place the dataset in data/ and positional.sqlite in index/. After installing the
dependencies, the downloaded index can be searched directly using the search
commands above, without rebuilding it. Regenerate data/articles.jsonl from the
dump if you want to run the source-text validation tests. Both uploaded files
were checked against their local sizes and SHA-256 checksums.
