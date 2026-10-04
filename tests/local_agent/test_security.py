from fastapi.testclient import TestClient

from mrqlab_agent.main import app, local_security

client = TestClient(app)


def _headers(**updates):
    headers = {
        "origin": "https://app.mrqlab.local",
        "x-mrqlab-pairing": local_security.pairing_secret,
        "x-mrqlab-csrf": local_security.csrf_token,
    }
    headers.update(updates)
    return headers


def test_capabilities_require_pairing_and_return_no_secrets():
    assert client.get("/v1/capabilities", headers={"origin": "https://app.mrqlab.local"}).status_code == 401
    response = client.get("/v1/capabilities", headers=_headers())
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://app.mrqlab.local"
    text = response.text.lower()
    assert "pairing_secret" not in text
    assert "private" not in text
    assert "token" not in text


def test_cors_preflight_options_succeeds_for_allowed_origin():
    response = client.options("/jobs", headers={"origin": "https://app.mrqlab.local"})
    assert response.status_code == 204
    assert response.headers.get("access-control-allow-origin") == "https://app.mrqlab.local"
    assert "X-MRQLab-Pairing" in response.headers.get("access-control-allow-headers", "")


def test_wrong_origin_and_missing_csrf_fail_before_mutation():
    assert client.post("/jobs", json={}, headers=_headers(origin="https://evil.example")).status_code == 403
    headers = _headers()
    headers.pop("x-mrqlab-csrf")
    assert client.post("/jobs", json={}, headers=headers).status_code == 403
