"""Fetch and normalise articles from configured public RSS feeds."""
import hashlib
import logging
import time
from datetime import datetime, timezone

import feedparser
import httpx

from config import REQUEST_DELAY_SECONDS, REQUEST_TIMEOUT_SECONDS, RSS_FEEDS, USER_AGENT

logger = logging.getLogger(__name__)


def _make_article_id(link: str) -> str:
    return hashlib.sha256(link.encode("utf-8")).hexdigest()[:16]


def _parse_published(entry) -> str:
    """Return an ISO 8601 timestamp, falling back to now if the feed omits one."""
    for field in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, field, None)
        if parsed:
            return datetime(*parsed[:6], tzinfo=timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


def fetch_feed(name: str, url: str) -> list[dict]:
    """Fetch a single RSS feed and return normalised article dicts. Never raises."""
    articles = []
    try:
        response = httpx.get(
            url,
            timeout=REQUEST_TIMEOUT_SECONDS,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
        response.raise_for_status()
        parsed = feedparser.parse(response.content)
    except Exception as exc:  # network/parse errors shouldn't take down the whole fetch
        logger.warning("Failed to fetch feed %s (%s): %s", name, url, exc)
        return articles

    for entry in parsed.entries:
        link = getattr(entry, "link", None)
        title = getattr(entry, "title", None)
        if not link or not title:
            continue
        articles.append(
            {
                "id": _make_article_id(link),
                "title": title.strip(),
                "link": link.strip(),
                "summary": (getattr(entry, "summary", "") or "").strip(),
                "source": name,
                "published_at": _parse_published(entry),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    return articles


def fetch_all_feeds(feeds: list[dict] | None = None) -> list[dict]:
    """Fetch all configured feeds sequentially, with a politeness delay between requests."""
    feeds = feeds if feeds is not None else RSS_FEEDS
    all_articles = []
    for i, feed in enumerate(feeds):
        all_articles.extend(fetch_feed(feed["name"], feed["url"]))
        if i < len(feeds) - 1:
            time.sleep(REQUEST_DELAY_SECONDS)
    return all_articles
