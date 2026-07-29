from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, Response

from app.paper.certification_evidence_incidents import (
    PaperCertificationEvidenceIncidentJournal,
)
from app.paper.certification_evidence_monitor import (
    paper_certification_evidence_monitor,
)


router = APIRouter(
    prefix="/paper/certification/evidence/incidents/ui",
    tags=["paper-certification-evidence-incidents-ui"],
)


DASHBOARD_HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta
    name="viewport"
    content="width=device-width, initial-scale=1"
  >
  <title>PredArb | Incidentes das Evidências</title>

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

    button.primary {
      border-color: var(--accent);
      background: var(--accent);
      color: #111;
      font-weight: 760;
    }

    button.small {
      min-height: 34px;
      padding: 0 12px;
      font-size: 12px;
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
        repeat(auto-fit, minmax(160px, 1fr));
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
      font-size: 25px;
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
      gap: 16px;
      padding: 16px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.02);
    }

    .table-wrap {
      overflow-x: auto;
    }

    table {
      width: 100%;
      min-width: 1220px;
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

    td.message {
      max-width: 360px;
      overflow: hidden;
      text-overflow: ellipsis;
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

    .active,
    .healthy {
      color: var(--good);
      font-weight: 760;
    }

    .resolved {
      color: var(--muted);
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

      .monitor-line {
        align-items: flex-start;
        flex-direction: column;
      }
    }
  </style>
</head>

<body>
  <main>
    <header>
      <div>
        <h1>Incidentes das Evidências</h1>
        <p class="muted">
          Gestão operacional dos alertas do monitor de integridade.
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
          href="/paper/certification/evidence/incidents/ui/export.csv"
        >
          Exportar CSV
        </a>

        <a
          class="button"
          href="/paper/certification/evidence/monitor/dashboard"
        >
          Monitor
        </a>
      </div>
    </header>

    <section class="safety">
      <span class="badge">
        Captura manual confirmada
      </span>
      <span class="badge">
        Reconhecimento não resolve alerta
      </span>
      <span class="badge">
        Execução live bloqueada
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
      <h2>Estado do monitor</h2>

      <div
        id="monitorLine"
        class="monitor-line"
      >
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
      <h2>Histórico</h2>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Status</th>
              <th>Severidade</th>
              <th>Código</th>
              <th>Título</th>
              <th>Ocorrências</th>
              <th>Reativações</th>
              <th>Primeira ocorrência</th>
              <th>Última ocorrência</th>
              <th>Resolvido em</th>
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

    function normalizeClass(value) {
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

    function card(label, value) {
      return `
        <article class="card">
          <div class="card-label">
            ${escapeHtml(label)}
          </div>
          <div class="card-value">
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

      const summary = payload.summary || {};
      const monitor = payload.monitor || {};
      const active = payload.active || [];
      const history = payload.history || [];

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
          "Informativos ativos",
          integer.format(
            Number(summary.active_info || 0)
          )
        ),
        card(
          "Resolvidos",
          integer.format(
            Number(summary.resolved_incidents || 0)
          )
        ),
        card(
          "Snapshots",
          integer.format(
            Number(summary.snapshots || 0)
          )
        )
      ].join("");

      document.getElementById(
        "monitorLine"
      ).innerHTML = `
        <div>
          <strong class="${normalizeClass(
            monitor.status
          )}">
            ${escapeHtml(monitor.status || "-")}
          </strong>

          <div class="muted">
            Score: ${Number(
              monitor.score || 0
            ).toFixed(0)}
          </div>
        </div>

        <div class="muted">
          Cadeia:
          ${escapeHtml(
            monitor.diagnostics
              ? monitor.diagnostics.chain_status
              : "-"
          )}
        </div>
      `;

      const activeBody = document.getElementById(
        "activeBody"
      );

      if (!active.length) {
        activeBody.innerHTML = `
          <tr>
            <td colspan="8" class="muted">
              Nenhum incidente ativo.
            </td>
          </tr>
        `;
      } else {
        activeBody.innerHTML = active.map(
          (item) => `
            <tr>
              <td class="${normalizeClass(
                item.severity
              )}">
                ${escapeHtml(
                  item.severity
                ).toUpperCase()}
              </td>
              <td>${escapeHtml(item.code)}</td>
              <td>${escapeHtml(item.title)}</td>
              <td
                class="message"
                title="${escapeHtml(item.message)}"
              >
                ${escapeHtml(item.message)}
              </td>
              <td>${integer.format(
                Number(item.occurrences || 0)
              )}</td>
              <td>${dateTime(item.last_seen_at)}</td>
              <td>
                ${item.acknowledged ? "SIM" : "NÃO"}
              </td>
              <td>
                ${
                  item.acknowledged
                    ? "-"
                    : `
                      <button
                        type="button"
                        class="small"
                        data-incident-id="${escapeHtml(item.id)}"
                      >
                        Reconhecer
                      </button>
                    `
                }
              </td>
            </tr>
          `
        ).join("");
      }

      document.getElementById(
        "historyBody"
      ).innerHTML = history.length
        ? history.map(
            (item) => `
              <tr>
                <td class="${normalizeClass(
                  item.status
                )}">
                  ${escapeHtml(item.status)}
                </td>
                <td class="${normalizeClass(
                  item.severity
                )}">
                  ${escapeHtml(
                    item.severity
                  ).toUpperCase()}
                </td>
                <td>${escapeHtml(item.code)}</td>
                <td>${escapeHtml(item.title)}</td>
                <td>${integer.format(
                  Number(item.occurrences || 0)
                )}</td>
                <td>${integer.format(
                  Number(item.reactivations || 0)
                )}</td>
                <td>${dateTime(item.first_seen_at)}</td>
                <td>${dateTime(item.last_seen_at)}</td>
                <td>${dateTime(item.resolved_at)}</td>
              </tr>
            `
          ).join("")
        : `
          <tr>
            <td colspan="9" class="muted">
              Nenhum incidente registrado.
            </td>
          </tr>
        `;

      document.querySelectorAll(
        "[data-incident-id]"
      ).forEach(
        (button) => {
          button.addEventListener(
            "click",
            () => acknowledge(
              button.dataset.incidentId
            )
          );
        }
      );
    }

    async function loadSnapshot() {
      const response = await fetch(
        "/paper/certification/evidence/incidents/ui/snapshot"
        + "?limit=250",
        {
          cache: "no-store"
        }
      );

      if (!response.ok) {
        throw new Error(
          `HTTP ${response.status}`
        );
      }

      return response.json();
    }

    async function refresh() {
      const button = document.getElementById(
        "refreshButton"
      );

      button.disabled = true;
      button.textContent = "Atualizando...";

      try {
        const payload = await loadSnapshot();
        render(payload);

        document.getElementById(
          "lastUpdate"
        ).textContent = (
          "Última atualização: "
          + new Date().toLocaleString("pt-BR")
          + " | Nenhuma autorização financeira"
        );
      } catch (error) {
        document.getElementById(
          "lastUpdate"
        ).textContent = (
          "Falha ao carregar: "
          + error.message
        );
      } finally {
        button.disabled = false;
        button.textContent = "Atualizar";
      }
    }

    async function post(endpoint) {
      const response = await fetch(
        endpoint,
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

      return payload;
    }

    async function capture() {
      const confirmed = window.confirm(
        "Capturar os alertas atuais do monitor de evidências?"
      );

      if (!confirmed) {
        return;
      }

      await post(
        "/paper/certification/evidence/incidents/capture"
        + "?confirm=CAPTURE-PAPER-EVIDENCE-INCIDENTS"
      );

      await refresh();
    }

    async function acknowledge(incidentId) {
      const confirmed = window.confirm(
        "Reconhecer este incidente? O alerta não será resolvido por esta ação."
      );

      if (!confirmed) {
        return;
      }

      const note = window.prompt(
        "Observação opcional:",
        "Incidente analisado pelo operador."
      );

      const endpoint = (
        "/paper/certification/evidence/incidents/"
        + encodeURIComponent(incidentId)
        + "/acknowledge"
        + "?confirm=ACK-PAPER-EVIDENCE-INCIDENT"
        + "&acknowledged_by=operator"
        + "&note="
        + encodeURIComponent(note || "")
      );

      await post(endpoint);
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
      () => guarded(capture)
    );

    refresh();
    setInterval(refresh, 10000);
  </script>
</body>
</html>
"""


def _journal():
    return PaperCertificationEvidenceIncidentJournal()


def _safe_base() -> dict[str, bool]:
    return {
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "read_only": True,
    }


@router.get(
    "/dashboard",
    response_class=HTMLResponse,
)
async def evidence_incident_dashboard():
    return HTMLResponse(
        content=DASHBOARD_HTML,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-PredArb-Live-Authorization": "false",
            "X-PredArb-Financial-Execution": "false",
        },
    )


@router.get("/snapshot")
async def evidence_incident_dashboard_snapshot(
    limit: int = Query(
        default=250,
        ge=1,
        le=5000,
    ),
):
    journal = _journal()

    return {
        "summary": journal.summary(),
        "monitor": (
            paper_certification_evidence_monitor
            .snapshot()
        ),
        "active": journal.list_incidents(
            status="ACTIVE",
            limit=limit,
        ),
        "history": journal.list_incidents(
            limit=limit,
        ),
        "snapshots": journal.list_snapshots(
            limit=min(limit, 250),
        ),
        **_safe_base(),
    }


@router.get("/export.csv")
async def evidence_incident_dashboard_export_csv(
    limit: int = Query(
        default=5000,
        ge=1,
        le=5000,
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
        "first_seen_at",
        "last_seen_at",
        "resolved_at",
        "reactivated_at",
        "occurrences",
        "reactivations",
        "acknowledged",
        "acknowledged_at",
        "acknowledged_by",
        "acknowledgement_note",
    ]

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=fieldnames,
        extrasaction="ignore",
    )

    writer.writeheader()

    for incident in incidents:
        writer.writerow(incident)

    return Response(
        content="\ufeff" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                "attachment; "
                'filename="predarb-paper-evidence-incidents.csv"'
            ),
            "Cache-Control": "no-store",
            "X-PredArb-Live-Authorization": "false",
            "X-PredArb-Financial-Execution": "false",
        },
    )
