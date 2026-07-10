# SIE primitives in the agent action gate

Draft content for the eventual `examples/agent-action-monitor/` README (R11),
shaped like `superlinked/sie`'s existing `stripe-link-fraud` example: a model
lineup, where each primitive is actually used in this codebase, and an honest
account of what the deterministic core still does versus what SIE adds.

## Model lineup

| Model | Primitive | Role |
|---|---|---|
| `BAAI/bge-m3` | encode | Embeds an action's description for similarity search against past decisions. |
| `BAAI/bge-reranker-v2-m3` | score | Cross-encoder rerank of the top candidate matches, and of an agent's own history against a new action. |
| `urchade/gliner_multi-v2.1` | extract | Zero-shot extraction of privileged terms (role, privilege, resource, segment, port) from an action's target and change payload, with no training data. |

All three are verified against the live Superlinked model catalog
(`superlinked.com/models`), not assumed from a family name.

## Where each primitive is wired in

- **encode** -- `src/dusk/trace/vector.py`'s `sie_encode()`, used by
  `find_similar()` to retrieve candidate past decisions by cosine similarity.
- **score** -- `src/dusk/trace/vector.py`'s `sie_score()`, used twice: to
  rerank `find_similar()`'s shortlist for higher precision, and inside
  `src/dusk/actions/analyse.py`'s `_semantic_novelty()` to check a new
  action's rerank similarity against the acting agent's own raw history.
- **extract** -- `src/dusk/trace/vector.py`'s `sie_extract()`, used inside
  `src/dusk/actions/analyse.py`'s `_extracted_sensitive_terms()` to flag
  privileged terms the static frozenset (`_SENSITIVE_TOKENS`/
  `_SENSITIVE_VALUES`) does not already cover.

## What happens without SIE

Every one of the three call sites above degrades to a no-op or a
deterministic fallback rather than failing: `sie_encode` falls back to a
hash-based n-gram embedding, `sie_score` and `sie_extract` return `None`/`[]`,
and every downstream signal that depends on them is additive-only, so the
gate's rule-based score is never reduced by their absence. `dusk gate` and
`/v1/gate` work identically without any SIE container running -- see
`tests/test_sie_live_benchmark.py` for the test that proves the reverse:
with SIE reachable, precision/recall must not regress, and at least one
attack's reasons must carry a SIE-sourced marker, proving the primitives are
actually contributing a signal rather than a no-op that happens to still
pass.

## Known limits

- The baseline/attack fixtures used in the benchmark (`lab/actions/
  generate_actions.py`) are synthetic, not real production traffic.
- The deterministic feature checks in `actions/baseline.py` and
  `actions/analyse.py` still do the primary anomaly scoring; SIE's three
  primitives are an enrichment layer on top, not a replacement for it. This
  matches the project's own stance that the core detection logic is not
  dependent on any AI model at runtime.
- `sie_score`'s rerank pass only reorders a small shortlist (`top_k`,
  default 3) of candidates already retrieved by cosine similarity -- it does
  not rerank the full decision history.
- `sie_extract`'s privileged-term detection is zero-shot: it has not been
  evaluated against an adversarial corpus designed to evade GLiNER
  specifically, only against the same synthetic fixtures used elsewhere.
