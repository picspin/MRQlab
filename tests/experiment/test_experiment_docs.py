from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_architecture_names_locked_contracts_and_boundaries():
    text = (ROOT / "docs/ARCHITECTURE.md").read_text()
    for required in (
        "ExperimentGraph", "PhysicsOperator", "StateRepresentation", "ObjectiveFunction", "Observation",
        "Experiment IR", "Sequence Compiler", "Sequence IR", "Physics Compiler", "Physics IR",
        "ONE Python process", "packages/mrqlab_experiment", "/experiments/run", "/simulate",
    ):
        assert required in text


def test_roadmap_holds_mvp_scope():
    text = (ROOT / "docs/ROADMAP.md").read_text()
    assert "SE" in text and "GRE" in text and "TSE" in text
    assert "Do not implement Floquet/CEST/MRS/DCE in v0.1" in text
