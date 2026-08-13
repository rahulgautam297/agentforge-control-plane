from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = (
        "postgresql+psycopg://agentforge:agentforge_dev_password@localhost:5432/agentforge"
    )
    execution_role_password: str = "execution_dev_password"
    dev_bearer_token: str = "dev-local-token"
    cors_origins: str = "http://localhost:3000"

    # Deterministic Phase-1 auth-shim identities. Seeded as data by the
    # 0001_initial_schema migration.
    default_tenant_id: str = "00000000-0000-0000-0000-000000000001"
    default_user_id: str = "00000000-0000-0000-0000-000000000002"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
