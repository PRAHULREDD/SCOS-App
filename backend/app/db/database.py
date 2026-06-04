import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

# Use async drivers
default_url = "postgresql+asyncpg://postgres:password@localhost:5432/scos_db"
DATABASE_URL = os.getenv("DATABASE_URL", default_url)

# Convert sync URLs to async URLs if they exist in env
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("sqlite:///"):
    DATABASE_URL = DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///", 1)

if DATABASE_URL.startswith("sqlite"):
    engine = create_async_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_async_engine(DATABASE_URL, pool_size=20, max_overflow=10)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

Base = declarative_base()

async def get_db():
    async with SessionLocal() as session:
        yield session
