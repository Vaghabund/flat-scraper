"""Listing filter service for flat-scraper-bot."""

from utils import format_price


class FilterService:
    """Applies configurable search criteria to flat listings."""

    DEFAULT_CRITERIA: dict = {
        "min_rooms": 2,
        "max_rooms": 4,
        "min_floor": 2,
        "max_price": 1500,
        "areas": [],
        "exclude_keywords": [],
    }

    def __init__(self, default_criteria: dict | None = None) -> None:
        """Initialise the filter service.

        Args:
            default_criteria: Override the built-in default criteria.  Any
                keys not provided fall back to :attr:`DEFAULT_CRITERIA`.
        """
        self.default_criteria = {**self.DEFAULT_CRITERIA, **(default_criteria or {})}

    def apply_filters(self, listing: dict, criteria: dict | None = None) -> bool:
        """Decide whether a listing matches the given (or default) criteria.

        All checks involving ``None`` listing values are skipped (the listing is
        not rejected purely because a value is missing).

        Args:
            listing: Flat listing dictionary.
            criteria: Optional override criteria.  Merged on top of defaults.

        Returns:
            ``True`` if the listing passes every applicable filter.
        """
        effective = {**self.default_criteria, **(criteria or {})}

        # Rooms check
        rooms = listing.get("rooms")
        if rooms is not None:
            if not (effective["min_rooms"] <= rooms <= effective["max_rooms"]):
                return False

        # Floor check
        floor = listing.get("floor")
        if floor is not None:
            if floor < effective["min_floor"]:
                return False

        # Price check
        price = listing.get("price")
        if price is not None:
            if price > effective["max_price"]:
                return False

        # Area / location check
        areas: list[str] = effective.get("areas", [])
        if areas:
            combined_location = (
                (listing.get("area") or "") + " " + (listing.get("address") or "")
            ).lower()
            if not any(area.lower() in combined_location for area in areas):
                return False

        # Excluded keywords check
        exclude_keywords: list[str] = effective.get("exclude_keywords", [])
        if exclude_keywords:
            search_text = (
                (listing.get("description") or "") + " " + (listing.get("address") or "")
            ).lower()
            if any(kw.lower() in search_text for kw in exclude_keywords):
                return False

        return True

    def get_criteria_summary(self, criteria: dict | None = None) -> str:
        """Return a human-readable summary of the active search criteria.

        Args:
            criteria: Optional criteria dict; falls back to defaults.

        Returns:
            Multi-line string ready for display in a Telegram message.
        """
        effective = {**self.default_criteria, **(criteria or {})}

        areas = effective.get("areas", [])
        areas_str = ", ".join(areas) if areas else "Any"

        keywords = effective.get("exclude_keywords", [])
        keywords_str = ", ".join(keywords) if keywords else "None"

        price_str = format_price(effective["max_price"])

        return (
            f"🛏️ Rooms: {effective['min_rooms']}–{effective['max_rooms']}\n"
            f"🏢 Min Floor: {effective['min_floor']}\n"
            f"💰 Max Price: {price_str}/month\n"
            f"📍 Areas: {areas_str}\n"
            f"🚫 Excluded: {keywords_str}"
        )
