export function byId(id) {
    return document.getElementById(id);
}

export function collection(value) {
    if (Array.isArray(value)) {
        return value;
    }
    if (value && typeof value === "object") {
        return Object.values(value);
    }
    return [];
}

export function number(value, fallback = 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
}

export function formatNumber(value, maximumFractionDigits = 2) {
    return new Intl.NumberFormat("pt-BR", {
        maximumFractionDigits,
    }).format(number(value));
}

export function formatCurrency(value) {
    return new Intl.NumberFormat("pt-BR", {
        style: "currency",
        currency: "BRL",
        maximumFractionDigits: 2,
    }).format(number(value));
}

export function formatPercent(value, decimals = 1, alreadyPercent = false) {
    const normalized = alreadyPercent ? number(value) / 100 : number(value);
    return new Intl.NumberFormat("pt-BR", {
        style: "percent",
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
    }).format(normalized);
}

export function formatDateTime(value) {
    if (!value) {
        return "Aguardando dados";
    }

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return String(value);
    }

    return new Intl.DateTimeFormat("pt-BR", {
        dateStyle: "short",
        timeStyle: "medium",
    }).format(date);
}

export function shortId(value, size = 10) {
    const text = String(value || "—");
    return text.length > size ? `${text.slice(0, size)}…` : text;
}

export function first(source, keys, fallback = "—") {
    if (!source || typeof source !== "object") {
        return fallback;
    }

    for (const key of keys) {
        const value = source[key];
        if (value !== undefined && value !== null && value !== "") {
            return value;
        }
    }
    return fallback;
}

export function statusTone(status) {
    const normalized = String(status || "UNKNOWN").toUpperCase();

    if (["ONLINE", "SUCCESS", "FILLED", "ACCEPTED", "OPEN", "RUNNING"].includes(normalized)) {
        return "success";
    }
    if (["DEGRADED", "PARTIAL", "PENDING", "SUBMITTED", "CREATED", "VALIDATED"].includes(normalized)) {
        return "warning";
    }
    if (["FAILED", "ERROR", "REJECTED", "CANCELLED", "OFFLINE"].includes(normalized)) {
        return "danger";
    }
    return "neutral";
}

export function badge(status) {
    const element = document.createElement("span");
    element.className = `table-badge badge-${statusTone(status)}`;
    element.textContent = String(status || "UNKNOWN").toUpperCase();
    return element;
}

function metricFormatter(card) {
    const key = String(card.key || "").toLowerCase();

    if (["portfolio", "pnl"].includes(key)) {
        return formatCurrency(card.value);
    }
    if (key === "ai_confidence") {
        return formatPercent(card.value, 1);
    }
    return formatNumber(card.value, 2);
}

export function renderCards(container, cards = []) {
    container.replaceChildren();

    for (const card of cards) {
        const article = document.createElement("article");
        const color = String(card.color || "blue").toLowerCase();
        article.className = `metric-card accent-${color}`;

        const label = document.createElement("span");
        label.textContent = card.title || card.key || "Métrica";

        const value = document.createElement("strong");
        value.textContent = metricFormatter(card);

        const detail = document.createElement("small");
        detail.textContent = card.unit || "Snapshot atual";

        article.append(label, value, detail);
        container.append(article);
    }
}

export function renderRows(tbody, rows, columns, emptyText = "Nenhum registro disponível") {
    tbody.replaceChildren();

    if (!rows.length) {
        const tr = document.createElement("tr");
        const td = document.createElement("td");
        td.className = "empty-row";
        td.colSpan = columns.length;
        td.textContent = emptyText;
        tr.append(td);
        tbody.append(tr);
        return;
    }

    for (const row of rows) {
        const tr = document.createElement("tr");

        for (const column of columns) {
            const td = document.createElement("td");
            const value = column.value(row);

            if (value instanceof Node) {
                td.append(value);
            } else {
                td.textContent = value ?? "—";
            }

            if (column.className) {
                td.className = column.className;
            }
            if (column.title) {
                td.title = String(column.title(row) || "");
            }

            tr.append(td);
        }

        tbody.append(tr);
    }
}

export function setSystemStatus(element, status) {
    const normalized = String(status || "UNKNOWN").toUpperCase();
    element.textContent = normalized;
    element.className = "status-badge";

    if (normalized === "ONLINE") {
        element.classList.add("status-online");
    } else if (normalized === "DEGRADED" || normalized === "STARTING") {
        element.classList.add("status-degraded");
    } else {
        element.classList.add("status-offline");
    }
}
