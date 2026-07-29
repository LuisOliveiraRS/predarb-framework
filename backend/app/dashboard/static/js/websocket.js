export class RouterSocket {
    constructor({
        path = "/ws/router",
        onData = () => {},
        onStatus = () => {},
    } = {}) {
        this.path = path;
        this.onData = onData;
        this.onStatus = onStatus;
        this.socket = null;
        this.retry = 0;
        this.closedByClient = false;
        this.reconnectTimer = null;
        this.heartbeatTimer = null;
    }

    url() {
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        return `${protocol}//${window.location.host}${this.path}`;
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

        this.socket.addEventListener("message", (event) => {
            try {
                this.onData(JSON.parse(event.data));
            } catch (error) {
                this.onStatus("invalid-message", error);
            }
        });

        this.socket.addEventListener("error", (event) => {
            this.onStatus("error", event);
        });

        this.socket.addEventListener("close", () => {
            this.stopHeartbeat();
            this.onStatus("disconnected");

            if (!this.closedByClient) {
                this.scheduleReconnect();
            }
        });
    }

    startHeartbeat() {
        this.stopHeartbeat();
        this.heartbeatTimer = window.setInterval(() => {
            if (this.socket?.readyState === WebSocket.OPEN) {
                this.socket.send("ping");
            }
        }, 20000);
    }

    stopHeartbeat() {
        if (this.heartbeatTimer) {
            window.clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
    }

    scheduleReconnect() {
        if (this.closedByClient || this.reconnectTimer) {
            return;
        }

        const delay = Math.min(15000, 1000 * (2 ** this.retry));
        this.retry += 1;
        this.onStatus("reconnecting", { delay });

        this.reconnectTimer = window.setTimeout(() => {
            this.reconnectTimer = null;
            this.connect();
        }, delay);
    }

    close() {
        this.closedByClient = true;
        this.stopHeartbeat();

        if (this.reconnectTimer) {
            window.clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }

        this.socket?.close(1000, "Dashboard encerrado");
    }
}
