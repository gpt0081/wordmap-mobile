#!/usr/bin/env python3

import core
import cleaning
import relations

# Order matters: normalize/prune first, then add semantic directionality.
cleaning.apply(core)
relations.apply(core)

import wordmap_mobile
import ui_patch

ui_patch.apply(wordmap_mobile)

if __name__ == "__main__":
    wordmap_mobile.main()
