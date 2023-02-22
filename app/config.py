from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, BaseSettings, PostgresDsn, validator


class _DSN(BaseModel):
    DATABASE: PostgresDsn
    DATABASE_ASYNC: Optional[str] = None

    @validator("DATABASE_ASYNC", pre=True, always=True)
    def get_async_database_dsn(cls, _, values: dict, **kwargs):
        database_dsn = values.get("DATABASE")
        if isinstance(database_dsn, str):
            return database_dsn.replace("postgres", "postgresql+asyncpg", 1)


class _Paths(BaseModel):
    SRC_DIR: Path = Path(__file__, "..").resolve()
    TEMPLATES_DIR: Path = Path(SRC_DIR, "templates")


class Settings(BaseSettings):
    DSN: _DSN
    PATHS: _Paths = _Paths()
    BOT_TOKEN: str
    JINJA_ENVIRONMENT: Environment = Environment(loader=FileSystemLoader(searchpath=PATHS.TEMPLATES_DIR))

    class Config:
        env_nested_delimiter = "__"
        case_sensitive = True


settings = Settings()
