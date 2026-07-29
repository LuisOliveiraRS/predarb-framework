from __future__ import annotations

from collections import Counter
from hashlib import sha256
from typing import Any, Callable

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split

from app.ai.datasets.dataset_validator import DatasetValidator, dataset_validator
from app.ai.feature_store.feature_builder import FeatureBuilder
from app.ai.trainers.base_trainer import BaseTrainer, TrainingResult


class Trainer(BaseTrainer):
    """
    Trainer supervisionado de oportunidades.

    O treinamento exige target real, duas classes e todas as features
    canônicas. Probabilidade calibrada somente é declarada quando o wrapper
    CalibratedClassifierCV foi realmente utilizado.
    """

    def __init__(
        self,
        *,
        validator: DatasetValidator | None = None,
        estimator_factory: Callable[..., Any] | None = None,
        random_state: int = 42,
    ) -> None:
        self.validator = validator or dataset_validator
        self.estimator_factory = estimator_factory or RandomForestClassifier
        self.random_state = int(random_state)
        self.last_result: TrainingResult | None = None

    def _estimator(self) -> Any:
        return self.estimator_factory(
            n_estimators=200,
            random_state=self.random_state,
            class_weight="balanced",
            n_jobs=-1,
        )

    @staticmethod
    def _version(
        dataframe: pd.DataFrame,
        feature_names: tuple[str, ...],
        *,
        calibrated: bool,
    ) -> str:
        target_values = dataframe["success"].astype(int).tolist()
        payload = "|".join(
            [
                ",".join(feature_names),
                str(len(dataframe)),
                ",".join(map(str, target_values)),
                str(bool(calibrated)),
            ]
        )
        digest = sha256(payload.encode("utf-8")).hexdigest()[:12]
        return f"opportunity-rf-{digest}"

    @staticmethod
    def _distribution(target: pd.Series) -> dict[str, int]:
        counts = Counter(int(value) for value in target.tolist())
        return {str(key): int(counts[key]) for key in sorted(counts)}

    def fit(
        self,
        dataframe: pd.DataFrame,
        *,
        test_size: float = 0.25,
        calibrate: bool = False,
        calibration_cv: int = 3,
    ) -> TrainingResult:
        if not isinstance(dataframe, pd.DataFrame):
            raise TypeError("dataframe deve ser um pandas.DataFrame.")

        self.validator.require(
            dataframe,
            require_target=True,
            allow_unlabeled=False,
            allow_missing_features=False,
        )

        feature_names = tuple(FeatureBuilder.FEATURE_NAMES)
        prepared = dataframe.loc[:, [*feature_names, "success"]].copy()

        for column in feature_names:
            prepared[column] = pd.to_numeric(prepared[column], errors="raise")

        prepared["success"] = pd.to_numeric(
            prepared["success"],
            errors="raise",
        ).astype(int)

        classes = sorted(prepared["success"].unique().tolist())
        if classes != [0, 1]:
            raise ValueError(
                "O treinamento exige as classes 0 e 1 com resultados reais."
            )

        x = prepared.loc[:, feature_names]
        y = prepared["success"]
        class_counts = y.value_counts()
        warnings: list[str] = []

        can_validate = (
            len(prepared) >= 8
            and int(class_counts.min()) >= 2
            and 0 < float(test_size) < 1
        )

        if can_validate:
            x_train, x_validation, y_train, y_validation = train_test_split(
                x,
                y,
                test_size=float(test_size),
                random_state=self.random_state,
                stratify=y,
            )
        else:
            x_train, y_train = x, y
            x_validation = x.iloc[0:0]
            y_validation = y.iloc[0:0]
            warnings.append("VALIDATION_SKIPPED_INSUFFICIENT_DATA")

        base_model = self._estimator()
        calibrated = False

        if calibrate:
            minimum_class_samples = int(y_train.value_counts().min())
            if minimum_class_samples >= int(calibration_cv):
                model = CalibratedClassifierCV(
                    estimator=base_model,
                    method="sigmoid",
                    cv=int(calibration_cv),
                )
                calibrated = True
            else:
                model = base_model
                warnings.append("CALIBRATION_SKIPPED_INSUFFICIENT_CLASS_SAMPLES")
        else:
            model = base_model

        model.fit(x_train, y_train)

        metrics: dict[str, Any] = {
            "class_distribution": self._distribution(y),
            "validation_performed": bool(len(x_validation)),
        }

        if len(x_validation):
            predicted = model.predict(x_validation)
            metrics["accuracy"] = round(
                float(accuracy_score(y_validation, predicted)),
                8,
            )
            metrics["balanced_accuracy"] = round(
                float(balanced_accuracy_score(y_validation, predicted)),
                8,
            )

            predict_proba = getattr(model, "predict_proba", None)
            if callable(predict_proba) and len(set(y_validation.tolist())) == 2:
                probability = predict_proba(x_validation)[:, 1]
                metrics["roc_auc"] = round(
                    float(roc_auc_score(y_validation, probability)),
                    8,
                )
            else:
                metrics["roc_auc"] = None
        else:
            metrics.update(
                {
                    "accuracy": None,
                    "balanced_accuracy": None,
                    "roc_auc": None,
                }
            )

        version = self._version(
            prepared,
            feature_names,
            calibrated=calibrated,
        )

        result = TrainingResult(
            model=model,
            version=version,
            status="TRAINED",
            feature_names=feature_names,
            target_name="success",
            rows=len(prepared),
            train_rows=len(x_train),
            validation_rows=len(x_validation),
            metrics=metrics,
            warnings=warnings,
            probability_calibrated=calibrated,
        )
        self.last_result = result
        return result

    def train(self, x: Any, y: Any = None) -> Any:
        """
        Compatibilidade com ``trainer.train(x, y)``.

        Retorna o modelo como antes. Para o contrato completo, use ``fit``.
        """

        if y is None:
            if not isinstance(x, pd.DataFrame) or "success" not in x.columns:
                raise TypeError(
                    "train(dataframe) exige a coluna success; "
                    "ou utilize train(x, y)."
                )
            dataframe = x.copy()
        else:
            if isinstance(x, pd.DataFrame):
                dataframe = x.copy()
            else:
                array = np.asarray(x)
                if array.ndim != 2 or array.shape[1] != len(FeatureBuilder.FEATURE_NAMES):
                    raise ValueError("x possui quantidade de features incompatível.")
                dataframe = pd.DataFrame(
                    array,
                    columns=FeatureBuilder.FEATURE_NAMES,
                )
            dataframe["success"] = list(y)

        return self.fit(dataframe).model

    def status(self) -> dict[str, Any]:
        return {
            "trained": self.last_result is not None,
            "last_result": self.last_result.to_dict() if self.last_result else None,
        }


trainer = Trainer()
