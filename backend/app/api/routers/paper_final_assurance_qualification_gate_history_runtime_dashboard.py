from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.paper.final_paper_assurance_qualification_gate import (
    final_paper_assurance_qualification_gate,
)
from app.paper.final_paper_assurance_qualification_gate_history import (
    FinalPaperAssuranceQualificationGateHistory,
)
from app.paper.final_paper_assurance_qualification_gate_history_runtime import (
    final_paper_assurance_qualification_gate_history_runtime,
)


router = APIRouter(
    prefix=(
        "/paper/final-assurance/"
        "qualification-gate/history-runtime"
    ),
    tags=[
        "paper-final-assurance-qualification-"
        "gate-history-runtime-dashboard"
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
  <title>
    PredArb | Runtime do Histórico do Gate de Qualificação
  </title>

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
    .badges {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }

    .badges {
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
      width: 145px;
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
        repeat(auto-fit, minmax(155px, 1fr));
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
      font-size: 24px;
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
    .qualified {
      color: var(--good);
    }

    .pending,
    .no_data {
      color: var(--warning);
    }

    .blocked {
      color: var(--critical);
    }

    .stopped,
    .unknown {
      color: var(--muted);
    }

    pre {
      max-height: 430px;
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
        <h1>
          Runtime do Histórico do Gate de Qualificação
        </h1>

        <p class="muted">
          Captura controlada da qualificação técnica final do ambiente Paper.
        </p>
      </div>

      <div class="actions">
        <a
          class="button"
          href="/paper/final-assurance/qualification-gate/dashboard"
        >
          Gate atual
        </a>

        <a
          class="button"
          href="/paper/final-assurance/qualification-gate/history/dashboard"
        >
          Histórico do gate
        </a>

        <a
          class="button"
          href="/paper/final-assurance/dashboard"
        >
          Garantia final
        </a>
      </div>
    </header>

    <section class="badges">
      <span class="badge">
        Início manual obrigatório
      </span>

      <span class="badge">
        Persiste somente o histórico do gate
      </span>

      <span class="badge">
        Próxima fase não autorizada
      </span>

      <span class="badge">
        Execução live e financeira bloqueada
      </span>
    </section>

    <div
      id="phase8atConfirmationTokens"
      hidden
      data-capture-confirmation="CAPTURE-FINAL-PAPER-ASSURANCE-QUALIFICATION-GATE"
      data-start-confirmation="START-FINAL-PAPER-ASSURANCE-QUALIFICATION-GATE-HISTORY-RUNTIME"
      data-stop-confirmation="STOP-FINAL-PAPER-ASSURANCE-QUALIFICATION-GATE-HISTORY-RUNTIME"
      data-reset-confirmation="RESET-FINAL-PAPER-ASSURANCE-QUALIFICATION-GATE-HISTORY-RUNTIME"
    ></div>


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

    <p
      id="lastUpdate"
      class="footer"
    >
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

    function card(
      label,
      value,
      className = ""
    ) {
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

      const runtime = payload.runtime || {};
      const gate = payload.gate || {};
      const history = payload.history || {};
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
          "Gate atual",
          gate.status || "-",
          css(gate.status)
        ),
        card(
          "Score de qualificação",
          Number(
            gate.qualification_score || 0
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
          "Registros do gate",
          integer.format(
            Number(history.total_entries || 0)
          )
        ),
        card(
          "Último gate persistido",
          history.latest_status || "-",
          css(history.latest_status)
        ),
        card(
          "Maior sequência QUALIFIED",
          integer.format(
            Number(
              history.longest_qualified_streak || 0
            )
          )
        ),
        card(
          "Transições",
          integer.format(
            Number(history.transitions || 0)
          )
        ),
        card(
          "Ciclos QUALIFIED",
          integer.format(
            Number(runtime.qualified_cycles || 0)
          ),
          "qualified"
        ),
        card(
          "Ciclos PENDING",
          integer.format(
            Number(runtime.pending_cycles || 0)
          ),
          "pending"
        ),
        card(
          "Ciclos BLOCKED",
          integer.format(
            Number(runtime.blocked_cycles || 0)
          ),
          "blocked"
        ),
        card(
          "Ciclos NO_DATA",
          integer.format(
            Number(runtime.no_data_cycles || 0)
          ),
          "no_data"
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

    async function refresh() {
      const button = document.getElementById(
        "refreshButton"
      );

      button.disabled = true;
      button.textContent = "Atualizando...";

      try {
        const response = await fetch(
          "/paper/final-assurance/"
          + "qualification-gate/"
          + "history-runtime/snapshot",
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
          + " | Runtime manual | Ambiente Paper"
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
        "Iniciar o runtime do histórico do Gate de Qualificação?"
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
        "/paper/final-assurance/"
        + "qualification-gate/"
        + "history-runtime/start"
        + "?confirm=START-FINAL-PAPER-ASSURANCE-"
        + "QUALIFICATION-GATE-HISTORY-RUNTIME"
        + `&interval_seconds=${encodeURIComponent(interval)}`
        + "&run_immediately=true"
      );

      await refresh();
    }

    async function stopRuntime() {
      const confirmed = window.confirm(
        "Parar o runtime do histórico do Gate de Qualificação?"
      );

      if (!confirmed) {
        return;
      }

      await post(
        "/paper/final-assurance/"
        + "qualification-gate/"
        + "history-runtime/stop"
        + "?confirm=STOP-FINAL-PAPER-ASSURANCE-"
        + "QUALIFICATION-GATE-HISTORY-RUNTIME"
      );

      await refresh();
    }

    async function runCycle() {
      const confirmed = window.confirm(
        "Capturar agora o Gate de Qualificação atual?"
      );

      if (!confirmed) {
        return;
      }

      await post(
        "/paper/final-assurance/"
        + "qualification-gate/"
        + "history-runtime/cycle"
        + "?confirm=CAPTURE-FINAL-PAPER-ASSURANCE-"
        + "QUALIFICATION-GATE"
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
        "/paper/final-assurance/"
        + "qualification-gate/"
        + "history-runtime/reset-statistics"
        + "?confirm=RESET-FINAL-PAPER-ASSURANCE-"
        + "QUALIFICATION-GATE-HISTORY-RUNTIME"
      );

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
      "startButton"
    ).addEventListener(
      "click",
      () => guarded(startRuntime)
    );

    document.getElementById(
      "stopButton"
    ).addEventListener(
      "click",
      () => guarded(stopRuntime)
    );

    document.getElementById(
      "cycleButton"
    ).addEventListener(
      "click",
      () => guarded(runCycle)
    );

    document.getElementById(
      "resetButton"
    ).addEventListener(
      "click",
      () => guarded(resetStatistics)
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
        "next_step_authorized": False,
    }


@router.get(
    "/dashboard",
    response_class=HTMLResponse,
)
async def qualification_gate_history_runtime_dashboard():
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
async def qualification_gate_history_runtime_snapshot():
    runtime = (
        final_paper_assurance_qualification_gate_history_runtime
        .status()
    )

    gate = (
        final_paper_assurance_qualification_gate
        .evaluate()
    )

    history = (
        FinalPaperAssuranceQualificationGateHistory()
        .summary()
    )

    return {
        "runtime": runtime,
        "gate": {
            "status": gate.get("status"),
            "qualified": gate.get("qualified"),
            "scope": gate.get("scope"),
            "qualification_score": gate.get(
                "qualification_score"
            ),
            "criteria": gate.get("criteria"),
            "summary": gate.get("summary"),
        },
        "history": history,
        "manual_start_required": True,
        "read_only_snapshot": True,
        "read_only": True,
        **_safe_flags(),
    }
