from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import TYPE_CHECKING, Any

from app.core.settings import settings

if TYPE_CHECKING:
    from app.ai.ai_engine import AIEngine


class AIRuntime:
    """
    Estado operacional seguro da camada AI.

    O runtime não carrega modelos, não acessa artefatos e não inicializa o
    Trainer durante o startup da aplicação. O AIEngine somente é resolvido
    quando uma operação de análise, treinamento, registro ou consulta detalhada
    é solicitada explicitamente.
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        pipeline_enabled: bool = True,
        strict_features: bool = False,
        fail_on_error: bool = False,
        advisory_only: bool = True,
        execution_authorized: bool = False,
        auto_load_model: bool = False,
        model_name: str = "opportunity",
        model_root: str = "model_artifacts",
        engine: AIEngine | None = None,
    ) -> None:
        if not advisory_only:
            raise ValueError("AI_ADVISORY_ONLY deve permanecer habilitado.")
        if execution_authorized:
            raise ValueError("AI_EXECUTION_AUTHORIZED deve permanecer desabilitado.")
        if auto_load_model:
            raise ValueError("AI_AUTO_LOAD_MODEL não é suportado por segurança.")

        self.enabled = bool(enabled)
        self.pipeline_enabled = bool(pipeline_enabled)
        self.strict_features = bool(strict_features)
        self.fail_on_error = bool(fail_on_error)
        self.advisory_only = True
        self.execution_authorized = False
        self.auto_load_model = False
        self.model_name = str(model_name or "opportunity").strip() or "opportunity"
        self.model_root = str(model_root or "model_artifacts").strip() or "model_artifacts"

        self._engine = engine
        self._started = False
        self._lock = RLock()
        self.last_report: dict[str, Any] = {}

    @classmethod
    def from_settings(cls) -> AIRuntime:
        return cls(
            enabled=settings.AI_ENABLED,
            pipeline_enabled=settings.AI_PIPELINE_ENABLED,
            strict_features=settings.AI_STRICT_FEATURES,
            fail_on_error=settings.AI_FAIL_ON_ERROR,
            advisory_only=settings.AI_ADVISORY_ONLY,
            execution_authorized=settings.AI_EXECUTION_AUTHORIZED,
            auto_load_model=settings.AI_AUTO_LOAD_MODEL,
            model_name=settings.AI_MODEL_NAME,
            model_root=settings.AI_MODEL_ROOT,
        )

    @property
    def engine_resolved(self) -> bool:
        return self._engine is not None

    @property
    def engine(self) -> AIEngine:
        with self._lock:
            if self._engine is None:
                from app.ai.ai_engine import ai_engine

                self._engine = ai_engine
            return self._engine

    @property
    def started(self) -> bool:
        with self._lock:
            return self._started

    def startup(self) -> dict[str, Any]:
        """
        Inicializa apenas o estado do runtime.

        Nenhum model manifest, artefato ou objeto de modelo é lido nesta etapa.
        """

        with self._lock:
            self._started = True
            self.last_report = {
                "operation": "STARTUP",
                "status": "READY" if self.enabled else "DISABLED",
                "engine_resolved": self.engine_resolved,
                "model_auto_load_attempted": False,
                "model_loaded_during_startup": False,
                "advisory_only": True,
                "execution_authorized": False,
            }

        return self.status(resolve_engine=False)

    def shutdown(self) -> dict[str, Any]:
        """Encerra o estado do runtime sem descarregar artefatos automaticamente."""

        with self._lock:
            self._started = False
            self.last_report = {
                "operation": "SHUTDOWN",
                "status": "STOPPED",
                "engine_resolved": self.engine_resolved,
                "model_auto_load_attempted": False,
                "advisory_only": True,
                "execution_authorized": False,
            }

        return self.status(resolve_engine=False)

    def analyze(self, opportunities: Any, **options: Any) -> list[Any]:
        if not self.enabled:
            raise RuntimeError("AI_RUNTIME_DISABLED")

        results = self.engine.analyze(opportunities, **options)
        self.last_report = {
            "operation": "ANALYZE",
            "status": "COMPLETED",
            "analyzed": len(results),
            "engine_report": dict(self.engine.last_report),
            "advisory_only": True,
            "execution_authorized": False,
        }
        return results

    def status(self, *, resolve_engine: bool = False) -> dict[str, Any]:
        engine_status: dict[str, Any]

        if resolve_engine:
            engine_status = self.engine.status(include_trainer=False)
        elif self._engine is not None:
            engine_status = self._engine.status(include_trainer=False)
        else:
            engine_status = {
                "status": "NOT_INITIALIZED",
                "predictor": {
                    "model_loaded": False,
                    "model_version": None,
                },
                "models": {
                    "auto_load": False,
                    "active_model": None,
                },
                "advisory_only": True,
                "execution_authorized": False,
            }

        predictor = engine_status.get("predictor", {})
        models = engine_status.get("models", {})

        return {
            "status": (
                "DISABLED"
                if not self.enabled
                else "READY"
                if self.started
                else "NOT_STARTED"
            ),
            "started": self.started,
            "enabled": self.enabled,
            "pipeline_enabled": self.pipeline_enabled,
            "strict_features": self.strict_features,
            "fail_on_error": self.fail_on_error,
            "engine_resolved": self.engine_resolved,
            "model_name": self.model_name,
            "model_root": self.model_root,
            "model_loaded": bool(predictor.get("model_loaded", False)),
            "model_version": predictor.get("model_version"),
            "active_model": (
                models.get("registry", {}).get("active", {}).get(self.model_name)
                if isinstance(models, dict)
                else None
            ),
            "auto_load_model": False,
            "model_auto_load_attempted": False,
            "advisory_only": True,
            "execution_authorized": False,
            "engine": engine_status if resolve_engine or self.engine_resolved else None,
            "last_report": deepcopy(self.last_report),
        }


ai_runtime = AIRuntime.from_settings()
