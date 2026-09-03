import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent

IGNORE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "logs",
}

IGNORE_SUFFIXES = {
    ".pyc",
}


def build_project_tree():
    """
    Build simplified MJONAI project structure.

    Returns:
        dict: folder -> files
    """

    project_map = {}

    for root, dirs, files in os.walk(ROOT_DIR):

        # Ignore unwanted dirs
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        rel_root = os.path.relpath(root, ROOT_DIR)

        clean_files = []

        for file in files:

            if any(file.endswith(x) for x in IGNORE_SUFFIXES):
                continue

            clean_files.append(file)

        if clean_files:
            project_map[rel_root] = sorted(clean_files)

    return project_map


def print_project_tree(project_map):
    """
    Pretty print project structure.
    """

    print("\n=== MJONAI PROJECT INDEX ===\n")

    for folder in sorted(project_map.keys()):

        print(f"\n[{folder}]")

        for file in project_map[folder]:
            print(f"  - {file}")


if __name__ == "__main__":

    project_map = build_project_tree()

    print_project_tree(project_map)