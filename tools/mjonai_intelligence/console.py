from tools.mjonai_intelligence.impact_analyzer import (
    analyze_architecture_impact,
    print_findings,
    simulate_component_impact,
    print_impact_simulation,
)

# ADR-0008: repo-root bootstrap — allows `python <this file>` from the repo root.
import sys as _boot_sys
from pathlib import Path as _boot_Path
_BOOT_ROOT = _boot_Path(__file__).resolve().parents[2]
if str(_BOOT_ROOT) not in _boot_sys.path:
    _boot_sys.path.insert(0, str(_BOOT_ROOT))

from tools.mjonai_intelligence.project_state_analyzer import (
    analyze_project_state,
)

from tools.mjonai_intelligence.memory_store import (
    query_memory,
)

from tools.mjonai_intelligence.subsystem_mapper import (
    get_subsystem_files,
)

from tools.mjonai_intelligence.refactor_advisor import (
    generate_refactor_proposal,
    print_refactor_proposal,
)

def print_help():

    print("\n=== MJONAI COMMANDS ===\n")

    print("help")
    print("exit")

    print("\nArchitecture:")
    print("analyze architecture")
    print("analyze state")

    print("\nMemory:")
    print("memory <query>")

    print("\nSubsystems:")
    print("subsystem <name>")

    print("impact <component>")

    print("propose refactor <component>")

    print()


def handle_command(command):

    command = command.strip()

    if command == "help":

        print_help()

    elif command == "analyze architecture":

        findings = analyze_architecture_impact()

        print_findings(findings)

    elif command == "analyze state":

        analyze_project_state()

    elif command.startswith("memory "):

        query = command.replace(
            "memory ",
            ""
        ).strip()

        query_memory(query)

    elif command.startswith("subsystem "):

        subsystem = command.replace(
            "subsystem ",
            ""
        ).strip()

        files = get_subsystem_files(
            subsystem
        )

        print(
            f"\n=== {subsystem.upper()} ===\n"
        )

        if not files:

            print("No subsystem files found.")
            return

        for file in files:
            print(f"- {file}")

        print()

    elif command.startswith("impact "):

        component = command.replace(
            "impact ",
            ""
        ).strip()

        result = simulate_component_impact(
            component
        )

        print_impact_simulation(result)

    elif command.startswith(
        "propose refactor "
    ):

        component = command.replace(
            "propose refactor ",
            ""
        ).strip()

        proposal = (
            generate_refactor_proposal(
                component
            )
        )

        print_refactor_proposal(
            proposal
        )

    else:

        print(
            "\nUnknown command."
        )

        print(
            "Type 'help' for commands.\n"
        )

    
def run_console():

    print(
        "\n=== MJONAI ENGINEERING CONSOLE ==="
    )

    print(
        "\nType 'help' for commands.\n"
    )

    while True:

        command = input(
            "\nMJONAI > "
        ).strip()

        if command.lower() in {
            "exit",
            "quit",
        }:

            print(
                "\nExiting MJONAI console.\n"
            )

            break

        handle_command(command)


if __name__ == "__main__":

    run_console()