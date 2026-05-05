from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.db.schema import init_db
from app.logging_config import setup_logging
from app.routers import cards, sessions, chat, import_routes, presets, worldbooks, upload, konata, creation


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cards.router, prefix="/api/cards", tags=["cards"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(import_routes.router)
app.include_router(presets.router, prefix="/api/presets", tags=["presets"])
app.include_router(worldbooks.router, prefix="/api/worldbooks", tags=["worldbooks"])
app.include_router(upload.router, prefix="/api/upload", tags=["upload"])
app.include_router(konata.router, prefix="/api/konata", tags=["konata"])
app.include_router(creation.router, prefix="/api/creation", tags=["creation"])

app.mount("/uploads", StaticFiles(directory=str(settings.uploads_dir)), name="uploads")


@app.get("/api/health")
def health():
    return {"status": "ok", "version": settings.version}
