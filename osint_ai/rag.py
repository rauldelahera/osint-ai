"""Local RAG: embed articles into Chroma, retrieve, and optionally answer via Ollama."""
import logging

import chromadb
import httpx
from chromadb.utils import embedding_functions

from config import CHROMA_DIR, EMBEDDING_MODEL, OLLAMA_HOST, OLLAMA_MODEL, RAG_TOP_K

logger = logging.getLogger(__name__)

_collection = None


def get_collection():
    """Lazily open the persistent Chroma collection (loading the embedding model is slow)."""
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )
        _collection = client.get_or_create_collection(
            name="articles",
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def index_articles(articles: list[dict]) -> int:
    """Embed articles into Chroma. Upsert by id, so re-running is safe and idempotent."""
    if not articles:
        return 0
    collection = get_collection()
    ids = [a["id"] for a in articles]
    documents = [f"{a['title']}. {a.get('summary', '')}".strip() for a in articles]
    metadatas = [
        {
            "title": a["title"],
            "source": a.get("source", ""),
            "link": a.get("link", ""),
            "published_at": a.get("published_at", ""),
        }
        for a in articles
    ]
    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    return len(ids)


def retrieve(question: str, top_k: int = RAG_TOP_K) -> list[dict]:
    """Return the top-k most relevant indexed articles with a 0-1 similarity score."""
    collection = get_collection()
    if collection.count() == 0:
        return []
    results = collection.query(query_texts=[question], n_results=min(top_k, collection.count()))
    hits = []
    for doc, meta, distance in zip(
        results["documents"][0], results["metadatas"][0], results["distances"][0]
    ):
        hits.append(
            {
                "title": meta.get("title", ""),
                "source": meta.get("source", ""),
                "link": meta.get("link", ""),
                "snippet": doc[:300],
                "score": round(max(0.0, 1 - distance), 3),
            }
        )
    return hits


def is_ollama_available() -> bool:
    """Check whether a local Ollama server is reachable. Never raises."""
    try:
        response = httpx.get(f"{OLLAMA_HOST}/api/tags", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


def generate_answer(question: str, hits: list[dict]) -> str:
    """Ask the local Ollama model to answer, grounded only in the retrieved sources."""
    context = "\n\n".join(
        f"[{i + 1}] {h['title']} ({h['source']}): {h['snippet']}" for i, h in enumerate(hits)
    )
    prompt = (
        "Answer the question using only the sources below. Cite sources by their "
        "number, e.g. [1]. If the sources don't contain the answer, say so.\n\n"
        f"Sources:\n{context}\n\nQuestion: {question}\nAnswer:"
    )
    response = httpx.post(
        f"{OLLAMA_HOST}/api/generate",
        json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
        timeout=60,
    )
    response.raise_for_status()
    return response.json().get("response", "").strip()


def ask(question: str, top_k: int = RAG_TOP_K) -> dict:
    """Retrieve relevant articles and, if Ollama is available, generate a grounded answer."""
    hits = retrieve(question, top_k)
    llm_available = is_ollama_available()
    answer = None
    if llm_available and hits:
        try:
            answer = generate_answer(question, hits)
        except Exception as exc:
            logger.warning("Ollama generation failed: %s", exc)
            llm_available = False
    return {"hits": hits, "answer": answer, "llm_available": llm_available}
