"""spaCy-based named entity extraction over ingested articles."""
from osint_ai import store
from config import SPACY_MODEL

_ENTITY_LABELS = {"PERSON", "ORG", "GPE", "LOC", "EVENT", "NORP", "FAC"}

_nlp = None


def get_nlp():
    """Lazily load the spaCy pipeline, since loading it is the expensive part."""
    global _nlp
    if _nlp is None:
        import spacy

        try:
            _nlp = spacy.load(SPACY_MODEL)
        except OSError as exc:
            raise RuntimeError(
                f"spaCy model '{SPACY_MODEL}' not found. Run: python -m spacy download {SPACY_MODEL}"
            ) from exc
    return _nlp


def extract_entities(text: str) -> list[tuple[str, str]]:
    """Return (text, label) pairs for entities of interest found in the given text."""
    nlp = get_nlp()
    doc = nlp(text)
    return [
        (ent.text.strip(), ent.label_)
        for ent in doc.ents
        if ent.label_ in _ENTITY_LABELS and ent.text.strip()
    ]


def process_articles(articles: list[dict], force: bool = False) -> int:
    """Run NER on articles that don't already have stored entities. Returns count processed."""
    processed = 0
    for article in articles:
        if not force and store.has_entities(article["id"]):
            continue
        text = f"{article['title']}. {article.get('summary', '')}"
        entities = extract_entities(text)
        store.save_entities(article["id"], entities)
        processed += 1
    return processed
