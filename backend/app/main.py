import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import account, admin, dashboard, help_center, issues, notifications, tickets
from app.services.sla import check_sla_risk

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(check_sla_risk, "interval", hours=1, id="sla_risk_check")
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="Qsolva API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tickets.router)
app.include_router(dashboard.router)
app.include_router(notifications.router)
app.include_router(issues.router)
app.include_router(help_center.router)
app.include_router(admin.router)
app.include_router(account.router)


@app.get("/health")
def health():
    return {"status": "ok"}
