"""Abstract base class for all flat-listing scrapers."""

import logging
import random
import re
import time
from abc import ABC, abstractmethod
from urllib.parse import urlparse, urlunparse

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

    def __init__(self, base_url: str, proxies: list[str] | None = None) -> None:
        self.base_url = base_url
        self.logger: logging.Logger = get_logger(self.__class__.__name__)
        self.session = requests.Session()
        self._proxies: list[str] = list(proxies) if proxies is not None else []
        self._warmed_hosts: set[str] = set()

    @abstractmethod
    def scrape(self) -> list[dict]:
        """Fetch listings and return them as a list of normalised dicts."""

    def _pick_proxy(self) -> dict[str, str] | None:
        """Return a random proxy dict for :mod:`requests`, or ``None``.

        Returns:
            A dict suitable for the ``proxies`` kwarg of
            :meth:`requests.Session.get`, e.g.
            ``{"http": "http://…", "https": "http://…"}``, or ``None`` when no
            proxies are configured.
        """
        if not self._proxies:
            return None
        proxy_url = random.choice(self._proxies)
        return {"http": proxy_url, "https": proxy_url}

    @staticmethod
    def _redact_proxy_url(proxy_url: str) -> str:
        """Return *proxy_url* with any embedded credentials removed.

        Replaces ``user:pass@`` in the netloc with ``***@`` so that proxy
        host/port information is still useful in logs while passwords are not
        leaked.

        Args:
            proxy_url: Full proxy URL, e.g. ``http://user:pass@host:8080``.

        Returns:
            URL with credentials replaced by ``***``, or the original string
            if it cannot be parsed.
        """
        try:
            parsed = urlparse(proxy_url)
            if "@" in parsed.netloc:
                host_port = parsed.netloc.split("@")[-1]
                parsed = parsed._replace(netloc=f"***@{host_port}")
            return urlunparse(parsed)
        except Exception:
            return "***"

    def get_soup(self, url: str, retries: int = 2) -> BeautifulSoup | None:
        """Fetch a URL and return a :class:`BeautifulSoup` object.

        Rotates the User-Agent header and proxy on every call and applies an
        exponential back-off retry strategy.  A random 2–3 second delay is
        added before each HTTP request to be polite to the target servers.

        Args:
            url: Target URL.
            retries: Number of additional attempts after the first failure.

        Returns:
            Parsed HTML, or ``None`` if all attempts fail.
        """
        for attempt in range(retries + 1):
            try:
                parsed_url = urlparse(url)
                host_root = f"{parsed_url.scheme}://{parsed_url.netloc}"
                self.session.headers.update(
                    {
                        "User-Agent": random.choice(self.USER_AGENTS),
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
                        "Cache-Control": "no-cache",
                        "Pragma": "no-cache",
                        "DNT": "1",
                        "Upgrade-Insecure-Requests": "1",
                        "Referer": host_root + "/",
                    }
                )
                proxy = self._pick_proxy()
                if proxy:
                    self.logger.debug(
                        "Fetching %s via proxy %s (attempt %d)",
                        url, self._redact_proxy_url(proxy.get("https", "")), attempt + 1,
                    )
                else:
                    self.logger.debug("Fetching %s (attempt %d)", url, attempt + 1)

                if parsed_url.netloc not in self._warmed_hosts:
                    try:
                        self.session.get(host_root, timeout=10, proxies=proxy)
                    except requests.RequestException:
                        pass
                    self._warmed_hosts.add(parsed_url.netloc)

                time.sleep(random.uniform(2, 3))
                response = self.session.get(url, timeout=10, proxies=proxy)
                if response.status_code in {401, 403, 429}:
                    page_title = ""
                    title_match = re.search(
                        r"<title[^>]*>(.*?)</title>", response.text, flags=re.IGNORECASE | re.DOTALL
                    )
                    if title_match:
                        page_title = re.sub(r"\s+", " ", title_match.group(1)).strip()
                    self.logger.warning(
                        "Blocked response for %s: status=%s title=%r",
                        url,
                        response.status_code,
                        page_title,
                    )
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
