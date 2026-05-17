import threading
import logging
import os

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def run_admin():
    from admin_panel import run
    logger.info("🌐 Starting Admin Panel...")
    run()

def run_bot():
    from devclin_bot import main
    logger.info("🤖 Starting Telegram Bot...")
    main()

if __name__ == "__main__":
    admin_thread = threading.Thread(target=run_admin, daemon=True)
    admin_thread.start()
    run_bot()
