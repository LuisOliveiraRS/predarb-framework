const WS_UNAUTHORIZED = 4401;
const WS_FORBIDDEN = 4403;

export class RouterSocket {
    constructor({
        path = "/ws/router",
        loginPath = "/login",
        refreshPath = "/auth/refresh",
        onData = () => {},
        onStatus = () => {},
    } = {}) {
        this.path = path;
        this.loginPath = loginPath;
        this.refreshPath = refreshPath;
        this.onData = onData;
        this.onStatus = onStatus;

        this.socket = null;
        this.retry = 0;
        this.closedByClient = false;
        this.reconnectTimer = null;
        this.heartbeatTimer = null;
        this.refreshInProgress = false;
    }

    url() {
        const protocol =
            window.location.protocol === "https:"
                ? "wss:"
                : "ws:";

        return (
            `${protocol}//${window.location.host}`
            + this.path
        );
    }

    connect() {
        this.closedByClient = false;
        this.onStatus("connecting");

        try {
            this.socket = new WebSocket(this.url());
        } catch (error) {
            this.onStatus("error", error);
            this.scheduleReconnect();
            return;
        }

        this.socket.addEventListener("open", () => {
            this.retry = 0;
            this.onStatus("connected");
            this.startHeartbeat();
        });

        this.socket.addEventListener(
            "message",
            (event) => {
                try {
                    this.onData(
                        JSON.parse(event.data)
                    );
                } catch (error) {
                    this.onStatus(
                        "invalid-message",
                        error
                    );
                }
            }
        );

        this.socket.addEventListener(
            "error",
            (event) => {
                this.onStatus("error", event);
            }
        );

        this.socket.addEventListener(
            "close",
            async (event) => {
                await this.handleClose(event);
            }
        );
    }

    async handleClose(event) {
        this.stopHeartbeat();
        this.socket = null;

        if (this.closedByClient) {
            this.onStatus("disconnected");
            return;
        }

        if (event.code === WS_UNAUTHORIZED) {
            this.onStatus("auth-refreshing");

            const refreshed =
                await this.refreshAuthentication();

            if (refreshed) {
                this.retry = 0;
                this.onStatus("auth-restored");
                this.scheduleReconnect(250);
                return;
            }

            this.onStatus("auth-required");
            this.redirectToLogin();
            return;
        }

        if (event.code === WS_FORBIDDEN) {
            this.onStatus("auth-required");
            this.redirectToLogin();
            return;
        }

        this.onStatus("disconnected");
        this.scheduleReconnect();
    }

    async refreshAuthentication() {
        if (this.refreshInProgress) {
            return false;
        }

        this.refreshInProgress = true;

        try {
            const response = await fetch(
                this.refreshPath,
                {
                    method: "POST",
                    credentials: "same-origin",
                    cache: "no-store",
                }
            );

            return response.ok;
        } catch {
            return false;
        } finally {
            this.refreshInProgress = false;
        }
    }

    redirectToLogin() {
        this.closedByClient = true;

        const currentPath =
            window.location.pathname
            + window.location.search
            + window.location.hash;

        const target = new URL(
            this.loginPath,
            window.location.origin
        );

        target.searchParams.set(
            "next",
            currentPath
        );

        window.location.replace(
            target.toString()
        );
    }

    startHeartbeat() {
        this.stopHeartbeat();

        this.heartbeatTimer = window.setInterval(
            () => {
                if (
                    this.socket?.readyState
                    === WebSocket.OPEN
                ) {
                    this.socket.send("ping");
                }
            },
            20000
        );
    }

    stopHeartbeat() {
        if (this.heartbeatTimer) {
            window.clearInterval(
                this.heartbeatTimer
            );

            this.heartbeatTimer = null;
        }
    }

    scheduleReconnect(
        explicitDelay = null
    ) {
        if (
            this.closedByClient
            || this.reconnectTimer
        ) {
            return;
        }

        const delay =
            explicitDelay
            ?? Math.min(
                15000,
                1000 * (2 ** this.retry)
            );

        if (explicitDelay === null) {
            this.retry += 1;
        }

        this.onStatus(
            "reconnecting",
            { delay }
        );

        this.reconnectTimer =
            window.setTimeout(
                () => {
                    this.reconnectTimer = null;
                    this.connect();
                },
                delay
            );
    }

    close() {
        this.closedByClient = true;
        this.stopHeartbeat();

        if (this.reconnectTimer) {
            window.clearTimeout(
                this.reconnectTimer
            );

            this.reconnectTimer = null;
        }

        this.socket?.close(
            1000,
            "Dashboard encerrado"
        );
    }
}
