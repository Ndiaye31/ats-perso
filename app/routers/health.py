from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db

router = APIRouter()


def _check_db(db: Session) -> dict:
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "detail": "Connexion DB opérationnelle"}
    except Exception as exc:
        return {"status": "ko", "detail": f"Erreur DB: {exc}"}


def _check_config() -> dict:
    problems: list[str] = []
    in_docker = Path("/.dockerenv").exists()

    if not settings.database_url.strip():
        problems.append("DATABASE_URL manquant ou vide")

    for env_name, path_value in (("CV_PATH", settings.cv_path), ("DIPLOME_PATH", settings.diplome_path)):
        if not path_value:
            continue
        if not in_docker and path_value.startswith("/app/"):
            continue
        if not Path(path_value).exists():
            problems.append(f"{env_name} introuvable: {path_value}")

    if problems:
        return {"status": "ko", "detail": "; ".join(problems)}
    return {"status": "ok", "detail": "Configuration minimale valide"}


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    db_check = _check_db(db)
    config_check = _check_config()

    global_ok = db_check["status"] == "ok" and config_check["status"] == "ok"
    payload = {
        "status": "ok" if global_ok else "ko",
        "checks": {
            "db": db_check,
            "config": config_check,
        },
    }

    if global_ok:
        return payload
    return JSONResponse(status_code=503, content=payload)
