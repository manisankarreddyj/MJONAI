from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

IGNORE_DIRS = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "logs",
}

IGNORE_SUFFIXES = {
    ".pyc",
    ".duckdb",
    ".txt",
}

SUBSYSTEM_MAP = {
    "runtime": [
        "main.py",
        "orchestration/",
        "core/runtime_config.py",
    ],

    "strategy": [
        "strategy/",
        "agents/",
    ],

    "risk": [
        "risk/",
    ],

    "execution": [
        "execution/",
    ],

    "research": [
        "research/",
        "Test/",
    ],

    "data": [
        "data/",
    ],

    "database": [
        "db/",
    ],

    "communication": [
        "communication/",
    ],

    "governance": [
        "docs/current_state/",
    ],

    "intelligence": [
        "mjonai_intelligence/",
    ],
}


def get_subsystem_files(subsystem_name):
    """
    Retrieve files belonging to subsystem.
    """

    subsystem_name = subsystem_name.lower()

    if subsystem_name not in SUBSYSTEM_MAP:
        return []

    matched_files = []

    for path in SUBSYSTEM_MAP[subsystem_name]:

        target = ROOT_DIR / path

        if target.is_file():
            matched_files.append(str(path))

        elif target.is_dir():

            for file in target.rglob("*"):

                # Ignore dirs
                if any(part in IGNORE_DIRS for part in file.parts):
                    continue

                # Ignore suffixes
                if file.suffix in IGNORE_SUFFIXES:
                    continue

                if file.is_file():

                    matched_files.append(
                        str(file.relative_to(ROOT_DIR))
                    )

    return sorted(matched_files)


if __name__ == "__main__":

    subsystem = input("Enter subsystem: ").strip()

    files = get_subsystem_files(subsystem)

    print(f"\n=== {subsystem.upper()} FILES ===\n")

    for file in files:
        print(file)