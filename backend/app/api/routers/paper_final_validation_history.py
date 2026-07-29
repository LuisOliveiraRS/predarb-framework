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

from app.paper.final_paper_validation import (
    final_paper_validation,
)
from app.paper.final_paper_validation_history import (
    FinalPaperValidationHistory,
)


router = APIRouter(
    prefix=(
        "/paper/final-validation/history"
    ),
    tags=[
        "paper-final-validation-history"
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
  <title>PredArb | Histórico da Validação Final Paper</title>

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
      width: min(1300px, calc(100% - 28px));
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

    .chart {
      width: 100%;
      height: 260px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: rgba(0, 0, 0, 0.2);
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

    .paper_validated {
      color: var(--good);
      font-weight: 760;
    }

    .paper_pending,
    .insufficient_data {
      color: var(--warning);
      font-weight: 760;
    }

    .paper_blocked {
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
        <h1>Histórico da Validação Final Paper</h1>
        <p class="muted">
          Evolução das avaliações finais do ambiente Paper.
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
          Registrar avaliação
        </button>

        <a
          class="button"
          href="/paper/final-validation/history/export.csv"
        >
          Exportar CSV
        </a>

        <a
          class="button"
          href="/paper/final-validation/dashboard"
        >
          Validação atual
        </a>
      </div>
    </header>

    <section class="safety">
      <span class="badge">
        Captura manual confirmada
      </span>
      <span class="badge">
        Escopo: PAPER_VALIDATION_ONLY
      </span>
      <span class="badge">
        Próxima fase não autorizada
      </span>
      <span class="badge">
        Execução live bloqueada
      </span>
    </section>

    <section
      id="summaryGrid"
      class="grid"
    ></section>

    <section class="panel">
      <h2>Evolução do score final</h2>

      <svg
        id="scoreChart"
        class="chart"
        viewBox="0 0 1000 260"
        role="img"
        aria-label="Histórico do score da validação final"
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
              <th>Gate</th>
              <th>Score gate</th>
              <th>Avaliações do gate</th>
              <th>Sequência QUALIFIED</th>
              <th>Falhas de runtime</th>
              <th>Checks reprovados</th>
              <th>Códigos de falha</th>
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
        payload.paper_execution_authorized !== false
        || payload.execution_authorized !== false
        || payload.live_execution !== false
        || payload.financial_execution !== false
        || payload.live_authorization !== false
        || payload.next_step_authorized !== false
        || payload.read_only !== true
      ) {
        throw new Error(
          "Guardas de segurança inválidas."
        );
      }
    }

    function renderChart(entries) {
      const svg = document.getElementById(
        "scoreChart"
      );

      const ordered = [...entries].reverse();

      if (!ordered.length) {
        svg.innerHTML = `
          <text
            x="500"
            y="135"
            text-anchor="middle"
            fill="#9ca9b5"
            font-size="18"
          >
            Nenhuma avaliação registrada
          </text>
        `;
        return;
      }

      const padding = 45;
      const width = 1000 - padding * 2;
      const height = 260 - padding * 2;
      const divisor = Math.max(
        1,
        ordered.length - 1
      );

      const points = ordered.map(
        (item, index) => {
          const x = (
            padding
            + width * index / divisor
          );

          const score = Math.max(
            0,
            Math.min(
              100,
              Number(
                item.validation_score || 0
              )
            )
          );

          const y = (
            padding
            + height * (1 - score / 100)
          );

          return {
            x,
            y,
            score
          };
        }
      );

      const polyline = points.map(
        (point) => (
          `${point.x},${point.y}`
        )
      ).join(" ");

      const guides = [0, 25, 50, 75, 100].map(
        (score) => {
          const y = (
            padding
            + height * (1 - score / 100)
          );

          return `
            <line
              x1="${padding}"
              y1="${y}"
              x2="${1000 - padding}"
              y2="${y}"
              stroke="#2b333d"
              stroke-width="1"
            />
            <text
              x="10"
              y="${y + 5}"
              fill="#9ca9b5"
              font-size="12"
            >
              ${score}
            </text>
          `;
        }
      ).join("");

      const circles = points.map(
        (point) => `
          <circle
            cx="${point.x}"
            cy="${point.y}"
            r="4"
            fill="#ff6a00"
          >
            <title>${point.score.toFixed(2)}</title>
          </circle>
        `
      ).join("");

      svg.innerHTML = `
        ${guides}
        <polyline
          points="${polyline}"
          fill="none"
          stroke="#f5f7f9"
          stroke-width="3"
          stroke-linejoin="round"
          stroke-linecap="round"
        />
        ${circles}
      `;
    }

    function render(payload) {
      ensureSafe(payload);

      const summary = payload.summary || {};
      const entries = payload.entries || [];
      const counts = summary.status_counts || {};

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
          "PAPER_VALIDATED",
          integer.format(
            Number(counts.PAPER_VALIDATED || 0)
          )
        ),
        card(
          "Último status",
          summary.latest_status || "-"
        ),
        card(
          "Último score",
          summary.latest_score === null
            ? "-"
            : Number(
                summary.latest_score
              ).toFixed(2)
        ),
        card(
          "Média do score",
          summary.average_score === null
            ? "-"
            : Number(
                summary.average_score
              ).toFixed(2)
        ),
        card(
          "Maior sequência validada",
          integer.format(
            Number(
              summary.longest_validated_streak
              || 0
            )
          )
        ),
        card(
          "Sequência atual",
          integer.format(
            Number(
              summary.current_streak || 0
            )
          )
        ),
        card(
          "Transições",
          integer.format(
            Number(
              summary.transitions || 0
            )
          )
        )
      ].join("");

      renderChart(entries);

      const body = document.getElementById(
        "historyBody"
      );

      if (!entries.length) {
        body.innerHTML = `
          <tr>
            <td colspan="12" class="muted">
              Nenhuma avaliação registrada.
            </td>
          </tr>
        `;
        return;
      }

      body.innerHTML = entries.map(
        (item) => {
          const details = item.summary || {};

          return `
            <tr>
              <td class="${normalizeClass(
                item.status
              )}">
                ${escapeHtml(item.status)}
              </td>
              <td>${dateTime(item.captured_at)}</td>
              <td>
                ${Number(
                  item.validation_score || 0
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
                ${escapeHtml(
                  details.gate_status || "-"
                )}
              </td>
              <td>
                ${Number(
                  details.gate_score || 0
                ).toFixed(2)}
              </td>
              <td>
                ${integer.format(
                  Number(
                    details.gate_history_entries
                    || 0
                  )
                )}
              </td>
              <td>
                ${integer.format(
                  Number(
                    details.qualified_streak
                    || 0
                  )
                )}
              </td>
              <td>
                ${integer.format(
                  Number(
                    details.total_runtime_failures
                    || 0
                  )
                )}
              </td>
              <td>
                ${integer.format(
                  Number(
                    details.failed_checks || 0
                  )
                )}
              </td>
              <td>
                ${escapeHtml(
                  (item.failure_codes || [])
                  .join(", ")
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
          "/paper/final-validation/"
          + "history/snapshot?limit=250",
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
          + " | Histórico restrito ao ambiente Paper"
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
        "Registrar a avaliação final atual do ambiente Paper?"
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
          "/paper/final-validation/"
          + "history/capture"
          + "?confirm=CAPTURE-FINAL-PAPER-VALIDATION",
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
        button.textContent = "Registrar avaliação";
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


def _history():
    return (
        FinalPaperValidationHistory()
    )


def _safe_base() -> dict[str, bool]:
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
async def final_validation_history_health():
    summary = _history().summary()

    return {
        "status": "healthy",
        "total_entries": (
            summary["total_entries"]
        ),
        "latest_status": (
            summary["latest_status"]
        ),
        **_safe_base(),
    }


@router.get("/summary")
async def final_validation_history_summary():
    return _history().summary()


@router.get("/latest")
async def final_validation_history_latest():
    return {
        "entry": (
            _history().latest()
        ),
        **_safe_base(),
    }


@router.get("/entries")
async def final_validation_history_entries(
    limit: int = Query(
        default=100,
        ge=1,
        le=5000,
    ),
):
    entries = (
        _history().list_entries(
            limit=limit
        )
    )

    return {
        "count": len(
            entries
        ),
        "entries": entries,
        **_safe_base(),
    }


@router.get("/snapshot")
async def final_validation_history_snapshot(
    limit: int = Query(
        default=250,
        ge=1,
        le=5000,
    ),
):
    history = _history()

    return {
        "summary": (
            history.summary()
        ),
        "latest": (
            history.latest()
        ),
        "entries": (
            history.list_entries(
                limit=limit
            )
        ),
        **_safe_base(),
    }


@router.post("/capture")
async def final_validation_history_capture(
    confirm: str = Query(...),
):
    if (
        confirm
        != "CAPTURE-FINAL-PAPER-VALIDATION"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Confirmação inválida. Use "
                "CAPTURE-FINAL-PAPER-VALIDATION."
            ),
        )

    report = (
        final_paper_validation
        .evaluate()
    )

    return _history().capture(
        report
    )


@router.get(
    "/dashboard",
    response_class=HTMLResponse,
)
async def final_validation_history_dashboard():
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
async def final_validation_history_export_csv(
    limit: int = Query(
        default=5000,
        ge=1,
        le=5000,
    ),
):
    entries = (
        _history().list_entries(
            limit=limit
        )
    )

    fieldnames = [
        "id",
        "captured_at",
        "report_generated_at",
        "status",
        "validated",
        "scope",
        "validation_score",
        "total_checks",
        "passed_checks",
        "failed_checks",
        "failed_data_checks",
        "failed_validation_checks",
        "assurance_status",
        "assurance_score",
        "gate_status",
        "gate_score",
        "gate_history_entries",
        "gate_history_latest_status",
        "qualified_streak",
        "assurance_runtime_status",
        "gate_runtime_status",
        "assurance_runtime_failures",
        "gate_runtime_failures",
        "total_runtime_failures",
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
                "status": (
                    entry.get("status")
                ),
                "validated": (
                    entry.get("validated")
                ),
                "scope": (
                    entry.get("scope")
                ),
                "validation_score": (
                    entry.get(
                        "validation_score"
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
                "failed_data_checks": (
                    summary.get(
                        "failed_data_checks"
                    )
                ),
                "failed_validation_checks": (
                    summary.get(
                        "failed_validation_checks"
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
                "gate_status": (
                    summary.get(
                        "gate_status"
                    )
                ),
                "gate_score": (
                    summary.get(
                        "gate_score"
                    )
                ),
                "gate_history_entries": (
                    summary.get(
                        "gate_history_entries"
                    )
                ),
                "gate_history_latest_status": (
                    summary.get(
                        "gate_history_latest_status"
                    )
                ),
                "qualified_streak": (
                    summary.get(
                        "qualified_streak"
                    )
                ),
                "assurance_runtime_status": (
                    summary.get(
                        "assurance_runtime_status"
                    )
                ),
                "gate_runtime_status": (
                    summary.get(
                        "gate_runtime_status"
                    )
                ),
                "assurance_runtime_failures": (
                    summary.get(
                        "assurance_runtime_failures"
                    )
                ),
                "gate_runtime_failures": (
                    summary.get(
                        "gate_runtime_failures"
                    )
                ),
                "total_runtime_failures": (
                    summary.get(
                        "total_runtime_failures"
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
                'filename="predarb-final-paper-validation-history.csv"'
            ),
            "Cache-Control": "no-store",
            "X-PredArb-Live-Authorization": "false",
            "X-PredArb-Financial-Execution": "false",
            "X-PredArb-Next-Step-Authorization": "false",
        },
    )
