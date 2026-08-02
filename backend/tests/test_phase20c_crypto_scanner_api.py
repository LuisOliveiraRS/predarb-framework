"""Fase 20C - API do scanner cripto.

O ponto central destes testes e que os endpoints nascem fechados.
A Fase 14 criou /opportunities publico, e a protecao adicionada na
Fase 17 virou no-op em producao porque a flag estava desligada.
Aqui a exigencia de autenticacao e verificada desde o primeiro
commit.
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.api.routers import crypto_scanner
from app.core.application import create_app
from app.core.settings import settings


SNAPSHOT_PATH = "/crypto/scanner/snapshot"
STATUS_PATH = "/crypto/scanner/status"


@pytest.fixture
def client(monkeypatch):
    """Cliente com a exigencia de auth desligada explicitamente.

    O .env local do projeto liga AUTH_REQUIRED_FOR_DASHBOARD, e
    teste que depende de configuracao de ambiente passa ou falha
    conforme a maquina. Cada teste declara o que precisa.
    """

    monkeypatch.setattr(
        settings,
        "AUTH_REQUIRED_FOR_DASHBOARD",
        False,
    )

    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def enforcing_client(monkeypatch):
    """Cliente com a exigencia de auth ligada."""

    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(
        settings,
        "AUTH_REQUIRED_FOR_DASHBOARD",
        True,
    )

    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def scanner_disabled(monkeypatch):
    monkeypatch.setattr(
        settings,
        "CRYPTO_SCANNER_ENABLED",
        False,
    )


class FakeService:
    def __init__(self):
        self.snapshot_calls = 0
        self.status_calls = 0

    def snapshot(self):
        self.snapshot_calls += 1

        return {
            "status": "READY",
            "snapshot_available": True,
            "served_from_snapshot": True,
            "opportunity_count": 2,
            "read_only": True,
            "market_data_only": True,
            "execution_authorized": False,
            "financial_execution": False,
            "automatic_execution_authorized": False,
            "order_submission_available": False,
        }

    def status(self):
        self.status_calls += 1

        return {
            "enabled": True,
            "cycles": 7,
            "successes": 7,
            "failures": 0,
            "last_status": "READY",
            "read_only": True,
            "market_data_only": True,
            "execution_authorized": False,
            "financial_execution": False,
            "order_submission_available": False,
        }


@pytest.fixture
def fake_service(monkeypatch):
    service = FakeService()

    monkeypatch.setattr(
        crypto_scanner,
        "_service",
        lambda: service,
    )

    return service


# ---------------------------------------------------------------
# Contrato de seguranca
# ---------------------------------------------------------------


def test_routes_are_registered():
    """Inspeciona o roteador, nao `app.routes`.

    O FastAPI 0.139 embrulha roteadores incluidos num
    `_IncludedRouter` e nao achata mais as rotas em `app.routes`,
    entao varrer a aplicacao por caminho nao encontra nada.
    """

    paths = {
        route.path
        for route in crypto_scanner.router.routes
    }

    assert SNAPSHOT_PATH in paths
    assert STATUS_PATH in paths


def test_routes_are_reachable_through_the_app(client):
    assert client.get(SNAPSHOT_PATH).status_code != 404
    assert client.get(STATUS_PATH).status_code != 404


def test_endpoints_declare_auth_dependency():
    """A dependencia esta no router, nao rota a rota.

    Verificar no router garante que endpoints futuros nasçam
    protegidos por construcao, sem depender de alguem lembrar.
    """

    names = [
        dependency.dependency.__name__
        for dependency in crypto_scanner.router.dependencies
    ]

    assert "require_dashboard_user" in names


def test_snapshot_requires_auth_when_enforced(
    enforcing_client,
):
    response = enforcing_client.get(SNAPSHOT_PATH)

    assert response.status_code == 401


def test_status_requires_auth_when_enforced(
    enforcing_client,
):
    response = enforcing_client.get(STATUS_PATH)

    assert response.status_code == 401


def test_auth_is_enforced_even_when_scanner_is_disabled(
    enforcing_client,
    scanner_disabled,
):
    """Desligado nao vaza estado para quem nao esta autenticado."""

    assert (
        enforcing_client.get(SNAPSHOT_PATH).status_code
        == 401
    )


# ---------------------------------------------------------------
# Coletor desligado
# ---------------------------------------------------------------


def test_snapshot_reports_disabled_without_error(
    client,
    scanner_disabled,
):
    """Desligado e configuracao valida, nao falha."""

    response = client.get(SNAPSHOT_PATH)

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "DISABLED"
    assert payload["snapshot_available"] is False
    assert "CRYPTO_SCANNER_ENABLED" in payload["detail"]


def test_status_reports_disabled_without_error(
    client,
    scanner_disabled,
):
    response = client.get(STATUS_PATH)

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "DISABLED"
    assert payload["enabled"] is False
    assert payload["cycles"] == 0


def test_disabled_scanner_never_builds_the_service(
    client,
    scanner_disabled,
    fake_service,
):
    """Desligado nao deve sequer construir o servico."""

    client.get(SNAPSHOT_PATH)
    client.get(STATUS_PATH)

    assert fake_service.snapshot_calls == 0
    assert fake_service.status_calls == 0


def test_disabled_payload_declares_safety_flags(
    client,
    scanner_disabled,
):
    payload = client.get(SNAPSHOT_PATH).json()

    assert payload["read_only"] is True
    assert payload["market_data_only"] is True
    assert payload["execution_authorized"] is False
    assert payload["financial_execution"] is False
    assert payload["order_submission_available"] is False
    assert (
        payload["automatic_execution_authorized"] is False
    )


# ---------------------------------------------------------------
# Coletor ligado
# ---------------------------------------------------------------


@pytest.fixture
def scanner_enabled(monkeypatch):
    monkeypatch.setattr(
        settings,
        "CRYPTO_SCANNER_ENABLED",
        True,
    )


def test_snapshot_serves_service_payload(
    client,
    scanner_enabled,
    fake_service,
):
    response = client.get(SNAPSHOT_PATH)

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "READY"
    assert payload["served_from_snapshot"] is True
    assert payload["opportunity_count"] == 2
    assert fake_service.snapshot_calls == 1


def test_status_serves_service_payload(
    client,
    scanner_enabled,
    fake_service,
):
    response = client.get(STATUS_PATH)

    assert response.status_code == 200

    payload = response.json()

    assert payload["cycles"] == 7
    assert payload["failures"] == 0
    assert fake_service.status_calls == 1


def test_reading_snapshot_does_not_trigger_collection(
    client,
    scanner_enabled,
    fake_service,
):
    """A API le memoria; quem coleta e o scheduler."""

    for _ in range(5):
        client.get(SNAPSHOT_PATH)

    # Cinco leituras, cinco chamadas ao snapshot em memoria.
    # Nenhuma delas dispara ciclo: o servico dublado registraria.
    assert fake_service.snapshot_calls == 5


def test_responses_are_not_cached(
    client,
    scanner_enabled,
    fake_service,
):
    response = client.get(SNAPSHOT_PATH)

    assert response.headers["Cache-Control"] == "no-store"


def test_enabled_payload_keeps_safety_flags(
    client,
    scanner_enabled,
    fake_service,
):
    payload = client.get(SNAPSHOT_PATH).json()

    assert payload["read_only"] is True
    assert payload["execution_authorized"] is False
    assert payload["financial_execution"] is False
    assert payload["order_submission_available"] is False


def test_no_endpoint_accepts_write_methods(client):
    for path in (SNAPSHOT_PATH, STATUS_PATH):
        for method in ("post", "put", "delete", "patch"):
            response = getattr(client, method)(path)

            assert response.status_code in (404, 405)
