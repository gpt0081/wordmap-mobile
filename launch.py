#!/usr/bin/env python3

import core
import cleaning
import corpus_filter
import language
import corpus_manager
import corpus_roles
import corpus_v1
import corpus_v1_quality
import corpus_integrity
import relations
import relation_guard
import hybrid
import sequence
import generation
import generation_tokens
import syntax_tags
import syntax_bridge
import event_graph
import temporal_event
import activation
import context_map
import wordmap_gpt2
import event_guidance
import dialogue_session
import visualizer
import lexicon_notes
import node_health
import dialogue_corpus
import credit_learning
import experiment_harness

# Order matters:
# 1) basic graph cleanup
# 2) analysis-only document scaffolding cleanup
# 3) surface -> lemma/POS resolution
# 4) corpus manager + TRAIN/DEV/TEST hard role guard
# 5) Corpus v1 quality patch + installer + integrity/leak checker
# 6) guarded semantic relations + sparse associations
# 7) ordered word transitions + grammar-preserving generation stream
# 8) Korean syntax/grammar tags
# 9) temporal/owner event patch before Situation/Event Graph wiring
# 10) Situation/Event Graph
# 11) dynamic activation + persistent ContextMap gate
# 12) WordMap GPT-2-style autoregression + event guidance
# 13) persistent runtime dialogue-session context
# 14) visual trace + lexicon notes + node-health diagnostics
# 15) session-aware dialogue corpus map on full rebuild
# 16) Credit Backprop usage/context/origin learning
# 17) B0/B1/B2/B3 experiment harness
cleaning.apply(core)
corpus_filter.apply(core)
language.apply(core)
corpus_manager.apply(core)
corpus_roles.apply(core)
corpus_v1_quality.apply(corpus_v1)
corpus_v1.apply(core)
corpus_integrity.apply(core)
relation_guard.apply(relations)
relations.apply(core)
hybrid.apply(core, relations)
sequence.apply(core)
generation_tokens.apply(generation)
generation.apply(core)
syntax_tags.apply(core)
syntax_bridge.apply(syntax_tags)
temporal_event.apply(event_graph)
event_graph.apply(core)
activation.apply(core)
context_map.apply(core, activation)
wordmap_gpt2.apply(core)
event_guidance.apply(core)
dialogue_session.apply(core)
visualizer.apply(core)
lexicon_notes.apply(core)
node_health.apply(core)
dialogue_corpus.apply(core)
credit_learning.apply(core, wordmap_gpt2)
experiment_harness.apply(core)

import wordmap_mobile
import ui_patch
import corpus_web
import visual_ui
import node_health_web
import learning_web
import experiment_web

ui_patch.apply(wordmap_mobile)
corpus_web.apply(wordmap_mobile, core)
visual_ui.apply(wordmap_mobile)
node_health_web.apply(wordmap_mobile, core)
learning_web.apply(wordmap_mobile, core)
experiment_web.apply(wordmap_mobile, core)

if __name__ == "__main__":
    wordmap_mobile.main()
