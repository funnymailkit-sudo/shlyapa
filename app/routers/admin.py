import json
from datetime import datetime
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import (Game, Location, Player, Season, Team, TeamPlayer,
                           get_db, get_or_create_season)

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="app/templates")


def _validate_teams(teams_data: list) -> Optional[str]:
    """Return error message or None if valid."""
    if not teams_data:
        return "Добавьте хотя бы одну команду."
    places = [int(td["place"]) for td in teams_data]
    if len(places) != len(set(places)):
        return "Два места не могут совпадать. Проверьте поля «Место»."
    for td in teams_data:
        if not td.get("player_ids"):
            return f"В команде «{td.get('name') or 'без названия'}» нет игроков."
    all_pids = [int(pid) for td in teams_data for pid in td.get("player_ids", [])]
    if len(all_pids) != len(set(all_pids)):
        return "Один игрок не может быть в двух командах одновременно."
    return None


def _game_form_ctx(db: Session, request: Request, form_action: str,
                   existing_game=None, existing_teams_json: str = "[]",
                   played_at: str = "", error: str = "") -> dict:
    return {
        "request": request,
        "locations": db.query(Location).all(),
        "players": db.query(Player).order_by(Player.name).all(),
        "today": played_at or datetime.now().strftime("%Y-%m-%d"),
        "form_action": form_action,
        "existing_game": existing_game,
        "existing_teams_json": existing_teams_json,
        "error": error,
    }


def _save_teams(db: Session, game: Game, teams_data: list[dict]) -> None:
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


# ── Games: Create ──────────────────────────────────────────────────────────────

@router.get("/games/new", response_class=HTMLResponse)
def admin_new_game(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        "admin/game_form.html",
        _game_form_ctx(db, request, "/admin/games/new"),
    )


@router.post("/games/new", response_class=HTMLResponse)
def admin_create_game(
    request: Request,
    location_id: int = Form(...),
    played_at: str = Form(...),
    notes: str = Form(""),
    teams_json: str = Form(...),
    db: Session = Depends(get_db),
):
    teams_data = json.loads(teams_json)
    err = _validate_teams(teams_data)
    if err:
        return templates.TemplateResponse(
            "admin/game_form.html",
            _game_form_ctx(db, request, "/admin/games/new",
                           existing_teams_json=teams_json,
                           played_at=played_at, error=err),
            status_code=422,
        )

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
    _save_teams(db, game, teams_data)
    db.commit()
    return RedirectResponse(f"/games/{game.id}", status_code=303)


# ── Games: Edit ────────────────────────────────────────────────────────────────

@router.get("/games/{game_id}/edit", response_class=HTMLResponse)
def admin_edit_game(request: Request, game_id: int, db: Session = Depends(get_db)):
    game = db.query(Game).filter_by(id=game_id).first()
    if not game:
        return HTMLResponse("Игра не найдена", status_code=404)

    existing_teams = [
        {
            "name": t.name or "",
            "place": t.place,
            "player_ids": [tp.player_id for tp in t.team_players],
        }
        for t in sorted(game.teams, key=lambda t: t.place)
    ]

    return templates.TemplateResponse(
        "admin/game_form.html",
        _game_form_ctx(
            db, request,
            form_action=f"/admin/games/{game_id}/edit",
            existing_game=game,
            existing_teams_json=json.dumps(existing_teams, ensure_ascii=False),
            played_at=game.played_at.strftime("%Y-%m-%d"),
        ),
    )


@router.post("/games/{game_id}/edit", response_class=HTMLResponse)
def admin_update_game(
    request: Request,
    game_id: int,
    location_id: int = Form(...),
    played_at: str = Form(...),
    notes: str = Form(""),
    teams_json: str = Form(...),
    db: Session = Depends(get_db),
):
    game = db.query(Game).filter_by(id=game_id).first()
    if not game:
        return HTMLResponse("Игра не найдена", status_code=404)

    teams_data = json.loads(teams_json)
    err = _validate_teams(teams_data)
    if err:
        return templates.TemplateResponse(
            "admin/game_form.html",
            _game_form_ctx(
                db, request,
                form_action=f"/admin/games/{game_id}/edit",
                existing_game=game,
                existing_teams_json=teams_json,
                played_at=played_at,
                error=err,
            ),
            status_code=422,
        )

    played_at_dt = datetime.strptime(played_at, "%Y-%m-%d")
    season = get_or_create_season(db, played_at_dt)

    for team in game.teams:
        db.delete(team)
    db.flush()

    game.location_id = location_id
    game.played_at = played_at_dt
    game.season_id = season.id
    game.notes = notes.strip()
    db.flush()

    _save_teams(db, game, teams_data)
    db.commit()
    return RedirectResponse(f"/games/{game.id}", status_code=303)


@router.post("/games/{game_id}/delete")
def admin_delete_game(game_id: int, db: Session = Depends(get_db)):
    game = db.query(Game).filter_by(id=game_id).first()
    if game:
        db.delete(game)
        db.commit()
    return RedirectResponse("/games", status_code=303)
