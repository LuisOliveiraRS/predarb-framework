from __future__ import annotations

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações centrais e guardas operacionais do PredArb."""

    APP_NAME: str = "PredArb Framework"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # Banco de dados
    DATABASE_URL: str = "sqlite:///predarb.db"
    DATABASE_ECHO: bool = False

    # Ciclo de vida operacional
    MOCK_CONNECTOR_ENABLED: bool = True
    HYPERLIQUID_CONNECTOR_ENABLED: bool = True
    INITIAL_MARKET_SYNC_ENABLED: bool = True
    SCHEDULER_ENABLED: bool = True
    MARKET_UPDATE_INTERVAL_SECONDS: int = 10
    EXECUTION_WORKER_ENABLED: bool = True
    ROUTER_DASHBOARD_ENABLED: bool = True

    # Hyperliquid
    HYPERLIQUID_API_URL: str = "https://api.hyperliquid.xyz"
    HYPERLIQUID_TIMEOUT_SECONDS: float = 10.0
    HYPERLIQUID_MAX_RETRIES: int = 2
    HYPERLIQUID_RETRY_DELAY_SECONDS: float = 0.25

    # Paper Trading persistente — completamente isolado da execução live
    PAPER_ACCOUNT_ENABLED: bool = True
    PAPER_ACCOUNT_AUTO_LOAD: bool = True
    PAPER_ACCOUNT_AUTO_SAVE: bool = True
    PAPER_ACCOUNT_PATH: str = "paper_data/paper_account.json"
    PAPER_INITIAL_BALANCE: float = 10_000.0

    # Sessão Paper automatizada — início sempre explícito
    PAPER_SESSION_ENABLED: bool = True
    PAPER_SESSION_AUTO_START: bool = False
    PAPER_SESSION_AUTO_LOAD_REPORT: bool = True
    PAPER_SESSION_INTERVAL_SECONDS: float = 30.0
    PAPER_SESSION_STAKE_AMOUNT: float = 250.0
    PAPER_SESSION_MAX_OPPORTUNITIES_PER_CYCLE: int = 1
    PAPER_SESSION_FEE_RATE: float = 0.001
    PAPER_SESSION_REPORT_PATH: str = "paper_data/paper_session_report.json"

    # Limites de risco exclusivos do ambiente Paper
    PAPER_RISK_ENABLED: bool = True
    PAPER_RISK_MAX_TRADE_NOTIONAL: float = 500.0
    PAPER_RISK_MAX_TOTAL_EXPOSURE: float = 2_500.0
    PAPER_RISK_MAX_MARKET_EXPOSURE: float = 1_000.0
    PAPER_RISK_MAX_OPEN_POSITIONS: int = 10
    PAPER_RISK_MAX_DAILY_TRADES: int = 20
    PAPER_RISK_DAILY_LOSS_LIMIT: float = 500.0
    PAPER_RISK_MAX_DRAWDOWN_RATE: float = 0.10
    PAPER_RISK_MIN_ROI: float = 0.0
    PAPER_RISK_MIN_CONFIDENCE: float = 0.0
    PAPER_RISK_MAX_RISK_SCORE: float = 100.0

    # AI — análise consultiva
    AI_ENABLED: bool = True
    AI_PIPELINE_ENABLED: bool = True
    AI_STRICT_FEATURES: bool = False
    AI_FAIL_ON_ERROR: bool = False

    # Guardas operacionais permanentes
    AI_ADVISORY_ONLY: bool = True
    AI_EXECUTION_AUTHORIZED: bool = False
    AI_AUTO_LOAD_MODEL: bool = False

    # Registro e artefatos
    AI_MODEL_NAME: str = "opportunity"
    AI_MODEL_ROOT: str = "model_artifacts"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @model_validator(mode="after")
    def validate_settings(self) -> "Settings":
        if not self.AI_ADVISORY_ONLY:
            raise ValueError("AI_ADVISORY_ONLY deve permanecer habilitado.")
        if self.AI_EXECUTION_AUTHORIZED:
            raise ValueError(
                "AI_EXECUTION_AUTHORIZED deve permanecer desabilitado."
            )
        if self.AI_AUTO_LOAD_MODEL:
            raise ValueError("AI_AUTO_LOAD_MODEL não é suportado por segurança.")

        self.PAPER_ACCOUNT_PATH = str(
            self.PAPER_ACCOUNT_PATH or "paper_data/paper_account.json"
        ).strip()
        self.PAPER_SESSION_REPORT_PATH = str(
            self.PAPER_SESSION_REPORT_PATH or "paper_data/paper_session_report.json"
        ).strip()
        self.AI_MODEL_NAME = str(self.AI_MODEL_NAME or "opportunity").strip()
        self.AI_MODEL_ROOT = str(self.AI_MODEL_ROOT or "model_artifacts").strip()
        self.DATABASE_URL = str(self.DATABASE_URL or "").strip()
        self.HYPERLIQUID_API_URL = str(self.HYPERLIQUID_API_URL or "").strip()

        if not self.PAPER_ACCOUNT_PATH:
            raise ValueError("PAPER_ACCOUNT_PATH não pode ser vazio.")
        if not self.PAPER_ACCOUNT_PATH.lower().endswith(".json"):
            raise ValueError("PAPER_ACCOUNT_PATH deve apontar para um arquivo .json.")
        if self.PAPER_INITIAL_BALANCE <= 0:
            raise ValueError("PAPER_INITIAL_BALANCE deve ser positivo.")
        if self.PAPER_SESSION_AUTO_START:
            raise ValueError(
                "PAPER_SESSION_AUTO_START deve permanecer desabilitado; "
                "o início da sessão exige confirmação explícita."
            )
        if not self.PAPER_SESSION_REPORT_PATH.lower().endswith(".json"):
            raise ValueError("PAPER_SESSION_REPORT_PATH deve apontar para .json.")
        if self.PAPER_SESSION_INTERVAL_SECONDS < 1:
            raise ValueError("PAPER_SESSION_INTERVAL_SECONDS deve ser pelo menos 1.")
        if self.PAPER_SESSION_STAKE_AMOUNT <= 0:
            raise ValueError("PAPER_SESSION_STAKE_AMOUNT deve ser positivo.")
        if self.PAPER_SESSION_MAX_OPPORTUNITIES_PER_CYCLE <= 0:
            raise ValueError(
                "PAPER_SESSION_MAX_OPPORTUNITIES_PER_CYCLE deve ser positivo."
            )
        if self.PAPER_SESSION_FEE_RATE < 0:
            raise ValueError("PAPER_SESSION_FEE_RATE não pode ser negativo.")
        for field_name in (
            "PAPER_RISK_MAX_TRADE_NOTIONAL",
            "PAPER_RISK_MAX_TOTAL_EXPOSURE",
            "PAPER_RISK_MAX_MARKET_EXPOSURE",
            "PAPER_RISK_DAILY_LOSS_LIMIT",
        ):
            if float(getattr(self, field_name)) <= 0:
                raise ValueError(f"{field_name} deve ser positivo.")
        if self.PAPER_RISK_MAX_OPEN_POSITIONS <= 0:
            raise ValueError("PAPER_RISK_MAX_OPEN_POSITIONS deve ser positivo.")
        if self.PAPER_RISK_MAX_DAILY_TRADES <= 0:
            raise ValueError("PAPER_RISK_MAX_DAILY_TRADES deve ser positivo.")
        if not 0 < self.PAPER_RISK_MAX_DRAWDOWN_RATE <= 1:
            raise ValueError(
                "PAPER_RISK_MAX_DRAWDOWN_RATE deve estar entre 0 e 1."
            )
        if not 0 <= self.PAPER_RISK_MIN_CONFIDENCE <= 1:
            raise ValueError("PAPER_RISK_MIN_CONFIDENCE deve estar entre 0 e 1.")
        if not 0 <= self.PAPER_RISK_MAX_RISK_SCORE <= 100:
            raise ValueError("PAPER_RISK_MAX_RISK_SCORE deve estar entre 0 e 100.")
        if not self.AI_MODEL_NAME:
            raise ValueError("AI_MODEL_NAME não pode ser vazio.")
        if not self.AI_MODEL_ROOT:
            raise ValueError("AI_MODEL_ROOT não pode ser vazio.")
        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL não pode ser vazio.")
        if self.HYPERLIQUID_CONNECTOR_ENABLED and not self.HYPERLIQUID_API_URL:
            raise ValueError(
                "HYPERLIQUID_API_URL é obrigatório quando o conector está ativo."
            )
        if self.MARKET_UPDATE_INTERVAL_SECONDS <= 0:
            raise ValueError("MARKET_UPDATE_INTERVAL_SECONDS deve ser positivo.")
        if self.HYPERLIQUID_TIMEOUT_SECONDS <= 0:
            raise ValueError("HYPERLIQUID_TIMEOUT_SECONDS deve ser positivo.")
        if self.HYPERLIQUID_MAX_RETRIES < 0:
            raise ValueError("HYPERLIQUID_MAX_RETRIES não pode ser negativo.")
        if self.HYPERLIQUID_RETRY_DELAY_SECONDS < 0:
            raise ValueError(
                "HYPERLIQUID_RETRY_DELAY_SECONDS não pode ser negativo."
            )

        return self


settings = Settings()
