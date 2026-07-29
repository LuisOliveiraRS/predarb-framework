from __future__ import annotations

import csv
import io
import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, Response

from app.paper.final_paper_assurance_qualification_gate import (
    final_paper_assurance_qualification_gate,
)
from app.paper.final_paper_assurance_qualification_gate_history import (
    FinalPaperAssuranceQualificationGateHistory,
)


router = APIRouter(
    prefix=(
        "/paper/final-assurance/"
        "qualification-gate/history"
    ),
    tags=[
        "paper-final-assurance-qualification-gate-history"
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
  <title>PredArb | Histórico do Gate de Qualificação</title>
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

    .chart {
      width: 100%;
      min-height: 260px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: rgba(0, 0, 0, 0.2);
    }

    .table-wrap {
      overflow-x: auto;
    }

    table {
      width: 100%;
      min-width: 1500px;
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

    .qualified {
      color: var(--good);
      font-weight: 760;
    }

    .pending,
    .no_data {
      color: var(--warning);
      font-weight: 760;
    }

    .blocked {
      color: var(--critical);
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
        <h1>Histórico do Gate de Qualificação</h1>
        <p class="muted">
          Evolução persistente da qualificação técnica final do ambiente Paper.
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
          Registrar gate
        </button>

        <a
          class="button"
          href="/paper/final-assurance/qualification-gate/history/export.csv"
        >
          CSV
        </a>

        <a
          class="button"
          href="/paper/final-assurance/qualification-gate/history/export.json"
        >
          JSON
        </a>

        <a
          class="button"
          href="/paper/final-assurance/qualification-gate/dashboard"
        >
          Gate atual
        </a>
      </div>
    </header>

    <section class="badges">
      <span class="badge">
        Captura manual confirmada
      </span>
      <span class="badge">
        Escopo Paper somente leitura
      </span>
      <span class="badge">
        Próxima fase não autorizada
      </span>
      <span class="badge">
        Execução live e financeira bloqueada
      </span>
    </section>

    <section
      id="summaryGrid"
      class="grid"
    ></section>

    <section class="panel">
      <h2>Evolução do score de qualificação</h2>

      <svg
        id="scoreChart"
        class="chart"
        viewBox="0 0 1000 260"
        preserveAspectRatio="none"
        role="img"
        aria-label="Evolução do score de qualificação"
      ></svg>
    </section>

    <section class="panel">
      <h2>Avaliações registradas</h2>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Status</th>
              <th>Capturado em</th>
              <th>Score</th>
              <th>Garantia</th>
              <th>Score garantia</th>
              <th>Histórico</th>
              <th>Sequência</th>
              <th>Integridade</th>
              <th>Monitor</th>
              <th>Incidentes</th>
              <th>Falhas runtime</th>
              <th>Códigos</th>
            </tr>
          </thead>

          <tbody id="entriesBody"></tbody>
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

    function renderChart(entries) {
      const svg = document.getElementById(
        "scoreChart"
      );

      const ordered = [...entries]
        .reverse()
        .slice(-100);

      if (!ordered.length) {
        svg.innerHTML = `
          <text
            x="500"
            y="135"
            text-anchor="middle"
            fill="#9ca9b5"
            font-size="22"
          >
            Nenhum gate registrado
          </text>
        `;
        return;
      }

      const width = 1000;
      const height = 260;
      const padding = 26;
      const usableWidth = width - padding * 2;
      const usableHeight = height - padding * 2;

      const points = ordered.map(
        (entry, index) => {
          const x = (
            ordered.length === 1
              ? width / 2
              : padding
                + index
                * usableWidth
                / (ordered.length - 1)
          );

          const score = Math.max(
            0,
            Math.min(
              100,
              Number(
                entry.qualification_score || 0
              )
            )
          );

          const y = (
            padding
            + (100 - score)
            / 100
            * usableHeight
          );

          return {
            x,
            y,
            score,
            status: entry.status
          };
        }
      );

      const polyline = points
        .map(
          (point) => (
            `${point.x},${point.y}`
          )
        )
        .join(" ");

      const lines = [
        [100, "100"],
        [79, "79"],
        [59, "59"],
        [49, "49"],
        [0, "0"]
      ].map(([score, label]) => {
        const y = (
          padding
          + (100 - score)
          / 100
          * usableHeight
        );

        return `
          <line
            x1="${padding}"
            y1="${y}"
            x2="${width - padding}"
            y2="${y}"
            stroke="#2b333d"
            stroke-width="1"
          />
          <text
            x="4"
            y="${y + 4}"
            fill="#9ca9b5"
            font-size="11"
          >
            ${label}
          </text>
        `;
      }).join("");

      const circles = points.map(
        (point) => `
          <circle
            cx="${point.x}"
            cy="${point.y}"
            r="4"
            fill="#ff6a00"
          >
            <title>
              ${escapeHtml(point.status)} — ${point.score.toFixed(2)}
            </title>
          </circle>
        `
      ).join("");

      svg.innerHTML = `
        ${lines}
        <polyline
          points="${polyline}"
          fill="none"
          stroke="#ff6a00"
          stroke-width="3"
          vector-effect="non-scaling-stroke"
        />
        ${circles}
      `;
    }

    function render(payload) {
      ensureSafe(payload);

      const summary = payload.summary || {};
      const entries = payload.entries || [];

      document.getElementById(
        "summaryGrid"
      ).innerHTML = [
        card(
          "Registros",
          integer.format(
            Number(summary.total_entries || 0)
          )
        ),
        card(
          "Último status",
          summary.latest_status || "-",
          css(summary.latest_status)
        ),
        card(
          "Último score",
          (
            summary.latest_score === null
              ? "-"
              : Number(
                  summary.latest_score
                ).toFixed(2)
          )
        ),
        card(
          "Score médio",
          (
            summary.average_score === null
              ? "-"
              : Number(
                  summary.average_score
                ).toFixed(2)
          )
        ),
        card(
          "Sequência atual",
          integer.format(
            Number(summary.current_streak || 0)
          )
        ),
        card(
          "Maior sequência QUALIFIED",
          integer.format(
            Number(
              summary.longest_qualified_streak || 0
            )
          )
        ),
        card(
          "Transições",
          integer.format(
            Number(summary.transitions || 0)
          )
        ),
        card(
          "QUALIFIED",
          integer.format(
            Number(
              (
                summary.status_counts
                || {}
              ).QUALIFIED
              || 0
            )
          ),
          "qualified"
        )
      ].join("");

      renderChart(entries);

      const body = document.getElementById(
        "entriesBody"
      );

      if (!entries.length) {
        body.innerHTML = `
          <tr>
            <td colspan="12" class="muted">
              Nenhum gate registrado.
            </td>
          </tr>
        `;
        return;
      }

      body.innerHTML = entries.map(
        (entry) => {
          const details = entry.summary || {};

          return `
            <tr>
              <td class="${css(entry.status)}">
                ${escapeHtml(entry.status)}
              </td>
              <td>${dateTime(entry.captured_at)}</td>
              <td>
                ${Number(
                  entry.qualification_score || 0
                ).toFixed(2)}
              </td>
              <td>
                ${escapeHtml(
                  details.assurance_status || "-"
                )}
              </td>
              <td>
                ${Number(
                  details.assurance_score || 0
                ).toFixed(2)}
              </td>
              <td>
                ${integer.format(
                  Number(details.history_entries || 0)
                )}
              </td>
              <td>
                ${escapeHtml(
                  details.current_streak_status || "-"
                )}
                /
                ${integer.format(
                  Number(details.current_streak || 0)
                )}
              </td>
              <td>
                ${escapeHtml(
                  details.integrity_status || "-"
                )}
              </td>
              <td>
                ${escapeHtml(
                  details.monitor_status || "-"
                )}
              </td>
              <td>
                ${integer.format(
                  Number(details.active_incidents || 0)
                )}
              </td>
              <td>
                ${integer.format(
                  Number(
                    details.total_runtime_failures || 0
                  )
                )}
              </td>
              <td>
                ${escapeHtml(
                  (entry.failure_codes || []).join(", ")
                  || "-"
                )}
              </td>
            </tr>
          `;
        }
      ).join("");
    }

    async function refresh() {
      const button = document.getElementById(
        "refreshButton"
      );

      button.disabled = true;
      button.textContent = "Atualizando...";

      try {
        const response = await fetch(
          "/paper/final-assurance/"
          + "qualification-gate/history/snapshot?limit=500",
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
          + " | Captura manual | Ambiente Paper"
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

    async function capture() {
      const confirmed = window.confirm(
        "Registrar o estado atual do gate de qualificação?"
      );

      if (!confirmed) {
        return;
      }

      const button = document.getElementById(
        "captureButton"
      );

      button.disabled = true;
      button.textContent = "Registrando...";

      try {
        const response = await fetch(
          "/paper/final-assurance/"
          + "qualification-gate/history/capture"
          + "?confirm=CAPTURE-FINAL-PAPER-ASSURANCE-QUALIFICATION-GATE",
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
      } catch (error) {
        window.alert(
          "Falha no registro: "
          + error.message
        );
      } finally {
        button.disabled = false;
        button.textContent = "Registrar gate";
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
      capture
    );

    refresh();
    setInterval(refresh, 15000);
  </script>
</body>
</html>
"""


def _history() -> FinalPaperAssuranceQualificationGateHistory:
    return FinalPaperAssuranceQualificationGateHistory()


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


@router.get("/health")
async def qualification_gate_history_health():
    summary = _history().summary()

    return {
        "status": "healthy",
        "total_entries": (
            summary["total_entries"]
        ),
        "latest_status": (
            summary["latest_status"]
        ),
        **_safe_flags(),
    }


@router.get("/summary")
async def qualification_gate_history_summary():
    return _history().summary()


@router.get("/latest")
async def qualification_gate_history_latest():
    return {
        "entry": _history().latest(),
        **_safe_flags(),
    }


@router.get("/entries")
async def qualification_gate_history_entries(
    limit: int = Query(
        default=500,
        ge=1,
        le=5000,
    ),
):
    entries = _history().list_entries(
        limit=limit
    )

    return {
        "count": len(entries),
        "entries": entries,
        **_safe_flags(),
    }


@router.get("/snapshot")
async def qualification_gate_history_snapshot(
    limit: int = Query(
        default=500,
        ge=1,
        le=5000,
    ),
):
    history = _history()

    return {
        "summary": history.summary(),
        "latest": history.latest(),
        "entries": history.list_entries(
            limit=limit
        ),
        **_safe_flags(),
    }


@router.post("/capture")
async def qualification_gate_history_capture(
    confirm: str = Query(...),
):
    if (
        confirm
        != (
            "CAPTURE-FINAL-PAPER-ASSURANCE-"
            "QUALIFICATION-GATE"
        )
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Confirmação inválida. Use "
                "CAPTURE-FINAL-PAPER-ASSURANCE-"
                "QUALIFICATION-GATE."
            ),
        )

    try:
        report = (
            final_paper_assurance_qualification_gate
            .evaluate()
        )

        return _history().capture(
            report
        )

    except (
        RuntimeError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


@router.get(
    "/dashboard",
    response_class=HTMLResponse,
)
async def qualification_gate_history_dashboard():
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


@router.get("/export.csv")
async def qualification_gate_history_export_csv(
    limit: int = Query(
        default=5000,
        ge=1,
        le=5000,
    ),
):
    entries = _history().list_entries(
        limit=limit
    )

    fieldnames = [
        "id",
        "captured_at",
        "report_generated_at",
        "status",
        "qualified",
        "scope",
        "qualification_score",
        "total_checks",
        "passed_checks",
        "failed_checks",
        "critical_failures",
        "warning_failures",
        "assurance_status",
        "assurance_score",
        "history_entries",
        "latest_history_status",
        "latest_history_score",
        "average_history_score",
        "current_streak_status",
        "current_streak",
        "integrity_status",
        "monitor_status",
        "active_incidents",
        "active_critical_incidents",
        "component_errors",
        "total_runtime_failures",
        "history_runtime_status",
        "failure_codes",
    ]

    buffer = io.StringIO()

    writer = csv.DictWriter(
        buffer,
        fieldnames=fieldnames,
        extrasaction="ignore",
    )

    writer.writeheader()

    for entry in entries:
        summary = (
            entry.get("summary")
            or {}
        )

        writer.writerow(
            {
                "id": entry.get("id"),
                "captured_at": (
                    entry.get(
                        "captured_at"
                    )
                ),
                "report_generated_at": (
                    entry.get(
                        "report_generated_at"
                    )
                ),
                "status": entry.get(
                    "status"
                ),
                "qualified": entry.get(
                    "qualified"
                ),
                "scope": entry.get(
                    "scope"
                ),
                "qualification_score": (
                    entry.get(
                        "qualification_score"
                    )
                ),
                "total_checks": (
                    summary.get(
                        "total_checks"
                    )
                ),
                "passed_checks": (
                    summary.get(
                        "passed_checks"
                    )
                ),
                "failed_checks": (
                    summary.get(
                        "failed_checks"
                    )
                ),
                "critical_failures": (
                    summary.get(
                        "critical_failures"
                    )
                ),
                "warning_failures": (
                    summary.get(
                        "warning_failures"
                    )
                ),
                "assurance_status": (
                    summary.get(
                        "assurance_status"
                    )
                ),
                "assurance_score": (
                    summary.get(
                        "assurance_score"
                    )
                ),
                "history_entries": (
                    summary.get(
                        "history_entries"
                    )
                ),
                "latest_history_status": (
                    summary.get(
                        "latest_history_status"
                    )
                ),
                "latest_history_score": (
                    summary.get(
                        "latest_history_score"
                    )
                ),
                "average_history_score": (
                    summary.get(
                        "average_history_score"
                    )
                ),
                "current_streak_status": (
                    summary.get(
                        "current_streak_status"
                    )
                ),
                "current_streak": (
                    summary.get(
                        "current_streak"
                    )
                ),
                "integrity_status": (
                    summary.get(
                        "integrity_status"
                    )
                ),
                "monitor_status": (
                    summary.get(
                        "monitor_status"
                    )
                ),
                "active_incidents": (
                    summary.get(
                        "active_incidents"
                    )
                ),
                "active_critical_incidents": (
                    summary.get(
                        "active_critical_incidents"
                    )
                ),
                "component_errors": (
                    summary.get(
                        "component_errors"
                    )
                ),
                "total_runtime_failures": (
                    summary.get(
                        "total_runtime_failures"
                    )
                ),
                "history_runtime_status": (
                    summary.get(
                        "history_runtime_status"
                    )
                ),
                "failure_codes": ",".join(
                    entry.get(
                        "failure_codes"
                    )
                    or []
                ),
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
                'filename="predarb-final-paper-'
                'assurance-qualification-gate-history.csv"'
            ),
            "Cache-Control": "no-store",
            "X-PredArb-Live-Authorization": "false",
            "X-PredArb-Financial-Execution": "false",
            "X-PredArb-Next-Step-Authorization": "false",
        },
    )


@router.get("/export.json")
async def qualification_gate_history_export_json():
    history = _history()

    payload = {
        "summary": history.summary(),
        "entries": history.list_entries(
            limit=5000
        ),
        **_safe_flags(),
    }

    return Response(
        content=json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        media_type="application/json",
        headers={
            "Content-Disposition": (
                "attachment; "
                'filename="predarb-final-paper-'
                'assurance-qualification-gate-history.json"'
            ),
            "Cache-Control": "no-store",
            "X-PredArb-Live-Authorization": "false",
            "X-PredArb-Financial-Execution": "false",
            "X-PredArb-Next-Step-Authorization": "false",
        },
    )
