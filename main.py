"""
main.py — Combined launcher for Dev Clin
Runs both the Telegram bot and the Flask admin panel together.
Railway starts this file via: python main.py
"""

import threading
import os
import logging

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def run_admin_panel():
    """Start the Flask admin panel."""
    from admin_panel import app
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"🌐 Admin panel starting on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


def run_bot():
    """Start the Telegram bot."""
    from devclin_bot import main
    logger.info("🤖 Telegram bot starting...")
    main()


if __name__ == "__main__":
    # Admin panel runs in a background thread (Flask)
    admin_thread = threading.Thread(target=run_admin_panel, daemon=True)
    admin_thread.start()
    logger.info("✅ Admin panel thread launched")

    # Bot runs in the main thread (blocking)
    run_bot()
