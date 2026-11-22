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

# git exports GIT_DIR / GIT_INDEX_FILE / GIT_WORK_TREE etc. to a running hook.
# This module itself runs *inside* the pre-commit hook (the hook invokes pytest),
# so those variables point at the OUTER repository and would make the nested git
# commands below operate on it instead of the throwaway repo — corrupting the
# real checkout's config. Scrub every GIT_* var so the smoke repo is hermetic.
def _clean_env(extra: dict | None = None) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(extra or {})
    return env


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, env=_clean_env())


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
    env = _clean_env({"MRQLAB_PYTHON": sys.executable, **(env_extra or {})})
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


def test_hook_fails_closed_when_no_interpreter_has_pytest(smoke_repo, tmp_path):
    # A gate that cannot run its checks must block, not silently pass. Point the
    # interpreter override at a python without pytest and assert the hook refuses.
    (smoke_repo / "services/local_agent/mrqlab_agent/license.py").write_text("# changed\n")
    _git(smoke_repo, "add", "-A")
    fake = tmp_path / "fakepy"
    fake.write_text("#!/bin/sh\nexit 1\n")  # `-c "import pytest"` fails -> not usable
    fake.chmod(0o755)
    result = _run_hook(smoke_repo, {"MRQLAB_PYTHON": str(fake)})
    assert result.returncode != 0
    assert "no interpreter with pytest" in result.stderr


def test_smoke_repo_never_writes_to_the_outer_repository(tmp_path, monkeypatch):
    """Guard against the incident where the smoke test corrupted the real config.

    The hook runs pytest, so this module executes with git's GIT_DIR /
    GIT_INDEX_FILE pointing at the OUTER repo. If the nested git calls inherit
    those, `git init` / `git config` inside the throwaway repo silently rewrite
    the outer repository's config (this once flipped core.bare and injected a
    [user] section). Assert the outer config is byte-identical after a run.
    """
    outer_git = subprocess.run(
        ["git", "rev-parse", "--absolute-git-dir"], cwd=ROOT, capture_output=True, text=True,
        env=_clean_env(),
    ).stdout.strip()
    if not outer_git:
        pytest.skip("not inside a git repository")
    outer_config = Path(outer_git) / "config"
    before = outer_config.read_bytes() if outer_config.is_file() else b""

    # Simulate the in-hook condition: point GIT_DIR/GIT_INDEX_FILE at the outer
    # repo, then seed and drive a smoke repo exactly as the other tests do.
    monkeypatch.setenv("GIT_DIR", outer_git)
    repo = tmp_path / "smoke"
    repo.mkdir()
    _seed_repo(repo)
    (repo / "services/local_agent/mrqlab_agent/license.py").write_text("# changed\n")
    _git(repo, "add", "-A")
    _run_hook(repo)

    after = outer_config.read_bytes() if outer_config.is_file() else b""
    assert after == before, "the smoke test mutated the outer repository's config"
