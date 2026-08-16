#!/usr/bin/env python3

import core
import cleaning
import corpus_filter
import language
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

# Order matters:
# 1) basic graph cleanup
# 2) analysis-only corpus scaffolding filter (source Corpus is untouched)
# 3) dictionary-style surface -> lemma/POS resolution with graph/grammar split
# 4) metalinguistic relation guard + semantic relation extraction
# 5) sparse association links
# 6) ordered graph next-word statistics
# 7) grammar-preserving generation token stream + sentence statistics
# 8) Korean grammar tags and normalized sentence patterns
# 9) bridge graph-less grammar words back into generation pattern checks
# 10) Situation/Event Graph: predicate + actor/place/target roles
# 11) dynamic context activation
# 12) WordMap GPT-2 autoregressive generation
# 13) event-guided context/start-node correction + direct event retrieval
# 14) layered visual debugger trace + graph snapshot API
# 15) expose lexicon + grammar metadata in Obsidian notes
cleaning.apply(core)
corpus_filter.apply(core)
language.apply(core)
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

import wordmap_mobile
import ui_patch
import visual_ui

ui_patch.apply(wordmap_mobile)
visual_ui.apply(wordmap_mobile)

if __name__ == "__main__":
    wordmap_mobile.main()
