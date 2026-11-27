"""Gate 4 regression guard: deep-reviewer.md keeps the validator-review region.

Asserts the working-tree agent file. Review runs inject the main-branch rules
(gate 2), so this guard only ensures the worktree copy does not silently lose the region.
"""
from pathlib import Path

AGENT = Path(__file__).resolve().parents[1] / ".claude" / "agents" / "deep-reviewer.md"


def test_agent_file_contains_validator_region():
    assert "## Validator Review" in AGENT.read_text(encoding="utf-8")


def test_agent_file_contains_six_checkpoints():
    text = AGENT.read_text(encoding="utf-8")
    for kw in (
        "sleep as async",
        "skipped assertion",
        "real path",
        "lowered threshold",
        "loosened assertion",
        "mock as measurement",
        "Severity guidance",
    ):
        assert kw in text, f"missing keyword: {kw}"
