from tools.mjonai_intelligence.subsystem_mapper import get_subsystem_files


QUERY_MAP = {
    "runtime": "runtime",
    "scheduler": "runtime",
    "startup": "runtime",
    "risk": "risk",
    "execution": "execution",
    "strategy": "strategy",
    "research": "research",
    "database": "database",
    "db": "database",
    "telegram": "communication",
    "communication": "communication",
    "data": "data",
    "governance": "governance",
    "intelligence": "intelligence",
}


def resolve_query(user_query):
    """
    Map user query -> subsystem.
    """

    query = user_query.lower()

    query_words = set(query.split())

    matches = []

    for keyword, subsystem in QUERY_MAP.items():

        keyword_words = set(keyword.split())

        if keyword_words & query_words:
            matches.append(subsystem)

    # Remove duplicates
    matches = list(dict.fromkeys(matches))

    return matches

def run_query_engine():

    print("\n=== MJONAI PROJECT QUERY ENGINE ===\n")

    while True:

        query = input("\nAsk MJONAI > ").strip()

        if query.lower() in {"exit", "quit"}:
            print("\nExiting query engine.\n")
            break

        subsystems = resolve_query(query)

        if not subsystems:
            print("\nNo subsystem match found.")
            continue

        for subsystem in subsystems:

            files = get_subsystem_files(subsystem)

            print(f"\n=== {subsystem.upper()} ===\n")

            for file in files:
                print(f"- {file}")


if __name__ == "__main__":
    run_query_engine()