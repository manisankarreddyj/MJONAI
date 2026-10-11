"""ECharts vendoring contract (interactive app).

The installable PWA must be fully self-contained: the runtime template loads ONLY the
vendored dist (never a CDN), the dist + version pin exist on disk, and the pin agrees
with the vendoring script's default. These pins make a CDN regression (offline PWA
breakage) and an accidental dist deletion impossible to ship silently.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = REPO_ROOT / "apps" / "web" / "templates" / "index.html"
VENDOR_DIR = REPO_ROOT / "apps" / "web" / "static" / "vendor"
DIST = VENDOR_DIR / "echarts.min.js"
VERSION_FILE = VENDOR_DIR / "echarts.version"
FETCH_SCRIPT = REPO_ROOT / "tools" / "scripts" / "fetch_echarts.py"

# Any runtime reference to a chart CDN breaks the offline PWA contract.
_CDN_HOSTS = ("unpkg.com", "jsdelivr.net", "cdnjs", "googleapis.com", "jsdelivr")


def test_template_loads_only_the_vendored_dist():
    html = TEMPLATE.read_text(encoding="utf-8")
    assert 'src="/static/vendor/echarts.min.js"' in html, "PWA must load the vendored ECharts dist"


def test_template_has_no_runtime_cdn_references():
    html = TEMPLATE.read_text(encoding="utf-8")
    for host in _CDN_HOSTS:
        assert host not in html, f"runtime CDN reference found ({host}) — the PWA must work offline"


def test_vendored_dist_and_pin_exist():
    assert DIST.is_file() and DIST.stat().st_size > 200_000, "vendored echarts.min.js missing or truncated"
    pin = VERSION_FILE.read_text(encoding="utf-8").strip()
    assert pin, "echarts.version pin file is empty"


def test_pin_matches_the_vendoring_script_default():
    src = FETCH_SCRIPT.read_text(encoding="utf-8")
    pin = VERSION_FILE.read_text(encoding="utf-8").strip()
    assert f'DEFAULT_VERSION = "{pin}"' in src, (
        f"pin {pin} disagrees with fetch_echarts.py — re-vendor or align the default"
    )
