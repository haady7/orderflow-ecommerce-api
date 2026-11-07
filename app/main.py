from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.api.router import api_router
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
import app.models  # noqa: F401 - register SQLAlchemy models


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Tables are created for easy local startup. Railway/Docker also runs Alembic migrations first.
    if settings.environment == "development":
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", description="OrderFlow e-commerce order and payment management API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True,
                   allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"], allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Razorpay-Signature"])
app.include_router(api_router, prefix="/api/v1")

frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/health", tags=["Operations"])
def health():
    return {"status": "ok", "service": "orderflow-api"}


@app.get("/", include_in_schema=False)
def frontend():
    index = frontend_dir / "index.html"
    return FileResponse(index) if index.exists() else {"message": "OrderFlow API", "docs": "/docs"}
