"""Scrapers package for flat-scraper-bot."""
from .scout24_scraper import Scout24Scraper
from .immowelt_scraper import ImmoweltScraper
from .facebook_groups_scraper import FacebookGroupScraper

__all__ = ["Scout24Scraper", "ImmoweltScraper", "FacebookGroupScraper"]
