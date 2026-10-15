# Two-tower retrieval: first training run

Implemented locally on `codex/two-tower-training`, based on the merged upstream main. No push, PR, or merge was performed for this milestone.

## Actual validation results

CPU training ran ten epochs on the existing 5,000-user sample. The selected checkpoint is epoch 10, the highest validation Recall@200; training took approximately 141 seconds, including per-epoch validation and checkpoint saving. This is training time, not serving latency.

| Metric | Popular baseline | Two-tower |
|---|---:|---:|
| Recall@10 | 8.48% | 5.22% |
| Recall@200 | 33.83% | 21.68% |
| NDCG@10 | 0.07486 | 0.03845 |
| NDCG@200 | 0.14097 | 0.07970 |

Both use the same 3,441 eligible validation users, training-known catalog, and repeat-view eligibility. The first model is worse than popularity on all reported metrics. Its loss decreased from 0.76982 to 0.38521 and recall improved across later epochs, but that does not establish competitive recommendation quality or identify the cause of the gap. Do not claim personalized improvement or online lift. The frozen test split was not evaluated.

## What is implemented

- `model.py`: independent 32-dimensional user/channel Embedding→Linear towers and dot-product scores.
- `sampling.py`: training-only uniform negatives, positive exclusions, bounded cache, and reproducible random state.
- `train.py`: masked pairwise logistic loss, CPU training, validation each epoch, ten checkpoint files, and best-model selection.
- Shared validation cohorts and exact batched dot-product scoring, including deterministic score ties.
- YAML configuration, a synthetic smoke command, and pinned dependencies.

The selected weights live in the existing checkout at `artifacts/retrieval-v001/best_model.pt`, alongside model configuration, history, and a validation comparison. These are training outputs, not the complete FAISS serving bundle. Generated data/models remain ignored by Git.

## Verification

All 26 Python checks pass, preserving the original baseline checks. A separate reviewer independently ran the tests and found no important issues. The smoke CLI ran successfully. The selected real-data model was loaded with `weights_only=True` into a fresh model, its input fingerprints were verified, and it reproduced the selected validation metrics exactly.

Docker execution remains unverified because Docker is unavailable. Java/frontend, FAISS export, online serving, ranking, and experiment events are not part of this milestone. Native PyArrow CPU-detection warnings under the sandbox did not prevent successful preparation/evaluation.

## Run it yourself

From the repository root, using a Python 3.12 virtual environment:

```bash
.venv/bin/python -m recommendation.train --smoke --output artifacts/my-smoke-run
.venv/bin/python -m recommendation.train --prepared data/prepared --output artifacts/my-training-run
```

Choose new output directory names for repeated runs. The smoke command uses tiny synthetic data and two epochs; its metrics are not representative.

## Files

- [Validation comparison](Two-Tower-Validation-Comparison.json)
- [Per-epoch history](Two-Tower-Training-History.json)
- [Source patch](https://github.com/Oliruirui/TwitchRecommender/pull/2)

Next recommendation: investigate the validation gap before treating this model as an improvement over popularity. The first retrieval service can still be built for inspecting model behavior, with popularity retained as the baseline/fallback.
