import json

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from app.database import Base, engine
from app.routers import admin, public

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Шляпа — Турнирная таблица")
app.include_router(public.router)
app.include_router(admin.router)

# Add tojson filter to every Jinja2Templates instance used by routers
def _tojson(value):
    return Markup(json.dumps(value, ensure_ascii=False))

for router_module in (public, admin):
    router_module.templates.env.filters["tojson"] = _tojson
