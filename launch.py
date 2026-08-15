#!/usr/bin/env python3

# Apply the v0.3.2 cleaning layer before the web server imports core functions.
import core
import cleaning

cleaning.apply(core)

import wordmap_mobile

if __name__ == "__main__":
    wordmap_mobile.main()
