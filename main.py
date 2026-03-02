"""
Main entry point for flat-scraper-bot.

Initializes all components and starts the Telegram bot with background scraping.
"""

import os
import signal
import sys
import asyncio
import atexit
from pathlib import Path

os.makedirs("data", exist_ok=True)
os.makedirs("logs", exist_ok=True)

from logger import get_logger  # noqa: E402

logger = get_logger(__name__)

from config import config  # noqa: E402
from database import init_db  # noqa: E402
from filters import FilterService  # noqa: E402
from notifier import NotificationService  # noqa: E402
from scheduler import ScraperScheduler  # noqa: E402
from scrapers import Scout24Scraper, ImmoweltScraper, FacebookGroupScraper  # noqa: E402
from telegram_bot import TelegramBot  # noqa: E402


if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


_LOCK_PATH = Path("data") / "flat-scraper.lock"


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform.startswith("win"):
        try:
            import ctypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, pid
            )
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True


def _release_single_instance_lock() -> None:
    try:
        _LOCK_PATH.unlink(missing_ok=True)
    except OSError:
        pass


def _acquire_single_instance_lock() -> object | None:
    _LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)

    if _LOCK_PATH.exists():
        try:
            existing_pid = int(_LOCK_PATH.read_text(encoding="utf-8").strip() or "0")
        except ValueError:
            existing_pid = 0
        if _pid_is_running(existing_pid):
            logger.error("Another flat-scraper instance is already running (pid=%s). Exiting.", existing_pid)
            return None
        _release_single_instance_lock()

    try:
        fd = os.open(_LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        logger.error("Another flat-scraper instance is already running. Exiting.")
        return None

    with os.fdopen(fd, "w", encoding="utf-8") as lock_file:
        lock_file.write(str(os.getpid()))

    return _LOCK_PATH


def main() -> None:
    """Bootstrap and run the flat-scraper-bot."""
    lock_handle = _acquire_single_instance_lock()
    if lock_handle is None:
        return
    atexit.register(_release_single_instance_lock)

    logger.info("Initialising flat-scraper-bot …")

    # Database
    init_db(config.DATABASE_PATH)
    logger.info("Database initialised at %s", config.DATABASE_PATH)

    # Scrapers
    scrapers = [
        Scout24Scraper(config.SCOUT24_BASE_URL, config.PROXIES),
        ImmoweltScraper(config.IMMOWELT_BASE_URL, config.PROXIES),
    ]
    if config.FACEBOOK_GROUP_URLS:
        scrapers.append(
            FacebookGroupScraper(
                config.FACEBOOK_GROUP_URLS,
                config.PROXIES,
                config.FACEBOOK_SESSION_COOKIE,
            )
        )

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
