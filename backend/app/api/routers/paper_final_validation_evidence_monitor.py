from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from app.paper.final_paper_validation_evidence_monitor import (
    final_paper_validation_evidence_monitor,
)


router = APIRouter(
    prefix="/paper/final-validation/evidence/monitor",
    tags=["paper-final-validation-evidence-monitor"],
)


DASHBOARD_HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PredArb | Monitor das Evidências Finais</title>
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
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(circle at top right, rgba(255,106,0,.16), transparent 35rem),
        var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, sans-serif;
    }
    main {
      width: min(1160px, calc(100% - 28px));
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
    h1, h2, p { margin-top: 0; }
    h1 {
      margin-bottom: 8px;
      font-size: clamp(30px, 5vw, 50px);
      letter-spacing: -.04em;
    }
    h2 { margin-bottom: 14px; font-size: 18px; }
    .muted { color: var(--muted); }
    .actions, .badges {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }
    .badges { margin-bottom: 20px; }
    button, a.button {
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
    button:disabled { opacity: .55; cursor: wait; }
    .badge {
      padding: 8px 11px;
      border: 1px solid var(--line);
      border-radius: 999px;
      color: var(--good);
      background: rgba(68,196,125,.08);
      font-size: 12px;
    }
    .hero {
      display: grid;
      grid-template-columns: 260px 1fr;
      gap: 16px;
      margin-bottom: 18px;
    }
    .decision, .panel, .metric, .alert {
      border: 1px solid var(--line);
      border-radius: 16px;
      background: rgba(21,26,32,.94);
      box-shadow: 0 18px 55px rgba(0,0,0,.18);
    }
    .decision {
      display: grid;
      min-height: 230px;
      place-items: center;
      padding: 20px;
      text-align: center;
    }
    .status {
      font-size: 22px;
      font-weight: 820;
      letter-spacing: .05em;
    }
    .score {
      margin-top: 8px;
      font-size: 62px;
      font-weight: 820;
      letter-spacing: -.06em;
    }
    .panel { margin-bottom: 18px; padding: 20px; }
    .metrics {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(145px, 1fr));
      gap: 12px;
    }
    .metric { padding: 15px; box-shadow: none; }
    .label { margin-bottom: 8px; color: var(--muted); font-size: 12px; }
    .value { font-size: 24px; font-weight: 770; letter-spacing: -.04em; }
    .alerts { display: grid; gap: 10px; }
    .alert {
      display: grid;
      grid-template-columns: 100px 1fr auto;
      gap: 14px;
      align-items: center;
      padding: 14px;
      border-radius: 12px;
      box-shadow: none;
    }
    .severity {
      font-size: 12px;
      font-weight: 800;
      letter-spacing: .08em;
    }
    .alert-title { margin-bottom: 4px; font-weight: 730; }
    .alert-value { color: var(--muted); font-size: 12px; text-align: right; }
    .healthy { color: var(--good); }
    .warning { color: var(--warning); }
    .critical { color: var(--critical); }
    .no_data, .info { color: var(--info); }
    .footer { color: var(--muted); font-size: 12px; }
    @media (max-width: 760px) {
      header { flex-direction: column; }
      .hero { grid-template-columns: 1fr; }
      .alert { grid-template-columns: 1fr; }
      .alert-value { text-align: left; }
      .actions { width: 100%; }
      button, a.button { flex: 1; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>Monitor das Evidências Finais</h1>
        <p class="muted">
          Integridade, atualização e estado do arquivo probatório Paper.
        </p>
      </div>
      <div class="actions">
        <button id="refreshButton" type="button">Atualizar</button>
        <a class="button" href="/paper/final-validation/evidence/dashboard">
          Evidências
        </a>
        <a class="button" href="/paper/final-validation/evidence/monitor/export.json">
          Exportar JSON
        </a>
      </div>
    </header>

    <section class="badges">
      <span class="badge">Somente leitura</span>
      <span class="badge">Verificação SHA-256</span>
      <span class="badge">Próxima fase não autorizada</span>
      <span class="badge">Execução financeira bloqueada</span>
    </section>

    <section class="hero">
      <article class="decision">
        <div>
          <div id="status" class="status">CARREGANDO</div>
          <div id="score" class="score">--</div>
          <div class="muted">Score de integridade</div>
        </div>
      </article>

      <article class="panel">
        <h2>Resumo</h2>
        <div id="metrics" class="metrics"></div>
      </article>
    </section>

    <section class="panel">
      <h2>Alertas</h2>
      <div id="alerts" class="alerts"></div>
    </section>

    <p id="lastUpdate" class="footer">Carregando...</p>
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
          throw new Error(`Guarda inválida: ${field}`);
        }
      }
      if (payload.read_only !== true) {
        throw new Error("Payload não é somente leitura.");
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
      return String(value || "").toLowerCase();
    }

    function metric(label, value) {
      return `
        <article class="metric">
          <div class="label">${escapeHtml(label)}</div>
          <div class="value">${escapeHtml(value)}</div>
        </article>
      `;
    }

    function render(payload) {
      ensureSafe(payload);

      const summary = payload.summary || {};
      const alerts = payload.alerts || [];

      const status = document.getElementById("status");
      status.textContent = payload.status;
      status.className = `status ${css(payload.status)}`;

      document.getElementById("score").textContent =
        Number(payload.score || 0).toFixed(0);

      document.getElementById("metrics").innerHTML = [
        metric("Evidências", Number(summary.total_entries || 0).toFixed(0)),
        metric("Integridade", summary.integrity_status || "-"),
        metric("Último status", summary.latest_status || "-"),
        metric("Críticos", Number(summary.critical_alerts || 0).toFixed(0)),
        metric("Warnings", Number(summary.warning_alerts || 0).toFixed(0)),
        metric("Alertas totais", Number(summary.total_alerts || 0).toFixed(0))
      ].join("");

      const container = document.getElementById("alerts");

      if (!alerts.length) {
        container.innerHTML = `
          <article class="alert">
            <div class="severity healthy">OK</div>
            <div>
              <div class="alert-title">Nenhum alerta ativo</div>
              <div class="muted">O arquivo probatório está íntegro.</div>
            </div>
            <div class="alert-value">HEALTHY</div>
          </article>
        `;
        return;
      }

      container.innerHTML = alerts.map((alert) => `
        <article class="alert">
          <div class="severity ${css(alert.severity)}">
            ${escapeHtml(alert.severity)}
          </div>
          <div>
            <div class="alert-title">${escapeHtml(alert.title)}</div>
            <div class="muted">${escapeHtml(alert.message)}</div>
          </div>
          <div class="alert-value">
            Atual: ${escapeHtml(alert.current_value)}
            <br>
            Esperado: ${escapeHtml(alert.expected_value)}
          </div>
        </article>
      `).join("");
    }

    async function refresh() {
      const button = document.getElementById("refreshButton");
      button.disabled = true;
      button.textContent = "Atualizando...";

      try {
        const response = await fetch(
          "/paper/final-validation/evidence/monitor/snapshot",
          { cache: "no-store" }
        );

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const payload = await response.json();
        render(payload);

        document.getElementById("lastUpdate").textContent =
          "Última atualização: "
          + new Date().toLocaleString("pt-BR")
          + " | Monitor somente leitura";
      } catch (error) {
        document.getElementById("lastUpdate").textContent =
          "Falha ao atualizar: " + error.message;
      } finally {
        button.disabled = false;
        button.textContent = "Atualizar";
      }
    }

    document.getElementById("refreshButton")
      .addEventListener("click", refresh);

    refresh();
    setInterval(refresh, 15000);
  </script>
</body>
</html>
"""


def _snapshot():
    return (
        final_paper_validation_evidence_monitor
        .evaluate()
    )


@router.get("/health")
async def final_evidence_monitor_health():
    snapshot = _snapshot()

    return {
        "status": snapshot["status"],
        "score": snapshot["score"],
        "summary": snapshot["summary"],
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "next_step_authorized": False,
        "read_only": True,
    }


@router.get("/alerts")
async def final_evidence_monitor_alerts():
    snapshot = _snapshot()

    return {
        "status": snapshot["status"],
        "count": len(snapshot["alerts"]),
        "alerts": snapshot["alerts"],
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "next_step_authorized": False,
        "read_only": True,
    }


@router.get("/score")
async def final_evidence_monitor_score():
    snapshot = _snapshot()

    return {
        "status": snapshot["status"],
        "score": snapshot["score"],
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "next_step_authorized": False,
        "read_only": True,
    }


@router.get("/snapshot")
async def final_evidence_monitor_snapshot():
    return _snapshot()


@router.get(
    "/dashboard",
    response_class=HTMLResponse,
)
async def final_evidence_monitor_dashboard():
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
async def final_evidence_monitor_export_json():
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
                'filename="predarb-final-evidence-monitor.json"'
            ),
            "Cache-Control": "no-store",
            "X-PredArb-Live-Authorization": "false",
            "X-PredArb-Financial-Execution": "false",
            "X-PredArb-Next-Step-Authorization": "false",
        },
    )
