import os
import time
import sys
import signal
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Ensure we can find and import local services
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db_service import init_db
from feed_service import sync_feed_data
from notification_service import send_telegram_notification

# Set up logging to both console and a log file
log_format = '%(asctime)s [%(levelname)s] %(message)s'
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(os.path.dirname(__file__), "daemon.log"), encoding='utf-8')
    ]
)
logger = logging.getLogger("SPOT_Daemon")

# Load environment variables from .env file
load_dotenv()

# --- Config & Defaults ---
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "tracking.db")
DEFAULT_FEED_ID = "0FOq6U5ICzOEL4qCqbM8YrAOqUzP8uGUp"

# Load config with overrides from env
feed_id = os.getenv("SPOT_FEED_ID", DEFAULT_FEED_ID)
tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
tg_chat_id = os.getenv("TELEGRAM_CHAT_ID")
poll_interval = int(os.getenv("POLL_INTERVAL", 60)) # Poll interval in seconds (default 1 minute)

# Flag to maintain graceful shutdown
running = True

def handle_shutdown(signum, frame):
    global running
    logger.info(f"Received shutdown signal ({signum}). Gracefully stopping background daemon...")
    running = False

# Register signal hooks
signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

def run_daemon():
    global running
    logger.info("==================================================")
    logger.info("🚀 SPOT 24/7 Background Scraping Daemon Started!")
    logger.info(f"SPOT Feed ID: {feed_id}")
    logger.info(f"Polling Interval: {poll_interval} seconds")
    logger.info(f"Database Path: {DB_PATH}")
    logger.info(f"Telegram Notification Integration: {'CONFIGURED' if (tg_token and tg_chat_id) else 'NOT CONFIGURED (Alerts Skipped)'}")
    logger.info("==================================================")
    
    # Initialize DB if needed
    init_db(DB_PATH)
    
    # Send a startup self-test notification to Telegram if configured
    if tg_token and tg_chat_id:
        logger.info("Sending startup Telegram self-test alert...")
        startup_msg = (
            "🚀 *SPOT Tracker Service Started!*\n\n"
            "The 24/7 background scraping service has successfully initialized and is now active.\n\n"
            "🧭 *Feed ID:* `{feed_id}`\n"
            "⏱️ *Interval:* {poll_interval}s\n\n"
            "Telegram notifications are active and verified! ✅"
        ).format(feed_id=feed_id, poll_interval=poll_interval)
        send_telegram_notification(tg_token, tg_chat_id, startup_msg)
    
    while running:
        try:
            logger.info("Initiating SPOT feed poll cycle...")
            
            # Use sliding 24-hour window to catch up on any potentially missed messages
            end_dt = datetime.utcnow()
            start_dt = end_dt - timedelta(hours=24)
            
            success, new_count, notifications_sent, err = sync_feed_data(
                feed_id=feed_id,
                start_dt=start_dt,
                end_dt=end_dt,
                tg_token=tg_token,
                tg_chat_id=tg_chat_id,
                db_path=DB_PATH
            )
            
            if success:
                if new_count > 0:
                    logger.info(f"Sync complete. Successfully added {new_count} new tracking points.")
                    if notifications_sent > 0:
                        logger.info(f"Dispatched {notifications_sent} Telegram alerts successfully.")
                else:
                    logger.info("Sync complete. No new points found.")
            else:
                logger.error(f"Sync failed: {err}")
                
        except Exception as e:
            logger.error(f"Unhandled exception during polling cycle: {e}", exc_info=True)
            
        # Wait for the next poll cycle with 1-second sleeps to respond to shutdown signals rapidly
        for _ in range(poll_interval):
            if not running:
                break
            time.sleep(1)
            
    logger.info("Background daemon stopped cleanly. Bye!")

if __name__ == "__main__":
    run_daemon()
