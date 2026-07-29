from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import (
    HTMLResponse,
    Response,
)

from app.paper.stability_certification import (
    paper_stability_certification,
)


router = APIRouter(
    prefix="/paper/certification",
    tags=["paper-stability-certification"],
)


DASHBOARD_HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta
    name="viewport"
    content="width=device-width, initial-scale=1"
  >
  <title>PredArb | Certificação Paper</title>

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
      width: min(1180px, calc(100% - 28px));
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

    .actions,
    .safety {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }

    .safety {
      margin-bottom: 20px;
    }

    .badge {
      padding: 8px 11px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(68, 196, 125, 0.08);
      color: var(--good);
      font-size: 12px;
    }

    .hero {
      display: grid;
      grid-template-columns: 250px 1fr;
      gap: 16px;
      margin-bottom: 18px;
    }

    .decision,
    .panel,
    .metric,
    .check {
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

    .checks {
      display: grid;
      gap: 10px;
    }

    .check {
      display: grid;
      grid-template-columns: 120px 1fr auto;
      gap: 14px;
      align-items: center;
      padding: 14px;
      border-radius: 12px;
      box-shadow: none;
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

    .certified,
    .pass {
      color: var(--good);
    }

    .pending {
      color: var(--warning);
    }

    .blocked,
    .blocker {
      color: var(--critical);
    }

    .no_data {
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

      .check {
        grid-template-columns: 1fr;
      }

      .check-value {
        text-align: left;
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
        <h1>Certificação de Estabilidade Paper</h1>
        <p class="muted">
          Validação de consistência baseada no histórico de readiness.
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
          href="/paper/certification/export.json"
        >
          Exportar JSON
        </a>

        <a
          class="button"
          href="/paper/readiness/history/dashboard"
        >
          Histórico
        </a>
      </div>
    </header>

    <section class="safety">
      <span class="badge">
        Escopo exclusivo: PAPER
      </span>
      <span class="badge">
        Não autoriza execução live
      </span>
      <span class="badge">
        Não autoriza ordens
      </span>
      <span class="badge">
        Avaliação somente leitura
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
            id="certificationScore"
            class="decision-score"
          >
            --
          </div>

          <div class="muted">
            Score da certificação
          </div>
        </div>
      </article>

      <article class="panel">
        <h2>Resumo da estabilidade</h2>
        <div
          id="metrics"
          class="metrics"
        ></div>
      </article>
    </section>

    <section class="panel">
      <h2>Critérios da certificação</h2>
      <div
        id="checks"
        class="checks"
      ></div>
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

    function normalizeClass(value) {
      return String(
        value || ""
      ).toLowerCase();
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

    function ensureSafe(payload) {
      if (
        payload.execution_authorized !== false
        || payload.live_execution !== false
        || payload.financial_execution !== false
        || payload.live_authorization !== false
        || payload.read_only !== true
      ) {
        throw new Error(
          "Guardas de segurança inválidas."
        );
      }
    }

    function render(payload) {
      ensureSafe(payload);

      const status = payload.status || "NO_DATA";
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
        "certificationScore"
      ).textContent = Number(
        payload.certification_score || 0
      ).toFixed(0);

      document.getElementById(
        "metrics"
      ).innerHTML = [
        metric(
          "Avaliações",
          integer.format(
            Number(
              summary.total_history_entries || 0
            )
          )
        ),
        metric(
          "Último status",
          summary.latest_status || "-"
        ),
        metric(
          "Último score",
          Number(
            summary.latest_score || 0
          ).toFixed(2)
        ),
        metric(
          "Média recente",
          Number(
            summary.recent_average_score || 0
          ).toFixed(2)
        ),
        metric(
          "Sequência READY",
          integer.format(
            Number(
              summary.consecutive_ready || 0
            )
          )
        ),
        metric(
          "Regressões recentes",
          integer.format(
            Number(
              summary.recent_not_ready || 0
            )
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
          "/paper/certification/report",
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
          + " | Certificação limitada ao ambiente Paper"
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
    return (
        paper_stability_certification
        .evaluate()
    )


@router.get("/health")
async def paper_certification_health():
    report = _report()

    return {
        "status": report["status"],
        "certified": report["certified"],
        "scope": report["scope"],
        "certification_score": report[
            "certification_score"
        ],
        "paper_execution_authorized": False,
        "live_authorization": False,
        "manual_start_required": True,
        "read_only": True,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
    }


@router.get("/report")
async def paper_certification_report():
    return _report()


@router.get(
    "/dashboard",
    response_class=HTMLResponse,
)
async def paper_certification_dashboard():
    return HTMLResponse(
        content=DASHBOARD_HTML,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-PredArb-Live-Authorization": "false",
            "X-PredArb-Financial-Execution": "false",
        },
    )


@router.get("/export.json")
async def paper_certification_export_json():
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
                'filename="predarb-paper-certification.json"'
            ),
            "Cache-Control": "no-store",
            "X-PredArb-Live-Authorization": "false",
            "X-PredArb-Financial-Execution": "false",
        },
    )
