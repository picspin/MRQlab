from mrqlab_physics.engines.bloch_engine import BlochEngine
from mrqlab_physics.engines.epg_engine import EPGEngine
from mrqlab_physics.engines.spectral_engine import SpectralEngine


def test_engine_modules_are_importable_from_split_package():
    assert BlochEngine.name == "bloch"
    assert EPGEngine.name == "epg"
    assert SpectralEngine.name == "spectral"
