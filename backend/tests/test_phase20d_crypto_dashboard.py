"""Fase 20D — painel do scanner cripto no dashboard.

Segue o padrão das fases 12B, 14, 15 e 17: a suíte não executa
JavaScript, então o contrato do front é verificado sobre o próprio
fonte. É rasteiro de propósito — pega remoção acidental de id,
troca de endpoint e regressão de encoding, que foram os defeitos
reais observados neste dashboard.
"""

from pathlib import Path


HTML = Path(
    "app/dashboard/templates/dashboard.html"
).read_text(encoding="utf-8")

JS = Path(
    "app/dashboard/static/js/dashboard.js"
).read_text(encoding="utf-8")

# O bloco do scanner cripto vive no fim do arquivo. Escopar as
# asserções negativas a ele evita quebrar esta fase quando outro
# painel, sem relação, precisar de um POST legítimo.
CRYPTO_JS = JS.split("const cryptoScannerState")[-1]

CSS = Path(
    "app/dashboard/static/css/dashboard.css"
).read_text(encoding="utf-8")


def test_panel_and_navigation_exist():
    assert 'id="crypto-scanner-panel"' in HTML
    assert 'href="#crypto-scanner-panel"' in HTML
    assert '"crypto-scanner-panel": "Scanner Cripto"' in JS


def test_panel_declares_every_id_the_script_writes():
    for element_id in (
        "crypto-scanner-pair",
        "crypto-scanner-opportunities",
        "crypto-scanner-rejected",
        "crypto-scanner-cycles",
        "crypto-scanner-failures",
        "crypto-scanner-venues",
        "crypto-scanner-last-status",
        "crypto-scanner-alerts",
        "crypto-scanner-status",
        "crypto-scanner-body",
        "crypto-scanner-rejected-body",
        "crypto-scanner-rejected-details",
        "crypto-scanner-refresh",
    ):
        assert f'id="{element_id}"' in HTML, element_id
        assert f'"{element_id}"' in JS, element_id


def test_reads_snapshot_and_status_only():
    assert '"/crypto/scanner/snapshot"' in JS
    assert '"/crypto/scanner/status"' in JS


def test_panel_never_triggers_collection():
    """Lição da Fase 17: coleta por acesso liga a carga upstream
    ao tráfego do dashboard, não ao intervalo configurado."""

    assert "force_refresh" not in CRYPTO_JS
    assert "/crypto/scanner/scan" not in CRYPTO_JS
    assert 'method: "POST"' not in CRYPTO_JS
    assert CRYPTO_JS.count('method: "GET"') >= 1


def test_disabled_state_is_rendered_as_configuration():
    """Desligado é configuração válida, não falha. É o estado
    atual em produção, então o painel não pode parecer quebrado."""

    assert 'payload.status === "DISABLED"' in JS
    assert "renderCryptoScannerDisabled" in JS


def test_auth_failure_has_its_own_message():
    """401/403 significam sessão sem MFA, não scanner com defeito.

    Evita repetir aqui o defeito de mensagem única já registrado
    para o login na seção 4 do CLAUDE.md.
    """

    assert "response.status === 401" in JS
    assert "response.status === 403" in JS
    assert "isAuthError" in JS
    assert "MFA" in JS


def test_venue_errors_are_surfaced():
    """"Nada encontrado" e "a OKX está fora" pedem ações
    diferentes, e a 20B só registra a segunda em
    last_venue_errors."""

    assert "last_venue_errors" in JS
    assert "cryptoScannerVenueAlerts" in JS


def test_status_failure_does_not_blank_the_panel():
    assert "STATUS_INDISPONÍVEL" in JS


def test_rejected_routes_show_reason_and_stage():
    assert "renderCryptoScannerRejected" in JS
    assert "CRYPTO_SCANNER_STAGE_LABEL" in JS

    for stage in (
        "freshness",
        "depth",
        "fees",
        "profitability",
        "modelling",
    ):
        assert f"{stage}:" in JS, stage


def test_breakdown_columns_are_present():
    for field in (
        "buy_vwap",
        "sell_vwap",
        "gross_profit",
        "total_fees",
        "total_reserves",
        "expected_net_profit",
        "expected_roi",
        "risk_status",
    ):
        assert field in JS, field


def test_panel_carries_no_execution_affordance():
    panel = HTML.split('id="crypto-scanner-panel"')[1]
    panel = panel.split("</section>")[0]

    for forbidden in (
        "Executar",
        "Enviar ordem",
        "submit_order",
        "<form",
        'type="submit"',
    ):
        assert forbidden not in panel, forbidden


def test_disclaimer_refuses_to_promise_profit():
    assert "crypto-scanner-disclaimer" in HTML
    assert "n&atilde;o s&atilde;o promessa de" in HTML


def test_alerts_do_not_reuse_the_green_radar_style():
    """Venue fora do ar pintada de verde comunicaria o oposto."""

    assert ".crypto-scanner-alerts" in CSS
    assert 'class="crypto-scanner-alerts"' in HTML


def test_new_css_classes_exist():
    for selector in (
        ".crypto-scanner-alerts",
        ".crypto-scanner-rejected",
        ".crypto-scanner-disclaimer",
    ):
        assert selector in CSS, selector


def test_dashboard_view_labels_are_not_mojibake():
    """Regressão real: DASHBOARD_VIEWS trazia "Vis?o Geral" e
    "Posi??es", e dashboard.js usa esse valor como título
    visível da página."""

    assert '"Visão Geral"' in JS
    assert '"Posições"' in JS
    assert "Vis?o" not in JS
    assert "Posi??es" not in JS
