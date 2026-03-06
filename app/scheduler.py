import asyncio
import logging
from time import perf_counter

from sqlalchemy import select

from app.config import settings
from app.logging_utils import log_event

logger = logging.getLogger(__name__)


def run_scrape_job() -> dict:
    from app.database import SessionLocal
    from app.routers.scrape import scrape_all

    db = SessionLocal()
    try:
        return scrape_all(db=db)
    finally:
        db.close()


def run_rescore_job() -> dict:
    from app.database import SessionLocal
    from app.routers.scoring import rescore_all

    db = SessionLocal()
    try:
        return rescore_all(db=db)
    finally:
        db.close()


def run_optional_batch_job() -> dict:
    from app.database import SessionLocal
    from app.models.candidature import Candidature
    from app.routers.candidatures import _bulk_generate_lm_impl

    if not settings.scheduler_batch_enabled:
        return {"enabled": False, "message": "optional batch disabled"}

    db = SessionLocal()
    try:
        ids = db.execute(
            select(Candidature.id)
            .where(Candidature.statut == "brouillon")
            .where(Candidature.mode_candidature == "plateforme")
            .order_by(Candidature.created_at.desc())
            .limit(max(1, settings.scheduler_batch_limit))
        ).scalars().all()
    finally:
        db.close()

    if not ids:
        return {"enabled": True, "selected": 0, "message": "no eligible candidatures"}

    result = _bulk_generate_lm_impl(ids, SessionLocal)
    return {
        "enabled": True,
        "selected": len(ids),
        "success": result.success,
        "failed": result.failed,
        "report_path": result.report_path,
    }


async def _run_periodic(job_name: str, interval_s: int, job_callable) -> None:
    interval = max(30, int(interval_s))
    while True:
        start = perf_counter()
        try:
            result = await asyncio.to_thread(job_callable)
            log_event(
                logger,
                logging.INFO,
                "scheduler_job_completed",
                source="scheduler",
                job=job_name,
                duration_ms=round((perf_counter() - start) * 1000, 2),
                result=result,
            )
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "scheduler_job_failed",
                source="scheduler",
                job=job_name,
                duration_ms=round((perf_counter() - start) * 1000, 2),
                error=str(exc),
            )
        await asyncio.sleep(interval)


def run_scheduled_jobs_once() -> dict:
    out = {"scrape": run_scrape_job(), "rescore": run_rescore_job()}
    if settings.scheduler_batch_enabled:
        out["optional_batch"] = run_optional_batch_job()
    else:
        out["optional_batch"] = {"enabled": False, "message": "optional batch disabled"}
    return out


def start_scheduler(app) -> None:
    if not settings.scheduler_enabled:
        log_event(logger, logging.INFO, "scheduler_disabled", source="scheduler")
        app.state.scheduler_tasks = []
        return

    tasks = [
        asyncio.create_task(_run_periodic("scrape", settings.scheduler_scrape_interval_s, run_scrape_job)),
        asyncio.create_task(_run_periodic("rescore", settings.scheduler_rescore_interval_s, run_rescore_job)),
    ]
    if settings.scheduler_batch_enabled:
        tasks.append(
            asyncio.create_task(
                _run_periodic("optional_batch", settings.scheduler_batch_interval_s, run_optional_batch_job)
            )
        )
    app.state.scheduler_tasks = tasks
    log_event(
        logger,
        logging.INFO,
        "scheduler_started",
        source="scheduler",
        jobs=[t.get_name() for t in tasks],
    )


async def stop_scheduler(app) -> None:
    tasks = getattr(app.state, "scheduler_tasks", [])
    for task in tasks:
        task.cancel()
    for task in tasks:
        try:
            await task
        except asyncio.CancelledError:
            pass
    log_event(logger, logging.INFO, "scheduler_stopped", source="scheduler", task_count=len(tasks))
