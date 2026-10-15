"""
Offline regression suite for data/derivatives/participant_oi.py fetch layer.

Pins the two defects found in the 2026-10-15 engine log (`logs15102926.txt`):
  1. One 15m scan issued ~90 live NSE downloads in 2 seconds (S15 fetched per
     signal per symbol) — the once-daily publication is now memoized.
  2. The fetcher disabled TLS certificate verification while parsing numbers
     that feed trading signals — verification is now the default.
"""

import ssl
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

root_dir = Path(__file__).resolve().parent.parent  # repo root (ADR-0008)
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import mjonai.data.derivatives.participant_oi as poi


class _FakeResponse:
    def __init__(self, body: str):
        self._body = body

    def read(self):
        return self._body.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


_FII_CSV = (
    "Client Type,Future Index Long,Future Index Short,Future Stock Long,Future Stock Short,"
    "Option Index Call Long,Option Index Put Long,Total\n"
    "FII,12000,58000,45000,90000,150000,260000,1000000\n"
    "DII,20000,15000,30000,28000,90000,80000,500000\n"
)


def _reset_cache():
    poi.clear_oi_cache()


def test_fetch_memoizes_successful_download():
    """A second fetch inside the TTL performs zero network calls."""
    _reset_cache()
    with patch("mjonai.data.derivatives.participant_oi._download_nse_participant_oi") as dl:
        dl.return_value = MagicMock(date_str="2026-10-15")
        first = poi.fetch_live_nse_participant_oi()
        second = poi.fetch_live_nse_participant_oi()
        third = poi.fetch_live_nse_participant_oi()

    assert dl.call_count == 1
    assert first is second is third


def test_fetch_force_refresh_bypasses_cache():
    """force_refresh=True re-downloads and repopulates the cache."""
    _reset_cache()
    with patch("mjonai.data.derivatives.participant_oi._download_nse_participant_oi") as dl:
        dl.side_effect = [MagicMock(date_str="a"), MagicMock(date_str="b")]
        poi.fetch_live_nse_participant_oi()
        refreshed = poi.fetch_live_nse_participant_oi(force_refresh=True)
        after = poi.fetch_live_nse_participant_oi()

    assert dl.call_count == 2
    assert refreshed.date_str == "b"
    assert after is refreshed


def test_failed_fetch_is_cached_briefly_not_hammered():
    """An outage caches the failure for the short TTL so NSE is not hammered."""
    _reset_cache()
    with patch("mjonai.data.derivatives.participant_oi._download_nse_participant_oi") as dl:
        dl.return_value = None
        assert poi.fetch_live_nse_participant_oi() is None
        assert poi.fetch_live_nse_participant_oi() is None
        assert dl.call_count == 1


def test_success_cache_expires_after_ttl():
    """An expired success entry triggers exactly one re-download."""
    _reset_cache()
    with patch("mjonai.data.derivatives.participant_oi._download_nse_participant_oi") as dl, \
         patch("mjonai.data.derivatives.participant_oi.time.time") as fake_time:
        dl.return_value = MagicMock(date_str="2026-10-15")
        fake_time.return_value = 1_000.0
        poi.fetch_live_nse_participant_oi()

        fake_time.return_value = 1_000.0 + poi._OI_CACHE_TTL_SECONDS + 1.0
        poi.fetch_live_nse_participant_oi()

    assert dl.call_count == 2


def test_download_parses_fii_row_over_verified_tls(monkeypatch):
    """The real download path parses the FII row and uses a verified TLS context."""
    captured = {}

    def _fake_urlopen(req, context=None, timeout=None):
        captured["ctx"] = context
        captured["url"] = req.full_url
        return _FakeResponse(_FII_CSV)

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    _reset_cache()

    snap = poi._download_nse_participant_oi()

    assert snap is not None
    assert snap.fii_index_fut_long == 12000
    assert snap.fii_index_fut_short == 58000
    assert abs(snap.fii_index_fut_ratio - (12000 / 70000)) < 1e-9
    # 17.1% long ratio < 20% -> short-squeeze trap zone (parser's own thresholds)
    assert snap.is_short_squeeze_candidate is True
    assert snap.positioning_zone is poi.InstitutionalPositioningZone.SHORT_SQUEEZE_TRAP
    assert "fao_participant_oi_" in captured["url"]
    # TLS verified by default — the feed's numbers drive trading signals.
    assert captured["ctx"].verify_mode == ssl.CERT_REQUIRED
    assert captured["ctx"].check_hostname is True


def test_download_returns_none_on_archive_outage(monkeypatch):
    """A dead archive yields None (S15's non-trippable baseline), never a fabrication."""
    def _dead_urlopen(req, context=None, timeout=None):
        raise OSError("boom")

    monkeypatch.setattr("urllib.request.urlopen", _dead_urlopen)
    _reset_cache()
    assert poi._download_nse_participant_oi() is None


def test_tls_killswitch_is_explicit_and_logged(monkeypatch, caplog):
    """MJONAI_NSE_TLS_INSECURE=1 disables verification but says so loudly."""
    monkeypatch.delenv("MJONAI_NSE_TLS_INSECURE", raising=False)
    ctx_default = poi._nse_tls_context()
    assert ctx_default.verify_mode == ssl.CERT_REQUIRED

    monkeypatch.setenv("MJONAI_NSE_TLS_INSECURE", "1")
    with caplog.at_level("WARNING"):
        ctx_insecure = poi._nse_tls_context()
    assert ctx_insecure.verify_mode == ssl.CERT_NONE
    assert any("TLS verification DISABLED" in r.message for r in caplog.records)
