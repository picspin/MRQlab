from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_physics_document_names_engines_contracts_and_primary_citations():
    text = (ROOT / "docs" / "PHYSICS.md").read_text()
    for required in (
        "BlochEngine", "EPGEngine", "SpectralEngine",
        "RfOp", "Relax", "Shift", "GradInterval", "AdcSample",
        "Weigel 2015", "Malik et al. 2018", "10.1002/mrm.29101",
        "10.1002/mrm.30055", "mrqlab.physics_engines",
        "not a clinical", "dimensionless teaching gradients",
    ):
        assert required in text
