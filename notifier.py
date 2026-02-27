"""Notification service for sending Telegram messages."""

import asyncio
from datetime import datetime, timedelta, timezone

from telegram import Bot
from telegram.error import TelegramError

from logger import get_logger

logger = get_logger(__name__)


class NotificationService:
    """Sends Telegram notifications for new flat listings."""

    def __init__(self, bot_token: str, chat_id: str) -> None:
        """Initialise the notification service.

        Args:
            bot_token: Telegram bot API token.
            chat_id: Target Telegram chat (or user) ID.
        """
        self.bot_token = bot_token
        self.chat_id = chat_id

    def should_notify(self, listing: dict, hours: int = 24) -> bool:
        """Decide whether a listing warrants a notification.

        Returns ``True`` when the listing has not yet been notified *and* was
        scraped within the last ``hours`` hours.

        Args:
            listing: Listing dict with ``notified_at`` and ``scraped_at`` keys.
            hours: Recency window in hours.

        Returns:
            ``True`` if the listing should trigger a notification.
        """
        if listing.get("notified_at") is not None:
            return False
        scraped_at_raw = listing.get("scraped_at")
        if not scraped_at_raw:
            return False
        try:
            scraped_at = datetime.fromisoformat(str(scraped_at_raw))
            # Ensure timezone-aware comparison
            if scraped_at.tzinfo is None:
                scraped_at = scraped_at.replace(tzinfo=timezone.utc)
        except ValueError:
            return False
        return scraped_at >= datetime.now(timezone.utc) - timedelta(hours=hours)

    def format_message(self, listing: dict) -> str:
        """Build a Markdown-formatted Telegram message for a listing.

        ``None`` values are rendered as "N/A".

        Args:
            listing: Listing dict.

        Returns:
            Markdown string ready to send via Telegram.
        """
        address = listing.get("address") or "N/A"
        rooms = listing.get("rooms") if listing.get("rooms") is not None else "N/A"
        floor = listing.get("floor") if listing.get("floor") is not None else "N/A"
        price = listing.get("price")
        price_str = f"€{price:,.0f}" if price is not None else "N/A"
        area = listing.get("area") or "N/A"
        url = listing.get("url", "")

        return (
            "🏠 *New Flat Found!*\n\n"
            f"📍 *Address:* {address}\n"
            f"🛏️ *Rooms:* {rooms}\n"
            f"🏢 *Floor:* {floor}\n"
            f"💰 *Price:* {price_str}/month\n"
            f"📐 *Area:* {area}\n\n"
            f"🔗 [View Listing]({url})"
        )

    def send_notification(self, listing: dict) -> bool:
        """Send a Telegram notification for a listing.

        Uses :func:`asyncio.run` with ``python-telegram-bot``'s async
        :meth:`~telegram.Bot.send_message`.

        Args:
            listing: Listing dict to notify about.

        Returns:
            ``True`` on success, ``False`` on any error.
        """
        message = self.format_message(listing)
        try:
            asyncio.run(self._send(message))
            logger.info("Notification sent for listing: %s", listing.get("url"))
            return True
        except TelegramError as exc:
            logger.error("Telegram error sending notification: %s", exc)
            return False
        except Exception as exc:
            logger.error("Unexpected error sending notification: %s", exc)
            return False

    async def _send(self, text: str) -> None:
        """Internal coroutine that dispatches the Telegram message.

        Args:
            text: Message body.
        """
        async with Bot(token=self.bot_token) as bot:
            await bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode="Markdown",
            )
