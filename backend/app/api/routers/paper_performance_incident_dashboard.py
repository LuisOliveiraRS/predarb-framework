from __future__ import annotations

import csv
import io
from typing import Any, Mapping

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, Response

from app.paper.performance_incidents import (
    PaperIncidentJournal,
)
from app.paper.performance_monitor import (
    PaperPerformanceMonitor,
)


router = APIRouter(
    prefix="/paper/performance/incidents",
    tags=["paper-performance-incident-dashboard"],
)


DASHBOARD_HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta
    name="viewport"
    content="width=device-width, initial-scale=1"
  >
  <title>PredArb | Incidentes Paper</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0a0d10;
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
      width: min(1320px, calc(100% - 28px));
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

    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
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

    button.primary {
      border-color: var(--accent);
      background: var(--accent);
      color: #111;
      font-weight: 750;
    }

    button.small {
      min-height: 34px;
      padding: 0 11px;
      font-size: 12px;
    }

    button:disabled {
      opacity: 0.55;
      cursor: wait;
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

    .grid {
      display: grid;
      grid-template-columns:
        repeat(auto-fit, minmax(170px, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }

    .card,
    .panel {
      border: 1px solid var(--line);
      border-radius: 16px;
      background: rgba(21, 26, 32, 0.94);
      box-shadow:
        0 18px 55px rgba(0, 0, 0, 0.18);
    }

    .card {
      padding: 16px;
    }

    .card-label {
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 12px;
    }

    .card-value {
      font-size: 27px;
      font-weight: 780;
      letter-spacing: -0.04em;
    }

    .panel {
      margin-bottom: 18px;
      padding: 20px;
      overflow: hidden;
    }

    .monitor-line {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.02);
    }

    .monitor-status {
      font-weight: 800;
      letter-spacing: 0.08em;
    }

    .table-wrap {
      overflow-x: auto;
    }

    table {
      width: 100%;
      min-width: 1100px;
      border-collapse: collapse;
    }

    th,
    td {
      padding: 12px 10px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      white-space: nowrap;
      font-size: 13px;
    }

    th {
      color: var(--muted);
      font-weight: 650;
    }

    td.message {
      max-width: 340px;
      white-space: normal;
    }

    .severity-critical {
      color: var(--critical);
      font-weight: 750;
    }

    .severity-warning {
      color: var(--warning);
      font-weight: 750;
    }

    .severity-info {
      color: var(--info);
      font-weight: 750;
    }

    .status-active {
      color: var(--warning);
      font-weight: 750;
    }

    .status-resolved {
      color: var(--healthy);
      font-weight: 750;
    }

    .empty {
      padding: 28px 10px;
      color: var(--muted);
      text-align: center;
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
        <h1>Incidentes Paper</h1>
        <p class="muted">
          Registro, resolução e reconhecimento de alertas operacionais.
        </p>
      </div>

      <div class="actions">
        <button
          id="refreshButton"
          type="button"
        >
          Atualizar
        </button>

        <button
          id="captureButton"
          type="button"
          class="primary"
        >
          Capturar alertas
        </button>

        <a
          class="button"
          href="/paper/performance/incidents/export.csv"
        >
          Exportar CSV
        </a>

        <a
          class="button"
          href="/paper/performance/monitor/dashboard"
        >
          Monitor
        </a>
      </div>
    </header>

    <section class="safety">
      <span class="badge">
        Execução financeira bloqueada
      </span>
      <span class="badge">
        IA sem autorização de ordens
      </span>
      <span class="badge">
        Ações limitadas ao journal
      </span>
    </section>

    <section class="grid" id="summaryGrid"></section>

    <section class="panel">
      <h2>Estado atual do monitor</h2>
      <div id="monitorLine" class="monitor-line">
        Carregando...
      </div>
    </section>

    <section class="panel">
      <h2>Incidentes ativos</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Severidade</th>
              <th>Código</th>
              <th>Título</th>
              <th>Mensagem</th>
              <th>Ocorrências</th>
              <th>Primeira ocorrência</th>
              <th>Última ocorrência</th>
              <th>Reconhecido</th>
              <th>Ação</th>
            </tr>
          </thead>
          <tbody id="activeBody"></tbody>
        </table>
      </div>
    </section>

    <section class="panel">
      <h2>Histórico recente</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Status</th>
              <th>Severidade</th>
              <th>Código</th>
              <th>Título</th>
              <th>Ocorrências</th>
              <th>Última ocorrência</th>
              <th>Resolvido em</th>
              <th>Reconhecido em</th>
            </tr>
          </thead>
          <tbody id="historyBody"></tbody>
        </table>
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

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function dateTime(value) {
      if (!value) {
        return "-";
      }

      const parsed = new Date(value);

      if (Number.isNaN(parsed.getTime())) {
        return escapeHtml(value);
      }

      return parsed.toLocaleString("pt-BR");
    }

    function card(label, value) {
      return `
        <article class="card">
          <div class="card-label">${escapeHtml(label)}</div>
          <div class="card-value">${escapeHtml(value)}</div>
        </article>
      `;
    }

    function severityClass(value) {
      return (
        "severity-"
        + String(value || "info").toLowerCase()
      );
    }

    function renderSummary(summary) {
      document.getElementById(
        "summaryGrid"
      ).innerHTML = [
        card(
          "Incidentes ativos",
          integer.format(
            Number(summary.active_incidents || 0)
          )
        ),
        card(
          "Críticos ativos",
          integer.format(
            Number(summary.active_critical || 0)
          )
        ),
        card(
          "Warnings ativos",
          integer.format(
            Number(summary.active_warning || 0)
          )
        ),
        card(
          "Resolvidos",
          integer.format(
            Number(summary.resolved_incidents || 0)
          )
        ),
        card(
          "Reconhecidos",
          integer.format(
            Number(summary.acknowledged_incidents || 0)
          )
        ),
        card(
          "Snapshots",
          integer.format(
            Number(summary.snapshots || 0)
          )
        )
      ].join("");
    }

    function renderMonitor(monitor) {
      const status = escapeHtml(
        monitor.status || "UNKNOWN"
      );

      const score = escapeHtml(
        monitor.score ?? "--"
      );

      const activeAlerts = (
        monitor.alert_counts
        ? Object.values(monitor.alert_counts)
            .reduce(
              (total, value) => (
                total + Number(value || 0)
              ),
              0
            )
        : 0
      );

      document.getElementById(
        "monitorLine"
      ).innerHTML = `
        <div>
          <div class="monitor-status">
            ${status}
          </div>
          <div class="muted">
            ${integer.format(activeAlerts)} alertas ativos
          </div>
        </div>
        <div>
          Score: <strong>${score}</strong>
        </div>
      `;
    }

    function renderActive(incidents) {
      const body = document.getElementById(
        "activeBody"
      );

      if (!incidents.length) {
        body.innerHTML = `
          <tr>
            <td colspan="9" class="empty">
              Nenhum incidente ativo.
            </td>
          </tr>
        `;
        return;
      }

      body.innerHTML = incidents.map(
        (incident) => `
          <tr>
            <td class="${severityClass(
              incident.severity
            )}">
              ${escapeHtml(incident.severity)}
            </td>
            <td>${escapeHtml(incident.code)}</td>
            <td>${escapeHtml(incident.title)}</td>
            <td class="message">
              ${escapeHtml(incident.message)}
            </td>
            <td>
              ${integer.format(
                Number(incident.occurrences || 0)
              )}
            </td>
            <td>${dateTime(incident.first_seen_at)}</td>
            <td>${dateTime(incident.last_seen_at)}</td>
            <td>
              ${incident.acknowledged_at ? "Sim" : "Não"}
            </td>
            <td>
              <button
                class="small"
                type="button"
                data-incident-id="${escapeHtml(
                  incident.id
                )}"
                ${incident.acknowledged_at ? "disabled" : ""}
              >
                Reconhecer
              </button>
            </td>
          </tr>
        `
      ).join("");

      body.querySelectorAll(
        "[data-incident-id]"
      ).forEach((button) => {
        button.addEventListener(
          "click",
          () => acknowledgeIncident(
            button.dataset.incidentId
          )
        );
      });
    }

    function renderHistory(incidents) {
      const body = document.getElementById(
        "historyBody"
      );

      if (!incidents.length) {
        body.innerHTML = `
          <tr>
            <td colspan="8" class="empty">
              Nenhum incidente registrado.
            </td>
          </tr>
        `;
        return;
      }

      body.innerHTML = incidents.map(
        (incident) => `
          <tr>
            <td class="${
              incident.status === "ACTIVE"
              ? "status-active"
              : "status-resolved"
            }">
              ${escapeHtml(incident.status)}
            </td>
            <td class="${severityClass(
              incident.severity
            )}">
              ${escapeHtml(incident.severity)}
            </td>
            <td>${escapeHtml(incident.code)}</td>
            <td>${escapeHtml(incident.title)}</td>
            <td>
              ${integer.format(
                Number(incident.occurrences || 0)
              )}
            </td>
            <td>${dateTime(incident.last_seen_at)}</td>
            <td>${dateTime(incident.resolved_at)}</td>
            <td>${dateTime(incident.acknowledged_at)}</td>
          </tr>
        `
      ).join("");
    }

    async function loadDashboard() {
      const refreshButton = document.getElementById(
        "refreshButton"
      );

      refreshButton.disabled = true;
      refreshButton.textContent = "Atualizando...";

      try {
        const response = await fetch(
          "/paper/performance/incidents/snapshot"
          + "?active_limit=100&history_limit=250",
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
          || payload.financial_execution !== false
        ) {
          throw new Error(
            "Guardas de segurança inválidas."
          );
        }

        renderSummary(payload.summary || {});
        renderMonitor(payload.monitor || {});
        renderActive(payload.active || []);
        renderHistory(payload.history || []);

        document.getElementById(
          "lastUpdate"
        ).textContent = (
          "Última atualização: "
          + new Date().toLocaleString("pt-BR")
          + " | Ações administrativas sem execução financeira"
        );
      } catch (error) {
        document.getElementById(
          "lastUpdate"
        ).textContent = (
          "Falha ao carregar o painel: "
          + error.message
        );
      } finally {
        refreshButton.disabled = false;
        refreshButton.textContent = "Atualizar";
      }
    }

    async function captureAlerts() {
      const button = document.getElementById(
        "captureButton"
      );

      const confirmed = window.confirm(
        "Capturar o estado atual do monitor no journal?"
      );

      if (!confirmed) {
        return;
      }

      button.disabled = true;
      button.textContent = "Capturando...";

      try {
        const response = await fetch(
          "/paper/performance/incidents/capture"
          + "?confirm=CAPTURE-PAPER-INCIDENTS",
          {
            method: "POST"
          }
        );

        if (!response.ok) {
          throw new Error(
            `HTTP ${response.status}`
          );
        }

        await loadDashboard();
      } catch (error) {
        window.alert(
          "Falha na captura: " + error.message
        );
      } finally {
        button.disabled = false;
        button.textContent = "Capturar alertas";
      }
    }

    async function acknowledgeIncident(incidentId) {
      const confirmed = window.confirm(
        "Reconhecer este incidente no journal?"
      );

      if (!confirmed) {
        return;
      }

      const endpoint = (
        "/paper/performance/incidents/"
        + encodeURIComponent(incidentId)
        + "/acknowledge"
        + "?confirm=ACK-PAPER-INCIDENT"
      );

      try {
        const response = await fetch(
          endpoint,
          {
            method: "POST"
          }
        );

        if (!response.ok) {
          throw new Error(
            `HTTP ${response.status}`
          );
        }

        await loadDashboard();
      } catch (error) {
        window.alert(
          "Falha ao reconhecer: "
          + error.message
        );
      }
    }

    document.getElementById(
      "refreshButton"
    ).addEventListener(
      "click",
      loadDashboard
    );

    document.getElementById(
      "captureButton"
    ).addEventListener(
      "click",
      captureAlerts
    );

    loadDashboard();
    setInterval(loadDashboard, 15000);
  </script>
</body>
</html>
"""


def _journal() -> PaperIncidentJournal:
    return PaperIncidentJournal()


def _monitor() -> PaperPerformanceMonitor:
    return PaperPerformanceMonitor()


def _csv_value(
    value: Any,
) -> Any:
    if value is None:
        return ""

    return value


@router.get(
    "/dashboard",
    response_class=HTMLResponse,
)
async def incident_dashboard():
    return HTMLResponse(
        content=DASHBOARD_HTML,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-PredArb-Financial-Execution": "false",
        },
    )


@router.get("/snapshot")
async def incident_dashboard_snapshot(
    active_limit: int = Query(
        default=100,
        ge=1,
        le=1000,
    ),
    history_limit: int = Query(
        default=250,
        ge=1,
        le=1000,
    ),
):
    journal = _journal()

    return {
        "summary": journal.summary(),
        "active": journal.list_incidents(
            status="ACTIVE",
            limit=active_limit,
        ),
        "history": journal.list_incidents(
            limit=history_limit,
        ),
        "monitor": _monitor().snapshot(),
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "journal_actions_supported": True,
    }


@router.get("/export.csv")
async def incident_export_csv(
    limit: int = Query(
        default=1000,
        ge=1,
        le=1000,
    ),
):
    incidents = _journal().list_incidents(
        limit=limit
    )

    fieldnames = [
        "id",
        "status",
        "severity",
        "code",
        "title",
        "message",
        "current_value",
        "threshold",
        "occurrences",
        "first_seen_at",
        "last_seen_at",
        "resolved_at",
        "acknowledged_at",
    ]

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=fieldnames,
        extrasaction="ignore",
    )

    writer.writeheader()

    for incident in incidents:
        writer.writerow(
            {
                field: _csv_value(
                    incident.get(field)
                )
                for field in fieldnames
            }
        )

    return Response(
        content="\ufeff" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                "attachment; "
                'filename="predarb-paper-incidents.csv"'
            ),
            "Cache-Control": "no-store",
            "X-PredArb-Financial-Execution": "false",
        },
    )
