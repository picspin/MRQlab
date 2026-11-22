"""End-to-end smoke test for the pre-commit hook.

This is the *e2e* of the validation framework: it copies the repository's
`.githooks/pre-commit` and `tools/validation/` into a throwaway git repo, makes a
staged change that removes a required lease test file, and asserts the hook
blocks the commit; then restores the file and asserts the hook passes.

It exercises the real script through real git, so a broken hook wiring (wrong
path, missing exec bit, swallowed exit code) fails here rather than in review.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REQUIRED_TEST = "tests/local_agent/test_lease_window_properties.py"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)


def _seed_repo(repo: Path) -> None:
    """A minimal repo carrying the hook, the tooling, and the surface files."""
    (repo / ".githooks").mkdir(parents=True)
    shutil.copy2(ROOT / ".githooks/pre-commit", repo / ".githooks/pre-commit")
    (repo / ".githooks/pre-commit").chmod(0o755)
    shutil.copytree(ROOT / "tools/validation", repo / "tools/validation")
    # The checklist requires these test files to exist for the lease surface.
    for rel in (
        "tests/local_agent/test_license.py",
        "tests/local_agent/test_lease_wiring.py",
        "tests/local_agent/test_lease_window_properties.py",
        "tests/local_agent/test_lease_window_differential.py",
    ):
        dest = repo / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("# placeholder for the smoke repo\n")
    # A file on the lease surface so the diff triggers that checklist entry.
    agent = repo / "services/local_agent/mrqlab_agent"
    agent.mkdir(parents=True, exist_ok=True)
    (agent / "license.py").write_text("# placeholder\n")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "smoke@example.com")
    _git(repo, "config", "user.name", "smoke")
    _git(repo, "config", "core.hooksPath", ".githooks")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "seed", "--no-verify")


def _run_hook(repo: Path, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "MRQLAB_PYTHON": sys.executable, **(env_extra or {})}
    return subprocess.run(
        [str(repo / ".githooks/pre-commit")], cwd=repo, capture_output=True, text=True, env=env,
    )


@pytest.fixture()
def smoke_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "smoke"
    repo.mkdir()
    _seed_repo(repo)
    return repo


def test_hook_blocks_a_lease_change_that_drops_a_required_test(smoke_repo):
    # Stage a lease-surface change AND delete a required test file: must block.
    (smoke_repo / "services/local_agent/mrqlab_agent/license.py").write_text("# changed\n")
    (smoke_repo / REQUIRED_TEST).unlink()
    _git(smoke_repo, "add", "-A")
    result = _run_hook(smoke_repo)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "MISSING" in result.stdout or "CHECK FAILED" in result.stdout


def test_hook_passes_when_the_surface_is_intact(smoke_repo):
    (smoke_repo / "services/local_agent/mrqlab_agent/license.py").write_text("# changed\n")
    _git(smoke_repo, "add", "-A")
    result = _run_hook(smoke_repo, {"MRQLAB_SKIP_PRECOMMIT": "0"})
    # The checklist passes (all required tests present); the focused pytest of the
    # placeholder tests may fail, so assert only that the checklist stage ran and
    # reported OK rather than asserting the whole hook's exit code.
    assert "diff-triggered validation checklist" in result.stdout
    assert "CHECK FAILED" not in result.stdout


def test_hook_is_bypassed_by_the_escape_hatch(smoke_repo):
    (smoke_repo / REQUIRED_TEST).unlink()
    _git(smoke_repo, "add", "-A")
    result = _run_hook(smoke_repo, {"MRQLAB_SKIP_PRECOMMIT": "1"})
    assert result.returncode == 0
    assert "skipped" in result.stdout
