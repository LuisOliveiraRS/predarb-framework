from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import (
    HTMLResponse,
    Response,
)

from app.paper.operations_center import (
    paper_operations_center,
)


router = APIRouter(
    prefix="/paper/operations",
    tags=["paper-operations-center"],
)


DASHBOARD_HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta
    name="viewport"
    content="width=device-width, initial-scale=1"
  >
  <title>PredArb | Centro de Operações Paper</title>

  <style>
    :root {
      color-scheme: dark;
      --bg: #090c0f;
      --panel: #151a20;
      --line: #2b333d;
      --text: #f5f7f9;
      --muted: #9ca9b5;
      --accent: #ff6a00;
      --healthy: #44c47d;
      --warning: #f6c453;
      --critical: #ff6b6b;
      --info: #6ab7ff;
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
          rgba(255, 106, 0, 0.15),
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
      align-items: flex-start;
      justify-content: space-between;
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

    button,
    a.button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 42px;
      padding: 0 16px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: var(--panel);
      color: var(--text);
      font: inherit;
      text-decoration: none;
      cursor: pointer;
    }

    button {
      border-color: var(--accent);
      background: var(--accent);
      color: #111;
      font-weight: 760;
    }

    button:disabled {
      opacity: 0.55;
      cursor: wait;
    }

    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }

    .safety {
      display: flex;
      flex-wrap: wrap;
      gap: 9px;
      margin-bottom: 20px;
    }

    .badge {
      padding: 8px 11px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(68, 196, 125, 0.08);
      color: var(--healthy);
      font-size: 12px;
    }

    .hero {
      display: grid;
      grid-template-columns: 220px 1fr;
      gap: 16px;
      margin-bottom: 18px;
    }

    .status-card,
    .panel,
    .metric,
    .module {
      border: 1px solid var(--line);
      border-radius: 16px;
      background: rgba(21, 26, 32, 0.94);
      box-shadow:
        0 18px 55px rgba(0, 0, 0, 0.18);
    }

    .status-card {
      display: grid;
      min-height: 210px;
      place-items: center;
      padding: 20px;
      text-align: center;
    }

    .status-value {
      font-size: 25px;
      font-weight: 820;
      letter-spacing: 0.08em;
    }

    .score {
      margin-top: 8px;
      font-size: 56px;
      font-weight: 820;
      letter-spacing: -0.06em;
    }

    .panel {
      padding: 20px;
    }

    .metrics {
      display: grid;
      grid-template-columns:
        repeat(auto-fit, minmax(150px, 1fr));
      gap: 12px;
    }

    .metric {
      padding: 15px;
    }

    .metric-label {
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 12px;
    }

    .metric-value {
      font-size: 25px;
      font-weight: 770;
      letter-spacing: -0.04em;
    }

    .modules {
      display: grid;
      grid-template-columns:
        repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
    }

    .module {
      display: grid;
      gap: 14px;
      padding: 17px;
    }

    .module-title {
      font-weight: 760;
    }

    .module a {
      justify-self: start;
    }

    .runtime-line {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.02);
    }

    .healthy {
      color: var(--healthy);
    }

    .warning {
      color: var(--warning);
    }

    .critical {
      color: var(--critical);
    }

    .no-data,
    .unknown {
      color: var(--info);
    }

    .footer {
      margin-top: 18px;
      color: var(--muted);
      font-size: 12px;
    }

    @media (max-width: 760px) {
      header {
        flex-direction: column;
      }

      .hero {
        grid-template-columns: 1fr;
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
        <h1>Centro de Operações Paper</h1>
        <p class="muted">
          Visão unificada de desempenho, monitor, incidentes e runtime.
        </p>
      </div>

      <div class="actions">
        <button
          id="refreshButton"
          type="button"
        >
          Atualizar
        </button>

        <a
          class="button"
          href="/paper/operations/export.json"
        >
          Exportar JSON
        </a>
      </div>
    </header>

    <section class="safety">
      <span class="badge">
        Execução live bloqueada
      </span>
      <span class="badge">
        Execução financeira bloqueada
      </span>
      <span class="badge">
        Runtime com início manual
      </span>
      <span class="badge">
        Centro somente leitura
      </span>
    </section>

    <section class="hero">
      <article class="status-card">
        <div>
          <div id="overallStatus" class="status-value">
            CARREGANDO
          </div>
          <div id="monitorScore" class="score">
            --
          </div>
          <div class="muted">
            Score do monitor
          </div>
        </div>
      </article>

      <article class="panel">
        <h2>Indicadores consolidados</h2>
        <div id="metrics" class="metrics"></div>
      </article>
    </section>

    <section class="panel">
      <h2>Estado do runtime</h2>
      <div id="runtimeLine" class="runtime-line">
        Carregando...
      </div>
    </section>

    <section class="panel">
      <h2>Módulos operacionais</h2>

      <div class="modules">
        <article class="module">
          <div>
            <div class="module-title">
              Desempenho
            </div>
            <div class="muted">
              Equity, sessões, trades e retorno.
            </div>
          </div>

          <a
            class="button"
            href="/paper/performance/dashboard"
          >
            Abrir desempenho
          </a>
        </article>

        <article class="module">
          <div>
            <div class="module-title">
              Monitor
            </div>
            <div class="muted">
              Score, alertas e saúde operacional.
            </div>
          </div>

          <a
            class="button"
            href="/paper/performance/monitor/dashboard"
          >
            Abrir monitor
          </a>
        </article>

        <article class="module">
          <div>
            <div class="module-title">
              Incidentes
            </div>
            <div class="muted">
              Journal, resolução e reconhecimento.
            </div>
          </div>

          <a
            class="button"
            href="/paper/performance/incidents/dashboard"
          >
            Abrir incidentes
          </a>
        </article>

        <article class="module">
          <div>
            <div class="module-title">
              Runtime
            </div>
            <div class="muted">
              Captura periódica com controle manual.
            </div>
          </div>

          <a
            class="button"
            href="/paper/performance/incidents/runtime/dashboard"
          >
            Abrir runtime
          </a>
        </article>
      </div>
    </section>

    <p id="lastUpdate" class="footer">
      Carregando dados...
    </p>
  </main>

  <script>
    const integer = new Intl.NumberFormat(
      "pt-BR",
      {
        maximumFractionDigits: 0
      }
    );

    const money = new Intl.NumberFormat(
      "pt-BR",
      {
        style: "currency",
        currency: "BRL"
      }
    );

    function ensureSafe(payload) {
      if (
        payload.execution_authorized !== false
        || payload.live_execution !== false
        || payload.financial_execution !== false
        || payload.read_only !== true
      ) {
        throw new Error(
          "Guardas de segurança inválidas."
        );
      }
    }

    function metric(label, value) {
      return `
        <article class="metric">
          <div class="metric-label">${label}</div>
          <div class="metric-value">${value}</div>
        </article>
      `;
    }

    function statusClass(status) {
      const value = String(
        status || "UNKNOWN"
      ).toLowerCase();

      if (value === "healthy") {
        return "healthy";
      }

      if (value === "warning") {
        return "warning";
      }

      if (value === "critical") {
        return "critical";
      }

      if (value === "no_data") {
        return "no-data";
      }

      return "unknown";
    }

    function render(payload) {
      ensureSafe(payload);

      const diagnostics = payload.diagnostics || {};
      const performance = payload.performance || {};
      const runtime = payload.runtime || {};

      const status = payload.status || "UNKNOWN";
      const statusElement = document.getElementById(
        "overallStatus"
      );

      statusElement.textContent = status;
      statusElement.className = (
        "status-value "
        + statusClass(status)
      );

      document.getElementById(
        "monitorScore"
      ).textContent = diagnostics.monitor_score ?? "--";

      document.getElementById(
        "metrics"
      ).innerHTML = [
        metric(
          "Relatórios",
          integer.format(
            Number(diagnostics.reports || 0)
          )
        ),
        metric(
          "Ciclos Paper",
          integer.format(
            Number(diagnostics.cycles || 0)
          )
        ),
        metric(
          "Trades Paper",
          integer.format(
            Number(diagnostics.trades || 0)
          )
        ),
        metric(
          "Resultado acumulado",
          money.format(
            Number(
              performance.cumulative_equity_delta || 0
            )
          )
        ),
        metric(
          "Incidentes ativos",
          integer.format(
            Number(
              diagnostics.active_incidents || 0
            )
          )
        ),
        metric(
          "Falhas do runtime",
          integer.format(
            Number(
              diagnostics.runtime_failures || 0
            )
          )
        )
      ].join("");

      document.getElementById(
        "runtimeLine"
      ).innerHTML = `
        <div>
          <strong>
            ${runtime.running ? "EXECUTANDO" : "PARADO"}
          </strong>
          <div class="muted">
            Intervalo:
            ${Number(runtime.interval_seconds || 0)}s
          </div>
        </div>
        <div>
          ${integer.format(
            Number(runtime.total_cycles || 0)
          )}
          ciclos
        </div>
      `;
    }

    async function refresh() {
      const button = document.getElementById(
        "refreshButton"
      );

      button.disabled = true;
      button.textContent = "Atualizando...";

      try {
        const response = await fetch(
          "/paper/operations/snapshot",
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
        render(payload);

        document.getElementById(
          "lastUpdate"
        ).textContent = (
          "Última atualização: "
          + new Date().toLocaleString("pt-BR")
          + " | Centro somente leitura"
        );
      } catch (error) {
        document.getElementById(
          "lastUpdate"
        ).textContent = (
          "Falha ao atualizar: "
          + error.message
        );
      } finally {
        button.disabled = false;
        button.textContent = "Atualizar";
      }
    }

    document.getElementById(
      "refreshButton"
    ).addEventListener(
      "click",
      refresh
    );

    refresh();
    setInterval(refresh, 10000);
  </script>
</body>
</html>
"""


def _snapshot():
    return paper_operations_center.snapshot()


@router.get("/health")
async def paper_operations_health():
    snapshot = _snapshot()

    return {
        "status": snapshot["status"],
        "generated_at": snapshot[
            "generated_at"
        ],
        "monitor_score": snapshot[
            "diagnostics"
        ]["monitor_score"],
        "manual_start_required": True,
        "read_only": True,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
    }


@router.get("/snapshot")
async def paper_operations_snapshot():
    return _snapshot()


@router.get(
    "/dashboard",
    response_class=HTMLResponse,
)
async def paper_operations_dashboard():
    return HTMLResponse(
        content=DASHBOARD_HTML,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-PredArb-Financial-Execution": "false",
        },
    )


@router.get("/export.json")
async def paper_operations_export_json():
    payload = json.dumps(
        _snapshot(),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )

    return Response(
        content=payload,
        media_type="application/json",
        headers={
            "Content-Disposition": (
                "attachment; "
                'filename="predarb-paper-operations.json"'
            ),
            "Cache-Control": "no-store",
            "X-PredArb-Financial-Execution": "false",
        },
    )
