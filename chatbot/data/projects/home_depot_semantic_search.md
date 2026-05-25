# Home Depot Semantic Search & Retrieval Uplift

> A learned semantic retrieval and reranking layer added on top of Home Depot's mature lexical search stack, lifting relevance and search success for millions of daily product queries.

## Overview
Home Depot's e-commerce search relied on a mature lexical retrieval stack that struggled with the long tail of natural-language and intent-driven queries — synonyms, descriptive phrasing, and project-driven queries like "fix a leaky faucet." We added a learned semantic retrieval and reranking layer alongside the existing lexical pipeline, in production for site search. The change delivered a 14% uplift in retrieval relevance and a 21% improvement in search success, at p95 latency under 900ms.

## Why
Lexical retrieval — BM25-style scoring over a tuned analyzer — is excellent when the query and the catalog speak the same vocabulary, but the gap on real customer queries was visible in the funnel. A query like "thing to unclog a drain" returned auger-adjacent SKUs only by accident. The product team had data showing that no-result and low-quality-result queries were a meaningful share of bounces, and the search-quality team's manual synonym list could not keep up.

The alternative was continuing to expand hand-curated synonym rules and learning-to-rank features over lexical signals — slow, brittle, and bounded above by what humans could anticipate. The opportunity was to add a semantic layer that learned product-query affinity from behavior, without ripping out the lexical backbone customers and the merchandising team relied on.

## What
Built: a sentence-embedding-based dense retrieval channel running alongside lexical retrieval, with a cross-encoder reranker over the merged candidate set. Embedding refresh pipeline for the product catalog (millions of SKUs, attribute-aware). Offline evaluation harness against held-out judged query sets. A/B-testable rollout path through the existing search infrastructure. Monitoring for latency, recall@k, and downstream conversion signals.

Explicit non-goals: not a replacement for lexical retrieval (kept as the primary recall channel); not a query understanding rewrite engine (no LLM-based query expansion in the window); not a generative answer layer (no chat-style product Q&A — the production LLM ecosystem was nowhere near ready and the catalog SLA could not absorb that risk).

## How — Architecture
A search request fans out to two parallel retrieval channels: the existing lexical stack (BM25 over the tuned product index) and a new dense retrieval channel against an approximate-nearest-neighbor index of product embeddings. Candidate sets from both channels are merged, deduplicated, and passed to a cross-encoder reranker that scores query-product pairs jointly. The top reranked results then feed the existing learning-to-rank stage for final ordering with business signals (inventory, margin, freshness).

Catalog embeddings are computed offline by a batch pipeline that runs nightly for changed SKUs and weekly for the full catalog. Embeddings live in an ANN index sized to handle production query rate with sub-100ms retrieval latency, leaving headroom for the reranker.

## How — Tech Stack
Python for model training and embedding pipelines. PyTorch and Hugging Face Transformers for sentence-transformer fine-tuning — `all-mpnet-base-v2` family in the POC, fine-tuned on Home Depot query-click pairs. FAISS for the ANN index. Cross-encoder reranker built on a smaller transformer fine-tuned on judged pairs. Existing search service (Java) extended with a dense-retrieval client and a reranker call. Offline evaluation in Python with pandas / scikit-learn. Pipelines orchestrated on Airflow. Serving infrastructure on GCP with autoscaling behind the search service. MLflow for experiment tracking and model registry. Monitoring via the existing Prometheus / Grafana stack with custom search-quality dashboards.

## Journey: POC
Initial hypothesis: an off-the-shelf sentence-transformer model would do well enough on Home Depot's catalog to be worth productionizing if we could prove a lift on judged queries.

Scope: a fine-tuned `all-mpnet-base-v2` model trained on query-click pairs sampled from production logs, a FAISS index over a category-scoped slice of the catalog (one large department), and an offline evaluation against a judged query set held out by the search-quality team. No production traffic.

What was learned: out-of-the-box sentence-transformers were mediocre on home-improvement vocabulary — lots of brand names, dimensions, materials, and project nouns the base model had not seen at the right density. Fine-tuning on in-domain query-click pairs closed most of the gap. We also learned that semantic retrieval alone was worse than the lexical baseline on head queries where exact-match still wins — confirming that the design needed to be a *layer*, not a replacement.

## Journey: MVP
What got hardened: the embedding pipeline (deterministic, idempotent, restartable, with proper handling of SKU adds / deletes / attribute changes), the ANN index build and swap process, and the reranker training loop with reproducible data splits.

New requirements that emerged: the search team needed deterministic behavior in the rollout — same query, same results, until we deliberately changed something. That required pinning model versions and embedding versions together with explicit promotion gates. The merchandising team needed an override path so that curated results for promoted queries were never displaced by the semantic layer. The latency budget tightened mid-project: the reranker had to be quantized and the candidate set size capped before the cross-encoder call.

Decisions under pressure: kept lexical as the primary recall channel with semantic as augmentation rather than merging on equal footing. This gave a clean rollback path and made the A/B story simple — turn the semantic channel off and you are back to the prior pipeline exactly.

## Journey: Production
Reliability: dense retrieval channel deployed behind a feature flag with kill-switch, lexical channel always live. ANN index built green-blue: new index built offline, validated against held-out queries, swapped atomically. Reranker served as a separate service with its own autoscaling so a query spike could not starve the rest of the pipeline.

Observability: per-channel recall@k metrics, latency histograms at each stage, reranker score distributions, and downstream conversion signals broken out by treatment cohort. A/B framework drove gradual rollout from 1% to 100% over several weeks with go / no-go reviews against quality and conversion guardrails.

Scale: production query volume in the millions per day, p95 end-to-end latency under 900ms including the reranker, with the dense channel and reranker accounting for a controlled share of that budget.

On-call: integrated into the existing search team rotation. The most common failure mode was the embedding refresh job lagging a catalog change, handled with a stale-index alert and a manual rebuild runbook.

## Key Decisions & Tradeoffs
Augmentation over replacement — chose to layer semantic retrieval on top of lexical rather than replace it. Rollback was trivial, the merchandising override story stayed intact, and we did not have to win every query type, only the ones lexical lost.

Fine-tuned open-source sentence transformer over a hosted embedding API — hosted embedding options at this catalog scale were either unavailable, immature, or commercially unviable in the window. Open-source plus in-domain fine-tuning gave full control of the embedding distribution and the refresh cadence. Would revisit today given how the embedding ecosystem has shifted.

Cross-encoder reranker on a capped candidate set rather than over the full merged list — the latency math forced this, but it also concentrated expensive scoring on the candidates most likely to matter.

Lexical-primary recall with semantic augmentation rather than learned merging — simpler to reason about, simpler to A/B, easier to defend in quality reviews.

## Outcomes
14% retrieval relevance uplift on the judged query set held out by the search-quality team. 21% improvement in search success rate, measured downstream as the share of search sessions converting to product engagement. P95 end-to-end latency under 900ms, sustained at production traffic.

Lessons: in a mature search stack, semantic retrieval earns its keep as a layer, not a replacement — the wins come from the tail, not the head. In-domain fine-tuning of a small open-source model beat generic large embeddings for our catalog at our latency budget. And building rollback in from day one — same kill switch, same lexical fallback — made every subsequent rollout decision faster.
