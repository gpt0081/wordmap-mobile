from __future__ import annotations

from pathlib import Path

VERSION = "0.16.1"


def apply(experiment_harness, corpus_integrity, eval_manifest):
    def load_manifest(core, vault, split):
        return eval_manifest.load(core, Path(vault), split)

    experiment_harness._manifest = load_manifest
    corpus_integrity._manifest = load_manifest
    experiment_harness.VERSION = VERSION
    corpus_integrity.VERSION = VERSION
    return {
        "version": VERSION,
        "experiment_harness": True,
        "corpus_integrity": True,
    }
