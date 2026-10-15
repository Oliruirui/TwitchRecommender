# TwitchRecommender — Low-Level Design

## Learning checkpoint — end of project

For now, treat the recommendation model as a black box and focus on its inputs, outputs, training pipeline, and serving behavior. Before closing the project, revisit these questions together using our implementation and measured results:

- [ ] Why did we choose two towers?
- [ ] What do the training examples and loss teach the model?
- [ ] How does negative sampling affect learning?
- [ ] How do we measure quality and detect data leakage?
- [ ] What happens with new users or channels?

This checkpoint is a deferred learning review, not a prerequisite for continuing the current LLD discussion. Explain each answer in plain English and identify remaining gaps.

**v0.1 | October 10, 2026 | Working draft; agreed decisions and remaining proposals are identified below**

## Two-tower retrieval: architecture and training

The user tower maps a user ID to a user vector. The channel tower maps a channel ID to a channel vector of the same dimension. Starting with IDs is the proposed initial approach; history and channel features can be added later.

The match score is the dot product of the two vectors:

```text
u = user_tower(user_id)
v = channel_tower(channel_id)
score(user_id, channel_id) = dot(u, v)
```

Two towers describe the model architecture. Positive pairs and negative sampling describe how we propose to train it.

An observed user–channel interaction supplies a positive pair. For that user, we sample other eligible channels as negative examples. The training objective encourages the positive channel to receive a higher score than the sampled alternatives.

For example, if Alice interacted with channel A and channels B and C are sampled:

```text
score(Alice, A) > score(Alice, B)
score(Alice, A) > score(Alice, C)
```

These inequalities express the learning objective, not a guarantee for every pair. The loss guides updates to both towers' parameters across many training examples. Shared interaction patterns can then help the model retrieve channels the user has not previously interacted with.

### Label interpretation

The historical data provides implicit observations, not recommendation clicks. An observed interaction is a positive training signal. An unobserved channel is not a confirmed dislike; a sampled negative may still interest the user.

Negative sampling is a common training approach rather than a defining requirement of two-tower models. In-batch negatives, where other examples in the training batch serve as comparisons, are another option. Explicit sampled negatives are the proposed starting approach for this project.

### Serving connection

After training, compute channel vectors and store them in a FAISS index. For a known user, obtain the user vector and retrieve approximately 200 channels using the same dot-product scoring convention. Send those candidates to the separate ranking model. Unknown users receive popular-channel recommendations.

### Decisions for the next LLD review

This section explains the training mechanism; it is not yet an implementation-ready specification. We still need to select the exact loss, negative sampling distribution and count, treatment of known positive channels during sampling, vector dimension, tower layers, and handling of repeated observations. Sampling and features must respect chronological boundaries and cannot use future interactions.

## First Python serving version — agreed behavior

The first serving version returns retrieval results directly. Java calls Python; the browser calls Java. Direct Python calls are also available for development tests. Ranking will later reorder approximately 200 retrieved candidates into a final Top 10.

### Artifact bundle

Load these files together from a versioned directory such as `artifacts/v001/`:

```text
manifest.json
retrieval_model.pt
user_mapping.json
channel_mapping.json
channel_vectors.npy
channels.faiss
popular_channels.json
```

The manifest records model configuration, data version, and checksums. Mappings preserve training identity assignments; channel mappings also retain channel names for response rendering. Internal embedding indices are bundle-local, not Twitch numeric IDs. Channel vectors and the index use dot-product scores. Do not mix files from different versions. Load and validate the bundle once at startup, then use the in-memory objects for requests.

### Recommendation API

`POST /v1/recommendations` accepts:

```json
{"user_id": "42", "k": 3}
```

`user_id` is a nonempty string identifying a historical demo user. `k` is an integer from 1 to 200, defaulting to 10. Invalid requests return HTTP 422 with a validation detail. A successful HTTP 200 response returns up to K distinct channels, highest score first:

```json
{
  "request_id": "example-request-id",
  "model_version": "v001",
  "method": "two_tower",
  "fallback_reason": null,
  "items": [
    {"channel_id": "12", "channel_name": "channel_a", "retrieval_score": 0.82},
    {"channel_id": "25", "channel_name": "channel_b", "retrieval_score": 0.76},
    {"channel_id": "39", "channel_name": "channel_c", "retrieval_score": 0.71}
  ]
}
```

Scores above are illustrative learned affinity scores, not probabilities. Previously watched channels remain eligible. If the eligible catalog has fewer than K channels, return fewer. Popular responses retain the same shape with `method: "popular"`, a fallback reason when applicable, and null retrieval scores.

### Fallback behavior

| Condition | Behavior |
|---|---|
| Unknown user | Python returns popular Top K; reason `unknown_user` |
| Recoverable retrieval exception | Python returns popular Top K; reason `retrieval_error`, logged server-side |
| Python unreachable or overall deadline exceeded | Java returns Top K from its local popular snapshot and records the transport reason |
| No valid fallback | HTTP 503; frontend shows an error and retry option |
| Invalid or mismatched bundle at startup | Fail readiness; do not serve personalized requests |

Java's snapshot comes from a validated bundle and responses report that snapshot's version. Connection timeout starts at 200 ms; the overall Java-to-Python deadline is 2 seconds, with no automatic request retry. These are configurable initial budgets, not measured performance targets. A user-initiated retry is a new request.

### Startup and health — agreed

At startup, read the configured artifact directory, validate file checksums, vector dimensions, and ID/index consistency, then load model, index, and popularity artifacts into memory. Run a small known-user recommendation check before marking the service ready. If no valid model exists, readiness fails. Replace model bundles by restarting the service; hot reload is outside v1.

- `GET /health/live`: HTTP 200 while the process can respond.
- `GET /health/ready`: HTTP 200 with the active model version after validation and loading; otherwise HTTP 503.

### Serving verification — agreed

- A known user requesting K=3 receives three distinct channels when the catalog permits.
- An unknown user receives popular results with reason `unknown_user`.
- Invalid K receives a validation error.
- Repeated requests with the same user and bundle produce consistent results.
- Exact FAISS retrieval matches direct dot-product Top K, allowing alternative ordering or membership at tied-score boundaries. Returned scores must match direct scores within numerical tolerance.
- A broken artifact bundle fails readiness.

## Offline evaluation — agreed approach

### Popular baseline — agreed

Count distinct training users per channel and sort descending by that count. Break ties by channel name in ascending order. Only training-period interactions contribute; multiple interactions by the same user with a channel count once for this baseline. Previously watched channels remain eligible. Every user receives the same ordered list, truncated to the requested K and available catalog size. Save the complete ordered training catalog with channel identity, name, and distinct-user count in `popular_channels.json`, so it supports requests up to K=200. Use this baseline for offline comparison, unknown users, and recoverable serving failures. Example counts discussed in chat were illustrative, not measurements.

### Metrics

Compare the popular baseline and two-tower retrieval on the same held-out period and candidate catalog. Once ranking exists, evaluate it under the same protocol.

- Recall@K is the fraction of a user's distinct relevant channels retrieved in the Top K.
- NDCG@K rewards placing relevant channels earlier in the list, using binary relevance.
- Later observed interactions supply relevance labels, not click labels. Repeat viewing remains eligible and counts as relevant.
- Report the primary personalized comparison for users and channels represented in training. Also report excluded/unknown-user and unknown-channel coverage rather than silently dropping them.

Illustration: if Alice's relevant channels are {B, D} and the returned list is [B, C, A], Recall@3 is 1/2. This is an illustrative calculation, not a measured project result. The exact cutoff-query construction and feature snapshot rules must be specified before evaluation code is implemented.

## Local container deployment — agreed

Run the FastAPI application with Uvicorn in a long-running Docker container on the user's laptop. Start with one Python worker, which loads its model and index once. Docker Compose connects this service to the existing Java application container. No AWS hosting is required.

| Component | Address or storage |
|---|---|
| Java application API | Host port 8080; browser accesses localhost:8080, with paths relative to the configured WAR context |
| Python recommendation API | Compose service `recommender`, container port 8000; Java uses http://recommender:8000 |
| Direct development access to Python | Bind host port 8000 to loopback for laptop testing |
| Model bundles | Host artifact directory mounted read-only at /app/artifacts; service selects one version directory at startup |
| Event database | Persistent Docker volume mounted at /app/events; SQLite file /app/events/events.sqlite |
| React frontend | Integrate during the frontend milestone |

Inside Java's container, localhost refers to that container, not the Python container. Compose provides service-name resolution. Event storage survives container replacement through the named volume. Recommendation computation runs when a request arrives; it does not launch a new container per user. The one-worker setup and request capacity will be measured before scaling. A 100-request/second load test is a possible scenario, not an accepted capacity guarantee or current performance target.

## Offline training execution — agreed

Use a separate, manually started training container on the laptop. It reads the historical dataset, runs preparation/training/evaluation/export, writes a new artifact version, and exits after its job. The serving container remains a separate long-running process and never trains during requests.

Training writes to a new version directory rather than overwriting the active bundle. Validate the exported bundle before restarting serving with it. Training has writable output storage; serving mounts approved artifacts read-only. Scheduled retraining and learning automatically from frontend events are outside v1.

We write our model definition using PyTorch building blocks rather than downloading a pretrained Twitch model. `model.py` defines the towers and scoring computation; training starts with randomly initialized weights and updates them using historical interaction examples. `retrieval_model.pt` contains learned weights, not the training dataset or a complete standalone service. Serving reconstructs the model using the shared definition, saved weights, and configuration. Mapping consistency is required.

## Historical data contract — representation agreed

Source: [LiveRec dataset documentation](https://github.com/JRappaz/liverec#datasets) and [official CSV loader](https://github.com/JRappaz/liverec/blob/main/data.py). Obtain `100k.csv` from the download linked by the source repository. The official loader reads five columns without a header: user, stream, streamer, start, stop.

| Source field | Internal meaning |
|---|---|
| user | Anonymized user ID |
| stream | Broadcast ID, retained for traceability |
| streamer | Channel name mapped to an internal channel ID |
| start | First observation round where the user appeared in chat |
| stop | Last observation round where the user appeared in chat |

Observation rounds are integer time indices; the dataset documentation describes ten-minute rounds. They are not calendar timestamps or click events. Recommend channels, so separate broadcasts of a channel share its channel ID. Initial model training reads this historical CSV, not the new application's SQLite event database. Inspect downloaded interval values before defining boundary conditions or duration features; do not infer continuous viewing from observation intervals.

### Data preparation — agreed starting settings

- Select up to 5,000 users reproducibly with seed 42 and retain their interactions. Specify the sampling population before implementation; sampling users from the full dataset can include users first observed after training, which must be reported as cold-start coverage.
- Drop rows with missing identities or invalid intervals and report counts. Remove exact duplicate rows but preserve distinct repeat interactions.
- Split the observation timeline into 70% training, 15% validation, and 15% test. These are timeline proportions, not guaranteed row-count proportions.
- Exclude intervals crossing split boundaries and report their count. Treat source start/stop as first/last observed rounds, inclusive, consistent with the documented field meanings. Use split windows [lower, upper); retain a row only if start >= lower and stop < upper. Accept stop == start as a single-round observation; reject stop < start.
- Build learned user/channel mappings from training data only. Preserve raw identities in held-out data so unknown-user/channel coverage can be measured.
- Produce train/validation/test Parquet files, mappings, and a data manifest recording the source checksum, seed, boundaries, and cleaning counts.

Chronological separation reflects future recommendation usage, rather than a requirement of the two-tower architecture. Training rows may be shuffled after the splits are fixed. Global cutoff evaluation must not use future interactions to construct features.

### Negative sampling — discussed proposal

Use up to five distinct uniformly sampled channels per positive example from the training catalog, excluding every channel the user interacted with in the training period. If fewer than five are eligible, use the eligible channels; if none are eligible, skip and count the example. Use a fixed seed. Never consult validation/test interactions to exclude negatives. V1 does not model historical live availability, so sampled negatives are imperfect preference signals.

Each observed interaction supplies a user–positive-channel example. Alice's interactions with A and B produce positive examples for both, updating the same user representation; neither A nor B is a negative for her. More repeat interactions can contribute more training signals but do not guarantee higher learned scores. Exact repeat weighting remains to be settled.

### Training configuration — proposal awaiting review

| Setting | Initial proposal |
|---|---|
| Vector dimension | 32 |
| Tower structure | ID embedding followed by a linear layer |
| Loss | Pairwise logistic loss |
| Optimizer | Adam, learning rate 0.001 |
| Batch size | 256 positive examples |
| Epoch count | 10; agreed below |
| Checkpoint selection | Highest validation Recall@200; agreed below |
| Random seed | 42 |

These are starting choices, not proven optimal settings. A tiny smoke test checks data loading, ID bounds, sample generation, finite loss, parameter updates, and saved/reloaded score consistency before a larger run. It does not establish recommendation quality. Freeze configuration selection before using the test set for the final report.

### Checkpoints and model selection — agreed

Run ten epochs for the initial experiment. An epoch is one pass through the eligible training examples. After each epoch, compute validation Recall@200 and save a resumable training checkpoint containing model weights, optimizer state, completed epoch, configuration, and random-generator states. Checkpoints remain separate from serving artifacts.

Select the checkpoint with the highest validation Recall@200; ties retain the earlier epoch. Export selected retrieval weights for the next serving milestone. Reserve frozen-test evaluation until the full pipeline configuration is selected. Test results do not select the epoch or tune the model. The last epoch is not automatically the selected model. A failed/non-finite training run is an error to diagnose, not a reason to silently publish a checkpoint.

Serving loads selected weights, model configuration, mappings, vectors, the index, and the popular list. It does not load optimizer state or resume training. A resumable training checkpoint is not itself a deployable serving bundle.

## Python file responsibilities — proposal awaiting review

Add the Python code alongside Java inside the existing TwitchRecommender repository. Exact directory layout and function signatures will be established in the implementation task plan.

| File | Responsibility |
|---|---|
| prepare_data.py | Clean, split, and map the historical data |
| model.py | Define both towers and dot-product scoring; shared by training and serving |
| train.py | Generate batches, optimize weights, and save the best validation checkpoint |
| evaluate.py | Compute offline Recall/NDCG and baseline comparisons |
| export.py | Produce channel vectors, the FAISS index, and the serving bundle |
| config.yaml | Store data, model, and training settings |

Execution flow: preparation → training with validation → final evaluation → export. The serving application imports the model definition and loads artifacts; it does not invoke the training pipeline.

## Remaining LLD work

Finalize the proposed preparation/sampling/training settings, model layer shapes and loss reduction, deterministic ranking of score ties, cutoff-query evaluation and feature snapshots, and artifact manifest/mapping schemas. Then define the ranking model, public Java API, frontend event schema, experiment assignment, and SQLite tables. This working document is not yet a complete implementation-ready LLD; approval of individual discussed sections does not finalize the remaining contracts.

## First implementation milestone — agreed

Prepare historical data, build training-only distinct-user popularity, and evaluate that baseline on validation data. Reserve the test period for final selected-model evaluation. Deliver prepared files and a reproducible validation report before adding neural-network training. The concrete task plan records operational choices and checks for this milestone; model and full-service implementation remain later work.

## Two-tower training milestone — configuration agreed, detailed contract for review

Use existing prepared files and training-only mappings. Each tower is an Embedding table with 32-dimensional rows followed by a 32-to-32 linear layer without bias. No vector normalization or sigmoid: the retrieval score is the raw dot product. The user and channel towers have separate parameters. Initial weights are random; CPU execution, seed 42, and one training thread are the reference configuration for laptop reproducibility. Record runtime/library versions and do not promise bit-identical results across platforms.

Each retained training observation is one positive example, including separate repeat observations. Shuffle examples each epoch. For each positive, sample up to five distinct negatives uniformly without replacement from the training catalog, excluding all of that user's training-positive channels. Resample each epoch with a seeded random generator. If none are eligible, skip/count the example; fail clearly if the entire run has no trainable examples. Do not inspect held-out interactions during sampling.

The loss for a positive/negative pair is softplus(negative_score - positive_score), equivalent to -log sigmoid(positive_score - negative_score). Average valid negatives within each positive example, then average examples in the batch; a short negative pool must not change the user's per-example weight. Use Adam, learning rate 0.001, no weight decay, positive batch size 256, and ten epochs. Non-finite loss or gradients fail the run and do not publish a best checkpoint.

After each epoch, generate channel vectors in evaluation mode and use exact dot-product search over the full training catalog. Score users in batches of 64 to bound memory. Resolve score ties by ascending internal channel index. Keep repeat-viewed channels eligible. Reuse the baseline's eligible-user labels, coverage definitions, macro averaging, and binary Recall/NDCG at K=10 and 200. This stage does not require FAISS; exact matrix scoring is the reference for later FAISS verification.

Select the highest validation Recall@200 checkpoint, retaining the earlier epoch on ties. Store epoch checkpoints with weights, optimizer state, training shuffle/sampler random states, configuration, metrics, and data/mapping fingerprints. Save selected weights separately as best_model.pt with a JSON model configuration; these are training outputs, not the complete serving bundle. Reject nonempty output directories. Automated resume is not part of this milestone, even though checkpoints preserve its required state.

Deliver training_history.json, validation_comparison.json, best_model.pt, model_config.json, and epoch checkpoints. The comparison includes the existing popular baseline and all K=10/200 model metrics plus coverage and fingerprints. Do not evaluate the frozen test period yet: ranking and candidate-count decisions remain open. Final test evaluation occurs after the full chosen pipeline is frozen.

Run a tiny deterministic smoke job first to check finite computation, parameter updates in both towers, negative exclusions, and checkpoint reload score consistency. Then run ten epochs on the existing 5,000-user sample and report actual validation results, including regressions. No Java, frontend, ranking, or serving changes in this milestone.

### Follow-up experiment — October 13, 2026

The approved controlled experiment changed only the training budget to thirty epochs, with identical data/mapping fingerprints and other settings. All first ten epoch losses/metrics reproduced exactly. The selected epoch was 30: validation Recall@10=0.1288382761, Recall@200=0.5063726243, NDCG@10=0.1007102133, NDCG@200=0.1994569796, compared with popular Recall@200=0.3382663977. This supports insufficient training as an important contributor to the earlier validation deficit. The saved model was reloaded and bucket recall reconciled with the reported metrics; the frozen test set remains unused. Source defaults remain ten epochs; the thirty-epoch experiment uses a separate configuration. The improved checkpoint is proposed for the next retrieval-service milestone, pending review. See [diagnostic report](Retrieval-Diagnosis-2026-10-13.md).
