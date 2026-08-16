from __future__ import annotations

import grammar
import language

VERSION = "0.10.0"


def surface_segments(sentence):
    """Contiguous generation tokens using the grammar-preserving resolver.

    Graph stopwords are intentionally not applied here. A word may be excluded
    from the association graph yet still be essential for sentence generation.
    """
    segments = []
    current = []

    for surface in grammar.raw_words(sentence):
        entries = language.resolve_surface_for_grammar(surface)
        if not entries:
            if current:
                segments.append(current)
                current = []
            continue

        entry = entries[0]
        lemma = entry.get("lemma")
        if not lemma:
            if current:
                segments.append(current)
                current = []
            continue
        current.append((lemma, surface))

    if current:
        segments.append(current)
    return segments


def _grammar_pos_from_forms(graph, lemma):
    forms = (
        graph.get("generation", {})
        .get("forms", {})
        .get(lemma, {})
    ) or {}
    ranked = sorted(forms.items(), key=lambda x: -int(x[1]))[:8]
    for surface, _count in ranked:
        rows = language.resolve_surface_for_grammar(surface)
        for row in rows:
            if row.get("lemma") == lemma and row.get("pos") not in {None, "unknown"}:
                return str(row.get("pos"))
    return "unknown"


def apply(generation_module):
    original_node_pos = generation_module._node_pos

    def node_pos(graph, lemma):
        pos = str(original_node_pos(graph, lemma))
        if pos != "unknown":
            return pos
        return _grammar_pos_from_forms(graph, lemma)

    generation_module._surface_segments = surface_segments
    generation_module._node_pos = node_pos
    generation_module.GENERATION_TOKEN_VERSION = VERSION
    return generation_module
