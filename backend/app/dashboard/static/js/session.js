function revealDashboard() {
    document.body.classList.remove("auth-pending");
}

function redirectToLogin(loginPath = "/login") {
    const currentPath =
        window.location.pathname
        + window.location.search
        + window.location.hash;

    const target = new URL(
        loginPath,
        window.location.origin
    );

    target.searchParams.set("next", currentPath);
    window.location.replace(target.toString());
}


function requiresMfa(user) {
    return Boolean(
        user
        && user.mfa_required === true
        && user.has_mfa !== true
        && user.aal !== "aal2"
    );
}

function redirectToMfa() {
    const currentPath = (
        window.location.pathname
        + window.location.search
        + window.location.hash
    );

    const target = new URL(
        "/mfa",
        window.location.origin
    );

    target.searchParams.set(
        "next",
        currentPath || "/dashboard"
    );

    window.location.replace(target.toString());
}

async function fetchNoStore(path, options = {}) {
    return fetch(path, {
        credentials: "same-origin",
        cache: "no-store",
        ...options,
    });
}

async function currentSession() {
    return fetchNoStore("/auth/me");
}

async function refreshSession() {
    return fetchNoStore("/auth/refresh", {
        method: "POST",
    });
}

function installAuthStylesheet() {
    if (
        document.querySelector(
            'link[data-predarb-auth-styles]'
        )
    ) {
        return;
    }

    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "/dashboard/static/css/auth.css";
    link.dataset.predarbAuthStyles = "true";
    document.head.appendChild(link);
}

function findTopbarTarget() {
    return (
        document.querySelector(".topbar-actions")
        || document.querySelector(".topbar")
        || document.querySelector("header")
        || document.body
    );
}

function installSessionControls(payload) {
    if (
        document.querySelector(
            "[data-predarb-session-controls]"
        )
    ) {
        return;
    }

    const user = payload?.user || {};

    const container = document.createElement("div");
    container.className = "predarb-user-session";
    container.dataset.predarbSessionControls = "true";

    const identity = document.createElement("div");
    identity.className = "predarb-user-identity";

    const name = document.createElement("span");
    name.className = "predarb-user-name";
    name.textContent =
        user.display_name
        || user.email
        || "Usu?rio PredArb";

    const role = document.createElement("span");
    role.className = "predarb-user-role";
    role.textContent =
        `${user.role || "viewer"} ? ${user.aal || "aal1"}`;

    identity.append(name, role);

    const logout = document.createElement("button");
    logout.type = "button";
    logout.className = "predarb-session-button";
    logout.textContent = "Sair";

    logout.addEventListener("click", async () => {
        logout.disabled = true;

        try {
            await fetchNoStore("/auth/logout", {
                method: "POST",
            });
        } finally {
            window.location.replace("/login");
        }
    });

    container.append(identity, logout);
    findTopbarTarget().appendChild(container);
}

export async function ensureDashboardSession() {
    installAuthStylesheet();

    let configResponse;

    try {
        configResponse = await fetchNoStore(
            "/auth/config"
        );
    } catch {
        revealDashboard();
        return null;
    }

    if (!configResponse.ok) {
        revealDashboard();
        return null;
    }

    const config = await configResponse.json();

    if (
        !config.enabled ||
        !config.dashboard_required
    ) {
        revealDashboard();
        return null;
    }

    let response = await currentSession();

    if (response.status === 401) {
        const refreshed = await refreshSession();

        if (refreshed.ok) {
            response = await currentSession();
        }
    }

    if (!response.ok) {
        redirectToLogin(
            config.login_path || "/login"
        );

        await new Promise(() => {});
    }

    const payload = await response.json();
    const user = payload?.user || {};

    if (requiresMfa(user)) {
        redirectToMfa();
        return null;
    }

    installSessionControls(payload);
    revealDashboard();

    return payload;
}
