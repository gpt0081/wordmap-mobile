#!/usr/bin/env python3

import core
import cleaning
import corpus_filter
import language
import corpus_manager
import relations
import relation_guard
import hybrid
import sequence
import generation
import generation_tokens
import syntax_tags
import syntax_bridge
import event_graph
import activation
import wordmap_gpt2
import event_guidance
import visualizer
import lexicon_notes
import node_health

# Order matters:
# 1) basic graph cleanup
# 2) analysis-only corpus scaffolding filter (source Corpus is untouched)
# 3) dictionary-style surface -> lemma/POS resolution with graph/grammar split
# 4) corpus manager: per-file enable/disable + edit/delete + rebuild dirty state
# 5) metalinguistic relation guard + semantic relation extraction
# 6) sparse association links
# 7) ordered graph next-word statistics
# 8) grammar-preserving generation token stream + sentence statistics
# 9) Korean grammar tags and normalized sentence patterns
# 10) bridge graph-less grammar words back into generation pattern checks
# 11) Situation/Event Graph: predicate + actor/place/target roles
# 12) dynamic context activation
# 13) WordMap GPT-2 autoregressive generation
# 14) event-guided context/start-node correction + direct event retrieval
# 15) layered visual debugger trace + graph snapshot API
# 16) expose lexicon + grammar metadata in Obsidian notes
# 17) node health/orphan analyzer: real/weak/visual/tag-filter isolation diagnosis
cleaning.apply(core)
corpus_filter.apply(core)
language.apply(core)
corpus_manager.apply(core)
relation_guard.apply(relations)
relations.apply(core)
hybrid.apply(core, relations)
sequence.apply(core)
generation_tokens.apply(generation)
generation.apply(core)
syntax_tags.apply(core)
syntax_bridge.apply(syntax_tags)
event_graph.apply(core)
activation.apply(core)
wordmap_gpt2.apply(core)
event_guidance.apply(core)
visualizer.apply(core)
lexicon_notes.apply(core)
node_health.apply(core)

import wordmap_mobile
import ui_patch
import corpus_web
import visual_ui
import node_health_web

ui_patch.apply(wordmap_mobile)
corpus_web.apply(wordmap_mobile, core)
visual_ui.apply(wordmap_mobile)
node_health_web.apply(wordmap_mobile, core)

if __name__ == "__main__":
    wordmap_mobile.main()
