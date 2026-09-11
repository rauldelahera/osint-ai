# Project summary: OSINT-AI

## Pitch

An AI-assisted open-source analysis tool: ingests public news feeds, extracts entities and
relationships, maps them as an interactive knowledge graph, enriches with sentiment and
geolocation, and answers natural-language questions over the corpus via local RAG. Fully local
and free to run, with no cloud, no employer systems, and no API keys.

## Why it exists

Demonstrates end-to-end applied AI on open data: ingestion, NLP entity and relationship
extraction, knowledge graph, geospatial, and retrieval-augmented Q&A, wrapped in a clean UI.

## Stack

Python, Streamlit, spaCy (NER), networkx + pyvis (graph), SQLite (local storage),
sentence-transformers + ChromaDB (RAG), Ollama (local LLM), VADER (sentiment), geopy +
Nominatim (geocoding), folium (map). Later: LLM-based relationship extraction for M4.

## Status: milestones

- [x] **M1 - MVP:** ingest configured RSS feeds, run spaCy NER, and show an article table plus
      an interactive entity co-occurrence graph, all in Streamlit. No LLM required.
- [x] **M2 - RAG:** embed articles into Chroma with `sentence-transformers`, retrieve the
      most relevant ones for a question, and generate a grounded answer with a local Ollama
      model. Retrieval-details panel (source titles, scores, snippets). Falls back to
      retrieval-only when Ollama isn't running.
- [x] **M3 - Enrichment:** sentiment per article via VADER, shown as a compound score and a
      tone label (🟢/🟡/🔴) in the article table. Place entities (GPE/LOC) are geocoded with
      geopy + Nominatim (rate-limited to 1 request/sec, cached locally in SQLite) and rendered
      as an interactive folium map sized by mention count. Degrades gracefully if geocoding is
      unavailable.
- [ ] **M4 - Richer graph + polish:** LLM-based subject-relation-object triples for a real
      link-analysis graph, plus a methodology write-up in the README.
- [x] **M5 - Analyst write-up:** ran the tool on one public topic and wrote a short
      methodology piece at `examples/analysis-2026-09-11.md`: sources, method, findings, and an
      honest limitations section (entity-resolution errors, co-occurrence not implying a real
      relationship, Western-source bias).

## Guardrails

- Public / open data only. No private individuals, no logins, respects feed politeness
  (rate limiting, identifying User-Agent).
- Local-first, zero cloud required. LLM features (RAG, relationship extraction) are optional
  and degrade gracefully: the app is fully usable without Ollama installed.
- No employer systems, credentials, or data are used anywhere in this project.
