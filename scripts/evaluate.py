"""Measure ranked retrieval against labeled, original synthetic questions."""

import json
from pathlib import Path

from citewise.retrieval import chunk_text, search


def main():
    root = Path(__file__).resolve().parents[1]
    fixture = json.loads((root / "data/retrieval-fixture.json").read_text())
    chunks = []
    for document in fixture["documents"]:
        for index, part in enumerate(chunk_text(document["text"])):
            chunks.append(
                {**part, "id": f"{document['title']}-{index}", "title": document["title"]}
            )
    outcomes = []
    for row in fixture["questions"]:
        titles = [hit.chunk["title"] for hit in search(row["question"], chunks)]
        rank = titles.index(row["title"]) + 1 if row["title"] in titles else None
        outcomes.append({**row, "retrieved": titles, "rank": rank})
    report = {
        "dataset": "original synthetic five-document fixture",
        "positive_queries": len(outcomes),
        "negative_queries": len(fixture["unsupported_questions"]),
        "recall_at_1": sum(row["rank"] == 1 for row in outcomes) / len(outcomes),
        "recall_at_4": sum(row["rank"] is not None for row in outcomes) / len(outcomes),
        "mrr_at_4": sum(1 / row["rank"] if row["rank"] else 0 for row in outcomes) / len(outcomes),
        "unsupported_abstention_rate": sum(
            not search(q, chunks) for q in fixture["unsupported_questions"]
        )
        / len(fixture["unsupported_questions"]),
        "outcomes": outcomes,
        "limitation": "Small synthetic fixture, not evidence of real-world retrieval or answer quality.",
    }
    output = root / "reports/retrieval.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
