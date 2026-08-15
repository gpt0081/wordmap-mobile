#!/usr/bin/env python3

import core
import cleaning
import relations
import hybrid

# Order matters: clean/prune -> semantic relations -> sparse hybrid links.
cleaning.apply(core)
relations.apply(core)
hybrid.apply(core, relations)

import wordmap_mobile
import ui_patch

ui_patch.apply(wordmap_mobile)

if __name__ == "__main__":
    wordmap_mobile.main()
