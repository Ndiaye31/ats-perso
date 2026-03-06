from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import validate_startup_config
from app.routers import health, offers, scrape, scoring, candidatures

app = FastAPI(title="mon-ATS", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(offers.router)
app.include_router(scrape.router)
app.include_router(scoring.router)
app.include_router(candidatures.router)


@app.on_event("startup")
def _validate_config_on_startup() -> None:
    validate_startup_config()
