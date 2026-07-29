from __future__ import annotations

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)
from fastapi.responses import HTMLResponse

from app.real_markets.economics import (
    economic_opportunity_engine,
)


router = APIRouter(
    prefix="/real-markets/economics",
    tags=[
        "real-market-economic-analysis"
    ],
)


DASHBOARD_HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta
    name="viewport"
    content="width=device-width, initial-scale=1"
  >
  <title>PredArb | Motor Econômico de Oportunidades</title>

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
      width: min(1320px, calc(100% - 28px));
      margin: 0 auto;
      padding: 32px 0 56px;
    }

    header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 20px;
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
    .badges,
    .controls {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }

    .badges {
      margin-bottom: 20px;
    }

    button,
    a.button,
    input {
      min-height: 42px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: var(--panel);
      color: var(--text);
      font: inherit;
    }

    button,
    a.button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 0 16px;
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

    input {
      padding: 0 12px;
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
    .panel,
    .opportunity {
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
    }

    .opportunity-list {
      display: grid;
      gap: 12px;
    }

    .opportunity {
      padding: 16px;
      box-shadow: none;
    }

    .opportunity-head {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 12px;
    }

    .profit {
      font-size: 28px;
      font-weight: 800;
    }

    .profitable {
      color: var(--good);
    }

    .not_profitable {
      color: var(--warning);
    }

    .rejected,
    .error {
      color: var(--critical);
    }

    .direction-grid {
      display: grid;
      grid-template-columns:
        repeat(auto-fit, minmax(270px, 1fr));
      gap: 10px;
    }

    .direction {
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: rgba(0, 0, 0, 0.18);
    }

    .direction strong {
      display: block;
      margin-bottom: 8px;
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
        <h1>Motor Econômico de Oportunidades</h1>

        <p class="muted">
          Custo, liquidez, taxas, slippage e retorno líquido simulado.
        </p>
      </div>

      <div class="actions">
        <button
          id="evaluateButton"
          class="primary"
          type="button"
        >
          Avaliar pares
        </button>

        <a
          class="button"
          href="/real-markets/matching/dashboard"
        >
          Correspondências
        </a>

        <a
          class="button"
          href="/real-markets/dashboard"
        >
          Dados de mercado
        </a>
      </div>
    </header>

    <section class="badges">
      <span class="badge">
        Análise econômica somente
      </span>

      <span class="badge">
        Shadow mode
      </span>

      <span class="badge">
        Nenhuma ordem disponível
      </span>

      <span class="badge">
        Execução real e financeira bloqueada
      </span>
    </section>

    <section class="panel">
      <h2>Parâmetros de avaliação</h2>

      <div class="controls">
        <label>
          <input
            id="forceRefresh"
            type="checkbox"
          >
          Forçar atualização externa
        </label>
      </div>
    </section>

    <section
      id="summaryGrid"
      class="grid"
    ></section>

    <section class="panel">
      <h2>Pares confirmados avaliados</h2>

      <div
        id="opportunityList"
        class="opportunity-list"
      ></div>
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
        payload.economic_analysis_only !== true
        || payload.shadow_only !== true
        || payload.order_submission_available !== false
      ) {
        throw new Error(
          "Payload fora do escopo econômico simulado."
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

    function money(value) {
      return Number(
        value || 0
      ).toLocaleString(
        "pt-BR",
        {
          minimumFractionDigits: 2,
          maximumFractionDigits: 8
        }
      );
    }

    function percentage(value) {
      return (
        Number(value || 0)
        * 100
      ).toLocaleString(
        "pt-BR",
        {
          minimumFractionDigits: 2,
          maximumFractionDigits: 4
        }
      ) + "%";
    }

    function renderDirection(item) {
      const legs = item.legs || [];

      return `
        <article class="direction">
          <strong class="${css(item.status)}">
            ${escapeHtml(item.direction || "-")}
            · ${escapeHtml(item.status || "-")}
          </strong>

          <div class="muted">
            ${legs.map(
              (leg) => (
                `${leg.connector_id} / `
                + `${leg.canonical_outcome} `
                + `ask ${leg.ask ?? "-"} `
                + `size ${leg.ask_size ?? "-"}`
              )
            ).join("<br>")}
          </div>

          <p>
            Quantidade simulada:
            <strong>${money(item.simulated_quantity)}</strong>
            <br>
            Custo bruto:
            <strong>${money(item.raw_cost)}</strong>
            <br>
            Taxas:
            <strong>${money(item.fee_cost)}</strong>
            <br>
            Slippage:
            <strong>${money(item.slippage_cost)}</strong>
            <br>
            Lucro líquido:
            <strong class="${css(item.status)}">
              ${money(item.net_profit)}
            </strong>
            <br>
            Edge líquido:
            <strong>${percentage(item.net_edge)}</strong>
          </p>

          <div class="muted">
            ${(item.reason_codes || []).join(", ") || "Sem bloqueios"}
          </div>
        </article>
      `;
    }

    function render(payload) {
      ensureSafe(payload);

      document.getElementById(
        "summaryGrid"
      ).innerHTML = [
        card(
          "Estado",
          payload.status || "-"
        ),
        card(
          "Pares confirmados",
          Number(
            payload.confirmed_matches || 0
          ).toFixed(0)
        ),
        card(
          "Lucrativos",
          Number(
            payload.profitable || 0
          ).toFixed(0),
          "profitable"
        ),
        card(
          "Não lucrativos",
          Number(
            payload.not_profitable || 0
          ).toFixed(0),
          "not_profitable"
        ),
        card(
          "Rejeitados",
          Number(
            payload.rejected || 0
          ).toFixed(0),
          "rejected"
        ),
        card(
          "Idade máxima",
          `${
            (
              payload.configuration
              || {}
            ).max_snapshot_age_seconds
            || 0
          }s`
        ),
        card(
          "Edge mínimo",
          percentage(
            (
              payload.configuration
              || {}
            ).min_net_edge
          )
        ),
        card(
          "Quantidade máxima",
          money(
            (
              payload.configuration
              || {}
            ).max_simulated_quantity
          )
        )
      ].join("");

      const container = document.getElementById(
        "opportunityList"
      );

      const opportunities = payload.opportunities || [];

      if (!opportunities.length) {
        container.innerHTML = `
          <p class="muted">
            Nenhum par manual confirmado. Use o dashboard de
            correspondências para confirmar mercados realmente equivalentes.
          </p>
        `;
        return;
      }

      container.innerHTML = opportunities.map(
        (item) => {
          const best = item.best_direction || {};

          return `
            <article class="opportunity">
              <div class="opportunity-head">
                <div>
                  <strong class="${css(item.status)}">
                    ${escapeHtml(item.status)}
                  </strong>

                  <div class="muted">
                    ${escapeHtml(item.left_key)}
                    ↔
                    ${escapeHtml(item.right_key)}
                  </div>
                </div>

                <div class="profit ${css(item.status)}">
                  ${money(best.net_profit)}
                </div>
              </div>

              <div class="direction-grid">
                ${(item.directions || [])
                  .map(renderDirection)
                  .join("")}
              </div>
            </article>
          `;
        }
      ).join("");
    }

    async function evaluate() {
      const button = document.getElementById(
        "evaluateButton"
      );

      button.disabled = true;
      button.textContent = "Avaliando...";

      try {
        const forceRefresh = document.getElementById(
          "forceRefresh"
        ).checked;

        const response = await fetch(
          "/real-markets/economics/opportunities"
          + `?force_refresh=${forceRefresh}`,
          {
            cache: "no-store"
          }
        );

        if (!response.ok) {
          throw new Error(
            `HTTP ${response.status}: `
            + await response.text()
          );
        }

        const payload = await response.json();
        render(payload);

        document.getElementById(
          "lastUpdate"
        ).textContent = (
          "Última avaliação: "
          + new Date().toLocaleString("pt-BR")
          + " | Nenhuma execução foi autorizada"
        );

      } catch (error) {
        document.getElementById(
          "lastUpdate"
        ).textContent = (
          "Falha na avaliação: "
          + error.message
        );

      } finally {
        button.disabled = false;
        button.textContent = "Avaliar pares";
      }
    }

    document.getElementById(
      "evaluateButton"
    ).addEventListener(
      "click",
      evaluate
    );

    evaluate();
  </script>
</body>
</html>
"""


def _safe_flags() -> dict:
    return {
        "economic_analysis_only": True,
        "shadow_only": True,
        "market_data_only": True,
        "read_only_market_access": True,
        "order_submission_available": False,
        "automatic_execution_authorized": False,
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "next_step_authorized": False,
    }


@router.get("/health")
async def economic_health():
    return (
        economic_opportunity_engine
        .health()
    )


@router.get("/configuration")
async def economic_configuration():
    return {
        "configuration": (
            economic_opportunity_engine
            .configuration
            .to_dict()
        ),
        "supported_structure": (
            "BINARY_YES_NO"
        ),
        "payout_assumption_per_pair": 1.0,
        "manual_match_required": True,
        **_safe_flags(),
    }


@router.get("/opportunities")
async def economic_opportunities(
    force_refresh: bool = Query(
        default=False
    ),
):
    return await (
        economic_opportunity_engine
        .evaluate_confirmed_matches(
            force_refresh=force_refresh
        )
    )


@router.get("/matches/{match_id}")
async def economic_match(
    match_id: str,
    force_refresh: bool = Query(
        default=False
    ),
):
    try:
        return await (
            economic_opportunity_engine
            .evaluate_match(
                match_id=match_id,
                force_refresh=(
                    force_refresh
                ),
            )
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


@router.get("/preview")
async def economic_preview(
    left_connector_id: str = Query(...),
    left_market_id: str = Query(...),
    right_connector_id: str = Query(...),
    right_market_id: str = Query(...),
    force_refresh: bool = Query(
        default=False
    ),
):
    try:
        return await (
            economic_opportunity_engine
            .evaluate_pair(
                left_key=(
                    f"{left_connector_id}:"
                    f"{left_market_id}"
                ),
                right_key=(
                    f"{right_connector_id}:"
                    f"{right_market_id}"
                ),
                source=(
                    "UNCONFIRMED_PREVIEW"
                ),
                force_refresh=(
                    force_refresh
                ),
            )
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


@router.get(
    "/dashboard",
    response_class=HTMLResponse,
)
async def economic_dashboard():
    return HTMLResponse(
        content=DASHBOARD_HTML,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-PredArb-Economic-Analysis-Only": "true",
            "X-PredArb-Order-Submission": "false",
            "X-PredArb-Live-Authorization": "false",
            "X-PredArb-Financial-Execution": "false",
            "X-PredArb-Next-Step-Authorization": "false",
        },
    )


@router.get("/architecture")
async def economic_architecture():
    return {
        "phase": "9D",
        "name": (
            "Economic Opportunity Engine"
        ),
        "components": [
            "confirmed_match_reader",
            "snapshot_freshness_guard",
            "binary_outcome_mapper",
            "best_ask_cost_model",
            "top_level_liquidity_limit",
            "configurable_fee_estimate",
            "configurable_slippage_estimate",
            "gross_and_net_profit",
            "shadow_opportunity_ranking",
        ],
        "supported_structure": (
            "BINARY_YES_NO"
        ),
        "manual_match_required": True,
        "automatic_execution_authorized": False,
        "explicitly_excluded": [
            "order_creation",
            "order_cancellation",
            "wallet_access",
            "balance_access",
            "private_keys",
            "financial_authorization",
            "automatic_pair_activation",
        ],
        **_safe_flags(),
    }
