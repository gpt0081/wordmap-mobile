from __future__ import annotations

VERSION = "0.18.0"


def apply(core, associative_cascade):
    if getattr(core, "_cognition_cache_guard_patched", False):
        return core
    original_ask = core.ask
    original_direct = getattr(core, "associative_cascade", None)

    def clear():
        associative_cascade._CACHE.clear()
        associative_cascade._REL_CACHE.clear()

    def ask(vault, question, limit=20, depth=2):
        clear()
        return original_ask(vault, question, limit=limit, depth=depth)

    core.ask = ask
    if original_direct:
        def direct(vault, **kwargs):
            clear()
            return original_direct(vault, **kwargs)
        core.associative_cascade = direct

    core.cognition_cache_clear = clear
    core.cognition_cache_guard_version = VERSION
    core._cognition_cache_guard_patched = True
    return core
