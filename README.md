# 🏠 Flat Scraper Bot

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Telegram](https://img.shields.io/badge/Telegram-Bot-blue?logo=telegram)

A production-ready Python bot that monitors German real estate websites for rental apartment listings and sends instant Telegram notifications when new flats matching your criteria appear.

**Scraped sites:**
- [ImmobilienScout24](https://www.immobilienscout24.de)
- [Immowelt](https://www.immowelt.de)
- [Immonet](https://www.immonet.de)

---

## Features

- 🔍 Scrapes three major German real estate portals simultaneously
- 📬 Instant Telegram notifications for new matching listings
- 🔁 Configurable scraping interval (default: every 30 minutes)
- 🧹 Duplicate prevention — every URL is stored and checked before insertion
- 🎛️ Flexible filters: rooms, floor, price, area, excluded keywords
- 💾 SQLite database for persistent storage
- 🤖 Telegram bot commands for live control
- 📋 Rotating log files with configurable log level
- ⚡ Graceful shutdown on SIGINT / SIGTERM

---

## Prerequisites

- Python 3.9 or higher
- A Telegram bot token — create one via [@BotFather](https://t.me/BotFather):
  1. Open Telegram and start a chat with `@BotFather`
  2. Send `/newbot` and follow the prompts
  3. Copy the token provided
  4. Send any message to your bot, then retrieve your Chat ID from:
     `https://api.telegram.org/bot<TOKEN>/getUpdates`

---

## Quick Start

```bash
git clone https://github.com/Vaghabund/flat-scraper.git
cd flat-scraper
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
python main.py
```

---

## Configuration

All configuration is done through environment variables (or a `.env` file).

| Variable | Description | Default |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram bot API token (**required**) | — |
| `TELEGRAM_CHAT_ID` | Target Telegram chat ID (**required**) | — |
| `DATABASE_URL` | SQLite database path | `sqlite:///data/flats.db` |
| `SCRAPE_INTERVAL_MINUTES` | How often to scrape (minutes) | `30` |
| `MIN_ROOMS` | Minimum number of rooms | `2` |
| `MAX_ROOMS` | Maximum number of rooms | `4` |
| `MIN_FLOOR` | Minimum floor number (0 = ground floor) | `2` |
| `MAX_PRICE` | Maximum monthly rent in € | `1500` |
| `AREAS` | Comma-separated list of accepted neighbourhoods | *(empty = any)* |
| `EXCLUDE_KEYWORDS` | Comma-separated keywords to exclude | *(empty = none)* |
| `LOG_LEVEL` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |
| `LOG_FILE` | Log file path | `logs/scraper.log` |
| `SCOUT24_BASE_URL` | ImmobilienScout24 search URL | Berlin wohnung-mieten |
| `IMMOWELT_BASE_URL` | Immowelt search URL | Berlin wohnungen mieten |
| `IMMONET_BASE_URL` | Immonet search URL | Berlin mieten |

---

## Telegram Commands

| Command | Description |
|---|---|
| `/start` | Welcome message with active criteria |
| `/filter` | Display current search filters |
| `/list` | Show the 5 most recent listings |
| `/refresh` | Trigger an immediate manual scrape |
| `/stop` | Pause notifications |
| `/help` | Show all available commands |

---

## Project Structure

```
flat-scraper/
├── .env.example          # Environment variable template
├── .gitignore
├── requirements.txt      # Python dependencies
├── README.md
├── config.py             # Loads & validates all settings
├── main.py               # Entry point — wires everything together
├── telegram_bot.py       # Telegram bot command handlers
├── database.py           # SQLite interface (listings table)
├── filters.py            # Listing filter logic
├── notifier.py           # Telegram notification formatting & dispatch
├── scheduler.py          # APScheduler background job
├── utils.py              # Helper functions (price parsing, slugify, …)
├── logger.py             # Logging setup (console + rotating file)
└── scrapers/
    ├── __init__.py
    ├── base_scraper.py   # Abstract base class with shared HTTP helpers
    ├── scout24_scraper.py
    ├── immowelt_scraper.py
    └── immonet_scraper.py
```

---

## How It Works

1. **Startup** — `main.py` initialises the database, scrapers, filter service, notifier, and scheduler, then starts the Telegram bot polling loop.
2. **Scraping** — `ScraperScheduler` fires a scrape cycle at the configured interval. Each scraper fetches up to 3 pages of results, extracts listing data, and returns normalised dicts.
3. **Deduplication** — Before every database insert, `is_duplicate(url)` is called to avoid storing the same listing twice.
4. **Filtering** — After each cycle, `get_new_listings()` retrieves un-notified listings. `FilterService.apply_filters()` checks rooms, floor, price, area, and excluded keywords.
5. **Notification** — Matching listings are formatted as Markdown messages and sent via the Telegram Bot API. `mark_notified()` is called immediately after to prevent duplicate alerts.
6. **Bot commands** — The Telegram bot runs concurrently and responds to chat commands for live control and inspection.

---

## Troubleshooting

**Bot doesn't start**
- Check that `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set in your `.env` file.
- Verify the token is valid by visiting `https://api.telegram.org/bot<TOKEN>/getMe`.

**No listings found**
- The target websites may have changed their HTML structure — inspect the page source and update CSS selectors in the scraper files.
- Your filter criteria may be too strict. Try relaxing `MIN_FLOOR` or increasing `MAX_PRICE`.

**Rate limited / blocked**
- Increase `SCRAPE_INTERVAL_MINUTES` to reduce request frequency.
- The scrapers already rotate User-Agent headers and add 2–3 second delays between requests.

---

## Legal Notice

This project is intended for personal, educational use only. Always respect the `robots.txt` and Terms of Service of each website. Excessive automated requests may violate the ToS and could result in your IP being blocked. Use responsibly.

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-change`
3. Commit your changes: `git commit -m "feat: describe your change"`
4. Push to the branch: `git push origin feature/my-change`
5. Open a Pull Request

---

## License

This project is licensed under the [MIT License](LICENSE).
