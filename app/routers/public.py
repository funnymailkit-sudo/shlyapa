from collections import defaultdict

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import Game, Player, Season, get_db

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def compute_leaderboard(db: Session, season: Season) -> list[dict]:
    games = db.query(Game).filter_by(season_id=season.id).all()
    points: dict[int, int] = defaultdict(int)
    games_played: dict[int, int] = defaultdict(int)

    for game in games:
        n = len(game.teams)
        if n == 0:
            continue
        for team in game.teams:
            team_points = n - team.place + 1
            for tp in team.team_players:
                points[tp.player_id] += team_points
                games_played[tp.player_id] += 1

    leaderboard = []
    for player in db.query(Player).all():
        if player.id in points:
            leaderboard.append(
                {
                    "player": player,
                    "points": points[player.id],
                    "games": games_played[player.id],
                }
            )

    leaderboard.sort(key=lambda x: (-x["points"], -x["games"], x["player"].name))
    for i, entry in enumerate(leaderboard):
        entry["rank"] = i + 1

    return leaderboard


@router.get("/", response_class=HTMLResponse)
def index(request: Request, season_id: int | None = None, db: Session = Depends(get_db)):
    seasons = (
        db.query(Season)
        .order_by(Season.year.desc(), Season.quarter.desc())
        .all()
    )
    season = (
        db.query(Season).filter_by(id=season_id).first()
        if season_id
        else (seasons[0] if seasons else None)
    )
    leaderboard = compute_leaderboard(db, season) if season else []

    return templates.TemplateResponse(
        "public/index.html",
        {
            "request": request,
            "seasons": seasons,
            "current_season": season,
            "leaderboard": leaderboard,
        },
    )


@router.get("/games", response_class=HTMLResponse)
def games_list(
    request: Request, season_id: int | None = None, db: Session = Depends(get_db)
):
    seasons = (
        db.query(Season)
        .order_by(Season.year.desc(), Season.quarter.desc())
        .all()
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
