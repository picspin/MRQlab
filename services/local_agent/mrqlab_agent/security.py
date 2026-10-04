import hashlib
import hmac
import secrets

from fastapi import HTTPException, Request, Response


class LocalSecurity:
    def __init__(self, allowed_origins: frozenset[str], pairing_secret: str | None = None):
        self.allowed_origins = allowed_origins
        self.pairing_secret = pairing_secret or secrets.token_urlsafe(32)
        self.csrf_token = hmac.new(self.pairing_secret.encode(), b"mrqlab-csrf", hashlib.sha256).hexdigest()

    def handle_cors(self, request: Request, response: Response | None = None) -> None:
        origin = request.headers.get("origin")
        if origin and origin in self.allowed_origins and response is not None:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-MRQLab-Pairing, X-MRQLab-CSRF"
            response.headers["Access-Control-Allow-Credentials"] = "true"

    def verify(self, request: Request, response: Response | None = None) -> None:
        self.handle_cors(request, response)
        host = request.client.host if request.client else ""
        if host not in {"127.0.0.1", "::1", "testclient"}:
            raise HTTPException(403, "local agent accepts loopback clients only")
        origin = request.headers.get("origin")
        if origin is not None and origin not in self.allowed_origins:
            raise HTTPException(403, "origin is not allowed")
        if request.method == "OPTIONS":
            return
        supplied = request.headers.get("x-mrqlab-pairing", "")
        if not hmac.compare_digest(supplied, self.pairing_secret):
            raise HTTPException(401, "local pairing is required")
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            csrf = request.headers.get("x-mrqlab-csrf", "")
            if not hmac.compare_digest(csrf, self.csrf_token):
                raise HTTPException(403, "valid CSRF token is required")
