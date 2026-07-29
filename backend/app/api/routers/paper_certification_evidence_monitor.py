from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import (
    HTMLResponse,
    Response,
)

from app.paper.certification_evidence_monitor import (
    paper_certification_evidence_monitor,
)


router = APIRouter(
    prefix=(
        "/paper/certification/evidence/monitor"
    ),
    tags=[
        "paper-certification-evidence-monitor"
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
  <title>PredArb | Monitor de Evidências</title>

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
    .metric,
    .alert {
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

    .alerts {
      display: grid;
      gap: 10px;
    }

    .alert {
      display: grid;
      grid-template-columns: 120px 1fr auto;
      gap: 14px;
      align-items: center;
      padding: 14px;
      border-radius: 12px;
      box-shadow: none;
    }

    .severity {
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.08em;
    }

    .alert-title {
      margin-bottom: 4px;
      font-weight: 730;
    }

    .alert-value {
      color: var(--muted);
      font-size: 12px;
      text-align: right;
    }

    .healthy,
    .valid {
      color: var(--good);
    }

    .warning {
      color: var(--warning);
    }

    .critical,
    .broken {
      color: var(--critical);
    }

    .info,
    .no_data,
    .empty {
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

      .alert {
        grid-template-columns: 1fr;
      }

      .alert-value {
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
        <h1>Monitor de Evidências</h1>
        <p class="muted">
          Saúde, integridade e atualização do arquivo encadeado.
        </p>
      </div>

      <div class="actions">
        <button
          id="refreshButton"
          type="button"
        >
          Verificar
        </button>

        <a
          class="button"
          href="/paper/certification/evidence/monitor/export.json"
        >
          Exportar JSON
        </a>

        <a
          class="button"
          href="/paper/certification/evidence/dashboard"
        >
          Evidências
        </a>
      </div>
    </header>

    <section class="safety">
      <span class="badge">
        Monitor somente leitura
      </span>
      <span class="badge">
        Nenhuma evidência é criada
      </span>
      <span class="badge">
        Não autoriza execução live
      </span>
      <span class="badge">
        Execução financeira bloqueada
      </span>
    </section>

    <section class="hero">
      <article class="decision">
        <div>
          <div
            id="monitorStatus"
            class="decision-status"
          >
            CARREGANDO
          </div>

          <div
            id="monitorScore"
            class="decision-score"
          >
            --
          </div>

          <div class="muted">
            Score de integridade
          </div>
        </div>
      </article>

      <article class="panel">
        <h2>Diagnóstico consolidado</h2>

        <div
          id="metrics"
          class="metrics"
        ></div>
      </article>
    </section>

    <section class="panel">
      <h2>Alertas ativos</h2>

      <div
        id="alerts"
        class="alerts"
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
      const diagnostics = payload.diagnostics || {};
      const counts = payload.alert_counts || {};
      const alerts = payload.alerts || [];

      const statusElement = document.getElementById(
        "monitorStatus"
      );

      statusElement.textContent = status;
      statusElement.className = (
        "decision-status "
        + normalizeClass(status)
      );

      document.getElementById(
        "monitorScore"
      ).textContent = Number(
        payload.score || 0
      ).toFixed(0);

      document.getElementById(
        "metrics"
      ).innerHTML = [
        metric(
          "Evidências",
          integer.format(
            Number(
              diagnostics.total_entries || 0
            )
          )
        ),
        metric(
          "Cadeia",
          diagnostics.chain_status || "-"
        ),
        metric(
          "Último status",
          diagnostics.latest_status || "-"
        ),
        metric(
          "Último score",
          Number(
            diagnostics.latest_score || 0
          ).toFixed(2)
        ),
        metric(
          "Idade em horas",
          diagnostics.latest_age_hours === null
            ? "-"
            : Number(
                diagnostics.latest_age_hours
              ).toFixed(2)
        ),
        metric(
          "Alertas críticos",
          integer.format(
            Number(counts.critical || 0)
          )
        )
      ].join("");

      const host = document.getElementById(
        "alerts"
      );

      if (!alerts.length) {
        host.innerHTML = `
          <article class="alert">
            <div class="severity healthy">
              HEALTHY
            </div>
            <div>
              <div class="alert-title">
                Nenhum alerta ativo
              </div>
              <div class="muted">
                A cadeia está íntegra e dentro dos limites.
              </div>
            </div>
            <div class="alert-value">
              Sem ação necessária
            </div>
          </article>
        `;
        return;
      }

      host.innerHTML = alerts.map(
        (alert) => `
          <article class="alert">
            <div class="severity ${normalizeClass(
              alert.severity
            )}">
              ${escapeHtml(
                alert.severity
              ).toUpperCase()}
            </div>

            <div>
              <div class="alert-title">
                ${escapeHtml(alert.title)}
              </div>

              <div class="muted">
                ${escapeHtml(alert.message)}
              </div>
            </div>

            <div class="alert-value">
              Atual: ${escapeHtml(alert.current_value)}
              <br>
              Limite: ${escapeHtml(alert.threshold)}
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
      button.textContent = "Verificando...";

      try {
        const response = await fetch(
          "/paper/certification/evidence/monitor/snapshot",
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
          "Última verificação: "
          + new Date().toLocaleString("pt-BR")
          + " | Nenhuma evidência foi modificada"
        );
      } catch (error) {
        document.getElementById(
          "lastUpdate"
        ).textContent = (
          "Falha na verificação: "
          + error.message
        );
      } finally {
        button.disabled = false;
        button.textContent = "Verificar";
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


def _snapshot():
    return (
        paper_certification_evidence_monitor
        .snapshot()
    )


@router.get("/health")
async def evidence_monitor_health():
    snapshot = _snapshot()

    return {
        "status": snapshot["status"],
        "score": snapshot["score"],
        "chain_status": snapshot[
            "diagnostics"
        ]["chain_status"],
        "chain_valid": snapshot[
            "diagnostics"
        ]["chain_valid"],
        **{
            key: snapshot[key]
            for key in (
                "paper_execution_authorized",
                "live_authorization",
                "execution_authorized",
                "live_execution",
                "financial_execution",
                "read_only",
            )
        },
    }


@router.get("/alerts")
async def evidence_monitor_alerts():
    snapshot = _snapshot()

    return {
        "status": snapshot["status"],
        "alert_counts": snapshot[
            "alert_counts"
        ],
        "alerts": snapshot["alerts"],
        **{
            key: snapshot[key]
            for key in (
                "paper_execution_authorized",
                "live_authorization",
                "execution_authorized",
                "live_execution",
                "financial_execution",
                "read_only",
            )
        },
    }


@router.get("/score")
async def evidence_monitor_score():
    snapshot = _snapshot()

    return {
        "status": snapshot["status"],
        "score": snapshot["score"],
        "thresholds": snapshot[
            "thresholds"
        ],
        **{
            key: snapshot[key]
            for key in (
                "paper_execution_authorized",
                "live_authorization",
                "execution_authorized",
                "live_execution",
                "financial_execution",
                "read_only",
            )
        },
    }


@router.get("/snapshot")
async def evidence_monitor_snapshot():
    return _snapshot()


@router.get(
    "/dashboard",
    response_class=HTMLResponse,
)
async def evidence_monitor_dashboard():
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
async def evidence_monitor_export_json():
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
                'filename="predarb-paper-evidence-monitor.json"'
            ),
            "Cache-Control": "no-store",
            "X-PredArb-Live-Authorization": "false",
            "X-PredArb-Financial-Execution": "false",
        },
    )
