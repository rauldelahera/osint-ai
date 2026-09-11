"""Build an entity co-occurrence graph from stored articles and render it with pyvis."""
from itertools import combinations

import networkx as nx
from pyvis.network import Network

from osint_ai import store

_LABEL_COLORS = {
    "PERSON": "#1f77b4",
    "ORG": "#ff7f0e",
    "GPE": "#2ca02c",
    "LOC": "#2ca02c",
    "EVENT": "#d62728",
    "NORP": "#9467bd",
    "FAC": "#8c564b",
}


def build_entity_graph(min_mentions: int = 1) -> nx.Graph:
    """Nodes are entities; edges connect entities that co-occur in the same article."""
    entities = store.get_entities()

    by_article: dict[str, set[tuple[str, str]]] = {}
    mention_counts: dict[tuple[str, str], int] = {}
    for row in entities:
        key = (row["text"], row["label"])
        by_article.setdefault(row["article_id"], set()).add(key)
        mention_counts[key] = mention_counts.get(key, 0) + 1

    graph = nx.Graph()
    for (text, label), count in mention_counts.items():
        if count >= min_mentions:
            graph.add_node(text, label=label, mentions=count)

    for article_entities in by_article.values():
        present = sorted(e for e in article_entities if e[0] in graph.nodes)
        for (text_a, _), (text_b, _) in combinations(present, 2):
            if graph.has_edge(text_a, text_b):
                graph[text_a][text_b]["weight"] += 1
            else:
                graph.add_edge(text_a, text_b, weight=1)

    return graph


def render_graph_html(graph: nx.Graph, output_path: str) -> str:
    """Render the graph to a standalone interactive HTML file and return its path."""
    net = Network(height="650px", width="100%", cdn_resources="in_line")
    for node, attrs in graph.nodes(data=True):
        label = attrs.get("label", "")
        mentions = attrs.get("mentions", 1)
        net.add_node(
            node,
            label=node,
            title=f"{label} — {mentions} mention(s)",
            color=_LABEL_COLORS.get(label, "#7f7f7f"),
            size=10 + mentions * 2,
        )
    for source, target, attrs in graph.edges(data=True):
        net.add_edge(source, target, value=attrs.get("weight", 1))

    net.save_graph(output_path)
    return output_path
