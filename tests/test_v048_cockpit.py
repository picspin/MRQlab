from fastapi.testclient import TestClient

from mrqlab_api.main import app
from mrqlab_experiment.cockpit_signals import (
    CockpitSignalRequest,
    CockpitTissue,
    compute_cockpit_signals,
)

client = TestClient(app)

LESION = CockpitTissue(id="lesion", name="MS Lesion", t1=1400, t2=120, t2s=80, pd=0.95)
WM = CockpitTissue(id="wm", name="WM", t1=900, t2=80, t2s=60, pd=0.70)


def test_tse_longer_te_reduces_short_t2_intensity():
    short = compute_cockpit_signals(
        CockpitSignalRequest(seq_type="TSE", fa_deg=150, te_ms=40, tr_ms=3000, tissues=[WM])
    )
    long = compute_cockpit_signals(
        CockpitSignalRequest(seq_type="TSE", fa_deg=150, te_ms=160, tr_ms=3000, tissues=[WM])
    )
    assert long.signals["wm"] < short.signals["wm"]


def test_tse_higher_fa_increases_relative_sar():
    lo = compute_cockpit_signals(
        CockpitSignalRequest(seq_type="TSE", fa_deg=120, te_ms=100, tr_ms=3000, tissues=[LESION, WM])
    )
    hi = compute_cockpit_signals(
        CockpitSignalRequest(seq_type="TSE", fa_deg=180, te_ms=100, tr_ms=3000, tissues=[LESION, WM])
    )
    assert hi.relative_sar > lo.relative_sar


def test_gre_ernst_peak_near_small_fa_for_short_tr():
    """Short-TR GRE: Ernst angle is small; 12° should beat 60° for liver-like T1."""
    liver = CockpitTissue(id="liver", name="Liver", t1=800, t2=45, t2s=30, pd=0.70)
    small = compute_cockpit_signals(
        CockpitSignalRequest(seq_type="GRE", fa_deg=12, te_ms=2.3, tr_ms=15, tissues=[liver])
    )
    large = compute_cockpit_signals(
        CockpitSignalRequest(seq_type="GRE", fa_deg=60, te_ms=2.3, tr_ms=15, tissues=[liver])
    )
    assert small.signals["liver"] > large.signals["liver"]
    assert small.is_gre is True


def test_contrast_and_cnr_from_two_tissues():
    analysis = compute_cockpit_signals(
        CockpitSignalRequest(seq_type="TSE", fa_deg=150, te_ms=100, tr_ms=3000, tissues=[LESION, WM])
    )
    assert analysis.delta_signal > 0
    assert abs(analysis.cnr_proxy - analysis.delta_signal * 20.0) < 1e-6
    assert set(analysis.signals) == {"lesion", "wm"}


def test_cockpit_signals_endpoint():
    res = client.post(
        "/cockpit/signals",
        json={
            "seq_type": "TSE",
            "fa_deg": 150,
            "te_ms": 100,
            "tr_ms": 3000,
            "tissues": [
                {"id": "lesion", "name": "MS", "t1": 1400, "t2": 120, "pd": 0.95},
                {"id": "wm", "name": "WM", "t1": 900, "t2": 80, "pd": 0.70},
            ],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert "signals" in body and "relative_sar" in body and "cnr_proxy" in body
    assert "lesion" in body["signals"]
    assert body["is_gre"] is False
    assert body["refocus_eff"] > 0
