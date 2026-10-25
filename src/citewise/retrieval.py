"""Inspectable BM25 retrieval, optional dense search, and reciprocal-rank fusion."""

import math
import re
from collections import Counter
from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

STOP = set("a an the is are of to in on for can how what do i my does and with".split())


def tokens(text):
    return [t for t in re.findall(r"\w+", text.casefold()) if t not in STOP]


@dataclass
class Hit:
    chunk: dict
    score: float


def chunk_text(text, size=900, overlap=120):
    """Retain line ranges so citations can be checked against original documents."""
    if size <= overlap or overlap < 0:
        raise ValueError("Require size > overlap >= 0")
    for start in range(0, len(text), size - overlap):
        end = min(start + size, len(text))
        if text[start:end].strip():
            yield {
                "text": text[start:end],
                "line_start": text.count("\n", 0, start) + 1,
                "line_end": text.count("\n", 0, end) + 1,
            }
        if end == len(text):
            break


def search(question, chunks, limit=4, encoder=None):
    """Fuse ranked candidates, then rerank by character-level lexical similarity.

    The default is entirely offline. A SentenceTransformer can supply normalized
    document/query embeddings; it is an explicit opt-in, never a silent download.
    """
    if not chunks or not tokens(question):
        return []
    corpus = [tokens(c["text"]) for c in chunks]
    query = tokens(question)
    counts = [Counter(words) for words in corpus]
    average_length = max(1, sum(map(len, corpus)) / len(corpus))
    bm25 = np.zeros(len(chunks))
    for word in set(query):
        frequency = sum(word in count for count in counts)
        inverse_frequency = math.log(1 + (len(chunks) - frequency + 0.5) / (frequency + 0.5))
        for i, count in enumerate(counts):
            tf = count[word]
            norm = tf + 1.5 * (0.25 + 0.75 * len(corpus[i]) / average_length)
            bm25[i] += inverse_frequency * tf * 2.5 / norm

    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5))
    vectors = vectorizer.fit_transform([c["text"] for c in chunks] + [question])
    lexical = cosine_similarity(vectors[-1], vectors[:-1]).ravel()
    dense = np.zeros(len(chunks))
    if encoder is not None:
        documents = encoder.encode_document([c["text"] for c in chunks], normalize_embeddings=True)
        query_vector = encoder.encode_query([question], normalize_embeddings=True)
        dense = np.asarray(documents) @ np.asarray(query_vector)[0]

    candidates = {i for i in range(len(chunks)) if bm25[i] > 0 or dense[i] >= 0.45}
    fused = np.zeros(len(chunks))
    signals = [bm25, lexical] + ([dense] if encoder is not None else [])
    for signal in signals:
        ranking = sorted(candidates, key=lambda i: (-signal[i], chunks[i]["id"]))
        for rank, index in enumerate(ranking, 1):
            fused[index] += 1 / (60 + rank)
    # Lexical reranking is cheap and transparent; it is not a learned cross-encoder.
    ranked = sorted(candidates, key=lambda i: -(fused[i] * (0.8 + 0.2 * lexical[i])))
    return [Hit(chunks[i], round(float(fused[i]), 6)) for i in ranked[:limit]]
