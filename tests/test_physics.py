import pytest
from mrqlab_sequence import build_sequence
from mrqlab_physics import EngineOptions, Phantom, ScannerModel, get_engine, list_engines

@pytest.mark.parametrize("template", ["SE", "GRE", "TSE"])
def test_bloch_template_returns_signal(template):
    sequence = build_sequence(template, {"te": .02, "tr": .1})
    result = get_engine().simulate(sequence, Phantom(), ScannerModel(), EngineOptions())
    assert result.signal.size > 0
    assert result.meta["engine"] == "bloch"

def test_registry_stubs_are_explicit():
    assert {e["name"] for e in list_engines()} == {"bloch", "epg", "spectral"}
    assert get_engine("bloch").available is True
    assert get_engine("epg").available is True
