import json
import re

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from app.database import Base, DATABASE_URL, engine
from app.routers import admin, public

try:
    Base.metadata.create_all(bind=engine)
except Exception as _e:
    import sys
    print(f"[WARNING] Could not create tables: {_e}", file=sys.stderr)

app = FastAPI(title="Шляпа — Турнирная таблица")
app.include_router(public.router)
app.include_router(admin.router)


@app.get("/healthz")
def healthz():
    """Diagnostic endpoint — shows DB type without exposing credentials."""
    safe_url = re.sub(r"://[^@]+@", "://*****@", DATABASE_URL)
    try:
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        ok = True
    except Exception as e:
        ok = False
    return JSONResponse({"db": safe_url, "connected": ok})

# Add tojson filter to every Jinja2Templates instance used by routers
def _tojson(value):
    return Markup(json.dumps(value, ensure_ascii=False))

for router_module in (public, admin):
    router_module.templates.env.filters["tojson"] = _tojson
