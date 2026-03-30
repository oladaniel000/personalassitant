"""
bot.py — Telegram Daily Personal Assistant
Webhook mode for Railway/Render free hosting.
"""

import json
import logging

import uvicorn
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import Application, CommandHandler

from config import TELEGRAM_BOT_TOKEN, WEBHOOK_URL, PORT
from database.db import init_db, get_db, get_or_create_user
from services.reminder_service import init_scheduler
from services import calendar_service

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

ptb_app = (
    Application.builder()
    .token(TELEGRAM_BOT_TOKEN)
    .updater(None)
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


web_app = FastAPI()
_started = False


@web_app.on_event("startup")
async def on_startup():
    global _started
    if _started:
        return
    _started = True

    init_db()
    log.info("Database initialised.")

    _register_handlers(ptb_app)
    await ptb_app.initialize()

    webhook_url = WEBHOOK_URL
    if webhook_url and not webhook_url.startswith("https://"):
        webhook_url = "https://" + webhook_url

    if webhook_url:
        webhook_endpoint = f"{webhook_url}/webhook"
        await ptb_app.bot.set_webhook(
            url=webhook_endpoint,
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True,
        )
        log.info(f"Webhook registered: {webhook_endpoint}")
    else:
        log.warning("WEBHOOK_URL not set — set it in environment variables.")

    await ptb_app.start()

    scheduler = init_scheduler()

    from database.models import UserState
    db = get_db()
    users = db.query(UserState).filter(UserState.setup_complete == True).all()
    db.close()
    for user in users:
        schedule_morning_job(user.telegram_chat_id, user.morning_time or "07:00",
                             user.timezone or "Africa/Lagos", ptb_app)
        schedule_evening_job(user.telegram_chat_id, user.evening_time or "21:00",
                             user.timezone or "Africa/Lagos", ptb_app)

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
    try:
        await ptb_app.bot.delete_webhook()
        await ptb_app.stop()
        await ptb_app.shutdown()
        log.info("Bot shut down cleanly.")
    except Exception as e:
        log.warning(f"Shutdown error (safe to ignore): {e}")


@web_app.get("/healthz")
async def health_check():
    return {"status": "ok"}


@web_app.get("/")
async def root():
    return {"status": "ok", "message": "Telegram Assistant is running"}


@web_app.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        update = Update.de_json(data, ptb_app.bot)
        await ptb_app.process_update(update)
    except Exception as e:
        log.warning(f"Webhook error: {e}")
    return Response(status_code=200)


if __name__ == "__main__":
    uvicorn.run(
        "bot:web_app",
        host="0.0.0.0",
        port=PORT,
        log_level="info",
        timeout_keep_alive=75,
    )
```

---

**Steps:**

1. Go to `github.com/oladaniel000/personalassitant`
2. Click `bot.py` → pencil icon → select all → paste the code above → **Commit changes**
3. Go to Railway → **Variables** → set `WEBHOOK_URL` to exactly:
```
https://web-production-1fb97.up.railway.app
