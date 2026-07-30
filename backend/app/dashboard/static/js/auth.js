const passwordResetCompleted = (
    new URLSearchParams(window.location.search)
    .get("password_reset") === "success"
);

const form = document.querySelector("#login-form");
const emailInput = document.querySelector("#login-email");
const passwordInput = document.querySelector("#login-password");
const submitButton = document.querySelector("#login-submit");
const message = document.querySelector("#login-message");
const togglePassword = document.querySelector("#toggle-password");

function safeNextPath(fallback = "/dashboard") {
    const value = new URLSearchParams(
        window.location.search
    ).get("next");

    if (
        value &&
        value.startsWith("/") &&
        !value.startsWith("//") &&
        !value.includes("://")
    ) {
        return value;
    }

    return fallback;
}

function setMessage(text, success = false) {
    message.textContent = text;
    message.classList.toggle("success", success);
}


function requiresMfa(user) {
    return Boolean(
        user
        && user.mfa_required === true
        && user.has_mfa !== true
        && user.aal !== "aal2"
    );
}

function mfaRedirectPath(nextPath) {
    const destination = String(
        nextPath || "/dashboard"
    );

    return (
        "/mfa?next="
        + encodeURIComponent(destination)
    );
}

async function readJson(response) {
    try {
        return await response.json();
    } catch {
        return {};
    }
}

async function loadConfig() {
    const response = await fetch("/auth/config", {
        credentials: "same-origin",
        cache: "no-store",
    });

    if (!response.ok) {
        throw new Error(
            "N?o foi poss?vel carregar a autentica??o."
        );
    }

    return response.json();
}

async function checkExistingSession(config) {
    if (
        !config.enabled ||
        !config.dashboard_required
    ) {
        window.location.replace(
            config.after_login_path || "/dashboard"
        );
        return true;
    }

    const response = await fetch("/auth/me", {
        credentials: "same-origin",
        cache: "no-store",
    });

    if (response.ok) {
        const payload = await readJson(response);

        const nextPath = safeNextPath(
            config.after_login_path || "/dashboard"
        );

        if (requiresMfa(payload?.user)) {
            window.location.replace(
                mfaRedirectPath(nextPath)
            );

            return true;
        }

        window.location.replace(nextPath);
        return true;
    }

    return false;
}

togglePassword?.addEventListener("click", () => {
    const showing =
        passwordInput.type === "text";

    passwordInput.type = showing
        ? "password"
        : "text";

    togglePassword.textContent = showing
        ? "Mostrar"
        : "Ocultar";

    togglePassword.setAttribute(
        "aria-label",
        showing ? "Mostrar senha" : "Ocultar senha"
    );
});

form?.addEventListener("submit", async (event) => {
    event.preventDefault();

    const email = emailInput.value.trim().toLowerCase();
    const password = passwordInput.value;

    if (!email || !password) {
        setMessage("Informe o e-mail e a senha.");
        return;
    }

    submitButton.disabled = true;
    setMessage("Autenticando...", true);

    try {
        const response = await fetch("/auth/login", {
            method: "POST",
            credentials: "same-origin",
            cache: "no-store",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                email,
                password,
            }),
        });

        const payload = await readJson(response);

        if (!response.ok) {
            throw new Error(
                payload.detail ||
                "N?o foi poss?vel realizar o login."
            );
        }

        setMessage("Acesso autorizado.", true);

        const nextPath = safeNextPath("/dashboard");

        if (requiresMfa(payload?.user)) {
            window.location.replace(
                mfaRedirectPath(nextPath)
            );

            return;
        }

        window.location.replace(nextPath);
    } catch (error) {
        setMessage(
            error instanceof Error
                ? error.message
                : "Falha inesperada na autentica??o."
        );
    } finally {
        submitButton.disabled = false;
    }
});

(async () => {
    if (passwordResetCompleted) {
        setMessage(
            "Senha atualizada. Entre com a nova senha.",
            true
        );
    }

    try {
        const config = await loadConfig();
        await checkExistingSession(config);
    } catch {
        setMessage(
            "O servi?o de autentica??o est? indispon?vel."
        );
    }
})();
