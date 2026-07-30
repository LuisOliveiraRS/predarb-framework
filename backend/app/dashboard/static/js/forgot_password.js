const form = document.querySelector("#recovery-form");
const emailInput = document.querySelector("#recovery-email");
const submitButton = document.querySelector("#recovery-submit");
const message = document.querySelector("#recovery-message");

function setMessage(text, success = false) {
    message.textContent = text;
    message.classList.toggle("success", success);
}

form?.addEventListener("submit", async (event) => {
    event.preventDefault();

    const email = emailInput.value.trim().toLowerCase();

    if (!email) {
        setMessage("Informe seu e-mail.");
        return;
    }

    submitButton.disabled = true;
    setMessage("Solicitando novo link...", true);

    try {
        const response = await fetch(
            "/auth/password/recovery",
            {
                method: "POST",
                credentials: "same-origin",
                cache: "no-store",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ email }),
            }
        );

        const payload = await response.json().catch(
            () => ({})
        );

        if (!response.ok) {
            throw new Error(
                payload.detail
                || "N?o foi poss?vel enviar o link."
            );
        }

        setMessage(
            payload.message
            || "Verifique sua caixa de entrada.",
            true
        );

        emailInput.disabled = true;
    } catch (error) {
        setMessage(
            error instanceof Error
                ? error.message
                : "Falha inesperada."
        );
    } finally {
        submitButton.disabled = false;
    }
});
