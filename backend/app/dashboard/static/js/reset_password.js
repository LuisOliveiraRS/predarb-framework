const form = document.querySelector("#reset-form");
const passwordInput = document.querySelector("#new-password");
const confirmInput = document.querySelector("#confirm-password");
const submitButton = document.querySelector("#reset-submit");
const message = document.querySelector("#reset-message");

const fragment = new URLSearchParams(
    window.location.hash.replace(/^#/, "")
);

const query = new URLSearchParams(
    window.location.search
);

const recoveryError =
    fragment.get("error_description")
    || query.get("error_description");

const recoveryErrorCode =
    fragment.get("error_code")
    || query.get("error_code");

const recoveryType = fragment.get("type");
const accessToken = fragment.get("access_token");

window.history.replaceState(
    null,
    "",
    window.location.pathname
);

function setMessage(text, success = false) {
    message.textContent = text;
    message.classList.toggle("success", success);
}

function disableForm() {
    passwordInput.disabled = true;
    confirmInput.disabled = true;
    submitButton.disabled = true;
}

if (recoveryError || recoveryErrorCode) {
    setMessage(
        "O link ? inv?lido ou expirou. Solicite um novo link."
    );

    disableForm();
} else if (
    recoveryType !== "recovery"
    || !accessToken
) {
    setMessage(
        "Token de recupera??o ausente. Solicite um novo link."
    );

    disableForm();
}

form?.addEventListener("submit", async (event) => {
    event.preventDefault();

    const newPassword = passwordInput.value;
    const confirmPassword = confirmInput.value;

    if (!accessToken) {
        setMessage("Token de recupera??o ausente.");
        return;
    }

    if (newPassword.length < 12) {
        setMessage(
            "A senha deve ter no m?nimo 12 caracteres."
        );
        return;
    }

    if (newPassword !== confirmPassword) {
        setMessage("As senhas n?o coincidem.");
        return;
    }

    submitButton.disabled = true;
    setMessage("Atualizando sua senha...", true);

    try {
        const response = await fetch(
            "/auth/password/update",
            {
                method: "POST",
                credentials: "same-origin",
                cache: "no-store",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    access_token: accessToken,
                    new_password: newPassword,
                    confirm_password: confirmPassword,
                }),
            }
        );

        const payload = await response.json().catch(
            () => ({})
        );

        if (!response.ok) {
            throw new Error(
                payload.detail
                || "N?o foi poss?vel atualizar a senha."
            );
        }

        setMessage("Senha atualizada com sucesso.", true);

        window.setTimeout(() => {
            window.location.replace(
                "/login?password_reset=success"
            );
        }, 900);
    } catch (error) {
        setMessage(
            error instanceof Error
                ? error.message
                : "Falha inesperada."
        );

        submitButton.disabled = false;
    }
});
