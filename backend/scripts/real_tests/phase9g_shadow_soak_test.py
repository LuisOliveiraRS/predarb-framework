from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import httpx


BACKEND_ROOT = Path(
    __file__
).resolve().parents[2]

REPORT_DIR = (
    BACKEND_ROOT
    / "real_test_reports"
)

SHADOW_AUDIT_PATH = (
    BACKEND_ROOT
    / "paper_data"
    / "shadow_execution_audit.jsonl"
)

PAPER_ACCOUNT_PATH = (
    BACKEND_ROOT
    / "paper_data"
    / "paper_account.json"
)

SHADOW_PREFIX = (
    "/real-markets/shadow-runtime"
)

ENDPOINTS = {
    "health": f"{SHADOW_PREFIX}/health",
    "status": f"{SHADOW_PREFIX}/status",
    "metrics": f"{SHADOW_PREFIX}/metrics",
    "last_cycle": f"{SHADOW_PREFIX}/last-cycle",
    "architecture": f"{SHADOW_PREFIX}/architecture",
}

PROTECTED_FALSE_FLAGS = (
    "paper_execution_authorized",
    "live_authorization",
    "execution_authorized",
    "live_execution",
    "financial_execution",
    "next_step_authorized",
    "automatic_execution_authorized",
    "order_submission_available",
    "paper_account_mutation",
    "wallet_access",
    "credential_access",
)


def utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


def iso_now() -> str:
    return utc_now().isoformat()


def number(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        return float(value)
    except (
        TypeError,
        ValueError,
    ):
        return default


def integer(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(value)
    except (
        TypeError,
        ValueError,
    ):
        return default


def file_state(
    path: Path,
) -> dict[str, Any]:
    if not path.exists():
        return {
            "exists": False,
            "size": None,
            "sha256": None,
        }

    content = path.read_bytes()

    return {
        "exists": True,
        "size": len(content),
        "sha256": hashlib.sha256(
            content
        ).hexdigest(),
    }


def truthy_safety_violations(
    value: Any,
    *,
    path: str = "$",
) -> list[str]:
    violations: list[str] = []

    if isinstance(
        value,
        Mapping,
    ):
        for key, child in value.items():
            child_path = (
                f"{path}.{key}"
            )

            if (
                key in PROTECTED_FALSE_FLAGS
                and child is not False
            ):
                violations.append(
                    f"{child_path}={child!r}"
                )

            violations.extend(
                truthy_safety_violations(
                    child,
                    path=child_path,
                )
            )

    elif isinstance(
        value,
        list,
    ):
        for index, child in enumerate(
            value
        ):
            violations.extend(
                truthy_safety_violations(
                    child,
                    path=(
                        f"{path}[{index}]"
                    ),
                )
            )

    return violations


def safe_label(
    value: str,
) -> str:
    normalized = "".join(
        character
        if (
            character.isalnum()
            or character in "-_"
        )
        else "-"
        for character in value.strip()
    )

    normalized = normalized.strip(
        "-"
    )

    return normalized[:50]


class Phase9GShadowSoakMonitor:
    def __init__(
        self,
        *,
        client: httpx.Client,
        duration_seconds: float,
        poll_seconds: float,
        label: str = "",
        allow_idle: bool = False,
    ) -> None:
        self.client = client
        self.duration_seconds = (
            duration_seconds
        )
        self.poll_seconds = poll_seconds
        self.allow_idle = allow_idle

        timestamp = utc_now().strftime(
            "%Y%m%d-%H%M%S"
        )

        resolved_label = safe_label(
            label
        )

        suffix = (
            f"_{resolved_label}"
            if resolved_label
            else ""
        )

        stem = (
            "phase9g_shadow_soak_"
            f"{timestamp}"
            f"{suffix}"
        )

        self.report_path = (
            REPORT_DIR
            / f"{stem}.json"
        )

        self.samples_path = (
            REPORT_DIR
            / f"{stem}.csv"
        )

        self.events_path = (
            REPORT_DIR
            / f"{stem}.jsonl"
        )

        self.samples: list[
            dict[str, Any]
        ] = []

        self.safety_violations: list[
            str
        ] = []

        self.notes: list[str] = []

        self.started_at: str | None = None
        self.completed_at: str | None = None

        self.audit_before: dict[
            str,
            Any,
        ] = {}

        self.audit_after: dict[
            str,
            Any,
        ] = {}

        self.paper_before: dict[
            str,
            Any,
        ] = {}

        self.paper_after: dict[
            str,
            Any,
        ] = {}

    def request_json(
        self,
        path: str,
    ) -> tuple[
        dict[str, Any],
        float,
    ]:
        started = time.perf_counter()

        response = self.client.get(
            path
        )

        elapsed_ms = round(
            (
                time.perf_counter()
                - started
            )
            * 1000,
            3,
        )

        response.raise_for_status()

        payload = response.json()

        if not isinstance(
            payload,
            dict,
        ):
            payload = {
                "value": payload,
            }

        violations = (
            truthy_safety_violations(
                payload,
                path=path,
            )
        )

        for violation in violations:
            if (
                violation
                not in self.safety_violations
            ):
                self.safety_violations.append(
                    violation
                )

        return payload, elapsed_ms

    def capture_bundle(
        self,
    ) -> dict[str, Any]:
        payloads: dict[
            str,
            dict[str, Any],
        ] = {}

        latencies: dict[
            str,
            float,
        ] = {}

        for name, endpoint in (
            ENDPOINTS.items()
        ):
            payload, latency = (
                self.request_json(
                    endpoint
                )
            )

            payloads[name] = payload
            latencies[name] = latency

        return {
            "captured_at": iso_now(),
            "payloads": payloads,
            "latency_ms": latencies,
        }

    @staticmethod
    def compact_sample(
        bundle: Mapping[str, Any],
    ) -> dict[str, Any]:
        payloads = (
            bundle.get("payloads")
            or {}
        )

        status = (
            payloads.get("status")
            or {}
        )

        metrics = (
            payloads.get("metrics")
            or {}
        )

        health = (
            payloads.get("health")
            or {}
        )

        last_cycle_payload = (
            payloads.get("last_cycle")
            or {}
        )

        last_cycle_record = (
            last_cycle_payload.get(
                "last_cycle"
            )
            or status.get(
                "last_cycle"
            )
            or metrics.get(
                "last_cycle"
            )
            or {}
        )

        latency = (
            bundle.get("latency_ms")
            or {}
        )

        return {
            "captured_at": (
                bundle.get(
                    "captured_at"
                )
            ),
            "runtime_status": (
                status.get(
                    "status",
                    health.get("status"),
                )
            ),
            "phase": status.get(
                "phase"
            ),
            "scheduler_connected": (
                status.get(
                    "scheduler_connected",
                    metrics.get(
                        "scheduler_connected"
                    ),
                )
            ),
            "cycle_count": integer(
                metrics.get(
                    "cycle_count",
                    status.get(
                        "cycle_count"
                    ),
                )
            ),
            "completed_cycle_count": (
                integer(
                    metrics.get(
                        "completed_cycle_count",
                        status.get(
                            "completed_cycle_count"
                        ),
                    )
                )
            ),
            "failed_cycle_count": (
                integer(
                    metrics.get(
                        "failed_cycle_count",
                        status.get(
                            "failed_cycle_count"
                        ),
                    )
                )
            ),
            "skipped_cycle_count": (
                integer(
                    metrics.get(
                        "skipped_cycle_count",
                        status.get(
                            "skipped_cycle_count"
                        ),
                    )
                )
            ),
            "simulated_count": integer(
                metrics.get(
                    "simulated_count",
                    status.get(
                        "simulated_count"
                    ),
                )
            ),
            "rejected_count": integer(
                metrics.get(
                    "rejected_count",
                    status.get(
                        "rejected_count"
                    ),
                )
            ),
            "error_count": integer(
                metrics.get(
                    "error_count",
                    status.get(
                        "error_count"
                    ),
                )
            ),
            "last_cycle_id": (
                metrics.get(
                    "last_cycle_id",
                    status.get(
                        "last_cycle_id"
                    ),
                )
            ),
            "last_cycle_status": (
                last_cycle_record.get(
                    "status"
                )
                or last_cycle_payload.get(
                    "last_cycle_status"
                )
                or metrics.get(
                    "last_cycle_status"
                )
            ),
            "last_duration_ms": number(
                metrics.get(
                    "last_duration_ms",
                    status.get(
                        "last_duration_ms"
                    ),
                )
            ),
            "last_error": (
                metrics.get(
                    "last_error",
                    status.get(
                        "last_error"
                    ),
                )
            ),
            "latency_health_ms": number(
                latency.get(
                    "health"
                )
            ),
            "latency_status_ms": number(
                latency.get(
                    "status"
                )
            ),
            "latency_metrics_ms": number(
                latency.get(
                    "metrics"
                )
            ),
            "latency_last_cycle_ms": (
                number(
                    latency.get(
                        "last_cycle"
                    )
                )
            ),
            "latency_architecture_ms": (
                number(
                    latency.get(
                        "architecture"
                    )
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
                    default=str,
                )
                + "\n"
            )

    def run_monitoring(
        self,
    ) -> None:
        deadline = (
            time.monotonic()
            + self.duration_seconds
        )

        next_capture = time.monotonic()

        while (
            time.monotonic()
            < deadline
        ):
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

            sample = self.compact_sample(
                bundle
            )

            self.samples.append(
                sample
            )

            self.append_event(
                bundle
            )

            print(
                "[AMOSTRA]"
                f" ciclos={sample['cycle_count']}"
                f" concluidos={sample['completed_cycle_count']}"
                f" falhas={sample['failed_cycle_count']}"
                f" ignorados={sample['skipped_cycle_count']}"
                f" simulados={sample['simulated_count']}"
                f" rejeitados={sample['rejected_count']}"
                f" erros={sample['error_count']}"
                f" conectado={sample['scheduler_connected']}"
                f" status={sample['runtime_status']}"
            )

            next_capture = (
                time.monotonic()
                + self.poll_seconds
            )

    @staticmethod
    def delta(
        first: Mapping[str, Any],
        last: Mapping[str, Any],
        key: str,
    ) -> int:
        return (
            integer(
                last.get(key)
            )
            - integer(
                first.get(key)
            )
        )

    def build_result(
        self,
    ) -> dict[str, Any]:
        first = (
            self.samples[0]
            if self.samples
            else {}
        )

        last = (
            self.samples[-1]
            if self.samples
            else {}
        )

        deltas = {
            key: self.delta(
                first,
                last,
                key,
            )
            for key in (
                "cycle_count",
                "completed_cycle_count",
                "failed_cycle_count",
                "skipped_cycle_count",
                "simulated_count",
                "rejected_count",
                "error_count",
            )
        }

        audit_unchanged = (
            self.audit_before
            == self.audit_after
        )

        paper_unchanged = (
            self.paper_before
            == self.paper_after
        )

        progress_approved = (
            self.allow_idle
            or deltas[
                "cycle_count"
            ] > 0
        )

        criteria = {
            "samples_collected": (
                len(self.samples) > 0
            ),
            "safety_violations_zero": (
                not self.safety_violations
            ),
            "shadow_audit_unchanged": (
                audit_unchanged
            ),
            "paper_account_unchanged": (
                paper_unchanged
            ),
            "cycle_progress": (
                progress_approved
            ),
            "financial_execution_disabled": (
                not self.safety_violations
            ),
        }

        approved = all(
            criteria.values()
        )

        if (
            not progress_approved
            and not self.allow_idle
        ):
            self.notes.append(
                "Nenhum novo ciclo Shadow foi "
                "observado durante o soak test."
            )

        if not audit_unchanged:
            self.notes.append(
                "O arquivo de auditoria Shadow "
                "foi alterado."
            )

        if not paper_unchanged:
            self.notes.append(
                "A conta Paper foi alterada."
            )

        latency_fields = (
            "latency_health_ms",
            "latency_status_ms",
            "latency_metrics_ms",
            "latency_last_cycle_ms",
            "latency_architecture_ms",
        )

        latency_summary = {}

        for field in latency_fields:
            values = [
                number(
                    sample.get(field)
                )
                for sample in self.samples
            ]

            latency_summary[field] = {
                "minimum": (
                    min(values)
                    if values
                    else None
                ),
                "maximum": (
                    max(values)
                    if values
                    else None
                ),
                "average": (
                    round(
                        sum(values)
                        / len(values),
                        3,
                    )
                    if values
                    else None
                ),
            }

        return {
            "phase": "9G",
            "test": (
                "shadow_runtime_soak_observability"
            ),
            "approved": approved,
            "started_at": self.started_at,
            "completed_at": (
                self.completed_at
            ),
            "duration_seconds": (
                self.duration_seconds
            ),
            "poll_seconds": (
                self.poll_seconds
            ),
            "allow_idle": (
                self.allow_idle
            ),
            "samples_count": (
                len(self.samples)
            ),
            "criteria": criteria,
            "deltas": deltas,
            "first_sample": first,
            "last_sample": last,
            "latency_summary": (
                latency_summary
            ),
            "safety_violations": (
                self.safety_violations
            ),
            "notes": self.notes,
            "artifacts": {
                "shadow_audit_before": (
                    self.audit_before
                ),
                "shadow_audit_after": (
                    self.audit_after
                ),
                "paper_account_before": (
                    self.paper_before
                ),
                "paper_account_after": (
                    self.paper_after
                ),
            },
            "reports": {
                "json": str(
                    self.report_path
                ),
                "csv": str(
                    self.samples_path
                ),
                "jsonl": str(
                    self.events_path
                ),
            },
            "market_data_only": True,
            "read_only_market_access": True,
            "shadow_execution": True,
            "simulation_only": True,
            "paper_execution_authorized": False,
            "live_authorization": False,
            "execution_authorized": False,
            "live_execution": False,
            "financial_execution": False,
            "next_step_authorized": False,
            "automatic_execution_authorized": False,
            "order_submission_available": False,
            "paper_account_mutation": False,
            "wallet_access": False,
            "credential_access": False,
        }

    def save_samples_csv(
        self,
    ) -> None:
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
            writer.writerows(
                self.samples
            )

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
                default=str,
            ),
            encoding="utf-8",
        )

    def execute(
        self,
    ) -> int:
        self.started_at = iso_now()

        self.audit_before = file_state(
            SHADOW_AUDIT_PATH
        )

        self.paper_before = file_state(
            PAPER_ACCOUNT_PATH
        )

        try:
            self.run_monitoring()

        except Exception:
            self.notes.append(
                traceback.format_exc()
            )

        finally:
            self.completed_at = iso_now()

            self.audit_after = file_state(
                SHADOW_AUDIT_PATH
            )

            self.paper_after = file_state(
                PAPER_ACCOUNT_PATH
            )

        result = self.build_result()

        self.save_samples_csv()
        self.save_result(
            result
        )

        print(
            "\n================ RESULTADO FASE 9G ================\n"
        )

        print(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )

        print(
            "\nRelatorio JSON:"
            f" {self.report_path}"
        )

        print(
            "Amostras CSV:"
            f" {self.samples_path}"
        )

        print(
            "Eventos JSONL:"
            f" {self.events_path}"
        )

        return (
            0
            if result["approved"]
            else 1
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Executa o soak test observacional "
            "do Shadow Runtime da Fase 9G."
        )
    )

    parser.add_argument(
        "--base-url",
        default=(
            "http://127.0.0.1:8000"
        ),
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
            "util para smoke tests."
        ),
    )

    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=10.0,
    )

    parser.add_argument(
        "--label",
        default="",
    )

    parser.add_argument(
        "--allow-idle",
        action="store_true",
        help=(
            "Permite aprovacao sem novos ciclos; "
            "destinado apenas a testes da coleta."
        ),
    )

    args = parser.parse_args()

    duration_seconds = (
        args.duration_seconds
        if (
            args.duration_seconds
            is not None
        )
        else (
            args.duration_minutes
            * 60
        )
    )

    if duration_seconds <= 0:
        parser.error(
            "A duracao deve ser positiva."
        )

    if args.poll_seconds < 1:
        parser.error(
            "--poll-seconds deve ser "
            "pelo menos 1."
        )

    args.duration_seconds = (
        duration_seconds
    )

    return args


def main() -> int:
    args = parse_args()

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        with httpx.Client(
            base_url=(
                args.base_url.rstrip("/")
            ),
            timeout=45.0,
        ) as client:
            monitor = (
                Phase9GShadowSoakMonitor(
                    client=client,
                    duration_seconds=(
                        args.duration_seconds
                    ),
                    poll_seconds=(
                        args.poll_seconds
                    ),
                    label=args.label,
                    allow_idle=(
                        args.allow_idle
                    ),
                )
            )

            return monitor.execute()

    except httpx.ConnectError as exc:
        print(
            "[FAIL] Nao foi possivel conectar "
            f"ao servidor: {exc}"
        )

        return 2

    except Exception:
        traceback.print_exc()

        return 3


if __name__ == "__main__":
    sys.exit(
        main()
    )
