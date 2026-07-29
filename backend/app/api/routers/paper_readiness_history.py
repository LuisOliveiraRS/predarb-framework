from __future__ import annotations

import csv
import io

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)
from fastapi.responses import (
    HTMLResponse,
    Response,
)

from app.paper.readiness import (
    paper_readiness_gate,
)
from app.paper.readiness_history import (
    PaperReadinessHistory,
)


router = APIRouter(
    prefix="/paper/readiness/history",
    tags=["paper-readiness-history"],
)


DASHBOARD_HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta
    name="viewport"
    content="width=device-width, initial-scale=1"
  >
  <title>PredArb | Histórico de Readiness</title>

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
      font-size: 26px;
      font-weight: 780;
      letter-spacing: -0.04em;
    }

    .panel {
      margin-bottom: 18px;
      padding: 20px;
      overflow: hidden;
    }

    .chart {
      min-height: 280px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.02);
    }

    .chart-empty {
      display: grid;
      min-height: 280px;
      place-items: center;
      color: var(--muted);
    }

    .table-wrap {
      overflow-x: auto;
    }

    table {
      width: 100%;
      min-width: 980px;
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

    .ready {
      color: var(--ready);
      font-weight: 760;
    }

    .not_ready {
      color: var(--critical);
      font-weight: 760;
    }

    .insufficient_data {
      color: var(--warning);
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
        <h1>Histórico de Readiness</h1>
        <p class="muted">
          Evolução das avaliações do gate ao longo dos testes Paper.
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
          Capturar avaliação
        </button>

        <a
          class="button"
          href="/paper/readiness/history/export.csv"
        >
          Exportar CSV
        </a>

        <a
          class="button"
          href="/paper/readiness/dashboard"
        >
          Gate atual
        </a>
      </div>
    </header>

    <section class="safety">
      <span class="badge">
        Captura manual confirmada
      </span>
      <span class="badge">
        Execução live bloqueada
      </span>
      <span class="badge">
        Execução financeira bloqueada
      </span>
      <span class="badge">
        Histórico somente leitura
      </span>
    </section>

    <section
      id="summaryGrid"
      class="grid"
    ></section>

    <section class="panel">
      <h2>Evolução do score</h2>
      <div
        id="scoreChart"
        class="chart"
      ></div>
    </section>

    <section class="panel">
      <h2>Avaliações registradas</h2>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Status</th>
              <th>Capturada em</th>
              <th>Score</th>
              <th>Variação</th>
              <th>Aprovados</th>
              <th>Bloqueadores</th>
              <th>Warnings</th>
              <th>Dados insuficientes</th>
              <th>Operação</th>
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
        || payload.read_only !== true
      ) {
        throw new Error(
          "Guardas de segurança inválidas."
        );
      }
    }

    function renderSummary(summary) {
      document.getElementById(
        "summaryGrid"
      ).innerHTML = [
        card(
          "Avaliações",
          integer.format(
            Number(summary.total_entries || 0)
          )
        ),
        card(
          "READY",
          integer.format(
            Number(summary.ready_entries || 0)
          )
        ),
        card(
          "NOT READY",
          integer.format(
            Number(summary.not_ready_entries || 0)
          )
        ),
        card(
          "Dados insuficientes",
          integer.format(
            Number(
              summary.insufficient_data_entries
              || 0
            )
          )
        ),
        card(
          "Sequência atual",
          integer.format(
            Number(summary.current_streak || 0)
          )
        ),
        card(
          "Maior sequência READY",
          integer.format(
            Number(
              summary.longest_ready_streak
              || 0
            )
          )
        )
      ].join("");
    }

    function renderHistory(entries) {
      const body = document.getElementById(
        "historyBody"
      );

      if (!entries.length) {
        body.innerHTML = `
          <tr>
            <td colspan="9" class="muted">
              Nenhuma avaliação capturada.
            </td>
          </tr>
        `;
        return;
      }

      body.innerHTML = entries.map(
        (entry) => `
          <tr>
            <td class="${normalizeClass(
              entry.status
            )}">
              ${escapeHtml(entry.status)}
            </td>
            <td>${dateTime(entry.captured_at)}</td>
            <td>
              ${Number(entry.readiness_score || 0).toFixed(2)}
            </td>
            <td>
              ${
                entry.score_delta === null
                ? "-"
                : Number(entry.score_delta).toFixed(2)
              }
            </td>
            <td>${integer.format(
              Number(entry.passed_checks || 0)
            )}</td>
            <td>${integer.format(
              Number(entry.blockers || 0)
            )}</td>
            <td>${integer.format(
              Number(entry.warnings || 0)
            )}</td>
            <td>${integer.format(
              Number(entry.insufficient_data || 0)
            )}</td>
            <td>
              ${escapeHtml(
                entry.operations_status || "-"
              )}
            </td>
          </tr>
        `
      ).join("");
    }

    function renderChart(entries) {
      const host = document.getElementById(
        "scoreChart"
      );

      const ordered = [...entries].reverse();

      if (ordered.length < 2) {
        host.innerHTML = `
          <div class="chart-empty">
            Capture ao menos duas avaliações para formar a curva.
          </div>
        `;
        return;
      }

      const width = 1100;
      const height = 280;
      const padding = 32;

      const points = ordered.map(
        (entry) => Number(
          entry.readiness_score || 0
        )
      );

      const polyline = points.map(
        (value, index) => {
          const x = (
            padding
            + (
              index
              / Math.max(
                points.length - 1,
                1
              )
            )
            * (width - padding * 2)
          );

          const y = (
            height
            - padding
            - (
              value / 100
            )
            * (height - padding * 2)
          );

          return `${x.toFixed(2)},${y.toFixed(2)}`;
        }
      ).join(" ");

      host.innerHTML = `
        <svg
          viewBox="0 0 ${width} ${height}"
          width="100%"
          height="280"
          role="img"
          aria-label="Evolução do score de readiness"
        >
          <line
            x1="${padding}"
            y1="${height - padding}"
            x2="${width - padding}"
            y2="${height - padding}"
            stroke="#2b333d"
          ></line>

          <line
            x1="${padding}"
            y1="${
              height
              - padding
              - 0.75
              * (height - padding * 2)
            }"
            x2="${width - padding}"
            y2="${
              height
              - padding
              - 0.75
              * (height - padding * 2)
            }"
            stroke="#f6c453"
            stroke-dasharray="8 8"
          ></line>

          <polyline
            points="${polyline}"
            fill="none"
            stroke="#ff6a00"
            stroke-width="4"
            stroke-linecap="round"
            stroke-linejoin="round"
          ></polyline>

          <text
            x="${padding}"
            y="20"
            fill="#9ca9b5"
            font-size="13"
          >
            100
          </text>

          <text
            x="${padding}"
            y="${height - 8}"
            fill="#9ca9b5"
            font-size="13"
          >
            0
          </text>
        </svg>
      `;
    }

    async function loadSnapshot() {
      const response = await fetch(
        "/paper/readiness/history/snapshot"
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
        ensureSafe(payload);

        renderSummary(payload.summary || {});
        renderHistory(payload.entries || []);
        renderChart(payload.entries || []);

        document.getElementById(
          "lastUpdate"
        ).textContent = (
          "Última atualização: "
          + new Date().toLocaleString("pt-BR")
          + " | Histórico somente leitura"
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

    async function capture() {
      const confirmed = window.confirm(
        "Capturar a avaliação atual do Readiness Gate?"
      );

      if (!confirmed) {
        return;
      }

      const button = document.getElementById(
        "captureButton"
      );

      button.disabled = true;
      button.textContent = "Capturando...";

      try {
        const response = await fetch(
          "/paper/readiness/history/capture"
          + "?confirm=CAPTURE-PAPER-READINESS",
          {
            method: "POST"
          }
        );

        if (!response.ok) {
          throw new Error(
            `HTTP ${response.status}`
          );
        }

        const payload = await response.json();
        ensureSafe(payload);

        await refresh();
      } catch (error) {
        window.alert(
          "Falha na captura: "
          + error.message
        );
      } finally {
        button.disabled = false;
        button.textContent = "Capturar avaliação";
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


def _history() -> PaperReadinessHistory:
    return PaperReadinessHistory()


@router.get("/health")
async def readiness_history_health():
    summary = _history().summary()

    return {
        "status": "healthy",
        "history_path": summary[
            "history_path"
        ],
        "total_entries": summary[
            "total_entries"
        ],
        "read_only": True,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
    }


@router.get("/summary")
async def readiness_history_summary():
    return _history().summary()


@router.get("/latest")
async def readiness_history_latest():
    return {
        "entry": _history().latest(),
        "read_only": True,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
    }


@router.get("/entries")
async def readiness_history_entries(
    limit: int = Query(
        default=100,
        ge=1,
        le=5000,
    ),
    status: str | None = Query(
        default=None
    ),
):
    try:
        entries = _history().list_entries(
            limit=limit,
            status=status,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "count": len(entries),
        "entries": entries,
        "read_only": True,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
    }


@router.get("/snapshot")
async def readiness_history_snapshot(
    limit: int = Query(
        default=250,
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
        "read_only": True,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
    }


@router.post("/capture")
async def readiness_history_capture(
    confirm: str = Query(...),
):
    if confirm != "CAPTURE-PAPER-READINESS":
        raise HTTPException(
            status_code=400,
            detail=(
                "Confirmação inválida. Use "
                "CAPTURE-PAPER-READINESS."
            ),
        )

    report = (
        paper_readiness_gate.evaluate()
    )

    return _history().capture(report)


@router.get(
    "/dashboard",
    response_class=HTMLResponse,
)
async def readiness_history_dashboard():
    return HTMLResponse(
        content=DASHBOARD_HTML,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-PredArb-Financial-Execution": "false",
        },
    )


@router.get("/export.csv")
async def readiness_history_export_csv(
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
        "ready",
        "readiness_score",
        "score_delta",
        "operations_status",
        "passed_checks",
        "blockers",
        "warnings",
        "insufficient_data",
        "blocker_codes",
        "warning_codes",
        "insufficient_codes",
    ]

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=fieldnames,
        extrasaction="ignore",
    )

    writer.writeheader()

    for entry in entries:
        row = dict(entry)

        for field in (
            "blocker_codes",
            "warning_codes",
            "insufficient_codes",
        ):
            row[field] = "|".join(
                str(value)
                for value in (
                    row.get(field)
                    or []
                )
            )

        writer.writerow(row)

    return Response(
        content="\ufeff" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                "attachment; "
                'filename="predarb-paper-readiness-history.csv"'
            ),
            "Cache-Control": "no-store",
            "X-PredArb-Financial-Execution": "false",
        },
    )
