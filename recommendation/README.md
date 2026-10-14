# Channel recommendation pipeline

This Python package inside the existing Java repository prepares LiveRec observations, evaluates a popular-channel baseline, trains a two-tower model, exports a FAISS bundle, and serves local HTTP recommendations. The sections below describe each stage separately.

## Data source

Download the Twitch100k CSV from the Drive folder linked in [LiveRec's dataset documentation](https://github.com/JRappaz/liverec#datasets). The publicly available file was named `100k_a.csv` at download time; the source loader describes `100k.csv`. Keep the actual downloaded name and checksum in the manifest. Put it at `data/raw/100k_a.csv`. Do not commit or redistribute raw data. Cite Rappaz, McAuley, and Aberer's RecSys 2021 paper in research uses, following the source's citation request.

The CSV has five headerless columns: anonymized user, broadcast ID, channel name, first observation round, last observation round. These are implicit chat-presence observations, not clicks or proof of continuous watching. The documentation describes ten-minute rounds. This milestone treats start/stop as inclusive observed endpoints and excludes intervals crossing split cutoffs.

## Local Python execution

From the repository root, using Python 3.12:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r recommendation/requirements.txt
.venv/bin/python -m recommendation.run -m pytest -q
.venv/bin/python -m recommendation.prepare_data --input data/raw/100k_a.csv --output data/prepared-v001
.venv/bin/python -m recommendation.evaluate --prepared data/prepared-v001 --output artifacts/baseline-validation-v001
```

Configuration is read from `recommendation/config.yaml`. Supply `--config` for another YAML file; explicit `--max-users`, `--seed`, and `--k` flags override corresponding file values. Defaults sample up to 5,000 users with seed 42 and evaluate K=10,200. Output directories must be empty or new; use new version directories for subsequent runs.

## Container execution

Docker must be installed and running. These commands are prepared but have not been verified on the current laptop, where Docker is unavailable.

```bash
docker build -f recommendation/Dockerfile -t twitch-offline .
docker run --rm twitch-offline -m pytest -q
docker run --rm -v "$PWD/data:/app/data" twitch-offline -m recommendation.prepare_data --input /app/data/raw/100k_a.csv --output /app/data/prepared-v001
docker run --rm -v "$PWD/data:/app/data:ro" -v "$PWD/artifacts:/app/artifacts" twitch-offline -m recommendation.evaluate --prepared /app/data/prepared-v001 --output /app/artifacts/baseline-validation-v001
```

Create the host `data/` and `artifacts/` directories first. Training and preparation are one-off container jobs; this image's entry point is Python, not Uvicorn. The later serving container will load a model bundle separately.

## Outputs and evaluation

Preparation writes train/validation/test Parquet, training-only identity mappings, and a manifest. Global timeline cutoffs use 70%/85% of the cleaned source observation range before sampling. Exact duplicates are removed; separate repeated observations remain. Seed-based SHA-256 ordering selects users independently of input-row order. The user population includes future-only users, reported as cold-start coverage.

Baseline popularity counts distinct training users per channel, breaking ties by channel name. The validation query is one recommendation list per eligible training-known user; relevance is distinct validation-period channels within the training catalog. Previously observed channels remain eligible. Recall/NDCG are averaged equally across eligible users. Users without eligible labels and unseen identities are reported separately, so these metrics do not imply performance for every validation user or every channel. No historical live-availability filter is applied.

`validation_report.json` records metrics, coverage denominators, protocol, source and prepared-file checksums, seed, and timeline. `popular_channels.json` contains the full ordered training catalog. Channel IDs are bundle-local embedding indices, not Twitch numeric IDs. The test split is created but is not consumed by the baseline validation evaluator.

The current laptop run passed 13 Python tests. Java files are unchanged; Java build verification and Docker runtime verification are not included in that claim.

## Two-tower retrieval training

Update the Python environment with the pinned requirements before running training. PyTorch is now included. All training/inference in this milestone uses CPU; no GPU or paid service is required.

```bash
.venv/bin/python -m pip install -r recommendation/requirements.txt
.venv/bin/python -m recommendation.train --smoke --output artifacts/retrieval-smoke-own
.venv/bin/python -m recommendation.train --prepared data/prepared-v001 --output artifacts/retrieval-own-v001
```

For the existing chat checkout and prepared data, use `../python-env/bin/python` instead of `.venv/bin/python`, and `data/prepared` instead of `data/prepared-v001`. Choose a new output directory for each run.

The smoke command generates tiny synthetic observations and runs two epochs to exercise the pipeline. Its metrics are not representative recommendation-quality results. A full run uses settings from the `training` section of `config.yaml`, initially ten epochs. Each epoch prints mean training loss and validation Recall/NDCG at K=10,200. The selected epoch maximizes validation Recall@200; ties keep the earlier epoch.

Outputs:

- `checkpoints/epoch-001.pt`, etc.: weights, optimizer, random states, data/mapping fingerprints and metrics for each epoch. Automated resume is not implemented.
- `best_model.pt`: selected model state dictionary, loaded with `weights_only=True`.
- `model_config.json`: architecture, vocabulary sizes, runtime/configuration, selected epoch and fingerprints.
- `training_history.json`: loss, validation metrics and elapsed time per epoch.
- `validation_comparison.json`: model and popular-baseline metrics with identical eligible-user coverage.

These are offline training artifacts, not yet a complete FAISS serving bundle. `model.py` defines separate user/channel Embedding→Linear towers; `sampling.py` chooses uniform negatives outside every user's training-positive set. Training averages pairwise logistic losses per positive example, preserving equal weight for users with fewer available negatives. Separate repeat observations remain positive examples.

Validation uses exact dot-product matrix search over the training catalog, batched by users, with stable index-based score ties. No FAISS or service is needed for this reference evaluation. Test data is not consumed: it remains reserved until the complete chosen pipeline is frozen. A higher validation score is evidence on this offline task, not an online engagement lift.

Native CPU execution has been checked; Docker build/runtime remains unverified on the current laptop. Reproducibility is scoped to the recorded runtime/configuration, not guaranteed across PyTorch versions or platforms.

## Offline FAISS bundle export

Install the updated pinned requirements first. This step uses an already-trained model; it does not train or start a server. For the thirty-epoch experiment in this checkout:

```bash
../python-env/bin/python -m pip install -r recommendation/requirements.txt
../python-env/bin/python -m recommendation.run -m recommendation.export \
  --model artifacts/retrieval-30epochs-v001 \
  --prepared data/prepared \
  --output artifacts/retrieval-bundle-v001 \
  --version retrieval-bundle-v001
../python-env/bin/python -m recommendation.run -m pytest -q
```

Use your own trained directory and interpreter if different. The thirty-epoch output was produced by a separate controlled experiment; the repository training default remains ten epochs. Choose a fresh bundle directory for every export, including when repeating the command. Generated models, indexes and data remain local and ignored by Git.

`recommendation.run` is a small Python launcher. On macOS, the installed PyTorch and FAISS wheels can load separate OpenMP runtimes and abort when used together. The launcher resolves both to PyTorch's bundled runtime by setting the child process's `DYLD_LIBRARY_PATH` before Python starts. It does not import either native library, modify installed binaries, change global shell settings, or enable `KMP_DUPLICATE_LIB_OK`. Elsewhere it forwards to the same interpreter without changing library paths. This compatibility step was verified with actual Torch computation and FAISS search on the laptop; Linux/container execution is still unverified. See the [upstream compatibility issue](https://github.com/pytorch/pytorch/issues/149201).

The bundle contains:

| File | Content |
|---|---|
| `retrieval_model.pt` | Selected weights, loaded with `weights_only=True` |
| `model_config.json` | Architecture, dimensions, selected epoch and training provenance |
| `user_mapping.json`, `channel_mapping.json` | Exact training identity assignments |
| `channel_vectors.npy` | Contiguous float32 channel vectors, row i = internal channel index i |
| `channels.faiss` | Exact `IndexFlatIP` dot-product index, with no normalization |
| `popular_channels.json` | Full training-only popularity snapshot for later fallback |
| `manifest.json` | Bundle version, index metadata, runtime versions and payload checksums |

`export_bundle()` verifies the consumed training inputs against recorded fingerprints and checks mappings before generating vectors. It writes into a temporary sibling directory, validates a complete reload, then publishes the final directory. Failed exports leave no published bundle. Held-out validation/test labels are not needed by export.

`load_bundle(path)` verifies all payload checksums before native index deserialization, then checks model finiteness, mappings, vector dimensions, model/vector/index alignment and popularity IDs. It returns the loaded model, index, vectors, mappings, popularity and manifest for the later service. Only locally trusted bundles are in scope; checksums detect inconsistent or changed files, not authenticate an untrusted manifest.

When searching a small catalog, use `min(k, index.ntotal)` to avoid FAISS padding IDs. Exact search uses learned dot products, not cosine similarity. Floating-point scores should match direct scoring within tolerance; tied scores can change order or membership at the K boundary. This step includes verification searches, not an online Top K API. The best model is copied from training output; its weights are not retrained or updated during export.

## Local retrieval HTTP service

The service loads a trusted exported bundle once at startup, then keeps its model, FAISS index and mappings in memory. Requests do not train, rebuild the index, or read historical datasets. This first version returns retrieval results directly; ranking, Java integration and the frontend are later milestones.

From the repository root, install dependencies and start one worker:

```bash
.venv/bin/python -m pip install -r recommendation/requirements.txt
RECOMMENDER_BUNDLE_DIR=artifacts/retrieval-bundle-v001 \
.venv/bin/python -m recommendation.run -m uvicorn \
  recommendation.serve:app --host 127.0.0.1 --port 8000 --workers 1
```

For the existing chat checkout, replace `.venv/bin/python` with `../python-env/bin/python`. Keep the terminal running; stop it with Ctrl+C. Open `http://127.0.0.1:8000/docs` for interactive API documentation. In another terminal:

```bash
curl -s http://127.0.0.1:8000/health/live
curl -s http://127.0.0.1:8000/health/ready
curl -s http://127.0.0.1:8000/v1/recommendations \
  -H 'Content-Type: application/json' -d '{"user_id":"1","k":10}'
curl -s http://127.0.0.1:8000/v1/recommendations \
  -H 'Content-Type: application/json' -d '{"user_id":"new-user","k":10}'
```

`user_id` must be a string, trimmed to 1–128 characters. These are anonymized dataset identities; application-account mapping is future integration work. `k` defaults to 10 and must be an integer from 1 to 200. Invalid requests return HTTP 422, including numeric strings, floats, booleans and null K values.

A successful response includes a new `request_id` (UUID4), the bundle's `model_version`, `method`, `fallback_reason` and `items`. Each item has a bundle-local string `channel_id`, `channel_name` and `retrieval_score`. Return count is `min(k, catalog_size)`, without duplicates. Known-user scores are raw learned dot products, not probabilities; previously observed channels remain eligible. Results are sorted by descending score, then numeric channel ID for ties within the returned set. FAISS chooses membership at tied K boundaries.

Unknown users get HTTP 200 with `method="popular"`, `fallback_reason="unknown_user"` and null scores. A recoverable inference/search failure uses `fallback_reason="retrieval_error"` with the same validated popularity snapshot; details are logged only on the server.

Liveness returns `{"status":"alive"}`. Readiness returns `{"status":"ready","model_version":"..."}` only after complete bundle validation and a successful personalized warmup. Missing/corrupt artifacts or failed warmup leave the process alive but unready: readiness returns 503 and recommendation requests return 503 with `{"detail":"recommendation service unavailable"}`. Correct configuration and restart; no automatic reload or partial-bundle fallback. Readiness is startup usability, not continuous model-quality monitoring.

Run the suite through the native compatibility launcher:

```bash
.venv/bin/python -m recommendation.run -m pytest -q
```

Optional Docker Compose (Docker must be installed and running):

```bash
docker compose up --build recommender
# Stop with Ctrl+C, then remove the stopped container:
docker compose down
```

Compose uses the existing Python image entry point with a Uvicorn command, binds only localhost port 8000 and mounts the exported bundle read-only. Export the bundle first; Compose refuses to silently create a missing host bundle directory. It starts only the Python service. Native macOS serving is verified; Docker/Linux build and runtime remain unverified on this laptop, which has no Docker executable. No throughput or latency target has been validated yet.
