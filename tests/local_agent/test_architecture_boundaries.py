from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_license_code_lives_only_at_the_execution_gateway():
    physics = "\n".join(path.read_text() for path in (ROOT / "packages/physics").rglob("*.py"))
    assert "LeaseVerifier" not in physics
    assert "require_entitlement" not in physics


def test_browser_has_no_lease_or_device_private_keys():
    web = "\n".join(path.read_text() for path in (ROOT / "apps/web").rglob("*.ts*") if "node_modules" not in path.parts)
    assert "Ed25519PrivateKey" not in web
    assert "device_private_key" not in web
    assert "lease_signing_key" not in web


def test_architecture_documents_capability_entitlement_and_sync_boundary():
    text = (ROOT / "docs/ARCHITECTURE.md").read_text()
    assert "Capability is not entitlement" in text
    assert " remains synchronous" in text
    assert "POST /jobs" in text
    assert "Ed25519" in text
    assert "loopback" in text
