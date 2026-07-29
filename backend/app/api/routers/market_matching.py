from __future__ import annotations

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.real_markets.matching import (
    market_matching_service,
)


router = APIRouter(
    prefix="/real-markets/matching",
    tags=[
        "real-market-identity-matching"
    ],
)


class ManualMatchRequest(BaseModel):
    left_connector_id: str = Field(
        min_length=1,
        max_length=100,
    )
    left_market_id: str = Field(
        min_length=1,
        max_length=300,
    )
    right_connector_id: str = Field(
        min_length=1,
        max_length=100,
    )
    right_market_id: str = Field(
        min_length=1,
        max_length=300,
    )
    note: str | None = Field(
        default=None,
        max_length=500,
    )


DASHBOARD_HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta
    name="viewport"
    content="width=device-width, initial-scale=1"
  >
  <title>PredArb | Identidade e Correspondência de Mercados</title>

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
      justify-content: space-between;
      align-items: flex-start;
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
    .badges,
    .controls {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }

    .badges {
      margin-bottom: 20px;
    }

    button,
    a.button,
    select,
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

    button:disabled {
      opacity: 0.55;
      cursor: wait;
    }

    select,
    input {
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
        repeat(auto-fit, minmax(160px, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }

    .card,
    .panel,
    .candidate {
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

    .candidate-list {
      display: grid;
      gap: 12px;
    }

    .candidate {
      padding: 16px;
      box-shadow: none;
    }

    .candidate-head {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 12px;
    }

    .pair {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
    }

    .market {
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: rgba(0, 0, 0, 0.18);
    }

    .score {
      font-size: 28px;
      font-weight: 800;
    }

    .strong_candidate {
      color: var(--good);
    }

    .candidate-status {
      color: var(--warning);
    }

    .rejected {
      color: var(--critical);
    }

    .table-wrap {
      overflow-x: auto;
    }

    table {
      width: 100%;
      min-width: 1000px;
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

    .footer {
      color: var(--muted);
      font-size: 12px;
    }

    @media (max-width: 760px) {
      header {
        flex-direction: column;
      }

      .pair {
        grid-template-columns: 1fr;
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
        <h1>Identidade e Correspondência de Mercados</h1>

        <p class="muted">
          Comparação segura de mercados equivalentes entre plataformas.
        </p>
      </div>

      <div class="actions">
        <button
          id="reloadButton"
          type="button"
        >
          Atualizar painel
        </button>

        <a
          class="button"
          href="/real-markets/dashboard"
        >
          Dados de mercado
        </a>
      </div>
    </header>

    <section class="badges">
      <span class="badge">
        Correspondência automática desativada
      </span>

      <span class="badge">
        Confirmação manual obrigatória
      </span>

      <span class="badge">
        Nenhuma ordem ou movimentação financeira
      </span>

      <span class="badge">
        Execução real bloqueada
      </span>
    </section>

    <div
      id="phase9cConfirmationTokens"
      hidden
      data-confirm-match="CONFIRM-REAL-MARKET-MATCH"
      data-remove-match="REMOVE-REAL-MARKET-MATCH"
    ></div>

    <section
      id="summaryGrid"
      class="grid"
    ></section>

    <section class="panel">
      <h2>Buscar candidatos</h2>

      <div class="controls">
        <select id="connectorA"></select>
        <select id="connectorB"></select>

        <input
          id="limitInput"
          type="number"
          min="1"
          max="50"
          value="10"
        >

        <button
          id="searchButton"
          class="primary"
          type="button"
        >
          Comparar mercados
        </button>
      </div>
    </section>

    <section class="panel">
      <h2>Candidatos encontrados</h2>

      <div
        id="candidateList"
        class="candidate-list"
      ></div>
    </section>

    <section class="panel">
      <h2>Correspondências manuais confirmadas</h2>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Mercado A</th>
              <th>Mercado B</th>
              <th>Score confirmado</th>
              <th>Criado em</th>
              <th>Nota</th>
              <th>Ação</th>
            </tr>
          </thead>

          <tbody id="manualMatchesBody"></tbody>
        </table>
      </div>
    </section>

    <p
      id="lastUpdate"
      class="footer"
    >
      Carregando dados...
    </p>
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
          throw new Error(
            `Guarda de segurança inválida: ${field}`
          );
        }
      }

      if (payload.market_data_only !== true) {
        throw new Error(
          "Payload fora do escopo de dados de mercado."
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

    async function fetchJson(path, options = {}) {
      const response = await fetch(
        path,
        {
          cache: "no-store",
          ...options
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

    async function loadBase() {
      const [
        health,
        connectors,
        matches
      ] = await Promise.all([
        fetchJson("/real-markets/matching/health"),
        fetchJson("/real-markets/connectors"),
        fetchJson("/real-markets/matching/manual-matches")
      ]);

      document.getElementById(
        "summaryGrid"
      ).innerHTML = [
        card(
          "Estado",
          health.status || "-"
        ),
        card(
          "Limiar candidato",
          Number(
            health.candidate_threshold || 0
          ).toFixed(2)
        ),
        card(
          "Limiar forte",
          Number(
            health.strong_threshold || 0
          ).toFixed(2)
        ),
        card(
          "Pares confirmados",
          Number(
            matches.count || 0
          ).toFixed(0)
        ),
        card(
          "Automático",
          "DESATIVADO",
          "rejected"
        )
      ].join("");

      const options = (
        connectors.connectors || []
      ).map(
        (item) => `
          <option value="${escapeHtml(item.connector_id)}">
            ${escapeHtml(item.name)}
          </option>
        `
      ).join("");

      const connectorA = document.getElementById(
        "connectorA"
      );

      const connectorB = document.getElementById(
        "connectorB"
      );

      connectorA.innerHTML = options;
      connectorB.innerHTML = options;

      if (connectorB.options.length > 1) {
        connectorB.selectedIndex = 1;
      }

      renderManualMatches(
        matches.matches || []
      );

      document.getElementById(
        "lastUpdate"
      ).textContent = (
        "Última atualização: "
        + new Date().toLocaleString("pt-BR")
        + " | Correspondência manual e segura"
      );
    }

    function renderManualMatches(matches) {
      const body = document.getElementById(
        "manualMatchesBody"
      );

      if (!matches.length) {
        body.innerHTML = `
          <tr>
            <td colspan="7" class="muted">
              Nenhuma correspondência manual confirmada.
            </td>
          </tr>
        `;
        return;
      }

      body.innerHTML = matches.map(
        (item) => `
          <tr>
            <td>${escapeHtml(item.id)}</td>
            <td>${escapeHtml(item.left_key)}</td>
            <td>${escapeHtml(item.right_key)}</td>
            <td>
              ${Number(
                (
                  item.score_at_confirmation
                  || {}
                ).score
                || 0
              ).toFixed(4)}
            </td>
            <td>${dateTime(item.created_at)}</td>
            <td>${escapeHtml(item.note || "-")}</td>
            <td>
              <button
                type="button"
                onclick="removeMatch('${escapeHtml(item.id)}')"
              >
                Remover
              </button>
            </td>
          </tr>
        `
      ).join("");
    }

    function renderCandidates(payload) {
      const container = document.getElementById(
        "candidateList"
      );

      const candidates = payload.candidates || [];

      if (!candidates.length) {
        container.innerHTML = `
          <p class="muted">
            Nenhum candidato acima do limiar atual.
          </p>
        `;
        return;
      }

      container.innerHTML = candidates.map(
        (item) => {
          const left = item.left || {};
          const right = item.right || {};
          const comparison = item.comparison || {};

          return `
            <article class="candidate">
              <div class="candidate-head">
                <div>
                  <div class="${css(comparison.status)} candidate-status">
                    ${escapeHtml(comparison.status)}
                  </div>

                  <div class="muted">
                    Title ${Number(
                      comparison.title_score || 0
                    ).toFixed(3)}
                    · Outcomes ${Number(
                      comparison.outcome_score || 0
                    ).toFixed(3)}
                    · Data ${Number(
                      comparison.close_time_score || 0
                    ).toFixed(3)}
                  </div>
                </div>

                <div class="score ${css(comparison.status)}">
                  ${Number(
                    comparison.score || 0
                  ).toFixed(4)}
                </div>
              </div>

              <div class="pair">
                <div class="market">
                  <strong>${escapeHtml(left.title)}</strong>
                  <div class="muted">
                    ${escapeHtml(left.key)}
                  </div>
                  <div class="muted">
                    Outcomes:
                    ${escapeHtml(
                      (left.outcome_signature || []).join(" / ")
                    )}
                  </div>
                </div>

                <div class="market">
                  <strong>${escapeHtml(right.title)}</strong>
                  <div class="muted">
                    ${escapeHtml(right.key)}
                  </div>
                  <div class="muted">
                    Outcomes:
                    ${escapeHtml(
                      (right.outcome_signature || []).join(" / ")
                    )}
                  </div>
                </div>
              </div>

              <div class="actions" style="margin-top: 12px">
                <button
                  type="button"
                  onclick='confirmMatch(${JSON.stringify({
                    left_connector_id: left.connector_id,
                    left_market_id: left.market_id,
                    right_connector_id: right.connector_id,
                    right_market_id: right.market_id
                  })})'
                >
                  Confirmar manualmente
                </button>
              </div>
            </article>
          `;
        }
      ).join("");
    }

    async function searchCandidates() {
      const connectorA = document.getElementById(
        "connectorA"
      ).value;

      const connectorB = document.getElementById(
        "connectorB"
      ).value;

      if (connectorA === connectorB) {
        window.alert(
          "Selecione conectores diferentes."
        );
        return;
      }

      const limit = Math.max(
        1,
        Math.min(
          50,
          Number(
            document.getElementById(
              "limitInput"
            ).value || 10
          )
        )
      );

      const button = document.getElementById(
        "searchButton"
      );

      button.disabled = true;
      button.textContent = "Comparando...";

      try {
        const payload = await fetchJson(
          "/real-markets/matching/candidates"
          + `?connector_a=${encodeURIComponent(connectorA)}`
          + `&connector_b=${encodeURIComponent(connectorB)}`
          + `&limit_per_connector=${encodeURIComponent(limit)}`
        );

        renderCandidates(payload);

      } catch (error) {
        window.alert(
          "Falha na comparação: "
          + error.message
        );

      } finally {
        button.disabled = false;
        button.textContent = "Comparar mercados";
      }
    }

    async function confirmMatch(pair) {
      const confirmed = window.confirm(
        "Confirmar manualmente que estes mercados são equivalentes?"
      );

      if (!confirmed) {
        return;
      }

      const note = window.prompt(
        "Nota opcional para esta correspondência:",
        ""
      );

      const tokenElement = document.getElementById(
        "phase9cConfirmationTokens"
      );

      try {
        await fetchJson(
          "/real-markets/matching/manual-matches"
          + `?confirm=${encodeURIComponent(
              tokenElement.dataset.confirmMatch
            )}`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json"
            },
            body: JSON.stringify({
              ...pair,
              note: note || null
            })
          }
        );

        await loadBase();

      } catch (error) {
        window.alert(
          "Falha na confirmação: "
          + error.message
        );
      }
    }

    async function removeMatch(matchId) {
      const confirmed = window.confirm(
        "Remover esta correspondência manual?"
      );

      if (!confirmed) {
        return;
      }

      const tokenElement = document.getElementById(
        "phase9cConfirmationTokens"
      );

      try {
        await fetchJson(
          "/real-markets/matching/manual-matches/"
          + encodeURIComponent(matchId)
          + `?confirm=${encodeURIComponent(
              tokenElement.dataset.removeMatch
            )}`,
          {
            method: "DELETE"
          }
        );

        await loadBase();

      } catch (error) {
        window.alert(
          "Falha na remoção: "
          + error.message
        );
      }
    }

    window.confirmMatch = confirmMatch;
    window.removeMatch = removeMatch;

    document.getElementById(
      "reloadButton"
    ).addEventListener(
      "click",
      loadBase
    );

    document.getElementById(
      "searchButton"
    ).addEventListener(
      "click",
      searchCandidates
    );

    loadBase();
  </script>
</body>
</html>
"""


def _safe_flags() -> dict:
    return {
        "market_data_only": True,
        "read_only": True,
        "automatic_matching_authorized": False,
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "next_step_authorized": False,
    }


@router.get("/health")
async def market_matching_health():
    return (
        market_matching_service
        .health()
    )


@router.get("/identities")
async def market_matching_identities(
    connector_id: str | None = Query(
        default=None
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
    ),
):
    try:
        identities = await (
            market_matching_service
            .list_identities(
                connector_id=connector_id,
                limit=limit,
            )
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    return {
        "count": len(identities),
        "connector_id": connector_id,
        "identities": [
            item.to_dict()
            for item in identities
        ],
        **_safe_flags(),
    }


@router.get("/compare")
async def market_matching_compare(
    left_connector_id: str = Query(...),
    left_market_id: str = Query(...),
    right_connector_id: str = Query(...),
    right_market_id: str = Query(...),
):
    try:
        return await (
            market_matching_service
            .compare_keys(
                left_connector_id=(
                    left_connector_id
                ),
                left_market_id=(
                    left_market_id
                ),
                right_connector_id=(
                    right_connector_id
                ),
                right_market_id=(
                    right_market_id
                ),
            )
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.get("/candidates")
async def market_matching_candidates(
    connector_a: str = Query(...),
    connector_b: str = Query(...),
    limit_per_connector: int = Query(
        default=50,
        ge=1,
        le=250,
    ),
    min_score: float | None = Query(
        default=None,
        ge=0,
        le=1,
    ),
    include_rejected: bool = Query(
        default=False
    ),
):
    try:
        return await (
            market_matching_service
            .candidates(
                connector_a=connector_a,
                connector_b=connector_b,
                limit_per_connector=(
                    limit_per_connector
                ),
                min_score=min_score,
                include_rejected=(
                    include_rejected
                ),
            )
        )

    except (
        KeyError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get("/manual-matches")
async def market_matching_manual_matches():
    return (
        market_matching_service
        .manual_matches()
    )


@router.post("/manual-matches")
async def market_matching_confirm_manual_match(
    request: ManualMatchRequest,
    confirm: str = Query(...),
):
    if (
        confirm
        != "CONFIRM-REAL-MARKET-MATCH"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Confirmação inválida. Use "
                "CONFIRM-REAL-MARKET-MATCH."
            ),
        )

    try:
        return await (
            market_matching_service
            .confirm_manual_match(
                left_connector_id=(
                    request.left_connector_id
                ),
                left_market_id=(
                    request.left_market_id
                ),
                right_connector_id=(
                    request.right_connector_id
                ),
                right_market_id=(
                    request.right_market_id
                ),
                note=request.note,
            )
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


@router.delete(
    "/manual-matches/{match_id}"
)
async def market_matching_remove_manual_match(
    match_id: str,
    confirm: str = Query(...),
):
    if (
        confirm
        != "REMOVE-REAL-MARKET-MATCH"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Confirmação inválida. Use "
                "REMOVE-REAL-MARKET-MATCH."
            ),
        )

    payload = (
        market_matching_service
        .remove_manual_match(
            match_id
        )
    )

    if payload["removed"] is not True:
        raise HTTPException(
            status_code=404,
            detail=(
                "Correspondência manual "
                "não encontrada."
            ),
        )

    return payload


@router.get(
    "/dashboard",
    response_class=HTMLResponse,
)
async def market_matching_dashboard():
    return HTMLResponse(
        content=DASHBOARD_HTML,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-PredArb-Automatic-Matching": "false",
            "X-PredArb-Live-Authorization": "false",
            "X-PredArb-Financial-Execution": "false",
            "X-PredArb-Next-Step-Authorization": "false",
        },
    )


@router.get("/architecture")
async def market_matching_architecture():
    return {
        "phase": "9C",
        "name": (
            "Market Identity and Matching"
        ),
        "components": [
            "text_normalization",
            "market_fingerprint",
            "outcome_signature",
            "close_time_similarity",
            "weighted_similarity_score",
            "candidate_generation",
            "manual_confirmation_store",
        ],
        "score_weights": {
            "title": 0.60,
            "outcomes": 0.20,
            "close_time": 0.15,
            "category": 0.05,
        },
        "manual_confirmation_required": True,
        "automatic_matching_authorized": False,
        "explicitly_excluded": [
            "automatic_pair_activation",
            "order_execution",
            "wallet_access",
            "balance_access",
            "financial_authorization",
        ],
        **_safe_flags(),
    }
