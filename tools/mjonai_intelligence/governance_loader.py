from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent

GOVERNANCE_DOCS = {
    "canonical_state":
        "docs/current_state/CANONICAL_SYSTEM_STATE.md",

    "active_work":
        "docs/current_state/ACTIVE_WORK_STATE.md",

    "subsystem_index":
        "docs/current_state/SUBSYSTEM_INDEX.md",

    "technical_debt":
        "docs/current_state/TECHNICAL_DEBT_REGISTER.md",

    "query_examples":
        "docs/current_state/PROJECT_QUERY_EXAMPLES.md",

    "runtime_architecture":
        "docs/current_state/RUNTIME_ARCHITECTURE.md",

    "operations_playbook":
        "docs/current_state/OPERATIONS_PLAYBOOK.md",
}


def load_governance_doc(doc_key):
    """
    Load governance document contents.
    """

    if doc_key not in GOVERNANCE_DOCS:
        return None

    file_path = ROOT_DIR / GOVERNANCE_DOCS[doc_key]

    if not file_path.exists():
        return None

    return file_path.read_text(
        encoding="utf-8",
        errors="ignore"
    )


def load_all_governance_docs():
    """
    Load all governance documents.
    """

    loaded_docs = {}

    for key in GOVERNANCE_DOCS:

        content = load_governance_doc(key)

        loaded_docs[key] = content

    return loaded_docs


if __name__ == "__main__":

    docs = load_all_governance_docs()

    print("\n=== MJONAI GOVERNANCE MEMORY ===\n")

    for key, content in docs.items():

        print(f"\n--- {key.upper()} ---")

        if not content:
            print("FAILED TO LOAD")
            continue

        preview = content[:500]

        print(preview)
        print("\n...")