from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.utils.logging_config import setup_logging
from app.schedulers.nightly_jobs import start_scheduler
from app.ml.models import risk_model
from app.api.routes import (
    risk_scoring,
    priority_list,
    confirmation,
    stock_forecast,
    cluster_detection,
    correlation,
)

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    risk_model.load()
    scheduler = start_scheduler()
    yield
    scheduler.shutdown()


app = FastAPI(
    title="HIV/TB AI Risk Scoring Service",
    description=(
        "AI microservice for the HIV/TB Co-infection Monitoring System. "
        "Reads directly from PostgreSQL. All endpoints require X-Internal-API-Key header."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.include_router(risk_scoring.router,      prefix="/ai", tags=["Risk Scoring"])
app.include_router(priority_list.router,     prefix="/ai", tags=["Priority List"])
app.include_router(confirmation.router,      prefix="/ai", tags=["Confirmation Analysis"])
app.include_router(stock_forecast.router,    prefix="/ai", tags=["Stock Forecast"])
app.include_router(cluster_detection.router, prefix="/ai", tags=["Early Warning"])
app.include_router(correlation.router,       prefix="/ai", tags=["Clinical Correlation"])


@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "service": "python-ai-service", "version": "2.0.0"}
