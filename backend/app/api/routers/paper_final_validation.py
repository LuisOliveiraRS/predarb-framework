from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import (
    HTMLResponse,
    Response,
)

from app.paper.final_paper_validation import (
    final_paper_validation,
)


router = APIRouter(
    prefix=(
        "/paper/final-validation"
    ),
    tags=[
        "paper-final-validation"
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
  <title>PredArb | Validação Final Paper</title>

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

    .actions,
    .safety {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }

    .safety {
      margin-bottom: 20px;
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
      grid-template-columns: 270px 1fr;
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
      min-height: 250px;
      place-items: center;
      padding: 20px;
      text-align: center;
    }

    .decision-status {
      font-size: 20px;
      font-weight: 820;
      letter-spacing: 0.04em;
    }

    .decision-score {
      margin-top: 8px;
      font-size: 62px;
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
      box-shadow: none;
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
      grid-template-columns: 100px 1fr auto;
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

    .paper_validated,
    .pass {
      color: var(--good);
    }

    .paper_pending,
    .insufficient_data {
      color: var(--warning);
    }

    .paper_blocked,
    .fail {
      color: var(--critical);
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
        <h1>Validação Final Paper</h1>
        <p class="muted">
          Consolidação final da garantia, qualificação e estabilidade operacional.
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
          href="/paper/final-validation/export.json"
        >
          Exportar JSON
        </a>

        <a
          class="button"
          href="/paper/certification/assurance/dashboard"
        >
          Centro de Garantia
        </a>

        <a
          class="button"
          href="/paper/certification/assurance/gate/dashboard"
        >
          Gate
        </a>
      </div>
    </header>

    <section class="safety">
      <span class="badge">
        Escopo: PAPER_VALIDATION_ONLY
      </span>
      <span class="badge">
        Somente leitura
      </span>
      <span class="badge">
        Não autoriza a próxima fase
      </span>
      <span class="badge">
        Não autoriza execução live
      </span>
    </section>

    <section class="hero">
      <article class="decision">
        <div>
          <div
            id="validationStatus"
            class="decision-status"
          >
            CARREGANDO
          </div>

          <div
            id="validationScore"
            class="decision-score"
          >
            --
          </div>

          <div class="muted">
            Score final de validação
          </div>
        </div>
      </article>

      <article class="panel">
        <h2>Resumo consolidado</h2>

        <div
          id="metrics"
          class="metrics"
        ></div>
      </article>
    </section>

    <section class="panel">
      <h2>Critérios finais</h2>

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

    function ensureSafe(payload) {
      if (
        payload.paper_execution_authorized !== false
        || payload.execution_authorized !== false
        || payload.live_execution !== false
        || payload.financial_execution !== false
        || payload.live_authorization !== false
        || payload.read_only !== true
        || payload.next_step_authorized !== false
      ) {
        throw new Error(
          "Guardas de segurança inválidas."
        );
      }
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

    function render(payload) {
      ensureSafe(payload);

      const summary = payload.summary || {};
      const checks = payload.checks || [];
      const status = payload.status || "INSUFFICIENT_DATA";

      const statusElement = document.getElementById(
        "validationStatus"
      );

      statusElement.textContent = status;
      statusElement.className = (
        "decision-status "
        + normalizeClass(status)
      );

      document.getElementById(
        "validationScore"
      ).textContent = Number(
        payload.validation_score || 0
      ).toFixed(0);

      document.getElementById(
        "metrics"
      ).innerHTML = [
        metric(
          "Garantia",
          summary.assurance_status || "-"
        ),
        metric(
          "Score de garantia",
          Number(
            summary.assurance_score || 0
          ).toFixed(2)
        ),
        metric(
          "Gate",
          summary.gate_status || "-"
        ),
        metric(
          "Score do gate",
          Number(
            summary.gate_score || 0
          ).toFixed(2)
        ),
        metric(
          "Avaliações do gate",
          Number(
            summary.gate_history_entries || 0
          ).toFixed(0)
        ),
        metric(
          "Sequência QUALIFIED",
          Number(
            summary.qualified_streak || 0
          ).toFixed(0)
        ),
        metric(
          "Falhas de runtime",
          Number(
            summary.total_runtime_failures || 0
          ).toFixed(0)
        ),
        metric(
          "Critérios reprovados",
          Number(
            summary.failed_checks || 0
          ).toFixed(0)
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
          "/paper/final-validation/report",
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
          + " | Resultado restrito ao ambiente Paper"
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
        final_paper_validation
        .evaluate()
    )


@router.get("/health")
async def final_paper_validation_health():
    report = _report()

    return {
        "status": report["status"],
        "validated": report["validated"],
        "scope": report["scope"],
        "validation_score": (
            report["validation_score"]
        ),
        "summary": report["summary"],
        "next_step_authorized": False,
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "read_only": True,
    }


@router.get("/report")
async def final_paper_validation_report():
    return _report()


@router.get(
    "/dashboard",
    response_class=HTMLResponse,
)
async def final_paper_validation_dashboard():
    return HTMLResponse(
        content=DASHBOARD_HTML,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-PredArb-Live-Authorization": "false",
            "X-PredArb-Financial-Execution": "false",
            "X-PredArb-Next-Step-Authorization": "false",
        },
    )


@router.get("/export.json")
async def final_paper_validation_export_json():
    return Response(
        content=json.dumps(
            _report(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        media_type="application/json",
        headers={
            "Content-Disposition": (
                "attachment; "
                'filename="predarb-final-paper-validation.json"'
            ),
            "Cache-Control": "no-store",
            "X-PredArb-Live-Authorization": "false",
            "X-PredArb-Financial-Execution": "false",
            "X-PredArb-Next-Step-Authorization": "false",
        },
    )
