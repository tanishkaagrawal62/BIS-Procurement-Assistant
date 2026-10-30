import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB = BASE_DIR / "data" / "bis_assist.sqlite3"
DATABASE_URL = os.getenv("BIS_DATABASE_URL", f"sqlite:///{DEFAULT_DB.as_posix()}")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL.removeprefix("postgres://")
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL.removeprefix("postgresql://")
if DATABASE_URL.startswith("sqlite"):
    Path(DATABASE_URL.removeprefix("sqlite:///" )).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(300), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    analyses: Mapped[list["Analysis"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class SessionToken(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Standard(Base):
    __tablename__ = "standards"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    is_number: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    scope: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[str] = mapped_column(Text, default="")
    department: Mapped[str | None] = mapped_column(String(300))
    revision_year: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str | None] = mapped_column(String(100))
    amendments: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provenance: Mapped[str] = mapped_column(Text, nullable=False)
    verification_state: Mapped[str] = mapped_column(String(40), default="unverified", nullable=False)


class Analysis(Base):
    __tablename__ = "analyses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    tender_name: Mapped[str] = mapped_column(String(300), nullable=False)
    location: Mapped[str | None] = mapped_column(String(200))
    filename: Mapped[str | None] = mapped_column(String(255))
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    requirements_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="complete", nullable=False)
    warning: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    user: Mapped[User] = relationship(back_populates="analyses")
    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="analysis", cascade="all, delete-orphan")


class Recommendation(Base):
    __tablename__ = "recommendations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    standard_id: Mapped[int] = mapped_column(ForeignKey("standards.id"), index=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    keyword_score: Mapped[float] = mapped_column(Float, default=0)
    semantic_score: Mapped[float | None] = mapped_column(Float)
    combined_score: Mapped[float] = mapped_column(Float, default=0)
    evidence_json: Mapped[str] = mapped_column(Text, default="[]")
    uncertainty_json: Mapped[str] = mapped_column(Text, default="[]")
    analysis: Mapped[Analysis] = relationship(back_populates="recommendations")
    standard: Mapped[Standard] = relationship()


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)
    # Additive migration for existing project databases; existing analyses stay intact.
    if "location" not in {column["name"] for column in inspect(engine).get_columns("analyses") }:
        with engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE analyses ADD COLUMN location VARCHAR(200)")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
