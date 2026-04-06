from fastapi import FastAPI
from fastapi.templating import Jinja2Templates  # noqa: F401 – imported for side-effects

from app.database import Base, engine
from app.routers import admin, public

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Шляпа — Турнирная таблица")

app.include_router(public.router)
app.include_router(admin.router)
