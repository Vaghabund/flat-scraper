"""Facebook Groups scraper for flat-scraper-bot.

This scraper targets public Facebook group pages (mobile basic HTML) and
extracts post links that likely describe flat listings.
"""

import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from .base_scraper import BaseScraper


class FacebookGroupScraper(BaseScraper):
    """Scraper for public Facebook groups focused on apartment listings."""

    _RELEVANT_KEYWORDS = {
        "wohnung",
        "zimmer",
        "miete",
        "warmmiete",
        "kaltmiete",
        "wg",
        "nachmieter",
        "untermiete",
        "apartment",
        "flat",
    }

    _BERLIN_AREAS = [
        "prenzlauer berg",
        "friedrichshain",
        "kreuzberg",
        "neukölln",
        "tempelhof",
        "schöneberg",
        "treptow",
        "köpenick",
        "lichtenberg",
        "marzahn",
        "hellersdorf",
        "mitte",
        "charlottenburg",
        "wilmersdorf",
        "berlin",
    ]

    def __init__(
        self,
        group_urls: list[str],
        proxies: list[str] | None = None,
        session_cookie: str = "",
    ) -> None:
        super().__init__("https://mbasic.facebook.com", proxies)
        self.group_urls = [url.strip() for url in group_urls if url.strip()]
        self.session_cookie = session_cookie.strip()
        if self.session_cookie:
            self.session.headers.update({"Cookie": self.session_cookie})

    def scrape(self) -> list[dict]:
        """Scrape configured Facebook groups and return listing-like posts."""
        if not self.group_urls:
            return []

        listings: list[dict] = []
        seen_urls: set[str] = set()

        for group_url in self.group_urls:
            url = self._to_mbasic_group_url(group_url)
            self.logger.info("Facebook: scraping group %s", url)
            soup = self.get_soup(url, retries=1)
            if soup is None:
                self.logger.error("Facebook: failed to fetch group page %s", url)
                continue

            if self._looks_like_login_page(soup):
                self.logger.warning(
                    "Facebook: login wall detected for %s. Add FACEBOOK_SESSION_COOKIE or use public groups.",
                    url,
                )
                continue

            post_blocks = self._collect_post_blocks(soup)
            self.logger.info("Facebook: found %d post candidates in %s", len(post_blocks), url)

            for post in post_blocks:
                listing = self._parse_post(post, group_url)
                if not listing:
                    continue
                if listing["url"] in seen_urls:
                    continue
                seen_urls.add(listing["url"])
                listings.append(listing)

        self.logger.info("Facebook: total listings collected: %d", len(listings))
        return listings

    @staticmethod
    def _to_mbasic_group_url(url: str) -> str:
        parsed = urlparse(url)
        path = parsed.path.strip()
        if not path.startswith("/groups/"):
            if path:
                path = "/groups/" + path.strip("/")
            else:
                path = "/groups/"
        if not path.endswith("/"):
            path += "/"
        return f"https://mbasic.facebook.com{path}"

    @staticmethod
    def _looks_like_login_page(soup) -> bool:
        title = (soup.title.get_text(strip=True).lower() if soup.title else "")
        if "log in" in title or "anmelden" in title:
            return True
        return bool(soup.select_one("form[action*='login']"))

    def _collect_post_blocks(self, soup) -> list:
        candidates = (
            soup.select("div[data-ft*='top_level_post_id']")
            or soup.select("article")
            or soup.select("div.story_body_container")
            or soup.select("div._5rgt")
        )

        if candidates:
            return candidates

        blocks = []
        for link in soup.select("a[href*='/groups/'][href*='/posts/']"):
            parent = link.find_parent("article") or link.find_parent("div")
            if parent is not None:
                blocks.append(parent)
        return blocks

    def _parse_post(self, post, source_group_url: str) -> dict | None:
        post_link = (
            post.select_one("a[href*='/groups/'][href*='/posts/']")
            or post.select_one("a[href*='story_fbid=']")
            or post.select_one("a[href]")
        )
        if not post_link:
            return None

        href = post_link.get("href", "")
        if not href:
            return None

        if href.startswith("http"):
            full_url = href
        else:
            full_url = f"https://www.facebook.com{href}"

        parsed = urlparse(full_url)
        normalized_url = f"https://www.facebook.com{parsed.path}"
        if parsed.query:
            normalized_url += f"?{parsed.query}"

        text = post.get_text(" ", strip=True)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return None

        text_lower = text.lower()
        if not any(keyword in text_lower for keyword in self._RELEVANT_KEYWORDS):
            return None

        price = self.extract_price(text)
        rooms = self.extract_rooms(text)
        area = self._extract_area(text_lower)

        post_id = self._extract_post_id(parsed)
        digest = hashlib.md5(normalized_url.encode("utf-8")).hexdigest()[:10]
        site_id = f"facebook_{post_id or digest}"

        return {
            "site_id": site_id,
            "url": normalized_url,
            "address": f"Facebook Group: {source_group_url}",
            "rooms": rooms,
            "floor": None,
            "price": price,
            "area": area,
            "description": text[:900],
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _extract_post_id(parsed_url) -> str | None:
        match = re.search(r"/posts/(\d+)", parsed_url.path)
        if match:
            return match.group(1)
        query = parse_qs(parsed_url.query)
        if "story_fbid" in query and query["story_fbid"]:
            return query["story_fbid"][0]
        return None

    def _extract_area(self, text_lower: str) -> str | None:
        for area in self._BERLIN_AREAS:
            if area in text_lower:
                return area.title()
        return "Berlin"
