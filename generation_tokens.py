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


def apply(generation_module):
    generation_module._surface_segments = surface_segments
    generation_module.GENERATION_TOKEN_VERSION = VERSION
    return generation_module
