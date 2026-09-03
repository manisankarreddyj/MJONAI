from pathlib import Path
import sys

# Root of mjonai-research
RESEARCH_ROOT = Path(__file__).resolve().parents[1]

# Root containing both repositories
WORKSPACE_ROOT = RESEARCH_ROOT.parent

# Production project
MJONAI_BUILD = WORKSPACE_ROOT / "mjonai-build"

if str(MJONAI_BUILD) not in sys.path:
    sys.path.insert(0, str(MJONAI_BUILD))