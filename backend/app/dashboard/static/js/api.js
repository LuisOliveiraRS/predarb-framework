const DEFAULT_TIMEOUT_MS = 8000;

function apiBase() {
    return window.PREDARB_DASHBOARD?.apiBase || "/dashboard/api";
}

export async function fetchJson(path, options = {}) {
    const controller = new AbortController();
    const timeout = window.setTimeout(
        () => controller.abort(),
        options.timeout ?? DEFAULT_TIMEOUT_MS,
    );

    try {
        const response = await fetch(`${apiBase()}${path}`, {
            method: options.method || "GET",
            headers: {
                Accept: "application/json",
                ...(options.headers || {}),
            },
            cache: "no-store",
            credentials: "same-origin",
            signal: controller.signal,
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        return await response.json();
    } catch (error) {
        if (error?.name === "AbortError") {
            throw new Error("Tempo limite excedido ao consultar o Dashboard.");
        }
        throw error;
    } finally {
        window.clearTimeout(timeout);
    }
}

export function loadSnapshot(refresh = true) {
    return fetchJson(`/snapshot?refresh=${refresh ? "true" : "false"}`);
}

export function loadEvents(limit = 50) {
    return fetchJson(`/events?limit=${encodeURIComponent(limit)}`);
}

export function loadHealth() {
    return fetchJson("/health");
}
