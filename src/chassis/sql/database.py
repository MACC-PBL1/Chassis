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
    echo=False,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=5,
    max_overflow=10
)

SessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=Engine,
    future=True,
    expire_on_commit=False,
)

Base = declarative_base()