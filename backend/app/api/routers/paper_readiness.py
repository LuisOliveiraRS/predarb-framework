from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import (
    HTMLResponse,
    Response,
)

from app.paper.readiness import (
    paper_readiness_gate,
)


router = APIRouter(
    prefix="/paper/readiness",
    tags=["paper-readiness"],
)


DASHBOARD_HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta
    name="viewport"
    content="width=device-width, initial-scale=1"
  >
  <title>PredArb | Readiness Paper</title>

  <style>
    :root {
      color-scheme: dark;
      --bg: #090c0f;
      --panel: #151a20;
      --line: #2b333d;
      --text: #f5f7f9;
      --muted: #9ca9b5;
      --accent: #ff6a00;
      --ready: #44c47d;
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
      width: min(1220px, calc(100% - 28px));
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
      color: var(--ready);
      font-size: 12px;
    }

    .hero {
      display: grid;
      grid-template-columns: 240px 1fr;
      gap: 16px;
      margin-bottom: 18px;
    }

    .decision,
    .panel,
    .metric {
      border: 1px solid var(--line);
      border-radius: 16px;
      background: rgba(21, 26, 32, 0.94);
      box-shadow:
        0 18px 55px rgba(0, 0, 0, 0.18);
    }

    .decision {
      display: grid;
      min-height: 230px;
      place-items: center;
      padding: 20px;
      text-align: center;
    }

    .decision-status {
      font-size: 22px;
      font-weight: 820;
      letter-spacing: 0.06em;
    }

    .decision-score {
      margin-top: 8px;
      font-size: 58px;
      font-weight: 820;
      letter-spacing: -0.06em;
    }

    .panel {
      margin-bottom: 18px;
      padding: 20px;
    }

    .metrics {
      display: grid;
      grid-template-columns:
        repeat(auto-fit, minmax(145px, 1fr));
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

    .checks {
      display: grid;
      gap: 10px;
    }

    .check {
      display: grid;
      grid-template-columns: 140px 1fr auto;
      gap: 14px;
      align-items: center;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.02);
    }

    .check-status {
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.08em;
    }

    .check-title {
      margin-bottom: 4px;
      font-weight: 730;
    }

    .check-value {
      color: var(--muted);
      font-size: 12px;
      text-align: right;
    }

    .pass,
    .ready {
      color: var(--ready);
    }

    .warning,
    .insufficient_data {
      color: var(--warning);
    }

    .blocker,
    .not_ready {
      color: var(--critical);
    }

    .unknown {
      color: var(--info);
    }

    .footer {
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

      .check {
        grid-template-columns: 1fr;
      }

      .check-value {
        text-align: left;
      }
    }
  </style>
</head>

<body>
  <main>
    <header>
      <div>
        <h1>Readiness Paper</h1>
        <p class="muted">
          Gate de qualificação para continuidade dos testes simulados.
        </p>
      </div>

      <div class="actions">
        <button
          id="refreshButton"
          type="button"
        >
          Avaliar
        </button>

        <a
          class="button"
          href="/paper/readiness/export.json"
        >
          Exportar JSON
        </a>

        <a
          class="button"
          href="/paper/operations/dashboard"
        >
          Operações
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
        Gate somente leitura
      </span>
      <span class="badge">
        Nenhuma autorização de ordens
      </span>
    </section>

    <section class="hero">
      <article class="decision">
        <div>
          <div
            id="decisionStatus"
            class="decision-status"
          >
            CARREGANDO
          </div>

          <div
            id="readinessScore"
            class="decision-score"
          >
            --
          </div>

          <div class="muted">
            Score de readiness
          </div>
        </div>
      </article>

      <article class="panel">
        <h2>Resumo da avaliação</h2>
        <div id="metrics" class="metrics"></div>
      </article>
    </section>

    <section class="panel">
      <h2>Checks de qualificação</h2>
      <div id="checks" class="checks"></div>
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

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function metric(label, value) {
      return `
        <article class="metric">
          <div class="metric-label">
            ${escapeHtml(label)}
          </div>
          <div class="metric-value">
            ${escapeHtml(value)}
          </div>
        </article>
      `;
    }

    function normalizeClass(value) {
      return String(
        value || "UNKNOWN"
      )
        .toLowerCase()
        .replaceAll(" ", "_");
    }

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

    function render(payload) {
      ensureSafe(payload);

      const status = payload.status || "UNKNOWN";
      const summary = payload.summary || {};
      const checks = payload.checks || [];

      const statusElement = document.getElementById(
        "decisionStatus"
      );

      statusElement.textContent = status;
      statusElement.className = (
        "decision-status "
        + normalizeClass(status)
      );

      document.getElementById(
        "readinessScore"
      ).textContent = (
        Number(payload.readiness_score || 0)
        .toFixed(0)
      );

      document.getElementById(
        "metrics"
      ).innerHTML = [
        metric(
          "Checks aprovados",
          integer.format(
            Number(summary.passed_checks || 0)
          )
        ),
        metric(
          "Bloqueadores",
          integer.format(
            Number(summary.blockers || 0)
          )
        ),
        metric(
          "Warnings",
          integer.format(
            Number(summary.warnings || 0)
          )
        ),
        metric(
          "Dados insuficientes",
          integer.format(
            Number(summary.insufficient_data || 0)
          )
        )
      ].join("");

      document.getElementById(
        "checks"
      ).innerHTML = checks.map(
        (check) => `
          <article class="check">
            <div class="check-status ${normalizeClass(
              check.status
            )}">
              ${escapeHtml(check.status)}
            </div>

            <div>
              <div class="check-title">
                ${escapeHtml(check.title)}
              </div>

              <div class="muted">
                ${escapeHtml(check.message)}
              </div>
            </div>

            <div class="check-value">
              Atual: ${escapeHtml(check.current_value)}
              <br>
              Esperado: ${escapeHtml(check.expected_value)}
            </div>
          </article>
        `
      ).join("");
    }

    async function refresh() {
      const button = document.getElementById(
        "refreshButton"
      );

      button.disabled = true;
      button.textContent = "Avaliando...";

      try {
        const response = await fetch(
          "/paper/readiness/report",
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
          "Última avaliação: "
          + new Date().toLocaleString("pt-BR")
          + " | Gate somente leitura"
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
        button.textContent = "Avaliar";
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


def _report():
    return paper_readiness_gate.evaluate()


@router.get("/health")
async def paper_readiness_health():
    report = _report()

    return {
        "status": report["status"],
        "ready": report["ready"],
        "readiness_score": report[
            "readiness_score"
        ],
        "manual_start_required": True,
        "read_only": True,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
    }


@router.get("/report")
async def paper_readiness_report():
    return _report()


@router.get(
    "/dashboard",
    response_class=HTMLResponse,
)
async def paper_readiness_dashboard():
    return HTMLResponse(
        content=DASHBOARD_HTML,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-PredArb-Financial-Execution": "false",
        },
    )


@router.get("/export.json")
async def paper_readiness_export_json():
    payload = json.dumps(
        _report(),
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
                'filename="predarb-paper-readiness.json"'
            ),
            "Cache-Control": "no-store",
            "X-PredArb-Financial-Execution": "false",
        },
    )
