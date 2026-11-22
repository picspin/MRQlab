import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def git(repo, *args, check=True):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "HOME": str(repo), "MRQLAB_PYTHON": sys.executable})
    return subprocess.run(["git", *args], cwd=repo, env=env, text=True,
                          capture_output=True, check=check)


def test_precommit_hook_checks_staged_diff_and_reports_affected_areas(tmp_path):
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.name", "Test")
    git(tmp_path, "config", "user.email", "test@example.invalid")
    (tmp_path / "scripts").mkdir()
    (tmp_path / ".githooks").mkdir()
    shutil.copy(ROOT / "scripts" / "check_staged.py", tmp_path / "scripts")
    shutil.copytree(ROOT / "tools" / "validation", tmp_path / "tools" / "validation")
    shutil.copy(ROOT / ".githooks" / "pre-commit", tmp_path / ".githooks")
    (tmp_path / ".githooks" / "pre-commit").chmod(0o755)
    git(tmp_path, "config", "core.hooksPath", ".githooks")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_smoke.py").write_text("def test_pass():\n    assert True\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "seed", "--no-verify")
    path = tmp_path / "packages" / "mrqlab_experiment" / "example.py"
    path.parent.mkdir(parents=True)
    path.write_text("value = 1\n")
    git(tmp_path, "add", str(path))
    ok = git(tmp_path, "commit", "-qm", "valid")
    assert "clinical/experiment" in ok.stderr
    path.write_text("value = 2  \n")
    git(tmp_path, "add", str(path))
    rejected = git(tmp_path, "commit", "-qm", "invalid", check=False)
    assert rejected.returncode != 0
    assert "trailing whitespace" in rejected.stderr
