# Offline FAISS export — October 13, 2026

Completed in [PR #3](https://github.com/Oliruirui/TwitchRecommender/pull/3), branch `codex/faiss-export`, commit `e2329e8`. The PR is open and not merged.

The selected epoch-30 model was exported into a local versioned bundle at `artifacts/retrieval-bundle-v001` in the existing repository checkout. The bundle contains selected model weights, configuration, user/channel mappings, 19,861 float32 channel vectors of dimension 32, an exact FAISS IndexFlatIP index, the popular fallback list, and a payload-checksum manifest. Its total size is 10,615,319 bytes. Model weights are copied from the trained checkpoint, not retrained.

## Verification

- All 36 Python checks pass, including existing data/training checks and new export cases.
- A separate reviewer independently ran the suite and found no significant issues.
- All 4,802 mapped users have the same Top-200 channel sets under FAISS and direct PyTorch dot products. Full ordering matches for 4,764 users; within-set tied/numerically close order differences are permitted. Maximum absolute score difference is 0.0000076294; comparison tolerances are 1e-5.
- Checksums, training mappings, model/vector/index alignment, wrong metric, corrupt payloads, nonfinite weights, and partial-output cleanup are checked.
- Export consumes no validation/test labels. No online API, Java, frontend, or retraining work was added.

## macOS compatibility decision

The installed Torch and FAISS wheels each include an OpenMP runtime. A minimal same-process search reproduced a native duplicate-runtime abort; import order and limiting threads did not fix it. Launching a new process with both libraries resolving to Torch's runtime did. Added `recommendation/run.py` and a native computation/search regression check; the launcher sets a process-local library path before starting the same interpreter. It does not modify third-party binaries or enable an unsafe duplicate-runtime override. This necessary compatibility file expands the initially described four-file scope to five. See the [upstream issue](https://github.com/pytorch/pytorch/issues/149201).

Other explicit scope decisions: export requires a fresh, nonexistent output directory for atomic publication; artifacts are trusted local files, and checksums are consistency checks rather than authentication. Docker/Linux execution and concurrent publishers remain unverified. Generated models/indexes stay local and ignored by Git.

## Run

From the repository root:

```bash
.venv/bin/python -m recommendation.run -m pytest -q

.venv/bin/python -m recommendation.run -m recommendation.export \
  --model artifacts/retrieval-30epochs-v001 \
  --prepared data/prepared \
  --output artifacts/my-retrieval-bundle \
  --version my-retrieval-bundle
```

Use a fresh output path for repeat runs. The current complete bundle is already saved locally. Runtime serving will load it in the next milestone.

## Evidence

- [Full-user verification](FAISS-Export-Verification.json)
- [Bundle manifest](FAISS-Bundle-Manifest.json)
- [Source patch](https://github.com/Oliruirui/TwitchRecommender/pull/3)
