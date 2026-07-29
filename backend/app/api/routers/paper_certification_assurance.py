from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import (
    HTMLResponse,
    Response,
)

from app.paper.certification_assurance_center import (
    paper_certification_assurance_center,
)


router = APIRouter(
    prefix=(
        "/paper/certification/assurance"
    ),
    tags=[
        "paper-certification-assurance"
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
  <title>PredArb | Centro de Garantia Paper</title>

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
      width: min(1260px, calc(100% - 28px));
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
      grid-template-columns: 250px 1fr;
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
        repeat(auto-fit, minmax(150px, 1fr));
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

    .links {
      display: grid;
      grid-template-columns:
        repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
    }

    .module-link {
      display: block;
      padding: 16px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.02);
      color: var(--text);
      text-decoration: none;
    }

    .module-link strong {
      display: block;
      margin-bottom: 5px;
    }

    .assured,
    .healthy,
    .valid,
    .certified {
      color: var(--good);
    }

    .warning,
    .pending,
    .blocked {
      color: var(--warning);
    }

    .critical,
    .broken {
      color: var(--critical);
    }

    .unknown,
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
        <h1>Centro de Garantia Paper</h1>
        <p class="muted">
          Certificação, evidências, integridade e incidentes em uma única visão.
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
          href="/paper/certification/assurance/export.json"
        >
          Exportar JSON
        </a>
      </div>
    </header>

    <section class="safety">
      <span class="badge">
        Escopo exclusivo: PAPER
      </span>
      <span class="badge">
        Dashboard somente leitura
      </span>
      <span class="badge">
        Não autoriza execução live
      </span>
      <span class="badge">
        Não envia ordens
      </span>
    </section>

    <section class="hero">
      <article class="decision">
        <div>
          <div
            id="globalStatus"
            class="decision-status"
          >
            CARREGANDO
          </div>

          <div
            id="assuranceScore"
            class="decision-score"
          >
            --
          </div>

          <div class="muted">
            Score consolidado
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
      <h2>Módulos operacionais</h2>

      <div class="links">
        <a
          class="module-link"
          href="/paper/certification/dashboard"
        >
          <strong>Certificação</strong>
          <span class="muted">
            Critérios de estabilidade Paper.
          </span>
        </a>

        <a
          class="module-link"
          href="/paper/certification/evidence/dashboard"
        >
          <strong>Evidências</strong>
          <span class="muted">
            Cadeia SHA-256 das avaliações.
          </span>
        </a>

        <a
          class="module-link"
          href="/paper/certification/evidence/monitor/dashboard"
        >
          <strong>Monitor de integridade</strong>
          <span class="muted">
            Saúde e validade da cadeia.
          </span>
        </a>

        <a
          class="module-link"
          href="/paper/certification/evidence/incidents/ui/dashboard"
        >
          <strong>Incidentes</strong>
          <span class="muted">
            Alertas ativos, resolvidos e reconhecimentos.
          </span>
        </a>

        <a
          class="module-link"
          href="/paper/certification/evidence/incident-runtime/dashboard"
        >
          <strong>Runtime dos incidentes</strong>
          <span class="muted">
            Captura periódica controlada.
          </span>
        </a>
      </div>
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
      const status = payload.status || "UNKNOWN";

      const statusElement = document.getElementById(
        "globalStatus"
      );

      statusElement.textContent = status;
      statusElement.className = (
        "decision-status "
        + normalizeClass(status)
      );

      document.getElementById(
        "assuranceScore"
      ).textContent = Number(
        payload.assurance_score || 0
      ).toFixed(0);

      document.getElementById(
        "metrics"
      ).innerHTML = [
        metric(
          "Certificação",
          summary.certification_status || "-"
        ),
        metric(
          "Score da certificação",
          Number(
            summary.certification_score || 0
          ).toFixed(2)
        ),
        metric(
          "Monitor",
          summary.monitor_status || "-"
        ),
        metric(
          "Score do monitor",
          Number(
            summary.monitor_score || 0
          ).toFixed(2)
        ),
        metric(
          "Cadeia",
          summary.chain_status || "-"
        ),
        metric(
          "Evidências",
          Number(
            summary.evidence_entries || 0
          ).toFixed(0)
        ),
        metric(
          "Incidentes ativos",
          Number(
            summary.active_incidents || 0
          ).toFixed(0)
        ),
        metric(
          "Runtime",
          summary.runtime_status || "-"
        )
      ].join("");
    }

    async function refresh() {
      const button = document.getElementById(
        "refreshButton"
      );

      button.disabled = true;
      button.textContent = "Atualizando...";

      try {
        const response = await fetch(
          "/paper/certification/assurance/snapshot",
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
          + " | Garantia limitada ao ambiente Paper"
        );
      } catch (error) {
        document.getElementById(
          "lastUpdate"
        ).textContent = (
          "Falha na atualização: "
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
    return (
        paper_certification_assurance_center
        .snapshot()
    )


@router.get("/health")
async def certification_assurance_health():
    snapshot = _snapshot()

    return {
        "status": snapshot["status"],
        "assured": snapshot["assured"],
        "scope": snapshot["scope"],
        "assurance_score": snapshot[
            "assurance_score"
        ],
        "summary": snapshot["summary"],
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "read_only": True,
    }


@router.get("/snapshot")
async def certification_assurance_snapshot():
    return _snapshot()


@router.get(
    "/dashboard",
    response_class=HTMLResponse,
)
async def certification_assurance_dashboard():
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
async def certification_assurance_export_json():
    return Response(
        content=json.dumps(
            _snapshot(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        media_type="application/json",
        headers={
            "Content-Disposition": (
                "attachment; "
                'filename="predarb-paper-certification-assurance.json"'
            ),
            "Cache-Control": "no-store",
            "X-PredArb-Live-Authorization": "false",
            "X-PredArb-Financial-Execution": "false",
        },
    )
