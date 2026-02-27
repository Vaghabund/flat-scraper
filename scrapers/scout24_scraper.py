"""ImmobilienScout24 scraper for flat-scraper-bot."""

import time
import random
from datetime import datetime, timezone

from .base_scraper import BaseScraper


class Scout24Scraper(BaseScraper):
    """Scraper for ImmobilienScout24 rental listings."""

    def __init__(self, base_url: str, proxies: list[str] | None = None) -> None:
        super().__init__(base_url, proxies)

    def scrape(self) -> list[dict]:
        """Fetch up to 3 pages of results from ImmobilienScout24.

        Returns:
            List of normalised listing dicts.
        """
        listings: list[dict] = []
        url = self.base_url

        for page_num in range(1, 4):
            self.logger.info("Scout24: scraping page %d — %s", page_num, url)
            soup = self.get_soup(url)
            if soup is None:
                self.logger.error("Scout24: failed to fetch page %d", page_num)
                break

            # Find result items — try multiple selector patterns
            items = (
                soup.select("li[data-obid]")
                or soup.select("article[data-obid]")
            )
            if not items:
                self.logger.info("Scout24: no items on page %d, stopping", page_num)
                break

            self.logger.info("Scout24: found %d items on page %d", len(items), page_num)

            for item in items:
                listing = self._parse_item(item)
                if listing and self.validate_listing(listing):
                    listings.append(listing)

            # Pagination
            next_link = (
                soup.select_one("a[data-nav-ref='resultlist_pagination_next']")
                or soup.select_one("li.pagination-next a")
            )
            if not next_link or not next_link.get("href"):
                break
            href = next_link["href"]
            url = href if href.startswith("http") else f"https://www.immobilienscout24.de{href}"
            time.sleep(random.uniform(2, 3))

        self.logger.info("Scout24: total listings collected: %d", len(listings))
        return listings

    def _parse_item(self, item) -> dict | None:
        """Extract fields from a single result list element.

        Args:
            item: BeautifulSoup tag representing one listing.

        Returns:
            Listing dict, or ``None`` on parse failure.
        """
        try:
            obid = item.get("data-obid", "")
            if not obid:
                return None
            site_id = f"scout24_{obid}"

            link_tag = (
                item.select_one("a.result-list-entry__brand-title-container")
                or item.select_one("a[data-nav-ref='result_list_entry']")
                or item.select_one("a[href*='/expose/']")
            )
            if not link_tag:
                return None
            href = link_tag.get("href", "")
            url = href if href.startswith("http") else f"https://www.immobilienscout24.de{href}"

            address_tag = (
                item.select_one(".result-list-entry__address")
                or item.select_one("[data-testid='result-list-entry-address']")
                or item.select_one("button.result-list-entry__map-link")
            )
            address = self.normalize_address(address_tag.get_text()) if address_tag else None

            price_tags = item.select(
                "dd.result-list-entry__primary-criterion, "
                ".result-list-entry__primary-criterion"
            )
            price = None
            rooms = None
            for tag in price_tags:
                text = tag.get_text(strip=True)
                if "€" in text or "EUR" in text:
                    price = self.extract_price(text)
                elif "Zi" in text or "Zimmer" in text:
                    rooms = self.extract_rooms(text)

            # Try criteria list for rooms/floor
            criteria_items = item.select("li.result-list-entry__criteria-item, dl dt, dl dd")
            floor = None
            for ci in criteria_items:
                text = ci.get_text(strip=True)
                if any(kw in text for kw in ["OG", "EG", "DG", "Etage", "Geschoss"]):
                    floor = self.extract_floor(text)

            area = address.split(",")[-1].strip() if address and "," in address else None

            return {
                "site_id": site_id,
                "url": url,
                "address": address,
                "rooms": rooms,
                "floor": floor,
                "price": price,
                "area": area,
                "description": None,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            self.logger.error("Scout24: error parsing item: %s", exc)
            return None
