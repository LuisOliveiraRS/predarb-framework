from __future__ import annotations

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações centrais e guardas operacionais do PredArb."""

    APP_NAME: str = "PredArb Framework"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # Fase 13B - autenticacao Supabase
    AUTH_ENABLED: bool = False
    AUTH_REQUIRED_FOR_DASHBOARD: bool = False
    AUTH_REQUIRE_MFA_FOR_OPERATIONS: bool = True

    AUTH_ACCESS_COOKIE_NAME: str = "predarb_access_token"
    AUTH_REFRESH_COOKIE_NAME: str = "predarb_refresh_token"
    AUTH_COOKIE_SECURE: bool = True
    AUTH_COOKIE_SAMESITE: str = "strict"
    AUTH_REFRESH_COOKIE_MAX_AGE_SECONDS: int = 2592000
    AUTH_LOGIN_PATH: str = "/login"
    AUTH_AFTER_LOGIN_PATH: str = "/dashboard"

    SUPABASE_URL: str = ""
    SUPABASE_PUBLISHABLE_KEY: str = ""
    SUPABASE_JWT_AUDIENCE: str = "authenticated"
    SUPABASE_JWT_ALGORITHMS: str = "ES256,RS256"
    SUPABASE_JWKS_CACHE_TTL_SECONDS: int = 600

    # Banco de dados
    DATABASE_URL: str = "sqlite:///predarb.db"
    DATABASE_ECHO: bool = False

    # Fase 16 - cache de coletas reais
    REAL_OPPORTUNITY_CACHE_TTL_SECONDS: float = 45.0
    REAL_OPPORTUNITY_PERSISTENCE_ENABLED: bool = False
    REAL_OPPORTUNITY_DATABASE_URL: str = ""
    REAL_OPPORTUNITY_PERSISTENCE_HISTORY_LIMIT: int = 60

    # Fase 17 - coletor automatico do Radar Real
    REAL_OPPORTUNITY_BACKGROUND_COLLECTOR_ENABLED: bool = False
    REAL_OPPORTUNITY_BACKGROUND_INTERVAL_SECONDS: int = 60
    REAL_OPPORTUNITY_BACKGROUND_LIMIT_PER_CONNECTOR: int = 20
    REAL_OPPORTUNITY_BACKGROUND_FEE_BUFFER: float = 0.02
    REAL_OPPORTUNITY_BACKGROUND_NEAR_THRESHOLD: float = 0.05
    REAL_OPPORTUNITY_BACKGROUND_CONCURRENCY: int = 8
    REAL_OPPORTUNITY_SNAPSHOT_MAX_AGE_MULTIPLIER: int = 3
    REAL_OPPORTUNITY_FORCE_REFRESH_COOLDOWN_SECONDS: int = 30

    # Fase 20B - coletor do scanner cripto CEX-CEX.
    # Valores Decimal ficam como str de proposito: o dominio
    # cripto recusa float em valor financeiro (secao 28).
    CRYPTO_SCANNER_ENABLED: bool = False
    CRYPTO_SCANNER_INTERVAL_SECONDS: int = 60
    CRYPTO_SCANNER_VENUES: str = "BINANCE,OKX,BYBIT"
    CRYPTO_SCANNER_BASE_ASSET: str = "BTC"
    CRYPTO_SCANNER_QUOTE_ASSET: str = "USDT"
    CRYPTO_SCANNER_QUANTITY: str = "0.01"
    CRYPTO_SCANNER_DEPTH: int = 50
    CRYPTO_SCANNER_MAX_BOOK_AGE_MS: int = 5000
    CRYPTO_SCANNER_SLIPPAGE_RATIO: str = "0.0005"
    CRYPTO_SCANNER_SAFETY_BUFFER_RATIO: str = "0.0005"
    CRYPTO_SCANNER_MINIMUM_NET_PROFIT: str = "0"
    CRYPTO_SCANNER_MINIMUM_ROI: str = "0"
    CRYPTO_SCANNER_TAKER_FEES: str = (
        "BINANCE:0.001,OKX:0.001,BYBIT:0.001"
    )
    CRYPTO_SCANNER_REQUEST_TIMEOUT_SECONDS: int = 10
    CRYPTO_SCANNER_RATE_LIMIT_CAPACITY: int = 10
    CRYPTO_SCANNER_RATE_LIMIT_REFILL_PER_SECOND: str = "5"

    # Ciclo de vida operacional
    MOCK_CONNECTOR_ENABLED: bool = True
    HYPERLIQUID_CONNECTOR_ENABLED: bool = True
    INITIAL_MARKET_SYNC_ENABLED: bool = True
    SCHEDULER_ENABLED: bool = True
    MARKET_UPDATE_INTERVAL_SECONDS: int = 10
    EXECUTION_WORKER_ENABLED: bool = True
    ROUTER_DASHBOARD_ENABLED: bool = True

    # Fase 12A ? CORS p?blico restrito
    PUBLIC_CORS_ENABLED: bool = False
    PUBLIC_CORS_ALLOWED_ORIGINS: str = ""
    PUBLIC_CORS_ALLOW_CREDENTIALS: bool = False

    # Fase 9F ? Shadow Runtime operacional
    SHADOW_RUNTIME_ENABLED: bool = True
    SHADOW_RUNTIME_SCHEDULER_ENABLED: bool = False
    SHADOW_RUNTIME_INTERVAL_SECONDS: int = 60
    SHADOW_RUNTIME_MAX_OPPORTUNITIES_PER_CYCLE: int = 10
    SHADOW_RUNTIME_FORCE_REFRESH: bool = False
    SHADOW_RUNTIME_PERSIST_AUDIT: bool = False

    # Hyperliquid
    HYPERLIQUID_API_URL: str = "https://api.hyperliquid.xyz"
    HYPERLIQUID_TIMEOUT_SECONDS: float = 10.0
    HYPERLIQUID_MAX_RETRIES: int = 2
    HYPERLIQUID_RETRY_DELAY_SECONDS: float = 0.25

    # Fase 10B ? execu??o isolada em testnet
    HYPERLIQUID_TESTNET_API_URL: str = (
        "https://api.hyperliquid-testnet.xyz"
    )
    HYPERLIQUID_TESTNET_EXECUTION_ENABLED: bool = False
    HYPERLIQUID_TESTNET_EXECUTION_AUTHORIZED: bool = False
    HYPERLIQUID_TESTNET_MAX_ORDER_NOTIONAL: float = 10.0

    # Mainnet permanece permanentemente bloqueada nesta fase
    HYPERLIQUID_MAINNET_EXECUTION_ENABLED: bool = False
    HYPERLIQUID_MAINNET_EXECUTION_AUTHORIZED: bool = False

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

        self.SUPABASE_URL = str(
            self.SUPABASE_URL or ""
        ).strip().rstrip("/")

        self.SUPABASE_PUBLISHABLE_KEY = str(
            self.SUPABASE_PUBLISHABLE_KEY or ""
        ).strip()

        self.SUPABASE_JWT_AUDIENCE = str(
            self.SUPABASE_JWT_AUDIENCE or ""
        ).strip()

        jwt_algorithms = [
            algorithm.strip()
            for algorithm in str(
                self.SUPABASE_JWT_ALGORITHMS or ""
            ).split(",")
            if algorithm.strip()
        ]

        allowed_algorithms = {
            "ES256",
            "RS256",
            "EdDSA",
        }

        unsupported_algorithms = sorted(
            set(jwt_algorithms) - allowed_algorithms
        )

        if not jwt_algorithms:
            raise ValueError(
                "SUPABASE_JWT_ALGORITHMS nao pode ficar vazio."
            )

        if unsupported_algorithms:
            raise ValueError(
                "Algoritmos JWT nao autorizados: "
                + ", ".join(unsupported_algorithms)
            )

        self.SUPABASE_JWT_ALGORITHMS = ",".join(
            jwt_algorithms
        )

        self.AUTH_ACCESS_COOKIE_NAME = str(
            self.AUTH_ACCESS_COOKIE_NAME or ""
        ).strip()

        self.AUTH_REFRESH_COOKIE_NAME = str(
            self.AUTH_REFRESH_COOKIE_NAME or ""
        ).strip()

        self.AUTH_COOKIE_SAMESITE = str(
            self.AUTH_COOKIE_SAMESITE or ""
        ).strip().lower()

        for cookie_name in (
            self.AUTH_ACCESS_COOKIE_NAME,
            self.AUTH_REFRESH_COOKIE_NAME,
        ):
            invalid_cookie_name = (
                not cookie_name
                or any(
                    character.isspace()
                    or character in ";,"
                    for character in cookie_name
                )
            )

            if invalid_cookie_name:
                raise ValueError(
                    "Nomes dos cookies Auth sao invalidos."
                )

        if (
            self.AUTH_ACCESS_COOKIE_NAME
            == self.AUTH_REFRESH_COOKIE_NAME
        ):
            raise ValueError(
                "Os cookies de acesso e renovacao "
                "devem possuir nomes diferentes."
            )

        if self.AUTH_COOKIE_SAMESITE not in {
            "strict",
            "lax",
        }:
            raise ValueError(
                "AUTH_COOKIE_SAMESITE deve ser strict ou lax."
            )

        if not (
            3600
            <= self.AUTH_REFRESH_COOKIE_MAX_AGE_SECONDS
            <= 7776000
        ):
            raise ValueError(
                "AUTH_REFRESH_COOKIE_MAX_AGE_SECONDS "
                "deve ficar entre 3600 e 7776000."
            )

        self.AUTH_LOGIN_PATH = str(
            self.AUTH_LOGIN_PATH or ""
        ).strip()

        self.AUTH_AFTER_LOGIN_PATH = str(
            self.AUTH_AFTER_LOGIN_PATH or ""
        ).strip()

        for auth_path in (
            self.AUTH_LOGIN_PATH,
            self.AUTH_AFTER_LOGIN_PATH,
        ):
            if (
                not auth_path.startswith("/")
                or auth_path.startswith("//")
                or "://" in auth_path
            ):
                raise ValueError(
                    "AUTH_LOGIN_PATH e AUTH_AFTER_LOGIN_PATH "
                    "devem ser caminhos locais."
                )

        if (
            self.AUTH_ENABLED
            and not self.DEBUG
            and not self.AUTH_COOKIE_SECURE
        ):
            raise ValueError(
                "Cookies Auth devem usar Secure em producao."
            )

        if not (
            60
            <= self.SUPABASE_JWKS_CACHE_TTL_SECONDS
            <= 600
        ):
            raise ValueError(
                "SUPABASE_JWKS_CACHE_TTL_SECONDS "
                "deve ficar entre 60 e 600."
            )

        if (
            self.AUTH_REQUIRED_FOR_DASHBOARD
            and not self.AUTH_ENABLED
        ):
            raise ValueError(
                "AUTH_REQUIRED_FOR_DASHBOARD exige AUTH_ENABLED."
            )

        if self.AUTH_ENABLED:
            if not self.SUPABASE_URL:
                raise ValueError(
                    "AUTH_ENABLED exige SUPABASE_URL."
                )

            if not self.SUPABASE_PUBLISHABLE_KEY:
                raise ValueError(
                    "AUTH_ENABLED exige "
                    "SUPABASE_PUBLISHABLE_KEY."
                )

            if not self.SUPABASE_JWT_AUDIENCE:
                raise ValueError(
                    "SUPABASE_JWT_AUDIENCE nao pode ficar vazio."
                )

            if self.DEBUG:
                valid_url = self.SUPABASE_URL.startswith(
                    ("https://", "http://")
                )
            else:
                valid_url = self.SUPABASE_URL.startswith(
                    "https://"
                )

            if not valid_url:
                raise ValueError(
                    "SUPABASE_URL deve utilizar HTTPS "
                    "fora do ambiente DEBUG."
                )

        self._validate_crypto_scanner()

        self.PUBLIC_CORS_ALLOWED_ORIGINS = str(
            self.PUBLIC_CORS_ALLOWED_ORIGINS or ""
        ).strip()

        cors_origins = [
            origin.strip().rstrip("/")
            for origin in self.PUBLIC_CORS_ALLOWED_ORIGINS.split(",")
            if origin.strip()
        ]

        if "*" in cors_origins:
            raise ValueError(
                "PUBLIC_CORS_ALLOWED_ORIGINS nao permite curinga."
            )

        if self.PUBLIC_CORS_ALLOW_CREDENTIALS:
            raise ValueError(
                "Credenciais CORS permanecem bloqueadas nesta fase."
            )

        if self.PUBLIC_CORS_ENABLED and not cors_origins:
            raise ValueError(
                "CORS habilitado exige ao menos uma origem autorizada."
            )

        for origin in cors_origins:
            if not origin.startswith(("https://", "http://")):
                raise ValueError(
                    "Toda origem CORS deve usar http:// ou https://."
                )

        self.PUBLIC_CORS_ALLOWED_ORIGINS = ",".join(cors_origins)

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

        self.HYPERLIQUID_TESTNET_API_URL = str(
            self.HYPERLIQUID_TESTNET_API_URL or ""
        ).strip().rstrip("/")

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
        if not (
            5.0
            <= float(
                self.REAL_OPPORTUNITY_CACHE_TTL_SECONDS
            )
            <= 300.0
        ):
            raise ValueError(
                "REAL_OPPORTUNITY_CACHE_TTL_SECONDS "
                "deve ficar entre 5 e 300 segundos."
            )

        self.REAL_OPPORTUNITY_DATABASE_URL = str(
            self.REAL_OPPORTUNITY_DATABASE_URL or ""
        ).strip()

        if (
            self.REAL_OPPORTUNITY_PERSISTENCE_ENABLED
            and not self.REAL_OPPORTUNITY_DATABASE_URL
        ):
            raise ValueError(
                "REAL_OPPORTUNITY_PERSISTENCE_ENABLED "
                "exige REAL_OPPORTUNITY_DATABASE_URL."
            )

        if (
            self.REAL_OPPORTUNITY_DATABASE_URL
            and not self.REAL_OPPORTUNITY_DATABASE_URL.startswith(
                (
                    "sqlite://",
                    "postgres://",
                    "postgresql://",
                    "postgresql+psycopg://",
                )
            )
        ):
            raise ValueError(
                "REAL_OPPORTUNITY_DATABASE_URL possui "
                "um protocolo nao autorizado."
            )

        if not (
            1
            <= int(
                self.REAL_OPPORTUNITY_PERSISTENCE_HISTORY_LIMIT
            )
            <= 1440
        ):
            raise ValueError(
                "REAL_OPPORTUNITY_PERSISTENCE_"
                "HISTORY_LIMIT deve ficar entre "
                "1 e 1440."
            )

        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL não pode ser vazio.")
        if self.HYPERLIQUID_CONNECTOR_ENABLED and not self.HYPERLIQUID_API_URL:
            raise ValueError(
                "HYPERLIQUID_API_URL é obrigatório quando o conector está ativo."
            )
        if not (
            30
            <= int(
                self.REAL_OPPORTUNITY_BACKGROUND_INTERVAL_SECONDS
            )
            <= 3600
        ):
            raise ValueError(
                "REAL_OPPORTUNITY_BACKGROUND_INTERVAL_SECONDS "
                "deve ficar entre 30 e 3600 segundos."
            )

        if not (
            1
            <= int(
                self.REAL_OPPORTUNITY_BACKGROUND_LIMIT_PER_CONNECTOR
            )
            <= 100
        ):
            raise ValueError(
                "REAL_OPPORTUNITY_BACKGROUND_LIMIT_PER_CONNECTOR "
                "deve ficar entre 1 e 100."
            )

        for field_name in (
            "REAL_OPPORTUNITY_BACKGROUND_FEE_BUFFER",
            "REAL_OPPORTUNITY_BACKGROUND_NEAR_THRESHOLD",
        ):
            value = float(getattr(self, field_name))

            if not 0.0 <= value <= 0.25:
                raise ValueError(
                    f"{field_name} deve ficar entre 0 e 0.25."
                )

        if not (
            1
            <= int(
                self.REAL_OPPORTUNITY_BACKGROUND_CONCURRENCY
            )
            <= 20
        ):
            raise ValueError(
                "REAL_OPPORTUNITY_BACKGROUND_CONCURRENCY "
                "deve ficar entre 1 e 20."
            )

        if not (
            1
            <= int(
                self.REAL_OPPORTUNITY_SNAPSHOT_MAX_AGE_MULTIPLIER
            )
            <= 10
        ):
            raise ValueError(
                "REAL_OPPORTUNITY_SNAPSHOT_MAX_AGE_MULTIPLIER "
                "deve ficar entre 1 e 10."
            )

        if not (
            0
            <= int(
                self
                .REAL_OPPORTUNITY_FORCE_REFRESH_COOLDOWN_SECONDS
            )
            <= 3600
        ):
            raise ValueError(
                "REAL_OPPORTUNITY_FORCE_REFRESH_COOLDOWN_SECONDS "
                "deve ficar entre 0 e 3600 segundos."
            )

        if (
            self.REAL_OPPORTUNITY_BACKGROUND_COLLECTOR_ENABLED
            and not self.SCHEDULER_ENABLED
        ):
            raise ValueError(
                "O coletor automatico do Radar exige "
                "SCHEDULER_ENABLED."
            )

        if self.MARKET_UPDATE_INTERVAL_SECONDS <= 0:
            raise ValueError("MARKET_UPDATE_INTERVAL_SECONDS deve ser positivo.")

        if self.SHADOW_RUNTIME_INTERVAL_SECONDS < 10:
            raise ValueError(
                "SHADOW_RUNTIME_INTERVAL_SECONDS deve ser "
                "pelo menos 10 segundos."
            )

        if (
            self.SHADOW_RUNTIME_MAX_OPPORTUNITIES_PER_CYCLE
            <= 0
        ):
            raise ValueError(
                "SHADOW_RUNTIME_MAX_OPPORTUNITIES_PER_CYCLE "
                "deve ser positivo."
            )

        if (
            self.SHADOW_RUNTIME_SCHEDULER_ENABLED
            and not self.SHADOW_RUNTIME_ENABLED
        ):
            raise ValueError(
                "SHADOW_RUNTIME_ENABLED deve permanecer ativo "
                "quando o scheduler Shadow estiver habilitado."
            )

        if (
            self.SHADOW_RUNTIME_SCHEDULER_ENABLED
            and not self.SCHEDULER_ENABLED
        ):
            raise ValueError(
                "SCHEDULER_ENABLED deve permanecer ativo "
                "quando o scheduler Shadow estiver habilitado."
            )

        if self.SHADOW_RUNTIME_PERSIST_AUDIT:
            raise ValueError(
                "SHADOW_RUNTIME_PERSIST_AUDIT deve permanecer "
                "desabilitado; persistencia exige acao explicita."
            )

        official_testnet_url = "https://api.hyperliquid-testnet.xyz"

        if self.HYPERLIQUID_MAINNET_EXECUTION_ENABLED:
            raise ValueError(
                "Execucao Hyperliquid mainnet deve permanecer desabilitada."
            )

        if self.HYPERLIQUID_MAINNET_EXECUTION_AUTHORIZED:
            raise ValueError(
                "Autorizacao Hyperliquid mainnet deve permanecer desabilitada."
            )

        if self.HYPERLIQUID_TESTNET_API_URL != official_testnet_url:
            raise ValueError(
                "HYPERLIQUID_TESTNET_API_URL deve apontar para a testnet oficial."
            )

        if (
            self.HYPERLIQUID_TESTNET_EXECUTION_AUTHORIZED
            and not self.HYPERLIQUID_TESTNET_EXECUTION_ENABLED
        ):
            raise ValueError(
                "A autorizacao testnet exige que a execucao testnet esteja ativa."
            )

        if self.HYPERLIQUID_TESTNET_MAX_ORDER_NOTIONAL <= 0:
            raise ValueError(
                "HYPERLIQUID_TESTNET_MAX_ORDER_NOTIONAL deve ser positivo."
            )

        if self.HYPERLIQUID_TIMEOUT_SECONDS <= 0:
            raise ValueError("HYPERLIQUID_TIMEOUT_SECONDS deve ser positivo.")
        if self.HYPERLIQUID_MAX_RETRIES < 0:
            raise ValueError("HYPERLIQUID_MAX_RETRIES não pode ser negativo.")
        if self.HYPERLIQUID_RETRY_DELAY_SECONDS < 0:
            raise ValueError(
                "HYPERLIQUID_RETRY_DELAY_SECONDS não pode ser negativo."
            )

        return self

    def _validate_crypto_scanner(self) -> None:
        """Valida a Fase 20B, fail-closed.

        Configuracao invalida impede o boot em vez de degradar em
        silencio: um scanner rodando com parametro errado produz
        oportunidade fantasma, que e pior do que scanner parado.
        """

        self.CRYPTO_SCANNER_VENUES = str(
            self.CRYPTO_SCANNER_VENUES or ""
        ).strip().upper()

        venues = [
            item.strip()
            for item in self.CRYPTO_SCANNER_VENUES.split(",")
            if item.strip()
        ]

        if self.CRYPTO_SCANNER_ENABLED and len(venues) < 2:
            raise ValueError(
                "CRYPTO_SCANNER_ENABLED exige ao menos duas "
                "venues: arbitragem espacial compara venues."
            )

        if not (
            30
            <= self.CRYPTO_SCANNER_INTERVAL_SECONDS
            <= 3600
        ):
            raise ValueError(
                "CRYPTO_SCANNER_INTERVAL_SECONDS deve ficar "
                "entre 30 e 3600."
            )

        if not 1 <= self.CRYPTO_SCANNER_DEPTH <= 500:
            raise ValueError(
                "CRYPTO_SCANNER_DEPTH deve ficar entre 1 e 500."
            )

        if not (
            100
            <= self.CRYPTO_SCANNER_MAX_BOOK_AGE_MS
            <= 600000
        ):
            raise ValueError(
                "CRYPTO_SCANNER_MAX_BOOK_AGE_MS deve ficar "
                "entre 100 e 600000."
            )

        if self.CRYPTO_SCANNER_REQUEST_TIMEOUT_SECONDS <= 0:
            raise ValueError(
                "CRYPTO_SCANNER_REQUEST_TIMEOUT_SECONDS deve "
                "ser positivo."
            )

        if self.CRYPTO_SCANNER_RATE_LIMIT_CAPACITY <= 0:
            raise ValueError(
                "CRYPTO_SCANNER_RATE_LIMIT_CAPACITY deve ser "
                "positivo."
            )

        for name in (
            "CRYPTO_SCANNER_BASE_ASSET",
            "CRYPTO_SCANNER_QUOTE_ASSET",
        ):
            value = str(
                getattr(self, name) or ""
            ).strip().upper()

            if not value:
                raise ValueError(f"{name} nao pode ficar vazio.")

            setattr(self, name, value)

        if (
            self.CRYPTO_SCANNER_BASE_ASSET
            == self.CRYPTO_SCANNER_QUOTE_ASSET
        ):
            raise ValueError(
                "CRYPTO_SCANNER_BASE_ASSET e "
                "CRYPTO_SCANNER_QUOTE_ASSET devem diferir."
            )

        self._validate_crypto_decimals()
        self._validate_crypto_fees(venues)

    def _validate_crypto_decimals(self) -> None:
        from decimal import Decimal, InvalidOperation

        limits = {
            "CRYPTO_SCANNER_QUANTITY": (
                Decimal("0"),
                None,
                False,
            ),
            "CRYPTO_SCANNER_SLIPPAGE_RATIO": (
                Decimal("0"),
                Decimal("0.25"),
                True,
            ),
            "CRYPTO_SCANNER_SAFETY_BUFFER_RATIO": (
                Decimal("0"),
                Decimal("0.25"),
                True,
            ),
            "CRYPTO_SCANNER_MINIMUM_NET_PROFIT": (
                Decimal("0"),
                None,
                True,
            ),
            "CRYPTO_SCANNER_MINIMUM_ROI": (
                Decimal("0"),
                Decimal("1"),
                True,
            ),
            "CRYPTO_SCANNER_RATE_LIMIT_REFILL_PER_SECOND": (
                Decimal("0"),
                None,
                False,
            ),
        }

        for name, (
            minimum,
            maximum,
            allow_equal,
        ) in limits.items():
            raw = str(getattr(self, name) or "").strip()

            try:
                value = Decimal(raw)
            except (InvalidOperation, ValueError) as exc:
                raise ValueError(
                    f"{name} nao e um numero decimal valido."
                ) from exc

            if not value.is_finite():
                raise ValueError(f"{name} deve ser finito.")

            if allow_equal and value < minimum:
                raise ValueError(
                    f"{name} nao pode ser menor que {minimum}."
                )

            if not allow_equal and value <= minimum:
                raise ValueError(
                    f"{name} deve ser maior que {minimum}."
                )

            if maximum is not None and value > maximum:
                raise ValueError(
                    f"{name} nao pode ser maior que {maximum}."
                )

            setattr(self, name, raw)

    def _validate_crypto_fees(
        self,
        venues: list[str],
    ) -> None:
        """Taxas vem de configuracao, nunca hardcoded.

        Secao 9: taxas variam por conta, tier, produto, par e
        regiao. Aqui elas sao versionadas e conservadoras ate a
        Fase 25 trazer a taxa efetiva por conta.
        """

        from decimal import Decimal, InvalidOperation

        self.CRYPTO_SCANNER_TAKER_FEES = str(
            self.CRYPTO_SCANNER_TAKER_FEES or ""
        ).strip().upper()

        parsed: dict[str, str] = {}

        for entry in self.CRYPTO_SCANNER_TAKER_FEES.split(","):
            item = entry.strip()

            if not item:
                continue

            if ":" not in item:
                raise ValueError(
                    "CRYPTO_SCANNER_TAKER_FEES usa o formato "
                    "VENUE:taxa separado por virgula."
                )

            venue_id, _, raw_rate = item.partition(":")
            venue_id = venue_id.strip()

            try:
                rate = Decimal(raw_rate.strip())
            except (InvalidOperation, ValueError) as exc:
                raise ValueError(
                    f"Taxa invalida para {venue_id} em "
                    "CRYPTO_SCANNER_TAKER_FEES."
                ) from exc

            if not Decimal("0") <= rate <= Decimal("0.25"):
                raise ValueError(
                    f"Taxa de {venue_id} fora do intervalo "
                    "aceitavel (0 a 0.25)."
                )

            parsed[venue_id] = raw_rate.strip()

        if not self.CRYPTO_SCANNER_ENABLED:
            return

        faltando = [
            venue for venue in venues if venue not in parsed
        ]

        if faltando:
            raise ValueError(
                "CRYPTO_SCANNER_TAKER_FEES nao cobre "
                f"{', '.join(faltando)}. Taxa desconhecida "
                "invalida a oportunidade (invariante 15)."
            )


settings = Settings()
