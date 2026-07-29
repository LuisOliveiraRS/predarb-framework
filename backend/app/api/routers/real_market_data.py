from __future__ import annotations

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)
from fastapi.responses import HTMLResponse

from app.real_markets.service import (
    real_market_data_service,
    real_market_registry,
)


router = APIRouter(
    prefix="/real-markets",
    tags=["real-market-data-read-only"],
)


DASHBOARD_HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta
    name="viewport"
    content="width=device-width, initial-scale=1"
  >
  <title>PredArb | Núcleo de Dados de Mercado</title>

  <style>
    :root {
      color-scheme: dark;
      --bg: #090c0f;
      --panel: #151a20;
      --line: #2b333d;
      --text: #f5f7f9;
      --muted: #9ca9b5;
      --accent: #ff6a00;
      --good: #44c47d;
      --warning: #f6c453;
      --critical: #ff6b6b;
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(
          circle at top right,
          rgba(255, 106, 0, 0.16),
          transparent 35rem
        ),
        var(--bg);
      color: var(--text);
      font-family:
        Inter,
        ui-sans-serif,
        system-ui,
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;
    }

    main {
      width: min(1280px, calc(100% - 28px));
      margin: 0 auto;
      padding: 32px 0 56px;
    }

    header {
      display: flex;
      justify-content: space-between;
      gap: 20px;
      align-items: flex-start;
      margin-bottom: 22px;
    }

    h1,
    h2,
    p {
      margin-top: 0;
    }

    h1 {
      margin-bottom: 8px;
      font-size: clamp(30px, 5vw, 50px);
      letter-spacing: -0.04em;
    }

    h2 {
      margin-bottom: 14px;
      font-size: 18px;
    }

    .muted {
      color: var(--muted);
    }

    .actions,
    .badges {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }

    .badges {
      margin-bottom: 20px;
    }

    button,
    a.button {
      display: inline-flex;
      min-height: 42px;
      padding: 0 16px;
      align-items: center;
      justify-content: center;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: var(--panel);
      color: var(--text);
      font: inherit;
      text-decoration: none;
      cursor: pointer;
    }

    button.primary {
      border-color: var(--accent);
      background: var(--accent);
      color: #111;
      font-weight: 760;
    }

    button:disabled {
      opacity: 0.55;
      cursor: wait;
    }

    .badge {
      padding: 8px 11px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(68, 196, 125, 0.08);
      color: var(--good);
      font-size: 12px;
    }

    .grid {
      display: grid;
      grid-template-columns:
        repeat(auto-fit, minmax(160px, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }

    .card,
    .panel {
      border: 1px solid var(--line);
      border-radius: 16px;
      background: rgba(21, 26, 32, 0.94);
      box-shadow:
        0 18px 55px rgba(0, 0, 0, 0.18);
    }

    .card {
      padding: 16px;
    }

    .label {
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 12px;
    }

    .value {
      font-size: 24px;
      font-weight: 780;
      letter-spacing: -0.04em;
    }

    .panel {
      margin-bottom: 18px;
      padding: 20px;
      overflow: hidden;
    }

    .table-wrap {
      overflow-x: auto;
    }

    table {
      width: 100%;
      min-width: 1100px;
      border-collapse: collapse;
    }

    th,
    td {
      padding: 12px 10px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      white-space: nowrap;
      font-size: 13px;
    }

    th {
      color: var(--muted);
      font-weight: 650;
    }

    .healthy,
    .open {
      color: var(--good);
      font-weight: 760;
    }

    .degraded,
    .unknown {
      color: var(--warning);
      font-weight: 760;
    }

    .unhealthy,
    .closed,
    .suspended {
      color: var(--critical);
      font-weight: 760;
    }

    .footer {
      color: var(--muted);
      font-size: 12px;
    }

    @media (max-width: 760px) {
      header {
        flex-direction: column;
      }

      .actions {
        width: 100%;
      }

      button,
      a.button {
        flex: 1;
      }
    }
  </style>
</head>

<body>
  <main>
    <header>
      <div>
        <h1>Núcleo de Dados de Mercado</h1>

        <p class="muted">
          Arquitetura consolidada para conectores reais somente leitura.
        </p>
      </div>

      <div class="actions">
        <button
          id="refreshButton"
          class="primary"
          type="button"
        >
          Atualizar dados
        </button>

        <button
          id="reloadButton"
          type="button"
        >
          Recarregar painel
        </button>
      </div>
    </header>

    <section class="badges">
      <span class="badge">
        Dados de mercado somente leitura
      </span>

      <span class="badge">
        Nenhum conector pode enviar ordens
      </span>

      <span class="badge">
        Atualização manual
      </span>

      <span class="badge">
        Execução real bloqueada
      </span>
    </section>

    <div
      id="phase9aConfirmationToken"
      hidden
      data-refresh-confirmation="REFRESH-REAL-MARKET-DATA"
    ></div>

    <section
      id="summaryGrid"
      class="grid"
    ></section>

    <section class="panel">
      <h2>Conectores registrados</h2>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Conector</th>
              <th>Nome</th>
              <th>Saúde</th>
              <th>Somente leitura</th>
              <th>Capacidades</th>
              <th>Mensagem</th>
            </tr>
          </thead>

          <tbody id="connectorsBody"></tbody>
        </table>
      </div>
    </section>

    <section class="panel">
      <h2>Mercados normalizados</h2>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Conector</th>
              <th>Mercado</th>
              <th>Título</th>
              <th>Status</th>
              <th>Categoria</th>
              <th>Fechamento</th>
              <th>Outcomes</th>
            </tr>
          </thead>

          <tbody id="marketsBody"></tbody>
        </table>
      </div>
    </section>

    <section class="panel">
      <h2>Snapshots em cache</h2>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Chave</th>
              <th>Capturado em</th>
              <th>Idade</th>
              <th>Stale</th>
              <th>Quotes</th>
            </tr>
          </thead>

          <tbody id="snapshotsBody"></tbody>
        </table>
      </div>
    </section>

    <p
      id="lastUpdate"
      class="footer"
    >
      Carregando dados...
    </p>
  </main>

  <script>
    function ensureSafe(payload) {
      for (const field of [
        "paper_execution_authorized",
        "live_authorization",
        "execution_authorized",
        "live_execution",
        "financial_execution",
        "next_step_authorized"
      ]) {
        if (payload[field] !== false) {
          throw new Error(
            `Guarda de segurança inválida: ${field}`
          );
        }
      }

      if (
        payload.read_only !== true
        || payload.market_data_only !== true
      ) {
        throw new Error(
          "Payload não está restrito a dados de mercado."
        );
      }
    }

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function css(value) {
      return String(
        value || ""
      ).toLowerCase();
    }

    function dateTime(value) {
      if (!value) {
        return "-";
      }

      const parsed = new Date(value);

      if (Number.isNaN(parsed.getTime())) {
        return escapeHtml(value);
      }

      return parsed.toLocaleString("pt-BR");
    }

    function card(label, value, className = "") {
      return `
        <article class="card">
          <div class="label">
            ${escapeHtml(label)}
          </div>

          <div class="value ${className}">
            ${escapeHtml(value)}
          </div>
        </article>
      `;
    }

    async function fetchJson(path) {
      const response = await fetch(
        path,
        {
          cache: "no-store"
        }
      );

      if (!response.ok) {
        throw new Error(
          `HTTP ${response.status}`
        );
      }

      const payload = await response.json();
      ensureSafe(payload);
      return payload;
    }

    async function loadDashboard() {
      const [
        health,
        connectors,
        markets,
        snapshots
      ] = await Promise.all([
        fetchJson("/real-markets/health"),
        fetchJson("/real-markets/connectors"),
        fetchJson("/real-markets/markets?limit=100"),
        fetchJson("/real-markets/snapshots/latest")
      ]);

      document.getElementById(
        "summaryGrid"
      ).innerHTML = [
        card(
          "Estado",
          health.status || "-",
          css(health.status)
        ),
        card(
          "Conectores",
          Number(
            health.registered_connectors || 0
          ).toFixed(0)
        ),
        card(
          "Conectores saudáveis",
          Number(
            health.healthy_connectors || 0
          ).toFixed(0)
        ),
        card(
          "Mercados",
          Number(
            markets.count || 0
          ).toFixed(0)
        ),
        card(
          "Snapshots",
          Number(
            snapshots.count || 0
          ).toFixed(0)
        ),
        card(
          "Atualizações",
          Number(
            health.refresh_count || 0
          ).toFixed(0)
        ),
        card(
          "Falhas",
          Number(
            health.refresh_failures || 0
          ).toFixed(0)
        ),
        card(
          "TTL do cache",
          `${Number(
            health.cache_ttl_seconds || 0
          ).toFixed(0)}s`
        )
      ].join("");

      const connectorsBody = document.getElementById(
        "connectorsBody"
      );

      connectorsBody.innerHTML = (
        connectors.connectors || []
      ).map(
        (item) => `
          <tr>
            <td>${escapeHtml(item.connector_id)}</td>
            <td>${escapeHtml(item.name)}</td>
            <td class="${
              item.healthy ? "healthy" : "unhealthy"
            }">
              ${item.healthy ? "HEALTHY" : "UNHEALTHY"}
            </td>
            <td>${item.read_only === true ? "SIM" : "NÃO"}</td>
            <td>
              ${escapeHtml(
                (item.capabilities || []).join(", ")
              )}
            </td>
            <td>${escapeHtml(item.message)}</td>
          </tr>
        `
      ).join("");

      const marketsBody = document.getElementById(
        "marketsBody"
      );

      marketsBody.innerHTML = (
        markets.markets || []
      ).map(
        (item) => `
          <tr>
            <td>${escapeHtml(item.connector_id)}</td>
            <td>${escapeHtml(item.market_id)}</td>
            <td>${escapeHtml(item.title)}</td>
            <td class="${css(item.status)}">
              ${escapeHtml(item.status)}
            </td>
            <td>${escapeHtml(item.category || "-")}</td>
            <td>${dateTime(item.close_time)}</td>
            <td>
              ${escapeHtml(
                (item.outcomes || [])
                  .map((outcome) => outcome.label)
                  .join(" / ")
              )}
            </td>
          </tr>
        `
      ).join("");

      const snapshotsBody = document.getElementById(
        "snapshotsBody"
      );

      if (!(snapshots.snapshots || []).length) {
        snapshotsBody.innerHTML = `
          <tr>
            <td colspan="5" class="muted">
              Nenhum snapshot em cache.
            </td>
          </tr>
        `;
      } else {
        snapshotsBody.innerHTML = (
          snapshots.snapshots || []
        ).map(
          (item) => `
            <tr>
              <td>${escapeHtml(item.key)}</td>
              <td>${dateTime(item.captured_at)}</td>
              <td>
                ${Number(
                  item.cache_age_seconds || 0
                ).toFixed(2)}s
              </td>
              <td>${item.stale ? "SIM" : "NÃO"}</td>
              <td>
                ${escapeHtml(
                  (item.quotes || [])
                    .map(
                      (quote) => (
                        `${quote.outcome_id}: `
                        + `bid ${quote.bid ?? "-"} / `
                        + `ask ${quote.ask ?? "-"}`
                      )
                    )
                    .join(" | ")
                )}
              </td>
            </tr>
          `
        ).join("");
      }

      document.getElementById(
        "lastUpdate"
      ).textContent = (
        "Última atualização do painel: "
        + new Date().toLocaleString("pt-BR")
        + " | Dados de mercado somente leitura"
      );
    }

    async function refreshData() {
      const confirmed = window.confirm(
        "Atualizar os snapshots de dados de mercado?"
      );

      if (!confirmed) {
        return;
      }

      const button = document.getElementById(
        "refreshButton"
      );

      button.disabled = true;
      button.textContent = "Atualizando...";

      try {
        const tokenElement = document.getElementById(
          "phase9aConfirmationToken"
        );

        const confirmation = (
          tokenElement.dataset.refreshConfirmation
        );

        const response = await fetch(
          "/real-markets/refresh"
          + `?confirm=${encodeURIComponent(confirmation)}`
          + "&limit=50",
          {
            method: "POST"
          }
        );

        if (!response.ok) {
          throw new Error(
            `HTTP ${response.status}: `
            + await response.text()
          );
        }

        const payload = await response.json();
        ensureSafe(payload);
        await loadDashboard();

      } catch (error) {
        window.alert(
          "Falha na atualização: "
          + error.message
        );

      } finally {
        button.disabled = false;
        button.textContent = "Atualizar dados";
      }
    }

    document.getElementById(
      "refreshButton"
    ).addEventListener(
      "click",
      refreshData
    );

    document.getElementById(
      "reloadButton"
    ).addEventListener(
      "click",
      loadDashboard
    );

    loadDashboard();
    setInterval(loadDashboard, 15000);
  </script>
</body>
</html>
"""


def _safe_flags() -> dict:
    return {
        "market_data_only": True,
        "read_only": True,
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "next_step_authorized": False,
    }


@router.get("/health")
async def real_market_health():
    return await real_market_data_service.health()


@router.get("/connectors")
async def real_market_connectors():
    health = (
        await real_market_data_service
        .connector_health()
    )

    return {
        "count": len(health),
        "connectors": health,
        **_safe_flags(),
    }


@router.get("/markets")
async def real_market_markets(
    connector_id: str | None = Query(
        default=None
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
    ),
):
    try:
        markets = await (
            real_market_data_service
            .list_markets(
                connector_id=connector_id,
                limit=limit,
            )
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    return {
        "count": len(markets),
        "connector_id": connector_id,
        "markets": [
            item.to_dict()
            for item in markets
        ],
        **_safe_flags(),
    }


@router.get(
    "/markets/{connector_id}/{market_id}"
)
async def real_market_market_snapshot(
    connector_id: str,
    market_id: str,
    force_refresh: bool = Query(
        default=False
    ),
):
    try:
        snapshot = await (
            real_market_data_service
            .get_snapshot(
                connector_id=connector_id,
                market_id=market_id,
                force_refresh=force_refresh,
            )
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return {
        "snapshot": snapshot.to_dict(),
        **_safe_flags(),
    }


@router.get("/snapshots/latest")
async def real_market_latest_snapshots():
    snapshots = (
        real_market_data_service
        .latest_snapshots()
    )

    return {
        "count": len(snapshots),
        "snapshots": snapshots,
        **_safe_flags(),
    }


@router.post("/refresh")
async def real_market_refresh(
    confirm: str = Query(...),
    connector_id: str | None = Query(
        default=None
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=250,
    ),
):
    if (
        confirm
        != "REFRESH-REAL-MARKET-DATA"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Confirmação inválida. Use "
                "REFRESH-REAL-MARKET-DATA."
            ),
        )

    try:
        return await (
            real_market_data_service
            .refresh(
                connector_id=connector_id,
                limit=limit,
            )
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


@router.get(
    "/dashboard",
    response_class=HTMLResponse,
)
async def real_market_dashboard():
    return HTMLResponse(
        content=DASHBOARD_HTML,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-PredArb-Market-Data-Only": "true",
            "X-PredArb-Live-Authorization": "false",
            "X-PredArb-Financial-Execution": "false",
            "X-PredArb-Next-Step-Authorization": "false",
        },
    )


@router.get("/architecture")
async def real_market_architecture():
    return {
        "phase": "9A",
        "name": (
            "Real Market Data Core"
        ),
        "purpose": (
            "Normalizar dados de mercado e "
            "padronizar conectores somente leitura."
        ),
        "components": [
            "normalized_market_models",
            "read_only_connector_contract",
            "connector_registry",
            "snapshot_cache",
            "manual_refresh",
            "market_data_dashboard",
        ],
        "registered_connectors": (
            real_market_registry
            .descriptors()
        ),
        "deferred_to_next_phases": [
            "real_external_connector",
            "market_matching",
            "fee_and_slippage_model",
            "shadow_execution",
            "risk_engine",
            "order_execution",
        ],
        **_safe_flags(),
    }
