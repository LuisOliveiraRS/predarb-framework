from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
import unicodedata
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable, Mapping

from app.real_markets.models import NormalizedMarket
from app.real_markets.service import (
    RealMarketDataService,
    real_market_data_service,
)


BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env_float(
    name: str,
    default: float,
) -> float:
    value = os.getenv(name)

    if value is None:
        return float(default)

    try:
        return float(value)
    except ValueError:
        return float(default)


def _strip_accents(
    value: str,
) -> str:
    normalized = unicodedata.normalize(
        "NFKD",
        value,
    )

    return "".join(
        char
        for char in normalized
        if not unicodedata.combining(char)
    )


STOPWORDS = {
    "a",
    "above",
    "an",
    "and",
    "as",
    "at",
    "ate",
    "be",
    "below",
    "by",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "em",
    "end",
    "fim",
    "for",
    "ficara",
    "ficarao",
    "in",
    "is",
    "no",
    "na",
    "nas",
    "nos",
    "of",
    "on",
    "or",
    "o",
    "os",
    "para",
    "sera",
    "serao",
    "the",
    "to",
    "um",
    "uma",
    "will",
}


OUTCOME_ALIASES = {
    "yes": "YES",
    "sim": "YES",
    "true": "YES",
    "no": "NO",
    "nao": "NO",
    "false": "NO",
    "over": "OVER",
    "above": "OVER",
    "acima": "OVER",
    "under": "UNDER",
    "below": "UNDER",
    "abaixo": "UNDER",
}


def normalize_text(
    value: str | None,
) -> str:
    if not value:
        return ""

    lowered = _strip_accents(
        value
    ).lower()

    lowered = re.sub(
        r"[^a-z0-9]+",
        " ",
        lowered,
    )

    tokens = [
        token
        for token in lowered.split()
        if (
            token
            and token not in STOPWORDS
        )
    ]

    return " ".join(tokens)


def normalized_tokens(
    value: str | None,
) -> tuple[str, ...]:
    return tuple(
        normalize_text(value).split()
    )


def canonical_outcome_label(
    value: str,
) -> str:
    normalized = _strip_accents(
        value
    ).lower()

    normalized = re.sub(
        r"[^a-z0-9]+",
        "_",
        normalized,
    ).strip("_")

    return OUTCOME_ALIASES.get(
        normalized,
        normalized.upper(),
    )


def outcome_signature(
    market: NormalizedMarket,
) -> tuple[str, ...]:
    return tuple(
        sorted(
            canonical_outcome_label(
                outcome.label
            )
            for outcome in market.outcomes
        )
    )


def _parse_datetime(
    value: str | None,
) -> datetime | None:
    if not value:
        return None

    normalized = value.strip()

    if normalized.endswith("Z"):
        normalized = (
            normalized[:-1]
            + "+00:00"
        )

    try:
        parsed = datetime.fromisoformat(
            normalized
        )
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(
        timezone.utc
    )


def market_fingerprint(
    market: NormalizedMarket,
) -> str:
    close_time = _parse_datetime(
        market.close_time
    )

    payload = {
        "title": normalize_text(
            market.title
        ),
        "close_date": (
            close_time.date().isoformat()
            if close_time
            else None
        ),
        "outcomes": list(
            outcome_signature(
                market
            )
        ),
        "category": normalize_text(
            market.category
        ),
    }

    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(
        encoded
    ).hexdigest()


def _jaccard(
    left: Iterable[str],
    right: Iterable[str],
) -> float:
    left_set = set(left)
    right_set = set(right)

    if not left_set and not right_set:
        return 1.0

    union = left_set | right_set

    if not union:
        return 0.0

    return len(
        left_set & right_set
    ) / len(union)


def _title_similarity(
    left: str,
    right: str,
) -> float:
    left_normalized = normalize_text(
        left
    )
    right_normalized = normalize_text(
        right
    )

    if (
        not left_normalized
        or not right_normalized
    ):
        return 0.0

    sequence = SequenceMatcher(
        None,
        left_normalized,
        right_normalized,
    ).ratio()

    token_score = _jaccard(
        left_normalized.split(),
        right_normalized.split(),
    )

    return round(
        sequence * 0.55
        + token_score * 0.45,
        8,
    )


def _close_time_similarity(
    left: str | None,
    right: str | None,
) -> tuple[float, int | None]:
    left_dt = _parse_datetime(left)
    right_dt = _parse_datetime(right)

    if (
        left_dt is None
        or right_dt is None
    ):
        return 0.5, None

    difference_days = abs(
        (
            left_dt
            - right_dt
        ).total_seconds()
    ) / 86400

    if difference_days <= 1:
        score = 1.0
    elif difference_days <= 7:
        score = 0.9
    elif difference_days <= 30:
        score = 0.7
    elif difference_days <= 90:
        score = 0.4
    elif difference_days <= 365:
        score = 0.15
    else:
        score = 0.0

    return (
        score,
        round(difference_days),
    )


@dataclass(frozen=True)
class MarketIdentity:
    key: str
    connector_id: str
    market_id: str
    title: str
    normalized_title: str
    fingerprint: str
    outcome_signature: tuple[str, ...]
    close_time: str | None
    category: str | None

    @classmethod
    def from_market(
        cls,
        market: NormalizedMarket,
    ) -> "MarketIdentity":
        return cls(
            key=market.key,
            connector_id=(
                market.connector_id
            ),
            market_id=market.market_id,
            title=market.title,
            normalized_title=(
                normalize_text(
                    market.title
                )
            ),
            fingerprint=(
                market_fingerprint(
                    market
                )
            ),
            outcome_signature=(
                outcome_signature(
                    market
                )
            ),
            close_time=market.close_time,
            category=market.category,
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MarketMatchScore:
    left_key: str
    right_key: str
    status: str
    score: float
    title_score: float
    outcome_score: float
    close_time_score: float
    category_score: float
    close_time_difference_days: int | None
    same_connector: bool
    hard_rejected: bool
    reasons: tuple[str, ...]

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return asdict(self)


class ManualMarketMatchStore:
    """Configuração persistente de pares equivalentes confirmados."""

    def __init__(
        self,
        path: str | Path | None = None,
    ) -> None:
        configured = (
            path
            if path is not None
            else os.getenv(
                "REAL_MARKET_MANUAL_MATCHES_PATH",
                (
                    "paper_data/"
                    "real_market_manual_matches.json"
                ),
            )
        )

        candidate = Path(configured)

        if not candidate.is_absolute():
            candidate = (
                BACKEND_ROOT
                / candidate
            )

        self.path = candidate.resolve()
        self._lock = threading.RLock()

    @staticmethod
    def _safe_flags() -> dict[str, Any]:
        return {
            "market_data_only": True,
            "mapping_configuration_only": True,
            "paper_execution_authorized": False,
            "live_authorization": False,
            "execution_authorized": False,
            "live_execution": False,
            "financial_execution": False,
            "next_step_authorized": False,
        }

    @classmethod
    def _empty_state(
        cls,
    ) -> dict[str, Any]:
        return {
            "version": 1,
            "updated_at": None,
            "matches": [],
            **cls._safe_flags(),
        }

    @staticmethod
    def _pair_id(
        left_key: str,
        right_key: str,
    ) -> str:
        ordered = sorted(
            [
                left_key,
                right_key,
            ]
        )

        digest = hashlib.sha256(
            "\n".join(
                ordered
            ).encode("utf-8")
        ).hexdigest()

        return digest[:24]

    def load(
        self,
    ) -> dict[str, Any]:
        with self._lock:
            if not self.path.is_file():
                return self._empty_state()

            payload = json.loads(
                self.path.read_text(
                    encoding="utf-8-sig"
                )
            )

            if not isinstance(
                payload,
                dict,
            ):
                raise ValueError(
                    "Arquivo de correspondências inválido."
                )

            payload.setdefault(
                "matches",
                [],
            )

            if not isinstance(
                payload["matches"],
                list,
            ):
                raise ValueError(
                    "Lista de correspondências inválida."
                )

            return payload

    def _save(
        self,
        state: Mapping[str, Any],
    ) -> None:
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = deepcopy(
            dict(state)
        )

        payload.update(
            self._safe_flags()
        )

        handle, temp_name = (
            tempfile.mkstemp(
                prefix=(
                    f"{self.path.stem}_"
                ),
                suffix=".tmp",
                dir=str(
                    self.path.parent
                ),
            )
        )

        temp_path = Path(
            temp_name
        )

        try:
            with os.fdopen(
                handle,
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    payload,
                    file,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                file.flush()
                os.fsync(
                    file.fileno()
                )

            temp_path.replace(
                self.path
            )

        finally:
            temp_path.unlink(
                missing_ok=True
            )

    def list_matches(
        self,
    ) -> list[dict[str, Any]]:
        matches = [
            deepcopy(item)
            for item in (
                self.load().get(
                    "matches",
                    [],
                )
            )
            if isinstance(
                item,
                Mapping,
            )
        ]

        matches.sort(
            key=lambda item: str(
                item.get(
                    "created_at"
                )
                or ""
            ),
            reverse=True,
        )

        return matches

    def add(
        self,
        *,
        left_key: str,
        right_key: str,
        score: Mapping[str, Any],
        note: str | None = None,
    ) -> dict[str, Any]:
        if left_key == right_key:
            raise ValueError(
                "Um mercado não pode ser "
                "correspondido consigo mesmo."
            )

        left_connector = (
            left_key.split(
                ":",
                1,
            )[0]
        )

        right_connector = (
            right_key.split(
                ":",
                1,
            )[0]
        )

        if (
            not left_connector
            or not right_connector
            or left_connector
            == right_connector
        ):
            raise ValueError(
                "A correspondência manual deve "
                "usar conectores diferentes."
            )

        pair_id = self._pair_id(
            left_key,
            right_key,
        )

        with self._lock:
            state = self.load()
            matches = [
                dict(item)
                for item in (
                    state.get(
                        "matches",
                        [],
                    )
                )
                if isinstance(
                    item,
                    Mapping,
                )
            ]

            if any(
                item.get("id")
                == pair_id
                for item in matches
            ):
                raise ValueError(
                    "A correspondência manual "
                    "já está registrada."
                )

            created_at = _utc_now()

            record = {
                "id": pair_id,
                "left_key": left_key,
                "right_key": right_key,
                "relation": "EQUIVALENT",
                "source": "MANUAL_CONFIRMATION",
                "note": (
                    note.strip()
                    if note
                    else None
                ),
                "created_at": created_at,
                "score_at_confirmation": (
                    deepcopy(
                        dict(score)
                    )
                ),
                **self._safe_flags(),
            }

            matches.append(
                record
            )

            state.update(
                {
                    "updated_at": (
                        created_at
                    ),
                    "matches": matches,
                    **self._safe_flags(),
                }
            )

            self._save(state)
            return deepcopy(record)

    def remove(
        self,
        match_id: str,
    ) -> bool:
        with self._lock:
            state = self.load()
            matches = [
                dict(item)
                for item in (
                    state.get(
                        "matches",
                        [],
                    )
                )
                if isinstance(
                    item,
                    Mapping,
                )
            ]

            filtered = [
                item
                for item in matches
                if item.get("id")
                != match_id
            ]

            if len(filtered) == len(
                matches
            ):
                return False

            state.update(
                {
                    "updated_at": (
                        _utc_now()
                    ),
                    "matches": filtered,
                    **self._safe_flags(),
                }
            )

            self._save(state)
            return True


class MarketMatchingService:
    """Identidade e correspondência segura entre mercados."""

    def __init__(
        self,
        *,
        market_data_service: (
            RealMarketDataService
        ) = real_market_data_service,
        store: (
            ManualMarketMatchStore
            | None
        ) = None,
        candidate_threshold: (
            float
            | None
        ) = None,
        strong_threshold: (
            float
            | None
        ) = None,
    ) -> None:
        self.market_data_service = (
            market_data_service
        )

        self.store = (
            store
            if store is not None
            else ManualMarketMatchStore()
        )

        self.candidate_threshold = max(
            0.0,
            min(
                1.0,
                (
                    _env_float(
                        "REAL_MARKET_MATCH_CANDIDATE_THRESHOLD",
                        0.55,
                    )
                    if candidate_threshold
                    is None
                    else float(
                        candidate_threshold
                    )
                ),
            ),
        )

        self.strong_threshold = max(
            self.candidate_threshold,
            min(
                1.0,
                (
                    _env_float(
                        "REAL_MARKET_MATCH_STRONG_THRESHOLD",
                        0.80,
                    )
                    if strong_threshold
                    is None
                    else float(
                        strong_threshold
                    )
                ),
            ),
        )

    @staticmethod
    def _safe_flags() -> dict[str, Any]:
        return {
            "market_data_only": True,
            "read_only": True,
            "automatic_matching_authorized": False,
            "paper_execution_authorized": False,
            "live_authorization": False,
            "execution_authorized": False,
            "live_execution": False,
            "financial_execution": False,
            "next_step_authorized": False,
        }

    @staticmethod
    def identity(
        market: NormalizedMarket,
    ) -> MarketIdentity:
        return MarketIdentity.from_market(
            market
        )

    def compare(
        self,
        left: NormalizedMarket,
        right: NormalizedMarket,
    ) -> MarketMatchScore:
        same_connector = (
            left.connector_id
            == right.connector_id
        )

        left_outcomes = set(
            outcome_signature(
                left
            )
        )

        right_outcomes = set(
            outcome_signature(
                right
            )
        )

        outcome_score = _jaccard(
            left_outcomes,
            right_outcomes,
        )

        title_score = (
            _title_similarity(
                left.title,
                right.title,
            )
        )

        (
            close_time_score,
            close_time_difference_days,
        ) = _close_time_similarity(
            left.close_time,
            right.close_time,
        )

        left_category = normalize_text(
            left.category
        )

        right_category = normalize_text(
            right.category
        )

        if (
            not left_category
            or not right_category
        ):
            category_score = 0.5

        elif left_category == right_category:
            category_score = 1.0

        else:
            category_score = 0.0

        minimum_title_score = 0.45

        hard_rejected = (
            same_connector
            or outcome_score < 0.5
            or title_score < minimum_title_score
        )

        reasons: list[str] = []

        if same_connector:
            reasons.append(
                "SAME_CONNECTOR"
            )

        if outcome_score < 0.5:
            reasons.append(
                "OUTCOME_STRUCTURE_MISMATCH"
            )

        if title_score < minimum_title_score:
            reasons.append(
                "TITLE_SIMILARITY_TOO_LOW"
            )

        if (
            close_time_difference_days
            is not None
            and close_time_difference_days
            > 365
        ):
            reasons.append(
                "CLOSE_TIME_TOO_DISTANT"
            )

        score = round(
            title_score * 0.60
            + outcome_score * 0.20
            + close_time_score * 0.15
            + category_score * 0.05,
            8,
        )

        if hard_rejected:
            status = "REJECTED"

        elif (
            score
            >= self.strong_threshold
        ):
            status = (
                "STRONG_CANDIDATE"
            )

        elif (
            score
            >= self.candidate_threshold
        ):
            status = "CANDIDATE"

        else:
            status = "REJECTED"

        if (
            status == "REJECTED"
            and not reasons
        ):
            reasons.append(
                "SCORE_BELOW_THRESHOLD"
            )

        return MarketMatchScore(
            left_key=left.key,
            right_key=right.key,
            status=status,
            score=score,
            title_score=title_score,
            outcome_score=round(
                outcome_score,
                8,
            ),
            close_time_score=round(
                close_time_score,
                8,
            ),
            category_score=round(
                category_score,
                8,
            ),
            close_time_difference_days=(
                close_time_difference_days
            ),
            same_connector=(
                same_connector
            ),
            hard_rejected=(
                hard_rejected
            ),
            reasons=tuple(reasons),
        )

    async def list_identities(
        self,
        *,
        connector_id: str | None = None,
        limit: int = 100,
    ) -> list[MarketIdentity]:
        markets = await (
            self.market_data_service
            .list_markets(
                connector_id=(
                    connector_id
                ),
                limit=limit,
            )
        )

        return [
            self.identity(
                market
            )
            for market in markets
        ]

    async def get_market(
        self,
        *,
        connector_id: str,
        market_id: str,
    ) -> NormalizedMarket:
        markets = await (
            self.market_data_service
            .list_markets(
                connector_id=(
                    connector_id
                ),
                limit=1000,
            )
        )

        for market in markets:
            if (
                market.market_id
                == market_id
            ):
                return market

        raise KeyError(
            "Mercado não encontrado: "
            f"{connector_id}:{market_id}"
        )

    async def compare_keys(
        self,
        *,
        left_connector_id: str,
        left_market_id: str,
        right_connector_id: str,
        right_market_id: str,
    ) -> dict[str, Any]:
        left = await self.get_market(
            connector_id=(
                left_connector_id
            ),
            market_id=(
                left_market_id
            ),
        )

        right = await self.get_market(
            connector_id=(
                right_connector_id
            ),
            market_id=(
                right_market_id
            ),
        )

        score = self.compare(
            left,
            right,
        )

        return {
            "left": self.identity(
                left
            ).to_dict(),
            "right": self.identity(
                right
            ).to_dict(),
            "comparison": score.to_dict(),
            **self._safe_flags(),
        }

    async def candidates(
        self,
        *,
        connector_a: str,
        connector_b: str,
        limit_per_connector: int = 50,
        min_score: float | None = None,
        include_rejected: bool = False,
    ) -> dict[str, Any]:
        if connector_a == connector_b:
            raise ValueError(
                "A comparação exige conectores diferentes."
            )

        normalized_limit = max(
            1,
            min(
                int(
                    limit_per_connector
                ),
                250,
            ),
        )

        threshold = (
            self.candidate_threshold
            if min_score is None
            else max(
                0.0,
                min(
                    1.0,
                    float(min_score),
                ),
            )
        )

        left_markets = await (
            self.market_data_service
            .list_markets(
                connector_id=(
                    connector_a
                ),
                limit=normalized_limit,
            )
        )

        right_markets = await (
            self.market_data_service
            .list_markets(
                connector_id=(
                    connector_b
                ),
                limit=normalized_limit,
            )
        )

        candidates = []

        for left in left_markets:
            for right in right_markets:
                comparison = self.compare(
                    left,
                    right,
                )

                if (
                    not include_rejected
                    and (
                        comparison.status
                        == "REJECTED"
                        or comparison.score
                        < threshold
                    )
                ):
                    continue

                candidates.append(
                    {
                        "left": self.identity(
                            left
                        ).to_dict(),
                        "right": self.identity(
                            right
                        ).to_dict(),
                        "comparison": (
                            comparison.to_dict()
                        ),
                    }
                )

        candidates.sort(
            key=lambda item: (
                item["comparison"][
                    "score"
                ]
            ),
            reverse=True,
        )

        return {
            "connector_a": connector_a,
            "connector_b": connector_b,
            "candidate_threshold": (
                threshold
            ),
            "strong_threshold": (
                self.strong_threshold
            ),
            "compared_pairs": (
                len(left_markets)
                * len(right_markets)
            ),
            "count": len(candidates),
            "candidates": candidates,
            **self._safe_flags(),
        }

    async def confirm_manual_match(
        self,
        *,
        left_connector_id: str,
        left_market_id: str,
        right_connector_id: str,
        right_market_id: str,
        note: str | None = None,
    ) -> dict[str, Any]:
        comparison = await self.compare_keys(
            left_connector_id=(
                left_connector_id
            ),
            left_market_id=(
                left_market_id
            ),
            right_connector_id=(
                right_connector_id
            ),
            right_market_id=(
                right_market_id
            ),
        )

        score = (
            comparison[
                "comparison"
            ]
        )

        if score.get(
            "hard_rejected"
        ) is True:
            raise ValueError(
                "O par foi rejeitado por uma "
                "incompatibilidade estrutural."
            )

        record = self.store.add(
            left_key=(
                comparison["left"][
                    "key"
                ]
            ),
            right_key=(
                comparison["right"][
                    "key"
                ]
            ),
            score=score,
            note=note,
        )

        return {
            "status": "CONFIRMED",
            "match": record,
            "comparison": score,
            "market_data_only": True,
            "mapping_configuration_only": True,
            "read_only_market_access": True,
            "automatic_matching_authorized": False,
            "paper_execution_authorized": False,
            "live_authorization": False,
            "execution_authorized": False,
            "live_execution": False,
            "financial_execution": False,
            "next_step_authorized": False,
        }

    def manual_matches(
        self,
    ) -> dict[str, Any]:
        matches = self.store.list_matches()

        return {
            "count": len(matches),
            "matches": matches,
            "market_data_only": True,
            "mapping_configuration_only": True,
            "read_only": True,
            "automatic_matching_authorized": False,
            "paper_execution_authorized": False,
            "live_authorization": False,
            "execution_authorized": False,
            "live_execution": False,
            "financial_execution": False,
            "next_step_authorized": False,
        }

    def remove_manual_match(
        self,
        match_id: str,
    ) -> dict[str, Any]:
        removed = self.store.remove(
            match_id
        )

        return {
            "status": (
                "REMOVED"
                if removed
                else "NOT_FOUND"
            ),
            "match_id": match_id,
            "removed": removed,
            "market_data_only": True,
            "mapping_configuration_only": True,
            "read_only_market_access": True,
            "automatic_matching_authorized": False,
            "paper_execution_authorized": False,
            "live_authorization": False,
            "execution_authorized": False,
            "live_execution": False,
            "financial_execution": False,
            "next_step_authorized": False,
        }

    def health(
        self,
    ) -> dict[str, Any]:
        matches = self.store.list_matches()

        return {
            "status": "healthy",
            "candidate_threshold": (
                self.candidate_threshold
            ),
            "strong_threshold": (
                self.strong_threshold
            ),
            "manual_matches": len(
                matches
            ),
            "manual_match_path": str(
                self.store.path
            ),
            "manual_confirmation_required": True,
            **self._safe_flags(),
        }


market_matching_service = (
    MarketMatchingService()
)
