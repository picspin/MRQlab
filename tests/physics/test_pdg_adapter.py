import numpy as np
import pytest

from mrqlab_physics import EngineOptions, Phantom, ScannerModel, SimResult, list_engines
from mrqlab_physics.backends.pdg import PDGAdapter, PDGProviderUnavailable


class FakeProvider:
    def simulate(self, sequence, phantom, scanner, options):
        return SimResult(
            signal=np.array([1 + 0j]),
            k_trajectory=np.zeros((1, 3)),
            meta={"provider": "fake"},
        )


def test_pdg_adapter_has_explicit_unavailable_path():
    with pytest.raises(PDGProviderUnavailable, match="install and pass a PDGProvider"):
        PDGAdapter().simulate(None, Phantom(), ScannerModel(), EngineOptions())


def test_pdg_adapter_delegates_unified_contract():
    result = PDGAdapter(FakeProvider()).simulate(
        None, Phantom(), ScannerModel(), EngineOptions()
    )
    assert result.signal.tolist() == [1 + 0j]
    assert result.meta == {"provider": "fake", "engine": "pdg"}


def test_builtin_pdg_does_not_replace_optional_provider_seam():
    pdg = next(item for item in list_engines() if item["name"] == "pdg")
    assert pdg["available"] is True
    assert pdg["source"] == "built-in"
    with pytest.raises(PDGProviderUnavailable, match="install and pass a PDGProvider"):
        PDGAdapter().simulate(None, Phantom(), ScannerModel(), EngineOptions())
