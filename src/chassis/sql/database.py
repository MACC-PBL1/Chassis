from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine, 
)
from sqlalchemy.orm import declarative_base
import os

SQLALCHEMY_DATABASE_URL = os.getenv(
    'SQLALCHEMY_DATABASE_URL',
    "sqlite+aiosqlite:///./database.db"
)

Engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    # connect_args={"check_same_thread": False},
    echo=False
)

SessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=Engine,
    future=True
)

Base = declarative_base()