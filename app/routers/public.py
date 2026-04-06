from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import Game, Player, Season, TeamPlayer, get_db

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _build_leaderboard(db: Session, games: list) -> list[dict]:
    points: dict[int, int] = defaultdict(int)
    games_played: dict[int, int] = defaultdict(int)
    wins: dict[int, int] = defaultdict(int)
    max_possible: dict[int, int] = defaultdict(int)

    for game in games:
        n = len(game.teams)
        if n == 0:
            continue
        for team in game.teams:
            team_points = n - team.place + 1
            for tp in team.team_players:
                pid = tp.player_id
                points[pid] += team_points
                games_played[pid] += 1
                max_possible[pid] += n
                if team.place == 1:
                    wins[pid] += 1

    leaderboard = []
    for player in db.query(Player).all():
        pid = player.id
        if pid not in games_played:
            continue
        g = games_played[pid]
        p = points[pid]
        w = wins[pid]
        mp = max_possible[pid]
        leaderboard.append(
            {
                "player": player,
                "points": p,
                "games": g,
                "wins": w,
                "win_pct": round(w / g * 100) if g > 0 else 0,
                "kpd": round(p / mp * 100) if mp > 0 else 0,
            }
        )

    leaderboard.sort(key=lambda x: (-x["points"], -x["kpd"], x["player"].name))
    for i, entry in enumerate(leaderboard):
        entry["rank"] = i + 1
    return leaderboard


def compute_seasonal_leaderboard(db: Session, season: Season) -> list[dict]:
    games = db.query(Game).filter_by(season_id=season.id).all()
    return _build_leaderboard(db, games)


def compute_alltime_leaderboard(db: Session) -> list[dict]:
    games = db.query(Game).all()
    return _build_leaderboard(db, games)


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    tab: str = "quarterly",
    season_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    seasons = (
        db.query(Season).order_by(Season.year.desc(), Season.quarter.desc()).all()
    )
    season = (
        db.query(Season).filter_by(id=season_id).first()
        if season_id
        else (seasons[0] if seasons else None)
    )
    seasonal_lb = compute_seasonal_leaderboard(db, season) if season else []
    alltime_lb = compute_alltime_leaderboard(db)

    return templates.TemplateResponse(
        "public/index.html",
        {
            "request": request,
            "tab": tab,
            "seasons": seasons,
            "current_season": season,
            "seasonal_lb": seasonal_lb,
            "alltime_lb": alltime_lb,
        },
    )


@router.get("/players/{player_id}", response_class=HTMLResponse)
def player_detail(request: Request, player_id: int, db: Session = Depends(get_db)):
    player = db.query(Player).filter_by(id=player_id).first()
    if not player:
        return HTMLResponse("Игрок не найден", status_code=404)

    rows = (
        db.query(TeamPlayer)
        .filter_by(player_id=player_id)
        .join(TeamPlayer.team)
        .join(TeamPlayer.team.property.mapper.class_.game)
        .all()
    )

    # Build game history
    history = []
    total_points = 0
    total_wins = 0
    total_max = 0

    for tp in rows:
        team = tp.team
        game = team.game
        n = len(game.teams)
        earned = n - team.place + 1
        total_points += earned
        total_max += n
        if team.place == 1:
            total_wins += 1
        teammates = [t.player for t in team.team_players if t.player_id != player_id]
        history.append(
            {
                "game": game,
                "team": team,
                "teammates": teammates,
                "points": earned,
                "n_teams": n,
            }
        )

    history.sort(key=lambda x: x["game"].played_at, reverse=True)
    total_games = len(history)
    win_pct = round(total_wins / total_games * 100) if total_games else 0
    kpd = round(total_points / total_max * 100) if total_max else 0

    return templates.TemplateResponse(
        "public/player.html",
        {
            "request": request,
            "player": player,
            "history": history,
            "total_games": total_games,
            "total_points": total_points,
            "total_wins": total_wins,
            "win_pct": win_pct,
            "kpd": kpd,
        },
    )


@router.get("/games", response_class=HTMLResponse)
def games_list(
    request: Request, season_id: Optional[int] = None, db: Session = Depends(get_db)
):
    seasons = (
        db.query(Season).order_by(Season.year.desc(), Season.quarter.desc()).all()
    )
    season = (
        db.query(Season).filter_by(id=season_id).first()
        if season_id
        else (seasons[0] if seasons else None)
    )
    games = (
        db.query(Game)
        .filter_by(season_id=season.id)
        .order_by(Game.played_at.desc())
        .all()
        if season
        else []
    )

    return templates.TemplateResponse(
        "public/games.html",
        {
            "request": request,
            "seasons": seasons,
            "current_season": season,
            "games": games,
        },
    )


@router.get("/games/{game_id}", response_class=HTMLResponse)
def game_detail(request: Request, game_id: int, db: Session = Depends(get_db)):
    game = db.query(Game).filter_by(id=game_id).first()
    if not game:
        return HTMLResponse("Игра не найдена", status_code=404)

    n = len(game.teams)
    teams_data = [
        {
            "team": team,
            "players": [tp.player for tp in team.team_players],
            "points": n - team.place + 1,
        }
        for team in sorted(game.teams, key=lambda t: t.place)
    ]

    return templates.TemplateResponse(
        "public/game_detail.html",
        {"request": request, "game": game, "teams_data": teams_data},
    )
