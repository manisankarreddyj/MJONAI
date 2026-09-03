from tools.mjonai_intelligence.impact_analyzer import (
    simulate_component_impact,
)


REFACTOR_PATTERNS = {

    "signal_scanner.py": {

        "problem":
            "Too many runtime responsibilities.",

        "splits": [
            "signal generation",
            "signal ranking",
            "execution triggering",
            "risk gating",
            "overlap protection",
        ],

        "migration_order": [
            "extract ranking layer",
            "extract execution routing",
            "extract risk validation",
            "preserve runtime behavior",
        ],

        "warnings": [
            "runtime sequencing risk",
            "strategy execution drift risk",
            "duplicate signal risk",
        ],
    },

    "repository.py": {

        "problem":
            "Monolithic persistence concentration.",

        "splits": [
            "runtime repository",
            "research repository",
            "execution repository",
            "risk repository",
        ],

        "migration_order": [
            "separate read/write boundaries",
            "extract research persistence",
            "extract runtime persistence",
            "preserve schema compatibility",
        ],

        "warnings": [
            "schema migration risk",
            "runtime state corruption risk",
            "query compatibility risk",
        ],
    },
}


def generate_refactor_proposal(
    component
):
    """
    Generate governed refactor proposal.
    """

    component_name = component.split("/")[-1]

    impact = simulate_component_impact(
        component
    )

    proposal = REFACTOR_PATTERNS.get(
        component_name
    )

    if not proposal:

        return {
            "component": component,
            "supported": False,
        }

    return {
        "component": component,
        "supported": True,
        "risk_level":
            impact["risk_level"],
        "risk_score":
            impact["risk_score"],
        "problem":
            proposal["problem"],
        "recommended_splits":
            proposal["splits"],
        "migration_order":
            proposal["migration_order"],
        "warnings":
            proposal["warnings"],
        "validations":
            impact[
                "recommended_validations"
            ],
    }


def print_refactor_proposal(
    proposal
):

    print(
        "\n=== REFACTOR PROPOSAL ===\n"
    )

    print(
        f"COMPONENT: "
        f"{proposal['component']}"
    )

    if not proposal["supported"]:

        print(
            "\nNo proposal template available.\n"
        )

        return

    print(
        f"RISK LEVEL: "
        f"{proposal['risk_level']}"
    )

    print(
        f"RISK SCORE: "
        f"{proposal['risk_score']}"
    )

    print(
        f"\nARCHITECTURE PROBLEM:\n"
    )

    print(
        f"- {proposal['problem']}"
    )

    print(
        "\nRECOMMENDED SPLITS:\n"
    )

    for split in proposal[
        "recommended_splits"
    ]:

        print(f"- {split}")

    print(
        "\nSAFE MIGRATION ORDER:\n"
    )

    for step in proposal[
        "migration_order"
    ]:

        print(f"- {step}")

    print(
        "\nOPERATIONAL WARNINGS:\n"
    )

    for warning in proposal[
        "warnings"
    ]:

        print(f"- {warning}")

    print(
        "\nREQUIRED VALIDATIONS:\n"
    )

    for validation in proposal[
        "validations"
    ]:

        print(f"- {validation}")

    print()