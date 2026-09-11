"""Central configuration: RSS feeds, model names, and local storage paths."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "osint.db"
GRAPH_HTML_PATH = DATA_DIR / "entity_graph.html"
MAP_HTML_PATH = DATA_DIR / "place_map.html"

# Reputable public news RSS feeds (general world news coverage).
RSS_FEEDS = [
    {"name": "BBC World", "url": "http://feeds.bbci.co.uk/news/world/rss.xml"},
    {"name": "NPR World", "url": "https://feeds.npr.org/1004/rss.xml"},
    {"name": "Al Jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
    {"name": "The Guardian World", "url": "https://www.theguardian.com/world/rss"},
    {"name": "NYT World", "url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"},
]

# Ingestion behaviour (politeness: identify ourselves, don't hammer feeds)
REQUEST_TIMEOUT_SECONDS = 10
REQUEST_DELAY_SECONDS = 1.0
USER_AGENT = "osint-ai/0.1 (personal research project; local use only)"

# NLP
SPACY_MODEL = "en_core_web_sm"

# RAG: local embeddings + vector store + optional local LLM
CHROMA_DIR = DATA_DIR / "chroma"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
RAG_TOP_K = 5
OLLAMA_HOST = "http://localhost:11434"
OLLAMA_MODEL = "llama3.1"

# Enrichment: sentiment labels + geocoding (Nominatim usage policy: max 1 request/sec)
SENTIMENT_POSITIVE_THRESHOLD = 0.05
SENTIMENT_NEGATIVE_THRESHOLD = -0.05
GEOCODE_LABELS = {"GPE", "LOC"}
GEOCODE_USER_AGENT = USER_AGENT
GEOCODE_DELAY_SECONDS = 1.0
GEOCODE_TIMEOUT_SECONDS = 10

