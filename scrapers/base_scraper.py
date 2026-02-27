"""Abstract base class for all flat-listing scrapers."""

import logging
import random
import re
import time
from abc import ABC, abstractmethod

import requests
from bs4 import BeautifulSoup

from logger import get_logger


class BaseScraper(ABC):
    """Abstract scraper providing shared HTTP and parsing helpers.

    Subclasses must implement :meth:`scrape`.
    """

    USER_AGENTS: list[str] = [
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Safari/605.1.15"
        ),
        (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/119.0.0.0 Safari/537.36"
        ),
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) "
            "Gecko/20100101 Firefox/120.0"
        ),
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    ]

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self.logger: logging.Logger = get_logger(self.__class__.__name__)
        self.session = requests.Session()

    @abstractmethod
    def scrape(self) -> list[dict]:
        """Fetch listings and return them as a list of normalised dicts."""

    def get_soup(self, url: str, retries: int = 2) -> BeautifulSoup | None:
        """Fetch a URL and return a :class:`BeautifulSoup` object.

        Rotates the User-Agent header on every call and applies an exponential
        back-off retry strategy.  A random 2–3 second delay is added before
        each HTTP request to be polite to the target servers.

        Args:
            url: Target URL.
            retries: Number of additional attempts after the first failure.

        Returns:
            Parsed HTML, or ``None`` if all attempts fail.
        """
        for attempt in range(retries + 1):
            try:
                self.session.headers.update({"User-Agent": random.choice(self.USER_AGENTS)})
                self.logger.debug("Fetching %s (attempt %d)", url, attempt + 1)
                time.sleep(random.uniform(2, 3))
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                return BeautifulSoup(response.text, "html.parser")
            except requests.RequestException as exc:
                self.logger.error("Error fetching %s: %s", url, exc)
                if attempt < retries:
                    sleep_time = 2 ** attempt  # 1s, 2s
                    self.logger.debug("Retrying in %ds …", sleep_time)
                    time.sleep(sleep_time)
        return None

    def extract_rooms(self, text: str) -> int | None:
        """Parse a room count from strings like "3 Zimmer" or "3,5 Zimmer".

        Args:
            text: Raw text containing a room description.

        Returns:
            Floored integer room count, or ``None``.
        """
        if not text:
            return None
        match = re.search(r"(\d+)[,.](\d+)", text)
        if match:
            return int(float(f"{match.group(1)}.{match.group(2)}"))
        match = re.search(r"(\d+)", text)
        if match:
            return int(match.group(1))
        return None

    def extract_floor(self, text: str) -> int | None:
        """Parse a floor number from German floor descriptions.

        Special values:
        - "Erdgeschoss" / "EG" → 0
        - "DG" (Dachgeschoss / attic) → 99

        Args:
            text: Raw floor description string.

        Returns:
            Integer floor number, or ``None``.
        """
        if not text:
            return None
        text_lower = text.lower().strip()
        if "erdgeschoss" in text_lower or text_lower == "eg":
            return 0
        if "dg" in text_lower or "dachgeschoss" in text_lower:
            return 99
        match = re.search(r"(\d+)", text)
        if match:
            return int(match.group(1))
        return None

    def extract_price(self, text: str) -> float | None:
        """Parse a price from German-formatted strings like "1.200,00 €".

        Args:
            text: Raw price string.

        Returns:
            Price as a float, or ``None``.
        """
        if not text:
            return None
        cleaned = text.replace("\xa0", "").strip()
        # German format: "1.200,00" → "1200.00"
        match = re.search(r"(\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:,\d+)?)", cleaned)
        if match:
            raw = match.group(1)
            raw = raw.replace(".", "").replace(",", ".")
            try:
                return float(raw)
            except ValueError:
                return None
        return None

    def normalize_address(self, address: str) -> str:
        """Strip and collapse excess whitespace from an address string.

        Args:
            address: Raw address text.

        Returns:
            Cleaned address string.
        """
        return re.sub(r"\s+", " ", address).strip()

    def validate_listing(self, data: dict) -> bool:
        """Check that a listing dict contains the minimum required fields.

        Args:
            data: Listing dictionary to validate.

        Returns:
            ``True`` if both ``url`` and ``site_id`` are present and non-empty.
        """
        return bool(data.get("url")) and bool(data.get("site_id"))
