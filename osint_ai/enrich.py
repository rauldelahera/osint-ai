"""Enrichment: VADER sentiment scoring and Nominatim geocoding of place entities."""
import logging

from config import (
    GEOCODE_DELAY_SECONDS,
    GEOCODE_LABELS,
    GEOCODE_TIMEOUT_SECONDS,
    GEOCODE_USER_AGENT,
)
from osint_ai import store

logger = logging.getLogger(__name__)

_analyzer = None
_geolocator = None


def get_sentiment_analyzer():
    """Lazily load the VADER analyzer (import is slow-ish, so defer it)."""
    global _analyzer
    if _analyzer is None:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

        _analyzer = SentimentIntensityAnalyzer()
    return _analyzer


def score_sentiment(text: str) -> float:
    """Return the VADER compound score (-1 negative to +1 positive) for a piece of text."""
    analyzer = get_sentiment_analyzer()
    return analyzer.polarity_scores(text)["compound"]


def analyze_sentiment(articles: list[dict], force: bool = False) -> int:
    """Score sentiment for articles missing it (or all of them if force=True). Returns count scored."""
    targets = articles if force else store.get_articles_without_sentiment()
    scored = 0
    for article in targets:
        text = f"{article['title']}. {article.get('summary', '')}"
        score = score_sentiment(text)
        store.save_sentiment(article["id"], score)
        scored += 1
    return scored


def sentiment_label(score: float | None) -> str:
    """Map a compound score to a short human label with an emoji cue."""
    if score is None:
        return "—"
    if score >= 0.05:
        return "🟢 positive"
    if score <= -0.05:
        return "🔴 negative"
    return "🟡 neutral"


def _get_geolocator():
    """Lazily build a rate-limited Nominatim geocoder (max 1 request/sec, per its usage policy)."""
    global _geolocator
    if _geolocator is None:
        from geopy.extra.rate_limiter import RateLimiter
        from geopy.geocoders import Nominatim

        geolocator = Nominatim(
            user_agent=GEOCODE_USER_AGENT, timeout=GEOCODE_TIMEOUT_SECONDS
        )
        _geolocator = RateLimiter(
            geolocator.geocode, min_delay_seconds=GEOCODE_DELAY_SECONDS
        )
    return _geolocator


def geocode_place(place: str) -> tuple[float, float] | None:
    """Geocode one place name, using the local cache first. Never raises; returns None on failure."""
    cached = store.get_geocode(place)
    if cached is not None:
        return (cached["lat"], cached["lon"]) if cached["resolved"] else None

    try:
        geocode = _get_geolocator()
        location = geocode(place)
    except Exception as exc:  # offline, timeout, or Nominatim service error
        logger.warning("Geocoding failed for %r: %s", place, exc)
        store.save_geocode(place, None, None, resolved=False)
        return None

    if location is None:
        store.save_geocode(place, None, None, resolved=False)
        return None

    store.save_geocode(place, location.latitude, location.longitude, resolved=True)
    return (location.latitude, location.longitude)


def geocode_places(force: bool = False) -> int:
    """Geocode every place entity (GPE/LOC) not already cached. Returns count newly attempted."""
    place_counts = store.get_place_mention_counts()
    attempted = 0
    for row in place_counts:
        place = row["text"]
        if not force and store.get_geocode(place) is not None:
            continue
        geocode_place(place)
        attempted += 1
    return attempted


def build_place_summary() -> list[dict]:
    """Return resolved places with lat/lon and mention counts, for map rendering."""
    mention_counts = {row["text"]: row["mentions"] for row in store.get_place_mention_counts()}
    places = []
    for row in store.get_resolved_geocodes():
        places.append(
            {
                "place": row["place"],
                "lat": row["lat"],
                "lon": row["lon"],
                "mentions": mention_counts.get(row["place"], 1),
            }
        )
    return places


def render_place_map(places: list[dict], output_path: str) -> str:
    """Render geocoded places as an interactive folium map, sized by mention count."""
    import folium

    center = [places[0]["lat"], places[0]["lon"]] if places else [20, 0]
    zoom = 3 if places else 1
    fmap = folium.Map(location=center, zoom_start=zoom)
    for place in places:
        radius = 5 + min(place["mentions"], 20) * 2
        folium.CircleMarker(
            location=[place["lat"], place["lon"]],
            radius=radius,
            popup=f"{place['place']} — {place['mentions']} mention(s)",
            tooltip=place["place"],
            color="#2ca02c",
            fill=True,
            fill_opacity=0.6,
        ).add_to(fmap)
    fmap.save(output_path)
    return output_path
