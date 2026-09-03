from tools.mjonai_intelligence.knowledge_engine import (
    build_knowledge_pipeline,
)


class MemoryStore:
    """
    Lightweight semantic project memory layer.
    """

    def __init__(self):

        self.documents = []

    def load_governance_memory(self):

        knowledge = (
            build_knowledge_pipeline()
        )

        docs = knowledge["documents"]

        for doc_name, content in docs.items():

            if not content:
                continue

            self.documents.append({
                "source": doc_name,
                "content": content,
            })

    def semantic_search(self, query):
        """
        Very primitive semantic retrieval.
        """

        query_words = set(query.lower().split())

        results = []

        for doc in self.documents:

            content = doc["content"].lower()

            score = 0

            for word in query_words:

                if word in content:
                    score += 1

            if score > 0:

                results.append({
                    "source": doc["source"],
                    "score": score,
                    "preview": doc["content"][:500],
                })

        results.sort(
            key=lambda x: x["score"],
            reverse=True
        )

        return results


def run_memory_demo():

    store = MemoryStore()

    store.load_governance_memory()

    print("\n=== MJONAI MEMORY STORE ===")

    while True:

        query = input("\nMemory Query > ").strip()

        if query.lower() in {"exit", "quit"}:
            break

        results = store.semantic_search(query)

        if not results:
            print("\nNo relevant memory found.")
            continue

        for result in results[:3]:

            print(f"\n--- SOURCE: {result['source']} ---")
            print(f"SCORE: {result['score']}")
            print(result["preview"])
            print("\n...")

def search_memory(query):
    """
    Search governance memory chunks.
    """

    query = query.lower()

    matches = []

    store = MemoryStore()
    store.load_governance_memory()

    docs = {
        doc["source"]: doc["content"]
        for doc in store.documents
    }

    for source, content in docs.items():

        content_lower = content.lower()

        score = 0

        for word in query.split():

            if word in content_lower:
                score += 1

        if score > 0:

            matches.append({
                "source": source,
                "score": score,
                "content": content,
            })

    matches.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return matches

def query_memory(query):
    """
    Query governance memory store.
    """

    results = search_memory(query)

    if not results:

        print("\nNo memory results found.\n")
        return

    print(f"\n=== MEMORY RESULTS: {query} ===\n")

    for result in results:

        print("--------------------")

        print(
            f"SOURCE: "
            f"{result['source']}"
        )

        print(
            f"SCORE: "
            f"{result['score']}"
        )

        print(result["content"][:500])

        print("\n...")
        print()

if __name__ == "__main__":

    run_memory_demo()