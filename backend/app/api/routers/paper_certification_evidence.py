from __future__ import annotations

import csv
import io
import json

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)
from fastapi.responses import (
    HTMLResponse,
    Response,
)

from app.paper.certification_evidence import (
    PaperCertificationEvidence,
)
from app.paper.stability_certification import (
    paper_stability_certification,
)


router = APIRouter(
    prefix="/paper/certification/evidence",
    tags=["paper-certification-evidence"],
)


DASHBOARD_HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta
    name="viewport"
    content="width=device-width, initial-scale=1"
  >
  <title>PredArb | Evidências da Certificação</title>

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
      font-size: 25px;
      font-weight: 780;
      letter-spacing: -0.04em;
    }

    .panel {
      margin-bottom: 18px;
      padding: 20px;
      overflow: hidden;
    }

    .integrity {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 16px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.02);
    }

    .valid {
      color: var(--good);
    }

    .broken {
      color: var(--critical);
    }

    .empty {
      color: var(--info);
    }

    .table-wrap {
      overflow-x: auto;
    }

    table {
      width: 100%;
      min-width: 1180px;
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

    td.hash {
      max-width: 270px;
      overflow: hidden;
      text-overflow: ellipsis;
      font-family: ui-monospace, monospace;
    }

    .certified {
      color: var(--good);
      font-weight: 760;
    }

    .pending {
      color: var(--warning);
      font-weight: 760;
    }

    .blocked {
      color: var(--critical);
      font-weight: 760;
    }

    .no_data {
      color: var(--info);
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

      .integrity {
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
        <h1>Evidências da Certificação</h1>
        <p class="muted">
          Arquivo encadeado e verificável das avaliações Paper.
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
          Registrar evidência
        </button>

        <a
          class="button"
          href="/paper/certification/evidence/export.csv"
        >
          Exportar CSV
        </a>

        <a
          class="button"
          href="/paper/certification/dashboard"
        >
          Certificação atual
        </a>
      </div>
    </header>

    <section class="safety">
      <span class="badge">
        Escopo exclusivo: PAPER
      </span>
      <span class="badge">
        Hash SHA-256 encadeado
      </span>
      <span class="badge">
        Não autoriza execução live
      </span>
      <span class="badge">
        Captura manual confirmada
      </span>
    </section>

    <section
      id="summaryGrid"
      class="grid"
    ></section>

    <section class="panel">
      <h2>Integridade do arquivo</h2>

      <div
        id="integrity"
        class="integrity"
      >
        Carregando...
      </div>
    </section>

    <section class="panel">
      <h2>Evidências registradas</h2>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Status</th>
              <th>Capturada em</th>
              <th>Score</th>
              <th>Sequência READY</th>
              <th>Bloqueadores</th>
              <th>Hash da evidência</th>
              <th>Hash anterior</th>
            </tr>
          </thead>

          <tbody id="evidenceBody"></tbody>
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
      const verification = payload.verification || {};
      const entries = payload.entries || [];

      document.getElementById(
        "summaryGrid"
      ).innerHTML = [
        card(
          "Evidências",
          integer.format(
            Number(summary.total_entries || 0)
          )
        ),
        card(
          "CERTIFIED",
          integer.format(
            Number(summary.certified_entries || 0)
          )
        ),
        card(
          "PENDING",
          integer.format(
            Number(summary.pending_entries || 0)
          )
        ),
        card(
          "BLOCKED",
          integer.format(
            Number(summary.blocked_entries || 0)
          )
        ),
        card(
          "Último status",
          summary.latest_status || "-"
        ),
        card(
          "Último score",
          Number(
            summary.latest_score || 0
          ).toFixed(2)
        )
      ].join("");

      document.getElementById(
        "integrity"
      ).innerHTML = `
        <div>
          <strong class="${normalizeClass(
            verification.status
          )}">
            ${escapeHtml(verification.status)}
          </strong>

          <div class="muted">
            ${integer.format(
              Number(
                verification.total_entries || 0
              )
            )}
            entradas verificadas
          </div>
        </div>

        <div class="muted">
          Chain head:
          ${escapeHtml(
            verification.chain_head || "-"
          )}
        </div>
      `;

      const body = document.getElementById(
        "evidenceBody"
      );

      if (!entries.length) {
        body.innerHTML = `
          <tr>
            <td colspan="7" class="muted">
              Nenhuma evidência registrada.
            </td>
          </tr>
        `;
        return;
      }

      body.innerHTML = entries.map(
        (item) => `
          <tr>
            <td class="${normalizeClass(
              item.status
            )}">
              ${escapeHtml(item.status)}
            </td>
            <td>${dateTime(item.captured_at)}</td>
            <td>
              ${Number(
                item.certification_score || 0
              ).toFixed(2)}
            </td>
            <td>
              ${integer.format(
                Number(
                  item.summary
                    ? item.summary.consecutive_ready
                    : 0
                )
              )}
            </td>
            <td>
              ${integer.format(
                Number(
                  item.summary
                    ? item.summary.blockers
                    : 0
                )
              )}
            </td>
            <td class="hash" title="${escapeHtml(
              item.evidence_hash
            )}">
              ${escapeHtml(item.evidence_hash)}
            </td>
            <td class="hash" title="${escapeHtml(
              item.previous_hash
            )}">
              ${escapeHtml(item.previous_hash)}
            </td>
          </tr>
        `
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
          "/paper/certification/evidence/snapshot"
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

        const payload = await response.json();
        render(payload);

        document.getElementById(
          "lastUpdate"
        ).textContent = (
          "Última atualização: "
          + new Date().toLocaleString("pt-BR")
          + " | Evidências limitadas ao ambiente Paper"
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
        "Registrar a certificação atual como evidência encadeada?"
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
          "/paper/certification/evidence/capture"
          + "?confirm=CAPTURE-PAPER-CERTIFICATION-EVIDENCE",
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
          "Falha no registro: "
          + error.message
        );
      } finally {
        button.disabled = false;
        button.textContent = "Registrar evidência";
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


def _evidence() -> PaperCertificationEvidence:
    return PaperCertificationEvidence()


def _safe_base() -> dict[str, bool]:
    return {
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "read_only": True,
    }


@router.get("/health")
async def certification_evidence_health():
    summary = _evidence().summary()

    return {
        "status": "healthy",
        "chain_status": summary[
            "chain_status"
        ],
        "chain_valid": summary[
            "chain_valid"
        ],
        "total_entries": summary[
            "total_entries"
        ],
        **_safe_base(),
    }


@router.get("/summary")
async def certification_evidence_summary():
    return _evidence().summary()


@router.get("/verify")
async def certification_evidence_verify():
    return _evidence().verify()


@router.get("/latest")
async def certification_evidence_latest():
    return {
        "evidence": _evidence().latest(),
        **_safe_base(),
    }


@router.get("/entries")
async def certification_evidence_entries(
    limit: int = Query(
        default=100,
        ge=1,
        le=5000,
    ),
):
    entries = _evidence().list_entries(
        limit=limit
    )

    return {
        "count": len(entries),
        "entries": entries,
        **_safe_base(),
    }


@router.get("/snapshot")
async def certification_evidence_snapshot(
    limit: int = Query(
        default=250,
        ge=1,
        le=5000,
    ),
):
    evidence = _evidence()

    return {
        "summary": evidence.summary(),
        "verification": evidence.verify(),
        "latest": evidence.latest(),
        "entries": evidence.list_entries(
            limit=limit
        ),
        **_safe_base(),
    }


@router.post("/capture")
async def certification_evidence_capture(
    confirm: str = Query(...),
):
    if (
        confirm
        != "CAPTURE-PAPER-CERTIFICATION-EVIDENCE"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Confirmação inválida. Use "
                "CAPTURE-PAPER-CERTIFICATION-EVIDENCE."
            ),
        )

    report = (
        paper_stability_certification
        .evaluate()
    )

    return _evidence().capture(report)


@router.get(
    "/dashboard",
    response_class=HTMLResponse,
)
async def certification_evidence_dashboard():
    return HTMLResponse(
        content=DASHBOARD_HTML,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-PredArb-Live-Authorization": "false",
            "X-PredArb-Financial-Execution": "false",
        },
    )


@router.get("/export.csv")
async def certification_evidence_export_csv(
    limit: int = Query(
        default=5000,
        ge=1,
        le=5000,
    ),
):
    entries = _evidence().list_entries(
        limit=limit
    )

    fieldnames = [
        "id",
        "captured_at",
        "report_generated_at",
        "status",
        "certified",
        "scope",
        "certification_score",
        "total_checks",
        "passed_checks",
        "pending_checks",
        "blockers",
        "total_history_entries",
        "latest_status",
        "latest_score",
        "recent_average_score",
        "consecutive_ready",
        "recent_not_ready",
        "blocker_codes",
        "pending_codes",
        "previous_hash",
        "evidence_hash",
    ]

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=fieldnames,
        extrasaction="ignore",
    )

    writer.writeheader()

    for item in entries:
        summary = item.get("summary") or {}

        writer.writerow(
            {
                "id": item.get("id"),
                "captured_at": item.get(
                    "captured_at"
                ),
                "report_generated_at": item.get(
                    "report_generated_at"
                ),
                "status": item.get("status"),
                "certified": item.get(
                    "certified"
                ),
                "scope": item.get("scope"),
                "certification_score": item.get(
                    "certification_score"
                ),
                "total_checks": summary.get(
                    "total_checks"
                ),
                "passed_checks": summary.get(
                    "passed_checks"
                ),
                "pending_checks": summary.get(
                    "pending_checks"
                ),
                "blockers": summary.get(
                    "blockers"
                ),
                "total_history_entries": summary.get(
                    "total_history_entries"
                ),
                "latest_status": summary.get(
                    "latest_status"
                ),
                "latest_score": summary.get(
                    "latest_score"
                ),
                "recent_average_score": summary.get(
                    "recent_average_score"
                ),
                "consecutive_ready": summary.get(
                    "consecutive_ready"
                ),
                "recent_not_ready": summary.get(
                    "recent_not_ready"
                ),
                "blocker_codes": "|".join(
                    item.get("blocker_codes")
                    or []
                ),
                "pending_codes": "|".join(
                    item.get("pending_codes")
                    or []
                ),
                "previous_hash": item.get(
                    "previous_hash"
                ),
                "evidence_hash": item.get(
                    "evidence_hash"
                ),
            }
        )

    return Response(
        content="\ufeff" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                "attachment; "
                'filename="predarb-paper-certification-evidence.csv"'
            ),
            "Cache-Control": "no-store",
            "X-PredArb-Live-Authorization": "false",
            "X-PredArb-Financial-Execution": "false",
        },
    )


@router.get("/export.json")
async def certification_evidence_export_json():
    evidence = _evidence()

    payload = {
        "summary": evidence.summary(),
        "verification": evidence.verify(),
        "entries": evidence.list_entries(
            limit=5000
        ),
        **_safe_base(),
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
                'filename="predarb-paper-certification-evidence.json"'
            ),
            "Cache-Control": "no-store",
            "X-PredArb-Live-Authorization": "false",
            "X-PredArb-Financial-Execution": "false",
        },
    )
