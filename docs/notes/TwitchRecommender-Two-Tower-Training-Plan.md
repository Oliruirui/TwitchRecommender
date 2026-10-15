# Two-Tower Training Implementation Plan

> Historical planning/usage note. Check [project status](../README.md) and [current run instructions](../../recommendation/README.md) before following commands. Unchecked boxes preserve the original plan; they are not a live task tracker.

> **For agentic workers:** Use superpowers:executing-plans after review. Implement inline, using test-first checks for each task. No serving implementation in this plan.

**Goal:** Train a small retrieval model and compare it honestly with the popular baseline.

**Architecture:** Share model definitions between later training and serving. This milestone uses direct matrix scoring for validation, leaving FAISS export to the next milestone.

**Tech stack:** Python 3.12, CPU PyTorch, pandas, existing pytest pipeline.

**Spec:** [LLD](TwitchRecommender-LLD-v0.1.md), final section: two-tower training milestone.

## Global constraints

Use the existing repository and prepared data; no paid services. Train ten epochs, seed 42, 32-dimensional vectors, Embedding→Linear towers, five negatives, Adam 0.001, batch size 256. Training-only identities/features; repeat observations retained. Select by validation Recall@200, not test results. No automatic resume, ranking, Java, or API changes.

## Review focus

- Fully positive user catalogs must terminate without an infinite sampling loop.
- Short negative pools must be masked and weighted correctly.
- Held-out users/channels must receive the same coverage treatment as the baseline.
- Tied scores must have deterministic Top K behavior.
- Non-finite training and mismatched mappings must prevent artifact publication.

## Task 1: Model and positive/negative examples

**Files:** Create `recommendation/model.py`, `recommendation/sampling.py`, and corresponding tests. Extend pinned requirements with a CPU-compatible PyTorch version verified on the available runtime; no install occurs during planning.

**Interfaces:** `TwoTower(num_users: int, num_channels: int, dimension: int = 32)` exposes `encode_users(ids)`, `encode_channels(ids)`, and `forward(user_ids, channel_ids)` for pair scores. Each encoding returns batch×32 vectors; pair scores return a batch vector. `NegativeSampler(positives_by_user, num_channels, seed)` exposes `sample(user_indices) -> (negative_indices, valid_mask)`, each batch×5. Padding is an in-range index masked out of loss.

- [ ] Write failing tests for output dimensions and dot-product scores, gradients reaching both towers, positive exclusion, no duplicate negatives, seed reproducibility, small eligible pools, and empty eligible pools.
- [ ] Run `python -m pytest recommendation/tests/test_model.py recommendation/tests/test_sampling.py -q` and observe missing-feature failures.
- [ ] Implement the LLD's tower and sampling definitions. Use uniformly sampled eligible channel-index arrays with a bounded LRU cache of at most 128 users; avoid unbounded rejection loops or storing a full catalog copy for every user. Never read validation/test labels.
- [ ] Run the tests; require all passing. Check actual selected negative IDs, not just sample shapes.

## Task 2: Shared validation protocol and exact retrieval

**Files:** Refactor `recommendation/evaluate.py`; add `recommendation/tests/test_retrieval_evaluation.py`. Preserve the existing popular evaluator CLI.

**Interfaces:** `validation_cases(train, validation) -> (labels_by_user, coverage)` becomes the shared eligibility source. `evaluate_retrieval(model, train, validation, user_mapping, channel_mapping, ks=(10,200), user_batch_size=64) -> dict` reports the same metric and coverage keys as popularity.

- [ ] Write failing tests using fixed, hand-designed vectors: known Top K, lower-index tie ordering, a short catalog, unknown identities, and repeated held-out observations. Assert that baseline and model evaluators use identical eligible users/coverage.
- [ ] Run the new tests and confirm intended failures.
- [ ] Extract shared labels/coverage and implement batched exact dot-product retrieval. Validate mapping equality with sorted training identities, vector dimensions, and finite scores.
- [ ] Run the full suite; existing 13 baseline/data checks must remain passing.

## Task 3: Training CLI and checkpoints

**Files:** Create `recommendation/train.py`, `recommendation/tests/test_train.py`; extend `config.yaml` and usage documentation.

**Interfaces:** `train_retrieval(prepared_dir: Path, output_dir: Path, config: dict) -> dict` returns a validation comparison. CLI: `python -m recommendation.train --prepared data/prepared --output artifacts/retrieval-v001`. Defaults come from the reviewed training configuration. `--config` selects another YAML file; `--smoke` runs a small deterministic synthetic job, not a replacement for real-data evaluation.

- [ ] Write failing tests for the specified masked pairwise loss; verify equal per-positive weighting when negative counts differ.
- [ ] Add tests for actual parameter updates, reloaded-weight score equality, best-checkpoint selection with earlier tie retention, rejected mapping mismatch, and no best-model publication after a non-finite failure. Run and observe failures.
- [ ] Implement ten-epoch training, per-epoch validation, random-state capture, and fingerprinted checkpoints. Stop on invalid loss/gradients. Fail early for nonempty output or no eligible examples.
- [ ] Save selected weights/config, complete training history, and validation comparison. Persist metadata separately from weights; do not read test.parquet.
- [ ] Verify the CLI smoke job and full pytest suite. Add an integration check where an unreadable test file does not affect training/validation.
- [ ] Run the real sampled-data job. Record every epoch's loss/metrics and compare best-model validation Recall/NDCG with popular Recall@10=0.08482395584 and Recall@200=0.33826639770. These are baseline measurements, not model targets.
- [ ] Verify artifacts reload, review changes, and commit source/tests/documentation only. Container verification remains pending unless Docker becomes available; clearly separate native execution from Docker claims.

## Deliverable

A reproducible trained retrieval checkpoint, validation history/comparison, and actual results. Improvement is not guaranteed; report a lower result honestly. Next milestone: export vectors/index and add the first Python retrieval service.
