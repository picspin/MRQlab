from fastapi.testclient import TestClient

from mrqlab_api.main import app
from mrqlab_experiment.pulse_inspector import PulseInspectRequest, inspect_pulse

client = TestClient(app)


def test_sinc_peak_at_center():
    analysis = inspect_pulse(PulseInspectRequest(flip_angle_deg=150.0, duration_ms=2.5, time_bandwidth=4.0))
    mid = len(analysis.waveform_b1) // 2
    assert analysis.waveform_b1[mid] == max(analysis.waveform_b1)
    assert analysis.peak_b1 > 0


def test_higher_fa_increases_peak_b1():
    low = inspect_pulse(PulseInspectRequest(flip_angle_deg=90.0))
    high = inspect_pulse(PulseInspectRequest(flip_angle_deg=180.0))
    assert high.peak_b1 > low.peak_b1


def test_slice_profile_mxy_peaks_at_isocenter():
    analysis = inspect_pulse(PulseInspectRequest(slice_thickness_mm=5.0))
    mid = len(analysis.slice_profile_mxy) // 2
    assert analysis.slice_profile_mxy[mid] == max(analysis.slice_profile_mxy)
    assert abs(analysis.spatial_axis_mm[mid]) < 0.2


def test_epg_matrix_is_3x3_and_bounded():
    analysis = inspect_pulse(PulseInspectRequest(flip_angle_deg=150.0))
    mat = analysis.epg_transition_matrix
    assert len(mat) == 3 and all(len(row) == 3 for row in mat)
    for row in mat:
        for val in row:
            assert abs(val) <= 1.0 + 1e-9


def test_pulse_inspect_endpoint():
    res = client.post(
        "/pulse/inspect",
        json={"flip_angle_deg": 150.0, "duration_ms": 2.5, "time_bandwidth": 4.0, "slice_thickness_mm": 5.0},
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body["waveform_b1"]) == 61
    assert len(body["freq_response_mag"]) == 51
    assert len(body["slice_profile_mxy"]) == 51
    assert body["kind"] == "shaped_sinc"
    assert body["bw_khz"] > 0
