from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.paper.certification_evidence_incident_runtime import (
    paper_evidence_incident_runtime,
)
from app.paper.certification_evidence_incidents import (
    PaperCertificationEvidenceIncidentJournal,
)
from app.paper.certification_evidence_monitor import (
    paper_certification_evidence_monitor,
)


router = APIRouter(
    prefix=(
        "/paper/certification/evidence/"
        "incident-runtime"
    ),
    tags=[
        "paper-certification-evidence-incident-runtime-dashboard"
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
  <title>PredArb | Runtime dos Incidentes das Evidências</title>

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
    a.button,
    input {
      min-height: 42px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: var(--panel);
      color: var(--text);
      font: inherit;
    }

    button,
    a.button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 0 16px;
      text-decoration: none;
      cursor: pointer;
    }

    button.primary {
      border-color: var(--accent);
      background: var(--accent);
      color: #111;
      font-weight: 760;
    }

    button.danger {
      border-color: var(--critical);
      color: var(--critical);
    }

    button:disabled {
      opacity: 0.55;
      cursor: wait;
    }

    input {
      width: 130px;
      padding: 0 12px;
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
    }

    .control-row {
      display: flex;
      align-items: end;
      flex-wrap: wrap;
      gap: 10px;
    }

    .field {
      display: grid;
      gap: 6px;
    }

    .field label {
      color: var(--muted);
      font-size: 12px;
    }

    .running,
    .healthy {
      color: var(--good);
    }

    .warning {
      color: var(--warning);
    }

    .critical {
      color: var(--critical);
    }

    .no_data,
    .info {
      color: var(--info);
    }

    .stopped {
      color: var(--muted);
    }

    pre {
      max-height: 420px;
      margin: 0;
      padding: 16px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: rgba(0, 0, 0, 0.25);
      color: #dbe4eb;
      font-size: 12px;
      line-height: 1.55;
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
        <h1>Runtime dos Incidentes das Evidências</h1>
        <p class="muted">
          Captura periódica e controlada do monitor no journal.
        </p>
      </div>

      <div class="actions">
        <a
          class="button"
          href="/paper/certification/evidence/incidents/ui/dashboard"
        >
          Incidentes
        </a>

        <a
          class="button"
          href="/paper/certification/evidence/monitor/dashboard"
        >
          Monitor
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
        Início manual obrigatório
      </span>
      <span class="badge">
        Nenhuma evidência é criada
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
      <h2>Controles administrativos</h2>

      <div class="control-row">
        <div class="field">
          <label for="intervalInput">
            Intervalo em segundos
          </label>

          <input
            id="intervalInput"
            type="number"
            min="30"
            max="86400"
            step="1"
            value="300"
          >
        </div>

        <button
          id="startButton"
          class="primary"
          type="button"
        >
          Iniciar runtime
        </button>

        <button
          id="stopButton"
          class="danger"
          type="button"
        >
          Parar runtime
        </button>

        <button
          id="cycleButton"
          type="button"
        >
          Capturar agora
        </button>

        <button
          id="resetButton"
          type="button"
        >
          Resetar estatísticas
        </button>

        <button
          id="refreshButton"
          type="button"
        >
          Atualizar
        </button>
      </div>
    </section>

    <section class="panel">
      <h2>Último ciclo</h2>
      <pre id="lastCycle">Carregando...</pre>
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
      if (
        payload.execution_authorized !== false
        || payload.live_execution !== false
        || payload.financial_execution !== false
        || payload.live_authorization !== false
      ) {
        throw new Error(
          "Guardas de segurança inválidas."
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

    function normalizeClass(value) {
      return String(
        value || ""
      ).toLowerCase();
    }

    function card(label, value, className = "") {
      return `
        <article class="card">
          <div class="card-label">
            ${escapeHtml(label)}
          </div>
          <div class="card-value ${className}">
            ${escapeHtml(value)}
          </div>
        </article>
      `;
    }

    function render(payload) {
      ensureSafe(payload);

      const runtime = payload.runtime || {};
      const monitor = payload.monitor || {};
      const journal = payload.journal || {};

      const running = runtime.running === true;

      document.getElementById(
        "summaryGrid"
      ).innerHTML = [
        card(
          "Runtime",
          running ? "EXECUTANDO" : "PARADO",
          running ? "running" : "stopped"
        ),
        card(
          "Monitor",
          monitor.status || "NO_DATA",
          normalizeClass(monitor.status)
        ),
        card(
          "Score do monitor",
          Number(
            monitor.score || 0
          ).toFixed(0)
        ),
        card(
          "Ciclos",
          integer.format(
            Number(runtime.total_cycles || 0)
          )
        ),
        card(
          "Sucessos",
          integer.format(
            Number(runtime.successful_cycles || 0)
          )
        ),
        card(
          "Falhas",
          integer.format(
            Number(runtime.failed_cycles || 0)
          )
        ),
        card(
          "Incidentes ativos",
          integer.format(
            Number(journal.active_incidents || 0)
          )
        ),
        card(
          "Snapshots do journal",
          integer.format(
            Number(journal.snapshots || 0)
          )
        )
      ].join("");

      document.getElementById(
        "intervalInput"
      ).value = Number(
        runtime.interval_seconds || 300
      );

      document.getElementById(
        "lastCycle"
      ).textContent = JSON.stringify(
        runtime.last_result || {
          status: "Nenhum ciclo executado"
        },
        null,
        2
      );

      document.getElementById(
        "startButton"
      ).disabled = running;

      document.getElementById(
        "stopButton"
      ).disabled = !running;

      document.getElementById(
        "resetButton"
      ).disabled = running;
    }

    async function getSnapshot() {
      const response = await fetch(
        "/paper/certification/evidence/"
        + "incident-runtime/snapshot",
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
        const payload = await getSnapshot();
        render(payload);

        document.getElementById(
          "lastUpdate"
        ).textContent = (
          "Última atualização: "
          + new Date().toLocaleString("pt-BR")
          + " | Runtime manual | Nenhuma execução financeira"
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

    async function startRuntime() {
      const confirmed = window.confirm(
        "Iniciar o runtime de captura dos incidentes das evidências?"
      );

      if (!confirmed) {
        return;
      }

      const interval = Math.max(
        30,
        Math.min(
          86400,
          Number(
            document.getElementById(
              "intervalInput"
            ).value || 300
          )
        )
      );

      await post(
        "/paper/certification/evidence/"
        + "incident-runtime/start"
        + "?confirm=START-PAPER-EVIDENCE-INCIDENT-RUNTIME"
        + `&interval_seconds=${encodeURIComponent(interval)}`
        + "&run_immediately=true"
      );

      await refresh();
    }

    async function stopRuntime() {
      const confirmed = window.confirm(
        "Parar o runtime dos incidentes das evidências?"
      );

      if (!confirmed) {
        return;
      }

      await post(
        "/paper/certification/evidence/"
        + "incident-runtime/stop"
        + "?confirm=STOP-PAPER-EVIDENCE-INCIDENT-RUNTIME"
      );

      await refresh();
    }

    async function runCycle() {
      const confirmed = window.confirm(
        "Capturar agora o monitor de evidências no journal?"
      );

      if (!confirmed) {
        return;
      }

      await post(
        "/paper/certification/evidence/"
        + "incident-runtime/cycle"
        + "?confirm=CAPTURE-PAPER-EVIDENCE-INCIDENTS"
      );

      await refresh();
    }

    async function resetStatistics() {
      const confirmed = window.confirm(
        "Resetar somente as estatísticas deste runtime?"
      );

      if (!confirmed) {
        return;
      }

      await post(
        "/paper/certification/evidence/"
        + "incident-runtime/reset-statistics"
        + "?confirm=RESET-PAPER-EVIDENCE-INCIDENT-RUNTIME"
      );

      await refresh();
    }

    async function guardedAction(action) {
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
      "startButton"
    ).addEventListener(
      "click",
      () => guardedAction(startRuntime)
    );

    document.getElementById(
      "stopButton"
    ).addEventListener(
      "click",
      () => guardedAction(stopRuntime)
    );

    document.getElementById(
      "cycleButton"
    ).addEventListener(
      "click",
      () => guardedAction(runCycle)
    );

    document.getElementById(
      "resetButton"
    ).addEventListener(
      "click",
      () => guardedAction(resetStatistics)
    );

    refresh();
    setInterval(refresh, 5000);
  </script>
</body>
</html>
"""


def _safe_flags() -> dict[str, bool]:
    return {
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
    }


@router.get(
    "/dashboard",
    response_class=HTMLResponse,
)
async def evidence_incident_runtime_dashboard():
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
async def evidence_incident_runtime_dashboard_snapshot():
    runtime = (
        paper_evidence_incident_runtime.status()
    )

    monitor = (
        paper_certification_evidence_monitor
        .snapshot()
    )

    journal = (
        PaperCertificationEvidenceIncidentJournal()
        .summary()
    )

    return {
        "runtime": runtime,
        "monitor": monitor,
        "journal": journal,
        "manual_start_required": True,
        "read_only_snapshot": True,
        **_safe_flags(),
    }
