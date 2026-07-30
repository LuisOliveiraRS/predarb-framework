from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth.errors import (
    InvalidAccessTokenError,
    MFARequiredError,
)
from app.auth.jwt_verifier import SupabaseJWTVerifier
from app.core.settings import Settings


ISSUER = "https://example.supabase.co/auth/v1"
AUDIENCE = "authenticated"


class FakeJWKClient:
    def __init__(self, public_key):
        self.public_key = public_key
        self.calls = 0

    def get_signing_key_from_jwt(self, token):
        self.calls += 1
        return self.public_key


@pytest.fixture()
def rsa_keys():
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    return private_key, private_key.public_key()


def make_settings():
    return Settings(
        _env_file=None,
        DEBUG=False,
        AUTH_ENABLED=True,
        AUTH_REQUIRED_FOR_DASHBOARD=True,
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_PUBLISHABLE_KEY="sb_publishable_test",
        SUPABASE_JWT_AUDIENCE=AUDIENCE,
        SUPABASE_JWT_ALGORITHMS="RS256",
        SUPABASE_JWKS_CACHE_TTL_SECONDS=600,
    )


def token_payload(**overrides):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(uuid4()),
        "email": "admin@example.com",
        "role": "authenticated",
        "aal": "aal1",
        "session_id": str(uuid4()),
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + timedelta(minutes=15),
        "is_anonymous": False,
    }
    payload.update(overrides)
    return payload


def encode_token(private_key, payload, algorithm="RS256"):
    return jwt.encode(
        payload,
        private_key,
        algorithm=algorithm,
        headers={"kid": "phase13b-test"},
    )


def make_verifier(public_key):
    return SupabaseJWTVerifier(
        make_settings(),
        jwks_client=FakeJWKClient(public_key),
    )


def test_valid_supabase_token_creates_principal(rsa_keys):
    private_key, public_key = rsa_keys
    payload = token_payload(aal="aal2")
    token = encode_token(private_key, payload)

    principal = make_verifier(public_key).verify(token)

    assert str(principal.user_id) == payload["sub"]
    assert principal.email == "admin@example.com"
    assert principal.token_role == "authenticated"
    assert principal.aal == "aal2"
    assert principal.has_mfa is True


def test_aal1_session_is_rejected_for_mfa_operation(rsa_keys):
    private_key, public_key = rsa_keys
    token = encode_token(
        private_key,
        token_payload(aal="aal1"),
    )

    principal = make_verifier(public_key).verify(token)

    with pytest.raises(
        MFARequiredError,
        match="autenticacao multifator",
    ):
        principal.require_mfa()


def test_missing_aal_is_treated_as_aal1(rsa_keys):
    private_key, public_key = rsa_keys
    payload = token_payload()
    payload.pop("aal")
    token = encode_token(private_key, payload)

    principal = make_verifier(public_key).verify(token)

    assert principal.aal == "aal1"
    assert principal.has_mfa is False


def test_expired_token_is_rejected(rsa_keys):
    private_key, public_key = rsa_keys
    now = datetime.now(timezone.utc)
    token = encode_token(
        private_key,
        token_payload(
            iat=now - timedelta(minutes=20),
            exp=now - timedelta(minutes=1),
        ),
    )

    with pytest.raises(
        InvalidAccessTokenError,
        match="invalido ou expirado",
    ):
        make_verifier(public_key).verify(token)


def test_wrong_audience_is_rejected(rsa_keys):
    private_key, public_key = rsa_keys
    token = encode_token(
        private_key,
        token_payload(aud="another-audience"),
    )

    with pytest.raises(InvalidAccessTokenError):
        make_verifier(public_key).verify(token)


def test_wrong_issuer_is_rejected(rsa_keys):
    private_key, public_key = rsa_keys
    token = encode_token(
        private_key,
        token_payload(
            iss="https://attacker.invalid/auth/v1",
        ),
    )

    with pytest.raises(InvalidAccessTokenError):
        make_verifier(public_key).verify(token)


def test_anonymous_user_is_rejected(rsa_keys):
    private_key, public_key = rsa_keys
    token = encode_token(
        private_key,
        token_payload(is_anonymous=True),
    )

    with pytest.raises(
        InvalidAccessTokenError,
        match="anonimos",
    ):
        make_verifier(public_key).verify(token)


def test_non_authenticated_role_is_rejected(rsa_keys):
    private_key, public_key = rsa_keys
    token = encode_token(
        private_key,
        token_payload(role="anon"),
    )

    with pytest.raises(
        InvalidAccessTokenError,
        match="usuario autenticado",
    ):
        make_verifier(public_key).verify(token)


def test_missing_subject_is_rejected(rsa_keys):
    private_key, public_key = rsa_keys
    payload = token_payload()
    payload.pop("sub")
    token = encode_token(private_key, payload)

    with pytest.raises(InvalidAccessTokenError):
        make_verifier(public_key).verify(token)


def test_disallowed_algorithm_is_rejected_before_jwks():
    fake_client = FakeJWKClient("unused")

    verifier = SupabaseJWTVerifier(
        make_settings(),
        jwks_client=fake_client,
    )

    token = jwt.encode(
        token_payload(),
        "temporary-test-secret",
        algorithm="HS256",
        headers={"kid": "invalid-algorithm"},
    )

    with pytest.raises(
        InvalidAccessTokenError,
        match="Algoritmo JWT nao autorizado",
    ):
        verifier.verify(token)

    assert fake_client.calls == 0
