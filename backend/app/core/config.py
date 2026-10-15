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
    MOCK_BANK_BASE_URL: str = "http://127.0.0.1:9000"
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

    # Gemini agent
    LLM_PROVIDER: str = "gemini"
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"

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

settings = Settings()
