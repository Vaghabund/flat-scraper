"""Utility helper functions for flat-scraper-bot."""

import re
from datetime import datetime


def clean_price(text: str) -> float | None:
    """Extract a numeric price from a German-formatted price string.

    Handles formats such as "1.200 €/Monat", "1.200,50 €", "1200 €".
    In German notation a period is the thousands separator and a comma is
    the decimal separator.

    Args:
        text: Raw price string extracted from a web page.

    Returns:
        Price as a float, or ``None`` if no number could be parsed.
    """
    if not text:
        return None
    # Remove currency symbols, "Monat", whitespace
    cleaned = re.sub(r"[€$£\s/Monatmonat]", "", text)
    # Handle German format: "1.200,50" → "1200.50"
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        # Remove thousands separators (period when no comma present)
        cleaned = cleaned.replace(".", "")
    match = re.search(r"\d+(?:\.\d+)?", cleaned)
    if match:
        try:
            return float(match.group())
        except ValueError:
            return None
    return None


def extract_number(text: str) -> int | None:
    """Extract the first integer from a string.

    Args:
        text: Input string, e.g. "3 Zimmer" or "2. OG".

    Returns:
        First integer found, or ``None``.
    """
    if not text:
        return None
    match = re.search(r"\d+", text)
    if match:
        try:
            return int(match.group())
        except ValueError:
            return None
    return None


def parse_german_date(date_str: str) -> datetime | None:
    """Parse a German date string into a :class:`datetime` object.

    Supported formats:
    - "27. Februar 2026"
    - "27.02.2026"

    Args:
        date_str: Raw date string.

    Returns:
        Parsed :class:`datetime`, or ``None`` on failure.
    """
    if not date_str:
        return None

    german_months = {
        "januar": 1, "februar": 2, "märz": 3, "april": 4,
        "mai": 5, "juni": 6, "juli": 7, "august": 8,
        "september": 9, "oktober": 10, "november": 11, "dezember": 12,
    }

    # "27. Februar 2026"
    match = re.match(
        r"(\d{1,2})\.\s*([A-Za-zä]+)\s+(\d{4})", date_str.strip(), re.IGNORECASE
    )
    if match:
        day = int(match.group(1))
        month_name = match.group(2).lower()
        year = int(match.group(3))
        month = german_months.get(month_name)
        if month:
            try:
                return datetime(year, month, day)
            except ValueError:
                return None

    # "27.02.2026"
    try:
        return datetime.strptime(date_str.strip(), "%d.%m.%Y")
    except ValueError:
        pass

    return None


def slugify(text: str) -> str:
    """Normalize a string to a URL-friendly slug.

    Converts to lowercase, removes umlauts, replaces spaces and special
    characters with hyphens, and strips leading/trailing hyphens.

    Args:
        text: Input string to slugify.

    Returns:
        Slugified string.
    """
    umlaut_map = {
        "ä": "ae", "ö": "oe", "ü": "ue",
        "Ä": "ae", "Ö": "oe", "Ü": "ue",
        "ß": "ss",
    }
    for char, replacement in umlaut_map.items():
        text = text.replace(char, replacement)
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def format_price(price: float) -> str:
    """Format a float price value as a human-readable currency string.

    Args:
        price: Numeric price value.

    Returns:
        Formatted string such as "€1,200".
    """
    return f"€{price:,.0f}"
