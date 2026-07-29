from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.paper.performance_monitor import (
    PaperPerformanceMonitor,
)


router = APIRouter(
    prefix="/paper/performance/monitor",
    tags=["paper-performance-monitor"],
)


MONITOR_HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta
    name="viewport"
    content="width=device-width, initial-scale=1"
  >
  <title>PredArb | Monitor Paper</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0a0d10;
      --panel: #151a20;
      --line: #2a333d;
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
          rgba(255, 106, 0, 0.14),
          transparent 34rem
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
      width: min(1200px, calc(100% - 28px));
      margin: 0 auto;
      padding: 32px 0 56px;
    }

    header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 20px;
      margin-bottom: 24px;
    }

    h1,
    h2,
    p {
      margin-top: 0;
    }

    h1 {
      margin-bottom: 8px;
      font-size: clamp(30px, 5vw, 48px);
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
    a {
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
      font-weight: 750;
    }

    .actions {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }

    .hero {
      display: grid;
      grid-template-columns: 220px 1fr;
      gap: 18px;
      margin-bottom: 18px;
    }

    .score,
    .panel {
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(21, 26, 32, 0.94);
      box-shadow:
        0 18px 55px rgba(0, 0, 0, 0.18);
    }

    .score {
      display: grid;
      min-height: 210px;
      place-items: center;
      padding: 20px;
      text-align: center;
    }

    .score-number {
      font-size: 72px;
      font-weight: 800;
      letter-spacing: -0.06em;
    }

    .score-status {
      font-size: 14px;
      font-weight: 750;
      text-transform: uppercase;
      letter-spacing: 0.1em;
    }

    .panel {
      padding: 20px;
    }

    .stats {
      display: grid;
      grid-template-columns:
        repeat(auto-fit, minmax(150px, 1fr));
      gap: 12px;
    }

    .stat {
      padding: 15px;
      border: 1px solid var(--line);
      border-radius: 13px;
      background: rgba(255, 255, 255, 0.02);
    }

    .stat-label {
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 12px;
    }

    .stat-value {
      font-size: 23px;
      font-weight: 750;
    }

    .alerts {
      display: grid;
      gap: 12px;
    }

    .alert {
      padding: 16px;
      border: 1px solid var(--line);
      border-left-width: 5px;
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.02);
    }

    .alert.critical {
      border-left-color: var(--critical);
    }

    .alert.warning {
      border-left-color: var(--warning);
    }

    .alert.info {
      border-left-color: var(--info);
    }

    .alert-title {
      margin-bottom: 6px;
      font-weight: 750;
    }

    .safe {
      color: var(--healthy);
    }

    .footer {
      margin-top: 18px;
      color: var(--muted);
      font-size: 12px;
    }

    @media (max-width: 760px) {
      .hero {
        grid-template-columns: 1fr;
      }

      header {
        flex-direction: column;
      }

      .actions {
        width: 100%;
      }

      button,
      a {
        flex: 1;
      }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>Monitor Paper</h1>
        <p class="muted">
          Saúde operacional, alertas e qualidade das sessões.
        </p>
      </div>

      <div class="actions">
        <button id="refreshButton" type="button">
          Atualizar
        </button>
        <a href="/paper/performance/dashboard">
          Desempenho
        </a>
      </div>
    </header>

    <section class="hero">
      <article class="score">
        <div>
          <div id="scoreNumber" class="score-number">
            --
          </div>
          <div id="scoreStatus" class="score-status">
            Carregando
          </div>
        </div>
      </article>

      <article class="panel">
        <h2>Indicadores</h2>
        <div id="stats" class="stats"></div>
      </article>
    </section>

    <section class="panel">
      <h2>Alertas operacionais</h2>
      <div id="alerts" class="alerts"></div>
    </section>

    <p class="footer" id="lastUpdate">
      Carregando dados...
    </p>
  </main>

  <script>
    const percent = new Intl.NumberFormat(
      "pt-BR",
      {
        style: "percent",
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      }
    );

    const number = new Intl.NumberFormat(
      "pt-BR",
      {
        maximumFractionDigits: 2
      }
    );

    function statusColor(status) {
      const map = {
        HEALTHY: "#44c47d",
        WARNING: "#f6c453",
        CRITICAL: "#ff6b6b",
        NO_DATA: "#6ab7ff"
      };

      return map[status] || "#9ca9b5";
    }

    function stat(label, value) {
      return `
        <div class="stat">
          <div class="stat-label">${label}</div>
          <div class="stat-value">${value}</div>
        </div>
      `;
    }

    function render(payload) {
      const status = payload.status || "UNKNOWN";

      document.getElementById(
        "scoreNumber"
      ).textContent = payload.score ?? "--";

      const statusElement = document.getElementById(
        "scoreStatus"
      );

      statusElement.textContent = status;
      statusElement.style.color = statusColor(status);

      const rates = payload.rates || {};
      const summary = payload.summary || {};

      document.getElementById("stats").innerHTML = [
        stat(
          "Taxa de sucesso",
          percent.format(
            Number(rates.success_cycle_rate || 0)
          )
        ),
        stat(
          "Taxa de falha",
          percent.format(
            Number(rates.failed_cycle_rate || 0)
          )
        ),
        stat(
          "Drawdown máximo",
          percent.format(
            Number(summary.max_drawdown_rate || 0)
          )
        ),
        stat(
          "Relatórios",
          number.format(
            Number(summary.total_reports || 0)
          )
        ),
        stat(
          "Erros de endpoint",
          number.format(
            Number(summary.endpoint_errors || 0)
          )
        ),
        stat(
          "Violações de segurança",
          number.format(
            Number(summary.safety_violations || 0)
          )
        )
      ].join("");

      const alerts = payload.alerts || [];
      const host = document.getElementById("alerts");

      if (!alerts.length) {
        host.innerHTML = `
          <div class="alert info">
            <div class="alert-title safe">
              Nenhum alerta ativo
            </div>
            <div class="muted">
              Os indicadores estão dentro dos limites configurados.
            </div>
          </div>
        `;
      } else {
        host.innerHTML = alerts.map((alert) => `
          <div class="alert ${alert.severity}">
            <div class="alert-title">
              ${alert.title}
            </div>
            <div class="muted">
              ${alert.message}
            </div>
          </div>
        `).join("");
      }

      document.getElementById(
        "lastUpdate"
      ).textContent = (
        "Última atualização: "
        + new Date().toLocaleString("pt-BR")
        + " | Somente leitura | Execução live bloqueada"
      );
    }

    async function refresh() {
      const button = document.getElementById(
        "refreshButton"
      );

      button.disabled = true;
      button.textContent = "Atualizando...";

      try {
        const response = await fetch(
          "/paper/performance/monitor/snapshot",
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

        if (
          payload.execution_authorized !== false
          || payload.live_execution !== false
          || payload.read_only !== true
        ) {
          throw new Error(
            "Guardas de segurança inválidas."
          );
        }

        render(payload);
      } catch (error) {
        document.getElementById(
          "lastUpdate"
        ).textContent = (
          "Falha ao carregar o monitor: "
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
    setInterval(refresh, 15000);
  </script>
</body>
</html>
"""


def _monitor() -> PaperPerformanceMonitor:
    return PaperPerformanceMonitor()


@router.get("/health")
async def performance_monitor_health():
    snapshot = _monitor().snapshot()

    return {
        "status": snapshot["status"],
        "score": snapshot["score"],
        "alert_counts": (
            snapshot["alert_counts"]
        ),
        "execution_authorized": False,
        "live_execution": False,
        "read_only": True,
    }


@router.get("/alerts")
async def performance_monitor_alerts():
    snapshot = _monitor().snapshot()

    return {
        "status": snapshot["status"],
        "score": snapshot["score"],
        "alerts": snapshot["alerts"],
        "alert_counts": (
            snapshot["alert_counts"]
        ),
        "execution_authorized": False,
        "live_execution": False,
        "read_only": True,
    }


@router.get("/score")
async def performance_monitor_score():
    snapshot = _monitor().snapshot()

    return {
        "status": snapshot["status"],
        "score": snapshot["score"],
        "rates": snapshot["rates"],
        "thresholds": snapshot["thresholds"],
        "staleness_hours": (
            snapshot["staleness_hours"]
        ),
        "execution_authorized": False,
        "live_execution": False,
        "read_only": True,
    }


@router.get("/snapshot")
async def performance_monitor_snapshot():
    return _monitor().snapshot()


@router.get(
    "/dashboard",
    response_class=HTMLResponse,
)
async def performance_monitor_dashboard():
    return HTMLResponse(
        content=MONITOR_HTML,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-PredArb-Live-Execution": "false",
        },
    )
