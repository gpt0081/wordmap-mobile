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
import activation
import wordmap_gpt2
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
# 10) dynamic context activation
# 11) WordMap GPT-2 autoregressive generation with expanded candidates
# 12) layered visual debugger trace + graph snapshot API
# 13) expose lexicon + grammar metadata in Obsidian notes
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
activation.apply(core)
wordmap_gpt2.apply(core)
visualizer.apply(core)
lexicon_notes.apply(core)

import wordmap_mobile
import ui_patch

ui_patch.apply(wordmap_mobile)

if __name__ == "__main__":
    wordmap_mobile.main()
