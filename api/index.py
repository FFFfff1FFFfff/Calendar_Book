import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import close_pool, init_pool
from app.routes.auth import router as auth_router
from app.routes.availability import router as availability_router
from app.routes.booking import router as booking_router


@asynccontextmanager
async def lifespan(application: FastAPI):
    await init_pool(settings.database_url)
    yield
    await close_pool()


app = FastAPI(title="Calendar Booking API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(availability_router)
app.include_router(booking_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# Serve static files locally. On Vercel the `public/` folder is served by
# the static build target instead.
_public_dir = _PROJECT_ROOT / "public"
if _public_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_public_dir), html=True), name="static")
