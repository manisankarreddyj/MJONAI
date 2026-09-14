from pathlib import Path
import sys

# ADR-0008 org-level layout: the kernel lives at <repo>/mjonai and the repo
# root is the import namespace for `import mjonai.*`.
RESEARCH_ROOT = Path(__file__).resolve().parents[1]

# Repo root: the single namespace that makes `import mjonai.core...` resolve.
WORKSPACE_ROOT = RESEARCH_ROOT.parent

# The "build" is the repo root itself — there is no separate mjonai-build tree.
MJONAI_BUILD = WORKSPACE_ROOT

if str(MJONAI_BUILD) not in sys.path:
    sys.path.insert(0, str(MJONAI_BUILD))