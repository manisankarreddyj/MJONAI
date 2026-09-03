from mjonai_intelligence.governance_loader import (
    load_all_governance_docs,
)

from mjonai_intelligence.section_parser import (
    parse_governance_sections,
)

from mjonai_intelligence.relationship_mapper import (
    detect_relationships,
)

def build_knowledge_pipeline():
    """
    Build canonical MJONAI knowledge pipeline.
    """

    docs = load_all_governance_docs()

    sections = parse_governance_sections()

    relationships = detect_relationships(
        sections
    )

    knowledge = {
        "documents": docs,
        "sections": sections,
        "relationships": relationships,
    }

    return knowledge


def summarize_knowledge(knowledge):

    print(
        "\n=== MJONAI KNOWLEDGE ENGINE ===\n"
    )

    print(
        f"Documents Loaded: "
        f"{len(knowledge['documents'])}"
    )

    print(
        f"Sections Parsed: "
        f"{len(knowledge['sections'])}"
    )

    print(
        f"Relationships Detected: "
        f"{len(knowledge['relationships'])}"
    )

    print()

    print(
        "Knowledge Pipeline Status:"
    )

    print("- governance loaded")
    print("- sections parsed")
    print("- relationships mapped")

    print()


if __name__ == "__main__":

    knowledge = (
        build_knowledge_pipeline()
    )

    summarize_knowledge(
        knowledge
    )