import pytest
from mrqlab_sequence import build_sequence
from mrqlab_physics import EngineOptions, Phantom, ScannerModel, get_engine, list_engines

@pytest.mark.parametrize("template", ["SE", "GRE", "TSE"])
def test_bloch_template_returns_signal(template):
    sequence = build_sequence(template, {"te": .02, "tr": .1})
    result = get_engine().simulate(sequence, Phantom(), ScannerModel(), EngineOptions())
    assert result.signal.size > 0
    assert result.meta["engine"] == "bloch"

def test_builtin_engine_descriptors_are_available_and_identified():
    descriptors = {item["name"]: item for item in list_engines()}
    assert set(descriptors) == {"bloch", "epg", "epg-x", "hybrid", "spectral", "ssepg", "pdg"}
    for name in descriptors:
        assert descriptors[name]["available"] is True
        assert descriptors[name]["source"] == "built-in"
