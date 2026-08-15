#!/usr/bin/env python3

import core
import cleaning
import language
import relations
import hybrid
import lexicon_notes

# Order matters:
# 1) basic graph cleanup
# 2) dictionary-style surface -> lemma/POS resolution
# 3) semantic relation extraction on normalized lemmas
# 4) sparse association links
# 5) expose lexicon metadata in Obsidian notes
cleaning.apply(core)
language.apply(core)
relations.apply(core)
hybrid.apply(core, relations)
lexicon_notes.apply(core)

import wordmap_mobile
import ui_patch

ui_patch.apply(wordmap_mobile)

if __name__ == "__main__":
    wordmap_mobile.main()
