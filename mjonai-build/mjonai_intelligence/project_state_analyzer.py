from mjonai_intelligence.governance_loader import (
    load_all_governance_docs,
)


def analyze_project_state():
    """
    Basic project-state cognition layer.
    """

    docs = load_all_governance_docs()

    findings = []

    technical_debt = docs.get("technical_debt", "") or ""
    canonical_state = docs.get("canonical_state", "") or ""
    subsystem_index = docs.get("subsystem_index", "") or ""

    # Detect major architecture risks
    if "signal_scanner.py responsibility overload" in technical_debt:
        findings.append(
            "HIGH RISK: signal_scanner.py is overloaded."
        )

    if "repository.py monolithic growth" in technical_debt:
        findings.append(
            "HIGH RISK: repository.py becoming monolithic."
        )

    # Detect research entropy
    if "duplicate experiment" in canonical_state.lower():
        findings.append(
            "MEDIUM RISK: research duplication entropy detected."
        )

    # Detect intelligence subsystem
    if "mjonai_intelligence/" in canonical_state:
        findings.append(
            "INFO: internal intelligence subsystem established."
        )

    # Detect orchestration maturity
    if "orchestration/" in subsystem_index:
        findings.append(
            "INFO: orchestration subsystem established."
        )

    return findings


def print_analysis(findings):

    print("\n=== MJONAI PROJECT STATE ANALYSIS ===\n")

    if not findings:
        print("No findings detected.")
        return

    for finding in findings:
        print(f"- {finding}")


if __name__ == "__main__":

    findings = analyze_project_state()

    print_analysis(findings)