# Offline data and popular-baseline milestone

Implemented in the existing TwitchRecommender repository's local checkout, on branch `codex/offline-data-baseline`, commit `df330a1`. The Java application was preserved. No remote push or merge was performed.

## What works

- Prepare the source CSV, select users reproducibly, split globally by observation time, and export training-only mappings.
- Build popularity from distinct training users and compute validation Recall/NDCG with explicit unknown-identity coverage.
- Run both commands from Python with YAML configuration and command-line overrides. Reject nonempty output directories to prevent accidental stale-artifact reuse.
- Produce traceable manifests and reports; exclude raw data and generated artifacts from Git.

## Actual laptop run

Source: public Twitch100k file `100k_a.csv`, linked by the [LiveRec repository](https://github.com/JRappaz/liverec#datasets). The actual filename differs from the README's `100k.csv`; its identity and checksum are recorded.

| Item | Result |
|---|---:|
| Source rows | 3,051,733 |
| Sampled users | 5,000 |
| Sampled rows | 151,561 |
| Training rows | 103,280 |
| Validation rows | 23,195 |
| Test rows, prepared only | 24,854 |
| Cross-boundary intervals excluded | 232 |
| Training users | 4,802 |
| Training channels | 19,861 |
| Eligible validation users | 3,441 |
| Popular Recall@10 | 8.48% |
| Popular Recall@200 | 33.83% |
| Popular NDCG@10 | 0.07486 |
| Popular NDCG@200 | 0.14097 |

These are offline validation metrics for training-known users with eligible training-known channel labels. They are not click probabilities or online engagement measurements. The report records excluded coverage. Test labels were not used to compute baseline metrics.

## Verification and limits

All 13 Python tests pass, including CLI execution, chronological boundaries, repeat observations, hand-calculated metrics, unknown coverage, and a check that evaluation does not read the test split. Two real-data preparation runs produced six byte-identical output files. A separate read-only reviewer independently reran the tests and found no significant issues.

Dockerfile and container commands are prepared, but Docker is absent on the laptop, so image build and container execution remain unverified. Native execution used an isolated project Python environment. Maven is also unavailable; Java build verification was not performed and Java source was unchanged. PyArrow emitted sandbox CPU-detection warnings during one successful native evaluation run; metric generation completed.

Model training, FAISS serving, ranking, frontend integration, and experiment events are later milestones.

## Deliverables

- [Usage instructions](Offline-Pipeline-Usage.md)
- [Machine-readable validation report](validation_report.json)
- [Code patch for the existing repository](https://github.com/Oliruirui/TwitchRecommender/pull/1)

Source and tests are committed in this repository; downloaded datasets and generated model/index artifacts remain local and ignored.
