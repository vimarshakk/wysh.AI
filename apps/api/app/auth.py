"""Minimal, strict HS256 gateway-token verification for the local service boundary.

The token is issued by WyshCare, not by this service. This implementation is
deliberately algorithm-pinned and validates the claims needed for tenant and
patient isolation. Production deployments should use a managed secret or a
JWKS-backed asymmetric issuer before enabling PHI processing.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import threading
import time
from dataclasses import dataclass
from urllib.request import Request, urlopen

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from .config import Settings


class AuthError(ValueError):
    pass


@dataclass(frozen=True)
class GatewayPrincipal:
    subject: str
    tenant_id: str
    patient_ids: frozenset[str]
    scopes: frozenset[str]
    roles: frozenset[str]
    token_id: str | None
    purpose_of_use: str | None = None
    consent_id: str | None = None
    delegated_by: str | None = None


_jwks_cache: dict[str, tuple[float, dict[str, dict[str, str]]]] = {}
_jwks_lock = threading.Lock()


def _decode_segment(value: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, TypeError):
        raise AuthError("malformed token") from None


def _decode_int(value: str) -> int:
    try:
        return int.from_bytes(_decode_segment(value), "big")
    except (TypeError, ValueError):
        raise AuthError("malformed JWKS key") from None


def _load_jwks(url: str, ttl_seconds: int) -> dict[str, dict[str, str]]:
    now = time.time()
    with _jwks_lock:
        cached = _jwks_cache.get(url)
        if cached and cached[0] > now:
            return cached[1]
    try:
        request = Request(url, headers={"Accept": "application/json"}, method="GET")
        with urlopen(request, timeout=5) as response:
            document = json.loads(response.read().decode("utf-8"))
    except (OSError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError):
        raise AuthError("JWKS unavailable") from None
    keys = document.get("keys")
    if not isinstance(keys, list):
        raise AuthError("invalid JWKS document")
    indexed: dict[str, dict[str, str]] = {}
    for key in keys:
        if isinstance(key, dict) and isinstance(key.get("kid"), str) and key.get("kty") == "RSA" and isinstance(key.get("n"), str) and isinstance(key.get("e"), str):
            indexed[key["kid"]] = key
    if not indexed:
        raise AuthError("JWKS has no usable RSA keys")
    with _jwks_lock:
        _jwks_cache[url] = (now + ttl_seconds, indexed)
    return indexed


def _verify_signature(header: dict, parts: list[str], signature: bytes, settings: Settings) -> None:
    algorithm = header.get("alg")
    if algorithm != settings.service_token_algorithm:
        raise AuthError("unsupported token algorithm")
    signing_input = f"{parts[0]}.{parts[1]}".encode()
    if algorithm == "HS256":
        if not settings.service_token_secret:
            raise AuthError("service token verification is not configured")
        expected = hmac.new(settings.service_token_secret.encode(), signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, signature):
            raise AuthError("invalid token signature")
        return
    if algorithm != "RS256" or not settings.service_token_jwks_url:
        raise AuthError("unsupported token algorithm")
    kid = header.get("kid")
    if not isinstance(kid, str):
        raise AuthError("token key id missing")
    key = _load_jwks(settings.service_token_jwks_url, settings.service_token_jwks_cache_ttl_seconds).get(kid)
    if not key:
        raise AuthError("token key not found")
    try:
        public_key = rsa.RSAPublicNumbers(_decode_int(key["e"]), _decode_int(key["n"])).public_key()
        public_key.verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA256())
    except (InvalidSignature, ValueError, TypeError):
        raise AuthError("invalid token signature") from None


def verify_bearer_token(
    authorization: str | None,
    settings: Settings,
    *,
    tenant_id: str,
    patient_id: str | None,
    required_scope: str,
) -> GatewayPrincipal:
    if settings.service_token_algorithm not in {"HS256", "RS256"}:
        raise AuthError("unsupported token algorithm")
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthError("bearer token required")
    token = authorization[7:].strip()
    parts = token.split(".")
    if len(parts) != 3:
        raise AuthError("malformed token")
    header_bytes, payload_bytes, signature = (_decode_segment(part) for part in parts)
    try:
        header = json.loads(header_bytes)
        claims = json.loads(payload_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise AuthError("malformed token") from None
    if header.get("typ") != "JWT":
        raise AuthError("unsupported token type")
    _verify_signature(header, parts, signature, settings)
    now = int(time.time())
    if claims.get("iss") != settings.service_token_issuer or claims.get("aud") != settings.service_token_audience:
        raise AuthError("invalid token issuer or audience")
    if not isinstance(claims.get("exp"), int) or claims["exp"] <= now:
        raise AuthError("expired token")
    if not isinstance(claims.get("iat"), int) or claims["iat"] > now + 60:
        raise AuthError("invalid token issued-at time")
    if claims.get("tenant_id") != tenant_id:
        raise AuthError("tenant scope denied")
    patient_scope = claims.get("patient_ids", [])
    if not isinstance(patient_scope, list) or not all(isinstance(item, str) for item in patient_scope):
        raise AuthError("invalid patient scope")
    if patient_id is not None and patient_id not in patient_scope and "*" not in patient_scope:
        raise AuthError("patient scope denied")
    scopes = claims.get("scope", [])
    if isinstance(scopes, str):
        scopes = scopes.split()
    if not isinstance(scopes, list) or not all(isinstance(item, str) for item in scopes):
        raise AuthError("invalid permission scope")
    if required_scope not in scopes:
        raise AuthError("permission scope denied")
    roles = claims.get("roles", [])
    if not isinstance(roles, list) or not all(isinstance(item, str) for item in roles):
        raise AuthError("invalid role claims")
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise AuthError("token subject missing")
    return GatewayPrincipal(subject, tenant_id, frozenset(patient_scope), frozenset(scopes), frozenset(roles), claims.get("jti"), claims.get("purpose_of_use"), claims.get("consent_id"), claims.get("delegated_by"))


def make_test_token(secret: str, *, issuer: str, audience: str, tenant_id: str, patient_ids: list[str], scopes: list[str], roles: list[str] | None = None, subject: str = "test-gateway", ttl_seconds: int = 300, purpose_of_use: str | None = None, consent_id: str | None = None, delegated_by: str | None = None) -> str:
    """Test-only token helper; never use this issuer in production."""
    now = int(time.time())  # noqa
def encode(value):
    return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).rstrip(b"=").decode()
    header = encode({"alg": "HS256", "typ": "JWT"})
    claims = {"iss": issuer, "aud": audience, "sub": subject, "iat": now, "exp": now + ttl_seconds, "tenant_id": tenant_id, "patient_ids": patient_ids, "scope": scopes, "roles": roles or []}  # noqa
    if purpose_of_use is not None:  # noqa
        claims["purpose_of_use"] = purpose_of_use  # noqa
    if consent_id is not None:  # noqa
        claims["consent_id"] = consent_id  # noqa
    if delegated_by is not None:  # noqa
        claims["delegated_by"] = delegated_by  # noqa
    payload = encode(claims)
    signature = base64.urlsafe_b64encode(hmac.new(secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()).rstrip(b"=").decode()  # noqa
    return f"{header}.{payload}.{signature}"
