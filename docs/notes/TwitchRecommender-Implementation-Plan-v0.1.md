# TwitchRecommender Implementation Plan

> Historical planning/usage note. Check [project status](../README.md) and [current run instructions](../../recommendation/README.md) before following commands. Unchecked boxes preserve the original plan; they are not a live task tracker.

> **For agentic workers:** Use superpowers:executing-plans for inline execution after review. Expand each milestone into concrete file, interface, and verification steps before implementing it. This is a staged planning draft, not an executable task specification.

**Goal:** Build a local channel recommender with a frontend, learned retrieval and ranking, honest evaluation, and an experiment framework.

**Architecture:** React calls the existing Java backend, which routes requests to a Python recommendation service. Offline jobs produce compatible versioned artifacts; serving provides personalized or popular recommendations.

**Tech stack:** Java, Python, PyTorch, FAISS, FastAPI, React, SQLite, Docker.

**Design references:** [Approved HLD](TwitchRecommender-HLD-v0.1.md) and [partial LLD](TwitchRecommender-LLD-v0.1.md).

## Global constraints

- Run locally with no additional paid services.
- Historical channel recommendations; no live-stream filtering in v1.
- Use chronological splits and features available before prediction time.
- Keep previously watched channels eligible; sampled negatives are not confirmed dislikes.
- HLD → LLD → implementation; review detailed designs before the corresponding code.
- Work in roughly one-hour sessions with a concrete deliverable, and short end-of-session Notion notes.
- Do not publish credentials or invent quality, latency, or online lift results.

## Review focus

- Unknown users must receive popular recommendations.
- Small catalogs must return valid distinct results, even when fewer than ten exist.
- Python outages must trigger Java's popular snapshot, or a clear failure if none is valid.
- Artifact version mismatches must be rejected before serving.
- Duplicate events must not inflate exposure or click counts.

## Implementation sequence

### 1. Complete the LLD and establish the workspace

- [ ] Locate or obtain the repository and inspect its Java structure without exposing credentials. The current chat directory contains design outputs, not a checked-out application.
- [ ] Verify dataset format, use terms, and local hardware; choose a manageable sample.
- [ ] Define split boundaries, evaluation eligibility, and repeat-interaction treatment.
- [ ] Define loss, negative sampling, model dimensions, and ranking features.
- [ ] Define API contracts, event schema, artifact layout, and timeout/fallback behavior.
- [ ] Review the LLD and prepare the first concrete task plan before product code.

**Deliverable:** Reviewed LLD and repository-specific first implementation task.

### 2. Build the data pipeline and popular baseline

- [ ] Clean and map IDs, create chronological splits, and generate training-only popularity statistics.
- [ ] Implement Recall@K and NDCG@K with explicit user/catalog eligibility rules.
- [ ] Verify leakage boundaries and metrics against a small hand-calculated fixture; verify distinct results for small catalogs and unknown users.
- [ ] Run and save the popular baseline evaluation.

**Deliverable:** Reproducible data preparation and measured baseline quality.

### 3. Train and evaluate two-tower retrieval

- [ ] Implement ID-based towers and the reviewed sampled-negative training objective.
- [ ] Verify sampling eligibility and gradients with a small deterministic fixture.
- [ ] Train on the local sample; save weights, mappings, configuration, and channel vectors.
- [ ] Compare retrieval quality with the popular baseline without tuning on the test period.

**Deliverable:** Reproducible retrieval model and evaluation report.

### 4. Add vector search and artifact loading

- [ ] Build an exact dot-product FAISS index first and compare its results with direct scoring.
- [ ] Measure retrieval quality and latency across candidate counts around the initial 200-candidate setting.
- [ ] Validate bundle compatibility and exercise rejection of mismatched versions.

**Deliverable:** Tested candidate retrieval and a loadable versioned bundle.

### 5. Add ranking

- [ ] Generate ranking examples and features using only permitted historical information.
- [ ] Train the reviewed MLP objective and score candidate batches.
- [ ] Compare retrieval-only and retrieval-plus-ranking results; include feature ablation where useful.

**Deliverable:** Measured ranking behavior; any regression is reported rather than hidden.

### 6. Connect services and frontend

- [ ] Expose recommendation serving in Python and integrate it with Java.
- [ ] Build the demo-user selector and recommendation cards in React, including loading, error, and fallback states.
- [ ] Verify unknown users, small catalogs, Python outages, and missing fallback snapshots end to end.
- [ ] Package the working local system with Docker and verify startup instructions.

**Deliverable:** Working browser demo backed by the real recommendation pipeline.

### 7. Implement experiment assignment and events

- [ ] Add stable 50/50 baseline/personalized assignment with an experiment version.
- [ ] Record displayed exposures and linked clicks in SQLite through the defined API.
- [ ] Verify assignment stability, duplicate-event handling, and event linkage.
- [ ] Produce demonstration metric analysis without claiming real engagement lift.

**Deliverable:** Verified A/B plumbing and traceable event records.

### 8. Measure serving and document results

- [ ] Measure stage latency, total latency, p50/p95/p99, throughput, errors, and fallback rates under stated conditions.
- [ ] Optimize only bottlenecks supported by measurements; repeat affected checks after changes.
- [ ] Record reproducible setup, model results, serving measurements, and project limitations.
- [ ] Complete the end-of-project learning checkpoint in the LLD: two-tower choice, examples/loss, negative sampling, quality/leakage, and new users/channels. Use our implementation and measured results; revisit remaining gaps before closing the project.

**Deliverable:** Runnable project and evidence-backed README/demo.

## Execution approach

Recommended: implement together in this chat, one reviewed task at a time. A milestone may take multiple one-hour sessions; this document does not promise a fixed daily completion schedule. The immediate next session is milestone 1, beginning with locating the repository and verifying the data format. No implementation has begun.
