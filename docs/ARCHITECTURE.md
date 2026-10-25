# Architecture decisions

- SQLite transactions keep document replacement atomic. Foreign keys remove old chunks on deletion.
- Every read/write binds tenant identity from server configuration. Request payloads cannot select it.
- BM25 plus character TF-IDF is an inspectable offline baseline. Optional dense retrieval handles paraphrases.
- Reciprocal-rank fusion avoids directly comparing differently scaled retrieval scores.
- Character similarity is a lexical reranker, not a learned cross-encoder.
- Generated answers are checked for source-ID validity; semantic support still requires evaluation.
- The current implementation loads a workspace corpus per query. A production-sized corpus needs a persistent vector/lexical index, quotas, and ingestion workers.
- Markdown/plain text is treated as text. PDF parsing, OCR, and document-level ACLs are future extensions.

Evaluation expansion: author independently labeled positive/negative questions across many documents;
report recall@k, MRR, citation precision, human answer correctness, p50/p95 latency, and model cost.
Keep a separate test set while selecting chunk sizes and thresholds on validation data.
