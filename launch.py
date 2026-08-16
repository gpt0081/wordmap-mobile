#!/usr/bin/env python3

import core
import cleaning
import language
import relations
import hybrid
import sequence
import generation
import syntax_tags
import activation
import wordmap_gpt2
import lexicon_notes

# Order matters:
# 1) basic graph cleanup
# 2) dictionary-style surface -> lemma/POS resolution
# 3) semantic relation extraction on normalized lemmas
# 4) sparse association links
# 5) ordered next-word statistics from real sentence order
# 6) corpus-grounded sentence generation + semantic realization
# 7) Korean grammar tags, sentence-role patterns, question-intent filtering
# 8) dynamic context activation
# 9) WordMap GPT-2 style autoregressive next-token generation
# 10) expose lexicon + grammar metadata in Obsidian notes
cleaning.apply(core)
language.apply(core)
relations.apply(core)
hybrid.apply(core, relations)
sequence.apply(core)
generation.apply(core)
syntax_tags.apply(core)
activation.apply(core)
wordmap_gpt2.apply(core)
lexicon_notes.apply(core)

import wordmap_mobile
import ui_patch

ui_patch.apply(wordmap_mobile)

if __name__ == "__main__":
    wordmap_mobile.main()
