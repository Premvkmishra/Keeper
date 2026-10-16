import hmac
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, AliasChoices

class Settings(BaseSettings):
    APP_ENV: str = "development"
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = Field(default=8000, validation_alias=AliasChoices("PORT", "APP_PORT"))

    # Supabase PostgreSQL connection
    SUPABASE_DB_URL: Optional[str] = None
    ALLOW_LOCAL_SQLITE: bool = False
    SUPABASE_URL: str = "https://amzllkpjwzqjrvudqxie.supabase.co"
    SUPABASE_JWT_SECRET: Optional[str] = None
    # Mock Bank
    MOCK_BANK_DATABASE_PATH: str = "backend/mock_bank/bank.sqlite"
    MOCK_BANK_AUTH_TOKEN: Optional[str] = None

    # ArmorIQ configuration
    ARMORIQ_ENFORCEMENT: str = "required"  # "required" | "optional" | "disabled"
    ARMORIQ_API_KEY: Optional[str] = None
    ARMORIQ_MCP_NAME: str = "keeper-payments"
    ARMORIQ_ROUTE: str = "proxy"  # "proxy" | "decision_gate"
    KEEPER_MCP_PUBLIC_URL: Optional[str] = None
    KEEPER_MCP_INBOUND_SECRET: Optional[str] = None
    ARMORIQ_MCP_KEEPER_PAYMENTS_AUTH_TYPE: str = "bearer"
    ARMORIQ_MCP_KEEPER_PAYMENTS_TOKEN: Optional[str] = None

    # Seed household for local fixtures; runtime MCP access uses signed per-user context.
    MCP_AGENT_HOUSEHOLD_ID: str = "00000000-0000-0000-0000-000000000001"

    # CORS configuration
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://localhost:8080,http://127.0.0.1:5173,http://127.0.0.1:3000,http://127.0.0.1:8080"

    # Agent LLM providers
    LLM_PROVIDER: str = "groq"
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    GROQ_FALLBACK_MODELS: str = "openai/gpt-oss-120b"
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_FALLBACK_MODELS: str = "gemini-2.5-flash-lite,gemini-2.5-pro"

    # Hard ceiling that ordinary human approval cannot override
    HARD_PAYMENT_LIMIT: float = 100000.00

    model_config = SettingsConfigDict(
        env_file=("backend/.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def armoriq_required(self) -> bool:
        return self.ARMORIQ_ENFORCEMENT.lower() not in ("disabled", "optional")

    @property
    def armoriq_mcp_credentials_match(self) -> bool:
        proxy_token = self.ARMORIQ_MCP_KEEPER_PAYMENTS_TOKEN
        inbound_secret = self.KEEPER_MCP_INBOUND_SECRET
        if not proxy_token:
            return True
        return bool(inbound_secret and hmac.compare_digest(proxy_token, inbound_secret))

    @property
    def mock_bank_base_url(self) -> str:
        return f"http://127.0.0.1:{self.APP_PORT}/_internal/mock-bank"

    @property
    def gemini_model_fallbacks(self) -> List[str]:
        configured = (model.strip() for model in self.GEMINI_FALLBACK_MODELS.split(","))
        return list(dict.fromkeys(model for model in configured if model and model != self.GEMINI_MODEL))

    @property
    def groq_model_fallbacks(self) -> List[str]:
        configured = (model.strip() for model in self.GROQ_FALLBACK_MODELS.split(","))
        return list(dict.fromkeys(model for model in configured if model and model != self.GROQ_MODEL))


settings = Settings()
