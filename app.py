"""Streamlit UI: ingest public news, run NER, browse the entity graph, and ask questions (RAG)."""
from pathlib import Path

import pandas as pd
import streamlit as st

import config
from osint_ai import enrich, extract, graph, ingest, rag, store

st.set_page_config(page_title="OSINT-AI", layout="wide")
store.init_db()

st.title("OSINT-AI — public news entity graph")
st.caption(
    "Ingests public RSS news, extracts entities with spaCy, maps how they co-occur, and "
    "answers questions over the corpus via local RAG. Runs fully offline — Ollama is optional."
)

with st.sidebar:
    st.header("Data")
    if st.button("Fetch latest news", type="primary"):
        with st.spinner("Fetching configured RSS feeds..."):
            fetched = ingest.fetch_all_feeds()
            inserted = store.save_articles(fetched)
        st.success(f"Fetched {len(fetched)} articles, {inserted} new.")

    if st.button("Extract entities (spaCy NER)"):
        with st.spinner("Running NER over stored articles..."):
            try:
                processed = extract.process_articles(store.get_articles())
                st.success(f"Extracted entities from {processed} article(s).")
            except RuntimeError as exc:
                st.error(str(exc))

    if st.button("Index articles for search (embeddings)"):
        with st.spinner("Embedding articles into the local vector store..."):
            indexed = rag.index_articles(store.get_articles())
        st.success(f"Indexed {indexed} article(s) for search.")

    if st.button("Analyze sentiment (VADER)"):
        with st.spinner("Scoring sentiment over stored articles..."):
            scored = enrich.analyze_sentiment(store.get_articles())
        st.success(f"Scored sentiment for {scored} article(s).")

    if st.button("Geocode places (Nominatim)"):
        with st.spinner("Geocoding place entities (max 1 request/sec)..."):
            attempted = enrich.geocode_places()
        st.success(f"Attempted geocoding for {attempted} new place(s).")

    st.caption(f"Feeds configured: {len(config.RSS_FEEDS)}")

articles = store.get_articles()

st.subheader(f"Ingested articles ({len(articles)})")
if articles:
    df = pd.DataFrame(articles)[["title", "source", "published_at", "sentiment", "link"]]
    df["tone"] = df["sentiment"].apply(enrich.sentiment_label)
    st.dataframe(
        df[["title", "source", "published_at", "tone", "sentiment", "link"]],
        width="stretch",
        hide_index=True,
    )
else:
    st.info("No articles yet — click 'Fetch latest news' in the sidebar.")

st.subheader("Entity graph")
entities = store.get_entities()
if not entities:
    st.info("No entities yet — click 'Extract entities' in the sidebar after fetching news.")
else:
    entity_graph = graph.build_entity_graph()
    if entity_graph.number_of_nodes() == 0:
        st.info("No entity co-occurrences found yet.")
    else:
        output_path = graph.render_graph_html(entity_graph, str(config.GRAPH_HTML_PATH))
        st.iframe(Path(output_path), height=680)
        st.caption(
            f"{entity_graph.number_of_nodes()} entities, "
            f"{entity_graph.number_of_edges()} co-occurrence links."
        )

st.subheader("Geographic mentions")
if not entities:
    st.info("No entities yet — click 'Extract entities' in the sidebar after fetching news.")
else:
    places = enrich.build_place_summary()
    if not places:
        st.info(
            "No geocoded places yet — click 'Geocode places' in the sidebar. Requires "
            "internet access to the free Nominatim service; place lookups are cached locally."
        )
    else:
        map_path = enrich.render_place_map(places, str(config.MAP_HTML_PATH))
        st.iframe(Path(map_path), height=500)
        st.caption(f"{len(places)} geocoded place(s), sized by mention count.")

st.subheader("Ask a question (local RAG)")
if not articles:
    st.info("Fetch some articles first, then index them for search.")
else:
    question = st.text_input("Question", placeholder="e.g. What is happening with...?")
    if st.button("Search & answer", type="primary") and question:
        with st.spinner("Retrieving relevant articles..."):
            result = rag.ask(question)

        if not result["hits"]:
            st.info("No indexed articles yet — click 'Index articles for search' in the sidebar.")
        else:
            st.markdown("**Retrieved sources**")
            hits_df = pd.DataFrame(result["hits"])[["title", "source", "score", "snippet"]]
            st.dataframe(hits_df, width="stretch", hide_index=True)

            st.markdown("**Answer**")
            if result["llm_available"] and result["answer"]:
                st.write(result["answer"])
            else:
                st.info(
                    "LLM not available — showing retrieved sources only. Install Ollama "
                    "(`brew install ollama && ollama pull llama3.1 && ollama serve`) "
                    "for generated answers."
                )
