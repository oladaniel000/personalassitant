"""
bot.py — Main entry point for the Telegram Daily Personal Assistant.
Runs in WEBHOOK mode so it works as a Render free Web Service.

How it works:
  - FastAPI serves HTTP on the port Render assigns ($PORT)
  - GET  /healthz  → Render's health check (must return 200 or service is killed)
  - POST /webhook  → Receives Telegram updates and feeds them to python-telegram-bot
  - On startup: registers the webhook URL with Telegram, initialises the scheduler
"""

import json
import logging

import uvicorn
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import (
    Application, CommandHandler
)

from config import TELEGRAM_BOT_TOKEN, WEBHOOK_URL, PORT
from database.db import init_db, get_db, get_or_create_user
from services.reminder_service import init_scheduler
from services import calendar_service

# ── Handlers ─────────────────────────────────────────────────────────────────
from handlers.setup import get_setup_handler
from handlers.event_add import get_add_handler
from handlers.event_checkin import get_checkin_handler
from handlers.morning import cmd_today, cmd_tomorrow, schedule_morning_job
from handlers.evening import cmd_recap, schedule_evening_job
from handlers.misc import cmd_help, cmd_sync, cmd_done, cmd_snooze, cmd_delete, cmd_woke

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ── Build the telegram Application once (module-level singleton) ──────────────
ptb_app = (
    Application.builder()
    .token(TELEGRAM_BOT_TOKEN)
    .updater(None)          # Disable built-in polling — we drive updates manually
    .build()
)


def _register_handlers(app):
    app.add_handler(get_setup_handler())
    app.add_handler(get_add_handler())
    app.add_handler(get_checkin_handler())
    app.add_handler(CommandHandler("today",    cmd_today))
    app.add_handler(CommandHandler("tomorrow", cmd_tomorrow))
    app.add_handler(CommandHandler("recap",    cmd_recap))
    app.add_handler(CommandHandler("help",     cmd_help))
    app.add_handler(CommandHandler("sync",     cmd_sync))
    app.add_handler(CommandHandler("done",     cmd_done))
    app.add_handler(CommandHandler("snooze",   cmd_snooze))
    app.add_handler(CommandHandler("delete",   cmd_delete))
    app.add_handler(CommandHandler("woke",     cmd_woke))


async def _sync_all_users():
    """Push any unsynced local events to Google Calendar for all users."""
    from database.models import UserState
    db = get_db()
    users = db.query(UserState).filter(
        UserState.setup_complete == True,
        UserState.google_token  != None,
    ).all()
    db.close()
    for user in users:
        try:
            db2 = get_db()
            token_dict = json.loads(user.google_token)
            count = calendar_service.sync_pending_events(db2, token_dict, user.timezone)
            if count:
                log.info(f"Synced {count} event(s) for {user.telegram_chat_id}")
            db2.close()
        except Exception as e:
            log.warning(f"Sync failed for {user.telegram_chat_id}: {e}")


# ── FastAPI app ───────────────────────────────────────────────────────────────
web_app = FastAPI()


@web_app.on_event("startup")
async def on_startup():
    """Startup: init DB, register webhook, start scheduler."""
    # 1. Database
    init_db()
    log.info("Database initialised.")

    # 2. Handlers + PTB initialise
    _register_handlers(ptb_app)
    await ptb_app.initialize()

    # 3. Register webhook with Telegram
    webhook_endpoint = f"{WEBHOOK_URL}/webhook"
    await ptb_app.bot.set_webhook(
        url=webhook_endpoint,
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True,
    )
    log.info(f"Webhook registered: {webhook_endpoint}")

    # 4. Start PTB
    await ptb_app.start()

    # 5. Scheduler
    scheduler = init_scheduler()

    # 6. Re-register daily jobs for all existing users
    from database.models import UserState
    db = get_db()
    users = db.query(UserState).filter(UserState.setup_complete == True).all()
    db.close()
    for user in users:
        schedule_morning_job(user.telegram_chat_id, user.morning_time or "07:00",
                             user.timezone or "Africa/Lagos", ptb_app)
        schedule_evening_job(user.telegram_chat_id, user.evening_time or "21:00",
                             user.timezone or "Africa/Lagos", ptb_app)

    # 7. GCal sync every 5 minutes
    scheduler.add_job(
        _sync_all_users,
        trigger="interval",
        minutes=5,
        id="gcal_sync_all",
        replace_existing=True,
    )

    log.info(f"Startup complete. {len(users)} existing user(s) loaded.")


@web_app.on_event("shutdown")
async def on_shutdown():
    await ptb_app.bot.delete_webhook()
    await ptb_app.stop()
    await ptb_app.shutdown()
    log.info("Bot shut down cleanly.")


@web_app.get("/healthz")
async def health_check():
    """
    Render pings this every 30 s. Must return 200 or the service is restarted.
    """
    return {"status": "ok"}


@web_app.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Telegram POSTs every update here. We parse and hand off to PTB.
    """
    data = await request.json()
    update = Update.de_json(data, ptb_app.bot)
    await ptb_app.process_update(update)
    return Response(status_code=200)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "bot:web_app",
        host="0.0.0.0",
        port=PORT,
        log_level="info",
    )
