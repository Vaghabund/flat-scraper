"""Telegram bot interface for flat-scraper-bot."""

import asyncio
import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.helpers import escape_markdown

from database import get_recent_listings
from logger import get_logger

logger = get_logger(__name__)


class TelegramBot:
    """Telegram bot that exposes scraper controls via chat commands."""

    def __init__(
        self,
        token: str,
        chat_id: str,
        db_path: str,
        filter_service,
        scheduler=None,
    ) -> None:
        """Initialise the bot and build the application.

        Args:
            token: Telegram bot API token.
            chat_id: Default chat ID for outgoing messages.
            db_path: Path to the SQLite database.
            filter_service: :class:`~filters.FilterService` instance.
            scheduler: Optional :class:`~scheduler.ScraperScheduler` instance.
        """
        self.token = token
        self.chat_id = chat_id
        self.db_path = db_path
        self.filter_service = filter_service
        self.scheduler = scheduler
        self.application = Application.builder().token(token).build()
        self.setup_handlers()

    def setup_handlers(self) -> None:
        """Register all command handlers on the application."""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("filter", self.filter_command))
        self.application.add_handler(CommandHandler("list", self.list_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("stop", self.stop_command))
        self.application.add_handler(CommandHandler("refresh", self.refresh_command))
        self.application.add_error_handler(self.error_handler)

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle unexpected Telegram update processing errors."""
        logger.error("Unhandled Telegram update error: %s", context.error)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start — send a welcome message with current criteria."""
        try:
            summary = self.filter_service.get_criteria_summary()
            await update.message.reply_text(
                f"👋 Welcome to *Flat Scraper Bot*!\n\n"
                f"I'll notify you when new flats matching your criteria are found.\n\n"
                f"📋 *Current criteria:*\n{summary}\n\n"
                f"Use /help to see all available commands.",
                parse_mode="Markdown",
            )
        except Exception as exc:
            logger.error("Error in /start handler: %s", exc)
            await update.message.reply_text("⚠️ An error occurred. Please try again.")

    async def filter_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /filter — display active search criteria."""
        try:
            summary = self.filter_service.get_criteria_summary()
            await update.message.reply_text(
                f"📋 *Active search criteria:*\n\n{summary}", parse_mode="Markdown"
            )
        except Exception as exc:
            logger.error("Error in /filter handler: %s", exc)
            await update.message.reply_text("⚠️ An error occurred. Please try again.")

    async def list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /list — show the 5 most recently scraped listings."""
        try:
            recent_listings = get_recent_listings(self.db_path, limit=100)
            listings = [
                listing
                for listing in recent_listings
                if self.filter_service.apply_filters(listing)
            ][:5]
            if not listings:
                await update.message.reply_text(
                    "📭 No listings match your active filters yet."
                )
                return

            lines = ["🏠 *Recent listings:*\n"]
            for i, listing in enumerate(listings, start=1):
                price = listing.get("price")
                price_str = f"€{price:,.0f}" if price is not None else "N/A"
                address = escape_markdown(listing.get("address") or "N/A", version=1)
                url = listing.get("url", "")
                lines.append(f"{i}. [{address} — {price_str}]({url})")

            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        except Exception as exc:
            logger.error("Error in /list handler: %s", exc)
            await update.message.reply_text("⚠️ An error occurred. Please try again.")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help — list all available commands."""
        try:
            help_text = (
                "🤖 *Flat Scraper Bot — Commands*\n\n"
                "/start — Welcome message & current criteria\n"
                "/filter — Show active search criteria\n"
                "/list — Show 5 most recent listings\n"
                "/refresh — Trigger a manual scrape now\n"
                "/stop — Show how to stop the bot\n"
                "/help — Show this help message"
            )
            await update.message.reply_text(help_text, parse_mode="Markdown")
        except Exception as exc:
            logger.error("Error in /help handler: %s", exc)
            await update.message.reply_text("⚠️ An error occurred. Please try again.")

    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /stop — inform the user that stopping requires scheduler reconfiguration."""
        try:
            await update.message.reply_text(
                "ℹ️ To stop receiving notifications, stop the bot process or "
                "remove your credentials from the .env file.\n"
                "Use /start to see the current monitoring criteria."
            )
        except Exception as exc:
            logger.error("Error in /stop handler: %s", exc)
            await update.message.reply_text("⚠️ An error occurred. Please try again.")

    async def refresh_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /refresh — trigger an immediate scrape cycle."""
        try:
            if self.scheduler is not None:
                self.scheduler.trigger_now()
                await update.message.reply_text("🔄 Manual scrape triggered!")
            else:
                await update.message.reply_text("⚠️ Scheduler is not available.")
        except Exception as exc:
            logger.error("Error in /refresh handler: %s", exc)
            await update.message.reply_text("⚠️ An error occurred. Please try again.")

    def run(self) -> None:
        """Start the bot in polling mode (blocks until interrupted)."""
        logger.info("Starting Telegram bot polling …")
        self.application.run_polling()

    def send_message(self, text: str, parse_mode: str = "Markdown") -> None:
        """Send a standalone message to the configured chat.

        If no event loop is running, uses :func:`asyncio.run`; if a loop is
        already active, schedules the coroutine with
        :func:`asyncio.run_coroutine_threadsafe`.

        Args:
            text: Message body.
            parse_mode: Telegram parse mode (default ``"Markdown"``).
        """
        async def _send() -> None:
            await self.application.bot.send_message(
                chat_id=self.chat_id, text=text, parse_mode=parse_mode
            )

        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                asyncio.run(_send())
            else:
                future = asyncio.run_coroutine_threadsafe(_send(), loop)
                future.result(timeout=30)
        except Exception as exc:
            logger.error("Error sending message: %s", exc)
