"""
Main entry point for flat-scraper-bot.

Initializes all components and starts the Telegram bot with background scraping.
"""

import os
import signal
import sys
import asyncio

os.makedirs("data", exist_ok=True)
os.makedirs("logs", exist_ok=True)

from logger import get_logger  # noqa: E402

logger = get_logger(__name__)

from config import config  # noqa: E402
from database import init_db  # noqa: E402
from filters import FilterService  # noqa: E402
from notifier import NotificationService  # noqa: E402
from scheduler import ScraperScheduler  # noqa: E402
from scrapers import Scout24Scraper, ImmoweltScraper, ImmonetScraper  # noqa: E402
from telegram_bot import TelegramBot  # noqa: E402


if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def main() -> None:
    """Bootstrap and run the flat-scraper-bot."""
    logger.info("Initialising flat-scraper-bot …")

    # Database
    init_db(config.DATABASE_PATH)
    logger.info("Database initialised at %s", config.DATABASE_PATH)

    # Scrapers
    scrapers = [
        Scout24Scraper(config.SCOUT24_BASE_URL),
        ImmoweltScraper(config.IMMOWELT_BASE_URL),
        ImmonetScraper(config.IMMONET_BASE_URL),
    ]

    # Services
    filter_service = FilterService(config.DEFAULT_CRITERIA)
    notifier = NotificationService(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID)

    # Scheduler
    scheduler = ScraperScheduler(
        scrapers, config.DATABASE_PATH, filter_service, notifier, config.DEFAULT_CRITERIA
    )
    scheduler.start(config.SCRAPE_INTERVAL_MINUTES)

    # Telegram bot
    bot = TelegramBot(
        config.TELEGRAM_BOT_TOKEN,
        config.TELEGRAM_CHAT_ID,
        config.DATABASE_PATH,
        filter_service,
        scheduler,
    )

    # Graceful shutdown
    def _shutdown(_signum, _frame):
        logger.info("Shutdown signal received — stopping scheduler …")
        scheduler.stop()
        logger.info("Flat-scraper-bot stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Startup notification
    startup_message = (
        "🤖 Flat Scraper Bot started!\n"
        "📋 Monitoring criteria:\n"
        f"{filter_service.get_criteria_summary()}\n"
        f"⏱️ Scraping every {config.SCRAPE_INTERVAL_MINUTES} minutes"
    )
    logger.info(startup_message)

    # Block — runs the Telegram polling loop
    bot.run()


if __name__ == "__main__":
    main()
