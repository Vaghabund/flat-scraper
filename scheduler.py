"""Background scheduler for periodic scraping cycles."""

import threading
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from database import add_listing, get_new_listings, is_duplicate, mark_notified
from logger import get_logger

logger = get_logger(__name__)


class ScraperScheduler:
    """Orchestrates periodic scraping, filtering, and notification."""

    def __init__(
        self,
        scrapers: list,
        db_path: str,
        filter_service,
        notifier,
        criteria: dict,
    ) -> None:
        """Initialise the scheduler.

        Args:
            scrapers: List of scraper instances (must implement ``scrape()``).
            db_path: Path to the SQLite database.
            filter_service: :class:`~filters.FilterService` instance.
            notifier: :class:`~notifier.NotificationService` instance.
            criteria: Search criteria dict passed to the filter service.
        """
        self.scrapers = scrapers
        self.db_path = db_path
        self.filter_service = filter_service
        self.notifier = notifier
        self.criteria = criteria
        self._scheduler: BackgroundScheduler | None = None

    def run_scrape_cycle(self) -> None:
        """Execute one full scrape → filter → notify cycle.

        For every scraper: fetch listings, store new ones, then notify about
        any matching, un-notified listings.
        """
        logger.info("=== Scrape cycle started at %s ===", datetime.now(timezone.utc))
        total_scraped = 0
        total_new = 0
        total_notified = 0

        for scraper in self.scrapers:
            try:
                listings = scraper.scrape()
                logger.info(
                    "%s returned %d listings", scraper.__class__.__name__, len(listings)
                )
                for listing in listings:
                    if not is_duplicate(self.db_path, listing["url"]):
                        add_listing(self.db_path, listing)
                        total_new += 1
                total_scraped += 1
            except Exception as exc:
                logger.error(
                    "Error running scraper %s: %s", scraper.__class__.__name__, exc
                )

        new_listings = get_new_listings(self.db_path)
        for listing in new_listings:
            if self.filter_service.apply_filters(
                listing, self.criteria
            ) and self.notifier.should_notify(listing):
                if self.notifier.send_notification(listing):
                    mark_notified(self.db_path, listing["id"])
                    total_notified += 1

        logger.info(
            "=== Cycle complete: %d scraped, %d new, %d notified ===",
            total_scraped,
            total_new,
            total_notified,
        )

    def start(self, interval_minutes: int = 30) -> None:
        """Start the background scheduler.

        Args:
            interval_minutes: How often (in minutes) to run a scrape cycle.
        """
        self._scheduler = BackgroundScheduler()
        self._scheduler.add_job(
            self.run_scrape_cycle,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id="scrape_cycle",
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info("Scheduler started — interval: %d minutes", interval_minutes)

    def stop(self) -> None:
        """Shut the background scheduler down gracefully."""
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped.")

    def trigger_now(self) -> None:
        """Run :meth:`run_scrape_cycle` immediately in a background daemon thread."""
        thread = threading.Thread(target=self.run_scrape_cycle, daemon=True)
        thread.start()
        logger.info("Manual scrape cycle triggered.")
