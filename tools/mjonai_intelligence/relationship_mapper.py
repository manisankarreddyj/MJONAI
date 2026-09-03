from tools.mjonai_intelligence.section_parser import (
    parse_governance_sections,
)


RELATIONSHIP_RULES = [
    ("technical debt", "runtime architecture"),
    ("runtime", "orchestration"),
    ("research", "technical debt"),
    ("governance", "runtime"),
    ("strategy", "risk"),
    ("execution", "risk"),
]


def detect_relationships(sections):
    """
    Detect primitive relationships between sections.
    """

    relationships = []

    for section in sections:

        title = section["title"].lower()
        content = section["content"].lower()

        combined = f"{title} {content}"

        for left, right in RELATIONSHIP_RULES:

            if left in combined and right in combined:

                relationships.append({
                    "source": section["source"],
                    "section_title": section["title"],
                    "relationship": f"{left} -> {right}",
                })

    return relationships


def run_relationship_demo():

    sections = parse_governance_sections()

    relationships = detect_relationships(sections)

    print(
        f"\nDetected {len(relationships)} relationships."
    )

    for rel in relationships:

        print("\n--------------------")
        print(f"SOURCE: {rel['source']}")
        print(f"SECTION: {rel['section_title']}")
        print(f"RELATIONSHIP: {rel['relationship']}")


if __name__ == "__main__":

    run_relationship_demo()