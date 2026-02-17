from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Use full database URL or individual components
    database_url: Optional[str] = None  # Will be set from env var or built from components
    
    # Fallback to individual components if DATABASE_URL not provided
    postgres_user: str = "user"
    postgres_password: str = "pass"
    postgres_db: str = "appdb"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    
    feature_flag_url: str = ""
    feature_flag_api_key: str = ""
    
    class Config:
        env_file = ".env"
    
    def get_database_url(self) -> str:
        """Get database URL, preferring DATABASE_URL if set"""
        if self.database_url:
            return self.database_url
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

settings = Settings()
