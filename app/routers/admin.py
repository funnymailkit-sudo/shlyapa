import json
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import (Game, Location, Player, Team, TeamPlayer,
                           get_db, get_or_create_season)

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="app/templates")


# ── Dashboard ──────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def admin_index(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        "admin/index.html",
        {
            "request": request,
            "locations_count": db.query(Location).count(),
            "players_count": db.query(Player).count(),
            "games_count": db.query(Game).count(),
        },
    )


# ── Locations ──────────────────────────────────────────────────────────────────

@router.get("/locations", response_class=HTMLResponse)
def admin_locations(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        "admin/locations.html",
        {"request": request, "locations": db.query(Location).all()},
    )


@router.post("/locations")
def admin_add_location(
    name: str = Form(...),
    address: str = Form(""),
    db: Session = Depends(get_db),
):
    db.add(Location(name=name.strip(), address=address.strip()))
    db.commit()
    return RedirectResponse("/admin/locations", status_code=303)


@router.post("/locations/{location_id}/delete")
def admin_delete_location(location_id: int, db: Session = Depends(get_db)):
    loc = db.query(Location).filter_by(id=location_id).first()
    if loc:
        db.delete(loc)
        db.commit()
    return RedirectResponse("/admin/locations", status_code=303)


# ── Players ────────────────────────────────────────────────────────────────────

@router.get("/players", response_class=HTMLResponse)
def admin_players(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        "admin/players.html",
        {"request": request, "players": db.query(Player).order_by(Player.name).all()},
    )


@router.post("/players")
def admin_add_player(name: str = Form(...), db: Session = Depends(get_db)):
    db.add(Player(name=name.strip()))
    db.commit()
    return RedirectResponse("/admin/players", status_code=303)


@router.post("/players/{player_id}/delete")
def admin_delete_player(player_id: int, db: Session = Depends(get_db)):
    player = db.query(Player).filter_by(id=player_id).first()
    if player:
        db.delete(player)
        db.commit()
    return RedirectResponse("/admin/players", status_code=303)


# ── Games ──────────────────────────────────────────────────────────────────────

@router.get("/games/new", response_class=HTMLResponse)
def admin_new_game(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        "admin/game_new.html",
        {
            "request": request,
            "locations": db.query(Location).all(),
            "players": db.query(Player).order_by(Player.name).all(),
            "today": datetime.now().strftime("%Y-%m-%d"),
        },
    )


@router.post("/games/new")
def admin_create_game(
    location_id: int = Form(...),
    played_at: str = Form(...),
    notes: str = Form(""),
    teams_json: str = Form(...),
    db: Session = Depends(get_db),
):
    played_at_dt = datetime.strptime(played_at, "%Y-%m-%d")
    season = get_or_create_season(db, played_at_dt)

    game = Game(
        season_id=season.id,
        location_id=location_id,
        played_at=played_at_dt,
        notes=notes.strip(),
    )
    db.add(game)
    db.flush()

    teams_data: list[dict] = json.loads(teams_json)
    for td in teams_data:
        team = Team(
            game_id=game.id,
            name=td.get("name", "").strip(),
            place=int(td["place"]),
        )
        db.add(team)
        db.flush()
        for pid in td.get("player_ids", []):
            db.add(TeamPlayer(team_id=team.id, player_id=int(pid)))

    db.commit()
    return RedirectResponse(f"/games/{game.id}", status_code=303)


@router.post("/games/{game_id}/delete")
def admin_delete_game(game_id: int, db: Session = Depends(get_db)):
    game = db.query(Game).filter_by(id=game_id).first()
    if game:
        db.delete(game)
        db.commit()
    return RedirectResponse("/games", status_code=303)
