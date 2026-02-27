"""Immowelt scraper for flat-scraper-bot."""

import hashlib
import time
import random
from datetime import datetime
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

from .base_scraper import BaseScraper


class ImmoweltScraper(BaseScraper):
    """Scraper for Immowelt rental listings."""

    def __init__(self, base_url: str) -> None:
        super().__init__(base_url)

    def scrape(self) -> list[dict]:
        """Fetch up to 3 pages of results from Immowelt.

        Returns:
            List of normalised listing dicts.
        """
        listings: list[dict] = []

        for page_num in range(1, 4):
            url = self._page_url(page_num)
            self.logger.info("Immowelt: scraping page %d — %s", page_num, url)
            soup = self.get_soup(url)
            if soup is None:
                self.logger.error("Immowelt: failed to fetch page %d", page_num)
                break

            items = (
                soup.select("div[data-testid='serp-card']")
                or soup.select("article.estate-item")
                or soup.select("div.listItem")
            )
            if not items:
                self.logger.info("Immowelt: no items on page %d, stopping", page_num)
                break

            self.logger.info("Immowelt: found %d items on page %d", len(items), page_num)

            for item in items:
                listing = self._parse_item(item)
                if listing and self.validate_listing(listing):
                    listings.append(listing)

            if page_num < 3:
                time.sleep(random.uniform(2, 3))

        self.logger.info("Immowelt: total listings collected: %d", len(listings))
        return listings

    def _page_url(self, page_num: int) -> str:
        """Build the URL for a given page number.

        Args:
            page_num: 1-based page number.

        Returns:
            URL string with ``cp`` query parameter set.
        """
        if page_num == 1:
            return self.base_url
        separator = "&" if "?" in self.base_url else "?"
        return f"{self.base_url}{separator}cp={page_num}"

    def _parse_item(self, item) -> dict | None:
        """Extract fields from a single card element.

        Args:
            item: BeautifulSoup tag representing one listing card.

        Returns:
            Listing dict, or ``None`` on parse failure.
        """
        try:
            link_tag = item.select_one("a[href*='/expose/']") or item.select_one("a[href]")
            if not link_tag:
                return None
            href = link_tag.get("href", "")
            url = href if href.startswith("http") else f"https://www.immowelt.de{href}"

            site_id = f"immowelt_{hashlib.md5(url.encode()).hexdigest()[:8]}"

            address_tag = (
                item.select_one(".card-content__address")
                or item.select_one("[data-testid='card-address']")
                or item.select_one(".location")
            )
            address = self.normalize_address(address_tag.get_text()) if address_tag else None

            price_tag = (
                item.select_one(".card-content__price-information")
                or item.select_one("[data-testid='card-price']")
                or item.select_one(".price")
            )
            price = self.extract_price(price_tag.get_text()) if price_tag else None

            # Key facts (rooms, area m²)
            rooms = None
            key_facts = item.select(".card-content__keyfacts li, .keyfact, .hard-fact")
            for fact in key_facts:
                text = fact.get_text(strip=True)
                if "Zi" in text or "Zimmer" in text:
                    rooms = self.extract_rooms(text)

            area = address.split(",")[-1].strip() if address and "," in address else None

            return {
                "site_id": site_id,
                "url": url,
                "address": address,
                "rooms": rooms,
                "floor": None,
                "price": price,
                "area": area,
                "description": None,
                "scraped_at": datetime.utcnow().isoformat(),
            }
        except Exception as exc:
            self.logger.error("Immowelt: error parsing item: %s", exc)
            return None
