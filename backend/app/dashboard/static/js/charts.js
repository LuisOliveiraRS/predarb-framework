import {
    byId,
    formatNumber,
    formatPercent,
    number,
} from "./widgets.js";

export function renderRouterSummary(routerSnapshot = {}) {
    const summary = routerSnapshot?.summary || {};
    const status = String(routerSnapshot?.status || "SEM DADOS").toUpperCase();
    const confidence = Math.min(1, Math.max(0, number(
        summary.confidence ?? summary.average_confidence,
    )));

    byId("router-status").textContent = status;
    byId("router-confidence").textContent = formatPercent(confidence, 1);
    byId("router-confidence-bar").style.width = `${confidence * 100}%`;

    const definitions = [
        ["Execuções", formatNumber(summary.orders ?? summary.reports, 0)],
        ["Venues", formatNumber(summary.venues, 0)],
        ["Sucesso", formatPercent(summary.success_rate, 1)],
        ["Latência", `${formatNumber(summary.average_latency_ms, 1)} ms`],
    ];

    const container = byId("router-kpis");
    container.replaceChildren();

    for (const [label, value] of definitions) {
        const item = document.createElement("div");
        item.className = "kpi-item";

        const labelElement = document.createElement("span");
        labelElement.textContent = label;

        const valueElement = document.createElement("strong");
        valueElement.textContent = value;

        item.append(labelElement, valueElement);
        container.append(item);
    }
}
