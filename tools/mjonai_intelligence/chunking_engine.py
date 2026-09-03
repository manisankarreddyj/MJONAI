from tools.mjonai_intelligence.governance_loader import (
    load_all_governance_docs,
)


def chunk_text(text, chunk_size=500):
    """
    Split text into fixed-size chunks.
    """

    chunks = []

    for i in range(0, len(text), chunk_size):

        chunk = text[i:i + chunk_size]

        chunks.append(chunk)

    return chunks


def build_memory_chunks():
    """
    Build chunked governance memory.
    """

    docs = load_all_governance_docs()

    memory_chunks = []

    for source, content in docs.items():

        if not content:
            continue

        chunks = chunk_text(content)

        for idx, chunk in enumerate(chunks):

            memory_chunks.append({
                "source": source,
                "chunk_id": idx,
                "content": chunk,
            })

    return memory_chunks


def search_chunks(query, chunks):
    """
    Primitive chunk retrieval.
    """

    query_words = set(query.lower().split())

    results = []

    for chunk in chunks:

        score = 0

        content = chunk["content"].lower()

        for word in query_words:

            if word in content:
                score += 1

        if score > 0:

            results.append({
                "source": chunk["source"],
                "chunk_id": chunk["chunk_id"],
                "score": score,
                "preview": chunk["content"][:300],
            })

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return results


def run_chunk_demo():

    chunks = build_memory_chunks()

    print(f"\nLoaded {len(chunks)} memory chunks.")

    while True:

        query = input("\nChunk Query > ").strip()

        if query.lower() in {"exit", "quit"}:
            break

        results = search_chunks(query, chunks)

        if not results:
            print("\nNo matching chunks.")
            continue

        for result in results[:5]:

            print("\n--------------------")
            print(f"SOURCE: {result['source']}")
            print(f"CHUNK: {result['chunk_id']}")
            print(f"SCORE: {result['score']}")
            print(result["preview"])


if __name__ == "__main__":

    run_chunk_demo()