"""Regression coverage for the diff-triggered validation classifier."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = spec_from_file_location("diff_checklist", ROOT / "tools/validation/diff_checklist.py")
assert SPEC and SPEC.loader
checklist = module_from_spec(SPEC)
SPEC.loader.exec_module(checklist)


def _names(paths: list[str]) -> set[str]:
    return set(checklist.classify(paths))


def test_agent_version_file_is_a_lease_surface():
    # The runtime compatibility version is imported from this file, so changing
    # it changes lease enforcement even though its basename lacks "license".
    assert "lease/licensing" in _names(["services/local_agent/mrqlab_agent/__init__.py"])


def test_deleting_hook_smoke_test_triggers_lease_surface():
    assert "lease/licensing" in _names(["tests/local_agent/test_precommit_hook.py"])


def test_package_web_path_is_a_frontend_surface():
    assert "frontend" in _names(["packages/example/web/components/Lease.tsx"])


def test_unrelated_package_path_is_not_frontend():
    assert "frontend" not in _names(["packages/example/core/license.py"])


def test_validation_tooling_has_its_own_guard_test():
    spec = checklist.SURFACES["validation-tooling"]
    assert "tests/test_diff_checklist.py" in spec["tests"]


def test_invalid_diff_base_has_a_readable_error():
    with pytest.raises(SystemExit, match="cannot read does-not-exist..HEAD"):
        checklist.changed_paths("does-not-exist", "HEAD")


def test_non_staged_cli_requires_an_explicit_base(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["diff_checklist.py"])
    with pytest.raises(SystemExit) as exc:
        checklist.main()
    assert exc.value.code == 2
    assert "--base is required unless --staged is used" in capsys.readouterr().err
