from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, Response

from app.paper.final_paper_validation_evidence_incidents import (
    FinalPaperEvidenceIncidentJournal,
)
from app.paper.final_paper_validation_evidence_monitor import (
    final_paper_validation_evidence_monitor,
)


router = APIRouter(
    prefix="/paper/final-validation/evidence/incidents/ui",
    tags=["paper-final-validation-evidence-incidents-dashboard"],
)


DASHBOARD_HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta
    name="viewport"
    content="width=device-width, initial-scale=1"
  >
  <title>PredArb | Incidentes das Evidências Finais</title>

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
    .badges {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }

    .badges {
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

    button.primary {
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

    .grid {
      display: grid;
      grid-template-columns:
        repeat(auto-fit, minmax(165px, 1fr));
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

    .label {
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 12px;
    }

    .value {
      font-size: 25px;
      font-weight: 780;
      letter-spacing: -0.04em;
    }

    .panel {
      margin-bottom: 18px;
      padding: 20px;
      overflow: hidden;
    }

    .table-wrap {
      overflow-x: auto;
    }

    table {
      width: 100%;
      min-width: 1450px;
      border-collapse: collapse;
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
      font-weight: 650;
    }

    .critical {
      color: var(--critical);
      font-weight: 760;
    }

    .warning {
      color: var(--warning);
      font-weight: 760;
    }

    .info {
      color: var(--info);
      font-weight: 760;
    }

    .active {
      color: var(--critical);
      font-weight: 760;
    }

    .resolved {
      color: var(--good);
      font-weight: 760;
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
        <h1>Incidentes das Evidências Finais</h1>
        <p class="muted">
          Visão operacional dos alertas persistidos pelo monitor.
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
          class="primary"
          type="button"
        >
          Capturar monitor
        </button>

        <a
          class="button"
          href="/paper/final-validation/evidence/incidents/ui/export.csv"
        >
          Exportar CSV
        </a>

        <a
          class="button"
          href="/paper/final-validation/evidence/monitor/dashboard"
        >
          Monitor
        </a>

        <a
          class="button"
          href="/paper/final-validation/evidence/dashboard"
        >
          Evidências
        </a>
      </div>
    </header>

    <section class="badges">
      <span class="badge">
        Captura manual confirmada
      </span>
      <span class="badge">
        Reconhecimento administrativo
      </span>
      <span class="badge">
        Próxima fase não autorizada
      </span>
      <span class="badge">
        Execução financeira bloqueada
      </span>
    </section>

    <section
      id="summaryGrid"
      class="grid"
    ></section>

    <section class="panel">
      <h2>Incidentes ativos</h2>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Severidade</th>
              <th>Código</th>
              <th>Título</th>
              <th>Primeiro registro</th>
              <th>Último registro</th>
              <th>Ocorrências</th>
              <th>Reativações</th>
              <th>Reconhecido por</th>
              <th>Ação</th>
            </tr>
          </thead>

          <tbody id="activeBody"></tbody>
        </table>
      </div>
    </section>

    <section class="panel">
      <h2>Histórico completo</h2>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Status</th>
              <th>Severidade</th>
              <th>Código</th>
              <th>Título</th>
              <th>Primeiro registro</th>
              <th>Último registro</th>
              <th>Resolvido em</th>
              <th>Ocorrências</th>
              <th>Reconhecido por</th>
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
          throw new Error(
            `Guarda de segurança inválida: ${field}`
          );
        }
      }

      if (payload.read_only !== true) {
        throw new Error(
          "Payload não está marcado como somente leitura."
        );
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
      return String(
        value || ""
      ).toLowerCase();
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

    function card(label, value, className = "") {
      return `
        <article class="card">
          <div class="label">
            ${escapeHtml(label)}
          </div>
          <div class="value ${className}">
            ${escapeHtml(value)}
          </div>
        </article>
      `;
    }

    function render(payload) {
      ensureSafe(payload);

      const summary = payload.summary || {};
      const monitor = payload.monitor || {};
      const active = payload.active || [];
      const history = payload.history || [];

      document.getElementById(
        "summaryGrid"
      ).innerHTML = [
        card(
          "Monitor",
          monitor.status || "-",
          css(monitor.status)
        ),
        card(
          "Score do monitor",
          Number(
            monitor.score || 0
          ).toFixed(0)
        ),
        card(
          "Incidentes ativos",
          integer.format(
            Number(
              summary.active_incidents || 0
            )
          )
        ),
        card(
          "Críticos ativos",
          integer.format(
            Number(
              summary.active_critical || 0
            )
          ),
          (
            Number(
              summary.active_critical || 0
            ) > 0
              ? "critical"
              : ""
          )
        ),
        card(
          "Warnings ativos",
          integer.format(
            Number(
              summary.active_warning || 0
            )
          )
        ),
        card(
          "Resolvidos",
          integer.format(
            Number(
              summary.resolved_incidents || 0
            )
          )
        ),
        card(
          "Não reconhecidos",
          integer.format(
            Number(
              summary.unacknowledged_active || 0
            )
          )
        ),
        card(
          "Snapshots",
          integer.format(
            Number(
              summary.total_snapshots || 0
            )
          )
        )
      ].join("");

      const activeBody = document.getElementById(
        "activeBody"
      );

      if (!active.length) {
        activeBody.innerHTML = `
          <tr>
            <td colspan="9" class="muted">
              Nenhum incidente ativo.
            </td>
          </tr>
        `;
      } else {
        activeBody.innerHTML = active.map(
          (item) => `
            <tr>
              <td class="${css(item.severity)}">
                ${escapeHtml(item.severity)}
              </td>
              <td>${escapeHtml(item.code)}</td>
              <td>${escapeHtml(item.title)}</td>
              <td>${dateTime(item.first_seen_at)}</td>
              <td>${dateTime(item.last_seen_at)}</td>
              <td>
                ${integer.format(
                  Number(item.occurrences || 0)
                )}
              </td>
              <td>
                ${integer.format(
                  Number(item.reactivations || 0)
                )}
              </td>
              <td>
                ${escapeHtml(
                  item.acknowledged_by || "-"
                )}
              </td>
              <td>
                <button
                  type="button"
                  data-incident-id="${escapeHtml(item.id)}"
                  onclick="acknowledgeIncident(this.dataset.incidentId)"
                >
                  Reconhecer
                </button>
              </td>
            </tr>
          `
        ).join("");
      }

      const historyBody = document.getElementById(
        "historyBody"
      );

      if (!history.length) {
        historyBody.innerHTML = `
          <tr>
            <td colspan="9" class="muted">
              Nenhum incidente registrado.
            </td>
          </tr>
        `;
      } else {
        historyBody.innerHTML = history.map(
          (item) => `
            <tr>
              <td class="${css(item.status)}">
                ${escapeHtml(item.status)}
              </td>
              <td class="${css(item.severity)}">
                ${escapeHtml(item.severity)}
              </td>
              <td>${escapeHtml(item.code)}</td>
              <td>${escapeHtml(item.title)}</td>
              <td>${dateTime(item.first_seen_at)}</td>
              <td>${dateTime(item.last_seen_at)}</td>
              <td>${dateTime(item.resolved_at)}</td>
              <td>
                ${integer.format(
                  Number(item.occurrences || 0)
                )}
              </td>
              <td>
                ${escapeHtml(
                  item.acknowledged_by || "-"
                )}
              </td>
            </tr>
          `
        ).join("");
      }
    }

    async function refresh() {
      const button = document.getElementById(
        "refreshButton"
      );

      button.disabled = true;
      button.textContent = "Atualizando...";

      try {
        const response = await fetch(
          "/paper/final-validation/"
          + "evidence/incidents/ui/snapshot",
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
          + " | Capturas e reconhecimentos exigem confirmação"
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

    async function captureMonitor() {
      const confirmed = window.confirm(
        "Capturar o estado atual do monitor e atualizar o diário de incidentes?"
      );

      if (!confirmed) {
        return;
      }

      const response = await fetch(
        "/paper/final-validation/"
        + "evidence/incidents/capture"
        + "?confirm=CAPTURE-FINAL-PAPER-EVIDENCE-INCIDENTS",
        {
          method: "POST"
        }
      );

      if (!response.ok) {
        throw new Error(
          `HTTP ${response.status}: `
          + await response.text()
        );
      }

      const payload = await response.json();
      ensureSafe(payload);
      await refresh();
    }

    async function acknowledgeIncident(
      incidentId
    ) {
      const operator = window.prompt(
        "Informe o nome do operador:",
        "administrador"
      );

      if (operator === null) {
        return;
      }

      const confirmed = window.confirm(
        "Reconhecer administrativamente este incidente?"
      );

      if (!confirmed) {
        return;
      }

      const response = await fetch(
        "/paper/final-validation/"
        + "evidence/incidents/"
        + encodeURIComponent(incidentId)
        + "/acknowledge"
        + "?confirm=ACK-FINAL-PAPER-EVIDENCE-INCIDENT"
        + "&operator="
        + encodeURIComponent(
            operator || "administrador"
          ),
        {
          method: "POST"
        }
      );

      if (!response.ok) {
        throw new Error(
          `HTTP ${response.status}: `
          + await response.text()
        );
      }

      const payload = await response.json();
      ensureSafe(payload);
      await refresh();
    }

    async function guarded(action) {
      try {
        await action();
      } catch (error) {
        window.alert(
          "Operação não concluída: "
          + error.message
        );
      }
    }

    document.getElementById(
      "refreshButton"
    ).addEventListener(
      "click",
      refresh
    );

    document.getElementById(
      "captureButton"
    ).addEventListener(
      "click",
      () => guarded(captureMonitor)
    );

    window.acknowledgeIncident = (
      incidentId
    ) => guarded(
      () => acknowledgeIncident(
        incidentId
      )
    );

    refresh();
    setInterval(refresh, 10000);
  </script>
</body>
</html>
"""


def _journal() -> FinalPaperEvidenceIncidentJournal:
    return FinalPaperEvidenceIncidentJournal()


def _safe_flags() -> dict[str, bool]:
    return {
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "next_step_authorized": False,
        "read_only": True,
    }


@router.get(
    "/dashboard",
    response_class=HTMLResponse,
)
async def final_evidence_incident_dashboard():
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


@router.get("/snapshot")
async def final_evidence_incident_dashboard_snapshot():
    journal = _journal()
    monitor = (
        final_paper_validation_evidence_monitor
        .evaluate()
    )

    return {
        "summary": journal.summary(),
        "monitor": {
            "status": monitor.get("status"),
            "score": monitor.get("score"),
            "summary": monitor.get("summary"),
        },
        "active": journal.list_incidents(
            status="ACTIVE",
            limit=500,
        ),
        "history": journal.list_incidents(
            limit=1000,
        ),
        **_safe_flags(),
    }


@router.get("/export.csv")
async def final_evidence_incident_dashboard_export_csv(
    limit: int = Query(
        default=5000,
        ge=1,
        le=5000,
    ),
):
    incidents = (
        _journal()
        .list_incidents(
            limit=limit
        )
    )

    fieldnames = [
        "id",
        "status",
        "severity",
        "code",
        "title",
        "message",
        "first_seen_at",
        "last_seen_at",
        "resolved_at",
        "occurrences",
        "reactivations",
        "acknowledged_at",
        "acknowledged_by",
        "current_value",
        "expected_value",
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
                field: incident.get(field)
                for field in fieldnames
            }
        )

    return Response(
        content=(
            "\ufeff"
            + buffer.getvalue()
        ),
        media_type=(
            "text/csv; charset=utf-8"
        ),
        headers={
            "Content-Disposition": (
                "attachment; "
                'filename="predarb-final-evidence-incidents.csv"'
            ),
            "Cache-Control": "no-store",
            "X-PredArb-Live-Authorization": "false",
            "X-PredArb-Financial-Execution": "false",
            "X-PredArb-Next-Step-Authorization": "false",
        },
    )
