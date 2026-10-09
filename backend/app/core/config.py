import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Settings:
    env: str
    demo_mode: bool
    host: str
    port: int
    database_path: str
    llm_api_key: str
    llm_provider: str
    llm_model: str
    llm_base_url: str
    oidc_issuer: str
    oidc_audience: str
    oidc_jwks_url: str

    @classmethod
    def load(cls) -> "Settings":
        env = os.environ.get("ENV", "development").lower()
        demo_mode_val = os.environ.get("DEMO_MODE", "true").lower() in ("true", "1", "yes")

        # Refuse demo mode in production
        if env == "production" and demo_mode_val:
            raise RuntimeError("Demo mode is strictly prohibited in production environment.")

        return cls(
            env=env,
            demo_mode=demo_mode_val,
            host=os.environ.get("HOST", "127.0.0.1"),
            port=int(os.environ.get("PORT", "8000")),
            database_path=os.environ.get("DATABASE_PATH", "data/code_review.db"),
            llm_api_key=os.environ.get("LLM_API_KEY", "").strip(),
            llm_provider=os.environ.get("LLM_PROVIDER", "openai").lower(),
            llm_model=os.environ.get("LLM_MODEL", "gpt-4o"),
            llm_base_url=os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1"),
            oidc_issuer=os.environ.get("OIDC_ISSUER", "http://127.0.0.1:8080/realms/code-review-realm"),
            oidc_audience=os.environ.get("OIDC_AUDIENCE", "code-review-client"),
            oidc_jwks_url=os.environ.get("OIDC_JWKS_URL", "http://127.0.0.1:8080/realms/code-review-realm/protocol/openid-connect/certs"),
        )


settings = Settings.load()
