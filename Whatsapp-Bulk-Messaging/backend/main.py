import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler
from pathlib import Path

import config
from database import init_db, db_cursor, now
from routers import dashboard, contacts, campaigns, inbox, bulk, templates, logs, settings, webhook

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.FileHandler(config.LOG_PATH), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _check_scheduled_campaigns():
    """Runs every minute: sends any campaign whose scheduled_at time has arrived."""
    with db_cursor() as cur:
        due = cur.execute(
            "SELECT id FROM campaigns WHERE status='scheduled' AND scheduled_at <= ?", (now(),)
        ).fetchall()
    for row in due:
        logger.info("Scheduled campaign %s is due — sending now", row["id"])
        try:
            # Reuse the same send flow as a manual "Send Now"
            from fastapi import BackgroundTasks
            with db_cursor() as cur:
                cur.execute("UPDATE campaigns SET status='sending', started_at=? WHERE id=?", (now(), row["id"]))
                campaign = cur.execute("SELECT * FROM campaigns WHERE id=?", (row["id"],)).fetchone()
                existing = cur.execute("SELECT COUNT(*) FROM campaign_recipients WHERE campaign_id=?",
                                        (row["id"],)).fetchone()[0]
                if existing == 0:
                    contacts_rows = cur.execute("SELECT id FROM contacts WHERE group_id=? AND opted_in=1",
                                                 (campaign["group_id"],)).fetchall()
                    for c in contacts_rows:
                        cur.execute(
                            "INSERT INTO campaign_recipients (campaign_id, contact_id, status) VALUES (?,?,?)",
                            (row["id"], c["id"], "pending"))
            campaigns.execute_campaign(row["id"])
        except Exception as e:
            logger.error("Failed to send scheduled campaign %s: %s", row["id"], e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler.add_job(_check_scheduled_campaigns, "interval", minutes=1, id="scheduled_campaigns")
    scheduler.start()
    logger.info("%s started.", config.APP_NAME)
    yield
    scheduler.shutdown()


app = FastAPI(title=config.APP_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router)
app.include_router(contacts.router)
app.include_router(campaigns.router)
app.include_router(inbox.router)
app.include_router(bulk.router)
app.include_router(templates.router)
app.include_router(logs.router)
app.include_router(settings.router)
app.include_router(webhook.router)

# Serve the frontend (single-page app) as static files, mounted last so /api and
# /webhook routes above take priority.
FRONTEND_DIR = str(Path(__file__).resolve().parent.parent / "frontend")
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
