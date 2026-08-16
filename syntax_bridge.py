from __future__ import annotations

import language

VERSION = "0.10.0"


def apply(syntax_tags_module):
    def aligned_tokens(graph, path, surfaces):
        tokens = []
        for lemma, surface in zip(path, surfaces):
            pos = str(graph.get("nodes", {}).get(lemma, {}).get("pos", "unknown"))
            confidence = 0.5
            if pos == "unknown":
                rows = language.resolve_surface_for_grammar(surface)
                if rows:
                    best = rows[0]
                    pos = str(best.get("pos", "unknown"))
                    confidence = float(best.get("confidence", 0.5))
            tokens.append(syntax_tags_module._entry_token(
                surface,
                {"lemma": lemma, "pos": pos, "confidence": confidence},
            ))
        syntax_tags_module._refine_roles(tokens)
        return tokens

    def pattern_from_aligned(graph, path, surfaces):
        return syntax_tags_module.normalized_pattern_from_tokens(
            aligned_tokens(graph, path, surfaces)
        )

    def raw_pattern_from_aligned(graph, path, surfaces):
        return syntax_tags_module.raw_pattern_from_tokens(
            aligned_tokens(graph, path, surfaces)
        )

    syntax_tags_module.pattern_from_aligned = pattern_from_aligned
    syntax_tags_module.raw_pattern_from_aligned = raw_pattern_from_aligned
    syntax_tags_module.SYNTAX_BRIDGE_VERSION = VERSION
    return syntax_tags_module
