# Data Preparation and Popular Baseline Implementation Plan

> Historical planning/usage note. Check [project status](../README.md) and [current run instructions](../../recommendation/README.md) before following commands. Unchecked boxes preserve the original plan; they are not a live task tracker.

> **For agentic workers:** Use superpowers:executing-plans for inline execution after plan review. Complete the data task before the baseline task. No model training or serving code is part of this plan.

**Goal:** Produce reproducible chronological data splits and a popular-baseline validation report.

**Architecture:** Add an offline Python package alongside the existing Java application. A preparation command writes cleaned splits and mappings; an evaluation command builds training-only popularity and measures validation quality.

**Tech stack:** Python, pandas, PyArrow, pytest, Docker for a one-off offline job. Pin compatible dependency versions after checking the runtime; do not introduce cloud services.

**Spec:** [Working LLD](TwitchRecommender-LLD-v0.1.md), data contract, agreed preparation settings, popular baseline, and first milestone.

## Global constraints

- Extend the existing Oliruirui/TwitchRecommender repository; do not create a replacement Java application or a new Git repository.
- Up to 5,000 users, seed 42; global timeline split 70/15/15.
- Training-only ID mappings and distinct-user popularity. No future interactions in model inputs or popularity counts.
- Preserve repeat interactions and permit recommendations of previously watched channels.
- No test-set metric report during this milestone.
- No credentials, raw dataset, or generated data committed to Git.
- The existing Java backend requires no changes in this milestone.

## Review focus

- Single-round observations are valid; malformed intervals are counted and removed.
- Entire observation rounds stay on one side of each global cutoff.
- Sampling and mappings must be invariant to input-row order.
- Unknown users/channels must appear in coverage counts rather than silently disappear.
- Empty splits or no eligible validation users must produce an actionable error, not a misleading zero-quality report.

## Workspace prerequisite

- [ ] Locate the existing checkout before edits. This chat directory currently contains documentation, not application sources. If no checkout is available, obtain a checkout of the existing repository in this workspace without creating a new repository or overwriting another checkout. Read applicable AGENTS.md files and inspect Git status before editing. Do not print files containing credentials.
- [ ] Inspect a small downloaded CSV sample and confirm five headerless columns and integer observation rounds against the official source. Preserve dataset provenance and review download/use terms before ingestion.

## Task 1: Reproducible data preparation

**Files, relative to the existing repository:**
- Create `recommendation/__init__.py`, `recommendation/prepare_data.py`, `recommendation/config.yaml`, `recommendation/requirements.txt`, `recommendation/Dockerfile`.
- Create `recommendation/tests/test_prepare_data.py`.
- Update `.gitignore` to exclude raw/generated data and artifacts.

**Interfaces:**
- `prepare_data(input_csv: Path, output_dir: Path, max_users: int = 5000, seed: int = 42) -> dict`: writes splits/mappings/manifest and returns manifest metadata.
- Command: `python -m recommendation.prepare_data --input data/raw/100k.csv --output data/prepared --max-users 5000 --seed 42`.
- Output rows retain raw string user/channel identities, source stream ID, and integer start/stop; model indices are represented by the separate mappings.

**Operational decisions for review:**
Clean first: trim identity fields, parse integer rounds, reject missing identities, negative rounds, and stop < start; retain stop == start. Remove exact duplicates on all five source fields. Do not estimate watch duration. Compute timeline lower=min(start), upper=max(stop)+1 on the complete cleaned source before user sampling; define boundaries lower+floor(0.70*(upper-lower)) and lower+floor(0.85*(upper-lower)). Error if these produce empty-width windows.

Choose users by ascending SHA-256 of UTF-8 `42:<raw_user_id>`, breaking hash ties by raw ID; take up to 5,000. This supplies deterministic seed-based sampling independent of input order, including potential future-only users. For each split [lo, hi), retain start >= lo and stop < hi; count boundary-crossing exclusions. Sort exported rows by start, stop, raw user, channel, and stream. Assign contiguous zero-based embedding indices to sorted training identities only. Preserve held-out raw identities for coverage analysis.

- [ ] Write fixture tests for single-round validity, malformed rows, exact duplicates versus repeats, cutoff-crossing exclusions, future-only IDs absent from mappings, and shuffled-input reproducibility.
- [ ] Run `python -m pytest recommendation/tests/test_prepare_data.py -q` and confirm expected failures before implementation.
- [ ] Implement preparation and CLI. Write `train.parquet`, `validation.parquet`, `test.parquet`, `user_mapping.json`, `channel_mapping.json`, and `data_manifest.json`. Record input checksum, boundaries, sample seed/population, counts, and mapping semantics in the manifest.
- [ ] Run the same tests; require all passing. Empty training or validation splits return a nonzero CLI exit with a clear message.
- [ ] Include pinned dependencies and a training image whose default entry point is Python; verify preparation on the tiny fixture in the container. This is a one-off job, not a server.
- [ ] Commit source, fixture tests, and configuration only after checks pass.

## Task 2: Popular baseline and validation evaluation

**Files:** Create `recommendation/evaluate.py` and `recommendation/tests/test_evaluate.py`.

**Interfaces:**
- `build_popular(train: DataFrame) -> list[dict]`: distinct-user count descending, channel-name ascending for ties.
- `evaluate_popular(train: DataFrame, validation: DataFrame, ks: tuple[int, ...] = (10, 200)) -> dict`: macro-average binary-relevance Recall/NDCG, evaluated-user counts, and coverage.
- Command: `python -m recommendation.evaluate --prepared data/prepared --output artifacts/baseline-validation`.

Construct one list per training-known user for the validation period. Relevant labels are distinct validation channels in the training-known catalog. Evaluate only users with at least one eligible label; count all other users separately. Keep repeat-viewed channels eligible. Freeze popularity at training cutoff. Recall denominator is eligible distinct labels; NDCG uses binary relevance and ideal DCG for min(K, number of eligible labels). Unknown coverage is reported separately at user and distinct-user/channel-pair levels with explicit denominators. A short catalog returns fewer than K; K itself remains unchanged in metric definitions.

- [ ] Write tests where Alex's labels {B,D} and returned Top 3 [B,D,E] yield Recall@3=1 and NDCG@3=1; [A,B,C] yields Recall@3=0.5 and NDCG@3=(1/log2(3))/(1+1/log2(3)).
- [ ] Add tests for duplicate validation observations, distinct-user popularity, popularity ties, unknown-user/channel coverage, short catalogs, and zero eligible users.
- [ ] Run `python -m pytest recommendation/tests/test_evaluate.py -q`; confirm the intended failures.
- [ ] Implement metrics, coverage, baseline export, and CLI. Do not read the test split. Zero eligible users produces an error rather than a numeric score.
- [ ] Run both fixture suites and require all passing. Save the full popularity list to `popular_channels.json` and the report to `validation_report.json` with data checksum, K values, counts, and metric definitions.
- [ ] Run preparation and evaluation on the sampled historical CSV, record actual counts/results, and investigate data-quality failures before claiming completion. Commit code; generated outputs remain ignored.

## Completion and handoff

Success means fixture checks pass, the real sample produces deterministic splits, and validation baseline metrics have recorded provenance and coverage. It does not mean the recommendation model is trained. Next: review the remaining model settings, define two-tower training tasks, and later reuse the identical evaluation protocol for model comparisons.
