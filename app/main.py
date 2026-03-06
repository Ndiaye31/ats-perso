import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import validate_startup_config
from app.logging_utils import emit_critical_alert
from app.scheduler import start_scheduler, stop_scheduler
from app.routers import health, offers, scrape, scoring, candidatures

app = FastAPI(title="mon-ATS", version="0.1.0")
logger = logging.getLogger(__name__)

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
async def _validate_config_on_startup() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    validate_startup_config()
    start_scheduler(app)


@app.on_event("shutdown")
async def _stop_scheduler_on_shutdown() -> None:
    await stop_scheduler(app)


@app.exception_handler(HTTPException)
async def _http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code >= 500:
        incident_id = emit_critical_alert(
            logger,
            alert_code="HTTP_5XX",
            message="Erreur HTTP critique",
            status_code=exc.status_code,
            path=request.url.path,
            method=request.method,
            detail=str(exc.detail),
        )
        payload = {
            "detail": str(exc.detail),
            "alert_code": "HTTP_5XX",
            "incident_id": incident_id,
        }
        return JSONResponse(status_code=exc.status_code, content=payload)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    incident_id = emit_critical_alert(
        logger,
        alert_code="UNHANDLED_EXCEPTION",
        message="Exception non gérée",
        path=request.url.path,
        method=request.method,
        error=str(exc),
    )
    payload = {
        "detail": "Erreur interne du serveur",
        "alert_code": "UNHANDLED_EXCEPTION",
        "incident_id": incident_id,
    }
    return JSONResponse(status_code=500, content=payload)
