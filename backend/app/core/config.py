"""
Application configuration using Pydantic Settings.
Loads configuration from environment variables and .env file.
"""

from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application Settings
    app_name: str = "Virtual Workspace Platform"
    app_env: str = "development"
    secret_key: str = "change-me-in-production"
    debug: bool = True
    
    # Server Settings
    host: str = "0.0.0.0"
    port: int = 8000
    frontend_url: str = "http://localhost:3000"
    
    # Database
    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    
    # GitHub OAuth
    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = "http://localhost:8000/auth/github/callback"
    
    # JWT Settings
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    
    # Admin Settings
    admin_github_usernames: str = ""
    
    @property
    def admin_usernames_list(self) -> List[str]:
        """Parse comma-separated admin usernames into a list."""
        if not self.admin_github_usernames:
            return []
        return [u.strip() for u in self.admin_github_usernames.split(",") if u.strip()]
    
    # Container Defaults
    default_cpu_limit: float = 1.0
    default_memory_limit: int = 1024  # MB
    default_disk_limit: int = 5  # GB
    default_max_runtime: int = 3600  # seconds
    
    # Docker Settings
    docker_network: str = "workspace-network"
    workspace_image: str = "workspace-dev:latest"
    
    # Proxy Settings
    proxy_domain: str = "localhost"


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Uses lru_cache to ensure settings are only loaded once.
    """
    return Settings()
