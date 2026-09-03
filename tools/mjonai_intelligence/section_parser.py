from tools.mjonai_intelligence.governance_loader import (
    load_all_governance_docs,
)


def split_by_sections(content):
    """
    Split markdown content by headings.
    """

    lines = content.splitlines()

    sections = []

    current_title = "ROOT"
    current_content = []

    for line in lines:

        if line.startswith("#"):

            # Save previous section
            if current_content:

                sections.append({
                    "title": current_title,
                    "content": "\n".join(current_content)
                })

            current_title = line.strip()
            current_content = []

        else:
            current_content.append(line)

    # Save final section
    if current_content:

        sections.append({
            "title": current_title,
            "content": "\n".join(current_content)
        })

    return sections


def parse_governance_sections():

    docs = load_all_governance_docs()

    parsed_sections = []

    for source, content in docs.items():

        if not content:
            continue

        sections = split_by_sections(content)

        for idx, section in enumerate(sections):

            parsed_sections.append({
                "source": source,
                "section_id": idx,
                "title": section["title"],
                "content": section["content"],
            })

    return parsed_sections


def run_section_demo():

    parsed = parse_governance_sections()

    print(
        f"\nLoaded {len(parsed)} structured sections."
    )

    for section in parsed[:15]:

        print("\n--------------------")
        print(f"SOURCE: {section['source']}")
        print(f"SECTION: {section['section_id']}")
        print(f"TITLE: {section['title']}")
        print(section["content"][:300])


if __name__ == "__main__":

    run_section_demo()