from mjonai_intelligence.governance_loader import (
    load_all_governance_docs,
)

from mjonai_intelligence.relationship_mapper import (
    detect_relationships,
)

from mjonai_intelligence.section_parser import (
    parse_governance_sections,
)
from pathlib import Path


HIGH_IMPACT_PATTERNS = {
    "signal_scanner": [
        "strategy",
        "runtime",
        "execution",
        "risk",
    ],

    "repository": [
        "database",
        "runtime",
        "research",
        "risk",
    ],

    "orchestration": [
        "runtime",
        "scheduler",
        "startup",
    ],
}


ROOT_DIR = Path(__file__).resolve().parent.parent

EXTERNAL_LIBRARIES = {
    "os",
    "sys",
    "time",
    "logging",
    "datetime",
    "pathlib",
    "json",
    "numpy",
    "pandas",
    "yfinance",
    "talib",
    "vectorbt",
    "duckdb",
    "dotenv",
    "requests",
}

HEALTHY_CENTRALITY = {
    "core",
    "communication",
    "governance_loader",
}

DANGEROUS_CONCENTRATION = {
    "signal_scanner.py",
    "repository.py",
    "db/repository.py",
}

REFACTOR_GUIDANCE = {
    "signal_scanner.py": {
        "problem":
            "too many runtime responsibilities",
        "recommended_split": [
            "signal generation",
            "ranking",
            "execution triggering",
            "risk gating",
        ],
        "priority": "CRITICAL",
    },

    "repository.py": {
        "problem":
            "monolithic persistence layer",
        "recommended_split": [
            "trade persistence",
            "runtime state",
            "research persistence",
            "risk persistence",
        ],
        "priority": "HIGH",
    },

    "db/repository.py": {
        "problem":
            "high persistence coupling",
        "recommended_split": [
            "runtime repository",
            "research repository",
            "execution repository",
        ],
        "priority": "HIGH",
    },
}

ARCHITECTURE_RULES = [
    {
        "source": "research",
        "forbidden": [
            "execution",
            "orchestration",
        ],
        "reason":
            "research must remain isolated "
            "from runtime execution",
    },

    {
        "source": "strategy",
        "forbidden": [
            "research",
        ],
        "reason":
            "runtime strategy layer should "
            "not depend on experimental research",
    },

    {
        "source": "execution",
        "forbidden": [
            "research",
        ],
        "reason":
            "execution layer must remain "
            "runtime-safe",
    },
]

SUBSYSTEM_RISK_WEIGHTS = {
    "execution": 5,
    "risk": 5,
    "orchestration": 4,
    "strategy": 4,
    "db": 4,
    "core": 4,
    "communication": 3,
    "research": 2,
    "agents": 2,
    "data": 2,
}

def scan_python_dependencies():
    """
    Scan project imports to detect module coupling.
    """

    dependency_map = {}

    SEARCH_DIRS = [
        "agents",
        "communication",
        "core",
        "data",
        "db",
        "execution",
        "mjonai_intelligence",
        "orchestration",
        "research",
        "risk",
        "strategy",
        "Test",
    ]

    for folder in SEARCH_DIRS:

        target_dir = ROOT_DIR / folder

        if not target_dir.exists():
            continue

        for py_file in target_dir.rglob("*.py"):

            relative_path = str(
                py_file.relative_to(ROOT_DIR)
            )

            imports = []

            try:

                with open(
                    py_file,
                    "r",
                    encoding="utf-8",
                    errors="ignore"
                ) as f:

                    for line in f:

                        line = line.strip()

                        if line.startswith("import "):
                            imports.append(line)

                        elif line.startswith("from "):
                            imports.append(line)

            except Exception:
                continue

            dependency_map[relative_path] = imports

    return dependency_map

def build_reverse_dependencies(dependency_map):
    """
    Build reverse dependency relationships.
    """

    reverse_map = {}

    for file_path, imports in dependency_map.items():

        for imp in imports:

            imp = imp.replace("import ", "")
            imp = imp.replace("from ", "")

            imp_root = imp.split()[0]
            imp_root = imp_root.split(".")[0]

            # Ignore external ecosystem dependencies
            if imp_root in EXTERNAL_LIBRARIES:
                continue

            if imp_root not in reverse_map:
                reverse_map[imp_root] = []

            reverse_map[imp_root].append(file_path)

    return reverse_map

def detect_architecture_violations(
    dependency_map
):
    """
    Detect forbidden subsystem coupling.
    """

    violations = []

    for file_path, imports in dependency_map.items():

        source_subsystem = file_path.split("/")[0]

        for rule in ARCHITECTURE_RULES:

            if source_subsystem != rule["source"]:
                continue

            for imp in imports:

                for forbidden in rule[
                    "forbidden"
                ]:

                    if forbidden in imp:

                        violations.append({
                            "severity": "CRITICAL",
                            "component": file_path,
                            "impact": [forbidden],
                            "reason": rule["reason"],
                        })

    return violations

def simulate_component_impact(
    component_name
):
    """
    Simulate architecture impact for a component.
    """

    dependencies = scan_python_dependencies()

    reverse_dependencies = (
        build_reverse_dependencies(
            dependencies
        )
    )

    component_key = component_name

    if "/" in component_name:
        component_key = (
            component_name.split("/")[0]
        )

    impacted_files = list(set(
        reverse_dependencies.get(
            component_key,
            []
        )
    ))

    impacted_subsystems = sorted(list(set(
        file.split("/")[0]
        for file in impacted_files
        if "/" in file
    )))

    risk_score = 0

    for subsystem in impacted_subsystems:

        risk_score += SUBSYSTEM_RISK_WEIGHTS.get(
            subsystem,
            1
        )

    risk_level = "LOW"

    if risk_score >= 25:
        risk_level = "CRITICAL"

    elif risk_score >= 15:
        risk_level = "HIGH"

    elif risk_score >= 8:
        risk_level = "MEDIUM"

    validations = []

    if "execution" in impacted_subsystems:
        validations.append(
            "execution runtime validation"
        )

    if "strategy" in impacted_subsystems:
        validations.append(
            "strategy signal validation"
        )

    if "orchestration" in impacted_subsystems:
        validations.append(
            "runtime startup validation"
        )

    if "risk" in impacted_subsystems:
        validations.append(
            "risk control validation"
        )

    return {
        "component": component_name,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "impacted_files": impacted_files,
        "impacted_subsystems":
            impacted_subsystems,
        "recommended_validations":
            validations,
    }

def analyze_architecture_impact():
    """
    Analyze high-impact architecture risks.
    """

    docs = load_all_governance_docs()

    sections = parse_governance_sections()

    relationships = detect_relationships(sections)

    dependencies = scan_python_dependencies()

    reverse_dependencies = build_reverse_dependencies(
        dependencies
    )

    violations = detect_architecture_violations(
        dependencies
    )

    findings = []

    technical_debt = docs.get(
        "technical_debt",
        ""
    ).lower()

    # Detect signal_scanner risk
    if "signal_scanner.py responsibility overload" in technical_debt:

        findings.append({
            "severity": "HIGH",
            "component": "signal_scanner.py",
            "impact": HIGH_IMPACT_PATTERNS[
                "signal_scanner"
            ],
            "reason":
                "strategy orchestration concentration risk",
        })

    # Detect repository growth risk
    if "repository.py monolithic growth" in technical_debt:

        findings.append({
            "severity": "HIGH",
            "component": "repository.py",
            "impact": HIGH_IMPACT_PATTERNS[
                "repository"
            ],
            "reason":
                "centralized persistence coupling risk",
        })

    # Detect orchestration centrality
    runtime_relationships = [
        r for r in relationships
        if "runtime -> orchestration"
        in r["relationship"]
    ]

    if len(runtime_relationships) >= 3:

        findings.append({
            "severity": "MEDIUM",
            "component": "orchestration",
            "impact": HIGH_IMPACT_PATTERNS[
                "orchestration"
            ],
            "reason":
                "runtime lifecycle dependency concentration",
        })

    # Detect high coupling files
    for file_path, imports in dependencies.items():

        if len(imports) >= 15:

            findings.append({
                "severity": "MEDIUM",
                "component": file_path,
                "impact": ["high_coupling"],
                "reason":
                    f"{len(imports)} imports detected",
            })

    # Detect blast-radius hotspots
    for module, dependents in reverse_dependencies.items():

        unique_dependents = list(set(dependents))

        if len(unique_dependents) >= 5:

            findings.append({
                "severity": "HIGH",
                "component": module,
                "impact": unique_dependents[:10],
                "reason":
                    f"high blast radius "
                    f"({len(unique_dependents)} dependent files)",
            })
    
    findings.extend(violations)

    return findings


def print_findings(findings):

    print(
        "\n=== MJONAI IMPACT ANALYSIS ===\n"
    )

    if not findings:

        print("No significant findings.")
        return

    for finding in findings:

        classification = "NEUTRAL"

        component = finding["component"]

        if component in HEALTHY_CENTRALITY:
            classification = "HEALTHY CENTRALITY"

        elif component in DANGEROUS_CONCENTRATION:
            classification = "DANGEROUS CONCENTRATION"

        print("--------------------")

        print(
            f"SEVERITY: "
            f"{finding['severity']}"
        )

        print(
            f"COMPONENT: "
            f"{finding['component']}"
        )

        print(
            f"CLASSIFICATION: "
            f"{classification}"
        )

        print(
            f"IMPACT ZONES: "
            f"{', '.join(finding['impact'])}"
        )

        print(
            f"REASON: "
            f"{finding['reason']}"
        )

        if component in REFACTOR_GUIDANCE:

            guidance = REFACTOR_GUIDANCE[
                component
            ]

            print(
                f"REFACTOR PRIORITY: "
                f"{guidance['priority']}"
            )

            print(
                f"ARCHITECTURE ISSUE: "
                f"{guidance['problem']}"
            )

            print(
                "RECOMMENDED SPLITS:"
            )

            for split in guidance[
                "recommended_split"
            ]:

                print(f"  - {split}")

        print()

def print_impact_simulation(result):

    print(
        "\n=== IMPACT SIMULATION ===\n"
    )

    print(
        f"COMPONENT: "
        f"{result['component']}"
    )

    print(
        f"RISK LEVEL: "
        f"{result['risk_level']}"
    )

    print(
        f"RISK SCORE: "
        f"{result['risk_score']}"
    )

    print("\nAffected Subsystems:")

    for subsystem in result[
        "impacted_subsystems"
    ]:

        print(f"- {subsystem}")

    print("\nAffected Files:")

    for file in result[
        "impacted_files"
    ][:15]:

        print(f"- {file}")

    print(
        "\nRecommended Validations:"
    )

    if not result[
        "recommended_validations"
    ]:

        print("- none")

    else:

        for validation in result[
            "recommended_validations"
        ]:

            print(f"- {validation}")

    print()

if __name__ == "__main__":

    findings = analyze_architecture_impact()

    print_findings(findings)