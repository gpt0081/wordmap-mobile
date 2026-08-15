from __future__ import annotations

from collections import Counter, defaultdict

VERSION = "0.5.2"


def _ensure(graph):
    seq = graph.setdefault("sequence", {})
    seq.setdefault("version", VERSION)
    seq.setdefault("bigrams", {})
    return seq


def accumulate_sequence(graph, tokens):
    seq = _ensure(graph)
    bigrams = seq["bigrams"]

    for a, b in zip(tokens, tokens[1:]):
        if not a or not b or a == b:
            continue
        bucket = bigrams.setdefault(a, {})
        bucket[b] = int(bucket.get(b, 0)) + 1


def make_analyze(core, original_analyze):
    def analyze_into_graph(graph, text, window=4):
        stats = original_analyze(graph, text, window=window)

        for sentence in core.split_sentences(text):
            tokens = core.tokenize(sentence)
            if len(tokens) >= 2:
                accumulate_sequence(graph, tokens)

        seq = _ensure(graph)
        seq["version"] = VERSION
        return stats

    return analyze_into_graph


def rank_next_words(graph, source, limit=12):
    counts = (
        graph.get("sequence", {})
        .get("bigrams", {})
        .get(source, {})
    )
    if not counts:
        return []

    total = sum(int(v) for v in counts.values())
    ranked = sorted(
        ((target, int(count)) for target, count in counts.items()),
        key=lambda x: (-x[1], x[0]),
    )[:max(1, int(limit))]

    return [
        {
            "token": target,
            "count": count,
            "probability": round(count / total, 4) if total else 0.0,
        }
        for target, count in ranked
    ]


def make_ask(core, original_ask):
    def ask(vault, question, limit=20, depth=2):
        result = original_ask(
            vault,
            question,
            limit=limit,
            depth=depth,
        )
        graph = core.load_graph(vault)
        query_tokens = result.get("query_tokens", [])

        source = query_tokens[-1] if query_tokens else None
        result["next_word_source"] = source
        result["next_word_candidates"] = (
            rank_next_words(graph, source, limit=12)
            if source
            else []
        )
        return result

    return ask


def make_status(core, original_status):
    def status():
        out = original_status()
        vault = out.get("vault")
        if not vault:
            return out

        graph = core.load_graph(vault)
        bigrams = graph.get("sequence", {}).get("bigrams", {})
        out["sequence_version"] = VERSION
        out["next_word_sources"] = len(bigrams)
        out["next_word_pairs"] = sum(len(v) for v in bigrams.values())
        return out

    return status


def apply(core):
    original_analyze = core.analyze_into_graph
    original_ask = core.ask
    original_status = core.status

    core.analyze_into_graph = make_analyze(core, original_analyze)
    core.ask = make_ask(core, original_ask)
    core.status = make_status(core, original_status)
    return core
