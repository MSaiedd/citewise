# Validation status

Validated locally on 2026-10-25 with Python 3.12.3. Exact commands and results are recorded
below. Portfolio fixtures are synthetic; passing checks do not establish production readiness.

## Automated checks

- `ruff check .` — passed.
- `ruff format --check .` — passed.
- `pytest --cov=src --cov-report=term-missing` — see the recorded test log in `reports/tests.txt`.
- `python scripts/browser_smoke.py` — passed: real Chromium desktop flow, 390 px mobile layout,
  no uncaught browser errors. Screenshots are in `docs/screenshots/`.

GitHub Actions repeats lint, tests on Python 3.11/3.12, and browser validation after publishing.
Local evidence is separate from hosted CI status.

## Boundaries

Static bearer tokens are development identities. No public hosting or production rollout was performed.
Optional external providers and CUDA-dependent paths require their own runtime validation.

## Packaging

`python -m build --wheel --outdir dist` — passed. The wheel includes HTML/CSS/JavaScript assets.

## Retrieval fixture

`python scripts/evaluate.py` — passed. Five synthetic documents, ten supported questions,
and three unsupported questions. Recall@1/4 and MRR@4: 1.0; unsupported-query abstention: 1.0.
These small hand-authored examples do not establish real-world retrieval quality. Full outcomes: `reports/retrieval.json`.

Optional Sentence Transformers and a live Ollama server were not exercised. Provider behavior
was validated with fault injection and malformed citation fixtures.

## Container

`docker build -t citewise:portfolio .` — passed.
`python scripts/container_smoke.py` — passed: non-root server, document ingestion/query,
and named-volume document persistence after a fresh container starts. See `reports/container.json`.
