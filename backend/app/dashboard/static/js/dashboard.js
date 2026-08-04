import {
    ensureDashboardSession,
} from "./session.js";

await ensureDashboardSession();

import { loadSnapshot } from "./api.js";
import { renderRouterSummary } from "./charts.js";
import { RouterSocket } from "./websocket.js";
import {
    badge,
    byId,
    collection,
    first,
    formatCurrency,
    formatDateTime,
    formatNumber,
    formatPercent,
    number,
    renderCards,
    renderRows,
    setSystemStatus,
    shortId,
} from "./widgets.js";

const REFRESH_INTERVAL_MS = 10000;
let refreshTimer = null;
let refreshing = false;
let lastSnapshot = null;

function showAlert(message = "") {
    const alert = byId("global-alert");
    alert.textContent = message;
    alert.hidden = !message;
}

function setConnectionStatus(status, detail = null) {
    const element = byId("connection-status");
    const labels = {
        connected: "WebSocket conectado",
        connecting: "Conectando WebSocket",
        reconnecting: "Reconectando WebSocket",
        disconnected: "WebSocket desconectado",
        error: "Erro no WebSocket",
        "auth-refreshing": "Renovando sess?o",
        "auth-restored": "Sess?o renovada",
        "auth-required": "Autentica??o necess?ria",
        "invalid-message": "Mensagem WebSocket inválida",
    };

    element.textContent = labels[status] || status;
    element.classList.toggle("connected", status === "connected");

    if (status === "reconnecting" && detail?.delay) {
        element.textContent += ` em ${Math.round(detail.delay / 1000)}s`;
    }
}

function renderPortfolio(snapshot) {
    const portfolio = snapshot?.data?.portfolio || {};
    const definitions = [
        ["Valor total", first(portfolio, ["total", "equity", "value"], snapshot.portfolio)],
        ["Disponível", first(portfolio, ["available", "free"], 0)],
        ["Bloqueado", first(portfolio, ["locked", "reserved", "allocated"], 0)],
        ["PnL", snapshot.pnl],
    ];

    const container = byId("portfolio-summary");
    container.replaceChildren();

    for (const [label, value] of definitions) {
        const wrapper = document.createElement("div");
        wrapper.className = "summary-item";

        const dt = document.createElement("dt");
        dt.textContent = label;

        const dd = document.createElement("dd");
        dd.textContent = formatCurrency(value);

        wrapper.append(dt, dd);
        container.append(wrapper);
    }
}


function opportunityLeg(row, key) {
    const leg = row?.[key];

    if (leg && typeof leg === "object") {
        const venue = first(
            leg,
            ["platform", "venue", "exchange", "source"],
            "?",
        );

        const price = first(
            leg,
            ["price", "odds", "value"],
            null,
        );

        return price === null
            ? venue
            : `${venue} @ ${formatNumber(price, 4)}`;
    }

    return leg || "?";
}

function renderOpportunities(snapshot) {
    const rows = collection(
        snapshot?.data?.opportunities
        ?? snapshot?.opportunities,
    ).slice(0, 50);

    byId("opportunities-count").textContent =
        `${rows.length} registros`;

    renderRows(
        byId("opportunities-body"),
        rows,
        [
            {
                value: (row) => first(
                    row,
                    [
                        "question",
                        "title",
                        "market",
                        "symbol",
                        "id",
                    ],
                    "Mercado n?o informado",
                ),
                className: "table-primary",
                title: (row) => first(
                    row,
                    [
                        "question",
                        "title",
                        "market",
                        "symbol",
                        "id",
                    ],
                    "",
                ),
            },
            {
                value: (row) => opportunityLeg(
                    row,
                    "buy_yes",
                ),
            },
            {
                value: (row) => opportunityLeg(
                    row,
                    "buy_no",
                ),
            },
            {
                value: (row) => formatCurrency(
                    first(
                        row,
                        ["cost", "total_cost", "notional"],
                        0,
                    ),
                ),
            },
            {
                value: (row) => formatCurrency(
                    first(
                        row,
                        ["profit", "expected_profit", "pnl"],
                        0,
                    ),
                ),
            },
            {
                value: (row) => {
                    const cost = Number(
                        first(
                            row,
                            ["cost", "total_cost", "notional"],
                            0,
                        ),
                    );

                    const profit = Number(
                        first(
                            row,
                            ["profit", "expected_profit", "pnl"],
                            0,
                        ),
                    );

                    const explicitRoi = first(
                        row,
                        ["roi", "roi_percent", "return_rate"],
                        null,
                    );

                    const roi = explicitRoi === null
                        ? (
                            cost > 0
                                ? (profit / cost) * 100
                                : 0
                        )
                        : Number(explicitRoi);

                    return `${formatNumber(roi, 2)}%`;
                },
            },
            {
                value: (row) => badge(
                    first(
                        row,
                        ["status", "state"],
                        "DETECTED",
                    ),
                ),
            },
        ],
        "Nenhuma oportunidade detectada",
    );
}

function renderMarkets(snapshot) {
    const rows = collection(snapshot?.data?.markets).slice(0, 20);
    byId("markets-count").textContent = `${rows.length} registros`;

    renderRows(byId("markets-body"), rows, [
        {
            value: (row) => first(row, ["question", "title", "market", "symbol", "id"]),
            className: "table-primary",
            title: (row) => first(row, ["question", "title", "market", "symbol", "id"]),
        },
        { value: (row) => first(row, ["platform", "venue", "exchange", "source"]) },
        { value: (row) => formatNumber(first(row, ["yes_price", "yes", "price_yes"], 0), 4) },
        { value: (row) => formatNumber(first(row, ["no_price", "no", "price_no"], 0), 4) },
        { value: (row) => badge(first(row, ["status", "state"], "ACTIVE")) },
    ], "Nenhum mercado sincronizado");
}

function renderOrders(snapshot) {
    const rows = collection(snapshot?.data?.orders).slice(0, 25);
    byId("orders-count").textContent = `${rows.length} registros`;

    renderRows(byId("orders-body"), rows, [
        { value: (row) => shortId(first(row, ["id", "order_id"])), className: "table-muted" },
        { value: (row) => first(row, ["platform", "venue", "exchange"]) },
        { value: (row) => first(row, ["leg"], "—") },
        { value: (row) => first(row, ["side"], "—") },
        { value: (row) => formatNumber(first(row, ["quantity", "size"], 0), 4) },
        { value: (row) => formatNumber(first(row, ["price", "average_price"], 0), 4) },
        { value: (row) => badge(first(row, ["status", "state"], "UNKNOWN")) },
    ], "Nenhuma ordem registrada no OMS");
}

function renderPositions(snapshot) {
    const rows = collection(snapshot?.data?.positions).slice(0, 20);
    byId("positions-count").textContent = `${rows.length} registros`;

    renderRows(byId("positions-body"), rows, [
        {
            value: (row) => first(row, ["market", "symbol", "question", "id"]),
            className: "table-primary",
        },
        { value: (row) => formatNumber(first(row, ["quantity", "size", "exposure"], 0), 4) },
        { value: (row) => formatCurrency(first(row, ["pnl", "profit", "unrealized_pnl"], 0)) },
        { value: (row) => badge(first(row, ["status", "state"], "OPEN")) },
    ], "Nenhuma posição aberta");
}

function renderVenues(routerSnapshot = {}) {
    const entries = Object.entries(routerSnapshot?.venues || {}).slice(0, 20);
    byId("venues-count").textContent = `${entries.length} venues`;

    const rows = entries.map(([name, metrics]) => ({ name, ...metrics }));

    renderRows(byId("venues-body"), rows, [
        { value: (row) => row.name, className: "table-primary" },
        { value: (row) => formatPercent(first(row, ["success_rate", "success"], 0), 1) },
        { value: (row) => `${formatNumber(first(row, ["average_latency_ms", "latency"], 0), 1)} ms` },
        { value: (row) => formatPercent(first(row, ["average_slippage_rate", "slippage"], 0), 2) },
        { value: (row) => formatNumber(first(row, ["samples", "orders"], 0), 0) },
    ], "O AI Router ainda não possui histórico");
}


function renderPaperMetrics(paper = {}) {
    const wallet = paper?.wallet || {};
    const analytics = paper?.equity_analytics || {};
    const definitions = [
        ["Saldo", formatCurrency(first(wallet, ["balance", "cash"], 0)), "Caixa virtual"],
        ["Equity", formatCurrency(first(paper, ["equity"], 0)), "Caixa + posições"],
        ["PnL total", formatCurrency(first(paper, ["total_pnl"], 0)), "Realizado + não realizado"],
        ["PnL realizado", formatCurrency(first(paper, ["realized_pnl"], 0)), "Posições encerradas"],
        ["PnL não realizado", formatCurrency(first(paper, ["unrealized_pnl"], 0)), "Mark-to-market"],
        ["Drawdown máx.", formatPercent(first(analytics, ["max_drawdown_rate"], 0), 2), "Curva persistida"],
    ];

    const container = byId("paper-metrics");
    container.replaceChildren();

    for (const [label, value, detail] of definitions) {
        const item = document.createElement("article");
        item.className = "paper-metric";

        const labelElement = document.createElement("span");
        labelElement.textContent = label;

        const valueElement = document.createElement("strong");
        valueElement.textContent = value;

        const detailElement = document.createElement("small");
        detailElement.textContent = detail;

        item.append(labelElement, valueElement, detailElement);
        container.append(item);
    }
}

function renderPaperCurve(paper = {}) {
    const svg = byId("paper-equity-chart");
    const empty = byId("paper-chart-empty");
    const points = collection(paper?.equity_curve).slice(-120);
    const analytics = paper?.equity_analytics || {};

    byId("paper-equity-current").textContent = formatCurrency(first(paper, ["equity"], 0));
    byId("paper-return").textContent = formatPercent(first(paper, ["return_rate"], 0), 2);
    byId("paper-drawdown").textContent = formatPercent(first(analytics, ["max_drawdown_rate"], 0), 2);
    byId("paper-curve-points").textContent = formatNumber(points.length, 0);

    svg.replaceChildren();
    empty.hidden = points.length > 0;
    if (!points.length) {
        return;
    }

    const namespace = "http://www.w3.org/2000/svg";
    const width = 900;
    const height = 220;
    const paddingX = 18;
    const paddingY = 18;
    const values = points.map((item) => number(item?.equity));
    let minimum = Math.min(...values);
    let maximum = Math.max(...values);

    if (minimum === maximum) {
        minimum -= Math.max(1, Math.abs(minimum) * 0.002);
        maximum += Math.max(1, Math.abs(maximum) * 0.002);
    }

    const range = maximum - minimum;
    const coords = values.map((value, index) => {
        const x = points.length === 1
            ? width / 2
            : paddingX + (index / (points.length - 1)) * (width - paddingX * 2);
        const y = paddingY + ((maximum - value) / range) * (height - paddingY * 2);
        return [x, y];
    });

    const defs = document.createElementNS(namespace, "defs");
    const gradient = document.createElementNS(namespace, "linearGradient");
    gradient.setAttribute("id", "paper-equity-gradient");
    gradient.setAttribute("x1", "0");
    gradient.setAttribute("y1", "0");
    gradient.setAttribute("x2", "0");
    gradient.setAttribute("y2", "1");

    const stopTop = document.createElementNS(namespace, "stop");
    stopTop.setAttribute("offset", "0%");
    stopTop.setAttribute("stop-color", "#34d399");
    stopTop.setAttribute("stop-opacity", "0.28");

    const stopBottom = document.createElementNS(namespace, "stop");
    stopBottom.setAttribute("offset", "100%");
    stopBottom.setAttribute("stop-color", "#34d399");
    stopBottom.setAttribute("stop-opacity", "0");

    gradient.append(stopTop, stopBottom);
    defs.append(gradient);
    svg.append(defs);

    const initial = number(points[0]?.equity);
    const baselineY = paddingY + ((maximum - initial) / range) * (height - paddingY * 2);
    const baseline = document.createElementNS(namespace, "line");
    baseline.classList.add("equity-baseline");
    baseline.setAttribute("x1", String(paddingX));
    baseline.setAttribute("x2", String(width - paddingX));
    baseline.setAttribute("y1", String(baselineY));
    baseline.setAttribute("y2", String(baselineY));
    svg.append(baseline);

    const linePath = coords
        .map(([x, y], index) => `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`)
        .join(" ");
    const areaPath = `${linePath} L${coords.at(-1)[0].toFixed(2)},${height - paddingY} L${coords[0][0].toFixed(2)},${height - paddingY} Z`;

    const area = document.createElementNS(namespace, "path");
    area.classList.add("equity-area");
    area.setAttribute("d", areaPath);

    const line = document.createElementNS(namespace, "path");
    line.classList.add("equity-line");
    line.setAttribute("d", linePath);

    const last = coords.at(-1);
    const dot = document.createElementNS(namespace, "circle");
    dot.classList.add("equity-dot");
    dot.setAttribute("cx", String(last[0]));
    dot.setAttribute("cy", String(last[1]));
    dot.setAttribute("r", "5");

    svg.append(area, line, dot);
}

function renderPaperPositions(paper = {}) {
    const rows = collection(paper?.positions).slice(0, 30);
    byId("paper-positions-count").textContent = `${rows.length} registros`;

    renderRows(byId("paper-positions-body"), rows, [
        {
            value: (row) => first(row, ["market", "symbol", "id"]),
            className: "table-primary",
            title: (row) => first(row, ["market", "symbol", "id"]),
        },
        { value: (row) => first(row, ["leg"], "—") },
        { value: (row) => formatNumber(first(row, ["quantity"], 0), 4) },
        { value: (row) => formatNumber(first(row, ["average_price"], 0), 4) },
        { value: (row) => formatNumber(first(row, ["mark_price"], 0), 4) },
        { value: (row) => formatCurrency(first(row, ["total_pnl", "unrealized_pnl", "realized_pnl"], 0)) },
        { value: (row) => badge(first(row, ["status"], "UNKNOWN")) },
    ], "Nenhuma posição Paper registrada");
}

function renderPaperTrades(paper = {}) {
    const rows = collection(paper?.trades).slice(-30).reverse();
    byId("paper-trades-count").textContent = `${rows.length} registros`;

    renderRows(byId("paper-trades-body"), rows, [
        { value: (row) => formatDateTime(first(row, ["executed_at"], null)), className: "table-muted" },
        {
            value: (row) => first(row, ["market", "symbol", "order_id"]),
            className: "table-primary",
            title: (row) => first(row, ["market", "symbol", "order_id"]),
        },
        { value: (row) => first(row, ["side"], "—") },
        { value: (row) => first(row, ["leg"], "—") },
        { value: (row) => formatNumber(first(row, ["quantity"], 0), 4) },
        { value: (row) => formatNumber(first(row, ["price"], 0), 4) },
        { value: (row) => formatCurrency(first(row, ["fee"], 0)) },
    ], "Nenhum trade Paper registrado");
}

function renderPaper(snapshot) {
    const paper = snapshot?.data?.paper || {};
    const enabled = paper?.enabled !== false && String(paper?.status || "").toUpperCase() !== "DISABLED";
    const status = enabled ? String(paper?.status || "READY").toUpperCase() : "DISABLED";

    const statusElement = byId("paper-status");
    statusElement.textContent = status;
    statusElement.className = `mini-badge ${enabled ? "connected" : ""}`;

    const persistence = byId("paper-persistence");
    persistence.textContent = paper?.last_persisted_at
        ? `Persistida ${formatDateTime(paper.last_persisted_at)}`
        : paper?.dirty
            ? "Alterações pendentes"
            : "Sem alterações pendentes";

    renderPaperMetrics(paper);
    renderPaperCurve(paper);
    renderPaperPositions(paper);
    renderPaperTrades(paper);
}

function renderEvents(snapshot) {
    const events = collection(snapshot?.events).slice(0, 30);
    const container = byId("events-list");
    container.replaceChildren();

    if (!events.length) {
        const empty = document.createElement("div");
        empty.className = "diagnostic-item";
        empty.textContent = "Nenhum evento registrado.";
        container.append(empty);
        return;
    }

    for (const event of events) {
        const item = document.createElement("article");
        item.className = "event-item";

        const dot = document.createElement("span");
        dot.className = "event-dot";

        const copy = document.createElement("div");
        const title = document.createElement("strong");
        title.textContent = event.text || event.type || "Evento";
        const detail = document.createElement("small");
        detail.textContent = String(event.type || "info").toUpperCase();
        copy.append(title, detail);

        const time = document.createElement("span");
        time.className = "event-time";
        time.textContent = event.time || formatDateTime(event.created_at);

        item.append(dot, copy, time);
        container.append(item);
    }
}

function renderDiagnostics(snapshot) {
    const diagnostics = snapshot?.diagnostics || {};
    const sources = diagnostics.sources || {};
    const errors = diagnostics.errors || {};
    const rows = [
        ["Status do snapshot", snapshot.status || "UNKNOWN"],
        ["Mercados", formatNumber(sources.markets ?? snapshot.markets, 0)],
        ["Ordens", formatNumber(sources.orders ?? snapshot.orders, 0)],
        ["Posições", formatNumber(sources.positions ?? snapshot.positions, 0)],
        ["Trades", formatNumber(sources.trades, 0)],
        ["Posições Paper", formatNumber(sources.paper_positions, 0)],
        ["Trades Paper", formatNumber(sources.paper_trades, 0)],
        ["Erros de fonte", formatNumber(Object.keys(errors).length, 0)],
    ];

    for (const [source, message] of Object.entries(errors)) {
        rows.push([`Erro: ${source}`, String(message)]);
    }

    const container = byId("diagnostics-list");
    container.replaceChildren();

    for (const [label, value] of rows) {
        const item = document.createElement("div");
        item.className = "diagnostic-item";

        const labelElement = document.createElement("span");
        labelElement.textContent = label;

        const valueElement = document.createElement("strong");
        valueElement.textContent = value;

        item.append(labelElement, valueElement);
        container.append(item);
    }
}

function applySnapshot(snapshot) {
    lastSnapshot = snapshot;
    setSystemStatus(byId("system-status"), snapshot.status);
    byId("last-updated").textContent = formatDateTime(snapshot.updated_at);

    renderCards(byId("metric-cards"), snapshot.cards || []);
    renderPortfolio(snapshot);
    renderMarkets(snapshot);
    renderOpportunities(snapshot);
    renderOrders(snapshot);
    renderPositions(snapshot);
    renderPaper(snapshot);
    renderEvents(snapshot);
    renderDiagnostics(snapshot);

    const routerSnapshot = snapshot?.data?.router || {};
    renderRouterSummary(routerSnapshot);
    renderVenues(routerSnapshot);

    const sourceErrors = Object.keys(snapshot?.diagnostics?.errors || {});
    showAlert(sourceErrors.length
        ? `Dashboard em modo degradado. Fontes indisponíveis: ${sourceErrors.join(", ")}.`
        : "");
}

async function refreshDashboard({ manual = false } = {}) {
    if (refreshing) {
        return;
    }

    refreshing = true;
    const button = byId("refresh-button");
    button.disabled = true;
    button.textContent = "Atualizando…";

    try {
        const snapshot = await loadSnapshot(true);
        applySnapshot(snapshot);
    } catch (error) {
        console.error("Falha ao atualizar o Dashboard", error);
        setSystemStatus(byId("system-status"), "OFFLINE");
        showAlert(error?.message || "Falha ao consultar o Dashboard.");

        if (manual && lastSnapshot) {
            byId("last-updated").textContent = `${formatDateTime(lastSnapshot.updated_at)} (cache local)`;
        }
    } finally {
        refreshing = false;
        button.disabled = false;
        button.textContent = "Atualizar";
    }
}

function scheduleRefresh() {
    window.clearInterval(refreshTimer);
    refreshTimer = window.setInterval(
        () => refreshDashboard(),
        REFRESH_INTERVAL_MS,
    );
}

function startWebSocket() {
    const socket = new RouterSocket({
        path: window.PREDARB_DASHBOARD?.routerWsPath || "/ws/router",
        onData: (routerSnapshot) => {
            renderRouterSummary(routerSnapshot);
            renderVenues(routerSnapshot);
        },
        onStatus: setConnectionStatus,
    });

    socket.connect();
    window.addEventListener("beforeunload", () => socket.close(), { once: true });
}


const DASHBOARD_VIEWS = {
    overview: "Visão Geral",
    "markets-panel": "Mercados",
    "opportunities-panel": "Oportunidades",
    "real-radar-panel": "Radar Real",
    "crypto-scanner-panel": "Scanner Cripto",
    "orders-panel": "Ordens",
    "positions-panel": "Posições",
    "paper-panel": "Conta Paper",
    "router-panel": "AI Router",
    "events-panel": "Eventos",
};

function topLevelSection(element) {
    const main = document.querySelector(".main-content");
    let current = element;

    while (
        current?.parentElement
        && current.parentElement !== main
    ) {
        current = current.parentElement;
    }

    return current;
}

function activateDashboardView() {
    const requestedId = (
        window.location.hash || "#overview"
    ).slice(1);

    const viewId = DASHBOARD_VIEWS[requestedId]
        ? requestedId
        : "overview";

    const target = document.getElementById(viewId);
    const main = document.querySelector(".main-content");

    if (!target || !main) {
        return;
    }

    const directSections = Array.from(
        main.children,
    ).filter(
        (element) => element.tagName === "SECTION",
    );

    for (const section of directSections) {
        section.hidden = true;
    }

    for (const nestedId of [
        "positions-panel",
        "router-panel",
    ]) {
        const nested = document.getElementById(nestedId);

        if (nested) {
            nested.hidden = false;
        }
    }

    const root = topLevelSection(target);

    if (root) {
        root.hidden = false;
    }

    if (viewId === "paper-panel") {
        const paperTables = document.querySelector(
            '[data-dashboard-group="paper"]',
        );

        if (paperTables) {
            paperTables.hidden = false;
        }
    }

    if (viewId === "positions-panel") {
        const routerPanel = byId("router-panel");

        if (routerPanel) {
            routerPanel.hidden = true;
        }
    }

    if (viewId === "router-panel") {
        const positionsPanel = byId("positions-panel");

        if (positionsPanel) {
            positionsPanel.hidden = true;
        }
    }

    const title = byId("overview-title");

    if (title) {
        title.textContent = DASHBOARD_VIEWS[viewId];
    }

    const links = document.querySelectorAll(
        ".nav-link[href^='#']",
    );

    for (const link of links) {
        link.classList.toggle(
            "active",
            link.getAttribute("href") === `#${viewId}`,
        );
    }

    window.scrollTo({
        top: 0,
        behavior: "instant",
    });
}

function initializeNavigation() {
    const links = document.querySelectorAll(
        ".nav-link[href^='#']",
    );

    for (const link of links) {
        link.addEventListener(
            "click",
            () => window.setTimeout(
                activateDashboardView,
                0,
            ),
        );
    }

    window.addEventListener(
        "hashchange",
        activateDashboardView,
    );

    activateDashboardView();
}

async function initialize() {
    initializeNavigation();
    byId("refresh-button").addEventListener("click", () => refreshDashboard({ manual: true }));

    await refreshDashboard();
    scheduleRefresh();
    startWebSocket();
}

initialize().catch((error) => {
    console.error("Falha ao iniciar o Dashboard", error);
    showAlert(error?.message || "Falha ao iniciar o Dashboard.");
});


const realRadarState = {
  timer: null,
  loading: false,
};

function realRadarNumber(value, digits = 3) {
  const parsed = Number(value);

  if (!Number.isFinite(parsed)) {
    return "?";
  }

  return parsed.toFixed(digits);
}

function realRadarPercent(value) {
  const parsed = Number(value);

  if (!Number.isFinite(parsed)) {
    return "?";
  }

  return `${(parsed * 100).toFixed(2)}%`;
}

function realRadarSignedPercent(value) {
  if (value === null || value === undefined) {
    return "\u2014";
  }

  const parsed = Number(value);

  if (!Number.isFinite(parsed)) {
    return "\u2014";
  }

  const prefix = parsed > 0 ? "+" : "";

  return `${prefix}${(parsed * 100).toFixed(2)}%`;
}

function realRadarStatusLabel(status) {
  const labels = {
    PROFITABLE: "Lucrativa",
    NEAR_OPPORTUNITY: "Pr\u00f3xima",
    NORMAL: "Normal",
  };

  return labels[status] || status || "Indefinido";
}

function realRadarTrendLabel(trend) {
  const labels = {
    NEW: "Novo",
    IMPROVING: "Melhorando",
    WORSENING: "Piorando",
    STABLE: "Est\u00e1vel",
  };

  return labels[trend] || trend || "Indefinido";
}

function realRadarTrendClass(trend) {
  const classes = {
    NEW: "real-radar-trend-new",
    IMPROVING: "real-radar-trend-improving",
    WORSENING: "real-radar-trend-worsening",
    STABLE: "",
  };

  return classes[trend] || "";
}

function realRadarCell(row, value) {
  const cell = document.createElement("td");
  cell.textContent = value;
  row.appendChild(cell);
  return cell;
}

function realRadarTrendCell(row, item) {
  const cell = document.createElement("td");
  const badge = document.createElement("span");

  badge.className = "real-radar-trend-badge";

  const trendClass = realRadarTrendClass(
    item.trend,
  );

  if (trendClass) {
    badge.classList.add(trendClass);
  }

  badge.textContent = realRadarTrendLabel(
    item.trend,
  );

  cell.appendChild(badge);
  row.appendChild(cell);

  return cell;
}

function renderRealOpportunityRadar(payload = {}) {
  const priced = document.getElementById(
    "real-radar-priced",
  );
  const profitable = document.getElementById(
    "real-radar-profitable",
  );
  const near = document.getElementById(
    "real-radar-near",
  );
  const newMarkets = document.getElementById(
    "real-radar-new",
  );
  const improving = document.getElementById(
    "real-radar-improving",
  );
  const worsening = document.getElementById(
    "real-radar-worsening",
  );
  const historyPoints = document.getElementById(
    "real-radar-history-points",
  );
  const alerts = document.getElementById(
    "real-radar-alerts",
  );
  const status = document.getElementById(
    "real-radar-status",
  );
  const body = document.getElementById(
    "real-radar-body",
  );

  if (
    !priced ||
    !profitable ||
    !near ||
    !newMarkets ||
    !improving ||
    !worsening ||
    !historyPoints ||
    !alerts ||
    !status ||
    !body
  ) {
    return;
  }

  const monitoring = payload.monitoring || {};

  priced.textContent = String(
    payload.markets_priced || 0,
  );
  profitable.textContent = String(
    payload.profitable_count || 0,
  );
  near.textContent = String(
    payload.near_opportunity_count || 0,
  );
  newMarkets.textContent = String(
    monitoring.new_count || 0,
  );
  improving.textContent = String(
    monitoring.improving_count || 0,
  );
  worsening.textContent = String(
    monitoring.worsening_count || 0,
  );
  historyPoints.textContent = String(
    monitoring.history_points || 0,
  );

  const alertItems = Array.isArray(payload.alerts)
    ? payload.alerts
    : [];

  if (alertItems.length > 0) {
    alerts.hidden = false;
    alerts.textContent =
      `${alertItems.length} mercado(s) se tornou(aram) ` +
      "lucrativo(s) desde a atualiza\u00e7\u00e3o anterior.";
  } else {
    alerts.hidden = true;
    alerts.textContent = "";
  }

  body.replaceChildren();

  const markets = Array.isArray(payload.best_markets)
    ? payload.best_markets.slice(0, 20)
    : [];

  if (markets.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");

    cell.colSpan = 9;
    cell.textContent =
      "Nenhum mercado precificado nesta atualiza\u00e7\u00e3o.";

    row.appendChild(cell);
    body.appendChild(row);
  }

  for (const item of markets) {
    const row = document.createElement("tr");

    if (item.became_profitable) {
      row.classList.add(
        "real-radar-row-profitable",
      );
    }

    realRadarCell(
      row,
      String(item.connector_id || "?"),
    );

    const marketCell = document.createElement("td");
    const sourceUrl = String(item.source_url || "");

    if (sourceUrl) {
      const link = document.createElement("a");

      link.href = sourceUrl;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = String(
        item.title || item.market_id || "Mercado",
      );

      marketCell.appendChild(link);
    } else {
      marketCell.textContent = String(
        item.title || item.market_id || "Mercado",
      );
    }

    row.appendChild(marketCell);

    realRadarCell(
      row,
      realRadarNumber(item.yes_ask),
    );
    realRadarCell(
      row,
      realRadarNumber(item.no_ask),
    );
    realRadarCell(
      row,
      realRadarNumber(item.total_cost),
    );
    realRadarCell(
      row,
      realRadarPercent(item.gross_edge),
    );
    realRadarCell(
      row,
      realRadarSignedPercent(item.edge_change),
    );
    realRadarTrendCell(
      row,
      item,
    );
    realRadarCell(
      row,
      realRadarStatusLabel(item.status),
    );

    body.appendChild(row);
  }

  const profitableCount = Number(
    payload.profitable_count || 0,
  );

  let summary;

  if (profitableCount > 0) {
    summary =
      `${profitableCount} oportunidade(s) ` +
      "lucrativa(s) detectada(s) ap\u00f3s o buffer de custos.";
  } else {
    summary =
      "Nenhuma arbitragem l\u00edquida neste momento. " +
      `${payload.near_opportunity_count || 0} mercado(s) ` +
      "est\u00e3o pr\u00f3ximos do ponto de arbitragem.";
  }

  const warnings = realRadarSnapshotWarnings(monitoring);

  if (warnings.length > 0) {
    status.textContent =
      `\u26a0 ${warnings.join(" ")} ${summary}`;
  } else {
    status.textContent = summary;
  }
}

function realRadarSeconds(value) {
  const parsed = Number(value);

  if (!Number.isFinite(parsed)) {
    return "?";
  }

  return `${Math.round(parsed)}s`;
}

function realRadarSnapshotWarnings(monitoring = {}) {
  const warnings = [];

  if (monitoring.snapshot_available === false) {
    warnings.push(
      "Snapshot ainda indispon\u00edvel: " +
        "aguardando o primeiro ciclo do coletor.",
    );

    return warnings;
  }

  if (monitoring.snapshot_is_stale === true) {
    warnings.push(
      "Snapshot desatualizado (" +
        realRadarSeconds(
          monitoring.snapshot_age_seconds,
        ) +
        " de idade, limite " +
        realRadarSeconds(
          monitoring.snapshot_max_age_seconds,
        ) +
        "). O coletor pode estar parado; " +
        "os dados abaixo podem n\u00e3o refletir o mercado atual.",
    );
  }

  if (
    monitoring.snapshot_configuration_match === false
  ) {
    warnings.push(
      "Snapshot coletado com configura\u00e7\u00e3o " +
        "diferente da solicitada.",
    );
  }

  return warnings;
}

async function refreshRealOpportunityRadar() {
  if (realRadarState.loading) {
    return;
  }

  const status = document.getElementById(
    "real-radar-status",
  );
  const button = document.getElementById(
    "real-radar-refresh",
  );

  realRadarState.loading = true;

  if (button) {
    button.disabled = true;
  }

  if (status) {
    status.textContent =
      "Atualizando pre\u00e7os reais...";
  }

  try {
    const response = await fetch(
      "/real-markets/radar/snapshot",
      {
        method: "GET",
        credentials: "same-origin",
        cache: "no-store",
        headers: {
          Accept: "application/json",
        },
      },
    );

    if (!response.ok) {
      throw new Error(
        `Radar respondeu HTTP ${response.status}`,
      );
    }

    const payload = await response.json();
    renderRealOpportunityRadar(payload);
  } catch (error) {
    if (status) {
      status.textContent =
        "N\u00e3o foi poss\u00edvel atualizar o radar: " +
        String(error?.message || error);
    }
  } finally {
    realRadarState.loading = false;

    if (button) {
      button.disabled = false;
    }
  }
}

function initializeRealOpportunityRadar() {
  const button = document.getElementById(
    "real-radar-refresh",
  );

  if (!button) {
    return;
  }

  button.addEventListener(
    "click",
    refreshRealOpportunityRadar,
  );

  refreshRealOpportunityRadar();

  realRadarState.timer = window.setInterval(
    refreshRealOpportunityRadar,
    60000,
  );
}

initializeRealOpportunityRadar();


const cryptoScannerState = {
  loading: false,
  timer: null,
};

const CRYPTO_SCANNER_STAGE_LABEL = {
  freshness: "Frescor",
  depth: "Profundidade",
  fees: "Taxas",
  profitability: "Lucratividade",
  modelling: "Modelagem",
};

function cryptoScannerText(id, value) {
  const node = document.getElementById(id);

  if (node) {
    node.textContent = value;
  }
}

// Os valores chegam como string porque o domínio cripto
// serializa Decimal. Number entra apenas para arredondar a
// exibição; o payload original permanece intacto.
function cryptoScannerNumber(value, digits = 2) {
  if (value === null || value === undefined) {
    return "—";
  }

  const parsed = Number(value);

  if (!Number.isFinite(parsed)) {
    return String(value);
  }

  return parsed.toFixed(digits);
}

function cryptoScannerPercent(value) {
  if (value === null || value === undefined) {
    return "—";
  }

  const parsed = Number(value);

  if (!Number.isFinite(parsed)) {
    return String(value);
  }

  return `${(parsed * 100).toFixed(3)}%`;
}

function cryptoScannerCell(row, value) {
  const cell = document.createElement("td");
  cell.textContent = value;
  row.appendChild(cell);

  return cell;
}

function cryptoScannerRoute(item) {
  return (
    `${item.buy_venue_id || "?"} → ` +
    `${item.sell_venue_id || "?"}`
  );
}

function cryptoScannerClearTable(id) {
  const body = document.getElementById(id);

  if (body) {
    body.innerHTML = "";
  }

  return body;
}

function cryptoScannerEmptyRow(body, columns, message) {
  const row = document.createElement("tr");
  const cell = document.createElement("td");

  cell.colSpan = columns;
  cell.textContent = message;
  row.appendChild(cell);
  body.appendChild(row);
}

function renderCryptoScannerAlerts(messages) {
  const alerts = document.getElementById(
    "crypto-scanner-alerts",
  );

  if (!alerts) {
    return;
  }

  alerts.innerHTML = "";

  if (messages.length === 0) {
    alerts.hidden = true;

    return;
  }

  messages.forEach((message) => {
    const line = document.createElement("p");
    line.textContent = message;
    alerts.appendChild(line);
  });

  alerts.hidden = false;
}

function renderCryptoScannerRejected(rejected) {
  const details = document.getElementById(
    "crypto-scanner-rejected-details",
  );
  const body = cryptoScannerClearTable(
    "crypto-scanner-rejected-body",
  );

  if (!body || !details) {
    return;
  }

  if (rejected.length === 0) {
    details.hidden = true;

    return;
  }

  details.hidden = false;

  rejected.forEach((item) => {
    const row = document.createElement("tr");

    cryptoScannerCell(row, cryptoScannerRoute(item));
    cryptoScannerCell(
      row,
      CRYPTO_SCANNER_STAGE_LABEL[item.stage] ||
        item.stage ||
        "—",
    );
    cryptoScannerCell(row, item.reason || "—");

    body.appendChild(row);
  });
}

// last_venue_errors é o que distingue "nenhuma rota fecha"
// de "a venue está fora do ar". São diagnósticos diferentes
// e pedem ações diferentes.
function cryptoScannerVenueAlerts(status) {
  const errors = status.last_venue_errors || {};

  return Object.keys(errors).map(
    (venue) =>
      `⚠ ${venue} não respondeu: ${errors[venue]}`,
  );
}

function renderCryptoScannerStatus(status) {
  cryptoScannerText(
    "crypto-scanner-cycles",
    status.cycles ?? 0,
  );
  cryptoScannerText(
    "crypto-scanner-failures",
    status.failures ?? 0,
  );
  cryptoScannerText(
    "crypto-scanner-venues",
    status.last_venues_collected ?? 0,
  );
  cryptoScannerText(
    "crypto-scanner-last-status",
    status.last_status || "—",
  );
}

function renderCryptoScannerDisabled(payload) {
  cryptoScannerText("crypto-scanner-pair", "—");
  cryptoScannerText("crypto-scanner-opportunities", 0);
  cryptoScannerText("crypto-scanner-rejected", 0);
  renderCryptoScannerRejected([]);
  renderCryptoScannerAlerts([]);

  const body = cryptoScannerClearTable(
    "crypto-scanner-body",
  );

  if (body) {
    cryptoScannerEmptyRow(
      body,
      10,
      "Scanner desligado.",
    );
  }

  cryptoScannerText(
    "crypto-scanner-status",
    payload.detail ||
      "CRYPTO_SCANNER_ENABLED está desligado. " +
        "Nenhum ciclo é executado.",
  );
}

function renderCryptoScanner(payload, status) {
  renderCryptoScannerStatus(status);

  const pair = payload.pair || {};

  cryptoScannerText(
    "crypto-scanner-pair",
    pair.canonical ||
      (pair.base_asset && pair.quote_asset
        ? `${pair.base_asset}/${pair.quote_asset}`
        : "—"),
  );

  const opportunities = payload.opportunities || [];
  const rejected = payload.rejected || [];

  cryptoScannerText(
    "crypto-scanner-opportunities",
    opportunities.length,
  );
  cryptoScannerText(
    "crypto-scanner-rejected",
    rejected.length,
  );

  const body = cryptoScannerClearTable(
    "crypto-scanner-body",
  );

  if (!body) {
    return;
  }

  if (opportunities.length === 0) {
    cryptoScannerEmptyRow(
      body,
      10,
      "Nenhuma rota líquida no último ciclo.",
    );
  }

  opportunities.forEach((item) => {
    const breakdown = item.breakdown || {};
    const row = document.createElement("tr");

    if (item.is_profitable_on_paper === true) {
      row.classList.add(
        "real-radar-row-profitable",
      );
    }

    cryptoScannerCell(row, cryptoScannerRoute(item));
    cryptoScannerCell(
      row,
      cryptoScannerNumber(
        item.executable_quantity,
        6,
      ),
    );
    cryptoScannerCell(
      row,
      cryptoScannerNumber(item.buy_vwap),
    );
    cryptoScannerCell(
      row,
      cryptoScannerNumber(item.sell_vwap),
    );
    cryptoScannerCell(
      row,
      cryptoScannerNumber(item.gross_profit, 4),
    );
    cryptoScannerCell(
      row,
      cryptoScannerNumber(item.total_fees, 4),
    );
    cryptoScannerCell(
      row,
      cryptoScannerNumber(
        breakdown.total_reserves,
        4,
      ),
    );
    cryptoScannerCell(
      row,
      cryptoScannerNumber(
        item.expected_net_profit,
        4,
      ),
    );
    cryptoScannerCell(
      row,
      cryptoScannerPercent(breakdown.expected_roi),
    );
    cryptoScannerCell(
      row,
      item.risk_status || "—",
    );

    body.appendChild(row);
  });

  renderCryptoScannerRejected(rejected);
  renderCryptoScannerAlerts(
    cryptoScannerVenueAlerts(status),
  );

  let summary;

  if (opportunities.length > 0) {
    summary =
      `${opportunities.length} rota(s) com lucro ` +
      "líquido positivo após taxas e reservas.";
  } else {
    summary =
      "Nenhuma ineficiência líquida neste ciclo. " +
      `${rejected.length} rota(s) descartada(s).`;
  }

  if (payload.status === "WARMING_UP") {
    summary =
      payload.detail ||
      "Aguardando o primeiro ciclo do coletor.";
  }

  cryptoScannerText("crypto-scanner-status", summary);
}

async function cryptoScannerFetch(path) {
  const response = await fetch(path, {
    method: "GET",
    credentials: "same-origin",
    cache: "no-store",
    headers: {
      Accept: "application/json",
    },
  });

  // 401/403 aqui significam sessão ausente ou sem MFA, não
  // falha do scanner. Distinguir evita repetir na Fase 20D o
  // defeito de mensagem única já registrado no login.
  if (
    response.status === 401 ||
    response.status === 403
  ) {
    const error = new Error(
      "Sessão expirada ou sem MFA. " +
        "Entre novamente para ver o scanner cripto.",
    );

    error.isAuthError = true;

    throw error;
  }

  if (!response.ok) {
    throw new Error(
      `Scanner respondeu HTTP ${response.status}`,
    );
  }

  return response.json();
}

async function refreshCryptoScanner() {
  if (cryptoScannerState.loading) {
    return;
  }

  const button = document.getElementById(
    "crypto-scanner-refresh",
  );

  cryptoScannerState.loading = true;

  if (button) {
    button.disabled = true;
  }

  cryptoScannerText(
    "crypto-scanner-status",
    "Atualizando scanner cripto...",
  );

  try {
    const payload = await cryptoScannerFetch(
      "/crypto/scanner/snapshot",
    );

    if (payload.status === "DISABLED") {
      renderCryptoScannerDisabled(payload);
      renderCryptoScannerStatus({
        last_status: "DISABLED",
      });

      return;
    }

    // O status é complementar: se falhar, o snapshot ainda
    // vale e o painel não deve ficar em branco por causa dele.
    let status = {};

    try {
      status = await cryptoScannerFetch(
        "/crypto/scanner/status",
      );
    } catch (statusError) {
      status = {
        last_status: "STATUS_INDISPONÍVEL",
      };
    }

    renderCryptoScanner(payload, status);
  } catch (error) {
    renderCryptoScannerAlerts([]);

    cryptoScannerText(
      "crypto-scanner-status",
      error?.isAuthError
        ? String(error.message)
        : "Não foi possível atualizar o scanner: " +
            String(error?.message || error),
    );
  } finally {
    cryptoScannerState.loading = false;

    if (button) {
      button.disabled = false;
    }
  }
}

function initializeCryptoScanner() {
  const button = document.getElementById(
    "crypto-scanner-refresh",
  );

  if (!button) {
    return;
  }

  button.addEventListener(
    "click",
    refreshCryptoScanner,
  );

  refreshCryptoScanner();

  cryptoScannerState.timer = window.setInterval(
    refreshCryptoScanner,
    60000,
  );
}

initializeCryptoScanner();
