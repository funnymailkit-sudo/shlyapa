import os
from datetime import datetime

from sqlalchemy import (Column, DateTime, ForeignKey, Integer, String, Text,
                        create_engine)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker

# Use DATABASE_URL env var in production (PostgreSQL), fall back to SQLite.
_raw = os.environ.get("DATABASE_URL", "")

# Normalize postgres:// → postgresql:// (Supabase/Heroku quirk)
if _raw.startswith("postgres://"):
    _raw = _raw.replace("postgres://", "postgresql://", 1)

# Accept only known schemes; ignore any garbage value (e.g. wrong API keys)
_VALID = ("postgresql://", "postgresql+", "sqlite")
DATABASE_URL = _raw if any(_raw.startswith(s) for s in _VALID) else "sqlite:///./shlyapa.db"

_is_sqlite = DATABASE_URL.startswith("sqlite")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {"sslmode": "require"},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_quarter(date: datetime) -> int:
    return (date.month - 1) // 3 + 1


def get_or_create_season(db, date: datetime) -> "Season":
    year = date.year
    quarter = get_quarter(date)
    season = db.query(Season).filter_by(year=year, quarter=quarter).first()
    if not season:
        season = Season(year=year, quarter=quarter)
        db.add(season)
        db.commit()
        db.refresh(season)
    return season


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    address = Column(String(200), default="")
    games = relationship("Game", back_populates="location")


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)


class Season(Base):
    __tablename__ = "seasons"

    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, nullable=False)
    quarter = Column(Integer, nullable=False)  # 1–4
    games = relationship("Game", back_populates="season")

    @property
    def label(self) -> str:
        return f"Q{self.quarter} {self.year}"


class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    played_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    notes = Column(Text, default="")
    season = relationship("Season", back_populates="games")
    location = relationship("Location", back_populates="games")
    teams = relationship("Team", back_populates="game", cascade="all, delete-orphan")


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    name = Column(String(100), default="")
    place = Column(Integer, nullable=False)
    game = relationship("Game", back_populates="teams")
    team_players = relationship(
        "TeamPlayer", back_populates="team", cascade="all, delete-orphan"
    )


class TeamPlayer(Base):
    __tablename__ = "team_players"

    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    team = relationship("Team", back_populates="team_players")
    player = relationship("Player")
