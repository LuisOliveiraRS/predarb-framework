(() => {
    "use strict";

    const state = {
        factorId: "",
        qrObjectUrl: "",
        busy: false,
    };

    const startPanel = document.getElementById(
        "mfa-start-panel"
    );

    const setupPanel = document.getElementById(
        "mfa-setup-panel"
    );

    const startButton = document.getElementById(
        "mfa-start-button"
    );

    const verifyForm = document.getElementById(
        "mfa-verify-form"
    );

    const verifyButton = document.getElementById(
        "mfa-verify-button"
    );

    const codeInput = document.getElementById(
        "mfa-code"
    );

    const qrImage = document.getElementById(
        "mfa-qr-image"
    );

    const secretElement = document.getElementById(
        "mfa-secret"
    );

    const copyButton = document.getElementById(
        "mfa-copy-button"
    );

    const messageElement = document.getElementById(
        "mfa-message"
    );

    const enrollmentQr = document.getElementById(
        "mfa-enrollment-qr"
    );

    const enrollmentManual = document.getElementById(
        "mfa-enrollment-manual"
    );

    const enrollmentWarning = document.getElementById(
        "mfa-enrollment-warning"
    );

    function safeNextPath(fallback = "/dashboard") {
        const candidate = new URLSearchParams(
            window.location.search
        ).get("next");

        if (
            !candidate
            || !candidate.startsWith("/")
            || candidate.startsWith("//")
            || candidate.startsWith("/login")
            || candidate.startsWith("/mfa")
        ) {
            return fallback;
        }

        return candidate;
    }

    function setMessage(text, success = false) {
        messageElement.textContent = text || "";

        messageElement.classList.toggle(
            "success",
            Boolean(success)
        );
    }

    function setBusy(value) {
        state.busy = Boolean(value);
        startButton.disabled = state.busy;
        verifyButton.disabled = state.busy;
        codeInput.disabled = state.busy;
        copyButton.disabled = state.busy;
    }

    async function readJson(response) {
        try {
            return await response.json();
        } catch {
            return {};
        }
    }

    function errorMessage(payload, fallback) {
        const detail = String(
            payload?.detail || ""
        ).trim();

        return detail || fallback;
    }

    function redirectToLogin() {
        const next = encodeURIComponent("/mfa");

        window.location.replace(
            `/login?next=${next}`
        );
    }

    function clearQrObjectUrl() {
        if (!state.qrObjectUrl) {
            return;
        }

        URL.revokeObjectURL(state.qrObjectUrl);
        state.qrObjectUrl = "";
    }

    function renderQrCode(value) {
        clearQrObjectUrl();

        let qrCode = String(value || "").trim();

        qrImage.hidden = false;
        qrImage.removeAttribute("src");

        if (/^data:image\//i.test(qrCode)) {
            qrImage.src = qrCode;
            return true;
        }

        if (
            qrCode.includes("%3Csvg")
            || qrCode.includes("%3csvg")
        ) {
            try {
                qrCode = decodeURIComponent(qrCode);
            } catch {
                // Continua com o valor original.
            }
        }

        const svgPosition = qrCode
            .toLowerCase()
            .indexOf("<svg");

        if (svgPosition >= 0) {
            const svg = qrCode.slice(svgPosition);

            qrImage.src = (
                "data:image/svg+xml;charset=utf-8,"
                + encodeURIComponent(svg)
            );

            return true;
        }

        qrImage.hidden = true;
        return false;
    }

    async function loadCurrentSession() {
        const response = await fetch(
            "/auth/me",
            {
                method: "GET",
                credentials: "same-origin",
                cache: "no-store",
                headers: {
                    Accept: "application/json",
                },
            }
        );

        if (response.status === 401) {
            redirectToLogin();
            return;
        }

        const payload = await readJson(response);

        if (!response.ok) {
            throw new Error(
                errorMessage(
                    payload,
                    "Nao foi possivel validar sua sessao."
                )
            );
        }

        const user = payload?.user || {};

        if (
            user.aal === "aal2"
            || user.has_mfa === true
        ) {
            startPanel.hidden = true;
            setupPanel.hidden = true;

            setMessage(
                "Sua sessao ja esta protegida por MFA no nivel AAL2.",
                true
            );

            return;
        }

        const statusResponse = await fetch(
            "/auth/mfa/status",
            {
                method: "GET",
                credentials: "same-origin",
                cache: "no-store",
                headers: {
                    Accept: "application/json",
                },
            }
        );

        if (statusResponse.status === 401) {
            redirectToLogin();
            return;
        }

        const statusPayload = await readJson(
            statusResponse
        );

        if (!statusResponse.ok) {
            throw new Error(
                errorMessage(
                    statusPayload,
                    "Nao foi possivel consultar os fatores MFA."
                )
            );
        }

        const verifiedFactors = Array.isArray(
            statusPayload.verified_factors
        )
            ? statusPayload.verified_factors
            : [];

        if (verifiedFactors.length > 0) {
            state.factorId = String(
                verifiedFactors[0].factor_id || ""
            ).trim();

            if (!state.factorId) {
                throw new Error(
                    "O fator MFA verificado e invalido."
                );
            }

            startPanel.hidden = true;
            setupPanel.hidden = false;

            enrollmentQr.hidden = true;
            enrollmentManual.hidden = true;
            enrollmentWarning.hidden = true;

            verifyButton.textContent = (
                "Confirmar segundo fator"
            );

            setMessage(
                "Informe o codigo atual do seu aplicativo autenticador."
            );

            codeInput.focus();
            return;
        }

        startPanel.hidden = false;
        setupPanel.hidden = true;

        setMessage(
            "Configure um aplicativo autenticador para proteger sua conta."
        );
    }

    async function enrollMfa() {
        if (state.busy) {
            return;
        }

        setBusy(true);
        setMessage(
            "Gerando configuracao segura do autenticador..."
        );

        try {
            const response = await fetch(
                "/auth/mfa/enroll",
                {
                    method: "POST",
                    credentials: "same-origin",
                    cache: "no-store",
                    headers: {
                        Accept: "application/json",
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({
                        friendly_name: (
                            "PredArb Authenticator "
                            + crypto.randomUUID().slice(0, 8)
                        ),
                    }),
                }
            );

            if (response.status === 401) {
                redirectToLogin();
                return;
            }

            const payload = await readJson(response);

            if (!response.ok) {
                throw new Error(
                    errorMessage(
                        payload,
                        "Nao foi possivel iniciar o MFA."
                    )
                );
            }

            state.factorId = String(
                payload.factor_id || ""
            ).trim();

            const secret = String(
                payload.secret || ""
            ).trim();

            if (!state.factorId || !secret) {
                throw new Error(
                    "O Supabase retornou dados MFA incompletos."
                );
            }

            enrollmentQr.hidden = false;
            enrollmentManual.hidden = false;
            enrollmentWarning.hidden = false;

            verifyButton.textContent = (
                "Confirmar e ativar MFA"
            );

            const qrRendered = renderQrCode(
                payload.qr_code
            );

            secretElement.textContent = secret;
            startPanel.hidden = true;
            setupPanel.hidden = false;

            if (qrRendered) {
                setMessage(
                    "Escaneie o QR Code e informe o codigo gerado."
                );
            } else {
                setMessage(
                    "O QR Code nao p?de ser exibido. "
                    + "Use a chave manual no autenticador."
                );
            }

            codeInput.focus();
        } catch (error) {
            setMessage(
                error instanceof Error
                    ? error.message
                    : "Falha ao iniciar o MFA."
            );
        } finally {
            setBusy(false);
        }
    }

    async function createChallenge() {
        const response = await fetch(
            "/auth/mfa/challenge",
            {
                method: "POST",
                credentials: "same-origin",
                cache: "no-store",
                headers: {
                    Accept: "application/json",
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    factor_id: state.factorId,
                }),
            }
        );

        if (response.status === 401) {
            redirectToLogin();
            return null;
        }

        const payload = await readJson(response);

        if (!response.ok) {
            throw new Error(
                errorMessage(
                    payload,
                    "Nao foi possivel criar o desafio MFA."
                )
            );
        }

        const challengeId = String(
            payload.challenge_id || ""
        ).trim();

        if (!challengeId) {
            throw new Error(
                "Identificador do desafio MFA ausente."
            );
        }

        return challengeId;
    }

    async function verifyMfa(event) {
        event.preventDefault();

        if (state.busy) {
            return;
        }

        const code = String(
            codeInput.value || ""
        ).replace(/\D/g, "");

        codeInput.value = code;

        if (code.length !== 6) {
            setMessage(
                "Informe o codigo de seis digitos."
            );

            codeInput.focus();
            return;
        }

        if (!state.factorId) {
            setMessage(
                "A configuracao MFA expirou. Inicie novamente."
            );
            return;
        }

        setBusy(true);
        setMessage("Validando o codigo TOTP...");

        try {
            const challengeId = await createChallenge();

            if (!challengeId) {
                return;
            }

            const response = await fetch(
                "/auth/mfa/verify",
                {
                    method: "POST",
                    credentials: "same-origin",
                    cache: "no-store",
                    headers: {
                        Accept: "application/json",
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({
                        factor_id: state.factorId,
                        challenge_id: challengeId,
                        code,
                    }),
                }
            );

            if (response.status === 401) {
                redirectToLogin();
                return;
            }

            const payload = await readJson(response);

            if (!response.ok) {
                throw new Error(
                    errorMessage(
                        payload,
                        "O codigo informado foi recusado."
                    )
                );
            }

            const user = payload?.user || {};

            if (
                payload.verified !== true
                || user.aal !== "aal2"
            ) {
                throw new Error(
                    "A sessao nao foi elevada para AAL2."
                );
            }

            state.factorId = "";
            codeInput.value = "";
            secretElement.textContent = "";
            clearQrObjectUrl();

            setupPanel.hidden = true;

            setMessage(
                "MFA ativado. Sessao elevada para AAL2.",
                true
            );

            window.setTimeout(() => {
                window.location.assign(
                    safeNextPath("/dashboard")
                );
            }, 900);
        } catch (error) {
            setMessage(
                error instanceof Error
                    ? error.message
                    : "Falha ao confirmar o MFA."
            );

            codeInput.select();
        } finally {
            setBusy(false);
        }
    }

    async function copySecret() {
        const secret = String(
            secretElement.textContent || ""
        ).trim();

        if (!secret) {
            return;
        }

        try {
            await navigator.clipboard.writeText(secret);

            setMessage(
                "Chave temporaria copiada.",
                true
            );
        } catch {
            setMessage(
                "Nao foi possivel copiar automaticamente."
            );
        }
    }

    codeInput.addEventListener("input", () => {
        codeInput.value = codeInput.value
            .replace(/\D/g, "")
            .slice(0, 6);
    });

    startButton.addEventListener(
        "click",
        enrollMfa
    );

    verifyForm.addEventListener(
        "submit",
        verifyMfa
    );

    copyButton.addEventListener(
        "click",
        copySecret
    );

    window.addEventListener(
        "beforeunload",
        clearQrObjectUrl
    );

    loadCurrentSession().catch((error) => {
        setMessage(
            error instanceof Error
                ? error.message
                : "Nao foi possivel carregar a sessao."
        );
    });
})();
