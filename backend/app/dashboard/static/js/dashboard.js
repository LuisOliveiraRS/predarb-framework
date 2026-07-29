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

function initializeNavigation() {
    const links = document.querySelectorAll(".nav-link[href^='#']");
    for (const link of links) {
        link.addEventListener("click", () => {
            for (const other of links) {
                other.classList.toggle("active", other === link);
            }
        });
    }
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
