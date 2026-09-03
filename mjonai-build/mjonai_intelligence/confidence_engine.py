from mjonai_intelligence.metadata_enricher import (
    build_enriched_memory,
)


def calculate_confidence(chunk):
    """
    Evidence-aware confidence scoring.
    """

    confidence = 0.1

    content = chunk["content"].lower()

    evidence_hits = 0

    # Strong subsystem evidence
    if chunk.get("subsystem"):

        subsystem = chunk["subsystem"]

        if subsystem in content:
            confidence += 0.25
            evidence_hits += 1

    # Strong severity evidence
    if chunk.get("severity"):

        severity = chunk["severity"].lower()

        if severity in content:
            confidence += 0.25
            evidence_hits += 1

    # Strong type evidence
    if chunk.get("type"):

        chunk_type = chunk["type"].replace("_", " ")

        type_words = chunk_type.split()

        if any(word in content for word in type_words):
            confidence += 0.25
            evidence_hits += 1

    # Canonical governance weighting
    if chunk["source"] in {
        "canonical_state",
        "technical_debt",
        "runtime_architecture",
    }:
        confidence += 0.1

    # Ambiguity penalty
    if evidence_hits <= 1:
        confidence -= 0.15

    confidence = max(0.0, min(confidence, 1.0))

    return round(confidence, 2)


def build_confident_memory():

    chunks = build_enriched_memory()

    confident_chunks = []

    for chunk in chunks:

        confidence = calculate_confidence(chunk)

        chunk["confidence"] = confidence

        confident_chunks.append(chunk)

    return confident_chunks


def print_confident_chunks():

    chunks = build_confident_memory()

    print(
        f"\nLoaded {len(chunks)} confidence-scored chunks."
    )

    sorted_chunks = sorted(
        chunks,
        key=lambda x: x["confidence"],
        reverse=True
    )

    for chunk in sorted_chunks[:10]:

        print("\n--------------------")
        print(f"SOURCE: {chunk['source']}")
        print(f"CONFIDENCE: {chunk['confidence']}")
        print(f"SUBSYSTEM: {chunk['subsystem']}")
        print(f"SEVERITY: {chunk['severity']}")
        print(f"TYPE: {chunk['type']}")
        print(chunk["content"][:250])


if __name__ == "__main__":

    print_confident_chunks()