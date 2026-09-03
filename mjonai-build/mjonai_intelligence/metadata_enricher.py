from mjonai_intelligence.chunking_engine import (
    build_memory_chunks,
)


SUBSYSTEM_HINTS = {
    "signal_scanner": "strategy",
    "strategy": "strategy",
    "risk": "risk",
    "runtime": "runtime",
    "orchestration": "runtime",
    "repository": "database",
    "research": "research",
    "telegram": "communication",
}


SEVERITY_HINTS = {
    "critical": "CRITICAL",
    "high": "HIGH",
    "medium": "MEDIUM",
    "low": "LOW",
}


TYPE_HINTS = {
    "risk": "architecture_risk",
    "debt": "technical_debt",
    "orchestration": "runtime_architecture",
    "research": "research_state",
    "governance": "governance",
}


def enrich_chunk(chunk):
    """
    Attach metadata to chunk.
    """

    content = chunk["content"].lower()

    metadata = {
        "subsystem": None,
        "severity": None,
        "type": None,
    }

    # Detect subsystem
    for keyword, subsystem in SUBSYSTEM_HINTS.items():

        if keyword in content:
            metadata["subsystem"] = subsystem
            break

    # Detect severity
    for keyword, severity in SEVERITY_HINTS.items():

        if keyword in content:
            metadata["severity"] = severity
            break

    # Detect type
    for keyword, chunk_type in TYPE_HINTS.items():

        if keyword in content:
            metadata["type"] = chunk_type
            break

    enriched = {
        **chunk,
        **metadata,
    }

    return enriched


def build_enriched_memory():

    chunks = build_memory_chunks()

    enriched_chunks = []

    for chunk in chunks:

        enriched_chunks.append(
            enrich_chunk(chunk)
        )

    return enriched_chunks


def run_metadata_demo():

    enriched_chunks = build_enriched_memory()

    print(
        f"\nLoaded {len(enriched_chunks)} enriched chunks."
    )

    for chunk in enriched_chunks[:10]:

        print("\n--------------------")
        print(f"SOURCE: {chunk['source']}")
        print(f"SUBSYSTEM: {chunk['subsystem']}")
        print(f"SEVERITY: {chunk['severity']}")
        print(f"TYPE: {chunk['type']}")
        print(chunk["content"][:250])


if __name__ == "__main__":

    run_metadata_demo()