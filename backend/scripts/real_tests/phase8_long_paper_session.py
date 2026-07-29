from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import httpx


BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = BACKEND_ROOT / "real_test_reports"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


def number(
    value: Any,
    default: float = 0.0,
) -> float:
    if value is None or isinstance(value, bool):
        return float(default)

    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def integer(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def get_path(
    payload: Mapping[str, Any] | None,
    *path: str,
    default: Any = None,
) -> Any:
    current: Any = payload

    for key in path:
        if not isinstance(current, Mapping):
            return default

        current = current.get(key)

    return default if current is None else current


def truthy_safety_violations(
    payload: Any,
    *,
    path: str = "root",
) -> list[str]:
    violations: list[str] = []

    if isinstance(payload, Mapping):
        for key, value in payload.items():
            current_path = f"{path}.{key}"

            if key in {
                "execution_authorized",
                "live_execution",
            } and value is True:
                violations.append(
                    f"{current_path}=true"
                )

            if (
                key == "execution_worker"
                and value is True
            ):
                violations.append(
                    f"{current_path}=true"
                )

            violations.extend(
                truthy_safety_violations(
                    value,
                    path=current_path,
                )
            )

    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            violations.extend(
                truthy_safety_violations(
                    value,
                    path=f"{path}[{index}]",
                )
            )

    return violations


class Phase8Monitor:
    def __init__(
        self,
        *,
        client: httpx.Client,
        duration_seconds: float,
        poll_seconds: float,
        reset: bool,
        reset_confirmation: str | None,
        leave_running: bool,
        label: str,
    ) -> None:
        self.client = client
        self.duration_seconds = duration_seconds
        self.poll_seconds = poll_seconds
        self.reset = reset
        self.reset_confirmation = reset_confirmation
        self.leave_running = leave_running
        self.label = label

        stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
        safe_label = "".join(
            char
            if char.isalnum() or char in {"-", "_"}
            else "_"
            for char in label
        ).strip("_")

        suffix = (
            f"_{safe_label}"
            if safe_label
            else ""
        )

        self.report_path = (
            REPORT_DIR
            / f"phase8_long_session_{stamp}{suffix}.json"
        )

        self.samples_path = (
            REPORT_DIR
            / f"phase8_long_session_{stamp}{suffix}.csv"
        )

        self.events_path = (
            REPORT_DIR
            / f"phase8_long_session_{stamp}{suffix}.jsonl"
        )

        self.started_at = utc_now()
        self.samples: list[dict[str, Any]] = []
        self.endpoint_errors: list[dict[str, Any]] = []
        self.safety_violations: list[str] = []
        self.notes: list[str] = []
        self.started_runtime = False
        self.interrupted = False

        self.initial: dict[str, Any] = {}
        self.final: dict[str, Any] = {}

    def request_json(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> tuple[dict[str, Any], float]:
        started = time.perf_counter()

        response = self.client.request(
            method,
            path,
            **kwargs,
        )

        elapsed_ms = round(
            (time.perf_counter() - started) * 1000,
            3,
        )

        response.raise_for_status()

        payload = response.json()

        if not isinstance(payload, dict):
            payload = {
                "value": payload,
            }

        violations = truthy_safety_violations(
            payload,
            path=path,
        )

        self.safety_violations.extend(
            item
            for item in violations
            if item not in self.safety_violations
        )

        return payload, elapsed_ms

    def preflight(self) -> dict[str, Any]:
        health, health_ms = self.request_json(
            "GET",
            "/health",
        )

        if health.get("status") != "healthy":
            raise RuntimeError(
                f"Health inválido: {health}"
            )

        lifecycle = health.get("lifecycle") or {}

        if lifecycle.get("execution_worker") is True:
            raise RuntimeError(
                "O worker de execução live está ativo."
            )

        ai = health.get("ai") or {}

        if ai.get("execution_authorized") is True:
            raise RuntimeError(
                "A IA está autorizada a executar ordens."
            )

        session = health.get("paper_session") or {}

        if session.get("enabled") is not True:
            raise RuntimeError(
                "A sessão Paper está desabilitada."
            )

        if session.get("auto_start") is True:
            raise RuntimeError(
                "PAPER_SESSION_AUTO_START está ativo."
            )

        return {
            "health": health,
            "health_latency_ms": health_ms,
        }

    def reset_state(self) -> None:
        if not self.reset:
            return

        if (
            self.reset_confirmation
            != "RESET-PHASE8-DATA"
        ):
            raise ValueError(
                "Para resetar, informe "
                "--confirm-reset RESET-PHASE8-DATA."
            )

        account, _ = self.request_json(
            "POST",
            "/paper/reset",
            params={
                "confirm": "RESET-PAPER",
                "persist": "true",
            },
        )

        session, _ = self.request_json(
            "POST",
            "/paper/session/reset-report",
            params={
                "confirm":
                    "RESET-PAPER-SESSION-REPORT",
            },
        )

        self.notes.append(
            "Conta e relatório da Fase 8 resetados."
        )

        self.initial["reset"] = {
            "account": account,
            "session": session,
        }

    def capture_bundle(self) -> dict[str, Any]:
        endpoint_specs = {
            "session_status": (
                "GET",
                "/paper/session/status",
                {},
            ),
            "session_report": (
                "GET",
                "/paper/session/report",
                {},
            ),
            "account": (
                "GET",
                "/paper/account",
                {
                    "params": {
                        "include_trades": "false",
                    }
                },
            ),
            "equity": (
                "GET",
                "/paper/equity",
                {
                    "params": {
                        "limit": 2000,
                    }
                },
            ),
            "statistics": (
                "GET",
                "/paper/statistics",
                {},
            ),
            "risk": (
                "GET",
                "/paper/risk/status",
                {},
            ),
        }

        bundle: dict[str, Any] = {
            "captured_at": iso_now(),
            "latency_ms": {},
        }

        for name, (
            method,
            path,
            kwargs,
        ) in endpoint_specs.items():
            try:
                payload, elapsed_ms = self.request_json(
                    method,
                    path,
                    **kwargs,
                )
                bundle[name] = payload
                bundle["latency_ms"][name] = elapsed_ms
            except Exception as exc:
                error = {
                    "captured_at": bundle["captured_at"],
                    "endpoint": path,
                    "error": str(exc),
                }

                self.endpoint_errors.append(error)
                bundle[name] = {
                    "error": str(exc),
                }

        return bundle

    @staticmethod
    def compact_sample(
        bundle: Mapping[str, Any],
    ) -> dict[str, Any]:
        status = bundle.get("session_status") or {}
        report = bundle.get("session_report") or {}
        account = bundle.get("account") or {}
        equity = bundle.get("equity") or {}
        statistics = bundle.get("statistics") or {}
        risk = bundle.get("risk") or {}
        analytics = equity.get("analytics") or {}
        session = status.get("session") or report

        return {
            "captured_at": bundle.get(
                "captured_at"
            ),
            "runtime_status": status.get("status"),
            "runtime_running": status.get("running"),
            "total_cycles": integer(
                session.get("total_cycles")
            ),
            "successful_cycles": integer(
                session.get("successful_cycles")
            ),
            "failed_cycles": integer(
                session.get("failed_cycles")
            ),
            "no_signal_cycles": integer(
                session.get("no_signal_cycles")
            ),
            "risk_stopped_cycles": integer(
                session.get("risk_stopped_cycles")
            ),
            "last_cycle_status": get_path(
                session,
                "last_cycle",
                "status",
            ),
            "equity": number(
                account.get("equity")
            ),
            "total_pnl": number(
                account.get("total_pnl")
            ),
            "realized_pnl": number(
                account.get("realized_pnl")
            ),
            "unrealized_pnl": number(
                account.get("unrealized_pnl")
            ),
            "return_rate": number(
                account.get("return_rate")
            ),
            "trade_count": integer(
                account.get(
                    "trade_count",
                    statistics.get("trade_count", 0),
                )
            ),
            "open_positions": integer(
                account.get(
                    "open_positions",
                    statistics.get("open_positions", 0),
                )
            ),
            "max_drawdown": number(
                analytics.get("max_drawdown")
            ),
            "max_drawdown_rate": number(
                analytics.get("max_drawdown_rate")
            ),
            "risk_approved": get_path(
                risk,
                "session",
                "approved",
                default=get_path(
                    risk,
                    "decision",
                    "approved",
                ),
            ),
            "latency_session_ms": number(
                get_path(
                    bundle,
                    "latency_ms",
                    "session_status",
                )
            ),
            "latency_account_ms": number(
                get_path(
                    bundle,
                    "latency_ms",
                    "account",
                )
            ),
        }

    def append_event(
        self,
        bundle: Mapping[str, Any],
    ) -> None:
        REPORT_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        with self.events_path.open(
            "a",
            encoding="utf-8",
        ) as file:
            file.write(
                json.dumps(
                    bundle,
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            file.write("\n")

    def start_session(self) -> dict[str, Any]:
        status, _ = self.request_json(
            "GET",
            "/paper/session/status",
        )

        if status.get("running") is True:
            self.notes.append(
                "A sessão já estava em execução."
            )
            return status

        started, _ = self.request_json(
            "POST",
            "/paper/session/start",
            params={
                "confirm": "START-PAPER-SESSION",
            },
        )

        if started.get("running") is not True:
            raise RuntimeError(
                f"A sessão não iniciou: {started}"
            )

        self.started_runtime = True
        self.notes.append(
            "Sessão iniciada explicitamente "
            "pelo monitor da Fase 8."
        )

        return started

    def stop_session(self) -> dict[str, Any]:
        stopped, _ = self.request_json(
            "POST",
            "/paper/session/stop",
        )

        if stopped.get("running") is True:
            raise RuntimeError(
                "A sessão permaneceu ativa após stop."
            )

        return stopped

    def run_monitoring(self) -> None:
        deadline = (
            time.monotonic()
            + self.duration_seconds
        )

        next_capture = time.monotonic()

        while time.monotonic() < deadline:
            now = time.monotonic()

            if now < next_capture:
                time.sleep(
                    min(
                        0.5,
                        next_capture - now,
                    )
                )
                continue

            bundle = self.capture_bundle()
            sample = self.compact_sample(bundle)

            self.samples.append(sample)
            self.append_event(bundle)

            print(
                "[AMOSTRA]"
                f" ciclos={sample['total_cycles']}"
                f" sucesso={sample['successful_cycles']}"
                f" sem_sinal={sample['no_signal_cycles']}"
                f" falhas={sample['failed_cycles']}"
                f" equity={sample['equity']:.2f}"
                f" trades={sample['trade_count']}"
                f" runtime={sample['runtime_status']}"
            )

            if (
                sample["risk_stopped_cycles"] > 0
                and sample["runtime_running"] is False
            ):
                self.notes.append(
                    "A sessão foi encerrada pelo "
                    "guardião de risco."
                )
                break

            next_capture = (
                time.monotonic()
                + self.poll_seconds
            )

    @staticmethod
    def delta(
        final: Mapping[str, Any],
        initial: Mapping[str, Any],
        key: str,
    ) -> float:
        return number(
            final.get(key)
        ) - number(
            initial.get(key)
        )

    def build_result(self) -> dict[str, Any]:
        initial_sample = (
            self.samples[0]
            if self.samples
            else {}
        )

        final_sample = (
            self.samples[-1]
            if self.samples
            else {}
        )

        finished_at = utc_now()
        actual_duration = (
            finished_at - self.started_at
        ).total_seconds()

        cycles_delta = integer(
            final_sample.get("total_cycles")
        ) - integer(
            initial_sample.get("total_cycles")
        )

        successful_delta = integer(
            final_sample.get("successful_cycles")
        ) - integer(
            initial_sample.get("successful_cycles")
        )

        failed_delta = integer(
            final_sample.get("failed_cycles")
        ) - integer(
            initial_sample.get("failed_cycles")
        )

        no_signal_delta = integer(
            final_sample.get("no_signal_cycles")
        ) - integer(
            initial_sample.get("no_signal_cycles")
        )

        risk_stopped_delta = integer(
            final_sample.get("risk_stopped_cycles")
        ) - integer(
            initial_sample.get("risk_stopped_cycles")
        )

        equity_delta = self.delta(
            final_sample,
            initial_sample,
            "equity",
        )

        trade_delta = integer(
            final_sample.get("trade_count")
        ) - integer(
            initial_sample.get("trade_count")
        )

        start_equity = number(
            initial_sample.get("equity")
        )

        return_rate = (
            equity_delta / start_equity
            if start_equity
            else 0.0
        )

        cycles_per_hour = (
            cycles_delta / actual_duration * 3600
            if actual_duration > 0
            else 0.0
        )

        max_drawdown = max(
            (
                number(
                    item.get("max_drawdown")
                )
                for item in self.samples
            ),
            default=0.0,
        )

        max_drawdown_rate = max(
            (
                number(
                    item.get("max_drawdown_rate")
                )
                for item in self.samples
            ),
            default=0.0,
        )

        checks = {
            "samples_collected": bool(
                self.samples
            ),
            "cycles_progressed": (
                cycles_delta > 0
            ),
            "endpoint_errors_zero": (
                len(self.endpoint_errors) == 0
            ),
            "safety_violations_zero": (
                len(self.safety_violations) == 0
            ),
            "live_execution_blocked": (
                len(self.safety_violations) == 0
            ),
        }

        passed = all(checks.values())

        return {
            "test": (
                "PredArb Phase 8 - "
                "Long Paper Session"
            ),
            "label": self.label,
            "started_at": (
                self.started_at.isoformat()
            ),
            "finished_at": (
                finished_at.isoformat()
            ),
            "requested_duration_seconds": (
                self.duration_seconds
            ),
            "actual_duration_seconds": round(
                actual_duration,
                3,
            ),
            "poll_seconds": self.poll_seconds,
            "interrupted": self.interrupted,
            "started_runtime": self.started_runtime,
            "leave_running": self.leave_running,
            "summary": {
                "status": (
                    "PASS"
                    if passed
                    else "FAIL"
                ),
                "checks": checks,
                "samples": len(self.samples),
                "endpoint_errors": len(
                    self.endpoint_errors
                ),
                "safety_violations": len(
                    self.safety_violations
                ),
            },
            "performance": {
                "cycles_delta": cycles_delta,
                "successful_cycles_delta":
                    successful_delta,
                "failed_cycles_delta":
                    failed_delta,
                "no_signal_cycles_delta":
                    no_signal_delta,
                "risk_stopped_cycles_delta":
                    risk_stopped_delta,
                "cycles_per_hour": round(
                    cycles_per_hour,
                    4,
                ),
                "trade_count_delta": trade_delta,
                "start_equity": round(
                    start_equity,
                    8,
                ),
                "end_equity": round(
                    number(
                        final_sample.get("equity")
                    ),
                    8,
                ),
                "equity_delta": round(
                    equity_delta,
                    8,
                ),
                "session_return_rate": round(
                    return_rate,
                    8,
                ),
                "max_drawdown": round(
                    max_drawdown,
                    8,
                ),
                "max_drawdown_rate": round(
                    max_drawdown_rate,
                    8,
                ),
            },
            "initial_sample": initial_sample,
            "final_sample": final_sample,
            "endpoint_errors": (
                self.endpoint_errors
            ),
            "safety_violations": (
                self.safety_violations
            ),
            "notes": self.notes,
            "artifacts": {
                "report_json": str(
                    self.report_path
                ),
                "samples_csv": str(
                    self.samples_path
                ),
                "events_jsonl": str(
                    self.events_path
                ),
            },
            "execution_authorized": False,
            "live_execution": False,
        }

    def save_samples_csv(self) -> None:
        REPORT_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        if not self.samples:
            self.samples_path.write_text(
                "",
                encoding="utf-8",
            )
            return

        fieldnames = list(
            self.samples[0].keys()
        )

        with self.samples_path.open(
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=fieldnames,
            )
            writer.writeheader()
            writer.writerows(self.samples)

    def save_result(
        self,
        result: Mapping[str, Any],
    ) -> None:
        REPORT_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.report_path.write_text(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

    def execute(self) -> int:
        print(
            "PredArb - Fase 8 / "
            "Sessão Paper prolongada"
        )
        print(
            f"Duração: "
            f"{self.duration_seconds:.0f} segundos"
        )
        print(
            f"Coleta: a cada "
            f"{self.poll_seconds:.0f} segundos"
        )
        print()

        try:
            self.initial[
                "preflight"
            ] = self.preflight()

            print(
                "[PASS] Servidor e guardas "
                "operacionais"
            )

            self.reset_state()

            self.initial[
                "before_start"
            ] = self.capture_bundle()

            self.start_session()

            print(
                "[PASS] Sessão Paper iniciada "
                "com confirmação explícita"
            )

            self.run_monitoring()

        except KeyboardInterrupt:
            self.interrupted = True
            self.notes.append(
                "Monitor interrompido pelo usuário."
            )
            print()
            print(
                "[AVISO] Interrupção solicitada."
            )

        except Exception as exc:
            self.endpoint_errors.append(
                {
                    "captured_at": iso_now(),
                    "stage": "execute",
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                }
            )
            print(
                f"[FAIL] Monitoramento: {exc}"
            )

        finally:
            if (
                self.started_runtime
                and not self.leave_running
            ):
                try:
                    self.final[
                        "stop"
                    ] = self.stop_session()

                    print(
                        "[PASS] Sessão Paper "
                        "encerrada"
                    )

                except Exception as exc:
                    self.endpoint_errors.append(
                        {
                            "captured_at": iso_now(),
                            "stage": "stop",
                            "error": str(exc),
                            "traceback":
                                traceback.format_exc(),
                        }
                    )

                    print(
                        "[FAIL] Não foi possível "
                        f"encerrar a sessão: {exc}"
                    )

            try:
                self.final[
                    "snapshot"
                ] = self.capture_bundle()

                final_sample = self.compact_sample(
                    self.final["snapshot"]
                )

                if (
                    not self.samples
                    or final_sample
                    != self.samples[-1]
                ):
                    self.samples.append(
                        final_sample
                    )
                    self.append_event(
                        self.final["snapshot"]
                    )

            except Exception as exc:
                self.endpoint_errors.append(
                    {
                        "captured_at": iso_now(),
                        "stage": "final_snapshot",
                        "error": str(exc),
                    }
                )

        result = self.build_result()
        self.save_samples_csv()
        self.save_result(result)

        summary = result["summary"]
        performance = result["performance"]

        print()
        print("=" * 68)
        print("RESULTADO DA FASE 8")
        print("=" * 68)
        print(
            "Status:              "
            f"{summary['status']}"
        )
        print(
            "Amostras:            "
            f"{summary['samples']}"
        )
        print(
            "Ciclos executados:   "
            f"{performance['cycles_delta']}"
        )
        print(
            "Ciclos com sucesso:  "
            f"{performance['successful_cycles_delta']}"
        )
        print(
            "Ciclos sem sinal:    "
            f"{performance['no_signal_cycles_delta']}"
        )
        print(
            "Ciclos com falha:    "
            f"{performance['failed_cycles_delta']}"
        )
        print(
            "Trades:              "
            f"{performance['trade_count_delta']}"
        )
        print(
            "Variação da equity:  "
            f"R$ {performance['equity_delta']:.2f}"
        )
        print(
            "Drawdown máximo:     "
            f"{performance['max_drawdown_rate']:.2%}"
        )
        print(
            "Erros de endpoint:   "
            f"{summary['endpoint_errors']}"
        )
        print(
            "Violações de segurança: "
            f"{summary['safety_violations']}"
        )
        print()
        print(
            f"Relatório JSON: {self.report_path}"
        )
        print(
            f"Amostras CSV:  {self.samples_path}"
        )
        print(
            f"Eventos JSONL: {self.events_path}"
        )

        return (
            0
            if summary["status"] == "PASS"
            else 1
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Executa e acompanha uma sessão "
            "Paper prolongada da Fase 8."
        )
    )

    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
    )

    parser.add_argument(
        "--duration-minutes",
        type=float,
        default=10.0,
    )

    parser.add_argument(
        "--duration-seconds",
        type=float,
        default=None,
        help=(
            "Sobrescreve --duration-minutes; "
            "útil para smoke tests."
        ),
    )

    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=10.0,
    )

    parser.add_argument(
        "--reset",
        action="store_true",
        help=(
            "Reseta conta e relatório antes "
            "da execução."
        ),
    )

    parser.add_argument(
        "--confirm-reset",
        default=None,
    )

    parser.add_argument(
        "--leave-running",
        action="store_true",
        help=(
            "Não encerra a sessão ao final."
        ),
    )

    parser.add_argument(
        "--label",
        default="",
    )

    args = parser.parse_args()

    duration_seconds = (
        args.duration_seconds
        if args.duration_seconds is not None
        else args.duration_minutes * 60
    )

    if duration_seconds <= 0:
        parser.error(
            "A duração deve ser positiva."
        )

    if args.poll_seconds < 1:
        parser.error(
            "--poll-seconds deve ser "
            "pelo menos 1."
        )

    args.duration_seconds = duration_seconds

    return args


def main() -> int:
    args = parse_args()

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        with httpx.Client(
            base_url=args.base_url.rstrip("/"),
            timeout=45.0,
        ) as client:
            monitor = Phase8Monitor(
                client=client,
                duration_seconds=(
                    args.duration_seconds
                ),
                poll_seconds=args.poll_seconds,
                reset=args.reset,
                reset_confirmation=(
                    args.confirm_reset
                ),
                leave_running=(
                    args.leave_running
                ),
                label=args.label,
            )

            return monitor.execute()

    except httpx.ConnectError as exc:
        print(
            "[FAIL] Não foi possível conectar "
            f"ao servidor: {exc}"
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
