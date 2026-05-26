"""
Scheduled AI jobs:
  23:00 daily  — risk scoring for all active patients
  06:00 daily  — priority lists for all CHWs
  Every hour   — stock forecasting for all CHWs
  Every 6 hrs  — cluster / early-warning detection
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.patient import Patient
from app.models.stock_record import StockRecord
from app.services import (
    risk_scoring_service,
    priority_list_service,
    stock_forecast_service,
    cluster_detection_service,
)

logger = logging.getLogger(__name__)


def _run_nightly_risk_scoring():
    logger.info("Nightly risk scoring job started")
    db = SessionLocal()
    try:
        patients = db.query(Patient).filter(Patient.is_active == True).all()
        ok, err = 0, 0
        for p in patients:
            try:
                risk_scoring_service.calculate(p.id, db)
                ok += 1
            except Exception as e:
                logger.warning("Risk scoring failed for %s: %s", p.full_name, e)
                err += 1
        logger.info("Nightly risk scoring done — ok=%d errors=%d", ok, err)
    finally:
        db.close()


def _run_morning_priority_lists():
    logger.info("Morning priority list job started")
    db = SessionLocal()
    try:
        chw_ids = {p.chw_id for p in db.query(Patient.chw_id).filter(Patient.is_active == True).distinct()}
        for chw_id in chw_ids:
            try:
                priority_list_service.generate(chw_id, db)
            except Exception as e:
                logger.warning("Priority list failed for CHW %s: %s", chw_id, e)
        logger.info("Morning priority lists generated for %d CHWs", len(chw_ids))
    finally:
        db.close()


def _run_stock_forecast():
    logger.info("Stock forecast job started")
    db = SessionLocal()
    try:
        chw_ids = {r.chw_id for r in db.query(StockRecord.chw_id).distinct()}
        for chw_id in chw_ids:
            try:
                stock_forecast_service.forecast(chw_id, db)
            except Exception as e:
                logger.warning("Stock forecast failed for CHW %s: %s", chw_id, e)
        logger.info("Stock forecast done for %d CHWs", len(chw_ids))
    finally:
        db.close()


def _run_cluster_detection():
    logger.info("Cluster detection job started")
    db = SessionLocal()
    try:
        result = cluster_detection_service.detect(db)
        logger.info("Cluster detection done — %d clusters found", result["clusters_detected"])
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()

    scheduler.add_job(
        _run_nightly_risk_scoring,
        CronTrigger(hour=settings.nightly_risk_score_hour, minute=0),
        id="nightly_risk_scoring", replace_existing=True,
    )
    scheduler.add_job(
        _run_morning_priority_lists,
        CronTrigger(hour=settings.morning_priority_list_hour, minute=0),
        id="morning_priority_lists", replace_existing=True,
    )
    scheduler.add_job(
        _run_stock_forecast,
        CronTrigger(minute=0),
        id="hourly_stock_forecast", replace_existing=True,
    )
    scheduler.add_job(
        _run_cluster_detection,
        CronTrigger(hour="*/6"),
        id="cluster_detection_6h", replace_existing=True,
    )

    scheduler.start()
    logger.info(
        "Scheduler started — risk@%d:00, priority@%d:00, stock@every hour, clusters@every 6h",
        settings.nightly_risk_score_hour,
        settings.morning_priority_list_hour,
    )
    return scheduler
