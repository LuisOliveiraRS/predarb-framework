from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import (
    APIRouter,
    Query,
)
from fastapi.responses import (
    HTMLResponse,
    Response,
)

from app.paper.performance import (
    PaperPerformanceService,
)


router = APIRouter(
    prefix="/paper/performance",
    tags=["paper-performance-dashboard"],
)


DASHBOARD_HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta
    name="viewport"
    content="width=device-width, initial-scale=1"
  >
  <title>PredArb | Desempenho Paper</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0b0d10;
      --panel: #14181d;
      --line: #2a3139;
      --text: #f2f5f7;
      --muted: #9ca8b3;
      --accent: #ff6a00;
      --ok: #44c47d;
      --danger: #ff6b6b;
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
          rgba(255, 106, 0, 0.13),
          transparent 32rem
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
      width: min(1400px, calc(100% - 32px));
      margin: 0 auto;
      padding: 32px 0 56px;
    }

    header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 24px;
      margin-bottom: 24px;
    }

    h1,
    h2,
    p {
      margin-top: 0;
    }

    h1 {
      margin-bottom: 8px;
      font-size: clamp(28px, 5vw, 48px);
      letter-spacing: -0.04em;
    }

    h2 {
      margin-bottom: 16px;
      font-size: 18px;
    }

    .subtitle,
    .muted {
      color: var(--muted);
    }

    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }

    button,
    a.button {
      appearance: none;
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

    button.primary {
      border-color: var(--accent);
      background: var(--accent);
      color: #111;
      font-weight: 700;
    }

    .safety {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-bottom: 24px;
    }

    .badge {
      padding: 8px 12px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(68, 196, 125, 0.08);
      color: var(--ok);
      font-size: 13px;
    }

    .grid {
      display: grid;
      grid-template-columns:
        repeat(auto-fit, minmax(180px, 1fr));
      gap: 14px;
      margin-bottom: 24px;
    }

    .card,
    .panel {
      border: 1px solid var(--line);
      border-radius: 16px;
      background: rgba(20, 24, 29, 0.92);
      box-shadow:
        0 18px 55px rgba(0, 0, 0, 0.18);
    }

    .card {
      padding: 18px;
    }

    .card .label {
      margin-bottom: 9px;
      color: var(--muted);
      font-size: 13px;
    }

    .card .value {
      font-size: 28px;
      font-weight: 750;
      letter-spacing: -0.04em;
    }

    .panel {
      margin-bottom: 18px;
      padding: 20px;
      overflow: hidden;
    }

    .chart {
      width: 100%;
      min-height: 280px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background:
        linear-gradient(
          180deg,
          rgba(255, 106, 0, 0.05),
          transparent
        );
    }

    .chart-empty {
      display: grid;
      min-height: 280px;
      place-items: center;
      color: var(--muted);
    }

    .table-wrap {
      overflow-x: auto;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      min-width: 920px;
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
      font-weight: 600;
    }

    .status-pass {
      color: var(--ok);
      font-weight: 700;
    }

    .status-fail {
      color: var(--danger);
      font-weight: 700;
    }

    .footer {
      margin-top: 20px;
      color: var(--muted);
      font-size: 12px;
    }

    @media (max-width: 720px) {
      main {
        width: min(100% - 20px, 1400px);
        padding-top: 20px;
      }

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
        <h1>Desempenho Paper</h1>
        <p class="subtitle">
          Histórico consolidado das sessões simuladas do PredArb.
        </p>
      </div>

      <div class="actions">
        <button
          class="primary"
          type="button"
          id="refreshButton"
        >
          Atualizar
        </button>

        <a
          class="button"
          href="/paper/performance/export.csv"
        >
          Exportar CSV
        </a>
      </div>
    </header>

    <section class="safety">
      <span class="badge">
        Execução live bloqueada
      </span>
      <span class="badge">
        IA sem autorização de ordens
      </span>
      <span class="badge">
        Painel somente leitura
      </span>
    </section>

    <section class="grid" id="summaryGrid"></section>

    <section class="panel">
      <h2>Curva de equity</h2>
      <div id="equityChart" class="chart"></div>
    </section>

    <section class="panel">
      <h2>Sessões registradas</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Status</th>
              <th>Rótulo</th>
              <th>Finalização</th>
              <th>Ciclos</th>
              <th>Sucessos</th>
              <th>Falhas</th>
              <th>Trades</th>
              <th>Resultado</th>
              <th>Drawdown</th>
            </tr>
          </thead>
          <tbody id="reportsBody"></tbody>
        </table>
      </div>
    </section>

    <p class="footer" id="lastUpdate">
      Carregando dados...
    </p>
  </main>

  <script>
    const money = new Intl.NumberFormat(
      "pt-BR",
      {
        style: "currency",
        currency: "BRL"
      }
    );

    const percent = new Intl.NumberFormat(
      "pt-BR",
      {
        style: "percent",
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      }
    );

    const integer = new Intl.NumberFormat(
      "pt-BR",
      {
        maximumFractionDigits: 0
      }
    );

    function number(value) {
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : 0;
    }

    function card(label, value) {
      return `
        <article class="card">
          <div class="label">${label}</div>
          <div class="value">${value}</div>
        </article>
      `;
    }

    function renderSummary(summary) {
      const grid = document.getElementById("summaryGrid");

      grid.innerHTML = [
        card(
          "Sessões",
          integer.format(number(summary.total_reports))
        ),
        card(
          "Ciclos",
          integer.format(number(summary.total_cycles))
        ),
        card(
          "Trades Paper",
          integer.format(number(summary.total_trades))
        ),
        card(
          "Resultado acumulado",
          money.format(
            number(summary.cumulative_equity_delta)
          )
        ),
        card(
          "Retorno médio",
          percent.format(
            number(summary.average_session_return_rate)
          )
        ),
        card(
          "Drawdown máximo",
          percent.format(
            number(summary.max_drawdown_rate)
          )
        )
      ].join("");
    }

    function renderReports(reports) {
      const body = document.getElementById("reportsBody");

      if (!reports.length) {
        body.innerHTML = `
          <tr>
            <td colspan="9" class="muted">
              Nenhum relatório encontrado.
            </td>
          </tr>
        `;
        return;
      }

      body.innerHTML = reports.map((report) => {
        const status = String(
          report.status || "UNKNOWN"
        ).toUpperCase();

        const className = (
          status === "PASS"
          ? "status-pass"
          : "status-fail"
        );

        const finishedAt = report.finished_at
          ? new Date(report.finished_at).toLocaleString(
              "pt-BR"
            )
          : "-";

        return `
          <tr>
            <td class="${className}">${status}</td>
            <td>${report.label || "-"}</td>
            <td>${finishedAt}</td>
            <td>${integer.format(number(report.cycles))}</td>
            <td>
              ${integer.format(
                number(report.successful_cycles)
              )}
            </td>
            <td>
              ${integer.format(
                number(report.failed_cycles)
              )}
            </td>
            <td>${integer.format(number(report.trades))}</td>
            <td>${money.format(number(report.equity_delta))}</td>
            <td>
              ${percent.format(
                number(report.max_drawdown_rate)
              )}
            </td>
          </tr>
        `;
      }).join("");
    }

    function renderEquity(points) {
      const host = document.getElementById("equityChart");

      const values = points
        .map((point) => ({
          capturedAt: point.captured_at,
          equity: number(point.equity)
        }))
        .filter((point) => (
          point.capturedAt
          && Number.isFinite(point.equity)
        ));

      if (values.length < 2) {
        host.innerHTML = `
          <div class="chart-empty">
            Histórico insuficiente para formar a curva.
          </div>
        `;
        return;
      }

      const width = 1100;
      const height = 280;
      const padding = 30;

      const equities = values.map(
        (item) => item.equity
      );

      const minValue = Math.min(...equities);
      const maxValue = Math.max(...equities);
      const span = Math.max(maxValue - minValue, 1);

      const polyline = values.map((item, index) => {
        const x = (
          padding
          + (
            index
            / Math.max(values.length - 1, 1)
          ) * (width - padding * 2)
        );

        const y = (
          height
          - padding
          - (
            (item.equity - minValue)
            / span
          ) * (height - padding * 2)
        );

        return `${x.toFixed(2)},${y.toFixed(2)}`;
      }).join(" ");

      host.innerHTML = `
        <svg
          viewBox="0 0 ${width} ${height}"
          width="100%"
          height="280"
          role="img"
          aria-label="Curva de equity do Paper Trading"
        >
          <line
            x1="${padding}"
            y1="${height - padding}"
            x2="${width - padding}"
            y2="${height - padding}"
            stroke="#2a3139"
          ></line>

          <polyline
            points="${polyline}"
            fill="none"
            stroke="#ff6a00"
            stroke-width="4"
            stroke-linecap="round"
            stroke-linejoin="round"
          ></polyline>

          <text
            x="${padding}"
            y="20"
            fill="#9ca8b3"
            font-size="13"
          >
            ${money.format(maxValue)}
          </text>

          <text
            x="${padding}"
            y="${height - 7}"
            fill="#9ca8b3"
            font-size="13"
          >
            ${money.format(minValue)}
          </text>
        </svg>
      `;
    }

    async function refreshDashboard() {
      const button = document.getElementById(
        "refreshButton"
      );

      button.disabled = true;
      button.textContent = "Atualizando...";

      try {
        const response = await fetch(
          "/paper/performance/snapshot"
          + "?report_limit=50&history_limit=1000",
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
        ) {
          throw new Error(
            "Guardas de segurança inválidas."
          );
        }

        renderSummary(payload.summary || {});
        renderReports(payload.reports || []);
        renderEquity(payload.history || []);

        document.getElementById(
          "lastUpdate"
        ).textContent = (
          "Última atualização: "
          + new Date().toLocaleString("pt-BR")
        );
      } catch (error) {
        document.getElementById(
          "lastUpdate"
        ).textContent = (
          "Falha ao carregar o painel: "
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
      refreshDashboard
    );

    refreshDashboard();
    setInterval(refreshDashboard, 15000);
  </script>
</body>
</html>
"""


def _service() -> PaperPerformanceService:
    return PaperPerformanceService()


@router.get(
    "/dashboard",
    response_class=HTMLResponse,
)
async def paper_performance_dashboard():
    return HTMLResponse(
        content=DASHBOARD_HTML,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/snapshot")
async def paper_performance_snapshot(
    report_limit: int = Query(
        default=50,
        ge=1,
        le=500,
    ),
    history_limit: int = Query(
        default=1000,
        ge=1,
        le=5000,
    ),
):
    service = _service()

    reports = service.list_reports(
        limit=report_limit
    )

    history = service.history(
        limit=history_limit,
        report_limit=report_limit,
    )

    return {
        "summary": service.summary(),
        "reports": reports,
        "history": history,
        "execution_authorized": False,
        "live_execution": False,
        "read_only": True,
    }


@router.get("/export.csv")
async def paper_performance_export_csv(
    history_limit: int = Query(
        default=5000,
        ge=1,
        le=5000,
    ),
):
    points = _service().history(
        limit=history_limit,
        report_limit=200,
    )

    fieldnames = [
        "captured_at",
        "report_name",
        "label",
        "runtime_status",
        "runtime_running",
        "total_cycles",
        "successful_cycles",
        "failed_cycles",
        "no_signal_cycles",
        "risk_stopped_cycles",
        "equity",
        "total_pnl",
        "realized_pnl",
        "unrealized_pnl",
        "return_rate",
        "trade_count",
        "open_positions",
        "max_drawdown",
        "max_drawdown_rate",
    ]

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=fieldnames,
        extrasaction="ignore",
    )
    writer.writeheader()

    for point in points:
        writer.writerow(point)

    content = (
        "\ufeff"
        + buffer.getvalue()
    )

    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                "attachment; "
                'filename="predarb-paper-performance.csv"'
            ),
            "Cache-Control": "no-store",
            "X-PredArb-Live-Execution": "false",
        },
    )
