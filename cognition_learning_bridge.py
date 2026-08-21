from __future__ import annotations

VERSION = "0.18.0"


def apply(credit_learning):
    if getattr(credit_learning, "_cognition_origin_patched", False):
        return credit_learning
    original = credit_learning._origin_key

    def origin_key(origin):
        text = str(origin or "")
        if text.startswith("점화"):
            return "점화"
        if text.startswith("연상 폭포"):
            return "연상 폭포"
        return original(origin)

    credit_learning._origin_key = origin_key
    credit_learning._cognition_origin_patched = True
    credit_learning.cognition_learning_version = VERSION
    return credit_learning
