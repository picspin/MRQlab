from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_adr_0007_defines_pr_ablation_gate():
    text = (ROOT / "docs/adr/ADR-0007-pr-ablation-gate.md").read_text()
    for required in (
        "Ablation Report",
        "Delete it in this PR",
        "one-use wrapper",
        "dual-stack still green",
        "lock-face",
        "Future-only stubs",
        "blocks",
    ):
        assert required in text


def test_pr_template_requires_ablation_section():
    text = (ROOT / ".github/pull_request_template.md").read_text()
    assert "## Ablation" in text
    assert "ADR-0007" in text
    assert "Future-only stubs" in text


def test_contributing_and_architecture_point_at_ablation_gate():
    contributing = (ROOT / "CONTRIBUTING.md").read_text()
    architecture = (ROOT / "docs/ARCHITECTURE.md").read_text()
    roadmap = (ROOT / "docs/ROADMAP.md").read_text()
    assert "ADR-0007" in contributing
    assert "Ablation gate" in contributing
    assert "ADR-0007" in architecture
    assert "ablation" in architecture.lower()
    assert "ADR-0007" in roadmap
    assert "ablation" in roadmap.lower()
