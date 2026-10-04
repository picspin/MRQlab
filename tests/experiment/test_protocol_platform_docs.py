from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_architecture_names_product_layers_profiles_and_contract():
    text = (ROOT / "docs/ARCHITECTURE.md").read_text()
    for required in (
        "research-use-only MRI contrast and protocol engineering platform",
        "Explore",
        "Protocol Studio",
        "Compute",
        "Export",
        "Enterprise Control Plane",
        "Tier 0",
        "Tier 1",
        "Tier 2",
        "ResolvedExecutionPlan",
        "Capability is not entitlement",
        "POST /experiments/run",
        "POST /jobs",
    ):
        assert required in text


def test_architecture_and_physics_agree_ssepg_and_pdg_are_available():
    architecture = (ROOT / "docs/ARCHITECTURE.md").read_text()
    physics = (ROOT / "docs/PHYSICS.md").read_text()
    assert "| ssEPG | yes |" in architecture
    assert "| PDG | yes |" in architecture
    assert "| ssEPG | yes |" in physics
    assert "| PDG | yes |" in physics


def test_roadmap_locks_two_a_verticals_and_parks_b_and_c():
    text = (ROOT / "docs/ROADMAP.md").read_text()
    assert "Brain lesion T2/TSE" in text
    assert "Knee cartilage/meniscus PD/T2 TSE" in text
    assert "Dixon / TOF / CEST research" in text
    assert "Milestone B — Executable Sequence (parked)" in text
    assert "Milestone C — Licensed Local Compute (parked)" in text
