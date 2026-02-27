"""Configuration module for flat-scraper-bot.

Loads settings from a ``.env`` file (or environment variables) at import time
and exposes a validated :class:`Config` dataclass singleton called ``config``.
"""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    """Application configuration loaded from environment variables."""

    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_CHAT_ID: str
    DATABASE_PATH: str
    SCRAPE_INTERVAL_MINUTES: int
    DEFAULT_CRITERIA: dict
    SCOUT24_BASE_URL: str
    IMMOWELT_BASE_URL: str
    IMMONET_BASE_URL: str
    LOG_LEVEL: str
    LOG_FILE: str


def _build_config() -> Config:
    """Read environment variables and return a :class:`Config` instance.

    Raises:
        ValueError: If ``TELEGRAM_BOT_TOKEN`` or ``TELEGRAM_CHAT_ID`` are
            missing or empty.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

    if not token:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN is not set. "
            "Please add it to your .env file or environment."
        )
    if not chat_id:
        raise ValueError(
            "TELEGRAM_CHAT_ID is not set. "
            "Please add it to your .env file or environment."
        )

    database_url = os.getenv("DATABASE_URL", "sqlite:///data/flats.db")
    database_path = database_url.replace("sqlite:///", "")

    areas_raw = os.getenv("AREAS", "")
    areas = [a.strip() for a in areas_raw.split(",") if a.strip()] if areas_raw else []

    keywords_raw = os.getenv("EXCLUDE_KEYWORDS", "")
    exclude_keywords = (
        [k.strip() for k in keywords_raw.split(",") if k.strip()] if keywords_raw else []
    )

    default_criteria: dict = {
        "min_rooms": int(os.getenv("MIN_ROOMS", "2")),
        "max_rooms": int(os.getenv("MAX_ROOMS", "4")),
        "min_floor": int(os.getenv("MIN_FLOOR", "2")),
        "max_price": float(os.getenv("MAX_PRICE", "1500")),
        "areas": areas,
        "exclude_keywords": exclude_keywords,
    }

    return Config(
        TELEGRAM_BOT_TOKEN=token,
        TELEGRAM_CHAT_ID=chat_id,
        DATABASE_PATH=database_path,
        SCRAPE_INTERVAL_MINUTES=int(os.getenv("SCRAPE_INTERVAL_MINUTES", "30")),
        DEFAULT_CRITERIA=default_criteria,
        SCOUT24_BASE_URL=os.getenv(
            "SCOUT24_BASE_URL",
            "https://www.immobilienscout24.de/Suche/de/berlin/berlin/wohnung-mieten",
        ),
        IMMOWELT_BASE_URL=os.getenv(
            "IMMOWELT_BASE_URL",
            "https://www.immowelt.de/liste/berlin/wohnungen/mieten",
        ),
        IMMONET_BASE_URL=os.getenv(
            "IMMONET_BASE_URL",
            "https://www.immonet.de/immobiliensuche/sel.do?city=Berlin&marketingtype=1&objecttype=1",
        ),
        LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO"),
        LOG_FILE=os.getenv("LOG_FILE", "logs/scraper.log"),
    )


config = _build_config()
